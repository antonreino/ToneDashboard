"""Run the real shell scheduler with fake inotifywait/curl; no network or media writes."""
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/emby-watch-refresh.sh'


class RefreshWatcherTests(unittest.TestCase):
    def scenario(self, events, duration, minimum=0, failures=0):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher = root / 'inotifywait'
            watcher.write_text('#!/bin/bash\n' + events + '\nsleep 20\n')
            curl = root / 'curl'
            curl.write_text('''#!/bin/bash
printf 'call\\n' >> "$CALLS"
n=$(wc -l < "$CALLS")
[ "$n" -gt "$FAILURES" ]
''')
            watcher.chmod(0o755)
            curl.chmod(0o755)
            calls = root / 'calls'
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       EMBY_WATCH_DIR=tmp, EMBY_URL='http://unused', EMBY_API_KEY='test',
                       COOLDOWN='1', MIN_REFRESH_INTERVAL=str(minimum), RETRY_INTERVAL='1',
                       CALLS=str(calls), FAILURES=str(failures), TELEGRAM_BOT_TOKEN='', TELEGRAM_CHAT_ID='')
            process = subprocess.Popen(['bash', str(SCRIPT)], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                time.sleep(duration)
                self.assertIsNone(process.poll(), 'watcher exited unexpectedly')
                return len(calls.read_text().splitlines()) if calls.exists() else 0
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                output, errors = process.communicate(timeout=5)
                if process.returncode not in (0, -signal.SIGTERM):
                    print(errors.decode())

    def test_burst_debounced_and_temporary_files_ignored(self):
        count = self.scenario("printf 'CREATE,ISDIR|/media/Show\\nCLOSE_WRITE|/media/a.mkv.uploading\\nMOVED_TO|/media/a.mkv\\nMOVED_TO|/media/b.MOV\\n'", 3)
        self.assertEqual(count, 1)

    def test_refresh_inside_minimum_interval_is_deferred(self):
        count = self.scenario("printf 'MOVED_TO|/media/a.mkv\\n'\nsleep 2\nprintf 'MOVED_TO|/media/b.mkv\\n'", 7, minimum=4)
        self.assertEqual(count, 2)

    def test_failed_refresh_retries_without_new_events(self):
        count = self.scenario("printf 'MOVED_TO|/media/a.mkv\\n'", 4, minimum=300, failures=1)
        self.assertEqual(count, 2)

    def test_directory_and_incomplete_upload_do_not_refresh(self):
        count = self.scenario("printf 'CREATE,ISDIR|/media/Show\\nCLOSE_WRITE|/media/a.mkv.uploading\\n'", 2)
        self.assertEqual(count, 0)
