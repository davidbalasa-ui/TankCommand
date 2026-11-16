"""Halo (Arcadian fighter): high over a dusk desert a lone Falcon cruises. Far above, a Halo
banks over and drops on it, blade ring spinning, gold lightning crackling off its tail. The
Falcon sees it too late, pulls its nose up and fires back: the lasers miss as the Halo jinks.
Head-on: the ring charges (bolts racing round its rim), a first bolt stings the Falcon's wing,
then a big three-pronged lash wraps the jet in crawling gold lightning. They pass a few metres
apart; the Halo whips over the lens, barrel-rolls away and climbs into a banking turn while the
camera circles it, and far below the dead Falcon corkscrews down on a smoke trail into the
desert floor.

Timeline (s): 0-1.5 hero intro: close on the Halo as it banks over into the dive |
1.5-3.0 over the Falcon's shoulder: the Halo grows out of the sky, Falcon bursts 2.0/2.3 miss,
rim charge 2.2, sting 2.45, lash 2.75 | 3.0 the pass | 3.0-6.0 orbit round the Halo: barrel
roll 3.1-3.8, climbing turn, Falcon spirals down behind, crash ~5.3, end on the Halo banking
over the smoke trail and the fire on the ground."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_halo', seconds=6.0, seed=23)
FPS = P.fps
NF = P.nf
R = P.rnd
P.env('dusk', sun=(74, 0, 125), sun_energy=4.0, props=60, radius=230)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- materials
GOLD = (1.0, 0.5, 0.06)
M_BOLT = K.emit_mat('HaloBolt', GOLD, 3.0)
M_CORE = K.emit_mat('HaloBoltCore', (1.0, 0.7, 0.28), 3.5)
M_GLOW = K.emit_mat('HaloBoltGlow', (1.0, 0.45, 0.04), 1.5, alpha=0.3)
M_SPARK = K.emit_mat('GoldSpark', (1.0, 0.62, 0.2), 3.0)
M_ENG = K.emit_mat('FalconEngine', COL['terran_neon'], 2.2)
M_ENG_HOT = K.emit_mat('FalconEngineHot', (0.3, 0.7, 1.0), 2.2)
M_ENG_GLOW = K.emit_mat('FalconEngineGlow', COL['terran_neon'], 1.2, alpha=0.15)
M_LASER = K.emit_mat('FalconLaser', COL['laser_blue'], 3.5)
M_LASER_CORE = K.emit_mat('FalconLaserCore', (0.7, 0.9, 1.0), 3.0)
M_LASER_GLOW = K.emit_mat('FalconLaserGlow', COL['laser_blue'], 1.6, alpha=0.3)
M_FLAME = K.emit_mat('FalconFlame', (1.0, 0.22, 0.02), 1.8)
M_VAPOR = K.emit_mat('Vapor', (1.0, 0.85, 0.7), 0.7, alpha=0.1)


# ------------------------------------------------------------------------------- flight helpers
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, upf, roll_extra=None):
    """Key root location + quaternion every frame. Nose along velocity, back toward upf()."""
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    dt = 1.0 / FPS
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        m3 = frame_from(v, upf(t, p, v, a))
        if roll_extra:
            m3 = m3 @ Matrix.Rotation(roll_extra(t), 3, 'X')
        q = m3.to_quaternion()
        if prev_q is not None:
            q.make_compatible(prev_q)
        prev_q = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.Translation(p) @ m3.to_4x4()
    K.set_interp(r, 'LINEAR')
    actor.mats = mats
    return mats


def W(actor, t, local):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


def bank_up(k=2.2, clamp=None):
    """Coordinated-turn bank: back points along (lift) = g + k * lateral acceleration."""
    def up(t, p, v, a):
        vn = v.normalized()
        lat = a - vn * a.dot(vn)
        u = (Vector((0, 0, 9.8)) + lat * k).normalized()
        if clamp is not None:
            ang = math.degrees(math.acos(max(-1, min(1, u.z))))
            if ang > clamp:
                h = Vector((u.x, u.y, 0)).normalized()
                c = math.radians(clamp)
                u = h * math.sin(c) + Vector((0, 0, math.cos(c)))
        return u
    return up


def hermite(keys):
    """Cubic Hermite spline through (t, pos, vel) keys; linear extrapolation outside."""
    ks = [(t, Vector(p), Vector(v)) for t, p, v in keys]

    def f(t):
        if t <= ks[0][0]:
            return ks[0][1] + ks[0][2] * (t - ks[0][0])
        if t >= ks[-1][0]:
            return ks[-1][1] + ks[-1][2] * (t - ks[-1][0])
        for (t0, p0, v0), (t1, p1, v1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                h = t1 - t0
                u = (t - t0) / h
                h00 = 2 * u ** 3 - 3 * u ** 2 + 1
                h10 = u ** 3 - 2 * u ** 2 + u
                h01 = -2 * u ** 3 + 3 * u ** 2
                h11 = u ** 3 - u ** 2
                return p0 * h00 + v0 * (h10 * h) + p1 * h01 + v1 * (h11 * h)
    return f


# ------------------------------------------------------------------------------- paths
T_FIRE1 = 2.0       # Falcon bursts (miss)
T_FIRE2 = 2.3
T_CHARGE = 2.15     # ring charges
T_STING = 2.45      # first bolt
T_LASH = 2.75       # kill lash
T_PASS = 3.0
T_ROLL0, T_ROLL1 = 3.08, 3.8

halo_pos = hermite([
    (0.0, (96, 10, 64), (-22, -1, 0)),
    (0.9, (75, 8, 61.5), (-26, -2, -7)),
    (1.9, (44, 4.5, 50), (-34, -3, -14)),
    (2.45, (25, 4.0, 44.5), (-36, -2, -8)),     # jink sideways around the lasers
    (T_PASS, (4, 1.0, 41.8), (-38, -4, -2)),
    (3.6, (-17, -4, 44), (-30, -14, 10)),
    (4.4, (-34, -19, 51), (-11, -22, 7)),
    (5.2, (-38, -37, 55), (4, -21, 3)),
    (6.0, (-30, -52, 56.5), (14, -16, 1)),
])
_halo_base = halo_pos


def halo_pos(t):  # noqa: F811 - add the jink away from the laser bursts
    p = _halo_base(t)
    j = 2.2 * math.sin(math.pi * max(0.0, min(1.0, (t - 1.85) / 0.7)))
    return p + Vector((0, j, 0.6 * j))


F_PASS = Vector((2, -1.8, 38.6))
F_V = Vector((24, 0, 3.5))
falcon_base = hermite([
    (0.0, (-70, -2.5, 33), (25, 0, 0)),
    (1.4, (-35, -2.0, 33.4), (25, 0, 0.8)),
    (2.1, (-17.5, -1.8, 35.6), (24.5, 0, 4.5)),
    (T_PASS, tuple(F_PASS), tuple(F_V)),
])
G_FALL = 9.0


def falcon_pos(t):
    if t <= T_PASS:
        return falcon_base(t)
    d = t - T_PASS
    p = F_PASS + F_V * d + Vector((-2.5 * d * d, 1.2 * d * d, -G_FALL * d * d))
    r = 3.0 * ss(d / 1.2)
    w = 5.5 * d + 1.2 * d * d
    return p + Vector((0, r * math.sin(w), r * (1 - math.cos(w)) * 0.8))


# ------------------------------------------------------------------------------- actors
falcon = P.load('falcon', label='falcon')
F_H = falcon.entry['height']
falcon.model_root.location.z = -F_H / 2
halo = P.load('halo', label='halo')
H_H = halo.entry['height']
halo.model_root.location.z = -H_H / 2

ZC = -F_H / 2
GUN_Z = 0.515 + ZC
MUZ = [Vector((2.25, 0.33, GUN_Z)), Vector((2.25, -0.33, GUN_Z))]
ENG = Vector((-2.62, 0.0, 0.52 + ZC))
TIPS = [Vector((0.85, 1.78, 0.42 + ZC)), Vector((0.85, -1.78, 0.42 + ZC))]


def halo_roll(t):
    # wing-over into the dive, then the barrel roll after the pass
    r = 0.6 * ss((t - 0.25) / 0.55) * (1 - ss((t - 1.0) / 0.6))
    r += 2 * math.pi * ss((t - T_ROLL0) / (T_ROLL1 - T_ROLL0))
    return r


def falcon_roll(t):
    if t <= T_PASS:
        return 0.0
    d = t - T_PASS
    return -(3.0 * d + 2.6 * d * d)


fly(halo, halo_pos, bank_up(0.4, clamp=38), roll_extra=halo_roll)
fly(falcon, falcon_pos, bank_up(1.2, clamp=60), roll_extra=falcon_roll)

# crash: first frame the Falcon reaches the ground
T_CRASH = None
CRASH_P = None
for f in range(int(P.T(T_PASS)), NF + 2):
    t = (f - 1) / FPS
    p = falcon_pos(t)
    gz = P.ground_z(p.x, p.y)
    if p.z <= gz + 1.0:
        T_CRASH = t
        CRASH_P = Vector((p.x, p.y, gz))
        break
if CRASH_P is None:
    p = falcon_pos(6.6)
    CRASH_P = Vector((p.x, p.y, P.ground_z(p.x, p.y)))
print('halo', halo_pos(0), halo_pos(T_PASS), halo_pos(6), 'falcon pass', falcon_pos(T_PASS),
      'crash', T_CRASH, CRASH_P)

# blade ring spin (fast)
mr = halo.model_root
mr.rotation_mode = 'XYZ'
for f in range(0, NF + 2, 2):
    mr.rotation_euler.z = math.radians(-480.0 * (f - 1) / FPS)
    mr.keyframe_insert('rotation_euler', index=2, frame=f)
K.set_interp(mr, 'LINEAR')


# ------------------------------------------------------------------------------- falcon guns
def split_guns(actor):
    """Cut the two gun barrels off the hull mesh into their own objects so they can collapse."""
    host = actor.meshes[0]
    bpy.context.view_layer.update()
    mw = Matrix.Translation((0, 0, F_H / 2)) @ actor.root.matrix_world.inverted() @ host.matrix_world
    inv = mw.inverted()
    out = []
    for sgn in (1, -1):
        bm = bmesh.new()
        bm.from_mesh(host.data)
        sel = []
        for fc in bm.faces:
            c = mw @ fc.calc_center_median()
            if c.x > 1.72 and 0.27 < c.y * sgn < 0.4 and 0.44 < c.z < 0.6:
                sel.append(fc)
        keep_idx = {fc.index for fc in sel}
        bm2 = bm.copy()
        bmesh.ops.delete(bm, geom=sel, context='FACES')
        bm.to_mesh(host.data)
        bm.free()
        bm2.faces.ensure_lookup_table()
        drop = [fc for fc in bm2.faces if fc.index not in keep_idx]
        bmesh.ops.delete(bm2, geom=drop, context='FACES')
        me2 = bpy.data.meshes.new('FalconGun')
        bm2.to_mesh(me2)
        bm2.free()
        for m in host.data.materials:
            me2.materials.append(m)
        b = K.link(bpy.data.objects.new(actor.name + '_Gun', me2))
        b.parent = host
        xs = [(mw @ v.co).x for v in me2.vertices]
        b['len_local'] = max(xs) - min(xs) if xs else 0.3
        b['ax'] = list(inv.to_3x3() @ Vector((-1, 0, 0)))
        out.append(b)
    actor.guns = out
    return out


split_guns(falcon)


def recoil(actor, t, kick=2.5):
    f = P.T(t)
    for b in actor.guns:
        ax = Vector(b['ax'])
        L = b['len_local'] * 0.8
        b.location = (0, 0, 0)
        b.keyframe_insert('location', frame=f - 1)
        b.location = ax * L
        b.keyframe_insert('location', frame=f + 1)
        b.location = (0, 0, 0)
        b.keyframe_insert('location', frame=f + 6)
    m = actor.model_root
    m.rotation_mode = 'XYZ'
    m.rotation_euler.y = 0
    m.keyframe_insert('rotation_euler', index=1, frame=f - 1)
    m.rotation_euler.y = -math.radians(kick)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 1)
    m.rotation_euler.y = 0
    m.keyframe_insert('rotation_euler', index=1, frame=f + 6)


# ------------------------------------------------------------------------------- falcon engine
def engine(actor):
    """Blue jet plume; sputters and dies after the lash."""
    core = K.sphere('EngCore', 1.0, M_ENG_HOT, seg=(10, 6))
    core.parent = actor.root
    core.location = ENG + Vector((-0.2, 0, 0))
    glow = K.sphere('EngGlow', 1.0, M_ENG_GLOW, seg=(12, 8))
    glow.parent = actor.root
    plume = K.sphere('EngPlume', 1.0, M_ENG, seg=(10, 6))
    plume.parent = actor.root
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        live = 1.0 - ss((t - T_LASH - 0.1) / 0.35)
        if T_LASH < t < T_LASH + 0.45 and f % 3 == 0:
            live *= 0.2          # sputter
        boost = 1.0 + 0.4 * ss((t - 1.5) / 0.4)
        fl = R.uniform(0.85, 1.15) * boost * max(live, 0.01)
        cs = 0.3 * max(live, 0.02)
        core.scale = (cs, cs * 0.85, cs * 0.85)
        plume.location = ENG + Vector((-0.75 * fl, 0, 0))
        plume.scale = (0.75 * fl, 0.12 * max(live, 0.05), 0.12 * max(live, 0.05))
        glow.location = ENG + Vector((-0.6 * fl, 0, 0))
        glow.scale = (1.2 * fl, 0.42 * max(live, 0.05), 0.42 * max(live, 0.05))
        for o in (plume, glow, core):
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('scale', frame=f)
    K.show_between(plume, 0, int(P.T(T_LASH + 0.5)))
    K.show_between(glow, 0, int(P.T(T_LASH + 0.5)))
    K.show_between(core, 0, int(P.T(T_LASH + 0.5)))


engine(falcon)


# ------------------------------------------------------------------------------- lightning
def jag_pts(p0, p1, segs, jag, ctrl=None):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        if ctrl is not None:
            base = p0 * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + p1 * u * u
        else:
            base = p0 + d * u
        env = math.sin(math.pi * u)
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * env if 0 < i < segs else Vector()
        pts.append(base + off)
    return pts


def bolt_frame(pts, f, width, parent=None, glow=True, forks=1, core=True):
    objs = [K.polyline('Bolt', pts, width, M_BOLT)]
    if core:
        objs.append(K.polyline('BoltCore', pts, width * 0.4, M_CORE))
    if glow:
        objs.append(K.polyline('BoltGlow', pts, width * 3.0, M_GLOW))
    n = len(pts) - 1
    for _ in range(forks):
        if n < 4:
            break
        k = R.randint(2, n - 2)
        a = pts[k]
        dv = (pts[k + 1] - pts[k - 1])
        side = dv.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        bl = dv.length * R.uniform(0.8, 1.6)
        dirb = (dv.normalized() + side * R.uniform(-1.2, 1.2) + Vector((0, 0, R.uniform(-.6, .6)))).normalized()
        objs.append(K.polyline('BoltFork', [a, a + dirb * bl * 0.5, a + dirb * bl], width * 0.55, M_BOLT))
    for o in objs:
        if parent is not None:
            o.parent = parent
        K.show_between(o, f, f + 1)
    return objs


RING_R = 2.55     # blade ring outer radius (local)


def ring_pt(ang, z=0.0, r=RING_R):
    return Vector((r * math.cos(ang), r * math.sin(ang), z))


def halo_thrust():
    """Gold lightning thrust crackling off the trailing rim; flares in the dive and the climb."""
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        power = 0.75 + 0.5 * ss((t - 1.0) / 0.5) * (1 - ss((t - 2.2) / 0.3)) + 0.5 * ss((t - 3.0) / 0.3)
        nb = 3 if power < 1.1 else 4
        for k in range(nb):
            if R.random() < 0.15:
                continue
            ang = math.pi + R.uniform(-0.75, 0.75)
            a = ring_pt(ang, R.uniform(-0.1, 0.15), RING_R * 0.92)
            b = a + Vector((-R.uniform(1.1, 2.0) * power, math.sin(ang) * R.uniform(0.1, 0.5),
                            R.uniform(-0.3, 0.2)))
            bolt_frame(jag_pts(a, b, 6, 0.4), f, 0.026 + 0.008 * (power - 0.7), parent=halo.root,
                       core=False, forks=1 if R.random() < 0.5 else 0)


halo_thrust()


def rim_charge(t0, t1, width=0.03):
    """Bolts racing round the rim of the ring before a shot."""
    for f in range(int(P.T(t0)), int(P.T(t1)) + 1):
        u = (f - P.T(t0)) / max(1, P.T(t1) - P.T(t0))
        for k in range(2 + int(2 * u)):
            a0 = R.uniform(0, 2 * math.pi)
            span = R.uniform(0.6, 1.4)
            pts = [ring_pt(a0 + span * i / 6, 0.2 + R.uniform(-0.12, 0.12), RING_R + R.uniform(0.0, 0.25))
                   for i in range(7)]
            bolt_frame(pts, f, width, parent=halo.root, glow=True, core=False, forks=0)
    P.light(W(halo, t0, (0, 0, 0)), t0, COL['arc_gold'], energy=2500, dur=t1 - t0, radius=1.5)


def gold_sparks(pos, t, size, vel=Vector()):
    f0 = P.T(t)
    o = K.ico('GoldHit', 1.0, M_BOLT, sub=2)
    o.location = pos
    o.visible_shadow = False
    for df_, s in ((0, 0.05), (1, 0.45 * size), (3, 0.01)):
        o.scale = (s, s, s)
        o.location = pos + vel * (df_ / FPS)
        o.keyframe_insert('scale', frame=f0 + df_)
        o.keyframe_insert('location', frame=f0 + df_)
    K.show_between(o, f0, f0 + 4)
    for _ in range(10):
        sp = K.sphere('Spk', 1.0, M_SPARK, seg=(6, 4))
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.6, 1))).normalized() * size * R.uniform(2.5, 4.5)
        sp.scale = (0.2 * size, 0.035 * size, 0.035 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = (v + vel * 0.3).to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + vel * 0.3 + Vector((0, 0, -0.3))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)
    P.light(pos, t, COL['arc_gold'], energy=2500 * size, dur=0.15, radius=0.5)


def strike(t, dur, local_hits, width=0.04, origin_ang=(0.0,)):
    """Bolts leaving the leading rim and landing on Falcon points (Falcon root space)."""
    f0 = int(round(P.T(t)))
    f1 = int(round(P.T(t + dur)))
    for f in range(f0, f1 + 1):
        tt = (f - 1) / FPS
        for k, lh in enumerate(local_hits):
            ang = origin_ang[k % len(origin_ang)]
            p0 = W(halo, tt, ring_pt(ang, 0.15, RING_R + 0.1))
            p1 = W(falcon, tt, lh)
            fwd = (W(halo, tt, (1, 0, 0)) - W(halo, tt, (0, 0, 0))).normalized()
            ctrl = (p0 + p1) / 2 + fwd * 1.5 + Vector((0, 0, 1.0))
            n = max(10, int((p1 - p0).length / 0.9))
            bolt_frame(jag_pts(p0, p1, n, 0.07, ctrl=ctrl), f, width, forks=2)
    for lh in local_hits:
        vel = (falcon_pos(t + 0.05) - falcon_pos(t - 0.05)) / 0.1
        gold_sparks(W(falcon, t, lh), t, 0.8, vel=vel)
    P.light(W(halo, t, (2.5, 0, 0)), t, COL['arc_gold'], energy=4000, dur=dur, radius=0.8)


def crawl(t0, t1):
    """Electrocution: short gold arcs crawl over the Falcon's hull and wings."""
    pts_local = [Vector((1.6, 0, 0.4 + ZC)), Vector((-2.2, 0, 0.5 + ZC)), TIPS[0], TIPS[1],
                 Vector((-1.6, 1.1, 0.4 + ZC)), Vector((-1.6, -1.1, 0.4 + ZC)), Vector((0.2, 0, 0.75 + ZC))]
    for f in range(int(P.T(t0)), int(P.T(t1)) + 1):
        u = (f - P.T(t0)) / max(1, P.T(t1) - P.T(t0))
        for k in range(3 if u < 0.6 else 1):
            if u > 0.6 and R.random() < 0.5:
                continue
            a, b = R.sample(pts_local, 2)
            pts = jag_pts(a, b, 6, 0.5)
            bolt_frame(pts, f, 0.028, parent=falcon.root, glow=True, core=False, forks=1)


rim_charge(T_CHARGE, T_STING)
strike(T_STING, 0.12, [TIPS[0]], width=0.035, origin_ang=(0.25,))
rim_charge(T_STING + 0.12, T_LASH, width=0.035)
strike(T_LASH, 0.22, [Vector((0.6, 0, 0.6 + ZC)), TIPS[1], Vector((-2.0, 0, 0.5 + ZC))],
       width=0.05, origin_ang=(0.0, -0.45, 0.45))
crawl(T_LASH + 0.05, T_PASS + 0.55)


# ------------------------------------------------------------------------------- falcon fires back
def laser_bolt(p0, p1, t0, speed=170.0, length=3.6):
    d = p1 - p0
    dur = max(1.0 / FPS, d.length / speed)
    root = K.empty('Laser')
    root.rotation_mode = 'QUATERNION'
    root.rotation_quaternion = d.to_track_quat('X', 'Z')
    c = K.sphere('LaserCore', 1.0, M_LASER_CORE, seg=(8, 6))
    c.parent = root
    c.scale = (length * 0.5, 0.035, 0.035)
    b = K.sphere('LaserBody', 1.0, M_LASER, seg=(8, 6))
    b.parent = root
    b.scale = (length * 0.52, 0.065, 0.065)
    gl = K.sphere('LaserGlow', 1.0, M_LASER_GLOW, seg=(10, 6))
    gl.parent = root
    gl.scale = (length * 0.58, 0.15, 0.15)
    root.location = p0 + d.normalized() * length * 0.5
    root.keyframe_insert('location', frame=P.T(t0))
    root.location = p1 - d.normalized() * length * 0.3
    root.keyframe_insert('location', frame=P.T(t0 + dur))
    K.set_interp(root, 'LINEAR')
    K.show_between(root, P.T(t0), P.T(t0 + dur) + 1)
    return t0 + dur


def muzzle_flash(actor, t, k):
    o = K.sphere('Flash', 1.0, P.soft_fire_mat(), seg=(10, 8))
    o.color = (*COL['laser_blue'], 1.0)
    o.parent = actor.root
    o.location = MUZ[k] + Vector((0.3, 0, 0))
    f0 = P.T(t)
    for df_, s in ((-1, (0.01, 0.01, 0.01)), (0, (0.7, 0.3, 0.3)), (1, (0.45, 0.2, 0.2)), (3, (0.01, 0.01, 0.01))):
        o.scale = s
        o.keyframe_insert('scale', frame=f0 + df_)
    K.show_between(o, f0 - 1, f0 + 3)


def burst(t0, miss, n=3, gap=0.08):
    for s in range(n):
        t = t0 + s * gap
        recoil(falcon, t)
        for k in range(2):
            muzzle_flash(falcon, t, k)
            p0 = W(falcon, t, MUZ[k])
            aim = halo_pos(t + 0.12) + miss + Vector((0, (k - 0.5) * 0.9, s * 0.4))
            p1 = p0 + (aim - p0).normalized() * 70.0
            laser_bolt(p0, p1, t)
        P.light(W(falcon, t, Vector((2.4, 0, GUN_Z))), t, COL['laser_blue'], energy=1500, dur=0.08)


burst(T_FIRE1, Vector((0, -3.5, 1.5)))
burst(T_FIRE2, Vector((0, 3.0, -2.8)))


# ------------------------------------------------------------------------------- falcon death
def falcon_damage():
    fl = K.ico('FalconFire', 1.0, M_FLAME, sub=2)
    fl.parent = falcon.root
    fl.location = ENG + Vector((0.2, 0, 0.1))
    fl.visible_shadow = False
    t_end = T_CRASH if T_CRASH else 6.1
    for f in range(int(P.T(T_LASH + 0.1)), int(P.T(t_end)) + 2):
        s = R.uniform(0.22, 0.34) * min(1.0, (f - P.T(T_LASH)) / 4 + 0.3)
        fl.scale = (s * 1.9, s, s)
        fl.keyframe_insert('scale', frame=f)
    K.show_between(fl, P.T(T_LASH + 0.1), P.T(t_end) + 1)
    t = T_LASH + 0.12
    while t < t_end:
        sz = 0.9 + 1.0 * ss((t - T_PASS) / 1.0)
        P.puff(W(falcon, t, ENG), t, size=sz, n=1, rise=0.6, life=3.0,
               color=(0.24, 0.22, 0.21), opacity=0.55)
        t += 0.04


falcon_damage()
if T_CRASH:
    falcon.vanish(T_CRASH + 1 / FPS)
    _before = set(bpy.data.objects)
    P.explosion(CRASH_P, T_CRASH, size=4.0, debris=14)
    P.fire_patch(CRASH_P + Vector((0, 0, 0.3)), T_CRASH + 0.2, 6.2, size=1.4)
    P.smoke_column(CRASH_P, T_CRASH + 0.25, 6.2, size=2.0, every=0.2)


# ------------------------------------------------------------------------------- halo vapour
def vapor(actor, pts_local, t0, t1):
    hist = {f: [actor.mats[f] @ tp for tp in pts_local] for f in range(0, NF + 2)}
    for f in range(max(4, int(P.T(t0))), min(NF + 2, int(P.T(t1)))):
        for k in range(len(pts_local)):
            pts = [hist[max(0, f - j)][k] for j in range(4)]
            o = K.polyline('Vapor', pts, 0.035, M_VAPOR)
            o.visible_shadow = False
            K.show_between(o, f, f + 1)


vapor(halo, [ring_pt(math.pi / 2, 0.1), ring_pt(-math.pi / 2, 0.1)], T_ROLL0, T_ROLL1 + 0.2)


# ------------------------------------------------------------------------------- camera
T_C1 = 1.5
T_C2 = T_PASS
keys = []

# shot A: hero intro, the camera floats just ahead of / beside the Halo and drifts above it
# as it banks over into the dive; the Falcon is a speck far below at the end
for t in [0.0, 0.4, 0.8, 1.15, T_C1 - 1 / FPS]:
    h = halo_pos(t)
    u = ss(t / T_C1)
    off = Vector((lerp(-13.0, -10.0, u), lerp(-8.0, 7.0, u), lerp(-1.5, 6.5, u)))
    look = h + Vector((lerp(0.0, -4.0, u), 0, lerp(0.3, -2.5, u)))
    keys.append((t, tuple(h + off), look, 35))


# shot B: over the Falcon's shoulder, looking up the Halo's dive
def shoulder(t):
    fp = falcon_pos(t)
    hp = halo_pos(t)
    d = (hp - fp)
    dh = Vector((d.x, d.y, 0)).normalized()
    side = Vector((-dh.y, dh.x, 0))
    cpos = fp - dh * 11.5 - side * 3.5 + Vector((0, 0, 2.6))
    w = 0.45 + 0.15 * ss((t - 2.2) / 0.6)
    tgt = hp * w + fp * (1 - w)
    return cpos, tgt


t = T_C1
while t < T_C2 - 0.05:
    c, g = shoulder(t)
    keys.append((t, tuple(c), g, 30))
    t += 0.25
c, g = shoulder(T_C2 - 1 / FPS)
keys.append((T_C2 - 1 / FPS, tuple(c), g, 30))

# shot C: orbit around the Halo as it rolls away and climbs; end looking past it down at the
# Falcon's smoke trail and the crash fire
end_h = halo_pos(6.0)
away = Vector((end_h.x - CRASH_P.x, end_h.y - CRASH_P.y, 0)).normalized()
th1 = math.atan2(away.y, away.x)
th0 = th1 - math.radians(210)
for i in range(13):
    u = i / 12
    t = T_C2 + (6.0 - T_C2) * u
    h = halo_pos(t)
    th = lerp(th0, th1, ss(u) * 0.35 + u * 0.65)
    rad = lerp(13.0, 15.0, u)
    z = lerp(-2.0, 5.5, ss(u))
    cpos = h + Vector((rad * math.cos(th), rad * math.sin(th), z))
    look = h + (CRASH_P - h).normalized() * 9.0 * ss((u - 0.4) / 0.6)
    keys.append((t, tuple(cpos), look, lerp(30, 32, u)))

P.camera(keys, shake=0.03, cuts=(T_C1, T_C2))
for tt in (T_FIRE1, T_FIRE2):
    P.cam_shake(tt, 0.05, dur=0.12)
P.cam_shake(T_STING, 0.08, dur=0.2)
P.cam_shake(T_LASH, 0.18, dur=0.3)
P.cam_shake(T_PASS, 0.15, dur=0.35)

# effects never cast shadows
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.active_material is not None:
        m = o.active_material
        if 'emit_node' in m or m.name.startswith(('SoftFire', 'Fireball')):
            o.visible_shadow = False

P.render()
