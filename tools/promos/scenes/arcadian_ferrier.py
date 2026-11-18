"""Ferrier (Arcadian tug): the ore run to the Landing Ring. A Sifter hangs over its ore field,
grinding, with a sealed cargo pod of refined ore glowing ember-orange in its crop. The Ferrier
sweeps in past the camera on short crackling gold lifters and brakes alongside. Gold arcs leap
from its two tall claws to the pod; the pod lifts out of the Sifter's crop, floats across and
drops into the claws, which flare as they lock on. Laden, the Ferrier glides off across the
field to the Landing Ring and noses up its mouth. The crown reaches up with arcs, the claws let
go, and the pod floats over the bowl and settles onto the crown. A bolt from the sky lights a
column of gold light down through the halo onto it, and the pod rises away up the column in a
train of light rings while the empty Ferrier backs out of the mouth.

Timeline (s): 0-0.8 Ferrier sweeps in and brakes beside the Sifter | 0.85 claws arc onto the pod
| 0.95-1.6 pod lifts across into the claws, lock flare | 1.75-3.55 laden glide to the ring |
3.6 brakes in the mouth | 3.7 crown arcs reach up | 3.8-4.45 pod floats over the bowl onto the
crown | 4.6 sky bolt, column of light | 4.75-6.0 pod rises up the column; Ferrier backs out.
Shots: A 0-1.75 low from the field (Sifter left, Ferrier sweeping in right) | B 1.75-3.5 low
front three-quarter tracking the laden Ferrier with the ring growing behind | C 3.5-6.0 low by
the mouth, tilting up after the pod as it rides the column; Ferrier foreground."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_ferrier', seconds=6.0, seed=23)
R = P.rnd
FPS = P.fps
NF = P.nf

GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
EMBER = (1.0, 0.3, 0.04)
AMBER = (1.0, 0.42, 0.06)
DUST = (0.6, 0.5, 0.42)


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- layout
SIF_AT = (-19.0, -1.0)          # Sifter mining, heading 90 (jaws face +y into the cluster)
CLUSTER = (-19.0, 1.4)
T_PARK = 0.8                     # Ferrier brakes alongside
T_GRAB, T_LIFT0, T_LOCK = 0.85, 0.95, 1.6
T_GO, T_MOUTH = 1.75, 3.6
T_REACH, T_REL0, T_SET = 3.7, 3.8, 4.45
T_COL = 4.6
T_RISE = 4.75
T_BACK = 4.7

P.env('highland', sun=(60, 0, 140), sun_energy=4.0, props=26,
      clear=[(0, 0, 13), (-18, -2, 8), (-10, -2, 6)],
      deposits=[('ore', (-23.5, 3.5), 0.7), ('ore', (-15.5, 4.5), 0.45), ('ore', (-25, -4), 0.4)])
P.flatten(0, 0, 13)
P.flatten(-18, -2, 8)
P.flatten(-10, -2, 6)
bpy.context.view_layer.update()

# ------------------------------------------------------------------------------- materials
M_BOLT = K.emit_mat('FrBolt', GOLD, 2.6)
M_CORE = K.emit_mat('FrBoltCore', (1.0, 0.7, 0.28), 2.8)
M_GLOW = K.emit_mat('FrBoltGlow', DEEP_GOLD, 1.0, alpha=0.22)
M_SPARK = K.emit_mat('FrSpark', (1.0, 0.62, 0.2), 2.8)
M_LIFT = K.emit_mat('FrLifter', DEEP_GOLD, 2.2)
M_LIFT_H = K.emit_mat('FrLifterHalo', DEEP_GOLD, 0.8, alpha=0.2)


def soft_emit(name, col, strength, power=2.0, blend=0.5):
    """Emission that fades to transparent toward the silhouette (a soft volume of light)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = blend
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = power
    pw.use_clamp = True
    nt.links.new(inv.outputs[0], pw.inputs[0])
    gain = nt.nodes.new('ShaderNodeMath')
    gain.operation = 'MULTIPLY'
    gain.use_clamp = True
    gain.inputs[1].default_value = 1.0
    nt.links.new(pw.outputs[0], gain.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*col, 1)
    em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(gain.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    m['gain_node'] = gain.name
    return m


def key_gain(m, t, v):
    g = m.node_tree.nodes[m['gain_node']]
    g.inputs[1].default_value = v
    g.inputs[1].keyframe_insert('default_value', frame=P.T(t))


# ------------------------------------------------------------------------------- lightning
def jag_pts(p0, p1, segs, jag, ctrl=None):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        base = p0 * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + p1 * u * u if ctrl is not None else p0 + d * u
        env = math.sin(math.pi * u)
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * env if 0 < i < segs else Vector()
        pts.append(base + off)
    return pts


def bolt_frame(pts, f, width, parent=None, glow=True, forks=1, core=True):
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
        dv = (pts[k + 1] - pts[k - 1])
        side = dv.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        bl = dv.length * R.uniform(0.8, 1.6)
        dirb = (dv.normalized() + side * R.uniform(-1.2, 1.2) + Vector((0, 0, R.uniform(-.6, .6)))).normalized()
        objs.append(K.polyline('BoltFork', [a, a + dirb * bl * 0.5, a + dirb * bl], width * 0.55, M_BOLT))
    for o in objs:
        if parent is not None:
            o.parent = parent
        o.visible_shadow = False
        K.show_between(o, f, f + 1)
    return objs


def gold_sparks(pos, t, size, n=10):
    f0 = P.T(t)
    for _ in range(n):
        sp = K.sphere('Spk', 1.0, M_SPARK, seg=(6, 4))
        sp.visible_shadow = False
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.3, 1))).normalized() * size * R.uniform(2.5, 4.5)
        sp.scale = (0.16 * size, 0.03 * size, 0.03 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + Vector((0, 0, -0.3))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)
    P.light(pos, t, GOLD, energy=1200 * size, dur=0.15, radius=0.5)


# ------------------------------------------------------------------------------- the ring
ring = P.load('landing_ring', at=(0, 0), heading=180, label='ring')
bpy.context.view_layer.update()
crown_pv = ring.parts['CrownPivot']
halo_pv = ring.parts['HaloPivot']
CROWN = crown_pv.matrix_world.translation.copy()
HALO = halo_pv.matrix_world.translation.copy()
CX = CROWN.x
print('crown', CROWN, 'halo', HALO)
# the mouth faces -x (toward the ore field); bowl/rim/mouth heights from the landing ring clip


def surface_z(x, y):
    dx = CX - x               # distance out toward the mouth
    r = math.hypot(x - CX, y)
    if dx > 4.3 and abs(y) < 2.9:
        return max(0.0, 0.84 * (1 - (dx - 4.3) / 3.2))
    if r < 6.2:
        return 0.78
    if r < 7.4:
        return 0.55
    return 0.0


# crown and halo turn slowly; both surge as the pod is set down and the column strikes
crown_pv.rotation_mode = 'XYZ'
halo_pv.rotation_mode = 'XYZ'
ac = ah = 0.0
for f in range(0, NF + 2):
    t = (f - 1) / FPS
    rc = 25 + 260 * math.exp(-((t - (T_COL + 0.2)) / 0.35) ** 2) + 60 * ss((t - T_SET) / 0.4)
    rh = -15 - 220 * math.exp(-((t - (T_COL + 0.4)) / 0.4) ** 2) - 30 * ss((t - T_SET) / 0.4)
    ac += rc / FPS
    ah += rh / FPS
    if f % 2 == 0 or f in (0, 1):
        crown_pv.rotation_euler.z = math.radians(ac)
        halo_pv.rotation_euler.z = math.radians(ah)
        crown_pv.keyframe_insert('rotation_euler', index=2, frame=f)
        halo_pv.keyframe_insert('rotation_euler', index=2, frame=f)
K.set_interp(crown_pv, 'LINEAR')
K.set_interp(halo_pv, 'LINEAR')

nest_mat = bpy.data.materials.get('KeshLandingNestMat')
if nest_mat is not None:
    es = nest_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
    base_es = es.default_value
    for t, v in [(0, base_es), (T_SET - 0.05, base_es), (T_SET + 0.1, base_es * 1.5), (T_COL, base_es * 1.3),
                 (T_COL + 0.1, base_es * 1.9), (T_COL + 0.6, base_es * 1.5), (6.1, base_es * 1.5)]:
        es.default_value = v
        es.keyframe_insert('default_value', frame=P.T(t))

# ------------------------------------------------------------------------------- the Sifter
clus = P.load('deposit_ore', at=CLUSTER, heading=35, size=2.2, label='cluster')
clus.root.location.z = P.ground_z(*CLUSTER) - 0.08
sif = P.load('sifter', at=SIF_AT, heading=90, label='sifter')
gzs = P.ground_z(*SIF_AT)
H_SIF = 0.22
sif.root.location.z = gzs + H_SIF
sif.hover_bob(0.03, 1.2)
sif.spin('GrinderPivot', 700, 0.0, 6.0, axis=0)
SIF_CROP = Vector((-1.25, 0.0, 1.0))      # model space: the open ore crop on its back

# the rest of its load: ember ore heaped in the crop round the pod
heap_mat = K.pbr_mat('Fr_Heap', (1.0, 0.45, 0.2), rough=0.45, emit=EMBER, emit_strength=0.5)
for i in range(14):
    a = 2 * math.pi * i / 14 + R.uniform(-0.2, 0.2)
    rr = R.uniform(0.45, 0.7)
    c = K.ico('HeapChunk', R.uniform(0.12, 0.2), heap_mat, sub=1)
    c.parent = sif.model_root
    c.location = SIF_CROP + Vector((rr * math.cos(a), rr * math.sin(a), R.uniform(0.05, 0.2)))
    c.rotation_euler = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    c.scale = (1.15, 1.0, 0.8)

# Sifter keeps grinding: a few pink chips and a little ore dust at the jaws
ORE_PINK = (1.0, 0.3, 0.56)
chip_mat = K.emit_mat('FrChip', ORE_PINK, 1.1)
BITE = Vector((2.15, 0.0, 0.55))
t = 0.0
while t < 6.0:
    c = K.ico('Chip', R.uniform(0.025, 0.045), chip_mat, sub=1)
    c.parent = sif.model_root
    c.visible_shadow = False
    s2 = R.choice((-1, 1))
    q0 = BITE + Vector((R.uniform(0, .2), s2 * 0.2, 0.0))
    v = Vector((R.uniform(-0.3, 0.8), s2 * R.uniform(0.8, 1.6), R.uniform(0.6, 1.4)))
    cl = R.uniform(0.35, 0.5)
    f0 = P.T(t)
    for j in range(5):
        u = j / 4 * cl
        c.location = q0 + v * u + Vector((0, 0, -4.9 * u * u))
        c.keyframe_insert('location', frame=f0 + u * FPS)
    K.show_between(c, int(f0), int(f0 + cl * FPS) + 1)
    t += R.uniform(0.05, 0.11)
for s in (0.2, 1.4, 2.6, 3.8, 5.0):
    P.puff(Vector((CLUSTER[0], CLUSTER[1] - 0.6, 0.3)), s, size=0.3, n=1, rise=0.4, life=0.8,
           color=(0.62, 0.48, 0.48), opacity=0.2)

# ------------------------------------------------------------------------------- the Ferrier
fer = P.load('ferrier', at=(-26, -9), heading=40, label='ferrier')
CRADLE = Vector((-0.43, 0.0, 1.58))       # model space: pod centre held between the two claws
CLAW_TIPS = [Vector((-0.72, 0.0, 1.78)), Vector((-0.16, 0.0, 1.78)),
             Vector((-1.0, 0.45, 1.78)), Vector((-1.0, -0.45, 1.78)),
             Vector((0.12, 0.45, 1.78)), Vector((0.12, -0.45, 1.78))]
H_FER = 0.32
crop_w = sif.model_root.matrix_world @ SIF_CROP
# park so the cradle sits 2.7 m east of the Sifter's crop, nose toward the ring (+x)
PARK = Vector((crop_w.x + 2.7 + 0.43, crop_w.y, 0))
gzf = P.ground_z(PARK.x, PARK.y)
MOUTH = Vector((CX - 5.7, 0.0, 0))
Z_MOUTH = surface_z(MOUTH.x, 0) + 0.75
BACK = Vector((CX - 10.4, 3.4, 0))
print('park', PARK, 'mouth', MOUTH, Z_MOUTH)
fer.path([
    (0.0, (-22.6, -8.2, gzf + H_FER + 0.1), 55.0),
    (0.35, (PARK.x - 4.2, PARK.y - 4.0, gzf + H_FER + 0.05), 40.0),
    (0.65, (PARK.x - 0.8, PARK.y - 0.7, gzf + H_FER), 12.0),
    (T_PARK, (PARK.x, PARK.y, gzf + H_FER), 0.0),
    (T_GO, (PARK.x, PARK.y, gzf + H_FER + 0.05), 0.0),
    (T_GO + 0.5, (PARK.x + 2.0, PARK.y + 0.35, gzf + H_FER + 0.1), 3.0),
    (2.9, (MOUTH.x - 5.0, -0.4, H_FER + 0.15), 2.0),
    (3.35, (MOUTH.x - 1.0, -0.05, Z_MOUTH - 0.1), 0.0),
    (T_MOUTH, (MOUTH.x, 0.0, Z_MOUTH), 0.0),
    (T_BACK, (MOUTH.x, 0.0, Z_MOUTH), 0.0),
    (5.3, (MOUTH.x - 1.3, 0.4, Z_MOUTH - 0.2), 25.0),
    (6.0, (BACK.x, BACK.y, H_FER + 0.12), 105.0),
])
fer.hover_bob(0.03, 0.9)
FM = fer.model_root


def fer_mat(t):
    sc = bpy.context.scene
    sc.frame_set(int(round(P.T(t))))
    return FM.matrix_world.copy()


def fer_alt(t):
    """Model-space depth from the hull to whatever is under it."""
    p = fer.pos_at(t)
    return p.z - max(P.ground_z(p.x, p.y), surface_z(p.x, p.y))


# lifter skirt: short dense gold crackle under the hull (Sifter/Darter style)
FER_EMIT = [(-0.95, 0.45), (-0.95, -0.45), (0.95, 0.4), (0.95, -0.4), (0.0, 0.5), (0.0, -0.5)]
SIF_EMIT = [(0.45, 0.0), (-1.2, 0.6), (-1.2, -0.6)]


def jag(p0, p1, segs, amp):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            e = math.sin(math.pi * u)
            q += Vector((R.uniform(-amp, amp), R.uniform(-amp, amp), 0)) * e
        pts.append(q)
    return pts


fer_alts = {f: fer_alt((f - 1) / FPS) for f in range(1, NF + 2)}
for f in range(1, NF + 2):
    for actor, emits, h, n in ((fer, FER_EMIT, fer_alts[f], 7), (sif, SIF_EMIT, H_SIF, 6)):
        for ex, ey in emits:
            for k in range(n):
                if R.random() < 0.3:
                    continue
                p0 = Vector((ex + R.uniform(-.12, .12), ey + R.uniform(-.1, .1), 0.08))
                ang = R.uniform(0, 2 * math.pi)
                r = R.uniform(0.12, 0.38)
                p1 = Vector((p0.x + r * math.cos(ang), p0.y + r * math.sin(ang), -h + 0.02))
                pts = jag(p0, p1, 3, 0.07)
                for o in (K.polyline('Lift', pts, 0.008, M_LIFT), K.polyline('LiftHalo', pts, 0.03, M_LIFT_H)):
                    o.parent = actor.model_root
                    o.visible_shadow = False
                    K.show_between(o, f, f + 1)
for actor, emits in ((fer, FER_EMIT[:4]), (sif, SIF_EMIT)):
    for ex, ey in emits:
        L = K.link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
        L.parent = actor.model_root
        L.location = (ex, ey, -0.15)
        L.data.color = GOLD
        L.data.energy = 30
        L.data.shadow_soft_size = 0.4

P.dust(fer, 0.0, 0.7, every=0.15, size=0.4, color=DUST)
P.dust(fer, T_GO + 0.3, 3.0, every=0.15, size=0.4, color=DUST)

# ------------------------------------------------------------------------------- the cargo pod
M_POD_CORE = K.emit_mat('FrPodCore', AMBER, 1.3)
M_POD_HALO = soft_emit('FrPodHalo', EMBER, 1.1, power=1.6, blend=0.4)
key_gain(M_POD_HALO, 0.0, 0.35)
M_POD_SHELL = K.pbr_mat('FrPodShell', (0.55, 0.36, 0.18), rough=0.3, metal=0.9)
M_POD_SEAM = K.emit_mat('FrPodSeam', (1.0, 0.62, 0.2), 2.6)
POD_R = 0.42
for t, v in [(0, 0.35), (T_LOCK - 0.05, 0.35), (T_LOCK + 0.05, 0.9), (T_LOCK + 0.4, 0.45), (T_SET - 0.05, 0.45),
             (T_SET + 0.05, 0.9), (T_COL + 0.1, 1.0), (6.1, 0.8)]:
    key_gain(M_POD_HALO, t, v)


def make_pod(name):
    """Ember ore pod: glowing ovoid core in a bronze cage of three bands and two end caps."""
    root = K.empty(name)
    root.rotation_mode = 'XYZ'
    core = K.sphere(name + 'Core', POD_R, M_POD_CORE, seg=(20, 12))
    core.scale = (0.88, 1.25, 0.88)
    core.parent = root
    halo = K.sphere(name + 'Halo', POD_R * 1.55, M_POD_HALO, seg=(20, 12))
    halo.scale = (1.0, 1.2, 1.0)
    halo.parent = root
    halo.visible_shadow = False
    for k, yy in enumerate((-0.32, 0.0, 0.32)):
        rr = POD_R * (0.98 if yy == 0 else 0.86) * 0.9
        pts = [(rr * math.cos(2 * math.pi * i / 32), yy, rr * math.sin(2 * math.pi * i / 32)) for i in range(33)]
        b = K.polyline(name + 'Band', pts, 0.045, M_POD_SHELL)
        b.parent = root
    for s in (-1, 1):
        cap = K.sphere(name + 'Cap', POD_R * 0.5, M_POD_SHELL, seg=(14, 8))
        cap.scale = (1.0, 0.55, 1.0)
        cap.location = (0, s * POD_R * 1.18, 0)
        cap.parent = root
        seam = K.polyline(name + 'Seam', [(0.16 * math.cos(2 * math.pi * i / 20), s * POD_R * 1.32,
                                           0.16 * math.sin(2 * math.pi * i / 20)) for i in range(21)], 0.018, M_POD_SEAM)
        seam.parent = root
    lt = K.link(bpy.data.objects.new(name + 'Light', bpy.data.lights.new(name + 'Light', 'POINT')))
    lt.parent = root
    lt.data.color = AMBER
    lt.data.energy = 120
    lt.data.shadow_soft_size = 0.5
    return root


def key_pod(root, f, loc, rz):
    root.location = loc
    root.rotation_euler = (0, 0, rz)
    root.keyframe_insert('location', frame=f)
    root.keyframe_insert('rotation_euler', frame=f)


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


POD_IN_CROP = SIF_CROP + Vector((0, 0, 0.42))
# 1) in the Sifter's crop
pod_s = make_pod('PodSifter')
pod_s.parent = sif.model_root
pod_s.location = POD_IN_CROP
K.show_between(pod_s, 0, int(P.T(T_LIFT0)))
# 2) floating across into the claws (world space)
pod_a = make_pod('PodLift')
fA0, fA1 = int(P.T(T_LIFT0)), int(P.T(T_LOCK))
pA0 = sif.model_root.matrix_world @ POD_IN_CROP
MF_PARK = fer_mat(T_LOCK)
pA3 = MF_PARK @ CRADLE
for f in range(fA0, fA1 + 1):
    u = (f - fA0) / (fA1 - fA0)
    w = ss(u)
    p = bez(pA0, pA0 + Vector((0, 0, 1.6)), pA3 + Vector((-0.4, 0, 1.4)), pA3, w)
    p.z += 0.1 * math.sin(math.pi * min(1, u * 1.1)) * math.sin(14 * u)
    key_pod(pod_a, f, p, math.radians(lerp(90.0, 0.0, w)))
K.show_between(pod_a, fA0, fA1 + 1)
# 3) locked in the claws (rides the hull)
pod_f = make_pod('PodClaws')
pod_f.parent = FM
pod_f.location = CRADLE
pod_f.rotation_euler = (0, 0, 0)     # long axis along the gap between the claws
pod_f.keyframe_insert('location', frame=fA1 + 1)
pod_f.location = CRADLE + Vector((0, 0, -0.1))
pod_f.keyframe_insert('location', frame=fA1 + 3)
pod_f.location = CRADLE
pod_f.keyframe_insert('location', frame=fA1 + 6)
fB0, fB1 = int(P.T(T_REL0)), int(P.T(T_SET))
K.show_between(pod_f, fA1 + 1, fB0)
# 4) released over the bowl onto the crown, then up the column (world space)
pod_b = make_pod('PodRing')
MF_M = fer_mat(T_REL0)
pB0 = MF_M @ CRADLE
SEAT = Vector((CX, CROWN.y, CROWN.z + 0.62))
for f in range(fB0, fB1 + 1):
    u = (f - fB0) / (fB1 - fB0)
    w = ss(u)
    p = bez(pB0, pB0 + Vector((0.6, 0, 1.3)), SEAT + Vector((-1.2, 0, 1.6)), SEAT, w)
    key_pod(pod_b, f, p, math.radians(25 * w))
# set down: a small squash on the crown, hold, then ride up the column
for f in range(fB1 + 1, NF + 2):
    t = (f - 1) / FPS
    z = SEAT.z - 0.06 * math.exp(-((t - T_SET - 0.05) / 0.06) ** 2)
    if t > T_RISE:
        u = (t - T_RISE)
        z = SEAT.z + 1.6 * u * u + 2.8 * u ** 3
    key_pod(pod_b, f, Vector((SEAT.x, SEAT.y, z)), math.radians(25 + 140 * max(0, t - T_SET) ** 1.5))
K.show_between(pod_b, fB0, NF + 2)
print('pod end z', SEAT.z + 1.6 * (6 - T_RISE) ** 2 + 2.8 * (6 - T_RISE) ** 3)

# ------------------------------------------------------------------------------- grab arcs
# 1) claws reach for the pod in the Sifter's crop, arcs hold it all the way across
for f in range(int(P.T(T_GRAB)), fA1 + 3):
    t = (f - 1) / FPS
    M = fer_mat(t)
    if f < fA0:
        pc = pA0
    else:
        bpy.context.scene.frame_set(min(f, fA1))
        pc = pod_a.matrix_world.translation.copy()
    for _ in range(3 if f < fA1 else 2):
        tip = M @ R.choice(CLAW_TIPS)
        d = (pc - tip)
        tgt = pc - d.normalized() * POD_R * 0.8 + Vector((R.uniform(-.15, .15), R.uniform(-.15, .15), R.uniform(-.1, .1)))
        ctrl = (tip + tgt) * 0.5 + Vector((0, 0, 0.5 + 0.12 * d.length))
        bolt_frame(jag_pts(tip, tgt, 7, 0.25, ctrl=ctrl), f, 0.022, forks=1 if R.random() < 0.5 else 0)
    if f < fA0 + 3:      # the crop rim crackles as it lets go
        for _ in range(2):
            a = R.uniform(0, 2 * math.pi)
            q0 = sif.model_root.matrix_world @ (SIF_CROP + Vector((0.6 * math.cos(a), 0.6 * math.sin(a), 0.1)))
            bolt_frame(jag_pts(q0, pc, 4, 0.4), f, 0.014, forks=0, core=False)
P.light(pA0 + Vector((0, 0, 0.5)), T_GRAB, GOLD, energy=1500, dur=0.25, radius=0.6)
# lock: claws flare, sparks, a little thunk
gold_sparks(pA3 + Vector((0, 0, 0.2)), T_LOCK + 0.02, 0.55, n=10)
P.light(pA3 + Vector((0, 0, 0.6)), T_LOCK, GOLD, energy=2500, dur=0.3, radius=0.8)
claw_light = K.link(bpy.data.objects.new('ClawLight', bpy.data.lights.new('ClawLight', 'POINT')))
claw_light.parent = FM
claw_light.location = CRADLE + Vector((0, 0, 0.9))
claw_light.data.color = EMBER
claw_light.data.shadow_soft_size = 0.6
for t, e in [(0, 0), (T_LOCK - 0.05, 0), (T_LOCK + 0.05, 260), (T_LOCK + 0.4, 110), (T_REL0, 110),
             (T_REL0 + 0.25, 0)]:
    claw_light.data.energy = e
    claw_light.data.keyframe_insert('energy', frame=P.T(t))

# 2) at the ring: the crown reaches up for the pod, the claws hand it over
for f in range(int(P.T(T_REACH)), fB1 + 4):
    t = (f - 1) / FPS
    bpy.context.scene.frame_set(f)
    pc = (pod_b if f >= fB0 else pod_f).matrix_world.translation.copy()
    for _ in range(3):
        aa = R.uniform(0, 2 * math.pi)
        p0 = Vector((CX + 1.1 * math.cos(aa), CROWN.y + 1.1 * math.sin(aa), CROWN.z + 0.25))
        d = pc - p0
        tgt = pc - d.normalized() * POD_R * 0.8
        ctrl = (p0 + tgt) * 0.5 + Vector((0, 0, 0.4 + 0.15 * d.length))
        bolt_frame(jag_pts(p0, tgt, 12, 0.16, ctrl=ctrl), f, 0.022, forks=1 if R.random() < 0.5 else 0)
    if f < fB0 + 5:
        M = fer_mat(t)
        for _ in range(2):
            tip = M @ R.choice(CLAW_TIPS)
            bolt_frame(jag_pts(tip, pc, 4, 0.4), f, 0.014, forks=0, core=False)
P.light(SEAT, T_SET, GOLD, energy=3000, dur=0.3, radius=1.0)
gold_sparks(SEAT + Vector((0, 0, -0.2)), T_SET, 0.6, n=10)
for i in range(8):
    aa = 2 * math.pi * i / 8 + R.uniform(-0.2, 0.2)
    P.puff(Vector((CX + 2.4 * math.cos(aa), 2.4 * math.sin(aa), 0.95)), T_SET, size=0.7, n=1, rise=0.3,
           life=0.7, color=(0.95, 0.78, 0.55), opacity=0.12)

# ------------------------------------------------------------------------------- column of light
COL_TOP = 90.0
COL_R = 1.5


def cyl_mesh(name, r, verts=32):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    ring0 = [bm.verts.new((r * math.cos(2 * math.pi * i / verts), r * math.sin(2 * math.pi * i / verts), 0)) for i in range(verts)]
    ring1 = [bm.verts.new((v.co.x, v.co.y, -1.0)) for v in ring0]
    for i in range(verts):
        j = (i + 1) % verts
        bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


M_COLUMN = soft_emit('FrColumn', (1.0, 0.45, 0.06), 1.6, power=1.6, blend=0.35)
M_COLCORE = soft_emit('FrColumnCore', (1.0, 0.62, 0.2), 2.0, power=3.0, blend=0.3)
COL_GAIN = {M_COLUMN.name: 0.24, M_COLCORE.name: 0.3}
for nm, r_, m_ in (('Column', COL_R, M_COLUMN), ('ColumnCore', COL_R * 0.45, M_COLCORE)):
    o = K.link(bpy.data.objects.new(nm, cyl_mesh(nm, r_)))
    o.data.materials.append(m_)
    o.location = (CX, CROWN.y, COL_TOP)
    o.visible_shadow = False
    for t, s in ((0.0, 0.001), (T_COL, 0.001), (T_COL + 0.14, COL_TOP - CROWN.z - 0.2)):
        o.scale = (1, 1, s)
        o.keyframe_insert('scale', frame=P.T(t))
    K.set_interp(o, 'LINEAR')
    K.show_between(o, int(P.T(T_COL)), NF + 2)
for m_ in (M_COLUMN, M_COLCORE):
    g_ = COL_GAIN[m_.name]
    key_gain(m_, T_COL, 0.0)
    key_gain(m_, T_COL + 0.08, 1.3 * g_)
    key_gain(m_, T_COL + 0.35, 0.8 * g_)
    key_gain(m_, 6.1, 0.9 * g_)

for f in range(int(P.T(T_COL - 0.06)), int(P.T(T_COL + 0.18)) + 1):
    t = (f - 1) / FPS
    top = Vector((CX + R.uniform(-1, 1), R.uniform(-1, 1), 45))
    mid = HALO + Vector((R.uniform(-0.4, 0.4), R.uniform(-0.4, 0.4), 0))
    bot = SEAT + Vector((0, 0, POD_R))
    bolt_frame(jag_pts(top, mid, 12, 0.08), f, 0.07, forks=2)
    bolt_frame(jag_pts(mid, bot, 6, 0.3), f, 0.05, forks=1)
    if R.random() < 0.7:
        for _ in range(2):
            a = R.uniform(0, 2 * math.pi)
            p0 = HALO + Vector((2.7 * math.cos(a), 2.7 * math.sin(a), 0))
            bolt_frame(jag_pts(p0, mid, 5, 0.4), f, 0.025, forks=0, core=False)
P.light(HALO, T_COL, GOLD, energy=9000, dur=0.35, radius=2.0)
gold_sparks(SEAT + Vector((0, 0, 0.4)), T_COL + 0.05, 0.9, n=12)
P.cam_shake(T_COL + 0.02, 0.07, dur=0.25)
hl = K.link(bpy.data.objects.new('HeartLight', bpy.data.lights.new('HeartLight', 'POINT')))
hl.location = (CX, CROWN.y, CROWN.z + 1.2)
hl.data.color = (1.0, 0.6, 0.2)
hl.data.shadow_soft_size = 1.5
for t, e in [(0, 0), (T_COL, 0), (T_COL + 0.1, 4000), (T_COL + 0.5, 2000), (6.1, 2000)]:
    hl.data.energy = e
    hl.data.keyframe_insert('energy', frame=P.T(t))

# light rings slide up the column with the pod
M_RING = soft_emit('FrRiseRing', (1.0, 0.55, 0.12), 2.6, power=0.6, blend=0.2)
for k in range(3):
    o2 = K.polyline('RiseRing', [(math.cos(2 * math.pi * i / 40), math.sin(2 * math.pi * i / 40), 0) for i in range(41)],
                    0.022, M_RING)
    o2.visible_shadow = False
    f0 = int(P.T(T_RISE - 0.05))
    for f in range(f0, NF + 2):
        t = (f - 1) / FPS
        bpy.context.scene.frame_set(f)
        pz = pod_b.matrix_world.translation.z
        lag = (k + 1) * 0.55 * ss((t - T_RISE) / 0.4)
        o2.location = (CX, CROWN.y, max(SEAT.z - 0.3, pz - lag))
        rr = COL_R * (0.75 + 0.1 * k) * (1 + 0.25 * (1 - ss((t - T_RISE) / 0.3)))
        o2.scale = (rr, rr, rr)
        o2.keyframe_insert('location', frame=f)
        o2.keyframe_insert('scale', frame=f)
    K.set_interp(o2, 'LINEAR')
    K.show_between(o2, f0, NF + 2)

M_MOTE = K.emit_mat('FrMote', (1.0, 0.68, 0.25), 2.4)
for i in range(36):
    o = K.sphere('Mote', 1.0, M_MOTE, seg=(6, 4))
    o.visible_shadow = False
    s = R.uniform(0.03, 0.06)
    o.scale = (s, s, s * 3)
    a0 = R.uniform(0, 2 * math.pi)
    rr = R.uniform(0.3, COL_R * 0.95)
    t0 = R.uniform(T_COL + 0.1, 5.7)
    life = R.uniform(0.7, 1.3)
    z0 = R.uniform(CROWN.z + 0.5, 6)
    for k in range(5):
        u = k / 4
        a = a0 + u * 1.5
        o.location = (CX + rr * math.cos(a), CROWN.y + rr * math.sin(a), z0 + u * life * 4.0)
        o.keyframe_insert('location', frame=P.T(t0 + u * life))
    K.show_between(o, int(P.T(t0)), int(P.T(t0 + life)))

bpy.context.scene.frame_set(1)

# ------------------------------------------------------------------------------- camera
CUT1, CUT2 = 42 / 24, 84 / 24          # 1.75, 3.5
SC = sif.root.location.copy()
P.camera([
    # A: low on the field: the Ferrier sweeps in from the left and brakes alongside the Sifter,
    #    then we push in and rise a touch to watch the pod float across into its claws
    (0.0, (-14.6, -11.0, 1.3), (-20.0, -4.8, 1.0), 25),
    (0.8, (-15.2, -10.2, 1.8), (-17.4, -2.2, 1.3), 27),
    (CUT1 - 1 / 24, (-15.9, -9.0, 2.4), (-17.5, -1.6, 1.8), 30),
    # B: rear three-quarter chase: the laden Ferrier heads for the ring, which grows ahead
    (CUT1, (-20.6, -6.4, 1.8), (-13.0, -1.4, 1.6), 30),
    (2.6, (-17.0, -5.4, 2.0), (-9.0, -0.6, 2.0), 30),
    (CUT2 - 1 / 24, (-12.6, -4.6, 2.2), (-3.0, 0.0, 2.4), 28),
    # C: low from the open north-west side of the mouth: the handover over the bowl, then tilt
    #    up after the pod in the column while the empty Ferrier backs out toward us
    (CUT2, (-11.0, 6.4, 1.5), (-3.6, 0.0, 2.2), 26),
    (T_SET, (-10.6, 5.8, 1.6), (-2.2, 0.0, 2.5), 27),
    (6.0, (-14.4, 9.2, 1.8), (-5.8, -1.0, 4.0), 20),
], cuts=(CUT1, CUT2), shake=0.012)

# effects never cast shadows
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.active_material is not None:
        m = o.active_material
        if 'emit_node' in m or m.name.startswith(('SoftFire', 'Fireball', 'SoftPuff')):
            o.visible_shadow = False

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.25, dur=6.0)                 # lifter skirts
P.sfx(T_GRAB, 'tractor_loop', gain=0.5, dur=T_LOCK - T_GRAB)   # claws arc onto the pod
P.sfx(T_GRAB, 'zap_small', gain=0.5)
P.sfx(T_LOCK, 'mech_clunk', gain=0.7)                          # pod locks into the claws
P.sfx(T_LOCK, 'impact_gold', gain=0.35)
P.sfx(T_REACH, 'tractor_loop', gain=0.5, dur=T_SET - T_REACH)  # crown takes the pod
P.sfx(T_SET, 'mech_clunk', gain=0.5, rate=0.8)
P.sfx(T_SET, 'power_up_arc', gain=0.6)
P.sfx(T_COL, 'shockwave', gain=0.6)                            # sky bolt opens the column
P.sfx(T_COL, 'zap_lightning', gain=0.6)
P.sfx(T_RISE, 'motes_loop', gain=0.5, dur=6.0 - T_RISE)        # pod rides the column up
P.sfx(T_RISE, 'whirr_loop', gain=0.3, dur=6.0 - T_RISE, rate=0.8)

P.render()
