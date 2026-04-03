#!/usr/bin/env python3
"""
Shortcut Overlay — shows predefined keyboard shortcuts as an on-screen overlay.
Uses evdev to work on Wayland across all applications.

Usage:
  python3 main.py                   # loads configs/default.json
  python3 main.py --config:em       # loads configs/em.json
  python3 main.py --config em       # same
  python3 main.py --debug           # print all key events to stdout
"""

import json
import sys
import tkinter as tk
import threading
import pathlib
import evdev
from evdev import ecodes

# ── Config loading ────────────────────────────────────────────────────────────

CONFIGS_DIR = pathlib.Path(__file__).parent / "configs"

def parse_args(argv):
    config_name = "default"
    debug = False
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--debug":
            debug = True
        elif arg.startswith("--config:"):
            config_name = arg.split(":", 1)[1]
        elif arg == "--config" and i + 1 < len(argv):
            config_name = argv[i + 1]
            i += 1
        i += 1
    return config_name, debug

def load_config(name):
    path = CONFIGS_DIR / f"{name}.json"
    if not path.exists():
        print(f"Config not found: {path}")
        print(f"Available: {', '.join(p.stem for p in CONFIGS_DIR.glob('*.json'))}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)

# ── Key name normalisation ────────────────────────────────────────────────────

_MODIFIER_ALIASES = {
    "leftctrl":  "ctrl",
    "rightctrl": "ctrl",
    "leftshift": "shift",
    "rightshift": "shift",
    "leftalt":   "alt",
    "rightalt":  "alt",
    "alt_gr":    "alt",
    "leftmeta":  "super",
    "rightmeta": "super",
}

# Physical QWERTY evdev key name -> logical Dvorak character.
# Keys not listed are identical in both layouts (digits, modifiers, tab, etc.)
_DVORAK_REMAP = {
    "q": "apostrophe", "w": "comma",     "e": "dot",      "r": "p",
    "t": "y",          "y": "f",         "u": "g",        "i": "c",
    "o": "r",          "p": "l",
    "s": "o",          "d": "e",         "f": "u",        "g": "i",
    "h": "d",          "j": "h",         "k": "t",        "l": "n",
    "semicolon": "s",
    "z": "semicolon",  "x": "q",         "c": "j",        "v": "k",
    "b": "x",          "n": "b",
    "comma": "w",      "dot": "v",       "slash": "z",
    "leftbrace": "slash", "rightbrace": "equal", "apostrophe": "minus",
}

def normalise_code(code):
    entry = ecodes.keys.get(code)
    if entry is None:
        return None
    raw = entry[0] if isinstance(entry, (list, tuple)) else entry
    name = raw.removeprefix("KEY_").lower()
    name = _MODIFIER_ALIASES.get(name, name)
    return _DVORAK_REMAP.get(name, name)

# ── Overlay window ────────────────────────────────────────────────────────────

class Overlay:
    def __init__(self, settings):
        self.position   = settings.get("position",   "bottom-right")
        self.padding    = settings.get("padding",    24)
        self.display_ms = settings.get("display_ms", 1500)
        font_family     = "Sans"
        font_size       = settings.get("font_size",  20)
        fg              = settings.get("fg_color",   "#ffffff")
        bg              = settings.get("bg_color",   "#222222")

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg=bg)
        self.root.withdraw()

        self._frame = tk.Frame(self.root, bg=bg, padx=16, pady=10)
        self._frame.pack()

        self._label = tk.Label(
            self._frame,
            text="",
            font=(font_family, font_size, "bold"),
            fg=fg, bg=bg,
        )
        self._label.pack()

        self._desc = tk.Label(
            self._frame,
            text="",
            font=(font_family, max(font_size - 6, 10)),
            fg="#aaaaaa", bg=bg,
        )
        # packed/unpacked dynamically depending on whether description exists

        self._hide_job = None

    def show(self, label, description=""):
        self.root.after(0, self._show, label, description)

    def _show(self, label, description):
        self._label.config(text=label)
        if description:
            self._desc.config(text=description)
            self._desc.pack()
        else:
            self._desc.pack_forget()

        self.root.update_idletasks()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww = self.root.winfo_reqwidth()
        wh = self.root.winfo_reqheight()

        positions = {
            "bottom-right": (sw - ww - self.padding, sh - wh - self.padding),
            "bottom-left":  (self.padding,            sh - wh - self.padding),
            "top-right":    (sw - ww - self.padding,  self.padding),
            "top-left":     (self.padding,             self.padding),
        }
        x, y = positions.get(self.position, positions["bottom-right"])
        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()

        if self._hide_job:
            self.root.after_cancel(self._hide_job)
        self._hide_job = self.root.after(self.display_ms, self._hide)

    def _hide(self):
        self.root.withdraw()
        self._hide_job = None

    def run(self):
        self.root.mainloop()

# ── Keyboard listener (evdev) ─────────────────────────────────────────────────

class ShortcutListener:
    def __init__(self, overlay, watched):
        self.overlay = overlay
        self.watched = watched   # frozenset(keys) -> (label, description)
        self.pressed = set()
        self._lock   = threading.Lock()

    def _listen(self, device, debug):
        try:
            for event in device.read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                name = normalise_code(event.code)
                if debug and event.value in (0, 1):
                    action = "down" if event.value == 1 else "up"
                    print(f"[{device.name}] code={event.code} name={name!r} {action} | pressed={self.pressed}")
                if name is None:
                    continue
                with self._lock:
                    if event.value == 1:
                        self.pressed.add(name)
                        match = self.watched.get(frozenset(self.pressed))
                        if match:
                            self.overlay.show(*match)
                    elif event.value == 0:
                        self.pressed.discard(name)
        except OSError:
            pass

    def start(self, debug=False):
        keyboards = []
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                keys = d.capabilities().get(ecodes.EV_KEY, [])
                if ecodes.KEY_A in keys and ecodes.KEY_LEFTCTRL in keys:
                    keyboards.append(d)
                else:
                    d.close()
            except (OSError, PermissionError):
                pass

        if not keyboards:
            print("No keyboard devices found. Check /dev/input/ permissions.")
            return

        for device in keyboards:
            print(f"Listening on: {device.path} | {device.name}")
            t = threading.Thread(target=self._listen, args=(device, debug), daemon=True)
            t.start()

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config_name, debug = parse_args(sys.argv)
    config = load_config(config_name)

    print(f"Loaded config: {config.get('name', config_name)}")

    settings = config.get("settings", {})
    watched = {
        frozenset(s["keys"]): (s["label"], s.get("description", ""))
        for s in config.get("shortcuts", [])
    }

    overlay  = Overlay(settings)
    listener = ShortcutListener(overlay, watched)
    listener.start(debug=debug)
    print("Shortcut overlay running. Press Ctrl+C in this terminal to quit.")
    try:
        overlay.run()
    except KeyboardInterrupt:
        pass
