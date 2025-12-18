import lvgl as lv
import peripherals
import urequests as requests
import ujson
import utime

NAME = "Proxmox"
VERSION = "0.0.5"
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
    'lxc_total': 0
}

# UI widgets (stored for updates)
_cpu_label = None
_vm_label = None
_mem_label = None
_lxc_label = None
_net_in_label = None
_net_out_label = None

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
            
            mem_data = data.get('memory', {})
            mem_used = mem_data.get('used', 0)
            mem_total = mem_data.get('total', 1)
            _metrics['mem_pct'] = int((mem_used / mem_total) * 100)
            _metrics['mem_used'] = mem_used // (1024**3)  # GB
            _metrics['mem_total'] = mem_total // (1024**3)  # GB
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

def update_ui_values():
    """Update UI widgets with current metrics"""
    if _cpu_label:
        _cpu_label.set_text(f"CPU\n\n{_metrics['cpu']}%")
    if _vm_label:
        _vm_label.set_text(f"VM\n\n{_metrics['vm_running']}/{_metrics['vm_total']}")
    if _mem_label:
        _mem_label.set_text(f"RAM {_metrics['mem_pct']}%\n{_metrics['mem_used']}/{_metrics['mem_total']}GB\n\nLXC\n{_metrics['lxc_running']}/{_metrics['lxc_total']}")
    if _net_in_label:
        _net_in_label.set_text(f"Network\n\nUp: {_metrics['netout']:.0f} KB/s\n\nDn: {_metrics['netin']:.0f} KB/s")

async def show_ui():
    """Display the dashboard UI"""
    global _cpu_label, _vm_label, _mem_label, _lxc_label, _net_in_label, _net_out_label
    
    if not _scr: 
        return
    
    # Clear screen
    _scr.clean()
    lv.group_get_default().set_editing(False)
    
    # Check if configured
    if not API_SECRET:
        error_label = lv.label(_scr)
        error_label.set_text("Not Configured\n\nPlease configure\nProxmox settings at:\n\nhttp://192.168.1.32/apps")
        error_label.center()
        error_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        error_label.set_style_text_color(lv.color_hex(0xFF6B6B), 0)
        return
    
    # Container style  
    container_style = lv.style_t()
    container_style.init()
    container_style.set_pad_all(8)
    container_style.set_border_width(0)
    container_style.set_bg_color(lv.color_hex(0x2D2D2D))
    container_style.set_radius(10)
    
    # TOP LEFT - CPU
    tl = lv.obj(_scr)
    tl.set_size(155, 115)
    tl.align(lv.ALIGN.TOP_LEFT, 2, 2)
    tl.add_style(container_style, lv.PART.MAIN)
    
    _cpu_label = lv.label(tl)
    _cpu_label.set_text(f"CPU\n\n{_metrics['cpu']}%")
    _cpu_label.center()
    _cpu_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    _cpu_label.set_style_text_color(lv.color_hex(0x00CED1), 0)
    
    # TOP RIGHT - VM
    tr = lv.obj(_scr)
    tr.set_size(155, 115)
    tr.align(lv.ALIGN.TOP_RIGHT, -2, 2)
    tr.add_style(container_style, lv.PART.MAIN)
    
    _vm_label = lv.label(tr)
    _vm_label.set_text(f"VM\n\n{_metrics['vm_running']}/{_metrics['vm_total']}")
    _vm_label.center()
    _vm_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    _vm_label.set_style_text_color(lv.color_hex(0x00CED1), 0)
    
    # BOTTOM LEFT - Memory + LXC
    bl = lv.obj(_scr)
    bl.set_size(155, 118)
    bl.align(lv.ALIGN.BOTTOM_LEFT, 2, -2)
    bl.add_style(container_style, lv.PART.MAIN)
    
    _mem_label = lv.label(bl)
    _mem_label.set_text(f"RAM {_metrics['mem_pct']}%\n{_metrics['mem_used']}/{_metrics['mem_total']}GB\n\nLXC\n{_metrics['lxc_running']}/{_metrics['lxc_total']}")
    _mem_label.center()
    _mem_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    _mem_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    
    # BOTTOM RIGHT - Network
    br = lv.obj(_scr)
    br.set_size(155, 118)
    br.align(lv.ALIGN.BOTTOM_RIGHT, -2, -2)
    br.add_style(container_style, lv.PART.MAIN)
    
    _net_in_label = lv.label(br)
    _net_in_label.set_text(f"Network\n\nUp: {_metrics['netout']:.0f} KB/s\n\nDn: {_metrics['netin']:.0f} KB/s")
    _net_in_label.center()
    _net_in_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    _net_in_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)

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
    global _scr
    
    if not _scr:
        _scr = lv.obj()
        _scr.set_style_bg_color(lv.color_hex3(0x000), lv.PART.MAIN)
        _app_mgr.enter_root_page()
        lv.screen_load(_scr)
    
    await show_ui()
    
    # Fetch initial data
    await fetch_proxmox_data()
    update_ui_values()

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
        update_ui_values()
