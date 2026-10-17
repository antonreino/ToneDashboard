#!/usr/bin/env python3
import argparse
import base64
import hmac
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from collections import deque
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR.parent / 'workers' / 'price_tracker'))
from state_db import (
    dashboard_statistics,
    dashboard_summary,
    emby_storage_snapshot,
    emby_system_snapshot,
    add_history,
    init_db,
    queue_download_request,
    recent_downloads,
    recent_history,
)
from torrent_utils import save_torrent_bytes
from download_security import validate_url, UnsafeDownload
from request_security import allowed_mutation

load_dotenv(APP_DIR / ".env")

LOG_DIR = Path.home() / "Library" / "Logs"
GAME_DOWNLOAD_DIR = Path(os.getenv("GAME_DOWNLOAD_DIR") or "/Volumes/Datos/Descargas").expanduser()
TORRENT_DROP_DIR = Path(os.getenv("TORRENT_DROP_DIR") or str(Path.home() / "Downloads")).expanduser()
TORRENT_UPLOAD_MAX_BYTES = int(os.getenv("TORRENT_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
DASHBOARD_BIND = (os.getenv("DASHBOARD_BIND") or "127.0.0.1").strip()
DASHBOARD_USER = (os.getenv("DASHBOARD_USER") or "").strip()
DASHBOARD_PASSWORD = (os.getenv("DASHBOARD_PASSWORD") or "").strip()
PRICE_BOT_DIR = Path(os.getenv("PRICE_BOT_DIR") or str(APP_DIR.parent / "workers" / "price_tracker")).expanduser()
PRICE_BOT_DB = PRICE_BOT_DIR / "data" / "prices.sqlite3"
PRICE_BOT_LOG = PRICE_BOT_DIR / "logs" / "bot.log"
PRICE_BOT_CONFIG = PRICE_BOT_DIR / "config.json"
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
_DOWNLOAD_SPEED_SAMPLES = {}
_DOWNLOAD_SPEED_LOCK = threading.Lock()
_NET_SAMPLE = None
_METRICS_CACHE = {"at": 0.0, "value": None}
LOGS = {
    "organizer_out": LOG_DIR / "emby-organizer.out.log",
    "organizer_err": LOG_DIR / "emby-organizer.err.log",
    "telegram_out": LOG_DIR / "telegram-download-bot.out.log",
    "telegram_err": LOG_DIR / "telegram-download-bot.err.log",
    "ps5_out": PRICE_BOT_LOG,
}
SERVICES = {
    "organizer": "com.tone.emby-organizer",
    "telegram": "com.tone.telegram-download-bot",
    "viewer": "com.tone.emby-log-viewer",
    "alerts": "com.tone.emby-log-alerts",
}

LOG_TS_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2})(?:,\d+)?(?P<rest>.*)$")

from web_assets import dashboard_html, VERSION
HTML = dashboard_html()




def format_log_timestamps(text: str) -> str:
    result = []
    last_stamp = None
    for line in text.splitlines():
        match = LOG_TS_RE.match(line)
        if match:
            year, month, day = match.group("date").split("-")
            last_stamp = f"{day}/{month}/{year} {match.group('time')}"
            result.append(f"{last_stamp}{match.group('rest')}")
        elif last_stamp and line.strip():
            result.append(f"{last_stamp} | {line}")
        else:
            result.append(line)
    return "\n".join(result)


def tail(path: Path, lines: int) -> str:
    if not path.exists():
        return "(sin archivo de log)"
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            raw = "".join(deque(handle, maxlen=lines)).strip()
        return format_log_timestamps(raw)
    except Exception as exc:
        return f"(error leyendo {path.name}: {exc})"


def service_state(label: str) -> dict:
    if sys.platform != "darwin":
        return {"running": False, "state": "no disponible"}
    try:
        proc = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True, text=True, timeout=3,
        )
        if proc.returncode != 0:
            return {"running": False, "state": "no cargado"}
        output = proc.stdout
        running = any(line.strip() in {"state = running", "job state = running"} for line in output.splitlines())
        if running:
            return {"running": True, "state": "running"}
        state = "cargado"
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("state = ") or stripped.startswith("job state = "):
                state = stripped.split("=", 1)[1].strip()
                break
        return {"running": False, "state": state}
    except Exception as exc:
        return {"running": False, "state": f"error: {exc}"}


def download_progress(rows: list[dict]) -> list[dict]:
    result = []
    now = time.monotonic()
    active_ids = set()
    for row in rows:
        item = dict(row)
        total = item.get("size_bytes")
        target = Path(item.get("target") or "")
        try:
            downloaded = target.stat().st_size if target.is_file() else 0
        except OSError:
            downloaded = 0

        status = str(item.get("status") or "").lower()
        if status == "completed" and total:
            downloaded = max(downloaded, int(total))

        speed_bps = None
        job_id = item.get("id")
        if status == "active" and job_id is not None:
            active_ids.add(job_id)
            with _DOWNLOAD_SPEED_LOCK:
                previous = _DOWNLOAD_SPEED_SAMPLES.get(job_id)
                if previous is not None:
                    previous_bytes, previous_at = previous
                    elapsed = now - previous_at
                    delta = downloaded - previous_bytes
                    if elapsed >= 0.5 and delta >= 0:
                        speed_bps = delta / elapsed
                _DOWNLOAD_SPEED_SAMPLES[job_id] = (downloaded, now)
        elif job_id is not None:
            with _DOWNLOAD_SPEED_LOCK:
                _DOWNLOAD_SPEED_SAMPLES.pop(job_id, None)

        item["downloaded_bytes"] = downloaded
        item["speed_bps"] = round(speed_bps, 1) if speed_bps is not None else None
        item["progress_percent"] = round(min(100.0, downloaded * 100.0 / int(total)), 1) if total and int(total) > 0 else None
        item["eta_seconds"] = (
            round(max(0, int(total) - downloaded) / speed_bps)
            if total and speed_bps is not None and speed_bps > 1 and downloaded < int(total)
            else None
        )
        result.append(item)

    with _DOWNLOAD_SPEED_LOCK:
        for job_id in list(_DOWNLOAD_SPEED_SAMPLES):
            if job_id not in active_ids:
                _DOWNLOAD_SPEED_SAMPLES.pop(job_id, None)
    return result




def _plain_telegram_html(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value or "")).strip()

def _epoch_iso(value) -> str | None:
    try:
        stamp = float(value)
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds")

def _tracked_products_module():
    from ps5bot import products
    return products


def tracked_products():
    return _tracked_products_module().list_tracking(PRICE_BOT_DB)


def inactive_tracking():
    try:
        return _tracked_products_module().list_tracking(PRICE_BOT_DB, enabled=False)
    except (OSError, ImportError):
        return []


def _price_bot_policy() -> tuple[set[str] | None, float | None]:
    try:
        cfg = json.loads(PRICE_BOT_CONFIG.read_text(encoding="utf-8"))
        enabled = {
            str(source.get("name"))
            for source in _tracked_products_module().configured_sources(PRICE_BOT_DB, cfg.get("sources", []))
        }
        module = _tracked_products_module()
        enabled.update(s["name"] for s in module.product_sources(module.list_products(PRICE_BOT_DB), cfg.get("sources", [])))
        stale = float(cfg.get("stale_after_seconds", 0) or 0)
        return enabled, stale if stale > 0 else None
    except Exception:
        return None, None


def _parse_bytes(value: str) -> int | None:
    match = re.match(r"\s*([0-9.]+)\s*([KMGT]?)(?:B)?\s*$", str(value), re.I)
    if not match:
        return None
    factor = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[match.group(2).upper()]
    return int(float(match.group(1)) * factor)


def _network_totals() -> tuple[int, int]:
    proc = subprocess.run(
        ["/usr/sbin/netstat", "-ibn"],
        capture_output=True, text=True, timeout=2,
    )
    if proc.returncode != 0:
        return 0, 0
    lines = proc.stdout.splitlines()
    if not lines:
        return 0, 0
    header = re.split(r"\s+", lines[0].strip())
    try:
        name_i, ibytes_i, obytes_i = header.index("Name"), header.index("Ibytes"), header.index("Obytes")
    except ValueError:
        return 0, 0
    per_iface = {}
    for line in lines[1:]:
        cols = re.split(r"\s+", line.strip())
        if len(cols) <= max(name_i, ibytes_i, obytes_i):
            continue
        name = cols[name_i]
        if name == "lo0":
            continue
        try:
            ibytes, obytes = int(cols[ibytes_i]), int(cols[obytes_i])
        except ValueError:
            continue
        previous = per_iface.get(name, (0, 0))
        per_iface[name] = (max(previous[0], ibytes), max(previous[1], obytes))
    return sum(v[0] for v in per_iface.values()), sum(v[1] for v in per_iface.values())


def _apple_silicon_metrics() -> dict:
    """GPU y temperaturas en Apple Silicon.

    Prioriza macmon porque expone GPU y temperaturas reales sin sudo.
    Si no está instalado, cae a powermetrics para GPU + presión térmica.
    """
    macmon_candidates = [
        Path("/opt/homebrew/bin/macmon"),
        Path("/usr/local/bin/macmon"),
    ]
    macmon = next((path for path in macmon_candidates if path.exists()), None)

    if macmon is not None:
        try:
            proc = subprocess.run(
                [str(macmon), "pipe", "-s", "1", "-i", "250"],
                capture_output=True, text=True, timeout=4,
            )
            lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            if proc.returncode == 0 and lines:
                data = json.loads(lines[-1])
                temp = data.get("temp") or {}
                cpu_temp = temp.get("cpu_temp_avg")
                gpu_temp = temp.get("gpu_temp_avg")

                gpu_active = data.get("gpu_active_ratio")
                if gpu_active is None:
                    gpu_usage = data.get("gpu_usage")
                    if isinstance(gpu_usage, list) and len(gpu_usage) >= 2:
                        gpu_active = gpu_usage[1]

                return {
                    "gpu_percent": float(gpu_active) * 100 if gpu_active is not None else None,
                    "cpu_temperature_c": float(cpu_temp) if cpu_temp is not None else None,
                    "gpu_temperature_c": float(gpu_temp) if gpu_temp is not None else None,
                    "thermal_state": None,
                    "note": "macmon",
                }
        except Exception:
            pass

    gpu_percent = None
    thermal_state = None
    note = "macmon no instalado"

    try:
        gpu_proc = subprocess.run(
            ["/usr/bin/sudo", "-n", "/usr/bin/powermetrics",
             "--samplers", "gpu_power", "-n", "1", "-i", "250"],
            capture_output=True, text=True, timeout=4,
        )
        if gpu_proc.returncode == 0:
            match = re.search(
                r"GPU HW active residency:\s*([0-9.]+)%",
                gpu_proc.stdout,
                re.I,
            )
            if match:
                gpu_percent = float(match.group(1))
            note = "powermetrics"
    except Exception:
        pass

    try:
        thermal_proc = subprocess.run(
            ["/usr/bin/sudo", "-n", "/usr/bin/powermetrics",
             "--samplers", "thermal", "-n", "1", "-i", "250"],
            capture_output=True, text=True, timeout=4,
        )
        if thermal_proc.returncode == 0:
            match = re.search(
                r"Current pressure level:\s*([A-Za-z]+)",
                thermal_proc.stdout,
                re.I,
            )
            if match:
                thermal_state = match.group(1)
    except Exception:
        pass

    return {
        "gpu_percent": gpu_percent,
        "cpu_temperature_c": None,
        "gpu_temperature_c": None,
        "thermal_state": thermal_state,
        "note": note,
    }

def mac_system_snapshot() -> dict:
    global _NET_SAMPLE, _METRICS_CACHE

    now = time.monotonic()
    cpu_percent = None
    ram_total = None
    ram_used = None

    try:
        proc = subprocess.run(
            ["/usr/bin/top", "-l", "1", "-n", "0"],
            capture_output=True, text=True, timeout=3,
        )
        cpu = re.search(r"CPU usage:\s*([0-9.]+)% user,\s*([0-9.]+)% sys", proc.stdout)
        if cpu:
            cpu_percent = float(cpu.group(1)) + float(cpu.group(2))
        phys = re.search(r"PhysMem:\s*([^ ]+) used.*?,\s*([^ ]+) unused", proc.stdout)
        if phys:
            ram_used = _parse_bytes(phys.group(1))
            ram_free = _parse_bytes(phys.group(2))
            if ram_used is not None and ram_free is not None:
                ram_total = ram_used + ram_free
    except Exception:
        pass

    memory_free_percent = None
    swap_used = None
    try:
        mp = subprocess.run(
            ["/usr/bin/memory_pressure", "-Q"],
            capture_output=True, text=True, timeout=2,
        )
        m = re.search(r"free percentage:\s*([0-9.]+)%", mp.stdout, re.I)
        if m:
            memory_free_percent = float(m.group(1))
    except Exception:
        pass

    try:
        sw = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "vm.swapusage"],
            capture_output=True, text=True, timeout=2,
        )
        m = re.search(r"used\s*=\s*([0-9.]+)([MGT])", sw.stdout, re.I)
        if m:
            factor = {"M": 1024**2, "G": 1024**3, "T": 1024**4}[m.group(2).upper()]
            swap_used = int(float(m.group(1)) * factor)
    except Exception:
        pass

    rx, tx = _network_totals()
    rx_bps = tx_bps = 0.0
    if _NET_SAMPLE is not None:
        old_at, old_rx, old_tx = _NET_SAMPLE
        elapsed = now - old_at
        if elapsed > 0:
            rx_bps = max(0.0, (rx - old_rx) / elapsed)
            tx_bps = max(0.0, (tx - old_tx) / elapsed)
    _NET_SAMPLE = (now, rx, tx)

    if now - float(_METRICS_CACHE.get("at") or 0) >= 10 or _METRICS_CACHE.get("value") is None:
        _METRICS_CACHE = {"at": now, "value": _apple_silicon_metrics()}
    apple = _METRICS_CACHE["value"]

    return {
        "cpu_percent": round(cpu_percent, 1) if cpu_percent is not None else None,
        "gpu_percent": round(apple.get("gpu_percent"), 1) if apple.get("gpu_percent") is not None else None,
        "temperature_c": (
            round(max(
                x for x in (
                    apple.get("cpu_temperature_c"),
                    apple.get("gpu_temperature_c"),
                ) if x is not None
            ), 1)
            if any(x is not None for x in (
                apple.get("cpu_temperature_c"),
                apple.get("gpu_temperature_c"),
            ))
            else None
        ),
        "cpu_temperature_c": round(apple.get("cpu_temperature_c"), 1) if apple.get("cpu_temperature_c") is not None else None,
        "gpu_temperature_c": round(apple.get("gpu_temperature_c"), 1) if apple.get("gpu_temperature_c") is not None else None,
        "thermal_state": apple.get("thermal_state"),
        "ram_total": ram_total,
        "ram_used": ram_used,
        "ram_percent": round(ram_used * 100 / ram_total, 1) if ram_used is not None and ram_total else None,
        "memory_free_percent": round(memory_free_percent, 1) if memory_free_percent is not None else None,
        "swap_used": swap_used,
        "net_rx_bps": round(rx_bps, 1),
        "net_tx_bps": round(tx_bps, 1),
        "powermetrics_note": apple.get("note"),
    }


def price_bot_snapshot(log_lines: int = 300) -> dict:
    log_text = tail(PRICE_BOT_LOG, log_lines)
    if not PRICE_BOT_DB.is_file():
        return {"available": False, "error": f"No se encuentra la base de datos: {PRICE_BOT_DB}", "active_offers": [], "history": [], "events": [], "log": log_text}
    conn = None
    try:
        conn = sqlite3.connect(PRICE_BOT_DB, timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute("SELECT o.source,o.payload,o.seen FROM offers o JOIN sources s ON s.name=o.source WHERE o.active=1 AND s.ok=1 ORDER BY o.price ASC").fetchall()
        enabled_sources, stale_after = _price_bot_policy()
        cutoff = time.time() - stale_after if stale_after else None
        active = []
        for row in rows:
            if enabled_sources is not None and row["source"] not in enabled_sources:
                continue
            if cutoff is not None and float(row["seen"] or 0) < cutoff:
                continue
            try:
                payload = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            model = str(payload.get("model") or "")
            payload["family"] = "ean" if model.startswith("ean:") else ("switch2" if model.startswith("switch2") else "ps5")
            if model.startswith("ean:"):
                payload["ean"] = model[4:]
            payload["seen_iso"] = _epoch_iso(row["seen"])
            active.append(payload)
        active.sort(key=lambda o: (o.get('price') if isinstance(o.get('price'), int) else float('inf'), str(o.get('source', '')), str(o.get('url', ''))))
        products = tracked_products()
        for product in products:
            match = next((o for o in active if product.get('family', 'ean') == 'ean' and o.get('ean') == product['ean']), None)
            if match:
                product['name'] = match.get('title') or product['name']
        history = [{"body": _plain_telegram_html(r["body"]), "created_iso": _epoch_iso(r["created"])} for r in conn.execute("SELECT body,created FROM published_notifications ORDER BY created DESC LIMIT 120")]
        events = [{"name": r["name"], "level": r["level"], "detail": r["detail"], "created_iso": _epoch_iso(r["created"])} for r in conn.execute("SELECT name,level,detail,created FROM source_events ORDER BY id DESC LIMIT 100")]
        return {"available": True, "products": products, "inactive_products": inactive_tracking(), "active_offers": active, "history": history, "events": events, "log": log_text}
    except sqlite3.Error as exc:
        return {"available": False, "error": f"No se pudo leer SQLite del bot de precios: {exc}", "active_offers": [], "history": [], "events": [], "log": log_text}
    finally:
        if conn is not None:
            conn.close()

def disk_info(path: Path) -> dict:
    probe = path if path.exists() else path.parent
    try:
        usage = shutil.disk_usage(probe)
        return {"path": str(path), "exists": path.exists(), "total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        return {"path": str(path), "exists": False, "total": 0, "used": 0, "free": 0}


PWA_MANIFEST = json.dumps({
    "name": "Tone Dashboard",
    "short_name": "Tone Dashboard",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#07111f",
    "theme_color": "#07111f",
    "description": "Panel privado ToneDashboard",
    "icons": [
        {"src": "/app-icon.png", "sizes": "180x180", "type": "image/png"},
        {"src": "/app-icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
    ]
}, ensure_ascii=False)

class Handler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        if not DASHBOARD_USER and not DASHBOARD_PASSWORD:
            return True
        raw = self.headers.get("Authorization", "")
        if not raw.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(raw[6:], validate=True).decode("utf-8")
            user, password = decoded.split(":", 1)
        except Exception:
            return False
        return hmac.compare_digest(user.encode(), DASHBOARD_USER.encode()) and hmac.compare_digest(password.encode(), DASHBOARD_PASSWORD.encode())

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        body = b"Authentication required"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="ToneDashboard", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def send_bytes(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._require_auth():
            return
        from orbit_dashboard_proxy import serve as orbit_serve
        if orbit_serve(self):
            return
        parsed = urlparse(self.path)
        if parsed.path == '/api/amule':
            from amule_dashboard import handle
            result,code=handle('GET',parsed.path)
            self.send_bytes(json.dumps(result,ensure_ascii=False).encode(), 'application/json; charset=utf-8',code)
            return
        if parsed.path == '/api/orbit/status':
            from orbit_dashboard_control import get_status
            self.send_bytes(json.dumps(get_status(),ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')
            return
        if parsed.path == '/api/version':
            self.send_bytes(json.dumps({'name': 'Tone Dashboard', 'version': VERSION}).encode(), 'application/json')
            return
        if parsed.path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/manifest.webmanifest":
            self.send_bytes(PWA_MANIFEST.encode("utf-8"), "application/manifest+json; charset=utf-8")
            return
        if parsed.path == "/app-icon.png":
            icon_path = APP_DIR / "static" / "app-icon.png"
            if icon_path.is_file():
                self.send_bytes(icon_path.read_bytes(), "image/png")
            else:
                self.send_error(404)
            return
        if parsed.path == "/health":
            self.send_bytes(b"ok", "text/plain")
            return
        if parsed.path == "/api/logs":
            query = parse_qs(parsed.query)
            try:
                lines = int(query.get("lines", ["300"])[0])
            except ValueError:
                lines = 300
            lines = max(10, min(lines, 2000))
            body = json.dumps({"logs": {name: tail(path, lines) for name, path in LOGS.items()}}, ensure_ascii=False).encode("utf-8")
            self.send_bytes(body, "application/json; charset=utf-8")
            return
        if parsed.path == "/api/deals":
            query = parse_qs(parsed.query)
            try:
                lines = int(query.get("lines", ["300"])[0])
            except ValueError:
                lines = 300
            lines = max(10, min(lines, 2000))
            data = price_bot_snapshot(lines)
            self.send_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if parsed.path == '/api/orbit/device':
            from orbit_devices import token, valid
            remembered = bool(DASHBOARD_USER and DASHBOARD_PASSWORD and valid(token(self.headers)))
            self.send_bytes(json.dumps({'remembered': remembered}).encode(), 'application/json; charset=utf-8')
            return
        if parsed.path == "/api/dashboard":
            data = {
                "services": {name: service_state(label) for name, label in SERVICES.items()},
                "summary": dashboard_summary(),
                "statistics": dashboard_statistics(),
                "downloads": download_progress(recent_downloads(20)),
                "history": recent_history(40),
                "disk": disk_info(GAME_DOWNLOAD_DIR),
                "internal_disk": disk_info(Path("/")),
                "emby_disk": emby_storage_snapshot(),
                "emby_system": emby_system_snapshot(),
                "system": mac_system_snapshot(),
            }
            self.send_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self):
        if not self._require_auth():
            return
        if not allowed_mutation(self.headers):
            self.send_bytes(b'{"error":"Origen no autorizado"}', 'application/json', 403)
            return
        from orbit_dashboard_proxy import serve as orbit_serve
        if orbit_serve(self):
            return
        parsed = urlparse(self.path)
        if parsed.path in ('/api/amule/search','/api/amule/download'):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 2048: raise ValueError()
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict): raise ValueError()
            except (ValueError,UnicodeError):
                self.send_bytes(b'{"error":"Solicitud aMule no valida"}', 'application/json',400)
                return
            from amule_dashboard import handle
            result,code=handle('POST',parsed.path,body)
            self.send_bytes(json.dumps(result,ensure_ascii=False).encode(), 'application/json; charset=utf-8',code)
            return
        if parsed.path in ('/api/deals/products', '/api/deals/products/remove', '/api/deals/products/restore'):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024:
                    raise ValueError('Solicitud vacía o demasiado grande')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Solicitud no válida')
                module = _tracked_products_module()
                if parsed.path.endswith('/remove'):
                    removed = module.remove_tracking(PRICE_BOT_DB, body['id']) if 'id' in body else module.remove_product(PRICE_BOT_DB, body.get('ean'))
                    result = {'ok': True, 'removed': removed}
                elif parsed.path.endswith('/restore'):
                    result = {'ok': True, 'restored': module.restore_tracking(PRICE_BOT_DB, body.get('id'))}
                else:
                    result = {'ok': True, 'product': module.add_product(PRICE_BOT_DB, body.get('ean'))}
                self.send_bytes(json.dumps(result).encode(), 'application/json', 200)
            except (ValueError, UnicodeError) as exc:
                self.send_bytes(json.dumps({'error': str(exc)}).encode(), 'application/json', 400)
            except (OSError, sqlite3.Error):
                self.send_bytes(b'{"error":"No se pudo guardar el producto"}', 'application/json', 503)
            return
        if parsed.path in ('/api/orbit/remember', '/api/orbit/forget'):
            from orbit_devices import action
            if not (DASHBOARD_USER and DASHBOARD_PASSWORD):
                self.send_bytes(b'{"error":"Configura las credenciales del dashboard"}', 'application/json', 503)
                return
            result, status, cookie = action(self.headers, self.client_address, parsed.path.endswith('/forget'))
            body = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            if cookie:
                self.send_header('Set-Cookie', cookie)
                self.send_header('Set-Cookie', 'orbitZero=; Max-Age=0; Path=/orbit-bridge/zero/; HttpOnly; Secure; SameSite=Strict')
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == '/api/orbit/pair-code':
            from orbit_pairing import reveal_code
            if not (DASHBOARD_USER and DASHBOARD_PASSWORD):
                self.send_bytes(b'{"error":"Configura las credenciales del dashboard"}', 'application/json', 503)
                return
            result, code = reveal_code(self.headers, self.client_address)
            self.send_bytes(json.dumps(result, ensure_ascii=False).encode(), 'application/json; charset=utf-8', code)
            return
        if parsed.path == '/api/orbit/start':
            from orbit_dashboard_control import start_app
            result,code=start_app(self.headers, self.client_address)
            self.send_bytes(json.dumps(result,ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8',code)
            return

        if parsed.path == "/api/torrent":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > TORRENT_UPLOAD_MAX_BYTES:
                self.send_bytes(
                    json.dumps({"error": f"Torrent vacío o demasiado grande; máximo {TORRENT_UPLOAD_MAX_BYTES // (1024*1024)} MB"}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 413 if length > TORRENT_UPLOAD_MAX_BYTES else 400,
                )
                return
            filename = unquote(self.headers.get("X-Torrent-Filename", "")).strip()
            if not filename.lower().endswith(".torrent"):
                self.send_bytes(
                    json.dumps({"error": "Selecciona un archivo con extensión .torrent"}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 400,
                )
                return
            try:
                data = self.rfile.read(length)
                target = save_torrent_bytes(data, filename, TORRENT_DROP_DIR, prefix="dashboard")
                add_history(
                    "torrent", "success", title=target.name, source_path="dashboard",
                    destination=str(target.parent), details="Torrent añadido desde el Dashboard", size_bytes=len(data),
                )
            except ValueError as exc:
                self.send_bytes(
                    json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 400,
                )
                return
            except OSError as exc:
                self.send_bytes(
                    json.dumps({"error": f"No se pudo guardar el torrent: {exc}"}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 500,
                )
                return
            self.send_bytes(
                json.dumps({"ok": True, "name": target.name}, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8", 201,
            )
            return

        if parsed.path == "/api/download":
            if not TELEGRAM_CHAT_ID:
                self.send_bytes(
                    json.dumps({"error": "TELEGRAM_CHAT_ID no configurado"}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 503,
                )
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 65536:
                self.send_bytes(
                    json.dumps({"error": "Petición inválida"}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 400,
                )
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                url = str(payload.get("url") or "").strip()
            except Exception:
                url = ""
            parsed_url = urlparse(url)
            if len(url) > 8192 or parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                self.send_bytes(
                    json.dumps({"error": "URL no válida"}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", 400,
                )
                return
            try:
                validate_url(url)
            except UnsafeDownload as exc:
                self.send_bytes(json.dumps({'error': str(exc)}).encode(), 'application/json', 400)
                return
            request_id = queue_download_request(chat_id=TELEGRAM_CHAT_ID, url=url)
            self.send_bytes(
                json.dumps({"ok": True, "request_id": request_id}, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8", 202,
            )
            return

        self.send_error(404)

    # El proxy permite los métodos que usa Orbit. Fuera de su namespace no hay cambios.
    def do_HEAD(self):
        from orbit_dashboard_proxy import serve as orbit_serve
        if not orbit_serve(self): self.send_error(405)

    def do_DELETE(self):
        from orbit_dashboard_proxy import serve as orbit_serve
        if not orbit_serve(self): self.send_error(405)

    def do_PUT(self):
        from orbit_dashboard_proxy import serve as orbit_serve
        if not orbit_serve(self): self.send_error(405)

    def do_PATCH(self):
        from orbit_dashboard_proxy import serve as orbit_serve
        if not orbit_serve(self): self.send_error(405)

    def do_OPTIONS(self):
        from orbit_dashboard_proxy import serve as orbit_serve
        if not orbit_serve(self): self.send_error(405)

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DASHBOARD_BIND)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    host = str(args.host or "127.0.0.1").strip()
    if host not in ("127.0.0.1", "localhost", "::1") and (not DASHBOARD_USER or not DASHBOARD_PASSWORD):
        raise SystemExit("Para exponer el Dashboard fuera de localhost configura DASHBOARD_USER y DASHBOARD_PASSWORD en .env")
    init_db()
    TORRENT_DROP_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, args.port), Handler)
    shown_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(f"Dashboard: http://{shown_host}:{args.port} (bind {host})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
