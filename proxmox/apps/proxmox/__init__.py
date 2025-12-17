"""
Proxmox Metrics Viewer for Vobot Mini Dock - Simplified Text Version
Displays VM/LXC counts and node metrics
"""
import lvgl as lv
import urequests as requests
import ujson
import utime

VERSION = "0.0.6"
__version__ = VERSION
NAME = "Proxmox"
# A file path or data (bytes type) of the logo image for this app.
# If not specified, the default icon will be applied.
ICON = "A:apps/proxmox/resources/icon.png"

# Default settings
PVE_HOST = "proxmox.home.lan:8006"
NODE_NAME = "proxmox"
API_TOKEN_ID = "api@pam!homepage"
API_SECRET = ""  # Must be configured via web settings
POLL_TIME = 10  # seconds between updates

# Globals
app_mgr = None
scr = None
label_title = None
label_page1 = None
label_page2 = None
label_page3 = None
gauge_container = None
gauge_cpu = None
gauge_ram = None
gauge_netin = None
gauge_netout = None
current_page = 0  # 0=page1, 1=page2, 2=page3
last_fetch_time = -999  # Force immediate first fetch

# Metrics storage
lxc_running = 0
lxc_total = 0
vm_running = 0
vm_total = 0
node_cpu_pct = 0.0
node_mem_used_gb = 0.0
node_mem_total_gb = 0.0
node_uptime_sec = 0
node_netin_bytes = 0
node_netout_bytes = 0


def get_settings_json():
    """Web settings form"""
    return {
        "title": "Proxmox Configuration",
        "form": [
            {
                "type": "input",
                "default": "proxmox.home.lan:8006",
                "caption": "Proxmox Host",
                "name": "pve_host",
                "attributes": {"maxLength": 100, "placeholder": "host:port"},
                "tip": "Hostname and port (e.g., proxmox.home.lan:8006)"
            },
            {
                "type": "input",
                "default": "pve",
                "caption": "Node Name",
                "name": "node_name",
                "attributes": {"maxLength": 50, "placeholder": "pve"},
                "tip": "Cluster node name"
            },
            {
                "type": "input",
                "default": "user@realm!token",
                "caption": "API Token ID",
                "name": "api_token_id",
                "attributes": {"maxLength": 100, "placeholder": "user@realm!token"},
                "tip": "Format: user@realm!tokenid"
            },
            {
                "type": "input",
                "default": "",
                "caption": "API Secret",
                "name": "api_secret",
                "attributes": {"maxLength": 100, "placeholder": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
                "tip": "API token secret (UUID format)"
            },
            {
                "type": "input",
                "default": "10",
                "caption": "Poll Interval (seconds)",
                "name": "poll_time",
                "attributes": {"maxLength": 3, "placeholder": "10"},
                "tip": "Update frequency (5-120 seconds)"
            }
        ]
    }


def format_uptime(seconds):
    """Format uptime as DD:HH:MM:SS"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{secs:02d}"


def create_gauge(parent, x, y, size, label_text, color_hex):
    """Create a circular gauge widget with arc and label"""
    # Container for gauge
    gauge_obj = lv.obj(parent)
    gauge_obj.set_size(size, size)
    gauge_obj.set_pos(x, y)
    gauge_obj.set_style_bg_color(lv.color_hex(0x222222), lv.PART.MAIN)
    gauge_obj.set_style_border_width(1, lv.PART.MAIN)
    gauge_obj.set_style_border_color(lv.color_hex(0x444444), lv.PART.MAIN)
    gauge_obj.set_style_radius(5, lv.PART.MAIN)
    gauge_obj.set_style_pad_all(2, lv.PART.MAIN)
    
    # Arc for progress
    arc = lv.arc(gauge_obj)
    arc.set_size(size - 8, size - 8)
    arc.set_style_arc_color(lv.color_hex(color_hex), lv.PART.INDICATOR)
    arc.set_style_arc_color(lv.color_hex(0x333333), lv.PART.MAIN)
    arc.set_style_arc_width(4, lv.PART.MAIN)
    arc.set_value(0)
    arc.center()
    
    # Percentage label (center)
    pct_label = lv.label(gauge_obj)
    pct_label.set_style_text_font(lv.font_ascii_bold_28, lv.PART.MAIN)
    pct_label.set_style_text_color(lv.color_hex(color_hex), lv.PART.MAIN)
    pct_label.set_text("0%")
    pct_label.center()
    
    # Title label (bottom)
    title_label = lv.label(gauge_obj)
    title_label.set_style_text_font(lv.font_ascii_14, lv.PART.MAIN)
    title_label.set_style_text_color(lv.color_hex(0xCCCCCC), lv.PART.MAIN)
    title_label.set_text(label_text)
    title_label.align(lv.ALIGN.BOTTOM_MID, 0, -2)
    
    # Store references for updating
    gauge_obj._arc = arc
    gauge_obj._pct_label = pct_label
    
    return gauge_obj


def update_gauge(gauge_obj, value_pct):
    """Update gauge arc and percentage"""
    if not gauge_obj or not hasattr(gauge_obj, '_arc'):
        return
    
    # Clamp to 0-100
    value_pct = max(0, min(100, value_pct))
    
    # Update arc (0-100 maps to 0-360)
    gauge_obj._arc.set_value(value_pct)
    
    # Update label
    gauge_obj._pct_label.set_text(f"{int(value_pct)}%")


def update_display():
    """Update the display with current metrics"""
    global current_page, label_page1, label_page2, label_page3, gauge_container
    global lxc_running, lxc_total, vm_running, vm_total
    global node_cpu_pct, node_mem_used_gb, node_mem_total_gb
    global node_uptime_sec, node_netin_bytes, node_netout_bytes
    
    print(f"[DBG] update_display() page={current_page}")
    
    # Hide all pages first
    if label_page1:
        label_page1.add_flag(lv.obj.FLAG.HIDDEN)
    if label_page2:
        label_page2.add_flag(lv.obj.FLAG.HIDDEN)
    if label_page3:
        label_page3.add_flag(lv.obj.FLAG.HIDDEN)
    if gauge_container:
        gauge_container.add_flag(lv.obj.FLAG.HIDDEN)
    
    # Show current page
    if current_page == 0:
        # Page 1: All data points (sanity test)
        if not label_page1:
            return
        label_page1.clear_flag(lv.obj.FLAG.HIDDEN)
        
        text = "=== Page 1: All Data ===\n"
        text += f"LXC: {lxc_running}/{lxc_total} running\n"
        text += f"VMs: {vm_running}/{vm_total} running\n"
        text += f"CPU: {node_cpu_pct:.1f}%\n"
        text += f"RAM: {node_mem_used_gb:.1f}/"
        text += f"{node_mem_total_gb:.1f} GB\n"
        text += f"Uptime: {format_uptime(node_uptime_sec)}\n"
        text += f"Net In: {node_netin_bytes / (1024**2):.1f} MB\n"
        text += f"Net Out: {node_netout_bytes / (1024**2):.1f} MB"
        
        label_page1.set_text(text)
        print(f"[DBG] Page 1 updated ({len(text)} chars)")
        
    elif current_page == 1:
        # Page 2: Summary with formatted uptime
        if not label_page2:
            return
        label_page2.clear_flag(lv.obj.FLAG.HIDDEN)
        
        text = "=== Page 2: Summary ===\n\n"
        text += f"LXC Containers:\n"
        text += f"  {lxc_running} of {lxc_total} running\n\n"
        text += f"VMs:\n"
        text += f"  {vm_running} of {vm_total} running\n\n"
        text += f"Uptime: {format_uptime(node_uptime_sec)}"
        
        label_page2.set_text(text)
        print(f"[DBG] Page 2 updated")
        
    elif current_page == 2:
        # Page 3: Graphical gauges
        if not gauge_container:
            return
        gauge_container.clear_flag(lv.obj.FLAG.HIDDEN)
        
        # Update gauge values
        if gauge_cpu:
            update_gauge(gauge_cpu, node_cpu_pct)
        
        if gauge_ram:
            ram_pct = (node_mem_used_gb / max(node_mem_total_gb, 1)) * 100.0
            update_gauge(gauge_ram, ram_pct)
        
        if gauge_netin:
            # Scale network to 0-100 (assuming max 100 MB/s is "full")
            netin_mb = node_netin_bytes / (1024**2)
            netin_pct = min(100, (netin_mb / 100.0) * 100.0) if netin_mb > 0 else 0
            update_gauge(gauge_netin, netin_pct)
        
        if gauge_netout:
            netout_mb = node_netout_bytes / (1024**2)
            netout_pct = min(100, (netout_mb / 100.0) * 100.0) if netout_mb > 0 else 0
            update_gauge(gauge_netout, netout_pct)
        
        print(f"[DBG] Page 3 gauges updated")


async def on_boot(apm):
    """Store app manager reference"""
    global app_mgr
    app_mgr = apm
    print("[DBG] on_boot() called")


async def on_start():
    """Initialize UI and load settings"""
    global scr, label_title, label_page1, label_page2, label_page3
    global PVE_HOST, NODE_NAME, API_TOKEN_ID, API_SECRET, POLL_TIME
    
    print("=== on_start() called ===")
    
    # Load settings from web config
    if app_mgr:
        try:
            cfg = app_mgr.config() if hasattr(app_mgr, "config") else {}
            if isinstance(cfg, dict):
                print(f"[DBG] Config loaded: {list(cfg.keys())}")
                
                # Host
                host = cfg.get("pve_host")
                if isinstance(host, str) and host:
                    PVE_HOST = host
                    print(f"[DBG] Host: {PVE_HOST}")
                
                # Node name
                node = cfg.get("node_name")
                if isinstance(node, str) and node:
                    NODE_NAME = node
                    print(f"[DBG] Node: {NODE_NAME}")
                
                # Token ID
                token = cfg.get("api_token_id")
                if isinstance(token, str) and token:
                    API_TOKEN_ID = token
                    print(f"[DBG] Token ID: {API_TOKEN_ID}")
                
                # Secret
                secret = cfg.get("api_secret")
                if isinstance(secret, str) and secret:
                    API_SECRET = secret
                    print("[DBG] API Secret configured")
                else:
                    print("[WARN] No API Secret configured!")
                
                # Poll time
                poll = cfg.get("poll_time")
                if poll:
                    try:
                        poll = int(poll)
                        if 5 <= poll <= 120:
                            POLL_TIME = poll
                            print(f"[DBG] Poll time: {POLL_TIME}s")
                    except ValueError:
                        print("[WARN] Invalid poll_time")
        except Exception as e:
            print(f"[ERR] Config load failed: {e}")
    
    # Create screen
    scr = lv.obj()
    print("[DBG] Created screen object")
    
    # Title bar
    label_title = lv.label(scr)
    label_title.set_text(f"Running {NAME}")
    label_title.set_pos(10, 8)
    label_title.set_style_text_color(lv.color_hex(0xFF6600), lv.PART.MAIN)
    print("[DBG] Created title label")
    
    # Separator line
    line_points = [{"x": 0, "y": 0}, {"x": 320, "y": 0}]
    separator_line = lv.line(scr)
    separator_line.set_points(line_points, 2)
    separator_line.set_pos(0, 32)
    separator_line.set_style_line_color(lv.color_hex(0xBBBBBB), 0)
    print("[DBG] Created separator line")
    
    # Page 1 label (detailed data)
    label_page1 = lv.label(scr)
    label_page1.set_pos(10, 40)
    label_page1.set_width(300)
    label_page1.set_long_mode(lv.label.LONG.WRAP)
    label_page1.set_style_text_color(lv.color_hex(0xFFFFFF), lv.PART.MAIN)
    label_page1.set_text("Loading...")
    print("[DBG] Created page 1 label")
    
    # Page 2 label (summary)
    label_page2 = lv.label(scr)
    label_page2.set_pos(10, 40)
    label_page2.set_width(300)
    label_page2.set_long_mode(lv.label.LONG.WRAP)
    label_page2.set_style_text_color(lv.color_hex(0xFFFFFF), lv.PART.MAIN)
    label_page2.add_flag(lv.obj.FLAG.HIDDEN)
    print("[DBG] Created page 2 label")
    
    # Page 3 label (graphs placeholder)
    label_page3 = lv.label(scr)
    label_page3.set_pos(10, 40)
    label_page3.set_width(300)
    label_page3.set_long_mode(lv.label.LONG.WRAP)
    label_page3.set_style_text_color(lv.color_hex(0xFFFFFF), lv.PART.MAIN)
    label_page3.add_flag(lv.obj.FLAG.HIDDEN)
    print("[DBG] Created page 3 label")
    
    # Page 3 gauge container (2x2 grid for gauges: CPU, RAM, Net In, Net Out)
    gauge_container = lv.obj(scr)
    gauge_container.set_size(320, 240)
    gauge_container.set_pos(0, 0)
    gauge_container.set_style_bg_opa(lv.OPA._0, lv.PART.MAIN)
    gauge_container.set_style_border_width(0, lv.PART.MAIN)
    gauge_container.add_flag(lv.obj.FLAG.HIDDEN)
    print("[DBG] Created gauge container")
    
    # Create gauges in 2x2 grid (each 140x100)
    gauge_cpu = create_gauge(gauge_container, 5, 35, 150, "CPU", 0xFF6B6B)
    gauge_ram = create_gauge(gauge_container, 165, 35, 150, "RAM", 0x4ECDC4)
    gauge_netin = create_gauge(gauge_container, 5, 135, 150, "Net In", 0x45B7D1)
    gauge_netout = create_gauge(gauge_container, 165, 135, 150, "Net Out", 0x96CEB4)
    print("[DBG] Created all gauges")
    
    # Load screen
    lv.screen_load(scr)
    print("[DBG] Screen loaded")
    
    # Setup input handling (encoder + buttons) - use add_event_cb
    scr.add_event_cb(event_handler, lv.EVENT.ALL, None)
    group = lv.group_get_default()
    if group:
        group.add_obj(scr)
        lv.group_focus_obj(scr)
        group.set_editing(True)
        print("[DBG] Input group configured")
    
    # Check if settings are configured, show warning if not
    if not API_SECRET or not API_TOKEN_ID or API_TOKEN_ID == "api@pam!homepage":
        label_page1.set_text(
            "⚠️ CONFIGURATION REQUIRED\n\n"
            "Please configure:\n"
            "• API Token ID\n"
            "• API Secret\n\n"
            "Visit:\nhttp://192.168.1.32/apps\n\n"
            "Press ENTER to refresh"
        )
        print("[WARN] Settings not configured - showing config reminder")
    else:
        # Force initial display update
        update_display()
    
    print("[DBG] on_start() complete")


def event_handler(e):
    """Handle encoder/button events"""
    global current_page, last_fetch_time
    
    e_code = e.get_code()
    print(f"[DBG] Event code: {e_code}, KEY event value={lv.EVENT.KEY}")
    
    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()
        print(f"[DBG] Key pressed: {e_key} (LEFT={lv.KEY.LEFT}, RIGHT={lv.KEY.RIGHT}, ENTER={lv.KEY.ENTER}, ESC={lv.KEY.ESC})")
        
        if e_key == lv.KEY.LEFT:  # Encoder rotates left = next page
            current_page = (current_page + 1) % 3
            print(f"[DBG] → Next page: {current_page + 1}/3")
            update_display()
            
        elif e_key == lv.KEY.RIGHT:  # Encoder rotates right = previous page
            current_page = (current_page - 1) % 3
            print(f"[DBG] ← Previous page: {current_page + 1}/3")
            update_display()
            
        elif e_key == lv.KEY.ENTER:  # Manual refresh
            print("[DBG] Manual refresh triggered")
            last_fetch_time = -999
    
    elif e_code == lv.EVENT.FOCUSED:
        print("[DBG] Screen focused - enabling edit mode")
        lv_group = lv.group_get_default()
        if lv_group and not lv_group.get_editing():
            lv_group.set_editing(True)


async def on_running_foreground():
    """Fetch metrics periodically"""
    global last_fetch_time, lxc_running, lxc_total, vm_running, vm_total
    global node_cpu_pct, node_mem_used_gb, node_mem_total_gb
    global node_uptime_sec, node_netin_bytes, node_netout_bytes
    global label_title
    
    now = utime.time()
    
    # Throttle to POLL_TIME seconds
    if (now - last_fetch_time) < POLL_TIME:
        return
    
    last_fetch_time = now
    
    # Validate config
    if not API_SECRET or not API_TOKEN_ID:
        print("[WARN] API credentials not configured")
        if label_page1:
            label_page1.set_text("ERROR:\nAPI credentials\nnot configured\n\nConfigure at:\nhttp://192.168.1.32/apps")
        return
    
    print(f"[DBG] Fetching metrics at {now}...")
    
    try:
        # Fetch VM/LXC data
        url_vms = f"https://{PVE_HOST}/api2/json/cluster/resources?type=vm"
        headers = {"Authorization": f"PVEAPIToken={API_TOKEN_ID}={API_SECRET}"}
        
        print(f"[DBG] Fetch URL: {url_vms}")
        resp = requests.get(url_vms, headers=headers, timeout=8)
        print(f"[DBG] Response status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = ujson.loads(resp.text)
            vms = data.get("data", [])
            
            # Reset counters
            lxc_r = 0
            lxc_t = 0
            vm_r = 0
            vm_t = 0
            
            # Count VMs/LXCs for this node
            for vm in vms:
                if vm.get("node") != NODE_NAME:
                    continue
                
                vm_type = vm.get("type", "")
                status = vm.get("status", "")
                
                if vm_type == "lxc":
                    lxc_t += 1
                    if status == "running":
                        lxc_r += 1
                elif vm_type == "qemu":
                    vm_t += 1
                    if status == "running":
                        vm_r += 1
            
            lxc_running = lxc_r
            lxc_total = lxc_t
            vm_running = vm_r
            vm_total = vm_t
            
            print(f"[DBG] LXC: {lxc_running}/{lxc_total} | VM: {vm_running}/{vm_total}")
        
        resp.close()
        
        # Small delay before second request
        utime.sleep_ms(100)
        
        # Fetch node metrics
        url_nodes = f"https://{PVE_HOST}/api2/json/cluster/resources?type=node"
        resp = requests.get(url_nodes, headers=headers, timeout=8)
        
        if resp.status_code == 200:
            data = ujson.loads(resp.text)
            nodes = data.get("data", [])
            
            for node in nodes:
                if node.get("node") == NODE_NAME:
                    # Extract metrics
                    cpu = node.get("cpu", 0.0)
                    node_cpu_pct = cpu * 100.0
                    
                    mem_used = node.get("mem", 0)
                    mem_total = node.get("maxmem", 1)
                    node_mem_used_gb = mem_used / (1024**3)
                    node_mem_total_gb = mem_total / (1024**3)
                    
                    node_uptime_sec = node.get("uptime", 0)
                    
                    # Try to get network stats from cluster resources (may be 0)
                    node_netin_bytes = node.get("netin", 0)
                    node_netout_bytes = node.get("netout", 0)
                    
                    print(f"[DBG] Node: cpu={node_cpu_pct:.1f}% mem={node_mem_used_gb:.1f}/{node_mem_total_gb:.1f}GB")
                    print(f"[DBG] Uptime: {format_uptime(node_uptime_sec)}")
                    print(f"[DBG] Net from cluster: in={node_netin_bytes} out={node_netout_bytes}")
                    
                    # Try /nodes/{node}/status for more detailed network stats
                    try:
                        url_status = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/status"
                        resp_status = requests.get(url_status, headers=headers, timeout=5)
                        if resp_status.status_code == 200:
                            status_data = ujson.loads(resp_status.text).get("data", {})
                            # Check for network interface stats
                            if "netin" in status_data:
                                node_netin_bytes = status_data.get("netin", node_netin_bytes)
                            if "netout" in status_data:
                                node_netout_bytes = status_data.get("netout", node_netout_bytes)
                            print(f"[DBG] Net from status: in={node_netin_bytes/(1024**2):.1f}MB out={node_netout_bytes/(1024**2):.1f}MB")
                        resp_status.close()
                    except Exception as e:
                        print(f"[DBG] Status endpoint failed: {e} (using cluster values)")
                    
                    break
        
        resp.close()
        
        # Update display
        update_display()
        
        # Success - set title green
        if label_title:
            label_title.set_style_text_color(lv.color_hex(0x00FF00), lv.PART.MAIN)
        
        print("[DBG] Fetch complete")
        
    except Exception as e:
        print(f"[ERR] Fetch failed: {e}")
        if label_page1:
            label_page1.set_text(f"ERROR:\n{str(e)[:100]}\n\nRetrying in {POLL_TIME}s...")
        if label_title:
            label_title.set_style_text_color(lv.color_hex(0xFF0000), lv.PART.MAIN)


async def on_stop():
    """Cleanup on app exit"""
    global scr, label_title, label_page1, label_page2, label_page3, gauge_container
    global gauge_cpu, gauge_ram, gauge_netin, gauge_netout
    print("[DBG] on_stop() called")
    
    if scr:
        scr.clean()
        scr.del_async()
        scr = None
    
    label_title = None
    label_page1 = None
    label_page2 = None
    label_page3 = None
    gauge_container = None
    gauge_cpu = None
    gauge_ram = None
    gauge_netin = None
    gauge_netout = None
