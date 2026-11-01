import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import task_runner as runner

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.enter=patch.object(runner.catalogue,'AUDIT_ROOT',self.root);self.enter.start();self.addCleanup(self.enter.stop)
    def test_unknown_and_path_identifiers_cannot_launch(self):
        for ident in ['../bad','future-task','x; rm',None]:
            with self.assertRaises(ValueError):runner.start(ident,Path('/tmp/price.db'))
    def test_duplicate_manual_launch_is_rejected(self):
        with patch.object(runner,'_ACTIVE','another-task'):
            data,code=runner.start('dashboard-backups',Path('/tmp/price.db'))
        self.assertEqual(code,409)
    def test_paused_automation_cannot_launch(self):
        raw='id="mantener-payloads-de-ps5"\nstatus="PAUSED"\nprompt="private"'
        with patch.object(runner.catalogue,'_read',return_value=raw):
            with self.assertRaises(ValueError):runner._prompt('mantener-payloads-de-ps5')
    def test_missing_process_does_not_claim_success(self):
        folder=runner._folder('dashboard-backups');runner._write(folder/'manual-state.json',{'state':'running','started_at':'2026-10-21T10:00:00Z','message':'starting'})
        with patch.object(runner,'_ACTIVE',None):self.assertEqual(runner.state('dashboard-backups')['state'],'interrupted')
    def test_cli_failure_is_error_not_success(self):
        with patch.object(runner.subprocess,'run',return_value=Mock(returncode=1)) as run:
            result=runner._codex('trusted prompt',7)
        self.assertEqual(result['status'],'error')
        command=run.call_args.args[0]
        self.assertIn('--approve-for-me',command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',command)
        self.assertEqual(run.call_args.kwargs['input'],'trusted prompt')
        self.assertEqual(run.call_args.kwargs['pass_fds'],(7,))
    def test_backup_worker_writes_result_without_exposing_exception(self):
        import os
        descriptor=os.open(self.root/'lock',os.O_CREAT|os.O_RDWR,0o600)
        with patch('operations.backup_all',side_effect=RuntimeError('secret-private-data')):
            runner._work('dashboard-backups',Path('/tmp/price.db'),None,descriptor,'2026-10-21T10:00:00Z')
        value=runner.state('dashboard-backups')
        self.assertEqual(value['state'],'error');self.assertNotIn('secret-private-data',json.dumps(value))
        reports=list(runner._folder('dashboard-backups').glob('*-manual.json'))
        self.assertEqual(len(reports),1)


    def test_proxmox_network_permission_is_explicit_but_does_not_change_profile(self):
        task='mantenimiento-semanal-proxmox-y-emby'
        raw='id="'+task+'"\nstatus="ACTIVE"\nprompt="Revisión autorizada"'
        with patch.object(runner.catalogue,'_read',return_value=raw):
            prompt=runner._prompt(task)
        self.assertIn('permiso puntual de red',prompt)
        self.assertIn('require_escalated',prompt)
        self.assertIn('No cambiar perfiles ni permisos permanentes',prompt)
        self.assertIn('remote.py --probe',prompt)
        self.assertNotIn('dangerously-bypass',prompt)

    def test_proxmox_uses_one_shot_app_and_private_job_files(self):
        helper=self.root/'ToneMaintenanceRunner.app';helper.mkdir()
        def run(command,**kwargs):
            self.assertEqual(command[:4],['/usr/bin/open','-n','-g','-W'])
            directory=Path(command[-1]);self.assertEqual(json.loads((directory/'task.json').read_text()),{'id':'mantenimiento-semanal-proxmox-y-emby'})
            self.assertEqual((directory/'prompt.txt').stat().st_mode&0o777,0o600)
            self.assertEqual((directory/'prompt.txt').read_text(),'trusted prompt')
            (directory/'answer.json').write_text(json.dumps({'status':'ok','message':'Revisión de prueba'}))
            return Mock(returncode=0)
        with patch.object(runner,'MAINTENANCE_HELPER',helper),patch.object(runner.sys,'platform','darwin'),patch.object(runner.subprocess,'run',side_effect=run):
            result=runner._codex('trusted prompt',7,'mantenimiento-semanal-proxmox-y-emby')
        self.assertEqual(result['status'],'ok')
    def test_ps5_uses_same_one_shot_network_helper(self):
        helper=self.root/'ToneMaintenanceRunner.app';helper.mkdir()
        def run(command,**kwargs):
            self.assertEqual(command[:4],['/usr/bin/open','-n','-g','-W'])
            directory=Path(command[-1])
            self.assertEqual(json.loads((directory/'task.json').read_text()),{'id':'mantener-payloads-de-ps5'})
            (directory/'answer.json').write_text(json.dumps({'status':'partial','message':'Consola apagada; sin cambios'}))
            return Mock(returncode=0)
        with patch.object(runner,'MAINTENANCE_HELPER',helper),patch.object(runner.sys,'platform','darwin'),patch.object(runner.subprocess,'run',side_effect=run):
            result=runner._codex('trusted prompt',7,'mantener-payloads-de-ps5')
        self.assertEqual(result['status'],'partial')
    def test_live_native_helper_lock_blocks_duplicate_manual_task(self):
        import fcntl,os
        path=self.root/'scheduled-tasks'/'maintenance-helper.lock';path.parent.mkdir()
        with path.open('w') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(runner,'_ACTIVE',None):data,code=runner.start('dashboard-backups',Path('/tmp/test.sqlite3'))
            self.assertEqual(code,409)
