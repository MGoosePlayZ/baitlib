# GUI SHOWCASE - every widget in the gui library, grouped into accordion sections, each with a short note
# on how it works. Everything is live: type in the boxes, drag the sliders, open the pickers. The page is
# itself a gui.ScrollView holding a gui.Accordion, so it doubles as an example of both.
#
# Click a section title to open it. Wheel scrolls (the widget under the mouse gets the wheel first).
import datetime
import gui

lib.window.setTitle("BaitLib - gui showcase")
lib.window.setSize(1100, 780)
lib.window.setFps(60)

width, height = 1100, 780
CW = 740                                   # content width inside a section
ui = gui.UI()
gui.add_language("sql", keywords=["select", "from", "where", "join", "group", "by", "order", "limit", "insert", "into"],
                 comment="--")


# ------------------------------------------------------------------ small helpers
def wrap(text, w, size=13):
    """Word wraps text to w pixels. Labels don't wrap on their own, they only understand \\n."""
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            test = (line + " " + word).strip()
            if lib.draw.measureText(test, size)[0] <= w or not line:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return "\n".join(lines)


class Note(gui.Label):
    """Muted explanatory text that follows the theme."""

    def draw(self):
        self.text(str(self.text_value), self.ax, self.ay, self.get("fg_muted"), self.size)


class Head(gui.Label):
    """Accent coloured widget name."""

    def draw(self):
        self.text(str(self.text_value), self.ax, self.ay, self.get("accent"), self.size)


class Col:
    """Tiny vertical layout: head(), note() and put() stack things down a section."""

    def __init__(self, section, x=16, w=CW):
        self.sec, self.x, self.w, self.y = section, x, w, 12

    def head(self, text):
        self.y += 6
        self.sec.add(Head(self.x, self.y, text=text, size=16))
        self.y += 24

    def note(self, text):
        n = self.sec.add(Note(self.x, self.y, text=wrap(text, self.w), size=13))
        self.y += n.h + 8
        return n

    def put(self, widget, gap=8):
        widget.x, widget.y = self.x, self.y
        self.sec.add(widget)
        self.y += widget.h + gap
        return widget

    def row(self, *widgets, gap=14, after=8):
        x = self.x
        for w in widgets:
            w.x, w.y = x, self.y
            self.sec.add(w)
            x += w.w + gap
        self.y += max(w.h for w in widgets) + after
        return widgets

    def space(self, n=10):
        self.y += n


def readout(text=""):
    return Note(0, 0, text=text, size=13)


# ------------------------------------------------------------------ sections
def sec_basics(sec):
    c = Col(sec)
    c.head("Label")
    c.note("Static text. Pass text=, color= and size=. label.set_text(s) changes it. Labels never take the mouse, so "
           "they can sit on top of other widgets.")
    c.put(gui.Label(text="A plain label, colored", color=0x45C37B))

    c.head("Button")
    c.note("Button(x, y, w, h, text=, on_click=fn, primary=False). on_click receives the button. Pass w/h as None to fit "
           "the text. enabled=False greys it out, tooltip='...' shows after a short hover. Enter/Space press it when focused.")
    c.row(gui.Button(text="Normal", on_click=lambda b: ui.toast("Clicked Normal", 1.5)),
          gui.Button(text="Primary", primary=True, on_click=lambda b: ui.toast("Clicked Primary", 1.5, "success")),
          gui.Button(text="Disabled", enabled=False),
          gui.Button(text="Tooltip", tooltip="Hover for a moment to see this", on_click=lambda b: None))

    c.head("ToggleButton")
    c.note("A button that stays pressed. .value is True/False, on_change(value) fires on every click.")
    out = readout("value: False")
    c.row(gui.ToggleButton(text="Toggle me", on_change=lambda v: out.set_text(f"value: {v}")), out)

    c.head("Checkbox and Switch")
    c.note("Same idea, different look: value=, text=, on_change(value). The switch animates its knob.")
    out = readout("")
    c.row(gui.Checkbox(text="Checkbox", on_change=lambda v: out.set_text(f"checkbox {v}")),
          gui.Switch(text="Switch", on_change=lambda v: out.set_text(f"switch {v}")), out, gap=24)

    c.head("Radio and RadioGroup")
    c.note("Radios share a gui.RadioGroup(value, on_change). A radio is selected when group.value == its key. "
           "Arrow keys and Space work when focused.")
    out = readout("group.value = b")
    group = gui.RadioGroup("b", on_change=lambda k: out.set_text(f"group.value = {k}"))
    c.row(gui.Radio(text="A", group=group, key="a"), gui.Radio(text="B", group=group, key="b"),
          gui.Radio(text="C", group=group, key="c"), out, gap=20)

    c.head("Separator and Panel")
    c.note("Separator is a plain line. Panel is a bordered container: children use coordinates relative to it.")
    c.put(gui.Separator(w=CW, h=1), 12)
    panel = gui.Panel(0, 0, 360, 70)
    panel.add(Note(12, 10, text="Children of a panel use panel coordinates.", size=13))
    panel.add(gui.Button(12, 32, 110, 28, text="Inside"))
    c.put(panel)


def sec_sliders(sec):
    c = Col(sec)
    c.head("Slider")
    c.note("Slider(x, y, w, h, min=, max=, value=, step=, vertical=False, show_value=False, fmt=fn, on_change=fn(value)). "
           "step snaps the value, fmt formats the number shown. Arrow keys, Home and End work when focused.")
    prog = gui.Progress(0, 0, 360, 20, value=0.35, show_text=True)
    c.put(gui.Slider(0, 0, 300, 26, min=0, max=100, value=35, step=1, show_value=True,
                     on_change=lambda v: setattr(prog, "value", v / 100)))
    c.head("Progress")
    c.note("Progress(value=, min=0, max=1, show_text=False, fmt=fn, animated=True). Assign .value and the bar eases "
           "toward it. This one follows the slider above.")
    c.put(prog)
    c.head("Vertical slider")
    c.note("vertical=True stands the slider up (the value is drawn underneath).")
    c.row(gui.Slider(0, 0, 40, 130, min=0, max=10, value=4, vertical=True, show_value=True, step=0.5),
          gui.Slider(0, 0, 40, 130, min=0, max=10, value=8, vertical=True), gap=40, after=28)
    c.head("Spinner and LoadingBar")
    c.note("Busy indicators with no value: Spinner(size=, dots=, speed=) and LoadingBar(w, h, speed=). "
           "Use Progress when you know how far along you are.")
    c.row(gui.Spinner(size=40), gui.Spinner(size=26, dots=8, speed=2.0), gui.LoadingBar(0, 18, 300, 6), gap=24)


def sec_text(sec):
    c = Col(sec)
    c.head("TextBox")
    c.note("One line of text. text=, placeholder=, on_change(text), on_submit(text) on Enter, max_length=, "
           "password=True, read_only=True, filter=fn(char)->bool. .value is the text. Selection, copy and paste, "
           "double click to select a word, Ctrl+arrows to jump words.")
    out = readout("")
    box = gui.TextBox(0, 0, 260, placeholder="Type something", on_change=lambda t: out.set_text(f"{len(t)} characters"))
    c.row(box, out)
    c.row(gui.TextBox(0, 0, 200, placeholder="password", password=True),
          gui.TextBox(0, 0, 200, placeholder="digits only, max 6", filter=lambda ch: ch.isdigit(), max_length=6),
          gui.TextBox(0, 0, 200, text="read only", read_only=True))

    c.head("TextArea")
    c.note("Multi-line: scrolling, selection, undo and redo (Ctrl+Z / Ctrl+Y).")
    c.put(gui.TextArea(0, 0, CW, 90, text="Line one\nLine two\nTry Ctrl+Z after typing."))

    c.head("Spinbox")
    c.note("Number field with arrows. value=, min=, max=, step=, decimals=. Type a number, use Up/Down or the wheel.")
    out = readout("")
    c.row(gui.Spinbox(0, 0, 130, value=5, min=0, max=20, step=1, on_change=lambda v: out.set_text(f"value {v}")),
          gui.Spinbox(0, 0, 150, value=0.5, min=0, max=1, step=0.05, decimals=2), out)

    c.head("ComboBox")
    c.note("A text box with suggestions: it filters the list as you type but accepts any text unless strict=True.")
    c.put(gui.ComboBox(0, 0, 260, options=["Apple", "Apricot", "Banana", "Blueberry", "Cherry", "Mango", "Pear"],
                       placeholder="Fruit..."))
    c.space(110)       # room for the popup list so it never covers the next section's header while open


def sec_code(sec):
    c = Col(sec)
    c.head("CodeBox")
    c.note("An editable code editor: monospace font, line numbers, syntax highlighting, Tab / Shift+Tab indent and "
           "auto indent. lang is python, lua, javascript, c or json, or one you add with gui.add_language(name, "
           "keywords=[...], comment='--'). The right box uses a language added at the top of this file.")
    c.row(gui.CodeBox(0, 0, 360, 150, lang="python",
                      text="def greet(name):\n    # say hello\n    print(f\"Hello {name}\")\n    return 42\n"),
          gui.CodeBox(0, 0, 360, 150, lang="sql", text="-- custom language\nselect name, score\nfrom players\nwhere score > 10\norder by score limit 5"))
    c.head("CodeBlock")
    c.note("Read-only highlighted code with a Copy button. Its height fits the text by default (auto_height=True).")
    c.put(gui.CodeBlock(0, 0, CW, text='local x = 0\nfunction update(dt)\n  x = x + dt * 60\nend', lang="lua", line_numbers=True))


def sec_data(sec):
    c = Col(sec)
    c.head("Dropdown")
    c.note("Pick one option. options can be ['a', 'b'] or [(label, value), ...]. on_change(value, index). "
           ".value gives the selected value, .select(i) picks one from code.")
    out = readout("")
    c.row(gui.Dropdown(0, 0, 220, options=[("Small", 1), ("Medium", 2), ("Large", 3)], index=1,
                       on_change=lambda v, i: out.set_text(f"value {v}, index {i}")), out)
    c.space(4)

    c.head("DataTable")
    c.note("Sortable table. Columns are names or dicts ({'title', 'key', 'width', 'align', 'fmt', 'sortable'}), rows "
           "are lists or dicts. Click a header to sort, drag a header edge to resize, click a row to select it "
           "(on_select(index, row)). Sizes are worked out once, in the constructor.")
    rows = [[n, v, "yes" if v % 2 else "no"] for n, v in (("Alpha", 42), ("Bravo", 7), ("Charlie", 19), ("Delta", 88),
                                                         ("Echo", 3), ("Foxtrot", 61), ("Golf", 25), ("Hotel", 54))]
    out = readout("click a row")
    c.put(gui.DataTable(0, 0, CW, 170, columns=["Name", {"title": "Value", "align": "right", "width": 100}, "Odd"],
                        rows=rows, on_select=lambda i, row: out.set_text(f"selected {row[0]}")), 4)
    c.put(out)

    c.head("FileTree")
    c.note("Expandable tree from a nested dict (a dict is a folder, anything else is a file). FileTree.from_path('dir') "
           "scans a real folder. on_select(node) and on_open(node) (Enter or double click). node.name, node.path, node.is_folder.")
    out = readout("")
    tree = gui.FileTree(0, 0, 300, 160, nodes={"src": {"main.py": None, "util": {"math.py": None, "io.py": None}},
                                              "assets": {"icon.png": None}, "README.md": None},
                        on_select=lambda n: out.set_text(f"selected {n.path}"))
    tree.expand_all()
    c.row(tree, out)

    c.head("Breadcrumb")
    c.note("Clickable path. on_click(index, label). Paths too long for the width collapse their middle into '...'.")
    out = readout("")
    c.row(gui.Breadcrumb(0, 0, 360, items=["Home", "Projects", "BaitLib", "demos", "gui_showcase"],
                         on_click=lambda i, s: out.set_text(f"clicked {s}")), out)

    c.head("Chart")
    c.note("kind is line, area, bar, scatter, pie or donut. series is [{'name', 'values'}, ...] with labels=[...]; "
           "scatter takes (x, y) pairs; pie and donut use the first series. Hover for values. set_series() replaces the data.")
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    a, b = [3, 5, 4, 8, 6], [2, 4, 7, 5, 9]
    c.row(gui.Chart(0, 0, 360, 220, kind="line", title="line", series=[{"name": "A", "values": a}, {"name": "B", "values": b}], labels=labels),
          gui.Chart(0, 0, 360, 220, kind="bar", title="bar", series=[{"name": "A", "values": a}, {"name": "B", "values": b}], labels=labels))
    c.row(gui.Chart(0, 0, 240, 200, kind="area", title="area", series=[{"name": "A", "values": a}], labels=labels, legend=False),
          gui.Chart(0, 0, 240, 200, kind="pie", title="pie", series=[{"values": a}], labels=labels),
          gui.Chart(0, 0, 240, 200, kind="scatter", title="scatter",
                    series=[{"name": "dots", "values": [(1, 2), (2, 4), (3, 3), (4, 7), (5, 5), (6, 9)]}], legend=False))


def sec_pickers(sec):
    c = Col(sec)
    c.head("Pickers (field + popup)")
    c.note("DatePicker, TimePicker, DateTimePicker and ColorPicker are fields that open a popup. Each takes value= and "
           "on_change(value). Values are datetime.date, datetime.time, datetime.datetime and a [r, g, b, a] list of floats "
           "that works directly as a BaitLib color.")
    out = readout("pick something")
    swatch = gui.Panel(0, 0, 34, 34, style={"panel_bg": "#FF8844"})
    c.row(gui.DatePicker(0, 0, 170, value=datetime.date.today(), on_change=lambda d: out.set_text(f"date {d}")),
          gui.TimePicker(0, 0, 130, value=datetime.time(9, 30), on_change=lambda d: out.set_text(f"time {d}")),
          gui.DateTimePicker(0, 0, 210, on_change=lambda d: out.set_text(f"datetime {d:%Y-%m-%d %H:%M}")),
          gui.ColorPicker(0, 0, 150, value="#FF8844", on_change=lambda v: (out.set_text(f"color {v[0]:.2f} {v[1]:.2f} {v[2]:.2f} {v[3]:.2f}"),
                                                                           swatch.style.update(panel_bg=v))), after=4)
    c.row(out, swatch)
    c.space(10)
    c.head("Inline versions")
    c.note("Calendar, TimeSelector and ColorPanel are the same controls without the popup, always visible. "
           "Use them when the control is the whole point of the screen.")
    c.row(gui.Calendar(0, 0, 252, 250), gui.TimeSelector(0, 0, 210, 130, seconds=True), gui.ColorPanel(0, 0, 240, 250), gap=24)
    c.space(340)       # room for the popups to open downward


def sec_containers(sec):
    c = Col(sec)
    c.head("Accordion")
    c.note("This whole page. acc = gui.Accordion(x, y, w, exclusive=False); section = acc.add_section('Title', open=False, "
           "height=None); section.add(widget). Positions inside are relative to the section body. exclusive=True keeps only "
           "one open at a time.")
    c.head("Splitter")
    c.note("Two panes and a draggable divider: gui.Splitter(x, y, w, h, first=, second=, vertical=False, ratio=0.5, min_size=60). "
           "Panes are resized for you. Try dragging the divider.")
    left, right = gui.Panel(), gui.Panel()
    left.add(Note(12, 12, text="left pane", size=13))
    right.add(Note(12, 12, text="right pane", size=13))
    c.put(gui.Splitter(0, 0, 500, 120, first=left, second=right, ratio=0.4))

    c.head("Carousel")
    c.note("Pages you flip with arrows or dots: gui.Carousel(x, y, w, h, pages=[...], autoplay=seconds, on_change=fn(index)). "
           "go(i) jumps to a page. Autoplay pauses while hovered.")
    pages = []
    for i, word in enumerate(("one", "two", "three")):
        p = gui.Panel()
        p.add(gui.Label(0, 50, 500, text=f"page {word}", align="center", size=24))
        pages.append(p)
    c.put(gui.Carousel(0, 0, 500, 150, pages=pages, autoplay=4))

    c.head("ScrollView")
    c.note("Vertical scroller. Add children at any y; the content height is measured. Wheel or drag the bar.")
    sv = gui.ScrollView(0, 0, 360, 110)
    for i in range(14):
        sv.add(gui.Label(12, 8 + i * 26, text=f"row {i + 1}"))
    c.put(sv)

    c.head("Modal and Resizable")
    c.note("Modal: gui.Modal(title=, w=, h=, message=, buttons=[(label, callback, primary)]) shown with ui.show(modal); it "
           "blocks everything below and Esc closes it. Resizable: a window you move by its title and resize from any edge; "
           "its layout=fn(self) re-arranges children whenever it changes size.")
    c.row(gui.Button(text="Open a Modal", primary=True, on_click=lambda b: open_modal()),
          gui.Button(text="Open a Resizable", on_click=lambda b: open_window()))


def sec_ui(sec):
    c = Col(sec)
    c.head("Toasts")
    c.note("ui.toast(text, duration=3, kind='info') shows a notification bottom right. kind: info, success, warning, danger.")
    c.row(*[gui.Button(text=k, on_click=lambda b, k=k: ui.toast(f"This is a {k} toast", 2.5, k)) for k in ("info", "success", "warning", "danger")])
    c.head("alert and confirm")
    c.note("ui.alert(title, message, on_close) and ui.confirm(title, message, on_yes, on_no) are quick ready-made modals.")
    c.row(gui.Button(text="alert", on_click=lambda b: ui.alert("Heads up", "Alerts have one button.", lambda: ui.toast("Closed", 1.2))),
          gui.Button(text="confirm", on_click=lambda b: ui.confirm("Sure?", "Confirm has two buttons.", lambda: ui.toast("Yes", 1.2, "success"), lambda: ui.toast("No", 1.2, "warning"))))
    c.head("Focus")
    c.note("Click focuses a widget; Tab and Shift+Tab cycle through the focusable ones. ui.set_focus(widget) does it from code.")
    c.space(4)


class Meter(gui.Widget):
    """A custom widget: subclass Widget, draw with self.ax / self.ay, react to mouse_down / mouse_drag."""

    def __init__(self, x=0, y=0, w=300, h=22, value=0.5, **kw):
        super().__init__(x, y, w, h, **kw)
        self.value = value

    def draw(self):
        gui.box(self.ax, self.ay, self.w, self.h, self.get("track"), None, 0, 6)
        gui.box(self.ax, self.ay, max(2, self.w * self.value), self.h, self.get("accent"), None, 0, 6)
        self.text(f"{self.value * 100:.0f}%", self.ax + self.w / 2, self.ay + self.h / 2, self.get("accent_fg"), 13, "center", "middle")

    def mouse_down(self, x, y, button, clicks):
        self.value = min(1, max(0, (x - self.ax) / self.w))

    mouse_drag = mouse_down
    cursor = "pointer"


def sec_style(sec):
    c = Col(sec)
    c.head("Themes")
    c.note("Everything reads its look from style keys: the widget's own style dict, then the theme entry for its class, then "
           "the theme default '*'. ui.theme = gui.Theme.light() swaps the whole look; gui.theme.set('*', accent=..., radius=...) "
           "restyles every widget at once; widget.style.update(bg=...) changes one.")

    def set_theme(light):
        ui.theme = gui.Theme.light() if light else gui.theme
    c.row(gui.Button(text="Dark", on_click=lambda b: set_theme(False)),
          gui.Button(text="Light", on_click=lambda b: set_theme(True)))

    def accent(v):
        ui.theme.set("*", accent=v, accent_hover=gui.shade(v, 0.15), accent_active=gui.shade(v, -0.15))
    c.row(gui.Label(text="Accent"), gui.ColorPicker(0, 0, 150, value="#4C8DFF", on_change=accent), gui.Label(text="Radius"),
          gui.Slider(0, 0, 160, 26, min=0, max=16, value=6, step=1, show_value=True,
                     on_change=lambda v: ui.theme.set("*", radius=v)), gap=12)
    c.head("Your own widget")
    c.note("Subclass gui.Widget, draw with lib.draw (self.ax / self.ay are the absolute position), and override "
           "mouse_down / mouse_drag / mouse_up / click / wheel / text_input / key_down / update. This Meter is about 15 lines "
           "and uses theme keys, so it follows the accent color. Click or drag it.")
    c.put(Meter())
    c.space(10)


# ------------------------------------------------------------------ modal / window demos
def open_modal():
    m = gui.Modal(title="A Modal", w=400, h=200, message="Modals dim and block everything underneath. Esc or the X closes it.",
                  buttons=[("Cancel", None, False), ("OK", lambda: ui.toast("OK pressed", 1.5, "success"), True)])
    ui.show(m)


def open_window():
    win = gui.Resizable(260, 140, 360, 240, title="A Resizable", min_w=240, min_h=160)
    note = win.add(Note(12, 12, text="Drag my title to move me.\nDrag any edge or corner to resize.", size=13))
    close = win.add(gui.Button(0, 0, 80, 28, text="Close", on_click=lambda b: ui.remove(win)))

    def layout(self):
        close.x, close.y = self.w - 92, self.body_h - 40
    win.layout_fn = layout
    layout(win)
    ui.add(win)


# ------------------------------------------------------------------ page
SECTIONS = [("Basics: Label, Button, Checkbox, Switch, Radio...", sec_basics),
            ("Sliders and progress", sec_sliders),
            ("Text input", sec_text),
            ("Code", sec_code),
            ("Data and navigation", sec_data),
            ("Pickers", sec_pickers),
            ("Containers", sec_containers),
            ("Dialogs, toasts and focus", sec_ui),
            ("Styling and custom widgets", sec_style)]

sv = ui.add(gui.ScrollView(16, 76, 1068, 690, border=False))
acc = sv.add(gui.Accordion(0, 4, 1020))
for i, (title, build) in enumerate(SECTIONS):
    build(acc.add_section(title, open=(i == 0)))


def set_all(open_):
    for s in acc.sections:
        s.open = open_


ui.add(gui.Button(16, 24, 110, 32, text="Expand all", on_click=lambda b: set_all(True)),
       gui.Button(134, 24, 120, 32, text="Collapse all", on_click=lambda b: set_all(False)))


def onResize(w, h):
    global width, height
    width, height = w, h
    sv.w, sv.h = w - 32, h - 92
    acc.w = w - 32 - 24


def onUpdate(dt):
    th = ui.theme.d["*"]
    lib.draw.rectangle(th["panel_bg"], 0, 0, 0, width, height)
    lib.draw.text(th["fg"], "GUI showcase", 270, 40, 22, "left", "middle")
    lib.draw.text(th["fg_muted"], "every widget, with notes on how it works", 440, 41, 14, "left", "middle")
    ui.update(dt)
    ui.draw()
