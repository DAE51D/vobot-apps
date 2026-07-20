# Mini Dock Skill Introduction

This document is the skill-specific introduction that can be linked from a Mini Dock manual, internal guide, or project README.

## What The Skill Does

`mini-dock` helps an AI coding agent generate, modify, and review Mini Dock apps without binding the output to a single companion app.

It focuses on:
- app folder and entrypoint conventions
- `NAME` and resource-path correctness
- optional auto-switch carousel support with `CAN_BE_AUTO_SWITCHED`
- LVGL screen and input patterns
- app manager, device info, settings, time, and network status
- web settings forms with `get_settings_json()`
- built-in SDK peripherals
- local simulator debugging
- packaging and App Gallery publishing
- safe GPIO and pin-definition decisions
- generic BLE Nordic UART Service (NUS) workflows
- short Thonny deployment and debugging handoff

## When To Use It

Use the skill when asking for:

```text
Use $mini-dock to make a Mini Dock app that displays a QR code.
```

```text
Use $mini-dock to create a generic BLE NUS status monitor.
```

```text
Use $mini-dock to check whether my app resources will work after upload.
```

```text
Use $mini-dock to add button/encoder navigation to this LVGL screen.
```

## What It Does Not Replace

The skill does not replace the Mini Dock manual. For device setup, SDK API details, and official constraints, use the official references:

- Developer getting started: https://dock.myvobot.com/developer/getting_started/
- Resource path configuration: https://dock.myvobot.com/developer/getting_started/#important-resource-file-path-configuration
- Application architecture: https://dock.myvobot.com/developer/guides/application-architecture/
- Button events: https://dock.myvobot.com/developer/guides/button-event/
- Interface guide: https://dock.myvobot.com/developer/guides/app-interface-guide/
- Peripherals reference: https://dock.myvobot.com/developer/reference/peripherals/

## Minimal App Shape

The skill generates or checks apps in this basic shape:

```text
my-app/
|-- __init__.py
`-- resources/
```

The entrypoint is `__init__.py`, and asset paths should be derived from `NAME`:

```python
NAME = "My App"
CAN_BE_AUTO_SWITCHED = True
ICON = f"A:apps/{NAME}/resources/icon.png"
```

See the official resource path documentation for the device-level rule.

## Reference Files In This Skill

- `references/app-structure-and-deployment.md`: app layout, lifecycle, upload handoff, path checks
- `references/ui-and-input.md`: LVGL, fonts, screen, buttons, encoder input
- `references/hardware-and-peripherals.md`: SDK peripherals and GPIO safety policy
- `references/emulator.md`: Docker-based Mini Dock simulator setup and debugging
- `references/publishing.md`: manifest, packaging, `.vbt`, and App Gallery upload flow
- `references/system-services.md`: app manager, device, settings, clocktime, and network APIs
- `references/web-settings.md`: web configuration forms and saved app settings
- `references/ble-nus.md`: generic BLE NUS advertising, GATT, and JSON protocol patterns

## Design Principle

Keep generated apps portable and explicit:
- use official SDK modules before raw hardware access
- prefer symbolic LVGL key constants over numeric key codes
- keep BLE identity and JSON protocol fields configurable
- do not invent physical pin mappings without hardware-specific evidence
- call out unverified assumptions clearly
