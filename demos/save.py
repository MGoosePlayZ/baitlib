# SAVE DEMO - ORB GARDEN, a tiny idle clicker whose point is the save system. It shows:
#   - lib.file.write (atomic) + lib.file.parseJson, three slots in demos/saves/
#   - a version field and migration from an old v1 format
#   - autosave on a timer, manual save/load, delete
#   - a .bak copy of the previous save, used automatically when the main file is corrupt
#   - offline progress computed from lib.time.unix() on load
#   - settings stored beside progress, and defaults filled in for missing keys
# Click the orb (or Space). Buy upgrades with 1 and 2. Everything else is buttons on the right.
import json
import math
import gui

lib.window.setTitle("BaitLib - save demo (orb garden)")
lib.window.setSize(1100, 640)
lib.window.setFps(60)

VERSION = 2
AUTOSAVE_EVERY = 10.0
width, height = 1100, 640
ui = gui.UI()
slot = 1
state = None
since_save = 0.0
autosave = True
pulse = 0.0
fx = []                       # floating "+n" texts: [x, y, text, life]
last_json = ""
json_t = 0.0


def path(n=None, bak=False):
    return f"saves/slot{n or slot}.json" + (".bak" if bak else "")


def new_state():
    now = lib.time.unix()
    return {"version": VERSION, "orbs": 0.0, "clicks": 0, "power": 1, "auto": 0,
            "created": now, "saved_at": now, "settings": {"autosave": True}}


def migrate(d):
    """Bring any older save up to VERSION, one step at a time. Never trust a file to be current."""
    if d.get("version", 1) < 2:                       # v1 was {"score", "click_power"}
        d = {"version": 2, "orbs": float(d.get("score", 0)), "clicks": 0, "power": d.get("click_power", 1),
             "auto": 0, "created": d.get("saved_at", lib.time.unix()), "saved_at": d.get("saved_at", lib.time.unix())}
        toast("migrated a v1 save to v2", "warning")
    base = new_state()                                # defaults fill in anything a file is missing
    base.update(d)
    base["settings"] = dict(new_state()["settings"], **d.get("settings", {}))
    return base


def cps():
    return state["auto"] * 0.5 * (1 + state["power"] * 0.1)


def toast(text, kind="info"):
    ui.toast(text, 2.5, kind)


def save(quiet=False):
    global since_save
    state["saved_at"] = lib.time.unix()
    try:
        old = lib.file.rawText(path())                # keep the previous good file as a backup first
        json.loads(old)
        lib.file.write(path(bak=True), old)
    except (FileNotFoundError, ValueError):
        pass
    lib.file.write(path(), state)                     # dict -> pretty JSON, atomic (temp file + rename)
    since_save = 0.0
    if not quiet:
        toast(f"saved slot {slot}", "success")


def load():
    """Returns True if a save was loaded. Falls back to the .bak file, then to nothing."""
    global state
    for use_bak in (False, True):
        try:
            d = lib.file.parseJson(path(bak=use_bak))
            if not isinstance(d, dict):
                raise ValueError("save is not an object")
        except FileNotFoundError:
            if not use_bak:
                toast(f"slot {slot} is empty", "warning")
                return False
            continue
        except ValueError:                            # json.JSONDecodeError is a ValueError
            toast(f"slot {slot} is corrupt" + (", trying backup" if not use_bak else ", no usable backup"), "danger")
            continue
        state = migrate(d)
        away = max(0.0, lib.time.unix() - state["saved_at"])
        gain = cps() * min(away, 3600) * 0.5          # offline progress: half rate, capped at an hour
        state["orbs"] += gain
        toast(f"loaded slot {slot}" + (" from backup" if use_bak else "") + (f", +{gain:.0f} orbs while away ({away:.0f}s)" if gain >= 1 else ""),
              "warning" if use_bak else "success")
        sync_ui()
        return True
    return False


def delete():
    import os
    for p in (path(), path(bak=True)):
        if os.path.exists(p):
            os.remove(p)
    toast(f"deleted slot {slot}", "warning")


def corrupt():
    lib.file.write(path(), "{ this is not json")
    toast("slot file overwritten with garbage: now press Load", "danger")


def legacy():
    lib.file.write(path(), {"score": 250, "click_power": 3, "saved_at": lib.time.unix() - 90})
    toast("wrote a v1 save: now press Load", "info")


def new_game():
    global state
    state = new_state()
    state["settings"]["autosave"] = autosave
    sync_ui()


def set_slot(k):
    global slot
    slot = k


def set_auto(v):
    global autosave
    autosave = v
    state["settings"]["autosave"] = v


def sync_ui():
    global autosave
    autosave = state["settings"]["autosave"]
    sw.value = autosave


def buy(kind):
    cost = 10 * 2 ** state["power"] if kind == "power" else 25 * 2 ** state["auto"]
    if state["orbs"] >= cost:
        state["orbs"] -= cost
        state[kind] += 1
        fx.append([330, 330, "upgraded!", 1.0])
    else:
        toast(f"need {cost:.0f} orbs", "warning")


# ---------------------------------------------------------------- ui
PX = 700
ui.add(gui.Label(PX, 20, text="Save slots", size=18))
group = gui.RadioGroup(1, on_change=set_slot)
for k in (1, 2, 3):
    ui.add(gui.Radio(PX + (k - 1) * 90, 52, text=f"Slot {k}", group=group, key=k))
ui.add(gui.Button(PX, 90, 90, 34, text="Save", primary=True, on_click=lambda b: save()),
       gui.Button(PX + 100, 90, 90, 34, text="Load", on_click=lambda b: load()),
       gui.Button(PX + 200, 90, 90, 34, text="Delete", on_click=lambda b: ui.confirm("Delete slot?", f"Slot {slot} and its backup will be removed.", delete)),
       gui.Button(PX + 300, 90, 90, 34, text="New game", on_click=lambda b: ui.confirm("Start over?", "Current progress is lost unless saved.", new_game)))
sw = ui.add(gui.Switch(PX, 140, text="Autosave every 10 seconds", value=True, on_change=set_auto))
ui.add(gui.Label(PX, 184, text="Test the edge cases", size=16, color=0x6FA8FF),
       gui.Button(PX, 212, 190, 32, text="Write a v1 save", on_click=lambda b: legacy(), tooltip="old format, migrated on Load"),
       gui.Button(PX + 200, 212, 190, 32, text="Corrupt this slot", on_click=lambda b: corrupt(), tooltip="Load then falls back to the .bak file"))
ui.add(gui.Label(PX, 262, text="What the save file holds", size=16, color=0x6FA8FF))
code = ui.add(gui.CodeBlock(PX, 290, 390, 300, text="", lang="json", auto_height=False))
code.h = 300                      # CodeBlock fits itself to its (empty) text on creation; restore the height we want
state = new_state()


def draw_game(dt):
    global pulse, since_save
    cx, cy, r = 330, 300, 110
    pulse = max(0.0, pulse - dt * 4)
    for k in range(6, 0, -1):
        lib.draw.circle([0.3, 1.0, 0.6, 0.05], 0, cx, cy, r * (1 + 0.12 * k + 0.1 * pulse))
    lib.draw.circle([0.12, 0.7, 0.4], 0, cx, cy, r * (1 + 0.06 * pulse))
    lib.draw.circle([0.6, 1, 0.8, 0.5], 0, cx - r * 0.3, cy - r * 0.3, r * 0.35)
    lib.draw.text("#FFFFFF", f"{state['orbs']:,.0f}", cx, 90, 64, "center", "middle")
    lib.draw.text("#9FE8C0", f"orbs   +{cps():.1f}/s", cx, 140, 20, "center", "middle")
    lib.draw.text("#B9C0D8", f"click power {state['power']}   helpers {state['auto']}   clicks {state['clicks']}", cx, 470, 16, "center")
    lib.draw.text("#FFD54A", f"[1] more power: {10 * 2 ** state['power']} orbs", cx, 510, 18, "center")
    lib.draw.text("#FFD54A", f"[2] a helper: {25 * 2 ** state['auto']} orbs", cx, 536, 18, "center")
    ago = lib.time.unix() - state["saved_at"]
    lib.draw.text("#7F8AAE", f"last saved {ago:.0f}s ago   next autosave in {max(0, AUTOSAVE_EVERY - since_save):.0f}s" if autosave else
                  f"last saved {ago:.0f}s ago   autosave off", cx, 590, 14, "center")
    for f in fx[:]:
        f[1] -= 60 * dt
        f[3] -= dt
        lib.draw.text([1, 1, 1, max(0, f[3])], f[2], f[0], f[1], 22, "center")
        if f[3] <= 0:
            fx.remove(f)
    click = lib.keyPressed("Space")
    for e in lib.getMouse():
        if e[7] == "Left" and e[8] and ui.hover is None and lib.collision.query(["point", e[1], e[2]], ["circle", cx, cy, r]):
            click = True
    if click:
        state["orbs"] += state["power"]
        state["clicks"] += 1
        pulse = 1.0
        fx.append([cx + lib.rand.float(-60, 60), cy - r - 10, f"+{state['power']}", 0.8])
    if lib.keyPressed("Key1"):
        buy("power")
    if lib.keyPressed("Key2"):
        buy("auto")


def onResize(w, h):
    global width, height
    width, height = w, h


def onUpdate(dt):
    global since_save, json_t, last_json
    dt = min(dt, 0.1)
    state["orbs"] += cps() * dt
    since_save += dt
    if autosave and since_save >= AUTOSAVE_EVERY:
        save(quiet=True)
        toast("autosaved", "info")
    json_t -= dt
    if json_t <= 0:                                   # refresh the live JSON view twice a second
        json_t = 0.5
        shown = dict(state, orbs=round(state["orbs"], 1), saved_at=round(state["saved_at"]), created=round(state["created"]))
        text = json.dumps(shown, indent=2)
        if text != last_json:
            last_json = text
            code.set_text(text)
    lib.draw.gradient("#0E1A1A", "#14102A", 0, 0, width, height, math.pi / 2)
    draw_game(dt)
    ui.update(dt)
    ui.draw()
