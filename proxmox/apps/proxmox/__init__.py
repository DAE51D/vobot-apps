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
VM_THRESHOLD = 0  # Alert if VMs running below this count (0 = disabled)
LXC_THRESHOLD = 0  # Alert if LXCs running below this count (0 = disabled)

# Globals
_scr = None
_app_mgr = None
_last_fetch_time = -999
_current_page = 0  # 0=main dashboard, 1=debug data
_ui = None  # Cached LVGL widget references for fast updates/page switches
_styles = None  # Cached LVGL styles to avoid recreating (and GC issues)
_last_rrd_fetch_time = -999  # RRD payload is large; allow throttling independently
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
                "attributes": {"maxLength": 50, "placeholder": "proxmox.home.lan:8006"},
                "tip": "Hostname:port of Proxmox server"
            },
            {
                "type": "input",
                "default": "pve",
                "caption": "Node Name",
                "name": "node_name",
                "attributes": {"maxLength": 30, "placeholder": "pve"},
                "tip": "Name of the node to monitor"
            },
            {
                "type": "input",
                "default": "api@realm!token_id",
                "caption": "API Token ID",
                "name": "api_token_id",
                "attributes": {"maxLength": 50, "placeholder": "api@realm!token_id"},
                "tip": "API token ID api@realm!token_id"
            },
            {
                "type": "input",
                "default": "",
                "caption": "API Secret",
                "name": "api_secret",
                "attributes": {"maxLength": 36, "placeholder": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
                "tip": "API token secret (UUID)"
            },
            {
                "type": "input",
                "default": "0",
                "caption": "VM Threshold",
                "name": "vm_threshold",
                "attributes": {"maxLength": 3, "placeholder": "0"},
                "tip": "Alert if running VMs fall below this count (0 = disabled)"
            },
            {
                "type": "input",
                "default": "0",
                "caption": "LXC Threshold",
                "name": "lxc_threshold",
                "attributes": {"maxLength": 3, "placeholder": "0"},
                "tip": "Alert if running LXCs fall below this count (0 = disabled)"
            }
        ]
    }

async def fetch_proxmox_data():
    """Fetch metrics from Proxmox API"""
    global _metrics, PVE_HOST, NODE_NAME, API_TOKEN_ID, API_SECRET, _last_rrd_fetch_time
    
    if not API_SECRET:
        return False
    
    try:
        # Keep request headers minimal; never log the token/secret.
        headers = {
            "Authorization": f"PVEAPIToken={API_TOKEN_ID}={API_SECRET}",
            "Accept": "application/json",
            "Connection": "close",  # Helps avoid socket/resource leaks on MicroPython
        }
        
        # Get node status
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/status"
        resp = None
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('data', {})

                cpu_frac = data.get('cpu', 0) or 0
                _metrics['cpu'] = int(cpu_frac * 100)
                _metrics['uptime'] = data.get('uptime', 0) or 0

                mem_data = data.get('memory', {}) or {}
                mem_used = mem_data.get('used', 0) or 0
                mem_total = mem_data.get('total', 1) or 1
                _metrics['mem_pct'] = int((mem_used * 100) / mem_total)
                _metrics['mem_used'] = int(mem_used / (1024**3) + 0.5)  # GB rounded
                _metrics['mem_total'] = int(mem_total / (1024**3) + 0.99)  # GB rounded up

                swap_data = data.get('swap', {}) or {}
                swap_used = swap_data.get('used', 0) or 0
                swap_total = swap_data.get('total', 0) or 0
                _metrics['swap_pct'] = int((swap_used * 100) / swap_total) if swap_total > 0 else 0
                _metrics['swap_used'] = int(swap_used / (1024**3) + 0.5)  # GB rounded
                _metrics['swap_total'] = int(swap_total / (1024**3) + 0.5)  # GB rounded

                disk_data = data.get('rootfs', {}) or {}
                disk_used = disk_data.get('used', 0) or 0
                disk_total = disk_data.get('total', 1) or 1
                _metrics['disk_pct'] = int((disk_used * 100) / disk_total)
                _metrics['disk_used'] = int(disk_used / (1024**3) + 0.5)  # GB rounded
                _metrics['disk_total'] = int(disk_total / (1024**3) + 0.5)  # GB rounded
        finally:
            if resp is not None:
                resp.close()
        
        # Get network stats from RRD data.
        # This endpoint returns a larger payload; we throttle it a bit independently to reduce load.
        now = utime.time()
        if now - _last_rrd_fetch_time >= max(10, POLL_TIME):
            _last_rrd_fetch_time = now
            url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/rrddata?timeframe=hour"
            resp = None
            try:
                resp = requests.get(url, headers=headers)
                if resp.status_code == 200:
                    rrd_data = resp.json().get('data', [])
                    if rrd_data:
                        # Proxmox may return newest-first or oldest-first; pick the last valid sample.
                        latest = None
                        for point in rrd_data:
                            if point and (point.get('netin') is not None or point.get('netout') is not None):
                                latest = point
                        if latest is None:
                            latest = rrd_data[-1]
                        # netin/netout are bytes/sec; convert to KB/s.
                        _metrics['netin'] = (latest.get('netin', 0) or 0) / 1024
                        _metrics['netout'] = (latest.get('netout', 0) or 0) / 1024
            finally:
                if resp is not None:
                    resp.close()
        
        # Get VM count
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/qemu"
        resp = None
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                vms = resp.json().get('data', [])
                _metrics['vm_total'] = len(vms)
                _metrics['vm_running'] = sum(1 for vm in vms if vm.get('status') == 'running')
        finally:
            if resp is not None:
                resp.close()
        
        # Get LXC count
        url = f"https://{PVE_HOST}/api2/json/nodes/{NODE_NAME}/lxc"
        resp = None
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                lxcs = resp.json().get('data', [])
                _metrics['lxc_total'] = len(lxcs)
                _metrics['lxc_running'] = sum(1 for lxc in lxcs if lxc.get('status') == 'running')
        finally:
            if resp is not None:
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
        
        # Only switch if page actually changed.
        # This avoids expensive LVGL rebuilds and makes the wheel feel instant.
        if _current_page != old_page:
            show_current_page()

def show_current_page():
    """Display the current page"""
    # Fast page switch: toggle visibility instead of deleting/recreating widgets.
    _set_page_visible(_current_page)
    _update_ui_for_current_page()


def _ensure_styles():
    """Create and retain LVGL styles.

    Keeping a global reference prevents GC from collecting styles that are still
    attached to objects (and avoids re-creating styles on every refresh).
    """
    global _styles
    if _styles is not None:
        return

    container_style = lv.style_t()
    container_style.init()
    container_style.set_pad_all(8)
    container_style.set_border_width(0)
    container_style.set_bg_color(lv.color_hex(0x2D2D2D))
    container_style.set_radius(10)

    # Reuse color objects where possible to reduce allocations.
    _styles = {
        'container': container_style,
        'c_white': lv.color_hex(0xFFFFFF),
        'c_gray': lv.color_hex(0x808080),
        'c_dark': lv.color_hex(0x404040),
        'c_accent': lv.color_hex(0x00CED1),
        'c_red': lv.color_hex(0xFF6B6B),
        'c_green': lv.color_hex(0x00FF00),
    }


def _ensure_ui():
    """Build both pages once and cache widget references.

    This is the main performance win: page switches become a cheap hide/show
    instead of `_scr.clean()` + PNG decode + widget allocation.
    """
    global _ui
    if _ui is not None or _scr is None:
        return

    _ensure_styles()

    # Page containers (we show/hide these)
    page_main = lv.obj(_scr)
    page_main.set_size(_SCR_WIDTH, _SCR_HEIGHT)
    page_main.align(lv.ALIGN.TOP_LEFT, 0, 0)
    page_main.set_style_bg_opa(0, lv.PART.MAIN)
    page_main.set_style_border_width(0, lv.PART.MAIN)
    page_main.set_style_pad_all(0, lv.PART.MAIN)
    page_main.clear_flag(lv.obj.FLAG.SCROLLABLE)

    page_debug = lv.obj(_scr)
    page_debug.set_size(_SCR_WIDTH, _SCR_HEIGHT)
    page_debug.align(lv.ALIGN.TOP_LEFT, 0, 0)
    page_debug.set_style_bg_opa(0, lv.PART.MAIN)
    page_debug.set_style_border_width(0, lv.PART.MAIN)
    page_debug.set_style_pad_all(0, lv.PART.MAIN)
    page_debug.clear_flag(lv.obj.FLAG.SCROLLABLE)

    # --- Main page widgets (created once) ---
    c = _styles['container']
    
    # TOP LEFT - CPU
    tl = lv.obj(page_main)
    tl.set_size(155, 115)
    tl.align(lv.ALIGN.TOP_LEFT, 2, 2)
    tl.add_style(c, lv.PART.MAIN)

    cpu_arc = lv.arc(tl)
    cpu_arc.set_size(75, 75)
    cpu_arc.align(lv.ALIGN.TOP_MID, 0, 0)
    cpu_arc.set_range(0, 100)
    cpu_arc.set_bg_angles(0, 360)
    cpu_arc.set_rotation(270)
    cpu_arc.set_style_arc_width(7, lv.PART.MAIN)
    cpu_arc.set_style_arc_width(7, lv.PART.INDICATOR)
    cpu_arc.set_style_arc_color(_styles['c_dark'], lv.PART.MAIN)
    cpu_arc.set_style_arc_color(_styles['c_accent'], lv.PART.INDICATOR)
    cpu_arc.set_style_bg_opa(0, lv.PART.KNOB)
    cpu_arc.set_style_pad_all(0, lv.PART.KNOB)
    cpu_arc.clear_flag(lv.obj.FLAG.CLICKABLE)

    cpu_pct_label = lv.label(tl)
    cpu_pct_label.align(lv.ALIGN.TOP_MID, 0, 18)
    cpu_pct_label.set_style_text_color(_styles['c_white'], 0)

    cpu_text_label = lv.label(tl)
    cpu_text_label.set_text("CPU")
    cpu_text_label.align(lv.ALIGN.TOP_MID, 0, 36)
    cpu_text_label.set_style_text_color(_styles['c_accent'], 0)

    cpu_count_label = lv.label(tl)
    cpu_count_label.set_text("72 Cores")
    cpu_count_label.align(lv.ALIGN.BOTTOM_MID, 0, 1)
    cpu_count_label.set_style_text_color(_styles['c_gray'], 0)

    # TOP RIGHT - RAM
    tr = lv.obj(page_main)
    tr.set_size(155, 115)
    tr.align(lv.ALIGN.TOP_RIGHT, -2, 2)
    tr.add_style(c, lv.PART.MAIN)

    ram_arc = lv.arc(tr)
    ram_arc.set_size(75, 75)
    ram_arc.align(lv.ALIGN.TOP_MID, 0, 0)
    ram_arc.set_range(0, 100)
    ram_arc.set_bg_angles(0, 360)
    ram_arc.set_rotation(270)
    ram_arc.set_style_arc_width(7, lv.PART.MAIN)
    ram_arc.set_style_arc_width(7, lv.PART.INDICATOR)
    ram_arc.set_style_arc_color(_styles['c_dark'], lv.PART.MAIN)
    ram_arc.set_style_arc_color(_styles['c_accent'], lv.PART.INDICATOR)
    ram_arc.set_style_bg_opa(0, lv.PART.KNOB)
    ram_arc.set_style_pad_all(0, lv.PART.KNOB)
    ram_arc.clear_flag(lv.obj.FLAG.CLICKABLE)

    ram_pct_label = lv.label(tr)
    ram_pct_label.align(lv.ALIGN.TOP_MID, 0, 18)
    ram_pct_label.set_style_text_color(_styles['c_white'], 0)

    ram_text_label = lv.label(tr)
    ram_text_label.set_text("RAM")
    ram_text_label.align(lv.ALIGN.TOP_MID, 0, 36)
    ram_text_label.set_style_text_color(_styles['c_accent'], 0)

    ram_detail_label = lv.label(tr)
    ram_detail_label.align(lv.ALIGN.BOTTOM_MID, 0, 1)
    ram_detail_label.set_style_text_color(_styles['c_gray'], 0)

    # BOTTOM LEFT - Network
    bl = lv.obj(page_main)
    bl.set_size(155, 118)
    bl.align(lv.ALIGN.BOTTOM_LEFT, 2, -2)
    bl.add_style(c, lv.PART.MAIN)

    net_in_img = lv.img(bl)
    net_in_img.set_src("A:apps/proxmox/resources/arrow_red.png")
    net_in_img.align(lv.ALIGN.TOP_LEFT, 6, 4)

    net_in_label = lv.label(bl)
    net_in_label.align(lv.ALIGN.TOP_LEFT, 24, 4)
    net_in_label.set_style_text_color(_styles['c_red'], 0)

    net_in_bar = lv.bar(bl)
    net_in_bar.set_size(135, 12)
    net_in_bar.align(lv.ALIGN.TOP_LEFT, 10, 28)
    net_in_bar.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    net_in_bar.set_style_bg_color(_styles['c_red'], lv.PART.INDICATOR)

    net_out_img = lv.img(bl)
    net_out_img.set_src("A:apps/proxmox/resources/arrow_green.png")
    net_out_img.align(lv.ALIGN.TOP_LEFT, 6, 52)

    net_out_label = lv.label(bl)
    net_out_label.align(lv.ALIGN.TOP_LEFT, 24, 52)
    net_out_label.set_style_text_color(_styles['c_green'], 0)

    net_out_bar = lv.bar(bl)
    net_out_bar.set_size(135, 12)
    net_out_bar.align(lv.ALIGN.TOP_LEFT, 10, 76)
    net_out_bar.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    net_out_bar.set_style_bg_color(_styles['c_green'], lv.PART.INDICATOR)

    # BOTTOM RIGHT - VM/LXC
    br = lv.obj(page_main)
    br.set_size(155, 118)
    br.align(lv.ALIGN.BOTTOM_RIGHT, -2, -2)
    br.add_style(c, lv.PART.MAIN)

    vm_label = lv.label(br)
    vm_label.align(lv.ALIGN.TOP_LEFT, 6, 4)
    vm_label.set_style_text_color(_styles['c_white'], 0)

    vm_bar = lv.bar(br)
    vm_bar.set_size(135, 12)
    vm_bar.align(lv.ALIGN.TOP_LEFT, 10, 28)
    vm_bar.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    vm_bar.set_style_bg_color(_styles['c_accent'], lv.PART.INDICATOR)

    lxc_label = lv.label(br)
    lxc_label.align(lv.ALIGN.TOP_LEFT, 6, 52)
    lxc_label.set_style_text_color(_styles['c_white'], 0)

    lxc_bar = lv.bar(br)
    lxc_bar.set_size(135, 12)
    lxc_bar.align(lv.ALIGN.TOP_LEFT, 10, 76)
    lxc_bar.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    lxc_bar.set_style_bg_color(_styles['c_accent'], lv.PART.INDICATOR)

    # --- Debug page widgets (created once) ---
    debug_label = lv.label(page_debug)
    debug_label.align(lv.ALIGN.TOP_LEFT, 8, 8)
    debug_label.set_style_text_color(_styles['c_white'], 0)
    debug_label.set_long_mode(lv.label.LONG.WRAP)
    debug_label.set_width(_SCR_WIDTH - 16)

    error_label = lv.label(page_debug)
    error_label.center()
    error_label.set_style_text_color(_styles['c_red'], 0)
    error_label.add_flag(lv.obj.FLAG.HIDDEN)

    _ui = {
        'page_main': page_main,
        'page_debug': page_debug,
        'cpu_arc': cpu_arc,
        'cpu_pct_label': cpu_pct_label,
        'ram_arc': ram_arc,
        'ram_pct_label': ram_pct_label,
        'ram_detail_label': ram_detail_label,
        'net_in_label': net_in_label,
        'net_in_bar': net_in_bar,
        'net_out_label': net_out_label,
        'net_out_bar': net_out_bar,
        'vm_label': vm_label,
        'vm_bar': vm_bar,
        'lxc_label': lxc_label,
        'lxc_bar': lxc_bar,
        'debug_label': debug_label,
        'error_label': error_label,
    }


def _set_page_visible(page_index):
    global _ui
    if _scr is None:
        return
    _ensure_ui()
    if _ui is None:
        return

    if page_index == 0:
        _ui['page_main'].clear_flag(lv.obj.FLAG.HIDDEN)
        _ui['page_debug'].add_flag(lv.obj.FLAG.HIDDEN)
    else:
        _ui['page_debug'].clear_flag(lv.obj.FLAG.HIDDEN)
        _ui['page_main'].add_flag(lv.obj.FLAG.HIDDEN)


def _update_ui_for_current_page():
    # Update in-place instead of rebuilding. This keeps wheel transitions snappy.
    global _ui
    if _scr is None:
        return
    _ensure_ui()
    if _ui is None:
        return

    # Main page updates
    cpu = int(_metrics['cpu'])
    mem_pct = int(_metrics['mem_pct'])
    _ui['cpu_arc'].set_value(cpu)
    _ui['cpu_pct_label'].set_text(f"{cpu}%")

    _ui['ram_arc'].set_value(mem_pct)
    _ui['ram_pct_label'].set_text(f"{mem_pct}%")
    _ui['ram_detail_label'].set_text(f"{_metrics['mem_used']}/{_metrics['mem_total']}GB")

    netin = float(_metrics['netin'])
    netout = float(_metrics['netout'])
    _ui['net_in_label'].set_text(f"Dn: {netin:.0f} KB/s")
    _ui['net_out_label'].set_text(f"Up: {netout:.0f} KB/s")
    _ui['net_in_bar'].set_value(min(100, int(netin / 10)), lv.ANIM.OFF)
    _ui['net_out_bar'].set_value(min(100, int(netout / 10)), lv.ANIM.OFF)

    vm_total = int(_metrics['vm_total'])
    vm_running = int(_metrics['vm_running'])
    # Check VM threshold and update label/color
    vm_deficit = 0
    vm_alert = False
    if VM_THRESHOLD > 0 and vm_running < VM_THRESHOLD:
        vm_deficit = VM_THRESHOLD - vm_running
        vm_alert = True
        print(f"VM ALERT: running={vm_running} < threshold={VM_THRESHOLD}, deficit={vm_deficit}")
        _ui['vm_label'].set_text(f"VMs: {vm_running}-{vm_deficit}/{vm_total}")
        _ui['vm_bar'].set_style_bg_color(_styles['c_red'], lv.PART.INDICATOR)
    else:
        print(f"VM OK: running={vm_running}, threshold={VM_THRESHOLD}")
        _ui['vm_label'].set_text(f"VMs: {vm_running}/{vm_total}")
        _ui['vm_bar'].set_style_bg_color(_styles['c_accent'], lv.PART.INDICATOR)
    _ui['vm_bar'].set_value(int((vm_running * 100) / (vm_total if vm_total else 1)), lv.ANIM.OFF)

    lxc_total = int(_metrics['lxc_total'])
    lxc_running = int(_metrics['lxc_running'])
    # Check LXC threshold and update label/color
    lxc_deficit = 0
    lxc_alert = False
    if LXC_THRESHOLD > 0 and lxc_running < LXC_THRESHOLD:
        lxc_deficit = LXC_THRESHOLD - lxc_running
        lxc_alert = True
        print(f"LXC ALERT: running={lxc_running} < threshold={LXC_THRESHOLD}, deficit={lxc_deficit}")
        _ui['lxc_label'].set_text(f"LXCs: {lxc_running}-{lxc_deficit}/{lxc_total}")
        _ui['lxc_bar'].set_style_bg_color(_styles['c_red'], lv.PART.INDICATOR)
    else:
        print(f"LXC OK: running={lxc_running}, threshold={LXC_THRESHOLD}")
        _ui['lxc_label'].set_text(f"LXCs: {lxc_running}/{lxc_total}")
        _ui['lxc_bar'].set_style_bg_color(_styles['c_accent'], lv.PART.INDICATOR)
    _ui['lxc_bar'].set_value(int((lxc_running * 100) / (lxc_total if lxc_total else 1)), lv.ANIM.OFF)

    # Debug page updates
    if not API_SECRET:
        _ui['error_label'].set_text("Not Configured\n\nGo to /apps settings.")
        _ui['error_label'].clear_flag(lv.obj.FLAG.HIDDEN)
        _ui['debug_label'].add_flag(lv.obj.FLAG.HIDDEN)
    else:
        _ui['error_label'].add_flag(lv.obj.FLAG.HIDDEN)
        _ui['debug_label'].clear_flag(lv.obj.FLAG.HIDDEN)

        uptime = int(_metrics['uptime'])
        uptime_d = uptime // 86400
        uptime_h = (uptime % 86400) // 3600
        uptime_m = (uptime % 3600) // 60
        uptime_s = uptime % 60

        # Build the debug string with a list + join to reduce intermediate allocations.
        lines = [
            "DEBUG DATA (Page 2/2)",
            f"Up: {uptime_d}d {uptime_h}:{uptime_m:02d}:{uptime_s:02d}",
            f"CPU: {cpu}%",
            f"RAM: {mem_pct}% ({_metrics['mem_used']}/{_metrics['mem_total']}GB)",
            f"Swap: {_metrics['swap_pct']}% ({_metrics['swap_used']}/{_metrics['swap_total']}GB)",
            f"Disk: {_metrics['disk_pct']}% ({_metrics['disk_used']}/{_metrics['disk_total']}GB)",
            f"Net Up: {netout:.0f} KB/s",
            f"Net Dn: {netin:.0f} KB/s",
        ]
        
        # Add VM count with threshold if set
        vm_line = f"VMs: {vm_running}/{vm_total}"
        if VM_THRESHOLD > 0:
            vm_line += f" [{VM_THRESHOLD}]"
        lines.append(vm_line)
        
        # Add LXC count with threshold if set
        lxc_line = f"LXCs: {lxc_running}/{lxc_total}"
        if LXC_THRESHOLD > 0:
            lxc_line += f" [{LXC_THRESHOLD}]"
        lines.append(lxc_line)
        
        _ui['debug_label'].set_text("\n".join(lines))

def show_debug_page():
    """Page 1: Debug text.

    Kept for backwards-compat with existing calls, but now it's a fast visibility
    switch + text update (no full widget rebuild).
    """
    show_current_page()

def show_main_page():
    """Page 0: Main dashboard.

    Kept for backwards-compat with existing calls, but now it's a fast visibility
    switch + in-place update (no full widget rebuild).
    """
    show_current_page()

# (Reverted) No widget-caching updater; pages are rebuilt when shown

async def on_boot(apm):
    """App lifecycle: Called when app first loaded"""
    global _app_mgr, PVE_HOST, NODE_NAME, API_TOKEN_ID, API_SECRET, VM_THRESHOLD, LXC_THRESHOLD
    _app_mgr = apm
    
    # Load settings
    if _app_mgr:
        cfg = _app_mgr.config()
        if isinstance(cfg, dict):
            PVE_HOST = cfg.get("pve_host", PVE_HOST)
            NODE_NAME = cfg.get("node_name", NODE_NAME)
            API_TOKEN_ID = cfg.get("api_token_id", API_TOKEN_ID)
            API_SECRET = cfg.get("api_secret", API_SECRET)
            
            # Load thresholds
            vm_thresh = cfg.get("vm_threshold")
            if vm_thresh:
                try:
                    VM_THRESHOLD = int(vm_thresh)
                    print(f"Loaded VM_THRESHOLD: {VM_THRESHOLD}")
                except ValueError:
                    print(f"Invalid VM threshold value: {vm_thresh}")
            
            lxc_thresh = cfg.get("lxc_threshold")
            if lxc_thresh:
                try:
                    LXC_THRESHOLD = int(lxc_thresh)
                    print(f"Loaded LXC_THRESHOLD: {LXC_THRESHOLD}")
                except ValueError:
                    print(f"Invalid LXC threshold value: {lxc_thresh}")

async def on_start():
    """App lifecycle: Called when user enters app"""
    global _scr, _current_page, PVE_HOST, NODE_NAME, API_TOKEN_ID, API_SECRET, VM_THRESHOLD, LXC_THRESHOLD
    
    # Reload settings every time app starts (in case user changed them via web UI)
    if _app_mgr:
        cfg = _app_mgr.config()
        if isinstance(cfg, dict):
            PVE_HOST = cfg.get("pve_host", PVE_HOST)
            NODE_NAME = cfg.get("node_name", NODE_NAME)
            API_TOKEN_ID = cfg.get("api_token_id", API_TOKEN_ID)
            API_SECRET = cfg.get("api_secret", API_SECRET)
            
            # Load thresholds
            vm_thresh = cfg.get("vm_threshold")
            if vm_thresh:
                try:
                    VM_THRESHOLD = int(vm_thresh)
                    print(f"[on_start] Loaded VM_THRESHOLD: {VM_THRESHOLD}")
                except ValueError:
                    print(f"[on_start] Invalid VM threshold: {vm_thresh}")
            else:
                VM_THRESHOLD = 0
                print("[on_start] VM threshold not set, using 0")
            
            lxc_thresh = cfg.get("lxc_threshold")
            if lxc_thresh:
                try:
                    LXC_THRESHOLD = int(lxc_thresh)
                    print(f"[on_start] Loaded LXC_THRESHOLD: {LXC_THRESHOLD}")
                except ValueError:
                    print(f"[on_start] Invalid LXC threshold: {lxc_thresh}")
            else:
                LXC_THRESHOLD = 0
                print("[on_start] LXC threshold not set, using 0")
    
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

        # Build the UI once. Subsequent refreshes only update existing widgets.
        _ensure_ui()
    
    # Show UI immediately (page 0 = main dashboard with default/cached values)
    _current_page = 0
    show_current_page()
    
    # Fetch initial data in background (non-blocking so UI appears instantly)
    await fetch_proxmox_data()
    
    # Update UI with fresh data
    show_current_page()

async def on_stop():
    """App lifecycle: Called when user leaves app"""
    global _scr, _app_mgr, _ui, _styles
    
    # Fast exit: leave root page immediately so user sees app close
    if _app_mgr:
        _app_mgr.leave_root_page()
    
    # Clean up screen and widgets (non-blocking)
    if _scr:
        _scr.clean()
        _scr = None
        _ui = None
        _styles = None

async def on_running_foreground():
    """App lifecycle: Called repeatedly when app is active (~200ms)"""
    global _last_fetch_time
    
    now = utime.time()
    if now - _last_fetch_time >= POLL_TIME:
        _last_fetch_time = now
        await fetch_proxmox_data()
        # Update UI in-place with fresh data (no full rebuild).
        _update_ui_for_current_page()
