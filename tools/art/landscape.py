"""Landscape props: rocks, cliff chunks, plants and alien growth, baked with the hero pipeline.

Each prop is one small model (one material, four maps) that the game scatters with instancing.
Shapes are displaced low-poly meshes, so the silhouettes are irregular, and the surface detail
(cracks, strata, lichen, leaf veins, glow) comes from procedural shaders baked into the maps.

Usage (pip bpy):  python landscape.py <out_dir> <all|name[,name]> [render_dir]
"""
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402  (pip bpy exposes bmesh only after bpy is imported)
import numpy as np
from mathutils import Vector, noise

sys.path.insert(0, os.path.dirname(__file__))
import hero  # noqa: E402
import kit  # noqa: E402

# Nature zones, added to the hero pipeline. 'stone' is a new shader kind defined below.
NATURE = {
    'rock': dict(kind='stone', base=(0.24, 0.22, 0.20), dark=(0.09, 0.085, 0.08), lichen=(0.24, 0.30, 0.12), rough=0.85),
    'cliff': dict(kind='stone', base=(0.36, 0.31, 0.26), dark=(0.13, 0.11, 0.09), lichen=(0.22, 0.27, 0.10), rough=0.9),
    'bark': dict(kind='stone', base=(0.16, 0.11, 0.07), dark=(0.05, 0.035, 0.02), lichen=(0.18, 0.2, 0.08), rough=0.9),
    'leaf': dict(kind='leaf', base=(0.10, 0.22, 0.05), tip=(0.30, 0.42, 0.10), rough=0.7),
    'foliage': dict(kind='leaf', foliage=True, base=(0.025, 0.06, 0.015), tip=(0.12, 0.22, 0.04), rough=0.8),
    'dryleaf': dict(kind='leaf', base=(0.30, 0.26, 0.10), tip=(0.50, 0.42, 0.18), rough=0.8),
    'alien': dict(kind='leaf', base=(0.10, 0.06, 0.18), tip=(0.20, 0.55, 0.55), rough=0.5),
    'glow': dict(kind='glow', base=(0.1, 0.3, 0.3), emit=(0.3, 1.0, 0.85), strength=5.0),
    'crystal': dict(kind='glow', base=(0.25, 0.1, 0.35), emit=(0.6, 0.3, 1.0), strength=2.5),
}
hero.ZONES['nature'] = NATURE
kit.FACTIONS['nature'] = dict(kit.FACTIONS['terran'], tiles={k: (0.0, 0.0, 1.0, 1.0) for k in NATURE})

_original_zone_material = hero.zone_material


def zone_material(zone):
    """Stone and leaf shaders for nature zones; everything else goes to the hero shaders."""
    if hero.H.get('faction') != 'nature' or NATURE.get(zone, {}).get('kind') not in ('stone', 'leaf'):
        return _original_zone_material(zone)
    if zone in hero.H['zone_mats']:
        return hero.H['zone_mats'][zone]
    z = NATURE[zone]
    mat = bpy.data.materials.new(f'zone_{zone}')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    coord = nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
    n = hero._n
    m = hero._math
    bump = n(nt, 'ShaderNodeBump', (0, -400), Strength=0.8, Distance=0.04)
    nt.links.new(bump.outputs[0], bsdf.inputs['Normal'])
    fine = n(nt, 'ShaderNodeTexNoise', (-600, 200), Scale=9.0, Detail=8.0, Roughness=0.65)
    nt.links.new(coord, fine.inputs['Vector'])
    broad = n(nt, 'ShaderNodeTexNoise', (-600, 0), Scale=1.6, Detail=3.0)
    nt.links.new(coord, broad.inputs['Vector'])
    if z['kind'] == 'stone':
        # Cracks: a few long fractures, not a cell pattern. The Voronoi lookup is warped by noise so
        # the edges wander, and only kept where a second noise allows, so most faces stay unbroken.
        warp = n(nt, 'ShaderNodeTexNoise', (-900, -200), Scale=1.2, Detail=2.0)
        nt.links.new(coord, warp.inputs['Vector'])
        wv = nt.nodes.new('ShaderNodeVectorMath'); wv.operation = 'ADD'
        nt.links.new(coord, wv.inputs[0])
        nt.links.new(warp.outputs['Color'], wv.inputs[1])
        cracks = n(nt, 'ShaderNodeTexVoronoi', (-600, -200), Scale=1.1)
        cracks.feature = 'DISTANCE_TO_EDGE'
        nt.links.new(wv.outputs[0], cracks.inputs['Vector'])
        keep = m(nt, 'GREATER_THAN', broad.outputs['Fac'], 0.52)
        crack = m(nt, 'MULTIPLY', m(nt, 'LESS_THAN', cracks.outputs['Distance'], 0.018), keep)
        # Strata: faint bands along height, wobbled by the broad noise.
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(coord, sep.inputs[0])
        strata = m(nt, 'SINE', m(nt, 'MULTIPLY', m(nt, 'ADD', sep.outputs[2], m(nt, 'MULTIPLY', broad.outputs['Fac'], 0.6)), 7.0))
        grain = n(nt, 'ShaderNodeTexNoise', (-600, 400), Scale=40.0, Detail=4.0)
        nt.links.new(coord, grain.inputs['Vector'])
        height = m(nt, 'SUBTRACT', m(nt, 'ADD', m(nt, 'ADD', m(nt, 'MULTIPLY', fine.outputs['Fac'], 0.6),
                                                    m(nt, 'MULTIPLY', grain.outputs['Fac'], 0.15)),
                                    m(nt, 'MULTIPLY', strata, 0.05)),
                   m(nt, 'MULTIPLY', crack, 0.35))
        nt.links.new(height, bump.inputs['Height'])
        col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'
        col.inputs['A'].default_value = (*z['dark'], 1)
        col.inputs['B'].default_value = (*z['base'], 1)
        # Mostly base colour; darker in the noise hollows, speckled by the grain.
        shade = m(nt, 'ADD', m(nt, 'ADD', m(nt, 'MULTIPLY', broad.outputs['Fac'], 0.7), m(nt, 'MULTIPLY', fine.outputs['Fac'], 0.5)),
                  m(nt, 'ADD', m(nt, 'MULTIPLY', grain.outputs['Fac'], 0.3), m(nt, 'MULTIPLY', strata, 0.08)))
        nt.links.new(m(nt, 'SUBTRACT', shade, 0.25, clamp=True), col.inputs['Factor'])
        cr = nt.nodes.new('ShaderNodeMix'); cr.data_type = 'RGBA'
        nt.links.new(col.outputs['Result'], cr.inputs['A'])
        cr.inputs['B'].default_value = (z['dark'][0] * 0.5, z['dark'][1] * 0.5, z['dark'][2] * 0.5, 1)
        nt.links.new(m(nt, 'MULTIPLY', crack, 0.8), cr.inputs['Factor'])
        # Lichen and moss in patches on the tops (normal facing up).
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        upz = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Normal'], upz.inputs[0])
        patch = n(nt, 'ShaderNodeTexNoise', (-600, 600), Scale=4.0, Detail=6.0, Roughness=0.7)
        nt.links.new(coord, patch.inputs['Vector'])
        top = m(nt, 'MULTIPLY', m(nt, 'SUBTRACT', upz.outputs[2], 0.45, clamp=True),
                m(nt, 'GREATER_THAN', patch.outputs['Fac'], 0.5))
        li = nt.nodes.new('ShaderNodeMix'); li.data_type = 'RGBA'
        nt.links.new(cr.outputs['Result'], li.inputs['A'])
        li.inputs['B'].default_value = (*z['lichen'], 1)
        nt.links.new(m(nt, 'MULTIPLY', top, 1.4, clamp=True), li.inputs['Factor'])
        nt.links.new(li.outputs['Result'], bsdf.inputs['Base Color'])
    elif z.get('foliage'):
        # Bush crowns: clumps of leaves as dense noise speckle, darker deep inside the crown.
        leaves = n(nt, 'ShaderNodeTexVoronoi', (-600, -200), Scale=22.0)
        nt.links.new(coord, leaves.inputs['Vector'])
        nt.links.new(m(nt, 'ADD', m(nt, 'MULTIPLY', leaves.outputs['Distance'], 1.0), m(nt, 'MULTIPLY', fine.outputs['Fac'], 0.4)),
                     bump.inputs['Height'])
        bump.inputs['Strength'].default_value = 1.0
        col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'
        col.inputs['A'].default_value = (*z['base'], 1)
        col.inputs['B'].default_value = (*z['tip'], 1)
        nt.links.new(m(nt, 'ADD', m(nt, 'MULTIPLY', leaves.outputs['Distance'], 1.2), m(nt, 'MULTIPLY', broad.outputs['Fac'], 0.5), clamp=True),
                     col.inputs['Factor'])
        nt.links.new(col.outputs['Result'], bsdf.inputs['Base Color'])
    else:  # leaf: veins and a colour ramp from base to tip (object height)
        veins = n(nt, 'ShaderNodeTexVoronoi', (-600, -200), Scale=7.0)
        veins.feature = 'DISTANCE_TO_EDGE'
        nt.links.new(coord, veins.inputs['Vector'])
        vein = m(nt, 'LESS_THAN', veins.outputs['Distance'], 0.03)
        nt.links.new(m(nt, 'SUBTRACT', m(nt, 'MULTIPLY', fine.outputs['Fac'], 0.3), m(nt, 'MULTIPLY', vein, 0.3)), bump.inputs['Height'])
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(coord, sep.inputs[0])
        col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'
        col.inputs['A'].default_value = (*z['base'], 1)
        col.inputs['B'].default_value = (*z['tip'], 1)
        nt.links.new(m(nt, 'ADD', m(nt, 'MULTIPLY', sep.outputs[2], 0.5), m(nt, 'MULTIPLY', fine.outputs['Fac'], 0.5), clamp=True), col.inputs['Factor'])
        dv = nt.nodes.new('ShaderNodeMix'); dv.data_type = 'RGBA'
        nt.links.new(col.outputs['Result'], dv.inputs['A'])
        dv.inputs['B'].default_value = (z['base'][0] * 0.5, z['base'][1] * 0.5, z['base'][2] * 0.5, 1)
        nt.links.new(m(nt, 'MULTIPLY', vein, 0.6), dv.inputs['Factor'])
        nt.links.new(dv.outputs['Result'], bsdf.inputs['Base Color'])
        if zone == 'alien':
            bsdf.inputs['Emission Color'].default_value = (0.3, 1.0, 0.85, 1)
            nt.links.new(m(nt, 'MULTIPLY', vein, 3.0), bsdf.inputs['Emission Strength'])
    bsdf.inputs['Metallic'].default_value = 0.0
    nt.links.new(m(nt, 'ADD', m(nt, 'MULTIPLY', fine.outputs['Fac'], 0.15), z['rough'] - 0.07), bsdf.inputs['Roughness'])
    hero.H['zone_mats'][zone] = mat
    return mat


hero.zone_material = zone_material


# ---------------------------------------------------------------- geometry helpers
def lump(name, centre, size, zone, seed, subdiv=2, flat=0.35, jag=0.35, squash=1.0, smooth=False):
    """A displaced icosphere: boulders, cliff chunks, bush crowns. Bottom flattened so it sits."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((seed * 7.31, seed * 3.17, seed * 5.53))
    for v in bm.verts:
        p = v.co.copy()
        d = 1.0 + jag * noise.noise(p * 1.3 + off) + jag * 0.5 * noise.noise(p * 3.1 + off)
        v.co = Vector((p.x * size[0] * d, p.y * size[1] * d, p.z * size[2] * d * squash))
        if v.co.z < -size[2] * flat:
            v.co.z = -size[2] * flat
    for v in bm.verts:
        v.co += Vector(centre) + Vector((0, 0, size[2] * flat))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return kit._link(name, me, zone, smooth)


def blade(name, base, height, width, lean, zone, turn=0.0, segs=3, curve=0.35):
    """A tapered curved blade (grass, tendril leaf): a strip of quads, both sides visible."""
    verts, faces = [], []
    c, s = math.cos(turn), math.sin(turn)
    for i in range(segs + 1):
        t = i / segs
        w = width * (1 - t) ** 0.8 * 0.5
        x = lean * t + curve * lean * t * t
        z = height * t
        for side in (-1, 1):
            lx, ly = x, side * w
            verts.append((base[0] + lx * c - ly * s, base[1] + lx * s + ly * c, base[2] + z))
    for i in range(segs):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    return kit.mesh_from(name, verts, faces, zone)


def spire(name, base, height, radius, sides, zone, tilt=(0.0, 0.0)):
    """A pointed prism (crystal, thorn)."""
    verts = []
    for k in range(sides):
        a = 2 * math.pi * k / sides
        verts.append((base[0] + radius * math.cos(a), base[1] + radius * math.sin(a), base[2]))
    for k in range(sides):
        a = 2 * math.pi * k / sides
        verts.append((base[0] + radius * 0.8 * math.cos(a) + tilt[0] * height * 0.7,
                      base[1] + radius * 0.8 * math.sin(a) + tilt[1] * height * 0.7, base[2] + height * 0.7))
    verts.append((base[0] + tilt[0] * height, base[1] + tilt[1] * height, base[2] + height))
    faces = []
    for k in range(sides):
        k2 = (k + 1) % sides
        faces.append((k, k2, sides + k2, sides + k))
        faces.append((sides + k, sides + k2, 2 * sides))
    faces.append(tuple(reversed(range(sides))))
    return kit.mesh_from(name, verts, faces, zone)


# ---------------------------------------------------------------- props
def boulder():
    return [lump('Boulder', (0, 0, 0), (1.3, 1.0, 0.9), 'rock', 1, subdiv=3)]


def rock_cluster():
    rnd = random.Random(2)
    out = [lump('Big', (0, 0, 0), (1.1, 0.9, 1.0), 'rock', 2)]
    for k, (x, y, s) in enumerate(((1.4, 0.5, 0.55), (-1.0, 0.9, 0.45), (0.3, -1.3, 0.4), (-1.4, -0.6, 0.3))):
        out.append(lump(f'Small{k}', (x, y, 0), (s * (1 + rnd.random() * 0.4), s, s * 0.8), 'rock', 10 + k, subdiv=1))
    return out


def slab():
    return [lump('Slab', (0, 0, 0), (1.9, 1.3, 0.45), 'rock', 3, flat=0.2, jag=0.25),
            lump('SlabTop', (0.5, 0.3, 0.45), (0.9, 0.7, 0.35), 'rock', 4, subdiv=1, flat=0.3)]


def cliff():
    """A tall jagged outcrop for steep ground: stacked chunks leaning together."""
    out = []
    for k, (x, y, z, sx, sy, sz) in enumerate(((0, 0, 0, 2.2, 1.6, 2.4), (1.6, 0.7, 0, 1.4, 1.2, 1.7),
                                               (-1.5, -0.4, 0, 1.5, 1.3, 1.5), (0.2, 0.2, 2.6, 1.3, 1.0, 1.3))):
        out.append(lump(f'Crag{k}', (x, y, z), (sx, sy, sz), 'cliff', 20 + k, jag=0.45, flat=0.3))
    return out


def shrub():
    """A bush: a ring of small leafy clumps round a taller middle, so it reads as foliage, not a rock."""
    rnd = random.Random(5)
    out = [kit.cyl('Trunk', (0, 0, 0), (0.05, 0.03, 0.5), 0.1, 5, 'bark', r1=0.06)]
    out.append(lump('Crown', (0, 0, 0.35), (0.5, 0.5, 0.45), 'foliage', 29, subdiv=2, flat=0.5, jag=0.5, smooth=True))
    for k in range(9):
        a = k * 2.4 + rnd.random() * 0.5
        d = 0.45 + rnd.random() * 0.35
        r = 0.22 + rnd.random() * 0.16
        out.append(lump(f'Clump{k}', (math.cos(a) * d, math.sin(a) * d, rnd.random() * 0.3),
                        (r * 1.2, r * 1.1, r), 'foliage', 30 + k, subdiv=1, flat=0.6, jag=0.6, smooth=True))
    return out


def grass():
    rnd = random.Random(7)
    out = []
    for k in range(9):
        a = rnd.random() * math.tau
        out.append(blade(f'Blade{k}', (math.cos(a) * 0.15, math.sin(a) * 0.15, 0), 0.5 + rnd.random() * 0.4,
                         0.09, 0.15 + rnd.random() * 0.2, 'leaf' if k % 3 else 'dryleaf', turn=a))
    return out


def dead_tree():
    out = [kit.cyl('Trunk', (0, 0, 0), (0.15, 0.1, 2.2), 0.22, 6, 'bark', r1=0.1)]
    for k, (a, h, l) in enumerate(((0.4, 1.2, 0.9), (2.6, 1.6, 0.7), (4.4, 1.9, 0.6))):
        out.append(kit.cyl(f'Branch{k}', (0.1, 0.05, h), (0.1 + math.cos(a) * l, 0.05 + math.sin(a) * l, h + l * 0.7),
                           0.08, 5, 'bark', r1=0.03))
    out.append(lump('Roots', (0, 0, 0), (0.45, 0.45, 0.2), 'bark', 40, subdiv=1, flat=0.5))
    return out


def tendril():
    """Alien growth: curling dark-violet fronds with glowing veins and bulb tips."""
    rnd = random.Random(11)
    out = []
    for k in range(6):
        a = k * math.tau / 6 + rnd.random() * 0.4
        h = 0.9 + rnd.random() * 0.7
        lean = 0.35 + rnd.random() * 0.3
        out.append(blade(f'Frond{k}', (0, 0, 0), h, 0.28, lean, 'alien', turn=a, segs=4, curve=1.2))
        tip = (math.cos(a) * lean * 2.2, math.sin(a) * lean * 2.2, h)
        out.append(kit.orb(f'Bulb{k}', tip, 0.09, 'glow', seg=(6, 4)))
    out.append(lump('Pod', (0, 0, 0), (0.35, 0.35, 0.25), 'alien', 50, subdiv=1, flat=0.5))
    return out


def crystals():
    """Alien crystal spires jutting from a rock base."""
    rnd = random.Random(13)
    out = [lump('Base', (0, 0, 0), (0.8, 0.7, 0.35), 'rock', 60, subdiv=1, flat=0.4)]
    for k in range(6):
        a = rnd.random() * math.tau
        r = rnd.random() * 0.45
        tilt = (math.cos(a) * 0.35, math.sin(a) * 0.35)
        out.append(spire(f'Spire{k}', (math.cos(a) * r, math.sin(a) * r, 0.25), 0.8 + rnd.random() * 1.1,
                         0.12 + rnd.random() * 0.1, 6, 'crystal', tilt=tilt))
    return out


PROPS = {
    'boulder': boulder, 'rock_cluster': rock_cluster, 'slab': slab, 'cliff': cliff,
    'shrub': shrub, 'grass': grass, 'dead_tree': dead_tree, 'tendril': tendril,
    # crystals() is kept but not baked: crystal spires on the map would read as ore sites.
}


def preview(obj, render_dir, name):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 480, 360
    scene.cycles.samples = 32
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    centre = sum(bb, Vector()) / 8
    size = max((max(v[i] for v in bb) - min(v[i] for v in bb)) for i in range(3))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    cam.location = centre + Vector((size * 1.3, -size * 1.5, size * 1.1))
    cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.5
    sun.rotation_euler = (0.7, 0.2, 0.8)
    scene.collection.objects.link(sun)
    scene.world.color = (0.35, 0.42, 0.5)
    bpy.ops.mesh.primitive_plane_add(size=size * 6, location=(centre.x, centre.y, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new('g'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.24, 0.1, 1)
    ground.data.materials.append(gm)
    scene.render.filepath = os.path.join(render_dir, f'{name}.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out_dir, which = args[0], args[1]
    render_dir = args[2] if len(args) > 2 else None
    names = list(PROPS) if which == 'all' else which.split(',')
    for name in names:
        hero.begin('nature')
        parts = PROPS[name]()
        obj = hero.bake_unit(name.title().replace('_', ''), parts, f'{out_dir}/{name}.glb', f'{out_dir}/tex_{name}', size=256)
        print('TRIANGLES', name, hero.tri_count(obj))
        hero.export(obj, f'{out_dir}/{name}.glb')
        if render_dir:
            os.makedirs(render_dir, exist_ok=True)
            preview(obj, render_dir, name)
