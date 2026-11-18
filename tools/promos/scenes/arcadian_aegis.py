"""Aegis (Arcadian heavy tank): it glides into a Terran gun line, takes it on the chin, and answers.

The Aegis advances on a skirt of gold lightning while two Lancers and a Bulwark pound its horned
front: shells burst on the silver hull and it does not even slow. It stops, lowers onto its
lifters and braces; its four cores light one by one; the charge arcs into the gun and one
massive gold blast destroys the Bulwark (huge hull kick). One second later a second blast kills
a Lancer. The last Lancer, off-screen beside the camera, keeps shooting; the Aegis shrugs it off,
swings its gun straight down the lens and its cores start to fill again.

0-1.75    low front 3/4: the Aegis advances at us, shells bursting on its front.
1.75-3.33 high on its flank, close on the deck: it settles low, the four cores ignite one by one.
3.33-6    long lens from behind the Terran line, the Aegis head-on between the Bulwark and a
          Lancer: charge arcs, BLAST -> Bulwark dies; blast -> Lancer dies; the gun turns to us."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link, sphere, key_strength  # noqa: E402

P = Promo('arcadian_aegis', seconds=6.0, seed=7)
FPS = P.fps
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)

P.env('highland', sun=(55, 0, -35), clear=[(-12, -1, 14), (6, 0, 13), (13.3, -9.85, 5), (27, -6, 3)], props=30)
P.flatten(-12, -1, 14)
P.flatten(6, 0, 13)
P.flatten(13.3, -9.85, 5)


def gz(x, y):
    return P.ground_z(x, y)


# --------------------------------------------------------------------------- the Terran gun line
BUL = (3.83, 1.38)
LA = (4.21, -6.16)
LB = (13.3, -9.85)
bulwark = P.load('bulwark', at=BUL, heading=184, label='bulwark')
bulwark.split_barrels()
lancA = P.load('lancer', at=LA, heading=150, label='lancerA')
lancA.split_barrels()
lancB = P.load('lancer', at=LB, heading=158, label='lancerB')
lancB.split_barrels()

# --------------------------------------------------------------------------- the Aegis
HOV = 0.75
LOW = 0.38
AX, AY = -9.2, -0.4
aegis = P.load('aegis', at=(-19, -1.2), heading=0, label='aegis')
aegis.split_barrels(thin=0.46)
print('AEGIS barrels', [(b.name, b['barrel_len']) for b in aegis.barrels])
aegis.path([
    (0.0, (-19.0, -1.2, HOV)),
    (0.9, (-14.4, -0.85, HOV)),
    (1.7, (-10.5, -0.5, HOV)),
    (2.2, (-9.4, -0.42, 0.55), 2.0),
    (2.65, (AX, AY, LOW), 2.0),
    (3.6, (AX, AY, LOW), 2.0),
    (4.2, (AX - 0.25, AY, 0.45), 2.0),
    (6.0, (AX - 0.35, AY, 0.5), 0.0),
])
aegis.hover_bob(0.035, 1.0)

# cores (model space, measured from the emissive map): front pair beside the gun, rear pair
CORES = [Vector((0.74, 0.73, 0.92)), Vector((0.74, -0.73, 0.92)),
         Vector((-0.86, -1.1, 0.86)), Vector((-0.86, 1.1, 0.86))]
T_CORE = [2.05, 2.4, 2.75, 3.1]
T_BLAST = 3.65
T_BLAST2 = 4.6

# --------------------------------------------------------------------------- lightning lifters
# Short, dense crackle tucked right under the belly (the Darter's skirt, scaled to a heavy hull).
bolt_mat = emit_mat('AegisLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('AegisLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)
bpy.context.view_layer.update()
hull = [o for o in aegis.meshes if o.name.startswith('Hull')][0]
inv = aegis.model_root.matrix_world.inverted()
belly = [inv @ (hull.matrix_world @ v.co) for v in hull.data.vertices if v.co.z < 0.25]
BX0, BX1 = min(p.x for p in belly) * 0.7, max(p.x for p in belly) * 0.7
BY = max(abs(p.y) for p in belly) * 0.55
print('AEGIS belly', BX0, BX1, BY)


def jag(p0, p1, segs, amp, rnd):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            e = math.sin(math.pi * u)
            q += Vector((rnd.uniform(-amp, amp), rnd.uniform(-amp, amp), rnd.uniform(-amp, amp) * 0.5)) * e
        pts.append(q)
    return pts


def crackle(a, n_lift=14):
    rnd = P.rnd
    for f in range(1, P.nf + 2):
        objs = []
        for k in range(n_lift):
            p0 = Vector((rnd.uniform(BX0, BX1), rnd.uniform(-BY, BY), 0.06))
            if k % 3 == 0:
                p1 = p0 + Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.2, 0.2), -rnd.uniform(0.0, 0.1)))
            else:
                side = 1 if p0.y > 0 else -1
                p1 = p0 + Vector((rnd.uniform(-0.25, 0.15), side * rnd.uniform(0.1, 0.35), -rnd.uniform(0.15, 0.32)))
            pts = jag(p0, p1, 4, 0.08, rnd)
            objs += [polyline('ALift', pts, 0.016, bolt_mat), polyline('ALiftHalo', pts, 0.055, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('AegisLiftLight', bpy.data.lights.new('AegisLiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.25)
    L.data.color = GOLD
    L.data.energy = 160
    L.data.shadow_soft_size = 1.0


crackle(aegis)
P.dust(aegis, 0.0, 2.4, every=0.12, size=0.6)

# --------------------------------------------------------------------------- the four cores
core_mats = []
for i, c in enumerate(CORES):
    m = emit_mat(f'AegisCore{i}', DEEP_GOLD, 0.0)
    core_mats.append(m)
    s = sphere(f'AegisCoreGlow{i}', 0.16, m, seg=(16, 10))
    s.parent = aegis.model_root
    s.location = c + Vector((0, 0, 0.03))
    hm = emit_mat(f'AegisCoreHalo{i}', DEEP_GOLD, 1.0, alpha=0.14)
    h = sphere(f'AegisCoreHalo{i}', 1.0, hm, seg=(16, 10))
    h.parent = aegis.model_root
    h.location = s.location
    h.visible_shadow = False
    s.visible_shadow = False
    L = link(bpy.data.objects.new(f'AegisCoreLight{i}', bpy.data.lights.new(f'AegisCoreLight{i}', 'POINT')))
    L.parent = aegis.model_root
    L.location = c + Vector((0, 0, 0.35))
    L.data.color = GOLD
    L.data.shadow_soft_size = 0.3
    t = T_CORE[i]
    f = P.T(t)
    # dim -> ignite (pop) -> held bright -> flash on the blast -> drained
    for fr, st, hs, le in [(1, 0.25, 0.01, 0), (f - 1, 0.25, 0.01, 0), (f + 2, 3.6, 0.3, 260),
                           (f + 6, 2.6, 0.22, 160), (P.T(T_BLAST) - 1, 3.0, 0.24, 200),
                           (P.T(T_BLAST) + 1, 3.8, 0.34, 320), (P.T(T_BLAST) + 8, 0.35, 0.05, 10),
                           (P.T(T_BLAST2) - 3, 0.9, 0.12, 40), (P.T(T_BLAST2) + 4, 0.3, 0.02, 0),
                           (P.T(5.25 + 0.1 * i), 0.3, 0.02, 0), (P.T(5.55 + 0.1 * i), 2.8, 0.22, 170),
                           (P.T(6.0), 3.0, 0.24, 190)]:
        key_strength(m, fr, st)
        h.scale = (hs,) * 3
        h.keyframe_insert('scale', frame=fr)
        L.data.energy = le
        L.data.keyframe_insert('energy', frame=fr)
    P.sfx(t, 'power_up_arc', gain=0.5, rate=1.0 + 0.12 * i)
P.sfx(3.15, 'charge_gold', gain=0.9)


# --------------------------------------------------------------------------- the Terran gun line fires
def front_hit(t_fire, src, y):
    """Point on the Aegis' horned front where a shell fired at t_fire lands."""
    p0 = src.root.location
    guess = aegis.world_at(aegis.model_root, t_fire + 0.35, local=(2.4, y, 0.85))
    t_hit = t_fire + (guess - Vector(p0)).length / 60.0
    return aegis.world_at(aegis.model_root, t_hit, local=(2.35, y, 0.85))


SHOTS = [
    (lancA, 0.35, 'cannon', 0.45),
    (lancB, 0.8, 'cannon', -0.35),
    (bulwark, 1.15, 'heavy', 0.1),
    (lancA, 1.45, 'cannon', -0.55),
    (lancB, 1.95, 'cannon', 0.5),
    (bulwark, 2.45, 'heavy', -0.2),
    (lancA, 2.7, 'cannon', 0.3),
    (lancB, 3.1, 'cannon', -0.45),
]
for src, t, kind, y in SHOTS:
    p = front_hit(t, src, y)
    src.aim(t, p, dur=0.4)
    src.fire(t, p, kind=kind, impact_size=0.8 if kind == 'heavy' else 0.55)

# --------------------------------------------------------------------------- the answer
mz = aegis.muzzle()
aegis.aim(T_BLAST - 0.05, bulwark, dur=0.7)
# charge: the cores arc into the gun breech for the last half second
bpy.context.view_layer.update()
breech = Vector((0.9, 0.0, 1.25))
for i, c in enumerate(CORES):
    p0 = aegis.world_at(aegis.model_root, 3.4, local=c + Vector((0, 0, 0.1)))
    p1 = aegis.world_at(aegis.model_root, 3.4, local=breech)
    P.lightning(p0, p1, 3.22 + 0.04 * i, T_BLAST - 0.02, width=0.025, jag=0.25, branches=1, segs=6)
t_hit = aegis.fire(T_BLAST, bulwark, kind='lightning', size=2.6, kick=14)
bulwark.destroy(t_hit + 0.02, size=2.1)
P.cam_shake(T_BLAST, 0.16)

aegis.aim(T_BLAST2 - 0.05, lancA, dur=0.55)
t_hit = aegis.fire(T_BLAST2, lancA, kind='lightning', size=1.9, kick=11)
lancA.destroy(t_hit + 0.02, size=1.9)
P.cam_shake(T_BLAST2, 0.1)

# the last Lancer, beside the camera, keeps shooting; the Aegis shrugs it off, swings its gun
# straight down the lens at it and the cores start to fill again
for t, y in ((4.15, 0.2), (5.15, -0.35)):
    p = front_hit(t, lancB, y)
    lancB.aim(t, p, dur=0.35)
    lancB.fire(t, p, kind='cannon', impact_size=0.55)
aegis.aim(5.85, lancB, dur=0.6)
P.sfx(5.5, 'power_up_arc', gain=0.6, rate=0.9)

# --------------------------------------------------------------------------- camera
C1, C2 = 42 / FPS, 80 / FPS     # cuts at 1.75 s and 3.333 s
AIM = (AX, AY, 1.3)
P.camera([
    # shot 1: low front 3/4, the Aegis advances at us, shells bursting on its front
    (0.0, (-4.6, 6.0, 1.05), (-17.5, -0.6, 1.3), 60),
    (C1 - 1 / FPS, (-4.2, 6.4, 1.2), (-10.6, -0.5, 1.2), 32),
    # shot 2: high on its flank, looking down on the deck; it settles and the cores ignite
    (C1, (-7.4, 6.8, 5.8), (-9.0, -0.4, 0.6), 32),
    (C2 - 1 / FPS, (-7.8, 5.8, 5.0), (-9.0, -0.4, 0.7), 34),
    # shot 3: long lens from behind the Terran line: the Aegis head-on between the tanks it
    # kills one per second; it ends facing us over three burning wrecks
    (C2, (28.0, -6.0, gz(28.0, -6.0) + 2.4), AIM, 92),
    (6.0, (27.2, -5.88, gz(27.2, -5.88) + 2.3), AIM, 112),
], cuts=(C1, C2), shake=0.015)

P.render()
