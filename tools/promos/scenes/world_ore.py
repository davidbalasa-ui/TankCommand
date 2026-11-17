"""Ore field (neutral resource): ore buys everything, so both sides come for it.

Dawn on the flats. A big pink ore deposit, crystal spires on a rock base, catches the first low
sun while the camera circles it slowly. Two miners crest in from opposite sides at once: a
Terran Prospector grinding in from the west, an Arcadian Sifter skimming in from the east on
crackling gold lifters. Both brake hard at the deposit, nose to nose across the crystals, and
square up: the Prospector revs its cutter drum in a burst of dust, the Sifter rears its jaws.
Then both dig in on the same rock. Pink ore rides up the Prospector's ramp into its hopper; the
Sifter grinds its side down into a stream of gold motes that pours into the crop on its back.
Each bite chips its own outcrop of the deposit down. The camera rises into a 3/4 hero frame:
the deposit glowing in the middle, a miner gnawing at each side, both loads climbing.

Timeline (s): 0-1.75 dawn orbit, deposit alone | 1.75 cut: wide low, both miners arrive |
2.35 / 2.5 brakes | 2.55-2.95 standoff (drum rev, jaws rear) | 2.95 both dig in |
3.5 cut: over the Prospector's drum, the Sifter across the crystals | 4.5 cut: rising 3/4
hero orbit to the end."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('world_ore', seconds=6.0, seed=41)
R = P.rnd
FPS = P.fps
NF = P.nf

GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
EMBER = (1.0, 0.3, 0.04)
ORE_PINK = (1.0, 0.28, 0.55)
ORE_DUST = (0.62, 0.38, 0.4)

DEP = Vector((0.0, 0.0, 0.0))
DEP_SIZE = 7.0
# miners park on either side of the deposit, each biting its own outcrop
PRO_STOP = Vector((-6.5, -1.2, 0.0))    # heading 0: drum faces +x (toward the deposit)
SIF_STOP = Vector((6.1, 1.0, 0.0))      # heading 180: jaws face -x
OUT_W = (-3.9, -1.2)                    # outcrop the Prospector eats
OUT_E = (3.75, 1.0)                     # outcrop the Sifter eats

T_P_STOP = 2.35
T_S_STOP = 2.5
T_DIG = 2.95
T_END = 6.2
CUT1, CUT2, CUT3 = 42 / 24, 84 / 24, 108 / 24   # 1.75, 3.5, 4.5

P.env('dusk', sun=(76, 0, 20), sun_energy=3.6, props=30,
      clear=[(0, 0, 13), (-16, -2, 6), (16, 2, 6)],
      deposits=[('ore', (-9.0, 8.5), 0.4), ('ore', (10.5, -8.0), 0.45), ('ore', (4.0, 11.0), 0.3)])
P.flatten(0, 0, 13)
P.flatten(-15, -2, 7)
P.flatten(15, 2, 7)
bpy.context.view_layer.update()
GZ = P.ground_z(0, 0)


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('Or_' + key, col, strength, alpha=alpha)
    return _mats[key]


# --------------------------------------------------------------------------- the deposit (hero)
dep = P.load('deposit_ore', at=DEP[:2], heading=25, size=DEP_SIZE, label='deposit')
dep.root.location.z = P.ground_z(*DEP[:2]) - 0.2

outcrops = []
for (x, y), h in ((OUT_W, 140), (OUT_E, 300)):
    c = P.copy(dep, at=(x, y), heading=h, label='outcrop')
    c.root.scale = (0.36, 0.36, 0.36)
    c.root.location.z = P.ground_z(x, y) - 0.08
    outcrops.append(c)


def chew(c, t0, t1, k1):
    """Outcrop ground down: shrinks and sinks between t0 and t1 in steps (one per bite surge)."""
    z0 = c.root.location.z
    s0 = c.root.scale.x
    n = 5
    for i in range(n + 1):
        u = i / n
        k = s0 * (1 - (1 - k1) * u)
        c.root.scale = (k, k, k)
        c.root.location.z = z0 - (s0 - k) * 0.6
        c.root.keyframe_insert('scale', frame=P.T(t0 + (t1 - t0) * u))
        c.root.keyframe_insert('location', index=2, frame=P.T(t0 + (t1 - t0) * u))


chew(outcrops[0], T_DIG + 0.1, 5.9, 0.55)
chew(outcrops[1], T_DIG + 0.15, 5.9, 0.5)

# dawn: the sun climbs a little and warms the crystals through the first shot
sun = P.sun
for t, e in [(0, 2.6), (1.6, 3.6), (6.2, 3.8)]:
    sun.data.energy = e
    sun.data.keyframe_insert('energy', frame=P.T(t))


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


# inner glow of the deposit: a soft pink light inside the spires, breathing slowly, brighter
# when the miners bite into it
dep_glow = [(0, 300)]
t = 0.0
while t < 6.2:
    dep_glow.append((t, 300 + 120 * math.sin(t * 2.4) + (300 if t > T_DIG else 0)))
    t += 0.25
plight('DepGlow', DEP + Vector((0, -0.8, 2.2)), dep_glow, ORE_PINK, radius=1.6)

# --------------------------------------------------------------------------- the Prospector
pr = P.load('prospector', at=(-24, -3.0), heading=0, label='prospector')
pr.path([(0.0, (-24.0, -3.4)), (1.0, (-17.5, -2.6)), (1.8, (-11.6, -1.6)), (2.15, (-8.2, -1.25)),
         (T_P_STOP, PRO_STOP[:2], 0.0), (T_END, PRO_STOP[:2], 0.0)])
P.dust(pr, 0.6, T_P_STOP, every=0.09, size=0.9, color=(0.36, 0.22, 0.13))
pm = pr.model_root
pm.rotation_mode = 'XYZ'
# brake: nose dips, rocks back; then a shudder while the drum bites
for t, pitch in [(T_P_STOP - 0.08, 0.0), (T_P_STOP + 0.08, 3.2), (T_P_STOP + 0.3, -1.2),
                 (T_P_STOP + 0.5, 0.0), (T_DIG - 0.02, 0.0), (T_DIG + 0.1, 2.2), (T_DIG + 0.3, 0.6)]:
    pm.rotation_euler.y = math.radians(pitch)
    pm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
t = T_DIG + 0.35
while t < T_END:
    pm.location.z = 0.014 * math.sin(t * 47.0)
    pm.keyframe_insert('location', index=2, frame=P.T(t))
    t += 1 / 12

# drum: idle on the drive in, a rev burst in the standoff, then grinding speed from the bite
drum = pr.parts['DrumPivot']
drum.rotation_mode = 'XYZ'


def drum_rate(t):
    if t < T_P_STOP:
        return -120.0
    if t < 2.6:
        return -120.0 * (1 - ss((t - T_P_STOP) / 0.2))
    if t < T_DIG - 0.05:          # rev burst
        u = (t - 2.6) / (T_DIG - 0.05 - 2.6)
        return -1100.0 * math.sin(math.pi * min(1.0, u)) ** 0.6
    return -760.0 * ss((t - T_DIG + 0.05) / 0.25)


ang = 0.0
t = 0.0
while t <= T_END:
    ang += drum_rate(t) / FPS
    drum.rotation_euler.y = math.radians(ang)
    drum.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    t += 1 / FPS
K.set_interp(drum, 'LINEAR')
P.sfx(2.6, 'servo', gain=0.6, pos=PRO_STOP)

PM = Matrix.Translation(PRO_STOP)


def WP(x, y, z):
    return PM @ Vector((x, y, z))


DRUM_FACE = WP(2.45, 0.0, 0.55)
RAMP_LOW = WP(1.55, 0.0, 0.95)
RAMP_TOP = WP(0.05, 0.0, 1.85)

# rev burst: a gout of ore dust thrown forward off the drum
for k in range(5):
    P.puff(DRUM_FACE + Vector((0.4 + 0.2 * k, R.uniform(-0.6, 0.6), 0.1)), 2.7 + 0.04 * k, size=0.6, n=1,
           rise=0.5, life=0.9, color=(0.36, 0.22, 0.13), opacity=0.28)

# chips + ore dust at the cutting face
t = T_DIG + 0.05
while t < 5.95:
    P.puff(DRUM_FACE + Vector((0.3, R.uniform(-0.7, 0.7), R.uniform(-0.2, 0.2))), t, size=0.4, n=1,
           rise=0.7, life=0.8, color=ORE_DUST, opacity=0.2)
    t += 0.16

chip_mat = mat('Chip', ORE_PINK, 1.1)


def chips(origin, t0, t1, rate, side_dir, up=1.0, parent=None):
    """Pink crystal chips flung out of a bite."""
    t = t0
    while t < t1:
        c = K.ico('Chip', R.uniform(0.03, 0.06), chip_mat, sub=1)
        c.visible_shadow = False
        if parent is not None:
            c.parent = parent
        s2 = R.choice((-1, 1))
        q0 = origin + Vector((R.uniform(-0.1, 0.2), s2 * R.uniform(0.1, 0.5), 0.0))
        v = Vector((side_dir * R.uniform(0.2, 1.2), s2 * R.uniform(0.6, 1.8), R.uniform(0.8, 2.0) * up))
        cl = R.uniform(0.35, 0.55)
        f0 = P.T(t)
        for j in range(5):
            u = j / 4 * cl
            c.location = q0 + v * u + Vector((0, 0, -4.9 * u * u))
            c.keyframe_insert('location', frame=f0 + u * FPS)
        K.show_between(c, int(f0), int(f0 + cl * FPS) + 1)
        t += rate * R.uniform(0.6, 1.4)


chips(DRUM_FACE + Vector((0.2, 0, 0)), T_DIG + 0.05, 5.95, 0.06, 1.0)

# ore chunks: drum face -> up the ramp -> over the lip -> heap in the hopper
M_ORE = K.pbr_mat('OreChunk', (0.62, 0.1, 0.3), rough=0.3, emit=ORE_PINK, emit_strength=0.35)
M_ORE_HOT = K.pbr_mat('OreChunkHot', (0.7, 0.12, 0.34), rough=0.25, emit=ORE_PINK, emit_strength=0.8)
slots = []
for z, spread, n in [(0.95, 1.0, 10), (1.18, 0.85, 8), (1.42, 0.65, 6), (1.66, 0.42, 4)]:
    for i in range(n):
        a = i / n * 2 * math.pi + R.uniform(0, 0.5)
        r = spread * math.sqrt(R.uniform(0.15, 1.0))
        slots.append(WP(-1.1 + math.cos(a) * r * 0.95, math.sin(a) * r * 0.75, z + R.uniform(-0.05, 0.05)))
NS = len(slots)
FLY = 0.42
p_times = [T_DIG + 0.15 + (5.35 - T_DIG - 0.15) * (k / (NS - 1)) ** 0.85 for k in range(NS)]
p_lands = []
for slot, t0 in zip(slots, p_times):
    s = R.uniform(0.12, 0.17)
    rot0 = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    f = K.ico('OreFly', 1.0, M_ORE_HOT, sub=1)
    f.scale = (s * 0.8, s * 0.7, s * 1.1)
    start = DRUM_FACE + Vector((0.0, R.uniform(-0.5, 0.5), 0.0))
    over = RAMP_TOP + Vector((0, (slot.y - PRO_STOP.y) * 0.4, 0.25))
    pts = [(0.0, start), (0.1, RAMP_LOW + Vector((0, (start.y - PRO_STOP.y) * 0.5, 0.1))), (0.24, over)]
    for i in range(1, 4):
        u = i / 3
        pts.append((0.24 + (FLY - 0.24) * u, over.lerp(slot + Vector((0, 0, 0.05)), u) + Vector((0, 0, 0.45 * u * (1 - u)))))
    for dt, p in pts:
        f.location = p
        f.rotation_euler = (rot0[0] + dt * 9, rot0[1] + dt * 7, rot0[2])
        f.keyframe_insert('location', frame=P.T(t0 + dt))
        f.keyframe_insert('rotation_euler', frame=P.T(t0 + dt))
    K.set_interp(f, 'LINEAR')
    K.show_between(f, P.T(t0), P.T(t0 + FLY))
    o = K.ico('OreRest', 1.0, M_ORE, sub=0)
    o.location = slot
    o.rotation_euler = (rot0[0] + FLY * 9, rot0[1] + FLY * 7, rot0[2])
    o.scale = (s, s * 0.8, s * 1.5)
    K.show_between(o, P.T(t0 + FLY), P.T(6.3))
    p_lands.append(t0 + FLY)

plight('HopperGlow', WP(-1.1, 0.0, 2.3), [(0, 0), (p_lands[0], 0), (4.2, 30), (p_lands[-1], 80), (6.2, 90)],
       ORE_PINK, radius=0.8)
plight('DrumGlow', DRUM_FACE + Vector((0.5, 0, 0.4)), [(0, 0), (T_DIG, 0), (T_DIG + 0.3, 30), (6.2, 30)],
       ORE_PINK, radius=0.5)

# --------------------------------------------------------------------------- the Sifter
H_MOVE, H_MINE, H_REAR = 0.34, 0.24, 0.5
sif = P.load('sifter', at=(31, 5.4), heading=180, label='sifter')
sif.path([(0.0, (31.0, 5.4, GZ + H_MOVE)), (1.0, (21.0, 3.4, GZ + H_MOVE)), (1.9, (12.0, 1.7, GZ + H_MOVE)),
          (2.25, (8.2, 1.15, GZ + 0.44)), (T_S_STOP, (SIF_STOP.x, SIF_STOP.y, GZ + H_MINE), 180.0),
          (2.7, (SIF_STOP.x + 0.15, SIF_STOP.y, GZ + H_REAR), 180.0),
          (T_DIG - 0.05, (SIF_STOP.x + 0.1, SIF_STOP.y, GZ + H_REAR), 180.0),
          (T_DIG + 0.1, (SIF_STOP.x, SIF_STOP.y, GZ + H_MINE), 180.0),
          (T_END, (SIF_STOP.x, SIF_STOP.y, GZ + H_MINE), 180.0)])
sif.hover_bob(0.035, 1.3)
P.dust(sif, 0.3, T_S_STOP, every=0.12, size=0.55, color=(0.36, 0.22, 0.13))
sm = sif.model_root
sm.rotation_mode = 'XYZ'
# brake, then rear the jaws up at the Prospector (standoff), then slam down onto the outcrop
for t, pitch in [(2.2, 0.0), (T_S_STOP, 4.0), (2.68, -7.0), (T_DIG - 0.1, -6.0), (T_DIG + 0.05, 5.0),
                 (T_DIG + 0.25, 3.0), (T_END, 3.0)]:
    sm.rotation_euler.y = math.radians(pitch)
    sm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))

sif.spin('GrinderPivot', 200, 0.0, 2.6, axis=0)
sif.spin('GrinderPivot', 900, 2.6, T_DIG, axis=0)
sif.spin('GrinderPivot', 1100, T_DIG, T_END, axis=0)

plight('BiteLight', Vector((2.0, 0, 0.55)), [(0, 12), (T_DIG, 12), (T_DIG + 0.15, 80), (6.2, 80)], EMBER,
       radius=0.3, parent=sm)


def hover_at(t):
    if t < 2.25:
        return H_MOVE
    if t < T_S_STOP:
        return H_MOVE + (H_MINE - H_MOVE) * ss((t - 2.25) / (T_S_STOP - 2.25))
    if t < T_DIG + 0.1:
        return H_MINE + (H_REAR - H_MINE) * ss((t - T_S_STOP) / 0.2)
    return H_MINE


# lifters: short, dense gold crackle from three pads straight down to the ground
bolt_mat = mat('Lifter', DEEP_GOLD, 2.2)
halo_mat = mat('LifterHalo', DEEP_GOLD, 0.8, alpha=0.2)
EMIT = [(0.45, 0.0), (-1.2, 0.6), (-1.2, -0.6)]


def jag(p0, p1, segs, amp):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            q += Vector((R.uniform(-amp, amp), R.uniform(-amp, amp), 0)) * math.sin(math.pi * u)
        pts.append(q)
    return pts


for f in range(1, NF + 2):
    t = (f - 1) / FPS
    h = hover_at(t)
    for ex, ey in EMIT:
        for k in range(6):
            if R.random() < 0.25:
                continue
            p0 = Vector((ex + R.uniform(-.1, .1), ey + R.uniform(-.08, .08), 0.05))
            a = R.uniform(0, 2 * math.pi)
            r = R.uniform(0.2, 0.5)
            p1 = Vector((p0.x + r * math.cos(a), p0.y + r * math.sin(a), -h + 0.02))
            pts = jag(p0, p1, 3, 0.07)
            for o in (K.polyline('Lift', pts, 0.008, bolt_mat), K.polyline('LiftHalo', pts, 0.03, halo_mat)):
                o.parent = sm
                o.visible_shadow = False
                K.show_between(o, f, f + 1)
for ex, ey in EMIT:
    plight('LiftLight', Vector((ex, ey, -0.15)), [(0, 35)], GOLD, radius=0.4, parent=sm)

# crop heap on its back, climbing with the stream, glow pulsing on each surge
CROP = Vector((-1.25, 0.0, 1.0))
heap_mat = K.pbr_mat('Or_Heap', (1.0, 0.45, 0.2), rough=0.45, emit=(1.0, 0.36, 0.06), emit_strength=0.3)
pink_heap = K.pbr_mat('Or_HeapPink', ORE_PINK, rough=0.35, emit=ORE_PINK, emit_strength=0.35)
SURGES = [3.3, 3.85, 4.4, 4.95, 5.5]
N_CHUNK = 24
for i in range(N_CHUNK):
    u = i / (N_CHUNK - 1)
    t_in = T_DIG + 0.5 + (5.7 - T_DIG - 0.5) * u
    rad = 0.75 * (1 - 0.55 * u) * math.sqrt(R.random())
    a = R.uniform(0, 2 * math.pi)
    p = CROP + Vector((rad * math.cos(a), rad * math.sin(a), 0.32 * u + R.uniform(-0.04, 0.04)))
    c = K.ico('Chunk', R.uniform(0.13, 0.22) * (1.1 - 0.3 * u), pink_heap if i % 3 == 0 else heap_mat, sub=1)
    c.parent = sm
    c.location = p
    c.rotation_euler = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    c.scale = (0.01,) * 3
    c.keyframe_insert('scale', frame=P.T(t_in) - 1)
    c.scale = (1.15, 1.0, 0.8)
    c.keyframe_insert('scale', frame=P.T(t_in + 0.12))
plight('CropLight', CROP + Vector((0, 0, 0.7)),
       [(0, 10), (T_DIG, 10)] + [x for j, s in enumerate(SURGES) for x in ((s, 40 + 18 * j), (s + 0.25, 25 + 14 * j))]
       + [(6.2, 110)], EMBER, radius=0.6, parent=sm)

mote_mat = mat('Mote', GOLD, 2.4)
mote_halo = mat('MoteHalo', DEEP_GOLD, 0.7, alpha=0.14)
BITE = Vector((2.15, 0.0, 0.55))


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


def surge_rate(t):
    return 0.6 + sum(0.9 * math.exp(-((t - s) / 0.18) ** 2) for s in SURGES)


t = T_DIG + 0.1
while t < 5.9:
    dens = surge_rate(t)
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
    o.parent = sm
    o.visible_shadow = False
    hl.visible_shadow = False
    f0 = P.T(t)
    for j in range(7):
        u = j / 6
        o.location = bez(p0, p1, p2, p3, u)
        o.keyframe_insert('location', frame=f0 + life * FPS * u)
    K.show_between(o, int(f0), int(f0 + life * FPS) + 1)
    t += 0.03 / dens

chips(BITE + Vector((0.2, 0, 0)), T_DIG + 0.05, 5.95, 0.07, 1.0, parent=sm)

for s in [T_DIG] + SURGES[::2]:
    P.puff(Vector((OUT_E[0], OUT_E[1] + R.choice((-0.9, 0.9)), GZ + 0.2)), s, size=0.35, n=1, rise=0.4, life=0.8,
           color=ORE_DUST, opacity=0.22)

# slam-down dust where the Sifter bites in
for k in range(6):
    a = 2 * math.pi * k / 6
    P.puff(Vector((OUT_E[0] + 0.9 * math.cos(a), OUT_E[1] + 1.2 * math.sin(a), GZ + 0.2)), T_DIG + 0.05, size=0.6,
           n=1, rise=0.5, life=1.0, color=(0.36, 0.22, 0.13), opacity=0.24)

# --------------------------------------------------------------------------- camera
PRE = 1 / FPS
P.camera([
    # 1: dawn orbit, low and close: the deposit alone, sun skimming the spires
    (0.0, (-5.6, -6.2, 0.7), (0.0, 0.0, 2.2), 30),
    (0.9, (-2.6, -7.8, 0.8), (0.0, 0.0, 2.2), 31),
    (CUT1 - PRE, (1.2, -8.2, 0.95), (0.0, 0.0, 2.1), 32),
    # 2: chase over the Prospector's left shoulder as it rolls in; across the crystals the Sifter
    #    skims in, brakes and rears its jaws at it (standoff), then both dig in
    (CUT1, (-16.4, -8.0, 1.6), (-7.0, 0.0, 1.6), 28),
    (2.4, (-12.6, -8.8, 1.9), (-0.6, 0.6, 1.8), 28),
    (CUT2 - PRE, (-12.0, -9.0, 2.1), (0.4, 0.7, 1.8), 28),
    # 3: beside the Prospector, a little high: drum biting, ore riding up into the hopper
    (CUT2, (-7.4, -7.6, 3.2), (-4.4, -0.8, 1.0), 31),
    (CUT3 - PRE, (-6.0, -8.0, 3.4), (-4.0, -0.8, 1.0), 31),
    # 4: rising 3/4 hero from the east-south-east: Sifter big in the foreground, deposit centre,
    #    Prospector gnawing at the far side
    (CUT3, (13.5, -3.4, 1.5), (2.8, 0.6, 1.5), 28),
    (6.0, (10.6, -6.8, 3.3), (1.3, 0.4, 1.3), 28),
], shake=0.012, cuts=(CUT1, CUT2, CUT3))
P.cam_shake(T_DIG, 0.05, 0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'gold_shimmer', gain=0.35, pos=DEP, rate=0.7)              # the crystals catch the dawn
P.sfx(T_DIG, 'grind_loop', gain=0.6, dur=6.0 - T_DIG, pos=DRUM_FACE)  # cutter drum chewing the west side
P.sfx(T_DIG, 'crunch_bed', gain=0.5, pos=OUT_E)                       # jaws slam down on the east side
P.sfx(T_DIG + 0.1, 'motes_loop', gain=0.35, dur=5.9 - T_DIG, pos=OUT_E)  # gold motes pouring into the crop
P.sfx(0.0, 'crackle_loop', gain=0.15, dur=6.0, pos=SIF_STOP)          # Sifter lifter crackle
for _i, _t in enumerate(p_lands):                                     # ore chunks dropping into the hopper
    P.sfx(_t, 'impact_dirt', gain=0.1 + 0.004 * _i, rate=1.35 + 0.04 * (_i % 5), pos=PRO_STOP)
for _s in SURGES:                                                     # each surge of ore into the crop
    P.sfx(_s, 'crystal_spike', gain=0.18, rate=1.5, pos=OUT_E)

P.render()
