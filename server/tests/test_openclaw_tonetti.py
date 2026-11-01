import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import openclaw_tonetti as bridge


class OpenClawBridgeTests(unittest.TestCase):
    def test_session_is_stable_and_response_is_parsed(self):
        payload={"runId":"run-1","status":"ok","result":{"payloads":[{"text":"Hola Tone"}],"meta":{"durationMs":1250,"agentMeta":{"model":"qwen","usage":{"input":20,"output":3}}},"aborted":False}}
        completed=type("Result",(),{"returncode":0,"stdout":json.dumps(payload),"stderr":""})()
        metrics={}
        with patch.object(bridge,"_cli",return_value="/safe/openclaw"),patch.object(bridge.subprocess,"run",return_value=completed) as run:
            answer,evidence=bridge.generate("/tmp","ignored","hola",conversation_id=42,telemetry=metrics)
        self.assertEqual(answer,"Hola Tone")
        command=run.call_args.args[0]
        self.assertEqual(command[command.index("--agent")+1],"main")
        self.assertRegex(command[command.index("--session-key")+1],r"^agent:main:tone-dashboard-v4-fast-agent-[a-f0-9]{12}-42$")
        self.assertNotIn("hola",command)
        self.assertEqual(metrics["path"],"openclaw")
        self.assertEqual(evidence[0]["source"],"agent")

    def test_rejects_failed_empty_and_oversized_results(self):
        for payload in [
            {"status":"error","result":{}},
            {"status":"ok","result":{"payloads":[],"aborted":False}},
            {"status":"ok","result":{"payloads":[{"text":"x"}],"aborted":True}},
        ]:
            completed=type("Result",(),{"returncode":0,"stdout":json.dumps(payload),"stderr":""})()
            with patch.object(bridge,"_cli",return_value="/safe/openclaw"),patch.object(bridge.subprocess,"run",return_value=completed):
                with self.assertRaises(bridge.OpenClawError):bridge.generate("/tmp","ignored","hola")

    def test_preloaded_code_does_not_override_reviewed_agent_model(self):
        payload={"runId":"run-code","status":"ok","result":{"payloads":[{"text":"Revisión"}],"meta":{},"aborted":False}}
        completed=type("Result",(),{"returncode":0,"stdout":json.dumps(payload),"stderr":""})()
        context="ARCHIVO SOLICITADO `demo.py` EN `/tmp/demo.py`:\n```py\nVALUE=1\n```"
        with patch.object(bridge,"_named_file_context",return_value=context),patch.object(bridge,"_cli",return_value="/safe/openclaw"),patch.object(bridge.subprocess,"run",return_value=completed) as run:
            bridge.generate("/tmp","ignored","Revisa demo.py")
        command=run.call_args.args[0]
        self.assertNotIn("--model",command)

    def test_printed_tool_call_is_rejected(self):
        payload={"status":"ok","result":{"payloads":[{"text":'{"name":"openclaw_tool_call","arguments":{}}'}],"aborted":False}}
        with self.assertRaisesRegex(bridge.OpenClawError,"sin ejecutar"):
            bridge._answer(payload)

    def test_plain_language_tool_name_is_not_mistaken_for_a_call(self):
        payload={"status":"ok","result":{"payloads":[{"text":"No necesitas usar openclaw_tool_call para esta explicación."}],"aborted":False}}
        self.assertEqual(
            bridge._answer(payload),
            "No necesitas usar openclaw_tool_call para esta explicación.",
        )

    def test_python_network_review_is_evidence_based_and_skips_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/"ToneDashboard"/"data"/"tonetti";root.mkdir(parents=True)
            source=base/"pokémon.py";source.write_text("import requests\ndef load(url):\n    return requests.get(url).content\n",encoding="utf-8")
            metrics={}
            with patch.object(bridge.subprocess,"run") as run:
                answer,evidence=bridge.generate(root,"ignored","Revisa Pokemon.py en la carpeta raíz de Scripts",telemetry=metrics)
            run.assert_not_called()
            self.assertIn("línea 3",answer);self.assertIn("timeout",answer);self.assertIn("RequestException",answer)
            self.assertEqual(metrics["path"],"local-python-analysis")
            self.assertEqual(evidence[0]["source"],"local-static-analysis")

    def test_requested_code_fix_reaches_operational_agent(self):
        payload={"runId":"run-fix","status":"ok","result":{"payloads":[{"text":"Corregido y verificado"}],"meta":{},"aborted":False}}
        completed=type("Result",(),{"returncode":0,"stdout":json.dumps(payload),"stderr":""})()
        context="ARCHIVO SOLICITADO `demo.py` EN `/tmp/demo.py`:\n```py\nVALUE=1\n```"
        with patch.object(bridge,"_named_file_context",return_value=context),patch.object(bridge,"_cli",return_value="/safe/openclaw"),patch.object(bridge.subprocess,"run",return_value=completed) as run:
            answer,_=bridge.generate("/tmp","ignored","Corrige demo.py")
        self.assertEqual(answer,"Corregido y verificado")
        self.assertEqual(run.call_args.args[0][run.call_args.args[0].index("--agent")+1],"main")

    def test_attachment_text_and_image_paths_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/"attachments";folder.mkdir();ident="a"*32
            (folder/(ident+".jpg")).write_bytes(b"jpeg")
            text=bridge._attachment_prompt(root,[ident],lambda ids:("nota segura",["base64"]))
            self.assertIn("nota segura",text);self.assertIn(str(folder/(ident+".jpg")),text)
            (folder/(ident+".jpg")).unlink()
            with self.assertRaises(bridge.OpenClawError):bridge._attachment_prompt(root,[ident],lambda ids:("",["base64"]))

    def test_secrets_from_stderr_are_not_exposed(self):
        completed=type("Result",(),{"returncode":2,"stdout":"","stderr":"TOKEN=private"})()
        with patch.object(bridge,"_cli",return_value="/safe/openclaw"),patch.object(bridge.subprocess,"run",return_value=completed):
            with self.assertRaisesRegex(bridge.OpenClawError,"OpenClaw no pudo") as caught:
                bridge.generate("/tmp","ignored","hola")
        self.assertNotIn("private",str(caught.exception))

    def test_named_source_is_preloaded_and_missing_file_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/"ToneDashboard"/"data"/"tonetti";root.mkdir(parents=True)
            source=base/"Pokemon.py";source.write_text("VALUE = 7\n",encoding="utf-8")
            found=bridge._named_file_context(root,"Revisa Pokemon.py")
            self.assertIn(str(source),found);self.assertIn("VALUE = 7",found)
            source.unlink()
            missing=bridge._named_file_context(root,"Revisa Pokemon.py")
            self.assertIn("no existe",missing)

    def test_root_filename_matching_accepts_case_and_diacritics(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/"ToneDashboard"/"data"/"tonetti";root.mkdir(parents=True)
            source=base/"pokémon.py";source.write_text("VALUE = 9\n",encoding="utf-8")
            found=bridge._named_file_context(root,"Revisa Pokemon.py en la carpeta raíz de Scripts")
            self.assertIn(str(source),found);self.assertIn("VALUE = 9",found)
            prompt=bridge._grounding_prompt(root,1,"Revisa Pokemon.py",found)
            self.assertIn("CONTRATO DE REVISIÓN DE CÓDIGO",prompt)
            self.assertIn("fragmento literal",prompt)

    def test_recent_context_uses_only_user_messages_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);db=sqlite3.connect(root/"chat.sqlite3")
            db.executescript("CREATE TABLE messages(id INTEGER PRIMARY KEY,conversation_id INTEGER,role TEXT,content TEXT,state TEXT);")
            db.execute("INSERT INTO messages VALUES(1,1,'user','archivo anterior','done')")
            db.execute("INSERT INTO messages VALUES(2,1,'assistant','dato inventado','done')")
            db.execute("INSERT INTO messages VALUES(3,1,'user','password=privada','done')");db.commit();db.close()
            context=bridge._recent_user_context(root,1)
            self.assertIn("archivo anterior",context);self.assertNotIn("dato inventado",context);self.assertNotIn("privada",context)

    def test_filename_followup_recovers_previous_user_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/"ToneDashboard"/"data"/"tonetti";root.mkdir(parents=True)
            source=base/"pokémon.py";source.write_text("import requests\ndef load(url):\n    return requests.get(url).content\n",encoding="utf-8")
            db=sqlite3.connect(root/"chat.sqlite3")
            db.executescript("CREATE TABLE messages(id INTEGER PRIMARY KEY,conversation_id INTEGER,role TEXT,content TEXT,state TEXT);")
            db.execute("INSERT INTO messages VALUES(1,1,'user','Eres capaz de leer y explicarme el código de Pokemon.py','done')")
            db.execute("INSERT INTO messages VALUES(2,1,'assistant','No encuentro el archivo','done')")
            db.execute("INSERT INTO messages VALUES(3,1,'user','pokémon.py','done')");db.commit();db.close()
            effective=bridge._contextual_query(root,1,"pokémon.py")
            self.assertIn("leer y explicarme",effective)
            self.assertIn("pokémon.py",effective)
            with patch.object(bridge.subprocess,"run") as run:
                answer,evidence=bridge.generate(root,"ignored","pokémon.py",conversation_id=1)
            run.assert_not_called()
            self.assertIn("timeout",answer)
            self.assertEqual(evidence[0]["source"],"local-static-analysis")

    def test_missing_named_file_is_answered_without_model_or_false_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/"ToneDashboard"/"data"/"tonetti";root.mkdir(parents=True)
            metrics={}
            missing="ARCHIVO SOLICITADO `Pokemon.py`: no existe bajo `"+str(base)+"` según el inventario local de este turno."
            with patch.object(bridge,"_named_file_context",return_value=missing),patch.object(bridge.subprocess,"run") as run:
                answer,evidence=bridge.generate(root,"ignored","Revisa Pokemon.py",telemetry=metrics)
            run.assert_not_called()
            self.assertIn("no encuentro",answer);self.assertIn("Confirma el nombre",answer)
            self.assertNotIn("voy a",answer.casefold())
            self.assertEqual(metrics["path"],"local-file-preflight")
            self.assertEqual(evidence[0]["source"],"local-inventory")
