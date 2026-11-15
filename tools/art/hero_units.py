"""Hero-pass units (art competition round): Terran Falcon fighter and Kesh Disc saucer.

2,300-2,500 triangles each, spread over the silhouette and surface relief; one material with
baked 512 base / normal / ORM / emissive maps (see hero.py).

  python hero_units.py <out_dir> <falcon|disc|all> [render_dir]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import hero  # noqa: E402
from kit import box, cyl, lathe, loft, lens, orb, plate, prism  # noqa: E402


def mirror(outline):
    return [(x, -y) for x, y in outline[::-1]]


def tilt(obj, rx=0.0, ry=0.0, rz=0.0, about=(0, 0, 0)):
    obj.location = (obj.location[0] - about[0], obj.location[1] - about[1], obj.location[2] - about[2])
    kit._apply(obj)
    obj.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    obj.location = about
    kit._apply(obj)
    return obj


def placed(obj, rz, at):
    """Turn a part built around the origin by rz degrees about Z, then move it to `at`."""
    obj.rotation_euler = (0, 0, math.radians(rz))
    obj.location = at
    kit._apply(obj)
    return obj


# ---------------------------------------------------------------- Terran Falcon
def falcon():
    """Forward-swept interceptor: long chined nose, canards, cranked forward-swept wing with a
    root extension, twin engine pods with intake ramps, canted twin tails, wing cannons and rails."""
    Z = 0.9
    p = []
    # Chined fuselage: wider and flatter than tall, sharp nose.
    secs = [(5.0, 0.0, Z + 0.05, Z - 0.05, Z),
            (4.4, 0.22, Z + 0.22, Z - 0.16, Z), (3.6, 0.42, Z + 0.42, Z - 0.26, Z + 0.02),
            (2.6, 0.62, Z + 0.62, Z - 0.34, Z + 0.04), (1.4, 0.8, Z + 0.7, Z - 0.38, Z + 0.04),
            (0.0, 0.9, Z + 0.62, Z - 0.4, Z + 0.02), (-1.4, 0.92, Z + 0.56, Z - 0.4, Z),
            (-2.8, 0.86, Z + 0.5, Z - 0.38, Z), (-3.8, 0.7, Z + 0.42, Z - 0.32, Z),
            (-4.4, 0.5, Z + 0.32, Z - 0.24, Z)]
    p.append(loft('Fuselage', secs, 20, 'hull', smooth=False))
    # Canopy: faceted glass blister.
    p.append(loft('Canopy', lens(1.2, 3.5, 0.36, Z + 1.02, Z + 0.5, Z + 0.55, n=8, nose=0.7), 10, 'canopy', smooth=False))
    p.append(loft('CanopyFrame', lens(1.0, 1.35, 0.42, Z + 0.88, Z + 0.5, Z + 0.55, n=3, nose=1.0), 10, 'turret', smooth=False))
    # Spine with raised armour plates and a cyan data strip.
    p.append(plate('Spine', [(-4.0, -0.28), (1.0, -0.22), (1.3, 0.0), (1.0, 0.22), (-4.0, 0.28)], Z + 0.5, Z + 0.72, 'turret', bevel=0.04))
    for k, (x0, x1) in enumerate(((-3.6, -2.4), (-2.2, -1.0), (-0.8, 0.6))):
        p.append(plate(f'SpinePlate{k}', [(x0, -0.42), (x1, -0.36), (x1, 0.36), (x0, 0.42)], Z + 0.6, Z + 0.78, 'hull', bevel=0.05))
    p.append(box('SpineGlow', (-1.5, 0, Z + 0.725), (2.3, 0.04, 0.012), 'glow'))
    # Main wing: forward-swept outer panel with a leading-edge root extension (LERX), cranked.
    wing = [(-3.2, 0.7), (1.8, 0.7), (0.4, 1.6), (-0.4, 2.6), (0.6, 4.9), (-0.3, 5.1), (-2.6, 2.9), (-3.4, 1.6)]
    p.append(plate('WingL', wing, Z - 0.14, Z + 0.06, 'hull', bevel=0.045))
    p.append(plate('WingR', mirror(wing), Z - 0.14, Z + 0.06, 'hull', bevel=0.045))
    for s in (1, -1):
        # Raised inner wing armour and the cyan leading-edge light.
        p.append(plate(f'WingArmour{s}', [(-2.6, s * 0.9), (0.6, s * 0.9), (-0.5, s * 2.4), (-2.2, s * 2.4)][::s], Z + 0.06, Z + 0.14, 'turret', bevel=0.03))
        p.append(placed(box(f'LeadGlow{s}', (0.0, 0.0, 0.0), (1.2, 0.04, 0.03), 'glow'), s * 66.5, (0.1, s * 3.75, Z + 0.07)))
        p.append(placed(box(f'RootGlow{s}', (0.0, 0.0, 0.0), (0.78, 0.035, 0.025), 'glow'), s * 147, (1.1, s * 1.15, Z + 0.07)))
        # Wingtip rail with a missile and orange nav light.
        p.append(box(f'TipRail{s}', (-0.2, s * 5.05, Z - 0.12), (1.0, 0.07, 0.07), 'dark', bevel=0.02))
        p.append(cyl(f'TipMissile{s}', (-1.3, s * 5.05, Z - 0.24), (0.9, s * 5.05, Z - 0.24), 0.09, 8, 'barrel'))
        p.append(cyl(f'TipSeeker{s}', (0.9, s * 5.05, Z - 0.24), (1.15, s * 5.05, Z - 0.24), 0.09, 8, 'barrel', r1=0.01))
        p.append(box(f'NavLight{s}', (-0.3, s * 5.15, Z + 0.02), (0.18, 0.05, 0.05), 'amber'))
        # Under-wing pylon with two missiles.
        p.append(box(f'Pylon{s}', (-1.0, s * 2.9, Z - 0.26), (0.7, 0.06, 0.12), 'dark', bevel=0.02))
        for k, dy in enumerate((-0.18, 0.18)):
            y = s * 2.9 + dy
            p.append(cyl(f'Msl{s}{k}', (-2.0, y, Z - 0.46), (0.2, y, Z - 0.46), 0.1, 8, 'turret'))
            p.append(cyl(f'MslTip{s}{k}', (0.2, y, Z - 0.46), (0.5, y, Z - 0.46), 0.1, 8, 'barrel', r1=0.01))
        # Canards.
        can = [(2.3, s * 0.7), (3.3, s * 0.7), (2.5, s * 1.9), (2.0, s * 1.9)]
        p.append(plate(f'Canard{s}', can if s > 0 else can[::-1], Z + 0.12, Z + 0.2, 'turret', bevel=0.025))
        # Engine pod: intake ramp, nacelle, nozzle petals and burner.
        y = s * 1.05
        pod = [(1.0, 0.0, Z + 0.1, Z - 0.42, Z - 0.16), (0.6, 0.36, Z + 0.16, Z - 0.5, Z - 0.16),
               (-1.0, 0.44, Z + 0.2, Z - 0.54, Z - 0.16), (-3.6, 0.44, Z + 0.2, Z - 0.54, Z - 0.16),
               (-4.6, 0.38, Z + 0.14, Z - 0.46, Z - 0.16)]
        p.append(loft(f'Pod{s}', pod, 12, 'turret', smooth=False, cy=y))
        p.append(box(f'IntakeLip{s}', (0.75, y, Z - 0.17), (0.08, 0.34, 0.26), 'dark', bevel=0.02))
        p.append(box(f'IntakeGlow{s}', (0.66, y, Z - 0.17), (0.02, 0.26, 0.18), 'glow'))
        p.append(cyl(f'Nozzle{s}', (-4.55, y, Z - 0.16), (-5.2, y, Z - 0.16), 0.36, 12, 'barrel', r1=0.3, caps=False))
        p.append(cyl(f'Burner{s}', (-5.0, y, Z - 0.16), (-5.12, y, Z - 0.16), 0.28, 12, 'glow'))
        # Canted tail with a darker rudder and a tip light.
        fin = prism(f'Tail{s}', [(-4.6, 0.0), (-2.9, 0.0), (-3.7, 1.9), (-4.4, 1.9)], -0.06, 0.06, 'hull', bevel=0.02)
        fin.location = (0, s * 1.05, Z + 0.15)
        kit._apply(fin)
        p.append(tilt(fin, rx=-s * 24, about=(0, s * 1.05, Z + 0.15)))
        rud = prism(f'Rudder{s}', [(-4.75, 0.25), (-4.4, 0.25), (-4.4, 1.75), (-4.62, 1.75)], -0.07, 0.07, 'dark')
        rud.location = (0, s * 1.05, Z + 0.15)
        kit._apply(rud)
        p.append(tilt(rud, rx=-s * 24, about=(0, s * 1.05, Z + 0.15)))
        p.append(tilt(box(f'TailLight{s}', (-3.95, s * 1.05, Z + 2.02), (0.18, 0.05, 0.04), 'amber'), rx=-s * 24, about=(0, s * 1.05, Z + 0.15)))
        # Ventral strake.
        p.append(prism(f'Strake{s}', [(-4.0, Z - 0.35), (-2.6, Z - 0.35), (-3.6, Z - 0.85)], s * 0.62 - 0.04, s * 0.62 + 0.04, 'dark'))
        # Nose cannon.
        p.append(cyl(f'Gun{s}', (3.0, s * 0.5, Z - 0.1), (4.2, s * 0.5, Z - 0.1), 0.05, 6, 'barrel'))
        # Chine glow strips along the nose.
        p.append(placed(box(f'Chine{s}', (0, 0, 0), (0.9, 0.03, 0.02), 'glow'), -s * 12.5, (3.5, s * 0.47, Z + 0.06)))
    return p


# ---------------------------------------------------------------- Kesh Disc
def disc():
    """Saucer built from a segmented crown of curved petal plates over a deep keel bowl, a raised
    core cradle with the gold orb, an outer ring of detached crescent blades held by the field,
    and a forward emitter prong so it has a direction of travel."""
    Z = 1.0
    p = []
    # Keel bowl underneath and the field ring.
    p.append(lathe('Keel', [(3.2, Z + 0.05), (2.9, Z - 0.25), (2.2, Z - 0.55), (1.2, Z - 0.75), (0.5, Z - 0.8)], 20, 'under',
                   bottom=Z - 0.82, smooth=True))
    p.append(lathe('FieldRing', [(3.0, Z - 0.28), (3.08, Z - 0.22), (3.0, Z - 0.16)], 24, 'glow', smooth=True))
    p.append(lathe('Rim', [(3.25, Z - 0.02), (3.45, Z + 0.05), (3.4, Z + 0.15), (3.15, Z + 0.18)], 24, 'fin', smooth=True))
    # Crown: ten curved petal plates, each a little lens raised along its spine.
    for k in range(10):
        a = k * 36.0
        petal = loft(f'Petal{k}', [(0.9, 0.0, Z + 0.62, Z + 0.4, Z + 0.5), (1.4, 0.34, Z + 0.62, Z + 0.24, Z + 0.4),
                                   (2.2, 0.52, Z + 0.5, Z + 0.14, Z + 0.3), (2.9, 0.5, Z + 0.32, Z + 0.06, Z + 0.17),
                                   (3.3, 0.0, Z + 0.17, Z + 0.06, Z + 0.1)], 6, 'shell', smooth=True)
        p.append(kit.rot_z(petal, a))
        vein = box(f'PetalVein{k}', (2.05, 0.0, Z + 0.47), (0.75, 0.025, 0.02), 'glow')
        vein.rotation_euler = (0, math.radians(13), 0)
        kit._apply(vein)
        p.append(kit.rot_z(vein, a))
    # Core cradle: a ring of five claws around the orb.
    p.append(lathe('Cradle', [(1.15, Z + 0.4), (1.05, Z + 0.72), (0.8, Z + 0.86), (0.62, Z + 0.78)], 20, 'fin', smooth=True))
    p.append(orb('Orb', (0, 0, Z + 1.05), 0.5, 'core', seg=(12, 8)))
    for k in range(5):
        claw = loft(f'Claw{k}', [(0.55, 0.0, Z + 0.8, Z + 0.7, Z + 0.75), (0.75, 0.1, Z + 1.05, Z + 0.78, Z + 0.9),
                                 (0.7, 0.08, Z + 1.35, Z + 1.15, Z + 1.25), (0.45, 0.0, Z + 1.55, Z + 1.45, Z + 1.5)], 6, 'fin', smooth=True)
        p.append(kit.rot_z(claw, k * 72 + 36))
    # Detached crescent blades orbiting the rim (held by the field, nothing touches).
    for k in range(6):
        a = k * 60.0 + 30.0
        blade = []
        n = 9
        for i in range(n):
            t = i / (n - 1)
            ang = math.radians(-26 + 52 * t)
            w = 0.08 + 0.28 * math.sin(math.pi * t)
            blade.append((3.75 * math.cos(ang), 3.75 * math.sin(ang)))
        inner = []
        for i in range(n):
            t = i / (n - 1)
            ang = math.radians(-26 + 52 * t)
            w = 0.04 + 0.34 * math.sin(math.pi * t)
            inner.append(((3.75 + w) * math.cos(ang), (3.75 + w) * math.sin(ang)))
        outline = blade + inner[::-1]
        b = plate(f'Blade{k}', outline[::-1], Z + 0.02, Z + 0.14, 'fin')
        b = tilt(b, ry=8, about=(3.9, 0, Z + 0.08))
        p.append(kit.rot_z(b, a))
        p.append(kit.rot_z(box(f'BladeGlow{k}', (3.95, 0.0, Z + 0.15), (0.05, 0.42, 0.012), 'glow'), a))
    # Forward emitter prong: a raised spur on +X carrying a gold emitter, plus two cheek emitters.
    p.append(loft('Spur', [(2.4, 0.0, Z + 0.45, Z + 0.25, Z + 0.35), (3.0, 0.22, Z + 0.42, Z + 0.12, Z + 0.27),
                           (3.9, 0.16, Z + 0.3, Z + 0.06, Z + 0.18), (4.5, 0.0, Z + 0.2, Z + 0.1, Z + 0.15)], 8, 'fin', smooth=True))
    p.append(orb('Emitter', (4.1, 0.0, Z + 0.3), 0.15, 'core', seg=(10, 6)))
    for s in (1, -1):
        p.append(orb(f'Cheek{s}', (3.0, s * 1.3, Z + 0.2), 0.12, 'core', seg=(8, 5)))
    # Underside emitters (point down at targets).
    for k in range(3):
        a = math.radians(k * 120)
        p.append(cyl(f'Down{k}', (1.6 * math.cos(a), 1.6 * math.sin(a), Z - 0.45),
                     (1.6 * math.cos(a), 1.6 * math.sin(a), Z - 0.75), 0.16, 8, 'barrel', r1=0.1))
        p.append(orb(f'DownGlow{k}', (1.6 * math.cos(a), 1.6 * math.sin(a), Z - 0.78), 0.1, 'core', seg=(8, 4)))
    return p


UNITS = {'falcon': ('terran', falcon, 'TerranFalcon'), 'disc': ('kesh', disc, 'KeshDisc')}


def preview(obj, render_dir, stem, faction):
    kit.S['meshes'] = [obj]
    kit.S['root'] = obj
    cfg = kit.FACTIONS[faction]
    kit.S['cfg'] = cfg
    kit.preview(render_dir, stem, samples=int(os.environ.get('SAMPLES', '32')),
                res=tuple(int(v) for v in os.environ.get('RES', '1200x750').split('x')),
                views=tuple(os.environ.get('VIEWS', 'front34,rts').split(',')))


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out_dir, which = args[0], args[1]
    render_dir = args[2] if len(args) > 2 else None
    names = list(UNITS) if which == 'all' else which.split(',')
    for name in names:
        faction, fn, title = UNITS[name]
        hero.begin(faction)
        parts = fn()
        count = sum(len(o.data.polygons) and sum(len(f.vertices) - 2 for f in o.data.polygons) for o in parts)
        print('PRE-BAKE TRIANGLES', name, count)
        if os.environ.get('COUNT_ONLY'):
            continue
        obj = hero.bake_unit(title, parts, f'{out_dir}/{name}.glb', f'{out_dir}/tex', size=512)
        print('TRIANGLES', name, hero.tri_count(obj))
        hero.export(obj, f'{out_dir}/{name}.glb')
        if render_dir:
            preview(obj, render_dir, name, faction)
