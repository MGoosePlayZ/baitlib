"""
Easing functions for BaitLib (separate library, not part of lib.py).

    import ease                       # also registers itself as lib.ease
    ease.out.bounce(0.5)              # same as lib.ease.out.bounce(0.5)

Every function takes progress t (0..1, clamped) and returns the eased progress. Back and elastic
overshoot outside 0..1 on purpose. Use it with lib.lerp:

    x = lib.lerp(100, 500, ease.inout.cubic(t))

Families: sine quad cubic quart quint expo circ back elastic bounce
Variants: ease.in_.NAME  ease.out.NAME  ease.inout.NAME

`in` is a Python keyword, so `lib.ease.in.sine` is a syntax error. The "in" group is therefore
`in_` (`ease.in_.sine`). `getattr(ease, "in")` and `ease.get("in", "sine")` also work.
"""
import math
import sys

import lib

_PI = math.pi


def _power(p):
    def f_in(t):
        return t ** p

    def f_out(t):
        return 1 - (1 - t) ** p

    def f_inout(t):
        return 2 ** (p - 1) * t ** p if t < 0.5 else 1 - (-2 * t + 2) ** p / 2

    return f_in, f_out, f_inout


def _sine():
    return (lambda t: 1 - math.cos(t * _PI / 2),
            lambda t: math.sin(t * _PI / 2),
            lambda t: -(math.cos(_PI * t) - 1) / 2)


def _expo():
    def f_in(t):
        return 0.0 if t == 0 else 2 ** (10 * t - 10)

    def f_out(t):
        return 1.0 if t == 1 else 1 - 2 ** (-10 * t)

    def f_inout(t):
        if t == 0 or t == 1:
            return t
        return 2 ** (20 * t - 10) / 2 if t < 0.5 else (2 - 2 ** (-20 * t + 10)) / 2

    return f_in, f_out, f_inout


def _circ():
    return (lambda t: 1 - math.sqrt(1 - t * t),
            lambda t: math.sqrt(1 - (t - 1) ** 2),
            lambda t: (1 - math.sqrt(1 - (2 * t) ** 2)) / 2 if t < 0.5
            else (math.sqrt(1 - (-2 * t + 2) ** 2) + 1) / 2)


def _back():
    c1 = 1.70158
    c2, c3 = c1 * 1.525, c1 + 1
    return (lambda t: c3 * t ** 3 - c1 * t ** 2,
            lambda t: 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2,
            lambda t: ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2 if t < 0.5
            else ((2 * t - 2) ** 2 * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2)


def _elastic():
    c4, c5 = 2 * _PI / 3, 2 * _PI / 4.5

    def f_in(t):
        return t if t in (0, 1) else -(2 ** (10 * t - 10)) * math.sin((10 * t - 10.75) * c4)

    def f_out(t):
        return t if t in (0, 1) else 2 ** (-10 * t) * math.sin((10 * t - 0.75) * c4) + 1

    def f_inout(t):
        if t in (0, 1):
            return t
        if t < 0.5:
            return -(2 ** (20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2
        return (2 ** (-20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2 + 1

    return f_in, f_out, f_inout


def _bounce():
    def f_out(t):
        n1, d1 = 7.5625, 2.75
        if t < 1 / d1:
            return n1 * t * t
        if t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        if t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        t -= 2.625 / d1
        return n1 * t * t + 0.984375

    return (lambda t: 1 - f_out(1 - t),
            f_out,
            lambda t: (1 - f_out(1 - 2 * t)) / 2 if t < 0.5 else (1 + f_out(2 * t - 1)) / 2)


def _clamped(f, name):
    def g(t):
        return f(0.0 if t < 0 else 1.0 if t > 1 else t)
    g.__name__ = name
    return g


class _Group:
    """Namespace holding one variant of every family (ease.out.bounce, ...)."""


in_, out, inout = _Group(), _Group(), _Group()
_FAMILIES = {
    "sine": _sine(), "quad": _power(2), "cubic": _power(3), "quart": _power(4), "quint": _power(5),
    "expo": _expo(), "circ": _circ(), "back": _back(), "elastic": _elastic(), "bounce": _bounce(),
}
names = list(_FAMILIES)

for _name, (_i, _o, _io) in _FAMILIES.items():
    setattr(in_, _name, _clamped(_i, "in_" + _name))
    setattr(out, _name, _clamped(_o, "out_" + _name))
    setattr(inout, _name, _clamped(_io, "inout_" + _name))

globals()["in"] = in_       # getattr(ease, "in") works even though `ease.in` can't be written
In, Out, InOut = in_, out, inout


def linear(t):
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def get(kind, name):
    """get("in" | "out" | "inout", "bounce") -> function. Handy when the names come from data."""
    group = {"in": in_, "in_": in_, "out": out, "inout": inout}[kind.lower()]
    return getattr(group, name)


lib.ease = sys.modules[__name__]
