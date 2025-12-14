"""
ntfy App Settings Configuration
Defines settings that appear in the Vobot web UI at http://192.168.1.32/apps
"""

# Settings schema for the Vobot web interface
# The web UI will scan this and create form fields for users to configure
SETTINGS = {
    "category": "Productivity",
    "form": [
        {
            "type": "input",
            "default": "http://ntfy.home.lan",
            "caption": "ntfy Server URL",
            "name": "ntfy_server",
            "attributes": {"placeholder": "http://ntfy.home.lan"},
            "tip": "Full URL to the ntfy server"
        },
        {
            "type": "input",
            "default": "general",
            "caption": "ntfy Topic",
            "name": "ntfy_topic",
            "attributes": {"placeholder": "general"},
            "tip": "Topic name to subscribe to"
        },
        {
            "type": "input",
            "default": "30",
            "caption": "Fetch Interval (seconds)",
            "name": "fetch_interval",
            "attributes": {"maxLength": 3, "placeholder": "30"},
            "tip": "How often to check for new messages (5-300)"
        },
        {
            "type": "input",
            "default": "20",
            "caption": "Max Cached Messages",
            "name": "max_messages",
            "attributes": {"maxLength": 3, "placeholder": "20"},
            "tip": "Maximum messages to cache (5-100)"
        }
    ]
}

# Default values
DEFAULTS = {
    "ntfy_server": "http://ntfy.home.lan",
    "ntfy_topic": "general",
    "fetch_interval": 30,
    "max_messages": 20
}


def load_settings(app_mgr=None):
    """Load settings from app_mgr config or return defaults"""
    if app_mgr:
        config = app_mgr.config()
        # Convert string numbers to int
        settings = {}
        for key, val in config.items():
            if key in ["fetch_interval", "max_messages"]:
                try:
                    settings[key] = int(val)
                except:
                    settings[key] = DEFAULTS[key]
            else:
                settings[key] = val
        # Merge with defaults
        for key, val in DEFAULTS.items():
            if key not in settings:
                settings[key] = val
        return settings
    return DEFAULTS.copy()


def save_settings(settings):
    """Save settings to persistent storage"""
    import ujson
    try:
        with open('/settings/ntfy.json', 'w') as f:
            ujson.dump(settings, f)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


def get_setting(key, default=None):
    """Get a single setting value"""
    settings = load_settings()
    if default is None:
        default = DEFAULTS.get(key)
    return settings.get(key, default)


def set_setting(key, value):
    """Set a single setting value"""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)
