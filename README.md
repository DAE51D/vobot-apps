# Vobot Apps Monorepo

A collection of custom applications for the Vobot Mini Dock smart display.

## Repository Structure

```
vobot-apps/
├── apps/
│   └── ntfy/           # ntfy notification viewer app
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

See [apps/ntfy/README.md](apps/ntfy/README.md) for details.

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

# Upload app (Windows example)
ampy --port COM4 --baud 115200 --delay 2 put apps/ntfy /apps/ntfy
```

**Using VS Code Pymakr:**

1. Install [Pymakr extension](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr)
2. Connect to ESP32 device
3. Use Pymakr commands to upload files
4. Restart via REPL (Ctrl+D)

### Uninstalling Apps

**Thonny:** View → Files → Right-click app folder → Delete → Ctrl+D

**ampy:** `ampy --port COM4 rmdir /apps/<app_name>`

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
- [Vobot Publishing Guide](https://dock.myvobot.com/developer/guides/publishing-guide/)

## Contributing

This is a personal project repository. Feel free to fork and adapt for your own use or even make a PR if you want to contribute back to this and make it better.

[My Vobot Community Forum Announcement](https://discuss.myvobot.com/t/nfty-app-polls-a-ntfy-server-and-displays-last-n-messages-with-new-ones-surface-to-top-configurable/385)

## License

MIT License - See individual app folders for specific licensing.

---

**Last Updated:** December 13, 2025
