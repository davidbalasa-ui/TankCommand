"""Kesh units, art pass v2."""
import math

import forge as F
from forge import body, box, crescent, cyl, lathe, lensfn, orb, shell, sweep, tube, sym
import kesh_kit as K

ASSETS = {}


def asset(path, label, size=512):
    def deco(fn):
        def run(glb, render, report):
            F.begin('kesh')
            kw = fn() or {}
            F.finish(kw.pop('name', fn.__name__.title().replace('_', '')), glb, render=render, report=report,
                     label=label, size=kw.pop('size', size), crevice=(0.75, 0.55, 0.4), **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='kesh')
        return run
    return deco


def turret(tz, L=2.9, w=0.85, h=0.62, x0=-1.6, gun=(5.4, 0.15), crest=True):
    """Low layered turret with an energy barrel and a small crest fin."""
    tf = lensfn(x0, x0 + L, w, tz + h, tz - 0.1, tz + 0.16, nose=0.85)
    body(tf, 'under', off=-0.04, nu=10, nv=12)
    shell(tf, 0.0, 0.55, 90, 150, 'shell', nu=8, nv=6, off=0.03, lift=0.04, shape=0.5)
    shell(tf, 0.38, 1.0, 90, 110, 'bronze', nu=8, nv=6, off=0.09, lift=0.1, shape=0.55)
    for vc in (10, 170):
        shell(tf, 0.12, 0.95, vc, 56, 'shell', nu=8, nv=4, off=0.08, lift=0.08)
    if gun:
        K.barrel(x0 + L * 0.72, gun[0], 0, tz + 0.2, gun[1])
    if crest:
        K.fin((x0 + L * 0.3, 0, tz + 0.35), 0.8, 205, 80, 0.3, 0.05)


@asset('alien/stinger.glb', 'Kesh Stinger (light tank)')
def stinger():
    fn = lensfn(-3.3, 3.5, 1.8, 1.8, 0.5, 1.05, nose=0.72)
    K.layered_hull(fn)
    K.lifters([(1.6, 0, 0.5), (-1.4, 0.8, 0.52), (-1.4, -0.8, 0.52)], 0.34)
    for s in (1, -1):
        # Rear crest fins sweeping up and forward, and a long blade hugging each flank.
        K.fin((-2.3, s * 0.8, 1.45), 1.6, 220, 62, 0.46, 0.06, lean=-s * 12)
    K.flanks(6.6, 1.85, 1.2)
    K.core((1.7, 0, 1.5), 0.26)
    tz = 1.72
    with F.group('Turret'):
        turret(tz)
    return dict(pivot=('Turret', (-0.2, 0, tz)))


@asset('alien/darter.glb', 'Kesh Darter (scout)')
def darter():
    fn = lensfn(-2.6, 3.6, 1.05, 1.45, 0.55, 0.95, nose=0.6)
    K.layered_hull(fn, sides=False)
    K.lifters([(1.4, 0, 0.55), (-1.3, 0, 0.56)], 0.28)
    for s in (1, -1):
        # Forward-swept pincer blades and a raked tail fin.
        # Forward-swept pincer blade, slim and raised.
        b = K.blade((1.0, s * 0.1, 1.05), 2.0, s * 12, s * 150, 0.22, 0.06, sq=(1.5, 0.72))
        F.rot(b, 'X', -s * 10, about=(1.0, 0, 1.05))
        K.fin((-1.9, s * 0.45, 1.2), 1.1, 215, 75, 0.34, 0.05, lean=-s * 22)
    orb((2.1, 0, 1.22), 0.16, 'core', seg=(12, 8))
    tz = 1.42
    with F.group('Turret'):
        tf = lensfn(-1.1, 0.7, 0.5, tz + 0.4, tz - 0.08, tz + 0.12, nose=0.85)
        body(tf, 'under', off=-0.03, nu=8, nv=10)
        shell(tf, 0.0, 1.0, 90, 150, 'shell', nu=8, nv=6, off=0.03, lift=0.05, shape=0.5)
        for s in (1, -1):
            tube((0.2, s * 0.28, tz + 0.14), (2.6, s * 0.28, tz + 0.14), [(0, 0.1), (0.2, 0.1), (0.22, 0.06), (0.9, 0.05), (0.92, 0.08), (1, 0.085)], 8, 'barrel')
            cyl((0.25, s * 0.28, tz + 0.14), (1.0, s * 0.28, tz + 0.14), 0.075, 8, 'slat')
            cyl((2.59, s * 0.28, tz + 0.14), (2.61, s * 0.28, tz + 0.14), 0.06, 8, 'glow')
    return dict(pivot=('Turret', (-0.2, 0, tz)))


@asset('alien/glider.glb', 'Kesh Glider (hover tank)')
def glider():
    fn = lensfn(-2.6, 3.0, 1.15, 1.6, 0.6, 1.05, nose=0.7)
    K.layered_hull(fn, sides=False)
    K.lifters([(1.2, 0, 0.6), (-1.2, 0, 0.6)], 0.3)
    for s in (1, -1):
        # Scythe wings: a long swept blade and a shorter one behind it, raked up at the tips.
        b1 = K.blade((0.4, s * 2.5, 1.02), 2.2, s * -60, s * -172, 0.95, 0.09, zone='shell')
        F.rot(b1, 'X', s * 7, about=(0, 0, 1.0))
        b2 = K.blade((-0.7, s * 2.0, 1.14), 1.6, s * -60, s * -170, 0.6, 0.07)
        F.rot(b2, 'X', s * 12, about=(0, 0, 1.1))
        K.fin((-1.9, s * 0.5, 1.3), 1.0, 215, 80, 0.3, 0.05, lean=-s * 18)
        # Fixed twin lances under the nose.
        tube((1.2, s * 0.55, 0.92), (4.3, s * 0.55, 0.92), [(0, 0.14), (0.15, 0.16), (0.2, 0.08), (0.92, 0.06), (0.94, 0.1), (1, 0.1)], 8, 'barrel')
        cyl((1.7, s * 0.55, 0.92), (2.6, s * 0.55, 0.92), 0.1, 8, 'slat')
        cyl((4.29, s * 0.55, 0.92), (4.31, s * 0.55, 0.92), 0.075, 8, 'glow')
    K.core((0.3, 0, 1.72), 0.3)
    return {}


@asset('alien/carapace.glb', 'Kesh Carapace (heavy tank)', size=1024)
def carapace():
    fn = lensfn(-4.2, 4.2, 3.1, 2.15, 0.5, 1.15, nose=0.9)
    K.layered_hull(fn, extra=True)
    for s in (1, -1):   # great forward horns
        K.blade((2.3, s * 0.9, 1.25), 2.7, s * -25, s * 92, 0.55, 0.14, sq=(1.25, 0.85), zone='shell')
    K.lifters([(2.2, 0, 0.5), (-2.0, 1.1, 0.52), (-2.0, -1.1, 0.52), (0.2, 0, 0.45)], 0.42)
    for s in (1, -1):
        K.fin((-3.0, s * 1.0, 1.7), 2.0, 222, 60, 0.6, 0.08, lean=-s * 10)
        K.fin((-2.2, s * 1.7, 1.35), 1.35, 215, 70, 0.42, 0.06, lean=-s * 26)
        K.core((1.9, s * 1.05, 1.52), 0.24)
    K.flanks(8.3, 3.15, 1.35)
    tz = 2.05
    with F.group('Turret'):
        turret(tz, L=3.9, w=1.25, h=0.85, x0=-2.2, gun=(7.2, 0.22))
        for s in (1, -1):
            K.fin((-1.2, s * 0.75, tz + 0.3), 1.0, 200, 75, 0.36, 0.05, lean=-s * 24)
            tube((0.2, s * 1.0, tz + 0.2), (3.0, s * 1.0, tz + 0.2), [(0, 0.16), (0.2, 0.18), (0.25, 0.09), (0.9, 0.07), (0.93, 0.11), (1, 0.11)], 8, 'barrel')
            cyl((0.9, s * 1.0, tz + 0.2), (1.7, s * 1.0, tz + 0.2), 0.11, 8, 'slat')
            cyl((2.99, s * 1.0, tz + 0.2), (3.01, s * 1.0, tz + 0.2), 0.085, 8, 'glow')
    return dict(pivot=('Turret', (-0.3, 0, tz)))


@asset('alien/spitter.glb', 'Kesh Spitter (missile tank)')
def spitter():
    fn = lensfn(-3.1, 3.2, 1.75, 1.7, 0.5, 1.02, nose=0.72)
    K.layered_hull(fn)
    K.lifters([(1.5, 0, 0.5), (-1.3, 0.8, 0.52), (-1.3, -0.8, 0.52)], 0.34)
    for s in (1, -1):   # twin tail spikes
        sweep([(-1.6, s * 1.0, 1.05), (-3.4, s * 1.25, 1.2), (-5.2, s * 1.2, 1.55)], [(0.3, 0.16), (0.22, 0.12), (0.03, 0.03)], 'bronze', sides=6)
    tz = 1.65
    with F.group('Turret'):
        tube((-0.3, 0, tz - 0.05), (-0.3, 0, tz + 0.3), [(0, 0.8), (0.5, 0.7), (1, 0.45)], 12, 'bronze')
        # Arched spine rack holding six seeker pods, three a side.
        for s in (1, -1):
            m = F.mark()
            K.fin((-0.3, 0, tz + 0.25), 1.7, 15, 165, 0.5, 0.08, zone='shell', plane='yz', sq=(1.0, 0.95))
            F.rot_all(m, 'Z', 0)
            F.move_all(m, (s * 0.75, 0, 0))
        for i, a in enumerate((38, 90, 142)):
            for dx in (-0.75, 0.75):
                y, z = 1.52 * math.cos(math.radians(a)), tz + 0.25 + 1.45 * math.sin(math.radians(a))
                m = F.mark()
                tube((dx - 0.2, y, z), (dx + 0.9, y, z), [(0, 0.1), (0.15, 0.2), (0.6, 0.2), (0.85, 0.13), (1, 0.02)], 10, 'barrel')
                cyl((dx + 0.05, y, z), (dx + 0.3, y, z), 0.215, 10, 'slat')
                F.rot_all(m, 'Y', -22, about=(dx, y, z))
        K.core((-0.3, 0, tz + 0.75), 0.36)
    return dict(pivot=('Turret', (-0.3, 0, tz)))


@asset('alien/mortar_beast.glb', 'Kesh Mortar Beast (artillery)', size=1024)
def mortar_beast():
    fn = lensfn(-3.6, 3.4, 2.0, 1.8, 0.5, 1.05, nose=0.75)
    K.layered_hull(fn, extra=True)
    K.lifters([(1.6, 0, 0.5), (-1.6, 0.9, 0.52), (-1.6, -0.9, 0.52)], 0.4)
    K.flanks(7.45, 2.35, 1.15, x=0.0)
    for s in (1, -1):
        K.fin((-2.6, s * 1.1, 1.4), 1.3, 215, 70, 0.42, 0.06, lean=-s * 20)
    tz = 1.75
    with F.group('Turret'):
        tube((-0.5, 0, tz - 0.05), (-0.5, 0, tz + 0.5), [(0, 1.1), (0.4, 1.0), (1, 0.6)], 14, 'bronze')
        m = F.mark()
        c = (-0.5, 0, tz + 1.75)
        orb(c, 0.85, 'core', seg=(20, 12))
        K.claws((c[0], c[1], c[2] - 1.25), 4, 0.25, 1.75, width=0.5, zone='shell', a0=-40, a1=78, thick=0.09)
        K.claws((c[0], c[1], c[2] - 1.2), 4, 0.5, 1.0, width=0.36, zone='bronze', a0=-35, a1=60, start=0.0)
        K.ring(c, 1.32, 0.08, 'bronze', sides=24)
        K.ring((c[0], c[1], c[2] + 0.75), 0.85, 0.05, 'glow', sides=20)
        F.rot_all(m, 'Y', 24, about=(-0.5, 0, tz + 0.5))
    return dict(pivot=('Turret', (-0.5, 0, tz)))


@asset('alien/gorger.glb', 'Kesh Gorger (ore miner)')
def gorger():
    fn = lensfn(-3.1, 2.9, 2.3, 1.5, 0.5, 1.0, nose=1.0)
    K.layered_hull(fn, rear=False, tone='worker')
    K.lifters([(1.4, 0, 0.5), (-1.5, 0.8, 0.52), (-1.5, -0.8, 0.52)], 0.34)
    # Ore crop: an open cup of petals behind the middle, where the mined ore shows.
    c = (-1.35, 0, 1.25)
    lathe([(0.3, 0.0), (1.0, 0.15), (1.35, 0.6), (1.42, 0.6), (1.1, 0.05), (0.3, -0.12)], 16, 'under', center=c)
    K.claws((c[0], c[1], c[2] - 0.1), 5, 0.75, 1.15, width=0.4, zone='shell', a0=-40, a1=70, start=36)
    lathe([(1.36, 0.5), (1.5, 0.62), (1.44, 0.72), (1.3, 0.6)], 16, 'bronze', center=c)
    K.ring((c[0], c[1], c[2] + 0.62), 1.4, 0.05, 'glow', sides=20)
    # Feeding mandibles and a glowing grinder maw at the nose.
    for s in (1, -1):
        K.blade((2.6, s * 0.15, 0.85), 1.7, s * -35, s * 100, 0.28, 0.1, sq=(1.15, 0.8), zone='shell')
        K.blade((2.9, s * 0.1, 0.7), 1.1, s * -30, s * 95, 0.18, 0.07, sq=(1.15, 0.8))
    m = F.mark()
    tube((2.5, 0, 0.85), (3.5, 0, 0.85), [(0, 0.5), (0.5, 0.55), (1, 0.4)], 12, 'bronze')
    cyl((3.48, 0, 0.85), (3.52, 0, 0.85), 0.34, 12, 'slat')
    for k in range(8):
        t = box((3.56, 0, 0.85 + 0.33), (0.12, 0.05, 0.06), 'barrel')
        F.rot(t, 'X', 45 * k, about=(0, 0, 0.85))
    K.core((1.3, 0, 1.5), 0.24)
    return {}


@asset('alien/ferrier.glb', 'Kesh Ferrier (cargo tug)')
def ferrier():
    fn = lensfn(-3.1, 3.0, 2.35, 1.3, 0.5, 0.95, nose=1.0)
    K.layered_hull(fn, rear=False, tone='worker')
    K.lifters([(1.5, 0, 0.5), (-1.5, 0.8, 0.52), (-1.5, -0.8, 0.52)], 0.34)
    # Cargo cradle: a shallow dish gripped by four tall claws.
    c = (-1.0, 0, 1.2)
    lathe([(0.2, 0.0), (1.2, 0.08), (1.55, 0.3), (1.62, 0.3), (1.25, -0.02), (0.2, -0.12)], 16, 'under', center=c)
    lathe([(1.2, 0.1), (1.5, 0.28), (1.52, 0.31)], 16, 'glow', center=c)
    for k in range(4):
        m = F.mark()
        K.fin((0, 0, 0.1), 1.25, -40, 75, 0.36, 0.07, zone='shell')
        F.move_all(m, (0.5, 0, 0))
        F.rot_all(m, 'Z', 45 + 90 * k)
        F.move_all(m, c)
    K.core((1.9, 0, 1.3), 0.26)
    return {}


@asset('alien/weaver.glb', 'Kesh Weaver (repair)')
def weaver():
    fn = lensfn(-2.8, 2.8, 2.15, 1.6, 0.5, 1.0, nose=1.0)
    K.layered_hull(fn, tone='worker')
    K.lifters([(1.5, 0, 0.5), (-1.3, 0.8, 0.52), (-1.3, -0.8, 0.52)], 0.34)
    tz = 1.55
    tube((-0.2, 0, tz - 0.05), (-0.2, 0, tz + 0.35), [(0, 0.8), (0.5, 0.7), (1, 0.4)], 12, 'bronze')
    with F.group('Halo'):
        # Floating mending halo: a ring with inward claws round a bright core, and three weaving arms.
        c = (-0.2, 0, tz + 1.2)
        K.ring(c, 1.25, 0.09, 'shell', sides=24)
        K.ring(c, 1.05, 0.035, 'glow', sides=24)
        orb(c, 0.36, 'core', seg=(16, 10))
        for k in range(3):
            m = F.mark()
            K.blade((0, 0, 0), 0.75, 20, 160, 0.26, 0.06, zone='bronze')
            F.move_all(m, (0, 0.45, 0))
            F.rot_all(m, 'Z', 120 * k)
            F.move_all(m, c)
            m = F.mark()
            sweep([(1.2, 0, 0.0), (1.9, 0, -0.1), (2.5, 0, -0.5), (2.8, 0, -1.0)], [(0.08, 0.1), (0.07, 0.09), (0.05, 0.06), (0.015, 0.02)], 'shell', sides=6)
            orb((2.8, 0, -1.05), 0.1, 'glow', seg=(10, 6))
            F.rot_all(m, 'Z', 120 * k + 60)
            F.move_all(m, c)
    return dict(pivot=('Halo', (-0.2, 0, tz)))


@asset('alien/seer.glb', 'Kesh Seer (mobile sensor)')
def seer():
    fn = lensfn(-2.6, 2.6, 2.0, 1.5, 0.5, 1.0, nose=1.0)
    K.layered_hull(fn, tone='worker')
    K.lifters([(1.4, 0, 0.5), (-1.2, 0.75, 0.52), (-1.2, -0.75, 0.52)], 0.32)
    tz = 1.45
    tube((-0.3, 0, tz - 0.05), (-0.3, 0, tz + 0.3), [(0, 0.75), (0.5, 0.65), (1, 0.4)], 12, 'bronze')
    with F.group('Eye'):
        # The eye: a large orb cradled by two tall horns, with two tilted orbit rings.
        c = (-0.3, 0, tz + 2.0)
        orb(c, 0.62, 'core', seg=(18, 12))
        for s in (1, -1):
            K.fin((-0.3, 0, tz + 1.55), 1.5, 270 - s * 80, 270 + s * 38 - s * 180, 0.36, 0.07, zone='shell', plane='yz')
        K.ring(c, 0.95, 0.045, 'bronze', sides=24, tilt=(24, 0))
        K.ring(c, 1.12, 0.035, 'glow', sides=24, tilt=(-18, 30))
        tube((-0.3, 0, tz + 0.3), (-0.3, 0, tz + 1.0), [(0, 0.3), (1, 0.12)], 8, 'shell')
    return dict(pivot=('Eye', (-0.3, 0, tz)))


def carrier():
    fn = lensfn(-2.9, 2.9, 2.15, 1.25, 0.5, 0.95, nose=1.0)
    K.layered_hull(fn, rear=False, tone='worker')
    K.lifters([(1.5, 0, 0.5), (-1.3, 0.8, 0.52), (-1.3, -0.8, 0.52)], 0.34)
    K.core((2.0, 0, 1.22), 0.2)


@asset('alien/thornmound_packed.glb', 'Kesh Thornmound, packed for transport')
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


@asset('alien/spore_tower_packed.glb', 'Kesh Spore Tower, packed for transport')
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


@asset('alien/disc.glb', 'Kesh Disc (saucer bomber)')
def disc():
    Z = 1.2
    R = 3.0
    top = F.discfn(R, Z + 0.95, Z, p=0.85)
    # Glowing ribbed core body, keel bowl, and two tiers of radial petal armour.
    lathe([(0.2, Z + 0.9), (1.4, Z + 0.72), (2.3, Z + 0.38), (2.92, Z + 0.02), (2.5, Z - 0.3), (1.4, Z - 0.6), (0.4, Z - 0.72)], 28, 'slat')
    lathe([(2.6, Z - 0.26), (1.5, Z - 0.6), (0.45, Z - 0.74), (0.4, Z - 0.84), (1.55, Z - 0.7), (2.7, Z - 0.3)], 28, 'under')
    for k in range(8):
        shell(top, 0.36, 1.0, 45 * k, 50, 'shell', nu=9, nv=5, off=0.03, lift=0.1, shape=0.22, skew=34, back=0.5)
    for k in range(5):
        shell(top, 0.1, 0.6, 72 * k + 15, 78, 'bronze', nu=8, nv=5, off=0.12, lift=0.06, shape=0.25, skew=40)
    K.ring((0, 0, Z + 0.02), R + 0.02, 0.07, 'bronze', sides=36)
    # Core cup with a floating orb and counter-swept claws.
    lathe([(0.75, Z + 0.98), (0.95, Z + 1.2), (0.86, Z + 1.24), (0.62, Z + 1.05)], 18, 'bronze')
    K.core((0, 0, Z + 1.5), 0.46, cage=4, ring=False)
    # Six sickle blades held off the rim.
    for k in range(3):
        m = F.mark()
        K.blade((0, 0, 0), R + 0.45, 150, 228, 0.42, 0.07, zone='bronze')
        F.move_all(m, (0, 0, Z + 0.12))
        F.rot_all(m, 'Z', 120 * k)
    # Mandibles and lance: the direction of travel.
    for s in (1, -1):
        K.blade((2.6, s * 0.1, Z - 0.1), 1.5, s * -30, s * 105, 0.55, 0.11, sq=(1.25, 0.82), zone='shell')
    tube((2.6, 0, Z - 0.1), (3.7, 0, Z - 0.1), [(0, 0.2), (0.3, 0.14), (1, 0.04)], 8, 'barrel')
    with F.group('TurretPod'):
        lathe([(0.75, Z - 0.75), (0.62, Z - 0.98), (0.3, Z - 1.1), (0.02, Z - 1.12)], 14, 'bronze')
        cyl((0, 0, Z - 1.13), (0, 0, Z - 1.08), 0.28, 12, 'glow')
        tube((0.2, 0, Z - 0.98), (1.15, 0, Z - 1.06), [(0, 0.1), (0.8, 0.07), (1, 0.09)], 8, 'barrel')
    return dict(name='KeshDisc', pivot=('TurretPod', (0, 0, Z - 0.75)))


@asset('alien/halo.glb', 'Kesh Halo (fighter)')
def halo():
    import compat
    compat.install()
    import aircraft2
    aircraft2.halo()
    return dict(name='KeshHalo', single=True)


@asset('alien/dragonfly.glb', 'Kesh Dragonfly (aircraft, role not assigned)')
def dragonfly():
    Z = 1.15
    # Thorax and head: a compact layered lens hull with caged gold eyes at the nose.
    fn = lensfn(-1.1, 2.3, 0.78, Z + 0.72, Z - 0.5, Z + 0.05, nose=0.75)
    K.layered_hull(fn, sides=False, rear=True)
    for s in (1, -1):
        K.core((1.75, s * 0.42, Z + 0.3), 0.26, ring=False)
        # Twin lances under the chin.
        tube((1.2, s * 0.26, Z - 0.3), (3.3, s * 0.26, Z - 0.3), [(0, 0.11), (0.15, 0.13), (0.2, 0.065), (0.92, 0.05), (0.94, 0.085), (1, 0.085)], 8, 'barrel')
        cyl((3.29, s * 0.26, Z - 0.3), (3.31, s * 0.26, Z - 0.3), 0.06, 8, 'glow')
    K.core((0.55, 0, Z + 0.74), 0.22)
    # Long straight segmented tail.
    n = 7
    x, r = -0.8, 0.5
    zc = Z + 0.05
    x_start, r_start = x, r
    for k in range(n):
        ln = 0.82 - k * 0.03
        r1 = r * 0.86
        tube((x, 0, zc), (x - ln, 0, zc), [(0, r * 0.72), (0.18, r), (0.7, r * 0.92), (1, r1 * 0.7)], 10,
             'shell' if k % 2 == 0 else 'bronze')
        K.ring((x - ln, 0, zc), r1 * 0.78, 0.035, 'glow', sides=10, tilt=(0, 90))
        x, r = x - ln, r1
    for s in (1, -1):   # tail claspers
        K.blade((x - 0.05, s * 0.75, zc), 0.75, s * -80, s * -190, 0.3, 0.06)
    # Straight lines down the back: a glowing spine flanked by two bronze rails, nose to tail tip.
    sweep([(1.1, 0, Z + 0.66), (-0.9, 0, Z + 0.62), (x + 0.2, 0, zc + r + 0.06)], [(0.035, 0.03), (0.035, 0.03), (0.02, 0.02)], 'glow', sides=4)
    for s in (1, -1):
        sweep([(0.9, s * 0.2, Z + 0.6), (-0.9, s * 0.2, Z + 0.56), (x + 0.2, s * 0.07, zc + r + 0.04)],
              [(0.05, 0.05), (0.05, 0.05), (0.025, 0.03)], 'bronze', sides=4, power=1.6)
    # Four long see-through wings in two pairs, each with straight veins and a bronze leading spar.
    for s in (1, -1):
        for (x0, span, sweep_, rise, chord) in ((0.75, 6.2, -0.4, 0.9, 0.62), (-0.3, 5.2, -1.9, 0.55, 0.54)):
            root = (x0, s * 0.35, Z + 0.5)
            tip = (x0 + sweep_, s * (0.35 + span), Z + 0.5 + rise)
            def at(t, dx=0.0, dz=0.0):
                return (root[0] + (tip[0] - root[0]) * t + dx, root[1] + (tip[1] - root[1]) * t, root[2] + (tip[2] - root[2]) * t + dz)
            sweep([at(0), at(0.3), at(0.7), at(1)], [(chord * 0.5, 0.03), (chord, 0.025), (chord * 0.9, 0.02), (chord * 0.2, 0.012)], 'wing', sides=6, power=0.7)
            sweep([at(0, chord * 0.5, 0.02), at(0.3, chord, 0.02), at(0.7, chord * 0.9, 0.02), at(1, chord * 0.2, 0.01)],
                  [(0.09, 0.07), (0.08, 0.06), (0.06, 0.05), (0.02, 0.02)], 'bronze', sides=6)
            for off in (-0.45, 0.0, 0.42):   # straight veins
                sweep([at(0.04, chord * off * 0.5, 0.03), at(0.95, chord * off * 0.25, 0.02)], [(0.018, 0.012), (0.01, 0.01)], 'glow', sides=4)
        orb((0.25, s * 0.42, Z + 0.48), 0.3, 'bronze', seg=(10, 8), sq=(1.9, 0.8, 0.6))
    K.lifters([(0.6, 0, Z - 0.5)], 0.3)
    return dict(name='KeshDragonfly', single=True, clear='wing')
