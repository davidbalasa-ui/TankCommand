"""The Shard, cinematic build v2 (2026-11-14, David: ~10x the shapes, truly translucent with a visible interior).

A towering cluster of ~170 faceted crystal spires growing out of one massif: a main spire, a crown of
secondary spires leaning out, a skirt of smaller ones and a scree of shards at the root, some broken off.
The glass is dark violet and translucent with absorption, so depth reads as darkness, and through it
you see the interior: ~45 smaller glowing crystals, a web of light veins, and a core that pulses.

shard_hd(name, height) returns the same object names the old new_pieces.shard used
(name, name+'_Core', name+'_Splinters', name+'_Ribbons', name+'_Inner', name+'_Veins'), so ground.py can swap it in.
"""
import math
import random
import sys
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(__file__))
import new_pieces as NP  # noqa: E402
import common as C  # noqa: E402
import forge as F  # noqa: E402
import ships as base  # noqa: E402
import barrage_pieces as BP  # noqa: E402

VIO = (0.45, 0.12, 1.0)


def _spire(bm, p0, d, h, r, rnd, sides=None, broken=False):
    """One faceted crystal: an irregular prism with a lopsided pyramid tip (or a fractured top)."""
    sides = sides or rnd.choice((5, 6, 6, 6, 7))
    d = Vector(d).normalized()
    q = d.to_track_quat('Z', 'Y')
    rot0 = rnd.uniform(0, 2 * math.pi)
    radii = [r * rnd.uniform(0.7, 1.15) for _ in range(sides)]
    angs = sorted(rot0 + 2 * math.pi * i / sides + rnd.uniform(-0.25, 0.25) for i in range(sides))
    body = h * rnd.uniform(0.62, 0.8)
    rings = []
    for z, k in ((0.0, 0.92), (body * 0.5, 1.0), (body, rnd.uniform(0.85, 1.0))):
        ring = [bm.verts.new(Vector(p0) + q @ Vector((math.cos(a) * rr * k, math.sin(a) * rr * k, z)))
                for a, rr in zip(angs, radii)]
        rings.append(ring)
    for a_, b_ in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            bm.faces.new((a_[i], a_[j], b_[j], b_[i]))
    bm.faces.new(list(reversed(rings[0])))
    top = rings[-1]
    if broken:          # fractured top: a tilted jagged cap
        cen = sum((v.co for v in top), Vector()) / sides
        n = q @ Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 1.0)).normalized()
        for v in top:
            v.co += n * ((v.co - cen).dot(n)) * -0.0 + q @ Vector((0, 0, rnd.uniform(-0.25, 0.1) * r))
        bm.faces.new(top)
    else:               # lopsided pyramid tip: the apex off-centre so the facets differ in size
        off = q @ Vector((rnd.uniform(-0.35, 0.35) * r, rnd.uniform(-0.35, 0.35) * r, h - body))
        cen = sum((v.co for v in top), Vector()) / sides
        apex = bm.verts.new(cen + off)
        for i in range(sides):
            bm.faces.new((top[i], top[(i + 1) % sides], apex))


def _obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def glass_mat(name='ShardGlassHD'):
    """Dark violet glass: clear surface, violet absorption inside (depth = darker, richer), a faint
    edge glow so the silhouette reads against a dark sky."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    n = BP._NT(m)
    b = n.node('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (0.38, 0.16, 0.85, 1)
    b.inputs['Roughness'].default_value = 0.04
    b.inputs['IOR'].default_value = 1.55
    b.inputs['Transmission Weight'].default_value = 1.0
    b.inputs['Coat Weight'].default_value = 0.15
    lw = n.node('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.15
    rim = n.maprange(lw.outputs['Facing'], 0.55, 1.0, 0.0, 1.2)
    b.inputs['Emission Color'].default_value = (0.5, 0.2, 1.0, 1)
    n.set(b.inputs['Emission Strength'], rim)
    vol = n.node('ShaderNodeVolumeAbsorption')
    vol.inputs['Color'].default_value = (0.35, 0.1, 0.9, 1)
    vol.inputs['Density'].default_value = 0.06
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], b.outputs[0])
    n.set(out.inputs['Volume'], vol.outputs[0])
    return m


def shard_hd(name='Shard', height=42.0, seed=9):
    rnd = random.Random(seed)
    base._faction('kesh')
    H = height
    root_z = 8.0
    # ---------------------------------------------------------------- outer glass: ~170 spires
    bm = bmesh.new()
    _spire(bm, (0, 0, root_z - 4), (0.03, -0.02, 1), H + 16, H * 0.15, rnd, sides=7)
    _spire(bm, (1.5, -1.0, root_z - 2), (0.12, -0.05, 1), H * 0.9, H * 0.09, rnd, sides=6)   # twin beside it
    count = 1
    for i in range(24):                        # crown: secondary spires leaning out from the massif
        a = 2 * math.pi * i / 24 + rnd.uniform(-0.12, 0.12)
        lean = rnd.uniform(0.12, 0.5)
        rr = rnd.uniform(1.0, 4.0)
        p0 = Vector((math.cos(a) * rr, math.sin(a) * rr, root_z + rnd.uniform(-2, H * 0.3)))
        d = (math.cos(a) * lean, math.sin(a) * lean, 1.0)
        h = H * rnd.uniform(0.3, 0.75)
        _spire(bm, p0, d, h, h * rnd.uniform(0.08, 0.13), rnd, broken=rnd.random() < 0.15)
        count += 1
    for i in range(60):                        # skirt: smaller spires all round the lower body
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(2.5, 8.0)
        z = root_z + rnd.uniform(-3, H * 0.45)
        lean = rnd.uniform(0.5, 1.8)
        d = (math.cos(a) * lean, math.sin(a) * lean, rnd.uniform(0.3, 1.0))
        h = H * rnd.uniform(0.08, 0.28)
        _spire(bm, (math.cos(a) * rr, math.sin(a) * rr, z), d, h, h * rnd.uniform(0.1, 0.18), rnd,
               broken=rnd.random() < 0.2)
        count += 1
    for i in range(85):                        # scree at the root: shards jutting from the base, many broken
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(5.0, 15.0)
        lean = rnd.uniform(0.6, 2.5)
        d = (math.cos(a) * lean, math.sin(a) * lean, rnd.uniform(0.2, 1.0))
        h = rnd.uniform(1.2, 6.5)
        _spire(bm, (math.cos(a) * rr, math.sin(a) * rr, root_z + rnd.uniform(-5, 1)), d, h,
               h * rnd.uniform(0.12, 0.22), rnd, broken=rnd.random() < 0.35)
        count += 1
    crystal = _obj(name, bm)
    crystal.data.materials.append(glass_mat(name + 'GlassM'))
    crystal['spires'] = count
    # ---------------------------------------------------------------- interior: glowing inner crystals
    bm = bmesh.new()
    for i in range(45):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.0, 3.2)
        z = root_z + rnd.uniform(2, H * 0.85)
        d = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), 1.0)
        h = rnd.uniform(2.0, 9.0)
        _spire(bm, (math.cos(a) * rr, math.sin(a) * rr, z), d, h, h * 0.12, rnd)
    inner = _obj(name + '_Inner', bm)
    im, nn = BP._new_mat(name + 'InnerM')
    tc = nn.node('ShaderNodeTexCoord')
    t = BP.time_value(im, 'time', 1.0)
    nz = nn.node('ShaderNodeTexNoise', Scale=0.12, Detail=3.0)
    nz.noise_dimensions = '4D'
    nn.set(nz.inputs['Vector'], tc.outputs['Object'])
    nn.set(nz.inputs['W'], nn.math('MULTIPLY', t, 0.6))
    k = nn.maprange(nz.outputs['Fac'], 0.35, 0.7, 1.0, 7.0)
    BP._add_out(nn, k, (0.6, 0.3, 1.0), trans=False)
    inner.data.materials.append(im)
    # ---------------------------------------------------------------- interior: light veins
    veins = []
    for k_ in range(30):
        pts = []
        p = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), root_z + rnd.uniform(0, H * 0.2)))
        d = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 1.0)).normalized()
        for s in range(18):
            pts.append(tuple(p))
            d = (d + Vector((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35), rnd.uniform(-0.1, 0.25)))).normalized()
            p = p + d * rnd.uniform(1.2, 2.6)
            rad = math.hypot(p.x, p.y)
            lim = 3.5 * (1 - (p.z - root_z) / (H + 4)) + 0.6
            if rad > lim:
                p.x *= lim / rad
                p.y *= lim / rad
        veins.append(F.sweep(pts, [(0.07, 0.07)] * len(pts), 'glow', sides=4))
    vn = base._join(veins, name + '_Veins')
    vm, vn_ = BP._new_mat(name + 'VeinM')
    t2 = BP.time_value(vm, 'time', 1.0)
    tc2 = vn_.node('ShaderNodeTexCoord')
    sep = vn_.node('ShaderNodeSeparateXYZ')
    vn_.set(sep.inputs[0], tc2.outputs['Object'])
    wave = vn_.math('SINE', vn_.math('SUBTRACT', vn_.math('MULTIPLY', sep.outputs[2], 0.35), vn_.math('MULTIPLY', t2, 4.0)))
    k2 = vn_.maprange(wave, -1.0, 1.0, 1.0, 9.0)     # pulses of light running up the veins
    BP._add_out(vn_, k2, (0.75, 0.5, 1.0), trans=False)
    vn.data.materials.clear()
    vn.data.materials.append(vm)
    # ---------------------------------------------------------------- core
    core = C.uv_sphere(name + '_Core', 2.0, seg=(32, 16), mat=C.emit_mat(name + 'CoreM', (0.6, 0.3, 1.0), 14.0))
    core.location = (0, 0, root_z + H * 0.42)
    core.scale = (1, 1, 2.2)
    L = bpy.data.objects.new(name + '_Light', bpy.data.lights.new(name + '_Light', 'POINT'))
    bpy.context.scene.collection.objects.link(L)
    L.location = core.location
    L.data.color = (0.55, 0.25, 1.0)
    L.data.energy = 4e5
    L.data.shadow_soft_size = 6
    # ---------------------------------------------------------------- floating splinters round it (kept, more of them)
    smat = NP._mat(name + 'SplM', base_col=(0.35, 0.15, 0.85), emit=VIO, strength=0.15, transmission=0.9, rough=0.05,
                   ior=1.55)
    bm = bmesh.new()
    for i in range(40):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(10, 22)
        z = rnd.uniform(root_z, H + 12)
        d = (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))
        h = rnd.uniform(0.8, 3.0)
        _spire(bm, (rr * math.cos(a), rr * math.sin(a), z), d, h, h * 0.18, rnd, broken=rnd.random() < 0.5)
    spl = _obj(name + '_Splinters', bm)
    spl.data.materials.append(smat)
    # no ribbons: the critique found them toy-like. An empty keeps the old name for callers.
    rb = bpy.data.objects.new(name + '_Ribbons', None)
    bpy.context.scene.collection.objects.link(rb)
    for o in (crystal, inner, vn, core, spl):
        o.visible_shadow = o is crystal
    return crystal
