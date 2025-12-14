# ntfy Client for Vobot Mini Dock

A MicroPython application for Vobot Mini Dock that displays notifications from a self-hosted ntfy server.

## Overview

This app connects to an ntfy server and displays push notifications on the Vobot Mini Dock display. Navigate through messages using the rotary encoder (scroll wheel) and view message details including title, body, timestamp, and priority.

## Features

- 📬 Subscribe to ntfy notification channels
- 🔄 Automatic periodic message fetching
- 📱 Display message title, body, and metadata
- 🎡 Navigate through messages with scroll wheel
- 🔢 Show message counter (current/total)
- 💾 Cache recent messages locally
- 🔄 Manual refresh on button press

## Prerequisites

- Vobot Mini Dock device
- USB-C data cable
- Code editor (VS Code, Thonny, or any text editor)
- Tool for file transfer to device:
  - [Thonny IDE](https://thonny.org/) (officially recommended, easiest option)
  - OR [ampy](https://github.com/scientifichackers/ampy) command-line tool
  - OR VS Code with [Pymakr extension](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr)
- Self-hosted ntfy server (http://ntfy.home.lan/)
- Vobot connected to WiFi network

## Developer Mode Setup

### Enabling Developer Mode

To install and test custom applications, you must enable Developer Mode on your Vobot Mini Dock:

1. **On the Vobot Mini Dock device**:
   - Navigate to **Settings**
   - Select **Miscellaneous**
   - Choose **Experimental Features**
   - Enable **Developer Mode**

2. **Power cycle the device**:
   - Disconnect the Vobot from its power source
   - Wait a few seconds
   - Reconnect the power cable
   - Developer mode will now be active

### Disabling Developer Mode

To return to normal operation:

1. Navigate back to **Settings → Miscellaneous → Experimental Features**
2. Disable **Developer Mode**
3. Power cycle the device (disconnect and reconnect power)

⚠️ **Note**: Developer mode must be enabled for Thonny to access the device filesystem and view debug logs.

## Installation

### Method 1: Using Thonny (Recommended)

#### 1. Connect to Vobot Mini Dock

1. Ensure Developer Mode is enabled (see above)
2. Connect Vobot to your computer using a USB-C cable
3. Open Thonny IDE
4. Select the ESP32 port from the port dropdown (bottom-right corner)

#### 2. Upload the App

1. In Thonny, click **View → Files** to open the file browser
2. In the device filesystem (right panel), navigate to the `/apps` folder
3. In your local filesystem (left panel), navigate to this project folder
4. Right-click the `ntfy` folder → **Upload to /apps**
5. Wait for upload to complete

#### 3. Restart the Device

1. In Thonny's Shell, press **Ctrl+D** on your keyboard
2. The device will restart and load the new app
3. The ntfy app should now appear in your apps list

### Method 2: Using VS Code with Pymakr

1. Install the [Pymakr extension](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr) in VS Code
2. Connect Vobot via USB-C cable (Developer Mode enabled)
3. Open this project folder in VS Code
4. Configure Pymakr to connect to the ESP32 device
5. Use Pymakr commands to upload files to `/apps/ntfy/`
6. Restart the device using Pymakr's REPL

### Method 3: Using ampy (Command Line)

```bash
# Install ampy
pip install adafruit-ampy

# Find your device port (Windows: COM3, Linux/Mac: /dev/ttyUSB0)
# Upload app folder
ampy --port COM3 put ntfy /apps/ntfy

# Connect to device and restart
# Use screen/putty/minicom to connect and press Ctrl+D
```

## Uninstalling the App

**Using Thonny:**
1. Connect to Vobot via Thonny (Developer Mode enabled)
2. Click **View → Files**
3. Navigate to `/apps/ntfy/` on the device
4. Right-click the `ntfy` folder → **Delete**
5. Press **Ctrl+D** to restart

**Using ampy:**
```bash
ampy --port COM3 rmdir /apps/ntfy
```

**Using Pymakr in VS Code:**
1. Use Pymakr file browser to navigate to `/apps/ntfy/`
2. Delete the folder
3. Restart device via REPL (Ctrl+D)

## Usage

### Launching the App

1. From the Vobot home screen, scroll to the ntfy app
2. Press the encoder to launch

### Controls

| Action | Button/Encoder | Function |
|--------|---------------|----------|
| Scroll Up | Rotate counter-clockwise | View previous message |
| Scroll Down | Rotate clockwise | View next message |
| Press | Press encoder | Refresh messages |
| Exit | Press ESC button | Return to app menu |

### Display Information

The app displays:
- **Topic name**: Which ntfy channel is being monitored
- **Message counter**: Current message number / Total messages (e.g., "2/5")
- **Message title**: Title of the notification (if provided)
- **Message body**: Main notification content
- **Timestamp**: When the message was sent
- **Priority**: Visual indicator for message priority (optional)

### No Messages

If no messages are available, the display shows:
```
ntfy: general
0/0
No messages
Waiting for notifications...
```

## Configuration

### ntfy Server Settings (Web UI)

The app now includes a settings interface accessible via the Vobot web portal at **http://192.168.1.32/apps**:

1. Open http://192.168.1.32/apps on your computer or phone
2. Find the "ntfy" app in the list
3. Click the settings gear icon to configure:
   - **ntfy Server URL**: Full URL to your ntfy server (e.g., `http://ntfy.home.lan` or `http://192.168.1.100`)
   - **ntfy Topic**: Topic name to subscribe to (e.g., `general`, `alerts`, `notifications`)
   - **Fetch Interval**: How often to check for new messages (5-300 seconds)
   - **Max Cached Messages**: Maximum number of messages to keep in memory (5-100)

Settings are saved persistently and apply immediately.

### Manual Configuration (Advanced)

To change settings manually, edit `ntfy/__init__.py`:

```python
NTFY_SERVER = "http://ntfy.home.lan"
NTFY_TOPIC = "general"
FETCH_INTERVAL = 30  # seconds
MAX_MESSAGES = 20    # message cache limit
```

Then re-upload the app using ampy or Thonny.

## Development

### Project Structure:

**Using Thonny:**
1. View real-time logs in the Thonny Shell window
2. Use `print()` statements in your code for debugging
3. Device errors will appear in the log output
4. Press **Ctrl+C** to stop execution
5. Press **Ctrl+D** to restart

**Using VS Code with Pymakr:**
1. Open Pymakr REPL to view logs
2. Use `print()` statements for debugging
3. Use Pymakr console for output

**Using Serial Monitor (any tool):**
1. Connect to ESP32 serial port (115200 baud)
2. View MicroPython REPL output
3. Use tools like PuTTY, screen, or minicom file
```

### Debugging

With Developer Mode enabled and Thonny connected:

1. View real-time logs in the Thonny Shell window
2. Use `print()` statements in your code for debugging
3. Device errors will appear in the log output
4. Press **Ctrl+C** to stop execution
5. Press **Ctrl+D** to restart

### Testing Messages

Send test notifications from any computer on the network:

```bash
# Simple message
curl -d "Hello from ntfy!" ntfy.home.lan/general

# Message with title
curl -H "Title: Server Alert" -d "Disk space low" ntfy.home.lan/general

# High priority message
curl -H "Priority: high" -H serial 
```

### Can't connect to device console or via Thonny/Pymakr
- Check USB cable is a data cable (not charge-only)
- Verify correct serial port is selected (check Device Manager on Windows)
- Disconnect and reconnect USB cable
- Try a different USB port
- Install/update USB-to-Serial drivers if needed

### App doesn't appear in app list
- Ensure Developer Mode is enabled
- Verify the app is in `/apps/ntfy/` (not `/apps/ntfy/ntfy/`)
- Restart device (Ctrl+D in Thonny)

### Can't connect to Thonny
- Check USB cable is a data cable (not charge-only)
- Verify ESP32 port is selected in Thonny
- Disconnserial consoled reconnect USB cable
- Try a different USB port

### No messages displaying
- Check Vobot is connected to WiFi
- Verify ntfy server is accessible: `ping ntfy.home.lan`
- Check network configuration on Vobot: Settings → Network
- Look for error messages in Thonny logs

### App crashes or freezes
- Check memory usage (MicroPython has limited RAM)
- Reduce `MAX_MESSAGES` if storing too many messages
- Review Thonny logs for error messages
- Ensure proper cleanup in `on_stop()` method

## Technical Details

- **Platform**: ESP32 with MicroPython
- **UI Framework**: LVGL (LittlevGL)
- **HTTP Client**: urequests (MicroPython)
- **JSON Parser**: ujson (MicroPython)
- **Max App Size**: 200KB
- **Total App Space**: 900KB (all apps combined)

## Resources

- [ntfy Documentation](https://docs.ntfy.sh/)
- [ntfy Subscribe API](https://docs.ntfy.sh/subscribe/api/)
- [Vobot Developer Documentation](https://dock.myvobot.com/developer/)
- [Vobot Getting Started](https://dock.myvobot.com/developer/getting_started/)
- [LVGL Documentation](https://docs.lvgl.io/)

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review Vobot documentation: https://dock.myvobot.com/developer/
- Check ntfy documentation: https://docs.ntfy.sh/

---

**Status**: 🚧 In Development

Last Updated: December 13, 2025
