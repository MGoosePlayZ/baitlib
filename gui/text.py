"""Text editing: TextBox, TextArea, CodeBox, CodeBlock, Spinbox, plus the syntax highlighter."""
import math

import pygame

import lib

from .core import Widget, box, clamp, icon, alpha, shade


# ====================================================================== syntax highlighting
_PY_KW = set("and as assert async await break class continue def del elif else except finally for from global if import "
             "in is lambda nonlocal not or pass raise return try while with yield None True False".split())
_PY_BI = set("print len range int float str list dict set tuple bool open enumerate zip map filter sum min max abs sorted "
             "isinstance super self type input round reversed any all".split())
_LUA_KW = set("and break do else elseif end false for function goto if in local nil not or repeat return then true until while".split())
_LUA_BI = set("print pairs ipairs table string math require tostring tonumber type pcall error lib".split())
_JS_KW = set("break case catch class const continue default delete do else export extends false finally for function if import "
             "in instanceof let new null return super switch this throw true try typeof var void while with yield async await".split())
_C_KW = set("auto break case char const continue default do double else enum extern float for goto if int long register return "
            "short signed sizeof static struct switch typedef union unsigned void volatile while bool true false NULL".split())

LANGS = {
    "python": dict(kw=_PY_KW, bi=_PY_BI, comment="#", strings="'\"", block=('"""', "'''"), defs=("def", "class")),
    "lua": dict(kw=_LUA_KW, bi=_LUA_BI, comment="--", strings="'\"", block=(), defs=("function",)),
    "javascript": dict(kw=_JS_KW, bi=set("console document window Math JSON Array Object String Number".split()),
                       comment="//", strings="'\"`", block=(), defs=("function", "class")),
    "c": dict(kw=_C_KW, bi=set("printf malloc free sizeof NULL".split()), comment="//", strings="'\"", block=(), defs=()),
    "json": dict(kw=set("true false null".split()), bi=set(), comment=None, strings='"', block=(), defs=()),
}


def add_language(name, keywords=(), builtins=(), comment=None, strings="'\"", block_strings=(), def_words=()):
    """register your own highlighter: gui.add_language("sql", keywords=["select", "from"], comment="--")"""
    LANGS[name] = dict(kw=set(keywords), bi=set(builtins), comment=comment, strings=strings, block=tuple(block_strings),
                       defs=tuple(def_words))


def _tokenize(line, L, state):
    out, i, n = [], 0, len(line)
    prev_word = None
    if state:
        j = line.find(state)
        if j < 0:
            return [(line, "string")], state
        out.append((line[:j + len(state)], "string"))
        i, state = j + len(state), None
    while i < n:
        ch = line[i]
        if L["comment"] and line.startswith(L["comment"], i):
            out.append((line[i:], "comment"))
            break
        blk = next((b for b in L["block"] if line.startswith(b, i)), None)
        if blk:
            j = line.find(blk, i + len(blk))
            if j < 0:
                out.append((line[i:], "string"))
                state = blk
                break
            out.append((line[i:j + len(blk)], "string"))
            i = j + len(blk)
        elif ch in L["strings"]:
            j = i + 1
            while j < n and line[j] != ch:
                j += 2 if line[j] == "\\" else 1
            out.append((line[i:j + 1], "string"))
            i = j + 1
        elif ch.isdigit() or (ch == "." and i + 1 < n and line[i + 1].isdigit()):
            j = i + 1
            while j < n and (line[j].isalnum() or line[j] in "._"):
                j += 1
            out.append((line[i:j], "number"))
            i = j
        elif ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (line[j].isalnum() or line[j] == "_"):
                j += 1
            w = line[i:j]
            k = j
            while k < n and line[k] == " ":
                k += 1
            if w in L["kw"]:
                kind = "keyword"
            elif prev_word in L["defs"]:
                kind = "function"
            elif w in L["bi"]:
                kind = "builtin"
            elif k < n and line[k] == "(":
                kind = "function"
            else:
                kind = "default"
            out.append((w, kind))
            prev_word = w
            i = j
            continue
        else:
            j = i + 1
            while j < n and not (line[j].isalnum() or line[j] in "_'\"#" or line.startswith(L["comment"] or "\0", j)):
                j += 1
            out.append((line[i:j], "default"))
            i = j
        prev_word = None
    merged = []
    for t, k in out:
        if merged and merged[-1][1] == k == "default":
            merged[-1] = (merged[-1][0] + t, k)
        else:
            merged.append((t, k))
    return merged, state


def highlight(lines, lang):
    """-> list of [(text, kind), ...] per line. kinds: default keyword string comment number function builtin"""
    L = LANGS.get(lang)
    if L is None:
        return [[(ln, "default")] for ln in lines]
    out, state = [], None
    for ln in lines:
        toks, state = _tokenize(ln, L, state)
        out.append(toks or [("", "default")])
    return out


# ====================================================================== clipboard
def clip_get(ui):
    try:
        import pygame.scrap
        pygame.scrap.init()
        t = pygame.scrap.get_text()
        if t:
            return t
    except Exception:
        pass
    return ui.clipboard if ui else ""


def clip_set(ui, s):
    if ui:
        ui.clipboard = s
    try:
        import pygame.scrap
        pygame.scrap.init()
        pygame.scrap.put_text(s)
    except Exception:
        pass


# ====================================================================== editor core
class _Editor(Widget):
    focusable = True
    cursor = "text"
    clip_children = False
    multiline = True
    tab_inserts = False
    line_numbers = False
    use_mono = False

    def __init__(self, x=0, y=0, w=240, h=120, text="", placeholder="", read_only=False, lang=None, on_change=None,
                 on_submit=None, max_length=None, password=False, filter=None, line_numbers=None, tab_size=4, **kw):
        super().__init__(x, y, w, h, **kw)
        self.lines = [""]
        self.cr = self.cc = self.ar = self.ac = 0
        self.scroll_x = self.scroll_y = 0.0
        self.placeholder, self.read_only, self.lang = placeholder, read_only, lang
        self.on_change, self.on_submit, self.on_blur = on_change, on_submit, None
        self.max_length, self.password, self.filter = max_length, password, filter
        if line_numbers is not None:
            self.line_numbers = line_numbers
        self.tab_size = tab_size
        self.undo, self.redo, self._undo_t = [], [], 0.0
        self.version = 0
        self._hl = None
        self._blink = 0.0
        self._cw = None
        self.set_text(text, notify=False)

    # ---- text access
    @property
    def value(self):
        return "\n".join(self.lines)

    @value.setter
    def value(self, s):
        self.set_text(s)

    def set_text(self, s, notify=True):
        s = str(s).replace("\r\n", "\n").replace("\t", " " * self.tab_size)
        if not self.multiline:
            s = s.replace("\n", " ")
        self.lines = s.split("\n")
        self.cr = len(self.lines) - 1
        self.cc = len(self.lines[-1])
        self.ar, self.ac = self.cr, self.cc
        self.version += 1
        self.undo.clear()
        self.redo.clear()
        if notify and self.on_change:
            self.on_change(self.value)

    # ---- metrics
    def _fontkw(self):
        return dict(mono=self.use_mono)

    def line_h(self):
        return self.measure("Ag", None, self.use_mono)[1] + 2

    def cw(self):
        return self.measure("M", None, self.use_mono)[0]

    def x_of(self, line, col):
        if col <= 0:
            return 0
        s = "*" * len(line) if self.password else line
        return self.measure(s[:col], None, self.use_mono)[0]

    def col_at(self, line, px):
        s = "*" * len(line) if self.password else line
        if px <= 0:
            return 0
        lo, hi = 0, len(s)
        while lo < hi:                          # first col whose right edge is past px
            mid = (lo + hi) // 2
            if self.measure(s[:mid + 1], None, self.use_mono)[0] <= px:
                lo = mid + 1
            else:
                hi = mid
        if lo < len(s):
            left = self.measure(s[:lo], None, self.use_mono)[0]
            right = self.measure(s[:lo + 1], None, self.use_mono)[0]
            if px - left > (right - left) / 2:
                lo += 1
        return lo

    def gutter(self):
        if not self.line_numbers:
            return 0
        return self.measure(str(len(self.lines)) + " ", None, self.use_mono)[0] + 18

    def inner(self):
        pad = 8 if self.multiline else 8
        top = 6 if self.multiline else (self.h - self.line_h()) / 2
        g = self.gutter()
        sb = 8 if self.multiline else 0
        return self.ax + g + pad, self.ay + top, self.w - g - pad * 2 - sb, self.h - top * 2

    # ---- selection / editing primitives
    def selection(self):
        a, b = (self.ar, self.ac), (self.cr, self.cc)
        if a == b:
            return None
        return (a, b) if a < b else (b, a)

    def selected_text(self):
        s = self.selection()
        if not s:
            return ""
        (r1, c1), (r2, c2) = s
        if r1 == r2:
            return self.lines[r1][c1:c2]
        return "\n".join([self.lines[r1][c1:]] + self.lines[r1 + 1:r2] + [self.lines[r2][:c2]])

    def _snapshot(self, coalesce=False):
        now = self.ui.time if self.ui else 0
        if coalesce and self.undo and now - self._undo_t < 0.8:
            self._undo_t = now
            return
        self.undo.append((list(self.lines), self.cr, self.cc))
        if len(self.undo) > 200:
            self.undo.pop(0)
        self.redo.clear()
        self._undo_t = now

    def _changed(self):
        self.version += 1
        self._blink = 0.0
        self.ensure_visible()
        if self.on_change:
            self.on_change(self.value)

    def delete_selection(self):
        s = self.selection()
        if not s:
            return False
        (r1, c1), (r2, c2) = s
        self.lines[r1:r2 + 1] = [self.lines[r1][:c1] + self.lines[r2][c2:]]
        self.cr, self.cc, self.ar, self.ac = r1, c1, r1, c1
        return True

    def insert(self, s, coalesce=True):
        if self.read_only or not s:
            return
        s = s.replace("\r", "").replace("\t", " " * self.tab_size)
        if not self.multiline:
            s = s.replace("\n", " ")
        if self.filter:
            s = "".join(ch for ch in s if self.filter(ch))
            if not s:
                return
        if self.max_length is not None:
            room = self.max_length - len(self.value) + len(self.selected_text())
            s = s[:max(0, room)]
            if not s:
                return
        self._snapshot(coalesce and "\n" not in s)
        self.delete_selection()
        parts = s.split("\n")
        line = self.lines[self.cr]
        head, tail = line[:self.cc], line[self.cc:]
        if len(parts) == 1:
            self.lines[self.cr] = head + parts[0] + tail
            self.cc += len(parts[0])
        else:
            self.lines[self.cr:self.cr + 1] = [head + parts[0]] + parts[1:-1] + [parts[-1] + tail]
            self.cr += len(parts) - 1
            self.cc = len(parts[-1])
        self.ar, self.ac = self.cr, self.cc
        self._changed()

    def _word_left(self, r, c):
        ln = self.lines[r]
        while c > 0 and not (ln[c - 1].isalnum() or ln[c - 1] == "_"):
            c -= 1
        while c > 0 and (ln[c - 1].isalnum() or ln[c - 1] == "_"):
            c -= 1
        return c

    def _word_right(self, r, c):
        ln = self.lines[r]
        while c < len(ln) and not (ln[c].isalnum() or ln[c] == "_"):
            c += 1
        while c < len(ln) and (ln[c].isalnum() or ln[c] == "_"):
            c += 1
        return c

    def move_to(self, r, c, select=False):
        self.cr = clamp(r, 0, len(self.lines) - 1)
        self.cc = clamp(c, 0, len(self.lines[self.cr]))
        if not select:
            self.ar, self.ac = self.cr, self.cc
        self._blink = 0.0
        self.ensure_visible()

    def ensure_visible(self):
        ix, iy, iw, ih = self.inner()
        lh = self.line_h()
        cx = self.x_of(self.lines[self.cr], self.cc)
        if cx - self.scroll_x < 0:
            self.scroll_x = cx
        elif cx - self.scroll_x > iw - 4:
            self.scroll_x = cx - iw + 4
        if self.multiline:
            top = self.cr * lh
            if top < self.scroll_y:
                self.scroll_y = top
            elif top + lh > self.scroll_y + ih:
                self.scroll_y = top + lh - ih
        self.scroll_x = max(0, self.scroll_x)
        self.scroll_y = max(0, self.scroll_y)

    def select_all(self):
        self.ar = self.ac = 0
        self.cr = len(self.lines) - 1
        self.cc = len(self.lines[-1])

    # ---- input
    def text_input(self, s):
        if not self.read_only:
            self.insert(s)

    def key_down(self, key, mods):
        sh, ct = mods.shift, mods.ctrl
        r, c = self.cr, self.cc
        ln = self.lines[r]
        if ct and key in ("KeyA",):
            self.select_all()
        elif ct and key in ("KeyC", "KeyX"):
            t = self.selected_text()
            if t and not self.password:
                clip_set(self.ui, t)
                if key == "KeyX" and not self.read_only:
                    self._snapshot()
                    self.delete_selection()
                    self._changed()
        elif ct and key == "KeyV":
            if not self.read_only:
                self.insert(clip_get(self.ui), coalesce=False)
        elif ct and key in ("KeyZ", "KeyY"):
            if self.read_only:
                return True
            if key == "KeyY" or sh:
                if self.redo:
                    self.undo.append((list(self.lines), self.cr, self.cc))
                    self.lines, self.cr, self.cc = self.redo.pop()
                    self.ar, self.ac = self.cr, self.cc
                    self._changed()
            elif self.undo:
                self.redo.append((list(self.lines), self.cr, self.cc))
                self.lines, self.cr, self.cc = self.undo.pop()
                self.ar, self.ac = self.cr, self.cc
                self._changed()
        elif key == "Left":
            if not sh and self.selection():
                (r1, c1), _ = self.selection()
                self.move_to(r1, c1)
            elif c > 0:
                self.move_to(r, self._word_left(r, c) if ct else c - 1, sh)
            elif r > 0:
                self.move_to(r - 1, len(self.lines[r - 1]), sh)
        elif key == "Right":
            if not sh and self.selection():
                _, (r2, c2) = self.selection()
                self.move_to(r2, c2)
            elif c < len(ln):
                self.move_to(r, self._word_right(r, c) if ct else c + 1, sh)
            elif r < len(self.lines) - 1:
                self.move_to(r + 1, 0, sh)
        elif key in ("Up", "Down") and self.multiline:
            d = -1 if key == "Up" else 1
            if 0 <= r + d < len(self.lines):
                x = self.x_of(ln, c)
                self.move_to(r + d, self.col_at(self.lines[r + d], x), sh)
            else:
                self.move_to(r, 0 if d < 0 else len(ln), sh)
        elif key == "Home":
            self.move_to(0 if ct else r, 0, sh)
        elif key == "End":
            self.move_to(len(self.lines) - 1 if ct else r, 10 ** 9, sh)
        elif key in ("PageUp", "PageDown") and self.multiline:
            n = max(1, int(self.inner()[3] / self.line_h()) - 1)
            self.move_to(r + (n if key == "PageDown" else -n), c, sh)
        elif key == "Backspace" and not self.read_only:
            self._snapshot(True)
            if not self.delete_selection():
                if c > 0:
                    start = self._word_left(r, c) if ct else c - 1
                    self.lines[r] = ln[:start] + ln[c:]
                    self.cc = start
                elif r > 0:
                    self.cc = len(self.lines[r - 1])
                    self.lines[r - 1] += ln
                    del self.lines[r]
                    self.cr -= 1
            self.ar, self.ac = self.cr, self.cc
            self._changed()
        elif key == "Del" and not self.read_only:
            self._snapshot(True)
            if not self.delete_selection():
                if c < len(ln):
                    end = self._word_right(r, c) if ct else c + 1
                    self.lines[r] = ln[:c] + ln[end:]
                elif r < len(self.lines) - 1:
                    self.lines[r] += self.lines[r + 1]
                    del self.lines[r + 1]
            self.ar, self.ac = self.cr, self.cc
            self._changed()
        elif key in ("Enter", "NumEnter"):
            if self.multiline and not self.read_only and not ct:
                self.insert("\n" + self.auto_indent(ln[:c]), coalesce=False)
            elif self.on_submit:
                self.on_submit(self.value)
            else:
                return False
        elif key == "Tab" and self.tab_inserts and not self.read_only:
            if sh:
                if ln.startswith(" " * self.tab_size):
                    self._snapshot()
                    self.lines[r] = ln[self.tab_size:]
                    self.cc = max(0, c - self.tab_size)
                    self.ar, self.ac = self.cr, self.cc
                    self._changed()
            else:
                self.insert(" " * (self.tab_size - c % self.tab_size), coalesce=False)
        else:
            return False
        self._blink = 0.0
        return True

    def auto_indent(self, before):
        return ""

    def mouse_down(self, x, y, button, clicks):
        if button != "left":
            return
        r, c = self._hit(x, y)
        if clicks == 2:
            ln = self.lines[r]
            self.ar, self.ac = r, self._word_left(r, min(c + 1, len(ln))) if c < len(ln) else c
            self.cr, self.cc = r, self._word_right(r, self.ac)
        elif clicks >= 3:
            self.ar, self.ac, self.cr, self.cc = r, 0, r, len(self.lines[r])
        else:
            self.move_to(r, c, self.ui is not None and (lib.keyDown("Shift") is not None or lib.keyDown("RightShift") is not None))

    def mouse_drag(self, x, y):
        r, c = self._hit(x, y)
        self.move_to(r, c, True)

    def _hit(self, x, y):
        ix, iy, iw, ih = self.inner()
        lh = self.line_h()
        r = clamp(int((y - iy + self.scroll_y) // lh), 0, len(self.lines) - 1) if self.multiline else 0
        return r, self.col_at(self.lines[r], x - ix + self.scroll_x)

    def wheel(self, delta, x, y):
        if not self.multiline:
            return False
        lh = self.line_h()
        ih = self.inner()[3]
        maxs = max(0, len(self.lines) * lh - ih)
        if maxs <= 0:
            return False
        self.scroll_y = clamp(self.scroll_y - delta * lh * 3, 0, maxs)
        return True

    def focus_in(self):
        self._blink = 0.0

    def focus_out(self):
        if self.on_blur:
            self.on_blur(self)

    def update(self, dt):
        self._blink += dt

    # ---- drawing
    def draw(self):
        enabled = self.enabled
        bg = self.get("bg") if enabled else self.get("bg_disabled")
        border = self.get("border_focus") if self.focused else (self.get("border_hover") if self.hover else self.get("border"))
        if not enabled:
            border = self.get("border_disabled")
        box(self.ax, self.ay, self.w, self.h, bg, border, self.plain("border_w", 1), self.plain("radius", 6))
        ix, iy, iw, ih = self.inner()
        lh = self.line_h()
        g = self.gutter()
        mono = self.use_mono
        fg = self.get("fg") if enabled else self.get("fg_disabled")

        self.ui.push_clip(self.ax + 1, self.ay + 1, self.w - 2, self.h - 2)
        if g:
            lib.draw.rectangle(self.get("bg_active"), 0, self.ax + 1, self.ay + 1, g - 1, self.h - 2)
        first = int(self.scroll_y // lh) if self.multiline else 0
        last = min(len(self.lines) - 1, first + int(ih // lh) + 1) if self.multiline else 0
        sel = self.selection()
        if self.lang and self._hl is None or (self._hl and self._hl[0] != self.version):
            self._hl = (self.version, highlight(self.lines, self.lang) if self.lang else None)
        toks = self._hl[1] if self._hl else None

        self.ui.push_clip(ix - 2, self.ay + 1, iw + 4, self.h - 2)
        for r in range(first, last + 1):
            ln = self.lines[r]
            y = iy + (r * lh - self.scroll_y if self.multiline else 0)
            if sel and sel[0][0] <= r <= sel[1][0]:
                c1 = sel[0][1] if r == sel[0][0] else 0
                c2 = sel[1][1] if r == sel[1][0] else len(ln)
                x1, x2 = self.x_of(ln, c1), self.x_of(ln, c2) + (6 if r < sel[1][0] else 0)
                lib.draw.rectangle(self.plain("selection"), 0, ix - self.scroll_x + x1, y, max(2, x2 - x1), lh)
            if self.password:
                self.text("*" * len(ln), ix - self.scroll_x, y + 1, fg, None, "left", "top", mono)
            elif toks and r < len(toks[1] if False else toks):
                x = ix - self.scroll_x
                for t, kind in toks[r]:
                    if t:
                        self.text(t, x, y + 1, self.plain("syn_" + kind), None, "left", "top", mono)
                        x += self.measure(t, None, mono)[0]
            else:
                self.text(ln, ix - self.scroll_x, y + 1, fg, None, "left", "top", mono)
        if not self.value and self.placeholder and not (self.focused and False):
            self.text(self.placeholder, ix, iy + 1, self.get("fg_muted"), None, "left", "top", mono)
        if self.focused and enabled and not self.read_only and int(self._blink * 1.8) % 2 == 0:
            cx = ix - self.scroll_x + self.x_of(self.lines[self.cr], self.cc)
            cy = iy + (self.cr * lh - self.scroll_y if self.multiline else 0)
            lib.draw.rectangle(self.plain("caret"), 0, cx, cy + 1, 2, lh - 2)
        self.ui.pop_clip()

        if g:
            for r in range(first, last + 1):
                y = iy + r * lh - self.scroll_y
                self.text(str(r + 1), self.ax + g - 10, y + 1, self.plain("syn_gutter") if r != self.cr else self.get("fg"), None, "right", "top", mono)
            lib.draw.line(self.get("border"), 1, self.ax + g, self.ay + 1, self.ax + g, self.ay + self.h - 1)
        if self.multiline:                                   # slim scrollbar
            total = len(self.lines) * lh
            if total > ih:
                th = max(24, ih * ih / total)
                ty = self.ay + 6 + (ih - th) * (self.scroll_y / max(1, total - ih))
                lib.draw.roundedRectangle(self.get("track"), 0, self.ax + self.w - 9, ty, 5, th, 2, 2)
        self.ui.pop_clip()


class TextBox(_Editor):
    """Single line input. gui.TextBox(x, y, w, h, text="", placeholder="Name", on_change=fn, on_submit=fn,
    max_length=None, password=False, filter=fn(char)->bool). .value is the text."""
    multiline = False

    def __init__(self, x=0, y=0, w=200, h=None, **kw):
        super().__init__(x, y, w, h or 34, **kw)
        if h is None:
            self.h = self.size_pt() + 16


class TextArea(_Editor):
    """Multi-line input with scrolling, selection, undo/redo, copy/paste."""
    multiline = True

    def __init__(self, x=0, y=0, w=260, h=120, **kw):
        super().__init__(x, y, w, h, **kw)


class CodeBox(_Editor):
    """Code editor: monospace font, line numbers, syntax highlighting (lang="python" | "lua" | "javascript" | "c" | "json"
    or one from gui.add_language), Tab/Shift+Tab indent, auto indent."""
    multiline = True
    tab_inserts = True
    line_numbers = True
    use_mono = True

    def __init__(self, x=0, y=0, w=360, h=200, lang="python", **kw):
        super().__init__(x, y, w, h, lang=lang, **kw)

    def auto_indent(self, before):
        ind = " " * (len(before) - len(before.lstrip(" ")))
        s = before.rstrip()
        if self.lang == "python" and s.endswith(":"):
            ind += " " * self.tab_size
        elif self.lang in ("javascript", "c", "json") and s.endswith(("{", "[", "(")):
            ind += " " * self.tab_size
        elif self.lang == "lua" and s.endswith(("then", "do", "function()", "else")):
            ind += " " * self.tab_size
        return ind

    def draw(self):
        super().draw()


class CodeBlock(CodeBox):
    """Read-only highlighted code with a Copy button. auto_height=True sizes the block to its lines."""

    def __init__(self, x=0, y=0, w=360, h=None, text="", lang="python", line_numbers=False, auto_height=True, **kw):
        super().__init__(x, y, w, h or 80, text=text, lang=lang, read_only=True, line_numbers=line_numbers, **kw)
        self.auto_height = auto_height and h is None
        self._copied = 0.0
        self._fit()

    def set_text(self, s, notify=True):
        super().set_text(s, notify)
        if hasattr(self, "auto_height") and self.auto_height:
            self._fit()

    def _fit(self):
        self.h = len(self.lines) * self.line_h() + 14

    def _btn(self):
        return self.ax + self.w - 62, self.ay + 6, 54, 22

    def mouse_down(self, x, y, button, clicks):
        bx, by, bw, bh = self._btn()
        if bx <= x <= bx + bw and by <= y <= by + bh:
            clip_set(self.ui, self.value)
            self._copied = 1.2
            return
        super().mouse_down(x, y, button, clicks)

    def update(self, dt):
        super().update(dt)
        self._copied = max(0.0, self._copied - dt)

    def draw(self):
        super().draw()
        bx, by, bw, bh = self._btn()
        hot = self.hover and bx <= self.ui.mouse[0] <= bx + bw and by <= self.ui.mouse[1] <= by + bh
        box(bx, by, bw, bh, self.get("bg_hover") if hot else alpha(self.get("bg_active"), 0.8), self.get("border"), 1, 4)
        self.text("Copied" if self._copied > 0 else "Copy", bx + bw / 2, by + bh / 2, self.get("fg_muted"), 12, "center", "middle")

    def get_cursor(self, x, y):
        bx, by, bw, bh = self._btn()
        return "pointer" if bx <= x <= bx + bw and by <= y <= by + bh else "text"


class _Arrow(Widget):
    cursor = "pointer"

    def __init__(self, direction, on_click, **kw):
        super().__init__(0, 0, 20, 16, **kw)
        self.direction, self.on_click = direction, on_click
        self._hold = 0.0

    def mouse_down(self, x, y, button, clicks):
        self.on_click()
        self._hold = 0.0

    def update(self, dt):
        if self.pressed:
            self._hold += dt
            if self._hold > 0.4:
                self._hold -= 0.06
                self.on_click()

    def draw(self):
        bg = self.get("accent") if self.pressed else (self.get("bg_hover") if self.hover else self.get("bg"))
        box(self.ax, self.ay, self.w, self.h, bg, self.get("border"), 1, 3)
        icon("caret-up" if self.direction > 0 else "caret-down", self.ax + self.w / 2, self.ay + self.h / 2, 9, self.get("fg"))


class Spinbox(Widget):
    """Number input with up/down buttons, mouse wheel and Up/Down keys.
    gui.Spinbox(x, y, w, h, value=0, min=None, max=None, step=1, decimals=0, on_change=fn)"""
    focusable = False

    def __init__(self, x=0, y=0, w=120, h=None, value=0, min=None, max=None, step=1, decimals=None, on_change=None, **kw):
        super().__init__(x, y, w, h or 34, **kw)
        if h is None:
            self.h = self.size_pt() + 16
        self.min, self.max, self.step, self.on_change = min, max, step, on_change
        self.decimals = decimals if decimals is not None else (0 if float(step).is_integer() else 2)
        self.value = value
        self.tb = TextBox(0, 0, self.w - 24, self.h, filter=lambda ch: ch in "0123456789.-+eE")
        self.tb.on_submit = lambda s: self._commit()
        self.tb.on_blur = lambda t: self._commit()
        self.tb.key_down_inner = self.tb.key_down
        self.tb.key_down = self._tb_key
        self.tb.wheel = lambda d, x, y: (self.bump(d), True)[1]
        self.up = _Arrow(1, lambda: self.bump(1))
        self.dn = _Arrow(-1, lambda: self.bump(-1))
        self.add(self.tb, self.up, self.dn)
        self._sync()
        self.layout()

    def _fmt(self, v):
        return f"{v:.{self.decimals}f}"

    def _sync(self):
        self.tb.set_text(self._fmt(self.value), notify=False)

    def layout(self):
        self.tb.w, self.tb.h = self.w - 24, self.h
        self.up.x, self.up.y, self.up.w, self.up.h = self.w - 22, 1, 21, self.h / 2 - 1
        self.dn.x, self.dn.y, self.dn.w, self.dn.h = self.w - 22, self.h / 2, 21, self.h / 2 - 1

    def set_value(self, v, notify=True):
        if self.min is not None:
            v = max(self.min, v)
        if self.max is not None:
            v = min(self.max, v)
        v = round(v, self.decimals)
        if self.decimals == 0:
            v = int(v)
        changed = v != self.value
        self.value = v
        self._sync()
        if changed and notify and self.on_change:
            self.on_change(v)

    def bump(self, n):
        self.set_value(self.value + n * self.step)

    def _commit(self):
        try:
            self.set_value(float(self.tb.value))
        except ValueError:
            self._sync()

    def _tb_key(self, key, mods):
        if key == "Up":
            self.bump(10 if mods.shift else 1)
            return True
        if key == "Down":
            self.bump(-10 if mods.shift else -1)
            return True
        return self.tb.key_down_inner(key, mods)

    def hit(self, px, py):
        return super().hit(px, py)

    def draw(self):
        pass
