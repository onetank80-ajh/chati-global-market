#!/usr/bin/env python3
"""Deterministic headline-only intelligence; no LLM or verified forecasts."""
import json,re,datetime, pathlib, math
from collections import Counter
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
def read(name):
 try:return json.loads((DATA/name).read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}
def clean(s):return re.sub(r'[^a-z0-9가-힣]+',' ',str(s).lower()).strip()
def key(title):
 s=re.sub(r'\s+-\s+[^-]+$','',str(title));return clean(s)
def main():
 now=datetime.datetime.now(datetime.timezone.utc)
 news=read('news.json');market=read('market.json');rows=[];seen=set()
 try:
  stamp=news.get('generated_at_utc') or news.get('generated_at_kst')
  news_time=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'))
  news_age=(now-news_time).total_seconds()/3600
  news_fresh=news_time.tzinfo is not None and 0<=news_age<=24
 except (AttributeError,ValueError,TypeError):news_fresh=False
 for item in (news.get('items',[]) if news_fresh and isinstance(news.get('items'),list) else []):
  if not isinstance(item,dict):continue
  title=item.get('title','');k=key(title)
  if not k or k in seen:continue
  try:dt=datetime.datetime.fromisoformat(item['published_at_utc'].replace('Z','+00:00'));age=(now-dt).total_seconds()/3600
  except (KeyError,ValueError,TypeError):continue
  if dt.tzinfo is None or not 0<=age<=48:continue
  seen.add(k)
  c=clean(title);cat=item.get('category','')
  semiconductor=bool(re.search(r'chip|semiconductor|nvidia|amd|tsmc|hynix|삼성전자|반도체',c))
  macro=bool(re.search(r'fed|inflation|interest rate|rate hike|tariff|환율|금리',c))
  korea=bool(re.search(r'korea|kospi|kosdaq|samsung|hynix|한국|코스피|코스닥',c))
  score=min(100, (35 if korea else 0)+(25 if semiconductor else 0)+(20 if macro else 0)+(10 if cat=='us_market' else 0)+max(0,20-int(age/3)))
  tags=(["한국시장 직접언급"] if korea else [])+(["반도체/AI"] if semiconductor else [])+(["거시경제"] if macro else [])
  rows.append({'title':title,'url':item.get('url',''),'source':item.get('source',''), 'published_at_utc':item['published_at_utc'],'age_hours':round(age,1),'relevance_score':score,'tags':tags,'category':cat,'needs_verification':True})
 rows.sort(key=lambda x:(-x['relevance_score'],x['age_hours']))
 markets=market.get('markets',{}); signals={}
 for k in ('sp500','sox','usdkrw','nasdaq'):
  d=markets.get(k,{})
  v=d.get('change_percent')
  valid=d.get('status')=='ok' and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
  signals[k]={'change_percent':v if valid else None,'market_date':d.get('market_date') if valid else None,'status':'ok' if valid else 'unavailable'}
 sox=signals['sox']['change_percent'];sp=signals['sp500']['change_percent'];fx=signals['usdkrw']['change_percent']
 sectors=[{'name':'반도체','related_stocks':['삼성전자','SK하이닉스'],'view':('변동성 주의' if isinstance(sox,(int,float)) and sox<0 else '방향 확인 필요'),'basis':('필라델피아 반도체지수와 최근 뉴스 제목' if news_fresh and rows else '필라델피아 반도체지수(최근 뉴스 근거 없음)')},{'name':'미국 대형주 연동','related_stocks':[],'view':('우호적 참고' if isinstance(sp,(int,float)) and sp>0 else '방향 확인 필요'),'basis':'S&P500 종가 방향'},{'name':'환율 민감 업종','related_stocks':[],'view':('원화 강세 참고' if isinstance(fx,(int,float)) and fx<0 else '환율 변동 확인'),'basis':'원/달러 환율 변화'}]
 output={'schema_version':1,'generated_at_utc':now.isoformat(),'analysis_kind':'rule_based_headlines_only_no_translation_no_ai_no_prediction','headline_count_before':len(news.get('items',[])) if isinstance(news.get('items'),list) else 0,'headline_count_after':len(rows),'news_snapshot_fresh':news_fresh,'market_snapshot_at':market.get('generated_at_kst') or market.get('generated_at_utc'),'market_signals':signals,'sectors':sectors,'top_headlines':rows[:12],'cautions':(['뉴스 수집 시각이 오래되거나 확인되지 않아 기사 분석을 보류했습니다'] if not news_fresh else [])+['기사 본문과 제목 사실관계 미검증','관련성 점수는 확률/매매신호가 아님','뉴스 제목은 자동 번역되지 않음','7:30 예약 실행은 지연될 수 있음']}
 DATA.mkdir(exist_ok=True);(DATA/'intelligence.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');print('intelligence generated:',len(rows),'unique recent headlines')
if __name__=='__main__':main()
