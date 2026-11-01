from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from limpiar_datos_catalogo import purge

class LegacyDataCleanupTests(unittest.TestCase):
    def test_backup_and_preserve_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'state.sqlite3'; backup=Path(tmp)/'backup.sqlite3'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE history(id INTEGER PRIMARY KEY, title TEXT)')
                conn.execute("INSERT INTO history (title) VALUES ('Conservar')")
                conn.execute('CREATE TABLE ps5_games(id INTEGER)')
                conn.execute('CREATE TABLE ps5_releases(id INTEGER)')
            self.assertEqual(set(purge(db)),{'ps5_games','ps5_releases'})
            self.assertFalse(backup.exists())
            self.assertEqual(set(purge(db,backup)),{'ps5_games','ps5_releases'})
            with closing(sqlite3.connect(db)) as conn, conn:
                self.assertEqual(conn.execute('SELECT title FROM history').fetchone()[0],'Conservar')
                self.assertFalse(conn.execute("SELECT 1 FROM sqlite_master WHERE name='ps5_games'").fetchone())
            with closing(sqlite3.connect(backup)) as conn, conn:
                self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE name='ps5_games'").fetchone())
