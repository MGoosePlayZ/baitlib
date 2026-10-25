# EASING - every function from the ease library as a circle travelling left to right and back,
# grouped into three columns: in, out, inout. Back and elastic overshoot the track on purpose.
#
# Space: pause   Up/Down: speed   Left/Right: scrub (while paused)   T: trails   Hover a row: show its curve
import math
import ease

lib.window.setTitle("BaitLib - easing functions")
lib.window.setSize(1280, 760)
lib.window.setFps(60)

width, height = 1280, 760
GROUPS = [("IN", "in", ease.in_), ("OUT", "out", ease.out), ("IN OUT", "inout", ease.inout)]
TRAVEL, HOLD = 1.6, 0.35                      # seconds per direction, pause at each end
CYCLE = (TRAVEL + HOLD) * 2
BG1, BG2 = "#0B0E1A", "#151B33"

t = 0.0
speed = 1.0
paused = False
trails = True
hist = {}                                      # (group, family) -> recent x positions for the trail


def hsv(h, s=0.65, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, u = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i]


def with_alpha(c, a):
    return [c[0], c[1], c[2], a]


def progress(time):
    """Returns (u, forward): u is linear progress 0..1 for the current leg, forward its direction."""
    p = time % CYCLE
    if p < TRAVEL:
        return p / TRAVEL, True
    if p < TRAVEL + HOLD:
        return 1.0, True
    p -= TRAVEL + HOLD
    if p < TRAVEL:
        return p / TRAVEL, False
    return 1.0, False


def layout():
    margin, gap = 36, 28
    col_w = (width - margin * 2 - gap * 2) / 3
    top = 128
    row_h = (height - top - 36) / len(ease.names)
    return margin, gap, col_w, top, row_h


def onResize(w, h):
    global width, height
    width, height = w, h


def draw_curve(fn, x, y, w, h, col):
    """The easing curve itself, drawn as a small inset with a marker for the current progress."""
    lib.draw.roundedRectangle("#000000A0", 0, x, y, w, h, 8)
    lib.draw.roundedRectangle(with_alpha(col, 0.6), 1, x, y, w, h, 8)
    pad = 10
    x0, y0, x1, y1 = x + pad, y + h * 0.78, x + w - pad, y + h * 0.22
    lib.draw.line("#FFFFFF30", 1, x0, y0, x1, y0)
    lib.draw.line("#FFFFFF30", 1, x0, y1, x1, y1)
    pts = []
    for i in range(61):
        u = i / 60
        pts += [lib.lerp(x0, x1, u), lib.lerp(y0, y1, fn(u))]
    for i in range(0, len(pts) - 2, 2):
        lib.draw.line(col, 2, pts[i], pts[i + 1], pts[i + 2], pts[i + 3])
    u, fwd = progress(t)
    cx, cy = lib.lerp(x0, x1, u), lib.lerp(y0, y1, fn(u))
    lib.draw.circle("#FFFFFF", 0, cx, cy, 4)


def onUpdate(dt):
    global t, speed, paused, trails
    dt = min(dt, 1 / 20)
    if lib.keyPressed("Space"):
        paused = not paused
    if lib.keyPressed("KeyT"):
        trails = not trails
    if lib.keyPressed("Up"):
        speed = min(4.0, speed * 1.25)
    if lib.keyPressed("Down"):
        speed = max(0.1, speed / 1.25)
    if paused:
        if lib.keyDown("Right") is not None:
            t += dt * 0.6
        if lib.keyDown("Left") is not None:
            t = max(0.0, t - dt * 0.6)
    else:
        t += dt * speed

    lib.draw.gradient(BG1, BG2, 0, 0, width, height, math.pi / 2)
    lib.draw.text("#FFFFFF", "Easing functions", 36, 24, 34)
    lib.draw.text("#8E9AC4", f"speed x{speed:.2f}   {'PAUSED' if paused else 'playing'}   "
                  "Space pause  Up/Down speed  Left/Right scrub  T trails", 36, 66, 16)

    u, fwd = progress(t)
    margin, gap, col_w, top, row_h = layout()
    mx, my = lib.getMousePos()
    hovered = None

    for gi, (title, key, group) in enumerate(GROUPS):
        cx = margin + gi * (col_w + gap)
        lib.draw.roundedRectangle("#FFFFFF08", 0, cx - 10, top - 6, col_w + 20, row_h * len(ease.names) + 12, 14)
        lib.draw.text("#FFFFFF", title, cx, top - 34, 22)
        label_w = 76
        tx0, tx1 = cx + label_w + 18, cx + col_w - 18
        for fi, name in enumerate(ease.names):
            fn = getattr(group, name)
            cy = top + fi * row_h + row_h / 2
            col = hsv(fi / len(ease.names))
            if cx <= mx <= cx + col_w and abs(my - cy) < row_h / 2:
                hovered = (fn, col, cx, cy, name, title)
                lib.draw.roundedRectangle("#FFFFFF10", 0, cx - 6, cy - row_h / 2 + 2, col_w + 12, row_h - 4, 8)
            lib.draw.text("#AAB4D8", name, cx, cy, 16, "left", "middle")
            # track with end stops
            lib.draw.line("#FFFFFF24", 2, tx0, cy, tx1, cy)
            lib.draw.line("#FFFFFF50", 2, tx0, cy - 9, tx0, cy + 9)
            lib.draw.line("#FFFFFF50", 2, tx1, cy - 9, tx1, cy + 9)

            e = fn(u)
            x = lib.lerp(tx0, tx1, e) if fwd else lib.lerp(tx1, tx0, e)
            tr = hist.setdefault((gi, name), [])
            tr.append(x)
            if len(tr) > 18:
                tr.pop(0)
            if trails:
                for k, px in enumerate(tr):
                    f = (k + 1) / len(tr)
                    lib.draw.circle(with_alpha(col, 0.05 + 0.3 * f * f), 0, px, cy, 4 + 5 * f)
            lib.draw.circle(with_alpha(col, 0.25), 0, x, cy, 15)       # soft halo
            lib.draw.circle(col, 0, x, cy, 9)
            lib.draw.circle("#FFFFFF90", 1, x, cy, 9)

    if hovered:
        fn, col, cx, cy, name, title = hovered
        w, h = 190, 120
        px = min(max(mx + 16, 8), width - w - 8)
        py = min(max(my - h - 12, 8), height - h - 8)
        draw_curve(fn, px, py, w, h, col)
        lib.draw.text("#FFFFFF", f"{title.lower()} {name}", px + 10, py + 6, 14)
