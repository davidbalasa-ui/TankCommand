"""Dragonfly (Arcadian interceptor, anti-air only): a swarm of five Dragonflies rockets up off
the deck at a Terran Condor bomber, corkscrews round it while its gunners hose tracers at them,
and stings it with scorpion-tail lightning (each sting charges in the tail first) until a final
three-way strike breaks the bomber in half. The lead Dragonfly peels off and hangs in front of
the camera, wings a blur, as the burning halves fall away behind it.

Timeline (s): 0-1.5 climb from the deck (camera on the ground looking up) | 1.5-4.5 corkscrew
and stings (camera in the air alongside) | 4.55 triple sting | 4.75 bomber breaks apart |
4.8-6 hero hover, wreck falling behind."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_dragonfly', seconds=6.0, seed=7)
FPS = P.fps
NF = P.nf
P.env('dusk', sun=(14, 0, 150), props=45, clear=[(0, -10, 18)])
R = P.rnd

T_BREAK = 4.75
ALT = 40.0
CV = Vector((7.0, 0, 0))          # bomber velocity


def C(t):
    """Condor centre (straight and level, 7 m/s)."""
    return Vector((-16.0, 0.0, ALT)) + CV * t


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- materials
M_BOLT = K.emit_mat('DfBolt', (1.0, 0.5, 0.04), 5)
M_CORE = K.emit_mat('DfBoltCore', (1.0, 0.8, 0.4), 8)
M_GLOW = K.emit_mat('DfBoltGlow', (1.0, 0.45, 0.04), 2.0, alpha=0.3)
M_BLUR = K.emit_mat('DfWingBlur', (1.0, 0.86, 0.55), 0.8, alpha=0.035)
M_FLAME = K.emit_mat('CondorFlame', (1.0, 0.12, 0.01), 1.4)
M_TRACER = K.emit_mat('CondorTracer', COL['tracer'], 30)


def jag_pts(p0, p1, segs, jag, ctrl=None):
    """Jagged points from p0 to p1 (optionally bowed through a quadratic control point)."""
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
    # gold bolt with a thin white-hot core inside a soft gold glow
    objs = [K.polyline('Bolt', pts, width, M_BOLT)]
    if core:
        objs.append(K.polyline('BoltCore', pts, width * 0.4, M_CORE))
    if glow:
        objs.append(K.polyline('BoltGlow', pts, width * 3.2, M_GLOW))
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
        objs.append(K.polyline('BoltFork', [a, a + dirb * bl * 0.5 + side * R.uniform(-.2, .2), a + dirb * bl], width * 0.55, M_BOLT))
    for o in objs:
        if parent is not None:
            o.parent = parent
        K.show_between(o, f, f + 1)
    return objs


# ------------------------------------------------------------------------------- flight helper
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, upf, t0=0.0, t1=6.0, roll_extra=None):
    """Key root location + quaternion every frame from an analytic position function.
    Orientation: nose along velocity, back toward upf(t, pos, vel). Stores per-frame world
    matrices on the actor for later local->world lookups."""
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    f0 = int(round(P.T(t0)))
    f1 = int(round(P.T(t1)))
    dt = 1.0 / FPS
    for f in range(f0, f1 + 1):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
        if v.length < 0.3:
            v = getattr(actor, '_last_v', Vector((1, 0, 0)))
        actor._last_v = v
        up = upf(t, p, v)
        m3 = frame_from(v, up)
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
    f = max(1, min(NF, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


# ------------------------------------------------------------------------------- the bomber
condor = P.load('condor', size=11.0, label='condor')
condor.model_root.location.z = -condor.entry['height'] / 2   # root at the hull centre
c_len = 11.0
condor_wobble = lambda t: 0.06 * math.sin(t * 1.7) + (0.22 * math.sin((t - 2.0) * 5.0) * ss((t - 2.2) / 1.0) if t > 2.2 else 0)
fly(condor, C, lambda t, p, v: Vector((0, 0, 1)), 0.0, 6.0, roll_extra=condor_wobble)

# ------------------------------------------------------------------------------- the swarm
N = 5
dfs = [P.load('dragonfly', label=f'df{i}') for i in range(N)]
DF_LEN = None

# Tail tip / wing root in root-local space (model faces +X, tail at -X)
bpy.context.view_layer.update()
hull = dfs[0].parts['Hull']
inv = dfs[0].root.matrix_world.inverted()
xs = [(inv @ (hull.matrix_world @ Vector(c))) for c in hull.bound_box]
HX0 = min(v.x for v in xs)
HX1 = max(v.x for v in xs)
HZ0 = min(v.z for v in xs)
HZ1 = max(v.z for v in xs)
ZM = (HZ0 + HZ1) / 2
TAIL = Vector((HX0 + 0.05, 0, ZM + 0.05))
wp = dfs[0].parts['WingLPivot']
WROOT = inv @ wp.matrix_world.translation
print('DF hull x', HX0, HX1, 'z', HZ0, HZ1, 'wingroot', WROOT)

# Launch starts (low, near the ground camera), helix params
starts = [Vector((-7.0, -31.0, 2.6)), Vector((-3.5, -33.0, 3.4)), Vector((-10.5, -34.0, 3.0)),
          Vector((-1.0, -37.0, 4.4)), Vector((-13.0, -38.0, 4.0))]
t_join = [1.55, 1.7, 1.85, 2.0, 2.15]
phi0 = [math.radians(a) for a in (-120, -60, -160, -20, -200)]
omega = [2.3, 2.1, 2.5, 2.0, 2.4]
radius = [7.0, 8.0, 6.5, 8.5, 7.5]
dx0 = [2.0, -3.0, 4.0, -1.0, 0.0]


def helix(i, t):
    phi = phi0[i] + omega[i] * (t - 1.5)
    r = radius[i] + 0.8 * math.sin(t * 1.3 + i)
    dx = dx0[i] + 2.5 * math.sin(0.9 * t + i * 1.7)
    return C(t) + Vector((dx, r * math.cos(phi), 0.85 * r * math.sin(phi)))


def launch(i, t):
    """Fast climb from the deck to the helix entry point."""
    tj = t_join[i]
    s = starts[i]
    e = helix(i, tj)
    u = max(0.0, min(1.0, t / tj))
    ctrl = Vector((lerp(s.x, e.x, 0.3), lerp(s.y, e.y, 0.7), s.z + 2.0))
    k = u ** 1.35
    return s * (1 - k) ** 2 + ctrl * 2 * k * (1 - k) + e * k * k


# exits after the break: scatter outward, the hero comes to a hover in front of the camera
CAM_END = Vector((26.0, -24.0, ALT + 1.5))
HERO_END = Vector((28.2, -15.5, ALT + 1.0))


def exit_pos(i, t):
    h = helix(i, T_BREAK)
    if i == 0:
        u = ss((t - T_BREAK) / 1.05)
        ctrl = h + Vector((5.0, -3.0, -1.5))
        p = h * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + HERO_END * u * u
        return p + Vector((0, 0, 0.15 * math.sin(t * 5.0))) * ss((t - T_BREAK - 0.8) / 0.4)
    d = (h - C(T_BREAK))
    d.x *= 0.4
    d = d.normalized()
    dt = t - T_BREAK
    return h + (d * 15.0 + Vector((10.0, 0, 3.0))) * dt + CV * dt * 0.5


def df_pos(i, t):
    tj = t_join[i]
    if t < tj:
        return launch(i, t)
    p = helix(i, t)
    if t > T_BREAK:
        w = ss((t - T_BREAK) / 0.35)
        p = lerp(p, exit_pos(i, t), w) if i else exit_pos(i, t)
    return p


def df_up(i):
    def up(t, p, v):
        z = Vector((0, 0, 1))
        if t < t_join[i] - 0.4 or t > T_BREAK + 0.6:
            if i == 0 and t > T_BREAK:
                return z
            return z
        a = C(t)
        toward = Vector((0, a.y - p.y, a.z - p.z))
        if toward.length < 1e-3:
            return z
        b = 0.85 * ss((t - (t_join[i] - 0.4)) / 0.4) * (1 - ss((t - T_BREAK) / 0.6))
        return (z * (1 - b) + toward.normalized() * b).normalized()
    return up


def hero_face(t):
    return 0.0


for i, a in enumerate(dfs):
    fly(a, lambda t, i=i: df_pos(i, t), df_up(i), 0.0, 6.0)

# hero: once hovering, turn to show its side to the camera (override orientation)
hero = dfs[0]
r = hero.root
look_dir = (CAM_END - HERO_END)
for f in range(int(P.T(T_BREAK + 0.75)), NF + 1):
    t = (f - 1) / FPS
    u = ss((t - (T_BREAK + 0.75)) / 0.45)
    p = df_pos(0, t)
    v = (df_pos(0, t + 0.02) - df_pos(0, t - 0.02)) / 0.04
    fwd_hover = Vector((look_dir.x * 0.25 + 1.0, look_dir.y * 0.25 - 0.2, 0.0)).normalized()
    fwd_hover = Vector((-0.85, -0.5, 0.05)).normalized()
    fwd = (v.normalized() * (1 - u) + fwd_hover * u) if v.length > 0.3 else fwd_hover
    m3 = frame_from(fwd, Vector((0.08, 0.15, 1)).normalized())
    q = m3.to_quaternion()
    q.make_compatible(r.rotation_quaternion)
    r.rotation_quaternion = q
    r.keyframe_insert('rotation_quaternion', frame=f)
    hero.mats[f] = Matrix.Translation(p) @ m3.to_4x4()
K.set_interp(r, 'LINEAR')


# ------------------------------------------------------------------------------- wings, lifters
def wings(actor, hz=11.0, amp=22.0, phase=0.0):
    for side, sgn in (('L', 1), ('R', -1)):
        pv = actor.parts[f'Wing{side}Pivot']
        wing = actor.parts[f'Wing{side}']
        pv.rotation_mode = 'XYZ'
        base = pv.rotation_euler.copy()
        # blur ghosts: fixed copies at the top and bottom of the stroke
        for k, ang in enumerate((amp * 0.85, -amp * 0.7)):
            g = K.empty(f'{actor.name}_ghost{side}{k}')
            g.parent = pv.parent
            g.matrix_parent_inverse = pv.matrix_parent_inverse.copy()
            g.location = pv.location.copy()
            g.rotation_mode = 'XYZ'
            g.rotation_euler = (base.x + math.radians(ang) * sgn, base.y, base.z)
            c = wing.copy()
            K.link(c)
            c.animation_data_clear()
            c.parent = g
            c.matrix_parent_inverse = wing.matrix_parent_inverse.copy()
            c.location = wing.location.copy()
            c.rotation_mode = wing.rotation_mode
            c.rotation_quaternion = wing.rotation_quaternion.copy()
            c.rotation_euler = wing.rotation_euler.copy()
            c.scale = wing.scale.copy()
            c.data = wing.data.copy()
            c.data.materials.clear()
            c.data.materials.append(M_BLUR)
        for f in range(1, NF + 2):
            t = (f - 1) / FPS
            # alternate up/down strokes frame to frame, with a little jitter
            s = math.sin(2 * math.pi * hz * t + phase) * 0.6 + (0.55 if f % 2 else -0.55)
            pv.rotation_euler = (base.x + math.radians(amp * s * sgn), base.y, base.z)
            pv.keyframe_insert('rotation_euler', index=0, frame=f)
        K.set_interp(pv, 'LINEAR')


def lifters(actor, t0=0.0, t1=6.0, every=1):
    """Gold lightning thrust: crackles trailing from the wing roots and a hot core at the
    thorax. Parented to the actor's root so they ride along."""
    core = K.sphere('DfCore', 1.0, M_BOLT, seg=(10, 6))
    core.parent = actor.root
    core.location = (WROOT.x - 0.3, 0, ZM - 0.15)
    core.scale = (0.2, 0.12, 0.12)
    halo = K.sphere('DfCoreGlow', 1.0, M_GLOW, seg=(10, 6))
    halo.parent = actor.root
    halo.location = core.location
    halo.scale = (0.38, 0.25, 0.25)
    for f in range(int(P.T(t0)), int(P.T(t1)) + 1, every):
        for sgn in (1, -1):
            if R.random() < 0.15:
                continue
            a = Vector((WROOT.x - 0.3, 0.18 * sgn, ZM - 0.1))
            b = a + Vector((-R.uniform(1.4, 2.4), sgn * R.uniform(0.2, 0.7), -R.uniform(0.1, 0.6)))
            pts = jag_pts(a, b, 5, 0.6)
            bolt_frame(pts, f, 0.022, parent=actor.root, glow=True, core=False, forks=1 if R.random() < 0.5 else 0)


for i, a in enumerate(dfs):
    wings(a, hz=10.0 + i * 0.7, phase=i * 1.3)
    lifters(a)

# ------------------------------------------------------------------------------- stings
condor_hits = []


def charge(actor, t0, t1):
    """Tail tip glows up before a sting."""
    o = K.sphere('TailCharge', 1.0, M_BOLT, seg=(10, 6))
    o.parent = actor.root
    o.location = TAIL
    g = K.sphere('TailChargeGlow', 1.0, M_GLOW, seg=(10, 6))
    g.parent = o
    g.scale = (2.4, 2.4, 2.4)
    for t, s in ((t0 - 0.01, 0.01), (t0, 0.05), (t1, 0.32), (t1 + 0.04, 0.42), (t1 + 0.16, 0.01)):
        o.scale = (s, s, s)
        o.keyframe_insert('scale', frame=P.T(t))
    K.show_between(o, int(P.T(t0)) - 1, int(P.T(t1 + 0.17)) + 1)


def sting(actor, t, local_hit, dur=0.2, width=0.035):
    """Scorpion-tail strike: the bolt leaves the tail tip, arcs up over the Dragonfly's back
    and lands on the bomber (local_hit is a point in the bomber's root space)."""
    charge(actor, t - 0.28, t)
    f0 = int(round(P.T(t)))
    f1 = int(round(P.T(t + dur)))
    for f in range(f0, f1 + 1):
        tt = (f - 1) / FPS
        m = actor.mats[f]
        p0 = m @ TAIL
        back = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
        fwd = (m.to_3x3() @ Vector((1, 0, 0))).normalized()
        p1 = W(condor, tt, local_hit)
        ctrl = p0 + back * 3.0 + fwd * 1.0 + (p1 - p0) * 0.25
        pts = jag_pts(p0, p1, 14, 0.22, ctrl=ctrl)
        bolt_frame(pts, f, width, glow=True, forks=2)
    p_hit = W(condor, t, local_hit)
    P.light(p_hit, t, COL['arc_gold'], energy=9000, dur=dur + 0.08, radius=1.0)
    P.light(W(actor, t, TAIL), t, COL['arc_gold'], energy=3000, dur=dur, radius=0.5)
    sparks(p_hit, t, 1.0)
    condor_hits.append((t, local_hit))


M_SPARK = K.emit_mat('StingSpark', (1.0, 0.8, 0.35), 20)


def sparks(pos, t, size):
    """Gold spark burst in the air (no ground puff)."""
    f0 = P.T(t)
    o = K.ico('StingHit', 1.0, M_CORE, sub=2)
    o.location = pos
    for df, s in ((0, 0.05), (1, 0.75 * size), (4, 0.01)):
        o.scale = (s, s, s)
        o.keyframe_insert('scale', frame=f0 + df)
    K.show_between(o, f0, f0 + 5)
    for _ in range(9):
        sp = K.sphere('Spk', 1.0, M_SPARK, seg=(6, 4))
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))).normalized() * size * R.uniform(2.5, 4.5)
        sp.scale = (0.18 * size, 0.035 * size, 0.035 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + CV * 0.3 + Vector((0, 0, -0.3))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)


# bomber root space: X forward (len 11), Y left, Z up (centred on hull)
hits = [
    (2.05, 2, (-2.0, 3.2, 0.3)),
    (2.45, 1, (1.5, -2.6, 0.2)),
    (2.8, 3, (-3.5, -1.0, 0.6)),
    (3.15, 0, (0.5, 2.0, 0.5)),
    (3.5, 4, (-1.0, -3.4, 0.1)),
    (3.85, 2, (2.5, 1.0, 0.4)),
    (4.15, 1, (-2.5, 2.5, 0.2)),
]
for t, i, lh in hits:
    sting(dfs[i], t, Vector(lh))
# the finisher: three at once
for i, lh in ((0, (0.0, 0.8, 0.5)), (3, (0.5, -0.8, 0.3)), (4, (-0.8, 0.0, -0.2))):
    sting(dfs[i], 4.5, Vector(lh), dur=0.28, width=0.05)

# ------------------------------------------------------------------------------- bomber fights back
gun_pts = [Vector((-4.2, 0, 0.5)), Vector((1.0, 0, 0.9)), Vector((-1.0, 0, -0.6))]
t = 1.7
k = 0
while t < 4.4:
    tgt = dfs[k % N]
    if t > t_join[k % N] - 0.2:
        g = gun_pts[k % 3]
        p0 = W(condor, t, g)
        p1 = W(tgt, t + 0.12, (-3.0, 0, 0)) + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))) * 1.2
        p1 = p0 + (p1 - p0).normalized() * 30.0
        P.projectile(p0, p1, t, 140, COL['tracer'], size=0.08)
        P.light(p0, t, COL['terran_orange'], energy=400, dur=0.06)
    t += 0.09 + (0.25 if k % 6 == 5 else 0)
    k += 1


# bomber damage: flames that ride on the hull after each hit, trailing smoke
def hull_fire(t0, lh, size):
    o = K.ico('HullFire', 1.0, M_FLAME, sub=2)
    o.parent = condor.root
    o.location = Vector(lh) * 0.9
    for f in range(int(P.T(t0)), int(P.T(T_BREAK)) + 2):
        s = size * R.uniform(0.6, 1.1) * min(1.0, (f - P.T(t0)) / 4 + 0.3)
        o.scale = (s * 1.5, s, s)
        o.keyframe_insert('scale', frame=f)
    K.show_between(o, P.T(t0), P.T(T_BREAK) + 1)
    t = t0 + 0.05
    while t < T_BREAK:
        P.puff(W(condor, t, Vector(lh)), t, size=size * 1.6, n=1, rise=0.6, life=1.4, color=(0.06, 0.055, 0.05), opacity=0.8)
        t += 0.1


for (t, lh) in condor_hits[1::2]:
    hull_fire(t + 0.05, lh, 0.3)

# ------------------------------------------------------------------------------- break-up
P.explosion(C(T_BREAK) + Vector((0, 0, 0.3)), T_BREAK, size=1.6, debris=18, smoke=True)
M_BURST = K.emit_mat('BreakFire', (1.0, 0.13, 0.01), 1.4)
M_BURST2 = K.emit_mat('BreakFireHot', (1.0, 0.3, 0.03), 2.2)
for k in range(7):
    o = K.ico('BreakFire', 1.0, M_BURST2 if k < 2 else M_BURST, sub=2)
    c0 = C(T_BREAK) + Vector((R.uniform(-2.5, 2.5), R.uniform(-1.2, 1.2), R.uniform(-0.6, 0.8)))
    f0 = P.T(T_BREAK + k * 0.02)
    o.rotation_euler = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    sz = R.uniform(0.9, 1.5)
    for df_, sc_, dp in ((0, 0.1, 0), (3, sz, 0.15), (9, sz * 0.8, 0.5), (14, 0.05, 0.9)):
        o.location = c0 + CV * (df_ / FPS) + Vector((0, 0, dp))
        o.scale = (sc_ * 1.3, sc_, sc_)
        o.keyframe_insert('location', frame=f0 + df_)
        o.keyframe_insert('scale', frame=f0 + df_)
    K.show_between(o, f0, f0 + 14)
P.light(C(T_BREAK), T_BREAK, (1.0, 0.45, 0.1), energy=15000, dur=0.4, radius=2)
condor.vanish(T_BREAK + 1 / FPS)

mb = condor.mats[int(round(P.T(T_BREAK)))]


def piece(name, keep, spin, vel, fire_at):
    """Copy the bomber's meshes in root space, cut with a plane, keep one side."""
    root = K.empty('CondorPiece_' + name)
    root.rotation_mode = 'QUATERNION'
    rinv = condor.mats[1].inverted()
    bpy.context.scene.frame_set(1)
    for m in condor.meshes:
        me = m.data.copy()
        me.transform(rinv @ m.matrix_world)
        bm = bmesh.new()
        bm.from_mesh(me)
        for (co, no) in keep:
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True, use_snap_center=False)
        bm.to_mesh(me)
        bm.free()
        o = K.link(bpy.data.objects.new('CPiece', me))
        o.parent = root
        for s in o.material_slots:
            pass
        # scorch the cut: darken by mixing in charred slots is overkill; add a charred inner shell
    fl = K.ico('PieceFire', 1.0, M_FLAME, sub=2)
    fl.parent = root
    fl.location = fire_at
    p0 = mb.translation.copy()
    q0 = mb.to_quaternion()
    prev = None
    for f in range(int(P.T(T_BREAK)), NF + 1):
        t = (f - 1) / FPS - T_BREAK
        p = p0 + (CV + vel) * t + Vector((0, 0, -0.5 * 9.8 * 0.8 * t * t))
        q = q0 @ (Matrix.Rotation(spin[0] * t, 3, 'X') @ Matrix.Rotation(spin[1] * t, 3, 'Y')).to_quaternion()
        if prev is not None:
            q.make_compatible(prev)
        prev = q
        root.location = p
        root.rotation_quaternion = q
        root.keyframe_insert('location', frame=f)
        root.keyframe_insert('rotation_quaternion', frame=f)
        s = R.uniform(0.3, 0.5)
        fl.scale = (s * 1.8, s, s)
        fl.keyframe_insert('scale', frame=f)
        if f % 2 == 0:
            wp_ = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Vector(fire_at)
            P.puff(wp_, (f - 1) / FPS, size=1.6, n=1, rise=1.0, life=1.6, color=(0.05, 0.045, 0.04), opacity=0.85)
    K.set_interp(root, 'LINEAR')
    for o in [root] + list(root.children_recursive):
        K.key_hide(o, 0, True)
        K.key_hide(o, P.T(T_BREAK) + 1, False)


piece('front', [(Vector((0.4, 0, 0)), Vector((-1, 0, 0)))], spin=(1.4, 0.9), vel=Vector((-2.0, 2.5, 1.5)),
      fire_at=Vector((0.6, 0, 0.2)))
piece('rearL', [(Vector((0.4, 0, 0)), Vector((1, 0, 0))), (Vector((0, 0, 0)), Vector((0, -1, 0)))],
      spin=(-2.2, -0.6), vel=Vector((-4.0, 3.0, 0.5)), fire_at=Vector((0.2, 0.3, 0.2)))
piece('rearR', [(Vector((0.4, 0, 0)), Vector((1, 0, 0))), (Vector((0, 0, 0)), Vector((0, 1, 0)))],
      spin=(2.6, -1.0), vel=Vector((-3.0, -1.5, 0.0)), fire_at=Vector((0.2, -0.3, 0.2)))

# ------------------------------------------------------------------------------- camera
A = ALT


def swarm(t):
    return sum((df_pos(i, t) for i in range(N)), Vector()) / N


P.camera([
    (0.0, (-4.0, -40.0, 1.6), (-9.0, -26.0, 10.0), 22),
    (0.45, (-5.0, -39.0, 3.5), swarm(0.5) + Vector((0, 4, 3)), 24),
    (0.9, (-6.0, -34.0, 9.0), swarm(0.95) + Vector((0, 6, 4)), 24),
    (1.5, (-9.0, -30.0, A - 13.0), (swarm(1.5) + C(1.5)) / 2, 24),
    (2.4, (-6.5, -20.0, A + 1.5), C(2.4), 30),
    (3.4, (1.0, -18.5, A + 4.5), C(3.4) + Vector((0, 0, -1)), 30),
    (4.4, (8.0, -19.0, A + 2.5), C(4.4), 28),
    (5.2, (16.0, -20.0, A + 0.5), C(T_BREAK) + Vector((3, 0, -1)), 28),
    (6.0, tuple(CAM_END), (25.5, 0.0, A - 2.5), 30),
], shake=0.04)
P.cam_shake(T_BREAK, 0.35, dur=0.5)
for t, i, lh in hits:
    P.cam_shake(t, 0.06, dur=0.15)

P.render()
