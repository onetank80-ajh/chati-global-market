import json, datetime, pathlib, math
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
KST=datetime.timezone(datetime.timedelta(hours=9))
now=datetime.datetime.now(KST)
def read(name):
    try:
        return json.loads((DATA/name).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {}
market=read('market.json'); news=read('news.json'); intel=read('intelligence.json')
if not isinstance(market,dict): market={}
if not isinstance(news,dict): news={}
if not isinstance(intel,dict): intel={}
markets=market.get('markets',{})
if not isinstance(markets,dict): markets={}
indicators=[]
for key,label in [('sp500','미국 대형주'),('sox','반도체'),('usdkrw','원/달러')]:
    m=markets.get(key,{})
    if not isinstance(m,dict): m={}
    if m.get('status')=='ok' and isinstance(m.get('change_percent'),(int,float)) and not isinstance(m.get('change_percent'),bool) and math.isfinite(m['change_percent']):
        v=m['change_percent']
        if key=='usdkrw': meaning='원화 강세 방향' if v<0 else '원화 약세 방향' if v>0 else '보합'
        else: meaning='상승' if v>0 else '하락' if v<0 else '보합'
        indicators.append({'name':label,'change_percent':v,'market_date':m.get('market_date'),'meaning':meaning})
def age_hours(value):
    try:
        dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None: return None
        return (now-dt).total_seconds()/3600
    except (AttributeError,ValueError,TypeError):
        return None
news_age=age_hours(news.get('generated_at_utc') or news.get('generated_at_kst'))
news_fresh=news_age is not None and 0<=news_age<=24
headlines=[]
if news_fresh:
    for item in (news.get('items') if isinstance(news.get('items'),list) else []):
        if not isinstance(item,dict): continue
        title=item.get('title'); url=item.get('url')
        published_age=age_hours(item.get('published_at_utc'))
        if isinstance(title,str) and title.strip() and isinstance(url,str) and url.startswith('https://') and published_age is not None and 0<=published_age<=48:
            headlines.append({'title':title,'url':url,'source':item.get('source',''),'published_at_utc':item.get('published_at_utc','')})
        if len(headlines)>=8: break
intel_age=age_hours(intel.get('generated_at_utc') or intel.get('generated_at_kst'))
intel_time_fresh=intel_age is not None and 0<=intel_age<=24
market_time=market.get('generated_at_kst') or market.get('generated_at_utc')
intel_market_time=intel.get('market_snapshot_at')
try:
    market_dt=datetime.datetime.fromisoformat(market_time.replace('Z','+00:00'))
    intel_dt=datetime.datetime.fromisoformat(intel_market_time.replace('Z','+00:00'))
    intel_market_drift=abs((market_dt-intel_dt).total_seconds()) if market_dt.tzinfo is not None and intel_dt.tzinfo is not None else None
except (AttributeError,ValueError,TypeError):
    intel_market_drift=None
intel_market_aligned=intel_market_drift is not None and math.isfinite(intel_market_drift) and intel_market_drift<=2
intel_signals=intel.get('market_signals',{})
intel_quotes_aligned=isinstance(intel_signals,dict) and all(
    isinstance(intel_signals.get(key),dict)
    and isinstance(markets.get(key),dict)
    and intel_signals[key].get('status')==markets[key].get('status')=='ok'
    and isinstance(intel_signals[key].get('change_percent'),(int,float))
    and not isinstance(intel_signals[key].get('change_percent'),bool)
    and math.isfinite(intel_signals[key]['change_percent'])
    and intel_signals[key].get('change_percent')==markets[key].get('change_percent')
    and intel_signals[key].get('market_date')==markets[key].get('market_date')
    for key in ('sp500','sox','usdkrw')
)
intel_safe=intel_time_fresh and intel_market_aligned and intel_quotes_aligned
sectors=intel.get('sectors',[])[:6] if intel_safe and isinstance(intel.get('sectors'),list) else []
snapshot_at=market.get('generated_at_utc') or market.get('generated_at_kst')
try:
    parsed=datetime.datetime.fromisoformat(snapshot_at.replace('Z','+00:00'))
    snapshot_age_exact=(now-parsed).total_seconds()/3600 if parsed.tzinfo is not None else None
except (AttributeError,ValueError,TypeError):
    snapshot_age_exact=None
snapshot_age_hours=round(snapshot_age_exact,2) if snapshot_age_exact is not None and math.isfinite(snapshot_age_exact) else None
snapshot_fresh=(snapshot_age_exact is not None and math.isfinite(snapshot_age_exact) and 0<=snapshot_age_exact<=12)
# Record how late the scheduled 07:00 KST combined refresh actually ran.
scheduled=now.replace(hour=7,minute=0,second=0,microsecond=0)
delay_minutes=round((now-scheduled).total_seconds()/60,1)
late=delay_minutes>10
out={'schema_version':1,'generated_at_kst':now.isoformat(),'analysis_kind':'rule_based_not_ai','market_snapshot_at':market.get('generated_at_kst') or market.get('generated_at_utc'), 'news_snapshot_at':news.get('generated_at_kst') or news.get('generated_at_utc'), 'market_snapshot_age_hours':snapshot_age_hours,'market_snapshot_fresh':snapshot_fresh,'scheduled_briefing_at_kst':scheduled.isoformat(),'briefing_delay_minutes':delay_minutes,'briefing_late_over_10min':late,'indicators':indicators,'sectors':sectors, 'headlines':headlines,'news_snapshot_fresh':news_fresh,'warnings':(['업종 분석이 오래되었거나 시장 데이터와 일치하지 않아 숨겼습니다.'] if not intel_safe else [])+(['뉴스 수집 시각이 오래되었거나 확인되지 않아 이전 헤드라인을 숨겼습니다.'] if not news_fresh else [])+(['시장 데이터가 오래되었거나 수집 시각을 확인할 수 없습니다. 오늘의 매매 판단에 사용하지 마세요.'] if not snapshot_fresh else [])+(['오전 7시 통합 데이터 갱신이 10분 넘게 지연되었습니다.'] if late else [])+['기존 market.json/news.json 스냅샷을 바탕으로 생성','기사 본문 미검증, AI 번역·요약 아님','한국 증시 주가 예측 또는 매매 신호 아님']}
DATA.mkdir(exist_ok=True)
(DATA/'morning.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('morning.json generated:',len(indicators),'indicators,',len(headlines),'headlines')
