# proxmox App for Vobot Mini Dock

A MicroPython notification viewer for self-hosted proxmox servers.

## Overview

Displays LXC and VM count as well as hardware statistics from an proxmox server on your Vobot Mini Dock. 
Navigate through screens with the rotary wheel.

## Features

- Real-time notification display
- Navigate screens with rotary encoder
- Automatic fetching (every 10 seconds)

## Screenshots

> Note these screenshots will not always be accurate to the current version. Newer displays look nicer IMHO, but I'm too lazy to take more photos and all that jazz just now. I'm too busy getting this app solid. Then I'll align things later as it's stable UI. But you get the idea of what this does.

I want to emulate the PC HW app, but I can't find the source code!
https://discuss.myvobot.com/t/linux-cpu-gpu-temps/351/5

<table>
<tr>
<td width="50%">
<img src="./settings.png" alt="Web configuration page" />
<p align="center"><em>Web Setup Interface</em></p>
</td>
<td width="50%">
<img src="./proxmox_critical_message.jpg" alt="Normal priority message" />
<p align="center"><em>Critical Priority (Red)</em></p>
</td>
</tr>
</table>

## Requirements

- Vobot Mini Dock with Developer Mode enabled
- Self-hosted proxmox server (tested with v2.x)
- WiFi connection

## Quick Start

See the main [repository README](../README.md) for general setup and installation instructions.

### proxmox Server Configuration

Configure via the web interface at http://192.168.1.32/apps/proxmox:

⚠️ **Note**: Developer mode must be enabled for Thonny to access the device filesystem and view debug logs.

## Installation

```powershell
.venv\Scripts\python.exe -m py_compile apps/proxmox/__init__.py

# Push to Vobot (Windows PowerShell example - run from repository root)
# Simple upload (use the `proxmox/apps/proxmox` local path)
Start-Sleep -Seconds 1; & ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put proxmox/apps/proxmox /apps/proxmox
# Force-stop other PowerShell instances then upload (if needed)
Get-Process | Where-Object {$_.Name -eq 'pwsh' -and $_.Id -ne $PID} | Stop-Process -Force; Start-Sleep -Seconds 2; & ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put proxmox/apps/proxmox /apps/proxmox

### Troubleshooting `ampy.exe`
If you encounter "Failed to canonicalize script path" when running the venv `ampy.exe`, prefer the module entrypoint instead:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install --upgrade adafruit-ampy
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put proxmox/apps/proxmox /apps/proxmox
```

Or install `adafruit-ampy` globally and use the `ampy` command from PATH:

```powershell
pip install --user adafruit-ampy
ampy --port COM4 --baud 115200 --delay 2 put proxmox/apps/proxmox /apps/proxmox
```

When in doubt, use Thonny's file view to upload the `proxmox` folder to `/apps/proxmox` — it is the most reliable option on Windows.

## Technical Details

- **Version:** 0.0.1
- **Platform:** ESP32-S3 (MicroPython)
- **UI Framework:** LVGL 8.x
- **Dependencies:** urequests, ujson, utime
- **Default mode:** Long-poll (real-time, stable)
- **Message cache:** Last `MAX_MESSAGES` messages (default 5, 24-hour window)

## Resources

- [Vobot Developer Docs](https://dock.myvobot.com/developer/)
- [Official Vobot Apps](https://github.com/myvobot/dock-mini-apps)
- [LVGL widgets](https://docs.lvgl.io/master/widgets/index.html)

## Authentication

I used this guide to make a token: https://www.home-assistant.io/integrations/proxmoxve/

## License

[baba-yaga](https://github.com/ErikMcClure/bad-licenses/blob/master/baba-yaga)

In other words, YOLO. IDGAF what you do with this. Have fun. Make it better. Make a million dollars off it. Learn something new (as I did). Make the community a better place by contributing to it something for the sad sad "[app store](https://app.myvobot.com/)"

---

- **Version:** 0.0.1
- **Last Updated:** December 14, 2025