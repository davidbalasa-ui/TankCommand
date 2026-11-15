"""Terran (human) unit set, built on tools/art/kit.py with the shared Terran atlas.

Same family as the approved Lancer (tools/art/terran_lancer.py): dark angular armour with chamfered,
sloped plates, track pods with side skirts, cyan seams and lights, orange running lights.
Budgets: normal units <= 2,500 triangles, big units (heavy tank, artillery, bomber) <= 5,000.

Run with Blender's Python (pip bpy):
  python terran_set.py <atlas_dir> <out_dir> <unit[,unit...]|all> [render_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cyl, lathe, loft, lens, orb, plate, prism  # noqa: E402


# ---------------------------------------------------------------- shared pieces
def wheel(name, x, y, z, r, w, sides=8, hub_glow=False):
    s = 1 if y > 0 else -1
    out = [cyl(f'{name}W', (x, y - s * w / 2, z), (x, y + s * w / 2, z), r, sides, 'dark')]
    out.append(cyl(f'{name}H', (x, y + s * w / 2, z), (x, y + s * (w / 2 + 0.04), z), r * 0.35, 6,
                   'glow' if hub_glow else 'dark'))
    return out


def tracked(L=6.2, hw=1.25, top=1.45, nwheels=6, pod_y=1.62, pod_w=0.42, skirt=True, lights=True):
    """Tracked chassis in the Lancer style. Returns (parts, deck_z)."""
    x0, x1 = -L / 2, L / 2
    parts = [prism('HullCore', [(x0, 0.55), (x1 - 0.6, 0.55), (x1, 0.95), (x1 - 0.8, top), (x0 + 0.3, top),
                                (x0 - 0.1, top - 0.3)], -hw, hw, 'hull', bevel=0.09, taper=0.82)]
    pod = [(x0 - 0.25, 0.1), (x1 - 0.25, 0.1), (x1 + 0.2, 0.5), (x1 - 0.2, 0.9), (x0 - 0.2, 0.9), (x0 - 0.45, 0.5)]
    for side in (1, -1):
        y = side * pod_y
        parts.append(prism(f'Track{side}', pod, y - pod_w, y + pod_w, 'track', bevel=0.07))
        y_out = y + side * (pod_w + 0.06)
        if skirt:
            sk = [(x0 - 0.1, 0.7), (x1 - 0.4, 0.7), (x1 - 0.05, 1.0), (x1 - 0.5, 1.32), (x0, 1.32)]
            parts.append(prism(f'Skirt{side}', sk, min(y, y_out), max(y, y_out), 'hull', bevel=0.05))
            if lights:
                parts.append(box(f'Amber{side}', (x1 - 0.2, y_out, 1.1), (0.12, 0.05, 0.06), 'amber'))
                parts.append(box(f'Seam{side}', (0.0, y_out + side * 0.02, 0.95), (L * 0.35, 0.02, 0.03), 'glow'))
        step = (L - 1.1) / (nwheels - 1)
        for i in range(nwheels):
            parts += wheel(f'Wh{side}{i}', x0 + 0.5 + i * step, y + side * (pod_w + 0.01), 0.45, 0.36, 0.08,
                           hub_glow=(i % 2 == 0))
    if lights:
        for y in (0.7 * hw, -0.7 * hw):
            parts.append(box(f'Head{y}', (x1 - 0.12, y, 1.02), (0.06, 0.16, 0.06), 'glow'))
    return parts, top


def antenna(name, x, y, z, h):
    return [cyl(name, (x, y, z), (x, y, z + h), 0.025, 4, 'dark'), box(f'{name}Tip', (x, y, z + h), (0.04, 0.04, 0.04), 'amber')]


def barrel(name, x0, x1, y, z, r, shroud=True):
    out = [cyl(f'{name}B', (x0, y, z), (x1, y, z), r, 8, 'dark')]
    if shroud:
        out.append(cyl(f'{name}S', (x0, y, z), (x0 + (x1 - x0) * 0.4, y, z), r * 1.55, 8, 'barrel'))
    out.append(cyl(f'{name}M', (x1 - 0.4, y, z), (x1 + 0.05, y, z), r * 1.35, 6, 'dark'))
    return out


# ---------------------------------------------------------------- units
def outrider():
    """Scout: fast six-wheeled armoured car, low wedge, small turret with an autocannon and a sensor mast."""
    body = [prism('Body', [(-2.7, 0.7), (2.1, 0.7), (2.9, 1.05), (2.0, 1.5), (-1.6, 1.62), (-2.8, 1.3)],
                  -1.0, 1.0, 'hull', bevel=0.08, taper=0.72)]
    body.append(prism('Belly', [(-2.5, 0.45), (2.0, 0.45), (2.4, 0.72), (-2.6, 0.72)], -0.85, 0.85, 'dark', bevel=0.04))
    for side in (1, -1):
        y = side * 1.18
        fender = [(-2.6, 0.95), (2.4, 0.95), (2.75, 1.15), (2.2, 1.3), (-2.4, 1.3), (-2.75, 1.12)]
        body.append(prism(f'Fender{side}', fender, min(y, y + side * 0.42), max(y, y + side * 0.42), 'hull', bevel=0.04))
        for i, x in enumerate((-1.75, 0.05, 1.75)):
            body += wheel(f'W{side}{i}', x, side * 1.4, 0.56, 0.56, 0.44, sides=10, hub_glow=True)
        body.append(box(f'Amber{side}', (2.6, side * 1.5, 1.15), (0.1, 0.06, 0.05), 'amber'))
        body.append(box(f'Seam{side}', (-0.2, side * 1.62, 1.08), (2.1, 0.02, 0.025), 'glow'))
    for y in (0.6, -0.6):
        body.append(box(f'Head{y}', (2.75, y, 1.1), (0.06, 0.16, 0.05), 'glow'))
    body.append(box('RearRack', (-2.45, 0, 1.55), (0.3, 0.75, 0.12), 'dark', bevel=0.03))
    body += antenna('Whip', -2.4, 0.7, 1.6, 1.6)
    tz = 1.6
    tur = [prism('Turret', [(-1.1, tz), (0.8, tz), (1.3, tz + 0.25), (0.8, tz + 0.55), (-0.9, tz + 0.55), (-1.25, tz + 0.3)],
                 -0.65, 0.65, 'turret', bevel=0.06, taper=0.7)]
    tur += barrel('Gun', 1.1, 3.6, 0.0, tz + 0.27, 0.08)
    tur.append(cyl('Mast', (-0.6, -0.3, tz + 0.5), (-0.6, -0.3, tz + 1.35), 0.05, 6, 'dark'))
    tur.append(orb('Sensor', (-0.6, -0.3, tz + 1.42), 0.16, 'glow'))
    tur.append(box('Optic', (0.55, 0.38, tz + 0.48), (0.18, 0.1, 0.08), 'dark'))
    tur.append(box('OpticLens', (0.74, 0.38, tz + 0.48), (0.02, 0.07, 0.05), 'glow'))
    return body, {'TurretPivot': (tur, (0, 0, tz), 'Turret', None)}, 2500


def prospector():
    """Ore miner: tracked hauler with a big cutter drum on arms at the front, cab, rear ore hopper."""
    body, top = tracked(L=6.6, hw=1.3, nwheels=6)
    # Cutter drum: a wide drum with a glowing coil band and cutter teeth, carried on two arms.
    dx, dz = 3.75, 0.75
    body.append(cyl('Drum', (dx, -1.45, dz), (dx, 1.45, dz), 0.62, 10, 'barrel'))
    for k in range(10):
        a = 2 * math.pi * k / 10
        for y in (-1.0, 0.0, 1.0):
            px, pz = dx + 0.62 * math.cos(a), dz + 0.62 * math.sin(a)
            body.append(cyl(f'Tooth{k}{y}', (px, y + 0.25 * (k % 2), pz), (dx + 0.9 * math.cos(a + 0.25), y + 0.25 * (k % 2),
                                                                         dz + 0.9 * math.sin(a + 0.25)), 0.08, 4, 'dark', r1=0.01))
    for y in (1.5, -1.5):
        body.append(prism(f'Arm{y}', [(2.4, 0.75), (3.75, 0.55), (3.85, 0.95), (2.5, 1.3)], y - 0.12, y + 0.12, 'hull',
                          bevel=0.03))
        body.append(cyl(f'Ram{y}', (2.2, y * 0.82, 1.4), (3.3, y * 1.05, 0.95), 0.09, 6, 'barrel'))
    # Cab on the front left, hopper bin at the rear.
    body.append(prism('Cab', [(0.8, top), (2.4, top), (2.2, top + 0.85), (1.0, top + 0.95)], 0.15, 1.2, 'turret',
                      bevel=0.05, taper=0.9))
    body.append(box('CabGlass', (2.31, 0.68, top + 0.55), (0.02, 0.42, 0.2), 'glow'))
    hx0, hx1, hz = -3.0, 0.4, top
    for name, c, s in (('BinL', ((hx0 + hx1) / 2, 1.22, hz + 0.6), ((hx1 - hx0) / 2, 0.08, 0.6)),
                       ('BinR', ((hx0 + hx1) / 2, -1.22, hz + 0.6), ((hx1 - hx0) / 2, 0.08, 0.6)),
                       ('BinB', (hx0, 0, hz + 0.6), (0.08, 1.2, 0.6)), ('BinF', (hx1, 0, hz + 0.5), (0.08, 1.2, 0.5))):
        body.append(box(name, c, s, 'hull', bevel=0.03))
    # Ore heap inside the bin, ribs, a chute.
    body.append(lathe('Heap', [(1.4, 0.0), (1.05, 0.35), (0.5, 0.6)], 8, 'dark', center=((hx0 + hx1) / 2, 0, hz + 0.6),
                      top=0.68, scale=(1.15, 0.75)))
    for x in (-2.2, -1.3, -0.4):
        body.append(box(f'Rib{x}', (x, 1.32, hz + 0.6), (0.06, 0.03, 0.58), 'dark'))
        body.append(box(f'RibR{x}', (x, -1.32, hz + 0.6), (0.06, 0.03, 0.58), 'dark'))
    body.append(prism('Chute', [(0.4, top + 0.2), (2.4, 0.95), (2.6, 1.15), (0.5, top + 0.5)], -1.0, -0.4, 'dark'))
    body.append(box('Beacon', (1.6, 0.68, top + 1.02), (0.12, 0.12, 0.07), 'amber'))
    return body, {}, 2500


def hauler():
    """Tug: heavy tracked tractor with a tall cab and a rear cradle with clamp arms and a winch."""
    body, top = tracked(L=6.4, hw=1.25, nwheels=6)
    body.append(prism('Cab', [(1.0, top), (3.0, top), (2.7, top + 1.1), (1.2, top + 1.25)], -1.05, 1.05, 'turret',
                      bevel=0.07, taper=0.85))
    body.append(box('CabGlass', (2.86, 0, top + 0.72), (0.02, 0.7, 0.22), 'glow'))
    body.append(box('CabRoofLights', (2.0, 0, top + 1.28), (0.12, 0.6, 0.04), 'amber'))
    body.append(box('Bed', (-1.3, 0, top + 0.12), (1.8, 1.15, 0.12), 'dark', bevel=0.03))
    for y in (1.0, -1.0):
        body.append(prism(f'Clamp{y}', [(-2.9, top + 0.2), (-0.2, top + 0.2), (-0.4, top + 0.75), (-2.6, top + 0.95)],
                          y - 0.1, y + 0.1, 'hull', bevel=0.03))
        body.append(box(f'ClampPad{y}', (-1.5, y * 0.88, top + 0.6), (0.9, 0.04, 0.12), 'glow'))
    body.append(cyl('Winch', (-0.1, -0.8, top + 0.55), (-0.1, 0.8, top + 0.55), 0.32, 10, 'barrel'))
    body.append(box('Hitch', (-3.35, 0, 0.9), (0.25, 0.3, 0.15), 'dark', bevel=0.03))
    body.append(cyl('Exhaust', (0.7, 0.95, top), (0.7, 0.95, top + 1.6), 0.09, 6, 'dark'))
    return body, {}, 2500


def mender():
    """Repair vehicle: tracked chassis, rear workshop module, a turning repair arm with a welding head."""
    body, top = tracked(L=6.2, hw=1.25, nwheels=6)
    body.append(prism('Shop', [(-3.0, top), (0.6, top), (0.4, top + 1.0), (-2.8, top + 1.05)], -1.1, 1.1, 'turret',
                      bevel=0.07, taper=0.88))
    for y in (1.0, -1.0):
        body.append(box(f'ShopStripe{y}', (-1.2, y * 1.02, top + 0.55), (1.6, 0.02, 0.05), 'glow'))
    body.append(box('ToolRack', (-2.2, 0, top + 1.15), (0.5, 0.75, 0.1), 'dark', bevel=0.02))
    body.append(prism('CabFront', [(0.6, top), (2.6, top), (2.3, top + 0.55), (0.7, top + 0.65)], -0.9, 0.9, 'hull',
                      bevel=0.05, taper=0.85))
    body.append(box('CabGlass', (2.45, 0, top + 0.4), (0.02, 0.6, 0.12), 'glow'))
    ax, az = -0.8, top + 1.05
    arm = [cyl('ArmBase', (ax, 0, az), (ax, 0, az + 0.35), 0.45, 10, 'dark')]
    shoulder = (ax + 0.1, 0, az + 0.45)
    elbow = (ax + 1.9, 0, az + 1.7)
    wrist = (ax + 3.4, 0, az + 0.9)
    for n, (a, b, r) in (('Boom', (shoulder, elbow, 0.2)), ('Fore', (elbow, wrist, 0.15))):
        arm.append(cyl(n, a, b, r, 6, 'hull'))
    arm.append(orb('Elbow', elbow, 0.24, 'dark'))
    arm.append(cyl('Piston', (ax + 0.5, 0, az + 0.4), (ax + 1.5, 0, az + 1.35), 0.07, 6, 'barrel'))
    arm.append(cyl('Head', wrist, (wrist[0] + 0.25, 0, wrist[2] - 0.5), 0.13, 6, 'dark', r1=0.05))
    arm.append(orb('Torch', (wrist[0] + 0.3, 0, wrist[2] - 0.6), 0.09, 'amber'))
    arm.append(box('Beacon', (ax, 0.5, az + 0.4), (0.1, 0.1, 0.06), 'amber'))
    return body, {'TurretPivot': (arm, (ax, 0, az), 'Arm', None)}, 2500


def watchman():
    """Mobile radar: tracked chassis, equipment housing, a big rotating dish on a mast."""
    body, top = tracked(L=6.2, hw=1.25, nwheels=6)
    body.append(prism('Housing', [(-2.8, top), (1.4, top), (1.1, top + 0.75), (-2.6, top + 0.8)], -1.05, 1.05, 'turret',
                      bevel=0.07, taper=0.85))
    body.append(prism('CabFront', [(1.4, top), (2.6, top), (2.3, top + 0.5), (1.5, top + 0.55)], -0.9, 0.9, 'hull',
                      bevel=0.05))
    body.append(box('CabGlass', (2.45, 0, top + 0.35), (0.02, 0.6, 0.1), 'glow'))
    for x in (-2.2, -1.5, -0.8):
        body.append(box(f'Vent{x}', (x, 0, top + 0.82), (0.22, 0.75, 0.04), 'dark'))
    mx, mz = -0.6, top + 0.8
    body.append(cyl('Mast', (mx, 0, mz), (mx, 0, mz + 1.2), 0.22, 8, 'dark'))
    dz = mz + 1.3
    dish = [cyl('Yoke', (mx, 0, dz - 0.1), (mx, 0, dz + 0.25), 0.35, 8, 'hull')]
    # Parabolic dish facing forward and up; profile revolved then tilted.
    prof = [(0.05, 0.0), (0.8, 0.08), (1.5, 0.32), (2.0, 0.6), (2.05, 0.68)]
    d = lathe('Dish', prof, 16, 'turret', center=(0, 0, 0), smooth=True, bottom=-0.02)
    d.rotation_euler = (0, math.radians(70), 0)
    d.location = (mx - 0.2, 0, dz + 1.1)
    kit._apply(d)
    dish.append(d)
    dish.append(cyl('Feed', (mx - 0.15, 0, dz + 1.1), (mx + 1.35, 0, dz + 1.65), 0.06, 4, 'dark'))
    dish.append(orb('FeedHorn', (mx + 1.4, 0, dz + 1.67), 0.14, 'glow'))
    dish.append(cyl('Strut', (mx, 0, dz + 0.2), (mx - 0.2, 0, dz + 1.05), 0.12, 6, 'dark'))
    return body, {'TurretPivot': (dish, (mx, 0, dz), 'Dish', None)}, 2500


def skimmer():
    """Hover tank: a fast angular hovercraft with a rubber skirt, two rear ducted fans, twin light guns."""
    H = 0.35
    body = [prism('Hull', [(-2.9, H + 0.35), (2.2, H + 0.35), (3.2, H + 0.7), (2.2, H + 1.15), (-2.5, H + 1.2),
                           (-3.0, H + 0.9)], -1.35, 1.35, 'hull', bevel=0.09, taper=0.7)]
    body.append(prism('Skirt', [(-3.0, H), (2.6, H), (3.3, H + 0.45), (-3.1, H + 0.45)], -1.55, 1.55, 'dark', bevel=0.1))
    for side in (1, -1):
        body.append(box(f'Seam{side}', (0, side * 1.45, H + 0.5), (2.4, 0.02, 0.03), 'glow'))
        body.append(box(f'Amber{side}', (2.9, side * 1.2, H + 0.75), (0.1, 0.06, 0.05), 'amber'))
        fy = side * 0.8
        body.append(lathe(f'Duct{side}', [(0.72, -0.4), (0.78, 0.0), (0.72, 0.4), (0.6, 0.4), (0.6, -0.4)], 12, 'hull',
                          center=(0, 0, 0), smooth=False))
        duct = body[-1]
        duct.rotation_euler = (0, math.radians(90), 0); duct.location = (-2.55, fy, H + 1.3)
        kit._apply(duct)
        body.append(cyl(f'Fan{side}', (-2.95, fy, H + 1.3), (-2.85, fy, H + 1.3), 0.6, 10, 'glow'))
        body.append(box(f'Hub{side}', (-2.75, fy, H + 1.3), (0.2, 0.16, 0.16), 'dark'))
    tz = H + 1.2
    tur = [prism('Turret', [(-1.2, tz), (0.9, tz), (1.4, tz + 0.25), (0.9, tz + 0.5), (-1.0, tz + 0.5)], -0.75, 0.75,
                 'turret', bevel=0.06, taper=0.7)]
    for y in (0.22, -0.22):
        tur += barrel(f'G{y}', 1.2, 3.6, y, tz + 0.25, 0.07)
    tur.append(box('Sensor', (-0.5, 0.4, tz + 0.6), (0.18, 0.12, 0.1), 'dark'))
    tur.append(box('SensorLens', (-0.31, 0.4, tz + 0.6), (0.02, 0.08, 0.05), 'glow'))
    return body, {'TurretPivot': (tur, (0, 0, tz), 'Turret', None)}, 2500


def bulwark():
    """Heavy tank: longer, wider Lancer cousin; big turret with twin heavy cannons and side rocket pods."""
    body, top = tracked(L=7.6, hw=1.5, top=1.55, nwheels=7, pod_y=1.95, pod_w=0.48)
    body.append(prism('Deck', [(-3.3, 1.55), (2.8, 1.55), (2.2, 1.85), (-3.0, 1.85)], -1.3, 1.3, 'hull', bevel=0.06,
                      taper=0.8))
    body.append(prism('NoseArmor', [(2.8, 1.25), (3.85, 0.95), (4.0, 1.07), (3.0, 1.58)], -1.2, 1.2, 'turret', bevel=0.04))
    for side in (1, -1):
        for i, x in enumerate((-2.4, -0.8, 0.8, 2.3)):
            body.append(box(f'Plate{side}{i}', (x, side * 2.5, 1.0), (0.72, 0.06, 0.33), 'hull', bevel=0.03))
            body.append(box(f'Bolt{side}{i}', (x + 0.5, side * 2.57, 1.15), (0.05, 0.02, 0.05), 'glow'))
    body.append(box('Engine', (-3.45, 0, 1.75), (0.4, 1.0, 0.25), 'dark', bevel=0.05, taper=0.85))
    for y in (0.6, -0.6):
        body.append(box(f'Exh{y}', (-3.85, y, 1.3), (0.06, 0.3, 0.14), 'dark'))
        body.append(box(f'ExhG{y}', (-3.92, y, 1.3), (0.01, 0.24, 0.06), 'glow'))
    tx, tz = -0.6, 1.85
    tur = [prism('TurretBody', [(tx - 2.1, tz), (tx + 1.6, tz), (tx + 2.5, tz + 0.35), (tx + 1.8, tz + 0.95),
                                (tx - 1.6, tz + 1.0), (tx - 2.3, tz + 0.55)], -1.35, 1.35, 'turret', bevel=0.09, taper=0.72)]
    tur.append(prism('Roof', [(tx - 1.3, tz + 0.95), (tx + 1.4, tz + 0.95), (tx + 1.1, tz + 1.15), (tx - 1.0, tz + 1.15)],
                     -0.9, 0.9, 'turret', bevel=0.04))
    tur.append(prism('Bustle', [(tx - 3.0, tz + 0.15), (tx - 2.1, tz + 0.1), (tx - 2.1, tz + 0.9), (tx - 2.8, tz + 0.85)],
                     -1.05, 1.05, 'turret', bevel=0.05, taper=0.8))
    tur.append(box('Mantlet', (tx + 2.5, 0, tz + 0.45), (0.3, 0.85, 0.3), 'dark', bevel=0.06, taper=0.8))
    for y in (0.4, -0.4):
        tur += barrel(f'Gun{y}', tx + 2.6, tx + 9.2, y, tz + 0.45, 0.15)
    for side in (1, -1):
        y = side * 1.55
        tur.append(box(f'Pod{side}', (tx - 0.3, y, tz + 0.55), (0.9, 0.28, 0.3), 'hull', bevel=0.04))
        for k in range(3):
            for j in range(2):
                tur.append(cyl(f'Rk{side}{k}{j}', (tx + 0.55, y + (k - 1) * 0.17, tz + 0.43 + j * 0.24),
                               (tx + 0.62, y + (k - 1) * 0.17, tz + 0.43 + j * 0.24), 0.07, 6, 'amber'))
    tur.append(cyl('Cupola', (tx - 0.4, -0.5, tz + 1.15), (tx - 0.4, -0.5, tz + 1.4), 0.32, 8, 'turret'))
    tur.append(box('CupolaGlass', (tx - 0.4, -0.5, tz + 1.42), (0.22, 0.22, 0.02), 'glow'))
    tur.append(box('TurretSeam', (tx + 0.3, 0, tz + 1.16), (1.0, 0.02, 0.01), 'glow'))
    tur += antenna('Ant', tx - 2.5, 0.7, tz + 0.85, 1.4)
    return body, {'TurretPivot': (tur, (tx, 0, tz), 'Turret', None)}, 5000


def javelin():
    """Missile tank: tracked chassis, a turning launcher of eight tubes raised on a yoke."""
    body, top = tracked(L=6.2, hw=1.25, nwheels=6)
    body.append(prism('Deck', [(-2.6, top), (2.2, top), (1.6, top + 0.3), (-2.3, top + 0.3)], -1.05, 1.05, 'hull',
                      bevel=0.06, taper=0.8))
    tx, tz = -0.5, top + 0.3
    tur = [cyl('Ring', (tx, 0, tz), (tx, 0, tz + 0.3), 0.95, 10, 'dark')]
    for y in (0.95, -0.95):
        tur.append(prism(f'Yoke{y}', [(tx - 0.6, tz + 0.3), (tx + 0.6, tz + 0.3), (tx + 0.3, tz + 1.2), (tx - 0.3, tz + 1.2)],
                         y - 0.12, y + 0.12, 'hull', bevel=0.03))
    # Launcher box, pitched up 18 degrees, 2 rows of 4 tubes with glowing caps.
    pitch = math.radians(18)
    cx, cz = tx + 0.2, tz + 1.15
    L2, H2, W2 = 1.7, 0.45, 0.82
    ca, sa = math.cos(pitch), math.sin(pitch)

    def P(x, z):
        return (cx + x * ca - z * sa, cz + x * sa + z * ca)
    prof = [P(-L2, -H2), P(L2, -H2), P(L2, H2), P(-L2, H2)]
    tur.append(prism('Launcher', prof, -W2, W2, 'turret', bevel=0.06))
    for j in range(2):
        for k in range(4):
            y = -0.6 + 0.4 * k
            zz = -0.2 + 0.4 * j
            a = P(L2 - 0.05, zz); b = P(L2 + 0.04, zz)
            tur.append(cyl(f'Tube{j}{k}', (a[0], y, a[1]), (b[0], y, b[1]), 0.15, 8, 'glow'))
    tur.append(box('LaunchStripe', (cx, 0.84, cz), (1.2, 0.02, 0.05), 'amber'))
    tur.append(box('Optic', (tx + 0.6, -0.65, tz + 0.5), (0.2, 0.12, 0.12), 'dark'))
    tur.append(box('OpticLens', (tx + 0.81, -0.65, tz + 0.5), (0.02, 0.08, 0.06), 'glow'))
    return body, {'TurretPivot': (tur, (tx, 0, tz), 'Turret', None)}, 2500


def longbow():
    """Artillery: tracked chassis, rear casemate, a very long gun raised high, recoil spades folded at the back."""
    body, top = tracked(L=6.8, hw=1.3, nwheels=7)
    body.append(prism('CabFront', [(1.4, top), (3.0, top), (2.7, top + 0.5), (1.5, top + 0.55)], -1.0, 1.0, 'hull',
                      bevel=0.05, taper=0.85))
    body.append(box('CabGlass', (2.85, 0, top + 0.35), (0.02, 0.65, 0.1), 'glow'))
    for y in (0.85, -0.85):
        body.append(prism(f'Spade{y}', [(-3.4, 0.3), (-3.0, 0.3), (-2.9, 1.3), (-3.3, 1.45)], y - 0.3, y + 0.3, 'dark',
                          bevel=0.03))
    tx, tz = -0.9, top
    tur = [prism('Casemate', [(tx - 2.0, tz), (tx + 1.7, tz), (tx + 1.4, tz + 1.15), (tx - 1.8, tz + 1.2)], -1.15, 1.15,
                 'turret', bevel=0.08, taper=0.78)]
    tur.append(box('Seam', (tx, 0, tz + 1.21), (1.2, 0.02, 0.01), 'glow'))
    el = math.radians(32)
    gx, gz = tx + 1.2, tz + 0.75
    ca, sa = math.cos(el), math.sin(el)
    tur.append(box('Cradle', (gx, 0, gz), (0.45, 0.55, 0.38), 'dark', bevel=0.05))
    end = (gx + 7.0 * ca, 0, gz + 7.0 * sa)
    tur.append(cyl('Tube', (gx, 0, gz), end, 0.18, 10, 'dark'))
    tur.append(cyl('Sleeve', (gx, 0, gz), (gx + 2.6 * ca, 0, gz + 2.6 * sa), 0.27, 10, 'barrel'))
    tur.append(cyl('Brake', (end[0] - 0.55 * ca, 0, end[2] - 0.55 * sa), (end[0] + 0.1 * ca, 0, end[2] + 0.1 * sa), 0.3, 8,
                   'dark'))
    for y in (0.3, -0.3):
        tur.append(cyl(f'Recoil{y}', (gx - 0.2, y, gz - 0.1), (gx + 2.0 * ca, y, gz + 2.0 * sa - 0.1), 0.08, 6, 'barrel'))
    tur += antenna('Ant', tx - 1.6, -0.7, tz + 1.15, 1.2)
    return body, {'TurretPivot': (tur, (tx, 0, tz), 'Turret', None)}, 5000


def falcon():
    """Fighter: delta-wing jet with canted twin tails, a cyan canopy and twin glowing engines."""
    Z = 0.0
    body = [loft('Fuselage', lens(-3.8, 4.2, 0.62, Z + 0.55, Z - 0.35, Z, n=10, nose=0.62), 10, 'hull', smooth=False)]
    body.append(plate('Wing', [(-3.1, 0.4), (1.2, 0.4), (-2.2, 4.0), (-3.3, 4.0)], Z - 0.07, Z + 0.07, 'hull', bevel=0.02))
    body.append(plate('WingR', [(-3.1, -0.4), (-3.3, -4.0), (-2.2, -4.0), (1.2, -0.4)], Z - 0.07, Z + 0.07, 'hull', bevel=0.02))
    body.append(plate('Canard', [(1.6, 0.35), (2.6, 0.35), (1.5, 1.4), (1.2, 1.4)], Z + 0.05, Z + 0.1, 'turret'))
    body.append(plate('CanardR', [(1.6, -0.35), (1.2, -1.4), (1.5, -1.4), (2.6, -0.35)], Z + 0.05, Z + 0.1, 'turret'))
    for side in (1, -1):
        tail = kit.prism(f'Tail{side}', [(-3.6, 0.0), (-2.4, 0.0), (-3.0, 1.5), (-3.5, 1.5)], -0.05, 0.05, 'turret', bevel=0.01)
        tail.rotation_euler = (math.radians(-22 * side), 0, 0)
        tail.location = (0, side * 0.5, Z + 0.3)
        kit._apply(tail)
        body.append(tail)
        body.append(box(f'TipLight{side}', (-2.8, side * 4.0, Z), (0.12, 0.04, 0.04), 'amber'))
        body.append(box(f'WingSeam{side}', (-1.6, side * 1.9, Z + 0.075), (0.9, 0.02, 0.005), 'glow'))
        y = side * 0.38
        body.append(cyl(f'Nozzle{side}', (-3.6, y, Z - 0.05), (-4.2, y, Z - 0.05), 0.3, 10, 'dark', r1=0.25))
        body.append(cyl(f'Burn{side}', (-4.15, y, Z - 0.05), (-4.22, y, Z - 0.05), 0.22, 10, 'glow'))
        body.append(cyl(f'Intake{side}', (0.4, side * 0.65, Z - 0.15), (-1.2, side * 0.65, Z - 0.15), 0.26, 6, 'dark'))
        body.append(cyl(f'Missile{side}', (-1.4, side * 2.6, Z - 0.18), (0.2, side * 2.6, Z - 0.18), 0.08, 6, 'turret'))
    body.append(orb('Canopy', (1.8, 0, Z + 0.45), 0.5, 'glow', seg=(10, 6), scale=(2.0, 0.75, 0.6)))
    return body, {}, 2500


def condor():
    """Bomber: heavy swept flying wing with a central fuselage, four engines, glowing bay seams."""
    Z = 0.0
    body = [loft('Fuselage', lens(-4.2, 5.4, 1.25, Z + 1.0, Z - 0.6, Z, n=11, nose=0.6), 12, 'hull', smooth=False)]
    wing = [(-3.8, 0.9), (3.6, 0.9), (0.4, 8.2), (-1.6, 8.2), (-2.6, 4.5), (-3.9, 3.6)]
    body.append(plate('WingL', wing, Z - 0.25, Z + 0.22, 'hull', bevel=0.06))
    body.append(plate('WingR', [(x, -y) for x, y in wing[::-1]], Z - 0.25, Z + 0.22, 'hull', bevel=0.06))
    for side in (1, -1):
        for k, (x, y) in enumerate(((0.6, 2.4), (-0.6, 4.6))):
            yy = side * y
            body.append(cyl(f'Nac{side}{k}', (x + 1.0, yy, Z + 0.55), (x - 2.0, yy, Z + 0.55), 0.48, 10, 'turret'))
            body.append(cyl(f'Inlet{side}{k}', (x + 1.05, yy, Z + 0.55), (x + 1.1, yy, Z + 0.55), 0.36, 10, 'dark'))
            body.append(cyl(f'Burn{side}{k}', (x - 2.0, yy, Z + 0.55), (x - 2.08, yy, Z + 0.55), 0.38, 10, 'glow'))
            body.append(box(f'Pylon{side}{k}', (x - 0.4, yy, Z + 0.25), (0.9, 0.08, 0.12), 'dark'))
        tail = prism(f'Fin{side}', [(-4.3, 0.0), (-2.6, 0.0), (-3.5, 1.8), (-4.1, 1.8)], -0.07, 0.07, 'turret', bevel=0.01)
        tail.rotation_euler = (math.radians(-28 * side), 0, 0)
        tail.location = (0, side * 0.7, Z + 0.5)
        kit._apply(tail)
        body.append(tail)
        body.append(box(f'Tip{side}', (-0.6, side * 8.2, Z), (0.45, 0.06, 0.06), 'amber'))
        body.append(box(f'Seam{side}', (-1.2, side * 6.2, Z + 0.225), (1.4, 0.02, 0.005), 'glow'))
    body.append(box('BayL', (0.3, 0.32, Z - 0.5), (1.8, 0.02, 0.01), 'glow'))
    body.append(box('BayR', (0.3, -0.32, Z - 0.5), (1.8, 0.02, 0.01), 'glow'))
    body.append(orb('Canopy', (3.6, 0, Z + 0.82), 0.5, 'glow', seg=(10, 6), scale=(1.6, 1.2, 0.45)))
    body.append(cyl('Sensor', (5.2, 0, Z), (5.7, 0, Z), 0.12, 6, 'dark', r1=0.02))
    return body, {}, 5000


def packed(kind):
    """Packed turret / missile battery: a low wheeled skid crate with the weapon folded on top."""
    body = [prism('Skid', [(-2.6, 0.45), (2.4, 0.45), (2.8, 0.8), (2.4, 1.2), (-2.4, 1.2), (-2.8, 0.85)], -1.15, 1.15,
                  'hull', bevel=0.08, taper=0.85)]
    for side in (1, -1):
        for i, x in enumerate((-1.6, 1.4)):
            body += wheel(f'W{side}{i}', x, side * 1.22, 0.42, 0.42, 0.3, sides=8, hub_glow=True)
        for k in range(4):
            body.append(box(f'Chev{side}{k}', (-1.5 + k * 1.0, side * 1.17, 0.95), (0.18, 0.02, 0.06), 'amber'))
    body.append(box('Lug', (2.7, 0, 0.75), (0.2, 0.3, 0.12), 'dark'))
    if kind == 'turret':
        body.append(lathe('Housing', [(1.15, 0.0), (1.2, 0.2), (1.0, 0.6), (0.6, 0.78)], 8, 'turret', center=(-0.6, 0, 1.2),
                          smooth=False, top=0.8))
        body.append(cyl('FoldedGun', (-0.2, 0, 1.75), (-3.3, 0, 1.85), 0.15, 8, 'dark'))
        body.append(cyl('GunShroud', (-0.2, 0, 1.75), (-1.4, 0, 1.8), 0.24, 8, 'barrel'))
        body.append(box('Rest', (-2.6, 0, 1.45), (0.12, 0.25, 0.3), 'dark'))
        body.append(box('Lamp', (0.4, 0, 1.95), (0.15, 0.15, 0.05), 'glow'))
    else:
        body.append(box('Rack', (-0.4, 0, 1.55), (1.9, 0.95, 0.33), 'turret', bevel=0.06))
        for k in range(4):
            body.append(cyl(f'Cell{k}', (1.52, -0.66 + k * 0.44, 1.55), (1.58, -0.66 + k * 0.44, 1.55), 0.17, 8, 'glow'))
        body.append(box('RackStripe', (-0.4, 0.97, 1.55), (1.5, 0.02, 0.06), 'amber'))
        body.append(cyl('Hinge', (-2.25, -0.9, 1.25), (-2.25, 0.9, 1.25), 0.12, 6, 'dark'))
    return body, {}, 2500


UNITS = {
    'outrider': outrider, 'prospector': prospector, 'hauler': hauler, 'mender': mender, 'watchman': watchman,
    'skimmer': skimmer, 'bulwark': bulwark, 'javelin': javelin, 'longbow': longbow, 'falcon': falcon, 'condor': condor,
    'bastion_packed': lambda: packed('turret'), 'spire_packed': lambda: packed('missile'),
}
AIR = {'falcon': 3.0, 'condor': 3.5}


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    atlas_dir, out_dir, which = args[0], args[1], args[2]
    render_dir = args[3] if len(args) > 3 else None
    names = list(UNITS) if which == 'all' else which.split(',')
    report = []
    for name in names:
        kit.begin('terran', atlas_dir)
        body, pivots, budget = UNITS[name]()
        kit.assemble(name.title().replace('_', ''), body, pivots)
        n = kit.finish(f'{out_dir}/{name}.glb', budget)
        report.append((name, n, budget))
        if render_dir:
            views = tuple(os.environ.get('VIEWS', 'front34,rts,side').split(','))
            res = tuple(int(v) for v in os.environ.get('RES', '900x560').split('x'))
            kit.preview(render_dir, name, lift=AIR.get(name, 0.0), views=views, res=res,
                        samples=int(os.environ.get('SAMPLES', '32')))
    for r in report:
        print('UNIT %-16s %5d / %d' % r)
