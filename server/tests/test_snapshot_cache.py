"""Concurrency regressions for the shared metrics cache; no external services."""
from concurrent.futures import Future, ThreadPoolExecutor
import threading
import unittest
from unittest.mock import Mock, patch

from runtime_support import SnapshotCache


class SnapshotCacheTests(unittest.TestCase):
    def test_slow_key_does_not_block_another_key(self):
        cache = SnapshotCache()
        started = threading.Event()
        release = threading.Event()

        def slow_probe():
            started.set()
            if not release.wait(3):
                raise TimeoutError('test probe was not released')
            return 'first snapshot'

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(cache.get, 'first', 60, slow_probe)
            try:
                self.assertTrue(started.wait(2))
                second = pool.submit(cache.get, 'second', 60, lambda: 'second snapshot')
                self.assertEqual(second.result(timeout=2), 'second snapshot')
                self.assertFalse(first.done())
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), 'first snapshot')

    def test_same_key_joins_inflight_probe(self):
        cache = SnapshotCache()
        started = threading.Event()
        release = threading.Event()
        waiting = threading.Event()
        snapshot = {'available': True}

        class ObservedFuture(Future):
            def result(self, timeout=None):
                waiting.set()
                return super().result(timeout)

        def probe():
            started.set()
            if not release.wait(3):
                raise TimeoutError('test probe was not released')
            return snapshot

        loader = Mock(side_effect=probe)
        with patch('runtime_support.Future', ObservedFuture), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(cache.get, 'shared', 60, loader)
            try:
                self.assertTrue(started.wait(2))
                second = pool.submit(cache.get, 'shared', 60, loader)
                self.assertTrue(waiting.wait(2))
                loader.assert_called_once()
            finally:
                release.set()
            self.assertIs(first.result(timeout=2), snapshot)
            self.assertIs(second.result(timeout=2), snapshot)
        self.assertIs(cache.get('shared', 60, loader), snapshot)
        loader.assert_called_once()
        self.assertFalse(cache._inflight)

    def test_failed_probe_reaches_waiters_and_can_be_retried(self):
        cache = SnapshotCache()
        started = threading.Event()
        release = threading.Event()
        waiting = threading.Event()

        class ObservedFuture(Future):
            def result(self, timeout=None):
                waiting.set()
                return super().result(timeout)

        def unavailable():
            started.set()
            if not release.wait(3):
                raise TimeoutError('test probe was not released')
            raise ValueError('probe unavailable')

        loader = Mock(side_effect=unavailable)
        with patch('runtime_support.Future', ObservedFuture), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(cache.get, 'shared', 60, loader)
            try:
                self.assertTrue(started.wait(2))
                second = pool.submit(cache.get, 'shared', 60, loader)
                self.assertTrue(waiting.wait(2))
            finally:
                release.set()
            for result in (first, second):
                with self.assertRaisesRegex(ValueError, 'probe unavailable'):
                    result.result(timeout=2)
        loader.assert_called_once()
        self.assertFalse(cache._inflight)
        self.assertNotIn('shared', cache.values)
        self.assertEqual(cache.get('shared', 60, lambda: 'recovered'), 'recovered')

    def test_ttl_boundary_refreshes_and_empty_values_are_cached(self):
        cache = SnapshotCache()
        loader = Mock(side_effect=[None, 'refreshed'])
        with patch('runtime_support.time.monotonic', return_value=100) as clock:
            self.assertIsNone(cache.get('shared', 10, loader))
            clock.return_value = 109
            self.assertIsNone(cache.get('shared', 10, loader))
            loader.assert_called_once()
            clock.return_value = 110
            self.assertEqual(cache.get('shared', 10, loader), 'refreshed')
            self.assertEqual(loader.call_count, 2)
        self.assertFalse(cache._inflight)

    def test_completed_keys_do_not_accumulate_inflight_coordination(self):
        cache = SnapshotCache()
        for key in range(100):
            self.assertEqual(cache.get(key, 60, lambda: key), key)
        self.assertFalse(cache._inflight)


if __name__ == '__main__':
    unittest.main()
