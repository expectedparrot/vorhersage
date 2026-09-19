"""Offline reproduction of the estimator declared before historical data retrieval."""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist, mean, stdev

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'research/raw'


def band(mu, sigma):
    d = NormalDist(mu, sigma)
    return d.cdf(77.5) - d.cdf(75.5)


def analyze():
    observed = {}
    with (RAW / 'observed_history.csv').open() as f:
        for row in csv.DictReader(f):
            assert row['station'] == 'MDW'
            if row['max_temp_f'] not in ('', 'None', 'M'):
                observed[row['day']] = float(row['max_temp_f'])
    forecasts = {}
    with (RAW / 'nbs_history.csv').open() as f:
        for row in csv.DictReader(f):
            runtime = dt.datetime.fromisoformat(row['runtime'])
            valid = dt.datetime.fromisoformat(row['ftime'])
            if runtime.hour == 6 and valid == runtime.replace(hour=0) + dt.timedelta(days=2) and row['txn']:
                assert row['station'] == 'KMDW' and row['model'] == 'NBS'
                day = (runtime.date() + dt.timedelta(days=1)).isoformat()
                assert day not in forecasts, 'Unexpected duplicate forecast'
                forecasts[day] = {'forecast': float(row['txn']), 'runtime': row['runtime'],
                                  'forecast_valid': row['ftime'], 'xnd': float(row['xnd']) if row['xnd'] else None}
    pairs, excluded = [], []
    for offset in range(60):
        day = (dt.date(2026, 7, 18) + dt.timedelta(days=offset)).isoformat()
        if day not in observed or day not in forecasts:
            excluded.append(day)
            continue
        pairs.append({'date': day, **forecasts[day], 'observed': observed[day],
                      'error': observed[day] - forecasts[day]['forecast']})
    assert len(pairs) >= 30, 'Declared minimum sample unavailable; retain initial forecast'
    current = [r for r in json.loads((RAW / 'nbs_current.json').read_text())['data']
               if r['ftime'] == '2026-09-18 00:00']
    assert len(current) == 1 and current[0]['runtime'] == '2026-09-16 06:00' and current[0]['station'] == 'KMDW'
    forecast, xnd = current[0]['txn'], current[0]['xnd']
    errors = [r['error'] for r in pairs]
    bias, sd, n = mean(errors), stdev(errors), len(errors)
    mu, sigma = forecast + bias, math.sqrt(sd**2 * (1 + 1/n) + 1)
    train, held = errors[:40], errors[40:60]
    holdout = None
    if held:
        train_bias, train_sd = mean(train), stdev(train)
        halfwidth = 1.6448536269514722 * math.sqrt(train_sd**2 * (1 + 1/len(train)) + 1)
        holdout = {'train_n': len(train), 'test_n': len(held), 'train_bias_f': train_bias,
                   'train_sd_f': train_sd, 'raw_rmse_f': math.sqrt(mean(e**2 for e in held)),
                   'bias_corrected_rmse_f': math.sqrt(mean((e-train_bias)**2 for e in held)),
                   'nominal_90pct_interval_coverage': mean(abs(e-train_bias) <= halfwidth for e in held),
                   'interval_halfwidth_f': halfwidth,
                   'qualification': 'One small chronological check on proxy observations; not validation against TWC settlements.'}
    nws = json.loads((RAW/'nws_forecast.json').read_text())['properties']
    nws_high = [r['temperature'] for r in nws['periods'] if r['isDaytime'] and r['startTime'].startswith('2026-09-17')]
    assert len(nws_high) == 1
    return {'selection': 'All 60 target dates July 18–September 15, 2026; previous-day KMDW NBS 06 UTC; TXN at following-day 00 UTC (42-hour lead).',
            'pairs': pairs, 'excluded_dates': excluded, 'n': n,
            'current_nbs_high_f': forecast, 'current_nbs_xnd_f': xnd,
            'initial_probability': band(forecast, math.sqrt(xnd**2+1)),
            'bias_observed_minus_forecast_f': bias, 'residual_sample_sd_f': sd,
            'final_mean_f': mu, 'final_sd_f': sigma, 'assumed_extra_provider_window_sd_f': 1,
            'final_probability': band(mu,sigma),
            'empirical_residual_probability': mean(76 <= forecast+e <= 77 for e in errors),
            'holdout_diagnostic': holdout,
            'nws_alternative': {'high_f': nws_high[0], 'issued_at': nws['updateTime'],
                 'probability_with_nws_center_and_same_sd': band(nws_high[0],sigma),
                 'qualification': 'Alternative raw NWS center; NBS bias is not transferred to a different forecast product. This is sensitivity, not the selected forecast.'},
            'sensitivity': [{'extra_sd_f':extra,'mean_shift_f':shift,
                            'probability':band(mu+shift,math.sqrt(sd**2*(1+1/n)+extra**2))}
                           for extra in (0,1,2) for shift in (-1,0,1)],
            'limitations': ['IEM daily maxima are not exact TWC settlements.',
                'NBS daytime maximum and full daily-report time windows differ.',
                'Gaussian errors, constant bias, nearest-integer rounding and independent 1°F extra SD are assumptions.',
                '60 adjacent summer days may be correlated and may not match the current rainy autumn regime.',
                'Forecast archive is retrieved now, not immutable original publication vintages.',
                'Same assistant context as NYC; price separation is procedural, not enforced isolation.',
                'Opening thresholds screen best quotes only, not trading volume or market calibration.'],
            'raw_sha256': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.iterdir()) if p.is_file()}}


if __name__ == '__main__':
    result=analyze()
    (ROOT/'research/inputs/calculation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('pairs','raw_sha256')},indent=2))
