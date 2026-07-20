---
description: "Vobot GPU Monitor App: Build/update the 'nvtop' Vobot Mini Dock app that shows live NVIDIA GPU stats (util/mem/temp/power/clocks) by polling our own vobot-gpu-daemon REST API. Use when: building or refining the nvtop app screens, wiring the daemon fetch, tuning arc/chart ranges, or debugging the device-side fetch."
agent: 'agent'
tools: ['search/changes', 'search', 'edit/editFiles', 'execute/runInTerminal']
context: |
  - Vobot platform conventions: see .github/copilot-instructions.md (lifecycle, LVGL, web settings, upload/debug workflow)
  - Reference apps for patterns: proxmox/apps/proxmox/__init__.py (arc gauges, encoder handling), ntfy/apps/ntfy/__init__.py (page caching via HIDDEN flag instead of rebuild), copilot/apps/copilot/__init__.py (stacked lv.chart bar+line pattern)
  - Our own daemon (built and deployed 2026-07-19): D:\daevid\Code\Vobot\nvtop-daemon\vobot_gpu_daemon.py + vobot-gpu-daemon.service, running on the Proxmox host at http://proxmox.home.lan:8039/api/gpu-data
  - Daemon README (deploy steps): D:\daevid\Code\Vobot\nvtop-daemon\README.md
  - gpu-hot project (reference/inspiration only, not a dependency): https://github.com/psalias2006/gpu-hot
  - App source (built 2026-07-19, deployed and actively tested on-device, v1.0.3 as of 2026-07-20): D:\daevid\Code\Vobot\nvtop\apps\nvtop\__init__.py
  - App manifest: D:\daevid\Code\Vobot\nvtop\apps\nvtop\manifest.yml
  - App icon (generated placeholder, 48x48 PNG): D:\daevid\Code\Vobot\nvtop\apps\nvtop\resources\icon.png
---

# nvtop / GPU Monitor App — Vobot Mini Dock

## Role

You are an expert MicroPython/LVGL developer building Vobot Mini Dock apps (see `.github/copilot-instructions.md` for the full platform guide). This prompt is scoped to the **`nvtop` app**: an on-device live monitor for an NVIDIA GPU, modeled visually on `nvtop`'s terminal UI, sourced from our own small daemon's REST API — no on-device `nvtop`/`nvidia-smi` execution.

## Feasibility & architecture — resolved

The original open question was "do we need a small Linux service the Vobot reads from?" **Yes — and it's built and already running.** Don't rely on `gpu-hot` (`komodo.home.lan:1312`) as the data source: it was only an example of "how do you read this data at all," and it's an optional third-party stack most users of this app won't have installed. Instead we built and deployed **our own daemon**, `vobot-gpu-daemon`, so the app works for anyone with an NVIDIA GPU + this daemon, independent of any other dashboard.

- **`nvtop-daemon/vobot_gpu_daemon.py`** — stdlib-only Python 3 HTTP server (`http.server`), no pip installs required. Shells out to `nvidia-smi --query-gpu=...` (CSV output) on whatever host it runs on, serves `GET /api/gpu-data` and `GET /health` on port `8039`.
- Response schema **intentionally mirrors gpu-hot's** `/api/gpu-data` shape (`{"gpus": {"<index>": {...}}, "timestamp": ...}` with the same field names: `temperature`, `utilization`, `memory_utilization`, `memory_used/total/free`, `power_draw/limit`, `fan_speed`, `clock_graphics/sm/memory` + `clock_max_*`, `pcie_gen/width` + `_max`, `performance_state`, `throttle_reasons`) — so the on-device parser is backend-agnostic; the app's `server` setting can point at our daemon or a gpu-hot instance interchangeably.
- **Deployed 2026-07-19 on the Proxmox host itself** (bare metal, `proxmox.home.lan:8039`) — that's the box directly attached to the GPU (`NVIDIA GeForce RTX 5060 Ti`, `GPU-2bb45349-6461-e802-99c1-098bae63ad20`), and the simplest/closest-to-hardware place to run it. Installed as a systemd service (`vobot-gpu-daemon.service`, `enabled --now`), runs as `nobody` (verified `/dev/nvidia*` is world read/write on this host, no elevated privileges needed), auto-restarts on failure. Verified live: `curl http://proxmox.home.lan:8039/api/gpu-data` returns real GPU telemetry.
- **Architecture is host-agnostic on purpose.** The daemon makes no assumption about being bare metal — it just calls whatever `nvidia-smi` resolves to locally, so the identical script would work unmodified in an LXC/VM with GPU passthrough (that's literally how `gpu-hot` does it in the `komodo` container) or on another physical Linux box. This matters because **not every future user of the Vobot app will have a bare-metal Proxmox+GPU box** — the daemon needs to run wherever *their* GPU actually lives.
- **Out of scope for now, noted for later**: macOS and Windows 11 equivalents of this daemon (different data source than `nvidia-smi` — `powermetrics`/IOKit on macOS, `nvidia-smi.exe` or WMI on Windows). Don't build these yet; just don't paint the on-device app or the JSON schema into a Linux-only corner if it's easy to avoid.
- **Process table: implemented (2026-07-20).** Originally left out (see history below), but we added it: the daemon's `query_processes()` shells out to `nvidia-smi --query-compute-apps=...` for `gpu_uuid,pid,process_name,used_memory`, then `ps -p <pids> -o pid=,%cpu=,rss=,comm=,args=` once for CPU%/full-command, and returns a `processes` dict (keyed by GPU index, same shape as `gpus`) alongside the `gpus` dict in `/api/gpu-data`. The app's Page 4 (Processes) renders the top 4 by GPU memory, each as `argv0` / `GPU/CPU/PID` / one CLI flag+value per line, with its own encoder-scroll mode (ENTER toggles; see `_process_scroll_mode` in `__init__.py`).

## Live response shape (`GET http://proxmox.home.lan:8039/api/gpu-data`)

Captured live from our running daemon on 2026-07-19:

```json
{
  "gpus": {
    "0": {
      "index": "0",
      "name": "NVIDIA GeForce RTX 5060 Ti",
      "uuid": "GPU-2bb45349-6461-e802-99c1-098bae63ad20",
      "driver_version": "595.71.05",
      "temperature": 33.0,
      "utilization": 0.0,
      "memory_utilization": 40.0,
      "memory_used": 5478.0,
      "memory_total": 16311.0,
      "memory_free": 10365.0,
      "power_draw": 4.41,
      "power_limit": 180.0,
      "fan_speed": 0.0,
      "clock_graphics": 210.0,
      "clock_sm": 210.0,
      "clock_memory": 405.0,
      "clock_max_graphics": 3120.0,
      "clock_max_sm": 3120.0,
      "clock_max_memory": 14001.0,
      "pcie_gen": "1",
      "pcie_gen_max": "3",
      "pcie_width": "8",
      "pcie_width_max": "16",
      "performance_state": "P8",
      "throttle_reasons": "None",
      "timestamp": "2026-07-19T19:35:00"
    }
  },
  "timestamp": 1784514900.5278919
}
```

Notes for parsing on-device:
- `gpus` is a dict keyed by GPU index as a **string** (`"0"`), not a list — iterate `.keys()` / take the first entry. Multi-GPU hosts would add more keys; this host only has one, but don't hardcode `gpus["0"]` without a fallback in case indexing ever shifts (read `gpu_index` from settings, default `"0"`).
- Any field can come back `null` (our daemon maps N/A → `None` → JSON `null`, e.g. `fan_speed` on cards without a controllable fan) — treat every field as optional and default missing/null values sensibly rather than erroring.
- `pcie_gen`/`pcie_width` are strings, not numbers — format directly, don't cast blindly.
- `throttle_reasons` is a human string (`"None"` when healthy, comma-joined reason names otherwise) — can be long when multiple reasons are active; truncate or scroll it.
- No `encoder_sessions`/`decoder_sessions` fields — deliberately left out of our daemon's schema (see architecture note above), don't reference them.

## Goal — app structure

A 4-page app (scroll wheel cycles pages manually; Gauges/History also auto-cycle every 5s like the reference `nvtop` capture unless the user is actively scrolling — reset the auto-cycle timer on manual input so it doesn't fight the user; Details/Processes are manual-only detours that auto-cycle resumes from once you leave them — see `AUTO_CYCLE_PAGES` vs `NUM_PAGES`). `CAN_BE_AUTO_SWITCHED = True` for the dock's own app-rotation (separate concept from this in-app page auto-cycle — don't conflate the two timers).

**Page 1 — Gauges (live snapshot)**
- Arc: GPU utilization % (reuse proxmox app's arc pattern: rotation 270, bg angle 0–360, hidden knob)
- Arc or bar: memory utilization % with `memory_used`/`memory_total` as a sub-label (e.g. `5.3G/15.9G`)
- Arc: temperature (color the arc red past ~80°C the way the dashboard highlights hot temps)
- Bar: power draw vs `power_limit` (e.g. `4.6W / 180W`)
- Header label: GPU name + driver version

**Page 2 — History chart**
- Rolling line chart (`lv.chart`, LVGL 9.1 — see copilot app's stacked-chart notes for `TYPE.LINE` vs `TYPE.BAR` being per-chart not per-series) of GPU utilization % and memory utilization % over the last N samples
- Match the reference nvtop capture's ~60s rolling window: buffer size = `60s / poll_interval`, default poll 2s → 30 points (tune once battery/network impact on-device is observed; keep buffer small, this is a memory-constrained device)
- Y axis 0–100 (both series are already percentages, so no dual-axis complexity needed here — simpler than the copilot app's bar+line overlay)

**Page 3 — Details**
- Clocks: graphics/SM (`clock_graphics`/`clock_sm`) and memory (`clock_memory`), each with their `clock_max_*` as a "/max" suffix
- Fan speed % (may read 0 at idle on this card — don't treat 0 as an error state)
- PCIe: `pcie_gen`x`pcie_width` current, with `pcie_gen_max`x`pcie_width_max` as a dimmed "(max ...)" suffix
- Performance state (`performance_state`, e.g. `P8`) and `throttle_reasons` (scrolling label if non-"None")
- Daemon commit + app version/commit, so you can tell what's actually running on both ends

**Page 4 — Processes** (added 2026-07-20, once the daemon grew a process-table endpoint — see the architecture note above)
- Top processes by GPU memory (`_metrics['processes']`, currently top 4), each rendered as `argv0` / `GPU: x MiB  CPU: y%  PID: z` / one CLI flag+value per line, dashed rule between processes
- ENTER toggles a content-scroll mode: the encoder scrolls the (often long) argument list instead of paging apps; ENTER or ESC exits back to normal paging. Auto-cycle is suppressed while scroll mode is active (see `_process_scroll_mode` guard in `on_running_foreground`) so it can't yank you back to page 0 mid-read.

## Web Settings (config page)

Per `get_settings_json()` convention (no `setup.html`, no manifest `settings:` YAML — see main platform guide):
- `server` (input, default `http://proxmox.home.lan:8039`) — base URL of the `vobot-gpu-daemon` instance; no credentials field, this is non-secret telemetry (also works pointed at a gpu-hot instance, since the schema matches)
- `gpu_index` (input, default `"0"`) — which key to read out of the `gpus` dict, for future multi-GPU hosts
- `poll_interval` (input, default `"2"`, seconds) — how often to `GET /api/gpu-data`
- `page_cycle_seconds` (input, default `"5"`) — auto-cycle interval between the 3 pages
- `auto_cycle` (switch, default `true`) — allow disabling auto-cycle for users who just want to leave it on one page

## Device-Side Fetch Pattern

Same shape as the `proxmox` app's `urequests` fetch: minimal headers, `Connection: close`, always `resp.close()` in a `finally`, try/except around the fetch setting an error flag the UI renders instead of crashing (e.g. "GPU offline" if the daemon host is unreachable — network hiccup, host rebooting, or the systemd service down independent of the GPU itself). Do the first fetch in `on_start()` so pages aren't empty on entry; poll on the configured interval from `on_running_foreground()`, not every 200ms tick.

## Daemon status (already done, reference only)

- Code lives in this repo at `nvtop-daemon/` (`vobot_gpu_daemon.py`, `vobot-gpu-daemon.service`, `README.md` with redeploy steps).
- Deployed and running on `proxmox.home.lan` as systemd unit `vobot-gpu-daemon.service` (`enabled`, auto-restart on failure), listening on `:8039`, running as `nobody`.
- Redeploy after script changes: `scp nvtop-daemon/vobot_gpu_daemon.py root@proxmox:/opt/vobot-gpu-daemon/ && ssh root@proxmox systemctl restart vobot-gpu-daemon`.

## Implementation status

**Built 2026-07-19, stable and released as v1.0.0.** Extensively verified on-device since (v1.0.0 → v1.0.3 as of 2026-07-20): 4-page cycle including the new Processes page, encoder paging, the offline indicator, `lv.chart` line-series rendering, gauges/history/details/processes all confirmed live against real GPU load (not just near-idle numbers).

**2026-07-20 hardening pass:**
- Added `timeout=10` to the daemon fetch — its absence was traced (via live serial `Ctrl+C` during a device-wide freeze) to being able to hang the *entire* device indefinitely, not just this app, since MicroPython's event loop is single-threaded. See the `requests.get()` timeout note in `.github/copilot-instructions.md`.
- Fixed a redundant double-fetch on every app entry (`on_start()`'s initial fetch wasn't syncing `_last_fetch_time`, so the next `on_running_foreground()` tick would immediately re-fetch).
- Added `GIT_COMMIT` (stamped at deploy time) shown on the Details page alongside the daemon's own `git_commit` field, so both ends of the pipeline are traceable to a commit.
- `lv_chart`'s built-in `set_div_line_count()` proved unreliable for the 25/50/75% gridlines (only the 50% line rendered) — replaced with explicit 1px `lv.obj` bars drawn as children of the chart at computed pixel offsets.
- Added the Processes page (see Page 4 above) once the daemon grew a process-table endpoint.

## Open items

- Icon: current `resources/icon.png` is a programmatically generated placeholder (green chip-with-pins glyph, matches the accent color used in the app) — swap for something nicer if desired, not blocking.
- Future, explicitly out of scope now: macOS/Windows 11 ports of the daemon for non-Proxmox users.
- Not yet committed to git as of 2026-07-20 (device testing is ongoing, per repo convention of not committing until confirmed working) — commit once the user gives the go-ahead.
