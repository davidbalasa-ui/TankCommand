"""Terran and Kesh structures, built on tools/art/kit.py with each faction's shared atlas.

Sized to the grid footprint (one cell is about 4 model units, the same scale as the units).
Rotating weapons and dishes sit under a TurretPivot empty, like the units.
Budgets: 1x1 and 2x2 structures <= 2,500 triangles, 3x3 structures <= 5,000.

Run with Blender's Python (pip bpy):
  python structures_set.py <atlas_dir> <out_dir> <name[,name...]|all|terran|kesh> [render_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cyl, lathe, loft, lens, orb, plate, prism  # noqa: E402
from kesh_set import arc_fin, petals, ring, barrel as kbarrel  # noqa: E402
from terran_set import antenna, barrel as tbarrel  # noqa: E402


def octagon(r, cx=0.0, cy=0.0, rot=math.pi / 8):
    return [(cx + r * math.cos(rot + k * math.pi / 4), cy + r * math.sin(rot + k * math.pi / 4)) for k in range(8)]


def foundation(name, half, h=0.4, tile='dark'):
    """Chamfered square slab every Terran structure sits on."""
    c = half * 0.82
    pts = [(-c, -half), (c, -half), (half, -c), (half, c), (c, half), (-c, half), (-half, c), (-half, -c)]
    return plate(name, pts, 0.0, h, tile, bevel=0.06)


# ---------------------------------------------------------------- Terran
def t_landing_pad():
    """12 x 12 pad. Landing circle in the middle, exit ramp on +X (the game turns +X toward the
    pad's exit edge), cargo lift and dock on -Y (left of the exit, where workers unload)."""
    H, R0 = 6.0, 2.6  # half size; ramp half width
    out = []
    # Foundation in three pieces so the ramp notch at +X is open to the ground.
    c = H * 0.84
    out.append(plate('Base', [(-c, -H), (3.6, -H), (3.6, H), (-c, H), (-H, c), (-H, -c)], 0.0, 0.5, 'dark', bevel=0.05))
    out.append(plate('BaseR', [(3.6, R0 + 0.3), (H, R0 + 0.3), (H, c), (c, H), (3.6, H)], 0.0, 0.5, 'dark', bevel=0.05))
    out.append(plate('BaseL', [(3.6, -H), (c, -H), (H, -c), (H, -R0 - 0.3), (3.6, -R0 - 0.3)], 0.0, 0.5, 'dark', bevel=0.05))
    # Exit ramp and its rails.
    out.append(prism('Ramp', [(3.4, 0.0), (H + 0.05, 0.0), (H + 0.05, 0.06), (3.4, 0.74)], -R0, R0, 'hull', bevel=0.03))
    for side in (-1, 1):
        y = side * (R0 + 0.15)
        out.append(prism(f'Rail{side}', [(3.4, 0.0), (H, 0.0), (H, 0.3), (3.4, 1.0)], y - 0.15, y + 0.15, 'turret', bevel=0.03))
        out.append(prism(f'RailGlow{side}', [(3.5, 0.98), (H - 0.1, 0.28), (H - 0.1, 0.33), (3.5, 1.03)], y - 0.06, y + 0.06, 'glow'))
    for k in range(2):  # arrows on the ramp pointing out
        x = 4.15 + k * 0.95
        z = 0.74 - (x + 0.3 - 3.4) / (H - 3.4) * 0.68 + 0.03
        out.append(plate(f'RampArrow{k}', [(x, -0.9), (x + 0.6, 0.0), (x, 0.9), (x + 0.25, 0.0)], z, z + 0.03, 'amber'))
    # Deck and landing circle.
    out.append(plate('Deck', octagon(3.5), 0.5, 0.75, 'hull', bevel=0.05))
    out.append(lathe('RingGlow', [(2.95, 0.76), (3.12, 0.76)], 28, 'glow', smooth=False))
    out.append(lathe('Inner', [(0.9, 0.76), (1.0, 0.76)], 16, 'amber', smooth=False))
    for k in range(8):
        g = box(f'Tick{k}', (2.2, 0, 0.77), (0.4, 0.07, 0.01), 'glow')
        out.append(kit.rot_z(g, 22.5 + 45 * k))
    # Exit arrow on the deck.
    out.append(plate('ExitArrow', [(1.5, -0.45), (2.3, 0.0), (1.5, 0.45), (1.75, 0.0)], 0.76, 0.78, 'glow'))
    # Cargo lift on the dock side: hazard-framed platform with a gantry over it.
    ly = -H * 0.62
    out.append(plate('LiftFrame', [(-1.35, ly - 1.35), (1.35, ly - 1.35), (1.35, ly + 1.0), (-1.35, ly + 1.0)], 0.5, 0.62, 'amber', bevel=0.03))
    out.append(plate('LiftDeck', [(-1.05, ly - 1.1), (1.05, ly - 1.1), (1.05, ly + 0.75), (-1.05, ly + 0.75)], 0.5, 0.66, 'turret', bevel=0.03))
    out.append(box('LiftGlow', (0, ly - 0.17, 0.665), (0.9, 0.04, 0.005), 'glow'))
    for side in (-1, 1):
        x = side * 1.6
        out.append(box(f'GantryPost{side}', (x, ly - 0.2, 1.55), (0.16, 0.16, 1.05), 'turret', bevel=0.03))
        out.append(box(f'GantryLamp{side}', (x, ly - 0.2, 2.68), (0.12, 0.12, 0.08), 'amber'))
    out.append(box('GantryBeam', (0, ly - 0.2, 2.5), (1.76, 0.18, 0.12), 'hull', bevel=0.03))
    out.append(box('GantryHook', (0, ly - 0.2, 2.2), (0.22, 0.22, 0.2), 'dark', bevel=0.03))
    # Dock apron: where the worker parks, painted bay lines just off the -Y edge.
    for side in (-1, 1):
        out.append(box(f'BayLine{side}', (side * 1.4, -H + 0.3, 0.51), (0.07, 0.28, 0.01), 'amber'))
    # Corner beacons and the control booth on the far corner.
    for k, (x, y) in enumerate(((-5.0, -5.0), (5.0, 5.0), (5.0, -5.0))):
        out.append(box(f'Beacon{k}', (x, y, 0.85), (0.25, 0.25, 0.35), 'dark', bevel=0.04))
        out.append(box(f'BeaconLamp{k}', (x, y, 1.25), (0.16, 0.16, 0.06), 'amber'))
    out.append(prism('Booth', [(-5.6, 0.5), (-3.9, 0.5), (-4.1, 2.4), (-5.4, 2.6)], 3.9, 5.6, 'turret', bevel=0.06))
    out.append(box('BoothGlass', (-3.98, 4.75, 2.0), (0.02, 0.6, 0.25), 'glow'))
    out += antenna('Ant', -5.0, 5.2, 2.6, 1.6)
    return out, {}, 5000


def t_metal_station():
    out = [foundation('Base', 4.0)]
    for k, (x, y, r, h) in enumerate(((-1.6, -1.4, 1.2, 4.2), (-1.6, 1.4, 1.0, 3.4))):
        out.append(cyl(f'Silo{k}', (x, y, 0.4), (x, y, h), r, 10, 'hull'))
        out.append(lathe(f'SiloTop{k}', [(r, h), (r * 0.6, h + 0.5)], 10, 'turret', top=h + 0.6, smooth=False))
        out.append(cyl(f'SiloBand{k}', (x, y, h * 0.55), (x, y, h * 0.55 + 0.25), r * 1.04, 10, 'glow'))
    out.append(prism('Mill', [(-0.2, 0.4), (3.4, 0.4), (3.2, 2.2), (0.1, 2.6)], -1.5, 1.5, 'turret', bevel=0.08, taper=0.85))
    out.append(prism('Hopper', [(2.2, 2.0), (3.8, 2.6), (3.8, 3.1), (1.8, 3.1)], -1.0, 1.0, 'hull', bevel=0.04))
    out.append(cyl('Coil', (0.9, -1.55, 1.4), (2.7, -1.55, 1.4), 0.35, 8, 'barrel'))
    for k, z in enumerate((1.2, 2.0)):
        out.append(cyl(f'Pipe{k}', (-0.6, -1.4 + 0.4 * k, z), (-0.2, -1.0 + 0.4 * k, z), 0.15, 6, 'dark'))
    out.append(cyl('Stack', (0.6, 1.0, 2.4), (0.6, 1.0, 4.4), 0.22, 6, 'dark'))
    out.append(box('Lamp', (3.25, 0, 1.8), (0.03, 0.9, 0.12), 'amber'))
    return out, {}, 2500


def t_turret():
    out = [foundation('Base', 2.0, 0.35)]
    out.append(lathe('Plinth', [(1.7, 0.35), (1.6, 1.0), (1.25, 1.3)], 8, 'hull', smooth=False))
    out.append(lathe('Glow', [(1.62, 0.85), (1.64, 0.95)], 8, 'glow', smooth=False))
    tz = 1.3
    tur = [prism('Turret', [(-1.3, tz), (0.9, tz), (1.4, tz + 0.35), (0.9, tz + 0.8), (-1.1, tz + 0.85), (-1.5, tz + 0.4)],
                 -1.0, 1.0, 'turret', bevel=0.07, taper=0.72)]
    tur.append(box('Mantlet', (1.4, 0, tz + 0.4), (0.22, 0.6, 0.22), 'dark', bevel=0.04))
    for y in (0.3, -0.3):
        tur += tbarrel(f'G{y}', 1.5, 4.4, y, tz + 0.4, 0.1)
    tur.append(box('Sensor', (-0.4, 0.55, tz + 1.0), (0.2, 0.15, 0.13), 'dark'))
    tur.append(box('SensorLens', (-0.18, 0.55, tz + 1.0), (0.02, 0.1, 0.07), 'glow'))
    return out, {'TurretPivot': (tur, (0, 0, tz), 'Turret', None)}, 2500


def t_radar():
    out = [foundation('Base', 2.0, 0.35)]
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        out.append(cyl(f'Leg{k}', (1.4 * math.cos(a), 1.4 * math.sin(a), 0.35), (0.35 * math.cos(a), 0.35 * math.sin(a), 4.2),
                       0.1, 4, 'hull'))
    for z, r in ((1.6, 1.05), (2.9, 0.68)):
        out.append(lathe(f'Brace{z}', [(r, z), (r, z + 0.12)], 4, 'dark', smooth=False))
    out.append(box('Hut', (0, 0, 0.9), (0.7, 0.7, 0.55), 'turret', bevel=0.05))
    out.append(box('HutLight', (0.71, 0, 1.0), (0.02, 0.4, 0.06), 'glow'))
    dz = 4.3
    dish = [cyl('Yoke', (0, 0, dz), (0, 0, dz + 0.3), 0.4, 8, 'hull')]
    d = lathe('Dish', [(0.05, 0.0), (0.7, 0.08), (1.3, 0.3), (1.7, 0.55), (1.75, 0.62)], 16, 'turret', bottom=-0.02)
    d.rotation_euler = (0, math.radians(75), 0); d.location = (-0.25, 0, dz + 1.0)
    kit._apply(d)
    dish.append(d)
    dish.append(cyl('Feed', (-0.2, 0, dz + 1.0), (1.2, 0, dz + 1.4), 0.05, 4, 'dark'))
    dish.append(orb('Horn', (1.25, 0, dz + 1.42), 0.13, 'glow'))
    dish.append(cyl('Strut', (0, 0, dz + 0.25), (-0.25, 0, dz + 0.95), 0.1, 6, 'dark'))
    out.append(box('TopLamp', (0, 0, dz - 0.05), (0.12, 0.12, 0.05), 'amber'))
    return out, {'TurretPivot': (dish, (0, 0, dz), 'Dish', None)}, 2500


def t_lab():
    out = [foundation('Base', 4.0)]
    out.append(prism('Hall', [(-3.4, 0.4), (3.0, 0.4), (3.4, 1.2), (2.8, 2.2), (-3.0, 2.2), (-3.5, 1.4)], -2.4, 2.4,
                     'hull', bevel=0.08, taper=0.8))
    out.append(lathe('Dome', [(1.9, 2.2), (1.85, 2.7), (1.5, 3.3), (0.9, 3.75), (0.3, 3.95)], 14, 'glow', top=4.0))
    out.append(lathe('DomeRing', [(2.0, 2.2), (2.0, 2.45)], 14, 'turret', smooth=False))
    for k in range(6):
        a = k * math.pi / 3
        rb = cyl(f'Rib{k}', (1.92 * math.cos(a), 1.92 * math.sin(a), 2.4), (0.3 * math.cos(a), 0.3 * math.sin(a), 3.98), 0.07,
                 4, 'dark')
        out.append(rb)
    for y in (2.42, -2.42):
        out.append(box(f'Win{y}', (-0.3, y, 1.45), (2.2, 0.02, 0.18), 'glow'))
    out.append(prism('Wing', [(-3.4, 0.4), (-1.6, 0.4), (-1.8, 1.6), (-3.2, 1.6)], 2.4, 3.6, 'turret', bevel=0.05))
    out += antenna('Ant', 2.6, -1.8, 2.2, 2.2)
    out.append(box('Door', (3.25, 0, 0.9), (0.05, 0.7, 0.45), 'amber'))
    return out, {}, 2500


def t_air_base():
    out = [foundation('Base', 6.0, 0.35)]
    out.append(plate('Runway', [(-5.8, -1.3), (5.8, -1.3), (5.8, 1.3), (-5.8, 1.3)], 0.35, 0.42, 'dark'))
    for k in range(7):
        out.append(box(f'Dash{k}', (-4.8 + 1.6 * k, 0, 0.43), (0.45, 0.06, 0.005), 'glow'))
    for y in (1.35, -1.35):
        for k in range(6):
            out.append(box(f'Edge{y}{k}', (-5.2 + 2.08 * k, y, 0.48), (0.08, 0.08, 0.06), 'amber'))
    # Hangar with a curved roof at the back.
    prof = [(-2.6, 0.4)] + [(-2.6 * math.cos(math.pi * t / 8), 0.4 + 2.6 * math.sin(math.pi * t / 8)) for t in range(1, 8)] + [(2.6, 0.4)]
    out.append(prism('Hangar', prof, 2.0, 5.8, 'hull', bevel=0.05))
    out.append(box('HangarDoor', (0, 1.98, 1.4), (2.1, 0.02, 0.95), 'turret'))
    out.append(box('DoorGlow', (0, 1.96, 2.45), (2.1, 0.02, 0.05), 'glow'))
    out.append(cyl('Tower', (4.6, 3.6, 0.4), (4.6, 3.6, 3.6), 0.5, 8, 'hull'))
    out.append(lathe('Cab', [(0.6, 3.6), (0.95, 3.9), (0.9, 4.5), (0.6, 4.7)], 8, 'turret', center=(4.6, 3.6, 0), top=4.75,
                     smooth=False))
    out.append(lathe('CabGlass', [(0.96, 4.0), (0.93, 4.35)], 8, 'glow', center=(4.6, 3.6, 0), smooth=False))
    out += antenna('Ant', 4.6, 3.6, 4.75, 1.4)
    return out, {}, 5000


def t_missile_battery():
    out = [foundation('Base', 2.0, 0.35)]
    out.append(lathe('Plinth', [(1.6, 0.35), (1.5, 0.9), (1.0, 1.15)], 8, 'hull', smooth=False))
    tz = 1.15
    tur = [cyl('Ring', (0, 0, tz), (0, 0, tz + 0.25), 0.9, 10, 'dark')]
    for y in (0.95, -0.95):
        tur.append(prism(f'Yoke{y}', [(-0.6, tz + 0.25), (0.6, tz + 0.25), (0.3, tz + 1.2), (-0.3, tz + 1.2)], y - 0.12,
                         y + 0.12, 'hull'))
    pitch = math.radians(40)
    ca, sa = math.cos(pitch), math.sin(pitch)
    cz = tz + 1.2

    def P(x, z):
        return (x * ca - z * sa, cz + x * sa + z * ca)
    tur.append(prism('Launcher', [P(-1.4, -0.55), P(1.4, -0.55), P(1.4, 0.55), P(-1.4, 0.55)], -0.82, 0.82, 'turret',
                     bevel=0.06))
    for j in range(2):
        for k in range(3):
            a, b = P(1.35, -0.25 + 0.5 * j), P(1.44, -0.25 + 0.5 * j)
            y = -0.5 + 0.5 * k
            tur.append(cyl(f'Cell{j}{k}', (a[0], y, a[1]), (b[0], y, b[1]), 0.19, 8, 'glow'))
    tur.append(box('Stripe', (0, 0.84, cz), (0.9, 0.02, 0.06), 'amber'))
    return out, {'TurretPivot': (tur, (0, 0, tz), 'Turret', None)}, 2500


# ---------------------------------------------------------------- Kesh
def k_base(name, r, h=0.35):
    return lathe(name, [(r, 0.0), (r * 0.97, h * 0.6), (r * 0.85, h)], 16, 'dark', top=h, smooth=True)


def k_landing_nest():
    """Kesh nest, same layout as the Terran pad: open mouth toward +X (exit), cargo cradle on -Y.
    The petals float free of the base, held up by nothing, like the rest of the Kesh."""
    out = [k_base('Base', 5.8)]
    out.append(lathe('Bowl', [(5.2, 0.35), (4.6, 0.75), (3.0, 0.55), (1.2, 0.45)], 20, 'shell', top=0.45))
    out.append(ring('GoldRing', (0, 0, 0.62), 2.9, 0.08, sides=24, tube=4, tile='glow'))
    out.append(orb('Heart', (0, 0, 0.5), 0.55, 'core', scale=(1, 1, 0.35)))
    # Exit tongue: a smooth lip sloping down and out on +X.
    out.append(prism('Tongue', [(3.2, 0.0), (6.0, 0.0), (6.0, 0.06), (3.2, 0.62)], -2.3, 2.3, 'shell', bevel=0.12, taper=0.8))
    for side in (-1, 1):
        out.append(cyl(f'TongueVein{side}', (3.5, side * 1.5, 0.52), (5.6, side * 1.6, 0.08), 0.06, 5, 'glow'))
    # Floating petals, leaving the mouth (+X) and the cradle side (-Y) open.
    for k, a in enumerate((67.5, 112.5, 157.5, 202.5, 247.5)):
        f = arc_fin(f'Petal{k}', 8.4, 0.3, 3.6, 180, 118, 0.55, 0.12, tile='fin')
        f.location = (0, 0, 0.35)
        kit._apply(f)
        out.append(kit.rot_z(f, a))
    # Cargo cradle on -Y: a floating ring over a glowing pool, held by three hovering claws.
    ly = -5.8 * 0.62
    out.append(lathe('Pool', [(1.25, 0.66), (1.05, 0.72)], 16, 'glow', center=(0, ly, 0), top=0.72, smooth=False))
    out.append(ring('CradleRing', (0, ly, 1.9), 1.15, 0.1, sides=20, tube=5, tile='fin'))
    for k in range(3):
        a = math.radians(90 + k * 120)
        cx, cy = 1.35 * math.cos(a), ly + 1.35 * math.sin(a)
        claw = arc_fin(f'Claw{k}', 0.0, 0.0, 1.3, 210, 150, 0.32, 0.1, tile='shell')
        claw.location = (cx, cy, 1.25)
        kit._apply(claw)
        out.append(kit.rot_z(claw, math.degrees(a) + 180, about=(cx, cy, 1.25)))
        out.append(orb(f'ClawBead{k}', (cx, cy, 0.95), 0.12, 'core'))
    return out, {}, 5000


def k_metal_siphon():
    out = [k_base('Base', 3.6)]
    for k in range(3):
        f = arc_fin(f'Leg{k}', 0, 0.3, 3.2, 10, 85, 0.7, 0.18, tile='fin', tip=0.1)
        out.append(kit.rot_z(f, 120 * k))
    out.append(lathe('Spire', [(1.3, 0.3), (1.1, 1.5), (0.7, 3.2), (0.35, 4.8), (0.1, 5.8)], 12, 'shell', top=6.1))
    out.append(orb('Core', (0, 0, 3.0), 0.75, 'core', seg=(12, 8)))
    out.append(ring('Halo', (0, 0, 3.0), 1.35, 0.07, sides=18, tube=4, tile='glow', tilt=(math.radians(15), 0)))
    for k in range(3):
        a = math.radians(60 + 120 * k)
        out.append(cyl(f'Tube{k}', (2.6 * math.cos(a), 2.6 * math.sin(a), 0.4), (0.9 * math.cos(a), 0.9 * math.sin(a), 2.4),
                       0.18, 6, 'barrel'))
        out.append(orb(f'Intake{k}', (2.7 * math.cos(a), 2.7 * math.sin(a), 0.45), 0.35, 'glow', scale=(1, 1, 0.5)))
    return out, {}, 2500


def k_thornmound():
    out = [k_base('Base', 1.9)]
    out.append(lathe('Mound', [(1.7, 0.3), (1.5, 0.9), (1.0, 1.35), (0.5, 1.5)], 12, 'shell', top=1.55))
    for k in range(6):
        t = kit.rot_z(cyl(f'Thorn{k}', (1.3, 0, 0.7), (2.1, 0, 1.6), 0.18, 5, 'fin', r1=0.0), 60 * k + 30)
        out.append(t)
    tz = 1.5
    tur = [loft('Head', lens(-1.2, 1.2, 0.7, tz + 0.7, tz - 0.05, tz + 0.25, n=7, nose=0.7), 10, 'shell')]
    tur.append(arc_fin('Crest', -0.6, tz + 0.2, 1.3, 200, 60, 0.4, 0.08))
    tur += kbarrel('Gun', 1.0, 3.6, 0, tz + 0.25, 0.1)
    tur.append(orb('Eye', (0.9, 0, tz + 0.55), 0.18, 'core'))
    return out, {'TurretPivot': (tur, (0, 0, tz), 'Turret', None)}, 2500


def k_seer_spire():
    out = [k_base('Base', 1.9)]
    out.append(lathe('Root', [(1.5, 0.3), (1.0, 0.9), (0.5, 1.6)], 10, 'shell', smooth=True))
    for k in range(3):
        f = arc_fin(f'Spire{k}', 0, 0.8, 3.2, 100, 172, 0.45, 0.1, tile='fin')
        out.append(kit.rot_z(f, 120 * k))
    ez = 4.6
    eye = [orb('Eye', (0, 0, ez), 0.7, 'core', seg=(12, 8))]
    eye.append(ring('Ring', (0, 0, ez), 1.3, 0.07, sides=20, tube=4, tile='fin', tilt=(math.radians(25), 0)))
    for k in range(4):
        a = 2 * math.pi * k / 4
        eye.append(orb(f'Bead{k}', (1.3 * math.cos(a), 1.3 * math.sin(a) * math.cos(math.radians(25)),
                                    ez + 1.3 * math.sin(a) * math.sin(math.radians(25))), 0.13, 'glow'))
    return out, {'TurretPivot': (eye, (0, 0, ez), 'Eye', None)}, 2500


def k_gene_vault():
    out = [k_base('Base', 3.8)]
    out.append(lathe('Vault', [(3.2, 0.3), (3.3, 1.0), (2.9, 2.2), (2.0, 3.2), (1.0, 3.7)], 16, 'shell', top=3.85))
    out.append(ring('Band', (0, 0, 1.2), 3.32, 0.08, sides=20, tube=4, tile='glow'))
    for k in range(5):
        f = arc_fin(f'Petal{k}', 0, 0.3, 3.7, 5, 60, 0.5, 0.12, tile='fin')
        out.append(kit.rot_z(f, 72 * k + 36))
    for k in range(3):
        a = 2 * math.pi * k / 3
        out.append(orb(f'Pod{k}', (2.6 * math.cos(a), 2.6 * math.sin(a), 2.6), 0.42, 'core'))
    out.append(orb('Crown', (0, 0, 4.1), 0.45, 'core'))
    out.append(arc_fin('Arch', 0, 3.6, 1.2, 20, 160, 0.25, 0.06))
    return out, {}, 2500


def k_hive_roost():
    out = [k_base('Base', 5.8)]
    out.append(lathe('Disc', [(3.0, 0.35), (2.8, 0.55), (1.0, 0.6)], 18, 'shell', top=0.6))
    out.append(ring('DiscRing', (0, 0, 0.62), 2.2, 0.06, sides=20, tube=4, tile='glow'))
    for k, yaw in enumerate((0, 60, 120)):
        f = arc_fin(f'Arch{k}', 0, 0.3, 5.0, 15, 165, 0.6, 0.18, tile='fin')
        out.append(kit.rot_z(f, yaw))
    for k in range(6):
        a = math.radians(60 * k + 30)
        x, y = 4.6 * math.cos(a), 4.6 * math.sin(a)
        out.append(cyl(f'Perch{k}', (x, y, 0.35), (x, y, 2.0), 0.18, 6, 'shell'))
        out.append(orb(f'PerchGlow{k}', (x, y, 2.1), 0.25, 'glow'))
    out.append(orb('Heart', (0, 0, 4.6), 0.55, 'core'))
    return out, {}, 5000


def k_spore_tower():
    out = [k_base('Base', 1.9)]
    out.append(lathe('Stalk', [(1.4, 0.3), (0.9, 1.0), (0.55, 2.4), (0.6, 3.0)], 10, 'shell', smooth=True))
    for k in range(3):
        f = arc_fin(f'Leaf{k}', 0, 0.4, 1.9, 15, 80, 0.4, 0.08, tile='fin')
        out.append(kit.rot_z(f, 120 * k + 60))
    tz = 3.0
    tur = [lathe('Cup', [(0.6, 0.0), (1.1, 0.3), (1.2, 0.7), (1.0, 0.9)], 12, 'fin', center=(0, 0, tz), smooth=True)]
    for k in range(5):
        a = 2 * math.pi * k / 5
        p = (0.55 * math.cos(a) + 0.2, 0.55 * math.sin(a), tz + 1.0)
        tur.append(orb(f'Spore{k}', p, 0.32, 'core', seg=(8, 6), scale=(1, 1, 1.4)))
    tur.append(orb('Lead', (0.3, 0, tz + 1.4), 0.38, 'glow'))
    return out, {'TurretPivot': (tur, (0, 0, tz), 'Turret', None)}, 2500


STRUCTURES = {
    'terran_landing_pad': ('terran', t_landing_pad), 'terran_metal_station': ('terran', t_metal_station),
    'terran_turret': ('terran', t_turret), 'terran_radar': ('terran', t_radar), 'terran_lab': ('terran', t_lab),
    'terran_air_base': ('terran', t_air_base), 'terran_missile_battery': ('terran', t_missile_battery),
    'kesh_landing_nest': ('kesh', k_landing_nest), 'kesh_metal_siphon': ('kesh', k_metal_siphon),
    'kesh_thornmound': ('kesh', k_thornmound), 'kesh_seer_spire': ('kesh', k_seer_spire),
    'kesh_gene_vault': ('kesh', k_gene_vault), 'kesh_hive_roost': ('kesh', k_hive_roost),
    'kesh_spore_tower': ('kesh', k_spore_tower),
}


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    atlas_dir, out_dir, which = args[0], args[1], args[2]
    render_dir = args[3] if len(args) > 3 else None
    if which in ('all', 'terran', 'kesh'):
        names = [n for n, (f, _) in STRUCTURES.items() if which in ('all', f)]
    else:
        names = which.split(',')
    report = []
    for name in names:
        faction, fn = STRUCTURES[name]
        kit.begin(faction, atlas_dir)
        body, pivots, budget = fn()
        kit.assemble(''.join(p.title() for p in name.split('_')), body, pivots)
        n = kit.finish(f'{out_dir}/{name}.glb', budget)
        report.append((name, n, budget))
        if render_dir:
            views = tuple(os.environ.get('VIEWS', 'front34,rts').split(','))
            res = tuple(int(v) for v in os.environ.get('RES', '900x560').split('x'))
            kit.preview(render_dir, name, views=views, res=res, samples=int(os.environ.get('SAMPLES', '32')))
    for r in report:
        print('STRUCT %-26s %5d / %d' % r)
