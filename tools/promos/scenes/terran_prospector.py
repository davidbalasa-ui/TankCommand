"""Prospector (Terran ore miner): a quiet work story. The Prospector grinds across the desert
toward a big pink ore deposit while an empty Hauler waits off to the side. It brakes nose-first
into the seam, the cutter drum spins up, and glowing ore chunks ride up the conveyor ramp and
tumble into the hopper, faster and faster: the heap visibly climbs until it crowns over the rim
and glows. The Hauler rolls up alongside to take the load. Ore buys everything.

Timeline (s): 0-1.6 drive in (low tracking camera) | 1.6 brake + dig in, dust ring |
1.75 drum spins up | 2.0-4.9 ore chunks fly into the hopper (accelerating), heap grows |
4.3 Hauler starts rolling up | 5.0-6.0 low hero frame: brimming hopper, Hauler alongside."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import Promo  # noqa: E402

P = Promo('terran_prospector', seconds=6.0, seed=23)
R = P.rnd
SAND = (0.5, 0.38, 0.27)
ORE_PINK = (1.0, 0.28, 0.55)
ORE_DUST = (0.62, 0.36, 0.38)

STOP = Vector((1.3, 0.0, 0.0))     # prospector parks here, heading 0 (drum faces +x)
DEP = (6.9, 0.2)
HAUL0 = (-4.6, 6.8)
HAUL1 = (-0.9, 4.4)
P.env('desert', sun=(56, 0, -62), sun_energy=4.0, props=26,
      clear=[(0, 0, 10), (-10, -1, 6), (-3, 6, 6), DEP + (5,)])
P.flatten(-2, 1, 13)
P.flatten(DEP[0], DEP[1], 6)
bpy.context.view_layer.update()

dep = P.load('deposit_ore', at=DEP, heading=200, size=6.0)
dep.root.location.z = P.ground_z(*DEP) - 0.2
for (x, y), s, h in [((9.5, -5.5), 0.35, 40), ((4.5, 7.5), 0.3, 150), ((12.5, 4.0), 0.45, 260),
                     ((-8.0, -7.0), 0.28, 90)]:
    c = P.copy(dep, at=(x, y), heading=h)
    c.root.scale = (s, s, s)
    c.root.location.z = P.ground_z(x, y) - 0.1

# --------------------------------------------------------------------------- the prospector
T_STOP = 1.6
pr = P.load('prospector', at=(-12, -0.6), heading=0, label='prospector')
pr.path([(0.0, (-12.5, -0.9)), (0.6, (-7.6, -0.6)), (1.15, (-2.6, -0.15)), (1.45, (0.4, 0.0)),
         (T_STOP, (STOP.x, STOP.y), 0.0), (6.2, (STOP.x, STOP.y), 0.0)])
m = pr.model_root
m.rotation_mode = 'XYZ'
for i in range(0, 20):
    t = i / 12
    m.location.z = 0.025 * math.sin(t * 31.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
# brake: nose dips into the seam, rocks back, then a small shudder while the drum bites
for t, pitch, z in [(1.55, 0.0, 0.0), (1.68, 3.0, -0.03), (1.85, -1.0, -0.04), (2.05, 0.6, 0.0),
                    (2.25, 0.0, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.location.z = z
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    m.keyframe_insert('location', index=2, frame=P.T(t))
t = 2.3
while t < 6.1:
    m.location.z = 0.012 * math.sin(t * 47.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
    t += 1 / 12
P.dust(pr, 0.0, T_STOP, every=0.08, size=0.9, color=SAND)


def dust_ring(center, t, r, n=14, size=0.8, life=1.2, opacity=0.24, rise=0.5, color=SAND):
    c = Vector(center)
    for i in range(n):
        a = 2 * math.pi * i / n + R.uniform(-0.1, 0.1)
        p = c + Vector((math.cos(a) * r * 1.3, math.sin(a) * r * 0.8, 0.2))
        P.puff(p, t + R.uniform(0, 0.05), size=size, n=1, rise=rise, life=life, color=color, opacity=opacity)


dust_ring(STOP, 1.62, 2.6)

# drum: spins up from 1.75 to full speed by 2.3 (front face moves up, scooping)
T_DRUM = 1.75
drum = pr.parts['DrumPivot']
drum.rotation_mode = 'XYZ'
FULL = -720.0    # deg/s
ang = 0.0
t = 0.0
prev = 0.0
while t <= 6.25:
    if t > T_DRUM:
        u = min(1.0, (t - T_DRUM) / 0.55)
        rate = FULL * u * u * (3 - 2 * u)
        ang += rate * (t - prev)
    drum.rotation_euler.y = math.radians(ang)
    drum.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    prev = t
    t += 1 / 24
K.set_interp(drum, 'LINEAR')

# parked frame: prospector-local -> world
PM = Matrix.Translation(STOP)


def W(x, y, z):
    return PM @ Vector((x, y, z))


DRUM_FACE = W(2.45, 0.0, 0.55)
RAMP_LOW = W(1.55, 0.0, 0.95)
RAMP_TOP = W(0.05, 0.0, 1.85)

# chips and ore dust at the cutting face
t = 2.0
while t < 5.9:
    P.puff(DRUM_FACE + Vector((0.25, R.uniform(-0.7, 0.7), R.uniform(-0.2, 0.2))), t, size=0.4, n=1,
           rise=0.7, life=0.8, color=ORE_DUST, opacity=0.2)
    t += 0.16

# --------------------------------------------------------------------------- ore chunks + heap
M_ORE = K.pbr_mat('OreChunk', (0.62, 0.1, 0.3), rough=0.3, emit=ORE_PINK, emit_strength=0.35)
M_ORE_HOT = K.pbr_mat('OreChunkHot', (0.7, 0.12, 0.34), rough=0.25, emit=ORE_PINK, emit_strength=0.8)

# heap slots inside the bin: floor z 0.81, inner x -2.15..-0.05, y -0.82..0.82. Fill bottom-up,
# the last layers crown over the rim (~1.5) toward the middle.
slots = []
layers = [(0.95, 1.0, 12), (1.18, 0.88, 10), (1.42, 0.7, 8), (1.66, 0.48, 5), (1.86, 0.25, 2)]
for z, spread, n in layers:
    for i in range(n):
        a = i / n * 2 * math.pi + R.uniform(0, 0.5)
        r = spread * math.sqrt(R.uniform(0.15, 1.0))
        x = -1.1 + math.cos(a) * r * 0.95
        y = math.sin(a) * r * 0.75
        slots.append(W(x, y, z + R.uniform(-0.05, 0.05)))

N = len(slots)
# landing times accelerate: first chunk lands at 2.35, last at ~4.95
T0, T1 = 2.0, 4.6
times = []
for k in range(N):
    u = k / (N - 1)
    times.append(T0 + (T1 - T0) * (u ** 0.8))
FLY = 0.42
lands = []
for k, (slot, t0) in enumerate(zip(slots, times)):
    s = R.uniform(0.12, 0.17)
    rot0 = (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    # flying chunk: drum face -> up the ramp -> over the lip -> drop onto its slot
    f = K.ico('OreFly', 1.0, M_ORE_HOT, sub=0)
    f.scale = (s, s * 0.8, s * 1.5)
    start = DRUM_FACE + Vector((0.0, R.uniform(-0.5, 0.5), 0.0))
    over = RAMP_TOP + Vector((0, slot.y * 0.4, 0.25))
    pts = [(0.0, start), (0.1, RAMP_LOW + Vector((0, start.y * 0.5, 0.1))), (0.24, over)]
    for i in range(1, 4):
        u = i / 3
        p = over.lerp(slot + Vector((0, 0, 0.05)), u) + Vector((0, 0, 0.45 * u * (1 - u)))
        pts.append((0.24 + (FLY - 0.24) * u, p))
    for i, (dt, p) in enumerate(pts):
        f.location = p
        f.rotation_euler = (rot0[0] + dt * 9, rot0[1] + dt * 7, rot0[2])
        f.keyframe_insert('location', frame=P.T(t0 + dt))
        f.keyframe_insert('rotation_euler', frame=P.T(t0 + dt))
    K.set_interp(f, 'LINEAR')
    K.show_between(f, P.T(t0), P.T(t0 + FLY))
    # resting chunk in the heap
    o = K.ico('OreRest', 1.0, M_ORE, sub=0)
    o.location = slot
    o.rotation_euler = (rot0[0] + FLY * 9, rot0[1] + FLY * 7, rot0[2])
    o.scale = (s, s * 0.8, s * 1.5)
    K.show_between(o, P.T(t0 + FLY), P.T(6.3))
    lands.append(t0 + FLY)

# hopper glow grows with the load
hop_l = bpy.data.objects.new('HopperGlow', bpy.data.lights.new('HopperGlow', 'POINT'))
K.link(hop_l)
hop_l.location = W(-1.1, 0.0, 2.3)
hop_l.data.color = ORE_PINK
hop_l.data.shadow_soft_size = 0.8
for t, e in [(0, 0), (lands[0], 0), (3.4, 25), (4.4, 55), (lands[-1], 90), (lands[-1] + 0.15, 120), (6.2, 100)]:
    hop_l.data.energy = e
    hop_l.data.keyframe_insert('energy', frame=P.T(t))
drum_l = bpy.data.objects.new('DrumGlow', bpy.data.lights.new('DrumGlow', 'POINT'))
K.link(drum_l)
drum_l.location = DRUM_FACE + Vector((0.5, 0, 0.4))
drum_l.data.color = ORE_PINK
for t, e in [(0, 0), (2.0, 0), (2.3, 25), (6.2, 25)]:
    drum_l.data.energy = e
    drum_l.data.keyframe_insert('energy', frame=P.T(t))

# --------------------------------------------------------------------------- the hauler
hl = P.load('hauler', at=HAUL0, heading=-35, label='hauler')
T_H0, T_H1 = 3.9, 5.2
hl.path([(0.0, HAUL0, -35), (T_H0, HAUL0, -35), (4.45, (-3.0, 5.5)), (T_H1, HAUL1, 0.0), (6.2, HAUL1, 0.0)])
hm = hl.model_root
hm.rotation_mode = 'XYZ'
for t, pitch in [(T_H0, 0.0), (T_H0 + 0.15, -1.5), (T_H0 + 0.4, 0.0), (T_H1 - 0.1, 0.0), (T_H1 + 0.05, 2.0),
                 (T_H1 + 0.25, -0.6), (T_H1 + 0.45, 0.0)]:
    hm.rotation_euler.y = math.radians(pitch)
    hm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
P.dust(hl, T_H0 + 0.1, T_H1, every=0.1, size=0.8, color=SAND)
crane = hl.parts.get('CranePivot')
if crane:
    crane.rotation_mode = 'XYZ'
    for t, a in [(0.0, 0), (5.1, 0), (5.8, -40), (6.2, -42)]:
        crane.rotation_euler.z = math.radians(a)
        crane.keyframe_insert('rotation_euler', index=2, frame=P.T(t))

# --------------------------------------------------------------------------- camera
P.camera([
    (0.0, (-6.6, -3.4, 0.55), (-10.6, -0.7, 0.75), 30),
    (0.8, (-1.4, -4.8, 0.7), pr.pos_at(0.8) + Vector((0.6, 0, 0.8)), 28),
    (1.6, (0.4, -9.4, 1.6), (2.6, 0.0, 1.0), 27),
    (2.7, (3.6, -6.9, 2.5), (2.6, 0.0, 1.05), 28),
    (3.9, (1.4, -6.8, 6.6), (1.0, 0.3, 0.9), 27),
    (5.0, (-3.6, -6.8, 3.8), (0.8, 1.0, 1.1), 27),
    (6.0, (-3.2, -5.9, 2.9), (1.1, 1.3, 1.1), 28),
], shake=0.012)
P.cam_shake(1.65, 0.06, 0.3)

P.render()
