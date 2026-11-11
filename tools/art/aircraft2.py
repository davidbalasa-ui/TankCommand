"""Aircraft redesign (David's picks from the sketch round, 2026-11-11).

  hornet   Terran fighter: the Hornet's armoured spine and four floating wings (front pair jagged and
           raked forward, rear pair swept back) with the Trident's three-prong nose around a floating
           energy core and a ring engine. Unmanned: a sensor eye, no cockpit.
  hammer   Terran bomber: the Hammerhead. Long armoured spine, a wide hammer-shaped sensor head,
           jagged canards under the head, a broad swept rear wing with two rotary bomb drums.
  halo     Kesh fighter: the Halo blade's open ring hull and forked spike cannon, with the Moth's core
           (two lens halves held apart by three floating gold rings). Scythe blades around the ring.

2,300-2,500 triangles each; one material with baked 512 base / normal / ORM / emissive maps.

  python aircraft2.py <out_dir> <hornet|hammer|halo|all> [render_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import hero  # noqa: E402
from hero_units import mirror, placed, preview, tilt  # noqa: E402
from kit import box, cyl, lathe, loft, orb, plate, prism  # noqa: E402


def ring_x(name, cx, cy, cz, r, tube, sides, tile, flat=1.0):
    """A torus whose axis runs along X (an engine ring or a floating band)."""
    prof = [(r - tube, 0.0), (r, -tube * flat), (r + tube, 0.0), (r, tube * flat), (r - tube, 0.0)]
    o = lathe(name, prof, sides, tile, smooth=True)
    o = tilt(o, ry=90)
    o.location = (cx, cy, cz)
    kit._apply(o)
    return o


def sector(name, r0, r1, a0, a1, z0, z1, tile, seg=8, bevel=0.0):
    """Annular sector seen from above (angles in degrees, 0 = nose), extruded z0..z1."""
    outer = [(r1 * math.cos(math.radians(a0 + (a1 - a0) * i / seg)), r1 * math.sin(math.radians(a0 + (a1 - a0) * i / seg)))
             for i in range(seg + 1)]
    inner = [(r0 * math.cos(math.radians(a1 - (a1 - a0) * i / seg)), r0 * math.sin(math.radians(a1 - (a1 - a0) * i / seg)))
             for i in range(seg + 1)]
    return plate(name, outer + inner, z0, z1, tile, bevel=bevel)


def saw(p0, p1, teeth, depth):
    """Sawtooth edge from p0 to p1: each tooth pushes `depth` along +X."""
    out = []
    for i in range(teeth * 2 + 1):
        t = i / (teeth * 2)
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        if i % 2 == 1:
            x += depth
        out.append((x, y))
    return out


def side(outline, s):
    """Mirror a left-side (+Y) outline to side s, keeping counter-clockwise order."""
    return outline if s > 0 else mirror(outline)


# ---------------------------------------------------------------- Terran fighter
def hornet():
    Z = 0.9
    p = []
    # Armoured spine: chined, hexagonal in section, ends in the ring engine.
    spine = [(-3.9, 0.36, Z + 0.32, Z - 0.28, Z), (-3.3, 0.52, Z + 0.46, Z - 0.36, Z), (-1.6, 0.62, Z + 0.56, Z - 0.4, Z + 0.02),
             (0.2, 0.62, Z + 0.54, Z - 0.38, Z + 0.02), (1.2, 0.5, Z + 0.42, Z - 0.32, Z), (1.6, 0.3, Z + 0.26, Z - 0.22, Z)]
    p.append(loft('Spine', spine, 12, 'hull', smooth=False))
    # Dorsal armour plates with a data strip, ventral keel.
    for k, (x0, x1) in enumerate(((-3.2, -2.2), (-2.0, -1.0), (-0.8, 0.4))):
        p.append(plate(f'Plate{k}', [(x0, -0.4), (x1, -0.34), (x1 + 0.12, 0.0), (x1, 0.34), (x0, 0.4)], Z + 0.48, Z + 0.62, 'turret', bevel=0.04))
    p.append(box('DataStrip', (-1.4, 0, Z + 0.63), (1.7, 0.035, 0.012), 'glow'))
    p.append(prism('Keel', [(-3.0, Z - 0.3), (0.6, Z - 0.3), (0.2, Z - 0.62), (-2.6, Z - 0.66)], -0.08, 0.08, 'dark', bevel=0.02))
    # Trident nose: three armoured prongs around a floating energy core.
    for k, (y, tip, w) in enumerate(((0.0, 5.2, 0.24), (0.62, 4.1, 0.2), (-0.62, 4.1, 0.2))):
        z = Z + (0.05 if k == 0 else -0.04)
        p.append(loft(f'Prong{k}', [(1.0, w * 0.9, z + w, z - w * 0.9, z), (2.4, w, z + w, z - w, z),
                                    (3.4, w * 0.8, z + w * 0.8, z - w * 0.8, z), (tip, 0.02, z + 0.03, z - 0.03, z)],
                      8, 'turret', smooth=False, cy=y))
        p.append(placed(box(f'ProngGlow{k}', (0, 0, 0), (0.7, 0.025, 0.012), 'glow'), 0, (2.7, y, z + w + 0.005)))
    p.append(orb('Core', (2.15, 0, Z + 0.02), 0.36, 'glow', seg=(12, 8)))
    p.append(ring_x('CoreBand', 2.15, 0, Z + 0.02, 0.5, 0.05, 14, 'barrel'))
    p.append(orb('Eye', (4.75, 0, Z + 0.2), 0.11, 'glow', seg=(8, 6)))
    for s in (1, -1):
        # Laser emitters at the side prong tips.
        p.append(cyl(f'Emitter{s}', (3.6, s * 0.62, Z - 0.04), (4.4, s * 0.62, Z - 0.04), 0.06, 6, 'barrel'))
        p.append(orb(f'EmitterGlow{s}', (4.42, s * 0.62, Z - 0.04), 0.06, 'glow', seg=(6, 4)))
        # Front wing: raked forward with a sawtooth leading edge, floating off the spine.
        front = [(-0.3, 0.8)] + saw((0.5, 0.82), (1.6, 3.1), 3, 0.28)[0:] + [(1.2, 3.25), (0.85, 3.2), (-0.55, 0.95)]
        p.append(tilt(plate(f'FrontWing{s}', side(front, s), Z - 0.02, Z + 0.1, 'hull', bevel=0.035), rx=-s * 6, about=(0, s * 0.8, Z)))
        p.append(plate(f'FrontArmour{s}', side([(-0.1, 1.0), (0.6, 1.05), (1.0, 2.2), (0.5, 2.2)], s), Z + 0.1, Z + 0.17, 'turret', bevel=0.02))
        p.append(placed(box(f'FrontEdge{s}', (0, 0, 0), (1.05, 0.03, 0.02), 'glow'), s * 64, (1.15, s * 1.95, Z + 0.11)))
        # Rear wing: swept back, set lower, also floating.
        rear = [(-1.0, 0.85), (-0.6, 0.85), (-2.4, 3.4), (-3.0, 3.35), (-2.5, 0.85)]
        p.append(tilt(plate(f'RearWing{s}', side(rear, s), Z - 0.2, Z - 0.08, 'hull', bevel=0.035), rx=s * 8, about=(0, s * 0.85, Z - 0.14)))
        p.append(plate(f'RearArmour{s}', side([(-1.0, 1.0), (-1.3, 2.0), (-1.9, 2.0), (-2.2, 1.0)], s), Z - 0.08 + 0.04 * s * 0, Z - 0.01, 'turret', bevel=0.02))
        p.append(placed(box(f'RearEdge{s}', (0, 0, 0), (1.3, 0.03, 0.02), 'glow'), -s * 55, (-1.55, s * 2.1, Z - 0.07)))
        # Glowing pylons bridging the gap between spine and wings.
        p.append(box(f'PylonF{s}', (0.15, s * 0.7, Z + 0.04), (0.35, 0.12, 0.035), 'glow'))
        p.append(box(f'PylonR{s}', (-1.6, s * 0.7, Z - 0.13), (0.5, 0.12, 0.035), 'glow'))
        # Wingtip laser cannons and nav lights.
        p.append(box(f'TipPod{s}', (1.05, s * 3.25, Z + 0.04), (0.5, 0.08, 0.08), 'dark', bevel=0.02))
        p.append(cyl(f'TipGun{s}', (1.5, s * 3.25, Z + 0.04), (2.2, s * 3.25, Z + 0.04), 0.045, 6, 'barrel'))
        p.append(box(f'TipLight{s}', (-2.75, s * 3.38, Z - 0.13), (0.14, 0.04, 0.04), 'amber'))
        # Ventral canted fins.
        fin = prism(f'Fin{s}', [(-3.6, 0.0), (-2.4, 0.0), (-3.0, -0.8), (-3.6, -0.75)], -0.04, 0.04, 'dark', bevel=0.015)
        fin.location = (0, s * 0.42, Z - 0.3)
        kit._apply(fin)
        p.append(tilt(fin, rx=s * 28, about=(0, s * 0.42, Z - 0.3)))
        # Ring engine struts.
        p.append(box(f'StrutH{s}', (-4.05, s * 0.55, Z), (0.35, 0.2, 0.05), 'turret', bevel=0.015))
        p.append(box(f'StrutV{s}', (-4.05, 0, Z + s * 0.55), (0.35, 0.05, 0.2), 'turret', bevel=0.015))
    # Ring engine: armoured outer ring, cyan drive ring inside, a nozzle cone on the spine.
    p.append(ring_x('Ring', -4.25, 0, Z, 0.82, 0.13, 20, 'turret', flat=1.6))
    p.append(ring_x('Drive', -4.3, 0, Z, 0.62, 0.05, 20, 'glow'))
    p.append(cyl('Nozzle', (-3.85, 0, Z), (-4.6, 0, Z), 0.34, 12, 'barrel', r1=0.18, caps=False))
    p.append(cyl('Burner', (-4.45, 0, Z), (-4.55, 0, Z), 0.22, 12, 'glow'))
    return p


# ---------------------------------------------------------------- Terran bomber
def hammer():
    Z = 1.0
    p = []
    spine = [(-4.6, 0.4, Z + 0.38, Z - 0.32, Z), (-3.6, 0.62, Z + 0.56, Z - 0.46, Z), (-1.0, 0.72, Z + 0.62, Z - 0.52, Z + 0.02),
             (1.6, 0.62, Z + 0.52, Z - 0.44, Z + 0.02), (3.0, 0.48, Z + 0.4, Z - 0.34, Z)]
    p.append(loft('Spine', spine, 14, 'hull', smooth=False))
    for k, (x0, x1) in enumerate(((-3.8, -2.6), (-2.4, -1.2), (-1.0, 0.2), (0.4, 1.6))):
        p.append(plate(f'Plate{k}', [(x0, -0.5), (x1, -0.44), (x1 + 0.12, 0.0), (x1, 0.44), (x0, 0.5)], Z + 0.54, Z + 0.68, 'turret', bevel=0.04))
    p.append(box('DataStrip', (-1.2, 0, Z + 0.69), (2.6, 0.035, 0.012), 'glow'))
    # The hammer head: a wide armoured bar with a sensor strip across its face and eye pods.
    head = [(3.0, 0.0), (3.1, -2.3), (3.55, -2.5), (4.3, -2.2), (4.55, -0.5), (4.75, 0.0), (4.55, 0.5), (4.3, 2.2), (3.55, 2.5), (3.1, 2.3)]
    p.append(plate('Head', head[::-1], Z - 0.2, Z + 0.28, 'turret', bevel=0.06))
    p.append(plate('HeadTop', [(3.3, 0.0), (3.35, -1.7), (4.1, -1.6), (4.3, 0.0), (4.1, 1.6), (3.35, 1.7)][::-1], Z + 0.28, Z + 0.4, 'hull', bevel=0.04))
    for s in (1, -1):
        p.append(placed(box(f'Sensor{s}', (0, 0, 0), (0.85, 0.035, 0.05), 'glow'), s * 84, (4.45, s * 1.25, Z + 0.05)))
        p.append(orb(f'EyePod{s}', (3.75, s * 2.45, Z + 0.04), 0.22, 'turret', seg=(10, 6)))
        p.append(orb(f'Eye{s}', (3.93, s * 2.47, Z + 0.06), 0.1, 'glow', seg=(8, 5)))
        # Jagged canards under the head, raked forward.
        can = [(2.2, 0.55)] + saw((2.5, 0.6), (2.9, 1.9), 2, 0.22) + [(2.5, 1.95), (1.9, 0.6)]
        p.append(plate(f'Canard{s}', side(can, s), Z - 0.42, Z - 0.34, 'hull', bevel=0.02))
        # Broad swept rear wing with raised armour and a lit leading edge.
        wing = [(-0.6, 0.6), (0.2, 0.6), (-2.6, 4.0), (-3.4, 4.0), (-3.2, 0.6)]
        p.append(plate(f'Wing{s}', side(wing, s), Z - 0.16, Z + 0.04, 'hull', bevel=0.045))
        p.append(plate(f'WingArmour{s}', side([(-0.6, 0.8), (-0.3, 0.8), (-1.9, 2.8), (-2.8, 2.8), (-2.8, 0.8)], s), Z + 0.04, Z + 0.12, 'turret', bevel=0.03))
        p.append(placed(box(f'WingEdge{s}', (0, 0, 0), (1.95, 0.035, 0.025), 'glow'), -s * 50, (-1.2, s * 2.3, Z + 0.05)))
        p.append(box(f'WingTip{s}', (-3.0, s * 4.02, Z - 0.06), (0.45, 0.06, 0.1), 'dark', bevel=0.02))
        p.append(box(f'NavLight{s}', (-3.0, s * 4.1, Z - 0.02), (0.15, 0.04, 0.04), 'amber'))
        # Rotary bomb drum under each wing: armoured drum, glowing feed ring, bomb noses.
        y = s * 1.9
        p.append(box(f'DrumPylon{s}', (-1.5, y, Z - 0.28), (0.8, 0.06, 0.14), 'dark', bevel=0.02))
        p.append(cyl(f'Drum{s}', (-2.8, y, Z - 0.66), (-0.4, y, Z - 0.66), 0.36, 12, 'turret'))
        p.append(cyl(f'DrumRing{s}', (-0.42, y, Z - 0.66), (-0.3, y, Z - 0.66), 0.3, 12, 'amber'))
        p.append(cyl(f'DrumBand{s}', (-1.7, y, Z - 0.66), (-1.5, y, Z - 0.66), 0.39, 12, 'dark'))
        for k in range(3):
            a = math.radians(90 + k * 120)
            yy, zz = y + 0.2 * math.cos(a), Z - 0.66 + 0.2 * math.sin(a)
            p.append(cyl(f'BombNose{s}{k}', (-0.3, yy, zz), (0.1, yy, zz), 0.08, 6, 'barrel', r1=0.01))
        # Twin engines at the tail with tails canted out.
        y = s * 0.62
        p.append(cyl(f'Engine{s}', (-3.2, y, Z + 0.1), (-4.9, y, Z + 0.1), 0.3, 12, 'turret'))
        p.append(cyl(f'Nozzle{s}', (-4.85, y, Z + 0.1), (-5.3, y, Z + 0.1), 0.3, 12, 'barrel', r1=0.24, caps=False))
        p.append(cyl(f'Burner{s}', (-5.15, y, Z + 0.1), (-5.25, y, Z + 0.1), 0.22, 12, 'glow'))
        fin = prism(f'Tail{s}', [(-4.8, 0.0), (-3.4, 0.0), (-4.2, 1.5), (-4.75, 1.5)], -0.05, 0.05, 'hull', bevel=0.02)
        fin.location = (0, s * 0.62, Z + 0.4)
        kit._apply(fin)
        p.append(tilt(fin, rx=-s * 30, about=(0, s * 0.62, Z + 0.4)))
    # Belly bomb bay doors.
    p.append(plate('Bay', [(-2.6, -0.4), (0.6, -0.4), (0.6, 0.4), (-2.6, 0.4)], Z - 0.56, Z - 0.5, 'dark', bevel=0.02))
    p.append(box('BayLight', (-1.0, 0, Z - 0.57), (1.4, 0.05, 0.01), 'amber'))
    return p


# ---------------------------------------------------------------- Kesh fighter
def halo():
    Z = 1.0
    p = []
    # Two ring halves (open fore and aft), each a layered etched band with a lower keel band.
    for s, (a0, a1) in ((1, (28, 152)), (-1, (-152, -28))):
        p.append(sector(f'Ring{s}', 2.3, 3.1, a0, a1, Z - 0.1, Z + 0.18, 'shell', seg=7, bevel=0.05))
        p.append(sector(f'RingCrest{s}', 2.5, 2.95, a0 + 6, a1 - 6, Z + 0.18, Z + 0.3, 'fin', seg=6))
        p.append(sector(f'RingKeel{s}', 2.45, 2.85, a0 + 10, a1 - 10, Z - 0.3, Z - 0.1, 'under', seg=6))
        p.append(sector(f'RingGlow{s}', 3.1, 3.16, a0 + 4, a1 - 4, Z + 0.0, Z + 0.06, 'glow', seg=6))
        # Moth core halves: lens plates either side of the open centre, joined to the ring by veins.
        half = [(-1.6, 0.42), (-1.1, 0.42), (1.1, 0.42), (1.6, 0.42), (1.9, 1.0), (1.4, 1.8), (0.0, 2.2), (-1.4, 1.8), (-1.9, 1.0)]
        p.append(plate(f'Half{s}', side(half, s), Z - 0.06, Z + 0.22, 'shell', bevel=0.05))
        p.append(plate(f'HalfCrest{s}', side([(-1.0, 0.6), (1.0, 0.6), (1.2, 1.1), (0.0, 1.55), (-1.2, 1.1)], s), Z + 0.22, Z + 0.32, 'fin', bevel=0.03))
        p.append(placed(box(f'HalfVein{s}', (0, 0, 0), (1.0, 0.025, 0.012), 'glow'), 0, (0.0, s * 1.0, Z + 0.325)))
        for k, a in enumerate((60, 90, 120)):
            ang = math.radians(a * s)
            p.append(placed(box(f'Bridge{s}{k}', (0, 0, 0), (0.18, 0.05, 0.05), 'fin', bevel=0.01), a * s,
                            (2.2 * math.cos(ang) * 1.0, 2.2 * math.sin(ang), Z + 0.08)))
        # Serrated lightning ports on the front of each half.
        teeth = [(1.55, 0.5)] + saw((1.75, 0.55), (1.95, 1.0), 2, 0.22) + [(1.7, 1.05)]
        p.append(plate(f'Teeth{s}', side(teeth, s), Z + 0.02, Z + 0.14, 'barrel', bevel=0.01))
        p.append(orb(f'Port{s}', (2.1, s * 0.78, Z + 0.08), 0.07, 'core', seg=(6, 4)))
        # Hover emitters under the halves.
        p.append(cyl(f'Hover{s}', (0.0, s * 1.2, Z - 0.06), (0.0, s * 1.2, Z - 0.3), 0.3, 8, 'under', r1=0.2))
        p.append(orb(f'HoverGlow{s}', (0.0, s * 1.2, Z - 0.31), 0.16, 'core', seg=(8, 4), scale=(1, 1, 0.4)))
    # Three floating gold rings bridge the open centre; an orb rides in the front one.
    for k, x in enumerate((-1.0, 0.0, 1.0)):
        p.append(ring_x(f'Band{k}', x, 0, Z + 0.1, 0.34, 0.06, 12, 'barrel'))
    p.append(orb('Orb', (1.0, 0, Z + 0.1), 0.2, 'core', seg=(10, 6)))
    p.append(cyl('Spindle', (-1.4, 0, Z + 0.1), (1.4, 0, Z + 0.1), 0.05, 6, 'glow'))
    # Forked spike cannon on the nose, with jagged prongs and a lightning port.
    spike = [(1.7, -0.12), (2.6, -0.4), (2.45, -0.2), (3.45, -0.32), (3.05, -0.06), (3.7, 0.0), (3.05, 0.06), (3.45, 0.32), (2.45, 0.2), (2.6, 0.4), (1.7, 0.12)]
    p.append(plate('Spike', spike, Z + 0.02, Z + 0.2, 'fin', bevel=0.03))
    p.append(orb('SpikePort', (3.35, 0, Z + 0.11), 0.09, 'core', seg=(8, 5)))
    p.append(placed(box('SpikeVein', (0, 0, 0), (0.6, 0.02, 0.01), 'glow'), 0, (2.5, 0, Z + 0.205)))
    # Scythe blades held around the ring: front and back pair solid (they sweep and fade in game).
    for k, a in enumerate((0, 180, 40, 220)):
        pts_o, pts_i = [], []
        n = 7
        for i in range(n):
            t = i / (n - 1)
            ang = math.radians(a - 32 + 64 * t)
            w = 0.05 + 0.32 * math.sin(math.pi * t ** 0.8)
            pts_o.append((3.6 * math.cos(ang), 3.6 * math.sin(ang)))
            pts_i.append(((3.6 - w) * math.cos(ang), (3.6 - w) * math.sin(ang)))
        outline = pts_o + pts_i[::-1]
        b = plate(f'Scythe{k}', outline, Z + 0.0, Z + 0.07, 'fin')
        p.append(tilt(b, rx=0, ry=0))
        mid = math.radians(a)
        p.append(placed(box(f'ScytheEdge{k}', (0, 0, 0), (0.9, 0.022, 0.012), 'glow'), a + 90, (3.62 * math.cos(mid), 3.62 * math.sin(mid), Z + 0.075)))
    return p


UNITS = {'hornet': ('terran', hornet, 'TerranHornet'), 'hammer': ('terran', hammer, 'TerranHammerhead'),
         'halo': ('kesh', halo, 'KeshHalo')}


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out_dir, which = args[0], args[1]
    render_dir = args[2] if len(args) > 2 else None
    names = list(UNITS) if which == 'all' else which.split(',')
    for name in names:
        faction, fn, title = UNITS[name]
        hero.begin(faction)
        parts = fn()
        count = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in parts)
        print('PRE-BAKE TRIANGLES', name, count)
        if os.environ.get('COUNT_ONLY'):
            continue
        obj = hero.bake_unit(title, parts, f'{out_dir}/{name}.glb', f'{out_dir}/tex_{name}', size=512)
        print('TRIANGLES', name, hero.tri_count(obj))
        hero.export(obj, f'{out_dir}/{name}.glb')
        if render_dir:
            preview(obj, render_dir, name, faction)
