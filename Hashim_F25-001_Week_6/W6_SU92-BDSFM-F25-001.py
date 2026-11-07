# %% Setup
"""PakFreight Week 6. Hashim Nadeem, SU92-BDSFM-F25-001, BS DS-7a.
Run from this folder. Python/pandas implementation; source inputs remain unchanged.
"""
from pathlib import Path
import csv, json, re, sqlite3
from datetime import datetime, timezone
import numpy as np
import pandas as pd
try:
    BASE = Path(__file__).resolve().parent
except NameError:
    BASE = Path.cwd()
DATA = BASE / 'data'
OUT = BASE / 'outputs'
OUT.mkdir(exist_ok=True)
CONTRACT = ['ShipmentID','ShipDate','Origin','Destination','WeightKG','FreightCostPKR','StatusRaw','CustomerID']
RUN_ID = 'PakFreight-March-2026-v1'
AUDIT_TIME = datetime.now(timezone.utc).isoformat()
pd.set_option('display.max_columns', 15)

# %% Step 01 - Immutable extraction with physical row lineage
# CSV reader keeps the empty record. Rail header is physical row 3.
SPECS = [
 ('marine_march.csv','Marine',['Shipment_ID','Ship_Date','Origin_Port','Dest_Port','Weight_KG','Cost_PKR','Status','Customer_Ref']),
 ('rail_march.xlsx','Rail',['consignment_no','date','from_station','to_station','net_tons','freight_charges','consignment_status','customer_code']),
 ('road_march.csv','Road',['trip_id','trip_date','from_city','to_city','weight_kg','cost_pkr','status','customer_id'])]
frames=[]
for filename, mode, source_cols in SPECS:
    path=DATA/'march'/filename
    if path.suffix=='.csv':
        with path.open(newline='', encoding='utf-8-sig') as f:
            reader=csv.reader(f); header=next(reader); records=[]
            for row in reader:
                line=reader.line_num
                row=(row+['']*len(header))[:len(header)]
                records.append(dict(zip(header,row), SourceRow=line))
        df=pd.DataFrame(records)
    else:
        df=pd.read_excel(path,header=2,keep_default_na=False,dtype=object)
        df['SourceRow']=np.arange(4,len(df)+4)
    raw_cols=list(source_cols)
    df['RawRecord']=df[raw_cols].apply(lambda r:json.dumps(r.to_dict(),default=str,ensure_ascii=False),axis=1)
    df=df.rename(columns=dict(zip(source_cols,CONTRACT)))
    df['SourceFile']=filename; df['SourceMode']=mode
    frames.append(df[CONTRACT+['SourceFile','SourceRow','SourceMode','RawRecord']])
landing=pd.concat(frames,ignore_index=True)
landing.to_csv(OUT/'RawLanding.csv',index=False)
print('Physical landing records:',len(landing))

# %% Step 02 - Shape contract; retain structural exceptions separately
# Brief inconsistency: 261 + 315 + 708 = 1284 data rows, but road has
# two additional structural records. Nothing is silently lost: 1286 = 1284 + 2.
all_blank=landing[CONTRACT].apply(lambda c:c.astype(str).str.strip().eq('')).all(axis=1)
footer=landing.ShipmentID.astype(str).str.strip().str.upper().eq('TOTAL')
structural=landing[all_blank|footer].copy()
structural['Reason']=np.where(footer[all_blank|footer],'TOTAL footer; not a consignment','Blank structural record')
structural.to_csv(OUT/'StructuralAudit.csv',index=False)
staging=landing[~(all_blank|footer)].copy().reset_index(drop=True)
staging.to_csv(OUT/'StagingRaw.csv',index=False)
assert len(landing)==len(staging)+len(structural)
print('Staging data rows:',len(staging),'Structural records retained:',len(structural))

# %% Step 03 - Profile untouched contract values
aliases=pd.read_csv(DATA/'alias_lookup.csv',keep_default_na=False)
registry=pd.read_csv(DATA/'customers_master.csv',keep_default_na=False)
dim_city=pd.read_csv(DATA/'dims/DimCity.csv',keep_default_na=False)
dim_route=pd.read_csv(DATA/'dims/DimRoute.csv',keep_default_na=False)
dim_mode=pd.read_csv(DATA/'dims/DimMode.csv',keep_default_na=False)
dim_status=pd.read_csv(DATA/'dims/DimStatus.csv',keep_default_na=False)
stale_date=pd.read_csv(DATA/'dims/DimDate.csv',keep_default_na=False)
def trim(v): return str(v).strip()
def norm(v): return ' '.join(trim(v).upper().split())
def blank(v): return trim(v)==''
def decimal_number(v):
    # Source contract accepts ordinary signed decimal numbers only.
    # Scientific notation is not issued by these source systems; 1.2e4 is quarantined.
    if isinstance(v,(int,float,np.number)): return float(v) if np.isfinite(v) else np.nan
    t=trim(v)
    return float(t) if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)',t) else np.nan

def parse_date(row):
    v=row.ShipDate
    if isinstance(v,(datetime,pd.Timestamp)): return pd.Timestamp(v).normalize()
    fmt='%d/%m/%Y' if row.SourceMode=='Marine' else '%Y-%m-%d'
    try:return pd.Timestamp(datetime.strptime(trim(v),fmt))
    except (ValueError,TypeError):return pd.NaT

id_norm=staging.ShipmentID.map(norm)
parsed_dates=staging.apply(parse_date,axis=1)
weights=staging.WeightKG.map(decimal_number)
costs=staging.FreightCostPKR.map(decimal_number)
alias_key=dict(zip(aliases.RawSpelling.map(norm),aliases.CityKey))
status_key=dict(zip(dim_status.StatusName.map(norm),dim_status.StatusKey))
origin=staging.Origin.map(norm).map(alias_key)
destination=staging.Destination.map(norm).map(alias_key)
status=staging.StatusRaw.map(norm).map(status_key)
failures=pd.DataFrame({
 'ShipmentID':id_norm.eq('') | (id_norm.duplicated() & id_norm.ne('')),
 'ShipDate':parsed_dates.isna() | ~parsed_dates.between('2026-03-01','2026-03-31'),
 'Origin':origin.isna(),'Destination':destination.isna(),
 'WeightKG':weights.isna() | weights.le(0),
 'FreightCostPKR':costs.isna(),'StatusRaw':status.isna(),
 'CustomerID':~staging.CustomerID.map(trim).isin(registry.CustomerID)})
city_names=dict(zip(dim_city.CityKey,dim_city.CityName))
text_transforms={
 'ShipmentID':((staging.ShipmentID.astype(str)!=id_norm)&id_norm.ne('')).sum(),
 'Origin':(origin.notna() & staging.Origin.astype(str).ne(origin.map(city_names))).sum(),
 'Destination':(destination.notna() & staging.Destination.astype(str).ne(destination.map(city_names))).sum(),
 'StatusRaw':(status.notna() & staging.StatusRaw.astype(str).ne(status.map(dict(zip(dim_status.StatusKey,dim_status.StatusName))))).sum()}
profile=pd.DataFrame([{'Column':c,'Blanks':int(staging[c].map(blank).sum()),
 'DistinctRaw':int(staging.loc[~staging[c].map(blank),c].map(str).nunique()),
 'RuleFailures':int(failures[c].sum()),'NeedsTextTransform':text_transforms.get(c,'—')} for c in CONTRACT])
profile.to_csv(OUT/'T2_Profile.csv',index=False)
assert profile.RuleFailures.sum()==105
print(profile.to_string(index=False))

# %% Step 04 - Reject only unrecoverable consignment fields
# Retain all applicable reasons, not merely the first failed validation.
reasons=[]
for idx,row in staging.iterrows():
    r=[]
    if id_norm.at[idx]=='':r.append('MISSING_SHIPMENT_ID')
    if failures.at[idx,'ShipDate']:r.append('INVALID_MARCH_DATE')
    if pd.isna(weights.at[idx]):r.append('NONNUMERIC_WEIGHT')
    elif weights.at[idx]<=0:r.append('NONPOSITIVE_WEIGHT')
    if pd.isna(costs.at[idx]):r.append('NONNUMERIC_COST')
    if failures.at[idx,'CustomerID']:r.append('UNRESOLVED_CUSTOMER')
    reasons.append(';'.join(r))
reasons=pd.Series(reasons,index=staging.index)
reject_mask=reasons.ne('')
reject_log=pd.DataFrame({
 'BatchID':RUN_ID,'SourceFile':staging.loc[reject_mask,'SourceFile'],
 'SourceRow':staging.loc[reject_mask,'SourceRow'],
 'RawRecord':staging.loc[reject_mask,'RawRecord'],
 'ReasonCode':reasons[reject_mask],'RejectedAtUTC':AUDIT_TIME})
reject_log.to_csv(OUT/'RejectLog.csv',index=False)
loadable=staging.loc[~reject_mask].copy()
print('Reject classes:',reject_log.ReasonCode.value_counts().to_dict())

# %% Step 05 - Conform types and source-specific units; canonical consignment ID
clean=loadable.copy()
clean['ShipmentID']=id_norm.loc[clean.index]
rail=clean.SourceMode.eq('Rail')
clean.loc[rail,'ShipmentID']=clean.loc[rail,'ShipmentID'].map(lambda v:v if v.startswith('RL-') else 'RL-'+v)
clean['ShipDate']=parsed_dates.loc[clean.index]
clean['WeightKG']=weights.loc[clean.index]*np.where(rail,1000,1)
clean['FreightCostPKR']=costs.loc[clean.index]
clean['OriginCityKey']=origin.loc[clean.index].fillna(-1).astype(int)
clean['DestCityKey']=destination.loc[clean.index].fillna(-1).astype(int)
clean['StatusKey']=status.loc[clean.index].fillna(-1).astype(int)

# %% Step 06 - Deduplicate at one row per canonical consignment
raw_exact=len(loadable.drop_duplicates(CONTRACT))
raw_id=len(loadable.drop_duplicates('ShipmentID'))
dup_mask=clean.ShipmentID.duplicated(keep='first')
removed=clean.loc[dup_mask].copy()
keepers=clean.loc[~dup_mask].copy()
first_source=keepers.set_index('ShipmentID')[['SourceFile','SourceRow']].to_dict('index')
removed['RetainedSource']=removed.ShipmentID.map(lambda k:json.dumps(first_source[k]))
removed['Reason']='DUPLICATE_CANONICAL_SHIPMENT_ID'
removed.to_csv(OUT/'DuplicateLog.csv',index=False)

# %% Step 07 - Conform customer businesses and preserve all registry aliases
# Match spelling variants using an explicit, reproducible business-name rule.
# This is the six known alias pairs in this exercise, not a universal identity algorithm.
def business_name(v):
    t=norm(v)
    t=re.sub(r'\(PVT\)',' ',t)
    t=re.sub(r'[^A-Z0-9 ]',' ',t)
    t=re.sub(r'\b(?:LIMITED|LTD)\b',' ',t)
    t=re.sub(r'\bCO\b','COMPANY',t)
    return ' '.join(t.split())
registry['BusinessName']=registry.CustomerName.map(business_name)
registry['CustomerKey']=pd.factorize(registry.BusinessName,sort=False)[0]+1
customer_aliases=registry.copy()
customer_aliases.to_csv(OUT/'CustomerAliases.csv',index=False)
rows=[]
for key,g in registry.groupby('CustomerKey',sort=True):
    first=g.iloc[0]
    rows.append({'CustomerKey':key,'CustomerName':first.CustomerName,'City':first.City,'Sector':first.Sector,
      'SignedUp':g.SignedUp.min(),'CustomerIDAliases':' | '.join(g.CustomerID),
      'NameAliases':' | '.join(g.CustomerName)})
dim_customer=pd.DataFrame([{'CustomerKey':-1,'CustomerName':'Unknown','City':'Unknown','Sector':'Unknown',
 'SignedUp':'','CustomerIDAliases':'','NameAliases':''}]+rows)
customer_lookup=dict(zip(registry.CustomerID,registry.CustomerKey))
keepers['CustomerKey']=keepers.CustomerID.map(trim).map(customer_lookup).fillna(-1).astype(int)

# %% Step 08 - Build gapless quarter date dimension and resolve all foreign keys
# The required 90 rows imply 2026 Q1, not only March's 31 days.
dates=pd.date_range('2026-01-01','2026-03-31')
dim_date=pd.DataFrame({'DateKey':dates.strftime('%Y%m%d').astype(int),'FullDate':dates.strftime('%Y-%m-%d'),
 'Year':dates.year,'Quarter':dates.quarter,'MonthNumber':dates.month,'MonthName':dates.month_name(),
 'DayOfMonth':dates.day,'DayOfWeek':(dates.dayofweek+1)%7+1,'DayName':dates.day_name(),
 'IsWeekend':np.where(dates.dayofweek>=5,'Yes','No'),
 'IsHoliday':'Unknown'})
# No holiday calendar was supplied; do not invent public holiday flags.
keepers['DateKey']=keepers.ShipDate.dt.strftime('%Y%m%d').astype(int)
keepers['ModeKey']=keepers.SourceMode.map(dict(zip(dim_mode.ModeName,dim_mode.ModeKey)))
route_lookup={(r.OriginCityKey,r.DestCityKey):r.RouteKey for r in dim_route.itertuples()}
keepers['RouteKey']=[route_lookup.get((o,d),-1) for o,d in zip(keepers.OriginCityKey,keepers.DestCityKey)]
keepers['ShipmentCount']=1
# Eight identifiers (seven dimension FKs + consignment ID), three additive facts.
FACT_COLS=['ShipmentID','DateKey','OriginCityKey','DestCityKey','RouteKey','ModeKey','StatusKey','CustomerKey',
 'WeightKG','FreightCostPKR','ShipmentCount']
fact=keepers[FACT_COLS].reset_index(drop=True)
unknown_rows=keepers[(keepers.OriginCityKey==-1)|(keepers.DestCityKey==-1)|(keepers.StatusKey==-1)].copy()
unknown_rows[['ShipmentID','SourceFile','SourceRow','Origin','Destination','StatusRaw','OriginCityKey','DestCityKey','StatusKey']].to_csv(OUT/'UnknownLookupAudit.csv',index=False)
for name,df in [('FactShipment_March',fact),('DimCustomer',dim_customer),('DimDate',dim_date),
 ('DimCity',dim_city),('DimRoute',dim_route),('DimMode',dim_mode),('DimStatus',dim_status)]:
    df.to_csv(OUT/f'{name}.csv',index=False)

# %% Step 09 - Reconciliation, ten definition-of-done assertions and referential checks
actual=[len(staging),len(reject_log),len(removed),len(fact),fact.WeightKG.sum(),fact.FreightCostPKR.sum(),
 int(((fact.OriginCityKey==-1)|(fact.DestCityKey==-1)).sum()),int((fact.StatusKey==-1).sum()),
 len(dim_customer[dim_customer.CustomerKey!=-1]),len(dim_date)]
expected=[1284,24,60,1200,17542050,147037000,14,7,40,90]
labels=['Extracted data rows','Rejected','Deduplicated','Fact rows','WeightKG','FreightCostPKR',
 'Unknown city rows','Unknown status rows','Known customers','Calendar days']
checks=pd.DataFrame({'Check':labels,'Actual':actual,'Expected':expected})
checks['Pass']=checks.Actual.eq(checks.Expected)
checks.to_csv(OUT/'T7_Checks.csv',index=False)
for row in checks.itertuples():assert row.Pass, f'{row.Check}: {row.Actual} != {row.Expected}'
assert len(staging)-len(fact)-len(reject_log)-len(removed)==0
assert fact.ShipmentID.is_unique and fact.notna().all().all()
assert (fact.FreightCostPKR<0).sum()==3
for fk,dim,pk in [('DateKey',dim_date,'DateKey'),('OriginCityKey',dim_city,'CityKey'),
 ('DestCityKey',dim_city,'CityKey'),('RouteKey',dim_route,'RouteKey'),('ModeKey',dim_mode,'ModeKey'),
 ('StatusKey',dim_status,'StatusKey'),('CustomerKey',dim_customer,'CustomerKey')]:
    assert dim[pk].is_unique and fact[fk].isin(dim[pk]).all(),fk
print(f'Extracted {len(staging):,} = loaded {len(fact):,} + rejected {len(reject_log)} + deduplicated {len(removed)}')
print(checks.to_string(index=False))

# %% Step 10 - Measured evidence for T1, T4, T5 and T6
natural=['ShipDate','OriginCityKey','DestCityKey','WeightKG','CustomerKey']
collisions=keepers[keepers.duplicated(natural,keep=False)].sort_values(natural)
collisions[['ShipmentID','ShipDate','OriginCityKey','DestCityKey','WeightKG','CustomerID','CustomerKey']].to_csv(OUT/'NaturalKeyCollisions.csv',index=False)
counts=[raw_exact,raw_id,len(keepers),len(keepers.drop_duplicates(natural))]
duplicate_defs=pd.DataFrame({'Definition':['Whole raw contract row','Raw ShipmentID','Canonical ShipmentID','Day + lane + weight + customer'], 'RowsSurviving':counts})
duplicate_defs.to_csv(OUT/'T5_DuplicateDefinitions.csv',index=False)
idx_cols=FACT_COLS[:8]
selectivity=pd.DataFrame([{'Column':c,'Distinct':fact[c].nunique(),'Selectivity':fact[c].nunique()/len(fact),
 'MeanRowsPerValue':len(fact)/fact[c].nunique(),'WorstValueRows':fact[c].value_counts().max()} for c in idx_cols])
selectivity.to_csv(OUT/'T6_Selectivity.csv',index=False)
ladder=[]
for filename,mode,_ in SPECS:
    d=staging[staging.SourceFile==filename]
    ladder.append({'Stage':filename,'Rows':len(d),'NumericWeightAsIssued':d.WeightKG.map(decimal_number).sum(),
       'FreightCostPKR':d.FreightCostPKR.map(decimal_number).sum(),'WeightUnit':'tonnes' if mode=='Rail' else 'kg; invalid text skipped'})
ladder.extend([{'Stage':'Staging','Rows':len(staging)},{'Stage':'Rejected','Rows':len(reject_log)},
 {'Stage':'Deduplicated','Rows':len(removed)}, {'Stage':'Loaded','Rows':len(fact),'NumericWeightAsIssued':fact.WeightKG.sum(),'FreightCostPKR':fact.FreightCostPKR.sum(),'WeightUnit':'kg'}])
pd.DataFrame(ladder).to_csv(OUT/'T4_Ladder.csv',index=False)
unknown_city=keepers.loc[keepers.OriginCityKey==-1,'Origin'].value_counts().to_dict()
unknown_status=keepers.loc[keepers.StatusKey==-1,'StatusRaw'].value_counts().to_dict()
weighted=fact.FreightCostPKR.sum()/fact.WeightKG.sum()
unweighted=(fact.FreightCostPKR/fact.WeightKG).mean()
evidence={'actual':actual,'duplicate_counts':counts,'unknown_city':unknown_city,'unknown_status':unknown_status,
 'weighted_rate':weighted,'mean_row_rate':unweighted,'negative_weight_rows':int(weights.lt(0).sum()),
 'negative_cost_rows':int(costs.lt(0).sum()),'collision_ids':collisions.ShipmentID.tolist(),
 'mode_counts':fact.ModeKey.value_counts().to_dict(), 'stale_dates':len(stale_date),
 'raw_customer_ids':keepers.CustomerID.nunique(),'natural_survivors':counts[-1]}
(OUT/'Evidence.json').write_text(json.dumps(evidence,indent=2,default=lambda v:int(v)),encoding='utf-8')
print('Duplicate definitions:',counts,'\nNatural-key collisions:',collisions.ShipmentID.tolist())
print('Unresolved cities:',unknown_city,'\nUnresolved statuses:',unknown_status)
print('Cost/kg: weighted',round(weighted,6),'versus mean row ratio',round(unweighted,6))

# %% Step 11 - Demonstrate a DateKey index and province join with SQLite
# SQLite is a reproducible SQL illustration, not a Power BI performance benchmark.
with sqlite3.connect(OUT/'PakFreight_March.sqlite') as conn:
    for name,df in [('FactShipment_March',fact),('DimCity',dim_city),('DimCustomer',dim_customer),('DimDate',dim_date)]:
        df.to_sql(name,conn,index=False,if_exists='replace')
    sql='SELECT SUM(WeightKG) FROM FactShipment_March WHERE DateKey BETWEEN 20260301 AND 20260307'
    before=conn.execute('EXPLAIN QUERY PLAN '+sql).fetchall()
    conn.execute('CREATE INDEX IF NOT EXISTS IX_FactShipment_DateKey ON FactShipment_March(DateKey)')
    after=conn.execute('EXPLAIN QUERY PLAN '+sql).fetchall()
    province=pd.read_sql_query('SELECT d.Province, SUM(f.WeightKG) AS WeightKG FROM FactShipment_March f JOIN DimCity d ON f.OriginCityKey=d.CityKey GROUP BY d.Province',conn)
    province.to_csv(OUT/'WeightByOriginProvince.csv',index=False)
    plan={'BeforeIndex':before,'AfterIndex':after,'NewIndexEntriesForMarch':len(fact)}
    (OUT/'IndexPlan.json').write_text(json.dumps(plan,indent=2))
print('Before index:',before,'\nAfter index:',after)
print('ALL TEN CHECKS PASS')
