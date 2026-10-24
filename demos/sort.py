# Shell sort visualizer. Sorts a shuffled 1..500 into 500..1, one comparison/write at a time,
# playing a tone for every step. Stress test: 500 filled rectangles + tones every frame.
#
# Up/Down: speed   Space: reshuffle   T: change waveform   M: mute
import math

lib.window.setTitle("BaitLib - shell sort")
lib.window.setSize(1100, 600)
lib.window.setFps(60)

N = 500
GAPS = [g for g in (701, 301, 132, 57, 23, 10, 4, 1) if g < N]  # Ciura gaps
WAVES = ["sine", "triangle", "square", "sawtooth"]

width, height, unit = 1100, 600, 600
wave_i = 0
muted = False
rate = 3000.0          # sort steps per second
acc = 0.0
shown_at = 0.0
time = 0.0


def hsv(h, s=0.8, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i]


COLORS = [hsv(0.0 + 0.78 * (max(v, 1) - 1) / (N - 1)) for v in range(N + 1)]


def shell_sort(a):
    """Generator: yields (index, other_index, kind) for every compare (0) and write (1).
    Sorts descending."""
    n = len(a)
    for gap in GAPS:
        for i in range(gap, n):
            tmp = a[i]
            j = i
            while j >= gap:
                yield (j, j - gap, 0, gap)
                if a[j - gap] < tmp:       # smaller value on the left -> shift it right
                    a[j] = a[j - gap]
                    yield (j, j, 1, gap)
                    j -= gap
                else:
                    break
            a[j] = tmp
            yield (j, j, 1, gap)


def shuffle():
    global arr, gen, compares, writes, phase, hot, gap, verified, wait
    arr = list(range(1, N + 1))
    for i in range(N - 1, 0, -1):
        j = lib.rand.int(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    gen = shell_sort(arr)
    compares = writes = 0
    phase = "sort"
    hot = (-1, -1, 0)
    gap = GAPS[0]
    verified = 0
    wait = 0.0


def blip(value, vol=0.12):
    if muted:
        return
    lib.sound.play(lib.sound.tone(0.05, 150 + value * 2, WAVES[wave_i], 0.002, 0.04), False, vol)


def onResize(w, h):
    global width, height, unit
    width, height, unit = w, h, min(w, h)


shuffle()


def onUpdate(dt):
    global acc, rate, wave_i, muted, time, phase, hot, gap, compares, writes, verified, wait
    time += dt

    # input
    if lib.keyPressed("Up"):
        rate = min(rate * 1.5, 600000)
    if lib.keyPressed("Down"):
        rate = max(rate / 1.5, 30)
    if lib.keyPressed("KeyT"):
        wave_i = (wave_i + 1) % len(WAVES)
    if lib.keyPressed("KeyM"):
        muted = not muted
    if lib.keyPressed("Space"):
        lib.sound.stopall()
        shuffle()

    # advance the sort
    if phase == "sort":
        acc += rate * dt
        steps = min(int(acc), 20000)
        acc -= int(acc)
        last = []
        for _ in range(steps):
            try:
                hot = next(gen)
            except StopIteration:
                phase = "verify"
                break
            gap = hot[3]
            if hot[2] == 0:
                compares += 1
            else:
                writes += 1
            last.append(arr[hot[0]])
        for v in last[-2:]:            # at most two tones per frame, keep it listenable
            blip(v)
    elif phase == "verify":            # green sweep, tone follows the value
        before = int(verified)
        verified += min(N / 1.5 * dt, N)
        for i in range(before, min(int(verified), N), 25):
            blip(arr[i], 0.1)
        if verified >= N:
            phase, wait = "done", 1.5
    else:
        wait -= dt
        if wait <= 0:
            shuffle()

    # draw
    lib.draw.rectangle(0x0B0D12, 0, 0, 0, width, height)
    left, right = width * 0.02, width * 0.98
    top, bottom = height * 0.16, height * 0.97
    bw = (right - left) / N
    area = bottom - top
    a, b = hot[0], hot[1]
    for i in range(N):
        v = arr[i]
        h = v / N * area
        if phase == "sort" and (i == a or i == b):
            col = 0xFFFFFF if i == a else 0xFF4060
        elif i < verified:
            col = 0x40FF80
        else:
            col = COLORS[v]
        lib.draw.rectangle(col, 0, left + i * bw, bottom - h, bw + 1, h)

    # sweep marker for verify pass
    if phase == "verify":
        lib.draw.rectangle(0xFFFFFF, 0, left + verified * bw, top, 2, area)

    s = unit * 0.035
    lib.draw.text(0xFFFFFF, "SHELL SORT   500 -> 1", width * 0.02, height * 0.02, s * 1.4)
    stats = (f"gap {gap}    compares {compares:,}    writes {writes:,}    "
             f"speed {rate:,.0f}/s    wave {WAVES[wave_i]}{'  (muted)' if muted else ''}")
    lib.draw.text("#9AA5B8", stats, width * 0.02, height * 0.02 + s * 1.7, s * 0.8)
    msg = {"sort": "sorting", "verify": "verifying", "done": "sorted!"}[phase]
    lib.draw.text(0x40FF80 if phase != "sort" else 0xFFD060, msg, width * 0.98, height * 0.02, s * 1.2, "right")
    lib.draw.text("#667", "Up/Down speed   Space reshuffle   T wave   M mute", width * 0.98,
                  height * 0.02 + s * 1.7, s * 0.7, "right")
