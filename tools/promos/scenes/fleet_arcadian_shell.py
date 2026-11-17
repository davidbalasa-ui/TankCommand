"""Arcadian Shell mothership (space): the nautilus Shell turns slowly over a blue planet, gold
current crawling along its whorls. Lightning runs along its seam and the two halves of the
shell part, gold light spilling out of the opening. One after another four Stingrays burst out
of the slit on crackling lightning thrusters, then an Orb uncoils out after them, tentacles
whipping. The swarm peels away over the planet while the Shell hangs open behind it.

Timeline (s): 0-2.25 high 3/4 over the Shell, seam crackles from 1.3, the halves part 1.6-2.6 |
2.25-4.0 close over the glowing slit: Stingrays launch 2.45 / 2.7 / 2.95 / 3.2, the Orb 3.45 |
4.0-6.0 among the swarm as it peels away, the open Shell and the planet behind.

Built at ~0.3x game scale (Shell 114 m); the fighters are nudged up (Stingray 6 m, Orb 11 m) so
they read at phone size."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as WFX  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_arcadian_shell', seconds=6.0, seed=71)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']



def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


def V(*a):
    return Vector(a)


def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def spline(keys):
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


def key_mats(actor, matf):
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        m = matf(t)
        q = m.to_quaternion()
        if prev_q is not None:
            q.make_compatible(prev_q)
        prev_q = q
        r.location = m.translation
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.LocRotScale(m.translation, q, None)
    K.set_interp(r, 'LINEAR')
    actor.mats = mats
    return mats


def fly_mat(posf, up=V(0, 0, 1)):
    dt = 1.0 / FPS

    def m(t):
        p = posf(t)
        v = posf(t + dt * 0.5) - posf(t - dt * 0.5)
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        vn = v.normalized()
        lat = a - vn * a.dot(vn)
        u = (up * 9.8 + lat * 0.8).normalized()
        return Matrix.Translation(p) @ frame_from(v, u).to_4x4()
    return m


def W(actor, t, local=(0, 0, 0)):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 54 / 24, 96 / 24            # 2.25, 4.0
T_SEAM, T_OPEN0, T_OPEN1 = 1.3, 1.6, 2.6
T_RAYS = (2.45, 2.7, 2.95, 3.2)
T_ORB = 3.45

# ------------------------------------------------------------------------------- the Shell
shell = P.load('arcadian_shell', size=114.0, label='shell')
bpy.context.view_layer.update()
hull = max(shell.meshes, key=lambda o: len(o.data.polygons))
SM = shell.root.matrix_world.inverted() @ hull.matrix_world


def sl(x, y, z):
    return SM @ Vector((x, y, z))


_S3 = SM.to_3x3()
_XM0 = (_S3 @ V(1, 0, 0)).normalized()
_F0 = ((_S3 @ V(0, 0, 1)).normalized() * 0.75 + (_S3 @ V(0, 1, 0)).normalized() * 0.6 + _XM0 * 0.15).normalized()
_pc = -_F0 * 1700 + V(0, 0, -250)
P.space(planet=(_pc.x, _pc.y, _pc.z, 800, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(55, 0, 120), sun_energy=4.0)
XM = (_S3 @ V(1, 0, 0)).normalized()
NM = (_S3 @ V(0, 1, 0)).normalized()      # seam normal: the halves part along this
ZM = (_S3 @ V(0, 0, 1)).normalized()
FWD = (ZM * 0.75 + NM * 0.6 + XM * 0.15).normalized()


def shell_mat(t):
    yaw = math.radians(lerp(-14, 4, t / 6.0))
    roll = math.radians(3) * math.sin(0.5 * t)
    return Matrix.Translation(V(0, 0, 0)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(roll, 4, 'X')


key_mats(shell, shell_mat)

# recolour + strip the baked static bolts
SHELL_RECOL = {
    'zone_shell': ((0.80, 0.78, 0.74), (0.52, 0.40, 0.26)),
    'zone_pale': ((0.86, 0.84, 0.80), (0.60, 0.50, 0.36)),
    'zone_bronze': ((0.58, 0.40, 0.20), (0.40, 0.26, 0.12)),
}


def arcadian_look(meshes, arc_flicker=True):
    seen = set()
    arcs = []
    for o in meshes:
        me = o.data
        bi = [i for i, m in enumerate(me.materials) if m and m.name.split('.')[0] == 'zone_bolt']
        if bi:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bi], context='FACES')
            bm.to_mesh(me)
            bm.free()
        for m in me.materials:
            if not m or m in seen or not m.node_tree:
                continue
            seen.add(m)
            base = m.name.split('.')[0]
            for n in m.node_tree.nodes:
                if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and base in SHELL_RECOL:
                    a, b = SHELL_RECOL[base]
                    ia, ib = n.inputs[6], n.inputs[7]
                    if not ia.is_linked and ia.default_value[0] > 0.2:
                        ia.default_value = (*a, 1)
                    if not ib.is_linked and ib.default_value[0] > 0.2:
                        ib.default_value = (*b, 1)
                if n.type == 'BSDF_PRINCIPLED' and base != 'zone_core':
                    n.inputs['Emission Color'].default_value = (*GOLD, 1)
                    if base == 'zone_glow':
                        n.inputs['Emission Strength'].default_value = 2.2
                    if base == 'zone_arc':
                        arcs.append(n)
    if arc_flicker:
        for n in arcs:
            sock = n.inputs['Emission Strength']
            for f in range(1, NF + 2):
                sock.default_value = R.choice((0.6, 1.2, 2.0, 2.6))
                sock.keyframe_insert('default_value', frame=f)


arcadian_look(shell.meshes)

# split into two halves along the seam (y = 0) and part them
me = hull.data
bm = bmesh.new()
bm.from_mesh(me)
b2 = bm.copy()
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < 0], context='FACES')
bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.calc_center_median().y >= 0], context='FACES')
me2 = bpy.data.meshes.new('ShellHalfB')
b2.to_mesh(me2)
b2.free()
bm.to_mesh(me)
bm.free()
for m in me.materials:
    me2.materials.append(m)
halfB = K.link(bpy.data.objects.new('ShellHalfB', me2))
halfB.parent = hull.parent
halfB.matrix_parent_inverse = hull.matrix_parent_inverse.copy()
halfB.matrix_basis = hull.matrix_basis.copy()
shell.meshes.append(halfB)
GAP = 5.5      # file units each side (~7.4 m)
for o, sgn in ((hull, 1), (halfB, -1)):
    base = o.location.copy()
    base_r = o.rotation_euler.copy()
    o.rotation_mode = 'XYZ'
    for f in (P.T(T_OPEN0), P.T(T_OPEN1)):
        u = 1.0 if f > P.T(T_OPEN0) else 0.0
        o.location = base + V(0, sgn * GAP * u, 0)
        o.rotation_euler = (base_r.x + sgn * math.radians(5) * u, base_r.y, base_r.z)
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_euler', frame=f)
    # a small settle wobble after it opens
    o.location = base + V(0, sgn * GAP * 1.08, 0)
    o.keyframe_insert('location', frame=P.T(T_OPEN1) + 4)
    o.location = base + V(0, sgn * GAP, 0)
    o.keyframe_insert('location', frame=P.T(T_OPEN1) + 10)

# inner light spilling out of the opening
Lin = P.light(V(0, 0, 0), 0.0, GOLD, energy=0, dur=0.1)
Lin.parent = shell.root
Lin.location = sl(-6, 0, 18)
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    Lin.data.energy = 1.2e5 * ss((t - T_OPEN0) / (T_OPEN1 - T_OPEN0)) * R.uniform(0.8, 1.0)
    Lin.data.keyframe_insert('energy', frame=f)


def attach_local(parent, fn):
    before = set(bpy.data.objects)
    fn()
    for o in bpy.data.objects:
        if o not in before and o.parent is None and not o.name.startswith('FxBoltLight'):
            o.parent = parent
            o.matrix_parent_inverse = Matrix()


# lightning running along the seam (both rims) as it unlocks, crackling on while open
SEAM = [sl(x, 0, z) for x, z in ((-30, 4), (-26, 13), (-17, 17), (-6, 15), (2, 9), (6, 0), (2, -9), (-8, -14),
                                  (-20, -12), (-27, -4))]


def seam_bolts():
    t = T_SEAM
    k = 0
    while t < 6.0:
        a = SEAM[k % len(SEAM)]
        b = SEAM[(k + 1) % len(SEAM)]
        du = R.uniform(0.1, 0.2)
        WFX.lightning(P, a, b, t, t + du, color=GOLD, width=0.35, jag=0.25, branches=1, segs=8,
                      light=False, sparks_=False)
        t += R.uniform(0.05, 0.12) if t < T_OPEN1 + 0.3 else R.uniform(0.2, 0.35)
        k += R.choice((1, 2, 3))


attach_local(shell.root, seam_bolts)
P.sfx(T_SEAM, 'zap_lightning', gain=0.8)
P.sfx(T_SEAM, 'crackle_loop', gain=0.6, dur=T_OPEN1 - T_SEAM + 0.5)
P.sfx(T_OPEN0, 'hydraulic', gain=0.9)
P.sfx(T_OPEN0 + 0.1, 'power_up_arc', gain=0.8)
P.sfx(T_OPEN1, 'mech_clunk', gain=0.6)

# ------------------------------------------------------------------------------- the swarm
RAY = 6.0
rk = RAY / 10.0
RAY_TRAIL = [V(-1.2, 0.9, -0.35) * rk, V(-1.2, -0.9, -0.35) * rk]


def W_shell(t, local):
    return W(shell, t, local)


LAUNCH = [sl(-22, 0, 15), sl(-12, 0, 17), sl(-2, 0, 13), sl(-17, 0, 16.5)]
_c0 = sl(-12, 0, 18)
form_c = spline([(2.4, tuple(_c0 + ZM * 22)), (3.4, tuple(_c0 + ZM * 40 + FWD * 30)), (4.4, tuple(_c0 + ZM * 40 + FWD * 90)),
                 (6.0, tuple(_c0 + ZM * 40 + FWD * 185)), (6.8, tuple(_c0 + ZM * 40 + FWD * 230))])
_sd = FWD.cross(ZM).normalized()
_up = _sd.cross(FWD).normalized()
SLOT = [V(0, 0, 0), _sd * -13 - FWD * 9 - _up * 2, _sd * 12 - FWD * 8 + _up * 2, -FWD * 19 - _up * 6]
rays = []
for i, tl in enumerate(T_RAYS):
    s0 = W_shell(tl, LAUNCH[i])
    up_ = spline([
        (tl - 0.6, tuple(s0 - ZM * 18)),
        (tl - 0.2, tuple(s0 - ZM * 6)),
        (tl, tuple(s0)),
        (tl + 0.5, tuple(s0 + ZM * 16 + NM * 3)),
        (tl + 1.0, tuple(s0 + ZM * 30 + FWD * 14)),
    ])

    def posf(t, up_=up_, tl=tl, i=i):
        u = ss((t - tl - 0.35) / 0.9)
        a = up_(min(t, tl + 1.0)) + (up_(tl + 1.0) - up_(tl + 0.99)) * 100 * max(0.0, t - tl - 1.0)
        return a.lerp(form_c(t) + SLOT[i], u)
    r_ = P.load('arcadian_stingray', size=RAY, label=f'ray{i}')
    key_mats(r_, fly_mat(posf))
    r_.posf = posf
    r_.appear(tl - 0.15)
    rays.append(r_)

    def thr(r_=r_, tl=tl):
        for p in RAY_TRAIL:
            t = tl - 0.15
            while t < 6.0:
                du = R.uniform(0.25, 0.4)
                boost = 1.6 if t < tl + 0.8 else 1.0
                end = p + V(-1, 0.25 * p.y, -0.05).normalized() * 4.0 * boost * R.uniform(0.75, 1.1)
                WFX.lightning(P, p, end, t, t + du, color=GOLD, width=0.05, jag=0.22, branches=1, segs=8,
                              light=False, sparks_=False)
                t += du
    attach_local(r_.root, thr)
    P.sfx(tl - 0.05, 'whoosh', gain=0.8, pos=s0)
    P.sfx(tl - 0.05, 'zap_small', gain=0.6, pos=s0)
arcadian_look([o for r_ in rays for o in r_.meshes], arc_flicker=False)

# The Orb: its own file carries a baked sample of its leg physics and flight along +X; it is
# aimed out of the slit so it uncoils out after the rays.
orb = P.load('arcadian_orb', size=14.0, label='orb')
OB = bpy.data.objects['Orb']
ORB_K = 11.0 / 14.0
orb.model_root.scale = (ORB_K,) * 3
F_BAKE0 = 20                            # baked frame at which the Orb leaves the slit
sc = bpy.context.scene
sc.frame_set(F_BAKE0)
bpy.context.view_layer.update()
orb.root.matrix_world = Matrix()
bpy.context.view_layer.update()
p_bake = OB.matrix_world.translation.copy()
o0 = W_shell(T_ORB, sl(-8, 0, 16))
dir_out = (ZM * 0.4 + FWD * 0.9).normalized()
Rq = V(1, 0, 0).rotation_difference(dir_out)
orb.root.rotation_mode = 'QUATERNION'
orb.root.rotation_quaternion = Rq
orb.root.location = o0 - Rq @ p_bake
# extra drift so the Orb keeps up with the swarm (the baked sample flies slower)
_base = orb.root.location.copy()
for f in range(int(P.T(T_ORB)) - 2, NF + 2):
    t = (f - 1) / FPS
    orb.root.location = _base + FWD * 34.0 * max(0.0, t - T_ORB) ** 1.15
    orb.root.keyframe_insert('location', frame=f)
# shift the baked clip so its frame F_BAKE0 lands at T_ORB
off = P.T(T_ORB) - F_BAKE0
for o in [OB] + list(OB.children_recursive):
    ad = o.animation_data
    if ad and ad.action:
        for fc in K._fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.co.x += off
                kp.handle_left.x += off
                kp.handle_right.x += off
orb.appear(T_ORB - 0.1)
arcadian_look([o for o in orb.meshes], arc_flicker=False)
for m in bpy.data.materials:
    if m.name.split('.')[0] == 'OrbBoltCoreM' and m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == 'EMISSION':
                n.inputs['Strength'].default_value = 3.0
P.sfx(T_ORB, 'whoosh', gain=0.9, pos=o0)
P.sfx(T_ORB, 'servo', gain=0.5, pos=o0)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2000, box=((-150, 300), (-150, 350), (-80, 160)), size=0.12, avoid=()):
    me_ = bpy.data.meshes.new('SpaceDust')
    b = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        if any((c - q).length < 8.0 for q in avoid) or c.length < 60:
            continue
        s = size * R.uniform(0.6, 1.4)
        r = bmesh.ops.create_icosphere(b, subdivisions=0, radius=s)
        bmesh.ops.translate(b, verts=r['verts'], vec=c)
    b.to_mesh(me_)
    b.free()
    o = K.link(bpy.data.objects.new('SpaceDust', me_))
    me_.materials.append(K.emit_mat('DustGlint', (0.55, 0.6, 0.75), 1.2))
    o.visible_shadow = False
    return o


# ------------------------------------------------------------------------------- camera
def cam_keys():
    keys = []

    def shot(t0, t1, n, fn, last=True):
        for i in range(n + 1):
            t_ = t0 + (t1 - t0) * i / n
            if i == n and last:
                t_ = t1 - 1 / FPS
            keys.append((t_,) + fn(t_, (t_ - t0) / (t1 - t0)))

    # 1: high 3/4 over the Shell, slow push as the seam crackles and the halves part
    def s1f(t_, u):
        c = sl(-10, 0, 0)
        pos = c + NM * lerp(105, 90, ss(u)) + ZM * lerp(85, 72, ss(u)) + XM * 25
        look = c + ZM * lerp(0, 6, ss(u))
        return pos, look, 30

    shot(0, CUT1, 10, s1f)

    # 2: close over the glowing slit, the fighters bursting out past the lens
    def s2f(t_, u):
        c = sl(-10, 0, 16)
        pos = c + ZM * lerp(48, 44, ss(u)) + NM * lerp(30, 26, ss(u)) + XM * lerp(38, 32, ss(u))
        look = c + ZM * lerp(4, 18, ss(u)) + FWD * lerp(0, 8, ss(u))
        return pos, look, 26

    shot(CUT1, CUT2, 10, s2f)

    # 3: among the swarm as it peels away: the open Shell and the planet behind
    def s3f(t_, u):
        c = form_c(t_)
        side = _sd
        pos = c + FWD * lerp(20, 14, ss(u)) + side * lerp(10, 7, ss(u)) + _up * lerp(5, 3.5, ss(u))
        look = c.lerp(V(0, 0, 0), lerp(0.1, 0.14, ss(u))) - FWD * 8
        return pos, look, lerp(24, 24, ss(u))

    shot(CUT2, 6.0, 12, s3f, last=False)
    return keys


P.camera(cam_keys(), lens=30, cuts=(CUT1, CUT2))
_cam_path = []
for _f in range(1, NF + 1):
    bpy.context.scene.frame_set(_f)
    _cam_path.append(P.cam.matrix_world.translation.copy())
dust_field(avoid=_cam_path)

print('launch', [W_shell(t, LAUNCH[i]) for i, t in enumerate(T_RAYS)], 'orb', o0)
P.render()
