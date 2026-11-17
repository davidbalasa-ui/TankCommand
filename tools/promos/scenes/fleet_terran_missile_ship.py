"""Terran Missile ship: an Arcadian corvette prowls across the missile ship's bow on crackling
gold lightning thrusters. The missile ship does nothing... then its launch-cell lids light up
one after another down both pods (the lock) and hold: a beat of stillness. Then the ripple:
two dozen missiles pop out of the cells in a rapid stern-to-bow ripple, alternating port and
starboard, climb, curl over and come down on the corvette from every side. The corvette jinks
and lashes two of them out of the sky with gold lightning, but the rest converge: hits walk
over its hull and it breaks apart, the pieces drifting off without gravity under the web of
curling smoke trails, the missile ship cruising on in the foreground.

Scale: 0.3x the models.json ship sizes (missile ship 27 m; the Arcadian corvette is nudged
to 19.5 m so it reads). Missiles are built here (1.6 m, scaled so they read at fleet scale).

Timeline (s): 0-1.75 high behind the stern quarter: the corvette crosses ahead, lids light in
sequence 0.9-1.5, the pause | cut 1.75: low on the port side of the pods: launch ripple
2.0-2.92 (24 missiles), camera tilts up after them | cut 3.25: beside the corvette looking back:
missiles curl in from every side, 2 zapped 3.55/3.75, hits 3.95-4.6, kill 4.62 | cut 5.0: low
behind the missile ship, the wreck burning beyond, trails overhead, to 6.0."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as WFX  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_terran_missile_ship', seconds=6.0, seed=31)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

SCALE = 0.3
MS_SIZE = 90 * SCALE           # 27 m
AC_SIZE = 50 * SCALE * 1.3     # 19.5 m

P.space(planet=(1500, -300, -700, 900, (0.12, 0.17, 0.27)), nebula=(0.07, 0.03, 0.11),
        sun=(45, 0, 225), sun_energy=4.5)

CUT1 = 42 / FPS     # frame 43
CUT2 = 78 / FPS     # frame 79
CUT3 = 120 / FPS    # frame 121


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


def lerp(a, b, u):
    return a + (b - a) * u


def VV(x, y, z):
    return Vector((x, y, z))


def terran_glow(actor):
    """Scene-only tint of Terran glow: purple/magenta -> neon blue, red -> orange."""
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


def catmull(keys, t):
    if t <= keys[0][0]:
        t0, p0 = keys[0]
        t1, p1 = keys[1]
        return p0 + (p1 - p0) * ((t - t0) / (t1 - t0))
    if t >= keys[-1][0]:
        t0, p0 = keys[-2]
        t1, p1 = keys[-1]
        return p1 + (p1 - p0) * ((t - t1) / (t1 - t0))
    for i in range(len(keys) - 1):
        if keys[i][0] <= t <= keys[i + 1][0]:
            break
    ta, pa = keys[i]
    tb, pb = keys[i + 1]
    pm = keys[i - 1][1] if i > 0 else pa - (pb - pa)
    pn = keys[i + 2][1] if i + 2 < len(keys) else pb + (pb - pa)
    u = (t - ta) / (tb - ta)
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2 * pa) + (-pm + pb) * u + (2 * pm - 5 * pa + 4 * pb - pn) * u2 + (-pm + 3 * pa - 3 * pb + pn) * u3)


def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, t1, bank=0.01, face=None):
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    prev = None
    dt = 1.0 / FPS
    for f in range(1, min(NF, int(P.T(t1)) + 2) + 1):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt) - posf(t - dt)) / (2 * dt)
        fwd = face(t) if face else v
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        lat = a - v.normalized() * a.dot(v.normalized())
        side = Vector((0, 0, 1)).cross(fwd).normalized()
        roll = max(-0.9, min(0.9, lat.dot(side) * bank))
        q = (frame_from(fwd, Vector((0, 0, 1))) @ Matrix.Rotation(roll, 3, 'X')).to_quaternion()
        if prev is not None:
            q.make_compatible(prev)
        prev = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
    K.set_interp(r, 'LINEAR')


# ------------------------------------------------------------------------------- missile ship
MV = Vector((5.0, 0, 0))


def C(t):
    return VV(0, 0, 0) + MV * t + VV(0, 0, 0.25 * math.sin(t * 1.4))


ms = P.load('terran_missile_ship', at=(0, 0), size=MS_SIZE, label='missileship')
terran_glow(ms)
bpy.context.view_layer.update()
HULL = max(ms.meshes, key=lambda o: len(o.data.vertices))
HULL_MW = HULL.matrix_world.copy()
HULL_INV = HULL_MW.inverted()


def hull_ray(origin, direction):
    o = HULL_INV @ Vector(origin)
    d = (HULL_INV.to_3x3() @ Vector(direction)).normalized()
    ok, loc, nrm, idx = HULL.ray_cast(o, d)
    return (HULL_MW @ loc) if ok else None


def model_pt(x, y, z):
    return HULL_MW @ VV(x, y, z)


r_ = ms.root
for f in range(1, NF + 1):
    r_.location = C((f - 1) / FPS)
    r_.keyframe_insert('location', frame=f)
K.set_interp(r_, 'LINEAR')


def MW(t, local):
    return C(t) + Vector(local)


# launch cells: 12 a side along the twin pods (model x 2 .. 12.5, y +-2)
M_LID = K.pbr_mat('CellLid', (0.07, 0.075, 0.085), rough=0.4, metal=0.7)
CELLS = []      # (side, local top point)
for k in range(12):
    mx = lerp(1.6, 12.4, k / 11)
    for sgn in (1, -1):
        h = hull_ray(model_pt(mx, 2.0 * sgn, 30), (0, 0, -1)) or model_pt(mx, 2.0 * sgn, 2.3)
        CELLS.append((sgn, k, h))
# lid glow: one small emissive square per cell, keyed dark -> lock glow -> flash on launch
lid_mats = []
T_LOCK = [0.9 + 0.05 * k for k in range(12)]       # lids light stern -> bow (the lock)
for sgn, k, h in CELLS:
    m = K.emit_mat(f'Lid_{sgn}_{k}', ORANGE, 0.0)
    lid = K.cube(f'Lid_{sgn}_{k}', 1.0, m)
    lid.parent = ms.root
    lid.location = h + VV(0, 0, 0.05)
    lid.scale = (0.7, 0.55, 0.04)
    rim = K.cube(f'LidRim_{sgn}_{k}', 1.0, M_LID)
    rim.parent = ms.root
    rim.location = h + VV(0, 0, 0.02)
    rim.scale = (0.82, 0.66, 0.03)
    lid_mats.append((sgn, k, m))

# ------------------------------------------------------------------------------- corvette
T_KILL = 4.62
AC_KEYS = [(0.0, VV(175, 110, 28)), (1.2, VV(170, 70, 22)), (2.4, VV(160, 30, 18)),
           (3.3, VV(150, 2, 14)), (4.0, VV(146, -16, 18)), (4.62, VV(140, -30, 13)),
           (5.5, VV(134, -44, 10))]


def A(t):
    p = catmull(AC_KEYS, t) * 0.75
    # evasive jinks once it sees the missiles coming
    j = ss((t - 2.9) / 0.3)
    return p + VV(0, 0, 1.6 * j * math.sin((t - 2.9) * 4.0)) + VV(0, 2.5 * j * math.sin((t - 2.9) * 3.0), 0)


ac = P.load('arcadian_corvette', at=(0, 0), size=AC_SIZE, label='arcorvette')
for m in {s.material for o in ac.meshes for s in o.material_slots if s.material}:
    for n in (m.node_tree.nodes if m.node_tree else []):
        if n.type == 'BSDF_PRINCIPLED' and m.name.startswith(('zone_bolt', 'zone_arc')):
            n.inputs['Emission Strength'].default_value = min(n.inputs['Emission Strength'].default_value, 3.0)
fly(ac, A, T_KILL, bank=0.008)
bpy.context.view_layer.update()
am = max(ac.meshes, key=lambda o: len(o.data.vertices))
inv0 = ac.root.matrix_world.inverted()
pts0 = [inv0 @ (am.matrix_world @ Vector(c)) for c in am.bound_box]
AX0 = min(p.x for p in pts0)
AX1 = max(p.x for p in pts0)
for sgn in (1, -1):
    WFX.lightning_thruster(P, ac, 0.0, T_KILL + 1 / FPS, local=(AX0 + 0.8, 1.6 * sgn, 0.0),
                           axis=(-1, 0.12 * sgn, 0), length=5.0, width=0.08, n=2, spread=0.3,
                           color=GOLD, light=False)

# ------------------------------------------------------------------------------- missiles
MBODY = K.pbr_mat('MslBody', (0.6, 0.61, 0.64), 0.35, 0.6)
MBAND = K.emit_mat('MslBand', NEON, 2.0)
MFLAME = K.emit_mat('MslFlame', (1.0, 0.38, 0.05), 2.2)
MCORE = K.emit_mat('MslCore', (1.0, 0.62, 0.25), 2.4)
TRAIL_COL = (0.62, 0.62, 0.66)
MS_K = 1.6          # missile scale (body 1.6 m)


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


def u_of(s):            # punch out of the cell, then accelerate
    return 0.3 * s + 0.7 * s * s


def missile_path(t0, cell, t_hit, approach, hit_off, curl, ph):
    sgn, k, h = cell
    p0 = MW(t0, h)
    p3 = A(t_hit) + hit_off
    pop = VV(0, 0.35 * sgn, 1.0).normalized()
    p1 = p0 + pop * 34.0 + MV * 0.4
    p2 = p3 - approach * 55.0
    to = (p3 - p0)
    side = to.cross(VV(0, 0, 1)).normalized()

    def pos(u):
        env = math.sin(math.pi * u) * min(1.0, u * 4)
        w = env * curl
        return bez(p0, p1, p2, p3, u) + side * w * math.sin(ph + u * 7.0) + VV(0, 0, 1) * w * 0.6 * math.cos(ph + u * 7.0)
    return pos


def missile(t0, dur, pos, end_u=1.0):
    """Body + flame + light flying pos(u_of(s)); a soft smoke trail grows behind it."""
    t_end = t0 + dur * end_u
    body = K.sphere('Missile', 1.0, MBODY, seg=(10, 6))
    body.scale = (0.5 * MS_K, 0.085 * MS_K, 0.085 * MS_K)
    body.rotation_mode = 'QUATERNION'
    band = K.sphere('MslBand', 1.0, MBAND, seg=(10, 4))
    band.parent = body
    band.location = (0.3, 0, 0)
    band.scale = (0.12, 1.08, 1.08)
    core = K.sphere('MslCore', 1.0, MCORE, seg=(8, 6))
    core.parent = body
    core.location = (-1.05, 0, 0)
    core.scale = (0.25, 0.8, 0.8)
    fl = K.sphere('MslFlame', 1.0, MFLAME, seg=(10, 6))
    fl.parent = body
    fl.location = (-1.6, 0, 0)
    for o in (body, band, core, fl):
        o.visible_shadow = False
    f0 = int(round(P.T(t0)))
    f1 = int(round(P.T(t_end)))
    for f in range(f0, f1 + 1):
        s = min(end_u, ((f - 1) / FPS - t0) / dur)
        u = u_of(s)
        p = pos(u)
        q = pos(min(1.0, u + 0.01)) - pos(max(0.0, u - 0.01))
        body.location = p
        body.rotation_quaternion = q.to_track_quat('X', 'Z')
        body.keyframe_insert('location', frame=f)
        body.keyframe_insert('rotation_quaternion', frame=f)
        fl.scale = (R.uniform(0.7, 1.3), 0.85, 0.85)
        fl.keyframe_insert('scale', frame=f)
    K.set_interp(body, 'LINEAR')
    K.show_between(body, f0, f1 + 1)
    L = K.link(bpy.data.objects.new('MslLight', bpy.data.lights.new('MslLight', 'POINT')))
    L.parent = body
    L.location = (-2.2, 0, 0)
    L.data.color = (1.0, 0.45, 0.12)
    L.data.energy = 400
    L.data.shadow_soft_size = 0.5
    K.show_between(L, f0, f1 + 1)
    # trail
    n = 70
    ue = u_of(end_u)
    pts = [pos(ue * i / n) for i in range(n + 1)]
    tr = K.polyline('Trail', pts, 0.2, P.soft_mat())
    tr.visible_shadow = False
    cu = tr.data
    cu.bevel_resolution = 3
    cu.bevel_factor_mapping_end = 'SPLINE'
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=f0)
    for f in range(f0 + 1, f1 + 1):
        s = min(end_u, ((f - 1) / FPS - t0) / dur)
        cu.bevel_factor_end = max(0.0, u_of(s) / ue - 0.01)
        cu.keyframe_insert('bevel_factor_end', frame=f)
    cu.bevel_depth = 0.14
    cu.keyframe_insert('bevel_depth', frame=f0)
    cu.bevel_depth = 0.38
    cu.keyframe_insert('bevel_depth', frame=f0 + 1.0 * FPS)
    cu.bevel_depth = 0.48
    cu.keyframe_insert('bevel_depth', frame=NF + 2)
    tr.color = (*TRAIL_COL, 0.0)
    tr.keyframe_insert('color', frame=f0 - 1)
    tr.color = (*TRAIL_COL, 0.42)
    tr.keyframe_insert('color', frame=f0)
    tr.color = (*TRAIL_COL, 0.26)
    tr.keyframe_insert('color', frame=f0 + 1.2 * FPS)
    tr.color = (*TRAIL_COL, 0.07)
    tr.keyframe_insert('color', frame=NF + 2)
    K.show_between(tr, f0, NF + 2)
    return t_end


# ripple: stern -> bow, alternating port/starboard, 0.04 s apart (24 missiles in ~0.92 s)
T_RIP0 = 2.0
order = []
for k in range(12):
    for sgn in ((1, -1) if k % 2 == 0 else (-1, 1)):
        order.append(next(c for c in CELLS if c[0] == sgn and c[1] == k))
# approach directions spread round the target (from above, both sides, below, ahead)
ZAP = {5: 3.55, 11: 3.78}           # missile index -> time the corvette's lightning kills it
launches = []
hit_times = []
for n, cell in enumerate(order):
    t0 = T_RIP0 + 0.04 * n
    t_hit = 3.95 + 0.028 * n + R.uniform(-0.02, 0.02)
    az = math.radians(n * 137.5)
    el = math.radians(R.uniform(-35, 55))
    approach = VV(math.cos(el) * math.cos(az) * 0.8 + 0.6, math.cos(el) * math.sin(az), -math.sin(el)).normalized()
    hit_off = VV(R.uniform(-5, 5), R.uniform(-2, 2), R.uniform(-1.5, 1.5))
    pos = missile_path(t0, cell, t_hit, approach, hit_off, curl=R.uniform(2.0, 5.0), ph=R.uniform(0, 6.3))
    dur = t_hit - t0
    if n in ZAP:
        tz = ZAP[n]
        end_u = (tz - t0) / dur
        missile(t0, dur, pos, end_u=end_u)
        pz = pos(u_of(end_u))
        src = A(tz) + (pz - A(tz)).normalized() * 5.0
        P.lightning(src, pz, tz - 0.08, tz + 0.12, color=GOLD, width=0.12, jag=0.2, branches=2, segs=10,
                    glow=False)
        P.explosion(pz, tz, size=2.6, debris=3)
    else:
        missile(t0, dur, pos)
        hit_times.append((t_hit, pos(1.0)))
    launches.append((t0, cell))

# launch flashes, cell blast smoke, lid flashes; sound by hand (custom missiles)
for t0, (sgn, k, h) in launches:
    p = MW(t0, h)
    WFX.flash(P, p + VV(0, 0, 0.6), t0, 1.4, (1.0, 0.5, 0.12), frames=(1, 2, 3), e=2.2, hot=0.5)
    WFX.smoke_puff(P, p + VV(0, 0, 0.8), t0 + 0.02, r0=0.4, r1=2.2, life=1.6, vel=VV(0, 1.2 * sgn, 3.0),
                   dens=0.35, hot=0.6, wind=(0, 0, 0))
    P.sfx(t0, 'shot_missile', gain=0.45, rate=0.9 + 0.2 * R.random())
for sgn, k, m in lid_mats:
    em = m.node_tree.nodes.get('Emission')
    sock = em.inputs['Strength'] if em else None
    if sock is None:
        continue
    tl = T_LOCK[k]
    tlaunch = next(t0 for t0, c in launches if c[0] == sgn and c[1] == k)
    for t, v in ((0.0, 0.0), (tl - 0.01, 0.0), (tl + 0.04, 3.0), (tl + 0.2, 1.4), (tlaunch - 0.01, 1.4),
                 (tlaunch + 0.03, 3.0), (tlaunch + 0.3, 0.15)):
        sock.default_value = v
        sock.keyframe_insert('default_value', frame=P.T(t))

# hull shudder under the ripple
mr = ms.model_root
mr.rotation_mode = 'XYZ'
mr.keyframe_insert('rotation_euler', frame=1)
for i, (t0, (sgn, k, h)) in enumerate(launches[::2]):
    f = P.T(t0)
    mr.rotation_euler = (math.radians(0.5 * sgn), math.radians(-0.25), 0)
    mr.keyframe_insert('rotation_euler', frame=f + 1)
mr.rotation_euler = (0, 0, 0)
mr.keyframe_insert('rotation_euler', frame=P.T(launches[-1][0]) + 8)

# hits walk over the hull, then the kill
hit_times.sort()
for n, (t, p) in enumerate(hit_times):
    if t < T_KILL - 0.02:
        if n % 2 == 0:
            P.explosion(p, t, size=2.8, debris=3)
        else:
            P.impact(p, t, size=2.2, color=COL['fire'])
    elif t < T_KILL + 0.3:
        P.explosion(p, t, size=4.5, debris=2)
ac.size = 9.0      # (destroy scales debris speed by actor.size / 4.5)
ac.destroy(T_KILL, size=8.0, wreck=False, debris=16)

# ------------------------------------------------------------------------------- camera
keys = []
# Shot A: high behind the stern quarter, over the pods at the corvette crossing ahead.
for i in range(6):
    t = CUT1 * i / 5 if i < 5 else CUT1 - 1 / FPS
    u = t / CUT1
    c = C(t)
    pod = c + VV(3, 0, 1)
    pos = pod + VV(lerp(-29, -24, ss(u)), lerp(-25, -21, ss(u)), lerp(6, 5, ss(u)))
    look = pod + (A(t) - pod) * 0.1
    keys.append((t, tuple(pos), tuple(look), lerp(38, 41, ss(u))))
# Shot B: low on the port side, close on the pods: the ripple; tilt up after the missiles.
for i in range(6):
    t = CUT1 + (CUT2 - CUT1) * i / 5 if i < 5 else CUT2 - 1 / FPS
    u = (t - CUT1) / (CUT2 - CUT1)
    c = C(t)
    pos = c + VV(lerp(-6, -10, ss(u)), lerp(24, 28, ss(u)), lerp(-1, -2, u))
    look = c + VV(lerp(6, 10, ss(u)), lerp(0, -2, u), lerp(3, 16, ss((u - 0.35) / 0.65)))
    keys.append((t, tuple(pos), tuple(look), 24))
# Shot C: beside the corvette, looking back along the missile stream: they curl in, hit, kill.
for i in range(7):
    t = CUT2 + (CUT3 - CUT2) * i / 6 if i < 6 else CUT3 - 1 / FPS
    u = (t - CUT2) / (CUT3 - CUT2)
    a = A(min(t, T_KILL))
    pos = a + VV(lerp(20, 23, ss(u)), lerp(22, 25, ss(u)), lerp(6, 7, u))
    look = a + VV(lerp(-34, -14, ss(u)), lerp(-10, -4, ss(u)), lerp(3, 0, u))
    keys.append((t, tuple(pos), tuple(look), 24))
# Shot D: low behind the missile ship, the wreck burning beyond, trails overhead.
for i in range(5):
    t = CUT3 + (6.0 - CUT3) * i / 4
    u = (t - CUT3) / (6.0 - CUT3)
    c = C(t)
    pos = c + VV(lerp(-31, -28, ss(u)), lerp(-25, -22, ss(u)), lerp(-3, -2, u))
    look = c + (A(T_KILL) - c) * 0.27 + VV(0, 0, 2)
    keys.append((t, tuple(pos), tuple(look), 30))
P.camera(keys, shake=0.03, cuts=(CUT1, CUT2, CUT3))
P.cam_shake(T_RIP0, 0.12, dur=0.9)
P.cam_shake(T_KILL, 0.45, dur=0.45)

# ---- sound cues for effects drawn in this script
for k in range(12):
    P.sfx(T_LOCK[k], 'lock_pulse', gain=0.35, rate=1.0 + 0.04 * k)
P.sfx(0.3, 'ship_arc', gain=0.5)

P.render()
