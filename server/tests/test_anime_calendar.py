from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import anime_calendar as c

class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);p=patch.object(c,'ROOT',self.root);p.start();self.addCleanup(p.stop)
        self.data={'checked_at':'2026-10-19','series':[{'id':'aoashi','title':'Ao Ashi','status':'active'}],'events':[{'series':'aoashi','season':2,'episode':4,'version':'sub-es','region':'ES','date':'2099-10-25','source':'https://example.org/schedule'}]}
    def test_token_private_stable_revocable(self):
        first=c.subscription();self.assertEqual(first,c.subscription())
        token=first.split('/')[-1][:-4];self.assertTrue(c.authorized(token));self.assertFalse(c.authorized('wrong'))
        self.assertEqual((self.root/'subscription.json').stat().st_mode&0o777,0o600)
        self.assertNotEqual(first,c.subscription(rotate=True));self.assertFalse(c.authorized(token))
    def test_no_secret_or_recurring_event_in_feed(self):
        link=c.subscription();body=c.calendar(self.data).decode()
        self.assertNotIn(link,body);self.assertNotIn('RRULE',body);self.assertIn('DTSTART;VALUE=DATE:20991025',body)
    def test_versions_have_distinct_stable_uids(self):
        self.data['events'].append({**self.data['events'][0],'version':'dub-es','date':'2099-11-01'})
        c.validate(self.data);body=c.calendar(self.data).decode()
        self.assertIn('e4-sub-es@',body);self.assertIn('e4-dub-es@',body)
    def test_reschedule_preserves_uid(self):
        uid=lambda body:next(l for l in body.decode().splitlines() if l.startswith('UID:'))
        first=uid(c.calendar(self.data));self.data['events'][0]['date']='2099-11-01'
        self.assertEqual(first,uid(c.calendar(self.data)))
    def test_finished_and_past_removed_without_deleting_history(self):
        self.data['series'][0].update(status='finished',conclusion_confirmed=True)
        c.private_write(self.root/'schedule.json',self.data)
        self.assertEqual(c.snapshot()['events'],[])
        self.assertEqual(len(json.loads((self.root/'schedule.json').read_text())['events']),1)
        self.data['series'][0]['status']='active';self.data['events'][0]['date']='2000-01-01'
        c.private_write(self.root/'schedule.json',self.data);self.assertEqual(c.snapshot()['events'],[])
    def test_unknown_dub_never_creates_event(self):
        self.assertNotIn('Doblaje castellano',c.calendar(self.data).decode())
    def test_invalid_region_source_duplicate_refused(self):
        for change in [{'region':'JP'},{'version':'dub-latam'},{'source':'https://example.org/\r\nBEGIN:VEVENT'},{'date':'2026-02-30'},{'episode':0}]:
            data=deepcopy(self.data);data['events'][0].update(change)
            with self.assertRaises(ValueError):c.validate(data)
        self.data['events']*=2
        with self.assertRaises(ValueError):c.validate(self.data)
    def test_unicode_line_folding_and_injection(self):
        self.data['series'][0]['title']='Á'*100+'\nBEGIN:VEVENT'
        body=c.calendar(self.data);self.assertEqual(body.count(b'\r\nBEGIN:VEVENT\r\n'),1)
        self.assertTrue(all(len(line)<=74 for line in body.split(b'\r\n')))
        self.assertIn('\\nBEGIN:VEVENT',body.decode().replace('\r\n ',''))

class NotificationTests(unittest.TestCase):
    setUp=CalendarTests.setUp
    def test_notifications_separate_versions_deduplicate(self):
        self.data['events'][0].update(available=True,date='2026-10-01')
        self.data['events'].append({**self.data['events'][0],'version':'dub-es'})
        c.private_write(self.root/'schedule.json',self.data)
        sent=[];self.assertEqual(c.notify_available(sent.append)['sent'],2)
        self.assertEqual(c.notify_available(sent.append)['sent'],0)
        self.assertIn('Subtitulado',sent[0]);self.assertIn('castellano',sent[1])
    def test_expected_date_is_not_availability(self):
        c.private_write(self.root/'schedule.json',self.data)
        self.assertEqual(c.notify_available(lambda _:self.fail('Aviso indebido'))['sent'],0)
    def test_uncertain_send_not_repeated(self):
        self.data['events'][0].update(available=True,date='2026-10-01');c.private_write(self.root/'schedule.json',self.data)
        def fail(_):raise RuntimeError('timeout')
        with self.assertRaises(RuntimeError):c.notify_available(fail)
        self.assertEqual(c.notify_available(lambda _:self.fail('Duplicado'))['uncertain'],1)
    def test_archive_preserves_watch_and_requires_confirmed_end(self):
        c.private_write(self.root/'schedule.json',self.data)
        c.set_status('aoashi','archived');self.assertEqual(len(c.snapshot()['series']),1)
        with self.assertRaises(ValueError):c.set_status('aoashi','finished')
        c.set_status('aoashi','finished',True);self.assertEqual(c.snapshot()['series'],[])

class ManageSeriesTests(unittest.TestCase):
    setUp=CalendarTests.setUp
    def test_add_duplicate_unfollow_restore_preserves_history_and_stops_notices(self):
        self.data['events'][0].update(date='2026-10-01',available=True)
        c.private_write(self.root/'schedule.json',self.data)
        token=c.subscription()
        c.manage_series('remove',series_id='aoashi')
        self.assertEqual(c.snapshot()['series'],[])
        self.assertEqual(c.notify_available(lambda _:self.fail('Unfollowed notice'))['sent'],0)
        self.assertEqual(len(json.loads((self.root/'schedule.json').read_text())['events']),1)
        restored=c.manage_series('add','  Ao Ashi  ')
        self.assertEqual(restored['id'],'aoashi');self.assertEqual(c.subscription(),token)
        with self.assertRaises(ValueError):c.manage_series('add','Ａｏ Ａｓｈｉ')
        new=c.manage_series('add','Frieren')
        self.assertEqual(c.snapshot()['series'][-1]['id'],new['id'])
        self.assertEqual(c.snapshot()['series'][-1]['status'],'archived')
    def test_invalid_inputs_do_not_write(self):
        for title in ['',[],None,'x'*151,'a\x00b']:
            with self.assertRaises(ValueError):c.manage_series('add',title)
        with self.assertRaises(ValueError):c.manage_series('remove',series_id='missing')
        self.assertFalse((self.root/'schedule.json').exists())

    def test_new_tracking_does_not_send_back_catalog(self):
        added=c.manage_series('add','New anime')['id']
        data=json.loads((self.root/'schedule.json').read_text())
        data['events']=[{**self.data['events'][0],'series':added,'date':'2000-01-01','available':True}]
        c.private_write(self.root/'schedule.json',data)
        self.assertEqual(c.notify_available(lambda _:self.fail('Historical notice'))['sent'],0)
