import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('tone_migration',ROOT/'scripts/migration.py');migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
class MigrationTests(unittest.TestCase):
 def test_sqlite_copy_preserves_all_rows_binary_and_history(self):
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'old.sqlite3';target=Path(d)/'new.sqlite3'
   with sqlite3.connect(source) as c:
    c.executescript('PRAGMA journal_mode=WAL;CREATE TABLE history(id INTEGER PRIMARY KEY,body TEXT);CREATE TABLE queue(payload BLOB);INSERT INTO history VALUES (1,"historial");INSERT INTO queue VALUES (X\'001122\');')
   expected=migration.verified_database_copy(source,target);self.assertEqual(expected,migration.database_manifest(source));self.assertEqual(expected,migration.database_manifest(target));self.assertEqual(expected['history']['rows'],1);self.assertTrue(source.exists())
 def test_source_never_overwritten(self):
  with self.assertRaises(ValueError):migration.verified_database_copy(ROOT/'VERSION',ROOT/'VERSION')
 def test_one_interface_and_version(self):
  version=(ROOT/'VERSION').read_text().strip();self.assertEqual(version,'1.0.0')
  source=(ROOT/'server/scripts/log-viewer.py').read_text();self.assertIn('HTML = dashboard_html()',source);self.assertNotIn('HTML = r',source);self.assertNotIn('spec_from_file_location',source)
  swift=list((ROOT/'apple/ToneDashboardApps').glob('*.swift'));self.assertEqual(len(swift),5)
  self.assertIn('MARKETING_VERSION = '+version+';',(ROOT/'apple/ToneDashboardApps.xcodeproj/project.pbxproj').read_text())
 def test_no_cookie_wipe_or_javascript_password_bridge(self):
  source='\n'.join(p.read_text() for p in (ROOT/'apple/ToneDashboardApps').glob('*.swift'))
  self.assertNotIn('removeData(',source);self.assertNotIn('WKScriptMessageHandler',source);self.assertIn('legacyWebAccount',source)
