"""
ntfy Notification Viewer for Vobot Mini Dock
Fetches messages in on_running_foreground, not on startup
"""
import lvgl as lv
import peripherals
import urequests as requests
import ujson
import utime
import clocktime
try:
    import uasyncio as asyncio
except Exception:
    asyncio = None

VERSION = "1.1.2"
__version__ = VERSION  # Expose version for web UI
GIT_COMMIT = "unknown"  # stamped at deploy time from `git rev-parse --short HEAD`
NAME = "ntfy"
# A file path or data (bytes type) of the logo image for this app.
# If not specified, the default icon will be applied.
ICON = "A:apps/ntfy/resources/icon.png"
CAN_BE_AUTO_SWITCHED = True

NTFY_SERVER = "http://ntfy.home.lan"
NTFY_TOPIC = "general"  # Comma-separated topics (ntfy requires at least one)
MAX_MESSAGES = 5
CONNECTION_MODE = "long-poll"  # polling | long-poll
fetch_interval = 10

SCR_WIDTH, SCR_HEIGHT = peripherals.screen.screen_resolution

# --- Layout ---
BANNER_H = 32
FOOTER_H = 22
FOOTER_Y = SCR_HEIGHT - FOOTER_H - 5  # -5: the footer band was getting clipped by the bottom edge
CONTENT_Y = BANNER_H + 8
CONTENT_BOTTOM = FOOTER_Y - 2
PAGER_MAX = 8  # beyond this many messages, rely on the x/y counter instead of dots
COUNTER_W = 46  # fixed right-aligned footer slot for "x/y" (up to "50/50")
FOOTER_RIGHT_INSET = 10 + COUNTER_W + 4  # pager sits just left of the counter slot
FOOTER_TEXT_NUDGE = 5  # dots/pager/mode-dot sit slightly high vs. the footer text baseline
SCROLL_STEP = 40  # px per encoder click while scrolling a long message
FOOTER_ALT_INTERVAL = 4  # seconds between alternating the footer between host and channel

# --- Palette ---
# Muted per-priority banner colors (icon/text sit on top, so kept dark enough for contrast)
PRIO_INFO = {
    5: {"name": "Critical", "icon": "A:apps/ntfy/resources/max.png", "banner": 0x8C2020, "accent": 0xE24B4A},
    4: {"name": "High", "icon": "A:apps/ntfy/resources/high.png", "banner": 0x9A5A0A, "accent": 0xF0A030},
    3: {"name": "Normal", "icon": "A:apps/ntfy/resources/default.png", "banner": 0x0F5A5A, "accent": 0x2FBFBF},
    2: {"name": "Low", "icon": "A:apps/ntfy/resources/low.png", "banner": 0x4A5560, "accent": 0x8FA0B0},
    1: {"name": "Min", "icon": "A:apps/ntfy/resources/min.png", "banner": 0x3A3A3A, "accent": 0x707070},
}
IDLE_BANNER = 0x262626
ERROR_BANNER = 0x4A1B1B
BG_BLACK = 0x000000
TEXT_TITLE = 0xF2F2F0
TEXT_BODY = 0x9A9A97
TEXT_MUTED = 0x707070
STATUS_RED = 0xE24B4A
STATUS_GREEN = 0x2FFF6A  # bright/saturated so it's unmistakable next to the gray "read" dot
STATUS_READ = 0x8A8A88
MODE_LIVE = 0x4488FF   # long-poll (subscription stays open), resting color
MODE_POLL = 0x666666   # polling (checks on an interval), resting color
MODE_BUSY = 0xF0C020   # either mode, while a request is actually in flight
PAGER_OFF = 0x3A3A3A

app_mgr = None  # Application manager (set in on_boot)
scr = None

# Widget refs (built once in on_start)
banner = None
banner_icon = None
banner_label = None
counter_label = None
time_label = None
status_dot = None
FONT_SMALL = None  # smaller font for metadata (time/channel/footer/counter), if this firmware has one
content_panel = None
content_label = None
scroll_mode = False  # ENTER toggles this: LEFT/RIGHT then scroll the message instead of paging
mode_dot = None
footer_label = None
footer_state = 0  # rotates footer_label: 0=host, 1=channel/topic, 2=build commit
footer_alt_time = -999
pager_dots = []  # up to PAGER_MAX small pill/dot widgets

recolor_ok = False  # whether lv.label.set_recolor() is available on this firmware

last_fetch_time = -999  # Force first fetch immediately
messages = []
current_index = 0

new_badge_time = 0
NEW_BADGE_TIMEOUT = 5  # seconds
last_time_seen = 0

# Self-healing: recover from stale connections after the ntfy server restarts
# (e.g. weekly LXC backup). Mirrors the "toggle WiFi off/on" fix needed on Android.
consecutive_failures = 0
WIFI_BOUNCE_THRESHOLD = 3   # consecutive failed fetches before bouncing WiFi
WIFI_BOUNCE_COOLDOWN = 30   # seconds to wait before allowing another bounce
last_bounce_time = -999


def _banner_name(name):
    return f"{name} (scroll)" if scroll_mode else name


def event_handler(e):
    """Encoder rotation: pages between messages, or scrolls the current one in scroll_mode.
    Encoder press (ENTER) toggles between the two."""
    global current_index, messages, new_badge_time, scroll_mode

    e_code = e.get_code()
    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()
        print(f"Key: {e_key}")

        if not messages:
            return

        if e_key == lv.KEY.ENTER:
            scroll_mode = not scroll_mode
            print(f"scroll_mode: {scroll_mode}")
            try:
                info = PRIO_INFO.get(messages[current_index].get('priority', 3), PRIO_INFO[3])
                banner_label.set_text(_banner_name(info['name']))
                if not scroll_mode and content_panel:
                    content_panel.scroll_to(0, 0, lv.ANIM.ON)
            except Exception:
                pass
            return

        if scroll_mode:
            try:
                if e_key == lv.KEY.RIGHT:  # scroll further into the message
                    content_panel.scroll_by(0, -SCROLL_STEP, lv.ANIM.ON)
                elif e_key == lv.KEY.LEFT:  # scroll back toward the top
                    content_panel.scroll_by(0, SCROLL_STEP, lv.ANIM.ON)
            except Exception:
                pass
            return

        moved = False
        if e_key == lv.KEY.RIGHT:  # Right = newer
            if current_index > 0:
                current_index -= 1
                moved = True
                print(f"< Message {current_index + 1}/{len(messages)}")
        elif e_key == lv.KEY.LEFT:  # Left = older
            if current_index < len(messages) - 1:
                current_index += 1
                moved = True
                print(f"> Message {current_index + 1}/{len(messages)}")

        if moved:
            # Manual navigation acknowledges the "new message" badge
            new_badge_time = 0
            update_display()
    elif e_code == lv.EVENT.FOCUSED:
        # Enable edit mode when focused
        if not lv.group_get_default().get_editing():
            lv.group_get_default().set_editing(True)


def format_time(timestamp):
    """Format Unix timestamp to dd/mm 12-hour time with am/pm"""
    try:
        tz_offset = clocktime.tzoffset()
        local_timestamp = timestamp + tz_offset
        t = utime.localtime(local_timestamp)
        month = t[1]
        day = t[2]
        hour24 = t[3]
        minute = t[4]
        ampm = "AM" if hour24 < 12 else "PM"
        hour12 = hour24 % 12
        if hour12 == 0:
            hour12 = 12
        return f"{day:02d}/{month:02d} {hour12}:{minute:02d} {ampm}"
    except Exception:
        return "--/-- --:--"


def _round_obj(parent):
    """A tiny fully-rounded rect used for status/mode dots and pager segments."""
    o = lv.obj(parent)
    o.set_style_border_width(0, lv.PART.MAIN)
    o.set_style_radius(100, lv.PART.MAIN)  # clamped to a circle/pill by LVGL
    o.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
    o.clear_flag(lv.obj.FLAG.SCROLLABLE)
    o.clear_flag(lv.obj.FLAG.CLICKABLE)
    return o


def refresh_status_dot():
    """Always visible: red = last fetch failed, green = unread, gray = read/idle."""
    global status_dot
    if not status_dot:
        return
    try:
        now = utime.time()
        if consecutive_failures > 0:
            color = STATUS_RED
        elif new_badge_time and (now - new_badge_time) < NEW_BADGE_TIMEOUT:
            color = STATUS_GREEN
        else:
            color = STATUS_READ
        status_dot.set_style_bg_color(lv.color_hex(color), lv.PART.MAIN)
        status_dot.clear_flag(lv.obj.FLAG.HIDDEN)
    except Exception:
        pass


def set_mode_dot(busy):
    """Yellow while a request is in flight; otherwise its resting mode color."""
    if not mode_dot:
        return
    try:
        if busy:
            mode_dot.set_style_bg_color(lv.color_hex(MODE_BUSY), lv.PART.MAIN)
        else:
            mode_dot.set_style_bg_color(
                lv.color_hex(MODE_LIVE if CONNECTION_MODE == "long-poll" else MODE_POLL), lv.PART.MAIN
            )
    except Exception:
        pass


def refresh_footer_label():
    """One footer line, rotating between the server host, the current channel/topic,
    and the running build's git commit every FOOTER_ALT_INTERVAL seconds, instead of
    squeezing all three into one row at once."""
    if not footer_label:
        return
    try:
        if footer_state == 1 and messages and current_index < len(messages):
            text = messages[current_index].get('topic', '') or NTFY_TOPIC
        elif footer_state == 2:
            text = f"build {GIT_COMMIT}"
        else:
            host = NTFY_SERVER.rstrip("/") or NTFY_SERVER
            for prefix in ("https://", "http://"):
                if host.startswith(prefix):
                    host = host[len(prefix):]
                    break
            text = host
        footer_label.set_text(text)
    except Exception:
        pass


def layout_pager(count, active_idx):
    """Footer pager, right-aligned.

    <=PAGER_MAX messages: one static dot per message, active one drawn as a wide pill.
    >PAGER_MAX messages: a fixed track with a thumb that slides proportionally to
    active_idx/count, so large caches (e.g. a busy Arr-stack topic) still show
    continuous position feedback instead of an unreadable smear of tiny dots.
    """
    if not pager_dots:
        return
    if count <= 1:
        for seg in pager_dots:
            seg.add_flag(lv.obj.FLAG.HIDDEN)
        return

    accent = PRIO_INFO.get(messages[active_idx].get('priority', 3), PRIO_INFO[3])['accent'] if messages else PAGER_OFF

    if count > PAGER_MAX:
        track_w, track_h, thumb_w, thumb_h = 70, 3, 14, 5
        y_track = FOOTER_Y + (FOOTER_H - track_h) // 2 + FOOTER_TEXT_NUDGE
        y_thumb = FOOTER_Y + (FOOTER_H - thumb_h) // 2 + FOOTER_TEXT_NUDGE
        x_track = SCR_WIDTH - FOOTER_RIGHT_INSET - track_w

        track, thumb = pager_dots[0], pager_dots[1]
        track.set_size(track_w, track_h)
        track.set_pos(x_track, y_track)
        track.set_style_bg_color(lv.color_hex(PAGER_OFF), lv.PART.MAIN)
        track.clear_flag(lv.obj.FLAG.HIDDEN)

        thumb_travel = track_w - thumb_w
        thumb_x = x_track + int(thumb_travel * (active_idx / (count - 1)))
        thumb.set_size(thumb_w, thumb_h)
        thumb.set_pos(thumb_x, y_thumb)
        thumb.set_style_bg_color(lv.color_hex(accent), lv.PART.MAIN)
        thumb.clear_flag(lv.obj.FLAG.HIDDEN)

        for seg in pager_dots[2:]:
            seg.add_flag(lv.obj.FLAG.HIDDEN)
        return

    dot_w, dash_w, seg_h, gap = 5, 14, 5, 4
    total_w = sum(dash_w if i == active_idx else dot_w for i in range(count)) + gap * (count - 1)
    x = SCR_WIDTH - FOOTER_RIGHT_INSET - total_w
    y = FOOTER_Y + (FOOTER_H - seg_h) // 2 + FOOTER_TEXT_NUDGE

    for i in range(PAGER_MAX):
        seg = pager_dots[i]
        if i >= count:
            seg.add_flag(lv.obj.FLAG.HIDDEN)
            continue
        w = dash_w if i == active_idx else dot_w
        seg.set_size(w, seg_h)
        seg.set_pos(x, y)
        seg.set_style_bg_color(lv.color_hex(accent if i == active_idx else PAGER_OFF), lv.PART.MAIN)
        seg.clear_flag(lv.obj.FLAG.HIDDEN)
        x += w + gap


def update_display():
    """Update UI with current message"""
    global messages, current_index

    refresh_footer_label()

    if not messages or current_index >= len(messages):
        banner.set_style_bg_color(lv.color_hex(ERROR_BANNER if consecutive_failures > 0 else IDLE_BANNER), lv.PART.MAIN)
        banner_icon.add_flag(lv.obj.FLAG.HIDDEN)
        banner_label.set_text("ntfy")
        time_label.set_text("")
        counter_label.set_text("")
        if consecutive_failures > 0:
            content_label.set_text(
                f"#{STATUS_RED:06x} Connection problem#\n#{TEXT_BODY:06x} Retrying in the background...#"
                if recolor_ok else "Connection problem\nRetrying in the background..."
            )
        else:
            content_label.set_text("No messages yet.\nWaiting for notifications...")
        content_label.set_style_text_color(lv.color_hex(TEXT_MUTED), lv.PART.MAIN)
        try:
            content_panel.scroll_to(0, 0, lv.ANIM.OFF)
        except Exception:
            pass
        layout_pager(0, 0)
        refresh_status_dot()
        return

    msg = messages[current_index]
    prio = msg.get('priority', 3)
    info = PRIO_INFO.get(prio, PRIO_INFO[3])

    # Banner: icon, unread/error dot, priority name (left) + timestamp (right)
    banner.set_style_bg_color(lv.color_hex(info['banner']), lv.PART.MAIN)
    try:
        banner_icon.set_src(info['icon'])
        banner_icon.clear_flag(lv.obj.FLAG.HIDDEN)
    except Exception:
        pass
    banner_label.set_text(_banner_name(info['name']))
    time_label.set_text(format_time(msg.get('time', 0)))

    # Footer counter, right next to the pager since both describe list position
    counter_label.set_text(f"{current_index + 1}/{len(messages)}")

    # Content: title (bright) + body (muted), single label so height stays dynamic
    title = (msg.get('title', '') or msg.get('topic', '') or '').replace('#', "'")
    body = (msg.get('message', '') or '').replace('#', "'")
    if len(title) > 60:
        title = title[:57] + "..."
    if len(body) > 220:
        body = body[:217] + "..."

    if title and body:
        text = f"#{TEXT_TITLE:06x} {title}#\n#{TEXT_BODY:06x} {body}#" if recolor_ok else f"{title}\n{body}"
    elif title:
        text = f"#{TEXT_TITLE:06x} {title}#" if recolor_ok else title
    elif body:
        text = f"#{TEXT_BODY:06x} {body}#" if recolor_ok else body
    else:
        text = "(no content)"
    content_label.set_text(text)
    content_label.set_style_text_color(lv.color_hex(TEXT_TITLE), lv.PART.MAIN)
    try:
        content_panel.scroll_to(0, 0, lv.ANIM.OFF)  # always render new/changed content from the top
    except Exception:
        pass

    layout_pager(len(messages), current_index)
    refresh_status_dot()


async def on_boot(apm):
    """Called when app is first loaded - store app manager"""
    global app_mgr
    app_mgr = apm
    print(f"=== ntfy on_boot() === app_mgr: {app_mgr}")


async def on_start():
    """Called when app starts - set up UI and load config"""
    global scr, banner, banner_icon, banner_label, counter_label, time_label, status_dot
    global content_panel, content_label, mode_dot, footer_label, pager_dots, recolor_ok, FONT_SMALL
    global NTFY_SERVER, NTFY_TOPIC, MAX_MESSAGES, fetch_interval, CONNECTION_MODE, last_fetch_time

    # Force an immediate fetch on the next foreground tick instead of waiting out
    # whatever's left of the throttle window from before the app was backgrounded.
    last_fetch_time = -999

    print("=== ntfy on_start() ===")
    print(f"app_mgr: {app_mgr}")

    try:
        # Load persisted settings from web setup
        try:
            if app_mgr:
                cfg = app_mgr.config() if hasattr(app_mgr, "config") else {}
                print(f"Config loaded: {cfg}")
                if isinstance(cfg, dict):
                    srv = cfg.get("server")
                    if isinstance(srv, str) and srv:
                        NTFY_SERVER = srv
                    top = cfg.get("topic")
                    if isinstance(top, str):
                        topics_raw = top.strip()
                        if topics_raw:
                            topics_list = [t.strip() for t in topics_raw.split(',') if t.strip()]
                            NTFY_TOPIC = ','.join(topics_list) if topics_list else "general"
                        else:
                            NTFY_TOPIC = "general"
                    mm = cfg.get("max_messages")
                    if mm:
                        try:
                            mm = int(mm)
                            if 1 <= mm <= 50:
                                MAX_MESSAGES = mm
                        except (ValueError, TypeError):
                            pass
                    fi = cfg.get("fetch_interval")
                    if fi:
                        try:
                            fi = int(fi)
                            if 2 <= fi <= 120:
                                fetch_interval = fi
                        except (ValueError, TypeError):
                            pass
                    cm = cfg.get("connection_mode")
                    if isinstance(cm, str) and cm in ("polling", "long-poll"):
                        CONNECTION_MODE = cm
            else:
                print("WARNING: app_mgr is None - config will not load")
        except Exception as e:
            print(f"Config load error: {e}")

        scr = lv.obj()
        scr.set_style_bg_color(lv.color_hex(BG_BLACK), lv.PART.MAIN)
        scr.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
        scr.clear_flag(lv.obj.FLAG.SCROLLABLE)
        if hasattr(scr, "set_scrollbar_mode"):
            scr.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Smaller font for metadata (time/channel/footer/counter) if this firmware has one built
        # in; headline elements (priority name, title/body) stay at the theme default size.
        for _fname in ("font_montserrat_12", "font_montserrat_14"):
            try:
                FONT_SMALL = getattr(lv, _fname)
                break
            except Exception:
                continue

        # --- Banner: icon, unread/error dot, priority name (left), timestamp (right) ---
        banner = lv.obj(scr)
        banner.set_pos(0, 0)
        banner.set_size(SCR_WIDTH, BANNER_H)
        banner.set_style_radius(0, lv.PART.MAIN)
        banner.set_style_border_width(0, lv.PART.MAIN)
        banner.set_style_pad_all(0, lv.PART.MAIN)
        banner.set_style_bg_color(lv.color_hex(IDLE_BANNER), lv.PART.MAIN)
        banner.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
        banner.clear_flag(lv.obj.FLAG.SCROLLABLE)

        banner_icon = lv.img(banner)
        banner_icon.set_src("A:apps/ntfy/resources/default.png")
        banner_icon.align(lv.ALIGN.LEFT_MID, 4, 0)
        banner_icon.add_flag(lv.obj.FLAG.HIDDEN)

        status_dot = _round_obj(banner)
        status_dot.set_size(8, 8)
        status_dot.align(lv.ALIGN.LEFT_MID, 30, 0)
        status_dot.add_flag(lv.obj.FLAG.HIDDEN)

        banner_label = lv.label(banner)
        banner_label.set_text("ntfy")
        banner_label.align(lv.ALIGN.LEFT_MID, 44, 0)
        banner_label.set_style_text_color(lv.color_hex(TEXT_TITLE), lv.PART.MAIN)

        time_label = lv.label(banner)
        time_label.set_text("")
        time_label.align(lv.ALIGN.RIGHT_MID, -10, 0)
        time_label.set_style_text_color(lv.color_hex(0xE8E8E8), lv.PART.MAIN)
        if FONT_SMALL:
            try:
                time_label.set_style_text_font(FONT_SMALL, lv.PART.MAIN)
            except Exception:
                pass

        # --- Content: scrollable panel so long messages are never clipped/hidden.
        # ENTER toggles scroll_mode; while off, the encoder still pages between messages. ---
        content_panel = lv.obj(scr)
        content_panel.set_pos(0, CONTENT_Y)
        content_panel.set_size(SCR_WIDTH, CONTENT_BOTTOM - CONTENT_Y)
        content_panel.set_style_bg_opa(0, lv.PART.MAIN)
        content_panel.set_style_border_width(0, lv.PART.MAIN)
        content_panel.set_style_pad_all(0, lv.PART.MAIN)
        content_panel.set_style_radius(0, lv.PART.MAIN)
        content_panel.clear_flag(lv.obj.FLAG.CLICKABLE)

        content_label = lv.label(content_panel)
        content_label.set_text("Fetching messages...")
        content_label.set_pos(10, 6)
        content_label.set_width(SCR_WIDTH - 20)
        content_label.set_style_text_color(lv.color_hex(TEXT_MUTED), lv.PART.MAIN)
        content_label.set_long_mode(lv.label.LONG.WRAP)
        content_label.set_style_text_line_space(3, lv.PART.MAIN)
        try:
            content_label.set_recolor(True)
            recolor_ok = True
        except Exception:
            recolor_ok = False
        print(f"Label recolor supported: {recolor_ok}")

        # --- Footer: connection-mode dot + host/channel (alternating, left), pager + x/y counter (right) ---
        mode_dot = _round_obj(scr)
        mode_dot.set_size(8, 8)
        mode_dot.set_pos(10, FOOTER_Y + 7 + FOOTER_TEXT_NUDGE)
        set_mode_dot(busy=False)

        footer_label = lv.label(scr)
        footer_label.set_pos(22, FOOTER_Y + 4)
        footer_label.set_width(SCR_WIDTH - 22 - FOOTER_RIGHT_INSET - 87)
        try:
            footer_label.set_long_mode(lv.label.LONG.DOT)  # single-line ellipsis
        except Exception:
            footer_label.set_long_mode(lv.label.LONG.WRAP)
        footer_label.set_style_text_color(lv.color_hex(TEXT_MUTED), lv.PART.MAIN)
        if FONT_SMALL:
            try:
                footer_label.set_style_text_font(FONT_SMALL, lv.PART.MAIN)
            except Exception:
                pass

        pager_dots = [_round_obj(scr) for _ in range(PAGER_MAX)]
        for seg in pager_dots:
            seg.add_flag(lv.obj.FLAG.HIDDEN)

        counter_label = lv.label(scr)
        counter_label.set_text("")
        counter_label.set_pos(SCR_WIDTH - 10 - COUNTER_W, FOOTER_Y + 4)
        counter_label.set_width(COUNTER_W)
        try:
            counter_label.set_style_text_align(lv.TEXT_ALIGN.RIGHT, lv.PART.MAIN)
        except Exception:
            pass
        counter_label.set_style_text_color(lv.color_hex(0xE8E8E8), lv.PART.MAIN)
        if FONT_SMALL:
            try:
                counter_label.set_style_text_font(FONT_SMALL, lv.PART.MAIN)
            except Exception:
                pass

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


def wifi_bounce():
    """Toggle the WiFi radio off/on to clear a stale connection.

    The ntfy LXC restarting (weekly backup, host reboot) leaves the ESP32's
    lwIP/ARP state pointing at a dead socket, so requests keep failing even
    though http://ntfy.home.lan works fine from other hosts. Power-cycling
    the Vobot fixes it; this does the same recovery without a full reboot.
    ESP-IDF keeps the last AP config in flash, so connect() needs no args.
    """
    global last_bounce_time
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        print("ntfy: bouncing WiFi to recover stuck connection...")
        wlan.disconnect()
        wlan.active(False)
        utime.sleep(1)
        wlan.active(True)
        wlan.connect()
        last_bounce_time = utime.time()
    except Exception as e:
        print(f"ntfy: WiFi bounce failed: {e}")


async def on_running_foreground():
    """Called every ~200ms - fetch messages here, not on startup"""
    global last_fetch_time, messages, current_index, new_badge_time, last_time_seen
    global consecutive_failures, last_bounce_time, scroll_mode
    global footer_state, footer_alt_time

    now = utime.time()

    # Rotate the footer between host/channel/build commit on its own cadence,
    # independent of the fetch throttle below (cheap: a time comparison plus an
    # occasional set_text).
    if now - footer_alt_time >= FOOTER_ALT_INTERVAL:
        footer_alt_time = now
        footer_state = (footer_state + 1) % 3
        refresh_footer_label()

    # Throttled polling/long-poll timing
    if now - last_fetch_time < fetch_interval:
        # Auto-hide the unread dot after its timeout so it doesn't linger forever
        if new_badge_time and (now - new_badge_time) >= NEW_BADGE_TIMEOUT:
            new_badge_time = 0
            refresh_status_dot()
        return  # Too soon to fetch again

    last_fetch_time = now
    print(f"Fetching messages at {now}...")

    try:
        base_server = NTFY_SERVER.rstrip("/") or NTFY_SERVER
        path = f"{base_server}/{NTFY_TOPIC}/json"

        if CONNECTION_MODE == "long-poll":
            url = f"{path}?poll=1&since={last_time_seen or '24h'}"
            print("Mode: Long-poll (subscription)")
        else:
            url = f"{path}?poll=1&since=24h"
            print("Mode: Polling")
        print(f"GET {url}")
        set_mode_dot(busy=True)
        if asyncio:
            try:
                # requests.get() below is a blocking call, not a real awaited one, so
                # nothing repaints while it runs. Yield here first so the LVGL redraw
                # task (if it shares this event loop) gets a chance to actually paint
                # the yellow dot before we block - otherwise busy=True/False can both
                # apply between two frames and never visibly render.
                await asyncio.sleep_ms(150)
            except Exception:
                pass
        try:
            response = requests.get(url, timeout=10)
        finally:
            set_mode_dot(busy=False)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            consecutive_failures = 0
            print("Got 200, reading...")

            try:
                data = response.content
                print(f"Read {len(data)} bytes")

                if data:
                    text = data.decode('utf-8')
                    lines = [ln for ln in text.strip().split('\n') if ln]

                    if lines:
                        new_messages = []
                        for line in lines:
                            try:
                                msg = ujson.loads(line)
                                new_messages.append(msg)
                            except Exception as parse_err:
                                print(f"Parse error: {parse_err}")
                                continue

                        previous_latest_time = messages[0].get('time', 0) if messages else 0

                        if CONNECTION_MODE == "long-poll":
                            # Merge: new messages at front + keep old cached messages,
                            # deduplicated by id so long-poll replays don't double up.
                            new_messages.reverse()  # Newest first
                            existing_ids = {msg.get('id') for msg in messages if msg.get('id')}
                            unique_new = []
                            for msg in new_messages:
                                msg_id = msg.get('id')
                                if not msg_id or msg_id not in existing_ids:
                                    unique_new.append(msg)
                                    if msg_id:
                                        existing_ids.add(msg_id)
                            messages = unique_new + messages
                            messages = messages[:MAX_MESSAGES]
                        else:
                            # Polling: take last MAX_MESSAGES from fetch
                            messages = new_messages[-MAX_MESSAGES:]
                            messages.reverse()  # Newest first

                        if messages:
                            last_time_seen = messages[0].get('time', last_time_seen) or last_time_seen

                        latest_time = messages[0].get('time', 0) if messages else 0
                        if latest_time and latest_time > previous_latest_time:
                            current_index = 0
                            scroll_mode = False  # a fresh message always starts at the top, browse mode
                            new_badge_time = now
                        else:
                            new_badge_time = 0

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
                consecutive_failures += 1
                update_display()
        else:
            print(f"HTTP {response.status_code}")
            consecutive_failures += 1
            update_display()

        response.close()

    except Exception as e:
        print(f"Fetch failed: {e}")
        consecutive_failures += 1
        update_display()

    print(f"ntfy: consecutive_failures={consecutive_failures}")
    if (consecutive_failures >= WIFI_BOUNCE_THRESHOLD
            and (now - last_bounce_time) >= WIFI_BOUNCE_COOLDOWN):
        wifi_bounce()


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
