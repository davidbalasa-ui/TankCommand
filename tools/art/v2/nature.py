"""Scenery pipeline (art pass 8): sculpted high-poly rocks baked down onto light game meshes.

forge.finish() bakes procedural shaders onto the same mesh it exports. For rocks that leaves every
crack, ledge and chip to the triangle budget. Here each body is built twice:

  high  a dense sculpt (fracture planes, strata ledges, cracks, chips, grain) with a rich shader
        (lichen, moss, dust in crevices, iron stains, soil at the foot)
  low   the same body decimated to a few hundred triangles

and finish() bakes colour, normal, roughness, AO and glow from high to low (selected to active),
exports one mesh with one material (plus OreGem for deposits) and renders a preview sheet with a
game-camera view, a 3/4 view and a low close-up.

    import nature as NA
    NA.begin()
    NA.rock((0, 0, 0.6), (1.3, 1.1, 0.9), 'granite', seed=3, tris=900)
    NA.finish('Boulder', out_glb, render=..., report=...)
"""
import json
import math
import os
import random

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector, noise

import forge as F

ST = dict(parts=[], mats={}, seq=0)


def begin():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    F.ST.update(parts=[], faction='nature', mats={}, group='Hull', seq=0, tread=False, tread_paths=[])
    ST.update(parts=[], mats={}, seq=0)


# ------------------------------------------------------------------ geometry
def _mesh(name, verts, faces, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [list(f) for f in faces])
    me.update()
    bm = bmesh.new()       # consistent outward normals: the high-to-low bake casts along them
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _decimate(obj, tris):
    have = len(obj.data.polygons)
    if tris >= have:
        return obj
    m = obj.modifiers.new('dec', 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = max(tris / have, 0.0005)
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return obj


def add(high, low, zone, gem=False, flat=False):
    """Register a high / low pair (low may be the same shape at game density). flat = faceted
    shading in the exported mesh (crystals)."""
    ST['seq'] += 1
    high.name = f'h{ST["seq"]}'
    low.name = f'l{ST["seq"]}'
    ST['parts'].append(dict(high=high, low=low, zone=zone, gem=gem, flat=flat))
    return high, low


def _smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(k - np.abs(a - b), 0, None) / k
    return np.minimum(a, b) - h * h * k * 0.25


def rock(c, size, zone, seed=0, tris=600, sub=None, cuts=7, chips=10, round_=0.03, lumpy=0.07,
         strata=None, cracks=1.0, grain=0.016, floor=-0.12, yaw=0.0, tilt=(0.0, 0.0), flat_top=0.0,
         taper=0.0, gem=False, crack_scale=1.0, depth=(0.6, 0.86), bed=(0.06, 0.03), facet=0.025):
    """A chiselled rock body.

    size      semi-axes (x, y, z) in metres before cuts
    cuts      big fracture planes (flat faces with crisp but slightly worn edges)
    chips     small corner chips
    round_    edge rounding as a fraction of the size (weathering)
    strata    (layers per metre, ledge depth m, seam depth m) - horizontal bedding with overhanging lips
    flat_top  bias for one near-horizontal cut on top (slab or table rock)
    taper     narrows the body towards the top (>0) or the bottom (<0)
    floor     world z the underside is flattened at (keep it under the ground line)
    """
    rnd = random.Random(seed)
    sx, sy, sz = size
    s = (sx + sy + sz) / 3
    if sub is None:
        sub = 7 if s > 0.7 else (6 if s > 0.3 else 5)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    d = np.array([v.co[:] for v in bm.verts], dtype=np.float64)
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    ax = np.array([sx, sy, sz])
    off = Vector((rnd.uniform(-90, 90), rnd.uniform(-90, 90), rnd.uniform(-90, 90)))

    def support(n):   # distance of the ellipsoid's tangent plane with normal n
        return math.sqrt((n[0] * sx) ** 2 + (n[1] * sy) ** 2 + (n[2] * sz) ** 2)
    # Base: lumpy ellipsoid.
    R = 1.0 / np.sqrt(((d / ax) ** 2).sum(1))
    low_n = np.array([noise.noise(Vector(p) * 1.1 + off) + 0.5 * noise.noise(Vector(p) * 2.3 + off * 1.3) for p in d])
    R *= 1 + lumpy * low_n
    if taper:
        R *= 1 - taper * d[:, 2] * 0.5
    k = round_ * s
    planes = []
    for i in range(cuts):
        if i == 0 and flat_top:
            n = Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 1.0)).normalized()
            u = 1.0 - flat_top * 0.35
        else:
            a = rnd.uniform(0, 2 * math.pi)
            el = rnd.uniform(-0.2, 0.7)
            n = Vector((math.cos(a), math.sin(a), el)).normalized()
            u = rnd.uniform(*depth)
        planes.append((np.array(n[:]), support(n) * u, k))
    for i in range(chips):
        n = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 1))).normalized()
        planes.append((np.array(n[:]), support(n) * rnd.uniform(0.86, 0.95), k * 0.4))
    for pi_, (n, h, kk) in enumerate(planes):
        dn = d @ n
        t = np.where(dn > 1e-4, h / np.maximum(dn, 1e-4), 1e9)
        # fracture faces are never quite flat: shallow conchoidal dishes and ripples across each one
        po = Vector((pi_ * 3.7 + 11.0, pi_ * 1.9 - 5.0, pi_ * 2.3))
        act = np.nonzero(t < R * 1.1 + kk)[0]          # only where this plane shapes the surface
        if len(act) and facet:
            q = d[act] * t[act][:, None]
            und = np.array([noise.noise(Vector(v) * (2.2 / s) + po) + 0.4 * noise.noise(Vector(v) * (5.5 / s) + po)
                            for v in q])
            t[act] = t[act] * (1 + facet * und)
        R = _smin(R, t, kk)
    p = d * R[:, None]
    # Detail along the outward direction.
    disp = np.zeros(len(d))
    M = (Matrix.Translation(Vector(c)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
         @ Matrix.Rotation(math.radians(tilt[0]), 4, 'X') @ Matrix.Rotation(math.radians(tilt[1]), 4, 'Y'))
    Mn = np.array(M)
    Rm = Mn[:3, :3]
    world = p @ Rm.T + Mn[:3, 3]          # strata and cracks live in world space, so bodies share beds
    dw = d @ Rm.T
    if strata:
        freq, ledge, seam = strata
        tv = np.array([bed[0], bed[1], 1.0])
        tv /= np.linalg.norm(tv)
        zz = world @ tv
        warp = np.array([noise.noise(Vector(q) * 0.45 + Vector((7.1, 3.3, 1.9))) for q in world]) * 0.3
        ph = zz * freq + warp + 0.3 * np.sin(zz * freq * 0.83 + 1.7)   # uneven bed thickness
        sfr = ph - np.floor(ph)
        side = np.clip(1.0 - np.abs(dw[:, 2]) * 1.1, 0, 1)
        lay = np.floor(ph)
        lay_k = np.array([0.5 + 1.0 * ((math.sin(L * 12.9898 + 4.1) * 43758.5453) % 1.0) for L in lay])
        disp -= side * ledge * lay_k * sfr ** 1.5      # each bed recedes upward: lip of the bed above overhangs
        disp -= seam * (np.exp(-(sfr / 0.07) ** 2) + np.exp(-((1 - sfr) / 0.05) ** 2)) * (0.4 + side)
    if cracks:
        cs = 1.05 / s * crack_scale
        cr = np.zeros(len(d))
        msk = np.zeros(len(d))
        for i, q in enumerate(world):
            v = Vector(q) * cs + off * 0.3
            dist, _pts = noise.voronoi(v, distance_metric='DISTANCE')
            cr[i] = dist[1] - dist[0]
            msk[i] = noise.noise(Vector(q) * (0.9 / s) + off * 0.5)
        groove = np.clip(1 - cr / 0.03, 0, 1) ** 1.5 * np.clip((msk - 0.12) * 4, 0, 1)
        disp -= groove * 0.022 * s * cracks
    if grain:
        gn = np.array([noise.noise(Vector(q) * 6.0 + off) + 0.5 * noise.noise(Vector(q) * 13.0 + off) for q in world])
        disp += gn * grain
    p = p + d * disp[:, None]
    # Pose: tilt / yaw, then place; flatten the underside below ground.
    p = p @ Rm.T + Mn[:3, 3]
    if floor is not None:
        p[:, 2] = np.maximum(p[:, 2], floor)
        # the flattened underside is never seen: drop it (saves triangles and texture space)
        under = p[:, 2] <= floor + 1e-5
        faces = [f for f in faces if not all(under[i] for i in f)]
    hi = _mesh('rock', p, faces)
    lo = hi.copy()
    lo.data = hi.data.copy()
    bpy.context.scene.collection.objects.link(lo)
    _decimate(lo, tris)
    return add(hi, lo, zone, gem)


def solid(obj, zone, gem=False, tris=None, flat=False):
    """An exact part (crystal, blade): the low mesh is the shape itself; high is a copy."""
    for p in obj.data.polygons:
        p.use_smooth = not flat
    hi = obj.copy()
    hi.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(hi)
    if tris:
        _decimate(obj, tris)
    return add(hi, obj, zone, gem, flat)


def crystal(base, h, r, yaw, lean, zone, sides=6, tip=0.28, sink=0.25, taper=0.85, broken=0.0, seed=0, gem=True):
    """Faceted crystal column growing from base: a slightly tapering prism with an uneven pointed
    termination (broken > 0 snaps the point off at a slant). Point attribute ct runs 0 root -> 1 tip."""
    rnd = random.Random(seed)
    a, l = math.radians(yaw), math.radians(lean)
    d = Vector((math.cos(a) * math.sin(l), math.sin(a) * math.sin(l), math.cos(l)))
    up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    ax = d.cross(up).normalized()
    ay = d.cross(ax).normalized()
    p0 = Vector(base) - d * min(sink * h, max(0.0, (base[2] + 0.2) / max(d.z, 0.2)))
    sink = (Vector(base) - p0).length / h
    rot0 = rnd.uniform(0, 2 * math.pi)
    radii = [r * rnd.uniform(0.82, 1.12) for _ in range(sides)]   # uneven faces, like real crystals
    rings = []
    ts = []
    for t, k in ((0.0, 1.0), (1 - tip, taper)):
        c = p0 + d * ((h + sink * h) * t)
        rings.append([c + (ax * math.cos(rot0 + 2 * math.pi * i / sides) + ay * math.sin(rot0 + 2 * math.pi * i / sides)) * radii[i] * k
                      for i in range(sides)])
        ts.append(t)
    verts = [v for ring in rings for v in ring]
    ct = [0.0] * sides + [1 - tip] * sides
    faces = [[i, (i + 1) % sides, sides + (i + 1) % sides, sides + i] for i in range(sides)]
    faces.append(list(range(sides))[::-1])
    top = p0 + d * (h + sink * h)
    if broken > 0:
        # slanted fracture through the upper body
        n = (d + ax * rnd.uniform(-0.6, 0.6) + ay * rnd.uniform(-0.6, 0.6)).normalized()
        cut = p0 + d * ((h + sink * h) * (1 - tip - broken * 0.3))
        for i in range(sides, 2 * sides):
            v = verts[i]
            # slide the upper ring down along the axis onto the fracture plane
            t_ = (cut - v).dot(n) / max(d.dot(n), 0.2)
            verts[i] = v + d * t_
            ct[i] = 1 - tip - broken * 0.3
        faces.append(list(range(sides, 2 * sides)))
    else:
        off = (ax * rnd.uniform(-0.3, 0.3) + ay * rnd.uniform(-0.3, 0.3)) * r
        verts.append(top + off)
        ct.append(1.0)
        apex = len(verts) - 1
        for i in range(sides):
            faces.append([sides + i, sides + (i + 1) % sides, apex])
    o = _mesh('crystal', verts, faces, smooth=False)
    att = o.data.attributes.new('ct', 'FLOAT', 'POINT')
    att.data.foreach_set('value', ct)
    return solid(o, zone, gem=gem, flat=True)


def strand(pts, widths, zone, sides=6, up=(0, 0, 1), flat=1.0, sv=None, caps=True, twist=0.0, gem=False):
    """Tube / blade along a path. widths = radius per point (or (w, h) pairs; flat squashes h).
    Point attributes: st 0 root -> 1 tip, sv one random value per strand (for colour variation)."""
    P = [Vector(p) for p in pts]
    upv = Vector(up).normalized()
    verts, st = [], []
    n = len(P)
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    side_prev = None
    for i, p in enumerate(P):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        side = t.cross(upv)
        if side.length < 1e-6:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        if side_prev is not None and side.dot(side_prev) < 0:
            side = -side
        side_prev = side
        nrm = side.cross(t).normalized()
        w = widths[i]
        w, h = (w if isinstance(w, (tuple, list)) else (w, w * flat))
        for k in range(sides):
            a = 2 * math.pi * k / sides + twist * i / max(n - 1, 1)
            verts.append(p + side * (w * math.cos(a)) + nrm * (h * math.sin(a)))
            st.append(L[i] / max(L[-1], 1e-6))
    faces = []
    for i in range(n - 1):
        for k in range(sides):
            j = (k + 1) % sides
            faces.append([i * sides + k, i * sides + j, (i + 1) * sides + j, (i + 1) * sides + k])
    if caps:
        faces.append(list(range(sides))[::-1])
        tipw = widths[-1] if not isinstance(widths[-1], (tuple, list)) else widths[-1][0]
        if tipw > 0.004:
            faces.append(list(range((n - 1) * sides, n * sides)))
    o = _mesh('strand', verts, faces)
    a1 = o.data.attributes.new('st', 'FLOAT', 'POINT')
    a1.data.foreach_set('value', st)
    a2 = o.data.attributes.new('sv', 'FLOAT', 'POINT')
    a2.data.foreach_set('value', [sv if sv is not None else 0.5] * len(verts))
    return solid(o, zone, gem=gem)


def ribbon(pts, widths, zone, fold=0.3, sv=None, up=(0, 0, 1)):
    """Open blade (grass): three verts across, folded along the midrib; rendered double-sided."""
    P = [Vector(p) for p in pts]
    upv = Vector(up)
    n = len(P)
    verts, st = [], []
    for i, p in enumerate(P):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        side = t.cross(upv)
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        nrm = side.cross(t).normalized()
        w = widths[i]
        verts += [p - side * w + nrm * (w * fold), p, p + side * w + nrm * (w * fold)]
        st += [i / (n - 1)] * 3
    faces = []
    for i in range(n - 1):
        a = i * 3
        faces += [[a, a + 1, a + 4, a + 3], [a + 1, a + 2, a + 5, a + 4]]
    o = _mesh('blade', verts, faces)
    a1 = o.data.attributes.new('st', 'FLOAT', 'POINT')
    a1.data.foreach_set('value', st)
    a2 = o.data.attributes.new('sv', 'FLOAT', 'POINT')
    a2.data.foreach_set('value', [sv if sv is not None else 0.5] * len(verts))
    return solid(o, zone)


def attr(n, name):
    a = n.nt.nodes.new('ShaderNodeAttribute')
    a.attribute_name = name
    return a.outputs['Fac']


def from_forge(obj, zone=None, gem=False):
    """Adopt a forge primitive (built with F.tube / F.sweep ...) as an exact part."""
    if obj in F.ST['parts']:
        F.ST['parts'].remove(obj)
    return solid(obj, zone or obj['zone'], gem)


# ------------------------------------------------------------------ shaders
PAL = {
    # dark, light, warm accent  (linear)
    'granite': dict(dark=(0.05, 0.046, 0.042), light=(0.25, 0.23, 0.2), warm=(0.3, 0.2, 0.12), lichen=1.0, moss=0.7,
                    strata=0.25, iron=0.5, soil=1.0),
    'sandstone': dict(dark=(0.11, 0.075, 0.05), light=(0.36, 0.27, 0.18), warm=(0.42, 0.22, 0.1), lichen=0.7, moss=0.45,
                      strata=0.9, iron=0.8, soil=1.0),
    'crag': dict(dark=(0.075, 0.064, 0.054), light=(0.28, 0.25, 0.205), warm=(0.36, 0.2, 0.09), lichen=0.8, moss=0.5,
                 strata=0.85, iron=0.7, soil=1.0),
    'hostteal': dict(dark=(0.03, 0.03, 0.035), light=(0.12, 0.12, 0.12), warm=(0.1, 0.09, 0.1), lichen=0.3, moss=0.3,
                     strata=0.2, iron=0.0, soil=1.0, vein=(0.12, 0.7, 0.5)),
    'hostred': dict(dark=(0.06, 0.025, 0.022), light=(0.22, 0.1, 0.075), warm=(0.3, 0.1, 0.05), lichen=0.0, moss=0.0,
                    strata=0.4, iron=0.6, soil=1.0, vein=(1.0, 0.08, 0.35)),
    'hostdark': dict(dark=(0.03, 0.032, 0.04), light=(0.13, 0.13, 0.15), warm=(0.12, 0.1, 0.12), lichen=0.0, moss=0.0,
                     strata=0.3, iron=0.0, soil=1.0, vein=(0.1, 0.45, 1.0)),
}
SOIL = (0.085, 0.07, 0.045)
GROUND_TOP = 0.0


def _wave_z(n, scale, distortion, co=None):
    w = n.nt.nodes.new('ShaderNodeTexWave')
    w.wave_type = 'BANDS'
    w.bands_direction = 'Z'
    w.inputs['Scale'].default_value = scale
    w.inputs['Distortion'].default_value = distortion
    w.inputs['Detail'].default_value = 3.0
    n.link(co or n.co, w.inputs['Vector'])
    return w.outputs[0]


def _ao_node(n, dist=0.5, ground=0.0):
    """Self-occlusion, plus (ground > 0) the darkening the ground itself casts on the foot."""
    a = n.nt.nodes.new('ShaderNodeAmbientOcclusion')
    a.only_local = True
    a.samples = 16
    a.inputs['Distance'].default_value = dist
    a.name = 'AONode'
    out = a.outputs['AO']
    if ground:
        zz = n.sep(n.co)[2]
        gf = n.m('ADD', 1.0 - ground, n.m('MULTIPLY', n.smooth(zz, -0.08, ground * 0.9), ground))
        out = n.m('MULTIPLY', out, gf)
    fin = n.nt.nodes.new('ShaderNodeMath')
    fin.operation = 'MULTIPLY'
    fin.name = 'AOOut'
    n.link(out, fin.inputs[0])
    fin.inputs[1].default_value = 1.0
    return a


def _geo(n):
    if not hasattr(n, '_g'):
        n._g = n.nt.nodes.new('ShaderNodeNewGeometry')
    return n._g


def rock_mat(zone, scale=1.0, ao_dist=0.6):
    key = f'{zone}@{scale}'
    if key in ST['mats']:
        return ST['mats'][key]
    z = PAL[zone]
    mat = bpy.data.materials.new(f'n_{zone}')
    mat.use_nodes = True
    n = F.N(mat)
    S = scale
    dark, light, warm = z['dark'], z['light'], z['warm']
    big = n.noise(0.45 / S, 4.0)
    mid = n.noise(2.2 / S, 6.0)
    fine = n.noise(18.0 / S, 6.0, rough=0.6)
    col = n.mix(n.smooth(n.m('ADD', n.m('MULTIPLY', big, 0.7), n.m('MULTIPLY', mid, 0.3)), 0.3, 0.72), dark, light)
    hue = n.smooth(n.noise(0.9 / S, 3.0), 0.35, 0.65)
    col = n.mix(n.m('MULTIPLY', hue, 0.5), col, n.mix(0.5, col, (warm[0] * 0.7, warm[1] * 0.7, warm[2] * 0.7)))
    # bedding colour bands
    bands = _wave_z(n, 1.6 / S, 4.0)
    col = n.mix(n.m('MULTIPLY', n.m('MULTIPLY', n.smooth(bands, 0.35, 0.85), n.smooth(n.noise(0.7 / S, 2.0), 0.3, 0.7)), z['strata'] * 0.45), col,
                (light[0] * 1.25, light[1] * 1.18, light[2] * 1.05))
    col = n.mix(n.m('MULTIPLY', n.smooth(_wave_z(n, 4.3 / S, 6.0), 0.75, 0.95), z['strata'] * 0.6), col,
                (dark[0] * 0.8, dark[1] * 0.75, dark[2] * 0.7))
    # mineral speckle and mottling
    spk = n.smooth(n.noise(90.0 / S, 2.0), 0.6, 0.68)
    col = n.mix(n.m('MULTIPLY', spk, 0.25), col, (light[0] * 1.3, light[1] * 1.3, light[2] * 1.3))
    mott = n.smooth(n.noise(7.0 / S, 6.0), 0.35, 0.75)
    col = n.mix(n.m('MULTIPLY', mott, 0.45), col, (dark[0] * 0.8, dark[1] * 0.8, dark[2] * 0.8))
    g = _geo(n)
    pt = g.outputs['Pointiness']
    convex = n.smooth(pt, 0.505, 0.55)
    concave = n.smooth(n.m('SUBTRACT', 1.0, pt), 0.503, 0.54)
    up = n.sep(g.outputs['Normal'])[2]
    upk = n.smooth(up, 0.25, 0.8)
    # iron / water stains running down the faces
    streak_co = n.vscale(n.co, (3.0 / S, 3.0 / S, 0.35 / S))
    streak = n.smooth(n.noise(1.0, 4.0, co=streak_co), 0.55, 0.72)
    side = n.m('SUBTRACT', 1.0, upk)
    col = n.mix(n.m('MULTIPLY', n.m('MULTIPLY', streak, side), z['iron'] * 0.55), col, warm)
    dstreak = n.smooth(n.noise(1.0, 4.0, co=n.vscale(n.co, (5.0 / S, 5.0 / S, 0.5 / S))), 0.6, 0.75)
    col = n.mix(n.m('MULTIPLY', n.m('MULTIPLY', dstreak, side), 0.35), col, (dark[0] * 0.6, dark[1] * 0.6, dark[2] * 0.6))
    # fresh, lighter rock on worn convex edges; grime in the hollows
    col = n.mix(n.m('MULTIPLY', convex, 0.55), col, (light[0] * 1.55, light[1] * 1.5, light[2] * 1.42))
    col = n.mix(n.m('MULTIPLY', concave, 0.9), col, (dark[0] * 0.3, dark[1] * 0.28, dark[2] * 0.26))
    # dust settled in up-facing hollows and ledges
    dust = n.m('MULTIPLY', n.m('MULTIPLY', n.smooth(up, 0.55, 0.9), n.m('ADD', 0.35, concave)),
               n.smooth(n.noise(3.0 / S, 5.0), 0.4, 0.6))
    col = n.mix(n.m('MULTIPLY', dust, 0.8, clamp=True), col, (0.26, 0.21, 0.15))
    rough = n.m('ADD', 0.8, n.m('MULTIPLY', fine, 0.12))
    height = n.m('ADD', n.m('MULTIPLY', fine, 0.6), n.m('MULTIPLY', n.noise(55.0 / S, 3.0), 0.25))
    if z['lichen'] > 0:
        patch = n.smooth(n.noise(1.3 / S, 3.0), 0.5, 0.62)
        crust = n.smooth(n.noise(14.0 / S, 8.0, rough=0.7), 0.5, 0.56)
        lich = n.m('MULTIPLY', n.m('MULTIPLY', patch, crust), n.smooth(up, -0.1, 0.5))
        lich = n.m('MULTIPLY', lich, z['lichen'], clamp=True)
        lcol = n.mix(n.smooth(n.noise(4.0 / S, 2.0), 0.4, 0.6), (0.15, 0.17, 0.1), (0.3, 0.32, 0.22))
        col = n.mix(lich, col, lcol)
        orange = n.m('MULTIPLY', n.smooth(n.noise(9.0 / S, 6.0), 0.66, 0.7), n.smooth(n.noise(0.8 / S, 2.0), 0.58, 0.66))
        orange = n.m('MULTIPLY', orange, n.m('MULTIPLY', upk, z['lichen']), clamp=True)
        col = n.mix(orange, col, (0.5, 0.2, 0.035))
        height = n.m('ADD', height, n.m('MULTIPLY', lich, 0.5))
        rough = n.m('ADD', rough, n.m('MULTIPLY', lich, 0.1))
    if z['moss'] > 0:
        mp = n.m('MULTIPLY', n.smooth(up, 0.45, 0.85), n.smooth(n.noise(2.0 / S, 5.0), 0.5, 0.6))
        mp = n.m('MULTIPLY', mp, n.m('ADD', 0.4, concave))
        mp = n.m('MULTIPLY', mp, z['moss'] * 1.6, clamp=True)
        mcol = n.mix(n.smooth(n.noise(25.0 / S, 4.0), 0.35, 0.65), (0.035, 0.06, 0.018), (0.1, 0.15, 0.04))
        col = n.mix(mp, col, mcol)
        height = n.m('ADD', height, n.m('MULTIPLY', mp, n.m('MULTIPLY', n.noise(40.0 / S, 3.0), 0.8)))
    # soil and dust creeping up the foot, so the rock sits in the ground
    zz = n.sep(n.co)[2]
    edge = n.m('ADD', zz, n.m('MULTIPLY', n.m('SUBTRACT', n.noise(4.0 / S, 4.0), 0.5), 0.12 * S))
    foot = n.m('SUBTRACT', 1.0, n.smooth(edge, GROUND_TOP + 0.02, GROUND_TOP + 0.3 * S))
    col = n.mix(n.m('MULTIPLY', foot, z['soil'] * 0.92, clamp=True), col, SOIL)
    rough = n.m('ADD', rough, n.m('MULTIPLY', foot, 0.1))
    if 'vein' in z:
        e = z['vein']
        vc = n.voronoi(1.3 / S, 'DISTANCE_TO_EDGE', co=n.vscale(n.co, (1.0, 1.0, 1.6))).outputs['Distance']
        vein = n.m('SUBTRACT', 1.0, n.smooth(vc, 0.0, 0.016))
        near = n.m('SUBTRACT', 1.0, n.smooth(n.m('ADD', n.m('MULTIPLY', zz, 0.5),
                                                  n.m('MULTIPLY', n.noise(1.5, 3.0), 0.6)), 0.3, 0.75))
        lv = n.nt.nodes.new('ShaderNodeVectorMath')     # only round the crystal heart (and its satellites)
        lv.operation = 'LENGTH'
        n.link(n.vscale(n.co, (1.0, 1.0, 0.0)), lv.inputs[0])
        rad = n.m('SUBTRACT', 1.0, n.smooth(n.m('ADD', lv.outputs['Value'], n.m('MULTIPLY', n.noise(2.0, 2.0), 0.8)), 1.0, 2.0))
        near = n.m('MULTIPLY', near, n.m('ADD', rad, n.m('MULTIPLY', n.smooth(n.noise(3.0 / S, 2.0), 0.55, 0.65), 0.6)))
        vein = n.m('MULTIPLY', vein, near, clamp=True)
        col = n.mix(n.m('MULTIPLY', vein, 0.8), col, (e[0] * 0.6, e[1] * 0.6, e[2] * 0.6))
        n.out(emit=e, emit_strength=n.m('MULTIPLY', vein, 1.4))
        height = n.m('SUBTRACT', height, n.m('MULTIPLY', vein, 0.6))
    n.out(col, rough, 0.0)
    n.bump(height, 0.35, 0.01 * S, soft=False)
    _ao_node(n, ao_dist * S, ground=0.45 * S)
    ST['mats'][key] = mat
    return mat


def gem_mat(name, base, base2, emit, strength=1.0, swirl=1.0, opal=False, height=2.0):
    """Crystal: deep body colour, lighter towards the tip, a swirling inner glow brightest at the root."""
    key = f'gem:{name}'
    if key in ST['mats']:
        return ST['mats'][key]
    mat = bpy.data.materials.new(f'n_{name}')
    mat.use_nodes = True
    n = F.N(mat)
    zz = n.sep(n.co)[2]
    at = n.nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'ct'
    tip = n.m('MAXIMUM', at.outputs['Fac'], n.smooth(zz, 0.0, height))
    # swirl: noise in a twisted coordinate frame
    tw = n.nt.nodes.new('ShaderNodeVectorMath')
    tw.operation = 'ADD'
    n.link(n.co, tw.inputs[0])
    wn = n.nt.nodes.new('ShaderNodeTexNoise')
    wn.inputs['Scale'].default_value = 1.4
    wn.inputs['Detail'].default_value = 3.0
    n.link(n.co, wn.inputs['Vector'])
    n.link(n.vscale(wn.outputs['Color'], (1.6 * swirl, 1.6 * swirl, 1.6 * swirl)), tw.inputs[1])
    sw = n.wave(1.3, 7.0, 3.0, 1.5, co=tw.outputs[0])
    swb = n.smooth(sw, 0.25, 0.85)
    swl = n.m('SUBTRACT', 1.0, n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', sw, 0.5)), 0.04, 0.14))   # thin swirl filaments
    col = n.mix(n.m('ADD', n.m('MULTIPLY', tip, 0.35), n.m('MULTIPLY', swb, 0.25), clamp=True), base, base2)
    col = n.mix(n.m('MULTIPLY', swl, 0.45), col, base2)
    if opal:
        fl = n.voronoi(9.0, 'F1', co=tw.outputs[0])
        flc = fl.outputs['Color']
        flk = n.smooth(n.noise(5.0, 2.0, co=tw.outputs[0]), 0.5, 0.65)
        col = n.mix(n.m('MULTIPLY', flk, 0.55), col, flc)
        col = n.mix(n.m('MULTIPLY', n.smooth(n.noise(3.0, 3.0), 0.55, 0.7), 0.5), col, (0.25, 0.85, 0.75))
    g = _geo(n)
    lw = n.nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    col = n.mix(n.m('MULTIPLY', lw.outputs[1], 0.25), col, (0.9, 0.9, 1.0))
    # facet edges catch light
    pt = g.outputs['Pointiness']
    col = n.mix(n.m('MULTIPLY', n.smooth(pt, 0.53, 0.62), 0.6), col, base2)
    root = n.m('SUBTRACT', 1.0, tip)
    glow = n.m('ADD', n.m('MULTIPLY', n.m('POWER', root, 2.0), 0.6), n.m('MULTIPLY', swl, n.m('SUBTRACT', 0.5, n.m('MULTIPLY', tip, 0.25))))
    glow = n.m('MULTIPLY', glow, n.m('ADD', 0.55, n.m('MULTIPLY', n.noise(3.0, 2.0), 0.5)))
    n.out(col, n.m('ADD', 0.12, n.m('MULTIPLY', n.noise(20.0, 3.0), 0.1)), 0.0, emit, n.m('MULTIPLY', glow, strength))
    n.bump(n.m('MULTIPLY', n.noise(30.0, 2.0), 0.3), 0.15, 0.005, soft=False)
    _ao_node(n, 0.4)
    ST['mats'][key] = mat
    return mat


def plain_mat(zone):
    """Fallback: forge's own zone shader with an AO node added (vegetation)."""
    key = f'f:{zone}'
    if key in ST['mats']:
        return ST['mats'][key]
    mat = F.zone_mat(zone).copy()
    n = F.N(mat)
    n.nt = mat.node_tree
    _ao_node(n, 0.3)
    ST['mats'][key] = mat
    return mat


MATS = {}   # zone name -> callable returning a material (filled by asset scripts)


def material_for(zone):
    if zone in MATS:
        return MATS[zone]()
    if zone in PAL:
        return rock_mat(zone)
    return plain_mat(zone)


# ------------------------------------------------------------------ bake
def _bake(low, kind, size, ext, samples, **kw):
    scene = bpy.context.scene
    scene.cycles.samples = samples
    img = bpy.data.images.new(f'bake_{kind}', size, size, alpha=False, float_buffer=True)
    if kind == 'NORMAL':
        img.colorspace_settings.name = 'Non-Color'
    nt = low.material_slots[0].material.node_tree
    node = nt.nodes.get('BakeTarget') or nt.nodes.new('ShaderNodeTexImage')
    node.name = 'BakeTarget'
    node.image = img
    for x in nt.nodes:
        x.select = False
    node.select = True
    nt.nodes.active = node
    bpy.ops.object.bake(type=kind, margin=max(6, size // 64), use_clear=True, use_selected_to_active=True,
                        cage_extrusion=ext, max_ray_distance=ext * 3, **kw)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)
    bpy.data.images.remove(img)
    return arr


def _route_all(highs, what):
    done = set()
    for h in highs:
        for slot in h.material_slots:
            mat = slot.material
            if mat.name in done:
                continue
            done.add(mat.name)
            nt = mat.node_tree
            if 'orig_links' not in mat:
                pass
            bsdf = nt.nodes['Principled BSDF']
            ec, es = bsdf.inputs['Emission Color'], bsdf.inputs['Emission Strength']
            # remember the glow wiring once
            if not hasattr(_route_all, 'saved'):
                _route_all.saved = {}
            if mat.name not in _route_all.saved:
                _route_all.saved[mat.name] = (
                    ec.links[0].from_socket if ec.is_linked else tuple(ec.default_value),
                    es.links[0].from_socket if es.is_linked else es.default_value)
            for link in list(nt.links):
                if link.to_socket in (ec, es):
                    nt.links.remove(link)
            es.default_value = 1.0
            if what == 'glow':
                src_c, src_s = _route_all.saved[mat.name]
                if isinstance(src_c, tuple):
                    ec.default_value = src_c
                else:
                    nt.links.new(src_c, ec)
                if isinstance(src_s, float):
                    es.default_value = src_s
                else:
                    nt.links.new(src_s, es)
            elif what == 'AO':
                nt.links.new(nt.nodes['AOOut'].outputs[0], ec)
            else:
                src = bsdf.inputs[what]
                if src.is_linked:
                    nt.links.new(src.links[0].from_socket, ec)
                else:
                    v = src.default_value
                    ec.default_value = (v[0], v[1], v[2], 1) if hasattr(v, '__len__') else (v, v, v, 1)


def finish(name, out_glb, render=None, report=None, label=None, size=512, supersample=2, ext=0.06,
           ao_floor=0.28, ao_gamma=1.1, views=None, gem_name='OreGem', tangents=True, frame=None, double=False):
    _route_all.saved = {}
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.use_denoising = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new('w')
    parts = ST['parts']
    bake_mat = bpy.data.materials.new('BakeLow')
    bake_mat.use_nodes = True
    highs, lows = [], []
    for p in parts:
        h, l = p['high'], p['low']
        h.data.materials.clear()
        h.data.materials.append(material_for(p['zone']))
        l.data.materials.clear()
        l.data.materials.append(bake_mat)
        att = l.data.attributes.new('gem', 'INT', 'FACE')
        att.data.foreach_set('value', [(1 if p['gem'] else 0) + (2 if p['flat'] else 0)] * len(l.data.polygons))
        highs.append(h)
        lows.append(l)
    bpy.ops.object.select_all(action='DESELECT')
    for l in lows:
        l.select_set(True)
    bpy.context.view_layer.objects.active = lows[0]
    if len(lows) > 1:
        bpy.ops.object.join()
    low = bpy.context.view_layer.objects.active
    low.name = name
    me = low.data
    me.name = name
    bm = bmesh.new()       # triangles throughout, so the exporter can write tangents
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(me)
    bm.free()
    while len(me.uv_layers) > 0:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(margin=0.006, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    tris = F.tri_count(low)
    # high objects into one (shader per zone kept via slots)
    bpy.ops.object.select_all(action='DESELECT')
    for h in highs:
        h.select_set(True)
    bpy.context.view_layer.objects.active = highs[0]
    if len(highs) > 1:
        bpy.ops.object.join()
    high = bpy.context.view_layer.objects.active
    high.name = name + '_high'
    hightris = F.tri_count(high)
    bpy.ops.object.select_all(action='DESELECT')
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bs = size * supersample
    _route_all([high], 'AO')
    ao = _bake(low, 'EMIT', size, ext, 48)
    _route_all([high], 'glow')
    emit = _bake(low, 'EMIT', bs, ext, 4)
    rough = _bake(low, 'ROUGHNESS', bs, ext, 4)
    normal = _bake(low, 'NORMAL', bs, ext, 4, normal_space='TANGENT')
    _route_all([high], 'Base Color')
    diffuse = _bake(low, 'EMIT', bs, ext, 4)
    k = supersample
    rough, normal, emit, diffuse = (F._down(x, k) for x in (rough, normal, emit, diffuse))
    a = np.clip(ao[..., :3], 0, 1) ** ao_gamma
    base = diffuse[..., :3] * (ao_floor + (1 - ao_floor) * a)
    nv = normal[..., :3] * 2 - 1
    nv /= np.maximum(np.linalg.norm(nv, axis=-1, keepdims=True), 1e-6)
    normal = nv * 0.5 + 0.5
    em = np.clip(emit[..., :3] / F.EMIT_SCALE, 0, 1)
    has_emit = float(em.max()) > 0.004
    orm = np.stack([np.ones_like(ao[..., 0]), np.clip(rough[..., 0], 0.04, 1), np.zeros_like(ao[..., 0])], axis=-1)   # AO is in the base colour; R unused by the game
    bake_dir = os.path.join(os.path.dirname(out_glb), '_bake')
    os.makedirs(bake_dir, exist_ok=True)
    stem = os.path.join(bake_dir, name.lower())
    imgs = {}
    for key, arr, srgb in (('base', F._srgb(base), True), ('normal', normal, False), ('orm', orm, False),
                           ('emissive', F._srgb(em), True)):
        if key == 'emissive' and not has_emit:
            continue
        F._png(f'{stem}_{key}.png', arr)
        im = bpy.data.images.load(f'{stem}_{key}.png')
        im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
        imgs[key] = im

    def final_mat(mname):
        mat = bpy.data.materials.new(mname)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes['Principled BSDF']
        t = {}
        for key in imgs:
            t[key] = nt.nodes.new('ShaderNodeTexImage')
            t[key].image = imgs[key]
        nm = nt.nodes.new('ShaderNodeNormalMap')
        sp = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(t['base'].outputs['Color'], bsdf.inputs['Base Color'])
        nt.links.new(t['normal'].outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        nt.links.new(t['orm'].outputs['Color'], sp.inputs['Color'])
        nt.links.new(sp.outputs['Green'], bsdf.inputs['Roughness'])
        bsdf.inputs['Metallic'].default_value = 0.0
        if 'emissive' in t:
            nt.links.new(t['emissive'].outputs['Color'], bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = F.EMIT_SCALE
        if double:
            mat.use_backface_culling = False
        else:
            mat.use_backface_culling = True
        return mat
    gemv = np.zeros(len(me.polygons), dtype=np.int32)
    me.attributes['gem'].data.foreach_get('value', gemv)
    isgem = (gemv & 1) > 0
    me.materials.clear()
    me.materials.append(final_mat(f'{name}Mat'))
    if isgem.any():
        me.materials.append(final_mat(gem_name))
    me.polygons.foreach_set('material_index', isgem.astype(np.int32))
    me.attributes.remove(me.attributes['gem'])
    me.polygons.foreach_set('use_smooth', ((gemv & 2) == 0).tolist())
    bpy.data.objects.remove(high)
    bpy.ops.object.select_all(action='DESELECT')
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_yup=True, export_apply=True,
                              export_image_format='JPEG', export_jpeg_quality=88, export_animations=False,
                              export_tangents=tangents, use_selection=True)
    lo = np.array([min(v.co[i] for v in me.vertices) for i in range(3)])
    hi = np.array([max(v.co[i] for v in me.vertices) for i in range(3)])
    info = dict(name=name, file=os.path.basename(out_glb), triangles=tris, high=hightris, texture=size,
                bytes=os.path.getsize(out_glb), size=[round(float(x), 2) for x in hi - lo], minz=round(float(lo[2]), 3))
    print('NATURE', json.dumps(info))
    if report:
        os.makedirs(os.path.dirname(report), exist_ok=True)
        with open(report, 'w') as f:
            json.dump(info, f)
    if render:
        preview(low, render, label or name, tris, views=views, frame=frame)
    return info


# ------------------------------------------------------------------ preview
def _ground(size, c):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(c.x, c.y, 0.0))
    g = bpy.context.object
    gm = bpy.data.materials.new('Ground')
    gm.use_nodes = True
    gn = F.N(gm)
    big = gn.noise(0.08, 4.0)
    col = gn.mix(gn.smooth(big, 0.35, 0.65), (0.05, 0.09, 0.025), (0.075, 0.11, 0.035))
    dirt = gn.smooth(gn.noise(0.5, 6.0), 0.55, 0.68)
    col = gn.mix(gn.m('MULTIPLY', dirt, 0.8), col, (0.11, 0.085, 0.05))
    blades = gn.noise(40.0, 4.0, co=gn.vscale(gn.co, (1.0, 1.0, 1.0)))
    col = gn.mix(gn.m('MULTIPLY', gn.smooth(blades, 0.55, 0.7), 0.4), col, (0.13, 0.15, 0.05))
    gn.out(col, 0.95, 0.0)
    gn.bump(gn.m('ADD', blades, gn.m('MULTIPLY', gn.noise(6.0, 6.0), 0.5)), 0.6, 0.02, soft=False)
    g.data.materials.append(gm)
    return g


def _look(cam, loc, target, lens):
    cam.location = loc
    dd = Vector(target) - Vector(loc)
    cam.rotation_euler = (math.atan2(math.hypot(dd.x, dd.y), -dd.z), 0, math.atan2(dd.y, dd.x) - math.pi / 2)
    cam.data.lens = lens


def preview(obj, path, label, tris, views=None, res=(820, 620), samples=40, frame=None):
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for cc in obj.bound_box:
        w = obj.matrix_world @ Vector(cc)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
    c = (lo + hi) / 2
    rad = max((hi - lo).length / 2, 0.5)
    world = bpy.data.worlds.new('Sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    tcn = nt.nodes.new('ShaderNodeTexCoord')
    sepn = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tcn.outputs['Generated'], sepn.inputs[0])
    nt.links.new(sepn.outputs[2], ramp.inputs[0])
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.32, 0.3, 0.24, 1)
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (0.35, 0.5, 0.75, 1)
    nt.links.new(ramp.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.8
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 4.2
    sun.data.angle = math.radians(2)
    sun.data.color = (1.0, 0.95, 0.84)
    # the game's sun: from (+42, 60, +26) in three.js (x, up, z) -> blender (x, -z, up)
    dvec = Vector((42, -26, 60)).normalized()
    sun.rotation_euler = dvec.to_track_quat('Z', 'Y').to_euler()
    scene.collection.objects.link(sun)
    _ground(rad * 80, c)
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.clip_start = 0.05
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'AgX' if 'AgX' in [i.name for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Standard'
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x, scene.render.resolution_y = res
    shots = []
    views = views or ('game', 'front34', 'low')
    for i, v in enumerate(views):
        if v == 'game':     # the RTS camera: pitched 49 degrees, looking from +z (three) = -y here
            p = math.radians(49)
            dist = rad * 4.2
            _look(cam, c + Vector((0, -math.cos(p) * dist, math.sin(p) * dist)), c, 40)
        elif v == 'front34':
            _look(cam, c + Vector((1.0, -0.9, 0.38)).normalized() * rad * 2.9, c, 50)
        elif v == 'low':    # promo close-up: camera low to the ground, a few metres off
            dist = max(rad * 1.7, 2.2)
            ey = Vector((-0.6, -1.0, 0)).normalized()
            loc = c + ey * dist
            loc.z = max(0.35, min(1.1, (hi.z - lo.z) * 0.3))
            _look(cam, loc, Vector((c.x, c.y, (hi.z - lo.z) * 0.38)), 28)
        elif v == 'top':
            _look(cam, c + Vector((0.0, -0.05, rad * 4.5)), c, 40)
        p = f'{path[:-4]}_{i}.png'
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        shots.append(p)
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(p).convert('RGB') for p in shots]
    sheet = Image.new('RGB', (sum(i.width for i in ims) + 6 * (len(ims) - 1), ims[0].height), (20, 20, 22))
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0))
        x += im.width + 6
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    except OSError:
        font = ImageFont.load_default()
    text = f'{label}  ·  {tris:,} triangles'
    w = dr.textlength(text, font=font)
    dr.rectangle((0, 0, w + 24, 40), fill=(0, 0, 0))
    dr.text((12, 7), text, fill=(255, 255, 255), font=font)
    sheet.save(path, quality=90)
    for p in shots:
        os.remove(p)
