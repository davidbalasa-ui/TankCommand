"""Darter (Arcadian scout): a needle-fast raider runs a Lancer picket for fun.

The Darter streaks in low over the highland, zig-zagging on a skirt of gold lightning. Three
Terran Lancers traverse and fire, always a beat late: every shell slams into the dirt where it
just was. It flicks quick, weak gold bolts at each tank as it slaloms between them (pings, not
kills: the tanks flinch), then leaps a ridge and is gone. On the far side it drift-stops,
swings round and hangs there, insolent, while a last blind shell rakes the crest behind it.

0-1.42  low over a Lancer's shoulder: the Darter darts in, a shell misses behind it, it pings
        the Lancer twice and whips past camera.
1.42-3.42 chase camera running ahead of it through the picket: misses behind, quick bolts at
        each Lancer.
3.42-6  far side of the ridge: it bursts over the crest, a shell hits the crest behind it, it
        drift-stops facing the camera 3/4; a blind shell sails high overhead."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('arcadian_darter', seconds=6.0, seed=23)
FPS = P.fps
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)

# --------------------------------------------------------------------------- terrain: the ridge
RX = 25.0        # crest line (runs along Y)
RS = 4.2         # gaussian half-width
RH = 2.6         # crest height


def ridge(x, y):
    taper = K.smoothstep((46 - abs(y + 2)) / 14.0)
    wob = 0.18 * math.sin(y * 0.27) + 0.1 * math.sin(y * 0.71 + 1.3)
    return (RH + wob) * taper * math.exp(-((x - RX - 0.8 * math.sin(y * 0.09)) / RS) ** 2)


P.env('highland', sun=(52, 0, 35), clear=[(-6, 0, 30), (8, 0, 16), (37, -3, 10)], props=30)
g = P.ground
for v in g.data.vertices:
    v.co.z += ridge(v.co.x, v.co.y)
g.data.update()
for o in bpy.data.objects:   # anything already dropped on the ground: lift onto the ridge
    if o.name.startswith('prop_'):
        o.location.z += ridge(o.location.x, o.location.y)
P.flatten(4, 0, 16)
P.flatten(-20, -3, 14)
P.flatten(38, -3, 8)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


# --------------------------------------------------------------------------- the Lancer picket
LANCERS = [((0.0, 5.0), 205), ((7.0, -4.8), 160), ((13.5, 3.8), 195)]
lancers = []
for i, ((x, y), h) in enumerate(LANCERS):
    a = P.load('lancer', at=(x, y), heading=h, label=f'lancer{i + 1}')
    a.split_barrels()
    lancers.append(a)
L1, L2, L3 = lancers

# --------------------------------------------------------------------------- the Darter
# Raider scale: smaller than a Lancer (registry 4.05 m -> 3.3 m, Lancer is 4.5 m)
darter = P.load('darter', at=(-36, -7), heading=0, size=3.3, label='darter')
HOV = 0.8

# --- the fork as its "barrel": split the two prongs off the hull so they can collapse back
hull = [o for o in darter.meshes if o.name.startswith('Hull')][0]
me = hull.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
seen = set()
fork_faces = []
for v in bm.verts:
    if v.index in seen:
        continue
    comp, st = [], [v]
    seen.add(v.index)
    while st:
        u = st.pop()
        comp.append(u)
        for e in u.link_edges:
            w = e.other_vert(u)
            if w.index not in seen:
                seen.add(w.index)
                st.append(w)
    xs = [q.co.x for q in comp]
    zs = [q.co.z for q in comp]
    if min(xs) > 0.3 and max(xs) > 3.6 and min(zs) > 0.95 and max(zs) < 1.3:
        for q in comp:
            fork_faces.extend(q.link_faces)
fork_faces = list(set(fork_faces))
NOSE_X = 3.45      # hull nose (prongs reach 4.83)
TIP_X = max(q.co.x for f in fork_faces for q in f.verts) if fork_faces else 4.83
bm2 = bm.copy()
fork_idx = {f.index for f in fork_faces}
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index in fork_idx], context='FACES')
bm.to_mesh(me)
bm.free()
bm2.faces.ensure_lookup_table()
bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.index not in fork_idx], context='FACES')
fme = bpy.data.meshes.new('DarterFork')
bm2.to_mesh(fme)
bm2.free()
for m in me.materials:
    fme.materials.append(m)
fork = link(bpy.data.objects.new('DarterFork', fme))
fork.parent = hull
fork['barrel_len'] = TIP_X - NOSE_X + 0.25
fork['axis'] = (1.0, 0.0, 0.0)
darter.barrels = [fork]
mz = K.empty('darter_Muzzle')
mz.parent = fork
mz.location = (TIP_X - 0.15, 0.0, 1.12)
darter._muzzles = [mz]
print('DARTER fork faces', len(fork_faces), 'tip', TIP_X)

# emitter points in model space (model_root), measured at rest
bpy.context.view_layer.update()
inv = darter.model_root.matrix_world.inverted()
belly = [inv @ (hull.matrix_world @ v.co) for v in me.vertices if v.co.z < 0.2]
FRONT = [p for p in belly if p.x > 0]
REAR = [p for p in belly if p.x <= 0]
tail_x = min((inv @ (hull.matrix_world @ v.co)).x for v in me.vertices)
TAIL = Vector((tail_x + 0.05, 0.0, 0.0))
TAIL.z = sum((inv @ (hull.matrix_world @ v.co)).z for v in me.vertices if v.co.x < -3.6) / max(1, len([v for v in me.vertices if v.co.x < -3.6]))


def cen(ps):
    return sum(ps, Vector()) / len(ps) if ps else Vector()


EMIT = [cen(FRONT), cen(REAR)]
for e in EMIT:
    e.z = 0.04
print('DARTER emitters', EMIT, 'tail', TAIL)

# --- the run: (t, (x, y)[, heading]). Zig-zags every ~0.35 s at ~20 m/s.
RUN = [
    (0.0, (-30.0, -4.4)),
    (0.35, (-24.0, -1.0)),
    (0.7, (-18.2, -5.8)),
    (1.05, (-12.6, -1.4)),
    (1.4, (-6.8, -4.8)),
    (1.75, (-0.5, 0.6)),
    (2.1, (5.5, 0.9)),
    (2.45, (10.8, -1.4)),
    (2.8, (16.0, 0.4)),
    (3.15, (20.6, -1.0)),
    (3.5, (25.0, -1.8)),
    (3.85, (29.6, -2.6)),
    (4.2, (33.6, -3.4)),
    (4.6, (36.3, -3.9), -28.0),
    (5.1, (37.4, -4.1), 4.0),
    (5.4, (37.55, -4.0), 26.0),
    (5.65, (37.62, -4.1), 6.0),
    (6.0, (37.7, -4.0), 15.0),
]
darter.path(RUN, z=HOV, bank=0.06)
darter.hover_bob(0.05, 1.4)

# per-frame height: ride HOV over the ground (the ridge), float off the crest under gravity
rc = darter.root
zs = []
zc = None
vz = 0.0
sc = bpy.context.scene
for f in range(1, P.nf + 2):
    sc.frame_set(f)
    p = rc.matrix_world.translation
    h = rc.rotation_euler.z
    fx, fy = math.cos(h), math.sin(h)
    gmax = max(gz(p.x + fx * d, p.y + fy * d) for d in (-1.4, 0.0, 1.4))
    tgt = gmax + HOV
    if zc is None:
        zc = tgt
    elif tgt >= zc:
        vz = (tgt - zc) * FPS
        zc = tgt
    else:
        vz -= 18.0 / FPS
        zc = max(tgt, zc + vz / FPS)
        if zc == tgt:
            vz = 0.0
    zs.append((f, zc))
sc.frame_set(1)
for i, (f, z) in enumerate(zs):
    rc.location.z = z
    rc.keyframe_insert('location', index=2, frame=f)
    a_ = zs[max(0, i - 2)]
    b_ = zs[min(len(zs) - 1, i + 2)]
    sc.frame_set(f)
    # nose follows the climb/descent
    sp = 20.0 if f < P.T(4.2) else 8.0
    pit = -math.degrees(math.atan2((b_[1] - a_[1]) * FPS / (b_[0] - a_[0]), sp)) * 0.8
    rc.rotation_euler.y = math.radians(max(-14, min(14, pit)))
    rc.keyframe_insert('rotation_euler', index=1, frame=f)
sc.frame_set(1)
for fc in K._fcurves(rc.animation_data.action):
    if (fc.data_path == 'location' and fc.array_index == 2) or (fc.data_path == 'rotation_euler' and fc.array_index == 1):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def dp(t):
    return darter.pos_at(t)


# --------------------------------------------------------------------------- lightning lifters
# Short, dense crackle tucked right under the belly (never long "legs"), plus a short tail
# thruster crackle streaming back.
bolt_mat = emit_mat('DarterLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('DarterLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)


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


def crackle(a, n_lift=8, n_tail=2):
    rnd = P.rnd
    x0, x1 = EMIT[1].x - 0.35, EMIT[0].x + 0.35
    for f in range(1, P.nf + 2):
        objs = []
        for k in range(n_lift):
            p0 = Vector((rnd.uniform(x0, x1), rnd.uniform(-0.12, 0.12), 0.05))
            if k % 3 == 0:
                # crawling arc along the belly
                p1 = p0 + Vector((rnd.uniform(-0.45, 0.45), rnd.uniform(-0.15, 0.15), -rnd.uniform(0.0, 0.08)))
            else:
                # short spark splaying out and down (0.12-0.3 m), swept back by the speed
                side = rnd.choice((-1, 1))
                p1 = p0 + Vector((-rnd.uniform(0.05, 0.25), side * rnd.uniform(0.08, 0.25), -rnd.uniform(0.1, 0.22)))
            pts = jag(p0, p1, 4, 0.06, rnd)
            objs += [polyline('DLift', pts, 0.011, bolt_mat), polyline('DLiftHalo', pts, 0.04, glow_mat)]
        for k in range(n_tail):
            p0 = TAIL + Vector((0, rnd.uniform(-0.12, 0.12), rnd.uniform(-0.08, 0.08)))
            p1 = p0 + Vector((-rnd.uniform(0.45, 0.9), rnd.uniform(-0.2, 0.2), rnd.uniform(-0.15, 0.1)))
            pts = jag(p0, p1, 5, 0.1, rnd)
            objs += [polyline('DThrust', pts, 0.014, bolt_mat), polyline('DThrustHalo', pts, 0.045, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('DarterLiftLight', bpy.data.lights.new('DarterLiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.3)
    L.data.color = GOLD
    L.data.energy = 90
    L.data.shadow_soft_size = 0.6


crackle(darter)
P.dust(darter, 0.0, 3.3, every=0.07, size=0.45)
P.dust(darter, 3.75, 4.9, every=0.07, size=0.5)


# --------------------------------------------------------------------------- the fight
def flinch(a, t, amt=3.0):
    """A weak hit: the tank rocks."""
    mr = a.model_root
    mr.rotation_mode = 'XYZ'
    f = P.T(t)
    mr.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    mr.rotation_euler.x = math.radians(amt)
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    mr.rotation_euler.x = math.radians(-amt * 0.4)
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 6)
    mr.rotation_euler.x = 0
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 10)


def zap(t, tgt, amt=3.0):
    """Darter: one quick, weak gold bolt from the fork (prongs snap back, nose twitches)."""
    darter.fire(t, tgt, kind='lightning', size=0.6, kick=1.2, impact_size=0.5)
    flinch(tgt, t + 0.03, amt)


def late_shot(lancer, t, lag=0.12, aim_dur=0.45, back=0.0):
    """Lancer fires where the Darter WAS: the shell lands behind it."""
    p = dp(t - lag)
    p = Vector((p.x - back, p.y, gz(p.x, p.y) + 0.1))
    lancer.aim(t, p, dur=aim_dur)
    lancer.fire(t, p, kind='cannon')


# turrets swing after it, always late
L1.aim(0.7, dp(0.4), dur=0.6)
late_shot(L1, 1.0, lag=0.2)
zap(1.12, L1)
zap(1.27, L1)
late_shot(L2, 1.82, lag=0.18)
L1.aim(2.3, dp(1.95), dur=0.6)
zap(1.9, L2)
zap(2.03, L2)
late_shot(L3, 2.5, lag=0.15)
zap(2.42, L3)
zap(2.55, L3)
zap(2.68, L3)
late_shot(L1, 2.75, lag=0.2)
L2.aim(3.2, dp(3.0), dur=0.6)
# L3 swings round and fires as it tops the crest: the tracer skims the ridge just behind its
# tail and is gone over the far side
over = dp(3.62) + Vector((-2.2, 0.0, 0.6))
far = L3.root.location + (over - L3.root.location) * 4.0
L3.aim(3.62, far, dur=0.55)
L3.fire(3.62, far, kind='cannon', impact=False)
# L2 fires blind over the ridge: the shell sails high overhead
L2.aim(4.7, (62.0, -9.0, 7.5), dur=0.8)
L2.fire(4.7, (62.0, -9.0, 7.5), kind='cannon', impact=False)
L1.aim(4.9, (40.0, -2.0, 2.5), dur=1.2)

# --------------------------------------------------------------------------- camera
C1, C2 = 34 / FPS, 82 / FPS     # cuts at 1.417 s and 3.417 s


def chase(t, off, look_lead=1.5, lz=0.7):
    p = dp(t)
    q = dp(min(6.0, t + 0.1))
    d = (q - p)
    d.z = 0
    d = d.normalized() if d.length > 1e-3 else Vector((1, 0, 0))
    s = Vector((-d.y, d.x, 0))
    cam = p + d * off[0] + s * off[1]
    cam.z = gz(cam.x, cam.y) + off[2]
    look = p + d * look_lead
    look.z = p.z + lz - HOV + 0.4
    return tuple(cam), tuple(look)


keys = [
    # shot 1: behind Lancer 1's shoulder, the Darter darts in at us
    (0.0, (5.5, 8.6, 2.0), (-27.0, -3.0, 1.0), 75),
    (0.7, (5.2, 8.4, 1.9), (-17.0, -2.5, 1.0), 48),
    (C1 - 1 / FPS, (4.9, 8.0, 1.8), (-5.0, -1.5, 1.0), 36),
]
# shot 2: chase camera leading the Darter through the picket
for t in (C1, 1.8, 2.2, 2.6, 3.0, C2 - 1 / FPS):
    c, l = chase(t, (6.5 - 1.2 * (t - C1), -5.5, 1.5))
    keys.append((t, c, l, 30))
keys += [
    # shot 3: far side of the ridge, low; it bursts over the crest and drift-stops 3/4 to us
    (C2, (45.5, 1.0, 1.25), (26.0, -1.9, 3.0), 60),
    (4.2, (45.0, 0.6, 1.2), (31.5, -2.8, 1.8), 40),
    (5.0, (43.8, -0.4, 1.05), (37.2, -3.8, 1.25), 34),
    (6.0, (42.6, -1.2, 0.95), (37.7, -3.9, 1.3), 36),
]
P.camera(keys, cuts=(C1, C2), shake=0.025)

P.render()
