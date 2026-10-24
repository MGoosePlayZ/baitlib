# ENDLESS - an infinite roguelike in one file.
# The map is generated lazily, one 24x24 region at a time: each region owns a room plus
# corridors to its east and south neighbours, all derived from (seed, region) so any part of the
# world can be rebuilt on demand. Enemies heal you when they die, and they get tougher and more
# frequent the longer you survive. There is no ending.
#
# WASD/arrows: move   Mouse / Left click or Space: slash toward the cursor   R: restart when dead
#
# Physics: lib.collision.query is used for wall pushout, sword hits, projectile hits, contact damage
# and enemy line of sight (a ray against every wall tile near the path).
import math
import random

lib.window.setTitle("BaitLib - ENDLESS")
lib.window.setSize(1100, 700)
lib.window.setFps(60)

R = 24                      # region size in tiles
LIGHT = 9.0                 # light radius in tiles
SPEED = 5.2
PLAYER_R = 0.32
SLASH_DMG = 3.0
width, height, unit = 1100, 700, 700
ts = 50.0                   # tile size in pixels
shx = shy = 0.0


class G:                    # all game state lives here so reset() is one function
    pass


regions = {}                # (rx, ry) -> set of floor tiles that region carved
room_cache = {}
fcache = {}                 # (x, y) -> bool, rebuilt after pruning


# ---------------------------------------------------------------- helpers
def mix(a, b, k):
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]


def hsv(h, s=0.8, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, u = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i]


def snd(length, freq, kind="square", vol=0.2, attack=0.002, release=0.05, pitch=1.0):
    lib.sound.play(lib.sound.tone(length, freq, kind, attack, release), False, vol, 1.0, pitch)


def difficulty():
    return 1 + G.t / 40


# ---------------------------------------------------------------- world generation
def room_of(rx, ry):
    k = (G.seed, rx, ry)
    if k not in room_cache:
        r = random.Random(f"{G.seed}:{rx}:{ry}")
        w, h = r.randint(5, 12), r.randint(5, 11)
        x = rx * R + r.randint(2, R - w - 2)
        y = ry * R + r.randint(2, R - h - 2)
        room_cache[k] = (x, y, w, h, r)
    return room_cache[k]


def carve(rx, ry):
    x, y, w, h, _ = room_of(rx, ry)
    r = random.Random(f"carve:{G.seed}:{rx}:{ry}")
    tiles = {(i, j) for i in range(x, x + w) for j in range(y, y + h)}
    cx, cy = x + w // 2, y + h // 2
    if w >= 8 and h >= 7:                       # pillars, kept off the centre row/column
        for _ in range(r.randint(0, 4)):
            px, py = r.randint(x + 1, x + w - 2), r.randint(y + 1, y + h - 2)
            if abs(px - cx) > 1 and abs(py - cy) > 1:
                tiles.discard((px, py))
    wide = r.random() < 0.3

    def add(i, j, horizontal):
        tiles.add((i, j))
        if wide:
            tiles.add((i, j + 1) if horizontal else (i + 1, j))

    ex, ey, ew, eh, _ = room_of(rx + 1, ry)     # corridor east: along our row, then up/down at theirs
    bx, by = ex + ew // 2, ey + eh // 2
    for i in range(min(cx, bx), max(cx, bx) + 1):
        add(i, cy, True)
    for j in range(min(cy, by), max(cy, by) + 1):
        add(bx, j, False)
    sx, sy, sw, sh, _ = room_of(rx, ry + 1)     # corridor south: down our column, then along theirs
    bx, by = sx + sw // 2, sy + sh // 2
    for j in range(min(cy, by), max(cy, by) + 1):
        add(cx, j, False)
    for i in range(min(cx, bx), max(cx, bx) + 1):
        add(i, by, True)
    return tiles


def region(rx, ry):
    s = regions.get((rx, ry))
    if s is None:
        s = regions[(rx, ry)] = carve(rx, ry)
    return s


def is_floor(x, y):
    k = (x, y)
    v = fcache.get(k)
    if v is None:
        rx, ry = x // R, y // R
        # only this region, the one to the west (its east corridor) and north (its south corridor)
        # can reach into this tile
        v = k in region(rx, ry) or k in region(rx - 1, ry) or k in region(rx, ry - 1)
        fcache[k] = v
    return v


def prune():
    prx, pry = int(G.px // R), int(G.py // R)
    if len(regions) > 90:
        for k in [k for k in regions if max(abs(k[0] - prx), abs(k[1] - pry)) > 4]:
            del regions[k]
        fcache.clear()


def resolve(x, y, r):
    """Push a circle out of solid tiles. Uses lib.collision.query as the overlap test."""
    for _ in range(2):
        for ty in range(math.floor(y - r), math.floor(y + r) + 1):
            for tx in range(math.floor(x - r), math.floor(x + r) + 1):
                if is_floor(tx, ty) or not lib.collision.query(["circle", x, y, r], ["rect", tx, ty, 1, 1]):
                    continue
                cx, cy = lib.clamp(x, tx, tx + 1), lib.clamp(y, ty, ty + 1)
                dx, dy = x - cx, y - cy
                d = math.hypot(dx, dy)
                if d > 1e-6:
                    k = (r - d) / d
                    x, y = x + dx * k, y + dy * k
                else:                                  # centre is inside the tile: leave by the nearest edge
                    gaps = [(x - tx, -1, 0), (tx + 1 - x, 1, 0), (y - ty, 0, -1), (ty + 1 - y, 0, 1)]
                    g, sx, sy = min(gaps)
                    x, y = x + sx * (g + r), y + sy * (g + r)
    return x, y


def clear_los(x1, y1, x2, y2):
    for ty in range(math.floor(min(y1, y2)), math.floor(max(y1, y2)) + 1):
        for tx in range(math.floor(min(x1, x2)), math.floor(max(x1, x2)) + 1):
            if not is_floor(tx, ty) and lib.collision.query(["ray", x1, y1, x2, y2], ["rect", tx, ty, 1, 1]):
                return False
    return True


# ---------------------------------------------------------------- entities
KINDS = {  # radius, hp, speed, damage, heal, color
    "grunt": (0.30, 4.0, 2.1, 6.0, 8, 0.33),
    "spitter": (0.28, 3.0, 1.7, 7.0, 10, 0.78),
    "brute": (0.50, 14.0, 1.4, 14.0, 25, 0.06),
}


class Enemy:
    def __init__(self, kind, x, y):
        diff = difficulty()
        r, hp, sp, dmg, heal, hue = KINDS[kind]
        sc = 1 + 0.18 * (diff - 1)
        self.kind, self.x, self.y, self.r = kind, x, y, r
        self.hp = self.maxhp = hp * sc
        self.speed = sp + min(1.8, 0.1 * (diff - 1))
        self.dmg = dmg * (1 + 0.12 * (diff - 1))
        self.heal, self.hue = heal, hue
        self.cd = 1.0
        self.los, self.los_t, self.seen = False, lib.rand.float(0, 0.3), None
        self.wx = self.wy = 0.0
        self.wt = 0.0
        self.kx = self.ky = 0.0          # knockback velocity
        self.flash = 0.0
        self.phase = lib.rand.float(0, 6.28)


def spawn():
    diff = difficulty()
    if len(G.enemies) >= min(45, 5 + diff * 2.2):
        return
    for _ in range(14):
        a, d = lib.rand.float(0, math.tau), lib.rand.float(8, 13)
        tx, ty = math.floor(G.px + math.cos(a) * d), math.floor(G.py + math.sin(a) * d)
        if is_floor(tx, ty):
            roll = lib.rand.float(0, 1)
            kind = "brute" if diff >= 4 and roll < 0.12 else "spitter" if diff >= 2.2 and roll < 0.38 else "grunt"
            G.enemies.append(Enemy(kind, tx + 0.5, ty + 0.5))
            return


def burst(x, y, col, n, speed=3.0, life=0.5):
    for _ in range(n):
        a, v = lib.rand.float(0, math.tau), lib.rand.float(0.3, 1.0) * speed
        l = lib.rand.float(0.5, 1.0) * life
        G.parts.append([x, y, math.cos(a) * v, math.sin(a) * v, l, l, col])


def popup(x, y, text, col):
    G.texts.append([x, y, text, 0.8, col])


def hurt_player(amount, fx, fy):
    if G.hurt > 0 or G.dead:
        return
    G.hp -= amount
    G.hurt = 0.55
    G.shake = 12
    dx, dy = G.px - fx, G.py - fy
    d = math.hypot(dx, dy) or 1
    G.kx, G.ky = dx / d * 7, dy / d * 7
    popup(G.px, G.py - 0.4, f"-{amount:.0f}", [1, 0.35, 0.35])
    burst(G.px, G.py, [1, 0.3, 0.3], 14, 4)
    snd(0.22, 150, "sawtooth", 0.3, 0.002, 0.2)
    if G.hp <= 0:
        G.hp, G.dead = 0, True
        burst(G.px, G.py, [1, 1, 1], 60, 6, 1.0)
        for i, n in enumerate((0, -3, -7, -12)):
            snd(0.35, 330 * 2 ** (n / 12), "triangle", 0.3, 0.003, 0.3, 1.0)


def kill(e):
    G.kills += 1
    G.enemies.remove(e)
    healed = min(e.heal, G.maxhp - G.hp)
    G.hp += healed
    burst(e.x, e.y, hsv(e.hue, 0.7, 1.0), 22, 4.5, 0.6)
    burst(e.x, e.y, [0.4, 1.0, 0.5], 8, 2.5, 0.9)
    popup(e.x, e.y - 0.3, f"+{e.heal}", [0.4, 1.0, 0.5])
    G.shake = max(G.shake, 5)
    snd(0.1, 392, "triangle", 0.25)
    snd(0.12, 587, "triangle", 0.2, 0.002, 0.1)


def slash():
    G.atk_cd = 0.28
    a = G.aim
    cx, cy = G.px + math.cos(a) * 0.75, G.py + math.sin(a) * 0.75
    G.slashes.append([G.px, G.py, a, 0.16])
    snd(0.07, 0, "noise", 0.16, 0.001, 0.06)
    for e in G.enemies[:]:
        if lib.collision.query(["circle", cx, cy, 0.95], ["circle", e.x, e.y, e.r]):
            e.hp -= SLASH_DMG
            e.flash = 0.12
            d = math.hypot(e.x - G.px, e.y - G.py) or 1
            e.kx, e.ky = (e.x - G.px) / d * 6, (e.y - G.py) / d * 6
            burst(e.x, e.y, [1, 1, 0.8], 6, 3, 0.25)
            snd(0.05, 210, "square", 0.18)
            if e.hp <= 0:
                kill(e)


# ---------------------------------------------------------------- game flow
def reset():
    G.seed = lib.rand.int(1, 10 ** 9)
    regions.clear()
    fcache.clear()
    room_cache.clear()
    x, y, w, h, _ = room_of(0, 0)
    G.px, G.py = x + w // 2 + 0.5, y + h // 2 + 0.5
    G.cam_x, G.cam_y = G.px, G.py
    G.hp = G.maxhp = 100.0
    G.t = G.hurt = G.atk_cd = G.shake = G.hb = 0.0
    G.kx = G.ky = 0.0
    G.kills, G.dead, G.aim = 0, False, 0.0
    G.spawn_t = 1.5
    G.enemies, G.shots, G.parts, G.texts, G.slashes = [], [], [], [], []


reset()


def update_enemy(e, dt):
    e.flash = max(0.0, e.flash - dt)
    e.cd -= dt
    dx, dy = G.px - e.x, G.py - e.y
    d = math.hypot(dx, dy) or 1e-6
    e.los_t -= dt
    if e.los_t <= 0:
        e.los_t = 0.18 + lib.rand.float(0, 0.12)
        e.los = d < 14 and clear_los(e.x, e.y, G.px, G.py)
        if e.los:
            e.seen = (G.px, G.py)

    mx = my = 0.0
    if e.los:
        ux, uy = dx / d, dy / d
        if e.kind == "spitter":
            if d < 4.5:
                mx, my = -ux, -uy
            elif d > 6.5:
                mx, my = ux, uy
            else:                                        # circle-strafe at range
                mx, my = -uy * math.sin(G.t + e.phase), ux * math.sin(G.t + e.phase)
            if e.cd <= 0 and d < 10:
                e.cd = max(0.9, 2.2 - 0.05 * (difficulty() - 1))
                a = math.atan2(dy, dx) + lib.rand.float(-0.08, 0.08)
                G.shots.append([e.x, e.y, math.cos(a) * 6.5, math.sin(a) * 6.5, 2.5, e.dmg])
                snd(0.08, 520, "square", 0.12, 0.002, 0.07, 0.8)
        else:
            mx, my = ux, uy
    elif e.seen:
        sx, sy = e.seen[0] - e.x, e.seen[1] - e.y
        sd = math.hypot(sx, sy)
        if sd < 0.4:
            e.seen = None
        else:
            mx, my = sx / sd, sy / sd
    else:
        e.wt -= dt
        if e.wt <= 0:
            e.wt = lib.rand.float(0.8, 2.0)
            e.wx, e.wy = lib.rand.choice((1, 0, 0, -1, 0)), lib.rand.choice((0, 1, -1, 0, 0))
        mx, my = e.wx * 0.4, e.wy * 0.4

    for o in G.enemies:                                  # separation, so they don't stack
        if o is not e:
            ox, oy = e.x - o.x, e.y - o.y
            if abs(ox) < 0.8 and abs(oy) < 0.8:
                od = math.hypot(ox, oy) or 1e-6
                if od < 0.7:
                    mx += ox / od * 0.6
                    my += oy / od * 0.6

    e.x += (mx * e.speed + e.kx) * dt
    e.y += (my * e.speed + e.ky) * dt
    e.kx *= 1 - 9 * dt
    e.ky *= 1 - 9 * dt
    e.x, e.y = resolve(e.x, e.y, e.r)

    if e.kind != "spitter" and e.cd <= 0 and lib.collision.query(["circle", e.x, e.y, e.r],
                                                                  ["circle", G.px, G.py, PLAYER_R]):
        e.cd = 0.8
        hurt_player(e.dmg, e.x, e.y)


def update(dt):
    G.t += dt
    G.atk_cd -= dt
    G.hurt = max(0.0, G.hurt - dt)
    G.shake = max(0.0, G.shake - 30 * dt)

    # aim from the cursor, in world space
    mp = lib.getMousePos()
    wx, wy = G.cam_x + (mp[0] - width / 2) / ts, G.cam_y + (mp[1] - height / 2) / ts
    G.aim = math.atan2(wy - G.py, wx - G.px)

    if not G.dead:
        dx = (lib.keyDown("KeyD") is not None or lib.keyDown("Right") is not None) - \
             (lib.keyDown("KeyA") is not None or lib.keyDown("Left") is not None)
        dy = (lib.keyDown("KeyS") is not None or lib.keyDown("Down") is not None) - \
             (lib.keyDown("KeyW") is not None or lib.keyDown("Up") is not None)
        n = math.hypot(dx, dy) or 1
        G.px += (dx / n * SPEED + G.kx) * dt
        G.py += (dy / n * SPEED + G.ky) * dt
        G.kx *= 1 - 9 * dt
        G.ky *= 1 - 9 * dt
        G.px, G.py = resolve(G.px, G.py, PLAYER_R)

        attacking = any(e[7] == "Left" for e in lib.getMouse()) or lib.keyDown("Space") is not None
        if attacking and G.atk_cd <= 0:
            slash()

        G.spawn_t -= dt
        if G.spawn_t <= 0:
            G.spawn_t = max(0.45, 3.5 * 0.93 ** (G.t / 10))
            spawn()
        for e in G.enemies[:]:
            update_enemy(e, dt)

        if G.hp < 30:                                    # heartbeat
            G.hb -= dt
            if G.hb <= 0:
                G.hb = 0.75
                snd(0.14, 55, "sine", 0.45, 0.01, 0.1)

    for s in G.shots[:]:                                 # enemy projectiles
        s[0] += s[2] * dt
        s[1] += s[3] * dt
        s[4] -= dt
        if s[4] <= 0 or not is_floor(math.floor(s[0]), math.floor(s[1])):
            G.shots.remove(s)
            burst(s[0], s[1], [0.9, 0.4, 1.0], 5, 2, 0.25)
        elif not G.dead and lib.collision.query(["circle", s[0], s[1], 0.16], ["circle", G.px, G.py, PLAYER_R]):
            G.shots.remove(s)
            hurt_player(s[5], s[0] - s[2] * 0.1, s[1] - s[3] * 0.1)

    for p in G.parts[:]:
        p[0] += p[2] * dt
        p[1] += p[3] * dt
        p[2] *= 1 - 3 * dt
        p[3] *= 1 - 3 * dt
        p[4] -= dt
        if p[4] <= 0:
            G.parts.remove(p)
    for t in G.texts[:]:
        t[1] -= 1.2 * dt
        t[3] -= dt
        if t[3] <= 0:
            G.texts.remove(t)
    for s in G.slashes[:]:
        s[3] -= dt
        if s[3] <= 0:
            G.slashes.remove(s)

    G.cam_x += (G.px - G.cam_x) * min(1, dt * 8)
    G.cam_y += (G.py - G.cam_y) * min(1, dt * 8)
    prune()


# ---------------------------------------------------------------- drawing
def S(x, y):
    return width / 2 + (x - G.cam_x) * ts + shx, height / 2 + (y - G.cam_y) * ts + shy


def draw_world():
    light = LIGHT + math.sin(G.t * 7) * 0.12
    l2 = light * light
    x0, x1 = math.floor(G.cam_x - width / 2 / ts) - 1, math.ceil(G.cam_x + width / 2 / ts) + 1
    y0, y1 = math.floor(G.cam_y - height / 2 / ts) - 1, math.ceil(G.cam_y + height / 2 / ts) + 1
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            d2 = (tx + 0.5 - G.px) ** 2 + (ty + 0.5 - G.py) ** 2
            if d2 > l2:
                continue
            b = 0.2 + 0.8 * (1 - d2 / l2)
            sx, sy = S(tx, ty)
            sx, sy = round(sx), round(sy)
            w, h = round(sx + ts) - sx, round(sy + ts) - sy
            if is_floor(tx, ty):
                tint = hsv(((tx // R * 31 + ty // R * 17) % 100) / 100, 0.35, 0.26 + 0.03 * ((tx * 7 + ty * 13) % 5))
                lib.draw.rectangle([c * b for c in tint], 0, sx, sy, w, h)
            elif any(is_floor(tx + i, ty + j) for i in (-1, 0, 1) for j in (-1, 0, 1)):
                base = [0.45, 0.38, 0.55]
                lib.draw.rectangle([c * b for c in base], 0, sx, sy, w, h)
                if is_floor(tx, ty + 1):
                    lib.draw.rectangle([c * b for c in [0.65, 0.55, 0.78]], 0, sx, sy + h * 0.7, w, h * 0.3)
                if is_floor(tx, ty - 1):
                    lib.draw.rectangle([c * b for c in [0.3, 0.25, 0.38]], 0, sx, sy, w, h * 0.25)


def draw_entities():
    light2 = LIGHT * LIGHT
    for e in G.enemies:
        d = math.hypot(e.x - G.px, e.y - G.py)
        if d > LIGHT - 1 or not (e.los or d < 2.5):
            continue
        sx, sy = S(e.x, e.y)
        r = e.r * ts
        col = [1, 1, 1] if e.flash > 0 else hsv(e.hue, 0.7, 0.95)
        lib.draw.ellipse(0x000000, 0, sx - r, sy + r * 0.5, r * 2, r * 0.9)           # shadow
        bob = math.sin(G.t * 8 + e.phase) * r * 0.08
        lib.draw.circle(col, 0, sx, sy + bob, r)
        lib.draw.circle(mix(col, [0, 0, 0], 0.45), max(1, round(ts * 0.04)), sx, sy + bob, r)
        ang = math.atan2(G.py - e.y, G.px - e.x)
        for side in (-1, 1):                                                          # eyes look at you
            ex = sx + math.cos(ang) * r * 0.35 - math.sin(ang) * side * r * 0.35
            ey = sy + bob + math.sin(ang) * r * 0.35 + math.cos(ang) * side * r * 0.35
            lib.draw.circle(0xFFFFFF, 0, ex, ey, r * 0.24)
            lib.draw.circle(0x101010, 0, ex + math.cos(ang) * r * 0.08, ey + math.sin(ang) * r * 0.08, r * 0.12)
        if e.kind == "spitter":
            lib.draw.circle([0.9, 0.5, 1.0], 0, sx, sy + bob - r * 0.9, r * 0.2)
        if e.hp < e.maxhp:
            lib.draw.rectangle(0x200000, 0, sx - r, sy - r - 8, r * 2, 4)
            lib.draw.rectangle(0xFF4040, 0, sx - r, sy - r - 8, r * 2 * e.hp / e.maxhp, 4)

    for s in G.shots:
        sx, sy = S(s[0], s[1])
        lib.draw.circle([0.5, 0.2, 0.7], 0, sx, sy, ts * 0.2)
        lib.draw.circle([0.95, 0.7, 1.0], 0, sx, sy, ts * 0.11)

    sx, sy = S(G.px, G.py)
    r = PLAYER_R * ts
    if not G.dead and not (G.hurt > 0 and int(G.t * 30) % 2):
        lib.draw.ellipse(0x000000, 0, sx - r, sy + r * 0.5, r * 2, r * 0.9)
        lib.draw.circle([0.35, 0.8, 1.0], 0, sx, sy, r)
        lib.draw.circle(0xFFFFFF, max(1, round(ts * 0.04)), sx, sy, r)
        lib.draw.circle(0xFFFFFF, 0, sx + math.cos(G.aim) * r * 0.55, sy + math.sin(G.aim) * r * 0.55, r * 0.3)

    for s in G.slashes:                                   # sword arc, shrinking + fading
        k = s[3] / 0.16
        pts = []
        for i in range(11):
            a = s[2] - 0.9 + 1.8 * i / 10
            pts.append(S(s[0] + math.cos(a) * (0.45 + 0.7 * (1 - k)), s[1] + math.sin(a) * (0.45 + 0.7 * (1 - k))))
        for i in range(10, -1, -1):
            a = s[2] - 0.9 + 1.8 * i / 10
            pts.append(S(s[0] + math.cos(a) * (0.9 + 0.35 * (1 - k)), s[1] + math.sin(a) * (0.9 + 0.35 * (1 - k))))
        lib.draw.polygon(mix([0.2, 0.2, 0.3], [1, 1, 1], k), 0, *[c for p in pts for c in p])

    for p in G.parts:
        sx, sy = S(p[0], p[1])
        lib.draw.circle(mix([0, 0, 0], p[6], p[4] / p[5]), 0, sx, sy, max(1, ts * 0.07 * p[4] / p[5] * 2))
    for t in G.texts:
        sx, sy = S(t[0], t[1])
        lib.draw.text(0x000000, t[2], sx + 1, sy + 1, ts * 0.5, "center", "middle")
        lib.draw.text(t[4], t[2], sx, sy, ts * 0.5, "center", "middle")


def draw_hud():
    s = unit * 0.03
    bw, bh = width * 0.28, unit * 0.035
    x, y = width * 0.025, height * 0.03
    lib.draw.roundedRectangle(0x000000, 0, x - 3, y - 3, bw + 6, bh + 6, 6, 6)
    frac = G.hp / G.maxhp
    lib.draw.roundedRectangle(mix([1, 0.2, 0.25], [0.3, 1, 0.45], frac), 0, x, y, max(1, bw * frac), bh, 4, 4)
    lib.draw.text(0xFFFFFF, f"{G.hp:.0f} / {G.maxhp:.0f}", x + bw / 2, y + bh / 2, s * 0.8, "center", "middle")
    secs = int(G.t)
    lib.draw.text(0xFFFFFF, f"{secs // 60}:{secs % 60:02d}   kills {G.kills}", x, y + bh + 12, s)
    diff = difficulty()
    lib.draw.text(mix([1, 0.9, 0.4], [1, 0.2, 0.2], min(1, (diff - 1) / 8)), f"threat {diff:.1f}   enemies {len(G.enemies)}",
                  x, y + bh + 12 + s * 1.3, s * 0.8)
    if G.t < 8 and not G.dead:
        lib.draw.text("#CCD", "WASD move   click / space slash   kills heal you", width / 2, height * 0.9, s, "center", "middle")
    if G.dead:
        lib.draw.rectangle(0x000000, 0, 0, height * 0.3, width, height * 0.4)
        lib.draw.text([1, 0.3, 0.35], "YOU DIED", width / 2, height * 0.42, unit * 0.1, "center", "middle")
        lib.draw.text(0xFFFFFF, f"survived {secs // 60}:{secs % 60:02d}   kills {G.kills}   threat {diff:.1f}",
                      width / 2, height * 0.54, unit * 0.04, "center", "middle")
        lib.draw.text("#AAB", "press R to restart", width / 2, height * 0.61, unit * 0.03, "center", "middle")


def onResize(w, h):
    global width, height, unit, ts
    width, height, unit = w, h, min(w, h)
    ts = unit / 14


def onUpdate(dt):
    global shx, shy
    dt = min(dt, 1 / 30)
    if G.dead and lib.keyPressed("KeyR"):
        reset()
    update(dt)
    shx, shy = lib.rand.float(-G.shake, G.shake), lib.rand.float(-G.shake, G.shake)
    lib.draw.rectangle(0x07070B, 0, 0, 0, width, height)
    draw_world()
    draw_entities()
    draw_hud()
