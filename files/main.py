# BaitLib demo, UV edition.  Run from the app folder:  python lib.py ./files/main.py
# Everything is positioned in UV space: (0,0) = top-left, (1,1) = bottom-right of the window.
# Sizes use `unit` = the shorter window side, so shapes keep their proportions on any window.
import math

lib.window.setTitle("BaitLib demo")
lib.window.setSize(960, 540)
lib.window.setFps(60)

icon = lib.file.image("icon.png")
beep = lib.file.audio("beep.wav")

width, height, unit = 960, 540, 540
time = 0.0
ball = lib.vec2(0.25, 0.35)        # uv
velocity = lib.vec2(0.28, 0.32)    # uv per second
radius = 0.05                      # fraction of unit
bounces = 0
BUTTON_COLORS = {"Left": 0xFF5555, "Middle": "#55FF55", "Right": [0.35, 0.6, 1.0]}


def px(u, v):
    """uv -> pixels"""
    return u * width, v * height


def uv(x, y):
    """pixels -> uv"""
    return x / width, y / height


def onResize(w, h):
    global width, height, unit
    width, height, unit = w, h, min(w, h)
    print(f"The window is now {w} pixels wide and {h} pixels tall!")


def bounce():
    global bounces
    bounces += 1
    lib.sound.play(beep, False, 0.4, 1.0, lib.rand.float(0.8, 1.6))


def rect(color, weight, u, v, w, h):
    """rectangle in uv; w,h are fractions of unit"""
    x, y = px(u, v)
    lib.draw.rectangle(color, weight, x, y, w * unit, h * unit)


def onUpdate(dt):
    global time, ball, velocity, radius
    time += dt

    # background + perlin noise bars along the bottom
    lib.draw.rectangle(0x14181F, 0, 0, 0, width, height)
    bars = 80
    for i in range(bars):
        u = i / bars
        n = lib.rand.perlin(u * 8, time * 0.5)
        h = n * 0.18
        x, y = px(u, 1 - h)
        lib.draw.rectangle([0.2, 0.3 + 0.4 * n, 0.5], 0, x, y, width / bars - 1, h * height)

    # bouncing ball: position in uv, radius in unit
    radius = lib.clamp(radius + lib.getScroll() * 0.005, 0.02, 0.2)
    ball = ball + velocity * dt
    ru, rv = radius * unit / width, radius * unit / height  # radius in uv, per axis
    if ball.x < ru or ball.x > 1 - ru:
        velocity.x = -velocity.x
        ball.x = lib.clamp(ball.x, ru, 1 - ru)
        bounce()
    if ball.y < rv or ball.y > 1 - rv:
        velocity.y = -velocity.y
        ball.y = lib.clamp(ball.y, rv, 1 - rv)
        bounce()

    # collision in pixel space: highlight ball while hovered
    bx, by = px(ball.x, ball.y)
    mx, my = lib.getMousePos()
    hovered = lib.collision.query(["circle", bx, by, radius * unit], ["point", mx, my])
    lib.draw.circle(0xFFD060 if hovered else 0xE0E0E0, 0, bx, by, radius * unit)
    lib.draw.circle(0x000000, 2, bx, by, radius * unit)
    lib.window.setCursor("pointer" if hovered else "default")

    # shape gallery: a row centered at v=0.72, each shape 0.1 unit
    s = 0.1
    row = 0.72
    rect(0xFF6B6B, 0, 0.08, row, s, s)
    x, y = px(0.22, row)
    lib.draw.roundedRectangle(0x6BCB77, 0, x, y, s * unit, s * unit, s * unit * 0.25, s * unit * 0.25)
    x, y = px(0.36, row)
    lib.draw.roundedRectangle(0x4D96FF, 3, x, y, s * unit * 1.4, s * unit, s * unit * 0.4, s * unit * 0.15)
    x, y = px(0.52, row)
    lib.draw.ellipse("#FFD93D", 0, x, y, s * unit * 1.4, s * unit)
    x1, y1 = px(0.68, row + s * unit / height)
    x2, y2 = px(0.68 + s * unit / width / 2, row)
    x3, y3 = px(0.68 + s * unit / width, row + s * unit / height)
    lib.draw.triangle(0xC77DFF, 0, x1, y1, x2, y2, x3, y3)
    cx, cy = px(0.82, row + 0.5 * s * unit / height)
    pts = []
    for i in range(6):
        a = time + i * math.pi / 3
        pts += [cx + s * unit * 0.5 * lib.cos(a), cy + s * unit * 0.5 * lib.sin(a)]
    lib.draw.polygon([1, 1, 1], 2, *pts)
    x1, y1 = px(0.9, row + s * unit / height)
    x2, y2 = px(0.95, row)
    lib.draw.line(0xFFFFFF, 4, x1, y1, x2, y2)

    # images: scale mode (1 scale = 1 image pixel, so derive scale from unit) and size mode
    x, y = px(0.04, 0.05)
    lib.draw.image("scale", x, y, icon, 1, unit * 0.12 / icon.width)
    x, y = px(0.04 + 0.14 * unit / width, 0.05)
    lib.draw.image("size", x, y, icon, 0.5 + 0.5 * lib.sin(time * 3), unit * 0.08, unit * 0.08)

    # mouse events: one per held button. Convert to uv to show it round-trips.
    for m in lib.getMouse():
        mid, x, y, dx, dy, ix, iy, action, pressed, released, duration = m
        col = BUTTON_COLORS[action]
        lib.draw.line(col, 3, ix, iy, x, y)
        lib.draw.circle(col, 0, x, y, unit * (0.015 + duration * 0.01))
        if pressed:
            u, v = uv(x, y)
            lib.sound.play(beep, False, 0.6, 1.0, lib.lerp(2.0, 0.5, v))

    # keys
    if lib.keyPressed("Space"):
        lib.sound.play(beep, False, 0.6, 1.5)
    held = lib.keyDown("KeyA")
    if held is not None:
        x, y = px(0.04, 0.3)
        lib.draw.text(0xFFFFFF, f"A held {held:.2f}s", x, y, unit * 0.04)

    # text: top-right, backed by a rounded box sized from measureText
    size = unit * 0.04
    msg = f"bounces: {bounces}   fps: {1 / max(dt, 1e-6):.0f}\nclick, scroll, space"
    tw, th = lib.draw.measureText(msg, size)
    pad = unit * 0.02
    x, y = px(0.97, 0.03)
    lib.draw.roundedRectangle(0x000000, 0, x - tw - pad, y - pad, tw + pad * 2, th + pad * 2, pad, pad)
    lib.draw.text(0xFFFFFF, msg, x, y, size, "right", "top")
    x, y = px(0.5, 0.99)
    lib.draw.text("#8899AA", "BaitLib", x, y, unit * 0.035, "center", "bottom")
