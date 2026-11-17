"""Research Lab (Terran research structure): dusk going to night. The lab sits dark on the plain
as a Hauler loaded with steel metal ingots rumbles past the camera; the lab's lights blink on to
greet it. The Hauler brakes beside the intake block, the intake port lights up and a neon tractor
arc lifts the ingots one by one out of the bed and drops them into the lab. Each ingot lights one
segment of a neon progress ring around the dome. When the ring closes, charge rings crawl up the
dome, the dome pulses blue and a research beam shoots up from the roof into the night sky with a
soft shockwave across the ground. The empty Hauler pulls away; end on a low hero frame looking
up at the lab and its beam. Metal is only for research: this is where it goes.

Timeline (s): 0-1.75 drive in, lights blink on 0.5-1.3 | 1.75 brake | 1.9 intake opens |
2.05-3.95 eight ingots transferred, ring fills | 3.35-4.1 charge rings climb the dome |
4.1 research complete: dome pulse, beam up, shockwave | 4.9 Hauler leaves | 4.3-6 hero orbit."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_lab', seconds=6.0, seed=5)
R = P.rnd
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
SAND = (0.5, 0.36, 0.26)
DUST = (0.55, 0.42, 0.32)

P.env('dusk', sun=(80, 0, -60), sun_energy=2.2, props=18,
      clear=[(0, 0, 14), (0, 18, 16), (-14, 10, 12), (12, 16, 10), (5.5, -8, 6), (5, -14, 4), (5, 8, 6), (-8, -10, 8)])
P.flatten(1.5, -2, 12)
P.flatten(5, 8, 7)
# darker, night-ish sky
bg = [n for n in bpy.context.scene.world.node_tree.nodes if n.type == 'BACKGROUND'][0]
bg.inputs['Strength'].default_value = 0.55
bpy.context.view_layer.update()


def no_shadow(o):
    for c in [o] + list(o.children_recursive):
        c.visible_shadow = False
    return o


def glow_mat(name, col, strength, alpha):
    """Emission mixed with transparency; returns (mat, emission node, mix node) for keying."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*col, 1)
    em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = alpha
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    return m, em, mix


def key_val(sock, keys):
    for t, v in keys:
        sock.default_value = v
        sock.keyframe_insert('default_value', frame=P.T(t))


# --------------------------------------------------------------------------- the lab
lab = P.load('terran_lab', at=(0, 0), heading=0, label='lab')
LAB_MAT = lab.meshes[0].material_slots[0].material
LB = LAB_MAT.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
# dark at first, lights blink on as the Hauler approaches, pulse at the breakthrough
T_DONE = 4.1
key_val(LB, [(0, 0.0), (0.5, 0.0), (0.55, 1.2), (0.62, 0.1), (0.8, 0.1), (0.85, 2.0), (0.92, 0.6),
             (1.05, 0.6), (1.1, 2.6), (T_DONE - 0.05, 2.6), (T_DONE + 0.05, 4.2), (T_DONE + 0.7, 2.8),
             (5.2, 3.2), (5.6, 2.8), (6.1, 3.2)])
DOME_C = Vector((0, 0, 1.0))   # dome is ~a hemisphere r 1.45 centred here
DOME_R = 1.45
TIP = Vector((0, 0, 2.95))
PORT = Vector((1.85, 0.0, 0.92))  # top of the east intake block

# interior glow under the dome glass
dome_l = bpy.data.objects.new('DomeLight', bpy.data.lights.new('DomeLight', 'POINT'))
K.link(dome_l)
dome_l.location = (0, 0, 3.4)
dome_l.data.color = NEON
dome_l.data.shadow_soft_size = 1.2
for t, e in [(0, 0), (0.84, 0), (0.86, 120), (0.93, 30), (1.08, 30), (1.12, 180), (3.3, 180),
             (T_DONE - 0.05, 260), (T_DONE + 0.05, 1600), (T_DONE + 0.6, 450), (6.1, 380)]:
    dome_l.data.energy = e
    dome_l.data.keyframe_insert('energy', frame=P.T(t))

# --------------------------------------------------------------------------- the hauler
T_STOP = 1.75
PARK = Vector((5.0, 1.25, 0.0))
hl = P.load('hauler', at=(5.6, -14.0), heading=90, label='hauler')
hl.path([(0.0, (5.7, -14.5)), (0.6, (5.3, -8.6)), (1.2, (5.05, -3.0)), (T_STOP, (PARK.x, PARK.y), 90),
         (4.9, (PARK.x, PARK.y), 90), (5.5, (5.0, 3.0), 90), (6.2, (5.0, 7.6), 90)])
hm = hl.model_root
hm.rotation_mode = 'XYZ'
for i in range(0, 22):
    t = i / 12
    hm.location.z = 0.025 * math.sin(t * 33.0)
    hm.keyframe_insert('location', index=2, frame=P.T(t))
for t, pitch, z in [(1.66, 0.0, 0.0), (1.8, 2.4, -0.02), (1.95, -0.9, -0.03), (2.15, 0.0, 0.0),
                    (4.9, 0.0, 0.0), (5.05, -1.6, 0.0), (5.3, 0.0, 0.0)]:
    hm.rotation_euler.y = math.radians(pitch)
    hm.location.z = z
    hm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    hm.keyframe_insert('location', index=2, frame=P.T(t))
P.dust(hl, 0.0, T_STOP, every=0.09, size=0.8, color=SAND)
for i in range(8):
    a = 2 * math.pi * i / 8
    P.puff(PARK + Vector((math.cos(a) * 2.4, math.sin(a) * 2.4, 0.2)), T_STOP + R.uniform(0, 0.06),
           size=0.7, n=1, rise=0.4, life=1.1, color=DUST, opacity=0.2)

# --------------------------------------------------------------------------- metal cargo
# parked hauler frame: local (lx, ly, lz) -> world; ingots stay parented to the hauler root.
PARK_M = Matrix.Translation(PARK) @ Matrix.Rotation(math.radians(90), 4, 'Z')
PARK_INV = PARK_M.inverted()
M_INGOT = K.pbr_mat('MetalIngot', (0.36, 0.4, 0.47), rough=0.38, metal=0.9, emit=NEON, emit_strength=0.22)
BED_Z = 0.9
IH = 0.26
slots = []
for lx in (-1.78, -1.18, -0.58):
    for ly in (-0.46, 0.46):
        slots.append(Vector((lx, ly, BED_Z + IH / 2)))
slots.append(Vector((-1.48, 0.0, BED_Z + IH * 1.5)))
slots.append(Vector((-0.88, 0.0, BED_Z + IH * 1.5)))
# take the top layer first, then the bottom from the back
order = [6, 7, 0, 1, 2, 3, 4, 5]
T_FEED0 = 2.05
FEED_STEP = 0.21
FLY = 0.55
absorbed = []
for k, si in enumerate(order):
    o = K.cube('Ingot', 1.0, M_INGOT)
    o.scale = (0.56, 0.42, IH)       # long axis along the hauler
    o.parent = hl.root
    home = slots[si]
    t0 = T_FEED0 + FEED_STEP * k
    o.location = home
    o.rotation_euler = (0, 0, 0)
    o.keyframe_insert('location', frame=0)
    o.keyframe_insert('location', frame=P.T(t0))
    o.keyframe_insert('rotation_euler', frame=P.T(t0))
    w0 = PARK_M @ home
    lift = w0 + Vector((0, 0, 0.55))
    over = PORT + Vector((0, 0, 0.95))
    sink = PORT + Vector((0, 0, -0.45))
    pts = [(0.0, w0), (0.12, lift)]
    n = 6
    for i in range(1, n + 1):
        u = i / n
        p = lift.lerp(over, u) + Vector((0, 0, 1.3 * u * (1 - u)))
        pts.append((0.12 + 0.3 * u, p))
    pts += [(0.5, PORT + Vector((0, 0, 0.12))), (FLY, sink)]
    for i, (dt, p) in enumerate(pts):
        o.location = PARK_INV @ p
        u = dt / FLY
        # long axis ends up along world y (the hauler frame's x is world y): spin a little in flight
        o.rotation_euler = (math.radians(14 * math.sin(u * 6 + k)), math.radians(10 * math.sin(u * 5)), 0)
        o.keyframe_insert('location', frame=P.T(t0 + dt))
        o.keyframe_insert('rotation_euler', frame=P.T(t0 + dt))
    K.show_between(o, 0, P.T(t0 + FLY) + 1)
    absorbed.append(t0 + 0.5)

# intake port: dark slot + neon rim on top of the east block
M_PORT_RIM, PR_EM, _ = glow_mat('PortRim', NEON, 0.0, 0.95)
rim = []
hw = 0.3
for a, b in [((-hw, -0.42), (hw, -0.42)), ((hw, -0.42), (hw, 0.42)), ((hw, 0.42), (-hw, 0.42)), ((-hw, 0.42), (-hw, -0.42))]:
    rim.append(Vector((PORT.x + a[0], PORT.y + a[1], PORT.z + 0.02)))
rim.append(rim[0])
po = no_shadow(K.polyline('PortRim', rim, 0.03, M_PORT_RIM))
key_val(PR_EM.inputs['Strength'], [(0, 0.0), (1.85, 0.0), (1.95, 2.4), (4.0, 2.4), (4.4, 1.0)])
slot = K.cube('PortSlot', 1.0, K.pbr_mat('PortSlotM', (0.01, 0.012, 0.016), rough=0.9))
slot.scale = (hw * 0.95, 0.4, 0.008)
slot.location = (PORT.x, PORT.y, PORT.z + 0.005)
port_l = bpy.data.objects.new('PortLight', bpy.data.lights.new('PortLight', 'POINT'))
K.link(port_l)
port_l.location = PORT + Vector((0, 0, 0.5))
port_l.data.color = NEON
port_l.data.shadow_soft_size = 0.3
for t, e in [(0, 0), (1.85, 0), (1.95, 60), (4.0, 60), (4.4, 15)]:
    port_l.data.energy = e
    port_l.data.keyframe_insert('energy', frame=P.T(t))
for t in absorbed:
    P.light(PORT + Vector((0, 0, 0.35)), t, NEON, energy=180, dur=0.18, radius=0.3)

# tractor arc: faint neon arc from the port up over to the bed
T_ARC0, T_ARC1 = 1.95, 4.0
bed_c = PARK_M @ Vector((-1.2, 0.0, BED_Z + 0.4))
arc = [PORT.lerp(bed_c, i / 16) + Vector((0, 0, 0.3 + 1.5 * (i / 16) * (1 - i / 16))) for i in range(17)]
arc[0] = PORT + Vector((0, 0, 0.05))
M_ARC, ARC_EM, ARC_MIX = glow_mat('TractorArc', NEON, 1.8, 0.07)
M_ARCC, ARCC_EM, _ = glow_mat('TractorCore', NEON, 2.2, 0.85)
for mat_, rad_ in ((M_ARC, 0.13), (M_ARCC, 0.014)):
    b = no_shadow(K.polyline('Tractor', arc, rad_, mat_))
    b.data.bevel_resolution = 3
    b.data.bevel_factor_mapping_end = 'SPLINE'
    b.data.bevel_factor_end = 0.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_ARC0))
    b.data.bevel_factor_end = 1.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_ARC0 + 0.15))
    K.show_between(b, P.T(T_ARC0), P.T(T_ARC1))
key_val(ARC_EM.inputs['Strength'], [(T_ARC0 + 0.2 * i, 2.0 if i % 2 == 0 else 1.1) for i in range(11)])
# pale glow on the bed while the arc holds the cargo
bed_l = bpy.data.objects.new('BedLight', bpy.data.lights.new('BedLight', 'POINT'))
K.link(bed_l)
bed_l.location = bed_c + Vector((0, 0, 0.6))
bed_l.data.color = NEON
for t, e in [(0, 0), (1.95, 0), (2.05, 90), (3.9, 90), (4.05, 0)]:
    bed_l.data.energy = e
    bed_l.data.keyframe_insert('energy', frame=P.T(t))

# --------------------------------------------------------------------------- progress ring
RING_R = 1.66
RING_Z = 1.18
M_RING_OFF = K.pbr_mat('RingOff', (0.03, 0.05, 0.08), rough=0.5, metal=0.5)
seg_mats = []
for k in range(8):
    # segment k lights when ingot k drops in, segments go round counter-clockwise from the east
    a0 = math.radians(45 * k + 4)
    a1 = math.radians(45 * (k + 1) - 4)
    pts = [Vector((RING_R * math.cos(a0 + (a1 - a0) * i / 8), RING_R * math.sin(a0 + (a1 - a0) * i / 8), RING_Z))
           for i in range(9)]
    m_, em_, _ = glow_mat(f'RingSeg{k}', NEON, 0.0, 1.0)
    s = no_shadow(K.polyline(f'RingSeg{k}', pts, 0.045, m_))
    s.data.bevel_resolution = 2
    ta = absorbed[k]
    key_val(em_.inputs['Strength'], [(0, 0.15), (ta - 0.02, 0.15), (ta + 0.03, 3.0), (ta + 0.25, 1.8),
                                      (T_DONE - 0.04, 1.8), (T_DONE + 0.04, 3.2), (T_DONE + 0.5, 1.8),
                                      (5.3, 2.2), (6.1, 1.8)])
    seg_mats.append(m_)
# thin dark carrier ring so the unlit segments read as hardware
carrier = [Vector((RING_R * math.cos(math.radians(i * 7.5)), RING_R * math.sin(math.radians(i * 7.5)), RING_Z - 0.06))
           for i in range(49)]
K.polyline('RingCarrier', carrier, 0.025, M_RING_OFF)

# --------------------------------------------------------------------------- charge rings up the dome
M_CH, CH_EM, CH_MIX = glow_mat('ChargeRing', NEON, 2.4, 0.9)
for j, tc in enumerate([3.35, 3.6, 3.85]):
    circ = [Vector((math.cos(math.radians(i * 10)), math.sin(math.radians(i * 10)), 0)) for i in range(37)]
    o = no_shadow(K.polyline('Charge', circ, 0.035, M_CH))
    o.data.bevel_resolution = 2
    dur = 0.45
    for i in range(7):
        u = i / 6
        ang = math.radians(8 + 70 * u)          # elevation on the dome
        r = (DOME_R + 0.05) * math.cos(ang)
        o.location = DOME_C + Vector((0, 0, (DOME_R + 0.05) * math.sin(ang)))
        o.scale = (r, r, r)
        o.keyframe_insert('location', frame=P.T(tc + dur * u))
        o.keyframe_insert('scale', frame=P.T(tc + dur * u))
    K.show_between(o, P.T(tc), P.T(tc + dur) + 1)

# dome pulse shell (upper hemisphere only)
me = bpy.data.meshes.new('DomeShell')
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.02], context='VERTS')
bm.to_mesh(me)
bm.free()
for p_ in me.polygons:
    p_.use_smooth = True
shell = no_shadow(K.link(bpy.data.objects.new('DomeShell', me)))
M_SHELL, SH_EM, SH_MIX = glow_mat('DomeShellM', NEON, 2.0, 0.0)
me.materials.append(M_SHELL)
shell.location = DOME_C
for t, s in [(T_DONE - 0.02, 1.47), (T_DONE + 0.25, 1.62), (T_DONE + 0.6, 1.5)]:
    shell.scale = (s, s, s)
    shell.keyframe_insert('scale', frame=P.T(t))
key_val(SH_MIX.inputs[0], [(0, 0.0), (3.3, 0.0), (3.9, 0.12), (T_DONE - 0.02, 0.18), (T_DONE + 0.04, 0.55),
                           (T_DONE + 0.5, 0.14), (5.0, 0.09), (5.4, 0.14), (5.8, 0.09), (6.1, 0.13)])
key_val(SH_EM.inputs['Strength'], [(0, 1.6), (T_DONE + 0.04, 2.6), (T_DONE + 0.5, 1.6)])

# --------------------------------------------------------------------------- research beam
T_BEAM = T_DONE + 0.04
TOP = TIP + Vector((0, 0, 90))
M_BEAMG, BG_EM, BG_MIX = glow_mat('BeamGlow', NEON, 1.8, 0.14)
M_BEAMC, BC_EM, _ = glow_mat('BeamCore', (0.25, 0.65, 1.0), 2.0, 1.0)
for mat_, rad_, w in ((M_BEAMG, 0.36, [(T_BEAM, 0.3), (T_BEAM + 0.15, 1.6), (T_BEAM + 0.5, 1.0), (6.1, 0.9)]),
                      (M_BEAMC, 0.09, [(T_BEAM, 0.5), (T_BEAM + 0.15, 1.5), (T_BEAM + 0.5, 1.0), (6.1, 1.0)])):
    b = no_shadow(K.polyline('ResearchBeam', [TIP, TIP + Vector((0, 0, 10)), TOP], rad_, mat_))
    b.data.bevel_resolution = 3
    b.data.bevel_factor_mapping_end = 'SPLINE'
    b.data.bevel_factor_end = 0.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_BEAM))
    b.data.bevel_factor_end = 1.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_BEAM + 0.3))
    # radius swell via object scale in x/y
    for t, s in w:
        b.scale = (s, s, 1.0)
        b.keyframe_insert('scale', frame=P.T(t))
    K.show_between(b, P.T(T_BEAM), P.T(6.2))
key_val(BG_MIX.inputs[0], [(T_BEAM + 0.5 + 0.25 * i, 0.14 if i % 2 == 0 else 0.09) for i in range(8)])
beam_l = bpy.data.objects.new('BeamLight', bpy.data.lights.new('BeamLight', 'POINT'))
K.link(beam_l)
beam_l.location = TIP + Vector((0, 0, 1.5))
beam_l.data.color = NEON
beam_l.data.shadow_soft_size = 0.6
for t, e in [(0, 0), (T_BEAM - 0.01, 0), (T_BEAM + 0.05, 2500), (T_BEAM + 0.6, 700), (6.1, 600)]:
    beam_l.data.energy = e
    beam_l.data.keyframe_insert('energy', frame=P.T(t))

# shockwave ring across the ground
M_SW, SW_EM, SW_MIX = glow_mat('Shockwave', NEON, 1.8, 0.0)
circ = [Vector((math.cos(math.radians(i * 6)), math.sin(math.radians(i * 6)), 0)) for i in range(61)]
sw = no_shadow(K.polyline('Shockwave', circ, 0.02, M_SW))
sw.data.bevel_resolution = 2
sw.location = (0, 0, 0.12)
for t, s in [(T_BEAM, 2.6), (T_BEAM + 0.9, 16.0)]:
    sw.scale = (s, s, 1.0)
    sw.keyframe_insert('scale', frame=P.T(t))
for fc in K._fcurves(sw.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = 'SINE'
        kp.easing = 'EASE_OUT'
key_val(SW_MIX.inputs[0], [(T_BEAM, 0.0), (T_BEAM + 0.06, 0.8), (T_BEAM + 0.9, 0.0)])
# light dust lifted by the wave
for i in range(18):
    a = 2 * math.pi * i / 18 + R.uniform(-0.1, 0.1)
    r = R.uniform(3.2, 4.2)
    p = Vector((math.cos(a) * r, math.sin(a) * r, 0.15))
    if (p - PARK).length < 2.0:
        continue
    P.puff(p, T_BEAM + 0.15 + r * 0.02, size=0.6, n=1, rise=0.35, life=1.0, color=DUST, opacity=0.16)
P.cam_shake(T_BEAM, 0.03, 0.35)

# --------------------------------------------------------------------------- camera
P.camera([
    # shot 1: head-on as the loaded Hauler rolls in, the lab waking up on the right
    (0.0, (10.6, 5.6, 1.0), (2.4, -2.9, 1.3), 26),
    (1.0, (10.2, 5.2, 1.15), (2.3, -2.1, 1.3), 26),
    (1.708, (9.8, 4.8, 1.3), (2.2, -1.4, 1.3), 26),
    # cut: south view of the transfer, the arc spanning the frame
    (1.75, (7.4, -7.4, 3.2), (3.3, 0.0, 1.3), 30),
    (3.0, (6.0, -8.0, 3.1), (2.9, 0.0, 1.5), 30),
    (3.75, (4.2, -7.8, 2.3), (1.8, 0.0, 1.8), 28),
    (4.3, (2.9, -7.4, 0.8), (0.6, 0.0, 2.8), 24),
    (5.1, (0.7, -7.9, 0.65), (0.3, 0.0, 2.6), 23),
    (6.0, (-2.5, -7.2, 0.6), (0.15, 0.0, 2.45), 24),
], shake=0.012, cuts=(1.75,))
P.cam_shake(T_STOP, 0.04, 0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.5, 'power_up_terran', gain=0.35, rate=1.2)    # lab lights blink on
P.sfx(1.9, 'servo', gain=0.4, pos=PORT)               # intake opens
P.sfx(1.92, 'hydraulic', gain=0.35, pos=PORT)
P.sfx(T_ARC0, 'tractor_loop', gain=0.5, dur=T_ARC1 - T_ARC0, pos=PORT)  # neon tractor arc
for _k in range(8):                                   # ingots plucked off the bed, dropped into the lab
    _t = T_FEED0 + FEED_STEP * _k
    P.sfx(_t, 'impact_metal', gain=0.18, pos=PARK, rate=1.15)
    P.sfx(_t + FLY, 'mech_clunk', gain=0.3, pos=PORT, rate=1.1 + 0.02 * _k)
P.sfx(3.35, 'charge_gold', gain=0.25, rate=0.7)       # charge rings crawl up the dome
P.sfx(3.4, 'power_up_terran', gain=0.5)
P.sfx(T_DONE, 'shockwave', gain=0.9)                  # research complete: pulse + shockwave
P.sfx(T_BEAM, 'beam_start', gain=0.7)
P.sfx(T_BEAM + 0.1, 'beam_blue_loop', gain=0.45, dur=6.0 - T_BEAM - 0.1)

P.render()
