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
markets=market.get('markets',{})
indicators=[]
for key,label in [('sp500','미국 대형주'),('sox','반도체'),('usdkrw','원/달러')]:
    m=markets.get(key,{})
    if m.get('status')=='ok' and isinstance(m.get('change_percent'),(int,float)) and not isinstance(m.get('change_percent'),bool) and math.isfinite(m['change_percent']):
        v=m['change_percent']
        if key=='usdkrw': meaning='원화 강세 방향' if v<0 else '원화 약세 방향' if v>0 else '보합'
        else: meaning='상승' if v>0 else '하락' if v<0 else '보합'
        indicators.append({'name':label,'change_percent':v,'market_date':m.get('market_date'),'meaning':meaning})
headlines=[]
for item in news.get('items',[]):
    if not isinstance(item,dict): continue
    title=item.get('title'); url=item.get('url')
    if isinstance(title,str) and isinstance(url,str) and url.startswith('https://'):
        headlines.append({'title':title,'url':url,'source':item.get('source',''),'published_at_utc':item.get('published_at_utc','')})
    if len(headlines)>=8: break
snapshot_at=market.get('generated_at_utc') or market.get('generated_at_kst')
try:
    parsed=datetime.datetime.fromisoformat(snapshot_at.replace('Z','+00:00'))
    snapshot_age_hours=round((now-parsed).total_seconds()/3600,2)
except (AttributeError,ValueError,TypeError):
    snapshot_age_hours=None
snapshot_fresh=(snapshot_age_hours is not None and 0<=snapshot_age_hours<=12)
# Record how late the scheduled 07:00 KST combined refresh actually ran.
scheduled=now.replace(hour=7,minute=0,second=0,microsecond=0)
delay_minutes=round((now-scheduled).total_seconds()/60,1)
late=delay_minutes>10
out={'schema_version':1,'generated_at_kst':now.isoformat(),'analysis_kind':'rule_based_not_ai','market_snapshot_at':market.get('generated_at_kst') or market.get('generated_at_utc'), 'news_snapshot_at':news.get('generated_at_kst') or news.get('generated_at_utc'), 'market_snapshot_age_hours':snapshot_age_hours,'market_snapshot_fresh':snapshot_fresh,'scheduled_briefing_at_kst':scheduled.isoformat(),'briefing_delay_minutes':delay_minutes,'briefing_late_over_10min':late,'indicators':indicators,'sectors':intel.get('sectors',[])[:6], 'headlines':headlines,'warnings':(['시장 데이터가 오래되었거나 수집 시각을 확인할 수 없습니다. 오늘의 매매 판단에 사용하지 마세요.'] if not snapshot_fresh else [])+(['오전 7시 통합 데이터 갱신이 10분 넘게 지연되었습니다.'] if late else [])+['기존 market.json/news.json 스냅샷을 바탕으로 생성','기사 본문 미검증, AI 번역·요약 아님','한국 증시 주가 예측 또는 매매 신호 아님']}
DATA.mkdir(exist_ok=True)
(DATA/'morning.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('morning.json generated:',len(indicators),'indicators,',len(headlines),'headlines')
