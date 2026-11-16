"""Sentinel (Arcadian gun tower): a packed Sentinel skims in low over ash flats, riding on legs of
gold lightning that rake the ground and kick up dust. It plants itself, the lifters die in a dust
ring, and the thorny tower grows open while three Terran Lancers roll up and start shelling it.
Its crown charges and a gold lightning chain leaps Lancer to Lancer, killing two at once; the last
Lancer backs off firing, the turret swings round and one gold energy round finishes it. End on a
low hero frame behind the tower, gun on the smoking wrecks, crown still crackling.

Timeline (s): 0-1.7 glide in (low tracking camera) | 1.7 touchdown | 1.8-3.0 unfold, Lancers
shelling | 3.0-3.3 crown charge | 3.3 chain lightning, two kills | 3.6-4.4 survivor reverses and
fires, turret tracks | 4.5 gun shot, third kill | 4.6-6 hero frame."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Quaternion, Vector  # noqa: E402

from promo_kit import (COL, Promo, emit_mat, empty, key_strength, link, polyline,  # noqa: E402
                       set_interp, show_between, sphere)

P = Promo('arcadian_sentinel', seconds=6.0, seed=11)
P.env('ash', sun=(30, 0, -150), sun_energy=4.2, clear=[(0, 0, 12), (20, 2, 16), (-14, -4, 10)], props=34)
P.flatten(0, 0, 10)
P.flatten(19, 2, 14)
P.flatten(-14, -4, 9)
R = P.rnd

GOLD = COL['arc_gold']
DEEP = (1.0, 0.42, 0.03)
M_BOLT = emit_mat('SnBolt', GOLD, 2.6)
M_CORE = emit_mat('SnBoltCore', (1.0, 0.72, 0.3), 3.2)
M_GLOW = emit_mat('SnBoltGlow', DEEP, 1.2, alpha=0.22)

T_LAND = 1.7
T_UNF0, T_UNF1 = 1.85, 3.0
LIFT = 0.32   # packed carrier underside height above the root


# ------------------------------------------------------------------------------- lightning
def jag_pts(p0, p1, segs, jag):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        env = math.sin(math.pi * u)
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * env if 0 < i < segs else Vector()
        pts.append(p0 + d * u + off)
    return pts


def bolt_frame(pts, f, width, parent=None, glow=True, forks=1, nframes=1):
    objs = [polyline('Bolt', pts, width, M_BOLT), polyline('BoltCore', pts, width * 0.4, M_CORE)]
    if glow:
        objs.append(polyline('BoltGlow', pts, width * 3.0, M_GLOW))
    n = len(pts) - 1
    for _ in range(forks):
        if n < 4:
            break
        k = R.randint(2, n - 2)
        a = pts[k]
        dv = pts[k + 1] - pts[k - 1]
        side = dv.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        bl = dv.length * R.uniform(0.7, 1.4)
        dirb = (dv.normalized() + side * R.uniform(-1.2, 1.2) + Vector((0, 0, R.uniform(-.6, .4)))).normalized()
        objs.append(polyline('BoltFork', [a, a + dirb * bl * 0.5 + side * R.uniform(-.2, .2), a + dirb * bl],
                             width * 0.55, M_BOLT))
    for o in objs:
        if parent is not None:
            o.parent = parent
        show_between(o, f, f + nframes)
    return objs


def bolt(p0f, p1f, t0, t1, width=0.06, jag=0.2, segs=12, forks=2, light=1500):
    """Bolt redrawn every frame; p0f/p1f are callables t -> Vector (so it follows movers)."""
    f0 = int(round(P.T(t0)))
    f1 = max(f0 + 1, int(round(P.T(t1))))
    for f in range(f0, f1):
        t = (f - 1) / P.fps
        a, b = p0f(t), p1f(t)
        bolt_frame(jag_pts(a, b, segs, jag), f, width, forks=forks)
    if light:
        mid = (p0f(t0) + p1f(t0)) / 2
        P.light(mid, t0, GOLD, energy=light, dur=t1 - t0 + 0.05, radius=1.0)


def gold_sparks(pos, t, size=1.0, n=8):
    m = emit_mat('SnSpark', GOLD, 2.5)
    f0 = P.T(t)
    for i in range(n):
        sp = sphere('SnSpk', 1.0, m, seg=(6, 4))
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(0.1, 1.3))).normalized() * size * 3.2
        sp.scale = (0.14 * size, 0.03 * size, 0.03 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + Vector((0, 0, -0.15))
        sp.keyframe_insert('location', frame=f0 + 0.3 * P.fps)
        show_between(sp, f0, f0 + 0.3 * P.fps)


# Lighter, thinner smoke: the default dark puffs pile into black blobs.
_kit_puff = P.puff


def _thin_puff(pos, t, size=0.6, n=3, rise=1.0, life=1.2, color=None, opacity=0.65):
    if color is None:
        color, size, opacity = (0.2, 0.19, 0.18), size * 0.75, opacity * 0.75
    return _kit_puff(pos, t, size=size, n=n, rise=rise, life=life, color=color, opacity=opacity)


P.puff = _thin_puff
SAND = tuple(min(1, c * 1.9) for c in P.palette['g1'])


def dust_wave(center, t, r0, r1, rings=3, n=28, size=1.2, life=1.4, color=SAND, opacity=0.33, rise=0.5, dt=0.1):
    c = Vector(center)
    for k in range(rings):
        u = k / max(1, rings - 1)
        r = r0 + (r1 - r0) * u
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.08, 0.08)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.92, 1.08)
            _kit_puff(p + Vector((0, 0, 0.25)), t + dt * k + R.uniform(0, 0.04), size=size * (0.8 + 0.5 * u),
                      n=1, rise=rise * (1 + u), life=life, color=color, opacity=opacity * (1 - 0.3 * u))


# ------------------------------------------------------------------------------- the Sentinel
sen = P.load('sentinel', at=(0, 0), heading=0, label='sentinel')
bpy.context.view_layer.update()
tp = sen.parts['TurretPivot']
turret_mesh = sen.parts['Turret']

# crown = top-centre of the turret dome (the gold orb); an empty riding the turret
tw = turret_mesh.matrix_world
piv = tp.matrix_world.translation
vs = [tw @ v.co for v in turret_mesh.data.vertices]
near = [v for v in vs if (v.x - piv.x) ** 2 + (v.y - piv.y) ** 2 < 0.6 ** 2]
ztop = max(v.z for v in near)
crown_w = Vector((piv.x, piv.y, ztop - 0.15))
crown = empty('Crown')
crown.parent = turret_mesh
crown.matrix_parent_inverse = tw.inverted()
crown.location = crown_w
print('CROWN', crown_w, 'pivot', piv)

sen.split_barrels()
mz = sen.muzzle()
bpy.context.view_layer.update()
mz_dep = mz.matrix_world.translation.copy()
gun_yaw0 = math.degrees(math.atan2(mz_dep.y - piv.y, mz_dep.x - piv.x))
print('GUN yaw deployed', gun_yaw0, 'muzzle', mz_dep, 'barrels', len(sen.barrels))

q_dep = tp.rotation_quaternion.copy() if tp.rotation_mode == 'QUATERNION' else tp.rotation_euler.to_quaternion()
sen.unfold(T_UNF0, T_UNF1)

# glide in: low and fast over the flats, nose down while racing, flare and settle
root = sen.root
root.rotation_mode = 'XYZ'
glide = [(0.0, (-30.0, -8.5, 1.5), 4, -3, -6), (0.7, (-17.0, -5.2, 1.45), -3, -4, 4),
         (1.25, (-6.0, -1.6, 1.3), 2, -2, 8), (1.55, (-1.2, -0.3, 0.75), 0, 3.5, 3),
         (T_LAND, (0, 0, -LIFT), 0, 0, 0)]
for t, p, rx, ry, rz in glide:
    root.location = p
    root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
root.location = (0, 0, -LIFT - 0.08)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.05))
root.location = (0, 0, -LIFT)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.22))
root.keyframe_insert('location', frame=P.T(T_UNF0))
root.location = (0, 0, 0)          # the packed carrier sits 0.34 m above the deployed base: rise as it opens
root.keyframe_insert('location', frame=P.T(T_UNF1))
set_interp(root, 'BEZIER')
# gentle float while gliding (on the model, stacks with the root path)
m = sen.model_root
for i in range(0, 9):
    t = i * T_LAND / 8
    m.location.z = 0.08 * math.sin(2 * math.pi * 1.4 * t) * (1 - t / T_LAND)
    m.keyframe_insert('location', index=2, frame=P.T(t))


def sen_pos(t):
    return sen.pos_at(t)


# lifter legs: 4-5 jagged gold bolts from under the carrier to the ground, raking along
gl = link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
gl.parent = root
gl.location = (0, 0, -0.3)
gl.data.color = GOLD
gl.data.shadow_soft_size = 1.5
for t, e in [(0.0, 1400), (1.3, 1400), (T_LAND, 600), (T_LAND + 0.12, 0)]:
    gl.data.energy = e
    gl.data.keyframe_insert('energy', frame=P.T(t))

f_end = int(round(P.T(T_LAND + 0.08)))
for f in range(1, f_end + 1):
    t = (f - 1) / P.fps
    c = sen_pos(t)
    h = max(0.12, c.z + LIFT)
    fade = 1.0 if t < T_LAND - 0.15 else max(0.0, (T_LAND + 0.08 - t) / 0.23)
    nlegs = 5 if fade > 0.6 else 3
    for k in range(nlegs):
        if R.random() < 0.18:
            continue
        a = 2 * math.pi * k / nlegs + R.uniform(-0.4, 0.4) + t * 3.0
        r0 = R.uniform(0.9, 1.6)
        p0 = c + Vector((r0 * math.cos(a), r0 * math.sin(a), LIFT + 0.1))
        r1 = r0 * R.uniform(1.0, 1.5)
        # legs trail behind (motion is +X) so it reads as riding the bolts
        p1 = c + Vector((r1 * math.cos(a) - 0.7 * h, r1 * math.sin(a), -h))
        p1.z = 0.02
        bolt_frame(jag_pts(p0, p1, 6, 0.28), f, 0.035 * (0.5 + 0.5 * fade), forks=1 if k % 2 else 0)
    # ground contact: little dust kicks where the bolts rake
    if f % 2 == 0 and t < T_LAND:
        _kit_puff(Vector((c.x - 0.8, c.y + R.uniform(-1.5, 1.5), 0.15)), t, size=1.0, n=1, rise=0.5,
                  life=0.9, color=SAND, opacity=0.32)
        if f % 4 == 0:
            gold_sparks(Vector((c.x - 0.6, c.y + R.uniform(-1.2, 1.2), 0.1)), t, size=0.35, n=3)

dust_wave((0, 0, 0), T_LAND - 0.03, 3.0, 9.0, rings=3, n=26, size=1.0, life=1.3, opacity=0.24)

# crown idle crackle once deployed + charge before the chain
def crown_w_at(t):
    return sen.world_at(crown, t)


M_ORB = emit_mat('SnOrb', DEEP, 0.0)
orb = sphere('CrownOrb', 1.0, M_ORB, seg=(14, 10))
orb.parent = crown
orb.scale = (0.32,) * 3
for t, v in [(0, 0), (T_UNF1 - 0.2, 0.0), (T_UNF1, 1.4), (3.0, 1.4), (3.28, 2.2), (3.4, 1.2), (6.0, 1.4)]:
    key_strength(M_ORB, P.T(t), v)
orb.scale = (0.01,) * 3
orb.keyframe_insert('scale', frame=P.T(T_UNF1 - 0.25))
orb.scale = (0.3,) * 3
orb.keyframe_insert('scale', frame=P.T(T_UNF1))
orb.keyframe_insert('scale', frame=P.T(3.02))
orb.scale = (0.38,) * 3
orb.keyframe_insert('scale', frame=P.T(3.3))
orb.scale = (0.3,) * 3
orb.keyframe_insert('scale', frame=P.T(3.45))
show_between(orb, P.T(T_UNF1 - 0.25), P.nf + 2)

t = T_UNF1
while t < 6.0:
    charging = 3.0 <= t < 3.3
    n = 3 if charging else 1
    for _ in range(n):
        if not charging and R.random() < 0.45:
            continue
        a = R.uniform(0, 2 * math.pi)
        rad = R.uniform(1.0, 1.7) if charging else R.uniform(0.6, 1.1)
        c = crown_w_at(t)
        p0 = c + Vector((rad * math.cos(a), rad * math.sin(a), R.uniform(-0.9, -0.2)))
        f = int(round(P.T(t)))
        bolt_frame(jag_pts(p0, c, 5, 0.3), f, 0.03 if charging else 0.022, forks=0, glow=charging, nframes=2)
    t += 2 / P.fps
P.light(crown_w + Vector((0, 0, 0.4)), 3.0, GOLD, energy=900, dur=0.32, radius=0.4)

# ------------------------------------------------------------------------------- Lancers
lan_paths = [
    [(0.0, (34.0, 3.0)), (3.3, (17.0, 2.0))],
    [(0.0, (35.0, -5.0)), (3.3, (19.5, -4.2))],
    [(0.0, (37.0, 10.0)), (3.4, (21.5, 8.2)), (4.55, (24.5, 9.8))],
]
lan = []
for i, pth in enumerate(lan_paths):
    a = P.load('lancer', at=pth[0][1], heading=180, label=f'lancer{i}')
    a.split_barrels()
    lan.append(a)
for i in (0, 1):
    lan[i].path(lan_paths[i])
# survivor: drives in, then reverses (keeps facing the tower)
lan[2].path([(0.0, (37.0, 10.0), 196), (3.4, (21.5, 8.2), 196), (4.55, (24.5, 9.8), 202)], face=False)
for i, a in enumerate(lan):
    P.dust(a, 0.0, 3.3, every=0.18, size=0.7)

# each Lancer fires at its own rhythm while the tower is opening
shots = {0: [2.1, 3.05], 1: [2.45], 2: [1.75, 2.75, 3.95]}
for i, ts in shots.items():
    for k, t in enumerate(ts):
        a = lan[i]
        a.aim(t - 0.02, sen, dur=0.4)
        tgt = sen.pos_at(t) + Vector((R.uniform(-0.8, 0.4), R.uniform(-1.0, 1.0), R.uniform(0.6, 1.6)))
        if t < 1.9:
            tgt = Vector((2.5, R.uniform(-2, 2), 0.1))    # first shot lands short as it touches down
        a.fire(t, tgt, kind='cannon', kick=3.0, size=0.65, impact_size=1.3)

# ------------------------------------------------------------------------------- the chain
T_CHAIN = 3.3


def anchor(actor, z=0.9):
    return lambda t: actor.pos_at(t) + Vector((0, 0, z))


bolt(crown_w_at, anchor(lan[0]), T_CHAIN, T_CHAIN + 0.3, width=0.075, jag=0.18, segs=16, forks=3, light=4000)
bolt(anchor(lan[0]), anchor(lan[1]), T_CHAIN + 0.07, T_CHAIN + 0.34, width=0.06, jag=0.22, segs=12, forks=2, light=2500)
gold_sparks(lan[0].pos_at(T_CHAIN) + Vector((0, 0, 0.9)), T_CHAIN + 0.02, 0.8)
gold_sparks(lan[1].pos_at(T_CHAIN) + Vector((0, 0, 0.9)), T_CHAIN + 0.09, 0.8)
lan[0].destroy(T_CHAIN + 0.2, size=2.3)
lan[1].destroy(T_CHAIN + 0.32, size=2.3)

# ------------------------------------------------------------------------------- turret tracks the survivor, one gold round
def set_turret(t, world_yaw):
    d = math.radians(world_yaw - gun_yaw0)
    tp.rotation_mode = 'QUATERNION'
    tp.rotation_quaternion = Quaternion((0, 0, 1), d) @ q_dep
    tp.keyframe_insert('rotation_quaternion', frame=P.T(t))


def yaw_to(p):
    return math.degrees(math.atan2(p.y - piv.y, p.x - piv.x))


set_turret(T_UNF1 + 0.02, gun_yaw0)
set_turret(3.6, yaw_to(lan[0].pos_at(3.3)))
y3 = yaw_to(lan[2].pos_at(4.5))
set_turret(4.3, y3 + 1.5)
set_turret(4.45, y3)
set_turret(6.0, y3)
set_interp(tp, 'BEZIER')

T_GUN = 4.5
p_m = sen.world_at(mz, T_GUN)
p_t = lan[2].pos_at(T_GUN + 0.1) + Vector((0, 0, 0.8))
th = P.projectile(p_m, p_t, T_GUN, speed=70, color=GOLD, size=0.22)
# gold sheath around the slug path: short crackle along it
bolt(lambda t: p_m, lambda t: p_t, T_GUN, T_GUN + 0.12, width=0.05, jag=0.08, segs=14, forks=1, light=2000)
sen.recoil(T_GUN, collapse=0.8, kick=2.0, back=0.12)
P.muzzle_flash(mz, T_GUN, GOLD, 0.9)
gold_sparks(p_t, th, 1.0)
lan[2].destroy(th + 0.02, size=2.6)

# ------------------------------------------------------------------------------- camera
P.camera([
    (0.0, (-25.0, -14.0, 1.0), sen.pos_at(0.0) + Vector((0, 0, 0.5)), 27),
    (0.8, (-15.0, -12.0, 1.2), sen.pos_at(0.8) + Vector((0, 0, 0.5)), 25),
    (1.5, (-7.5, -10.0, 1.6), (-0.8, -0.2, 1.2), 28),
    (2.2, (-1.5, -10.5, 1.7), (2.0, 0.5, 1.6), 28),
    (2.95, (-5.5, -7.5, 4.4), (6.5, 1.5, 1.0), 26),
    (3.45, (-8.5, -4.6, 5.0), (11.0, 2.0, 0.4), 27),
    (3.9, (-6.5, -6.5, 3.6), (10.0, 4.0, 1.2), 27),
    (4.5, (-4.2, -9.0, 2.8), (7.0, 4.0, 1.4), 26),
    (6.0, (-4.5, -8.5, 3.0), (5.0, 1.5, 1.2), 26),
], shake=0.02)
P.cam_shake(T_LAND, 0.18, 0.4)
P.cam_shake(T_CHAIN + 0.05, 0.12, 0.4)
P.cam_shake(th, 0.12, 0.4)

# explosion cores flash white under Standard: deepen to fire; wreck flames saturated
for mat in bpy.data.materials:
    if mat.name.startswith('Core'):
        em = mat.node_tree.nodes[mat['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.35, 0.05, 1)
        em.inputs['Strength'].default_value = 5.0
    if mat.name.startswith('Slug'):      # kit slugs are strength 12: white streaks
        em = mat.node_tree.nodes[mat['emit_node']]
        em.inputs['Strength'].default_value = 3.0

P.render()
