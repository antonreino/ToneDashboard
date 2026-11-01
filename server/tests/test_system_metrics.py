"""Physical RAM and pressure are independent macOS readings."""
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import system_metrics as metrics


class MemoryMetricsTests(unittest.TestCase):
    def snapshot(self, physical="17179869184", top="PhysMem: 15G used (3G wired), 170M unused."):
        def command(args, **kwargs):
            if args[0] == "/usr/bin/top":
                return SimpleNamespace(returncode=0, stdout=top)
            if args[-1] == "hw.memsize":
                if isinstance(physical, Exception):
                    raise physical
                return SimpleNamespace(returncode=0, stdout=physical)
            if args[0] == "/usr/bin/memory_pressure":
                return SimpleNamespace(returncode=0, stdout="System-wide memory free percentage: 59%")
            if args[-1] == "vm.swapusage":
                return SimpleNamespace(returncode=0, stdout="used = 1380.56M")
            raise AssertionError(args)
        with patch.object(metrics.sys, 'platform', 'darwin'), patch.object(metrics.subprocess, 'run', side_effect=command), patch.object(metrics, '_network_totals', return_value=(0, 0)), patch.object(metrics, '_apple_silicon_metrics', return_value={}), patch.object(metrics, '_METRICS_CACHE', {'at': 0, 'value': None}), patch.object(metrics, '_NET_SAMPLE', None):
            return metrics.mac_system_snapshot()

    def test_rounded_top_cannot_reduce_installed_ram_or_inflate_percentage(self):
        value=self.snapshot()
        self.assertEqual(value['ram_total'], 16*1024**3)
        self.assertEqual(value['ram_used'], 15*1024**3)
        self.assertEqual(value['ram_percent'], 93.8)
        self.assertEqual(value['memory_free_percent'], 59)

    def test_unavailable_or_invalid_physical_reading_keeps_top_fallback(self):
        for value in ('', '0', '-1', 'bad', OSError('unavailable'), subprocess.TimeoutExpired('sysctl', 2)):
            with self.subTest(value=value):
                result=self.snapshot(value)
                self.assertEqual(result['ram_total'], 15*1024**3+170*1024**2)
                self.assertEqual(result['ram_percent'], 98.9)

    def test_physical_total_survives_missing_top_reading_without_inventing_usage(self):
        value=self.snapshot(top='unavailable')
        self.assertEqual(value['ram_total'], 16*1024**3)
        self.assertIsNone(value['ram_used'])
        self.assertIsNone(value['ram_percent'])

    def test_rounded_used_value_cannot_exceed_physical_ram(self):
        value=self.snapshot(top='PhysMem: 17G used, 1M unused.')
        self.assertEqual(value['ram_used'], 16*1024**3)
        self.assertEqual(value['ram_percent'], 100)


if __name__=='__main__':
    unittest.main()
