"""Javelin (Terran missile tank): anti-air.

A pair of Halos slides across the late-afternoon sky, ring blades spinning, gold lightning
crackling off their rims. Below, a Javelin grinds to a stop, slews its turret onto them and its
twin launcher pods raise. A pause: the tube caps pulse a lock... then the ripple, left pod,
right pod, left, right, the hull rocking side to side under each launch. Four missiles corkscrew
up into the sky on curling smoke trails and climb into the Halos from below: each Halo takes a
hit that staggers it, then a second that tears it apart. The broken rings rain down burning and
crash into the desert; the Javelin sits under the hanging trails, launcher still raised.

Timeline (s): 0-1.0 drive in + brake | 0.7-1.1 turret slews | 1.0-1.75 launcher raises |
1.75-2.3 the pause (lock pulses) | 2.3/2.42/2.54/2.66 ripple L R L R | ~3.25/3.37 staggering hits |
~3.49/3.61 kills | ~4.8-5.3 wrecks crash.

0-1.875    low behind the Javelin's left shoulder, the Halos far up ahead: it brakes, slews and the
           launcher rises against the sky.
1.875-3.0  low front-left, close on the launcher: the pause, the ripple, missiles leave frame up.
3.0-6.0    wide and low behind it, looking up: trails climb, the four hits, wrecks fall and crash;
           end on the Javelin under the hanging trails with the wrecks burning beyond.

Models by name only (javelin, halo)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as W  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_javelin', seconds=6.0, seed=31)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
SAND = (0.55, 0.42, 0.3)

P.env('desert', sun=(60, 0, -40), sun_energy=4.3, props=34,
      clear=[(0, 0, 9), (-8, 0, 6), (-12, -6, 5), (-10, 4, 4), (3, 5, 4)])
P.flatten(0, 0, 8)
P.flatten(-8, 0, 5)


def ss(x):
    return K.smoothstep(x)


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('J_' + key, col, strength, alpha=alpha)
    return _mats[key]


# --------------------------------------------------------------------------- timing
T_STOP = 1.0
T_RAISE0, T_RAISE1 = 1.0, 1.75
T_RIP = [2.30, 2.42, 2.54, 2.66]
FLIGHT = [0.95, 0.95, 0.95, 0.95]
C1, C2 = 1.875, 3.0          # camera cuts (frames 46, 73)

# --------------------------------------------------------------------------- the Javelin
jav = P.load('javelin', at=(-10, 0), heading=0, label='javelin')
jav.path([(0.0, (-10.0, 0.0)), (0.55, (-3.2, 0.0)), (T_STOP, (0.0, 0.0)), (6.0, (0.0, 0.0), 0.0)])
P.dust(jav, 0.0, T_STOP, every=0.08, size=1.0, color=SAND)

tur = jav.parts['Turret']
tmesh = tur.data

# ---- cut the two launcher pods off the turret mesh so they can raise on a rear hinge
HINGE = Vector((-1.45, 0.0, 1.5))      # turret-mesh space: rear bottom edge of the pods
POD_TILT = math.radians(15.7)          # the pods' modelled elevation
STOW, RAISED = -10.0, 26.0             # extra pitch (deg) stowed / raised


def cut_pod(sgn):
    bm = bmesh.new()
    bm.from_mesh(tmesh)
    sel = [f for f in bm.faces if f.calc_center_median().y * sgn > 0.62]
    keep = {f.index for f in sel}
    b2 = bm.copy()
    bmesh.ops.delete(bm, geom=sel, context='FACES')
    bm.to_mesh(tmesh)
    bm.free()
    b2.faces.ensure_lookup_table()
    bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
    piv = Vector((HINGE.x, sgn * 1.1, HINGE.z))
    for v in b2.verts:
        v.co -= piv
    me = bpy.data.meshes.new('JavPod' + ('L' if sgn > 0 else 'R'))
    b2.to_mesh(me)
    b2.free()
    for m in tmesh.materials:
        me.materials.append(m)
    o = K.link(bpy.data.objects.new(me.name, me))
    o.parent = tur
    o.location = piv
    o.rotation_mode = 'XYZ'
    return o, piv


podL, pivL = cut_pod(1)
podR, pivR = cut_pod(-1)
PODS = {1: podL, -1: podR}


def pod_pitch(o, t, deg):
    o.rotation_euler.y = -math.radians(deg)      # nose up = negative Y rotation
    o.keyframe_insert('rotation_euler', index=1, frame=P.T(t))


for o in (podL, podR):
    pod_pitch(o, 0.0, STOW)
    pod_pitch(o, T_RAISE0, STOW)
    pod_pitch(o, T_RAISE1 - 0.12, RAISED + 2.5)
    pod_pitch(o, T_RAISE1, RAISED - 0.8)
    pod_pitch(o, T_RAISE1 + 0.12, RAISED)
    K.set_interp(o, 'BEZIER')

# tube mouths (turret-mesh space) -> empties on the pods, pointing along the tube
AX = Vector((math.cos(POD_TILT), 0, math.sin(POD_TILT)))
MOUTHS = {}
for sgn in (1, -1):
    for name, (x, y, z) in (('outer_hi', (0.99, 1.35, 2.66)), ('inner_hi', (0.99, 0.89, 2.66)),
                            ('outer_lo', (1.09, 1.35, 2.30)), ('inner_lo', (1.09, 0.89, 2.30))):
        e = K.empty(f'Tube_{sgn}_{name}')
        e.parent = PODS[sgn]
        piv = pivL if sgn > 0 else pivR
        e.location = Vector((x, sgn * y, z)) - piv + AX * 0.02
        e.rotation_mode = 'QUATERNION'
        e.rotation_quaternion = AX.to_track_quat('X', 'Z')
        MOUTHS[(sgn, name)] = e

# firing order: back and forth between the pods
SHOTS = [(1, 'outer_hi'), (-1, 'outer_hi'), (1, 'inner_hi'), (-1, 'inner_hi')]

# lock lights: a red cap glowing in each tube mouth; dim, then pulsing through the pause,
# out the moment that tube fires (an empty dark tube left behind with a hot rim)
LOCK_M = mat('LockRed', (1.0, 0.05, 0.03), 0.8)
for t, v in [(0.0, 0.8), (1.7, 0.8), (1.8, 3.2), (1.92, 0.9), (2.04, 3.2), (2.16, 0.9), (2.26, 3.6),
             (6.0, 3.6)]:
    K.key_strength(LOCK_M, P.T(t), v)
EMPTY_M = K.pbr_mat('TubeEmpty', (0.01, 0.01, 0.012), rough=1.0)
HOT_M = mat('TubeHot', (1.0, 0.32, 0.05), 2.4)
for k, key in enumerate(MOUTHS):
    e = MOUTHS[key]
    cap = K.sphere('LockCap', 1.0, LOCK_M, seg=(12, 6))
    cap.parent = e
    cap.location = (0.0, 0, 0)
    cap.scale = (0.015, 0.11, 0.11)
    cap.visible_shadow = False
    fired = [i for i, s in enumerate(SHOTS) if s == key]
    if fired:
        tf = T_RIP[fired[0]]
        K.show_between(cap, 0, P.T(tf))
        hole = K.sphere('TubeEmpty', 1.0, EMPTY_M, seg=(12, 6))
        hole.parent = e
        hole.scale = (0.012, 0.12, 0.12)
        K.show_between(hole, P.T(tf), NF + 2)
        rim = K.sphere('TubeHot', 1.0, HOT_M, seg=(12, 6))
        rim.parent = e
        rim.location = (-0.005, 0, 0)
        rim.scale = (0.01, 0.135, 0.135)
        rim.visible_shadow = False
        K.show_between(rim, P.T(tf), P.T(tf + 1.2))

# --------------------------------------------------------------------------- the Halos
HALO_RUN = [
    # A: lead, a little lower and nearer
    [(0.0, (44.0, 30.0, 18.5)), (1.5, (38.5, 14.0, 17.2)), (3.0, (33.0, -2.0, 16.0)),
     (4.0, (29.5, -12.5, 15.2))],
    # B: trailing on A's left, higher
    [(0.0, (53.0, 36.0, 22.0)), (1.5, (47.5, 20.0, 20.8)), (3.0, (42.0, 4.0, 19.6)),
     (4.0, (38.5, -6.5, 18.9))],
]
halos = []
for i, run in enumerate(HALO_RUN):
    h = P.load('halo', label=f'halo{"AB"[i]}')
    h.path(run, face=True, bank=0.4, interp='BEZIER')
    mr = h.model_root
    mr.rotation_mode = 'XYZ'
    mr.rotation_euler.z = 0
    mr.keyframe_insert('rotation_euler', index=2, frame=1)
    mr.rotation_euler.z = math.radians(320 * 6.0) * (1 if i == 0 else -1)
    mr.keyframe_insert('rotation_euler', index=2, frame=NF + 1)
    K.set_interp(mr, 'LINEAR')
    halos.append(h)
HALO_H = halos[0].entry['height']

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
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * amt * L * 0.25 * math.sin(math.pi * u) \
            if 0 < i < segs else Vector()
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
        o.visible_shadow = False
        K.show_between(o, f, f + step)
    return obs


def lifters(h, f_end):
    """Gold lightning crackling off the trailing rim and under the ring (parented to the root,
    so the fracture never picks the bolts up)."""
    for f in range(1, f_end, 2):
        for k in range(3):
            if R.random() < 0.2:
                continue
            a = math.pi + R.uniform(-1.1, 1.1)
            p0 = Vector((2.4 * math.cos(a), 2.4 * math.sin(a), 0.3))
            p1 = p0 + Vector((-R.uniform(1.4, 2.6), R.uniform(-0.5, 0.5), -R.uniform(0.2, 0.7)))
            bolt_objs(jag(p0, p1, 6, 0.6), f, 0.05, parent=h.root, core=False, step=2)
    L = K.link(bpy.data.objects.new('HaloGlow', bpy.data.lights.new('HaloGlow', 'POINT')))
    L.parent = h.root
    L.location = (-1.5, 0, 0.0)
    L.data.color = GOLD
    L.data.energy = 900
    L.data.shadow_soft_size = 1.2
    L.data.keyframe_insert('energy', frame=f_end - 1)
    L.data.energy = 0
    L.data.keyframe_insert('energy', frame=f_end)


# --------------------------------------------------------------------------- turret + launch
# aim between the two Halos' hit points, slew while braking
def hit_point(h, t):
    return h.pos_at(t) + Vector((0, 0, HALO_H * 0.5))


T_HIT = [t + d for t, d in zip(T_RIP, FLIGHT)]
TGT = [0, 1, 0, 1]
aim_pt = (hit_point(halos[0], T_HIT[0]) + hit_point(halos[1], T_HIT[1])) / 2
jav.aim(1.05, Vector((aim_pt.x, aim_pt.y, 1.5)), dur=0.45)
jav.aim(2.2, Vector((aim_pt.x, aim_pt.y, 1.5)) + Vector((0, -1.0, 0)), dur=0.6)

MBODY = K.pbr_mat('MslBody', (0.6, 0.61, 0.64), 0.35, 0.6)
MBAND = mat('MslBand', NEON, 2.0)
MFLAME = mat('MslFlame', (1.0, 0.38, 0.05), 2.2)
MCORE = mat('MslCore', (1.0, 0.62, 0.25), 2.4)
TRAIL_COL = (0.66, 0.64, 0.62)


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


def missile(t0, tube, p3, dur, curl, ph):
    """Off the rail along the tube, loft, curl, and climb into p3 from below. Smoke trail: a
    soft tube growing behind it, thickening and fading, plus a few puffs for texture."""
    sc = bpy.context.scene
    sc.frame_set(int(round(P.T(t0))))
    p0 = tube.matrix_world.translation.copy()
    dirv = (tube.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    sc.frame_set(1)
    dh = Vector((p3.x - p0.x, p3.y - p0.y, 0)).normalized()
    p1 = p0 + dirv * 11.0
    p2 = p3 - dh * 5.0 - Vector((0, 0, 7.0))
    side = dh.cross(Vector((0, 0, 1))).normalized()

    def pos(u):
        env = math.sin(math.pi * u) * min(1.0, u * 5)
        w = env * curl
        return bez(p0, p1, p2, p3, u) + side * w * math.sin(ph + u * 9.0) + Vector((0, 0, 1)) * w * 0.6 * math.cos(ph + u * 9.0)

    def u_of(s):            # accelerate off the rail
        return 0.25 * s + 0.75 * s * s

    body = K.sphere('Missile', 1.0, MBODY, seg=(10, 6))
    body.scale = (0.5, 0.085, 0.085)
    body.rotation_mode = 'QUATERNION'
    band = K.sphere('MslBand', 1.0, MBAND, seg=(10, 4))
    band.parent = body
    band.location = (0.3, 0, 0)
    band.scale = (0.12, 1.08, 1.08)
    core = K.sphere('MslCore', 1.0, MCORE, seg=(8, 6))
    core.parent = body
    core.location = (-1.05, 0, 0)
    core.scale = (0.25, 0.7, 0.7)
    fl = K.sphere('MslFlame', 1.0, MFLAME, seg=(10, 6))
    fl.parent = body
    fl.location = (-1.5, 0, 0)
    for o in (body, band, core, fl):
        o.visible_shadow = False
    f0 = int(round(P.T(t0)))
    f1 = int(round(P.T(t0 + dur)))
    for f in range(f0, f1 + 1):
        s = min(1.0, ((f - 1) / FPS - t0) / dur)
        u = u_of(s)
        p = pos(u)
        q = pos(min(1.0, u + 0.01)) - pos(max(0.0, u - 0.01))
        body.location = p
        body.rotation_quaternion = q.to_track_quat('X', 'Z')
        body.keyframe_insert('location', frame=f)
        body.keyframe_insert('rotation_quaternion', frame=f)
        fl.scale = (R.uniform(0.6, 1.1), 0.8, 0.8)
        fl.keyframe_insert('scale', frame=f)
    K.set_interp(body, 'LINEAR')
    K.show_between(body, f0, f1 + 1)
    L = K.link(bpy.data.objects.new('MslLight', bpy.data.lights.new('MslLight', 'POINT')))
    L.parent = body
    L.location = (-2.0, 0, 0)
    L.data.color = (1.0, 0.45, 0.12)
    L.data.energy = 140
    L.data.shadow_soft_size = 0.3
    K.show_between(L, f0, f1 + 1)
    # trail
    n = 60
    pts = [pos(i / n) for i in range(n + 1)]
    tr = K.polyline('Trail', pts, 0.12, P.soft_mat())
    tr.visible_shadow = False
    cu = tr.data
    cu.bevel_resolution = 3
    cu.bevel_factor_mapping_end = 'SPLINE'
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=f0)
    for f in range(f0 + 1, f1 + 1):
        s = min(1.0, ((f - 1) / FPS - t0) / dur)
        cu.bevel_factor_end = max(0.0, u_of(s) - 0.015)
        cu.keyframe_insert('bevel_factor_end', frame=f)
    cu.bevel_depth = 0.12
    cu.keyframe_insert('bevel_depth', frame=f0)
    cu.bevel_depth = 0.38
    cu.keyframe_insert('bevel_depth', frame=f0 + 1.0 * FPS)
    cu.bevel_depth = 0.62
    cu.keyframe_insert('bevel_depth', frame=NF + 2)
    tr.color = (*TRAIL_COL, 0.0)
    tr.keyframe_insert('color', frame=f0 - 1)
    tr.color = (*TRAIL_COL, 0.6)
    tr.keyframe_insert('color', frame=f0)
    tr.color = (*TRAIL_COL, 0.42)
    tr.keyframe_insert('color', frame=f0 + 1.2 * FPS)
    tr.color = (*TRAIL_COL, 0.22)
    tr.keyframe_insert('color', frame=NF + 2)
    K.show_between(tr, f0, NF + 2)
    # launch: flash at the tube, backblast off the pod's rear, a puff at the mouth
    P.muzzle_flash(tube, t0, (1.0, 0.45, 0.1), size=0.6)
    P.puff(p0 - dirv * 2.6 + Vector((0, 0, -0.3)), t0, size=1.1, n=2, rise=0.4, life=1.5,
           color=(0.5, 0.46, 0.42), opacity=0.22)
    P.puff(p0 + dirv * 0.8, t0 + 0.03, size=0.6, n=1, rise=0.4, life=1.0, color=(0.55, 0.53, 0.5), opacity=0.3)
    P.light(p0, t0, (1.0, 0.5, 0.15), energy=600, dur=0.1)
    return t0 + dur


# hull rock: each launch shoves the hull back and rolls it away from that pod
mr = jav.model_root
mr.rotation_mode = 'XYZ'
for k, (t, (sgn, name)) in enumerate(zip(T_RIP, SHOTS)):
    tube = MOUTHS[(sgn, name)]
    h = halos[TGT[k]]
    p3 = hit_point(h, T_HIT[k])
    missile(t, tube, p3, FLIGHT[k], curl=0.9 + 0.3 * (k % 2), ph=R.uniform(0, 6))
    jav.recoil(t, kick=2.0, back=0.06)
    f = P.T(t)
    mr.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    mr.rotation_euler.x = math.radians(-2.6 * sgn)
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    mr.rotation_euler.x = 0.0
    # pod jolts back on its hinge
    pod = PODS[sgn]
    pod.keyframe_insert('rotation_euler', index=1, frame=f - 1)
    pod.rotation_euler.y = -math.radians(RAISED - 3.0)
    pod.keyframe_insert('rotation_euler', index=1, frame=f + 1)
    pod.rotation_euler.y = -math.radians(RAISED)
    pod.keyframe_insert('rotation_euler', index=1, frame=f + 5)
mr.rotation_euler.x = 0.0
mr.keyframe_insert('rotation_euler', index=0, frame=P.T(T_RIP[-1]) + 9)

# --------------------------------------------------------------------------- hits and kills
SMOKE_DARK = (0.12, 0.11, 0.1)


def quiet_explosion(pos, t, size, debris=8):
    """Kit explosion with a softer core and no ground scorch (air bursts)."""
    before = set(bpy.data.objects)
    P.explosion(pos, t, size=size, debris=debris, smoke=True)
    for o in set(bpy.data.objects) - before:
        nm = o.name.split('.')[0]
        if nm == 'Core':
            o.data.materials[0] = mat('CoreSoft', (1.0, 0.45, 0.08), 2.5)
            o.scale = o.scale * 0.6
        elif nm == 'Scorch' and pos.z - P.ground_z(pos.x, pos.y) > 2.0:
            bpy.data.objects.remove(o)
        if o.type == 'MESH':
            o.visible_shadow = False


def flinch(h, t, roll, pitch):
    m = h.model_root
    f = P.T(t)
    for idx, amt in ((0, roll), (1, pitch)):
        m.keyframe_insert('rotation_euler', index=idx, frame=f - 1)
        m.rotation_euler[idx] = math.radians(amt)
        m.keyframe_insert('rotation_euler', index=idx, frame=f + 3)
        m.rotation_euler[idx] = math.radians(-amt * 0.35)
        m.keyframe_insert('rotation_euler', index=idx, frame=f + 9)
        m.rotation_euler[idx] = math.radians(amt * 0.15)
        m.keyframe_insert('rotation_euler', index=idx, frame=f + 14)
        m.rotation_euler[idx] = 0


def core_rupture(pos, t):
    """Arcadian core bursts: short gold bolts crack out of the fireball."""
    f0 = int(round(P.T(t)))
    for f in range(f0, f0 + 4):
        for k in range(5):
            dv = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.6, 1))).normalized()
            bolt_objs(jag(pos, pos + dv * R.uniform(2.2, 4.0), 6, 0.5), f, 0.06, core=(k == 0))
    P.light(pos, t, GOLD, energy=8000, dur=0.25, radius=1.5)


def damage_smoke(h, t0, t1):
    """A damaged Halo trails dark smoke and a flicker of flame from the hit."""
    t = t0
    while t < t1:
        p = h.pos_at(t) + Vector((0, 0, HALO_H * 0.6))
        P.puff(p, t, size=1.0, n=1, rise=0.3, life=1.6, color=SMOKE_DARK, opacity=0.5)
        t += 0.04


def frag_track(actor, t):
    """World positions per frame of the actor's fracture pieces (biggest first)."""
    frags = [o for o in bpy.data.objects if o.name.startswith(actor.name + '_Frag')]
    frags.sort(key=lambda o: -len(o.data.vertices))
    sc = bpy.context.scene
    tr = {o: {} for o in frags}
    for f in range(int(P.T(t)), NF + 2):
        sc.frame_set(f)
        for o in frags:
            tr[o][f] = o.matrix_world.translation.copy()
    sc.frame_set(1)
    return frags, tr


DRIFT = 0.55


def kill(h, t, size=2.6):
    import promo_fx
    p = hit_point(h, t)
    ok = promo_fx.destroy(h, t, size=size, wreck=True, debris=22)
    h.vanish(t + 1 / FPS)
    h.alive_until = t
    quiet_explosion(p, t, size, debris=10)
    core_rupture(p, t)
    P.cam_shake(t + 0.02, 0.06, 0.35)
    if not ok:
        return
    # the wrecks keep less of the ring's speed (they fall nearer, into the end frame)
    fk = P.T(t)
    for o in bpy.data.objects:
        if o.name.startswith(h.name + '_Frag') and o.animation_data and o.animation_data.action:
            for fc in K._fcurves(o.animation_data.action):
                if fc.data_path != 'location' or fc.array_index > 1:
                    continue
                pts = sorted(fc.keyframe_points, key=lambda kp: kp.co.x)
                base = None
                for kp in pts:
                    if kp.co.x <= fk:
                        base = kp.co.y
                if base is None:
                    base = fc.evaluate(fk)
                for kp in pts:
                    if kp.co.x > fk:
                        d = (kp.co.y - base) * (DRIFT - 1.0)
                        kp.co.y += d
                        kp.handle_left.y += d
                        kp.handle_right.y += d
    frags, tr = frag_track(h, t)
    fm = P.soft_fire_mat()
    crashes = []
    for i, o in enumerate(frags[:5]):
        path = tr[o]
        # landed: first frame within 0.6 m of the ground
        land = None
        for f in sorted(path):
            q = path[f]
            if q.z < P.ground_z(q.x, q.y) + 0.7 and f > P.T(t) + 4:
                land = f
                break
        # burning + smoke trail while falling
        big = i < 2
        f_end = land if land else NF + 1
        fl = K.sphere('WreckFlame', 1.0, fm, seg=(12, 8))
        fl.parent = o
        fl.visible_shadow = False
        for f in range(int(P.T(t)) + 1, NF + 2, 2):
            s_ = (0.55 if big else 0.32) * R.uniform(0.75, 1.15)
            fl.scale = (s_, s_, s_ * 1.6)
            fl.color = (1.0, R.uniform(0.25, 0.42), 0.05, R.uniform(0.55, 0.85))
            fl.keyframe_insert('scale', frame=f)
            fl.keyframe_insert('color', frame=f)
        K.show_between(fl, int(P.T(t)) + 1, NF + 2)
        for f in range(int(P.T(t)) + 2, f_end, 2 if big else 3):
            q = path[f]
            P.puff(q + Vector((0, 0, 0.3)), (f - 1) / FPS, size=(1.5 if big else 0.9), n=1, rise=0.5,
                   life=1.8, color=SMOKE_DARK, opacity=0.55 if big else 0.45)
        if land and big:
            crashes.append((land, path[land]))
    for land, q in crashes:
        tc = (land - 1) / FPS
        c = Vector((q.x, q.y, P.ground_z(q.x, q.y)))
        quiet_explosion(c + Vector((0, 0, 0.4)), tc, 2.4, debris=8)
        P.cam_shake(tc, 0.04, dur=0.3)
        for k in range(10):
            a = 2 * math.pi * k / 10
            P.puff(c + Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, 0.3)), tc + 0.03, size=1.4, n=1,
                   rise=0.6, life=1.4, color=SAND, opacity=0.4)
        P.fire_patch(c + Vector((0, 0, 0.3)), tc + 0.05, 6.2, size=0.9)
        tt = tc + 0.2
        while tt < 6.0:
            P.puff(c + Vector((0, 0, 0.8)), tt, size=1.6, n=1, rise=3.5, life=2.2, color=(0.2, 0.18, 0.17),
                   opacity=0.45)
            tt += 0.18
        P.sfx(tc, 'debris_metal', gain=0.7, pos=tuple(c))
    print('KILL', h.name, 'crashes', [(round((f - 1) / FPS, 2), tuple(round(x, 1) for x in q)) for f, q in crashes])


kill_t = {}
for k in range(4):
    h = halos[TGT[k]]
    p = hit_point(h, T_HIT[k])
    if TGT[k] not in kill_t and k < 2:
        # first hit: a burst on the rim, the ring staggers and starts to smoke
        quiet_explosion(p + Vector((0, 0, -0.3)), T_HIT[k], 1.5, debris=6)
        W.sparks(P, p, T_HIT[k], n=14, speed=9.0, color=GOLD)
        P.light(p, T_HIT[k], GOLD, energy=3000, dur=0.15, radius=0.8)
        flinch(h, T_HIT[k], 14.0 * (1 if k == 0 else -1), -9.0)
        damage_smoke(h, T_HIT[k] + 0.03, T_HIT[k + 2])
    else:
        kill_t[TGT[k]] = T_HIT[k]

for i, h in enumerate(halos):
    lifters(h, int(P.T(kill_t[i])) + 1)
for i, h in enumerate(halos):
    kill(h, kill_t[i], size=2.8)

# --------------------------------------------------------------------------- camera
look_c = Vector((40.0, 15.0, 17.0))     # where the Halos are early on
hmid = (hit_point(halos[0], 3.4) + hit_point(halos[1], 3.5)) / 2
keys = []
# shot 1: low behind the left shoulder, tracking it in; Halos up in the sky beyond;
# it brakes, slews and the launcher rises against the sky
for t in (0.0, 0.4, 0.8, 1.2, 1.5, C1 - 1 / FPS):
    jp = jav.pos_at(t)
    u = ss(t / C1)
    cam = jp + Vector((-8.6 + 2.0 * u, -4.6 + 0.6 * u, 1.15 + 0.2 * u))
    look = jp + Vector((4.0, 2.2, 3.4 + 0.4 * u))
    keys.append((t, tuple(cam), tuple(look), 28))
keys += [
    # shot 2: low front-left, close on the launcher: pause, ripple
    (C1, (4.2, 5.2, 0.9), (-0.4, 0.0, 2.0), 26),
    (2.45, (4.0, 5.6, 0.95), (-0.2, 0.0, 2.3), 26),
    (C2 - 1 / FPS, (3.7, 6.0, 1.0), (0.5, -0.5, 3.6), 26),
    # shot 3: low behind it, long lens up on the Halos as the trails climb into them; then
    # widen and tilt down with the falling wrecks onto the Javelin
    (C2, (-6.0, 5.0, 1.2), tuple(hmid + Vector((-3.0, 0, -2.5))), 40),
    (3.3, (-6.1, 5.1, 1.25), tuple(hmid + Vector((-1.5, -1.0, -1.0))), 40),
    (3.8, (-6.3, 5.3, 1.3), tuple(hmid + Vector((-2.0, -3.0, -2.5))), 36),
    (4.6, (-6.5, 6.6, 1.4), (17.0, -10.0, 6.0), 29),
    (6.0, (-6.2, 9.4, 1.5), (12.0, -9.0, 2.8), 26),
]
P.camera(keys, cuts=(C1, C2), shake=0.015)
for t in T_RIP:
    P.cam_shake(t + 0.01, 0.05, dur=0.15)

# ---- sound cues for effects drawn in this script
P.sfx(0.0, 'eng_tracked', gain=0.5, dur=1.4)
P.sfx(0.8, 'skid', gain=0.3, rate=0.8)
P.sfx(T_RAISE0, 'hydraulic', gain=0.8)
P.sfx(T_RAISE1 - 0.05, 'mech_clunk', gain=0.6)
P.sfx(1.78, 'lock_pulse', gain=0.6)
P.sfx(0.0, 'hover_arc', gain=0.2, dur=3.6, pos=(40, 10, 17))
for k, t in enumerate(T_RIP):
    P.sfx(t, 'shot_missile', gain=0.9, rate=0.95 + 0.04 * k)
    P.sfx(t + 0.12, 'whoosh', gain=0.3, rate=0.9 + 0.06 * (k % 2))

P.render()
