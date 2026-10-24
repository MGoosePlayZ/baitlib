"""Buttons, toggles, sliders and progress indicators."""
import math

import lib

from .core import Widget, box, clamp, icon, lerp, mix, alpha


class Button(Widget):
    """gui.Button(x, y, w, h, text="OK", on_click=fn, primary=False). w/h None = fit the text."""
    focusable = True
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=None, h=None, text="", on_click=None, primary=False, **kw):
        self.text_value, self.on_click, self.primary = text, on_click, primary
        super().__init__(x, y, w or 100, h or 34, **kw)
        if w is None:
            self.w = max(48, self.measure(str(text))[0] + 2 * self.plain("pad", 8) + 8)
        if h is None:
            self.h = self.size_pt() + 16

    def colors(self):
        if not self.enabled:
            return self.get("bg_disabled"), self.get("border_disabled"), self.get("fg_disabled")
        if self.primary:
            bg = self.get("accent")
            return bg, (self.get("border_focus") if self.focused else bg), self.get("accent_fg")
        return self.get("bg"), (self.get("border_focus") if self.focused else self.get("border")), self.get("fg")

    def draw(self):
        bg, border, fg = self.colors()
        box(self.ax, self.ay, self.w, self.h, bg, border, self.plain("border_w", 1), self.plain("radius", 6))
        self.draw_content(fg)

    def draw_content(self, fg):
        t = self.fit(str(self.text_value), self.w - 12)
        self.text(t, self.ax + self.w / 2, self.ay + self.h / 2, fg, None, "center", "middle")

    def click(self, x, y, button):
        if button == "left" and self.on_click:
            self.on_click(self)

    def key_down(self, key, mods):
        if key in ("Enter", "Space"):
            self.click(0, 0, "left")
            return True
        return False


class ToggleButton(Button):
    """A button that stays pressed. .value, on_change(value)"""

    def __init__(self, *a, value=False, on_change=None, **kw):
        super().__init__(*a, **kw)
        self.value, self.on_change = bool(value), on_change

    def colors(self):
        if not self.enabled:
            return super().colors()
        if self.value:
            bg = self.get("accent")
            return bg, (self.get("border_focus") if self.focused else bg), self.get("accent_fg")
        return super().colors()

    def click(self, x, y, button):
        if button == "left":
            self.value = not self.value
            if self.on_change:
                self.on_change(self.value)


class Checkbox(Widget):
    """gui.Checkbox(x, y, w, h, text="Label", value=False, on_change=fn)"""
    focusable = True
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=None, h=None, text="", value=False, on_change=None, **kw):
        self.text_value, self.value, self.on_change = text, bool(value), on_change
        super().__init__(x, y, w or 160, h or 24, **kw)
        if w is None:
            self.w = self.measure(str(text))[0] + self.size_pt() + 14
        if h is None:
            self.h = self.size_pt() + 8

    def toggle(self):
        self.value = not self.value
        if self.on_change:
            self.on_change(self.value)

    def draw(self):
        s = self.size_pt() + 2
        bx, by = self.ax, self.ay + (self.h - s) / 2
        if not self.enabled:
            fill, border, fg = self.get("bg_disabled"), self.get("border_disabled"), self.get("fg_disabled")
        else:
            fill = self.get("accent") if self.value else self.get("bg")
            border = self.get("border_focus") if self.focused else (self.get("accent") if self.value else self.get("border"))
            fg = self.get("fg")
        box(bx, by, s, s, fill, border, self.plain("border_w", 1), min(4, self.plain("radius", 6)))
        if self.value:
            icon("check", bx + s / 2, by + s / 2, s * 0.8, self.get("accent_fg") if self.enabled else fg, 2)
        self.text(str(self.text_value), bx + s + 8, self.ay + self.h / 2, fg, None, "left", "middle")

    def click(self, x, y, button):
        if button == "left":
            self.toggle()

    def key_down(self, key, mods):
        if key == "Space":
            self.toggle()
            return True
        return False


class Switch(Widget):
    """On/off switch with a sliding knob. gui.Switch(x, y, w, h, value=False, text="", on_change=fn)"""
    focusable = True
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=None, h=None, value=False, text="", on_change=None, **kw):
        self.value, self.text_value, self.on_change = bool(value), text, on_change
        super().__init__(x, y, w or 44, h or 24, **kw)
        self.track_w = 44 if w is None else min(w, 44)
        if w is None and text:
            self.w = self.track_w + 10 + self.measure(str(text))[0]
        self._t = 1.0 if self.value else 0.0

    def update(self, dt):
        self._t = lerp(self._t, 1.0 if self.value else 0.0, min(1.0, dt * 16))

    def draw(self):
        h, tw = self.h, self.track_w
        on, off = self.get("accent"), self.get("track")
        col = mix(off, on, self._t) if self.enabled else self.get("bg_disabled")
        box(self.ax, self.ay, tw, h, col, self.get("border_focus") if self.focused else None, 1, h / 2)
        kx = self.ax + h / 2 + (tw - h) * self._t
        lib.draw.circle(0x000000 if False else "#00000040", 0, kx, self.ay + h / 2 + 1, h / 2 - 2)
        lib.draw.circle(self.get("accent_fg") if self.enabled else self.get("fg_disabled"), 0, kx, self.ay + h / 2, h / 2 - 3)
        if self.text_value:
            self.text(str(self.text_value), self.ax + tw + 10, self.ay + h / 2,
                      self.get("fg") if self.enabled else self.get("fg_disabled"), None, "left", "middle")

    def click(self, x, y, button):
        if button == "left":
            self.value = not self.value
            if self.on_change:
                self.on_change(self.value)

    def key_down(self, key, mods):
        if key in ("Space", "Enter"):
            self.click(0, 0, "left")
            return True
        return False


class RadioGroup:
    """Shared by Radio buttons: group.value is the selected key."""

    def __init__(self, value=None, on_change=None):
        self.value, self.on_change = value, on_change

    def select(self, key):
        if key != self.value:
            self.value = key
            if self.on_change:
                self.on_change(key)


class Radio(Widget):
    """gui.Radio(x, y, w, h, text="Option", group=group, key="a")"""
    focusable = True
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=None, h=None, text="", group=None, key=None, **kw):
        self.text_value, self.group, self.key = text, group or RadioGroup(), key if key is not None else text
        super().__init__(x, y, w or 160, h or 24, **kw)
        if w is None:
            self.w = self.measure(str(text))[0] + self.size_pt() + 14
        if h is None:
            self.h = self.size_pt() + 8

    @property
    def selected(self):
        return self.group.value == self.key

    def draw(self):
        s = self.size_pt() + 2
        cx, cy = self.ax + s / 2, self.ay + self.h / 2
        if not self.enabled:
            border, fg = self.get("border_disabled"), self.get("fg_disabled")
        else:
            border = self.get("border_focus") if self.focused else (self.get("accent") if self.selected else self.get("border"))
            fg = self.get("fg")
        lib.draw.circle(self.get("bg") if self.enabled else self.get("bg_disabled"), 0, cx, cy, s / 2)
        lib.draw.circle(border, 2 if self.selected else 1, cx, cy, s / 2)
        if self.selected:
            lib.draw.circle(self.get("accent") if self.enabled else fg, 0, cx, cy, s / 4 + 1)
        self.text(str(self.text_value), self.ax + s + 8, self.ay + self.h / 2, fg, None, "left", "middle")

    def click(self, x, y, button):
        if button == "left":
            self.group.select(self.key)

    def key_down(self, key, mods):
        if key == "Space":
            self.group.select(self.key)
            return True
        return False


class Slider(Widget):
    """gui.Slider(x, y, w, h, min=0, max=100, value=50, step=None, vertical=False, show_value=True, on_change=fn)"""
    focusable = True
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=200, h=26, min=0.0, max=100.0, value=None, step=None, vertical=False,
                 show_value=False, fmt=None, on_change=None, **kw):
        super().__init__(x, y, w, h, **kw)
        self.min, self.max, self.step, self.vertical = min, max, step, vertical
        self.show_value, self.fmt, self.on_change = show_value, fmt, on_change
        self.value = min if value is None else value

    @property
    def fraction(self):
        return 0.0 if self.max == self.min else clamp((self.value - self.min) / (self.max - self.min), 0, 1)

    def set_value(self, v, notify=True):
        if self.step:
            v = self.min + round((v - self.min) / self.step) * self.step
        v = clamp(v, self.min, self.max)
        if isinstance(self.step, int) and isinstance(self.min, int):
            v = int(round(v))
        if v != self.value:
            self.value = v
            if notify and self.on_change:
                self.on_change(v)

    def _track(self):
        pad = self.h / 2 if not self.vertical else self.w / 2
        if self.vertical:
            return self.ax + self.w / 2, self.ay + pad, self.ay + self.h - pad
        return self.ay + self.h / 2, self.ax + pad, self.ax + self.w - pad

    def _from_mouse(self, x, y):
        c, a, b = self._track()
        f = ((y if self.vertical else x) - a) / max(1, (b - a))
        if self.vertical:
            f = 1 - f
        self.set_value(self.min + clamp(f, 0, 1) * (self.max - self.min))

    def draw(self):
        c, a, b = self._track()
        f = self.fraction
        th = 6
        r = (self.w if self.vertical else self.h) / 2 - 3
        off = self.get("track")
        on = self.get("accent") if self.enabled else self.get("border_disabled")
        if self.vertical:
            box(c - th / 2, a, th, b - a, off, None, 0, th / 2)
            ky = b - (b - a) * f
            box(c - th / 2, ky, th, b - ky, on, None, 0, th / 2)
            kx, ky2 = c, ky
        else:
            box(a, c - th / 2, b - a, th, off, None, 0, th / 2)
            kx = a + (b - a) * f
            box(a, c - th / 2, kx - a, th, on, None, 0, th / 2)
            ky2 = c
        if self.focused:
            lib.draw.circle(alpha(self.get("border_focus"), 0.35), 0, kx, ky2, r + 4)
        lib.draw.circle("#00000040", 0, kx, ky2 + 1, r)
        lib.draw.circle(self.get("accent_fg") if self.enabled else self.get("fg_disabled"), 0, kx, ky2, r)
        lib.draw.circle(on, 2, kx, ky2, r)
        if self.show_value:
            s = self.fmt(self.value) if self.fmt else (f"{self.value:g}" if isinstance(self.value, float) else str(self.value))
            self.text(s, self.ax + self.w + 8 if not self.vertical else self.ax + self.w / 2,
                      self.ay + self.h / 2 if not self.vertical else self.ay + self.h + 4,
                      self.get("fg_muted"), None, "left" if not self.vertical else "center", "middle" if not self.vertical else "top")

    def mouse_down(self, x, y, button, clicks):
        if button == "left":
            self._from_mouse(x, y)

    def mouse_drag(self, x, y):
        self._from_mouse(x, y)

    def key_down(self, key, mods):
        d = self.step or (self.max - self.min) / 20
        if key in ("Left", "Down"):
            self.set_value(self.value - d)
        elif key in ("Right", "Up"):
            self.set_value(self.value + d)
        elif key == "Home":
            self.set_value(self.min)
        elif key == "End":
            self.set_value(self.max)
        else:
            return False
        return True


class Progress(Widget):
    """Determinate bar. gui.Progress(x, y, w, h, value=0.4, min=0, max=1, show_text=True)"""
    passthrough = True

    def __init__(self, x=0, y=0, w=200, h=18, value=0.0, min=0.0, max=1.0, show_text=False, fmt=None, animated=True, **kw):
        super().__init__(x, y, w, h, **kw)
        self.value, self.min, self.max, self.show_text, self.fmt, self.animated = value, min, max, show_text, fmt, animated
        self._disp = self.fraction

    @property
    def fraction(self):
        return 0.0 if self.max == self.min else clamp((self.value - self.min) / (self.max - self.min), 0, 1)

    def update(self, dt):
        self._disp = lerp(self._disp, self.fraction, min(1.0, dt * 10)) if self.animated else self.fraction

    def draw(self):
        r = self.h / 2
        box(self.ax, self.ay, self.w, self.h, self.get("track"), None, 0, r)
        w = max(0.0, self.w * self._disp)
        if w > 0:
            box(self.ax, self.ay, w, self.h, self.get("accent"), None, 0, r)
        if self.show_text:
            s = self.fmt(self.value) if self.fmt else f"{self.fraction * 100:.0f}%"
            self.text(s, self.ax + self.w / 2, self.ay + self.h / 2, self.get("accent_fg") if self._disp > 0.5 else self.get("fg"),
                      max(10, self.h - 6), "center", "middle")


class Spinner(Widget):
    """Rotating dots for 'busy'. gui.Spinner(x, y, size=32, dots=12, speed=1.0)"""
    passthrough = True

    def __init__(self, x=0, y=0, size=32, dots=12, speed=1.0, **kw):
        super().__init__(x, y, size, size, **kw)
        self.dots, self.speed, self.t = dots, speed, 0.0

    def update(self, dt):
        self.t += dt * self.speed

    def draw(self):
        cx, cy = self.ax + self.w / 2, self.ay + self.h / 2
        R = self.w / 2 - self.w * 0.1
        head = (self.t * 1.2) % 1.0
        col = self.get("accent")
        for i in range(self.dots):
            f = i / self.dots
            age = (head - f) % 1.0
            a = 1 - age
            ang = f * math.tau - math.pi / 2
            lib.draw.circle(alpha(col, 0.15 + 0.85 * a ** 2), 0, cx + math.cos(ang) * R, cy + math.sin(ang) * R,
                            self.w * (0.06 + 0.05 * a))


class LoadingBar(Widget):
    """Indeterminate bar with a segment sweeping back and forth. gui.LoadingBar(x, y, w, h)"""
    passthrough = True

    def __init__(self, x=0, y=0, w=200, h=6, speed=1.0, **kw):
        super().__init__(x, y, w, h, **kw)
        self.speed, self.t = speed, 0.0

    def update(self, dt):
        self.t += dt * self.speed

    def draw(self):
        r = self.h / 2
        box(self.ax, self.ay, self.w, self.h, self.get("track"), None, 0, r)
        seg = self.w * 0.3
        p = (math.sin(self.t * 2.4 - math.pi / 2) + 1) / 2
        x = self.ax + (self.w - seg) * p
        self.ui.push_clip(self.ax, self.ay, self.w, self.h) if self.ui else None
        box(x, self.ay, seg, self.h, self.get("accent"), None, 0, r)
        if self.ui:
            self.ui.pop_clip()
