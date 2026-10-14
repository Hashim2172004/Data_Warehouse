"""Repeatable PakFreight staging. Inputs are read-only; outputs retain row lineage."""
from pathlib import Path
import csv
import hashlib
import json
import pandas as pd

CONTRACT = ['ShipmentID','ShipDate','Origin','Destination','WeightKG','CostPKR','Status','SourceSystem']
MAPPING = {
 'Marine': dict(zip(['Shipment_ID','Ship_Date','Origin_Port','Dest_Port','Weight_KG','Cost_PKR','Status'], CONTRACT[:7])),
 'Rail': dict(zip(['Consignment No','Dispatch Date','From Station','To Station','Weight (Tons)','Freight Charges (PKR)','Status'], CONTRACT[:7])),
 'Road': dict(zip(['trip_id','trip_date','from_city','to_city','weight_kg','cost_pkr','status'], CONTRACT[:7]))
}
FILES={'Marine':'marine_shipments.csv','Rail':'rail_shipments.xlsx','Road':'road_shipments.csv'}

def hashes(data_dir):
 return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(data_dir).iterdir()) if p.name in FILES.values()}

def load_sources(data_dir):
 data_dir=Path(data_dir)
 raw={}
 for mode, name in FILES.items():
  if mode=='Rail':
   frame=pd.read_excel(data_dir/name, sheet_name='Rail',header=2)
   first_row=4
  else:
   # csv.reader preserves the all-empty road record and its physical line number.
   with (data_dir/name).open(encoding='utf-8',newline='') as f:
    reader=csv.reader(f); header=next(reader); records=list(reader)
   frame=pd.DataFrame(records,columns=header)
   first_row=2
  if set(frame.columns)!=set(MAPPING[mode]):
   raise ValueError(f'{mode}: unexpected schema {list(frame.columns)}')
  frame['_SourceFile']=name
  frame['_RawRow']=range(first_row,first_row+len(frame))
  raw[mode]=frame
 return raw

def stage_sources(raw):
 staged={}; rejected=[]
 for mode, frame in raw.items():
  f=frame.rename(columns=MAPPING[mode]).copy(deep=True)
  if mode=='Road':
   f['ShipmentID']=f['ShipmentID'].fillna('').astype(str).str.strip().str.upper()
   blank=f[CONTRACT[:7]].fillna('').astype(str).apply(lambda col:col.str.strip()).eq('').all(axis=1)
   total=f['ShipmentID'].eq('TOTAL')
   for mask,reason in [(blank,'Blank record: no shipment fields'),(total,'Aggregate TOTAL row: not an individual shipment')]:
    for _,r in f.loc[mask].iterrows():
     rejected.append({'SourceFile':r['_SourceFile'],'RawRow':int(r['_RawRow']),'ShipmentID':r['ShipmentID'],'WeightKG':r['WeightKG'],'Reason':reason})
   f=f.loc[~(blank|total)].copy()
   duplicate=f.duplicated('ShipmentID',keep='first')
   for _,r in f.loc[duplicate].iterrows():
    first=f.loc[f.ShipmentID.eq(r.ShipmentID)].iloc[0]
    if not r[CONTRACT[:7]].equals(first[CONTRACT[:7]]):
     raise ValueError(f'Conflicting duplicate {r.ShipmentID}; requires steward review')
    rejected.append({'SourceFile':r['_SourceFile'],'RawRow':int(r['_RawRow']),'ShipmentID':r['ShipmentID'],'WeightKG':r['WeightKG'],'Reason':f'Identical duplicate; retain raw row {int(first["_RawRow"])}'})
   f=f.loc[~duplicate].copy()
  if mode=='Rail':
   f['ShipmentID']='RL-'+f['ShipmentID'].astype('int64').astype(str)
   f['ShipDate']=pd.to_datetime(f['ShipDate'],errors='raise').dt.normalize()
  else:
   fmt='%d/%m/%Y' if mode=='Marine' else '%Y-%m-%d'
   f['ShipDate']=pd.to_datetime(f['ShipDate'],format=fmt,errors='raise')
  for col in ['Origin','Destination','Status']:
   f[col]=f[col].astype(str).str.strip()
  f['Status']=f['Status'].str.title()
  for col in ['WeightKG','CostPKR']:
   f[col]=pd.to_numeric(f[col],errors='raise')
  if mode=='Rail': f['WeightKG']=f['WeightKG']*1000
  f['SourceSystem']=mode
  staged[mode]=f[CONTRACT+['_SourceFile','_RawRow']]
 lineage=pd.concat(staged.values(),ignore_index=True)
 shipments=lineage[CONTRACT].copy()
 return staged,shipments,lineage,pd.DataFrame(rejected)

def validate(raw,staged,shipments):
 assert shipments.shape==(34,8),shipments.shape
 assert list(shipments)==CONTRACT
 assert not shipments[['ShipmentID','ShipDate','WeightKG']].isna().any().any()
 assert shipments.ShipmentID.str.strip().ne('').all()
 assert shipments.ShipmentID.is_unique
 assert (shipments.WeightKG>0).all()
 assert (shipments.ShipDate.dt.to_period('M')==pd.Period('2026-02')).all()
 totals=shipments.groupby('SourceSystem').WeightKG.sum().to_dict()
 assert totals=={'Marine':206500.0,'Rail':295250.0,'Road':76900.0},totals
 statuses=shipments.Status.value_counts().to_dict()
 assert statuses=={'Delivered':22,'In Transit':8,'Delayed':4},statuses
 dates=shipments.set_index('ShipmentID').ShipDate
 assert dates['MR-1003']==pd.Timestamp('2026-02-03')
 assert dates['MR-1012']==pd.Timestamp('2026-02-13')
 assert shipments.loc[shipments.ShipmentID.eq('RL-45012'),'WeightKG'].iloc[0]==32500
 assert [len(raw[m]) for m in FILES]==[12,10,15]
 assert [len(staged[m]) for m in FILES]==[12,10,12]
 return {'rows':len(shipments),'columns':len(shipments.columns),'total_weight_kg':float(shipments.WeightKG.sum()),'source_weight_kg':totals,'status_counts':statuses,'all_checks_passed':True}

def run(base=None):
 base=Path(base) if base else Path(__file__).resolve().parent
 before=hashes(base/'data'); raw=load_sources(base/'data')
 staged,shipments,lineage,rejected=stage_sources(raw)
 report=validate(raw,staged,shipments)
 assert before==hashes(base/'data'),'Source bytes changed'
 out=base/'results';out.mkdir(exist_ok=True)
 shipments.to_csv(out/'Shipments.csv',index=False,date_format='%Y-%m-%d')
 lineage.to_csv(out/'lineage.csv',index=False,date_format='%Y-%m-%d')
 rejected.to_csv(out/'excluded_rows.csv',index=False)
 report['source_sha256']=before
 (out/'validation.json').write_text(json.dumps(report,indent=2))
 return raw,staged,shipments,lineage,rejected,report

if __name__=='__main__':
 *_,report=run();print(json.dumps(report,indent=2))
