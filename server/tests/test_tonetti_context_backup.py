import hashlib,json,tempfile,unittest
from pathlib import Path
from tonetti_context_backup import backup_context
class ContextBackupTests(unittest.TestCase):
 def test_only_named_files_private_and_verified(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'live';root.mkdir();(root/'current-facts.json').write_text('{"checked":true}');(root/'.env').write_text('DO_NOT_COPY')
   out=Path(t)/'copies';r=backup_context(root,out);folder=out/r['snapshot']
   self.assertFalse((folder/'.env').exists());self.assertEqual((folder/'current-facts.json').stat().st_mode&0o777,0o600)
   self.assertEqual(r['files'][0]['sha256'],hashlib.sha256((folder/'current-facts.json').read_bytes()).hexdigest())
 def test_symlink_rejected_and_partial_removed(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'live';root.mkdir();outside=Path(t)/'outside';outside.write_text('private');(root/'runbooks.md').symlink_to(outside);out=Path(t)/'copies'
   with self.assertRaises(ValueError):backup_context(root,out)
   self.assertEqual(list(out.iterdir()),[])
 def test_retention_applies_only_to_owned_context_pattern(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'live';root.mkdir();out=Path(t)/'copies';out.mkdir();(out/'other').mkdir()
   for _ in range(3):backup_context(root,out,retain=2)
   self.assertEqual(len(list(out.glob('context-*'))),2);self.assertTrue((out/'other').exists())
