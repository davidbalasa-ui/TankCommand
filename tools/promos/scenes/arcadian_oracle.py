"""Oracle (Arcadian radar spire): a packed Oracle skims in low over violet flats riding legs of gold
lightning and settles in a dust ring. Then it comes apart upward: the base blooms open on the
ground, the horns lift off and drift into place with a gap of air under them, the eye-orb floats
up high above the horns, and a few loose shards rise from the dust to orbit it, everything held
together by threads of gold lightning. The eye swings round to stare across the valley, charges,
and a pale gold light wave rolls out over the land. As the wave passes, Terran armour that had
been creeping up hidden in the fog is revealed: gold outlines snap on around each tank. A beat
later gold energy strikes from Arcadian guns far behind arc over the spire into the marked tanks.
End low behind the Oracle, parts still hovering, a second pulse rolling out over the wrecks.

Timeline (s): 0-1.45 glide in (low tracking camera) | 1.45 touchdown + dust ring | 1.55-3.0
float-apart unfold, shards rise | 3.0-3.3 eye turns + charges | 3.3 pulse | ~3.6-4.2 reveals |
4.4-4.9 gold strikes (3 kills) | 5.15 second pulse | 5.0-6 low hero frame."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Quaternion, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_oracle', seconds=6.0, seed=5)
FPS = P.fps
R = P.rnd

P.env('alien', sun=(62, 0, -35), sun_energy=3.4, props=38,
      clear=[(0, 0, 9), (-14, -6, 8), (19, 9, 12)])
P.flatten(0, 0, 8)
P.flatten(19, 9, 11)

GOLD = COL['arc_gold']
DEEP = (1.0, 0.42, 0.03)
PALE = (1.0, 0.72, 0.32)          # pale gold of the pulse
SAND = tuple(min(1, c * 1.9) for c in P.palette['g1'])


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('O_' + key, col, strength, alpha=alpha)
    return _mats[key]


M_BOLT = mat('Bolt', GOLD, 2.4)
M_CORE = mat('BoltCore', (1.0, 0.7, 0.3), 2.8)
M_GLOW = mat('BoltGlow', DEEP, 1.1, alpha=0.22)

# light, thin smoke (the kit default is a dark ball)
_kit_puff = P.puff


def _thin_puff(pos, t, size=0.6, n=3, rise=1.0, life=1.2, color=None, opacity=0.65):
    if color is None:
        color, size, opacity = (0.3, 0.27, 0.28), size * 0.7, opacity * 0.6
    return _kit_puff(pos, t, size=size, n=n, rise=rise, life=life, color=color, opacity=opacity)


P.puff = _thin_puff


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
        o.visible_shadow = False
        K.show_between(o, f, f + nframes)
    return objs


def gold_sparks(pos, t, size=1.0, n=8):
    m = mat('Spark', GOLD, 2.5)
    f0 = P.T(t)
    for i in range(n):
        sp = K.sphere('Spk', 1.0, m, seg=(6, 4))
        sp.visible_shadow = False
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.2, 1.2))).normalized() * size * 3.2
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
            _kit_puff(p + Vector((0, 0, 0.25)), t + dt * k + R.uniform(0, 0.04), size=size * (0.8 + 0.5 * u),
                      n=1, rise=rise * (1 + u), life=life, color=SAND, opacity=opacity * (1 - 0.3 * u))


def quiet_explosion(pos, t, size, debris=8):
    """Kit explosion with the white-hot core toned down to saturated fire."""
    before = set(bpy.data.objects)
    P.explosion(pos, t, size=size, debris=debris)
    for o in set(bpy.data.objects) - before:
        if o.name.split('.')[0] == 'Core':
            o.data.materials[0] = mat('CoreSoft', (1.0, 0.4, 0.06), 2.4)
            o.scale = o.scale * 0.6


# --------------------------------------------------------------------------- the Oracle
T_LAND = 1.45
T_UF0, T_UF1 = 1.55, 3.0
GLIDE_Z = 1.25
SKID = 0.25        # the packed carrier hull floats this far above the root

ora = P.load('oracle', at=(0, 0), heading=0, label='oracle')
bpy.context.view_layer.update()
parts = {n: ora.parts[n] for n in ('Base', 'Carrier', 'Horns', 'TurretPivot', 'Turret')}


def packed_pose(o):
    pk = o['packed']
    p, r, s = pk['p'], pk['r'], pk['s']
    return (Vector((p[0], -p[2], p[1])), Quaternion((r[3], r[0], -r[2], r[1])), Vector((s[0], s[2], s[1])))


dep = {}
for n in ('Base', 'Carrier', 'Horns', 'TurretPivot'):
    o = parts[n]
    o.rotation_mode = 'QUATERNION'
    dep[n] = (o.location.copy(), o.rotation_quaternion.copy(), o.scale.copy())
    pk = packed_pose(o)
    o.location, o.rotation_quaternion, o.scale = pk
    for attr in ('location', 'rotation_quaternion', 'scale'):
        o.keyframe_insert(attr, frame=0)


def key_part(n, t, dz=0.0, yaw=0.0, scale_mul=1.0, packed=False, dxy=(0.0, 0.0)):
    o = parts[n]
    if packed:
        loc, q, s = packed_pose(o)
    else:
        loc, q, s = dep[n]
    o.location = loc + Vector((dxy[0], dxy[1], dz))
    o.rotation_quaternion = Quaternion((0, 0, 1), math.radians(yaw)) @ q
    o.scale = s * scale_mul
    for attr in ('location', 'rotation_quaternion', 'scale'):
        o.keyframe_insert(attr, frame=P.T(t))


# parts are in KeshSeerSpire space; its Norm scale k maps them to world
NORM_K = ora.parts['oracle_Norm'].scale.x
HORN_GAP = 0.36 / NORM_K
EYE_GAP = 0.62 / NORM_K

# Base: blooms open on the ground
key_part('Base', T_UF0, packed=True)
key_part('Base', T_UF0 + 0.55, scale_mul=1.06)
key_part('Base', T_UF0 + 0.75)
# Carrier: shrinks under the growing base, then hides (hideWhenDeployed)
key_part('Carrier', T_UF0, packed=True)
key_part('Carrier', T_UF0 + 0.45, packed=True, scale_mul=0.4, dz=-0.25)
for c in [parts['Carrier']] + list(parts['Carrier'].children_recursive):
    K.key_hide(c, 0, False)
    K.key_hide(c, P.T(T_UF0 + 0.46), True)
# Horns: lift off the stack, drift up high and swing round, then sink into place over an air gap
key_part('Horns', T_UF0 + 0.1, packed=True)
key_part('Horns', T_UF0 + 0.7, dz=HORN_GAP + 1.0 / NORM_K, yaw=-70, scale_mul=0.92)
key_part('Horns', T_UF0 + 1.25, dz=HORN_GAP - 0.06 / NORM_K, yaw=4)
key_part('Horns', T_UF1, dz=HORN_GAP, yaw=0)
# Eye: floats straight up out of the stack, overshoots high, settles above the horn tips
key_part('TurretPivot', T_UF0 + 0.2, packed=True)
key_part('TurretPivot', T_UF0 + 0.95, dz=EYE_GAP + 1.5 / NORM_K, yaw=0, scale_mul=0.9)
key_part('TurretPivot', T_UF1 - 0.1, dz=EYE_GAP - 0.08 / NORM_K)
key_part('TurretPivot', T_UF1 + 0.15, dz=EYE_GAP)
for n in ('Base', 'Carrier', 'Horns', 'TurretPivot'):
    K.set_interp(parts[n], 'BEZIER')

# idle float after assembly: horns and eye bob out of phase (location z only, on top of their keys)
for n, amp, hz, ph in (('Horns', 0.05, 0.55, 0.0), ('TurretPivot', 0.09, 0.7, 1.9)):
    o = parts[n]
    base_z = dep[n][0].z + (HORN_GAP if n == 'Horns' else EYE_GAP)
    t = T_UF1 + 0.2
    first = True
    while t <= 6.1:
        o.location.z = base_z + (amp / NORM_K) * math.sin(2 * math.pi * hz * (t - T_UF1 - 0.2) + ph) * (0.0 if first else 1.0)
        o.keyframe_insert('location', index=2, frame=P.T(t))
        first = False
        t += 0.25

# eye yaw: an empty between the pivot and the eye mesh (unfold-owned pivot keeps its quaternion)
piv = parts['TurretPivot']
eye = parts['Turret']
yaw = K.empty('EyeYaw')
yaw.parent = piv
yaw.rotation_mode = 'XYZ'
mpi = eye.matrix_parent_inverse.copy()
eye.parent = yaw
eye.matrix_parent_inverse = mpi
T_TURN = 2.85
T_PULSE = 3.3
T_PULSE2 = 5.15
for t, deg in [(0, 0), (T_UF1 - 0.4, -40), (T_TURN, -40), (T_TURN + 0.32, 75), (T_TURN + 0.42, 68),
               (T_PULSE2 - 0.3, 90), (T_PULSE2, 160), (6.0, 205)]:
    yaw.rotation_euler.z = math.radians(deg)
    yaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
K.set_interp(yaw, 'BEZIER')

# glide in on gold lightning legs
root = ora.root
root.rotation_mode = 'XYZ'
glide = [(0.0, (-27.0, -11.0, GLIDE_Z), 3, -3, 20), (0.65, (-15.5, -6.4, GLIDE_Z), -3, -4, 22),
         (1.1, (-5.5, -2.2, GLIDE_Z - 0.1), 2, -1, 14), (1.33, (-1.0, -0.4, 0.55), 0, 4, 4),
         (T_LAND, (0, 0, -SKID), 0, 0, 0)]
for t, p, rx, ry, rz in glide:
    root.location = p
    root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
root.location = (0, 0, -SKID - 0.06)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.06))
root.location = (0, 0, -SKID)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.2))
root.keyframe_insert('location', frame=P.T(T_UF0))
root.location = (0, 0, 0)
root.keyframe_insert('location', frame=P.T(T_UF0 + 0.5))
K.set_interp(root, 'BEZIER')
m = ora.model_root
for i in range(0, 9):
    t = i * T_LAND / 8
    m.location.z = 0.07 * math.sin(2 * math.pi * 1.3 * t) * (1 - t / T_LAND)
    m.keyframe_insert('location', index=2, frame=P.T(t))

LIFT = SKID + 0.04
gl = K.link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
gl.parent = root
gl.location = (0, 0, -0.2)
gl.data.color = GOLD
gl.data.shadow_soft_size = 1.5
for t, e in [(0.0, 1100), (1.2, 1100), (T_LAND, 400), (T_LAND + 0.12, 0)]:
    gl.data.energy = e
    gl.data.keyframe_insert('energy', frame=P.T(t))

f_end = int(round(P.T(T_LAND + 0.06)))
for f in range(1, f_end + 1):
    t = (f - 1) / FPS
    c = ora.pos_at(t)
    h = max(0.1, c.z + SKID)
    fade = 1.0 if t < T_LAND - 0.15 else max(0.0, (T_LAND + 0.06 - t) / 0.21)
    nlegs = 4 if fade > 0.6 else 2
    for k in range(nlegs):
        if R.random() < 0.15:
            continue
        a = 2 * math.pi * k / nlegs + R.uniform(-0.4, 0.4) + t * 3.0
        r0 = R.uniform(0.5, 0.95)
        p0 = c + Vector((r0 * math.cos(a), r0 * math.sin(a), LIFT))
        r1 = r0 * R.uniform(1.0, 1.5)
        p1 = c + Vector((r1 * math.cos(a) - 0.6 * h, r1 * math.sin(a) - 0.25 * h, 0))
        p1.z = 0.02
        bolt_frame(jag_pts(p0, p1, 6, 0.28), f, 0.03 * (0.5 + 0.5 * fade), forks=1 if k % 2 else 0)
    if f % 2 == 0 and t < T_LAND:
        _kit_puff(Vector((c.x - 0.7, c.y + R.uniform(-1.0, 1.0), 0.15)), t, size=0.6, n=1, rise=0.4,
                  life=0.7, color=SAND, opacity=0.2)
        if f % 4 == 0:
            gold_sparks(Vector((c.x - 0.5, c.y + R.uniform(-0.8, 0.8), 0.1)), t, size=0.3, n=3)

dust_wave((0, 0, 0), T_LAND - 0.03, 2.2, 6.0, rings=3, n=22, size=0.7, life=1.1, opacity=0.16)


# --------------------------------------------------------------------------- world anchors on the spire
def ws_point(obj, t, local=(0, 0, 0)):
    return ora.world_at(obj, t, local)


bpy.context.scene.frame_set(int(P.T(T_UF1 + 0.3)))
tw = eye.matrix_world
vs = [tw @ v.co for v in eye.data.vertices]
zc = sum(v.z for v in vs) / len(vs)
eye_center_w = Vector((sum(v.x for v in vs) / len(vs), sum(v.y for v in vs) / len(vs), zc))
eye_anchor = K.empty('EyeAnchor')
eye_anchor.parent = eye
eye_anchor.matrix_parent_inverse = tw.inverted()
eye_anchor.location = eye_center_w
hw = parts['Horns'].matrix_world
hv = [hw @ v.co for v in parts['Horns'].data.vertices]
horn_top = max(v.z for v in hv)
horn_bot = min(v.z for v in hv)
print('EYE CENTER', eye_center_w, 'HORNS z', horn_bot, horn_top)
horn_tips = []      # highest vertices of each horn (left/right in y)
for sgn in (-1, 1):
    side = [v for v in hv if v.y * sgn > 0.4]
    if side:
        top = max(side, key=lambda v: v.z)
        horn_tips.append(top)
horn_feet = []
for sgn in (-1, 1):
    side = [v for v in hv if v.y * sgn > 0.4]
    if side:
        horn_feet.append(min(side, key=lambda v: v.z))
print('HORN TIPS', horn_tips, 'FEET', horn_feet)


def anchor_on(obj, world_pt):
    e = K.empty('Anchor')
    e.parent = obj
    e.matrix_parent_inverse = obj.matrix_world.inverted()
    e.location = world_pt
    return e


tip_anchors = [anchor_on(parts['Horns'], p) for p in horn_tips]
foot_anchors = [anchor_on(parts['Horns'], p) for p in horn_feet]
base_top = Vector((0, 0, 0.45 * NORM_K))
foot_ground = [Vector((p.x * 1.05, p.y * 1.05, base_top.z)) for p in horn_feet]

# eye glow: an inner orb light that breathes, charges before each pulse
M_EYE = mat('EyeGlow', DEEP, 0.0)
orb = K.sphere('EyeOrb', 1.0, M_EYE, seg=(16, 10))
orb.visible_shadow = False
orb.parent = eye_anchor
orb.scale = (0.3,) * 3
for t, v in [(0, 0.0), (T_UF0 + 0.8, 0.0), (T_UF1, 1.2), (T_TURN + 0.1, 1.2), (T_PULSE - 0.02, 3.0),
             (T_PULSE + 0.15, 1.0), (T_PULSE2 - 0.35, 1.2), (T_PULSE2 - 0.02, 2.8), (T_PULSE2 + 0.15, 1.0),
             (6.0, 1.2)]:
    K.key_strength(M_EYE, P.T(t), v)
K.show_between(orb, P.T(T_UF0 + 0.7), P.nf + 2)
eye_light = K.link(bpy.data.objects.new('EyeLight', bpy.data.lights.new('EyeLight', 'POINT')))
eye_light.parent = eye_anchor
eye_light.data.color = GOLD
eye_light.data.shadow_soft_size = 0.4
for t, e in [(0, 0), (T_UF0 + 0.8, 0), (T_UF1, 160), (T_PULSE - 0.05, 700), (T_PULSE + 0.2, 160),
             (T_PULSE2 - 0.05, 650), (T_PULSE2 + 0.2, 160), (6.0, 180)]:
    eye_light.data.energy = e
    eye_light.data.keyframe_insert('energy', frame=P.T(t))

# floating shards: loose stones that rise out of the dust and orbit the horns
M_SHARD = K.pbr_mat('ShardStone', (0.4, 0.36, 0.33), rough=0.45, metal=0.3)
M_SHARD_RIM = mat('ShardRim', GOLD, 1.6)
shards = []
for i in range(5):
    s = K.ico('Shard', 1.0, M_SHARD, sub=0)
    s.scale = (0.16, 0.05, 0.22)
    rim = K.ico('ShardRim', 1.0, M_SHARD_RIM, sub=0)
    rim.visible_shadow = False
    rim.parent = s
    rim.scale = (0.45, 0.45, 0.45)
    rim.location = (0, 0, -0.75)
    shards.append(s)
for i, s in enumerate(shards):
    a0 = 2 * math.pi * i / len(shards) + 0.4
    rad = 1.55 + 0.18 * (i % 2)
    zf = 1.25 + 0.55 * ((i * 3) % 5) / 4
    tr = T_LAND + 0.25 + 0.12 * i
    s.rotation_mode = 'XYZ'
    t = tr
    while t <= 6.05:
        u = ss((t - tr) / 1.1)
        a = a0 + 0.9 * (t - tr)
        r = rad * (0.6 + 0.4 * u)
        z = 0.05 + (zf - 0.05) * u + 0.06 * math.sin(3.0 * t + i)
        s.location = (r * math.cos(a), r * math.sin(a), z)
        s.rotation_euler = (0.4 * math.sin(t + i), 0.3 * math.cos(1.3 * t), a + i)
        s.keyframe_insert('location', frame=P.T(t))
        s.keyframe_insert('rotation_euler', frame=P.T(t))
        t += 0.125
    K.show_between(s, P.T(tr), P.nf + 2)

# threads of gold lightning holding the parts together (thin, flickering)
t = T_UF0 + 0.65
while t < 6.0:
    f = int(round(P.T(t)))
    assembling = t < T_UF1
    for k, (fa, fg) in enumerate(zip(foot_anchors, foot_ground)):
        if R.random() < 0.45:
            pa = ws_point(fa, t)
            bolt_frame(jag_pts(fg, pa, 4, 0.35), f, 0.016, glow=False, nframes=2)
    if t > T_UF0 + 0.95:
        for ta in tip_anchors:
            if R.random() < 0.4:
                pa = ws_point(ta, t)
                pe = ws_point(eye_anchor, t)
                pe = pe + (pa - pe).normalized() * 0.35
                bolt_frame(jag_pts(pa, pe, 5, 0.35), f, 0.016, glow=False, nframes=2)
    for s in shards:
        if R.random() < (0.22 if assembling else 0.12):
            fr_t = t
            sc = bpy.context.scene
            sc.frame_set(f)
            ps = s.matrix_world.translation.copy()
            if s.hide_render:
                continue
            pe = ws_point(eye_anchor, fr_t)
            tgt = pe + (ps - pe).normalized() * 0.4
            bolt_frame(jag_pts(ps, tgt, 5, 0.3), f, 0.013, glow=False, core=False, nframes=2)
    t += 2 / FPS

# charge: crackles converge on the eye before each pulse
for tc0, tc1 in ((T_TURN + 0.1, T_PULSE), (T_PULSE2 - 0.3, T_PULSE2)):
    t = tc0
    while t < tc1:
        f = int(round(P.T(t)))
        pe = ws_point(eye_anchor, t)
        for _ in range(3):
            a = R.uniform(0, 2 * math.pi)
            rr = R.uniform(0.9, 1.5)
            p0 = pe + Vector((rr * math.cos(a), rr * math.sin(a), R.uniform(-0.7, 0.5)))
            bolt_frame(jag_pts(p0, pe, 5, 0.3), f, 0.022, glow=True, nframes=1)
        t += 1 / FPS

# --------------------------------------------------------------------------- the pulse
R0 = 1.8
SPD1, SPD2 = 26.0, 30.0

gm = bpy.data.materials['GroundMat']
nt = gm.node_tree
N = nt.nodes
Lk = nt.links
bsdf = N.get('Principled BSDF')


def node(kind, **kw):
    n = N.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def math_n(op, a=None, b=None, clamp=False):
    n = node('ShaderNodeMath', operation=op)
    n.use_clamp = clamp
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            Lk.new(x, n.inputs[i])
    return n.outputs[0]


def keyed_value(name, keys_):
    n = node('ShaderNodeValue')
    n.label = name
    for t, v in keys_:
        n.outputs[0].default_value = v
        n.outputs[0].keyframe_insert('default_value', frame=P.T(t))
    return n.outputs[0]


def ring_radius(t0, spd, t_end=6.3):
    return [(t0 - 0.01, 0.0), (t0, R0), (t_end, R0 + spd * (t_end - t0))]


coord = node('ShaderNodeTexCoord')
sep = node('ShaderNodeSeparateXYZ')
Lk.new(coord.outputs['Object'], sep.inputs[0])
X, Y = sep.outputs[0], sep.outputs[1]
dist = math_n('SQRT', math_n('ADD', math_n('MULTIPLY', X, X), math_n('MULTIPLY', Y, Y)))

Rp1 = keyed_value('R1', ring_radius(T_PULSE, SPD1))
Rp2 = keyed_value('R2', ring_radius(T_PULSE2, SPD2))
A1 = keyed_value('A1', [(T_PULSE - 0.01, 0.0), (T_PULSE, 1.0), (T_PULSE + 1.3, 0.7), (T_PULSE + 2.4, 0.0)])
A2 = keyed_value('A2', [(T_PULSE2 - 0.01, 0.0), (T_PULSE2, 1.0), (6.1, 0.8)])
for fc in K._fcurves(gm.node_tree.animation_data.action):
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'


def ring(Rv, width, tail):
    d = math_n('SUBTRACT', Rv, dist)                       # >0 inside the ring
    edge = math_n('SUBTRACT', 1.0, math_n('DIVIDE', math_n('ABSOLUTE', d), width), clamp=True)
    edge = math_n('MULTIPLY', edge, edge)
    inside = math_n('GREATER_THAN', d, 0.0)
    tl = math_n('SUBTRACT', 1.0, math_n('DIVIDE', d, tail), clamp=True)
    tl = math_n('MULTIPLY', math_n('MULTIPLY', tl, tl), inside)
    return edge, tl


# concentric ripples trailing the wave (Arcadian: rings, not a grid)
rip = math_n('SUBTRACT', math_n('FRACT', math_n('MULTIPLY', dist, 1.0 / 2.2)), 0.5)
rip = math_n('SUBTRACT', 1.0, math_n('DIVIDE', math_n('ABSOLUTE', rip), 0.07), clamp=True)

e1, t1_ = ring(Rp1, 1.5, 9.0)
e2, t2_ = ring(Rp2, 1.3, 7.0)
s1 = math_n('MULTIPLY', math_n('ADD', math_n('MULTIPLY', e1, 2.2), math_n('MULTIPLY', math_n('MULTIPLY', t1_, math_n('ADD', 0.25, rip)), 0.8)), A1)
s2 = math_n('MULTIPLY', math_n('ADD', math_n('MULTIPLY', e2, 1.9), math_n('MULTIPLY', math_n('MULTIPLY', t2_, math_n('ADD', 0.25, rip)), 0.6)), A2)
total = math_n('ADD', s1, s2)
total = math_n('MULTIPLY', total, math_n('DIVIDE', math_n('SUBTRACT', dist, 1.6), 1.2, clamp=True))
bsdf.inputs['Emission Color'].default_value = (*PALE, 1)
Lk.new(total, bsdf.inputs['Emission Strength'])


def ping_time(d, t0=T_PULSE, spd=SPD1):
    return t0 + max(0.0, d - R0) / spd


# light curtain: a low, translucent band of pale gold riding the wave front
def curtain_mat():
    m = bpy.data.materials.new('O_Curtain')
    m.use_nodes = True
    t_ = m.node_tree
    t_.nodes.clear()
    out = t_.nodes.new('ShaderNodeOutputMaterial')
    gen = t_.nodes.new('ShaderNodeTexCoord')
    spz = t_.nodes.new('ShaderNodeSeparateXYZ')
    t_.links.new(gen.outputs['Generated'], spz.inputs[0])
    inv = t_.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.use_clamp = True
    inv.inputs[0].default_value = 1.0
    t_.links.new(spz.outputs['Z'], inv.inputs[1])
    sq = t_.nodes.new('ShaderNodeMath')
    sq.operation = 'POWER'
    sq.inputs[1].default_value = 2.5
    t_.links.new(inv.outputs[0], sq.inputs[0])
    oi = t_.nodes.new('ShaderNodeObjectInfo')
    mul = t_.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.use_clamp = True
    t_.links.new(sq.outputs[0], mul.inputs[0])
    lw = t_.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    fade = t_.nodes.new('ShaderNodeMath')
    fade.operation = 'SUBTRACT'
    fade.use_clamp = True
    fade.inputs[0].default_value = 1.0
    t_.links.new(lw.outputs['Facing'], fade.inputs[1])
    fa = t_.nodes.new('ShaderNodeMath')
    fa.operation = 'MULTIPLY'
    t_.links.new(oi.outputs['Alpha'], fa.inputs[0])
    t_.links.new(fade.outputs[0], fa.inputs[1])
    t_.links.new(fa.outputs[0], mul.inputs[1])
    em = t_.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*PALE, 1)
    em.inputs['Strength'].default_value = 1.1
    tr = t_.nodes.new('ShaderNodeBsdfTransparent')
    mix = t_.nodes.new('ShaderNodeMixShader')
    t_.links.new(mul.outputs[0], mix.inputs[0])
    t_.links.new(tr.outputs[0], mix.inputs[1])
    t_.links.new(em.outputs[0], mix.inputs[2])
    t_.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


M_CURT = curtain_mat()


def curtain(t0, spd, t_end, height, alpha):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.0, depth=1.0, end_fill_type='NOTHING',
                                        location=(0, 0, 0.5))
    c = bpy.context.active_object
    c.name = 'Curtain'
    bpy.ops.object.transform_apply(location=True)
    c.data.materials.append(M_CURT)
    c.visible_shadow = False
    c.visible_diffuse = False
    c.visible_glossy = False
    f = t0
    while f <= t_end + 1e-6:
        r = R0 + spd * (f - t0)
        u = (f - t0) / (t_end - t0)
        c.scale = (r, r, height * (1 - 0.4 * u))
        c.location = (0, 0, -0.1)
        c.color = (1, 1, 1, alpha * (1 - u) ** 1.3 * min(1.0, (f - t0) / 0.15))
        c.keyframe_insert('scale', frame=P.T(f))
        c.keyframe_insert('color', frame=P.T(f))
        f += 0.05
    c.keyframe_insert('location', frame=P.T(t0))
    K.set_interp(c, 'LINEAR')
    K.show_between(c, P.T(t0), P.T(t_end))
    return c


curtain(T_PULSE, SPD1, T_PULSE + 1.6, 2.2, 0.55)
curtain(T_PULSE2, SPD2, 6.1, 1.9, 0.38)

# ring of light bursting off the eye at the pulse
M_HALO = mat('Halo', PALE, 1.6, alpha=0.5)
for tp_ in (T_PULSE, T_PULSE2):
    pe = ws_point(eye_anchor, tp_)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.025, major_segments=64, minor_segments=6,
                                     location=pe)
    h = bpy.context.active_object
    h.name = 'EyeHalo'
    h.data.materials.append(M_HALO)
    h.visible_shadow = False
    for dt, s in [(0.0, 0.3), (0.12, 2.2), (0.3, 4.0)]:
        h.scale = (s, s, s)
        h.keyframe_insert('scale', frame=P.T(tp_ + dt))
    K.show_between(h, P.T(tp_), P.T(tp_ + 0.3))
    P.light(pe, tp_, GOLD, energy=1800, dur=0.3, radius=0.5)

# --------------------------------------------------------------------------- the hidden Terrans
# creeping up the valley toward the spire, unseen (fog of war) until the wave passes them
TERRANS = [
    ('lancer', (21.0, 4.5), (17.0, 3.0)),
    ('lancer', (23.5, 10.0), (19.0, 8.2)),
    ('javelin', (17.0, 13.5), (13.8, 11.2)),
    ('bulwark', (27.0, 15.5), (23.0, 13.0)),
]
units = []
loaded = {}
for i, (nm, a0, a1) in enumerate(TERRANS):
    a = P.load(nm, at=a0, label=f'{nm}{i}')      # separate loads: outlines need own objects
    gz0, gz1 = P.ground_z(*a0), P.ground_z(*a1)
    a.path([(0.0, (a0[0], a0[1], gz0)), (6.0, (a1[0], a1[1], gz1))], interp='LINEAR')
    units.append(a)

M_OUT = mat('Outline', GOLD, 2.6)
M_OUT_DIM = mat('OutlineDim', GOLD, 1.3)


def outline_mat(name, strength_keys):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t_ = m.node_tree
    t_.nodes.clear()
    out = t_.nodes.new('ShaderNodeOutputMaterial')
    geo = t_.nodes.new('ShaderNodeNewGeometry')
    em = t_.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*GOLD, 1)
    tr = t_.nodes.new('ShaderNodeBsdfTransparent')
    mix = t_.nodes.new('ShaderNodeMixShader')
    t_.links.new(geo.outputs['Backfacing'], mix.inputs[0])
    t_.links.new(tr.outputs[0], mix.inputs[1])
    t_.links.new(em.outputs[0], mix.inputs[2])
    t_.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    for t, v in strength_keys:
        K.key_strength(m, P.T(t), v)
    return m


def add_outline(a, t_rev, t_end):
    """Inverted-hull gold outline around every mesh of the unit, snapping on at t_rev."""
    m = outline_mat(a.name + '_Outline', [(0, 0), (t_rev - 0.01, 0), (t_rev, 3.2), (t_rev + 0.25, 1.6),
                                          (t_end, 1.6)])
    k = a.root.matrix_world.to_scale()
    for ms in list(a.meshes):
        c = ms.copy()
        K.link(c)
        c.parent = ms
        c.matrix_parent_inverse.identity()
        c.location = (0, 0, 0)
        c.rotation_euler = (0, 0, 0)
        c.rotation_quaternion = (1, 0, 0, 0)
        c.scale = (1, 1, 1)
        c.animation_data_clear()
        c.data = ms.data
        for s in c.material_slots:
            s.link = 'OBJECT'
            s.material = m
        sc_ = ms.matrix_world.to_scale()
        th = 0.07 / max(1e-4, (sc_.x + sc_.y + sc_.z) / 3)
        wl = c.modifiers.new('Weld', 'WELD')
        wl.merge_threshold = 0.002 / max(1e-4, (sc_.x + sc_.y + sc_.z) / 3)
        dp = c.modifiers.new('Hull', 'DISPLACE')
        dp.direction = 'NORMAL'
        dp.mid_level = 0.0
        dp.strength = th
        c.visible_shadow = False
        c.visible_diffuse = False
        c.visible_glossy = False
        K.show_between(c, P.T(t_rev), P.T(t_end))
    return m


mark_t = {}
for i, a in enumerate(units):
    t = T_PULSE
    for _ in range(4):
        p = a.pos_at(t)
        t = ping_time(math.hypot(p.x, p.y))
    mark_t[i] = t
print('REVEAL TIMES', mark_t)

# gold strikes from Arcadian guns far behind the spire
T_HITS = {0: 4.45, 2: 4.62, 1: 4.8}
for i, th in T_HITS.items():
    a = units[i]
    tgt = a.pos_at(th) + Vector((0, 0, 0.7))
    src = Vector((-34.0 + 5 * i, -20.0, 17.0))
    dur = 0.5
    M_SH = mat('Strike', GOLD, 2.6)
    sh = K.sphere('StrikeOrb', 1.0, M_SH, seg=(10, 8))
    sh.visible_shadow = False
    sh.rotation_mode = 'QUATERNION'
    n = 8
    for k in range(n + 1):
        u = k / n
        p = src.lerp(tgt, u) + Vector((0, 0, 9.0 * u * (1 - u)))
        u2 = min(1.0, u + 0.03)
        p2 = src.lerp(tgt, u2) + Vector((0, 0, 9.0 * u2 * (1 - u2)))
        sh.location = p
        sh.rotation_quaternion = (p2 - p).to_track_quat('X', 'Z') if (p2 - p).length > 1e-5 else Quaternion()
        sh.scale = (1.6, 0.22, 0.22)
        sh.keyframe_insert('location', frame=P.T(th - dur + dur * u))
        sh.keyframe_insert('rotation_quaternion', frame=P.T(th - dur + dur * u))
    K.set_interp(sh, 'LINEAR')
    K.show_between(sh, P.T(th - dur), P.T(th) + 1)
    # crackling sheath on the last stretch
    t = th - 0.2
    while t < th:
        f = int(round(P.T(t)))
        u = (t - (th - dur)) / dur
        p = src.lerp(tgt, u) + Vector((0, 0, 9.0 * u * (1 - u)))
        u0 = max(0, u - 0.12)
        p0 = src.lerp(tgt, u0) + Vector((0, 0, 9.0 * u0 * (1 - u0)))
        bolt_frame(jag_pts(p0, p, 6, 0.12), f, 0.04, nframes=1)
        t += 1 / FPS
    gold_sparks(tgt, th, 1.0)
    # gold lightning crawling over the hull for an instant, then it blows
    for k in range(3):
        bolt_frame(jag_pts(tgt + Vector((0, 0, 0.6)), tgt + Vector((R.uniform(-2, 2), R.uniform(-2, 2), -0.6)), 6, 0.3),
                   int(round(P.T(th))) + k, 0.04, forks=1, nframes=1)
    P.light(tgt + Vector((0, 0, 1)), th, GOLD, energy=2500, dur=0.25, radius=0.8)
    a.destroy(th + 0.04, size=2.4)
    P.cam_shake(th, 0.05, 0.3)

for i, a in enumerate(units):
    t_end = (a.alive_until + 1 / FPS) if a.alive_until is not None else 6.5
    a.appear(mark_t[i])
    add_outline(a, mark_t[i], t_end)
    p = a.pos_at(mark_t[i])
    P.light(p + Vector((0, 0, 2.0)), mark_t[i], GOLD, energy=900, dur=0.3, radius=1.0)
    gold_sparks(p + Vector((0, 0, 1.0)), mark_t[i], 0.5, n=5)

# --------------------------------------------------------------------------- camera
P.camera([
    (0.0, (-21.0, -17.0, 1.1), ora.pos_at(0.0) + Vector((0, 0, 0.9)), 30),
    (0.7, (-13.0, -12.0, 1.2), ora.pos_at(0.7) + Vector((0, 0, 0.9)), 30),
    (1.4, (-4.6, -6.4, 1.0), (0.0, 0.0, 1.0), 30),
    (2.2, (-4.4, -10.6, 0.9), (0.0, 0.0, 3.5), 24),
    (2.9, (1.2, -7.4, 0.8), (0.0, 0.0, 3.0), 28),
    (3.25, (1.6, -6.2, 1.4), (0.2, 0.0, 3.0), 29),
    (3.75, (-4.5, -8.0, 5.0), (10.0, 5.0, 0.8), 24),
    (4.3, (-6.0, -7.0, 5.6), (15.0, 7.5, 0.6), 26),
    (4.85, (-5.5, -6.5, 4.6), (16.0, 8.5, 1.0), 28),
    (6.0, (-3.5, -5.0, 1.0), (2.45, 0.35, 2.6), 22),
], shake=0.015)
P.cam_shake(T_LAND, 0.15, 0.35)
P.cam_shake(T_PULSE, 0.06, 0.3)

for mtl in bpy.data.materials:
    if mtl.name.startswith('Core') and 'emit_node' in mtl.keys():
        em = mtl.node_tree.nodes[mtl['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.38, 0.05, 1)
        em.inputs['Strength'].default_value = 2.4

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.4, dur=T_LAND)      # glide in
P.sfx(T_UF0, 'power_up_arc', gain=0.7)                # unfurl
P.sfx(T_TURN - 0.05, 'servo', gain=0.45, rate=0.75)   # eye turns
P.sfx(T_PULSE - 0.35, 'charge_gold', gain=0.8)
P.sfx(T_PULSE, 'shockwave', gain=0.85)                # reveal pulse
P.sfx(T_PULSE2 - 0.35, 'charge_gold', gain=0.6, rate=1.1)
P.sfx(T_PULSE2, 'shockwave', gain=0.7, rate=1.1)
for _i, _t in enumerate(sorted(T_HITS.values())):     # hidden units light up
    P.sfx(_t - 0.03, 'lock_pulse', gain=0.5, rate=1.0 + 0.08 * _i)

P.render()
