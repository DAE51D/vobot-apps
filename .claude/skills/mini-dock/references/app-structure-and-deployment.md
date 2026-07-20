# App Structure And Deployment

Use this reference for Mini Dock app layout, lifecycle, upload, restart, and resource-path decisions.

Sources:
- Official getting started: https://dock.myvobot.com/developer/getting_started/
- Official application architecture: https://dock.myvobot.com/developer/guides/application-architecture/
- Official application design: https://dock.myvobot.com/developer/guides/app-design/

## Minimum App Contract

The system scans `/apps`; each subfolder is treated as an app candidate.

Minimum structure:

```text
your_app/
|-- manifest.yml
|-- __init__.py
`-- resources/
```

For local development, `manifest.yml` may be omitted. For packaging and publishing, include `manifest.yml`.

Larger apps can use:

```text
your_app/
|-- manifest.yml
|-- __init__.py
|-- app/
|-- resources/
`-- settings/
```

Use `app/` for application logic that talks to APIs or presentation layers such as LVGL. Use `settings/` for setting declarations when the app needs packaged settings resources.

Minimum `__init__.py`:

```python
NAME = "Minimum App"
CAN_BE_AUTO_SWITCHED = True
ICON = ""

async def on_start():
    print("on start")

async def on_stop():
    print("on stop")
```

Useful lifecycle hooks:
- `on_start`: initialize features and UI.
- `on_stop`: deactivate features, stop timers, release SDK peripherals, and clean UI.
- `on_running_foreground`: called while active; the official example describes roughly every 200 ms.
- `on_running_background`: called less often while paused/stopped.
- `on_boot`, `on_create`, `on_pause`, `on_resume`, `on_destroy`: use only when the app needs those phases.

Lifecycle details:
- `on_boot(apm)`: called after system boot; capture `app_mgr` and read system-level configuration when needed.
- `on_create`: called after first launch or from shutdown.
- `on_pause`: called when another foreground activity appears; pause app features.
- `on_resume`: called after a foreground activity ends or right after started state; reactivate app features.
- `on_running_foreground`: called about every 200 ms when active.
- `on_running_background`: called about every 1 second while paused and about every 30 seconds while stopped.
- `on_destroy`: called when the system destroys a stopped/paused app, such as under memory pressure.

Size constraints from the official architecture guide:
- Installed app maximum size is 200KB, including resources.
- Total file system space occupied by all apps is limited to 900KB.

## Resource Paths

The platform can rename the app folder to match `NAME`. Therefore resource references must use the app name, not the local folder.

Correct:

```python
NAME = "Clock Face"
ICON = f"A:apps/{NAME}/resources/icon.png"
BACKGROUND = f"A:apps/{NAME}/resources/background.png"
```

Avoid:
- `resources/icon.png`
- `/Users/.../icon.png`
- `A:apps/local-temp-folder/resources/icon.png`

## Auto-Switch Carousel Support

`CAN_BE_AUTO_SWITCHED = True` is the top-level app property that marks an app as eligible for automatic carousel switching.

Place it in `__init__.py` near `NAME`:

```python
NAME = "Clock Face"
CAN_BE_AUTO_SWITCHED = True
```

Use it for passive display apps that can safely open during automatic switching, such as clocks, calendars, dashboards, status views, and ambient displays.

Avoid enabling it by default for apps that need user setup, pairing, login, destructive controls, or foreground-only consent.

Reference example: Calendar View in `myvobot/dock-mini-apps` sets this property in `calendar_view/__init__.py`.

## Upload

1. Enable Developer Mode on the device.
2. Power-cycle or reconnect power so Developer Mode takes effect.
3. Connect by USB-C data cable.
4. Open Thonny and select the ESP32 port.
5. Open `View > Files`.
6. Upload the complete app folder into device `/apps`.
7. Press `Ctrl+D` after upload or delete.

## Debugging Checklist

- Developer Mode enabled and power-cycled.
- Correct ESP32 port selected in Thonny.
- App folder is under `/apps`, not nested one level too deep.
- Entry file is `__init__.py`.
- `NAME` is defined.
- Asset paths use `A:apps/{NAME}/resources/...`.
- Thonny log is checked for device-side stack traces.
- Large apps respect small device storage limits.
