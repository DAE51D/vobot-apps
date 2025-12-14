"""
ntfy - Minimal Test Version
Just show that the app can load and display something
"""
import lvgl as lv

NAME = "ntfy"
ICON = "A:apps/ntfy/resources/icon.png"

scr = None
label = None

async def on_start():
    """Called when app starts"""
    global scr, label
    print("=== MINIMAL ntfy on_start() ===")
    
    try:
        scr = lv.obj()
        label = lv.label(scr)
        label.set_text("ntfy App\nLoaded!")
        label.center()
        lv.scr_load(scr)
        print("App loaded successfully")
    except Exception as e:
        print(f"Error in on_start: {e}")

async def on_running_foreground():
    """Called every ~200ms when app is active"""
    pass

async def on_stop():
    """Called when leaving app"""
    global scr, label
    if scr:
        scr.clean()
        del scr
        scr = None
    label = None

def get_settings_json():
    """Return settings schema"""
    return {}
