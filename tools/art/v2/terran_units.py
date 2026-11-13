"""Terran units, art pass v2."""
import math

import forge as F
from forge import box, cyl, hull, loft, plate, prism, sym, tube, orb, lathe, sweep
import terran_kit as K

ASSETS = {}


def asset(path, label, size=512):
    def deco(fn):
        def run(glb, render, report):
            F.begin('terran')
            kw = fn() or {}
            F.finish(kw.pop('name', fn.__name__.title().replace('_', '')), glb, render=render, report=report,
                     label=label, size=kw.pop('size', size), **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='terran')
        return run
    return deco


def turret_shell(x0, x1, w, tz, h, zone='armor', nose=0.6, back=0.72):
    """Faceted wedge turret from x0 (bustle) to x1 (mantlet)."""
    L = x1 - x0
    return hull([
        (x0, [(0, tz + 0.16), (w * back, tz + 0.16), (w * (back + 0.12), tz + h * 0.5), (w * back * 0.8, tz + h * 0.88), (0, tz + h * 0.88)]),
        (x0 + L * 0.2, [(0, tz + 0.06), (w * 0.9, tz + 0.06), (w, tz + h * 0.5), (w * 0.72, tz + h), (0, tz + h)]),
        (x0 + L * 0.68, [(0, tz + 0.06), (w * 0.92, tz + 0.06), (w, tz + h * 0.48), (w * 0.66, tz + h * 0.97), (0, tz + h)]),
        (x1, [(0, tz + 0.1), (w * nose, tz + 0.1), (w * (nose + 0.07), tz + h * 0.42), (w * nose * 0.8, tz + h * 0.76), (0, tz + h * 0.78)]),
    ], zone, bevel=0.045)


def turret_kit(x0, x1, w, tz, h, cupola=True, rack=True):
    """Roof plates, cupola, optics, smoke launchers, bustle rack, antennas for a turret_shell."""
    L = x1 - x0
    xa, xb = x0 + L * 0.22, x0 + L * 0.66
    plate([(xa, -w * 0.62), (xb, -w * 0.56), (xb + L * 0.1, -w * 0.3), (xb + L * 0.1, w * 0.3), (xb, w * 0.56), (xa, w * 0.62)],
          tz + h - 0.01, tz + h + 0.05, 'plate', inset=0.04, bevel=0.02)
    for s in (1, -1):
        # Side applique armour slab, leaning with the turret cheek.
        p = prism([(xa - 0.1, tz + 0.18), (xb + 0.1, tz + 0.18), (xb + 0.3, tz + h * 0.45), (xb, tz + h * 0.82), (xa, tz + h * 0.82)],
                  0, 0.07, 'plate', bevel=0.025)
        F.rot(p, 'X', 22, about=(0, 0, tz + 0.18))
        F.move(p, (0, w * 1.0, 0.0))
        if s < 0:
            F.xf(p, F.Matrix.Diagonal((1, -1, 1, 1)))
        box(((xa + xb) / 2, s * w * 0.99, tz + h * 0.5), (L * 0.16, 0.02, 0.02), 'glow')
        K.smoke(xb - 0.1, s * w * 0.9, tz + h * 0.72, s)
    if cupola:
        K.hatch(x0 + L * 0.38, w * 0.3, tz + h + 0.04, 0.27)
        box((x0 + L * 0.52, w * 0.3, tz + h + 0.12), (0.06, 0.12, 0.05), 'glass')
    # Sensor head.
    box((x0 + L * 0.5, -w * 0.36, tz + h + 0.14), (0.2, 0.16, 0.11), 'dark', bevel=0.03)
    box((x0 + L * 0.5 + 0.2, -w * 0.36, tz + h + 0.15), (0.012, 0.1, 0.06), 'glass')
    box((x0 + L * 0.5, -w * 0.36, tz + h + 0.26), (0.08, 0.08, 0.012), 'amber')
    if rack:
        for s in (1, -1):
            box((x0 - 0.12, s * w * 0.5, tz + h * 0.5), (0.2, 0.03, 0.03), 'dark')
        box((x0 - 0.3, 0, tz + h * 0.5), (0.03, w * 0.55, 0.16), 'dark')
        K.stow((x0 - 0.08, 0, tz + h * 0.42), (0.16, w * 0.42, 0.14))
    K.antenna(x0 + 0.25, w * 0.5, tz + h * 0.9, 1.25)
    K.antenna(x0 + 0.25, -w * 0.5, tz + h * 0.9, 0.9, tip='glow')


@asset('human/lancer.glb', 'Terran Lancer (light tank)')
def lancer():
    L, hw, top = 6.4, 1.22, 1.42
    K.tank_hull(L, hw, top)
    K.hull_fittings(L, hw, top)
    for s in (1, -1):
        K.track_unit(-3.35, 3.3, s * 1.68, w=0.42, side=s)
        box((0.0, s * 1.2, 1.1), (2.7, 0.12, 0.2), 'dark')
        K.stow((-2.2, s * 0.86, top + 0.13), (0.5, 0.22, 0.12))
        K.chevron(1.9, s * 0.55, top - 0.19, 0.1)
    K.hatch(1.05, 0.0, top + 0.02, 0.26, 6)
    tz, th = top + 0.04, 0.84
    with F.group('Turret'):
        tube((-0.35, 0, tz - 0.03), (-0.35, 0, tz + 0.09), [(0, 1.02), (1, 0.98)], 20, 'dark')
        turret_shell(-1.95, 1.3, 1.1, tz, th)
        turret_kit(-1.95, 1.3, 1.1, tz, th)
        box((1.42, 0, tz + 0.38), (0.24, 0.74, 0.25), 'dark', bevel=0.05)
        for s in (1, -1):
            K.railgun(1.45, 6.55, s * 0.4, tz + 0.38, 0.118)
        box((2.25, 0, tz + 0.38), (0.5, 0.26, 0.07), 'armor', bevel=0.02)
        K.gun(0.2, 1.5, 0.62, tz + th + 0.2, 0.035)
        box((0.25, 0.62, tz + th + 0.14), (0.14, 0.06, 0.07), 'dark', bevel=0.02)
    return dict(pivot=('Turret', (-0.35, 0, tz)))


@asset('human/outrider.glb', 'Terran Outrider (scout)')
def outrider():
    hull([(-2.9, [(0, 0.78), (0.9, 0.78), (1.02, 1.08), (0.86, 1.4), (0, 1.4)]),
          (-2.2, [(0, 0.62), (0.98, 0.62), (1.1, 1.08), (0.92, 1.64), (0, 1.64)]),
          (0.4, [(0, 0.62), (0.98, 0.62), (1.1, 1.08), (0.9, 1.56), (0, 1.6)]),
          (2.1, [(0, 0.64), (0.94, 0.64), (1.04, 1.0), (0.78, 1.2), (0, 1.26)]),
          (3.0, [(0, 0.82), (0.66, 0.82), (0.74, 0.94), (0.62, 1.04), (0, 1.04)])], 'hull', bevel=0.04)
    # Sensor band instead of a windscreen (unmanned), nose plate, belly.
    loft([[(0.45, -0.8, 1.6), (0.45, 0.8, 1.6), (1.5, 0.72, 1.36), (1.5, -0.72, 1.36)],
          [(0.47, -0.8, 1.65), (0.47, 0.8, 1.65), (1.52, 0.72, 1.41), (1.52, -0.72, 1.41)]], 'armor', bevel=0.02)
    box((1.02, 0, 1.53), (0.2, 0.6, 0.03), 'glass')
    box((3.02, 0, 0.92), (0.02, 0.5, 0.06), 'grille')
    box((-0.2, 0, 0.55), (2.3, 0.8, 0.1), 'dark', bevel=0.03)
    for s in (1, -1):
        for i, x in enumerate((-1.9, 0.0, 1.9)):
            K.tire((x, s * 1.42, 0.6), 0.6, 0.46, s)
            cyl((x, s * 0.9, 0.6), (x, s * 1.3, 0.6), 0.1, 6, 'dark')
            # Angular wheel arch.
            prism([(x - 0.85, 1.0), (x - 0.5, 1.32), (x + 0.5, 1.32), (x + 0.85, 1.0), (x + 0.8, 0.94), (x + 0.46, 1.24),
                   (x - 0.46, 1.24), (x - 0.8, 0.94)], min(s * 1.05, s * 1.72), max(s * 1.05, s * 1.72), 'armor', bevel=0.02)
        box((-0.05, s * 1.74, 1.28), (2.3, 0.012, 0.02), 'glow')
        K.light((2.72, s * 0.62, 1.12), (0.07, 0.14, 0.04))
        box((2.6, s * 1.74, 1.12), (0.12, 0.012, 0.03), 'amber')
        K.stow((-1.0, s * 1.38, 1.42), (0.45, 0.22, 0.09))
        box((-2.92, s * 0.6, 1.2), (0.02, 0.14, 0.04), 'red')
    K.vent((-2.0, 0, 1.66), (0.45, 0.6, 0.04))
    K.antenna(-2.5, 0.75, 1.55, 1.5)
    tz = 1.62
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.03), (-0.5, 0, tz + 0.07), [(0, 0.66), (1, 0.62)], 16, 'dark')
        turret_shell(-1.3, 0.55, 0.68, tz, 0.5)
        box((0.62, 0, tz + 0.24), (0.14, 0.3, 0.16), 'dark', bevel=0.03)
        K.gun(0.6, 3.3, 0.0, tz + 0.25, 0.07)
        box((1.5, 0, tz + 0.25), (0.5, 0.11, 0.09), 'armor', bevel=0.02)
        cyl((-0.95, -0.3, tz + 0.45), (-0.95, -0.3, tz + 1.2), 0.045, 6, 'dark')
        box((-0.95, -0.3, tz + 1.28), (0.14, 0.2, 0.1), 'dark', bevel=0.03)
        box((-0.8, -0.3, tz + 1.28), (0.012, 0.14, 0.06), 'glow')
        box((-0.4, 0.3, tz + 0.52), (0.16, 0.12, 0.05), 'plate', bevel=0.02)
        box((-0.5, 0, tz + 0.27), (0.4, 0.69, 0.02), 'glow')
    return dict(pivot=('Turret', (-0.5, 0, tz)))


@asset('human/skimmer.glb', 'Terran Skimmer (hover tank)')
def skimmer():
    # Hover hull: broad low wedge riding on a dark plenum skirt.
    hull([(-3.1, [(0, 0.6), (1.2, 0.6), (1.5, 0.82), (1.25, 1.25), (0, 1.3)]),
          (-2.2, [(0, 0.5), (1.5, 0.5), (1.85, 0.82), (1.45, 1.42), (0, 1.5)]),
          (0.8, [(0, 0.5), (1.5, 0.5), (1.85, 0.82), (1.35, 1.36), (0, 1.42)]),
          (2.5, [(0, 0.55), (1.2, 0.55), (1.45, 0.8), (0.9, 1.05), (0, 1.1)]),
          (3.4, [(0, 0.68), (0.55, 0.68), (0.66, 0.78), (0.5, 0.86), (0, 0.88)])], 'hull', bevel=0.04)
    hull([(-3.0, [(0, 0.28), (1.15, 0.28), (1.35, 0.6), (0, 0.6)]),
          (0.8, [(0, 0.24), (1.4, 0.24), (1.62, 0.56), (0, 0.56)]),
          (3.1, [(0, 0.34), (0.5, 0.34), (0.6, 0.7), (0, 0.7)])], 'dark', bevel=0.03)
    plate([(-1.9, -0.9), (0.6, -0.86), (2.2, -0.5), (2.2, 0.5), (0.6, 0.86), (-1.9, 0.9)], 1.4, 1.5, 'armor', inset=0.06, bevel=0.025)
    for s in (1, -1):
        for x, r in ((1.55, 0.52), (-1.75, 0.6)):
            # Lift fan: shrouded ring with a grille on top and a glowing disc underneath.
            y = s * 1.75
            tube((x, y, 0.42), (x, y, 1.0), [(0, r * 0.92), (0.15, r * 1.08), (0.85, r * 1.08), (1, r * 0.95), (1, r * 0.78), (0.8, r * 0.76)], 8, 'armor', sharp=30, bevel=0.02)
            cyl((x, y, 0.8), (x, y, 0.84), r * 0.78, 14, 'vent')
            cyl((x, y, 0.84), (x, y, 0.9), r * 0.22, 8, 'dark')
            cyl((x, y, 0.4), (x, y, 0.44), r * 0.82, 14, 'glow')
            box((x, s * 1.3, 0.75), (0.3, 0.25, 0.14), 'dark', bevel=0.03)
        box((0.0, s * 1.83, 0.86), (1.0, 0.012, 0.02), 'glow')
        K.light((2.6, s * 0.75, 0.98), (0.07, 0.14, 0.04))
        box((2.3, s * 1.42, 0.86), (0.12, 0.012, 0.03), 'amber')
        # Rear thrusters.
        tube((-3.0, s * 0.62, 0.95), (-3.55, s * 0.62, 0.95), [(0, 0.34), (0.6, 0.36), (1, 0.28)], 10, 'armor', sharp=40)
        cyl((-3.5, s * 0.62, 0.95), (-3.56, s * 0.62, 0.95), 0.25, 10, 'glow')
        # Steering vanes.
        prism([(-3.3, 1.2), (-2.5, 1.2), (-2.8, 1.85), (-3.25, 1.85)], s * 1.0 - 0.04, s * 1.0 + 0.04, 'armor', bevel=0.02)
        box((-3.05, s * 1.0, 1.87), (0.2, 0.045, 0.012), 'amber')
    K.vent((-2.2, 0, 1.5), (0.4, 0.5, 0.04))
    box((3.4, 0, 0.78), (0.02, 0.4, 0.05), 'grille')
    tz = 1.48
    with F.group('Turret'):
        tube((-0.4, 0, tz - 0.03), (-0.4, 0, tz + 0.07), [(0, 0.78), (1, 0.74)], 16, 'dark')
        turret_shell(-1.35, 0.75, 0.82, tz, 0.56)
        box((-0.3, 0, tz + 0.58), (0.5, 0.45, 0.025), 'plate', bevel=0.02)
        box((0.82, 0, tz + 0.27), (0.14, 0.52, 0.17), 'dark', bevel=0.03)
        for s in (1, -1):
            K.railgun(0.8, 4.3, s * 0.3, tz + 0.27, 0.085)
            box((-0.3, s * 0.83, tz + 0.3), (0.5, 0.012, 0.02), 'glow')
        box((-0.6, -0.3, tz + 0.66), (0.16, 0.13, 0.08), 'dark', bevel=0.03)
        box((-0.44, -0.3, tz + 0.67), (0.012, 0.09, 0.045), 'glass')
        K.antenna(-1.1, 0.4, tz + 0.5, 1.0)
    return dict(pivot=('Turret', (-0.4, 0, tz)))


@asset('human/bulwark.glb', 'Terran Bulwark (heavy tank)', size=1024)
def bulwark():
    L, hw, top = 7.8, 1.5, 1.62
    K.chassis(L, hw, top, pod=2.08, w=0.56, nwheels=6, nose=1.05)
    for s in (1, -1):
        # Extra slab armour over the skirts and on the bow.
        for i in range(3):
            x = -2.6 + i * 2.2
            prism([(x - 0.95, 0.92), (x + 0.95, 0.92), (x + 0.85, 1.34), (x - 0.85, 1.34)], min(s * 2.75, s * 2.88), max(s * 2.75, s * 2.88), 'plate', bevel=0.03)
        box((L / 2 - 1.3, s * 0.72, top - 0.06), (0.55, 0.42, 0.05), 'plate', bevel=0.02)
        K.chevron(L / 2 - 1.3, s * 0.72, top + 0.0, 0.12)
        K.stow((-L / 2 + 0.7, s * 1.0, top + 0.14), (0.42, 0.3, 0.13))
    box((L / 2 + 0.02, 0, 0.62), (0.1, hw * 0.75, 0.16), 'plate', bevel=0.04)
    tz, th = top + 0.04, 1.0
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.03), (-0.5, 0, tz + 0.1), [(0, 1.4), (1, 1.34)], 24, 'dark')
        turret_shell(-2.7, 1.5, 1.45, tz, th)
        turret_kit(-2.7, 1.5, 1.45, tz, th)
        box((1.62, 0, tz + 0.46), (0.3, 1.0, 0.33), 'dark', bevel=0.06)
        for s in (1, -1):
            K.railgun(1.7, 8.6, s * 0.52, tz + 0.46, 0.165)
            # Side missile pods on the turret cheeks.
            K.missile_box((-0.9, s * 1.78, tz + 0.62), (0.75, 0.3, 0.24), nx=2, nz=2)
            box((-0.9, s * 1.5, tz + 0.5), (0.3, 0.1, 0.1), 'dark')
        box((2.7, 0, tz + 0.46), (0.7, 0.36, 0.09), 'armor', bevel=0.02)
        box((2.2, 0, tz + 0.72), (0.5, 0.2, 0.06), 'plate', bevel=0.02)
        K.gun(0.2, 1.9, -0.75, tz + th + 0.24, 0.04)
        box((0.25, -0.75, tz + th + 0.17), (0.16, 0.07, 0.08), 'dark', bevel=0.02)
        K.hatch(-1.4, -0.5, tz + th + 0.04, 0.3)
    return dict(pivot=('Turret', (-0.5, 0, tz)))


@asset('human/javelin.glb', 'Terran Javelin (missile tank)')
def javelin():
    L, hw, top = 6.4, 1.22, 1.42
    K.chassis(L, hw, top)
    K.hatch(1.2, 0.0, top + 0.02, 0.26, 6)
    tz = top + 0.04
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.03), (-0.5, 0, tz + 0.14), [(0, 1.0), (1, 0.9)], 20, 'dark')
        hull([(-1.5, [(0, tz + 0.12), (0.5, tz + 0.12), (0.6, tz + 0.5), (0.4, tz + 0.95), (0, tz + 0.95)]),
              (0.3, [(0, tz + 0.12), (0.5, tz + 0.12), (0.6, tz + 0.45), (0.36, tz + 0.8), (0, tz + 0.8)]),
              (0.9, [(0, tz + 0.14), (0.3, tz + 0.14), (0.36, tz + 0.36), (0.22, tz + 0.5), (0, tz + 0.5)])], 'armor', bevel=0.04)
        cyl((-0.5, -0.95, tz + 0.62), (-0.5, 0.95, tz + 0.62), 0.14, 10, 'dark')
        for s in (1, -1):
            m = F.mark()
            K.missile_box((-0.3, s * 1.12, tz + 0.62), (1.35, 0.46, 0.38), nx=2, nz=2)
            box((-0.3, s * 1.6, tz + 0.62), (1.1, 0.012, 0.02), 'glow')
            box((0.6, s * 1.12, tz + 1.02), (0.25, 0.3, 0.012), 'hazard')
            F.rot_all(m, 'Y', -16, about=(-0.5, 0, tz + 0.62))
        # Targeting head between the boxes.
        box((0.1, 0, tz + 1.0), (0.26, 0.2, 0.14), 'dark', bevel=0.04)
        box((0.37, 0, tz + 1.0), (0.012, 0.14, 0.08), 'glass')
        cyl((-0.9, 0, tz + 0.95), (-0.9, 0, tz + 1.2), 0.05, 6, 'dark')
        tube((-0.9, 0, tz + 1.2), (-0.9, 0, tz + 1.32), [(0, 0.26), (1, 0.2)], 10, 'plate')
        K.antenna(-1.3, 0.3, tz + 0.95, 1.1)
    return dict(pivot=('Turret', (-0.5, 0, tz)))


@asset('human/longbow.glb', 'Terran Longbow (artillery)', size=1024)
def longbow():
    L, hw, top = 7.2, 1.3, 1.42
    K.chassis(L, hw, top, pod=1.78, w=0.46, nwheels=6)
    for s in (1, -1):
        # Recoil spades folded down at the rear.
        m = F.mark()
        box((-4.3, s * 1.1, 0.9), (0.75, 0.1, 0.09), 'armor', bevel=0.03)
        prism([(-5.3, 0.1), (-4.9, 0.1), (-4.8, 0.85), (-5.1, 0.85)], s * 1.1 - 0.4, s * 1.1 + 0.4, 'plate', bevel=0.03)
        box((-5.07, s * 1.1, 0.3), (0.03, 0.36, 0.1), 'hazard')
        F.rot_all(m, 'Y', -8, about=(-3.6, 0, 0.9))
        K.stow((0.9, s * 0.8, top + 0.12), (0.5, 0.3, 0.1))
    tz = top + 0.04
    with F.group('Turret'):
        tube((-0.9, 0, tz - 0.03), (-0.9, 0, tz + 0.1), [(0, 1.2), (1, 1.12)], 20, 'dark')
        # Open-backed gun house with trunnion cheeks.
        hull([(-2.6, [(0, tz + 0.1), (1.0, tz + 0.1), (1.1, tz + 0.5), (0.9, tz + 0.9), (0, tz + 0.9)]),
              (-0.2, [(0, tz + 0.1), (1.05, tz + 0.1), (1.12, tz + 0.5), (0.85, tz + 0.95), (0, tz + 0.95)]),
              (0.7, [(0, tz + 0.12), (0.8, tz + 0.12), (0.86, tz + 0.4), (0.6, tz + 0.62), (0, tz + 0.62)])], 'armor', bevel=0.04)
        for s in (1, -1):
            prism([(-1.7, tz + 0.7), (0.1, tz + 0.7), (-0.3, tz + 1.75), (-1.3, tz + 1.75)], min(s * 0.62, s * 0.84), max(s * 0.62, s * 0.84), 'plate', bevel=0.035)
            cyl((-0.8, s * 0.6, tz + 1.3), (-0.8, s * 0.9, tz + 1.3), 0.24, 10, 'dark')
            box((-0.8, s * 0.86, tz + 1.3), (0.5, 0.012, 0.02), 'glow')
            # Elevation rams.
            m = F.mark()
            cyl((0.2, s * 0.4, tz + 0.5), (1.4, s * 0.4, tz + 0.5), 0.07, 8, 'barrel')
            cyl((-0.2, s * 0.4, tz + 0.5), (0.5, s * 0.4, tz + 0.5), 0.11, 8, 'dark')
            F.rot_all(m, 'Y', -44, about=(-0.1, 0, tz + 0.5))
        m = F.mark()
        gz = tz + 1.3
        box((-1.6, 0, gz), (0.8, 0.5, 0.42), 'armor', bevel=0.06)
        box((-2.45, 0, gz), (0.1, 0.36, 0.3), 'dark', bevel=0.03)
        K.railgun(-0.9, 8.4, 0.0, gz, 0.2)
        for s in (1, -1):
            box((0.9, s * 0.42, gz), (1.6, 0.07, 0.1), 'dark', bevel=0.02)   # recoil rails
            cyl((-0.6, s * 0.42, gz + 0.2), (1.6, s * 0.42, gz + 0.2), 0.08, 8, 'barrel')
        box((3.6, 0, gz - 0.33), (0.25, 0.3, 0.08), 'armor', bevel=0.02)
        F.rot_all(m, 'Y', -26, about=(-0.8, 0, gz))
        K.antenna(-2.3, 0.7, tz + 0.9, 1.3)
        box((-2.0, -0.6, tz + 1.0), (0.2, 0.16, 0.1), 'dark', bevel=0.03)
        box((-1.8, -0.6, tz + 1.01), (0.012, 0.1, 0.06), 'glass')
    return dict(pivot=('Turret', (-0.9, 0, tz)))


def cab(x, y, z, sx=0.7, sy=0.6, sz=0.55):
    """Unmanned control cab: crisp wedge with a slanted sensor window, roof kit and beacon."""
    prism([(x - sx, z), (x + sx, z), (x + sx, z + sz * 0.42), (x + sx * 0.45, z + sz), (x - sx * 0.8, z + sz), (x - sx, z + sz * 0.8)],
          y - sy, y + sy, 'armor', taper=0.84, bevel=0.03)
    m = F.mark()
    box((0, 0, 0), (sx * 0.36, sy * 0.66, 0.012), 'glass')
    box((0, 0, -0.012), (sx * 0.42, sy * 0.72, 0.012), 'dark')
    ang = math.degrees(math.atan2(sz * 0.58, sx * 0.55))
    F.rot_all(m, 'Y', ang)
    F.move_all(m, (x + sx * 0.74, y, z + sz * 0.73))
    for s in (1, -1):
        box((x - sx * 0.1, y + s * sy * 0.93, z + sz * 0.5), (sx * 0.5, 0.012, 0.02), 'glow')
    K.beacon(x - sx * 0.45, y + sy * 0.4, z + sz)
    box((x - sx * 0.2, y - sy * 0.3, z + sz + 0.02), (0.25, 0.14, 0.03), 'plate', bevel=0.015)
    box((x - sx - 0.012, y, z + sz * 0.45), (0.012, sy * 0.6, sz * 0.22), 'vent')


@asset('human/prospector.glb', 'Terran Prospector (ore miner)')
def prospector():
    L, hw, top = 6.6, 1.22, 1.3
    K.chassis(L, hw, top, stowage=False, nose=0.9)
    cab(1.5, 0.0, top + 0.02, 0.75, 0.75, 0.62)
    # Open ore hopper behind the cab: sloped walls, hazard rim, ribbed sides.
    x0, x1, wy, z0, z1 = -3.1, 0.55, 1.5, top + 0.02, top + 1.15
    for s in (1, -1):
        loft([[(x0, s * (wy - 0.25), z0), (x1, s * (wy - 0.25), z0), (x1, s * wy, z1), (x0, s * wy, z1)],
              [(x0, s * (wy - 0.13), z0), (x1, s * (wy - 0.13), z0), (x1, s * (wy + 0.12), z1), (x0, s * (wy + 0.12), z1)]], 'armor', bevel=0.02)
        for k in range(4):
            x = x0 + 0.35 + k * 0.98
            loft([[(x - 0.07, s * (wy - 0.12), z0 + 0.05), (x + 0.07, s * (wy - 0.12), z0 + 0.05), (x + 0.07, s * (wy + 0.13), z1 - 0.05), (x - 0.07, s * (wy + 0.13), z1 - 0.05)],
                  [(x - 0.07, s * (wy - 0.04), z0 + 0.05), (x + 0.07, s * (wy - 0.04), z0 + 0.05), (x + 0.07, s * (wy + 0.21), z1 - 0.05), (x - 0.07, s * (wy + 0.21), z1 - 0.05)]], 'plate', bevel=0.015)
        box(((x0 + x1) / 2, s * (wy + 0.06), z1 + 0.03), ((x1 - x0) / 2 + 0.05, 0.11, 0.035), 'hazard', bevel=0.01)
    for x, lean in ((x0, -0.2), (x1, 0.12)):
        loft([[(x, -wy + 0.2, z0), (x, wy - 0.2, z0), (x + lean, wy, z1), (x + lean, -wy, z1)],
              [(x + 0.1, -wy + 0.2, z0), (x + 0.1, wy - 0.2, z0), (x + lean + 0.1, wy, z1), (x + lean + 0.1, -wy, z1)]], 'armor', bevel=0.02)
    box(((x0 + x1) / 2, 0, z0 + 0.03), ((x1 - x0) / 2, wy - 0.25, 0.03), 'dark')
    # Cutter boom and toothed grinding drum out front.
    for s in (1, -1):
        m = F.mark()
        box((3.3, s * 1.0, 1.0), (1.0, 0.1, 0.14), 'armor', bevel=0.03)
        cyl((2.5, s * 0.8, 1.2), (3.6, s * 0.8, 1.1), 0.07, 8, 'barrel')
        F.rot_all(m, 'Y', 12, about=(2.4, 0, 1.0))
    dz = 0.66
    with F.group('Drum'):   # its own part so the game can spin it while mining
        cyl((4.25, -1.25, dz), (4.25, 1.25, dz), 0.52, 14, 'barrel')
        for k in range(14):
            for j in range(5):
                a = 360.0 * k / 14 + j * 13
                t = box((0.56, -1.0 + j * 0.5, 0), (0.1, 0.07, 0.05), 'plate')
                t['uv'] = 0.4
                F.rot(t, 'Y', a)
                F.move(t, (4.25, 0, dz))
        for s in (1, -1):
            cyl((4.25, s * 1.25, dz), (4.25, s * 1.33, dz), 0.3, 10, 'hazard')
            box((4.25, s * 1.34, dz), (0.1, 0.012, 0.1), 'amber')
    box((3.6, 0, 1.25), (0.25, 1.1, 0.06), 'hazard', bevel=0.02)
    # Conveyor from the drum up into the hopper.
    loft([[(3.5, -0.35, 0.85), (3.5, 0.35, 0.85), (0.7, 0.35, z1 + 0.1), (0.7, -0.35, z1 + 0.1)],
          [(3.5, -0.35, 1.0), (3.5, 0.35, 1.0), (0.7, 0.35, z1 + 0.25), (0.7, -0.35, z1 + 0.25)]], 'dark', bevel=0.02)
    return dict(pivot=[('Drum', (4.25, 0, dz), 'DrumPivot')])


@asset('human/hauler.glb', 'Terran Hauler (cargo tug)')
def hauler():
    L, hw, top = 6.8, 1.22, 1.2
    K.chassis(L, hw, top, stowage=False, nose=0.9)
    cab(2.2, 0.0, top + 0.02, 0.8, 0.9, 0.75)
    # Flat cargo bed with low drop sides, stake posts and a tailgate.
    x0, x1, wy, z0 = -3.5, 1.2, 1.7, top + 0.12
    box(((x0 + x1) / 2, 0, z0 - 0.05), ((x1 - x0) / 2, wy, 0.07), 'armor', bevel=0.03)
    box(((x0 + x1) / 2, 0, z0 + 0.03), ((x1 - x0) / 2 - 0.1, wy - 0.12, 0.012), 'deck')
    for s in (1, -1):
        box(((x0 + x1) / 2, s * (wy - 0.04), z0 + 0.3), ((x1 - x0) / 2, 0.05, 0.28), 'armor', bevel=0.02)
        box(((x0 + x1) / 2, s * (wy + 0.015), z0 + 0.5), ((x1 - x0) / 2 - 0.1, 0.012, 0.06), 'hazard')
        for k in range(5):
            x = x0 + 0.2 + k * (x1 - x0 - 0.4) / 4
            box((x, s * (wy + 0.03), z0 + 0.36), (0.06, 0.035, 0.36), 'plate', bevel=0.015)
        box((x0 - 0.02, s * 1.2, z0 + 0.15), (0.02, 0.16, 0.05), 'red')
    box((x0 + 0.04, 0, z0 + 0.3), (0.05, wy - 0.1, 0.28), 'armor', bevel=0.02)
    box((x1 - 0.04, 0, z0 + 0.5), (0.06, wy - 0.05, 0.5), 'armor', bevel=0.02)
    box((x1 - 0.11, 0, z0 + 0.6), (0.012, wy * 0.6, 0.2), 'vent')
    # Loading crane stub at the front of the bed.
    cyl((x1 - 0.3, -1.3, z0), (x1 - 0.3, -1.3, z0 + 1.2), 0.1, 8, 'dark')
    m = F.mark()
    box((x1 - 1.0, -1.3, z0 + 1.2), (0.8, 0.07, 0.07), 'plate', bevel=0.02)
    cyl((x1 - 1.7, -1.3, z0 + 1.15), (x1 - 1.7, -1.3, z0 + 0.85), 0.03, 6, 'dark')
    box((x1 - 1.7, -1.3, z0 + 0.8), (0.07, 0.07, 0.05), 'amber')
    F.rot_all(m, 'Y', 12, about=(x1 - 0.3, 0, z0 + 1.2))
    return {}


@asset('human/mender.glb', 'Terran Mender (repair vehicle)')
def mender():
    L, hw, top = 6.4, 1.22, 1.42
    K.chassis(L, hw, top, stowage=False)
    cab(1.7, 0.0, top + 0.02, 0.7, 0.8, 0.6)
    # Workshop body: tool lockers, spares, a welding-gas rack.
    box((-1.6, 0, top + 0.4), (1.35, 1.15, 0.4), 'armor', bevel=0.05)
    for s in (1, -1):
        for k in range(3):
            box((-2.5 + k * 0.9, s * 1.16, top + 0.42), (0.38, 0.012, 0.28), 'plate', bevel=0.01)
            box((-2.5 + k * 0.9, s * 1.18, top + 0.42), (0.1, 0.012, 0.02), 'dark')
        for k in range(3):
            cyl((-2.6 + k * 0.42, s * 0.75, top + 0.82), (-2.6 + k * 0.42, s * 0.75, top + 1.25), 0.15, 10, 'plate')
            cyl((-2.6 + k * 0.42, s * 0.75, top + 1.25), (-2.6 + k * 0.42, s * 0.75, top + 1.33), 0.06, 6, 'dark')
        box((-2.2, s * 0.75, top + 1.02), (0.7, 0.19, 0.03), 'dark')
    K.plus(-0.75, 0, top + 0.815, 0.3)
    box((-2.96, 0, top + 0.4), (0.012, 0.8, 0.2), 'hazard')
    tz = top + 0.82
    with F.group('Arm'):
        tube((-1.7, 0, tz), (-1.7, 0, tz + 0.3), [(0, 0.5), (0.6, 0.5), (1, 0.36)], 12, 'dark')
        box((-1.7, 0, tz + 0.5), (0.28, 0.3, 0.3), 'armor', bevel=0.05)
        m = F.mark()
        box((-0.2, 0, tz + 0.55), (1.6, 0.14, 0.16), 'plate', bevel=0.04)
        box((-0.2, 0, tz + 0.73), (1.3, 0.05, 0.03), 'hazard')
        cyl((-1.4, 0.2, tz + 0.4), (0.4, 0.2, tz + 0.5), 0.06, 8, 'barrel')
        F.rot_all(m, 'Y', -32, about=(-1.7, 0, tz + 0.55))
        ex, ez = -1.7 + 3.2 * math.cos(math.radians(32)), tz + 0.55 + 3.2 * math.sin(math.radians(32))
        cyl((ex, -0.22, ez), (ex, 0.22, ez), 0.2, 10, 'dark')
        m = F.mark()
        box((ex + 1.0, 0, ez), (1.0, 0.11, 0.12), 'plate', bevel=0.03)
        # Tool head: welding emitter between two claws.
        box((ex + 2.1, 0, ez), (0.2, 0.2, 0.18), 'dark', bevel=0.04)
        tube((ex + 2.3, 0, ez), (ex + 2.65, 0, ez), [(0, 0.1), (0.7, 0.07), (1, 0.03)], 8, 'glow')
        for s in (1, -1):
            prism([(ex + 2.2, ez + s * 0.12), (ex + 2.75, ez + s * 0.3), (ex + 2.95, ez + s * 0.1), (ex + 2.8, ez + s * 0.16), (ex + 2.3, ez + s * 0.04)][::s],
                  -0.05, 0.05, 'barrel', bevel=0.012)
        F.rot_all(m, 'Y', 38, about=(ex, 0, ez))
        K.beacon(-1.7, 0, tz + 0.8, 'glow')
    return dict(pivot=('Arm', (-1.7, 0, tz)))


@asset('human/watchman.glb', 'Terran Watchman (mobile radar)')
def watchman():
    L, hw, top = 6.4, 1.22, 1.42
    K.chassis(L, hw, top, stowage=False)
    cab(1.8, 0.0, top + 0.02, 0.65, 0.8, 0.5)
    box((-1.4, 0, top + 0.3), (1.5, 1.1, 0.3), 'armor', bevel=0.05)
    for s in (1, -1):
        K.vent((-2.2, s * 0.6, top + 0.62), (0.4, 0.3, 0.04))
        box((-1.4, s * 1.11, top + 0.32), (1.2, 0.012, 0.02), 'glow')
        K.antenna(-2.7, s * 0.9, top + 0.6, 1.6)
    box((-0.3, 0.6, top + 0.72), (0.3, 0.25, 0.12), 'plate', bevel=0.03)
    tz = top + 0.62
    with F.group('Dish'):
        tube((-1.2, 0, tz), (-1.2, 0, tz + 0.5), [(0, 0.6), (0.3, 0.6), (0.5, 0.3), (1, 0.26)], 12, 'dark')
        for s in (1, -1):
            prism([(-1.6, tz + 0.4), (-0.8, tz + 0.4), (-0.95, tz + 2.1), (-1.45, tz + 2.1)], min(s * 0.3, s * 0.44), max(s * 0.3, s * 0.44), 'plate', bevel=0.03)
        cyl((-1.2, -0.5, tz + 1.8), (-1.2, 0.5, tz + 1.8), 0.12, 8, 'dark')
        m = F.mark()
        c = (-1.2, 0, tz + 1.8)
        prof = [(0.12, 0.0), (0.9, 0.1), (1.6, 0.36), (2.15, 0.8), (2.22, 0.8), (1.62, 0.3), (0.9, 0.02), (0.12, -0.1)]
        F.lathe(prof, 18, 'armor', center=c, sharp=40)
        for k in range(6):   # back ribs
            a = math.radians(60 * k)
            r = F.loft([[(0.3, -0.03, -0.12), (0.3, 0.03, -0.12), (2.0, 0.03, 0.62), (2.0, -0.03, 0.62)],
                        [(0.3, -0.03, -0.3), (0.3, 0.03, -0.3), (2.0, 0.03, 0.55), (2.0, -0.03, 0.55)]], 'plate')
            F.rot(r, 'Z', 60 * k)
            F.move(r, c)
        F.lathe([(2.16, 0.78), (2.26, 0.8), (2.2, 0.86)], 18, 'glow', center=c)
        cyl((c[0], c[1], c[2] + 0.02), (c[0], c[1], c[2] + 1.35), 0.04, 6, 'dark')
        for k in range(3):
            st = cyl((1.3, 0, 0.26), (0.06, 0, 1.3), 0.025, 4, 'dark')
            F.rot(st, 'Z', 120 * k + 30)
            F.move(st, c)
        orb((c[0], c[1], c[2] + 1.4), 0.16, 'glow')
        F.rot_all(m, 'Y', 62, about=c)
        box((-1.9, 0, tz + 1.8), (0.3, 0.3, 0.3), 'dark', bevel=0.05)
    return dict(pivot=('Dish', (-1.2, 0, tz)))


@asset('human/bastion_packed.glb', 'Terran Bastion Gun, packed for transport')
def bastion_packed():
    L, hw, top = 6.2, 1.22, 1.25
    K.chassis(L, hw, top, stowage=False, nose=0.9)
    cab(2.1, 0.0, top + 0.02, 0.6, 0.8, 0.5)
    z0 = top + 0.06
    box((-0.9, 0, z0), (2.1, 1.5, 0.07), 'armor', bevel=0.03)
    # The folded gun: octagonal base on its side rails, turret block, twin barrels stowed rearward.
    tube((-0.6, 0, z0 + 0.07), (-0.6, 0, z0 + 0.35), [(0, 1.15), (0.7, 1.15), (1, 0.95)], 8, 'plate', sharp=30)
    turret_shell(-1.6, 0.7, 0.85, z0 + 0.3, 0.62)
    box((-1.7, 0, z0 + 0.6), (0.14, 0.55, 0.18), 'dark', bevel=0.03)
    for s in (1, -1):
        m = F.mark()
        K.railgun(0.0, 2.6, s * 0.3, z0 + 0.6, 0.1)
        F.rot_all(m, 'Z', 180, about=(-0.85, 0, 0))
        # Folded stabiliser legs with hazard feet.
        box((-0.6, s * 1.42, z0 + 0.3), (1.2, 0.07, 0.1), 'armor', bevel=0.03)
        box((0.55, s * 1.42, z0 + 0.3), (0.16, 0.14, 0.14), 'hazard', bevel=0.03)
        box((-1.75, s * 1.42, z0 + 0.3), (0.16, 0.14, 0.14), 'hazard', bevel=0.03)
        box((-0.6, s * 1.5, z0 + 0.3), (0.8, 0.012, 0.02), 'amber')
    return {}


@asset('human/spire_packed.glb', 'Terran Spire Missile Battery, packed for transport')
def spire_packed():
    L, hw, top = 6.2, 1.22, 1.25
    K.chassis(L, hw, top, stowage=False, nose=0.9)
    cab(2.1, 0.0, top + 0.02, 0.6, 0.8, 0.5)
    z0 = top + 0.06
    box((-0.9, 0, z0), (2.1, 1.5, 0.07), 'armor', bevel=0.03)
    # Launch stack lying on its cradle, nose to the rear, plus the folded base.
    for s in (1, -1):
        box((-0.9, s * 0.6, z0 + 0.2), (1.7, 0.08, 0.14), 'dark', bevel=0.03)
    m = F.mark()
    K.missile_box((-0.8, 0, z0 + 0.82), (1.75, 0.72, 0.46), nx=3, nz=2)
    F.rot_all(m, 'Z', 180, about=(-0.8, 0, 0))
    box((-0.8, 0, z0 + 1.3), (1.2, 0.5, 0.012), 'hazard')
    tube((1.0, 0, z0 + 0.3), (1.25, 0, z0 + 0.3), [(0, 0.5), (1, 0.42)], 8, 'plate', sharp=30)
    for s in (1, -1):
        box((-0.9, s * 1.42, z0 + 0.3), (1.2, 0.07, 0.1), 'armor', bevel=0.03)
        box((0.25, s * 1.42, z0 + 0.3), (0.16, 0.14, 0.14), 'hazard', bevel=0.03)
        box((-2.05, s * 1.42, z0 + 0.3), (0.16, 0.14, 0.14), 'hazard', bevel=0.03)
        box((-0.9, s * 1.5, z0 + 0.3), (0.8, 0.012, 0.02), 'amber')
    return {}


@asset('human/falcon.glb', 'Terran Falcon (fighter)')
def falcon():
    import compat
    compat.install()
    import aircraft2
    aircraft2.hornet()
    return dict(name='TerranHornet', single=True)


@asset('human/condor.glb', 'Terran Condor (bomber)', size=1024)
def condor():
    import compat
    compat.install()
    import aircraft2
    aircraft2.hammer()
    return dict(name='TerranHammerhead', single=True)
