"""Metal Siphon (Arcadian research-economy structure): a field of blue metal crystals at violet
dusk. The packed Siphon disc comes down out of the sky like a spinning seed, circling the
crystals on legs of gold lightning, and settles beside the outcrop. Then it comes apart and
floats: the base ring blooms on the ground, the horns lift off with air under them, the spire
rises above them and turns, and the basin drifts out over its own gap, facing the crystals.
The horn tips crackle and touch the crystals, which start to glow from inside. The metal is
drawn up out of them as liquid gold light: three threads lift off the outcrop and two small
crystals, braid together into one twisting rope that arcs over and whirls down in a vortex into
the floating basin, which brightens and ripples as it fills. A small crystal is drained to
nothing. End low beside the basin, parts hovering, the gold river still pouring in.

Timeline (s): 0-1.55 spiral descent on lightning legs | 1.55 settle + dust ring |
1.65-2.95 float-apart unfold | 2.95-3.3 horn taps, crystals kindle | 3.3 threads lift |
3.9 vortex reaches the basin, basin fills + ripples | 4.2-5.6 small crystal drained |
4.6-6 low hero push-in."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_metal_siphon', seconds=6.0, seed=23)
FPS = P.fps
R = P.rnd

GOLD = COL['arc_gold']
DEEP = (1.0, 0.42, 0.03)
LIQ = (1.0, 0.6, 0.14)        # liquid-gold core

DEP = (0.6, -7.8)             # the big outcrop, in front of the basin (basin faces -y)
SMALL = [((-3.6, -6.4), 0.34, 140), ((4.0, -5.6), 0.3, 260)]

P.env('alien', sun=(64, 0, -150), sun_energy=3.6, props=30,
      clear=[(0, -2, 10), (0, -8, 6), (7, -11, 5), (-6, -8, 5)])
P.flatten(0, -3, 11)
bpy.context.view_layer.update()

SAND = tuple(min(1, c * 1.9) for c in P.palette['g1'])


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('S_' + key, col, strength, alpha=alpha)
    return _mats[key]


M_BOLT = mat('Bolt', GOLD, 2.4)
M_CORE = mat('BoltCore', (1.0, 0.7, 0.3), 2.8)
M_GLOW = mat('BoltGlow', DEEP, 1.1, alpha=0.22)

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


def add_light(name, loc, col, keys, radius=0.4, parent=None):
    L = K.link(bpy.data.objects.new(name, bpy.data.lights.new(name, 'POINT')))
    L.location = loc
    if parent is not None:
        L.parent = parent
    L.data.color = col
    L.data.shadow_soft_size = radius
    for t, e in keys:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=P.T(t))
    return L


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


# --------------------------------------------------------------------------- crystals
dep = P.load('deposit_metal', at=DEP, heading=200, size=4.6)
dep.root.location.z = P.ground_z(*DEP) - 0.15
smalls = []
for (x, y), s, h in SMALL:
    c = P.copy(dep, at=(x, y), heading=h)
    c.root.scale = (s, s, s)
    c.root.location.z = P.ground_z(x, y) - 0.08
    smalls.append(c)
for (x, y), s, h in [((-6.5, -11.0), 0.3, 40), ((6.8, -10.5), 0.26, 310), ((-7.0, 2.5), 0.24, 90)]:
    c = P.copy(dep, at=(x, y), heading=h)
    c.root.scale = (s, s, s)
    c.root.location.z = P.ground_z(x, y) - 0.08
gem = None
for o in dep.meshes:
    for sl in o.material_slots:
        if sl.material and 'Gem' in sl.material.name:
            gem = sl.material
T_TAP = 2.95
T_FLOW = 3.2
if gem is not None:
    gb = gem.node_tree.nodes.get('Principled BSDF')
    gb.inputs['Emission Color'].default_value = (0.55, 0.62, 1.0, 1)
    for t, v in [(0, 0.0), (T_TAP, 0.0), (T_TAP + 0.2, 0.9), (T_FLOW, 0.5), (3.7, 0.9), (4.2, 0.55),
                 (4.7, 0.9), (5.2, 0.55), (5.7, 0.9), (6.1, 0.6)]:
        gb.inputs['Emission Strength'].default_value = v
        gb.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))

bpy.context.view_layer.update()
dlo, dhi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for o in dep.meshes:
    lo, hi = bbox(o)
    dlo = Vector(map(min, dlo, lo))
    dhi = Vector(map(max, dhi, hi))
print('DEPOSIT bbox', dlo, dhi)

# --------------------------------------------------------------------------- the Siphon
T_LAND = 1.55
T_UF0, T_UF1 = 1.65, 2.95
sip = P.load('metal_siphon', at=(0, 0), heading=0, label='siphon')
bpy.context.view_layer.update()
parts = sip.parts
KS = parts['KeshMetalSiphon'].matrix_world.to_scale().x    # model units -> metres
print('KS', KS)

# spire yaw joint (unfold owns the pivot's quaternion)
piv = parts['TurretPivot']
spire = parts['Turret']
syaw = K.empty('SpireYaw')
syaw.parent = piv
syaw.rotation_mode = 'XYZ'
mpi = spire.matrix_parent_inverse.copy()
spire.parent = syaw
spire.matrix_parent_inverse = mpi

sip.unfold(T_UF0, T_UF1, stagger=0.1)

# floating gaps: delta_location on top of the unfold keys (metres / KS)
GAPS = {'Basin': (0.34, 0.035, 0.62, 0.3, (0, -0.12)), 'Horns': (0.26, 0.03, 0.5, 1.4, (0, 0)),
        'TurretPivot': (0.55, 0.06, 0.7, 2.5, (0, 0))}
OVERSHOOT = {'Basin': 0.35, 'Horns': 0.55, 'TurretPivot': 0.9}
START = {'Basin': T_UF0 + 0.35, 'Horns': T_UF0 + 0.2, 'TurretPivot': T_UF0 + 0.3}
for n, (gap, amp, hz, ph, dxy) in GAPS.items():
    o = parts[n]
    t0 = START[n]
    for t, dz, dx in [(0, 0, 0), (t0, 0, 0), (T_UF1 - 0.35, gap + OVERSHOOT[n], 1),
                      (T_UF1 + 0.05, gap - 0.04, 1), (T_UF1 + 0.3, gap, 1)]:
        o.delta_location = (dxy[0] * dx / KS, dxy[1] * dx / KS, dz / KS)
        o.keyframe_insert('delta_location', frame=P.T(t))
    t = T_UF1 + 0.55
    while t <= 6.2:
        o.delta_location = (dxy[0] / KS, dxy[1] / KS, (gap + amp * math.sin(2 * math.pi * hz * (t - T_UF1 - 0.3) + ph)) / KS)
        o.keyframe_insert('delta_location', frame=P.T(t))
        t += 0.25
    K.set_interp(o, 'BEZIER')

# spire turns: slow while assembling, quicker once it drinks
for t, deg in [(0, 0), (T_UF0 + 0.3, 0), (T_UF1, 70), (T_FLOW, 110), (6.2, 110 + 95 * (6.2 - T_FLOW))]:
    syaw.rotation_euler.z = math.radians(deg)
    syaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))

# spiral descent: circles down around the crystals, spinning like a seed
root = sip.root
root.rotation_mode = 'XYZ'
desc = [(0.0, (-5.5, 3.5, 7.2), 8), (0.45, (-5.8, -3.0, 5.3), 10), (0.85, (-0.5, -5.2, 3.4), 9),
        (1.2, (3.0, -1.6, 1.5), 6), (1.42, (0.8, 0.3, 0.45), 2), (T_LAND, (0.0, 0.0, 0.0), 0)]
for t, p, tilt in desc:
    u = t / T_LAND
    root.location = p
    # tilt the disc into the turn (towards the circle centre), spin decelerating to heading 0
    a = math.atan2(-p[1] - 2.0, -p[0])
    root.rotation_euler = (math.radians(tilt) * math.sin(a), -math.radians(tilt) * math.cos(a),
                           math.radians(-560 * (1 - ss(u)) ** 1.5))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
root.location = (0, 0, -0.05)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.06))
root.location = (0, 0, 0)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.22))
K.set_interp(root, 'BEZIER')

# lightning legs under the descending disc
gl = add_light('LiftLight', (0, 0, -0.1), GOLD, [(0.0, 900), (1.3, 900), (T_LAND, 300), (T_LAND + 0.12, 0)],
               radius=1.5, parent=root)
f_end = int(round(P.T(T_LAND + 0.05)))
for f in range(1, f_end + 1):
    t = (f - 1) / FPS
    c = sip.pos_at(t)
    h = max(0.1, c.z)
    fade = 1.0 if t < T_LAND - 0.15 else max(0.0, (T_LAND + 0.05 - t) / 0.2)
    nlegs = 3 if fade > 0.6 else 2
    for k in range(nlegs):
        if R.random() < 0.15:
            continue
        a = 2 * math.pi * k / nlegs + R.uniform(-0.4, 0.4) + t * 5.0
        r0 = R.uniform(0.5, 0.9)
        p0 = c + Vector((r0 * math.cos(a), r0 * math.sin(a), 0.08))
        r1 = r0 + 0.35 * h * R.uniform(0.6, 1.2)
        p1 = Vector((c.x + r1 * math.cos(a), c.y + r1 * math.sin(a), 0.02))
        p1.z = P.ground_z(p1.x, p1.y) + 0.02
        bolt_frame(jag_pts(p0, p1, 6 + int(h), 0.28), f, 0.03 * (0.5 + 0.5 * fade), forks=1 if k % 2 else 0)
    if f % 3 == 0 and c.z < 3.5:
        _kit_puff(Vector((c.x + R.uniform(-1, 1), c.y + R.uniform(-1, 1), P.ground_z(c.x, c.y) + 0.15)), t,
                  size=0.6, n=1, rise=0.4, life=0.8, color=SAND, opacity=0.16)
dust_wave((0, 0, 0), T_LAND - 0.03, 2.2, 5.5, rings=3, n=22, size=0.7, life=1.1, opacity=0.16)
gold_sparks(Vector((0, 0, 0.15)), T_LAND, size=0.5, n=8)
P.cam_shake(T_LAND, 0.05, 0.3)

# assembly threads: thin lightning between the base and the lifting parts
bpy.context.scene.frame_set(int(P.T(5.0)))
bpy.context.view_layer.update()
blo, bhi = bbox(parts['Basin'])
hlo, hhi = bbox(parts['Horns'])
slo, shi = bbox(spire)
BASIN_C = Vector(((blo.x + bhi.x) / 2, (blo.y + bhi.y) / 2, bhi.z))
BASIN_R = (bhi.x - blo.x) / 2
print('BASIN', blo, bhi, 'HORNS', hlo, hhi, 'SPIRE', slo, shi)
hw = parts['Horns'].matrix_world
hv = [hw @ v.co for v in parts['Horns'].data.vertices]
tips = []
for sgn in (-1, 1):
    side = [v for v in hv if v.x * sgn > 0.5]
    tips.append(max(side, key=lambda v: v.z))
print('HORN TIPS', tips)


def anchor_on(obj, world_pt):
    e = K.empty('Anchor')
    e.parent = obj
    e.matrix_parent_inverse = obj.matrix_world.inverted()
    e.location = world_pt
    return e


tip_anchors = [anchor_on(parts['Horns'], p) for p in tips]
basin_anchor = anchor_on(parts['Basin'], BASIN_C)
foot_pts = [Vector((sg * 1.0, 0.2, 0.3)) for sg in (-1, 1)] + [Vector((0, -1.5, 0.4))]

t = T_UF0 + 0.5
while t < 6.0:
    f = int(round(P.T(t)))
    if R.random() < (0.8 if t < T_UF1 + 0.2 else 0.35):
        bpy.context.scene.frame_set(f)
        k = R.randint(0, 2)
        tgt = tip_anchors[k].matrix_world.translation if k < 2 else basin_anchor.matrix_world.translation
        if k < 2:
            tgt = tgt + Vector((0, 0, -(tips[k].z - hlo.z) + 0.05))     # under the horn foot
        else:
            tgt = tgt + Vector((0, 0, -0.35))
        bolt_frame(jag_pts(foot_pts[k], tgt, 4, 0.4), f, 0.014, glow=False, nframes=2)
    t += 1 / FPS * 2

# --------------------------------------------------------------------------- the tap
CRYS = [Vector((DEP[0] - 0.1, DEP[1] + 0.6, dhi.z * 0.82))]
for c in smalls:
    lo_, hi_ = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in c.meshes:
        a_, b_ = bbox(o)
        lo_ = Vector(map(min, lo_, a_))
        hi_ = Vector(map(max, hi_, b_))
    CRYS.append(Vector(((lo_.x + hi_.x) / 2, (lo_.y + hi_.y) / 2, hi_.z * 0.8)))
print('CRYS', CRYS)

# horn tips reach out and touch the crystals: a few forked bolts, then a steady thin grip
for i, t in enumerate([T_TAP, T_TAP + 0.1, T_TAP + 0.2]):
    f = int(round(P.T(t)))
    bpy.context.scene.frame_set(f)
    for k, ta in enumerate(tip_anchors):
        p0 = ta.matrix_world.translation
        p1 = CRYS[0] + Vector((R.uniform(-0.6, 0.6), R.uniform(-0.3, 0.3), R.uniform(-0.6, 0.2)))
        bolt_frame(jag_pts(p0, p1, 18, 0.12), f, 0.022, forks=2, nframes=2)
gold_sparks(CRYS[0], T_TAP + 0.05, size=0.6, n=10)
add_light('CrysLight', CRYS[0] + Vector((0, 1.0, 0.2)), (1.0, 0.6, 0.25),
          [(0, 0), (T_TAP, 0), (T_TAP + 0.1, 700), (T_FLOW, 250), (6.0, 300)], radius=1.0)

# --------------------------------------------------------------------------- the gold river
M_RIV = mat('River', (1.0, 0.55, 0.1), 2.2)
M_RIVG = mat('RiverGlow', GOLD, 0.9, alpha=0.16)
M_MOTE = mat('Mote', (1.0, 0.5, 0.08), 2.4)
BTOP = BASIN_C + Vector((0, 0, 1.5))
MEET = Vector((DEP[0] * 0.6, DEP[1] + 1.9, dhi.z + 0.7))
APEX = (MEET + BTOP) / 2 + Vector((0, 0, 1.0))


def bez(a, b, c, u):
    return a * (1 - u) ** 2 + b * 2 * u * (1 - u) + c * u * u


def strand_pts(j, n=180):
    """Lift-off from crystal j to the meeting point, braided arc to the top of the vortex, then a
    narrowing whirlpool down into the basin."""
    S = CRYS[j]
    ph = 2 * math.pi * j / 3
    pts = []
    for i in range(n + 1):
        u = i / n
        if u < 0.22:
            v = u / 0.22
            lift = S + Vector((0, 0, 1.4)) + (MEET - S) * 0.3
            p = bez(S, lift, MEET, v)
            # spiral off the crystal
            r = 0.12 * math.sin(math.pi * v)
            a = ph + v * 3 * math.pi
            p = p + Vector((math.cos(a) * r, math.sin(a) * r, 0))
        elif u < 0.68:
            v = (u - 0.22) / 0.46
            p = bez(MEET, APEX, BTOP, v)
            tan = (bez(MEET, APEX, BTOP, min(1, v + 0.01)) - bez(MEET, APEX, BTOP, max(0, v - 0.01))).normalized()
            n1 = tan.cross(Vector((0, 0, 1))).normalized()
            n2 = n1.cross(tan).normalized()
            r = 0.2 + 0.1 * math.sin(math.pi * v)
            a = ph + 4 * math.pi + v * 8 * math.pi
            # blend the braid in from the meeting point
            r *= ss(v / 0.1) if v < 0.1 else 1.0
            p = p + (n1 * math.cos(a) + n2 * math.sin(a)) * r
        else:
            v = (u - 0.68) / 0.32
            a = ph + 10 * math.pi + v * 5 * math.pi
            r = (BASIN_R * 0.75) * (1 - v) ** 0.8 + 0.04
            z = BTOP.z + (BASIN_C.z - 0.12 - BTOP.z) * (v ** 0.9)
            # ease in from the braid: start radius 0.26 around BTOP
            r0 = 0.26
            rr = r0 + (r - r0) * ss(v / 0.25)
            p = Vector((BASIN_C.x + math.cos(a) * rr, BASIN_C.y + math.sin(a) * rr, z))
        pts.append(p)
    return pts


def arc_param(pts):
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + (pts[i] - pts[i - 1]).length)
    return d


def at_len(pts, d, s):
    s = max(0.0, min(d[-1], s))
    lo, hi = 0, len(d) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if d[mid] <= s:
            lo = mid
        else:
            hi = mid
    w = (s - d[lo]) / max(1e-6, d[hi] - d[lo])
    return pts[lo].lerp(pts[hi], w)


T_START = [T_FLOW, T_FLOW + 0.1, T_FLOW + 0.16]
SPEED = 11.0                   # m/s along the river
strands = []
for j in range(3):
    pts = strand_pts(j)
    d = arc_param(pts)
    strands.append((pts, d))
    t0 = T_START[j]
    dur = d[-1] / SPEED
    print('strand', j, 'len', round(d[-1], 2), 'dur', round(dur, 2))
    for m_, rad in ((M_RIV, 0.03 if j == 0 else 0.022), (M_RIVG, 0.11 if j == 0 else 0.085)):
        b = K.polyline('River', pts, rad, m_)
        b.visible_shadow = False
        b.data.bevel_resolution = 2
        b.data.bevel_factor_mapping_end = 'SPLINE'
        b.data.bevel_factor_end = 0.0
        b.data.keyframe_insert('bevel_factor_end', frame=P.T(t0))
        b.data.bevel_factor_end = 1.0
        b.data.keyframe_insert('bevel_factor_end', frame=P.T(t0 + dur))
        fc = [f for f in K._fcurves(b.data.animation_data.action)][0]
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        K.show_between(b, P.T(t0), P.nf + 2)
    # motes riding the river
    tt = t0
    while tt < 6.05:
        o = K.sphere('Mote', 1.0, M_MOTE, seg=(8, 6))
        o.visible_shadow = False
        s0 = R.uniform(0.035, 0.06) * (1.2 if j == 0 else 1.0)
        o.scale = (s0,) * 3
        jit = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))) * 0.06
        f0 = int(math.floor(P.T(tt)))
        fl = f0
        while True:
            el = (fl - P.T(tt)) / FPS
            s = SPEED * el
            o.location = at_len(pts, d, s) + jit
            o.keyframe_insert('location', frame=fl)
            if s >= d[-1] or fl > P.nf + 2:
                break
            fl += 2
        K.set_interp(o, 'LINEAR')
        K.show_between(o, f0, fl)
        tt += R.uniform(0.025, 0.045) * (1.0 if j == 0 else 1.6)

# river glow pulses
for t, v in [(T_FLOW, 2.0), (4.0, 1.6), (4.5, 2.1), (5.0, 1.6), (5.5, 2.1), (6.0, 1.7)]:
    K.key_strength(M_RIV, P.T(t), v)
T_FILL = T_FLOW + strands[0][1][-1] / SPEED - 0.05
print('T_FILL', T_FILL)
add_light('RiverLight', APEX, GOLD, [(0, 0), (T_FLOW + 0.3, 0), (T_FLOW + 0.6, 350), (6.0, 400)], radius=1.5)

# --------------------------------------------------------------------------- the basin fills
M_POOL = mat('Pool', LIQ, 0.0, alpha=0.75)
pool = K.sphere('Pool', 1.0, M_POOL, seg=(24, 8))
pool.visible_shadow = False
pool.parent = basin_anchor
pool.location = (0, 0, -0.1)
pool.scale = (BASIN_R * 0.82, BASIN_R * 0.82, 0.03)
for t, v in [(0, 0.0), (T_FILL - 0.1, 0.0), (T_FILL + 0.3, 1.6), (T_FILL + 0.8, 1.2), (5.0, 1.9),
             (5.4, 1.4), (6.0, 2.0)]:
    K.key_strength(M_POOL, P.T(t), v)
add_light('BasinLight', (0, 0, 0.6), GOLD, [(0, 0), (T_FILL - 0.1, 0), (T_FILL + 0.3, 500), (6.0, 650)],
          radius=0.8, parent=basin_anchor)
M_RING = mat('Ripple', GOLD, 2.0, alpha=0.6)
for k, t in enumerate([T_FILL, T_FILL + 0.45, T_FILL + 0.9, T_FILL + 1.35, T_FILL + 1.8]):
    if t > 5.95:
        break
    ring = K.polyline('Ripple', [Vector((math.cos(2 * math.pi * i / 32), math.sin(2 * math.pi * i / 32), 0))
                                 for i in range(33)], 0.03, M_RING)
    ring.visible_shadow = False
    ring.parent = basin_anchor
    ring.location = (0, 0, -0.06)
    f0 = P.T(t)
    for fr, sc in [(f0, 0.1), (f0 + 0.6 * FPS, BASIN_R * 0.8)]:
        ring.scale = (sc, sc, 1)
        ring.keyframe_insert('scale', frame=fr)
    K.show_between(ring, f0, f0 + 0.6 * FPS)
gold_sparks(BASIN_C + Vector((0, 0, 0.1)), T_FILL, size=0.4, n=8)

# --------------------------------------------------------------------------- a small crystal drained
drain = smalls[1]
s0 = drain.root.scale.x
for t, k in [(0, 1.0), (4.2, 1.0), (5.0, 0.6), (5.6, 0.0)]:
    drain.root.scale = (s0 * max(k, 0.001),) * 3
    drain.root.keyframe_insert('scale', frame=P.T(t))
gold_sparks(CRYS[2], 5.55, size=0.4, n=8)

# --------------------------------------------------------------------------- camera
P.camera([
    (0.0, (7.0, -13.0, 1.0), (-3.5, 0.5, 5.0), 28),
    (0.8, (6.8, -12.0, 1.2), (-0.8, -4.0, 3.2), 28),
    (1.55, (7.2, -9.0, 1.8), (0.0, -0.6, 1.0), 30),
    (2.4, (7.8, -4.2, 2.5), (0.0, -0.8, 1.9), 30),
    (2.95, (9.4, -3.6, 2.8), (0.2, -3.2, 2.1), 26),
    (3.9, (10.8, -3.0, 3.0), (0.2, -4.0, 2.2), 26),
    (4.8, (10.0, -2.2, 2.3), (0.0, -3.2, 2.0), 25),
    (6.0, (8.8, -1.6, 1.85), (-0.3, -2.8, 1.85), 26),
], shake=0.012)

P.render()
