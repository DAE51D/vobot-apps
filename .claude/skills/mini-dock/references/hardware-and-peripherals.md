# Hardware And Peripherals

Use this reference for built-in hardware, SDK peripherals, connector/pin caution, and raw GPIO decisions.

Sources:
- Official peripherals reference: https://dock.myvobot.com/developer/reference/peripherals/
- Official device reference: https://dock.myvobot.com/developer/reference/system/
- Official settings reference: https://dock.myvobot.com/developer/reference/settings/
- Official product intro/spec: https://dock.myvobot.com/

## Device Facts

Publicly documented hardware facts:
- device family: Mini Dock
- screen: 2 inch, 320x240, 16M colors
- ports include USB-C, USB 3.0, HDMI, and Ethernet
- Python app development is supported through the Mini Dock SDK and MicroPython/LVGL

Use `device` when available:

```python
import device

dev_id = device.id
dev_model = device.model
hardware_version = device.version.hardware
firmware_version = device.version.firmware
nightstand = device.in_nightstand_mode()
```

Use `settings` for system preferences:

```python
import settings

use_celsius = settings.temp_unit() == 1
use_24h = settings.hour24()
```

## Built-In Peripherals

Prefer SDK modules over raw pins for built-in hardware.

Common rules:
- Import the official SDK module with `import peripherals`.
- Call `acquire()` before controlling shared peripherals that require ownership.
- Call `release()` in `on_stop()` or a `finally` block so system effects can resume.
- Treat brightness and light-effect changes as temporary app-owned state unless the official API says otherwise.

### Screen

Use screen APIs for display brightness and resolution. Screen brightness accepts 0-100; without an argument it returns the current value. The official reference notes app-set screen brightness is temporary and reverts when the app closes.

```python
import peripherals

resolution = peripherals.screen.screen_resolution
brightness = peripherals.screen.brightness()
peripherals.screen.brightness(50)
```

### Buzzer

Use the buzzer API for tones. Check `peripherals.buzzer.enabled` when an app needs to know whether buzzing is allowed. Frequency range is 100-8000 Hz; volume range is 0-100, and volume 0 stops the buzz. `acquire()`, `release()`, `set_freq()`, and `set_volume()` return success/failure booleans.

```python
import peripherals

async def on_start():
    if peripherals.buzzer.enabled and peripherals.buzzer.acquire():
        try:
            peripherals.buzzer.set_freq(400)
            peripherals.buzzer.set_volume(50)
        finally:
            peripherals.buzzer.set_volume(0)
            peripherals.buzzer.release()
```

### LED Clock

The LED clock needs ownership with `acquire()`. While acquired, the system's built-in LED clock effect stops; after `release()`, it resumes.

Lamp groups:
- groups 1-4: seven-segment digit groups
- group 4 bit 8: colon
- group 5: weekdays and PM
- group 6: symbols such as `.`, `%`, Celsius, and Fahrenheit

Digit segment values from the official reference:

```python
DIGITS = {
    0: 0x5F,
    1: 0x06,
    2: 0x3B,
    3: 0x2F,
    4: 0x66,
    5: 0x6D,
    6: 0x7D,
    7: 0x07,
    8: 0x7F,
    9: 0x6F,
}
```

`brightness()` gets or sets LED clock brightness from 0-100. The official reference notes this adjusted brightness is temporary and reverts after release or app close.

```python
import peripherals

if peripherals.led_clock.acquire():
    try:
        peripherals.led_clock.set_display(1, DIGITS[1])
        peripherals.led_clock.set_display(2, DIGITS[2])
        peripherals.led_clock.set_display(3, DIGITS[3])
        peripherals.led_clock.set_display(4, DIGITS[4] | 0x80)
        peripherals.led_clock.brightness(80)
    finally:
        peripherals.led_clock.release()
```

### Ambient Light

The ambient light needs ownership with `acquire()`. While acquired, the system's built-in ambient effect stops; after `release()`, it resumes.

Use `ambient_light.count` to read LED count. `set_color(buffer, repeat=True)` accepts RGB tuples in 0-255 ranges. If the buffer is shorter than the LED count, repeat mode can fill the strip; if longer, only the initial matching segment is used. `brightness()` gets or sets 0-100 and is temporary until release/app close.

```python
import peripherals

if peripherals.ambient_light.acquire():
    try:
        count = peripherals.ambient_light.count
        pattern = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        peripherals.ambient_light.set_color(pattern, True)
        peripherals.ambient_light.brightness(80)
    finally:
        peripherals.ambient_light.release()
```

## Physical Pins And Raw GPIO

Do not assume Mini Dock has the same pin mapping as unrelated development boards.

Skill policy:
- If the user asks for "pin definitions", first distinguish built-in peripheral APIs, external connector pins, and raw MCU GPIO.
- For built-in functions, use SDK modules above.
- For physical connector wiring, ask for or inspect the exact hardware revision, schematic, board photo, or vendor documentation.
- For raw GPIO code, generate a diagnostic REPL script rather than claiming a fixed pinout.
- Avoid assigning GPIOs used by display, buttons, USB, flash, boot straps, or internal peripherals unless verified.

Diagnostic pattern:

```python
from machine import Pin
import time

PIN = 0  # replace only after hardware verification
p = Pin(PIN, Pin.IN, Pin.PULL_UP)

while True:
    print(PIN, p.value())
    time.sleep_ms(200)
```

When producing code that uses raw GPIO, label the mapping as "user-provided" or "needs device verification" unless it comes from a trusted source for the exact Mini Dock hardware revision.
