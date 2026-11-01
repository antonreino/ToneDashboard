import importlib.util,json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('maintenance_bridge',Path(__file__).resolve().parents[1]/'scripts/maintenance_bridge.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class BridgeTests(unittest.TestCase):
 def test_private_job_validated_and_rejects_replay(self):
  with tempfile.TemporaryDirectory(prefix='tone-task-') as name:
   root=Path(name);(root/'prompt.txt').write_text('test');(root/'task.json').write_text(json.dumps({'id':'mantenimiento-semanal-proxmox-y-emby'}));self.assertEqual(bridge.validate_job(name),root.resolve())
   (root/'answer.json').write_text('{}')
   with self.assertRaises(ValueError):bridge.validate_job(name)
 def test_wrong_task_permissions_and_symlink_are_refused(self):
  with tempfile.TemporaryDirectory(prefix='tone-task-') as name:
   root=Path(name);(root/'prompt.txt').write_text('test');(root/'task.json').write_text(json.dumps({'id':'other'}))
   with self.assertRaises(ValueError):bridge.validate_job(name)
   (root/'task.json').write_text(json.dumps({'id':'mantener-payloads-de-ps5'}));root.chmod(0o755)
   with self.assertRaises(ValueError):bridge.validate_job(name)
 def test_ps5_id_is_allowed_but_other_ids_are_not(self):
  with tempfile.TemporaryDirectory(prefix='tone-task-') as name:
   root=Path(name);(root/'prompt.txt').write_text('test');(root/'task.json').write_text(json.dumps({'id':'mantener-payloads-de-ps5'}))
   self.assertEqual(bridge.validate_job(name),root.resolve())
   (root/'task.json').write_text(json.dumps({'id':'dashboard-backups'}))
   with self.assertRaises(ValueError):bridge.validate_job(name)
   root.chmod(0o700);(root/'prompt.txt').unlink();(root/'prompt.txt').symlink_to(root/'task.json')
   with self.assertRaises(ValueError):bridge.validate_job(name)
