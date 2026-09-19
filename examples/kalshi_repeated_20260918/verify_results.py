"""Independent arithmetic and commitment checks against the published archive."""
import json
from math import isclose, sqrt
from statistics import mean, stdev
from batch import OUT, MODELS, CONDITIONS, verify_seals, audit_reviews
from vorhersage.common import digest, load, time


def main():
    reg,seals=verify_seals();audit_reviews(seals)
    d=load(OUT/'comparison.json')
    assert d['registration_sha256']==digest(reg)
    cases={c['id']:c for c in reg['cases']}
    assert set(p['id'] for p in d['pairs'])==set(cases)
    for p in d['pairs']:
        cid=p['id']
        t=load(OUT/'revealed-targets'/(cid+'.json'))
        r=load(OUT/'reveals'/(cid+'.json'))
        assert digest(t)==cases[cid]['start']['target_sha256']
        assert p['target']==t['baseline']['quote']['midpoint']
        assert all(time(s['sealed_at'])<time(r['revealed_at']) for s in seals.values())
        assert time(load(OUT/'fresh-call-audit.json')['checked_at'])<time(r['revealed_at'])
        for key in MODELS:
            for c in CONDITIONS:
                expected=[f['probability'] for f in seals[key]['forecasts'] if f['question_id']==cid and f['condition']==c]
                assert expected==p['draws'][key][c]
    common=[p for p in d['pairs'] if all(len(p['draws'][k][c])==3 for k in MODELS for c in CONDITIONS)]
    assert d['common_question_ids']==[p['id'] for p in common]
    for key in MODELS:
        for c in CONDITIONS:
            m=d['common_metrics'][key][c]
            qloss=[mean(abs(x-p['target']) for x in p['draws'][key][c]) for p in common]
            sqloss=[mean((x-p['target'])**2 for x in p['draws'][key][c]) for p in common]
            meanloss=[abs(mean(p['draws'][key][c])-p['target']) for p in common]
            sd=[stdev(p['draws'][key][c]) for p in common]
            for field,value in [('mean_draw_mae_pp',100*mean(qloss)),('draw_rmse_pp',100*sqrt(mean(sqloss))),
                                ('three_draw_mean_mae_pp',100*mean(meanloss)),('mean_within_question_sd_pp',100*mean(sd))]:
                assert isclose(m[field],value,abs_tol=1e-10),field
    ens=mean(abs(mean(mean(p['draws'][k]['outside_research']) for k in MODELS)-p['target']) for p in common)*100
    assert isclose(ens,d['equal_weight_research_metrics']['mae_pp'],abs_tol=1e-10)
    const=mean(abs(.5-p['target']) for p in common)*100
    assert isclose(const,d['constant_50_metrics']['mae_pp'],abs_tol=1e-10)
    print(json.dumps({'verified':True,'contracts':len(common),'calls':sum(len(s['attempts']) for s in seals.values()),
                      'constant_50_mae_pp':const,'max_midpoint_drift_pp':100*max(abs(p['target']-p['followup_quote']['midpoint']) for p in common),
                      'comparison_sha256':digest(d)},indent=2))

if __name__=='__main__':main()
