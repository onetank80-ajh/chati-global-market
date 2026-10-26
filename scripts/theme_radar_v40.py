"""v4.0 hotfix: public Naver ranking-page scanner; partial coverage, not full KRX."""
import json, re, math, time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
import requests

KST=ZoneInfo('Asia/Seoul')
OUT=Path('data/theme_radar_v40.json')
HEAD={'User-Agent':'Mozilla/5.0 (compatible; ChatiRadar/4.0; market research)', 'Accept-Language':'ko-KR,ko;q=0.9'}

class Rows(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.cell=None;self.anchor=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='tr':self.row=[]
        if self.row is None:return
        if tag in ('td','th'):self.cell={'text':'','code':None}
        if tag=='a' and self.cell is not None:
            m=re.search(r'(?:code=|/)(\d{6})(?:\b|$)',a.get('href',''))
            if m:self.cell['code']=m.group(1)
    def handle_data(self,data):
        if self.cell is not None:self.cell['text']+=data
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.cell['text']=' '.join(self.cell['text'].split());self.row.append(self.cell);self.cell=None
        if tag=='tr' and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None;self.cell=None

def number(s):
    s=re.sub(r'[^\d.\-]','',str(s).replace(',',''))
    try:return float(s)
    except ValueError:return None

def fetch_rankings(session,market,kind):
    url=f'https://finance.naver.com/sise/sise_{kind}.naver?sosok={market}'
    r=session.get(url,timeout=14);r.raise_for_status();r.encoding=r.apparent_encoding if r.apparent_encoding.lower()!='ascii' else 'euc-kr'
    parser=Rows();parser.feed(r.text)
    found=[]
    for cells in parser.rows:
        index=next((i for i,c in enumerate(cells) if c['code']),None)
        if index is None:continue
        cell=cells[index];ticker=cell['code'];name=cell['text']
        if not name or not re.fullmatch(r'\d{6}',ticker):continue
        if any(s in name.upper() for s in ['ETF','ETN','스팩','SPAC','인버스','레버리지']):continue
        if name.endswith(('우','우B','우C')):continue
        # Naver's rank tables use stock-name / price / change / percent in consecutive cells.
        values=[c['text'] for c in cells[index+1:]]
        close=number(values[0]) if values else None
        if not close or close<=0:continue
        percent=None
        for value in values[1:5]:
            if '%' in value:
                percent=number(value)
                if '하락' in value or value.lstrip().startswith('-'):percent=-abs(percent)
                elif '상승' in value:percent=abs(percent)
                break
        if percent is None:continue
        # Do not guess volume/turnover from Naver's layout: validate via Yahoo daily history below.
        found.append({'ticker':ticker,'name':name,'market':'KOSPI' if market==0 else 'KOSDAQ','rank_change_percent':percent})
    return found

def chart(session,item):
    suffix='.KS' if item['market']=='KOSPI' else '.KQ'
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{item["ticker"]}{suffix}'
    try:
        r=session.get(url,params={'range':'3mo','interval':'1d'},timeout=12)
        r.raise_for_status();obj=r.json()['chart']['result'][0]
        q=obj['indicators']['quote'][0];dates=obj.get('timestamp') or []
        records=[]
        for i,ts in enumerate(dates):
            try:
                c=float(q['close'][i]);v=int(q['volume'][i]);h=float(q['high'][i]);lo=float(q['low'][i])
                if math.isfinite(c) and c>0 and v>=0:records.append((datetime.fromtimestamp(ts,KST).strftime('%Y-%m-%d'),c,v,h,lo))
            except (ValueError,TypeError,IndexError,KeyError):continue
        if len(records)<21:return None
        last=records[-1];prev=records[-2]
        change=(last[1]/prev[1]-1)*100
        avgvol=sum(x[2] for x in records[-21:-1])/20
        return dict(item,close=round(last[1],2),change_percent=round(change,2),volume=last[2],turnover_krw=int(last[1]*last[2]),market_date=last[0],ma5=round(sum(x[1] for x in records[-5:])/5,2),ma20=round(sum(x[1] for x in records[-20:])/20,2),volume_ratio_20d=round(last[2]/avgvol,2) if avgvol else 0,prior_20d_high=round(max(x[3] for x in records[-21:-1]),2),source='Yahoo Finance daily candles (unofficial)')
    except (requests.RequestException,ValueError,KeyError,IndexError,TypeError):return None

def main():
    now=datetime.now(KST);session=requests.Session();session.headers.update(HEAD)
    pool={};errors=[];pages=0
    for market in (0,1):
        for kind in ('rise','quant'):
            try:
                items=fetch_rankings(session,market,kind)
                if not items:raise RuntimeError('No rows parsed')
                pages+=1
                for x in items:pool[x['ticker']]=x
                print('Ranking page',market,kind,len(items),flush=True)
            except Exception as e:errors.append(f'Naver {market} {kind}: {str(e)[:120]}')
    if not pool:
        # Do not replace the last valid candidate set with fabricated or empty signals.
        # Write a separate health report; preserve the existing radar snapshot.
        status={'generated_at_kst':now.isoformat(),'status':'SOURCE_UNAVAILABLE',
                'candidate_data_updated':False,'ranking_pages_ok':pages,
                'errors':errors,'message':'공개 순위 데이터 수집 실패. 기존 후보는 과거 자료이며 현재 추천이 아닙니다.'}
        health=OUT.with_name('theme_radar_v40_health.json')
        health.parent.mkdir(parents=True,exist_ok=True)
        health.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')
        print('Radar unavailable; existing candidates preserved:', '; '.join(errors),flush=True)
        return
    # Capped subset, not entire market. Daily Yahoo bars may be delayed/incomplete.
    scanned=[]
    for i,item in enumerate(list(pool.values())[:85]):
        x=chart(session,item)
        if x:scanned.append(x)
        if (i+1)%15==0:print('History checks',i+1,'valid',len(scanned),flush=True)
        time.sleep(.08)
    if not scanned:raise RuntimeError('Public ranking pages loaded but no verified historical OHLCV; refusing fabricated signals')
    day=[dict(x,reason='상승률·추정 거래대금 조건 충족(일봉) · 장중 진입 신호 아님') for x in scanned if 3<=x['change_percent']<=22 and x['turnover_krw']>=10_000_000_000]
    day.sort(key=lambda x:(x['turnover_krw'],x['change_percent']),reverse=True)
    swing=[dict(x,reason='5일선>20일선 · 종가>20일선 · 거래량 증가(일봉)') for x in scanned if -3<=x['change_percent']<=15 and x['turnover_krw']>=8_000_000_000 and x['ma5']>x['ma20'] and x['close']>x['ma20'] and x['volume_ratio_20d']>=1.2]
    swing.sort(key=lambda x:(x['volume_ratio_20d'],x['turnover_krw']),reverse=True)
    dates=sorted({x['market_date'] for x in scanned});latest=dates[-1]
    # Do not mix old observations with latest day candidates.
    day=[x for x in day if x['market_date']==latest]
    swing=[x for x in swing if x['market_date']==latest]
    result={'schema_version':2,'generated_at_kst':now.isoformat(),'market_date':latest,'source':'Naver Finance public ranking pages + Yahoo Finance unofficial daily candles','data_kind':'partial_ranking_universe_daily_not_realtime','universe_count':len(scanned),'ranking_universe_count':len(pool),'ranking_pages_ok':pages,'daytrade_candidates':day[:20],'swing_candidates':swing[:20],'errors':errors,'warnings':['전체 코스피·코스닥 스캔이 아닙니다. 네이버 공개 상승률/거래량 순위 페이지에 나타난 일부 종목만 검사합니다.','거래대금은 일봉 종가×거래량 추정치이며 실제 거래대금이 아닙니다.','Yahoo Finance 비공식 일봉 자료이므로 당일 장중 시세/확정 종가가 아닐 수 있습니다.','장중 매수 타이밍이나 손절가를 확정할 수 없습니다. 분봉·실시간 호가·공시 확인이 필요합니다.','일봉 검증에 실패한 종목은 후보에서 제외했습니다.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Saved',OUT,'ranking pages',pages,'verified',len(scanned),'day',len(day),'swing',len(swing),'date',latest,flush=True)
if __name__=='__main__':main()
