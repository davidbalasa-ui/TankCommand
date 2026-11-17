"""Radar Tower (Terran sensor structure): the packed radar grinds up the last stretch of a dusk
hill, crests and digs in on the flat top. The mast telescopes up tall, the dish swings round and
starts turning, and a neon radar ping washes out from the hilltop across the whole valley,
draping over the terrain with a scan grid in its wake. As the ring passes an Arcadian column
hidden down in the valley, each contact lights up: an orange target ring under it and a target
diamond above it. Seconds later Terran artillery the tower is spotting for drops out of the sky
on the marked contacts. End on a low hero frame behind the tower: dish turning, a second ping
rolling out, wrecks burning under their markers.

Timeline (s): 0-1.9 climb (low tracking camera) | 1.9 crest + dig in | 2.0-3.15 unfold |
3.0 dish spins up | 3.3 first ping, sweep wedge follows the dish | ~3.95-4.3 contacts marked |
4.35-4.65 shells arrive (3 hits) | 5.0 second ping | 5.2-6 hero frame."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_radar', seconds=6.0, seed=7)
R = P.rnd
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

# --------------------------------------------------------------------------- terrain: a hill
HX, HY = 0.0, 0.0
H = 5.0          # hilltop height
R_TOP = 5.5      # flat top radius
R_FOOT = 19.0    # where the hill meets the valley


def hill(x, y):
    r = math.hypot(x - HX, y - HY)
    if r <= R_TOP:
        return H
    u = min(1.0, (r - R_TOP) / (R_FOOT - R_TOP))
    return H * (1 - K.smoothstep(u))


P.env('dusk', sun=(24, 0, -70), sun_energy=3.6, props=40,
      clear=[(0, 0, 21), (-12, -16, 9), (-20, -8, 7), (24, 6, 15)])
g = P.ground
for v in g.data.vertices:
    v.co.z += hill(v.co.x, v.co.y)
g.data.update()
for o in bpy.data.objects:          # props were dropped on the flat ground: lift them onto the hill
    if o.name.startswith('prop_'):
        o.location.z += hill(o.location.x, o.location.y)
P.flatten(0, 0, 6.5)
P.flatten(24, 6, 13)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


SAND = (0.52, 0.36, 0.24)

# --------------------------------------------------------------------------- the radar
T_TOP = 1.9
T_UF0, T_UF1 = 2.0, 3.15
rad = P.load('terran_radar', at=(0, 0), heading=0, label='radar')
route = [(0.0, (-17.5, -7.6)), (0.5, (-13.6, -5.9)), (1.0, (-9.2, -3.9)), (1.45, (-4.6, -1.9)),
         (T_TOP, (0.0, 0.0))]
keys = []
for t, (x, y) in route:
    keys.append((t, (x, y, gz(x, y) + 0.02)))
keys[-1] = (T_TOP, (0.0, 0.0, H))
rad.path(keys, pitch=True)
# hold level on the top once it has crested
root = rad.root
root.rotation_euler.y = 0.0
root.keyframe_insert('rotation_euler', index=1, frame=P.T(T_TOP))
rad.unfold(T_UF0, T_UF1)

# drive rumble + crest dip (model_root stacks on the root path)
m = rad.model_root
m.rotation_mode = 'XYZ'
for i in range(0, 23):
    t = i / 12
    m.location.z = 0.035 * math.sin(t * 29.0)
    m.keyframe_insert('location', index=2, frame=P.T(t))
for t, pitch, z in [(1.8, 0.0, 0.0), (1.95, 2.8, -0.05), (2.12, -1.0, -0.1), (2.35, 0.0, 0.0)]:
    m.rotation_euler.y = math.radians(pitch)
    m.location.z = z
    m.keyframe_insert('rotation_euler', index=1, frame=P.T(t))
    m.keyframe_insert('location', index=2, frame=P.T(t))
P.dust(rad, 0.0, T_TOP, every=0.08, size=1.0, color=SAND)


def dust_ring(center, t, r0, r1, n=18, size=1.1, life=1.4, opacity=0.3, rise=0.5):
    c = Vector(center)
    for k, r in enumerate((r0, r1)):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.9, 1.1)
            P.puff(p + Vector((0, 0, 0.25)), t + 0.1 * k + R.uniform(0, 0.04), size=size * (1 + 0.3 * k),
                   n=1, rise=rise * (1 + k), life=life, color=SAND, opacity=opacity)


dust_ring((0, 0, H), 2.0, 2.2, 3.6, n=14, size=0.9, life=1.2, opacity=0.3)
dust_ring((0, 0, H), T_UF1 - 0.15, 2.4, 3.8, n=14, size=0.8, life=1.1, opacity=0.22)

# dish yaw joint between the unfolding pivot and the dish (the pivot's rotation belongs to unfold)
piv = rad.parts['TurretPivot']
dish = rad.parts['Turret']
yaw = K.empty('DishYaw')
yaw.parent = piv
yaw.rotation_mode = 'XYZ'
mpi = dish.matrix_parent_inverse.copy()
dish.parent = yaw
dish.matrix_parent_inverse = mpi

T_SPIN = 3.0
SPIN_RATE = 140.0     # deg/s once up to speed


def dish_yaw(t):
    """Dish yaw (deg) relative to its deployed pose: eases in from T_SPIN."""
    if t <= T_SPIN:
        return 0.0
    ramp = 0.6
    if t < T_SPIN + ramp:
        u = (t - T_SPIN) / ramp
        return SPIN_RATE * ramp * u * u / 2
    return SPIN_RATE * (ramp / 2 + (t - T_SPIN - ramp))


f = int(P.T(T_SPIN))
while f <= P.nf + 1:
    t = (f - 1) / P.fps
    yaw.rotation_euler.z = math.radians(dish_yaw(t))
    yaw.keyframe_insert('rotation_euler', index=2, frame=f)
    f += 2
K.set_interp(yaw, 'LINEAR')

# beacon: a small neon light on the dish pulsing once deployed
bpy.context.scene.frame_set(int(P.T(T_UF1 + 0.1)))
mast_top = piv.matrix_world.translation.copy()
print('MAST TOP', mast_top)
M_BEAC = K.emit_mat('Beacon', ORANGE, 0.0)
beac = K.sphere('Beacon', 0.13, M_BEAC, seg=(10, 6))
beac.parent = piv
beac.location = (0, 0, 0.12)
for t, v in [(0, 0), (T_UF1, 0), (T_UF1 + 0.1, 2.5), (3.5, 0.4), (3.9, 2.5), (4.3, 0.4), (4.7, 2.5),
             (5.1, 0.4), (5.5, 2.5), (5.9, 0.4)]:
    K.key_strength(M_BEAC, P.T(t), v)

# --------------------------------------------------------------------------- radar ping on the ground
T_P1, T_P2 = 3.3, 5.0
SPD1, SPD2 = 30.0, 34.0
R0 = 3.0

gm = bpy.data.materials['GroundMat']
nt = gm.node_tree
N = nt.nodes
Lk = nt.links
bsdf = N.get('Principled BSDF')


def node(kind, **kw):
    n = N.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def math_n(op, a=None, b=None, clamp=False):
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


def keyed_value(name, keys_):
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
dist = math_n('SQRT', math_n('ADD', math_n('MULTIPLY', X, X), math_n('MULTIPLY', Y, Y)))


def ring_radius(t0, spd, t_end=6.2):
    return [(t0 - 0.01, 0.0), (t0, R0), (t_end, R0 + spd * (t_end - t0))]


def linear_fcurves(mat):
    ad = mat.node_tree.animation_data
    for fc in K._fcurves(ad.action):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'


Rp1 = keyed_value('R1', ring_radius(T_P1, SPD1))
Rp2 = keyed_value('R2', ring_radius(T_P2, SPD2))
A1 = keyed_value('A1', [(T_P1 - 0.01, 0.0), (T_P1, 1.0), (T_P1 + 1.4, 0.75), (T_P1 + 2.4, 0.0)])
A2 = keyed_value('A2', [(T_P2 - 0.01, 0.0), (T_P2, 1.0), (6.0, 0.75)])
SWEEP = keyed_value('Sweep', [(t / 24, math.radians(dish_yaw(t / 24))) for t in range(0, 150, 3)])
linear_fcurves(gm)


def ring(Rv, width, tail):
    d = math_n('SUBTRACT', Rv, dist)                       # >0 inside the ring
    edge = math_n('SUBTRACT', 1.0, math_n('DIVIDE', math_n('ABSOLUTE', d), width), clamp=True)
    edge = math_n('MULTIPLY', edge, edge)
    inside = math_n('GREATER_THAN', d, 0.0)
    tl = math_n('SUBTRACT', 1.0, math_n('DIVIDE', d, tail), clamp=True)
    tl = math_n('MULTIPLY', tl, inside)
    return edge, tl


e1, t1_ = ring(Rp1, 1.7, 14.0)
e2, t2_ = ring(Rp2, 1.5, 10.0)


def grid_line(c, spacing, w):
    v = math_n('ADD', math_n('MULTIPLY', c, 1.0 / spacing), 0.5)
    v = math_n('SUBTRACT', math_n('FRACT', v), 0.5)
    return math_n('SUBTRACT', 1.0, math_n('DIVIDE', math_n('ABSOLUTE', v), w), clamp=True)


grid = math_n('MAXIMUM', grid_line(X, 3.0, 0.05), grid_line(Y, 3.0, 0.05))

# sweep wedge following the dish: bright at the leading edge, fading behind; only inside the
# scanned range
ang = math_n('ARCTAN2', Y, X)
dang = math_n('FLOORED_MODULO', math_n('SUBTRACT', math_n('ADD', SWEEP, 0.0), ang), 2 * math.pi)
wedge = math_n('SUBTRACT', 1.0, math_n('DIVIDE', dang, 1.1), clamp=True)
wedge = math_n('MULTIPLY', wedge, wedge)
in_range = math_n('LESS_THAN', dist, Rp1)
wedge = math_n('MULTIPLY', wedge, in_range)
wedge = math_n('MULTIPLY', wedge, math_n('ADD', 0.25, grid))

s1 = math_n('MULTIPLY', math_n('ADD', math_n('MULTIPLY', e1, 2.6), math_n('MULTIPLY', math_n('MULTIPLY', t1_, grid), 0.7)), A1)
s2 = math_n('MULTIPLY', math_n('ADD', math_n('MULTIPLY', e2, 2.2), math_n('MULTIPLY', math_n('MULTIPLY', t2_, grid), 0.5)), A2)
sw = math_n('MULTIPLY', wedge, 0.9)
total = math_n('ADD', math_n('ADD', s1, s2), sw)
# keep it off the hilltop pad right under the tower
total = math_n('MULTIPLY', total, math_n('DIVIDE', math_n('SUBTRACT', dist, 2.5), 2.0, clamp=True))
bsdf.inputs['Emission Color'].default_value = (*NEON, 1)
Lk.new(total, bsdf.inputs['Emission Strength'])


def ping_time(d, t0=T_P1, spd=SPD1):
    return t0 + max(0.0, d - R0) / spd


# --------------------------------------------------------------------------- the Arcadian column
# moving through the valley below, heading south-west across the foot of the hill
COLUMN = [
    ('lumen', (24.0, 9.0), (21.0, -3.0)),
    ('lumen', (30.5, 5.0), (27.5, -7.0)),
    ('aegis', (25.5, 18.0), (22.5, 7.5)),
    ('lumen', (31.0, 16.0), (28.0, 4.5)),
    ('sunfall', (28.0, 25.0), (25.5, 14.0)),
]
contacts = []
loaded = {}
for i, (nm, a0, a1) in enumerate(COLUMN):
    if nm in loaded:
        a = P.copy(loaded[nm], at=a0, label=f'{nm}{i}')
    else:
        a = P.load(nm, at=a0, label=f'{nm}{i}')
        loaded[nm] = a
    a.path([(0.0, (a0[0], a0[1], gz(*a0))), (6.0, (a1[0], a1[1], gz(*a1)))], interp='LINEAR')
    if nm == 'lumen':
        a.hover_bob(0.1, 0.8)
    contacts.append(a)

M_TGT = K.emit_mat('Target', ORANGE, 2.4)
M_TGT_SOFT = K.emit_mat('TargetSoft', ORANGE, 1.4, alpha=0.5)


def torus_ring(name, r, minor, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    n = 48
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        ring_ = []
        for j in range(6):
            b = 2 * math.pi * j / 6
            rr = r + minor * math.cos(b)
            ring_.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), minor * math.sin(b))))
        verts.append(ring_)
    for i in range(n):
        for j in range(6):
            bm.faces.new((verts[i][j], verts[(i + 1) % n][j], verts[(i + 1) % n][(j + 1) % 6], verts[i][(j + 1) % 6]))
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    return o


def diamond(name, s, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    pts = [(0, 0, 1.6), (0, 0, -1.6), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)]
    vs = [bm.verts.new(Vector(p) * s) for p in pts]
    for k in range(4):
        a, b = vs[2 + k], vs[2 + (k + 1) % 4]
        bm.faces.new((vs[0], a, b))
        bm.faces.new((vs[1], b, a))
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    return o


def mark(a, t_mark, t_end):
    """Orange target ring on the ground + a spinning target diamond over the contact."""
    f0, f1 = P.T(t_mark), P.T(t_end)
    h = a.entry.get('height', 2.5) or 2.5
    holder = K.empty(a.name + '_Mark')
    holder.parent = a.root
    rg = torus_ring('TgtRing', a.size * 0.55, 0.07, M_TGT)
    rg.parent = holder
    rg.location = (0, 0, 0.15)
    for t, s in [(t_mark, 2.2), (t_mark + 0.18, 0.9), (t_mark + 0.3, 1.0)]:
        rg.scale = (s, s, s)
        rg.keyframe_insert('scale', frame=P.T(t))
    dm = diamond('TgtDiamond', 0.38, M_TGT)
    dm.parent = holder
    dm.rotation_mode = 'XYZ'
    top = h + 2.2
    for t, z, s in [(t_mark, top + 1.5, 0.01), (t_mark + 0.2, top - 0.1, 1.15), (t_mark + 0.32, top, 1.0)]:
        dm.location = (0, 0, z)
        dm.scale = (s, s, s)
        dm.keyframe_insert('location', frame=P.T(t))
        dm.keyframe_insert('scale', frame=P.T(t))
    dm.rotation_euler.z = 0
    dm.keyframe_insert('rotation_euler', index=2, frame=f0)
    dm.rotation_euler.z = math.radians(300 * (t_end - t_mark))
    dm.keyframe_insert('rotation_euler', index=2, frame=f1)
    ln = K.polyline('TgtLine', [Vector((0, 0, h * 0.6)), Vector((0, 0, top - 0.6))], 0.025, M_TGT_SOFT)
    ln.parent = holder
    K.show_between(holder, f0, f1)
    p = a.pos_at(t_mark)
    P.light(p + Vector((0, 0, 2.0)), t_mark, ORANGE, energy=1500, dur=0.35, radius=1.0)


# --------------------------------------------------------------------------- artillery on the marks
T_HITS = [4.45, 4.62, 4.8]
VICTIMS = [0, 2, 1]
mark_times = {}
for i, a in enumerate(contacts):
    t = 3.3
    for _ in range(4):           # iterate: the contact moves while the ring travels
        p = a.pos_at(t)
        t = ping_time(math.hypot(p.x - HX, p.y - HY))
    mark_times[i] = t
print('MARK TIMES', mark_times)

M_SHELL = K.emit_mat('ShellGlow', ORANGE, 2.6)
for k, (vi, th) in enumerate(zip(VICTIMS, T_HITS)):
    a = contacts[vi]
    tgt = a.pos_at(th) + Vector((0, 0, 0.6))
    src = Vector((-15.0 + 8 * k, 70.0, 60.0))
    dur = 0.55
    # incoming shell: falling streak along a steep line from high behind the hill
    sh = K.sphere('Shell', 1.0, M_SHELL, seg=(8, 6))
    sh.rotation_mode = 'QUATERNION'
    d = tgt - src
    p_start = tgt - d.normalized() * 34.0
    sh.rotation_quaternion = d.to_track_quat('X', 'Z')
    sh.scale = (2.2, 0.07, 0.07)
    sh.location = p_start
    sh.keyframe_insert('location', frame=P.T(th - dur))
    sh.location = tgt
    sh.keyframe_insert('location', frame=P.T(th))
    K.set_interp(sh, 'LINEAR')
    K.show_between(sh, P.T(th - dur), P.T(th) + 1)
    a.destroy(th, size=2.4)
    P.cam_shake(th, 0.05, 0.3)

for i, a in enumerate(contacts):
    t_end = a.alive_until if a.alive_until is not None else 6.5
    mark(a, mark_times[i], t_end)

# --------------------------------------------------------------------------- camera
C = Vector((0, 0, H))
P.camera([
    (0.0, (-9.0, -19.0, gz(-9.0, -19.0) + 1.0), rad.pos_at(0.0) + Vector((0, 0, 1.6)), 30),
    (1.0, (-5.0, -15.5, gz(-5.0, -15.5) + 1.2), rad.pos_at(1.0) + Vector((0, 0, 1.8)), 30),
    (1.9, (1.0, -11.5, H + 0.5), (0.0, 0.0, H + 2.0), 26),
    (2.8, (3.6, -5.6, H + 0.35), (0.0, 0.0, H + 3.7), 21),
    (3.35, (2.0, -9.0, H + 2.2), (4.0, 1.0, H + 3.2), 21),
    (4.0, (-7.5, -10.0, H + 5.0), (16.0, 5.0, 3.6), 23),
    (4.7, (-5.5, -9.5, H + 4.8), (21.0, 5.0, 1.6), 32),
    (5.2, (-6.5, -9.5, H + 4.6), (16.0, 5.0, 5.6), 27),
    (6.0, (-8.5, -9.0, H + 4.5), (10.0, 4.0, H + 1.2), 23),
], shake=0.02)
P.cam_shake(1.95, 0.08, 0.35)

# explosion cores flash white under Standard: deepen to fire
for mat in bpy.data.materials:
    if mat.name.startswith('Core'):
        em = mat.node_tree.nodes[mat['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.35, 0.05, 1)
        em.inputs['Strength'].default_value = 2.4

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(T_SPIN, 'whirr_loop', gain=0.3, dur=6.0 - T_SPIN, rate=0.6)  # dish turning
for _t, _g in ((T_P1, 0.8), (T_P2, 0.55)):            # neon ping washing out over the valley
    P.sfx(_t, 'shockwave', gain=_g, rate=1.25)
    P.sfx(_t + 0.05, 'power_up_terran', gain=0.3 * _g, rate=1.4)
for _i, _t in enumerate(sorted(mark_times.values())):  # each contact marked
    P.sfx(_t, 'lock_pulse', gain=0.4, rate=1.0 + 0.06 * _i)
for _t in T_HITS:                                     # spotted artillery screaming in
    P.sfx(_t - 0.6, 'whoosh', gain=0.5, rate=0.75)

P.render()
