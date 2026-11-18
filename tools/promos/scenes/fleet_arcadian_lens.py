"""Arcadian Lens mothership (space): the Lens hangs against the sun, gathering sunlight: thin
gold shafts stream into its rings and converge on a focus point ahead of its nose, which swells.
Across the gulf a Terran Broadside raises its blue triangle shield. The Lens fires: one gold
beam lances into the shield, which dents deep under it and ripples but holds. The beam slices
sideways across the bubble, dragging the dent along the membrane, ringing it with ripples and
deflected sparks, pressing the shield almost onto the hull. The beam cuts out; the shield snaps
back with a wobble, intact (shields never shatter), the Broadside unharmed behind it.

Timeline (s): 0-2.0 behind the Lens, light shafts converging, focus swells, the Broadside's
shield powers up far off | 2.0 beam fires; 2.0-3.5 low beside the shield looking back up the
beam, dent forms | 3.5-6.0 side of the Broadside: the slice 3.0-4.9, beam off 4.95, shield
snaps back and wobbles, end on the Broadside behind its shield with the Lens beyond.

Built at ~1/3 game scale (Lens 90 m, Broadside 78 m)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as WFX  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_arcadian_lens', seconds=6.0, seed=53)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']
SHB = COL['shield_blue']

P.space(planet=(700, -2600, -900, 700, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(80, 0, 180), sun_energy=4.0)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


def V(*a):
    return Vector(a)


def key_mats(actor, matf):
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        m = matf(t)
        q = m.to_quaternion()
        if prev_q is not None:
            q.make_compatible(prev_q)
        prev_q = q
        r.location = m.translation
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.LocRotScale(m.translation, q, None)
    K.set_interp(r, 'LINEAR')
    actor.mats = mats
    return mats


def W(actor, t, local=(0, 0, 0)):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 62 / 24, 200 / 24          # 2.58 (one cut)
T_FIRE, T_OFF = 2.0, 4.95
T_SLICE0, T_SLICE1 = 3.0, 4.85

# ------------------------------------------------------------------------------- the Lens
lens = P.load('arcadian_lens', size=90.0, label='lens')
bpy.context.view_layer.update()
hull = max(lens.meshes, key=lambda o: len(o.data.polygons))
LM = lens.root.matrix_world.inverted() @ hull.matrix_world


def ll(x, y, z):
    return LM @ Vector((x, y, z))


def lens_mat(t):
    roll = math.radians(10) * t                    # the rings turn slowly
    yaw = math.radians(lerp(4, 0, ss(t / 2.0)))
    return Matrix.Translation(V(0, 0, 0)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(roll, 4, 'X')


key_mats(lens, lens_mat)

SHELL_RECOL = {
    'zone_shell': ((0.80, 0.78, 0.74), (0.52, 0.40, 0.26)),
    'zone_pale': ((0.86, 0.84, 0.80), (0.60, 0.50, 0.36)),
    'zone_bronze': ((0.58, 0.40, 0.20), (0.40, 0.26, 0.12)),
}
me = hull.data
bolt_idx = [i for i, m in enumerate(me.materials) if m and m.name.split('.')[0] == 'zone_bolt']
bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bolt_idx], context='FACES')
bm.to_mesh(me)
bm.free()
ARC = []
for m in me.materials:
    if not m or not m.node_tree:
        continue
    base = m.name.split('.')[0]
    for n in m.node_tree.nodes:
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and base in SHELL_RECOL:
            a, b = SHELL_RECOL[base]
            ia, ib = n.inputs[6], n.inputs[7]
            if not ia.is_linked and ia.default_value[0] > 0.2:
                ia.default_value = (*a, 1)
            if not ib.is_linked and ib.default_value[0] > 0.2:
                ib.default_value = (*b, 1)
        if n.type == 'BSDF_PRINCIPLED':
            n.inputs['Emission Color'].default_value = (*GOLD, 1) if base != 'zone_core' else n.inputs['Emission Color'].default_value
            if base == 'zone_glow':
                n.inputs['Emission Strength'].default_value = 2.2
            if base == 'zone_arc':
                ARC.append(n)
for n in ARC:
    sock = n.inputs['Emission Strength']
    for f in range(1, NF + 2):
        t = (f - 1) / FPS
        sock.default_value = R.choice((0.6, 1.2, 2.0)) * (1 + 0.8 * ss((t - 0.8) / 1.2) * (t < T_OFF))
        sock.keyframe_insert('default_value', frame=f)

NOSE = ll(36.5, 0, 0)
FOCUS_L = NOSE + V(10, 0, 0)
RIM = [ll(14, 22 * math.cos(a), 22 * math.sin(a)) for a in [math.radians(30 + 60 * k) for k in range(6)]]

# ------------------------------------------------------------------------------- the Broadside
BS_C = V(300, 30, -12)
bs = P.load('terran_broadside', size=78.0, label='broadside')
key_mats(bs, lambda t: Matrix.Translation(BS_C + V(0, 0.6, 0) * t) @ Matrix.Rotation(math.radians(96), 4, 'Z'))


def terran_glow(actor):
    seen = set()
    for o in actor.meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m in seen or not m.node_tree:
                continue
            seen.add(m)
            for n in m.node_tree.nodes:
                if n.type == 'EMISSION':
                    sock = n.inputs['Color']
                elif n.type == 'BSDF_PRINCIPLED':
                    sock = n.inputs['Emission Color']
                    if n.inputs['Emission Strength'].default_value <= 0:
                        continue
                else:
                    continue
                if sock.is_linked:
                    continue
                r, g, b = sock.default_value[:3]
                if r > 0.3 and b > 0.3 and g < 0.6 * min(r, b):
                    sock.default_value = (*NEON, 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:
                    sock.default_value = (*ORANGE, 1)


terran_glow(bs)

# ------------------------------------------------------------------------------- gathering light
def lw(local):
    return lambda t: W(lens, t, local)


focus = WFX.glow(P, 'LensFocus', GOLD, loc=(0, 0, 0), scale=(1, 1, 1), fx_e=0.0, fx_p=2.0, fx_hot=0.8)
for f in range(1, NF + 2):
    t = (f - 1) / FPS
    ch = ss((t - 0.3) / 1.6)
    on = 1.0 if t < T_OFF else max(0.0, 1 - (t - T_OFF) * 3)
    e = (0.2 + 1.6 * ch) * on * R.uniform(0.85, 1.0)
    WFX.kprop(focus, 'fx_e', f, e, const=True)
    s_ = (1.0 + 3.5 * ch) * (1 + 0.15 * (T_FIRE <= t < T_OFF)) * max(on, 0.05)
    focus.scale = (s_, s_, s_)
    focus.location = W(lens, t, FOCUS_L)
    focus.keyframe_insert('scale', frame=f)
    focus.keyframe_insert('location', frame=f)

# shafts: sunlight streaming in from behind into the rim, then converging on the focus
for k, rp in enumerate(RIM):
    t0 = 0.25 + 0.12 * k
    far = rp + V(-260, (rp.y) * 0.4, (rp.z) * 0.4)
    P.beam(lw(far), lw(rp), t0, T_OFF - 0.05, GOLD, width=0.2, strength=5)
    P.beam(lw(rp), lw(FOCUS_L), t0 + 0.15, T_OFF - 0.05, GOLD, width=0.16, strength=5)
P.sfx(0.3, 'charge_gold', gain=0.9, pos=W(lens, 0.3, FOCUS_L))
P.sfx(0.6, 'motes_loop', gain=0.5, pos=W(lens, 1.0, FOCUS_L), dur=1.4)

# ------------------------------------------------------------------------------- the shield
SH_R = 50.0
SH_C = BS_C + V(0, 0, 0)
n0 = (W(lens, T_FIRE, FOCUS_L) - SH_C).normalized()


def contact_dir(t):
    """Where the beam meets the membrane: first straight on, then slicing sideways across it."""
    u = ss((t - T_SLICE0) / (T_SLICE1 - T_SLICE0))
    ang = math.radians(lerp(-4, 8, u))
    el = math.radians(lerp(22, -26, u))
    return (Matrix.Rotation(ang, 3, 'Z') @ Matrix.Rotation(el, 3, Vector((0, 0, 1)).cross(n0).normalized()) @ n0).normalized()


def depth(t):
    d = 20.0 * ss((t - T_FIRE) / 0.45) + 10.0 * ss((t - 3.2) / 1.0)
    return d if t < T_OFF else 0.0


HIT_T = [T_FIRE + 0.02 + 0.22 * k for k in range(int((T_OFF - T_FIRE) / 0.22))]
shell = P.shield_dome(SH_C, SH_R, 0.2, 6.3, color=SHB,
                      hits=[(t, SH_C + contact_dir(t) * SH_R) for t in HIT_T])

# dent: Warp on the shell and all its layers, its ends following the contact
src = K.empty('DentFrom')
dst = K.empty('DentTo')
for f in range(0, NF + 2):
    t = (f - 1) / FPS
    n = contact_dir(t)
    src.location = SH_C + n * SH_R
    dst.location = SH_C + n * (SH_R - depth(min(t, T_OFF - 0.01)))
    src.keyframe_insert('location', frame=f)
    dst.keyframe_insert('location', frame=f)
shell['fx_e'] = 0.75
for c_ in shell.children:
    if c_.name.startswith('ShieldLattice'):
        c_['fx_e'] = 0.55
sub = shell.modifiers.new('Smooth', 'SUBSURF')
sub.subdivision_type = 'SIMPLE'
sub.levels = sub.render_levels = 2
mods = []
for o in [shell] + list(shell.children_recursive):
    if o.type != 'MESH':
        continue
    w = o.modifiers.new('Dent', 'WARP')
    w.object_from = src
    w.object_to = dst
    w.falloff_radius = 30.0
    w.falloff_type = 'SMOOTH'
    w.use_volume_preserve = False
    first = 'Smooth' if o is shell else None
    while o.modifiers[0] != w and not (first and o.modifiers[1] == w and o.modifiers[0].name == first):
        with bpy.context.temp_override(object=o):
            bpy.ops.object.modifier_move_up(modifier=w.name)
    mods.append(w)
fo = P.T(T_OFF)
for w in mods:
    w.strength = 0.0
    w.keyframe_insert('strength', frame=P.T(T_FIRE) - 1)
    w.strength = 1.0
    w.keyframe_insert('strength', frame=P.T(T_FIRE) + 2)
    w.keyframe_insert('strength', frame=fo)
    for i, v in enumerate((-0.35, 0.18, -0.07, 0.0)):    # snaps back, wobbles, holds
        w.strength = v
        w.keyframe_insert('strength', frame=fo + (i + 1) * 4)


def dent_pt(t):
    n = contact_dir(t)
    return SH_C + n * (SH_R - depth(min(t, T_OFF - 0.01)) * 0.92)


# the beam: focus -> dent bottom, followed every frame
P.beam(lw(FOCUS_L), dent_pt, T_FIRE, T_OFF, GOLD, width=1.6, strength=9)
P.light(W(lens, T_FIRE, FOCUS_L), T_FIRE, GOLD, energy=2.0e5, dur=0.25, radius=4)
WFX.shield_hit(P, shell, next(c for c in shell.children if c.name.startswith('ShieldLattice')), SH_C, SH_R,
               T_OFF + 0.02, SH_C + contact_dir(T_OFF) * SH_R, SHB, False, 6.3)
P.cam_shake(T_FIRE + 0.04, 0.35, dur=0.4)
P.sfx(T_FIRE - 0.05, 'beam_start', gain=1.0, pos=W(lens, T_FIRE, FOCUS_L))
P.sfx(T_FIRE, 'crackle_loop', gain=0.5, pos=dent_pt(T_FIRE), dur=T_OFF - T_FIRE)
P.sfx(T_FIRE + 0.05, 'shield_loop', gain=0.8, pos=SH_C, dur=T_OFF - T_FIRE)
for t in HIT_T[::2]:
    P.sfx(t, 'shield_hit', gain=0.5, pos=dent_pt(t))
P.sfx(T_OFF + 0.02, 'shockwave', gain=0.8, pos=SH_C)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2000, box=((-120, 420), (-200, 200), (-120, 120)), size=0.15, avoid=()):
    me_ = bpy.data.meshes.new('SpaceDust')
    b = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        if any((c - q).length < 8.0 for q in avoid) or (c - SH_C).length < SH_R + 4:
            continue
        s = size * R.uniform(0.6, 1.4)
        r = bmesh.ops.create_icosphere(b, subdivisions=0, radius=s)
        bmesh.ops.translate(b, verts=r['verts'], vec=c)
    b.to_mesh(me_)
    b.free()
    o = K.link(bpy.data.objects.new('SpaceDust', me_))
    me_.materials.append(K.emit_mat('DustGlint', (0.55, 0.6, 0.75), 1.2))
    o.visible_shadow = False
    return o


# ------------------------------------------------------------------------------- camera
def cam_keys():
    keys = []

    def shot(t0, t1, n, fn, last=True):
        for i in range(n + 1):
            t_ = t0 + (t1 - t0) * i / n
            if i == n and last:
                t_ = t1 - 1 / FPS
            keys.append((t_,) + fn(t_, (t_ - t0) / (t1 - t0)))

    # 1: behind and beside the Lens: shafts converging, it fires at the shielded Broadside
    def s1f(t_, u):
        pos = V(lerp(-95, -72, ss(u)), lerp(-105, -84, ss(u)), lerp(34, 26, ss(u)))
        look = V(lerp(40, 85, ss(u)), lerp(0, 10, ss(u)), lerp(0, -3, ss(u)))
        return pos, look, 30

    shot(0, CUT1, 12, s1f)

    # 2: level profile of the shield: the dent reads in silhouette as the beam slices down it,
    # then the membrane snaps back with the Broadside unharmed inside
    side = Vector((0, 0, 1)).cross(n0).normalized()

    def s2f(t_, u):
        pos = SH_C - side * lerp(150, 128, ss(u)) + n0 * lerp(70, 55, ss(u)) + V(0, 0, lerp(8, 12, ss(u)))
        look = SH_C + n0 * lerp(38, 26, ss(u)) + V(0, 0, lerp(2, 0, ss(u)))
        return pos, look, lerp(28, 30, ss(u))

    shot(CUT1, 6.0, 14, s2f, last=False)
    return keys


P.camera(cam_keys(), lens=30, cuts=(CUT1,))
_cam_path = []
for _f in range(1, NF + 1):
    bpy.context.scene.frame_set(_f)
    _cam_path.append(P.cam.matrix_world.translation.copy())
dust_field(avoid=_cam_path)

print('focus', W(lens, 2, FOCUS_L), 'n0', n0, 'nose', NOSE)
P.render()
