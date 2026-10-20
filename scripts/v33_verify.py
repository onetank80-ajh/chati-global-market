"""Append-only premarket predictions and later verify official daily direction via delayed Yahoo data."""
import json,sys
from datetime import datetime,time,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
KST=ZoneInfo('Asia/Seoul')
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
OUT=DATA/'v33_history.json'
SYMBOLS={'kospi':'^KS11','kosdaq':'^KQ11'}
def read(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default
def direction(change):return '상승' if change>0.1 else '하락' if change< -0.1 else '중립'
def main(mode):
    now=datetime.now(KST)
    doc=read(OUT,{'schema_version':1,'records':[]})
    rows=doc.get('records',[])
    if not isinstance(rows,list):raise ValueError('invalid history')
    if mode=='predict':
        if now.weekday()>=5 or not time(7,0)<=now.time()<time(8,0):
            print('Skip: outside premarket');return
        analysis=read(DATA/'analysis_v33.json',{})
        if analysis.get('analysis_mode')!='premarket_reference' or not analysis.get('eligible_for_prediction_record') or analysis.get('coverage',0)<.75:
            print('Skip: analysis not eligible');return
        if analysis.get('market_snapshot_at') is None:return
        try:
            snap=datetime.fromisoformat(analysis['market_snapshot_at'].replace('Z','+00:00'))
            generated=datetime.fromisoformat(analysis['generated_at_kst'])
            age=(now.astimezone(timezone.utc)-snap).total_seconds()/3600
            analysis_age=(now-generated).total_seconds()/60
        except (ValueError,KeyError,TypeError):return
        if not 0<=age<=12 or not 0<=analysis_age<=15:
            print('Skip: stale snapshot or analysis');return
        for item in analysis.get('scenarios',[]):
            market=item.get('market')
            if market not in SYMBOLS or any(r.get('date')==now.date().isoformat() and r.get('market')==market for r in rows):continue
            bias=item.get('bias')
            predicted={'상승 우세':'상승','하락 우세':'하락','중립/혼조':'중립'}.get(bias)
            if not predicted:continue
            rows.append({'date':now.date().isoformat(),'market':market,'prediction':predicted,'predicted_at_kst':now.isoformat(),'source_snapshot_utc':analysis['market_snapshot_at'],'score':item.get('score'),'status':'pending'})
    elif mode=='settle':
        import yfinance as yf
        for market,symbol in SYMBOLS.items():
            pending=[r for r in rows if r.get('market')==market and r.get('status')=='pending' and r.get('date')<=now.date().isoformat()]
            if not pending:continue
            try:
                closes=yf.Ticker(symbol).history(period='45d',interval='1d',auto_adjust=False)['Close'].dropna()
                for r in pending:
                    ix=[i for i,d in enumerate(closes.index) if d.strftime('%Y-%m-%d')==r['date']]
                    if not ix or ix[-1]<1:continue
                    i=ix[-1];old=float(closes.iloc[i-1]);new=float(closes.iloc[i]);
                    if old<=0:continue
                    pct=round((new/old-1)*100,4)
                    r.update({'status':'verified','actual_percent':pct,'actual_direction':direction(pct),'matched':direction(pct)==r['prediction'],'settled_at_kst':now.isoformat(),'source':'Yahoo Finance unofficial delayed'})
            except Exception as exc:print('Settlement error:',market,type(exc).__name__,str(exc)[:100])
    else:raise ValueError('predict or settle')
    doc.update({'schema_version':1,'updated_at_kst':now.isoformat(),'records':rows[-500:],'rule':'up >0.1%, down <-0.1%, otherwise flat'})
    DATA.mkdir(exist_ok=True);OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(mode,'records',len(rows),'verified',sum(r.get('status')=='verified' for r in rows))
if __name__=='__main__':main(sys.argv[1])
