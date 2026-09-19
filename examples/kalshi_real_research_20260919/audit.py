"""Check actual call identities and chronology without accessing target prices."""
import json
from collections import Counter
from batch import OUT, MODELS, verify_seals, audit_reviews, write
from vorhersage.common import digest, load, now, require, time


def main():
    reg,seals=verify_seals()
    audit_reviews(seals)
    cases={c['id']:c for c in reg['cases']}
    trials={t['trial_id']:t for t in reg['trials']}
    result={'checked_at':now(),'registration_sha256':digest(reg),'models':{}}
    for key in MODELS:
        rows=load(OUT/key/'raw-records.json')
        require(len(rows)==42,'Missing raw response.')
        ids=[]
        caches=[]
        for r in rows:
            raw=r['raw_model_response']['forecast_raw_model_response']
            rid=raw.get('id',raw.get('response_id'))
            require(isinstance(rid,str) and rid,'Missing provider response identity.')
            ids.append(rid)
            caches.append(r.get('cache_used',{}))
        require(len(set(ids))==len(ids),'Provider response reused across registered calls.')
        counts=Counter((trials[f['trial_id']]['question_id'],f['condition']) for f in seals[key]['forecasts'])
        require(len(counts)==14 and all(n==3 for n in counts.values()),'Incomplete repetition grid.')
        screens=load(OUT/key/'screening.json')['records']
        statuses=Counter(s['status'] for r in screens for s in r.get('fields',{}).values())
        result['models'][key]={'unique_provider_response_ids':len(set(ids)), 'provider_ids':ids,
                              'screened_field_statuses':dict(statuses),'cache_receipts':caches,
                              'forecast_seal_sha256':digest(seals[key])}
    for cid,case in cases.items():
        opened=time(case['start']['baseline_captured_at'])
        for record in load(OUT/'packets'/(cid+'.json'))['records']:
            for source in record['sources']:
                require(opened<time(source['retrieved_at'])<time(reg['registered_at']),'Evidence timing does not match protocol.')
    require(all(time(s['sealed_at'])<time(reg['specification']['forecast_cutoff']) for s in seals.values()),'Forecasts sealed after cutoff.')
    result['total_unique_responses']=sum(v['unique_provider_response_ids'] for v in result['models'].values())
    dest=OUT/'fresh-call-audit.json'
    if not dest.exists(): write(dest,result)
    print(json.dumps({'verified':True,'unique_responses':result['total_unique_responses'],
                      'screening':{k:v['screened_field_statuses'] for k,v in result['models'].items()}},indent=2))

if __name__=='__main__':main()
