import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ps5_wake as w

class WakeTests(unittest.TestCase):
    def setUp(self):
        w._last_attempt = 0.0

    def test_states(self):
        for code, state in [(200, 'ready'), (620, 'standby'), (500, 'unknown')]:
            self.assertEqual(w.parse_state(f'HTTP/1.1 {code} Status text\ndevice-discovery-protocol-version:00030010\n'.encode()), state)
    def test_foreign_protocol(self):
        self.assertEqual(w.parse_state(b'HTTP/1.1 620\ndevice-discovery-protocol-version:00020020'), 'unknown')
    def test_no_wake_ready_or_unknown(self):
        for state in ['ready', 'unreachable', 'unknown']:
            with patch.object(w, 'discover', return_value=state), patch.object(w, 'load_key') as key:
                self.assertFalse(w.run(True)['wake_sent'])
                key.assert_not_called()
    def test_missing_pairing(self):
        with patch.object(w, 'discover', return_value='standby'), patch.object(w, 'load_key', side_effect=FileNotFoundError):
            self.assertFalse(w.run(True)['wake_sent'])
    def test_permissions_and_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'key'
            path.write_text('{"host":"192.168.1.50","registration_key":"abcdef"}')
            path.chmod(0o600)
            self.assertEqual(w.load_key(path), 0xabcdef)
            path.chmod(0o644)
            with self.assertRaises(ValueError): w.load_key(path)
    def test_packet(self):
        self.assertIn(b'user-credential:255\n', w.wake_packet(255))
        self.assertTrue(w.wake_packet(255).endswith(b'\0'))
    def test_first_wake_is_allowed_with_recent_monotonic_epoch(self):
        # Linux runners may expose an epoch only seconds old; zero is not an attempt.
        with patch.object(w.time, 'monotonic', return_value=10), patch.object(w, '_run', return_value={'state':'ready','wake_sent':True}) as wake:
            self.assertTrue(w.run(True)['wake_sent'])
            wake.assert_called_once_with(True, 60)
            self.assertEqual(w._last_attempt, 10)

    def test_wake_once(self):
        with patch.object(w, 'discover', side_effect=['standby','ready']), patch.object(w,'load_key',return_value=255), patch.object(w.socket,'socket') as socket, patch.object(w.time,'sleep'):
            result = w.run(True)
            self.assertEqual(result['state'], 'ready')
            socket.return_value.__enter__.return_value.sendto.assert_called_once()

class AvailabilityTests(unittest.TestCase):
    def test_awake_without_orbit_does_not_claim_success(self):
        with patch.object(w, 'run', return_value={'state':'ready','wake_sent':True}), patch.object(w.socket,'create_connection',side_effect=OSError), patch.object(w.time,'monotonic',side_effect=[0,9]):
            self.assertIn('Orbit no responde', w.ensure_console()['error'])
    def test_sleep_wake_and_orbit_ready(self):
        with patch.object(w, 'run', return_value={'state':'ready','wake_sent':True}), patch.object(w.socket,'create_connection'):
            self.assertTrue(w.ensure_console()['console_woken'])
    def test_unreachable_does_not_probe_orbit(self):
        with patch.object(w, 'run', return_value={'state':'unreachable','wake_sent':False}), patch.object(w.socket,'create_connection') as connect:
            self.assertIn('error', w.ensure_console()); connect.assert_not_called()
    def test_wake_cooldown(self):
        w._last_attempt = w.time.monotonic()
        with patch.object(w, 'discover', return_value='standby'), patch.object(w, '_run') as wake:
            self.assertFalse(w.run(True)['wake_sent']); wake.assert_not_called()

class HelperTests(unittest.TestCase):
    def setUp(self):
        w._last_helper_wake = 0
    def test_private_pipe_and_fixed_command(self):
        import os
        import stat
        import subprocess
        def launch(command, **kwargs):
            self.assertEqual(command[:4], ['/usr/bin/open','-n','-g','-W'])
            fifo=Path(command[command.index('--stdout')+1])
            self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
            self.assertEqual(stat.S_IMODE(fifo.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(fifo.parent.stat().st_mode),0o700)
            self.assertNotIn('registration_key',str(command))
            with fifo.open('w') as pipe: pipe.write('{"console_woken":false}')
            return subprocess.CompletedProcess(command,0)
        with patch.object(w.sys,'platform','darwin'), patch.object(w,'HELPER') as helper, patch.object(w.subprocess,'run',side_effect=launch):
            helper.is_dir.return_value=True
            self.assertEqual(w.ensure_from_dashboard(),{'console_woken':False})
    def test_helper_missing_is_actionable(self):
        with patch.object(w.sys,'platform','darwin'), patch.object(w,'HELPER') as helper:
            helper.is_dir.return_value=False
            self.assertIn('Instala',w.ensure_from_dashboard()['error'])
    def test_helper_wake_cooldown_prevents_launch(self):
        w._last_helper_wake=w.time.monotonic()
        with patch.object(w.sys,'platform','darwin'), patch.object(w,'HELPER') as helper, patch.object(w.subprocess,'run') as launch:
            helper.is_dir.return_value=True
            self.assertIn('error',w.ensure_from_dashboard())
            self.assertEqual(launch.call_args.args[0][-2:], ['--args','--check-only'])

if __name__ == '__main__': unittest.main()
