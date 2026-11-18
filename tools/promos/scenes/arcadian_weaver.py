"""Weaver (Arcadian repair): field surgery under fire.

A battered Aegis sits stranded on the plain, its bronze armour charred black, ember cracks
glowing, smoke rising, its own gold glow guttering. Two Terran Lancers keep shelling it. A Weaver
streaks in on its skirt of gold lightning and starts to circle the tank, its three long arms
spinning faster and faster. From the bright arm tips, threads of pale white-gold light reach out
and weave into the wounds: the char shrinks back behind a bright seam, the cracks close, the smoke
thins and the Aegis's glow comes back to full. The mended Aegis swings its turret and answers:
one heavy gold blast per Lancer. The Weaver settles at its side, arms winding down.

0-1.5   low on the wounded Aegis' flank: smoke, ember cracks, a Lancer shell slams into it; the
        Weaver darts in past camera.
1.5-3.0 orbiting medium shot: the Weaver circles, arms whirling, threads weaving into the wounds.
3.0-4.0 close on the flank: the char closes behind a bright seam; the Aegis glow surges back.
4.0-6.0 low 3/4 over the pair: the Aegis kills both Lancers; end on the pair with the wrecks
        burning beyond."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('arcadian_weaver', seconds=6.0, seed=31)
FPS = P.fps
R = P.rnd
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
THREAD = (1.0, 0.8, 0.45)        # pale white-gold repair light
EMBER = (1.0, 0.28, 0.04)

P.env('highland', sun=(58, 0, -45), clear=[(0, 0, 14), (-14, 2, 10), (14, -9, 8)], props=26)
P.flatten(0, 0, 14)
P.flatten(-14, 6, 10)
P.flatten(14, -9, 9)

T_RESTORE = 3.9        # repair complete: glow surges back
T_KILL1, T_KILL2 = 4.35, 5.25

# --------------------------------------------------------------------------- cast
aegis = P.load('aegis', at=(0, 0), heading=0, label='aegis')
aegis.split_barrels()
L1 = P.load('lancer', at=(14.0, -6.0), heading=160, label='lancer1')
L2 = P.load('lancer', at=(15.0, -12.0), heading=140, label='lancer2')
for l_ in (L1, L2):
    l_.split_barrels()
# repair unit: a touch smaller than a Lancer (4.5 m); the Aegis is 5.85 m
weaver = P.load('weaver', at=(-22, 2), heading=0, size=3.6, label='weaver')
weaver.motion['scale'] = 0.45      # keep the orbit banking gentle; no lingering tilt when it settles
HOV = 0.55
bpy.context.view_layer.update()


# --------------------------------------------------------------------------- damage patches
def surface(o, d):
    """First hit on the Aegis from point o along d (world, Aegis at origin)."""
    dg = bpy.context.evaluated_depsgraph_get()
    for _ in range(6):
        hit, loc, nrm, _i, ob, _m = bpy.context.scene.ray_cast(dg, Vector(o), Vector(d).normalized())
        if not hit:
            return None
        if ob in aegis.meshes:
            return loc, nrm
        o = loc + Vector(d).normalized() * 0.01
    return None


# (ray origin, ray dir, radius, heal start, heal end)
PATCH_RAYS = [
    ((-0.3, 6, 0.9), (0, -1, 0), 1.4, 2.6, 3.88),    # big wound on the +y flank (close-up, shot 3)
    ((1.5, 1.4, 6), (0, 0, -1), 0.85, 1.6, 3.0),      # front deck, left
    ((0.3, -0.4, 6), (0, 0, -1), 0.8, 1.9, 3.3),      # turret roof
    ((-1.9, -6, 0.9), (0, 1, 0), 1.05, 1.65, 3.15),   # far flank, rear (shot 2)
]
PATCHES = []
for o, d, r, h0, h1 in PATCH_RAYS:
    s = surface(o, d)
    if s is None:
        print('WEAVER patch miss', o)
        continue
    PATCHES.append(dict(c=s[0].copy(), n=s[1].copy(), r=r, h0=h0, h1=h1))
print('WEAVER patches', [(tuple(round(c, 2) for c in p['c']), p['r']) for p in PATCHES])


def nmath(nt, op, a, b=None, clamp=False):
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def nmix(nt, dtype, fac, a, b):
    m = nt.nodes.new('ShaderNodeMix')
    m.data_type = dtype
    suf = 'Color' if dtype == 'RGBA' else 'Float'
    ins = {s.identifier: s for s in m.inputs}
    outs = {s.identifier: s for s in m.outputs}
    for key, v in (('Factor_Float', fac), ('A_' + suf, a), ('B_' + suf, b)):
        if isinstance(v, (int, float)):
            ins[key].default_value = v
        elif isinstance(v, tuple):
            ins[key].default_value = (*v, 1.0) if len(v) == 3 else v
        else:
            nt.links.new(v, ins[key])
    return outs['Result_' + suf]


def key_value(node, keys):
    for t, v in keys:
        node.outputs[0].default_value = v
        node.outputs[0].keyframe_insert('default_value', frame=P.T(t))


def smooth01(nt, x, e0, e1):
    m = nt.nodes.new('ShaderNodeMapRange')
    m.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(x, m.inputs['Value'])
    m.inputs['From Min'].default_value = e0
    m.inputs['From Max'].default_value = e1
    return m.outputs['Result']


def damage_material(mat):
    """Wire the damage field into the Aegis' own material: char, ember cracks, a bright healing
    seam that closes in, and the unit's glow (dim and guttering until repaired)."""
    nt = mat.node_tree
    bs = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    src = {k: bs.inputs[k].links[0].from_socket for k in ('Base Color', 'Metallic', 'Roughness', 'Emission Color')}
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.object = aegis.model_root
    p = tc.outputs['Object']
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 2.2
    noise.inputs['Detail'].default_value = 6.0
    nt.links.new(p, noise.inputs['Vector'])
    nz = nmath(nt, 'SUBTRACT', noise.outputs['Fac'], 0.5)
    nz = nmath(nt, 'MULTIPLY', nz, 1.1)
    field = None
    for i, pa in enumerate(PATCHES):
        vm = nt.nodes.new('ShaderNodeVectorMath')
        vm.operation = 'DISTANCE'
        nt.links.new(p, vm.inputs[0])
        vm.inputs[1].default_value = pa['c']
        d = nmath(nt, 'DIVIDE', vm.outputs['Value'], pa['r'])
        d = nmath(nt, 'SUBTRACT', 1.0, d)
        heal = nt.nodes.new('ShaderNodeValue')
        heal.label = f'heal{i}'
        key_value(heal, [(0, 0.0), (pa['h0'], 0.0), (pa['h1'], 1.2)])
        d = nmath(nt, 'SUBTRACT', d, heal.outputs[0])
        field = d if field is None else nmath(nt, 'MAXIMUM', field, d)
    field = nmath(nt, 'ADD', field, nz)
    mask = smooth01(nt, field, 0.0, 0.05)                     # 1 = charred
    deep = smooth01(nt, field, 0.25, 0.6)                    # inner char
    # ember cracks: voronoi edges inside the deep char
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 4.0
    nt.links.new(p, vor.inputs['Vector'])
    crack = nmath(nt, 'SUBTRACT', 1.0, smooth01(nt, vor.outputs['Distance'], 0.0, 0.028))
    crack = nmath(nt, 'MULTIPLY', crack, deep)
    # bright healing seam right at the char's edge, plus a fading afterglow just behind it
    ab = nmath(nt, 'ABSOLUTE', field)
    seam = nmath(nt, 'SUBTRACT', 1.0, smooth01(nt, ab, 0.0, 0.07))
    after = nmath(nt, 'MULTIPLY', smooth01(nt, field, -0.35, 0.0), nmath(nt, 'SUBTRACT', 1.0, mask))
    active = nt.nodes.new('ShaderNodeValue')
    active.label = 'repair_active'
    t_on = min(pa['h0'] for pa in PATCHES)
    key_value(active, [(0, 0.0), (t_on - 0.05, 0.0), (t_on + 0.15, 1.0), (T_RESTORE - 0.1, 1.0), (T_RESTORE + 0.5, 0.0)])
    seam = nmath(nt, 'MULTIPLY', seam, active.outputs[0])
    after = nmath(nt, 'MULTIPLY', nmath(nt, 'MULTIPLY', after, 0.35), active.outputs[0])
    # char colour, a little mottled
    char = nmix(nt, 'RGBA', noise.outputs['Fac'], (0.012, 0.011, 0.01), (0.05, 0.04, 0.032))
    nt.links.new(nmix(nt, 'RGBA', mask, src['Base Color'], char), bs.inputs['Base Color'])
    nt.links.new(nmix(nt, 'FLOAT', mask, src['Roughness'], 0.92), bs.inputs['Roughness'])
    nt.links.new(nmix(nt, 'FLOAT', mask, src['Metallic'], 0.05), bs.inputs['Metallic'])
    # emission: own glow * glow level * (1 - char) + ember cracks + seam + afterglow
    glow = nt.nodes.new('ShaderNodeValue')
    glow.label = 'glow_level'
    gk = [(0, 1.1)]
    t = 0.12
    while t < T_RESTORE - 0.3:              # guttering
        gk.append((t, R.choice((0.35, 0.6, 1.2, 0.8, 0.25, 1.0))))
        t += R.uniform(0.08, 0.2)
    gk += [(T_RESTORE - 0.3, 1.6), (T_RESTORE, 2.6), (T_RESTORE + 0.12, 6.0), (T_RESTORE + 0.6, 4.0), (6.2, 4.0)]
    key_value(glow, gk)
    em_own = nmix(nt, 'RGBA', mask, src['Emission Color'], (0, 0, 0))
    em_own = nmix(nt, 'RGBA', 1.0, (0, 0, 0), em_own)
    vmul = nt.nodes.new('ShaderNodeVectorMath')
    vmul.operation = 'SCALE'
    nt.links.new(em_own, vmul.inputs[0])
    nt.links.new(glow.outputs[0], vmul.inputs['Scale'])
    ember_k = nt.nodes.new('ShaderNodeValue')
    ember_k.label = 'ember'
    ek = []
    t = 0.0
    while t < 6.2:
        ek.append((t, R.uniform(0.5, 1.0)))
        t += R.uniform(0.1, 0.25)
    key_value(ember_k, ek)
    e_amt = nmath(nt, 'MULTIPLY', crack, ember_k.outputs[0])
    va = nt.nodes.new('ShaderNodeVectorMath')
    va.operation = 'SCALE'
    va.inputs[0].default_value = EMBER
    nt.links.new(e_amt, va.inputs['Scale'])
    s_amt = nmath(nt, 'ADD', nmath(nt, 'MULTIPLY', seam, 2.4), after)
    vs = nt.nodes.new('ShaderNodeVectorMath')
    vs.operation = 'SCALE'
    vs.inputs[0].default_value = THREAD
    nt.links.new(s_amt, vs.inputs['Scale'])
    add1 = nt.nodes.new('ShaderNodeVectorMath')
    add1.operation = 'ADD'
    nt.links.new(vmul.outputs[0], add1.inputs[0])
    nt.links.new(va.outputs[0], add1.inputs[1])
    add2 = nt.nodes.new('ShaderNodeVectorMath')
    add2.operation = 'ADD'
    nt.links.new(add1.outputs[0], add2.inputs[0])
    nt.links.new(vs.outputs[0], add2.inputs[1])
    nt.links.new(add2.outputs[0], bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value = 1.0


for m_ in {s.material for o in aegis.meshes for s in o.material_slots if s.material}:
    damage_material(m_)

# smoke and a few flames off the wounds, dying as each is mended (smoke starts before frame 1
# so the column is already standing)
for i, pa in enumerate(PATCHES):
    if pa['n'].z < -0.2:
        continue
    top = pa['c'] + pa['n'] * 0.15
    t = -1.8 + R.uniform(0, 0.3)
    end = pa['h0'] + 0.55 * (pa['h1'] - pa['h0'])
    while t < end:
        fade = 1.0 if t < pa['h0'] else max(0.15, 1 - (t - pa['h0']) / (end - pa['h0']))
        P.puff(top, t, size=0.55 * (0.6 + 0.4 * fade), n=1, rise=2.4, life=2.0,
               color=(0.2, 0.19, 0.18), opacity=0.32 * fade)
        t += 0.2
    if i in (0, 1):
        P.fire_patch(top - pa['n'] * 0.05, 0.0, pa['h0'] + 0.35, size=0.32)

# --------------------------------------------------------------------------- the Weaver
CX, CY, RX, RY = -0.2, 0.0, 5.6, 4.9      # elliptical orbit round the Aegis
T_ARR, T_ORB1, T_SET = 1.3, 3.95, 4.9


def orbit_pt(deg):
    a = math.radians(deg)
    return (CX + RX * math.cos(a), CY + RY * math.sin(a))


A0, A1 = 165.0, 165.0 + 330.0
wkeys = [(0.0, (-22.0, 2.0)), (0.6, (-14.0, 3.0)), (0.95, (-9.0, 3.0))]
n = 12
for i in range(n + 1):
    u = i / n
    wkeys.append((T_ARR + (T_ORB1 - T_ARR) * u, orbit_pt(A0 + (A1 - A0) * u)))
wkeys += [(4.45, (-4.5, 3.9)), (T_SET, (-4.75, 4.25), -32.0), (6.0, (-4.8, 4.3), -28.0)]
weaver.path(wkeys, z=HOV)
weaver.hover_bob(0.05, 1.2)

# arms: TurretPivot spins (glTF anim: spin about up), winding up during the repair
tp = weaver.parts['TurretPivot']
tp.rotation_mode = 'XYZ'
ang = 0.0


def arm_rate(t):
    pts = [(0.0, 140.0), (1.2, 160.0), (2.1, 760.0), (3.8, 760.0), (4.8, 170.0), (6.2, 120.0)]
    for (t0, r0), (t1, r1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            return r0 + (r1 - r0) * K.smoothstep((t - t0) / (t1 - t0))
    return pts[-1][1]


for f in range(1, P.nf + 2):
    tp.rotation_euler.z = math.radians(ang)
    tp.keyframe_insert('rotation_euler', index=2, frame=f)
    ang += arm_rate((f - 1) / FPS) / FPS
for fc in K._fcurves(tp.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'

# arm tips in pivot space (the bright balls at the end of each arm)
halo = [o for o in weaver.meshes if o.name.startswith('Halo')][0]
inv = tp.matrix_world.inverted()
hpts = [inv @ (halo.matrix_world @ v.co) for v in halo.data.vertices]
TIPS = []
for a0 in (60, 180, 300):
    c = [q for q in hpts if abs(((math.degrees(math.atan2(q.y, q.x)) - a0 + 180) % 360) - 180) < 30]
    far = max(q.xy.length for q in c)
    ball = [q for q in c if q.xy.length > far - 0.35]
    TIPS.append(sum(ball, Vector()) / len(ball))
print('WEAVER tips', TIPS)

# lifter crackle: short and dense right under the round belly (Darter skirt approach)
bolt_mat = emit_mat('WeaverLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('WeaverLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)


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


def crackle(a, n_lift=9):
    rnd = P.rnd
    for f in range(1, P.nf + 2):
        objs = []
        for k in range(n_lift):
            rr = 1.05 * math.sqrt(rnd.random())
            th = rnd.uniform(0, 2 * math.pi)
            p0 = Vector((rr * math.cos(th), rr * math.sin(th), 0.05))
            if k % 3 == 0:
                p1 = p0 + Vector((rnd.uniform(-0.45, 0.45), rnd.uniform(-0.45, 0.45), -rnd.uniform(0.0, 0.08)))
            else:
                out = Vector((math.cos(th), math.sin(th), 0)) * rnd.uniform(0.08, 0.25)
                p1 = p0 + out + Vector((0, 0, -rnd.uniform(0.12, 0.26)))
            pts = jag(p0, p1, 4, 0.06, rnd)
            objs += [polyline('WLift', pts, 0.011, bolt_mat), polyline('WLiftHalo', pts, 0.04, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            o.visible_shadow = False
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('WeaverLiftLight', bpy.data.lights.new('WeaverLiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.3)
    L.data.color = GOLD
    L.data.energy = 110
    L.data.shadow_soft_size = 0.7


crackle(weaver)
P.dust(weaver, 0.0, T_SET, every=0.1, size=0.45)

# --------------------------------------------------------------------------- repair threads
th_core = emit_mat('WeaveThread', THREAD, 2.2)
th_halo = emit_mat('WeaveThreadHalo', THREAD, 0.9, alpha=0.12)
spark_mat = emit_mat('WeaveSpark', THREAD, 2.5)
sc = bpy.context.scene
cam_side = Vector((0, 1, 0))


def thread_pts(a, b, f, k, strand):
    """A woven strand from a to b: arcing curve, two strands twisting round each other."""
    d = b - a
    up = Vector((0, 0, 1))
    side = d.cross(up)
    side = side.normalized() if side.length > 1e-4 else Vector((1, 0, 0))
    up2 = side.cross(d).normalized()
    pts = []
    segs = 14
    for s in range(segs + 1):
        u = s / segs
        q = a.lerp(b, u) + up * (0.35 * math.sin(math.pi * u))
        env = math.sin(math.pi * u) ** 0.7
        ph = u * 10.0 + f * 0.9 + k * 2.1 + strand * math.pi
        q += (side * math.cos(ph) + up2 * math.sin(ph)) * 0.07 * env
        pts.append(q)
    return pts


contact_lights = []
for i in range(3):
    Lc = link(bpy.data.objects.new(f'WeaveLight{i}', bpy.data.lights.new(f'WeaveLight{i}', 'POINT')))
    Lc.data.color = THREAD
    Lc.data.shadow_soft_size = 0.4
    Lc.data.energy = 0
    Lc.data.keyframe_insert('energy', frame=1)
    contact_lights.append(Lc)

for f in range(1, P.nf + 2):
    t = (f - 1) / FPS
    live = [pa for pa in PATCHES if pa['h0'] - 0.05 <= t <= pa['h1'] - 0.1]
    sc.frame_set(f)
    tips = [tp.matrix_world @ tv for tv in TIPS]
    wc = weaver.root.matrix_world.translation
    used = []
    for pa in live:
        # the patch's current healing point wanders round its shrinking edge
        u = (t - pa['h0']) / (pa['h1'] - pa['h0'])
        n_ = pa['n']
        tang = n_.cross(Vector((0, 0, 1)))
        tang = tang.normalized() if tang.length > 1e-3 else Vector((1, 0, 0))
        bit = n_.cross(tang).normalized()
        rr = pa['r'] * 0.55 * (1 - u)
        ph = t * 9.0 + pa['r'] * 7
        tgt = pa['c'] + n_ * 0.03 + (tang * math.cos(ph) + bit * math.sin(ph)) * rr
        # only patches the Weaver can reach from where it is (not straight through the hull)
        to = (tgt - wc)
        to.z = 0
        nh = Vector((n_.x, n_.y, 0))
        if nh.length > 0.3 and nh.normalized().dot(-to.normalized()) < -0.5:
            continue
        tip = min(tips, key=lambda q: (q - tgt).length)
        k = tips.index(tip)
        used.append(tgt)
        objs = []
        for strand in (0, 1):
            pts = thread_pts(tip, tgt, f, k, strand)
            objs += [polyline('Weave', pts, 0.01, th_core), polyline('WeaveHalo', pts, 0.035, th_halo)]
        sp = K.sphere('WeaveSpark', 0.05 + 0.03 * R.random(), spark_mat, seg=(8, 6), loc=tgt)
        objs.append(sp)
        tsp = K.sphere('WeaveTipSpark', 0.07, spark_mat, seg=(8, 6), loc=tip)
        objs.append(tsp)
        for o in objs:
            o.visible_shadow = False
            show_between(o, f, f + 1)
    for i, Lc in enumerate(contact_lights):
        if i < len(used):
            Lc.location = used[i] + Vector((0, 0, 0.25))
            Lc.data.energy = 70 + 30 * R.random()
        else:
            Lc.data.energy = 0
        Lc.keyframe_insert('location', frame=f)
        Lc.data.keyframe_insert('energy', frame=f)
        for fc in K._fcurves(Lc.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
        for fc in K._fcurves(Lc.data.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
sc.frame_set(1)

# restore pulse: a soft white-gold light swell in the Aegis as the glow returns
Lr = link(bpy.data.objects.new('RestoreLight', bpy.data.lights.new('RestoreLight', 'POINT')))
Lr.location = (0, 0, 2.6)
Lr.data.color = THREAD
Lr.data.shadow_soft_size = 1.5
for t, e in [(0, 0), (T_RESTORE - 0.05, 0), (T_RESTORE + 0.1, 900), (T_RESTORE + 0.7, 0)]:
    Lr.data.energy = e
    Lr.data.keyframe_insert('energy', frame=P.T(t))

# --------------------------------------------------------------------------- the pressure
HULL_HITS = [Vector((2.7, 0.4, 0.9)), Vector((1.6, -1.2, 1.1)), Vector((2.6, -0.6, 0.9))]
L1.aim(0.25, HULL_HITS[0], dur=0.4)
L1.fire(0.35, HULL_HITS[0], kind='cannon')
L2.aim(0.9, Vector((-7.0, 1.5, 0.1)), dur=0.5)
L2.fire(1.0, Vector((-7.5, 1.2, 0.1)), kind='cannon', impact_size=0.7)   # at the incoming Weaver: misses
L1.aim(1.75, HULL_HITS[1], dur=0.5)
L1.fire(1.85, HULL_HITS[1], kind='cannon')
L2.aim(2.55, Vector((7.0, -6.0, 0.1)), dur=0.5)
L2.fire(2.65, Vector((7.0, -6.5, 0.1)), kind='cannon', impact_size=0.7)
L1.aim(3.3, HULL_HITS[2], dur=0.45)
L1.fire(3.4, HULL_HITS[2], kind='cannon')

# the mended Aegis answers: one heavy blast per Lancer
aegis.aim(T_KILL1 - 0.05, L1, dur=0.45)
aegis.fire(T_KILL1, L1, kind='lightning', size=1.6, kick=3.0)
L1.destroy(T_KILL1 + 0.05)
aegis.aim(T_KILL2 - 0.05, L2, dur=0.55)
aegis.fire(T_KILL2, L2, kind='lightning', size=1.6, kick=3.0)
L2.destroy(T_KILL2 + 0.05)
L2.aim(4.9, aegis, dur=0.5)

# --------------------------------------------------------------------------- camera
C1, C2, C3 = 36 / FPS, 72 / FPS, 96 / FPS    # cuts at 1.5, 3.0, 4.0 s
D = 1 / FPS


def look2(t):
    w = weaver.pos_at(t)
    return tuple(Vector((0, 0, 0.9)) * 1.0 + Vector((w.x, w.y, 0)) * 0.35)


P.camera([
    # shot 1: low on the wounded flank, the Lancers firing beyond; the Weaver darts in from the right
    (0.0, (-5.0, 6.8, 1.3), (1.0, 0.0, 1.0), 34),
    (0.85, (-4.6, 6.6, 1.3), (0.5, 0.1, 1.0), 34),
    (C1 - D, (-3.6, 7.3, 1.35), (-2.8, 0.6, 1.0), 33),
    # shot 2: orbiting medium shot on the far side, the Weaver circling past camera
    (C1, (-10.0, -7.0, 3.0), look2(C1), 28),
    (2.25, (-4.5, -11.0, 2.8), look2(2.25), 28),
    (C2 - D, (2.5, -11.0, 2.7), look2(C2 - D), 28),
    # shot 3: over the Weaver's arms onto the flank wound closing
    (C2, (3.4, 9.8, 3.8), (-0.3, 1.4, 0.9), 38),
    (C3 - D, (1.6, 9.4, 3.4), (-0.4, 1.4, 1.0), 40),
    # shot 4: low wide over the mended pair toward the Lancers
    (C3, (-9.0, 14.5, 5.2), (-0.6, 0.9, 0.6), 31),
    (6.0, (-7.6, 12.6, 4.1), (-0.8, 1.0, 0.7), 33),
], cuts=(C1, C2, C3), shake=0.02)
P.cam_shake(T_KILL1 + 0.05, 0.05)
P.cam_shake(T_KILL2 + 0.05, 0.05)

P.render()
