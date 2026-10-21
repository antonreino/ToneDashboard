import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import scheduled_tasks as tasks


class ScheduledTasksTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.automations = self.root / "automations"
        self.audits = self.root / "audits"
        self.database = self.root / "state.sqlite3"
        self.automations.mkdir()
        self.audits.mkdir()

    def automation(self, task_id="future-task", **values):
        data = {"id": task_id, "name": "Nueva comprobación", "kind": "heartbeat", "status": "ACTIVE", "rrule": "FREQ=HOURLY;INTERVAL=3", "prompt": "NEVER_PUBLISH_THIS_PRIVATE_PROMPT"}
        data.update(values)
        folder = self.automations / task_id
        folder.mkdir(exist_ok=True)
        (folder / "automation.toml").write_text("\n".join(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in data.items()))
        return folder

    def report(self, relative, value):
        path = self.audits / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value)
        return path

    def snapshot(self):
        return tasks.snapshot(automations_root=self.automations, audit_root=self.audits, database=self.database)

    def codex(self):
        return [task for task in self.snapshot()["tasks"] if task["executor"] == "Codex"]

    def test_outcome_explains_pending_console_and_preserves_history(self):
        logs = [tasks._event("2026-10-21T08:00:00Z", "partial", "Resultado: PARCIAL. Preparados, sin instalar.\nEstado: Despertada; gestor accesible.\nPendiente: Certificar transferencias y probar arranque.")]
        task = tasks._task("mantener-payloads-de-ps5", "PS5", "", "Codex", True, "Diario", logs, [], "", {"at": "2026-10-21T10:00:00Z", "message": "Revisión posterior"})
        self.assertEqual(task["status"], "partial")
        self.assertIn("Despertada", task["outcome"]["console"])
        self.assertIn("transferencias", task["outcome"]["next_step"])
        self.assertIsNotNone(task["follow_up"])

    def test_missing_logs_never_claim_completed_maintenance(self):
        outcome = tasks._outcome("future-task", "unknown", [])
        self.assertIn("sin ejecución", outcome["title"])
        self.assertNotIn("completada", outcome["title"])

    def test_outcome_redacts_private_report_data(self):
        logs = [tasks._event("2026-10-21T08:00:00Z", "partial", "Resultado: pendiente\nPendiente: revisar http://192.168.1.50/private y /Users/tone/private")]
        outcome = tasks._outcome("mantener-payloads-de-ps5", "partial", logs)
        self.assertNotIn("192.168", str(outcome))
        self.assertNotIn("/Users/tone", str(outcome))

    def test_dynamic_discovery_does_not_publish_prompts_or_raw_schedule(self):
        self.automation()
        result = self.snapshot()
        self.assertEqual(len(self.codex()), 1)
        task = self.codex()[0]
        self.assertEqual(task["schedule"], "Cada 3 horas")
        self.assertEqual(task["status"], "unknown")
        self.assertFalse(task["history_available"])
        self.assertIsNone(task["last_run"])
        rendered = json.dumps(result)
        for private in ("NEVER_PUBLISH", str(self.root), "FREQ=", "automation.toml"):
            self.assertNotIn(private, rendered)
        self.automation("second-task")
        self.assertEqual(len(self.codex()), 2)

    def test_paused_is_distinct_from_missing_logs_and_errors(self):
        self.automation(status="PAUSED")
        task = self.codex()[0]
        self.assertEqual(task["status"], "disabled")
        self.assertFalse(task["enabled"])
        self.assertEqual(self.snapshot()["summary"]["paused"], 1)

    def test_future_tasks_can_add_safe_metadata_and_history(self):
        self.automation()
        self.report("scheduled-tasks/future-task/metadata.json", {"description": "Comprueba las copias de seguridad.", "requirements": ["Servidor accesible"], "command": "rm -rf /", "log_path": "/private/secrets"})
        self.report("scheduled-tasks/future-task/2026-10-21.json", {"at": "2026-10-21T10:00:00Z", "status": "partial", "message": "Dos copias correctas; una pendiente.", "token": "THIS_SHOULD_NOT_APPEAR"})
        task = self.codex()[0]
        self.assertEqual(task["description"], "Comprueba las copias de seguridad.")
        self.assertEqual(task["requirements"], ["Servidor accesible"])
        self.assertEqual(task["status"], "partial")
        self.assertEqual(task["last_run"], "2026-10-21T10:00:00+00:00")
        self.assertEqual(self.snapshot()["summary"]["attention"], 1)
        rendered = json.dumps(task)
        for private in ("rm -rf", "THIS_SHOULD", "log_path", "/private"):
            self.assertNotIn(private, rendered)

    def test_reports_never_disclose_credentials_paths_or_links(self):
        self.automation()
        self.report("scheduled-tasks/future-task/2026-10-21.json", {
            "at": "2026-10-21T10:00:00Z", "status": "error",
            "message": "Falló\npassword=not-a-long-secret\n{\"token\":\"short-private-value\"}\nAuthorization: Bearer short-auth\nCódigo: 43906485\nRuta /Users/private/.ssh/key y ~/private\nHTTPS://user:pass@example.test/?token=abc\n123456789:abcdefghijklmnopq\n192.168.1.50 owner@example.test " + "abcdef" * 12,
        })
        rendered = json.dumps(self.codex())
        for secret in ("not-a-long-secret", "short-private-value", "short-auth", "43906485", "/Users/", "~/private", "user:pass", "token=abc", "abcdefghijklmnopq", "192.168.1.50", "owner@example.test", "abcdef" * 12):
            self.assertNotIn(secret, rendered)

    def test_path_redaction_preserves_dates_slash_lists_and_version_names(self):
        text = "21/10/2026, 171g/vk-285-177. No se han duplicado/reiniciado payloads. Ruta /data/config y C:\\Users\\private\\key y ~/secret y ../private.key y audits/report/RESULTADO.md. error/Users/private/key"
        result = tasks._text(text)
        for public in ("21/10/2026", "171g/vk-285-177", "duplicado/reiniciado"):
            self.assertIn(public, result)
        for private in ("/data/config", "C:\\Users", "~/secret", "../private.key", "audits/report", "/Users/private/key"):
            self.assertNotIn(private, result)

    def test_symlinked_automation_directory_and_file_are_ignored(self):
        real = self.automation("real-task")
        (self.automations / "linked-task").symlink_to(real, target_is_directory=True)
        folder = self.automations / "linked-file"
        folder.mkdir()
        (folder / "automation.toml").symlink_to(real / "automation.toml")
        self.assertEqual([task["id"] for task in self.codex()], ["real-task"])
        self.assertTrue(self.snapshot()["warnings"])

    def test_symlinked_reports_cannot_read_another_file_or_directory(self):
        self.automation()
        outside = self.root / "outside"
        outside.mkdir()
        secret = outside / "private.json"
        secret.write_text(json.dumps({"at": "2026-10-21T10:00:00Z", "status": "ok", "message": "PRIVATE_READ_FORBIDDEN"}))
        folder = self.audits / "scheduled-tasks" / "future-task"
        folder.mkdir(parents=True)
        (folder / "2026-10-21.json").symlink_to(secret)
        self.assertEqual(self.codex()[0]["logs"], [])
        (folder / "2026-10-21.json").unlink()
        folder.rmdir()
        folder.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.codex()[0]["logs"], [])

    def test_malformed_and_oversized_files_do_not_break_catalogue(self):
        self.automation("good")
        folder = self.automation("broken")
        (folder / "automation.toml").write_text("not = [ valid")
        folder = self.automation("large")
        (folder / "automation.toml").write_text("a" * (tasks.MAX_FILE_BYTES + 1))
        self.report("scheduled-tasks/good/invalid.json", {"at": "2026-10-21", "status": "ok", "message": "Missing timezone"})
        self.report("scheduled-tasks/good/large.json", "a" * (tasks.MAX_FILE_BYTES + 1))
        self.report("scheduled-tasks/good/malformed.json", "{{invalid")
        self.assertEqual([task["id"] for task in self.codex()], ["good"])
        self.assertEqual(self.codex()[0]["logs"], [])
        self.assertEqual(len(self.snapshot()["warnings"]), 2)

    def test_invalid_ids_and_folder_mismatch_cannot_select_report_paths(self):
        self.automation("invalid", id="../../private")
        self.automation("different-folder", id="different-task")
        self.assertEqual(self.codex(), [])
        self.assertTrue(self.snapshot()["warnings"])

    def test_log_count_and_message_size_are_bounded_and_sorted(self):
        self.automation()
        for index in range(20):
            self.report(f"scheduled-tasks/future-task/2026-10-{index + 1:02}.json", {"at": f"2026-10-{index + 1:02}T10:00:00Z", "status": "ok", "message": "Resultado correcto. " * 500})
        logs = self.codex()[0]["logs"]
        self.assertEqual(len(logs), tasks.MAX_LOGS)
        self.assertLessEqual(max(len(log["message"]) for log in logs), 2400)
        self.assertTrue(logs[0]["at"].startswith("2026-10-20"))

    def test_arbitrary_report_commands_and_external_paths_are_never_used(self):
        self.automation(log_path="/private/secret", command="curl https://evil.test", prompt="Read /private/secret")
        with patch.object(tasks.sqlite3, "connect", side_effect=AssertionError("must not create a missing database")):
            result = self.snapshot()
        self.assertNotIn("evil.test", json.dumps(result))
        self.assertFalse(self.database.exists())

    def test_anime_results_are_projected_without_private_fields(self):
        self.automation("anime-espa-a-estrenos-y-avisos")
        self.report("anime-calendar/2026-10-21T100000Z.json", {"trigger": "2026-10-21T10:00:00Z", "metadata": {"updated": 35, "failed": [{"error": "private-exception-value"}]}, "notifications": {"sent": 1, "uncertain": 1, "chat_id": "PRIVATE_OWNER"}, "manual_exclusions_preserved": ["private-series"], "sources": ["https://example.test/private"], "result": "Datos conservados."})
        task = self.codex()[0]
        self.assertEqual(task["status"], "partial")
        self.assertIn("35 series", task["logs"][0]["message"])
        self.assertIn("no se repiten", task["logs"][0]["message"])
        for private in ("private-exception", "PRIVATE_OWNER", "private-series", "example.test"):
            self.assertNotIn(private, json.dumps(task))

    def test_weekly_anime_does_not_claim_three_hourly_runs_as_its_own(self):
        self.automation("anime-pr-ximas-temporadas")
        self.report("anime-calendar/2026-10-21.json", {"trigger": "2026-10-21T10:00:00Z", "metadata": {"updated": 35}})
        self.assertEqual(self.codex()[0]["logs"], [])

    def test_anime_legacy_failure_ids_and_explicit_status_are_honoured(self):
        self.automation("anime-espa-a-estrenos-y-avisos")
        self.report("anime-calendar/2026-10-21T100000Z.json", {"trigger": "2026-10-21T10:00:00Z", "status": "partial", "metadata": {"updated": 28, "failed_ids": [str(index) for index in range(7)]}, "limitations": "Consulta temporalmente incompleta."})
        task = self.codex()[0]
        self.assertEqual(task["status"], "partial")
        self.assertIn("7 consultas fallidas", task["logs"][0]["message"])
        self.assertIn("limitaciones", task["logs"][0]["message"])
        self.report("anime-calendar/2026-10-22T100000Z.json", {"trigger": "2026-10-22T10:00:00Z", "status": "error", "metadata": {"updated": 0, "failed": []}})
        self.assertEqual(self.codex()[0]["status"], "error")

    def test_anime_explicit_ok_does_not_mask_string_limitations(self):
        self.automation("anime-espa-a-estrenos-y-avisos")
        self.report("anime-calendar/2026-10-21.json", {"trigger": "2026-10-21T10:00:00Z", "status": "ok", "metadata": {"updated": 35, "failed": []}, "limitations": "La fuente conserva fechas de la semana anterior."})
        self.assertEqual(self.codex()[0]["status"], "partial")

    def test_official_report_summary_distinguishes_partial_and_error(self):
        self.automation("mantener-payloads-de-ps5")
        self.report("ps5-payload-updates/checks/2026-10-21-informe.txt", "Mantenimiento PS5\nResultado: PARCIAL. Preparadas actualizaciones; pendiente instalación.\nNo se reinicia la consola.")
        self.assertEqual(self.codex()[0]["status"], "partial")
        self.assertIn("Preparadas actualizaciones", self.codex()[0]["logs"][0]["message"])
        self.assertEqual(tasks._report_status("Resultado: ERROR. Falló la conexión"), "error")

    def test_report_status_does_not_treat_negated_findings_as_partial(self):
        for report in (
            "Resultado: Correcto. 0 pendientes; sin incidencias.",
            "Resultado: Revisión completada sin errores ni fallos.",
            "Resultado: Sin cambios. No hay actualizaciones pendientes.",
            "Resultado: Correcto. Pendientes: ninguno.",
            "Resultado: Correcto. Incidencia resuelta.",
            "Resultado: Correcto.\n\n## Pendientes\nNinguno.\n\n## Historial\nLa incidencia pasada quedó resuelta.",
        ):
            with self.subTest(report=report):
                self.assertEqual(tasks._report_status(report), "ok")

    def test_report_status_requires_evidence_and_keeps_real_pending_findings(self):
        for report in (
            "Resultado: Revisión completada. Incidencia previa de Home Assistant pendiente de intervención.",
            "Resultado: Correcto. Sin incidencias, pero hay actualizaciones pendientes.",
            "Resultado: Revisión completada.\n\n## Pendientes\n- El agente sigue sin responder.\n",
            "Resultado: Revisión completada.\n\n## Pendientes\n- CT103 requiere planificar migración soportada.\n",
            "Resultado: PARCIAL. Actualizaciones preparadas sin instalar.",
        ):
            with self.subTest(report=report):
                self.assertEqual(tasks._report_status(report), "partial")
        self.assertEqual(tasks._report_status("No consta el resultado. Hay un ejemplo de incidencia."), "unknown")
        self.assertEqual(tasks._report_status("Resultado: consulta registrada."), "unknown")

    def test_follow_up_is_separate_from_historical_result_and_run_time(self):
        self.automation("mantenimiento-semanal-proxmox-y-emby")
        self.report("proxmox-weekly-20261019/INFORME.md", "Resultado: PARCIAL. Incidencia Home Assistant pendiente de intervención.")
        original = self.codex()[0]
        self.report("scheduled-tasks/mantenimiento-semanal-proxmox-y-emby/metadata.json", {"follow_up": {"at": "2026-10-19T07:58:00Z", "message": "Agente y MariaDB revisados después del mantenimiento. Ruta /private/audit omitida.", "status": "ok", "command": "run shell"}})
        updated = self.codex()[0]
        self.assertEqual(updated["status"], "partial")
        self.assertEqual(updated["last_run"], original["last_run"])
        self.assertEqual(updated["logs"], original["logs"])
        self.assertEqual(updated["follow_up"]["at"], "2026-10-19T07:58:00+00:00")
        self.assertIn("Agente y MariaDB", updated["follow_up"]["message"])
        self.assertNotIn("/private", updated["follow_up"]["message"])
        self.assertNotIn("command", updated["follow_up"])
        self.assertNotIn("status", updated["follow_up"])

    def test_follow_up_requires_a_timezone_and_nonempty_safe_message(self):
        self.assertIsNone(tasks._follow_up({"at": "2026-10-19", "message": "No cuenta como ejecución."}))
        self.assertIsNone(tasks._follow_up({"at": "2026-10-19T07:58:00Z", "message": ""}))
        self.assertIsNone(tasks._follow_up("not metadata"))

    def test_proxmox_report_uses_only_known_report_location(self):
        self.automation("mantenimiento-semanal-proxmox-y-emby")
        self.report("proxmox-weekly-20261019/INFORME.md", "# Informe\nResultado: revisión completada sin cambios.")
        self.report("proxmox-private-20261021/INFORME.md", "PRIVATE_NOT_A_TASK_REPORT")
        self.assertEqual(self.codex()[0]["status"], "ok")
        self.assertNotIn("PRIVATE_NOT", json.dumps(self.codex()))

    def test_internal_tasks_read_runtime_without_initializing_or_mutating_database(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE runtime_state (key TEXT, value TEXT, updated_at TEXT)")
            connection.executemany("INSERT INTO runtime_state VALUES (?,?,?)", [("backup_status", json.dumps({"ok": True, "files": [{"snapshot": "/private/snapshot", "database": "private.sqlite"}]}), "2026-10-21T10:00:00Z"), ("amule_recovery", json.dumps({"state": "failed", "error": "PRIVATE_EXCEPTION"}), "2026-10-21T10:00:00Z"), ("private-other", json.dumps({"token": "PRIVATE_TOKEN"}), "2026-10-21T10:00:00Z")])
        before = self.database.read_bytes()
        result = self.snapshot()
        self.assertEqual(before, self.database.read_bytes())
        lookup = {task["id"]: task for task in result["tasks"]}
        self.assertEqual(lookup["dashboard-backups"]["status"], "ok")
        self.assertEqual(lookup["dashboard-amule-recovery"]["status"], "error")
        self.assertEqual(result["summary"]["attention"], 1)
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("private.sqlite", json.dumps(result))

    def test_missing_catalogue_does_not_claim_no_automations_are_scheduled(self):
        self.automations.rmdir()
        result = self.snapshot()
        self.assertTrue(result["warnings"])
        self.assertEqual(result["summary"]["total"], 2)

    def test_schedule_labels_are_readable_and_untrusted_rules_are_not_echoed(self):
        for rule, expected in [("FREQ=WEEKLY;BYDAY=MO;BYHOUR=4;BYMINUTE=0;BYSECOND=0", "Cada lunes a las 04:00"), ("FREQ=DAILY;BYHOUR=10;BYMINUTE=0", "Cada día a las 10:00"), ("FREQ=WEEKLY;BYDAY=MO;BYHOUR=8;BYMINUTE=0", "Cada lunes a las 08:00"), ("FREQ=DAILY;INTERVAL=99999999999", "Horario definido en Codex")]:
            with self.subTest(rule=rule):
                self.assertEqual(tasks._schedule(rule), expected)
        self.assertNotIn("evil", tasks._schedule("FREQ=evil;BYHOUR=secret"))


if __name__ == "__main__":
    unittest.main()
