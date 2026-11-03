---
description: "Vobot GPU Monitor App: Build/update the 'nvtop' Vobot Mini Dock app that shows live GPU stats (util/mem/temp/power/clocks) by polling the nvstats-service HTTP API. Use when: building or refining the nvtop app screens, wiring the nvstats fetch, tuning arc/chart ranges, or debugging the device-side fetch."
agent: 'agent'
tools: ['search/changes', 'search', 'edit/editFiles', 'execute/runInTerminal', 'jcodemunch/*', 'jdocmunch/*', 'jdatamunch/*']
context: |
  - Vobot platform conventions: see .github/copilot-instructions.md (lifecycle, LVGL, web settings, upload/debug workflow)
  - Reference apps for patterns: proxmox/apps/proxmox/__init__.py (arc gauges, encoder handling), ntfy/apps/ntfy/__init__.py (page caching via HIDDEN flag instead of rebuild), copilot/apps/copilot/__init__.py (stacked lv.chart bar+line pattern)
  - Data source: nvstats-service (https://github.com/DAE51D/nvstats-service, local clone D:\daevid\Code\nvstats-service), HTTP API on :8039 of each GPU host (proxmox NVIDIA, evo-x2 AMD): GET /api/v1/sample. Migration record: docs/vobot-nvtop-migration.md in that repo. (Replaced the old Vobot-only vobot-gpu-daemon on 2026-11-02.)
  - gpu-hot project (reference/inspiration only, not a dependency): https://github.com/psalias2006/gpu-hot
  - App source (v1.1.0, deployed and tested on-device as of 2026-11-02): D:\daevid\Code\Vobot\nvtop\apps\nvtop\__init__.py
  - App manifest: D:\daevid\Code\Vobot\nvtop\apps\nvtop\manifest.yml
  - App icon (generated placeholder, 48x48 PNG): D:\daevid\Code\Vobot\nvtop\apps\nvtop\resources\icon.png
---

# nvtop / GPU Monitor App — Vobot Mini Dock

## Role

You are an expert MicroPython/LVGL developer building Vobot Mini Dock apps (see `.github/copilot-instructions.md` for the full platform guide). This prompt is scoped to the **`nvtop` app**: an on-device live monitor for an NVIDIA or AMD GPU, modeled visually on `nvtop`'s terminal UI, sourced from nvstats-service's HTTP API — no on-device `nvtop`/`nvidia-smi` execution.

## Feasibility & architecture — resolved

The original open question was "do we need a small Linux service the Vobot reads from?" **Yes — and it's built and already running.** Don't rely on `gpu-hot` (`komodo.home.lan:1312`) as the data source: it was only an example of "how do you read this data at all," and it's an optional third-party stack most users of this app won't have installed. Instead the app reads **nvstats-service**, our own shared telemetry service (also used by the knvtop Plasma widget and onvtop), so it works for anyone with a GPU + that service, independent of any other dashboard. nvstats replaced the earlier Vobot-only `vobot-gpu-daemon` (2026-11-02): one sampler, one response shape for all clients, NVIDIA and AMD backends.

- **nvstats-service** (https://github.com/DAE51D/nvstats-service) is a Python service that samples the GPU once per second and exposes it over D-Bus (knvtop, onvtop) and, optionally, HTTP (this app): `GET /api/v1/sample`, `/api/v1/stream` (SSE), and `/health`, on port `8039`. Stdlib-only; no pip installs.
- **Backends:** `nvidia-smi` (one `--query-gpu` call per poll, `--query-compute-apps` for processes) or AMD sysfs plus a cached `amd-smi static`; auto-detected, override with `NVSTATS_GPU_BACKEND=nvidia|amd`. The response reports which one in `gpu.backend`.
- **Deployed 2026-11-02:** `proxmox.home.lan:8039` (NVIDIA RTX 5060 Ti, headless system unit running as `nobody`) and `evo-x2.home.lan:8039` (AMD Radeon 8060S APU, user unit). AMD APUs report no fan, PCIe link state, performance state, or power limit (all `null`), report GTT as memory so totals look huge (78 GB), and have no per-process GPU% for NVIDIA processes. The app treats every field as optional, so none of that needs special handling.
- **Host-agnostic on purpose.** The service just calls whatever `nvidia-smi`/`amd-smi` resolves to locally, so it runs unmodified on bare metal, in an LXC/VM with GPU passthrough, or on another Linux box. Not every future user of this app will have a Proxmox+GPU host; the service has to run wherever *their* GPU lives.
- **Out of scope for now:** macOS and Windows equivalents (different data sources, e.g. `powermetrics` on macOS, `nvidia-smi.exe`/WMI on Windows). Don't paint the on-device app or the JSON schema into a Linux-only corner if it's easy to avoid.
- **Process table (2026-07-20, now from nvstats `gpu_procs`):** the service returns the top 5 GPU processes by VRAM with CPU% and the full command line (secret-looking option values masked). The app's Page 4 (Processes) renders the top 4, each as `argv0` / `GPU/CPU/PID` / one CLI flag+value per line, with its own encoder-scroll mode (ENTER toggles; see `_process_scroll_mode` in `__init__.py`).

## Response shape (`GET http://proxmox.home.lan:8039/api/v1/sample`)

Minimal view (default; sized for the dock's RAM, ~1-3 KB). `?full=1` adds everything else and `/api/v1/stream` is an SSE stream; the dock uses neither (polling with `urequests`):

```json
{
  "schema": 1, "host": "proxmox", "seq": 4, "ts": 1793660158.2, "version": "0.2.0", "git_commit": "d6894d0",
  "gpu": {
    "index": 0, "name": "NVIDIA GeForce RTX 5060 Ti", "uuid": "GPU-...", "driver": "595.99.02", "backend": "nvidia",
    "util": 0, "mem_util": 39, "mem_used": 10410, "mem_total": 16311,
    "temp": 32, "power_w": 3.75, "power_cap_w": 180, "fan_pct": 0,
    "clock_gfx": 210, "clock_gfx_max": 3120, "clock_mem": 405, "clock_mem_max": 14001,
    "pcie_gen": 1, "pcie_gen_max": 3, "pcie_width": 8, "pcie_width_max": 16,
    "pstate": "P8", "throttle": "None"
  },
  "gpu_procs": [
    {"pid": 2012084, "name": "llama-server", "user": "1001", "vram_kb": 10641408, "gpu_pct": null, "cpu_pct": 0.0, "cmdline": "/opt/llama-bonsai/llama-server --port 8084 ..."}
  ]
}
```

Notes for parsing on-device:
- `gpu` is a single object (GPU 0 by default; the service picks the GPU via `NVSTATS_GPU_INDEX`, the dock has no GPU-index setting). `gpu_procs` is the top 5 by VRAM; `vram_kb` is KiB, `cmdline` is capped at 1024 chars and has secret-looking option values masked by the service.
- Any field can be `null` (e.g. `fan_pct`/`power_cap_w` on AMD APUs, `gpu_pct` for NVIDIA processes): treat every field as optional and default sensibly rather than erroring.
- `throttle` is a human string (`"None"` when healthy, comma-joined reason names otherwise); it can be long, so truncate or scroll it.
- AMD APUs report GTT as memory so totals look huge (e.g. 78 GB); that is expected.
- `sys.cpu` (host CPU %) is the only `sys` field in the minimal view; it feeds the CPU history line.
- Top-level `version`/`git_commit` identify the nvstats build running on the host (shown on the Details page).

## Goal — app structure

A 4-page app (scroll wheel cycles pages manually; Gauges/History also auto-cycle every 5s like the reference `nvtop` capture unless the user is actively scrolling — reset the auto-cycle timer on manual input so it doesn't fight the user; Details/Processes are manual-only detours that auto-cycle resumes from once you leave them — see `AUTO_CYCLE_PAGES` vs `NUM_PAGES`). `CAN_BE_AUTO_SWITCHED = True` for the dock's own app-rotation (separate concept from this in-app page auto-cycle — don't conflate the two timers).

**Page 1 — Gauges (live snapshot)**
- Arc: GPU utilization % (reuse proxmox app's arc pattern: rotation 270, bg angle 0–360, hidden knob)
- Arc or bar: memory utilization % with `mem_used`/`mem_total` as a sub-label (e.g. `5.3G/15.9G`)
- Arc: temperature (color the arc red past ~80°C the way the dashboard highlights hot temps)
- Bar: power draw vs `power_cap_w` (e.g. `4.6W / 180W`)
- Header label: GPU name + driver version

**Page 2 — History chart**
- Rolling line chart (`lv.chart`, LVGL 9.1 — see copilot app's stacked-chart notes for `TYPE.LINE` vs `TYPE.BAR` being per-chart not per-series) of five series, matching knvtop/onvtop (colors and scales): GPU % (#4d9fff), MEM = mem_used/mem_total % (#e8c33a), temp raw 0-100 (#b07fe8), power as % of `power_cap_w` or of 100 W (#3ddc84), host CPU % from `sys.cpu` (#ff8c42), over the last N samples
- 30-sample rolling window, about 150s at the default 5s poll interval (keep the buffer small for the memory-constrained device)
- Y axis 0–100 (every series is a percentage or a 0-100 value, so no dual-axis complexity)

**Page 3 — Details**
- Clocks: graphics/SM (`clock_gfx`) and memory (`clock_mem`), each with their `clock_*_max` as a "/max" suffix
- Fan % `fan_pct` (may read 0 at idle on this card — don't treat 0 as an error state)
- PCIe: `pcie_gen`x`pcie_width` current, with `pcie_gen_max`x`pcie_width_max` as a dimmed "(max ...)" suffix
- Performance state (`pstate`, e.g. `P8`) and `throttle` (scrolling label if non-"None")
- nvstats version/commit + app version/commit, so you can tell what's actually running on both ends

**Page 4 — Processes** (added 2026-07-20, now fed by `gpu_procs`)
- Top processes by GPU memory (`_metrics['processes']`, currently top 4), each rendered as `argv0` / `GPU: x MiB  CPU: y%  PID: z` / one CLI flag+value per line, dashed rule between processes
- ENTER toggles a content-scroll mode: the encoder scrolls the (often long) argument list instead of paging apps; ENTER or ESC exits back to normal paging. Auto-cycle is suppressed while scroll mode is active (see `_process_scroll_mode` guard in `on_running_foreground`) so it can't yank you back to page 0 mid-read.

## Web Settings (config page)

Per `get_settings_json()` convention (no `setup.html`, no manifest `settings:` YAML — see main platform guide):
- `server` (input, default `http://proxmox.home.lan:8039`) — base URL of the nvstats-service instance; no credentials field, this is non-secret telemetry. (No GPU-index setting: the service chooses the GPU.)
- `poll_interval` (input, default `"5"`, seconds) — how often to `GET /api/v1/sample`
- `page_cycle_seconds` (input, default `"5"`) — auto-cycle interval between the 3 pages
- `auto_cycle` (switch, default `true`) — allow disabling auto-cycle for users who just want to leave it on one page

## Device-Side Fetch Pattern

Same shape as the `proxmox` app's `urequests` fetch: minimal headers, `Connection: close`, `timeout=5`, always `resp.close()` in a `finally`, try/except around the fetch setting an error flag the UI renders instead of crashing. A failed poll clears telemetry and graph history; after two consecutive failures, a full-screen black view displays "GPU OFFLINE" and the configured `/api/v1/sample` URL. A successful poll restores the normal pages. Do the first fetch in `on_start()` so pages aren't empty on entry; poll on the configured interval from `on_running_foreground()`, not every 200ms tick.

## nvstats-service status (reference only)

- Code and docs live in https://github.com/DAE51D/nvstats-service (not in this repo; `nvtop-daemon/` was removed on 2026-11-02).
- Deployed on `proxmox.home.lan` (NVIDIA, system unit `nvstats-httpd.service`, runs as `nobody`) and `evo-x2.home.lan` (AMD, user unit `nvstats.service`), both on `:8039`.
- Install/redeploy from a checkout of that repo: `./install.sh --http --bind 0.0.0.0 --port 8039` (desktop host) or `sudo ./install.sh --system --port 8039` (headless). The installer stamps the build commit and removes the legacy `vobot-gpu-daemon`.

## Implementation status

**Current release: v1.1.0 (2026-11-02).** The 4-page cycle, encoder paging, chart rendering, gauges/history/details/processes, and offline behavior have been verified on-device. The offline behavior was tested by stopping and restarting the daemon on `evox2`.

**2026-11-02 nvstats migration (v1.1.0):** replaced `vobot-gpu-daemon` + `/api/gpu-data` with nvstats-service + `/api/v1/sample`; parser reads `gpu`/`gpu_procs`; GPU Index setting removed; verified on-device against both evo-x2 (AMD) and proxmox (NVIDIA).

**2026-07-20 hardening pass:**
- Added a bounded timeout to the daemon fetch after confirming a blocked request can freeze the single-threaded device event loop; the current timeout is 5 seconds. See the `requests.get()` timeout note in `.github/copilot-instructions.md`.
- Fixed a redundant double-fetch on every app entry (`on_start()`'s initial fetch wasn't syncing `_last_fetch_time`, so the next `on_running_foreground()` tick would immediately re-fetch).
- Added `GIT_COMMIT` (stamped at deploy time) shown on the Details page alongside the daemon's own `git_commit` field, so both ends of the pipeline are traceable to a commit.
- `lv_chart`'s built-in `set_div_line_count()` proved unreliable for the 25/50/75% gridlines (only the 50% line rendered) — replaced with explicit 1px `lv.obj` bars drawn as children of the chart at computed pixel offsets.
- Added the Processes page (see Page 4 above) once the daemon grew a process-table endpoint.

**2026-10-16 offline-state update:** Failed polls clear numeric telemetry, process rows, and graph history immediately. After two consecutive failures, the app covers the pages with a black "GPU OFFLINE" view and shows the configured API URL. Fresh data restores the normal page view.

## Open items

- Icon: current `resources/icon.png` is a programmatically generated placeholder (green chip-with-pins glyph, matches the accent color used in the app) — swap for something nicer if desired, not blocking.
- Future, out of scope now: bearer-token support if nvstats is ever run with `NVSTATS_TOKEN`; macOS/Windows ports of the service.
