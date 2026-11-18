"""Arcadian Corvette (space): two Arcadian corvettes run a lightning gauntlet. A Terran corvette
pair comes head-on, side by side, coilguns hammering (one in 3-shot bursts, the other in single
heavy shots on its own beat); the Arcadians weave through the fire on crackling gold lightning
thrusters, one heavy slug glancing off the lead, then thread the gap between the two
Terrans and lash out to BOTH sides at once: the wingman burns the left corvette, the lead the
right. Both Terran corvettes burst apart behind them and their pieces drift; the camera ends
ahead of the Arcadian pair as they come on through the debris, the planet behind.

Timeline (s): 0-2.0 behind and between the Terran pair, the Arcadians charging out of the
distance through the blue fire | 2.0-3.5 high over the gap: double lash 2.3-2.8, left corvette
bursts 2.8, right 3.05 | 3.5-6.0 ahead of the Arcadians: they come on through the wreckage,
push in on the lead.

Built at 0.3x game scale like the other fleet clips (Terran corvette 13.5 m, Arcadian corvettes
nudged up to 19.5 m)."""
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

P = Promo('fleet_arcadian_corvette', seconds=6.0, seed=67)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

SCALE = 0.3
CV_SIZE = 45 * SCALE
AC_SIZE = 50 * SCALE * 1.3

P.space(planet=(1500, 260, -420, 760, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(62, 0, 160), sun_energy=4.2)


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


# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 39 / 24, 94 / 24            # 1.625 s, 3.92 s
T_LASH0, T_LASH1 = 0.45, 1.05
BURSTS = [(1.95, False), (2.6, True), (3.2, True)]   # (start, hits)
SHOT_GAP = 0.15
T_KILL = 3.55


def terran_glow(actor):
    """Scene-only: red accents -> Terran orange, glass portholes -> dark hull (no windows)."""
    seen = set()
    for o in actor.meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m in seen or not m.node_tree:
                continue
            seen.add(m)
            base = m.name.split('.')[0]
            for n in m.node_tree.nodes:
                if base == 'zone_glass' and n.type == 'BSDF_PRINCIPLED':
                    n.inputs['Base Color'].default_value = (0.03, 0.035, 0.04, 1)
                    n.inputs['Roughness'].default_value = 0.5
                    n.inputs['Metallic'].default_value = 0.6
                    for nm in ('Transmission Weight', 'Emission Strength'):
                        if nm in n.inputs:
                            n.inputs[nm].default_value = 0.0
                    if 'Alpha' in n.inputs:
                        n.inputs['Alpha'].default_value = 1.0
                    continue
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
                if r > 0.3 and b > 0.3 and g < 0.6 * min(r, b):          # magenta / purple
                    sock.default_value = (*NEON, 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:                   # red accent
                    sock.default_value = (*ORANGE, 1)



# corvette model -> root space: (orig - C) * K
CV_C = Vector((0.286, 0.0, 0.34))
CV_K = CV_SIZE / 10.5715


def cv(x, y, z):
    return (Vector((x, y, z)) - CV_C) * CV_K


CV_MUZZLE = cv(5.35, 0, 0.03)
CV_ENGINES = [(cv(-5.0, 2.25, 0.0), 0.5), (cv(-5.0, -2.25, 0.0), 0.5), (cv(-4.25, 0, 0.05), 0.6)]
RAIL_BACK = 2.6          # model units: ~80% of the rail's exposed length


def split_rail(actor):
    """Cut the spinal coilgun (rod + coil + muzzle cap) out of the hull into its own object."""
    host = actor.meshes[0]
    me = host.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen = set()
    rail_faces = set()
    for v in bm.verts:
        if v in seen:
            continue
        st = [v]
        seen.add(v)
        comp = []
        while st:
            x = st.pop()
            comp.append(x)
            for e in x.link_edges:
                w = e.other_vert(x)
                if w not in seen:
                    seen.add(w)
                    st.append(w)
        xs = [c.co.x for c in comp]
        if all(abs(c.co.y) < 0.18 for c in comp) and min(xs) > 0.9 and max(xs) > 4.3:
            for c in comp:
                rail_faces.update(c.link_faces)
    b2 = bm.copy()
    keep = {f.index for f in rail_faces}
    bmesh.ops.delete(bm, geom=list(rail_faces), context='FACES')
    bm.to_mesh(me)
    bm.free()
    b2.faces.ensure_lookup_table()
    bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
    nme = bpy.data.meshes.new(actor.name + '_Rail')
    b2.to_mesh(nme)
    b2.free()
    for m in me.materials:
        nme.materials.append(m)
    rail = K.link(bpy.data.objects.new(actor.name + '_Rail', nme))
    rail.parent = host
    rail.matrix_parent_inverse = Matrix()
    rail.matrix_basis = Matrix()
    actor.rail = rail
    mz = K.empty(actor.name + '_Muzzle')
    mz.parent = actor.root
    mz.matrix_parent_inverse = Matrix()
    mz.location = CV_MUZZLE
    actor.mz = mz
    return rail




def rail_recoil(actor, t):
    r = actor.rail
    f = P.T(t)
    r.location.x = 0
    r.keyframe_insert('location', index=0, frame=f - 1)
    r.location.x = -RAIL_BACK
    r.keyframe_insert('location', index=0, frame=f + 0.7)
    r.location.x = 0
    r.keyframe_insert('location', index=0, frame=f + 3.2)


def hull_kick(actor, t, kick=2.2, back=0.6):
    m = actor.model_root
    f = P.T(t)
    m.rotation_mode = 'XYZ'
    m.location.x = 0
    m.rotation_euler.y = 0
    m.keyframe_insert('location', index=0, frame=f - 0.5)
    m.keyframe_insert('rotation_euler', index=1, frame=f - 0.5)
    m.location.x = -back
    m.rotation_euler.y = math.radians(-kick)
    m.keyframe_insert('location', index=0, frame=f + 1)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 1)
    m.location.x = 0
    m.rotation_euler.y = 0
    m.keyframe_insert('location', index=0, frame=f + 3.4)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 3.4)


def coil_shot(actor, target, t, hit, miss=4.0, speed=300):
    p0 = W(actor, t, CV_MUZZLE)
    aim = W(target, t + 0.1)
    if hit:
        aim = W(target, t + 0.1, (R.uniform(-4.5, 3.5), R.uniform(-1.4, 1.4), R.uniform(-0.6, 0.8)))
    else:
        side = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))).normalized()
        aim = p0 + (aim + side * miss - p0) * 1.8
    th = P.projectile(p0, aim, t, speed=speed, color=NEON, size=0.3)
    P.muzzle_flash(actor.mz, t, NEON, 0.9)
    rail_recoil(actor, t)
    hull_kick(actor, t)
    if hit:
        P.impact(aim, th, size=1.1, color=NEON)
    return th



def exhausts(actor, flick_seed):
    """Neon-blue engine cones (low strength, saturated) parented to the ship."""
    mat = K.emit_mat('CvExhaust', NEON, 1.4, alpha=0.55)
    core = K.emit_mat('CvExhaustCore', (0.2, 0.6, 1.0), 2.0)
    for p, r in CV_ENGINES:
        for m_, rr, ll in ((mat, r * CV_K * 0.8, 2.2), (core, r * CV_K * 0.4, 1.2)):
            me = bpy.data.meshes.new('Exhaust')
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=rr, radius2=0.02, depth=1.0)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, 'Y'))
            bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-0.5, 0, 0)))
            bm.to_mesh(me)
            bm.free()
            me.materials.append(m_)
            o = K.link(bpy.data.objects.new('Exhaust', me))
            o.visible_shadow = False
            o.parent = actor.root
            o.matrix_parent_inverse = Matrix()
            o.location = p
            for f in range(0, NF + 2, 2):
                o.scale = (ll * R.uniform(0.8, 1.15), 1, 1)
                o.keyframe_insert('scale', index=0, frame=f)





# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 48 / 24, 84 / 24          # 2.0, 3.5
T_LASH = (2.3, 2.42)
T_LASH_END = (2.8, 3.05)
T_KILL = (2.8, 3.05)
T_GRAZE = 2.12

# ------------------------------------------------------------------------------- Terran pair (+X)
def ta_pos(t):
    return V(32 * t, 21 + 0.8 * math.sin(1.1 * t), 0.6 * math.sin(0.9 * t))


def tb_pos(t):
    return V(32 * t + 3, -21 + 0.7 * math.sin(1.3 * t + 1), 1.5 + 0.5 * math.sin(0.8 * t + 2))


tA = P.load('terran_corvette', size=CV_SIZE, label='terranA')
tB = P.load('terran_corvette', size=CV_SIZE, label='terranB')
fly(tA, ta_pos, bank_up(0.6, 30))
fly(tB, tb_pos, bank_up(0.6, 30))
for a_ in (tA, tB):
    terran_glow(a_)
    bpy.context.scene.frame_set(1)
    split_rail(a_)
    exhausts(a_, 0)

# ------------------------------------------------------------------------------- Arcadian pair (-X)
X_PASS = 82.0
VA = 52.0
l_pos = spline([
    (-0.6, (X_PASS + VA * 3.2, 2, 7)),
    (0.0, (X_PASS + VA * 2.6, -3, 6)),
    (0.8, (X_PASS + VA * 1.8, 5, 4)),
    (1.5, (X_PASS + VA * 1.1, -4, 3)),
    (2.1, (X_PASS + VA * 0.5, 1, 2)),
    (2.6, (X_PASS, 0, 1.5)),
    (3.4, (X_PASS - VA * 0.8, 2, 2)),
    (4.6, (X_PASS - VA * 2.0, 1, 4)),
    (6.0, (X_PASS - VA * 3.4, -1, 6)),
    (6.6, (X_PASS - VA * 4.0, -1.5, 7)),
])


def w_pos(t):
    """Wingman: echeloned behind-right of the lead, weaving on its own phase."""
    return l_pos(t - 0.22) + V(0, 9 + 2.0 * math.sin(2.1 * t + 1), 4.5 + 1.5 * math.sin(1.7 * t))


def weave_roll(ph, k=0.45):
    return lambda t: k * math.sin(2.4 * t + ph)


acL = P.load('arcadian_corvette', size=AC_SIZE, label='arcLead')
acW = P.load('arcadian_corvette', size=AC_SIZE, label='arcWing')
fly(acL, l_pos, bank_up(1.2, 60), roll_extra=weave_roll(0.0))
fly(acW, w_pos, bank_up(1.2, 60), roll_extra=weave_roll(1.3))

SHELL_RECOL = {
    'zone_shell': ((0.80, 0.78, 0.74), (0.52, 0.40, 0.26)),
    'zone_pale': ((0.86, 0.84, 0.80), (0.60, 0.50, 0.36)),
    'zone_bronze': ((0.58, 0.40, 0.20), (0.40, 0.26, 0.12)),
}
for a_ in (acL, acW):
    for o in a_.meshes:
        me = o.data
        bi = [i for i, m in enumerate(me.materials) if m and m.name.split('.')[0] == 'zone_bolt']
        if bi:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bi], context='FACES')
            bm.to_mesh(me)
            bm.free()
seen = set()
for a_ in (acL, acW):
    for o in a_.meshes:
        for m in o.data.materials:
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
                    if base == 'zone_arc':
                        n.inputs['Emission Strength'].default_value = 2.5
                    if base == 'zone_glow':
                        n.inputs['Emission Strength'].default_value = 2.4

AC_C = Vector((-0.575, 0, -0.005))
AC_K = AC_SIZE / 17.65


def ac(x, y, z):
    return (Vector((x, y, z)) - AC_C) * AC_K


AC_NOSE = ac(8.1, 0, 0.05)
AC_PORT = ac(2.0, 3.4, 0.6)
AC_STBD = ac(2.0, -3.4, 0.6)
AC_REAR = [ac(-9.2, 1.3, 0.0), ac(-9.2, -1.3, 0.0), ac(-9.0, 0, 1.0)]


def attach_local(actor, fn):
    """Bolts built at actor-local points, then hung on the ship (cheap; no lights)."""
    before = set(bpy.data.objects)
    fn()
    for o in bpy.data.objects:
        if o not in before and o.parent is None and not o.name.startswith('FxBoltLight'):
            o.parent = actor.root
            o.matrix_parent_inverse = Matrix()


def thrusters(boost_t):
    def fn():
        for p in AC_REAR:
            ax = V(-1, 0.1 * p.y, 0.08 * p.z).normalized()
            t = 0.0
            while t < 6.0:
                du = R.uniform(0.3, 0.5)
                boost = 1.35 if boost_t[0] <= t <= boost_t[1] else 1.0
                end = p + (ax + V(0, R.uniform(-0.25, 0.25), R.uniform(-0.25, 0.25))).normalized() * 6.5 * boost * R.uniform(0.75, 1.1)
                WFX.lightning(P, p, end, t, t + du, color=GOLD, width=0.07, jag=0.22, branches=1, segs=8,
                              light=False, sparks_=False)
                t += du
    return fn


attach_local(acL, thrusters((1.6, 3.2)))
attach_local(acW, thrusters((1.7, 3.3)))

# ------------------------------------------------------------------------------- the gauntlet fire
# A: 3-shot bursts; B: single heavy shots on its own beat. All near misses; one slug glances
# off the wingman's hull.
BURSTS_A = (0.45, 1.05, 1.65)
for t0 in BURSTS_A:
    for i in range(3):
        coil_shot(tA, acL, t0 + i * 0.1, False, miss=6.0)
for t0, hit in ((0.75, False), (1.45, False), (T_GRAZE - 0.2, True)):
    th = coil_shot(tB, acL, t0, hit, miss=7.0)
    if hit:
        P.sfx(th, 'impact_metal', gain=0.8, pos=W(acL, th))


# ------------------------------------------------------------------------------- the double lash
def lash(src, side_local, dst, t0, t1):
    P.lightning(lambda t: W(src, t, side_local), lambda t: W(dst, t, V(R.uniform(-2, 2), 0, 0.6)), t0, t1,
                color=GOLD, width=0.12, jag=0.2, branches=2, segs=12)
    for k in range(3):
        tk = t0 + 0.04 + k * (t1 - t0) / 3
        P.impact(W(dst, tk, V(R.uniform(-3, 3), 0, 0.8)), tk, size=1.2, color=GOLD)
    P.sfx(t0, 'zap_lightning', gain=1.0, pos=W(dst, t0))
    P.sfx(t0, 'crackle_loop', gain=0.5, pos=W(dst, t0), dur=t1 - t0)


# wingman (on the +Y side) takes A from its port side; the lead takes B (-Y) from starboard
lash(acW, AC_PORT, tA, T_LASH[0], T_LASH_END[0])
lash(acL, AC_STBD, tB, T_LASH[1], T_LASH_END[1])
tA.destroy(T_KILL[0], size=6.0, wreck=False, debris=12)
tB.destroy(T_KILL[1], size=6.0, wreck=False, debris=12)

P.sfx(1.0, 'whoosh', gain=0.6, pos=W(acL, 1.0))
P.sfx(2.45, 'whoosh', gain=1.0, pos=W(acL, 2.6))
P.sfx(4.0, 'ship_arc', gain=0.5, pos=W(acL, 4.0), dur=2.0)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2400, box=((-200, 260), (-90, 90), (-50, 60)), size=0.1, avoid=()):
    me_ = bpy.data.meshes.new('SpaceDust')
    b = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        if any((c - q).length < 6.0 for q in avoid):
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

    # 1: behind and between the Terran pair, the Arcadians charging out of the distance
    def s1f(t_, u):
        mid = (ta_pos(t_) + tb_pos(t_)) / 2
        pos = mid + V(lerp(-62, -50, ss(u)), lerp(5, 3, ss(u)), lerp(13, 10, ss(u)))
        look = mid.lerp(l_pos(t_), lerp(0.3, 0.2, ss(u))) + V(0, 0, 0.5)
        return pos, look, 32

    shot(0, CUT1, 10, s1f)

    # 2: high over the gap as they thread it and lash both sides
    def s2f(t_, u):
        c = V(lerp(84, 92, ss(u)), 0, 0)
        pos = c + V(lerp(-46, -40, ss(u)), lerp(-26, -22, ss(u)), lerp(40, 36, ss(u)))
        look = c + V(lerp(-6, -14, ss(u)), 0, 0)
        return pos, look, 26

    shot(CUT1, CUT2, 10, s2f)

    # 3: ahead of the pair as they come on through the wreckage; push in on the lead
    def s3f(t_, u):
        lp = l_pos(t_)
        pos = lp + V(lerp(-44, -24, ss(u)), lerp(-15, -10, ss(u)), lerp(7, 4.5, ss(u)))
        look = lp.lerp(w_pos(t_), 0.3) + V(lerp(10, 5, ss(u)), 0, 0.5)
        return pos, look, lerp(30, 34, ss(u))

    shot(CUT2, 6.0, 12, s3f, last=False)
    return keys


P.camera(cam_keys(), lens=30, cuts=(CUT1, CUT2))
_cam_path = []
for _f in range(1, NF + 1):
    bpy.context.scene.frame_set(_f)
    _cam_path.append(P.cam.matrix_world.translation.copy())
dust_field(avoid=_cam_path)

print('pass', l_pos(2.6), ta_pos(2.6), tb_pos(2.6))
P.render()
