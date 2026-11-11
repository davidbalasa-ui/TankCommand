"""Landing pads, second pass: the Terran pad and the Kesh nest rebuilt with the hero bake method.

The first versions (structures_set.py) were 43 and 20 plain parts on the shared flat atlas. These
are built from many more shaped parts (layered decks, buttresses, grilles, tower, tanks, crane,
masts, crates for the Terrans; a layered etched bowl, floating petals, hovering rings and orbs for
the Kesh), then baked with hero.py's procedural panel / etched shaders into one 512 texture set.

Layout is unchanged, because the game relies on it: 12 x 12 units, exit ramp on +X, cargo lift on
-Y about 0.62 of the half size out, landing circle in the middle.

  python pads_hero.py <out_dir> <terran|kesh|all> [render_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import hero  # noqa: E402
from kit import box, cyl, lathe, lens, loft, orb, plate, prism  # noqa: E402
from kesh_set import arc_fin, ring  # noqa: E402

H = 6.0  # half size
LY = -H * 0.62  # cargo lift centre (y)
CIRCLE_SCALE = 0.84  # Terran landing circle: 3.85 -> about 3.2 across the rim
CIRCLE_Y = 0.55


def chamfer_square(half, c):
    return [(-half + c, -half), (half - c, -half), (half, -half + c), (half, half - c),
            (half - c, half), (-half + c, half), (-half, half - c), (-half, -half + c)]


def octagon(r, cx=0.0, cy=0.0, rot=math.pi / 8):
    return [(cx + r * math.cos(rot + k * math.pi / 4), cy + r * math.sin(rot + k * math.pi / 4)) for k in range(8)]


# ---------------------------------------------------------------- Terran landing pad
def terran_pad():
    p = []
    R0 = 2.6  # ramp half width
    # Plinth: a wide dark base with sloped armoured sides, open at +X for the ramp.
    p.append(plate('Plinth', [(-5.2, -6.0), (3.4, -6.0), (3.4, 6.0), (-5.2, 6.0), (-6.0, 5.2), (-6.0, -5.2)], 0.0, 0.32, 'dark', bevel=0.05))
    p.append(plate('PlinthR', [(3.4, R0 + 0.35), (6.0, R0 + 0.35), (6.0, 5.2), (5.2, 6.0), (3.4, 6.0)], 0.0, 0.32, 'dark', bevel=0.05))
    p.append(plate('PlinthL', [(3.4, -6.0), (5.2, -6.0), (6.0, -5.2), (6.0, -R0 - 0.35), (3.4, -R0 - 0.35)], 0.0, 0.32, 'dark', bevel=0.05))
    # Upper deck tier, set in from the plinth edge so the step catches light.
    p.append(plate('Tier', [(-4.9, -5.6), (3.4, -5.6), (3.4, 5.6), (-4.9, 5.6), (-5.6, 4.9), (-5.6, -4.9)], 0.32, 0.58, 'hull', bevel=0.06))
    p.append(plate('TierR', [(3.4, R0 + 0.35), (5.6, R0 + 0.35), (5.6, 4.9), (4.9, 5.6), (3.4, 5.6)], 0.32, 0.58, 'hull', bevel=0.06))
    p.append(plate('TierL', [(3.4, -5.6), (4.9, -5.6), (5.6, -4.9), (5.6, -R0 - 0.35), (3.4, -R0 - 0.35)], 0.32, 0.58, 'hull', bevel=0.06))
    # Buttresses round the outside: sloped armour blocks between the plinth and the tier.
    for k, (x, y, ang) in enumerate(((-5.65, -2.6, 0), (-5.65, 2.6, 0), (-3.0, 5.65, 90), (1.2, 5.65, 90),
                                     (-3.0, -5.65, -90), (1.2, -5.65, -90), (5.65, 4.2, 180), (5.65, -4.2, 180))):
        b = prism(f'Buttress{k}', [(-0.35, 0.0), (0.35, 0.0), (0.2, 0.62), (-0.1, 0.62)], -0.55, 0.55, 'turret', bevel=0.04)
        b.rotation_euler = (0, 0, math.radians(ang + 90))
        b.location = (x, y, 0)
        kit._apply(b)
        p.append(b)
        p.append(box(f'ButtLamp{k}', (x * 1.06 if abs(x) > 5 else x, y * 1.06 if abs(y) > 5 else y, 0.45), (0.06, 0.06, 0.04), 'amber'))
    # Edge light strips on the tier face.
    for k, (c, s) in enumerate((((-5.62, 0, 0.47), (0.02, 1.2, 0.03)), ((-1.0, 5.62, 0.47), (1.6, 0.02, 0.03)),
                                ((-1.0, -5.62, 0.47), (1.6, 0.02, 0.03)))):
        p.append(box(f'EdgeGlow{k}', c, s, 'glow'))

    # Landing circle: stepped round deck with a recessed dark centre. Built at full size, then
    # shrunk and nudged toward +Y so it clears the cargo lift well on -Y.
    circ = []
    circ.append(lathe('Deck', [(3.85, 0.58), (3.85, 0.72), (3.65, 0.8), (3.2, 0.8), (3.1, 0.74), (0.0, 0.74)], 32, 'turret',
                   smooth=False))
    circ.append(lathe('DeckInner', [(3.0, 0.745), (0.0, 0.745)], 32, 'hull', smooth=False))
    circ.append(lathe('RingGlow', [(3.28, 0.805), (3.5, 0.805)], 32, 'glow', smooth=False))
    # Hazard band: alternating amber / dark segments just inside the rim.
    for k in range(24):
        a = 360 / 24 * k
        seg = box(f'Hazard{k}', (2.85, 0, 0.755), (0.18, 0.28, 0.008), 'amber' if k % 2 == 0 else 'dark')
        circ.append(kit.rot_z(seg, a))
    # Touchdown marks: four corner brackets and a centre emblem (chevron in a ring).
    for k in range(4):
        a = 45 + 90 * k
        circ.append(kit.rot_z(box(f'MarkA{k}', (1.9, 0.35, 0.752), (0.4, 0.06, 0.006), 'glow'), a))
        circ.append(kit.rot_z(box(f'MarkB{k}', (1.55, 0.0, 0.752), (0.06, 0.4, 0.006), 'glow'), a))
    circ.append(lathe('Emblem', [(0.95, 0.752), (1.08, 0.752)], 24, 'amber', smooth=False))
    circ.append(plate('Chevron', [(-0.35, -0.55), (0.55, 0.0), (-0.35, 0.55), (-0.1, 0.0)], 0.748, 0.758, 'amber'))
    for o in circ:
        o.scale = (CIRCLE_SCALE, CIRCLE_SCALE, 1.0)
        o.location = (0.0, CIRCLE_Y, 0.0)
        kit._apply(o)
    p += circ
    # Deck vents in the four corners outside the circle: dark wells with slats.
    for k, (x, y) in enumerate(((4.3, 4.3), (-1.9, 4.75))):
        p.append(plate(f'Vent{k}', octagon(0.75, x, y), 0.56, 0.6, 'dark'))
        for s in range(4):
            p.append(box(f'Slat{k}{s}', (x, y - 0.45 + 0.3 * s, 0.6), (0.55, 0.05, 0.03), 'barrel'))

    # Exit ramp on +X with treads, rails and lit chevrons.
    p.append(prism('Ramp', [(3.4, 0.0), (6.05, 0.0), (6.05, 0.06), (3.4, 0.82)], -R0, R0, 'hull', bevel=0.03))
    for k in range(5):
        x = 3.75 + k * 0.48
        z = 0.82 - (x - 3.4) / (6.05 - 3.4) * 0.76 + 0.02
        p.append(box(f'Tread{k}', (x, 0, z), (0.05, R0 - 0.25, 0.025), 'dark'))
    for side in (-1, 1):
        y = side * (R0 + 0.18)
        p.append(prism(f'Rail{side}', [(3.3, 0.0), (6.0, 0.0), (6.0, 0.32), (3.3, 1.08)], y - 0.17, y + 0.17, 'turret', bevel=0.04))
        p.append(prism(f'RailGlow{side}', [(3.4, 1.06), (5.9, 0.3), (5.9, 0.36), (3.4, 1.12)], y - 0.07, y + 0.07, 'glow'))
    for k in range(2):
        x = 4.1 + k * 0.95
        z = 0.82 - (x + 0.3 - 3.4) / (6.05 - 3.4) * 0.76 + 0.035
        p.append(plate(f'RampArrow{k}', [(x, -0.9), (x + 0.6, 0.0), (x, 0.9), (x + 0.25, 0.0)], z, z + 0.03, 'amber'))

    # Cargo lift on -Y: a recessed well framed in hazard stripes, platform inside, crane over it.
    p.append(plate('LiftWell', [(-1.45, LY - 1.45), (1.45, LY - 1.45), (1.45, LY + 0.95), (-1.45, LY + 0.95)], 0.5, 0.6, 'dark'))
    for k in range(10):
        x = -1.35 + k * 0.3
        p.append(box(f'LiftStripeN{k}', (x + 0.15, LY + 0.87, 0.6), (0.14, 0.08, 0.012), 'amber' if k % 2 == 0 else 'dark'))
        p.append(box(f'LiftStripeS{k}', (x + 0.15, LY - 1.37, 0.6), (0.14, 0.08, 0.012), 'amber' if k % 2 else 'dark'))
    p.append(plate('LiftDeck', [(-1.1, LY - 1.15), (1.1, LY - 1.15), (1.1, LY + 0.7), (-1.1, LY + 0.7)], 0.5, 0.64, 'turret', bevel=0.03))
    for k in range(3):
        p.append(box(f'LiftRib{k}', (-0.6 + 0.6 * k, LY - 0.17, 0.655), (0.04, 0.85, 0.015), 'barrel'))
    p.append(box('LiftGlow', (0, LY + 0.62, 0.66), (0.95, 0.04, 0.008), 'glow'))
    for side in (-1, 1):
        x = side * 1.7
        p.append(box(f'CranePost{side}', (x, LY - 0.2, 1.7), (0.17, 0.2, 1.1), 'turret', bevel=0.04, taper=0.8))
        p.append(box(f'CraneFoot{side}', (x, LY - 0.2, 0.68), (0.3, 0.32, 0.1), 'dark', bevel=0.03))
        p.append(box(f'CraneLamp{side}', (x, LY - 0.42, 2.55), (0.1, 0.03, 0.06), 'amber'))
    p.append(box('CraneBeam', (0, LY - 0.2, 2.86), (1.95, 0.22, 0.14), 'hull', bevel=0.04))
    p.append(box('CraneBeamTop', (0, LY - 0.2, 3.03), (1.6, 0.12, 0.04), 'dark'))
    p.append(box('Trolley', (0.2, LY - 0.2, 2.62), (0.32, 0.28, 0.12), 'turret', bevel=0.03))
    for side in (-1, 1):
        p.append(cyl(f'Cable{side}', (0.2 + side * 0.15, LY - 0.2, 2.5), (0.2 + side * 0.15, LY - 0.2, 1.75), 0.02, 4, 'dark'))
    p.append(box('Hook', (0.2, LY - 0.2, 1.68), (0.3, 0.12, 0.08), 'amber'))

    # Control tower on the back-left corner: base block, tapered cab with a lit window band,
    # roof sensor and mast.
    tx, ty = -4.55, 4.3
    p.append(box('TowerBase', (tx, ty, 1.35), (0.75, 0.75, 0.8), 'hull', bevel=0.05, taper=0.88))
    p.append(lathe('TowerCab', [(0.95, 2.15), (1.1, 2.45), (1.1, 2.95), (0.85, 3.2)], 8, 'turret', center=(tx, ty, 0),
                   smooth=False, top=3.22))
    p.append(lathe('TowerGlass', [(1.115, 2.55), (1.115, 2.85)], 8, 'canopy', center=(tx, ty, 0), smooth=False))
    p.append(cyl('TowerMast', (tx, ty, 3.2), (tx, ty, 4.4), 0.04, 4, 'dark'))
    p.append(box('TowerMastTip', (tx, ty, 4.42), (0.06, 0.06, 0.05), 'amber'))
    p.append(lathe('TowerDish', [(0.05, 3.3), (0.42, 3.42), (0.48, 3.5)], 10, 'barrel', center=(tx + 0.55, ty - 0.3, 0), smooth=False))
    p.append(box('TowerDoor', (tx + 0.76, ty, 0.95), (0.02, 0.3, 0.38), 'dark'))

    # Fuel tanks on the back-right corner, banded, with a pipe run to the deck.
    for k, y in enumerate((-3.5, -4.6)):
        p.append(cyl(f'Tank{k}', (-5.3, y, 1.05), (-3.1, y, 1.05), 0.48, 12, 'barrel', smooth=True))
        p.append(lathe(f'TankCapA{k}', [(0.48, 0), (0.3, 0.25), (0.0, 0.3)], 12, 'barrel', center=(0, 0, 0)))
        cap = p[-1]
        cap.rotation_euler = (0, math.radians(90), 0)
        cap.location = (-3.1, y, 1.05)
        kit._apply(cap)
        for b in range(2):
            x = -4.8 + b * 1.2
            p.append(cyl(f'TankBand{k}{b}', (x, y, 1.05), (x + 0.14, y, 1.05), 0.5, 12, 'dark'))
        p.append(box(f'TankCradle{k}', (-4.2, y, 0.7), (0.9, 0.22, 0.14), 'dark', bevel=0.03))
    p.append(cyl('Pipe', (-3.0, -4.05, 0.8), (-2.2, -4.05, 0.8), 0.09, 6, 'dark'))
    p.append(cyl('PipeUp', (-2.2, -4.05, 0.8), (-2.2, -3.2, 0.62), 0.09, 6, 'dark'))

    # Floodlight masts on three corners, heads turned in toward the circle.
    for k, (x, y) in enumerate(((5.0, 5.0), (5.0, -5.0), (-5.15, -5.15))):
        p.append(cyl(f'Mast{k}', (x, y, 0.58), (x, y, 3.0), 0.09, 6, 'turret', r1=0.06))
        head = box(f'Lamp{k}', (0, 0, 0), (0.22, 0.32, 0.1), 'dark', bevel=0.02)
        face = box(f'LampFace{k}', (0.225, 0, 0), (0.005, 0.27, 0.07), 'amber')
        for o in (head, face):
            o.rotation_euler = (0, math.radians(30), math.atan2(-y, -x))
            o.location = (x, y, 3.05)
            kit._apply(o)
            p.append(o)

    # Cargo crates stacked beside the lift, ready to go.
    for k, (x, y, z) in enumerate(((2.6, -4.6, 0.58), (3.55, -4.6, 0.58), (3.05, -4.6, 1.26))):
        p.append(box(f'Crate{k}', (x, y, z + 0.34), (0.44, 0.5, 0.34), 'hull', bevel=0.04))
        p.append(box(f'CrateBand{k}', (x, y, z + 0.34), (0.45, 0.51, 0.06), 'amber'))
    return p


# ---------------------------------------------------------------- Kesh landing nest
def kesh_nest():
    p = []
    # Etched base: three stacked discs, each a little smaller, like grown layers.
    p.append(lathe('BaseLow', [(5.9, 0.0), (6.0, 0.12), (5.85, 0.24), (5.5, 0.3)], 24, 'under', smooth=True, bottom=0.0))
    p.append(lathe('BaseMid', [(5.5, 0.28), (5.4, 0.38), (5.0, 0.42)], 24, 'dark', smooth=True))
    # The bowl: a shallow curved dish, rim lip, sloping into a ring trench round the heart.
    p.append(lathe('Bowl', [(5.0, 0.42), (5.05, 0.62), (4.85, 0.8), (4.4, 0.78), (3.6, 0.62), (3.1, 0.55),
                            (2.95, 0.5), (1.4, 0.5), (1.2, 0.56)], 24, 'shell', smooth=True))
    p.append(lathe('Floor', [(1.2, 0.56), (0.0, 0.58)], 24, 'fin', smooth=True))
    # Gold veins etched into the bowl: a ring and radial spokes.
    p.append(ring('GoldRing', (0, 0, 0.53), 3.02, 0.07, sides=24, tube=4, tile='glow'))
    p.append(ring('GoldRingIn', (0, 0, 0.57), 1.28, 0.05, sides=24, tube=4, tile='glow'))
    for k in range(12):
        a = 30 * k + 15
        if 60 < a < 120 or a > 340 or a < 20:  # leave the cradle side and the mouth clear
            continue
        p.append(kit.rot_z(box(f'Spoke{k}', (2.2, 0, 0.515), (0.75, 0.03, 0.02), 'glow'), a))
    # The heart: a glowing core under a floating etched crown.
    p.append(orb('Heart', (0, 0, 0.62), 0.6, 'core', seg=(16, 8), scale=(1, 1, 0.4)))
    p.append(ring('Crown', (0, 0, 1.45), 0.9, 0.09, sides=24, tube=5, tile='fin'))
    for k in range(6):
        a = math.radians(60 * k)
        p.append(orb(f'CrownBead{k}', (0.9 * math.cos(a), 0.9 * math.sin(a), 1.45), 0.11, 'core', seg=(8, 5)))

    # Exit tongue on +X: a smooth sloping lip with glowing veins.
    p.append(prism('Tongue', [(3.4, 0.0), (6.1, 0.0), (6.1, 0.08), (3.6, 0.68)], -2.4, 2.4, 'shell', bevel=0.14, taper=0.8))
    for side in (-1, 1):
        p.append(cyl(f'TongueVein{side}', (3.7, side * 1.6, 0.6), (5.8, side * 1.7, 0.1), 0.06, 6, 'glow'))
    for k in range(3):
        x = 4.2 + 0.55 * k
        z = 0.68 - (x - 3.6) / 2.5 * 0.6 + 0.02
        p.append(kit.rot_z(arc_fin(f'TongueRib{k}', x, z, 0.9, 200, 340, 0.08, 0.05, tile='fin', flat=True, y=0.0), 0))

    # Petal centres sit at radius PR so the tips stay inside the 12 x 12 footprint (the game sizes
    # the model by its width, so anything sticking out would shrink the whole nest).
    PR = 4.45
    # Floating petals: broad leaf blades round the rim, tipped up and out like an opening flower,
    # leaving the mouth (+X) and the cradle side (-Y) open. Each hangs free above the rim with a
    # gold vein along its spine and a glowing seed at its tip.
    for k, a in enumerate((67.5, 112.5, 157.5, 202.5, 247.5)):
        for o in (loft(f'Petal{k}', lens(-1.7, 1.9, 0.85, 0.16, -0.1, 0.0, n=8, nose=0.8), 8, 'fin'),
                  box(f'PetalVein{k}', (0.1, 0.0, 0.15), (1.5, 0.035, 0.02), 'glow')):
            o.rotation_euler = (0, math.radians(-32), math.radians(a))
            o.location = (PR * math.cos(math.radians(a)), PR * math.sin(math.radians(a)), 1.6)
            kit._apply(o)
            p.append(o)
        ta = math.radians(a)
        tip = PR + 1.9 * math.cos(math.radians(32))
        p.append(orb(f'Seed{k}', (tip * math.cos(ta), tip * math.sin(ta), 1.6 + 1.9 * math.sin(math.radians(32)) + 0.1),
                     0.14, 'core', seg=(8, 5)))
        # A smaller inner petal between each pair, lower and closer in.
        if k < 4:
            b = math.radians(a + 22.5)
            o = loft(f'PetalIn{k}', lens(-1.0, 1.2, 0.5, 0.1, -0.06, 0.0, n=7, nose=0.8), 8, 'shell')
            o.rotation_euler = (0, math.radians(-22), b)
            o.location = (4.2 * math.cos(b), 4.2 * math.sin(b), 1.15)
            kit._apply(o)
            p.append(o)

    # Hovering halo high over the nest: where deliveries come down.
    p.append(ring('Halo', (0, 0, 4.2), 2.2, 0.08, sides=28, tube=4, tile='fin'))
    p.append(ring('HaloGlow', (0, 0, 4.2), 2.2, 0.035, sides=28, tube=3, tile='glow'))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        p.append(orb(f'HaloBead{k}', (2.2 * math.cos(a), 2.2 * math.sin(a), 4.2), 0.16, 'core', seg=(8, 5)))

    # Cargo cradle on -Y: a floating ring over a glowing pool, held by three hovering claws.
    p.append(lathe('PoolRim', [(1.45, 0.55), (1.55, 0.88), (1.3, 0.98)], 20, 'shell', center=(0, LY, 0)))
    p.append(lathe('Pool', [(1.3, 0.94), (0.0, 0.97)], 20, 'glow', center=(0, LY, 0), smooth=False))
    p.append(ring('CradleRing', (0, LY, 2.25), 1.15, 0.11, sides=24, tube=5, tile='fin'))
    for k in range(3):
        a = math.radians(90 + k * 120)
        cx, cy = 1.4 * math.cos(a), LY + 1.4 * math.sin(a)
        claw = arc_fin(f'Claw{k}', 0.0, 0.0, 1.35, 210, 150, 0.34, 0.1, tile='shell', n=10)
        claw.location = (cx, cy, 1.55)
        kit._apply(claw)
        p.append(kit.rot_z(claw, math.degrees(a) + 180, about=(cx, cy, 1.55)))
        p.append(orb(f'ClawBead{k}', (cx, cy, 1.25), 0.13, 'core', seg=(8, 5)))
    return p


PADS = {
    'terran_landing_pad': ('terran', terran_pad, 'TerranLandingPad'),
    'kesh_landing_nest': ('kesh', kesh_nest, 'KeshLandingNest'),
}


def preview(obj, render_dir, stem, faction):
    kit.S['meshes'] = [obj]
    kit.S['root'] = obj
    kit.S['cfg'] = kit.FACTIONS[faction]
    kit.preview(render_dir, stem, samples=int(os.environ.get('SAMPLES', '32')),
                res=tuple(int(v) for v in os.environ.get('RES', '1200x750').split('x')),
                views=tuple(os.environ.get('VIEWS', 'front34,rts').split(',')))


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out_dir, which = args[0], args[1]
    render_dir = args[2] if len(args) > 2 else None
    names = list(PADS) if which == 'all' else [n for n in PADS if which in n]
    for name in names:
        faction, fn, title = PADS[name]
        hero.begin(faction)
        parts = fn()
        count = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in parts)
        print('PRE-BAKE', name, 'parts', len(parts), 'triangles', count)
        if os.environ.get('COUNT_ONLY'):
            continue
        obj = hero.bake_unit(title, parts, f'{out_dir}/{name}.glb', f'{out_dir}/tex', size=512)
        print('TRIANGLES', name, hero.tri_count(obj))
        hero.export(obj, f'{out_dir}/{name}.glb')
        if render_dir:
            preview(obj, render_dir, name, faction)
