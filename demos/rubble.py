# RUBBLE - a pile of rocks (random convex and concave polygons) in a walled box. Drag any rock with the
# mouse: the pick uses world.pick, the drag is a spring joint (world.grab). Concave rocks are triangulated
# by the physics library automatically; the dark seams you see are the internal triangles.
#
# Drag: pick up a rock   R: new pile   Space: shake the box   T: show triangles   K: rk4 on/off
import math
import physics

lib.window.setTitle("BaitLib - rubble")
lib.window.setSize(1100, 760)
lib.window.setFps(60)

width, height = 1100, 760
ROCKS = 34
world = None
grab = None
held = None
shake = 0.0
show_tris = False
rk4 = False
arena = [0, 0, 0, 0]                 # x, y, w, h of the walled box
stats = {"concave": 0, "convex": 0}


def hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, u = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i]


def convex_rock(r):
    n = lib.rand.int(5, 8)
    angs = sorted(lib.rand.float(0, math.tau) for _ in range(n))
    return [(math.cos(a) * r * lib.rand.float(0.8, 1.05), math.sin(a) * r * lib.rand.float(0.8, 1.05)) for a in angs]


def concave_rock(r):
    """Star / jagged outline: alternating long and short spokes makes the polygon concave."""
    n = lib.rand.int(5, 7)
    off = lib.rand.float(0, math.tau)
    pts = []
    for i in range(n * 2):
        a = off + i * math.pi / n
        rr = r * (lib.rand.float(0.95, 1.15) if i % 2 == 0 else lib.rand.float(0.35, 0.6))
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    return pts


def arch_rock(r):
    """A fat 'L' shape, concave for sure."""
    s = r * 0.9
    return [(-s, -s), (-s * 0.1, -s), (-s * 0.1, s * 0.15), (s, s * 0.15), (s, s), (-s, s)]


def build():
    global world, held, grab
    world = physics.World(gravity=(0, 1000), iterations=10, substeps=3, cell=70)
    world.angular_damping = 0.4
    world.linear_damping = 0.05
    aw, ah = min(width - 40, 640), height - 80
    arena[:] = [(width - aw) / 2, 40, aw, ah]
    world.boundary(*arena, thickness=80, friction=0.8)
    grab = held = None
    stats["concave"] = stats["convex"] = 0
    for i in range(ROCKS):
        r = lib.rand.float(24, 46)
        kind = lib.rand.choice("convex", "convex", "concave", "arch")
        pts = {"convex": convex_rock, "concave": concave_rock, "arch": arch_rock}[kind](r)
        per_row = max(1, int((arena[2] - 60) // 95))
        gx, gy = i % per_row, i // per_row                      # jittered grid so rocks never start overlapped
        b = world.polygon(pts, x=arena[0] + 50 + gx * 95 + lib.rand.float(-4, 4), y=arena[1] + 50 + gy * 95 + lib.rand.float(-6, 6),
                          angle=lib.rand.float(0, math.tau), density=1.0, restitution=0.15, friction=0.7)
        b.user["hue"] = lib.rand.float(0.05, 0.14) if lib.rand.int(0, 3) else lib.rand.float(0.55, 0.62)
        b.user["tone"] = lib.rand.float(0.35, 0.8)
        b.user["concave"] = kind != "convex"
        stats["concave" if kind != "convex" else "convex"] += 1


build()


def onResize(w, h):
    global width, height
    if (w, h) != (width, height):
        width, height = w, h
        build()


def draw_rock(b, picked):
    base = hsv(b.user["hue"], 0.18 + 0.12 * b.user["tone"], 0.35 + 0.4 * b.user["tone"])
    hl = [min(1, c + 0.18) for c in base]
    dk = [c * 0.55 for c in base]
    # fill with the body's own triangles, tinted slightly per triangle so facets read as rock
    for i, s in enumerate(b.shapes()):
        k = 0.88 + 0.12 * math.sin(i * 2.7 + b.user["tone"] * 9)
        lib.draw.triangle([c * k for c in base], 0, *s[1:])
    pts = b.outline_points()
    # light edge on the upper-left, dark on the rest: cheap bevel from alpha lines
    if pts:
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            nx, ny = y2 - y1, -(x2 - x1)                        # outward-ish normal
            lit = (nx * -0.5 + ny * -0.85) / (math.hypot(nx, ny) or 1)
            lib.draw.line(with_a(hl, 0.7) if lit > 0.2 else with_a(dk, 0.9), 2, x1, y1, x2, y2)
        lib.draw.polygon("#00000050", 1, *[c for p in pts for c in p])
    if show_tris:
        for s in b.shapes():
            lib.draw.triangle("#FFFFFF60", 1, *s[1:])
    if picked:
        lib.draw.polygon("#FFD54A", 3, *[c for p in pts for c in p])


def with_a(c, a):
    return [c[0], c[1], c[2], a]


def onUpdate(dt):
    global grab, held, shake, show_tris, rk4
    dt = min(dt, 1 / 30)
    mx, my = lib.getMousePos()
    if lib.keyPressed("KeyR"):
        build()
    if lib.keyPressed("KeyT"):
        show_tris = not show_tris
    if lib.keyPressed("KeyK"):
        rk4 = not rk4
        physics.enableRk4(rk4)
    if lib.keyPressed("Space"):
        for b in world.bodies:
            if not b.static:
                b.apply_impulse(lib.rand.float(-1, 1) * b.mass * 500, -b.mass * lib.rand.float(500, 900))
        shake = 0.4

    for e in lib.getMouse():
        if e[7] != "Left":
            continue
        if e[8]:
            body = world.pick(mx, my)
            if body:
                grab, held = world.grab(body, mx, my, stiffness=160, damping=18), body
        if e[9] and grab:
            grab.release()
            grab = held = None
    if grab:
        grab.move(mx, my)
    lib.window.setCursor("move" if held else ("pointer" if world.pick(mx, my) else "default"))

    world.step(dt)
    shake = max(0.0, shake - dt)

    ox = lib.rand.float(-6, 6) * shake / 0.4
    oy = lib.rand.float(-6, 6) * shake / 0.4
    lib.draw.gradient("#2A2F3F", "#12141C", 0, 0, width, height, math.pi / 2)
    for i in range(0, width, 60):                                   # faint backdrop grid
        lib.draw.line("#FFFFFF08", 1, i + ox, 0, i + ox, height)
    for j in range(0, height, 60):
        lib.draw.line("#FFFFFF08", 1, 0, j + oy, width, j + oy)

    ax, ay, aw, ah = arena
    lib.draw.roundedRectangle("#00000040", 0, ax, ay, aw, ah, 6)
    lib.draw.roundedRectangle("#FFFFFF30", 2, ax - 1, ay - 1, aw + 2, ah + 2, 6)
    for b in world.bodies:
        if b.static:
            continue
        draw_rock(b, b is held)

    if grab and held:
        gx, gy = held.world_point(grab.lx, grab.ly)
        lib.draw.line("#FFD54AC0", 2, gx, gy, mx, my)
        lib.draw.circle("#FFD54A", 0, gx, gy, 4)
        lib.draw.circle("#FFD54A60", 2, mx, my, 9)

    lib.draw.roundedRectangle("#00000090", 0, 12, 12, 330, 62, 8)
    lib.draw.text("#FFFFFF", "Rubble", 24, 18, 22)
    lib.draw.text("#B9C0D8", f"{stats['convex']} convex, {stats['concave']} concave   rk4 {'on' if rk4 else 'off'}", 24, 44, 14)
    lib.draw.text("#6E7692", "drag  R new pile  Space shake  T triangles  K rk4", width / 2, height - 18, 14, "center", "middle")
