import json,hashlib,datetime,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'outputs'
seal=out/'sealed_result.json'
assert not seal.exists(),'Sealed outputs must be preserved.'
with sqlite3.connect(root/'project/.vorhersage/state.sqlite') as c:
 c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
f=json.loads((out/'forecast.json').read_text())
files=[]
for p in root.rglob('*'):
 if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and not p.name.endswith(('-wal','-shm')) and p!=seal:
  files.append(p)
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
body={'schema_version':'independent_pilot_seal.v1','question_id':f['question_id'],'forecast_id':f['id'],'disposition':'prospective','already_known':False,'probability':f['probability'],'information_as_of':f['information_as_of'],'issued_at':f['issued_at'],'sealed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'workspace':str(root),'sha256':hashes,'exposure_declaration':json.loads((out/'exposure.json').read_text()),'cost_accounting':'Unmetered model calls and cost; package numeric zeros are unreported counters, not actual zero usage.','integrity_scope':'All substantive workspace files including frozen inputs, package source, captured public operator content, outputs and checkpointed SQLite history. SQLite transient WAL/SHM and Python bytecode excluded.','limitation':'A seal proves artifact stability, not factual correctness or calibration.'}
seal.write_text(json.dumps(body,indent=2)+'\n')
print(json.dumps({'sealed_at':body['sealed_at'],'forecast_id':f['id'],'probability':f['probability'],'files_hashed':len(hashes)}))
