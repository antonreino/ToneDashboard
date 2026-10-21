"""Read-only task catalogue. Never execute an automation or publish its prompt.

Only explicit report formats are read; automation prompts cannot select files,
commands, URLs or database queries. All client-visible text is bounded/redacted.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tomllib
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTOMATIONS_ROOT = Path.home() / ".codex" / "automations"
AUDIT_ROOT = PROJECT_ROOT.parent / "audits"
DATABASE = Path.home() / ".local" / "share" / "emby_organizer" / "state.sqlite3"
TIMEZONE = "Europe/Madrid"
MAX_AUTOMATIONS = 100
MAX_REPORTS = 200
MAX_LOGS = 8
MAX_FILE_BYTES = 128 * 1024
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,95}\Z")
_STATUSES = {"ok", "partial", "error", "unknown"}
_LABELS = {"ok": "Correcto", "partial": "Parcial", "error": "Error", "unknown": "Sin registros", "disabled": "Pausada"}

# Curated descriptions explain intent without disclosing private instructions.
_PROFILES = {
    "anime-espa-a-estrenos-y-avisos": {
        "description": "Actualiza las portadas y comprueba estrenos originales en Japón y doblajes en castellano. Avisa por Telegram cuando la publicación está confirmada, sin repetir avisos.",
        "requirements": ["Mac y Codex disponibles", "Fuentes públicas accesibles"],
        "report_type": "anime",
    },
    "anime-pr-ximas-temporadas": {
        "description": "Investiga nuevas temporadas y continuaciones, también películas, de todos los animes seguidos. Los archivados siguen vigilados; respeta las bajas manuales.",
        "requirements": ["Mac y Codex disponibles", "Fuentes públicas accesibles"],
        "report_type": "anime-weekly",
    },
    "mantener-payloads-de-ps5": {
        "description": "Comprueba versiones oficiales de los payloads y prepara actualizaciones compatibles con recuperación. Puede despertar la consola emparejada; aplaza la instalación si no puede comprobar juegos o transferencias. Envía un informe diario por Telegram.",
        "requirements": ["Mac y Codex disponibles", "PS5 accesible para instalar", "Prueba manual para cambios de arranque"],
        "report_type": "ps5",
    },
    "mantenimiento-semanal-proxmox-y-emby": {
        "description": "Revisa Proxmox, contenedores y aplicaciones, con copias y comprobaciones posteriores. Aplaza reinicios con actividad y envía un informe por Telegram incluso sin cambios. No reinicia el host automáticamente.",
        "requirements": ["Mac y Codex disponibles", "Servidor accesible", "Autorización adicional para cambios de versión principal"],
        "report_type": "proxmox",
    },
}


def _text(value: Any, limit: int = 1000) -> str:
    """Defence in depth for human-authored reports; never use for raw prompts."""
    if not isinstance(value, str):
        return ""
    value = value[:16_384]
    # Drop entire assignment lines: a secret need not have a predictable format.
    value = re.sub(r"(?s)-----BEGIN [^-]+-----.*?-----END [^-]+-----", "[credencial omitida]", value)
    value = re.sub(r"(?im)^.*\b(?:password|passwd|contrase(?:ña|na)|secret|credential|credencial|token|authorization|api[_ -]?key|chat[_ -]?id|account[_ -]?id|c[oó]digo|clave|pin)[\"']?\s*[:=].*$", "[dato privado omitido]", value)
    value = re.sub(r"(?i)\bBearer\s+\S+", "[credencial omitida]", value)
    value = re.sub(r"(?i)\b[a-z][a-z0-9+.-]{1,12}://[^\s<>]+", "[enlace omitido]", value)
    # A slash inside a word, date or version is not an absolute path. Keep
    # "21/10/2026", "duplicado/reiniciado" and "171g/vk-285-177" readable.
    value = re.sub(r"(?<![\w./-])(?:[A-Za-z]:[\\/]|~/|/)[^\s,;<>\"']+", "[ruta omitida]", value)
    # Protect common private roots even if a logger concatenated its label
    # without a separating space, e.g. "error/Users/...".
    value = re.sub(r"/(?:Users|Volumes|private|tmp|var|home|data|etc|Applications|opt|root|run|media|mnt|srv)(?=/|\b)[^\s,;<>\"']*", "[ruta omitida]", value)
    value = re.sub(r"(?<![\w.-])(?:\.{1,2}/|(?:audits|server|infra-maintenance)/)[^\s,;<>\"']+", "[ruta omitida]", value)
    value = re.sub(r"\b\d{5,}:[A-Za-z0-9_-]{15,}\b", "[credencial omitida]", value)
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[red privada]", value)
    value = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[correo omitido]", value)
    value = re.sub(r"\b[A-Za-z0-9_+=-]{32,}\b", "[identificador omitido]", value)
    value = "".join(c for c in value if c in "\n\t" or ord(c) >= 32)
    return value.strip()[:limit]


def _read(path: Path, root: Path) -> str | None:
    """No symlinks, traversal, special files, oversized input or unbounded reads."""
    try:
        base = root.absolute()
        relative = path.absolute().relative_to(base)
        current = base
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return None
        if base.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
            return None
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                return None
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            return None
        return raw.decode("utf-8")
    except (OSError, ValueError, UnicodeError):
        return None


def _json(path: Path, root: Path) -> dict[str, Any] | None:
    raw = _read(path, root)
    try:
        value = json.loads(raw) if raw is not None else None
        return value if isinstance(value, dict) else None
    except (ValueError, RecursionError):
        return None


def _timestamp(value: Any) -> str | None:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            instant = datetime.fromtimestamp(value / 1000, timezone.utc)
        elif isinstance(value, str):
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                # A report with only a date cannot assert a precise run time.
                return None
        else:
            return None
        return instant.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OverflowError, OSError):
        return None


def _file_time(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return None


def _count(value: Any) -> int:
    return max(0, min(value, 1_000_000)) if isinstance(value, int) and not isinstance(value, bool) else 0


def _schedule(rule: Any) -> str:
    if not isinstance(rule, str) or len(rule) > 512:
        return "Horario no disponible"
    parts = dict(part.split("=", 1) for part in rule.removeprefix("RRULE:").split(";") if "=" in part)
    interval = parts.get("INTERVAL", "1")
    if not interval.isdigit() or not 1 <= int(interval) <= 365:
        return "Horario definido en Codex"
    frequency = parts.get("FREQ")
    if frequency in {"HOURLY", "MINUTELY"}:
        unit = "horas" if frequency == "HOURLY" else "minutos"
        return f"Cada {int(interval)} {unit}" if interval != "1" else ("Cada hora" if frequency == "HOURLY" else "Cada minuto")
    hour, minute = parts.get("BYHOUR", ""), parts.get("BYMINUTE", "0")
    clock = f" a las {int(hour):02}:{int(minute):02}" if hour.isdigit() and minute.isdigit() and 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59 else ""
    if frequency == "DAILY":
        return ("Cada día" if interval == "1" else f"Cada {int(interval)} días") + clock
    if frequency == "WEEKLY":
        days = {"MO": "lunes", "TU": "martes", "WE": "miércoles", "TH": "jueves", "FR": "viernes", "SA": "sábado", "SU": "domingo"}
        selected = [days[day] for day in parts.get("BYDAY", "").split(",") if day in days]
        prefix = "Cada " + ", ".join(selected) if selected and interval == "1" else f"Cada {int(interval)} semanas"
        return prefix + clock
    return "Horario definido en Codex"


def _event(at: Any, status: str, message: str) -> dict[str, Any]:
    return {"at": _timestamp(at), "status": status if status in _STATUSES else "unknown", "message": _text(message, 2400)}


def _reports(folder: Path, pattern: str, audit_root: Path) -> list[Path]:
    # Fixed caller-selected patterns only. Never select paths from TOML/prompts.
    try:
        if not folder.resolve().is_relative_to(audit_root.resolve()) or folder.is_symlink():
            return []
        return sorted(folder.glob(pattern), reverse=True)[:MAX_REPORTS]
    except OSError:
        return []


def _generic(task_id: str, audit_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    folder = audit_root / "scheduled-tasks" / task_id
    metadata = _json(folder / "metadata.json", audit_root) or {}
    result = []
    for path in _reports(folder, "*.json", audit_root):
        if path.name == "metadata.json":
            continue
        data = _json(path, audit_root)
        if not data or data.get("status") not in _STATUSES or not _timestamp(data.get("at")):
            continue
        message = _text(data.get("message"), 2400)
        if message:
            result.append(_event(data["at"], data["status"], message))
        if len(result) == MAX_LOGS:
            break
    return metadata, result


def _anime_logs(audit_root: Path) -> list[dict[str, Any]]:
    result = []
    for path in _reports(audit_root / "anime-calendar", "*.json", audit_root):
        data = _json(path, audit_root)
        if not data or not isinstance(data.get("metadata"), dict):
            continue
        metadata = data["metadata"]
        failed = metadata.get("failed")
        failed_ids = metadata.get("failed_ids")
        failures = max(len(failed) if isinstance(failed, list) else _count(failed), len(failed_ids) if isinstance(failed_ids, list) else 0)
        notifications = data.get("notifications") if isinstance(data.get("notifications"), dict) else {}
        uncertain = _count(notifications.get("uncertain"))
        limitations = data.get("limitations")
        has_limitations = bool(limitations.strip()) if isinstance(limitations, str) else bool(isinstance(limitations, list) and limitations)
        partial = failures or uncertain or has_limitations or bool(metadata.get("error")) or data.get("status") == "partial"
        status = "error" if data.get("status") == "error" else "partial" if partial else "ok"
        summary = f"{_count(metadata.get('updated'))} series actualizadas; {failures} consultas fallidas. Avisos enviados: {_count(notifications.get('sent'))}."
        if uncertain:
            summary += f" {uncertain} envíos pendientes de confirmar; no se repiten automáticamente."
        if has_limitations:
            summary += " Hay limitaciones en las fuentes; se conservan los datos sin confirmar publicaciones."
            details = limitations if isinstance(limitations, str) else " ".join(item for item in limitations[:4] if isinstance(item, str))
            summary += " " + _text(details, 800)
        if data.get("result"):
            summary += " " + _text(data["result"], 900)
        result.append(_event(data.get("trigger") or _file_time(path), status, summary))
        if len(result) == MAX_LOGS:
            break
    return result


def _outstanding(text: str) -> bool:
    """Recognise affirmative findings, not "0 pendientes"/"sin incidencias".

    Use this only on the declared result or an explicit pending section, never
    on an entire narrative containing commands, historic errors and examples.
    """
    text = text.lower()
    finding = r"(?:pendientes?|incidencias?|aplazad[oa]s?|errores?|fallos?)"
    words = r"(?:\s+[a-záéíóúüñ]+){0,4}\s+"
    text = re.sub(rf"\b(?:0|cero|sin|ning[uú]n[ao]?s?){words}{finding}\b", "", text)
    text = re.sub(rf"\bno\s+(?:hay|quedan|existen|constan|se\s+(?:detectan|observan)){words}{finding}\b", "", text)
    text = re.sub(rf"\b{finding}\s*:\s*(?:0|cero|ningun[oa]s?|ningún[oa]?|no\s+hay)\b", "", text)
    text = re.sub(rf"\b{finding}(?:\s+[a-záéíóúüñ]+){{0,3}}\s+(?:resuelt[oa]s?|solucionad[oa]s?|cerrad[oa]s?)\b", "", text)
    return bool(re.search(rf"\b{finding}\b|\bsigue[n]?\s+sin\s+responder\b|\brequiere[n]?\s+(?:intervención|planificar|migración)\b", text))


def _report_status(text: str) -> str:
    # Plain-text historical reports have no machine status. Require evidence
    # from their Result line; unrecognised prose remains unknown, never green.
    text = text[:MAX_FILE_BYTES]
    declared = re.search(r"(?im)^\s*(?:\*\*)?resultado\s*:\s*(.+)$", text)
    if not declared:
        return "unknown"
    result = declared.group(1).lower().strip()
    if re.match(r"(?:error|fallo|fallid[oa])\b", result):
        return "error"
    if re.match(r"parcial\b", result) or _outstanding(result):
        return "partial"
    pending = re.search(r"(?ims)^\s*#{1,6}\s+pendientes\s*\n(.*?)(?=^\s*#{1,6}\s|\Z)", text)
    if pending and _outstanding(pending.group(1)):
        return "partial"
    positive = re.match(r"(?:ok|correct[oa]|éxito|exito|sin\s+cambios|completad[oa])\b", result)
    completed_review = re.match(r"revisión\b[^\n]*\bcompletad[oa]\b", result)
    return "ok" if positive or completed_review else "unknown"


def _follow_up(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    at, message = _timestamp(value.get("at")), _text(value.get("message"), 1400)
    return {"at": at, "message": message} if at and message else None


def _known_logs(kind: str, audit_root: Path) -> list[dict[str, Any]]:
    if kind == "anime":
        return _anime_logs(audit_root)
    if kind == "ps5":
        paths = _reports(audit_root / "ps5-payload-updates" / "checks", "*-informe.txt", audit_root)
    elif kind == "proxmox":
        paths = _reports(audit_root, "proxmox-weekly-*/INFORME.md", audit_root)
    else:
        return []
    result = []
    for path in paths:
        raw = _read(path, audit_root)
        if raw:
            result.append(_event(_file_time(path), _report_status(raw), raw))
        if len(result) == MAX_LOGS:
            break
    return result


def _task(task_id: str, name: str, description: str, executor: str, enabled: bool, schedule: str, logs: list[dict[str, Any]], requirements: list[str], source: str, follow_up: Any = None) -> dict[str, Any]:
    logs = sorted(logs, key=lambda log: log.get("at") or "", reverse=True)[:MAX_LOGS]
    status = logs[0]["status"] if logs else "unknown"
    return {
        "id": task_id, "name": _text(name, 140) or "Tarea programada", "description": _text(description, 1400),
        "executor": executor, "enabled": enabled, "schedule": schedule, "status": "disabled" if not enabled else status,
        "status_label": "Pausada" if not enabled else _LABELS[status], "last_run": logs[0]["at"] if logs else None,
        "logs": logs, "requirements": [_text(item, 200) for item in requirements[:5] if isinstance(item, str)],
        "source": source, "history_available": bool(logs),
        "follow_up": _follow_up(follow_up),
    }


def _runtime(database: Path) -> dict[str, Any]:
    if not database.is_file() or database.is_symlink():
        return {}
    try:
        with closing(sqlite3.connect(database.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.3)) as connection:
            rows = connection.execute("SELECT key,value,updated_at FROM runtime_state WHERE key IN ('backup_status','amule_recovery')").fetchall()
        result = {}
        for key, raw, at in rows:
            if len(raw) > MAX_FILE_BYTES:
                continue
            value = json.loads(raw)
            if isinstance(value, dict):
                result[key] = (value, at)
        return result
    except (sqlite3.Error, OSError, ValueError, TypeError, RecursionError):
        return {}


def _internal(database: Path, audit_root: Path) -> list[dict[str, Any]]:
    states = _runtime(database)
    result = []
    definitions = [
        ("dashboard-backups", "Copias verificadas", "Crea copias consistentes de las bases del Dashboard y del tracker, comprueba su integridad y aplica la retención configurada. Conserva los datos y el historial.", "Cada 24 horas mientras el Dashboard está activo", "backup_status"),
        ("dashboard-amule-recovery", "Disponibilidad de aMule", "Comprueba aMule y lo abre si está ausente y la recuperación está habilitada. No termina procesos ni reinicia una instancia que ya está abierta.", "Cada 30 segundos; reintentos de apertura separados al menos 2 minutos", "amule_recovery"),
    ]
    for task_id, name, description, schedule, key in definitions:
        _, logs = _generic(task_id, audit_root)
        enabled = True
        if key in states:
            data, stored_at = states[key]
            at = data.get("checked_at") or stored_at
            if key == "backup_status":
                ok = data.get("ok") is True
                message = f"Copia verificada de {len(data['files'])} bases de datos." if ok and isinstance(data.get("files"), list) else "Última copia verificada." if ok else "No se pudo completar la copia verificada."
                logs.append(_event(at, "ok" if ok else "error", message))
            else:
                state = data.get("state")
                enabled = state != "disabled"
                messages = {"running": "aMule está disponible o su proceso sigue abierto.", "starting": "Se solicitó abrir aMule; pendiente de la siguiente comprobación.", "disabled": "La recuperación automática de aMule está desactivada.", "failed": "No se pudo comprobar o abrir aMule.", "unknown": "No se pudo confirmar el estado del proceso de aMule."}
                logs.append(_event(at, "ok" if state == "running" else "error" if state == "failed" else "unknown", messages.get(state, "Todavía no hay una comprobación del proceso.")))
        result.append(_task(task_id, name, description, "Dashboard", enabled, schedule, logs, ["Dashboard activo en el Mac"], "Estado del servicio; último registro disponible"))
    return result


def snapshot(*, automations_root: Path | None = None, audit_root: Path | None = None, database: Path | None = None) -> dict[str, Any]:
    """Called only from an authenticated GET; roots are server-side injection points.

    The endpoint must not accept these filesystem arguments from the client.
    No .env, subscription, Telegram ledger, process or network access is needed.
    """
    automations_root = automations_root if automations_root is not None else AUTOMATIONS_ROOT
    audit_root = audit_root if audit_root is not None else AUDIT_ROOT
    tasks = []
    warnings = []
    if not automations_root.is_dir() or automations_root.is_symlink():
        warnings.append("No se puede leer el catálogo de automatizaciones de Codex.")
    else:
        paths = sorted(automations_root.glob("*/automation.toml"))[:MAX_AUTOMATIONS]
        for path in paths:
            raw = _read(path, automations_root)
            if raw is None:
                warnings.append("No se pudo leer una automatización; se omite por seguridad.")
                continue
            try:
                data = tomllib.loads(raw)
            except (ValueError, RecursionError):
                warnings.append("Una automatización tiene un formato inválido.")
                continue
            task_id = data.get("id")
            if not isinstance(task_id, str) or not _IDENTIFIER.fullmatch(task_id) or path.parent.name != task_id:
                warnings.append("Se omitió una automatización con identificador inválido.")
                continue
            profile = _PROFILES.get(task_id, {})
            metadata, logs = _generic(task_id, audit_root)
            logs.extend(_known_logs(profile.get("report_type", ""), audit_root))
            description = metadata.get("description") or profile.get("description") or "Automatización gestionada por Codex. Su descripción detallada aún no está registrada en este catálogo."
            requirements = metadata.get("requirements", profile.get("requirements", ["Mac y Codex disponibles"]))
            if not isinstance(requirements, list):
                requirements = ["Mac y Codex disponibles"]
            tasks.append(_task(task_id, data.get("name"), description, "Codex", data.get("status") == "ACTIVE", _schedule(data.get("rrule")), logs, requirements, "Automatización Codex y auditorías registradas", metadata.get("follow_up")))
    tasks.extend(_internal(database if database is not None else DATABASE, audit_root))
    tasks.sort(key=lambda task: (task["executor"], task["name"].casefold()))
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "timezone": TIMEZONE,
        "summary": {"total": len(tasks), "active": sum(task["enabled"] for task in tasks), "paused": sum(not task["enabled"] for task in tasks), "attention": sum(task["enabled"] and task["status"] in {"partial", "error"} for task in tasks)},
        "tasks": tasks, "warnings": list(dict.fromkeys(warnings)),
        "limitations": ["El horario indica la programación; Codex necesita que el Mac y la aplicación estén disponibles.", "Los registros muestran resultados documentados, no prueban que una ejecución esté en curso ni que un servicio siga activo.", "Las tareas nuevas aparecen automáticamente. Su descripción e historial se completan al registrar metadatos y resultados; no se muestran instrucciones privadas."],
    }
