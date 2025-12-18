# Vobot Apps Monorepo

A collection of custom applications for the Vobot Mini Dock smart display.

# What's a Vobot

Basically it's this sweet little computer dock (you know with all kinds of extra ports) that you can get for about [$50 on Amazon](https://www.amazon.com/dp/B0FF4KK446) but it has a display and a wheel that you can then install apps from their store (it's pretty sparse TBH). But the real reason I got it is so that *I* can write apps myself for it. Please to enjoy...

## Repository Structure

```
vobot-apps/
├── ntfy/                    # ntfy project folder
│   ├── apps/
│   │   └── ntfy/           # app package for device
│   └── *.jpg               # screenshots
├── proxmox/                 # Proxmox dashboard project folder
│   ├── apps/
│   │   └── proxmox/        # app package for device
│   └── *.jpg               # screenshots
├── .venv/                   # workspace-level Python venv
├── .github/
│   ├── copilot-instructions.md
│   └── prompts/
└── README.md
```

## Apps

### ntfy

A notification viewer for self-hosted ntfy servers. Displays push notifications with message navigation via rotary encoder.

**Features:**
- Real-time notification display
- Message navigation with scroll wheel
- Message counter (1/5 display)
- Automatic periodic fetching
- Timestamped messages

**Status:** 🚧 In Development (v0.0.2)

See [ntfy/apps/ntfy/README.md](ntfy/README.md) for details.

### proxmox

A two-page Proxmox dashboard showing CPU/RAM arcs, network in/out bars with arrows, and VM/LXC counts; includes a text debug page (uptime, swap, disk, metrics).

**Features:**
- Rotary wheel navigation between dashboard and debug pages
- CPU/RAM arc gauges; network KB/s bars; VM/LXC bars
- Polls Proxmox every 10 seconds; shows uptime/swap/disk on debug page

**Status:** 🚧 In Development (v0.0.9)

See [proxmox/README.md](proxmox/README.md) for details.

## Vobot Mini Dock Platform

### Overview

- **Hardware:** ESP32-S3 with rotary encoder, buttons, and 320x240 display
- **Software:** MicroPython with LVGL UI framework
- **Resources:** 200KB per app, 900KB total app storage

### Development Requirements

#### Hardware
- Vobot Mini Dock device
- USB-C data cable (not charge-only)
- Computer (Windows/Linux/macOS)
- Connect via the USB-C on the right side of the device (literally named "computer")

#### Software
- [Thonny IDE](https://thonny.org/) (recommended) or VS Code with [ampy](https://github.com/scientifichackers/ampy)
- [ampy](https://github.com/scientifichackers/ampy) for command-line uploads
- Python 3.7+ for development tools

### Developer Mode

To install custom apps, enable Developer Mode:

1. On Vobot: **Settings → Miscellaneous → Experimental Features → Developer Mode**
2. Power cycle the device (disconnect and reconnect power)
3. Developer mode is now active

### Installing Apps

**Using Thonny (Easiest):**

1. Connect Vobot via USB-C cable
2. Open Thonny → Select ESP32 port
3. View → Files → Navigate to `/apps`
4. Upload app folder to `/apps/<app_name>/`
5. Press Ctrl+D to restart

**Using ampy (Command Line):**

```powershell
# Install ampy
pip install adafruit-ampy

# Upload app (Windows PowerShell example - run from repository root)
# Prefer module invocation to avoid Windows EXE shim issues
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put ntfy/apps/ntfy /apps/ntfy
```

**Using VS Code Pymakr:**

1. Install [Pymakr extension](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr)
2. Connect to ESP32 device
3. Use Pymakr commands to upload files
4. Restart via REPL (Ctrl+D)

### Uninstalling Apps

**Thonny:** View → Files → Right-click app folder → Delete → Ctrl+D

**ampy:** `& ".\.venv\Scripts\ampy.exe" --port COM4 rmdir /apps/<app_name>`

If `ampy.exe` returns "Failed to canonicalize script path", use the module entrypoint instead (recommended):

```powershell
& ".\.venv\Scripts\python.exe" -m pip install --upgrade adafruit-ampy
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 2 put ntfy/apps/ntfy /apps/ntfy
```

### Debugging

**Real-time logs (PowerShell):**

```powershell
$port = New-Object System.IO.Ports.SerialPort COM4, 115200, None, 8, One
$port.Open()
Write-Host "Monitoring COM4"
while($port.IsOpen) { 
    try { 
        $byte = $port.ReadChar()
        [Console]::Write([char]$byte)
    } catch { 
        Start-Sleep -Milliseconds 100 
    } 
}
```

**Thonny logs:** View Shell window for real-time output

### Common Issues

**Can't connect to device:**
- Check USB cable is data-capable (not charge-only)
- Verify correct serial port (Device Manager on Windows)
- Close other programs using the port
- Try different USB port

**App doesn't appear:**
- Ensure Developer Mode is enabled
- Verify app is in `/apps/<app_name>/` (not nested)
- Restart device (Ctrl+D)

**App crashes:**
- Check memory usage (MicroPython has limited RAM)
- Review logs for error messages
- Ensure proper cleanup in `on_stop()` method

## Resources

- [Vobot Developer Documentation](https://dock.myvobot.com/developer/)
- [LVGL Documentation](https://docs.lvgl.io/)
- [MicroPython Documentation](https://docs.micropython.org/)
- [Official Vobot Apps Repository](https://github.com/myvobot/dock-mini-apps)
- [User Forum](https://discuss.myvobot.com/)
- [Vobot Mini Dock Simulator](https://dock.myvobot.com/developer/mini_dock_emulator/)

## Publishing

- [Vobot Publishing Guide](https://dock.myvobot.com/developer/guides/publishing-guide/)

Use the `dock-app-bundler-win.exe` and choose `D:\daevid\Code\Vobot\ntfy\apps\ntfy` it will bundle up a `ntfy.vbt` file, 
save it in the parent folder: `D:\daevid\Code\Vobot\ntfy\apps`

Login to https://app.myvobot.com/profile 

## Contributing

This is a personal project repository. Feel free to fork and adapt for your own use or even make a PR if you want to contribute back to this and make it better.

[My Vobot Community Forum Announcement](https://discuss.myvobot.com/t/nfty-app-polls-a-ntfy-server-and-displays-last-n-messages-with-new-ones-surface-to-top-configurable/385)

## Git 

This is for my own note to append to the last commit. Useful for minor changes I don't want to clutter up my history with...
```
git add -u
git commit --amend --no-edit
git push origin master:main --force
git status
```

---

**Last Updated:** December 13, 2025
