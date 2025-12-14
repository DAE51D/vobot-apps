# ntfy App for Vobot Mini Dock

A MicroPython notification viewer for self-hosted ntfy servers.

## Overview

Displays push notifications from an ntfy server on your Vobot Mini Dock. Navigate through messages with the rotary encoder and stay updated on alerts, reminders, and notifications.

## Features

- 📬 Real-time notification display
- 🎡 Navigate messages with rotary encoder
- 🔢 Message counter (e.g., "2/5")
- 📅 Timestamped messages (MM/DD HH:MM)
- 🔄 Automatic fetching (every 30 seconds)
- 💾 Caches last 5 messages

## Requirements

- Vobot Mini Dock with Developer Mode enabled
- Self-hosted ntfy server (tested with v2.x)
- WiFi connection

## Quick Start

See the main [repository README](../../README.md) for general setup and installation instructions.

### ntfy Server Configuration

This app connects to: `http://ntfy.home.lan/general`

To change the server or topic, edit `__init__.py`:

```python
NTFY_SERVER = "http://your-ntfy-server"
NTFY_TOPIC = "your-topic"
```

**Future:** Web-based settings UI coming soon!

To return to normal operation:

1. Navigate back to **Settings → Miscellaneous → Experimental Features**
2. Disable **Developer Mode**
3. Power cycle the device (disconnect and reconnect power)

⚠️ **Note**: Developer mode must be enabled for Thonny to access the device filesystem and view debug logs.

## Installation


## Usage

### Controls

| Action | Function |
|--------|----------|
| Rotate counter-clockwise | View newer message |
| Rotate clockwise | View older message |
| Press ESC | Exit to app menu |

### Display

- **Line 1:** Topic name (`ntfy: general`)
- **Line 2:** Status (OK/ERR) and counter (`2/5`)
- **Line 3+:** Message number, timestamp, and content

Example:
```
ntfy: general
OK                    2/5

#2 [12/13 14:35]
Server backup completed
```

## Testing

Send test notifications:

```bash
# Simple message
curl -d "Hello Vobot!" http://ntfy.home.lan/general

# With title
curl -H "Title: Alert" -d "Disk space low" http://ntfy.home.lan/general
```

## Troubleshooting

### No messages appear
- Check WiFi: Vobot must be connected
- Verify ntfy server is accessible: `ping ntfy.home.lan`
- Check logs for errors (see main README)

### Scroll wheel doesn't work
- Ensure app is focused (launch from menu)
- Check that focus group is set up (see code)

### App crashes
- Check memory usage (reduce message cache if needed)
- Review device logs for errors

## Technical Details

- **Version:** 0.0.2
- **Platform:** ESP32-S3 (MicroPython)
- **UI Framework:** LVGL 8.x
- **Dependencies:** urequests, ujson, utime
- **Fetch interval:** 30 seconds
- **Message cache:** Last 5 messages (24 hours)

## Resources

- [ntfy Documentation](https://docs.ntfy.sh/)
- [Vobot Developer Docs](https://dock.myvobot.com/developer/)
- [Official Vobot Apps](https://github.com/myvobot/dock-mini-apps)

---

**Version:** 0.0.2  
**Last Updated:** December 13, 2025
