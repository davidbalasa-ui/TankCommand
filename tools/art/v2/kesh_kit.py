"""Shared Kesh pieces: layered shell hulls, crescent fins, energy barrels, core orbs."""
import math
import random

from mathutils import Vector

import forge as F
from forge import body, box, crescent, cyl, lensfn, orb, shell, sweep, tube


def plate(fn, u0, u1, vc, vw, zone, trim=True, lines=1, **kw):
    """One armour leaf with a gold lip showing all round its edge and fine gold lines inlaid along it."""
    shell(fn, u0, u1, vc, vw, zone, **kw)
    off, thick = kw.get('off', 0.05), kw.get('thick', 0.07)
    k2 = {a: b for a, b in kw.items() if a not in ('off', 'thick', 'nv')}
    if trim:
        shell(fn, u0 - 0.008, u1 + 0.012, vc, vw + 4.5, 'gold', off=off - 0.028, thick=0.04, nv=kw.get('nv', 6), **k2)
    du = u1 - u0
    marks = [(0.0, 0.07, 0.93)] + ([(0.27, 0.3, 0.72), (-0.27, 0.3, 0.72)] if lines > 1 else [])
    if lines:
        sk = kw.get('skew', 0.0)
        lf = kw.get('lift', 0.0)
        for t, a, b in marks:
            k3 = {x: y for x, y in k2.items() if x not in ('skew', 'lift', 'shape', 'nu')}
            shell(fn, u0 + du * a, u0 + du * b, vc + t * vw + sk * ((a + b) / 2 - 0.5), 1.6, 'gold', off=off + thick * 0.82 + lf * a, thick=0.022,
                  nv=1, nu=kw.get('nu', 10), lift=lf * (b - a), skew=sk * (b - a), shape=0.35, **k3)


def layered_hull(fn, top=True, sides=True, under=True, rear=True, glow='slat', extra=False, nose=True, tone=None):
    """Glowing ribbed inner body wrapped in overlapping leaf-shaped shell plates, each with a gold lip
    and inlaid gold lines. tone='worker' gives the bronze-and-copper livery of the non-combat units."""
    hi, lo = ('bronze', 'copper') if tone == 'worker' else ('shell', 'bronze')
    body(fn, glow, off=-0.06, nu=16, nv=14)
    if top:
        if nose:
            plate(fn, 0.0, 0.42, 90, 104, hi, lines=2, nu=10, nv=6, off=0.05, lift=0.05, shape=0.6)
            for vc in (34, 146):
                plate(fn, 0.04, 0.5, vc, 52, lo, nu=9, nv=4, off=0.02, lift=0.06, shape=0.6, skew=(90 - vc) * 0.3)
        for vc in (56, 124):
            plate(fn, 0.3, 0.76, vc, 56, hi, lines=2, nu=10, nv=5, off=0.09, lift=0.1, skew=(90 - vc) * 0.25)
        plate(fn, 0.28, 0.72, 90, 30, lo, nu=9, nv=3, off=0.17, lift=0.08, shape=0.7)
        if rear:
            plate(fn, 0.55, 1.0, 90, 96, lo, lines=2, nu=10, nv=6, off=0.13, lift=0.12, shape=0.6)
        if extra:
            for vc in (38, 142):
                plate(fn, 0.5, 0.97, vc, 50, hi, nu=8, nv=4, off=0.16, lift=0.16, skew=(90 - vc) * 0.2)
    if sides:
        for vc in (4, 176):
            plate(fn, 0.1, 0.96, vc, 32, lo, lines=0, nu=12, nv=4, off=0.14, lift=0.14, shape=0.7)
    if under:
        for vc in (232, 308):
            shell(fn, 0.04, 0.96, vc, 74, 'under', nu=10, nv=4, off=0.03, lift=0.02, shape=0.5)
        shell(fn, 0.1, 0.9, 270, 40, 'under', nu=8, nv=3, off=0.1, shape=0.6)


def xring(x, y, z, r, t=0.03, zone='gold', sides=12, w=0.03):
    """Flat band round the X axis (accelerator rings, collars)."""
    return tube((x - w, y, z), (x + w, y, z), [(0, r), (1, r), (1, r - t), (0, r - t)], sides, zone)


def _barrel(x0, x1, y, z, r, zone="barrel", blades=False, prongs=3):
    """Energy lance: bulb breech, caged glowing section, tapering silver lance threaded through floating
    gold accelerator rings, ending in curved prongs gripping a white-gold core."""
    L = x1 - x0
    xa, xb = x0 + L * 0.14, x0 + L * 0.42
    xm = x1 - L * 0.2
    tube((x0, y, z), (xa, y, z), [(0, r * 1.3), (0.3, r * 2.25), (0.7, r * 2.05), (1, r * 1.3)], 12, 'shell')
    xring(x0 + L * 0.07, y, z, r * 2.36, r * 0.2, 'gold', 12, r * 0.14)
    cyl((xa, y, z), (xb, y, z), r * 0.95, 10, 'slat')
    for a in (0, 120, 240):
        b = sweep([(xa - 0.05, y, z + r * 1.25), ((xa + xb) / 2, y, z + r * 1.55), (xb + 0.05, y, z + r * 1.2)],
                  [(r * 0.5, r * 0.22), (r * 0.6, r * 0.3), (r * 0.4, r * 0.2)], 'bronze', sides=6, up=(0, 0, 1))
        F.rot(b, 'X', a, about=(0, y, z))
    tube((xb, y, z), (xm, y, z), [(0, r * 1.5), (0.05, r * 1.5), (0.1, r * 1.02), (1, r * 0.6)], 12, zone)
    for t in (0.26, 0.52, 0.78):
        xring(xb + (xm - xb) * t, y, z, r * (2.0 - 0.6 * t), r * 0.26, 'gold', 14, r * 0.12)
    cyl((xm - 0.04, y, z), (x1 - L * 0.04, y, z), r * 0.26, 6, 'glow')
    lp = x1 - xm
    for k in range(prongs):
        b = sweep([(xm - lp * 0.35, y, z + r * 0.62), (xm + lp * 0.3, y, z + r * 1.7), (xm + lp * 0.75, y, z + r * 1.45), (x1, y, z + r * 0.5)],
                  [(r * 0.95, r * 0.42), (r * 0.85, r * 0.36), (r * 0.55, r * 0.26), (r * 0.08, r * 0.06)], zone, sides=6, up=(0, 0, 1))
        F.rot(b, 'X', 360.0 * k / prongs + (90 if prongs == 2 else 0), about=(0, y, z))
        g = sweep([(xm + lp * 0.3, y, z + r * 1.9), (xm + lp * 0.75, y, z + r * 1.63), (x1 + 0.01, y, z + r * 0.56)],
                  [(r * 0.2, r * 0.12), (r * 0.16, r * 0.1), (r * 0.05, r * 0.04)], 'gold', sides=4, up=(0, 0, 1))
        F.rot(g, 'X', 360.0 * k / prongs + (90 if prongs == 2 else 0), about=(0, y, z))
    orb((xm + lp * 0.5, y, z), r * 0.62, 'core', seg=(10, 8))
    if blades:
        for s in (1, -1):
            crescent((x1 - L * 0.3, y, z), r * 2.6, s * 150, s * 30, r * 1.1, r * 0.3, 'bronze', n=8, plane='xz')


def core(c, r, cage=3, ring=True):
    """White-gold core gripped by slim gold-edged claws, with two thin tilted gimbal rings."""
    orb(c, r * 0.82, 'core', seg=(16, 10))
    for k in range(cage):
        for zone, w, t in (('bronze', 0.36, 0.11), ('gold', 0.42, 0.035)):
            b = crescent(c, r * 1.2, -70, 78, r * w, r * t, zone, n=9, plane='xz')
            F.rot(b, 'Z', 360.0 * k / cage + 30, about=c)
    globals()['ring'](c, r * 1.5, r * 0.045, 'gold', sides=20, flat=1.6, tilt=(24, 0))
    globals()['ring'](c, r * 1.68, r * 0.035, 'gold', sides=20, flat=1.6, tilt=(-20, 34))
    if ring:
        F.lathe([(r * 1.02, -r * 0.2), (r * 1.3, -r * 0.3), (r * 1.34, -r * 0.12), (r * 1.06, -r * 0.02)], 14, 'bronze', center=c)


def fin(c, r, a0, a1, width, thick=0.06, zone='bronze', lean=0.0, plane='xz', sq=(1, 1), n=14, edge=True):
    """Crescent fin in a vertical plane, optionally leaned outward round X: a thin blade with a gold
    knife edge running right round it."""
    b = crescent(c, r, a0, a1, width, thick * 0.75, zone, n=n, plane=plane, sq=sq)
    out = [b]
    if edge:
        out.append(crescent(c, r, a0, a1, width * 1.13, thick * 0.22, 'gold', n=n, plane=plane, sq=sq, tip=0.03))
    if lean:
        for o in out:
            F.rot(o, 'X', lean, about=c)
    return out


def blade(c, r, a0, a1, width, thick=0.06, zone='bronze', sq=(1, 1), n=14, tilt=0.0, edge=True):
    """Crescent blade lying flat (seen from above), e.g. side sweeps and mandibles, gold-edged."""
    out = [crescent(c, r, a0, a1, width, thick * 0.8, zone, n=n, plane='xy', sq=sq)]
    if edge:
        out.append(crescent(c, r, a0, a1, width * 1.12, thick * 0.24, 'gold', n=n, plane='xy', sq=sq, tip=0.03))
    if tilt:
        for o in out:
            F.rot(o, 'X', tilt, about=c)
    return out


def arc(p0, p1, rnd, r=0.042, rough=0.2, depth=4, forks=2, zj=1.0, tip=False):
    """Electricity: a thin white-hot core inside a soft gold halo, jagged by midpoint displacement,
    with tapering forks. The 'halo' zone must be listed in the model's clear= zones."""
    pts = [Vector(p0), Vector(p1)]
    for _ in range(depth):
        out = [pts[0]]
        for u, v in zip(pts[:-1], pts[1:]):
            j = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1) * zj)) * (v - u).length * rough
            out += [(u + v) / 2 + j, v]
        pts = out
    n = len(pts)
    w = [(1.0 - 0.9 * i / (n - 1)) if tip else (0.3 + 0.7 * math.sin(math.pi * i / (n - 1)) ** 0.5) for i in range(n)]
    path = [tuple(q) for q in pts]
    sweep(path, [(r * k, r * k) for k in w], 'bolt', sides=3, caps=False)
    sweep(path, [(r * 3.6 * k, r * 3.6 * k) for k in w], 'halo', sides=4, caps=False)
    span = (pts[-1] - pts[0]).length
    for _ in range(forks):
        i = rnd.randint(max(1, n // 5), n - 3)
        d = (pts[i + 1] - pts[i - 1]).normalized()
        side = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 1) * zj)).normalized()
        end = pts[i] + (d * 0.7 + side * 0.75).normalized() * span * rnd.uniform(0.22, 0.42)
        arc(pts[i], end, rnd, r * 0.62, rough, max(2, depth - 1), forks - 1, zj, tip=True)
    return pts


def lifters(points, r=0.3, flicker=True, seed=7):
    """Lightning lift: bronze emitter cups with a gold rim and a pin, throwing jagged gold arcs at the
    ground. The arcs come in two sets ('LiftA', 'LiftB') that the game shows in turn; flicker=False
    keeps one fixed set in the current group."""
    for x, y, z in points:
        F.lathe([(r * 0.5, 0.12), (r, 0.05), (r * 1.1, -0.05), (r * 0.82, -0.09)], 12, 'under', center=(x, y, z))
        globals()['ring']((x, y, z - 0.07), r * 0.96, 0.028, 'gold', sides=14)
        cyl((x, y, z - 0.085), (x, y, z - 0.07), r * 0.78, 10, 'glow')
        tube((x, y, z - 0.07), (x, y, z - 0.3), [(0, r * 0.3), (0.5, r * 0.17), (1, 0.015)], 6, 'bronze')
        for k in range(3):
            b = crescent((x, y, z - 0.12), r * 0.8, 200, 300, r * 0.3, 0.03, 'bronze', n=7, plane='xz')
            F.move(b, (r * 0.75, 0, 0))
            F.rot(b, 'Z', 120 * k + 20, about=(x, y, z))

    def bolts(rnd, n):
        for x, y, z in points:
            for _ in range(n):
                a, d = rnd.uniform(0, 6.283), rnd.uniform(0.25, 1.0) * r * 1.9
                arc((x, y, z - 0.29), (x + math.cos(a) * d, y + math.sin(a) * d, 0.03), rnd, r=0.026, rough=0.24, depth=3, forks=1, zj=0.35)
    rnd = random.Random(seed)
    if flicker:
        for g in ('LiftA', 'LiftB'):
            with F.group(g):
                bolts(rnd, 2)
    else:
        bolts(rnd, 2)



def ring(c, r, t, zone='bronze', sides=20, flat=0.6, tilt=(0, 0)):
    """Floating torus band."""
    o = F.lathe([(r - t, 0), (r, -t * flat), (r + t, 0), (r, t * flat), (r - t, 0)], sides, zone, center=c)
    if tilt[0]:
        F.rot(o, 'X', tilt[0], about=c)
    if tilt[1]:
        F.rot(o, 'Y', tilt[1], about=c)
    return o


def petals(c, n, r0, r1, h, zone='shell', width=0.5, open_=35, thick=0.06, start=0.0):
    """Ring of upright petals leaning outward (cups, nests, bud shells)."""
    out = []
    for k in range(n):
        m = F.mark()
        p = [(r0, 0, 0), ((r0 + r1) / 2 + 0.08 * h, 0, h * 0.55), (r1, 0, h)]
        sweep(p, [(thick, width * 0.7), (thick, width), (thick * 0.5, width * 0.12)], zone, sides=6, up=(0, 1, 0), power=0.8)
        F.rot_all(m, 'Z', start + 360.0 * k / n)
        F.move_all(m, c)
        out += F.since(m)
    return out


def flanks(L, w, z, x=0.1, width=0.2):
    """One slim raised blade along each flank, tips sweeping clear of the hull, gold along its edge."""
    r = L * 0.47
    for s in (1, -1):
        for zone, wd, th in (('bronze', width, 0.05), ('gold', width * 1.14, 0.014)):
            b = crescent((x, 0, z), r, s * 32, s * 148, wd, th, zone, n=14, plane='xy', sq=(1.0, (w + 0.28) / r))
            F.rot(b, 'X', -s * 9, about=(x, 0, z))


def claws(c, n, reach, r, width=0.34, zone='shell', a0=-35, a1=80, start=45.0, thick=0.07):
    """Ring of tall claws curling inward over c (cradles, cages)."""
    for k in range(n):
        m = F.mark()
        fin((0, 0, 0.1), r, a0, a1, width, thick, zone=zone)
        F.move_all(m, (reach, 0, 0))
        F.rot_all(m, 'Z', start + 360.0 * k / n)
        F.move_all(m, c)


def thrusters(points, length=1.3, r=0.028, flicker=True, seed=11):
    """Lightning thrusters: a gold-collared emitter spike at each point with arcs streaming back from
    it. Two alternating sets ('ThrustA', 'ThrustB') unless flicker=False."""
    for x, y, z in points:
        tube((x + 0.3, y, z), (x - 0.22, y, z), [(0, 0.13), (0.5, 0.1), (1, 0.015)], 6, 'bronze')
        xring(x + 0.12, y, z, 0.16, 0.04, 'gold', 10, 0.03)
        xring(x - 0.02, y, z, 0.12, 0.03, 'gold', 10, 0.02)

    def bolts(rnd):
        for x, y, z in points:
            for _ in range(2):
                d = length * rnd.uniform(0.65, 1.0)
                arc((x - 0.2, y, z), (x - 0.2 - d, y + rnd.uniform(-0.3, 0.3) * d, max(0.1, z + rnd.uniform(-0.3, 0.25) * d)), rnd,
                    r=r, rough=0.2, depth=3, forks=1, tip=True)
    rnd = random.Random(seed)
    if flicker:
        for g in ('ThrustA', 'ThrustB'):
            with F.group(g):
                bolts(rnd)
    else:
        bolts(rnd)


def eye(c, r=0.2, brow=True):
    """Forward sensor: a narrow almond of white-gold light in a dark socket under a hooded bronze brow."""
    x, y, z = c
    orb(c, r, 'under', seg=(12, 8), sq=(1.25, 1.0, 0.62))
    orb((x + r * 0.5, y, z), r * 0.62, 'core', seg=(10, 6), sq=(1.3, 1.25, 0.3))
    xring(x + r * 0.2, y, z, r * 1.06, r * 0.16, 'gold', 12, r * 0.08)
    if brow:
        b = crescent((x - r * 0.2, y, z + r * 0.42), r * 1.25, -75, 75, r * 0.7, r * 0.26, 'bronze', n=9, plane='xy')
        F.rot(b, 'Y', 12, about=(x, y, z + r * 0.42))


def slit_eyes(fn, u=0.08, off=0.1, v=(62, 118), r=0.07):
    """Two slanted slits of light either side of the prow."""
    for a in v:
        p = fn(u, a, off)
        orb(tuple(p), r, 'core', seg=(8, 6), sq=(2.6, 0.8, 0.5))
        orb((p[0] - r * 0.4, p[1], p[2] + r * 0.2), r * 1.2, 'under', seg=(8, 6), sq=(2.4, 0.9, 0.5))


def ore_heap(c, R, h, n=10, seed=5, crystals=7):
    """Heaped mound of dark ore chunks studded with glowing gold crystal."""
    rnd = random.Random(seed)
    for k in range(n):
        a, d = rnd.uniform(0, 6.283), R * math.sqrt(rnd.random()) * 0.78
        z = c[2] + h * (1 - d / R) * rnd.uniform(0.55, 1.0)
        F.rock((c[0] + d * math.cos(a), c[1] + d * math.sin(a), z), R * rnd.uniform(0.24, 0.36), 'copper', seed=seed * 10 + k, sub=1, cuts=4)
    for k in range(crystals):
        a, d = rnd.uniform(0, 6.283), R * math.sqrt(rnd.random()) * 0.7
        z = c[2] + h * (1 - d / R) + R * 0.16
        o = F.ico((c[0] + d * math.cos(a), c[1] + d * math.sin(a), z), R * rnd.uniform(0.09, 0.15), 'core', sub=1, sq=(0.65, 0.65, 1.7), jitter=0.12, seed=k)
        F.rot(o, 'X', rnd.uniform(-35, 35), about=(c[0] + d * math.cos(a), c[1] + d * math.sin(a), z))


def gimbals(c, r, n=3, zone='gold', w=2.6):
    """Nested flat bands on different axes round a core."""
    tilts = [(22, 0), (-18, 38), (62, -24), (-55, 60)]
    for k in range(n):
        ring(c, r * (1.0 + 0.16 * k), r * 0.028, zone if k != 1 else 'bronze', sides=24, flat=w, tilt=tilts[k % 4])


# ---- firing ----
def flash(x, y, z, r, group, seed=2):
    """Discharge burst pointing +X in its own group: a white-gold flare with a crown of short lightning.
    The game shows it for an instant when the weapon fires."""
    rnd = random.Random(seed)
    with F.group(group):
        tube((x - r, y, z), (x + r * 9, y, z), [(0, r * 0.6), (0.14, r * 2.3), (1, 0.01)], 8, 'flash')
        orb((x, y, z), r * 1.9, 'flash', seg=(8, 6))
        for k in range(5):
            a = 6.283 * k / 5 + rnd.uniform(-0.3, 0.3)
            arc((x, y, z), (x + r * rnd.uniform(3, 7), y + math.cos(a) * r * 6, z + math.sin(a) * r * 6), rnd, r=r * 0.22, rough=0.25, depth=2, forks=1, tip=True)


def barrel(x0, x1, y, z, r, zone="barrel", blades=False, prongs=3, group=None, flash_group=None):
    """Energy lance; group= makes it its own part (it recoils when fired), flash_group= adds the discharge."""
    if group:
        with F.group(group):
            _barrel(x0, x1, y, z, r, zone, blades, prongs)
    else:
        _barrel(x0, x1, y, z, r, zone, blades, prongs)
    if flash_group:
        flash(x1 + r, y, z, r, flash_group)


def gun_pivots(specs, parent='Turret'):
    out = []
    for sfx, b, mz in specs:
        out += [('Barrel' + sfx, b, 'Barrel' + sfx + 'Pivot', parent), ('Flash' + sfx, mz, 'Flash' + sfx + 'Pivot', 'Barrel' + sfx)]
    return out
