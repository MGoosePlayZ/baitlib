# PHYSICS STRESS TEST - balls rain into a box until the frame rate gives up. Shows FPS, ball count,
# contact count and how long the physics step takes, with a live graph. Everything is a toggle.
#
# Space: spawning on/off   K: rk4 on/off   C: delete all balls   Up/Down: spawn rate   G: flip gravity
# B: bigger/smaller balls   Click: burst at the mouse   1-4: substeps
import math
import time
import physics

lib.window.setTitle("BaitLib - physics stress test")
lib.window.setSize(1180, 760)
lib.window.setFps(0)                       # uncapped so the FPS number means something

width, height = 1180, 760
world = physics.World(gravity=(0, 900), iterations=6, substeps=2, cell=40)
box = [0, 0, 0, 0]
spawning = True
rate = 60                                  # balls per second
rk4 = False
big = False
spawn_acc = 0.0
fps = 60.0
step_ms = 0.0
hist_fps, hist_ms = [], []
flip = 1
total_spawned = 0


def build_box():
    global world
    bx, by = 250, 20
    bw, bh = width - 270, height - 40
    box[:] = [bx, by, bw, bh]
    world.clear()
    world.boundary(*box, thickness=60, friction=0.4)


build_box()


def onResize(w, h):
    global width, height
    if (w, h) != (width, height):
        width, height = w, h
        build_box()


def hsv(h, s=0.7, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, u = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i]


def spawn(x=None, y=None):
    global total_spawned
    bx, by, bw, bh = box
    r = lib.rand.float(9, 14) if big else lib.rand.float(4, 7)
    if x is None:
        x = lib.rand.float(bx + bw * 0.25, bx + bw * 0.75)
        y = by + 20 if flip > 0 else by + bh - 20
    b = world.circle(x, y, r, restitution=0.35, friction=0.2)
    b.vx = lib.rand.float(-60, 60)
    b.user["hue"] = (total_spawned * 0.0007) % 1.0
    total_spawned += 1


def balls():
    return len(world.bodies) - 4


def graph(x, y, w, h, data, top, col, label):
    lib.draw.roundedRectangle("#00000060", 0, x, y, w, h, 6)
    if len(data) > 1:
        pts = []
        for i, v in enumerate(data):
            pts += [x + 4 + (w - 8) * i / (len(data) - 1), y + h - 4 - (h - 8) * min(1, v / top)]
        lib.draw.polygon([col[0], col[1], col[2], 0.18], 0, *pts, x + w - 4, y + h - 4, x + 4, y + h - 4)
        for i in range(0, len(pts) - 2, 2):
            lib.draw.line(col, 2, pts[i], pts[i + 1], pts[i + 2], pts[i + 3])
    lib.draw.text("#AEB6D4", label, x + 8, y + 4, 12)


def onUpdate(dt):
    global spawning, rate, rk4, big, spawn_acc, fps, step_ms, flip
    if lib.keyPressed("Space"):
        spawning = not spawning
    if lib.keyPressed("KeyK"):
        rk4 = not rk4
        physics.enableRk4(rk4)
    if lib.keyPressed("KeyC"):
        world.clear(keep_static=True)
    if lib.keyPressed("KeyB"):
        big = not big
    if lib.keyPressed("KeyG"):
        flip = -flip
        world.gravity = (0, 900 * flip)
    if lib.keyPressed("Up"):
        rate = min(2000, int(rate * 1.5) + 1)
    if lib.keyPressed("Down"):
        rate = max(1, int(rate / 1.5))
    for n, key in enumerate(("Key1", "Key2", "Key3", "Key4"), 1):
        if lib.keyPressed(key):
            world.substeps = n
    for e in lib.getMouse():
        if e[7] == "Left" and e[8]:
            for _ in range(25):
                spawn(e[1] + lib.rand.float(-20, 20), e[2] + lib.rand.float(-20, 20))

    if spawning:
        spawn_acc += rate * dt
        while spawn_acc >= 1:
            spawn_acc -= 1
            spawn()
    t0 = time.perf_counter()
    world.step(min(dt, 1 / 30))
    step_ms += ((time.perf_counter() - t0) * 1000 - step_ms) * 0.1
    fps += (1 / max(dt, 1e-6) - fps) * 0.08

    if lib.time.frame() % 4 == 0:
        hist_fps.append(fps)
        hist_ms.append(step_ms)
        del hist_fps[:-90], hist_ms[:-90]

    lib.draw.gradient("#10131E", "#1A2035", 0, 0, width, height, math.pi / 2)
    bx, by, bw, bh = box
    lib.draw.roundedRectangle("#00000050", 0, bx, by, bw, bh, 4)
    lib.draw.rectangle("#FFFFFF40", 2, bx - 1, by - 1, bw + 2, bh + 2)
    for b in world.bodies:
        if b.static:
            continue
        col = hsv(b.user["hue"])
        r = b.radius
        lib.draw.circle(col, 0, b.x, b.y, r)
        lib.draw.circle("#FFFFFF45", 0, b.x - r * 0.3, b.y - r * 0.3, r * 0.35)

    # side panel
    lib.draw.roundedRectangle("#00000070", 0, 12, 20, 226, height - 40, 10)
    lib.draw.text("#FFFFFF", "Stress test", 28, 32, 24)
    good = fps > 50
    fcol = [0.45, 1, 0.55] if good else ([1, 0.8, 0.3] if fps > 25 else [1, 0.4, 0.4])
    lib.draw.text(fcol, f"{fps:5.0f} FPS", 28, 72, 40)
    lib.draw.text("#DDE3FF", f"balls     {balls():>6}", 28, 130, 17)
    lib.draw.text("#DDE3FF", f"contacts  {world.contact_count:>6}", 28, 152, 17)
    lib.draw.text("#DDE3FF", f"step      {step_ms:5.1f} ms", 28, 174, 17)
    graph(24, 204, 202, 70, hist_fps, 150, fcol, "fps")
    graph(24, 282, 202, 70, hist_ms, 40, [0.5, 0.7, 1.0], "physics ms")

    def row(y, key, name, state):
        lib.draw.text("#FFD54A", key, 28, y, 16)
        lib.draw.text("#CBD2EE", name, 88, y, 16)
        if isinstance(state, str):
            lib.draw.text("#8E9AC4", state, 224, y + 1, 14, "right")
        else:
            lib.draw.circle([0.4, 1, 0.5] if state else [0.45, 0.45, 0.55], 0, 214, y + 9, 6)

    row(384, "Space", "spawning", spawning)
    row(410, "K", "rk4", rk4)
    row(436, "G", "gravity", "up" if flip < 0 else "down")
    row(462, "B", "big balls", big)
    row(488, "1-4", "substeps", str(world.substeps))
    row(514, "Up/Dn", "rate/s", str(rate))
    row(540, "C", "delete all", "")
    row(566, "Click", "burst of 25", "")
