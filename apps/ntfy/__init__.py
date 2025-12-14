"""
ntfy Notification Viewer for Vobot Mini Dock
Fetches messages in on_running_foreground, not on startup
"""
import lvgl as lv
import urequests as requests
import ujson
import utime

VERSION = "0.0.3"
NAME = "ntfy"
ICON = "A:apps/ntfy/resources/icon.png"

NTFY_SERVER = "http://ntfy.home.lan"
NTFY_TOPIC = "general"
MAX_MESSAGES = 5

scr = None
label_title = None
label_status = None
label_info = None
label_counter = None

last_fetch_time = 0
fetch_interval = 10
messages = []
current_index = 0
separator_line = None
new_badge_time = 0
NEW_BADGE_TIMEOUT = 5  # seconds

def event_handler(e):
    """Handle encoder rotation for message navigation"""
    global current_index, messages
    
    e_code = e.get_code()
    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()
        print(f"Key: {e_key}")
        
        if not messages:
            return
        
        if e_key == lv.KEY.RIGHT:  # Right = newer
            if current_index > 0:
                current_index -= 1
                update_display()
                print(f"← Message {current_index + 1}/{len(messages)}")
                # Hide NEW badge on user navigation
                try:
                    new_badge.add_flag(lv.obj.FLAG.HIDDEN)
                except Exception:
                    pass
        elif e_key == lv.KEY.LEFT:  # Left = older
            if current_index < len(messages) - 1:
                current_index += 1
                update_display()
                print(f"→ Message {current_index + 1}/{len(messages)}")
                # Hide NEW badge on user navigation
                try:
                    new_badge.add_flag(lv.obj.FLAG.HIDDEN)
                except Exception:
                    pass
    elif e_code == lv.EVENT.FOCUSED:
        # Enable edit mode when focused
        if not lv.group_get_default().get_editing():
            lv.group_get_default().set_editing(True)

def format_time(timestamp):
    """Format Unix timestamp to 12-hour time with am/pm"""
    try:
        t = utime.localtime(timestamp)
        month = t[1]
        day = t[2]
        hour24 = t[3]
        minute = t[4]
        ampm = "AM" if hour24 < 12 else "PM"
        hour12 = hour24 % 12
        if hour12 == 0:
            hour12 = 12
        return f"{month:02d}/{day:02d} {hour12}:{minute:02d} {ampm}"
    except:
        return "--/-- --:--"

def update_display():
    """Update UI with current message"""
    global messages, current_index, label_info, label_counter, label_status, separator_line
    
    if not messages or current_index >= len(messages):
        label_info.set_text("No messages yet.\n\nWaiting for notifications...")
        label_info.set_style_text_color(lv.color_hex(0x808080), lv.PART.MAIN)  # Dim gray
        label_counter.set_text("0/0")
        label_status.set_text("IDLE")
        label_status.set_style_text_color(lv.color_hex(0x808080), lv.PART.MAIN)
        return
    
    msg = messages[current_index]
    
    # Format time
    time_str = format_time(msg.get('time', 0))

    # Priority mapping (1-5). Fallback to 3 (normal)
    prio = msg.get('priority', 3)
    prio_name = {
        5: 'Critical',
        4: 'High',
        3: 'Normal',
        2: 'Low',
        1: 'Min'
    }.get(prio, 'Normal')
    prio_color = {
        5: 0xFF4444,  # red
        4: 0xFFA500,  # orange
        3: 0x00FF88,  # green
        2: 0x3399FF,  # blue
        1: 0x808080   # gray
    }.get(prio, 0x00FF88)
    
    # Build multi-line header: priority, message counter, date time
    header_lines = [
        f"{prio_name}",
        f"Message #{current_index + 1}/{len(messages)}",
        f"{time_str}",
    ]
    
    # Get message content
    title = msg.get('title', '')
    body = msg.get('message', '')
    
    # Build display with title (if present) and body
    header = "\n".join(header_lines)
    if title and body:
        display = f"{header}\n\n{title}\n{body}"
    elif title:
        display = f"{header}\n\n{title}"
    elif body:
        display = f"{header}\n\n{body}"
    else:
        display = f"{header}\n\n(no content)"
    
    # Truncate if too long
    if len(display) > 180:
        display = display[:177] + "..."
    
    label_info.set_text(display)
    label_info.set_style_text_color(lv.color_hex(0xFFFFFF), lv.PART.MAIN)  # Bright white for content
    # Counter now integrated in header; clear standalone counter
    try:
        label_counter.set_text("")
    except Exception:
        pass

    # Color the separator line based on priority
    try:
        if separator_line:
            separator_line.set_style_line_color(lv.color_hex(prio_color), 0)
    except Exception:
        pass

async def on_start(app_mgr=None):
    """Called when app starts - just set up UI"""
    global scr, label_title, label_status, label_info, label_counter, separator_line
    print("=== ntfy on_start() ===")
    
    try:
        scr = lv.obj()
        scr.set_style_bg_color(lv.color_hex(0x000000), lv.PART.MAIN)
        scr.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
        
        # Optionally load persisted settings from web setup
        try:
            if app_mgr:
                cfg = app_mgr.config() if hasattr(app_mgr, "config") else {}
                if isinstance(cfg, dict):
                    # max_messages
                    mm = cfg.get("max_messages")
                    if isinstance(mm, int) and 1 <= mm <= 50:
                        global MAX_MESSAGES
                        MAX_MESSAGES = mm
                    # fetch_interval
                    fi = cfg.get("fetch_interval")
                    if isinstance(fi, int) and 5 <= fi <= 120:
                        global fetch_interval
                        fetch_interval = fi
        except Exception as _:
            pass

        # Title bar with larger font
        label_title = lv.label(scr)
        # Display full server/topic URL for clarity on data source
        label_title.set_text(f"{NTFY_SERVER}/{NTFY_TOPIC}")
        label_title.set_pos(10, 8)
        label_title.set_style_text_color(lv.color_hex(0x00FF88), lv.PART.MAIN)  # Greenish by default
        # Note: font_montserrat_18 might not be available, using default
        
        # Status indicator (left) - will be colored based on state
        label_status = lv.label(scr)
        label_status.set_text("...")
        label_status.set_pos(10, 35)
        label_status.set_style_text_color(lv.color_hex(0x808080), lv.PART.MAIN)  # Gray initially

        # New message badge (hidden by default)
        try:
            global new_badge
            new_badge = lv.label(scr)
            new_badge.set_text("NEW")
            new_badge.align(lv.ALIGN.TOP_RIGHT, -10, 8)
            new_badge.set_style_text_color(lv.color_hex(0xFFA500), lv.PART.MAIN)  # Orange
            new_badge.add_flag(lv.obj.FLAG.HIDDEN)
        except Exception as _:
            pass
        
        # Message counter (right aligned)
        label_counter = lv.label(scr)
        label_counter.set_text("")
        label_counter.align(lv.ALIGN.TOP_RIGHT, -10, 35)
        label_counter.set_style_text_color(lv.color_hex(0xFFFFFF), lv.PART.MAIN)  # White
        
        # Separator line (tighter spacing under the title)
        line_points = [{"x": 10, "y": 48}, {"x": 310, "y": 48}]
        separator_line = lv.line(scr)
        separator_line.set_points(line_points, len(line_points))
        separator_line.set_style_line_width(3, 0)
        separator_line.set_style_line_color(lv.color_hex(0x333333), 0)
        
        # Message content area
        label_info = lv.label(scr)
        label_info.set_text("Fetching messages...")
        label_info.set_pos(10, 56)
        label_info.set_width(300)
        label_info.set_style_text_color(lv.color_hex(0xE0E0E0), lv.PART.MAIN)  # Light gray
        label_info.set_long_mode(lv.label.LONG.WRAP)
        label_info.set_style_text_line_space(3, lv.PART.MAIN)  # Better line spacing

        # No priority dot; the separator line will be colored by priority
        
        lv.scr_load(scr)
        
        # Attach event handler and set up focus group
        scr.add_event(event_handler, lv.EVENT.ALL, None)
        group = lv.group_get_default()
        if group:
            group.add_obj(scr)
            lv.group_focus_obj(scr)
            group.set_editing(True)
        print("UI ready")
        
    except Exception as e:
        print(f"ERROR: {e}")

async def on_running_foreground():
    """Called every ~200ms - fetch messages here, not on startup"""
    global last_fetch_time, label_status, messages, current_index, label_title, new_badge, new_badge_time
    
    now = utime.time()
    if now - last_fetch_time < fetch_interval:
        # Also handle NEW badge timeout
        try:
            if new_badge_time and (now - new_badge_time) >= NEW_BADGE_TIMEOUT:
                new_badge.add_flag(lv.obj.FLAG.HIDDEN)
                new_badge_time = 0
        except Exception:
            pass
        return  # Too soon to fetch again
    
    last_fetch_time = now
    print(f"Fetching messages at {now}...")
    
    try:
        # Fetch last 5 messages from past 24h without streaming
        url = f"{NTFY_SERVER}/{NTFY_TOPIC}/json?poll=1&since=24h"
        print(f"GET {url}")
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                label_title.set_style_text_color(lv.color_hex(0x00FF88), lv.PART.MAIN)
            except Exception:
                pass
            label_status.set_text("")
            print("Got 200, reading...")
            
            try:
                # Read whole body and parse all JSON lines
                data = response.content
                print(f"Read {len(data)} bytes")

                if data:
                    text = data.decode('utf-8')
                    lines = [ln for ln in text.strip().split('\n') if ln]
                    
                    if lines:
                        # Parse each line as a separate JSON message
                        new_messages = []
                        for line in lines:
                            try:
                                msg = ujson.loads(line)
                                new_messages.append(msg)
                            except Exception as parse_err:
                                print(f"Parse error: {parse_err}")
                                continue
                        
                        # Keep last 5 messages (newest first)
                        previous_latest_time = messages[0].get('time', 0) if messages else 0
                        messages = new_messages[-MAX_MESSAGES:]
                        messages.reverse()  # Newest first
                        
                        # Detect new message arrival
                        latest_time = messages[0].get('time', 0) if messages else 0
                        if latest_time and latest_time > previous_latest_time:
                            # Jump to newest and show badge
                            current_index = 0
                            try:
                                new_badge.clear_flag(lv.obj.FLAG.HIDDEN)
                                new_badge_time = now
                            except Exception:
                                pass
                        else:
                            try:
                                new_badge.add_flag(lv.obj.FLAG.HIDDEN)
                                new_badge_time = 0
                            except Exception:
                                pass

                        print(f"Loaded {len(messages)} messages")
                        update_display()
                    else:
                        messages = []
                        update_display()
                else:
                    messages = []
                    update_display()
                    
            except Exception as read_err:
                print(f"Read error: {read_err}")
                label_status.set_text("ERR")
                label_status.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)  # Red
                label_info.set_text(f"Error: {str(read_err)[:30]}")
        else:
            print(f"HTTP {response.status_code}")
            label_status.set_text(f"{response.status_code}")
            label_status.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
            try:
                label_title.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
            except Exception:
                pass
            label_info.set_text("Server error")
        
        response.close()
        
    except Exception as e:
        print(f"Fetch failed: {e}")
        label_status.set_text("FAIL")
        label_status.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
        try:
            label_title.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
        except Exception:
            pass
        label_info.set_text(str(e)[:40])

async def on_stop():
    """Called when leaving app"""
    global scr
    print("ntfy stopping")
    if scr:
        scr.clean()
        del scr
        scr = None

def get_settings_json():
    # Configuration schema for web setup UI
    return {
        "schema": {
            "max_messages": {
                "type": "integer",
                "title": "Max messages to cache",
                "description": "Number of recent messages to display",
                "minimum": 1,
                "maximum": 50,
                "default": MAX_MESSAGES,
            },
            "fetch_interval": {
                "type": "integer",
                "title": "Polling interval (seconds)",
                "description": "How often to poll the ntfy server",
                "minimum": 5,
                "maximum": 120,
                "default": fetch_interval,
            }
        }
    }

