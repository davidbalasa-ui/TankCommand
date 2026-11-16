"""Star Vault (Arcadian research): dusk is going to night over the violet flats and the first stars
are out. The Vault stands in pieces held on nothing: the dome hangs over its base, four tusks
float out around it, four lanterns drift at its sides and the crown turns slowly high above.
From three far horizons the metal comes in as falling stars: streams of gold motes arc in over
the hills and drop into orbit around the Vault, a spinning ring of light like a little galaxy.
One by one the motes peel off the ring and dive into the lanterns and the crown; every hit makes
the lanterns pulse, the Vault glows brighter, its floating parts drift further apart and the
crown spins faster. Then the ring collapses into the crown in one gulp: research completes in a
crown flare, a circlet of gold light blades bursts up out of the crown, a halo ring and a ground
wave roll out, every suspended part kicks outward and settles, and a single new star is flung up
into the sky. End low under the glowing Vault, its new star twinkling over it.

Timeline (s): 0-1.6 motes streak in over the horizon (low wide) | 1.6-3.9 orbit as the ring
forms and motes dive in | 3.95-4.2 the gulp | 4.25 crown flare + new star | 4.3-6 low hero
push-in, parts settling, embers rising."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Vector, Quaternion  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_star_vault', seconds=6.0, seed=38)
FPS = P.fps
R = P.rnd

GOLD = COL['arc_gold']
DEEP = (1.0, 0.42, 0.03)
HOT = (1.0, 0.66, 0.26)

T_GULP = 3.95
T_FLARE = 4.25

P.env('dusk', sun=(76, 0, -125), sun_energy=3.2, props=34,
      clear=[(0, 0, 13), (-9, -9, 5)])
P.flatten(0, 0, 14)
bpy.context.view_layer.update()
SAND = tuple(min(1, c * 1.8) for c in P.palette['g1'])

# ------------------------------------------------------------------------- night sky with stars
w = bpy.context.scene.world
nt = w.node_tree
bg = [n for n in nt.nodes if n.type == 'BACKGROUND'][0]
ramp = [n for n in nt.nodes if n.type == 'VALTORGB'][0]
ramp.color_ramp.elements[1].color = (0.05, 0.07, 0.2, 1)
ramp.color_ramp.elements[1].position = 0.5
e = ramp.color_ramp.elements.new(0.12)
e.color = (0.55, 0.3, 0.32, 1)
ramp.color_ramp.elements[0].color = (1.0, 0.52, 0.3, 1)
bg.inputs['Strength'].default_value = 0.85
tc = [n for n in nt.nodes if n.type == 'TEX_COORD'][0]
vor = nt.nodes.new('ShaderNodeTexVoronoi')
vor.inputs['Scale'].default_value = 140
nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
mr = nt.nodes.new('ShaderNodeMapRange')
mr.inputs['From Min'].default_value = 0.0
mr.inputs['From Max'].default_value = 0.06
mr.inputs['To Min'].default_value = 1.0
mr.inputs['To Max'].default_value = 0.0
nt.links.new(vor.outputs['Distance'], mr.inputs['Value'])
sepz = [n for n in nt.nodes if n.type == 'SEPXYZ'][0]
zm = nt.nodes.new('ShaderNodeMapRange')
zm.inputs['From Min'].default_value = 0.08
zm.inputs['From Max'].default_value = 0.35
nt.links.new(sepz.outputs['Z'], zm.inputs['Value'])
mul = nt.nodes.new('ShaderNodeMath')
mul.operation = 'MULTIPLY'
nt.links.new(mr.outputs[0], mul.inputs[0])
nt.links.new(zm.outputs[0], mul.inputs[1])
pw = nt.nodes.new('ShaderNodeMath')
pw.operation = 'POWER'
pw.inputs[1].default_value = 3.0
nt.links.new(mul.outputs[0], pw.inputs[0])
sc_ = nt.nodes.new('ShaderNodeMath')
sc_.operation = 'MULTIPLY'
sc_.inputs[1].default_value = 1.6
nt.links.new(pw.outputs[0], sc_.inputs[0])
add = nt.nodes.new('ShaderNodeMix')
add.data_type = 'RGBA'
add.blend_type = 'ADD'
add.inputs['Factor'].default_value = 1.0
nt.links.new(ramp.outputs['Color'], add.inputs['A'])
star_col = nt.nodes.new('ShaderNodeCombineColor')
nt.links.new(sc_.outputs[0], star_col.inputs[0])
nt.links.new(sc_.outputs[0], star_col.inputs[1])
nt.links.new(sc_.outputs[0], star_col.inputs[2])
nt.links.new(star_col.outputs[0], add.inputs['B'])
nt.links.new(add.outputs['Result'], bg.inputs['Color'])


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('SV_' + key, col, strength, alpha=alpha)
    return _mats[key]


M_BOLT = mat('Bolt', GOLD, 2.2)
M_CORE = mat('BoltCore', (1.0, 0.7, 0.3), 2.6)
M_GLOW = mat('BoltGlow', DEEP, 1.0, alpha=0.2)


def jag_pts(p0, p1, segs, jag):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
        pts.append(p0 + d * u + off)
    return pts


def bolt_frame(pts, f, width, glow=True, core=True, nframes=1):
    objs = [K.polyline('Bolt', pts, width, M_BOLT)]
    if core:
        objs.append(K.polyline('BoltCore', pts, width * 0.4, M_CORE))
    if glow:
        objs.append(K.polyline('BoltGlow', pts, width * 3.0, M_GLOW))
    for o in objs:
        o.visible_shadow = False
        K.show_between(o, f, f + nframes)
    return objs


def gold_sparks(pos, t, size=1.0, n=8, life=0.3):
    m = mat('Spark', GOLD, 2.4)
    f0 = P.T(t)
    for i in range(n):
        sp = K.sphere('Spk', 1.0, m, seg=(6, 4))
        sp.visible_shadow = False
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.3, 1.2))).normalized() * size * 3.0
        sp.scale = (0.12 * size, 0.025 * size, 0.025 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * life + Vector((0, 0, -0.1))
        sp.keyframe_insert('location', frame=f0 + life * FPS)
        K.show_between(sp, f0, f0 + life * FPS)


def add_light(name, loc, col, keys, radius=0.4, parent=None):
    L = K.link(bpy.data.objects.new(name, bpy.data.lights.new(name, 'POINT')))
    L.location = loc
    if parent is not None:
        L.parent = parent
    L.data.color = col
    L.data.shadow_soft_size = radius
    for t, en in keys:
        L.data.energy = en
        L.data.keyframe_insert('energy', frame=P.T(t))
    return L


def bbox_objs(objs):
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        mw = o.matrix_world
        if o.type == 'MESH':
            pts = [mw @ v.co for v in o.data.vertices]
        else:
            pts = [mw @ Vector(c) for c in o.bound_box]
        for p in pts:
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


# ------------------------------------------------------------------------- the Vault, in pieces
vault = P.load('star_vault', at=(0, 0), heading=0, label='vault')
bpy.context.view_layer.update()
hull = vault.parts['Hull']
crown_piv = vault.parts['CrownPivot']
crown_mesh = vault.parts['Crown']
for o in bpy.context.view_layer.objects:
    o.select_set(False)
bpy.context.view_layer.objects.active = hull
hull.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='LOOSE')
bpy.ops.object.mode_set(mode='OBJECT')
pieces = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Hull')]
bpy.context.view_layer.update()
groups = {}
for o in pieces:
    lo, hi = bbox_objs([o])
    c = (lo + hi) / 2
    ext = hi - lo
    r = math.hypot(c.x, c.y)
    ang = math.degrees(math.atan2(c.y, c.x)) % 360
    if ext.z > 1.0 and max(ext.x, ext.y) < 0.4:
        o.hide_render = True        # a thin mast that would cross every floating gap
        continue
    if ext.z > 1.4 and r > 0.6 and max(ext.x, ext.y) > 0.5:
        g = 'tusk%d' % int(ang // 90)
    elif c.z < 0.45:
        g = 'base'
    elif c.z < 1.1 and r > 1.65:
        g = 'lant%d' % int(((ang + 45) % 360) // 90)
    elif c.z >= 1.95 and r < 0.9:
        g = 'cap'
    else:
        g = 'dome'
    groups.setdefault(g, []).append(o)
print('GROUPS', {k: len(v) for k, v in groups.items()})

vmat = bpy.data.materials['KeshGeneVaultMat']
lmat = vmat.copy()
lmat.name = 'VaultLanternMat'
G = {}
for g, objs in groups.items():
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = 'V_' + g
    if g.startswith('lant'):
        ob.data.materials[0] = lmat
    G[g] = ob
bpy.context.view_layer.update()

# floating rigs: one world-space empty per group, pivot where it makes sense
GEO = {}
RIG = {}
for g, ob in G.items():
    if g == 'base':
        continue
    lo, hi = bbox_objs([ob])
    GEO[g] = (lo, hi)
    if g.startswith('tusk'):
        piv = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    elif g.startswith('lant'):
        piv = (lo + hi) / 2
    else:
        piv = Vector((0, 0, lo.z))
    em = K.empty('Rig_' + g, piv)
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = em
    ob.matrix_world = mw
    RIG[g] = (em, piv.copy())
print('GEO', {k: (tuple(round(x, 2) for x in v[0]), tuple(round(x, 2) for x in v[1])) for k, v in GEO.items()})

# crown: its own world rig (spin + float)
clo, chi = bbox_objs([crown_mesh])
CROWN_C0 = (clo + chi) / 2
CROWN_R = (chi.x - clo.x) / 2
crown_rig = K.empty('Rig_crown', Vector((0, 0, CROWN_C0.z)))
bpy.context.view_layer.update()
mw = crown_piv.matrix_world.copy()
crown_piv.parent = crown_rig
crown_piv.matrix_world = mw
crown_rig.rotation_mode = 'XYZ'
print('CROWN', CROWN_C0, CROWN_R)


# power level drives every gap: dormant 0.55 -> charged 1 -> flare kick -> settle
def level(t):
    lv = 0.55 + 0.45 * ss((t - 0.8) / 3.0)
    if t > T_GULP:
        lv += 0.12 * ss((t - T_GULP) / 0.3)
    if t > T_FLARE:
        k = t - T_FLARE
        lv += 0.75 * math.exp(-k * 4.5) * (1 - math.exp(-k * 40)) - 0.12 * ss(k / 0.4)
    return lv


SPEC = {}   # g -> (dir xyz at full, bob amp, bob hz, phase, tilt deg)
for i in range(4):
    a = math.radians(i * 90 + 45)
    SPEC['tusk%d' % i] = (Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.42)), 0.045, 0.55, i * 1.7, 7.0)
    a = math.radians(i * 90)
    SPEC['lant%d' % i] = (Vector((math.cos(a) * 0.42, math.sin(a) * 0.42, 0.24)), 0.06, 0.8, i * 2.3 + 0.5, 0.0)
SPEC['dome'] = (Vector((0, 0, 0.34)), 0.025, 0.5, 0.3, 0.0)
SPEC['cap'] = (Vector((0, 0, 0.55)), 0.035, 0.65, 1.1, 0.0)
CROWN_LIFT = 0.85


def rig_off(g, t):
    d, amp, hz, ph, tilt = SPEC[g]
    return d * level(t) + Vector((0, 0, amp * math.sin(2 * math.pi * hz * t + ph)))


def crown_center(t):
    return CROWN_C0 + Vector((0, 0, CROWN_LIFT * level(t) + 0.06 * math.sin(2 * math.pi * 0.45 * t + 2.0)))


def lantern_center(i, t):
    g = 'lant%d' % i
    return RIG[g][1] + rig_off(g, t)


t = -0.1
while t <= 6.15:
    f = P.T(t)
    for g, (em, piv) in RIG.items():
        em.location = piv + rig_off(g, t)
        em.keyframe_insert('location', frame=f)
        tilt = SPEC[g][4]
        if tilt:
            a = math.radians(int(g[4]) * 90 + 45)
            k = math.radians(tilt) * level(t)
            # lean outward: rotate about the horizontal axis perpendicular to the radial direction
            em.rotation_mode = 'XYZ'
            em.rotation_euler = (-math.sin(a) * k, math.cos(a) * k, 0)
            em.keyframe_insert('rotation_euler', frame=f)
    crown_rig.location = Vector((0, 0, crown_center(t).z))
    crown_rig.keyframe_insert('location', frame=f)
    t += 1 / FPS
for em, _ in RIG.values():
    K.set_interp(em, 'LINEAR')
K.set_interp(crown_rig, 'LINEAR')

# cap petals counter-rotate slowly
cap_em = RIG['cap'][0]
cap_em.rotation_mode = 'XYZ'
for t, deg in [(0, 0), (6.2, -110)]:
    cap_em.rotation_euler.z = math.radians(deg)
    cap_em.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
for fc in K._fcurves(cap_em.animation_data.action):
    if fc.data_path == 'rotation_euler':
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


# crown spin speed (deg/s): slow, winding up with the charge, screaming at the gulp, then calm
def crown_rate(t):
    r = 45 + 260 * ss((t - 1.2) / 2.6)
    if t > T_GULP - 0.2:
        r += 380 * ss((t - T_GULP + 0.2) / 0.45)
    if t > T_FLARE:
        r = 70 + (r - 70) * math.exp(-(t - T_FLARE) * 2.2)
    return r


ang = 0.0
t = 0.0
dt = 1 / FPS
crown_rig.rotation_euler.z = 0
crown_rig.keyframe_insert('rotation_euler', index=2, frame=P.T(-0.05))
while t <= 6.15:
    crown_rig.rotation_euler.z = math.radians(ang)
    crown_rig.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
    ang += crown_rate(t) * dt
    t += dt
for fc in K._fcurves(crown_rig.animation_data.action):
    if fc.data_path == 'rotation_euler':
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# ------------------------------------------------------------------------- motes: falling stars
M_MOTE = mat('Mote', HOT, 2.6)
M_MOTEG = mat('MoteGlow', GOLD, 1.3, alpha=0.28)
RING_R0, RING_R1 = 3.9, 2.9
RING_Z = 3.15
RING_TILT = math.radians(13)
OMEGA = math.radians(250)


def ring_pt(theta, r, t):
    # inclined ring plane (tilted about the x axis), slow wobble
    z = RING_Z + r * math.sin(RING_TILT) * math.sin(theta) + 0.08 * math.sin(3 * theta + t)
    return Vector((r * math.cos(theta), r * math.sin(theta) * math.cos(RING_TILT), z))


def bez3(a, b, c, d, u):
    v = 1 - u
    return a * v ** 3 + b * 3 * v * v * u + c * 3 * v * u * u + d * u ** 3


STREAMS = [  # azimuth of the far source (deg), distance, launch window
    (58, 75, (-1.3, 2.55)),
    (165, 70, (-0.9, 2.65)),
    (290, 72, (-0.5, 2.7)),
]
motes = []
for si, (az, dist, (w0, w1)) in enumerate(STREAMS):
    n = 34
    for k in range(n):
        t0 = w0 + (w1 - w0) * (k + R.uniform(-0.3, 0.3)) / n
        a = math.radians(az + R.uniform(-7, 7))
        S = Vector((math.cos(a) * dist, math.sin(a) * dist, R.uniform(2.0, 6.0)))
        th_in = math.radians(az + 100 + R.uniform(-25, 25))       # enter the ring off to one side
        fly = R.uniform(1.15, 1.5)
        orbit = R.uniform(0.35, 1.25)
        tgt = 'crown' if R.random() < 0.38 else 'lant%d' % R.randint(0, 3)
        motes.append(dict(t0=t0, S=S, th=th_in, fly=fly, orbit=orbit, tgt=tgt, si=si,
                          size=R.uniform(0.75, 1.15), apex=R.uniform(9, 16)))


def ring_r(tt, te):
    return RING_R0 + (RING_R1 - RING_R0) * ss((tt - te) / 1.4)


def build_path(m):
    """returns (t_end, pos(t) function, target)"""
    te = m['t0'] + m['fly']
    td = te + m['orbit']
    tgt = m['tgt']
    if td + 0.28 > T_GULP:           # still orbiting at the gulp: everyone dives into the crown
        td = T_GULP + R.uniform(0.0, 0.16)
        tgt = 'crown'
        if td < te + 0.15:
            te = td - 0.15
    ddur = 0.26 if tgt == 'crown' else 0.3
    E = ring_pt(m['th'], RING_R0, te)
    tan = (ring_pt(m['th'] + 0.01, RING_R0, te) - ring_pt(m['th'] - 0.01, RING_R0, te)).normalized()
    S = m['S']
    C1 = S + (Vector((0, 0, m['apex'])) + (E - S) * 0.3)
    C2 = E - tan * 6.0 + Vector((0, 0, 2.0))

    def pos(t):
        if t <= te:
            u = (t - m['t0']) / (te - m['t0'])
            u = max(0.0, u)
            # ease-in on arrival so motes brake into the ring
            uu = 1 - (1 - u) ** 1.6
            return bez3(S, C1, C2, E, uu)
        th = m['th'] + OMEGA * (min(t, td) - te)
        if t <= td:
            return ring_pt(th, ring_r(t, te), t)
        O = ring_pt(th, ring_r(td, te), td)
        tn = (ring_pt(th + 0.02, ring_r(td, te), td) - O).normalized()
        u = min(1.0, (t - td) / ddur)
        if tgt == 'crown':
            T = crown_center(t)
        else:
            T = lantern_center(int(tgt[4]), t)
        return bez3(O, O + tn * 1.2, T + Vector((0, 0, 0.9 if tgt == 'crown' else 0.6)), T, u ** 1.3)
    return td + ddur, pos, tgt


hits = []      # (time, target)
for m in motes:
    t_end, pos, tgt = build_path(m)
    m['t_end'], m['tgt'] = t_end, tgt
    hits.append((t_end, tgt))
    f0 = max(1, int(math.floor(P.T(max(m['t0'], 0.0)))))
    f1 = int(math.ceil(P.T(t_end)))
    if f1 < 1:
        continue
    core = K.sphere('Mote', 1.0, M_MOTE, seg=(8, 6))
    glow = K.sphere('MoteGlow', 1.0, M_MOTEG, seg=(10, 6))
    for o in (core, glow):
        o.visible_shadow = False
        o.rotation_mode = 'QUATERNION'
    sz = m['size']
    for f in range(f0, f1 + 1):
        t = (f - 1) / FPS
        p = pos(min(t, t_end))
        v = (pos(min(t + 0.02, t_end)) - pos(max(t - 0.02, m['t0']))) / 0.04
        sp = v.length
        q = v.to_track_quat('X', 'Z') if sp > 0.1 else Quaternion()
        L = 0.05 + min(0.9, sp * 0.02)
        # far motes are drawn a little bigger so they read at phone size
        dcam = 1.0 + 0.008 * p.length
        for o, wdt, ln in ((core, 0.026, L), (glow, 0.075, L * 1.15)):
            o.location = p - v.normalized() * ln * 0.5 if sp > 0.1 else p
            o.rotation_quaternion = q
            o.scale = (ln * sz, wdt * sz * dcam, wdt * sz * dcam)
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('rotation_quaternion', frame=f)
            o.keyframe_insert('scale', frame=f)
    for o in (core, glow):
        K.set_interp(o, 'LINEAR')
        K.show_between(o, f0, f1)
hits.sort()
print('motes', len(motes), 'hits by target', {g: sum(1 for h in hits if h[1] == g) for g in set(h[1] for h in hits)})

# faint ring of light along the orbit, brightening as it fills
M_RING = mat('OrbitRing', GOLD, 0.0, alpha=0.18)
ring_objs = []
for rr, wd in ((3.5, 0.05), (3.15, 0.03)):
    pts = [ring_pt(2 * math.pi * i / 96, rr, 0) for i in range(97)]
    ro = K.polyline('OrbitRing', pts, wd, M_RING)
    ro.visible_shadow = False
    ring_objs.append(ro)
for t, v in [(0, 0.0), (1.0, 0.0), (2.0, 0.6), (3.0, 1.1), (T_GULP, 1.4), (T_GULP + 0.2, 0.4), (T_FLARE, 0.0)]:
    K.key_strength(M_RING, P.T(t), v)


# ------------------------------------------------------------------------- the Vault drinks
def absorbed(t):
    return sum(1 for h in hits if h[0] <= t)


NH = len(hits)
vb = vmat.node_tree.nodes.get('Principled BSDF')
lb = lmat.node_tree.nodes.get('Principled BSDF')
t = 0.0
while t <= 6.1:
    fr = absorbed(t) / NH
    base = 1.3 + 2.4 * fr
    if t > T_FLARE:
        k = t - T_FLARE
        base = 3.9 + 2.2 * math.exp(-k * 3.0)
    vb.inputs['Emission Strength'].default_value = base
    vb.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))
    t += 0.125
# lanterns: pulse on every lantern hit
lv = {}
for th, g in hits:
    if g.startswith('lant'):
        lv[round(th * FPS)] = 1
t = 0.0
lan_keys = []
while t <= 6.1:
    fr = absorbed(t) / NH
    v = 1.5 + 2.2 * fr
    recent = [th for th, g in hits if g.startswith('lant') and 0 <= t - th < 0.25]
    if recent:
        v += 1.6 * max(1 - (t - th) / 0.25 for th in recent)
    if t > T_FLARE:
        v = 4.2 + 2.0 * math.exp(-(t - T_FLARE) * 3.0)
    lb.inputs['Emission Strength'].default_value = v
    lb.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))
    t += 1 / FPS

# lights inside the lanterns and under the dome, growing with the charge
for i in range(4):
    em = RIG['lant%d' % i][0]
    keys = []
    for t in [x * 0.25 for x in range(25)]:
        e_ = 25 + 140 * absorbed(t) / NH
        if t > T_FLARE:
            e_ = 190
        keys.append((t, e_))
    add_light('LanternLight%d' % i, (0, 0, 0), GOLD, keys, radius=0.25, parent=em)
dome_em = RIG['dome'][0]
add_light('UnderDome', (0, 0, 0.08), GOLD,
          [(t, 30 + 260 * absorbed(t) / NH if t < T_FLARE else 320) for t in [x * 0.25 for x in range(25)]],
          radius=1.2, parent=dome_em)

# a small spark at each hit
for th, g in hits:
    if th < 0 or th > 6:
        continue
    p = crown_center(th) if g == 'crown' else lantern_center(int(g[4]), th)
    if R.random() < 0.5:
        gold_sparks(p, th, size=0.22, n=4, life=0.22)

# ------------------------------------------------------------------------- arcs in the gaps
dome_lo = GEO['dome'][0].z
foot = {}
for i in range(4):
    g = 'tusk%d' % i
    foot[g] = RIG[g][1]
t = 0.3
while t < 6.0:
    f = int(round(P.T(t)))
    charge = 0.25 + 0.6 * absorbed(t) / NH
    if T_GULP - 0.1 < t < T_FLARE + 0.6:
        charge = 1.0
    if R.random() < charge:
        kind = R.random()
        if kind < 0.4:
            i = R.randint(0, 3)
            g = 'tusk%d' % i
            top = foot[g] + rig_off(g, t) + Vector((0, 0, 0.02))
            a = math.radians(i * 90 + 45)
            bot = Vector((math.cos(a) * 1.9, math.sin(a) * 1.9, 0.42))
            bolt_frame(jag_pts(bot, top, 5, 0.5), f, 0.012, glow=False, nframes=2)
        elif kind < 0.75:
            a = R.uniform(0, 2 * math.pi)
            rr = R.uniform(1.4, 1.75)
            p0 = Vector((math.cos(a) * rr, math.sin(a) * rr, 0.55))
            p1 = Vector((math.cos(a + R.uniform(-.3, .3)) * rr, math.sin(a + R.uniform(-.3, .3)) * rr,
                         dome_lo + rig_off('dome', t).z + 0.04))
            bolt_frame(jag_pts(p0, p1, 4, 0.6), f, 0.011, glow=False, nframes=2)
        else:
            cc = crown_center(t)
            a = R.uniform(0, 2 * math.pi)
            p0 = Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, GEO['cap'][1].z + rig_off('cap', t).z - 0.05))
            p1 = cc + Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, -0.25))
            bolt_frame(jag_pts(p0, p1, 5, 0.5), f, 0.013, glow=False, nframes=2)
    t += 2 / FPS

# ------------------------------------------------------------------------- the crown flare
FC = crown_center(T_FLARE)
P.light(FC + Vector((0, 0, 0.4)), T_FLARE, HOT, energy=9000, dur=0.35, radius=0.8)
add_light('CrownGlow', (0, 0, 0.0), GOLD,
          [(0, 60), (2.0, 120), (T_GULP, 400), (T_FLARE, 900), (T_FLARE + 0.6, 450), (6.1, 420)],
          radius=0.5, parent=crown_rig)
P.cam_shake(T_FLARE, 0.035, 0.35)

# circlet of light blades bursting up out of the crown
M_BLADE = mat('Blade', (1.0, 0.56, 0.12), 2.4)
M_BLADEG = mat('BladeGlow', GOLD, 1.2, alpha=0.22)


def cone_mesh(name, r0, mat_):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r0, radius2=0.0, depth=1.0)
    for v in bm.verts:
        v.co.z += 0.5
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat_)
    return me


blade_me = cone_mesh('Blade', 0.06, M_BLADE)
bladeg_me = cone_mesh('BladeG', 0.17, M_BLADEG)
halo = K.empty('Halo', (0, 0, 0))
halo.parent = crown_rig
NB = 12
for i in range(NB):
    a = 2 * math.pi * i / NB
    Lb = 2.3 if i % 2 == 0 else 1.35
    for me in (blade_me, bladeg_me):
        b = K.link(bpy.data.objects.new('CrownBlade', me))
        b.visible_shadow = False
        b.parent = halo
        b.location = (math.cos(a) * CROWN_R * 0.95, math.sin(a) * CROWN_R * 0.95, 0.05)
        b.rotation_mode = 'XYZ'
        lean = math.radians(22)
        b.rotation_euler = (-math.sin(a) * lean, math.cos(a) * lean, 0)
        f0 = P.T(T_FLARE - 0.02 + 0.012 * (i % 3))
        for fr, sz in [(f0, 0.02), (f0 + 0.12 * FPS, 1.15), (f0 + 0.35 * FPS, 1.0), (P.T(5.0), 0.8),
                       (P.T(6.1), 0.62)]:
            b.scale = (1, 1, Lb * sz)
            b.keyframe_insert('scale', frame=fr)
        K.show_between(b, f0, P.nf + 5)
for t, v in [(T_FLARE, 3.0), (T_FLARE + 0.3, 2.4), (5.0, 1.8), (6.0, 1.6)]:
    K.key_strength(M_BLADE, P.T(t), v)
for t, v in [(T_FLARE, 1.6), (T_FLARE + 0.4, 1.0), (6.0, 0.7)]:
    K.key_strength(M_BLADEG, P.T(t), v)


def ring_obj(name, rad, mat_, n=72):
    pts = [Vector((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0)) for i in range(n + 1)]
    o = K.polyline(name, pts, rad, mat_)
    o.visible_shadow = False
    return o


def grow_ring(o, t0, t1, s0, s1, width):
    f = int(math.floor(P.T(t0)))
    while f <= P.T(t1) + 1:
        u = max(0.0, min(1.0, ((f - 1) / FPS - t0) / (t1 - t0)))
        s = s0 + (s1 - s0) * (1 - (1 - u) ** 2)
        o.scale = (s, s, 1)
        o.keyframe_insert('scale', frame=f)
        o.data.bevel_depth = width / s
        o.data.keyframe_insert('bevel_depth', frame=f)
        f += 1


# halo ring rolling out level with the crown
M_HRING = mat('HaloRing', GOLD, 1.8, alpha=0.6)
hr = ring_obj('HaloRing', 0.05, M_HRING)
hr.location = FC
grow_ring(hr, T_FLARE, T_FLARE + 0.8, 0.8, 14, 0.05)
K.show_between(hr, P.T(T_FLARE), P.T(T_FLARE + 0.8))
for t, v in [(T_FLARE, 1.9), (T_FLARE + 0.45, 1.0), (T_FLARE + 0.8, 0.0)]:
    K.key_strength(M_HRING, P.T(t), v)
# the ground wave
M_GRING = mat('GroundRing', GOLD, 2.0, alpha=0.6)
gr = ring_obj('GroundRing', 0.09, M_GRING)
gr.location = (0, 0, 0.08)
grow_ring(gr, T_FLARE + 0.04, T_FLARE + 1.0, 2.6, 17, 0.08)
K.show_between(gr, P.T(T_FLARE + 0.04), P.T(T_FLARE + 1.0))
for t, v in [(T_FLARE, 1.8), (T_FLARE + 0.6, 0.9), (T_FLARE + 1.0, 0.0)]:
    K.key_strength(M_GRING, P.T(t), v)
for k in range(26):
    a = 2 * math.pi * k / 26 + R.uniform(-0.1, 0.1)
    for rr, dt_ in ((4.5, 0.12), (8.0, 0.32)):
        p = Vector((math.cos(a) * rr, math.sin(a) * rr, 0.2))
        P.puff(p, T_FLARE + dt_ + R.uniform(0, 0.05), size=0.65, n=1, rise=0.35, life=1.0, color=SAND,
               opacity=0.18)
gold_sparks(FC, T_FLARE, size=0.7, n=14, life=0.35)

# the new star: flung up out of the crown, it hangs in the sky and twinkles
CAM_END, LOOK_END = Vector((9.0, 2.9, 0.8)), Vector((-0.2, 0.8, 2.6))
_fw = (LOOK_END - CAM_END).normalized()
_rt = _fw.cross(Vector((0, 0, 1))).normalized()
_up = _rt.cross(_fw).normalized()
STAR_END = CAM_END + (_fw - _rt * 0.34 + _up * 0.25).normalized() * 40
star = K.empty('NewStarRig')
st_core = K.sphere('NewStar', 0.12, mat('Star', (1.0, 0.75, 0.4), 2.8), seg=(10, 8))
st_glow = K.sphere('NewStarGlow', 0.26, mat('StarGlow', GOLD, 1.2, alpha=0.18), seg=(10, 8))
M_SPIKE = mat('StarSpike', HOT, 2.4)
spikes = []
for ax, ln in ((_rt, 0.95), (_up, 1.25), ((_rt + _up).normalized(), 0.4), ((_rt - _up).normalized(), 0.4)):
    sp = K.sphere('StarSpike', 1.0, M_SPIKE, seg=(8, 6))
    sp.rotation_mode = 'QUATERNION'
    sp.rotation_quaternion = ax.to_track_quat('X', 'Z')
    sp.scale = (ln, 0.018, 0.018)
    spikes.append(sp)
for o in [st_core, st_glow] + spikes:
    o.visible_shadow = False
    o.parent = star
T_S0, T_S1 = T_FLARE + 0.05, T_FLARE + 0.75
f = P.T(T_S0)
while f <= P.nf + 2:
    t = (f - 1) / FPS
    u = ss((t - T_S0) / (T_S1 - T_S0))
    uu = 1 - (1 - min(1, (t - T_S0) / (T_S1 - T_S0))) ** 2.2
    star.location = bez3(FC, FC + Vector((0, 0, 9)), STAR_END + Vector((2, -3, -3)), STAR_END, uu)
    tw = 1.0 + (0.3 * math.sin(t * 19) + 0.18 * math.sin(t * 31)) * u
    star.scale = (tw * (1 + 2.6 * uu),) * 3
    star.keyframe_insert('location', frame=f)
    star.keyframe_insert('scale', frame=f)
    f += 1
for sp in spikes:
    s0 = sp.scale.copy()
    for t, k in [(T_S0, 0.15), (T_S1 - 0.1, 0.3), (T_S1 + 0.1, 1.0)]:
        sp.scale = (s0.x * k, s0.y, s0.z)
        sp.keyframe_insert('scale', frame=P.T(t))
K.show_between(star, P.T(T_S0), P.nf + 5)
# its trail
st_pts = [bez3(FC, FC + Vector((0, 0, 9)), STAR_END + Vector((2, -3, -3)), STAR_END, i / 40) for i in range(41)]
M_STRAIL = mat('StarTrail', GOLD, 2.0, alpha=0.5)
trail = K.polyline('StarTrail', st_pts, 0.04, M_STRAIL)
trail.visible_shadow = False
trail.data.bevel_factor_mapping_start = 'SPLINE'
trail.data.bevel_factor_mapping_end = 'SPLINE'
for t, s0, s1 in [(T_S0, 0.0, 0.0), (T_S0 + 0.3, 0.05, 0.62), (T_S1, 0.6, 1.0), (T_S1 + 0.5, 1.0, 1.0)]:
    trail.data.bevel_factor_start = s0
    trail.data.bevel_factor_end = s1
    trail.data.keyframe_insert('bevel_factor_start', frame=P.T(t))
    trail.data.keyframe_insert('bevel_factor_end', frame=P.T(t))
K.show_between(trail, P.T(T_S0), P.T(T_S1 + 0.5))

# embers drifting up off the crown after the flare
M_EMB = mat('Ember', HOT, 2.2)
for k in range(22):
    o = K.sphere('Ember', 1.0, M_EMB, seg=(6, 4))
    o.visible_shadow = False
    t0 = T_FLARE + 0.1 + R.uniform(0, 1.3)
    a0 = R.uniform(0, 2 * math.pi)
    r0 = R.uniform(0.4, 1.4)
    life = R.uniform(0.9, 1.6)
    f0 = P.T(t0)
    for j in range(7):
        u = j / 6
        t = t0 + life * u
        c = crown_center(t)
        a = a0 + u * 2.0
        rr = r0 * (1 + u * 0.8)
        o.location = (c.x + math.cos(a) * rr, c.y + math.sin(a) * rr, c.z - 0.3 + u * 2.4)
        s = 0.035 * (1 - u) + 0.004
        o.scale = (s,) * 3
        o.keyframe_insert('location', frame=P.T(t))
        o.keyframe_insert('scale', frame=P.T(t))
    K.show_between(o, f0, P.T(t0 + life))

# ------------------------------------------------------------------------- camera
# Low wide on the horizon as the first stars fall in, then a rising orbit round the Vault while
# the ring forms, a lift for the flare and a low hero push-in to end.
keys = []
keys.append((0.0, (-6.3, -7.3, 0.7), (2.6, 5.2, 4.1), 24))
keys.append((0.8, (-6.6, -6.4, 0.9), (1.6, 3.4, 3.5), 25))
keys.append((1.6, (-8.1, -5.3, 1.3), (0.4, 1.2, 2.9), 24))
for i in range(1, 9):
    u = i / 8
    t = 1.6 + (3.75 - 1.6) * u
    a = math.radians(213 + 150 * u)
    rr = 10.6 - 2.0 * ss(u)
    h = 1.35 + 3.0 * math.sin(math.pi * min(1, u * 1.1)) * 0.85
    keys.append((t, (rr * math.cos(a), rr * math.sin(a), h), (0, 0, 2.5 + 0.3 * u), 23))
keys.append((T_FLARE + 0.05, (9.4, 5.0, 1.25), (0, 0, 2.9), 21))
keys.append((5.0, (9.4, 3.9, 0.95), (0, 0.6, 2.8), 23))
keys.append((6.0, tuple(CAM_END), tuple(LOOK_END), 27))
P.camera(keys, shake=0.01)

P.render()
