"""The shared SQLite state contains private download URLs and chat IDs."""
from contextlib import closing
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import state_db as db


class PrivateStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/'state'/'state.sqlite3'
        p=patch.object(db,'DB_PATH',self.path)
        p.start();self.addCleanup(p.stop)

    def test_new_database_stays_private_even_with_permissive_umask(self):
        old=os.umask(0)
        try:
            with closing(db.connect()) as conn, conn:
                conn.execute('CREATE TABLE example(value TEXT)')
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode),0o700)

    def test_existing_database_and_journals_are_hardened_without_data_loss(self):
        self.path.parent.mkdir(mode=0o755)
        with closing(db.connect()) as conn, conn:
            conn.execute('CREATE TABLE example(value TEXT)')
            conn.execute("INSERT INTO example VALUES('private')")
        for suffix in ('','-wal','-shm'):
            target=Path(str(self.path)+suffix)
            if suffix:target.touch()
            target.chmod(0o644)
        self.path.parent.chmod(0o755)
        db._prepare_private_database()
        for suffix in ('','-wal','-shm'):
            self.assertEqual(stat.S_IMODE(Path(str(self.path)+suffix).stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode),0o700)
        # Empty journal placeholders are not real WAL data.
        for suffix in ('-wal','-shm'):Path(str(self.path)+suffix).unlink()
        with closing(db.connect()) as conn, conn:
            self.assertEqual(conn.execute('SELECT value FROM example').fetchone()[0],'private')

    def test_symlinked_state_never_chmods_or_opens_the_target(self):
        target=self.root/'other.sqlite3';target.write_bytes(b'other');target.chmod(0o644)
        self.path.parent.mkdir()
        self.path.symlink_to(target)
        with self.assertRaises(OSError):db.connect()
        self.assertEqual(target.read_bytes(),b'other')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o644)

    def test_symlinked_parent_and_journal_are_rejected(self):
        outside=self.root/'outside';outside.mkdir(mode=0o755)
        self.path.parent.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(OSError):db.connect()
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode),0o755)
        self.path.parent.unlink();self.path.parent.mkdir()
        other=self.root/'other';other.write_text('unrelated');other.chmod(0o644)
        Path(str(self.path)+'-wal').symlink_to(other)
        with self.assertRaises(OSError):db.connect()
        self.assertEqual(stat.S_IMODE(other.stat().st_mode),0o644)


if __name__=='__main__':unittest.main()
