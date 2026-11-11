"""Shared Kesh pieces: layered shell hulls, crescent fins, energy barrels, core orbs."""
import math

import forge as F
from forge import body, box, crescent, cyl, lensfn, orb, shell, sweep, tube


def layered_hull(fn, top=True, sides=True, under=True, rear=True, glow='slat', extra=False, nose=True):
    """Glowing ribbed inner body wrapped in overlapping leaf-shaped shell plates."""
    body(fn, glow, off=-0.06, nu=16, nv=14)
    if top:
        if nose:
            shell(fn, 0.0, 0.42, 90, 104, 'shell', nu=10, nv=6, off=0.05, lift=0.05, shape=0.6)
            for vc in (34, 146):
                shell(fn, 0.04, 0.5, vc, 52, 'bronze', nu=9, nv=4, off=0.02, lift=0.06, shape=0.6, skew=(90 - vc) * 0.3)
        for vc in (56, 124):
            shell(fn, 0.3, 0.76, vc, 56, 'shell', nu=10, nv=5, off=0.09, lift=0.1, skew=(90 - vc) * 0.25)
        shell(fn, 0.28, 0.72, 90, 30, 'bronze', nu=9, nv=3, off=0.17, lift=0.08, shape=0.7)
        if rear:
            shell(fn, 0.55, 1.0, 90, 96, 'bronze', nu=10, nv=6, off=0.13, lift=0.12, shape=0.6)
        if extra:
            for vc in (38, 142):
                shell(fn, 0.5, 0.97, vc, 50, 'shell', nu=8, nv=4, off=0.16, lift=0.16, skew=(90 - vc) * 0.2)
    if sides:
        for vc in (4, 176):
            shell(fn, 0.1, 0.96, vc, 32, 'bronze', nu=12, nv=4, off=0.14, lift=0.14, shape=0.7)
    if under:
        for vc in (232, 308):
            shell(fn, 0.04, 0.96, vc, 74, 'under', nu=10, nv=4, off=0.03, lift=0.02, shape=0.5)
        shell(fn, 0.1, 0.9, 270, 40, 'under', nu=8, nv=3, off=0.1, shape=0.6)


def barrel(x0, x1, y, z, r, zone="barrel", blades=False):
    """Energy barrel: bulb breech, long caged glowing section, tapered tube, flared muzzle, guide blades."""
    L = x1 - x0
    xa, xb = x0 + L * 0.16, x0 + L * 0.56
    tube((x0, y, z), (xa, y, z), [(0, r * 1.2), (0.3, r * 2.1), (0.7, r * 1.9), (1, r * 1.25)], 12, 'shell')
    cyl((xa, y, z), (xb, y, z), r * 0.95, 10, 'slat')
    for a in (0, 120, 240):
        b = sweep([(xa - 0.05, y, z + r * 1.25), ((xa + xb) / 2, y, z + r * 1.5), (xb + 0.05, y, z + r * 1.2)],
                  [(r * 0.5, r * 0.22), (r * 0.6, r * 0.3), (r * 0.4, r * 0.2)], 'bronze', sides=6, up=(0, 0, 1))
        F.rot(b, 'X', a, about=(0, y, z))
    tube((xb, y, z), (x1, y, z), [(0, r * 1.45), (0.06, r * 1.45), (0.1, r * 0.95), (0.8, r * 0.8), (0.9, r * 1.15), (1, r * 1.35)],
         12, zone)
    cyl((x1 - 0.06, y, z), (x1 - 0.03, y, z), r * 0.7, 10, 'glow')
    tube((x1 - 0.08, y, z), (x1 + 0.02, y, z), [(0, r * 1.3), (1, r * 1.38), (1, r * 0.78), (0.2, r * 0.74)], 12, 'under')
    if blades:
        for s in (1, -1):
            crescent((x1 - L * 0.16, y, z), r * 2.6, s * 150, s * 30, r * 1.1, r * 0.3, 'bronze', n=8, plane='xz')


def core(c, r, cage=3, ring=True):
    """Glowing core orb held by curved claws."""
    orb(c, r, 'core', seg=(16, 10))
    for k in range(cage):
        b = crescent(c, r * 1.22, -70, 70, r * 0.42, r * 0.12, 'bronze', n=9, plane='xz')
        F.rot(b, 'Z', 360.0 * k / cage + 30, about=c)
    if ring:
        F.lathe([(r * 1.02, -r * 0.2), (r * 1.3, -r * 0.3), (r * 1.34, -r * 0.12), (r * 1.06, -r * 0.02)], 14, 'bronze', center=c)


def fin(c, r, a0, a1, width, thick=0.06, zone='bronze', lean=0.0, plane='xz', sq=(1, 1), n=14):
    """Crescent fin in a vertical plane, optionally leaned outward round X."""
    b = crescent(c, r, a0, a1, width, thick, zone, n=n, plane=plane, sq=sq)
    if lean:
        F.rot(b, 'X', lean, about=c)
    return b


def blade(c, r, a0, a1, width, thick=0.06, zone='bronze', sq=(1, 1), n=14, tilt=0.0):
    """Crescent blade lying flat (seen from above), e.g. side sweeps and mandibles."""
    b = crescent(c, r, a0, a1, width, thick, zone, n=n, plane='xy', sq=sq)
    if tilt:
        F.rot(b, 'X', tilt, about=c)
    return b


def lifters(points, r=0.3):
    """Hover emitters under the hull: glowing dishes with a dark rim."""
    for x, y, z in points:
        F.lathe([(r * 0.5, 0.1), (r, 0.04), (r * 1.08, -0.04), (r * 0.8, -0.07)], 10, 'under', center=(x, y, z))
        cyl((x, y, z - 0.075), (x, y, z - 0.06), r * 0.78, 10, 'glow')


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
    """One slim raised blade along each flank, tips sweeping clear of the hull."""
    r = L * 0.47
    for s in (1, -1):
        b = crescent((x, 0, z), r, s * 32, s * 148, width, 0.06, 'bronze', n=14, plane='xy', sq=(1.0, (w + 0.28) / r))
        F.rot(b, 'X', -s * 9, about=(x, 0, z))


def claws(c, n, reach, r, width=0.34, zone='shell', a0=-35, a1=80, start=45.0, thick=0.07):
    """Ring of tall claws curling inward over c (cradles, cages)."""
    for k in range(n):
        m = F.mark()
        fin((0, 0, 0.1), r, a0, a1, width, thick, zone=zone)
        F.move_all(m, (reach, 0, 0))
        F.rot_all(m, 'Z', start + 360.0 * k / n)
        F.move_all(m, c)
