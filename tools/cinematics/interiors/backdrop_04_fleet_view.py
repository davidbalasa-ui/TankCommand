"""Battle backdrop still 4: fleet view (the zoomed-out view where the player picks a bay door).

    /home/user/artenv/venv/bin/python tools/cinematics/interiors/backdrop_04_fleet_view.py --out=FILE.jpg [--final=1]

Three-quarter view from above and astern, looking down the gap between two capital ships running side by
side at boarding range: the Terran dreadnought (right) and the gold crescent mothership (left). Boarding
pods cross the gap on cyan trails from the dreadnought's two lit launch bays to three lit bay mouths set
into the crescent's flank (the bay mouths are added here, backdrop_kit.arcadian_bay: the crescent has no
flank bays of its own). The crescent's point defence answers with gold tracer, flak bursts and lightning.
The escort battle is a dimmer, smaller layer far ahead; space is dark, the planet only a limb in a corner.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

OUT = K.ARGS.get('out', os.path.join(K.SCRATCH, '04_fleet_view.jpg'))
k = K.Kit(sun_dir=(0.65, 0.3, -0.6), sun_energy=7.0, planet_c=(2400, -1650, 900), rim_dir=(-0.8, -0.3, 0.2), rim=2.0,
          fill_dir=(1, 0.0, -0.5), fill=2.2, tint='blue', nebula=2.4)
cam = k.camera((-80, -8, 102), (-8, 7, 0), lens=27.5)

# ---------------------------------------------------------------- the two capital ships
dr = k.ship('dread', scale=2.2)
k.place(dr, (0, -30, 0), fwd=(1, 0.18, 0), roll=16)
k.engines(dr, 0.35, length=3.5)
S = 1.75
cr = k.ship('crescent', scale=S)
k.place(cr, (10, 48, 0), fwd=(1, -0.1, 0), roll=-8)

# launch bays on the dreadnought's flank that faces the crescent (+Y)
d_loc = sorted([b for b in k.extra('dread') if b.y > 0], key=lambda b: -b.x)
for b in d_loc:
    K.terran_bay(k, dr, b, 1)
d_bays = [k.world_pt(dr, b + Vector((0, 0.6, 0))) for b in d_loc]

# three bay mouths set into the crescent's outer flank (its arc: R 17, a 36..324 deg, see crescent_mothership_v2)
c_bays = []
for a_deg, r in ((208, 2.7), (238, 2.5), (268, 2.1)):
    a = math.radians(a_deg)
    u = (a_deg - 36) / 288.0
    rad = 0.35 + 5.2 * math.sin(math.pi * u) ** 0.9
    pth = Vector((17 * math.cos(a) * 1.12, 17 * math.sin(a), 0))
    n = Vector((math.cos(a), math.sin(a) * 1.12, 0)).normalized()
    c = pth + n * (rad * 0.92)
    K.arcadian_bay(k, cr, c, n, r)
    c_bays.append((k.world_pt(cr, c + n * 1.4), (cr.matrix_world.to_3x3() @ n).normalized()))

# ---------------------------------------------------------------- boarding pods
pod_hull = K.metal_mat('PodHull', (0.3, 0.34, 0.4), 0.35, 0.9)
pod_dark = K.metal_mat('PodDark', (0.05, 0.06, 0.07), 0.5, 0.9)
pod_glow = K.C.emit_mat('PodGlow', (0.15, 0.7, 1.0), 18.0)
pod_eng = K.C.emit_mat('PodEngine', (0.75, 0.93, 1.0), 45.0)


def pod(p, d, s=1.0):
    """Boarding pod: blunt armoured capsule with a ram collar, two cyan bands and a hard engine glow."""
    d = Vector(d).normalized()
    o = K.C.uv_sphere(k.uid('Pod'), 1.0, seg=(20, 10), mat=pod_hull, scale=(3.0 * s, 1.15 * s, 1.15 * s))
    o.location = p
    K.BP.aim(o, d)
    for dx, mat, w in ((0.62, pod_dark, 0.12), (0.25, pod_glow, 0.035), (-0.35, pod_glow, 0.035), (-0.7, pod_dark, 0.1)):
        rr = (1 - dx * dx) ** 0.5 * 1.06
        b = K.C.uv_sphere(k.uid('PodBand'), 1.0, seg=(20, 6), mat=mat, scale=(w, rr, rr))
        b.parent = o
        b.location = (dx, 0, 0)
    e = K.C.uv_sphere(k.uid('PodEng'), 1.0, seg=(12, 6), mat=pod_eng, scale=(0.5 * s, 0.6 * s, 0.6 * s))
    e.location = Vector(p) - d * 2.9 * s
    k.streak(Vector(p) - d * 3.0 * s, d, 17.0 * s, (0.08, 0.5, 1.0), r=0.75 * s, k=5.0, head=False)
    k.streak(Vector(p) - d * 3.0 * s, d, 24.0 * s, (0.03, 0.3, 1.0), r=1.2 * s, k=1.0, head=False)
    return o


out_d = (dr.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
lanes = [(d_bays[0], c_bays[2], (0.22, 0.60, 0.93)), (d_bays[1], c_bays[1], (0.12, 0.47, 0.80)),
         (d_bays[1], c_bays[0], (0.30, 0.66))]
pods = []
for a, (b, bn), ts in lanes:
    a2 = a + out_d * 2.0
    for t in ts:
        f = lambda t: a2.lerp(b, t) + Vector((0, 0, 4.0 * math.sin(math.pi * t)))  # noqa: E731
        p = f(t)
        pods.append(p)
        pod(p, f(t + 0.02) - p)

# ---------------------------------------------------------------- point defence
gun = [k.world_pt(cr, g) for g in ((-17, -12.5, 3.2), (-4, -19.5, 3.0), (6, -18, 2.6))]
for i, (g, tp) in enumerate(((gun[0], pods[7]), (gun[1], pods[4]), (gun[2], pods[1]), (gun[1], pods[0]))):
    d = (tp + Vector((0, 0, 3 + i)) - g)
    L = d.length
    d.normalize()
    for j in range(4):
        k.bolt(g + d * L * (0.18 + 0.2 * j), d, 3.2, K.HOTGOLD, r=0.2, strength=30.0)
for i, (pi_, off) in enumerate(((7, (2, 3, 3)), (4, (-3, 2, 4)), (1, (3, -2, 3)), (5, (-2, -4, 2)), (0, (2, 4, -2)))):
    k.impact(pods[pi_] + Vector(off), 1.5 + 0.4 * (i % 2), seed=i, sparks=8)
kill = d_bays[0].lerp(c_bays[1][0], 0.56) + Vector((6, 0, 5))
k.lightning([(gun[1], kill)], width=0.3, seed=4)
k.boom(kill, 5.0, 'fire', age=3, light=6e4)
k.debris(kill, 8, 7, 0.6, seed=2)

# ---------------------------------------------------------------- far ahead: the escort battle, kept small and dim
BS = Vector((300, -60, -260))
LN = Vector((430, 130, -340))
bs = k.ship('bship')
e = LN - BS
e.z = 0
e.normalize()
k.place(bs, BS, fwd=(-e.y, e.x, 0), roll=-20)
k.tshield(bs, vis=0.7)
ln = k.ship('lens', scale=1.5)
k.place(ln, LN, fwd=(-1, -0.3, 0), roll=15)
gs = k.gshield(ln, hit=BS, vis=0.7)
muz = [k.world_pt(bs, m) for m in k.extra('bship')]
tgt = k.shield_point(ln, gs, muz[1])
d = (tgt - muz[1]).normalized()
k.comet(muz[1] + d * (tgt - muz[1]).length * 0.5, d, scale=3.0)
k.boom(tgt, 16, 'blue', age=6)
for x, y, z in ((150, -170, -200), (190, -120, -230)):
    c = k.ship('corvette', scale=2.0)
    k.place(c, (x, y, z), fwd=(1, 0.3, 0), roll=10)
    k.engines(c, 0.6)
ac = k.ship('acorv', scale=2.4)
k.place(ac, (320, -200, -300), fwd=(-1, 0.2, 0), roll=-10)
k.beam(k.world_pt(ac, (7, 0, 0)), Vector((196, -122, -229)), r=0.7, glow=3.0, halo=1.8)
k.boom((196, -122, -229), 7, 'gold', age=4)

k.render(OUT)
