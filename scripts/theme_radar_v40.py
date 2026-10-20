"""KRX end-of-day momentum shortlist. Not live signals or investment advice."""
import json, math, time
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

OUT=Path('data/theme_radar_v40.json')
KST=ZoneInfo('Asia/Seoul')

def safe(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError): return None

def main():
    from pykrx import stock
    now=datetime.now(KST)
    end=now.strftime('%Y%m%d')
    start=(now-timedelta(days=75)).strftime('%Y%m%d')
    items=[]; errors=[]
    # pykrx relies on unofficial KRX website endpoints; failure must not create fabricated signals.
    for market in ('KOSPI','KOSDAQ'):
        try:
            daily=stock.get_market_ohlcv_by_ticker(end,market=market)
            if daily is None or daily.empty: raise RuntimeError('empty market table')
            daily=daily.reset_index()
            for _,r in daily.iterrows():
                ticker=str(r.iloc[0]).zfill(6)
                close=safe(r.get('종가')); vol=safe(r.get('거래량')); value=safe(r.get('거래대금')); change=safe(r.get('등락률'))
                if not close or close<=0 or not vol or vol<=0 or not value or value<=0 or change is None:continue
                # Ignore preferred shares, ETFs/ETNs and SPACs where possible by name.
                try:name=stock.get_market_ticker_name(ticker)
                except Exception:name=ticker
                if not name or any(w in name.upper() for w in ('ETF','ETN','스팩','SPAC','인버스','레버리지')):continue
                if name.endswith(('우','우B','우C')):continue
                if value < 3_000_000_000:continue
                items.append({'ticker':ticker,'name':name,'market':market,'close':round(close,2),'change_percent':round(change,2),'volume':int(vol),'turnover_krw':int(value)})
        except Exception as e: errors.append(f'{market}: {str(e)[:130]}')
    if not items:
        raise RuntimeError('KRX data unavailable; no shortlist published: '+'; '.join(errors))
    # Intraday style: strong same-day movement and liquidity; generated after close, never claim live entry.
    day=[dict(x,reason='당일 상승률과 거래대금 조건 충족 · 실시간 진입 신호 아님') for x in items if 3<=x['change_percent']<=22 and x['turnover_krw']>=10_000_000_000]
    day.sort(key=lambda x:(x['turnover_krw'],x['change_percent']),reverse=True)
    # Swing: request individual historical OHLCV only for top liquid stocks to avoid overloading endpoints.
    liquid=sorted((x for x in items if x['turnover_krw']>=8_000_000_000 and -3<=x['change_percent']<=18),key=lambda x:x['turnover_krw'],reverse=True)[:70]
    swing=[]
    for x in liquid:
        try:
            df=stock.get_market_ohlcv_by_date(start,end,x['ticker'])
            if df is None or len(df)<21:continue
            closes=df['종가'].astype(float); volumes=df['거래량'].astype(float)
            if closes.iloc[-1]<=0:continue
            ma5=float(closes.tail(5).mean());ma20=float(closes.tail(20).mean());v20=float(volumes.iloc[-21:-1].mean())
            ratio=x['volume']/v20 if v20>0 else None
            high20=float(df['고가'].iloc[-21:-1].max())
            if ma5<=ma20 or x['close']<=ma20 or ratio is None or ratio<1.2:continue
            if x['change_percent']>15:continue
            y=dict(x,ma5=round(ma5,2),ma20=round(ma20,2),volume_ratio_20d=round(ratio,2),prior_20d_high=round(high20,2),reason='5일선>20일선·종가>20일선·거래량 증가')
            swing.append(y)
        except Exception as e:
            if len(errors)<12:errors.append(f"{x['ticker']}: {str(e)[:70]}")
        time.sleep(.07)
    swing.sort(key=lambda x:(x['volume_ratio_20d'],x['turnover_krw']),reverse=True)
    # Do not pretend prices are current or imply reliable entry points.
    result={'schema_version':1,'generated_at_kst':now.isoformat(),'market_date':end[:4]+'-'+end[4:6]+'-'+end[6:],'source':'pykrx / KRX unofficial endpoints; delayed or unavailable','data_kind':'end_of_day_or_latest_available_not_realtime','universe_count':len(items),'daytrade_candidates':day[:20],'swing_candidates':swing[:20],'errors':errors,'warnings':['당일 단타 후보는 장중 신호가 아니라 일별 상승률·거래대금 스크리닝 결과입니다.','스윙 후보는 기술적 필터 통과 종목이며 수익 가능성이나 매수 추천을 의미하지 않습니다.','실시간 분봉·호가·체결·공시 확인 전에는 매수가·손절가를 확정하지 않습니다.','시장 날짜는 요청 날짜이며 실제 반환된 거래일과 다를 수 있습니다. 휴장·지연 시 주의하세요.']}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('saved',OUT,'universe',len(items),'day',len(day),'swing',len(swing),'errors',len(errors))
if __name__=='__main__':main()
