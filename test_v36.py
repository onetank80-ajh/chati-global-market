import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from v36_briefing import compile_briefing
NOW=datetime(2026,10,20,0,0,tzinfo=timezone.utc)
class TestV36(unittest.TestCase):
 def test_no_data(self):
  d=compile_briefing({}, {}, {}, NOW);self.assertTrue(d["market_stale"]);self.assertEqual(d["headlines"],[])
 def test_future_news_excluded(self):
  n={"items":[{"title":"Nvidia chips","url":"https://example.org/a","published_at_utc":"2026-10-21T00:00:00+00:00"}]}
  self.assertEqual(compile_briefing({},n,{},NOW)["headlines"],[])
 def test_topic(self):
  n={"items":[{"title":"Nvidia semiconductor shares","url":"https://example.org/a","source":"Example","published_at_utc":"2026-10-19T22:00:00+00:00"}]}
  d=compile_briefing({},n,{},NOW);self.assertEqual(d["themes"][0]["theme"],"반도체/AI")
 def test_bad_url(self):
  n={"items":[{"title":"Nvidia","url":"javascript:alert(1)","published_at_utc":"2026-10-19T22:00:00+00:00"}]}
  self.assertFalse(compile_briefing({},n,{},NOW)["headlines"])
 def test_stale(self):
  m={"generated_at_utc":"2026-10-19T00:00:00+00:00"}
  self.assertTrue(compile_briefing(m,{}, {},NOW)["market_stale"])
if __name__=="__main__":unittest.main()
