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
_cpu_slider = None
_cpu_label = None
_mem_slider = None
_mem_label = None
_net_in_slider = None
_net_in_label = None
_net_out_slider = None
_net_out_label = None
_vm_label = None
_lxc_label = None

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
            _metrics['mem_pct'] = int((data.get('memory', {}).get('used', 0) / data.get('memory', {}).get('total', 1)) * 100)
            _metrics['mem_used'] = data.get('memory', {}).get('used', 0) // (1024**3)  # GB
            _metrics['mem_total'] = data.get('memory', {}).get('total', 1) // (1024**3)  # GB
            _metrics['netin'] = data.get('netin', 0) // (1024**2)  # MB/s
            _metrics['netout'] = data.get('netout', 0) // (1024**2)  # MB/s
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
    if _cpu_slider:
        _cpu_slider.set_value(_metrics['cpu'], lv.ANIM.OFF)
    if _cpu_label:
        _cpu_label.set_text(f"{_metrics['cpu']}%")
    
    if _mem_slider:
        _mem_slider.set_value(_metrics['mem_pct'], lv.ANIM.OFF)
    if _mem_label:
        _mem_label.set_text(f"{_metrics['mem_used']}/{_metrics['mem_total']}GB")
    
    if _net_in_slider:
        _net_in_slider.set_value(min(_metrics['netin'], 100), lv.ANIM.OFF)
    if _net_in_label:
        _net_in_label.set_text(f"{_metrics['netin']}MB/s")
    
    if _net_out_slider:
        _net_out_slider.set_value(min(_metrics['netout'], 100), lv.ANIM.OFF)
    if _net_out_label:
        _net_out_label.set_text(f"{_metrics['netout']}MB/s")
    
    if _vm_label:
        _vm_label.set_text(f"VM: {_metrics['vm_running']}/{_metrics['vm_total']}")
    if _lxc_label:
        _lxc_label.set_text(f"LXC: {_metrics['lxc_running']}/{_metrics['lxc_total']}")

async def show_ui():
    """Display the dashboard UI"""
    global _cpu_slider, _cpu_label, _mem_slider, _mem_label
    global _net_in_slider, _net_in_label, _net_out_slider, _net_out_label
    global _vm_label, _lxc_label
    
    if not _scr: 
        return
    
    # Clear screen
    _scr.clean()
    lv.group_get_default().set_editing(False)
    
    # Create container style  
    container_style = lv.style_t()
    container_style.init()
    container_style.set_pad_all(0)
    container_style.set_border_width(0)
    container_style.set_bg_color(lv.color_hex3(0x000))
    
    # CPU container
    cpu_container = lv.obj(_scr)
    cpu_container.set_size(_SCR_WIDTH, 35)
    cpu_container.align(lv.ALIGN.TOP_LEFT, 0, 5)
    cpu_container.add_style(container_style, lv.PART.MAIN)
    
    cpu_title = lv.label(cpu_container)
    cpu_title.set_text("CPU")
    cpu_title.align(lv.ALIGN.LEFT_MID, 5, 0)
    
    _cpu_slider = lv.slider(cpu_container)
    _cpu_slider.set_size(160, 8)
    _cpu_slider.align(lv.ALIGN.CENTER, 0, 0)
    _cpu_slider.set_value(_metrics['cpu'], lv.ANIM.OFF)
    
    _cpu_label = lv.label(cpu_container)
    _cpu_label.set_text(f"{_metrics['cpu']}%")
    _cpu_label.align(lv.ALIGN.RIGHT_MID, -5, 0)
    
    # Memory container
    mem_container = lv.obj(_scr)
    mem_container.set_size(_SCR_WIDTH, 35)
    mem_container.align_to(cpu_container, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 0)
    mem_container.add_style(container_style, lv.PART.MAIN)
    
    mem_title = lv.label(mem_container)
    mem_title.set_text("RAM")
    mem_title.align(lv.ALIGN.LEFT_MID, 5, 0)
    
    _mem_slider = lv.slider(mem_container)
    _mem_slider.set_size(160, 8)
    _mem_slider.align(lv.ALIGN.CENTER, 0, 0)
    _mem_slider.set_value(_metrics['mem_pct'], lv.ANIM.OFF)
    
    _mem_label = lv.label(mem_container)
    _mem_label.set_text(f"{_metrics['mem_used']}/{_metrics['mem_total']}GB")
    _mem_label.align(lv.ALIGN.RIGHT_MID, -5, 0)
    
    # Network In container
    netin_container = lv.obj(_scr)
    netin_container.set_size(_SCR_WIDTH, 35)
    netin_container.align_to(mem_container, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 0)
    netin_container.add_style(container_style, lv.PART.MAIN)
    
    netin_title = lv.label(netin_container)
    netin_title.set_text("IN")
    netin_title.align(lv.ALIGN.LEFT_MID, 5, 0)
    
    _net_in_slider = lv.slider(netin_container)
    _net_in_slider.set_size(160, 8)
    _net_in_slider.align(lv.ALIGN.CENTER, 0, 0)
    _net_in_slider.set_value(min(_metrics['netin'], 100), lv.ANIM.OFF)
    
    _net_in_label = lv.label(netin_container)
    _net_in_label.set_text(f"{_metrics['netin']}MB/s")
    _net_in_label.align(lv.ALIGN.RIGHT_MID, -5, 0)
    
    # Network Out container
    netout_container = lv.obj(_scr)
    netout_container.set_size(_SCR_WIDTH, 35)
    netout_container.align_to(netin_container, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 0)
    netout_container.add_style(container_style, lv.PART.MAIN)
    
    netout_title = lv.label(netout_container)
    netout_title.set_text("OUT")
    netout_title.align(lv.ALIGN.LEFT_MID, 5, 0)
    
    _net_out_slider = lv.slider(netout_container)
    _net_out_slider.set_size(160, 8)
    _net_out_slider.align(lv.ALIGN.CENTER, 0, 0)
    _net_out_slider.set_value(min(_metrics['netout'], 100), lv.ANIM.OFF)
    
    _net_out_label = lv.label(netout_container)
    _net_out_label.set_text(f"{_metrics['netout']}MB/s")
    _net_out_label.align(lv.ALIGN.RIGHT_MID, -5, 0)
    
    # VM/LXC summary at bottom
    summary_container = lv.obj(_scr)
    summary_container.set_size(_SCR_WIDTH, 50)
    summary_container.align_to(netout_container, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
    summary_container.add_style(container_style, lv.PART.MAIN)
    
    _vm_label = lv.label(summary_container)
    _vm_label.set_text(f"VM: {_metrics['vm_running']}/{_metrics['vm_total']}")
    _vm_label.align(lv.ALIGN.LEFT_MID, 40, 0)
    
    _lxc_label = lv.label(summary_container)
    _lxc_label.set_text(f"LXC: {_metrics['lxc_running']}/{_metrics['lxc_total']}")
    _lxc_label.align(lv.ALIGN.RIGHT_MID, -40, 0)

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
