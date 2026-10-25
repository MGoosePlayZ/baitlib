# BaitLib

A small pygame-ce framework that recreates the useful parts of Castle scripting without the rest. Immediate-mode drawing, event-style input, sound, vectors, collision and a few helpers.

- [Getting started](#getting-started)
- [Conventions](#conventions)
- [Lifecycle](#lifecycle)
- [lib.draw](#libdraw)
- [lib.sound](#libsound)
- [Input](#input)
- [lib.file](#libfile)
- [Vectors](#vectors)
- [Essentials](#essentials)
- [lib.time](#libtime)
- [lib.rand](#librand)
- [lib.collision](#libcollision)
- [lib.window](#libwindow)
- [lib.json](#libjson)
- [Separate libraries](#separate-libraries): [ease](#ease), [physics](#physics), [gui](#gui)
- [Notes and limits](#notes-and-limits)

---

## Getting started

Requirements: Python 3, `pygame-ce`. `numpy` is optional and only needed for sound `Speed` / `Pitch` changes.

```
pip install pygame-ce numpy
```

App layout. Only `lib.py` is required.

```
app-name/
  lib.py
  files/
    main.py
    (other files)
```

Run:

```
python lib.py ./files/main.py
uv run --with pygame-ce --with numpy lib.py ./files/main.py
```

`main.py` is executed with `lib` already in its globals. No import needed.

Minimal app:

```python
lib.window.setTitle("Hello")

def onUpdate(dt):
    lib.draw.text(0xFFFFFF, "Hello world", 20, 20, 32)
```

Other files in `files/` can be imported normally. If they need the library, `import lib` gives the same running instance.

Relative paths (`lib.file.image("a.png")`) resolve from the folder that contains `main.py`.

---

## Conventions

| Thing | Rule |
|---|---|
| Origin | Top-left of the window, +x right, +y down |
| Units | Pixels, seconds, radians |
| Colors | `0xRRGGBB`, `"#RRGGBB"` (also `"#RGB"`), or `[r, g, b]` with floats 0 to 1, each with an optional alpha: `0xRRGGBBAA`, `"#RRGGBBAA"` (`"#RGBA"`), `[r, g, b, a]`. No alpha = fully opaque. |
| Weight | `0` = filled shape. Any other number = outline with that many pixels. |
| Rect-like X,Y | Top-left corner of the bounding box (rectangle, ellipse, roundedRectangle, image) |
| Circle X,Y | Center |

Alpha notes:

- Ints up to `0xFFFFFF` are `RRGGBB`; bigger ints are `RRGGBBAA`. A color whose red byte is `00` therefore can't be written as an int with alpha (`0x00FF00FF` is just magenta). Use `"#00FF00FF"` or `[0, 1, 0, 1]` for those.
- Translucent shapes are drawn into a scratch patch and blended once, so a single shape never darkens itself. Alpha works on every draw function including text.

Color examples:

```python
lib.draw.circle(0xFF0000, 0, 100, 100, 20)        # int
lib.draw.circle("#00FF00", 0, 150, 100, 20)       # string
lib.draw.circle([0.2, 0.4, 1.0], 0, 200, 100, 20) # floats 0-1
lib.draw.circle("#FF000080", 0, 150, 100, 20)       # 50% red, drawn over the green one
```

Tip: for windows that can be any size (tiling WMs, resizing), work in UV space (0 to 1) and multiply by the window size. See the bundled example.

---

## Lifecycle

```python
# 1. Top-level code runs once on startup.
lib.window.setTitle("My App")
lib.window.setSize(1280, 720)
lib.window.setFps(60)
image = lib.file.image("player.png")
speed = 200

# 2. The window is created, then onResize fires once.
def onResize(width, height):
    print(f"The window is now {width} pixels wide and {height} pixels tall!")

# 3. onUpdate fires every frame.
def onUpdate(dt):
    ...
```

| Callback | Called | Notes |
|---|---|---|
| `onResize(width, height)` | Once at startup, then whenever the window size changes (drag, `setSize`, fullscreen toggle) | Optional |
| `onUpdate(dt)` | Every frame | `dt` is seconds since the previous frame. Optional. |

Details:

- The screen is cleared to black before every `onUpdate`. Draw a full-window rectangle first if you want another background.
- Drawing calls only make sense inside `onUpdate`. The window does not exist yet during top-level code.
- Window settings (`setTitle`, `setSize`, `setFps`, `setFullscreen`) are fine at top level. They are applied when the window is created.
- Use `global` to change top-level variables from callbacks:

```python
time = 0
def onUpdate(dt):
    global time
    time += dt
```

- Closing the window ends the app. Errors in your code print a traceback and exit cleanly.

---

## lib.draw

All draw functions draw straight to the screen, in call order. Later calls draw on top.

### `lib.draw.line(Color, Weight, X1, Y1, X2, Y2)`

Line between two points. A `Weight` of 0 is treated as 1 pixel.

```python
lib.draw.line(0xFFFFFF, 3, 10, 10, 200, 120)
```

### `lib.draw.circle(Color, Weight, X, Y, Rad)`

Circle centered at `X, Y` with radius `Rad`.

```python
lib.draw.circle(0xFF8800, 0, 400, 300, 50)   # filled
lib.draw.circle(0xFFFFFF, 2, 400, 300, 50)   # 2px outline
```

### `lib.draw.ellipse(Color, Weight, X, Y, W, H)`

Ellipse fitting the box with top-left `X, Y` and size `W, H`.

### `lib.draw.rectangle(Color, Weight, X, Y, W, H)`

Rectangle with top-left `X, Y` and size `W, H`. Negative `W` or `H` extend left or up.

```python
lib.draw.rectangle(0x202020, 0, 0, 0, 800, 600)  # background
```

### `lib.draw.roundedRectangle(Color, Weight, X, Y, W, H, RX, RY=None)`

Rectangle with rounded corners. `RX` and `RY` are the corner radii. If `RY` is omitted it equals `RX`. Radii are clamped to half the size. Different `RX` and `RY` give elliptical corners.

```python
lib.draw.roundedRectangle(0x4D96FF, 0, 50, 50, 200, 80, 20, 20)
lib.draw.roundedRectangle(0x4D96FF, 3, 50, 150, 200, 80, 40, 10)
```

### `lib.draw.gradient(Color1, Color2, X, Y, W, H, Rad=0)`

Fills the rectangle at `X, Y` of size `W, H` with a linear gradient from `Color1` to `Color2`. `Rad` is the direction in radians: `0` = left to right, `math.pi / 2` = top to bottom. Both colors may carry alpha (fade to transparent works). Gradients are cached, so drawing the same one every frame is cheap.

```python
lib.draw.gradient(0x1A2A6C, 0xB21F1F, 0, 0, 800, 600, math.pi / 2)        # sky
lib.draw.gradient("#FFFFFF", "#FFFFFF00", 100, 100, 300, 80, 0)          # fade out to the right
```

### `lib.draw.setClip(X, Y, W, H)` / `lib.draw.clearClip()`

Restricts all drawing to a rectangle until `clearClip()`. Useful for scrolling areas. (The GUI library uses this.)

### `lib.draw.triangle(Color, Weight, X1, Y1, X2, Y2, X3, Y3)`

Triangle through three points.

### `lib.draw.polygon(Color, Weight, X1, Y1, X2, Y2, X3, Y3, ...)`

Polygon through any number of points. You can pass flat coordinates or a list of pairs.

```python
lib.draw.polygon(0xFF00FF, 0, 100, 100, 200, 100, 150, 180)
lib.draw.polygon(0xFF00FF, 0, [(100, 100), (200, 100), (150, 180)])

points = [100, 100, 200, 100, 150, 180]
lib.draw.polygon(0xFF00FF, 2, *points)
```

### `lib.draw.text(Color, Text, X, Y, Scale=16, HA="left", VA="top", File=None)`

Draws text aligned to the point `X, Y`.

| Argument | Meaning |
|---|---|
| `Scale` | Line height in pixels (approximately) |
| `HA` | Horizontal alignment: `"left"`, `"center"`, `"right"` |
| `VA` | Vertical alignment: `"top"`, `"middle"`, `"bottom"` |
| `File` | A font from `lib.file.font(...)`. `None` uses the built-in default font. |

`"\n"` starts a new line. In multi-line text each line is aligned according to `HA`.

```python
lib.draw.text(0xFFFFFF, "Score: 10", 20, 20, 24)
lib.draw.text(0xFFFFFF, "Centered", 400, 300, 40, "center", "middle")

font = lib.file.font("fonts/Pixel.ttf")   # at top level
lib.draw.text(0xFFFFFF, "Custom font", 20, 60, 32, "left", "top", font)
```

### `lib.draw.measureText(Text, Scale=16, File=None)`

Returns `(width, height)` in pixels of the text as it would be drawn. Draws nothing.

```python
w, h = lib.draw.measureText("Hello", 24)
lib.draw.rectangle(0x000000, 0, 20, 20, w, h)   # box behind the text
lib.draw.text(0xFFFFFF, "Hello", 20, 20, 24)
```

### `lib.draw.image(Mode, X, Y, File, Opacity=1, *args)`

Draws an image with its top-left at `X, Y`. `File` comes from `lib.file.image(...)`. `Opacity` is 0 to 1.

| Mode | Extra args | Meaning |
|---|---|---|
| `"scale"` | `scale` (default 1) | `1` = one screen pixel per image pixel, `2` = double size |
| `"size"` | `width, height` | Exact size in pixels. If `height` is omitted or `None`, the aspect ratio is kept. |

Negative scale or size values flip the image.

```python
sprite = lib.file.image("sprite.png")   # top level

def onUpdate(dt):
    lib.draw.image("scale", 100, 100, sprite, 1, 2)         # 2x
    lib.draw.image("size", 300, 100, sprite, 0.5, 64, 64)   # 64x64, half transparent
    lib.draw.image("size", 400, 100, sprite, 1, 64)         # 64 wide, height from aspect
    lib.draw.image("size", 500, 100, sprite, 1, -64, 64)    # flipped horizontally
```

The image object also has `.width` and `.height` (original pixel size).

---

## lib.sound

Sounds are loaded with `lib.file.audio(path)`, then played. Playing returns an id used to control that playing instance. Many sounds can play at once (64 channels, the oldest is cut off if all are busy).

If no audio device is available, `lib.sound` is disabled with a warning and `play` returns `-1`.

### `lib.sound.play(File, Looping=False, Volume=1.0, Speed=1.0, Pitch=1.0)`

Plays a sound and returns its id.

| Argument | Meaning |
|---|---|
| `File` | Object from `lib.file.audio(...)`. A path string also works. |
| `Looping` | Repeat forever |
| `Volume` | 0 to 1 |
| `Speed` | Tempo multiplier. `2` = twice as fast. Does **not** change pitch. |
| `Pitch` | Pitch multiplier. `2` = one octave up. Does **not** change tempo. |

`Speed` and `Pitch` are clamped to a minimum of 0.05. Changing them needs `numpy` (without it they are ignored with a warning). Processing happens when the sound starts and results are cached, so reusing the same values is cheap. Changing them every frame is not.

```python
beep = lib.file.audio("beep.wav")   # top level

def onUpdate(dt):
    if lib.keyPressed("Space"):
        lib.sound.play(beep)
        lib.sound.play(beep, False, 0.5, 1.0, lib.rand.float(0.8, 1.6))  # random pitch
        lib.sound.play(beep, False, 1.0, 1.5)                            # faster, same pitch
```

### `lib.sound.tone(length, frequency, type="sine", attack=0.01, release=0.05)`

Generates a tone in code, no sound file needed. Returns an audio object, so it works anywhere `lib.file.audio(...)` does: pass it to `lib.sound.play` and use Volume / Looping / Speed / Pitch as usual.

| Argument | Meaning |
|---|---|
| `length` | Duration in seconds |
| `frequency` | Pitch in Hz (ignored for `"noise"`) |
| `type` | `"sine"`, `"sawtooth"`, `"square"`, `"triangle"` or `"noise"` |
| `attack` | Fade-in time in seconds (linear ramp from silence) |
| `release` | Fade-out time in seconds (linear ramp to silence at the end) |

If `attack + release` is longer than `length`, both are shrunk to fit. An invalid `type`, `length <= 0` or `frequency <= 0` raises `ValueError`.

Results are cached by their arguments, so calling `tone(...)` right before every `play` is fine. Cache holds up to 1024 tones; round frequencies if you generate them continuously.

```python
# one-liners
lib.sound.play(lib.sound.tone(0.1, 440, "square"))                          # beep
lib.sound.play(lib.sound.tone(0.3, 220, "sawtooth", 0.01, 0.25), False, 0.5) # plucky note
lib.sound.play(lib.sound.tone(0.08, 0, "noise", 0.001, 0.07))               # hi-hat / hit

# musical: semitone n above A4
def note(n, length=0.3):
    return lib.sound.tone(length, 440 * 2 ** (n / 12), "triangle", 0.005, 0.2)

lib.sound.play(note(0))
lib.sound.play(note(4))
lib.sound.play(note(7))

# loop a tone (clicks at the loop point unless length is a whole number of cycles)
hum = lib.sound.play(lib.sound.tone(1.0, 100, "sine", 0, 0), True, 0.3)
```

Without `numpy`, tones are generated with a slower pure-Python fallback (fine for short sounds).

### `lib.sound.stop(id)`

Stops one sound. Unknown or finished ids are ignored.

### `lib.sound.stopall()`

Stops every sound.

### `lib.sound.setVolume(id, Volume)`
### `lib.sound.setSpeed(id, Speed)`
### `lib.sound.setPitch(id, Pitch)`

Change a playing sound. `setSpeed` and `setPitch` rebuild the sound and continue from the current position (a tiny click is possible).

### `lib.sound.isLooping(id, Bool=None)`

`lib.sound.isLooping(id, True)` sets looping. `lib.sound.isLooping(id)` returns whether it loops.

```python
music = lib.file.audio("music.ogg")
track = lib.sound.play(music, True, 0.5)
lib.sound.setPitch(track, 1.2)
lib.sound.isLooping(track, False)
lib.sound.stop(track)
```

Supported formats are whatever pygame's mixer loads (WAV, OGG, MP3 depending on your SDL build).

---

## Input

### Mouse

#### `lib.getMouse()`

Returns a list of mouse events. There is one event for each button that is currently held (or was released this update). With nothing held it returns `[]`.

Each event is a list:

```
[Id, X, Y, DX, DY, IX, IY, Action, Pressed, Released, Duration]
```

| Field | Meaning |
|---|---|
| `Id` | Unique to this event, never reused |
| `X`, `Y` | Current mouse position |
| `DX`, `DY` | Movement since the previous update |
| `IX`, `IY` | Position where the event began |
| `Action` | `"Left"`, `"Middle"` or `"Right"` |
| `Pressed` | `True` for exactly one update, the one where the button went down |
| `Released` | `True` for exactly one update, the last one in which the event appears |
| `Duration` | Seconds since the event began (0 on the first update) |

A click shorter than one frame shows up as one event with both `Pressed` and `Released` true.

```python
def onUpdate(dt):
    for e in lib.getMouse():
        id, x, y, dx, dy, ix, iy, action, pressed, released, duration = e
        if action == "Left":
            lib.draw.line(0xFF5555, 3, ix, iy, x, y)      # drag line
            if pressed:
                print("click at", x, y)
            if released:
                print("dragged for", duration, "seconds")
```

#### `lib.getMousePos()`

Extra, not part of the original spec. Returns `[x, y]` of the pointer even when nothing is clicked. Use it for hover effects.

#### `lib.getScroll()`

Returns the scroll wheel movement during this update as a number. Positive = scrolled up, `0` = none.

```python
zoom = 1.0
def onUpdate(dt):
    global zoom
    zoom = lib.clamp(zoom + lib.getScroll() * 0.1, 0.5, 4)
```

### Typed text

#### `lib.getText()`

Characters typed during this update as a string (keyboard layout, shift and IME already applied), or `""`. Use it for text fields; use `getKeys` for key-style input like movement. The GUI library's text boxes are built on it.

```python
name = ""
def onUpdate(dt):
    global name
    name += lib.getText()
    if lib.keyPressed("Backspace"):
        name = name[:-1]
```

### Keyboard

Key names refer to the key itself, before modifiers. Pressing Shift+A gives `"Shift"` and `"KeyA"` as two separate keys.

#### `lib.getKeys()`

Returns a list of key events, one per key currently held (or released this update):

```
[id, key, pressed, released, duration]
```

Same rules as mouse events: `pressed` and `released` are true for one update each, `id` is unique, `duration` is seconds since the key went down.

```python
for id, key, pressed, released, duration in lib.getKeys():
    if pressed:
        print(key, "went down")
```

#### `lib.keyDown(Key)`

Returns how long the key has been held, in seconds, or `None` if it is not held.

#### `lib.keyPressed(Key)`

`True` only during the update where the key went down.

#### `lib.keyReleased(Key)`

`True` only during the update where the key was released.

```python
x = 100
def onUpdate(dt):
    global x
    if lib.keyDown("Left") is not None:
        x -= 200 * dt
    if lib.keyDown("Right") is not None:
        x += 200 * dt
    if lib.keyPressed("Space"):
        print("jump")
    if lib.keyDown("Ctrl") is not None and lib.keyPressed("KeyS"):
        print("save")
```

#### Key names

| Group | Names |
|---|---|
| Letters | `KeyA` ... `KeyZ` |
| Digits | `Key0` ... `Key9` |
| Punctuation | `KeyBackslash`, `KeyApostrophe`, `KeyComma`, `KeyPeriod`, `KeySlash`, `KeySemicolon`, `KeyEquals`, `KeyMinus`, `KeyLeftBracket`, `KeyRightBracket`, `KeyGrave` |
| Editing | `Space`, `Enter`, `Tab`, `Backspace`, `Escape`, `Del`, `Insert` |
| Navigation | `Left`, `Right`, `Up`, `Down`, `Home`, `End`, `PageUp`, `PageDown` |
| Modifiers | `Shift`, `RightShift`, `Ctrl`, `RightCtrl`, `Alt`, `RightAlt`, `Super`, `RightSuper` |
| Function | `F1` ... `F15` |
| Keypad | `Num0` ... `Num9`, `NumEnter`, `NumPlus`, `NumMinus`, `NumMultiply`, `NumDivide`, `NumPeriod`, `NumEquals` |
| Other | `CapsLock`, `NumLock`, `ScrollLock`, `PrintScreen`, `Pause`, `Menu` |

Unlisted keys get a name of `"Key"` plus the pygame key name. The table lives in `_build_keynames()` in `lib.py` if you want to change names.

If the window loses focus, all held keys and buttons are released automatically.

---

## lib.file

Loading functions return objects you pass to other functions. Load assets at top level, not every frame.

### `lib.file.image(Path)`

Returns an image object for `lib.draw.image`. Has `.width` and `.height`.

### `lib.file.font(Path)`

Returns a font object (TTF/OTF) for `lib.draw.text` and `lib.draw.measureText`.

### `lib.file.audio(Path)`

Returns an audio object for `lib.sound.play`.

### `lib.file.rawBinary(Path)`

Returns the file contents as `bytes`.

### `lib.file.rawText(Path)`

Returns the file contents as a `str` (UTF-8).

### `lib.file.parseJson(Path)`

Parses a JSON file and returns the result (a `dict` or `list`).

```python
config = lib.file.parseJson("config.json")
level  = lib.file.rawText("level1.txt").split("\n")
data   = lib.file.rawBinary("save.dat")
```

### `lib.file.write(Path, Data)`

Writes a file. `str` is saved as UTF-8 text, `bytes` as-is, and `dict`/`list` as pretty JSON. Missing folders are created, and the write is atomic (temp file then rename), so a crash can't leave a half-written save.

```python
lib.file.write("saves/slot1.json", {"level": 3, "hp": 80})
lib.file.write("notes.txt", "hello")
data = lib.file.parseJson("saves/slot1.json")
```

A missing file when reading raises `FileNotFoundError`.

---

## Vectors

### Constructors

```python
lib.vec2(X, Y)
lib.vec3(X, Y, Z)
lib.vec4(X, Y, Z, W)
```

Also accepted: no arguments (all zeros), one number (all components equal), or one list/tuple/vector.

```python
a = lib.vec2(1, 2)
b = lib.vec2()        # (0, 0)
c = lib.vec3(5)       # (5, 5, 5)
d = lib.vec2([3, 4])
```

### Components

`.x`, `.y` (vec2); `.x`, `.y`, `.z` (vec3); `.x`, `.y`, `.z`, `.w` (vec4). They can be read and assigned. Vectors can be indexed (`v[0]`), iterated and unpacked.

```python
v = lib.vec2(3, 4)
v.x = 10
x, y = v
print(v[1])
```

### Arithmetic

`+  -  *  /  //  **  %` work component by component, between two vectors of the same size or between a vector and a number (either order). Results are new vectors. `-v` negates, `abs(v)` takes absolute values per component, and `==` compares.

```python
a = lib.vec2(1, 2)
b = lib.vec2(3, 4)
a + b        # vec2(4, 6)
a * 2        # vec2(2, 4)
10 - a       # vec2(9, 8)
b ** 2       # vec2(9, 16)
b % 2        # vec2(1, 0)
a * b        # vec2(3, 8), per component, not a dot product
```

Vectors are mutable. `a += b` creates a new vector and rebinds `a`, which means inside a function you need `global a` if `a` is a top-level variable.

### Methods

| Method | Returns |
|---|---|
| `v.length()` | Length of the vector |
| `v.dot(other)` | Dot product |
| `v.cross(other)` | Cross product (vec3 only) |
| `v.copy()` | Independent copy |

### `lib.dist(A, B)`

Distance between two vectors (or two equal-length lists).

```python
lib.dist(lib.vec2(0, 0), lib.vec2(3, 4))   # 5.0
```

### `lib.norm(Vector)`

Returns the vector scaled to length 1. A zero vector is returned unchanged.

```python
direction = lib.norm(target - position)
position = position + direction * speed * dt
```

---

## Essentials

### `lib.lerp(A, B, T)`

Linear interpolation: `A + (B - A) * T`. `T = 0` gives `A`, `T = 1` gives `B`. Works on numbers and on vectors. `T` is not clamped.

```python
lib.lerp(0, 100, 0.25)                           # 25
lib.lerp(lib.vec2(0, 0), lib.vec2(10, 20), 0.5)  # vec2(5, 10)
```

### `lib.clamp(Val, Min, Max)`

Limits a number to the range `[Min, Max]`.

### `lib.sign(Value)`

`-1` if negative, `0` if zero, `1` if positive.

### Trigonometry (radians)

`lib.sin  lib.cos  lib.tan  lib.asin  lib.acos  lib.atan  lib.atan2(Y, X)  lib.sinh  lib.cosh  lib.tanh  lib.asinh  lib.acosh  lib.atanh`

```python
import math
angle = lib.atan2(dy, dx)
x = lib.cos(angle) * 100
degrees = angle * 180 / math.pi
```

---

## lib.time

### `lib.time.frame()`

Frame counter: `0` during the first `onUpdate`, then `+1` every frame.

```python
if lib.time.frame() % 30 == 0:
    print("twice a second at 60 fps")
```

### `lib.time.unix()`

Seconds since 1970-01-01 as a float.

### `lib.time.civil()`

Local date and time as `[year, month, day, hour, minute, second]`.

```python
year, month, day, hour, minute, second = lib.time.civil()
```

For frame timing use the `dt` passed to `onUpdate`.

---

## lib.rand

### `lib.rand.float(min, max)`

Random float between `min` and `max`.

### `lib.rand.int(min, max)`

Random integer from `min` to `max`, both inclusive.

### `lib.rand.choice(*args)`

Picks one of the arguments. A single list or tuple argument is also accepted.

```python
lib.rand.choice("red", "green", "blue")
lib.rand.choice(["a", "b", "c"])
```

### `lib.rand.gauss(mean, sigma)`

Normally distributed random number.

### `lib.rand.perlin(x, y, z=0)`

Smooth Perlin noise, returned in the range 0 to 1. Nearby inputs give nearby outputs. The same input always gives the same output (the noise table is fixed). Use `z` as a third axis, for example time.

```python
# wavy terrain
for i in range(0, 800, 4):
    n = lib.rand.perlin(i * 0.01, 0)
    lib.draw.rectangle(0x44AA66, 0, i, 400 - n * 100, 4, n * 100)

# animated noise
n = lib.rand.perlin(x * 0.05, y * 0.05, time)
```

---

## lib.collision

### `lib.collision.query(Primitive1, Primitive2)`

Returns `True` if the two primitives overlap or touch, else `False`. Argument order does not matter. Every combination of the five primitives is supported.

| Primitive | Format |
|---|---|
| Point | `["point", X, Y]` |
| Ray | `["ray", X1, Y1, X2, Y2]` (a finite segment between the two points) |
| Rect | `["rect", X, Y, W, H]` (top-left corner, negative sizes allowed) |
| Circle | `["circle", X, Y, R]` (center, radius) |
| Triangle | `["triangle", X1, Y1, X2, Y2, X3, Y3]` (any winding) |

Edges count as touching.

```python
mx, my = lib.getMousePos()
if lib.collision.query(["point", mx, my], ["rect", 100, 100, 200, 50]):
    lib.draw.rectangle(0xFFFF00, 0, 100, 100, 200, 50)

hit = lib.collision.query(["circle", px, py, 20], ["circle", ex, ey, 30])
blocked = lib.collision.query(["ray", x1, y1, x2, y2], ["rect", wx, wy, ww, wh])
```

Only yes/no is returned, not the contact point or normal.

---

## lib.window

### `lib.window.setIcon(File)`

Sets the window icon from an image (`lib.file.image(...)`, or a path). Square images around 64x64 work best. Safe to call at top level.

### `lib.window.setTitle(Text)`

Sets the window title.

### `lib.window.setSize(width, height)`

Sets the window size in pixels (windowed mode). The user can still resize the window afterwards. `onResize` is called with the actual size.

### `lib.window.setFps(Int)`

Frame rate cap. `0` removes the cap. Default is 60.

### `lib.window.setFullscreen(Bool)`

Switches fullscreen on or off. Fullscreen uses the desktop resolution. Leaving it restores the previous windowed size. `onResize` is called after the switch.

```python
def onUpdate(dt):
    if lib.keyPressed("F11"):
        fullscreen = not fullscreen        # keep this variable at top level, with `global`
        lib.window.setFullscreen(fullscreen)
```

### `lib.window.setCursor(Cursor)`

Sets the mouse cursor. Cheap to call every frame (repeat calls with the same name do nothing).

| Name | Shown as |
|---|---|
| `default` | arrow |
| `pointer` | hand |
| `wait` | busy |
| `progress` | busy with arrow |
| `text` | I-beam |
| `not-allowed` | no symbol |
| `help` | arrow (no help cursor in pygame) |
| `crosshair` | crosshair |
| `move` | four-way arrows |
| `ns-resize` | vertical resize |
| `ew-resize` | horizontal resize |
| `nsew-resize` | four-way arrows |
| `copy` | hand (no copy cursor in pygame) |
| `alias` | hand (no alias cursor in pygame) |

An unknown name raises `ValueError`.

---

## lib.json

### `lib.json.compile(Value, Indent=None)`

dict/list to a JSON string. `Indent` (an int) pretty-prints.

### `lib.json.parse(Text)`

JSON string to dict/list/number/string.

```python
text = lib.json.compile({"a": [1, 2, 3]})   # '{"a": [1, 2, 3]}'
data = lib.json.parse(text)
```

---

## Notes and limits

- **Alpha.** Translucent shapes are slower than opaque ones (they go through a scratch surface), fine for dozens per frame, not thousands.
- **Window creation is lazy.** Draw calls before the first frame create the window early at the current size settings.
- **Outlines.** Thick outlines on ellipses and polygons are approximate. Polygons get rounded joins.
- **Text rendering** is cached per string, color and size, so repeated text is cheap, but changing text every frame (counters) renders new surfaces. This is fine at normal sizes.
- **Sound Speed/Pitch** quality: tempo changes use simple overlap-add, which can sound slightly phasey at extreme values. Pitch uses linear resampling.
- **Sound position tracking** after `setSpeed` / `setPitch` is estimated from elapsed time, not read from the mixer, so it can drift a few milliseconds.
- **Mouse events** only report held buttons. Use `getMousePos()` for hover. There is no touch or gamepad support.
- **Platform.** Targets desktop, tested on Linux-style SDL setups. Fullscreen and cursor behavior depend on your window manager.
- **Adding file handlers.** `lib.py` has a `_HANDLERS` dict near the bottom mapping file extensions to functions, which is where custom file types (for example custom editors) would be registered.

---

## Demos

Run any demo from the app folder:

```
python lib.py demos/sort.py
```

| File | Shows |
|---|---|
| `demos/sort.py` | Shell sort of 500 values (shuffled 1-500 to 500-1) with a tone per step. 500 filled rectangles per frame + sound stress test. Up/Down speed, Space reshuffle, T waveform, M mute |
| `demos/pong.py` | Neon pong: translucent glow, fading trails, sparks, shockwaves, screen shake, squash/stretch, gradient synthwave backdrop, chromatic text, alpha scanlines, procedural sound. W/S, arrows or mouse |
| `demos/wireframe.py` | 2D wireframe renderer for `.obj` files (software 3D to `lib.draw.line`). Includes `cube`, `icosphere`, `torus`, `knot`; drop in your own. Drag rotate, scroll zoom, Left/Right model, M mode, P projection, V verts, F flip winding |
| `demos/roguelike.py` | Endless roguelike: lazily generated rooms and hallways, enemies that heal you on death and scale over time, uses `lib.collision.query` for walls, melee, projectiles, contact damage and line of sight. WASD + mouse, R restarts |
| `demos/synth.py` | Tone Lab: playable synth on `lib.sound.tone` with waveform buttons, attack/release/length sliders, piano keys (keyboard or mouse), oscilloscope and arpeggiator |
| `demos/easing.py` | Every `ease` function (10 families x in/out/inout) as circles travelling left to right and back, with fading trails. Hover for the curve. Space, Up/Down, Left/Right, T |
| `demos/rubble.py` | Pile of convex and concave polygon rocks you can drag (`world.pick` + `world.grab`). R new pile, Space shake, T triangles, K rk4 |
| `demos/stress.py` | Physics stress test: balls rain into a box. FPS, ball/contact counts, step time and graphs. Toggles for spawning, rk4, gravity, substeps, rate, delete all |
| `demos/gui_demo.py` | Fake game menu (modals, resizable windows, table, chart, file tree, pickers, loading screen) using many gui widgets |
| `demos/gui_showcase.py` | Every gui widget in an accordion, each with a note on how it works |
| `demos/save.py` | Orb Garden idle clicker built around save data: slots, autosave, versioned JSON + migration, `.bak` recovery from corrupt files, offline progress. Writes to `demos/saves/` |
| `files/main.py` | Original small API tour using UV coordinates |

Demo notes:

- Window-size independent: sort/wireframe/synth/roguelike use fractions of the window, pong fits a fixed 1600x900 playfield into the window.
- With no alpha channel, glow and fades are faked by mixing colors toward the background.
- `wireframe.py` auto-detects inside-out face winding on closed meshes; press `F` if a model still looks wrong.


---

# Separate libraries

Separate libraries are built on BaitLib and live next to `lib.py` instead of inside it: `ease.py`, `physics.py` and the `gui/` folder. `lib.py` adds its own folder to `sys.path`, so `import ease`, `import physics` and `import gui` work from any app. Each also registers itself on the library (`lib.ease`, `lib.physics`, `lib.gui`) once imported.

---

## ease

Easing functions. 10 families x in / out / inout = 30 functions. Each takes progress `t` (0 to 1, clamped) and returns eased progress. `back` and `elastic` overshoot on purpose.

```python
import ease

x = lib.lerp(100, 500, ease.out.bounce(t))
y = lib.lerp(0, 300, lib.ease.inout.cubic(t))      # same thing through lib
```

| Family | Notes |
|---|---|
| `sine` `quad` `cubic` `quart` `quint` | increasingly sharp polynomial curves |
| `expo` | exponential, very sharp |
| `circ` | quarter circle |
| `back` | pulls back first (in) or overshoots (out) |
| `elastic` | springy wobble |
| `bounce` | bouncing ball |

Access: `ease.in_.NAME`, `ease.out.NAME`, `ease.inout.NAME`.

**`in` is a Python keyword**, so `ease.in.sine` can't be written. The group is called `in_` (`ease.in_.sine`). `getattr(ease, "in")` and `ease.get("in", "sine")` work too.

Extras: `ease.names` (list of families), `ease.linear(t)`, `ease.get(kind, name)` for lookups from data:

```python
fn = ease.get("out", "elastic")
for name in ease.names:
    f = ease.out.__dict__[name]
```

---

## physics

2D rigid body physics. Bodies are made of **circles and triangles** (rects can't rotate, so boxes and polygons are built from triangles; concave polygons are triangulated automatically). Overlap detection uses `lib.collision.query`; contact normals, depth and contact points are then computed and solved with sequential impulses (friction, restitution, spin).

```python
import physics

physics.enableRk4(True)                       # accurate integration

world = physics.World(gravity=(0, 900))       # pixels / s^2, +y down
world.boundary(0, 0, 800, 600)                # four static walls around a rectangle
ball = world.circle(300, 100, 20, restitution=0.7)
rock = world.polygon([(-30, -10), (0, -40), (35, -5), (10, 30)], x=500, y=200)
crate = world.box(400, 300, 60, 60, angle=0.3)

def onUpdate(dt):
    world.step(dt)
    for b in world.bodies:
        b.draw(fill=0x4C8DFF, outline=0xFFFFFF, marker=0xFFFFFF)
```

### `physics.enableRk4(on=True)`

Switches the integrator for **all** worlds.

| | Method | Use |
|---|---|---|
| `False` (default) | semi-implicit Euler | fast, fine for gravity and collisions |
| `True` | 4th order Runge-Kutta | forces are sampled 4x per substep, so velocity-dependent forces (drag, springs, orbits, mouse grabs) stay accurate even with big steps |

Constant gravity is already exact with both, collisions are impulse-based either way. `physics.rk4Enabled()` reads the flag.

### `physics.World(gravity=(0, 900), iterations=8, substeps=2, cell=96)`

| Attribute | Meaning |
|---|---|
| `gravity` | `(gx, gy)` |
| `iterations` | solver passes per substep, higher = stiffer stacks |
| `substeps` | physics steps per `step()` call, higher = fewer tunnelling/jitter issues |
| `cell` | broadphase grid size, about the size of a typical body |
| `linear_damping`, `angular_damping` | drag per second (a body can override them) |
| `bounce_threshold` | slower impacts don't bounce (default 40) |
| `forces` | list of callbacks `fn(body, x, y, angle, vx, vy, w) -> (fx, fy[, torque])` evaluated at every integrator stage |
| `on_collision` | `fn(a, b, x, y, impact_speed)` fired for hard hits (`impact_threshold`, default 120) |
| `bodies`, `contact_count` | the bodies, and contacts solved last substep |

Methods:

| Method | Does |
|---|---|
| `step(dt, substeps=None)` | advance the world (dt is capped at 1/20 s) |
| `circle(x, y, r, angle=0, **opts)` | circle |
| `box(x, y, w, h, angle=0, **opts)` | box centered on x, y |
| `triangle(x1, y1, x2, y2, x3, y3, **opts)` | triangle from world points |
| `polygon(points, x=0, y=0, angle=0, **opts)` | polygon, points relative to x, y; convex or concave |
| `boundary(x, y, w, h, thickness=60)` | static walls around a rectangle |
| `remove(body)`, `clear(keep_static=False)` | delete bodies |
| `pick(x, y)` | topmost dynamic body under a point |
| `query(primitive)` | bodies overlapping any `lib.collision` primitive (point, ray, rect, circle, triangle) |
| `grab(body, x, y, stiffness=120, damping=14)` | spring joint to a world target (mouse drag), see below |

Creation options (`**opts`): `density=1`, `restitution=0.3`, `friction=0.5`, `static=False`, `group=0` (bodies sharing a nonzero group don't collide), `gravity_scale=1`, `linear_damping`, `angular_damping`.

### Body

| Member | Meaning |
|---|---|
| `x, y, angle` | center of mass and rotation |
| `vx, vy, w` | linear and angular velocity |
| `mass, inertia, static` | `set_static(bool)` changes it |
| `restitution, friction, group, gravity_scale, user` | tweakable; `user` is a free dict for your data |
| `apply_force(fx, fy, px=None, py=None)` | force for the next step (optionally at a world point, which adds torque) |
| `apply_impulse(ix, iy, px=None, py=None)` | instant velocity change |
| `contains(x, y)` | point test |
| `shapes()` | world space primitives, usable with `lib.collision.query` |
| `outline_points()` | world space outline of a polygon/box, else `None` |
| `world_point(lx, ly)`, `local_point(wx, wy)` | convert between body-local (relative to center of mass) and world |
| `speed()`, `kinetic_energy()` | handy for debugging |
| `draw(fill=None, outline=None, weight=1, marker=None)` | convenience drawing with BaitLib colors |

### Dragging bodies

```python
grab = None
def onUpdate(dt):
    global grab
    mx, my = lib.getMousePos()
    for e in lib.getMouse():
        if e[7] == "Left" and e[8]:                       # pressed
            body = world.pick(mx, my)
            if body:
                grab = world.grab(body, mx, my)
        if e[7] == "Left" and e[9] and grab:              # released
            grab.release()
            grab = None
    if grab:
        grab.move(mx, my)
    world.step(dt)
```

### Custom forces

```python
def wind(body, x, y, angle, vx, vy, w):
    return (200 * body.mass, 0)           # constant push

def planet(body, x, y, angle, vx, vy, w):
    dx, dy = 400 - x, 300 - y
    d2 = max(dx * dx + dy * dy, 400)
    k = 5e6 * body.mass / d2 ** 1.5
    return (dx * k, dy * k)               # orbits are where RK4 pays off

world.forces.append(planet)
```

Tips: use `world.substeps = 4` for thin walls or fast bodies, `iterations = 12` for tall stacks. There is no sleeping, so very large piles cost the same when at rest. `physics.triangulate(points)` is public if you want the triangles yourself.

---

## gui

A widget library. Widgets are retained objects (create once, add to a `UI`, update and draw every frame).

```python
import gui

ui = gui.UI()
ui.add(gui.Button(20, 20, 140, 36, text="Click me", primary=True,
                  on_click=lambda b: ui.toast("Hello!", kind="success")))
name = ui.add(gui.TextBox(20, 70, 240, placeholder="Your name"))

def onUpdate(dt):
    lib.draw.rectangle(0x14171F, 0, 0, 0, 800, 600)
    ui.update(dt)      # input, hover, focus, animation
    ui.draw()
```

Conventions:

- Every widget takes `(x, y, w, h)` first, then keyword options. Positions of children are **relative to their container**.
- Every widget also accepts `style={...}`, `enabled=True`, `visible=True`, `tooltip=None`, `name=None`.
- Callbacks are plain functions: `on_click(widget)`, `on_change(value)`, etc. Values live in `.value` unless noted.
- `w` / `h` of `None` (Button, Checkbox, Radio, Label, ...) means fit the content.
- Call `ui.update(dt)` before drawing, and draw your own background first.

### UI

| Method | Does |
|---|---|
| `ui.add(*widgets)`, `ui.remove(w)` | top level widgets (drawn in order, last = on top) |
| `ui.update(dt)`, `ui.draw()` | per frame |
| `ui.show(modal)`, `ui.close(modal)` | modal dialogs (block everything below, Esc closes) |
| `ui.alert(title, message, on_close=None)` | quick OK dialog |
| `ui.confirm(title, message, on_yes, on_no)` | quick Cancel / Confirm dialog |
| `ui.toast(text, duration=3, kind="info")` | notification bottom right. kind: `info` `success` `warning` `danger` |
| `ui.set_focus(w)` | keyboard focus. Tab / Shift+Tab cycle, clicking focuses |
| `ui.theme` | the theme used (default is the shared `gui.theme`) |
| `ui.focus`, `ui.hover` | current focused / hovered widget |

Keyboard: text widgets read `lib.getText()` and keys with auto repeat, so widgets work with the keyboard when focused (arrows, Enter, Space, Home/End, PageUp/Down). Copy/paste works inside the app and through the system clipboard when pygame supports it.

### Widget base

Attributes: `x y w h`, `style`, `enabled`, `visible`, `tooltip`, `name`, `parent`, `children`, `hover`, `pressed`, `focused`, `ax`/`ay` (absolute position).
Methods: `add(*children)`, `remove(child)`, `bring_to_front()`, `focus()`, `blur()`, `rect()`.

### Basic widgets

| Widget | Constructor options | Notes |
|---|---|---|
| `Label` | `text, color, size, align="left", mono=False` | `set_text(s)`. Passes mouse through |
| `Button` | `text, on_click, primary=False` | Enter/Space when focused |
| `ToggleButton` | Button options + `value, on_change` | stays pressed |
| `Checkbox` | `text, value, on_change` | |
| `Switch` | `value, text, on_change` | animated knob |
| `Radio` | `text, group, key` | `group = gui.RadioGroup(value, on_change)`, selected when `group.value == key` |
| `Slider` | `min, max, value, step, vertical, show_value, fmt, on_change` | keyboard arrows when focused |
| `Progress` | `value, min, max, show_text, fmt, animated` | determinate bar |
| `Spinner` | `size, dots, speed` | rotating busy indicator |
| `LoadingBar` | `speed` | indeterminate bar |
| `Separator` | `vertical` | line |
| `Panel` | | plain container |

```python
group = gui.RadioGroup("easy", on_change=lambda k: print("mode", k))
ui.add(gui.Radio(20, 20, text="Easy", group=group, key="easy"),
       gui.Radio(20, 50, text="Hard", group=group, key="hard"))
```

### Text input

| Widget | Constructor options | Notes |
|---|---|---|
| `TextBox` | `text, placeholder, on_change, on_submit, max_length, password, filter, read_only` | one line. `filter(char) -> bool` restricts input |
| `TextArea` | same, multi-line | scroll, selection, undo/redo (Ctrl+Z / Ctrl+Y) |
| `CodeBox` | `lang="python", text, line_numbers, tab_size` | monospace, syntax highlighting, Tab indent, auto indent |
| `CodeBlock` | `text, lang, line_numbers, auto_height` | read-only code with a Copy button |
| `Spinbox` | `value, min, max, step, decimals, on_change` | arrows, wheel, Up/Down, type a number |
| `ComboBox` | `options, text, placeholder, on_change, strict` | type to filter suggestions |

All text widgets support mouse selection, double-click word select, triple-click line, Ctrl+A/C/X/V, Shift+arrows, Ctrl+arrows for words. `.value` is the text.

Languages: `python`, `lua`, `javascript`, `c`, `json`. Add your own:

```python
gui.add_language("sql", keywords=["select", "from", "where", "join"], comment="--")
ui.add(gui.CodeBox(20, 20, 400, 200, lang="sql", text="select * from t"))
```

### Containers

| Widget | Constructor options | Notes |
|---|---|---|
| `Accordion` | `exclusive=False, gap` | `section = acc.add_section(title, open=False, height=None)`, then `section.add(widget)` (positions relative to the body). `height=None` fits the content |
| `Splitter` | `first, second, vertical=False, ratio, min_size, on_resize` | two panes with a draggable divider |
| `Carousel` | `pages, autoplay=0, on_change` | arrows, dots, slide animation. `.go(i)` |
| `Modal` | `title, w, h, message, buttons=[(label, callback, primary)], closable, draggable, on_close` | use with `ui.show(modal)`. `modal.add(widget)` is relative to below the title bar |
| `Resizable` | `title, movable, min_w, min_h, max_w, max_h, on_resize, layout` | window you can drag by the title and resize from any edge. `layout(self)` re-arranges children |
| `ScrollView` | `border` | vertical scrolling container, content height is measured |

```python
acc = gui.Accordion(20, 20, 320)
sec = acc.add_section("Audio", open=True)
sec.add(gui.Slider(10, 10, 280, min=0, max=100, value=70, show_value=True))
sec.add(gui.Checkbox(10, 46, text="Mute"))
ui.add(acc)

m = gui.Modal(title="Quit?", w=360, h=170, message="Unsaved changes will be lost.",
              buttons=[("Cancel", None, False), ("Quit", do_quit, True)])
ui.show(m)
```

### Data and navigation

| Widget | Constructor options | Notes |
|---|---|---|
| `Dropdown` | `options, index, placeholder, on_change(value, index)` | options: `["a", "b"]` or `[("Label", value), ...]`. `.value`, `.index`, `.select(i)` |
| `DataTable` | `columns, rows, sortable, zebra, on_select(index, row), on_sort, resizable_columns` | columns: `"Name"` or `{"title", "key", "width", "align", "fmt", "sortable"}`; rows: lists or dicts. Click header to sort, drag its edge to resize. `.selected`, `.selected_row()`, `.set_rows(rows)` |
| `FileTree` | `nodes, on_select(node), on_open(node)` | `nodes` is a nested dict (dict = folder, other = file). `FileTree.from_path(dir)` scans a real folder. `node.name`, `node.path`, `node.is_folder`. `.expand_all()` |
| `Breadcrumb` | `items, on_click(index, label)` | long paths collapse to `...` |
| `Chart` | `kind, series, labels, title, legend, grid, y_min, y_max, colors, animated` | kinds `line`, `area`, `bar`, `scatter`, `pie`, `donut`. Hover for values. `.set_series(...)` |

```python
ui.add(gui.DataTable(20, 20, 420, 220,
        columns=["Name", {"title": "Qty", "width": 70, "align": "right"}],
        rows=[["Apple", 3], ["Pear", 7]],
        on_select=lambda i, row: print(row)))

ui.add(gui.Chart(20, 260, 360, 220, kind="bar", title="Sales",
        series=[{"name": "2025", "values": [3, 5, 4]}, {"name": "2026", "values": [4, 6, 7]}],
        labels=["Q1", "Q2", "Q3"]))
```

### Pickers

| Widget | Value | Notes |
|---|---|---|
| `DatePicker` | `datetime.date` | field + calendar popup. `fmt="%Y-%m-%d"` |
| `TimePicker` | `datetime.time` | `seconds=False, use_24h=True` |
| `DateTimePicker` | `datetime.datetime` | calendar + time in one popup |
| `ColorPicker` | `[r, g, b, a]` floats 0-1 | field with swatch + popup. `.hex`. The value works directly as a BaitLib color |
| `Calendar`, `TimeSelector`, `ColorPanel` | same as above | the inline (always visible) versions |

All take `on_change(value)` and `value=` in the constructor.

```python
ui.add(gui.DatePicker(20, 20, 200, value=datetime.date.today(),
                      on_change=lambda d: print("picked", d)))
cp = ui.add(gui.ColorPicker(20, 70, 200, value="#4C8DFF"))
lib.draw.rectangle(cp.value, 0, 240, 70, 40, 34)     # use the color directly
```

### Styling

Everything reads its look from style keys. A key is looked up in this order, first match wins:

1. the widget's own `style` dict
2. the theme entry for its class (`"Button"`, then base classes)
3. the theme default `"*"`

At every level a state variant beats the plain key: `key_disabled`, `key_active` (pressed), `key_focus`, `key_hover`.

```python
gui.theme.set("*", accent=0xFF6B6B, radius=12, font_size=18)            # everything
gui.theme.set("Button", bg=0x303030, bg_hover=0x404040, fg=0xFFFFFF)    # all buttons
btn.style.update(bg=0x00AA00, bg_hover=0x00CC00, radius=0)               # one widget

ui = gui.UI(gui.Theme.light())          # built-in light theme (also Theme.dark())
mine = gui.theme.copy()                 # independent copy to modify
```

Main keys (all overridable):

| Group | Keys |
|---|---|
| text | `fg`, `fg_muted`, `fg_disabled`, `font` (a `lib.file.font`), `font_size`, `mono_font`, `mono_size` |
| surfaces | `bg`, `bg_hover`, `bg_active`, `bg_disabled`, `border`, `border_hover`, `border_focus`, `border_disabled`, `border_w`, `radius`, `pad` |
| accent | `accent`, `accent_hover`, `accent_active`, `accent_fg`, `track` |
| status | `success`, `warning`, `danger`, `info` |
| containers | `panel_bg`, `panel_border`, `popup_bg`, `popup_border`, `overlay`, `shadow` |
| lists / text | `row_alt`, `row_hover`, `row_selected`, `selection`, `caret` |
| syntax | `syn_default`, `syn_keyword`, `syn_string`, `syn_comment`, `syn_number`, `syn_function`, `syn_builtin`, `syn_gutter` |

Colors may carry alpha (use strings like `"#4C8DFF66"`). Helpers: `gui.mix(c1, c2, t)`, `gui.shade(c, k)`, `gui.alpha(c, a)`, `gui.box(...)`, `gui.icon(...)`.

### Layout helpers

`gui.vstack(widgets, x, y, w=None, gap=8)` and `gui.hstack(widgets, x, y, h=None, gap=8)` place widgets in a column / row and return the total size.

### Writing your own widget

```python
class Meter(gui.Widget):
    def __init__(self, x, y, w=200, h=20, value=0.5, **kw):
        super().__init__(x, y, w, h, **kw)
        self.value = value

    def draw(self):                                   # self.ax / self.ay = absolute position
        gui.box(self.ax, self.ay, self.w, self.h, self.get("track"), None, 0, 6)
        gui.box(self.ax, self.ay, self.w * self.value, self.h, self.get("accent"), None, 0, 6)

    def mouse_down(self, x, y, button, clicks):       # also: mouse_drag, mouse_up, click, wheel,
        self.value = (x - self.ax) / self.w           # text_input, key_down(key, mods), update(dt)
```

Set `focusable = True` to receive keys and text, `cursor = "pointer"` for the hover cursor, `clip_children = True` for containers that should clip.

### Notes

- Popups (dropdown lists, pickers) and toasts draw above everything; modals dim the screen and block input behind them.
- Text rendering uses BaitLib's default font unless you set `font`. Code boxes use a system monospace font when one is found (DejaVu Sans Mono, Consolas, Menlo...).
- `lib.draw.setClip` is used for scrolling and clipping, so don't leave a clip set when calling `ui.draw()`.
- IME composition, drag and drop and right-click menus are not implemented.
