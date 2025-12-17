"""
ntfy Notification Viewer for Vobot Mini Dock
Fetches messages in on_running_foreground, not on startup
"""
import lvgl as lv
import urequests as requests
import ujson
import utime
import clocktime

VERSION = "1.0.0"
__version__ = VERSION  # Expose version for web UI
NAME = "ntfy"
# A file path or data (bytes type) of the logo image for this app.
# If not specified, the default icon will be applied.
ICON = "A:apps/ntfy/resources/icon.png"

# MicroPython uses 2000-01-01 epoch, Unix uses 1970-01-01
SECONDS_FROM_1970_TO_2000 = 946684800

NTFY_SERVER = "http://ntfy.home.lan"
NTFY_TOPIC = "general"  # Comma-separated topics (ntfy requires at least one)
MAX_MESSAGES = 5
CONNECTION_MODE = "long-poll"  # polling | long-poll
fetch_interval = 10

app_mgr = None  # Application manager (set in on_boot)
scr = None
label_title = None
label_info = None
base_server = None
header_prio_icon = None  # Icon shown next to header line

last_fetch_time = -999  # Force first fetch immediately
messages = []
current_index = 0
separator_line = None
new_badge_time = 0
NEW_BADGE_TIMEOUT = 5  # seconds
last_time_seen = 0
new_badge_icon = None  # Priority icon shown on new message

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
                    # Hide priority icon when user navigates
                    if new_badge_icon:
                        new_badge_icon.add_flag(lv.obj.FLAG.HIDDEN)
                except Exception:
                    pass
        elif e_key == lv.KEY.LEFT:  # Left = older
            if current_index < len(messages) - 1:
                current_index += 1
                update_display()
                print(f"→ Message {current_index + 1}/{len(messages)}")
                # Hide NEW badge on user navigation
                try:
                    # Hide priority icon when user navigates
                    if new_badge_icon:
                        new_badge_icon.add_flag(lv.obj.FLAG.HIDDEN)
                except Exception:
                    pass
    elif e_code == lv.EVENT.FOCUSED:
        # Enable edit mode when focused
        if not lv.group_get_default().get_editing():
            lv.group_get_default().set_editing(True)

def format_time(timestamp):
    """Format Unix timestamp to 12-hour time with am/pm"""
    try:
        # Apply timezone offset to the Unix timestamp
        tz_offset = clocktime.tzoffset()
        local_timestamp = timestamp + tz_offset
        # Convert to time tuple using utime.localtime
        t = utime.localtime(local_timestamp)
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
    global messages, current_index, label_info, separator_line, header_prio_icon
    
    if not messages or current_index >= len(messages):
        label_info.set_text("No messages yet.\n\nWaiting for notifications...")
        label_info.set_style_text_color(lv.color_hex(0x808080), lv.PART.MAIN)  # Dim gray
        try:
            if header_prio_icon:
                header_prio_icon.add_flag(lv.obj.FLAG.HIDDEN)
        except Exception:
            pass
        # Separator line blue when idle
        try:
            if separator_line:
                separator_line.set_style_line_color(lv.color_hex(0x4488FF), 0)  # Blue
        except Exception:
            pass
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
        2: 0xFFFFFF,  # white (low)
        1: 0xFFFFFF   # white (min)
    }.get(prio, 0x00FF88)
    
    # Condensed single-line header: [1/1] Normal - 12/14 9:25 PM
    header = f"[{current_index + 1}/{len(messages)}] {prio_name} - {time_str}"

    # Update header icon for current priority
    try:
        prio_icon_map = {
            1: "A:apps/ntfy/resources/min.png",
            2: "A:apps/ntfy/resources/low.png",
            3: "A:apps/ntfy/resources/default.png",
            4: "A:apps/ntfy/resources/high.png",
            5: "A:apps/ntfy/resources/max.png",
        }
        icon_src = prio_icon_map.get(prio, "A:apps/ntfy/resources/default.png")
        if header_prio_icon:
            header_prio_icon.set_src(icon_src)
            header_prio_icon.clear_flag(lv.obj.FLAG.HIDDEN)
    except Exception:
        pass
    
    # Get message content
    title = msg.get('title', '')
    # If no title, fall back to topic name (useful when subscribing to multiple topics)
    if not title:
        title = msg.get('topic', '')
    body = msg.get('message', '')

    # Update title bar to show current message topic when multiple topics are configured
    try:
        mode_prefix = "[P]" if CONNECTION_MODE == "polling" else ("[L]" if CONNECTION_MODE == "long-poll" else "[S]")
    except Exception:
        mode_prefix = "[P]"
    try:
        if base_server:
            current_topic = msg.get('topic', '') or NTFY_TOPIC
            # If multi-topic config, prefer the message's topic for display
            if "," in NTFY_TOPIC and current_topic:
                title_path = f"{base_server}/{current_topic}"
            else:
                title_path = f"{base_server}/{NTFY_TOPIC}"
            label_title.set_text(f"{mode_prefix} {title_path}")
    except Exception:
        pass
    
    # Build display: header, optional title (bold if present), body
    if title and body:
        # Title on its own line, then body. Try to bold title.
        display = f"{header}\n\n{title}\n{body}"
    elif title:
        # Only title, no body
        display = f"{header}\n\n{title}"
    elif body:
        # Only body
        display = f"{header}\n\n{body}"
    else:
        display = f"{header}\n\n(no content)"
    
    # Truncate if too long
    if len(display) > 200:
        display = display[:197] + "..."
    
    label_info.set_text(display)
    label_info.set_style_text_color(lv.color_hex(0xFFFFFF), lv.PART.MAIN)  # Bright white for content
    
    # Color the separator line based on priority
    try:
        if separator_line:
            separator_line.set_style_line_color(lv.color_hex(prio_color), 0)
    except Exception:
        pass

async def on_boot(apm):
    """Called when app is first loaded - store app manager"""
    global app_mgr
    app_mgr = apm
    print(f"=== ntfy on_boot() === app_mgr: {app_mgr}")

async def on_start():
    """Called when app starts - set up UI and load config"""
    global scr, label_title, label_info, separator_line, base_server, header_prio_icon
    global NTFY_SERVER, NTFY_TOPIC, MAX_MESSAGES, fetch_interval, CONNECTION_MODE
    
    print("=== ntfy on_start() ===")
    print(f"app_mgr: {app_mgr}")
    print(f"Current CONNECTION_MODE: {CONNECTION_MODE}")
    
    try:
        scr = lv.obj()
        scr.set_style_bg_color(lv.color_hex(0x000000), lv.PART.MAIN)
        scr.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
        
        # Load persisted settings from web setup
        try:
            if app_mgr:
                cfg = app_mgr.config() if hasattr(app_mgr, "config") else {}
                print(f"Config loaded: {cfg}")
                if isinstance(cfg, dict):
                    # server
                    srv = cfg.get("server")
                    if isinstance(srv, str) and srv:
                        NTFY_SERVER = srv
                        print(f"Server set to: {NTFY_SERVER}")
                    # topic
                    top = cfg.get("topic")
                    if isinstance(top, str):
                        topics_raw = top.strip()
                        if topics_raw:
                            topics_list = [t.strip() for t in topics_raw.split(',') if t.strip()]
                            if topics_list:
                                NTFY_TOPIC = ','.join(topics_list)
                                print(f"Topic(s) set to: {NTFY_TOPIC}")
                            else:
                                NTFY_TOPIC = "general"
                                print("Topic empty after parsing; defaulting to 'general'")
                        else:
                            NTFY_TOPIC = "general"
                            print("Topic blank; defaulting to 'general'")
                    # max_messages (comes as string from input field)
                    mm = cfg.get("max_messages")
                    if mm:
                        try:
                            mm = int(mm)
                            if 1 <= mm <= 50:
                                MAX_MESSAGES = mm
                                print(f"Max messages set to: {MAX_MESSAGES}")
                        except (ValueError, TypeError):
                            pass
                    # fetch_interval (comes as string from input field)
                    fi = cfg.get("fetch_interval")
                    if fi:
                        try:
                            fi = int(fi)
                            if 2 <= fi <= 120:
                                fetch_interval = fi
                                print(f"Fetch interval set to: {fetch_interval}")
                        except (ValueError, TypeError):
                            pass
                    # connection_mode
                    cm = cfg.get("connection_mode")
                    if isinstance(cm, str) and cm in ("polling","long-poll","sse"):
                        CONNECTION_MODE = cm
                        print(f"Connection mode set to: {CONNECTION_MODE}")
            else:
                print("WARNING: app_mgr is None - config will not load")
        except Exception as e:
            print(f"Config load error: {e}")

        # Title bar with larger font
        label_title = lv.label(scr)
        # Display server/topic with mode prefix; multi-topic uses first topic for initial display
        try:
            mode_prefix = "[P]" if CONNECTION_MODE == "polling" else ("[L]" if CONNECTION_MODE == "long-poll" else "[S]")
        except Exception:
            mode_prefix = "[P]"
        base_server = NTFY_SERVER.rstrip("/") or NTFY_SERVER
        initial_topic = NTFY_TOPIC
        if "," in NTFY_TOPIC:
            parts = [p.strip() for p in NTFY_TOPIC.split(',') if p.strip()]
            if parts:
                initial_topic = parts[0]
        title_path = f"{base_server}/{initial_topic}"
        label_title.set_text(f"{mode_prefix} {title_path}")
        label_title.set_pos(10, 8)
        label_title.set_style_text_color(lv.color_hex(0x00FF88), lv.PART.MAIN)  # Greenish by default

        # New message priority icon (hidden by default)
        try:
            global new_badge_icon
            new_badge_icon = lv.img(scr)
            # Default icon source; will be updated per priority on new message
            new_badge_icon.set_src("A:apps/ntfy/resources/default.png")
            new_badge_icon.align(lv.ALIGN.TOP_RIGHT, -10, 4)
            # Hide until a new message arrives
            new_badge_icon.add_flag(lv.obj.FLAG.HIDDEN)
        except Exception as _:
            # Fallback is to do nothing; we keep UI functional without icon
            pass
        
        # Separator line (under title) - moved down 2px and made thicker
        line_points = [{"x": 10, "y": 34}, {"x": 310, "y": 32}]
        separator_line = lv.line(scr)
        separator_line.set_points(line_points, len(line_points))
        separator_line.set_style_line_width(4, 0)
        separator_line.set_style_line_color(lv.color_hex(0x4488FF), 0)  # Blue when idle
        
        # Header priority icon (aligned to the left of header line)
        try:
            header_prio_icon = lv.img(scr)
            header_prio_icon.set_src("A:apps/ntfy/resources/default.png")
            header_prio_icon.set_pos(10, 34)
            header_prio_icon.add_flag(lv.obj.FLAG.HIDDEN)
        except Exception:
            header_prio_icon = None

        # Message content area (starts right under separator). Shift right to leave space for icon.
        label_info = lv.label(scr)
        label_info.set_text("Fetching messages...")
        label_info.set_pos(36, 34)
        label_info.set_width(280)
        label_info.set_style_text_color(lv.color_hex(0xE0E0E0), lv.PART.MAIN)  # Light gray
        label_info.set_long_mode(lv.label.LONG.WRAP)
        label_info.set_style_text_line_space(3, lv.PART.MAIN)  # Better line spacing

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
    global last_fetch_time, messages, current_index, label_title, new_badge_icon, new_badge_time, last_time_seen
    
    now = utime.time()

    # Throttled polling/long-poll timing
    if now - last_fetch_time < fetch_interval:
        # Also handle NEW badge timeout
        try:
            # Auto-hide the priority icon after timeout to reduce visual noise
            if new_badge_time and (now - new_badge_time) >= NEW_BADGE_TIMEOUT:
                if new_badge_icon:
                    new_badge_icon.add_flag(lv.obj.FLAG.HIDDEN)
                new_badge_time = 0
        except Exception:
            pass
        return  # Too soon to fetch again
    
    last_fetch_time = now
    print(f"Fetching messages at {now}...")
    
    try:
        # Polling vs Long-poll
        base_server = NTFY_SERVER.rstrip("/") or NTFY_SERVER
        path = f"{base_server}/{NTFY_TOPIC}/json"

        if CONNECTION_MODE == "long-poll":
            url = f"{path}?poll=1&since={last_time_seen or '24h'}"
            print("Mode: Long-poll (subscription)")
        else:
            url = f"{path}?poll=1&since=24h"
            print("Mode: Polling")
        print(f"GET {url}")
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                label_title.set_style_text_color(lv.color_hex(0x00FF88), lv.PART.MAIN)
            except Exception:
                pass
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
                        
                        # Keep track of old messages before update
                        previous_latest_time = messages[0].get('time', 0) if messages else 0
                        
                        # For long-poll: prepend new messages to history, keep cached messages
                        # For polling: replace entire list with fetched messages
                        if CONNECTION_MODE == "long-poll":
                            # Merge: new messages at front + keep old cached messages
                            # Deduplicate by message ID to avoid showing same message multiple times
                            new_messages.reverse()  # Newest first
                            existing_ids = {msg.get('id') for msg in messages if msg.get('id')}
                            unique_new = []
                            for msg in new_messages:
                                msg_id = msg.get('id')
                                if not msg_id or msg_id not in existing_ids:
                                    unique_new.append(msg)
                                    if msg_id:
                                        existing_ids.add(msg_id)
                            # Concatenate: newest new messages first, then old messages
                            messages = unique_new + messages
                            messages = messages[:MAX_MESSAGES]  # Trim to max
                        else:
                            # Polling: take last MAX_MESSAGES from fetch
                            messages = new_messages[-MAX_MESSAGES:]
                            messages.reverse()  # Newest first
                        
                        if messages:
                            last_time_seen = messages[0].get('time', last_time_seen) or last_time_seen
                        
                        # Detect new message arrival
                        latest_time = messages[0].get('time', 0) if messages else 0
                        if latest_time and latest_time > previous_latest_time:
                            # Jump to newest and show priority icon badge
                            current_index = 0
                            try:
                                # Select icon based on priority of the newest message
                                newest_prio = messages[0].get('priority', 3)
                                prio_icon_map = {
                                    1: "A:apps/ntfy/resources/min.png",
                                    2: "A:apps/ntfy/resources/low.png",
                                    3: "A:apps/ntfy/resources/default.png",
                                    4: "A:apps/ntfy/resources/high.png",
                                    5: "A:apps/ntfy/resources/max.png",
                                }
                                icon_src = prio_icon_map.get(newest_prio, "A:apps/ntfy/resources/default.png")
                                if new_badge_icon:
                                    new_badge_icon.set_src(icon_src)  # Update icon to match priority
                                    new_badge_icon.clear_flag(lv.obj.FLAG.HIDDEN)  # Show icon
                                new_badge_time = now
                            except Exception:
                                pass
                        else:
                            try:
                                # No newer message; ensure icon is hidden
                                if new_badge_icon:
                                    new_badge_icon.add_flag(lv.obj.FLAG.HIDDEN)
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
                try:
                    label_title.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
                except Exception:
                    pass
                label_info.set_text(f"Error: {str(read_err)[:40]}")
        else:
            print(f"HTTP {response.status_code}")
            try:
                label_title.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
            except Exception:
                pass
            label_info.set_text(f"Server error: {response.status_code}")
        
        response.close()
        
    except Exception as e:
        print(f"Fetch failed: {e}")
        try:
            label_title.set_style_text_color(lv.color_hex(0xFF4444), lv.PART.MAIN)
        except Exception:
            pass
        label_info.set_text(f"Error: {str(e)[:40]}")

async def on_stop():
    """Called when leaving app"""
    global scr
    print("ntfy stopping")
    if scr:
        scr.clean()
        del scr
        scr = None

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
                "caption": "ntfy Topic(s)",
                "name": "topic",
                "attributes": {"maxLength": 100, "placeholder": "e.g., general or alerts,builds"},
                "tip": "Comma-separated topics (ntfy requires at least one)"
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
                "type": "input",
                "default": "5",
                "caption": "Max Cached Messages",
                "name": "max_messages",
                "attributes": {"maxLength": 2, "placeholder": "5"},
                "tip": "Maximum number of messages to cache (1-20)"
            },
            {
                "type": "select",
                "default": "long-poll",
                "caption": "Connection Mode",
                "name": "connection_mode",
                "options": [("Polling", "polling"), ("Long-poll", "long-poll")],
                "tip": "Polling checks periodically; Long-poll waits for new messages"
            }
        ]
    }

