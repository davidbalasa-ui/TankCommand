"""Disc (Arcadian heavy saucer gunship): a Terran mining crew is working an ore seam at dusk.
Three Discs slide in overhead, low and slow, on crackling gold-lightning lifters. Their
under-pods charge and pulse four times: the fleeing Hauler is cut off, the Prospector dies on
its seam, the Hauler dies, and the last pulse cracks the ore seam itself. The saucers never
stop drifting. Ominous, slow and total."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, sphere, key_strength, link  # noqa: E402

P = Promo('arcadian_disc', seconds=6.0, seed=7)
P.env('dusk', sun=(74, 0, 140), sun_energy=3.6, clear=[(-4, 2, 18)], props=30)
P.flatten(-4, 2, 16)

GOLD = COL['arc_gold']
WHITE = COL['arc_white']
DEEP_GOLD = (1.0, 0.5, 0.06)   # rich gold; keep emission strength ~1.5 so channels don't clip to yellow

# ------------------------------------------------------------------ the mining site
deposit = P.load('deposit_ore', at=(0.5, -0.5), heading=35, size=6.5)
deposit.root.location.z = -0.25

# Prospector chewing into the seam (drum faces +X), Hauler parked alongside, crane working.
pros = P.load('prospector', at=(-4.6, -0.6), heading=4, label='prospector')
pros.spin('DrumPivot', -340, 0.0, 2.9, axis=1)
haul = P.load('hauler', at=(-6.0, 4.6), heading=-25, label='hauler')
crane = haul.parts.get('CranePivot')
if crane:
    crane.rotation_mode = 'XYZ'
    for t, a in [(0.0, 0), (0.7, 28), (1.3, 0), (1.6, -35)]:
        crane.rotation_euler.z = math.radians(a)
        crane.keyframe_insert('rotation_euler', index=2, frame=P.T(t))

# The Hauler sees them and bolts (reverses out, swings away); pulse 1 cuts it off, it
# swerves, and pulse 3 finds it.
haul.path([(0.0, (-6.0, 4.6), -25), (1.55, (-6.0, 4.6), -25), (1.95, (-7.3, 5.3), 150),
           (2.45, (-10.3, 6.6), 155), (2.62, (-10.8, 6.6), 190), (2.95, (-11.4, 4.9), 245),
           (3.2, (-11.7, 3.6), 255)], face=True)
P.dust(haul, 1.6, 3.2, every=0.08, size=1.1)
# skid spray where it brakes hard in front of pulse 1
P.puff((-11.2, 6.9, 0.3), 2.58, size=1.6, n=3, rise=0.8, life=1.0,
       color=tuple(min(1, c * 1.6) for c in P.palette['g1']), opacity=0.55)

# Ore chips spraying off the drum while it works
ORE = (0.75, 0.36, 0.14)
drum_tip = Vector((-1.9, -0.4, 0.5))
t = 0.0
while t < 2.85:
    P.puff(drum_tip + Vector((P.rnd.uniform(-.3, .3), P.rnd.uniform(-.6, .6), 0)), t, size=0.8, n=1,
           rise=0.9, life=0.8, color=ORE, opacity=0.85)
    t += 0.14

# ------------------------------------------------------------------ the saucers
# They come from behind the opening camera, high and slow, and never stop drifting.
discs = []
plans = [
    # lead disc: right over the miners
    [(0.0, (-24, -22, 13.0)), (1.4, (-9.5, -5.5, 10.6)), (2.3, (-4.0, 0.5, 9.5)), (6.0, (5.0, 6.0, 9.2))],
    # left wing (fires pulse 1 and 3 at the Hauler)
    [(0.0, (-32, -15, 14.5)), (1.4, (-17.5, 1.0, 12.0)), (2.3, (-11.5, 6.0, 11.0)), (6.0, (-3.0, 12.5, 10.8))],
    # right wing, higher, trailing (fires pulse 4)
    [(0.0, (-20, -30, 15.5)), (1.4, (-5.0, -14.0, 13.0)), (2.3, (2.5, -7.0, 12.0)), (6.0, (11.0, -1.0, 11.5))],
]
src = P.load('disc', at=plans[0][0][1][:2], z=plans[0][0][1][2], label='disc0')
discs.append(src)
for i in (1, 2):
    discs.append(P.copy(src, at=plans[i][0][1][:2], z=plans[i][0][1][2], label=f'disc{i}'))
for i, d in enumerate(discs):
    d.path(plans[i], face=False)
    d.root.rotation_euler.z = math.radians(40 + 25 * i)
    d.root.keyframe_insert('rotation_euler', index=2, frame=1)
    d.root.rotation_euler.z = math.radians(55 + 25 * i)
    d.root.keyframe_insert('rotation_euler', index=2, frame=P.T(6))
    d.hover_bob(0.18, 0.45 + 0.07 * i)
    bp = d.parts.get('BladesPivot') or next((o for o in d.root.children_recursive if o.name.startswith('BladesPivot')), None)
    if bp is not None:
        d.parts['BladesPivot'] = bp
    d.spin('BladesPivot', 200 + 30 * i, 0.0, 6.0, axis=2)


# ---- gold lightning lifters: short crackling arcs under the hull, re-drawn every 2 frames
bolt_mat = emit_mat('LifterBolt', DEEP_GOLD, 1.5)
core_mat = emit_mat('LifterCore', WHITE, 10)
glow_mat = emit_mat('LifterGlow', DEEP_GOLD, 0.8, alpha=0.3)


def lifters(d, step=2, n=2):
    rnd = P.rnd
    for f in range(1, P.nf + 1, step):
        for k in range(n):
            if rnd.random() < 0.35:
                continue  # flicker
            a = rnd.uniform(0, 2 * math.pi)
            r0 = rnd.uniform(1.2, 2.0)
            p0 = Vector((r0 * math.cos(a), r0 * math.sin(a), 0.25))
            b = a + rnd.uniform(-0.9, 0.9)
            r1 = r0 * rnd.uniform(0.55, 0.85)
            b = a + rnd.uniform(-0.4, 0.4)
            p1 = Vector((r1 * math.cos(b), r1 * math.sin(b), rnd.uniform(-0.55, -0.2)))
            pts = []
            for s in range(5):
                u = s / 4
                q = p0.lerp(p1, u)
                if 0 < s < 4:
                    q += Vector((rnd.uniform(-.18, .18), rnd.uniform(-.18, .18), rnd.uniform(-.08, .08)))
                pts.append(q)
            o = polyline('Lifter', pts, 0.04, bolt_mat)
            o.parent = d.model_root
            show_between(o, f, f + step)
            g = polyline('LifterHalo', pts, 0.14, glow_mat)
            g.parent = d.model_root
            show_between(g, f, f + step)
    # soft gold under-glow + a light that tints the ground below
    L = link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
    L.parent = d.model_root
    L.location = (0, 0, -2.5)
    L.data.color = GOLD
    L.data.energy = 900
    L.data.shadow_soft_size = 1.5


for d in discs:
    lifters(d)


# ---- the under-beam pulse
ring_mat = emit_mat('PulseRing', DEEP_GOLD, 1.4, alpha=0.8)


def gold_beam(p0, p1, t0, t1, col, width, strength, alpha=None):
    """Beam like P.beam but with controllable emission (the kit's 30 clips gold to white)."""
    d = p1 - p0
    o = sphere('UBeam', 1.0, emit_mat('UBeamM', col, strength, alpha=alpha), seg=(14, 8))
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('X', 'Z')
    o.location = (p0 + p1) / 2
    f0, f1 = P.T(t0), P.T(t1)
    o.scale = (d.length / 2, 0.02, 0.02)
    o.keyframe_insert('scale', frame=f0 - 1)
    for f in range(int(f0), int(f1) + 1):
        w = width * P.rnd.uniform(0.8, 1.15) * (1.4 if f - f0 < 2 else 1.0)
        o.scale = (d.length / 2, w, w)
        o.keyframe_insert('scale', frame=f)
    o.scale = (d.length / 2, 0.01, 0.01)
    o.keyframe_insert('scale', frame=f1 + 2)
    show_between(o, f0, f1 + 2)


def pod(d, t):
    """World position of the under-pod (centre bottom) at time t."""
    return d.world_at(d.model_root, t, (0, 0, -0.05))


def pulse(d, t, target, size=1.0):
    """Charge (0.3 s), then one fat gold beam straight down onto `target` with lightning
    wrapping it, a ground shock ring, a hull kick upward. Returns the hit time."""
    p_hit = target.pos_at(t) + Vector((0, 0, 0.6)) if hasattr(target, 'pos_at') else Vector(target)
    # charge: gathering gold sphere under the pod
    cm = emit_mat('Charge', DEEP_GOLD, 1.6)
    c = sphere('Charge', 1.0, cm, seg=(12, 8))
    c.parent = d.model_root
    c.location = (0, 0, -0.35)
    f0, f1 = P.T(t - 0.32), P.T(t)
    c.scale = (0.05,) * 3
    c.keyframe_insert('scale', frame=f0)
    c.scale = (0.5 * size,) * 3
    c.keyframe_insert('scale', frame=f1)
    c.scale = (0.2,) * 3
    c.keyframe_insert('scale', frame=f1 + 4)
    show_between(c, f0, f1 + 4)
    # converging arcs during the charge
    for k in range(3):
        a = k * 2.1
        tt = t - 0.28 + k * 0.08
        p0 = pod(d, tt)
        P.lightning(p0 + Vector((2.2 * math.cos(a), 2.2 * math.sin(a), 0.3)), p0 + Vector((0, 0, -0.35)),
                    tt, tt + 0.08, width=0.03, branches=0, segs=6, glow=False)
    p0 = pod(d, t)
    # the beam: white core + gold sheath + crackle
    gold_beam(p0, p_hit, t, t + 0.3, WHITE, 0.12 * size, 3)
    gold_beam(p0, p_hit, t, t + 0.36, (1.0, 0.42, 0.03), 0.42 * size, 1.25)
    P.light(p_hit + Vector((0, 0, 1.5)), t, GOLD, energy=6000 * size, dur=0.35, radius=1.0)
    P.lightning(p0, p_hit, t, t + 0.3, color=DEEP_GOLD, width=0.05, jag=0.25, branches=3)
    # ground ring blast
    gz = P.ground_z(p_hit.x, p_hit.y) + 0.15
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.08, location=(p_hit.x, p_hit.y, gz))
    ring = bpy.context.active_object
    ring.data.materials.append(ring_mat)
    fr = P.T(t + 0.02)
    ring.scale = (0.3, 0.3, 1)
    ring.keyframe_insert('scale', frame=fr)
    ring.scale = (6.0 * size, 6.0 * size, 2.5)
    ring.keyframe_insert('scale', frame=fr + 9)
    show_between(ring, fr, fr + 9)
    P.impact(p_hit, t + 0.03, size=0.8 * size, color=DEEP_GOLD)
    # hull kicks up and tilts away from the shot, then settles
    m = d.model_root
    m.rotation_mode = 'XYZ'
    f = P.T(t)
    m.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    m.rotation_euler.x = math.radians(5)
    m.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    m.rotation_euler.x = 0
    m.keyframe_insert('rotation_euler', index=0, frame=f + 14)
    P.cam_shake(t + 0.03, 0.12 * size, 0.35) if P.cam else None
    return t + 0.04


# ------------------------------------------------------------------ camera (built before the
# pulses so they can add shake)
P.camera([
    (0.0, (-10.5, -7.5, 1.0), (-3.0, -0.2, 1.0), 34),
    (1.0, (-11.5, -8.0, 1.2), (-3.5, 0.0, 2.0), 32),
    (1.3, (-12.2, -8.6, 1.25), (-4.2, -0.4, 3.6), 30),
    (1.55, (-12.8, -9.0, 1.3), discs[0], 27),
    (1.8, (-13.6, -9.6, 1.4), (-6.5, -1.0, 8.5), 26),
    (2.3, (-16.0, -11.5, 2.0), (-4.5, 1.0, 7.2), 24),
    (3.7, (-17.0, -14.5, 3.0), (-5.0, 2.5, 5.0), 26),
    (4.9, (-3.0, -14.0, 2.0), (-1.0, 3.0, 6.5), 24),
    (6.0, (5.5, -7.0, 2.4), (0.0, 3.5, 5.0), 22),
], shake=0.03)

# Lighter, thinner smoke: the default dark puffs pile into black blobs over the ending.
_kit_puff = P.puff


def _thin_puff(pos, t, size=0.6, n=3, rise=1.0, life=1.2, color=None, opacity=0.65):
    if color is None:
        color, size, opacity = (0.2, 0.185, 0.17), size * 0.75, opacity * 0.8
    return _kit_puff(pos, t, size=size, n=n, rise=rise, life=life, color=color, opacity=opacity)


P.puff = _thin_puff

# ------------------------------------------------------------------ four pulses
th = pulse(discs[1], 2.5, (-13.6, 8.0, 0.2), size=0.85)          # cut the Hauler off
th = pulse(discs[0], 2.85, pros, size=1.0)                         # the Prospector
pros.destroy(th, size=2.6)
th = pulse(discs[1], 3.2, haul, size=0.95)                         # the Hauler
haul.destroy(th, size=2.4)
th = pulse(discs[2], 3.6, (0.8, -0.2, 0.8), size=1.25)           # crack the seam itself
P.explosion((0.8, -0.2, 1.0), th + 0.05, size=4.2, debris=18, smoke=False)
P.smoke_column((0.8, -0.2, 0.5), th + 0.4, 6.0, size=0.9, every=0.45)
P.fire_patch((0.8, -0.2, 0.8), th + 0.1, 6.0, size=0.55)
P.cam_shake(th + 0.05, 0.25, 0.6)

# Wreck flames: keep them saturated orange (bright emission goes cream under AgX).
for m in bpy.data.materials:
    if m.name.startswith('WreckFlame'):
        em = m.node_tree.nodes[m['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.18, 0.01, 1)
        em.inputs['Strength'].default_value = 1.6

# Explosion cores (pale, strength 20) still flash white on these hits: deepen to fire.
for m in bpy.data.materials:
    if m.name.startswith('Core'):
        em = m.node_tree.nodes[m['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.35, 0.05, 1)
        em.inputs['Strength'].default_value = 6.0

P.render()
