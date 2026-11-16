"""Falcon (Terran air-superiority fighter): a Halo screams low down a desert canyon with two
Falcons glued to its tail. The pair bank hard through the S-bend, wingtip vapour streaming.
The Halo cracks a gold lightning bolt back at them; the lead's first twin laser burst misses as
it jinks and chews the canyon floor, the wingman's burst connects and it starts to smoke, the
lead's second burst splits its ring in two. The burning halves tumble into the canyon floor and
the Falcons haul up through the smoke, past the camera, into the sky.

Timeline (s): 0-1.8 on the canyon floor: Halo rips overhead, Falcons right behind (pan) |
1.8-4.25 chase camera behind the Falcons: back-fire 2.3, miss 2.1, hit 2.8, kill 3.45-3.62,
halves fall | 4.25-6 low on the floor ahead: halves crash ~4.7, Falcons pull up over the
fireball and climb past camera (wingman victory roll)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_falcon', seconds=6.0, seed=11)
FPS = P.fps
NF = P.nf
R = P.rnd
P.env('desert', sun=(58, 0, 35), sun_energy=4.2, props=0, radius=170)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- the canyon
def cy(x):
    """Canyon centreline y at x."""
    return 14.0 * math.sin((x + 20.0) / 38.0)


def wall_h(x, side):
    return 34.0 + 9.0 * math.sin(x / 17.0 + side) + 5.0 * math.sin(x / 6.9 + 2 * side)


def canyon_z(x, y):
    d = y - cy(x)
    side = 1 if d > 0 else -1
    half = 23.0 + 3.0 * math.sin(x / 11.0 + side)
    u = (abs(d) - half) / 19.0
    if u <= 0:
        return 0.0
    # terraced cliff: steep step, shelf, steep step
    s = ss(min(1.0, u / 0.45)) * 0.6 + ss((u - 0.6) / 0.4) * 0.4
    return wall_h(x, side) * s


g = P.ground
for v in g.data.vertices:
    v.co.z += canyon_z(v.co.x, v.co.y)
g.data.update()
g.modifiers['Displace'].strength = 1.6
bpy.context.view_layer.update()


def scatter(n, rmin, rmax, kinds, seed, scale=(0.6, 1.5)):
    import random
    rnd = random.Random(seed)
    protos = {}
    for kd in kinds:
        protos[kd] = P.load(kd, at=(0, 0), label='proto_' + kd)
        for o in [protos[kd].root] + list(protos[kd].root.children_recursive):
            o.hide_render = True
            o.hide_viewport = True
    for i in range(n):
        x = rnd.uniform(-150, 150)
        d = rnd.uniform(rmin, rmax) * rnd.choice((-1, 1))
        y = cy(x) + d
        kd = rnd.choice(kinds)
        h = K.empty(f'prop_{kd}_{i}')
        P._instance(protos[kd].root, h)
        h.location = (x, y, P.ground_z(x, y) - 0.15)
        h.rotation_euler.z = rnd.uniform(0, 6.28)
        s_ = rnd.uniform(*scale)
        h.scale = (s_, s_, s_)


scatter(70, 3, 30, ['boulder', 'rock_cluster', 'shrub', 'dead_tree'], 3)
scatter(45, 24, 60, ['boulder', 'rock_cluster'], 4, scale=(1.5, 3.5))

# ------------------------------------------------------------------------------- materials
M_BOLT = K.emit_mat('HaloBolt', (1.0, 0.5, 0.06), 3.0)
M_CORE = K.emit_mat('HaloBoltCore', (1.0, 0.72, 0.3), 3.5)
M_GLOW = K.emit_mat('HaloBoltGlow', (1.0, 0.45, 0.04), 1.5, alpha=0.3)
M_ENG = K.emit_mat('FalconEngine', COL['terran_neon'], 2.2)
M_ENG_HOT = K.emit_mat('FalconEngineHot', (0.3, 0.7, 1.0), 2.2)
M_ENG_GLOW = K.emit_mat('FalconEngineGlow', COL['terran_neon'], 1.2, alpha=0.15)
M_VAPOR = K.emit_mat('Vapor', (0.9, 0.93, 1.0), 0.9, alpha=0.11)
M_LASER = K.emit_mat('FalconLaser', COL['laser_blue'], 3.5)
M_LASER_CORE = K.emit_mat('FalconLaserCore', (0.7, 0.9, 1.0), 3.0)
M_LASER_GLOW = K.emit_mat('FalconLaserGlow', COL['laser_blue'], 1.6, alpha=0.3)
M_FLAME = K.emit_mat('HaloFlame', (1.0, 0.22, 0.02), 1.8)
M_SPARK = K.emit_mat('Spark', (0.5, 0.8, 1.0), 3.0)


# ------------------------------------------------------------------------------- flight helper
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


# ------------------------------------------------------------------------------- paths
T_HIT1 = 2.8          # wingman burst connects
T_KILL = 3.45         # lead's second burst
T_BREAK = 3.62
T_PU = 4.45           # pull-up starts


def halo_lat(t):
    return 5.5 * math.sin(2.2 * t + 0.3) + 2.0 * math.sin(4.1 * t)


def halo_alt(t):
    a = 9.5 + 2.2 * math.sin(1.6 * t + 0.5)
    if t > T_HIT1:
        a -= 1.4 * ss((t - T_HIT1) / 0.5)        # staggers lower after the hit
    return a


def halo_pos(t):
    x = -95.0 + 31.0 * t
    return Vector((x, cy(x) + halo_lat(t), halo_alt(t)))


def base_falcon(i, t):
    lag = 0.42 if i == 0 else 0.58
    x = -119.0 + 33.4 * t - (6.5 if i else 0.0)
    lat = halo_lat(t - lag) * 0.9 + (-4.8 if i else 0.0)
    alt = halo_alt(t - lag) + (0.6 if i == 0 else 2.4)
    return Vector((x, cy(x) + lat, alt))


# pull-up: integrate from the base path at T_PU (+ stagger for the wingman)
PU = {}
for i in range(2):
    t0 = T_PU + 0.14 * i
    dt = 1.0 / 240
    p = base_falcon(i, t0)
    v0 = (base_falcon(i, t0 + dt) - base_falcon(i, t0 - dt)) / (2 * dt)
    hdir = Vector((v0.x, v0.y, 0)).normalized()
    spd = v0.length
    tab = [(t0, p.copy())]
    t = t0
    while t < 7.0:
        th = math.radians(30.0) * ss((t - t0) / 0.9)
        turn = Matrix.Rotation(math.radians(-6.0 if i == 0 else 9.0) * (t - t0), 3, 'Z')
        d = (turn @ hdir) * math.cos(th) + Vector((0, 0, 1)) * math.sin(th)
        blend = ss((t - t0) / 0.25)
        vv = v0 * (1 - blend) + d * spd * blend
        p = p + vv * dt
        t += dt
        tab.append((t, p.copy()))
    PU[i] = (t0, dt, tab)


def falcon_pos(i, t):
    t0, dt, tab = PU[i]
    if t <= t0:
        return base_falcon(i, t)
    k = (t - t0) / dt
    j = min(int(k), len(tab) - 2)
    u = k - j
    return tab[j][1] * (1 - u) + tab[j + 1][1] * u


# ------------------------------------------------------------------------------- actors
falcons = [P.load('falcon', label=f'falcon{i}') for i in range(2)]
F_H = falcons[0].entry['height']
for a in falcons:
    a.model_root.location.z = -F_H / 2
halo = P.load('halo', label='halo')
H_H = halo.entry['height']
halo.model_root.location.z = -H_H / 2

# Falcon local points (root space: +X nose, centred on the hull height). Gun pods at y=+-0.33.
ZC = -F_H / 2
GUN_Z = 0.515 + ZC
MUZ = [Vector((2.25, 0.33, GUN_Z)), Vector((2.25, -0.33, GUN_Z))]
ENG = Vector((-2.62, 0.0, 0.52 + ZC))
TIPS = [Vector((0.85, 1.78, 0.42 + ZC)), Vector((0.85, -1.78, 0.42 + ZC))]

halo_wobble = (lambda t: 0.0 if t < T_HIT1 else
               0.45 * math.sin((t - T_HIT1) * 9.0) * math.exp(-(t - T_HIT1) * 1.2))
fly(halo, halo_pos, bank_up(0.55, clamp=30), roll_extra=halo_wobble)
fly(falcons[0], lambda t: falcon_pos(0, t), bank_up(1.7, clamp=70))
fly(falcons[1], lambda t: falcon_pos(1, t), bank_up(1.7, clamp=70),
    roll_extra=lambda t: -2 * math.pi * ss((t - 4.85) / 0.8))

for i in range(2):
    print('falcon', i, 'T_PU', falcon_pos(i, T_PU), '4.7', falcon_pos(i, 4.7), '5.3', falcon_pos(i, 5.3),
          '6', falcon_pos(i, 6.0))
print('halo break', halo_pos(T_BREAK))

# halo blade ring spin
mr = halo.model_root
mr.rotation_mode = 'XYZ'
for f in range(0, NF + 2, 2):
    mr.rotation_euler.z = math.radians(-420.0 * (f - 1) / FPS)
    mr.keyframe_insert('rotation_euler', index=2, frame=f)
K.set_interp(mr, 'LINEAR')


# ------------------------------------------------------------------------------- barrels
def split_guns(actor):
    """Cut the two gun barrels off the hull mesh into their own objects so they can collapse."""
    host = actor.meshes[0]
    bpy.context.view_layer.update()
    # host -> model space (root-local, base on z=0, as when first loaded)
    mw = Matrix.Translation((0, 0, F_H / 2)) @ actor.root.matrix_world.inverted() @ host.matrix_world
    inv = mw.inverted()
    out = []
    for sgn in (1, -1):
        bm = bmesh.new()
        bm.from_mesh(host.data)
        sel = []
        for f in bm.faces:
            c = mw @ f.calc_center_median()
            if c.x > 1.72 and 0.27 < c.y * sgn < 0.4 and 0.44 < c.z < 0.6:
                sel.append(f)
        keep_idx = {f.index for f in sel}
        bm2 = bm.copy()
        bmesh.ops.delete(bm, geom=sel, context='FACES')
        bm.to_mesh(host.data)
        bm.free()
        bm2.faces.ensure_lookup_table()
        drop = [f for f in bm2.faces if f.index not in keep_idx]
        bmesh.ops.delete(bm2, geom=drop, context='FACES')
        me2 = bpy.data.meshes.new('FalconGun')
        bm2.to_mesh(me2)
        bm2.free()
        for m in host.data.materials:
            me2.materials.append(m)
        b = K.link(bpy.data.objects.new(actor.name + '_Gun', me2))
        b.parent = host
        xs = [(mw @ v.co).x for v in me2.vertices]
        L = max(xs) - min(xs)
        # local axis that maps to world -X (collapse direction), in host space
        ax = (inv.to_3x3() @ Vector((-1, 0, 0)))
        b['len_local'] = L / mw.to_3x3().to_scale()[0] if False else L
        b['ax'] = list(ax)
        out.append(b)
    actor.guns = out
    return out


for a in falcons:
    split_guns(a)
    print(a.name, 'guns', [len(b.data.vertices) for b in a.guns])


def recoil(actor, t, kick=2.5):
    """Barrels collapse 80% into the pods and slide back out; the airframe jolts nose-up."""
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


# ------------------------------------------------------------------------------- engines
def engine(actor, seed):
    core = K.sphere('EngCore', 1.0, M_ENG_HOT, seg=(10, 6))
    core.parent = actor.root
    core.location = ENG + Vector((-0.2, 0, 0))
    glow = K.sphere('EngGlow', 1.0, M_ENG_GLOW, seg=(12, 8))
    glow.parent = actor.root
    plume = K.sphere('EngPlume', 1.0, M_ENG, seg=(10, 6))
    plume.parent = actor.root
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        boost = 1.0 + 0.6 * ss((t - T_PU) / 0.4)
        fl = R.uniform(0.85, 1.15) * boost
        core.scale = (0.32, 0.26, 0.26)
        plume.location = ENG + Vector((-0.75 * fl, 0, 0))
        plume.scale = (0.75 * fl, 0.12, 0.12)
        glow.location = ENG + Vector((-0.6 * fl, 0, 0))
        glow.scale = (1.2 * fl, 0.42, 0.42)
        for o in (plume, glow):
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('scale', frame=f)
    core.keyframe_insert('scale', frame=1)


for i, a in enumerate(falcons):
    engine(a, i)


# ------------------------------------------------------------------------------- vapour trails
def vapor(actor):
    """Wingtip vapour streaks: shown while the jet pulls hard (bank / pull-up)."""
    hist = {}
    for f in range(0, NF + 2):
        hist[f] = [actor.mats[f] @ tp for tp in TIPS]
    dt = 1.0 / FPS
    for f in range(4, NF + 2):
        t = (f - 1) / FPS
        m = actor.mats[f]
        up = m.to_3x3() @ Vector((0, 0, 1))
        upv = up.normalized()
        # g-load ~ how far the back is tilted from vertical, or pull-up phase
        load = 1 - abs(upv.z)
        if t > T_PU:
            load = max(load, ss((t - T_PU) / 0.3) * (1 - ss((t - 5.6) / 0.4)))
        if load < 0.28:
            continue
        n = int(4 + 6 * min(1.0, load))
        for k in range(2):
            pts = [hist[max(0, f - j)][k] for j in range(n)]
            o = K.polyline('Vapor', pts, 0.03, M_VAPOR)
            K.show_between(o, f, f + 1)


for a in falcons:
    vapor(a)


# ------------------------------------------------------------------------------- halo thrusters
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


HZ = 0.0   # halo root is at the hull centre


def halo_thrust():
    for f in range(0, int(P.T(T_BREAK)) + 1):
        for sgn in (1, -1):
            if R.random() < 0.2:
                continue
            a = Vector((-1.6, 0.9 * sgn, HZ))
            b = a + Vector((-R.uniform(2.0, 3.4), sgn * R.uniform(0.0, 0.6), R.uniform(-0.4, 0.3)))
            bolt_frame(jag_pts(a, b, 6, 0.55), f, 0.04, parent=halo.root, core=False,
                       forks=1 if R.random() < 0.5 else 0)


halo_thrust()


# ------------------------------------------------------------------------------- effects
def sparks(pos, t, size, col_mat=M_SPARK, vel=Vector()):
    f0 = P.T(t)
    o = K.sphere('Hit', 1.0, P.soft_fire_mat(), seg=(12, 8))
    o.color = (*COL['laser_blue'], 1.0)
    o.location = pos
    for df_, s in ((0, 0.05), (1, 0.7 * size), (4, 0.01)):
        o.scale = (s, s, s)
        o.location = pos + vel * (df_ / FPS)
        o.keyframe_insert('scale', frame=f0 + df_)
        o.keyframe_insert('location', frame=f0 + df_)
    K.show_between(o, f0, f0 + 5)
    for _ in range(9):
        sp = K.sphere('Spk', 1.0, col_mat, seg=(6, 4))
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.6, 1))).normalized() * size * R.uniform(2.5, 4.5)
        sp.scale = (0.2 * size, 0.035 * size, 0.035 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = (v + vel * 0.3).to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + vel * 0.3 + Vector((0, 0, -0.3))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)
    P.light(pos, t, COL['laser_blue'], energy=2500 * size, dur=0.12, radius=0.5)


def laser_bolt(p0, p1, t0, speed=170.0, length=3.6):
    """Fast blue laser dart: bright core in a soft glow, flying p0 -> p1. Returns hit time."""
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


def ground_hit(p, t):
    """Laser strike on the canyon floor: blue spark + a little sandy dust kick."""
    sparks(p + Vector((0, 0, 0.2)), t, 0.8)
    P.puff(p, t + 0.02, size=1.1, n=2, rise=1.2, life=1.2,
           color=tuple(min(1, c * 1.6) for c in P.palette['g1']), opacity=0.45)


def burst(actor, t0, target_fn, miss=None, n=2, gap=0.09):
    """Twin-gun burst: both pods fire together, n shots. target_fn(t) -> world point."""
    for s in range(n):
        t = t0 + s * gap
        recoil(actor, t)
        for k in range(2):
            muzzle_flash(actor, t, k)
            p0 = W(actor, t, MUZ[k])
            if miss is None:
                tgt = target_fn(t + 0.1)
                # converge: both guns on the same point, slight spread
                p1 = tgt + Vector((R.uniform(-.3, .3), R.uniform(-.3, .3), R.uniform(-.2, .2)))
                th = laser_bolt(p0, p1, t)
                sparks(p1, th, 0.9, vel=(halo_pos(th + 0.05) - halo_pos(th - 0.05)) / 0.1)
            else:
                aim = target_fn(t + 0.1) + miss + Vector((0, (k - 0.5) * 0.8, 0))
                d = (aim - p0).normalized()
                # march along the ray to the ground
                q = p0.copy()
                for _ in range(200):
                    q = q + d * 0.5
                    if q.z <= P.ground_z(q.x, q.y) + 0.1 or (q - p0).length > 90:
                        break
                th = laser_bolt(p0, q, t)
                ground_hit(q, th)
        P.light(W(actor, t, Vector((2.4, 0, GUN_Z))), t, COL['laser_blue'], energy=1500, dur=0.08)


# 1) lead's first burst: the Halo jinks, the lasers rake the canyon floor beside it
burst(falcons[0], 2.05, halo_pos, miss=Vector((0, -3.2, -4.5)))
# 2) wingman connects: sparks on the ring
burst(falcons[1], T_HIT1 - 0.1, halo_pos)
# 3) lead's kill burst
burst(falcons[0], T_KILL - 0.09, halo_pos)


# Halo fights back: a gold bolt whips back over the Falcons and misses
def back_bolt(t, dur, target_fn):
    for f in range(int(round(P.T(t))), int(round(P.T(t + dur))) + 1):
        tt = (f - 1) / FPS
        p0 = W(halo, tt, Vector((-2.0, 0, 0.1)))
        p1 = target_fn(tt)
        ctrl = (p0 + p1) / 2 + Vector((0, 0, 3.0))
        bolt_frame(jag_pts(p0, p1, 14, 0.2, ctrl=ctrl), f, 0.045, forks=2)
    P.light(W(halo, t, Vector((-2.0, 0, 0))), t, COL['arc_gold'], energy=3500, dur=dur, radius=0.6)


back_bolt(2.3, 0.2, lambda t: falcon_pos(1, t) + Vector((-6.0, 3.5, 2.8)))
back_bolt(3.05, 0.16, lambda t: falcon_pos(0, t) + Vector((-7.0, -2.5, 3.5)))


# wounded halo: smoke and flame from the hit
def halo_smoke():
    fl = K.ico('HaloFire', 1.0, M_FLAME, sub=2)
    fl.parent = halo.root
    fl.location = (-0.6, 0.8, 0.25)
    for f in range(int(P.T(T_HIT1)), int(P.T(T_BREAK)) + 2):
        s = R.uniform(0.35, 0.55) * min(1.0, (f - P.T(T_HIT1)) / 3 + 0.3)
        fl.scale = (s * 1.8, s, s)
        fl.keyframe_insert('scale', frame=f)
    K.show_between(fl, P.T(T_HIT1), P.T(T_BREAK) + 1)
    t = T_HIT1 + 0.04
    while t < T_BREAK:
        P.puff(W(halo, t, Vector((-0.8, 0.8, 0.3))), t, size=1.1, n=1, rise=0.8, life=1.5,
               color=(0.1, 0.09, 0.085), opacity=0.55)
        t += 0.06


halo_smoke()

# ------------------------------------------------------------------------------- break-up
HV = (halo_pos(T_BREAK + 0.02) - halo_pos(T_BREAK - 0.02)) / 0.04
_before = set(bpy.data.objects)
P.explosion(halo_pos(T_BREAK), T_BREAK, size=1.6, debris=16, smoke=False)
for o in set(bpy.data.objects) - _before:
    if o.name.startswith('Scorch'):
        bpy.data.objects.remove(o)
P.light(halo_pos(T_BREAK), T_BREAK, (1.0, 0.45, 0.1), energy=12000, dur=0.35, radius=2)
M_BURST = K.emit_mat('BreakFire', (1.0, 0.15, 0.01), 1.6)
M_BURST2 = K.emit_mat('BreakFireHot', (1.0, 0.32, 0.03), 2.2)
for k in range(6):
    o = K.ico('BreakFire', 1.0, M_BURST2 if k < 2 else M_BURST, sub=2)
    c0 = halo_pos(T_BREAK) + Vector((R.uniform(-1.5, 1.5), R.uniform(-1.5, 1.5), R.uniform(-0.4, 0.6)))
    f0 = P.T(T_BREAK + k * 0.02)
    o.rotation_euler = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    sz = R.uniform(0.8, 1.3)
    for df_, sc_, dp in ((0, 0.1, 0), (3, sz, 0.15), (9, sz * 0.8, 0.5), (14, 0.05, 0.9)):
        o.location = c0 + HV * 0.6 * (df_ / FPS) + Vector((0, 0, dp))
        o.scale = (sc_ * 1.3, sc_, sc_)
        o.keyframe_insert('location', frame=f0 + df_)
        o.keyframe_insert('scale', frame=f0 + df_)
    K.show_between(o, f0, f0 + 14)
P.puff(halo_pos(T_BREAK), T_BREAK + 0.1, size=2.2, n=3, rise=2.0, life=2.0, color=(0.1, 0.09, 0.085), opacity=0.5)
halo.vanish(T_BREAK + 1 / FPS)

mb = halo.mats[int(round(P.T(T_BREAK)))]
CRASH = []


def piece(name, keep, spin, vel, fire_at):
    root = K.empty('HaloPiece_' + name)
    root.rotation_mode = 'QUATERNION'
    rinv = halo.mats[1].inverted()
    bpy.context.scene.frame_set(1)
    for m in halo.meshes:
        me = m.data.copy()
        me.transform(rinv @ m.matrix_world)
        bm = bmesh.new()
        bm.from_mesh(me)
        for (co, no) in keep:
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
        bm.to_mesh(me)
        bm.free()
        o = K.link(bpy.data.objects.new('HPiece', me))
        o.parent = root
    fl = K.ico('PieceFire', 1.0, M_FLAME, sub=2)
    fl.parent = root
    fl.location = fire_at
    p = mb.translation.copy()
    q0 = mb.to_quaternion()
    v = HV * 0.7 + vel
    prev = None
    landed = None
    for f in range(int(P.T(T_BREAK)), NF + 2):
        t = (f - 1) / FPS - T_BREAK
        if landed is None:
            pp = mb.translation + v * t + Vector((0, 0, -0.5 * 15.0 * t * t))
            gz = P.ground_z(pp.x, pp.y) + 0.3
            if pp.z <= gz:
                landed = (f, Vector((pp.x, pp.y, gz)))
                CRASH.append((T_BREAK + t, landed[1]))
            else:
                p = pp
                q = q0 @ (Matrix.Rotation(spin[0] * t, 3, 'X') @ Matrix.Rotation(spin[1] * t, 3, 'Y')).to_quaternion()
                if prev is not None:
                    q.make_compatible(prev)
                prev = q
                root.location = p
                root.rotation_quaternion = q
                root.keyframe_insert('location', frame=f)
                root.keyframe_insert('rotation_quaternion', frame=f)
                s = R.uniform(0.35, 0.55)
                fl.scale = (s * 1.8, s, s)
                fl.keyframe_insert('scale', frame=f)
                if f % 2 == 0:
                    wp_ = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Vector(fire_at)
                    P.puff(wp_, (f - 1) / FPS, size=1.5, n=1, rise=1.0, life=1.6, color=(0.09, 0.08, 0.075), opacity=0.6)
    K.set_interp(root, 'LINEAR')
    for o in [root] + list(root.children_recursive):
        K.key_hide(o, 0, True)
        K.key_hide(o, P.T(T_BREAK) + 1, False)
        if landed:
            K.key_hide(o, landed[0], True)


piece('L', [(Vector((0, 0, 0)), Vector((0, -1, 0)))], spin=(2.4, 1.1), vel=Vector((0, 4.0, -3.0)),
      fire_at=Vector((0, 0.4, 0.2)))
piece('R', [(Vector((0, 0, 0)), Vector((0, 1, 0)))], spin=(-3.0, -0.8), vel=Vector((-3.0, -3.5, -3.5)),
      fire_at=Vector((0, -0.4, 0.2)))
print('crash', CRASH)
for t, p in CRASH:
    P.explosion(p, t, size=3.2, debris=14)
    P.fire_patch(p + Vector((0, 0, 0.3)), t + 0.15, 6.0, size=1.0)
    P.smoke_column(p, t + 0.3, 6.0, size=1.6, every=0.22)

# ------------------------------------------------------------------------------- camera
T_C1 = 1.6
T_C2 = 4.3
T_PASS = 5.3
keys = []


def pair(t):
    return (falcon_pos(0, t) + falcon_pos(1, t)) / 2


# shot A: off to the side on the canyon floor; the Halo then the Falcons rip past (pan)
CA = Vector((-62.0, cy(-62.0) - 6.0, 1.8))
keys += [
    (0.0, tuple(CA), halo_pos(0.0) * 0.6 + pair(0.0) * 0.4 + Vector((0, 0, 1)), 34),
    (0.6, tuple(CA + Vector((0.8, 0, 0))), halo_pos(0.6) * 0.7 + pair(0.6) * 0.3, 30),
    (1.1, tuple(CA + Vector((1.6, 0.3, 0.1))), halo_pos(1.1) * 0.55 + pair(1.1) * 0.45, 24),
    (T_C1 - 1 / FPS, tuple(CA + Vector((2.4, 0.6, 0.2))), halo_pos(1.55) * 0.4 + pair(1.55) * 0.6, 28),
]


# shot B: chase camera behind and above the pair
def heading(x):
    d = Vector((1.0, (cy(x + 1) - cy(x - 1)) / 2, 0)).normalized()
    return d


def chase(t):
    lead = falcon_pos(0, t)
    h = heading(lead.x)
    side = Vector((-h.y, h.x, 0))
    back = 15.0 - 2.5 * ss((t - 2.6) / 1.0)
    cpos = lead - h * back + side * 4.5 + Vector((0, 0, 4.6))
    tgt = halo_pos(min(t, T_BREAK)) * 0.65 + lead * 0.35 + Vector((0, 0, -0.8)) - side * 1.0
    if t > T_BREAK:
        tgt = tgt + Vector((0, 0, -2.5 * ss((t - T_BREAK) / 0.4)))
    return cpos, tgt


t = T_C1
while t < T_C2 - 0.05:
    cpos, tgt = chase(t)
    keys.append((t, tuple(cpos), tgt, 31))
    t += 0.25
cpos, tgt = chase(T_C2 - 1 / FPS)
keys.append((T_C2 - 1 / FPS, tuple(cpos), tgt, 31))

# shot C: camera hangs in the air beyond the crash; the pair hauls up out of the smoke and
# screams just over the lens, then the camera whips round to watch them climb away
crash_c = sum((p for _, p in CRASH), Vector()) / max(1, len(CRASH)) if CRASH else Vector((40, cy(40), 0))
pp = pair(T_PASS)
hp = heading(pp.x)
sp = Vector((-hp.y, hp.x, 0))
CC = pp + sp * 4.5 + Vector((0, 0, -3.8))
keys += [
    (T_C2, tuple(CC), crash_c * 0.55 + pair(T_C2) * 0.45 + Vector((0, 0, 1.5)), 26),
    (4.8, tuple(CC + hp * 0.3), crash_c * 0.4 + pair(4.8) * 0.6 + Vector((0, 0, 1.0)), 26),
    (5.15, tuple(CC + hp * 0.6), pair(5.15), 24),
    (5.45, tuple(CC + hp * 1.2 + Vector((0, 0, 0.4))), pair(5.5) + hp * 4.0, 24),
    (5.7, tuple(CC + hp * 2.5 + Vector((0, 0, 5.0))), pair(5.75), 30),
    (6.0, tuple(pair(6.0) - hp * 17.0 - sp * 3.0 + Vector((0, 0, -3.5))), pair(6.0) + hp * 1.0 + Vector((0, 0, -0.6)), 36),
]
print('crash centre', crash_c, 'camC', CC, 'pair pass', pp, 'pair 6', pair(6.0))
P.camera(keys, shake=0.03, cuts=(T_C1, T_C2))
for tt in (2.05, 2.14, T_HIT1 - 0.1, T_HIT1, T_KILL - 0.09, T_KILL):
    P.cam_shake(tt, 0.05, dur=0.12)
P.cam_shake(T_BREAK, 0.25, dur=0.4)
for tt, _ in CRASH:
    P.cam_shake(tt, 0.3, dur=0.45)
P.cam_shake(T_PASS, 0.2, dur=0.5)   # jet wash as the pair goes over

# effects never cast shadows
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.active_material is not None:
        m = o.active_material
        if 'emit_node' in m or m.name.startswith(('SoftFire', 'Fireball')):
            o.visible_shadow = False

P.render()
