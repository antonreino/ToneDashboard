import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch,Mock
import state_db as db
import task_store as tasks
from runtime_support import backup_database,tail_text,SnapshotCache
import download_security as downloads

class OperationalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for key,value in [('DB_PATH',self.root/'state.sqlite3'),('_INITIALIZED',False)]:
            p=patch.object(db,key,value);p.start();self.addCleanup(p.stop)
        db.init_db()
    def job(self,status='queued'):
        ident=db.create_download(chat_id='private',url='https://example.test/private-token',name='file',target=str(self.root/'file'),size_bytes=100,resume_supported=True,queued_at=0)
        db.update_download(ident,status=status);return ident
    def test_active_jobs_survive_many_newer_completed_rows(self):
        active=self.job('active')
        for _ in range(55):self.job('completed')
        page=db.download_page(20);self.assertEqual([r['id'] for r in page['active']],[active]);self.assertEqual(len(page['history']),20)
        second=db.download_page(20,page['next_cursor']);self.assertFalse(set(r['id'] for r in page['history'])&set(r['id'] for r in second['history']))
        self.assertNotIn('url',page['active'][0]);self.assertNotIn('chat_id',page['active'][0])
    def test_commands_validate_state_and_preserve_files(self):
        ident=self.job('active');target=self.root/'file';target.write_text('partial')
        result=tasks.command(ident,'pause');self.assertEqual(result['status'],'pending')
        with self.assertRaises(ValueError):tasks.command(ident,'cancel')
        tasks.finish_command(result['command_id']);db.update_download(ident,status='paused')
        self.assertTrue(tasks.command(ident,'resume')['ok']);self.assertEqual(target.read_text(),'partial')
        for action in ['delete','shell','retry']:
            with self.assertRaises(ValueError):tasks.command(ident,action)
        with self.assertRaises(ValueError):tasks.command(True,'pause')
    def test_review_approval_changed_file_and_safe_rule(self):
        path=self.root/'odd.mkv';path.write_text('movie');tasks.review(path,'unknown');row=tasks.reviews()[0]
        body={'id':row['id'],'title':'Movie','category':'movies','year':2020,'pattern':'odd.'}
        tasks.decide_review(body);self.assertEqual(tasks.approved_reviews()[0]['id'],row['id'])
        self.assertEqual(tasks.rule_for(path)['title'],'Movie')
        tasks.finish_review(row['id'],'offline');path.write_text('changed')
        with self.assertRaises(ValueError):tasks.decide_review(body)
    def test_review_rejects_path_injection_and_invalid_episode(self):
        for d in [{'title':'../other','category':'movies'},{'title':'Movie','category':'shell'},{'title':'Series','category':'series'},{'title':'Series','category':'anime','season':True,'episode':1}]:
            with self.assertRaises(ValueError):tasks.validate_decision(d)
    def test_activity_never_returns_local_paths(self):
        tasks.activity(self.root/'private'/'movie.mkv','classifying')
        row=tasks.activities()['items'][0];self.assertEqual(row['name'],'movie.mkv');self.assertNotIn('path',row)
    def test_online_backup_restore_and_retention(self):
        self.job();backup=backup_database(db.DB_PATH,self.root/'backups',retain=2)
        spec=importlib.util.spec_from_file_location('restore',Path(__file__).resolve().parents[2]/'scripts/restore-backup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        target=m.restore(backup,self.root/'restored.sqlite3')
        with sqlite3.connect(target) as c:self.assertEqual(c.execute('SELECT count(*) FROM downloads').fetchone()[0],1)
        self.assertEqual(target.stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):m.restore(backup,target)
        for _ in range(4):backup_database(db.DB_PATH,self.root/'backups',retain=2)
        self.assertEqual(len(list((self.root/'backups').glob('*.sqlite3'))),2)
    def test_failed_backup_never_publishes_an_unverified_snapshot(self):
        broken=self.root/'broken.sqlite3';broken.write_bytes(b'not a SQLite file')
        folder=self.root/'snapshots'
        with self.assertRaises(sqlite3.DatabaseError):backup_database(broken,folder)
        self.assertEqual(list(folder.iterdir()),[])
    def test_bounded_tail_unicode_and_partial_line(self):
        p=self.root/'large.log';p.write_text('x'*100000+'\nuno\ndos á\ntres\n')
        self.assertEqual(tail_text(p,2),'dos á\ntres')
        self.assertLessEqual(len(tail_text(p,100,max_bytes=8192)),8192)
    def test_shared_cache_does_not_repeat_expensive_probe(self):
        cache=SnapshotCache();load=Mock(return_value={'ok':True})
        self.assertEqual(cache.get('x',60,load),cache.get('x',60,load));load.assert_called_once()

class ReviewExecutionTests(unittest.TestCase):
    setUp=OperationalTests.setUp
    def test_approved_review_runs_safe_uploader_and_preserves_existing_remote(self):
        import emby_organizer as m
        root=self.root/'Inbox';q=root/'NoClasificado';q.mkdir(parents=True)
        path=q/'odd.mkv';path.write_bytes(b'media');tasks.review(path,'unknown')
        ident=tasks.reviews()[0]['id'];tasks.decide_review({'id':ident,'title':'Movie','category':'movies'})
        org=m.MediaOrganizer.__new__(m.MediaOrganizer);org.dry_run=False;org.is_stable=Mock(return_value=True);org.uploader=Mock();org.uploader.build_remote_path.return_value='/movies/Movie.mkv';org.uploader.exists.return_value=True;org.notify_telegram=Mock();org.cleanup_download_folder=Mock();org.cleanup_empty_folders=Mock()
        with patch.object(m,'INBOX_DIR',root),patch.object(m,'QUARANTINE_LOCAL_DIR',q):org.scan_once()
        self.assertTrue(path.exists());org.uploader.upload_file.assert_not_called();self.assertEqual(tasks.reviews()[0]['status'],'failed')
        tasks.decide_review({'id':ident,'title':'Movie','category':'movies'});org.uploader.exists.return_value=False
        with patch.object(m,'INBOX_DIR',root),patch.object(m,'QUARANTINE_LOCAL_DIR',q):org.scan_once()
        self.assertFalse(path.exists());self.assertEqual(tasks.reviews(),[]);org.uploader.upload_file.assert_called_once();org.notify_telegram.assert_called_once()
    def test_file_timeline_survives_quarantine_relocation(self):
        old=self.root/'movie.mkv';new=self.root/'NoClasificado'/'movie.mkv'
        tasks.activity(old,'classifying');tasks.relocate(old,new);tasks.activity(new,'review')
        rows=tasks.activities()['items'];timeline=tasks.activities(file_id=rows[0]['id'])['items'];self.assertEqual(len(timeline),2)

class ResumeTests(unittest.TestCase):
    def response(self,status,headers,blocks):
        r=Mock(status=status);r.getheader.side_effect=lambda name,default=None:headers.get(name,default);r.read.side_effect=blocks;return r
    def test_without_validator_discards_legacy_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_bytes(b'old')
            r=self.response(200,{'Content-Length':'3'},[b'new',b''])
            with patch.object(downloads,'open_public',return_value=r) as opened:
                downloads.download_public('https://example.test/f',path)
                self.assertNotIn('Range',opened.call_args.kwargs['headers']);self.assertEqual(path.read_bytes(),b'new')
    def test_validator_change_and_stop_preserve_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_bytes(b'abc')
            Path(str(path)+'.resume.json').write_text(json.dumps({'url':'https://example.test/f','validator':'"old"'}))
            r=self.response(206,{'Content-Range':'bytes 3-5/6','ETag':'"new"'},[])
            with patch.object(downloads,'open_public',return_value=r),self.assertRaises(OSError):downloads.download_public('https://example.test/f',path)
            self.assertEqual(path.read_bytes(),b'abc')
            r=self.response(200,{'Content-Length':'3','ETag':'"new"'},[b'new',b''])
            with patch.object(downloads,'open_public',return_value=r),self.assertRaises(downloads.DownloadStopped):downloads.download_public('https://example.test/f',path,check=Mock(side_effect=downloads.DownloadStopped('pause')))
            self.assertEqual(path.read_bytes(),b'abc')
    def test_low_space_never_truncates_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_bytes(b'abc');r=self.response(200,{'Content-Length':'5000'},[])
            with patch.object(downloads,'open_public',return_value=r),patch.object(downloads.shutil,'disk_usage',return_value=Mock(free=100)),self.assertRaises(OSError):downloads.download_public('https://example.test/f',path)
            self.assertEqual(path.read_bytes(),b'abc')

class IsolationTests(unittest.TestCase):
    def test_disabled_invalid_and_separate_authority(self):
        import orbit_isolation as m
        with patch.dict(os.environ,{'DASHBOARD_PUBLIC_ORIGIN':'','ORBIT_ISOLATED_ORIGIN':''}):self.assertIsNone(m.origins())
        with patch.dict(os.environ,{'DASHBOARD_PUBLIC_ORIGIN':'https://dashboard.test','ORBIT_ISOLATED_ORIGIN':'https://orbit.test'}):
            self.assertTrue(m.isolated_host({'Host':'orbit.test'}));self.assertFalse(m.valid({'Host':'orbit.test'}))
            self.assertTrue(m.entry()['url'].startswith('https://orbit.test/orbit-session?ticket='))
            self.assertFalse(m.isolated_host({'Host':'dashboard.test'}))
    def test_ticket_one_use_and_scope_cookie(self):
        import orbit_isolation as m
        class Handler:
            headers={'Host':'orbit.test'}
            def __init__(self,path):self.path=path;self.response={}
            def send_response(self,status):self.status=status
            def send_header(self,key,value):self.response[key]=value
            def end_headers(self):pass
        with patch.dict(os.environ,{'DASHBOARD_PUBLIC_ORIGIN':'https://dashboard.test','ORBIT_ISOLATED_ORIGIN':'https://orbit.test'}):
            from urllib.parse import urlsplit
            url=m.entry()['url'];h=Handler('/orbit-session?'+urlsplit(url).query);self.assertTrue(m.handle_entry(h));self.assertEqual(h.status,303)
            cookie=h.response['Set-Cookie'];self.assertIn('HttpOnly; Secure; SameSite=Lax',cookie)
            self.assertTrue(m.valid({'Host':'orbit.test','Cookie':cookie.split(';')[0]}))
            self.assertFalse(m.valid({'Host':'dashboard.test','Cookie':cookie.split(';')[0]}))
            second=Handler(h.path);m.handle_entry(second);self.assertEqual(second.status,403)
