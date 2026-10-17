"""Cached platform probes, kept separate from HTTP routing."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

_NET_SAMPLE=None
_METRICS_CACHE={"at":0.0,"value":None}

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
    if sys.platform!="darwin":return {"available":False}
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


