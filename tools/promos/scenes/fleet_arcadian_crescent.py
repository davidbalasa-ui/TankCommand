"""Arcadian Crescent mothership (space): the vast Crescent hangs in front of a blue planet,
turning slowly, gold lightning crackling between the fins along its back and streaming from
its tail. A Terran frigate slides across its bow and ripple-fires four missiles. The Crescent
completes its turn; gold lightning leaps from its horns and swats the missiles one by one in
mid-flight while the core between the horns charges. Then it unleashes the storm: bolt after
bolt from both horns and the core rakes the frigate, faster and faster, until it bursts and
its pieces drift off. The camera ends close on the Crescent's mouth, the core still crackling,
debris tumbling past.

Timeline (s): 0-2.25 behind the frigate, the Crescent turning against the planet; missiles
launch 1.2-1.56 | 2.25-3.75 beside the Crescent's horn: missiles swatted 2.55 / 2.75 / 2.95 /
3.15, core charges, first storm bolts 3.45 | 3.75-6.0 low beside the frigate looking back up
the storm, frigate bursts 4.95, camera drifts back toward the Crescent.

Built at ~1/3 game scale like the other fleet clips (Crescent 160 m, frigate 36 m)."""
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

P = Promo('fleet_arcadian_crescent', seconds=6.0, seed=29)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

P.space(planet=(-1400, 300, -700, 900, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(60, 0, 25), sun_energy=4.0)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


def V(*a):
    return Vector(a)


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


def W(actor, t, local=(0, 0, 0)):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 54 / 24, 90 / 24          # 2.25, 3.75
T_MIS = (1.2, 1.32, 1.44, 1.56)
T_SWAT = (2.55, 2.75, 2.95, 3.15)
T_STORM0, T_KILL = 3.45, 4.95

# ------------------------------------------------------------------------------- the Crescent
CR = 160.0
cres = P.load('arcadian_crescent', size=CR, label='crescent')
bpy.context.view_layer.update()
_hull0 = max(cres.meshes, key=lambda o: len(o.data.polygons))
CINNER = cres.root.matrix_world.inverted() @ _hull0.matrix_world   # mesh coords -> root-local metres
CK = CINNER.to_scale().x


def cl(x, y, z):
    """Crescent model-space point (file units) -> root-local metres."""
    return CINNER @ Vector((x, y, z))


def cres_mat(t):
    yaw = math.radians(lerp(48, -4, ss(t / 3.6)))
    roll = math.radians(4) * math.sin(0.6 * t + 0.4)
    pitch = math.radians(lerp(-3, 2, ss(t / 6)))
    p = V(0, 0, 0) + V(1.5, 0, 0) * t
    return Matrix.Translation(p) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'Y') @ Matrix.Rotation(roll, 4, 'X')


key_mats(cres, cres_mat)

# Scene-only: strip the baked static bolts (they become live kit lightning) and recolour the
# hull etched silver-bronze with gold glow.
SHELL_RECOL = {
    'zone_shell': ((0.80, 0.78, 0.74), (0.52, 0.40, 0.26)),
    'zone_pale': ((0.86, 0.84, 0.80), (0.60, 0.50, 0.36)),
    'zone_bronze': ((0.58, 0.40, 0.20), (0.40, 0.26, 0.12)),
}
hull = max(cres.meshes, key=lambda o: len(o.data.polygons))
me = hull.data
bolt_idx = [i for i, m in enumerate(me.materials) if m and m.name.split('.')[0] == 'zone_bolt']
bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bolt_idx], context='FACES')
bm.to_mesh(me)
bm.free()
ARC_MATS = []
for m in me.materials:
    if not m or not m.node_tree:
        continue
    base = m.name.split('.')[0]
    for n in m.node_tree.nodes:
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and base in SHELL_RECOL:
            a, b = SHELL_RECOL[base]
            ia, ib = n.inputs[6], n.inputs[7]
            if not ia.is_linked and ia.default_value[0] > 0.2:
                ia.default_value = (*a, 1)
            if not ib.is_linked and ib.default_value[0] > 0.2:
                ib.default_value = (*b, 1)
        if n.type == 'BSDF_PRINCIPLED':
            if base in SHELL_RECOL or base in ('zone_under', 'zone_slat'):
                n.inputs['Emission Color'].default_value = (*GOLD, 1)
            if base == 'zone_glow':
                n.inputs['Emission Color'].default_value = (*GOLD, 1)
                n.inputs['Emission Strength'].default_value = 2.2
            if base == 'zone_arc':
                n.inputs['Emission Color'].default_value = (*GOLD, 1)
                ARC_MATS.append(n)
    if base == 'zone_core':
        CORE_MAT = m

# zone_arc filaments flicker like live current (strength keyed per frame)
for n in ARC_MATS:
    sock = n.inputs['Emission Strength']
    for f in range(1, NF + 2):
        sock.default_value = R.choice((0.6, 1.2, 2.0, 2.8)) * (1.4 if (f - 1) / FPS > T_STORM0 else 1.0)
        sock.keyframe_insert('default_value', frame=f)

# core: charge glow sphere over the core between the horns
CORE = cl(13.7, 0, 0)
core_glow = WFX.glow(P, 'CoreCharge', GOLD, loc=(0, 0, 0), scale=(1, 1, 1), fx_e=0.0, fx_p=2.0, fx_hot=0.7)
core_glow.parent = cres.root
core_glow.location = CORE
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    ch = ss((t - 2.3) / 1.1)
    e = 0.2 + 1.3 * ch * R.uniform(0.75, 1.0)
    if t > T_KILL + 0.2:
        e *= max(0.45, 1 - (t - T_KILL - 0.2) * 0.6)
    WFX.kprop(core_glow, 'fx_e', f, e, const=True)
    s = 7.0 + 5.0 * ch + R.uniform(-0.5, 0.5)
    core_glow.scale = (s, s, s)
    core_glow.keyframe_insert('scale', frame=f)
cl_light = P.light(V(0, 0, 0), 0.0, GOLD, energy=0, dur=0.1)
cl_light.parent = cres.root
cl_light.location = CORE + V(6, 0, 0)
d = cl_light.data
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    d.energy = 1.5e5 * ss((t - 2.3) / 1.1) * R.uniform(0.7, 1.0)
    d.keyframe_insert('energy', frame=f)

HORNS = [cl(15.0, 13.4, 1.0), cl(15.0, -13.4, 1.0)]
FINS = [cl(-20, 0, 13.4), cl(-11, 14.6, 10.8), cl(-11, -14.6, 10.8), cl(5.5, 16.2, 9.5),
        cl(5.5, -16.2, 9.5), cl(-14, 12, 11.0), cl(-14, -12, 11.0)]
FIN_PAIRS = [(0, 1), (0, 2), (1, 3), (2, 4), (5, 1), (6, 2), (0, 5), (0, 6)]


def cw(local):
    return lambda t: W(cres, t, local)


def attach_local(fn):
    """Build bolts at root-local points (static), then hang them on the Crescent: cheap, no
    per-frame scene evaluation. No lights (the shared bolt lights stay unparented)."""
    before = set(bpy.data.objects)
    fn()
    for o in bpy.data.objects:
        if o not in before and o.parent is None and not o.name.startswith('FxBoltLight'):
            o.parent = cres.root
            o.matrix_parent_inverse = Matrix()


def fin_crackle():
    t = 0.05
    while t < 6.0:
        a, b = FIN_PAIRS[R.randrange(len(FIN_PAIRS))]
        du = R.uniform(0.08, 0.16)
        WFX.lightning(P, FINS[a], FINS[b], t, t + du, color=GOLD, width=0.3, jag=0.25, branches=1,
                      segs=10, light=False, sparks_=False)
        t += R.uniform(0.16, 0.3)


def tail_thrust():
    for loc, ax, ln in ((cl(-35, 0, 0), (-1, 0, 0), 34.0), (cl(-22, 9, 3), (-1, 0.25, 0.1), 22.0),
                        (cl(-22, -9, 3), (-1, -0.25, 0.1), 22.0), (cl(-18, 15, 1), (-1, 0.5, 0), 18.0),
                        (cl(-18, -15, 1), (-1, -0.5, 0), 18.0)):
        ax = Vector(ax).normalized()
        for k in range(2):
            t = 0.0 + k * 0.04
            while t < 6.0:
                du = R.uniform(0.35, 0.6)
                end = loc + (ax + Vector((0, R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3)))).normalized() * ln * R.uniform(0.6, 1.1)
                WFX.lightning(P, loc, end, t, t + du, color=GOLD, width=0.28, jag=0.22, branches=1, segs=8,
                              light=False, sparks_=False)
                t += du


attach_local(fin_crackle)
attach_local(tail_thrust)
P.sfx(0.0, 'crackle_loop', gain=0.35, dur=6.0)

# ------------------------------------------------------------------------------- the frigate
FR = 36.0
frig = P.load('terran_frigate', size=FR, label='frigate')
FK = frig.model_root.children[0].scale.x


def terran_glow(actor):
    seen = set()
    for o in actor.meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m in seen or not m.node_tree:
                continue
            seen.add(m)
            for n in m.node_tree.nodes:
                if n.type == 'EMISSION':
                    sock = n.inputs['Color']
                elif n.type == 'BSDF_PRINCIPLED':
                    sock = n.inputs['Emission Color']
                    if n.inputs['Emission Strength'].default_value <= 0:
                        continue
                else:
                    continue
                if sock.is_linked:
                    continue
                r, g, b = sock.default_value[:3]
                if r > 0.3 and b > 0.3 and g < 0.6 * min(r, b):
                    sock.default_value = (*NEON, 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:
                    sock.default_value = (*ORANGE, 1)


terran_glow(frig)
f_pos = spline([(-0.5, (255, 72, -22)), (0.0, (255, 64, -22)), (6.0, (250, -40, -26)), (6.5, (249.5, -48, -26.5))])


def frig_mat(t):
    p = f_pos(t)
    v = (f_pos(t + 0.02) - f_pos(t - 0.02)).normalized()
    yaw = math.atan2(v.y, v.x)
    # rocks as the storm hits
    shake = 0.0
    if t > T_STORM0:
        shake = math.radians(3.5) * math.sin(37 * t) * ss((t - T_STORM0) / 0.5)
    return Matrix.Translation(p) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(shake, 4, 'X') @ \
        Matrix.Rotation(shake * 0.6, 4, 'Y')


key_mats(frig, frig_mat)

# ------------------------------------------------------------------------------- missiles (Terran ripple)
LAUNCH = [V(-3, 3.2, 3.2), V(3, 3.2, 3.2), V(-3, -3.2, 3.2), V(3, -3.2, 3.2)]
for i, (tm, ts) in enumerate(zip(T_MIS, T_SWAT)):
    p0 = W(frig, tm, LAUNCH[i] * FK)
    tgt = W(cres, ts, HORNS[i % 2] * 0.5 + V(40, 0, 0))
    # the interception point: where the missile is when the Crescent swats it
    frac = 0.38 + 0.08 * i
    pint = p0.lerp(tgt, frac) + V(0, R.uniform(-8, 8), R.uniform(6, 14))
    spd = (pint - p0).length / (ts - tm)
    th = P.missile(p0, pint, tm, speed=spd, color=ORANGE, arc=6.0, wobble=0.8)
    P.light(p0 + V(0, 0, 3), tm, ORANGE, energy=6000, dur=0.12)
    P.lightning(cw(HORNS[i % 2]), pint, th - 0.12, th + 0.02, color=GOLD, width=0.45, jag=0.2, branches=2,
                segs=12)
    P.explosion(pint, th, size=4.0, debris=4, smoke=True, light=True)
    P.sfx(th - 0.12, 'zap_lightning', gain=0.8, pos=pint)
P.sfx(T_MIS[0], 'shot_missile', gain=0.9, pos=W(frig, T_MIS[0]))

# ------------------------------------------------------------------------------- the storm
SRCS = [HORNS[0], HORNS[1], CORE + V(8, 0, 0)]


def frig_pt(local):
    return lambda t: W(frig, t, local)


t = T_STORM0
k = 0
while t < T_KILL:
    u = (t - T_STORM0) / (T_KILL - T_STORM0)
    src = SRCS[k % 3]
    loc = V(R.uniform(-9, 9), R.uniform(-2.5, 2.5), R.uniform(-1.5, 2.5)) * FK
    du = R.uniform(0.1, 0.18)
    P.lightning(cw(src), frig_pt(loc), t, t + du, color=GOLD, width=0.32 + 0.16 * u, jag=0.2,
                branches=2, segs=14)
    if k % 2 == 0:
        P.impact(W(frig, t + 0.03, loc), t + 0.03, size=3.0 + 2 * u, color=GOLD)
    if k % 3 == 0:
        P.sfx(t, 'zap_lightning', gain=0.7 + 0.3 * u, pos=W(frig, t, loc))
    # the storm accelerates: ~0.22 s apart at first, ~0.06 s at the end
    t += lerp(0.22, 0.06, ss(u))
    k += 1
P.sfx(T_STORM0, 'crackle_loop', gain=0.7, pos=W(frig, T_STORM0), dur=T_KILL - T_STORM0 + 0.3)
P.sfx(2.3, 'charge_gold', gain=0.8, pos=W(cres, 2.3, CORE))

frig.destroy(T_KILL, size=16.0, wreck=False, debris=16)
P.cam_shake(T_KILL + 0.03, 0.6, dur=0.5)
P.sfx(T_KILL + 0.3, 'debris_metal', gain=0.6)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2200, box=((-150, 400), (-250, 250), (-120, 140)), size=0.18, avoid=()):
    me_ = bpy.data.meshes.new('SpaceDust')
    b = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        if any((c - q).length < 10.0 for q in avoid):
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

    # 1: high behind the Crescent: its whole C turning over the planet, the frigate ahead
    def s1f(t_, u):
        fp = f_pos(t_)
        pos = fp + V(lerp(100, 92, ss(u)), lerp(42, 36, ss(u)), lerp(30, 26, ss(u)))
        look = V(lerp(70, 60, ss(u)), lerp(14, 8, ss(u)), lerp(-30, -30, ss(u)))
        return pos, look, 36

    shot(0, CUT1, 10, s1f)

    # 2: beside the lower horn: horn and core big, missiles coming in and swatted
    def s2f(t_, u):
        pos = V(lerp(-25, -10, ss(u)), lerp(-128, -118, ss(u)), lerp(14, 10, ss(u)))
        look = V(lerp(140, 160, ss(u)), lerp(-10, 5, ss(u)), lerp(-16, -18, ss(u)))
        return pos, look, 26

    shot(CUT1, CUT2, 10, s2f)

    # 3: above and behind the frigate looking back up the storm; drift back toward the Crescent
    def s3f(t_, u):
        fp = f_pos(t_)
        pos = fp + V(lerp(62, 30, ss(u)), lerp(-62, -58, ss(u)), lerp(18, 24, ss(u)))
        look = fp.lerp(W(cres, t_, CORE), lerp(0.28, 0.62, ss((u - 0.45) / 0.55)))
        return pos, look, lerp(28, 36, ss((u - 0.4) / 0.6))

    shot(CUT2, 6.0, 12, s3f, last=False)
    return keys


P.camera(cam_keys(), lens=30, cuts=(CUT1, CUT2))

_cam_path = []
for _f in range(1, NF + 1):
    bpy.context.scene.frame_set(_f)
    _cam_path.append(P.cam.matrix_world.translation.copy())
dust_field(avoid=_cam_path)

print('frig', f_pos(0), f_pos(5), 'core', W(cres, 4, CORE), 'horns', W(cres, 4, HORNS[0]), W(cres, 4, HORNS[1]))
P.render()
