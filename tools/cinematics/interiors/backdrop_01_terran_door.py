"""Battle backdrop still 1: the fleet fight seen through a Terran hangar bay door.

    /home/user/artenv/venv/bin/python tools/cinematics/interiors/backdrop_01_terran_door.py --out=FILE.jpg [--final=1]

Read left to right: a Terran broadside battleship (seen from astern, guns to the right) throws blue comets
across the frame into the gold shield of an Arcadian crescent mothership, which answers with a gold beam
on the battleship's triangle shield. A Terran corvette crosses close outside the door; far off a
dreadnought and a lens ship trade fire; frigates and Arcadian corvettes fight low over the planet's limb. The door frame is a plain placeholder.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
from mathutils import Vector  # noqa: E402

OUT = K.ARGS.get('out', os.path.join(K.SCRATCH, '01_terran_door.jpg'))
k = K.Kit(sun_dir=(0.78, -0.3, -0.3), sun_energy=6.5, planet_c=(0, 0, -2490), rim_dir=(-0.6, 0.7, 0.25), rim=1.6,
          fill_dir=(0.15, 1, -0.3), fill=1.3, tint='blue', nebula=3.0)
cam = k.camera((0, 0, 0), (0, 100, -7), lens=24)
P = k.cam_pt                    # (screen x, screen y, distance) -> world; the door opening is about +-0.86, -0.75..0.82

# ---------------------------------------------------------------- mid left: the battleship, firing right
BS = P(-0.42, 0.0, 96)
CR = P(0.44, 0.30, 260)
e = (CR - BS)
e.z = 0
e.normalize()
bs = k.ship('bship')
k.place(bs, BS, fwd=(-e.y, e.x, 0.0), roll=-10)
k.engines(bs, 0.5)
muz = [k.world_pt(bs, m) for m in k.extra('bship')]

# ---------------------------------------------------------------- mid right: the crescent mothership
cr = k.ship('crescent', scale=1.7)
k.place(cr, CR, fwd=(-0.9, -0.3, -0.05), roll=-52)
gs = k.gshield(cr, hit=muz[1], vis=0.9)

# bow gun has fired (comet in flight), middle gun is firing, aft gun is charging; an earlier comet bursts
# on the gold shield
loc = k.extra('bship')
tgt = k.shield_point(cr, gs, muz[0]) + Vector((0, 0, 16))
d = (tgt - muz[0]).normalized()
k.comet(muz[0] + d * (tgt - muz[0]).length * 0.52, d, scale=2.6)
k.muzzle(bs, loc[0], 'fired')
k.muzzle(bs, loc[1], 'fire', scale=0.6)
k.muzzle(bs, loc[2], 'charge')
k.light(muz[1] + d * 3, K.CYAN, 1.5e5, 1.5)
burst = tgt
k.boom(burst, 20, 'blue', age=5, light=3e5)
k.shards(burst, 24, K.CYAN, 0.8, 30, 7, age=7)

# the crescent's answer: a gold beam on the battleship's triangle shield
src = k.world_pt(cr, (20, 0, 2))
aim = src + Vector((30, 0, -70))        # the beam strikes low on the bubble, clear of the comets' path
ts = k.tshield(bs, hit=aim, ring=0.42)
hit = k.shield_point(bs, ts, aim)
k.beam(src, hit, r=0.55, glow=4.0, halo=2.0)
k.flare(src, 4, K.GOLD, 5.0, core=K.HOTGOLD, core_k=14.0)
k.flare(hit, 2.6, K.GOLD, 6.0, core=K.HOTGOLD, core_k=14.0, light=8e4)

# ---------------------------------------------------------------- near: a corvette crossing outside the door
cv = k.ship('corvette', scale=1.2)
k.place(cv, P(0.30, -0.42, 30), fwd=(1, 0.35, 0.1), roll=-18)
k.engines(cv, 0.35)
for x, y, dpt, L in ((0.0, 0.12, 150, 16), (0.06, 0.2, 165, 18), (-0.07, 0.24, 180, 17)):
    k.streak(P(x, y, dpt), (1, 0.45, 0.1), L, K.CYAN, r=0.16, k=6.0)

# ---------------------------------------------------------------- far: dreadnought vs lens ship
dr = k.ship('dread')
k.place(dr, P(-0.34, 0.50, 340), fwd=(1, 0.1, 0.05), roll=14)
k.tshield(dr, vis=0.9)
ln = k.ship('lens', scale=1.8)
k.place(ln, P(0.08, 0.58, 760), fwd=(-1, -0.3, -0.1), roll=-12)
lsrc = P(0.03, 0.585, 700)
dhit = P(-0.26, 0.515, 335)
k.beam(lsrc, dhit, r=0.9, glow=4.0, halo=2.0)
k.boom(dhit, 13, 'gold', age=6)
for i in range(3):
    k.bolt(P(-0.2 + i * 0.07, 0.6 + i * 0.012, 400 + i * 90), lsrc - dhit, 12, K.CYAN, r=0.5)
# debris of an earlier kill drifting low right, well outside the door
k.debris(P(0.7, -0.3, 85), 22, 26, 2.2, seed=4, stretch=(1.2, 0.8, 0.6))
k.boom(P(0.72, -0.26, 95), 6, 'fire', age=13)

# ---------------------------------------------------------------- far right, just over the limb: a second fight
for i, (x, y, dpt, kind, fw, sc_) in enumerate(((0.05, -0.17, 360, 'frigate', (1, 0.25, 0.0), 2.0),
                                                (0.15, -0.07, 440, 'frigate', (1, 0.3, 0.0), 2.0),
                                                (0.56, -0.17, 470, 'acorv', (-1, -0.2, 0.0), 2.8),
                                                (0.70, -0.08, 540, 'acorv', (-1, -0.1, 0.05), 2.8))):
    o = k.ship(kind, scale=sc_)
    k.place(o, P(x, y, dpt), fwd=fw)
    k.engines(o, 0.6)
k.beam(P(0.51, -0.17, 465), P(0.12, -0.17, 365), r=0.6, glow=3.0, halo=1.8)
k.boom(P(0.12, -0.17, 365), 8, 'gold', age=4)
for j in range(3):
    k.bolt(P(0.26 + j * 0.12, -0.07 + j * 0.0, 450 + j * 30), (1, 0.3, 0), 12, K.CYAN, r=0.4)
k.boom(P(0.68, -0.08, 535), 12, 'blue', age=6)

K.terran_door(k)
k.render(OUT)
