"""The two factions' portals. One build each, shared by every film, so a faction's way through space
always looks the same (David 2026-11-14).

ARCADIAN (arcadian_portal): electrical but black, dark, mysterious, crisp, precise, almost
scientific. A perfect black void with a razor-thin white-gold lip; starlight bends round it (a
refracting lens ring); concentric hairline rings with tick marks like a precision instrument turn
at their own rates; crisp electric arcs jump between the rings (arcadian_arcs). Behind the mouth a
black tunnel with only the faintest cold glints, so ships come up out of darkness.
Contract: object 'Rift', unit disc in local XY facing local +Z; it is scaled (S, S, 1), so local
x/y are in portal radii and local z is in world units.

TERRAN (terran_tear): terrifying; space-time brutally torn open, as if an invisible force grabs the
edges and pulls in jerks until it rips. A jagged hole whose shredded edges glow white-hot blue;
strands of space stretch across the gap and snap; shards of space break away like glass; inside, a
violent churning light. It slams shut. World-unit object facing local +Z.
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import barrage_pieces as BP

GOLD = (1.0, 0.78, 0.42)
ICE = (0.72, 0.86, 1.0)


# ================================================================== shared bits
def _obj(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.visible_shadow = False
    return ob


def _annulus(name, r0, r1, z, segs=512):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new((r0 * math.cos(2 * math.pi * i / segs), r0 * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)]
    b = [bm.verts.new((r1 * math.cos(2 * math.pi * i / segs), r1 * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)]
    for i in range(segs):
        i2 = (i + 1) % segs
        bm.faces.new((a[i], a[i2], b[i2], b[i]))
    bm.to_mesh(me)
    bm.free()
    return _obj(name, me)


def _disc(name, r, z, segs=256):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    return _obj(name, me)


def _polar(n, tc):
    sep = n.node('ShaderNodeSeparateXYZ')
    n.set(sep.inputs[0], tc.outputs['Object'])
    xy = n.node('ShaderNodeCombineXYZ')
    n.set(xy.inputs['X'], sep.outputs['X'])
    n.set(xy.inputs['Y'], sep.outputs['Y'])
    ln = n.node('ShaderNodeVectorMath', operation='LENGTH')
    n.set(ln.inputs[0], xy.outputs[0])
    ang = n.node('ShaderNodeMath', operation='ARCTAN2')
    n.set(ang.inputs[0], sep.outputs['Y'])
    n.set(ang.inputs[1], sep.outputs['X'])
    return ln.outputs['Value'], ang.outputs[0], sep


def _black(name):
    m, n = BP._new_mat(name)
    em = n.node('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 0.0
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], em.outputs[0])
    return m


# ================================================================== Arcadian
def _instrument_ring_mat(name, r0, w, ticks, duty, col, strength, major=0, major_len=0.0):
    """A hairline ring with evenly spaced tick marks (every `major`-th tick runs longer)."""
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    r, ang, _ = _polar(n, tc)
    line = n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', r, r0)), w * 0.5, w * 0.5 + 0.0012, 1.0, 0.0)
    u = n.math('FRACT', n.math('MULTIPLY', n.math('ADD', ang, math.pi), ticks / (2 * math.pi)))
    tick_on = n.math('LESS_THAN', u, duty)
    tick_len = 0.018
    if major:
        um = n.math('FRACT', n.math('MULTIPLY', n.math('ADD', ang, math.pi), ticks / major / (2 * math.pi)))
        is_major = n.math('LESS_THAN', um, duty / major)
        tick_len = n.math('MULTIPLY_ADD', is_major, major_len, 0.018)
    dr = n.math('SUBTRACT', r, r0)
    in_tick = n.math('MULTIPLY', n.math('GREATER_THAN', dr, 0.0), n.math('LESS_THAN', dr, tick_len))
    tick = n.math('MULTIPLY', tick_on, in_tick)
    v = n.math('MINIMUM', n.math('ADD', line, n.math('MULTIPLY', tick, 0.7)), 1.0)
    BP._add_out(n, n.math('MULTIPLY', v, strength), col)
    return m


def _lip_mat(name, r0):
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    r, ang, _ = _polar(n, tc)
    d = n.math('SUBTRACT', r, r0)
    core = n.maprange(n.math('ABSOLUTE', d), 0.0, 0.0035, 1.0, 0.0)
    glow = n.math('MULTIPLY', n.math('POWER', n.maprange(d, 0.0, 0.06, 1.0, 0.0), 3.0), n.math('GREATER_THAN', d, 0.0))
    # a slow precise pulse travelling round the lip
    pulse = n.math('POWER', n.math('MULTIPLY_ADD', n.math('SINE', n.math('ADD', n.math('MULTIPLY', ang, 3.0),
                                                                          n.math('MULTIPLY', t, 1.6))), 0.5, 0.5), 6.0)
    s = n.math('ADD', n.math('MULTIPLY', core, 16.0), n.math('MULTIPLY', glow, n.math('MULTIPLY_ADD', pulse, 1.6, 0.25)))
    BP._add_out(n, s, (1.0, 0.86, 0.6))
    return m


def _lens_mat(name, r0, r1):
    """Clear ring that bends the starlight round the void, strongest at the lip."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    n = BP._NT(m)
    tc = n.node('ShaderNodeTexCoord')
    r, ang, _ = _polar(n, tc)
    k = n.math('POWER', n.maprange(r, r0, r1, 1.0, 0.0), 1.5)
    gl = n.node('ShaderNodeBsdfRefraction')
    gl.inputs['Roughness'].default_value = 0.0
    n.set(gl.inputs['IOR'], n.math('MULTIPLY_ADD', k, 0.5, 1.0))
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], n.math('MINIMUM', n.math('MULTIPLY', k, 1.6), 1.0))
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], gl.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], mx.outputs[0])
    return m


def _void_tunnel_mat(name, depth):
    """Black, with only rare cold glints sliding down into the dark."""
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    r, ang, sep = _polar(n, tc)
    z = sep.outputs['Z']
    k = n.maprange(z, -depth, 0.0, 0.0, 1.0)
    co = n.node('ShaderNodeCombineXYZ')
    n.set(co.inputs['X'], n.math('MULTIPLY', n.math('SINE', ang), 3.0))
    n.set(co.inputs['Y'], n.math('MULTIPLY', n.math('COSINE', ang), 3.0))
    n.set(co.inputs['Z'], n.math('ADD', n.math('MULTIPLY', z, 0.05), n.math('MULTIPLY', t, 2.0)))
    nz = n.node('ShaderNodeTexNoise', Scale=1.0, Detail=2.0)
    n.set(nz.inputs['Vector'], co.outputs[0])
    glint = n.math('POWER', n.maprange(nz.outputs['Fac'], 0.68, 0.78, 0.0, 1.0), 3.0)
    s = n.math('MULTIPLY', glint, n.math('MULTIPLY', n.math('POWER', k, 3.0), 1.4))
    em = n.node('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*ICE, 1)
    n.set(em.inputs['Strength'], s)
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], em.outputs[0])
    return m


def arcadian_portal(depth=240.0, frames=1441):
    """See the module docstring. Returns the root ('Rift'); its rings are children and turn on the
    global clock. Also returns nothing else: the arcs are added with arcadian_arcs()."""
    R0 = 0.5                                                   # the void's edge
    root = _disc('Rift', R0, 0.0)               # the mouth itself is open: the tunnel's walls do the hiding
    m0 = bpy.data.materials.new('RiftMouthM')
    m0.use_nodes = True
    nt0 = m0.node_tree
    for nd in list(nt0.nodes):
        nt0.nodes.remove(nd)
    tr0 = nt0.nodes.new('ShaderNodeBsdfTransparent')
    o0 = nt0.nodes.new('ShaderNodeOutputMaterial')
    nt0.links.new(tr0.outputs[0], o0.inputs[0])
    root.data.materials.append(m0)
    # the lip: razor line + soft inner glow
    lip = _annulus('RiftLip', R0 - 0.002, R0 + 0.07, 0.3)
    lip.data.materials.append(_lip_mat('RiftLipM', R0))
    lip.parent = root
    # a darkness round the void that swallows starlight and planet glow behind it
    dm = bpy.data.materials.new('RiftDarkM')
    dm.use_nodes = True
    ntd = dm.node_tree
    for nd in list(ntd.nodes):
        ntd.nodes.remove(nd)
    nd_ = BP._NT(dm)
    tcd = nd_.node('ShaderNodeTexCoord')
    rd, _, _ = _polar(nd_, tcd)
    kd = nd_.math('MULTIPLY', nd_.math('POWER', nd_.maprange(rd, R0, 1.25, 1.0, 0.0), 1.8), 0.9)
    trd = nd_.node('ShaderNodeBsdfTransparent')
    emd = nd_.node('ShaderNodeEmission')
    emd.inputs['Strength'].default_value = 0.0
    mxd = nd_.node('ShaderNodeMixShader')
    nd_.set(mxd.inputs[0], kd)
    nd_.set(mxd.inputs[1], trd.outputs[0])
    nd_.set(mxd.inputs[2], emd.outputs[0])
    od = nd_.node('ShaderNodeOutputMaterial')
    nd_.set(od.inputs['Surface'], mxd.outputs[0])
    dark = _annulus('RiftDark', R0, 1.25, -2.0, segs=256)
    dark.data.materials.append(dm)
    dark.parent = root
    # lensing ring
    lens = _annulus('RiftLens', R0, 0.95, 1.5, segs=384)
    lens.data.materials.append(_lens_mat('RiftLensM', R0, 0.95))
    lens.parent = root
    # precision rings: (radius, width, ticks, duty, colour, strength, turns per minute, z, major, major_len)
    rings = [(0.545, 0.0014, 120, 0.12, GOLD, 2.2, 0.6, 4.0, 10, 0.03),       # dim, set at different depths
             (0.63, 0.0010, 360, 0.25, ICE, 0.9, -0.25, -30.0, 30, 0.02),     # so they drift past each
             (0.74, 0.0018, 24, 0.05, GOLD, 1.8, 0.15, 28.0, 6, 0.05),        # other as the camera moves
             (0.95, 0.0009, 12, 0.02, ICE, 0.7, -0.05, 70.0, 3, 0.06)]
    for i, (rr, w, ticks, duty, col, st, tpm, z, major, mlen) in enumerate(rings):
        ob = _annulus(f'RiftRing{i}', rr - 0.01, rr + 0.075, z)
        ob.data.materials.append(_instrument_ring_mat(f'RiftRingM{i}', rr, w, ticks, duty, col, st, major, mlen))
        ob.parent = root
        ob.rotation_mode = 'XYZ'
        for f, a in ((1, 0.0), (frames, 2 * math.pi * tpm * (frames - 1) / 24.0 / 60.0)):
            ob.rotation_euler = (0, 0, a)
            ob.keyframe_insert('rotation_euler', frame=f)
        if ob.animation_data and ob.animation_data.action:
            import common as C
            C.set_interp(ob, 'LINEAR')
    # tunnel back into the dark
    me = bpy.data.meshes.new('RiftTunnel')
    bm = bmesh.new()
    prof = [(R0, 0.0), (R0 * 0.93, -15.0), (R0 * 0.78, -55.0), (R0 * 0.55, -110.0), (R0 * 0.3, -170.0),
            (R0 * 0.1, -depth)]
    segs = 128
    rs = [[bm.verts.new((rr * math.cos(2 * math.pi * i / segs), rr * math.sin(2 * math.pi * i / segs), z))
           for i in range(segs)] for rr, z in prof]
    for a, b in zip(rs[:-1], rs[1:]):
        for i in range(segs):
            i2 = (i + 1) % segs
            bm.faces.new((a[i], a[i2], b[i2], b[i]))
    cap = bm.verts.new((0, 0, -depth))
    for i in range(segs):
        bm.faces.new((rs[-1][(i + 1) % segs], rs[-1][i], cap))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    tun = _obj('RiftTunnel', me)
    tun.data.materials.append(_void_tunnel_mat('RiftTunnelM', depth))
    tun.parent = root
    return root


def arcadian_arcs(centre, normal, radius, f0, f1, seed=11, every=9):
    """Crisp electric arcs that jump between the portal's rings: short, straight-ish, white-blue
    and gold, one burst every `every` frames (world space; radius = the void's radius)."""
    import space as SP
    rnd = random.Random(seed)
    nrm = Vector(normal).normalized()
    e1 = nrm.orthogonal().normalized()
    e2 = nrm.cross(e1)
    ring_r = [1.09, 1.26, 1.48, 1.9]
    f = f0
    k = 0
    while f < f1:
        pairs = []
        for _ in range(rnd.randint(1, 3)):
            a = rnd.uniform(0, 2 * math.pi)
            i = rnd.randrange(len(ring_r) - 1)
            r0, r1 = ring_r[i] * radius, ring_r[i + 1] * radius
            da = rnd.uniform(-0.05, 0.05)
            p0 = Vector(centre) + (e1 * math.cos(a) + e2 * math.sin(a)) * r0 + nrm * 2
            p1 = Vector(centre) + (e1 * math.cos(a + da) + e2 * math.sin(a + da)) * r1 + nrm * 2
            pairs.append((p0, p1))
        SP.flicker_lightning(pairs, seed * 100 + k, f, f + 3, every=1, width=0.3 * radius / 130.0,
                             name=f'RiftArc{k}', zone_col=ICE if k % 3 else GOLD, strength=12.0)
        f += every + rnd.randint(-3, 5)
        k += 1


# ================================================================== Terran
def _tear_outline(rnd, n=160, R=1.0):
    """Jagged outline of space torn open (unit size): a tall ragged slit, wider at the pull points,
    with uneven fractal raggedness, deep notches and long splinters. Returns (pts, claws) where
    claws are the indices where the force has hold of the edge."""
    ph = [rnd.uniform(0, 6.3) for _ in range(6)]
    claws = sorted(rnd.sample(range(n), 5))
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rag = (0.07 * math.sin(7 * a + ph[0]) + 0.05 * math.sin(13 * a + ph[1]) + 0.035 * math.sin(23 * a + ph[2])
               + 0.025 * math.sin(41 * a + ph[3]))
        rag += rnd.uniform(-0.04, 0.04)
        if rnd.random() < 0.07:
            rag += rnd.uniform(0.12, 0.4)             # splinter torn out of the edge
        if rnd.random() < 0.05:
            rag -= rnd.uniform(0.08, 0.16)            # notch where it held
        for c in claws:                               # pulled points: wide sharp tents
            d = min(abs(i - c), n - abs(i - c))
            rag += 0.32 * math.exp(-(d / 2.2) ** 2)
        rr = R * (1.0 + rag)
        pts.append((rr * 0.62 * math.cos(a), rr * 1.15 * math.sin(a)))
    return pts, claws


def _tear_inside_mat(name, size):
    """The wound: a pitch-black throat with blue-white veins clawing in from the edge."""
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    sc = n.node('ShaderNodeVectorMath', operation='SCALE')
    n.set(sc.inputs[0], tc.outputs['Object'])
    sc.inputs['Scale'].default_value = 1.6 / size
    ra = n.node('ShaderNodeAttribute', attribute_name='edge')
    rim = n.math('POWER', n.maprange(ra.outputs['Fac'], 0.45, 1.0, 0.0, 1.0), 2.5)
    n1 = n.node('ShaderNodeTexNoise', Scale=1.0, Detail=14.0, Roughness=0.7, Distortion=1.4)
    n1.noise_dimensions = '4D'
    n.set(n1.inputs['Vector'], sc.outputs[0])
    n.set(n1.inputs['W'], n.math('MULTIPLY', t, 1.8))
    wob = n.node('ShaderNodeTexNoise', Scale=2.0, Detail=4.0)
    wob.noise_dimensions = '4D'
    n.set(wob.inputs['Vector'], sc.outputs[0])
    n.set(wob.inputs['W'], n.math('MULTIPLY', t, 1.2))
    wv = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    n.set(wv.inputs[0], wob.outputs['Color'])
    wv.inputs[1].default_value = (0.35, 0.35, 0.35)
    n.set(wv.inputs[2], sc.outputs[0])
    vr = n.node('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    vr.voronoi_dimensions = '4D'
    vr.inputs['Scale'].default_value = 7.0
    n.set(vr.inputs['Vector'], wv.outputs[0])
    n.set(vr.inputs['W'], n.math('MULTIPLY', t, 2.5))
    cracks = n.math('MULTIPLY', n.maprange(vr.outputs['Distance'], 0.0, 0.018, 1.0, 0.0), rim)
    flare = n.math('MULTIPLY', n.math('POWER', n.maprange(n1.outputs['Fac'], 0.55, 0.85, 0.0, 1.0), 3.0),
                   n.math('ADD', rim, 0.15))
    s = n.math('ADD', n.math('MULTIPLY', flare, 4.0), n.math('MULTIPLY', cracks, 7.0))
    ramp = n.node('ShaderNodeValToRGB')
    n.set(ramp.inputs[0], n.math('MINIMUM', n.math('ADD', flare, cracks), 1.0))
    els = ramp.color_ramp.elements
    els[0].color = (0.0, 0.0, 0.0, 1)
    els[1].color = (0.85, 0.95, 1.0, 1)
    e = els.new(0.4)
    e.color = (0.05, 0.2, 1.0, 1)
    em = n.node('ShaderNodeEmission')
    n.set(em.inputs['Color'], ramp.outputs[0])
    n.set(em.inputs['Strength'], s)
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], em.outputs[0])
    return m


def _tear_edge_mat(name, size):
    """Shredded, white-hot edge: bright at the cut, flickering, fading outward."""
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    attr = n.node('ShaderNodeAttribute', attribute_name='edge')
    nz = n.node('ShaderNodeTexNoise', Scale=9.0 / size, Detail=8.0, Roughness=0.7)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 4.0))
    k = n.math('POWER', attr.outputs['Fac'], 3.0)
    flick = n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.3, 1.8)
    s = n.math('MULTIPLY', n.math('MULTIPLY', k, flick), 22.0)
    ramp = n.node('ShaderNodeValToRGB')
    n.set(ramp.inputs[0], k)
    els = ramp.color_ramp.elements
    els[0].color = (0.02, 0.1, 0.6, 1)
    els[1].color = (0.92, 0.97, 1.0, 1)
    BP._add_out(n, s, ramp.outputs[0])
    return m


def _warp_mat(name, size):
    """Space round the wound, crumpled: a clear refracting sheet with a violent bump."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    n = BP._NT(m)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    attr = n.node('ShaderNodeAttribute', attribute_name='edge')
    nz = n.node('ShaderNodeTexNoise', Scale=4.0 / size, Detail=6.0, Distortion=0.8)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 0.8))
    bump = n.node('ShaderNodeBump')
    n.set(bump.inputs['Height'], nz.outputs['Fac'])
    n.set(bump.inputs['Strength'], n.math('MULTIPLY', attr.outputs['Fac'], 1.0))
    bump.inputs['Distance'].default_value = size * 0.05
    gl = n.node('ShaderNodeBsdfRefraction')
    gl.inputs['IOR'].default_value = 1.12
    gl.inputs['Roughness'].default_value = 0.0
    n.set(gl.inputs['Normal'], bump.outputs['Normal'])
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], attr.outputs['Fac'])
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], gl.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], mx.outputs[0])
    return m


def _ribbon(name, inner, outer, z, attr_in=1.0, attr_out=0.0):
    """Mesh between two outlines (same point count) with an 'edge' attribute 1 at inner, 0 at outer."""
    me = bpy.data.meshes.new(name)
    nseg = len(inner)
    verts = [(x, y, z) for x, y in inner] + [(x, y, z) for x, y in outer]
    faces = [(i, (i + 1) % nseg, nseg + (i + 1) % nseg, nseg + i) for i in range(nseg)]
    me.from_pydata(verts, [], faces)
    at = me.attributes.new('edge', 'FLOAT', 'POINT')
    for i in range(2 * nseg):
        at.data[i].value = attr_in if i < nseg else attr_out
    return _obj(name, me)


def terran_tear(name, at, normal, size, f_rip, f_shut, seed=21):
    """Space ripped open at `at`, facing `normal`, `size` = half-width of the open hole (world).
    Rips open in four jerks from f_rip (about 0.5 s), stays open shaking, slams shut at f_shut.
    Returns (root, opening_value(f)) where opening_value gives 0..1 for the ships' timing."""
    import space as SP
    import common as C
    rnd = random.Random(seed)
    root = bpy.data.objects.new(name, None)
    SP.link(root)
    root.location = at
    root.rotation_mode = 'QUATERNION'
    root.rotation_quaternion = Vector(normal).normalized().to_track_quat('Z', 'Y')
    out_line, claws = _tear_outline(rnd)
    hole = [(x * size, y * size) for x, y in out_line]
    # inside of the wound (a fan), the burning edge band, the crumpled space round it
    me = bpy.data.meshes.new(name + 'In')
    me.from_pydata([(0, 0, -1.0)] + [(x, y, -1.0) for x, y in hole], [],
                   [(0, i + 1, (i + 1) % len(hole) + 1) for i in range(len(hole))])
    at_ = me.attributes.new('edge', 'FLOAT', 'POINT')
    for i in range(len(me.vertices)):
        at_.data[i].value = 0.0 if i == 0 else 1.0
    inside = _obj(name + 'In', me)
    inside.data.materials.append(_tear_inside_mat(name + 'InM', size))
    wid = [1.04 + 0.1 * rnd.random() ** 3 for _ in hole]
    edge_out = [(x * w, y * w) for (x, y), w in zip(hole, wid)]
    edge = _ribbon(name + 'Edge', hole, edge_out, 0.0)
    edge.data.materials.append(_tear_edge_mat(name + 'EdgeM', size))
    warp_out = [(x * 2.3, y * 2.3) for x, y in hole]
    warp = _ribbon(name + 'Warp', edge_out, warp_out, 0.5)
    warp.data.materials.append(_warp_mat(name + 'WarpM', size))
    for ob in (inside, edge, warp):
        ob.parent = root
    # opening in jerks: each pull snaps wider, overshoots a little, sags back
    jerks = [(0, 0.0), (2, 0.18), (4, 0.14), (7, 0.42), (9, 0.36), (12, 0.7), (14, 0.63), (17, 1.05), (20, 1.0)]
    open_keys = [(1, (0.02, 0.0, 1.0)), (f_rip - 1, (0.02, 0.0, 1.0))]
    for df, v in jerks:
        open_keys.append((f_rip + df, (0.25 + 0.75 * v, max(0.003, v), 1.0)))
    for f in range(f_rip + 22, f_shut, 3):                   # never still: it strains, shudders
        w = 1.0 + 0.025 * math.sin(f * 1.9) + 0.015 * math.sin(f * 4.3)
        open_keys.append((f, (w, w * (1.0 + 0.02 * math.sin(f * 2.7)), 1.0)))
    open_keys += [(f_shut, (1.0, 1.0, 1.0)), (f_shut + 2, (0.3, 1.06, 1.0)), (f_shut + 4, (0.01, 0.55, 1.0)),
                  (f_shut + 5, (0.002, 0.05, 1.0))]
    SP.key_scale(root, open_keys, 'LINEAR')
    SP.show(root, f_rip, f_shut + 5)
    # strands of space stretched across the gap, snapping one by one as it is pulled open
    sm = SP.emit(name + 'StrandM', (0.75, 0.88, 1.0), 14.0)
    for k in range(14):
        i = rnd.randrange(len(hole))
        j = (i + rnd.choice((1, -1)) * rnd.randint(len(hole) // 8, len(hole) // 4)) % len(hole)
        p0 = Vector((*hole[i], 0.2))
        p1 = Vector((*hole[j], 0.2))
        mid = (p0 + p1) / 2
        d = p1 - p0
        st = C.uv_sphere(f'{name}Strand{k}', 1.0, seg=(8, 4), mat=sm, scale=(d.length / 2, size * 0.0025, size * 0.0025))
        st.parent = root
        st.location = mid
        st.rotation_mode = 'QUATERNION'
        st.rotation_quaternion = d.to_track_quat('X', 'Z')
        f_snap = f_rip + [2, 7, 12, 17][k % 4] + rnd.randint(0, 2)
        SP.show(st, f_rip, f_snap)
        st.visible_shadow = False
    # where the force has hold: fans of strained, glowing fibres dragged outward from the edge
    cm = SP.emit(name + 'ClawM', (0.6, 0.8, 1.0), 9.0)
    for ci, c in enumerate(claws):
        p = Vector((*hole[c], 0.1))
        out_d = Vector((p.x / 0.62, p.y / 1.15, 0)).normalized()
        side = Vector((-out_d.y, out_d.x, 0))
        for q in range(5):
            ln_ = size * rnd.uniform(0.35, 0.8)
            d = (out_d + side * rnd.uniform(-0.35, 0.35)).normalized()
            st = C.uv_sphere(f'{name}Claw{ci}_{q}', 1.0, seg=(8, 4), mat=cm,
                             scale=(ln_ / 2, size * 0.004, size * 0.004))
            st.parent = root
            st.location = p + d * ln_ / 2 + side * size * rnd.uniform(-0.04, 0.04)
            st.rotation_mode = 'QUATERNION'
            st.rotation_quaternion = d.to_track_quat('X', 'Z')
            st.visible_shadow = False
            SP.show(st, f_rip + 1, f_shut + 1)
    # shards of space breaking off like glass at each pull
    gm = bpy.data.materials.new(name + 'ShardM')
    gm.use_nodes = True
    b = gm.node_tree.nodes['Principled BSDF']
    b.inputs['Transmission Weight'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.0
    b.inputs['IOR'].default_value = 1.35
    b.inputs['Emission Color'].default_value = (0.4, 0.7, 1.0, 1)
    b.inputs['Emission Strength'].default_value = 0.6
    for k in range(70):
        i = rnd.randrange(len(hole))
        p = Vector((*edge_out[i], 0.0))
        out_d = Vector((p.x / 0.62, p.y / 1.15, 0)).normalized()
        f0 = f_rip + [2, 7, 12, 17][k % 4]
        mme = bpy.data.meshes.new(f'{name}Shard{k}')
        s_ = size * rnd.uniform(0.03, 0.09)
        mme.from_pydata([(0, 0, 0), (s_, rnd.uniform(-0.3, 0.3) * s_, 0), (rnd.uniform(0.1, 0.6) * s_, s_ * rnd.uniform(0.6, 1.2), 0)],
                        [], [(0, 1, 2)])
        mme.materials.append(gm)
        sh = _obj(f'{name}Shard{k}', mme)
        sh.parent = root
        sp_ = size * rnd.uniform(0.02, 0.05)
        SP.key_loc(sh, [(f0, p), (f0 + 30, p + out_d * sp_ * 30 + Vector((0, 0, rnd.uniform(-1, 1) * size * 0.3)))], 'LINEAR')
        SP.key_rot(sh, [(f0, (0, 0, 0)), (f0 + 30, (rnd.uniform(-400, 400), rnd.uniform(-400, 400), rnd.uniform(-400, 400)))],
                   'LINEAR')
        SP.show(sh, f0, f0 + 30)
    # its light on everything round it
    L = bpy.data.objects.new(name + 'Light', bpy.data.lights.new(name + 'Light', 'POINT'))
    SP.link(L)
    L.location = Vector(at) + Vector(normal).normalized() * size * 0.6
    L.data.color = (0.55, 0.75, 1.0)
    L.data.shadow_soft_size = size * 0.5
    for f, e in [(1, 0), (f_rip, 0), (f_rip + 2, 2e6), (f_rip + 4, 6e5), (f_rip + 7, 3e6), (f_rip + 9, 1e6),
                 (f_rip + 12, 4e6), (f_rip + 17, 6e6), (f_rip + 22, 3e6), (f_shut, 3e6), (f_shut + 5, 0)]:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=f)
    SP.lin(L.data)
    return root
