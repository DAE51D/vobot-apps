# BLE Nordic UART Service

Use this reference for generic BLE NUS advertising, service registration, RX/TX, and JSON command flows on Mini Dock MicroPython apps.

This reference merges the prior local/project BLE baseline but removes app-specific assumptions. It is not an official vendor guarantee and is not tied to any one companion app.

## Generic Identity

Make identity configurable:

```python
BLE_NAME = "Mini Dock"
APP_PROTOCOL = "json-nus"
```

Only use a branded or companion-specific name if the user requests it.

Standard Nordic UART Service UUIDs:
- service: `6e400001-b5a3-f393-e0a9-e50e24dcca9e`
- RX/write: `6e400002-b5a3-f393-e0a9-e50e24dcca9e`
- TX/notify: `6e400003-b5a3-f393-e0a9-e50e24dcca9e`

## Stable Implementation Rules

- Use raw `bluetooth.BLE()` for the local/project-verified RX baseline.
- Use `_IRQ_GATTS_WRITE` plus `gatts_read(rx_handle)` for RX.
- Use `gatts_notify(conn_handle, tx_handle, data)` for TX.
- Register the NUS GATT service only once per VM lifecycle.
- Cache the BLE object and handles in `builtins` so app re-entry can reuse them.
- Set the RX characteristic buffer to about `1024` bytes with append mode when available.
- During normal app stop, disconnect active centrals, stop advertising, clear IRQ handlers, and clean UI state.
- Avoid `ble.active(False)` during normal app stop unless a full BLE reset is intentionally requested.
- Assume one central connection at a time unless testing proves otherwise.

Repeated `gatts_register_services()` during app re-entry can freeze the app or produce service-busy behavior.

## Advertising

- Set the GAP name before advertising.
- Keep the primary advertising payload under 31 bytes.
- Prefer name-only advertising when the name is long.
- Let centrals discover NUS through GATT discovery after connecting.
- If the device appears as `ESP32`, verify the GAP name setup and fully restart after upload.

Minimal advertising payload helper:

```python
def adv_payload(name):
    name_b = name.encode()
    payload = bytearray()
    payload += bytes((2, 0x01, 0x06))
    if len(name_b) <= 26:
        payload += bytes((len(name_b) + 1, 0x09)) + name_b
    return payload
```

## Wire Protocol

Prefer newline-delimited UTF-8 JSON:

Incoming:

```json
{"cmd":"status"}
```

Outgoing:

```json
{"ack":"status","ok":true,"data":{}}
```

Rules:
- Accumulate RX bytes.
- Split complete packets on `\n` or `\r`.
- Decode UTF-8.
- Parse JSON.
- Send each JSON response followed by `\n`.
- Chunk TX notifications around 100 bytes to reduce MTU surprises.

Protocol fields should be app-defined. For generic apps, start with `cmd`, `ack`, `ok`, `error`, and `data`.

## Generic Command Suggestions

Useful generic commands:
- `status`: return app/device status.
- `ping`: return `pong`.
- `name`: return BLE/app name.
- `config`: return configurable fields.
- `set`: update a named setting if the app supports it.
- `unpair` or `disconnect`: disconnect the current central if desired.

Approval or permission flows are application-level protocols. If requested, model them generically:

```json
{"type":"prompt","id":"abc","text":"Allow action?"}
```

```json
{"cmd":"decision","id":"abc","decision":"allow"}
```

Do not assume a specific CLI, automation tool, or companion app.

## Not Verified By The Baseline

Do not claim support for these without separate tests:
- BLE OTA
- BLE file upload
- retransmission protocol
- measured throughput tuning
- multi-central behavior
