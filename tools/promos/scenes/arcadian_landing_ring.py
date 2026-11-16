"""Landing Ring (Arcadian logistics structure / Kesh nest): the ring comes down out of a dusk sky
as a closed golden bud, its petals folded up round the heart and the halo clasped round their tips,
walking down on legs of gold lightning. It settles in a ring of dust and blooms: the halo floats
up off the tips, the petals swing open one after another and hang free over the rim on crackling
arcs, the crown lifts and both begin to turn. A bolt from the sky lights a column of gold light
down through the halo onto the heart, and the deliveries start, strictly one at a time: a Lumen
sinks down the column wrapped in sliding light rings, couples to the crown, glides out over the
mouth and takes up guard; only then does the Darter drop in and dart away; then the Ferrier.
No ships, no cockpits: units ride the light and hover on gold-lightning lifters.

Timeline (s): 0-1.4 descent on lightning legs | 1.4 touchdown, dust | 1.5-2.3 bloom, halo lifts,
crown spins up | 2.0 sky bolt, column of light | 2.2/3.35/4.45 deliveries (Lumen, Darter, Ferrier)
| end low at the mouth: Ferrier gliding out at the camera, Lumen on guard, column blazing."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('arcadian_landing_ring', seconds=6.0, seed=17)
FPS = P.fps
NF = P.nf
R = P.rnd
P.env('dusk', sun=(68, 0, -35), sun_energy=4.5, props=34,
      clear=[(0, 0, 16), (12, -6, 8), (18, 6, 8)])
P.flatten(0, 0, 13)
P.flatten(12, -4, 7)

GOLD = COL['arc_gold']
DUST = (0.62, 0.48, 0.38)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- materials
M_BOLT = K.emit_mat('LrBolt', GOLD, 2.8)
M_CORE = K.emit_mat('LrBoltCore', (1.0, 0.7, 0.28), 3.0)
M_GLOW = K.emit_mat('LrBoltGlow', (1.0, 0.45, 0.04), 1.2, alpha=0.25)
M_SPARK = K.emit_mat('LrSpark', (1.0, 0.62, 0.2), 3.0)


def soft_emit(name, col, strength, power=2.0, blend=0.5):
    """Emission that fades to transparent toward the silhouette (a soft volume of light)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = blend
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = power
    pw.use_clamp = True
    nt.links.new(inv.outputs[0], pw.inputs[0])
    gain = nt.nodes.new('ShaderNodeMath')
    gain.operation = 'MULTIPLY'
    gain.use_clamp = True
    gain.inputs[1].default_value = 1.0
    nt.links.new(pw.outputs[0], gain.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*col, 1)
    em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(gain.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    m['gain_node'] = gain.name
    return m


def key_gain(m, t, v):
    g = m.node_tree.nodes[m['gain_node']]
    g.inputs[1].default_value = v
    g.inputs[1].keyframe_insert('default_value', frame=P.T(t))


# ------------------------------------------------------------------------------- lightning
def jag_pts(p0, p1, segs, jag, ctrl=None):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        base = p0 * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + p1 * u * u if ctrl is not None else p0 + d * u
        env = math.sin(math.pi * u)
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * env if 0 < i < segs else Vector()
        pts.append(base + off)
    return pts


def bolt_frame(pts, f, width, parent=None, glow=True, forks=1, core=True, nf=1):
    objs = [K.polyline('Bolt', pts, width, M_BOLT)]
    if core:
        objs.append(K.polyline('BoltCore', pts, width * 0.4, M_CORE))
    if glow:
        objs.append(K.polyline('BoltGlow', pts, width * 3.0, M_GLOW))
    n = len(pts) - 1
    for _ in range(forks):
        if n < 4:
            break
        k = R.randint(2, n - 2)
        a = pts[k]
        dv = (pts[k + 1] - pts[k - 1])
        side = dv.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        bl = dv.length * R.uniform(0.8, 1.6)
        dirb = (dv.normalized() + side * R.uniform(-1.2, 1.2) + Vector((0, 0, R.uniform(-.6, .6)))).normalized()
        objs.append(K.polyline('BoltFork', [a, a + dirb * bl * 0.5, a + dirb * bl], width * 0.55, M_BOLT))
    for o in objs:
        if parent is not None:
            o.parent = parent
        o.visible_shadow = False
        K.show_between(o, f, f + nf)
    return objs


def gold_sparks(pos, t, size, n=10):
    f0 = P.T(t)
    for _ in range(n):
        sp = K.sphere('Spk', 1.0, M_SPARK, seg=(6, 4))
        sp.visible_shadow = False
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.3, 1))).normalized() * size * R.uniform(2.5, 4.5)
        sp.scale = (0.16 * size, 0.03 * size, 0.03 * size)
        sp.rotation_mode = 'QUATERNION'
        sp.rotation_quaternion = v.to_track_quat('X', 'Z')
        sp.location = pos
        sp.keyframe_insert('location', frame=f0)
        sp.location = pos + v * 0.3 + Vector((0, 0, -0.3))
        sp.keyframe_insert('location', frame=f0 + 0.3 * FPS)
        K.show_between(sp, f0, f0 + 0.3 * FPS)
    P.light(pos, t, GOLD, energy=1500 * size, dur=0.15, radius=0.5)


def dust_ring(center, t, r0, r1, n=22, size=1.3, life=1.5, opacity=0.3, rise=0.6, rings=2):
    c = Vector(center)
    for k in range(rings):
        u = k / max(1, rings - 1)
        r = lerp(r0, r1, u)
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.92, 1.08)
            P.puff(p + Vector((0, 0, 0.25)), t + 0.1 * k + R.uniform(0, 0.05), size=size * (1 + 0.3 * u), n=1,
                   rise=rise * (1 + u), life=life, color=DUST, opacity=opacity * (1 - 0.3 * u))


# ------------------------------------------------------------------------------- the ring
ring = P.load('landing_ring', at=(0, 0), heading=0, label='ring')
bpy.context.view_layer.update()
root = ring.root
hull = ring.parts['Hull']
crown_pv = ring.parts['CrownPivot']
halo_pv = ring.parts['HaloPivot']
AX = crown_pv.matrix_world.translation.x          # ring axis (the tongue shifts the bbox centre)
CROWN_Z = crown_pv.matrix_world.translation.z      # 1.79
HALO_Z = halo_pv.matrix_world.translation.z        # 5.19
print('axis', AX, 'crown', CROWN_Z, 'halo', HALO_Z)

# ---- split the petals off the hull so they can fold into a bud and hang free
OUTER_AZ = [67.5, 112.5, 157.5, -157.5, -112.5]
INNER_AZ = [91.0, 136.0, 180.0, -136.0]


def components(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    seen = set()
    comps = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]
        seen.add(v.index)
        vs = []
        while stack:
            x = stack.pop()
            vs.append(x.index)
            for e in x.link_edges:
                y = e.other_vert(x)
                if y.index not in seen:
                    seen.add(y.index)
                    stack.append(y)
        comps.append(set(vs))
    bm.free()
    return comps


def az_diff(a, b):
    return (a - b + 180) % 360 - 180


MW = hull.matrix_world.copy()
comps = components(hull.data)
groups = {('o', k): set() for k in range(len(OUTER_AZ))}
groups.update({('i', k): set() for k in range(len(INNER_AZ))})
for c in comps:
    ws = [MW @ hull.data.vertices[i].co for i in c]
    cen = sum(ws, Vector()) / len(ws)
    r = math.hypot(cen.x - AX, cen.y)
    az = math.degrees(math.atan2(cen.y, cen.x - AX))
    # outer petals rise with radius (pitched 32 deg); seeds at the tips ride along
    if 3.6 < r < 7.9 and abs(cen.z - (1.2 + (r - 3.9) * 0.63)) < 0.45 and cen.z > 0.85:
        k = min(range(len(OUTER_AZ)), key=lambda j: abs(az_diff(az, OUTER_AZ[j])))
        if abs(az_diff(az, OUTER_AZ[k])) < 16:
            groups[('o', k)] |= c
            continue
    if 3.9 < r < 6.8 and 1.2 < cen.z < 1.7:
        k = min(range(len(INNER_AZ)), key=lambda j: abs(az_diff(az, INNER_AZ[j])))
        if abs(az_diff(az, INNER_AZ[k])) < 12:
            groups[('i', k)] |= c


def cut_piece(name, vset):
    """New object holding the faces whose verts are all in vset; those faces leave the hull."""
    me = hull.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    drop = [f for f in bm.faces if not all(v.index in vset for v in f.verts)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new(name, me))
    o.parent = hull.parent
    o.matrix_parent_inverse = hull.matrix_parent_inverse.copy()
    o.location = hull.location.copy()
    o.rotation_mode = hull.rotation_mode
    o.rotation_quaternion = hull.rotation_quaternion.copy()
    o.scale = hull.scale.copy()
    return o


all_cut = set()
for v in groups.values():
    all_cut |= v
pieces = {}
for key, vset in groups.items():
    if vset:
        pieces[key] = cut_piece(f'Petal_{key[0]}{key[1]}', vset)
# remove the cut faces from the hull
bm = bmesh.new()
bm.from_mesh(hull.data)
kill = [f for f in bm.faces if all(v.index in all_cut for v in f.verts)]
bmesh.ops.delete(bm, geom=kill, context='FACES')
bm.to_mesh(hull.data)
bm.free()
bpy.context.view_layer.update()
print('petal pieces', {k: len(v) for k, v in groups.items()})


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = Matrix()
    bpy.context.view_layer.update()
    child.matrix_world = mw


# pivots at the inner foot of each petal (root space == world at rest)
PETALS = []
for key, o in pieces.items():
    kind, k = key
    az = OUTER_AZ[k] if kind == 'o' else INNER_AZ[k]
    a = math.radians(az)
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    rmin = min(math.hypot(v.x - AX, v.y) for v in vs)
    zfoot = min(v.z for v in vs)
    foot = Vector((AX + rmin * math.cos(a), rmin * math.sin(a), zfoot))
    pv = K.empty(f'PetalPv_{kind}{k}', loc=foot)
    pv.parent = root
    pv.rotation_mode = 'QUATERNION'
    parent_keep(o, pv)
    tang = Vector((-math.sin(a), math.cos(a), 0))
    PETALS.append(dict(obj=o, pv=pv, az=az, kind=kind, foot=foot, tang=tang,
                       tip_r=max(math.hypot(v.x - AX, v.y) for v in vs)))
print('petals', [(p['kind'], round(p['az']), [round(x, 2) for x in p['foot']]) for p in PETALS])

# ---- descent: a closed bud dropping on lightning legs, turning slowly as it brakes
T_LAND = 1.4
root.rotation_mode = 'XYZ'
DESC = [(0.0, (-15.0, 7.0, 15.0), 1, -1.5, -75), (0.6, (-5.5, 2.4, 6.5), -4, 3, -32),
        (1.05, (-1.0, 0.4, 1.8), 1.5, -1, -8), (T_LAND, (0, 0, 0.0), 0, 0, 0)]
for t, p, rx, ry, rz in DESC:
    root.location = p
    root.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    root.keyframe_insert('location', frame=P.T(t))
    root.keyframe_insert('rotation_euler', frame=P.T(t))
root.location = (0, 0, -0.08)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.05))
root.location = (0, 0, 0)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.2))
K.set_interp(root, 'BEZIER')

# ---- bloom: petals folded up into a bud until landing, then swing open one after another
# (camera side first), overshoot, then hang free over the rim with a gap and a gentle bob
T_BLOOM = T_LAND + 0.08
LIFT = 0.28
order = sorted(PETALS, key=lambda p: (p['kind'] != 'o', abs(az_diff(p['az'], -112))))
for i, pc in enumerate(order):
    pv = pc['pv']
    fold = -82.0 if pc['kind'] == 'o' else -70.0
    t0 = T_BLOOM + 0.07 * i
    qf = Quaternion(pc['tang'], math.radians(fold))
    qo = Quaternion(pc['tang'], math.radians(9.0))
    base = pv.location.copy()
    seed = i * 1.37

    def key(t, q, dz):
        pv.rotation_quaternion = q
        pv.location = base + Vector((0, 0, dz))
        pv.keyframe_insert('rotation_quaternion', frame=P.T(t))
        pv.keyframe_insert('location', frame=P.T(t))
    key(0.0, qf, 0.12)
    key(t0, qf, 0.12)
    key(t0 + 0.42, qo, LIFT + 0.25)
    t = t0 + 0.62
    while t <= 6.2:
        w = ss((t - t0 - 0.62) / 0.4)
        sway = Quaternion(pc['tang'], math.radians(1.6 * math.sin(2.0 * t + seed) * w))
        key(t, sway, LIFT + 0.07 * math.sin(2 * math.pi * 0.55 * t + seed) * w)
        t += 0.25
    K.set_interp(pv, 'BEZIER')
    pc['t_open'] = t0 + 0.62

# ---- halo clasps the bud tips in flight, floats up off them after landing; crown rises too.
# Both spin (their own pivots), the halo surging each time a delivery passes through it.
halo_pv.rotation_mode = 'XYZ'
crown_pv.rotation_mode = 'XYZ'
H0 = halo_pv.location.copy()
C0 = crown_pv.location.copy()
NK = halo_pv.parent.matrix_world.to_scale().z     # pivot parent space -> world metres
T_ARR = [2.2, 3.35, 4.45]                          # deliveries start down the column
T_HOVER = [t + 0.62 for t in T_ARR]


def halo_dz(t):
    """World metres relative to its modelled height."""
    clasp = -0.75
    u = ss((t - (T_BLOOM + 0.1)) / 0.55)
    over = 0.35 * math.sin(math.pi * min(1, max(0, (t - T_BLOOM - 0.1) / 0.75))) if t > T_BLOOM + 0.1 else 0
    bob = 0.1 * math.sin(2 * math.pi * 0.4 * t) * ss((t - 2.2) / 0.5)
    return lerp(clasp, 0.25, u) + over + bob


def crown_dz(t):
    u = ss((t - (T_BLOOM + 0.25)) / 0.5)
    bob = 0.06 * math.sin(2 * math.pi * 0.6 * t + 1.0) * ss((t - 2.2) / 0.5)
    kick = 0.0
    for th in T_HOVER:
        if t > th - 0.1:
            d = t - (th - 0.1)
            kick -= 0.12 * (d * 8.0) * math.exp(1.0 - d * 8.0)
    return lerp(-0.35, 0.2, u) + bob + kick


def spin_rate(t, base, surge):
    r = base * ss((t - (T_BLOOM + 0.2)) / 0.6)
    for ta in T_ARR:
        tp = ta + 0.45              # unit passing the halo
        r += surge * math.exp(-((t - tp) / 0.22) ** 2)
    return r


ang_h = ang_c = 0.0
for f in range(0, NF + 2):
    t = (f - 1) / FPS
    halo_pv.location = H0 + Vector((0, 0, halo_dz(t) / NK))
    crown_pv.location = C0 + Vector((0, 0, crown_dz(t) / NK))
    ang_h += spin_rate(t, -28.0, -260.0) / FPS
    ang_c += spin_rate(t, 55.0, 160.0) / FPS
    halo_pv.rotation_euler.z = math.radians(ang_h)
    crown_pv.rotation_euler.z = math.radians(ang_c)
    for o in (halo_pv, crown_pv):
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_euler', index=2, frame=f)
K.set_interp(halo_pv, 'LINEAR')
K.set_interp(crown_pv, 'LINEAR')


def halo_c(t):
    return Vector((AX, 0, HALO_Z + halo_dz(t)))


def crown_c(t):
    return Vector((AX, 0, CROWN_Z + crown_dz(t)))


# ---- veins: dim in flight, flare as the column strikes, settle to a warm glow
nest_mat = bpy.data.materials['KeshLandingNestMat']
es = nest_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
for t, v in [(0, 1.6), (T_LAND, 1.6), (T_LAND + 0.6, 3.2), (2.05, 3.2), (2.15, 5.0), (2.6, 3.6), (6, 3.6)]:
    es.default_value = v
    es.keyframe_insert('default_value', frame=P.T(t))

# ---- descent lightning legs: jagged gold bolts from the underside reaching for the ground
for f in range(1, int(P.T(T_LAND)) + 2):
    t = (f - 1) / FPS
    c = ring.pos_at(t)
    alt = c.z
    fade = 1 - ss((t - T_LAND + 0.12) / 0.15)
    if fade < 0.05:
        continue
    for k in range(5):
        if R.random() < 0.2:
            continue
        a = R.uniform(0, 2 * math.pi)
        rr = R.uniform(3.0, 5.5)
        p0 = c + Vector((AX + math.cos(a) * rr, math.sin(a) * rr, 0.1))
        reach = min(alt + 0.05, R.uniform(4.0, 8.0))
        out = Vector((math.cos(a), math.sin(a), 0)) * R.uniform(0.3, 1.6)
        p1 = p0 + out + Vector((0, 0, -reach))
        bolt_frame(jag_pts(p0, p1, 7, 0.45), f, (0.03 + 0.02 * (alt < 6)) * fade, forks=1, core=alt < 8)
    if alt < 4.5 and f % 2 == 0:
        a = R.uniform(0, 2 * math.pi)
        P.puff(Vector((AX + math.cos(a) * 4, math.sin(a) * 4, 0.2)), t, size=1.3, n=1, rise=0.5, life=1.0,
               color=DUST, opacity=0.22)
# under-glow while the legs crackle
gl = K.link(bpy.data.objects.new('LegLight', bpy.data.lights.new('LegLight', 'POINT')))
gl.parent = root
gl.location = (AX, 0, -1.0)
gl.data.color = GOLD
gl.data.shadow_soft_size = 3.0
for t, e in [(0.0, 3000), (1.0, 9000), (T_LAND, 6000), (T_LAND + 0.15, 0)]:
    gl.data.energy = e
    gl.data.keyframe_insert('energy', frame=P.T(t))

dust_ring((AX, 0, 0), T_LAND - 0.02, 6.5, 10.5, n=26, size=1.5, life=1.6, opacity=0.28)
dust_ring((AX, 0, 0), T_LAND + 0.1, 11.0, 14.0, n=30, size=1.2, life=1.3, opacity=0.16, rings=1)
P.cam_shake(T_LAND, 0.16, dur=0.35)

# ---- suspension arcs: faint gold crackle in the gaps under the floating petals
for f in range(int(P.T(T_BLOOM + 0.3)), NF + 1):
    t = (f - 1) / FPS
    for _ in range(3):
        if R.random() < 0.4:
            continue
        pc = R.choice(PETALS)
        if t < pc['t_open'] - 0.2:
            continue
        pv = pc['pv']
        a = math.radians(pc['az'] + R.uniform(-5, 5))
        rr = math.hypot(pc['foot'].x - AX, pc['foot'].y) + R.uniform(0.0, 0.5)
        p0 = Vector((AX + rr * math.cos(a), rr * math.sin(a), pc['foot'].z - 0.05))
        p1 = p0 + Vector((0, 0, LIFT + 0.12))
        bolt_frame(jag_pts(p0, p1, 4, 0.9), f, 0.012, forks=0, core=False)

# ------------------------------------------------------------------------------- column of light
COL_TOP = 90.0
COL_R = 2.2
T_COL = 2.0


def cyl_mesh(name, r, verts=32):
    """Open cylinder from z=0 down to z=-1 (origin at the top)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    ring0 = [bm.verts.new((r * math.cos(2 * math.pi * i / verts), r * math.sin(2 * math.pi * i / verts), 0)) for i in range(verts)]
    ring1 = [bm.verts.new((v.co.x, v.co.y, -1.0)) for v in ring0]
    for i in range(verts):
        j = (i + 1) % verts
        bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


M_COLUMN = soft_emit('LrColumn', (1.0, 0.45, 0.06), 1.6, power=1.6, blend=0.35)
M_COLCORE = soft_emit('LrColumnCore', (1.0, 0.62, 0.2), 2.0, power=3.0, blend=0.3)
COL_GAIN = {M_COLUMN.name: 0.24, M_COLCORE.name: 0.3}
columns = []
for nm, r_, m_ in (('Column', COL_R, M_COLUMN), ('ColumnCore', COL_R * 0.45, M_COLCORE)):
    o = K.link(bpy.data.objects.new(nm, cyl_mesh(nm, r_)))
    o.data.materials.append(m_)
    o.location = (AX, 0, COL_TOP)
    o.visible_shadow = False
    columns.append(o)
HEART_Z = 0.75
for o in columns:
    for t, s in ((0.0, 0.001), (T_COL, 0.001), (T_COL + 0.16, COL_TOP - HEART_Z)):
        o.scale = (1, 1, s)
        o.keyframe_insert('scale', frame=P.T(t))
    K.set_interp(o, 'LINEAR')
    K.show_between(o, P.T(T_COL), NF + 2)
# brightness: flare on the strike, breathe, swell for each delivery
for m_ in (M_COLUMN, M_COLCORE):
    g_ = COL_GAIN[m_.name]
    key_gain(m_, T_COL, 0.0)
    key_gain(m_, T_COL + 0.08, 1.3 * g_)
    key_gain(m_, T_COL + 0.3, 0.75 * g_)
    for ta, th in zip(T_ARR, T_HOVER):
        key_gain(m_, ta, 0.75 * g_)
        key_gain(m_, ta + 0.25, 1.0 * g_)
        key_gain(m_, th + 0.2, 0.75 * g_)
    key_gain(m_, 6.1, 0.75 * g_)

# sky bolt: the column is called down by a strike from above through the halo onto the heart
for f in range(int(P.T(T_COL - 0.08)), int(P.T(T_COL + 0.2)) + 1):
    t = (f - 1) / FPS
    top = Vector((AX + R.uniform(-1, 1), R.uniform(-1, 1), 45))
    mid = halo_c(t) + Vector((R.uniform(-0.4, 0.4), R.uniform(-0.4, 0.4), 0))
    bot = Vector((AX, 0, HEART_Z + 0.1))
    bolt_frame(jag_pts(top, mid, 12, 0.08), f, 0.07, forks=2)
    bolt_frame(jag_pts(mid, bot, 6, 0.3), f, 0.05, forks=1)
    if R.random() < 0.7:
        for _ in range(2):      # the halo rim throws arcs inward
            a = R.uniform(0, 2 * math.pi)
            p0 = halo_c(t) + Vector((2.7 * math.cos(a), 2.7 * math.sin(a), 0))
            bolt_frame(jag_pts(p0, mid, 5, 0.4), f, 0.025, forks=0, core=False)
P.light(halo_c(T_COL), T_COL, GOLD, energy=12000, dur=0.35, radius=2.0)
gold_sparks(Vector((AX, 0, HEART_Z + 0.4)), T_COL + 0.05, 1.0, n=14)
P.cam_shake(T_COL + 0.02, 0.08, dur=0.25)
P.puff(Vector((AX, 0, 0.9)), T_COL + 0.05, size=2.0, n=3, rise=0.6, life=1.0, color=(0.95, 0.75, 0.5), opacity=0.18)
# steady heart light under the column
hl = K.link(bpy.data.objects.new('HeartLight', bpy.data.lights.new('HeartLight', 'POINT')))
hl.location = (AX, 0, 2.6)
hl.data.color = (1.0, 0.6, 0.2)
hl.data.shadow_soft_size = 1.5
for t, e in [(0, 0), (T_COL, 0), (T_COL + 0.1, 5000), (T_COL + 0.5, 2500), (6.1, 2500)]:
    hl.data.energy = e
    hl.data.keyframe_insert('energy', frame=P.T(t))

# motes drifting up the column
M_MOTE = K.emit_mat('LrMote', (1.0, 0.68, 0.25), 2.5)
for i in range(46):
    o = K.sphere('Mote', 1.0, M_MOTE, seg=(6, 4))
    o.visible_shadow = False
    s = R.uniform(0.035, 0.07)
    o.scale = (s, s, s * 3)
    a0 = R.uniform(0, 2 * math.pi)
    rr = R.uniform(0.4, COL_R * 0.95)
    t0 = R.uniform(T_COL + 0.1, 5.6)
    life = R.uniform(0.8, 1.6)
    z0 = R.uniform(0.8, 6)
    for k in range(5):
        u = k / 4
        a = a0 + u * 1.5
        o.location = (AX + rr * math.cos(a), rr * math.sin(a), z0 + u * life * 4.0)
        o.keyframe_insert('location', frame=P.T(t0 + u * life))
    K.show_between(o, P.T(t0), P.T(t0 + life))

# ------------------------------------------------------------------------------- flight helpers
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def hermite(keys):
    ks = [(t, Vector(p), Vector(v)) for t, p, v in keys]

    def f(t):
        if t <= ks[0][0]:
            return ks[0][1] + ks[0][2] * (t - ks[0][0])
        if t >= ks[-1][0]:
            return ks[-1][1] + ks[-1][2] * (t - ks[-1][0])
        for (t0, p0, v0), (t1, p1, v1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                h = t1 - t0
                u = (t - t0) / h
                h00 = 2 * u ** 3 - 3 * u ** 2 + 1
                h10 = u ** 3 - 2 * u ** 2 + u
                h01 = -2 * u ** 3 + 3 * u ** 2
                h11 = u ** 3 - u ** 2
                return p0 * h00 + v0 * (h10 * h) + p1 * h01 + v1 * (h11 * h)
    return f


def fly(actor, posf, rest_fwd, bank=0.25, clamp=35, pitch_max=14):
    """Key the root every frame: nose follows horizontal velocity (rest_fwd when hovering),
    gentle pitch with climb/descent, banked into turns."""
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    dt = 1.0 / FPS
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        vh = Vector((v.x, v.y, 0))
        rf = rest_fwd(t)
        w = ss((vh.length - 0.6) / 3.0)
        hd = (rf * (1 - w) + (vh.normalized() if vh.length > 1e-3 else rf) * w).normalized()
        pit = math.atan2(v.z, max(vh.length, 6.0)) * w
        pit = max(-math.radians(pitch_max), min(math.radians(pitch_max), pit))
        fwd = hd * math.cos(pit) + Vector((0, 0, math.sin(pit)))
        vn = v.normalized() if v.length > 1e-3 else fwd
        lat = a - vn * a.dot(vn)
        lat.z = 0
        up = (Vector((0, 0, 9.8)) + lat * bank * w)
        up.normalize()
        angu = math.degrees(math.acos(max(-1, min(1, up.z))))
        if angu > clamp:
            h = Vector((up.x, up.y, 0)).normalized()
            c = math.radians(clamp)
            up = h * math.sin(c) + Vector((0, 0, math.cos(c)))
        m3 = frame_from(fwd, up)
        q = m3.to_quaternion()
        if prev_q is not None:
            q.make_compatible(prev_q)
        prev_q = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.Translation(p) @ m3.to_4x4()
    K.set_interp(r, 'LINEAR')
    actor.mats = mats
    return mats


def surface_z(x, y):
    """Height of what lies under (x, y): crown ring, bowl floor, rim, the sloping mouth, ground."""
    dx = x - AX
    r = math.hypot(dx, y)
    if dx > 4.3 and abs(y) < 2.9:
        return max(0.0, 0.84 * (1 - (dx - 4.3) / 3.2))
    if r < 6.2:
        return 0.78
    if r < 7.4:
        return 0.55
    return 0.0


# ------------------------------------------------------------------------------- deliveries
HOVER_Z = 2.55          # over the crown
DROP_Z = 30.0
GROUND_HOVER = 0.6

M_RING = soft_emit('LrDropRing', (1.0, 0.55, 0.12), 2.6, power=0.6, blend=0.2)


def drop_keys(ta, tail):
    th = ta + 0.62
    return th, [
        (ta, (AX, 0, DROP_Z), (0, 0, -55)),
        (ta + 0.42, (AX, 0, HOVER_Z + 1.4), (0, 0, -5.5)),
        (th, (AX, 0, HOVER_Z), (0, 0, 0)),
    ] + tail


def bob_wrap(base, t_hover, amp=0.06, hz=1.1):
    def pos(t):
        p = base(t)
        if t > t_hover:
            p = p + Vector((0, 0, amp * math.sin(2 * math.pi * hz * (t - t_hover)) * ss((t - t_hover) / 0.3)))
        return p
    return pos


units = []
# 1) Lumen: couples, glides out over the mouth, swings left and takes up guard
lumen = P.load('lumen', label='lumen_d')
th, keys = drop_keys(T_ARR[0], [
    (T_ARR[0] + 0.86, (AX + 0.6, 0, HOVER_Z + 0.05), (3.0, 0, 0)),
    (T_ARR[0] + 1.28, (6.4, 0.5, 1.45), (10.5, 2.0, -2.2)),
    (T_ARR[0] + 1.75, (8.7, 3.4, GROUND_HOVER), (2.0, 5.5, -0.4)),
    (T_ARR[0] + 2.35, (8.9, 5.5, GROUND_HOVER), (0.1, 0.3, 0)),
    (7.0, (8.95, 5.7, GROUND_HOVER), (0, 0, 0)),
])
units.append(dict(a=lumen, ta=T_ARR[0], th=th, t_go=T_ARR[0] + 0.86, pos=bob_wrap(hermite(keys), th),
                  rest=lambda t: Vector((1, 0, 0)) if t < 3.5 else Vector((1, 0.45, 0)).normalized()))
# 2) Darter: the scout barely touches down before it is gone, fast and low out to the right
darter = P.load('darter', label='darter_d')
th, keys = drop_keys(T_ARR[1], [
    (T_ARR[1] + 0.78, (AX + 0.5, 0, HOVER_Z + 0.05), (6.0, 0, 0)),
    (T_ARR[1] + 1.05, (7.4, 0.2, 1.2), (22.0, 0.5, -2.5)),
    (T_ARR[1] + 1.45, (16.0, 1.2, GROUND_HOVER + 0.1), (24.0, 2.5, 0)),
    (T_ARR[1] + 2.2, (34.0, 3.5, GROUND_HOVER + 0.1), (24.0, 3.0, 0)),
])
units.append(dict(a=darter, ta=T_ARR[1], th=th, t_go=T_ARR[1] + 0.78, pos=bob_wrap(hermite(keys), th, 0.04, 1.6),
                  rest=lambda t: Vector((1, 0, 0))))
# 3) Ferrier: heavy tug, last one down, still gliding out over the mouth at the end
ferrier = P.load('ferrier', label='ferrier_d')
th, keys = drop_keys(T_ARR[2], [
    (T_ARR[2] + 0.9, (AX + 0.4, 0, HOVER_Z + 0.05), (2.0, 0, 0)),
    (6.0, (7.2, -0.9, 1.15), (7.0, -1.2, -1.0)),
])
units.append(dict(a=ferrier, ta=T_ARR[2], th=th, t_go=T_ARR[2] + 0.9, pos=bob_wrap(hermite(keys), th, 0.05, 0.9),
                  rest=lambda t: Vector((1, 0, 0))))

for u in units:
    a = u['a']
    fly(a, u['pos'], u['rest'], bank=0.22)
    a.appear(u['ta'])
    bpy.context.view_layer.update()
    u['L'] = a.entry['size']
    print(a.name, 'hover', u['th'], 'pos end', u['pos'](6.0))


def unit_lifters(u, t_end=6.05):
    """Gold lightning lifters under the hull: short legs while riding the column, reaching to
    whatever is below once low (crown, bowl, mouth, ground)."""
    a = u['a']
    L = u['L']
    for f in range(int(P.T(u['ta'])), int(P.T(t_end)) + 1):
        t = (f - 1) / FPS
        m = a.mats[min(NF + 1, f)]
        p = m.translation
        for k in range(3):
            if R.random() < 0.22:
                continue
            loc = Vector((R.uniform(-0.3, 0.3) * L, R.uniform(-0.18, 0.18) * L, 0.18))
            p0 = m @ loc
            gz = surface_z(p0.x, p0.y)
            # over the crown: arc to the crown ring
            if math.hypot(p0.x - AX, p0.y) < 2.0 and p0.z < 4.5:
                cc = crown_c(t)
                aa = math.atan2(p0.y, p0.x - AX) + R.uniform(-0.5, 0.5)
                p1 = cc + Vector((1.1 * math.cos(aa), 1.1 * math.sin(aa), 0.1))
            elif p0.z - gz < 2.4:
                p1 = Vector((p0.x + R.uniform(-0.4, 0.4), p0.y + R.uniform(-0.4, 0.4), gz))
            else:
                p1 = p0 + Vector((R.uniform(-0.4, 0.4), R.uniform(-0.4, 0.4), -R.uniform(0.7, 1.4)))
            bolt_frame(jag_pts(p0, p1, 5, 0.5), f, 0.02, forks=1 if R.random() < 0.4 else 0, core=False)
    lt = K.link(bpy.data.objects.new(a.name + '_Lift', bpy.data.lights.new(a.name + '_Lift', 'POINT')))
    lt.parent = a.root
    lt.location = (0, 0, -0.2)
    lt.data.color = GOLD
    lt.data.energy = 500
    lt.data.shadow_soft_size = 0.8
    K.show_between(lt, P.T(u['ta']), NF + 2)


def drop_rings(u):
    """Three light rings slide down the column wrapped round the unit, then flare and fade."""
    a = u['a']
    for k in range(3):
        o2 = K.polyline('DropRing', [(math.cos(2 * math.pi * i / 40), math.sin(2 * math.pi * i / 40), 0) for i in range(41)],
                        0.024, M_RING)
        o2.visible_shadow = False
        f0 = int(P.T(u['ta']))
        f1 = int(P.T(u['th'] + 0.12))
        for f in range(f0, f1 + 1):
            t = (f - 1) / FPS
            p = u['pos'](t)
            z = p.z + 0.6 + k * 1.1 + 1.2 * (1 - ss((t - u['ta']) / 0.5)) * k
            rr = COL_R * (1.05 - 0.12 * k)
            if t > u['th'] - 0.05:
                w = ss((t - u['th'] + 0.05) / 0.27)
                rr *= 1 + 0.6 * w
                z = lerp(z, p.z + 0.4, w)
            o2.location = (AX, 0, z)
            o2.scale = (rr, rr, rr)
            o2.keyframe_insert('location', frame=f)
            o2.keyframe_insert('scale', frame=f)
        K.set_interp(o2, 'LINEAR')
        K.show_between(o2, f0, f1)


def couple(u):
    """At the bottom of the column: arcs lock between crown and belly, the crown flares."""
    th = u['th']
    a = u['a']
    for f in range(int(P.T(th - 0.12)), int(P.T(u['t_go'])) + 1):
        t = (f - 1) / FPS
        m = a.mats[f]
        for _ in range(2):
            aa = R.uniform(0, 2 * math.pi)
            p0 = crown_c(t) + Vector((1.1 * math.cos(aa), 1.1 * math.sin(aa), 0.1))
            p1 = m @ Vector((R.uniform(-0.3, 0.3) * u['L'], R.uniform(-0.15, 0.15) * u['L'], 0.2))
            bolt_frame(jag_pts(p0, p1, 6, 0.4), f, 0.028, forks=1, core=True)
    P.light(crown_c(th), th - 0.05, GOLD, energy=5000, dur=0.35, radius=1.0)
    gold_sparks(crown_c(th) + Vector((0, 0, 0.2)), th - 0.02, 0.6, n=8)
    # wash across the bowl as it sets down
    for i in range(10):
        aa = 2 * math.pi * i / 10 + R.uniform(-0.2, 0.2)
        P.puff(Vector((AX + 3.2 * math.cos(aa), 3.2 * math.sin(aa), 1.0)), th - 0.08, size=0.8, n=1, rise=0.3,
               life=0.7, color=(0.95, 0.78, 0.55), opacity=0.14)


for u in units:
    unit_lifters(u)
    drop_rings(u)
    couple(u)
    # dust once it reaches open ground
    t = u['t_go'] + 0.5
    while t < min(6.0, u['t_go'] + 2.2):
        p = u['pos'](t)
        if p.z < 1.2 and math.hypot(p.x - AX, p.y) > 7.0:
            P.puff(Vector((p.x, p.y, 0.2)), t, size=0.8, n=1, rise=0.4, life=0.9, color=DUST, opacity=0.22)
        t += 0.1

# the Lumen's turret sweeps the approaches once it is on guard
lumen.turret_yaw([(0.0, 0), (4.4, 0), (5.0, 35), (5.6, -20), (6.0, -15)])

# ------------------------------------------------------------------------------- camera
# 0-1.4 low and wide, looking up as the gold bud walks down on its lightning legs;
# 1.4-2.3 hold low on the -Y side as it blooms, tilt up with the sky strike;
# 2.3-4.6 drift round toward the mouth, watching each delivery come down and leave;
# 4.6-6.0 settle low at the mouth: the Ferrier glides out toward us, Lumen on guard, column high.
cam_keys = []
for t in (0.0, 0.45, 0.9):
    c = ring.pos_at(t)
    cam_keys.append((t, (-2.0 + 0.8 * t, -17.0, 6.5 - 3.6 * t), (c.x + AX, c.y, c.z + 3.2), 26))
cam_keys += [
    (1.4, (-1.0, -16.5, 2.6), (AX, 0, 2.6), 26),
    (2.0, (1.0, -16.0, 3.0), (AX, 0, 4.6), 24),
    (2.6, (5.0, -15.0, 3.4), (AX + 1.0, 0, 3.8), 26),
    (3.4, (10.0, -13.0, 3.3), (AX + 2.5, 0, 3.0), 26),
    (4.2, (14.0, -10.0, 3.0), (AX + 3.0, 0, 3.2), 26),
    (5.0, (16.5, -7.5, 2.4), (2.6, 0.8, 3.3), 24),
    (6.0, (16.0, -6.0, 2.0), (3.0, 1.2, 3.3), 22),
]
P.camera(cam_keys, shake=0.02)

# effects never cast shadows
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.active_material is not None:
        m = o.active_material
        if 'emit_node' in m or m.name.startswith(('SoftFire', 'Fireball', 'SoftPuff')):
            o.visible_shadow = False

P.render()
