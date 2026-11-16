"""Arcadian Stingray fighter (space): three Terran Twin-X fighters cruise in a V over a blue
planet. Out of the dark behind them three gold Stingrays dive in one after another, lightning
thrusters flaring, and ripple straight through the formation: the first lashes the left wingman
with gold lightning and flies through the fireball, the second takes the right wingman, the
lead Twin-X breaks and runs. The rays re-form into an arrowhead and the camera pushes in on the
hero ray, thrusters crackling, the two burning wrecks falling away behind.

Timeline (s): 0-2.0 chase cam behind the Twin-X V, rays sweep in from behind/above; S1 lashes
B 1.45-1.75, B blows 1.75 | 2.0-3.5 side shot: S2 lashes C 2.15-2.45, C blows 2.45, S2 bursts
through the smoke, lead Twin-X A breaks away | 3.5-6.0 front hero shot: the three rays form up,
push in on S1, end on S1 big, wingmen behind, wreck smoke far behind.

Ships are film placeholders: loaded by name, nose along +X (models.json kind 'ship')."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_arcadian_stingray', seconds=6.0, seed=31)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']

P.space(planet=(900, 260, -820, 760, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(58, 0, 150), sun_energy=4.0)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


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
    """Key root location + quaternion every frame. Nose along velocity."""
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
    actor.posf = posf
    return mats


def W(actor, t, local=(0, 0, 0)):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


def bank_up(k=1.0, clamp=55):
    """Bank into turns: back points along +Z plus k * lateral acceleration."""
    def up(t, p, v, a):
        vn = v.normalized()
        lat = a - vn * a.dot(vn)
        u = (Vector((0, 0, 9.8)) + lat * k).normalized()
        ang = math.degrees(math.acos(max(-1, min(1, u.z))))
        if ang > clamp:
            h = Vector((u.x, u.y, 0)).normalized()
            c = math.radians(clamp)
            u = h * math.sin(c) + Vector((0, 0, math.cos(c)))
        return u
    return up


def spline(keys):
    """Catmull-Rom through (t, (x, y, z)) keys, linear extrapolation outside."""
    ks = [(t, Vector(p)) for t, p in keys]
    vel = []
    for i, (t, p) in enumerate(ks):
        a = ks[max(i - 1, 0)]
        b = ks[min(i + 1, len(ks) - 1)]
        vel.append((b[1] - a[1]) / max(1e-4, b[0] - a[0]))

    def f(t):
        if t <= ks[0][0]:
            return ks[0][1] + vel[0] * (t - ks[0][0])
        if t >= ks[-1][0]:
            return ks[-1][1] + vel[-1] * (t - ks[-1][0])
        for i in range(len(ks) - 1):
            t0, p0 = ks[i]
            t1, p1 = ks[i + 1]
            if t0 <= t <= t1:
                h = t1 - t0
                u = (t - t0) / h
                h00 = 2 * u ** 3 - 3 * u ** 2 + 1
                h10 = u ** 3 - 2 * u ** 2 + u
                h01 = -2 * u ** 3 + 3 * u ** 2
                h11 = u ** 3 - u ** 2
                return p0 * h00 + vel[i] * (h10 * h) + p1 * h01 + vel[i + 1] * (h11 * h)
    return f


# Formation frame: the Twin-X V cruises along +X.
U = Vector((24, 0, 0))


def F(t):
    return U * t


def rel(keys):
    """Keys given relative to the formation frame -> world spline."""
    return spline([(t, F(t) + Vector(p)) for t, p in keys])


# ------------------------------------------------------------------------------- timing
T_LASH1, T_KILL_B = 1.45, 1.75
T_LASH2, T_KILL_C = 2.15, 2.45
CUT1, CUT2 = 48 / 24, 84 / 24      # 2.0 s, 3.5 s

# ------------------------------------------------------------------------------- Twin-X V
B_OFF = Vector((-16, 14, 2))
C_OFF = Vector((-16, -14, -2))


def tw_pos(off, ph):
    def f(t):
        return F(t) + off + Vector((0, 0.6 * math.sin(1.3 * t + ph), 0.5 * math.sin(0.9 * t + ph * 2)))
    return f


a_base = tw_pos(Vector((0, 0, 0)), 0.0)


def a_pos(t):
    """Lead Twin-X: breaks hard down and right once both wingmen are gone."""
    p = a_base(t)
    d = max(0.0, t - 2.2)
    return p + Vector((4 * d * d, 10 * d * d, -18 * d * d))


twA = P.load('terran_twinx', label='twinA')
twB = P.load('terran_twinx', label='twinB')
twC = P.load('terran_twinx', label='twinC')
fly(twA, a_pos, bank_up(0.5, 70))
fly(twB, tw_pos(B_OFF, 1.1), bank_up(0.5))
fly(twC, tw_pos(C_OFF, 2.3), bank_up(0.5))

# ------------------------------------------------------------------------------- Stingrays
# S1 (hero) takes B, S2 takes C, S3 dives on the lead and chases it off.
s1_pos = rel([
    (-0.6, (-150, 40, 34)),
    (0.0, (-112, 32, 24)),
    (0.8, (-74, 23, 13)),
    (1.5, (-42, 16, 5)),
    (2.0, (-12, 9, -2)),
    (2.7, (26, 3, 7)),
    (3.5, (60, -3, 8)),
    (4.6, (100, -4, 6)),
    (6.0, (146, -4, 5)),
    (6.6, (166, -4, 5)),
])
s2_pos = rel([
    (-0.6, (-178, 6, 44)),
    (0.0, (-150, 2, 34)),
    (0.9, (-104, -6, 18)),
    (1.6, (-68, -12, 6)),
    (2.2, (-40, -13, 0)),
    (2.75, (-12, -10, -1)),
    (3.5, (34, -11, 4)),
    (4.6, (88, -15, 4)),
    (6.0, (134, -13, 3)),
    (6.6, (156, -13, 3)),
])
s3_pos = rel([
    (-0.6, (-172, 30, 64)),
    (0.0, (-140, 24, 52)),
    (1.0, (-100, 18, 34)),
    (2.0, (-58, 8, 16)),
    (2.8, (-22, 0, 4)),
    (3.5, (28, 8, 6)),
    (4.6, (88, 7, 8)),
    (6.0, (134, 5.5, 7)),
    (6.6, (156, 5.5, 7)),
])


def s3_roll(t):
    return 2 * math.pi * ss((t - 2.55) / 0.7)


s1 = P.load('arcadian_stingray', label='ray1')
s2 = P.load('arcadian_stingray', label='ray2')
s3 = P.load('arcadian_stingray', label='ray3')
fly(s1, s1_pos, bank_up(1.4, 50))
fly(s2, s2_pos, bank_up(1.4, 50))
fly(s3, s3_pos, bank_up(1.4, 50), roll_extra=s3_roll)
print('s1', s1_pos(0), s1_pos(2), s1_pos(6), ' A', a_pos(6))

# Stingray local landmarks (normalised model, nose +X, 10 m span)
RAY_NOSE = Vector((4.6, 0, -0.5))
RAY_TRAIL = [Vector((-1.2, 0.9, -0.35)), Vector((-1.2, -0.9, -0.35))]
RAY_TIPS = [Vector((-0.9, 4.7, 0.2)), Vector((-0.9, -4.7, 0.2))]


# ------------------------------------------------------------------------------- lightning thrusters
def attach_new(before, parent):
    """Parent every object created since `before` to `parent` (local coords = as created)."""
    for o in bpy.data.objects:
        if o not in before and o.parent is None:
            o.parent = parent
            o.matrix_parent_inverse = Matrix()


def thrust(actor, t0, t1, length, width, tips=False):
    """Gold lightning thrusters: kit bolts built in the ray's local space, parented to it."""
    before = set(bpy.data.objects)
    for p in RAY_TRAIL:
        P.lightning(p, p + Vector((-length, 0.25 * p.y, -0.1)), t0, t1, color=GOLD,
                    width=width, jag=0.22, branches=1, segs=8)
    if tips:
        for p in RAY_TIPS:
            P.lightning(p, p + Vector((-length * 0.45, 0.1 * p.y, 0)), t0, t1, color=GOLD,
                        width=width * 0.7, jag=0.3, branches=0, segs=5)
    attach_new(before, actor.root)


def thrust_plan(actor, plan):
    """plan: [(t0, t1, length, width, tips)] contiguous segments."""
    for t0, t1, L, w, tips in plan:
        thrust(actor, t0, t1, L, w, tips)


thrust_plan(s1, [(0.0, 1.2, 5.5, 0.09, False), (1.2, 2.2, 9.0, 0.13, True),
                 (2.2, 3.6, 6.0, 0.1, False), (3.6, 6.05, 7.5, 0.11, True)])
thrust_plan(s2, [(0.0, 1.8, 5.5, 0.09, False), (1.8, 2.9, 9.0, 0.13, True),
                 (2.9, 6.05, 6.5, 0.1, False)])
thrust_plan(s3, [(0.0, 2.4, 6.0, 0.09, False), (2.4, 3.4, 9.0, 0.13, True),
                 (3.4, 6.05, 6.5, 0.1, False)])


# ------------------------------------------------------------------------------- attacks
def lash(src, dst, t0, t1, hit_local=(0, 0, 0)):
    """Gold lightning from the ray's nose to the target, re-aimed every frame."""
    f0 = int(round(P.T(t0)))
    f1 = int(round(P.T(t1)))
    for f in range(f0, f1):
        t = (f - 1) / FPS
        P.lightning(W(src, t, RAY_NOSE), W(dst, t, hit_local), t, t + 1 / FPS, color=GOLD,
                    width=0.09, jag=0.16, branches=2, segs=12)
    P.impact(W(dst, t0 + 0.05, hit_local), t0 + 0.05, size=1.3, color=GOLD)


def kill(actor, t, size=4.5):
    p = W(actor, t)
    before = set(bpy.data.objects)
    P.explosion(p, t, size=size, debris=16)
    for o in list(bpy.data.objects):
        if o not in before and o.name.split('.')[0] == 'Scorch':
            bpy.data.objects.remove(o, do_unlink=True)
    P.puff(p, t + 0.4, size=size * 0.7, n=3, rise=1.0, life=2.4, color=(0.2, 0.19, 0.18), opacity=0.45)
    actor.vanish(t + 1 / FPS)


lash(s1, twB, T_LASH1, T_KILL_B)
kill(twB, T_KILL_B)
lash(s2, twC, T_LASH2, T_KILL_C)
kill(twC, T_KILL_C)

# ------------------------------------------------------------------------------- space dust (speed cue)
def dust_field(n=1600, box=((-160, 260), (-70, 70), (-40, 60)), size=0.09):
    me = bpy.data.meshes.new('SpaceDust')
    bm = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        s = size * R.uniform(0.6, 1.4)
        r = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=s)
        bmesh.ops.translate(bm, verts=r['verts'], vec=c)
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new('SpaceDust', me))
    me.materials.append(K.emit_mat('DustGlint', (0.55, 0.6, 0.75), 1.2))
    o.visible_shadow = False
    return o


dust_field()


# ------------------------------------------------------------------------------- camera
def cam_keys():
    keys = []
    # Shot 1: over the hero's shoulder as it dives on the Twin-X V.
    for i in range(0, 13):
        t = CUT1 * i / 12
        if i == 12:
            t = CUT1 - 1 / FPS
        u = t / CUT1
        s = s1_pos(t)
        pos = s + Vector((lerp(-17, -14, ss(u)), lerp(4, -5, ss(u)), lerp(7.5, 7, ss(u))))
        look = (s + Vector((14, -2, -2))).lerp(W(twB, min(t, T_KILL_B - 0.05)), 0.35 * ss(u * 1.4))
        keys.append((t, pos, look, 30))
    # Shot 2: alongside the second ray as it lashes the right wingman.
    for i in range(0, 10):
        t = CUT1 + (CUT2 - CUT1) * i / 9
        if i == 9:
            t = CUT2 - 1 / FPS
        u = (t - CUT1) / (CUT2 - CUT1)
        s = s2_pos(t)
        pos = s + Vector((lerp(20, -4, u), lerp(-32, -24, ss(u)), lerp(9, 5, u)))
        look = s.lerp(W(twC, min(t, T_KILL_C - 0.05)), 0.55 * (1 - ss((u - 0.3) / 0.4)))
        keys.append((t, pos, look, 32))
    # Shot 3: ahead of the re-formed arrowhead, push in on the hero.
    for i in range(0, 13):
        t = CUT2 + (6.0 - CUT2) * i / 12
        u = (t - CUT2) / (6.0 - CUT2)
        s = s1_pos(t)
        pos = s + Vector((lerp(38, 17, ss(u)), lerp(-18, -9, ss(u)), lerp(13, 8, ss(u))))
        look = s * 0.5 + (s2_pos(t) + s3_pos(t)) * 0.25 + Vector((lerp(-6, -2, ss(u)), 0, -0.5))
        keys.append((t, pos, look, 32))
    return keys


P.camera(cam_keys(), lens=30, cuts=(CUT1, CUT2))

P.render()
