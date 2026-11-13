"""Terran structures, art pass v2. Centre at the origin, ground at z = 0, weapons face +X."""
import math

import forge as F
from forge import box, cyl, hull, loft, plate, prism, tube, orb, lathe
import terran_kit as K
from terran_units import turret_shell

ASSETS = {}


def asset(path, label, size=1024):
    def deco(fn):
        def run(glb, render, report):
            F.begin('terran')
            kw = fn() or {}
            F.finish(kw.pop('name'), glb, render=render, report=report, label=label, size=kw.pop('size', size), **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='structures')
        run.build = fn
        return run
    return deco


def octo(h, c=0.28):
    k = h * (1 - c)
    return [(h, -k), (h, k), (k, h), (-k, h), (-h, k), (-h, -k), (-k, -h), (k, -h)]


def foundation(h, z=0.3, lights=True):
    """Chamfered armoured footing with a recessed deck, hazard corners and marker lights."""
    plate(octo(h), 0.0, z * 0.55, 'concrete', inset=0.0, bevel=0.03)
    plate(octo(h * 0.94), z * 0.55, z, 'armor', inset=0.04, bevel=0.03)
    plate(octo(h * 0.8), z, z + 0.03, 'deck')
    for sx in (1, -1):
        for sy in (1, -1):
            b = box((0, 0, z * 0.78), (h * 0.2, 0.03, z * 0.2), 'hazard')
            F.rot(b, 'Z', -45 * sx * sy)
            F.move(b, (sx * h * 0.865, sy * h * 0.865, 0))
            if lights:
                K.beacon(sx * h * 0.72, sy * h * 0.72, z, 'amber' if sx > 0 else 'glow')
    for a in range(4):
        b = box((h * 0.965, 0, z * 0.78), (0.012, h * 0.45, 0.025), 'glow')
        F.rot(b, 'Z', 90 * a)
    return z


@asset('structures/terran_turret.glb', 'Terran Bastion Gun (turret)', size=512)
def terran_turret():
    z = foundation(2.0, 0.34)
    tube((0, 0, z), (0, 0, z + 0.7), [(0, 1.35), (0.25, 1.35), (0.45, 1.05), (1, 0.98)], 8, 'armor', sharp=30, bevel=0.03)
    for a in range(4):
        b = prism([(0.9, z), (1.75, z), (1.1, z + 0.6)], -0.1, 0.1, 'plate', bevel=0.025)
        F.rot(b, 'Z', 45 + 90 * a)
        v = box((1.2, 0, z + 0.45), (0.012, 0.3, 0.12), 'vent')
        F.rot(v, 'Z', 90 * a + 90)
    tz = z + 0.7
    with F.group('Turret'):
        tube((0, 0, tz - 0.03), (0, 0, tz + 0.1), [(0, 1.0), (1, 0.95)], 20, 'dark')
        turret_shell(-1.35, 1.05, 1.05, tz, 0.86)
        plate([(-0.9, -0.6), (0.3, -0.55), (0.55, 0), (0.3, 0.55), (-0.9, 0.6)], tz + 0.85, tz + 0.92, 'plate', inset=0.05, bevel=0.02)
        box((1.12, 0, tz + 0.4), (0.2, 0.72, 0.26), 'dark', bevel=0.05)
        for s in (1, -1):
            K.railgun(1.1, 4.3, s * 0.4, tz + 0.4, 0.13)
            # Ammunition drums on the flanks.
            cyl((-0.5, s * 1.0, tz + 0.42), (-0.5, s * 1.32, tz + 0.42), 0.36, 12, 'plate')
            cyl((-0.5, s * 1.32, tz + 0.42), (-0.5, s * 1.35, tz + 0.42), 0.16, 8, 'amber')
            box((-0.2, s * 1.07, tz + 0.75), (0.5, 0.012, 0.02), 'glow')
        box((-0.3, 0.45, tz + 1.0), (0.2, 0.16, 0.1), 'dark', bevel=0.03)
        box((-0.1, 0.45, tz + 1.01), (0.012, 0.1, 0.06), 'glass')
        K.antenna(-1.0, -0.5, tz + 0.75, 1.0)
    return dict(name='TerranTurret', pivot=('Turret', (0, 0, tz)))


@asset('structures/terran_missile_battery.glb', 'Terran Spire Missile Battery', size=512)
def terran_missile_battery():
    z = foundation(2.0, 0.34)
    tube((0, 0, z), (0, 0, z + 0.9), [(0, 1.2), (0.3, 1.2), (0.5, 0.8), (1, 0.72)], 8, 'armor', sharp=30, bevel=0.03)
    for a in range(4):
        b = prism([(0.7, z), (1.7, z), (0.85, z + 0.75)], -0.1, 0.1, 'plate', bevel=0.025)
        F.rot(b, 'Z', 45 + 90 * a)
    tz = z + 0.9
    with F.group('Turret'):
        tube((0, 0, tz - 0.03), (0, 0, tz + 0.12), [(0, 0.82), (1, 0.75)], 16, 'dark')
        box((-0.1, 0, tz + 0.6), (0.5, 0.42, 0.5), 'armor', bevel=0.06)
        cyl((0, -1.1, tz + 0.75), (0, 1.1, tz + 0.75), 0.15, 10, 'dark')
        for s in (1, -1):
            m = F.mark()
            K.missile_box((0.2, s * 1.05, tz + 0.75), (1.35, 0.52, 0.52), nx=2, nz=2)
            box((0.2, s * 1.585, tz + 0.75), (1.0, 0.012, 0.02), 'glow')
            box((1.0, s * 1.05, tz + 1.29), (0.3, 0.35, 0.012), 'hazard')
            F.rot_all(m, 'Y', -38, about=(0, 0, tz + 0.75))
        box((0.25, 0, tz + 1.2), (0.22, 0.2, 0.12), 'dark', bevel=0.04)
        box((0.48, 0, tz + 1.2), (0.012, 0.14, 0.07), 'glass')
        tube((-0.5, 0, tz + 1.1), (-0.5, 0, tz + 1.5), [(0, 0.05), (0.7, 0.05), (0.7, 0.3), (1, 0.22)], 10, 'plate')
        K.beacon(-0.5, 0, tz + 1.5, 'red')
    return dict(name='TerranMissileBattery', pivot=('Turret', (0, 0, tz)))


@asset('structures/terran_radar.glb', 'Terran Radar Tower', size=512)
def terran_radar():
    z = foundation(2.0, 0.34)
    # Equipment hut and a braced four-leg tower.
    box((0, 0, z + 0.45), (1.0, 1.0, 0.45), 'armor', bevel=0.06)
    for a in range(4):
        v = box((1.01, 0, z + 0.5), (0.012, 0.45, 0.18), 'vent')
        F.rot(v, 'Z', 90 * a)
    top = z + 4.6
    for sx in (1, -1):
        for sy in (1, -1):
            sweep_leg = F.sweep([(sx * 1.25, sy * 1.25, z + 0.1), (sx * 0.6, sy * 0.6, z + 2.6), (sx * 0.42, sy * 0.42, top)],
                                [(0.1, 0.1), (0.08, 0.08), (0.07, 0.07)], 'plate', sides=4)
    for h, r in ((z + 1.5, 0.92), (z + 2.6, 0.62), (z + 3.6, 0.5)):
        for a in range(4):
            b = box((r, 0, h), (0.04, r, 0.04), 'dark')
            F.rot(b, 'Z', 90 * a)
    for a in range(4):
        b = F.sweep([(0.92, -0.92, z + 1.5), (0.62, 0.62, z + 2.6)], [(0.035, 0.035)] * 2, 'dark', sides=4)
        F.rot(b, 'Z', 90 * a)
    plate(octo(0.75), top, top + 0.16, 'armor', bevel=0.03)
    box((0, 0, top + 0.02), (0.78, 0.78, 0.015), 'glow')
    cyl((0, 0, z + 0.9), (0, 0, top), 0.12, 8, 'dark')
    tz = top + 0.16
    with F.group('Dish'):
        tube((0, 0, tz), (0, 0, tz + 0.4), [(0, 0.45), (0.4, 0.45), (0.6, 0.22), (1, 0.2)], 12, 'dark')
        for s in (1, -1):
            prism([(-0.3, tz + 0.3), (0.3, tz + 0.3), (0.18, tz + 1.3), (-0.18, tz + 1.3)], min(s * 0.24, s * 0.34), max(s * 0.24, s * 0.34), 'plate', bevel=0.025)
        m = F.mark()
        c = (0, 0, tz + 1.15)
        prof = [(0.1, 0.0), (0.7, 0.08), (1.25, 0.28), (1.7, 0.64), (1.76, 0.64), (1.27, 0.22), (0.7, 0.0), (0.1, -0.08)]
        lathe(prof, 18, 'armor', center=c, sharp=40)
        lathe([(1.7, 0.62), (1.79, 0.64), (1.74, 0.7)], 18, 'glow', center=c)
        for k in range(6):
            r = loft([[(0.25, -0.025, -0.1), (0.25, 0.025, -0.1), (1.6, 0.025, 0.5), (1.6, -0.025, 0.5)],
                      [(0.25, -0.025, -0.25), (0.25, 0.025, -0.25), (1.6, 0.025, 0.44), (1.6, -0.025, 0.44)]], 'plate')
            F.rot(r, 'Z', 60 * k)
            F.move(r, c)
        cyl(c, (c[0], c[1], c[2] + 1.05), 0.035, 6, 'dark')
        orb((c[0], c[1], c[2] + 1.1), 0.13, 'glow')
        F.rot_all(m, 'Y', 66, about=c)
        box((-0.5, 0, tz + 1.15), (0.25, 0.22, 0.22), 'dark', bevel=0.04)
    return dict(name='TerranRadar', pivot=('Dish', (0, 0, tz)))


def tank(x, y, z, r, h, zone='plate'):
    tube((x, y, z), (x, y, z + h), [(0, r), (0.85, r), (0.93, r * 0.9), (1, r * 0.55)], 14, zone)
    for k in (0.3, 0.65):
        tube((x, y, z + h * k), (x, y, z + h * k + 0.06), [(0, r * 1.04), (1, r * 1.04)], 14, 'dark')
    box((x, y, z + h * 0.45), (r * 1.02, 0.03, 0.09), 'hazard')


def pipe(points, r=0.09, zone='barrel'):
    F.sweep(points, [(r, r)] * len(points), zone, sides=8)


@asset('structures/terran_lab.glb', 'Terran Research Lab')
def terran_lab():
    z = foundation(4.0, 0.32)
    # Main hall: octagonal drum with buttresses and a glowing glass dome.
    tube((0, 0, z), (0, 0, z + 1.9), [(0, 2.5), (0.75, 2.5), (1, 2.15)], 8, 'armor', sharp=30, bevel=0.05)
    for a in range(8):
        b = prism([(2.2, z), (3.2, z), (2.4, z + 1.7), (2.2, z + 1.7)], -0.16, 0.16, 'plate', bevel=0.03)
        F.rot(b, 'Z', 45 * a + 22.5)
        g = box((2.42, 0, z + 0.95), (0.012, 0.5, 0.3), 'glass')
        F.rot(g, 'Z', 45 * a)
        g2 = box((2.52, 0, z + 0.55), (0.012, 0.62, 0.02), 'glow')
        F.rot(g2, 'Z', 45 * a)
    tube((0, 0, z + 1.9), (0, 0, z + 2.2), [(0, 2.0), (1, 1.7)], 16, 'plate', sharp=30)
    lathe([(1.6, 0.0), (1.5, 0.55), (1.15, 1.0), (0.6, 1.3), (0.02, 1.4)], 16, 'glass', center=(0, 0, z + 2.2))
    for k in range(8):
        rib = F.crescent((0, 0, z + 2.2), 1.62, 0, 88, 0.09, 0.05, 'plate', n=8, plane='xz', sq=(1, 0.88), tip=0.8)
        F.rot(rib, 'Z', 45 * k)
    orb((0, 0, z + 2.75), 0.5, 'glow', seg=(12, 8))
    cyl((0, 0, z + 3.6), (0, 0, z + 4.3), 0.04, 6, 'dark')
    K.beacon(0, 0, z + 4.3, 'glow')
    # Annex modules, entrance, pipes and coolant tanks.
    box((2.9, 0, z + 0.55), (0.75, 0.8, 0.55), 'armor', bevel=0.06)
    box((3.66, 0, z + 0.45), (0.012, 0.45, 0.4), 'dark')
    box((3.67, 0, z + 0.92), (0.012, 0.5, 0.03), 'glow')
    prism([(3.6, z), (3.95, z), (3.6, z + 0.12)], -0.6, 0.6, 'deck')
    box((-2.6, -2.0, z + 0.6), (0.9, 0.7, 0.6), 'armor', bevel=0.06)
    K.vent((-2.6, -2.0, z + 1.22), (0.6, 0.45, 0.04))
    tank(-2.7, 2.2, z, 0.62, 1.7)
    tank(-1.5, 2.9, z, 0.5, 1.3)
    pipe([(-2.7, 2.2, z + 1.72), (-2.7, 2.2, z + 2.1), (-1.6, 1.3, z + 2.1), (-1.6, 1.3, z + 1.6)])
    pipe([(-1.5, 2.9, z + 1.32), (-1.5, 2.9, z + 1.6), (-0.9, 2.3, z + 1.6)], 0.07)
    # Dish and mast cluster.
    cyl((2.3, -2.5, z), (2.3, -2.5, z + 2.4), 0.07, 6, 'dark')
    m = F.mark()
    lathe([(0.06, 0), (0.45, 0.06), (0.8, 0.25), (0.84, 0.25), (0.46, 0.0), (0.06, -0.05)], 12, 'plate', center=(2.3, -2.5, z + 2.5))
    F.rot_all(m, 'Y', 50, about=(2.3, -2.5, z + 2.5))
    K.antenna(1.6, -3.0, z, 3.0)
    return dict(name='TerranLab')


@asset('structures/terran_metal_station.glb', 'Terran Metal Station (refinery)')
def terran_metal_station():
    z = foundation(4.0, 0.32)
    # Receiving hopper on the -Y side (where haulers tip), smelter block, stack, storage tanks.
    x0, x1, y0, y1, zt = -1.6, 1.6, -3.3, -1.3, z + 1.5
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        cx, cy = (ax + bx) / 2, (ay + by) / 2
        ox, oy = cx * 0.22, (cy - (y0 + y1) / 2) * 0.35
        loft([[(ax, ay, z), (bx, by, z), (bx + ox, by + oy, zt), (ax + ox, ay + oy, zt)],
              [(ax * 0.9, (ay - (y0 + y1) / 2) * 0.85 + (y0 + y1) / 2, z), (bx * 0.9, (by - (y0 + y1) / 2) * 0.85 + (y0 + y1) / 2, z),
               (bx * 0.94 + ox, (by - (y0 + y1) / 2) * 0.9 + (y0 + y1) / 2 + oy, zt), (ax * 0.94 + ox, (ay - (y0 + y1) / 2) * 0.9 + (y0 + y1) / 2 + oy, zt)]],
             'armor', bevel=0.02)
    box((0, (y0 + y1) / 2, zt + 0.02), (1.95, 1.32, 0.04), 'hazard', bevel=0.01)
    box((0, (y0 + y1) / 2, zt + 0.03), (1.75, 1.12, 0.06), 'dark')
    box((0, (y0 + y1) / 2, z + 0.5), (1.45, 0.85, 0.3), 'dark')
    # Smelter: heavy block with glowing furnace slots.
    box((-0.6, 1.0, z + 1.1), (1.9, 1.5, 1.1), 'armor', bevel=0.08)
    for k in range(4):
        box((-1.9 + k * 0.85, -0.52, z + 0.75), (0.26, 0.012, 0.4), 'amber')
        box((-1.9 + k * 0.85, -0.53, z + 0.75), (0.3, 0.02, 0.05), 'dark')
    box((-0.6, 1.0, z + 2.25), (1.5, 1.1, 0.08), 'plate', bevel=0.03)
    K.vent((-1.2, 1.0, z + 2.36), (0.5, 0.8, 0.05))
    # Chimney stack with a hot throat.
    tube((0.6, 1.3, z + 2.2), (0.6, 1.3, z + 4.4), [(0, 0.55), (0.1, 0.5), (0.8, 0.4), (0.86, 0.48), (1, 0.46)], 12, 'plate')
    cyl((0.6, 1.3, z + 4.36), (0.6, 1.3, z + 4.4), 0.36, 12, 'amber')
    for k in (0.35, 0.6):
        tube((0.6, 1.3, z + 2.2 + 2.2 * k), (0.6, 1.3, z + 2.28 + 2.2 * k), [(0, 0.5), (1, 0.5)], 12, 'hazard')
    # Conveyor from hopper to smelter.
    loft([[(0.9, -1.4, z + 1.2), (1.5, -1.4, z + 1.2), (1.5, 0.2, z + 2.1), (0.9, 0.2, z + 2.1)],
          [(0.9, -1.4, z + 1.4), (1.5, -1.4, z + 1.4), (1.5, 0.2, z + 2.3), (0.9, 0.2, z + 2.3)]], 'dark', bevel=0.02)
    tank(2.6, 1.6, z, 0.75, 2.2)
    tank(2.6, -0.1, z, 0.6, 1.6)
    pipe([(2.6, 1.6, z + 2.22), (2.6, 1.6, z + 2.6), (1.3, 1.3, z + 2.6)], 0.09)
    pipe([(2.6, -0.1, z + 1.62), (2.6, -0.1, z + 1.9), (2.6, 0.9, z + 1.9)], 0.07)
    # Ingot rack: finished metal stacked by the output door.
    for i in range(3):
        for j in range(2):
            box((-2.9, -0.2 + i * 0.5, z + 0.12 + j * 0.2), (0.4, 0.2, 0.08), 'barrel', bevel=0.03)
    box((-2.52, 1.0, z + 0.6), (0.012, 0.6, 0.5), 'dark')
    box((-2.53, 1.0, z + 1.15), (0.012, 0.65, 0.03), 'glow')
    K.antenna(-2.2, 2.3, z + 2.2, 1.6)
    return dict(name='TerranMetalStation')


@asset('structures/terran_air_base.glb', 'Terran Airfield')
def terran_air_base():
    z = foundation(6.0, 0.3, lights=False)
    # Flight deck with approach markings, hangar, control tower, fuel farm.
    plate([(-5.2, -1.2), (5.4, -1.2), (5.4, 4.6), (-5.2, 4.6)], z, z + 0.06, 'deck', bevel=0.02)
    for k in range(7):
        box((-4.2 + k * 1.5, 1.7, z + 0.07), (0.45, 0.07, 0.008), 'glow')
    for s in (-0.8, 4.2):
        for k in range(9):
            box((-4.6 + k * 1.2, s, z + 0.07), (0.1, 0.1, 0.012), 'amber' if k % 2 else 'glow')
    lathe([(1.5, 0), (1.62, 0), (1.62, 0.012), (1.5, 0.012)], 24, 'hazard', center=(3.0, 1.7, z + 0.065))
    box((3.0, 1.7, z + 0.07), (0.9, 0.09, 0.008), 'hazard')
    box((3.0, 1.7, z + 0.07), (0.09, 0.9, 0.008), 'hazard')
    # Hangar: faceted arch with ribbed roof and an open door showing a dark bay.
    rings = []
    for x in (-5.0, -1.2):
        rings.append([(x, -5.2, z), (x, -5.3, z + 1.3), (x, -4.6, z + 2.3), (x, -3.4, z + 2.75), (x, -2.2, z + 2.3), (x, -1.5, z + 1.3), (x, -1.6, z)])
    loft(rings, 'armor', bevel=0.05)
    for k in range(5):
        x = -4.7 + k * 0.82
        loft([[(x, -5.36, z), (x, -5.4, z + 1.32), (x, -4.64, z + 2.38), (x, -3.4, z + 2.86), (x, -2.16, z + 2.38), (x, -1.4, z + 1.32), (x, -1.44, z)],
              [(x + 0.14, -5.36, z), (x + 0.14, -5.4, z + 1.32), (x + 0.14, -4.64, z + 2.38), (x + 0.14, -3.4, z + 2.86), (x + 0.14, -2.16, z + 2.38), (x + 0.14, -1.4, z + 1.32), (x + 0.14, -1.44, z)]],
             'plate', caps=True)
    box((-1.19, -3.4, z + 1.0), (0.012, 1.5, 1.0), 'dark')
    box((-1.18, -3.4, z + 2.08), (0.012, 1.55, 0.04), 'glow')
    box((-1.18, -3.4, z + 0.05), (0.02, 1.6, 0.05), 'hazard')
    # Control tower.
    tube((3.8, -3.6, z), (3.8, -3.6, z + 3.4), [(0, 0.95), (0.2, 0.7), (0.9, 0.62), (1, 0.9)], 8, 'armor', sharp=30, bevel=0.03)
    tube((3.8, -3.6, z + 3.4), (3.8, -3.6, z + 4.2), [(0, 1.0), (0.2, 1.35), (0.75, 1.25), (1, 0.9)], 8, 'plate', sharp=30, bevel=0.03)
    tube((3.8, -3.6, z + 3.62), (3.8, -3.6, z + 3.98), [(0, 1.36), (1, 1.3)], 8, 'glass', sharp=30)
    cyl((3.8, -3.6, z + 4.2), (3.8, -3.6, z + 5.3), 0.05, 6, 'dark')
    K.beacon(3.8, -3.6, z + 5.3, 'red')
    m = F.mark()
    lathe([(0.05, 0), (0.35, 0.05), (0.6, 0.2), (0.64, 0.2), (0.36, 0.0), (0.05, -0.04)], 12, 'plate', center=(4.3, -3.1, z + 4.5))
    F.rot_all(m, 'Y', 55, about=(4.3, -3.1, z + 4.5))
    # Fuel farm and service gear.
    for k in range(3):
        m = F.mark()
        tube((0.5 + k * 0.0, -4.9 + k * 0.95, z + 0.5), (2.3, -4.9 + k * 0.95, z + 0.5), [(0, 0.3), (0.08, 0.42), (0.92, 0.42), (1, 0.3)], 12, 'plate')
        box((1.4, -4.9 + k * 0.95, z + 0.5), (0.06, 0.44, 0.44), 'hazard')
        box((1.4, -4.9 + k * 0.95, z + 0.1), (0.7, 0.3, 0.1), 'dark')
    pipe([(0.4, -4.9, z + 0.5), (0.0, -4.9, z + 0.5), (0.0, -2.0, z + 0.2), (1.0, -1.4, z + 0.12)], 0.07)
    for x, y in ((-5.3, 5.2), (5.3, 5.2), (5.3, -1.6)):
        cyl((x, y, z), (x, y, z + 2.6), 0.06, 6, 'dark')
        box((x, y - 0.15, z + 2.6), (0.22, 0.22, 0.05), 'plate', bevel=0.02)
        box((x, y - 0.15, z + 2.54), (0.16, 0.16, 0.012), 'glow')
    K.stow((-3.5, 5.0, z + 0.25), (0.6, 0.35, 0.25))
    K.stow((-2.2, 5.0, z + 0.2), (0.4, 0.3, 0.2))
    return dict(name='TerranAirBase')


@asset('structures/terran_landing_pad.glb', 'Terran Landing Pad')
def terran_landing_pad():
    import compat
    compat.install()
    import pads_hero
    pads_hero.terran_pad()
    return dict(name='TerranLandingPad', single=True)
