"""Append premarket rule predictions and verify with delayed KOSPI/KOSDAQ daily closes.
No backfilling: prediction must be recorded before 08:00 KST on the target day.
"""
import json
import sys
from datetime import datetime, timezone, time
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
OUT = Path('data/verification.json')
MARKET = Path('data/market.json')
SYMBOLS = {'kospi': '^KS11', 'kosdaq': '^KQ11'}

def read(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError): return default

def direction(v):
    return 'up' if v > 0.1 else 'down' if v < -0.1 else 'flat'

def main(mode):
    now = datetime.now(timezone.utc).astimezone(KST)
    doc = read(OUT, {'schema_version': 1, 'records': []})
    records = doc.get('records', [])
    if not isinstance(records, list): raise ValueError('Invalid records')
    if mode == 'predict':
        if now.weekday() >= 5 or now.time() >= time(8, 0):
            print('Outside premarket recording window'); return
        market = read(MARKET, {})
        mk = market.get('markets', {})
        vals = []
        for key in ('sp500', 'sox', 'usdkrw'):
            obj = mk.get(key, {})
            if obj.get('status') != 'ok' or not isinstance(obj.get('change_percent'), (float, int)):
                print('Missing indicator:', key); return
            vals.append(float(obj['change_percent']))
        snapshot = market.get('generated_at_utc')
        try: age = (now.astimezone(timezone.utc) - datetime.fromisoformat(snapshot.replace('Z','+00:00'))).total_seconds()/3600
        except (ValueError, AttributeError): return
        if not 0 <= age <= 36:
            print('Stale market snapshot, skip prediction'); return
        score = (1 if vals[0] > .3 else -1 if vals[0] < -.3 else 0) + (1 if vals[1] > .5 else -1 if vals[1] < -.5 else 0) + (1 if vals[2] < -.3 else -1 if vals[2] > .3 else 0)
        predicted = 'up' if score >= 2 else 'down' if score <= -2 else 'flat'
        for key in SYMBOLS:
            if any(r.get('date') == now.date().isoformat() and r.get('market') == key for r in records): continue
            records.append({'date': now.date().isoformat(), 'market': key, 'prediction': predicted, 'score': score, 'predicted_at_kst': now.isoformat(), 'source_snapshot_utc': snapshot, 'source_dates': {k:mk[k].get('market_date') for k in ('sp500','sox','usdkrw')}, 'actual': None, 'status': 'pending'})
    elif mode == 'settle':
        import yfinance as yf
        for key, symbol in SYMBOLS.items():
            pending = [r for r in records if r.get('market') == key and r.get('status') == 'pending' and r.get('date') <= now.date().isoformat()]
            if not pending: continue
            try:
                frame = yf.Ticker(symbol).history(period='14d', interval='1d', auto_adjust=False)
                closes = frame['Close'].dropna()
                for r in pending:
                    matches = [i for i, d in enumerate(closes.index) if d.strftime('%Y-%m-%d') == r['date']]
                    if not matches: continue
                    i = matches[-1]
                    if i < 1: continue
                    previous, current = float(closes.iloc[i-1]), float(closes.iloc[i])
                    if previous <= 0: continue
                    change = round((current / previous - 1) * 100, 4)
                    r.update({'actual': change, 'actual_close': round(current, 4), 'actual_direction': direction(change), 'status': 'verified', 'matched': r['prediction'] == direction(change), 'settled_at_kst': now.isoformat(), 'source': 'Yahoo Finance via yfinance (unofficial, delayed)'})
            except Exception as exc: print('Settlement failed', key, str(exc)[:200])
    else: raise ValueError('mode must be predict or settle')
    doc.update({'schema_version':1, 'generated_at_kst':now.isoformat(), 'method':'S&P500 ±0.3%, SOX ±0.5%, USDKRW ±0.3%; sum >=2 up, <=-2 down, else flat. Flat actual ±0.1%.', 'records':records[-250:]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(mode, 'records', len(doc['records']), 'verified', sum(r.get('status')=='verified' for r in doc['records']))

if __name__ == '__main__': main(sys.argv[1])
