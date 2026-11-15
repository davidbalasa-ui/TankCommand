"""Kesh structures, art pass v2. Centre at the origin, ground at z = 0, weapons face +X.
Kesh buildings are grown, not built: a petal dais on the ground and parts that hang in the air."""
import math

import forge as F
from forge import body, box, crescent, cyl, lathe, lensfn, orb, shell, sweep, tube, discfn
import kesh_kit as K

ASSETS = {}


def asset(path, label, size=1024):
    def deco(fn):
        def run(glb, render, report):
            F.begin('kesh')
            kw = fn() or {}
            F.finish(kw.pop('name'), glb, render=render, report=report, label=label, size=kw.pop('size', size),
                     crevice=(0.75, 0.55, 0.4), **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='structures')
        run.build = fn
        return run
    return deco


def dais(R, h=0.4, n=0, glow=True):
    """Low dark plinth with a silver collar and a glowing seam. Returns the height of its top."""
    sd = 28
    lathe([(R, 0.0), (R * 0.97, h * 0.55), (R * 0.82, h), (R * 0.6, h * 1.04)], sd, 'under')
    lathe([(R * 0.84, h * 0.96), (R * 0.78, h + 0.12), (R * 0.62, h + 0.14), (R * 0.56, h + 0.02), (0.02, h + 0.02)], sd, 'shell')
    K.ring((0, 0, h * 0.5), R * 0.985, 0.035, 'glow', sides=sd)
    for k in range(4):   # bronze clamps over the rim
        m = F.mark()
        box((R * 0.9, 0, h * 0.55), (R * 0.12, R * 0.09, h * 0.6), 'bronze', bevel=0.04)
        F.rot_all(m, 'Z', 90 * k + 45)
    return h + 0.14


def saucer(c, R, ht, hb, plates=3, sides=24, start=0.0, zone='shell'):
    """Floating lens hull: etched dome with bronze sector plates, dark keel, glowing waist and lifter."""
    cx, cy, cz = c
    fn = discfn(R, cz + ht, cz, cx=cx, cy=cy, p=0.8)
    body(fn, zone, nu=8, nv=sides)
    for k in range(plates):
        shell(fn, 0.34, 0.93, start + 360.0 * k / plates, 360.0 / plates * 0.62, 'bronze', nu=7, nv=6, off=0.03,
              lift=0.03, shape=0.5, front=1.0, back=1.0, thick=0.06)
    lathe([(R, 0.0), (R * 0.9, -hb * 0.4), (R * 0.5, -hb * 0.9), (R * 0.3, -hb)], sides, 'under', center=c)
    K.ring((cx, cy, cz - 0.02), R * 1.01, 0.06, 'bronze', sides=sides)
    K.ring((cx, cy, cz - hb * 0.3), R * 0.9, 0.03, 'glow', sides=sides)
    cyl((cx, cy, cz - hb - 0.02), (cx, cy, cz - hb + 0.02), R * 0.3, 14, 'glow')
    return fn


def horn(c, r, lean, zone='shell', width=0.4, a0=-20, a1=95, yaw=0.0, thick=0.07):
    """Tall crescent horn rising from the ground and curling inward. yaw turns it round the centre."""
    m = F.mark()
    K.fin((0, 0, 0), r, a0, a1, width, thick, zone=zone)
    F.move_all(m, (-r * math.cos(math.radians(a0)) + lean, 0, -r * math.sin(math.radians(a0))))
    F.rot_all(m, 'Z', yaw)
    F.move_all(m, c)


def thorn_turret(tz):
    """The Thornmound's floating gun: shared by the deployed tower and its packed carrier."""
    saucer((0, 0, tz), 1.35, 0.62, 0.38, start=60)
    K.barrel(0.55, 2.95, 0, tz + 0.3, 0.15)
    K.core((-0.6, 0, tz + 0.62), 0.3)
    for s in (1, -1):
        K.fin((-0.35, s * 0.95, tz + 0.2), 1.05, 205, 65, 0.36, 0.06, lean=-s * 14)


@asset('structures/kesh_thornmound.glb', 'Kesh Thornmound (turret)', size=512)
def kesh_thornmound():
    z = dais(2.0, 0.42)
    K.claws((0, 0, z - 0.15), 3, 1.45, 0.95, width=0.34, zone='bronze', start=60)
    tz = z + 1.0
    with F.group('Turret'):
        thorn_turret(tz)
    return dict(name='KeshThornmound', pivot=('Turret', (0, 0, tz)))


def spore_pod(tz):
    pf = lensfn(-0.9, 0.9, 0.8, tz + 2.7, tz, tz + 1.3, nose=1.0)
    body(pf, 'under', off=-0.04, nu=10, nv=12)
    for k in range(4):
        shell(pf, 0.04, 0.96, 45 + 90 * k, 70, 'shell' if k % 2 else 'bronze', nu=8, nv=4, off=0.04, lift=0.02,
              shape=0.5, front=0.6, back=0.6)
    # Six seeker pods in two rows, noses forward and up.
    for i, zz in enumerate((tz + 0.9, tz + 1.8)):
        for y in (-0.85, 0, 0.85):
            m = F.mark()
            tube((0.15, y, zz), (1.35, y, zz), [(0, 0.1), (0.15, 0.22), (0.6, 0.22), (0.85, 0.14), (1, 0.02)], 10, 'barrel')
            cyl((0.5, y, zz), (0.58, y, zz), 0.232, 10, 'glow')
            F.rot_all(m, 'Y', -28, about=(0.15, y, zz))
    K.ring((0, 0, tz + 2.95), 0.6, 0.04, 'glow', sides=18)
    K.ring((0, 0, tz + 0.1), 1.1, 0.06, 'bronze', sides=20)


@asset('structures/kesh_spore_tower.glb', 'Kesh Spore Tower (missile battery)', size=512)
def kesh_spore_tower():
    z = dais(1.9, 0.42)
    # Three ribs rise from the plinth and cradle a floating pod stack.
    for k in range(3):
        horn((0, 0, z - 0.2), 2.3, 1.5, 'bronze', 0.4, -8, 78, yaw=120 * k + 60)
    tz = z + 1.3
    with F.group('Turret'):
        spore_pod(tz)
    return dict(name='KeshSporeTower', pivot=('Turret', (0, 0, tz)))


@asset('structures/kesh_seer_spire.glb', 'Kesh Seer Spire (sensor)', size=512)
def kesh_seer_spire():
    z = dais(2.2, 0.42)
    for k in range(2):
        horn((0, 0, z - 0.2), 4.2, 1.9, 'shell', 0.55, -5, 62, yaw=180 * k + 90, thick=0.09)
        horn((0, 0, z - 0.2), 2.2, 1.5, 'bronze', 0.4, -5, 70, yaw=180 * k)
    tz = z + 3.4
    with F.group('Eye'):
        c = (0, 0, tz)
        orb(c, 0.55, 'core', seg=(18, 12))
        for sgn in (1, -1):   # floating shell caps above and below the core
            lathe([(0.02, sgn * 1.0), (0.5, sgn * 0.9), (0.85, sgn * 0.55), (0.74, sgn * 0.52), (0.45, sgn * 0.8), (0.02, sgn * 0.88)],
                  18, 'shell', center=c)
        K.ring(c, 1.1, 0.05, 'bronze', sides=24, tilt=(22, 0))
        K.ring(c, 1.3, 0.035, 'glow', sides=24, tilt=(-16, 28))
        for k in range(4):
            m = F.mark()
            K.blade((0, 0, 0), 0.5, 20, 160, 0.2, 0.04, zone='shell')
            F.move_all(m, (0, 1.2, 0))
            F.rot_all(m, 'Z', 90 * k + 45)
            F.move_all(m, (0, 0, tz - 0.9))
    return dict(name='KeshSeerSpire', pivot=('Eye', (0, 0, tz)))


@asset('structures/kesh_gene_vault.glb', 'Kesh Gene Vault (research)')
def kesh_gene_vault():
    z = dais(3.8, 0.45)
    # A great floating dome over a glowing gap, a hovering crown, four horns and caged specimen cores.
    fn = saucer((0, 0, z + 0.75), 2.7, 2.0, 0.5, plates=4, sides=28, start=45)
    for k in range(4):
        shell(fn, 0.05, 0.4, 90 * k, 60, 'bronze', nu=6, nv=5, off=0.05, lift=0.03, shape=0.5, front=0.3, back=1.0)
    for k in range(4):
        horn((0, 0, z - 0.25), 3.2, 3.1, 'shell', 0.5, -8, 72, yaw=90 * k + 45, thick=0.09)
    with F.group('Crown'):   # the hovering crown turns slowly
        K.ring((0, 0, z + 3.45), 1.3, 0.09, 'bronze', sides=24)
        K.ring((0, 0, z + 3.45), 1.05, 0.035, 'glow', sides=24)
        K.core((0, 0, z + 3.5), 0.42, ring=False)
    for k in range(4):
        a = math.radians(90 * k)
        K.core((3.05 * math.cos(a), 3.05 * math.sin(a), z + 0.5), 0.32)
    return dict(name='KeshGeneVault', pivot=[('Crown', (0, 0, z + 3.45), 'CrownPivot')])


@asset('structures/kesh_metal_siphon.glb', 'Kesh Metal Siphon (refinery)')
def kesh_metal_siphon():
    z = dais(3.7, 0.45)
    # Intake basin on the -Y side for the Ferriers, and a column of molten metal drawn up into a floating core.
    bc = (0, -2.2, z + 0.05)
    lathe([(0.2, 0.0), (1.0, 0.1), (1.35, 0.45), (1.45, 0.45), (1.1, 0.0), (0.2, -0.1)], 16, 'under', center=bc)
    K.ring((bc[0], bc[1], bc[2] + 0.46), 1.4, 0.07, 'bronze', sides=18)
    cyl((bc[0], bc[1], bc[2] + 0.1), (bc[0], bc[1], bc[2] + 0.14), 0.85, 14, 'glow')
    c = (0, 0.5, z)
    lathe([(1.5, 0.0), (1.2, 0.5), (0.9, 0.7), (0.7, 0.7), (0.8, 0.2), (0.3, 0.0)], 16, 'bronze', center=c)
    tube((0, 0.5, z + 0.3), (0, 0.5, z + 3.2), [(0, 0.4), (0.3, 0.16), (0.7, 0.12), (1, 0.3)], 10, 'glow')
    K.core((0, 0.5, z + 3.9), 0.8, cage=4, ring=False)
    for k in range(5):
        horn((0, 0.5, z - 0.2), 4.4, 1.7, 'shell' if k % 2 else 'bronze', 0.5, -6, 66, yaw=72 * k + 18, thick=0.09)
    for i, (zz, r) in enumerate(((z + 1.3, 1.25), (z + 2.0, 1.0), (z + 2.7, 1.2))):
        K.ring((0, 0.5, zz), r, 0.07, 'bronze' if i % 2 else 'shell', sides=22)
    K.ring((0, 0.5, z + 5.0), 0.7, 0.04, 'glow', sides=20)
    # Cooling ingots on the +X side.
    for k in range(3):
        p = (2.4, -0.6 + k * 0.9, z + 0.25)
        orb(p, 0.36, 'barrel', seg=(10, 8), sq=(1.3, 0.9, 0.7))
        K.ring(p, 0.5, 0.035, 'glow', sides=14)
    return dict(name='KeshMetalSiphon')


@asset('structures/kesh_hive_roost.glb', 'Kesh Hive Roost (air base)')
def kesh_hive_roost():
    z = dais(5.7, 0.45)
    # Landing ring, an open cage of arching ribs, and floating perches for the fliers.
    lathe([(3.3, z - 0.05), (3.55, z + 0.02), (3.8, z - 0.05)], 36, 'glow')
    lathe([(1.2, z - 0.05), (1.3, z + 0.01), (1.4, z - 0.05)], 24, 'glow')
    for k in range(6):
        horn((0, 0, z - 0.25), 5.2, 4.6, 'shell' if k % 2 else 'bronze', 0.75, -8, 58, yaw=60 * k + 30, thick=0.11)
    for k in range(6):
        horn((0, 0, z - 0.25), 2.0, 5.1, 'bronze', 0.4, -10, 80, yaw=60 * k, thick=0.07)
    K.ring((0, 0, z + 4.9), 1.9, 0.12, 'bronze', sides=30)
    K.ring((0, 0, z + 4.9), 1.55, 0.05, 'glow', sides=30)
    orb((0, 0, z + 5.0), 0.6, 'core', seg=(16, 10))
    for k in range(3):
        a = math.radians(120 * k + 90)
        p = (3.6 * math.cos(a), 3.6 * math.sin(a), z + 2.2 + 0.5 * k)
        lathe([(0.1, 0.0), (0.9, 0.06), (1.15, 0.22), (1.2, 0.2), (0.9, -0.04), (0.1, -0.12)], 16, 'shell', center=p)
        K.ring((p[0], p[1], p[2] + 0.1), 0.75, 0.035, 'glow', sides=16)
        cyl((p[0], p[1], p[2] - 0.16), (p[0], p[1], p[2] - 0.12), 0.5, 14, 'glow')
    return dict(name='KeshHiveRoost')


@asset('structures/kesh_landing_nest.glb', 'Kesh Landing Nest')
def kesh_landing_nest():
    import compat
    compat.install()
    import pads_hero
    pads_hero.kesh_nest()
    # The crown over the heart and the high halo are their own parts so they can turn.
    import towers
    for o in F.ST['parts']:
        x, y, zz = towers.centre(o)
        if zz > 4.0:
            o['group'] = 'Halo'
        elif zz > 1.3 and x * x + y * y < 1.0:
            o['group'] = 'Crown'
    return dict(name='KeshLandingNest', pivot=[('Crown', (0, 0, 1.45), 'CrownPivot'), ('Halo', (0, 0, 4.2), 'HaloPivot')])
