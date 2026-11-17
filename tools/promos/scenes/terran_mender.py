"""Mender (Terran repair): field repair in the middle of a fight.

A battered Bulwark limps out of the fight at dusk, listing, scorched, smoking, its lights
stuttering. A Mender overtakes it and brakes alongside; its crane arm swings over the gap and a
blue-green repair beam walks across the damage: the charred patches and their glowing seams
close up, the fire goes out, the smoke thins away, the hull levels off and the lights come back
steady. The arm folds away, the Bulwark swings its gun back toward the distant battle and fires:
back in the fight. Distant flashes and tracers on the horizon throughout.

Timeline (s): 0-1.5 Bulwark limps in (low tracking camera) | 0.6-2.1 Mender overtakes, brakes |
2.1-2.75 arm swings over (cut to the front of the gap at 2.5) | 2.75-4.9 beam walks over four
damage points, scars close, smoke thins, hull levels | 4.9 lights pulse back | 5.0 cut: low hero
frame on the Mender | 5.1-5.6 arm folds, Bulwark turret swings to the fight | 5.6 heavy shot.

Models by name only (mender, bulwark): remodels just need a re-render. Glows are tinted to
Terran neon blue + orange in this scene only (model files untouched)."""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_mender', seconds=6.0, seed=7)
R = P.rnd
FPS = P.fps
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
TEAL = (0.12, 1.0, 0.72)          # repair beam: blue-green

P.env('dusk', sun=(74, 0, -75), sun_energy=4.2, props=30,
      clear=[(-6, 2.5, 14), (6, 0, 8), (-15, 15, 10), (-26, 26, 12)])
P.flatten(-4, 2.4, 14)
bpy.context.view_layer.update()

BUL_PARK = Vector((0.0, 4.7, 0.0))
MEN_PARK = Vector((0.0, 0.0, 0.0))
T_BUL_PARK = 1.5
T_MEN_PARK = 2.1


# ------------------------------------------------------------------------------- glow tint
def terran_glow(actor, strength=2.2, damage=None):
    """Scene-only: route the emissive texture through a tint (cool -> neon blue, warm ->
    Terran orange) at a safe strength. damage=dict(...) also adds charred patches with hot
    orange seams whose threshold is keyed (see bulwark below). Returns {material: info}."""
    out = {}
    for o in actor.meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m in out or not m.node_tree:
                continue
            nt = m.node_tree
            bs = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bs is None:
                continue
            ec = bs.inputs['Emission Color']
            if not ec.is_linked and bs.inputs['Emission Strength'].default_value <= 0:
                out[m] = None
                continue
            info = {'bsdf': bs}
            if ec.is_linked:
                src = ec.links[0].from_socket
                sep = nt.nodes.new('ShaderNodeSeparateColor')
                nt.links.new(src, sep.inputs[0])
                diff = nt.nodes.new('ShaderNodeMath')
                diff.operation = 'SUBTRACT'
                nt.links.new(sep.outputs[0], diff.inputs[0])
                nt.links.new(sep.outputs[2], diff.inputs[1])
                warm = nt.nodes.new('ShaderNodeMapRange')
                warm.inputs['From Min'].default_value = 0.1
                warm.inputs['From Max'].default_value = 0.4
                nt.links.new(diff.outputs[0], warm.inputs['Value'])
                mx1 = nt.nodes.new('ShaderNodeMath')
                mx1.operation = 'MAXIMUM'
                nt.links.new(sep.outputs[0], mx1.inputs[0])
                nt.links.new(sep.outputs[1], mx1.inputs[1])
                mx2 = nt.nodes.new('ShaderNodeMath')
                mx2.operation = 'MAXIMUM'
                nt.links.new(mx1.outputs[0], mx2.inputs[0])
                nt.links.new(sep.outputs[2], mx2.inputs[1])
                hue = nt.nodes.new('ShaderNodeMix')
                hue.data_type = 'RGBA'
                hue.inputs['A'].default_value = (*NEON, 1)
                hue.inputs['B'].default_value = (*ORANGE, 1)
                nt.links.new(warm.outputs['Result'], hue.inputs['Factor'])
                val = nt.nodes.new('ShaderNodeVectorMath')
                val.operation = 'SCALE'
                nt.links.new(hue.outputs['Result'], val.inputs[0])
                nt.links.new(mx2.outputs[0], val.inputs['Scale'])
                tinted = val.outputs[0]
            else:
                tinted = None
                ec.default_value = (*NEON, 1)
            bs.inputs['Emission Strength'].default_value = strength
            if damage and tinted is not None:
                # charred patches: noise in object space, threshold keyed by a Value node
                tc = nt.nodes.new('ShaderNodeTexCoord')
                nz = nt.nodes.new('ShaderNodeTexNoise')
                nz.inputs['Scale'].default_value = damage['scale']
                nz.inputs['Detail'].default_value = 3
                nz.inputs['Roughness'].default_value = 0.6
                nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
                thr = nt.nodes.new('ShaderNodeValue')
                thr.outputs[0].default_value = damage['thr0']
                info['thr'] = thr

                def band(lo_off, hi_off):
                    mr = nt.nodes.new('ShaderNodeMapRange')
                    a = nt.nodes.new('ShaderNodeMath')
                    a.operation = 'ADD'
                    a.inputs[1].default_value = lo_off
                    nt.links.new(thr.outputs[0], a.inputs[0])
                    b = nt.nodes.new('ShaderNodeMath')
                    b.operation = 'ADD'
                    b.inputs[1].default_value = hi_off
                    nt.links.new(thr.outputs[0], b.inputs[0])
                    nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
                    nt.links.new(a.outputs[0], mr.inputs['From Min'])
                    nt.links.new(b.outputs[0], mr.inputs['From Max'])
                    return mr.outputs['Result']
                char = band(0.0, 0.025)           # 1 inside the burn
                rim = band(-0.035, 0.0)           # 1 from just outside the burn edge
                seam = nt.nodes.new('ShaderNodeMath')
                seam.operation = 'SUBTRACT'
                nt.links.new(rim, seam.inputs[0])
                nt.links.new(char, seam.inputs[1])
                # base colour -> soot
                bc = bs.inputs['Base Color']
                if bc.is_linked:
                    bsrc = bc.links[0].from_socket
                    mixb = nt.nodes.new('ShaderNodeMix')
                    mixb.data_type = 'RGBA'
                    mixb.inputs['B'].default_value = (0.02, 0.018, 0.016, 1)
                    nt.links.new(bsrc, mixb.inputs['A'])
                    nt.links.new(char, mixb.inputs['Factor'])
                    nt.links.new(mixb.outputs['Result'], bc)
                # emission: lights dead inside the burn, hot orange seam around it
                dead = nt.nodes.new('ShaderNodeMix')
                dead.data_type = 'RGBA'
                dead.inputs['B'].default_value = (0, 0, 0, 1)
                nt.links.new(tinted, dead.inputs['A'])
                nt.links.new(char, dead.inputs['Factor'])
                hot = nt.nodes.new('ShaderNodeMix')
                hot.data_type = 'RGBA'
                hot.inputs['B'].default_value = (0.75, 0.2, 0.03, 1)
                nt.links.new(dead.outputs['Result'], hot.inputs['A'])
                nt.links.new(seam.outputs[0], hot.inputs['Factor'])
                tinted = hot.outputs['Result']
            if tinted is not None:
                nt.links.new(tinted, ec)
            out[m] = info
    return out


def key_emit(infos, keys):
    for info in infos.values():
        if not info:
            continue
        s = info['bsdf'].inputs['Emission Strength']
        for t, v in keys:
            s.default_value = v
            s.keyframe_insert('default_value', frame=P.T(t))


# ------------------------------------------------------------------------------- cast
bul = P.load('bulwark', at=(-15, 4.9), heading=0, label='bulwark')
men = P.load('mender', at=(-17, 0.2), heading=0, label='mender')


BUL_GLOW = terran_glow(bul, 2.0, damage=dict(scale=0.9, thr0=0.6))
MEN_GLOW = terran_glow(men, 2.2)

# Bulwark limps in: uneven, lurching speed, listing to one side
bul.path([(0.0, (-8.6, 5.0)), (0.35, (-6.9, 4.9)), (0.55, (-6.3, 4.85)), (0.9, (-4.2, 4.78)),
          (1.1, (-3.1, 4.74)), (1.3, (-1.2, 4.7)), (T_BUL_PARK, (BUL_PARK.x, BUL_PARK.y), 0.0),
          (6.5, (BUL_PARK.x, BUL_PARK.y), 0.0)])
bm = bul.model_root
bm.rotation_mode = 'XYZ'
LIST = 3.2      # degrees of list from the wrecked suspension (toward the camera side)
for t, pitch, roll in [(0.0, 0.0, -LIST), (0.3, 1.8, -LIST - 1.5), (0.45, -1.2, -LIST), (0.6, 0.6, -LIST),
                       (0.95, 1.6, -LIST - 1.2), (1.1, -0.8, -LIST + 0.4), (1.35, 0.4, -LIST),
                       (T_BUL_PARK, -1.6, -LIST - 0.6), (T_BUL_PARK + 0.25, 0.6, -LIST), (T_BUL_PARK + 0.5, 0.0, -LIST),
                       (3.2, 0.0, -LIST), (4.5, 0.0, 0.0), (6.0, 0.0, 0.0)]:
    bm.rotation_euler = (math.radians(roll), math.radians(pitch), 0)
    bm.keyframe_insert('rotation_euler', index=0, frame=P.T(t))
    bm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
bm.rotation_euler = (0, 0, 0)
P.dust(bul, 0.0, T_BUL_PARK - 0.1, every=0.14, size=0.6)

# Mender: overtakes on the near side and brakes alongside
men.path([(0.0, (-21.0, 0.3)), (0.6, (-15.0, 0.25)), (1.4, (-5.2, 0.1)),
          (1.85, (-1.3, 0.0)), (T_MEN_PARK, (MEN_PARK.x, MEN_PARK.y), 0.0), (6.5, (MEN_PARK.x, MEN_PARK.y), 0.0)])
mm = men.model_root
mm.rotation_mode = 'XYZ'
for t, pitch in [(T_MEN_PARK - 0.15, 0.0), (T_MEN_PARK + 0.05, 2.4), (T_MEN_PARK + 0.3, -0.8),
                 (T_MEN_PARK + 0.55, 0.0)]:
    mm.rotation_euler.y = math.radians(pitch)
    mm.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
P.dust(men, 0.0, T_MEN_PARK, every=0.1, size=0.65)

# ------------------------------------------------------------------------------- the arm
arm = men.parts['Arm']
lv = [v.co for v in arm.data.vertices]
xmax = max(c.x for c in lv)
span = xmax - min(c.x for c in lv)
near = [c for c in lv if c.x > xmax - 0.06 * span]
tip_local = Vector((xmax, sum(c.y for c in near) / len(near), min(c.z for c in near)))
EMIT = K.empty('MenderEmitter')
EMIT.parent = arm
EMIT.location = tip_local
bpy.context.view_layer.update()
PIV = men.turret.matrix_world.translation.copy() - men.root.matrix_world.translation   # pivot rel. to root
REACH = (EMIT.matrix_world.translation - men.turret.matrix_world.translation)
REACH = math.hypot(REACH.x, REACH.y)

# damage points on the Bulwark's gap-facing side (world, parked)
DMG = [Vector((-2.0, 3.5, 0.62)), Vector((-0.9, 3.85, 1.35)), Vector((0.3, 3.5, 0.7)), Vector((-1.6, 3.95, 1.62))]


def yaw_for(x):
    c = max(-0.45, min(0.5, (x - (MEN_PARK.x + PIV.x)) / REACH))
    return math.degrees(math.acos(c))


T_SWING0, T_SWING1 = 2.1, 2.75
T_BEAM = [(2.75, 3.3), (3.3, 3.85), (3.85, 4.4), (4.4, 4.9)]
yk = [(0.0, 0.0), (T_SWING0, 0.0), (T_SWING1 - 0.1, yaw_for(DMG[0].x) + 6), (T_SWING1, yaw_for(DMG[0].x))]
for (t0, t1), p in zip(T_BEAM, DMG):
    yk.append((t0 + 0.08, yaw_for(p.x)))
    yk.append((t1 - 0.05, yaw_for(p.x) + (2 if p.x < -1 else -2)))
yk += [(5.1, yk[-1][1]), (5.65, -4.0), (5.85, 0.0), (6.2, 0.0)]
men.turret_yaw(yk)

# arm tip glow while working
tip_l = bpy.data.objects.new('TipGlow', bpy.data.lights.new('TipGlow', 'POINT'))
K.link(tip_l)
tip_l.parent = EMIT
tip_l.data.color = TEAL
tip_l.data.shadow_soft_size = 0.2
for t, e in [(0, 0), (2.5, 0), (2.75, 25), (4.9, 25), (5.1, 0)]:
    tip_l.data.energy = e
    tip_l.data.keyframe_insert('energy', frame=P.T(t))

M_MOTE = K.emit_mat('RepairMote', TEAL, 3.0)
M_EMBER = K.emit_mat('Ember', ORANGE, 3.0)


def motes(p0, p1, t0, t1, every=0.035, size=0.045, mat=M_MOTE, life=0.22):
    """Small glowing specks streaming p0 -> p1 along the beam."""
    t = t0
    while t < t1 - life * 0.5:
        o = K.sphere('Mote', 1.0, mat, seg=(6, 4))
        o.scale = (size,) * 3
        jit = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))) * 0.12
        o.location = p0 + jit
        o.keyframe_insert('location', frame=P.T(t))
        o.location = p1 + jit * 0.4
        o.keyframe_insert('location', frame=P.T(t + life))
        K.set_interp(o, 'LINEAR')
        K.show_between(o, P.T(t), P.T(t + life))
        t += every


def sparkle(p, t0, t1, every=0.05, mat=M_MOTE, size=0.04, spread=0.6, up=0.4):
    """Specks bouncing off a contact point (weld sparkle)."""
    t = t0
    while t < t1:
        o = K.sphere('Spark', 1.0, mat, seg=(6, 4))
        o.scale = (size * 1.8, size, size)
        v = Vector((R.uniform(-1, 1), R.uniform(-1.3, 0.2), R.uniform(0.2, 1.2))).normalized()
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = v.to_track_quat('X', 'Z')
        o.location = p
        o.keyframe_insert('location', frame=P.T(t))
        o.location = p + v * spread + Vector((0, 0, -up))
        o.keyframe_insert('location', frame=P.T(t + 0.25))
        K.show_between(o, P.T(t), P.T(t + 0.25))
        t += every


# the repair: the beam walks from point to point
for (t0, t1), p in zip(T_BEAM, DMG):
    a = men.world_at(EMIT, (t0 + t1) / 2)
    P.beam(a, p, t0, t1 - 0.03, TEAL, width=0.06, strength=2.6)
    motes(a, p, t0, t1)
    sparkle(p, t0 + 0.04, t1 - 0.05)

# scars close as the beam works: threshold rises (fewer, smaller burns) and lights steady
for info in BUL_GLOW.values():
    if info and 'thr' in info:
        sock = info['thr'].outputs[0]
        for t, v in [(0.0, 0.6), (2.75, 0.6), (3.3, 0.64), (3.85, 0.69), (4.4, 0.76), (4.9, 0.95), (6.0, 0.95)]:
            sock.default_value = v
            sock.keyframe_insert('default_value', frame=P.T(t))
fl = []
t = 0.0
while t < 3.5:
    fl.append((t, R.choice([0.15, 0.4, 1.4, 1.8, 0.2, 1.6])))
    t += R.choice([1, 2, 3]) / FPS
fl += [(3.9, 1.6), (4.9, 1.8), (5.0, 3.0), (5.35, 2.0), (6.0, 2.0)]
key_emit(BUL_GLOW, fl)

# smoke: black and thick while limping, thinning away during the repair
t = 0.0
while t < 4.8:
    u = max(0.0, min(1.0, (t - 2.75) / 2.0))
    op = 0.32 * (1 - u) + 0.04
    sz = 0.55 * (1 - 0.5 * u)
    shade = 0.2 + 0.25 * u
    p = bul.pos_at(t)
    for off in [(-2.3, 0.2, 1.0), (-0.9, -0.4, 1.8)]:
        if u > 0.6 and off[0] < -2:
            continue
        P.puff(p + Vector(off), t, size=sz, n=1, rise=1.3, life=1.3, color=(shade, shade * 0.95, shade * 0.9),
               opacity=op)
    t += 0.12 if t < 2.75 else 0.12 + 0.2 * u
P.fire_patch(BUL_PARK + Vector((-2.3, 0.1, 0.95)), T_BUL_PARK, 3.35, size=0.45)
# sparks spitting from the wounds while it limps
for k in range(9):
    tk = 0.2 + k * 0.33
    if tk > 2.7:
        break
    d = DMG[k % len(DMG)] - BUL_PARK + bul.pos_at(tk)
    sparkle(d, tk, tk + 0.12, every=0.03, mat=M_EMBER, size=0.035, spread=0.9, up=0.6)

# ------------------------------------------------------------------------------- back in the fight
FIGHT = Vector((-45.0, 62.0, 0.0))
bul.split_barrels(max_frac=0.6, thin=0.65) or bul.split_barrels()
bul.aim(5.55, FIGHT + Vector((0, 0, 2.0)), dur=0.5)
bul.turret.keyframe_insert('rotation_euler', index=2, frame=P.T(5.05))
bm.rotation_euler = (0, 0, 0)
bm.location.x = 0.0
bul.fire(5.6, FIGHT + Vector((0, 0, 1.0)), kind='heavy', size=1.0, impact_size=3.0)

# ------------------------------------------------------------------------------- distant battle
for t, p, s in [(0.45, (-75, 42), 2.6), (1.5, (-52, 68), 2.2), (2.6, (-90, 18), 3.0), (3.5, (-64, 58), 2.2),
                (4.3, (-84, 30), 2.6), (5.2, (-46, 72), 2.4)]:
    P.explosion((p[0], p[1], P.ground_z(*p) + 0.5), t, size=s, debris=4)
for t, a, b in [(0.2, (-90, 30, 2), (-50, 55, 1)), (0.9, (-45, 70, 2), (-80, 25, 1)),
                (1.9, (-95, 45, 2), (-55, 40, 1)), (3.0, (-40, 58, 2), (-75, 35, 1)),
                (3.9, (-88, 20, 2), (-52, 64, 1)), (4.8, (-60, 70, 2), (-90, 38, 1))]:
    for k in range(3):
        P.projectile(Vector(a) + Vector((0, k * 1.5, 0)), Vector(b), t + k * 0.12, 70, COL['tracer'],
                     size=0.1, arc=1.5)

# ------------------------------------------------------------------------------- camera
CUT1 = 2.5
CUT2 = 5.0
P.camera([
    # shot 1: low, ahead and left; pan with the limping Bulwark, the Mender overtakes past us
    (0.0, (-3.8, -1.2, 0.95), (-8.4, 4.8, 1.05), 30),
    (1.0, (0.4, -3.6, 1.2), (-4.2, 3.8, 1.1), 30),
    (1.8, (4.2, -5.0, 1.9), (-1.6, 2.6, 1.1), 29),
    (CUT1 - 1 / FPS, (5.4, -5.3, 2.4), (-1.0, 2.5, 1.3), 29),
    # shot 2: in front of the gap between them, arm arching over, beam walking; slow push in
    (CUT1, (9.5, 1.3, 2.4), (-1.0, 2.5, 1.25), 30),
    (3.8, (8.2, 1.6, 2.2), (-1.0, 2.6, 1.2), 31),
    (CUT2 - 1 / FPS, (7.0, 1.8, 2.0), (-1.0, 2.7, 1.2), 31),
    # shot 3: low hero angle on the Mender, repaired Bulwark behind swinging to the fight
    (CUT2, (8.8, -2.6, 0.9), (-0.4, 1.9, 1.75), 36),
    (6.0, (7.9, -2.2, 0.8), (-0.4, 1.95, 1.8), 37),
], shake=0.015, cuts=[CUT1, CUT2])
P.cam_shake(T_MEN_PARK, 0.04, 0.25)
P.cam_shake(5.6, 0.06, 0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(T_SWING0, 'servo', gain=0.45, rate=0.8)         # crane arm swings over the gap
P.sfx(T_SWING1 - 0.03, 'mech_clunk', gain=0.35, rate=1.1)
for _t0, _t1 in T_BEAM:                               # repair beam walks over each damage point
    P.sfx(_t0, 'tractor_loop', gain=0.35, dur=_t1 - _t0)
    P.sfx(_t0 + 0.1, 'crackle_loop', gain=0.12, dur=0.35)   # scar sizzling closed
P.sfx(4.9, 'power_up_terran', gain=0.55)              # lights pulse back on
P.sfx(5.1, 'servo', gain=0.4, rate=0.85)              # arm folds away
P.sfx(5.45, 'mech_clunk', gain=0.35, rate=1.0)

P.render()
