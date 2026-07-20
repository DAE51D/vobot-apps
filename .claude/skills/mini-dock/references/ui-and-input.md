# UI And Input

Use this reference when building LVGL layouts, screen-size adaptive UI, fonts, buttons, encoder flows, or input diagnostics.

Sources:
- Official interface guide: https://dock.myvobot.com/developer/guides/app-interface-guide/
- Official button events: https://dock.myvobot.com/developer/guides/button-event/
- Official product intro/spec: https://dock.myvobot.com/

## Screen

The official interface guide states the system uses MicroPython and LVGL, with LVGL version 9.1 on the current Mini Dock.

Known public device spec:
- 2 inch IPS LCD.
- 320x240 resolution.
- 16M colors.

Runtime-first resolution pattern:

```python
def get_resolution():
    try:
        import peripherals
        return peripherals.screen.screen_resolution
    except Exception:
        return (320, 240)
```

Use 320x240 as the fallback. Do not use 240x135 as the default for new Mini Dock code.

## LVGL Baseline

```python
import lvgl as lv

scr = None
label = None

async def on_start():
    global scr, label
    scr = lv.obj()
    label = lv.label(scr)
    label.set_text("Ready")
    label.center()
    lv.scr_load(scr)

async def on_stop():
    global scr, label
    if scr:
        scr.clean()
    scr = None
    label = None
```

## Fonts

Officially documented font names include:
- character fonts: `font_ascii_10`, `font_ascii_14`, `font_ascii_18`, `font_ascii_22`, `font_ascii_bold_18`, `font_ascii_bold_22`, `font_ascii_bold_28`, `font_ascii_bold_48`
- number fonts: `font_numbers_32`, `font_numbers_72`, `font_numbers_92`

If unsure, inspect with `dir(lv)` on device.

Font note from the official guide: one font file contains one font size. If the same text needs different sizes, use different font objects, such as `lv.font_ascii_14` and `lv.font_ascii_22`.

## Input API

Use LVGL events and symbolic constants:

```python
def event_handler(e):
    key = e.get_key()
    if key == lv.KEY.RIGHT:
        print("up")
    elif key == lv.KEY.LEFT:
        print("down")
    elif key == lv.KEY.ENTER:
        print("enter")
    elif key == lv.KEY.ESC:
        print("esc")

scr.add_event(event_handler, lv.EVENT.ALL, None)
```

Official operation mapping:
- encoder clockwise/down: `lv.KEY.LEFT`
- encoder counter-clockwise/up: `lv.KEY.RIGHT`
- encoder press: `lv.KEY.ENTER`
- ESC button: `lv.KEY.ESC`

Observed numeric codes from prior local testing:
- left/rotate: `19`
- right/rotate: `20`
- enter/press: `10`
- back/ESC: `27`
- duplicate/system back: `411`

Use numeric codes only for diagnostics or compatibility shims. Prefer `lv.KEY.*` in generated apps.

## Layout Guidance

- Size labels from runtime screen width.
- Use circular scrolling for long text.
- Avoid dense redraw in `on_running_foreground`; update only when state changes where possible.
- Keep cleanup idempotent because apps may be entered and left repeatedly.
