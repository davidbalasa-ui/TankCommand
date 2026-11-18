"""Glider (Arcadian hover tank): a manta-winged hunter circle-strafes a Terran Skimmer in a crater.

The Glider sweeps in low over the outer slope and skims the crater lip, wingtip lights drawing
gold trails, and drops onto the crater wall in a banking curve round the Skimmer that sits on the
crater floor. Sliding sideways with its nose locked on the Skimmer it fires its 2-shot burst
(left gun, right gun): gold bolts slam the Skimmer's hull. The Skimmer's turret chases it and
answers with its own burst; the Glider flicks up the crater wall and both shells burst on the
slope where it would have been. It carries on round, swings its nose back in and the second
burst destroys the Skimmer. It drifts to a stop on the wall, turning to face us over the
burning wreck.

0-1.25    outer slope, low: the Glider rushes at us and leaps the crater lip right over the
          camera, which cranes up to look down into the crater (the Skimmer waits below).
1.25-3.5  tracking along the crater wall behind the Glider: it slides sideways round the
          Skimmer, burst -> hits; the Skimmer replies, the Glider flicks up the wall, misses.
3.5-6     low on the far wall: the Glider sweeps round, second burst -> the Skimmer explodes;
          the Glider drift-stops in front of us, nose swinging to us, wreck burning behind."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('arcadian_glider', seconds=6.0, seed=11)
FPS = P.fps
NF = P.nf
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)

# --------------------------------------------------------------------------- terrain: the crater
CX, CY = 2.0, -1.0      # crater centre
R_FLOOR = 4.0           # flat floor radius
R_RIM = 15.0            # rim crest radius
DEPTH = 2.1             # floor below the plain
RIM_H = 2.0             # crest above the plain


def crater(x, y):
    dx, dy = x - CX, y - CY
    r = math.hypot(dx, dy)
    a = math.atan2(dy, dx)
    rr = R_RIM + 0.6 * math.sin(3 * a + 0.7) + 0.35 * math.sin(7 * a + 2.1)
    if r < rr:
        u = max(0.0, (r - R_FLOOR) / (rr - R_FLOOR))
        s = u * u * (3 - 2 * u)
        return -DEPTH + (DEPTH + RIM_H) * s ** 1.3
    return RIM_H * math.exp(-((r - rr) / 5.0) ** 1.6)


P.env('ash', sun=(56, 0, -35), clear=[(CX, CY, 4.5)], props=34)
g = P.ground
for v in g.data.vertices:
    if abs(v.co.x - CX) < 32 and abs(v.co.y - CY) < 32:
        v.co.z += crater(v.co.x, v.co.y)
g.data.update()
P.flatten(CX, CY, 21)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


def ss(x):
    return K.smoothstep(x)


def wrap(a):
    while a > 180:
        a -= 360
    while a < -180:
        a += 360
    return a


# --------------------------------------------------------------------------- the Skimmer
SK0, SK1 = (4.6, -2.4), (3.1, -1.4)
T_KILL_SHOT = 4.3
skimmer = P.load('skimmer', at=SK0, heading=165, label='skimmer')
skimmer.split_barrels()
SK_HOV = 0.32
skimmer.path([(0.0, (SK0[0], SK0[1], gz(*SK0) + SK_HOV), 165.0),
              (4.4, (SK1[0], SK1[1], gz(*SK1) + SK_HOV), 150.0)])
skimmer.hover_bob(0.03, 0.9)
for fan in ('FanFLPivot', 'FanFRPivot', 'FanBLPivot', 'FanBRPivot'):
    skimmer.spin(fan, 410, 0.0, 4.4)


def sk_pos(t):
    return skimmer.pos_at(t)


# --------------------------------------------------------------------------- the Glider's run
# (t, (x, y)): low over the plain, over the lip, then round the Skimmer on the crater wall
RUN = [
    (0.0, (-27.0, -7.2)),
    (0.3, (-21.4, -5.9)),
    (0.6, (-15.6, -4.2)),
    (0.95, (-9.6, -1.4)),
    (1.3, (-5.4, 2.0)),
    (1.7, (-1.4, 5.4)),
    (2.1, (3.1, 7.1)),
    (2.5, (7.4, 5.9)),
    (2.9, (9.9, 2.8)),
    (3.3, (10.9, -1.2)),
    (3.7, (9.9, -5.0)),
    (4.1, (7.1, -7.9)),
    (4.5, (3.3, -9.1)),
    (4.9, (1.4, -9.9)),
    (5.3, (0.75, -10.15)),
    (5.7, (0.55, -10.2)),
    (6.0, (0.5, -10.2)),
]


def hermite(keys, t):
    """Catmull-Rom through time-stamped 2D keys (C1, non-uniform)."""
    ts = [k[0] for k in keys]
    ps = [Vector(k[1]) for k in keys]
    if t <= ts[0]:
        v = (ps[1] - ps[0]) / (ts[1] - ts[0])
        return ps[0] + v * (t - ts[0])
    if t >= ts[-1]:
        return ps[-1].copy()
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)

    def tan(j):
        a, b = max(0, j - 1), min(len(ts) - 1, j + 1)
        return (ps[b] - ps[a]) / (ts[b] - ts[a])
    h = ts[i + 1] - ts[i]
    u = (t - ts[i]) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return ps[i] * h00 + tan(i) * h * h10 + ps[i + 1] * h01 + tan(i + 1) * h * h11


# the dodge: as the Skimmer fires, the Glider flicks up the crater wall (outward) and checks
# back, then eases back down onto its line
T_DODGE = 2.83


def dodge(t):
    k = ss((t - T_DODGE) / 0.26) * (1.0 - 0.55 * ss((t - 3.35) / 0.7))
    p = hermite(RUN, T_DODGE + 0.12)
    out = Vector((p.x - CX, p.y - CY)).normalized()
    v = (hermite(RUN, T_DODGE + 0.17) - hermite(RUN, T_DODGE + 0.07)).normalized()
    return out * 2.3 * k - v * 1.2 * k


def base_xy(t):
    return hermite(RUN, t)


def glider_xy(t):
    return base_xy(t) + dodge(t)


# nose: follows the (smoothed) travel direction, locks on the Skimmer for each burst,
# swings round to face the camera as it drift-stops
BURSTS = [(1.95, 2.2), (4.05, T_KILL_SHOT)]
AIM_WIN = [(1.45, 1.8, 2.35, 2.65), (3.55, 3.9, 4.4, 4.75)]
END_HEAD = 218.0


def vel_heading(t):
    acc = Vector((0.0, 0.0))
    for k in range(-4, 5):
        tt = t + k * 0.04
        d = glider_xy(tt + 0.02) - glider_xy(tt - 0.02)
        acc += d * math.exp(-(k / 3.0) ** 2)
    if t > 5.0 or acc.length < 1e-4:
        acc = base_xy(min(t, 5.0) + 0.02) - base_xy(min(t, 5.0) - 0.02)
    return math.degrees(math.atan2(acc.y, acc.x))


def aim_w(t):
    w = 0.0
    for a, b, c, d in AIM_WIN:
        if a <= t <= d:
            w = max(w, ss((t - a) / (b - a)) * (1 - ss((t - c) / (d - c))))
    return w


heads = []
prev = None
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    hv = vel_heading(t)
    p = glider_xy(t)
    s = sk_pos(t)
    ht = math.degrees(math.atan2(s.y - p.y, s.x - p.x))
    h = hv + wrap(ht - hv) * aim_w(t)
    we = ss((t - 4.85) / 0.85)
    h = h + wrap(END_HEAD - h) * we
    if prev is not None:
        h = prev + wrap(h - prev)
    heads.append(h)
    prev = h

# height: ride HOV over the ground (sampled under the hull and ahead along the travel), float
# off the crater lip under gravity
HOV = 0.78
zs = []
zc = None
vz = 0.0
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    p = glider_xy(t)
    d = glider_xy(t + 0.05) - glider_xy(t - 0.05)
    d = d.normalized() if d.length > 1e-4 else Vector((1, 0))
    h = math.radians(heads[f - 1])
    hx, hy = math.cos(h), math.sin(h)
    under = [gz(p.x + d.x * k, p.y + d.y * k) for k in (-1.2, 0.0, 1.2, 2.4)]
    ring = [gz(p.x + 2.3 * math.cos(h + a), p.y + 2.3 * math.sin(h + a)) for a in (0, 1.57, 3.14, -1.57)]
    tgt = max(max(under) + HOV, max(ring) - 0.25)
    if zc is None:
        zc = tgt
    elif tgt >= zc:
        vz = (tgt - zc) * FPS
        zc = tgt
    else:
        vz -= 14.0 / FPS
        zc = max(tgt, zc + vz / FPS)
        if zc == tgt:
            vz = 0.0
    zs.append(zc)
# light smoothing (never below the clearance)
zsm = []
for i in range(len(zs)):
    win = [zs[j] for j in range(max(0, i - 2), min(len(zs), i + 3))]
    zsm.append(max(zs[i] - 0.02, sum(win) / len(win)))

glider = P.load('glider', at=(RUN[0][1][0], RUN[0][1][1]), heading=heads[0], label='glider')
keys = []
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    p = glider_xy(t)
    keys.append((t, (p.x, p.y, zsm[f - 1]), heads[f - 1]))
glider.path(keys, interp='LINEAR')
# nose follows the climb / descent (speed floored so a slow drift never tips it up)
rc = glider.root
sc = bpy.context.scene
for f in range(1, NF + 2):
    a_, b_ = max(1, f - 2), min(NF + 1, f + 2)
    dz = (zsm[b_ - 1] - zsm[a_ - 1]) * FPS / (b_ - a_)
    t = (f - 1) / FPS
    spd = (glider_xy(t + 0.04) - glider_xy(t - 0.04)).length / 0.08
    pit = -math.degrees(math.atan2(dz, max(spd, 8.0))) * 0.8
    sc.frame_set(f)
    rc.rotation_euler.y = math.radians(max(-12.0, min(12.0, pit)))
    rc.keyframe_insert('rotation_euler', index=1, frame=f)
sc.frame_set(1)
K.set_interp(rc, 'LINEAR')
glider.hover_bob(0.04, 1.1)


def gp(t):
    return glider.pos_at(t)


# --------------------------------------------------------------------------- twin guns
# The nose carries two short guns (hull mesh, x > 2.85 m raw): cut each into its own barrel so
# they can collapse back alternately (left, right) on the 2-shot burst.
hull = glider.parts['Hull']
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
barrels = {}
muzzles = {}
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
    mz = K.empty(f'glider_Muzzle{"L" if sgn > 0 else "R"}')
    mz.parent = bo
    mz.location = (3.74, 0.55 * sgn, 0.92)
    barrels[sgn] = bo
    muzzles[sgn] = mz
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in all_idx], context='FACES')
bm.to_mesh(me)
bm.free()
print('GLIDER gun faces', len(sides[1]), len(sides[-1]), 'len', barrels[1]['barrel_len'])

# emitters in model space (measured on the readability model)
bpy.context.view_layer.update()
_M = glider.model_root.matrix_world.inverted() @ hull.matrix_world
PODS = [_M @ Vector((1.0, 0.0, 0.05)), _M @ Vector((-1.4, 0.1, 0.05))]
TAIL = _M @ Vector((-3.55, 0.0, 0.95))
TIPS = [_M @ Vector((-2.1, 3.0, 1.55)), _M @ Vector((-2.1, -3.0, 1.55))]
print('GLIDER pods', PODS, 'tail', TAIL, 'tips', TIPS)

# --------------------------------------------------------------------------- lightning lifters
# Short, dense crackle tucked under the two belly pods (the Darter/Aegis skirt), plus a short
# tail thruster crackle streaming back.
bolt_mat = emit_mat('GliderLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('GliderLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)


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
    for f in range(1, NF + 2):
        objs = []
        for k in range(n_lift):
            pod = PODS[k % 2]
            p0 = pod + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.18, 0.18), 0.0))
            if k % 3 == 0:
                p1 = p0 + Vector((rnd.uniform(-0.45, 0.45), rnd.uniform(-0.2, 0.2), -rnd.uniform(0.0, 0.08)))
            else:
                side = rnd.choice((-1, 1))
                p1 = p0 + Vector((-rnd.uniform(0.05, 0.2), side * rnd.uniform(0.08, 0.24), -rnd.uniform(0.05, 0.13)))
            pts = jag(p0, p1, 4, 0.05, rnd)
            objs += [polyline('GLift', pts, 0.009, bolt_mat), polyline('GLiftHalo', pts, 0.03, glow_mat)]
        for k in range(n_tail):
            p0 = TAIL + Vector((0, rnd.uniform(-0.12, 0.12), rnd.uniform(-0.08, 0.08)))
            p1 = p0 + Vector((-rnd.uniform(0.45, 0.85), rnd.uniform(-0.2, 0.2), rnd.uniform(-0.15, 0.1)))
            pts = jag(p0, p1, 5, 0.1, rnd)
            objs += [polyline('GThrust', pts, 0.014, bolt_mat), polyline('GThrustHalo', pts, 0.045, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            o.visible_shadow = False
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('GliderLiftLight', bpy.data.lights.new('GliderLiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.25)
    L.data.color = GOLD
    L.data.energy = 110
    L.data.shadow_soft_size = 0.8


crackle(glider)
P.dust(glider, 0.0, 0.75, every=0.07, size=0.5)
P.dust(glider, 1.0, 5.5, every=0.08, size=0.45)


# --------------------------------------------------------------------------- the fight
def flinch(a, t, amt=3.0, axis=0):
    """A hit: the hull rocks."""
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


def hull_point(t, off):
    """A point on the Skimmer's hull facing the Glider (off: sideways jitter)."""
    s = sk_pos(t)
    p = gp(t)
    d = Vector((p.x - s.x, p.y - s.y, 0)).normalized()
    side = Vector((-d.y, d.x, 0))
    return s + d * 1.25 + side * off + Vector((0, 0, 0.85))


def gfire(t, sgn, target):
    """One gold bolt from the left (+1) or right (-1) gun: that barrel collapses, gold flash."""
    glider.barrels = [barrels[sgn]]
    glider._muzzles = [muzzles[sgn]]
    glider._last_recoil = -99.0      # the other barrel is at rest: no mid-burst pose for it
    glider.recoil(t, collapse=0.8, kick=3.0, back=0.15)
    P.muzzle_flash(muzzles[sgn], t, GOLD, 0.75)
    p0 = glider.world_at(muzzles[sgn], t - 1.0 / FPS)
    th = P.projectile(p0, target, t, speed=46, color=GOLD, size=0.24)
    return th


# burst 1: two hits on the hull, the Skimmer rocks
for t, sgn, off in ((BURSTS[0][0], 1, 0.35), (BURSTS[0][1], -1, -0.3)):
    tgt = hull_point(t + 0.2, off)
    th = gfire(t, sgn, tgt)
    P.impact(tgt, th, size=0.75, color=GOLD)
    flinch(skimmer, th, 3.2 * sgn)

# burst 2: the first bolt hits, the second kills
t, sgn = BURSTS[1][0], 1
tgt = hull_point(t + 0.2, 0.25)
th = gfire(t, sgn, tgt)
P.impact(tgt, th, size=0.8, color=GOLD)
flinch(skimmer, th, 3.5)
tgt = hull_point(T_KILL_SHOT + 0.2, -0.1)
th_kill = gfire(T_KILL_SHOT, -1, tgt)
P.impact(tgt, th_kill, size=1.0, color=GOLD)
skimmer.destroy(th_kill + 0.02, size=2.0)
P.cam_shake(th_kill + 0.02, 0.12)

# the Skimmer's turret chases the Glider, always a touch behind
t = 0.5
while t < 2.6:
    skimmer.aim(t, gp(t - 0.15) + Vector((0, 0, 0.6)), dur=0.25)
    t += 0.25


# its reply: a 2-round burst led onto the Glider's line; the Glider flicks up the wall and both
# rounds burst on the slope behind where it would have been
def ground_hit(p0, p1):
    d = (p1 - p0).normalized()
    q = Vector(p1)
    for _ in range(400):
        q = q + d * 0.1
        if q.z <= gz(q.x, q.y) + 0.05:
            return q
    return Vector((p1.x, p1.y, gz(p1.x, p1.y) + 0.05))


for tf in (2.9, 3.15):
    b = base_xy(tf + 0.17)
    pred = Vector((b.x, b.y, gz(b.x, b.y) + 0.6))
    skimmer.aim(tf, pred, dur=0.3 if tf < 3.0 else 0.2)
    mz0 = skimmer.world_at(skimmer.muzzle(), tf)
    hit = ground_hit(mz0, pred)
    print('SKIMMER reply', tf, tuple(round(c, 2) for c in hit), 'pred', tuple(round(c, 2) for c in pred))
    skimmer.fire(tf, hit, kind='cannon', impact_size=0.75)
t = 3.45
while t < th_kill:
    skimmer.aim(t, gp(t - 0.1) + Vector((0, 0, 0.6)), dur=0.3)
    t += 0.3

# --------------------------------------------------------------------------- camera
C1, C2 = 30 / FPS, 84 / FPS     # cuts at 1.25 s and 3.5 s


def track(t):
    """Shot 2: up the crater wall outside the Glider's circle, a little behind it."""
    b = base_xy(t)
    out = Vector((b.x - CX, b.y - CY)).normalized()
    v = (base_xy(t + 0.05) - base_xy(t - 0.05)).normalized()
    c = b + out * 8.4 - v * 6.5
    cz = max(gz(c.x, c.y) + 1.8, gp(t).z + 3.0)
    s = sk_pos(min(t, 4.3))
    p = gp(t)
    look = p.lerp(s, 0.5)
    look.z = (p.z + s.z) / 2 + 0.6
    return (c.x, c.y, cz), tuple(look)


CAM3 = Vector((-8.0, -12.5, 0.0))
CAM3.z = gz(CAM3.x, CAM3.y) + 0.9
WRECK = Vector((SK1[0], SK1[1], gz(*SK1) + 0.5))
END_G = gp(6.0)

keys = [
    # shot 1: low on the outer slope; the Glider rushes at us and leaps the lip over the camera
    (0.0, (-16.5, -11.8, gz(-16.5, -11.8) + 0.8), gp(0.0) + Vector((0, 0, 0.7)), 34),
    (0.45, (-16.2, -11.6, gz(-16.2, -11.6) + 1.1), gp(0.45) + Vector((0, 0, 0.7)), 26),
    (0.8, (-15.6, -11.0, gz(-15.6, -11.0) + 2.0), gp(0.85) + Vector((0, 0, 0.6)), 22),
    (C1 - 1 / FPS, (-14.8, -10.2, gz(-14.8, -10.2) + 3.0), gp(C1).lerp(sk_pos(C1), 0.3), 30),
]
for t in (C1, 1.65, 2.05, 2.45, 2.85, 3.2, C2 - 1 / FPS):
    c, l = track(t)
    keys.append((t, c, l, 28))
keys += [
    # shot 3: low on the far wall; the Glider sweeps round, kills the Skimmer and drift-stops
    # in front of us, the wreck burning behind it
    (C2, tuple(CAM3), gp(C2).lerp(WRECK, 0.3), 30),
    (4.3, tuple(CAM3 + Vector((0.2, 0.15, -0.05))), gp(4.3).lerp(WRECK, 0.4), 30),
    (5.2, tuple(CAM3 + Vector((0.45, 0.3, -0.15))), gp(5.2).lerp(WRECK, 0.42) + Vector((0, 0, 0.1)), 32),
    (6.0, tuple(CAM3 + Vector((0.6, 0.4, -0.2))), END_G.lerp(WRECK, 0.42) + Vector((0, 0, 0.15)), 34),
]
P.camera(keys, cuts=(C1, C2), shake=0.02)

# --------------------------------------------------------------------------- wingtip light trails
# drawn last, after the motion layer is baked, so the trails start exactly on the lights
import promo_motion  # noqa: E402
promo_motion.bake(P)
trail_core = emit_mat('GliderTrail', (1.0, 0.62, 0.2), 2.2)
trail_glow = emit_mat('GliderTrailGlow', DEEP_GOLD, 0.9, alpha=0.18)
sc = bpy.context.scene
tips_w = {}
for f in range(1, NF + 2):
    sc.frame_set(f)
    mw = glider.model_root.matrix_world
    tips_w[f] = [mw @ tp for tp in TIPS]
sc.frame_set(1)
TRAIL = 7
for f in range(2, NF + 2):
    for side in (0, 1):
        pts = [tips_w[ff][side] for ff in range(f, max(0, f - TRAIL), -1) if ff in tips_w]
        # cap the streak at ~1.6 m so it reads as a light trail, not a beam
        cut, acc = [pts[0]], 0.0
        for q0, q1 in zip(pts, pts[1:]):
            d = (q1 - q0).length
            if acc + d > 1.6:
                cut.append(q0.lerp(q1, (1.6 - acc) / max(d, 1e-4)))
                break
            acc += d
            cut.append(q1)
        pts = cut
        if len(pts) < 2 or acc < 0.35:
            continue
        n = len(pts) - 1
        segs = [(0, 2, 0.03), (1, 3, 0.022), (2, n + 1, 0.013)]
        objs = []
        for a, b, r in segs:
            sp = pts[a:b]
            if len(sp) >= 2:
                objs.append(polyline('GTrail', sp, r, trail_core))
        objs.append(polyline('GTrailGlow', pts[:3], 0.07, trail_glow))
        for o in objs:
            o.visible_shadow = False
            show_between(o, f, f + 1)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.35, dur=6.0)          # lightning lifter skirt
P.sfx(0.35, 'whoosh', gain=0.9)                         # leaps the lip over the camera
P.sfx(2.8, 'whoosh', gain=0.7, rate=1.25)               # the flick up the wall
P.sfx(5.0, 'skid', gain=0.35, rate=1.3)                 # drift-stop on the wall

P.render()
