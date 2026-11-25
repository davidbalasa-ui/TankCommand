"""Battle backdrop still 2: Terran ships attacking, seen out of an Arcadian bay mouth.

    /home/user/artenv/venv/bin/python tools/cinematics/interiors/backdrop_02_arcadian_arch.py --out=FILE.jpg [--final=1]

A Terran dreadnought bears down on the viewer's ship behind its triangle shield, which flares where the
mothership's gold beam and lightning strike it. To its right a missile ship sends a stream of heavy
missiles straight at us. An Arcadian corvette and two stingrays go out to meet them (lightning thrusters);
far off a broadside battleship duels a hooked-shell mothership. The planet arcs across the upper right.
The crescent-shaped gold-bronze mouth (etched inlay, glowing lip, tick-marked force ring) is a placeholder.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
from mathutils import Vector  # noqa: E402

OUT = K.ARGS.get('out', os.path.join(K.SCRATCH, '02_arcadian_arch.jpg'))
k = K.Kit(sun_dir=(0.6, 0.55, 0.45), sun_energy=7.0, planet_c=(1500, -500, 1950), rim_dir=(-0.7, 0.3, -0.5), rim=2.0,
          fill_dir=(0.1, 1, -0.2), fill=3.5, tint='teal', nebula=3.0)
cam = k.camera((0, 0, 0), (0, 100, 0), lens=24)
P = k.cam_pt

# ---------------------------------------------------------------- mid: the dreadnought coming at us
dr = k.ship('dread')
k.place(dr, P(-0.24, 0.06, 135), fwd=(0.88, -0.46, -0.06), roll=-16)
src = P(0.7, -1.25, 50)                                     # our own ship's beam, from below right of the mouth
ts = k.tshield(dr, hit=src, ring=0.45)
hit = k.shield_point(dr, ts, src)
k.beam(src, hit, r=0.55, glow=4.0, halo=2.0)
k.impact(hit, 3.2, seed=2, light=1.2e6, sparks=18)
k.light(P(-0.3, -0.25, 95), (0.85, 0.92, 1.0), 2.5e6, 8)       # lift the dreadnought's hull out of the dark
k.lightning([(hit, hit + Vector((-14, 6, 16))), (hit, hit + Vector((10, 2, -15))), (hit, hit + Vector((-18, 3, -8)))],
            width=0.3, seed=5)
# its reply: cyan beams from the midship turrets past the mouth, low
for i, (tx, ty) in enumerate(((-0.75, -1.2), (-0.1, -1.3))):
    a = k.world_pt(dr, (-7 + i * 7, -1.5, 2.6))
    k.beam(a, P(tx, ty, 50), col=K.BLUE, core=(0.8, 0.95, 1.0), r=0.3, glow=4.0, halo=2.0)
    k.flare(a, 1.2, K.CYAN, 5.0, core_k=10.0)

# ---------------------------------------------------------------- mid right: the missile ship and its stream
ms = k.ship('missile')
k.place(ms, P(0.52, -0.10, 92), fwd=(-0.88, -0.47, -0.04), roll=14)
k.tshield(ms, vis=0.8)
tubes = [k.world_pt(ms, t) for t in k.extra('missile')]
fwd = (ms.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
for i, (tube, dist, off) in enumerate(((0, 5, 0.0), (1, 17, 0.02), (0, 31, -0.03), (1, 47, 0.04), (0, 64, -0.02))):
    m = K.T.missile(f'BkMissile{i}', scale=1.3, plume=True)
    d = (fwd + Vector((off, 0, off * 0.6))).normalized()
    k.place(m, tubes[tube] + d * dist, fwd=d)

# ---------------------------------------------------------------- near: the defenders going out
ac = k.ship('acorv', scale=1.25)
k.place(ac, P(-0.46, -0.36, 36), fwd=(0.5, 1.0, 0.2), roll=24)
k.engines(ac, 1.0)
for x, y, dpt, fw, roll in ((0.20, 0.40, 40, (0.3, 1, 0.1), 30), (0.42, 0.24, 58, (0.25, 1, 0.05), -20)):
    s = k.ship('sting', scale=5.5)
    k.place(s, P(x, y, dpt), fwd=fw, roll=roll)
    k.engines(s, 1.0)

# twin-X fighters diving in: cyan streaks
for x, y, dpt in ((-0.66, 0.30, 70), (-0.74, 0.40, 82), (-0.60, 0.44, 95)):
    k.streak(P(x, y, dpt), (0.6, -1, -0.3), 15, K.CYAN, r=0.14, k=6.0)
# two corvettes screening the dreadnought's flank
for x, y, dpt in ((-0.74, 0.10, 150), (-0.80, -0.10, 120)):
    c = k.ship('corvette', scale=1.5)
    k.place(c, P(x, y, dpt), fwd=(0.8, -0.6, 0.0), roll=-10)
    k.engines(c, 0.4)
# a stingray that did not make it
k.boom(P(0.36, -0.42, 62), 4.5, 'fire', age=5, light=3e4)
k.impact(P(0.36, -0.42, 62), 2.0, seed=8, sparks=16)
k.debris(P(0.36, -0.42, 62), 10, 9, 0.9, seed=9, gold=True)

# ---------------------------------------------------------------- far: battleship against the shell mothership
bs = k.ship('bship')
BS = P(-0.42, 0.60, 420)
SH = P(0.02, 0.62, 560)
e = SH - BS
e.z = 0
e.normalize()
k.place(bs, BS, fwd=(-e.y, e.x, 0), roll=-20)
k.tshield(bs, vis=0.9)
sh = k.ship('shell', scale=1.0)
k.place(sh, SH, fwd=(-1, -0.4, 0), roll=-30)
muz = [k.world_pt(bs, m) for m in k.extra('bship')]
d = (SH - muz[1]).normalized()
k.comet(muz[1] + d * (SH - muz[1]).length * 0.45, d, scale=4.0)
k.boom(SH + Vector((-34, -10, 8)), 15, 'blue', age=5)


rim = K.arcadian_mouth(k)
# a few gold arcs crawling along the lip
for i, j in ((66, 73), (84, 92), (104, 110), (120, 128)):
    k.lightning([(rim[i], rim[j])], width=0.012, seed=i)
k.render(OUT)
