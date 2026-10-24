"""Pickers: Calendar, TimeSelector, DatePicker, TimePicker, DateTimePicker, ColorPanel, ColorPicker."""
import calendar as _cal
import datetime
import math

import lib

from .core import Widget, Popup, box, icon, clamp, lerp, alpha, mix
from .basic import Button
from .text import TextBox

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


class _PopupBox(Popup):
    """popup that just hosts child widgets"""

    def __init__(self, w, h, **kw):
        super().__init__(0, 0, w, h, **kw)


class _PopupField(Widget):
    focusable = True
    cursor = "pointer"
    icon_name = "down"
    popup_w, popup_h = 260, 260

    def __init__(self, x=0, y=0, w=200, h=None, on_change=None, placeholder="", **kw):
        super().__init__(x, y, w, h or 34, **kw)
        if h is None:
            self.h = self.size_pt() + 16
        self.on_change, self.placeholder = on_change, placeholder
        self.popup = None

    # subclasses implement: field_text(), build_popup(popup)
    def field_text(self):
        return ""

    def build_popup(self, popup):
        pass

    @property
    def is_open(self):
        return self.popup is not None and self.ui is not None and self.popup in self.ui.overlays

    def open(self):
        if self.is_open:
            return
        self.popup = _PopupBox(self.popup_w, self.popup_h)
        self.build_popup(self.popup)
        self.ui.open_popup(self.popup, self)
        self.popup.place_below(self)

    def close(self):
        if self.is_open:
            self.ui.close_popup(self.popup)

    def changed(self, v):
        if self.on_change:
            self.on_change(v)

    def click(self, x, y, button):
        if button == "left":
            self.close() if self.is_open else self.open()

    def key_down(self, key, mods):
        if key in ("Enter", "Space"):
            self.close() if self.is_open else self.open()
            return True
        return False

    def draw_swatch(self, x, y, w, h):
        pass

    def draw(self):
        self.draw_box()
        t = self.field_text()
        col = self.get("fg") if t else self.get("fg_muted")
        if not self.enabled:
            col = self.get("fg_disabled")
        self.draw_swatch(self.ax + 8, self.ay + 7, 26, self.h - 14)
        self.text(self.fit(t or self.placeholder, self.w - 52 - self.swatch_w()), self.ax + 12 + self.swatch_w(), self.ay + self.h / 2, col, None, "left", "middle")
        icon(self.icon_name, self.ax + self.w - 18, self.ay + self.h / 2, 14, self.get("fg_muted"), 1)

    def swatch_w(self):
        return 0


# ====================================================================== calendar
class Calendar(Widget):
    """Month grid. gui.Calendar(x, y, w, h, value=date, on_select=fn(date), week_starts=0)  (0 = Monday, 6 = Sunday)
    .value is a datetime.date or None."""
    focusable = True

    def __init__(self, x=0, y=0, w=252, h=250, value=None, on_select=None, week_starts=0, **kw):
        super().__init__(x, y, w, h, **kw)
        self.value, self.on_select, self.week_starts = value, on_select, week_starts
        today = value or datetime.date.today()
        self.year, self.month = today.year, today.month
        self._cell = None

    def _grid(self):
        first = datetime.date(self.year, self.month, 1)
        start = first - datetime.timedelta(days=(first.weekday() - self.week_starts) % 7)
        return [start + datetime.timedelta(days=i) for i in range(42)]

    def shift_month(self, d):
        m = self.month - 1 + d
        self.year += m // 12
        self.month = m % 12 + 1

    def select(self, d, notify=True):
        self.value = d
        self.year, self.month = d.year, d.month
        if notify and self.on_select:
            self.on_select(d)

    def _geom(self):
        head = 36
        cw = self.w / 7
        ch = (self.h - head - 26) / 6
        return head, cw, ch

    def mouse_down(self, x, y, button, clicks):
        head, cw, ch = self._geom()
        rx, ry = x - self.ax, y - self.ay
        if ry < head:
            if rx < 40:
                self.shift_month(-1)
            elif rx > self.w - 40:
                self.shift_month(1)
            return
        r, c = int((ry - head - 26) // ch), int(rx // cw)
        if ry >= head + 26 and 0 <= r < 6 and 0 <= c < 7:
            self.select(self._grid()[r * 7 + c])

    def mouse_move(self, x, y):
        head, cw, ch = self._geom()
        rx, ry = x - self.ax, y - self.ay
        r, c = int((ry - head - 26) // ch), int(rx // cw)
        self._cell = r * 7 + c if ry >= head + 26 and 0 <= r < 6 and 0 <= c < 7 else None

    def mouse_leave(self):
        self._cell = None

    def key_down(self, key, mods):
        d = {"Left": -1, "Right": 1, "Up": -7, "Down": 7}.get(key)
        if key in ("PageUp", "PageDown"):
            self.shift_month(-1 if key == "PageUp" else 1)
            return True
        if d is None:
            return False
        self.select((self.value or datetime.date.today()) + datetime.timedelta(days=d))
        return True

    def draw(self):
        self.draw_box(bg="popup_bg" if self.parent is not None and isinstance(self.parent, Popup) else "bg", border="border")
        head, cw, ch = self._geom()
        for sx, name in ((self.ax + 20, "left"), (self.ax + self.w - 20, "right")):
            icon(name, sx, self.ay + head / 2, 12, self.get("fg_muted"))
        self.text(f"{MONTHS[self.month - 1]} {self.year}", self.ax + self.w / 2, self.ay + head / 2, self.get("fg"), self.size_pt() + 1, "center", "middle")
        for c in range(7):
            self.text(WEEKDAYS[(self.week_starts + c) % 7], self.ax + cw * (c + 0.5), self.ay + head + 12, self.get("fg_muted"), self.size_pt() - 3, "center", "middle")
        today = datetime.date.today()
        for i, d in enumerate(self._grid()):
            r, c = divmod(i, 7)
            cx, cy = self.ax + cw * (c + 0.5), self.ay + head + 26 + ch * (r + 0.5)
            rad = min(cw, ch) / 2 - 2
            inm = d.month == self.month
            if d == self.value:
                lib.draw.circle(self.get("accent"), 0, cx, cy, rad)
            elif self._cell == i:
                lib.draw.circle(self.plain("row_hover"), 0, cx, cy, rad)
            if d == today and d != self.value:
                lib.draw.circle(self.get("accent"), 1, cx, cy, rad)
            col = self.get("accent_fg") if d == self.value else (self.get("fg") if inm else self.get("fg_disabled"))
            self.text(str(d.day), cx, cy, col, self.size_pt() - 1, "center", "middle")


class TimeSelector(Widget):
    """Spin columns for hours / minutes (/ seconds). gui.TimeSelector(x, y, w, h, value=time, seconds=False, use_24h=True, on_change=fn(time))"""
    focusable = True

    def __init__(self, x=0, y=0, w=210, h=130, value=None, seconds=False, use_24h=True, minute_step=1, on_change=None, **kw):
        super().__init__(x, y, w, h, **kw)
        self.value = value or datetime.time(12, 0)
        self.seconds, self.use_24h, self.minute_step, self.on_change = seconds, use_24h, minute_step, on_change
        self._hot = None

    def _cols(self):
        names = ["h", "m"] + (["s"] if self.seconds else []) + ([] if self.use_24h else ["ap"])
        cw = self.w / len(names)
        return [(n, self.ax + i * cw, cw) for i, n in enumerate(names)]

    def _adjust(self, name, d):
        t = self.value
        h, m, s = t.hour, t.minute, t.second
        if name == "h":
            h = (h + d) % 24
        elif name == "m":
            m = (m + d * self.minute_step) % 60
        elif name == "s":
            s = (s + d) % 60
        elif name == "ap":
            h = (h + 12) % 24
        self.value = datetime.time(h, m, s)
        if self.on_change:
            self.on_change(self.value)

    def _at(self, x, y):
        for n, cx, cw in self._cols():
            if cx <= x < cx + cw:
                zone = "up" if y < self.ay + self.h * 0.32 else "down" if y > self.ay + self.h * 0.68 else "mid"
                return n, zone
        return None, None

    def mouse_down(self, x, y, button, clicks):
        n, z = self._at(x, y)
        if n and z in ("up", "down"):
            self._adjust(n, 1 if z == "up" else -1)
        elif n and z == "mid" and n == "ap":
            self._adjust("ap", 1)

    def mouse_move(self, x, y):
        self._hot = self._at(x, y)

    def mouse_leave(self):
        self._hot = None

    def wheel(self, delta, x, y):
        n, z = self._at(x, y)
        if n:
            self._adjust(n, 1 if delta > 0 else -1)
            return True
        return False

    def key_down(self, key, mods):
        if key in ("Up", "Down"):
            self._adjust("m", 1 if key == "Up" else -1)
            return True
        return False

    def draw(self):
        self.draw_box()
        t = self.value
        h = t.hour if self.use_24h else (t.hour % 12 or 12)
        vals = {"h": f"{h:02d}", "m": f"{t.minute:02d}", "s": f"{t.second:02d}", "ap": "PM" if t.hour >= 12 else "AM"}
        for i, (n, cx, cw) in enumerate(self._cols()):
            mid = cx + cw / 2
            for zone, name, yy in (("up", "up", self.ay + self.h * 0.18), ("down", "down", self.ay + self.h * 0.82)):
                hot = self.hover and self._hot == (n, zone)
                if n != "ap":
                    icon(name, mid, yy, 14, self.get("accent") if hot else self.get("fg_muted"))
            self.text(vals[n], mid, self.ay + self.h / 2, self.get("fg"), self.size_pt() + 10, "center", "middle")
            if i < len(self._cols()) - 1 and n != "ap" and self._cols()[i + 1][0] != "ap":
                self.text(":", cx + cw, self.ay + self.h / 2 - 1, self.get("fg_muted"), self.size_pt() + 8, "center", "middle")


# ====================================================================== fields
class DatePicker(_PopupField):
    """Date field that opens a calendar. gui.DatePicker(x, y, w, h, value=datetime.date(...), fmt="%Y-%m-%d", on_change=fn(date))"""
    icon_name = "calendar"
    popup_w, popup_h = 268, 266

    def __init__(self, x=0, y=0, w=200, h=None, value=None, fmt="%Y-%m-%d", placeholder="Pick a date", **kw):
        super().__init__(x, y, w, h, placeholder=placeholder, **kw)
        self.value, self.fmt = value, fmt

    def field_text(self):
        return self.value.strftime(self.fmt) if self.value else ""

    def build_popup(self, p):
        cal = Calendar(8, 8, 252, 250, value=self.value, on_select=self._pick)
        p.add(cal)

    def _pick(self, d):
        self.value = d
        self.changed(d)
        self.close()


class TimePicker(_PopupField):
    """Time field with a spinner popup. gui.TimePicker(x, y, w, h, value=datetime.time(9, 30), seconds=False, use_24h=True)"""
    icon_name = "clock"
    popup_w, popup_h = 226, 170

    def __init__(self, x=0, y=0, w=160, h=None, value=None, seconds=False, use_24h=True, placeholder="Pick a time", **kw):
        super().__init__(x, y, w, h, placeholder=placeholder, **kw)
        self.value, self.seconds, self.use_24h = value, seconds, use_24h

    def field_text(self):
        if not self.value:
            return ""
        return self.value.strftime(("%H:%M" if self.use_24h else "%I:%M") + (":%S" if self.seconds else "") + ("" if self.use_24h else " %p"))

    def build_popup(self, p):
        sel = TimeSelector(8, 8, 210, 112, value=self.value or datetime.time(12, 0), seconds=self.seconds, use_24h=self.use_24h,
                           on_change=self._pick)
        p.add(sel)
        p.add(Button(118, 128, 100, 32, text="Done", primary=True, on_click=lambda b: self.close()))
        p.add(Button(8, 128, 100, 32, text="Now", on_click=lambda b: (sel.__setattr__("value", datetime.datetime.now().time().replace(microsecond=0)), self._pick(sel.value))))

    def _pick(self, t):
        self.value = t
        self.changed(t)


class DateTimePicker(_PopupField):
    """Date and time in one popup. value is a datetime.datetime.
    gui.DateTimePicker(x, y, w, h, value=datetime.datetime.now(), fmt="%Y-%m-%d %H:%M", on_change=fn(datetime))"""
    icon_name = "calendar"
    popup_w, popup_h = 268, 420

    def __init__(self, x=0, y=0, w=240, h=None, value=None, fmt="%Y-%m-%d %H:%M", seconds=False, placeholder="Pick date and time", **kw):
        super().__init__(x, y, w, h, placeholder=placeholder, **kw)
        self.value, self.fmt, self.seconds = value, fmt, seconds

    def field_text(self):
        return self.value.strftime(self.fmt) if self.value else ""

    def build_popup(self, p):
        v = self.value or datetime.datetime.now().replace(second=0, microsecond=0)
        self._tmp = v
        cal = Calendar(8, 8, 252, 250, value=v.date(), on_select=self._date)
        sel = TimeSelector(8, 266, 252, 100, value=v.time(), seconds=self.seconds, on_change=self._time)
        p.add(cal, sel)
        p.add(Button(160, 376, 100, 34, text="Done", primary=True, on_click=lambda b: self.close()))
        p.add(Button(8, 376, 100, 34, text="Now", on_click=lambda b: self._now(cal, sel)))

    def _now(self, cal, sel):
        n = datetime.datetime.now().replace(second=0, microsecond=0)
        cal.select(n.date(), notify=False)
        sel.value = n.time()
        self._tmp = n
        self._commit()

    def _date(self, d):
        self._tmp = datetime.datetime.combine(d, self._tmp.time())
        self._commit()

    def _time(self, t):
        self._tmp = datetime.datetime.combine(self._tmp.date(), t)
        self._commit()

    def _commit(self):
        self.value = self._tmp
        self.changed(self.value)


# ====================================================================== color
def _hsv_to_rgb(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


def _rgb_to_hsv(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h / 6, (0 if mx == 0 else d / mx), mx


def _checker(x, y, w, h, size=6):
    lib.draw.rectangle(0xFFFFFF, 0, x, y, w, h)
    for r in range(int(math.ceil(h / size))):
        for c in range(int(math.ceil(w / size))):
            if (r + c) % 2:
                lib.draw.rectangle(0xC8C8C8, 0, x + c * size, y + r * size, min(size, w - c * size), min(size, h - r * size))


class ColorPanel(Widget):
    """Saturation/value square, hue and alpha sliders and a hex box. .value is [r, g, b, a] floats 0-1
    (usable directly as a lib color), .hex is "#RRGGBB" / "#RRGGBBAA". gui.ColorPanel(x, y, w, h, value=[1, 0, 0, 1], on_change=fn(value))"""

    def __init__(self, x=0, y=0, w=240, h=250, value=(0.3, 0.55, 1.0, 1.0), on_change=None, alpha_slider=True, **kw):
        super().__init__(x, y, w, h, **kw)
        self.on_change, self.alpha_slider = on_change, alpha_slider
        self.hue = self.sat = self.val = 0.0
        self.a = 1.0
        self._mode = None
        self.hex_box = TextBox(0, 0, 100, 30, max_length=9, on_submit=self._hex_in)
        self.hex_box.on_blur = lambda t: self._hex_in(t.value)
        self.add(self.hex_box)
        self.set_value(value, notify=False)

    # ---- value
    @property
    def value(self):
        r, g, b = _hsv_to_rgb(self.hue, self.sat, self.val)
        return [r, g, b, self.a]

    @property
    def hex(self):
        r, g, b, a = lib._rgba(self.value)
        return f"#{r:02X}{g:02X}{b:02X}" + (f"{a:02X}" if a < 255 else "")

    def set_value(self, v, notify=True):
        r, g, b, a = lib._rgba(v)
        h, s, vv = _rgb_to_hsv(r / 255, g / 255, b / 255)
        if s > 0 and vv > 0:
            self.hue = h
        self.sat, self.val, self.a = s, vv, a / 255
        self.hex_box.set_text(self.hex, notify=False)
        if notify:
            self._fire()

    def _fire(self):
        self.hex_box.set_text(self.hex, notify=False)
        if self.on_change:
            self.on_change(self.value)

    def _hex_in(self, text):
        try:
            self.set_value(text.strip())
        except (ValueError, TypeError):
            self.hex_box.set_text(self.hex, notify=False)

    # ---- geometry
    def _sv(self):
        return self.ax + 8, self.ay + 8, self.w - 16, self.h - 8 - 8 - 22 - (22 if self.alpha_slider else 0) - 42

    def _hue_bar(self):
        x, y, w, h = self._sv()
        return x, y + h + 10, w, 14

    def _alpha_bar(self):
        x, y, w, h = self._hue_bar()
        return x, y + 22, w, 14

    def update(self, dt):
        x, y, w, h = self._alpha_bar() if self.alpha_slider else self._hue_bar()
        self.hex_box.x, self.hex_box.y = 8 + 36, self.h - 8 - 30
        self.hex_box.w, self.hex_box.h = self.w - 16 - 36, 30

    def _drag(self, x, y):
        sx, sy, sw, sh = self._sv()
        if self._mode == "sv":
            self.sat = clamp((x - sx) / sw, 0, 1)
            self.val = 1 - clamp((y - sy) / sh, 0, 1)
        elif self._mode == "hue":
            self.hue = clamp((x - sx) / sw, 0, 0.9999)
        elif self._mode == "alpha":
            self.a = clamp((x - sx) / sw, 0, 1)
        self._fire()

    def mouse_down(self, x, y, button, clicks):
        sx, sy, sw, sh = self._sv()
        hx, hy, hw, hh = self._hue_bar()
        ax_, ay_, aw, ah = self._alpha_bar()
        if sx <= x <= sx + sw and sy <= y <= sy + sh:
            self._mode = "sv"
        elif hy - 3 <= y <= hy + hh + 3:
            self._mode = "hue"
        elif self.alpha_slider and ay_ - 3 <= y <= ay_ + ah + 3:
            self._mode = "alpha"
        else:
            self._mode = None
        if self._mode:
            self._drag(x, y)

    def mouse_drag(self, x, y):
        if self._mode:
            self._drag(x, y)

    def mouse_up(self, x, y, button):
        self._mode = None

    def get_cursor(self, x, y):
        sx, sy, sw, sh = self._sv()
        return "crosshair" if sx <= x <= sx + sw and sy <= y <= sy + sh else "pointer" if y < self._alpha_bar()[1] + 20 else "default"

    def draw(self):
        box(self.ax, self.ay, self.w, self.h, self.plain("popup_bg") if isinstance(self.parent, Popup) else self.plain("panel_bg"),
            self.plain("panel_border"), 1, self.plain("radius", 6))
        sx, sy, sw, sh = self._sv()
        base = _hsv_to_rgb(self.hue, 1, 1)
        lib.draw.gradient(0xFFFFFF, base, sx, sy, sw, sh, 0)
        lib.draw.gradient("#00000000", "#000000FF", sx, sy, sw, sh, math.pi / 2)
        lib.draw.rectangle(self.get("border"), 1, sx, sy, sw, sh)
        mx, my = sx + self.sat * sw, sy + (1 - self.val) * sh
        lib.draw.circle(0x000000, 2, mx, my, 7)
        lib.draw.circle(0xFFFFFF, 2, mx, my, 6)
        hx, hy, hw, hh = self._hue_bar()
        seg = hw / 6
        for i in range(6):
            lib.draw.gradient(_hsv_to_rgb(i / 6, 1, 1), _hsv_to_rgb((i + 1) / 6 % 1 if i < 5 else 0, 1, 1), hx + i * seg, hy, seg + 1, hh, 0)
        kx = hx + self.hue * hw
        lib.draw.roundedRectangle(0xFFFFFF, 0, kx - 3, hy - 3, 6, hh + 6, 3, 3)
        lib.draw.roundedRectangle(0x000000, 1, kx - 3, hy - 3, 6, hh + 6, 3, 3)
        if self.alpha_slider:
            x2, y2, w2, h2 = self._alpha_bar()
            _checker(x2, y2, w2, h2, 7)
            r, g, b = _hsv_to_rgb(self.hue, self.sat, self.val)
            lib.draw.gradient([r, g, b, 0.0], [r, g, b, 1.0], x2, y2, w2, h2, 0)
            kx = x2 + self.a * w2
            lib.draw.roundedRectangle(0xFFFFFF, 0, kx - 3, y2 - 3, 6, h2 + 6, 3, 3)
            lib.draw.roundedRectangle(0x000000, 1, kx - 3, y2 - 3, 6, h2 + 6, 3, 3)
        py = self.ay + self.h - 8 - 30
        _checker(self.ax + 8, py, 30, 30, 6)
        lib.draw.rectangle(self.value, 0, self.ax + 8, py, 30, 30)
        lib.draw.rectangle(self.get("border"), 1, self.ax + 8, py, 30, 30)


class ColorPicker(_PopupField):
    """Color field with a popup ColorPanel. .value is [r, g, b, a] (floats 0-1), .hex the string.
    gui.ColorPicker(x, y, w, h, value=[1, 0.3, 0.2, 1], on_change=fn(value))"""
    popup_w, popup_h = 256, 266

    def __init__(self, x=0, y=0, w=180, h=None, value=(0.3, 0.55, 1.0, 1.0), alpha_slider=True, **kw):
        super().__init__(x, y, w, h, **kw)
        self.value = list(lib._rgba(value))
        self.value = [c / 255 for c in self.value]
        self.alpha_slider = alpha_slider

    @property
    def hex(self):
        r, g, b, a = lib._rgba(self.value)
        return f"#{r:02X}{g:02X}{b:02X}" + (f"{a:02X}" if a < 255 else "")

    def field_text(self):
        return self.hex

    def swatch_w(self):
        return 30

    def draw_swatch(self, x, y, w, h):
        _checker(x, y, w, h, 6)
        lib.draw.rectangle(self.value, 0, x, y, w, h)
        lib.draw.rectangle(self.get("border"), 1, x, y, w, h)

    def build_popup(self, p):
        panel = ColorPanel(0, 0, self.popup_w, self.popup_h, value=self.value, alpha_slider=self.alpha_slider, on_change=self._pick)
        p.add(panel)

    def _pick(self, v):
        self.value = list(v)
        self.changed(self.value)
