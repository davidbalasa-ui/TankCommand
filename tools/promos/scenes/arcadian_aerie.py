"""Aerie (Arcadian air base / hive roost): a packed Aerie saucer skims in over the alien flats on
legs of gold lightning, spinning as it brakes, and settles. It comes apart into the air: the base
blooms open, twelve ribs lift out one by one and hang over the rim on nothing (faint gold arcs
crackle in the gaps), three perches rise between the struts to staggered heights and the crown
floats high above the orb. Gold cocoons crackle on the perches and hatch three Dragonflies; a
fourth in the crown hatches a Halo. The Dragonflies kick off their perches one after another (each
perch dips, arcs leap to the belly), climb out over the ribs and swing wide; the crown spins up and
flings the Halo straight up. End low under the roost, its suspended parts bobbing, as the squadron
forms up and makes a flypast over it, the Halo leading.

Timeline (s): 0-1.15 glide in (tracking) | 1.15 touchdown, dust | 1.25-2.8 float-apart unfold |
2.55-3.0 cocoons hatch (3 Dragonflies, then the Halo) | 3.05/3.3/3.55 Dragonfly launches |
3.95 cut low under the crown | 4.05 Halo launch | 5.0-6.0 flypast over the roost."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_aerie', seconds=6.0, seed=31)
FPS = P.fps
NF = P.nf
R = P.rnd
P.env('alien', sun=(62, 0, -60), sun_energy=4.2, props=40,
      clear=[(0, 0, 15), (-12, 5, 7), (-22, 9, 7)])
P.flatten(0, 0, 12)
P.flatten(-12, 5, 6)
P.flatten(-22, 9, 6)

GOLD = COL['arc_gold']
DUST = (0.78, 0.66, 0.62)          # light dust (kit puffs need an explicit light colour)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- materials
M_BOLT = K.emit_mat('AeBolt', GOLD, 2.8)
M_CORE = K.emit_mat('AeBoltCore', (1.0, 0.7, 0.28), 3.2)
M_GLOW = K.emit_mat('AeBoltGlow', (1.0, 0.45, 0.04), 1.3, alpha=0.25)
M_SPARK = K.emit_mat('AeSpark', (1.0, 0.62, 0.2), 3.0)
M_BLUR = K.emit_mat('DfWingBlur', (1.0, 0.86, 0.55), 0.8, alpha=0.035)


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
        base = p0 * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + p1 * u * u if ctrl is not None else p0 + d * u
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
        o.visible_shadow = False
        K.show_between(o, f, f + 1)
    return objs


def gold_sparks(pos, t, size, n=10):
    f0 = P.T(t)
    o = K.ico('GoldHit', 1.0, M_BOLT, sub=2)
    o.location = pos
    o.visible_shadow = False
    for df_, s in ((0, 0.05), (1, 0.4 * size), (3, 0.01)):
        o.scale = (s, s, s)
        o.keyframe_insert('scale', frame=f0 + df_)
    K.show_between(o, f0, f0 + 4)
    for _ in range(n):
        sp = K.sphere('Spk', 1.0, M_SPARK, seg=(6, 4))
        sp.visible_shadow = False
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.4, 1))).normalized() * size * R.uniform(2.5, 4.5)
        sp.scale = (0.18 * size, 0.03 * size, 0.03 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + Vector((0, 0, -0.3))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)
    P.light(pos, t, GOLD, energy=2000 * size, dur=0.15, radius=0.5)


def dust_ring(center, t, r0, r1, n=22, size=1.3, life=1.5, opacity=0.3, rise=0.6):
    c = Vector(center)
    for k in range(2):
        r = lerp(r0, r1, k)
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.92, 1.08)
            P.puff(p + Vector((0, 0, 0.25)), t + 0.1 * k + R.uniform(0, 0.05), size=size * (1 + 0.3 * k), n=1,
                   rise=rise * (1 + k), life=life, color=DUST, opacity=opacity * (1 - 0.3 * k))


# ------------------------------------------------------------------------------- the Aerie
AER = 12.0
aer = P.load('aerie', at=(0, 0), heading=0, size=AER, label='aerie')
bpy.context.view_layer.update()
ribs = aer.parts['Ribs']
perches = aer.parts['Perches']
base = aer.parts['Base']
carrier = aer.parts['Carrier']
tpiv = aer.parts['TurretPivot']
turret = aer.parts['Turret']
PM = ribs.parent.matrix_world.copy()          # part space -> world (root at origin)
PMI3 = PM.to_3x3().inverted()
NK = PM.to_scale().x


def to_local_d(dw):
    return PMI3 @ Vector(dw)


def conv_packed(o):
    pk = o['packed']
    p, r, s = pk['p'], pk['r'], pk['s']
    return (Vector((p[0], -p[2], p[1])), Quaternion((r[3], r[0], -r[2], r[1])), Vector((s[0], s[2], s[1])))


def az_of(o, poly):
    c = o.matrix_world @ poly.center
    return math.degrees(math.atan2(c.y, c.x)) % 360


def split(o, centres, half, rot_deg=0.0):
    """Cut a part mesh into azimuth sectors; each piece gets its own origin at its centre so it
    can float, bob and tilt on its own. rot_deg turns the deployed piece about the roost axis."""
    pieces = []
    q0 = o.rotation_quaternion.copy()
    assert abs(q0.angle) < 1e-4 and (o.scale - Vector((1, 1, 1))).length < 1e-4, (o.name, q0, o.scale)
    pk_loc, pk_q, pk_s = conv_packed(o)
    for c in centres:
        me = o.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        mw = o.matrix_world
        drop = []
        for f in bm.faces:
            w = mw @ f.calc_center_median()
            a = math.degrees(math.atan2(w.y, w.x)) % 360
            d = (a - c + 180) % 360 - 180
            if abs(d) > half:
                drop.append(f)
        bmesh.ops.delete(bm, geom=drop, context='FACES')
        bm.to_mesh(me)
        bm.free()
        vs = [v.co for v in me.vertices]
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        cen = (lo + hi) / 2
        me.transform(Matrix.Translation(-cen))
        p = K.link(bpy.data.objects.new(o.name + f'_{int(c)}', me))
        p.parent = o.parent
        p.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        p.rotation_mode = 'QUATERNION'
        rq = Quaternion((0, 0, 1), math.radians(rot_deg))
        dep = rq @ (o.location + cen)
        p.location = dep
        p.rotation_quaternion = rq
        bpy.context.view_layer.update()
        wtop = max((p.matrix_world @ v.co).z for v in me.vertices)
        wbot = min((p.matrix_world @ v.co).z for v in me.vertices)
        pieces.append(dict(obj=p, az=(c + rot_deg) % 360, dep=dep.copy(), rq=rq,
                           pk_loc=pk_loc + Vector((pk_s.x * cen.x, pk_s.y * cen.y, pk_s.z * cen.z)),
                           pk_s=pk_s.copy(), top=wtop, bot=wbot, wc=p.matrix_world.translation.copy()))
    o.hide_render = True
    o.hide_viewport = True
    return pieces


RIBS = split(ribs, [30 * k for k in range(12)], 15)
PERCH = split(perches, [90, 210, 330], 45, rot_deg=30.0)     # perches between the struts
for pc in RIBS + PERCH:
    print('piece', pc['obj'].name, 'az', round(pc['az']), 'wc', [round(x, 2) for x in pc['wc']],
          'top', round(pc['top'], 2), 'bot', round(pc['bot'], 2))


def key_piece(pc, t, loc, q=None, s=None):
    o = pc['obj']
    o.location = loc
    o.rotation_quaternion = q if q is not None else pc['rq']
    o.scale = s if s is not None else Vector((1, 1, 1))
    for attr in ('location', 'rotation_quaternion', 'scale'):
        o.keyframe_insert(attr, frame=P.T(t))


def packed(pc, t):
    key_piece(pc, t, pc['pk_loc'], Quaternion(), pc['pk_s'])


# floating offsets (world metres) once deployed
RIB_GAP = 0.6
PERCH_GAP = 0.9
CROWN_GAP = 1.0

T_LAND = 1.15
T_UF0 = 1.25


def bob(seed, t, amp, hz=0.55):
    return amp * math.sin(2 * math.pi * hz * t + seed * 2.39)


# ---- ribs: lift out one at a time in a spiral (starting on the camera side), swing high and wide,
# then settle hanging over the rim on air
ORDER = sorted(RIBS, key=lambda pc: (pc['az'] - 250) % 360)
RIB_SETTLE = {}
for k, pc in enumerate(ORDER):
    t0 = T_UF0 + 0.12 + 0.055 * k
    a = math.radians(pc['az'])
    out = Vector((math.cos(a), math.sin(a), 0))
    tang = Vector((-math.sin(a), math.cos(a), 0))
    packed(pc, 0)
    packed(pc, t0)
    tall = pc['top'] > 4.5
    mid_w = out * (1.6 if tall else 2.4) + Vector((0, 0, 2.2 if tall else 1.6))
    tilt = Quaternion(to_local_d(tang).normalized(), math.radians(18 if tall else 28))
    key_piece(pc, t0 + 0.4, pc['dep'] + to_local_d(mid_w), tilt @ pc['rq'], Vector((1, 1, 1)))
    key_piece(pc, t0 + 0.72, pc['dep'] + to_local_d((0, 0, RIB_GAP - 0.12)),
              Quaternion(to_local_d(tang).normalized(), math.radians(-3)) @ pc['rq'])
    ts = t0 + 0.9
    RIB_SETTLE[pc['obj'].name] = ts
    seed = k * 1.7
    t = ts
    while t <= 6.15:
        w = ss((t - ts) / 0.4)
        z = RIB_GAP + bob(seed, t, 0.07) * w
        sway = Quaternion(to_local_d(tang).normalized(), math.radians(1.5 * math.sin(2.1 * t + seed)) * w)
        key_piece(pc, t, pc['dep'] + to_local_d((0, 0, z)), sway @ pc['rq'])
        t += 0.25
    K.set_interp(pc['obj'], 'BEZIER')

# ---- perches: rise from the stack, overshoot, settle at staggered heights; each dips when its
# Dragonfly kicks off
PERCH_T = {}
T_HATCH = {}
T_LIFT = {}
P_ORDER = sorted(PERCH, key=lambda pc: (pc['az'] - 100) % 360)     # far side first, camera side last
for i, pc in enumerate(P_ORDER):
    PERCH_T[i] = T_UF0 + 0.45 + 0.1 * i
    T_HATCH[i] = 2.55 + 0.12 * i
    T_LIFT[i] = 3.05 + 0.25 * i


def perch_off(i, t):
    """World offset of perch i from its deployed pose after it settles (gap + bob + launch dip)."""
    pc = P_ORDER[i]
    ts = PERCH_T[i] + 0.85
    w = ss((t - ts) / 0.4)
    z = PERCH_GAP + bob(3.1 + i, t, 0.08, 0.6) * w
    tl = T_LIFT[i]
    if t > tl - 0.05:
        d = t - (tl - 0.05)
        z -= 0.35 * (d * 8.0) * math.exp(1.0 - d * 8.0)
    return Vector((0, 0, z))


for i, pc in enumerate(P_ORDER):
    t0 = PERCH_T[i]
    a = math.radians(pc['az'])
    out = Vector((math.cos(a), math.sin(a), 0))
    packed(pc, 0)
    packed(pc, t0)
    key_piece(pc, t0 + 0.5, pc['dep'] + to_local_d(out * 1.0 + Vector((0, 0, PERCH_GAP + 1.4))),
              Quaternion((0, 0, 1), math.radians(-40)) @ pc['rq'])
    ts = t0 + 0.85
    t = ts
    while t <= 6.15:
        key_piece(pc, t, pc['dep'] + to_local_d(perch_off(i, t)))
        t += 1 / FPS if T_LIFT[i] - 0.1 < t < T_LIFT[i] + 0.6 else 0.25
    K.set_interp(pc['obj'], 'BEZIER')


def perch_top(i, t):
    pc = P_ORDER[i]
    return Vector((pc['wc'].x, pc['wc'].y, pc['top'])) + perch_off(i, t)


# ---- base: blooms open on the ground; carrier shrinks into it and hides
base.rotation_mode = carrier.rotation_mode = tpiv.rotation_mode = 'QUATERNION'
DEP = {o.name: (o.location.copy(), o.rotation_quaternion.copy(), o.scale.copy()) for o in (base, carrier, tpiv)}


def key_obj(o, t, packed_=False, dz=0.0, yaw=0.0, smul=1.0):
    loc, q, s = conv_packed(o) if packed_ else DEP[o.name]
    o.location = loc + to_local_d((0, 0, dz))
    o.rotation_quaternion = Quaternion((0, 0, 1), math.radians(yaw)) @ q
    o.scale = s * smul
    for attr in ('location', 'rotation_quaternion', 'scale'):
        o.keyframe_insert(attr, frame=P.T(t))


key_obj(base, 0, packed_=True)
key_obj(base, T_UF0, packed_=True)
key_obj(base, T_UF0 + 0.5, smul=1.05, yaw=8)
key_obj(base, T_UF0 + 0.72)
key_obj(carrier, 0, packed_=True)
key_obj(carrier, T_UF0, packed_=True)
key_obj(carrier, T_UF0 + 0.4, packed_=True, smul=0.45, dz=-0.2)
for c in [carrier] + list(carrier.children_recursive):
    K.key_hide(c, 0, False)
    K.key_hide(c, P.T(T_UF0 + 0.41), True)

# ---- crown: floats straight up out of the stack, overshoots, hangs high over the struts
T_CROWN = T_UF0 + 0.35
key_obj(tpiv, 0, packed_=True)
key_obj(tpiv, T_CROWN, packed_=True)
key_obj(tpiv, T_CROWN + 0.7, dz=CROWN_GAP + 1.6, smul=0.95)
key_obj(tpiv, T_CROWN + 1.15, dz=CROWN_GAP - 0.1)
T_CROWN_SET = T_CROWN + 1.35
t = T_CROWN_SET
while t <= 6.15:
    w = ss((t - T_CROWN_SET) / 0.4)
    # the Halo launch shoves the crown down a little
    kick = -0.3 * math.exp(-max(0, t - 4.05) * 5) * (1 if t > 4.05 else 0)
    key_obj(tpiv, t, dz=CROWN_GAP + bob(0.7, t, 0.1, 0.45) * w + kick)
    t += 1 / FPS if 3.95 < t < 4.6 else 0.25
for o in (base, carrier, tpiv):
    K.set_interp(o, 'BEZIER')


def crown_c(t):
    return Vector((0, 0, 5.9 + CROWN_GAP + bob(0.7, t, 0.1, 0.45) * ss((t - T_CROWN_SET) / 0.4)))


# crown rings turn slowly (yaw empty between the unfold-owned pivot and the mesh), spin up for
# the Halo launch
yaw = K.empty('CrownYaw')
yaw.parent = tpiv
yaw.rotation_mode = 'XYZ'
mpi = turret.matrix_parent_inverse.copy()
turret.parent = yaw
turret.matrix_parent_inverse = mpi
ang = 0.0
for f in range(0, NF + 2):
    t = (f - 1) / FPS
    rate = 25 + 420 * ss((t - 3.6) / 0.4) * (1 - ss((t - 4.4) / 0.8))
    ang += rate / FPS
    yaw.rotation_euler.z = math.radians(ang)
    yaw.keyframe_insert('rotation_euler', index=2, frame=f)
K.set_interp(yaw, 'LINEAR')

# ---- glide in: the packed saucer skims in spinning on gold lightning legs and settles
root = aer.root
root.rotation_mode = 'XYZ'
GLIDE = [(0.0, (-26.0, 10.5, 1.25), 2, -4, -200), (0.55, (-13.5, 5.2, 1.3), -2, -5, -110),
         (0.9, (-4.8, 1.8, 1.0), 3, 3, -35), (T_LAND, (0, 0, 0.0), 0, 0, 0)]
for t, p, rx, ry, rz in GLIDE:
    root.location = p
    root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
root.location = (0, 0, -0.05)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.06))
root.location = (0, 0, 0)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.18))
K.set_interp(root, 'BEZIER')


def root_pos(t):
    return aer.pos_at(t)


# lightning legs under the saucer while gliding
for f in range(1, int(P.T(T_LAND)) + 2):
    t = (f - 1) / FPS
    c = root_pos(t)
    fade = 1 - ss((t - T_LAND + 0.15) / 0.2)
    for k in range(4):
        if R.random() < 0.2:
            continue
        a = R.uniform(0, 2 * math.pi)
        p0 = c + Vector((math.cos(a) * 0.9, math.sin(a) * 0.9, 0.15))
        gz = P.ground_z(p0.x, p0.y)
        p1 = Vector((p0.x + R.uniform(-0.8, 0.8) + 1.2, p0.y + R.uniform(-0.8, 0.8) - 0.4, gz))
        if fade > 0.05:
            bolt_frame(jag_pts(p0, p1, 6, 0.5), f, 0.025 * fade + 0.008, forks=1, core=False)
    if f % 3 == 0 and t < T_LAND - 0.1:
        P.puff(Vector((c.x, c.y, P.ground_z(c.x, c.y) + 0.2)), t, size=1.1, n=1, rise=0.5, life=1.0,
               color=DUST, opacity=0.25)
dust_ring((0, 0, 0), T_LAND, 2.0, 4.5, n=16, size=1.3, opacity=0.2)
dust_ring((0, 0, 0), T_UF0 + 0.3, 5.5, 7.5, n=22, size=1.4, opacity=0.18)
P.cam_shake(T_LAND, 0.12, dur=0.3)

# suspension: faint gold arcs flicker in the gaps between the floating ribs and the base rim
for f in range(int(P.T(2.4)), NF + 1):
    t = (f - 1) / FPS
    for _ in range(2):
        if R.random() < 0.45:
            continue
        pc = R.choice(RIBS)
        if t < RIB_SETTLE[pc['obj'].name]:
            continue
        a = math.radians(pc['az'] + R.uniform(-4, 4))
        r = R.uniform(4.0, 5.4)
        p0 = Vector((r * math.cos(a), r * math.sin(a), 0.66))
        p1 = p0 + Vector((0, 0, RIB_GAP - 0.25 + bob(0, t, 0.05)))
        bolt_frame(jag_pts(p0, p1, 4, 0.9), f, 0.012, forks=0, core=False)


# ------------------------------------------------------------------------------- flight helpers
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def hermite(keys):
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


def fly(actor, posf, rest_fwd, bank=0.25, clamp=45, pitch_max=30):
    """Key root every frame. Nose follows horizontal velocity (falls back to rest_fwd(t) when
    hovering or rising straight up), pitched by the climb angle, banked into turns."""
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
        vh = Vector((v.x, v.y, 0))
        rf = rest_fwd(t)
        w = ss((vh.length - 0.5) / 3.0)
        hd = (rf * (1 - w) + (vh.normalized() if vh.length > 1e-3 else rf) * w).normalized()
        pit = math.atan2(v.z, max(vh.length, 2.5))
        pit = max(-math.radians(pitch_max), min(math.radians(pitch_max), pit))
        fwd = hd * math.cos(pit) + Vector((0, 0, math.sin(pit)))
        vn = v.normalized() if v.length > 1e-3 else fwd
        lat = a - vn * a.dot(vn)
        lat.z = 0
        up = (Vector((0, 0, 9.8)) + lat * bank * w)
        up.normalize()
        angu = math.degrees(math.acos(max(-1, min(1, up.z))))
        if angu > clamp:
            h = Vector((up.x, up.y, 0)).normalized()
            c = math.radians(clamp)
            up = h * math.sin(c) + Vector((0, 0, math.cos(c)))
        m3 = frame_from(fwd, up)
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


# ------------------------------------------------------------------------------- Dragonflies
DF_SIZE = 3.2
dfs = [P.load('dragonfly', size=DF_SIZE, label=f'df{i}') for i in range(3)]
bpy.context.view_layer.update()
hull = dfs[0].parts['Hull']
inv = dfs[0].root.matrix_world.inverted()
xs = [(inv @ (hull.matrix_world @ Vector(c))) for c in hull.bound_box]
HX0 = min(v.x for v in xs)
HZ0 = min(v.z for v in xs)
HZ1 = max(v.z for v in xs)
ZM = (HZ0 + HZ1) / 2
WROOT = inv @ dfs[0].parts['WingLPivot'].matrix_world.translation
print('DF hull', HX0, HZ0, HZ1, 'wingroot', WROOT, 'height', dfs[0].entry['height'])

# flypast: the squadron crosses over the roost right to left as seen from the final camera
FF = Vector((-1.0, 1.0, 0.0)).normalized()
FS = Vector((1.0, 1.0, 0.0)).normalized()        # away from the final camera
FV = FF * 15.0 + Vector((0, 0, 0.6))
DEPART = FF.copy()


def form(t):
    return Vector((-4.5, 3.0, 10.8)) + FV * (t - 6.0)


SLOTS = [-FF * 3.0 - FS * 3.0, -FF * 3.0 + FS * 3.0, -FF * 6.0 + Vector((0, 0, -1.0))]


def df_path(i):
    pc = P_ORDER[i]
    a = math.radians(pc['az'])
    out = Vector((math.cos(a), math.sin(a), 0))
    tl = T_LIFT[i]
    p0 = perch_top(i, tl)
    # climb out over the ribs, swing wide, then form up for a flypast over the roost
    a1 = a - math.radians(25)
    p2 = Vector((9.0 * math.cos(a1), 9.0 * math.sin(a1), p0.z + 4.0))
    slot = SLOTS[i]
    e = form(5.0) + slot
    v2 = (e - p2).normalized() * 13.0 + Vector((0, 0, 2.5))
    keys = [
        (tl, p0, (0, 0, 0)),
        (tl + 0.35, p0 + Vector((0, 0, 1.6)) + out * 0.3, tuple(Vector((0, 0, 6.0)) + out * 2.5)),
        (tl + 0.8, tuple(p2), tuple(v2)),
        (5.0, tuple(e), tuple(FV)),
        (6.0, tuple(form(6.0) + slot), tuple(FV)),
    ]
    hp = hermite(keys)

    def pos(t):
        if t < tl:
            return perch_top(i, t)
        return hp(t)
    return pos, out


DF_POS = []
for i, a in enumerate(dfs):
    pos, out = df_path(i)
    DF_POS.append(pos)
    fly(a, pos, lambda t, out=out: out, bank=0.3)
    print('df', i, 'perch', perch_top(i, 3.0), 'liftoff', T_LIFT[i], 'end', pos(6.0))


def wings(actor, t_on, t_full, hz=11.0, amp=22.0, phase=0.0):
    """Wing flutter (from arcadian_dragonfly) with a slow idle shiver after hatching, full buzz
    and blur ghosts from launch."""
    for side, sgn in (('L', 1), ('R', -1)):
        pv = actor.parts[f'Wing{side}Pivot']
        wing = actor.parts[f'Wing{side}']
        pv.rotation_mode = 'XYZ'
        base_r = pv.rotation_euler.copy()
        for k, ang_ in enumerate((amp * 0.85, -amp * 0.7)):
            g = K.empty(f'{actor.name}_ghost{side}{k}')
            g.parent = pv.parent
            g.matrix_parent_inverse = pv.matrix_parent_inverse.copy()
            g.location = pv.location.copy()
            g.rotation_mode = 'XYZ'
            g.rotation_euler = (base_r.x + math.radians(ang_) * sgn, base_r.y, base_r.z)
            c = wing.copy()
            K.link(c)
            c.animation_data_clear()
            c.parent = g
            c.matrix_parent_inverse = wing.matrix_parent_inverse.copy()
            c.data = wing.data.copy()
            c.data.materials.clear()
            c.data.materials.append(M_BLUR)
            K.show_between(g, P.T(t_full - 0.1), NF + 2)
        for f in range(1, NF + 2):
            t = (f - 1) / FPS
            if t < t_on:
                s = 0.0
            elif t < t_full - 0.1:
                s = 0.35 * math.sin(2 * math.pi * 3.0 * (t - t_on) + phase)
            else:
                s = math.sin(2 * math.pi * hz * t + phase) * 0.6 + (0.55 if f % 2 else -0.55)
            pv.rotation_euler = (base_r.x + math.radians(amp * s * sgn), base_r.y, base_r.z)
            pv.keyframe_insert('rotation_euler', index=0, frame=f)
        K.set_interp(pv, 'LINEAR')


def df_lifters(actor, t0, t1=6.0):
    """Gold lightning thrust from the wing roots (from arcadian_dragonfly), raking down/back."""
    core = K.sphere('DfCore', 1.0, M_BOLT, seg=(10, 6))
    core.parent = actor.root
    core.location = (WROOT.x - 0.18, 0, ZM - 0.1)
    core.scale = (0.12, 0.07, 0.07)
    glow = K.sphere('DfCoreGlow', 1.0, M_GLOW, seg=(10, 6))
    glow.parent = actor.root
    glow.location = core.location
    glow.scale = (0.24, 0.16, 0.16)
    for o in (core, glow):
        o.visible_shadow = False
        K.show_between(o, P.T(t0), NF + 2)
    k = DF_SIZE / 5.4
    for f in range(int(P.T(t0)), int(P.T(t1)) + 1):
        t = (f - 1) / FPS
        boost = 1.0 + 0.6 * math.exp(-max(0.0, t - t0 - 0.15) * 3.0)
        for sgn in (1, -1):
            if R.random() < 0.15:
                continue
            a = Vector((WROOT.x - 0.2 * k, 0.18 * k * sgn, ZM - 0.06))
            b = a + Vector((-R.uniform(1.2, 2.2) * k * boost, sgn * R.uniform(0.2, 0.6) * k,
                            -R.uniform(0.4, 1.2) * k * boost))
            bolt_frame(jag_pts(a, b, 5, 0.6), f, 0.016, parent=actor.root, glow=True, core=False,
                       forks=1 if R.random() < 0.5 else 0)


def cocoon(pos, t_h, rx, ry, rz, yaw_deg=0.0, dur=0.42, alpha=1.0):
    """A gold cocoon swells and crackles, then bursts: the unit hatches out of it."""
    o = K.sphere('Cocoon', 1.0, P.soft_fire_mat(), seg=(16, 10))
    o.visible_shadow = False
    o.location = pos
    o.rotation_euler = (0, 0, math.radians(yaw_deg))
    t0 = t_h - dur
    for t, s, al in ((t0, 0.15, 0.0), (t0 + dur * 0.6, 0.8, 0.2), (t_h - 0.02, 1.0, 0.32),
                     (t_h + 1 / FPS, 1.25, 0.25), (t_h + 4 / FPS, 1.5, 0.0)):
        o.scale = (rx * s, ry * s, rz * s)
        o.color = (1.0, 0.42, 0.05, al * alpha)
        o.keyframe_insert('scale', frame=P.T(t))
        o.keyframe_insert('color', frame=P.T(t))
    K.show_between(o, P.T(t0), P.T(t_h) + 5)
    rmax = max(rx, ry, rz)
    for f in range(int(P.T(t0)), int(P.T(t_h)) + 1):
        u = (f - P.T(t0)) / max(1, P.T(t_h) - P.T(t0))
        for _ in range(1 + int(2 * u)):
            a1 = R.uniform(0, 2 * math.pi)
            a2 = a1 + R.uniform(0.8, 1.8)
            e1, e2 = R.uniform(-0.6, 0.8), R.uniform(-0.6, 0.8)
            yr = math.radians(yaw_deg)

            def sp(a, e):
                v = Vector((math.cos(a) * math.cos(e) * rx, math.sin(a) * math.cos(e) * ry, math.sin(e) * rz)) * (0.6 + 0.4 * u)
                return pos + Matrix.Rotation(yr, 3, 'Z') @ v
            bolt_frame(jag_pts(sp(a1, e1), sp(a2, e2), 6, 0.5), f, 0.02 + 0.01 * u, forks=0, core=False)
    P.light(pos, t0, GOLD, energy=300, dur=dur, radius=rmax)
    gold_sparks(pos, t_h, 0.9, n=12)
    P.light(pos, t_h, GOLD, energy=2500, dur=0.2, radius=rmax)


def hatch_scale(actor, t_h):
    m = actor.model_root
    for t, s in ((t_h - 0.01, 0.55), (t_h + 3 / FPS, 1.08), (t_h + 7 / FPS, 1.0)):
        m.scale = (s, s, s)
        m.keyframe_insert('scale', frame=P.T(t))
    actor.appear(t_h)


for i, a in enumerate(dfs):
    th, tl = T_HATCH[i], T_LIFT[i]
    p = perch_top(i, th)
    pc = P_ORDER[i]
    cocoon(p + Vector((0, 0, 0.45)), th, DF_SIZE * 0.5, DF_SIZE * 0.42, 1.0, yaw_deg=pc['az'], alpha=0.6)
    hatch_scale(a, th)
    wings(a, th, tl, hz=10.0 + i * 0.7, phase=i * 1.3)
    df_lifters(a, tl - 0.12)
    # launch kick: arcs leap between the perch and the Dragonfly's belly, the perch flares
    for f in range(int(P.T(tl - 0.05)), int(P.T(tl + 0.3)) + 1):
        t = (f - 1) / FPS
        for _ in range(2):
            q = perch_top(i, t) + Vector((R.uniform(-0.8, 0.8), R.uniform(-0.8, 0.8), 0))
            b = DF_POS[i](t) + Vector((R.uniform(-0.4, 0.4), R.uniform(-0.4, 0.4), 0.15))
            bolt_frame(jag_pts(q, b, 6, 0.4), f, 0.03, forks=1, core=True)
    P.light(perch_top(i, tl), tl, GOLD, energy=3000, dur=0.3, radius=1.2)
    P.puff(perch_top(i, tl) + Vector((0, 0, -0.2)), tl + 0.02, size=0.9, n=2, rise=-0.3, life=0.9,
           color=(0.95, 0.8, 0.6), opacity=0.25)

# ------------------------------------------------------------------------------- the Halo
HALO_SIZE = 4.2
halo = P.load('halo', size=HALO_SIZE, label='halo')
H_H = halo.entry['height']
halo.model_root.location.z = -H_H / 2
T_HHATCH = 3.0
T_HLAUNCH = 4.05
HALO_REST = 1.0 + H_H / 2       # above the crown centre


def halo_pos_base(t):
    c = crown_c(min(t, T_HLAUNCH))
    rest = c + Vector((0, 0, HALO_REST))
    if t <= T_HLAUNCH:
        return crown_c(t) + Vector((0, 0, HALO_REST))
    return hp_halo(t)


_hrest = Vector((0, 0, 5.9 + CROWN_GAP + HALO_REST))
hp_halo = hermite([
    (T_HLAUNCH, tuple(_hrest), (0, 0, 0)),
    (T_HLAUNCH + 0.45, tuple(_hrest + Vector((0.4, 0.3, 5.5))), (2.0, 2.0, 16.0)),
    (5.2, (-1.0, 2.0, 14.5), tuple(FF * 9.0 + Vector((0, 0, 0.3)))),
    (6.0, (-6.0, 7.0, 14.3), tuple(FF * 13.0 + Vector((0, 0, 0.5)))),
])
fly(halo, halo_pos_base, lambda t: DEPART.copy().to_2d().to_3d().normalized(), bank=0.2, clamp=30, pitch_max=14)

# blade ring spin: idles after hatching, spins up hard for the launch
mr = halo.model_root
mr.rotation_mode = 'XYZ'
ang = 0.0
for f in range(0, NF + 2):
    t = (f - 1) / FPS
    rate = 0 if t < T_HHATCH else 120 + 520 * ss((t - 3.6) / 0.45)
    ang += rate / FPS
    mr.rotation_euler.z = -math.radians(ang)
    mr.keyframe_insert('rotation_euler', index=2, frame=f)
K.set_interp(mr, 'LINEAR')

cocoon(_hrest + Vector((0, 0, -0.1)), T_HHATCH, HALO_SIZE * 0.5, HALO_SIZE * 0.5, 1.1, dur=0.45, alpha=0.45)
hatch_scale(halo, T_HHATCH)
RING_R = HALO_SIZE * 0.47


def ring_pt(a, z=0.0, r=RING_R):
    return Vector((r * math.cos(a), r * math.sin(a), z))


# Halo thrust: gold lightning legs off the rim, raking down/back along the motion
for f in range(int(P.T(T_HHATCH)), NF + 2):
    t = (f - 1) / FPS
    power = 0.45 + 0.9 * ss((t - (T_HLAUNCH - 0.2)) / 0.2) * (1 - 0.35 * ss((t - T_HLAUNCH - 0.7) / 0.5))
    v = (halo_pos_base(t + 0.02) - halo_pos_base(t - 0.02)) / 0.04
    back = (-v.normalized() if v.length > 1.0 else Vector((0, 0, -1)))
    back = (back + Vector((0, 0, -0.6))).normalized()
    m = halo.mats[max(0, min(NF + 1, f))]
    for k in range(3 if power < 0.8 else 5):
        if R.random() < 0.2:
            continue
        a = R.uniform(0, 2 * math.pi)
        p0 = m @ ring_pt(a, R.uniform(-0.15, 0.05), RING_R * 0.9)
        p1 = p0 + (back * R.uniform(1.0, 2.2) + Vector((R.uniform(-.3, .3), R.uniform(-.3, .3), 0))) * power
        bolt_frame(jag_pts(p0, p1, 6, 0.45), f, 0.018 + 0.012 * power, forks=1 if R.random() < 0.4 else 0, core=False)

# launch: the crown hurls it, arcs between the crown ring and the Halo's rim
for f in range(int(P.T(T_HLAUNCH - 0.1)), int(P.T(T_HLAUNCH + 0.35)) + 1):
    t = (f - 1) / FPS
    m = halo.mats[f]
    for _ in range(3):
        a = R.uniform(0, 2 * math.pi)
        p0 = crown_c(t) + Vector((2.0 * math.cos(a), 2.0 * math.sin(a), 0.0))
        p1 = m @ ring_pt(a + R.uniform(-0.3, 0.3), 0.0, RING_R * 0.95)
        bolt_frame(jag_pts(p0, p1, 7, 0.35), f, 0.03, forks=1)
P.light(crown_c(T_HLAUNCH), T_HLAUNCH, GOLD, energy=6000, dur=0.35, radius=2.0)
gold_sparks(crown_c(T_HLAUNCH) + Vector((0, 0, 0.8)), T_HLAUNCH, 1.1, n=14)
# crown flares up before the launch (pulsing light inside the rings)
P.light(crown_c(3.7), 3.65, GOLD, energy=1200, dur=0.45, radius=1.5)

# ------------------------------------------------------------------------------- camera
T_CUT = 3.95


def car(t):
    return root_pos(t)


keys = []
for t in (0.0, 0.3, 0.6, 0.85):
    c = car(t)
    keys.append((t, tuple(c + Vector((3.5, -10.0, 1.3))), c + Vector((-0.8, 0, 1.0)), 30))
keys += [
    (1.25, (-1.0, -10.5, 1.5), (-0.4, 0.0, 1.6), 28),
    (1.9, (2.0, -15.5, 2.3), (0.0, 0.0, 3.0), 26),
    (2.7, (8.5, -14.5, 3.0), (0.0, 0.0, 4.3), 26),
    (3.35, (13.0, -10.0, 3.6), (0.0, 0.5, 5.6), 26),
    (T_CUT - 1 / FPS, (15.0, -5.5, 4.3), (0.5, 1.0, 6.8), 26),
    # shot B: low under the roost looking up at the crown; the Halo leaves, pull back for the end
    (T_CUT, (-6.5, -8.5, 1.1), (0.3, 0.3, 7.6), 20),
    (4.6, (-8.0, -10.0, 1.4), (0.5, 0.5, 10.0), 20),
    (5.3, (-10.5, -11.5, 1.8), (0.5, 1.0, 7.0), 20),
    (6.0, (-12.0, -13.0, 2.0), (-1.2, 2.0, 6.4), 19),
]
P.camera(keys, shake=0.03, cuts=(T_CUT,))
for t in T_LIFT.values():
    P.cam_shake(t, 0.05, dur=0.15)
P.cam_shake(T_HLAUNCH, 0.12, dur=0.3)

# effects never cast shadows
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.active_material is not None:
        m = o.active_material
        if 'emit_node' in m or m.name.startswith(('SoftFire', 'Fireball', 'SoftPuff')):
            o.visible_shadow = False

P.render()
