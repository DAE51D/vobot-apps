#!/usr/bin/env python3
"""Minimal local GPU stats daemon for the Vobot Mini Dock 'nvtop' app.

Queries `nvidia-smi` for the GPU(s) visible on *this* host and serves a
small JSON API. The response schema intentionally mirrors gpu-hot's
`/api/gpu-data` (https://github.com/psalias2006/gpu-hot) so the on-device
app's parser works unmodified against either backend -- point the app's
"server" setting at whichever one is running.

Stdlib only, no pip install required. Designed to be dropped onto any
box that can see an NVIDIA GPU (bare metal, or an LXC/VM with GPU
passthrough) -- it makes no assumption about being "the" Proxmox host,
it just reads whatever `nvidia-smi` reports locally.
"""
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8039
NVIDIA_SMI = "nvidia-smi"
SUBPROCESS_TIMEOUT = 5

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


def _num(raw):
    """CSV cell -> float, or None for N/A, or the raw string if not numeric."""
    s = raw.strip()
    if s in ("", "[N/A]", "N/A"):
        return None
    try:
        return float(s.split()[0])
    except ValueError:
        return s


def query_gpus():
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


class Handler(BaseHTTPRequestHandler):
    server_version = "VobotGPUDaemon/1.0"

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
                self._json(200, {"gpus": gpus, "timestamp": time.time()})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
        elif self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/":
            self._json(200, {"service": "vobot-gpu-daemon", "endpoints": ["/api/gpu-data", "/health"]})
        else:
            self._json(404, {"error": "not found"})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"vobot-gpu-daemon listening on :{PORT}")
    server.serve_forever()
