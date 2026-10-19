import unittest
from unittest.mock import Mock,patch
import requests
import anime_metadata as m

class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.session=Mock();self.session.trust_env=False
        p=patch.object(m.requests,'Session',return_value=self.session);p.start();self.addCleanup(p.stop)
        self.show={'id':10,'name':'Example Anime','type':'Animation','language':'Japanese','genres':['Anime'],'status':'Ended','url':'https://www.tvmaze.com/shows/10/example','image':{'original':'https://static.tvmaze.com/uploads/images/original_untouched/1/1.jpg'},'network':{'country':{'code':'JP'}},'_links':{}}
        self.image=Mock();self.image.iter_content.return_value=[b'\xff\xd8\xffposter'];self.image.__enter__=Mock(return_value=self.image);self.image.__exit__=Mock(return_value=False);self.session.get.return_value=self.image
    def json_patch(self,rows=None):return patch.object(m,'get_json',return_value=[{'show':s} for s in (rows if rows is not None else [self.show])])
    def test_match_downloads_poster_and_does_not_mark_ended_as_story_finished(self):
        with self.json_patch():result=m.lookup('Example Anime')
        self.assertEqual(result['tvmaze_id'],10);self.assertEqual(result['_poster_bytes'],b'\xff\xd8\xffposter');self.assertNotIn('status',result)
        self.session.get.assert_called_once_with(self.show['image']['original'],timeout=(4,12),allow_redirects=False,stream=True)
    def test_ambiguous_and_live_action_are_not_chosen(self):
        for rows in [[self.show,{**self.show,'id':11}],[{**self.show,'type':'Scripted'}],[{**self.show,'name':'Other Anime'}]]:
            with self.json_patch(rows),self.assertRaises(ValueError):m.lookup('Example Anime')
        self.session.get.assert_not_called()
    def test_catalog_cannot_redirect_fetch_to_private_hosts(self):
        for url in ['http://static.tvmaze.com/poster.jpg','https://127.0.0.1/poster.jpg','https://static.tvmaze.com.evil.test/a','https://static.tvmaze.com:8443/a','https://user@static.tvmaze.com/a']:
            show={**self.show,'image':{'original':url}}
            with self.json_patch([show]),self.assertRaises(ValueError):m.lookup('Example Anime')
        self.session.get.assert_not_called()
        with self.assertRaises(ValueError):m.get_json(self.session,'https://192.168.1.170/')
    def test_bad_and_oversized_images_are_refused(self):
        for chunks in [[b'<html>bad</html>'],[b'\xff\xd8\xff'+b'x'*4_000_000]]:
            self.image.iter_content.return_value=chunks
            with self.json_patch(),self.assertRaises(ValueError):m.lookup('Example Anime')
    def test_network_failure_is_clear(self):
        with patch.object(m,'get_json',side_effect=requests.Timeout),self.assertRaisesRegex(ValueError,'consultar el catálogo'):m.lookup('Example Anime')
    def test_next_episode_converts_timestamp_to_japanese_civil_day(self):
        show={**self.show,'_links':{'nextepisode':{'href':'https://api.tvmaze.com/episodes/23'}}}
        episode={'season':2,'number':1,'airstamp':'2026-10-24T16:30:00Z','url':'https://www.tvmaze.com/episodes/23/example'}
        with patch.object(m,'get_json',side_effect=[[{'show':show}],episode]):result=m.lookup('Example Anime')
        self.assertEqual(result['_next_event']['date'],'2026-10-25');self.assertEqual(result['_next_event']['region'],'JP')
