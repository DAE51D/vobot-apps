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

last_fetch_time = 0
fetch_interval = 30

async def on_start():
    """Called when app starts - just set up UI"""
    global scr, label_title, label_status, label_info
    print("=== ntfy on_start() ===")
    
    try:
        scr = lv.obj()
        
        label_title = lv.label(scr)
        label_title.set_text(f"ntfy: {NTFY_TOPIC}")
        label_title.set_pos(5, 10)
        
        label_status = lv.label(scr)
        label_status.set_text("Loading...")
        label_status.set_pos(5, 40)
        
        label_info = lv.label(scr)
        label_info.set_text("Fetching...")
        label_info.set_pos(5, 70)
        label_info.set_width(310)
        label_info.set_long_mode(lv.label.LONG.WRAP)
        
        lv.scr_load(scr)
        print("UI ready")
        
    except Exception as e:
        print(f"ERROR: {e}")

async def on_running_foreground():
    """Called every ~200ms - fetch messages here, not on startup"""
    global last_fetch_time, label_status, label_info
    
    now = utime.time()
    if now - last_fetch_time < fetch_interval:
        return  # Too soon to fetch again
    
    last_fetch_time = now
    print(f"Fetching messages at {now}...")
    
    try:
        # Get only the latest cached message without streaming
        url = f"{NTFY_SERVER}/{NTFY_TOPIC}/json?poll=1&since=latest"
        print(f"GET {url}")
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            label_status.set_text("OK")
            print("Got 200, reading...")
            
            try:
                # Read whole body once and parse last JSON line
                data = response.content
                print(f"Read {len(data)} bytes")

                if data:
                    text = data.decode('utf-8')
                    lines = [ln for ln in text.strip().split('\n') if ln]
                    if lines:
                        msg = ujson.loads(lines[-1])
                        display = msg.get('message') or msg.get('title') or "(no message)"
                        if len(display) > 40:
                            display = display[:37] + "..."
                        label_info.set_text(display)
                        print(f"Displayed: {display}")
                    else:
                        label_info.set_text("No messages")
                else:
                    label_info.set_text("No messages")
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

