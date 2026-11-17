"""Harpoon Battery (Terran missile tower): a tracked carrier grinds in at dusk, brakes hard and
digs in; the launcher unfolds up off its back and settles on its pad. Three Halos come in low
over the flats, ring blades spinning, gold lightning crackling under them. One rakes the dirt
in front of the battery, another tags its base: the battery does not flinch. It slews round,
its tube lights pulse a lock... a pause... then it ripples all eight tubes. Smoke trails curl
up and over and drop onto the Halos: the lead and the middle Halo burst, gold cores rupturing,
and fall burning into the flats. The third breaks off and runs for the horizon.

Timeline (s): 0-1.35 drive in | 1.35 brake + dig in | 1.5-2.7 unfold | 2.7-3.15 slew + lock,
Halo strafe 3.1/3.3 | 3.4-4.0 ripple (8) | ~3.95 / ~4.3 kills | 4.8 / 5.2 wrecks crash |
end: low hero frame, battery left, burning wrecks right, trails hanging in the sky."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_harpoon', seconds=6.0, seed=11)
FPS = P.fps
NF = P.nf
R = P.rnd

P.env('dusk', sun=(66, 0, -25), sun_energy=4.2, props=30,
      clear=[(0, 0, 13), (-10, -5, 8), (18, 3, 12), (-2, -12, 5)])
P.flatten(0, 0, 11)
P.flatten(-9, -4, 8)
P.flatten(18, 3, 10)

GOLD = COL['arc_gold']
SAND = (0.5, 0.36, 0.25)


def ss(x):
    return K.smoothstep(x)


# --------------------------------------------------------------------------- shared materials
_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('H_' + key, col, strength, alpha=alpha)
    return _mats[key]


def quiet_explosion(pos, t, size, debris=8, scorch=True, smoke=True):
    """Kit explosion without the white-hot core blob (and optionally without the ground
    scorch, for blasts in the air)."""
    before = set(bpy.data.objects)
    P.explosion(pos, t, size=size, debris=debris, smoke=smoke)
    for o in set(bpy.data.objects) - before:
        nm = o.name.split('.')[0]
        if nm == 'Core':
            o.data.materials[0] = mat('CoreSoft', (1.0, 0.45, 0.08), 2.5)
            o.scale = o.scale * 0.6
        elif nm == 'Scorch' and not scorch:
            bpy.data.objects.remove(o)


def dust_ring(center, t, r0, r1, n=18, size=1.1, life=1.4, opacity=0.35, rise=0.5):
    c = Vector(center)
    for k, r in enumerate((r0, r1)):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.9, 1.1)
            P.puff(p + Vector((0, 0, 0.25)), t + 0.1 * k + R.uniform(0, 0.04), size=size * (1 + 0.3 * k),
                   n=1, rise=rise * (1 + k), life=life, color=SAND, opacity=opacity)


# --------------------------------------------------------------------------- the battery
H0 = 25.0
T_STOP = 1.35
T_UF0, T_UF1 = 1.5, 2.7
bat = P.load('harpoon', at=(0, 0), heading=H0, label='harpoon')
d0 = Vector((math.cos(math.radians(H0)), math.sin(math.radians(H0)), 0))
bat.path([(-0.6, tuple(-d0 * 21.0)), (0.0, tuple(-d0 * 15.0)), (0.75, tuple(-d0 * 6.4)),
          (T_STOP, (0, 0))], face=False)
bat.unfold(T_UF0, T_UF1)

# drive rumble, brake dip, dig-in squat (model_root, so it stacks on the root path)
m = bat.model_root
m.rotation_mode = 'XYZ'
for t in [x / 12 for x in range(0, 16)]:
    m.location.z = 0.04 * math.sin(t * 31.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
for t, pitch, z in [(1.25, 0.0, 0.0), (1.42, 3.2, -0.06), (1.6, -1.2, -0.12), (1.8, 0.0, -0.05), (2.0, 0.0, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.location.z = z
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    m.keyframe_insert('location', index=2, frame=P.T(t))
m.rotation_euler.y = 0.0
m.location.z = 0.0

P.dust(bat, 0.0, T_STOP, every=0.09, size=1.0, color=SAND)
dust_ring((0, 0, 0), 1.42, 2.6, 4.2, n=14, size=1.0, life=1.3, opacity=0.4)     # dig in
dust_ring((0, 0, 0), T_UF1 - 0.12, 3.0, 5.0, n=16, size=0.9, life=1.2, opacity=0.3)  # pad lands

# yaw joint between the unfolding pivot and the launcher (the pivot's rotation belongs to unfold)
piv = bat.parts['TurretPivot']
tur = bat.parts['Turret']
yaw = K.empty('HarpYaw')
yaw.parent = piv
yaw.rotation_mode = 'XYZ'
mpi = tur.matrix_parent_inverse.copy()
tur.parent = yaw
tur.matrix_parent_inverse = mpi

# eight tubes, two pods (turret mesh space). The pods are pitched ~38 deg up.
D_TUBE = Vector((0.79, 0.0, 0.61)).normalized()
ORDER = [(1.31, 'hi'), (-1.31, 'hi'), (0.79, 'hi'), (-0.79, 'hi'),
         (1.31, 'lo'), (-1.31, 'lo'), (0.79, 'lo'), (-0.79, 'lo')]
tubes = []
for y, lvl in ORDER:
    c = Vector((1.066, y, 3.153)) if lvl == 'hi' else Vector((1.386, y, 2.743))
    e = K.empty('Tube')
    e.parent = tur
    e.location = c + D_TUBE * 0.06
    e.rotation_mode = 'QUATERNION'
    e.rotation_quaternion = D_TUBE.to_track_quat('X', 'Z')
    tubes.append(e)

# lock lights: a red cap in each tube mouth, dim until the lock, then pulsing, out as it fires
LOCK_M = K.emit_mat('LockRed', (1.0, 0.06, 0.03), 0.6)
for t, v in [(0.0, 0.6), (2.5, 0.6), (2.7, 1.6), (3.0, 1.6), (3.08, 4.0), (3.16, 1.2), (3.24, 4.0),
             (3.32, 1.2), (3.38, 4.5), (6.0, 4.5)]:
    K.key_strength(LOCK_M, P.T(t), v)


# --------------------------------------------------------------------------- the Halos
def halo_path(keys):
    return [(t, p) for t, p in keys]


HALO_PLANS = [
    # A: lead, nearest the camera side; first to die
    [(1.4, (104, -18, 9.0)), (2.6, (58, -9, 6.0)), (3.3, (34, -4.5, 4.6)), (3.9, (23.5, -2.4, 4.2)),
     (4.5, (15, -0.5, 3.8))],
    # B: middle, a little further back; second kill
    [(1.4, (112, -2, 10.0)), (2.6, (66, 2, 7.0)), (3.3, (44, 4, 5.3)), (3.9, (32, 5, 4.7)),
     (4.4, (25.5, 5.6, 4.5)), (5.0, (19, 6.2, 4.2))],
    # C: far wing; strafes the battery's base, then breaks hard away and runs
    [(1.4, (108, 14, 10.5)), (2.6, (62, 11, 7.0)), (3.3, (40, 10, 5.4)), (3.75, (32.5, 10.5, 5.6)),
     (4.3, (31, 19, 8.5)), (5.0, (40, 33, 13.5)), (6.0, (62, 52, 21.0))],
]
halos = []
src = P.load('halo', label='halo0')
halos.append(src)
for i in (1, 2):
    halos.append(P.copy(src, label=f'halo{i}'))
HALO_H = src.entry['height']
for i, h in enumerate(halos):
    h.path(HALO_PLANS[i], face=True, bank=0.35)
    # blade ring spinning
    mr = h.model_root
    mr.rotation_mode = 'XYZ'
    mr.rotation_euler.z = 0
    mr.keyframe_insert('rotation_euler', index=2, frame=1)
    mr.rotation_euler.z = math.radians(330 * 6.0) * (1 if i != 1 else -1)
    mr.keyframe_insert('rotation_euler', index=2, frame=NF + 1)
    K.set_interp(mr, 'LINEAR')
    h.hover_bob(0.1, 1.3 + 0.2 * i)
    # gold under-glow that tints the ground as they come in low
    L = K.link(bpy.data.objects.new('HaloGlow', bpy.data.lights.new('HaloGlow', 'POINT')))
    L.parent = h.root
    L.location = (0, 0, -0.6)
    L.data.color = GOLD
    L.data.energy = 500
    L.data.shadow_soft_size = 1.2

BOLT_M = mat('Bolt', GOLD, 2.4)
BOLT_CORE = mat('BoltCore', (1.0, 0.72, 0.35), 3.0)
BOLT_GLOW = mat('BoltGlow', GOLD, 1.2, alpha=0.3)


def jag(p0, p1, segs, amt):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * amt * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
        pts.append(p0 + d * u + off)
    return pts


def bolt_objs(pts, f, width, parent=None, glow=True, core=True, step=1):
    obs = [K.polyline('HBolt', pts, width, BOLT_M)]
    if core:
        obs.append(K.polyline('HBoltC', pts, width * 0.4, BOLT_CORE))
    if glow:
        obs.append(K.polyline('HBoltG', pts, width * 2.8, BOLT_GLOW))
    for o in obs:
        if parent is not None:
            o.parent = parent
        K.show_between(o, f, f + step)
    return obs


def lifters(h, t1):
    """Gold lightning crackling under and behind the ring (thrusters/lifters)."""
    for f in range(1, int(P.T(t1)) + 1, 2):
        for k in range(2):
            if R.random() < 0.25:
                continue
            a = math.pi + R.uniform(-1.2, 1.2)       # back half of the ring
            p0 = Vector((2.3 * math.cos(a), 2.3 * math.sin(a), 0.2))
            p1 = p0 + Vector((-R.uniform(1.2, 2.2), R.uniform(-0.5, 0.5), -R.uniform(0.3, 0.8)))
            bolt_objs(jag(p0, p1, 5, 0.6), f, 0.035, parent=h.root, core=False, step=2)


def strike(h, t, target, dur=0.22):
    """Halo gold lightning burst from its belly to a point."""
    f0 = int(round(P.T(t)))
    f1 = int(round(P.T(t + dur)))
    for f in range(f0, f1 + 1):
        p0 = h.pos_at((f - 1) / FPS) + Vector((0, 0, 0.1))
        bolt_objs(jag(p0, Vector(target), 14, 0.16), f, 0.06)
        if R.random() < 0.7:
            pts = jag(p0, Vector(target), 14, 0.16)
            k = R.randint(4, 10)
            a = pts[k]
            b = a + (Vector(target) - a).normalized() * 2.0 + Vector((R.uniform(-1.5, 1.5), R.uniform(-1.5, 1.5), R.uniform(-1, 0.3)))
            bolt_objs(jag(a, b, 4, 0.4), f, 0.03, glow=False, core=False)
    P.light(Vector(target) + Vector((0, 0, 0.6)), t, GOLD, energy=900, dur=dur + 0.05, radius=0.6)
    P.impact(Vector(target), t + 0.02, size=0.55, color=GOLD)
    P.puff(Vector(target), t + 0.05, size=1.3, n=3, rise=1.2, life=1.4, color=SAND, opacity=0.4)


for i, h in enumerate(halos):
    lifters(h, 6.0)
strike(halos[0], 3.1, (5.2, -2.6, 0.1))
strike(halos[2], 3.3, (1.0, 2.6, 1.0))

# --------------------------------------------------------------------------- yaw / lock


def world_yaw_to(p, t):
    """Yaw (deg, launcher local) that points the pods at world point p."""
    sc = bpy.context.scene
    sc.frame_set(int(round(P.T(t))))
    loc = yaw.parent.matrix_world.inverted() @ Vector(p)
    return math.degrees(math.atan2(loc.y, loc.x))


T_RIP = [3.40, 3.47, 3.54, 3.61, 3.74, 3.81, 3.88, 3.95]
TGT = [0, 0, 0, 0, 1, 1, 1, 1]
yA = world_yaw_to(halos[0].pos_at(3.95), 3.0)
yB = world_yaw_to(halos[1].pos_at(4.3), 3.7)
for t, v in [(2.75, 0.0), (3.08, yA - 4.0), (3.2, yA + 1.0), (3.6, yA), (3.72, yB), (4.4, yB), (5.2, yB - 6)]:
    yaw.rotation_euler.z = math.radians(v)
    yaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
yaw.location = (0, 0, 0)
yaw.keyframe_insert('location', index=0, frame=1)

# --------------------------------------------------------------------------- missiles
MBODY = K.pbr_mat('MslBody', (0.55, 0.56, 0.6), 0.35, 0.6)
MBAND = K.emit_mat('MslBand', COL['terran_neon'], 2.0)
MFLAME = K.emit_mat('MslFlame', (1.0, 0.4, 0.06), 3.0)
TRAIL_COL = (0.62, 0.6, 0.6)


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


def missile(t0, tube, hit_pos_fn, dur, curl):
    """Launch along the tube, loft, then dive onto hit_pos_fn(t_hit). Smoke trail is a soft
    curve that grows behind it and slowly thickens and fades. Returns (t_hit, hit point)."""
    sc = bpy.context.scene
    sc.frame_set(int(round(P.T(t0))))
    p0 = tube.matrix_world.translation.copy()
    dirv = (tube.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    t_hit = t0 + dur
    p3 = Vector(hit_pos_fn(t_hit))
    p1 = p0 + dirv * 7.0
    p2 = p3 + Vector((-(p3 - p0).normalized().x * 5.0, -(p3 - p0).normalized().y * 5.0, 4.0))
    side = (p3 - p0).cross(Vector((0, 0, 1))).normalized()
    ph = R.uniform(0, 6)

    def pos(u):
        w = math.sin(math.pi * u) * curl * math.sin(ph + u * 7.0)
        return bez(p0, p1, p2, p3, u) + side * w

    def u_of(s):            # accelerate off the rail
        return 0.35 * s + 0.65 * s * s

    # body
    body = K.sphere('Missile', 1.0, MBODY, seg=(10, 6))
    body.scale = (0.55, 0.09, 0.09)
    body.rotation_mode = 'QUATERNION'
    band = K.sphere('MslBand', 1.0, MBAND, seg=(10, 4))
    band.parent = body
    band.location = (0.25, 0, 0)
    band.scale = (0.1, 1.08, 1.08)
    fl = K.sphere('MslFlame', 1.0, MFLAME, seg=(10, 6))
    fl.parent = body
    fl.location = (-1.25, 0, 0)
    fl.scale = (0.5, 0.9, 0.9)
    f0 = int(round(P.T(t0)))
    f1 = int(round(P.T(t_hit)))
    for f in range(f0, f1 + 1):
        s = min(1.0, ((f - 1) / FPS - t0) / dur)
        u = u_of(s)
        p = pos(u)
        q = pos(min(1.0, u + 0.01)) - pos(max(0.0, u - 0.01))
        body.location = p
        body.rotation_quaternion = q.to_track_quat('X', 'Z')
        body.keyframe_insert('location', frame=f)
        body.keyframe_insert('rotation_quaternion', frame=f)
        fl.scale = (R.uniform(0.45, 0.8), 0.9, 0.9)
        fl.keyframe_insert('scale', frame=f)
    K.set_interp(body, 'LINEAR')
    K.show_between(body, f0, f1 + 1)
    L = K.link(bpy.data.objects.new('MslLight', bpy.data.lights.new('MslLight', 'POINT')))
    L.parent = body
    L.location = (-1.6, 0, 0)
    L.data.color = (1.0, 0.45, 0.12)
    L.data.energy = 250
    K.show_between(L, f0, f1 + 1)
    # trail
    n = 40
    pts = [pos(i / n) for i in range(n + 1)]
    tr = K.polyline('Trail', pts, 0.12, P.soft_mat())
    cu = tr.data
    cu.bevel_resolution = 3
    cu.bevel_factor_mapping_end = 'SPLINE'
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=f0)
    for f in range(f0 + 1, f1 + 1):
        s = min(1.0, ((f - 1) / FPS - t0) / dur)
        cu.bevel_factor_end = max(0.0, u_of(s) - 0.02)
        cu.keyframe_insert('bevel_factor_end', frame=f)
    cu.bevel_depth = 0.1
    cu.keyframe_insert('bevel_depth', frame=f0)
    cu.bevel_depth = 0.32
    cu.keyframe_insert('bevel_depth', frame=f0 + 1.0 * FPS)
    cu.bevel_depth = 0.5
    cu.keyframe_insert('bevel_depth', frame=NF + 2)
    tr.color = (*TRAIL_COL, 0.0)
    tr.keyframe_insert('color', frame=f0 - 1)
    tr.color = (*TRAIL_COL, 0.75)
    tr.keyframe_insert('color', frame=f0)
    tr.color = (*TRAIL_COL, 0.45)
    tr.keyframe_insert('color', frame=f0 + 1.2 * FPS)
    tr.color = (*TRAIL_COL, 0.2)
    tr.keyframe_insert('color', frame=NF + 2)
    K.show_between(tr, f0, NF + 2)
    # launch: flash at the tube, backblast out of the pod's rear, small jolt
    P.muzzle_flash(tube, t0, (1.0, 0.45, 0.1), size=0.8)
    P.puff(p0 - dirv * 2.2, t0, size=1.2, n=2, rise=0.5, life=1.4, color=(0.55, 0.52, 0.5), opacity=0.4)
    P.puff(p0 + dirv * 0.8, t0 + 0.02, size=0.8, n=1, rise=0.4, life=1.0, color=(0.6, 0.58, 0.56), opacity=0.4)
    return t_hit, p3


def halo_hit_point(h):
    return lambda t: h.pos_at(t) + Vector((0, 0, HALO_H * 0.5))


# fire: first four at Halo A, last four at Halo B
results = []
kill_t = {}
kill_p = {}
DUR = [0.56, 0.58, 0.6, 0.62, 0.55, 0.57, 0.6, 0.62]
for k, (t, ti) in enumerate(zip(T_RIP, TGT)):
    h = halos[ti]
    tube = tubes[k]
    if ti in kill_t:
        # target is already dead by the time this one arrives: detonate in its fireball
        kp = kill_p[ti]
        fn = (lambda kp=kp: (lambda tt: kp + Vector((R.uniform(-1.5, 1.5), R.uniform(-1.5, 1.5), R.uniform(-0.5, 1.2)))))()
    else:
        fn = halo_hit_point(h)
    th, ph = missile(t, tube, fn, DUR[k], curl=0.5 + 0.3 * (k % 3))
    if ti not in kill_t:
        kill_t[ti] = th
        kill_p[ti] = ph
    else:
        quiet_explosion(ph, th, 1.0, debris=3, scorch=False, smoke=True)
    # tube cap goes out as it fires
    # (cap object made below)
    results.append((t, th))
    # launcher shudder
    jf = P.T(t)
    yaw.location = (0, 0, 0)
    yaw.keyframe_insert('location', index=0, frame=jf - 1)
    yaw.location = (-0.07, 0, 0)
    yaw.keyframe_insert('location', index=0, frame=jf + 1)
    yaw.location = (0, 0, 0)
    yaw.keyframe_insert('location', index=0, frame=jf + 3)
    P.light(tube.matrix_world.translation, t, (1.0, 0.5, 0.15), energy=900, dur=0.12)

# tube caps
for k, tube in enumerate(tubes):
    cap = K.sphere('LockCap', 1.0, LOCK_M, seg=(12, 6))
    cap.parent = tube
    cap.location = (-0.03, 0, 0)
    cap.scale = (0.02, 0.15, 0.15)
    K.show_between(cap, 0, P.T(T_RIP[k]))


# --------------------------------------------------------------------------- kills
CHAR = P.charred
EMBER = mat('Ember', (1.0, 0.28, 0.03), 1.4)
FLAME_M = mat('WreckFlame', (1.0, 0.2, 0.02), 1.6)


def core_rupture(pos, t):
    """Arcadian core bursts: short gold bolts crack out of the fireball."""
    f0 = int(round(P.T(t)))
    for f in range(f0, f0 + 4):
        for k in range(5):
            dv = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.4, 1))).normalized()
            bolt_objs(jag(pos, pos + dv * R.uniform(2.0, 3.8), 6, 0.5), f, 0.045, core=(k == 0))
    P.light(pos, t, GOLD, energy=6000, dur=0.25, radius=1.5)


def kill(h, t, crash_t, crash_xy, spin):
    p = h.pos_at(t) + Vector((0, 0, HALO_H * 0.5))
    quiet_explosion(p, t, 2.2, debris=18, scorch=False)
    core_rupture(p, t)
    P.cam_shake(t, 0.12, dur=0.35)
    h.vanish(t + 1 / FPS)
    # charred wreck tumbling down
    w = K.empty(h.name + '_wreck')
    w.rotation_mode = 'XYZ'
    src_mesh = halos[0].meshes[0]
    wm = src_mesh.copy()
    K.link(wm)
    wm.animation_data_clear()
    sc = bpy.context.scene
    sc.frame_set(1)
    rel = halos[0].root.matrix_world.inverted() @ src_mesh.matrix_world
    wm.parent = w
    wm.matrix_parent_inverse.identity()
    wm.matrix_basis = rel
    for s in wm.material_slots:
        s.link = 'OBJECT'
        s.material = CHAR
    fl = K.ico('WreckFire', 1.0, FLAME_M, sub=2)
    fl.parent = w
    fl.location = (0.3, 0.2, 0.5)
    p0 = p - Vector((0, 0, HALO_H * 0.5))
    vel = (h.pos_at(t) - h.pos_at(t - 0.1)) / 0.1
    c = Vector((crash_xy[0], crash_xy[1], P.ground_z(*crash_xy) + 0.1))
    fA = int(round(P.T(t)))
    fB = int(round(P.T(crash_t)))
    for f in range(fA, fB + 1):
        u = (f - fA) / max(1, fB - fA)
        # horizontal: ease from current velocity to the crash point; vertical: falling
        ph = p0.lerp(c, 1 - (1 - u) ** 1.6) + vel * 0.25 * u * (1 - u)
        ph.z = p0.z + (c.z - p0.z) * u * u + 1.0 * u * (1 - u)
        w.location = ph
        w.rotation_euler = (spin[0] * u, spin[1] * u, spin[2] * u)
        w.keyframe_insert('location', frame=f)
        w.keyframe_insert('rotation_euler', frame=f)
        s_ = R.uniform(0.35, 0.6)
        fl.scale = (s_ * 1.6, s_, s_)
        fl.keyframe_insert('scale', frame=f)
        if f % 2 == 0:
            P.puff(ph + Vector((0, 0, 0.4)), (f - 1) / FPS, size=1.4, n=1, rise=0.6, life=1.5,
                   color=(0.07, 0.06, 0.055), opacity=0.6)
    # lie on the ground afterwards, a little tilted
    w.location = c
    w.rotation_euler = (math.radians(9), math.radians(-6), spin[2])
    w.keyframe_insert('location', frame=fB + 1)
    w.keyframe_insert('rotation_euler', frame=fB + 1)
    K.set_interp(w, 'LINEAR')
    K.show_between(w, fA + 1, NF + 2)
    K.show_between(fl, fA + 1, fB + 1)
    # crash
    quiet_explosion(c + Vector((0, 0, 0.3)), crash_t, 2.4, debris=10, scorch=True)
    P.cam_shake(crash_t, 0.08, dur=0.3)
    dust_ring(c, crash_t, 1.8, 3.4, n=12, size=1.0, life=1.4, opacity=0.35)
    P.fire_patch(c + Vector((0, 0, 0.3)), crash_t + 0.05, 6.0, size=0.9)
    t_ = crash_t + 0.2
    while t_ < 6.0:
        P.puff(c + Vector((0, 0, 0.6)), t_, size=1.1, n=1, rise=3.0, life=2.0, color=(0.2, 0.18, 0.17), opacity=0.45)
        t_ += 0.22


kill(halos[0], kill_t[0], kill_t[0] + 0.85, (14.5, -1.2), (0.7, -0.5, 1.6))
kill(halos[1], kill_t[1], kill_t[1] + 0.9, (20.5, 7.0), (-0.6, 0.8, -1.2))
print('KILLS', kill_t)

# --------------------------------------------------------------------------- camera
P.camera([
    (0.0, (-0.5, -10.5, 0.8), bat.pos_at(0.0) + Vector((0, 0, 1.3)), 30),
    (0.7, (2.5, -11.0, 1.1), bat.pos_at(0.7) + Vector((0, 0, 1.4)), 30),
    (1.35, (5.5, -10.5, 1.7), (0, 0, 1.4), 30),
    (1.95, (1.0, -11.5, 2.2), (0, 0, 1.9), 30),
    (2.55, (-7.5, -9.0, 3.0), (2.0, 0.0, 2.4), 30),
    (3.05, (-10.5, -7.0, 4.3), (14.0, -0.5, 3.4), 32),
    (3.9, (-9.0, -7.8, 3.6), (18.0, 0.0, 4.0), 32),
    (4.7, (-6.0, -10.0, 1.9), (9.0, 1.0, 3.0), 30),
    (6.0, (-2.8, -11.5, 1.0), (7.0, 3.0, 2.5), 28),
], shake=0.02)
for t in T_RIP:
    P.cam_shake(t, 0.035, dur=0.12)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(2.7, 'turret_servo', gain=0.5, rate=0.7)        # battery slews round
P.sfx(2.95, 'lock_pulse', gain=0.55)                  # tube lights pulse a lock... a pause...
for _i, _t in enumerate(T_RIP):                       # ...then the ripple: smoke trails over and down
    P.sfx(_t + 0.15, 'whoosh', gain=0.25, rate=0.9 + 0.05 * (_i % 3))

P.render()
