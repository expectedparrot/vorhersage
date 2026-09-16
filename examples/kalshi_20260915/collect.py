"""Preserve a sealed worker result and independently validate its calendar model."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
import zipfile

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'src'))
from vorhersage.workflow import Workflow
from vorhersage.store import Store
from vorhersage import timeline

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dt(t):return datetime.fromisoformat(t.replace('Z','+00:00')).astimezone(timezone.utc)

def calculate(spec,scenario):
    values={a['parameter_id']:a for a in scenario['assessments']}; dates={}; todo={n['id']:n for n in spec['nodes']}; cutoff=dt(spec['information_as_of'])
    while todo:
        ready=[n for n in todo.values() if all(p in dates for p in n['parents'])]
        assert ready,'Invalid dependency order'
        for n in ready:
            parents=[dates[p] for p in n['parents']]
            if n['state']=='completed': value=dt(n['completed_at'])
            elif n['kind']=='any':
                value='unknown' if 'unknown' in parents else min((p for p in parents if p is not None),default=None)
            elif None in parents:value=None
            elif 'unknown' in parents:value='unknown'
            elif n['kind']=='all':value=max(parents)
            else:
                a=values.get(n['parameter_id'],{'basis':'unresolved'})
                if a['basis']=='unresolved':value='unknown'
                elif a['value']=='never':value=None
                elif n['kind']=='event':value=dt(a['value'])
                else:
                    start=cutoff if n['state']=='in_progress' else max([cutoff,dt(n.get('not_before',spec['information_as_of']))]+parents)
                    value=start+timedelta(seconds=86400*a['value'])
            dates[n['id']]=value;del todo[n['id']]
    finish=dates[spec['target']]; assert finish!='unknown'
    yes=False if finish is None else (finish<dt(spec['deadline']) if spec['deadline_rule']=='before' else finish<=dt(spec['deadline']))
    return {'scenario_id':scenario['id'],'weight':scenario['weight'],'launch_at':finish.isoformat() if finish else None,'meets_deadline':yes}

def main(key):
    launch=next(r for r in read(ROOT/'launches.json') if r['key']==key)
    source=Path(launch['workspace']); dest=ROOT/'forecasts'/key
    seal=read(source/'outputs/sealed_result.json'); files=seal.get('files',seal.get('sha256',seal.get('hashes',{})));assert files
    for relative,expected in files.items():
        p=source/'outputs'/relative
        if not p.exists():p=source/relative
        assert p.resolve().is_relative_to(source.resolve())
        assert sha(p)==expected,relative
    manifest=read(source/'input_manifest.json')
    for relative,expected in manifest['inputs'].items():assert sha(source/relative)==expected,relative
    # Working webpage/JavaScript downloads are left in the temporary workspace.
    # Core inputs, histories and all sealed files are preserved byte for byte.
    copied=[]
    for folder in (source,source/'outputs'):
        for p in folder.iterdir():
            if p.is_file() and (p.suffix in ('.json','.md','.py') or p.name=='forecast.html'):
                target=dest/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,target);copied.append(str(target.relative_to(dest)))
    for relative,expected in files.items():
        source_file=source/'outputs'/relative
        if not source_file.exists():source_file=source/relative
        target=dest/source_file.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source_file,target);assert sha(target)==expected
    database=source/'project/.vorhersage/state.sqlite'; wal=Path(str(database)+'-wal')
    uri=database.as_uri()+('?mode=ro' if wal.exists() and wal.stat().st_size else '?mode=ro&immutable=1')
    # Some workers also hash the physical SQLite file. Preserve that exact file
    # and use a separate logical copy for portable auditing, since changing the
    # journal mode alters bytes without changing any forecast record.
    project_name='validation_project' if (dest/'project/.vorhersage/state.sqlite').exists() else 'project'
    target_db=dest/project_name/'.vorhersage/state.sqlite';target_db.parent.mkdir(parents=True,exist_ok=True)
    assert not target_db.exists(),'Existing validation database is preserved'
    with sqlite3.connect(uri,uri=True) as c, sqlite3.connect(target_db) as backup:
        c.backup(backup);backup.execute('PRAGMA journal_mode=DELETE')
    with zipfile.ZipFile(dest/'input_snapshot.zip') as z:
        for name in z.namelist():
            if name.startswith('src/'):z.extract(name,dest)
    w=Workflow(dest/project_name);doctor=w.doctor();assert doctor['ok']
    with w.store.connect() as c:
        fs=Store.all(c,'forecast');assert len(fs)==1
        forecast=fs[0];assert forecast['question']==read(dest/'question.json')
        model=timeline.read(c,forecast['timeline_model_id'])['specification']; analysis=timeline.analyze(model)
        rows=[calculate(model,s) for s in model['scenarios']]
        for independent,engine in zip(rows,analysis['scenarios']):
            assert all(independent[k]==engine[k] for k in ('scenario_id','launch_at','meets_deadline'))
        assert math.isclose(math.fsum(r['weight'] for r in rows),1,abs_tol=1e-12)
        p=math.fsum(r['weight'] for r in rows if r['meets_deadline'])
        assert math.isclose(p,forecast['probability'],abs_tol=1e-12)
        assert math.isclose(p,seal['probability'],abs_tol=1e-12)
    result={'collected_at':datetime.now(timezone.utc).isoformat(),'key':key,'forecast_id':forecast['id'],
            'probability':p,'sealed_hashes_verified':len(files),'input_hashes_verified':len(manifest['inputs']),
            'doctor':doctor,'independent_calendar_and_sum_match':True,'scenarios':rows,
            'copied_files':copied,'validation_project':project_name,
            'database_copy':'Logical backup in DELETE journal mode; exact sealed database file retained separately when present.',
            'limitation':'Integrity and arithmetic checks do not validate subjective scenario weights.'}
    (dest/'collection.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('key','probability','sealed_hashes_verified','doctor')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('key',choices=['starship','gta','fed']);main(p.parse_args().key)
