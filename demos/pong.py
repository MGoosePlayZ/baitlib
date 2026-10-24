# NEON PONG - pong with every effect the draw API can fake without alpha:
# glow (stacked dim shapes), ball trail, sparks, shockwave rings, screen shake, paddle squash,
# synthwave backdrop, chromatic score text, scanlines, procedural sound (lib.sound.tone).
#
# W/S or Up/Down or mouse: move   Space: start / serve   C: toggle scanlines
import math

lib.window.setTitle("BaitLib - neon pong")
lib.window.setSize(1280, 720)
lib.window.setFps(60)

VW, VH = 1600, 900                 # virtual playfield, scaled + centered to fit any window
PAD_W, PAD_H, PAD_X = 20, 150, 70
BALL_R = 14
WIN_SCORE = 7
BG = [0.03, 0.02, 0.07]

width, height = 1280, 720
scale, ox, oy = 0.8, 0, 0
shake = 0.0
shx = shy = 0.0
t = 0.0
scanlines = True


# ---------------------------------------------------------------- helpers
def X(x):
    return ox + shx + x * scale


def Y(y):
    return oy + shy + y * scale


def S(n):
    return n * scale


def mix(a, b, k):
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]


def hsv(h, s=0.8, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, u = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i]


def glow_circle(x, y, r, col, layers=6, spread=0.45):
    """No alpha, so a glow is bigger shapes in colors mixed toward the background, drawn outside-in."""
    for k in range(layers, 0, -1):
        f = k / layers
        lib.draw.circle(mix(BG, col, 0.2 + (1 - f) ** 2 * 0.75), 0, X(x), Y(y), S(r * (1 + spread * k)))
    lib.draw.circle(mix(col, [1, 1, 1], 0.6), 0, X(x), Y(y), S(r))


def glow_rect(x, y, w, h, col, layers=5, spread=7, radius=8):
    for k in range(layers, 0, -1):
        f = k / layers
        g = spread * k
        lib.draw.roundedRectangle(mix(BG, col, 0.2 + (1 - f) ** 2 * 0.75), 0, X(x - g), Y(y - g),
                                  S(w + g * 2), S(h + g * 2), S(radius + g), S(radius + g))
    lib.draw.roundedRectangle(col, 0, X(x), Y(y), S(w), S(h), S(radius), S(radius))
    lib.draw.roundedRectangle(mix(col, [1, 1, 1], 0.7), 0, X(x + w * 0.25), Y(y + 6), S(w * 0.5), S(h - 12),
                              S(radius * 0.5), S(radius * 0.5))


def sfx(length, freq, kind="square", vol=0.25, attack=0.002, release=0.06, pitch=1.0):
    lib.sound.play(lib.sound.tone(length, freq, kind, attack, release), False, vol, 1.0, pitch)


pending = []


def later(delay, fn):
    pending.append([delay, fn])


# ---------------------------------------------------------------- state
class Paddle:
    def __init__(self, x, col):
        self.x, self.y, self.col = x, VH / 2, col
        self.vy = 0.0
        self.squash = 0.0
        self.score = 0


player = Paddle(PAD_X, [0.1, 0.9, 1.0])
cpu = Paddle(VW - PAD_X - PAD_W, [1.0, 0.25, 0.7])
bx = by = bvx = bvy = 0.0
rally = 0
trail = []          # (x, y)
sparks = []         # [x, y, vx, vy, life, maxlife, color]
rings = []          # [x, y, r, life, color]
state = "title"     # title | serve | play | over
serve_t = 0.0
flash = 0.0
flash_col = [1, 1, 1]
winner = None
mouse_mode = False
last_mouse = (0, 0)
stars = [[lib.rand.float(0, VW), lib.rand.float(0, VH), lib.rand.float(0.2, 1.0)] for _ in range(90)]


def add_sparks(x, y, col, n, speed=500, spread=math.pi * 2, angle=0.0):
    for _ in range(n):
        a = angle + lib.rand.float(-spread / 2, spread / 2)
        v = lib.rand.float(0.2, 1.0) * speed
        life = lib.rand.float(0.25, 0.7)
        sparks.append([x, y, math.cos(a) * v, math.sin(a) * v, life, life, col])


def add_ring(x, y, col, r=10):
    rings.append([x, y, r, 0.45, col])


def serve(direction):
    global bx, by, bvx, bvy, rally, state, serve_t
    bx, by, rally = VW / 2, VH / 2, 0
    a = lib.rand.float(-0.4, 0.4)
    bvx, bvy = math.cos(a) * 620 * direction, math.sin(a) * 620
    trail.clear()
    state, serve_t = "serve", 1.1


def reset_match():
    global winner
    player.score = cpu.score = 0
    winner = None
    serve(1 if lib.rand.int(0, 1) else -1)


def hit_paddle(p, direction):
    global bvx, bvy, rally, shake, flash, flash_col
    rally += 1
    off = (by - p.y) / (PAD_H / 2)                 # -1 top .. 1 bottom
    off = lib.clamp(off, -1, 1)
    speed = min(620 + rally * 38, 1500)
    ang = off * 0.95
    bvx, bvy = math.cos(ang) * speed * direction, math.sin(ang) * speed
    p.squash = 1.0
    shake = min(6 + rally * 1.5, 22)
    flash, flash_col = 0.25, mix(p.col, [1, 1, 1], 0.4)
    add_sparks(bx, by, p.col, 26, 600 + rally * 30, 2.6, 0 if direction > 0 else math.pi)
    add_sparks(bx, by, [1, 1, 1], 8, 400, 2.6, 0 if direction > 0 else math.pi)
    add_ring(bx, by, p.col)
    sfx(0.09, 330 * 2 ** (min(rally, 14) / 12), "square", 0.22)      # climbs a semitone per hit
    sfx(0.05, 0, "noise", 0.12, 0.001, 0.045)


def score(p, other_dir):
    global shake, flash, flash_col, state, winner
    p.score += 1
    shake, flash, flash_col = 28, 0.5, p.col
    add_sparks(bx, by, p.col, 90, 900)
    for i in range(3):
        add_ring(bx, by, p.col, 10 + i * 30)
    for i, n in enumerate((0, 4, 7, 12)):                              # little arpeggio
        later(i * 0.07, lambda n=n: sfx(0.18, 392 * 2 ** (n / 12), "triangle", 0.28, 0.003, 0.14))
    if p.score >= WIN_SCORE:
        winner, state = p, "over"
        for i, n in enumerate((0, 4, 7, 12, 16, 19, 24)):
            later(0.3 + i * 0.09, lambda n=n: sfx(0.3, 262 * 2 ** (n / 12), "sawtooth", 0.18, 0.003, 0.25))
    else:
        serve(other_dir)


# ---------------------------------------------------------------- update
def move_paddles(dt):
    global mouse_mode, last_mouse
    mp = lib.getMousePos()
    if abs(mp[0] - last_mouse[0]) + abs(mp[1] - last_mouse[1]) > 2:
        mouse_mode = True
    last_mouse = tuple(mp)
    up = lib.keyDown("KeyW") is not None or lib.keyDown("Up") is not None
    down = lib.keyDown("KeyS") is not None or lib.keyDown("Down") is not None
    if up or down:
        mouse_mode = False
    old = player.y
    if mouse_mode:
        target = (mp[1] - oy) / scale
        player.y += lib.clamp(target - player.y, -1400 * dt, 1400 * dt)
    else:
        player.y += ((1 if down else 0) - (1 if up else 0)) * 900 * dt
    player.y = lib.clamp(player.y, PAD_H / 2, VH - PAD_H / 2)
    player.vy = (player.y - old) / max(dt, 1e-6)

    # cpu: tracks the ball with reaction lag and a speed cap so it can lose
    old = cpu.y
    if state == "play" and bvx > 0:
        target = by + math.sin(t * 2.1) * 55
    else:
        target = VH / 2
    cpu.y += lib.clamp(target - cpu.y, -(430 + rally * 12) * dt, (430 + rally * 12) * dt)
    cpu.y = lib.clamp(cpu.y, PAD_H / 2, VH - PAD_H / 2)
    cpu.vy = (cpu.y - old) / max(dt, 1e-6)
    for p in (player, cpu):
        p.squash = max(0.0, p.squash - dt * 4)


def move_ball(dt):
    global bx, by, bvx, bvy, shake
    steps = max(1, int(math.hypot(bvx, bvy) * dt / 10))
    for _ in range(steps):
        bx += bvx * dt / steps
        by += bvy * dt / steps
        if by < BALL_R or by > VH - BALL_R:
            by = lib.clamp(by, BALL_R, VH - BALL_R)
            bvy = -bvy
            shake = max(shake, 5)
            add_sparks(bx, by, [0.6, 0.6, 1.0], 12, 300, 2.5, math.pi / 2 if by < VH / 2 else -math.pi / 2)
            add_ring(bx, by, [0.6, 0.6, 1.0], 6)
            sfx(0.06, 196, "triangle", 0.2)
        # circle vs paddle rect through the library's collision query
        if bvx < 0 and lib.collision.query(["circle", bx, by, BALL_R],
                                           ["rect", player.x, player.y - PAD_H / 2, PAD_W, PAD_H]):
            bx = player.x + PAD_W + BALL_R
            hit_paddle(player, 1)
        elif bvx > 0 and lib.collision.query(["circle", bx, by, BALL_R],
                                             ["rect", cpu.x, cpu.y - PAD_H / 2, PAD_W, PAD_H]):
            bx = cpu.x - BALL_R
            hit_paddle(cpu, -1)
    if bx < -40:
        score(cpu, 1)
    elif bx > VW + 40:
        score(player, -1)


def onResize(w, h):
    global width, height, scale, ox, oy
    width, height = w, h
    scale = min(w / VW, h / VH)
    ox, oy = (w - VW * scale) / 2, (h - VH * scale) / 2


def onUpdate(dt):
    global t, shake, shx, shy, flash, state, serve_t, scanlines
    dt = min(dt, 1 / 30)
    t += dt
    if lib.keyPressed("KeyC"):
        scanlines = not scanlines
    if lib.keyPressed("Space") and state in ("title", "over"):
        reset_match()
    for p in pending[:]:
        p[0] -= dt
        if p[0] <= 0:
            pending.remove(p)
            p[1]()

    move_paddles(dt)
    if state == "serve":
        serve_t -= dt
        if serve_t <= 0:
            state = "play"
            sfx(0.12, 523, "square", 0.2)
    elif state == "play":
        move_ball(dt)
        trail.append((bx, by))
        if len(trail) > 26:
            trail.pop(0)

    for s in sparks[:]:
        s[0] += s[2] * dt
        s[1] += s[3] * dt
        s[2] *= 1 - 2.2 * dt
        s[3] *= 1 - 2.2 * dt
        s[4] -= dt
        if s[4] <= 0:
            sparks.remove(s)
    for r in rings[:]:
        r[2] += 700 * dt
        r[3] -= dt
        if r[3] <= 0:
            rings.remove(r)
    shake = max(0.0, shake - 60 * dt)
    shx, shy = lib.rand.float(-shake, shake) * scale, lib.rand.float(-shake, shake) * scale
    flash = max(0.0, flash - dt * 2.5)
    draw_scene()


# ---------------------------------------------------------------- drawing
def draw_backdrop():
    lib.draw.rectangle(BG, 0, 0, 0, width, height)
    for s in stars:                                              # parallax starfield
        s[0] = (s[0] - 18 * s[2] * (1 / 60)) % VW
        tw = 0.5 + 0.5 * math.sin(t * 2 + s[1])
        lib.draw.circle(mix(BG, [1, 1, 1], 0.25 + 0.5 * s[2] * tw), 0, X(s[0]), Y(s[1]), S(1 + 1.6 * s[2]))
    horizon = 520
    # striped sun
    for i in range(12):
        top = horizon - 300 + i * 25
        h = 25 - i * 1.6
        if h > 1:
            w = math.sqrt(max(0, 150 ** 2 - (top + h / 2 - (horizon - 150)) ** 2))
            lib.draw.rectangle(mix(BG, [1.0, 0.3 + i * 0.04, 0.5], 0.28), 0, X(VW / 2 - w), Y(top), S(w * 2), S(h))
    # perspective grid, scrolling toward the viewer
    gcol = mix(BG, [0.7, 0.2, 1.0], 0.35)
    lib.draw.rectangle(mix(BG, [0.2, 0.05, 0.4], 0.35), 0, X(0), Y(horizon), S(VW), S(VH - horizon))
    for i in range(-14, 15):
        x0 = VW / 2 + i * 22
        x1 = VW / 2 + i * 150
        lib.draw.line(gcol, 1, X(x0), Y(horizon), X(x1), Y(VH))
    for i in range(10):
        f = ((i + t * 0.6) % 10) / 10
        y = horizon + (VH - horizon) * f ** 2
        lib.draw.line(gcol, 1, X(0), Y(y), X(VW), Y(y))
    # arena frame
    lib.draw.rectangle(mix(BG, [0.5, 0.5, 1.0], 0.5), 2, X(4), Y(4), S(VW - 8), S(VH - 8))
    for i in range(0, VH, 50):                                    # dashed centre line
        lib.draw.rectangle(mix(BG, [1, 1, 1], 0.25 + 0.1 * math.sin(t * 3 + i)), 0, X(VW / 2 - 3), Y(i + 10), S(6), S(28))


def big_text(txt, x, y, size, col, ha="center", va="middle"):
    """Chromatic aberration: red + cyan copies offset behind the real text."""
    d = S(3 + 5 * flash + shake * 0.15)
    lib.draw.text([1, 0.1, 0.2], txt, X(x) - d, Y(y), S(size), ha, va)
    lib.draw.text([0.1, 0.9, 1.0], txt, X(x) + d, Y(y), S(size), ha, va)
    lib.draw.text(col, txt, X(x), Y(y), S(size), ha, va)


def draw_scene():
    draw_backdrop()

    big_text(str(player.score), VW / 2 - 200, 110, 150, mix(player.col, [1, 1, 1], 0.5))
    big_text(str(cpu.score), VW / 2 + 200, 110, 150, mix(cpu.col, [1, 1, 1], 0.5))

    for r in rings:                                               # shockwaves
        k = r[3] / 0.45
        lib.draw.circle(mix(BG, r[4], k), max(1, round(4 * k)), X(r[0]), Y(r[1]), S(r[2]))

    for p in (player, cpu):                                       # paddles, squash + stretch
        sq = p.squash
        w = PAD_W * (1 + 0.6 * sq)
        h = PAD_H * (1 - 0.08 * sq) + abs(p.vy) * 0.04
        glow_rect(p.x - (w - PAD_W) / 2, p.y - h / 2, w, h, p.col)

    if state in ("play", "serve"):
        speed = math.hypot(bvx, bvy)
        col = hsv((0.5 + speed / 3000) % 1, 0.7, 1.0)             # ball hue follows speed
        for i, (tx, ty) in enumerate(trail):                      # comet trail
            f = (i + 1) / len(trail)
            lib.draw.circle(mix(BG, col, 0.2 + f * 0.6), 0, X(tx), Y(ty), S(BALL_R * (0.3 + 0.7 * f)))
        pulse = 1 + (0.25 * math.sin(t * 30) if state == "serve" else 0)
        glow_circle(bx, by, BALL_R * pulse, col)

    for s in sparks:                                              # sparks as streaks
        f = s[4] / s[5]
        lib.draw.line(mix(BG, s[6], f), 2, X(s[0]), Y(s[1]), X(s[0] - s[2] * 0.03), Y(s[1] - s[3] * 0.03))

    if flash > 0:                                                 # edge flash
        e = 40 * flash / 0.5
        c = mix(BG, flash_col, min(1, flash * 1.6))
        lib.draw.rectangle(c, 0, 0, 0, width, e)
        lib.draw.rectangle(c, 0, 0, height - e, width, e)

    if state == "title":
        big_text("NEON PONG", VW / 2, 330, 120, [1, 1, 1])
        lib.draw.text(mix(BG, [1, 1, 1], 0.6 + 0.4 * math.sin(t * 4)), "press SPACE", X(VW / 2), Y(470), S(36), "center", "middle")
        lib.draw.text("#8899bb", "W/S, arrows or mouse to move   first to 7   C: scanlines", X(VW / 2), Y(540), S(24), "center", "middle")
    elif state == "serve":
        n = max(1, math.ceil(serve_t / 0.37))
        lib.draw.text([1, 1, 1], str(n), X(VW / 2), Y(VH / 2 - 90), S(70 + (serve_t % 0.37) * 100), "center", "middle")
    elif state == "over":
        who = "YOU WIN" if winner is player else "CPU WINS"
        big_text(who, VW / 2, 330, 130, mix(winner.col, [1, 1, 1], 0.4))
        lib.draw.text(mix(BG, [1, 1, 1], 0.6 + 0.4 * math.sin(t * 4)), "SPACE to play again", X(VW / 2), Y(470), S(34), "center", "middle")

    if rally > 2 and state == "play":                             # rally counter
        lib.draw.text(mix(BG, [1, 0.9, 0.3], 0.8), f"RALLY {rally}", X(VW / 2), Y(VH - 40), S(30 + min(rally, 20)), "center", "middle")

    if scanlines:                                                 # CRT look
        for y in range(0, height, 4):
            lib.draw.rectangle(0x000000, 0, 0, y, width, 1)
    # letterbox bars hide the shake offset outside the arena
    if ox > 1:
        lib.draw.rectangle(0x000000, 0, 0, 0, ox, height)
        lib.draw.rectangle(0x000000, 0, width - ox, 0, ox + 1, height)
    if oy > 1:
        lib.draw.rectangle(0x000000, 0, 0, 0, width, oy)
        lib.draw.rectangle(0x000000, 0, 0, height - oy, width, oy + 1)
