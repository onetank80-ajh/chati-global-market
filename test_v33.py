import importlib.util, json, tempfile, unittest
from pathlib import Path
from datetime import datetime as RealDateTime, timezone
from unittest.mock import patch
from types import SimpleNamespace
import sys
import pandas as pd
ROOT=Path(__file__).parent

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/filename)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

class Tests(unittest.TestCase):
 def setUp(self):
    self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
    self.data=Path(self.temp.name);self.a=load('analysis_test','analysis_v33.py');self.v=load('verify_test','v33_verify.py')
    self.a.DATA=self.data;self.v.DATA=self.data;self.v.OUT=self.data/'v33_history.json'
    self.now=RealDateTime(2026,10,20,7,50,tzinfo=self.v.KST)
    self.write('market.json',{'generated_at_utc':self.now.astimezone(timezone.utc).isoformat(),'markets':{k:{'status':'ok','change_percent':val,'market_date':'2026-10-19'} for k,val in {'sp500':.41,'nasdaq':1.1,'sox':1.6,'usdkrw':-.22}.items()}})
 def write(self,name,obj):(self.data/name).write_text(json.dumps(obj),encoding='utf8')
 def fixed(self,module,now):
    class Clock(RealDateTime):
      @classmethod
      def now(cls,tz=None):return now.astimezone(tz) if tz else now.replace(tzinfo=None)
    return patch.object(module,'datetime',Clock)
 def generate(self,now=None):
    now=now or self.now
    with self.fixed(self.a,now):self.a.main()
    return json.loads((self.data/'analysis_v33.json').read_text())
 def test_premarket_prediction_and_duplicate(self):
    a=self.generate();self.assertTrue(a['eligible_for_prediction_record'])
    with self.fixed(self.v,self.now):self.v.main('predict');self.v.main('predict')
    r=json.loads(self.v.OUT.read_text())['records'];self.assertEqual(len(r),2);self.assertTrue(all(x['status']=='pending' for x in r))
 def test_after_eight_no_prediction(self):
    later=self.now.replace(hour=8,minute=1);self.generate(later)
    with self.fixed(self.v,later):self.v.main('predict')
    self.assertFalse(self.v.OUT.exists())
 def test_stale_snapshot_no_prediction(self):
    m=json.loads((self.data/'market.json').read_text());m['generated_at_utc']=(self.now.replace(day=19,hour=8)).astimezone(timezone.utc).isoformat();self.write('market.json',m)
    a=self.generate();self.assertFalse(a['eligible_for_prediction_record'])
    with self.fixed(self.v,self.now):self.v.main('predict')
    self.assertFalse(self.v.OUT.exists())
 def test_missing_indicators_holds(self):
    m=json.loads((self.data/'market.json').read_text());m['markets'].pop('sp500');m['markets'].pop('sox');self.write('market.json',m)
    a=self.generate();self.assertFalse(a['eligible_for_prediction_record']);self.assertTrue(all(s['bias']=='판단 보류' for s in a['scenarios']))
 def test_settle_with_mock_daily_closes(self):
    self.generate()
    with self.fixed(self.v,self.now):self.v.main('predict')
    days=pd.to_datetime(['2026-10-19','2026-10-20'])
    closes=pd.Series([100.,101.],index=days)
    class FakeTicker:
      def __init__(self,symbol):self.symbol=symbol
      def history(self,**kwargs):return pd.DataFrame({'Close':closes})
    fake=SimpleNamespace(Ticker=FakeTicker)
    later=self.now.replace(hour=20,minute=30)
    with patch.dict(sys.modules,{'yfinance':fake}),self.fixed(self.v,later):self.v.main('settle')
    records=json.loads(self.v.OUT.read_text())['records']
    self.assertEqual(len(records),2)
    self.assertTrue(all(r['status']=='verified' and r['actual_percent']==1.0 for r in records))
    self.assertTrue(all(r['matched'] for r in records))
 def test_future_snapshot_rejected(self):
    m=json.loads((self.data/'market.json').read_text());m['generated_at_utc']=(self.now.replace(hour=8)).astimezone(timezone.utc).isoformat();self.write('market.json',m)
    self.assertFalse(self.generate()['eligible_for_prediction_record'])
if __name__=='__main__':unittest.main(verbosity=2)
