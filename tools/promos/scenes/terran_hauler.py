"""Hauler (Terran tug): the ore run. A Prospector at the seam has just filled a cargo bin: the
last glowing pink chunks rattle up its conveyor into the bin sitting in its hopper. The Hauler,
parked alongside, has its telescoping crane boom out over the Prospector; the hook drops, the
spreader latches (bin strip flares neon blue), and the brimming bin is hoisted out, swung round
behind the cab and lowered onto the Hauler's bed with a thunk. The crane keeps it clamped while
the Hauler tears off along the edge of a Landing Pad, brakes alongside, hoists the bin again,
turns it square and sets it down on the pad's marked delivery spot, which lights up blue and
orange: cargo ready for lift. The hook rises away.

Crane boom, cable, hook rig and the cargo bin are built here and keyed per frame from the
Hauler's animated pose; the model's own CranePivot yaws with the boom.

Timeline (s): 0-0.45 last chunks into the bin, hook latches | 0.45-1.0 hoist | 0.85-1.5 swing
round | 1.5-1.85 lower onto the bed, thunk | CUT 2.0 | 1.95-4.1 drive past the pad |
CUT 4.0 | 4.2-4.55 hoist | 4.45-5.05 swing out over the pad, bin turns square |
5.0-5.42 set down, spot lights up | 5.55-6.0 hook releases and rises; hero frame on the ore."""
import math
import os
import sys

import bpy  # noqa: I001
import bmesh
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_hauler', seconds=6.0, seed=31)
R = P.rnd
FPS = P.fps
NF = int(P.seconds * FPS) + 1
SAND = (0.55, 0.43, 0.31)
ORE_PINK = (1.0, 0.28, 0.55)
ORE_DUST = (0.62, 0.36, 0.38)
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

# ------------------------------------------------------------------------------ layout
PROS_AT = (0.35, -3.4)          # prospector, heading 180 (drum faces -X into the seam)
DEP = (-5.3, -3.7)
PAD_AT = (11.2, -9.3)           # landing pad, heading 0; its +Y side deck faces the road
SPOT = Vector((PAD_AT[0] + 3.0, PAD_AT[1] + 5.6, 0.0))   # delivery spot on the side deck,
# on the clear east half (the pad's tower stands at the west end of that side)
PARK_X = SPOT.x - 0.63          # hauler parks with its crane post abreast of the spot
T_GO, T_PARK = 1.95, 4.1

P.env('desert', sun=(52, 0, -60), sun_energy=4.0, props=24,
      clear=[(4, -3, 14), (12, -9, 11), (14, 3, 9), DEP + (5,)])
P.flatten(4, -2, 12)
P.flatten(PAD_AT[0], PAD_AT[1], 10)
P.flatten(DEP[0], DEP[1], 5)
bpy.context.view_layer.update()

dep = P.load('deposit_ore', at=DEP, heading=20, size=6.0)
dep.root.location.z = P.ground_z(*DEP) - 0.2
for (x, y), s, h in [((-4.0, 3.5), 0.35, 40), ((-9.0, -8.0), 0.45, 150), ((-1.5, -9.5), 0.3, 260)]:
    c = P.copy(dep, at=(x, y), heading=h)
    c.root.scale = (s, s, s)
    c.root.location.z = P.ground_z(x, y) - 0.1

pad = P.load('terran_landing_pad', at=PAD_AT, heading=0)
pros = P.load('prospector', at=PROS_AT, heading=180, label='prospector')
hl = P.load('hauler', at=(0, 0), heading=0, label='hauler')

# ------------------------------------------------------------------------------ hauler drive
hl.path([(0.0, (0, 0), 0.0), (T_GO, (0, 0), 0.0), (T_GO + 0.55, (2.0, 0), 0.0), (T_PARK - 0.5, (PARK_X - 2.3, 0), 0.0),
         (T_PARK, (PARK_X, 0), 0.0), (6.2, (PARK_X, 0), 0.0)])
hm = hl.model_root
hm.rotation_mode = 'XYZ'
for t, pitch in [(0.0, 0), (T_GO, 0.0), (T_GO + 0.2, -2.2), (T_GO + 0.6, 0.0), (T_PARK - 0.25, 0.0),
                 (T_PARK + 0.05, 2.6), (T_PARK + 0.3, -0.8), (T_PARK + 0.5, 0.0), (6.2, 0.0)]:
    hm.rotation_euler.y = math.radians(pitch)
    hm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
# suspension: bin lands on the bed (dip), bin leaves the bed (rise)
for t, z in [(0.0, 0.0), (1.8, 0.0), (1.9, -0.07), (2.05, 0.01), (2.15, 0.0),
             (4.22, 0.0), (4.32, 0.035), (4.5, 0.0), (6.2, 0.0)]:
    hm.location.z = z
    hm.keyframe_insert('location', index=2, frame=P.T(t))
# engine idle shiver while driving
t = T_GO
while t < T_PARK:
    hm.location.z = 0.015 * math.sin(t * 40)
    hm.keyframe_insert('location', index=2, frame=P.T(t))
    t += 1 / 12
P.dust(hl, T_GO + 0.1, T_PARK + 0.1, every=0.08, size=0.85, color=SAND)

# prospector keeps grinding the seam
pros.spin('DrumPivot', -600, 0.0, 6.2, axis=1)
pm = pros.model_root
t = 0.0
while t < 6.2:
    pm.location.z = 0.012 * math.sin(t * 47.0)
    pm.keyframe_insert('location', index=2, frame=P.T(t))
    t += 1 / 12
PM = pros.root.matrix_world.copy()


def PW(x, y, z):
    return PM @ Vector((x, y, z))


DRUM_FACE = PW(2.45, 0.0, 0.55)
t = -0.2
while t < 6.0:
    P.puff(DRUM_FACE + Vector((-0.25, R.uniform(-0.7, 0.7), R.uniform(-0.2, 0.2))), t, size=0.4, n=1,
           rise=0.6, life=0.8, color=ORE_DUST, opacity=0.18)
    t += 0.2

# ------------------------------------------------------------------------------ materials
M_BIN = K.pbr_mat('BinHull', (0.11, 0.115, 0.125), rough=0.45, metal=0.7)
M_BIN_DARK = K.pbr_mat('BinDark', (0.05, 0.052, 0.056), rough=0.5, metal=0.6)
M_HAZ = K.pbr_mat('BinHazard', (0.95, 0.5, 0.05), rough=0.5, emit=ORANGE, emit_strength=0.25)
M_NEON = K.emit_mat('BinNeon', NEON, 0.6)
M_LAMP = K.emit_mat('HookLamp', ORANGE, 2.5)
M_CABLE = K.pbr_mat('Cable', (0.03, 0.03, 0.03), rough=0.6, metal=0.5)
M_BOOM = K.pbr_mat('Boom', (0.14, 0.145, 0.155), rough=0.4, metal=0.7)
M_ORE = K.pbr_mat('OreChunk', (0.62, 0.1, 0.3), rough=0.3, emit=ORE_PINK, emit_strength=0.45)
M_ORE_HOT = K.pbr_mat('OreChunkHot', (0.7, 0.12, 0.34), rough=0.25, emit=ORE_PINK, emit_strength=0.9)


def box(name, dims, loc, mat, parent=None):
    o = K.cube(name, 1.0, mat, loc=loc)
    o.scale = dims
    if parent:
        o.parent = parent
    return o


def unit_mesh(name, kind):
    """kind 'beam': box x 0..1, y/z +-0.5. 'rod': 8-sided cylinder z 0..1, radius 1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    if kind == 'beam':
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x += 0.5
    else:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=1.0, radius2=1.0, depth=1.0)
        for v in bm.verts:
            v.co.z += 0.5
    bm.to_mesh(me)
    bm.free()
    return me


# ------------------------------------------------------------------------------ cargo bin
BX, BY, BH = 1.5, 2.1, 0.7      # outer size (x along the hauler, y across), height
WALL = 0.08
bin_root = K.empty('CargoBin')
bin_root.rotation_mode = 'QUATERNION'
box('BinFloor', (BX, BY, 0.1), (0, 0, 0.05), M_BIN, bin_root)
for s in (1, -1):
    box(f'BinWallX{s}', (WALL, BY, BH), (s * (BX - WALL) / 2, 0, BH / 2), M_BIN, bin_root)
    box(f'BinWallY{s}', (BX, WALL, BH), (0, s * (BY - WALL) / 2, BH / 2), M_BIN, bin_root)
    # hazard rim, dark ribs, neon strip on the long faces, orange lift lugs
    box(f'BinRimY{s}', (BX + 0.04, WALL + 0.04, 0.09), (0, s * (BY - WALL) / 2, BH - 0.02), M_HAZ, bin_root)
    box(f'BinRimX{s}', (WALL + 0.04, BY + 0.04, 0.09), (s * (BX - WALL) / 2, 0, BH - 0.02), M_HAZ, bin_root)
    box(f'BinNeonY{s}', (BX * 0.8, 0.03, 0.07), (0, s * (BY / 2 + 0.01), BH * 0.42), M_NEON, bin_root)
    box(f'BinNeonX{s}', (0.03, BY * 0.8, 0.07), (s * (BX / 2 + 0.01), 0, BH * 0.42), M_NEON, bin_root)
    for k in (-1, 1):
        box(f'BinRib{s}{k}', (0.1, 0.05, BH * 0.9), (k * BX * 0.33, s * (BY / 2 + 0.02), BH * 0.45), M_BIN_DARK, bin_root)
CORNERS = [Vector((sx * (BX / 2 - 0.1), sy * (BY / 2 - 0.1), BH + 0.05)) for sx in (1, -1) for sy in (1, -1)]
for i, c in enumerate(CORNERS):
    box(f'BinLug{i}', (0.14, 0.14, 0.12), c, M_HAZ, bin_root)

# ore heap: fills the bin and crowns well over the rim so the load reads at phone size
layers = [(0.22, 1.0, 14), (0.42, 0.95, 13), (0.6, 0.85, 11), (0.78, 0.65, 8), (0.95, 0.42, 5), (1.08, 0.18, 2)]
for z, spread, n in layers:
    for i in range(n):
        a = i / n * 2 * math.pi + R.uniform(0, 0.5)
        r = spread * math.sqrt(R.uniform(0.2, 1.0))
        x = math.cos(a) * r * (BX / 2 - 0.2)
        y = math.sin(a) * r * (BY / 2 - 0.2)
        o = K.ico('Ore', 1.0, M_ORE if R.random() < 0.7 else M_ORE_HOT, sub=1 if R.random() < 0.3 else 0)
        s = R.uniform(0.15, 0.22)
        o.scale = (s, s * 0.85, s * 1.2)
        o.rotation_euler = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
        o.location = (x, y, z + R.uniform(-0.04, 0.04))
        o.parent = bin_root
ore_l = K.link(bpy.data.objects.new('OreGlow', bpy.data.lights.new('OreGlow', 'POINT')))
ore_l.parent = bin_root
ore_l.location = (0, 0, 1.6)
ore_l.data.color = ORE_PINK
ore_l.data.energy = 60
ore_l.data.shadow_soft_size = 0.7

# hook rig: spreader frame + four chains to the lugs + hook block with orange lamps
HOOK_H = 0.6    # hook block above the bin rim when latched
rig = K.empty('HookRig')
rig.rotation_mode = 'QUATERNION'
box('HookBlock', (0.34, 0.34, 0.3), (0, 0, BH + HOOK_H + 0.15), M_BOOM, rig)
box('HookCollar', (0.38, 0.38, 0.06), (0, 0, BH + HOOK_H + 0.02), M_HAZ, rig)
for s in (1, -1):
    box(f'HookLamp{s}', (0.06, 0.08, 0.06), (s * 0.19, 0, BH + HOOK_H + 0.2), M_LAMP, rig)
rod = unit_mesh('Rod', 'rod')
top = Vector((0, 0, BH + HOOK_H))
for i, c in enumerate(CORNERS):
    d = c + Vector((0, 0, 0.06)) - top
    o = K.link(bpy.data.objects.new(f'Chain{i}', rod))
    o.data.materials.append(M_CABLE) if not o.data.materials else None
    o.parent = rig
    o.location = top
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    o.scale = (0.025, 0.025, d.length)
    # once released, the slack chains swing in and hang under the hook
    hang = Vector((c.x * 0.12, c.y * 0.12, -0.75))
    for t_, dd in [(5.55, d), (5.8, hang)]:
        o.rotation_quaternion = dd.to_track_quat('Z', 'Y')
        o.scale = (0.025, 0.025, dd.length)
        o.keyframe_insert('rotation_quaternion', frame=P.T(t_))
        o.keyframe_insert('scale', frame=P.T(t_))

# boom (outer sleeve + telescoping inner beam) and main cable
beam = unit_mesh('Beam', 'beam')
beam.materials.append(M_BOOM)
boom_out = K.link(bpy.data.objects.new('BoomOuter', beam))
boom_in = K.link(bpy.data.objects.new('BoomInner', beam))
boom_stripe = K.link(bpy.data.objects.new('BoomStripe', beam.copy()))
boom_stripe.data.materials.clear()
boom_stripe.data.materials.append(M_HAZ)
boom_neon = K.link(bpy.data.objects.new('BoomNeon', beam.copy()))
boom_neon.data.materials.clear()
boom_neon.data.materials.append(K.emit_mat('BoomNeonM', NEON, 2.2))
tip_block = box('BoomTip', (0.3, 0.3, 0.3), (0, 0, 0), M_HAZ)
cable_me = unit_mesh('CableRod', 'rod')
cable_me.materials.append(M_CABLE)
cable = K.link(bpy.data.objects.new('Cable', cable_me))
for o in (boom_out, boom_in, boom_stripe, boom_neon, cable):
    o.rotation_mode = 'QUATERNION'

# ------------------------------------------------------------------------------ crane motion
crane_pv = hl.parts.get('CranePivot')
crane_me = hl.parts.get('Crane')
bpy.context.view_layer.update()
inv0 = hl.model_root.matrix_world.inverted()
O = inv0 @ crane_pv.matrix_world.translation       # crane post base in hauler-model space
POST_TOP = max((inv0 @ (crane_me.matrix_world @ Vector(c))).z for c in crane_me.bound_box)
O.z = POST_TOP - 0.05


def polar_of(p_local):
    d = p_local - O
    return math.degrees(math.atan2(d.y, d.x)), math.hypot(d.x, d.y)


PROS_BIN = PW(-1.25, 0.0, 0.81)                     # bin bottom-centre in the hopper (world)
BED = Vector((-0.8, 0.0, 0.9))                     # bin bottom-centre on the bed (hauler space)
PAD_BIN = Vector((SPOT.x - PARK_X, SPOT.y, 0.71))  # on the pad deck (hauler space when parked)
y_pr, r_pr = polar_of(Vector((PROS_BIN.x, PROS_BIN.y, 0)))
y_bed, r_bed = polar_of(BED)
y_pad, r_pad = polar_of(PAD_BIN)
# shortest swings
while y_bed - y_pr > 180:
    y_bed -= 360
while y_bed - y_pr < -180:
    y_bed += 360
while y_pad - y_bed > 180:
    y_pad -= 360
while y_pad - y_bed < -180:
    y_pad += 360

CH = {
    'yaw': [(0, y_pr), (0.85, y_pr), (1.5, y_bed), (4.45, y_bed), (5.05, y_pad), (6.2, y_pad)],
    'r': [(0, r_pr), (0.85, r_pr), (1.5, r_bed), (4.45, r_bed), (5.05, r_pad), (6.2, r_pad)],
    'z': [(0, PROS_BIN.z), (0.42, PROS_BIN.z), (0.95, 2.2), (1.45, 2.2), (1.85, BED.z), (4.2, BED.z),
          (4.55, 2.15), (5.0, 2.15), (5.42, PAD_BIN.z), (6.2, PAD_BIN.z)],
    'byaw': [(0, 0), (4.5, 0), (5.1, 90), (6.2, 90)],
    'hook': [(0, 0.8), (0.36, 0.0), (5.55, 0.0), (6.05, 0.9)],
}


def ch(name, t):
    ks = CH[name]
    if t <= ks[0][0]:
        return ks[0][1]
    for (ta, va), (tb, vb) in zip(ks, ks[1:]):
        if ta <= t <= tb:
            return va + (vb - va) * K.smoothstep((t - ta) / max(1e-4, tb - ta))
    return ks[-1][1]


def track(o, a, b, w, h):
    d = b - a
    o.location = a
    o.rotation_quaternion = d.to_track_quat('X', 'Z')
    o.scale = (max(1e-3, d.length), w, h)


def rod_between(o, a, b, r):
    d = b - a
    o.location = a
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    o.scale = (r, r, max(1e-3, d.length))


sc = bpy.context.scene
crane_pv.rotation_mode = 'XYZ'
rest_yaw = math.degrees(crane_pv.rotation_euler.z)
prev = []
for f in range(0, NF + 2):
    t = (f - 1) / FPS
    sc.frame_set(f)
    M = hl.model_root.matrix_world.copy()
    yaw, r, z = ch('yaw', t), ch('r', t), ch('z', t)
    a = math.radians(yaw)
    bottom_l = O.copy()
    bottom_l.x += r * math.cos(a)
    bottom_l.y += r * math.sin(a)
    bottom_l.z = z
    bottom = M @ bottom_l
    prev.append(bottom.copy())
    # pendulum sway while hanging: lag behind horizontal acceleration
    tilt = Quaternion()
    if len(prev) >= 3 and z > 1.0:
        acc = (prev[-1] - 2 * prev[-2] + prev[-3]) * FPS * FPS
        acc.z = 0
        ax = Vector((0, 0, 1)).cross(acc)
        ang = min(0.12, acc.length * 0.006)
        if ax.length > 1e-4:
            tilt = Quaternion(ax.normalized(), -ang)
    q_h = M.to_quaternion()
    q_bin = tilt @ q_h @ Quaternion((0, 0, 1), math.radians(ch('byaw', t)))
    bin_root.location = bottom
    bin_root.rotation_quaternion = q_bin
    bin_root.keyframe_insert('location', frame=f)
    bin_root.keyframe_insert('rotation_quaternion', frame=f)
    lift = ch('hook', t)
    rig.location = bottom + Vector((0, 0, lift))
    rig.rotation_quaternion = q_bin
    rig.keyframe_insert('location', frame=f)
    rig.keyframe_insert('rotation_quaternion', frame=f)
    hook_top = bottom + q_bin @ Vector((0, 0, BH + HOOK_H + 0.3)) + Vector((0, 0, lift))
    # boom: post top -> tip directly above the hook
    base = M @ O
    tip_l = O.copy()
    tip_l.x += r * math.cos(a)
    tip_l.y += r * math.sin(a)
    tip = M @ tip_l
    tip.z = max(base.z + 0.9, hook_top.z + 0.9)
    d = (tip - base)
    L = d.length
    dn = d.normalized()
    side = dn.cross(Vector((0, 0, 1))).normalized()
    track(boom_out, base - dn * 0.15, base + dn * min(L, 1.25), 0.26, 0.26)
    track(boom_in, base + dn * 0.9, tip, 0.17, 0.17)
    track(boom_stripe, base + dn * 0.1 + Vector((0, 0, 0.135)), base + dn * min(L, 1.15) + Vector((0, 0, 0.135)), 0.2, 0.02)
    track(boom_neon, base + dn * 0.2 + side * 0.135, base + dn * min(L, 1.1) + side * 0.135, 0.02, 0.05)
    tip_block.location = tip
    rod_between(cable, tip, hook_top, 0.03)
    for o in (boom_out, boom_in, boom_stripe, boom_neon, cable):
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_quaternion', frame=f)
        o.keyframe_insert('scale', frame=f)
    tip_block.keyframe_insert('location', frame=f)
    # the model's own crane arm turns with the boom (arm points -X at rest)
    yaw_world = math.degrees(math.atan2(d.y, d.x))
    hz = math.degrees(M.to_euler().z)
    crane_pv.rotation_euler.z = math.radians(rest_yaw + yaw_world - hz - 180)
    crane_pv.keyframe_insert('rotation_euler', index=2, frame=f)
for o in (bin_root, rig, boom_out, boom_in, boom_stripe, boom_neon, cable, tip_block, crane_pv):
    K.set_interp(o, 'LINEAR')
sc.frame_set(1)

# latch: bin strips flare blue, hook lamps blink
for t, v in [(0, 0.5), (0.34, 0.5), (0.38, 4.0), (0.6, 2.2), (5.45, 2.2), (5.53, 4.0), (5.75, 2.0)]:
    K.key_strength(M_NEON, P.T(t), v)
for t, v in [(0, 2.5), (0.34, 2.5), (0.37, 6), (0.5, 2.5), (5.55, 2.5), (5.58, 6), (5.75, 2.5)]:
    K.key_strength(M_LAMP, P.T(t), v)

# ------------------------------------------------------------------------------ last chunks in
RAMP_LOW = PW(1.55, 0.0, 0.95)
RAMP_TOP = PW(0.05, 0.0, 1.85)
for k in range(7):
    t0 = -0.35 + k * 0.1
    f = K.ico('OreFly', 1.0, M_ORE_HOT, sub=0)
    s = R.uniform(0.13, 0.17)
    f.scale = (s, s * 0.8, s * 1.4)
    st = DRUM_FACE + Vector((0, R.uniform(-0.5, 0.5), 0))
    land = PROS_BIN + Vector((R.uniform(-0.4, 0.4), R.uniform(-0.6, 0.6), 1.25))
    over = RAMP_TOP + Vector((0, 0, 0.25))
    pts = [(0.0, st), (0.1, RAMP_LOW + Vector((0, 0, 0.1))), (0.24, over),
           (0.33, over.lerp(land, 0.6) + Vector((0, 0, 0.2))), (0.42, land)]
    for dt, p in pts:
        f.location = p
        f.rotation_euler = (dt * 9 + k, dt * 7, k)
        f.keyframe_insert('location', frame=P.T(t0 + dt))
        f.keyframe_insert('rotation_euler', frame=P.T(t0 + dt))
    K.set_interp(f, 'LINEAR')
    K.show_between(f, max(0, P.T(t0)), P.T(t0 + 0.42))

# ------------------------------------------------------------------------------ pad delivery spot
spot_root = K.empty('SpotMarker')
spot_root.location = (SPOT.x, SPOT.y, 0.71)
M_SPOT = K.emit_mat('SpotNeon', NEON, 0.4)
M_SPOT_OR = K.emit_mat('SpotOrange', ORANGE, 0.4)
SW, SD = 2.75, 2.15   # marker outline (x, y): fits the bin turned square
for s in (1, -1):
    box(f'SpotX{s}', (SW, 0.07, 0.03), (0, s * SD / 2, 0.015), M_SPOT, spot_root)
    box(f'SpotY{s}', (0.07, SD, 0.03), (s * SW / 2, 0, 0.015), M_SPOT, spot_root)
    for k in (1, -1):
        box(f'SpotC{s}{k}', (0.28, 0.28, 0.04), (s * SW / 2, k * SD / 2, 0.02), M_SPOT_OR, spot_root)
# idle blink while the hauler approaches, solid and bright once the bin lands
for t, v in [(0, 0.4), (2.6, 0.4), (2.8, 2.2), (3.0, 0.5), (3.3, 2.2), (3.5, 0.5), (3.8, 2.2), (4.0, 0.6), (4.3, 2.0), (4.5, 0.6),
             (5.4, 0.6), (5.47, 4.0), (5.8, 2.6), (6.2, 2.6)]:
    K.key_strength(M_SPOT, P.T(t), v)
for t, v in [(0, 0.4), (5.4, 0.4), (5.47, 4.0), (5.75, 1.0), (5.9, 3.0), (6.2, 2.2)]:
    K.key_strength(M_SPOT_OR, P.T(t), v)
spot_l = K.link(bpy.data.objects.new('SpotGlow', bpy.data.lights.new('SpotGlow', 'POINT')))
spot_l.location = (SPOT.x, SPOT.y, 1.4)
spot_l.data.color = NEON
spot_l.data.shadow_soft_size = 1.0
for t, e in [(0, 0), (5.4, 0), (5.47, 260), (6.2, 120)]:
    spot_l.data.energy = e
    spot_l.data.keyframe_insert('energy', frame=P.T(t))


# ------------------------------------------------------------------------------ dust
def dust_ring(center, t, r, n=10, size=0.5, life=0.9, opacity=0.22, rise=0.35, color=SAND):
    c = Vector(center)
    for i in range(n):
        a = 2 * math.pi * i / n + R.uniform(-0.1, 0.1)
        p = c + Vector((math.cos(a) * r, math.sin(a) * r, 0.1))
        P.puff(p, t + R.uniform(0, 0.04), size=size, n=1, rise=rise, life=life, color=color, opacity=opacity)


sc.frame_set(int(P.T(1.86)))
dust_ring(hl.model_root.matrix_world @ (BED + Vector((0, 0, 0.05))), 1.86, 1.0, n=8, size=0.4, color=ORE_DUST, opacity=0.2)
dust_ring((SPOT.x, SPOT.y, 0.75), 5.42, 1.2, n=10, size=0.45, color=(0.5, 0.5, 0.52), opacity=0.2)
dust_ring((0, 0, 0), T_GO + 0.05, 2.4, n=10, size=0.8, color=SAND, opacity=0.25)
sc.frame_set(1)

# ------------------------------------------------------------------------------ camera
CUT1, CUT = 2.0, 4.0
P.camera([
    # A: from the seam side, over the prospector's shoulder: the full bin in its hopper, the
    # hauler's crane hook dropping onto it, then the swing across onto the hauler's bed
    (0.0, (-0.6, -11.2, 3.0), (-0.5, -2.2, 1.9), 34),
    (0.9, (-1.0, -10.8, 3.6), (-0.6, -1.8, 2.7), 34),
    (CUT1 - 1 / 24, (-2.0, -9.3, 4.0), (-0.8, -0.8, 1.8), 35),
    # B: cut ahead of the hauler on the open side; it tears off past the pad
    (CUT1, (4.6, 5.9, 2.4), (0.2, -0.3, 1.3), 28),
    (2.8, (6.4, 6.0, 2.5), hl, 28),
    (3.5, (10.6, 5.8, 2.5), hl, 28),
    (CUT - 1 / 24, (13.6, 5.4, 2.6), hl, 28),
    # C: cut onto the pad deck: the delivery, the bin big in the foreground at the end
    (CUT, (PARK_X + 2.4, -8.2, 3.4), (PARK_X - 0.4, -1.6, 1.7), 26),
    (5.0, (PARK_X + 2.2, -8.0, 3.0), (PARK_X + 0.1, -2.6, 1.6), 26),
    (6.0, (PARK_X + 2.4, -7.6, 3.1), (PARK_X + 0.1, -2.4, 1.4), 26),
], shake=0.01, cuts=(CUT1, CUT))
P.cam_shake(1.87, 0.04, 0.25)
P.cam_shake(5.44, 0.03, 0.25)

P.render()
