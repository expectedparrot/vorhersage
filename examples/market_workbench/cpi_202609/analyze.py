"""Reproduce the pre-reveal CPI calculation from frozen public data, offline.

Rates and model errors use percentage points: 0.25 means monthly inflation 0.25%.
Historical CPI values are the downloaded vintage, not original release vintages.
"""
import calendar
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist, mean, median, stdev

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'research/raw'


def shift(month, offset):
    year, mon = map(int, month[:7].split('-'))
    number = year*12 + mon-1 + offset
    return f'{number//12:04d}-{number%12+1:02d}-01'


def tail(mu, sd):
    return 1-NormalDist(mu,sd).cdf(.25)


def analyze():
    with (RAW/'cpi_indices.csv').open() as f:
        levels = {r['observation_date']:{k:float(v) for k,v in r.items() if k!='observation_date' and v not in ('','.')} for r in csv.DictReader(f) if r['observation_date']<='2026-08-01'}
    def rate(month, series):
        previous=shift(month,-1)
        if series not in levels.get(month,{}) or series not in levels.get(previous,{}):return None
        return 100*(levels[month][series]/levels[previous][series]-1)
    def trend(month):
        rates=[rate(shift(month,-i),'CPIAUCSL') for i in (1,2,3)]
        return None if None in rates else mean(rates)
    pairs,excluded=[],[]
    for i in range(48):
        month=shift('2022-09-01',i);actual=rate(month,'CPIAUCSL');forecast=trend(month)
        if actual is None or forecast is None:
            excluded.append({'month':month,'reason':'Missing target or one of three lagged monthly changes; no interpolation.'});continue
        pairs.append({'month':month,'actual_change_pp':actual,'three_month_forecast_pp':forecast,'error_pp':actual-forecast})
    assert len(pairs)>=36
    errors=[r['error_pp'] for r in pairs];bias=mean(errors);sd=stdev(errors);n=len(errors);sigma=sd*math.sqrt(1+1/n)
    point=trend('2026-09-01');baseline=point+bias
    train=[r['error_pp'] for r in pairs if r['month']<'2025-09-01'];test=[r['error_pp'] for r in pairs if r['month']>='2025-09-01']
    tb,ts=mean(train),stdev(train);width=1.6448536269514722*ts*math.sqrt(1+1/len(train))
    with (RAW/'gasoline_primary.csv').open() as f:
        weekly=sorted((dt.date.fromisoformat(r['observation_date']),float(r['GASALLW'])) for r in csv.DictReader(f) if r['observation_date']<='2026-09-16')
    def daily_price(date, future_shift=0):
        price=[p for day,p in weekly if day<=date][-1]
        return price*(1+future_shift if date>dt.date(2026,9,16) else 1)
    def monthly_price(month,future_shift=0):
        return mean(daily_price(dt.date(2026,month,day),future_shift) for day in range(1,calendar.monthrange(2026,month)[1]+1))
    august,sept=monthly_price(8),monthly_price(9)
    season=[]
    for year in range(2021,2026):
        month=f'{year}-09-01';sa=rate(month,'CUSR0000SETB01');nsa=rate(month,'CUUR0000SETB01');assert sa is not None and nsa is not None
        season.append({'year':year,'sa_change_pct':sa,'nsa_change_pct':nsa,'correction_pp':sa-nsa})
    correction=median(r['correction_pp'] for r in season)
    recent_gas=mean(rate(f'2026-{m:02d}-01','CUSR0000SETB01') for m in (6,7,8))
    weight_record=json.loads((RAW/'bls_weight.json').read_text());w=weight_record['gasoline_relative_importance_percent']/100
    projected_raw=100*(sept/august-1);projected_sa=projected_raw+correction
    adjustment=w*(projected_sa-recent_gas);final=baseline+adjustment
    rolled_w=w*(weight_record['august_gasoline_nsa']/weight_record['july_gasoline_nsa'])/(weight_record['august_headline_nsa']/weight_record['july_headline_nsa'])
    result={'units':'Monthly inflation percentage points, not fractions. Probability is a fraction.',
        'initial_probability':tail(.2,.15),'n':n,'pairs':pairs,'excluded':excluded,
        'recent_headline_changes_pp':{f'2026-{m:02d}':rate(f'2026-{m:02d}-01','CPIAUCSL') for m in (6,7,8)},
        'raw_momentum_center_pp':point,'mean_residual_pp':bias,'sample_residual_sd_pp':sd,'predictive_sd_pp':sigma,
        'momentum_center_pp':baseline,'momentum_probability':tail(baseline,sigma),
        'holdout':{'train_n':len(train),'test_n':len(test),'train_bias_pp':tb,'train_sd_pp':ts,
            'raw_rmse_pp':math.sqrt(mean(e*e for e in test)),
            'corrected_rmse_pp':math.sqrt(mean((e-tb)**2 for e in test)),
            'nominal90_coverage':mean(abs(e-tb)<=width for e in test),'halfwidth_pp':width,
            'qualification':'Fixed first36/last12 calendar months; missing data reduce valid holdout to seven. Revised-vintage diagnostic, not original-release validation.'},
        'gasoline':{'latest_observation':weekly[-1][0].isoformat(),'latest_price':weekly[-1][1],
            'august_daily_step_average':august,'september_projected_daily_step_average':sept,
            'raw_projected_change_pct':projected_raw,'seasonal_corrections':season,'median_seasonal_correction_pp':correction,
            'projected_sa_change_pct':projected_sa,'recent_three_month_sa_change_pct':recent_gas,
            'weight_fraction':w,'weight_reference_month':weight_record['weight_reference_month'],
            'headline_adjustment_pp':adjustment},
        'final_center_pp':final,'final_probability':tail(final,sigma),
        'empirical_residual_probability':mean(point+adjustment+e>=.25 for e in errors),
        'remaining_month_gas_sensitivity':[{'future_price_shift':x,'center_pp':baseline+w*(100*(monthly_price(9,x)/august-1)+correction-recent_gas),'probability':tail(baseline+w*(100*(monthly_price(9,x)/august-1)+correction-recent_gas),sigma)} for x in (-.05,0,.05)],
        'seasonal_sensitivity':[{'year':r['year'],'center_pp':baseline+w*(projected_raw+r['correction_pp']-recent_gas),'probability':tail(baseline+w*(projected_raw+r['correction_pp']-recent_gas),sigma)} for r in season],
        'center_sensitivity':[{'shift_pp':x,'probability':tail(final+x,sigma)} for x in (-.05,0,.05)],
        'rolled_weight_sensitivity':{'weight_fraction':rolled_w,'probability':tail(baseline+rolled_w*(projected_sa-recent_gas),sigma),'label':'Approximate August weight rolled forward with NSA relative changes; not selected primary.'},
        'limitations':['Historical indices are revised; October2025 missing data remove five residual targets.','Gaussian stable residual distribution and three-month momentum are declared modeling assumptions.','Gasoline is a linear contribution approximation; EIA prices, sampling and weights differ from BLS gasoline CPI.','September remainder is projected flat at last observed price; no oil-price, inventory or shock model.','Seasonal correction is five-year September median, not the exact published2026 adjustment factor.','August release reports July relative importance; primary uses its3.770% lagged weight, with updated-weight sensitivity.','Residual spread is from the momentum model, not a validated gasoline-adjusted model.','Core, shelter, food and other energy keep implicit three-month trend; no separate forward-looking models.','No model for exceptional delayed-release or no-data fallback; ordinary release assumed.','Same assistant context and procedural price separation, not verified independent blinding.'],
        'raw_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.iterdir()) if p.is_file()}}
    return result


if __name__=='__main__':
    result=analyze();(ROOT/'research/inputs/calculation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('pairs','raw_sha256')},indent=2))
