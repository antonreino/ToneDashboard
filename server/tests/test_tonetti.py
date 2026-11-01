import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import tonetti

class TonettiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=patch.object(tonetti,'ROOT',Path(self.tmp.name));self.root.start();self.addCleanup(self.root.stop)
    def test_bad_messages_never_call_model(self):
        for body in [None,[],{}, {'message':1},{'message':''},{'message':'x'*4001},{'message':'hola','url':'http://evil'}]:
            with self.assertRaises(ValueError):tonetti.start(body)
        self.assertEqual(tonetti.snapshot()['messages'],[])
    def test_async_persists_and_limits_concurrency(self):
        entered=threading.Event();release=threading.Event()
        def answer(*args,**kwargs):
            entered.set();release.wait(3);return 'Emby está documentado en 192.168.1.177.',[{'source':'agent','reference':'openclaw:test'}]
        with patch.object(tonetti.service,'generate',side_effect=answer) as call:
            self.assertEqual(tonetti.start({'message':'¿Dónde está Emby?'})[1],202)
            self.assertTrue(entered.wait(2));self.assertEqual(tonetti.start({'message':'otra'})[1],409)
            self.assertTrue(tonetti.snapshot()['busy']);release.set()
            self.assertTrue(tonetti._LOCK.acquire(timeout=4));tonetti._LOCK.release()
            self.assertEqual(call.call_args.args[4],1)
        self.assertEqual([m['role'] for m in tonetti.snapshot()['messages']],['user','assistant'])
        self.assertIn('192.168.1.177',tonetti.snapshot()['messages'][-1]['content'])
        self.assertEqual((Path(self.tmp.name)/'chat.sqlite3').stat().st_mode & 0o777,0o600)
    def test_failure_is_persisted_and_unlocks(self):
        with patch.object(tonetti.service,'generate',side_effect=OSError('private details')):
            tonetti.start({'message':'hola'})
            self.assertTrue(tonetti._LOCK.acquire(timeout=4));tonetti._LOCK.release()
        last=tonetti.snapshot()['messages'][-1]
        self.assertEqual(last['state'],'error');self.assertNotIn('private details',last['content'])

    def test_abandoned_pending_is_interrupted_not_retried(self):
        with tonetti.connect() as db:
            db.execute("INSERT INTO messages(role,content,state,at) VALUES('assistant','','pending','now')")
        with patch.object(tonetti.urllib.request,'urlopen') as call:
            result=tonetti.snapshot()
        call.assert_not_called()
        self.assertEqual(result['messages'][-1]['state'],'interrupted')
        self.assertFalse(result['busy'])
