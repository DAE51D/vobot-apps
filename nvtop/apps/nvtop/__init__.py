import lvgl as lv
import peripherals
import urequests as requests
import utime

# Note the case-sensitivity of this {NAME} when constructing the f'A:apps/{NAME}/resources/
# https://dock.myvobot.com/developer/getting_started/#important-resource-file-path-configuration
NAME = "nvtop"
VERSION = "1.0.0"
__version__ = VERSION
ICON = "A:apps/nvtop/resources/icon.png"
CAN_BE_AUTO_SWITCHED = True

_SCR_WIDTH, _SCR_HEIGHT = peripherals.screen.screen_resolution

# Default settings (see get_settings_json / .github/prompts/nvtop.prompt.md)
SERVER = "http://proxmox.home.lan:8039"  # vobot-gpu-daemon (or a gpu-hot instance)
GPU_INDEX = "0"
POLL_INTERVAL = 2  # seconds between /api/gpu-data fetches
PAGE_CYCLE_SECONDS = 5  # seconds between auto page cycles
AUTO_CYCLE = True

HISTORY_POINTS = 30  # ~60s of history at the default 2s poll interval
NUM_PAGES = 3
AUTO_CYCLE_PAGES = 2

# Globals
_scr = None
_app_mgr = None
_last_fetch_time = -999
_last_page_cycle_time = -999
_current_page = 0  # 0=gauges, 1=history chart, 2=details
_ui = None  # Cached LVGL widget references for fast updates/page switches
_styles = None  # Cached LVGL styles to avoid recreating (and GC issues)
_fetch_ok = False  # False until first successful fetch; drives OFFLINE indicator
_hist_util = []
_hist_mem = []
_metrics = {
    'name': '',
    'driver': '',
    'util': 0,
    'mem_pct': 0,
    'mem_used_gb': 0.0,
    'mem_total_gb': 0.0,
    'temp': 0,
    'power_draw': 0.0,
    'power_limit': 0.0,
    'fan': 0,
    'clock_gfx': 0,
    'clock_gfx_max': 0,
    'clock_mem': 0,
    'clock_mem_max': 0,
    'pcie_gen': '?',
    'pcie_gen_max': '?',
    'pcie_width': '?',
    'pcie_width_max': '?',
    'pstate': '?',
    'throttle': 'None',
}


def get_settings_json():
    return {
        "title": "nvtop / GPU Monitor Configuration",
        "form": [
            {
                "type": "input",
                "default": "http://proxmox.home.lan:8039",
                "caption": "GPU Daemon Server",
                "name": "server",
                "attributes": {"maxLength": 100, "placeholder": "http://proxmox.home.lan:8039"},
                "tip": "Base URL of vobot-gpu-daemon (or a gpu-hot instance - same JSON schema)"
            },
            {
                "type": "input",
                "default": "0",
                "caption": "GPU Index",
                "name": "gpu_index",
                "attributes": {"maxLength": 3, "placeholder": "0"},
                "tip": "Which GPU index to display on multi-GPU hosts"
            },
            {
                "type": "input",
                "default": "2",
                "caption": "Poll Interval (seconds)",
                "name": "poll_interval",
                "attributes": {"maxLength": 3, "placeholder": "2"},
                "tip": "How often to fetch GPU stats (1-60 seconds)"
            },
            {
                "type": "input",
                "default": "5",
                "caption": "Page Cycle (seconds)",
                "name": "page_cycle_seconds",
                "attributes": {"maxLength": 3, "placeholder": "5"},
                "tip": "How often to auto-advance between pages (2-60 seconds)"
            },
            {
                "type": "switch",
                "default": True,
                "caption": "Auto-Cycle Pages",
                "name": "auto_cycle",
                "tip": "Automatically cycle between Gauges / History / Details pages"
            }
        ]
    }


def _load_settings():
    """Read settings from app_mgr.config() into module globals."""
    global SERVER, GPU_INDEX, POLL_INTERVAL, PAGE_CYCLE_SECONDS, AUTO_CYCLE

    if not _app_mgr:
        return
    cfg = _app_mgr.config()
    if not isinstance(cfg, dict):
        return

    srv = cfg.get("server")
    if isinstance(srv, str) and srv:
        SERVER = srv.rstrip("/")

    idx = cfg.get("gpu_index")
    if isinstance(idx, str) and idx:
        GPU_INDEX = idx

    poll = cfg.get("poll_interval")
    if poll:
        try:
            poll = int(poll)
            if 1 <= poll <= 60:
                POLL_INTERVAL = poll
        except ValueError:
            print(f"Invalid poll_interval: {poll}")

    cycle = cfg.get("page_cycle_seconds")
    if cycle:
        try:
            cycle = int(cycle)
            if 2 <= cycle <= 60:
                PAGE_CYCLE_SECONDS = cycle
        except ValueError:
            print(f"Invalid page_cycle_seconds: {cycle}")

    auto = cfg.get("auto_cycle")
    if isinstance(auto, bool):
        AUTO_CYCLE = auto


async def fetch_gpu_data():
    """Fetch GPU telemetry from the configured daemon (vobot-gpu-daemon or gpu-hot)."""
    global _metrics, _fetch_ok, _hist_util, _hist_mem

    headers = {
        "Accept": "application/json",
        "Connection": "close",  # Helps avoid socket/resource leaks on MicroPython
    }
    url = f"{SERVER}/api/gpu-data"
    resp = None
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            _fetch_ok = False
            return False

        data = resp.json()
        gpus = data.get('gpus', {}) or {}
        g = gpus.get(GPU_INDEX)
        if g is None and gpus:
            # Configured index missing (e.g. renumbered) - fall back to first GPU reported.
            g = list(gpus.values())[0]
        if not g:
            _fetch_ok = False
            return False

        _metrics['name'] = g.get('name') or _metrics['name']
        _metrics['driver'] = g.get('driver_version') or _metrics['driver']
        _metrics['util'] = int(g.get('utilization') or 0)
        _metrics['mem_pct'] = int(g.get('memory_utilization') or 0)
        _metrics['mem_used_gb'] = (g.get('memory_used') or 0) / 1024.0
        _metrics['mem_total_gb'] = (g.get('memory_total') or 0) / 1024.0
        _metrics['temp'] = int(g.get('temperature') or 0)
        _metrics['power_draw'] = float(g.get('power_draw') or 0)
        _metrics['power_limit'] = float(g.get('power_limit') or 0)
        _metrics['fan'] = int(g.get('fan_speed') or 0)
        _metrics['clock_gfx'] = int(g.get('clock_graphics') or 0)
        _metrics['clock_gfx_max'] = int(g.get('clock_max_graphics') or 0)
        _metrics['clock_mem'] = int(g.get('clock_memory') or 0)
        _metrics['clock_mem_max'] = int(g.get('clock_max_memory') or 0)
        _metrics['pcie_gen'] = str(g.get('pcie_gen') or '?')
        _metrics['pcie_gen_max'] = str(g.get('pcie_gen_max') or '?')
        _metrics['pcie_width'] = str(g.get('pcie_width') or '?')
        _metrics['pcie_width_max'] = str(g.get('pcie_width_max') or '?')
        _metrics['pstate'] = str(g.get('performance_state') or '?')
        _metrics['throttle'] = str(g.get('throttle_reasons') or 'None')

        _hist_util.append(_metrics['util'])
        _hist_mem.append(_metrics['mem_pct'])
        if len(_hist_util) > HISTORY_POINTS:
            _hist_util.pop(0)
        if len(_hist_mem) > HISTORY_POINTS:
            _hist_mem.pop(0)

        _fetch_ok = True
        return True
    except Exception as e:
        print(f"Fetch error: {e}")
        _fetch_ok = False
        return False
    finally:
        if resp is not None:
            resp.close()


def event_handler(e):
    """Handle encoder/button events"""
    global _current_page, _last_page_cycle_time
    e_code = e.get_code()

    if e_code == lv.EVENT.FOCUSED:
        # Some app-switch paths clear group edit mode; restore it whenever
        # this screen regains focus so encoder KEY events continue arriving.
        group = lv.group_get_default()
        if group:
            group.set_editing(True)

    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()
        old_page = _current_page
        if e_key == lv.KEY.LEFT:  # Scroll down = next page
            _current_page = (_current_page + 1) % NUM_PAGES
        elif e_key == lv.KEY.RIGHT:  # Scroll up = previous page
            _current_page = (_current_page - 1) % NUM_PAGES

        if _current_page != old_page:
            # Manual navigation resets the auto-cycle timer so it doesn't
            # immediately flip the page again out from under the user.
            _last_page_cycle_time = utime.time()
            show_current_page()


def show_current_page():
    """Display the current page"""
    _set_page_visible(_current_page)
    _update_ui_for_current_page()


def _ensure_styles():
    """Create and retain LVGL styles (kept global so GC doesn't collect them)."""
    global _styles
    if _styles is not None:
        return

    container_style = lv.style_t()
    container_style.init()
    container_style.set_pad_all(8)
    container_style.set_border_width(0)
    container_style.set_bg_color(lv.color_hex(0x2D2D2D))
    container_style.set_radius(10)

    _styles = {
        'container': container_style,
        'c_white': lv.color_hex(0xFFFFFF),
        'c_gray': lv.color_hex(0x808080),
        'c_dark': lv.color_hex(0x404040),
        'c_accent': lv.color_hex(0x76B900),  # NVIDIA-ish green, matches the app icon
        'c_orange': lv.color_hex(0xFFA500),
        'c_red': lv.color_hex(0xFF6B6B),
    }


def _make_page(parent):
    page = lv.obj(parent)
    page.set_size(_SCR_WIDTH, _SCR_HEIGHT)
    page.align(lv.ALIGN.TOP_LEFT, 0, 0)
    page.set_style_bg_opa(0, lv.PART.MAIN)
    page.set_style_border_width(0, lv.PART.MAIN)
    page.set_style_pad_all(0, lv.PART.MAIN)
    page.clear_flag(lv.obj.FLAG.SCROLLABLE)
    return page


def _make_arc(parent, color):
    arc = lv.arc(parent)
    arc.set_size(102, 102)
    arc.align(lv.ALIGN.TOP_MID, 0, 2)
    arc.set_range(0, 100)
    arc.set_bg_angles(0, 360)
    arc.set_rotation(270)
    arc.set_style_arc_width(7, lv.PART.MAIN)
    arc.set_style_arc_width(7, lv.PART.INDICATOR)
    arc.set_style_arc_color(_styles['c_dark'], lv.PART.MAIN)
    arc.set_style_arc_color(color, lv.PART.INDICATOR)
    arc.set_style_bg_opa(0, lv.PART.KNOB)
    arc.set_style_pad_all(0, lv.PART.KNOB)
    arc.clear_flag(lv.obj.FLAG.CLICKABLE)
    return arc


def _make_tile(parent, align, x, y, w, h):
    tile = lv.obj(parent)
    tile.set_size(w, h)
    tile.align(align, x, y)
    tile.add_style(_styles['container'], lv.PART.MAIN)
    tile.clear_flag(lv.obj.FLAG.SCROLLABLE)
    if hasattr(tile, "set_scrollbar_mode"):
        tile.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
    return tile


def _ensure_ui():
    """Build all 3 pages once and cache widget references.

    Page switches become a cheap hide/show instead of scr.clean() + rebuild.
    """
    global _ui
    if _ui is not None or _scr is None:
        return

    _ensure_styles()

    page_gauges = _make_page(_scr)
    page_history = _make_page(_scr)
    page_details = _make_page(_scr)

    # --- Page 0: Gauges (2x2, same tile layout as the proxmox app) ---
    tl = _make_tile(page_gauges, lv.ALIGN.TOP_LEFT, 2, 2, 155, 115)
    util_arc = _make_arc(tl, _styles['c_accent'])
    util_pct_label = lv.label(tl)
    util_pct_label.align(lv.ALIGN.TOP_MID, 0, 28)
    util_pct_label.set_style_text_color(_styles['c_white'], 0)
    util_text_label = lv.label(tl)
    util_text_label.set_text("GPU")
    util_text_label.align(lv.ALIGN.TOP_MID, 0, 48)
    util_text_label.set_style_text_color(_styles['c_accent'], 0)

    tr = _make_tile(page_gauges, lv.ALIGN.TOP_RIGHT, -2, 2, 155, 115)
    mem_arc = _make_arc(tr, _styles['c_accent'])
    mem_pct_label = lv.label(tr)
    mem_pct_label.align(lv.ALIGN.TOP_MID, 0, 28)
    mem_pct_label.set_style_text_color(_styles['c_white'], 0)
    mem_text_label = lv.label(tr)
    mem_text_label.set_text("MEM")
    mem_text_label.align(lv.ALIGN.TOP_MID, 0, 48)
    mem_text_label.set_style_text_color(_styles['c_accent'], 0)

    bl = _make_tile(page_gauges, lv.ALIGN.BOTTOM_LEFT, 2, -2, 155, 118)
    temp_arc = _make_arc(bl, _styles['c_accent'])
    temp_pct_label = lv.label(bl)
    temp_pct_label.align(lv.ALIGN.TOP_MID, 0, 28)
    temp_pct_label.set_style_text_color(_styles['c_white'], 0)
    temp_text_label = lv.label(bl)
    temp_text_label.set_text("TEMP")
    temp_text_label.align(lv.ALIGN.TOP_MID, 0, 48)
    temp_text_label.set_style_text_color(_styles['c_accent'], 0)

    br = _make_tile(page_gauges, lv.ALIGN.BOTTOM_RIGHT, -2, -2, 155, 118)
    power_label = lv.label(br)
    power_label.align(lv.ALIGN.TOP_LEFT, 6, 4)
    power_label.set_style_text_color(_styles['c_white'], 0)
    power_bar = lv.bar(br)
    power_bar.set_size(135, 12)
    power_bar.align(lv.ALIGN.TOP_LEFT, 10, 28)
    power_bar.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    power_bar.set_style_bg_color(_styles['c_accent'], lv.PART.INDICATOR)
    mem_usage_label = lv.label(br)
    mem_usage_label.align(lv.ALIGN.TOP_LEFT, 6, 52)
    mem_usage_label.set_style_text_color(_styles['c_white'], 0)
    mem_usage_bar = lv.bar(br)
    mem_usage_bar.set_size(135, 12)
    mem_usage_bar.align(lv.ALIGN.TOP_LEFT, 10, 76)
    mem_usage_bar.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    mem_usage_bar.set_style_bg_color(_styles['c_accent'], lv.PART.INDICATOR)

    # --- Page 1: History chart ---
    hist_title_util = lv.label(page_history)
    hist_title_util.set_text("GPU %")
    hist_title_util.align(lv.ALIGN.TOP_LEFT, 4, 4)
    hist_title_util.set_style_text_color(_styles['c_accent'], 0)

    hist_title_mem = lv.label(page_history)
    hist_title_mem.set_text("MEM %")
    hist_title_mem.align(lv.ALIGN.TOP_RIGHT, -4, 4)
    hist_title_mem.set_style_text_color(_styles['c_orange'], 0)

    chart = lv.chart(page_history)
    chart.set_pos(2, 25)
    chart.set_size(_SCR_WIDTH - 4, _SCR_HEIGHT - 27)
    chart.clear_flag(lv.obj.FLAG.SCROLLABLE)
    chart.clear_flag(lv.obj.FLAG.CLICKABLE)
    chart.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    chart.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
    chart.set_style_border_width(0, lv.PART.MAIN)
    chart.set_style_pad_all(4, lv.PART.MAIN)
    chart.set_type(lv.chart.TYPE.LINE)
    chart.set_point_count(HISTORY_POINTS)
    try:
        chart.set_axis_range(lv.chart.AXIS.PRIMARY_Y, 0, 100)
    except Exception:
        chart.set_range(lv.chart.AXIS.PRIMARY_Y, 0, 100)
    try:
        chart.set_div_line_count(3, 0)
    except Exception:
        pass
    util_series = chart.add_series(_styles['c_accent'], lv.chart.AXIS.PRIMARY_Y)
    mem_series = chart.add_series(_styles['c_orange'], lv.chart.AXIS.PRIMARY_Y)

    # --- Page 2: Details ---
    details_header = lv.label(page_details)
    details_header.align(lv.ALIGN.TOP_LEFT, 6, 4)
    details_header.set_style_text_color(_styles['c_accent'], 0)
    details_header.set_long_mode(lv.label.LONG.WRAP)
    details_header.set_width(_SCR_WIDTH - 12)

    details_body = lv.label(page_details)
    details_body.align(lv.ALIGN.TOP_LEFT, 6, 54)
    details_body.set_style_text_color(_styles['c_white'], 0)
    details_body.set_long_mode(lv.label.LONG.WRAP)
    details_body.set_width(_SCR_WIDTH - 12)

    # --- Status overlay: shown on every page when the daemon is unreachable ---
    offline_label = lv.label(_scr)
    offline_label.set_text("OFFLINE")
    offline_label.align(lv.ALIGN.TOP_RIGHT, -4, 2)
    offline_label.set_style_text_color(_styles['c_red'], 0)
    offline_label.add_flag(lv.obj.FLAG.HIDDEN)

    _ui = {
        'page_gauges': page_gauges,
        'page_history': page_history,
        'page_details': page_details,
        'util_arc': util_arc,
        'util_pct_label': util_pct_label,
        'mem_arc': mem_arc,
        'mem_pct_label': mem_pct_label,
        'temp_arc': temp_arc,
        'temp_pct_label': temp_pct_label,
        'power_label': power_label,
        'power_bar': power_bar,
        'mem_usage_label': mem_usage_label,
        'mem_usage_bar': mem_usage_bar,
        'chart': chart,
        'util_series': util_series,
        'mem_series': mem_series,
        'details_header': details_header,
        'details_body': details_body,
        'offline_label': offline_label,
    }

    # Start with only the gauges page visible to avoid initial page overlap.
    _ui['page_history'].add_flag(lv.obj.FLAG.HIDDEN)
    _ui['page_details'].add_flag(lv.obj.FLAG.HIDDEN)


def _set_page_visible(page_index):
    global _ui
    if _scr is None:
        return
    _ensure_ui()
    if _ui is None:
        return

    pages = (_ui['page_gauges'], _ui['page_history'], _ui['page_details'])
    for i, page in enumerate(pages):
        if page is None:
            continue
        if i == page_index:
            page.clear_flag(lv.obj.FLAG.HIDDEN)
        else:
            page.add_flag(lv.obj.FLAG.HIDDEN)


def _fill_history_chart():
    """Push the rolling util/mem history buffers into the Page 1 chart series."""
    n = len(_hist_util)
    none_val = getattr(lv.chart, "POINT_NONE", getattr(lv, "CHART_POINT_NONE", 0))
    for i in range(HISTORY_POINTS):
        if i < n:
            _ui['chart'].set_value_by_id(_ui['util_series'], i, int(_hist_util[i]))
            _ui['chart'].set_value_by_id(_ui['mem_series'], i, int(_hist_mem[i]))
        else:
            _ui['chart'].set_value_by_id(_ui['util_series'], i, none_val)
            _ui['chart'].set_value_by_id(_ui['mem_series'], i, none_val)


def _update_ui_for_current_page():
    global _ui
    if _scr is None:
        return
    _ensure_ui()
    if _ui is None:
        return

    if _fetch_ok:
        _ui['offline_label'].add_flag(lv.obj.FLAG.HIDDEN)
    else:
        _ui['offline_label'].clear_flag(lv.obj.FLAG.HIDDEN)

    if _current_page == 0:
        util = int(_metrics['util'])
        mem_pct = int(_metrics['mem_pct'])
        temp = int(_metrics['temp'])
        power_draw = float(_metrics['power_draw'])
        power_limit = float(_metrics['power_limit'])
        mem_used_gb = _metrics['mem_used_gb']
        mem_total_gb = _metrics['mem_total_gb']

        _ui['util_arc'].set_value(util)
        _ui['util_pct_label'].set_text(f"{util}%")

        _ui['mem_arc'].set_value(mem_pct)
        _ui['mem_pct_label'].set_text(f"{mem_pct}%")

        _ui['temp_arc'].set_value(min(100, temp))
        _ui['temp_pct_label'].set_text(f"{temp}C")
        temp_color = _styles['c_red'] if temp >= 80 else _styles['c_accent']
        _ui['temp_arc'].set_style_arc_color(temp_color, lv.PART.INDICATOR)

        power_pct = int((power_draw * 100) / power_limit) if power_limit > 0 else 0
        _ui['power_label'].set_text(f"Power: {power_draw:.0f}/{power_limit:.0f}W")
        _ui['power_bar'].set_value(min(100, power_pct), lv.ANIM.OFF)

        _ui['mem_usage_label'].set_text(f"Mem: {mem_used_gb:.1f}/{mem_total_gb:.1f}G")
        _ui['mem_usage_bar'].set_value(min(100, mem_pct), lv.ANIM.OFF)

    elif _current_page == 1:
        _fill_history_chart()

    else:  # page 2: details
        name = _metrics['name'] or "GPU"
        driver = _metrics['driver'] or "?"
        _ui['details_header'].set_text(f"{name}\nDriver {driver}")

        clock_gfx = _metrics['clock_gfx']
        clock_gfx_max = _metrics['clock_gfx_max']
        clock_mem = _metrics['clock_mem']
        clock_mem_max = _metrics['clock_mem_max']
        fan_pct = _metrics['fan']
        pcie_gen = _metrics['pcie_gen']
        pcie_width = _metrics['pcie_width']
        pcie_gen_max = _metrics['pcie_gen_max']
        pcie_width_max = _metrics['pcie_width_max']
        pstate = _metrics['pstate']
        throttle = _metrics['throttle']

        lines = [
            f"Clock GFX: {clock_gfx}/{clock_gfx_max} MHz",
            f"Clock MEM: {clock_mem}/{clock_mem_max} MHz",
            f"Fan: {fan_pct}%",
            f"PCIe: Gen{pcie_gen}x{pcie_width} (max Gen{pcie_gen_max}x{pcie_width_max})",
            f"State: {pstate}",
            f"Throttle: {throttle}",
        ]
        _ui['details_body'].set_text("\n".join(lines))


async def on_boot(apm):
    """App lifecycle: Called when app is first loaded"""
    global _app_mgr
    _app_mgr = apm
    _load_settings()


async def on_start():
    """App lifecycle: Called when user enters app"""
    global _scr, _current_page, _last_page_cycle_time

    # Reload settings every time app starts (in case user changed them via web UI)
    _load_settings()

    if not _scr:
        _scr = lv.obj()
        _scr.set_style_bg_color(lv.color_hex3(0x000), lv.PART.MAIN)
        _scr.add_event(event_handler, lv.EVENT.ALL, None)

    # Always restore focus and screen load on app start/resume so the rotary
    # encoder keeps sending KEY events after app switches.
    group = lv.group_get_default()
    if group:
        try:
            group.add_obj(_scr)
        except Exception:
            pass
        lv.group_focus_obj(_scr)
        group.set_editing(True)

    _app_mgr.enter_root_page()
    lv.scr_load(_scr)

    # Re-assert focus after screen load because LVGL can move focus as part of
    # root-page transitions, which would stop KEY events from reaching _scr.
    group = lv.group_get_default()
    if group:
        lv.group_focus_obj(_scr)
        group.set_editing(True)

    # Build the UI once. Subsequent refreshes only update existing widgets.
    _ensure_ui()

    _current_page = 0
    _last_page_cycle_time = utime.time()
    show_current_page()

    # Fetch initial data so the UI isn't empty on entry
    await fetch_gpu_data()
    show_current_page()


async def on_stop():
    """App lifecycle: Called when user leaves app"""
    global _scr, _app_mgr, _ui, _styles

    if _app_mgr:
        _app_mgr.leave_root_page()

    if _scr:
        _scr.clean()
        _scr = None
        _ui = None
        _styles = None


async def on_running_foreground():
    """App lifecycle: Called repeatedly when app is active (~200ms)"""
    global _last_fetch_time, _last_page_cycle_time, _current_page

    now = utime.time()

    if now - _last_fetch_time >= POLL_INTERVAL:
        _last_fetch_time = now
        await fetch_gpu_data()
        _update_ui_for_current_page()

    if AUTO_CYCLE and now - _last_page_cycle_time >= PAGE_CYCLE_SECONDS:
        _last_page_cycle_time = now
        if _current_page >= AUTO_CYCLE_PAGES:
            _current_page = 0
        else:
            _current_page = (_current_page + 1) % AUTO_CYCLE_PAGES
        show_current_page()
