# TONE LAB - a playable synth built on lib.sound.tone. Tests: tone() with every waveform and envelope,
# mouse events (buttons, sliders, piano keys), keyboard events, and an oscilloscope that re-synthesises
# what you're hearing from the same maths and draws it with glowing lines.
#
# Piano: A S D F G H J K L (white)  W E T Y U O (black)   or click the keys
# 1-5: waveform   Z/X: octave   drag sliders: attack / release / length   R: random arpeggiator
import math

lib.window.setTitle("BaitLib - tone lab")
lib.window.setSize(1100, 700)
lib.window.setFps(60)

width, height, unit = 1100, 700, 700
WAVES = ["sine", "triangle", "square", "sawtooth", "noise"]
BG = [0.04, 0.05, 0.09]
wave_i = 0
octave = 0
attack, release, length = 0.01, 0.25, 0.6
time = 0.0
active = []          # [freq, t0, length, attack, release, kind, hue]
bursts = []          # [u, v, hue, life]  visual notes
drag = None          # name of the slider being dragged
arp = False
arp_t = 0.0
SLIDERS = {"attack": (0.0, 0.5), "release": (0.0, 1.0), "length": (0.1, 2.0)}

# white keys -> keyboard letters, black keys sit between white index i and i+1
WHITES = [("KeyA", 0), ("KeyS", 2), ("KeyD", 4), ("KeyF", 5), ("KeyG", 7), ("KeyH", 9), ("KeyJ", 11), ("KeyK", 12), ("KeyL", 14)]
BLACKS = [("KeyW", 1, 0), ("KeyE", 3, 1), ("KeyT", 6, 3), ("KeyY", 8, 4), ("KeyU", 10, 5), ("KeyO", 13, 7)]
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def mix(a, b, k):
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]


def hsv(h, s=0.7, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, u = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, u, p], [q, v, p], [p, v, u], [p, q, v], [u, p, v], [v, p, q]][i]


def wave(kind, ph):
    if kind == "sine":
        return math.sin(2 * math.pi * ph)
    if kind == "sawtooth":
        return 2 * ph - 1
    if kind == "square":
        return 1.0 if ph < 0.5 else -1.0
    if kind == "triangle":
        return 2 * abs(2 * ((ph + 0.25) % 1.0) - 1) - 1
    return (math.sin(ph * 12.9898 * 78.233) * 43758.5453) % 1.0 * 2 - 1      # deterministic "noise"


def envelope(age, a, r, L):
    if age < 0 or age > L:
        return 0.0
    k = 1.0
    if a > 0:
        k = min(k, age / a)
    if r > 0:
        k = min(k, (L - age) / r)
    return max(0.0, k)


def note_freq(semi):
    return 261.63 * 2 ** ((semi + octave * 12) / 12)


def play_note(semi, key_u=None):
    kind = WAVES[wave_i]
    f = note_freq(semi)
    q = lambda v: round(v, 2)
    lib.sound.play(lib.sound.tone(q(length), f, kind, q(attack), q(release)), False, 0.35)
    hue = (semi % 12) / 12
    active.append([f, time, q(length), q(attack), q(release), kind, hue])
    if key_u is not None:
        bursts.append([key_u, 0.6, hue, 1.0])


# ---------------------------------------------------------------- layout (uv)
def key_rects():
    """returns [(semi, kind, x, y, w, h, letter)] in pixels; black keys last so they win hit tests"""
    x0, x1, y0, y1 = width * 0.05, width * 0.95, height * 0.62, height * 0.95
    ww = (x1 - x0) / len(WHITES)
    out = [(semi, "w", x0 + i * ww, y0, ww - 3, y1 - y0, k) for i, (k, semi) in enumerate(WHITES)]
    for k, semi, i in BLACKS:
        out.append((semi, "b", x0 + (i + 1) * ww - ww * 0.3, y0, ww * 0.6, (y1 - y0) * 0.6, k))
    return out


def slider_rect(i):
    return width * 0.05, height * 0.3 + i * unit * 0.07, width * 0.26, unit * 0.025


def button_rect(i):
    w = width * 0.9 / 5
    return width * 0.05 + i * w, height * 0.135, w - 8, unit * 0.06


def onResize(w, h):
    global width, height, unit
    width, height, unit = w, h, min(w, h)


def values():
    return {"attack": attack, "release": release, "length": length}


def set_value(name, v):
    global attack, release, length
    if name == "attack":
        attack = v
    elif name == "release":
        release = v
    else:
        length = v


def onUpdate(dt):
    global time, wave_i, octave, drag, arp, arp_t
    time += dt
    dt = min(dt, 1 / 30)

    # ---- keyboard
    for i in range(5):
        if lib.keyPressed(f"Key{i + 1}"):
            wave_i = i
    if lib.keyPressed("KeyZ"):
        octave = max(-2, octave - 1)
    if lib.keyPressed("KeyX"):
        octave = min(2, octave + 1)
    if lib.keyPressed("KeyR"):
        arp = not arp
    rects = key_rects()
    for semi, kind, x, y, w, h, letter in rects:
        if lib.keyPressed(letter):
            play_note(semi, (x + w / 2) / width)

    if arp:
        arp_t -= dt
        if arp_t <= 0:
            arp_t = 0.16
            scale = [0, 2, 4, 7, 9, 12, 14]
            play_note(lib.rand.choice(scale), lib.rand.float(0.1, 0.9))

    # ---- mouse: buttons, sliders, keys
    for e in lib.getMouse():
        if e[7] != "Left":
            continue
        x, y = e[1], e[2]
        if e[8]:                                                     # pressed this frame
            drag = None
            for i in range(5):
                bx, by, bw, bh = button_rect(i)
                if lib.collision.query(["point", x, y], ["rect", bx, by, bw, bh]):
                    wave_i = i
            for i, name in enumerate(SLIDERS):
                sx, sy, sw, sh = slider_rect(i)
                if lib.collision.query(["point", x, y], ["rect", sx - 10, sy - 12, sw + 20, sh + 24]):
                    drag = name
            if drag is None:
                for semi, kind, kx, ky, kw, kh, letter in reversed(rects):     # black keys first
                    if lib.collision.query(["point", x, y], ["rect", kx, ky, kw, kh]):
                        play_note(semi, (kx + kw / 2) / width)
                        break
        if drag:
            i = list(SLIDERS).index(drag)
            sx, sy, sw, sh = slider_rect(i)
            lo, hi = SLIDERS[drag]
            set_value(drag, round(lo + lib.clamp((x - sx) / sw, 0, 1) * (hi - lo), 2))
        if e[9]:
            drag = None

    # ---- housekeeping
    active[:] = [n for n in active if time - n[1] < n[2]]
    for b in bursts[:]:
        b[1] -= dt * 0.18
        b[3] -= dt * 0.9
        if b[3] <= 0:
            bursts.remove(b)

    draw()


# ---------------------------------------------------------------- drawing
def glow_line(pts, col, w=3):
    """polyline with a fake glow: wide dim passes underneath, bright thin pass on top"""
    for ww, k in ((w * 3, 0.18), (w * 2, 0.35), (w, 1.0)):
        c = mix(BG, col, k)
        for i in range(len(pts) - 1):
            lib.draw.line(c, ww, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])


def draw_scope():
    x, y, w, h = width * 0.36, height * 0.26, width * 0.59, height * 0.29
    lib.draw.roundedRectangle(0x0A0D14, 0, x, y, w, h, 10, 10)
    lib.draw.roundedRectangle(0x1B2433, 2, x, y, w, h, 10, 10)
    for i in range(1, 8):
        lib.draw.line(0x141B28, 1, x + w * i / 8, y, x + w * i / 8, y + h)
    for i in range(1, 4):
        lib.draw.line(0x141B28, 1, x, y + h * i / 4, x + w, y + h * i / 4)
    N = 320
    window = 0.025
    kind = WAVES[wave_i]
    pts, col = [], [0.3, 0.9, 0.7]
    if active:
        col = hsv(active[-1][6], 0.6, 1.0)
        for i in range(N):
            tau = time - window + i / N * window
            s = 0.0
            for f, t0, L, a, r, k, hue in active:
                age = tau - t0
                s += envelope(age, a, r, L) * wave(k, (f * age) % 1.0)
            s = lib.clamp(s / max(1, len(active)) * 0.5 * 2, -1, 1)
            pts.append((x + w * i / (N - 1), y + h / 2 - s * h * 0.42))
    else:                                                           # idle: preview the chosen waveform
        for i in range(N):
            ph = (i / N * 3 + time * 0.4) % 1.0
            pts.append((x + w * i / (N - 1), y + h / 2 - wave(kind, ph) * h * 0.3))
        col = [0.35, 0.45, 0.6]
    glow_line(pts, col)
    lib.draw.text("#6B7A99", "oscilloscope" if active else f"{kind} preview", x + 12, y + 8, unit * 0.028)


def draw_controls():
    s = unit * 0.03
    lib.draw.text(0xEAF0FF, "TONE LAB", width * 0.05, height * 0.025, s * 1.9)
    lib.draw.text("#6B7A99", f"lib.sound.tone({length:.2f}, {note_freq(0):.1f}..., \"{WAVES[wave_i]}\", {attack:.2f}, {release:.2f})",
                  width * 0.05, height * 0.025 + s * 2.4, s * 0.65)
    for i, name in enumerate(WAVES):
        x, y, w, h = button_rect(i)
        on = i == wave_i
        col = hsv(i / 6 + 0.05, 0.6, 1.0)
        lib.draw.roundedRectangle(mix(BG, col, 0.9) if on else 0x151B29, 0, x, y, w, h, 10, 10)
        lib.draw.roundedRectangle(col, 2, x, y, w, h, 10, 10)
        lib.draw.text(0x0A0A14 if on else 0xC8D2EA, f"{i + 1}  {name}", x + w / 2, y + h / 2, s * 0.9, "center", "middle")
    vals = values()
    for i, (name, (lo, hi)) in enumerate(SLIDERS.items()):
        x, y, w, h = slider_rect(i)
        frac = (vals[name] - lo) / (hi - lo)
        lib.draw.text("#9AA8C8", f"{name}  {vals[name]:.2f}s", x, y - s * 1.2, s * 0.8)
        lib.draw.roundedRectangle(0x1B2433, 0, x, y, w, h, 6, 6)
        lib.draw.roundedRectangle([0.3, 0.8, 1.0], 0, x, y, max(2, w * frac), h, 6, 6)
        lib.draw.circle(0xFFFFFF, 0, x + w * frac, y + h / 2, h * 0.9)
    # envelope shape preview under the sliders
    ex, ey, ew, eh = width * 0.05, height * 0.3 + 3 * unit * 0.07 - 6, width * 0.26, height * 0.55 - (height * 0.3 + 3 * unit * 0.07) + 2
    pts = [(ex + ew * t / 60, ey + eh - envelope(t / 60 * length, attack, release, length) * eh) for t in range(61)]
    lib.draw.line(0x253049, 1, ex, ey + eh, ex + ew, ey + eh)
    for i in range(60):
        lib.draw.line([0.4, 1.0, 0.7], 2, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
    lib.draw.text("#6B7A99", f"octave {octave:+d}   R: arpeggiator {'ON' if arp else 'off'}",
                  width * 0.05, height * 0.57, s * 0.7)


def draw_keys():
    now_on = {}
    for n in active:
        if time - n[1] < n[2]:
            now_on[round(math.log2(n[0] / 261.63) * 12 - octave * 12)] = n[6]
    rects = key_rects()
    for semi, kind, x, y, w, h, letter in rects:
        if kind != "w":
            continue
        hue = now_on.get(semi)
        lib.draw.roundedRectangle(mix([0.9, 0.9, 0.95], hsv(hue, 0.7, 1.0), 0.8) if hue is not None else 0xE9EDF5, 0, x, y, w, h, 8, 8)
        lib.draw.text(0x445, letter[3:], x + w / 2, y + h - 16, unit * 0.03, "center", "bottom")
        lib.draw.text("#889", NAMES[(semi) % 12], x + w / 2, y + h - 16 - unit * 0.04, unit * 0.022, "center", "bottom")
    for semi, kind, x, y, w, h, letter in rects:
        if kind != "b":
            continue
        hue = now_on.get(semi)
        lib.draw.roundedRectangle(hsv(hue, 0.8, 0.9) if hue is not None else 0x14171F, 0, x, y, w, h, 6, 6)
        lib.draw.text("#AAB", letter[3:], x + w / 2, y + h - 10, unit * 0.025, "center", "bottom")


def draw_bursts():
    for b in bursts:                                              # rising note streaks above the keys
        x = width * b[0]
        lib.draw.roundedRectangle(mix(BG, hsv(b[2], 0.6, 1.0), b[3] * 0.6), 0, x - 6, height * b[1] - 40, 12, 40 + (1 - b[3]) * 40, 6, 6)


def draw():
    lib.draw.rectangle(BG, 0, 0, 0, width, height)
    draw_bursts()
    draw_controls()
    draw_scope()
    draw_keys()
