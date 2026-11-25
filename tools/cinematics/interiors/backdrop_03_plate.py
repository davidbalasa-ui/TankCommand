"""Battle backdrop still 3: wide backdrop plates with no foreground (the battle as a panorama that could
wrap behind a ship deck, skybox style). Two variants:

    /home/user/artenv/venv/bin/python tools/cinematics/interiors/backdrop_03_plate.py --variant=terran|arcadian --out=FILE.jpg [--final=1]

terran:   the Terran line seen close (what you would see from an Arcadian deck): dreadnought, broadside
          battleship firing comets, frigate, missile ship, corvettes; the Arcadian motherships far off.
arcadian: the Arcadian fleet seen close (from a Terran deck): crescent, hooked shell and lens motherships,
          corvettes, a squid ship and stingrays; the Terran line far off, firing in.
The action sits in the upper two thirds; the planet's limb fills the bottom, where a deck would cover it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
from mathutils import Vector  # noqa: E402

VAR = K.ARGS.get('variant', 'terran')
OUT = K.ARGS.get('out', os.path.join(K.SCRATCH, f'03_plate_{VAR}.jpg'))


def terran():
    k = K.Kit(sun_dir=(0.7, 0.35, -0.4), sun_energy=6.5, planet_c=(0, 0, -2530), rim_dir=(-0.7, 0.5, 0.2), rim=2.0,
              fill_dir=(0.1, 1, -0.2), fill=2.5, tint='blue', nebula=3.0)
    k.set_res(1920, 864)
    k.camera((0, 0, 0), (0, 100, -2), lens=20)
    P = k.cam_pt
    # far right: the lens mothership under fire
    LN = P(0.60, 0.34, 430)
    ln = k.ship('lens', scale=1.8)
    k.place(ln, LN, fwd=(-1, -0.35, -0.05), roll=-14)
    # centre: the battleship, guns on the lens ship
    BS = P(0.04, 0.0, 185)
    e = LN - BS
    e.z = 0
    e.normalize()
    bs = k.ship('bship')
    k.place(bs, BS, fwd=(-e.y, e.x, 0), roll=-12)
    k.tshield(bs, vis=0.85)
    k.engines(bs, 0.6)
    muz = [k.world_pt(bs, m) for m in k.extra('bship')]
    gs = k.gshield(ln, hit=muz[1], vis=0.9)
    loc = k.extra('bship')
    tgt = k.shield_point(ln, gs, muz[0])
    d = (tgt - muz[0]).normalized()
    k.comet(muz[0] + d * (tgt - muz[0]).length * 0.55, d, scale=3.2)
    k.comet(muz[2] + d * (tgt - muz[2]).length * 0.2 + Vector((0, 0, -6)), d, scale=3.0)
    k.muzzle(bs, loc[1], 'fire', scale=0.6)
    k.boom(tgt + Vector((0, 0, 10)), 26, 'blue', age=5, light=4e5)
    k.shards(tgt + Vector((0, 0, 10)), 22, K.CYAN, 1.2, 40, 3, age=7)
    # near left: the dreadnought, its shield taking the lens ship's beam
    dr = k.ship('dread')
    k.place(dr, P(-0.55, 0.06, 112), fwd=(0.9, 0.42, 0.04), roll=10)
    src = k.world_pt(ln, (24, 0, 0))
    aim = src + Vector((0, 0, 120))
    ts = k.tshield(dr, hit=aim, ring=0.4)
    hit = k.shield_point(dr, ts, aim)
    k.beam(src, hit, r=0.7, glow=4.0, halo=2.0)
    k.flare(hit, 3.5, K.GOLD, 6.0, core=K.HOTGOLD, core_k=14.0, light=6e5)
    k.flare(src, 6, K.GOLD, 5.0, core=K.HOTGOLD, core_k=14.0)
    k.engines(dr, 0.6)
    # near right: frigate, with the missile ship beyond it launching
    fg = k.ship('frigate', scale=1.2)
    k.place(fg, P(0.70, -0.40, 58), fwd=(0.85, 0.5, 0.06), roll=-12)
    k.engines(fg, 0.6)
    ms = k.ship('missile')
    k.place(ms, P(0.24, -0.34, 130), fwd=(0.9, 0.42, 0.12), roll=6)
    k.engines(ms, 0.6)
    tubes = [k.world_pt(ms, t) for t in k.extra('missile')]
    fw = (ms.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    for i, (tube, dist) in enumerate(((0, 6), (1, 20), (0, 38), (1, 60), (0, 84))):
        m = K.T.missile(f'BkMissile{i}', scale=1.6, plume=True)
        dd = (fw + Vector((0, 0, 0.02 * i))).normalized()
        k.place(m, tubes[tube] + dd * dist, fwd=dd)
    # corvette screen, upper left
    for x, y, dpt in ((-0.80, 0.62, 170), (-0.62, 0.70, 210), (-0.40, 0.66, 250)):
        c = k.ship('corvette', scale=1.6)
        k.place(c, P(x, y, dpt), fwd=(0.9, 0.4, 0.0), roll=-8)
        k.engines(c, 0.6)
    # fighters going in
    for x, y, dpt in ((0.30, 0.60, 200), (0.37, 0.68, 220), (0.25, 0.74, 240), (0.44, 0.58, 260)):
        k.streak(P(x, y, dpt), (1, 0.6, -0.05), 20, K.CYAN, r=0.22, k=6.0)
    # far: the crescent and its escorts, and the fight round them
    cr = k.ship('crescent', scale=2.0)
    k.place(cr, P(0.08, 0.68, 900), fwd=(-1, -0.2, 0), roll=-50)
    for x, y, dpt in ((0.86, -0.02, 520), (0.78, 0.74, 600)):
        a = k.ship('acorv', scale=2.4)
        k.place(a, P(x, y, dpt), fwd=(-1, -0.3, 0))
    k.boom(P(0.86, -0.02, 510), 14, 'fire', age=4)
    for x, y, dpt in ((0.74, 0.02, 300), (0.68, 0.08, 320), (0.80, 0.12, 340)):
        k.streak(P(x, y, dpt), (-1, -0.4, 0.0), 24, K.GOLD, r=0.4, k=5.0)
    return k


def arcadian():
    k = K.Kit(sun_dir=(0.65, 0.45, -0.4), sun_energy=6.0, planet_c=(0, 0, -2530), rim_dir=(-0.7, 0.5, 0.2), rim=2.0,
              fill_dir=(0.1, 1, -0.2), fill=1.5, tint='teal', nebula=3.0)
    k.set_res(1920, 864)
    k.camera((0, 0, 0), (0, 100, -2), lens=20)
    P = k.cam_pt
    # far right: the Terran line
    DR = P(0.70, 0.44, 310)
    BSP = P(0.44, 0.76, 390)
    dr = k.ship('dread')
    k.place(dr, DR, fwd=(-1, -0.3, 0), roll=-10)
    k.engines(dr, 0.6)
    # near left: the crescent, face on, firing on the dreadnought
    CR = P(-0.50, 0.02, 175)
    cr = k.ship('crescent', scale=2.2)
    k.place(cr, CR, fwd=(0.92, 0.3, 0.05), roll=-55)
    src = k.world_pt(cr, (20, 0, 2))
    ts = k.tshield(dr, hit=src, ring=0.45)
    hit = k.shield_point(dr, ts, src)
    k.beam(src, hit, r=0.8, glow=4.0, halo=2.0)
    k.flare(src, 6, K.GOLD, 5.0, core=K.HOTGOLD, core_k=14.0)
    k.flare(hit, 6, K.GOLD, 6.0, core=K.HOTGOLD, core_k=14.0, light=1e6)
    # centre, further off: the lens mothership, its gold shield taking a comet from the battleship
    LN = P(0.02, 0.56, 380)
    ln = k.ship('lens', scale=1.6)
    k.place(ln, LN, fwd=(1, 0.25, 0), roll=12)
    bs = k.ship('bship')
    e = LN - BSP
    e.z = 0
    e.normalize()
    k.place(bs, BSP, fwd=(-e.y, e.x, 0), roll=-15)
    k.tshield(bs, vis=0.9)
    muz = [k.world_pt(bs, m) for m in k.extra('bship')]
    gs = k.gshield(ln, hit=muz[1], vis=0.9)
    tgt = k.shield_point(ln, gs, muz[1])
    d = (tgt - muz[1]).normalized()
    k.comet(muz[1] + d * (tgt - muz[1]).length * 0.45, d, scale=3.6)
    k.boom(tgt, 20, 'blue', age=5, light=4e5)
    k.shards(tgt, 22, K.CYAN, 1.0, 36, 3, age=7)
    # right, nearer: the hooked shell mothership
    sh = k.ship('shell', scale=1.2)
    k.place(sh, P(0.56, -0.12, 200), fwd=(0.95, 0.3, 0.05), roll=-20)
    # near: corvettes and stingrays heading out (lightning thrusters)
    for x, y, dpt, roll in ((-0.02, -0.34, 60, 14), (0.26, -0.50, 85, -10)):
        a = k.ship('acorv', scale=1.2)
        k.place(a, P(x, y, dpt), fwd=(0.9, 0.42, 0.03), roll=roll)
        k.engines(a, 0.45)
    for x, y, dpt, roll in ((0.18, -0.02, 70, 25), (0.31, 0.08, 85, 10), (0.10, 0.12, 100, -20), (0.40, -0.06, 110, 30)):
        s = k.ship('sting', scale=5.0)
        k.place(s, P(x, y, dpt), fwd=(0.9, 0.4, 0.05), roll=roll)
        k.engines(s, 0.5)
    # incoming Terran fire, and fighters
    for x, y, dpt in ((0.52, 0.30, 300), (0.62, 0.26, 280), (0.30, 0.50, 330)):
        k.bolt(P(x, y, dpt), (-1, -0.4, -0.05), 16, K.CYAN, r=0.45)
    for x, y, dpt in ((0.80, 0.78, 260), (0.88, 0.70, 280), (0.74, 0.86, 300)):
        k.streak(P(x, y, dpt), (-1, -0.5, -0.1), 22, K.CYAN, r=0.25, k=6.0)
    for x, y, dpt in ((-0.70, 0.74, 420), (-0.52, 0.80, 480), (-0.86, 0.60, 380)):
        a = k.ship('acorv', scale=2.2)
        k.place(a, P(x, y, dpt), fwd=(0.95, 0.3, 0.0), roll=10)
        k.engines(a, 0.5)
    k.boom(P(0.86, 0.02, 330), 12, 'fire', age=4)
    k.debris(P(0.86, 0.02, 330), 12, 22, 2.0, seed=3)
    return k


k = {'terran': terran, 'arcadian': arcadian}[VAR]()
k.render(OUT)
