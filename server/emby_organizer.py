#!/usr/bin/env python3
import argparse
import getpass
import fcntl
import uuid
import json
import logging
import os
import re
import shutil
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

import task_store

from state_db import (
    set_runtime_state, utc_now, add_history, init_db, mark_emby_storage_error, mark_emby_system_error,
    save_emby_storage, save_emby_system,
)

try:
    import paramiko
except ImportError:
    paramiko = None


# =========================
# CONFIGURACIÓN
# =========================
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

INBOX_DIR = Path(os.environ.get("INBOX_DIR", str(Path.home() / "Documents" / "Torrent"))).expanduser()
STABLE_SECONDS = 180
SCAN_INTERVAL_SECONDS = 30
EMBY_STORAGE_REFRESH_SECONDS = int(os.environ.get("EMBY_STORAGE_REFRESH_SECONDS", "300"))
EMBY_SYSTEM_REFRESH_SECONDS = int(os.environ.get("EMBY_SYSTEM_REFRESH_SECONDS", "60"))
LOG_FILE = Path.home() / ".local" / "share" / "emby_organizer" / "organizer.log"
STATE_DIR = Path.home() / ".local" / "share" / "emby_organizer"
QUARANTINE_LOCAL_DIR = INBOX_DIR / "NoClasificado"

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
TMDB_CACHE_FILE = STATE_DIR / "tmdb_cache.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
EMBY_SFTP_KNOWN_HOSTS = Path(
    os.environ.get("EMBY_SFTP_KNOWN_HOSTS", str(Path.home() / ".ssh" / "known_hosts"))
).expanduser()


def redact_secrets(text: str) -> str:
    value = str(text)
    secrets = (
        TELEGRAM_BOT_TOKEN or "",
        TMDB_API_KEY or "",
        os.environ.get("EMBY_API_KEY", ""),
        os.environ.get("EMBY_SFTP_PASSWORD", ""),
    )
    for secret in secrets:
        if secret and len(secret) >= 6:
            value = value.replace(secret, "[REDACTADO]")
    return value

def error_summary(exc: Exception) -> str:
    detail = str(exc).strip()
    return redact_secrets(f"{type(exc).__name__}: {detail}" if detail else f"{type(exc).__name__}: conexión cerrada o sin detalle")


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts"}
IGNORE_EXTENSIONS = {".part", ".tmp", ".crdownload", ".!qB", ".aria2"}
IGNORE_FILENAMES = {"canal telegram oficial.url"}
IGNORE_DIR_NAMES = {"NoClasificado", ".staging", ".git"}

LIBRARIES = {
    "anime": os.environ.get("EMBY_SFTP_ANIME_URL", ""),
    "series": os.environ.get("EMBY_SFTP_SERIES_URL", ""),
    "movies": os.environ.get("EMBY_SFTP_MOVIES_URL", ""),
}

ANIME_HINTS = {
    "anime",
    "ova",
    "ona",
    "fansub",
    "sub esp",
    "subspa",
    "japanese",
    "japones",
    "japonés",
    "erai-raws",
    "subsplease",
    "horriblesubs",
    "multi-sub",
    "multisub",
}

ANIME_RELEASE_GROUPS = {
    "erai-raws",
    "subsplease",
    "horriblesubs",
    "judas",
    "ember",
    "anime time",
    "nyaa",
}

SERIES_EPISODE_PATTERNS = [
    re.compile(r"(?i)(?<!\w)S(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?!\w)"),
    re.compile(r"(?i)(?<!\d)(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?!\d)"),
    re.compile(r"(?i)\bSeason[ ._-]?(?P<season>\d{1,2})[ ._-]*Episode[ ._-]?(?P<episode>\d{1,3})\b"),
]

SPANISH_EPISODE_PATTERNS = [
    re.compile(r"(?i)\[Cap[ ._-]?(?P<episode>\d{1,4})\]"),
    re.compile(r"(?i)\bCap[íi]?tulo[ ._-]?(?P<episode>\d{1,4})\b"),
    re.compile(r"(?i)\bCap[ ._-]?(?P<episode>\d{1,4})\b"),
]

QUALITY_TOKENS = re.compile(
    r"(?i)\b(2160p|1080p|720p|480p|x264|x265|h\.264|h\.265|hevc|bluray|bdrip|webrip|web-dl|web dl|hdrip|dvdrip|aac|dts|10bit|8bit|multi|multi-audio|dual audio|subbed|proper|repack|hdtv|microhd|cr|avc)\b"
)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
HASH_BLOCK_PATTERN = re.compile(r"\[[A-F0-9]{6,10}\]", re.IGNORECASE)
BRACKET_BLOCK_PATTERN = re.compile(r"\[[^\]]+\]")
PAREN_BLOCK_PATTERN = re.compile(r"\([^\)]+\)")


@dataclass
class SftpTarget:
    username: str
    host: str
    port: int
    path: str


@dataclass
class MediaInfo:
    source_path: Path
    title: str
    category: str  # anime | series | movies | unknown
    season: Optional[int] = None
    episode: Optional[int] = None
    year: Optional[int] = None
    extension: str = ""
    episode_suffix: str = ""


class OrganizerError(Exception):
    pass


class SftpUploader:
    def __init__(self, targets: dict[str, str]):
        if paramiko is None:
            raise OrganizerError(
                "Falta la librería 'paramiko'. Instálala con: python3 -m pip install paramiko"
            )
        self.targets = {name: self._parse_sftp_url(url) for name, url in targets.items()}
        self._ssh = None
        self._transport = None
        self._sftp = None
        self._active_key = None
        self._password = os.environ.get("EMBY_SFTP_PASSWORD") or None

    @staticmethod
    def _parse_sftp_url(url: str) -> SftpTarget:
        parsed = urlparse(url)
        if parsed.scheme != "sftp":
            raise OrganizerError(f"URL SFTP inválida: {url}")
        if not parsed.hostname or not parsed.username or not parsed.path:
            raise OrganizerError(f"URL SFTP incompleta: {url}")
        return SftpTarget(
            username=parsed.username,
            host=parsed.hostname,
            port=parsed.port or 22,
            path=parsed.path,
        )

    @staticmethod
    def safe_component(value: str) -> str:
        value = value.strip()
        value = value.replace("/", "-").replace("\\", "-")
        value = re.sub(r"\s+", " ", value)
        return value.strip(" .-_") or "Unknown"

    def _connect(self, category: str):
        target = self.targets[category]
        key = (target.username, target.host, target.port)
        if (
            self._sftp
            and self._transport
            and self._transport.is_active()
            and self._active_key == key
            and not self._sftp.get_channel().closed
        ):
            return self._sftp, target

        self.close()

        if not EMBY_SFTP_KNOWN_HOSTS.is_file():
            raise OrganizerError(
                f"No existe el archivo known_hosts: {EMBY_SFTP_KNOWN_HOSTS}. "
                "Conéctate una vez por SSH al servidor y verifica su huella antes de usar el Organizer."
            )

        client = paramiko.SSHClient()
        try:
            client.load_host_keys(str(EMBY_SFTP_KNOWN_HOSTS))
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.connect(
                hostname=target.host,
                port=target.port,
                username=target.username,
                password=self._password,
                look_for_keys=True,
                allow_agent=True,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )
            transport = client.get_transport()
            if transport is None or not transport.is_active():
                raise OrganizerError("La conexión SSH no quedó activa")

            transport.set_keepalive(30)
            self._ssh = client
            self._transport = transport
            self._sftp = client.open_sftp()
            self._sftp.get_channel().settimeout(15)
            self._active_key = key
            return self._sftp, target
        except paramiko.BadHostKeyException as exc:
            client.close()
            raise OrganizerError(
                f"La clave SSH del servidor {target.host}:{target.port} ha cambiado. "
                "No se establece la conexión por seguridad."
            ) from exc
        except paramiko.SSHException as exc:
            client.close()
            message = error_summary(exc)
            if "not found in known_hosts" in message.lower() or "known_hosts" in message.lower():
                raise OrganizerError(
                    f"El servidor {target.host}:{target.port} no está validado en "
                    f"{EMBY_SFTP_KNOWN_HOSTS}. Verifica su huella y añádelo a known_hosts."
                ) from exc
            raise OrganizerError(f"No se pudo abrir la conexión SSH/SFTP: {message}") from exc
        except Exception as exc:
            client.close()
            raise OrganizerError(
                f"No se pudo abrir la conexión SSH/SFTP: {error_summary(exc)}"
            ) from exc

    def close(self):
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
        elif self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
        self._sftp = None
        self._transport = None
        self._ssh = None
        self._active_key = None

    def _with_reconnect(self, category: str, operation):
        """Recupera canales cerrados con un único reintento y mantiene el pinning SSH."""
        for attempt in range(2):
            try:
                sftp, _ = self._connect(category)
                return operation(sftp)
            except (OSError, EOFError, paramiko.SSHException) as exc:
                self.close()
                if attempt:
                    raise
                logging.warning("Conexión SSH/SFTP interrumpida (%s). Reconectando una vez...", error_summary(exc))

    def storage_info(self, category: str = "movies") -> dict:
        return self._with_reconnect(category, lambda sftp: self._storage_info_once(sftp, self.targets[category]))

    def _storage_info_once(self, sftp, target) -> dict:
        """Devuelve espacio total/usado/disponible del filesystem remoto por SFTP."""
        try:
            stat = sftp.statvfs(target.path)
            block_size = int(stat.f_frsize or stat.f_bsize or 4096)
            total = int(stat.f_blocks) * block_size
            free_all = int(stat.f_bfree) * block_size
            free_available = int(stat.f_bavail) * block_size
            used = max(0, total - free_all)
            return {
                "path": target.path,
                "total": total,
                "used": used,
                "free": free_available,
            }
        except Exception:
            if self._transport is None:
                raise
            channel = self._transport.open_session(timeout=8)
            try:
                command_path = target.path.replace("'", "'\"'\"'")
                channel.settimeout(10)
                channel.exec_command(f"df -Pk '{command_path}'")
                stdout = channel.makefile("r", -1).read()
                stderr = channel.makefile_stderr("r", -1).read()
                status = channel.recv_exit_status()
                if status != 0:
                    raise OrganizerError(stderr.strip() or f"df terminó con código {status}")

                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                lines = [line for line in stdout.splitlines() if line.strip()]
                if len(lines) < 2:
                    raise OrganizerError("Respuesta de df incompleta")

                parts = lines[-1].split()
                if len(parts) < 6:
                    raise OrganizerError("Formato de df no reconocido")

                return {
                    "path": target.path,
                    "total": int(parts[1]) * 1024,
                    "used": int(parts[2]) * 1024,
                    "free": int(parts[3]) * 1024,
                }
            finally:
                channel.close()

    def system_info(self, category: str = "movies") -> dict:
        return self._with_reconnect(category, lambda _: self._system_info_once())

    def _system_info_once(self) -> dict:
        """Obtiene CPU, RAM y carga del host Linux remoto usando la conexión SSH ya abierta."""
        if self._transport is None:
            raise OrganizerError("No hay transporte SSH disponible")

        channel = self._transport.open_session(timeout=8)
        try:
            channel.settimeout(10)
            channel.exec_command("cat /proc/stat | head -1; sleep 0.25; cat /proc/stat | head -1; cat /proc/meminfo; cat /proc/loadavg")
            stdout = channel.makefile("r", -1).read()
            stderr = channel.makefile_stderr("r", -1).read()
            status = channel.recv_exit_status()
            if status != 0:
                raise OrganizerError(stderr.strip() or f"lectura de métricas terminó con código {status}")
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")

            lines = [line.strip() for line in stdout.splitlines() if line.strip()]
            cpu_lines = [line for line in lines if line.startswith("cpu ")]
            if len(cpu_lines) < 2:
                raise OrganizerError("No se pudieron leer dos muestras de /proc/stat")

            def cpu_values(line: str):
                values = [int(v) for v in line.split()[1:]]
                total = sum(values)
                idle = (values[3] if len(values) > 3 else 0) + (values[4] if len(values) > 4 else 0)
                return total, idle

            total1, idle1 = cpu_values(cpu_lines[0])
            total2, idle2 = cpu_values(cpu_lines[1])
            delta_total = max(1, total2 - total1)
            delta_idle = max(0, idle2 - idle1)
            cpu_percent = max(0.0, min(100.0, (delta_total - delta_idle) * 100.0 / delta_total))

            mem = {}
            for line in lines:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                match = re.search(r"(\d+)", value)
                if match:
                    mem[key] = int(match.group(1)) * 1024
            ram_total = int(mem.get("MemTotal", 0))
            ram_available = int(mem.get("MemAvailable", mem.get("MemFree", 0)))
            ram_used = max(0, ram_total - ram_available)
            if not ram_total:
                raise OrganizerError("No se pudo leer MemTotal de /proc/meminfo")

            load_line = next((line for line in reversed(lines) if re.match(r"^\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s", line)), "")
            if not load_line:
                raise OrganizerError("No se pudo leer /proc/loadavg")
            loads = [float(x) for x in load_line.split()[:3]]
            return {
                "cpu_percent": cpu_percent,
                "ram_total": ram_total,
                "ram_used": ram_used,
                "ram_available": ram_available,
                "load_1": loads[0],
                "load_5": loads[1],
                "load_15": loads[2],
            }
        finally:
            channel.close()

    def ensure_remote_dir(self, category: str, remote_dir: str):
        def op(sftp):
            parts = [p for p in remote_dir.strip("/").split("/") if p]
            current = ""
            for part in parts:
                current += "/" + part
                try:
                    sftp.stat(current)
                except FileNotFoundError:
                    sftp.mkdir(current)

        return self._with_reconnect(category, op)

    def upload_file(self, local_path: Path, category: str, remote_path: str):
        remote_dir = str(Path(remote_path).parent).replace("\\", "/")
        self.ensure_remote_dir(category, remote_dir)
        temp_remote_path = remote_path + "." + uuid.uuid4().hex + ".uploading"

        signature = MediaOrganizer.file_signature(local_path)

        def op(sftp):
            try:
                sftp.put(str(local_path), temp_remote_path)
                if MediaOrganizer.file_signature(local_path) != signature:
                    raise OrganizerError("El archivo cambió durante la subida")
                sftp.rename(temp_remote_path, remote_path)
            except Exception:
                try:
                    sftp.remove(temp_remote_path)
                except OSError:
                    pass
                raise

        return self._with_reconnect(category, op)

    def exists(self, category: str, remote_path: str) -> bool:
        def op(sftp):
            try:
                sftp.stat(remote_path)
                return True
            except FileNotFoundError:
                return False

        return self._with_reconnect(category, op)

    def list_remote_dirs(self, category: str) -> list[str]:
        target = self.targets[category]
        def op(sftp):
            try:
                entries = sftp.listdir_attr(target.path)
            except FileNotFoundError:
                return []
            return [entry.filename for entry in entries
                    if not entry.filename.startswith('.') and entry.st_mode
                    and (entry.st_mode & 0o170000) == 0o040000]
        return self._with_reconnect(category, op)

    def build_remote_path(self, media: MediaInfo) -> str:
        target = self.targets[media.category]
        safe_title = self.safe_component(media.title)
        safe_title = re.sub(r"\s+", " ", safe_title).strip()

        # Series normales o anime episódico.
        if media.category in {"series", "anime"} and media.episode is not None:
            season = media.season if media.season is not None else 1
            filename = f"S{season:02d}E{media.episode:03d}{media.extension}" if media.category == "anime" and media.episode >= 100 else f"S{season:02d}E{media.episode:02d}{media.extension}"
            filename = filename[:-len(media.extension)] + media.episode_suffix + media.extension if media.extension else filename + media.episode_suffix
            return f"{target.path}/{safe_title}/Season {season}/{filename}"

        # Películas SIN carpeta (estructura plana)
        filename = safe_title if media.year is None else f"{safe_title} ({media.year})"
        filename = f"{filename}{media.extension}"
        return f"{target.path}/{filename}"


class MediaOrganizer:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.uploader = SftpUploader(LIBRARIES)
        self._last_storage_refresh = 0.0
        self._last_system_refresh = 0.0
        self._ensure_dirs()

    def _ensure_dirs(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        QUARANTINE_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        init_db()

    def refresh_emby_storage(self, force: bool = False):
        now = time.monotonic()
        if (
            not force
            and self._last_storage_refresh
            and now - self._last_storage_refresh < EMBY_STORAGE_REFRESH_SECONDS
        ):
            return

        self._last_storage_refresh = now
        try:
            info = self.uploader.storage_info("movies")
            save_emby_storage(
                path=info["path"],
                total=info["total"],
                used=info["used"],
                free=info["free"],
            )
            logging.info(
                "Espacio Emby actualizado: %.1f GB libres de %.1f TB",
                info["free"] / 1_000_000_000,
                info["total"] / 1_000_000_000_000,
            )
        except Exception as exc:
            safe_error = error_summary(exc)
            mark_emby_storage_error(safe_error)
            logging.warning("No se pudo actualizar el espacio de Emby: %s", safe_error)

    def refresh_emby_system(self, force: bool = False):
        now = time.monotonic()
        if (
            not force
            and self._last_system_refresh
            and now - self._last_system_refresh < EMBY_SYSTEM_REFRESH_SECONDS
        ):
            return
        self._last_system_refresh = now
        try:
            info = self.uploader.system_info("movies")
            save_emby_system(**info)
            logging.info(
                "Servidor Emby: CPU %.1f%% · RAM %.1f%%",
                info["cpu_percent"],
                (info["ram_used"] * 100 / info["ram_total"]) if info["ram_total"] else 0,
            )
        except Exception as exc:
            safe_error = error_summary(exc)
            mark_emby_system_error(safe_error)
            logging.warning("No se pudieron actualizar CPU/RAM de Emby: %s", safe_error)

    def shutdown(self):
        self.uploader.close()

    def should_ignore(self, path: Path) -> bool:
        if path.is_symlink() or not path.is_file():
            return True
        try:
            relative = path.relative_to(INBOX_DIR)
        except ValueError:
            return True
        if any(part in IGNORE_DIR_NAMES for part in relative.parts[:-1]):
            return True
        if any((INBOX_DIR.joinpath(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts))):
            return True
        return path.name.lower() in IGNORE_FILENAMES or path.suffix.lower() not in VIDEO_EXTENSIONS

    @staticmethod
    def file_signature(path):
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def is_stable(self, path: Path) -> bool:
        # Observe a full quiet period, even when a manual copy preserves its old mtime.
        observations = getattr(self, "_observations", None)
        if observations is None:
            self._observations = observations = {}
        try:
            signature = self.file_signature(path)
        except FileNotFoundError:
            observations.pop(path, None)
            return False
        now = time.monotonic()
        previous = observations.get(path)
        if previous is None or previous[0] != signature:
            observations[path] = signature, now
            return False
        return now - previous[1] >= STABLE_SECONDS

    def clean_title(self, raw_name: str) -> str:
        raw_name = unicodedata.normalize("NFC", raw_name)
        name = re.sub(r"(?i)(?:www\.|newpct\d*).*?$", "", raw_name)
        name = re.sub(r"^\[[^\]]+\]\s*", "", name)
        metadata = re.search(r"(?i)\b(?:4k|uhd|hdr10|hdr|dolby[ ._-]+vision|h[ .]?26[45]|2160p|1080p|720p|480p|x26[45]|hevc|bluray|bdrip|webrip|web[ ._-]?dl|hdrip|dvdrip|hdtv)\b", name)
        if metadata and name[:metadata.start()].strip(" -_.([]"):
            name = name[:metadata.start()]
        name = re.sub(r"(?i)\bh[ .]?26[45]\b", " ", name)
        name = name.replace(".", " ").replace("_", " ")
        name = re.sub(r"(?i)\b(?:4k|uhd|hdr10\+?|hdr|dv|dolby[ ._-]+vision|atmos|ddp?5[ .]1)\b", " ", name)
        name = re.sub(r"(?i)\bS\d{1,2}E\d{1,3}(?:E\d{1,3}|-S\d{1,2}E\d{1,3})*.*$", "", name)
        name = re.sub(r"(?i)\b\d{1,2}x\d{1,3}.*$", "", name)
        name = re.sub(r"(?i)\bSeason[ ._-]*\d+[ ._-]*Episode[ ._-]*\d+.*$", "", name)
        name = re.sub(r"^\[[^\]]+\]\s*", "", name)
        name = HASH_BLOCK_PATTERN.sub("", name)
        name = re.sub(r"(?i)\[Cap[ ._-]?\d{1,4}\]", "", name)
        name = re.sub(r"(?i)\bCap[íi]?tulo[ ._-]?\d{1,4}\b.*$", "", name)
        name = re.sub(r"(?i)\bCap[ ._-]?\d{1,4}\b", "", name)
        name = QUALITY_TOKENS.sub("", name)
        name = re.sub(r"(?i)www\..*$", "", name)
        name = re.sub(r"(?i)newpct\d*.*$", "", name)
        name = re.sub(r"\[\s*\]", "", name)
        name = re.sub(r"\s+", " ", name).strip(" -_.[]")
        return name

    def clean_release_title(self, raw_title: str) -> str:
        """Limpia títulos procedentes de releases anime/fansub sin tocar el número de episodio."""
        title = raw_title.replace(".", " ").replace("_", " ")
        title = QUALITY_TOKENS.sub(" ", title)
        title = re.sub(r"(?i)\b(mkv|mp4|avi|mov|m4v|ts)\b", " ", title)
        title = re.sub(r"\s+", " ", title).strip(" -_.[]")
        return title

    def strip_release_noise(self, raw_name: str) -> Tuple[str, Optional[str]]:
        """
        Limpia releases tipo:
          [Erai-raws] Naruto Shippuuden - 290 [1080p CR WEB-DL AVC AAC][MultiSub][26C1ED83]

        Devuelve:
          ("Naruto Shippuuden - 290", "Erai-raws")
        """
        name = Path(raw_name).stem
        release_group = None

        initial_group = re.match(r"^\[(?P<group>[^\]]+)\]\s*(?P<rest>.*)$", name)
        if initial_group:
            release_group = initial_group.group("group").strip()
            name = initial_group.group("rest").strip()

        name = HASH_BLOCK_PATTERN.sub(" ", name)
        name = BRACKET_BLOCK_PATTERN.sub(" ", name)

        # Paréntesis solo si parecen metadatos técnicos. Evitamos eliminar títulos legítimos.
        name = re.sub(
            r"(?i)\((?:\d{3,4}p|WEB-DL|WEBRip|BluRay|BDRip|AAC|HEVC|AVC|x264|x265|10bit|8bit|MultiSub|Dual Audio).*?\)",
            " ",
            name,
        )

        name = re.sub(r"\s+", " ", name).strip(" -_.[]")
        return name, release_group

    def clean_title_for_tmdb(self, raw_name: str) -> str:
        name = self.clean_title(raw_name)
        year = self.detect_year(name)
        if year and name != str(year):
            name = re.sub(r"[ (]*" + str(year) + r"[ )]*$", "", name).strip()
        return name

    def detect_episode(self, name: str) -> Tuple[Optional[int], Optional[int]]:
        for pattern in SERIES_EPISODE_PATTERNS:
            match = pattern.search(name)
            if match:
                return int(match.group("season")), int(match.group("episode"))
        return None, None

    def detect_spanish_episode(self, name: str, force_absolute: bool = False) -> Tuple[Optional[int], Optional[int]]:
        """
        Detecta Cap.XX / Capítulo XX.

        Si force_absolute=True, NO interpreta 290 como S02E90.
        Esto es importante para anime con numeración absoluta.
        """
        name = unicodedata.normalize("NFC", name)
        # Natural-language labels use absolute numbering (daily soaps, etc.).
        # Keep compact release notation Cap.103 / Capitulo.103 compatible.
        absolute = re.search(r"(?i)\bCap[íi]?tulo\s+(?P<episode>\d{1,4})(?!\d)", name)
        if absolute:
            number = int(absolute.group("episode"))
            return (1, number) if number > 0 else (None, None)
        for pattern in SPANISH_EPISODE_PATTERNS:
            match = pattern.search(name)
            if match:
                raw = match.group("episode")
                if force_absolute:
                    return 1, int(raw)
                if len(raw) >= 3:
                    season = int(raw[:-2])
                    episode = int(raw[-2:])
                else:
                    season = 1
                    episode = int(raw)
                return season, episode
        return None, None

    def detect_anime_release(self, path: Path) -> Optional[MediaInfo]:
        """
        Detecta anime en formato release/fansub/scene, antes de reglas genéricas.

        Casos cubiertos:
          [Erai-raws] Naruto Shippuuden - 290 [1080p CR WEB-DL AVC AAC][MultiSub][26C1ED83].mkv
          [SubsPlease] One Piece - 1120 (1080p) [A1B2C3D4].mkv
          [HorribleSubs] Bleach - 045 [720p].mkv
          Naruto Shippuden - Cap.291.mkv
          Naruto Shippuden - 291.mkv

        Decisión de diseño:
          - El número se trata como episodio absoluto de anime.
          - No se convierte 290 en S02E90.
          - Por defecto se envía a Anime/Título/Season 1/S01E290.mkv.
        """
        extension = path.suffix.lower()
        cleaned, release_group = self.strip_release_noise(path.name)
        parent_cleaned, parent_group = self.strip_release_noise(path.parent.name)

        group_l = (release_group or parent_group or "").lower()
        lower_cleaned = cleaned.lower()
        lower_parent = parent_cleaned.lower()
        lower_original = path.name.lower()

        has_anime_release_signal = (
            group_l in ANIME_RELEASE_GROUPS
            or any(hint in lower_original for hint in ANIME_HINTS)
            or any(hint in lower_parent for hint in ANIME_HINTS)
        )

        # Formatos habituales: "Titulo - 290", "Titulo 290", "Titulo - Cap.290".
        patterns = [
            re.compile(r"^(?P<title>.+?)\s*[-–—]\s*(?:Cap\.?\s*)?(?P<episode>\d{1,4})(?:\s+v\d+)?$", re.IGNORECASE),
            re.compile(r"^(?P<title>.+?)\s+Cap\.?\s*(?P<episode>\d{1,4})(?:\s+v\d+)?$", re.IGNORECASE),
            re.compile(r"^(?P<title>.+?)\s+(?P<episode>\d{1,4})(?:\s+v\d+)?$", re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(cleaned)
            if not match:
                continue

            title = self.clean_release_title(match.group("title"))
            episode = int(match.group("episode"))

            if episode <= 0:
                return None

            # Cap.103 alone also occurs in ordinary series; require an anime signal.
            if not has_anime_release_signal:
                return None

            if not title:
                return None

            category, final_title = self.resolve_existing_series(title, "anime")
            if category != "anime" and has_anime_release_signal:
                # Si existe en Series por error, mantenemos resolución; si no, forzamos Anime por señal fuerte.
                category = "anime"
                final_title = title

            logging.info(
                "Anime release detectado: file=%s | cleaned=%s | group=%s | title=%s | episode_abs=%s",
                path.name,
                cleaned,
                release_group,
                final_title,
                episode,
            )

            return MediaInfo(
                source_path=path,
                title=final_title,
                category="anime",
                season=1,
                episode=episode,
                extension=extension,
            )

        return None

    def detect_year(self, name: str) -> Optional[int]:
        matches = list(YEAR_PATTERN.finditer(name))
        if not matches:
            return None
        year = matches[-1].group(1)
        # Titles such as "1917" are not themselves release years.
        return None if self.clean_title(name).strip(" ()") == year else int(year)

    def normalize_name(self, value: str) -> str:
        value = value.lower()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = re.sub(r"[^a-z0-9]+", "", value)
        return value

    def resolve_existing_series(self, parsed_title: str, preferred_category: str) -> Tuple[str, str]:
        normalized_target = self.normalize_name(parsed_title)
        for category in dict.fromkeys([preferred_category, "series", "anime"]):
            try:
                directories = self.uploader.list_remote_dirs(category)
            except Exception as exc:
                raise OrganizerError(f"No se pudo comprobar la biblioteca remota ({category}): {error_summary(exc)}") from exc
            matches = [name for name in directories if self.normalize_name(name) == normalized_target]
            if len(matches) > 1:
                raise OrganizerError("Hay varias carpetas remotas con el mismo título normalizado")
            if matches:
                return category, matches[0]
        return preferred_category, parsed_title

    def load_tmdb_cache(self) -> dict:
        try:
            if TMDB_CACHE_FILE.exists():
                return json.loads(TMDB_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("No se pudo leer caché TMDb")
        return {}

    def save_tmdb_cache(self, cache: dict):
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            TMDB_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logging.exception("No se pudo guardar caché TMDb")

    def tmdb_search_multi(self, query: str) -> Optional[dict]:
        if not TMDB_API_KEY:
            logging.info("TMDb no configurado: falta TMDB_API_KEY")
            return None

        query = query.strip()
        if not query:
            return None

        cache = self.load_tmdb_cache()
        cache_key = self.normalize_name(query)

        cached = cache.get(cache_key)
        if isinstance(cached, dict) and time.time() - cached.get("cached_at", 0) < 86400:
            return cached.get("result")

        url = "https://api.themoviedb.org/3/search/multi"
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "language": "es-ES",
            "include_adult": "false",
        }

        try:
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            data = response.json()
            results = [
                r for r in data.get("results", [])
                if r.get("media_type") in {"movie", "tv"}
            ]

            if not results:
                cache[cache_key] = {"cached_at": time.time(), "result": None}
                self.save_tmdb_cache(cache)
                logging.info("TMDb sin resultados para query=%s", query)
                return None

            results = [r for r in results if any(
                self.normalize_name(r.get(key) or "") == self.normalize_name(query)
                for key in ("title", "name", "original_title", "original_name")
            )]
            if len(results) != 1:
                return None
            result = results[0]

            cache[cache_key] = {"cached_at": time.time(), "result": result}
            self.save_tmdb_cache(cache)
            return result

        except Exception as exc:
            logging.error(
                "Error consultando TMDb para query=%s: %s",
                query,
                redact_secrets(str(exc)),
            )
            return None

    def classify_with_tmdb(self, path: Path) -> Optional[MediaInfo]:
        raw_candidates = [
            path.stem,
        ]

        extension = path.suffix.lower()

        for raw in raw_candidates:
            query = self.clean_title_for_tmdb(raw)
            if not query:
                continue

            result = self.tmdb_search_multi(query)
            if not result:
                continue

            expected_year = self.detect_year(path.stem)
            if expected_year and not str(result.get("release_date") or result.get("first_air_date") or "").startswith(str(expected_year)):
                continue
            media_type = result.get("media_type")
            genre_ids = result.get("genre_ids", [])
            original_language = result.get("original_language")
            origin_country = result.get("origin_country") or []

            if media_type == "movie":
                title = result.get("title") or result.get("original_title") or query

                year = None
                release_date = result.get("release_date")
                if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
                    year = int(release_date[:4])

                is_animation = 16 in genre_ids
                is_japanese = original_language == "ja" or "JP" in origin_country
                category = "anime" if is_animation and is_japanese else "movies"

                logging.info(
                    "TMDb fallback: %s -> %s | title=%s | year=%s | media_type=%s | genres=%s | lang=%s | country=%s",
                    path.name,
                    category,
                    title,
                    year,
                    media_type,
                    genre_ids,
                    original_language,
                    origin_country,
                )

                return MediaInfo(
                    source_path=path,
                    title=title,
                    category=category,
                    year=year,
                    extension=extension,
                )

            if media_type == "tv":
                title = result.get("name") or result.get("original_name") or query
                is_animation = 16 in genre_ids
                is_japanese = original_language == "ja" or "JP" in origin_country
                category = "anime" if is_animation and is_japanese else "series"

                logging.info(
                    "TMDb fallback detectó TV sin episodio: %s -> %s | title=%s. Se ignora porque no hay episodio.",
                    path.name,
                    category,
                    title,
                )

                return None

        return None

    def classify(self, path: Path) -> MediaInfo:
        stem = path.stem
        lower = stem.lower()
        parent_stem = path.parent.name if path.parent != INBOX_DIR else ""
        parent_lower = parent_stem.lower()
        extension = path.suffix.lower()

        # 1) Primero, releases anime/fansub/scene.
        # Esto evita que "[Erai-raws] Naruto Shippuuden - 290 [...]" acabe en NoClasificado
        # o que "Cap.290" se convierta erróneamente en S02E90.
        anime_release = self.detect_anime_release(path)
        if anime_release:
            return anime_release

        episode_name = stem if re.search(r"(?i)\bS\d{1,2}E\d{1,3}", stem) else parent_stem
        multi = re.search(r"(?i)\bS(\d{1,2})E(\d{1,3})((?:E\d{1,3})+|-(?:S\d{1,2})?E?\d{1,3})(?!\d)", episode_name)
        episode_suffix = ""
        if multi:
            season, episode = int(multi[1]), int(multi[2])
            if multi[3].startswith("-"):
                end = re.fullmatch(r"(?i)-(?:S(\d{1,2}))?E?(\d{1,3})", multi[3])
                end_season = int(end[1]) if end[1] is not None else season
                if end_season != season or not episode < int(end[2]) <= episode + 50:
                    return MediaInfo(path, stem, "unknown", extension=extension)
                episode_suffix = "".join(f"E{n:02d}" for n in range(episode + 1, int(end[2]) + 1))
            else:
                extra_episodes = [int(n) for n in re.findall(r"(?i)E(\d+)", multi[3])]
                if any(b <= a for a, b in zip([episode] + extra_episodes, extra_episodes)):
                    return MediaInfo(path, stem, "unknown", extension=extension)
                episode_suffix = "".join(f"E{n:02d}" for n in extra_episodes)
        else:
            season, episode = self.detect_episode(stem)
        filename_has_episode = (multi is not None and episode_name == stem) or self.detect_episode(stem)[0] is not None
        if season is None or episode is None:
            season, episode = self.detect_episode(parent_stem)

        year = self.detect_year(stem)
        title = self.clean_title(stem)
        parent_title = ""
        for ancestor in path.parents:
            if ancestor == INBOX_DIR:
                break
            candidate = self.clean_title(ancestor.name)
            generic = {"series", "serie", "anime", "animes", "peliculas", "movies", "torrent", "torrents", "descargas", "downloads", "completed", "completados"}
            if candidate and self.normalize_name(candidate) not in generic and not re.fullmatch(r"(?i)(?:season|temporada|s)[ ._-]*\d+", candidate):
                parent_title = candidate
                break

        anime_context = any(hint in lower for hint in ANIME_HINTS) or any(hint in parent_lower for hint in ANIME_HINTS)

        if season is not None and episode is not None:
            category = "anime" if anime_context else "series"
            final_title = (title or parent_title) if filename_has_episode else (parent_title or title)
            if not final_title:
                return MediaInfo(path, stem, "unknown", extension=extension)
            category, final_title = self.resolve_existing_series(final_title, category)
            return MediaInfo(
                source_path=path,
                title=final_title,
                category=category,
                season=season,
                episode=episode,
                extension=extension,
                episode_suffix=episode_suffix,
            )

        # 2) Capítulos en español.
        # Si hay contexto anime, Cap.290 debe tratarse como episodio absoluto S01E290,
        # no como S02E90.
        spanish_season, spanish_episode = self.detect_spanish_episode(stem, force_absolute=anime_context)
        if spanish_season is None or spanish_episode is None:
            spanish_season, spanish_episode = self.detect_spanish_episode(parent_stem, force_absolute=anime_context)

        if spanish_season is not None and spanish_episode is not None:
            filename_has_spanish_episode = self.detect_spanish_episode(stem)[0] is not None
            final_title = (title or parent_title) if filename_has_spanish_episode else (parent_title or title)
            if not final_title:
                return MediaInfo(path, stem, "unknown", extension=extension)
            category = "anime" if anime_context else "series"
            category, final_title = self.resolve_existing_series(final_title, category)
            return MediaInfo(
                source_path=path,
                title=final_title,
                category=category,
                season=spanish_season,
                episode=spanish_episode,
                extension=extension,
            )

        # Antes de asumir película normal por año/calidad, probamos TMDb.
        # Esto evita que películas anime con año o calidad acaben en Peliculas.
        tmdb_media = self.classify_with_tmdb(path)
        if tmdb_media:
            return tmdb_media

        movie_like = year is not None or any(token in lower for token in ["movie", "film", "part ", "part-"])
        if movie_like:
            return MediaInfo(
                source_path=path,
                title=re.sub(r"[ (]*" + str(year) + r"[ )]*$", "", title).strip() if year and title != str(year) else title,
                category="movies",
                year=year,
                extension=extension,
            )

        return MediaInfo(
            source_path=path,
            title=title or path.stem,
            category="unknown",
            extension=extension,
        )

    def quarantine(self, path: Path, reason: str):
        destination = QUARANTINE_LOCAL_DIR / path.name
        if destination.exists():
            destination = QUARANTINE_LOCAL_DIR / self._dedupe_name(path.name, QUARANTINE_LOCAL_DIR)

        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = None

        if self.dry_run:
            logging.warning("[DRY-RUN] Cuarentena: %s -> %s | Motivo: %s", path, destination, reason)
            add_history(
                "organizer", "dry-run", title=path.name, source_path=str(path),
                destination=str(destination), details=reason, size_bytes=size_bytes,
            )
            return

        task_store.relocate(path,destination)
        shutil.move(str(path), str(destination))
        task_store.review(destination,reason)
        task_store.activity(destination,"review",reason)
        logging.warning("Cuarentena: %s -> %s | Motivo: %s", path, destination, reason)
        add_history(
            "organizer", "quarantined", title=path.name, source_path=str(path),
            destination=str(destination), details=reason, size_bytes=size_bytes,
        )

    def _dedupe_name(self, filename: str, folder: Path) -> str:
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while True:
            candidate = f"{stem} ({counter}){suffix}"
            if not (folder / candidate).exists():
                return candidate
            counter += 1

    def cleanup_download_folder(self, source_path: Path):
        """Elimina la carpeta contenedora solo si está realmente vacía."""
        folder = source_path.parent

        if folder == INBOX_DIR:
            return

        try:
            folder.relative_to(INBOX_DIR)
        except ValueError:
            return

        if not folder.exists():
            return

        if self.dry_run:
            try:
                next(folder.iterdir())
            except StopIteration:
                logging.info("[DRY-RUN] Se eliminaría la carpeta vacía: %s", folder)
            except OSError:
                pass
            else:
                logging.info(
                    "[DRY-RUN] Se conservaría la carpeta porque contiene otros elementos: %s",
                    folder,
                )
            return

        try:
            folder.rmdir()
            logging.info("Carpeta vacía eliminada: %s", folder)
        except OSError:
            logging.debug("Carpeta conservada porque contiene otros elementos: %s", folder)

    def cleanup_empty_folders(self):
        """Elimina únicamente directorios realmente vacíos."""
        folders = [p for p in INBOX_DIR.rglob("*") if p.is_dir()]
        folders.sort(key=lambda p: len(p.parts), reverse=True)

        for folder in folders:
            if folder == INBOX_DIR:
                continue
            if folder.is_symlink() or any(part in IGNORE_DIR_NAMES for part in folder.relative_to(INBOX_DIR).parts):
                continue

            if self.dry_run:
                try:
                    next(folder.iterdir())
                except StopIteration:
                    logging.info("[DRY-RUN] Se eliminaría carpeta vacía: %s", folder)
                except OSError:
                    pass
                continue

            try:
                folder.rmdir()
                logging.info("Carpeta vacía eliminada: %s", folder)
            except OSError:
                pass

    def notify_telegram(self, media: MediaInfo, remote_path: str):
        if not TELEGRAM_BOT_TOKEN:
            logging.info("Telegram no configurado: falta TELEGRAM_BOT_TOKEN")
            return

        category_names = {
            "anime": "Anime",
            "series": "Series",
            "movies": "Películas",
        }

        category = category_names.get(media.category, media.category)

        if media.episode is not None:
            detail = f"{media.title} - S{(media.season if media.season is not None else 1):02d}E{media.episode:03d}" if media.category == "anime" and media.episode >= 100 else f"{media.title} - S{(media.season if media.season is not None else 1):02d}E{media.episode:02d}"
        else:
            detail = media.title if media.year is None else f"{media.title} ({media.year})"

        text = (
            "✅ Contenido añadido a Emby\n"
            f"📚 Biblioteca: {category}\n"
            f"🎬 Título: {detail}\n"
            f"📁 Ruta: {remote_path}"
        )

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                },
                timeout=8,
            )
            response.raise_for_status()
            logging.info("Notificación Telegram enviada")
        except Exception as exc:
            logging.error(
                "Error enviando notificación Telegram: %s",
                redact_secrets(str(exc)),
            )

    def process_file(self, path: Path, decision=None):
        if decision is None and self.should_ignore(path):
            logging.debug("Ignorado: %s", path)
            return

        if not self.is_stable(path):
            logging.info("Archivo aún en copia o demasiado reciente: %s", path)
            return

        stable_signature = self.file_signature(path)
        task_store.activity(path,'classifying')
        rule=decision or task_store.rule_for(path)
        if rule:
            rule=dict(rule)
            if rule['category']!='movies' and 'episode' not in rule:
                season,episode=self.detect_episode(path.name)
                if season is not None and episode is not None:rule.update(season=season,episode=episode)
                else:rule=None
        media=MediaInfo(source_path=path,extension=path.suffix,**rule) if rule else self.classify(path)
        if self.file_signature(path) != stable_signature:
            logging.info("Archivo modificado durante la clasificación; se pospone: %s", path)
            return
        if media.category == "unknown":
            self.quarantine(path, "No se pudo clasificar con suficiente confianza")
            return

        remote_path = self.uploader.build_remote_path(media)
        logging.info("Clasificado: %s -> %s | Título=%s", path.name, media.category, media.title)
        logging.info("Destino remoto: %s", remote_path)

        if self.dry_run:
            logging.info("[DRY-RUN] Se subiría: %s -> %s", path, remote_path)
            add_history(
                "organizer", "dry-run", title=media.title, category=media.category,
                source_path=str(path), destination=remote_path,
                details="Subida simulada",
                size_bytes=path.stat().st_size if path.exists() else None,
            )
            return

        destination_exists = self.uploader.exists(media.category, remote_path)
        if self.file_signature(path) != stable_signature:
            logging.info("Archivo modificado antes de la subida; se pospone: %s", path)
            return
        if destination_exists:
            if decision is not None:raise OrganizerError("El archivo remoto ya existe; se conserva el archivo para revisión")
            self.quarantine(path, f"El archivo remoto ya existe: {remote_path}")
            return

        signature = self.file_signature(path)
        size_bytes = signature[2]
        task_store.activity(path,"transferring",remote_path)
        self.uploader.upload_file(path, media.category, remote_path)
        if self.file_signature(path) != signature:
            raise OrganizerError("El archivo cambió durante la subida; se conserva la copia local")
        path.unlink()
        getattr(self, "_observations", {}).pop(path, None)
        task_store.activity(path,"incorporated",remote_path)
        logging.info("Subido y eliminado localmente: %s", path)
        add_history(
            "organizer", "success", title=media.title, category=media.category,
            source_path=str(path), destination=remote_path,
            details="Subido a Emby", size_bytes=size_bytes,
        )

        self.notify_telegram(media, remote_path)

        self.cleanup_download_folder(path)

    def scan_once(self):
        if not getattr(self,'_last_review_import',0) or time.monotonic()-self._last_review_import>300:
            self._last_review_import=time.monotonic()
            for candidate in QUARANTINE_LOCAL_DIR.rglob('*'):
                if candidate.is_file() and not candidate.is_symlink() and candidate.suffix.lower() in VIDEO_EXTENSIONS:
                    task_store.register_existing(candidate)
        for row in task_store.approved_reviews():
            try:
                path=Path(row['path'])
                if not path.resolve().is_relative_to(QUARANTINE_LOCAL_DIR.resolve()) or path.is_symlink():raise OrganizerError('El archivo de revisión está fuera de la cuarentena')
                if task_store.signature(path)!=row['signature']:raise OrganizerError('El archivo ha cambiado desde la revisión')
                # An explicit review bypasses inbox exclusion, never stability or upload checks.
                if not self.is_stable(path):continue
                self.process_file(path,task_store.validate_decision(json.loads(row['decision'])))
                if not path.exists():task_store.finish_review(row['id'])
            except Exception as exc:task_store.finish_review(row['id'],error_summary(exc))
        found_any = False
        retries=getattr(self,"_file_retries",{});self._file_retries=retries
        for item in sorted(INBOX_DIR.rglob("*")):
            if item.is_dir():
                continue
            found_any = True
            try:
                previous=retries.get(item)
                if previous and previous[0]==self.file_signature(item) and time.monotonic()<previous[1]:continue
                self.process_file(item)
                retries.pop(item,None)
            except Exception as exc:
                logging.error("No se pudo procesar %s: %s", item, error_summary(exc))
                task_store.activity(item,"failed",error_summary(exc))
                try:
                    attempts=min(6,(retries.get(item) or (None,0,0))[2]+1)
                    retries[item]=(self.file_signature(item),time.monotonic()+min(900,30*2**attempts),attempts)
                except OSError:retries.pop(item,None)

        if not found_any:
            logging.info("No se encontraron archivos dentro de %s", INBOX_DIR)

        self.cleanup_empty_folders()

    def run_daemon(self):
        logging.info("Modo daemon iniciado. Escaneando %s cada %s segundos.", INBOX_DIR, SCAN_INTERVAL_SECONDS)
        while True:
            try:
                self.refresh_emby_storage()
                self.refresh_emby_system()
                self.scan_once()
                set_runtime_state("organizer_heartbeat",{"ok":True,"checked_at":utc_now()})
            except Exception as exc:
                logging.exception("Error durante el escaneo")
                add_history(
                    "organizer", "error", title="Error durante el escaneo",
                    details=str(exc),
                )
            time.sleep(SCAN_INTERVAL_SECONDS)


def setup_logging(verbose: bool = False):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organizador local para Emby con subida SFTP")
    parser.add_argument("--scan-once", action="store_true", help="Ejecuta un único escaneo")
    parser.add_argument("--daemon", action="store_true", help="Modo continuo")
    parser.add_argument("--dry-run", action="store_true", help="No mueve ni sube archivos")
    parser.add_argument("--verbose", action="store_true", help="Más detalle en logs")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.scan_once and not args.daemon:
        args.scan_once = True

    setup_logging(args.verbose)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock = (STATE_DIR / "organizer.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise SystemExit("Ya hay un organizador activo")
    organizer = MediaOrganizer(dry_run=args.dry_run)

    try:
        if args.scan_once:
            organizer.refresh_emby_storage(force=True)
            organizer.refresh_emby_system(force=True)
            organizer.scan_once()
            # A one-shot run must also observe a full quiet period.
            time.sleep(STABLE_SECONDS)
            organizer.scan_once()
        elif args.daemon:
            organizer.run_daemon()
    finally:
        organizer.shutdown()
        lock.close()


if __name__ == "__main__":
    main()
