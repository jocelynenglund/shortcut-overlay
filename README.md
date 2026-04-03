# shortcut-overlay

An on-screen keyboard shortcut overlay for screen recordings on **Wayland Linux**.
Shows a small label whenever you press a shortcut from a predefined set — without capturing or interrupting any input.

## Why

Wayland's security model blocks global keyboard listeners, so tools like `screenkey` only work for XWayland apps. This tool reads directly from `/dev/input` via `evdev`, so it works across all apps including Chrome, Firefox, and native Wayland apps.

## Requirements

- Python 3.11+
- `evdev` — `pip install evdev`
- `tkinter` — usually pre-installed; if not: `sudo apt install python3-tk`
- User must be in the `input` group:
  ```bash
  sudo usermod -aG input $USER
  # log out and back in for this to take effect
  ```

## Usage

```bash
# Load the default config
python3 main.py

# Load a named config
python3 main.py --config:em
python3 main.py --config em

# Debug mode — prints every key event to stdout
python3 main.py --config:em --debug
```

## Configs

Configs live in the `configs/` directory as JSON files. Load one with `--config:<name>` where `<name>` is the filename without `.json`.

```
configs/
  default.json   # general shortcuts (save, undo, copy, paste…)
  em.json        # Event Modelling app
```

### Config format

```json
{
  "name": "My App",
  "settings": {
    "position":   "bottom-right",
    "padding":    24,
    "font_size":  20,
    "display_ms": 1500,
    "fg_color":   "#ffffff",
    "bg_color":   "#222222"
  },
  "shortcuts": [
    { "keys": ["ctrl", "s"],  "label": "Ctrl+S",  "description": "Save" },
    { "keys": ["ctrl", "z"],  "label": "Ctrl+Z",  "description": "Undo" }
  ]
}
```

**`settings` fields**

| Field | Default | Description |
|---|---|---|
| `position` | `bottom-right` | `bottom-right`, `bottom-left`, `top-right`, `top-left` |
| `padding` | `24` | Distance in px from screen edge |
| `font_size` | `20` | Label font size |
| `display_ms` | `1500` | How long the overlay stays visible (ms) |
| `fg_color` | `#ffffff` | Label text colour |
| `bg_color` | `#222222` | Background colour |

**`shortcuts` fields**

| Field | Required | Description |
|---|---|---|
| `keys` | yes | Array of key names that must be held simultaneously |
| `label` | yes | Primary text shown in the overlay |
| `description` | no | Smaller subtitle shown below the label |

**Valid key names:** `ctrl`, `shift`, `alt`, `super`, `a`–`z`, `0`–`9`, `tab`, `space`, `enter`, `backspace`, `esc`, `delete`, `up`, `down`, `left`, `right`, `slash`, `equal`, `minus`, and other evdev key names (lowercase, no `KEY_` prefix).

## Keyboard layout

The tool includes a **Dvorak** remap by default. If you use a different layout, edit `_DVORAK_REMAP` in `main.py` — or remove it entirely if you're on QWERTY. The remap translates physical evdev key codes to their logical characters so config files can use the logical key name (e.g. `"s"` rather than the physical key position).

Use `--debug` to see which names your keys resolve to if shortcuts aren't firing as expected.
