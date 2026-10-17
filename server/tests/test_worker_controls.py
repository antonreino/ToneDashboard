import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import state_db as db
import task_store as tasks

class WorkerControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for key,value in [('DB_PATH',self.root/'state.sqlite3'),('_INITIALIZED',False)]:
            p=patch.object(db,key,value);p.start();self.addCleanup(p.stop)
        spec=importlib.util.spec_from_file_location('controlled_download_worker',Path(__file__).resolve().parents[1]/'scripts/telegram_torrent_bot.py');self.m=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'test-only','TELEGRAM_CHAT_ID':'123'}):spec.loader.exec_module(self.m)
        self.m.start_queued_downloads=Mock();self.m.send_message=Mock();self.m.GAME_DOWNLOAD_DIR=self.root
    def job(self,status='queued'):
        target=self.root/'file';target.write_bytes(b'partial')
        ident=db.create_download(chat_id='123',url='https://example.test/f',name='file',target=str(target),size_bytes=100,resume_supported=True,queued_at=0)
        db.update_download(ident,status=status)
        row=tasks.download_record(ident);job=dict(row,target=target,size=100);self.m.KNOWN_TARGETS.add(str(target));return ident,job
    def test_pause_resume_cancel_queued_confirmed_and_partial_preserved(self):
        ident,job=self.job();self.m.QUEUED_DOWNLOADS.append(job)
        tasks.command(ident,'pause');self.m.apply_download_commands();self.assertEqual(tasks.download_record(ident)['status'],'paused');self.assertFalse(self.m.QUEUED_DOWNLOADS)
        tasks.command(ident,'resume');self.m.apply_download_commands();self.assertEqual(tasks.download_record(ident)['status'],'queued');self.assertEqual(len(self.m.QUEUED_DOWNLOADS),1)
        tasks.command(ident,'cancel');self.m.apply_download_commands();self.assertEqual(tasks.download_record(ident)['status'],'cancelled');self.assertEqual(job['target'].read_bytes(),b'partial')
        tasks.command(ident,'retry');self.m.apply_download_commands();self.assertEqual(len(self.m.QUEUED_DOWNLOADS),1)
        self.m.send_message.assert_not_called()
    def test_active_pause_waits_for_transfer_confirmation(self):
        ident,job=self.job('active');self.m.ACTIVE_DOWNLOADS[ident]=job
        tasks.command(ident,'pause');self.m.apply_download_commands()
        self.assertEqual(job['stop_action'],'pause');self.assertEqual(tasks.download_record(ident)['status'],'active');self.assertEqual(len(tasks.pending_commands()),1)
        with patch.object(self.m.subprocess,"Popen",return_value=Mock()):self.m.run_game_download(job)
        self.assertEqual(tasks.download_record(ident)['status'],'paused');self.assertFalse(tasks.pending_commands());self.assertEqual(job['target'].read_bytes(),b'partial')
    def test_completed_race_never_changes_completed_status(self):
        ident,_=self.job('active');tasks.command(ident,'cancel');db.update_download(ident,status='completed');self.m.apply_download_commands()
        self.assertEqual(tasks.download_record(ident)['status'],'completed');self.assertFalse(tasks.pending_commands())
