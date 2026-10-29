"""Repeatable PakFreight Python track. All raw/intermediate frames are private staging."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, shutil, sqlite3
import pandas as pd
ROOT = Path(__file__).resolve().parent
CONTRACT = ['ShipmentID','ShipDate','OriginRaw','DestRaw','WeightKG','FreightCostPKR','StatusRaw']
HEADERS = {
 'marine':['Shipment_ID','Ship_Date','Origin_Port','Dest_Port','Weight_KG','Cost_PKR','Status'],
 'road':['trip_id','trip_date','from_city','to_city','weight_kg','cost_pkr','status'],
 'rail':['Consignment No','Dispatch Date','From Station','To Station','Weight (Tons)','Freight Charges (PKR)','Status']}
MODE = {'marine':1,'rail':2,'road':3}
# Ordered logical design. Physical source steps below preserve inspectable snapshots.
STEPS = ['ConnectSources','LandFaithfulCopy','LogExtraction','ShapeTables','RenameToContract',
         'TrimCleanText','NormalizeStatus','ParseDatesExplicitly','ConvertUnitsSetTypes',
         'AddModeKey','AppendSources','DeduplicateShipmentID','ConformKeys',
         'LoadIndependentDimensions','LoadDimRoute','LoadFactShipment','ReconcileOrRollback']

def pipeline(source, run_name):
    source=Path(source); frames={}; logs=[]; parts={}
    landing=ROOT/'outputs'/'staging'/run_name; landing.mkdir(parents=True,exist_ok=True)
    def keep(name,df): frames[name]=df.copy(deep=True); return df
    for name in ('marine','rail','road'):
        ext='xlsx' if name=='rail' else 'csv'; path=source/f'{name}_shipments.{ext}'
        landed=landing/path.name
        shutil.copyfile(path,landed) # byte-for-byte copy: extraction changes nothing
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==hashlib.sha256(landed.read_bytes()).hexdigest()
        raw=(pd.read_excel(landed,sheet_name='Rail',header=None) if name=='rail'
             else pd.read_csv(landed,header=None,skip_blank_lines=False))
        keep(f'{name}.Source',raw)
        count=len(raw)-(3 if name=='rail' else 1)
        logs.append({'source':path.name,'utc':datetime.now(timezone.utc).isoformat(),'rows_landed':count,'sha256':digest})
        if name=='rail': raw=keep('rail.SkippedTitleRows',raw.iloc[2:].reset_index(drop=True))
        df=raw.iloc[1:].copy(); df.columns=raw.iloc[0].tolist(); df=df.reset_index(drop=True)
        keep(f'{name}.PromotedHeaders',df)
        assert list(df.columns)==HEADERS[name], f'Unexpected schema: {name}'
        if name=='road':
            df=keep('road.RemovedBlankRows',df.loc[~df.isna().all(axis=1)].copy())
            df=keep('road.RemovedTotalRow',df.loc[df.trip_id.astype('string').str.strip().str.upper()!='TOTAL'].copy())
        df=keep(f'{name}.RenamedToContract',df.rename(columns=dict(zip(HEADERS[name],CONTRACT))))
        for c in CONTRACT:
            if c not in ['ShipDate','WeightKG','FreightCostPKR']:
                df[c]=df[c].astype('string').str.replace(r'\s+',' ',regex=True).str.replace(r'[\x00-\x1f]','',regex=True).str.strip()
        df.ShipmentID=df.ShipmentID.str.upper()
        if name=='rail': df.ShipmentID='RL-'+pd.to_numeric(df.ShipmentID).astype('int64').astype(str)
        keep(f'{name}.TrimmedCleanedText',df)
        df.StatusRaw=df.StatusRaw.str.title(); keep(f'{name}.NormalizedStatus',df)
        if name=='marine': df.ShipDate=pd.to_datetime(df.ShipDate,format='%d/%m/%Y',errors='raise')
        elif name=='road': df.ShipDate=pd.to_datetime(df.ShipDate,format='%Y-%m-%d',errors='raise')
        else: df.ShipDate=pd.to_datetime(df.ShipDate,errors='raise') # native Excel dates
        keep(f'{name}.ParsedDates',df)
        for c in ['WeightKG','FreightCostPKR']: df[c]=pd.to_numeric(df[c],errors='raise')
        if name=='rail': df.WeightKG=df.WeightKG*1000
        for c in ['WeightKG','FreightCostPKR']:
            assert (df[c]%1==0).all(); df[c]=df[c].astype('int64')
        keep(f'{name}.ConvertedUnitsSetTypes',df)
        assert list(df.columns)==CONTRACT # seven BEFORE derived ModeKey
        df['ModeKey']=MODE[name]; parts[name]=keep(f'{name}.AddedModeKey',df)
    dims={n:pd.read_csv(ROOT/'data/dims'/f'{n}.csv') for n in ['DimDate','DimCity','DimMode','DimStatus','DimRoute']}
    alias=(dims['DimCity'][['CityKey','CityName','RawAliases']].assign(RawAliases=lambda d:d.RawAliases.str.split(' | ',regex=False)).explode('RawAliases').dropna(subset=['RawAliases']).rename(columns={'RawAliases':'RawSpelling'}))
    alias.RawSpelling=alias.RawSpelling.str.strip(); alias=alias[alias.RawSpelling.ne('')]
    assert len(alias)==23 and alias.CityKey.nunique()==14 and alias.RawSpelling.is_unique
    keep('AliasLookup',alias)
    fact=keep('Appended',pd.concat(parts.values(),ignore_index=True))
    duplicates=fact[fact.duplicated('ShipmentID',keep=False)].copy()
    for _, group in duplicates.groupby('ShipmentID'):
        assert len(group.drop_duplicates())==1, 'Conflicting duplicate: manual business review required'
    fact=keep('Deduplicated',fact.drop_duplicates(subset=['ShipmentID']).copy())
    for raw,key in [('OriginRaw','OriginCityKey'),('DestRaw','DestCityKey')]:
        fact=fact.merge(alias[['RawSpelling','CityKey']].rename(columns={'RawSpelling':raw,'CityKey':key}),on=raw,how='left',validate='many_to_one')
        fact[key]=fact[key].fillna(-1).astype('int64'); keep(f'Conformed{key}',fact)
    unknown=fact.loc[(fact.OriginCityKey==-1)|(fact.DestCityKey==-1)].copy()
    dates=dims['DimDate'][['DateKey','FullDate']].copy(); dates['ShipDate']=pd.to_datetime(dates.pop('FullDate'),format='%Y-%m-%d')
    fact=fact.merge(dates,on='ShipDate',how='left',validate='many_to_one')
    assert fact.DateKey.notna().all(), 'Date outside supplied dimension'
    fact=fact.merge(dims['DimStatus'][['StatusKey','StatusName']],left_on='StatusRaw',right_on='StatusName',how='left',validate='many_to_one').drop(columns='StatusName')
    fact.StatusKey=fact.StatusKey.fillna(-1).astype('int64')
    fact=fact.merge(dims['DimRoute'][['RouteKey','OriginCityKey','DestCityKey']],on=['OriginCityKey','DestCityKey'],how='left',validate='many_to_one')
    fact.RouteKey=fact.RouteKey.fillna(-1).astype('int64')
    keep('FactStaging',fact)
    return dict(fact=fact,parts=parts,frames=frames,log=pd.DataFrame(logs),alias=alias,dims=dims,unknown=unknown,duplicates=duplicates)

def checks(run,night=1):
    f=run['fact']; expected=[7,295250,3,'2026-02-13',34 if night==1 else 35,0 if night==1 else 1,578650 if night==1 else 584950,4808000 if night==1 else 4860000]
    actual=[7 if all(list(run['frames'][f'{n}.ConvertedUnitsSetTypes'].columns)==CONTRACT for n in MODE) else -1,
            int(run['parts']['rail'].WeightKG.sum()),f.StatusRaw.nunique(),f.ShipDate.max().strftime('%Y-%m-%d'),len(f),len(run['unknown']),int(f.WeightKG.sum()),int(f.FreightCostPKR.sum())]
    assert set(f.ShipDate.dt.month)=={2} and set(f.ShipDate.dt.year)=={2026}
    table=pd.DataFrame({'Check':['Contract columns per source','Rail kg','Status values','Latest date','Fact rows','Unknown city rows','Weight kg','Cost PKR'],'Actual':actual,'Expected':expected})
    table['Result']=['PASS' if a==b else 'FAIL' for a,b in zip(actual,expected)]
    # Unknown count is reported; fixture verification is separate from pipeline policy.
    for i in [0,1,2,3,4,6,7]: assert actual[i]==expected[i],table.iloc[i].to_dict()
    print(f'Night {night}: Unknown city rows = {actual[5]}')
    return table

def publish(run,night):
    """Validated six-table star. Transactional SQLite replacement; idempotent reruns."""
    out=ROOT/'outputs'/f'night{night}'; out.mkdir(parents=True,exist_ok=True)
    f=run['fact']; tables=dict(run['dims'],FactShipment=f)
    db=sqlite3.connect(out/'PakFreight.sqlite'); db.execute('BEGIN')
    try:
        for name,df in tables.items():
            for c in df.columns: assert c.replace('_','').isalnum()
            db.execute(f'DROP TABLE IF EXISTS "{name}"')
            defs=[]
            for c in df.columns:
                typ='INTEGER' if pd.api.types.is_integer_dtype(df[c]) else ('REAL' if pd.api.types.is_numeric_dtype(df[c]) else 'TEXT')
                pk=' PRIMARY KEY' if c==({'FactShipment':'ShipmentID'}.get(name,name.replace('Dim','')+'Key')) else ''
                defs.append(f'"{c}" {typ}{pk}')
            db.execute(f'CREATE TABLE "{name}" ({", ".join(defs)})')
            values=df.copy()
            for c in values:
                if pd.api.types.is_datetime64_any_dtype(values[c]): values[c]=values[c].dt.strftime('%Y-%m-%d')
            rows=[tuple(None if pd.isna(v) else (v.item() if hasattr(v,'item') else v) for v in row) for row in values.itertuples(index=False,name=None)]
            db.executemany(f'INSERT INTO "{name}" VALUES ({",".join(["?"]*len(df.columns))})',rows)
        for col,dim,key in [('OriginCityKey','DimCity','CityKey'),('DestCityKey','DimCity','CityKey'),('DateKey','DimDate','DateKey'),('ModeKey','DimMode','ModeKey'),('StatusKey','DimStatus','StatusKey'),('RouteKey','DimRoute','RouteKey')]:
            assert db.execute(f'SELECT COUNT(*) FROM FactShipment f LEFT JOIN {dim} d ON f.{col}=d.{key} WHERE d.{key} IS NULL').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*),SUM(WeightKG),SUM(FreightCostPKR) FROM FactShipment').fetchone()==(len(f),int(f.WeightKG.sum()),int(f.FreightCostPKR.sum()))
        db.commit()
    except Exception: db.rollback(); raise
    finally: db.close()
    for name,df in tables.items(): df.to_csv(out/f'{name}.csv',index=False)
    run['log'].to_csv(out/'extract_log.csv',index=False)
    run['unknown'].to_csv(out/'unknown_city_rows.csv',index=False)
    run['duplicates'].to_csv(out/'duplicate_audit.csv',index=False)
    run['alias'].to_csv(out/'AliasLookup_derived.csv',index=False)
    checks(run,night).to_csv(out/'validation.csv',index=False)

if __name__=='__main__':
    for night,source in [(1,ROOT/'data/source'),(2,ROOT/'data/source/night2')]:
        run=pipeline(source,f'night{night}'); print(checks(run,night).to_string(index=False)); publish(run,night)
