# System Services

Use this reference for app manager behavior, device identity/version, global settings, time, and network status.

Sources:
- Application manager: https://dock.myvobot.com/developer/reference/manager/
- Device: https://dock.myvobot.com/developer/reference/system/
- Settings: https://dock.myvobot.com/developer/reference/settings/
- Clocktime: https://dock.myvobot.com/developer/reference/clocktime/
- Network: https://dock.myvobot.com/developer/reference/network/

## Application Manager

Capture `app_mgr` during boot when the app needs configuration, dialogs, root-page state, or active exit:

```python
app_mgr = None

async def on_boot(apm):
    global app_mgr
    app_mgr = apm
```

Useful APIs:
- `app_mgr.state`: lifecycle state. Official values: `0` shutdown, `1` started, `2` active, `3` paused, `4` stopped.
- `app_mgr.enter_root_page()`: tell the system the app is on its top-level page, so ESC can exit the app.
- `app_mgr.leave_root_page()`: tell the system the app is in a subpage, so ESC should not exit the app.
- `app_mgr.custom_dialog(title, content, confirm=None, cancel=None, cb=None, subtitle=None, qr=None, style=None)`: show a system dialog and return the LVGL dialog widget.
- `app_mgr.config(cfg=None)`: read or save this app's configuration.
- `await app_mgr.exit()`: actively exit the current app when it is active.

Dialog callback pattern:

```python
def on_dialog_key(res):
    if res == lv.KEY.ENTER:
        print("confirmed")
    elif res == lv.KEY.ESC:
        print("cancelled")

app_mgr.custom_dialog(
    title="Network",
    content="Connect first",
    cancel="Back",
    cb=on_dialog_key,
    style=app_mgr.DIALOG.WARNING,
)
```

Rules:
- Clear app UI before calling `app_mgr.exit()`.
- Only actively exit when the app is in the active state.
- Use root/subpage calls to keep ESC behavior aligned with nested screens.

## App Configuration

Use `app_mgr.config()` for per-app settings saved by the app or by generated web settings forms:

```python
cfg = app_mgr.config() or {}
username = cfg.get("username", "Unknown")

cfg["username"] = username
app_mgr.config(cfg)
```

## Device

Use the `device` module for system-level identity and version data:

```python
import device

dev_id = device.id
dev_model = device.model
hardware_version = device.version.hardware
firmware_version = device.version.firmware
in_nightstand = device.in_nightstand_mode()
```

`device.in_nightstand_mode()` returns `True` when the device is in night mode, otherwise `False`.

## Settings

Use the `settings` module to respect system preferences:

```python
import settings

use_celsius = settings.temp_unit() == 1
use_24h = settings.hour24()
```

Official return values:
- `settings.temp_unit()`: `1` for Celsius, `0` for Fahrenheit. Default is Fahrenheit.
- `settings.hour24()`: `True` for 24-hour time, `False` for 12-hour time. Default is `True`.

## Clocktime

Use `clocktime` for real clock data:

```python
import clocktime

timestamp = clocktime.now()
dt = clocktime.datetime()
tz_seconds = clocktime.tzoffset()
```

Official behavior:
- `clocktime.now()` returns Unix timestamp seconds, or `-1` when time is not synchronized.
- `clocktime.datetime()` returns `(YYYY, MM, DD, hh, mm, ss, wday, yday)`.
- `clocktime.tzoffset()` returns offset seconds from UTC+0.

For uptime since boot, use the MicroPython `time` module instead of `clocktime`.

## Network

Use `net` to check network status before network-dependent work:

```python
import net

connected = net.connected()
info = net.config()
```

`net.connected()` returns `True` or `False`.

`net.config()` returns current network information such as:
- `IP`
- `route`
- `dns`
- `rssi`
- `essid`

For HTTP requests, use MicroPython's `urequests` module when available.

