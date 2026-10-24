"""
2D rigid body physics for BaitLib (separate library, not part of lib.py).

    import physics
    physics.enableRk4(True)                    # accurate integration (default: quick semi-implicit Euler)

    world = physics.World(gravity=(0, 900))    # pixels / second^2, +y is down like the screen
    world.boundary(0, 0, 1000, 700)            # four static walls around a rectangle
    ball = world.circle(300, 100, 20, restitution=0.6)
    rock = world.polygon([(-30, -10), (0, -40), (35, -5), (10, 30)], x=500, y=200)   # concave is fine
    world.box(400, 650, 800, 40, static=True)

    def onUpdate(dt):
        world.step(dt)
        for b in world.bodies:
            b.draw(fill=0x4C8DFF)

Shapes are circles and triangles only (rect primitives can't rotate). Boxes and polygons are built from
triangles (ear clipping, so concave polygons work). Overlap detection runs through lib.collision.query,
then contact normals / depth / contact points are computed here and solved with sequential impulses
(friction, restitution, angular motion).

Units are pixels, seconds, radians. Angles follow the screen (positive = clockwise on screen).
"""
import math
import sys

import lib

_rk4 = False


def enableRk4(on=True):
    """True: 4th order Runge-Kutta integration of every body's motion (forces are sampled 4x per
    substep, so drag, springs, force fields and mouse grabs are much more accurate, about 3x the
    force cost). False: quick semi-implicit Euler."""
    global _rk4
    _rk4 = bool(on)


def rk4Enabled():
    return _rk4


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


# ====================================================================== geometry
def triangulate(points):
    """Ear clipping. points: [(x, y), ...] simple polygon (convex or concave, any winding).
    Returns a list of triangles [(p1, p2, p3), ...]."""
    pts = [tuple(p) for p in points]
    n = len(pts)
    if n < 3:
        return []
    area = sum(_cross(pts[i][0], pts[i][1], pts[(i + 1) % n][0], pts[(i + 1) % n][1]) for i in range(n))
    idx = list(range(n)) if area >= 0 else list(range(n))[::-1]
    tris, guard = [], 0
    while len(idx) > 3 and guard < n * n:
        guard += 1
        m = len(idx)
        for k in range(m):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % m]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if _cross(b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]) <= 1e-9:
                continue                                    # reflex or collinear: not an ear
            if any(pts[j] not in (a, b, c) and lib.collision.query(["point", *pts[j]], ["triangle", *a, *b, *c])
                   for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((a, b, c))
            del idx[k]
            break
        else:
            idx.pop(0)                                      # degenerate input: drop a vertex and go on
    if len(idx) == 3:
        a, b, c = (pts[i] for i in idx)
        if abs(_cross(b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1])) > 1e-9:
            tris.append((a, b, c))
    return tris


def _tri_pts(t):
    return [(t[1], t[2]), (t[3], t[4]), (t[5], t[6])]


# ---- contact manifolds. Every function returns (nx, ny, [(px, py, depth), ...]) with the normal pointing
# from the first shape to the second, or None.
def _m_cc(A, B):
    dx, dy = B[1] - A[1], B[2] - A[2]
    rr = A[3] + B[3]
    d2 = dx * dx + dy * dy
    if d2 >= rr * rr:
        return None
    d = math.sqrt(d2)
    if d < 1e-9:
        nx, ny, depth = 0.0, 1.0, rr
    else:
        nx, ny, depth = dx / d, dy / d, rr - d
    k = A[3] - depth / 2
    return nx, ny, [(A[1] + nx * k, A[2] + ny * k, depth)]


def _m_tc(T, C):
    cx, cy, r = C[1], C[2], C[3]
    p = _tri_pts(T)
    best, bn = -1e18, (0.0, 1.0)
    cl_d, cl = 1e18, (0.0, 0.0)
    for i in range(3):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % 3]
        ex, ey = x2 - x1, y2 - y1
        l2 = ex * ex + ey * ey
        if l2 < 1e-12:
            continue
        l = math.sqrt(l2)
        nx, ny = ey / l, -ex / l
        sep = (cx - x1) * nx + (cy - y1) * ny
        if sep > best:
            best, bn = sep, (nx, ny)
        t = max(0.0, min(1.0, ((cx - x1) * ex + (cy - y1) * ey) / l2))      # closest point on this edge
        qx, qy = x1 + ex * t, y1 + ey * t
        d = math.hypot(cx - qx, cy - qy)
        if d < cl_d:
            cl_d, cl = d, (qx, qy)
    if best > r:
        return None
    if best < 0:                                                           # centre inside the triangle
        return bn[0], bn[1], [(cx - bn[0] * best, cy - bn[1] * best, r - best)]
    if cl_d >= r:
        return None
    if cl_d < 1e-9:
        return bn[0], bn[1], [(cl[0], cl[1], r)]
    return (cx - cl[0]) / cl_d, (cy - cl[1]) / cl_d, [(cl[0], cl[1], r - cl_d)]


def _m_ct(C, T):
    m = _m_tc(T, C)
    return None if m is None else (-m[0], -m[1], m[2])


def _separation(P, Q):
    """largest (least negative) separation of Q from the edge planes of P, and which edge"""
    best, bi = -1e18, 0
    for i in range(3):
        x1, y1 = P[i]
        x2, y2 = P[(i + 1) % 3]
        ex, ey = x2 - x1, y2 - y1
        l = math.hypot(ex, ey)
        if l < 1e-12:
            continue
        nx, ny = ey / l, -ex / l
        s = min((qx - x1) * nx + (qy - y1) * ny for qx, qy in Q)
        if s > best:
            best, bi = s, i
    return best, bi


def _clip(seg, nx, ny, c):
    d0 = nx * seg[0][0] + ny * seg[0][1] - c
    d1 = nx * seg[1][0] + ny * seg[1][1] - c
    out = []
    if d0 <= 0:
        out.append(seg[0])
    if d1 <= 0:
        out.append(seg[1])
    if d0 * d1 < 0:
        t = d0 / (d0 - d1)
        out.append((seg[0][0] + (seg[1][0] - seg[0][0]) * t, seg[0][1] + (seg[1][1] - seg[0][1]) * t))
    return out


def _m_tt(A, B):
    P, Q = _tri_pts(A), _tri_pts(B)
    sa, ia = _separation(P, Q)
    if sa > 0:
        return None
    sb, ib = _separation(Q, P)
    if sb > 0:
        return None
    if sb > sa + 0.1:                      # reference polygon = the one with the shallower axis
        R, I, ri, flip = Q, P, ib, True
    else:
        R, I, ri, flip = P, Q, ia, False
    p1, p2 = R[ri], R[(ri + 1) % 3]
    tx, ty = p2[0] - p1[0], p2[1] - p1[1]
    l = math.hypot(tx, ty) or 1.0
    tx, ty = tx / l, ty / l
    nx, ny = ty, -tx                        # outward normal of the reference edge
    j_best, d_best = 0, 1e18
    for j in range(3):                      # incident edge: the one facing most against the normal
        x1, y1 = I[j]
        x2, y2 = I[(j + 1) % 3]
        ex, ey = x2 - x1, y2 - y1
        el = math.hypot(ex, ey) or 1.0
        d = (ey / el) * nx + (-ex / el) * ny
        if d < d_best:
            j_best, d_best = j, d
    seg = [I[j_best], I[(j_best + 1) % 3]]
    seg = _clip(seg, -tx, -ty, -(tx * p1[0] + ty * p1[1]))
    if len(seg) < 2:
        return None
    seg = _clip(seg, tx, ty, tx * p2[0] + ty * p2[1])
    pts = []
    for vx, vy in seg:
        sep = (vx - p1[0]) * nx + (vy - p1[1]) * ny
        if sep <= 0:
            pts.append((vx, vy, -sep))
    if not pts:
        return None
    return (-nx, -ny, pts) if flip else (nx, ny, pts)


_MANIFOLD = {("circle", "circle"): _m_cc, ("circle", "triangle"): _m_ct,
             ("triangle", "circle"): _m_tc, ("triangle", "triangle"): _m_tt}


# ====================================================================== bodies
class Body:
    """A rigid body: one or more circles/triangles that move together.
    Read/write: x, y (centre of mass), angle, vx, vy, w (angular velocity), restitution, friction,
    linear_damping, angular_damping, gravity_scale, group, user (free dict).
    Read only: mass, inertia, static, shapes()."""

    def __init__(self, world, shapes, x, y, angle, density, restitution, friction, static, outline=None):
        self.world = world
        self.restitution, self.friction = restitution, friction
        self.linear_damping = self.angular_damping = None      # None = use the world's
        self.gravity_scale = 1.0
        self.group = 0
        self.user = {}
        self.static = static
        self.vx = self.vy = self.w = 0.0
        self.fx = self.fy = self.torque = 0.0
        self.angle = angle

        parts, mass, cx, cy = [], 0.0, 0.0, 0.0
        for s in shapes:
            if s[0] == "circle":
                _, sx, sy, r = s
                m = density * math.pi * r * r
                parts.append((s, m, 0.5 * m * r * r, sx, sy))
            else:
                _, x1, y1, x2, y2, x3, y3 = s
                cr = _cross(x2 - x1, y2 - y1, x3 - x1, y3 - y1)
                if cr < 0:                                      # keep triangles in one winding
                    s = ("triangle", x1, y1, x3, y3, x2, y2)
                    _, x1, y1, x2, y2, x3, y3 = s
                m = density * abs(cr) / 2
                sides = ((x2 - x1) ** 2 + (y2 - y1) ** 2) + ((x3 - x2) ** 2 + (y3 - y2) ** 2) + ((x1 - x3) ** 2 + (y1 - y3) ** 2)
                parts.append((s, m, m * sides / 36, (x1 + x2 + x3) / 3, (y1 + y2 + y3) / 3))
            mass += parts[-1][1]
            cx += parts[-1][1] * parts[-1][3]
            cy += parts[-1][1] * parts[-1][4]
        if mass <= 0:
            raise ValueError("body has no area")
        cx, cy = cx / mass, cy / mass
        inertia = sum(i + m * ((sx - cx) ** 2 + (sy - cy) ** 2) for _, m, i, sx, sy in parts)
        self.mass, self.inertia = mass, inertia
        self.local = []                                         # shapes relative to the centre of mass
        for s, *_ in parts:
            if s[0] == "circle":
                self.local.append(("circle", s[1] - cx, s[2] - cy, s[3]))
            else:
                self.local.append(("triangle", s[1] - cx, s[2] - cy, s[3] - cx, s[4] - cy, s[5] - cx, s[6] - cy))
        self._outline = None if outline is None else [(px - cx, py - cy) for px, py in outline]
        ca, sa = math.cos(angle), math.sin(angle)
        self.x, self.y = x + cx * ca - cy * sa, y + cx * sa + cy * ca
        self.radius = max(math.hypot(s[1], s[2]) + s[3] if s[0] == "circle" else
                          max(math.hypot(s[i], s[i + 1]) for i in (1, 3, 5)) for s in self.local)
        self._set_static(static)
        self.ws = []
        self.aabb = (0, 0, 0, 0)

    def _set_static(self, static):
        self.static = static
        self.im = 0.0 if static else 1.0 / self.mass
        self.ii = 0.0 if static else 1.0 / self.inertia

    def set_static(self, static=True):
        self._set_static(bool(static))
        if static:
            self.vx = self.vy = self.w = 0.0

    # ---- world space
    def update_shapes(self):
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        x, y = self.x, self.y
        out, x0, y0, x1, y1 = [], 1e18, 1e18, -1e18, -1e18
        for s in self.local:
            if s[0] == "circle":
                wx, wy, r = x + s[1] * ca - s[2] * sa, y + s[1] * sa + s[2] * ca, s[3]
                sh = ("circle", wx, wy, r)
                a0, b0, a1, b1 = wx - r, wy - r, wx + r, wy + r
            else:
                v = []
                for i in (1, 3, 5):
                    v += [x + s[i] * ca - s[i + 1] * sa, y + s[i] * sa + s[i + 1] * ca]
                sh = ("triangle", *v)
                a0, b0, a1, b1 = min(v[0::2]), min(v[1::2]), max(v[0::2]), max(v[1::2])
            out.append((sh, a0, b0, a1, b1))
            x0, y0, x1, y1 = min(x0, a0), min(y0, b0), max(x1, a1), max(y1, b1)
        self.ws = out
        self.aabb = (x0, y0, x1, y1)

    def shapes(self):
        """collision primitives in world space, usable with lib.collision.query"""
        self.update_shapes()
        return [list(s[0]) for s in self.ws]

    def outline_points(self):
        """world space outline of a polygon/box body (None for circles and raw triangles)"""
        if self._outline is None:
            return None
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        return [(self.x + px * ca - py * sa, self.y + px * sa + py * ca) for px, py in self._outline]

    def world_point(self, lx, ly):
        """body local point (relative to the centre of mass) -> world"""
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        return self.x + lx * ca - ly * sa, self.y + lx * sa + ly * ca

    def local_point(self, wx, wy):
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        dx, dy = wx - self.x, wy - self.y
        return dx * ca + dy * sa, -dx * sa + dy * ca

    def contains(self, x, y):
        self.update_shapes()
        return any(lib.collision.query(["point", x, y], list(s[0])) for s in self.ws)

    # ---- forces
    def apply_force(self, fx, fy, px=None, py=None):
        """force in newton-ish units (mass * px/s^2) for the next step(); optional world point of application"""
        self.fx += fx
        self.fy += fy
        if px is not None:
            self.torque += _cross(px - self.x, py - self.y, fx, fy)

    def apply_impulse(self, ix, iy, px=None, py=None):
        self.vx += ix * self.im
        self.vy += iy * self.im
        if px is not None:
            self.w += _cross(px - self.x, py - self.y, ix, iy) * self.ii

    def speed(self):
        return math.hypot(self.vx, self.vy)

    def kinetic_energy(self):
        return 0.5 * self.mass * (self.vx ** 2 + self.vy ** 2) + 0.5 * self.inertia * self.w ** 2

    # ---- drawing convenience
    def draw(self, fill=None, outline=None, weight=1, marker=None):
        """fill / outline are BaitLib colors (alpha ok). marker draws a tick showing rotation."""
        pts = self.outline_points()
        if fill is not None:
            if pts is not None and len(self.local) > 1:                 # compound: fill the triangles
                for s in self.shapes():
                    lib.draw.triangle(fill, 0, *s[1:])
            else:
                for s in self.shapes():
                    if s[0] == "circle":
                        lib.draw.circle(fill, 0, s[1], s[2], s[3])
                    else:
                        lib.draw.triangle(fill, 0, *s[1:])
        if outline is not None:
            if pts is not None:
                lib.draw.polygon(outline, weight, *[c for p in pts for c in p])
            else:
                for s in self.shapes():
                    if s[0] == "circle":
                        lib.draw.circle(outline, weight, s[1], s[2], s[3])
                    else:
                        lib.draw.triangle(outline, weight, *s[1:])
        if marker is not None:
            x2, y2 = self.world_point(self.radius * 0.6, 0)
            lib.draw.line(marker, max(1, weight), self.x, self.y, x2, y2)


class Grab:
    """Spring joint between a point on a body and a target in the world (a mouse drag).
    Created with world.grab(body, x, y). Call .move(x, y) every frame and .release() when done."""

    def __init__(self, world, body, wx, wy, stiffness, damping):
        self.world, self.body = world, body
        self.lx, self.ly = body.local_point(wx, wy)
        self.tx, self.ty = wx, wy
        self.k = body.mass * stiffness
        self.c = body.mass * damping

    def move(self, x, y):
        self.tx, self.ty = x, y

    def release(self):
        if self in self.world.grabs:
            self.world.grabs.remove(self)


# ====================================================================== world
class World:
    def __init__(self, gravity=(0, 900), iterations=8, substeps=2, cell=96):
        self.gravity = tuple(gravity)
        self.iterations = iterations
        self.substeps = substeps
        self.cell = cell                     # broadphase grid cell size, roughly your typical body size
        self.linear_damping = 0.0            # per second, drag proportional to velocity
        self.angular_damping = 0.02
        self.bodies = []
        self.forces = []                     # callbacks fn(body, x, y, angle, vx, vy, w) -> (fx, fy, torque) or None
        self.grabs = []
        self.on_collision = None             # fn(a, b, x, y, impact_speed), fired for hard hits
        self.impact_threshold = 120.0
        self.bounce_threshold = 40.0         # slower impacts don't bounce
        self.bias = 0.2                      # Baumgarte factor for pushing overlaps apart
        self.slop = 0.5
        self.contact_count = 0

    # ---- creating bodies
    def _add(self, shapes, x, y, angle, o, outline=None):
        b = Body(self, shapes, x, y, angle, o.get("density", 1.0), o.get("restitution", 0.3),
                 o.get("friction", 0.5), o.get("static", False), outline)
        b.group = o.get("group", 0)
        b.gravity_scale = o.get("gravity_scale", 1.0)
        b.linear_damping, b.angular_damping = o.get("linear_damping"), o.get("angular_damping")
        b.update_shapes()
        self.bodies.append(b)
        return b

    def circle(self, x, y, r, angle=0.0, **opts):
        """opts: density, restitution, friction, static, group, gravity_scale, linear_damping, angular_damping"""
        return self._add([("circle", 0.0, 0.0, r)], x, y, angle, opts)

    def triangle(self, x1, y1, x2, y2, x3, y3, **opts):
        """points are world coordinates"""
        return self._add([("triangle", x1, y1, x2, y2, x3, y3)], 0, 0, 0.0, opts)

    def box(self, x, y, w, h, angle=0.0, **opts):
        """centred on x, y"""
        hw, hh = w / 2, h / 2
        pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return self._add([("triangle", *pts[0], *pts[1], *pts[2]), ("triangle", *pts[0], *pts[2], *pts[3])],
                         x, y, angle, opts, pts)

    def polygon(self, points, x=0.0, y=0.0, angle=0.0, **opts):
        """points relative to (x, y). Concave polygons are split into triangles."""
        tris = triangulate(points)
        if not tris:
            raise ValueError("polygon needs at least 3 non-collinear points")
        return self._add([("triangle", *a, *b, *c) for a, b, c in tris], x, y, angle, opts, [tuple(p) for p in points])

    def boundary(self, x, y, w, h, thickness=60, **opts):
        """four static walls just outside the rectangle (x, y, w, h)"""
        opts = dict(opts, static=True)
        t = thickness
        return [self.box(x + w / 2, y - t / 2, w + 2 * t, t, **opts), self.box(x + w / 2, y + h + t / 2, w + 2 * t, t, **opts),
                self.box(x - t / 2, y + h / 2, t, h + 2 * t, **opts), self.box(x + w + t / 2, y + h / 2, t, h + 2 * t, **opts)]

    def remove(self, body):
        if body in self.bodies:
            self.bodies.remove(body)
        for g in [g for g in self.grabs if g.body is body]:
            g.release()

    def clear(self, keep_static=False):
        self.bodies = [b for b in self.bodies if keep_static and b.static]
        self.grabs = [g for g in self.grabs if g.body in self.bodies]

    # ---- queries
    def query(self, primitive):
        """bodies overlapping any lib.collision primitive (point, ray, rect, circle, triangle)"""
        out = []
        for b in self.bodies:
            b.update_shapes()
            if any(lib.collision.query(primitive, list(s[0])) for s in b.ws):
                out.append(b)
        return out

    def pick(self, x, y, dynamic_only=True):
        """topmost (last created) body under a point"""
        for b in reversed(self.bodies):
            if (b.static and dynamic_only):
                continue
            x0, y0, x1, y1 = b.aabb
            if x0 <= x <= x1 and y0 <= y <= y1 and b.contains(x, y):
                return b
        return None

    def grab(self, body, x, y, stiffness=120.0, damping=14.0):
        g = Grab(self, body, x, y, stiffness, damping)
        self.grabs.append(g)
        return g

    # ---- dynamics
    def _deriv(self, b, x, y, a, vx, vy, w):
        ld = b.linear_damping if b.linear_damping is not None else self.linear_damping
        ad = b.angular_damping if b.angular_damping is not None else self.angular_damping
        im, ii = b.im, b.ii
        ax = b.fx * im + self.gravity[0] * b.gravity_scale - vx * ld
        ay = b.fy * im + self.gravity[1] * b.gravity_scale - vy * ld
        al = b.torque * ii - w * ad
        for fn in self.forces:
            r = fn(b, x, y, a, vx, vy, w)
            if r:
                ax += r[0] * im
                ay += r[1] * im
                if len(r) > 2:
                    al += r[2] * ii
        if self.grabs:
            ca, sa = math.cos(a), math.sin(a)
            for g in self.grabs:
                if g.body is b:
                    rx, ry = g.lx * ca - g.ly * sa, g.lx * sa + g.ly * ca
                    px, py = x + rx, y + ry
                    ux, uy = vx - w * ry, vy + w * rx            # velocity of the anchor point
                    fx = g.k * (g.tx - px) - g.c * ux
                    fy = g.k * (g.ty - py) - g.c * uy
                    ax += fx * im
                    ay += fy * im
                    al += _cross(rx, ry, fx, fy) * ii
        return ax, ay, al

    def _integrate(self, b, h):
        x, y, a, vx, vy, w = b.x, b.y, b.angle, b.vx, b.vy, b.w
        d = self._deriv
        if _rk4:
            ax1, ay1, al1 = d(b, x, y, a, vx, vy, w)
            k1 = (vx, vy, w, ax1, ay1, al1)
            s = (x + k1[0] * h / 2, y + k1[1] * h / 2, a + k1[2] * h / 2, vx + k1[3] * h / 2, vy + k1[4] * h / 2, w + k1[5] * h / 2)
            a2 = d(b, *s)
            k2 = (s[3], s[4], s[5], *a2)
            s = (x + k2[0] * h / 2, y + k2[1] * h / 2, a + k2[2] * h / 2, vx + k2[3] * h / 2, vy + k2[4] * h / 2, w + k2[5] * h / 2)
            a3 = d(b, *s)
            k3 = (s[3], s[4], s[5], *a3)
            s = (x + k3[0] * h, y + k3[1] * h, a + k3[2] * h, vx + k3[3] * h, vy + k3[4] * h, w + k3[5] * h)
            a4 = d(b, *s)
            k4 = (s[3], s[4], s[5], *a4)
            b.x += h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            b.y += h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            b.angle += h / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
            b.vx += h / 6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
            b.vy += h / 6 * (k1[4] + 2 * k2[4] + 2 * k3[4] + k4[4])
            b.w += h / 6 * (k1[5] + 2 * k2[5] + 2 * k3[5] + k4[5])
        else:
            ax, ay, al = d(b, x, y, a, vx, vy, w)
            b.vx += ax * h
            b.vy += ay * h
            b.w += al * h
            b.x += b.vx * h
            b.y += b.vy * h
            b.angle += b.w * h

    def _pairs(self):
        grid, c = {}, self.cell
        for b in self.bodies:
            x0, y0, x1, y1 = b.aabb
            for cy in range(int(y0 // c), int(y1 // c) + 1):
                for cx in range(int(x0 // c), int(x1 // c) + 1):
                    grid.setdefault((cx, cy), []).append(b)
        seen, pairs = set(), []
        for cell in grid.values():
            n = len(cell)
            for i in range(n):
                a = cell[i]
                for j in range(i + 1, n):
                    b = cell[j]
                    if a.static and b.static:
                        continue
                    key = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
                    if key in seen:
                        continue
                    seen.add(key)
                    if a.group and a.group == b.group:
                        continue
                    ax0, ay0, ax1, ay1 = a.aabb
                    bx0, by0, bx1, by1 = b.aabb
                    if ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1:
                        pairs.append((a, b))
        return pairs

    def _contacts(self, pairs):
        query = lib.collision.query
        out = []
        for a, b in pairs:
            for sa, ax0, ay0, ax1, ay1 in a.ws:
                for sb, bx0, by0, bx1, by1 in b.ws:
                    if ax0 > bx1 or bx0 > ax1 or ay0 > by1 or by0 > ay1:
                        continue
                    if not query(sa, sb):                  # the library says if they touch ...
                        continue
                    m = _MANIFOLD[(sa[0], sb[0])](sa, sb)  # ... we work out where and how deep
                    if m is None:
                        continue
                    nx, ny, pts = m
                    for px, py, depth in pts:
                        out.append(_Contact(a, b, nx, ny, px, py, depth))
        return out

    def _solve(self, contacts, h):
        bt, bias, slop = self.bounce_threshold, self.bias, self.slop
        for c in contacts:
            a, b = c.a, c.b
            nx, ny = c.nx, c.ny
            c.rax, c.ray, c.rbx, c.rby = c.px - a.x, c.py - a.y, c.px - b.x, c.py - b.y
            rna, rnb = _cross(c.rax, c.ray, nx, ny), _cross(c.rbx, c.rby, nx, ny)
            c.mn = 1.0 / (a.im + b.im + rna * rna * a.ii + rnb * rnb * b.ii)
            tx, ty = -ny, nx
            rta, rtb = _cross(c.rax, c.ray, tx, ty), _cross(c.rbx, c.rby, tx, ty)
            k = a.im + b.im + rta * rta * a.ii + rtb * rtb * b.ii
            c.mt = 1.0 / k if k > 0 else 0.0
            vn = ((b.vx - b.w * c.rby) - (a.vx - a.w * c.ray)) * nx + ((b.vy + b.w * c.rbx) - (a.vy + a.w * c.rax)) * ny
            c.vn0 = vn
            e = a.restitution if a.restitution > b.restitution else b.restitution
            c.target = max(-e * vn if vn < -bt else 0.0, min(bias / h * max(c.depth - slop, 0.0), 400.0))
            c.mu = math.sqrt(a.friction * b.friction)
        for _ in range(self.iterations):
            for c in contacts:
                a, b = c.a, c.b
                nx, ny = c.nx, c.ny
                rax, ray, rbx, rby = c.rax, c.ray, c.rbx, c.rby
                # normal
                vn = ((b.vx - b.w * rby) - (a.vx - a.w * ray)) * nx + ((b.vy + b.w * rbx) - (a.vy + a.w * rax)) * ny
                lam = (c.target - vn) * c.mn
                nj = c.jn + lam
                if nj < 0.0:
                    nj = 0.0
                lam = nj - c.jn
                c.jn = nj
                px, py = nx * lam, ny * lam
                a.vx -= px * a.im
                a.vy -= py * a.im
                a.w -= (rax * py - ray * px) * a.ii
                b.vx += px * b.im
                b.vy += py * b.im
                b.w += (rbx * py - rby * px) * b.ii
                # friction
                tx, ty = -ny, nx
                vt = ((b.vx - b.w * rby) - (a.vx - a.w * ray)) * tx + ((b.vy + b.w * rbx) - (a.vy + a.w * rax)) * ty
                lam = -vt * c.mt
                mx = c.mu * c.jn
                nt = c.jt + lam
                nt = -mx if nt < -mx else mx if nt > mx else nt
                lam = nt - c.jt
                c.jt = nt
                px, py = tx * lam, ty * lam
                a.vx -= px * a.im
                a.vy -= py * a.im
                a.w -= (rax * py - ray * px) * a.ii
                b.vx += px * b.im
                b.vy += py * b.im
                b.w += (rbx * py - rby * px) * b.ii

    def step(self, dt, substeps=None):
        """Advance the simulation. Large dt values are split into substeps (default self.substeps)."""
        n = max(1, substeps or self.substeps)
        h = min(dt, 1 / 20) / n
        hits = {}
        for _ in range(n):
            for b in self.bodies:
                if not b.static:
                    self._integrate(b, h)
            for b in self.bodies:
                b.update_shapes()
            contacts = self._contacts(self._pairs())
            self.contact_count = len(contacts)
            self._solve(contacts, h)
            if self.on_collision:
                for c in contacts:
                    if -c.vn0 >= self.impact_threshold:
                        k = (id(c.a), id(c.b))
                        if -c.vn0 > hits.get(k, (0,))[0]:
                            hits[k] = (-c.vn0, c.a, c.b, c.px, c.py)
        for b in self.bodies:
            b.fx = b.fy = b.torque = 0.0
        for speed, a, b, x, y in hits.values():
            self.on_collision(a, b, x, y, speed)


class _Contact:
    __slots__ = ("a", "b", "nx", "ny", "px", "py", "depth", "rax", "ray", "rbx", "rby", "mn", "mt", "vn0",
                 "target", "mu", "jn", "jt")

    def __init__(self, a, b, nx, ny, px, py, depth):
        self.a, self.b, self.nx, self.ny, self.px, self.py, self.depth = a, b, nx, ny, px, py, depth
        self.jn = self.jt = 0.0


lib.physics = sys.modules[__name__]
