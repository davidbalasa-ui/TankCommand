"""Corona (Arcadian missile tower): a packed Corona drops out of a violet sky riding legs of gold
lightning, slams down in a dust ring and blooms open, its claw of seeker pods rising and lighting
up. Two Terran Falcons scream in low right over the claw. The crown slews after them, the pods
pulse a lock... a beat... then it ripple-fires six gold seeker orbs. They leap off the rails,
curl up and over and chase the Falcons into their break: the lead bursts in the climb, the
wingman dives for the deck and the last orbs swing down after it. End low on the Corona, crown
still glowing, gold trails hanging in the sky and two wrecks burning on the horizon.

Timeline (s): 0-1.5 drop-in on lightning lifters | 1.5 touchdown + dust ring | 1.6-2.7 bloom |
2.3-2.7 Falcons scream over | 2.7-3.1 slew + lock | 3.1-3.45 ripple (6 orbs) | ~3.9 / ~4.4
kills | wrecks fall | 4.8-6 low hero frame."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_corona', seconds=6.0, seed=7)
FPS = P.fps
NF = P.nf
R = P.rnd

P.env('alien', sun=(38, 0, -40), sun_energy=4.2, props=34,
      clear=[(0, 0, 12), (-12, 8, 8), (38, 20, 14)])
P.flatten(0, 0, 11)
P.flatten(40, 22, 14)

GOLD = COL['arc_gold']
DEEP = (1.0, 0.42, 0.03)
SAND = tuple(min(1, c * 1.9) for c in P.palette['g1'])


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('C_' + key, col, strength, alpha=alpha)
    return _mats[key]


M_BOLT = mat('Bolt', GOLD, 2.4)
M_CORE = mat('BoltCore', (1.0, 0.7, 0.3), 3.0)
M_GLOW = mat('BoltGlow', DEEP, 1.1, alpha=0.22)


# --------------------------------------------------------------------------- lightning helpers
def jag_pts(p0, p1, segs, jag):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
        pts.append(p0 + d * u + off)
    return pts


def bolt_frame(pts, f, width, glow=True, core=True, forks=0, nframes=1):
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
        dv = pts[k + 1] - pts[k - 1]
        side = dv.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        dirb = (dv.normalized() + side * R.uniform(-1.2, 1.2) + Vector((0, 0, R.uniform(-.6, .4)))).normalized()
        bl = dv.length * R.uniform(0.7, 1.4)
        objs.append(K.polyline('BoltFork', [a, a + dirb * bl * 0.5, a + dirb * bl], width * 0.55, M_BOLT))
    for o in objs:
        K.show_between(o, f, f + nframes)
    return objs


def gold_sparks(pos, t, size=1.0, n=8):
    m = mat('Spark', GOLD, 2.5)
    f0 = P.T(t)
    for i in range(n):
        sp = K.sphere('Spk', 1.0, m, seg=(6, 4))
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.5, 1.2))).normalized() * size * 3.2
        sp.scale = (0.14 * size, 0.03 * size, 0.03 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + Vector((0, 0, -0.15))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)


def dust_wave(center, t, r0, r1, rings=3, n=26, size=1.1, life=1.4, opacity=0.3, rise=0.5, dt=0.1):
    c = Vector(center)
    for k in range(rings):
        u = k / max(1, rings - 1)
        r = r0 + (r1 - r0) * u
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.08, 0.08)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.92, 1.08)
            P.puff(p + Vector((0, 0, 0.25)), t + dt * k + R.uniform(0, 0.04), size=size * (0.8 + 0.5 * u),
                   n=1, rise=rise * (1 + u), life=life, color=SAND, opacity=opacity * (1 - 0.3 * u))


def quiet_explosion(pos, t, size, debris=8, scorch=True, smoke=True):
    """Kit explosion without the white-hot core blob (optionally no ground scorch, for air bursts)."""
    before = set(bpy.data.objects)
    P.explosion(pos, t, size=size, debris=debris, smoke=smoke)
    for o in set(bpy.data.objects) - before:
        nm = o.name.split('.')[0]
        if nm == 'Core':
            o.data.materials[0] = mat('CoreSoft', (1.0, 0.45, 0.08), 2.5)
            o.scale = o.scale * 0.6
        elif nm == 'Scorch' and not scorch:
            bpy.data.objects.remove(o)


# --------------------------------------------------------------------------- the Corona
T_LAND = 1.5
T_UF0, T_UF1 = 1.62, 2.7

cor = P.load('corona', at=(0, 0), heading=0, label='corona')
bpy.context.view_layer.update()
piv = cor.parts['TurretPivot']
tur = cor.parts['Turret']

# pod tips (measured on the deployed mesh: two rows of three, pitched up toward +X)
TIPS = []
for y in (1.11, 0.0, -1.11):
    TIPS.append((Vector((1.62, y, 5.6)), Vector((0.77, 0, 0.64)).normalized()))
for y in (1.11, 0.0, -1.11):
    TIPS.append((Vector((1.5, y, 4.15)), Vector((0.84, 0, 0.54)).normalized()))

# yaw joint between the unfolding pivot and the claw (the pivot's rotation belongs to unfold)
yaw = K.empty('CorYaw')
yaw.parent = piv
yaw.rotation_mode = 'XYZ'
mpi = tur.matrix_parent_inverse.copy()
tur.parent = yaw
tur.matrix_parent_inverse = mpi
bpy.context.view_layer.update()
tw_inv = tur.matrix_world.inverted()
tip_e = []
for p, d in TIPS:
    e = K.empty('PodTip')
    e.parent = tur
    e.matrix_parent_inverse = tw_inv
    e.location = p
    e.rotation_mode = 'QUATERNION'
    e.rotation_quaternion = d.to_track_quat('X', 'Z')
    tip_e.append(e)

cor.unfold(T_UF0, T_UF1)

# packed underside height (root-local) so the carrier sits on the ground at touchdown
sc = bpy.context.scene
sc.frame_set(1)
bpy.context.view_layer.update()
zmin = 1e9
for o in cor.meshes:
    for c in o.bound_box:
        zmin = min(zmin, (o.matrix_world @ Vector(c)).z)
LIFT = zmin
print('PACKED underside z', LIFT)

root = cor.root
root.rotation_mode = 'XYZ'
drop = [(0.0, (-19.0, 12.5, 9.0), -6, 8, -26), (0.55, (-10.5, 7.0, 5.2), -4, 6, -20),
        (1.1, (-3.2, 2.1, 1.7), 3, -3, -8), (1.38, (-0.5, 0.35, 0.45 - LIFT), 2, -5, -2),
        (T_LAND, (0, 0, 0.02 - LIFT), 0, 0, 0)]
for t, p, rx, ry, rz in drop:
    root.location = p
    root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
root.location = (0, 0, -0.06 - LIFT)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.05))
root.location = (0, 0, 0.02 - LIFT)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.15))
root.keyframe_insert('location', frame=P.T(T_UF0))
root.location = (0, 0, 0)
root.keyframe_insert('location', frame=P.T(T_UF1))
K.set_interp(root, 'BEZIER')


def cor_pos(t):
    return cor.pos_at(t)


# lifter legs: jagged gold bolts from under the carrier down to the ground, longer when high
gl = K.link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
gl.parent = root
gl.location = (0, 0, LIFT - 0.4)
gl.data.color = GOLD
gl.data.shadow_soft_size = 1.5
for t, e in [(0.0, 1500), (1.2, 1500), (T_LAND, 500), (T_LAND + 0.1, 0)]:
    gl.data.energy = e
    gl.data.keyframe_insert('energy', frame=P.T(t))

f_end = int(round(P.T(T_LAND + 0.06)))
for f in range(1, f_end + 1):
    t = (f - 1) / FPS
    c = cor_pos(t)
    under = c.z + LIFT
    fade = 1.0 if t < T_LAND - 0.12 else max(0.0, (T_LAND + 0.06 - t) / 0.18)
    nlegs = 4 if fade > 0.6 else 3
    vel = (cor_pos(t + 0.05) - cor_pos(max(0, t - 0.05))) / 0.1 if t > 0 else Vector((14, -9, -7))
    hv = Vector((vel.x, vel.y, 0))
    for k in range(nlegs):
        if R.random() < 0.15:
            continue
        a = 2 * math.pi * k / nlegs + R.uniform(-0.4, 0.4) + t * 2.5
        r0 = R.uniform(0.8, 1.4)
        p0 = c + Vector((r0 * math.cos(a), r0 * math.sin(a), LIFT + 0.05))
        r1 = r0 * R.uniform(1.0, 1.6)
        # legs rake back against the direction of travel
        p1 = Vector((p0.x + (r1 - r0) * math.cos(a), p0.y + (r1 - r0) * math.sin(a), 0.03)) - hv * 0.06 * min(1.0, under / 3)
        if under > 6.5:     # too high to reach the ground: short crackling stubs under the hull
            p1 = p0 + Vector((R.uniform(-.6, .6), R.uniform(-.6, .6), -R.uniform(1.2, 2.2)))
        bolt_frame(jag_pts(p0, p1, 7, 0.26), f, 0.035 * (0.5 + 0.5 * fade), forks=1 if k % 2 else 0, glow=(k == 0))
    if f % 2 == 0 and under < 6.5 and t < T_LAND:
        gp = Vector((c.x + R.uniform(-1.4, 1.4), c.y + R.uniform(-1.4, 1.4), 0.15))
        P.puff(gp, t, size=1.0, n=1, rise=0.5, life=0.9, color=SAND, opacity=0.3)
        if f % 4 == 0:
            gold_sparks(gp, t, size=0.35, n=3)

dust_wave((0, 0, 0), T_LAND - 0.02, 3.0, 9.0, rings=3, n=24, size=1.0, life=1.3, opacity=0.26)
dust_wave((0, 0, 0), T_UF1 - 0.1, 3.2, 5.5, rings=2, n=18, size=0.8, life=1.1, opacity=0.18)

# --------------------------------------------------------------------------- loaded seeker orbs
M_POD = K.emit_mat('PodOrb', GOLD, 0.0)
for t, v in [(0, 0.0), (T_UF1 - 0.35, 0.0), (T_UF1, 1.3), (2.85, 1.3), (2.92, 2.6), (2.98, 1.3),
             (3.04, 2.8), (3.1, 2.8), (6.0, 2.8)]:
    K.key_strength(M_POD, P.T(t), v)
M_POD_GLOW = K.emit_mat('PodOrbGlow', DEEP, 0.0, alpha=0.25)
for t, v in [(0, 0.0), (T_UF1 - 0.35, 0.0), (T_UF1, 1.0), (2.9, 1.0), (3.04, 1.8), (6.0, 1.8)]:
    K.key_strength(M_POD_GLOW, P.T(t), v)

T_RIP = [3.10, 3.17, 3.24, 3.31, 3.38, 3.45]
ORDER = [0, 3, 2, 5, 1, 4]          # which pod fires on each shot (alternate rows/sides)
TGT = [0, 0, 0, 1, 1, 1]            # 0 = lead Falcon, 1 = wingman
pod_orbs = []
for k, e in enumerate(tip_e):
    o = K.sphere('PodOrb', 1.0, M_POD, seg=(12, 8))
    o.parent = e
    o.location = (0.05, 0, 0)
    o.scale = (0.2,) * 3
    g = K.sphere('PodOrbGlow', 1.0, M_POD_GLOW, seg=(12, 8))
    g.parent = o
    g.scale = (2.0,) * 3
    tf = T_RIP[ORDER.index(k)]
    for ob in (o, g):
        K.show_between(ob, P.T(T_UF1 - 0.35), P.T(tf))
    pod_orbs.append(o)

# --------------------------------------------------------------------------- Falcons


def catmull(keys):
    """t -> Vector through [(t, (x, y, z))] (Catmull-Rom in time, extrapolated at the ends)."""
    ts = [k[0] for k in keys]
    ps = [Vector(k[1]) for k in keys]

    def f(t):
        if t <= ts[0]:
            v = (ps[1] - ps[0]) / (ts[1] - ts[0])
            return ps[0] + v * (t - ts[0])
        if t >= ts[-1]:
            v = (ps[-1] - ps[-2]) / (ts[-1] - ts[-2])
            return ps[-1] + v * (t - ts[-1])
        i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
        t0, t1 = ts[i], ts[i + 1]
        p0, p1 = ps[i], ps[i + 1]
        h = t1 - t0
        m0 = (ps[i + 1] - ps[i - 1]) / (ts[i + 1] - ts[i - 1]) if i > 0 else (p1 - p0) / h
        m1 = (ps[i + 2] - ps[i]) / (ts[i + 2] - ts[i]) if i + 2 < len(ts) else (p1 - p0) / h
        u = (t - t0) / h
        h00 = 2 * u ** 3 - 3 * u ** 2 + 1
        h10 = u ** 3 - 2 * u ** 2 + u
        h01 = -2 * u ** 3 + 3 * u ** 2
        h11 = u ** 3 - u ** 2
        return p0 * h00 + m0 * (h10 * h) + p1 * h01 + m1 * (h11 * h)
    return f


FAL_KEYS = [
    # lead: screams over the claw, then a climbing left break
    [(0.0, (-92, -40, 10.5)), (1.0, (-52, -23, 9.5)), (2.0, (-14, -5.5, 8.4)), (2.45, (2.5, 1.0, 8.2)),
     (2.95, (17, 6, 9.5)), (3.4, (27, 12, 13.0)), (3.9, (33, 22, 17.0)), (4.5, (33, 36, 21.0)),
     (5.4, (26, 50, 24.0))],
    # wingman: lower, offset to the right, breaks left and down for the deck
    [(0.0, (-96, -46, 9.5)), (1.0, (-56, -29, 8.8)), (2.0, (-18, -11, 7.8)), (2.55, (1.0, -3.6, 7.4)),
     (3.05, (17, -2, 6.5)), (3.5, (27, 3, 5.0)), (4.0, (33, 10, 4.0)), (4.6, (36, 20, 3.8)),
     (5.4, (37, 34, 4.0))],
]
fal_pos = [catmull(k) for k in FAL_KEYS]

falcons = [P.load('falcon', label=f'falcon{i}') for i in range(2)]
F_H = falcons[0].entry['height']
for a in falcons:
    a.model_root.location.z = -F_H / 2

ENG = Vector((-2.62, 0.0, 0.52 - F_H / 2))


def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def bank_up(k=1.6, clamp=70):
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


def fly(actor, posf, upf, t_end):
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    dt = 1.0 / FPS
    for f in range(0, int(P.T(t_end)) + 2):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        m3 = frame_from(v, upf(t, p, v, a))
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


for i, a in enumerate(falcons):
    fly(a, fal_pos[i], bank_up(), 6.0)

M_ENG = mat('Eng', COL['terran_neon'], 2.2)
M_ENG_HOT = mat('EngHot', (0.3, 0.7, 1.0), 2.2)
M_ENG_GLOW = mat('EngGlow', COL['terran_neon'], 1.2, alpha=0.15)


def engine(actor):
    core = K.sphere('EngCore', 1.0, M_ENG_HOT, seg=(10, 6))
    core.parent = actor.root
    core.location = ENG + Vector((-0.2, 0, 0))
    core.scale = (0.32, 0.26, 0.26)
    glow = K.sphere('EngGlow', 1.0, M_ENG_GLOW, seg=(12, 8))
    glow.parent = actor.root
    plume = K.sphere('EngPlume', 1.0, M_ENG, seg=(10, 6))
    plume.parent = actor.root
    for f in range(0, NF + 2, 2):
        fl = R.uniform(0.85, 1.2)
        plume.location = ENG + Vector((-0.75 * fl, 0, 0))
        plume.scale = (0.75 * fl, 0.12, 0.12)
        glow.location = ENG + Vector((-0.6 * fl, 0, 0))
        glow.scale = (1.2 * fl, 0.42, 0.42)
        for o in (plume, glow):
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('scale', frame=f)
    L = K.link(bpy.data.objects.new('EngLight', bpy.data.lights.new('EngLight', 'POINT')))
    L.parent = actor.root
    L.location = ENG + Vector((-0.8, 0, 0))
    L.data.color = COL['terran_neon']
    L.data.energy = 300
    return [core, glow, plume, L]


eng_parts = [engine(a) for a in falcons]

# wingtip vapour while they pull hard
M_VAPOR = mat('Vapor', (0.9, 0.93, 1.0), 0.9, alpha=0.11)
WTIPS = [Vector((0.85, 1.78, 0.42 - F_H / 2)), Vector((0.85, -1.78, 0.42 - F_H / 2))]


def vapor(actor, t_end):
    fe = int(P.T(t_end))
    hist = {f: [actor.mats[f] @ tp for tp in WTIPS] for f in range(0, fe + 1)}
    for f in range(4, fe + 1):
        m = actor.mats[f]
        upv = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
        load = 1 - abs(upv.z)
        if load < 0.3:
            continue
        n = int(3 + 5 * min(1.0, load))
        for k in range(2):
            pts = [hist[max(0, f - j)][k] for j in range(n)]
            o = K.polyline('Vapor', pts, 0.03, M_VAPOR)
            K.show_between(o, f, f + 1)


# --------------------------------------------------------------------------- crown slew + lock
def world_yaw_to(p, t):
    sc.frame_set(int(round(P.T(t))))
    loc = yaw.parent.matrix_world.inverted() @ Vector(p)
    return math.degrees(math.atan2(loc.y, loc.x))


yA = world_yaw_to(fal_pos[0](3.5), 2.9)
yB = world_yaw_to(fal_pos[1](3.7), 3.2)
print('YAW A', yA, 'B', yB)
for t, v in [(0.0, 0.0), (2.62, 0.0), (2.95, yA + 6.0), (3.05, yA - 1.5), (3.15, yA), (3.28, (yA + yB) / 2),
             (3.5, yB), (4.2, yB + 4), (4.7, yB + 4), (5.6, -18.0), (6.0, -20.0)]:
    yaw.rotation_euler.z = math.radians(v)
    yaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
K.set_interp(yaw, 'BEZIER')

# lock crackle: little gold arcs jumping between the pods as they charge
for f in range(int(P.T(2.75)), int(P.T(3.1)) + 1, 2):
    sc.frame_set(f)
    for _ in range(2):
        a, b = R.sample(range(6), 2)
        pa = tip_e[a].matrix_world.translation
        pb = tip_e[b].matrix_world.translation
        bolt_frame(jag_pts(pa, pb, 6, 0.4), f, 0.025, glow=False, core=False, nframes=2)
P.light(Vector((1.5, 0, 5.0)), 2.78, GOLD, energy=700, dur=0.35, radius=0.8)

# --------------------------------------------------------------------------- seeker orbs
M_ORB = mat('Orb', (1.0, 0.55, 0.1), 2.4)
M_ORB_GLOW = mat('OrbGlow', DEEP, 1.2, alpha=0.22)
M_TRAIL = mat('Trail', GOLD, 1.8, alpha=0.55)
M_TRAIL_GLOW = mat('TrailGlow', DEEP, 0.9, alpha=0.14)
HAZE = (0.95, 0.8, 0.6)


def falcon_center(i, t):
    return fal_pos[i](t)


kill_t = {}
kill_p = {}


def seeker(k, t0, tgt_i):
    """Simulate one homing orb: launch along the pod rail, slow turn at first, then hard pursuit
    with a corkscrew curl. Returns (t_hit, p_hit, pts per frame)."""
    e = tip_e[ORDER[k]]
    sc.frame_set(int(round(P.T(t0))))
    p = e.matrix_world.translation.copy()
    v = (e.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized() * 16.0
    ph = R.uniform(0, 6.28)
    curl_amp = R.uniform(2.5, 4.0)
    sub = 4
    dt = 1.0 / (FPS * sub)
    t = t0
    frames = [(t0, p.copy())]
    hit = None
    for step in range(int(2.5 * FPS * sub)):
        age = t - t0
        if tgt_i in kill_t and t > kill_t[tgt_i] - 0.02:
            tgt = kill_p[tgt_i] + Vector((math.cos(ph) * 1.5, math.sin(ph) * 1.5, 0.6))
        else:
            tgt = falcon_center(tgt_i, t + 0.08)
        want = (tgt - p)
        dist = want.length
        want.normalize()
        speed = min(80.0, 18.0 + 110.0 * age)
        turn = (1.6 if age < 0.18 else 3.0 + 9.0 * ss((age - 0.18) / 0.4))
        vn = v.normalized()
        ang = vn.angle(want) if vn.dot(want) < 0.99999 else 0.0
        mx = turn * dt
        if ang > 1e-5:
            axis = vn.cross(want)
            if axis.length < 1e-6:
                axis = Vector((0, 0, 1))
            vn = Matrix.Rotation(min(ang, mx), 3, axis.normalized()) @ vn
        # corkscrew curl that dies as it closes in
        side = vn.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        upv = side.cross(vn).normalized()
        cw = curl_amp * math.exp(-age * 2.0)
        lat = (side * math.cos(ph + age * 13) + upv * math.sin(ph + age * 13)) * cw
        v = vn * speed
        p = p + (v + lat) * dt
        t += dt
        if step % sub == sub - 1:
            frames.append((t, p.copy()))
        if dist < 1.2 and age > 0.2:
            hit = (t, p.copy())
            break
    if hit is None:
        hit = (t, p.copy())
    return hit[0], hit[1], frames


def draw_orb(frames, t_hit):
    f0 = int(round(P.T(frames[0][0])))
    o = K.sphere('Seeker', 1.0, M_ORB, seg=(12, 8))
    o.scale = (0.3,) * 3
    g = K.sphere('SeekerGlow', 1.0, M_ORB_GLOW, seg=(12, 8))
    g.parent = o
    g.scale = (2.0,) * 3
    for i, (t, p) in enumerate(frames):
        o.location = p
        o.keyframe_insert('location', frame=f0 + i)
    K.set_interp(o, 'LINEAR')
    f1 = f0 + len(frames) - 1
    K.show_between(o, f0, f1 + 1)
    K.show_between(g, f0, f1 + 1)
    L = K.link(bpy.data.objects.new('OrbLight', bpy.data.lights.new('OrbLight', 'POINT')))
    L.parent = o
    L.data.color = GOLD
    L.data.energy = 220
    L.data.shadow_soft_size = 0.4
    K.show_between(L, f0, f1 + 1)
    pts = [p for _, p in frames]
    if len(pts) < 3:
        return
    # bright comet tail: a short window of the path that slides along with the orb
    n = len(pts) - 1
    for name, width, m, tail in (('OrbTrail', 0.09, M_TRAIL, 6), ('OrbTrailGlow', 0.28, M_TRAIL_GLOW, 9)):
        tr = K.polyline(name, pts, width, m)
        cu = tr.data
        cu.bevel_factor_mapping_start = 'SPLINE'
        cu.bevel_factor_mapping_end = 'SPLINE'
        for i in range(n + 1 + tail):
            cu.bevel_factor_end = min(1.0, i / n)
            cu.bevel_factor_start = max(0.0, min(1.0, (i - tail) / n))
            cu.keyframe_insert('bevel_factor_end', frame=f0 + i)
            cu.keyframe_insert('bevel_factor_start', frame=f0 + i)
        K.show_between(tr, f0, f0 + n + tail)
    # faint warm haze trail that lingers in the sky
    hz = K.polyline('OrbHaze', pts, 0.12, P.soft_mat())
    cu = hz.data
    cu.bevel_resolution = 3
    cu.bevel_factor_mapping_end = 'SPLINE'
    for i in range(n + 1):
        cu.bevel_factor_end = max(0.0, (i - 1) / n)
        cu.keyframe_insert('bevel_factor_end', frame=f0 + i)
    cu.bevel_depth = 0.1
    cu.keyframe_insert('bevel_depth', frame=f0)
    cu.bevel_depth = 0.32
    cu.keyframe_insert('bevel_depth', frame=f0 + FPS)
    cu.bevel_depth = 0.5
    cu.keyframe_insert('bevel_depth', frame=NF + 2)
    hz.color = (*HAZE, 0.5)
    hz.keyframe_insert('color', frame=f0)
    hz.color = (*HAZE, 0.3)
    hz.keyframe_insert('color', frame=f0 + int(1.2 * FPS))
    hz.color = (*HAZE, 0.14)
    hz.keyframe_insert('color', frame=NF + 2)
    K.show_between(hz, f0, NF + 2)
    # crackle: tiny gold arcs flicking off the orb
    for i in range(1, len(frames), 2):
        p = frames[i][1]
        back = (frames[i - 1][1] - p)
        q = p + back * R.uniform(1.5, 3.0) + Vector((R.uniform(-.5, .5), R.uniform(-.5, .5), R.uniform(-.5, .5)))
        bolt_frame(jag_pts(p, q, 4, 0.6), f0 + i, 0.025, glow=False, core=False)


results = []
for k, (t0, ti) in enumerate(zip(T_RIP, TGT)):
    th, ph, frames = seeker(k, t0, ti)
    draw_orb(frames, th)
    if ti not in kill_t:
        kill_t[ti] = th
        kill_p[ti] = ph
    else:
        # the target is already dead: this one bursts in its fireball
        quiet_explosion(ph, th, 0.9, debris=0, scorch=False, smoke=False)
        gold_sparks(ph, th, 0.7, n=6)
    results.append((t0, th))
    # launch: gold flash at the pod, the crown kicks back on its mount
    e = tip_e[ORDER[k]]
    P.muzzle_flash(e, t0, GOLD, size=0.7)
    P.light(e.matrix_world.translation, t0, GOLD, energy=900, dur=0.12)
    jf = P.T(t0)
    yaw.location = (0, 0, 0)
    yaw.keyframe_insert('location', index=0, frame=jf - 1)
    yaw.location = (-0.12, 0, 0)
    yaw.keyframe_insert('location', index=0, frame=jf + 1)
    yaw.location = (0, 0, 0)
    yaw.keyframe_insert('location', index=0, frame=jf + 4)
    yaw.rotation_euler.y = 0
    yaw.keyframe_insert('rotation_euler', index=1, frame=jf - 1)
    yaw.rotation_euler.y = math.radians(-2.5)
    yaw.keyframe_insert('rotation_euler', index=1, frame=jf + 1)
    yaw.rotation_euler.y = 0
    yaw.keyframe_insert('rotation_euler', index=1, frame=jf + 5)
print('ORBS', [(round(a, 2), round(b, 2)) for a, b in results])
print('KILLS', kill_t, kill_p)

# --------------------------------------------------------------------------- kills
FLAME_M = mat('WreckFlame', (1.0, 0.25, 0.03), 1.6)


def kill(i, t, crash_t, spin):
    a = falcons[i]
    p = fal_pos[i](t)
    quiet_explosion(p, t, 3.0, debris=16, scorch=False, smoke=False)
    P.puff(p, t + 0.2, size=2.2, n=3, rise=1.5, life=1.8, color=(0.36, 0.33, 0.31), opacity=0.35)
    gold_sparks(p, t, 1.2, n=10)
    P.light(p, t, GOLD, energy=5000, dur=0.2, radius=1.2)
    P.cam_shake(t, 0.06, dur=0.3)
    a.vanish(t + 1 / FPS)
    for o in eng_parts[i]:
        K.show_between(o, 0, P.T(t) + 1)
    # charred wreck tumbling down, trailing fire and smoke
    w = K.empty(a.name + '_wreck')
    w.rotation_mode = 'XYZ'
    src = a.meshes[0]
    wm = src.copy()
    K.link(wm)
    wm.animation_data_clear()
    fA = int(round(P.T(t)))
    sc.frame_set(fA)
    rel = a.root.matrix_world.inverted() @ src.matrix_world
    wm.parent = w
    wm.matrix_parent_inverse.identity()
    wm.matrix_basis = rel
    for s in wm.material_slots:
        s.link = 'OBJECT'
        s.material = P.charred
    fl = K.ico('WreckFire', 1.0, FLAME_M, sub=2)
    fl.parent = w
    fl.location = (-0.6, 0, 0.1)
    vel = (fal_pos[i](t + 0.05) - fal_pos[i](t - 0.05)) / 0.1
    hdg = math.atan2(vel.y, vel.x)
    fB = int(round(P.T(crash_t)))
    tc = crash_t - t
    end = p + Vector((vel.x, vel.y, 0)) * tc * 0.55
    end.z = P.ground_z(end.x, end.y) + 0.2
    for f in range(fA, fB + 1):
        u = (f - fA) / max(1, fB - fA)
        tt = u * tc
        ph = p + Vector((vel.x, vel.y, 0)) * tt * (1 - 0.45 * u)
        ph.z = p.z + vel.z * tt * (1 - u) - 0.5 * 14.0 * tt * tt
        ph.z = max(ph.z, end.z) if u < 1 else end.z
        w.location = ph
        w.rotation_euler = (spin[0] * u, spin[1] * u - 0.5 * u, hdg + spin[2] * u)
        w.keyframe_insert('location', frame=f)
        w.keyframe_insert('rotation_euler', frame=f)
        s_ = R.uniform(0.35, 0.6)
        fl.scale = (s_ * 1.8, s_, s_)
        fl.keyframe_insert('scale', frame=f)
        if f % 2 == 0:
            P.puff(ph + Vector((0, 0, 0.3)), (f - 1) / FPS, size=1.2, n=1, rise=0.6, life=1.6,
                   color=(0.3, 0.27, 0.26), opacity=0.4)
    K.set_interp(w, 'LINEAR')
    K.show_between(w, fA + 1, fB + 1)
    K.show_between(fl, fA + 1, fB + 1)
    c = Vector((ph.x, ph.y, end.z))
    quiet_explosion(c + Vector((0, 0, 0.3)), crash_t, 2.6, debris=10, scorch=True, smoke=False)
    P.fire_patch(c + Vector((0, 0, 0.3)), crash_t + 0.05, 6.0, size=1.0)
    t_ = crash_t + 0.15
    while t_ < 6.0:
        P.puff(c + Vector((0, 0, 0.8)), t_, size=1.4, n=1, rise=4.5, life=2.0, color=(0.32, 0.29, 0.28), opacity=0.35)
        t_ += 0.18
    return c


CRASH = {}
CRASH[0] = kill(0, kill_t[0], kill_t[0] + 1.0, (1.2, 0.6, 1.5))
CRASH[1] = kill(1, kill_t[1], kill_t[1] + 0.6, (-0.9, 0.4, -1.0))
for i, a in enumerate(falcons):
    vapor(a, kill_t[i])
print('CRASH', CRASH)

# --------------------------------------------------------------------------- camera
P.camera([
    (0.0, (8.0, -13.0, 0.8), cor_pos(0.0) + Vector((0, 0, 0.4)), 30),
    (0.7, (6.5, -12.0, 0.9), cor_pos(0.7) + Vector((0, 0, 0.6)), 30),
    (1.5, (3.5, -11.0, 1.0), (0, 0, 1.3), 30),
    (2.1, (-1.5, -9.5, 0.8), (0.5, 0, 3.4), 26),
    (2.55, (-3.8, -10.5, 1.0), (2.0, 1.0, 5.4), 21),
    (3.15, (-4.0, -15.0, 1.5), (14.0, 8.0, 7.5), 22),
    (3.8, (-4.5, -16.0, 1.7), (19.0, 12.0, 9.5), 22),
    (4.4, (-4.5, -15.5, 1.5), (18.0, 10.0, 6.0), 22),
    (5.1, (-4.0, -12.0, 1.0), (10.0, 5.0, 4.2), 24),
    (6.0, (-3.0, -10.5, 0.7), (8.0, 5.5, 4.4), 23),
], shake=0.02)
P.cam_shake(T_LAND, 0.2, 0.4)
P.cam_shake(2.5, 0.08, 0.35)   # Falcons rip overhead
for t in T_RIP:
    P.cam_shake(t, 0.03, dur=0.12)

# deepen kit explosion cores / slugs (Standard view transform clips bright emission to white)
for m_ in bpy.data.materials:
    if m_.name.startswith('Core') and 'emit_node' in m_:
        em = m_.node_tree.nodes[m_['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.35, 0.05, 1)
        em.inputs['Strength'].default_value = 3.0

P.render()
