# Mini Dock Skill

A generic AI coding skill for building and reviewing **Mini Dock** MicroPython apps.

This repository contains the skill instructions. Device setup, SDK behavior, Thonny usage, app lifecycle, and resource-path rules belong to the official VOBOT documentation and are linked below instead of being duplicated here.

## Skill Guide

- Skill introduction and examples: [docs/skill-introduction.md](docs/skill-introduction.md)
- Main skill file: [SKILL.md](SKILL.md)
- Test prompts: [tests/prompts.md](tests/prompts.md)

## Repository Structure

```text
mini_dock/
|-- SKILL.md
|-- README.md
|-- agents/
|   `-- openai.yaml
|-- docs/
|   `-- skill-introduction.md
|-- references/
|   |-- app-structure-and-deployment.md
|   |-- ble-nus.md
|   |-- emulator.md
|   |-- hardware-and-peripherals.md
|   |-- publishing.md
|   |-- system-services.md
|   |-- ui-and-input.md
|   `-- web-settings.md
`-- tests/
    `-- prompts.md
```

## Official Mini Dock References

- VOBOT developer getting started: https://dock.myvobot.com/developer/getting_started/
- Important resource path configuration: https://dock.myvobot.com/developer/getting_started/#important-resource-file-path-configuration
- Thonny download: https://thonny.org/
- Application architecture: https://dock.myvobot.com/developer/guides/application-architecture/
- Application design: https://dock.myvobot.com/developer/guides/app-design/
- Button events: https://dock.myvobot.com/developer/guides/button-event/
- Interface guide: https://dock.myvobot.com/developer/guides/app-interface-guide/
- Application settings: https://dock.myvobot.com/developer/guides/app-settings/
- Publishing guide: https://dock.myvobot.com/developer/guides/publishing-guide/
- MiniDock emulator: https://dock.myvobot.com/developer/mini_dock_emulator/
- Peripherals reference: https://dock.myvobot.com/developer/reference/peripherals/
- Application manager: https://dock.myvobot.com/developer/reference/manager/
- Device: https://dock.myvobot.com/developer/reference/system/
- Settings: https://dock.myvobot.com/developer/reference/settings/
- Clocktime: https://dock.myvobot.com/developer/reference/clocktime/
- Network: https://dock.myvobot.com/developer/reference/network/
- App settings on web page: https://dock.myvobot.com/developer/reference/web-page/

## Install

```bash
npx skills add https://github.com/myvobot/dock-mini-app-skill --skill mini-dock
```

Restart or reload the app after installing.

## Use

```text
Use $mini-dock to build a generic Mini Dock app.
```

```text
Use $mini-dock to create a BLE NUS control app for Mini Dock.
```

```text
Use $mini-dock to review my Mini Dock app structure and resource paths.
```

## Scope

This skill is device-focused and app-neutral. It covers Mini Dock app structure, LVGL UI, input handling, SDK peripherals, GPIO safety policy, BLE NUS patterns, and deployment guidance. It does not assume compatibility with any single companion app or protocol.
