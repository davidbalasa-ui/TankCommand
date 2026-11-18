"""Seer (Arcadian sensor): only the eye looks over the ridge.

A Seer glides up a slope on its gold lightning skirt with a Sunfall lumbering in behind it and
parks on a shelf just under a ridge crest: the hull stays in cover, only the tall mast and its
great eye stand above the skyline. The crescent dish stops idling, swings round and stares over
the crest; the eye opens and a fan of pale white-gold light washes out over the ridge and down
into the hollow beyond, where a Terran ambush sits hull-down waiting for whatever crests the
ridge. As the light passes, each tank snaps on a gold outline. A Lancer panics and fires at the
eye: the shell only hits the crest. Behind the ridge the Sunfall heaves three times; three small
suns arc high over the Seer and fall on the marked tanks.

0-1.33    low front 3/4 on the slope: the Seer glides up at us and settles under the crest, dish
          idling; the Sunfall lumbers in behind.
1.33-2.83 on the crest, looking back up at the mast over the skyline: the dish swings round to stare
          at us, the eye opens (charge, halo) and the light wave washes over the camera.
2.83-4.0  far side, low behind the Terran ambush: the wave rolls down the slope, the tanks light
          up gold one by one; a Lancer fires at the eye and hits the crest.
4.0-6.0   high behind the Arcadians: the Sunfall heaves three times, three suns arc over the Seer
          and the ridge and crash down on the outlined tanks; end on burning wrecks under the
          Seer's gaze."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link, sphere  # noqa: E402

P = Promo('arcadian_seer', seconds=6.0, seed=11)
FPS = P.fps
R = P.rnd
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
PALE = (1.0, 0.84, 0.55)          # the Seer's pale white-gold sensor light


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


# --------------------------------------------------------------------------- terrain: shelf + ridge
SHELF_Z = 1.4
CREST_X = 0.3


def crest_x(y):
    return CREST_X + 0.6 * math.sin(y * 0.15) + 0.3 * math.sin(y * 0.41 + 1.0)


def ridge(x, y):
    taper = ss((60 - abs(y)) / 18.0)
    cx = crest_x(y)
    shelf = SHELF_Z * ss((x + 17.0) / 11.0) * (1 - ss((x - cx - 0.8) / 7.5))
    crest = 1.95 * math.exp(-((x - cx) / 2.4) ** 2)
    return (shelf + crest) * taper


P.env('highland', sun=(58, 0, 150), sun_energy=3.8, props=30,
      clear=[(-6, 0, 9), (-15, 8, 7), (12, -7, 10), (-26, 9, 5)])
g = P.ground
for v in g.data.vertices:
    v.co.z += ridge(v.co.x, v.co.y)
g.data.update()
P.flatten(-6, 0, 8)
P.flatten(-15, 9, 6)
P.flatten(12, -7, 9)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


# --------------------------------------------------------------------------- the Terran ambush
# hull-down in the hollow behind the ridge, guns laid on the crest, waiting
LA = (10.5, -3.0)
BU = (15.0, -8.5)
LB = (8.8, -11.0)
lancA = P.load('lancer', at=(*LA, gz(*LA)), heading=168, label='lancerA')
lancA.split_barrels()
bulwark = P.load('bulwark', at=(*BU, gz(*BU)), heading=158, label='bulwark')
bulwark.split_barrels()
lancB = P.load('lancer', at=(*LB, gz(*LB)), heading=140, label='lancerB')
lancB.split_barrels()
TERRANS = [lancA, bulwark, lancB]

# --------------------------------------------------------------------------- the Seer
HOV = 0.4
SX, SY = -5.5, 0.0
seer = P.load('seer', at=(-22, 3), heading=0, label='seer')
route = [(0.0, (-22.0, 3.0)), (0.55, (-13.0, 1.4)), (1.05, (-8.0, 0.35)), (1.45, (-5.8, 0.02)),
         (1.9, (SX, SY)), (6.0, (SX - 0.05, SY))]
keys = []
for i, (t, (x, y)) in enumerate(route):
    h = 0.0 if i >= len(route) - 2 else None
    keys.append((t, (x, y, gz(x, y) + HOV), h))
seer.path(keys)
seer.hover_bob(0.04, 0.9)

# ----- Seer anatomy (model space, measured at rest)
bpy.context.view_layer.update()
s_hull = [o for o in seer.meshes if o.name.startswith('Hull')][0]
s_eye = [o for o in seer.meshes if o.name.startswith('Eye')][0]
inv = seer.model_root.matrix_world.inverted()
hv = [inv @ (s_hull.matrix_world @ v.co) for v in s_hull.data.vertices]
belly = [p for p in hv if p.z < 0.3]
ev = [inv @ (s_eye.matrix_world @ v.co) for v in s_eye.data.vertices]
core = [p for p in ev if abs(p.y) < 0.75]
EYE_C = Vector(((min(p.x for p in core) + max(p.x for p in core)) / 2, 0.0,
                (min(p.z for p in core) + max(p.z for p in core)) / 2))
EYE_R = (max(p.z for p in core) - min(p.z for p in core)) / 2
print('SEER eye centre', EYE_C, 'r', EYE_R, 'belly n', len(belly))
eye_anchor = K.empty('SeerEyeAnchor')
eye_anchor.parent = seer.turret
bpy.context.view_layer.update()
eye_anchor.matrix_parent_inverse = seer.turret.matrix_world.inverted() @ seer.model_root.matrix_world
eye_anchor.location = EYE_C


def jag(p0, p1, segs, amp, rnd):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            e = math.sin(math.pi * u)
            q += Vector((rnd.uniform(-amp, amp), rnd.uniform(-amp, amp), rnd.uniform(-amp, amp) * 0.5)) * e
        pts.append(q)
    return pts


def jag_pts(p0, p1, segs, jg):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jg * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
        pts.append(p0 + d * u + off)
    return pts


# ----- lightning lifters: short, dense crackle tucked under the belly (Darter/Aegis skirt)
bolt_mat = emit_mat('SeerLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('SeerLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)


def crackle(a, pts, n_lift, light_e, tag):
    rnd = P.rnd
    X0, X1 = min(p.x for p in pts) * 0.7, max(p.x for p in pts) * 0.7
    BY = max(abs(p.y) for p in pts) * 0.55
    for f in range(1, P.nf + 2):
        objs = []
        for k in range(n_lift):
            p0 = Vector((rnd.uniform(X0, X1), rnd.uniform(-BY, BY), 0.06))
            if k % 3 == 0:
                p1 = p0 + Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.2, 0.2), -rnd.uniform(0.0, 0.08)))
            else:
                side = 1 if p0.y > 0 else -1
                p1 = p0 + Vector((rnd.uniform(-0.25, 0.15), side * rnd.uniform(0.1, 0.3), -rnd.uniform(0.14, 0.3)))
            pp = jag(p0, p1, 4, 0.07, rnd)
            objs += [polyline(tag + 'Lift', pp, 0.014, bolt_mat), polyline(tag + 'LiftHalo', pp, 0.05, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            o.visible_shadow = False
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new(tag + 'LiftLight', bpy.data.lights.new(tag + 'LiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.2)
    L.data.color = GOLD
    L.data.energy = light_e
    L.data.shadow_soft_size = 0.8


crackle(seer, belly, 11, 110, 'S')
P.dust(seer, 0.0, 1.8, every=0.1, size=0.5)

# ----- the dish: idles round, swings to stare over the crest, then scans slowly
DISH = -24.0          # yaw (deg, = world heading: hull faces +X) that looks over the crest at the ambush
T_SWING0, T_SWING1 = 1.5, 1.95
T_OPEN = 2.05
T_WAVE = 2.45
dish_keys = [(0.0, -160.0), (0.5, -137.0), (1.0, -114.0), (T_SWING0, -91.0), (T_SWING1, DISH + 9.0),
             (T_SWING1 + 0.12, DISH - 3.0), (T_SWING1 + 0.25, DISH), (3.6, DISH - 2.0), (4.6, DISH + 5.0),
             (6.0, DISH - 4.0)]
seer.turret_yaw(dish_keys)
for fc in K._fcurves(seer.turret.animation_data.action):
    for kp in fc.keyframe_points:
        if kp.co.x <= P.T(T_SWING0) + 0.5:
            kp.interpolation = 'LINEAR'

# ----- the eye opens: the unit's own sensor glow sleeps dim, then wakes
smat = bpy.data.materials['SeerMat']
sb = smat.node_tree.nodes.get('Principled BSDF')
E0 = sb.inputs['Emission Strength'].default_value
for t, k in [(0.0, 0.35), (T_OPEN - 0.25, 0.35), (T_OPEN - 0.05, 0.6), (T_OPEN + 0.08, 1.15),
             (T_WAVE - 0.03, 1.0), (T_WAVE + 0.02, 1.3), (T_WAVE + 0.3, 1.0), (6.0, 1.0)]:
    sb.inputs['Emission Strength'].default_value = E0 * k
    sb.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))

eL = link(bpy.data.objects.new('SeerEyeLight', bpy.data.lights.new('SeerEyeLight', 'POINT')))
eL.parent = eye_anchor
eL.location = (EYE_R + 0.4, 0, 0)
eL.data.color = PALE
eL.data.shadow_soft_size = 0.5
for t, e in [(0, 0), (T_OPEN - 0.05, 0), (T_OPEN + 0.08, 900), (T_WAVE - 0.05, 500), (T_WAVE, 1500),
             (T_WAVE + 0.35, 450), (6.0, 400)]:
    eL.data.energy = e
    eL.data.keyframe_insert('energy', frame=P.T(t))


def eye_w(t):
    return seer.world_at(eye_anchor, t)


M_CH = emit_mat('SeerCharge', PALE, 1.8)
M_CHG = emit_mat('SeerChargeGlow', PALE, 0.8, alpha=0.2)
# charge: short pale crackles converge on the eye as it opens
t = T_OPEN - 0.15
while t < T_WAVE:
    f = int(round(P.T(t)))
    pe = eye_w(t)
    for _ in range(3):
        a = R.uniform(0, 2 * math.pi)
        rr = R.uniform(EYE_R + 0.5, EYE_R + 1.2)
        p0 = pe + Vector((0.3 * math.cos(a) * rr, rr * math.sin(a), R.uniform(-0.9, 0.9)))
        pts = jag_pts(p0, pe + (p0 - pe).normalized() * EYE_R * 0.95, 5, 0.3)
        for o in (polyline('SCh', pts, 0.018, M_CH), polyline('SChG', pts, 0.06, M_CHG)):
            o.visible_shadow = False
            show_between(o, f, f + 1)
    t += 1 / FPS

# halo ring bursting off the eye as the wave leaves
M_HALO = emit_mat('SeerHalo', PALE, 1.6, alpha=0.55)
for tp_, s1 in ((T_OPEN + 0.02, 2.4), (T_WAVE, 4.5)):
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.03, major_segments=64, minor_segments=6)
    h = bpy.context.active_object
    h.name = 'SeerHaloRing'
    h.data.materials.append(M_HALO)
    h.visible_shadow = False
    h.parent = eye_anchor
    h.rotation_euler = (0, math.radians(90), 0)       # ring faces the way the eye looks
    for dt, s in [(0.0, EYE_R * 1.05), (0.1, s1 * 0.6), (0.28, s1)]:
        h.scale = (s, s, s)
        h.keyframe_insert('scale', frame=P.T(tp_ + dt))
    show_between(h, P.T(tp_), P.T(tp_ + 0.28))

# --------------------------------------------------------------------------- the light wave
FAN = math.radians(DISH)
HALF = math.radians(50)
R0 = 1.6
SPD = 24.0
T_END = T_WAVE + 1.55
ORG = Vector((SX, SY, 0))


def wave_r(t):
    return R0 + SPD * (t - T_WAVE)


def fan_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, Lk = nt.nodes, nt.links

    def mn(op, a=None, b=None, clamp=False):
        n = N.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                Lk.new(x, n.inputs[i])
        return n.outputs[0]

    out = N.new('ShaderNodeOutputMaterial')
    tc = N.new('ShaderNodeTexCoord')
    sp = N.new('ShaderNodeSeparateXYZ')
    Lk.new(tc.outputs['Object'], sp.inputs[0])
    X, Y = sp.outputs[0], sp.outputs[1]
    dist = mn('SQRT', mn('ADD', mn('MULTIPLY', X, X), mn('MULTIPLY', Y, Y)))
    ang = mn('ABSOLUTE', mn('ARCTAN2', Y, X))
    rv = N.new('ShaderNodeValue')
    rv.label = 'WaveR'
    av = N.new('ShaderNodeValue')
    av.label = 'WaveA'
    for t_, r_ in [(T_WAVE - 0.01, 0.0), (T_WAVE, R0), (T_END + 0.2, wave_r(T_END + 0.2))]:
        rv.outputs[0].default_value = r_
        rv.outputs[0].keyframe_insert('default_value', frame=P.T(t_))
    for t_, a_ in [(T_WAVE - 0.01, 0.0), (T_WAVE, 1.0), (T_WAVE + 0.9, 0.85), (T_END, 0.0)]:
        av.outputs[0].default_value = a_
        av.outputs[0].keyframe_insert('default_value', frame=P.T(t_))
    for fc in K._fcurves(nt.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    d = mn('SUBTRACT', rv.outputs[0], dist)                     # >0 inside the front
    edge = mn('SUBTRACT', 1.0, mn('DIVIDE', mn('ABSOLUTE', d), 1.3), clamp=True)
    edge = mn('MULTIPLY', edge, edge)
    inside = mn('GREATER_THAN', d, 0.0)
    tail = mn('SUBTRACT', 1.0, mn('DIVIDE', d, 8.0), clamp=True)
    tail = mn('MULTIPLY', mn('MULTIPLY', tail, tail), inside)
    rip = mn('SUBTRACT', mn('FRACT', mn('MULTIPLY', dist, 1.0 / 1.8)), 0.5)
    rip = mn('SUBTRACT', 1.0, mn('DIVIDE', mn('ABSOLUTE', rip), 0.08), clamp=True)
    body = mn('ADD', edge, mn('MULTIPLY', tail, mn('ADD', 0.18, mn('MULTIPLY', rip, 0.5))))
    side = mn('SUBTRACT', 1.0, mn('DIVIDE', mn('SUBTRACT', ang, HALF * 0.55), HALF * 0.45, clamp=False), clamp=True)
    near = mn('DIVIDE', mn('SUBTRACT', dist, 1.2), 1.5, clamp=True)
    fac = mn('MULTIPLY', mn('MULTIPLY', mn('MULTIPLY', body, side), near), av.outputs[0])
    fac = mn('MINIMUM', fac, 1.0)
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*PALE, 1)
    em.inputs['Strength'].default_value = 2.0
    tr = N.new('ShaderNodeBsdfTransparent')
    mix = N.new('ShaderNodeMixShader')
    Lk.new(fac, mix.inputs[0])
    Lk.new(tr.outputs[0], mix.inputs[1])
    Lk.new(em.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], out.inputs['Surface'])
    return m


def fan_decal():
    """Ground-hugging polar fan (local +X = the fan direction), draped over the terrain."""
    me = bpy.data.meshes.new('SeerWave')
    bm = bmesh.new()
    nr, na = 120, 56
    rmax = wave_r(T_END) + 2
    rows = []
    for i in range(nr + 1):
        r = 1.0 + (rmax - 1.0) * (i / nr) ** 1.15
        row = []
        for j in range(na + 1):
            a = -HALF * 1.05 + 2 * HALF * 1.05 * j / na
            wa = FAN + a
            x, y = ORG.x + r * math.cos(wa), ORG.y + r * math.sin(wa)
            lx, ly = r * math.cos(a), r * math.sin(a)
            row.append(bm.verts.new((lx, ly, gz(x, y) + 0.06)))
        rows.append(row)
    for i in range(nr):
        for j in range(na):
            bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new('SeerWave', me))
    o.location = (ORG.x, ORG.y, 0)
    o.rotation_euler = (0, 0, FAN)
    me.materials.append(fan_mat('SeerWaveMat'))
    o.visible_shadow = False
    o.visible_diffuse = False
    o.visible_glossy = False
    show_between(o, P.T(T_WAVE) - 1, P.T(T_END) + 1)
    return o


fan_decal()


def curtain_mat():
    m = bpy.data.materials.new('SeerCurtain')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, Lk = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    uv = N.new('ShaderNodeUVMap')
    sp = N.new('ShaderNodeSeparateXYZ')
    Lk.new(uv.outputs[0], sp.inputs[0])
    # u: across the fan (0..1), v: up the curtain (0..1)
    v1 = N.new('ShaderNodeMath')
    v1.operation = 'SUBTRACT'
    v1.use_clamp = True
    v1.inputs[0].default_value = 1.0
    Lk.new(sp.outputs[1], v1.inputs[1])
    vp = N.new('ShaderNodeMath')
    vp.operation = 'POWER'
    vp.inputs[1].default_value = 2.2
    Lk.new(v1.outputs[0], vp.inputs[0])
    us = N.new('ShaderNodeMath')
    us.operation = 'MULTIPLY'
    us.inputs[1].default_value = math.pi
    Lk.new(sp.outputs[0], us.inputs[0])
    usn = N.new('ShaderNodeMath')
    usn.operation = 'SINE'
    Lk.new(us.outputs[0], usn.inputs[0])
    m1 = N.new('ShaderNodeMath')
    m1.operation = 'MULTIPLY'
    Lk.new(vp.outputs[0], m1.inputs[0])
    Lk.new(usn.outputs[0], m1.inputs[1])
    oi = N.new('ShaderNodeObjectInfo')
    m2 = N.new('ShaderNodeMath')
    m2.operation = 'MULTIPLY'
    m2.use_clamp = True
    Lk.new(m1.outputs[0], m2.inputs[0])
    Lk.new(oi.outputs['Alpha'], m2.inputs[1])
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*PALE, 1)
    em.inputs['Strength'].default_value = 1.4
    tr = N.new('ShaderNodeBsdfTransparent')
    mix = N.new('ShaderNodeMixShader')
    Lk.new(m2.outputs[0], mix.inputs[0])
    Lk.new(tr.outputs[0], mix.inputs[1])
    Lk.new(em.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], out.inputs['Surface'])
    return m


M_CURT = curtain_mat()


def curtain_frame(f):
    t = (f - 1) / FPS
    r = wave_r(t)
    u = (t - T_WAVE) / (T_END - T_WAVE)
    hgt = 2.6 * (1 - 0.45 * u)
    alpha = 0.6 * (1 - u) ** 1.2 * min(1.0, (t - T_WAVE) / 0.1 + 0.2)
    me = bpy.data.meshes.new('SeerCurt')
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    na = 64
    cols = []
    for j in range(na + 1):
        a = FAN - HALF + 2 * HALF * j / na
        x, y = ORG.x + r * math.cos(a), ORG.y + r * math.sin(a)
        z0 = gz(x, y) - 0.05
        cols.append((bm.verts.new((x, y, z0)), bm.verts.new((x, y, z0 + hgt)), j / na))
    for j in range(na):
        a0, a1 = cols[j], cols[j + 1]
        fc = bm.faces.new((a0[0], a1[0], a1[1], a0[1]))
        for lp, uvv in zip(fc.loops, ((a0[2], 0), (a1[2], 0), (a1[2], 1), (a0[2], 1))):
            lp[uvl].uv = uvv
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new('SeerCurt', me))
    me.materials.append(M_CURT)
    o.color = (1, 1, 1, alpha)
    o.visible_shadow = False
    o.visible_diffuse = False
    o.visible_glossy = False
    show_between(o, f, f + 1)


for f in range(int(P.T(T_WAVE)), int(P.T(T_END)) + 1):
    curtain_frame(f)


def wave_time(p):
    d = math.hypot(p.x - ORG.x, p.y - ORG.y)
    return T_WAVE + max(0.0, d - R0) / SPD


# --------------------------------------------------------------------------- gold outlines on contact
def outline_mat(name, keys_):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t_ = m.node_tree
    t_.nodes.clear()
    out = t_.nodes.new('ShaderNodeOutputMaterial')
    geo = t_.nodes.new('ShaderNodeNewGeometry')
    em = t_.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*GOLD, 1)
    tr = t_.nodes.new('ShaderNodeBsdfTransparent')
    mix = t_.nodes.new('ShaderNodeMixShader')
    t_.links.new(geo.outputs['Backfacing'], mix.inputs[0])
    t_.links.new(tr.outputs[0], mix.inputs[1])
    t_.links.new(em.outputs[0], mix.inputs[2])
    t_.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    for t, v in keys_:
        K.key_strength(m, P.T(t), v)
    return m


def add_outline(a, t_rev, t_end):
    """Inverted-hull gold outline round every mesh of the unit, snapping on at t_rev."""
    m = outline_mat(a.name + '_Outline', [(0, 0), (t_rev - 0.01, 0), (t_rev, 2.6), (t_rev + 0.25, 1.4),
                                          (t_end, 1.4)])
    for ms in list(a.meshes):
        c = ms.copy()
        link(c)
        c.parent = ms
        c.matrix_parent_inverse.identity()
        c.location = (0, 0, 0)
        c.rotation_euler = (0, 0, 0)
        c.rotation_quaternion = (1, 0, 0, 0)
        c.scale = (1, 1, 1)
        c.animation_data_clear()
        c.data = ms.data
        for s in c.material_slots:
            s.link = 'OBJECT'
            s.material = m
        sc_ = ms.matrix_world.to_scale()
        k = max(1e-4, (sc_.x + sc_.y + sc_.z) / 3)
        wl = c.modifiers.new('Weld', 'WELD')
        wl.merge_threshold = 0.002 / k
        dp = c.modifiers.new('Hull', 'DISPLACE')
        dp.direction = 'NORMAL'
        dp.mid_level = 0.0
        dp.strength = 0.045 / k
        c.visible_shadow = False
        c.visible_diffuse = False
        c.visible_glossy = False
        show_between(c, P.T(t_rev), P.T(t_end))


REV = {a.name: wave_time(a.pos_at(3.0)) for a in TERRANS}
print('REVEAL', REV)
M_SPARK = emit_mat('SeerRevealSpark', GOLD, 2.0)
for a in TERRANS:
    tr_ = REV[a.name]
    p = a.pos_at(tr_)
    P.light(p + Vector((0, 0, 2.0)), tr_, GOLD, energy=900, dur=0.3, radius=1.0)

# --------------------------------------------------------------------------- the Terrans react
# Lancer A panics and fires at the eye: the shell slams into the crest in front of the Seer
T_PANIC = 3.5
crest_hit = Vector((crest_x(-1.4) + 0.2, -1.4, 0))
crest_hit.z = gz(crest_hit.x, crest_hit.y) + 0.25
lancA.aim(T_PANIC, crest_hit, dur=0.3)
lancA.fire(T_PANIC, crest_hit, kind='cannon', impact_size=0.9)
bulwark.aim(4.2, eye_w(4.2) - Vector((0, 0, 1.2)), dur=0.6)
lancB.aim(4.0, eye_w(4.0) - Vector((0, 0, 1.5)), dur=0.55)
crest_hit2 = Vector((crest_x(-2.6) + 0.1, -2.6, 0))
crest_hit2.z = gz(crest_hit2.x, crest_hit2.y) + 0.3
bulwark.aim(4.6, crest_hit2, dur=0.3)
bulwark.fire(4.6, crest_hit2, kind='heavy', impact_size=1.0)

# --------------------------------------------------------------------------- the Sunfall
FX, FY = -7.2, 8.6
sunfall = P.load('sunfall', at=(-27, 12), heading=0, label='sunfall')
sroute = [(0.0, (-27.0, 7.5)), (1.2, (-17.0, 9.4)), (2.3, (FX, FY)), (6.0, (FX, FY))]
skeys = []
for i, (t, (x, y)) in enumerate(sroute):
    skeys.append((t, (x, y, gz(x, y) + 0.45), -38.0 if i >= 2 else None))
sunfall.path(skeys)
sunfall.hover_bob(0.035, 0.7)
bpy.context.view_layer.update()
f_hull = [o for o in sunfall.meshes if o.name.startswith('Hull')][0]
f_tur = [o for o in sunfall.meshes if o.name.startswith('Turret')][0]
finv = sunfall.model_root.matrix_world.inverted()
fbelly = [finv @ (f_hull.matrix_world @ v.co) for v in f_hull.data.vertices if (finv @ (f_hull.matrix_world @ v.co)).z < 0.3]
crackle(sunfall, fbelly, 13, 140, 'F')
P.dust(sunfall, 0.0, 2.4, every=0.14, size=0.65)
tv = [finv @ (f_tur.matrix_world @ v.co) for v in f_tur.data.vertices]
ztop = max(p.z for p in tv)
orbv = [p for p in tv if p.z > ztop - 1.1 and abs(p.y) < 0.7]
ORB_C = Vector((sum(p.x for p in orbv) / len(orbv), 0.0, sum(p.z for p in orbv) / len(orbv)))
print('SUNFALL orb centre', ORB_C)
orb_anchor = K.empty('SunfallOrbAnchor')
orb_anchor.parent = sunfall.turret
bpy.context.view_layer.update()
orb_anchor.matrix_parent_inverse = sunfall.turret.matrix_world.inverted() @ sunfall.model_root.matrix_world
orb_anchor.location = ORB_C

M_ORB = emit_mat('SunOrb', (1.0, 0.72, 0.3), 2.6)
M_ORBH = emit_mat('SunOrbHalo', GOLD, 1.1, alpha=0.22)
M_TRAIL = emit_mat('SunOrbTrail', GOLD, 1.2, alpha=0.3)
SHOTS = [(4.05, lancA, 0.78), (4.32, bulwark, 0.82), (4.59, lancB, 0.8)]


def fly_orb(t0, target, dur):
    p0 = sunfall.world_at(orb_anchor, t0) + Vector((0.4, 0, 0.5))
    th = t0 + dur
    p1 = target.pos_at(th) + Vector((0, 0, 0.7))
    apex = max(p0.z, p1.z) + 9.0
    hgt = apex - (p0.z + p1.z) / 2

    def at(u):
        return p0.lerp(p1, u) + Vector((0, 0, 4 * hgt * u * (1 - u)))

    core = sphere('SunOrb', 0.34, M_ORB, seg=(12, 8))
    halo = sphere('SunOrbHalo', 0.95, M_ORBH, seg=(12, 8))
    halo.parent = core
    for o in (core, halo):
        o.visible_shadow = False
    Lt = link(bpy.data.objects.new('SunOrbLight', bpy.data.lights.new('SunOrbLight', 'POINT')))
    Lt.parent = core
    Lt.data.color = GOLD
    Lt.data.energy = 600
    Lt.data.shadow_soft_size = 0.4
    n = int(dur * FPS) + 1
    for i in range(n + 1):
        u = i / n
        core.location = at(u)
        core.keyframe_insert('location', frame=P.T(t0 + dur * u))
    K.set_interp(core, 'LINEAR')
    show_between(core, P.T(t0), P.T(th) + 1)
    show_between(halo, P.T(t0), P.T(th) + 1)
    # glowing wake: fading blobs left behind each frame
    for i in range(1, n):
        u = i / n
        b = sphere('SunWake', 1.0, M_TRAIL, seg=(8, 6))
        b.visible_shadow = False
        b.location = at(u)
        f = P.T(t0 + dur * u)
        for df, s in ((0, 0.3), (3, 0.16), (6, 0.02)):
            b.scale = (s, s, s)
            b.keyframe_insert('scale', frame=f + df)
        show_between(b, f, f + 6)
    return p1, th


T_HITS = []
for i, (t0, tgt, dur) in enumerate(SHOTS):
    sunfall.aim(t0 - 0.02, tgt, dur=0.5 if i == 0 else 0.22)
    sunfall.recoil(t0, kick=13.0, back=0.35)
    # muzzle bloom: the orb leaves the cradle in a gold flash
    P.light(sunfall.world_at(orb_anchor, t0), t0, GOLD, energy=1800, dur=0.15, radius=0.8)
    p1, th = fly_orb(t0, tgt, dur)
    T_HITS.append(th)
    P.impact(p1, th, size=1.3, color=GOLD)
    P.light(p1 + Vector((0, 0, 1.0)), th, GOLD, energy=2500, dur=0.25, radius=0.8)
    for k in range(3):
        pts = jag_pts(p1 + Vector((0, 0, 0.4)), p1 + Vector((R.uniform(-2, 2), R.uniform(-2, 2), -0.5)), 6, 0.3)
        for o in (polyline('SunCrawl', pts, 0.03, bolt_mat), polyline('SunCrawlG', pts, 0.09, glow_mat)):
            o.visible_shadow = False
            show_between(o, int(round(P.T(th))) + k, int(round(P.T(th))) + k + 1)
    tgt.destroy(th + 0.03, size=2.2 if tgt is bulwark else 1.9)
    P.cam_shake(th, 0.07, 0.3)

# charge: light drawn into the orb before the volley
t = 3.6
while t < SHOTS[0][0]:
    f = int(round(P.T(t)))
    pe = sunfall.world_at(orb_anchor, t)
    for _ in range(2):
        a = R.uniform(0, 2 * math.pi)
        rr = R.uniform(1.4, 2.2)
        p0 = pe + Vector((rr * math.cos(a), rr * math.sin(a), R.uniform(-0.6, 0.8)))
        pts = jag_pts(p0, pe + (p0 - pe).normalized() * 0.5, 5, 0.3)
        for o in (polyline('FCh', pts, 0.02, bolt_mat), polyline('FChG', pts, 0.07, glow_mat)):
            o.visible_shadow = False
            show_between(o, f, f + 1)
    t += 1 / FPS

for a in TERRANS:
    add_outline(a, REV[a.name], (a.alive_until + 1 / FPS) if a.alive_until is not None else 6.5)

# --------------------------------------------------------------------------- camera
C1, C2, C3, C4 = 32 / FPS, 68 / FPS, 96 / FPS, 126 / FPS
EYE_T = eye_w(2.2)
keys = [
    # A: low on the Seer's left, by the crest: it glides up the slope at us past the Sunfall
    (0.0, (-1.2, 6.8, gz(-1.2, 6.8) + 1.3), seer.pos_at(0.0) + Vector((0, 0, 2.0)), 50),
    (0.7, (-1.3, 6.6, gz(-1.3, 6.6) + 1.35), seer.pos_at(0.7) + Vector((0, 0, 2.2)), 34),
    (C1 - 1 / FPS, (-1.4, 6.4, gz(-1.4, 6.4) + 1.4), seer.pos_at(C1) + Vector((0, 0, 2.6)), 27),
    # B: just over the crest, looking back up at the mast over the skyline; the eye turns to us
    (C1, (3.6, -3.6, gz(3.6, -3.6) + 2.3), EYE_T - Vector((0, 0, 0.4)), 34),
    (C2 - 1 / FPS, (3.3, -3.3, gz(3.3, -3.3) + 2.3), EYE_T - Vector((0, 0, 0.3)), 40),
    # C: in the hollow, low behind Lancer A: the wave washes over it, it lights up and fires
    (C2, (18.6, -6.9, gz(18.6, -6.9) + 1.8), (1.5, 0.5, 2.2), 32),
    (C3 - 1 / FPS, (17.9, -6.6, gz(17.9, -6.6) + 1.8), (1.5, 0.5, 2.4), 35),
    # D: wide and high on the far side: the outlined ambush below, the Seer's eye and the
    # Sunfall over the crest; the suns rise over the ridge and fall on the tanks
    (C3, (27.0, -17.0, gz(27.0, -17.0) + 5.5), (1.5, -1.0, 2.6), 30),
    (C4 - 1 / FPS, (24.6, -15.4, gz(24.6, -15.4) + 5.2), (2.5, -2.5, 2.2), 33),
    # E: high over the Seer's shoulder: its eye watches the last sun land on the ambush
    (C4, (-14.0, -3.0, gz(-14.0, -3.0) + 7.0), (5.0, -1.8, 1.0), 31),
    (6.0, (-13.3, -3.2, gz(-13.3, -3.2) + 6.8), (4.5, -1.6, 1.1), 33),
]
P.camera(keys, cuts=(C1, C2, C3, C4), shake=0.015)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.35, dur=2.0)                 # lightning skirts
P.sfx(0.0, 'whirr_loop', gain=0.2, dur=1.6, rate=0.7)          # dish idling round
P.sfx(T_SWING0, 'turret_servo', gain=0.6, rate=0.8)           # dish swings to the crest
P.sfx(T_OPEN - 0.15, 'power_up_arc', gain=0.7, rate=0.85)      # the eye opens
P.sfx(T_OPEN, 'charge_gold', gain=0.5, rate=1.2)
P.sfx(T_WAVE, 'shockwave', gain=0.8, rate=1.15)                # the light wave
for _i, _a in enumerate(sorted(REV.values())):                 # each tank lights up
    P.sfx(_a, 'lock_pulse', gain=0.45, rate=1.0 + 0.07 * _i)
P.sfx(3.6, 'charge_gold', gain=0.6, rate=0.8)                  # Sunfall draws in light
for _t, _ in [(s[0], s[1]) for s in SHOTS]:
    P.sfx(_t + 0.12, 'whoosh', gain=0.5, rate=0.7)             # suns arcing overhead
for _th in T_HITS:
    P.sfx(_th, 'impact_gold', gain=0.8)

P.render()
