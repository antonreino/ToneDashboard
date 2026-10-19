import os
import unittest
from unittest.mock import Mock,patch
import subprocess
import amule_recovery as r

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'AMULE_ENABLED':'true','AMULE_AUTOSTART':'true'});self.env.start();self.addCleanup(self.env.stop)
        self.platform=patch.object(r.sys,'platform','darwin');self.platform.start();self.addCleanup(self.platform.stop)
        r._LAST_ATTEMPT=None;r._STATE={'state':'disabled'}
    def test_healthy_ec_never_launches(self):
        sock=Mock();sock.__enter__=Mock(return_value=sock);sock.__exit__=Mock(return_value=False)
        with patch.object(r.socket,'create_connection',return_value=sock),patch.object(r.subprocess,'run') as run:
            self.assertEqual(r.ensure_running()['state'],'running');run.assert_not_called()
    def test_running_process_with_failed_ec_is_not_restarted(self):
        with patch.object(r.socket,'create_connection',side_effect=OSError),patch.object(r.subprocess,'run',return_value=Mock(returncode=0)) as run:
            self.assertEqual(r.ensure_running()['state'],'running');self.assertEqual(run.call_count,1);self.assertIn('/usr/bin/pgrep',run.call_args.args[0])
    def test_closed_app_launches_once_with_cooldown_even_low_monotonic_epoch(self):
        with patch.object(r.socket,'create_connection',side_effect=OSError),patch.object(r.Path,'is_file',return_value=True),patch.object(r.subprocess,'run',side_effect=[Mock(returncode=1),Mock(returncode=0),Mock(returncode=1),Mock(returncode=1),Mock(returncode=0)]) as run:
            self.assertEqual(r.ensure_running(clock=lambda:1)['state'],'starting')
            r.ensure_running(clock=lambda:2);self.assertEqual(run.call_count,3)
            r.ensure_running(clock=lambda:122);self.assertEqual(run.call_count,5)
            self.assertEqual(run.call_args.args[0],['/usr/bin/open','-g','-a','/Applications/aMule.app'])
    def test_missing_app_unknown_process_and_disabled_never_launch(self):
        with patch.object(r.socket,'create_connection',side_effect=OSError),patch.object(r.Path,'is_file',return_value=False),patch.object(r.subprocess,'run',return_value=Mock(returncode=1)) as run:
            self.assertEqual(r.ensure_running()['state'],'failed');self.assertEqual(run.call_count,1)
        with patch.object(r.socket,'create_connection',side_effect=OSError),patch.object(r.subprocess,'run',return_value=Mock(returncode=2)) as run:
            self.assertEqual(r.ensure_running()['state'],'unknown');self.assertEqual(run.call_count,1)
        with patch.dict(os.environ,{'AMULE_AUTOSTART':'false'}),patch.object(r.subprocess,'run') as run:
            self.assertEqual(r.ensure_running()['state'],'disabled');run.assert_not_called()
    def test_process_check_timeout_never_opens_second_instance(self):
        with patch.object(r.socket,'create_connection',side_effect=OSError),patch.object(r.subprocess,'run',side_effect=subprocess.TimeoutExpired('pgrep',3)) as run:
            self.assertEqual(r.ensure_running()['state'],'failed');self.assertEqual(run.call_count,1)

class ExistingMaintenanceLoopTests(unittest.TestCase):
    def test_checks_app_every_tick_but_preserves_daily_backup_interval(self):
        import operations
        stop=Mock();stop.is_set.side_effect=[False,False,False,True]
        with patch.object(operations.time,'monotonic',side_effect=[1,31,86401]),patch.object(operations,'backup_all') as backup,patch.object(r,'ensure_running',return_value={'state':'running'}) as ensure,patch.object(operations.state_db,'set_runtime_state'):
            operations.maintenance_loop('/tmp/test-db',stop)
        self.assertEqual(backup.call_count,2);self.assertEqual(ensure.call_count,3)
        self.assertEqual([call.args[0] for call in stop.wait.call_args_list],[30,30,30])
