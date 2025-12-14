"""
ntfy Notification Viewer for Vobot Mini Dock
Fetches messages in on_running_foreground, not on startup
"""
import lvgl as lv
import urequests as requests
import ujson
import utime

VERSION = "0.01"
NAME = "ntfy"
ICON = "A:apps/ntfy/resources/icon.png"

NTFY_SERVER = "http://ntfy.home.lan"
NTFY_TOPIC = "general"

scr = None
label_title = None
label_status = None
label_info = None
label_counter = None

last_fetch_time = 0
fetch_interval = 30
messages = []
current_index = 0

def event_handler(e):
    """Handle encoder rotation for message navigation"""
    global current_index, messages
    e_key = e.get_key()
    
    if not messages:
        return
    
    if e_key == lv.KEY.RIGHT:  # Rotate counter-clockwise (up/newer)
        if current_index > 0:
            current_index -= 1
            update_display()
            print(f"← Message {current_index + 1}/{len(messages)}")
    elif e_key == lv.KEY.LEFT:  # Rotate clockwise (down/older)
        if current_index < len(messages) - 1:
            current_index += 1
            update_display()
            print(f"→ Message {current_index + 1}/{len(messages)}")

def update_display():
    """Update UI with current message"""
    global messages, current_index, label_info, label_counter
    
    if not messages or current_index >= len(messages):
        label_info.set_text("No messages")
        label_counter.set_text("")
        return
    
    msg = messages[current_index]
    display = msg.get('message') or msg.get('title') or "(no message)"
    if len(display) > 100:
        display = display[:97] + "..."
    
    label_info.set_text(display)
    label_counter.set_text(f"{current_index + 1}/{len(messages)}")

async def on_start():
    """Called when app starts - just set up UI"""
    global scr, label_title, label_status, label_info, label_counter
    print("=== ntfy on_start() ===")
    
    try:
        scr = lv.obj()
        
        label_title = lv.label(scr)
        label_title.set_text(f"ntfy: {NTFY_TOPIC}")
        label_title.set_pos(5, 10)
        
        label_status = lv.label(scr)
        label_status.set_text("Loading...")
        label_status.set_pos(5, 35)
        
        label_counter = lv.label(scr)
        label_counter.set_text("")
        label_counter.set_pos(240, 35)
        
        label_info = lv.label(scr)
        label_info.set_text("Fetching...")
        label_info.set_pos(5, 60)
        label_info.set_width(310)
        label_info.set_long_mode(lv.label.LONG.WRAP)
        
        # Attach event handler for encoder rotation
        scr.add_event(event_handler, lv.EVENT.KEY, None)
        
        lv.scr_load(scr)
        print("UI ready")
        
    except Exception as e:
        print(f"ERROR: {e}")

async def on_running_foreground():
    """Called every ~200ms - fetch messages here, not on startup"""
    global last_fetch_time, label_status, messages, current_index
    
    now = utime.time()
    if now - last_fetch_time < fetch_interval:
        return  # Too soon to fetch again
    
    last_fetch_time = now
    print(f"Fetching messages at {now}...")
    
    try:
        # Fetch last 5 messages without streaming
        url = f"{NTFY_SERVER}/{NTFY_TOPIC}/json?poll=1&since=10m"
        print(f"GET {url}")
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            label_status.set_text("OK")
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
                        messages = new_messages[-5:]
                        messages.reverse()  # Newest first
                        current_index = 0  # Reset to newest
                        
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
                label_info.set_text(f"Error: {str(read_err)[:30]}")
        else:
            print(f"HTTP {response.status_code}")
            label_status.set_text(f"{response.status_code}")
            label_info.set_text("Server error")
        
        response.close()
        
    except Exception as e:
        print(f"Fetch failed: {e}")
        label_status.set_text("FAIL")
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
    return {}

