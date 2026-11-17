"""Watchman (Terran radar truck): it sees what you can't.

The Watchman grinds up a hazy ridge and parks on the crest, nose to the valley. The dish spins up,
and a neon radar ping rolls off the hilltop and out across the ground. Down in the haze the valley
looks empty, until the ring passes over it: one, two, three Arcadian raiders flash into view as
glowing outlines (neon on contact, then locked orange) creeping toward the hill. A beat later a
Longbow barrage from somewhere far behind the ridge drops out of the sky on exactly what the truck
found: three quick hits. End low in the valley among the burning wrecks, looking up at the
Watchman on the crest, dish still turning, a second ping rolling out under the camera.

Timeline (s): 0-1.75 climb (low tracking camera) | 1.75 cut: crest, dig in, dish spins up |
2.2 ping | 2.75 cut: over the shoulder into the valley | ~3.1-3.6 contacts revealed |
3.95 / 4.2 / 4.45 shells land | 4.9 cut: low hero frame from the valley | 5.2 second ping.

Hero loaded by model NAME ('watchman'); its emissive texture is remapped in-scene to neon blue
with orange accents, so a remodel only needs a re-render."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_watchman', seconds=6.0, seed=11)
R = P.rnd
FPS = P.fps
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']


def cut_t(frame):
    return (frame - 1) / FPS


# --------------------------------------------------------------------------- terrain: a ridge
H = 3.6          # crest height
R_TOP = 4.5
R_FOOT = 17.0


def hill(x, y):
    # elongated along Y so it reads as a ridge line
    r = math.hypot(x, y * 0.6)
    if r <= R_TOP:
        return H
    u = min(1.0, (r - R_TOP) / (R_FOOT - R_TOP))
    return H * (1 - K.smoothstep(u))


P.env('dusk', sun=(70, 0, -150), sun_energy=3.8, props=38,
      clear=[(0, 0, 18), (-14, -2, 8), (17, -2, 10), (10, -9, 6)])
g = P.ground
for v in g.data.vertices:
    v.co.z += hill(v.co.x, v.co.y)
g.data.update()
for o in bpy.data.objects:
    if o.name.startswith('prop_'):
        o.location.z += hill(o.location.x, o.location.y)
P.flatten(0, 0, 5.0)
P.flatten(17, -2, 7)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


SOIL = (0.5, 0.36, 0.25)

# --------------------------------------------------------------------------- the Watchman
T_TOP = 1.75
wm = P.load('watchman', at=(0, 0), heading=0, label='watchman')
route = [(0.0, (-15.5, -3.2)), (0.6, (-10.4, -2.0)), (1.2, (-5.0, -0.8)), (T_TOP, (0.0, 0.0))]
keys = [(t, (x, y, gz(x, y) + 0.02)) for t, (x, y) in route]
keys[-1] = (T_TOP, (0.0, 0.0, gz(0, 0) + 0.02))
wm.path(keys, pitch=True)
wm.root.rotation_euler.y = 0.0
wm.root.keyframe_insert('rotation_euler', index=1, frame=P.T(T_TOP))
wm.root.rotation_euler.y = 0.0
wm.root.keyframe_insert('rotation_euler', index=1, frame=P.T(6.2))
# ease the arrival (last segment decelerates)
K.set_interp(wm.root, 'BEZIER')

m = wm.model_root
m.rotation_mode = 'XYZ'
for i in range(0, 21):
    t = i / 12
    m.location.z = 0.03 * math.sin(t * 31.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
for t, pitch, z in [(1.7, 0.0, 0.0), (1.85, -2.5, -0.06), (2.05, 1.0, -0.04), (2.3, 0.0, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.location.z = z
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    m.keyframe_insert('location', index=2, frame=P.T(t))
P.dust(wm, 0.0, T_TOP, every=0.09, size=0.9, color=SOIL)

# dish: TurretPivot yaw, spinning up from the crest
piv = wm.parts.get('TurretPivot')
T_SPIN = 1.85
SPIN = 150.0


def dish_yaw(t):
    if t <= T_SPIN:
        return 0.0
    ramp = 0.6
    if t < T_SPIN + ramp:
        u = (t - T_SPIN) / ramp
        return SPIN * ramp * u * u / 2
    return SPIN * (ramp / 2 + (t - T_SPIN - ramp))


if piv is not None:
    piv.rotation_mode = 'XYZ'
    base = piv.rotation_euler.z
    f = 1
    while f <= P.nf + 2:
        piv.rotation_euler.z = base + math.radians(dish_yaw((f - 1) / FPS))
        piv.keyframe_insert('rotation_euler', index=2, frame=f)
        f += 2
    K.set_interp(piv, 'LINEAR')

# Terran glow: remap the model's emissive texture to neon blue, orange where the texture is warm
T_P1, T_P2 = 2.2, 5.2
for mat in {s.material for o in wm.meshes for s in o.material_slots if s.material}:
    nt = mat.node_tree
    b = nt.nodes.get('Principled BSDF')
    if b is None:
        continue
    em_in = b.inputs['Emission Color']
    src = em_in.links[0].from_socket if em_in.links else None
    if src is None:
        continue
    N, L = nt.nodes, nt.links
    hsv = N.new('ShaderNodeSeparateColor')
    hsv.mode = 'HSV'
    L.new(src, hsv.inputs[0])

    def mth(op, a, bb, clamp=False):
        n = N.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, x in enumerate((a, bb)):
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    hue, sat, val = hsv.outputs[0], hsv.outputs[1], hsv.outputs[2]
    warm = mth('MAXIMUM', mth('LESS_THAN', hue, 0.14), mth('GREATER_THAN', hue, 0.93))
    warm = mth('MULTIPLY', warm, mth('GREATER_THAN', sat, 0.35))
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = (*NEON, 1)
    mix.inputs['B'].default_value = (*ORANGE, 1)
    L.new(warm, mix.inputs['Factor'])
    sc_ = N.new('ShaderNodeMix')
    sc_.data_type = 'RGBA'
    sc_.blend_type = 'MULTIPLY'
    sc_.inputs['Factor'].default_value = 1.0
    L.new(mix.outputs['Result'], sc_.inputs['A'])
    vv = N.new('ShaderNodeCombineColor')
    for i in range(3):
        L.new(mth('MINIMUM', mth('MULTIPLY', val, 1.6), 1.0), vv.inputs[i])
    L.new(vv.outputs[0], sc_.inputs['B'])
    L.new(sc_.outputs['Result'], em_in)
    es = b.inputs['Emission Strength']
    for t, v in [(0, 1.8), (T_P1 - 0.05, 1.8), (T_P1, 3.6), (T_P1 + 0.4, 1.8),
                 (T_P2 - 0.05, 1.8), (T_P2, 3.6), (T_P2 + 0.4, 1.8)]:
        es.default_value = v
        es.keyframe_insert('default_value', frame=P.T(t))

# --------------------------------------------------------------------------- radar ping (own decal)
PING_R = 48.0
SPD1, SPD2 = 17.0, 19.0
R0 = 2.5
me = bpy.data.meshes.new('PingDisc')
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=120, y_segments=120, size=PING_R)
bm.to_mesh(me)
bm.free()
disc = K.link(bpy.data.objects.new('PingDisc', me))
disc.location = (0, 0, H + 12)
sw = disc.modifiers.new('Wrap', 'SHRINKWRAP')
sw.target = P.ground
sw.wrap_method = 'PROJECT'
sw.use_project_z = True
sw.use_negative_direction = True
sw.use_positive_direction = False
sw.offset = 0.07
disc.visible_shadow = False
for p in me.polygons:
    p.use_smooth = True

pm = bpy.data.materials.new('PingMat')
pm.use_nodes = True
nt = pm.node_tree
nt.nodes.clear()
N, Lk = nt.nodes, nt.links


def node(kind, **kw):
    n = N.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def mth(op, a=None, b=None, clamp=False):
    n = node('ShaderNodeMath', operation=op)
    n.use_clamp = clamp
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            Lk.new(x, n.inputs[i])
    return n.outputs[0]


def keyed(name, keys_):
    n = node('ShaderNodeValue')
    n.label = name
    for t, v in keys_:
        n.outputs[0].default_value = v
        n.outputs[0].keyframe_insert('default_value', frame=P.T(t))
    return n.outputs[0]


coord = node('ShaderNodeTexCoord')
sep = node('ShaderNodeSeparateXYZ')
Lk.new(coord.outputs['Object'], sep.inputs[0])
X, Y = sep.outputs[0], sep.outputs[1]
dist = mth('SQRT', mth('ADD', mth('MULTIPLY', X, X), mth('MULTIPLY', Y, Y)))


def rkeys(t0, spd, t_end=6.3):
    return [(t0 - 0.01, 0.0), (t0, R0), (t_end, R0 + spd * (t_end - t0))]


Rp1 = keyed('R1', rkeys(T_P1, SPD1))
Rp2 = keyed('R2', rkeys(T_P2, SPD2))
A1 = keyed('A1', [(T_P1 - 0.01, 0.0), (T_P1, 1.0), (T_P1 + 1.8, 0.8), (T_P1 + 3.0, 0.0)])
A2 = keyed('A2', [(T_P2 - 0.01, 0.0), (T_P2, 1.0), (6.2, 0.85)])
ad = nt.animation_data
for fc in K._fcurves(ad.action):
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'


def ring(Rv, width, tail):
    d = mth('SUBTRACT', Rv, dist)
    edge = mth('SUBTRACT', 1.0, mth('DIVIDE', mth('ABSOLUTE', d), width), clamp=True)
    edge = mth('MULTIPLY', edge, edge)
    inside = mth('GREATER_THAN', d, 0.0)
    tl = mth('SUBTRACT', 1.0, mth('DIVIDE', d, tail), clamp=True)
    return edge, mth('MULTIPLY', tl, inside), d


def grid_line(c, spacing, w):
    v = mth('ADD', mth('MULTIPLY', c, 1.0 / spacing), 0.5)
    v = mth('SUBTRACT', mth('FRACT', v), 0.5)
    return mth('SUBTRACT', 1.0, mth('DIVIDE', mth('ABSOLUTE', v), w), clamp=True)


# polar scan grid: range rings + spokes
rings_ = mth('SUBTRACT', 1.0, mth('DIVIDE', mth('ABSOLUTE', mth('SUBTRACT', mth('FRACT', mth('MULTIPLY', dist, 1 / 4.0)), 0.5)), 0.06), clamp=True)
ang = mth('ARCTAN2', Y, X)
spokes = mth('SUBTRACT', 1.0, mth('DIVIDE', mth('ABSOLUTE', mth('SUBTRACT', mth('FRACT', mth('MULTIPLY', ang, 12 / math.pi)), 0.5)), 0.05), clamp=True)
grid = mth('MAXIMUM', rings_, mth('MULTIPLY', spokes, mth('LESS_THAN', 0.0, dist)))

e1, t1_, d1 = ring(Rp1, 1.9, 10.0)
e2, t2_, d2 = ring(Rp2, 1.7, 8.0)
# thin orange accent line riding just behind each neon front
acc1 = mth('SUBTRACT', 1.0, mth('DIVIDE', mth('ABSOLUTE', mth('SUBTRACT', d1, 2.6)), 0.3), clamp=True)
acc2 = mth('SUBTRACT', 1.0, mth('DIVIDE', mth('ABSOLUTE', mth('SUBTRACT', d2, 2.4)), 0.28), clamp=True)
neon = mth('ADD',
           mth('MULTIPLY', mth('ADD', e1, mth('MULTIPLY', mth('MULTIPLY', t1_, grid), 0.55)), A1),
           mth('MULTIPLY', mth('ADD', e2, mth('MULTIPLY', mth('MULTIPLY', t2_, grid), 0.45)), A2))
orng = mth('ADD', mth('MULTIPLY', acc1, A1), mth('MULTIPLY', acc2, A2))
# fade near the truck and at the disc edge
fade = mth('MULTIPLY', mth('DIVIDE', mth('SUBTRACT', dist, 2.2), 2.0, clamp=True),
           mth('DIVIDE', mth('SUBTRACT', PING_R - 1.0, dist), 6.0, clamp=True))
neon = mth('MULTIPLY', neon, fade)
orng = mth('MULTIPLY', orng, fade)
alpha = mth('MINIMUM', mth('ADD', neon, orng), 1.0)
em_n = node('ShaderNodeEmission')
em_n.inputs['Color'].default_value = (*NEON, 1)
Lk.new(mth('MULTIPLY', neon, 3.2), em_n.inputs['Strength'])
em_o = node('ShaderNodeEmission')
em_o.inputs['Color'].default_value = (*ORANGE, 1)
Lk.new(mth('MULTIPLY', orng, 2.6), em_o.inputs['Strength'])
addsh = node('ShaderNodeAddShader')
Lk.new(em_n.outputs[0], addsh.inputs[0])
Lk.new(em_o.outputs[0], addsh.inputs[1])
tr = node('ShaderNodeBsdfTransparent')
mixs = node('ShaderNodeMixShader')
Lk.new(alpha, mixs.inputs[0])
Lk.new(tr.outputs[0], mixs.inputs[1])
Lk.new(addsh.outputs[0], mixs.inputs[2])
out = node('ShaderNodeOutputMaterial')
Lk.new(mixs.outputs[0], out.inputs['Surface'])
me.materials.append(pm)

# a burst of light off the dish on each ping
bpy.context.scene.frame_set(int(P.T(2.0)))
dish_pt = (piv.matrix_world.translation if piv else wm.root.matrix_world.translation) + Vector((0, 0, 2.0))
for tp in (T_P1, T_P2):
    P.light(dish_pt, tp, NEON, energy=500, dur=0.3, radius=1.5)


def ping_time(dd, t0=T_P1, spd=SPD1):
    return t0 + max(0.0, dd - R0) / spd


# --------------------------------------------------------------------------- the hidden Arcadians
CAST = [  # name, start, end (creeping toward the ridge)
    ('lumen', (15.0, -6.5), (12.8, -5.4)),
    ('flare', (19.0, 1.0), (16.6, 0.6)),
    ('lumen', (22.5, -3.8), (20.0, -3.0)),
]
targets = []
loaded = {}
for i, (nm, a0, a1) in enumerate(CAST):
    a = P.load(nm, at=a0, label=f'{nm}{i}')
    dz = 0.45 if nm == 'lumen' else 0.0
    a.path([(0.0, (a0[0], a0[1], gz(*a0) + dz)), (6.0, (a1[0], a1[1], gz(*a1) + dz))], interp='LINEAR')
    if nm == 'lumen':
        a.hover_bob(0.1, 0.9)
    a._dz = dz
    targets.append(a)

# contact outlines: a copy of each target pushed out a hair, glowing only at grazing angles (a
# fresnel rim), so the silhouette lights up while the body stays readable inside it
M_OUT = bpy.data.materials.new('RadarOutline')
M_OUT.use_nodes = True
ont = M_OUT.node_tree
ont.nodes.clear()
_n, _l = ont.nodes, ont.links
o_lw = _n.new('ShaderNodeLayerWeight')
o_lw.inputs['Blend'].default_value = 0.5
o_oi = _n.new('ShaderNodeObjectInfo')


def _m(op, a, b, clamp=False):
    n = _n.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i_, x in enumerate((a, b)):
        if isinstance(x, (int, float)):
            n.inputs[i_].default_value = x
        else:
            _l.new(x, n.inputs[i_])
    return n.outputs[0]


rim = _m('MULTIPLY', _m('POWER', o_lw.outputs['Facing'], 2.2), 1.7, clamp=True)
mask = _m('MULTIPLY', rim, _m('MINIMUM', _m('MULTIPLY', o_oi.outputs['Alpha'], 3.0), 1.0))
o_em = _n.new('ShaderNodeEmission')
_l.new(o_oi.outputs['Color'], o_em.inputs['Color'])
_l.new(_m('MULTIPLY', o_oi.outputs['Alpha'], 3.2), o_em.inputs['Strength'])
o_tr = _n.new('ShaderNodeBsdfTransparent')
o_mix = _n.new('ShaderNodeMixShader')
_l.new(mask, o_mix.inputs[0])
_l.new(o_tr.outputs[0], o_mix.inputs[1])
_l.new(o_em.outputs[0], o_mix.inputs[2])
o_out = _n.new('ShaderNodeOutputMaterial')
_l.new(o_mix.outputs[0], o_out.inputs['Surface'])


def outline(a, t_rev):
    shells = []
    for mo in list(a.meshes):
        c = mo.copy()
        K.link(c)
        c.animation_data_clear()
        c.parent = mo.parent
        c.matrix_parent_inverse = mo.matrix_parent_inverse.copy()
        sc = mo.matrix_world.to_scale()
        k = max(1e-4, (abs(sc.x) + abs(sc.y) + abs(sc.z)) / 3)
        dm = c.modifiers.new('Push', 'DISPLACE')
        dm.mid_level = 0.0
        dm.strength = 0.035 / k
        for sl in c.material_slots:
            sl.link = 'OBJECT'
            sl.material = M_OUT
        c.visible_shadow = False
        for t, col, al in [(0.0, NEON, 0.0), (t_rev - 0.01, NEON, 0.0), (t_rev, (0.5, 0.82, 1.0), 1.0),
                           (t_rev + 0.15, NEON, 0.8), (t_rev + 0.5, ORANGE, 0.6), (6.5, ORANGE, 0.55)]:
            c.color = (*col, al)
            c.keyframe_insert('color', frame=P.T(t))
        shells.append(c)
    return shells


reveal = []
for a in targets:
    t = T_P1
    for _ in range(4):
        p = a.pos_at(t)
        t = ping_time(math.hypot(p.x, p.y))
    reveal.append(t)
print('REVEAL', reveal)

T_HITS = [3.95, 4.2, 4.45]
ORDER = [0, 1, 2]
for a, t_rev in zip(targets, reveal):
    outline(a, t_rev)
    a.appear(t_rev)
    p = a.pos_at(t_rev)
    P.light(p + Vector((0, 0, 2.5)), t_rev, NEON, energy=1400, dur=0.3, radius=1.5)

# --------------------------------------------------------------------------- Longbow barrage
SHELL_SPEED = 95.0
for vi, th in zip(ORDER, T_HITS):
    a = targets[vi]
    tgt = a.pos_at(th) + Vector((0, 0, 0.5))
    src = tgt + Vector((-62.0 + R.uniform(-4, 4), R.uniform(-8, 8), 58.0))
    dur = (tgt - src).length / SHELL_SPEED
    P.projectile(src, tgt, th - dur, SHELL_SPEED, COL['tracer'], size=0.22, arc=0.0)
    a.destroy(th, size=2.4)
    P.cam_shake(th, 0.06, 0.3)
    # hover wrecks: put them on the ground
    w = bpy.data.objects.get(a.name + '_Wreck')
    if w is not None and a._dz:
        w.location.z -= a._dz
    # vanish() re-keyed frame 0 to visible: keep it hidden before the reveal
    for o in [a.root] + list(a.root.children_recursive):
        K.key_hide(o, 0, True)

# --------------------------------------------------------------------------- camera
C1, C2, C3 = cut_t(43), cut_t(67), cut_t(119)   # 1.75, 2.75, 4.92
crest = Vector((0, 0, gz(0, 0)))
keys = [
    # shot A: low on the slope, truck grinding up toward and past the lens
    (0.0, (-7.5, -8.5, gz(-7.5, -8.5) + 0.7), wm.pos_at(0.0) + Vector((0, 0, 1.9)), 30),
    (0.9, (-5.6, -8.0, gz(-5.6, -8.0) + 0.8), wm.pos_at(0.9) + Vector((0, 0, 2.0)), 30),
    (C1 - 1 / FPS, (-3.8, -8.4, gz(-3.8, -8.4) + 1.0), wm.pos_at(C1) + Vector((0, 0, 2.3)), 27),
    # shot B: crest, low front three-quarter, dish spinning up, ping rolls past the lens
    (C1, (4.2, -3.9, crest.z + 0.45), crest + Vector((-0.4, 0, 2.2)), 22),
    (C2 - 1 / FPS, (3.5, -3.3, crest.z + 0.55), crest + Vector((-0.5, 0, 2.5)), 21),
    # shot C: over the shoulder into the valley, pushing in on the contacts
    (C2, (-8.6, -3.6, crest.z + 3.4), Vector((15.5, -2.4, 1.0)), 32),
    (3.7, (-6.6, -3.9, crest.z + 3.5), Vector((16.0, -2.4, 0.9)), 40),
    (C3 - 1 / FPS, (-5.2, -4.0, crest.z + 3.4), Vector((16.5, -2.4, 0.9)), 47),
    # shot D: low rear three-quarter from the other side: dish turning, wrecks burning below
    (C3, (-6.4, 6.3, crest.z + 2.1), Vector((2.6, -1.6, crest.z + 1.1)), 27),
    (6.0, (-5.3, 6.6, crest.z + 1.7), Vector((2.2, -1.8, crest.z + 1.5)), 31),
]
P.camera(keys, shake=0.015, cuts=(C1, C2, C3))
P.cam_shake(1.85, 0.05, 0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(T_SPIN, 'whirr_loop', gain=0.3, dur=6.0 - T_SPIN, rate=0.65)  # dish spins up
for _t, _g in ((T_P1, 0.8), (T_P2, 0.55)):            # radar ping rolling out off the crest
    P.sfx(_t, 'shockwave', gain=_g, rate=1.25)
    P.sfx(_t + 0.05, 'power_up_terran', gain=0.3 * _g, rate=1.4)
for _i, _t in enumerate(reveal):                      # contacts flash into view, then lock
    P.sfx(_t, 'lock_pulse', gain=0.45, rate=1.0 + 0.06 * _i)
for _t in T_HITS:                                     # Longbow shells dropping in
    P.sfx(_t - 0.6, 'whoosh', gain=0.5, rate=0.75)

P.render()
