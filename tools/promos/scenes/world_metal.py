"""Metal deposit (neutral resource): metal is only for research, and both sides tap it.

Cool highland morning. Low and close, the camera slides along a big steel-blue metal deposit:
polished facets catch the sun, star glints pop along the edges, and far behind it a packed
Arcadian Siphon spirals down onto a vein on legs of gold lightning. Cut: a packed Terran
Metal Station sits on the near vein, the metal outcrop it will feed on right in front of the
lens. It unfolds like machinery: base plates slam out, tanks, smelter, hopper and stack rise
one after another with hydraulic thumps and dust, the fan spins up, neon trims kindle and a
blue intake beam locks onto the outcrop. Cut across the field: the Siphon comes apart in the
air. Its basin, horns and spire lift off the base ring and hang there, held on threads of gold
lightning, turning slowly, then drift down into place with air still under them. The horns
tap its own outcrop and threads of liquid gold climb into the basin. Final shot rises behind
the Terran station: station near, the hero deposit glinting in the middle, the Siphon far
beyond, both drinking from their veins.

Timeline (s): 0-1.5 deposit slide + glints, Siphon lands far behind (1.45) |
1.5 cut: Terran unfold 1.6-2.95, fan 2.9, beam 3.05 | 3.25 cut: Siphon float-apart 3.3-4.5,
horns tap 4.45, gold threads 4.55 | 4.75 cut: rising hero frame, both extracting."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Quaternion, Vector  # noqa: E402

import promo_fx_weapons as W  # noqa: E402
import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('world_metal', seconds=6.0, seed=57)
R = P.rnd
FPS = P.fps

NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
STEEL = (0.46, 0.53, 0.64)
GLINT = (0.7, 0.85, 1.0)

DEP = Vector((0.0, 0.0, 0.0))          # hero deposit
TS = Vector((-5.0, -5.0, 0.0))         # Terran Metal Station (hopper faces -y)
T_VEIN = Vector((-4.1, -8.7, 0.0))     # outcrop the station feeds on (south of it, near the lens)
SP = Vector((10.0, 7.0, 0.0))          # Arcadian Siphon (basin faces -y)
S_VEIN = Vector((9.3, 3.5, 0.0))       # outcrop the siphon drinks

CUT1, CUT2, CUT3 = 36 / 24, 78 / 24, 114 / 24   # 1.5, 3.25, 4.75

P.env('highland', sun=(60, 0, -60), sun_energy=4.2, props=26,
      clear=[(0, 0, 6), (TS.x, TS.y, 5), (SP.x, SP.y, 5), (T_VEIN.x, T_VEIN.y, 2.5), (S_VEIN.x, S_VEIN.y, 2.5),
             (-2.5, -4.5, 3), (5.0, 3.5, 3)])
P.flatten(0, 0, 7)
P.flatten(TS.x, TS.y, 5.5)
P.flatten(SP.x, SP.y, 5.5)
P.flatten(T_VEIN.x, T_VEIN.y, 3)
P.flatten(S_VEIN.x, S_VEIN.y, 3)
bpy.context.view_layer.update()


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('Mt_' + key, col, strength, alpha=alpha)
    return _mats[key]


def plight(name, pos, keys, color, radius=1.0, parent=None):
    L = K.link(bpy.data.objects.new(name, bpy.data.lights.new(name, 'POINT')))
    L.location = pos
    L.data.color = color
    L.data.shadow_soft_size = radius
    if parent is not None:
        L.parent = parent
    for t, e in keys:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=P.T(t))
    return L


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def actor_bbox(a):
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in a.meshes:
        l_, h_ = bbox(o)
        lo = Vector(map(min, lo, l_))
        hi = Vector(map(max, hi, h_))
    return lo, hi


# --------------------------------------------------------------------------- the metal
dep = P.load('deposit_metal', at=DEP[:2], heading=35, size=5.2, label='deposit')
dep.root.location.z = P.ground_z(*DEP[:2]) - 0.15

# steel, not crystal: the gem faces become polished blue-grey metal (pink ore stays pink)
for o in dep.meshes:
    for sl in o.material_slots:
        m = sl.material
        if not m or not m.node_tree:
            continue
        b = m.node_tree.nodes.get('Principled BSDF')
        if b is None:
            continue
        print('DEPMAT', m.name, tuple(b.inputs['Base Color'].default_value)[:3])
        if 'Gem' in m.name:
            nt = m.node_tree
            for ln in list(nt.links):
                if ln.to_node == b and ln.to_socket.name in ('Base Color', 'Metallic', 'Roughness', 'Emission Color'):
                    nt.links.remove(ln)
            b.inputs['Base Color'].default_value = (*STEEL, 1)
            b.inputs['Metallic'].default_value = 1.0
            b.inputs['Roughness'].default_value = 0.24
            b.inputs['Emission Color'].default_value = (0.3, 0.45, 0.8, 1)
            b.inputs['Emission Strength'].default_value = 0.12

outcrops = []
for (pos, s, h) in [(T_VEIN, 0.36, 150), (S_VEIN, 0.34, 260)]:
    c = P.copy(dep, at=pos[:2], heading=h, label='outcrop')
    c.root.scale = (s, s, s)
    c.root.location.z = P.ground_z(pos.x, pos.y) - 0.08
    outcrops.append(c)

# veins: chips of metal breaking the surface from the deposit out to each outcrop
VEIN_PATHS = [[Vector((-1.6, -2.6, 0)), Vector((-2.4, -4.4, 0)), Vector((-2.2, -6.4, 0)), Vector((-3.2, -7.8, 0))],
              [Vector((2.6, 1.0, 0)), Vector((4.6, 1.9, 0)), Vector((6.6, 2.6, 0)), Vector((8.0, 3.0, 0))],
              [Vector((-2.8, 1.8, 0)), Vector((-4.6, 3.4, 0))],
              [Vector((1.8, -2.8, 0)), Vector((3.4, -4.4, 0))]]
chips = []
for path in VEIN_PATHS:
    for i in range(len(path) - 1):
        for k in range(3):
            u = (k + R.uniform(0, 0.8)) / 3
            p = path[i].lerp(path[i + 1], u) + Vector((R.uniform(-0.35, 0.35), R.uniform(-0.35, 0.35), 0))
            c = P.copy(dep, at=p[:2], heading=R.uniform(0, 360), label='chip')
            s = R.uniform(0.07, 0.15)
            c.root.scale = (s, s, s * R.uniform(0.7, 1.1))
            c.root.location.z = P.ground_z(p.x, p.y) - 0.05 - s * 0.6
            chips.append(c)

bpy.context.view_layer.update()
DLO, DHI = actor_bbox(dep)
print('DEPOSIT', DLO, DHI)

# glints: four-point stars popping on the facets, cool white-blue, facing the camera
M_GLINT = mat('Glint', GLINT, 3.0)
M_GLINT_H = mat('GlintHalo', (0.5, 0.7, 1.0), 1.0, alpha=0.25)
GLINTS = []


def glint(pos, t, size=0.35, dur=0.32):
    GLINTS.append((Vector(pos), t, size, dur))


def build_glints():
    for pos, t, size, dur in GLINTS:
        root = K.empty('GlintRoot')
        root.location = pos
        con = root.constraints.new('TRACK_TO')
        con.target = P.cam
        con.track_axis = 'TRACK_Z'
        con.up_axis = 'UP_Y'
        spin = K.empty('GlintSpin')
        spin.parent = root
        spin.rotation_mode = 'XYZ'
        for ang, ln in ((0, 1.0), (90, 1.0), (45, 0.45), (135, 0.45)):
            o = K.sphere('GlintRay', 1.0, M_GLINT, seg=(8, 4))
            o.scale = (ln, 0.035, 0.035)
            o.rotation_euler = (0, 0, math.radians(ang))
            o.parent = spin
            o.visible_shadow = False
        h = K.sphere('GlintCore', 0.12, M_GLINT_H, seg=(8, 6))
        h.parent = spin
        h.visible_shadow = False
        f0, f1 = P.T(t), P.T(t + dur)
        for f, sc, rot in [(f0, 0.01, 0), (f0 + (f1 - f0) * 0.35, size, 25), (f1, 0.01, 50)]:
            spin.scale = (sc, sc, sc)
            spin.rotation_euler.z = math.radians(rot)
            spin.keyframe_insert('scale', frame=f)
            spin.keyframe_insert('rotation_euler', index=2, frame=f)
        for o in [root, spin] + list(spin.children):
            K.show_between(o, int(f0), int(f1) + 1)


# hero deposit: glints run along the camera-side facets as the camera slides
# glints are placed on real facets facing the camera once the camera exists (place_glints)
GLINT_PLAN = [('dep', t, 0.55) for t in (0.12, 0.38, 0.62, 0.86, 1.1, 1.32)] + \
    [('t_vein', 2.1, 0.3), ('t_vein', 2.7, 0.28), ('s_vein', 3.6, 0.3), ('s_vein', 4.15, 0.28)] + \
    [('dep', t, 0.6) for t in (4.9, 5.25, 5.55, 5.85)]


# a cool sheen light that sweeps across the facets in the opening slide
sheen = plight('Sheen', (-3.5, -3.6, 2.8), [(0, 260), (1.5, 260), (1.55, 0)], (0.75, 0.85, 1.0), radius=0.4)
for t, p in [(0.0, (-3.5, -3.6, 2.8)), (1.5, (3.0, -3.4, 2.6))]:
    sheen.location = p
    sheen.keyframe_insert('location', frame=P.T(t))

# --------------------------------------------------------------------------- the Terran station
T_UF0, T_UF1 = 1.6, 2.95
st = P.load('terran_metal_station', at=TS[:2], heading=0, label='station')
st.unfold(T_UF0, T_UF1, stagger=0.14)
sm_ = st.model_root
sm_.rotation_mode = 'XYZ'
# the carriage settles onto its jacks: a sag, then a clunk per stage
for t, z in [(0, 0), (T_UF0, 0), (T_UF0 + 0.08, -0.06), (T_UF0 + 0.2, 0.0), (2.2, 0.0), (2.26, -0.035), (2.36, 0.0),
             (2.7, 0.0), (2.76, -0.03), (2.86, 0.0)]:
    sm_.location.z = z
    sm_.keyframe_insert('location', index=2, frame=P.T(t))

SAND = (0.42, 0.38, 0.3)


def dust_ring(center, t, r, n=12, size=0.6, life=1.0, opacity=0.22, rise=0.4):
    c = Vector(center)
    for i in range(n):
        a = 2 * math.pi * i / n + R.uniform(-0.15, 0.15)
        p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.9, 1.1)
        P.puff(p + Vector((0, 0, 0.15)), t + R.uniform(0, 0.05), size=size, n=1, rise=rise, life=life, color=SAND,
               opacity=opacity)


dust_ring(TS, T_UF0 + 0.05, 2.6, n=14, size=0.7)
dust_ring(TS, 2.25, 2.9, n=8, size=0.5, opacity=0.16)
P.cam_shake(T_UF0 + 0.05, 0.03, 0.25)
P.cam_shake(2.25, 0.02, 0.2)

fpiv = st.parts['FanPivot']
fan = st.parts['Fan']
fyaw = K.empty('FanYaw')
fyaw.parent = fpiv
fyaw.rotation_mode = 'XYZ'
mpi = fan.matrix_parent_inverse.copy()
fan.parent = fyaw
fan.matrix_parent_inverse = mpi
T_FAN = 2.9
for t, ang in [(0, 0), (T_FAN, 0), (T_FAN + 0.6, 330), (6.2, 330 + 1300 * (6.2 - T_FAN - 0.6))]:
    fyaw.rotation_euler.z = math.radians(ang)
    fyaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
K.set_interp(fyaw, 'LINEAR')

bpy.context.scene.frame_set(int(P.T(T_UF1 + 0.1)))
bpy.context.view_layer.update()
hlo, hhi = bbox(st.parts['Hopper'])
slo, shi = bbox(st.parts['Stack'])
HOPPER_MOUTH = Vector(((hlo.x + hhi.x) / 2, (hlo.y + hhi.y) / 2 - 0.2, hhi.z + 0.05))
STACK_TOP = Vector(((slo.x + shi.x) / 2, (slo.y + shi.y) / 2, shi.z + 0.05))
print('HOPPER', HOPPER_MOUTH, 'STACK', STACK_TOP)

# neon intake beam: outcrop -> hopper, steel shards ride it
T_BEAM = 3.05
OLO, OHI = actor_bbox(outcrops[0])
T_GRIP = Vector(((OLO.x + OHI.x) / 2, (OLO.y + OHI.y) / 2 + 0.2, OHI.z * 0.75))
M_BEAM = K.emit_mat('IntakeBeam', NEON, 2.0, alpha=0.22)
M_BEAMC = K.emit_mat('IntakeCore', NEON, 2.8)


def arc_pts(p0, p1, lift, n=14):
    return [p0.lerp(p1, i / n) + Vector((0, 0, 4 * lift * (i / n) * (1 - i / n))) for i in range(n + 1)]


beam_pts = arc_pts(HOPPER_MOUTH, T_GRIP, 0.6)
for m_, rad_ in ((M_BEAM, 0.09), (M_BEAMC, 0.022)):
    b = K.polyline('Intake', beam_pts, rad_, m_)
    b.visible_shadow = False
    b.data.bevel_resolution = 3
    b.data.bevel_factor_mapping_end = 'SPLINE'
    b.data.bevel_factor_end = 0.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_BEAM))
    b.data.bevel_factor_end = 1.0
    b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_BEAM + 0.15))
    K.show_between(b, P.T(T_BEAM), P.nf + 2)
plight('GripLight', T_GRIP + Vector((0, -0.4, 0.2)), [(0, 0), (T_BEAM + 0.1, 0), (T_BEAM + 0.2, 90), (6.2, 70)],
       NEON, radius=0.5)
M_SHARD = K.pbr_mat('SteelShard', STEEL, rough=0.25, metal=1.0, emit=NEON, emit_strength=0.5)
shard_ts = [T_BEAM + 0.25 + 0.26 * k for k in range(11)]
for k, t0 in enumerate(shard_ts):
    o = K.ico('Shard', 1.0, M_SHARD, sub=0)
    s = R.uniform(0.09, 0.14)
    o.scale = (s, s, s * 2.2)
    p0 = T_GRIP + Vector((R.uniform(-0.3, 0.3), R.uniform(-0.15, 0.15), R.uniform(-0.2, 0.2)))
    pts = arc_pts(p0, HOPPER_MOUTH + Vector((R.uniform(-0.25, 0.25), 0, 0)), 0.6 + R.uniform(-0.1, 0.15), n=8)
    dur = 0.5
    for i, p in enumerate(pts):
        u = i / 8
        o.location = p
        o.rotation_euler = (u * 8 + k, u * 6, u * 5 + k)
        fr = P.T(t0 + dur * u * u * (0.6 + 0.4 * u))
        o.keyframe_insert('location', frame=fr)
        o.keyframe_insert('rotation_euler', frame=fr)
    K.set_interp(o, 'LINEAR')
    K.show_between(o, P.T(t0), P.T(t0 + dur) + 1)

# smelter kindles orange, stack vents
T_IGN = 3.2
plight('Furnace', TS + Vector((-2.5, -0.6, 0.9)), [(0, 0), (T_IGN, 0), (T_IGN + 0.15, 380), (T_IGN + 0.5, 260),
                                                     (4.5, 320), (5.2, 250), (6.2, 320)], ORANGE, radius=0.5)
t = T_IGN + 0.1
while t < 6.0:
    P.puff(STACK_TOP + Vector((0, 0, 0.1)), t, size=0.4, n=1, rise=1.4, life=1.5, color=(0.55, 0.55, 0.56),
           opacity=0.2)
    t += 0.25

# --------------------------------------------------------------------------- the Siphon
T_LAND = 1.45
S_UF0, S_UF1 = 3.3, 4.5
sip = P.load('metal_siphon', at=SP[:2], heading=0, label='siphon')
bpy.context.view_layer.update()
sparts = sip.parts
KS = sparts['KeshMetalSiphon'].matrix_world.to_scale().x
piv = sparts['TurretPivot']
spire = sparts['Turret']
syaw = K.empty('SpireYaw')
syaw.parent = piv
syaw.rotation_mode = 'XYZ'
mpi = spire.matrix_parent_inverse.copy()
spire.parent = syaw
spire.matrix_parent_inverse = mpi
sip.unfold(S_UF0, S_UF1, stagger=0.08)

# suspended assembly: each part lifts off the base, hangs in the air on gold threads, then
# drifts down into its floating gap. delta_location on top of the unfold keys (metres / KS).
#        part           hang  gap   bob   hz   phase  hang window
FLOAT = {'Basin':       (1.1, 0.34, 0.035, 0.6, 0.3, (3.42, 3.95, 4.35)),
         'Horns':       (1.7, 0.26, 0.03, 0.5, 1.4, (3.36, 3.9, 4.4)),
         'TurretPivot': (2.4, 0.55, 0.05, 0.7, 2.5, (3.38, 4.0, 4.45))}
for n, (hang, gap, amp, hz, ph, (ta, tb, tc)) in FLOAT.items():
    o = sparts[n]
    keys = [(0, 0), (ta, 0), (ta + 0.35, hang * 0.85), (tb, hang), (tc, gap + 0.1), (S_UF1 + 0.12, gap - 0.03),
            (S_UF1 + 0.35, gap)]
    for t, dz in keys:
        o.delta_location = (0, 0, dz / KS)
        o.keyframe_insert('delta_location', frame=P.T(t))
    t = S_UF1 + 0.6
    while t <= 6.2:
        o.delta_location = (0, 0, (gap + amp * math.sin(2 * math.pi * hz * (t - S_UF1 - 0.35) + ph)) / KS)
        o.keyframe_insert('delta_location', frame=P.T(t))
        t += 0.25
    # slow turn while hanging
    if n != 'TurretPivot':
        o.rotation_mode = 'QUATERNION'
        spin_deg = 40 if n == 'Basin' else -55
        for t, d in [(0, 0), (ta, 0), (tb, spin_deg * 0.6), (tc, spin_deg * 0.15), (S_UF1 + 0.2, 0)]:
            o.delta_rotation_quaternion = Quaternion((0, 0, 1), math.radians(d))
            o.keyframe_insert('delta_rotation_quaternion', frame=P.T(t))
for t, deg in [(0, 0), (3.4, 0), (4.0, 120), (S_UF1, 160), (6.2, 160 + 90 * (6.2 - S_UF1))]:
    syaw.rotation_euler.z = math.radians(deg)
    syaw.keyframe_insert('rotation_euler', index=2, frame=P.T(t))

# descent: the packed disc spirals down onto its vein far behind the deposit
root = sip.root
root.rotation_mode = 'XYZ'
desc = [(0.0, (2.0, 10.0, 5.0), 9), (0.5, (5.0, 5.0, 3.6), 10), (0.95, (11.5, 4.6, 2.0), 7),
        (1.25, (10.8, 7.4, 0.6), 3), (T_LAND, tuple(SP), 0)]
for t, p, tilt in desc:
    u = t / T_LAND
    root.location = p
    a = math.atan2(SP.y - p[1], SP.x - p[0])
    root.rotation_euler = (math.radians(tilt) * math.sin(a), -math.radians(tilt) * math.cos(a),
                           math.radians(-480 * (1 - ss(u)) ** 1.5))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
K.set_interp(root, 'BEZIER')
for k in range(3):
    a = 2 * math.pi * k / 3
    W.lightning_thruster(P, root, 0.0, T_LAND + 0.02, local=(1.0 * math.cos(a), 1.0 * math.sin(a), 0.05),
                         axis=(0.35 * math.cos(a), 0.35 * math.sin(a), -1), length=2.2, width=0.045, n=1,
                         light=(k == 0))
dust_ring(SP, T_LAND, 2.6, n=12, size=0.8, opacity=0.2)

bpy.context.scene.frame_set(int(P.T(5.5)))
bpy.context.view_layer.update()
blo, bhi = bbox(sparts['Basin'])
BASIN_C = Vector(((blo.x + bhi.x) / 2, (blo.y + bhi.y) / 2, bhi.z))
BASIN_R = (bhi.x - blo.x) / 2
print('BASIN', blo, bhi)


def anchor_on(obj, world_pt):
    e = K.empty('Anchor')
    e.parent = obj
    e.matrix_parent_inverse = obj.matrix_world.inverted()
    e.location = world_pt
    return e


def under(obj, drop=0.0):
    lo, hi = bbox(obj)
    return anchor_on(obj, Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + drop)))


basin_anchor = anchor_on(sparts['Basin'], BASIN_C)
holds = [(under(sparts['Basin'], 0.05), [SP + Vector((-1.2, -0.6, 0.15)), SP + Vector((1.2, -0.6, 0.15))]),
         (under(sparts['Horns'], 0.2), [SP + Vector((-1.6, 0.4, 0.15)), SP + Vector((1.6, 0.4, 0.15))]),
         (under(spire, 0.0), [SP + Vector((0, 0.3, 0.6))])]
# threads of gold lightning hold the parts while they hang
for anc, feet in holds:
    for ft in feet:
        W.lightning(P, ft, anc, 3.42, 4.5, width=0.03, jag=0.16, branches=1, segs=8, sparks_=False, light=False)
plight('HoldLight', SP + Vector((0, -0.5, 1.4)), [(0, 0), (3.4, 0), (3.55, 500), (4.4, 450), (4.6, 120), (6.2, 120)],
       GOLD, radius=1.2)

# horns tap the outcrop, liquid gold threads climb into the basin
T_TAP = 4.45
SLO, SHI = actor_bbox(outcrops[1])
S_GRIP = Vector(((SLO.x + SHI.x) / 2, (SLO.y + SHI.y) / 2 + 0.2, SHI.z * 0.8))
W.lightning(P, basin_anchor, S_GRIP, T_TAP, T_TAP + 0.2, width=0.025, jag=0.2, branches=2, segs=10)
M_RIV = mat('River', (1.0, 0.55, 0.1), 2.2)
M_RIVG = mat('RiverGlow', GOLD, 0.9, alpha=0.16)
M_MOTE = mat('Mote', (1.0, 0.5, 0.08), 2.4)


def bez(a, b, c, u):
    return a * (1 - u) ** 2 + b * 2 * u * (1 - u) + c * u * u


T_FLOW = 4.55
top = BASIN_C + Vector((0, 0, 0.4))
for j in range(3):
    ph = 2 * math.pi * j / 3
    p0 = S_GRIP + Vector((0.25 * math.cos(ph), 0.2 * math.sin(ph), 0))
    mid = (p0 + top) / 2 + Vector((0, 0, 1.3))
    pts = []
    for i in range(41):
        u = i / 40
        q = bez(p0, mid, top, u)
        r = 0.15 * math.sin(math.pi * u)
        a = ph + u * 6 * math.pi
        pts.append(q + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
    pts.append(BASIN_C + Vector((0, 0, -0.05)))
    for m_, rad in ((M_RIV, 0.025), (M_RIVG, 0.08)):
        b = K.polyline('River', pts, rad, m_)
        b.visible_shadow = False
        b.data.bevel_factor_mapping_end = 'SPLINE'
        b.data.bevel_factor_end = 0.0
        b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_FLOW + 0.07 * j))
        b.data.bevel_factor_end = 1.0
        b.data.keyframe_insert('bevel_factor_end', frame=P.T(T_FLOW + 0.07 * j + 0.45))
        K.show_between(b, P.T(T_FLOW), P.nf + 2)
    tt = T_FLOW + 0.1 * j
    while tt < 6.0:
        o = K.sphere('Mote', 0.045, M_MOTE, seg=(6, 4))
        o.visible_shadow = False
        for i in range(0, 41, 8):
            o.location = pts[i]
            o.keyframe_insert('location', frame=P.T(tt + 0.5 * i / 40))
        K.set_interp(o, 'LINEAR')
        K.show_between(o, int(P.T(tt)), int(P.T(tt + 0.5)) + 1)
        tt += 0.09
plight('BasinLight', (0, 0, 0.5), [(0, 0), (T_FLOW + 0.3, 0), (T_FLOW + 0.6, 400), (6.2, 500)], GOLD, radius=0.8,
       parent=basin_anchor)

# --------------------------------------------------------------------------- camera
PRE = 1 / FPS
P.camera([
    # 1: low slide across the deposit's facets; the Siphon spirals down behind it
    (0.0, (-1.4, -5.2, 0.45), (0.2, 0.0, 1.45), 30),
    (CUT1 - PRE, (2.4, -4.9, 0.6), (1.0, 0.3, 1.5), 32),
    # 2: south of the Terran station, its outcrop in the foreground: the unfold
    (CUT1, (-2.0, -10.6, 0.8), (-4.8, -5.3, 1.2), 28),
    (2.4, (-2.4, -10.9, 1.2), (-4.9, -5.2, 1.3), 28),
    (CUT2 - PRE, (-3.0, -11.1, 1.6), (-5.0, -5.5, 1.3), 28),
    # 3: across the field, past the Siphon's outcrop: suspended parts assembling
    (CUT2, (7.2, -0.4, 1.25), (9.9, 6.8, 2.2), 24),
    (4.0, (7.7, 0.0, 1.3), (10.0, 6.9, 2.0), 24),
    (CUT3 - PRE, (8.2, 0.4, 1.35), (9.9, 6.6, 1.7), 25),
    # 4: rising hero frame: station near left, deposit glinting mid, Siphon far right
    (CUT3, (-6.0, -13.4, 1.2), (-0.2, 0.2, 1.5), 33),
    (6.0, (-6.5, -14.4, 2.5), (0.0, 0.4, 1.3), 33),
], shake=0.01, cuts=(CUT1, CUT2, CUT3))


def facets(actor):
    """World (centre, normal) of the actor's polished metal faces."""
    out = []
    for o in actor.meshes:
        mw = o.matrix_world
        n3 = mw.to_3x3()
        gem = {i for i, sl in enumerate(o.material_slots) if sl.material and 'Gem' in sl.material.name}
        for pg in o.data.polygons:
            if pg.material_index in gem and pg.area > 0.0005:
                out.append((mw @ pg.center, (n3 @ pg.normal).normalized()))
    return out


bpy.context.view_layer.update()
FACETS = {'dep': facets(dep), 't_vein': facets(outcrops[0]), 's_vein': facets(outcrops[1])}
for key, t, size in GLINT_PLAN:
    bpy.context.scene.frame_set(int(round(P.T(t))))
    cp = P.cam.matrix_world.translation.copy()
    fw = -(P.cam.matrix_world.to_3x3() @ Vector((0, 0, 1)))
    good = []
    for c, n in FACETS[key]:
        d = (cp - c)
        if c.z < 0.5 or d.normalized().dot(fw) > -0.93:
            continue                       # keep to the middle of the frame
        if n.dot(d.normalized()) > 0.55:
            good.append((n.dot(d.normalized()) + R.uniform(0, 0.3), c, n))
    if good:
        good.sort(key=lambda g: -g[0])
        _, c, n = R.choice(good[:max(1, len(good) // 4)])
        glint(c + n * 0.04, t, size=size)
bpy.context.scene.frame_set(1)
build_glints()

# ---- sound
P.sfx(0.0, 'shard_wake', gain=0.2, pos=DEP, rate=1.2)
for _g in GLINTS:
    P.sfx(_g[1], 'crystal_spike', gain=0.12, rate=1.8, pos=_g[0])
P.sfx(0.0, 'crackle_loop', gain=0.18, dur=T_LAND, pos=SP)
P.sfx(T_UF0, 'hydraulic', gain=0.5, pos=TS)
for _t in (T_UF0 + 0.05, 2.25, 2.75):
    P.sfx(_t, 'mech_clunk', gain=0.5, pos=TS)
P.sfx(T_FAN, 'whirr_loop', gain=0.3, dur=6.0 - T_FAN, rate=0.75, pos=TS)
P.sfx(T_BEAM, 'beam_start', gain=0.4, rate=1.2, pos=TS)
P.sfx(T_BEAM + 0.1, 'tractor_loop', gain=0.3, dur=6.0 - T_BEAM - 0.1, pos=TS)
for _t in shard_ts:
    P.sfx(_t + 0.45, 'impact_metal', gain=0.1, rate=1.5, pos=HOPPER_MOUTH)
P.sfx(3.4, 'crackle_loop', gain=0.35, dur=1.1, pos=SP)
P.sfx(3.42, 'hover_arc', gain=0.35, pos=SP)
P.sfx(T_TAP, 'zap_small', gain=0.4, pos=SP)
P.sfx(T_FLOW, 'motes_loop', gain=0.35, dur=6.0 - T_FLOW, pos=SP)

P.render()
