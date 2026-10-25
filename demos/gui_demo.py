# GUI DEMO - a fake game menu ("STARFALL") that leans on a lot of the gui library without trying to show
# everything (see gui_showcase.py for that). Buttons open modals and resizable windows with sliders,
# switches, radios, dropdowns, a data table, a chart, a file tree, a code preview, text boxes, pickers...
# Several widgets really do something: Fullscreen, Show FPS, the light theme and the captain's log.
#
# Mouse and keyboard (Tab cycles focus, Esc closes a modal). Drag windows by the title, resize from the edges.
import math
import gui

lib.window.setTitle("BaitLib - gui demo")
lib.window.setSize(1180, 720)
lib.window.setFps(60)

width, height = 1180, 720
ui = gui.UI()
wins = {}                    # name -> open Resizable, so a second click raises the window instead of duplicating it
settings = {"fps": False, "volume": 80, "light": False}
pilot = {"name": "Captain", "color": [0.3, 0.55, 1.0, 1.0]}
loading = {"on": False, "t": 0.0, "bar": None, "label": None, "modal": None, "steps": []}
t = 0.0
stars = [[lib.rand.float(0, 1), lib.rand.float(0, 1), lib.rand.float(0.2, 1)] for _ in range(130)]
fps = 60.0


# ------------------------------------------------------------------ windows
START = {"opt": (700, 40), "lb": (330, 60), "load": (330, 280), "log": (640, 330)}      # where each window first appears


def open_window(key, title, w, h, build, min_w=340, min_h=260):
    """Creates (or raises) a Resizable with a Close button. build(win) adds the content and returns a
    function fit(body_w, body_h) that lays it out whenever the window is resized."""
    win = wins.get(key)
    if win is not None and win in ui.widgets:
        win.bring_to_front()
        return win
    px, py = START.get(key, (340, 70))
    win = gui.Resizable(px, py, w, h, title=title, min_w=min_w, min_h=min_h)
    fit = build(win)
    close = win.add(gui.Button(0, 0, 86, 30, text="Close", on_click=lambda b: ui.remove(win)))

    def layout(self):
        bw, bh = self.w, self.body_h
        close.x, close.y = bw - 98, bh - 40
        fit(bw, bh - 50)
    win.layout_fn = layout
    layout(win)
    ui.add(win)
    wins[key] = win
    return win


def build_options(win):
    sv = win.add(gui.ScrollView(0, 0, 400, 300, border=False))
    y = 8

    def head(text):
        nonlocal y
        sv.add(gui.Label(14, y, text=text, color=0x6FA8FF))
        y += 26

    head("AUDIO")
    for name, val in (("Master", 80), ("Music", 55), ("Effects", 90)):
        sv.add(gui.Label(14, y + 3, text=name))
        sl = sv.add(gui.Slider(100, y, 230, 26, min=0, max=100, value=val, step=1, show_value=True,
                               on_change=(lambda v: settings.__setitem__("volume", v)) if name == "Master" else None))
        y += 34
    sv.add(gui.Separator(14, y + 2, 360))
    y += 14
    head("VIDEO")
    sv.add(gui.Label(14, y + 6, text="Resolution"))
    sv.add(gui.Dropdown(130, y, 200, options=["1280 x 720", "1920 x 1080", "2560 x 1440", "3840 x 2160"], index=0))
    y += 44
    sv.add(gui.Switch(14, y, text="Fullscreen", on_change=lambda v: lib.window.setFullscreen(v)))
    y += 36
    sv.add(gui.Checkbox(14, y, text="Show FPS counter", value=settings["fps"],
                        on_change=lambda v: settings.__setitem__("fps", v)))
    y += 32
    sv.add(gui.Checkbox(14, y, text="Vertical sync", value=True))
    y += 38
    sv.add(gui.Label(14, y + 6, text="Field of view"))
    sv.add(gui.Spinbox(130, y, 110, value=90, min=50, max=120, step=5))
    y += 44
    sv.add(gui.Label(14, y + 6, text="Brightness"))
    sv.add(gui.Slider(130, y, 200, 26, min=0, max=1, value=0.5, show_value=True, fmt=lambda v: f"{v:.2f}"))
    y += 40
    sv.add(gui.Separator(14, y, 360))
    y += 12
    head("INTERFACE")
    sv.add(gui.ToggleButton(14, y, 150, 32, text="Light theme", on_change=set_light))
    sv.add(gui.Label(176, y + 7, text="hot-swaps the whole UI", color=0x8E97AD))
    y += 46
    sv.add(gui.Label(14, y, text="Controls"))
    y += 26
    g = gui.RadioGroup("kbm", on_change=lambda k: ui.toast(f"Controls: {k}", 1.5))
    for key, text in (("kbm", "Keyboard + mouse"), ("pad", "Gamepad"), ("touch", "Touch")):
        sv.add(gui.Radio(14, y, text=text, group=g, key=key))
        y += 28
    sv.add(gui.Label(14, y + 8, text=" "))

    def fit(bw, bh):
        sv.w, sv.h = bw, bh
    return fit


def set_light(on):
    settings["light"] = on
    ui.theme = gui.Theme.light() if on else gui.theme
    ui.toast("Light theme" if on else "Dark theme", 1.5)


SCORES = [("Nova", 98420, "Hawk"), ("Kestrel", 91200, "Wasp"), ("Vega", 88750, "Hawk"), ("Orion", 80110, "Tank"),
          ("Lyra", 76490, "Wasp"), ("Atlas", 70120, "Tank"), ("Juno", 65340, "Hawk"), ("Rigel", 60880, "Wasp"),
          ("Mira", 55010, "Tank"), ("Cass", 49970, "Hawk"), ("Dax", 44230, "Wasp"), ("Echo", 39800, "Tank")]


def build_leaderboard(win):
    crumb = win.add(gui.Breadcrumb(10, 8, 400, items=["Home", "Leaderboard", "Global", "This season"],
                                   on_click=lambda i, label: ui.toast(f"Go to {label}", 1.2)))
    table = gui.DataTable(0, 0, 540, 240,           # built at its usual width: columns are sized once, in the constructor
                          columns=[{"title": "#", "width": 44, "align": "right"}, "Pilot",
                                   {"title": "Score", "width": 90, "align": "right", "fmt": lambda v: f"{v:,}"}, "Ship"],
                          rows=[[i + 1, n, s, ship] for i, (n, s, ship) in enumerate(SCORES)],
                          on_select=lambda i, row: ui.toast(f"{row[1]}: {row[2]:,} points", 1.5))
    chart = gui.Chart(0, 0, 100, 100, kind="bar", title="Top 6 scores",
                      series=[{"name": "Score", "values": [s for _, s, _ in SCORES[:6]]}],
                      labels=[n for n, _, _ in SCORES[:6]], legend=False)
    split = win.add(gui.Splitter(10, 44, 400, 300, first=table, second=chart, vertical=True, ratio=0.55))

    def fit(bw, bh):
        crumb.w = bw - 20
        split.w, split.h = bw - 20, bh - 44
    return fit


SAVE_TREE = {
    "saves": {
        "slot1.json": '{\n  "pilot": "Captain",\n  "ship": "Hawk",\n  "credits": 4200,\n  "sector": "Orion Gate",\n  "playtime": 7312\n}',
        "slot2.json": '{\n  "pilot": "Nova",\n  "ship": "Wasp",\n  "credits": 910,\n  "sector": "Vega Reach",\n  "playtime": 1204\n}',
        "autosave.json": '{\n  "pilot": "Captain",\n  "ship": "Hawk",\n  "credits": 4310,\n  "sector": "Orion Gate",\n  "playtime": 7390\n}',
    },
    "backups": {"slot1.bak": '{\n  "pilot": "Captain",\n  "credits": 3900\n}'},
}


def build_load(win):
    code = gui.CodeBlock(0, 0, 100, 140, text="Select a save file.", lang="json", auto_height=False)
    chosen = {"node": None}

    def pick(node):
        chosen["node"] = node
        if node.is_folder:
            code.set_text(f"// folder {node.name}")
        else:
            code.set_text(node.data)
    tree = gui.FileTree(0, 0, 100, 100, nodes=SAVE_TREE, on_select=pick,
                        on_open=lambda n: ui.toast(f"Loading {n.name}...", 1.5, "success"))
    tree.expand_all()
    split = win.add(gui.Splitter(10, 10, 400, 300, first=tree, second=code, ratio=0.42))
    delete = win.add(gui.Button(10, 0, 90, 30, text="Delete",
                                on_click=lambda b: chosen["node"] and not chosen["node"].is_folder and ui.confirm(
                                    "Delete save?", f"{chosen['node'].path} will be gone for good.",
                                    on_yes=lambda: ui.toast("Deleted (not really)", 1.5, "warning"))))
    load = win.add(gui.Button(110, 0, 90, 30, text="Load", primary=True,
                              on_click=lambda b: chosen["node"] and not chosen["node"].is_folder and ui.toast(
                                  f"Loaded {chosen['node'].name}", 2, "success")))

    def fit(bw, bh):
        split.w, split.h = bw - 20, bh - 52
        delete.y = load.y = bh - 26
    return fit


def build_log(win):
    area = win.add(gui.TextArea(10, 10, 400, 200, text="Day 1. Departed the station without incident.",
                                placeholder="Captain's log"))
    box = win.add(gui.TextBox(10, 0, 300, placeholder="Write an entry and press Enter..."))

    def submit(text):
        if not text.strip():
            return
        h, m = lib.time.civil()[3:5]
        area.set_text(area.value + f"\n[{h:02d}:{m:02d}] {text.strip()}", notify=False)
        box.set_text("", notify=False)
        area.cr = len(area.lines) - 1
        area.cc = len(area.lines[-1])
        area.ar, area.ac = area.cr, area.cc
    box.on_submit = submit

    def fit(bw, bh):
        area.w, area.h = bw - 20, bh - 56
        box.x, box.y, box.w = 10, bh - 38 + 10, bw - 20 - 100
    return fit


# ------------------------------------------------------------------ modals
def new_game():
    def launch():
        pilot["name"] = name.value.strip() or "Captain"
        pilot["color"] = list(hull.value)
        start_loading()

    m = gui.Modal(title="New game", w=560, h=560, buttons=[("Cancel", None, False), ("Launch", launch, True)])
    m.add(gui.Label(24, 16, text="Pilot name"))
    name = m.add(gui.TextBox(150, 10, 240, text=pilot["name"], placeholder="Your name", max_length=14))
    m.add(gui.Label(24, 62, text="Ship class"))
    ship = m.add(gui.Dropdown(150, 56, 240, options=[("Hawk - balanced", "Hawk"), ("Wasp - fast", "Wasp"), ("Tank - tough", "Tank")], index=0))
    m.add(gui.Label(24, 108, text="Difficulty"))
    g = gui.RadioGroup("normal")
    for i, (key, text) in enumerate((("easy", "Easy"), ("normal", "Normal"), ("hard", "Hard"))):
        m.add(gui.Radio(150 + i * 90, 106, text=text, group=g, key=key))
    m.add(gui.Label(24, 154, text="Home planet"))
    planet = m.add(gui.ComboBox(150, 148, 240, options=["Earth", "Mars", "Europa", "Titan", "Ceres", "Vesta"], text="Earth"))
    m.add(gui.Label(24, 200, text="Hull color"))
    hull = m.add(gui.ColorPicker(150, 194, 180, value=pilot["color"]))
    m.add(gui.Label(24, 246, text="Start date"))
    m.add(gui.DatePicker(150, 240, 180))
    m.add(gui.Label(24, 292, text="Credits"))
    m.add(gui.Spinbox(150, 286, 140, value=1000, min=0, max=10000, step=250))
    m.add(gui.Switch(24, 338, text="Permadeath"))
    m.add(gui.Checkbox(24, 374, text="Skip the tutorial"))
    m.add(gui.Separator(24, 414, 512))
    m.add(gui.Label(24, 424, text="Tab moves between fields. Esc cancels.", color=0x8E97AD))
    ui.show(m)
    ui.set_focus(name)


def start_loading():
    steps = ["Charging the jump drive", "Generating star systems", "Seeding the asteroid fields", "Waking the crew", "Ready"]
    m = gui.Modal(title="Launching", w=420, h=210, closable=False, draggable=False)
    m.add(gui.Spinner(24, 18, size=40))
    label = m.add(gui.Label(80, 26, text=steps[0]))
    bar = m.add(gui.Progress(24, 76, 370, 22, value=0, show_text=True))
    m.add(gui.LoadingBar(24, 116, 370, 6))
    loading.update(on=True, t=0.0, bar=bar, label=label, modal=m, steps=steps)
    ui.show(m)


def credits():
    pages = []
    for title, lines in (("STARFALL", "A fake game for a very real GUI library."),
                         ("Engine", "BaitLib: pygame-ce wearing a Castle costume."),
                         ("Music", "Procedural. Every note is a lib.sound.tone."),
                         ("Thanks", "To everyone who clicked the buttons.")):
        p = gui.Panel(0, 0, 100, 100)
        p.add(gui.Label(0, 40, 480, text=title, align="center", size=26))
        p.add(gui.Label(0, 90, 480, text=lines, align="center", color=0x8E97AD))
        pages.append(p)
    m = gui.Modal(title="Credits", w=520, h=300, buttons=[("Close", None, True)])
    m.add(gui.Carousel(10, 10, 500, 170, pages=pages, autoplay=3))
    ui.show(m)


def quit_game():
    ui.confirm("Quit to desktop?", "Unsaved progress will be lost.", on_yes=lambda: ui.toast("Just kidding, keep playing.", 2.5, "warning"))


# ------------------------------------------------------------------ main menu
MENU = [("New game", new_game, True), ("Load game", lambda: open_window("load", "Load game", 620, 380, build_load, 460, 280), False),
        ("Leaderboard", lambda: open_window("lb", "Leaderboard", 560, 480, build_leaderboard, 420, 360), False),
        ("Captain's log", lambda: open_window("log", "Captain's log", 460, 340, build_log, 320, 220), False),
        ("Options", lambda: open_window("opt", "Options", 420, 560, build_options, 340, 300), False),
        ("Credits", credits, False), ("Quit", quit_game, False)]
y = 250
for text, fn, primary in MENU:
    ui.add(gui.Button(60, y, 230, 44, text=text, primary=primary, on_click=lambda b, fn=fn: fn(),
                      tooltip=f"Open {text.lower()}"))
    y += 54
version = ui.add(gui.Label(60, 0, text="build 0.1.0  |  tab: focus  esc: close dialog", color=0x6B7592, size=13))


def onResize(w, h):
    global width, height
    width, height = w, h
    version.y = h - 30


def onUpdate(dt):
    global t, fps
    t += dt
    fps += (1 / max(dt, 1e-6) - fps) * 0.05

    # animated backdrop: a moving starfield and a planet, all drawn before the ui
    light = settings["light"]
    lib.draw.gradient("#EAF0FF" if light else "#05071A", "#B8C8F0" if light else "#1A1040", 0, 0, width, height, math.pi / 2)
    for s in stars:
        x = (s[0] - t * 0.01 * s[2]) % 1
        lib.draw.circle([0.2, 0.25, 0.5, 0.4] if light else [1, 1, 1, 0.25 + 0.6 * s[2]], 0, x * width, s[1] * height, 0.8 + 1.8 * s[2])
    px, py, pr = width * 0.78, height * 0.62, min(width, height) * 0.28
    for k in range(5, 0, -1):
        lib.draw.circle(pilot["color"][:3] + [0.04], 0, px, py, pr + k * 14)
    lib.draw.circle([0.08, 0.1, 0.2], 0, px, py, pr)
    lib.draw.circle(pilot["color"][:3] + [0.35], 0, px - pr * 0.25, py - pr * 0.25, pr * 0.72)
    lib.draw.circle([0, 0, 0, 0.45], 0, px + pr * 0.35, py + pr * 0.3, pr * 0.8)
    lib.draw.text("#F4F6FF" if not light else "#1D2330", "STARFALL", 60, 96, 76)
    lib.draw.text("#6FA8FF", "a fake menu for a real gui library", 64, 176, 20)

    # loading sequence driven from the demo
    if loading["on"]:
        loading["t"] += dt
        f = min(1.0, loading["t"] / 3.2)
        loading["bar"].value = f
        loading["label"].set_text(loading["steps"][min(len(loading["steps"]) - 1, int(f * len(loading["steps"])))])
        if f >= 1.0 and loading["t"] > 3.6:
            loading["on"] = False
            ui.close(loading["modal"])
            ui.toast("Welcome aboard, " + pilot["name"], 3, "success")

    ui.update(dt)
    ui.draw()
    if settings["fps"]:
        lib.draw.text("#6FF0A0", f"{fps:.0f} FPS", width - 16, 14, 18, "right")
