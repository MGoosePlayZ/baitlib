# 2D wireframe renderer: loads .obj files from this folder and draws them as lines with a tiny
# software 3D pipeline (rotate -> perspective -> lib.draw.line). Drop your own .obj next to this file.
#
# Drag: rotate   Scroll: zoom   Left/Right: model   M: draw mode   P: perspective/ortho
# V: vertex dots   F: flip face winding   Space: pause spin
import math
import os

lib.window.setTitle("BaitLib - wireframe")
lib.window.setSize(1000, 700)
lib.window.setFps(60)

width, height, unit = 1000, 700, 700
yaw, pitch = 0.6, 0.35
yaw_v = 0.0
spin = True
zoom = 1.0
mode = 0                       # 0 all edges, 1 front faces only (hidden-line approximation)
MODES = ["all edges (depth cued)", "front faces only"]
show_verts = False
cam = 3.0                      # camera distance, animates between perspective (3) and ortho (60)
cam_target = 3.0
time = 0.0


def mix(a, b, k):
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]


class Model:
    def __init__(self, path):
        self.name = os.path.basename(path)
        verts, faces = [], []
        for line in lib.file.rawText(path).splitlines():
            p = line.split()
            if not p:
                continue
            if p[0] == "v" and len(p) >= 4:
                verts.append([float(p[1]), float(p[2]), float(p[3])])
            elif p[0] == "f" and len(p) >= 4:
                idx = []
                for tok in p[1:]:
                    i = int(tok.split("/")[0])
                    idx.append(i - 1 if i > 0 else len(verts) + i)   # negative = relative
                faces.append(idx)
        # center on the bounding box and scale into a unit sphere
        lo = [min(v[k] for v in verts) for k in range(3)]
        hi = [max(v[k] for v in verts) for k in range(3)]
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        r = max(math.sqrt(sum((v[k] - c[k]) ** 2 for k in range(3))) for v in verts) or 1
        self.verts = [[(v[k] - c[k]) / r for k in range(3)] for v in verts]
        self.faces = faces
        self.auto_orient()
        self.build_edges()

    def auto_orient(self):
        """Sum of dot(face normal, centroid) is 3x the enclosed volume: negative = inside-out."""
        total = 0.0
        for f in self.faces:
            a, b, c = (self.verts[i] for i in f[:3])
            n = cross(sub(b, a), sub(c, a))
            total += dot(n, a)
        if total < 0:
            self.flip()

    def flip(self):
        self.faces = [f[::-1] for f in self.faces]

    def build_edges(self):
        edges = {}
        for fi, f in enumerate(self.faces):
            for k in range(len(f)):
                a, b = f[k], f[(k + 1) % len(f)]
                edges.setdefault((min(a, b), max(a, b)), []).append(fi)
        self.edges = list(edges.items())            # ((a, b), [face ids])


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


models = [Model(f) for f in sorted(os.listdir(".")) if f.lower().endswith(".obj")]
current = 0


def rotate(v, cy, sy, cp, sp):
    x, y, z = v
    x, z = x * cy + z * sy, -x * sy + z * cy       # yaw around Y
    y, z = y * cp - z * sp, y * sp + z * cp        # pitch around X
    return x, y, z


def onResize(w, h):
    global width, height, unit
    width, height, unit = w, h, min(w, h)


def onUpdate(dt):
    global yaw, pitch, yaw_v, spin, zoom, mode, show_verts, cam, cam_target, time, current
    time += dt

    # ---- input
    if lib.keyPressed("Right"):
        current = (current + 1) % len(models)
    if lib.keyPressed("Left"):
        current = (current - 1) % len(models)
    if lib.keyPressed("KeyM"):
        mode = (mode + 1) % len(MODES)
    if lib.keyPressed("KeyV"):
        show_verts = not show_verts
    if lib.keyPressed("Space"):
        spin = not spin
    if lib.keyPressed("KeyP"):
        cam_target = 60.0 if cam_target < 10 else 3.0
    if lib.keyPressed("KeyF"):
        models[current].flip()
    zoom = lib.clamp(zoom * 1.1 ** lib.getScroll(), 0.3, 4)
    cam += (cam_target - cam) * min(1, dt * 6)

    dragging = False
    for e in lib.getMouse():
        if e[7] == "Left":
            dragging = True
            yaw += e[3] * 0.01
            pitch = lib.clamp(pitch + e[4] * 0.01, -1.5, 1.5)
            yaw_v = e[3] * 0.01 / max(dt, 1e-3)
    if not dragging:
        yaw += yaw_v * dt
        yaw_v += ((0.5 if spin else 0.0) - yaw_v) * min(1, dt * 1.5)   # glide back to the idle spin

    # ---- transform
    m = models[current]
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    k = unit * 0.36 * zoom * cam                  # screen size of a unit at the focal plane
    cx, cyc = width / 2, height / 2
    sx_, sy_, dz = [], [], []
    cams = []                                      # camera-space points, kept for facing tests
    for v in m.verts:
        x, y, z = rotate(v, cy, sy, cp, sp)
        d = cam - z
        cams.append((x, y, z))
        dz.append(d)
        sx_.append(cx + x * k / d)
        sy_.append(cyc - y * k / d)
    near, far = min(dz), max(dz)
    span = (far - near) or 1

    front = None
    if mode == 1:
        front = []
        eye = (0, 0, cam)
        for f in m.faces:
            a, b, c = cams[f[0]], cams[f[1]], cams[f[2]]
            n = cross(sub(b, a), sub(c, a))
            front.append(dot(n, sub(eye, a)) > 0)

    # ---- draw
    lib.draw.rectangle(0x0A0E14, 0, 0, 0, width, height)
    for i in range(1, 8):                          # soft floor rings for a sense of space
        lib.draw.ellipse(0x121A24, 1, cx - unit * 0.09 * i * zoom, cyc + unit * 0.3 * zoom - unit * 0.025 * i * zoom,
                         unit * 0.18 * i * zoom, unit * 0.05 * i * zoom)

    far_col, near_col = [0.08, 0.28, 0.26], [0.45, 1.0, 0.85]
    drawn = 0
    for (a, b), fs in m.edges:
        if front is not None and not any(front[fi] for fi in fs):
            continue
        depth = 1 - ((dz[a] + dz[b]) / 2 - near) / span        # 1 = closest
        lib.draw.line(mix(far_col, near_col, depth), 1, sx_[a], sy_[a], sx_[b], sy_[b])
        drawn += 1
    if show_verts:
        for i in range(len(m.verts)):
            depth = 1 - (dz[i] - near) / span
            lib.draw.circle(mix(far_col, [1, 0.8, 0.3], depth), 0, sx_[i], sy_[i], 1 + 2 * depth)

    # axis gizmo
    ox, oy = width * 0.08, height - unit * 0.1
    for axis, col in (((1, 0, 0), 0xFF5050), ((0, 1, 0), 0x50FF70), ((0, 0, 1), 0x5090FF)):
        x, y, z = rotate(axis, cy, sy, cp, sp)
        lib.draw.line(col, 2, ox, oy, ox + x * unit * 0.06, oy - y * unit * 0.06)

    s = unit * 0.032
    lib.draw.text(0xE8F4F0, f"{m.name}   ({current + 1}/{len(models)})", width * 0.025, height * 0.03, s * 1.3)
    info = (f"{len(m.verts)} verts   {len(m.edges)} edges ({drawn} drawn)   {len(m.faces)} faces   "
            f"{MODES[mode]}   {'perspective' if cam_target < 10 else 'orthographic'}")
    lib.draw.text("#7FA89E", info, width * 0.025, height * 0.03 + s * 1.7, s * 0.75)
    lib.draw.text("#556", "drag rotate   scroll zoom   </> model   M mode   P projection   V verts   F flip   space spin",
                  width / 2, height - 10, s * 0.7, "center", "bottom")
