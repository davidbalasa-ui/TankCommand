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
        return run
    return deco


def dais(R, h=0.45, n=10, glow=True):
    """Low mound of overlapping petals round a glowing seam."""
    lathe([(R * 0.99, 0.0), (R * 0.96, h * 0.45), (R * 0.72, h * 0.9), (0.05, h)], max(16, n * 2), 'slat')
    lathe([(R, 0.0), (R * 1.0, h * 0.18), (R * 0.93, h * 0.3), (R * 0.9, 0.0)], max(16, n * 2), 'under')
    f = discfn(R * 0.99, h + 0.06, h * 0.25, p=0.6)
    for k in range(n):
        shell(f, 0.3, 1.0, 360.0 * k / n, 360.0 / n * 0.86, 'shell' if k % 2 else 'bronze', nu=7, nv=4,
              off=0.02, lift=0.05, shape=0.4, skew=12, thick=0.07)
    f2 = discfn(R * 0.5, h + 0.16, h + 0.02, p=0.7)
    for k in range(n // 2):
        shell(f2, 0.1, 1.0, 720.0 * k / n + 18, 720.0 / n * 0.8, 'bronze', nu=6, nv=4, off=0.02, lift=0.03, shape=0.45, skew=18)
    return h + 0.16


def horn(c, r, lean, zone='shell', width=0.4, a0=-20, a1=95, yaw=0.0, thick=0.07):
    """Tall crescent horn rising from the ground and curling inward. yaw turns it round the centre."""
    m = F.mark()
    K.fin((0, 0, 0), r, a0, a1, width, thick, zone=zone)
    F.move_all(m, (-r * math.cos(math.radians(a0)) + lean, 0, -r * math.sin(math.radians(a0))))
    F.rot_all(m, 'Z', yaw)
    F.move_all(m, c)


@asset('structures/kesh_thornmound.glb', 'Kesh Thornmound (turret)', size=512)
def kesh_thornmound():
    z = dais(2.0, 0.5, 8)
    lathe([(1.0, z - 0.1), (0.85, z + 0.25), (0.5, z + 0.5)], 14, 'bronze')
    tz = z + 0.5
    with F.group('Turret'):
        # Open bud: petals peeled back round the thorn cannon, core glowing at its heart.
        K.petals((0, 0, tz - 0.1), 6, 0.45, 1.25, 0.95, 'shell', width=0.5, thick=0.07)
        K.petals((0, 0, tz - 0.05), 6, 0.4, 0.85, 1.2, 'bronze', width=0.36, thick=0.06, start=30)
        orb((0, 0, tz + 0.55), 0.42, 'core', seg=(14, 10))
        K.barrel(0.2, 3.3, 0, tz + 0.75, 0.15)
        for s in (1, -1):
            K.fin((-0.5, s * 0.5, tz + 0.5), 1.0, 205, 70, 0.34, 0.05, lean=-s * 20)
        # Floating guard blades.
        for s in (1, -1):
            K.blade((0.2, 0, tz + 1.5), 1.45, s * 40, s * 140, 0.26, 0.05, zone='shell')
    return dict(name='KeshThornmound', pivot=('Turret', (0, 0, tz)))


@asset('structures/kesh_spore_tower.glb', 'Kesh Spore Tower (missile battery)', size=512)
def kesh_spore_tower():
    z = dais(1.9, 0.5, 8)
    # Three ribs rise from the dais and cradle a floating pod stack.
    for k in range(3):
        horn((0, 0, z - 0.2), 2.3, 1.5, 'bronze', 0.4, -8, 78, yaw=120 * k + 60)
    tz = z + 1.3
    with F.group('Turret'):
        pf = lensfn(-0.9, 0.9, 0.8, tz + 2.7, tz, tz + 1.3, nose=1.0)
        body(pf, 'slat', off=-0.05, nu=10, nv=12)
        for k in range(4):
            shell(pf, 0.05, 0.95, 45 + 90 * k, 72, 'shell' if k % 2 else 'bronze', nu=8, nv=4, off=0.04, lift=0.02, shape=0.5)
        # Six seeker pods in two rows, noses forward and up.
        for i, zz in enumerate((tz + 0.9, tz + 1.8)):
            for y in (-0.85, 0, 0.85):
                m = F.mark()
                tube((0.15, y, zz), (1.35, y, zz), [(0, 0.1), (0.15, 0.22), (0.6, 0.22), (0.85, 0.14), (1, 0.02)], 10, 'barrel')
                cyl((0.4, y, zz), (0.7, y, zz), 0.235, 10, 'slat')
                F.rot_all(m, 'Y', -28, about=(0.15, y, zz))
        K.ring((0, 0, tz + 2.95), 0.6, 0.05, 'glow', sides=18)
        K.ring((0, 0, tz + 0.1), 1.1, 0.06, 'bronze', sides=20)
        orb((0, 0, tz + 3.2), 0.2, 'core', seg=(12, 8))
    return dict(name='KeshSporeTower', pivot=('Turret', (0, 0, tz)))


@asset('structures/kesh_seer_spire.glb', 'Kesh Seer Spire (sensor)', size=512)
def kesh_seer_spire():
    z = dais(2.2, 0.5, 8)
    for k in range(2):
        horn((0, 0, z - 0.2), 4.2, 1.9, 'shell', 0.55, -5, 62, yaw=180 * k + 90, thick=0.09)
        horn((0, 0, z - 0.2), 2.2, 1.5, 'bronze', 0.4, -5, 70, yaw=180 * k)
    tz = z + 3.4
    with F.group('Eye'):
        c = (0, 0, tz)
        orb(c, 0.75, 'core', seg=(18, 12))
        orb((0.62, 0, tz), 0.26, 'under', seg=(10, 8), sq=(0.6, 1, 1))
        K.ring(c, 1.1, 0.05, 'bronze', sides=24, tilt=(22, 0))
        K.ring(c, 1.3, 0.04, 'glow', sides=24, tilt=(-16, 28))
        for k in range(4):
            m = F.mark()
            K.blade((0, 0, 0), 0.5, 20, 160, 0.2, 0.04, zone='shell')
            F.move_all(m, (0, 1.2, 0))
            F.rot_all(m, 'Z', 90 * k + 45)
            F.move_all(m, (0, 0, tz - 0.9))
    return dict(name='KeshSeerSpire', pivot=('Eye', (0, 0, tz)))


@asset('structures/kesh_gene_vault.glb', 'Kesh Gene Vault (research)')
def kesh_gene_vault():
    z = dais(3.8, 0.5, 12)
    # A closed dome of two shell tiers over a glowing heart, a floating crown, and four horns.
    c = (0, 0, z - 0.1)
    lathe([(2.5, 0.0), (2.3, 1.0), (1.6, 1.85), (0.7, 2.3), (0.02, 2.4)], 20, 'slat', center=c)
    d1 = discfn(2.62, z + 2.45, z - 0.2, p=0.75)
    for k in range(8):
        shell(d1, 0.5, 1.0, 45 * k, 39, 'shell', nu=9, nv=5, off=0.05, lift=0.05, shape=0.35, skew=10, thick=0.09)
    for k in range(4):
        shell(d1, 0.06, 0.6, 90 * k + 22, 74, 'bronze', nu=9, nv=6, off=0.1, lift=0.06, shape=0.5, skew=24, thick=0.08)
    for k in range(4):
        horn((0, 0, z - 0.25), 3.2, 3.1, 'shell', 0.5, -8, 72, yaw=90 * k + 45, thick=0.09)
    K.ring((0, 0, z + 3.3), 1.3, 0.09, 'bronze', sides=24)
    K.ring((0, 0, z + 3.3), 1.05, 0.04, 'glow', sides=24)
    orb((0, 0, z + 3.35), 0.45, 'core', seg=(16, 10))
    for k in range(6):
        m = F.mark()
        K.blade((0, 0, 0), 0.6, 20, 160, 0.24, 0.05, zone='shell')
        F.move_all(m, (0, 1.75, 0))
        F.rot_all(m, 'Z', 60 * k)
        F.move_all(m, (0, 0, z + 2.9 + 0.25 * (k % 2)))
    # Specimen pods round the base.
    for k in range(4):
        a = math.radians(90 * k)
        p = (3.0 * math.cos(a), 3.0 * math.sin(a), z + 0.35)
        orb(p, 0.38, 'core', seg=(12, 8), sq=(1, 1, 1.25))
        K.petals((p[0], p[1], p[2] - 0.35), 4, 0.25, 0.5, 0.6, 'bronze', width=0.3, thick=0.04)
    return dict(name='KeshGeneVault')


@asset('structures/kesh_metal_siphon.glb', 'Kesh Metal Siphon (refinery)')
def kesh_metal_siphon():
    z = dais(3.7, 0.5, 12)
    # Intake basin on the -Y side for the Ferriers, and a column of molten metal drawn up into a floating orb.
    bc = (0, -2.2, z + 0.05)
    lathe([(0.2, 0.0), (1.0, 0.1), (1.35, 0.45), (1.45, 0.45), (1.1, 0.0), (0.2, -0.1)], 16, 'under', center=bc)
    lathe([(0.2, 0.05), (1.0, 0.14), (1.3, 0.42)], 16, 'slat', center=bc)
    K.petals((bc[0], bc[1], bc[2] - 0.05), 6, 1.25, 1.7, 0.75, 'bronze', width=0.5, thick=0.06)
    c = (0, 0.5, z)
    lathe([(1.5, 0.0), (1.2, 0.5), (0.9, 0.7), (0.7, 0.7), (0.8, 0.2), (0.3, 0.0)], 16, 'bronze', center=c)
    tube((0, 0.5, z + 0.3), (0, 0.5, z + 3.2), [(0, 0.6), (0.3, 0.3), (0.7, 0.22), (1, 0.45)], 10, 'slat')
    orb((0, 0.5, z + 3.9), 0.85, 'core', seg=(18, 12))
    for k in range(5):
        horn((0, 0.5, z - 0.2), 4.4, 1.7, 'shell' if k % 2 else 'bronze', 0.5, -6, 66, yaw=72 * k + 18, thick=0.09)
    for i, (zz, r) in enumerate(((z + 1.3, 1.25), (z + 2.0, 1.0), (z + 2.7, 1.2))):
        K.ring((0, 0.5, zz), r, 0.07, 'bronze' if i % 2 else 'shell', sides=22)
    K.ring((0, 0.5, z + 5.0), 0.7, 0.05, 'glow', sides=20)
    # Cooling ingot buds on the +X side.
    for k in range(3):
        p = (2.4, -0.6 + k * 0.9, z + 0.25)
        orb(p, 0.36, 'barrel', seg=(10, 8), sq=(1.3, 0.9, 0.7))
        K.ring(p, 0.5, 0.04, 'glow', sides=14)
    return dict(name='KeshMetalSiphon')


@asset('structures/kesh_hive_roost.glb', 'Kesh Hive Roost (air base)')
def kesh_hive_roost():
    z = dais(5.7, 0.5, 14)
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
    return dict(name='KeshLandingNest', single=True)
