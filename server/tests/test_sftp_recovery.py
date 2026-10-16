import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import emby_organizer as m

class SftpRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.u=m.SftpUploader.__new__(m.SftpUploader);self.u.targets={k:m.SftpTarget('user','host',22,'/'+k) for k in ['movies','series','anime']};self.u.close=Mock()
 def test_directory_eof_reconnects_once(self):
  broken=Mock();broken.listdir_attr.side_effect=EOFError();healthy=Mock();healthy.listdir_attr.return_value=[SimpleNamespace(filename='Ted Lasso',st_mode=0o40755)]
  self.u._connect=Mock(side_effect=[(broken,self.u.targets['series']),(healthy,self.u.targets['series'])])
  self.assertEqual(self.u.list_remote_dirs('series'),['Ted Lasso']);self.assertEqual(self.u._connect.call_count,2);self.u.close.assert_called_once()
 def test_ssh_channel_exception_reconnects(self):
  self.u._connect=Mock(return_value=(Mock(),self.u.targets['series']));operation=Mock(side_effect=[m.paramiko.SSHException('closed'),42]);self.assertEqual(self.u._with_reconnect('series',operation),42)
 def test_second_failure_is_bounded_and_drops_connection(self):
  self.u._connect=Mock(return_value=(Mock(),self.u.targets['series']));operation=Mock(side_effect=EOFError())
  with self.assertRaises(EOFError):self.u._with_reconnect('series',operation)
  self.assertEqual(operation.call_count,2);self.assertEqual(self.u.close.call_count,2)
 def test_security_error_is_not_retried(self):
  self.u._connect=Mock(side_effect=m.OrganizerError('host key changed'))
  with self.assertRaises(m.OrganizerError):self.u._with_reconnect('series',Mock())
  self.assertEqual(self.u._connect.call_count,1)
 def test_missing_library_is_empty_without_reconnect(self):
  sftp=Mock();sftp.listdir_attr.side_effect=FileNotFoundError();self.u._connect=Mock(return_value=(sftp,self.u.targets['series']));self.assertEqual(self.u.list_remote_dirs('series'),[]);self.u.close.assert_not_called()
 def test_storage_recovers_dead_session(self):
  first=Mock();first.statvfs.side_effect=EOFError();second=Mock();second.statvfs.return_value=SimpleNamespace(f_frsize=4096,f_bsize=4096,f_blocks=100,f_bfree=30,f_bavail=20)
  self.u._connect=Mock(side_effect=[(first,self.u.targets['movies']),(second,self.u.targets['movies'])]);self.u._transport=Mock();self.u._transport.open_session.side_effect=EOFError()
  d=self.u.storage_info();self.assertEqual(d['free'],81920);self.assertEqual(d['used'],286720);self.u.close.assert_called_once()
 def test_metrics_recovers_and_parses_samples(self):
  channel=Mock();channel.makefile.return_value=io.BytesIO(b'cpu 100 0 0 900 0 0 0 0\ncpu 120 0 0 980 0 0 0 0\nMemTotal: 8192 kB\nMemAvailable: 2048 kB\n0.1 0.2 0.3 1/100 22\n');channel.makefile_stderr.return_value=io.BytesIO(b'');channel.recv_exit_status.return_value=0
  self.u._transport=Mock();self.u._transport.open_session.side_effect=[EOFError(),channel];self.u._connect=Mock(return_value=(Mock(),self.u.targets['movies']))
  d=self.u.system_info();self.assertEqual(d['cpu_percent'],20);self.assertEqual(d['ram_used'],6144*1024);self.assertEqual(d['load_15'],0.3);channel.settimeout.assert_called_once_with(10);self.u.close.assert_called_once()
 def test_closed_sftp_channel_is_not_reused(self):
  u=m.SftpUploader.__new__(m.SftpUploader);u.targets=self.u.targets;u._password=None;u._active_key=('user','host',22);u._transport=Mock();u._transport.is_active.return_value=True;u._sftp=Mock();u._sftp.get_channel.return_value.closed=True;u.close=Mock()
  client=Mock();client.get_transport.return_value.is_active.return_value=True
  with patch.object(m,'EMBY_SFTP_KNOWN_HOSTS',Path(__file__)),patch.object(m.paramiko,'SSHClient',return_value=client):u._connect('movies')
  client.connect.assert_called_once();client.set_missing_host_key_policy.assert_called_once();client.get_transport.return_value.set_keepalive.assert_called_once_with(30);client.open_sftp.return_value.get_channel.return_value.settimeout.assert_called_once_with(15)
 def test_empty_exception_and_secret_have_useful_safe_text(self):
  self.assertIn('EOFError',m.error_summary(EOFError()))
  with patch.dict(m.os.environ,{'EMBY_SFTP_PASSWORD':'secret-password'}):self.assertNotIn('secret-password',m.error_summary(OSError('secret-password')))
 def test_resolution_failure_keeps_cause(self):
  org=m.MediaOrganizer.__new__(m.MediaOrganizer);org.uploader=Mock();org.uploader.list_remote_dirs.side_effect=EOFError()
  with self.assertRaisesRegex(m.OrganizerError,r'biblioteca remota \(series\).*EOFError'):org.resolve_existing_series('Ted Lasso','series')
