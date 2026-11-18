"""Skimmer (Terran hover tank): agile and slippery.

Two Arcadian Gliders chase a Skimmer down a dry riverbed. It bursts past the camera low over the
silt, its four fans throwing a dust wake, then whips round in a banked skid to face them while
still sliding backwards. A quick 2-round burst on the move: the lead Glider is hit, hit again,
and its wreck crashes into the bed. The second Glider answers with a pair of gold bolts; the
Skimmer flicks sideways and both bolts slam the silt where it was. It answers with another
2-round burst, the second Glider goes down, and the Skimmer slides away past us, turret still
trained up the riverbed, both wrecks burning behind it.

0-1.5     low on the riverbed: the Skimmer races at us and bursts past, dust wake; two gold
          glints (the Gliders) far behind it. The camera whips round after it.
1.5-3.25  from the bank, three-quarter: the banked skid (spray fans out), it slides backwards
          and fires its burst; the lead Glider is hit twice and crashes.
3.25-6    low beside the Skimmer: gold bolts come in, it flicks sideways, they miss; it answers,
          the second Glider goes down; it drifts past us into the end frame.

Models by name only (skimmer, glider)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as W  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('terran_skimmer', seconds=6.0, seed=7)
FPS = P.fps
NF = P.nf
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']


def ss(x):
    return K.smoothstep(x)


def wrap(a):
    while a > 180:
        a -= 360
    while a < -180:
        a += 360
    return a


# --------------------------------------------------------------------------- terrain: the riverbed
BED_D = 2.3       # bed below the plain
BED_W = 7.5       # flat bed half width
BANK_W = 3.6      # bank slope width


def cy(x):
    """Bed centre line."""
    return 1.6 * math.sin(x / 23.0 + 0.4)


def bed(x, y):
    d = abs(y - cy(x))
    if d < BED_W:
        return -BED_D
    u = (d - BED_W) / BANK_W
    if u < 1:
        return -BED_D * (1 - ss(u)) + 0.5 * math.sin(math.pi * u) ** 2
    return 0.0


BED_CLEAR = [(x, cy(x), BED_W + 0.5) for x in range(-70, 46, 8)]
P.env('dusk', sun=(64, 0, -130), sun_energy=4.2, clear=BED_CLEAR, props=40)
g = P.ground
for v in g.data.vertices:
    if abs(v.co.x) < 150:
        v.co.z += bed(v.co.x, v.co.y)
g.data.update()
for x, y, r in BED_CLEAR:
    P.flatten(x, y, r - 1.5)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


BZ = -BED_D      # bed level

# --------------------------------------------------------------------------- the Skimmer's run
# (t, (x, y)): races +X down the bed, whips round, slides backwards, flicks sideways to dodge
SK_RUN = [
    (0.0, (-26.0, -1.0)),
    (0.5, (-18.2, -0.7)),
    (1.0, (-10.4, -1.3)),
    (1.5, (-2.8, -1.0)),
    (1.8, (1.2, -0.3)),
    (2.1, (3.5, 0.8)),
    (2.4, (4.6, 1.8)),
    (2.8, (5.0, 2.9)),
    (3.2, (5.2, 3.8)),
    (3.5, (5.3, 4.3)),
    (3.75, (5.3, 2.8)),
    (4.0, (5.5, 1.3)),
    (4.5, (6.1, -0.4)),
    (5.0, (7.1, -1.9)),
    (5.5, (8.4, -3.2)),
    (6.0, (9.9, -4.3)),
    (6.5, (11.4, -5.2)),
]
# hull heading: straight run, the whip round (counter-clockwise) to face back up the bed,
# then it holds its nose on the fight while sliding
SK_HEAD = [(0.0, 2.0), (1.45, -2.0), (1.6, 12.0), (1.8, 70.0), (2.0, 135.0), (2.2, 172.0),
           (2.4, 186.0), (2.7, 181.0), (3.3, 176.0), (3.6, 184.0), (4.0, 192.0), (4.6, 196.0),
           (5.3, 203.0), (6.5, 210.0)]


def hermite(keys, t):
    """Catmull-Rom through time-stamped 2D keys (C1, non-uniform)."""
    ts = [k[0] for k in keys]
    ps = [Vector(k[1]) for k in keys]
    if t <= ts[0]:
        v = (ps[1] - ps[0]) / (ts[1] - ts[0])
        return ps[0] + v * (t - ts[0])
    if t >= ts[-1]:
        v = (ps[-1] - ps[-2]) / (ts[-1] - ts[-2])
        return ps[-1] + v * (t - ts[-1])
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)

    def tan(j):
        a, b = max(0, j - 1), min(len(ts) - 1, j + 1)
        return (ps[b] - ps[a]) / (ts[b] - ts[a])
    h = ts[i + 1] - ts[i]
    u = (t - ts[i]) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return ps[i] * h00 + tan(i) * h * h10 + ps[i + 1] * h01 + tan(i + 1) * h * h11


def head_at(keys, t):
    ts = [k[0] for k in keys]
    if t <= ts[0]:
        return keys[0][1]
    if t >= ts[-1]:
        return keys[-1][1]
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
    u = (t - ts[i]) / (ts[i + 1] - ts[i])
    # smooth but C1-ish: Catmull-Rom on the scalar
    a = keys[max(0, i - 1)][1]
    b, c = keys[i][1], keys[i + 1][1]
    d = keys[min(len(keys) - 1, i + 2)][1]
    return 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)


SK_HOV = 0.3


def sk_xy(t):
    return hermite(SK_RUN, t)


def body_frame_acc(xy_fn, head_fn, t, h=1.0 / 24):
    p0, p1, p2 = xy_fn(t - h), xy_fn(t), xy_fn(t + h)
    acc = (p2 - 2 * p1 + p0) / (h * h)
    a = math.radians(head_fn(t))
    fwd = Vector((math.cos(a), math.sin(a)))
    left = Vector((-math.sin(a), math.cos(a)))
    return acc.dot(fwd), acc.dot(left)


sk = P.load('skimmer', at=(SK_RUN[0][1][0], SK_RUN[0][1][1]), heading=0, label='skimmer')
sk.split_barrels() or sk.split_barrels(max_frac=0.6, thin=0.65)
print('SKIMMER barrels', [(b.name, round(b['barrel_len'], 2), round(b['tip_x'], 2)) for b in sk.barrels])
# own bank and pitch (a hover tank throws its weight around), the motion layer adds sway/recoil
sk.motion['roll'] = False
sk.motion['pitch'] = False

raw_roll, raw_pitch = [], []
for f in range(1, NF + 3):
    t = (f - 1) / FPS
    al, at = body_frame_acc(sk_xy, lambda tt: head_at(SK_HEAD, tt), t)
    raw_roll.append(max(-24.0, min(24.0, -1.5 * at)))
    raw_pitch.append(max(-9.0, min(9.0, 0.55 * al)))


def gsmooth(xs, s=2.0):
    out = []
    r = int(3 * s)
    for i in range(len(xs)):
        acc, wsum = 0.0, 0.0
        for k in range(-r, r + 1):
            j = min(len(xs) - 1, max(0, i + k))
            w = math.exp(-0.5 * (k / s) ** 2)
            acc += xs[j] * w
            wsum += w
        out.append(acc / wsum)
    return out


s_roll, s_pitch = gsmooth(raw_roll, 2.0), gsmooth(raw_pitch, 2.0)
keys = []
for f in range(1, NF + 3):
    t = (f - 1) / FPS
    p = sk_xy(t)
    keys.append((t, (p.x, p.y, gz(p.x, p.y) + SK_HOV), head_at(SK_HEAD, t)))
sk.path(keys, interp='LINEAR')
rt = sk.root
for f in range(1, NF + 3):
    rt.rotation_euler.x = math.radians(s_roll[f - 1])
    rt.rotation_euler.y = math.radians(s_pitch[f - 1])
    rt.keyframe_insert('rotation_euler', index=0, frame=f)
    rt.keyframe_insert('rotation_euler', index=1, frame=f)
K.set_interp(rt, 'LINEAR')
sk.hover_bob(0.04, 1.3)
for fan in ('FanFLPivot', 'FanFRPivot', 'FanBLPivot', 'FanBRPivot'):
    sk.spin(fan, 1440 if fan[4] == 'L' else -1440, 0.0, 6.2)


def skp(t):
    return sk.pos_at(t)


# neon fan glow: a soft blue disc under each fan and a pool light under the hull
FANS = {k: sk.parts[k] for k in ('FanFLPivot', 'FanFRPivot', 'FanBLPivot', 'FanBRPivot') if k in sk.parts}
fan_mat = emit_mat('SkimFanGlow', NEON, 2.2, alpha=0.75)
for k, fp in FANS.items():
    d = K.sphere('SkimFanDisc', 0.22, fan_mat, seg=(16, 6))
    d.parent = fp
    d.location = (0, 0, -0.03)
    d.scale = (1.0, 1.0, 0.12)
    d.visible_shadow = False
under = link(bpy.data.objects.new('SkimUnderLight', bpy.data.lights.new('SkimUnderLight', 'POINT')))
under.parent = sk.model_root
under.location = (-0.2, 0, 0.05)
under.data.color = NEON
under.data.energy = 160
under.data.shadow_soft_size = 1.2

# --------------------------------------------------------------------------- the Gliders
G_HOV = 0.85
GA_RUN = [(0.0, (-40.0, 2.6)), (0.8, (-31.0, 2.2)), (1.6, (-22.6, 2.9)), (2.2, (-16.6, 2.4)),
          (2.68, (-14.4, 2.1)), (3.2, (-13.2, 1.9))]
GB_RUN = [(0.0, (-47.0, -3.2)), (0.8, (-38.0, -3.6)), (1.6, (-29.4, -3.0)), (2.4, (-22.0, -4.0)),
          (3.0, (-17.8, -5.0)), (3.6, (-15.4, -5.6)), (4.2, (-13.6, -5.4)), (4.81, (-12.0, -5.0)),
          (5.4, (-10.6, -4.6))]


def make_glider(label, run, nose_on=None):
    a = P.load('glider', at=run[0][1], heading=0, label=label)
    kk = []
    prev = None
    for f in range(1, NF + 3):
        t = (f - 1) / FPS
        p = hermite(run, t)
        d = hermite(run, t + 0.05) - hermite(run, t - 0.05)
        h = math.degrees(math.atan2(d.y, d.x))
        if nose_on is not None:
            w = nose_on(t)
            if w > 0:
                s = sk_xy(t)
                ht = math.degrees(math.atan2(s.y - p.y, s.x - p.x))
                h = h + wrap(ht - h) * w
        if prev is not None:
            h = prev + wrap(h - prev)
        prev = h
        kk.append((t, (p.x, p.y, gz(p.x, p.y) + G_HOV), h))
    a.path(kk, interp='LINEAR')
    a.hover_bob(0.05, 1.1)
    return a


def nose_b(t):
    # B swings its nose onto the Skimmer for its pair of bolts, and keeps it there
    return ss((t - 2.7) / 0.5)


GA = make_glider('gliderA', GA_RUN)
GB = make_glider('gliderB', GB_RUN, nose_on=nose_b)

# glider B: the nose guns cut out of the hull so each collapses on its own shot (as in
# arcadian_glider.py)
hull = GB.parts['Hull']
me = hull.data
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
GUN_X = 2.85
sides = {1: [], -1: []}
for fc in bm.faces:
    c = fc.calc_center_median()
    if c.x > GUN_X and 0.25 < abs(c.y) < 0.85 and 0.7 < c.z < 1.15:
        sides[1 if c.y > 0 else -1].append(fc.index)
GB_BARRELS, GB_MUZZLES = {}, {}
all_idx = set(sides[1]) | set(sides[-1])
for sgn in (1, -1):
    b2 = bm.copy()
    b2.faces.ensure_lookup_table()
    keep = set(sides[sgn])
    bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
    bme = bpy.data.meshes.new(f'GliderGun{"L" if sgn > 0 else "R"}')
    b2.to_mesh(bme)
    b2.free()
    for m in me.materials:
        bme.materials.append(m)
    bo = link(bpy.data.objects.new(bme.name, bme))
    bo.parent = hull
    xs = [v.co.x for v in bme.vertices]
    bo['barrel_len'] = (max(xs) - GUN_X) if xs else 0.8
    bo['axis'] = (1.0, 0.0, 0.0)
    mz = K.empty(f'gliderB_Muzzle{"L" if sgn > 0 else "R"}')
    mz.parent = bo
    mz.location = (3.74, 0.55 * sgn, 0.92)
    GB_BARRELS[sgn] = bo
    GB_MUZZLES[sgn] = mz
if all_idx:
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in all_idx], context='FACES')
    bm.to_mesh(me)
bm.free()
print('GLIDER gun faces', len(sides[1]), len(sides[-1]))

# lightning lifters + tail thruster, parented to the root (not the model, so the fracture
# destroy never picks the bolts up)
bolt_mat = emit_mat('GliderLiftBolt', GOLD, 1.9)
glow_mat = emit_mat('GliderLiftGlow', GOLD, 0.7, alpha=0.2)


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


def crackle(a, f_end, n_lift=6, n_tail=2):
    rnd = P.rnd
    bpy.context.view_layer.update()
    hl = a.parts['Hull']
    M = a.root.matrix_world.inverted() @ hl.matrix_world
    pods = [M @ Vector((1.0, 0.0, 0.05)), M @ Vector((-1.4, 0.1, 0.05))]
    tail = M @ Vector((-3.55, 0.0, 0.95))
    for f in range(1, min(NF + 2, f_end)):
        objs = []
        for k in range(n_lift):
            pod = pods[k % 2]
            p0 = pod + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.18, 0.18), 0.0))
            side = rnd.choice((-1, 1))
            p1 = p0 + Vector((-rnd.uniform(0.05, 0.3), side * rnd.uniform(0.08, 0.3), -rnd.uniform(0.1, 0.35)))
            pts = jag(p0, p1, 4, 0.06, rnd)
            objs += [polyline('GLift', pts, 0.01, bolt_mat), polyline('GLiftHalo', pts, 0.035, glow_mat)]
        for k in range(n_tail):
            p0 = tail + Vector((0, rnd.uniform(-0.12, 0.12), rnd.uniform(-0.08, 0.08)))
            p1 = p0 + Vector((-rnd.uniform(0.6, 1.1), rnd.uniform(-0.25, 0.25), rnd.uniform(-0.15, 0.1)))
            pts = jag(p0, p1, 5, 0.12, rnd)
            objs += [polyline('GThrust', pts, 0.016, bolt_mat), polyline('GThrustHalo', pts, 0.05, glow_mat)]
        for o in objs:
            o.parent = a.root
            o.visible_shadow = False
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('GliderLiftLight', bpy.data.lights.new('GliderLiftLight', 'POINT')))
    L.parent = a.root
    L.location = (0, 0, 0.1)
    L.data.color = GOLD
    L.data.energy = 90
    L.data.shadow_soft_size = 0.8
    key_light_off(L, f_end)


def key_light_off(L, f):
    L.data.keyframe_insert('energy', frame=f - 1)
    e = L.data.energy
    L.data.energy = 0
    L.data.keyframe_insert('energy', frame=f)
    L.data.energy = e


# --------------------------------------------------------------------------- helpers
def flinch(a, t, amt=4.0, axis=0):
    mr = a.model_root
    mr.rotation_mode = 'XYZ'
    f = P.T(t)
    mr.keyframe_insert('rotation_euler', index=axis, frame=f - 1)
    mr.rotation_euler[axis] = math.radians(amt)
    mr.keyframe_insert('rotation_euler', index=axis, frame=f + 2)
    mr.rotation_euler[axis] = math.radians(-amt * 0.4)
    mr.keyframe_insert('rotation_euler', index=axis, frame=f + 6)
    mr.rotation_euler[axis] = 0
    mr.keyframe_insert('rotation_euler', index=axis, frame=f + 10)


def ground_hit(p0, p1):
    d = (p1 - p0).normalized()
    q = Vector(p1)
    for _ in range(600):
        if q.z <= gz(q.x, q.y) + 0.05:
            return q
        q = q + d * 0.1
    return Vector((q.x, q.y, gz(q.x, q.y) + 0.05))


def sk_fire(t, target_actor):
    """One Skimmer round: lead the moving Glider, tracer, barrel collapse, hull kick."""
    p0 = sk.world_at(sk.muzzle(), t)
    tgt = target_actor.pos_at(t + 0.3) + Vector((0, 0, 0.75))
    for _ in range(2):
        tt = t + (tgt - p0).length / 62.0
        tgt = target_actor.pos_at(tt) + Vector((0, 0, 0.75))
    sk.aim(t, tgt, dur=0.12)
    return sk.fire(t, tgt, kind='cannon', speed=62, kick=3.0, impact_size=0.9)


def wreck_fire(actor, t, size):
    """Flames riding the biggest wreck piece + a smoke column where it ends up (the flipbook
    fire/smoke the fracture destroy would add are not in the library on this machine)."""
    frags = [o for o in bpy.data.objects if o.name.startswith(actor.name + '_Frag')]
    if not frags:
        return
    big = max(frags, key=lambda o: len(o.data.vertices))
    fm = P.soft_fire_mat()
    t0 = t + 0.15
    for i in range(5):
        o = K.sphere('WreckFlame', 1.0, fm, seg=(12, 8))
        o.parent = big
        o.location = Vector((P.rnd.uniform(-.5, .5), P.rnd.uniform(-.5, .5), 0.25)) * size
        o.visible_shadow = False
        f = P.T(t0)
        while f < P.T(6.2):
            s_ = size * P.rnd.uniform(0.18, 0.32)
            o.scale = (s_, s_, s_ * 2.0)
            o.color = (1.0, P.rnd.uniform(0.25, 0.42), 0.05, P.rnd.uniform(0.5, 0.85))
            o.keyframe_insert('scale', frame=f)
            o.keyframe_insert('color', frame=f)
            f += 2
        show_between(o, P.T(t0), P.T(6.2) + 1)
    sc = bpy.context.scene
    sc.frame_set(int(P.T(min(6.0, t + 1.2))))
    rest = big.matrix_world.translation.copy()
    sc.frame_set(1)
    tt = t + 0.3
    while tt < 6.0:
        W.smoke_puff(P, rest + Vector((P.rnd.uniform(-.4, .4), P.rnd.uniform(-.4, .4), 0.4)), tt,
                     r0=0.15, r1=P.rnd.uniform(0.5, 0.9) * size, life=2.0,
                     vel=(P.rnd.uniform(-.4, .4), P.rnd.uniform(-.4, .4), 1.8), color=(0.2, 0.18, 0.17),
                     dens=0.45, wind=(0.7, 0.25, 0.5))
        tt += 0.1
    L = link(bpy.data.objects.new('WreckFireLight', bpy.data.lights.new('WreckFireLight', 'POINT')))
    L.parent = big
    L.location = (0, 0, 0.8)
    L.data.color = (1.0, 0.45, 0.12)
    L.data.shadow_soft_size = 0.6
    f = P.T(t0)
    L.data.energy = 0
    L.data.keyframe_insert('energy', frame=f - 1)
    while f < P.T(6.2):
        L.data.energy = 260 * P.rnd.uniform(0.7, 1.15)
        L.data.keyframe_insert('energy', frame=f + 3)
        f += 3


TCOMP = 0.75


def kill(actor, t, size):
    """Fracture destroy (promo_fx) + fireball; hover wrecks drop and crash into the bed."""
    import promo_fx
    ok = promo_fx.destroy(actor, t, size=size, wreck=True, debris=24)
    if ok:
        # snappier debris: compress the fragments' flight in time (reads less floaty at 24 fps)
        fk = P.T(t)
        for o in bpy.data.objects:
            if o.name.startswith(actor.name + '_Frag') and o.animation_data and o.animation_data.action:
                for fc in K._fcurves(o.animation_data.action):
                    if not fc.data_path.startswith(('location', 'rotation')):
                        continue
                    for kp in fc.keyframe_points:
                        if kp.co.x > fk:
                            dx = (kp.co.x - fk) * (TCOMP - 1.0)
                            kp.co.x += dx
                            kp.handle_left.x += dx
                            kp.handle_right.x += dx
                    if fc.data_path == 'location' and fc.array_index == 2 and len(fc.keyframe_points) > 2:
                        zr = fc.keyframe_points[-1].co.y
                        for kp in fc.keyframe_points:
                            w = min(1.0, max(0.0, (kp.co.x - fk) / 4.0)) * 0.6
                            if kp.co.y > zr:
                                d = (kp.co.y - zr) * w
                                kp.co.y -= d
                                kp.handle_left.y -= d
                                kp.handle_right.y -= d
    if ok:
        actor.vanish(t + 1 / FPS)
        actor.alive_until = t
    else:
        actor.destroy(t, size=size)
    p = actor.pos_at(t)
    if not promo_fx.find_flipbook('explo_ground'):
        P.explosion(p + Vector((0, 0, 0.5)), t, size=size, debris=6, smoke=False)
        wreck_fire(actor, t, size * 0.6)
    P.cam_shake(t + 0.02, 0.1, 0.4)


# --------------------------------------------------------------------------- the fight
# turret: forward on the run, swings with the whip onto Glider A
sk.turret_yaw([(0.0, 0.0), (1.55, 0.0)])
sk.aim(2.0, GA.pos_at(2.0) + Vector((0, 0, 0.7)), dur=0.4)

# burst 1: two rounds on the move, ~0.2 s apart
T_B1 = (2.15, 2.36)
th1 = sk_fire(T_B1[0], GA)
flinch(GA, th1, 6.0)
th2 = sk_fire(T_B1[1], GA)
T_KILL_A = th2
kill(GA, T_KILL_A, 1.8)
crackle(GA, int(P.T(T_KILL_A)) + 1)

# turret follows Glider B
t = T_B1[1] + 0.35
while t < 3.4:
    sk.aim(t, GB.pos_at(t) + Vector((0, 0, 0.7)), dur=0.3)
    t += 0.3


# Glider B's answer: left gun, right gun, aimed where the Skimmer is drifting; the Skimmer
# flicks the other way and both bolts slam the silt
def gfire(t, sgn, target):
    GB.barrels = [GB_BARRELS[sgn]]
    GB._muzzles = [GB_MUZZLES[sgn]]
    GB._last_recoil = -99.0
    GB.recoil(t, collapse=0.8, kick=3.0, back=0.15)
    P.muzzle_flash(GB_MUZZLES[sgn], t, GOLD, 0.8)
    p0 = GB.world_at(GB_MUZZLES[sgn], t - 1.0 / FPS)
    hit = ground_hit(p0, target)
    th = P.projectile(p0, hit, t, speed=42, color=GOLD, size=0.26)
    P.impact(hit, th, size=1.0, color=GOLD)
    return th


T_GB = (3.38, 3.52)
for tf, sgn in zip(T_GB, (1, -1)):
    # predicted: where the Skimmer would be if it kept drifting (+Y)
    s = sk_xy(3.5)
    pred = Vector((s.x + 0.4 + (0.8 if sgn < 0 else 0.0), s.y + 0.9, BZ + 0.25))
    gfire(tf, sgn, pred)

# burst 2: on Glider B, still sliding
t = 3.55
while t < 4.2:
    sk.aim(t, GB.pos_at(t) + Vector((0, 0, 0.7)), dur=0.25)
    t += 0.25
T_B2 = (4.3, 4.51)
th3 = sk_fire(T_B2[0], GB)
flinch(GB, th3, -6.0)
th4 = sk_fire(T_B2[1], GB)
T_KILL_B = th4
kill(GB, T_KILL_B, 1.8)
crackle(GB, int(P.T(T_KILL_B)) + 1)
# afterwards the turret holds up the bed
sk.aim(5.2, Vector((-20, 0, BZ + 1.0)), dur=0.6)

# --------------------------------------------------------------------------- dust wake
DUST = (0.52, 0.38, 0.27)
GRIT = (0.2, 0.13, 0.08)


def fan_world(t):
    sc = bpy.context.scene
    sc.frame_set(int(round(P.T(t))))
    out = [fp.matrix_world.translation.copy() for fp in FANS.values()]
    c = sk.root.matrix_world.translation.copy()
    sc.frame_set(1)
    return c, out


def sk_vel(t):
    return (sk_xy(t + 0.04) - sk_xy(t - 0.04)) / 0.08


t = 0.0
while t < 6.0:
    c, fans = fan_world(t)
    v = sk_vel(t)
    spd = v.length
    al, at = body_frame_acc(sk_xy, lambda tt: head_at(SK_HEAD, tt), t)
    acc = math.hypot(al, at)
    k = min(1.0, 0.35 + spd / 16.0 + acc / 40.0)
    for fp in fans:
        out = Vector((fp.x - c.x, fp.y - c.y, 0))
        out = out.normalized() if out.length > 1e-3 else Vector((1, 0, 0))
        base = Vector((fp.x, fp.y, gz(fp.x, fp.y) + 0.12))
        vel = out * 2.2 - Vector((v.x, v.y, 0)) * 0.12 + Vector((0, 0, 0.7))
        W.smoke_puff(P, base, t + P.rnd.uniform(0, 0.03), r0=0.18, r1=P.rnd.uniform(0.8, 1.2) * (0.6 + 0.6 * k),
                     life=P.rnd.uniform(1.0, 1.5), vel=vel, color=DUST, dens=0.65 * k, wind=(0.25, 0.1, 0.25))
    t += 2.0 / FPS

# the skid: a fan of grit and a dust curtain thrown ahead as the fans brake the slide
for i in range(36):
    t = 1.62 + 0.6 * i / 36
    c = skp(t)
    v = sk_vel(t)
    dirv = Vector((v.x, v.y, 0))
    if dirv.length < 1e-3:
        continue
    dirv.normalize()
    side = Vector((-dirv.y, dirv.x, 0)) * P.rnd.uniform(-1.0, 1.0)
    p0 = Vector((c.x, c.y, BZ + 0.1)) + dirv * 1.6 + side * 1.2
    vv = (dirv * P.rnd.uniform(4, 9) + side * 3 + Vector((0, 0, P.rnd.uniform(2.5, 5.0))))
    o = K.ico('Grit', 1.0, K.pbr_mat('GritM', GRIT, rough=1.0) if i == 0 else bpy.data.materials['GritM'], sub=0)
    s = P.rnd.uniform(0.03, 0.07)
    o.scale = (s, s, s * 0.7)
    L = 2 * vv.z / 9.8
    n = max(3, int(L * FPS / 2))
    f0 = P.T(t)
    for kk in range(n + 1):
        tt = L * kk / n
        o.location = p0 + Vector((vv.x * tt, vv.y * tt, max(0.03, vv.z * tt - 4.9 * tt * tt)))
        o.keyframe_insert('location', frame=f0 + tt * FPS)
    show_between(o, int(f0), int(f0 + L * FPS) + 1)
    if i % 3 == 0:
        W.smoke_puff(P, p0 + Vector((0, 0, 0.2)), t, r0=0.3, r1=P.rnd.uniform(1.3, 1.9), life=1.8,
                     vel=dirv * 5.0 + side * 1.5 + Vector((0, 0, 1.2)), color=DUST, dens=0.8,
                     wind=(0.3, 0.1, 0.25))
# the dodge flick: a sideways sheet of dust
for i in range(6):
    t = 3.52 + 0.05 * i
    c = skp(t)
    W.smoke_puff(P, Vector((c.x, c.y + 1.0, BZ + 0.2)), t, r0=0.3, r1=1.4, life=1.6,
                 vel=(P.rnd.uniform(-1, 1), 4.0, 0.8), color=DUST, dens=0.7, wind=(0.3, 0.1, 0.25))

# --------------------------------------------------------------------------- camera
C1, C2 = 1.5, 3.25          # frames 37, 79


def look_sk(t, dz=0.7, lead=0.0):
    p = skp(t + lead)
    return Vector((p.x, p.y, p.z + dz))


cam1 = Vector((-5.0, -5.4, BZ + 0.55))
cam2 = Vector((13.5, -0.8, BZ + 1.45))
cam3 = Vector((13.0, -5.0, BZ + 0.85))
def gcam(v, h=0.85):
    return (v.x, v.y, max(v.z, gz(v.x, v.y) + h))


keys = [
    # shot 1: low on the bed; it races at us and bursts past, the camera whips after it
    (0.0, tuple(cam1), (-30.0, 0.0, BZ + 1.0), 30),
    (0.6, tuple(cam1), (-26.0, -0.6, BZ + 0.9), 30),
    (1.0, tuple(cam1 + Vector((0.1, 0, 0))), tuple(look_sk(1.0, 0.6)), 28),
    (1.2, tuple(cam1 + Vector((0.2, 0.05, 0))), tuple(look_sk(1.22, 0.6)), 26),
    (1.35, tuple(cam1 + Vector((0.3, 0.1, 0))), tuple(look_sk(1.37, 0.6)), 26),
    (C1 - 1 / FPS, tuple(cam1 + Vector((0.4, 0.15, 0))), tuple(look_sk(C1, 0.6)), 26),
    # shot 2: from the bank, three-quarter: the skid, the burst, A crashes
    (C1, tuple(cam2), tuple(look_sk(C1 + 0.1, 0.5).lerp(Vector((-14, 2.5, BZ + 0.5)), 0.3)), 28),
    (2.0, tuple(cam2 + Vector((0.3, -0.3, 0.0))), tuple(look_sk(2.0, 0.5).lerp(Vector((-14, 2.4, BZ + 0.7)), 0.35)), 28),
    (2.6, tuple(cam2 + Vector((0.5, -0.6, 0.0))), tuple(look_sk(2.6, 0.5).lerp(Vector((-12, 2.0, BZ + 0.7)), 0.35)), 28),
    (C2 - 1 / FPS, tuple(cam2 + Vector((0.6, -0.9, 0.0))), tuple(look_sk(C2, 0.5).lerp(Vector((-12, 0.0, BZ + 0.7)), 0.35)), 28),
    # shot 3: low beside the Skimmer: the bolts, the flick, burst 2, it slides past us
    (C2, gcam(cam3), tuple(look_sk(C2, 0.6).lerp(Vector((-14, -5, BZ + 0.7)), 0.12)), 26),
    (4.0, gcam(cam3 + Vector((0.6, -0.6, 0))), tuple(look_sk(4.0, 0.6).lerp(Vector((-13, -5, BZ + 0.7)), 0.22)), 27),
    (5.0, gcam(cam3 + Vector((1.9, -1.7, 0))), tuple(look_sk(5.0, 0.6).lerp(Vector((-11, -4.5, BZ + 0.7)), 0.3)), 28),
    (6.0, gcam(cam3 + Vector((3.2, -2.6, 0))), tuple(look_sk(6.0, 0.6).lerp(Vector((-11, -4.5, BZ + 0.7)), 0.3)), 28),
]
P.camera(keys, cuts=(C1, C2), shake=0.02)

# ---- sound cues for things the kit does not hear on its own
P.sfx(0.95, 'whoosh', gain=1.0)                 # bursts past the camera
P.sfx(1.6, 'skid', gain=0.8, rate=1.15)         # the whip round
P.sfx(3.45, 'whoosh', gain=0.7, rate=1.3)       # the sideways flick
P.sfx(0.0, 'crackle_loop', gain=0.18, dur=5.0)  # glider lifters (distant)

P.render()
