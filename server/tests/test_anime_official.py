from copy import deepcopy
import unittest
import anime_official as official
import anime_calendar as c
class Announcements(unittest.TestCase):
 def test_japanese_date_without_episode_fabrication(self):
  result=official.parse_premiere('<h4>3rd Season</h4><p>2027年01月10日から</p>',official.SOURCES[69007]);self.assertEqual(result['date'],'2027-01-10');self.assertEqual(result['season'],3)
  self.assertNotIn('episode',result);self.assertNotIn('available',result)
  self.assertIsNone(official.parse_premiere('3rd Season 2027年1月開始',official.SOURCES[69007]))
 def test_separate_calendar_event_and_injection(self):
  data={'series':[{'id':'frontier','title':'Shangri-La Frontier','status':'archived','premiere':{'season':3,'date':'2099-01-10','region':'JP','source':'https://anime.shangrilafrontier.com/onair/'}}],'events':[]}
  c.validate(data);body=c.calendar(data).decode();self.assertIn('premiere-s3@',body);self.assertNotIn('e1-jp-original',body)
  data['series'][0]['tracking']=False;self.assertNotIn('BEGIN:VEVENT',c.calendar(data).decode())
  data['series'][0]['premiere']['source']='https://example.org/\r\nBEGIN:VEVENT'
  with self.assertRaises(ValueError):c.validate(data)
