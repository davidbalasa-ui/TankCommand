"""Vesper, built to hold up from orbit and on the way down.

Surface: warped multi-octave relief in the valley palette (plum basalt basins, mauve-brown plains,
ochre highlands, pale pink crystal flats that glint), canyon networks, fine bump detail, a lilac
limb haze, and on the night side faint violet veins glowing through the crystal flats (the Shard's
light, foreshadowed). A separate cloud shell (casts shadows, gives parallax when diving through)
and a sun-facing atmosphere rim shell.

All procedural in object space, so there are no seams or texture resolution limits.
"""
import math

import bpy
from mathutils import Vector, Matrix

import barrage_pieces as BP

R = 2400.0
CLOUD_H = 60.0          # cloud tops above the ground
ATMO_H = 55.0
VIOLET = (0.55, 0.15, 1.0)


def _sphere(name, r, seg):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=r)
    # poles sideways (+-X), away from where the fleets and the drop sit (over +Z)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def _unit_pos(n, r):
    """Object-space position scaled to the unit sphere."""
    tc = n.node('ShaderNodeTexCoord')
    vm = n.node('ShaderNodeVectorMath', operation='SCALE')
    n.set(vm.inputs[0], tc.outputs['Object'])
    vm.inputs['Scale'].default_value = 1.0 / r
    return vm.outputs[0]


def _warp(n, p, scale, amt, w=0.0):
    nz = n.node('ShaderNodeTexNoise', Scale=scale, Detail=4.0)
    nz.noise_dimensions = '4D'
    nz.inputs['W'].default_value = w
    n.set(nz.inputs['Vector'], p)
    c = n.node('ShaderNodeVectorMath', operation='SUBTRACT')
    n.set(c.inputs[0], nz.outputs['Color'])
    c.inputs[1].default_value = (0.5, 0.5, 0.5)
    vm = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    n.set(vm.inputs[0], c.outputs[0])
    vm.inputs[1].default_value = (amt, amt, amt)
    n.set(vm.inputs[2], p)
    return vm.outputs[0]


def _sun_dot(n, sun_dir):
    geo = n.node('ShaderNodeNewGeometry')
    d = n.node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    n.set(d.inputs[0], geo.outputs['Normal'])
    d.inputs[1].default_value = tuple(sun_dir)
    return d.outputs['Value']


def surface_mat(sun_dir):
    m, n = BP._new_mat('VesperSurface')
    out = n.node('ShaderNodeOutputMaterial')
    b = n.node('ShaderNodeBsdfPrincipled')
    p = _unit_pos(n, R)
    pw = _warp(n, _warp(n, p, 2.2, 0.35, 1.0), 7.0, 0.08, 2.0)
    # relief
    land = n.node('ShaderNodeTexNoise', Scale=2.6, Detail=15.0, Roughness=0.58, Lacunarity=2.1)
    n.set(land.inputs['Vector'], pw)
    h = land.outputs['Fac']
    # crystal flats: a second field, only on the low plains
    flats = n.node('ShaderNodeTexNoise', Scale=5.5, Detail=10.0, Roughness=0.55)
    n.set(flats.inputs['Vector'], pw)
    fl = n.math('MULTIPLY', n.maprange(flats.outputs['Fac'], 0.56, 0.64, 0.0, 1.0),
                n.maprange(h, 0.52, 0.47, 0.0, 1.0))
    # canyons: warped cell edges, cut into the mid and high ground
    vor = n.node('ShaderNodeTexVoronoi', Scale=11.0)
    vor.feature = 'DISTANCE_TO_EDGE'
    n.set(vor.inputs['Vector'], _warp(n, pw, 16.0, 0.03, 3.0))
    sparse = n.node('ShaderNodeTexNoise', Scale=3.0, Detail=2.0)
    n.set(sparse.inputs['Vector'], pw)
    can = n.math('MULTIPLY', n.maprange(vor.outputs['Distance'], 0.0, 0.022, 0.8, 0.0),
                 n.math('MULTIPLY', n.maprange(h, 0.46, 0.52, 0.0, 1.0), n.maprange(sparse.outputs['Fac'], 0.45, 0.6, 0.0, 1.0)))
    vor2 = n.node('ShaderNodeTexVoronoi', Scale=37.0)
    vor2.feature = 'DISTANCE_TO_EDGE'
    n.set(vor2.inputs['Vector'], _warp(n, pw, 40.0, 0.012, 4.0))
    can2 = n.math('MULTIPLY', n.maprange(vor2.outputs['Distance'], 0.0, 0.015, 0.35, 0.0),
                  n.maprange(h, 0.5, 0.56, 0.0, 1.0))
    can = n.math('MAXIMUM', can, can2)
    # colour by height
    ramp = n.node('ShaderNodeValToRGB')
    n.set(ramp.inputs[0], h)
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.36, (0.025, 0.014, 0.03, 1)      # deep basalt basins
    els[1].position, els[1].color = 0.72, (0.62, 0.5, 0.4, 1)          # bleached high ridges
    for pos, col in ((0.44, (0.07, 0.04, 0.06, 1)), (0.49, (0.2, 0.13, 0.13, 1)), (0.55, (0.33, 0.23, 0.21, 1)),
                     (0.62, (0.45, 0.32, 0.22, 1))):
        e = els.new(pos)
        e.color = col
    # fine colour breakup
    grit = n.node('ShaderNodeTexNoise', Scale=60.0, Detail=10.0, Roughness=0.6)
    n.set(grit.inputs['Vector'], pw)
    col = n.node('ShaderNodeMix')
    col.data_type = 'RGBA'
    col.blend_type = 'MULTIPLY'
    n.set(col.inputs[0], 0.5)
    n.set(col.inputs[6], ramp.outputs[0])
    n.set(col.inputs[7], n.mix(grit.outputs['Fac'], (0.7, 0.7, 0.75), (1.3, 1.25, 1.2)))
    c1 = col.outputs[2]
    c2 = n.mix(fl, c1, (0.88, 0.7, 0.8))                          # pale pink crystal flats
    c3 = n.mix(n.math('MULTIPLY', can, 0.85), c2, (0.03, 0.015, 0.025))   # dark canyon floors
    n.set(b.inputs['Base Color'], c3)
    n.set(b.inputs['Roughness'], n.maprange(fl, 0.0, 1.0, 0.9, 0.28))
    b.inputs['Specular IOR Level'].default_value = 0.5
    # relief bump: big land + canyons cut down + fine grain
    fine = n.node('ShaderNodeTexNoise', Scale=420.0, Detail=8.0, Roughness=0.6)
    n.set(fine.inputs['Vector'], pw)
    hb = n.math('ADD', n.math('MULTIPLY', h, 1.0), n.math('MULTIPLY', can, -0.06))
    hb = n.math('ADD', hb, n.math('MULTIPLY', fine.outputs['Fac'], 0.012))
    bump = n.node('ShaderNodeBump', Strength=0.55, Distance=6.0)
    n.set(bump.inputs['Height'], hb)
    n.set(b.inputs['Normal'], bump.outputs[0])
    # emission: lilac limb haze on the day side + violet veins in the crystal flats at night
    sd = _sun_dot(n, sun_dir)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.35)
    haze = n.math('MULTIPLY', n.math('POWER', lw.outputs['Facing'], 2.2), n.maprange(sd, -0.15, 0.5, 0.0, 1.0))
    night = n.maprange(sd, 0.02, -0.15, 0.0, 1.0)
    vv = n.node('ShaderNodeTexVoronoi', Scale=26.0)
    vv.feature = 'DISTANCE_TO_EDGE'
    n.set(vv.inputs['Vector'], _warp(n, pw, 60.0, 0.006, 5.0))
    vmask = n.node('ShaderNodeTexNoise', Scale=9.0, Detail=4.0)
    n.set(vmask.inputs['Vector'], pw)
    vein = n.math('MULTIPLY', n.maprange(vv.outputs['Distance'], 0.0, 0.008, 1.0, 0.0),
                  n.math('MULTIPLY', n.math('ADD', fl, 0.1), n.maprange(vmask.outputs['Fac'], 0.5, 0.62, 0.0, 1.0)))
    vein = n.math('MULTIPLY', vein, night)
    ecol = n.mix(n.math('MINIMUM', n.math('MULTIPLY', vein, 6.0), 1.0), (0.6, 0.62, 1.0), (0.42, 0.08, 1.0))
    n.set(b.inputs['Emission Color'], ecol)
    n.set(b.inputs['Emission Strength'], n.math('ADD', n.math('MULTIPLY', haze, 0.12), n.math('MULTIPLY', vein, 1.6)))
    n.set(out.inputs['Surface'], b.outputs[0])
    return m


def cloud_mat(sun_dir, r):
    m, n = BP._new_mat('VesperClouds')
    out = n.node('ShaderNodeOutputMaterial')
    p = _unit_pos(n, r)
    mp = n.node('ShaderNodeMapping')
    n.set(mp.inputs['Vector'], p)
    mp.inputs['Scale'].default_value = (1.0, 1.0, 2.4)        # banded along latitude (world z)
    pw = _warp(n, _warp(n, mp.outputs[0], 3.0, 0.5, 7.0), 12.0, 0.06, 8.0)
    nz = n.node('ShaderNodeTexNoise', Scale=7.0, Detail=14.0, Roughness=0.62)
    n.set(nz.inputs['Vector'], pw)
    big = n.node('ShaderNodeTexNoise', Scale=1.6, Detail=3.0)
    n.set(big.inputs['Vector'], p)
    cover = n.maprange(big.outputs['Fac'], 0.35, 0.65, 0.58, 0.46)          # some regions clear, some overcast
    dens = n.math('SUBTRACT', nz.outputs['Fac'], cover)
    dens = n.maprange(dens, 0.0, 0.14, 0.0, 0.95)
    d = n.node('ShaderNodeBsdfDiffuse')
    d.inputs['Color'].default_value = (0.95, 0.88, 0.9, 1)
    tl = n.node('ShaderNodeBsdfTranslucent')
    tl.inputs['Color'].default_value = (0.9, 0.75, 0.8, 1)
    mx0 = n.node('ShaderNodeMixShader')
    mx0.inputs[0].default_value = 0.2
    n.set(mx0.inputs[1], d.outputs[0])
    n.set(mx0.inputs[2], tl.outputs[0])
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], dens)
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], mx0.outputs[0])
    n.set(out.inputs['Surface'], mx.outputs[0])
    return m


def atmo_mat(sun_dir):
    m, n = BP._new_mat('VesperAtmo')
    out = n.node('ShaderNodeOutputMaterial')
    lw = n.node('ShaderNodeLayerWeight', Blend=0.3)
    rim = n.math('MULTIPLY', n.math('POWER', lw.outputs['Facing'], 3.0),
                 n.maprange(lw.outputs['Facing'], 0.998, 0.9, 0.0, 1.0))      # soft outer edge, densest low
    sd = _sun_dot(n, sun_dir)
    day = n.maprange(sd, -0.35, 0.35, 0.0, 1.0)
    term = n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', sd, 0.0)), 0.0, 0.3, 1.0, 0.0)  # sunset band
    col = n.mix(term, (0.42, 0.55, 1.0), (1.0, 0.5, 0.55))
    em = n.node('ShaderNodeEmission')
    n.set(em.inputs['Color'], col)
    n.set(em.inputs['Strength'], n.math('MULTIPLY', n.math('MULTIPLY', rim, day), 1.1))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


def build(center, sun_obj, draft=True):
    """Planet, clouds ('VesperClouds') and atmosphere ('Atmosphere'), all at `center`."""
    sun_dir = (sun_obj.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    seg = (384, 192) if draft else (768, 384)
    p = _sphere('Vesper', R, seg)
    p.data.materials.append(surface_mat(sun_dir))
    c = _sphere('VesperClouds', R + CLOUD_H, seg)
    c.data.materials.append(cloud_mat(sun_dir, R + CLOUD_H))
    a = _sphere('Atmosphere', R + ATMO_H, (256, 128))
    a.data.materials.append(atmo_mat(sun_dir))
    a.visible_shadow = False
    for o in (p, c, a):
        o.location = center
    return p
