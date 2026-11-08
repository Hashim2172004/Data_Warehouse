from pathlib import Path
import pandas as pd, numpy as np, json, hashlib
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)
def read(name): return pd.read_csv(DATA/name)
def norm(v): return '' if pd.isna(v) else str(v).strip().casefold()
def run_pipeline():
    # S01 Extract and shape without correcting source values.
    columns=['ShipmentID','ShipDate','OriginCity','DestCity','WeightKG','FreightCostPKR','Status','CustomerID']
    specs=[('marine_april.csv','Marine',['Shipment_ID','Ship_Date','Origin_Port','Dest_Port','Weight_KG','Cost_PKR','Status','Customer_Ref']),('rail_april.xlsx','Rail',['consignment_no','date','from_station','to_station','net_tons','freight_charges','consignment_status','customer_code']),('road_april.csv','Road',['trip_id','trip_date','from_city','to_city','weight_kg','cost_pkr','status','customer_id'])]
    pieces=[]; structural=[]
    for filename,mode,src in specs:
        raw=pd.read_excel(DATA/filename,header=2) if mode=='Rail' else pd.read_csv(DATA/filename,skip_blank_lines=False)
        digest=hashlib.sha256((DATA/filename).read_bytes()).hexdigest()
        keep=~raw.isna().all(axis=1)
        if mode=='Road': keep &= raw.trip_id.fillna('').str.strip().ne('TOTAL')
        for i,row in raw[~keep].iterrows(): structural.append({'SourceFile':filename,'Locator':f'line {i+2}','Reason':'Blank line' if row.isna().all() else 'TOTAL footer'})
        frame=raw.loc[keep,src].copy(); frame.columns=columns
        frame['SourceMode']=mode;frame['SourceFile']=filename
        frame['Locator']=[f'Consignments!row {i+4}' if mode=='Rail' else f'line {i+2}' for i in frame.index]
        frame['SourceSHA256']=digest
        frame['RawRecord']=[json.dumps(raw.loc[i].to_dict(),default=str) for i in frame.index]
        pieces.append(frame)
    filename='courier_april.json'; payload=json.loads((DATA/filename).read_text()); digest=hashlib.sha256((DATA/filename).read_bytes()).hexdigest(); rows=[]
    for i,r in enumerate(payload['consignments']):
        rows.append([r.get('consignment'),r.get('booked_at'),r.get('pickup',{}).get('city'),r.get('dropoff',{}).get('city'),r.get('weight_grams'),r.get('charge',{}).get('amount'),r.get('status_code'),r.get('customer',{}).get('ref'),'Courier',filename,f'$.consignments[{i}]',digest,json.dumps(r)])
    pieces.append(pd.DataFrame(rows,columns=columns+['SourceMode','SourceFile','Locator','SourceSHA256','RawRecord']))
    staging=pd.concat(pieces,ignore_index=True)
    # S02 Conform city/status/customer lookups; preserve raw staging separately.
    cities=read('DimCity(4).csv'); aliases=read('alias_lookup(2).csv'); base=read('DimCustomer.csv'); status=read('DimStatus(4).csv'); changes=read('customer_changes.csv')
    alias_map={norm(r.RawSpelling):r.CityKey for r in aliases.itertuples()}
    city_names=cities.set_index('CityKey').CityName.to_dict(); provinces=cities.set_index('CityName').Province.to_dict()
    status_map={norm(r.StatusName):r.StatusKey for r in status.itertuples() if r.StatusKey!=-1}
    known=set(base.CustomerID.dropna())
    name_to_id={}
    for r in base.dropna(subset=['CustomerID']).itertuples():
        for alias in str(r.RawAliases).split('|'):name_to_id[' '.join(norm(alias).split())]=r.CustomerID
    registry=read('customers_master(1).csv')
    customer_alias={r.CustomerID:name_to_id.get(' '.join(norm(r.CustomerName).split()),r.CustomerID) for r in registry.itertuples()}
    t=staging.copy()
    t['ShipmentID']=t.ShipmentID.map(lambda x:'' if pd.isna(x) else str(x).strip().upper())
    t.loc[t.SourceMode.eq('Rail'),'ShipmentID']='RL-'+t.loc[t.SourceMode.eq('Rail'),'ShipmentID'].str.replace(r'\.0$','',regex=True)
    t['CustomerID']=t.CustomerID.map(lambda x:'' if pd.isna(x) else str(x).strip().upper())
    t['CustomerID']=t.CustomerID.map(lambda v:customer_alias.get(v,v))
    # S03 Normalize units and dates in transform, including local courier day.
    def parse_date(r):
        try:
            fmt={'Marine':'%d/%m/%Y','Road':'%Y-%m-%d'}.get(r.SourceMode)
            d=pd.to_datetime(r.ShipDate,format=fmt,errors='raise')
            if pd.isna(d): return pd.NaT
            if d.tzinfo is not None: d=d.tz_convert('Asia/Karachi').tz_localize(None)
            return d.normalize()
        except (ValueError,TypeError):return pd.NaT
    t['ShipDate']=t.apply(parse_date,axis=1)
    t['WeightKG']=pd.to_numeric(t.WeightKG,errors='coerce')*t.SourceMode.map({'Marine':1,'Rail':1000,'Road':1,'Courier':.001})
    t['FreightCostPKR']=pd.to_numeric(t.FreightCostPKR,errors='coerce')
    for field,key in [('OriginCity','OriginCityKey'),('DestCity','DestCityKey')]:t[key]=t[field].map(lambda v:alias_map.get(norm(v),-1))
    t['StatusKey']=[({1:1,2:2,3:3}.get(int(v),-1) if pd.notna(v) else -1) if m=='Courier' else status_map.get(norm(v),-1) for v,m in zip(t.Status,t.SourceMode)]
    failures=pd.DataFrame(index=t.index)
    failures['ShipmentID']=t.ShipmentID.eq('')
    failures['ShipDate']=t.ShipDate.isna()|~t.ShipDate.between('2026-04-01','2026-04-30')
    failures['OriginCity']=t.OriginCityKey.eq(-1); failures['DestCity']=t.DestCityKey.eq(-1)
    failures['WeightKG']=t.WeightKG.isna()|t.WeightKG.le(0)|t.WeightKG.gt(t.SourceMode.map({'Marine':25000,'Rail':35000,'Road':8000,'Courier':8000}))
    failures['FreightCostPKR']=t.FreightCostPKR.isna();failures['Status']=t.StatusKey.eq(-1);failures['CustomerID']=~t.CustomerID.isin(known)
    # S04 Profile raw values against the conformed rules, without mutating staging.
    prof=[]
    for c in columns:
        raw=staging[c]; blank=raw.isna()|raw.astype(str).str.strip().eq('')
        normalized=t[c]
        text_only=raw.astype(str).ne(normalized.astype(str))&~failures[c]&~blank if c in ['ShipmentID','OriginCity','DestCity','Status','CustomerID'] else pd.Series(False,index=t.index)
        if c in ['OriginCity','DestCity']:text_only=raw.map(lambda v:str(v) != city_names.get(alias_map.get(norm(v),-1),str(v)))&~failures[c]&~blank
        if c=='Status':text_only=pd.Series([m!='Courier' and str(v)!=status.set_index('StatusKey').StatusName.get(k,'') for v,m,k in zip(raw,t.SourceMode,t.StatusKey)])&~failures[c]
        prof.append([c,int(blank.sum()),raw.nunique(dropna=True),int(failures[c].sum()),int(text_only.sum())])
    profile=pd.DataFrame(prof,columns=['Column','Blanks','DistinctRaw','RuleFailures','TextTransformOnly'])
    # S05 Reject invalid measures, dates or IDs. All failed reasons retained.
    reason_masks={'WEIGHT_NOT_NUMERIC':t.WeightKG.isna(),'WEIGHT_NONPOSITIVE':t.WeightKG.le(0),'WEIGHT_OVER_CAPACITY':t.WeightKG.gt(t.SourceMode.map({'Marine':25000,'Rail':35000,'Road':8000,'Courier':8000})),'MISSING_SHIPMENT_ID':failures.ShipmentID,'INVALID_APRIL_DATE':failures.ShipDate,'COST_NOT_NUMERIC':failures.FreightCostPKR}
    invalid=pd.DataFrame(reason_masks).any(axis=1)
    reject=t.loc[invalid,['SourceFile','SourceSHA256','Locator','ShipmentID','RawRecord']].copy()
    reject['ReasonCode']=[';'.join(k for k,v in reason_masks.items() if v.loc[i]) for i in reject.index]
    reject['LoadBatch']='2026-04'
    good=t.loc[~invalid].copy()
    # S06 Deduplicate only same source + normalized shipment ID.
    same=good.duplicated(['SourceFile','ShipmentID'],keep='first');dups=good.loc[same].copy();dups['RemovalReason']='Same source / ShipmentID';good=good.loc[~same].copy()
    # S07 Remove one courier record per matching road consignment, never road-road.
    bk=['ShipDate','OriginCityKey','DestCityKey','WeightKG','CustomerID']
    road=good.loc[good.SourceMode.eq('Road')].copy(); courier=good.loc[good.SourceMode.eq('Courier')].copy()
    road['Occurrence']=road.groupby(bk,dropna=False).cumcount();courier['Occurrence']=courier.groupby(bk,dropna=False).cumcount()
    matches=courier.reset_index().merge(road[bk+['Occurrence','ShipmentID']],on=bk+['Occurrence'],suffixes=('_Courier','_Road'))
    cross=good.loc[matches['index']].copy();cross['RemovalReason']='Road / Courier same consignment';dups=pd.concat([dups,cross]);good=good.drop(index=cross.index)
    # S08 Build deterministic Type 2 snapshot. Rebuild from immutable carryforward on each run.
    dim=base.copy();dim['ValidFrom']='1900-01-01';dim['ValidTo']='9999-12-31';dim['RowIsCurrent']='Yes'
    for change in changes.itertuples():
        ix=dim.index[(dim.CustomerID==change.CustomerID)&dim.RowIsCurrent.eq('Yes')][0]
        new=dim.loc[ix].copy();effective=pd.Timestamp(change.EffectiveDate)
        dim.loc[ix,['ValidTo','RowIsCurrent']]=[(effective-pd.Timedelta(days=1)).strftime('%Y-%m-%d'),'No']
        new['CustomerKey']=int(dim.CustomerKey.max())+1;new['ValidFrom']=change.EffectiveDate;new['ValidTo']='9999-12-31';new['RowIsCurrent']='Yes'
        attr='HQCity' if change.Attribute=='City' else change.Attribute;new[attr]=change.NewValue
        if attr=='HQCity':new['HQProvince']=provinces[change.NewValue]
        dim=pd.concat([dim,pd.DataFrame([new])],ignore_index=True)
    def customer_key(r):
        d=r.ShipDate.strftime('%Y-%m-%d'); candidates=dim.loc[dim.CustomerID.eq(r.CustomerID)&dim.ValidFrom.le(d)&dim.ValidTo.ge(d)]
        return int(candidates.iloc[0].CustomerKey) if len(candidates)==1 else -1
    good['CustomerKey']=good.apply(customer_key,axis=1)
    # S09 Add new lanes and Courier; retain all old keys.
    route=read('DimRoute(4).csv'); existing=set(zip(route.OriginCityKey,route.DestCityKey))
    for a,b in sorted(set(zip(good.OriginCityKey,good.DestCityKey))-existing):
        if a==-1 or b==-1:continue
        route.loc[len(route)]=[int(route.RouteKey.max())+1,a,b,f'{city_names[a]} -> {city_names[b]}','Not supplied','Not supplied']
    rmap={(r.OriginCityKey,r.DestCityKey):r.RouteKey for r in route.itertuples()}
    good['RouteKey']=[rmap.get((a,b),-1) for a,b in zip(good.OriginCityKey,good.DestCityKey)]
    mode=read('DimMode(4).csv');mode.loc[len(mode)]=[4,'Courier','ShaheenEx Courier Services','Up to 8 t','Parcel / subcontract road','No']
    good['ModeKey']=good.SourceMode.map({'Marine':1,'Rail':2,'Road':3,'Courier':4});good['DateKey']=good.ShipDate.dt.strftime('%Y%m%d').astype(int)
    feb=read('FactShipment_Feb.csv');march=read('FactShipment_March.csv');good['ShipmentKey']=np.arange(max(feb.ShipmentKey.max(),march.ShipmentKey.max())+1,max(feb.ShipmentKey.max(),march.ShipmentKey.max())+1+len(good))
    april=good[feb.columns].copy()
    for measure in ['WeightKG','FreightCostPKR']:
        assert april[measure].eq(april[measure].round()).all()
        april[measure]=april[measure].astype('int64')
    allfact=pd.concat([feb,march,april],ignore_index=True)
    # S10 Extend calendar without changing Q1 attributes.
    dates=read('DimDate(4).csv');newdates=[]
    for d in pd.date_range('2026-04-01','2026-04-30'):
        newdates.append([int(d.strftime('%Y%m%d')),d.strftime('%Y-%m-%d'),d.year,2,4,'April',d.day,(d.dayofweek+1)%7+1,d.day_name(),'Yes' if d.dayofweek>=5 else 'No','No'])
    dates=pd.concat([dates,pd.DataFrame(newdates,columns=dates.columns)],ignore_index=True)
    # S11 Publish detailed auditable tables. Staging remains an in-memory connection-only equivalent.
    outputs={'FactShipment_April':april,'RejectLog_April':reject,'DimCustomer':dim,'DimDate':dates,'DimRoute':route,'DimMode':mode,'DimCity':cities,'DimStatus':status,'FactShipment_FebToApril':allfact,'DuplicateLog_April':dups,'StructuralRemovalLog':pd.DataFrame(structural),'SourceProfile':profile}
    for name,table in outputs.items():table.to_csv(OUT/f'{name}.csv',index=False)
    return locals()
if __name__=='__main__':
    x=run_pipeline()
    for k in ['staging','reject','dups','good','dim','route']:print(k,len(x[k]))
    print(x['profile'].to_string(index=False));print(x['april'][['WeightKG','FreightCostPKR']].sum());print(x['reject'].ReasonCode.value_counts())
