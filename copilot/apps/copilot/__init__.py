import lvgl as lv
import peripherals
import urequests as requests
import utime
import clocktime
try:
    import uasyncio as asyncio
except Exception:
    asyncio = None

# Note the case-sensitivity of this {NAME} when constructing the f'A:apps/{NAME}/resources/
# https://dock.myvobot.com/developer/getting_started/#important-resource-file-path-configuration
NAME = "copilot"
VERSION = "1.0.2"
__version__ = VERSION
GIT_COMMIT = "unknown"  # stamped at deploy time from `git rev-parse --short HEAD`
ICON = "A:apps/copilot/resources/icon.png"
CAN_BE_AUTO_SWITCHED = True

_SCR_WIDTH, _SCR_HEIGHT = peripherals.screen.screen_resolution

# --- Default settings (overridden by web config in on_boot/on_start) ---
GITHUB_PAT = ""
GITHUB_USER = ""
POLL_MINUTES = 30          # how often to hit the GitHub API
CAP_SPEND = 100.0          # $ max for the "Spend" / "Net Billed" gauges
CAP_SAVINGS = 70.0         # $ max for the "Savings" gauge
CAP_CREDITS = 9000         # credits max for the "Credits" gauge
# NOTE: no reset-day/hour setting - GitHub's metered billing cycle always resets at
# 00:00:00 UTC on the 1st of the month, fixed regardless of plan/account
# (https://docs.github.com/en/copilot/reference/copilot-billing/billing-cycle).
# The progress/countdown page computes this directly instead of asking the user for it.
# NOTE: no "budget cap" setting is derivable either - GitHub's Budgets API (the one
# place spending caps are queryable) is org/enterprise-only, no personal-account
# equivalent exists (https://docs.github.com/en/rest/billing/budgets).

HISTORY_POINTS = 31         # cap: at most one calendar month of daily points

# --- Globals ---
_scr = None
_app_mgr = None
_current_page = 0
_num_pages = 3
_ui = None
_styles = None
FONT_SMALL = None
_last_fetch_time = -999   # forces an immediate fetch on first on_running_foreground tick
_last_error = None
_dot_hide_at = -999       # when to auto-hide the busy/result dot, or -999 if not scheduled

_summary = {
    'gross': 0.0,
    'discount': 0.0,
    'net': 0.0,
    'gross_qty': 0.0,
}

_history_dates = []       # "YYYY-MM-DD" oldest -> newest, len <= HISTORY_POINTS
_history_daily_amt = []
_history_daily_qty = []
_history_cum_amt = []
_history_cum_qty = []


def get_settings_json():
    return {
        "title": "Copilot Spend Configuration",
        "form": [
            {
                "type": "input",
                "default": "",
                "caption": "GitHub PAT (Plan/read-only scope)",
                "name": "github_pat",
                "attributes": {"maxLength": 100, "placeholder": "github_pat_..."},
                "tip": "Fine-grained PAT with 'Plan' account permission (read-only). Create at github.com/settings/personal-access-tokens/new"
            },
            {
                "type": "input",
                "default": "",
                "caption": "GitHub Username",
                "name": "github_user",
                "attributes": {"maxLength": 40, "placeholder": "e.g. DAE51D"},
                "tip": "Your GitHub login (billing endpoints are per-user, not /user/)"
            },
            {
                "type": "input",
                "default": "30",
                "caption": "Poll Interval (minutes)",
                "name": "poll_minutes",
                "attributes": {"maxLength": 4, "placeholder": "30"},
                "tip": "How often to refresh from GitHub (5-1440). Billing data updates slowly."
            },
            {
                "type": "input",
                "default": "100",
                "caption": "Monthly Spend Cap ($)",
                "name": "cap_spend",
                "attributes": {"maxLength": 8, "placeholder": "100"},
                "tip": "Gauge max for Spend / Net Billed. Not exposed by GitHub's API - set to your plan's cap."
            },
            {
                "type": "input",
                "default": "70",
                "caption": "Included Savings Cap ($)",
                "name": "cap_savings",
                "attributes": {"maxLength": 8, "placeholder": "70"},
                "tip": "Gauge max for the Savings gauge."
            },
            {
                "type": "input",
                "default": "9000",
                "caption": "Credits Cap",
                "name": "cap_credits",
                "attributes": {"maxLength": 8, "placeholder": "9000"},
                "tip": "Gauge max for the Credits gauge."
            }
        ]
    }


def _load_settings(cfg):
    """Parse the web-config dict into the module globals, with validation/fallbacks."""
    global GITHUB_PAT, GITHUB_USER, POLL_MINUTES, CAP_SPEND, CAP_SAVINGS, CAP_CREDITS

    if not isinstance(cfg, dict):
        return

    pat = cfg.get("github_pat")
    if isinstance(pat, str):
        GITHUB_PAT = pat.strip()

    user = cfg.get("github_user")
    if isinstance(user, str):
        GITHUB_USER = user.strip()

    def _int(name, default, lo, hi):
        raw = cfg.get(name)
        if raw:
            try:
                v = int(raw)
                if lo <= v <= hi:
                    return v
            except (ValueError, TypeError):
                pass
        return default

    def _float(name, default, lo, hi):
        raw = cfg.get(name)
        if raw:
            try:
                v = float(raw)
                if lo <= v <= hi:
                    return v
            except (ValueError, TypeError):
                pass
        return default

    POLL_MINUTES = _int("poll_minutes", 30, 5, 1440)
    CAP_SPEND = _float("cap_spend", 100.0, 1.0, 100000.0)
    CAP_SAVINGS = _float("cap_savings", 70.0, 1.0, 100000.0)
    CAP_CREDITS = _int("cap_credits", 9000, 1, 10000000)


def _headers():
    return {
        "Authorization": "Bearer %s" % GITHUB_PAT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Connection": "close",
        # GitHub's REST API returns 403 Forbidden on any request missing a
        # User-Agent header - curl sends one implicitly so this never showed up
        # when testing with curl by hand.
        "User-Agent": "vobot-copilot-app",
    }


async def fetch_summary():
    """Current-month aggregate totals -> drives the 4 gauges."""
    global _summary, _last_error
    if not GITHUB_PAT or not GITHUB_USER:
        _last_error = "Not configured"
        return False

    url = "https://api.github.com/users/%s/settings/billing/usage/summary" % GITHUB_USER
    resp = None
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('usageItems', []) or []
            gross = discount = net = qty = 0.0
            for it in items:
                if (it.get('product') or '').lower() != 'copilot':
                    continue
                gross += it.get('grossAmount', 0) or 0
                discount += it.get('discountAmount', 0) or 0
                net += it.get('netAmount', 0) or 0
                qty += it.get('grossQuantity', 0) or 0
            _summary['gross'] = gross
            _summary['discount'] = discount
            _summary['net'] = net
            _summary['gross_qty'] = qty
            return True
        else:
            _last_error = "Summary HTTP %d" % resp.status_code
            return False
    except Exception as e:
        _last_error = "Summary fetch error: %s" % e
        print("copilot: summary fetch error:", e)
        return False
    finally:
        if resp is not None:
            resp.close()


async def fetch_history():
    """Daily usage rows for the current month -> drives the charts."""
    global _history_dates, _history_daily_amt, _history_daily_qty
    global _history_cum_amt, _history_cum_qty, _last_error

    if not GITHUB_PAT or not GITHUB_USER:
        return False

    now = clocktime.datetime()  # (Y, M, D, h, mi, s, wday, yday), already local
    year, month = now[0], now[1]
    url = "https://api.github.com/users/%s/settings/billing/usage?year=%d&month=%d" % (GITHUB_USER, year, month)
    resp = None
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('usageItems', []) or []

            by_day = {}
            for it in items:
                if (it.get('product') or '').lower() != 'copilot':
                    continue
                date_str = (it.get('date') or '')[:10]  # "YYYY-MM-DD"
                if not date_str:
                    continue
                d = by_day.setdefault(date_str, {'amt': 0.0, 'qty': 0.0})
                # grossAmount (not netAmount) to match the "Spend" gauge on page 1,
                # which is pre-discount consumption value - netAmount is what you're
                # actually billed after the included-usage discount, which can sit at
                # ~$0 all month and made this chart look empty.
                d['amt'] += it.get('grossAmount', 0) or 0
                d['qty'] += it.get('quantity', 0) or 0

            days = sorted(by_day.keys())[-HISTORY_POINTS:]

            daily_amt, daily_qty, cum_amt, cum_qty = [], [], [], []
            running_amt = running_qty = 0.0
            for d in days:
                a = by_day[d]['amt']
                q = by_day[d]['qty']
                daily_amt.append(a)
                daily_qty.append(q)
                running_amt += a
                running_qty += q
                cum_amt.append(running_amt)
                cum_qty.append(running_qty)

            _history_dates = days
            _history_daily_amt = daily_amt
            _history_daily_qty = daily_qty
            _history_cum_amt = cum_amt
            _history_cum_qty = cum_qty
            return True
        else:
            _last_error = "History HTTP %d" % resp.status_code
            return False
    except Exception as e:
        _last_error = "History fetch error: %s" % e
        print("copilot: history fetch error:", e)
        return False
    finally:
        if resp is not None:
            resp.close()


async def fetch_all():
    global _last_error
    _last_error = None
    ok1 = await fetch_summary()
    ok2 = await fetch_history()
    return ok1 and ok2


# --- Billing-period progress (used on the reset/countdown page) -------------

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(y):
    return (y % 4 == 0) and (y % 100 != 0 or y % 400 == 0)


def _days_in_month(y, m):
    d = _DAYS_IN_MONTH[m - 1]
    if m == 2 and _is_leap(y):
        d = 29
    return d


def _billing_progress():
    """GitHub's metered billing cycle always resets at 00:00:00 UTC on the 1st of the
    month - fixed, not plan/account-specific:
    https://docs.github.com/en/copilot/reference/copilot-billing/billing-cycle

    clocktime.now() is a UTC unix timestamp; utime.localtime() on this firmware does a
    plain calendar breakdown with no TZ shift applied (the codebase's own convention -
    see .github/copilot-instructions.md's clocktime notes), so calling it directly on
    that UTC timestamp yields UTC calendar fields, which is what we want here.

    Returns (pct_elapsed, seconds_remaining, reset_tuple_local) where reset_tuple_local
    is a (Y, M, D, H) tuple already shifted to local time for display.
    """
    try:
        now_utc = clocktime.now()
        if now_utc < 0:
            return None, None, None
        y, m, d, h, mi, s = utime.localtime(now_utc)[:6]
        total = _days_in_month(y, m) * 86400
        elapsed = (d - 1) * 86400 + h * 3600 + mi * 60 + s
        remaining = max(0, total - elapsed)
        pct = max(0, min(100, int(elapsed * 100 / total)))

        reset_utc = now_utc + remaining
        reset_local = reset_utc + clocktime.tzoffset()
        ry, rm, rd, rh = utime.localtime(reset_local)[:4]
        return pct, remaining, (ry, rm, rd, rh)
    except Exception as e:
        print("copilot: progress calc error:", e)
        return None, None, None


_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _fmt_reset_date(reset_tuple):
    if not reset_tuple:
        return "--"
    y, m, d, h = reset_tuple[0], reset_tuple[1], reset_tuple[2], reset_tuple[3]
    ampm = "am" if h < 12 else "pm"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{_MONTH_ABBR[m - 1]} {d} at {h12}:00 {ampm}"


def _fmt_countdown(remaining_s):
    if remaining_s is None:
        return "--d:--h:--m"
    d = remaining_s // 86400
    h = (remaining_s % 86400) // 3600
    m = (remaining_s % 3600) // 60
    return f"{d}d:{h}h:{m}m"


# --- Input handling -------------------------------------------------

def event_handler(e):
    global _current_page, _last_fetch_time

    e_code = e.get_code()
    if e_code == lv.EVENT.KEY:
        e_key = e.get_key()

        if e_key == lv.KEY.ENTER:
            # ENTER forces an immediate re-fetch on the next foreground tick
            _last_fetch_time = -999
            return

        old_page = _current_page
        if e_key == lv.KEY.LEFT:   # Scroll down = next page
            _current_page = (_current_page + 1) % _num_pages
        elif e_key == lv.KEY.RIGHT:  # Scroll up = previous page
            _current_page = (_current_page - 1) % _num_pages

        if _current_page != old_page:
            show_current_page()

    elif e_code == lv.EVENT.FOCUSED:
        if not lv.group_get_default().get_editing():
            lv.group_get_default().set_editing(True)


def show_current_page():
    _set_page_visible(_current_page)
    _update_ui_for_current_page()


def _set_dot(color_key, visible=True):
    """Show/hide the corner busy-dot. color_key indexes _styles (e.g. 'c_orange'
    while fetching, 'c_green'/'c_red' briefly after a fetch completes)."""
    if not (_ui and _ui.get('busy_dot') and _styles):
        return
    try:
        if visible:
            _ui['busy_dot'].set_style_bg_color(_styles[color_key], lv.PART.MAIN)
            _ui['busy_dot'].clear_flag(lv.obj.FLAG.HIDDEN)
        else:
            _ui['busy_dot'].add_flag(lv.obj.FLAG.HIDDEN)
    except Exception:
        pass


async def _yield_for_paint():
    """requests.get() below is a blocking call, not a real awaited one, so nothing
    repaints while it runs. Yield here first so the LVGL redraw task (if it shares
    this event loop) gets a chance to actually paint the busy dot before we block -
    otherwise the color change and the block can land between the same two frames
    and never visibly render. Same gotcha/fix as the ntfy app's mode_dot."""
    if asyncio:
        try:
            await asyncio.sleep_ms(150)
        except Exception:
            pass


# --- Styles -------------------------------------------------

def _ensure_styles():
    global _styles
    if _styles is not None:
        return

    container_style = lv.style_t()
    container_style.init()
    container_style.set_pad_all(6)
    container_style.set_border_width(0)
    container_style.set_bg_color(lv.color_hex(0x2D2D2D))
    container_style.set_radius(10)

    _styles = {
        'container': container_style,
        'c_white': lv.color_hex(0xFFFFFF),
        'c_gray': lv.color_hex(0x808080),
        'c_dark': lv.color_hex(0x404040),
        'c_purple': lv.color_hex(0x8957E5),   # Copilot purple
        'c_green': lv.color_hex(0x3FB950),    # GitHub green
        'c_yellow': lv.color_hex(0xE0C020),
        'c_blue': lv.color_hex(0x58A6FF),
        'c_orange': lv.color_hex(0xF0A030),
        'c_red': lv.color_hex(0xFF6B6B),
    }
    global FONT_SMALL
    for _fname in ("font_montserrat_12", "font_montserrat_14"):
        try:
            FONT_SMALL = getattr(lv, _fname)
            break
        except Exception:
            continue


# --- Page 0: gauges -------------------------------------------------

def _build_gauge_quadrant(parent, align, x_off, y_off, w, h, title, color):
    """One arc gauge + labels, reusing the arc pattern proven in the proxmox app.

    The ring sweeps clockwise from 12 o'clock as its value rises, so ANY fixed spot
    on its circumference gets crossed at some fill percentage (e.g. bottom-left is
    crossed around 60-65% full). The only way to guarantee the title never collides
    with the ring at any fill level is to keep it structurally outside the ring's
    bounding circle - so we carve a dedicated vertical gutter down the left edge and
    confine the arc to the remaining square on the right, and stack the title's
    letters top-to-bottom in that gutter (no rotated-text API to rely on)."""
    c = _styles['container']

    box = lv.obj(parent)
    box.set_size(w, h)
    box.align(align, x_off, y_off)
    box.add_style(c, lv.PART.MAIN)
    box.clear_flag(lv.obj.FLAG.SCROLLABLE)
    if hasattr(box, "set_scrollbar_mode"):
        box.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

    gutter_w = 14

    title_label = lv.label(box)
    title_label.set_text("\n".join(title.upper()))
    title_label.set_pos(0, 0)
    title_label.set_size(gutter_w, h)
    title_label.set_style_text_color(color, 0)
    try:
        title_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    except Exception:
        pass
    try:
        title_label.set_style_text_line_space(-3, 0)
    except Exception:
        pass
    if FONT_SMALL:
        try:
            title_label.set_style_text_font(FONT_SMALL, 0)
        except Exception:
            pass

    holder = lv.obj(box)
    holder.set_pos(gutter_w, 0)
    holder.set_size(w - gutter_w, h)
    holder.set_style_bg_opa(0, lv.PART.MAIN)
    holder.set_style_border_width(0, lv.PART.MAIN)
    holder.set_style_pad_all(0, lv.PART.MAIN)
    holder.clear_flag(lv.obj.FLAG.SCROLLABLE)
    holder.clear_flag(lv.obj.FLAG.CLICKABLE)

    arc_d = min(w - gutter_w, h) - 8

    arc = lv.arc(holder)
    arc.set_size(arc_d, arc_d)
    arc.align(lv.ALIGN.CENTER, 0, -6)
    arc.set_bg_angles(0, 360)
    arc.set_rotation(270)
    arc.set_style_arc_width(7, lv.PART.MAIN)
    arc.set_style_arc_width(7, lv.PART.INDICATOR)
    arc.set_style_arc_color(_styles['c_dark'], lv.PART.MAIN)
    arc.set_style_arc_color(color, lv.PART.INDICATOR)
    arc.set_style_bg_opa(0, lv.PART.KNOB)
    arc.set_style_pad_all(0, lv.PART.KNOB)
    arc.clear_flag(lv.obj.FLAG.CLICKABLE)

    value_label = lv.label(holder)
    value_label.align(lv.ALIGN.CENTER, 0, -12)
    value_label.set_style_text_color(_styles['c_white'], 0)
    try:
        value_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    except Exception:
        pass

    return {'arc': arc, 'value_label': value_label}


def _build_page_gauges(parent, content_h):
    gap = 2
    half_w = (_SCR_WIDTH - gap * 3) // 2
    half_h = (content_h - gap * 3) // 2

    tl = _build_gauge_quadrant(parent, lv.ALIGN.TOP_LEFT, gap, gap, half_w, half_h,
                                "Spend", _styles['c_purple'])
    tr = _build_gauge_quadrant(parent, lv.ALIGN.TOP_RIGHT, -gap, gap, half_w, half_h,
                                "Save", _styles['c_green'])
    bl = _build_gauge_quadrant(parent, lv.ALIGN.BOTTOM_LEFT, gap, -gap, half_w, half_h,
                                "Cred", _styles['c_blue'])
    br = _build_gauge_quadrant(parent, lv.ALIGN.BOTTOM_RIGHT, -gap, -gap, half_w, half_h,
                                "Bill", _styles['c_orange'])
    return {'gauge_spend': tl, 'gauge_savings': tr, 'gauge_credits': bl, 'gauge_net': br}


# --- Page 1: charts -------------------------------------------------

def _build_chart_pair(parent, x, y, w, h, bar_color, line_color):
    """Two stacked lv.chart widgets: a BAR chart (daily) behind a transparent
    LINE chart (cumulative) on its own axis range. LVGL sets chart type per
    chart object (not per series), so this is how the dashboard's "bars +
    cumulative line" look is reproduced. See .github/prompts/copilot.prompt.md."""
    bar_chart = lv.chart(parent)
    bar_chart.set_pos(x, y)
    bar_chart.set_size(w, h)
    bar_chart.clear_flag(lv.obj.FLAG.SCROLLABLE)
    bar_chart.clear_flag(lv.obj.FLAG.CLICKABLE)
    bar_chart.set_style_bg_color(_styles['c_dark'], lv.PART.MAIN)
    bar_chart.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
    bar_chart.set_style_border_width(0, lv.PART.MAIN)
    bar_chart.set_style_pad_all(4, lv.PART.MAIN)
    bar_chart.set_type(lv.chart.TYPE.BAR)
    bar_chart.set_point_count(HISTORY_POINTS)
    try:
        bar_chart.set_div_line_count(3, 0)
    except Exception:
        pass
    bar_series = bar_chart.add_series(bar_color, lv.chart.AXIS.PRIMARY_Y)

    line_chart = lv.chart(parent)
    line_chart.set_pos(x, y)
    line_chart.set_size(w, h)
    line_chart.clear_flag(lv.obj.FLAG.SCROLLABLE)
    line_chart.clear_flag(lv.obj.FLAG.CLICKABLE)
    line_chart.set_style_bg_opa(0, lv.PART.MAIN)
    line_chart.set_style_border_width(0, lv.PART.MAIN)
    line_chart.set_style_pad_all(4, lv.PART.MAIN)
    line_chart.set_type(lv.chart.TYPE.LINE)
    line_chart.set_point_count(HISTORY_POINTS)
    try:
        line_chart.set_div_line_count(0, 0)
    except Exception:
        pass
    line_series = line_chart.add_series(line_color, lv.chart.AXIS.PRIMARY_Y)
    try:
        line_chart.set_style_size(3, 3, lv.PART.INDICATOR)
    except Exception:
        pass

    return {'bar_chart': bar_chart, 'bar_series': bar_series,
            'line_chart': line_chart, 'line_series': line_series}


def _build_page_charts(parent, content_h):
    gap = 2
    title_h = 23      # +5px breathing room above each chart (was crowding the title text)
    chart_bottom_pad = 5  # +5px breathing room below each chart
    panel_h = (content_h - gap * 3) // 2
    w = _SCR_WIDTH - gap * 2

    title1 = lv.label(parent)
    title1.set_text("Credits (day / cum.)")
    title1.align(lv.ALIGN.TOP_LEFT, gap, gap)
    title1.set_style_text_color(_styles['c_blue'], 0)
    if FONT_SMALL:
        try:
            title1.set_style_text_font(FONT_SMALL, 0)
        except Exception:
            pass

    credits_pair = _build_chart_pair(parent, gap, gap + title_h, w, panel_h - title_h - chart_bottom_pad,
                                      _styles['c_purple'], _styles['c_blue'])

    y2 = gap + panel_h + gap
    title2 = lv.label(parent)
    title2.set_text("Spend $ (day / cum.)")
    title2.align(lv.ALIGN.TOP_LEFT, gap, y2)
    title2.set_style_text_color(_styles['c_orange'], 0)
    if FONT_SMALL:
        try:
            title2.set_style_text_font(FONT_SMALL, 0)
        except Exception:
            pass

    spend_pair = _build_chart_pair(parent, gap, y2 + title_h, w, panel_h - title_h - chart_bottom_pad,
                                    _styles['c_purple'], _styles['c_green'])

    note_label = lv.label(parent)
    note_label.align(lv.ALIGN.BOTTOM_MID, 0, -2)
    note_label.set_style_text_color(_styles['c_gray'], 0)
    note_label.add_flag(lv.obj.FLAG.HIDDEN)

    return {'chart_credits': credits_pair, 'chart_spend': spend_pair, 'chart_note': note_label}


def _fill_chart_pair(pair, daily_vals, cum_vals, daily_scale=1.0, cum_scale=1.0):
    """daily/cum_scale let $ values be scaled to integer 'cents' for arc precision.

    Sizes the chart to exactly `n` points instead of padding out to HISTORY_POINTS -
    this binding doesn't expose an LV_CHART_POINT_NONE-equivalent sentinel, so padding
    entries previously had to be real 0s, which made the cumulative line crash back
    down to zero for every not-yet-reached day of the month instead of just stopping."""
    try:
        n = len(daily_vals)
        if n == 0:
            return
        bar_max = max(daily_vals) if daily_vals else 1
        cum_max = max(cum_vals) if cum_vals else 1
        bar_range = max(1, int(bar_max * daily_scale))
        cum_range = max(1, int(cum_max * cum_scale))
        pair['bar_chart'].set_point_count(n)
        pair['line_chart'].set_point_count(n)
        pair['bar_chart'].set_range(lv.chart.AXIS.PRIMARY_Y, 0, bar_range)
        pair['line_chart'].set_range(lv.chart.AXIS.PRIMARY_Y, 0, cum_range)

        for i in range(n):
            pair['bar_chart'].set_value_by_id(pair['bar_series'], i, int(daily_vals[i] * daily_scale))
            pair['line_chart'].set_value_by_id(pair['line_series'], i, int(cum_vals[i] * cum_scale))
        pair['bar_chart'].refresh()
        pair['line_chart'].refresh()
    except Exception as e:
        print("copilot: chart update error:", e)


# --- Page 2: billing-period progress / countdown ---------------------------

def _progress_color(pct):
    """Green early in the billing period, sliding to red as the reset approaches."""
    if pct < 40:
        return _styles['c_green']
    if pct < 70:
        return _styles['c_yellow']
    if pct < 90:
        return _styles['c_orange']
    return _styles['c_red']


def _build_page_progress(parent, content_h):
    """A decorative progress ring (colored by how much of the billing period has
    elapsed) with no text inside it - the countdown/date/percent stack sits
    centered on the page instead, sharing the ring's visual center."""
    arc_d = min(_SCR_WIDTH, content_h) - 30

    arc = lv.arc(parent)
    arc.set_size(arc_d, arc_d)
    arc.align(lv.ALIGN.CENTER, 0, 0)
    arc.set_range(0, 100)
    arc.set_bg_angles(0, 360)
    arc.set_rotation(270)
    arc.set_style_arc_width(10, lv.PART.MAIN)
    arc.set_style_arc_width(10, lv.PART.INDICATOR)
    arc.set_style_arc_color(_styles['c_dark'], lv.PART.MAIN)
    arc.set_style_arc_color(_styles['c_green'], lv.PART.INDICATOR)
    arc.set_style_bg_opa(0, lv.PART.KNOB)
    arc.set_style_pad_all(0, lv.PART.KNOB)
    arc.clear_flag(lv.obj.FLAG.CLICKABLE)

    countdown_label = lv.label(parent)
    countdown_label.align(lv.ALIGN.CENTER, 0, -22)
    countdown_label.set_style_text_color(_styles['c_purple'], 0)
    try:
        countdown_label.set_style_text_font(lv.font_montserrat_20, 0)
    except Exception:
        pass

    date_label = lv.label(parent)
    date_label.align(lv.ALIGN.CENTER, 0, 4)
    date_label.set_style_text_color(_styles['c_white'], 0)

    elapsed_label = lv.label(parent)
    elapsed_label.align(lv.ALIGN.CENTER, 0, 26)
    elapsed_label.set_style_text_color(_styles['c_gray'], 0)

    return {
        'progress_arc': arc, 'countdown_label': countdown_label,
        'date_label': date_label, 'elapsed_label': elapsed_label,
    }


# --- Page assembly -------------------------------------------------

def _ensure_ui():
    global _ui
    if _ui is not None or _scr is None:
        return

    _ensure_styles()

    content_h = _SCR_HEIGHT

    page_containers = []
    for _ in range(_num_pages):
        p = lv.obj(_scr)
        p.set_size(_SCR_WIDTH, content_h)
        p.align(lv.ALIGN.TOP_LEFT, 0, 0)
        p.set_style_bg_opa(0, lv.PART.MAIN)
        p.set_style_border_width(0, lv.PART.MAIN)
        p.set_style_pad_all(0, lv.PART.MAIN)
        p.clear_flag(lv.obj.FLAG.SCROLLABLE)
        page_containers.append(p)

    gauges = _build_page_gauges(page_containers[0], content_h)
    charts = _build_page_charts(page_containers[1], content_h)
    progress = _build_page_progress(page_containers[2], content_h)

    # Created last (after the page containers) so it renders on top of whichever
    # page is visible, on every page - the only always-on indicator that a fetch
    # (background poll or ENTER-forced) is actually happening, since there's no
    # persistent status row anymore.
    busy_dot = lv.obj(_scr)
    busy_dot.set_size(8, 8)
    busy_dot.align(lv.ALIGN.TOP_RIGHT, -4, 4)
    busy_dot.set_style_border_width(0, lv.PART.MAIN)
    busy_dot.set_style_radius(100, lv.PART.MAIN)
    busy_dot.set_style_bg_color(_styles['c_orange'], lv.PART.MAIN)
    busy_dot.clear_flag(lv.obj.FLAG.SCROLLABLE)
    busy_dot.clear_flag(lv.obj.FLAG.CLICKABLE)
    busy_dot.add_flag(lv.obj.FLAG.HIDDEN)

    # Tiny always-on build stamp so we can tell what's actually running on the
    # device without pulling up a serial log.
    build_label = lv.label(_scr)
    build_label.set_text(GIT_COMMIT)
    build_label.align(lv.ALIGN.BOTTOM_LEFT, 4, -2)
    build_label.set_style_text_color(_styles['c_gray'], 0)

    _ui = {'pages': page_containers, 'busy_dot': busy_dot, 'build_label': build_label}
    _ui.update(gauges)
    _ui.update(charts)
    _ui.update(progress)


def _set_page_visible(page_index):
    if _scr is None:
        return
    _ensure_ui()
    if _ui is None:
        return
    for i, p in enumerate(_ui['pages']):
        if i == page_index:
            p.clear_flag(lv.obj.FLAG.HIDDEN)
        else:
            p.add_flag(lv.obj.FLAG.HIDDEN)


def _update_page(page_index):
    if _scr is None:
        return
    _ensure_ui()
    if _ui is None:
        return

    if page_index == 0:
        spend_i = int(round(_summary['gross']))
        cap_spend_i = int(round(CAP_SPEND))
        _ui['gauge_spend']['arc'].set_range(0, cap_spend_i)
        _ui['gauge_spend']['arc'].set_value(min(cap_spend_i, spend_i))
        _ui['gauge_spend']['value_label'].set_text(f"${spend_i}\n/ ${cap_spend_i}")

        savings_i = int(round(_summary['discount']))
        cap_savings_i = int(round(CAP_SAVINGS))
        _ui['gauge_savings']['arc'].set_range(0, cap_savings_i)
        _ui['gauge_savings']['arc'].set_value(min(cap_savings_i, savings_i))
        _ui['gauge_savings']['value_label'].set_text(f"${savings_i}\n/ ${cap_savings_i}")

        credits_i = int(round(_summary['gross_qty']))
        _ui['gauge_credits']['arc'].set_range(0, CAP_CREDITS)
        _ui['gauge_credits']['arc'].set_value(min(CAP_CREDITS, credits_i))
        _ui['gauge_credits']['value_label'].set_text(f"{credits_i}\n/ {CAP_CREDITS}")

        net_i = int(round(_summary['net']))
        _ui['gauge_net']['arc'].set_range(0, cap_spend_i)
        _ui['gauge_net']['arc'].set_value(min(cap_spend_i, net_i))
        _ui['gauge_net']['value_label'].set_text(f"${net_i}\n/ ${cap_spend_i}")

    elif page_index == 1:
        _fill_chart_pair(_ui['chart_credits'], _history_daily_qty, _history_cum_qty,
                          daily_scale=1.0, cum_scale=1.0)
        _fill_chart_pair(_ui['chart_spend'], _history_daily_amt, _history_cum_amt,
                          daily_scale=100.0, cum_scale=100.0)
        if not _history_dates:
            note = f"Error: {_last_error}" if _last_error else "No daily history yet"
            _ui['chart_note'].set_text(note)
            _ui['chart_note'].clear_flag(lv.obj.FLAG.HIDDEN)
        else:
            _ui['chart_note'].add_flag(lv.obj.FLAG.HIDDEN)

    elif page_index == 2:
        pct, remaining, reset_tuple = _billing_progress()
        pct_val = pct if pct is not None else 0
        _ui['progress_arc'].set_style_arc_color(_progress_color(pct_val), lv.PART.INDICATOR)
        _ui['progress_arc'].set_value(pct_val)
        _ui['countdown_label'].set_text(_fmt_countdown(remaining))
        _ui['date_label'].set_text(_fmt_reset_date(reset_tuple))
        _ui['elapsed_label'].set_text(f"{pct}% elapsed" if pct is not None else "--% elapsed")


def _update_ui_for_current_page():
    _update_page(_current_page)


def _update_all_pages():
    """Refresh every page's data, not just the one currently visible - otherwise a
    background poll while sitting on the gauges page would leave the chart page
    showing stale data until the user happens to scroll to it."""
    for i in range(_num_pages):
        _update_page(i)


# --- App lifecycle -------------------------------------------------

async def on_boot(apm):
    global _app_mgr
    _app_mgr = apm
    if _app_mgr:
        _load_settings(_app_mgr.config())


async def on_start():
    global _scr, _current_page, _last_fetch_time

    if _app_mgr:
        _load_settings(_app_mgr.config())

    if not _scr:
        _scr = lv.obj()
        _scr.set_style_bg_color(lv.color_hex3(0x000), lv.PART.MAIN)
        _scr.add_event(event_handler, lv.EVENT.ALL, None)

        group = lv.group_get_default()
        if group:
            group.add_obj(_scr)
            lv.group_focus_obj(_scr)
            group.set_editing(True)

        _app_mgr.enter_root_page()
        lv.scr_load(_scr)

        _ensure_ui()

    _current_page = 0
    show_current_page()

    global _dot_hide_at
    _set_dot('c_orange')
    await _yield_for_paint()
    ok = await fetch_all()
    _last_fetch_time = utime.time()  # avoid an immediate duplicate fetch on the next foreground tick
    _set_dot('c_green' if ok else 'c_red')
    _dot_hide_at = utime.time() + 1.5
    _update_all_pages()
    _set_page_visible(_current_page)


async def on_stop():
    global _scr, _app_mgr, _ui, _styles

    if _app_mgr:
        _app_mgr.leave_root_page()

    if _scr:
        _scr.clean()
        _scr = None
        _ui = None
        _styles = None


async def on_running_foreground():
    global _last_fetch_time, _dot_hide_at

    now = utime.time()

    if _dot_hide_at > 0 and now >= _dot_hide_at:
        _dot_hide_at = -999
        _set_dot('c_gray', visible=False)

    poll_seconds = max(60, POLL_MINUTES * 60)
    if now - _last_fetch_time >= poll_seconds:
        _last_fetch_time = now
        _set_dot('c_orange')
        await _yield_for_paint()
        ok = await fetch_all()
        _set_dot('c_green' if ok else 'c_red')
        _dot_hide_at = utime.time() + 1.5
        _update_all_pages()
    elif _current_page == 2:
        # Progress page: keep ticking every foreground frame without re-fetching
        _update_ui_for_current_page()
