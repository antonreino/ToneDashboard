"""Bounded log reads, shared snapshots and verified SQLite backups."""
from contextlib import closing
from concurrent.futures import Future
from pathlib import Path
import os
import sqlite3
import threading
import time

class SnapshotCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.values = {}
        self._inflight = {}

    def get(self, key, ttl, loader):
        """Share one load per key without blocking unrelated snapshots.

        Futures exist only while their loader runs. Failures reach the callers
        already waiting for that load and are never stored as cached values.
        """
        with self.lock:
            now = time.monotonic()
            value = self.values.get(key)
            if value and now - value[0] < ttl:
                return value[1]
            pending = self._inflight.get(key)
            owner = pending is None
            if owner:
                pending = Future()
                self._inflight[key] = pending

        if not owner:
            return pending.result()

        try:
            result = loader()
        except BaseException as exc:
            with self.lock:
                self._inflight.pop(key)
            pending.set_exception(exc)
            raise

        with self.lock:
            self.values[key] = (time.monotonic(), result)
            self._inflight.pop(key)
        pending.set_result(result)
        return result

snapshots = SnapshotCache()

def tail_text(path, lines, max_bytes=512*1024):
    """Read at most max_bytes backwards; never scan an entire growing log."""
    with Path(path).open('rb') as stream:
        stream.seek(0, 2)
        end = stream.tell()
        chunks, size, count = [], 0, 0
        while end and count <= lines and size < max_bytes:
            n = min(8192, end, max_bytes-size)
            end -= n
            stream.seek(end)
            chunk = stream.read(n)
            chunks.append(chunk);size += len(chunk);count += chunk.count(b'\n')
        data = b''.join(reversed(chunks))
        if end:
            data = data.partition(b'\n')[2]
        return '\n'.join(data.decode('utf-8', errors='replace').splitlines()[-lines:])

def backup_database(source, directory, retain=14):
    """Use SQLite's online backup API, including committed WAL data."""
    source, directory = Path(source), Path(directory)
    if not source.is_file():
        raise FileNotFoundError(source.name)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = source.stem + '-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns()) + '.sqlite3'
    target = directory/name
    staging=target.with_suffix('.partial')
    fd = os.open(staging, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600);os.close(fd)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True)) as src, closing(sqlite3.connect(staging)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('La copia SQLite no supera la comprobación de integridad')
        os.replace(staging,target)
        for old in sorted(directory.glob(source.stem+'-*.sqlite3'), key=lambda p:p.stat().st_mtime, reverse=True)[retain:]:
            if old.is_file() and not old.is_symlink():old.unlink()
        return target
    except Exception:
        staging.unlink(missing_ok=True)
        raise


from http.server import ThreadingHTTPServer
class BoundedHTTPServer(ThreadingHTTPServer):
    """Bound concurrent requests and stalled headers; WebSocket handshakes opt out."""
    daemon_threads=True
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(32)
        super().__init__(*args,**kwargs)
    def get_request(self):
        connection,address=super().get_request();connection.settimeout(20);return connection,address
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            try:request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except Exception:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
