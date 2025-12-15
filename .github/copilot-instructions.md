# Infrastructure

You are running in #vscode on a Windows 11 machine. The current working directory is `D:\daevid\Code\Vobot`

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

# LVGL widgets and app manager (globals)
scr = None
app_mgr = None  # Set by on_boot()

async def on_boot(apm):
    """
    Called when app is first loaded (before on_start).
    CRITICAL: Receives and stores the app manager for config access.
    """
    global app_mgr
    app_mgr = apm

async def on_start():
    """
    Called when:
    - User enters app for first time
    - App transitions from STOPPED state
    Initialize all resources, create LVGL widgets
    App becomes STARTED state
    Access app_mgr (set in on_boot) to load persisted settings
    """
    global scr
    scr = lv.obj()
    # Load settings via app_mgr.config() if available
    if app_mgr:
        cfg = app_mgr.config()  # Returns dict of saved settings
        # Use cfg to initialize app state
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

**CRITICAL:** The `on_boot(apm)` function is called **before** `on_start()` and receives the app manager. Store it as a global so it's accessible throughout your app's lifecycle. Without `on_boot()`, `app_mgr` will be `None` and settings won't load.

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
    e_code = e.get_code()
    
    # Only process KEY events
    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()
        if e_key == lv.KEY.RIGHT:
            print("up")
        elif e_key == lv.KEY.LEFT:
            print("down")
        elif e_key == lv.KEY.ENTER:
            print("enter")
        elif e_key == lv.KEY.ESC:
            print("esc")
    
    # Handle focus events
    elif e_code == lv.EVENT.FOCUSED:
        # Enable edit mode when focused
        if not lv.group_get_default().get_editing():
            lv.group_get_default().set_editing(True)

# Attach to screen object and set up focus group
scr.add_event(event_handler, lv.EVENT.ALL, None)

# CRITICAL: Add screen to focus group for encoder events to work
group = lv.group_get_default()
if group:
    group.add_obj(scr)
    lv.group_focus_obj(scr)
    group.set_editing(True)
```

**IMPORTANT:** The rotary encoder will not work unless:
1. Event handler is attached with `lv.EVENT.ALL` (not just `lv.EVENT.KEY`)
2. Screen is added to the default LVGL group
3. Screen is focused and editing mode is enabled

See official examples: [photo_album](https://github.com/myvobot/dock-mini-apps/tree/main/photo_album), [countdown](https://github.com/myvobot/dock-mini-apps/tree/main/countdown)

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

## Time and Timezone Handling

### clocktime Module
The Vobot provides a `clocktime` module for timezone-aware time operations. **Always use `clocktime` for working with timestamps and dates.**

Reference: https://dock.myvobot.com/developer/reference/clocktime/

### Available Functions
- `clocktime.now()` - Returns current Unix timestamp (seconds since 1970-01-01) or `-1` if time not synced
- `clocktime.datetime()` - Returns current local date/time as tuple: `(YYYY, MM, DD, hh, mm, ss, wday, yday)`
- `clocktime.tzoffset()` - Returns timezone offset in seconds from UTC (e.g., `-28800` for PST/UTC-8)

### Converting Unix Timestamps to Local Time

**CRITICAL:** When displaying timestamps from external APIs (like ntfy, weather services, etc.), you must convert UTC timestamps to the device's local timezone.

**❌ WRONG - No timezone conversion:**
```python
import utime

def format_time(timestamp):
    # This treats UTC timestamp as if it's already local time - WRONG!
    t = utime.localtime(timestamp)  
    return f"{t[1]:02d}/{t[2]:02d} {t[3]}:{t[4]:02d}"
```

**✅ CORRECT - Apply timezone offset:**
```python
import utime
import clocktime

def format_time(timestamp):
    """Convert Unix timestamp (UTC) to local time and format"""
    try:
        # Get device timezone offset and apply it
        tz_offset = clocktime.tzoffset()
        local_timestamp = timestamp + tz_offset
        
        # Now convert to time tuple
        t = utime.localtime(local_timestamp)
        month, day, hour, minute = t[1], t[2], t[3], t[4]
        
        # Format as needed (12-hour example)
        ampm = "AM" if hour < 12 else "PM"
        hour12 = hour % 12 if hour % 12 != 0 else 12
        return f"{month:02d}/{day:02d} {hour12}:{minute:02d} {ampm}"
    except:
        return "--/-- --:--"
```

### When to Use Each Function

- **`clocktime.now()`** - Get current time as Unix timestamp (for comparisons, calculations)
- **`clocktime.datetime()`** - Get current date/time tuple (already in local timezone)
- **`clocktime.tzoffset()`** - Convert external UTC timestamps to local time
- **`utime.localtime()`** - Only for formatting time tuples, NOT for timezone conversion

### Common Patterns

```python
import clocktime
import utime

# Check if time is synced
if clocktime.now() == -1:
    print("Time not synced yet")
    return

# Get current local time
curr_time = clocktime.datetime()
print(f"Current time: {curr_time[3]}:{curr_time[4]:02d}")

# Convert API timestamp (UTC) to local time
api_timestamp = 1734226560  # Example UTC timestamp from ntfy/API
tz_offset = clocktime.tzoffset()
local_timestamp = api_timestamp + tz_offset
local_time = utime.localtime(local_timestamp)
print(f"Message time: {local_time[3]}:{local_time[4]:02d}")
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
cd D:\daevid\Code\Vobot\ntfy
../.venv/Scripts/ampy.exe --port COM4 --baud 115200 --delay 1 put apps/ntfy /apps/ntfy

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

## Web Setup Screen / Settings Configuration

Most apps need user configuration (server URL, API keys, topics, etc.). Vobot provides a web-based setup interface accessible at http://192.168.1.32/apps.

### How It Works

1. **Device runs a web server** at http://192.168.1.32 with `/apps` endpoint
2. **Settings form is defined by `get_settings_json()` function** in your app's `__init__.py`
3. **Vobot system auto-generates the web form** from the returned JSON structure
4. **User configures settings** via the auto-generated form in their browser
5. **Settings stored** in app config and accessible via `app_mgr.config()` in Python

### Setting Up App Configuration (get_settings_json Function - REQUIRED)

https://dock.myvobot.com/developer/reference/web-page/

**DO NOT create a `setup.html` file or YAML `settings:` section.** The Vobot system requires a `get_settings_json()` function in `__init__.py` that returns JSON.

1. **Define `get_settings_json()` function in `apps/your_app/__init__.py`**:
```python
def get_settings_json():
    """Return JSON for web settings form - called by Vobot system"""
    return {
        "title": "ntfy Configuration",
        "form": [
            {
                "type": "input",
                "default": "http://ntfy.home.lan",
                "caption": "ntfy Server URL",
                "name": "server",
                "attributes": {"maxLength": 100, "placeholder": "http://ntfy.home.lan"},
                "tip": "Full URL to the ntfy server"
            },
            {
                "type": "input",
                "default": "general",
                "caption": "ntfy Topic",
                "name": "topic",
                "attributes": {"maxLength": 50, "placeholder": "general"},
                "tip": "Topic name to subscribe to"
            },
            {
                "type": "input",
                "default": "10",
                "caption": "Fetch Interval (seconds)",
                "name": "fetch_interval",
                "attributes": {"maxLength": 3, "placeholder": "10"},
                "tip": "How often to check for new messages (2-120 seconds)"
            },
            {
                "type": "select",
                "default": "polling",
                "caption": "Connection Mode",
                "name": "connection_mode",
                "options": [("Polling", "polling"), ("Long-poll", "long-poll"), ("SSE", "sse")],
                "tip": "Choose how the app receives messages"
            }
        ]
    }
```

2. **Read settings in your app** via `app_mgr.config()` after `on_boot()` receives it:
```python
# Store app_mgr in on_boot()
async def on_boot(apm):
    global app_mgr
    app_mgr = apm

# Access it in on_start()
async def on_start():
    global NTFY_SERVER, NTFY_TOPIC, fetch_interval, CONNECTION_MODE
    
    # Load settings from web config
    try:
        if app_mgr:
            cfg = app_mgr.config() if hasattr(app_mgr, "config") else {}
            if isinstance(cfg, dict):
                # Read string settings
                srv = cfg.get("server")
                if isinstance(srv, str) and srv:
                    NTFY_SERVER = srv
                
                # Read number settings (note: comes as string from input fields)
                fi = cfg.get("fetch_interval")
                if fi:
                    try:
                        fi = int(fi)
                        if 5 <= fi <= 120:
                            fetch_interval = fi
                    except ValueError:
                        pass
                
                # Read select/enum settings
                cm = cfg.get("connection_mode")
                if isinstance(cm, str) and cm in ("polling", "long-poll", "sse"):
                    CONNECTION_MODE = cm
    except Exception:
        pass  # Use defaults if config unavailable
```

### Settings Field Types

Based on Vobot documentation (https://dock.myvobot.com/developer/reference/web-page/):

- **input**: Text input field (type: "input")
  - Properties: `default`, `caption`, `name`, `attributes` (maxLength, placeholder), `tip`
  - Returns: String value
- **select**: Dropdown menu (type: "select")
  - Properties: `default`, `caption`, `name`, `options` (list of tuples), `tip`
  - Returns: String value matching option value
- **checkbox**: Multiple selection (type: "checkbox")
  - Properties: `default` (list), `caption`, `name`, `options`, `tip`
  - Returns: List of selected values
- **radio**: Single selection (type: "radio")
  - Properties: `default`, `caption`, `name`, `options`, `tip`
  - Returns: String value
- **switch**: Toggle switch (type: "switch")
  - Properties: `default` (bool), `caption`, `name`, `tip`
  - Returns: Boolean

### Manifest Structure Requirements

https://dock.myvobot.com/developer/guides/publishing-guide/manifest_file/

- **MUST include** `files.include` (not just `files:`)
- **MUST include** `system_requirements` section
- **MUST define** `get_settings_json()` function in `__init__.py` (not YAML in manifest)
- **Settings `name` fields** in JSON must match the keys used in `app_mgr.config().get()`
- **DO NOT use** `setup_ui` field in manifest.yml
- **DO NOT use** `settings:` YAML section in manifest.yml
- **DO NOT create** `setup.html` file

### Versioning Policy
- Whenever bumping the Python app version (e.g., `__version__ = "0.0.X"` in `apps/ntfy/__init__.py`), **ALWAYS** bump `application.version` in `apps/ntfy/manifest.yml` to keep the `/apps` page version accurate.
- The version shown on /apps comes from `manifest.yml`, NOT from Python code.
- Verify the `/apps` page shows the updated version after upload.

### Best Practices
- Use sensible defaults for all settings (e.g., default topic `general`; ntfy requires at least one topic, use comma-separated list for multiple)
- Validate config values with type checks and range checks
- Provide fallback to defaults if config is unavailable or invalid
- Keep setting IDs simple and consistent (lowercase, underscores)
- Use descriptive labels and helpful descriptions for users

# Github

The repo for all of these apps: https://github.com/DAE51D/vobot-apps 

Do not add/commit/push un-tested or non-working code to the repo without express permission to do that. It's a public repository and we don't want followers to download broken versions.

You have `gh` CLI installed at `C:\Program Files\GitHub CLI\gh.exe`. Since it's not in PATH, use the full path with the call operator:

```powershell
&"C:\Program Files\GitHub CLI\gh.exe" <command>
```

Example:
```powershell
&"C:\Program Files\GitHub CLI\gh.exe" repo edit DAE51D/vobot-apps --visibility public --accept-visibility-change-consequences
```

To add `gh` to the user path:

```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\GitHub CLI", "User")
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
gh --version
```

# Publishing

When all complete and ready to publish to the Vobot app store follow these instructions
https://dock.myvobot.com/developer/guides/publishing-guide/

The packaging tool is found at: D:\daevid\Code\Vobot\dock-app-bundler-win.exe which is the root of the parent VSCode project folder as well.
