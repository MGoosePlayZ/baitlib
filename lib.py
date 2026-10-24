#!/usr/bin/env python3
"""
BaitLib - small pygame-ce framework that mimics Castle scripting.

Run an app:
    python lib.py ./files/main.py
    uv run --with pygame-ce --with numpy lib.py ./files/main.py

numpy is optional: only needed for Speed/Pitch changes in lib.sound.

How it works
    main.py is exec'd with `lib` in its globals. Top-level code runs once, then the
    window is created, onResize(w, h) fires once, then onUpdate(dt) fires every frame.
    The screen is cleared to black before each onUpdate.
    Relative file paths resolve from the folder that contains main.py, and that
    folder is on sys.path, so other files next to main.py can be imported.
    `import lib` inside those files gives the same instance that is running.

Conventions
    origin top-left, +y down, angles in radians, time in seconds
    colors: 0xRRGGBB | "#RRGGBB" | [r, g, b] floats 0-1, each with optional alpha (0xRRGGBBAA, "#RRGGBBAA", [r, g, b, a])
    Weight 0 = filled, otherwise outline of that many pixels

Assumptions (spec was silent):
    circle X,Y is the center. rectangle / ellipse / roundedRectangle / image X,Y is the
    top-left corner of the bounding box.
    text Scale is the line height in pixels (approx). text/measureText handle "\\n".
    "ray" collision primitives are finite segments between their two points.
    rand.perlin returns 0..1. getScroll() is positive when scrolling up.
    Extras, not in the original spec: lib.getMousePos() (hover position without a click), lib.getText()
    (typed characters), lib.draw.setClip/clearClip (clip rectangle), ints > 0xFFFFFF are RRGGBBAA colors.
    Separate libraries next to this file: ease.py, physics.py, gui/ (import them like any module).
"""
import array as _array
import itertools as _itertools
import json as _json
import math as _math
import operator as _operator
import os as _os
import random as _random
import sys as _sys
import time as _time

try:
    import pygame
except ImportError:
    _sys.exit("BaitLib needs pygame-ce:  pip install pygame-ce")
if not getattr(pygame, "IS_CE", False):
    print("warning: BaitLib targets pygame-ce; plain pygame may misbehave", file=_sys.stderr)

try:
    import numpy as _np
except ImportError:
    _np = None

_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:  # lets apps do `import gui`, `import physics`, `import ease` from any folder
    _sys.path.append(_HERE)

_ids = _itertools.count(1)  # shared by mouse + key events, never reused
_N_CHANNELS = 64


# ============================================================ internal state
class _S:
    title = "BaitLib"
    size = (800, 600)
    fullscreen = False
    fps = 60
    cursor = None
    icon = None
    frame = 0
    screen = None


class _Snd:
    ok = False
    channels = []
    owner = []
    voices = {}
    warned = False


def _init():
    if pygame.get_init():
        return
    pygame.mixer.pre_init(44100, -16, 2, 512, allowedchanges=0)
    pygame.init()
    if pygame.mixer.get_init():
        pygame.mixer.set_num_channels(_N_CHANNELS)
        _Snd.channels = [pygame.mixer.Channel(i) for i in range(_N_CHANNELS)]
        _Snd.owner = [None] * _N_CHANNELS
        _Snd.ok = True
    else:
        print("warning: no audio device, lib.sound is disabled", file=_sys.stderr)


def _make_window():
    _init()
    if _S.icon is not None:
        pygame.display.set_icon(_S.icon)
    if _S.fullscreen:
        _S.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        _S.screen = pygame.display.set_mode(_S.size, pygame.RESIZABLE)
    pygame.display.set_caption(_S.title)
    pygame.key.start_text_input()  # lib.getText()


def _screen():
    if _S.screen is None:
        _make_window()
    return _S.screen


def _r(v):
    return int(_math.floor(v + 0.5))


# ============================================================ colors
def _rgba(c):
    """Any supported color -> (r, g, b, a) ints 0-255. Alpha is optional and defaults to opaque.
    Ints: <= 0xFFFFFF is RRGGBB, bigger is RRGGBBAA (so RGBA colors whose red byte is 0x00
    cannot be written as an int, use "#00RRGGBBAA" or a list)."""
    if isinstance(c, str):
        h = c.strip().lstrip("#")
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8):
            raise ValueError(f"bad color string {c!r}, expected '#RRGGBB' or '#RRGGBBAA'")
        v = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
        return (v[0], v[1], v[2], v[3] if len(v) == 4 else 255)
    if isinstance(c, pygame.Color):
        return (c.r, c.g, c.b, c.a)
    if isinstance(c, int) and not isinstance(c, bool):
        if c > 0xFFFFFF:
            return ((c >> 24) & 255, (c >> 16) & 255, (c >> 8) & 255, c & 255)
        return ((c >> 16) & 255, (c >> 8) & 255, c & 255, 255)
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        v = [max(0, min(255, _r(x * 255))) for x in c[:4]]
        return (v[0], v[1], v[2], v[3] if len(v) == 4 else 255)
    raise TypeError(f"bad color {c!r}")


def _color(c):
    return _rgba(c)[:3]


def _width(weight):
    return 0 if not weight or weight <= 0 else max(1, _r(weight))


# ============================================================ files
class _Image:
    def __init__(self, path):
        self.path = path
        self._raw = pygame.image.load(path)
        self._surf = None
        self._scaled = {}
        self.width, self.height = self._raw.get_size()

    def _base(self):
        if self._surf is None:  # needs a display, so convert lazily
            _screen()
            self._surf = self._raw.convert_alpha()
        return self._surf

    def _get(self, w, h):
        flip_x, flip_y = w < 0, h < 0
        w, h = abs(_r(w)), abs(_r(h))
        if w == 0 or h == 0:
            return None
        base = self._base()
        if (w, h) == (self.width, self.height) and not (flip_x or flip_y):
            return base
        key = (w, h, flip_x, flip_y)
        s = self._scaled.get(key)
        if s is None:
            if len(self._scaled) > 16:
                self._scaled.clear()
            if w < self.width and h < self.height:
                s = pygame.transform.smoothscale(base, (w, h))
            else:
                s = pygame.transform.scale(base, (w, h))
            if flip_x or flip_y:
                s = pygame.transform.flip(s, flip_x, flip_y)
            self._scaled[key] = s
        return s


class _Font:
    _default = None

    def __init__(self, path=None):
        self.path = path
        self._by_size = {}
        self.get(16)  # fail early on a bad path

    def get(self, size):
        f = self._by_size.get(size)
        if f is None:
            f = pygame.font.Font(self.path, size)
            ls = f.get_linesize()
            if ls and ls != size:  # pygame size != line height, rescale so Scale ~ line height in px
                f = pygame.font.Font(self.path, max(1, _r(size * size / ls)))
            self._by_size[size] = f
        return f


def _default_font():
    if _Font._default is None:
        _init()
        _Font._default = _Font(None)
    return _Font._default


class _Audio:
    def __init__(self, path=None, sound=None):
        self.path = path
        if sound is not None:
            self.sound = sound
        else:
            self.sound = pygame.mixer.Sound(path) if _Snd.ok and path else None
        self.duration = max(self.sound.get_length(), 1e-6) if self.sound else 1.0
        self._array = None
        self._proc = {}
        self._snds = {}

    def array(self):
        if self._array is None:
            a = pygame.sndarray.array(self.sound)
            if a.ndim == 1:
                a = _np.stack([a, a], axis=1)
            self._array = a
        return self._array

    def processed(self, speed, pitch):
        """int16 array with tempo=speed and pitch=pitch (cached)."""
        key = (round(speed, 3), round(pitch, 3))
        out = self._proc.get(key)
        if out is None:
            x = self.array()
            if key != (1.0, 1.0):
                y = x.astype(_np.float32)
                ratio = speed / pitch  # tempo change still needed after resampling
                if abs(ratio - 1) > 1e-3:
                    y = _stretch(y, ratio)
                if abs(pitch - 1) > 1e-3:
                    y = _resample(y, pitch)
                x = _np.clip(y, -32768, 32767).astype(_np.int16)
            if len(self._proc) >= 8:
                self._proc.pop(next(iter(self._proc)))
            out = self._proc[key] = x
        return out

    def sound_for(self, speed, pitch):
        key = (round(speed, 3), round(pitch, 3))
        s = self._snds.get(key)
        if s is None:
            if len(self._snds) >= 8:
                self._snds.pop(next(iter(self._snds)))
            s = self._snds[key] = pygame.sndarray.make_sound(
                _np.ascontiguousarray(self.processed(speed, pitch)))
        return s


_WAVES = ("sine", "sawtooth", "square", "triangle", "noise")
_tone_cache = {}


def _synth(length, freq, kind, attack, release):
    """Builds a stereo int16 pygame Sound for a simple waveform with a linear attack/release."""
    rate = pygame.mixer.get_init()[0]
    n = max(1, int(length * rate))
    a, r = max(0.0, attack), max(0.0, release)
    if a + r > length:  # envelope longer than the sound: shrink both to fit
        k = length / (a + r)
        a, r = a * k, r * k
    na, nr = int(a * rate), int(r * rate)
    amp = 0.6 * 32767  # headroom so several tones can overlap
    if _np is not None:
        ph = (_np.arange(n) * (freq / rate)) % 1.0
        if kind == "sine":
            w = _np.sin(2 * _math.pi * ph)
        elif kind == "sawtooth":
            w = 2 * ph - 1
        elif kind == "square":
            w = _np.where(ph < 0.5, 1.0, -1.0)
        elif kind == "triangle":
            w = 2 * _np.abs(2 * ((ph + 0.25) % 1.0) - 1) - 1
        else:
            w = _np.random.uniform(-1, 1, n)
        env = _np.ones(n)
        if na:
            env[:na] = _np.linspace(0, 1, na, endpoint=False)
        if nr:
            env[n - nr:] *= _np.linspace(1, 0, nr)
        mono = (w * env * amp).astype(_np.int16)
        return pygame.sndarray.make_sound(_np.ascontiguousarray(_np.repeat(mono[:, None], 2, axis=1)))
    buf = _array.array("h")  # pure python fallback, slower but no numpy needed
    for i in range(n):
        p = (i * freq / rate) % 1.0
        if kind == "sine":
            v = _math.sin(2 * _math.pi * p)
        elif kind == "sawtooth":
            v = 2 * p - 1
        elif kind == "square":
            v = 1.0 if p < 0.5 else -1.0
        elif kind == "triangle":
            v = 2 * abs(2 * ((p + 0.25) % 1.0) - 1) - 1
        else:
            v = _random.uniform(-1, 1)
        if i < na:
            v *= i / na
        if i >= n - nr:
            v *= (n - 1 - i) / nr
        v = int(v * amp)
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _resample(y, factor):
    """Linear-interpolation resample. factor>1 = shorter + higher pitch."""
    n = len(y)
    m = max(1, int(n / factor))
    idx = _np.arange(m) * factor
    i0 = _np.floor(idx).astype(_np.int64)
    fr = (idx - i0).astype(_np.float32)[:, None]
    i1 = _np.minimum(i0 + 1, n - 1)
    return y[i0] * (1 - fr) + y[i1] * fr


def _stretch(y, ratio):
    """Plain overlap-add time stretch, pitch unchanged. ratio>1 = faster/shorter.
    Swap for WSOLA if quality ever matters."""
    n, ch = y.shape
    N = 2048
    hs = N // 4
    ha = hs * ratio
    frames = max(1, int(_math.ceil(n / ha)))
    x = _np.concatenate([y, _np.zeros((N, ch), _np.float32)])
    out = _np.zeros(((frames - 1) * hs + N, ch), _np.float32)
    norm = _np.zeros(len(out), _np.float32)
    win = _np.hanning(N).astype(_np.float32)
    for k in range(frames):
        a = int(k * ha)
        o = k * hs
        out[o:o + N] += x[a:a + N] * win[:, None]
        norm[o:o + N] += win
    norm[norm < 1e-3] = 1.0
    out /= norm[:, None]
    return out[:max(1, int(n / ratio))]


class file:
    @staticmethod
    def image(Path):
        return _Image(Path)

    @staticmethod
    def font(Path):
        return _Font(Path)

    @staticmethod
    def audio(Path):
        _init()
        return _Audio(Path)

    @staticmethod
    def rawBinary(Path):
        with open(Path, "rb") as f:
            return f.read()

    @staticmethod
    def rawText(Path):
        with open(Path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write(Path, Data):
        """Writes str as UTF-8 text, bytes as-is, dict/list as JSON text. Creates missing folders and
        writes atomically (temp file + rename) so a crash never leaves half a save."""
        if isinstance(Data, (bytes, bytearray, memoryview)):
            mode, payload = "wb", bytes(Data)
        elif isinstance(Data, str):
            mode, payload = "w", Data
        elif isinstance(Data, (dict, list, tuple)):
            mode, payload = "w", _json.dumps(Data, indent=2)
        else:
            raise TypeError("file.write takes str, bytes, dict or list")
        folder = _os.path.dirname(_os.path.abspath(Path))
        _os.makedirs(folder, exist_ok=True)
        tmp = str(Path) + ".tmp"
        with open(tmp, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
            f.write(payload)
        _os.replace(tmp, Path)

    @staticmethod
    def parseJson(Path):
        with open(Path, "r", encoding="utf-8") as f:
            return _json.load(f)


# ============================================================ vectors
def _comp(i):
    return property(lambda s: s._c[i], lambda s, v: s._c.__setitem__(i, v))


class _Vec:
    __slots__ = ("_c",)
    _n = 0

    def __init__(self, *a):
        n = self._n
        if not a:
            a = (0,) * n
        elif len(a) == 1:
            a = (a[0],) * n if isinstance(a[0], (int, float)) else tuple(a[0])
        if len(a) != n:
            raise TypeError(f"{type(self).__name__} needs {n} components, got {len(a)}")
        self._c = list(a)

    def _other(self, o):
        if isinstance(o, _Vec):
            if o._n != self._n:
                raise TypeError("vector size mismatch")
            return o._c
        if isinstance(o, (int, float)) and not isinstance(o, bool):
            return [o] * self._n
        if isinstance(o, (list, tuple)) and len(o) == self._n:
            return list(o)
        return None

    def _bin(self, o, f, rev=False):
        b = self._other(o)
        if b is None:
            return NotImplemented
        if rev:
            return type(self)(*[f(y, x) for x, y in zip(self._c, b)])
        return type(self)(*[f(x, y) for x, y in zip(self._c, b)])

    def __neg__(self):
        return type(self)(*[-x for x in self._c])

    def __pos__(self):
        return self.copy()

    def __abs__(self):
        return type(self)(*[abs(x) for x in self._c])

    def __eq__(self, o):
        b = self._other(o) if not isinstance(o, (int, float)) else None
        return b is not None and self._c == b

    def __iter__(self):
        return iter(self._c)

    def __len__(self):
        return self._n

    def __getitem__(self, i):
        return self._c[i]

    def __setitem__(self, i, v):
        self._c[i] = v

    def __repr__(self):
        return f"{type(self).__name__}({', '.join(repr(x) for x in self._c)})"

    def copy(self):
        return type(self)(*self._c)

    def length(self):
        return _math.sqrt(sum(x * x for x in self._c))

    def dot(self, o):
        return sum(x * y for x, y in zip(self._c, self._other(o)))


for _name, _fn in (("add", _operator.add), ("sub", _operator.sub), ("mul", _operator.mul),
                   ("truediv", _operator.truediv), ("floordiv", _operator.floordiv),
                   ("pow", _operator.pow), ("mod", _operator.mod)):
    setattr(_Vec, f"__{_name}__", lambda self, o, _f=_fn: self._bin(o, _f))
    setattr(_Vec, f"__r{_name}__", lambda self, o, _f=_fn: self._bin(o, _f, True))


class vec2(_Vec):
    __slots__ = ()
    _n = 2
    x = _comp(0)
    y = _comp(1)


class vec3(_Vec):
    __slots__ = ()
    _n = 3
    x = _comp(0)
    y = _comp(1)
    z = _comp(2)

    def cross(self, o):
        a, b = self._c, self._other(o)
        return vec3(a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class vec4(_Vec):
    __slots__ = ()
    _n = 4
    x = _comp(0)
    y = _comp(1)
    z = _comp(2)
    w = _comp(3)


_VEC = {2: vec2, 3: vec3, 4: vec4}


def dist(A, B):
    return _math.dist(list(A), list(B))


def norm(Vector):
    v = Vector if isinstance(Vector, _Vec) else _VEC[len(Vector)](*Vector)
    length = v.length()
    return v / length if length else v.copy()


# ============================================================ essentials
def sign(Value):
    """-1, 0 or 1"""
    return (Value > 0) - (Value < 0)


class json:
    @staticmethod
    def compile(Value, Indent=None):
        """dict/list -> JSON string. Indent (optional int) pretty-prints."""
        return _json.dumps(Value, indent=Indent)

    @staticmethod
    def parse(Text):
        """JSON string -> dict/list/number/str"""
        return _json.loads(Text)


def lerp(A, B, T):
    return A + (B - A) * T


def clamp(Val, Min, Max):
    return max(Min, min(Max, Val))


sin, cos, tan = _math.sin, _math.cos, _math.tan
asin, acos, atan, atan2 = _math.asin, _math.acos, _math.atan, _math.atan2
sinh, cosh, tanh = _math.sinh, _math.cosh, _math.tanh
asinh, acosh, atanh = _math.asinh, _math.acosh, _math.atanh


class time:
    @staticmethod
    def frame():
        """Frame counter: 0 during the first onUpdate, +1 every frame."""
        return _S.frame

    @staticmethod
    def unix():
        return _time.time()

    @staticmethod
    def civil():
        t = _time.localtime()
        return [t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec]


_perm = list(range(256))
_random.Random(0).shuffle(_perm)  # fixed seed -> same noise every run
_perm += _perm


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def _grad(h, x, y, z):
    h &= 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h in (12, 14) else z)
    return (-u if h & 1 else u) + (-v if h & 2 else v)


class rand:
    @staticmethod
    def float(min, max):
        return _random.uniform(min, max)

    @staticmethod
    def int(min, max):  # inclusive both ends
        return _random.randint(min, max)

    @staticmethod
    def choice(*args):
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]
        return _random.choice(args)

    @staticmethod
    def gauss(mean, sigma):
        return _random.gauss(mean, sigma)

    @staticmethod
    def perlin(x, y, z=0):
        """Improved Perlin noise, remapped to 0..1."""
        xi, yi, zi = _math.floor(x), _math.floor(y), _math.floor(z)
        X, Y, Z = xi & 255, yi & 255, zi & 255
        x, y, z = x - xi, y - yi, z - zi
        u, v, w = _fade(x), _fade(y), _fade(z)
        p = _perm
        A = p[X] + Y
        AA, AB = p[A] + Z, p[A + 1] + Z
        B = p[X + 1] + Y
        BA, BB = p[B] + Z, p[B + 1] + Z
        n = lerp(
            lerp(lerp(_grad(p[AA], x, y, z), _grad(p[BA], x - 1, y, z), u),
                 lerp(_grad(p[AB], x, y - 1, z), _grad(p[BB], x - 1, y - 1, z), u), v),
            lerp(lerp(_grad(p[AA + 1], x, y, z - 1), _grad(p[BA + 1], x - 1, y, z - 1), u),
                 lerp(_grad(p[AB + 1], x, y - 1, z - 1), _grad(p[BB + 1], x - 1, y - 1, z - 1), u), v),
            w)
        return clamp(n * 0.5 + 0.5, 0.0, 1.0)


# ============================================================ collision
def _nr(r):
    x, y, w, h = r
    if w < 0:
        x, w = x + w, -w
    if h < 0:
        y, h = y + h, -h
    return x, y, w, h


def _seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return _math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _on_seg(x1, y1, x2, y2, px, py):
    return min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2)


def _seg_seg(a, b):
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b

    def cr(ax, ay, bx, by):
        return ax * by - ay * bx

    d1 = cr(x2 - x1, y2 - y1, x3 - x1, y3 - y1)
    d2 = cr(x2 - x1, y2 - y1, x4 - x1, y4 - y1)
    d3 = cr(x4 - x3, y4 - y3, x1 - x3, y1 - y3)
    d4 = cr(x4 - x3, y4 - y3, x2 - x3, y2 - y3)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return True
    return ((d1 == 0 and _on_seg(x1, y1, x2, y2, x3, y3)) or
            (d2 == 0 and _on_seg(x1, y1, x2, y2, x4, y4)) or
            (d3 == 0 and _on_seg(x3, y3, x4, y4, x1, y1)) or
            (d4 == 0 and _on_seg(x3, y3, x4, y4, x2, y2)))


def _seg_rect(s, r):  # Liang-Barsky
    x1, y1, x2, y2 = s
    rx, ry, rw, rh = _nr(r)
    t0, t1 = 0.0, 1.0
    dx, dy = x2 - x1, y2 - y1
    for p, q in ((-dx, x1 - rx), (dx, rx + rw - x1), (-dy, y1 - ry), (dy, ry + rh - y1)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return True


def _rect_rect(a, b):
    ax, ay, aw, ah = _nr(a)
    bx, by, bw, bh = _nr(b)
    return ax <= bx + bw and bx <= ax + aw and ay <= by + bh and by <= ay + ah


def _rect_circle(r, c):
    x, y, w, h = _nr(r)
    return _math.hypot(c[0] - clamp(c[0], x, x + w), c[1] - clamp(c[1], y, y + h)) <= c[2]


def _tri_pts(t):
    return [(t[0], t[1]), (t[2], t[3]), (t[4], t[5])]


def _rect_pts(r):
    x, y, w, h = _nr(r)
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _sat(P, Q):
    """Separating axis test for two convex polygons. Touching counts as overlapping."""
    for poly in (P, Q):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            ax, ay = y1 - y2, x2 - x1
            if ax == 0 and ay == 0:
                continue
            p = [ax * x + ay * y for x, y in P]
            q = [ax * x + ay * y for x, y in Q]
            if max(p) < min(q) or max(q) < min(p):
                return False
    return True


def _p_tri(p, t):
    (x1, y1), (x2, y2), (x3, y3) = _tri_pts(t)
    px, py = p[0], p[1]
    d1 = (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)
    d2 = (px - x3) * (y2 - y3) - (x2 - x3) * (py - y3)
    d3 = (px - x1) * (y3 - y1) - (x3 - x1) * (py - y1)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def _tri_edges(t):
    p = _tri_pts(t)
    return [(p[i][0], p[i][1], p[(i + 1) % 3][0], p[(i + 1) % 3][1]) for i in range(3)]


def _ray_tri(s, t):
    return _p_tri(s[0:2], t) or _p_tri(s[2:4], t) or any(_seg_seg(s, e) for e in _tri_edges(t))


def _circle_tri(c, t):
    return _p_tri(c[0:2], t) or any(_seg_point_dist(c[0], c[1], *e) <= c[2] for e in _tri_edges(t))


_COLLIDE = {
    ("point", "point"): lambda a, b: a[0] == b[0] and a[1] == b[1],
    ("point", "ray"): lambda p, s: _seg_point_dist(p[0], p[1], *s) <= 1e-6,
    ("point", "rect"): lambda p, r: (lambda x, y, w, h: x <= p[0] <= x + w and y <= p[1] <= y + h)(*_nr(r)),
    ("point", "circle"): lambda p, c: _math.hypot(p[0] - c[0], p[1] - c[1]) <= c[2],
    ("ray", "ray"): _seg_seg,
    ("ray", "rect"): _seg_rect,
    ("ray", "circle"): lambda s, c: _seg_point_dist(c[0], c[1], *s) <= c[2],
    ("rect", "rect"): _rect_rect,
    ("rect", "circle"): _rect_circle,
    ("circle", "circle"): lambda a, b: _math.hypot(a[0] - b[0], a[1] - b[1]) <= a[2] + b[2],
    ("point", "triangle"): _p_tri,
    ("ray", "triangle"): _ray_tri,
    ("rect", "triangle"): lambda r, t: _sat(_rect_pts(r), _tri_pts(t)),
    ("circle", "triangle"): _circle_tri,
    ("triangle", "triangle"): lambda a, b: _sat(_tri_pts(a), _tri_pts(b)),
}


class collision:
    @staticmethod
    def query(Primitive1, Primitive2):
        a, b = Primitive1, Primitive2
        f = _COLLIDE.get((a[0], b[0]))
        if f:
            return bool(f(a[1:], b[1:]))
        f = _COLLIDE.get((b[0], a[0]))
        if f:
            return bool(f(b[1:], a[1:]))
        raise ValueError(f"unknown primitive pair {a[0]!r}, {b[0]!r}")


# ============================================================ drawing
def _rect(x, y, w, h):
    r = pygame.Rect(_r(x), _r(y), _r(w), _r(h))
    r.normalize()  # in place: fixes negative w/h
    return r


def _points(coords):
    if len(coords) == 1:
        coords = coords[0]
    c = list(coords)
    if c and isinstance(c[0], (list, tuple, _Vec)):
        return [(_r(p[0]), _r(p[1])) for p in c]
    if len(c) % 2:
        raise ValueError("odd number of coordinates")
    return [(_r(c[i]), _r(c[i + 1])) for i in range(0, len(c), 2)]


_scratch = [None]


def _emit(rgba, bbox, fn):
    """Runs fn(surface, ox, oy, color). Opaque colors draw straight to the screen. Translucent ones
    draw into a cleared patch of a scratch surface that is then alpha-blitted, so a single shape never
    double-blends with itself."""
    scr = _screen()
    if rgba[3] >= 255:
        fn(scr, 0, 0, rgba[:3])
        return
    if rgba[3] <= 0:
        return
    r = bbox.clip(scr.get_clip())
    if r.w <= 0 or r.h <= 0:
        return
    sc = _scratch[0]
    if sc is None or sc.get_size() != scr.get_size():
        sc = _scratch[0] = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
    sub = sc.subsurface(r)
    sub.fill((0, 0, 0, 0))
    fn(sub, -r.x, -r.y, rgba)
    scr.blit(sub, r.topleft)


def _bbox_pts(pts, pad):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return pygame.Rect(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad + 1, max(ys) - min(ys) + 2 * pad + 1)


def _poly(color, weight, pts):
    rgba, wd = _rgba(color), _width(weight)
    if len(pts) < 2:
        return

    def fn(s, ox, oy, c):
        P = [(x + ox, y + oy) for x, y in pts]
        if len(P) == 2:
            pygame.draw.line(s, c, P[0], P[1], max(1, wd))
            return
        pygame.draw.polygon(s, c, P, wd)
        if wd > 2:  # round joins so thick outlines have no corner gaps
            for p in P:
                pygame.draw.circle(s, c, p, wd // 2)

    _emit(rgba, _bbox_pts(pts, wd + 2), fn)


def _rounded_pts(x, y, w, h, rx, ry, seg=12):
    pts = []
    corners = ((x + w - rx, y + ry, -90), (x + w - rx, y + h - ry, 0),
               (x + rx, y + h - ry, 90), (x + rx, y + ry, 180))
    for cx, cy, a0 in corners:
        for i in range(seg + 1):
            a = _math.radians(a0 + 90 * i / seg)
            pts.append((_r(cx + rx * _math.cos(a)), _r(cy + ry * _math.sin(a))))
    return pts


_HA = {"left": 0.0, "center": 0.5, "right": 1.0}
_VA = {"top": 0.0, "middle": 0.5, "bottom": 1.0}
_text_cache = {}
_grad_cache = {}


def _text_metrics(text, scale, fontobj):
    f = (fontobj or _default_font()).get(max(1, _r(scale)))
    lines = str(text).split("\n")
    widths = [f.size(ln)[0] for ln in lines]
    lh = f.get_linesize()
    return f, lines, widths, lh, max(widths), lh * len(lines)


def _gradient_surface(w, h, c1, c2, ang):
    k = min(1.0, 128 / max(w, h))                      # build small, smooth-scale up
    tw, th = max(2, _r(w * k)), max(2, _r(h * k))
    ca, sa = _math.cos(ang), _math.sin(ang)
    ext = abs(w * ca) + abs(h * sa) or 1.0
    buf = bytearray()
    for j in range(th):
        py = ((j + 0.5) / th - 0.5) * h
        for i in range(tw):
            px = ((i + 0.5) / tw - 0.5) * w
            t = max(0.0, min(1.0, (px * ca + py * sa) / ext + 0.5))
            buf += bytes((_r(c1[0] + (c2[0] - c1[0]) * t), _r(c1[1] + (c2[1] - c1[1]) * t),
                          _r(c1[2] + (c2[2] - c1[2]) * t), _r(c1[3] + (c2[3] - c1[3]) * t)))
    surf = pygame.image.frombuffer(bytes(buf), (tw, th), "RGBA").convert_alpha()
    if (tw, th) != (w, h):
        surf = pygame.transform.smoothscale(surf, (w, h))
    return surf


class draw:
    @staticmethod
    def line(Color, Weight, X1, Y1, X2, Y2):
        w = max(1, _width(Weight))
        p1, p2 = (_r(X1), _r(Y1)), (_r(X2), _r(Y2))
        _emit(_rgba(Color), _bbox_pts([p1, p2], w + 1),
              lambda s, ox, oy, c: pygame.draw.line(s, c, (p1[0] + ox, p1[1] + oy), (p2[0] + ox, p2[1] + oy), w))

    @staticmethod
    def circle(Color, Weight, X, Y, Rad):
        if Rad <= 0:
            return
        x, y, rad, wd = _r(X), _r(Y), max(1, _r(Rad)), _width(Weight)
        _emit(_rgba(Color), pygame.Rect(x - rad - 1, y - rad - 1, rad * 2 + 3, rad * 2 + 3),
              lambda s, ox, oy, c: pygame.draw.circle(s, c, (x + ox, y + oy), rad, wd))

    @staticmethod
    def ellipse(Color, Weight, X, Y, W, H):
        r, wd = _rect(X, Y, W, H), _width(Weight)
        if r.w and r.h:
            _emit(_rgba(Color), r.inflate(2, 2),
                  lambda s, ox, oy, c: pygame.draw.ellipse(s, c, r.move(ox, oy), wd))

    @staticmethod
    def rectangle(Color, Weight, X, Y, W, H):
        r, wd = _rect(X, Y, W, H), _width(Weight)
        _emit(_rgba(Color), r, lambda s, ox, oy, c: pygame.draw.rect(s, c, r.move(ox, oy), wd))

    @staticmethod
    def roundedRectangle(Color, Weight, X, Y, W, H, RX, RY=None):
        RY = RX if RY is None else RY
        x, y, w, h = _nr((X, Y, W, H))
        rx, ry = max(0, min(RX, w / 2)), max(0, min(RY, h / 2))
        if rx < 1 or ry < 1:
            return draw.rectangle(Color, Weight, X, Y, W, H)
        if abs(rx - ry) < 1e-6:
            r, wd, rad = pygame.Rect(_r(x), _r(y), _r(w), _r(h)), _width(Weight), _r(rx)
            _emit(_rgba(Color), r, lambda s, ox, oy, c: pygame.draw.rect(s, c, r.move(ox, oy), wd, border_radius=rad))
        else:  # elliptical corners: polygon approximation
            _poly(Color, Weight, _rounded_pts(x, y, w, h, rx, ry))

    @staticmethod
    def triangle(Color, Weight, X1, Y1, X2, Y2, X3, Y3):
        _poly(Color, Weight, _points((X1, Y1, X2, Y2, X3, Y3)))

    @staticmethod
    def polygon(Color, Weight, *coords):
        _poly(Color, Weight, _points(coords))

    @staticmethod
    def gradient(Color1, Color2, X, Y, W, H, Rad=0.0):
        """Linear gradient filling the rectangle. Rad is the direction in radians:
        0 = left to right, pi/2 = top to bottom. Both colors may carry alpha."""
        x, y, w, h = _nr((X, Y, W, H))
        wi, hi = _r(w), _r(h)
        if wi < 1 or hi < 1:
            return
        c1, c2 = _rgba(Color1), _rgba(Color2)
        key = (wi, hi, round(Rad, 4), c1, c2)
        surf = _grad_cache.get(key)
        if surf is None:
            if len(_grad_cache) >= 12:
                _grad_cache.pop(next(iter(_grad_cache)))
            surf = _grad_cache[key] = _gradient_surface(wi, hi, c1, c2, Rad)
        _screen().blit(surf, (_r(x), _r(y)))

    @staticmethod
    def setClip(X, Y, W, H):
        """Restrict drawing to a rectangle until clearClip() is called."""
        _screen().set_clip(_rect(X, Y, W, H))

    @staticmethod
    def clearClip():
        _screen().set_clip(None)

    @staticmethod
    def text(Color, Text, X, Y, Scale=16, HA="left", VA="top", File=None):
        rgba = _rgba(Color)
        col = rgba[:3]
        f, lines, widths, lh, tw, th = _text_metrics(Text, Scale, File)
        ha, va = _HA[HA.lower()], _VA[VA.lower()]
        ox, oy = X - tw * ha, Y - th * va
        scr = _screen()
        for i, ln in enumerate(lines):
            if not ln:
                continue
            key = (id(f), ln, col)
            surf = _text_cache.get(key)
            if surf is None:
                if len(_text_cache) > 512:
                    _text_cache.clear()
                surf = _text_cache[key] = f.render(ln, True, col)
            surf.set_alpha(rgba[3])
            scr.blit(surf, (_r(ox + (tw - widths[i]) * ha), _r(oy + i * lh)))

    @staticmethod
    def measureText(Text, Scale=16, File=None):
        _, _, _, _, tw, th = _text_metrics(Text, Scale, File)
        return (tw, th)

    @staticmethod
    def image(Mode, X, Y, File, Opacity=1.0, *args):
        mode = str(Mode).lower()
        if mode == "scale":
            s = args[0] if args else 1
            w, h = File.width * s, File.height * s
        elif mode == "size":
            w = args[0]
            h = args[1] if len(args) > 1 and args[1] is not None else w * File.height / File.width
        else:
            raise ValueError("image mode must be 'scale' or 'size'")
        surf = File._get(w, h)
        if surf is None:
            return
        surf.set_alpha(_r(clamp(Opacity, 0.0, 1.0) * 255))
        _screen().blit(surf, (_r(X), _r(Y)))


# ============================================================ sound
def _vol(v):
    return clamp(float(v), 0.0, 1.0)


def _rate(v):
    return max(0.05, float(v))


def _alloc():
    oldest = None
    for i, ch in enumerate(_Snd.channels):
        v = _Snd.owner[i]
        if v is None or not ch.get_busy():
            return i
        if oldest is None or v.t0 < _Snd.owner[oldest].t0:
            oldest = i
    return oldest


class _Voice:
    def __init__(self, audio, looping, volume, speed, pitch):
        self.id = next(_ids)
        self.audio, self.looping, self.volume = audio, looping, volume
        self.speed, self.pitch = speed, pitch
        self.idx, self.t0, self.frac0, self._speed = -1, 0.0, 0.0, speed

    def _snd(self, frac):
        a = self.audio
        needs_dsp = self.speed != 1 or self.pitch != 1
        if needs_dsp and _np is None:
            if not _Snd.warned:
                _Snd.warned = True
                print("warning: numpy missing, sound Speed/Pitch ignored", file=_sys.stderr)
            self._speed = 1.0
            return a.sound, 0.0
        self._speed = self.speed
        if frac == 0:
            return (a.sound_for(self.speed, self.pitch) if needs_dsp else a.sound), 0.0
        arr = a.processed(self.speed, self.pitch)
        k = int(frac * len(arr))
        if k >= len(arr):
            return None, frac
        arr = _np.roll(arr, -k, axis=0) if self.looping else arr[k:]
        return pygame.sndarray.make_sound(_np.ascontiguousarray(arr)), frac

    def start(self, frac):
        snd, frac = self._snd(frac)
        if snd is None:
            return self.stop()
        mine = self.idx >= 0 and _Snd.owner[self.idx] is self
        idx = self.idx if mine else _alloc()
        ch = _Snd.channels[idx]
        ch.play(snd, loops=-1 if self.looping else 0)
        ch.set_volume(self.volume)  # after play(), play resets channel volume
        _Snd.owner[idx] = self
        self.idx, self.t0, self.frac0 = idx, _time.perf_counter(), frac

    def frac(self):
        f = self.frac0 + (_time.perf_counter() - self.t0) * self._speed / self.audio.duration
        return f % 1.0 if self.looping else f

    def playing(self):
        return (self.idx >= 0 and _Snd.owner[self.idx] is self
                and _Snd.channels[self.idx].get_busy())

    def stop(self):
        if self.idx >= 0 and _Snd.owner[self.idx] is self:
            _Snd.channels[self.idx].stop()
            _Snd.owner[self.idx] = None

    def restart(self):  # speed/pitch/looping changed: rebuild from current position
        f = self.frac()
        if not self.looping and f >= 1.0:
            return self.stop()
        self.start(f)


def _sweep():
    for vid in [i for i, v in _Snd.voices.items() if not v.playing()]:
        v = _Snd.voices.pop(vid)
        if v.idx >= 0 and _Snd.owner[v.idx] is v:
            _Snd.owner[v.idx] = None


class sound:
    @staticmethod
    def play(File, Looping=False, Volume=1.0, Speed=1.0, Pitch=1.0):
        """Speed = tempo (pitch unchanged), Pitch = pitch multiplier (tempo unchanged).
        Returns a sound id, or -1 if there is no audio device."""
        if not _Snd.ok:
            return -1
        if isinstance(File, str):
            File = file.audio(File)
        v = _Voice(File, bool(Looping), _vol(Volume), _rate(Speed), _rate(Pitch))
        v.start(0.0)
        _Snd.voices[v.id] = v
        return v.id

    @staticmethod
    def tone(length, frequency, type="sine", attack=0.01, release=0.05):
        """Generates a tone and returns an audio object, usable anywhere lib.file.audio() is.
        length/attack/release in seconds, frequency in Hz (ignored for "noise"),
        type: "sine" | "sawtooth" | "square" | "triangle" | "noise".
        Results are cached, so calling this every time you play is fine."""
        _init()
        if type not in _WAVES:
            raise ValueError(f"tone type must be one of {_WAVES}, got {type!r}")
        if length <= 0:
            raise ValueError("tone length must be > 0")
        if type != "noise" and frequency <= 0:
            raise ValueError("tone frequency must be > 0")
        if not _Snd.ok:
            return _Audio()
        key = (round(length, 4), round(frequency, 2), type, round(attack, 4), round(release, 4))
        a = _tone_cache.get(key)
        if a is None:
            if len(_tone_cache) >= 1024:
                _tone_cache.pop(next(iter(_tone_cache)))
            a = _tone_cache[key] = _Audio(sound=_synth(length, frequency, type, attack, release))
        return a

    @staticmethod
    def stop(id):
        v = _Snd.voices.pop(id, None)
        if v:
            v.stop()

    @staticmethod
    def stopall():
        if _Snd.ok:
            pygame.mixer.stop()
            _Snd.owner[:] = [None] * _N_CHANNELS
        _Snd.voices.clear()

    @staticmethod
    def setVolume(id, Volume):
        v = _Snd.voices.get(id)
        if v:
            v.volume = _vol(Volume)
            if v.playing():
                _Snd.channels[v.idx].set_volume(v.volume)

    @staticmethod
    def setSpeed(id, Speed):
        v = _Snd.voices.get(id)
        if v and v.playing():
            v.speed = _rate(Speed)
            v.restart()

    @staticmethod
    def setPitch(id, Pitch):
        v = _Snd.voices.get(id)
        if v and v.playing():
            v.pitch = _rate(Pitch)
            v.restart()

    @staticmethod
    def isLooping(id, Bool=None):
        """isLooping(id, True/False) sets looping. isLooping(id) returns it."""
        v = _Snd.voices.get(id)
        if Bool is None:
            return bool(v and v.looping)
        if v and v.playing() and bool(Bool) != v.looping:
            v.looping = bool(Bool)
            v.restart()


# ============================================================ input
def _build_keynames():
    t = {}
    for ch in "abcdefghijklmnopqrstuvwxyz":
        t[getattr(pygame, "K_" + ch)] = "Key" + ch.upper()
    for d in "0123456789":
        t[getattr(pygame, "K_" + d)] = "Key" + d
        t[getattr(pygame, "K_KP" + d)] = "Num" + d
    for i in range(1, 16):
        t[getattr(pygame, f"K_F{i}")] = f"F{i}"
    named = {
        "BACKSLASH": "KeyBackslash", "QUOTE": "KeyApostrophe", "COMMA": "KeyComma",
        "PERIOD": "KeyPeriod", "SLASH": "KeySlash", "SEMICOLON": "KeySemicolon",
        "EQUALS": "KeyEquals", "MINUS": "KeyMinus", "LEFTBRACKET": "KeyLeftBracket",
        "RIGHTBRACKET": "KeyRightBracket", "BACKQUOTE": "KeyGrave",
        "SPACE": "Space", "RETURN": "Enter", "TAB": "Tab", "BACKSPACE": "Backspace",
        "ESCAPE": "Escape", "DELETE": "Del", "INSERT": "Insert", "HOME": "Home", "END": "End",
        "PAGEUP": "PageUp", "PAGEDOWN": "PageDown", "LEFT": "Left", "RIGHT": "Right",
        "UP": "Up", "DOWN": "Down",
        "LSHIFT": "Shift", "RSHIFT": "RightShift", "LCTRL": "Ctrl", "RCTRL": "RightCtrl",
        "LALT": "Alt", "RALT": "RightAlt", "LSUPER": "Super", "RSUPER": "RightSuper",
        "LMETA": "Super", "RMETA": "RightSuper",
        "CAPSLOCK": "CapsLock", "NUMLOCK": "NumLock", "SCROLLLOCK": "ScrollLock",
        "PRINTSCREEN": "PrintScreen", "PAUSE": "Pause", "MENU": "Menu",
        "KP_ENTER": "NumEnter", "KP_PLUS": "NumPlus", "KP_MINUS": "NumMinus",
        "KP_MULTIPLY": "NumMultiply", "KP_DIVIDE": "NumDivide", "KP_PERIOD": "NumPeriod",
        "KP_EQUALS": "NumEquals",
    }
    for suffix, name in named.items():
        code = getattr(pygame, "K_" + suffix, None)
        if code is not None and code not in t:
            t[code] = name
    return t


_KEYNAMES = _build_keynames()


def _keyname(code):
    n = _KEYNAMES.get(code)
    if n is None:
        n = "Key" + pygame.key.name(code).title().replace(" ", "") if pygame.key.name(code) else f"Key{code}"
    return n


class _MEv:
    def __init__(self, action, pos, now):
        self.id = next(_ids)
        self.action = action
        self.x = self.px = self.ix = pos[0]
        self.y = self.py = self.iy = pos[1]
        self.dx = self.dy = 0
        self.pressed, self.released = True, False
        self.t0, self.dur = now, 0.0


class _KEv:
    def __init__(self, code, now):
        self.id = next(_ids)
        self.code = code
        self.name = _keyname(code)
        self.pressed, self.released = True, False
        self.t0, self.dur = now, 0.0


_BUTTONS = {1: "Left", 2: "Middle", 3: "Right"}


class _In:
    mouse = {}
    keys = {}
    scroll = 0.0
    text = ""


def _in_begin():
    for d in (_In.mouse, _In.keys):
        for k in [k for k, e in d.items() if e.released]:
            del d[k]
        for e in d.values():
            e.pressed = False
    _In.scroll = 0.0
    _In.text = ""


def _in_handle(ev, now):
    t = ev.type
    if t == pygame.MOUSEBUTTONDOWN:
        name = _BUTTONS.get(ev.button)
        if name and name not in _In.mouse:
            _In.mouse[name] = _MEv(name, ev.pos, now)
    elif t == pygame.MOUSEBUTTONUP:
        e = _In.mouse.get(_BUTTONS.get(ev.button))
        if e and not e.released:
            e.released = True
            e.x, e.y = ev.pos
    elif t == pygame.MOUSEWHEEL:
        _In.scroll += getattr(ev, "precise_y", ev.y)
    elif t == pygame.TEXTINPUT:
        _In.text += ev.text
    elif t == pygame.KEYDOWN:
        if ev.key not in _In.keys:
            _In.keys[ev.key] = _KEv(ev.key, now)
    elif t == pygame.KEYUP:
        e = _In.keys.get(ev.key)
        if e and not e.released:
            e.released = True
    elif t == pygame.WINDOWFOCUSLOST:  # no KEYUP/BUTTONUP will arrive, release everything
        for e in list(_In.mouse.values()) + list(_In.keys.values()):
            e.released = True


def _in_finish(now):
    mx, my = pygame.mouse.get_pos()
    for e in _In.mouse.values():
        if not e.released and not e.pressed:
            e.x, e.y = mx, my
        e.dx, e.dy = e.x - e.px, e.y - e.py
        e.px, e.py = e.x, e.y
        e.dur = now - e.t0
    for e in _In.keys.values():
        e.dur = now - e.t0


def getMouse():
    """[[Id, X, Y, DX, DY, IX, IY, Action, Pressed, Released, Duration], ...] one per held button."""
    return [[e.id, e.x, e.y, e.dx, e.dy, e.ix, e.iy, e.action, e.pressed, e.released, e.dur]
            for e in _In.mouse.values()]


def getMousePos():
    return list(pygame.mouse.get_pos())


def getScroll():
    return _In.scroll


def getText():
    """Characters typed during this update, as a string (layout, shift and IME applied).
    Use it for text fields. getKeys() is for key-style input."""
    return _In.text


def getKeys():
    """[[id, key, pressed, released, duration], ...]"""
    return [[e.id, e.name, e.pressed, e.released, e.dur] for e in _In.keys.values()]


def keyDown(Key):
    for e in _In.keys.values():
        if e.name == Key and not e.released:
            return e.dur
    return None


def keyPressed(Key):
    return any(e.name == Key and e.pressed for e in _In.keys.values())


def keyReleased(Key):
    return any(e.name == Key and e.released for e in _In.keys.values())


# ============================================================ window
_CURSORS = {
    "default": "ARROW", "pointer": "HAND", "wait": "WAIT", "progress": "WAITARROW",
    "text": "IBEAM", "not-allowed": "NO", "help": "ARROW", "crosshair": "CROSSHAIR",
    "move": "SIZEALL", "ns-resize": "SIZENS", "ew-resize": "SIZEWE", "nsew-resize": "SIZEALL",
    "copy": "HAND", "alias": "HAND",  # pygame has no help/copy/alias cursors, closest match used
}


class window:
    @staticmethod
    def setCursor(Cursor):
        if Cursor not in _CURSORS:
            raise ValueError(f"unknown cursor {Cursor!r}")
        _init()
        if Cursor == _S.cursor:  # cheap to call every frame
            return
        _S.cursor = Cursor
        try:
            pygame.mouse.set_cursor(getattr(pygame, "SYSTEM_CURSOR_" + _CURSORS[Cursor]))
        except pygame.error:  # eg. headless video driver has no system cursors
            pass

    @staticmethod
    def setFullscreen(Bool):
        Bool = bool(Bool)
        if Bool != _S.fullscreen:
            _S.fullscreen = Bool
            if _S.screen is not None:
                _make_window()

    @staticmethod
    def setIcon(File):
        """File: an image from lib.file.image(...) (or a path). Square images around 64x64 work best."""
        _init()
        if isinstance(File, str):
            File = _Image(File)
        _S.icon = File._raw
        pygame.display.set_icon(_S.icon)

    @staticmethod
    def setTitle(Text):
        _init()
        _S.title = str(Text)
        pygame.display.set_caption(_S.title)

    @staticmethod
    def setSize(width, height):
        _S.size = (max(1, int(width)), max(1, int(height)))
        if _S.screen is not None and not _S.fullscreen:
            _make_window()

    @staticmethod
    def setFps(Int):
        _S.fps = max(0, int(Int))  # 0 = uncapped


# ============================================================ runner
def _run(path):
    path = _os.path.abspath(path)
    if not _os.path.isfile(path):
        _sys.exit(f"file not found: {path}")
    folder = _os.path.dirname(path)
    _os.chdir(folder)
    _sys.path.insert(0, folder)
    _init()

    g = {"__name__": "__main__", "__file__": path, "lib": _sys.modules[__name__]}
    with open(path, "r", encoding="utf-8") as f:
        code = compile(f.read(), path, "exec")

    try:
        exec(code, g)  # top-level code, runs once
        last = _screen().get_size()
        cb = g.get("onResize")
        if callable(cb):
            cb(*last)

        clock = pygame.time.Clock()
        prev = _time.perf_counter()
        running = True
        while running:
            now = _time.perf_counter()
            dt, prev = now - prev, now

            _in_begin()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                _in_handle(ev, now)
            if not running:
                break
            _in_finish(now)

            screen = _screen()
            size = screen.get_size()
            if size != last:
                last = size
                if not _S.fullscreen:
                    _S.size = size
                cb = g.get("onResize")
                if callable(cb):
                    cb(*size)
                screen = _screen()

            screen.fill((0, 0, 0))
            cb = g.get("onUpdate")
            if callable(cb):
                cb(dt)
            _S.frame += 1
            _sweep()
            pygame.display.flip()
            clock.tick(_S.fps)
    finally:
        pygame.quit()


# Register future file handlers here (eg. ".filetype": open_custom_editor).
_HANDLERS = {".py": _run}

if __name__ == "__main__":
    _sys.modules["lib"] = _sys.modules[__name__]  # `import lib` in app files -> same instance
    if len(_sys.argv) < 2:
        _sys.exit("usage: python lib.py ./files/main.py")
    _ext = _os.path.splitext(_sys.argv[1])[1].lower()
    if _ext not in _HANDLERS:
        _sys.exit(f"no handler for '{_ext}' files")
    _HANDLERS[_ext](_sys.argv[1])
