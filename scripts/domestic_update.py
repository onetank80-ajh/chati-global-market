"""Indicative Korean daily closes; not intraday quotes or official exchange data."""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import yfinance as yf

SYMBOLS = {
    'kospi': ('^KS11', '코스피'),
    'kosdaq': ('^KQ11', '코스닥'),
    'samsung': ('005930.KS', '삼성전자'),
    'skhynix': ('000660.KS', 'SK하이닉스'),
}

def fetch(symbol, name):
    try:
        df = yf.Ticker(symbol).history(period='12d', interval='1d', auto_adjust=False)
        df = df.dropna(subset=['Close'])
        if len(df) < 2:
            raise ValueError('2개 이상의 일별 종가가 필요합니다')
        last, prev = df.iloc[-1], df.iloc[-2]
        close, previous = float(last['Close']), float(prev['Close'])
        if previous <= 0:
            raise ValueError('이전 종가 오류')
        volume = int(last['Volume']) if 'Volume' in df and not __import__('math').isnan(float(last['Volume'])) else None
        return {'symbol':symbol,'name':name,'status':'ok','market_date':df.index[-1].strftime('%Y-%m-%d'),
                'close':round(close,2),'previous_close':round(previous,2),
                'change_percent':round((close/previous-1)*100,3),'volume':volume}
    except Exception as exc:
        return {'symbol':symbol,'name':name,'status':'unavailable','error':str(exc)[:160]}

def main():
    path=Path('data/domestic_v39.json')
    old=None
    if path.exists():
        try: old=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError): pass
    markets={k:fetch(*v) for k,v in SYMBOLS.items()}
    good=sum(x['status']=='ok' for x in markets.values())
    if good == 0:
        raise RuntimeError('모든 국내 종목 수집 실패: 기존 파일 유지')
    # Preserve earlier successful observations if a single ticker fails today.
    if old and isinstance(old.get('markets'),dict):
        for k,v in markets.items():
            if v['status']!='ok' and old['markets'].get(k,{}).get('status')=='ok':
                markets[k]=dict(old['markets'][k],stale_from_previous_run=True)
    now=datetime.now(timezone.utc)
    data={'schema_version':1,'generated_at_utc':now.isoformat(),
          'generated_at_kst':now.astimezone(ZoneInfo('Asia/Seoul')).isoformat(),
          'data_kind':'daily_close_snapshot_not_live',
          'source':'Yahoo Finance via yfinance (unofficial, may be delayed)',
          'markets':markets}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Saved',path,'fresh tickers:',good)

if __name__=='__main__': main()
