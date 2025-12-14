---
agent: 'agent'
tools: ['search/changes', 'search/codebase', 'edit/editFiles', 'web/fetch', 'web/githubRepo', 'read/problems', 'search', 'search/searchResults', 'search/usages', 'github/*', 'pylance-mcp-server/*']
description: 'Implement ntfy client for Vobot Mini Dock'
---

# Role and Context

You are an expert Python developer specializing in MicroPython applications for the Vobot Mini Dock platform.

# Infrastructure

## ntfy Server
- Self-hosted ntfy server: http://ntfy.home.lan/
- Primary topic: `general` (http://ntfy.home.lan/general)
- No authentication required for subscriptions
- Supports multiple topics via comma-separated URLs

### ntfy API Details

#### Publishing (for testing)
```bash
curl -d "Hello World." ntfy.home.lan/general
```

#### Subscribing Options
1. **JSON Stream** (Recommended): `http://ntfy.home.lan/general/json`
2. **SSE Stream**: `http://ntfy.home.lan/general/sse`
3. **Raw Stream**: `http://ntfy.home.lan/general/raw`
4. **WebSockets**: `ws://ntfy.home.lan/general/ws`

#### JSON Message Format
```json
{
    "id": "hwQ2YpKdmg",
    "time": 1635528741,
    "expires": 1673542291,
    "event": "message",
    "topic": "general",
    "message": "Disk full",
    "title": "Alert",
    "priority": 3,
    "tags": ["warning", "server"]
}
```

#### Event Types
- `open` - Connection established
- `message` - New notification message
- `keepalive` - Keep connection alive (empty)
- `poll_request` - Polling mode

#### Message Fields
- **id**: Unique message identifier
- **time**: Unix timestamp
- **event**: Event type (open/message/keepalive)
- **topic**: Topic name
- **message**: Message body (main content)
- **title**: Optional message title
- **priority**: 1-5 (1=min, 3=default, 5=max)
- **tags**: Array of tags (may map to emojis)
- **click**: Optional URL to open
- **attachment**: Optional file attachment metadata

#### Useful Query Parameters
- `poll=1` - Get cached messages and close connection
- `since=10m` - Get messages from last 10 minutes
- `since=all` - Get all cached messages
- `since=latest` - Get only the most recent message

## Vobot Mini Dock Environment
- Platform: ESP32 running MicroPython
- HTTP library: `urequests` (MicroPython HTTP client)
- UI: LVGL (LittlevGL)
- Limited memory: Keep data structures minimal
- Async operations via `async/await`

# Task: Build ntfy Notification Viewer App

## Objectives

Create a Vobot Mini Dock application that:

1. **Subscribes to ntfy server**: Connect to `http://ntfy.home.lan/general/json`
2. **Displays notifications**: Show message content, title, and metadata
3. **Message navigation**: Use scroll wheel to browse through messages
4. **Message counter**: Display current message index and total count
5. **Background updates**: Fetch new messages periodically
6. **Resource management**: Handle memory constraints, cache messages

## Functional Requirements

### Message Fetching
- Poll for messages periodically (e.g., every 30 seconds) in background
- Use `poll=1` to get cached messages without keeping connection open
- Parse JSON response and extract message data
- Store messages in a list (limit to last N messages, e.g., 20)
- Handle network errors gracefully

### UI Display
- **Screen Layout**:
  - Title bar: "ntfy: general"
  - Message counter: "2/5" (current/total)
  - Message title (if available)
  - Message body (main content)
  - Timestamp (formatted human-readable)
  - Priority indicator (optional)
  - Tags (optional)

### Navigation
- **Scroll up** (encoder counter-clockwise, `lv.KEY.RIGHT`): Previous message
- **Scroll down** (encoder clockwise, `lv.KEY.LEFT`): Next message
- **Press encoder** (`lv.KEY.ENTER`): Mark as read / Refresh messages
- **Press ESC** (`lv.KEY.ESC`): Exit app

### Data Management
- Cache messages in memory (list/array)
- Limit cache to prevent memory exhaustion (e.g., 20 messages max)
- Track current message index for navigation
- Handle empty state (no messages)

## Technical Implementation Details

### HTTP Request Pattern
```python
import urequests as requests

try:
    # Poll for recent messages
    url = "http://ntfy.home.lan/general/json?poll=1&since=10m"
    response = requests.get(url)
    
    # Parse response line by line (JSONL format)
    for line in response.text.strip().split('\n'):
        if line:
            msg = ujson.loads(line)
            if msg.get('event') == 'message':
                # Process message
                messages.append({
                    'id': msg.get('id'),
                    'title': msg.get('title', 'ntfy'),
                    'message': msg.get('message', ''),
                    'time': msg.get('time'),
                    'priority': msg.get('priority', 3),
                    'tags': msg.get('tags', [])
                })
    
    response.close()
except Exception as e:
    print(f"Error fetching messages: {e}")
```

### State Management
```python
# Global state
messages = []          # List of message dicts
current_index = 0      # Currently displayed message
last_fetch_time = 0    # Unix timestamp of last fetch
fetch_interval = 30    # Seconds between fetches
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
    label_title.set_text(msg.get('title', 'ntfy'))
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
resp = r.get("http://ntfy.home.lan/general/json?poll=1&since=all")
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
cd D:\daevid\Code\Vobot\nfty
.venv\Scripts\ampy.exe --port COM4 --baud 115200 --delay 1 put ntfy /apps/ntfy

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

# On Vobot: Launch ntfy app from menu and watch logs stream in real-time
# Look for ERROR, timeouts, or "Fetch error:" messages
```

### JSON Parser Notes

**ujson is built into MicroPython** - no import needed beyond what's standard:
```python
import ujson

# Parse single JSON object
msg = ujson.loads('{"id":"123","message":"Hello"}')
print(msg['message'])  # Output: Hello

# The real challenge: getting the raw response text from urequests
# urequests.Response.text property can timeout on MicroPython when reading large responses
# Solutions being explored:
# 1. Use socket module directly (more control, lower-level)
# 2. Switch to simpler API (single message instead of JSONL stream)
# 3. Use polling mode (poll=1) to get cached messages in one shot
# 4. Read response in smaller chunks with timeout handling
```

## Implementation Steps

1. **Setup project structure**:
   - Create `/apps/ntfy/` folder
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
   - Send test messages: `curl -d "Test message" ntfy.home.lan/general`
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

## Potential Enhancements (Future)

- [ ] Support multiple topics
- [ ] Filter by priority or tags
- [ ] Display icons/emojis for tags
- [ ] Show message age (e.g., "5m ago")
- [ ] Mark messages as read/unread
- [ ] Delete/dismiss messages
- [ ] Open click URLs (if applicable)
- [ ] Sound/vibration on new message
- [ ] Settings page (topic selection, refresh interval)

## Dependencies & Libraries

- `urequests` - HTTP client (MicroPython built-in)
- `ujson` - JSON parser (MicroPython built-in)
- `lvgl` - UI framework (Vobot platform provides)
- `time` or `utime` - Time operations (MicroPython built-in)

## Resources & References

- ntfy documentation: https://docs.ntfy.sh/
- ntfy subscribe API: https://docs.ntfy.sh/subscribe/api/
- Vobot developer docs: https://dock.myvobot.com/developer/
- LVGL documentation: https://docs.lvgl.io/
- MicroPython urequests: https://docs.micropython.org/en/latest/library/urequests.html

## Deployment (ampy on Windows)

- USB: use the data-capable USB-C port; device enumerates as `USB Serial Device` (CH34x). Here it appears on **COM4**.
- Ensure only one tool holds the port (close Pymakr/Arduino/other serial monitors).

Common commands (from project root):
```powershell
# Upload app to /apps/ntfy
D:/daevid/Code/Vobot/nfty/.venv/Scripts/ampy.exe --port COM4 --baud 115200 --delay 1 put ntfy /apps/ntfy

# List apps to verify
D:/daevid/Code/Vobot/nfty/.venv/Scripts/ampy.exe --port COM4 --baud 115200 ls /apps

# Optional: check port mapping
Get-CimInstance -ClassName Win32_SerialPort | Select-Object Name, DeviceID, Description | Format-Table -AutoSize

# Restart device (via serial terminal, 115200 baud): press Ctrl+D in REPL
```

## Quick Test (send message via PowerShell)

From your Windows dev machine:
```powershell
Invoke-WebRequest -Uri "http://ntfy.home.lan/general" -Method Post -Body "Hello from Vobot test via PowerShell"
```
