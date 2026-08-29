#!/usr/bin/env python3
"""Minimal local GPU stats daemon for the Vobot Mini Dock 'nvtop' app.

Queries the local GPU tooling (`nvidia-smi` or `amd-smi`) for the GPU(s)
visible on *this* host and serves a small JSON API. The response schema
intentionally mirrors gpu-hot's `/api/gpu-data`
(https://github.com/psalias2006/gpu-hot) so the on-device app's parser
works unmodified against either backend -- point the app's "server"
setting at whichever one is running.

Stdlib only, no pip install required. Designed to be dropped onto any
box that can see a GPU (bare metal, or an LXC/VM with GPU passthrough)
-- it makes no assumption about being "the" Proxmox host, it just reads
whatever the vendor CLI reports locally. The vendor backend is detected
at startup (override with the VOBOT_GPU_BACKEND env var: nvidia|amd).
"""
import json
import os
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8039
NVIDIA_SMI = "nvidia-smi"
AMD_SMI = "amd-smi"
SUBPROCESS_TIMEOUT = 5

# Bump on any change to the response schema or a backend's behaviour. Unlike
# GIT_COMMIT this is human-meaningful: it's what the app compares against when
# deciding whether a field it wants can be expected to exist.
# 1.0.0 - nvidia-smi only
# 1.1.0 - amd-smi backend + auto-detection, "backend"/"version" response fields
VERSION = "1.1.0"

# Stamped at deploy time from `git rev-parse --short HEAD` (see README's deploy
# steps) so /api/gpu-data tells you exactly which commit is running on the
# host -- catches the "did I actually redeploy after that change?" mistake.
GIT_COMMIT = "unknown"

QUERY_FIELDS = [
    "index", "name", "uuid", "driver_version",
    "temperature.gpu", "utilization.gpu", "utilization.memory",
    "memory.used", "memory.total", "memory.free",
    "power.draw", "power.limit", "fan.speed",
    "clocks.gr", "clocks.sm", "clocks.mem",
    "clocks.max.gr", "clocks.max.sm", "clocks.max.mem",
    "pcie.link.gen.current", "pcie.link.gen.max",
    "pcie.link.width.current", "pcie.link.width.max",
    "pstate",
]
THROTTLE_FIELDS = [
    "clocks_throttle_reasons.hw_slowdown",
    "clocks_throttle_reasons.sw_power_cap",
    "clocks_throttle_reasons.hw_thermal_slowdown",
    "clocks_throttle_reasons.sw_thermal_slowdown",
]
THROTTLE_LABELS = ["HW Slowdown", "SW Power Cap", "HW Thermal", "SW Thermal"]

PROCESS_FIELDS = [
    "gpu_uuid", "pid", "process_name", "used_memory",
]


def _num(raw):
    """CSV cell -> float, or None for N/A, or the raw string if not numeric."""
    s = raw.strip()
    if s in ("", "[N/A]", "N/A"):
        return None
    try:
        return float(s.split()[0])
    except ValueError:
        return s


def detect_backend():
    """Return 'nvidia' or 'amd' based on which vendor CLI is on PATH."""
    forced = os.environ.get("VOBOT_GPU_BACKEND", "").strip().lower()
    if forced in ("nvidia", "amd"):
        return forced
    if shutil.which(NVIDIA_SMI):
        return "nvidia"
    if shutil.which(AMD_SMI):
        return "amd"
    raise RuntimeError("no GPU tooling found on PATH (looked for nvidia-smi, amd-smi)")


def _nvidia_query_gpus():
    fields = ",".join(QUERY_FIELDS)
    out = subprocess.run(
        [NVIDIA_SMI, "--query-gpu=" + fields, "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, check=True,
    ).stdout.strip()

    throttle_lines = []
    try:
        throttle_out = subprocess.run(
            [NVIDIA_SMI, "--query-gpu=" + ",".join(THROTTLE_FIELDS), "--format=csv,noheader"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, check=True,
        ).stdout.strip()
        throttle_lines = throttle_out.splitlines()
    except subprocess.CalledProcessError:
        pass  # older driver without these fields -- just report "None" below

    gpus = {}
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for i, line in enumerate(out.splitlines()):
        vals = [v.strip() for v in line.split(",")]
        row = dict(zip(QUERY_FIELDS, vals))

        throttle_reasons = "None"
        if i < len(throttle_lines):
            trow = [v.strip() for v in throttle_lines[i].split(",")]
            active = [label for label, val in zip(THROTTLE_LABELS, trow) if val == "Active"]
            if active:
                throttle_reasons = ", ".join(active)

        gpus[row["index"]] = {
            "index": row["index"],
            "name": row["name"],
            "uuid": row["uuid"],
            "driver_version": row["driver_version"],
            "temperature": _num(row["temperature.gpu"]),
            "utilization": _num(row["utilization.gpu"]),
            "memory_utilization": _num(row["utilization.memory"]),
            "memory_used": _num(row["memory.used"]),
            "memory_total": _num(row["memory.total"]),
            "memory_free": _num(row["memory.free"]),
            "power_draw": _num(row["power.draw"]),
            "power_limit": _num(row["power.limit"]),
            "fan_speed": _num(row["fan.speed"]),
            "clock_graphics": _num(row["clocks.gr"]),
            "clock_sm": _num(row["clocks.sm"]),
            "clock_memory": _num(row["clocks.mem"]),
            "clock_max_graphics": _num(row["clocks.max.gr"]),
            "clock_max_sm": _num(row["clocks.max.sm"]),
            "clock_max_memory": _num(row["clocks.max.mem"]),
            "pcie_gen": row["pcie.link.gen.current"],
            "pcie_gen_max": row["pcie.link.gen.max"],
            "pcie_width": row["pcie.link.width.current"],
            "pcie_width_max": row["pcie.link.width.max"],
            "performance_state": row["pstate"],
            "throttle_reasons": throttle_reasons,
            "timestamp": now,
        }
    return gpus


def _read_pid_stats(pids):
    """Return per-PID cpu/rss/cmd metadata from ps when available."""
    if not pids:
        return {}
    try:
        pid_arg = ",".join(str(pid) for pid in sorted(set(pids)))
        out = subprocess.run(
            ["ps", "-p", pid_arg, "-o", "pid=,%cpu=,rss=,comm=,args="],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, check=True,
        ).stdout.strip()
    except Exception:
        return {}

    stats = {}
    for line in out.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) < 4:
            continue
        pid = parts[0]
        cpu = parts[1]
        rss = parts[2]
        comm = parts[3]
        args = parts[4] if len(parts) > 4 else comm
        try:
            cpu_v = float(cpu)
        except ValueError:
            cpu_v = None
        try:
            rss_v = int(rss)
        except ValueError:
            rss_v = None
        stats[pid] = {
            "cpu_percent": cpu_v,
            "rss_kib": rss_v,
            "command": args,
            "comm": comm,
        }
    return stats


def _nvidia_query_processes(gpus):
    """Return active GPU compute processes grouped by GPU index."""
    uuid_to_index = {}
    for idx, g in gpus.items():
        uuid = g.get("uuid")
        if uuid:
            uuid_to_index[str(uuid)] = str(idx)

    try:
        out = subprocess.run(
            [NVIDIA_SMI, "--query-compute-apps=" + ",".join(PROCESS_FIELDS), "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return {str(idx): [] for idx in gpus.keys()}

    rows = []
    pids = []
    for line in out.splitlines():
        vals = [v.strip() for v in line.split(",")]
        if len(vals) < len(PROCESS_FIELDS):
            continue
        row = dict(zip(PROCESS_FIELDS, vals))
        pid = row.get("pid", "")
        if pid:
            pids.append(pid)
        rows.append(row)

    pid_stats = _read_pid_stats(pids)
    grouped = {str(idx): [] for idx in gpus.keys()}

    for row in rows:
        uuid = str(row.get("gpu_uuid") or "")
        gpu_index = uuid_to_index.get(uuid)
        if gpu_index is None and grouped:
            gpu_index = next(iter(grouped.keys()))
        if gpu_index is None:
            continue

        pid = str(row.get("pid") or "?")
        proc_name = row.get("process_name") or "?"
        used_mem = _num(row.get("used_memory", "0"))
        if not isinstance(used_mem, (int, float)):
            used_mem = 0.0

        pstat = pid_stats.get(pid, {})
        grouped[gpu_index].append({
            "pid": pid,
            "process_name": proc_name,
            "used_memory": float(used_mem),
            "cpu_percent": pstat.get("cpu_percent"),
            "rss_kib": pstat.get("rss_kib"),
            "command": pstat.get("command") or proc_name,
        })

    for idx, plist in grouped.items():
        plist.sort(key=lambda p: p.get("used_memory", 0), reverse=True)
    return grouped


# --- AMD (amd-smi) backend -------------------------------------------------
#
# amd-smi speaks JSON with every scalar wrapped as {"value": x, "unit": "..."},
# and reports unsupported fields as the literal string "N/A" (or omits the key
# entirely -- APUs drop fan/pcie/mem-util wholesale). Everything below is
# deliberately tolerant of both, mapping onto the nvidia-shaped schema so the
# on-device app needs no branching.

_amd_static_cache = None


def _amd_run(args):
    out = subprocess.run(
        [AMD_SMI] + args + ["--json"],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, check=True,
    ).stdout.strip()
    return json.loads(out) if out else None


def _amd_val(node, scale=1.0):
    """Unwrap amd-smi's {"value": x, "unit": y} (or bare scalar) -> float|None."""
    if isinstance(node, dict):
        node = node.get("value")
    if node is None or node == "N/A":
        return None
    try:
        return float(node) * scale
    except (TypeError, ValueError):
        return None


def _amd_mb(node):
    """Unwrap a memory field to MB, honouring its declared unit."""
    unit = node.get("unit", "MB") if isinstance(node, dict) else "MB"
    scale = {"B": 1.0 / (1024 * 1024), "KB": 1.0 / 1024, "MB": 1.0,
             "GB": 1024.0, "TB": 1024.0 * 1024}.get(unit, 1.0)
    return _amd_val(node, scale)


def _amd_max_level(levels):
    """Largest frequency from a static clock's {"Level N": {...}} map, in MHz."""
    if not isinstance(levels, dict):
        return None
    vals = [v for v in (_amd_val(lvl) for lvl in levels.values()) if v is not None]
    return max(vals) if vals else None


def _amd_static():
    """Board identity + ceilings. Immutable for the life of the process, so
    cached -- `amd-smi static` is ~50x the payload of a `monitor` poll."""
    global _amd_static_cache
    if _amd_static_cache is not None:
        return _amd_static_cache

    uuids = {}
    try:
        for row in _amd_run(["list"]) or []:
            uuids[str(row.get("gpu"))] = row.get("uuid")
    except Exception:
        pass

    static = {}
    for row in (_amd_run(["static"]) or {}).get("gpu_data", []):
        idx = str(row.get("gpu"))
        asic = row.get("asic") or {}
        board = row.get("board") or {}
        bus = row.get("bus") or {}
        driver = row.get("driver") or {}
        clock = row.get("clock") or {}
        limit = row.get("limit") or {}

        gen = bus.get("pcie_interface_version")
        if isinstance(gen, str):
            gen = gen.replace("Gen", "").strip() or None

        static[idx] = {
            "name": asic.get("market_name") or board.get("product_name") or "AMD GPU",
            "uuid": uuids.get(idx) or asic.get("asic_serial") or "",
            "driver_version": driver.get("version") or "",
            "power_limit": _amd_val((limit.get("ppt0") or {}).get("socket_power_limit")),
            "clock_max_graphics": _amd_max_level((clock.get("sys") or {}).get("frequency_levels")),
            "clock_max_memory": _amd_max_level((clock.get("mem") or {}).get("frequency_levels")),
            "pcie_gen_max": str(gen) if gen else "",
            "pcie_width_max": str(bus.get("max_pcie_width") or ""),
        }

    _amd_static_cache = static
    return static


def _amd_query_gpus():
    static = _amd_static()
    extra = {}
    try:
        for row in (_amd_run(["metric", "--fan", "--pcie"]) or {}).get("gpu_data", []):
            extra[str(row.get("gpu"))] = row
    except Exception:
        pass  # APUs report neither; nulls below are the expected outcome

    gpus = {}
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for row in _amd_run(["monitor"]) or []:
        idx = str(row.get("gpu"))
        s = static.get(idx, {})
        e = extra.get(idx, {})
        fan = e.get("fan") or {}
        pcie = e.get("pcie") or {}

        mem_used = _amd_mb(row.get("vram_used"))
        mem_total = _amd_mb(row.get("vram_total"))
        mem_free = None
        if mem_used is not None and mem_total is not None:
            mem_free = mem_total - mem_used

        mem_util = _amd_val(row.get("mem"))
        if mem_util is None and mem_used is not None and mem_total:
            mem_util = round(mem_used / mem_total * 100, 1)

        gfx_clk = _amd_val(row.get("gfx_clk"))
        # Hotspot is the closest analogue to nvidia's single reported temp;
        # fall back to edge, which is what APUs expose instead.
        temp = _amd_val(row.get("hotspot_temperature"))
        if temp is None:
            temp = _amd_val(row.get("edge_temperature"))

        gpus[idx] = {
            "index": idx,
            "name": s.get("name", "AMD GPU"),
            "uuid": s.get("uuid", ""),
            "driver_version": s.get("driver_version", ""),
            "temperature": temp,
            "utilization": _amd_val(row.get("gfx")),
            "memory_utilization": mem_util,
            "memory_used": mem_used,
            "memory_total": mem_total,
            "memory_free": mem_free,
            "power_draw": _amd_val(row.get("power_usage")),
            "power_limit": s.get("power_limit"),
            "fan_speed": _amd_val(fan.get("usage") if "usage" in fan else fan.get("speed")),
            "clock_graphics": gfx_clk,
            "clock_sm": gfx_clk,
            "clock_memory": _amd_val(row.get("mem_clk")),
            "clock_max_graphics": s.get("clock_max_graphics"),
            "clock_max_sm": s.get("clock_max_graphics"),
            "clock_max_memory": s.get("clock_max_memory"),
            "pcie_gen": str(pcie.get("current_speed", "") or ""),
            "pcie_gen_max": s.get("pcie_gen_max", ""),
            "pcie_width": str(pcie.get("width", "") or ""),
            "pcie_width_max": s.get("pcie_width_max", ""),
            "performance_state": "",
            "throttle_reasons": "None",
            "timestamp": now,
        }
    return gpus


def _amd_query_processes(gpus):
    grouped = {str(idx): [] for idx in gpus.keys()}
    try:
        rows = _amd_run(["process"]) or []
    except Exception:
        return grouped

    pending = []
    pids = []
    for row in rows:
        idx = str(row.get("gpu"))
        if idx not in grouped:
            continue
        for entry in row.get("process_list") or []:
            info = entry.get("process_info")
            if not isinstance(info, dict):
                continue  # idle GPUs yield the string "No running processes detected"
            pid = str(info.get("pid") or "?")
            pids.append(pid)
            pending.append((idx, pid, info))

    pid_stats = _read_pid_stats(pids)
    for idx, pid, info in pending:
        mem = (info.get("memory_usage") or {}).get("vram_mem") or info.get("mem")
        used = _amd_mb(mem) or 0.0
        pstat = pid_stats.get(pid, {})
        name = info.get("name") or "?"
        grouped[idx].append({
            "pid": pid,
            "process_name": name,
            "used_memory": used,
            "cpu_percent": pstat.get("cpu_percent"),
            "rss_kib": pstat.get("rss_kib"),
            "command": pstat.get("command") or name,
        })

    for plist in grouped.values():
        plist.sort(key=lambda p: p.get("used_memory", 0), reverse=True)
    return grouped


# --- dispatch --------------------------------------------------------------

BACKEND = None


def query_gpus():
    return _amd_query_gpus() if BACKEND == "amd" else _nvidia_query_gpus()


def query_processes(gpus):
    return _amd_query_processes(gpus) if BACKEND == "amd" else _nvidia_query_processes(gpus)


class Handler(BaseHTTPRequestHandler):
    server_version = "VobotGPUDaemon/" + VERSION

    def log_message(self, fmt, *args):
        pass  # systemd journal stays quiet on normal requests

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/gpu-data":
            try:
                gpus = query_gpus()
                processes = query_processes(gpus)
                self._json(200, {
                    "gpus": gpus,
                    "processes": processes,
                    "timestamp": time.time(),
                    "backend": BACKEND,
                    "version": VERSION,
                    "git_commit": GIT_COMMIT,
                })
            except Exception as exc:
                self._json(500, {
                    "error": str(exc),
                    "backend": BACKEND,
                    "version": VERSION,
                    "git_commit": GIT_COMMIT,
                })
        elif self.path == "/health":
            self._json(200, {
                "status": "ok",
                "backend": BACKEND,
                "version": VERSION,
                "git_commit": GIT_COMMIT,
            })
        elif self.path == "/":
            self._json(200, {
                "service": "vobot-gpu-daemon",
                "endpoints": ["/api/gpu-data", "/health"],
                "backend": BACKEND,
                "version": VERSION,
                "git_commit": GIT_COMMIT,
            })
        else:
            self._json(404, {"error": "not found"})


if __name__ == "__main__":
    BACKEND = detect_backend()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"vobot-gpu-daemon v{VERSION} listening on :{PORT} (backend: {BACKEND})")
    server.serve_forever()
