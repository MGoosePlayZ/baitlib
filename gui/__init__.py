"""
BaitLib GUI library (separate library, not part of lib.py).

    import gui
    ui = gui.UI()
    ui.add(gui.Button(20, 20, 140, 36, text="Click me", primary=True, on_click=lambda b: ui.toast("Hi!")))

    def onUpdate(dt):
        ui.update(dt)      # input, hover, focus, animation
        ui.draw()

Widgets use `(x, y, w, h)` first, then keywords. Children use coordinates relative to their container.
See gui.theme / gui.Theme for styling. Every widget also takes style={...} and enabled/visible/tooltip.
"""
import sys

import lib

from .core import (Theme, theme, Widget, Panel, Label, Separator, UI, Popup, Mods, vstack, hstack,
                   box, shadow, icon, shade, alpha, mix, mono_font)
from .basic import (Button, ToggleButton, Checkbox, Switch, RadioGroup, Radio, Slider, Progress, Spinner, LoadingBar)
from .text import (TextBox, TextArea, CodeBox, CodeBlock, Spinbox, add_language, highlight)

for _mod in ("containers", "data", "pickers"):
    try:
        __import__(f"{__name__}.{_mod}")
        _m = sys.modules[f"{__name__}.{_mod}"]
        globals().update({k: v for k, v in vars(_m).items() if not k.startswith("_") and k[0].isupper()})
    except ModuleNotFoundError as e:
        if f"{__name__}.{_mod}" not in str(e):
            raise

lib.gui = sys.modules[__name__]
