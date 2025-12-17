---
agent: 'agent'
tools: ['search','edit', 'web', 'read','github/*']
description: 'Implement Proxmox client for Vobot Mini Dock'
---

# Role and Context

You are an expert Python developer specializing in MicroPython applications for the Vobot Mini Dock platform.

# Infrastructure

## Proxmox

Server: proxmox.home.lan:8006
Node: proxmox

See credentials in the API examples below

## Vobot Mini Dock Environment
- Platform: ESP32 running MicroPython
- HTTP library: `urequests` (MicroPython HTTP client)
- UI: LVGL (LittlevGL)
- Limited memory: Keep data structures minimal
- Async operations via `async/await`

# Task: Build proxmox Notification Viewer App

# Task: Build proxmox Notification Viewer App

## ✅ COMPLETED OBJECTIVES

Create a Vobot Mini Dock application that displays on three pages (use scroll wheel to paginate through them)

**Page 1: All Data (Sanity Test)**
- ✅ LXC/VM container counts and running status
- ✅ CPU percentage
- ✅ RAM usage in GB
- ✅ Uptime in DD:HH:MM:SS format
- ✅ Network In/Out in MB

**Page 2: Summary View**
- ✅ Number of LXCs running (out of available)
- ✅ Number of VMs running (out of available)  
- ✅ Uptime DD:HH:MM:SS format

**Page 3: Graphical Widgets (2x2 Grid)**
- ✅ CPU - Circular arc gauge with percentage
- ✅ RAM - Circular arc gauge with percentage
- ✅ Network In - Circular arc gauge scaled to 0-100 MB/s
- ✅ Network Out - Circular arc gauge scaled to 0-100 MB/s

## Functional Requirements

### Message Fetching
- Poll for messages periodically (e.g., every 30 seconds) in background
- Parse response and extract statistic data
- update display graphs and values
- Handle network errors gracefully

### Navigation
- **Scroll up** (encoder counter-clockwise, `lv.KEY.RIGHT`): Previous screen (circular)
- **Scroll down** (encoder clockwise, `lv.KEY.LEFT`): Next screen (circular)
- **Press encoder** (`lv.KEY.ENTER`): no action yet
- **Press ESC** (`lv.KEY.ESC`): Exit app

## Technical Implementation Details

### HTTP Request Pattern
```python
import urequests as requests

try:
    # Poll for recent messages
    url = "http://proxmox.home.lan/general/json?poll=1&since=10m"
    response = requests.get(url)
    
    # Parse response line by line (JSONL format)
    for line in response.text.strip().split('\n'):
        if line:
            msg = ujson.loads(line)
            if msg.get('event') == 'message':
                # Process message
                messages.append({
                    'id': msg.get('id'),
                    'title': msg.get('title', 'proxmox'),
                    'message': msg.get('message', ''),
                    'time': msg.get('time'),
                    'priority': msg.get('priority', 3),
                    'tags': msg.get('tags', [])
                })
    
    response.close()
except Exception as e:
    print(f"Error fetching messages: {e}")
```

### UI Update Pattern
```python
def update_display():
    """Update UI with current message"""
    if not messages:
        label_counter.set_text("0/0")
        label_title.set_text("No messages")
        label_message.set_text("Waiting for notifications...")
        return
    
    msg = messages[current_index]
    label_counter.set_text(f"{current_index + 1}/{len(messages)}")
    label_title.set_text(msg.get('title', 'proxmox'))
    label_message.set_text(msg.get('message', ''))
```

### Event Handler Pattern
```python
def event_handler(e):
    global current_index
    e_key = e.get_key()
    
    if e_key == lv.KEY.RIGHT:  # Scroll up = previous message
        if current_index > 0:
            current_index -= 1
            update_display()
    
    elif e_key == lv.KEY.LEFT:  # Scroll down = next message
        if current_index < len(messages) - 1:
            current_index += 1
            update_display()
    
    elif e_key == lv.KEY.ENTER:  # Refresh
        fetch_messages()
        update_display()
```

## Debug

```python
import urequests as r
resp = r.get("http://proxmox.home.lan/general/json?poll=1&since=all")
print(resp.status_code)
print(resp.text[:200])
resp.close()
```
Should yield example like this:
```json
200
{"id":"TuL7m0XZcdbs","time":1765661722,"expires":1765704922,"event":"message","topic":"general","message":"Hi Chris"}
{"id":"EU4W9j5jVDvI","time":1765666454,"expires":1765709654,"event":"message","top
```

### Real-Time Log Monitoring During Development

```powershell
# Terminal 1: Upload latest code (ampy will disconnect after upload)
# From repository root (PowerShell example); prefer module invocation
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 1 put proxmox/apps/proxmox /apps/proxmox

# Terminal 2: Monitor logs continuously (run in separate PowerShell window)
$port = New-Object System.IO.Ports.SerialPort COM4, 115200, None, 8, One
$port.Open()
Write-Host "Monitoring COM4 - Press Ctrl+C to stop"
while($port.IsOpen) { 
    try { 
        $byte = $port.ReadChar()
        [Console]::Write([char]$byte)
    } catch { 
        Start-Sleep -Milliseconds 100 
    } 
}

# On Vobot: Launch proxmox app from menu and watch logs stream in real-time
# Look for ERROR, timeouts, or "Fetch error:" messages
```

### JSON Parser Notes

**ujson is built into MicroPython** - no import needed beyond what's standard:
```python
import ujson

# Parse single JSON object
msg = ujson.loads('{"id":"123","message":"Hello"}')
print(msg['message'])  # Output: Hello
```

## Settings Web Configuration

Use the standard Vobot settings method to configure these variables

- PVE_HOST - "proxmox.home.lan:8006"
- NODE_NAME - "pve"
- API_TOKEN_ID - "user@realm!tokenname"
- API_SECRET - "UUID"
- POLL_TIME - how many seconds between polling for updates (10 )

## Implementation Steps

1. **Setup project structure**:
   - Create `/apps/proxmox/` folder
   - Create `__init__.py` with lifecycle methods
   - Define global variables for state

2. **Implement message fetching**:
   - Write `fetch_messages()` function using `urequests`
   - Parse JSON response (handle JSONL format)
   - Store in `messages` list

3. **Create LVGL UI**:
   - Design screen layout with labels
   - Position elements (counter, title, message)
   - Style text (font size, alignment)

4. **Implement event handling**:
   - Write `event_handler()` for encoder/button input
   - Update `current_index` based on scroll direction
   - Refresh display on navigation

5. **Add periodic updates**:
   - Check elapsed time in `on_running_foreground()`
   - Fetch new messages at intervals
   - Update UI if new messages arrive

6. **Handle edge cases**:
   - Empty message list
   - Network failures
   - Invalid JSON
   - Memory limits (trim old messages)

## Testing Plan

1. **Manual testing**:
   - Send test messages: `curl -d "Test message" proxmox.home.lan/general`
   - Verify messages appear on Vobot display
   - Test scroll wheel navigation
   - Test refresh on encoder press
   - Test ESC button exits

2. **Edge case testing**:
   - No messages (empty state)
   - Single message
   - Many messages (20+)
   - Long message text (truncation)
   - Network disconnection
   - Server unavailable

3. **Performance testing**:
   - Memory usage monitoring
   - Response time for UI updates
   - Network request duration

## Dependencies & Libraries

- `urequests` - HTTP client (MicroPython built-in)
- `ujson` - JSON parser (MicroPython built-in)
- `lvgl` - UI framework (Vobot platform provides)
- `time` or `utime` - Time operations (MicroPython built-in)

## Resources & References

- Vobot developer docs: https://dock.myvobot.com/developer/
- LVGL documentation: https://docs.lvgl.io/
- MicroPython urequests: https://docs.micropython.org/en/latest/library/urequests.html
- Proxmox API: https://pve.proxmox.com/wiki/Proxmox_VE_API and https://pve.proxmox.com/pve-docs/api-viewer/index.html

### Proxmox API Examples (bash)

```bash
export PVE_HOST='proxmox.home.lan:8006'
export API_TOKEN_ID='api@pam!homepage'
export API_SECRET='7a37d386-896c-46b2-b12f-ed3edc17ee47'
export NODE_NAME="proxmox" 

# basic test
curl -k -v \
  -H "Authorization: PVEAPIToken=${API_TOKEN_ID}=${API_SECRET}" \
  "https://${PVE_HOST}/api2/json/"
```

```powershell
$env:PVE_HOST     = "proxmox.home.lan:8006"
$env:API_TOKEN_ID = "api@pam!homepage"
$env:API_SECRET   = "7a37d386-896c-46b2-b12f-ed3edc17ee47"
$env:NODE_NAME    = "proxmox"

# basic test
curl -k `
  -H "Authorization: PVEAPIToken=$($env:API_TOKEN_ID)=$($env:API_SECRET)" `
  "https://$($env:PVE_HOST)/api2/json/"
```

#### Get number of running LXCs

First list all LXCs on a given node, then filter by status == "running":

```bash
curl -k \
  -H "Authorization: PVEAPIToken=${API_TOKEN_ID}=${API_SECRET}" \
  "https://${PVE_HOST}/api2/json/nodes/${NODE_NAME}/lxc" \
  | jq '.data | map(select(.status == "running")) | length'
```

```powershell
curl -k `
  -H "Authorization: PVEAPIToken=$($env:API_TOKEN_ID)=$($env:API_SECRET)" `
  "https://$($env:PVE_HOST)/api2/json/nodes/$($env:NODE_NAME)/lxc" `
  | jq '.data | map(select(.status == "running")) | length'
```

The path `/nodes/{node}/lxc` returns an array of containers with `status`, `vmid`, etc., which you can count with `jq`

#### Get node CPU usage percent

For overall node CPU usage, use the cluster resources endpoint and filter by node name

```bash
curl -k \
  -H "Authorization: PVEAPIToken=${API_TOKEN_ID}=${API_SECRET}" \
  "https://${PVE_HOST}/api2/json/cluster/resources?type=node" \
  | jq ".data[] | select(.type == \"node\" and .node == \"${NODE_NAME}\") | .cpu"
```

```powershell
curl -k `
  -H "Authorization: PVEAPIToken=$($env:API_TOKEN_ID)=$($env:API_SECRET)" `
  "https://$($env:PVE_HOST)/api2/json/cluster/resources?type=node" `
  | jq ".data[] | select(.type == \"node\" and .node == \"${env:NODE_NAME}\") | .cpu"
```

The `.cpu` field is a fraction of total (for example 0.12 means about 12% usage), which is how the Proxmox API exposes CPU utilization.

## Deployment (ampy on Windows)

- USB: use the data-capable USB-C port; device enumerates as `USB Serial Device` (CH34x). Here it appears on **COM4**.
- Ensure only one tool holds the port (close Pymakr/Arduino/other serial monitors).

Common commands (from project root):
```powershell
# Upload app to /apps/proxmox (run from repository root)
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 --delay 1 put proxmox/apps/proxmox /apps/proxmox

# List apps to verify
& ".\.venv\Scripts\python.exe" -m ampy.cli --port COM4 --baud 115200 ls /apps

# Optional: check port mapping
Get-CimInstance -ClassName Win32_SerialPort | Select-Object Name, DeviceID, Description | Format-Table -AutoSize

# Restart device (via serial terminal, 115200 baud): press Ctrl+D in REPL
```
