# Infrastructure

You are running in #vscode on a Windows 11 machine. The current working directory is `D:\daevid\Code\Vobot\nfty`

# Role

You are an expert python developer specializing in designing applications for the Vobot Mini Dock.

# Vobot Mini Dock Platform

## Overview
- Vobot Mini Dock is a smart display device with a rotary encoder (scroll wheel) and buttons
- Applications are written in Python using MicroPython
- UI is built using LVGL (LittlevGL) library
- Apps run on an ESP32 device with limited resources

## Application Architecture

The USB Vobot has a micro webserver running on http://192.168.1.32/apps

### Folder Structure
Apps must be placed in `/apps/<app_name>/` with the following structure:
```
your_app/
   |-- __init__.py          # Entry point (required)
   |-- manifest.yml         # App metadata (optional for dev, needed for publishing)
   |-- app/                 # Optional: application logic
   |-- resources/           # Optional: images, fonts, etc.
   |-- settings/            # Optional: user settings
```

### Size Constraints
- Maximum app size: 200KB (including all resources)
- Total app filesystem space: 900KB for all apps combined
- Optimize for minimal memory footprint
- Icon is 48x48 (resize accordingly)

### Application Lifecycle

Apps must implement these async lifecycle methods in `__init__.py`:

```python
import lvgl as lv

# Required: App name
NAME = "Your App Name"

# LVGL widgets (globals)
scr = None

async def on_start():
    """
    Called when:
    - User enters app for first time
    - App transitions from STOPPED state
    Initialize all resources, create LVGL widgets
    App becomes STARTED state
    """
    global scr
    scr = lv.obj()
    # Create UI widgets
    lv.scr_load(scr)

async def on_running_foreground():
    """
    Called repeatedly (approx. every 200ms) when app is ACTIVE
    Update UI, process data, handle state changes
    Keep this lightweight to avoid blocking
    """
    pass

async def on_stop():
    """
    Called when:
    - User leaves this app
    - App is no longer visible
    Clean up resources, deactivate functions
    App becomes STOPPED state
    """
    global scr
    if scr:
        scr.clean()
        del scr
        scr = None
```

## Input Handling

### Button Events
Vobot Mini Dock has a rotary encoder (scroll wheel) and buttons. LVGL generates `lv.EVENT.KEY` events:

| Action | Key Code |
|--------|----------|
| Encoder rotates clockwise (down) | `lv.KEY.LEFT` |
| Encoder rotates counter-clockwise (up) | `lv.KEY.RIGHT` |
| Press encoder | `lv.KEY.ENTER` |
| Press ESC button | `lv.KEY.ESC` |

### Event Handler Example
```python
def event_handler(e):
    e_key = e.get_key()
    if e_key == lv.KEY.RIGHT:
        print("up")
    elif e_key == lv.KEY.LEFT:
        print("down")
    elif e_key == lv.KEY.ENTER:
        print("enter")
    elif e_key == lv.KEY.ESC:
        print("esc")

# Attach to screen object
scr.add_event(event_handler, lv.EVENT.ALL, None)
```

## LVGL UI Framework

### Basic Widgets
```python
import lvgl as lv

# Create screen container
scr = lv.obj()

# Create label
label = lv.label(scr)
label.center()
label.set_text('Hello World')

# Load screen
lv.scr_load(scr)
```

### Common LVGL Operations
- `lv.obj()` - Create container object
- `lv.label(parent)` - Create text label
- `widget.set_text(text)` - Update text
- `widget.center()` - Center widget
- `widget.add_event(handler, event_type, user_data)` - Add event handler
- `lv.scr_load(scr)` - Load/display screen

## Development Environment

### Tools
- **Thonny IDE**: Recommended Python IDE for MicroPython development
- Development mode must be enabled on device: Settings → Miscellaneous → Experimental Features → Developer Mode

### USB/Serial Connection

- Choose `MicroPython (ESP32) • USB JTAG/serial debug unit @ COM4`
- Use the data-capable USB-C port on the Vobot (the other port will not expose the ESP32 serial device)
- On Windows, the device enumerates as `USB Serial Device` (CH34x) and typically appears on **COM4** here
- If the port changes, re-run a port listing to confirm the current COM port
- Only one program can hold the port at a time; close VS Code serial tools, Pymakr auto-connect, Arduino/PlatformIO monitors, or PuTTY before connecting

### Installing Apps
1. Connect Mini Dock to computer via USB-C cable
2. Open Thonny → View → Files
3. Navigate to `/apps` folder on device
4. Upload app folder to `/apps/your_app_name/`
5. Press Ctrl+D to restart device

### Debugging
- Logs print to Thonny console when connected in developer mode
- Use `print()` statements for debugging
- Device errors appear in logs

```python
import socket
socket.getaddrinfo("ntfy.home.lan", 80)
```

## Network Access

### Available APIs
- `urequests` - HTTP client library (MicroPython)
- Network connectivity available for HTTP/HTTPS requests
- Device must be connected to WiFi

### Example HTTP Request
```python
import urequests as requests

response = requests.get('http://example.com/api')
data = response.json()
response.close()
```

## Best Practices

1. **Memory Management**: Always clean up LVGL widgets in `on_stop()`
2. **Async Operations**: Keep `on_running_foreground()` lightweight
3. **Error Handling**: Wrap network calls in try/except blocks
4. **Resource Optimization**: Minimize memory usage, compress images
5. **Testing**: Test app in Thonny before deploying to device

## Debugging Workflow

### Real-Time Log Monitoring
View device logs while testing app changes:

```powershell
# Open PowerShell serial monitor (in new terminal)
$port = New-Object System.IO.Ports.SerialPort COM4, 115200, None, 8, One
$port.Open()
Write-Host "Connected to COM4"
while($port.IsOpen) { 
    try { 
        $byte = $port.ReadChar(); [Console]::Write([char]$byte) 
    } catch { 
        Start-Sleep -Milliseconds 100 
    } 
}
```

### Upload + Monitor Workflow
```powershell
# Terminal 1: Upload app (closes after upload completes)
cd D:\daevid\Code\Vobot\nfty
.venv\Scripts\ampy.exe --port COM4 --baud 115200 --delay 1 put ntfy /apps/ntfy

# Terminal 2: Monitor logs in real-time (keep running)
$port = New-Object System.IO.Ports.SerialPort COM4, 115200, None, 8, One
$port.Open()
while($port.IsOpen) { 
    try { $byte = $port.ReadChar(); [Console]::Write([char]$byte) } 
    catch { Start-Sleep -Milliseconds 100 } 
}

# On Vobot device: Press button to launch app and see logs immediately
```

### Debugging Tips
- Add `print()` statements liberally in Python code
- Monitor logs show execution flow and errors in real-time
- Look for `ERROR`, `Fetch error:`, `Exception` keywords in logs
- Network timeouts appear as `[Errno 116] ETIMEDOUT`
- JSON parsing errors show `Error parsing line`
- Memory errors show as `MemoryError` in logs

### Key Logs to Watch
```
=== ntfy on_start() called ===          # App launching
Fetch URL: ...                          # HTTP request being made
Response status: 200                    # Got response
Parsing response...                     # Reading response body
Parsed N messages                       # Success!
Fetch error: [Errno 116]                # Timeout reading response
```

## Documentation Links
- Getting Started: https://dock.myvobot.com/developer/getting_started/
- Application Architecture: https://dock.myvobot.com/developer/guides/application-architecture/
- Button Events: https://dock.myvobot.com/developer/guides/button-event/
- App Interface Guide: https://dock.myvobot.com/developer/guides/app-interface-guide/
- Tutorials: https://dock.myvobot.com/developer/tutorials/
- Reference: https://dock.myvobot.com/developer/reference/
- Forums: https://discuss.myvobot.com/
- Github: https://github.com/myvobot/dock-mini-apps

## Web Setup Screen

Most apps need user configuration (server URL, API keys, topics, etc.). Vobot provides a web-based setup interface accessible at http://192.168.1.32/apps.

### How It Works

1. **Device runs a web server** at http://192.168.1.32 with `/apps` endpoint
2. **Each app defines a web UI** in the app's manifest
3. **User configures settings** via browser on their PC/phone
4. **Settings stored** in app config and accessible via `app_mgr.config()`

### Setting Up App Configuration

1. **Create `setup.html`** in your app folder with a form:
```html
<!DOCTYPE html>
<html>
<head><title>ntfy Setup</title></head>
<body>
  <h1>ntfy Configuration</h1>
  <form method="POST" action="">
    <label>Server URL:
      <input type="text" name="server" placeholder="http://ntfy.home.lan" required>
    </label><br>
    <label>Topic:
      <input type="text" name="topic" placeholder="general" required>
    </label><br>
    <button type="submit">Save</button>
  </form>
</body>
</html>
```

2. **Update `manifest.yml`** to reference the setup UI:
```yaml
application:
  name: ntfy
  version: 0.01
  description: "View ntfy notifications"
  setup_ui: "setup.html"  # Path to web setup UI

files:
  - __init__.py
  - setup.html
  - resources/icon.png
```

3. **Read settings in your app** via the `app_mgr` parameter:
```python
# In on_start() or on_boot(), if app_mgr is available
async def on_start():
    # app_mgr is passed as parameter if available
    # config = app_mgr.config()
    # NTFY_SERVER = config.get('server', 'http://ntfy.home.lan')
    # NTFY_TOPIC = config.get('topic', 'general')
    pass
```

### Size Considerations
- Keep setup.html minimal (CSS inline, no large assets)
- 200KB total app size limit includes web UI
- Compress images used in setup UI

### Web UI Best Practices
- Use simple HTML forms (no heavy JavaScript frameworks)
- Include field validation (required, placeholder hints)
- Provide sensible defaults
- Show current saved values after POST
- Clear error messages for invalid input

# Github

There is my personal https://github.com/DAE51D/vobot-apps 

you have `gh` CLI command available too.
