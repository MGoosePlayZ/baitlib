"""Lists and data: Dropdown, ComboBox, DataTable, FileTree, Breadcrumb, Chart."""
import math
import os

import lib

from .core import Widget, Popup, box, icon, clamp, lerp, alpha, mix, shadow
from .text import TextBox


def _norm_options(options):
    out = []
    for o in options:
        out.append((str(o[0]), o[1]) if isinstance(o, (tuple, list)) else (str(o), o))
    return out


class _DropList(Popup):
    def __init__(self, labels, on_pick, selected=-1, max_items=8, min_w=0):
        super().__init__(0, 0, 100, 100)
        self.labels, self.on_pick, self.selected, self.max_items = labels, on_pick, selected, max_items
        self.hi = selected
        self.scroll = 0.0
        self.min_w = min_w

    def set_labels(self, labels):
        self.labels = labels
        self.hi = -1
        self.scroll = 0.0

    @property
    def row_h(self):
        return self.size_pt() + 12

    def fit_size(self, anchor):
        rows = min(len(self.labels), self.max_items) or 1
        self.w = max(anchor.w, self.min_w)
        self.h = rows * self.row_h + 8
        self.place_below(anchor)

    def _row_at(self, y):
        i = int((y - self.ay - 4 + self.scroll) // self.row_h)
        return i if 0 <= i < len(self.labels) else -1

    def move(self, d):
        if not self.labels:
            return
        self.hi = clamp(self.hi + d, 0, len(self.labels) - 1)
        top, bot = self.hi * self.row_h, (self.hi + 1) * self.row_h
        view = self.h - 8
        if top < self.scroll:
            self.scroll = top
        elif bot > self.scroll + view:
            self.scroll = bot - view

    def pick_highlighted(self):
        if 0 <= self.hi < len(self.labels):
            self.on_pick(self.hi)

    def mouse_move(self, x, y):
        self.hi = self._row_at(y)

    def click(self, x, y, button):
        i = self._row_at(y)
        if i >= 0:
            self.on_pick(i)

    def wheel(self, delta, x, y):
        maxs = max(0, len(self.labels) * self.row_h - (self.h - 8))
        self.scroll = clamp(self.scroll - delta * self.row_h, 0, maxs)
        return True

    def draw(self):
        super().draw()
        self.ui.push_clip(self.ax + 1, self.ay + 4, self.w - 2, self.h - 8)
        for i, lab in enumerate(self.labels):
            y = self.ay + 4 + i * self.row_h - self.scroll
            if y + self.row_h < self.ay or y > self.ay + self.h:
                continue
            if i == self.hi:
                lib.draw.roundedRectangle(self.plain("row_hover"), 0, self.ax + 4, y + 1, self.w - 8, self.row_h - 2, 4, 4)
            if i == self.selected:
                lib.draw.roundedRectangle(self.plain("row_selected"), 0, self.ax + 4, y + 1, self.w - 8, self.row_h - 2, 4, 4)
            self.text(self.fit(lab, self.w - 24), self.ax + 12, y + self.row_h / 2, self.get("fg"), None, "left", "middle")
        self.ui.pop_clip()
        total = len(self.labels) * self.row_h
        if total > self.h - 8:
            th = max(20, (self.h - 8) ** 2 / total)
            ty = self.ay + 4 + ((self.h - 8) - th) * self.scroll / max(1, total - (self.h - 8))
            lib.draw.roundedRectangle(self.get("track"), 0, self.ax + self.w - 8, ty, 4, th, 2, 2)


class Dropdown(Widget):
    """Pick one option. options: ["a", "b"] or [("Label", value), ...].
    gui.Dropdown(x, y, w, h, options=[...], index=0, placeholder="Select...", on_change=fn(value, index))"""
    focusable = True
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=200, h=None, options=(), index=-1, placeholder="Select...", on_change=None, max_items=8, **kw):
        super().__init__(x, y, w, h or 34, **kw)
        if h is None:
            self.h = self.size_pt() + 16
        self.options = _norm_options(options)
        self.index, self.placeholder, self.on_change, self.max_items = index, placeholder, on_change, max_items
        self.popup = None

    @property
    def value(self):
        return self.options[self.index][1] if 0 <= self.index < len(self.options) else None

    def select(self, i, notify=True):
        i = int(i)
        if 0 <= i < len(self.options) and i != self.index:
            self.index = i
            if notify and self.on_change:
                self.on_change(self.options[i][1], i)

    @property
    def is_open(self):
        return self.popup is not None and self.popup in (self.ui.overlays if self.ui else [])

    def open(self):
        if self.is_open or not self.options:
            return
        self.popup = _DropList([o[0] for o in self.options], self._pick, self.index, self.max_items)
        self.ui.open_popup(self.popup, self)
        self.popup.fit_size(self)

    def close(self):
        if self.is_open:
            self.ui.close_popup(self.popup)

    def _pick(self, i):
        self.select(i)
        self.close()

    def click(self, x, y, button):
        if button == "left":
            self.close() if self.is_open else self.open()

    def key_down(self, key, mods):
        if self.is_open:
            if key == "Down":
                self.popup.move(1)
            elif key == "Up":
                self.popup.move(-1)
            elif key in ("Enter", "Space"):
                self.popup.pick_highlighted()
            else:
                return False
            return True
        if key in ("Enter", "Space"):
            self.open()
        elif key == "Down":
            self.select(min(len(self.options) - 1, self.index + 1))
        elif key == "Up":
            self.select(max(0, self.index - 1))
        else:
            return False
        return True

    def draw(self):
        self.draw_box()
        label = self.options[self.index][0] if 0 <= self.index < len(self.options) else self.placeholder
        col = self.get("fg") if 0 <= self.index < len(self.options) else self.get("fg_muted")
        if not self.enabled:
            col = self.get("fg_disabled")
        self.text(self.fit(label, self.w - 40), self.ax + 12, self.ay + self.h / 2, col, None, "left", "middle")
        icon("up" if self.is_open else "down", self.ax + self.w - 18, self.ay + self.h / 2, 10, self.get("fg_muted"))


class ComboBox(Widget):
    """Editable dropdown: type to filter suggestions, or pick from the list. .value is the text.
    gui.ComboBox(x, y, w, h, options=[...], text="", placeholder="", on_change=fn(text), strict=False)"""
    focusable = False

    def __init__(self, x=0, y=0, w=220, h=None, options=(), text="", placeholder="", on_change=None, strict=False, max_items=8, **kw):
        super().__init__(x, y, w, h or 34, **kw)
        if h is None:
            self.h = self.size_pt() + 16
        self.options = [o[0] for o in _norm_options(options)]
        self.on_change, self.strict, self.max_items = on_change, strict, max_items
        self.tb = TextBox(0, 0, self.w - 30, self.h, text=text, placeholder=placeholder)
        self.tb.on_change = self._typed
        self.tb.key_inner = self.tb.key_down
        self.tb.key_down = self._key
        self.arrow = _ArrowToggle(self)
        self.add(self.tb, self.arrow)
        self.popup = None
        self.layout()

    @property
    def value(self):
        return self.tb.value

    @value.setter
    def value(self, v):
        self.tb.set_text(v, notify=False)

    def layout(self):
        self.tb.w, self.tb.h = self.w - 30, self.h
        self.arrow.x, self.arrow.y, self.arrow.w, self.arrow.h = self.w - 30, 0, 30, self.h

    @property
    def is_open(self):
        return self.popup is not None and self.popup in (self.ui.overlays if self.ui else [])

    def _matches(self, query):
        q = query.lower()
        return [o for o in self.options if q in o.lower()] if q else list(self.options)

    def open(self, query=""):
        labels = self._matches(query)
        if not labels:
            self.close()
            return
        if not self.is_open:
            self.popup = _DropList(labels, self._pick, -1, self.max_items)
            self.ui.open_popup(self.popup, self)
        else:
            self.popup.set_labels(labels)
        self.popup.fit_size(self)

    def close(self):
        if self.is_open:
            self.ui.close_popup(self.popup)

    def _pick(self, i):
        self.tb.set_text(self.popup.labels[i], notify=False)
        self.close()
        if self.on_change:
            self.on_change(self.tb.value)

    def _typed(self, text):
        if self.tb.focused:
            self.open(text)
        if self.on_change:
            self.on_change(text)

    def _key(self, key, mods):
        if self.is_open:
            if key == "Down":
                self.popup.move(1)
                return True
            if key == "Up":
                self.popup.move(-1)
                return True
            if key in ("Enter", "NumEnter") and self.popup.hi >= 0:
                self.popup.pick_highlighted()
                return True
        elif key == "Down":
            self.open("")
            return True
        return self.tb.key_inner(key, mods)

    def draw(self):
        pass


class _ArrowToggle(Widget):
    cursor = "pointer"

    def __init__(self, combo):
        super().__init__(0, 0, 30, 30)
        self.combo = combo

    def click(self, x, y, button):
        c = self.combo
        c.close() if c.is_open else c.open("")

    def draw(self):
        icon("up" if self.combo.is_open else "down", self.ax + self.w / 2, self.ay + self.h / 2, 10, self.get("fg_muted"))


# ====================================================================== DataTable
class DataTable(Widget):
    """Scrollable, sortable table.

        t = gui.DataTable(x, y, w, h, columns=["Name", {"title": "Qty", "key": "qty", "width": 70, "align": "right"}],
                          rows=[["Apple", 3], ["Pear", 7]], on_select=fn(index, row))

    rows can be lists or dicts (matched by column key). Click a header to sort, drag a header edge to resize,
    click a row to select. .selected is the index into the rows you passed (or None)."""
    focusable = True

    def __init__(self, x=0, y=0, w=400, h=240, columns=(), rows=(), sortable=True, zebra=True, on_select=None,
                 on_sort=None, resizable_columns=True, **kw):
        super().__init__(x, y, w, h, **kw)
        self.columns = []
        for i, c in enumerate(columns):
            c = {"title": c} if isinstance(c, str) else dict(c)
            c.setdefault("key", c["title"])
            c.setdefault("align", "left")
            self.columns.append(c)
        self.rows = [list(r) if not isinstance(r, dict) else [r.get(c["key"]) for c in self.columns] for r in rows]
        self.sortable, self.zebra, self.on_select, self.on_sort, self.resizable_columns = sortable, zebra, on_select, on_sort, resizable_columns
        self.sort_col, self.sort_asc = None, True
        self.selected = None
        self.scroll = 0.0
        self.hover_row = -1
        self._resize = None
        self._order = list(range(len(self.rows)))
        self._widths = None
        self._fit_widths()

    # ---- data
    def set_rows(self, rows):
        self.rows = [list(r) if not isinstance(r, dict) else [r.get(c["key"]) for c in self.columns] for r in rows]
        self.selected = None
        self._resort()

    def selected_row(self):
        return self.rows[self.selected] if self.selected is not None else None

    def _fit_widths(self):
        fixed = sum(c.get("width", 0) for c in self.columns)
        free = [c for c in self.columns if not c.get("width")]
        share = max(40, (self.w - 10 - fixed) / max(1, len(free)))
        self._widths = [c.get("width") or share for c in self.columns]

    def _resort(self):
        order = list(range(len(self.rows)))
        if self.sort_col is not None:
            def key(i):
                v = self.rows[i][self.sort_col]
                return (0, v) if isinstance(v, (int, float)) else (1, str(v).lower())
            order.sort(key=key, reverse=not self.sort_asc)
        self._order = order

    # ---- geometry
    @property
    def row_h(self):
        return self.size_pt() + 12

    @property
    def head_h(self):
        return self.row_h + 4

    def _body(self):
        return self.ax, self.ay + self.head_h, self.w, self.h - self.head_h

    def _max_scroll(self):
        return max(0, len(self.rows) * self.row_h - (self.h - self.head_h))

    def _col_edges(self):
        x, out = self.ax, []
        for w in self._widths:
            out.append((x, x + w))
            x += w
        return out

    def _row_at(self, y):
        i = int((y - self.ay - self.head_h + self.scroll) // self.row_h)
        return i if 0 <= i < len(self.rows) else -1

    # ---- events
    def mouse_down(self, x, y, button, clicks):
        if y < self.ay + self.head_h:
            for i, (a, b) in enumerate(self._col_edges()):
                if self.resizable_columns and abs(x - b) <= 4:
                    self._resize = (i, x, self._widths[i])
                    return
            for i, (a, b) in enumerate(self._col_edges()):
                if a <= x < b and self.sortable and self.columns[i].get("sortable", True):
                    self.sort_asc = not self.sort_asc if self.sort_col == i else True
                    self.sort_col = i
                    self._resort()
                    if self.on_sort:
                        self.on_sort(i, self.sort_asc)
        else:
            r = self._row_at(y)
            if r >= 0:
                self.selected = self._order[r]
                if self.on_select:
                    self.on_select(self.selected, self.rows[self.selected])

    def mouse_drag(self, x, y):
        if self._resize:
            i, x0, w0 = self._resize
            self._widths[i] = max(30, w0 + x - x0)

    def mouse_up(self, x, y, button):
        self._resize = None

    def mouse_move(self, x, y):
        self.hover_row = self._row_at(y) if y >= self.ay + self.head_h else -1

    def mouse_leave(self):
        self.hover_row = -1

    def get_cursor(self, x, y):
        if self.resizable_columns and y < self.ay + self.head_h:
            for a, b in self._col_edges():
                if abs(x - b) <= 4:
                    return "ew-resize"
        return "default"

    def wheel(self, delta, x, y):
        if self._max_scroll() <= 0:
            return False
        self.scroll = clamp(self.scroll - delta * self.row_h * 2, 0, self._max_scroll())
        return True

    def key_down(self, key, mods):
        if not self.rows:
            return False
        pos = self._order.index(self.selected) if self.selected in self._order else -1
        n = int((self.h - self.head_h) / self.row_h)
        d = {"Up": -1, "Down": 1, "PageUp": -n, "PageDown": n}.get(key)
        if key == "Home":
            pos = 0
        elif key == "End":
            pos = len(self.rows) - 1
        elif d is not None:
            pos = clamp(pos + d, 0, len(self.rows) - 1)
        else:
            return False
        self.selected = self._order[pos]
        top, bot = pos * self.row_h, (pos + 1) * self.row_h
        view = self.h - self.head_h
        if top < self.scroll:
            self.scroll = top
        elif bot > self.scroll + view:
            self.scroll = bot - view
        if self.on_select:
            self.on_select(self.selected, self.rows[self.selected])
        return True

    def update(self, dt):
        self.scroll = clamp(self.scroll, 0, self._max_scroll())

    # ---- drawing
    def draw(self):
        self.draw_box(bg="panel_bg")
        edges = self._col_edges()
        bx, by, bw, bh = self._body()
        self.ui.push_clip(self.ax + 1, by, self.w - 2, bh - 1)
        first = int(self.scroll // self.row_h)
        for vis in range(first, min(len(self.rows), first + int(bh // self.row_h) + 2)):
            i = self._order[vis]
            y = by + vis * self.row_h - self.scroll
            if i == self.selected:
                lib.draw.rectangle(self.plain("row_selected"), 0, self.ax + 1, y, self.w - 2, self.row_h)
            elif vis == self.hover_row:
                lib.draw.rectangle(self.plain("row_hover"), 0, self.ax + 1, y, self.w - 2, self.row_h)
            elif self.zebra and vis % 2:
                lib.draw.rectangle(self.plain("row_alt"), 0, self.ax + 1, y, self.w - 2, self.row_h)
            for ci, (a, b) in enumerate(edges):
                v = self.rows[i][ci] if ci < len(self.rows[i]) else ""
                fmt = self.columns[ci].get("fmt")
                s = fmt(v) if fmt else str(v)
                al = self.columns[ci]["align"]
                self.ui.push_clip(a + 2, y, b - a - 4, self.row_h)
                if al == "right":
                    self.text(s, b - 10, y + self.row_h / 2, self.get("fg"), None, "right", "middle")
                elif al == "center":
                    self.text(s, (a + b) / 2, y + self.row_h / 2, self.get("fg"), None, "center", "middle")
                else:
                    self.text(s, a + 10, y + self.row_h / 2, self.get("fg"), None, "left", "middle")
                self.ui.pop_clip()
        self.ui.pop_clip()
        # header
        lib.draw.roundedRectangle(self.get("bg"), 0, self.ax + 1, self.ay + 1, self.w - 2, self.head_h, 5, 5)
        lib.draw.rectangle(self.get("bg"), 0, self.ax + 1, self.ay + self.head_h - 6, self.w - 2, 6)
        for ci, (a, b) in enumerate(edges):
            col = self.columns[ci]
            self.ui.push_clip(a, self.ay, b - a, self.head_h)
            title = col["title"]
            al = col["align"]
            tx = {"left": a + 10, "center": (a + b) / 2, "right": b - 10 - (14 if self.sort_col == ci else 0)}[al]
            self.text(title, tx, self.ay + self.head_h / 2, self.get("fg"), None, al, "middle")
            if self.sort_col == ci:
                icon("caret-up" if self.sort_asc else "caret-down", b - 14, self.ay + self.head_h / 2, 9, self.get("accent"))
            self.ui.pop_clip()
            if ci < len(edges) - 1:
                lib.draw.line(self.get("border"), 1, b, self.ay + 6, b, self.ay + self.head_h - 6)
        lib.draw.line(self.get("border"), 1, self.ax + 1, self.ay + self.head_h, self.ax + self.w - 1, self.ay + self.head_h)
        ms = self._max_scroll()
        if ms > 0:
            th = max(24, bh * bh / (len(self.rows) * self.row_h))
            ty = by + (bh - th) * self.scroll / ms
            lib.draw.roundedRectangle(self.get("track"), 0, self.ax + self.w - 9, ty, 5, th, 2, 2)


# ====================================================================== FileTree
class TreeNode:
    def __init__(self, name, children=None, data=None, parent=None, expanded=False):
        self.name, self.data, self.parent, self.expanded = name, data, parent, expanded
        self.children = None if children is None else [TreeNode(c.name, None if c.children is None else c.children, c.data, self) if isinstance(c, TreeNode) else c for c in children]

    @property
    def is_folder(self):
        return self.children is not None

    @property
    def path(self):
        return "/".join(reversed([n.name for n in self._chain()]))

    def _chain(self):
        n = self
        while n is not None:
            yield n
            n = n.parent


def _build(d, parent=None):
    out = []
    items = sorted(d.items(), key=lambda kv: (not isinstance(kv[1], dict), kv[0].lower()))
    for name, v in items:
        node = TreeNode(name, None, None, parent)
        if isinstance(v, dict):
            node.children = _build(v, node)
        else:
            node.data = v
        out.append(node)
    return out


class FileTree(Widget):
    """Expandable tree. nodes: nested dict {"src": {"main.py": None}, "README.md": None} (dict = folder).
    gui.FileTree(x, y, w, h, nodes={...}, on_select=fn(node), on_open=fn(node))   or   FileTree.from_path("some/dir")
    node.name, node.path, node.is_folder, node.data. Arrow keys navigate, Enter/double click opens/toggles."""
    focusable = True

    def __init__(self, x=0, y=0, w=240, h=300, nodes=None, on_select=None, on_open=None, show_root=False, **kw):
        super().__init__(x, y, w, h, **kw)
        self.on_select, self.on_open = on_select, on_open
        self.roots = _build(nodes or {})
        self.selected = None
        self.scroll = 0.0
        self.hover_row = -1
        self._rows = []

    @classmethod
    def from_path(cls, path, max_depth=4, max_entries=2000, **kw):
        count = [0]

        def scan(p, depth):
            d = {}
            try:
                for e in sorted(os.scandir(p), key=lambda e: e.name.lower()):
                    if e.name.startswith(".") or e.name == "__pycache__" or count[0] > max_entries:
                        continue
                    count[0] += 1
                    d[e.name] = scan(e.path, depth + 1) if e.is_dir() and depth < max_depth else ({} if e.is_dir() else None)
            except OSError:
                pass
            return d
        return cls(nodes=scan(path, 0), **kw)

    def _all(self, node):
        yield node
        for c in node.children or []:
            yield from self._all(c)

    def expand_all(self, expanded=True):
        for r in self.roots:
            for n in self._all(r):
                if n.is_folder:
                    n.expanded = expanded

    @property
    def row_h(self):
        return self.size_pt() + 8

    def _flatten(self):
        out = []

        def walk(nodes, depth):
            for n in nodes:
                out.append((n, depth))
                if n.is_folder and n.expanded:
                    walk(n.children, depth + 1)
        walk(self.roots, 0)
        self._rows = out
        return out

    def _max_scroll(self):
        return max(0, len(self._rows) * self.row_h + 8 - self.h)

    def _row_at(self, y):
        i = int((y - self.ay - 4 + self.scroll) // self.row_h)
        return i if 0 <= i < len(self._rows) else -1

    def select(self, node):
        self.selected = node
        if self.on_select:
            self.on_select(node)

    def toggle(self, node):
        if node.is_folder:
            node.expanded = not node.expanded
        elif self.on_open:
            self.on_open(node)

    def mouse_down(self, x, y, button, clicks):
        i = self._row_at(y)
        if i < 0:
            return
        node, depth = self._rows[i]
        ax = self.ax + 8 + depth * 18
        if node.is_folder and ax - 2 <= x <= ax + 16:
            self.toggle(node)
            return
        self.select(node)
        if clicks >= 2:
            self.toggle(node)

    def mouse_move(self, x, y):
        self.hover_row = self._row_at(y)

    def mouse_leave(self):
        self.hover_row = -1

    def wheel(self, delta, x, y):
        if self._max_scroll() <= 0:
            return False
        self.scroll = clamp(self.scroll - delta * self.row_h * 2, 0, self._max_scroll())
        return True

    def key_down(self, key, mods):
        rows = self._rows
        if not rows:
            return False
        idx = next((i for i, (n, d) in enumerate(rows) if n is self.selected), -1)
        if key == "Down":
            idx = min(len(rows) - 1, idx + 1)
        elif key == "Up":
            idx = max(0, idx - 1)
        elif key == "Right" and self.selected is not None and self.selected.is_folder:
            if not self.selected.expanded:
                self.selected.expanded = True
                return True
            idx = min(len(rows) - 1, idx + 1)
        elif key == "Left" and self.selected is not None:
            if self.selected.is_folder and self.selected.expanded:
                self.selected.expanded = False
                return True
            if self.selected.parent is not None:
                idx = next(i for i, (n, d) in enumerate(rows) if n is self.selected.parent)
        elif key in ("Enter", "Space") and self.selected is not None:
            self.toggle(self.selected)
            return True
        else:
            return False
        self.select(rows[idx][0])
        top, bot = idx * self.row_h, (idx + 1) * self.row_h + 8
        if top < self.scroll:
            self.scroll = top
        elif bot > self.scroll + self.h:
            self.scroll = bot - self.h
        return True

    def update(self, dt):
        self._flatten()
        self.scroll = clamp(self.scroll, 0, self._max_scroll())

    def draw(self):
        self.draw_box(bg="panel_bg")
        self.ui.push_clip(self.ax + 1, self.ay + 1, self.w - 2, self.h - 2)
        first = int(self.scroll // self.row_h)
        for i in range(first, min(len(self._rows), first + int(self.h // self.row_h) + 2)):
            node, depth = self._rows[i]
            y = self.ay + 4 + i * self.row_h - self.scroll
            if node is self.selected:
                lib.draw.rectangle(self.plain("row_selected"), 0, self.ax + 2, y, self.w - 4, self.row_h)
            elif i == self.hover_row:
                lib.draw.rectangle(self.plain("row_hover"), 0, self.ax + 2, y, self.w - 4, self.row_h)
            x = self.ax + 8 + depth * 18
            cy = y + self.row_h / 2
            if node.is_folder:
                icon("caret-down" if node.expanded else "caret-right", x + 7, cy, 9, self.get("fg_muted"))
                icon("folder", x + 26, cy, 15, self.get("warning"))
            else:
                icon("file", x + 26, cy, 15, self.get("fg_muted"), 1)
            self.text(self.fit(node.name, self.w - (x - self.ax) - 50), x + 40, cy, self.get("fg"), None, "left", "middle")
        self.ui.pop_clip()
        ms = self._max_scroll()
        if ms > 0:
            th = max(24, self.h * self.h / (len(self._rows) * self.row_h + 8))
            ty = self.ay + (self.h - th) * self.scroll / ms
            lib.draw.roundedRectangle(self.get("track"), 0, self.ax + self.w - 9, ty, 5, th, 2, 2)


# ====================================================================== Breadcrumb
class Breadcrumb(Widget):
    """Clickable path. gui.Breadcrumb(x, y, w, h, items=["Home", "Projects", "BaitLib"], on_click=fn(index, label))
    The last item is the current location. Too long paths collapse the middle into an ellipsis."""
    cursor = "pointer"

    def __init__(self, x=0, y=0, w=360, h=None, items=(), on_click=None, **kw):
        super().__init__(x, y, w, h or 28, **kw)
        self.items, self.on_click = list(items), on_click
        self._boxes = []

    def _layout(self):
        sep = 22
        widths = [self.measure(str(s))[0] + 12 for s in self.items]
        shown = list(range(len(self.items)))
        total = sum(widths) + sep * max(0, len(widths) - 1)
        collapsed = False
        while total > self.w and len(shown) > 2:
            collapsed = True
            drop = 1
            total -= widths[shown[drop]] + sep
            shown.pop(drop)
        out, x = [], self.ax
        for k, i in enumerate(shown):
            out.append((i, x, widths[i]))
            x += widths[i]
            if collapsed and k == 0:
                out.append((-1, x + sep, 22))
                x += 22 + sep
            if k < len(shown) - 1:
                x += sep if not (collapsed and k == 0) else 0
        return out

    def _item_at(self, x):
        for i, bx, bw in self._layout():
            if i >= 0 and bx <= x < bx + bw:
                return i
        return -1

    def click(self, x, y, button):
        i = self._item_at(x)
        if i >= 0 and i != len(self.items) - 1 and self.on_click:
            self.on_click(i, self.items[i])

    def get_cursor(self, x, y):
        i = self._item_at(x)
        return "pointer" if 0 <= i < len(self.items) - 1 else "default"

    def draw(self):
        lay = self._layout()
        mx = self.ui.mouse[0] if self.ui else -1
        cy = self.ay + self.h / 2
        for k, (i, bx, bw) in enumerate(lay):
            if i < 0:
                self.text("…", bx + 11, cy, self.get("fg_muted"), None, "center", "middle")
            else:
                last = i == len(self.items) - 1
                hot = self.hover and bx <= mx < bx + bw and not last
                col = self.get("fg") if last else (self.get("accent_hover") if hot else self.get("accent"))
                self.text(str(self.items[i]), bx + 6, cy, col, None, "left", "middle")
                if hot:
                    lib.draw.line(col, 1, bx + 6, cy + self.size_pt() / 2 + 1, bx + bw - 6, cy + self.size_pt() / 2 + 1)
            if k < len(lay) - 1:
                nx = lay[k + 1][1]
                icon("right", (bx + bw + nx) / 2, cy, 9, self.get("fg_muted"), 1)


# ====================================================================== Chart
PALETTE = [0x4C8DFF, 0x45C37B, 0xF0B24A, 0xEF5B6B, 0xB07CFF, 0x35C4D6, 0xFF8FB1, 0xA3D95B]


def _nice_ticks(lo, hi, n=5):
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.001:
        ticks.append(round(v, 10))
        v += step
    return ticks


class Chart(Widget):
    """Charts: kind = "line" | "area" | "bar" | "scatter" | "pie" | "donut".

        gui.Chart(x, y, w, h, kind="line", title="Sales",
                  series=[{"name": "2025", "values": [3, 5, 4, 8]}, {"name": "2026", "values": [4, 6, 7, 9]}],
                  labels=["Q1", "Q2", "Q3", "Q4"])

    series values: numbers (one per label), or for "scatter" a list of (x, y) pairs. pie/donut use series[0].values + labels.
    Optional: colors=[...], y_min, y_max, legend=True, grid=True, animated=True. Hover shows values."""

    def __init__(self, x=0, y=0, w=400, h=260, kind="line", series=(), labels=None, title="", legend=True, grid=True,
                 y_min=None, y_max=None, colors=None, animated=True, **kw):
        super().__init__(x, y, w, h, **kw)
        self.kind, self.title, self.legend, self.grid = kind, title, legend, grid
        self.labels, self.y_min, self.y_max, self.colors, self.animated = labels, y_min, y_max, colors or PALETTE, animated
        self.series = []
        self.set_series(series)
        self._t = 0.0 if animated else 1.0
        self._hover = None
        self._mouse = (0, 0)

    def set_series(self, series):
        out = []
        for i, s in enumerate(series):
            if not isinstance(s, dict):
                s = {"values": list(s)}
            s = dict(s)
            s.setdefault("name", f"Series {i + 1}")
            s.setdefault("color", self.colors[i % len(self.colors)] if hasattr(self, "colors") else PALETTE[i % len(PALETTE)])
            out.append(s)
        self.series = out
        self._t = 0.0 if getattr(self, "animated", False) else 1.0

    def update(self, dt):
        self._t = min(1.0, self._t + dt / 0.8)

    def mouse_move(self, x, y):
        self._mouse = (x, y)

    def mouse_leave(self):
        self._hover = None

    # ---- geometry
    def _plot(self):
        top = 38 if self.title else 14
        bottom = 30 if self.kind not in ("pie", "donut") else 14
        left = 48 if self.kind not in ("pie", "donut") else 14
        right = 14 + (110 if self.legend and self.kind in ("pie", "donut") else 0)
        if self.legend and self.kind not in ("pie", "donut") and len(self.series) > 1:
            top += 20
        return self.ax + left, self.ay + top, self.w - left - right, self.h - top - bottom

    def _range(self):
        vals = []
        for s in self.series:
            vs = [p[1] if isinstance(p, (tuple, list)) else p for p in s["values"]]
            vals += vs
        lo = self.y_min if self.y_min is not None else min(0, min(vals or [0]))
        hi = self.y_max if self.y_max is not None else max(vals or [1])
        ticks = _nice_ticks(lo, hi)
        return ticks[0], ticks[-1], ticks

    def draw(self):
        box(self.ax, self.ay, self.w, self.h, self.plain("panel_bg"), self.plain("panel_border"), 1, self.plain("radius", 6))
        self.ui.push_clip(self.ax + 1, self.ay + 1, self.w - 2, self.h - 2)
        if self.title:
            self.text(self.title, self.ax + 14, self.ay + 10, self.get("fg"), self.size_pt() + 2)
        e = 1 - (1 - self._t) ** 3
        if self.kind in ("pie", "donut"):
            self._draw_pie(e)
        else:
            self._draw_xy(e)
        self.ui.pop_clip()

    def _draw_legend_row(self):
        x, y = self.ax + 14, self.ay + (36 if self.title else 12)
        for s in self.series:
            lib.draw.roundedRectangle(s["color"], 0, x, y + 3, 12, 12, 3, 3)
            self.text(s["name"], x + 18, y, self.get("fg_muted"), self.size_pt() - 2)
            x += 30 + self.measure(s["name"], self.size_pt() - 2)[0]

    def _draw_xy(self, e):
        px, py, pw, ph = self._plot()
        lo, hi, ticks = self._range()
        scatter = self.kind == "scatter"
        span = (hi - lo) or 1
        ypos = lambda v: py + ph - (v - lo) / span * ph * e
        n = max((len(s["values"]) for s in self.series), default=1)
        labels = self.labels or [str(i + 1) for i in range(n)]
        if self.legend and len(self.series) > 1:
            self._draw_legend_row()
        for t in ticks:                                         # grid + y labels
            y = py + ph - (t - lo) / span * ph
            if self.grid:
                lib.draw.line(alpha(self.get("border"), 0.6), 1, px, y, px + pw, y)
            self.text(f"{t:g}", px - 8, y, self.get("fg_muted"), self.size_pt() - 3, "right", "middle")
        lib.draw.line(self.get("border_hover"), 1, px, py + ph, px + pw, py + ph)

        if scatter:
            xs = [p[0] for s in self.series for p in s["values"]]
            xlo, xhi = (min(xs), max(xs)) if xs else (0, 1)
            xticks = _nice_ticks(xlo, xhi, 6)
            xlo, xhi = xticks[0], xticks[-1]
            xpos = lambda v: px + (v - xlo) / ((xhi - xlo) or 1) * pw
            for t in xticks:
                self.text(f"{t:g}", xpos(t), py + ph + 6, self.get("fg_muted"), self.size_pt() - 3, "center", "top")
            for s in self.series:
                for (vx, vy) in s["values"]:
                    lib.draw.circle(alpha(s["color"], 0.85), 0, xpos(vx), ypos(vy), 4.5)
            self._hover_scatter(xpos, ypos)
            return

        cat_w = pw / n
        xc = lambda i: px + cat_w * (i + 0.5)
        step = max(1, math.ceil(self.measure(max(labels, key=len))[0] / max(1, cat_w) * 1.2)) if labels else 1
        for i, lab in enumerate(labels[:n]):
            if i % step == 0:
                self.text(str(lab), xc(i), py + ph + 6, self.get("fg_muted"), self.size_pt() - 3, "center", "top")

        mx, my = self._mouse
        hov = None
        if self.hover and px <= mx <= px + pw and py <= my <= py + ph:
            hov = clamp(int((mx - px) // cat_w), 0, n - 1)
        base = ypos(max(lo, 0)) if lo <= 0 <= hi else py + ph
        if self.kind == "bar":
            m = len(self.series)
            bw = cat_w * 0.7 / m
            for si, s in enumerate(self.series):
                for i, v in enumerate(s["values"]):
                    x = px + cat_w * i + cat_w * 0.15 + si * bw
                    y = ypos(v)
                    top, h = min(y, base), abs(base - y)
                    col = s["color"] if hov != i else mix(s["color"], 0xFFFFFF, 0.25)
                    lib.draw.roundedRectangle(col, 0, x + 1, top, max(1, bw - 2), max(1, h), 3, 3)
        else:
            for s in self.series:
                pts = [(xc(i), ypos(v)) for i, v in enumerate(s["values"])]
                if self.kind == "area" and len(pts) > 1:
                    poly = [pts[0][0], base] + [c for p in pts for c in p] + [pts[-1][0], base]
                    lib.draw.polygon(alpha(s["color"], 0.22), 0, *poly)
                for a, b in zip(pts, pts[1:]):
                    lib.draw.line(s["color"], 3, a[0], a[1], b[0], b[1])
                for i, p in enumerate(pts):
                    lib.draw.circle(self.plain("panel_bg"), 0, p[0], p[1], 5)
                    lib.draw.circle(s["color"], 0, p[0], p[1], 3.5 if hov != i else 5)
        if hov is not None:
            if self.kind != "bar":
                lib.draw.line(alpha(self.get("fg_muted"), 0.5), 1, xc(hov), py, xc(hov), py + ph)
            rows = [(s["name"], s["values"][hov], s["color"]) for s in self.series if hov < len(s["values"])]
            self._tooltip(str(labels[hov]) if hov < len(labels) else "", rows)

    def _hover_scatter(self, xpos, ypos):
        mx, my = self._mouse
        if not self.hover:
            return
        best, bd = None, 12
        for s in self.series:
            for (vx, vy) in s["values"]:
                d = math.hypot(xpos(vx) - mx, ypos(vy) - my)
                if d < bd:
                    best, bd = (s, vx, vy), d
        if best:
            lib.draw.circle(best[0]["color"], 2, xpos(best[1]), ypos(best[2]), 8)
            self._tooltip(best[0]["name"], [("x", best[1], best[0]["color"]), ("y", best[2], best[0]["color"])])

    def _tooltip(self, head, rows):
        size = self.size_pt() - 2
        lines = [(head, None)] + [(f"{n}: {v:g}" if isinstance(v, (int, float)) else f"{n}: {v}", c) for n, v, c in rows]
        w = max(self.measure(t, size)[0] for t, _ in lines) + 30
        h = len(lines) * (size + 6) + 10
        x = min(self._mouse[0] + 14, self.ax + self.w - w - 6)
        y = max(self.ay + 4, self._mouse[1] - h - 8)
        box(x, y, w, h, self.plain("popup_bg"), self.plain("popup_border"), 1, 5)
        for i, (t, c) in enumerate(lines):
            yy = y + 6 + i * (size + 6)
            if c is not None:
                lib.draw.circle(c, 0, x + 11, yy + size / 2 + 1, 4)
            self.text(t, x + (20 if c is not None else 10), yy, self.get("fg") if c is not None else self.get("fg_muted"), size)

    def _draw_pie(self, e):
        s = self.series[0] if self.series else {"values": [], "color": 0}
        vals = [max(0, v) for v in s["values"]]
        total = sum(vals) or 1
        px, py, pw, ph = self._plot()
        R = min(pw, ph) / 2 - 4
        cx, cy = px + pw / 2, py + ph / 2
        labels = self.labels or [str(i + 1) for i in range(len(vals))]
        mx, my = self._mouse
        ang = -math.pi / 2
        hov = None
        if self.hover:
            d = math.hypot(mx - cx, my - cy)
            if d <= R and (self.kind == "pie" or d >= R * 0.55):
                a = (math.atan2(my - cy, mx - cx) + math.pi / 2) % math.tau
                acc = 0
                for i, v in enumerate(vals):
                    acc += v / total * math.tau * e
                    if a <= acc:
                        hov = i
                        break
        for i, v in enumerate(vals):
            sweep = v / total * math.tau * e
            col = self.colors[i % len(self.colors)]
            r = R + (6 if hov == i else 0)
            if sweep > 0.001:
                n = max(2, int(sweep / 0.08))
                pts = [cx, cy] + [c for k in range(n + 1) for c in (cx + math.cos(ang + sweep * k / n) * r, cy + math.sin(ang + sweep * k / n) * r)]
                lib.draw.polygon(col, 0, *pts)
                lib.draw.polygon(self.plain("panel_bg"), 2, *pts)
            ang += sweep
        if self.kind == "donut":
            lib.draw.circle(self.plain("panel_bg"), 0, cx, cy, R * 0.55)
            self.text(f"{total:g}", cx, cy, self.get("fg"), self.size_pt() + 4, "center", "middle")
        if self.legend:
            for i, lab in enumerate(labels[:len(vals)]):
                y = py + 6 + i * (self.size_pt() + 6)
                lib.draw.roundedRectangle(self.colors[i % len(self.colors)], 0, self.ax + self.w - 120, y + 2, 12, 12, 3, 3)
                self.text(self.fit(f"{lab} {vals[i] / total * 100:.0f}%", 92), self.ax + self.w - 102, y, self.get("fg_muted"), self.size_pt() - 2)
        if hov is not None:
            self._tooltip(str(labels[hov]), [("value", vals[hov], self.colors[hov % len(self.colors)])])
