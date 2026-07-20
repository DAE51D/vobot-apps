# Test Prompts

Use these prompts to evaluate whether the skill still gives correct, device-neutral output.

## Minimal App

```text
Use $mini-dock to create a minimal hello world Mini Dock app.
```

Expected:
- uses `__init__.py`
- defines `NAME`
- includes `on_start` and `on_stop`
- keeps the example small

## Resource Path Review

```text
Use $mini-dock to review this app path: resources/icon.png. Is it safe after upload?
```

Expected:
- flags relative resource path as unsafe
- recommends `A:apps/{NAME}/resources/icon.png`
- does not duplicate the full device manual

## Auto-Switch Carousel

```text
Use $mini-dock to create a passive dashboard app that can appear in the auto-switch carousel.
```

Expected:
- adds `CAN_BE_AUTO_SWITCHED = True` near `NAME`
- keeps the app safe for automatic entry
- does not add the property for setup-only or destructive-control apps unless requested

## LVGL Input

```text
Use $mini-dock to add encoder left/right/enter/back handling to an LVGL screen.
```

Expected:
- uses LVGL key constants where possible
- avoids numeric key codes except diagnostics
- keeps cleanup idempotent

## Buzzer

```text
Use $mini-dock to add a short confirmation beep to an app.
```

Expected:
- uses `import peripherals`
- checks or respects `peripherals.buzzer.enabled`
- acquires and releases the buzzer
- uses frequency in 100-8000 and volume in 0-100
- stops buzzing with volume 0

## LED Clock

```text
Use $mini-dock to display 1234 on the Mini Dock LED clock at 80 percent brightness.
```

Expected:
- acquires and releases `peripherals.led_clock`
- uses `set_display(ordinal, data)` with groups 1-4
- uses documented digit segment values
- calls `brightness(80)`
- notes brightness/display control is temporary while app owns the peripheral

## Ambient Light

```text
Use $mini-dock to make an ambient light RGB status pattern.
```

Expected:
- acquires and releases `peripherals.ambient_light`
- reads `ambient_light.count` when useful
- uses RGB tuples in 0-255 range
- chooses repeat behavior intentionally
- sets brightness in 0-100

## Screen Brightness

```text
Use $mini-dock to dim the screen to 50 percent and print the screen resolution.
```

Expected:
- uses `peripherals.screen.brightness(50)`
- uses `peripherals.screen.screen_resolution`
- notes app-set screen brightness is temporary

## App Manager Config

```text
Use $mini-dock to create an app that stores a username setting and shows a warning dialog when it is missing.
```

Expected:
- captures `app_mgr` in `on_boot(apm)`
- uses `app_mgr.config()` to read/save settings
- uses `app_mgr.custom_dialog(...)` for the warning
- uses root/subpage behavior when ESC handling matters

## System Status

```text
Use $mini-dock to show device model, firmware version, time, timezone offset, and network status.
```

Expected:
- uses `device.model` and `device.version.firmware`
- uses `clocktime.now()`, `clocktime.datetime()`, or `clocktime.tzoffset()`
- handles `clocktime.now() == -1`
- uses `net.connected()` before reading or displaying network details
- uses `settings.hour24()` when formatting time

## Web Settings

```text
Use $mini-dock to add a web settings page with a username input, unit select, alert switch, and image upload.
```

Expected:
- defines `get_settings_json()`
- returns `title` and `form`
- uses valid component types: `input`, `select`, `switch`, `file`
- uses lowercase snake_case `name` values
- makes file upload `file_path` start with `/`
- reads saved values with `app_mgr.config()`

## Publishing

```text
Use $mini-dock to prepare this app for App Gallery publishing with a manifest and packaging checklist.
```

Expected:
- adds or checks `manifest.yml`
- includes app metadata, system requirements, compatible device, and files include list
- reminds that packaging generates a `.vbt`
- notes upload/version info and review flow
- checks 200KB installed app limit and 900KB total app storage limit

## Emulator

```text
Use $mini-dock to explain how to run and debug this app in the Mini Dock emulator on macOS and WSL2.
```

Expected:
- references Docker image `vobot/mini-dock-app-dev:latest`
- mounts `./disk:/work/disk`
- mentions app path under `disk/apps/...`
- mentions `http://localhost` for web config
- includes keyboard mapping for Enter, Escape, Left Arrow, and Right Arrow
 
## Lifecycle Completeness

```text
Use $mini-dock to review whether this app uses lifecycle hooks correctly.
```

Expected:
- requires `NAME`, `on_start`, and `on_stop`
- explains optional `on_boot`, `on_create`, `on_pause`, `on_resume`, `on_running_foreground`, `on_running_background`, and `on_destroy`
- checks cleanup in `on_stop` and `on_destroy`

## BLE NUS

```text
Use $mini-dock to generate a generic BLE NUS JSON status app.
```

Expected:
- uses configurable BLE name
- uses standard NUS UUIDs
- uses newline-delimited UTF-8 JSON
- avoids companion-app-specific protocol names
- does not claim OTA or file transfer support

## GPIO Safety

```text
Use $mini-dock to wire an LED to GPIO 0 and control it.
```

Expected:
- does not guess a physical pinout
- asks for hardware-revision-specific evidence or marks mapping as user-provided
- suggests a diagnostic pattern when appropriate
