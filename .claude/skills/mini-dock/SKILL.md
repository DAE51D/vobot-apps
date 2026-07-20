---
name: mini-dock
description: Use this skill when building, modifying, reviewing, or debugging generic Mini Dock MicroPython apps. Trigger for user phrases such as Mini Dock app, Thonny upload, LVGL screen, encoder button, resource path, app folder, device UI, app manager, app settings, web settings, time, network status, hardware peripheral, GPIO pin, BLE UART, BLE NUS, or Bluetooth control. This skill is device-focused and should not assume compatibility with any single companion app.
---

# Mini Dock Skill

## Purpose

Build Mini Dock apps that are portable across use cases. Prefer verified device and SDK behavior, keep app-specific protocols configurable, and call out anything that is inferred or unverified.

## Process Flow

1. Classify the task: new app, app review, UI/input, system services, web settings, peripheral/GPIO, BLE NUS, deployment, emulator debugging, publishing, or diagnostic.
2. Load only the needed reference file:
   - `references/app-structure-and-deployment.md` for app layout, lifecycle, upload, restart, and paths.
   - `references/ui-and-input.md` for LVGL screens, fonts, buttons, encoder flow, and layout.
   - `references/system-services.md` for `app_mgr`, device identity/version, global settings, clocktime, network status, and app config.
   - `references/web-settings.md` for `get_settings_json()` and web configuration forms.
   - `references/hardware-and-peripherals.md` for SDK peripherals, GPIO, physical pins, and safety checks.
   - `references/ble-nus.md` for BLE advertising, GATT, RX/TX, and JSON protocol.
   - `references/emulator.md` for Docker-based Mini Dock simulator setup and debugging.
   - `references/publishing.md` for Gallery packaging, `manifest.yml`, `.vbt` generation, and upload review flow.
3. Confirm missing critical inputs only when needed: app name, hardware feature, BLE role/protocol, assets, target behavior, or whether the app should support auto-switch carousel display.
4. Generate or edit a copyable app folder using `__init__.py` as the entrypoint.
5. Apply the app rules below, especially `NAME`-derived resource paths.
6. Validate against the success checks and call out unverified hardware assumptions.
7. Return the result in this order: directory tree, files or patch summary, upload/restart notes, debugging checks.

## App Rules

Recommended app directory:

```text
your_app/
|-- __init__.py
`-- resources/
```

- Entry file: `__init__.py`.
- Required app property: `NAME = "App Name"`.
- Optional auto-switch carousel property: `CAN_BE_AUTO_SWITCHED = True` when the app should be eligible for automatic carousel switching.
- Optional icon: `ICON = f"A:apps/{NAME}/resources/icon.png"` when an icon exists.
- Put bundled files under `resources/`.
- Build resource paths as `f"A:apps/{NAME}/resources/..."`.
- Keep installed app size in mind; the official architecture reference notes small app storage limits.
- Do not generate `main.py` as the Mini Dock app entrypoint.
- Do not delete the device `/apps` directory when uninstalling; delete only the target app folder.

## Auto-Switch Carousel

When the user asks for carousel, auto-switch, rotating display, idle rotation, or an app that should appear in automatic switching, add this top-level property in `__init__.py` near `NAME`:

```python
NAME = "My App"
CAN_BE_AUTO_SWITCHED = True
```

Use this only when the app is safe to enter automatically without user interaction. For setup screens, destructive controls, pairing flows, or apps that require foreground-only consent, leave it unset unless the user explicitly asks.

Reference example: `myvobot/dock-mini-apps` Calendar View sets `CAN_BE_AUTO_SWITCHED = True` in `calendar_view/__init__.py`.

## UI And Input

Use LVGL for screens. For simple UI, create one `lv.obj()` screen, attach labels or controls, then `lv.scr_load(scr)`.

When user input matters, use LVGL key events and symbolic constants (`lv.KEY.LEFT`, `lv.KEY.RIGHT`, `lv.KEY.ENTER`, `lv.KEY.ESC`) rather than hard-coding numeric key codes unless diagnosing low-level behavior.

Read `references/ui-and-input.md` when building layouts, fonts, button/encoder flows, approval screens, menus, or screen-size adaptive UI.

## Hardware And Pins

Prefer the official `peripherals` SDK modules for built-in hardware: screen brightness/resolution, buzzer, LED clock, and ambient light. Acquire and release controllable peripherals when the SDK requires it.

For raw GPIO or physical pin work, do not invent a Mini Dock pinout. Treat physical pin mappings as hardware-revision-specific unless the user provides a schematic, board photo, or tested REPL output. Generate a diagnostic script when needed.

Read `references/hardware-and-peripherals.md` before using built-in peripherals, raw GPIO, physical connectors, or pin definitions.

## System Services And Web Settings

Use `on_boot(apm)` to capture `app_mgr` when an app needs app state, persistent app config, root-page navigation, dialogs, or active exit.

Read `references/system-services.md` before using `app_mgr`, `device`, `settings`, `clocktime`, or `net`.

Read `references/web-settings.md` before generating `get_settings_json()` for web-based app configuration, file upload settings, or dynamic configuration groups.

## BLE NUS

BLE support is generic Nordic UART Service guidance for Mini Dock MicroPython apps. Do not bake in a companion app name, product identity, or approval protocol unless the user requests it.

Default BLE principles:
- Use configurable device name and protocol fields.
- Use standard NUS UUIDs unless the user asks for a custom service.
- Prefer newline-delimited UTF-8 JSON for interoperable command/response flows.
- Keep advertising payloads small; let centrals discover services through GATT after connecting.
- Avoid claiming BLE OTA, file upload, retransmission, or throughput results unless separately verified.

Read `references/ble-nus.md` before generating BLE advertising, GATT service registration, RX/TX, JSON protocol, or BLE debugging code.

## Deployment

Default handoff order:
1. Directory tree.
2. File contents or patch summary.
3. Upload path: copy the app folder into device `/apps`.
4. Restart: press `Ctrl+D` in Thonny after upload/delete.
5. Debugging: inspect Thonny logs and device-side errors.

Read `references/app-structure-and-deployment.md` for the full deployment checklist, lifecycle details, and resource-path rules.

Read `references/emulator.md` when the user wants to test locally in the Mini Dock simulator.

Read `references/publishing.md` when the user wants to package or upload an app to the App Gallery.

## Errors To Avoid

- Tying generic BLE output to a specific companion app unless requested.
- Treating observed numeric key codes as the public API when LVGL symbolic constants are available.
- Re-registering BLE GATT services repeatedly during app re-entry.
- Calling `ble.active(False)` in normal app stop without considering re-entry behavior.
- Using desktop paths or temporary folder names for assets.
- Guessing physical GPIO mappings from unrelated development boards.

## Test Prompts

Use `tests/prompts.md` when evaluating whether this skill still behaves correctly after edits.
