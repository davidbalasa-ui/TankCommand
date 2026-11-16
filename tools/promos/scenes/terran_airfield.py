"""Airfield (Terran air structure): a tracked carrier hauls the packed airfield across the desert
and slews to a stop. It unfolds: the deck spreads out, hangar, control tower and fuel tanks
rise, the hangar swings round to face the runway and the tower dish starts turning. The hangar's
end wall drops forward as a ramp, a Falcon taxis out into the light, spools its engine on the
neon catapult lane and is flung down the deck, lifting off the edge and screaming over the
camera. End wide behind the tower: the Falcon climbing away in a banking turn, the dish turning,
and the next Falcon already nosing out of the hangar.

Timeline (s): 0-1.3 carrier drives in (low tracking camera) | 1.3 stop + dust | 1.45-2.75 unfold,
camera orbits up and round | 2.7-3.1 hangar swivels | 2.9 dish spins up | 3.15-3.5 ramp door
drops | 3.35-4.0 Falcon taxis out | 4.0-4.25 spool on the catapult | 4.25 launch | ~4.55 liftoff |
~4.85 over camera | 4.917 cut: wide hero frame, Falcon banks away, second Falcon rolls out."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_airfield', seconds=6.0, seed=5)
FPS = P.fps
NF = P.nf
R = P.rnd
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
P.env('desert', sun=(64, 0, -38), sun_energy=4.2, props=34,
      clear=[(0, 0, 12), (-12, -1, 7), (0, 14, 10), (0, 30, 12)])
P.flatten(0, 0, 10)
P.flatten(-12, -1, 6)
P.flatten(0, 9, 7)
SAND = (0.62, 0.52, 0.40)
DECK = 0.19


def ss(x):
    return K.smoothstep(x)


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    child.matrix_world = mw


# ------------------------------------------------------------------------------ the airfield
af = P.load('terran_airfield', at=(0, 0), heading=0, label='airfield')
bpy.context.view_layer.update()
TAB = af.parts['TerranAirBase']
hangar = af.parts['Hangar']

# --- cut the hangar's east end wall loose: it becomes a drop-down ramp door
mw = hangar.matrix_world.copy()
n3 = mw.to_3x3().inverted().transposed()
bm = bmesh.new()
bm.from_mesh(hangar.data)
door_faces = []
for f in bm.faces:
    c = mw @ f.calc_center_median()
    n = (n3 @ f.normal).normalized()
    if abs(n.x) > 0.9 and c.x > -0.92 and 0.15 < c.z < 1.85 and -3.2 < c.y < -1.0:
        door_faces.append(f.index)
bm2 = bm.copy()
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in door_faces], context='FACES')
bm.to_mesh(hangar.data)
bm.free()
bm2.faces.ensure_lookup_table()
keep = set(door_faces)
bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.index not in keep], context='FACES')
bm2.transform(mw)
HINGE = Vector((-0.74, -2.1, DECK + 0.01))
bmesh.ops.translate(bm2, verts=bm2.verts, vec=-HINGE)
door_me = bpy.data.meshes.new('HangarDoor')
bm2.to_mesh(door_me)
bm2.free()
for m in hangar.data.materials:
    door_me.materials.append(m)
door = K.link(bpy.data.objects.new('HangarDoor', door_me))
door.location = HINGE
door.rotation_mode = 'XYZ'
parent_keep(door, hangar)
print('door faces', len(door_faces))

# --- hangar swivel: the hangar rotates about its own centre to face the runway (+Y)
lo = Vector((1e9,) * 3)
hi = -lo
for c in hangar.bound_box:
    w = mw @ Vector(c)
    lo = Vector(map(min, lo, w))
    hi = Vector(map(max, hi, w))
HC = (lo + hi) / 2
HC.z = 0
c_loc = TAB.matrix_world.inverted() @ HC
swv = K.empty('HangarSwivel')
swv.parent = TAB
swv.location = c_loc
swv.rotation_mode = 'XYZ'
hangar.parent = swv
hangar.matrix_parent_inverse = Matrix.Translation(-c_loc)
bpy.context.view_layer.update()
LANE_X = HC.x            # the hangar mouth after the swivel is centred on this x
MOUTH_Y = HC.y + (hi.x - lo.x) / 2
print('hangar centre', HC, 'mouth y', MOUTH_Y)

# swivel axis in TAB space = TAB's local axis mapping to world Z
zax = TAB.matrix_world.inverted().to_3x3() @ Vector((0, 0, 1))
zax.normalize()
T_SW0, T_SW1 = 2.72, 3.1
for t, deg in [(0, 0), (T_SW0, 0), (T_SW1 - 0.06, 93), (T_SW1 + 0.08, 90)]:
    swv.rotation_mode = 'AXIS_ANGLE'
    swv.rotation_axis_angle = (math.radians(deg), zax.x, zax.y, zax.z)
    swv.keyframe_insert('rotation_axis_angle', frame=P.T(t))
K.set_interp(swv, 'BEZIER')

# ramp door: drops forward (top swings out about the bottom hinge) with a bounce
T_DOOR0, T_DOOR1 = 3.12, 3.45
for t, deg in [(0, 0), (T_DOOR0, 0), (T_DOOR1, 92), (T_DOOR1 + 0.07, 86), (T_DOOR1 + 0.15, 90)]:
    door.rotation_euler.y = math.radians(deg)
    door.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
K.set_interp(door, 'BEZIER')

# --- dish: a yaw joint between the unfolding pivot and the dish mesh
dpiv = af.parts['DishPivot']
dish = af.parts['TowerDish']
yaw = K.empty('DishYaw')
yaw.parent = dpiv
yaw.rotation_mode = 'XYZ'
mpi = dish.matrix_parent_inverse.copy()
dish.parent = yaw
dish.matrix_parent_inverse = mpi
dax = 1  # glTF anim axis y -> local y of the pivot (pivot keeps glTF axis convention)
T_SPIN = 2.9
f = int(P.T(T_SPIN))
while f <= NF + 1:
    t = (f - 1) / FPS
    u = t - T_SPIN
    ang = 150.0 * (u * u / 1.2 if u < 0.6 else (0.3 + (u - 0.6)))
    yaw.rotation_euler[dax] = math.radians(ang)
    yaw.keyframe_insert('rotation_euler', index=dax, frame=f)
    f += 2
yaw.keyframe_insert('rotation_euler', index=dax, frame=1)
K.set_interp(yaw, 'LINEAR')

# --- drive in + unfold
T_STOP = 1.3
T_UF0, T_UF1 = 1.45, 2.75
route = [(0.0, (-24.0, -3.2)), (0.45, (-15.5, -2.0)), (0.9, (-6.8, -0.6)), (1.15, (-2.0, -0.08)),
         (T_STOP, (0.0, 0.0))]
af.path([(t, (x, y, 0.0)) for t, (x, y) in route])
root = af.root
root.rotation_euler.z = 0.0
root.keyframe_insert('rotation_euler', index=2, frame=P.T(T_STOP))
af.unfold(T_UF0, T_UF1)
m = af.model_root
m.rotation_mode = 'XYZ'
for i in range(0, 16):
    t = i / 12
    m.location.z = 0.03 * math.sin(t * 31.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
for t, pitch, z in [(T_STOP - 0.1, 0.0, 0.0), (T_STOP + 0.04, 4.5, -0.03), (T_STOP + 0.2, -1.5, 0.0),
                    (T_STOP + 0.36, 0.0, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.location.z = z
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    m.keyframe_insert('location', index=2, frame=P.T(t))
P.dust(af, 0.0, T_STOP, every=0.06, size=1.1, color=SAND)


def dust_ring(center, t, r0, r1, n=18, size=1.1, life=1.4, opacity=0.3, rise=0.5):
    c = Vector(center)
    for k, r in enumerate((r0, r1)):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.9, 1.1)
            P.puff(p + Vector((0, 0, 0.25)), t + 0.1 * k + R.uniform(0, 0.04), size=size * (1 + 0.3 * k),
                   n=1, rise=rise * (1 + k), life=life, color=SAND, opacity=opacity)


# slew-stop: a forward plume of dust
for i in range(12):
    P.puff((2.0 + R.uniform(0, 1.8), R.uniform(-1.6, 1.6), 0.25), T_STOP + R.uniform(-0.05, 0.1),
           size=R.uniform(0.5, 0.9), n=1, rise=0.4, life=1.0, color=SAND, opacity=0.22)
dust_ring((0, 0, 0), T_UF0 + 0.45, 3.9, 5.2, n=16, size=0.65, life=1.0, opacity=0.11, rise=0.35)

# deck lights flare up when the field comes online
mat = bpy.data.materials.get('TerranAirBaseMat')
es = None
if mat and mat.node_tree:
    b = mat.node_tree.nodes.get('Principled BSDF')
    if b is not None:
        es = b.inputs['Emission Strength']
        base = es.default_value
        for t, v in [(0, base * 0.5), (T_UF1 - 0.1, base * 0.5), (T_UF1 + 0.1, base * 2.2), (T_UF1 + 0.5, base * 1.2),
                     (6, base * 1.2)]:
            es.default_value = v
            es.keyframe_insert('default_value', frame=P.T(t))
        print('deck emission base', base)

# ------------------------------------------------------------------------------ hangar interior
il = K.link(bpy.data.objects.new('HangarLight', bpy.data.lights.new('HangarLight', 'POINT')))
il.location = (LANE_X, MOUTH_Y - 1.9, 1.5)
il.data.color = (0.55, 0.78, 1.0)
il.data.shadow_soft_size = 0.6
for t, e in [(0, 0), (T_DOOR0, 0), (T_DOOR0 + 0.25, 140), (6, 120)]:
    il.data.energy = e
    il.data.keyframe_insert('energy', frame=P.T(t))
# neon lintel across the hangar mouth (lit once the door is down)
M_LINTEL = K.emit_mat('Lintel', NEON, 0.0)
lin = K.cube('Lintel', 1.0, M_LINTEL, loc=(LANE_X, MOUTH_Y + 0.02, 1.52))
lin.scale = (1.5, 0.04, 0.05)
K.show_between(lin, P.T(T_SW1 + 0.05), NF + 2)
K.key_strength(M_LINTEL, P.T(T_DOOR0), 0.0)
K.key_strength(M_LINTEL, P.T(T_DOOR0 + 0.2), 3.0)

# ------------------------------------------------------------------------------ falcon kit
FS = 2.2
KF = FS / 5.175
M_ENG = K.emit_mat('FalconEngine', NEON, 2.2)
M_ENG_HOT = K.emit_mat('FalconEngineHot', (0.25, 0.62, 1.0), 2.0)
M_ENG_GLOW = K.emit_mat('FalconEngineGlow', NEON, 0.9, alpha=0.12)
M_VAPOR = K.emit_mat('Vapor', (0.9, 0.93, 1.0), 0.9, alpha=0.11)
M_TRAIL = K.emit_mat('Trail', (0.85, 0.9, 1.0), 0.8, alpha=0.08)
ENG = Vector((-2.62 * KF, 0.0, 0.52 * KF))
TIPS = [Vector((0.85 * KF, 1.78 * KF, 0.42 * KF)), Vector((0.85 * KF, -1.78 * KF, 0.42 * KF))]


def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, upf, fwd0=Vector((0, 1, 0)), t_from=0.0):
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
        if v.length < 0.4:
            v = fwd0.copy()
            a = Vector()
        m3 = frame_from(v, upf(t, p, v, a))
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


def bank_up(k=2.2, clamp=None):
    def up(t, p, v, a):
        vn = v.normalized()
        lat = a - vn * a.dot(vn)
        lat.z = 0 if p.z < DECK + 0.05 else lat.z
        u = (Vector((0, 0, 9.8)) + lat * k).normalized()
        if clamp is not None:
            ang = math.degrees(math.acos(max(-1, min(1, u.z))))
            if ang > clamp:
                h = Vector((u.x, u.y, 0)).normalized()
                c = math.radians(clamp)
                u = h * math.sin(c) + Vector((0, 0, math.cos(c)))
        return u
    return up


def W(actor, t, local):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


# ------------------------------------------------------------------------------ falcon 1 path
Y0 = MOUTH_Y - FS / 2 - 0.08      # parked inside, nose just behind the mouth
T_TAXI = 3.38
T_SPOOL = 4.0
T_LAUNCH = 4.25
Y_LIFT = 1.7


def speed1(t, tl=None):
    if t < T_TAXI:
        return 0.0
    if t < T_SPOOL:
        u = (t - T_TAXI) / (T_SPOOL - T_TAXI)
        return 4.6 * math.sin(math.pi * min(1.0, u)) ** 0.8
    if t < T_LAUNCH:
        return 0.0
    v = min(22.0, 44.0 * (t - T_LAUNCH))
    if tl is not None:
        v += (14.0 - v) * ss((t - tl - 0.3) / 0.6)
    return v


TAB1 = []
dt_i = 1.0 / 480
_p = Vector((LANE_X, Y0, DECK))
_t = -0.2
_hd = math.radians(90.0)
_gam = 0.0
_tl = None
while _t < 6.3:
    v = speed1(_t, _tl)
    if _tl is None and _p.y > Y_LIFT:
        _tl = _t
    if _tl is not None:
        ut = _t - _tl
        _gam = math.radians(36.0) * ss(ut / 0.3) - math.radians(44.0) * ss((ut - 0.6) / 0.5)
        _hd -= math.radians(230.0) * ss((ut - 0.45) / 0.4) * dt_i
    d = Vector((math.cos(_hd) * math.cos(_gam), math.sin(_hd) * math.cos(_gam), math.sin(_gam)))
    TAB1.append((_t, _p.copy()))
    _p = _p + d * v * dt_i
    _t += dt_i
T_LIFT = _tl
print('liftoff at', T_LIFT)


def fpos1(t):
    k = (t + 0.2) / dt_i
    j = max(0, min(int(k), len(TAB1) - 2))
    u = k - j
    return TAB1[j][1] * (1 - u) + TAB1[j + 1][1] * u


for tt in (4.0, 4.4, 4.6, 4.8, 4.9, 5.0, 5.4, 6.0):
    print('falcon1', tt, tuple(round(c, 2) for c in fpos1(tt)))

fal1 = P.load('falcon', size=FS, label='falcon1')
fly(fal1, fpos1, bank_up(1.4, clamp=65))


# ------------------------------------------------------------------------------ falcon 2
T2 = 4.9


def fpos2(t):
    u = ss((t - 5.15) / 0.85)
    return Vector((LANE_X, Y0 + 1.1 * u, DECK))


fal2 = P.load('falcon', size=FS, label='falcon2')
fly(fal2, fpos2, bank_up(0.0))


# ------------------------------------------------------------------------------ engines
def engine(actor, power, seed=0):
    core = K.sphere('EngCore', 1.0, M_ENG_HOT, seg=(10, 6))
    core.parent = actor.root
    core.location = ENG + Vector((-0.06, 0, 0))
    glow = K.sphere('EngGlow', 1.0, M_ENG_GLOW, seg=(12, 8))
    glow.parent = actor.root
    plume = K.sphere('EngPlume', 1.0, M_ENG, seg=(10, 6))
    plume.parent = actor.root
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        pw = power(t)
        fl = R.uniform(0.85, 1.15) * pw
        s = max(0.001, pw)
        core.scale = (0.14 * min(1, s * 2), 0.11 * min(1, s * 2), 0.11 * min(1, s * 2))
        plume.location = ENG + Vector((-0.32 * fl, 0, 0))
        plume.scale = (max(0.001, 0.34 * fl), 0.055, 0.055)
        glow.location = ENG + Vector((-0.25 * fl, 0, 0))
        glow.scale = (max(0.001, 0.5 * fl), 0.19, 0.19)
        for o in (plume, glow, core):
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('scale', frame=f)
    return core


def power1(t):
    if t < T_DOOR0:
        return 0.0
    if t < T_SPOOL:
        return 0.35 * ss((t - T_DOOR0) / 0.3)
    if t < T_LAUNCH:
        return 0.35 + 0.95 * ss((t - T_SPOOL) / 0.2)
    return 1.3 + 0.5 * ss((t - T_LAUNCH) / 0.2)


engine(fal1, power1)
engine(fal2, lambda t: 0.3 * ss((t - 5.3) / 0.3))
fal2.appear(T2)

# engine light on the deck while it spools and launches
el = K.link(bpy.data.objects.new('EngLight', bpy.data.lights.new('EngLight', 'POINT')))
el.parent = fal1.root
el.location = ENG + Vector((-0.5, 0, 0.1))
el.data.color = (0.35, 0.65, 1.0)
el.data.shadow_soft_size = 0.4
for t, e in [(0, 0), (T_DOOR0 + 0.2, 0), (T_DOOR0 + 0.5, 25), (T_SPOOL, 25), (T_LAUNCH, 140),
             (T_LAUNCH + 0.5, 160), (5.2, 120)]:
    el.data.energy = e
    el.data.keyframe_insert('energy', frame=P.T(t))

fal1.appear(T_SW1)

# jet wash: light dust streaming back off the deck while it spools and launches
t = T_SPOOL + 0.04
while t < T_LIFT + 0.15:
    p = W(fal1, t, ENG + Vector((-0.6, 0, 0)))
    p.z = DECK + 0.15
    P.puff(p, t, size=0.55, n=1, rise=0.35, life=0.7, color=(0.82, 0.8, 0.76), opacity=0.22)
    t += 0.05
# deck edge: dust kicked off the ground below as it clears the deck
for i in range(8):
    P.puff((LANE_X + R.uniform(-1.2, 1.2), 4.4 + R.uniform(0, 2.5), 0.25), T_LIFT + 0.1 + R.uniform(0, 0.15),
           size=0.9, n=1, rise=0.5, life=1.0, color=(0.8, 0.72, 0.6), opacity=0.2)


# ------------------------------------------------------------------------------ catapult lane
M_LANE = []
N_SEG = 10
y_a, y_b = MOUTH_Y + 0.3, 3.55
for i in range(N_SEG):
    mt = K.emit_mat(f'Lane{i}', NEON, 0.0)
    M_LANE.append(mt)
    y = y_a + (y_b - y_a) * (i + 0.5) / N_SEG
    for sx in (-0.62, 0.62):
        o = K.cube(f'LaneSeg{i}_{sx}', 1.0, mt, loc=(LANE_X + sx, y, DECK + 0.012))
        o.scale = ((0.08, (y_b - y_a) / N_SEG * 0.55, 0.012))
        o.visible_shadow = False
    # idle dim, chase toward the end while spooling, flare as the Falcon passes
    K.key_strength(mt, 1, 0.0)
    K.key_strength(mt, P.T(T_UF1 - 0.1), 0.0)
    K.key_strength(mt, P.T(T_UF1 + 0.2), 0.6)
    for k in range(3):
        tc = T_SPOOL + 0.02 + k * 0.08 + i * 0.012
        K.key_strength(mt, P.T(tc) - 1, 0.6)
        K.key_strength(mt, P.T(tc), 2.6)
        K.key_strength(mt, P.T(tc) + 2, 0.6)
    tp = T_LAUNCH + math.sqrt(max(0.0, 2 * (y - Y0 - 2.0) / 42.0))
    K.key_strength(mt, P.T(tp) - 1, 0.6)
    K.key_strength(mt, P.T(tp), 3.0)
    K.key_strength(mt, P.T(tp + 0.4), 0.8)


# ------------------------------------------------------------------------------ vapour + trail
def vapor(actor, t0):
    hist = {f: [actor.mats[f] @ tp for tp in TIPS] for f in range(0, NF + 2)}
    for f in range(int(P.T(t0)), NF + 2):
        n = 5
        for k in range(2):
            pts = [hist[max(0, f - j)][k] for j in range(n)]
            o = K.polyline('Vapor', pts, 0.018, M_VAPOR)
            K.show_between(o, f, f + 1)


vapor(fal1, T_LIFT + 0.15)
# engine contrail in the end shot
for f in range(int(P.T(4.92)), NF + 2):
    pts = [fal1.mats[max(0, f - j)] @ ENG for j in range(0, 14)]
    o = K.polyline('Trail', pts, 0.05, M_TRAIL)
    K.show_between(o, f, f + 1)

# ------------------------------------------------------------------------------ camera
# A 0-1.3: low and close beside the carrier's path, panning as it rushes past and stops
# B 1.3-3.0: rise and orbit round the west side while it unfolds, ending north of the hangar
# C 3.0-4.9: drop to deck level on the north edge facing the hangar mouth; the Falcon taxis
#   at camera, launches and roars over (look target follows it up)
# D 4.917-6: cut to a low wide frame south-east, behind the tower: Falcon banking away into
#   the sky, the next one nosing out of the hangar.
cpos_c = Vector((LANE_X + 0.7, 7.3, 1.25))
keys = [
    (0.0, (-16.5, -7.2, 1.0), (-21.5, -3.0, 0.9), 32),
    (0.5, (-12.5, -7.6, 1.3), (-13.5, -1.8, 1.0), 28),
    (1.0, (-8.5, -8.6, 1.9), (-4.5, -0.4, 1.0), 26),
    (1.5, (-7.5, -8.4, 2.8), (0.0, 0.0, 1.0), 26),
    (2.2, (-10.0, -1.8, 3.6), (-0.6, -0.8, 1.1), 26),
    (2.9, (-6.5, 6.6, 2.5), (-1.4, -1.2, 0.9), 26),
    (3.4, (cpos_c.x - 0.6, 7.8, 1.7), (LANE_X, MOUTH_Y - 0.4, 0.7), 30),
    (4.0, tuple(cpos_c), (LANE_X, Y0 + 2.2, 0.5), 30),
]
# follow the falcon from launch until it passes over
t = 4.2
while t <= 4.875:
    keys.append((t, tuple(cpos_c), tuple(fpos1(t) + Vector((0, 0, 0.15))), 30))
    t += 0.075
keys.append((4.875, tuple(cpos_c), tuple(fpos1(4.875) + Vector((0, 0, 0.15))), 30))
T_CUT = 118 / 24
# D: high on the outside of the Falcon's turn, north of the field: it climbs toward camera,
# banks hard round close by and dives back toward its airfield
camD0 = Vector((10.0, 21.5, 8.6))
camD1 = Vector((9.0, 20.0, 9.0))
HOME = Vector((0.5, 1.5, 0.8))
for i in range(7):
    u = i / 6
    t = T_CUT + (6.0 - T_CUT) * u
    look = fpos1(t).lerp(HOME, 0.35 + 0.15 * u)
    keys.append((t, tuple(camD0.lerp(camD1, ss(u))), tuple(look), 24 + 4 * ss(u)))
P.camera(keys, shake=0.015, cuts=[T_CUT])
P.cam_shake(T_STOP, 0.1, dur=0.35)
P.cam_shake(T_LAUNCH + 0.05, 0.05, dur=0.3)
P.cam_shake(4.83, 0.12, dur=0.3)

P.render()
