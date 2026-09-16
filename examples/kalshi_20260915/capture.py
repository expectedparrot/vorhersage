"""Capture public Kalshi market quotes/rules. GET requests only, no credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
BASE = 'https://api.elections.kalshi.com/trade-api/v2'
MARKETS = {
    'starship': ('KXSPACEXSTARSHIP-14-26OCT01', 'KXSPACEXSTARSHIP'),
    'gta': ('KXGTA6-26NOV30', 'KXGTA6'),
    'fed': ('KXRATECUT-26DEC31', 'KXRATECUT'),
}

def now():
    return datetime.now(timezone.utc).isoformat()

def get(path):
    started = now()
    result = subprocess.run(['curl', '-L', '--fail', '--silent', '--show-error', '--max-time', '45', BASE+path], capture_output=True, check=True)
    return {'url': BASE+path, 'request_started_at': started, 'retrieved_at': now(),
            'response_sha256': hashlib.sha256(result.stdout).hexdigest(),
            'data': json.loads(result.stdout)}

def capture(name):
    ticker, series_ticker = MARKETS[name]
    market = get('/markets/'+ticker)
    m = market['data']['market']
    # Final settlement checks must not depend on a still-open order book.
    book={'not_requested':'Market is no longer active.'}
    if m['status']=='active':
        try:
            book=get('/markets/'+ticker+'/orderbook?depth=5')
        except subprocess.CalledProcessError as exc:
            book={'retrieved_at':now(),'error':exc.stderr.decode(errors='replace'),
                  'limitation':'Market quote preserved; order-book retrieval failed.'}
    series = get('/series/'+series_ticker)
    bid, ask = Decimal(m['yes_bid_dollars']), Decimal(m['yes_ask_dollars'])
    valid = (m['status']=='active' and m.get('result','')=='' and
             Decimal(m.get('yes_bid_size_fp','0'))>0 and Decimal(m.get('yes_ask_size_fp','0'))>0 and
             Decimal(0)<bid<=ask<Decimal(1))
    return {'key': name, 'ticker': ticker, 'series_ticker': series_ticker,
            'market_response': market, 'orderbook_response': book, 'series_response': series,
            'quote': {'captured_at': market['retrieved_at'], 'yes_bid': float(bid), 'yes_ask': float(ask),
                      'last_trade': float(m['last_price_dollars']), 'spread': float(ask-bid),
                      'midpoint': float((bid+ask)/2) if valid else None,
                      'two_sided_active_quote': valid,
                      'method': 'Arithmetic midpoint of positive-sized YES bid and ask in the same market response; not an executable price.'}}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--stage',required=True,choices=['baseline','post_forecast','resolution'])
    args=p.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(capture,MARKETS))
    body={'stage':args.stage,'captured_at':now(),'records':records}
    folder=ROOT/'raw'; folder.mkdir(exist_ok=True)
    path=folder/(args.stage+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    path.write_text(json.dumps(body,indent=2)+'\n')
    if args.stage=='baseline':
        assert all(r['quote']['two_sided_active_quote'] for r in records), 'Selected baseline has an unavailable two-sided quote'
        baseline=ROOT/'baseline.json'
        with baseline.open('x') as out:
            json.dump({'snapshot_file':str(path.relative_to(ROOT)), 'snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                       'records':records,'captured_at':body['captured_at']},out,indent=2)
            out.write('\n')
    print(json.dumps({'snapshot':str(path), 'quotes':[{r['key']:r['quote']} for r in records]},indent=2))

if __name__=='__main__': main()
