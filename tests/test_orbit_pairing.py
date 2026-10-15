import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orbit_pairing as pairing

class PairCodeTests(unittest.TestCase):
    def setUp(self):
        pairing._failures.clear()
        self.env = mock.patch.dict(os.environ, {'ORBIT_PAIR_CODE_PASSWORD': 'testing-password-only'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.headers = {'X-Dashboard-Action': 'write', 'X-Orbit-Action': 'reveal-code',
                        'X-Orbit-Pair-Password': 'testing-password-only'}

    def reveal(self, headers=None):
        return pairing.reveal_code(self.headers if headers is None else headers, ('127.0.0.1', 1234))

    def test_missing_configuration_never_runs_reader(self):
        with mock.patch.dict(os.environ, {'ORBIT_PAIR_CODE_PASSWORD': ''}), mock.patch.object(pairing.subprocess, 'run') as run:
            self.assertEqual(self.reveal()[1], 503); run.assert_not_called()

    def test_wrong_password_never_runs_reader_and_throttles(self):
        self.headers['X-Orbit-Pair-Password'] = 'incorrect'
        with mock.patch.object(pairing.subprocess, 'run') as run:
            for _ in range(5): self.assertEqual(self.reveal()[1], 403)
            self.assertEqual(self.reveal()[1], 429); run.assert_not_called()

    def test_cross_origin_never_runs_reader(self):
        self.headers.update({'Origin': 'https://evil.test', 'Host': 'dashboard.test'})
        with mock.patch.object(pairing.subprocess, 'run') as run:
            self.assertEqual(self.reveal()[1], 403); run.assert_not_called()

    def test_reads_current_code_each_time_without_password_argument(self):
        with mock.patch.object(pairing, 'READER') as reader, mock.patch.object(pairing.subprocess, 'run') as run:
            reader.is_file.return_value = True
            run.side_effect = [subprocess.CompletedProcess([], 0, '{"code":"123456"}'),
                               subprocess.CompletedProcess([], 0, '{"code":"654321"}')]
            self.assertEqual(self.reveal()[0]['code'], '123456')
            self.assertEqual(self.reveal()[0]['code'], '654321')
            self.assertEqual(len(run.call_args.args[0]), 1)
            self.assertNotIn('testing-password-only', repr(run.call_args))

    def test_invalid_code_is_not_returned(self):
        with mock.patch.object(pairing, 'READER') as reader, mock.patch.object(pairing.subprocess, 'run',
                return_value=subprocess.CompletedProcess([], 0, '{"code":"not-a-code"}')):
            reader.is_file.return_value = True
            result, status = self.reveal()
            self.assertEqual(status, 503); self.assertNotIn('code', result)

    def test_permission_error_is_actionable(self):
        with mock.patch.object(pairing, 'READER') as reader, mock.patch.object(pairing.subprocess, 'run',
                return_value=subprocess.CompletedProcess([], 1, '{"error":"permission"}')):
            reader.is_file.return_value = True
            result, status = self.reveal()
            self.assertEqual(status, 503); self.assertIn('Accesibilidad', result['error'])

    def test_timeout_does_not_leak_reader_output(self):
        with mock.patch.object(pairing, 'READER') as reader, mock.patch.object(pairing.subprocess, 'run',
                side_effect=subprocess.TimeoutExpired('reader', 15, output='sensitive')):
            reader.is_file.return_value = True
            result, status = self.reveal()
            self.assertEqual(status, 502); self.assertNotIn('sensitive', str(result))
