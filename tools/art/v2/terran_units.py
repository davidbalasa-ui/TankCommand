"""Terran units, art pass v2."""
import math

import forge as F
from forge import box, cyl, hull, loft, plate, prism, sym, tube, orb, lathe, sweep
import terran_kit as K
import terran_v3 as V

ASSETS = {}


def asset(path, label, size=512):
    def deco(fn):
        def run(glb, render, report):
            F.begin('terran')
            F.ST['tread'] = True
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
                  0, 0.07, 'olive', bevel=0.025)
        F.rot(p, 'X', 22, about=(0, 0, tz + 0.18))
        F.move(p, (0, w * 1.0, 0.0))
        if s < 0:
            F.xf(p, F.Matrix.Diagonal((1, -1, 1, 1)))
        box(((xa + xb) / 2, s * w * 0.99, tz + h * 0.5), (L * 0.16, 0.02, 0.02), 'glow')
        K.smoke(xb - 0.1, s * w * 0.9, tz + h * 0.72, s)
        K.id_marks(x0 + L * 0.08, s * w * 0.86, tz + h * 0.52, s)
    if cupola:
        K.cupola(x0 + L * 0.36, w * 0.3, tz + h + 0.04, w * 0.25)
    # Flat radar puck on a short post at the roof rear.
    cyl((x0 + L * 0.2, -w * 0.2, tz + h * 0.95), (x0 + L * 0.2, -w * 0.2, tz + h + 0.2), 0.035, 6, 'steel')
    tube((x0 + L * 0.2, -w * 0.2, tz + h + 0.2), (x0 + L * 0.2, -w * 0.2, tz + h + 0.27), [(0, w * 0.14), (0.3, w * 0.17), (0.8, w * 0.17), (1, w * 0.1)], 12, 'plate', sharp=30)
    box((x0 + L * 0.2 + w * 0.17, -w * 0.2, tz + h + 0.235), (0.008, w * 0.07, 0.016), 'glow')
    # Sensor head.
    box((x0 + L * 0.5, -w * 0.36, tz + h + 0.14), (0.2, 0.16, 0.11), 'dark', bevel=0.03)
    box((x0 + L * 0.5 + 0.2, -w * 0.36, tz + h + 0.15), (0.012, 0.1, 0.06), 'glass')
    box((x0 + L * 0.5, -w * 0.36, tz + h + 0.26), (0.08, 0.08, 0.012), 'amber')
    if rack:
        for s in (1, -1):
            box((x0 - 0.12, s * w * 0.5, tz + h * 0.5), (0.2, 0.03, 0.03), 'dark')
        K.basket(x0 - 0.42, x0 + 0.02, w * 0.6, tz + h * 0.3, h * 0.36)
    K.antenna(x0 + 0.25, w * 0.5, tz + h * 0.9, 1.25)
    K.antenna(x0 + 0.25, -w * 0.5, tz + h * 0.9, 0.9, tip='glow')


@asset('human/lancer.glb', 'Terran Lancer (light tank)')
def lancer():
    L, hw, top = 6.4, 1.22, 1.42
    V.scifi_chassis(L, hw, top, pod=1.68, w=0.42, nwheels=5)
    tz, th = top + 0.04, 0.7
    with F.group('Turret'):
        tube((-0.35, 0, tz - 0.03), (-0.35, 0, tz + 0.09), [(0, 1.02), (1, 0.98)], 20, 'dark')
        V.arrow_turret(-1.9, 1.5, 1.05, tz, th)
        gz = tz + 0.36
        for s in (1, -1):
            # Cheek block carrying each lance, tight against the needle nose.
            prism([(0.2, gz - 0.3), (1.5, gz - 0.24), (1.9, gz), (1.5, gz + 0.24), (0.2, gz + 0.34)], min(s * 0.3, s * 0.74), max(s * 0.3, s * 0.74), 'plate', bevel=0.035)
            V.neon((0.9, s * 0.75, gz), (0.45, 0.012, 0.02))
            sd = 'L' if s > 0 else 'R'
            V.tele_cannon(1.2, 6.2, gz, 0.2, 4, y=s * 0.52, piston=False, prefix='Barrel' + sd, flash_group='Flash' + sd)
    p = (1.2, 0, gz)
    piv = [('Turret', (-0.35, 0, tz))]
    for sd, sy in (('L', 1), ('R', -1)):
        piv += [(f'Barrel{sd}{k}', p, f'Barrel{sd}{k}Pivot', 'Turret') for k in (1, 2, 3, 4)]
        piv += [('Flash' + sd, p, f'Flash{sd}Pivot', f'Barrel{sd}4'), ('Blade' + sd, (-1.4, sy * 0.756, tz + 0.49), f'Blade{sd}Pivot', 'Turret')]
    return dict(pivot=piv)


@asset('human/outrider.glb', 'Terran Outrider (scout)')
def outrider():
    # Six-wheeled dart: narrow faceted body, needle prow, no crew.
    hull([(-3.0, [(0, 0.8), (0.7, 0.8), (0.82, 1.08), (0.56, 1.36), (0, 1.36)]),
          (-2.2, [(0, 0.62), (0.98, 0.62), (1.12, 1.08), (0.68, 1.64), (0, 1.66)]),
          (0.4, [(0, 0.62), (0.98, 0.62), (1.12, 1.08), (0.64, 1.56), (0, 1.6)]),
          (2.1, [(0, 0.64), (0.8, 0.64), (0.9, 1.0), (0.46, 1.18), (0, 1.22)]),
          (4.0, [(0, 0.8), (0.1, 0.8), (0.14, 0.86), (0.07, 0.9), (0, 0.91)])], 'hull', bevel=0.04)
    box((-0.2, 0, 0.55), (2.3, 0.8, 0.1), 'dark', bevel=0.03)
    prism([(0.5, 1.58), (3.7, 0.9), (2.0, 1.3), (0.5, 1.7)], -0.08, 0.08, 'armor', bevel=0.02)
    V.reactor(-2.85, 1.64, 0.9, n=5, L=0.9)
    for s in (1, -1):
        V.eye((1.4, s * 0.36, 1.4), 11.5, s * 16, 0.4, 0.1)
        V.neon((-0.9, s * 1.115, 1.08), (1.2, 0.014, 0.018))
        box((3.45, s * 0.12, 0.9), (0.1, 0.02, 0.014), 'amber')
        box((-3.02, s * 0.5, 1.0), (0.02, 0.08, 0.03), 'amber')
        for k in range(3):   # prow teeth
            tx = 2.5 + k * 0.32
            ty = 0.62 - 0.17 * k
            prism([(tx, 0.64), (tx + 0.2, 0.66), (tx + 0.24, 0.46)], min(s * ty, s * (ty - 0.07)), max(s * ty, s * (ty - 0.07)), 'steel', bevel=0.01)
        for i, x in enumerate((-1.9, 0.0, 1.9)):
            with F.group(f"Wheel{i}{'L' if s > 0 else 'R'}"):   # each wheel turns
                K.tire((x, s * 1.42, 0.6), 0.6, 0.46, s)
            cyl((x, s * 0.9, 0.6), (x, s * 1.3, 0.6), 0.1, 6, 'dark')
            # Knife-edged arch over each wheel, swept back, with an energy line.
            prism([(x - 0.95, 0.98), (x - 0.4, 1.34), (x + 0.6, 1.34), (x + 1.0, 0.9), (x + 0.88, 0.88), (x + 0.52, 1.25),
                   (x - 0.36, 1.25), (x - 0.86, 0.92)], min(s * 1.05, s * 1.46), max(s * 1.05, s * 1.46), 'armor' if i != 1 else 'plate', bevel=0.02)
            V.neon((x + 0.1, s * 1.47, 1.295), (0.38, 0.012, 0.018))
            box((x, s * 1.08, 0.74), (0.3, 0.17, 0.03), 'steel', bevel=0.01)
            K.ram((x - 0.3, s * 0.98, 1.16), (x - 0.12, s * 1.2, 0.76), 0.045)
        # Swept tail blade.
        prism([(-3.0, 1.2), (-2.2, 1.3), (-2.5, 1.7), (-3.6, 2.15)], min(s * 0.62, s * 0.68), max(s * 0.62, s * 0.68), 'plate', bevel=0.015)
        box((-3.2, s * 0.69, 1.9), (0.14, 0.008, 0.02), 'amber')
    tz = 1.62
    gz = tz + 0.24
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.03), (-0.5, 0, tz + 0.07), [(0, 0.66), (1, 0.62)], 16, 'dark')
        V.arrow_turret(-1.3, 0.55, 0.68, tz, 0.5, bs=0.55)
        box((0.5, 0, gz), (0.3, 0.2, 0.17), 'plate', bevel=0.04)
        V.tele_cannon(0.6, 3.6, gz, 0.11, 4, piston=False)
        # Scout sensor mast with a rotating scanner bar.
        for kk, (rr, hh) in enumerate(((0.075, 0.38), (0.055, 0.36), (0.038, 0.3))):
            zb = tz + 0.42 + sum(h for _, h in ((0.075, 0.38), (0.055, 0.36), (0.038, 0.3))[:kk])
            cyl((-0.95, -0.3, zb), (-0.95, -0.3, zb + hh), rr, 6, 'steel' if kk % 2 else 'dark')
            cyl((-0.95, -0.3, zb + hh - 0.03), (-0.95, -0.3, zb + hh), rr * 1.3, 6, 'black')
        box((-0.95, -0.3, tz + 1.38), (0.13, 0.13, 0.1), 'dark', bevel=0.03)
        cyl((-0.82, -0.3, tz + 1.38), (-0.8, -0.3, tz + 1.38), 0.07, 8, 'hot')
        with F.group('Radar'):
            cyl((-0.95, -0.3, tz + 1.48), (-0.95, -0.3, tz + 1.64), 0.045, 6, 'steel')
            prism([(-1.0, tz + 1.64), (-0.9, tz + 1.64), (-0.88, tz + 1.78), (-1.02, tz + 1.78)], -0.95, 0.35, 'plate', bevel=0.015)
            box((-0.875, -0.3, tz + 1.71), (0.008, 0.55, 0.02), 'hot')
    wheels = [(f"Wheel{i}{'L' if sd > 0 else 'R'}", (x, sd * 1.42, 0.6), f"Wheel{i}{'L' if sd > 0 else 'R'}Pivot")
              for sd in (1, -1) for i, x in enumerate((-1.9, 0.0, 1.9))]
    return dict(pivot=[('Turret', (-0.5, 0, tz))] + wheels + [('Radar', (-0.95, -0.3, tz + 1.5), 'RadarPivot', 'Turret')]
                + V.cannon_pivots((0.6, 0, gz)) + V.blade_pivots(-1.3, 0.68, tz, 0.5))


@asset('human/skimmer.glb', 'Terran Skimmer (hover tank)')
def skimmer():
    # Hover dart on four ducted fans, with a glowing repulsor keel instead of a skirt.
    hull([(-3.3, [(0, 0.7), (0.9, 0.7), (1.1, 0.86), (0.8, 1.2), (0, 1.25)]),
          (-2.4, [(0, 0.5), (1.45, 0.5), (1.8, 0.82), (1.2, 1.46), (0, 1.52)]),
          (0.6, [(0, 0.5), (1.45, 0.5), (1.8, 0.82), (1.1, 1.36), (0, 1.42)]),
          (2.4, [(0, 0.55), (0.95, 0.55), (1.15, 0.78), (0.6, 1.02), (0, 1.06)]),
          (4.4, [(0, 0.7), (0.12, 0.7), (0.16, 0.76), (0.08, 0.8), (0, 0.81)])], 'hull', bevel=0.04)
    hull([(-3.0, [(0, 0.26), (1.1, 0.26), (1.3, 0.52), (0, 0.52)]),
          (0.8, [(0, 0.22), (1.3, 0.22), (1.5, 0.52), (0, 0.52)]),
          (3.2, [(0, 0.4), (0.35, 0.4), (0.45, 0.6), (0, 0.6)])], 'black', bevel=0.03)
    prism([(0.7, 1.4), (4.1, 0.8), (2.2, 1.18), (0.7, 1.52)], -0.09, 0.09, 'armor', bevel=0.02)
    V.reactor(-3.15, 1.5, 1.1, n=6, L=1.0)
    for s in (1, -1):
        V.eye((1.7, s * 0.42, 1.24), 11.3, s * 18, 0.44, 0.11)
        for x, r in ((1.55, 0.56), (-1.75, 0.64)):
            V.fan_pod(x, s * 1.78, s, r, f"Fan{'F' if x > 0 else 'B'}{'L' if s > 0 else 'R'}")
            box((x, s * 1.3, 0.76), (0.34, 0.3, 0.12), 'plate', bevel=0.03)
            K.ram((x - 0.34, s * 1.0, 1.24), (x - 0.2, s * 1.52, 1.0), 0.045)
        for i, xa in enumerate((-2.0, -0.92, 0.16)):   # raked armour tiles down the flank
            xb = xa + 0.98
            loft([[(xa + 0.2, s * 1.84, 0.86), (xb + 0.2, s * 1.84, 0.86), (xb - 0.1, s * 1.3, 1.4), (xa - 0.1, s * 1.3, 1.4)],
                  [(xa + 0.24, s * 1.9, 0.9), (xb + 0.16, s * 1.9, 0.9), (xb - 0.14, s * 1.37, 1.44), (xa - 0.06, s * 1.37, 1.44)]], 'plate' if i != 1 else 'armor', bevel=0.02)
        V.neon((0.1, s * 1.83, 0.8), (0.9, 0.012, 0.02))
        box((2.3, s * 1.2, 0.8), (0.12, 0.012, 0.03), 'amber')
        for k in range(3):   # repulsor slots along the keel edge
            V.neon((-1.6 + 1.3 * k, s * 1.36, 0.4), (0.36, 0.012, 0.03))
        for k in range(4):   # prow teeth
            tx = 2.5 + k * 0.38
            ty = 0.8 - 0.19 * k
            prism([(tx, 0.56), (tx + 0.22, 0.6), (tx + 0.26, 0.38)], min(s * ty, s * (ty - 0.08)), max(s * ty, s * (ty - 0.08)), 'steel', bevel=0.01)
        # Rear thrusters burning white-blue.
        tube((-3.1, s * 0.62, 0.95), (-3.65, s * 0.62, 0.95), [(0, 0.34), (0.6, 0.36), (1, 0.28)], 8, 'armor', sharp=20)
        cyl((-3.6, s * 0.62, 0.95), (-3.66, s * 0.62, 0.95), 0.25, 10, 'neon')
        cyl((-3.62, s * 0.62, 0.95), (-3.68, s * 0.62, 0.95), 0.14, 10, 'hot')
        # Swept stabiliser blades.
        prism([(-3.45, 1.15), (-2.1, 1.15), (-2.75, 1.6), (-3.9, 2.35)], s * 1.0 - 0.035, s * 1.0 + 0.035, 'armor', bevel=0.02)
        box((-3.5, s * 1.04, 2.0), (0.16, 0.008, 0.02), 'amber')
        V.neon((-2.9, s * 1.04, 1.4), (0.3, 0.008, 0.02))
    tz = 1.48
    gz = tz + 0.27
    with F.group('Turret'):
        tube((-0.4, 0, tz - 0.03), (-0.4, 0, tz + 0.07), [(0, 0.78), (1, 0.74)], 16, 'dark')
        V.arrow_turret(-1.35, 0.9, 0.82, tz, 0.56, bs=0.7)
        for s in (1, -1):
            sd = 'L' if s > 0 else 'R'
            prism([(0.1, gz - 0.2), (0.9, gz - 0.16), (1.15, gz), (0.9, gz + 0.16), (0.1, gz + 0.22)], min(s * 0.16, s * 0.5), max(s * 0.16, s * 0.5), 'plate', bevel=0.03)
            V.tele_cannon(0.8, 4.3, gz, 0.13, 4, y=s * 0.32, piston=False, prefix='Barrel' + sd, flash_group='Flash' + sd)
    fans = [(f"Fan{'F' if x > 0 else 'B'}{'L' if sd > 0 else 'R'}", (x, sd * 1.78, 0.84),
             f"Fan{'F' if x > 0 else 'B'}{'L' if sd > 0 else 'R'}Pivot") for sd in (1, -1) for x in (1.55, -1.75)]
    return dict(pivot=[('Turret', (-0.4, 0, tz))] + fans + V.cannon_pivots((0.8, 0, gz), ('L', 'R')) + V.blade_pivots(-1.35, 0.82, tz, 0.56))


@asset('human/bulwark.glb', 'Terran Bulwark (heavy tank)', size=1024)
def bulwark():
    L, hw, top = 7.8, 1.5, 1.62
    V.scifi_chassis(L, hw, top, pod=2.08, w=0.56, nwheels=6, nose=1.0, prow=1.45, fin=0.85)
    for s in (1, -1):
        # Heavy slab armour hung over the skirts, raked like the rest.
        for k in range(3):
            x = -2.5 + k * 2.05
            ya = s * (2.08 + 0.56 + 0.14)
            prism([(x - 0.6, 0.84), (x + 1.05, 0.84), (x + 0.8, 1.42), (x - 0.85, 1.42)], min(ya, ya + s * 0.12), max(ya, ya + s * 0.12), 'plate' if k % 2 else 'armor', bevel=0.035)
            V.neon((x + 0.1, ya + s * 0.125, 1.14), (0.5, 0.012, 0.022))
            for bx in (x - 0.45, x + 0.7):
                cyl((bx, ya + s * 0.1, 0.98), (bx, ya + s * 0.14, 0.98), 0.04, 6, 'steel')
    tz, th = top + 0.04, 0.95
    gz = tz + 0.45
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.03), (-0.5, 0, tz + 0.1), [(0, 1.4), (1, 1.34)], 24, 'dark')
        V.arrow_turret(-2.6, 1.8, 1.4, tz, th, bs=1.3)
        for s in (1, -1):
            sd = 'L' if s > 0 else 'R'
            prism([(0.2, gz - 0.44), (2.0, gz - 0.36), (2.6, gz), (2.0, gz + 0.36), (0.2, gz + 0.5)], min(s * 0.2, s * 1.02), max(s * 0.2, s * 1.02), 'plate', bevel=0.045)
            V.neon((1.1, s * 1.03, gz), (0.6, 0.012, 0.028))
            V.tele_cannon(1.8, 8.6, gz, 0.3, 4, y=s * 0.6, piston=False, prefix='Barrel' + sd, flash_group='Flash' + sd)
            # Shoulder capacitor bank feeding the gun: armoured block, cooling blades, glowing cells.
            box((-1.3, s * 1.78, tz + 0.52), (0.95, 0.3, 0.3), 'armor', bevel=0.07)
            box((-1.3, s * 1.42, tz + 0.45), (0.5, 0.12, 0.14), 'dark')
            box((-1.3, s * 2.09, tz + 0.52), (0.7, 0.012, 0.1), 'coilhot')
            for k in range(5):
                fx = -2.0 + k * 0.35
                prism([(fx, tz + 0.8), (fx + 0.3, tz + 0.8), (fx + 0.05, tz + 1.12), (fx - 0.3, tz + 1.2)], min(s * 1.56, s * 2.0), max(s * 1.56, s * 2.0), 'plate', bevel=0.012)
            box((-0.3, s * 1.78, tz + 0.52), (0.03, 0.2, 0.18), 'amber')
    return dict(pivot=[('Turret', (-0.5, 0, tz))] + V.cannon_pivots((1.8, 0, gz), ('L', 'R')) + V.blade_pivots(-2.6, 1.4, tz, th))


@asset('human/javelin.glb', 'Terran Javelin (missile tank)')
def javelin():
    L, hw, top = 6.4, 1.22, 1.42
    V.scifi_chassis(L, hw, top)
    tz = top + 0.04
    pz = tz + 0.72
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.03), (-0.5, 0, tz + 0.14), [(0, 1.0), (1, 0.9)], 20, 'dark')
        hull([(-1.9, [(0, tz + 0.2), (0.4, tz + 0.2), (0.5, tz + 0.55), (0.3, tz + 0.9), (0, tz + 0.9)]),
              (-1.2, [(0, tz + 0.12), (0.62, tz + 0.12), (0.74, tz + 0.55), (0.42, tz + 1.08), (0, tz + 1.08)]),
              (0.3, [(0, tz + 0.12), (0.62, tz + 0.12), (0.74, tz + 0.5), (0.36, tz + 0.92), (0, tz + 0.92)]),
              (1.6, [(0, tz + 0.14), (0.1, tz + 0.14), (0.13, tz + 0.3), (0.06, tz + 0.4), (0, tz + 0.41)])], 'armor', bevel=0.04)
        cyl((-0.5, -1.0, pz), (-0.5, 1.0, pz), 0.2, 8, 'dark')
        msl = []
        for s in (1, -1):
            # Swept yoke blade and trunnion.
            prism([(-1.25, tz + 0.2), (0.25, tz + 0.2), (-0.2, tz + 1.02), (-1.1, tz + 1.3)], min(s * 0.8, s * 0.9), max(s * 0.8, s * 0.9), 'plate', bevel=0.03)
            cyl((-0.5, s * 0.78, pz), (-0.5, s * 0.94, pz), 0.27, 8, 'steel')
            cyl((-0.5, s * 0.94, pz), (-0.5, s * 0.97, pz), 0.15, 8, 'hot')
            K.ram((0.2, s * 0.96, tz + 0.2), (0.75, s * 1.0, tz + 0.66), 0.06)
            m = F.mark()
            msl += K.missile_box((-0.7, s * 1.46, pz), (1.85, 0.5, 0.4), nx=3, nz=2, group='Msl' + 'LR'[s < 0])
            V.neon((-0.7, s * 1.975, pz), (1.3, 0.012, 0.03))
            V.neon((-0.7, s * 1.46, pz + 0.412), (1.2, 0.05, 0.012))
            # Raked dorsal blade and a fanged front lip on each pod.
            prism([(-2.4, pz + 0.4), (-0.7, pz + 0.4), (-1.7, pz + 0.85), (-3.1, pz + 1.0)], s * 1.46 - 0.03, s * 1.46 + 0.03, 'plate', bevel=0.012)
            for dy in (-0.42, 0.42):
                prism([(1.1, pz + 0.3), (1.55, pz + 0.36), (1.15, pz + 0.48)], s * 1.46 + dy - 0.04, s * 1.46 + dy + 0.04, 'steel', bevel=0.01)
                prism([(1.1, pz - 0.48), (1.55, pz - 0.36), (1.15, pz - 0.3)], s * 1.46 + dy - 0.04, s * 1.46 + dy + 0.04, 'steel', bevel=0.01)
            box((-2.57, s * 1.46, pz), (0.02, 0.3, 0.2), 'amber')
            F.rot_all(m, 'Y', -16, about=(-0.5, 0, pz))
        # Targeting sensor and a rotating fire-control panel.
        box((0.25, 0, tz + 1.02), (0.26, 0.2, 0.12), 'dark', bevel=0.04)
        box((0.52, 0, tz + 1.02), (0.012, 0.14, 0.05), 'hot')
        with F.group('Radar'):
            cyl((-1.1, 0, tz + 1.08), (-1.1, 0, tz + 1.5), 0.06, 6, 'steel')
            m = F.mark()
            prism([(-0.05, -0.32), (0.05, -0.32), (0.05, 0.32), (-0.05, 0.44)], -0.6, 0.6, 'plate', bevel=0.02)
            for k in (-1, 0, 1):
                box((0.055, 0, k * 0.2), (0.008, 0.5, 0.02), 'hot')
            F.rot_all(m, 'Y', -14)
            F.move_all(m, (-1.1, 0, tz + 1.82))
    return dict(pivot=[('Turret', (-0.5, 0, tz)), ('Radar', (-1.1, 0, tz + 1.5), 'RadarPivot', 'Turret')] + [(g, p, g + 'Pivot', 'Turret') for g, p in msl])


@asset('human/longbow.glb', 'Terran Longbow (artillery)', size=1024)
def longbow():
    L, hw, top = 7.2, 1.3, 1.42
    V.scifi_chassis(L, hw, top, pod=1.78, w=0.46, nwheels=6, prow=1.3, fin=0.75, claws=(-2.0, 1.2))
    tz = top + 0.04
    with F.group('Turret'):
        tube((-0.9, 0, tz - 0.03), (-0.9, 0, tz + 0.1), [(0, 1.15), (1, 1.05)], 20, 'dark')
        # Low wedge base with two shark-fin trunnion blades holding the cannon cradle.
        hull([(-2.5, [(0, tz + 0.1), (0.7, tz + 0.1), (0.8, tz + 0.4), (0.5, tz + 0.62), (0, tz + 0.62)]),
              (-0.6, [(0, tz + 0.1), (1.1, tz + 0.1), (1.18, tz + 0.4), (0.8, tz + 0.7), (0, tz + 0.7)]),
              (1.3, [(0, tz + 0.12), (0.3, tz + 0.12), (0.34, tz + 0.26), (0.2, tz + 0.36), (0, tz + 0.37)])], 'armor', bevel=0.04)
        gz = tz + 1.35
        for s in (1, -1):
            prism([(-2.2, tz + 0.5), (0.5, tz + 0.5), (-0.1, tz + 1.5), (-0.9, tz + 2.05), (-2.6, tz + 2.75), (-1.75, tz + 1.5)],
                  min(s * 0.72, s * 0.9), max(s * 0.72, s * 0.9), 'plate', bevel=0.03)
            cyl((-0.8, s * 0.7, gz), (-0.8, s * 0.97, gz), 0.3, 8, 'steel')
            cyl((-0.8, s * 0.97, gz), (-0.8, s * 1.0, gz), 0.17, 8, 'hot')
            V.neon((-1.1, s * 0.905, tz + 0.82), (0.5, 0.012, 0.022))
            box((-2.1, s * 0.905, tz + 2.2), (0.16, 0.012, 0.03), 'amber')
        m = F.mark()
        # Cradle housing the first sleeve slams back into.
        box((-1.35, 0, gz), (1.55, 0.62, 0.52), 'armor', bevel=0.07)
        box((-1.35, 0, gz + 0.53), (1.2, 0.2, 0.03), 'dark')
        V.neon((-1.35, 0, gz + 0.56), (1.1, 0.06, 0.012))
        for s in (1, -1):
            box((-1.6, s * 0.63, gz), (0.9, 0.012, 0.14), 'coilhot')
            for q in range(4):
                box((-2.3 + q * 0.45, s * 0.64, gz), (0.04, 0.02, 0.3), 'black')
        box((0.22, 0, gz), (0.06, 0.66, 0.56), 'plate', bevel=0.02)
        step = V.tele_cannon(0.2, 9.0, gz, 0.44, 4)
        F.rot_all(m, 'Y', -26, about=(-0.8, 0, gz))
        with F.group('Radar'):   # fire-control dish
            c = (-2.0, 0.0, tz + 0.75)
            cyl((c[0], c[1], tz + 0.55), c, 0.05, 8, 'steel')
            m = F.mark()
            F.lathe([(0.04, 0.0), (0.26, 0.05), (0.4, 0.15), (0.43, 0.15), (0.26, 0.01), (0.04, -0.05)], 6, 'plate', center=(0, 0, 0), sharp=40)
            box((0, 0, 0.2), (0.02, 0.02, 0.12), 'glow')
            F.rot_all(m, 'Y', -50)
            F.move_all(m, (c[0], c[1], c[2] + 0.12))
    p = (-0.8, 0, gz)
    return dict(pivot=[('Turret', (-0.9, 0, tz)), ('Radar', (-2.0, 0.0, tz + 0.75), 'RadarPivot', 'Turret')]
                + [(f'Barrel{k}', p, f'Barrel{k}Pivot', 'Turret') for k in (1, 2, 3, 4)] + [('Flash', p, 'FlashPivot', 'Barrel4')])


def cab(x, y, z, sx=0.7, sy=0.6, sz=0.55):
    """Unmanned sensor core where a cab would sit: faceted wedge, two slanted glowing eyes, swept blades. No crew, no windows."""
    prism([(x - sx, z), (x + sx * 1.25, z), (x + sx * 1.3, z + sz * 0.2), (x + sx * 0.3, z + sz), (x - sx * 0.8, z + sz), (x - sx, z + sz * 0.8)],
          y - sy, y + sy, 'armor', taper=0.7, bevel=0.03)
    ang = math.degrees(math.atan2(sz * 0.8, sx))
    for sg in (1, -1):
        V.eye((x + sx * 0.8, y + sg * sy * 0.36, z + sz * 0.62), ang, sg * 14, sx * 0.4, sy * 0.16)
        V.neon((x - sx * 0.1, y + sg * sy * 0.95, z + sz * 0.2), (sx * 0.45, 0.012, 0.02))
        prism([(x - sx, z + sz * 0.8), (x - sx * 0.2, z + sz), (x - sx * 0.7, z + sz + 0.35), (x - sx * 1.6, z + sz + 0.75)],
              y + sg * sy * 0.5 - 0.025, y + sg * sy * 0.5 + 0.025, 'plate', bevel=0.01)
    box((x - sx * 0.25, y, z + sz + 0.03), (sx * 0.5, sy * 0.16, 0.03), 'plate', bevel=0.012)
    V.neon((x - sx * 0.25, y, z + sz + 0.062), (sx * 0.4, sy * 0.05, 0.008))
    box((x - sx * 0.82, y, z + sz + 0.02), (0.05, sy * 0.3, 0.02), 'amber')
    box((x - sx - 0.012, y, z + sz * 0.45), (0.012, sy * 0.6, sz * 0.22), 'vent')


@asset('human/prospector.glb', 'Terran Prospector (ore miner)')
def prospector():
    L, hw, top = 6.6, 1.22, 1.3
    V.scifi_chassis(L, hw, top, nose=0.25, prow=0.4)
    cab(1.5, 0.62, top + 0.02, 0.78, 0.52, 0.76)
    # Ore hopper: double-skin sloped walls, rolled top rail, gussets, grizzly bars, tailgate with latch rams.
    x0, x1, wy, z0, z1 = -3.1, 0.55, 1.5, top + 0.02, top + 1.15
    for s in (1, -1):
        loft([[(x0, s * (wy - 0.25), z0), (x1, s * (wy - 0.25), z0), (x1, s * wy, z1), (x0, s * wy, z1)],
              [(x0, s * (wy - 0.1), z0), (x1, s * (wy - 0.1), z0), (x1, s * (wy + 0.16), z1), (x0, s * (wy + 0.16), z1)]], 'armor', bevel=0.02)
        for k in range(5):
            x = x0 + 0.3 + k * 0.78
            loft([[(x - 0.07, s * (wy - 0.1), z0 + 0.05), (x + 0.07, s * (wy - 0.1), z0 + 0.05), (x + 0.05, s * (wy + 0.16), z1 - 0.05), (x - 0.05, s * (wy + 0.16), z1 - 0.05)],
                  [(x - 0.07, s * (wy + 0.1), z0 + 0.05), (x + 0.07, s * (wy + 0.1), z0 + 0.05), (x + 0.05, s * (wy + 0.24), z1 - 0.05), (x - 0.05, s * (wy + 0.24), z1 - 0.05)]], 'plate', bevel=0.015)
        cyl((x0 - 0.1, s * (wy + 0.08), z1 + 0.03), (x1 + 0.1, s * (wy + 0.08), z1 + 0.03), 0.09, 8, 'hazard')
        box(((x0 + x1) / 2, s * (wy - 0.06), z1 - 0.2), ((x1 - x0) / 2 - 0.1, 0.012, 0.25), 'steel')     # scraped inner face
        K.ram((x0 + 0.5, s * (wy + 0.2), z0 + 0.55), (x0 - 0.12, s * (wy + 0.2), z0 + 0.85), 0.05)        # tailgate latch rams
    loft([[(x0, -wy + 0.2, z0), (x0, wy - 0.2, z0), (x0 - 0.2, wy, z1), (x0 - 0.2, -wy, z1)],
          [(x0 + 0.1, -wy + 0.2, z0), (x0 + 0.1, wy - 0.2, z0), (x0 - 0.1, wy, z1), (x0 - 0.1, -wy, z1)]], 'plate', bevel=0.02)
    box((x0 - 0.22, 0, z0 + 0.75), (0.02, wy * 0.7, 0.05), 'hazard')
    loft([[(x1, -wy + 0.2, z0), (x1, wy - 0.2, z0), (x1 + 0.12, wy, z1), (x1 + 0.12, -wy, z1)],
          [(x1 + 0.1, -wy + 0.2, z0), (x1 + 0.1, wy - 0.2, z0), (x1 + 0.22, wy, z1), (x1 + 0.22, -wy, z1)]], 'armor', bevel=0.02)
    box(((x0 + x1) / 2, 0, z0 + 0.03), ((x1 - x0) / 2, wy - 0.25, 0.03), 'dark')
    for k in range(5):
        box((x1 - 0.2 - k * 0.24, 0, z1 - 0.08), (0.03, wy - 0.05, 0.035), 'steel')
    with F.group('Ore'):   # the load; the game can hide it when the miner is empty
        K.ore_load(x0 + 0.25, x1 - 1.35, wy - 0.3, z0 + 0.1, z1 - z0 + 0.25)
    # Cutter head: boxed arms out to gearboxes on both drum ends, two fat lift rams, spray guard.
    dz, dx, dw = 0.8, 4.3, 2.0
    for s in (1, -1):
        sweep([(2.5, s * 1.25, 1.15), (3.3, s * (dw + 0.2), 1.05), (dx, s * (dw + 0.2), dz)], [(0.1, 0.16), (0.1, 0.16), (0.1, 0.14)], 'plate', sides=4)
        K.ram((2.3, s * 0.95, 1.35), (3.5, s * (dw + 0.02), 1.12), 0.075)
        tube((dx, s * (dw + 0.02), dz), (dx, s * (dw + 0.36), dz), [(0, 0.3), (0.2, 0.36), (0.8, 0.36), (1, 0.28)], 10, 'plate', sharp=30)
        for k in range(8):
            a = math.pi * k / 4
            box((dx + math.cos(a) * 0.29, s * (dw + 0.365), dz + math.sin(a) * 0.29), (0.03, 0.01, 0.03), 'steel')
        cyl((dx, s * (dw + 0.36), dz), (dx, s * (dw + 0.4), dz), 0.13, 8, 'hazard')
        tube((dx - 0.36, s * (dw + 0.2), dz + 0.36), (dx - 0.95, s * (dw + 0.2), dz + 0.46), [(0, 0.17), (0.1, 0.2), (0.9, 0.2), (1, 0.15)], 10, 'dark')   # motor can
        for k in range(4):
            cyl((dx - 0.45 - k * 0.12, s * (dw + 0.2), dz + 0.375 + k * 0.02), (dx - 0.48 - k * 0.12, s * (dw + 0.2), dz + 0.38 + k * 0.02), 0.22, 10, 'steel')
    with F.group('Drum'):   # its own part so the game can spin it while mining
        cyl((dx, -dw, dz), (dx, dw, dz), 0.46, 16, 'dark')
        n = 44
        for j in range(n):
            y = -dw + 0.12 + (2 * dw - 0.24) * j / (n - 1)
            for start in (0, 180):
                a = start + j * 16.4 * (1 if y < 0 else -1) + (0 if y < 0 else 40)
                hb = box((0, y, 0.5), (0.11, 0.07, 0.07), 'plate')
                hb['uv'] = 0.4
                F.rot(hb, 'Y', a)
                F.move(hb, (dx, 0, dz))
                if j % 2 == start // 180:
                    pk = tube((0.03, y, 0.52), (0.14, y, 0.8), [(0, 0.07), (0.45, 0.055), (1, 0.01)], 6, 'steel')
                    pk['uv'] = 0.4
                    F.rot(pk, 'Y', a)
                    F.move(pk, (dx, 0, dz))
    box((dx - 0.5, 0, dz + 0.72), (0.2, dw + 0.1, 0.045), 'hazard', bevel=0.02)
    for s in (1, -1):
        box((dx - 0.6, s * (dw + 0.2), dz + 0.5), (0.06, 0.08, 0.22), 'plate')
    # Chain conveyor from the drum up into the hopper, beside the cab.
    cy = -0.42
    loft([[(3.75, cy - 0.4, 0.8), (3.75, cy + 0.4, 0.8), (0.75, cy + 0.4, z1 + 0.12), (0.75, cy - 0.4, z1 + 0.12)],
          [(3.75, cy - 0.4, 0.9), (3.75, cy + 0.4, 0.9), (0.75, cy + 0.4, z1 + 0.22), (0.75, cy - 0.4, z1 + 0.22)]], 'black', bevel=0.02)
    for s in (1, -1):
        loft([[(3.75, cy + s * 0.4 - 0.04, 0.86), (3.75, cy + s * 0.4 + 0.04, 0.86), (0.75, cy + s * 0.4 + 0.04, z1 + 0.18), (0.75, cy + s * 0.4 - 0.04, z1 + 0.18)],
              [(3.75, cy + s * 0.4 - 0.04, 1.08), (3.75, cy + s * 0.4 + 0.04, 1.08), (0.75, cy + s * 0.4 + 0.04, z1 + 0.4), (0.75, cy + s * 0.4 - 0.04, z1 + 0.4)]], 'plate', bevel=0.015)
    for k in range(9):
        t = (k + 0.5) / 9
        box((3.75 - 3.0 * t, cy, 0.93 + (z1 + 0.25 - 0.93) * t), (0.03, 0.36, 0.035), 'steel')
    return dict(pivot=[('Drum', (dx, 0, dz), 'DrumPivot')])


@asset('human/hauler.glb', 'Terran Hauler (cargo tug)')
def hauler():
    L, hw, top = 6.8, 1.22, 1.2
    V.scifi_chassis(L, hw, top, nose=0.9)
    cab(2.25, 0.0, top + 0.02, 0.85, 1.0, 0.85)
    # Deep cargo bed: thick ribbed walls with a flared lip, tie-down rings, hinged tailgate with latch rams.
    x0, x1, wy, z0 = -3.5, 1.2, 1.7, top + 0.12
    bh = 0.42
    box(((x0 + x1) / 2, 0, z0 - 0.05), ((x1 - x0) / 2, wy, 0.07), 'armor', bevel=0.03)
    box(((x0 + x1) / 2, 0, z0 + 0.03), ((x1 - x0) / 2 - 0.1, wy - 0.12, 0.012), 'steel')
    for s in (1, -1):
        box(((x0 + x1) / 2, s * (wy - 0.06), z0 + bh), ((x1 - x0) / 2, 0.09, bh), 'armor', bevel=0.02)
        loft([[(x0, s * (wy - 0.15), z0 + 2 * bh), (x1, s * (wy - 0.15), z0 + 2 * bh), (x1, s * (wy + 0.2), z0 + 2 * bh + 0.2), (x0, s * (wy + 0.2), z0 + 2 * bh + 0.2)],
              [(x0, s * (wy - 0.05), z0 + 2 * bh - 0.04), (x1, s * (wy - 0.05), z0 + 2 * bh - 0.04), (x1, s * (wy + 0.26), z0 + 2 * bh + 0.14), (x0, s * (wy + 0.26), z0 + 2 * bh + 0.14)]], 'hazard', bevel=0.012)
        for k in range(9):
            x = x0 + 0.2 + k * (x1 - x0 - 0.4) / 8
            box((x, s * (wy + 0.05), z0 + bh), (0.05, 0.035, bh), 'plate', bevel=0.015)
            if k % 2:
                tube((x + 0.25, s * (wy + 0.06), z0 + 0.2), (x + 0.25, s * (wy + 0.1), z0 + 0.2), [(0, 0.07), (1, 0.07), (1, 0.04), (0, 0.04)], 8, 'steel')
        box((x0 - 0.02, s * 1.2, z0 + 0.15), (0.02, 0.16, 0.05), 'red')
        K.ram((x0 + 0.6, s * (wy + 0.14), z0 + 0.3), (x0 - 0.1, s * (wy + 0.14), z0 + 0.62), 0.05)
    box((x0 + 0.04, 0, z0 + bh), (0.06, wy - 0.1, bh), 'plate', bevel=0.02)
    box((x0 - 0.03, 0, z0 + bh), (0.012, wy * 0.6, 0.06), 'hazard')
    box((x1 - 0.04, 0, z0 + 0.62), (0.07, wy - 0.05, 0.62), 'armor', bevel=0.02)
    box((x1 - 0.12, 0, z0 + 0.75), (0.012, wy * 0.6, 0.22), 'vent')
    with F.group('Ore'):   # the cargo; the game can hide it when the bed is empty
        K.ore_load(x0 + 0.35, x1 - 0.8, wy - 0.3, z0 + 0.12, 2 * bh + 0.5, seed=11)
    # Knuckle-boom loading crane with a four-tine grapple.
    cx, cy = x1 - 0.35, -1.25
    with F.group('Crane'):   # swings over the bed while loading
        tube((cx, cy, z0), (cx, cy, z0 + 0.2), [(0, 0.45), (0.7, 0.45), (1, 0.36)], 16, 'steel', sharp=40)
        for k in range(16):
            a = 2 * math.pi * k / 16
            box((cx + math.cos(a) * 0.46, cy + math.sin(a) * 0.46, z0 + 0.07), (0.03, 0.03, 0.05), 'dark')
        box((cx, cy, z0 + 0.85), (0.16, 0.16, 0.68), 'plate', bevel=0.03)
        cyl((cx + 0.18, cy - 0.2, z0 + 0.55), (cx + 0.18, cy + 0.2, z0 + 0.55), 0.14, 10, 'steel')    # cable drum
        jz = z0 + 1.5
        cyl((cx, cy - 0.2, jz), (cx, cy + 0.2, jz), 0.17, 10, 'dark')
        m = F.mark()
        box((cx - 1.0, cy, jz), (1.05, 0.12, 0.13), 'plate', bevel=0.03)
        box((cx - 1.0, cy, jz + 0.135), (0.5, 0.1, 0.008), 'hazard')
        F.rot_all(m, 'Y', 24, about=(cx, 0, jz))
        K.ram((cx - 0.12, cy, z0 + 0.7), (cx - 1.0, cy, jz + 0.26), 0.07)
        ex, ez = cx - 2.0 * math.cos(math.radians(24)), jz + 2.0 * math.sin(math.radians(24))
        cyl((ex, cy - 0.18, ez), (ex, cy + 0.18, ez), 0.15, 10, 'steel')
        m = F.mark()
        box((ex - 0.75, cy, ez), (0.8, 0.09, 0.1), 'plate', bevel=0.025)
        K.ram((ex + 0.5, cy, ez + 0.2), (ex - 0.6, cy, ez + 0.14), 0.05)
        F.rot_all(m, 'Y', -30, about=(ex, 0, ez))
        hx, hz = ex - 1.5 * math.cos(math.radians(30)), ez - 1.5 * math.sin(math.radians(30))
        cyl((hx, cy - 0.12, hz), (hx, cy + 0.12, hz), 0.1, 8, 'steel')                                  # pulley head
        cyl((hx, cy, hz), (hx, cy, hz - 0.4), 0.022, 6, 'steel')
        box((hx, cy, hz - 0.46), (0.13, 0.13, 0.09), 'dark', bevel=0.03)
        for k in range(4):   # grapple tines
            t = prism([(0.1, 0.0), (0.42, -0.12), (0.5, -0.42), (0.3, -0.72), (0.26, -0.68), (0.4, -0.42), (0.34, -0.2), (0.1, -0.1)], -0.04, 0.04, 'steel', bevel=0.012)
            F.rot(t, 'Z', 90 * k + 45)
            F.move(t, (hx, cy, hz - 0.5))
    return dict(pivot=[('Crane', (cx, cy, z0), 'CranePivot')])


@asset('human/mender.glb', 'Terran Mender (repair vehicle)')
def mender():
    L, hw, top = 6.4, 1.22, 1.42
    V.scifi_chassis(L, hw, top, claws=(-1.7, 0.7))
    cab(1.7, 0.0, top + 0.02, 0.7, 0.8, 0.6)
    # Workshop body: chamfered roof, roll-up locker shutters, grab rails, spares rack, gas cylinders.
    hull([(-2.95, [(0, top + 0.02), (1.15, top + 0.02), (1.15, top + 0.62), (0.95, top + 0.8), (0, top + 0.8)]),
          (-0.25, [(0, top + 0.02), (1.15, top + 0.02), (1.15, top + 0.62), (0.95, top + 0.8), (0, top + 0.8)])], 'armor', bevel=0.03)
    for s in (1, -1):
        for k in range(3):
            box((-2.5 + k * 0.9, s * 1.16, top + 0.34), (0.38, 0.012, 0.25), 'vent', bevel=0.01)
            box((-2.5 + k * 0.9, s * 1.165, top + 0.34), (0.4, 0.01, 0.27), 'armor')
            box((-2.5 + k * 0.9, s * 1.18, top + 0.12), (0.1, 0.012, 0.02), 'steel')
        box((-1.6, s * 1.1, top + 0.74), (1.2, 0.012, 0.012), 'steel')
        for k in range(3):
            c = (-2.62 + k * 0.4, s * 0.72)
            cyl((c[0], c[1], top + 0.82), (c[0], c[1], top + 1.25), 0.15, 10, 'plate')
            cyl((c[0], c[1], top + 1.05), (c[0], c[1], top + 1.1), 0.155, 10, 'neon')
            tube((c[0], c[1], top + 1.25), (c[0], c[1], top + 1.36), [(0, 0.15), (0.5, 0.08), (1, 0.05)], 8, 'steel')
        box((-2.22, s * 0.72, top + 0.95), (0.66, 0.19, 0.02), 'dark')
    K.plus(-0.72, 0, top + 0.815, 0.3)
    # Rear rack with spare armour plates.
    for k in range(3):
        p = box((-3.06 - k * 0.07, 0, top + 0.45), (0.025, 0.7 - k * 0.1, 0.32), 'plate' if k != 1 else 'armor', bevel=0.012)
        F.rot(p, 'Y', -8, about=(-3.0, 0, top + 0.15))
    box((-3.15, 0, top + 0.12), (0.2, 0.8, 0.03), 'steel')
    # Folded auxiliary jib and a cable drum on the roof.
    box((-1.0, 0.82, top + 0.9), (0.9, 0.07, 0.08), 'plate', bevel=0.02)
    cyl((-1.9, 0.82, top + 0.82), (-1.9, 0.82, top + 1.0), 0.12, 8, 'steel')
    cyl((-0.15, 0.82, top + 0.9), (-0.15, 0.82, top + 0.7), 0.02, 6, 'steel')
    cyl((-0.75, -1.0, top + 0.98), (-0.75, -0.55, top + 0.98), 0.17, 10, 'black')
    for yy in (-1.0, -0.55):
        cyl((-0.75, yy - 0.02, top + 0.98), (-0.75, yy + 0.02, top + 0.98), 0.22, 10, 'steel')
    tz = top + 0.82
    az = tz + 0.62
    with F.group('Arm'):
        tube((-1.7, 0, tz), (-1.7, 0, tz + 0.26), [(0, 0.58), (0.6, 0.58), (1, 0.42)], 16, 'steel', sharp=40)
        for k in range(18):
            a = 2 * math.pi * k / 18
            box((-1.7 + math.cos(a) * 0.59, math.sin(a) * 0.59, tz + 0.08), (0.03, 0.03, 0.06), 'dark')
        box((-1.7, 0, tz + 0.55), (0.3, 0.36, 0.32), 'armor', bevel=0.05)
        box((-2.25, 0, tz + 0.5), (0.25, 0.4, 0.25), 'plate', bevel=0.04)       # counterweight
        box((-2.51, 0, tz + 0.5), (0.012, 0.3, 0.12), 'hazard')
        m = F.mark()
        for s in (1, -1):   # twin-rail upper boom with cross braces
            box((-0.1, s * 0.2, az), (1.65, 0.05, 0.13), 'plate', bevel=0.02)
        for k in range(7):
            box((-1.3 + k * 0.42, 0, az), (0.03, 0.2, 0.09), 'steel')
        box((-0.1, 0, az + 0.14), (1.2, 0.03, 0.008), 'hazard')
        K.ram((-1.45, 0, az - 0.3), (0.3, 0, az - 0.16), 0.085)
        sweep([(-1.6, -0.3, az + 0.1), (-0.5, -0.3, az + 0.2), (1.2, -0.28, az + 0.05)], [(0.04, 0.04)] * 3, 'black', sides=6)   # hoses
        sweep([(-1.6, -0.36, az + 0.02), (-0.5, -0.38, az + 0.12), (1.2, -0.34, az - 0.03)], [(0.03, 0.03)] * 3, 'neon', sides=5)
        F.rot_all(m, 'Y', -32, about=(-1.7, 0, az))
        ex, ez = -1.7 + 3.2 * math.cos(math.radians(32)), az + 3.2 * math.sin(math.radians(32))
        cyl((ex, -0.3, ez), (ex, 0.3, ez), 0.27, 12, 'dark')
        for s in (1, -1):
            cyl((ex, s * 0.3, ez), (ex, s * 0.34, ez), 0.2, 10, 'steel')
        m = F.mark()
        box((ex + 1.0, 0, ez), (1.0, 0.14, 0.15), 'plate', bevel=0.03)
        K.ram((ex - 0.2, 0, ez + 0.32), (ex + 1.2, 0, ez + 0.2), 0.06)
        # Tool head: three hydraulic fingers round a welding emitter.
        tx = ex + 2.1
        box((tx, 0, ez), (0.24, 0.26, 0.26), 'dark', bevel=0.05)
        cyl((tx + 0.2, 0, ez), (tx + 0.3, 0, ez), 0.3, 10, 'steel')
        tube((tx + 0.3, 0, ez), (tx + 0.62, 0, ez), [(0, 0.13), (0.6, 0.1), (1, 0.07)], 8, 'dark')
        cyl((tx + 0.62, 0, ez), (tx + 0.64, 0, ez), 0.075, 8, 'amber')
        cyl((tx + 0.63, 0, ez), (tx + 0.66, 0, ez), 0.045, 8, 'neon')
        for k in range(3):
            fg = prism([(tx + 0.25, ez + 0.2), (tx + 0.65, ez + 0.46), (tx + 1.0, ez + 0.3), (tx + 1.08, ez + 0.1), (tx + 0.98, ez + 0.12),
                        (tx + 0.9, ez + 0.24), (tx + 0.66, ez + 0.32), (tx + 0.3, ez + 0.1)], -0.06, 0.06, 'steel', bevel=0.012)
            F.rot(fg, 'X', 120 * k + 90, about=(0, 0, ez))
        with F.group('Spark'):   # welding arc, flickers while repairing
            for k in range(3):
                b = box((tx + 0.8, 0, ez), (0.16, 0.012, 0.012), 'neon')
                F.rot(b, 'Y', 60 * k - 60, about=(tx + 0.72, 0, ez))
            orb((tx + 0.72, 0, ez), 0.06, 'neon', seg=(6, 4))
        F.rot_all(m, 'Y', 38, about=(ex, 0, ez))
    return dict(pivot=[('Arm', (-1.7, 0, tz)), ('Spark', (-1.7, 0, tz), 'SparkPivot', 'Arm')])


@asset('human/watchman.glb', 'Terran Watchman (mobile radar)')
def watchman():
    L, hw, top = 6.4, 1.22, 1.42
    V.scifi_chassis(L, hw, top, claws=(-1.7, 0.7))
    cab(1.8, 0.0, top + 0.02, 0.65, 0.8, 0.5)
    box((-1.4, 0, top + 0.3), (1.5, 1.1, 0.3), 'armor', bevel=0.05)
    # Generator housing at the rear with vents, conduits to the turntable, lattice beacon mast.
    box((-2.5, 0, top + 0.72), (0.38, 0.8, 0.14), 'plate', bevel=0.04)
    for s in (1, -1):
        K.vent((-2.5, s * 0.45, top + 0.88), (0.3, 0.26, 0.035))
        box((-1.4, s * 1.11, top + 0.32), (0.8, 0.012, 0.02), 'neon')
        sweep([(-2.3, s * 0.7, top + 0.66), (-1.9, s * 0.95, top + 0.66), (-1.3, s * 0.9, top + 0.66)], [(0.05, 0.05)] * 3, 'black', sides=6)
    box((0.1, 0.72, top + 0.72), (0.3, 0.25, 0.12), 'armor', bevel=0.03)
    for dx, dy in ((0, 0), (0.3, 0), (0, 0.3), (0.3, 0.3)):
        cyl((0.0 + dx, -0.95 + dy, top + 0.6), (0.06 + dx * 0.6, -0.89 + dy * 0.6, top + 1.7), 0.02, 4, 'steel')
    box((0.15, -0.8, top + 1.15), (0.14, 0.14, 0.012), 'steel')
    with F.group('Radar'):   # small spinning bar antenna on the generator
        K.radar_bar(-2.5, 0, top + 0.92, w=0.6, post=0.3)
    tz = top + 0.62
    with F.group('Dish'):
        # Turntable with a hazard rim, twin-arm yoke, trunnion drum and elevation rams.
        tube((-1.2, 0, tz), (-1.2, 0, tz + 0.22), [(0, 1.0), (0.6, 1.0), (1, 0.86)], 24, 'steel', sharp=40)
        tube((-1.2, 0, tz + 0.02), (-1.2, 0, tz + 0.1), [(0, 1.02), (1, 1.02), (1, 0.98), (0, 0.98)], 24, 'hazard')
        for s in (1, -1):
            prism([(-1.75, tz + 0.2), (-0.65, tz + 0.2), (-0.92, tz + 2.05), (-1.48, tz + 2.05)], min(s * 0.42, s * 0.6), max(s * 0.42, s * 0.6), 'plate', bevel=0.03)
            cyl((-1.2, s * 0.6, tz + 1.8), (-1.2, s * 0.68, tz + 1.8), 0.22, 10, 'steel')
            K.ram((-1.85, s * 0.3, tz + 0.3), (-1.75, s * 0.3, tz + 1.55), 0.07)
        cyl((-1.2, -0.44, tz + 1.8), (-1.2, 0.44, tz + 1.8), 0.3, 12, 'dark')
        m = F.mark()
        c = (-1.2, 0, tz + 1.8)
        prof = [(0.12, 0.0), (0.9, 0.1), (1.6, 0.36), (2.15, 0.8), (2.2, 0.8), (1.62, 0.3), (0.9, 0.02), (0.12, -0.1)]
        F.lathe(prof, 32, 'armor', center=c, sharp=40)
        F.lathe([(2.13, 0.76), (2.3, 0.8), (2.26, 0.92), (2.12, 0.86)], 32, 'dark', center=c)       # rolled lip
        F.lathe([(2.0, 0.69), (2.08, 0.75), (2.06, 0.77), (1.99, 0.72)], 32, 'neon', center=c)
        F.lathe([(1.1, 0.02), (1.24, 0.06), (1.22, -0.08), (1.1, -0.1)], 24, 'steel', center=c)     # back stiffener ring
        for k in range(8):   # truss ribs on the back
            r = F.loft([[(0.3, -0.035, -0.12), (0.3, 0.035, -0.12), (2.05, 0.035, 0.66), (2.05, -0.035, 0.66)],
                        [(0.3, -0.035, -0.38), (0.3, 0.035, -0.38), (2.05, 0.035, 0.58), (2.05, -0.035, 0.58)]], 'plate')
            F.rot(r, 'Z', 45 * k + 22.5)
            F.move(r, c)
        cyl((c[0], c[1], c[2] - 0.5), (c[0], c[1], c[2] - 0.05), 0.34, 12, 'plate')
        box((c[0], c[1], c[2] - 0.66), (0.3, 0.42, 0.16), 'dark', bevel=0.04)                     # counterweight
        for k in range(4):   # quad strut to the feed horn
            st = cyl((1.5, 0, 0.36), (0.12, 0, 1.42), 0.045, 6, 'steel')
            F.rot(st, 'Z', 90 * k + 45)
            F.move(st, c)
        box((c[0], c[1], c[2] + 1.48), (0.15, 0.15, 0.16), 'plate', bevel=0.03)
        cyl((c[0], c[1], c[2] + 1.28), (c[0], c[1], c[2] + 1.33), 0.24, 12, 'dark')
        cyl((c[0], c[1], c[2] + 1.26), (c[0], c[1], c[2] + 1.28), 0.1, 10, 'neon')
        F.rot_all(m, 'Y', 62, about=c)
    return dict(pivot=[('Dish', (-1.2, 0, tz)), ('Radar', (-2.5, 0, top + 1.2), 'RadarPivot')])


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
