"""Kesh units, art pass v2."""
import math

import forge as F
from forge import body, box, crescent, cyl, lathe, lensfn, orb, shell, sweep, tube, sym
import kesh_kit as K

ASSETS = {}


# Role glow: the same parts in a different light, so a unit's job reads from far away.
ROLE_GLOW = {
    'ember': {'core': 'embercore', 'glow': 'ember', 'slat': 'emberslat'},   # miners and haulers
    'pale': {'core': 'palecore', 'glow': 'pale', 'slat': 'paleslat'},       # repair and sensors
}


def asset(path, label, size=512, role=None):
    def deco(fn):
        def run(glb, render, report):
            F.begin('kesh')
            kw = fn() or {}
            for o in F.ST['parts']:
                o['zone'] = ROLE_GLOW.get(role, {}).get(o['zone'], o['zone'])
            kw.setdefault('clear', ('halo',))
            kw.setdefault('clear_alpha', 0.3)
            F.finish(kw.pop('name', fn.__name__.title().replace('_', '')), glb, render=render, report=report,
                     label=label, size=kw.pop('size', size), crevice=(0.75, 0.55, 0.4), **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='kesh')
        return run
    return deco


def turret(tz, L=2.9, w=0.85, h=0.62, x0=-1.6, gun=(5.4, 0.15), crest=True, prongs=3, halo=False):
    """Low layered turret with a gold collar ring, a sensor slit, an energy lance and a small crest fin."""
    tf = lensfn(x0, x0 + L, w, tz + h, tz - 0.1, tz + 0.16, nose=0.85)
    body(tf, 'under', off=-0.04, nu=10, nv=12)
    K.plate(tf, 0.0, 0.55, 90, 150, 'shell', lines=2, nu=8, nv=6, off=0.03, lift=0.04, shape=0.5)
    K.plate(tf, 0.38, 1.0, 90, 110, 'bronze', nu=8, nv=6, off=0.09, lift=0.1, shape=0.55)
    for vc in (10, 170):
        K.plate(tf, 0.12, 0.95, vc, 56, 'shell', lines=0, nu=8, nv=4, off=0.08, lift=0.08)
    cx = x0 + L * 0.5
    K.ring((cx, 0, tz + 0.0), w * 1.1, 0.024, 'gold', sides=24)
    if halo:   # a ring of light round the turret foot
        K.ring((cx, 0, tz + 0.16), w * 1.42, 0.09, 'glow', sides=28, flat=0.6)
        K.ring((cx, 0, tz + 0.12), w * 1.58, 0.03, 'gold', sides=28)
    sweep([tuple(tf(0.13, v, 0.085)) for v in (48, 66, 90, 114, 132)], [(0.03, 0.02), (0.055, 0.03), (0.06, 0.03), (0.055, 0.03), (0.03, 0.02)], 'glow', sides=4)
    if gun:
        K.barrel(x0 + L * 0.72, gun[0], 0, tz + 0.2, gun[1], prongs=prongs, group='Barrel', flash_group='Flash')
    if crest:
        K.fin((x0 + L * 0.3, 0, tz + 0.35), 0.8, 205, 80, 0.3, 0.05)


@asset('alien/stinger.glb', 'Arcadian Stinger (light tank)')
def stinger():
    fn = lensfn(-3.3, 3.5, 1.8, 1.85, 0.62, 1.12, nose=0.72)
    K.layered_hull(fn)
    K.lifters([(1.6, 0, 0.64), (-1.4, 0.8, 0.66), (-1.4, -0.8, 0.66)], 0.34)
    for s in (1, -1):
        # Rear crest fins sweeping up and forward, and a long blade hugging each flank.
        K.fin((-2.3, s * 0.8, 1.5), 1.6, 220, 62, 0.46, 0.06, lean=-s * 12)
    K.flanks(6.6, 1.85, 1.26)
    K.core((1.7, 0, 1.56), 0.24)
    K.slit_eyes(fn, 0.07)
    K.thrusters([(-3.0, 0.45, 1.12), (-3.0, -0.45, 1.12)], 1.2)
    tz = 1.78
    with F.group('Turret'):
        turret(tz, gun=(5.6, 0.16), halo=True)   # reads as: a teardrop, one lance, one ring of light
    return dict(pivot=[('Turret', (-0.2, 0, tz))] + K.gun_pivots([('', (0.5, 0, tz + 0.2), (5.7, 0, tz + 0.2))]))


@asset('alien/darter.glb', 'Arcadian Darter (scout)')
def darter():
    # Reads as: a needle with a two-pronged fork out in front and one line of light down its back.
    fn = lensfn(-2.6, 3.6, 0.86, 1.5, 0.66, 1.02, nose=0.6)
    K.layered_hull(fn, sides=False)
    K.lifters([(1.5, 0, 0.68), (-1.3, 0, 0.7)], 0.28)
    for u0, u1 in ((0.05, 0.4), (0.74, 0.97)):   # spine of light, fore and aft of the turret
        sweep([tuple(fn(u0 + (u1 - u0) * k / 5, 90, 0.2)) for k in range(6)], [(0.11, 0.05)] * 6, 'glow', sides=4)
    for s in (1, -1):
        # Forward-swept pincer blade reaching well past the nose, slim and raised, and a raked tail fin.
        b = K.blade((1.6, s * 3.4, 1.12), 3.0, s * -104, s * -48, 0.46, 0.09, sq=(1.6, 1.0), zone='shell')
        K.fin((-1.9, s * 0.45, 1.25), 1.1, 215, 75, 0.34, 0.05, lean=-s * 22)
    K.eye((2.1, 0, 1.27), 0.17, brow=False)
    K.thrusters([(-2.4, 0, 1.05)], 1.3)
    tz = 1.47
    with F.group('Turret'):
        tf = lensfn(-1.1, 0.7, 0.5, tz + 0.4, tz - 0.08, tz + 0.12, nose=0.85)
        body(tf, 'under', off=-0.03, nu=8, nv=10)
        K.plate(tf, 0.0, 1.0, 90, 150, 'shell', nu=8, nv=6, off=0.03, lift=0.05, shape=0.5)
        K.ring((-0.2, 0, tz), 0.54, 0.02, 'gold', sides=18)
        for s in (1, -1):
            K.barrel(0.15, 2.75, s * 0.28, tz + 0.14, 0.07, prongs=2, group='Barrel' + 'LR'[s < 0], flash_group='Flash' + 'LR'[s < 0])
    return dict(pivot=[('Turret', (-0.2, 0, tz))] + K.gun_pivots([(a, (0.15, y, tz + 0.14), (2.8, y, tz + 0.14)) for a, y in (('L', 0.28), ('R', -0.28))]))


@asset('alien/glider.glb', 'Arcadian Glider (hover tank)')
def glider():
    fn = lensfn(-2.6, 3.0, 1.15, 1.6, 0.6, 1.05, nose=0.7)
    K.layered_hull(fn, sides=False)
    K.lifters([(1.2, 0, 0.6), (-1.2, 0, 0.6)], 0.3)
    for s in (1, -1):
        # Reads as: a wide manta, wider than it is long, with a light on each wingtip.
        b1 = K.blade((0.6, s * 3.5, 1.02), 3.2, s * -60, s * -172, 1.25, 0.09, zone='shell')
        F.rot(b1, 'X', s * 7, about=(0, 0, 1.0))
        b2 = K.blade((-0.6, s * 2.8, 1.14), 2.3, s * -60, s * -170, 0.75, 0.07)
        F.rot(b2, 'X', s * 12, about=(0, 0, 1.1))
        K.fin((-1.9, s * 0.5, 1.3), 1.0, 215, 80, 0.3, 0.05, lean=-s * 18)
        K.barrel(1.2, 3.7, s * 0.55, 0.92, 0.1, prongs=2, group='Barrel' + 'LR'[s < 0], flash_group='Flash' + 'LR'[s < 0])
        K.core((-2.35, s * 3.0, 1.55), 0.3, ring=False)
    K.core((0.3, 0, 1.72), 0.3)
    K.thrusters([(-2.5, 0, 1.05)], 1.0)
    return dict(pivot=K.gun_pivots([(a, (1.2, y, 0.92), (3.8, y, 0.92)) for a, y in (('L', 0.55), ('R', -0.55))], parent=None))


@asset('alien/carapace.glb', 'Arcadian Carapace (heavy tank)', size=1024)
def carapace():
    fn = lensfn(-4.2, 4.2, 3.1, 2.2, 0.62, 1.22, nose=0.9)
    K.layered_hull(fn, extra=True)
    for s in (1, -1):   # great forward horns
        b = K.blade((2.3, s * 0.9, 1.34), 2.7, s * -25, s * 92, 0.85, 0.24, sq=(1.25, 0.85), zone='shell')
        F.rot(b, 'Y', -5, about=(2.3, 0, 1.34))
    K.lifters([(2.3, 0, 0.64), (-2.0, 1.2, 0.66), (-2.0, -1.2, 0.66), (0.3, 1.4, 0.64), (0.3, -1.4, 0.64)], 0.42)
    for s in (1, -1):
        K.fin((-3.0, s * 1.0, 1.76), 2.0, 222, 60, 0.6, 0.08, lean=-s * 10)
        K.fin((-2.2, s * 1.7, 1.42), 1.35, 215, 70, 0.42, 0.06, lean=-s * 26)
        # Reads as: the biggest hull, great horns, and four cores set in a square.
        K.core((2.0, s * 1.5, 1.8), 0.36)
        K.core((-1.3, s * 2.3, 1.75), 0.36)
    K.flanks(8.3, 3.15, 1.42)
    K.slit_eyes(fn, 0.05, v=(66, 114), r=0.09)
    K.thrusters([(-3.9, 0.9, 1.3), (-3.9, -0.9, 1.3)], 1.6, r=0.034)
    tz = 2.1
    with F.group('Turret'):
        turret(tz, L=3.9, w=1.25, h=0.85, x0=-2.2, gun=(6.6, 0.31))
        for s in (1, -1):
            K.fin((-1.2, s * 0.75, tz + 0.3), 1.0, 200, 75, 0.36, 0.05, lean=-s * 24)
            K.barrel(0.2, 3.1, s * 1.0, tz + 0.2, 0.1, prongs=2)
    return dict(pivot=[('Turret', (-0.3, 0, tz))] + K.gun_pivots([('', (0.6, 0, tz + 0.2), (6.8, 0, tz + 0.2))]))


@asset('alien/spitter.glb', 'Arcadian Spitter (missile tank)')
def spitter():
    fn = lensfn(-3.1, 3.2, 1.75, 1.75, 0.62, 1.08, nose=0.72)
    K.layered_hull(fn)
    K.lifters([(1.5, 0, 0.64), (-1.3, 0.8, 0.66), (-1.3, -0.8, 0.66)], 0.34)
    for s in (1, -1):   # twin tail spikes, gold-tipped
        sweep([(-1.6, s * 1.0, 1.1), (-3.1, s * 1.25, 1.25), (-4.4, s * 1.2, 1.6)], [(0.3, 0.16), (0.22, 0.12), (0.03, 0.03)], 'bronze', sides=6)
        sweep([(-3.1, s * 1.25, 1.32), (-3.8, s * 1.23, 1.47), (-4.45, s * 1.2, 1.63)], [(0.06, 0.03), (0.05, 0.03), (0.02, 0.02)], 'gold', sides=4)
    K.slit_eyes(fn, 0.07)
    K.thrusters([(-2.9, 0.4, 1.08), (-2.9, -0.4, 1.08)], 1.2)
    tz = 1.7
    with F.group('Turret'):
        tube((-0.3, 0, tz - 0.05), (-0.3, 0, tz + 0.3), [(0, 0.8), (0.5, 0.7), (1, 0.45)], 16, 'bronze')
        K.ring((-0.3, 0, tz + 0.02), 0.84, 0.024, 'gold', sides=24)
        # Arched spine rack holding six seeker pods, three a side.
        import random
        rnd = random.Random(8)
        pods = []
        for s in (1, -1):
            m = F.mark()
            K.fin((-0.3, 0, tz + 0.25), 1.7, 15, 165, 0.5, 0.08, zone='shell', plane='yz', sq=(1.0, 0.95))
            crescent((-0.3, 0, tz + 0.25), 1.92, 30, 150, 0.06, 0.05, 'gold', n=14, plane='yz', sq=(1.0, 0.95))
            F.move_all(m, (s * 0.75, 0, 0))
        for i, a in enumerate((38, 90, 142)):
            for dx in (-0.75, 0.75):
                y, z = 1.52 * math.cos(math.radians(a)), tz + 0.25 + 1.45 * math.sin(math.radians(a))
                m = F.mark()
                # Reads as: an arch of six bright seeker heads (fatter pods, each with a glowing nose).
                tube((dx - 0.2, y, z), (dx + 0.9, y, z), [(0, 0.13), (0.15, 0.27), (0.6, 0.27), (0.82, 0.2), (1, 0.12)], 10, 'barrel')
                cyl((dx + 0.05, y, z), (dx + 0.3, y, z), 0.285, 10, 'slat')
                K.xring(dx + 0.38, y, z, 0.3, 0.04, 'gold', 10, 0.03)
                cyl((dx - 0.22, y, z), (dx - 0.2, y, z), 0.1, 8, 'glow')
                orb((dx + 0.92, y, z), 0.22, 'core', seg=(8, 6))
                K.arc((dx - 0.2, y, z), (dx - 1.3, y, z), rnd, r=0.03, rough=0.2, depth=2, forks=1, tip=True)   # launch trail
                F.rot_all(m, 'Y', -22, about=(dx, y, z))
                g = f'Pod{i}{"FB"[dx < 0]}'
                F.regroup(m, g)
                pods.append((g, (dx, y, z), g + 'Pivot', 'Turret'))
        K.core((-0.3, 0, tz + 0.75), 0.33)
    return dict(pivot=[('Turret', (-0.3, 0, tz))] + pods)


@asset('alien/mortar_beast.glb', 'Arcadian Mortar Beast (artillery)', size=1024)
def mortar_beast():
    fn = lensfn(-3.6, 3.4, 2.0, 1.85, 0.62, 1.1, nose=0.75)
    K.layered_hull(fn, extra=True)
    K.lifters([(1.6, 0, 0.64), (-1.6, 0.9, 0.66), (-1.6, -0.9, 0.66), (0.0, 0, 0.62)], 0.4)
    K.flanks(7.45, 2.35, 1.2, x=0.0)
    for s in (1, -1):
        K.fin((-2.6, s * 1.1, 1.45), 1.3, 215, 70, 0.42, 0.06, lean=-s * 20)
    K.slit_eyes(fn, 0.06)
    K.thrusters([(-3.4, 0.5, 1.1), (-3.4, -0.5, 1.1)], 1.3)
    tz = 1.8
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.05), (-0.5, 0, tz + 0.5), [(0, 1.1), (0.4, 1.0), (1, 0.6)], 18, 'bronze')
        tube((-0.5, 0, tz + 0.02), (-0.5, 0, tz + 0.12), [(0, 1.12), (1, 1.09)], 18, 'slat')
        K.ring((-0.5, 0, tz + 0.15), 1.08, 0.028, 'gold', sides=24)
        m = F.mark()
        c = (-0.5, 0, tz + 1.75)
        orb(c, 0.8, 'core', seg=(20, 12))
        K.claws((c[0], c[1], c[2] - 1.25), 4, 0.25, 1.75, width=0.5, zone='shell', a0=-40, a1=78, thick=0.09)
        K.claws((c[0], c[1], c[2] - 1.2), 4, 0.5, 1.0, width=0.36, zone='bronze', a0=-35, a1=60, start=0.0)
        K.ring(c, 1.32, 0.08, 'bronze', sides=28)
        K.ring(c, 1.33, 0.03, 'gold', sides=28, flat=3.2)
        K.ring(c, 1.0, 0.022, 'gold', sides=24, flat=2.6, tilt=(0, 62))
        # Accelerator rings stepping down along the firing line above the charge.
        for dz, rr in ((0.78, 0.85), (1.15, 0.62), (1.45, 0.42)):
            K.ring((c[0], c[1], c[2] + dz), rr, 0.04, 'gold', sides=20, flat=1.4)
            K.ring((c[0], c[1], c[2] + dz), rr - 0.05, 0.018, 'glow', sides=20)
        mf = F.mark()
        K.flash(0, 0, 0, 0.3, 'Flash')
        F.rot_all(mf, 'Y', -90)
        F.move_all(mf, (c[0], c[1], c[2] + 1.5))
        F.rot_all(m, 'Y', 24, about=(-0.5, 0, tz + 0.5))
    return dict(pivot=[('Turret', (-0.5, 0, tz)), ('Flash', (-0.5, 0, tz + 2.5), 'FlashPivot', 'Turret')])


@asset('alien/gorger.glb', 'Arcadian Sifter (ore miner)', role='ember')
def gorger():
    fn = lensfn(-3.1, 2.9, 2.3, 1.55, 0.62, 1.06, nose=1.0)
    K.layered_hull(fn, rear=False, tone='worker')
    K.lifters([(1.4, 0, 0.64), (-1.5, 0.85, 0.66), (-1.5, -0.85, 0.66)], 0.34)
    # Ore crop: an open cup of petals behind the middle, heaped with ore.
    c = (-1.35, 0, 1.3)
    lathe([(0.3, 0.0), (1.0, 0.15), (1.35, 0.6), (1.42, 0.6), (1.1, 0.05), (0.3, -0.12)], 20, 'under', center=c)
    K.claws((c[0], c[1], c[2] - 0.1), 5, 0.75, 1.15, width=0.4, zone='shell', a0=-40, a1=70, start=36)
    lathe([(1.36, 0.5), (1.5, 0.62), (1.44, 0.72), (1.3, 0.6)], 24, 'bronze', center=c)
    K.ring((c[0], c[1], c[2] + 0.72), 1.44, 0.028, 'gold', sides=24)
    K.ring((c[0], c[1], c[2] + 0.62), 1.4, 0.04, 'glow', sides=24)
    with F.group('Ore'):   # its own part so the game can show the load
        K.ore_heap((c[0], c[1], c[2] + 0.25), 1.15, 0.55, n=11, seed=4)
    # Feed conduit from the grinder back along one flank to the crop.
    sweep([(2.3, 0.6, 1.02), (1.4, 1.5, 1.25), (-0.2, 1.72, 1.38), (-1.0, 1.25, 1.68)], [(0.13, 0.13)] * 4, 'slat', sides=8)
    for x, y, z in ((1.85, 1.08, 1.14), (0.6, 1.66, 1.33), (-0.6, 1.52, 1.5)):
        orb((x, y, z), 0.17, 'bronze', seg=(8, 6))
    # Feeding mandibles and a toothed grinder drum at the nose.
    for s in (1, -1):
        # Reads as: a beetle with great open jaws round a glowing grinder, ore heaped on its back.
        K.blade((2.5, s * 0.5, 0.95), 2.3, s * -22, s * 100, 0.5, 0.13, sq=(1.15, 0.8), zone='shell')
        K.blade((2.9, s * 0.1, 0.77), 1.25, s * -30, s * 95, 0.22, 0.07, sq=(1.15, 0.8))
        cyl((1.6, s * 0.45, 1.5), (2.75, s * 0.42, 1.2), 0.045, 8, 'barrel')
        cyl((1.6, s * 0.45, 1.5), (2.2, s * 0.435, 1.35), 0.07, 8, 'bronze')
        K.xring(2.3, s * 0.43, 1.32, 0.07, 0.025, 'gold', 8, 0.02)
    gx0, gz = 2.5, 0.92
    tube((gx0, 0, gz), (gx0 + 0.75, 0, gz), [(0, 0.5), (0.5, 0.62), (1, 0.6)], 16, 'bronze')
    for a in range(4):
        b = box((gx0 + 0.5, 0, gz + 0.62), (0.18, 0.04, 0.04), 'gold')
        F.rot(b, 'X', 90 * a + 45, about=(0, 0, gz))
    with F.group('Grinder'):   # its own part so the game can spin it while mining
        L = 0.75
        rr = lambda t: 0.56 - 0.2 * t
        tube((gx0 + 0.75, 0, gz), (gx0 + 0.75 + L, 0, gz), [(0, rr(0)), (1, rr(1)), (1, rr(1) * 0.6), (0.7, 0.1)], 16, 'under', sharp=40)
        cyl((gx0 + 0.72 + L * 0.75, 0, gz), (gx0 + 0.76 + L * 0.75, 0, gz), 0.2, 10, 'glow')
        orb((gx0 + 0.75 + L, 0, gz), 0.26, 'core', seg=(10, 8))          # gold throat
        K.xring(gx0 + 0.75 + L, 0, gz, rr(1) * 1.02, 0.04, 'gold', 16, 0.025)
        for row in range(3):
            for i in range(7):
                t = (i + 0.5) / 7
                x, r, a = gx0 + 0.75 + L * t, rr(t), row * 120 + i * 30
                m = F.mark()
                F.prism([(x - 0.06, gz + r - 0.03), (x + 0.06, gz + r - 0.03), (x + 0.09, gz + r + 0.15), (x + 0.02, gz + r + 0.09)], -0.04, 0.04, 'barrel', bevel=0.008)
                F.rot_all(m, 'X', a, about=(0, 0, gz))
    K.core((1.3, 0, 1.56), 0.22)
    K.thrusters([(-2.95, 0.4, 1.05), (-2.95, -0.4, 1.05)], 1.1)
    return dict(pivot=[('Grinder', (gx0 + 1.0, 0, gz), 'GrinderPivot')])


@asset('alien/ferrier.glb', 'Arcadian Ferrier (cargo tug)', role='ember')
def ferrier():
    # Reads as: a long barge with two straight rails of light and four tall claws round the load.
    fn = lensfn(-3.7, 3.5, 1.95, 1.35, 0.62, 1.0, nose=1.0)
    K.layered_hull(fn, rear=False, tone='worker')
    K.lifters([(1.5, 0, 0.64), (-1.5, 0.85, 0.66), (-1.5, -0.85, 0.66)], 0.34)
    for s in (1, -1):   # cargo rails: long floating tusks held off each flank, a line of ember light along each
        pts = [(-3.9, s * 1.55, 1.5), (-2.2, s * 1.98, 1.42), (-0.4, s * 2.1, 1.4), (1.4, s * 1.98, 1.42), (3.1, s * 1.55, 1.5)]
        sweep(pts, [(0.03, 0.03), (0.2, 0.11), (0.24, 0.13), (0.2, 0.11), (0.03, 0.03)], 'bronze', sides=6)
        sweep([(x, y, z + 0.13) for x, y, z in pts[1:-1]], [(0.11, 0.035)] * 3, 'glow', sides=4)
        sweep([(x, y + s * 0.2, z) for x, y, z in pts], [(0.02, 0.02), (0.05, 0.03), (0.05, 0.03), (0.05, 0.03), (0.02, 0.02)], 'gold', sides=4)
        for x in (-1.9, 0.9):   # struts holding the rail off the hull
            sweep([(x, s * 1.1, 1.15), (x, s * 1.95, 1.38)], [(0.08, 0.08), (0.05, 0.05)], 'bronze', sides=5)
    # Cargo cradle: a ribbed dish with a toothed gold collar, gripped by four tall claws, heaped with ore.
    c = (-1.0, 0, 1.25)
    lathe([(0.2, 0.0), (1.2, 0.08), (1.55, 0.3), (1.62, 0.3), (1.25, -0.02), (0.2, -0.12)], 24, 'under', center=c)
    lathe([(1.2, 0.1), (1.5, 0.28)], 24, 'slat', center=c)
    K.ring((c[0], c[1], c[2] + 0.33), 1.57, 0.035, 'gold', sides=24)
    K.ring((c[0], c[1], c[2] + 0.29), 1.47, 0.02, 'glow', sides=24)
    for k in range(8):
        b = box((1.42, 0, c[2] + 0.33), (0.1, 0.05, 0.03), 'gold')
        F.rot(b, 'Z', 45 * k)
        F.move(b, (c[0], 0, 0))
    with F.group('Ore'):
        K.ore_heap((c[0], c[1], c[2] + 0.1), 1.25, 0.6, n=13, seed=9, crystals=8)
    for k in range(4):
        m = F.mark()
        K.fin((0, 0, 0.1), 1.6, -40, 75, 0.5, 0.1, zone='shell')
        F.move_all(m, (0.25, 0, 0))
        F.rot_all(m, 'Z', 45 + 90 * k)
        F.move_all(m, c)
    K.core((2.3, 0, 1.35), 0.24)
    K.thrusters([(-2.95, 0.4, 1.0), (-2.95, -0.4, 1.0)], 1.1)
    return {}


@asset('alien/weaver.glb', 'Arcadian Weaver (repair)', role='pale')
def weaver():
    # Reads as: a round body under a turning three-armed star, a pale light at each arm tip.
    fn = lensfn(-2.5, 2.5, 2.3, 1.65, 0.62, 1.05, nose=1.0)
    K.layered_hull(fn, tone='worker')
    K.lifters([(1.5, 0, 0.64), (-1.3, 0.8, 0.66), (-1.3, -0.8, 0.66)], 0.34)
    K.thrusters([(-2.4, 0, 1.05)], 0.9)
    tz = 1.6
    tube((-0.2, 0, tz - 0.05), (-0.2, 0, tz + 0.35), [(0, 0.8), (0.5, 0.7), (1, 0.4)], 16, 'bronze')
    for z, r in ((0.1, 0.78), (0.34, 0.42)):
        K.ring((-0.2, 0, tz + z), r, 0.025, 'gold', sides=20)
    with F.group('Halo'):
        # Floating mending halo: a gold-banded ring with inward claws round a bright core, and three
        # weaving arms each ending in a forked gold emitter with a spark across it.
        c = (-0.2, 0, tz + 1.2)
        K.ring(c, 1.25, 0.09, 'shell', sides=32)
        K.ring(c, 1.25, 0.04, 'gold', sides=32, flat=2.3)
        K.ring(c, 1.05, 0.035, 'glow', sides=24)
        for k in range(8):
            a = math.radians(45 * k + 22.5)
            orb((c[0] + 1.25 * math.cos(a), c[1] + 1.25 * math.sin(a), c[2] + 0.08), 0.06, 'gold', seg=(8, 6))
        orb(c, 0.34, 'core', seg=(16, 10))
        K.gimbals(c, 0.5, 2, w=2.0)
        import random
        rnd = random.Random(5)
        for k in range(3):
            m = F.mark()
            K.blade((0, 0, 0), 0.75, 20, 160, 0.26, 0.06, zone='bronze')
            F.move_all(m, (0, 0.45, 0))
            F.rot_all(m, 'Z', 120 * k)
            F.move_all(m, c)
            m = F.mark()
            path = [(1.2, 0, 0.0), (2.1, 0, 0.14), (2.9, 0, 0.05), (3.5, 0, -0.3)]
            sweep(path, [(0.2, 0.13), (0.17, 0.11), (0.12, 0.08), (0.05, 0.04)], 'shell', sides=6)
            sweep([(p[0], 0, p[2] + 0.08) for p in path], [(0.035, 0.025)] * 4, 'gold', sides=4)
            ax, az = 0.7, 0.7   # the emitter fork rides out at the arm tip
            for s in (1, -1):
                sweep([(2.78 + ax, s * 0.03, -0.96 + az), (2.9 + ax, s * 0.2, -1.12 + az), (2.92 + ax, s * 0.14, -1.4 + az)], [(0.05, 0.05), (0.045, 0.045), (0.01, 0.01)], 'gold', sides=5)
            K.arc((2.92 + ax, 0.14, -1.38 + az), (2.92 + ax, -0.14, -1.38 + az), rnd, r=0.02, rough=0.3, depth=2, forks=0)
            orb((2.84 + ax, 0, -1.02 + az), 0.2, 'core', seg=(10, 8))
            F.rot_all(m, 'Z', 120 * k + 60)
            F.move_all(m, c)
    return dict(pivot=('Halo', (-0.2, 0, tz)))


@asset('alien/seer.glb', 'Arcadian Seer (mobile sensor)', role='pale')
def seer():
    # Reads as: a small slim body carrying a tall mast with a crescent moon turning round one pale eye.
    fn = lensfn(-2.5, 2.5, 1.55, 1.55, 0.62, 1.05, nose=0.85)
    K.layered_hull(fn, tone='worker')
    K.lifters([(1.4, 0, 0.64), (-1.2, 0.6, 0.66), (-1.2, -0.6, 0.66)], 0.32)
    K.thrusters([(-2.4, 0, 1.05)], 0.9)
    tz = 1.5
    tube((-0.3, 0, tz - 0.05), (-0.3, 0, tz + 0.3), [(0, 0.75), (0.5, 0.65), (1, 0.4)], 16, 'bronze')
    K.ring((-0.3, 0, tz + 0.1), 0.72, 0.025, 'gold', sides=20)
    with F.group('Eye'):
        # The eye: a large orb with a dark forward pupil, cradled by two tall horns, with flat orbit bands.
        c = (-0.3, 0, tz + 2.7)
        orb(c, 0.7, 'core', seg=(18, 12))
        orb((c[0] + 0.63, 0, c[2]), 0.16, 'under', seg=(8, 8), sq=(0.5, 0.6, 1.5))
        K.xring(c[0] + 0.62, 0, c[2], 0.3, 0.04, 'gold', 14, 0.015)
        for s in (1, -1):
            K.fin((-0.3, 0, tz + 2.15), 1.95, 270 - s * 80, 270 + s * 38 - s * 180, 0.6, 0.09, zone='shell', plane='yz')
        K.ring(c, 1.1, 0.045, 'bronze', sides=24, flat=2.6, tilt=(24, 0))
        K.ring(c, 1.32, 0.04, 'gold', sides=24, flat=2.6, tilt=(-18, 30))
        tube((-0.3, 0, tz + 0.3), (-0.3, 0, tz + 1.6), [(0, 0.32), (1, 0.13)], 10, 'shell')
        for z, r in ((0.5, 0.29), (0.9, 0.23), (1.3, 0.17)):
            K.ring((-0.3, 0, tz + z), r, 0.025, 'gold', sides=12)
    return dict(pivot=('Eye', (-0.3, 0, tz)))


def carrier():
    """Flat-backed hover bed that the towers ride on (built inside the caller's group)."""
    fn = lensfn(-2.9, 2.9, 2.15, 1.3, 0.62, 1.0, nose=1.0)
    K.layered_hull(fn, rear=False, tone='worker')
    K.lifters([(1.5, 0, 0.64), (-1.3, 0.8, 0.66), (-1.3, -0.8, 0.66)], 0.34, flicker=False)
    K.thrusters([(-2.75, 0, 1.02)], 1.0, flicker=False)
    K.core((2.0, 0, 1.27), 0.2)


@asset('alien/thornmound_packed.glb', 'Arcadian Thornmound, packed for transport')
def thornmound_packed():
    carrier()
    # The turret travels as a closed bud: petals folded over the thorn, glow leaking from the seams.
    c = (-0.6, 0, 1.15)
    orb((c[0], c[1], c[2] + 0.55), 0.8, 'slat', seg=(14, 10), sq=(1.25, 1, 0.75))
    for k in range(6):
        m = F.mark()
        sweep([(1.25, 0, 0.0), (1.2, 0, 0.6), (0.7, 0, 1.1), (0.12, 0, 1.3)], [(0.07, 0.5), (0.07, 0.56), (0.06, 0.4), (0.03, 0.08)], 'shell' if k % 2 else 'bronze', sides=6, up=(0, 1, 0), power=0.8)
        F.rot_all(m, 'Z', 60 * k)
        F.scale(F.since(m)[0], (1.25, 1, 1))
        F.move_all(m, c)
    tube((c[0], 0, c[2] + 1.2), (c[0] - 1.6, 0, c[2] + 1.75), [(0, 0.14), (0.8, 0.07), (1, 0.01)], 8, 'barrel')
    K.ring((c[0], c[1], c[2] + 0.05), 1.55, 0.07, 'bronze', sides=20)
    return {}


@asset('alien/spore_tower_packed.glb', 'Arcadian Spore Tower, packed for transport')
def spore_tower_packed():
    carrier()
    # The tower travels lying down: a long closed pod in a cradle of ribs.
    m = F.mark()
    pf = lensfn(-2.4, 1.4, 0.75, 2.35, 0.95, 1.65, nose=0.9)
    body(pf, 'slat', off=-0.05, nu=12, nv=12)
    for vc in (45, 135, 225, 315):
        shell(pf, 0.02, 0.98, vc, 78, 'shell' if vc < 180 else 'bronze', nu=12, nv=5, off=0.03, lift=0.02, shape=0.5)
    for x in (-1.6, -0.5, 0.6):
        K.ring((x, 0, 1.65), 0.85 if x < 0.5 else 0.7, 0.06, 'bronze', sides=18, tilt=(0, 90))
    for s in (1, -1):
        for x in (-1.6, 0.6):
            K.fin((x, s * 0.5, 1.0), 0.75, 180 if s > 0 else 0, 90, 0.26, 0.06, plane='yz')
    return {}


@asset('alien/disc.glb', 'Arcadian Disc (saucer bomber)')
def disc():
    Z = 1.2
    R = 3.0
    top = F.discfn(R, Z + 0.95, Z, p=0.85)
    # Dark ribbed core body, keel bowl, and two tiers of pointed scale armour with gold lips.
    lathe([(0.2, Z + 0.9), (1.4, Z + 0.72), (2.3, Z + 0.38), (2.92, Z + 0.02), (2.5, Z - 0.3), (1.4, Z - 0.6), (0.4, Z - 0.72)], 32, 'slat')
    lathe([(2.6, Z - 0.26), (1.5, Z - 0.6), (0.45, Z - 0.74), (0.4, Z - 0.84), (1.55, Z - 0.7), (2.7, Z - 0.3)], 32, 'under')
    for k in range(8):
        K.plate(top, 0.36, 1.0, 45 * k, 50, 'shell', nu=9, nv=5, off=0.03, lift=0.1, shape=0.22, skew=34, back=0.5)
    for k in range(5):
        K.plate(top, 0.1, 0.6, 72 * k + 15, 78, 'bronze', nu=8, nv=5, off=0.12, lift=0.06, shape=0.25, skew=40)
    K.ring((0, 0, Z + 0.02), R + 0.02, 0.08, 'bronze', sides=40)
    K.ring((0, 0, Z + 0.1), R + 0.03, 0.03, 'gold', sides=40)
    for k in range(12):
        a = math.radians(30 * k + 15)
        orb(((R + 0.1) * math.cos(a), (R + 0.1) * math.sin(a), Z + 0.04), 0.15, 'core', seg=(8, 6))
    # Crown: white-gold core in six slim fins with a tilted ring.
    lathe([(0.75, Z + 0.98), (0.95, Z + 1.2), (0.86, Z + 1.24), (0.62, Z + 1.05)], 18, 'bronze')
    K.ring((0, 0, Z + 1.22), 0.9, 0.025, 'gold', sides=18)
    K.core((0, 0, Z + 1.5), 0.44, cage=4, ring=False)
    # Three sickle blades held off the rim.
    with F.group('Blades'):   # the sickle ring turns slowly in flight
        for k in range(3):
            m = F.mark()
            K.blade((0, 0, 0), R + 0.45, 150, 228, 0.42, 0.07, zone='bronze')
            F.move_all(m, (0, 0, Z + 0.12))
            F.rot_all(m, 'Z', 120 * k)
    # Prow: twin horns, sensor eye and lance give it a front; a raked fin marks the tail.
    for s in (1, -1):
        K.blade((2.6, s * 0.1, Z - 0.1), 1.5, s * -30, s * 105, 0.55, 0.11, sq=(1.25, 0.82), zone='shell')
    K.barrel(2.5, 4.0, 0, Z - 0.12, 0.09, prongs=2)
    # Belly: ring of teardrop bombs round a downward emitter, and lightning lifters on the lower rim.
    for k in range(6):
        a = math.radians(60 * k + 30)
        x, y = 1.35 * math.cos(a), 1.35 * math.sin(a)
        orb((x, y, Z - 0.92), 0.26, 'bronze', seg=(10, 8), sq=(1, 1, 1.5))
        orb((x, y, Z - 1.27), 0.13, 'core', seg=(8, 6))
        K.ring((x, y, Z - 1.1), 0.2, 0.025, 'gold', sides=12)
    K.lifters([(2.3 * math.cos(math.radians(a)), 2.3 * math.sin(math.radians(a)), Z - 0.42) for a in (60, 180, 300)], 0.32)
    with F.group('TurretPod'):
        lathe([(0.75, Z - 0.75), (0.62, Z - 0.98), (0.3, Z - 1.1), (0.02, Z - 1.12)], 14, 'bronze')
        cyl((0, 0, Z - 1.13), (0, 0, Z - 1.08), 0.28, 12, 'glow')
        tube((0.2, 0, Z - 0.98), (1.15, 0, Z - 1.06), [(0, 0.1), (0.8, 0.07), (1, 0.09)], 8, 'barrel')
    K.thrusters([(-3.0, 0.5, Z + 0.1), (-3.0, -0.5, Z + 0.1)], 1.4)
    return dict(name='KeshDisc', pivot=[('TurretPod', (0, 0, Z - 0.75)), ('Blades', (0, 0, Z + 0.12), 'BladesPivot')])


@asset('alien/halo.glb', 'Arcadian Halo (fighter)')
def halo():
    import compat
    compat.install()
    import aircraft2
    aircraft2.halo()
    return dict(name='KeshHalo', single=True)


@asset('alien/dragonfly.glb', 'Arcadian Dragonfly (fighter)')
def dragonfly():
    import random
    Z = 1.15
    # Thorax and head: a compact layered lens hull with big caged gold eyes at the nose.
    fn = lensfn(-1.1, 2.3, 0.78, Z + 0.72, Z - 0.5, Z + 0.05, nose=0.75)
    K.layered_hull(fn, sides=False, rear=True)
    for s in (1, -1):
        K.core((1.72, s * 0.44, Z + 0.3), 0.31, ring=False)
        # Twin lances under the chin.
        tube((1.2, s * 0.26, Z - 0.3), (3.3, s * 0.26, Z - 0.3), [(0, 0.11), (0.15, 0.13), (0.2, 0.065), (0.92, 0.05), (0.94, 0.085), (1, 0.085)], 8, 'barrel')
        cyl((3.29, s * 0.26, Z - 0.3), (3.31, s * 0.26, Z - 0.3), 0.06, 8, 'glow')
        # Legs folded back under the thorax.
        for x in (1.0, 0.4, -0.2):
            sweep([(x, s * 0.4, Z - 0.3), (x + 0.2, s * 0.85, Z - 0.5), (x - 0.5, s * 0.6, Z - 0.72)],
                  [(0.055, 0.055), (0.04, 0.04), (0.015, 0.015)], 'bronze', sides=5)
        # Wing-root shoulders.
        orb((0.25, s * 0.42, Z + 0.48), 0.32, 'bronze', seg=(10, 8), sq=(2.3, 0.8, 0.6))
    K.core((0.55, 0, Z + 0.74), 0.24)
    sweep([(1.1, 0, Z + 0.66), (-0.8, 0, Z + 0.63)], [(0.035, 0.03), (0.035, 0.03)], 'glow', sides=4)
    for s in (1, -1):
        sweep([(0.9, s * 0.2, Z + 0.6), (-0.8, s * 0.2, Z + 0.57)], [(0.05, 0.05), (0.05, 0.05)], 'bronze', sides=4, power=1.6)

    # Long tail in three jointed sections, so it can flex. Straight lines run down its back.
    x, r, zc = -0.8, 0.5, Z + 0.05
    joints = []
    for k in range(9):
        if k % 3 == 0:
            joints.append((x, 0, zc))
        with F.group(f'Tail{k // 3 + 1}'):
            ln = 0.84 - k * 0.025
            r1 = r * 0.885
            tube((x, 0, zc), (x - ln, 0, zc), [(0, r * 0.72), (0.18, r), (0.7, r * 0.92), (1, r1 * 0.7)], 10,
                 'shell' if k % 2 == 0 else 'bronze')
            K.ring((x - ln, 0, zc), r1 * 0.78, 0.035, 'glow', sides=10, tilt=(0, 90))
            sweep([(x + 0.05, 0, zc + r + 0.05), (x - ln, 0, zc + r1 + 0.05)], [(0.03, 0.025), (0.026, 0.022)], 'glow', sides=4)
            for s in (1, -1):
                sweep([(x + 0.05, s * r * 0.42, zc + r * 0.93), (x - ln, s * r1 * 0.42, zc + r1 * 0.93)],
                      [(0.04, 0.04), (0.035, 0.035)], 'bronze', sides=4, power=1.6)
            x, r = x - ln, r1
    with F.group('Tail3'):   # claspers and a charged sting at the tip
        for s in (1, -1):
            K.blade((x - 0.05, s * 0.75, zc), 0.75, s * -80, s * -190, 0.3, 0.06)
        tube((x + 0.05, 0, zc), (x - 1.1, 0, zc + 0.12), [(0, r * 0.7), (0.3, r * 0.45), (1, 0.02)], 8, 'barrel')
        orb((x - 0.22, 0, zc + 0.03), r * 0.62, 'core', seg=(10, 8))
    mf = F.mark()   # discharge from the sting when it fires
    K.flash(0, 0, 0, 0.17, 'Sting')
    F.rot_all(mf, 'Z', 180)
    F.move_all(mf, (x - 1.1, 0, zc + 0.12))

    # Electricity: thin white-hot cores with a soft gold halo, jagged by midpoint displacement, with tapering forks.
    from mathutils import Vector

    def arc(p0, p1, rnd, r=0.042, rough=0.2, depth=4, forks=2, zj=1.0, tip=False):
        pts = [Vector(p0), Vector(p1)]
        for _ in range(depth):
            out = [pts[0]]
            for u, v in zip(pts[:-1], pts[1:]):
                j = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1) * zj)) * (v - u).length * rough
                out += [(u + v) / 2 + j, v]
            pts = out
        n = len(pts)
        w = [(1.0 - 0.9 * i / (n - 1)) if tip else (0.3 + 0.7 * math.sin(math.pi * i / (n - 1)) ** 0.5) for i in range(n)]
        path = [tuple(q) for q in pts]
        sweep(path, [(r * k, r * k) for k in w], 'bolt', sides=3, caps=False)
        sweep(path, [(r * 3.6 * k, r * 3.6 * k) for k in w], 'halo', sides=4, caps=False)
        span = (pts[-1] - pts[0]).length
        for _ in range(forks):
            i = rnd.randint(max(1, n // 5), n - 3)
            d = (pts[i + 1] - pts[i - 1]).normalized()
            side = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 1) * zj)).normalized()
            end = pts[i] + (d * 0.7 + side * 0.75).normalized() * span * rnd.uniform(0.22, 0.42)
            arc(pts[i], end, rnd, r * 0.62, rough, max(2, depth - 1), forks - 1, zj, tip=True)
        return pts

    # Four very long scythe wings: swept, hooked tip, barbed trailing edge, gold spar and fine gold line work.
    # Each is its own part so the pairs can beat out of step.
    def wing(group, root, L, c, dihedral, back, s):
        with F.group(group):
            m = F.mark()
            P = lambda a, b, z=0.014: (a * c, s * b * L, z)
            lead = [(0.08, 0.0), (0.14, 0.08), (0.17, 0.28), (0.17, 0.52), (0.13, 0.7), (0.06, 0.84), (-0.08, 0.93), (-0.34, 1.0)]
            barbs = [(-0.8, 0.868), (-1.04, 0.715), (-1.14, 0.515), (-1.04, 0.305)]
            notches = [(-0.3, 0.9), (-0.42, 0.765), (-0.52, 0.575), (-0.58, 0.365), (-0.56, 0.15)]
            trail = [notches[0]]
            for bb, nn in zip(barbs, notches[1:]):
                trail += [bb, nn]
            trail.append((-0.42, 0.02))
            F.plate([(a * c, s * b * L) for a, b in lead + trail], -0.01, 0.01, 'wing')
            # Heavy gold leading spar that ends in the hooked tip, with thorns along it.
            sweep([P(a, b, 0.012) for a, b in lead], [(0.1, 0.08), (0.095, 0.075), (0.085, 0.066), (0.072, 0.056), (0.06, 0.046), (0.046, 0.036), (0.034, 0.026), (0.008, 0.008)],
                  'gold', sides=6)
            sweep([P(a - 0.04, b, 0.06) for a, b in lead[:-1]], [(0.014, 0.014)] * 6 + [(0.008, 0.008)], 'glow', sides=4)
            for b in (0.2, 0.36, 0.52, 0.67, 0.8):
                a = 0.17 if b < 0.6 else (0.13 if b < 0.75 else 0.08)
                sweep([P(a - 0.02, b - 0.012), P(a + 0.3 / c * (1 - b * 0.5), b + 0.03)], [(0.05, 0.04), (0.004, 0.004)], 'gold', sides=5)
            # Gold rim tracing the barbed trailing edge.
            edge = [(-0.34, 1.0)] + trail
            for q0, q1 in zip(edge[:-1], edge[1:]):
                sweep([P(*q0), P(*q1)], [(0.02, 0.014), (0.02, 0.014)], 'glow', sides=4)
            # Main veins from the root to the tip and to every barb, finer veins to the notches.
            sweep([P(-0.05, 0.015), P(-0.3, 0.985)], [(0.022, 0.014), (0.01, 0.008)], 'glow', sides=4)
            for (a1, b1), (na, nb) in zip(barbs, notches[1:]):   # bend inside the membrane, then out along the barb
                wp = P(-0.22, nb + 0.03)
                sweep([P(-0.05, 0.015), wp], [(0.02, 0.013), (0.014, 0.01)], 'glow', sides=4)
                sweep([wp, P(a1, b1)], [(0.014, 0.01), (0.008, 0.007)], 'glow', sides=4)
            for a1, b1 in notches:
                sweep([P(-0.1, 0.02), P(a1, b1)], [(0.011, 0.008), (0.006, 0.005)], 'glow', sides=4)
            # Fine cross lines, a dense ladder all the way out.
            n = 22
            for i in range(1, n):
                b = 0.05 + 0.88 * i / n
                back_a = -0.5 if b < 0.86 else -0.25
                la = 0.15 if b < 0.6 else 0.15 - (b - 0.6) * 0.5
                sweep([P(la, b), P(back_a, b + 0.015)], [(0.0075, 0.006), (0.005, 0.004)], 'glow', sides=4)
            # Bright root orb.
            orb((0, s * 0.05, 0.03), 0.14, 'glow', seg=(8, 6))
            for v in (1, 2):   # two different crawls of electricity along the spar, shown at different moments
                rnd = random.Random(sum(map(ord, group)) * 7 + v)
                with F.group(f'Arc{group[4:]}{v}'):
                    far = rnd.uniform(0.3, 0.42) if v == 1 else rnd.uniform(0.5, 0.68)
                    pts = arc(P(0.0, 0.004, 0.1), P(0.12, far, 0.1), rnd, r=0.046, rough=0.11, depth=4, forks=0, zj=0.5)
                    for k in sorted(rnd.sample(range(3, len(pts) - 1), 3)):
                        q = pts[k]
                        arc(q, (q[0] - rnd.uniform(0.5, 0.95) * c, q[1] + s * rnd.uniform(0.2, 1.1), 0.06), rnd, r=0.03, rough=0.2, depth=3, forks=1, zj=0.3, tip=True)
            F.rot_all(m, 'X', s * dihedral)
            F.rot_all(m, 'Z', s * back)
            F.move_all(m, root)
    pivots, wing_arcs = [], []
    for s, side in ((1, 'L'), (-1, 'R')):
        for name, rx, rz, L, c, dih, back in (('F', 0.78, 0.52, 13.0, 1.5, 8, 6), ('H', -0.22, 0.47, 11.0, 1.7, 4, 24)):
            root = (rx, s * 0.36, Z + rz)
            wing(f'Wing{name}{side}', root, L, c, dih, back, s)
            pivots.append((f'Wing{name}{side}', root, f'Wing{name}{side}Pivot'))
            wing_arcs += [(f'Arc{name}{side}{v}', root, f'Arc{name}{side}{v}Pivot', f'Wing{name}{side}') for v in (1, 2)]
    pivots += [('Tail1', joints[0], 'Tail1Pivot'), ('Tail2', joints[1], 'Tail2Pivot', 'Tail1'), ('Tail3', joints[2], 'Tail3Pivot', 'Tail2')]

    pivots += wing_arcs
    # Body electricity: four different sets. The game shows one at a time, changing fast.
    heart = (0.55, 0, Z + 0.98)
    roots = {(n, sd): (rx, sd * 0.36, Z + rz + 0.12) for n, rx, rz in (('F', 0.78, 0.52), ('H', -0.22, 0.47)) for sd in (1, -1)}
    for gi, gname in enumerate(('ArcA', 'ArcB', 'ArcC', 'ArcD')):
        rnd = random.Random(170 + gi)
        sd = 1 if gi % 2 == 0 else -1
        with F.group(gname):
            arc(heart, (-1.4 - rnd.uniform(0.0, 1.6), rnd.uniform(-0.2, 0.2), Z + 0.68), rnd, rough=0.13, forks=2, zj=0.7)
            arc(heart, (1.72, sd * 0.44, Z + 0.64), rnd, r=0.034, rough=0.16, depth=3, forks=1, zj=0.6)
            arc((3.3, 0.26, Z - 0.3), (3.3, -0.26, Z - 0.3), rnd, r=0.02, rough=0.24, depth=3, forks=0)
            arc(roots[('F', sd)], roots[('H', sd)], rnd, r=0.034, rough=0.22, depth=3, forks=1)
            arc(roots[('F', -sd)], roots[('H', sd)] if gi > 1 else roots[('F', sd)], rnd, r=0.034, rough=0.2, depth=3, forks=0)
            for _ in range(3):   # short corona spikes off the dorsal core
                arc(heart, (heart[0] + rnd.uniform(-0.9, 0.9), rnd.uniform(-0.9, 0.9), heart[2] + rnd.uniform(0.25, 0.8)), rnd, r=0.024, rough=0.22, depth=3, forks=1, tip=True)
    # Lightning thruster (Arcadians fly on lightning): a forked jet of arcs streaming back off the tail sting.
    # Three variants ride on the last tail section; the game shows one at a time while it flies.
    for gi, gname in enumerate(('ThrustA', 'ThrustB', 'ThrustC')):
        rnd = random.Random(310 + gi)
        with F.group(gname):
            src = [(x - 1.05, 0, zc + 0.12), (x - 0.75, 0.62, zc), (x - 0.75, -0.62, zc)]
            for k in range(5):
                p0 = src[0] if k < 3 else src[k - 2]
                ln = rnd.uniform(2.6, 4.4) if k < 3 else rnd.uniform(1.4, 2.4)
                arc(p0, (p0[0] - ln, p0[1] * 0.4 + rnd.uniform(-0.7, 0.7), p0[2] + rnd.uniform(-0.6, 0.6)), rnd,
                    r=0.06 if k < 3 else 0.04, rough=0.15, depth=4 if k < 3 else 3, forks=2 if k < 3 else 1, tip=True)
            arc(src[1], src[2], rnd, r=0.03, rough=0.2, depth=3, forks=0)
        pivots.append((gname, joints[2], gname + 'Pivot', 'Tail3'))
    for gi, gname in enumerate(('LiftA', 'LiftB')):   # lift arcs striking down from the belly pad
        rnd = random.Random(350 + gi)
        with F.group(gname):
            for _ in range(3):
                arc((0.6 + rnd.uniform(-0.2, 0.2), rnd.uniform(-0.15, 0.15), Z - 0.55), (0.6 + rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), Z - 1.1 - rnd.uniform(0, 0.25)), rnd,
                    r=0.03, rough=0.2, depth=3, forks=1, tip=True)
    K.lifters([(0.6, 0, Z - 0.5)], 0.3)
    pivots.append(('Sting', joints[2], 'StingPivot', 'Tail3'))
    return dict(name='KeshDragonfly', clear=('wing', 'halo'), clear_alpha=0.3, pivot=pivots)
