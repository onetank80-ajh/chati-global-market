#!/usr/bin/env python3
"""Chati v3.6: sourced headline intelligence, not article/full-video interpretation."""
import json, re, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
CATEGORIES={
 "반도체/AI": (r"semiconductor|chip|nvidia|amd|hynix|반도체|엔비디아|인공지능|\bai\b",["삼성전자","SK하이닉스"],"SOX와 국내 외국인 수급 확인"),
 "금리/연준": (r"federal reserve|\bfed\b|fomc|powell|rate cut|rate hike|yield|금리|연준",["코스피 성장주","코스닥 성장주"],"미국 10년물 국채금리와 원/달러 확인"),
 "기술주": (r"nasdaq|big tech|technology stocks|tesla|apple|microsoft|나스닥|빅테크",["국내 기술주"],"나스닥·국내 장초반 거래대금 확인"),
 "환율/한국": (r"won|\bkrw\b|currency|dollar|kospi|korea|원화|환율|코스피",["국내 수출주"],"원/달러 방향과 외국인 현물 수급 확인")
}
def read(path):
 try: return json.loads(Path(path).read_text(encoding="utf-8"))
 except (OSError,ValueError): return {}
def stamp(s):
 try:
  d=datetime.fromisoformat(s.replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (ValueError,AttributeError): return None
def compile_briefing(market,news,analysis,now=None):
 now=now or datetime.now(timezone.utc)
 if now.tzinfo is None: raise ValueError("now must be timezone-aware")
 now=now.astimezone(timezone.utc)
 asof=now.astimezone(ZoneInfo("Asia/Seoul"))
 entries=[]; seen=set()
 for item in news.get("items",[]):
  title=item.get("title","").strip()
  url=item.get("url","")
  published=stamp(item.get("published_at_utc",""))
  if not title or not isinstance(url,str) or not url.startswith("https://") or not published or published>now or now-published>timedelta(hours=48): continue
  key=re.sub(r"\W+","",title.lower())[:100]
  if key in seen:continue
  seen.add(key)
  themes=[k for k,(pat,_,_) in CATEGORIES.items() if re.search(pat,title,re.I)]
  entries.append({"title":title[:220],"source":item.get("source","미상")[:100],"url":url,"published_at_utc":published.isoformat(),"themes":themes,"kind":"headline_only_not_verified_article"})
 entries.sort(key=lambda x:x["published_at_utc"],reverse=True)
 entries=entries[:18]
 groups=[]
 for name,(_,stocks,check) in CATEGORIES.items():
  related=[x for x in entries if name in x["themes"]]
  if related:groups.append({"theme":name,"headline_count":len(related),"stocks_to_watch":stocks,"verification":check,"headlines":related[:4],"interpretation":"기사 제목에 주제어가 언급됨. 본문과 전문가 발언을 확인하지 않았으며 방향 예측이 아님"})
 markets=[]
 for key,label in [("sp500","S&P 500"),("nasdaq","나스닥"),("sox","필라델피아 반도체"),("usdkrw","달러/원")]:
  item=market.get("markets",{}).get(key,{})
  markets.append({"key":key,"label":label,"status":item.get("status","unavailable"),"change_percent":item.get("change_percent"),"market_date":item.get("market_date")})
 scenario=[]
 for x in analysis.get("scenarios",[]):
  if x.get("market") in ("kospi","kosdaq"):scenario.append({"market":x["market"],"bias":x.get("bias","판단 보류"),"reason":x.get("reason",""),"score":x.get("score")})
 age=None
 t=stamp(market.get("generated_at_utc",""))
 if t:age=round((now-t).total_seconds()/3600,1)
 stale=age is None or age<0 or age>12
 warnings=["뉴스는 RSS 기사 제목만 분류했으며 기사 본문·방송 발언을 분석한 결과가 아닙니다.","주제별 관련 종목은 관찰 대상이지 매수·매도 추천이 아닙니다.","실시간 시세가 아닌 지연될 수 있는 일별 종가입니다."]
 if stale:warnings.append("시장 스냅샷이 없거나 12시간 이상 오래됐습니다.")
 if analysis.get("analysis_mode")!="premarket_reference":warnings.append("v3.3 분석은 유효한 개장 전 예측으로 확인되지 않았습니다.")
 return {"schema_version":1,"version":"3.6-preview","generated_at_kst":asof.isoformat(),"data_cutoff_utc":now.isoformat(),"kind":"sourced_headline_theme_watchlist_not_ai","market_snapshot_age_hours":age,"market_stale":stale,"market_indicators":markets,"v33_scenarios":scenario,"v33_mode":analysis.get("analysis_mode","unknown"),"themes":groups,"headlines":entries,"sources":{"market":market.get("source","unknown"),"news":news.get("source","unknown"),"broadcast":"not_available_no_verified_transcript"},"warnings":warnings}
def main():
 p=argparse.ArgumentParser();p.add_argument("--data",default="data");p.add_argument("--output",default="data/briefing_v36.json");a=p.parse_args()
 d=Path(a.data);result=compile_briefing(read(d/"market.json"),read(d/"news.json"),read(d/"analysis_v33.json"))
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("Saved",out,"headlines:",len(result["headlines"]),"themes:",len(result["themes"]))
if __name__=="__main__":main()
