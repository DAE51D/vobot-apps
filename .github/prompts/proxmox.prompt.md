---
agent: 'agent'
tools: ['search','edit', 'web', 'read','github/*']
description: 'Implement Proxmox dashboard for Vobot Mini Dock'
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

# Task: Build proxmox Dashboard App

## Objectives

Create a Vobot Mini Dock application that displays on two pages (use scroll wheel to paginate through them)

https://docs.lvgl.io/master/widgets/

Page 1:

- four quadrants. Use proxmox/pc_hw_mockup.jpg as emulation
- top left: 
  - CPU % using LVGL arc
  - CPU: total
- top right:
  - RAM % using LVGL arc
  - RAM: used / total
- bottom left:
  - Network In Kb/s
  - Network In line graph
  - Network Out KB/s
  - Network Out line graph
  - use green and red arrows on text lines
- bottom right:
  - VMs: running / total
  - line graph like network %
  - LXCs: running / total
  - line graph like VMs %
  
Page 2:

- Text version
- all of the data points and values
- this is a sanity test page to ensure the API calls are working and we're pulling the correct values
- Uptime DD:HH:MM:SS
- use smaller font if needed to squeeze it all on the page: https://dock.myvobot.com/developer/guides/app-interface-guide/#currently-supported-fonts

## Functional Requirements

### Metrics Fetching
- Poll Proxmox every ~10 seconds
- Endpoints:
  - `/nodes/{node}/status` for cpu/mem/swap/disk/uptime
  - `/nodes/{node}/rrddata?timeframe=hour` for `netin`/`netout` (use latest point; display KB/s)
  - `/nodes/{node}/qemu` and `/nodes/{node}/lxc` to count running/total
- Handle network errors gracefully and keep last good data

### Navigation
- **Scroll up** (encoder counter-clockwise, `lv.KEY.RIGHT`): Previous screen (circular)
- **Scroll down** (encoder clockwise, `lv.KEY.LEFT`): Next screen (circular)
- **Press encoder** (`lv.KEY.ENTER`): no action yet
- **Press ESC** (`lv.KEY.ESC`): Exit app

## Technical Implementation Details

### HTTP Request Pattern (token auth)
```python
import urequests as requests

headers = {"Authorization": f"PVEAPIToken={API_TOKEN_ID}={API_SECRET}"}
resp = requests.get(f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/status", headers=headers)
data = resp.json().get("data", {})
resp.close()
# Repeat for rrddata/qemu/lxc; cache last-good metrics
```

### UI Update Pattern (arcs/bars)
```python
cpu_arc.set_value(int(metrics['cpu']))
cpu_pct_label.set_text(f"{metrics['cpu']}%")
ram_arc.set_value(int(metrics['mem_pct']))
ram_detail_label.set_text(f"{metrics['mem_used']}/{metrics['mem_total']}GB")
net_in_bar.set_value(min(100, int(metrics['netin']/10)))
net_in_label.set_text(f"Dn: {metrics['netin']:.0f} KB/s")
```

### Event Handler Pattern
```python
def event_handler(e):
  global current_page
  e_key = e.get_key()
  if e_key == lv.KEY.LEFT:
    current_page = (current_page + 1) % 2
    show_current_page()
  elif e_key == lv.KEY.RIGHT:
    current_page = (current_page - 1) % 2
    show_current_page()
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
- POLL_TIME - polling interval seconds (default 10)

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

https://www.perplexity.ai/search/i-have-a-https-proxmox-home-la-KZwXOdvbQY.eVlWPKbDxmA#12

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

#### Network Traffic

```powershell
curl -k -H "Authorization: PVEAPIToken=$($env:API_TOKEN_ID)=$($env:API_SECRET)" "https://$($env:PVE_HOST)/api2/json/nodes/$($env:NODE_NAME)/rrddata?timeframe=hour" | ConvertFrom-Json | Select-Object -ExpandProperty data | Select-Object -First 3 | ConvertTo-Json -Depth 3
```
yields an array of these objects... use `netin` (This is INcoming = DOWNload) and `netout` (This is OUTgoing = UPload)
```json
[
    {
    "pressureiosome": 1.115,
    "pressurecpusome": 0.0666666666666667,
    "netout": 35853.7333333333,
    "pressureiofull": 1.11333333333333,
    "time": 1766014200,
    "pressurememorysome": 0,
    "loadavg": 3.44,
    "arcsize": 17280,
    "netin": 95589.45,
    "swaptotal": 8589930496,
    "memtotal": 135038619648,
    "cpu": 0.0277346455515237,
    "rootused": 30622670848,
    "maxcpu": 72,
    "swapused": 2550175061.33333,
    "memused": 57576897877.3333,
    "memavailable": 77461721770.6667,
    "pressurememoryfull": 0,
    "iowait": 0.000922842288903207,
    "roottotal": 100861726720
  }
]
```

```powershell
curl -k `
  -H "Authorization: PVEAPIToken=$($env:API_TOKEN_ID)=$($env:API_SECRET)" `
  "https://$($env:PVE_HOST)/api2/json/nodes/$($env:NODE_NAME)/rrddata?timeframe=hour" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty data |
  Select-Object -First 1 -Property netin, netout
```
yeilds
```
    netin   netout
    -----   ------
106151.08 30824.88
```

Or for the raw numbers only
```powershell
$point = curl -k `
  -H "Authorization: PVEAPIToken=$($env:API_TOKEN_ID)=$($env:API_SECRET)" `
  "https://$($env:PVE_HOST)/api2/json/nodes/$($env:NODE_NAME)/rrddata?timeframe=hour" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty data |
  Select-Object -First 1

$point.netin
$point.netout
```
yields
```
PS D:\daevid\Code\Vobot> $point.netin
100643.65
PS D:\daevid\Code\Vobot> $point.netout
42314.3833333333
```

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
