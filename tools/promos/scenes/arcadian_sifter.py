"""Sifter (Arcadian ore miner): a work story on a pink ore field. The Sifter skims in low on short
crackling gold lifters, brakes over a crystal cluster at the edge of the field and dips its big
silver stag-beetle jaws round it. The grinder spins up: pink chips spray from the bite, and the
ore dissolves into a stream of gold motes that pours back over the bronze hull into the open
crop on its back. The heap in the crop climbs and its ember-orange glow pulses brighter with
every surge. The cluster is ground down to a stump; the grinder spins down, and the loaded
Sifter swings round and heads home past the camera, crop brimming. Ore buys everything.

Timeline (s): 0-1.75 low tracking shot, Sifter glides in over the field | 1.7 brake, jaws dip
round the cluster | 1.75 grinder spins up | 1.9-4.6 chips + gold motes stream into the crop,
heap grows, glow pulses brighter | 4.6 cluster gone, grinder spins down | 4.75-6.0 loaded
Sifter backs off and turns for home, low 3/4 hero frame on the brimming crop."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_sifter', seconds=6.0, seed=31)
R = P.rnd
FPS = P.fps

GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
EMBER = (1.0, 0.3, 0.04)
ORE_PINK = (1.0, 0.3, 0.56)

STOP = (0.0, 0.0)          # Sifter mines here, heading 0 (jaws face +x)
CLUSTER = (2.35, 0.0)      # the crystal cluster it eats, between the jaws
T_STOP = 1.7
T_BITE = 1.85
T_FILL0, T_FILL1 = 1.95, 4.55
T_DONE = 4.6
H_MOVE, H_MINE = 0.32, 0.24

P.env('highland', sun=(58, 0, 125), sun_energy=4.0, props=26,
      clear=[(0, 0, 9), (-10, -5, 6)],
      deposits=[('ore', (5.2, 4.6), 0.8), ('ore', (7.5, -3.8), 0.5), ('ore', (-2.5, 6.5), 0.35)])
P.flatten(0, 0, 8)
P.flatten(-9, -5, 6)
bpy.context.view_layer.update()

_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('Sf_' + key, col, strength, alpha=alpha)
    return _mats[key]


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


# --------------------------------------------------------------------------- the cluster
clus = P.load('deposit_ore', at=CLUSTER, heading=35, size=2.6, label='cluster')
clus.root.location.z = P.ground_z(*CLUSTER) - 0.08
cz = clus.root.location.z
for t, k in [(0.0, 1.0), (T_FILL0, 1.0), (2.6, 0.86), (3.3, 0.64), (4.0, 0.38), (T_DONE, 0.12)]:
    clus.root.scale = (k, k, k)
    clus.root.location.z = cz - (1 - k) * 0.25
    clus.root.keyframe_insert('scale', frame=P.T(t))
    clus.root.keyframe_insert('location', index=2, frame=P.T(t))

# --------------------------------------------------------------------------- the Sifter
sif = P.load('sifter', at=(-15, -6), heading=20, label='sifter')
gz = P.ground_z(0, 0)
sif.path([(0.0, (-15.5, -6.6, gz + H_MOVE)), (0.6, (-10.2, -4.6, gz + H_MOVE)),
          (1.15, (-4.6, -1.6, gz + H_MOVE)), (1.5, (-1.2, -0.2, gz + 0.44)),
          (T_STOP, (STOP[0], STOP[1], gz + H_MINE), 0.0), (4.75, (STOP[0], STOP[1], gz + H_MINE), 0.0),
          (5.2, (-0.7, -0.3, gz + 0.28), -25.0), (5.6, (-1.6, -1.2, gz + 0.3), -90.0),
          (6.0, (-2.6, -3.4, gz + 0.32), -110.0)])
sif.hover_bob(0.035, 1.3)
m = sif.model_root
m.rotation_mode = 'XYZ'
# brake and bite: the nose dips the jaws down round the cluster, then holds a little low while
# grinding (with a small shudder on each surge), and lifts as it backs off.
for t, pitch in [(1.55, 0.0), (T_BITE, 5.0), (2.05, 2.2), (2.2, 3.2), (4.55, 3.2), (4.8, -1.5),
                 (5.1, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))

# grinder: spin up, grind, spin down (axis X in the model)
sif.spin('GrinderPivot', 260, 1.45, T_BITE, axis=0)
sif.spin('GrinderPivot', 1100, T_BITE, T_DONE, axis=0)
sif.spin('GrinderPivot', 300, T_DONE, 5.3, axis=0)
sif.spin('GrinderPivot', 60, 5.3, 6.0, axis=0)

# grinder glow light at the bite
gl = K.link(bpy.data.objects.new('BiteLight', bpy.data.lights.new('BiteLight', 'POINT')))
gl.parent = m
gl.location = (2.0, 0, 0.55)
gl.data.color = EMBER
gl.data.shadow_soft_size = 0.3
for t, e in [(0, 15), (T_BITE, 15), (T_BITE + 0.15, 90), (T_DONE, 90), (5.0, 15)]:
    gl.data.energy = e
    gl.data.keyframe_insert('energy', frame=P.T(t))


def hover_at(t):
    if t < 1.5:
        return H_MOVE
    if t < T_STOP:
        return H_MOVE + (H_MINE - H_MOVE) * ss((t - 1.5) / (T_STOP - 1.5))
    if t < 4.75:
        return H_MINE
    return H_MINE + (0.32 - H_MINE) * ss((t - 4.75) / 1.25)


# --------------------------------------------------------------------------- lifters
# Short, dense crackle under the hull: many small arcs from the three lifter pads straight
# down to the ground, redrawn every frame.
bolt_mat = mat('Lifter', DEEP_GOLD, 2.2)
halo_mat = mat('LifterHalo', DEEP_GOLD, 0.8, alpha=0.2)
EMIT = [(0.45, 0.0), (-1.2, 0.6), (-1.2, -0.6)]


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


for f in range(1, P.nf + 2):
    t = (f - 1) / FPS
    h = hover_at(t)
    for ex, ey in EMIT:
        for k in range(7):
            if R.random() < 0.25:
                continue
            p0 = Vector((ex + R.uniform(-.1, .1), ey + R.uniform(-.08, .08), 0.05))
            ang = R.uniform(0, 2 * math.pi)
            r = R.uniform(0.2, 0.55)
            p1 = Vector((p0.x + r * math.cos(ang), p0.y + r * math.sin(ang), -h + 0.02))
            pts = jag(p0, p1, 3, 0.07)
            for o in (K.polyline('Lift', pts, 0.008, bolt_mat), K.polyline('LiftHalo', pts, 0.03, halo_mat)):
                o.parent = m
                o.visible_shadow = False
                K.show_between(o, f, f + 1)
for ex, ey in EMIT:
    L = K.link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
    L.parent = m
    L.location = (ex, ey, -0.15)
    L.data.color = GOLD
    L.data.energy = 35
    L.data.shadow_soft_size = 0.4

P.dust(sif, 0.0, 1.8, every=0.12, size=0.5)

# --------------------------------------------------------------------------- the crop + heap
CROP = Vector((-1.25, 0.0, 1.0))     # model space: centre of the ore crop on its back
heap_mat = K.pbr_mat('Sf_Heap', (1.0, 0.45, 0.2), rough=0.45, emit=(1.0, 0.36, 0.06), emit_strength=0.3)
heap_b = heap_mat.node_tree.nodes.get('Principled BSDF')
pink_heap = K.pbr_mat('Sf_HeapPink', ORE_PINK, rough=0.35, emit=ORE_PINK, emit_strength=0.35)
SURGES = [2.35, 2.95, 3.5, 4.05, 4.5]
for t, v in [(0, 0.2), (T_FILL0, 0.2)] + [x for s in SURGES for x in ((s, 0.4 + 0.12 * SURGES.index(s)),
                                                                      (s + 0.25, 0.25 + 0.1 * SURGES.index(s)))] + \
        [(5.0, 0.85), (6.0, 0.75)]:
    heap_b.inputs['Emission Strength'].default_value = v
    heap_b.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))

N_CHUNK = 26
for i in range(N_CHUNK):
    u = i / (N_CHUNK - 1)
    t_in = T_FILL0 + 0.35 + (T_FILL1 - T_FILL0 - 0.3) * u
    rad = 0.75 * (1 - 0.55 * u) * math.sqrt(R.random())
    a = R.uniform(0, 2 * math.pi)
    p = CROP + Vector((rad * math.cos(a), rad * math.sin(a), 0.0 + 0.32 * u + R.uniform(-0.04, 0.04)))
    c = K.ico('Chunk', R.uniform(0.13, 0.22) * (1.1 - 0.3 * u), pink_heap if i % 3 == 0 else heap_mat, sub=1)
    c.parent = m
    c.location = p
    c.rotation_euler = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    c.scale = (0.01,) * 3
    c.keyframe_insert('scale', frame=P.T(t_in) - 1)
    c.scale = (1.15, 1.0, 0.8)
    c.keyframe_insert('scale', frame=P.T(t_in + 0.12))

crop_light = K.link(bpy.data.objects.new('CropLight', bpy.data.lights.new('CropLight', 'POINT')))
crop_light.parent = m
crop_light.location = CROP + Vector((0, 0, 0.7))
crop_light.data.color = EMBER
crop_light.data.shadow_soft_size = 0.6
for t, e in [(0, 12), (T_FILL0, 12)] + [x for j, s in enumerate(SURGES) for x in ((s, 40 + 18 * j), (s + 0.25, 25 + 14 * j))] + \
        [(5.0, 120), (6.0, 110)]:
    crop_light.data.energy = e
    crop_light.data.keyframe_insert('energy', frame=P.T(t))

# --------------------------------------------------------------------------- the stream
# Pink chips spray out of the bite and fall; the ore turns into gold motes that pour back over
# the hull into the crop, in surges.
chip_mat = mat('Chip', ORE_PINK, 1.1)
mote_mat = mat('Mote', GOLD, 2.4)
mote_halo = mat('MoteHalo', DEEP_GOLD, 0.7, alpha=0.14)
BITE = Vector((2.15, 0.0, 0.55))


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


def surge_rate(t):
    k = 0.6
    for s in SURGES:
        k += 0.9 * math.exp(-((t - s) / 0.18) ** 2)
    return k


t = T_FILL0
while t < T_FILL1:
    dens = surge_rate(t)
    # gold mote
    side = R.choice((-1, 1))
    p0 = BITE + Vector((R.uniform(-.1, .1), side * R.uniform(0.0, 0.3), R.uniform(-.1, .15)))
    p1 = Vector((1.3, side * R.uniform(0.35, 0.7), 1.5 + R.uniform(-.1, .2)))
    p2 = Vector((0.0, side * R.uniform(0.2, 0.55), 1.95 + R.uniform(-.1, .2)))
    p3 = CROP + Vector((R.uniform(-.3, .3), R.uniform(-.3, .3), 0.35))
    life = R.uniform(0.5, 0.7)
    sz = R.uniform(0.022, 0.038)
    o = K.sphere('Mote', sz, mote_mat, seg=(6, 4))
    hl = K.sphere('MoteH', sz * 1.9, mote_halo, seg=(6, 4))
    hl.parent = o
    o.parent = m
    o.visible_shadow = False
    hl.visible_shadow = False
    f0 = P.T(t)
    nk = 6
    for j in range(nk + 1):
        u = j / nk
        o.location = bez(p0, p1, p2, p3, u)
        o.keyframe_insert('location', frame=f0 + life * FPS * u)
    K.show_between(o, int(f0), int(f0 + life * FPS) + 1)
    # pink chip flung sideways out of the jaws
    if R.random() < 0.55 * dens:
        c = K.ico('Chip', R.uniform(0.025, 0.05), chip_mat, sub=1)
        c.parent = m
        c.visible_shadow = False
        s2 = R.choice((-1, 1))
        q0 = BITE + Vector((R.uniform(0, .2), s2 * 0.2, 0.0))
        v = Vector((R.uniform(-0.3, 0.8), s2 * R.uniform(0.8, 1.8), R.uniform(0.6, 1.6)))
        cl = R.uniform(0.35, 0.5)
        for j in range(5):
            u = j / 4 * cl
            c.location = q0 + v * u + Vector((0, 0, -4.9 * u * u))
            c.keyframe_insert('location', frame=f0 + u * FPS)
        K.show_between(c, int(f0), int(f0 + cl * FPS) + 1)
    t += 0.022 / dens

# a little pink ore dust at the bite, on every surge
for s in [T_BITE] + SURGES[::2]:
    p = sif.pos_at(2.5) + Vector((2.5, R.choice((-0.9, 0.9)), 0.1))
    P.puff(p, s, size=0.3, n=1, rise=0.4, life=0.8, color=(0.62, 0.48, 0.48), opacity=0.22)

# --------------------------------------------------------------------------- camera
CUT1, CUT2 = 42 / 24, 108 / 24     # 1.75, 4.5
P.camera([
    # shot 1: low tracking alongside as it glides in over the field
    (0.0, (-11.0, -12.0, 1.5), (-15.0, -6.5, 0.7), 32),
    (0.8, (-7.5, -10.5, 1.6), (-8.4, -3.8, 0.7), 32),
    (1.45, (-4.0, -8.0, 1.7), (-1.2, -0.4, 0.7), 38),
    (CUT1 - 1 / 24, (-3.6, -7.6, 1.7), (0.6, 0.0, 0.7), 40),
    # shot 2: low and frontal on the jaws, then rise and swing to follow the stream into the crop
    (CUT1, (5.6, -1.1, 0.75), (1.7, 0.0, 0.6), 32),
    (2.6, (5.6, -2.9, 1.4), (1.4, 0.0, 0.75), 34),
    (3.5, (4.2, -4.4, 2.7), (0.4, 0.0, 1.0), 34),
    (CUT2 - 1 / 24, (1.6, -5.0, 3.6), (-0.6, 0.0, 1.1), 34),
    # shot 3: low 3/4 hero as the loaded Sifter swings round for home
    (CUT2, (-7.5, -3.0, 2.3), (-1.0, -0.4, 0.8), 32),
    (6.0, (-8.6, -6.2, 2.4), (-2.9, -3.7, 0.8), 34),
], cuts=(CUT1, CUT2), shake=0.012)

P.render()
