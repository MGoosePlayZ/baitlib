"""Containers: ScrollView, Accordion, Splitter, Carousel, Modal, Resizable."""
import math

import lib

from .core import Widget, Panel, box, shadow, icon, clamp, lerp, alpha
from .basic import Button


def _wrap(widget, text, maxw, size=None):
    out = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            t = (line + " " + word).strip()
            if widget.measure(t, size)[0] <= maxw or not line:
                line = t
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


class ScrollView(Widget):
    """Vertical scrolling container. Add children at any y; content height is measured automatically.
    Mouse wheel scrolls, the bar can be dragged. .scroll_y is in pixels."""
    clip_children = True

    def __init__(self, x=0, y=0, w=240, h=200, border=True, **kw):
        super().__init__(x, y, w, h, **kw)
        self.scroll_y = 0.0
        self.border = border
        self.content_h = 0.0
        self._drag = None

    def content_origin(self):
        return self.ax, self.ay - self.scroll_y

    def measure_content(self):
        return max([c.y + c.h for c in self.children if c.visible] + [0]) + 8

    def update(self, dt):
        self.content_h = self.measure_content()
        self.scroll_y = clamp(self.scroll_y, 0, max(0, self.content_h - self.h))

    def wheel(self, delta, x, y):
        if self.content_h <= self.h:
            return False
        self.scroll_y = clamp(self.scroll_y - delta * 40, 0, self.content_h - self.h)
        return True

    def _bar(self):
        th = max(28, self.h * self.h / self.content_h)
        ty = self.ay + (self.h - th) * (self.scroll_y / max(1, self.content_h - self.h))
        return self.ax + self.w - 9, ty, 7, th

    def hit(self, px, py):
        if self.visible and self.content_h > self.h and self.contains(px, py):
            bx, by, bw, bh = self._bar()
            if bx - 3 <= px <= bx + bw + 3:
                return self
        return super().hit(px, py)

    def mouse_down(self, x, y, button, clicks):
        if self.content_h > self.h:
            bx, by, bw, bh = self._bar()
            if bx - 3 <= x <= bx + bw + 3:
                self._drag = y - by if by <= y <= by + bh else bh / 2

    def mouse_drag(self, x, y):
        if self._drag is not None and self.content_h > self.h:
            th = self._bar()[3]
            f = (y - self.ay - self._drag) / max(1, self.h - th)
            self.scroll_y = clamp(f, 0, 1) * (self.content_h - self.h)

    def mouse_up(self, x, y, button):
        self._drag = None

    def draw(self):
        if self.border:
            box(self.ax, self.ay, self.w, self.h, self.plain("panel_bg"), self.plain("panel_border"), 1, self.plain("radius", 6))

    def draw_over(self):
        if self.content_h > self.h:
            bx, by, bw, bh = self._bar()
            lib.draw.roundedRectangle(self.get("border_hover") if self.pressed else self.get("track"), 0, bx, by, bw, bh, 3, 3)


class Section(Widget):
    """One accordion section. Add widgets with section.add(...), positions are relative to the body."""

    def __init__(self, title="", open=False, height=None, **kw):
        super().__init__(0, 0, 200, 30, **kw)
        self.title, self.open, self.body_h = title, open, height
        self._t = 1.0 if open else 0.0
        self.on_toggle = None

    @property
    def header_h(self):
        return self.size_pt() + 18

    def content_origin(self):
        return self.ax, self.ay + self.header_h

    def natural_body(self):
        return self.body_h if self.body_h is not None else max([c.y + c.h for c in self.children] + [20]) + 10

    def update(self, dt):
        self._t = lerp(self._t, 1.0 if self.open else 0.0, min(1.0, dt * 14))
        if abs(self._t - (1.0 if self.open else 0.0)) < 0.002:
            self._t = 1.0 if self.open else 0.0
        self.h = self.header_h + self.natural_body() * self._t

    def hit(self, px, py):
        if not self.visible or not self.contains(px, py):
            return None
        if py < self.ay + self.header_h:
            return self
        for c in reversed(self.children):
            r = c.hit(px, py)
            if r is not None:
                return r
        return self

    def mouse_down(self, x, y, button, clicks):
        if y < self.ay + self.header_h and button == "left":
            self.open = not self.open
            if self.on_toggle:
                self.on_toggle(self)

    def get_cursor(self, x, y):
        return "pointer" if y < self.ay + self.header_h else "default"

    def draw_tree(self):
        if not self.visible:
            return
        hh = self.header_h
        r = self.plain("radius", 6)
        open_amt = self._t
        hover = self.hover and self.ui.mouse[1] < self.ay + hh
        box(self.ax, self.ay, self.w, self.h, self.plain("panel_bg"), self.plain("panel_border"), 1, r)
        box(self.ax, self.ay, self.w, hh, self.get("bg_hover") if hover else self.get("bg"), self.plain("panel_border"), 1, r)
        icon("down" if self.open else "right", self.ax + 18, self.ay + hh / 2, 10, self.get("fg"))
        self.text(self.title, self.ax + 34, self.ay + hh / 2, self.get("fg"), None, "left", "middle")
        if self.h > hh + 1:
            self.ui.push_clip(self.ax + 1, self.ay + hh, self.w - 2, self.h - hh - 1)
            for c in self.children:
                c.draw_tree()
            self.ui.pop_clip()


class Accordion(Widget):
    """Stack of collapsible sections.
    acc = gui.Accordion(x, y, w, exclusive=False); s = acc.add_section("Title", open=True, height=120); s.add(widget)"""
    passthrough = False

    def __init__(self, x=0, y=0, w=300, h=0, exclusive=False, gap=6, **kw):
        super().__init__(x, y, w, h, **kw)
        self.exclusive, self.gap = exclusive, gap

    def add_section(self, title, children=(), open=False, height=None):
        s = Section(title, open, height)
        s.on_toggle = self._toggled
        self.add(s)
        for c in children:
            s.add(c)
        return s

    @property
    def sections(self):
        return self.children

    def _toggled(self, s):
        if self.exclusive and s.open:
            for o in self.children:
                if o is not s:
                    o.open = False

    def update(self, dt):
        y = 0
        for s in self.children:
            s.x, s.y, s.w = 0, y, self.w
            y += s.h + self.gap
        self.h = max(0, y - self.gap)

    def hit(self, px, py):
        r = super().hit(px, py)
        return None if r is self else r

    def draw(self):
        pass


class Splitter(Widget):
    """Two panes with a draggable divider. gui.Splitter(x, y, w, h, first=widget, second=widget, vertical=False, ratio=0.5)
    vertical=False: panes side by side. vertical=True: stacked."""

    def __init__(self, x=0, y=0, w=400, h=240, first=None, second=None, vertical=False, ratio=0.5, min_size=60,
                 divider=8, on_resize=None, **kw):
        super().__init__(x, y, w, h, **kw)
        self.vertical, self.ratio, self.min_size, self.divider, self.on_resize = vertical, ratio, min_size, divider, on_resize
        self.first, self.second = first, second
        for p in (first, second):
            if p is not None:
                self.add(p)
        self.layout()

    def _split(self):
        total = (self.h if self.vertical else self.w) - self.divider
        a = clamp(total * self.ratio, self.min_size, max(self.min_size, total - self.min_size))
        return a, total - a

    def layout(self):
        a, b = self._split()
        if self.vertical:
            rects = [(0, 0, self.w, a), (0, a + self.divider, self.w, b)]
        else:
            rects = [(0, 0, a, self.h), (a + self.divider, 0, b, self.h)]
        for p, (x, y, w, h) in zip((self.first, self.second), rects):
            if p is not None:
                p.x, p.y, p.w, p.h = x, y, w, h
                p.layout()

    def update(self, dt):
        self.layout()

    def _div(self):
        a, _ = self._split()
        return (self.ax, self.ay + a, self.w, self.divider) if self.vertical else (self.ax + a, self.ay, self.divider, self.h)

    def hit(self, px, py):
        if not self.visible or not self.contains(px, py):
            return None
        dx, dy, dw, dh = self._div()
        if dx <= px < dx + dw and dy <= py < dy + dh:
            return self
        return super().hit(px, py) or self

    def get_cursor(self, x, y):
        dx, dy, dw, dh = self._div()
        return ("ns-resize" if self.vertical else "ew-resize") if dx <= x < dx + dw and dy <= y < dy + dh else "default"

    def mouse_down(self, x, y, button, clicks):
        self._grab = True

    def mouse_drag(self, x, y):
        total = (self.h if self.vertical else self.w) - self.divider
        pos = (y - self.ay if self.vertical else x - self.ax) - self.divider / 2
        self.ratio = clamp(pos / max(1, total), 0.0, 1.0)
        self.layout()
        if self.on_resize:
            self.on_resize(self.ratio)

    def draw(self):
        dx, dy, dw, dh = self._div()
        hot = self.pressed or (self.hover and self.ui.mouse[0] >= dx and self.ui.mouse[0] < dx + dw and self.ui.mouse[1] >= dy and self.ui.mouse[1] < dy + dh)
        lib.draw.rectangle(self.get("accent") if hot else self.get("border"), 0, dx + dw / 2 - 1, dy + 2, 2, dh - 4) if not self.vertical else \
            lib.draw.rectangle(self.get("accent") if hot else self.get("border"), 0, dx + 2, dy + dh / 2 - 1, dw - 4, 2)
        for i in (-1, 0, 1):                                  # grip dots
            if self.vertical:
                lib.draw.circle(self.get("fg_muted"), 0, dx + dw / 2 + i * 7, dy + dh / 2, 1.5)
            else:
                lib.draw.circle(self.get("fg_muted"), 0, dx + dw / 2, dy + dh / 2 + i * 7, 1.5)


class Carousel(Widget):
    """Pages you flip through with arrows or dots. gui.Carousel(x, y, w, h, pages=[panel, panel, ...], autoplay=0)"""
    clip_children = True

    def __init__(self, x=0, y=0, w=400, h=240, pages=(), autoplay=0.0, on_change=None, **kw):
        super().__init__(x, y, w, h, **kw)
        self.index, self._pos, self.autoplay, self.on_change = 0, 0.0, autoplay, on_change
        self._timer = 0.0
        for p in pages:
            self.add_page(p)

    def add_page(self, page):
        self.add(page)
        return page

    def go(self, i):
        n = len(self.children)
        if n:
            self.index = i % n
            self._timer = 0.0
            if self.on_change:
                self.on_change(self.index)

    def update(self, dt):
        n = len(self.children)
        self._pos = lerp(self._pos, self.index, min(1.0, dt * 9))
        if self.autoplay and n > 1:
            self._timer += dt
            if self._timer >= self.autoplay and not self.hover:
                self.go(self.index + 1)
        bar = 30
        for i, p in enumerate(self.children):
            p.x, p.y, p.w, p.h = (i - self._pos) * self.w, 0, self.w, self.h - bar
            p.visible = abs(i - self._pos) < 1.01

    def _zones(self):
        n = len(self.children)
        y = self.ay + (self.h - 30) / 2 - 18
        left = (self.ax + 8, y, 36, 36)
        right = (self.ax + self.w - 44, y, 36, 36)
        dots = []
        for i in range(n):
            dots.append((self.ax + self.w / 2 + (i - (n - 1) / 2) * 20, self.ay + self.h - 15))
        return left, right, dots

    def hit(self, px, py):
        if not self.visible or not self.contains(px, py):
            return None
        l, r, dots = self._zones()
        for z in (l, r):
            if z[0] <= px <= z[0] + z[2] and z[1] <= py <= z[1] + z[3] and len(self.children) > 1:
                return self
        if py > self.ay + self.h - 30:
            return self
        return super().hit(px, py) or self

    def mouse_down(self, x, y, button, clicks):
        l, r, dots = self._zones()
        if l[0] <= x <= l[0] + l[2] and l[1] <= y <= l[1] + l[3]:
            self.go(self.index - 1)
        elif r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
            self.go(self.index + 1)
        else:
            for i, (dx, dy) in enumerate(dots):
                if abs(x - dx) < 10 and abs(y - dy) < 10:
                    self.go(i)

    def get_cursor(self, x, y):
        l, r, dots = self._zones()
        for z in (l, r):
            if z[0] <= x <= z[0] + z[2] and z[1] <= y <= z[1] + z[3]:
                return "pointer"
        return "pointer" if y > self.ay + self.h - 30 else "default"

    def draw(self):
        box(self.ax, self.ay, self.w, self.h, self.plain("panel_bg"), self.plain("panel_border"), 1, self.plain("radius", 6))

    def draw_over(self):
        n = len(self.children)
        if n < 2:
            return
        l, r, dots = self._zones()
        for z, name in ((l, "left"), (r, "right")):
            hot = z[0] <= self.ui.mouse[0] <= z[0] + z[2] and z[1] <= self.ui.mouse[1] <= z[1] + z[3] and self.hover
            lib.draw.circle("#000000" + ("90" if hot else "50"), 0, z[0] + 18, z[1] + 18, 16)
            icon(name, z[0] + 18, z[1] + 18, 14, 0xFFFFFF, 2)
        for i, (dx, dy) in enumerate(dots):
            on = i == self.index
            lib.draw.circle(self.get("accent") if on else self.get("border_hover"), 0, dx, dy, 5 if on else 3.5)


class Modal(Widget):
    """Dialog shown with ui.show(modal) and closed with ui.close(modal) / Esc / its buttons.

        m = gui.Modal(title="Delete?", w=380, h=180, message="This cannot be undone.",
                      buttons=[("Cancel", None, False), ("Delete", do_delete, True)])
        ui.show(m)

    buttons: [(label, callback_or_None, primary)]. Put your own widgets in with m.add(...) (relative to below the title bar).
    """
    TITLE_H = 40

    def __init__(self, title="", w=380, h=200, message=None, buttons=(), closable=True, draggable=True, on_close=None, **kw):
        super().__init__(0, 0, w, h, **kw)
        self.title, self.message, self.closable, self.draggable, self.on_close = title, message, closable, draggable, on_close
        self.owner = None
        self._btns = []
        self._grab = None
        for label, cb, primary in buttons:
            def handler(b, cb=cb):
                if cb:
                    cb()
                self.close()
            self._btns.append(self.add(Button(0, 0, None, 34, text=label, primary=primary, on_click=handler)))

    def content_origin(self):
        return self.ax, self.ay + self.TITLE_H

    def center(self):
        if self.ui:
            self.x, self.y = (self.ui.width - self.w) / 2, (self.ui.height - self.h) / 2

    def close(self):
        if self.ui:
            self.ui.close(self)

    def opened(self): pass

    def closed(self):
        if self.on_close:
            self.on_close()

    def update(self, dt):
        x = self.w - 16
        for b in reversed(self._btns):
            x -= b.w
            b.x, b.y = x, self.h - self.TITLE_H - 16 - b.h
            x -= 10

    def hit(self, px, py):
        if not self.visible or not self.contains(px, py):
            return None
        return super().hit(px, py) or self

    def mouse_down(self, x, y, button, clicks):
        if y < self.ay + self.TITLE_H:
            if self.closable and x > self.ax + self.w - 38:
                self.close()
            elif self.draggable:
                self._grab = (x - self.x, y - self.y)

    def mouse_drag(self, x, y):
        if self._grab and self.ui:
            self.x = clamp(x - self._grab[0], 0, max(0, self.ui.width - self.w))
            self.y = clamp(y - self._grab[1], 0, max(0, self.ui.height - self.h))

    def mouse_up(self, x, y, button):
        self._grab = None

    def get_cursor(self, x, y):
        if y < self.ay + self.TITLE_H and self.closable and x > self.ax + self.w - 38:
            return "pointer"
        return "default"

    def draw(self):
        r = self.plain("radius", 6) + 2
        shadow(self.ax, self.ay, self.w, self.h, r, 14, self.plain("shadow"))
        box(self.ax, self.ay, self.w, self.h, self.plain("popup_bg"), self.plain("popup_border"), 1, r)
        lib.draw.line(self.get("border"), 1, self.ax + 1, self.ay + self.TITLE_H, self.ax + self.w - 1, self.ay + self.TITLE_H)
        self.text(self.title, self.ax + 18, self.ay + self.TITLE_H / 2, self.get("fg"), self.size_pt() + 2, "left", "middle")
        if self.closable:
            hot = self.hover and self.ui.mouse[1] < self.ay + self.TITLE_H and self.ui.mouse[0] > self.ax + self.w - 38
            icon("close", self.ax + self.w - 20, self.ay + self.TITLE_H / 2, 12, self.get("danger") if hot else self.get("fg_muted"))
        if self.message:
            for i, ln in enumerate(_wrap(self, self.message, self.w - 40)):
                self.text(ln, self.ax + 20, self.ay + self.TITLE_H + 18 + i * (self.size_pt() + 6), self.get("fg"))


class Resizable(Widget):
    """A panel (window) the user can resize by its edges and move by its title.
    gui.Resizable(x, y, w, h, title="Window", movable=True, min_w=140, min_h=100, on_resize=fn, layout=fn)
    layout(self) runs whenever the size changes so you can re-arrange children (relative to the panel body)."""
    EDGE = 6

    def __init__(self, x=0, y=0, w=300, h=200, title="", movable=True, min_w=140, min_h=100, max_w=None, max_h=None,
                 on_resize=None, layout=None, **kw):
        super().__init__(x, y, w, h, **kw)
        self.title, self.movable, self.min_w, self.min_h, self.max_w, self.max_h = title, movable, min_w, min_h, max_w, max_h
        self.on_resize, self.layout_fn = on_resize, layout
        self._mode = None
        self._last = (w, h)

    @property
    def title_h(self):
        return (self.size_pt() + 16) if self.title else 0

    def content_origin(self):
        return self.ax, self.ay + self.title_h

    @property
    def body_h(self):
        return self.h - self.title_h

    def layout(self):
        if self.layout_fn:
            self.layout_fn(self)

    def update(self, dt):
        if (self.w, self.h) != self._last:
            self._last = (self.w, self.h)
            self.layout()
            if self.on_resize:
                self.on_resize(self.w, self.h)

    def _region(self, x, y):
        e = self.EDGE
        l, r = x < self.ax + e, x >= self.ax + self.w - e
        t, b = y < self.ay + e, y >= self.ay + self.h - e
        mask = (1 if l else 0) | (2 if r else 0) | (4 if t else 0) | (8 if b else 0)
        if mask:
            return ("resize", mask)
        if self.title and y < self.ay + self.title_h and self.movable:
            return ("move", 0)
        return (None, 0)

    def hit(self, px, py):
        if not self.visible or not self.contains(px, py):
            return None
        if self._region(px, py)[0] == "resize":
            return self
        return super().hit(px, py) or self

    def get_cursor(self, x, y):
        kind, m = self._region(x, y)
        if kind == "resize":
            if m in (1, 2):
                return "ew-resize"
            if m in (4, 8):
                return "ns-resize"
            return "nsew-resize"
        return "move" if kind == "move" else "default"

    def mouse_down(self, x, y, button, clicks):
        self.bring_to_front()
        kind, m = self._region(x, y)
        self._mode = (kind, m, x, y, self.x, self.y, self.w, self.h) if kind else None

    def mouse_drag(self, x, y):
        if not self._mode:
            return
        kind, m, x0, y0, bx, by, bw, bh = self._mode
        dx, dy = x - x0, y - y0
        if kind == "move":
            self.x, self.y = bx + dx, by + dy
            return
        nx, ny, nw, nh = bx, by, bw, bh
        if m & 1:
            nw = clamp(bw - dx, self.min_w, self.max_w or 1e9)
            nx = bx + bw - nw
        if m & 2:
            nw = clamp(bw + dx, self.min_w, self.max_w or 1e9)
        if m & 4:
            nh = clamp(bh - dy, self.min_h, self.max_h or 1e9)
            ny = by + bh - nh
        if m & 8:
            nh = clamp(bh + dy, self.min_h, self.max_h or 1e9)
        self.x, self.y, self.w, self.h = nx, ny, nw, nh

    def mouse_up(self, x, y, button):
        self._mode = None

    def draw_tree(self):
        if not self.visible:
            return
        self.draw()
        self.ui.push_clip(self.ax + 1, self.ay + self.title_h, self.w - 2, self.h - self.title_h - 1)
        for c in self.children:
            c.draw_tree()
        self.ui.pop_clip()
        self.draw_over()

    def draw(self):
        r = self.plain("radius", 6)
        shadow(self.ax, self.ay, self.w, self.h, r, 10, self.plain("shadow"))
        box(self.ax, self.ay, self.w, self.h, self.plain("panel_bg"), self.get("accent") if self._mode else self.plain("panel_border"), 1, r)
        if self.title:
            box(self.ax, self.ay, self.w, self.title_h, self.get("bg"), self.plain("panel_border"), 1, r)
            self.text(self.title, self.ax + 12, self.ay + self.title_h / 2, self.get("fg"), None, "left", "middle")
        gx, gy = self.ax + self.w - 4, self.ay + self.h - 4              # grip
        for i in range(3):
            lib.draw.line(self.get("fg_muted"), 1, gx - 4 - i * 4, gy, gx, gy - 4 - i * 4)
