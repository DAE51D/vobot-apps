# nvtop App for Vobot Mini Dock

A MicroPython GPU monitor for the Vobot Mini Dock.

## Overview

`nvtop` shows live GPU telemetry from [nvstats-service](https://github.com/DAE51D/nvstats-service), a small HTTP service running on the machine that actually has the GPU (NVIDIA via `nvidia-smi`, AMD via sysfs/`amd-smi`).

The app currently provides a 4-page UI:

- Gauges page with GPU, memory, temperature, and power/memory bars
- History page with GPU, memory, temperature, power, and CPU trend lines (same five lines and colors as knvtop and onvtop) plus 25/50/75% gridlines (30 samples, about 150 seconds at the default poll interval)
- Details page with clocks, PCIe info, performance state, throttle reasons, and nvstats/app build info
- Processes page listing the top GPU-memory processes, with full command-line args and its own encoder-driven scroll mode

Gauges/History auto-cycle between themselves; Details/Processes are manual-only detours (auto-cycle resumes once you leave them). All pages can also be changed directly with the Vobot rotary encoder.

## Features

- Live GPU utilization gauge
- Live VRAM utilization gauge
- Temperature gauge with hot-state color change
- Power draw bar and memory usage bar
- Rolling history chart for GPU %, memory %, temperature, power (% of cap), and host CPU %, with 25/50/75% gridlines and a 0%/100% border
- Details page with clocks, PCIe link, P-state, throttle reason text, and the service's + app's git commit (so you always know what's actually running)
- Processes page: top GPU-memory processes, each showing `argv0`, `GPU/CPU/PID`, and every CLI flag on its own line, separated by a rule; press **ENTER** to toggle a content-scroll mode where the encoder scrolls the list instead of paging apps (press **ENTER** or **ESC** to exit back to normal paging)
- Configurable polling interval and page auto-cycle
- Multi-GPU hosts: the service reports GPU 0 by default; pick another with `NVSTATS_GPU_INDEX` in the service config
- Failed polls clear stale readings and graph history; after two consecutive failures, a full-screen offline view shows the configured API URL
- All `requests.get()` calls use a 5-second timeout — a slow/unreachable service can't freeze the whole device indefinitely

## Screenshots

<table>
<tr>
    <td width="33%">
        <img src="./config.png" alt="nvtop configuration page" />
        <p align="center"><em>Web Setup Interface</em></p>
    </td>
    <td width="33%">
        <img src="./quadrants.jpg" alt="Quadrants" />
        <p align="center"><em>Quadrants</em></p>
    </td>
    <td width="33%">
        <img src="./gpu_mem_graph.jpg" alt="Graph" />
        <p align="center"><em>GPU MEM graph</em></p>
    </td>
</tr>
</table>

## Requirements

- Vobot Mini Dock with Developer Mode enabled
- WiFi connection
- A supported GPU host reachable on your LAN
- `nvstats-service` running on that host with its HTTP API enabled

## Quick Start

See the main [repository README](../README.md) for general Vobot setup and upload instructions.

### nvstats-service Requirement

This app does not query the GPU itself. It reads JSON from [nvstats-service](https://github.com/DAE51D/nvstats-service) running on your PC, server, or Proxmox host. The same service also feeds the knvtop and onvtop clients.

Default endpoint:

```text
http://proxmox.home.lan:8039/api/v1/sample
```

Install on the GPU host (see the nvstats-service README for details):

```bash
# desktop host (also serves D-Bus clients)
./install.sh --http --bind 0.0.0.0 --port 8039
# headless host
sudo ./install.sh --system --port 8039
```

The response is a compact payload (GPU stats + top 5 processes, about 1-3 KB) sized for the dock's small RAM. If you used the old `vobot-gpu-daemon`, running the nvstats installer removes it.

## Configuration

Configure via the Vobot web UI at:

```text
http://192.168.1.32/apps/nvtop
```

Settings:

- **nvstats Server:** Base URL of nvstats-service, for example `http://proxmox.home.lan:8039`
- **Poll Interval:** Fetch interval in seconds, default `5`
- **Page Cycle Seconds:** Auto-cycle interval between pages, default `5`
- **Auto-Cycle Pages:** Enable or disable automatic page rotation

## Installation

```powershell
.venv\Scripts\python.exe -m py_compile nvtop/apps/nvtop/__init__.py

# Push to Vobot (Windows PowerShell example - run from repository root)
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put nvtop/apps/nvtop /apps/nvtop
```

If `ampy.exe` gives you Windows path weirdness, prefer the module entrypoint:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install --upgrade adafruit-ampy
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put nvtop/apps/nvtop /apps/nvtop
```

When in doubt, Thonny file upload is still the least annoying option on Windows.

## Usage

### Controls


| Action                               | Function                                                  |
| -------------------------------------- | ----------------------------------------------------------- |
| Rotate clockwise / counter-clockwise | Change pages (or scroll the process list, in scroll mode) |
| Wait                                 | Auto-cycle between Gauges/History if enabled              |
| Press ENTER (on Processes page)      | Toggle content-scroll mode                                |
| Press ENTER or ESC (in scroll mode)  | Exit scroll mode, back to normal page navigation          |
| Press ESC (not in scroll mode)       | Exit app                                                  |

### Pages

#### Gauges

- GPU utilization arc
- Memory utilization arc
- Temperature arc
- Power draw bar
- Memory usage bar (`used / total`)

#### History

- GPU percent trend line
- Memory-used percent, temperature (0-100 °C), power (% of cap) and host CPU percent trend lines
- 25/50/75% horizontal gridlines, 0%/100% framed by the chart border

#### Details

- GPU name and driver version
- Graphics and memory clocks
- Fan percent
- PCIe current and max link
- Performance state
- Throttle reasons
- nvstats version/commit + app version/commit

#### Processes

- Top GPU-memory processes (by default the top 4), each rendered as:
  ```
  /opt/llama-cpp/bin/llama-server
  GPU: 5460 MiB   CPU: 1%   PID: 3237629
  --foo bar
  --fee fum
  ```

  (argv0, then a summary line, then every CLI flag with its value on its own line)
- A dashed rule separates consecutive processes
- Press **ENTER** to enter scroll mode (header turns blue, "ENTER/ESC to exit") — the encoder then scrolls the list instead of changing pages, so long argument lists are fully readable

## Troubleshooting

### App opens but shows no data

- Verify the GPU host and nvstats-service are up
- Check the configured server URL
- Test the endpoint from another machine:

```bash
curl http://proxmox.home.lan:8039/api/v1/sample
```

### App shows GPU OFFLINE

- The app clears telemetry after a failed poll and shows the full-screen offline view after two consecutive failures
- Check that the configured server's `/api/v1/sample` endpoint is reachable and nvstats-service is running (a 404 means the host still runs the old `vobot-gpu-daemon`)
- The offline view displays the configured endpoint; fresh telemetry restores the normal pages

### App does not appear in Vobot

- Confirm the folder exists at `/apps/nvtop`
- Restart the device after upload
- Make sure `manifest.yml` and `__init__.py` are present

### Scroll wheel does nothing

- Re-open the app from the app list
- If it still ignores input, restart the dock and re-enter the app

### COM4 / upload errors

- Close Thonny, serial monitors, and any other process using the port
- Retry the `ampy` command

## Technical Details

- **Version:** 1.2.0
- **Platform:** ESP32-S3 (MicroPython)
- **UI Framework:** LVGL
- **Dependencies:** `urequests`, `utime`, `lvgl`, `peripherals`
- **Backend:** JSON API from nvstats-service (`/api/v1/sample`)
- **Build tracking:** `GIT_COMMIT` is stamped at deploy time from `git rev-parse --short HEAD` and shown on the Details page next to the service's own commit

## Resources

- [Vobot Developer Docs](https://dock.myvobot.com/developer/)
- [LVGL Docs](https://docs.lvgl.io/)
- [Official Vobot Apps](https://github.com/myvobot/dock-mini-apps)
- [gpu-hot](https://github.com/psalias2006/gpu-hot) for inspiration only

## License

[baba-yaga](https://github.com/ErikMcClure/bad-licenses/blob/master/baba-yaga)

In other words, YOLO. Use it, change it, break it, improve it.
