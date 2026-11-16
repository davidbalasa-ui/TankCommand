"""Metal Station (Terran research-economy structure): the packed station grinds across a dusk
plain toward a field of blue metal crystals, brakes beside the big outcrop and unfolds: base
plates out, smelter, hopper and stack rise. The fan spins up, a neon intake beam locks onto the
outcrop and pulls crystal shards across into the hopper, the smelter window flares orange, the
stack starts venting, and with a spray of sparks the first glowing metal ingots slide out and
stack on the pad, cooling to steel. Metal buys research, not armies: this is the quiet heart of
the tech tree.

Timeline (s): 0-1.75 drive in (low tracking camera past the crystals) | 1.75 brake + dig in |
1.85-3.0 unfold | 3.0 fan spins up | 3.1 intake beam, shards fly every ~0.28 s |
3.4 smelter ignites, stack vents | 4.1 / 4.85 / 5.5 ingots slide out | 5.2-6 low hero frame."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_metal_station', seconds=6.0, seed=11)
R = P.rnd
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
SAND = (0.5, 0.36, 0.26)

DEP = (0.0, -6.6)          # the big metal outcrop, south of the station (hopper faces -y)
P.env('dusk', sun=(58, 0, -100), sun_energy=3.8, props=34,
      clear=[(0, 0, 9), (-9, 0.5, 6), (-16, 1.5, 5), (-6, -6, 8), (-9, -3, 5), DEP + (5,)])
P.flatten(0, -2, 13)
P.flatten(-14, 1, 8)
bpy.context.view_layer.update()

# deposits AFTER flatten so they sit on the final ground
dep = P.load('deposit_metal', at=DEP, heading=20, size=5.0)
dep.root.location.z = P.ground_z(*DEP) - 0.15
field = [((5.8, -9.8), 0.42, 70), ((7.0, -3.6), 0.3, 140), ((-3.4, -11.8), 0.34, 200),
         ((3.6, 6.2), 0.36, 10), ((-7.5, 5.5), 0.28, 300), ((-8.6, -6.6), 0.3, 120)]
for (x, y), s, h in field:
    c = P.copy(dep, at=(x, y), heading=h)
    c.root.scale = (s, s, s)
    c.root.location.z = P.ground_z(x, y) - 0.1
gem_mat = None
for o in dep.meshes:
    for sl in o.material_slots:
        if sl.material and 'Gem' in sl.material.name:
            gem_mat = sl.material
gem_mat = gem_mat or K.pbr_mat('GemFallback', (0.35, 0.55, 1.0), rough=0.15)

# --------------------------------------------------------------------------- the station
T_STOP = 1.75
T_UF0, T_UF1 = 1.85, 3.0
st = P.load('terran_metal_station', at=(0, 0), heading=0, label='station')
route = [(0.0, (-17.0, 1.6)), (0.6, (-11.0, 1.3)), (1.2, (-5.0, 0.5)), (1.55, (-1.6, 0.08)),
         (T_STOP, (0.0, 0.0))]
st.path([(t, (x, y, 0.0)) for t, (x, y) in route])
# hold the final heading exactly 0 once stopped
root = st.root
root.rotation_euler = (0, 0, 0)
root.keyframe_insert('rotation_euler', frame=P.T(T_STOP))
st.unfold(T_UF0, T_UF1, stagger=0.12)

m = st.model_root
m.rotation_mode = 'XYZ'
for i in range(0, 21):
    t = i / 12
    m.location.z = 0.03 * math.sin(t * 31.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
for t, pitch, z in [(1.7, 0.0, 0.0), (1.82, 2.6, -0.03), (1.98, -0.8, -0.06), (2.2, 0.0, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.location.z = z
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    m.keyframe_insert('location', index=2, frame=P.T(t))
P.dust(st, 0.0, T_STOP, every=0.08, size=0.9, color=SAND)


def dust_ring(center, t, r0, r1, n=16, size=0.8, life=1.2, opacity=0.26, rise=0.45):
    c = Vector(center)
    for k, r in enumerate((r0, r1)):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.9, 1.1)
            P.puff(p + Vector((0, 0, 0.2)), t + 0.08 * k + R.uniform(0, 0.04), size=size * (1 + 0.3 * k),
                   n=1, rise=rise * (1 + k), life=life, color=SAND, opacity=opacity)


dust_ring((0, 0, 0), 1.8, 2.0, 3.2, n=14)
dust_ring((0, 0, 0), T_UF1 - 0.2, 3.0, 3.8, n=14, size=0.7, opacity=0.18)

# fan: yaw empty between the unfolding FanPivot and the Fan blades
fpiv = st.parts['FanPivot']
fan = st.parts['Fan']
fyaw = K.empty('FanYaw')
fyaw.parent = fpiv
fyaw.rotation_mode = 'XYZ'
mpi = fan.matrix_parent_inverse.copy()
fan.parent = fyaw
fan.matrix_parent_inverse = mpi
T_FAN = 3.0
for t, ang in [(0, 0), (T_FAN, 0), (T_FAN + 0.6, 360 * 0.9), (6.2, 360 * 0.9 + 1300 * (6.2 - T_FAN - 0.6))]:
    fyaw.rotation_euler.z = math.radians(ang)
    fyaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
K.set_interp(fyaw, 'LINEAR')

# --------------------------------------------------------------------------- key points (deployed)
bpy.context.scene.frame_set(int(P.T(T_UF1 + 0.1)))
bpy.context.view_layer.update()


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


hlo, hhi = bbox(st.parts['Hopper'])
slo, shi = bbox(st.parts['Stack'])
HOPPER_MOUTH = Vector(((hlo.x + hhi.x) / 2, (hlo.y + hhi.y) / 2 - 0.2, hhi.z + 0.05))
STACK_TOP = Vector(((slo.x + shi.x) / 2, (slo.y + shi.y) / 2, shi.z + 0.05))
print('HOPPER', HOPPER_MOUTH, 'STACK', STACK_TOP)

# --------------------------------------------------------------------------- intake beam + shards
T_BEAM0, T_BEAM1 = 3.1, 6.2
dep_face = Vector((DEP[0] + 0.2, DEP[1] + 1.6, 1.4))
M_BEAM = K.emit_mat('IntakeBeam', NEON, 2.2, alpha=0.22)
M_BEAMC = K.emit_mat('IntakeCore', NEON, 3.0)


def arc_pts(p0, p1, lift, n=14):
    return [p0.lerp(p1, i / n) + Vector((0, 0, 4 * lift * (i / n) * (1 - i / n))) for i in range(n + 1)]


ARC_LIFT = 1.1
beam_pts = arc_pts(dep_face, HOPPER_MOUTH, ARC_LIFT)
for mat_, rad_ in ((M_BEAM, 0.1), (M_BEAMC, 0.025)):
    b = K.polyline('Intake', beam_pts, rad_, mat_)
    b.data.bevel_resolution = 3
    # beam shoots out from the hopper to the rock
    b.data.bevel_factor_mapping_end = 'SPLINE'
    b.data.bevel_factor_start = 0.0
    b.data.bevel_factor_end = 0.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_BEAM0))
    b.data.bevel_factor_end = 1.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_BEAM0 + 0.18))
    K.show_between(b, P.T(T_BEAM0), P.T(T_BEAM1))
for t, v in [(T_BEAM0, 2.2), (3.6, 1.6), (4.2, 2.2), (4.8, 1.6), (5.4, 2.2), (6.0, 1.6)]:
    K.key_strength(M_BEAM, P.T(t), v)
# glow on the crystal where the beam grips
grip = P.light(dep_face, T_BEAM0 + 0.15, NEON, energy=500, dur=3.0, radius=0.8)
P.impact(dep_face, T_BEAM0 + 0.18, size=0.5, color=NEON)

M_SHARD = K.pbr_mat('ShardM', (0.35, 0.55, 1.0), rough=0.2, emit=NEON, emit_strength=1.4)
shard_ts = [3.3 + 0.27 * k for k in range(10)]
for k, t0 in enumerate(shard_ts):
    o = K.ico('Shard', 1.0, M_SHARD, sub=0)
    s = R.uniform(0.11, 0.17)
    o.scale = (s, s, s * 2.4)
    off = Vector((R.uniform(-0.5, 0.5), R.uniform(-0.2, 0.2), R.uniform(-0.4, 0.3)))
    p0 = dep_face + off
    dur = 0.55
    pts = arc_pts(p0, HOPPER_MOUTH + Vector((R.uniform(-0.3, 0.3), 0, 0)), ARC_LIFT + R.uniform(-0.1, 0.2), n=8)
    for i, p in enumerate(pts):
        u = i / 8
        o.location = p
        o.rotation_euler = (u * 8 + k, u * 6, u * 5 + k)
        fr = P.T(t0 + dur * u * u * (0.6 + 0.4 * u) / 1.0)
        o.keyframe_insert('location', frame=fr)
        o.keyframe_insert('rotation_euler', frame=fr)
    K.set_interp(o, 'LINEAR')
    K.show_between(o, P.T(t0), P.T(t0 + dur) + 1)
    if k % 3 == 0:
        P.light(p0, t0, NEON, energy=250, dur=0.15, radius=0.4)

# --------------------------------------------------------------------------- smelter ignites
T_IGN = 3.45
furnace = bpy.data.objects.new('FurnaceLight', bpy.data.lights.new('FurnaceLight', 'POINT'))
K.link(furnace)
furnace.location = (-2.5, -0.6, 0.9)
furnace.data.color = ORANGE
furnace.data.shadow_soft_size = 0.5
for t, e in [(0, 0), (T_IGN, 0), (T_IGN + 0.15, 450), (T_IGN + 0.4, 280)] + \
        [(T_IGN + 0.4 + 0.2 * i, 280 + 80 * ((-1) ** i)) for i in range(1, 12)]:
    furnace.data.energy = e
    furnace.data.keyframe_insert('energy', frame=P.T(t))
stack_l = bpy.data.objects.new('StackLight', bpy.data.lights.new('StackLight', 'POINT'))
K.link(stack_l)
stack_l.location = STACK_TOP + Vector((0, 0, 0.3))
stack_l.data.color = ORANGE
for t, e in [(0, 0), (T_IGN, 0), (T_IGN + 0.2, 70), (6.0, 60)]:
    stack_l.data.energy = e
    stack_l.data.keyframe_insert('energy', frame=P.T(t))
t = T_IGN + 0.1
while t < 6.0:
    P.puff(STACK_TOP + Vector((0, 0, 0.1)), t, size=0.45, n=1, rise=1.6, life=1.6,
           color=(0.5, 0.48, 0.47), opacity=0.24)
    t += 0.22

# --------------------------------------------------------------------------- ingots
OUT = Vector((-2.15, -0.55, 0.62))        # outlet on the smelter's west face
STACK_SPOT = Vector((-1.85, -1.75, 0.32))  # front-west corner of the pad
M_SPARK = K.emit_mat('IngotSpark', (1.0, 0.55, 0.15), 3.0)


def ingot(t0, slot):
    mat = K.pbr_mat('Ingot', (0.42, 0.45, 0.5), rough=0.3, metal=0.9, emit=(1.0, 0.3, 0.03), emit_strength=0)
    b = mat.node_tree.nodes['Principled BSDF']
    for t_, v in [(t0 - 0.05, 0.0), (t0, 1.8), (t0 + 0.6, 1.2), (t0 + 1.6, 0.15)]:
        b.inputs['Emission Strength'].default_value = v
        b.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t_))
    o = K.cube('Ingot', 1.0, mat)
    o.scale = (0.24, 0.5, 0.15)
    end = STACK_SPOT + slot
    mid = OUT + Vector((-0.35, -0.2, 0.0))
    for t_, p in [(t0, OUT), (t0 + 0.18, mid), (t0 + 0.42, end + Vector((0, 0, 0.25))), (t0 + 0.52, end),
                  (t0 + 0.6, end + Vector((0, 0, 0.04))), (t0 + 0.68, end)]:
        o.location = p
        o.keyframe_insert('location', frame=P.T(t_))
    K.show_between(o, P.T(t0), P.T(6.3))
    # sparks spraying from the outlet
    for i in range(10):
        sp = K.sphere('Spark', 1.0, M_SPARK, seg=(6, 4))
        v = Vector((R.uniform(-1.4, -0.4), R.uniform(-0.9, 0.6), R.uniform(0.3, 1.4)))
        sp.scale = (0.08, 0.018, 0.018)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        ts = t0 + R.uniform(0.0, 0.15)
        life = R.uniform(0.25, 0.45)
        for k in range(4):
            tt = life * k / 3
            sp.location = OUT + v * tt * 2.2 + Vector((0, 0, -4.9 * tt * tt))
            sp.keyframe_insert('location', frame=P.T(ts + tt))
        K.show_between(sp, P.T(ts), P.T(ts + life))
    P.light(OUT + Vector((-0.4, 0, 0.3)), t0, ORANGE, energy=300, dur=0.3, radius=0.4)
    P.puff(OUT + Vector((-0.3, 0, 0.3)), t0 + 0.1, size=0.3, n=1, rise=0.8, life=0.9,
           color=(0.4, 0.38, 0.36), opacity=0.18)


ingot(4.1, Vector((0.0, -0.27, 0.0)))
ingot(4.85, Vector((0.0, 0.27, 0.0)))
ingot(5.5, Vector((0.0, 0.0, 0.15)))

# --------------------------------------------------------------------------- camera
P.camera([
    (0.0, (-6.5, -4.8, 0.7), (-16.0, 1.4, 1.0), 30),
    (0.9, (-5.8, -5.4, 0.8), st.pos_at(0.9) + Vector((0, 0, 1.0)), 30),
    (1.75, (-3.5, -7.8, 1.4), (0.0, 0.0, 1.0), 30),
    (2.9, (-6.0, -6.0, 2.4), (0.0, -0.6, 1.3), 30),
    (3.9, (-7.5, -8.0, 2.6), (-0.3, -3.2, 1.3), 26),
    (4.7, (-5.2, -4.2, 1.3), (-1.8, -1.4, 0.7), 34),
    (6.0, (-5.8, -7.4, 0.8), (-0.4, -1.8, 1.6), 24),
], shake=0.015)
P.cam_shake(1.8, 0.06, 0.3)

P.render()
