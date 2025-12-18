import lvgl as lv
import peripherals
import urequests as requests
import ujson
import utime

NAME = "Proxmox"
VERSION = "0.0.9"
__version__ = VERSION
ICON = "A:apps/proxmox/resources/icon.png"

_SCR_WIDTH, _SCR_HEIGHT = peripherals.screen.screen_resolution

# Default settings
PVE_HOST = "proxmox.home.lan:8006"
NODE_NAME = "proxmox"
API_TOKEN_ID = "api@pam!homepage"
API_SECRET = ""  # Must be configured via web settings
POLL_TIME = 10  # seconds between updates

# Globals
_scr = None
_app_mgr = None
_last_fetch_time = -999
_current_page = 0  # 0=main dashboard, 1=debug data
_metrics = {
    'cpu': 0,
    'mem_pct': 0,
    'mem_used': 0,
    'mem_total': 0,
    'netin': 0,
    'netout': 0,
    'vm_running': 0,
    'vm_total': 0,
    'lxc_running': 0,
    'lxc_total': 0,
    'uptime': 0,
    'swap_pct': 0,
    'swap_used': 0,
    'swap_total': 0,
    'disk_pct': 0,
    'disk_used': 0,
    'disk_total': 0
}

def get_settings_json():
    return {
        "title": "Proxmox Configuration",
        "form": [
            {
                "type": "input",
                "default": "proxmox.home.lan:8006",
                "caption": "Proxmox Host",
                "name": "pve_host",
                "attributes": {"maxLength": 100, "placeholder": "proxmox.home.lan:8006"},
                "tip": "Hostname:port of Proxmox server"
            },
            {
                "type": "input",
                "default": "proxmox",
                "caption": "Node Name",
                "name": "node_name",
                "attributes": {"maxLength": 50, "placeholder": "proxmox"},
                "tip": "Name of the Proxmox node to monitor"
            },
            {
                "type": "input",
                "default": "api@pam!homepage",
                "caption": "API Token ID",
                "name": "api_token_id",
                "attributes": {"maxLength": 100, "placeholder": "api@pam!homepage"},
                "tip": "Proxmox API token ID"
            },
            {
                "type": "input",
                "default": "",
                "caption": "API Secret",
                "name": "api_secret",
                "attributes": {"maxLength": 100, "placeholder": "xxxxxxxx-xxxx-xxxx"},
                "tip": "Proxmox API token secret"
            }
        ]
    }

async def fetch_proxmox_data():
    """Fetch metrics from Proxmox API"""
    global _metrics, PVE_HOST, NODE_NAME, API_TOKEN_ID, API_SECRET
    
    if not API_SECRET:
        return False
    
    try:
        headers = {"Authorization": f"PVEAPIToken={API_TOKEN_ID}={API_SECRET}"}
        
        # Get node status
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/status"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()['data']
            _metrics['cpu'] = int(data.get('cpu', 0) * 100)
            _metrics['uptime'] = data.get('uptime', 0)
            
            mem_data = data.get('memory', {})
            mem_used = mem_data.get('used', 0)
            mem_total = mem_data.get('total', 1)
            _metrics['mem_pct'] = int((mem_used / mem_total) * 100)
            _metrics['mem_used'] = int(mem_used / (1024**3) + 0.5)  # GB rounded
            _metrics['mem_total'] = int(mem_total / (1024**3) + 0.99)  # GB rounded up
            
            swap_data = data.get('swap', {})
            swap_used = swap_data.get('used', 0)
            swap_total = swap_data.get('total', 1)
            _metrics['swap_pct'] = int((swap_used / swap_total) * 100) if swap_total > 0 else 0
            _metrics['swap_used'] = round(swap_used / (1024**3))  # GB rounded
            _metrics['swap_total'] = round(swap_total / (1024**3))  # GB rounded
            
            disk_data = data.get('rootfs', {})
            disk_used = disk_data.get('used', 0)
            disk_total = disk_data.get('total', 1)
            _metrics['disk_pct'] = int((disk_used / disk_total) * 100)
            _metrics['disk_used'] = round(disk_used / (1024**3))  # GB rounded
            _metrics['disk_total'] = round(disk_total / (1024**3))  # GB rounded
        resp.close()
        
        # Get network stats from RRD data (most recent data point)
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/rrddata?timeframe=hour"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            rrd_data = resp.json()['data']
            if rrd_data:
                latest = rrd_data[0]  # Most recent data point
                # netin/netout are in bytes/sec, convert to KB/s
                _metrics['netin'] = float(latest.get('netin', 0)) / 1024
                _metrics['netout'] = float(latest.get('netout', 0)) / 1024
        resp.close()
        
        # Get VM count
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/qemu"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            vms = resp.json()['data']
            _metrics['vm_total'] = len(vms)
            _metrics['vm_running'] = sum(1 for vm in vms if vm.get('status') == 'running')
        resp.close()
        
        # Get LXC count
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/lxc"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            lxcs = resp.json()['data']
            _metrics['lxc_total'] = len(lxcs)
            _metrics['lxc_running'] = sum(1 for lxc in lxcs if lxc.get('status') == 'running')
        resp.close()
        
        return True
    except Exception as e:
        print(f"Fetch error: {e}")
        return False

def event_handler(e):
    """Handle encoder/button events"""
    global _current_page
    e_code = e.get_code()
    
    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()
        old_page = _current_page
        if e_key == lv.KEY.LEFT:  # Scroll down = next page
            _current_page = (_current_page + 1) % 2
        elif e_key == lv.KEY.RIGHT:  # Scroll up = previous page
            _current_page = (_current_page - 1) % 2
        
        # Only redraw if page actually changed
        if _current_page != old_page:
            show_current_page()

def show_current_page():
    """Display the current page"""
    if _current_page == 0:
        show_main_page()
    else:
        show_debug_page()

def show_debug_page():
    """Page 1: Debug text with all raw values"""
    if not _scr:
        return
    
    _scr.clean()
    
    if not API_SECRET:
        error_label = lv.label(_scr)
        error_label.set_text("Not Configured\n\nGo to http://192.168.1.32/apps")
        error_label.center()
        error_label.set_style_text_color(lv.color_hex(0xFF6B6B), 0)
        return
    
    debug_label = lv.label(_scr)
    uptime_d = _metrics['uptime'] // 86400
    uptime_h = (_metrics['uptime'] % 86400) // 3600
    uptime_m = (_metrics['uptime'] % 3600) // 60
    uptime_s = _metrics['uptime'] % 60
    
    text = f"DEBUG DATA (Page 2/2)\n"
    text += f"Up: {uptime_d}d {uptime_h}:{uptime_m:02d}:{uptime_s:02d}\n"
    text += f"CPU: {_metrics['cpu']}%\n"
    text += f"RAM: {_metrics['mem_pct']}% ({_metrics['mem_used']}/{_metrics['mem_total']}GB)\n"
    text += f"Swap: {_metrics['swap_pct']}% ({_metrics['swap_used']}/{_metrics['swap_total']}GB)\n"
    text += f"Disk: {_metrics['disk_pct']}% ({_metrics['disk_used']}/{_metrics['disk_total']}GB)\n"
    text += f"Net Up: {_metrics['netout']:.0f} KB/s\n"
    text += f"Net Dn: {_metrics['netin']:.0f} KB/s\n"
    text += f"VMs: {_metrics['vm_running']}/{_metrics['vm_total']}\n"
    text += f"LXCs: {_metrics['lxc_running']}/{_metrics['lxc_total']}"
    
    debug_label.set_text(text)
    debug_label.align(lv.ALIGN.TOP_LEFT, 8, 8)
    debug_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)

def show_main_page():
    """Page 0: Main dashboard - 4 quadrants"""
    if not _scr:
        return
    
    _scr.clean()
    
    container_style = lv.style_t()
    container_style.init()
    container_style.set_pad_all(8)
    container_style.set_border_width(0)
    container_style.set_bg_color(lv.color_hex(0x2D2D2D))
    container_style.set_radius(10)
    
    # TOP LEFT - CPU with arc gauge
    tl = lv.obj(_scr)
    tl.set_size(155, 115)
    tl.align(lv.ALIGN.TOP_LEFT, 2, 2)
    tl.add_style(container_style, lv.PART.MAIN)
    
    # Arc gauge - smaller and positioned at top
    cpu_arc = lv.arc(tl)
    cpu_arc.set_size(75, 75)
    cpu_arc.align(lv.ALIGN.TOP_MID, 0, 0)
    cpu_arc.set_range(0, 100)
    cpu_arc.set_value(int(_metrics['cpu']))
    cpu_arc.set_bg_angles(0, 360)
    cpu_arc.set_rotation(270)
    cpu_arc.set_style_arc_width(7, lv.PART.MAIN)
    cpu_arc.set_style_arc_width(7, lv.PART.INDICATOR)
    cpu_arc.set_style_arc_color(lv.color_hex(0x404040), lv.PART.MAIN)
    cpu_arc.set_style_arc_color(lv.color_hex(0x00CED1), lv.PART.INDICATOR)
    cpu_arc.set_style_bg_opa(0, lv.PART.KNOB)  # Hide knob
    cpu_arc.set_style_pad_all(0, lv.PART.KNOB)
    cpu_arc.clear_flag(lv.obj.FLAG.CLICKABLE)
    
    # Center labels (positioned in arc center)
    cpu_pct_label = lv.label(tl)
    cpu_pct_label.set_text(f"{_metrics['cpu']}%")
    cpu_pct_label.align(lv.ALIGN.TOP_MID, 0, 18)
    cpu_pct_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    
    cpu_text_label = lv.label(tl)
    cpu_text_label.set_text("CPU")
    cpu_text_label.align(lv.ALIGN.TOP_MID, 0, 36)
    cpu_text_label.set_style_text_color(lv.color_hex(0x00CED1), 0)
    
    cpu_count_label = lv.label(tl)
    cpu_count_label.set_text("72 Cores")
    cpu_count_label.align(lv.ALIGN.BOTTOM_MID, 0, 1)
    cpu_count_label.set_style_text_color(lv.color_hex(0x808080), 0)
    
    # TOP RIGHT - RAM with arc gauge
    tr = lv.obj(_scr)
    tr.set_size(155, 115)
    tr.align(lv.ALIGN.TOP_RIGHT, -2, 2)
    tr.add_style(container_style, lv.PART.MAIN)
    
    # Arc gauge - smaller and positioned at top
    ram_arc = lv.arc(tr)
    ram_arc.set_size(75, 75)
    ram_arc.align(lv.ALIGN.TOP_MID, 0, 0)
    ram_arc.set_range(0, 100)
    ram_arc.set_value(int(_metrics['mem_pct']))
    ram_arc.set_bg_angles(0, 360)
    ram_arc.set_rotation(270)
    ram_arc.set_style_arc_width(7, lv.PART.MAIN)
    ram_arc.set_style_arc_width(7, lv.PART.INDICATOR)
    ram_arc.set_style_arc_color(lv.color_hex(0x404040), lv.PART.MAIN)
    ram_arc.set_style_arc_color(lv.color_hex(0x00CED1), lv.PART.INDICATOR)
    ram_arc.set_style_bg_opa(0, lv.PART.KNOB)  # Hide knob
    ram_arc.set_style_pad_all(0, lv.PART.KNOB)
    ram_arc.clear_flag(lv.obj.FLAG.CLICKABLE)
    
    # Center labels (positioned in arc center)
    ram_pct_label = lv.label(tr)
    ram_pct_label.set_text(f"{_metrics['mem_pct']}%")
    ram_pct_label.align(lv.ALIGN.TOP_MID, 0, 18)
    ram_pct_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    
    ram_text_label = lv.label(tr)
    ram_text_label.set_text("RAM")
    ram_text_label.align(lv.ALIGN.TOP_MID, 0, 36)
    ram_text_label.set_style_text_color(lv.color_hex(0x00CED1), 0)
    
    ram_detail_label = lv.label(tr)
    ram_detail_label.set_text(f"{_metrics['mem_used']}/{_metrics['mem_total']}GB")
    ram_detail_label.align(lv.ALIGN.BOTTOM_MID, 0, 1)
    ram_detail_label.set_style_text_color(lv.color_hex(0x808080), 0)
    
    # BOTTOM LEFT - Network with bars
    bl = lv.obj(_scr)
    bl.set_size(155, 118)
    bl.align(lv.ALIGN.BOTTOM_LEFT, 2, -2)
    bl.add_style(container_style, lv.PART.MAIN)
    
    # Download arrow
    net_in_img = lv.img(bl)
    net_in_img.set_src("A:apps/proxmox/resources/arrow_red.png")
    net_in_img.align(lv.ALIGN.TOP_LEFT, 6, 4)
    
    net_in_label = lv.label(bl)
    net_in_label.set_text(f"Dn: {_metrics['netin']:.0f} KB/s")
    net_in_label.align(lv.ALIGN.TOP_LEFT, 24, 4)
    net_in_label.set_style_text_color(lv.color_hex(0xFF6B6B), 0)
    
    net_in_bar = lv.bar(bl)
    net_in_bar.set_size(135, 12)
    net_in_bar.align(lv.ALIGN.TOP_LEFT, 10, 28)
    net_in_bar.set_value(min(100, int(_metrics['netin'] / 10)), lv.ANIM.OFF)
    net_in_bar.set_style_bg_color(lv.color_hex(0x404040), lv.PART.MAIN)
    net_in_bar.set_style_bg_color(lv.color_hex(0xFF6B6B), lv.PART.INDICATOR)
    
    # Upload arrow
    net_out_img = lv.img(bl)
    net_out_img.set_src("A:apps/proxmox/resources/arrow_green.png")
    net_out_img.align(lv.ALIGN.TOP_LEFT, 6, 52)
    
    net_out_label = lv.label(bl)
    net_out_label.set_text(f"Up: {_metrics['netout']:.0f} KB/s")
    net_out_label.align(lv.ALIGN.TOP_LEFT, 24, 52)
    net_out_label.set_style_text_color(lv.color_hex(0x00FF00), 0)
    
    net_out_bar = lv.bar(bl)
    net_out_bar.set_size(135, 12)
    net_out_bar.align(lv.ALIGN.TOP_LEFT, 10, 76)
    net_out_bar.set_value(min(100, int(_metrics['netout'] / 10)), lv.ANIM.OFF)
    net_out_bar.set_style_bg_color(lv.color_hex(0x404040), lv.PART.MAIN)
    net_out_bar.set_style_bg_color(lv.color_hex(0x00FF00), lv.PART.INDICATOR)
    
    # BOTTOM RIGHT - VMs and LXCs with bars
    br = lv.obj(_scr)
    br.set_size(155, 118)
    br.align(lv.ALIGN.BOTTOM_RIGHT, -2, -2)
    br.add_style(container_style, lv.PART.MAIN)
    
    vm_label = lv.label(br)
    vm_label.set_text(f"VMs: {_metrics['vm_running']}/{_metrics['vm_total']}")
    vm_label.align(lv.ALIGN.TOP_LEFT, 6, 4)
    vm_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    
    vm_pct = int((_metrics['vm_running'] * 100) / max(1, _metrics['vm_total']))
    vm_bar = lv.bar(br)
    vm_bar.set_size(135, 12)
    vm_bar.align(lv.ALIGN.TOP_LEFT, 10, 28)
    vm_bar.set_value(vm_pct, lv.ANIM.OFF)
    vm_bar.set_style_bg_color(lv.color_hex(0x404040), lv.PART.MAIN)
    vm_bar.set_style_bg_color(lv.color_hex(0x00CED1), lv.PART.INDICATOR)
    
    lxc_label = lv.label(br)
    lxc_label.set_text(f"LXCs: {_metrics['lxc_running']}/{_metrics['lxc_total']}")
    lxc_label.align(lv.ALIGN.TOP_LEFT, 6, 52)
    lxc_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    
    lxc_pct = int((_metrics['lxc_running'] * 100) / max(1, _metrics['lxc_total']))
    lxc_bar = lv.bar(br)
    lxc_bar.set_size(135, 12)
    lxc_bar.align(lv.ALIGN.TOP_LEFT, 10, 76)
    lxc_bar.set_value(lxc_pct, lv.ANIM.OFF)
    lxc_bar.set_style_bg_color(lv.color_hex(0x404040), lv.PART.MAIN)
    lxc_bar.set_style_bg_color(lv.color_hex(0x00CED1), lv.PART.INDICATOR)

async def on_boot(apm):
    """App lifecycle: Called when app first loaded"""
    global _app_mgr, PVE_HOST, NODE_NAME, API_TOKEN_ID, API_SECRET
    _app_mgr = apm
    
    # Load settings
    if _app_mgr:
        cfg = _app_mgr.config()
        if isinstance(cfg, dict):
            PVE_HOST = cfg.get("pve_host", PVE_HOST)
            NODE_NAME = cfg.get("node_name", NODE_NAME)
            API_TOKEN_ID = cfg.get("api_token_id", API_TOKEN_ID)
            API_SECRET = cfg.get("api_secret", API_SECRET)

async def on_start():
    """App lifecycle: Called when user enters app"""
    global _scr, _current_page
    
    if not _scr:
        _scr = lv.obj()
        _scr.set_style_bg_color(lv.color_hex3(0x000), lv.PART.MAIN)
        _scr.add_event(event_handler, lv.EVENT.ALL, None)
        
        # Setup focus group for encoder events
        group = lv.group_get_default()
        if group:
            group.add_obj(_scr)
            lv.group_focus_obj(_scr)
            group.set_editing(True)
        
        _app_mgr.enter_root_page()
        lv.screen_load(_scr)
    
    # Fetch initial data
    await fetch_proxmox_data()
    
    # Start on debug page
    _current_page = 0
    show_current_page()

async def on_stop():
    """App lifecycle: Called when user leaves app"""
    global _scr
    if _scr:
        _scr.clean()
        _scr.delete_async()
        _scr = None
        _app_mgr.leave_root_page()

async def on_running_foreground():
    """App lifecycle: Called repeatedly when app is active (~200ms)"""
    global _last_fetch_time
    
    now = utime.time()
    if now - _last_fetch_time >= POLL_TIME:
        _last_fetch_time = now
        await fetch_proxmox_data()
        show_current_page()  # Refresh current page with new data
