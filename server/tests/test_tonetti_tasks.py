import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tonetti_tasks as plans

class PlansTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=patch.object(plans,'ROOT',Path(self.tmp.name));self.root.start();self.addCleanup(self.root.stop)
  self.task={'id':'dashboard-backups','name':'Copias','description':'Copias consistentes','requirements':['Mac disponible'],'enabled':True,'can_run':True}
  self.snapshot=patch.object(plans.catalogue,'snapshot',return_value={'tasks':[self.task]});self.snapshot.start();self.addCleanup(self.snapshot.stop)
 def plan(self):return plans.create({'id':self.task['id']})[0]
 def test_prepare_never_executes_and_does_not_read_model(self):
  with patch.object(plans.runner,'start') as start:
   value=self.plan();start.assert_not_called()
  self.assertEqual(value['id'],'dashboard-backups');self.assertEqual(len(value['token']),48)
  self.assertNotIn('prompt',json.dumps(value));self.assertEqual((Path(self.tmp.name)/'plans.sqlite3').stat().st_mode&0o777,0o600)
 def test_unknown_injection_extra_fields_and_no_natural_authority(self):
  for body in [None,[],{'id':'../bad'},{'id':'ejecuta todo'},{'id':'dashboard-backups','prompt':'evil'},{'id':'dashboard-backups','attachments':[]}]:
   with self.assertRaises(ValueError):plans.create(body)
  for body in [{},{'token':'../bad'},{'token':'a'*48,'id':'dashboard-backups'}]:
   with self.assertRaises(ValueError):plans.execute(body,Path('/tmp/test.db'))
 def test_paused_or_unavailable_blocks_creation_and_execution(self):
  token=self.plan()['token'];self.task['enabled']=False
  with patch.object(plans.runner,'start') as start:
   with self.assertRaises(ValueError):self.plan()
   with self.assertRaises(ValueError):plans.execute({'token':token},Path('/tmp/test.db'))
   start.assert_not_called()
 def test_expired_and_changed_plans_block(self):
  with patch.object(plans.time,'time',return_value=1000):token=self.plan()['token']
  with patch.object(plans.time,'time',return_value=1600),patch.object(plans.runner,'start') as start:
   self.assertEqual(plans.execute({'token':token},Path('/tmp/test.db'))[1],409);start.assert_not_called()
  token=self.plan()['token'];self.task['description']='Otro procedimiento'
  with patch.object(plans.runner,'start') as start:
   self.assertEqual(plans.execute({'token':token},Path('/tmp/test.db'))[1],409);start.assert_not_called()
 def test_single_use_concurrent_launch_and_final_result(self):
  token=self.plan()['token'];state={'state':'running','started_at':'2026-10-25T10:00:00Z','message':'En marcha'}
  with patch.object(plans.runner,'start',return_value=({'state':'running','started_at':state['started_at']},202)) as start,patch.object(plans.runner,'state',return_value=state):
   with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    codes=list(pool.map(lambda _:plans.execute({'token':token},Path('/tmp/test.db'))[1],range(2)))
   self.assertEqual(sorted(codes),[202,409]);self.assertEqual(start.call_count,1)
   state.update(state='partial',message='Copia pendiente de validar')
   self.assertEqual(plans.status({'token':token})[0]['result']['state'],'partial')
   state['started_at']='otra ejecución'
   self.assertEqual(plans.status({'token':token})[0]['result']['state'],'unknown')
 def test_busy_and_ambiguous_failure_are_never_retried(self):
  for response in [({'error':'Ocupado'},409),RuntimeError('secret')]:
   token=self.plan()['token']
   context=patch.object(plans.runner,'start',side_effect=response) if isinstance(response,Exception) else patch.object(plans.runner,'start',return_value=response)
   with context as start:
    plans.execute({'token':token},Path('/tmp/test.db'))
    self.assertEqual(plans.execute({'token':token},Path('/tmp/test.db'))[1],409);self.assertEqual(start.call_count,1)
   self.assertNotIn('secret',json.dumps(plans.status({'token':token})[0]))
 def test_crash_between_claim_and_receipt_is_uncertain(self):
  token=self.plan()['token']
  from contextlib import closing
  with closing(plans._db()) as db,db:db.execute("UPDATE plans SET state='dispatching' WHERE token=?",(token,))
  self.assertEqual(plans.status({'token':token})[0]['result']['state'],'unknown')
  with patch.object(plans.runner,'start') as start:
   self.assertEqual(plans.execute({'token':token},Path('/tmp/test.db'))[1],409);start.assert_not_called()
 def test_actual_prompt_change_blocks_launch(self):
  self.task['id']='mantener-payloads-de-ps5'
  with patch.object(plans.runner,'_prompt',return_value='original'):token=self.plan()['token']
  with patch.object(plans.runner,'_prompt',return_value='changed'),patch.object(plans.runner,'start') as start:
   self.assertEqual(plans.execute({'token':token},Path('/tmp/test.db'))[1],409);start.assert_not_called()
 def test_runner_rechecks_exact_prompt_before_worker(self):
  import task_runner
  with patch.object(task_runner.CODEX.__class__,'is_file',return_value=True),patch.object(task_runner,'_prompt',return_value='changed'),patch.object(task_runner.threading,'Thread') as thread:
   with self.assertRaises(ValueError):task_runner.start('mantener-payloads-de-ps5',Path('/tmp/test.db'),expected_prompt_digest='old')
   thread.assert_not_called()
