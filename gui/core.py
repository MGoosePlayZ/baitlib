"""GUI core: theme, Widget base class, containers, the UI manager (input routing, focus, popups, modals, toasts)."""
import math

import pygame

import lib

# ====================================================================== theme
DEFAULTS = dict(
    # text
    fg=0xE8ECF4, fg_muted=0x8E97AD, fg_disabled=0x5B6479,
    font=None, font_size=16, mono_font=None, mono_size=15,
    # surfaces
    bg=0x252A3A, bg_hover=0x2F3650, bg_active=0x1D2130, bg_disabled=0x1E2230,
    border=0x3B4360, border_hover=0x5A678F, border_focus=0x6FA8FF, border_disabled=0x2C3248,
    border_w=1, radius=6, pad=8,
    # accent / semantic
    accent=0x4C8DFF, accent_hover=0x6FA3FF, accent_active=0x3A74DB, accent_fg=0xFFFFFF,
    track=0x2E3550, success=0x45C37B, warning=0xF0B24A, danger=0xEF5B6B, info=0x4C8DFF,
    # containers / overlays
    panel_bg=0x1B1F2E, panel_border=0x33395A, popup_bg=0x20253A, popup_border=0x46507A,
    overlay="#000000A0", shadow="#00000022", selection="#4C8DFF66", caret=0xFFFFFF,
    row_alt="#FFFFFF08", row_hover="#FFFFFF10", row_selected="#4C8DFF55",
    # syntax highlighting
    syn_default=0xD6DAE6, syn_keyword=0xC792EA, syn_string=0xC3E88D, syn_comment=0x667088,
    syn_number=0xF78C6C, syn_function=0x82AAFF, syn_builtin=0xFFCB6B, syn_gutter=0x586078,
)

LIGHT = dict(
    fg=0x1D2330, fg_muted=0x6A7388, fg_disabled=0xA4ABBB,
    bg=0xFFFFFF, bg_hover=0xEEF2FA, bg_active=0xDDE5F5, bg_disabled=0xF0F2F6,
    border=0xC5CCDC, border_hover=0x9AA6C2, border_focus=0x3B7BFF, border_disabled=0xDDE1EA,
    accent=0x3B7BFF, accent_hover=0x5B92FF, accent_active=0x2A63D8,
    track=0xDCE2EF, panel_bg=0xF4F6FB, panel_border=0xD3D9E8, popup_bg=0xFFFFFF, popup_border=0xB9C2D8,
    overlay="#00000066", shadow="#00000018", selection="#3B7BFF55", caret=0x1D2330,
    row_alt="#00000007", row_hover="#00000010", row_selected="#3B7BFF40",
    syn_default=0x2B3245, syn_keyword=0x8A3FC7, syn_string=0x3E8F2B, syn_comment=0x9AA3B8,
    syn_number=0xD2601A, syn_function=0x2B6BD6, syn_builtin=0xB8860B, syn_gutter=0x9AA3B8,
)


class Theme:
    """Styles are looked up per key: widget.style (instance) > theme[ClassName] (most derived class first)
    > theme["*"]. At every level `key_state` (state = disabled, active, focus, hover) beats plain `key`.

        theme.set("*", accent=0xFF6B6B, radius=10)          # everything
        theme.set("Button", bg=0x303030, bg_hover=0x404040)   # every Button (and subclasses)
        button.style["bg"] = 0x00AA00                         # one widget
    """

    def __init__(self, **base):
        self.d = {"*": dict(DEFAULTS, **base)}
        self.version = 0

    def set(self, widget="*", **values):
        if not isinstance(widget, str):
            widget = widget.__name__
        self.d.setdefault(widget, {}).update(values)
        self.version += 1
        return self

    def copy(self):
        t = Theme()
        t.d = {k: dict(v) for k, v in self.d.items()}
        return t

    @classmethod
    def dark(cls):
        return cls()

    @classmethod
    def light(cls):
        return cls(**LIGHT)


theme = Theme()          # shared default theme: gui.theme.set(...)

_mono_cache = []


def mono_font():
    """best monospace system font (or None -> default font)"""
    if not _mono_cache:
        path = pygame.font.match_font("dejavusansmono,liberationmono,consolas,menlo,couriernew,ubuntumono,monospace")
        try:
            _mono_cache.append(lib.file.font(path) if path else None)
        except Exception:
            _mono_cache.append(None)
    return _mono_cache[0]


class Mods:
    def __init__(self, shift=False, ctrl=False, alt=False):
        self.shift, self.ctrl, self.alt = shift, ctrl, alt


# ====================================================================== drawing helpers
def shade(c, k):
    """mix a color toward white (k>0) or black (k<0)"""
    r, g, b, a = lib._rgba(c)
    t = 255 if k > 0 else 0
    k = abs(k)
    return [(r + (t - r) * k) / 255, (g + (t - g) * k) / 255, (b + (t - b) * k) / 255, a / 255]


def alpha(c, a):
    r, g, b, _ = lib._rgba(c)
    return [r / 255, g / 255, b / 255, a]


def mix(c1, c2, t):
    a, b = lib._rgba(c1), lib._rgba(c2)
    return [(a[i] + (b[i] - a[i]) * t) / 255 for i in range(4)]


def box(x, y, w, h, fill=None, border=None, bw=1, radius=0):
    if w <= 0 or h <= 0:
        return
    if fill is not None:
        if radius > 0:
            lib.draw.roundedRectangle(fill, 0, x, y, w, h, radius, radius)
        else:
            lib.draw.rectangle(fill, 0, x, y, w, h)
    if border is not None and bw > 0:
        if radius > 0:
            lib.draw.roundedRectangle(border, bw, x, y, w, h, radius, radius)
        else:
            lib.draw.rectangle(border, bw, x, y, w, h)


def shadow(x, y, w, h, radius=6, size=8, color="#00000030"):
    for i in range(size, 0, -3):
        lib.draw.roundedRectangle(color, 0, x - i, y - i + size * 0.4, w + 2 * i, h + 2 * i, radius + i, radius + i)


def icon(name, cx, cy, size, color, weight=2):
    """small vector icons centred on cx, cy"""
    s = size / 2
    line = lambda ax, ay, bx, by: lib.draw.line(color, weight, cx + ax * s, cy + ay * s, cx + bx * s, cy + by * s)
    if name == "check":
        line(-0.6, 0.05, -0.15, 0.5)
        line(-0.15, 0.5, 0.65, -0.5)
    elif name in ("down", "up", "left", "right"):
        a = {"down": ((-0.55, -0.25), (0, 0.3), (0.55, -0.25)), "up": ((-0.55, 0.25), (0, -0.3), (0.55, 0.25)),
             "left": ((0.25, -0.55), (-0.3, 0), (0.25, 0.55)), "right": ((-0.25, -0.55), (0.3, 0), (-0.25, 0.55))}[name]
        line(*a[0], *a[1])
        line(*a[1], *a[2])
    elif name in ("caret-down", "caret-right", "caret-up", "caret-left"):
        p = {"caret-down": ((-0.5, -0.3), (0.5, -0.3), (0, 0.4)), "caret-up": ((-0.5, 0.3), (0.5, 0.3), (0, -0.4)),
             "caret-right": ((-0.3, -0.5), (-0.3, 0.5), (0.4, 0)), "caret-left": ((0.3, -0.5), (0.3, 0.5), (-0.4, 0))}[name]
        lib.draw.triangle(color, 0, *[v for q in p for v in (cx + q[0] * s, cy + q[1] * s)])
    elif name == "close":
        line(-0.5, -0.5, 0.5, 0.5)
        line(-0.5, 0.5, 0.5, -0.5)
    elif name == "plus":
        line(-0.6, 0, 0.6, 0)
        line(0, -0.6, 0, 0.6)
    elif name == "minus":
        line(-0.6, 0, 0.6, 0)
    elif name == "folder":
        lib.draw.roundedRectangle(color, 0, cx - s * 0.9, cy - s * 0.5, s * 1.8, s * 1.2, 2, 2)
        lib.draw.roundedRectangle(color, 0, cx - s * 0.9, cy - s * 0.7, s * 0.8, s * 0.35, 2, 2)
    elif name == "file":
        lib.draw.roundedRectangle(color, weight if weight < 2 else 1, cx - s * 0.6, cy - s * 0.85, s * 1.2, s * 1.7, 2, 2)
        line(-0.3, -0.1, 0.3, -0.1)
        line(-0.3, 0.3, 0.3, 0.3)
    elif name == "calendar":
        lib.draw.roundedRectangle(color, 1, cx - s * 0.8, cy - s * 0.7, s * 1.6, s * 1.5, 2, 2)
        line(-0.8, -0.2, 0.8, -0.2)
        line(-0.4, -0.95, -0.4, -0.45)
        line(0.4, -0.95, 0.4, -0.45)
    elif name == "clock":
        lib.draw.circle(color, 1, cx, cy, s * 0.85)
        line(0, 0, 0, -0.55)
        line(0, 0, 0.4, 0.2)
    elif name == "search":
        lib.draw.circle(color, 1, cx - s * 0.15, cy - s * 0.15, s * 0.55)
        line(0.25, 0.25, 0.8, 0.8)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ====================================================================== widget base
class Widget:
    focusable = False
    cursor = "default"
    passthrough = False          # True: mouse events fall through to whatever is below
    clip_children = False
    closes_on_outside = False    # popups only

    def __init__(self, x=0, y=0, w=100, h=32, style=None, enabled=True, visible=True, tooltip=None, name=None):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.style = dict(style or {})
        self.enabled, self.visible = enabled, visible
        self.tooltip, self.name = tooltip, name
        self.parent = None
        self.ui = None
        self.children = []
        self.hover = self.pressed = self.focused = False
        self._lv = None

    # ---- tree
    def add(self, *widgets):
        for wd in widgets:
            if wd.parent is not None:
                wd.parent.children.remove(wd)
            wd.parent = self
            self.children.append(wd)
            wd._attach(self.ui)
        return widgets[0] if len(widgets) == 1 else widgets

    def remove(self, widget):
        if widget in self.children:
            self.children.remove(widget)
            widget.parent = None
            widget._attach(None)

    def _attach(self, ui):
        self.ui = ui
        for c in self.children:
            c._attach(ui)

    def content_origin(self):
        return self.ax, self.ay

    @property
    def ax(self):
        return self.x if self.parent is None else self.parent.content_origin()[0] + self.x

    @property
    def ay(self):
        return self.y if self.parent is None else self.parent.content_origin()[1] + self.y

    def rect(self):
        return self.ax, self.ay, self.w, self.h

    def contains(self, px, py):
        return self.ax <= px < self.ax + self.w and self.ay <= py < self.ay + self.h

    def is_inside(self, ancestor):
        w = self
        while w is not None:
            if w is ancestor:
                return True
            w = w.parent
        return False

    def bring_to_front(self):
        if self.parent and self.parent.children[-1] is not self:
            self.parent.children.remove(self)
            self.parent.children.append(self)

    def hit(self, px, py):
        if not self.visible or not self.contains(px, py):
            return None
        if self.clip_children or self.children:
            for c in reversed(self.children):
                r = c.hit(px, py)
                if r is not None:
                    return r
        return None if self.passthrough else self

    # ---- styling
    def _levels(self):
        th = self.ui.theme if self.ui else theme
        key = (th, th.version)
        if self._lv is None or self._lv[0] != key:
            lv = [self.style] + [th.d[c.__name__] for c in type(self).__mro__ if c.__name__ in th.d]
            lv.append(th.d["*"])
            self._lv = (key, [d for d in lv if d is not None])
        return self._lv[1]

    def get(self, key, default=None):
        if not self.enabled:
            states = ("disabled",)
        else:
            states = (("active",) if self.pressed else ()) + (("focus",) if self.focused else ()) + (("hover",) if self.hover else ())
        for d in self._levels():
            for s in states:
                v = d.get(key + "_" + s)
                if v is not None:
                    return v
            v = d.get(key)
            if v is not None:
                return v
        return default

    def plain(self, key, default=None):
        """style lookup ignoring hover/active/focus state"""
        for d in self._levels():
            v = d.get(key)
            if v is not None:
                return v
        return default

    def size_pt(self):
        return self.plain("font_size", 16)

    # ---- text helpers
    def font(self, mono=False):
        return (self.plain("mono_font") or mono_font()) if mono else self.plain("font")

    def text(self, s, x, y, color=None, size=None, ha="left", va="top", mono=False):
        lib.draw.text(color if color is not None else self.get("fg"), s, x, y, size or (self.plain("mono_size", 15) if mono else self.size_pt()),
                      ha, va, self.font(mono))

    def measure(self, s, size=None, mono=False):
        return lib.draw.measureText(s, size or (self.plain("mono_size", 15) if mono else self.size_pt()), self.font(mono))

    def fit(self, s, maxw, size=None, mono=False):
        """shorten s with an ellipsis so it fits in maxw pixels"""
        if maxw <= 0:
            return ""
        if self.measure(s, size, mono)[0] <= maxw:
            return s
        lo, hi = 0, len(s)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.measure(s[:mid] + "…", size, mono)[0] <= maxw:
                lo = mid
            else:
                hi = mid - 1
        return s[:lo] + "…"

    def draw_box(self, x=None, y=None, w=None, h=None, bg="bg", border="border", radius="radius"):
        x = self.ax if x is None else x
        y = self.ay if y is None else y
        w = self.w if w is None else w
        h = self.h if h is None else h
        b = self.get(border)
        if self.focused and self.focusable and self.enabled:
            b = self.get("border_focus")
        box(x, y, w, h, self.get(bg), b, self.plain("border_w", 1), self.plain(radius, 6))

    # ---- lifecycle / drawing
    def update(self, dt):
        pass

    def update_tree(self, dt):
        if not self.visible:
            return
        self.update(dt)
        for c in self.children[:]:
            c.update_tree(dt)

    def draw(self):
        pass

    def draw_over(self):
        pass

    def clip_rect(self):
        return self.ax, self.ay, self.w, self.h

    def draw_tree(self):
        if not self.visible:
            return
        self.draw()
        if self.children:
            if self.clip_children:
                self.ui.push_clip(*self.clip_rect())
            for c in self.children:
                c.draw_tree()
            if self.clip_children:
                self.ui.pop_clip()
        self.draw_over()

    # ---- events (override what you need)
    def mouse_down(self, x, y, button, clicks): pass
    def mouse_up(self, x, y, button): pass
    def mouse_drag(self, x, y): pass
    def mouse_move(self, x, y): pass
    def mouse_enter(self): pass
    def mouse_leave(self): pass
    def click(self, x, y, button): pass
    def wheel(self, delta, x, y): return False
    def text_input(self, s): pass
    def key_down(self, key, mods): return False
    def focus_in(self): pass
    def focus_out(self): pass

    def get_cursor(self, x, y):
        return self.cursor

    def focus(self):
        if self.ui:
            self.ui.set_focus(self)

    def blur(self):
        if self.ui and self.ui.focus is self:
            self.ui.set_focus(None)

    def layout(self):
        pass


# ====================================================================== basic containers / static widgets
class Panel(Widget):
    """Plain container with background and border. Children use coordinates relative to the panel."""

    def __init__(self, x=0, y=0, w=200, h=150, **kw):
        super().__init__(x, y, w, h, **kw)

    def draw(self):
        box(self.ax, self.ay, self.w, self.h, self.plain("panel_bg"), self.plain("panel_border"), self.plain("border_w", 1), self.plain("radius", 6))


class Label(Widget):
    passthrough = True

    def __init__(self, x=0, y=0, w=None, h=None, text="", color=None, size=None, align="left", mono=False, **kw):
        self.text_value, self.color, self.size, self.align, self.mono = text, color, size, align, mono
        super().__init__(x, y, w or 10, h or 10, **kw)
        self._auto = (w is None, h is None)
        self._autosize()

    def set_text(self, s):
        self.text_value = str(s)
        self._autosize()

    def _autosize(self):
        tw, th = self.measure(str(self.text_value), self.size, self.mono)
        if self._auto[0]:
            self.w = tw
        if self._auto[1]:
            self.h = th

    def draw(self):
        ax = {"left": self.ax, "center": self.ax + self.w / 2, "right": self.ax + self.w}[self.align]
        col = self.color if self.color is not None else self.get("fg")
        if not self.enabled:
            col = self.get("fg_disabled")
        self.text(str(self.text_value), ax, self.ay, col, self.size, self.align, "top", self.mono)


class Separator(Widget):
    passthrough = True

    def __init__(self, x=0, y=0, w=100, h=1, vertical=False, **kw):
        super().__init__(x, y, w if not vertical else 1, h if not vertical else w, **kw)

    def draw(self):
        lib.draw.rectangle(self.get("border"), 0, self.ax, self.ay, self.w, self.h)


# ====================================================================== layout helpers
def vstack(widgets, x=0, y=0, w=None, gap=8):
    """place widgets in a column; returns the total height"""
    for wd in widgets:
        wd.x, wd.y = x, y
        if w is not None:
            wd.w = w
        wd.layout()
        y += wd.h + gap
    return max(0, y - gap)


def hstack(widgets, x=0, y=0, h=None, gap=8):
    """place widgets in a row; returns the total width"""
    for wd in widgets:
        wd.x, wd.y = x, y
        if h is not None:
            wd.h = h
        wd.layout()
        x += wd.w + gap
    return max(0, x - gap)


# ====================================================================== UI manager
class UI:
    """Owns the widget tree and routes input. Per frame:  ui.update(dt)  then  ui.draw()."""

    def __init__(self, ui_theme=None):
        self.theme = ui_theme or theme
        self.widgets = []
        self.overlays = []        # popups (dropdown lists, pickers), drawn above everything but modals
        self.modals = []
        self.toasts = []
        self.focus = None
        self.hover = None
        self.captured = None
        self.mouse = (0, 0)
        self.width = self.height = 0
        self._clip = []
        self._last_click = (0, -1, -1, 0)
        self._rep = {}
        self.clipboard = ""
        self._tip_t = 0.0
        self._tip_w = None
        self.time = 0.0

    # ---- tree
    def add(self, *widgets):
        for wd in widgets:
            wd.parent = None
            wd._attach(self)
            self.widgets.append(wd)
        return widgets[0] if len(widgets) == 1 else widgets

    def remove(self, widget):
        if widget in self.widgets:
            self.widgets.remove(widget)
            widget._attach(None)

    # ---- popups, modals, toasts
    def open_popup(self, popup, owner=None):
        if popup in self.overlays:
            return
        popup.parent = None
        popup.owner = owner
        popup._attach(self)
        self.overlays.append(popup)
        popup.opened()

    def close_popup(self, popup):
        if popup in self.overlays:
            self.overlays.remove(popup)
            popup.closed()
            if self.focus is not None and self.focus.is_inside(popup):
                self.set_focus(None)

    def show(self, modal):
        modal._attach(self)
        modal.parent = None
        modal.ui = self
        if modal not in self.modals:
            self.modals.append(modal)
        modal.center()
        modal.opened()

    def close(self, modal):
        if modal in self.modals:
            self.modals.remove(modal)
            modal.closed()

    def toast(self, text, duration=3.0, kind="info"):
        """small notification in the bottom right. kind: info | success | warning | danger"""
        self.toasts.append({"text": str(text), "kind": kind, "t": 0.0, "dur": duration})

    def alert(self, title, message, on_close=None):
        from .containers import Modal
        m = Modal(title=title, w=360, h=170, message=message, buttons=[("OK", on_close, True)])
        self.show(m)
        return m

    def confirm(self, title, message, on_yes=None, on_no=None):
        from .containers import Modal
        m = Modal(title=title, w=380, h=170, message=message,
                  buttons=[("Cancel", on_no, False), ("Confirm", on_yes, True)])
        self.show(m)
        return m

    # ---- focus
    def set_focus(self, w):
        if w is self.focus:
            return
        if self.focus is not None:
            self.focus.focused = False
            self.focus.focus_out()
        self.focus = w
        if w is not None:
            w.focused = True
            w.focus_in()

    def _focusables(self):
        out = []

        def walk(w):
            if w.visible and w.enabled:
                if w.focusable:
                    out.append(w)
                for c in w.children:
                    walk(c)
        roots = [self.modals[-1]] if self.modals else self.widgets
        for r in roots:
            walk(r)
        return out

    # ---- clipping
    def push_clip(self, x, y, w, h):
        r = pygame.Rect(round(x), round(y), max(0, round(w)), max(0, round(h)))
        if self._clip:
            r = r.clip(self._clip[-1])
        self._clip.append(r)
        lib.draw.setClip(r.x, r.y, r.w, r.h)

    def pop_clip(self):
        self._clip.pop()
        if self._clip:
            r = self._clip[-1]
            lib.draw.setClip(r.x, r.y, r.w, r.h)
        else:
            lib.draw.clearClip()

    # ---- hit testing
    def _top_hit(self, x, y):
        if self.modals:
            for o in reversed(self.overlays):
                r = o.hit(x, y)
                if r is not None:
                    return r
            return self.modals[-1].hit(x, y)
        for o in reversed(self.overlays):
            r = o.hit(x, y)
            if r is not None:
                return r
        for w in reversed(self.widgets):
            r = w.hit(x, y)
            if r is not None:
                return r
        return None

    # ---- per-frame
    def update(self, dt):
        self.time += dt
        surf = pygame.display.get_surface()
        if surf:
            self.width, self.height = surf.get_size()
        mx, my = lib.getMousePos()
        moved = (mx, my) != self.mouse
        self.mouse = (mx, my)
        top = self._top_hit(mx, my) if self.captured is None else self.captured
        under = self._top_hit(mx, my)

        # hover bookkeeping
        if under is not self.hover:
            if self.hover is not None:
                self.hover.hover = False
                self.hover.mouse_leave()
            self.hover = under
            if under is not None and under.enabled:
                under.hover = True
                under.mouse_enter()
            self._tip_t, self._tip_w = 0.0, under
        else:
            self._tip_t += dt
        if moved and under is not None and under.enabled:
            under.mouse_move(mx, my)

        # mouse buttons
        for e in lib.getMouse():
            _, x, y, _, _, ix, iy, action, pressed, released, _ = e
            btn = action.lower()
            if pressed:
                self._press(self._top_hit(x, y), x, y, btn)
            if self.captured is not None and not released:
                self.captured.mouse_drag(x, y)
            if released:
                self._release(x, y, btn)

        # wheel
        sc = lib.getScroll()
        if sc and under is not None:
            w = under
            while w is not None:
                if w.enabled and w.wheel(sc, mx, my):
                    break
                w = w.parent

        # text + keys
        if self.focus is not None and self.focus.enabled:
            t = lib.getText()
            if t:
                self.focus.text_input(t)
        self._keys(dt)

        for w in self.widgets:
            w.update_tree(dt)
        for o in self.overlays[:]:
            o.update_tree(dt)
        for m in self.modals:
            m.update_tree(dt)
        for t in self.toasts[:]:
            t["t"] += dt
            if t["t"] > t["dur"] + 0.4:
                self.toasts.remove(t)

        lib.window.setCursor((under.get_cursor(mx, my) if under is not None and under.enabled else "default"))

    def _press(self, target, x, y, button):
        if self.modals and (target is None or not (target.is_inside(self.modals[-1]) or any(target.is_inside(o) for o in self.overlays))):
            target = None
        for o in self.overlays[:]:
            if o.closes_on_outside and (target is None or not target.is_inside(o)) and (target is None or o.owner is None or not target.is_inside(o.owner)):
                self.close_popup(o)
        clicks = 1
        t0, lx, ly, n = self._last_click
        if self.time - t0 < 0.4 and abs(x - lx) < 5 and abs(y - ly) < 5:
            clicks = n + 1
        self._last_click = (self.time, x, y, clicks)
        w = target
        while w is not None and not w.focusable:
            w = w.parent
        if w is not None and not w.enabled:
            w = None
        self.set_focus(w)
        self.captured = target
        if target is not None and target.enabled:
            target.pressed = True
            target.mouse_down(x, y, button, clicks)

    def _release(self, x, y, button):
        c = self.captured
        self.captured = None
        if c is None:
            return
        c.pressed = False
        if not c.enabled:
            return
        c.mouse_up(x, y, button)
        if self._top_hit(x, y) is c:
            c.click(x, y, button)

    def _keys(self, dt):
        mods = Mods(lib.keyDown("Shift") is not None or lib.keyDown("RightShift") is not None,
                    lib.keyDown("Ctrl") is not None or lib.keyDown("RightCtrl") is not None,
                    lib.keyDown("Alt") is not None or lib.keyDown("RightAlt") is not None)
        for _, key, pressed, released, dur in lib.getKeys():
            if key in ("Shift", "RightShift", "Ctrl", "RightCtrl", "Alt", "RightAlt", "Super", "RightSuper"):
                continue
            fire = False
            if pressed:
                fire = True
                self._rep[key] = 0.45
            elif not released and dur >= self._rep.get(key, 99):
                fire = True
                self._rep[key] = dur + 0.035
            if not fire:
                continue
            handled = False
            if self.focus is not None and self.focus.enabled:
                handled = self.focus.key_down(key, mods)
            if not handled:
                if key == "Tab" and pressed:
                    f = self._focusables()
                    if f:
                        i = f.index(self.focus) if self.focus in f else -1
                        self.set_focus(f[(i + (-1 if mods.shift else 1)) % len(f)])
                elif key == "Escape" and pressed:
                    if self.overlays:
                        self.close_popup(self.overlays[-1])
                    elif self.modals and self.modals[-1].closable:
                        self.close(self.modals[-1])

    def draw(self):
        for w in self.widgets:
            w.draw_tree()
        for o in self.overlays:
            o.draw_tree()
        if self.modals:
            lib.draw.rectangle(self.theme.d["*"]["overlay"], 0, 0, 0, self.width, self.height)
            for m in self.modals:
                m.draw_tree()
                for o in self.overlays:
                    if o.owner is not None and o.owner.is_inside(m):
                        o.draw_tree()
        self._draw_toasts()
        self._draw_tooltip()

    def _draw_toasts(self):
        y = self.height - 16
        base = self.theme.d["*"]
        size = base["font_size"]
        for t in reversed(self.toasts):
            tw = lib.draw.measureText(t["text"], size, base["font"])[0]
            w, h = tw + 44, size + 22
            k = min(1, t["t"] / 0.25)
            fade = 1 - max(0, (t["t"] - t["dur"]) / 0.4)
            ease = 1 - (1 - k) ** 3
            x = self.width - 16 - w + (1 - ease) * 40
            y -= h
            col = base.get(t["kind"], base["info"])
            a = max(0.0, min(1.0, fade * ease))
            shadow(x, y, w, h, 8, 8)
            box(x, y, w, h, alpha(base["popup_bg"], a), alpha(base["popup_border"], a), 1, 8)
            lib.draw.roundedRectangle(alpha(col, a), 0, x, y, 5, h, 3, 3)
            lib.draw.text(alpha(base["fg"], a), t["text"], x + 22, y + h / 2, size, "left", "middle", base["font"])
            y -= 8

    def _draw_tooltip(self):
        w = self._tip_w
        if w is None or not w.tooltip or self._tip_t < 0.6 or self.captured is not None:
            return
        base = self.theme.d["*"]
        size = base["font_size"] - 2
        tw, th = lib.draw.measureText(w.tooltip, size, base["font"])
        x = min(self.mouse[0] + 14, self.width - tw - 14)
        y = min(self.mouse[1] + 20, self.height - th - 14)
        box(x, y, tw + 14, th + 10, base["popup_bg"], base["popup_border"], 1, 5)
        lib.draw.text(base["fg"], w.tooltip, x + 7, y + 5, size, "left", "top", base["font"])


# ====================================================================== popup base (dropdown lists, pickers)
class Popup(Widget):
    """A widget shown above everything. ui.open_popup(p, owner) / ui.close_popup(p)."""
    closes_on_outside = True

    def __init__(self, x=0, y=0, w=200, h=200, **kw):
        super().__init__(x, y, w, h, **kw)
        self.owner = None

    def opened(self): pass
    def closed(self): pass

    def place_below(self, anchor, gap=2):
        """position under the anchor widget (above it if there's no room), kept on screen"""
        x, y = anchor.ax, anchor.ay + anchor.h + gap
        if y + self.h > self.ui.height and anchor.ay - self.h - gap > 0:
            y = anchor.ay - self.h - gap
        self.x = clamp(x, 0, max(0, self.ui.width - self.w))
        self.y = clamp(y, 0, max(0, self.ui.height - self.h))

    def draw(self):
        shadow(self.ax, self.ay, self.w, self.h, 8, 10, self.plain("shadow"))
        box(self.ax, self.ay, self.w, self.h, self.plain("popup_bg"), self.plain("popup_border"), 1, self.plain("radius", 6))
