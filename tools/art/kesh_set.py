"""Kesh (alien) unit set, built on tools/art/kit.py with the shared Kesh atlas.

Same family as the approved Darter scout (tools/art/kesh_darter.py): hovering lens-shaped
silver-bronze hulls with etched shells, layered petals with gold slots, crescent fins, glowing gold
core orbs. Nothing touches the ground: every hull floats with a gold hover plate underneath.
Budgets: normal units <= 2,500 triangles, big units (heavy, artillery) <= 5,000.

Run with Blender's Python (pip bpy):
  python kesh_set.py <atlas_dir> <out_dir> <unit[,unit...]|all> [render_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cyl, lathe, loft, lens, orb, plate, prism  # noqa: E402

HOVER = 0.75


# ---------------------------------------------------------------- shared pieces
def hover_plate(name, cx, rx, ry, z=HOVER + 0.02, n=14):
    pts = [(cx + rx * math.cos(2 * math.pi * k / n), ry * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return kit.mesh_from(name, [(x, y, z) for x, y in pts], [list(range(n))[::-1]], 'under')


def arc_fin(name, cx, cz, R, a0, a1, th, half_w, tile='shell', n=9, y=0.0, yaw=0.0, tip=0.03, flat=False):
    """A crescent blade in the XZ plane: arc of radius R from angle a0 to a1 (degrees), thickest mid-way."""
    outer, inner = [], []
    for i in range(n):
        t = i / (n - 1)
        a = math.radians(a0 + (a1 - a0) * t)
        w = th * math.sin(math.pi * t) ** 0.7 + tip
        outer.append((R * math.cos(a), R * math.sin(a)))
        inner.append(((R - w) * math.cos(a), (R - w) * math.sin(a)))
    prof = outer + inner[::-1]
    if flat:  # lying in the horizontal plane at height cz, centre (cx, y)
        return plate(name, [(cx + px, y + py) for px, py in prof][::-1], cz - half_w, cz + half_w, tile)
    o = prism(name, prof, -half_w, half_w, tile)
    o.rotation_euler = (0, 0, math.radians(yaw))
    o.location = (cx, y, cz)
    kit._apply(o)
    return o


def ring(name, c, R, r, sides=16, tube=6, tile='fin', tilt=(0, 0)):
    prof = [(R + r * math.cos(2 * math.pi * k / tube), r * math.sin(2 * math.pi * k / tube)) for k in range(tube + 1)]
    o = lathe(name, prof, sides, tile, center=(0, 0, 0), smooth=True)
    o.rotation_euler = (tilt[0], tilt[1], 0)
    o.location = c
    kit._apply(o)
    return o


def petals(prefix, spans, y, zm, h=0.5, w=0.38):
    """Layered side petals with gold slots tucked underneath, both sides. spans: [(x0, x1)]."""
    out = []
    for side in (1, -1):
        for i, (x0, x1) in enumerate(spans):
            out.append(loft(f'{prefix}P{side}{i}', lens(x0, x1, w, zm + h, zm - 0.3, zm, n=7, nose=1.0), 8, 'fin',
                            cy=side * y))
            slot = [(x0 + 0.5, zm - 0.12), (x1 - 0.6, zm - 0.12), (x1 - 0.9, zm - 0.02), (x0 + 0.8, zm - 0.02)]
            yy = side * (y + 0.18)
            out.append(prism(f'{prefix}S{side}{i}', slot, min(yy, yy + side * 0.05), max(yy, yy + side * 0.05), 'glow'))
    return out


def barrel(name, x0, x1, y, z, r=0.1):
    return [cyl(f'{name}Sl', (x0, y, z), (x0 + (x1 - x0) * 0.45, y, z), r * 1.6, 8, 'shell'),
            cyl(f'{name}B', (x0, y, z), (x1, y, z), r, 8, 'shell'),
            cyl(f'{name}G', (x0 + (x1 - x0) * 0.5, y, z), (x1 - 0.3, y, z), r * 1.05, 8, 'barrel'),
            cyl(f'{name}M', (x1 - 0.35, y, z), (x1 + 0.05, y, z), r * 1.4, 8, 'fin'),
            orb(f'{name}C', (x1 + 0.08, y, z), r, 'glow')]


# ---------------------------------------------------------------- units
def stinger():
    """Light tank: compact scarab hull with a dorsal ridge; the weapon is a scorpion tail curling over
    the back and striking forward, a gold orb in its tip, twin short guns under the nose."""
    body = [loft('Hull', lens(-2.9, 2.9, 1.7, HOVER + 1.2, HOVER + 0.05, HOVER + 0.5, n=9, nose=0.8), 12, 'shell')]
    body.append(loft('Ridge', lens(-2.4, 2.3, 0.35, HOVER + 1.5, HOVER + 0.9, HOVER + 1.1, n=7), 6, 'fin'))
    body.append(hover_plate('Hover', 0.0, 2.0, 1.2))
    body += petals('Side', [(-2.6, 0.2), (-0.6, 2.6)], 1.45, HOVER + 0.45, h=0.45)
    for side in (1, -1):
        body.append(orb(f'Eye{side}', (2.25, side * 0.55, HOVER + 0.8), 0.17, 'core'))
        body += barrel(f'Gun{side}', 2.2, 3.8, side * 0.45, HOVER + 0.38, 0.07)
    tx, tz = -0.6, HOVER + 1.25
    tail = [lathe('Socket', [(0.75, 0.0), (0.7, 0.2), (0.45, 0.35)], 10, 'fin', center=(tx, 0, tz), top=0.4)]
    # Tail: segments climbing back and up, then curling forward over the hull.
    pts = []
    for i in range(8):
        a = math.radians(200 - 165 * i / 7)
        pts.append((tx + 0.3 + 1.7 * math.cos(a), 0, tz + 0.3 + 1.9 * math.sin(a) * 0.95 + (0.2 if i > 0 else 0)))
    for i in range(len(pts) - 1):
        r0 = 0.33 - 0.028 * i
        tail.append(cyl(f'Seg{i}', pts[i], pts[i + 1], r0, 8, 'shell' if i % 2 else 'fin', r1=r0 - 0.03))
        tail.append(orb(f'Joint{i}', pts[i + 1], r0 * 0.95, 'barrel', seg=(8, 5)))
    end = pts[-1]
    tail.append(orb('Venom', (end[0] + 0.25, 0, end[2] - 0.1), 0.3, 'core'))
    tail.append(cyl('Barb', (end[0] + 0.35, 0, end[2] - 0.15), (end[0] + 1.3, 0, end[2] - 0.6), 0.14, 6, 'fin', r1=0.0))
    return body, {'TurretPivot': (tail, (tx, 0, tz), 'Turret', None)}, 2500


def gorger():
    """Ore miner: a fat hovering hull with two curved mandibles framing a glowing intake maw, and a big
    glowing ore sac on its back."""
    body = [loft('Hull', lens(-3.2, 2.8, 1.8, HOVER + 1.3, HOVER + 0.05, HOVER + 0.55, n=9, nose=0.7), 12, 'shell')]
    body.append(hover_plate('Hover', -0.2, 2.2, 1.3))
    body += petals('Side', [(-3.0, 0.0)], 1.55, HOVER + 0.5, h=0.5)
    for side in (1, -1):
        body.append(arc_fin(f'Mandible{side}', 1.5, HOVER + 0.62, 1.45, side * 85, side * 12, 0.34, 0.09, tile='fin',
                            flat=True))
        body.append(orb(f'Eye{side}', (2.35, side * 0.95, HOVER + 1.05), 0.14, 'core'))
    body.append(orb('Maw', (2.45, 0, HOVER + 0.5), 0.4, 'glow', scale=(0.5, 1.3, 0.7)))
    body.append(orb('Sac', (-1.3, 0, HOVER + 1.55), 1.0, 'core', seg=(12, 8), scale=(1.3, 1.0, 0.75)))
    for k in range(5):
        a = -0.9 + 0.45 * k
        body.append(cyl(f'Rib{k}', (-1.3 - 1.25 * math.cos(a), 1.0 * math.sin(a), HOVER + 1.25),
                        (-1.3 - 1.25 * math.cos(a) * 0.6, 0.6 * math.sin(a), HOVER + 2.25), 0.07, 5, 'fin'))
    body.append(arc_fin('Crest', -1.3, HOVER + 1.2, 1.3, 20, 160, 0.25, 0.06, tile='shell'))
    return body, {}, 2500


def ferrier():
    """Tug: long flat hull ending in two forward crescent prongs with a gold tractor glow between them."""
    body = [loft('Hull', lens(-3.3, 1.9, 1.3, HOVER + 0.95, HOVER + 0.05, HOVER + 0.45, n=9, nose=0.6), 12, 'shell')]
    body.append(hover_plate('Hover', -0.6, 2.0, 1.0))
    body += petals('Side', [(-3.0, 0.4)], 1.2, HOVER + 0.45, h=0.4)
    for side in (1, -1):
        body.append(arc_fin(f'Prong{side}', 1.0, HOVER + 0.55, 1.9, side * 75, side * 12, 0.32, 0.09, tile='fin',
                            flat=True))
        body.append(orb(f'Emitter{side}', (2.82, side * 0.42, HOVER + 0.5), 0.2, 'core'))
    body.append(orb('Beam', (2.85, 0, HOVER + 0.5), 0.3, 'glow', scale=(0.3, 1.3, 0.3)))
    body.append(orb('Core', (-1.0, 0, HOVER + 1.05), 0.42, 'core'))
    body.append(arc_fin('Fin', -1.8, HOVER + 0.6, 1.2, 60, 175, 0.3, 0.06))
    return body, {}, 2500


def weaver():
    """Repair craft: hovering lens hull, above it a slowly turning halo ring with three needle arms
    pointing at a central orb (the repair beam source)."""
    body = [loft('Hull', lens(-2.9, 2.9, 1.5, HOVER + 1.0, HOVER + 0.05, HOVER + 0.45, n=9), 12, 'shell')]
    body.append(hover_plate('Hover', 0.0, 2.0, 1.1))
    body += petals('Side', [(-2.7, 0.0), (-0.4, 2.6)], 1.3, HOVER + 0.42, h=0.4)
    hz = HOVER + 2.0
    body.append(cyl('Stem', (0, 0, HOVER + 0.9), (0, 0, hz - 0.2), 0.16, 6, 'fin'))
    halo = [ring('Halo', (0, 0, hz), 1.5, 0.11, sides=20, tube=5, tile='fin')]
    halo.append(orb('Heart', (0, 0, hz), 0.38, 'core'))
    for k in range(3):
        a = 2 * math.pi * k / 3
        p = (1.5 * math.cos(a), 1.5 * math.sin(a), hz)
        halo.append(cyl(f'Needle{k}', p, (0.5 * math.cos(a), 0.5 * math.sin(a), hz), 0.09, 5, 'shell', r1=0.0))
        halo.append(orb(f'Node{k}', p, 0.17, 'glow'))
    return body, {'TurretPivot': (halo, (0, 0, hz), 'Halo', None)}, 2500


def seer():
    """Radar: a tall crescent spire holding a great floating eye-orb, circled by a tilted turning ring."""
    body = [loft('Hull', lens(-2.6, 2.6, 1.4, HOVER + 0.9, HOVER + 0.05, HOVER + 0.4, n=9), 12, 'shell')]
    body.append(hover_plate('Hover', 0.0, 1.8, 1.0))
    body += petals('Side', [(-2.4, 2.2)], 1.25, HOVER + 0.4, h=0.4)
    body.append(arc_fin('Spire', 0.9, HOVER + 0.6, 2.6, 95, 175, 0.55, 0.14))
    ez = HOVER + 3.4
    eye = [orb('Eye', (0, 0, ez), 0.6, 'core', seg=(12, 8))]
    eye.append(ring('EyeRing', (0, 0, ez), 1.15, 0.07, sides=20, tube=4, tile='fin', tilt=(math.radians(25), 0)))
    for k in range(4):
        a = 2 * math.pi * k / 4
        eye.append(orb(f'Bead{k}', (1.15 * math.cos(a), 1.15 * math.sin(a) * math.cos(math.radians(25)),
                                    ez + 1.15 * math.sin(a) * math.sin(math.radians(25))), 0.12, 'glow'))
    return body, {'TurretPivot': (eye, (0, 0, ez), 'Eye', None)}, 2500


def glider():
    """Light aircraft: manta-like swept wing with crescent tips, a lens body and gold slots."""
    Z = 0.0
    body = [loft('Body', lens(-2.8, 3.2, 0.7, Z + 0.45, Z - 0.3, Z, n=9), 10, 'shell')]
    outline = []
    for i in range(13):
        t = i / 12
        a = math.pi * t
        outline.append((1.4 - 3.4 * t ** 1.4 + 0.8 * math.sin(a), 4.2 * math.sin(a) ** 0.6))
    wl = outline[:7] + [(-2.2, 0.0)]
    body.append(plate('WingL', [(x, y + 0.3) for x, y in wl], Z - 0.06, Z + 0.06, 'fin', smooth=True))
    body.append(plate('WingR', [(x, -y - 0.3) for x, y in wl[::-1]], Z - 0.06, Z + 0.06, 'fin', smooth=True))
    for side in (1, -1):
        body.append(arc_fin(f'Tip{side}', 0.7, Z, 0.7, 20, 130, 0.22, 0.04, y=side * 4.45, tile='shell'))
        body.append(box(f'Slot{side}', (-0.3, side * 2.0, Z + 0.065), (0.8, 0.06, 0.005), 'glow'))
        body.append(orb(f'Drive{side}', (-2.4, side * 0.5, Z), 0.2, 'glow'))
    body.append(orb('Core', (0.8, 0, Z + 0.4), 0.28, 'core'))
    return body, {}, 2500


def disc():
    """Saucer: a thick lens disc with a domed top, a ring of gold rim lights and a glowing underside."""
    Z = 0.0
    prof = [(0.0, Z - 0.45), (1.6, Z - 0.35), (2.9, Z - 0.1), (3.2, Z), (2.9, Z + 0.15), (1.8, Z + 0.45), (1.0, Z + 0.6)]
    body = [lathe('Disc', prof, 20, 'shell', center=(0, 0, 0), top=0.62, smooth=True)]
    body.append(lathe('Dome', [(1.05, Z + 0.55), (0.95, Z + 0.9), (0.6, Z + 1.15)], 14, 'fin', top=1.25))
    body.append(orb('Eye', (0.85, 0, Z + 0.95), 0.25, 'core'))
    body.append(ring('Rim', (0, 0, Z), 3.15, 0.06, sides=24, tube=4, tile='glow'))
    body.append(lathe('Under', [(1.6, Z - 0.37), (0.8, Z - 0.5)], 14, 'under', bottom=-0.52))
    for k in range(6):
        a = 2 * math.pi * k / 6
        rd = box(f'Ridge{k}', (2.15, 0, Z + 0.22), (0.65, 0.07, 0.07), 'fin')
        body.append(kit.rot_z(rd, math.degrees(a)))
        sl = box(f'RidgeGlow{k}', (2.15, 0, Z + 0.3), (0.5, 0.025, 0.02), 'glow')
        body.append(kit.rot_z(sl, math.degrees(a)))
    return body, {}, 2500


def dropper():
    """Air transport: a bulky hovering lens with four curved claws underneath gripping a cargo orb."""
    Z = 0.0
    body = [loft('Hull', lens(-3.4, 3.2, 1.6, Z + 1.0, Z - 0.5, Z, n=9, nose=0.7), 12, 'shell')]
    body += [o for o in petals('Side', [(-3.1, 0.2), (-0.8, 2.9)], 1.45, Z, h=0.5)]
    for side in (1, -1):
        wing = [(0.6, 1.3), (-2.8, 3.6), (-3.4, 3.4), (-1.6, 1.3)]
        pts = [(x, side * y) for x, y in wing]
        body.append(plate(f'Wing{side}', pts if side > 0 else pts[::-1], Z + 0.15, Z + 0.25, 'fin'))
        body.append(box(f'WingSlot{side}', (-1.4, side * 2.4, Z + 0.26), (0.7, 0.05, 0.005), 'glow'))
        body.append(orb(f'Drive{side}', (-3.2, side * 0.7, Z + 0.1), 0.3, 'glow'))
    body.append(orb('Cargo', (0.0, 0, Z - 1.35), 0.75, 'core'))
    for k in range(4):
        yaw = 45 + 90 * k
        body.append(arc_fin(f'Claw{k}', 0.0, Z - 1.3, 1.05, 190, 330, 0.25, 0.08, yaw=yaw, tile='fin'))
    body.append(cyl('Tether', (0, 0, Z - 0.5), (0, 0, Z - 0.7), 0.25, 8, 'dark'))
    return body, {}, 2500


def carapace():
    """Heavy tank: two overlapping shell layers, a broad turret flanked by twin crescent fins, twin long
    gold-slotted guns and three core orbs along the back."""
    body = [loft('HullLow', lens(-4.0, 3.8, 2.1, HOVER + 0.9, HOVER + 0.05, HOVER + 0.45, n=11, nose=0.7), 14, 'shell')]
    body.append(loft('HullHigh', lens(-3.4, 2.8, 1.6, HOVER + 1.45, HOVER + 0.6, HOVER + 0.9, n=9, nose=0.7), 12, 'fin'))
    body.append(hover_plate('Hover', -0.1, 2.8, 1.6))
    body += petals('Side', [(-3.8, -0.6), (-1.6, 1.6), (0.4, 3.6)], 1.95, HOVER + 0.45, h=0.5, w=0.42)
    for k, x in enumerate((-3.0, -2.2, -1.4)):
        body.append(orb(f'Core{k}', (x, 0, HOVER + 1.45), 0.3, 'core'))
    for side in (1, -1):
        body.append(orb(f'Eye{side}', (3.1, side * 0.75, HOVER + 0.8), 0.18, 'core'))
    tx, tz = 0.2, HOVER + 1.4
    tur = [loft('Turret', lens(-1.9, 2.0, 1.15, tz + 0.85, tz - 0.05, tz + 0.3, n=9, nose=0.7), 12, 'shell')]
    for side in (1, -1):
        tur.append(loft(f'Shoulder{side}', lens(-1.5, 1.4, 0.35, tz + 0.65, tz + 0.05, tz + 0.35, n=6), 6, 'fin',
                        cy=side * 1.15))
        tur.append(arc_fin(f'Crescent{side}', tx - 1.5, tz + 0.4, 1.9, 200, 50, 0.55, 0.1, y=side * 0.75))
        tur += barrel(f'Gun{side}', tx + 1.6, tx + 8.0, side * 0.42, tz + 0.35, 0.13)
    tur.append(cyl('Collar', (tx + 1.2, 0, tz + 0.35), (tx + 2.0, 0, tz + 0.35), 0.45, 10, 'dark'))
    tur.append(orb('Brow', (tx + 1.0, 0, tz + 0.8), 0.25, 'core'))
    return body, {'TurretPivot': (tur, (tx, 0, tz), 'Turret', None)}, 5000


def spitter():
    """Missile craft: lens hull, a turning crescent frame holding a fan of six glowing seed pods."""
    body = [loft('Hull', lens(-2.9, 2.9, 1.55, HOVER + 1.0, HOVER + 0.05, HOVER + 0.45, n=9), 12, 'shell')]
    body.append(hover_plate('Hover', 0.0, 2.0, 1.1))
    body += petals('Side', [(-2.7, 0.0), (-0.4, 2.7)], 1.35, HOVER + 0.42, h=0.42)
    tx, tz = -0.4, HOVER + 0.95
    tur = [lathe('Base', [(0.8, 0.0), (0.75, 0.25), (0.5, 0.4)], 10, 'fin', center=(tx, 0, tz), top=0.45)]
    tur.append(arc_fin('Frame', 0, tz + 0.4, 1.85, 15, 165, 0.4, 0.15, yaw=90))
    tur[-1].location.x += tx - 0.2
    kit._apply(tur[-1])
    for side in (1, -1):
        tur.append(cyl(f'Strut{side}', (tx, side * 0.45, tz + 0.3), (tx - 0.2, side * 1.72, tz + 0.88), 0.11, 6, 'fin'))
    for k in range(5):
        a = math.radians(30 + 30 * k)
        p = (tx + 0.15, 1.4 * math.cos(a), tz + 0.4 + 1.4 * math.sin(a))
        tur.append(orb(f'Pod{k}', p, 0.22, 'core', seg=(8, 6), scale=(2.0, 0.8, 0.8)))
        tur.append(cyl(f'PodTip{k}', (p[0] + 0.4, p[1], p[2]), (p[0] + 0.75, p[1], p[2]), 0.15, 6, 'fin', r1=0.0))
    return body, {'TurretPivot': (tur, (tx, 0, tz), 'Turret', None)}, 2500


def mortar_beast():
    """Artillery: long heavy hull; on its back four tall curved prongs cradle a great glowing orb that
    it hurls in a high arc. A tilted ring of gold beads circles the cradle."""
    body = [loft('Hull', lens(-4.0, 3.6, 1.9, HOVER + 1.1, HOVER + 0.05, HOVER + 0.5, n=11, nose=0.75), 14, 'shell')]
    body.append(loft('Spine', lens(-3.6, 3.0, 0.4, HOVER + 1.45, HOVER + 0.9, HOVER + 1.15, n=7), 6, 'fin'))
    body.append(hover_plate('Hover', -0.2, 2.6, 1.4))
    body += petals('Side', [(-3.8, -0.4), (-1.4, 1.8), (0.4, 3.4)], 1.75, HOVER + 0.45, h=0.5, w=0.4)
    for side in (1, -1):
        body.append(orb(f'Eye{side}', (3.0, side * 0.65, HOVER + 0.8), 0.16, 'core'))
    tx, tz = -1.0, HOVER + 1.3
    tur = [lathe('Socket', [(1.1, 0.0), (1.0, 0.3), (0.6, 0.5)], 12, 'fin', center=(tx, 0, tz), top=0.55)]
    oz = tz + 2.1
    tur.append(cyl('Stalk', (tx, 0, tz + 0.5), (tx, 0, oz - 0.6), 0.25, 8, 'fin'))
    tur.append(orb('Shell', (tx, 0, oz), 0.8, 'core', seg=(12, 8)))
    for k in range(4):
        pr = arc_fin(f'Prong{k}', 0, oz, 1.2, -85, 55, 0.32, 0.09, tile='shell', tip=0.0)
        tur.append(kit.rot_z(pr, 45 + 90 * k))
        tur[-1].location.x += tx
        kit._apply(tur[-1])
    tur.append(ring('Beads', (tx, 0, oz - 0.6), 1.5, 0.06, sides=18, tube=4, tile='glow', tilt=(0, math.radians(15))))
    return body, {'TurretPivot': (tur, (tx, 0, tz), 'Turret', None)}, 5000


def seed(kind):
    """Packed turret / spore tower: a hovering seed pod with its weapon folded flat along the back."""
    body = [loft('Seed', lens(-2.6, 2.6, 1.25, HOVER + 1.1, HOVER + 0.05, HOVER + 0.5, n=9, nose=0.9), 12, 'shell')]
    body.append(hover_plate('Hover', 0.0, 1.8, 0.95))
    body += petals('Side', [(-2.4, 2.2)], 1.1, HOVER + 0.45, h=0.45)
    if kind == 'thorn':
        for k in range(5):
            x = -1.6 + 0.8 * k
            body.append(cyl(f'Thorn{k}', (x, 0, HOVER + 1.05), (x - 1.0, 0, HOVER + 1.45), 0.16, 5, 'fin', r1=0.0))
        body.append(orb('Bud', (1.6, 0, HOVER + 1.0), 0.3, 'core'))
    else:
        body.append(loft('Tower', lens(-2.2, 1.6, 0.45, HOVER + 1.55, HOVER + 0.95, HOVER + 1.2, n=7), 8, 'fin'))
        for k in range(4):
            body.append(orb(f'Spore{k}', (-1.5 + 0.8 * k, 0, HOVER + 1.55), 0.2, 'core'))
    body.append(orb('Heart', (0.0, 0, HOVER + 0.3), 0.35, 'glow', scale=(1.5, 1.0, 0.6)))
    return body, {}, 2500


UNITS = {
    'stinger': stinger, 'gorger': gorger, 'ferrier': ferrier, 'weaver': weaver, 'seer': seer, 'glider': glider,
    'disc': disc, 'dropper': dropper, 'carapace': carapace, 'spitter': spitter, 'mortar_beast': mortar_beast,
    'thornmound_packed': lambda: seed('thorn'), 'spore_tower_packed': lambda: seed('spore'),
}
AIR = {'glider': 3.0, 'disc': 3.0, 'dropper': 3.5}


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    atlas_dir, out_dir, which = args[0], args[1], args[2]
    render_dir = args[3] if len(args) > 3 else None
    names = list(UNITS) if which == 'all' else which.split(',')
    report = []
    for name in names:
        kit.begin('kesh', atlas_dir)
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
        print('UNIT %-20s %5d / %d' % r)
