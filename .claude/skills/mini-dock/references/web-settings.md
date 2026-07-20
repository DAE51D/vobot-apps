# Web Settings

Use this reference when an app needs a web configuration page generated from `get_settings_json()`.

Source:
- App Settings on Web Page: https://dock.myvobot.com/developer/reference/web-page/
- Application Settings guide: https://dock.myvobot.com/developer/guides/app-settings/

## When To Use

Use web settings when users should configure app parameters from a browser instead of only through the Mini Dock screen and buttons.

The official Application Settings guide says configuration mode calls `get_settings_json()` in each app, generates HTML controls from the returned data, saves changed values on the device, and lets the app read them with `app_mgr.config()`.

Implement a top-level `get_settings_json()` in `__init__.py`. It should return a JSON-like dict with:
- `title`: page title
- optional `hint`: link dict with `url` and `label`
- `form`: list of settings components

```python
def get_settings_json():
    return {
        "title": "My App Settings",
        "hint": {
            "url": "https://example.com/help",
            "label": "Help",
        },
        "form": [
            {
                "type": "input",
                "default": "",
                "caption": "User name",
                "name": "username",
                "attributes": {
                    "maxLength": 20,
                    "placeholder": "Enter your name",
                },
            },
            {
                "type": "switch",
                "default": False,
                "caption": "Enable alerts",
                "name": "enable_alerts",
            },
        ],
    }
```

Read saved settings with `app_mgr.config()` after capturing `app_mgr` in `on_boot(apm)`.

## Component Types

### input

Text input:

```python
{
    "type": "input",
    "default": "",
    "caption": "User name",
    "name": "username",
    "attributes": {"maxLength": 20, "placeholder": "Enter your name"},
    "tip": "Shown below the field",
}
```

### select

Drop-down select. `default` should match one option value:

```python
{
    "type": "select",
    "default": "metric",
    "caption": "Units",
    "name": "units",
    "options": [("Metric", "metric"), ("Imperial", "imperial")],
}
```

### checkbox

Multiple selection. `default` is a list of selected values:

```python
{
    "type": "checkbox",
    "default": ["weather", "clock"],
    "caption": "Widgets",
    "name": "widgets",
    "options": [("Weather", "weather"), ("Clock", "clock")],
}
```

### radio

Single selection:

```python
{
    "type": "radio",
    "default": "small",
    "caption": "Size",
    "name": "size",
    "options": [("Small", "small"), ("Large", "large")],
}
```

### switch

Boolean switch:

```python
{
    "type": "switch",
    "default": False,
    "caption": "Enable alerts",
    "name": "enable_alerts",
}
```

### file

File upload component:

```python
{
    "type": "file",
    "caption": "Upload image",
    "file_path": "/image",
    "name": "image",
    "attributes": {
        "accept": ".jpg,.png",
        "multiple": False,
        "max_size": 5242880,
        "max_files": 5,
    },
}
```

Rules from the official reference:
- `file_path` must start with `/`.
- Use only lowercase letters, numbers, and underscores in `file_path`.
- `name` should use only lowercase letters and underscores.
- Uploaded files are saved under the app's `resources/app_config/...` folder.

### group

Dynamic configuration group for repeated sub-configurations:

```python
{
    "type": "group",
    "caption": "Sources",
    "name": "sources",
    "templates": {
        "template_name_default": "New Source",
        "template_config": [
            {
                "type": "input",
                "default": "",
                "caption": "Source name",
                "name": "source_name",
                "attributes": {"maxLength": 50},
            },
            {
                "type": "select",
                "default": "rss",
                "caption": "Type",
                "name": "source_type",
                "options": [("RSS", "rss"), ("API", "api")],
            },
        ],
        "combinations": {
            "caption": "Type",
            "name": "source_kind",
            "combinations_list": [
                {
                    "caption": "RSS",
                    "name": "rss",
                    "components": ["source_name"],
                },
                {
                    "caption": "API",
                    "name": "api",
                    "components": ["source_name", "source_type"],
                },
            ],
        },
    },
    "attributes": {"maxLength": 10},
}
```

## Naming Rules

- Prefer lowercase snake_case for `name`.
- Component `name` should be stable because saved config uses it as a key.
- Keep captions short and user-facing.
- Put detailed help in `tip` or `hint` rather than the caption.
