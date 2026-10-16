"""Rule-based, headline-only briefing; not AI translation, fact checking, or price prediction."""
import json,re
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

POS=('rebound','rally','surge','gain','rise','higher','record high','beats expectations','eases','upgrade','strong earnings')
NEG=('sell-off','selloff','slump','sink','plunge','drop','fall','lower','inflation','rate hike','downgrade','circuit breaker','rout','worries','loss')
SECTORS={
 '반도체/AI':('semiconductor','chip','nvidia','nvda','amd','tsmc','ai ','hynix','samsung'),
 '2차전지':('battery','lithium','ev ','electric vehicle'),
 '방산':('defense','defence','missile','military','aerospace'),
}

def label(title):
    t=title.lower(); p=sum(bool(re.search(r'(?<![a-z])'+re.escape(w)+r'(?![a-z])',t)) for w in POS)
    n=sum(bool(re.search(r'(?<![a-z])'+re.escape(w)+r'(?![a-z])',t)) for w in NEG)
    return '긍정 표현' if p>n else '부정 표현' if n>p else '혼재/불명'

def main():
    market=json.loads(Path('data/market.json').read_text(encoding='utf-8'))
    news=json.loads(Path('data/news.json').read_text(encoding='utf-8'))
    now=datetime.now(timezone.utc); rows=[]; seen=set()
    for item in news.get('items',[]):
        title=str(item.get('title','')).strip(); key=re.sub(r'[^a-z0-9]+',' ',title.lower()).strip()
        if not title or key in seen: continue
        seen.add(key)
        try: age=(now-datetime.fromisoformat(item['published_at_utc'].replace('Z','+00:00'))).total_seconds()/3600
        except (ValueError,KeyError,TypeError): continue
        if age < -1 or age > 48: continue
        sectors=[k for k,words in SECTORS.items() if any(w in title.lower() for w in words)]
        score=max(0,round(100-2*max(0,age)))
        rows.append({'title':title,'url':item.get('url',''),'source':item.get('source',''),
          'published_at_utc':item.get('published_at_utc'),'category':item.get('category'),
          'age_hours':round(age,1),'freshness_score':score,'headline_tone':label(title),'sectors':sectors})
    rows.sort(key=lambda x:(-x['freshness_score'],x['title']))
    markets=market.get('markets',{})
    signals=[]
    for key,name,weight in [('sp500','미국 대형주',1),('sox','반도체',2),('usdkrw','원/달러',-1)]:
        m=markets.get(key,{})
        if m.get('status')!='ok' or not isinstance(m.get('change_percent'),(int,float)): continue
        pct=m['change_percent']; direction=(1 if pct>0 else -1 if pct<0 else 0)*weight
        signals.append({'indicator':name,'change_percent':pct,'reference_direction': '우호적' if direction>0 else '주의' if direction<0 else '중립'})
    result={'schema_version':1,'generated_at_utc':now.isoformat(),
      'generated_at_kst':now.astimezone(ZoneInfo('Asia/Seoul')).isoformat(),
      'analysis_kind':'rule_based_headline_only_not_ai_not_forecast',
      'method':'48시간 이내 뉴스 제목만 키워드 매칭; 신선도=100-시간*2; 지수 방향 별도 표시',
      'cautions':['기사 본문 미검증','제목 긍정/부정은 실제 주가 영향과 다름','예측 확률 또는 매매 신호 아님'],
      'market_signals':signals,'headlines':rows[:15]}
    dest=Path('data/briefing.json');dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Briefing saved:',len(result['headlines']),'recent headlines')

if __name__=='__main__':main()
