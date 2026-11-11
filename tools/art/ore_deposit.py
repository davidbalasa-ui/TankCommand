"""Ore deposit samples from David's references, <= 1,500 triangles each, one 512px atlas.

  pink: a faceted magenta crystal with a swirling glowing core, half-buried in red rock, shards around.
  opal: an iridescent blue / violet / gold opal mass growing out of dark wet rock, with a crystal cluster.
The sparkle is a cheap particle effect in game; the render adds a few glints only as a preview.
As ore is mined the crystal scales down (engine side), so one model covers full to nearly empty.

Run with Blender's Python (pip bpy):
  python ore_deposit.py <atlas_dir> <pink|opal> <out.glb> [render_dir]
"""
import math
import random
import sys

import bpy
import bmesh
import mathutils

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
atlas_dir, variant, out_glb = args[0], args[1], args[2]
render_dir = args[3] if len(args) > 3 else None
assert variant in ('pink', 'opal'), variant

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
TILES = {
    'pink': (0.0, 0.5, 0.5, 1.0),
    'opal': (0.5, 0.5, 1.0, 1.0),
    'red': (0.0, 0.0, 0.5, 0.5),
    'wet': (0.5, 0.0, 1.0, 0.5),
}


def make_mat(name, glass, emit_strength, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    b = t.nodes['Principled BSDF']
    base = t.nodes.new('ShaderNodeTexImage')
    base.image = bpy.data.images.load(f'{atlas_dir}/ore_atlas.png')
    emi = t.nodes.new('ShaderNodeTexImage')
    emi.image = bpy.data.images.load(f'{atlas_dir}/ore_emissive.png')
    t.links.new(base.outputs['Color'], b.inputs['Base Color'])
    t.links.new(emi.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = emit_strength
    b.inputs['Roughness'].default_value = roughness
    if glass:
        b.inputs['Coat Weight'].default_value = 1.0
        b.inputs['Specular IOR Level'].default_value = 1.0
    return m


gem = make_mat('OreGem', True, 2.2, 0.05)
stone = make_mat('OreRock', False, 0.0, 0.45 if variant == 'opal' else 0.9)
rng = random.Random(17 if variant == 'pink' else 23)


def fit_uv(obj, tile, margin=0.01):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    u0, v0, u1, v1 = TILES[tile]
    u0 += margin; v0 += margin; u1 -= margin; v1 -= margin
    for loop in obj.data.uv_layers.active.data:
        u, v = loop.uv
        loop.uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def planar_uv(obj, tile, c, size, margin=0.01):
    """Project from the front (x, z) so one swirl spans the whole gem, like the references."""
    u0, v0, u1, v1 = TILES[tile]
    u0 += margin; v0 += margin; u1 -= margin; v1 -= margin
    me = obj.data
    for poly in me.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            co = me.vertices[vi].co
            u = min(1, max(0, (co.x - c[0] + 0.35 * (co.y - c[1])) / (2 * size) + 0.5))
            v = min(1, max(0, (co.z - c[2]) / (2 * size) + 0.5))
            me.uv_layers.active.data[li].uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def hull(name, points, tile, material, smooth=False, planar=None):
    """Convex hull of a point cloud: the cheapest way to get a natural faceted rock or gem."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    fit_uv(obj, tile)
    if planar:
        planar_uv(obj, tile, *planar)
    for p in obj.data.polygons:
        p.use_smooth = smooth
    return obj


def blob(c, sx, sy, sz, n, jitter, zmin=None):
    pts = []
    for _ in range(n):
        v = mathutils.Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        k = rng.uniform(1 - jitter, 1)
        p = (c[0] + v.x * sx * k, c[1] + v.y * sy * k, c[2] + v.z * sz * k)
        if zmin is not None:
            p = (p[0], p[1], max(zmin, p[2]))
        pts.append(p)
    return pts


def shard(name, c, length, w, tilt, yaw, tile):
    rot = mathutils.Euler((tilt, 0, yaw)).to_matrix()
    pts = [(0, 0, length), (0, 0, -0.2 * length)]
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.2, 0.2)
        pts.append((w * math.cos(a), w * math.sin(a), rng.uniform(0, 0.3) * length))
    pts = [tuple(rot @ mathutils.Vector(p) + mathutils.Vector(c)) for p in pts]
    return hull(name, pts, tile, gem)


objs = []
if variant == 'pink':
    # Rock pit: a low lumpy ring of red rock the crystal is sunk into.
    for k in range(7):
        a = 2 * math.pi * k / 7
        r = rng.uniform(2.6, 3.1)
        objs.append(hull(f'Rock{k}', blob((r * math.cos(a), r * math.sin(a), 0.1), 1.3, 1.1, 0.8, 18, 0.45, zmin=-0.2),
                         'red', stone))
    # The crystal: a big tilted faceted lump, a third of it below ground.
    pts = blob((0, 0, 0.9), 2.4, 1.7, 2.0, 44, 0.3, zmin=-0.4)
    gem_obj = hull('Crystal', pts, 'pink', gem, planar=((0, 0, 0.9), 2.4))
    gem_obj.rotation_euler = (0.25, -0.35, 0.4)
    objs.append(gem_obj)
    for k in range(6):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(2.2, 3.4)
        objs.append(shard(f'Shard{k}', (r * math.cos(a), r * math.sin(a), 0.1), rng.uniform(0.6, 1.3),
                          rng.uniform(0.15, 0.3), rng.uniform(0.3, 0.9), a + math.pi / 2, 'pink'))
else:
    # Dark wet rock bed with a few boulders.
    objs.append(hull('Bed', blob((0, 0, -0.1), 3.6, 3.0, 0.7, 30, 0.35, zmin=-0.3), 'wet', stone))
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        objs.append(hull(f'Boulder{k}', blob((2.6 * math.cos(a), 2.4 * math.sin(a), 0.4), 0.9, 0.8, 0.8, 14, 0.4),
                         'wet', stone))
    # The opal: a smooth rounded mass, rock crust on its back end.
    objs.append(hull('Opal', blob((-0.2, 0, 1.2), 2.2, 1.6, 1.4, 90, 0.22, zmin=0.0), 'opal', gem, smooth=True,
                     planar=((-0.2, 0, 1.2), 2.2)))
    objs.append(hull('Crust', blob((1.4, 0.2, 1.1), 1.0, 1.3, 1.2, 16, 0.4), 'wet', stone))
    # A cluster of iridescent crystals bursting from the crust.
    for k in range(6):
        yaw = rng.uniform(-0.8, 0.8)
        objs.append(shard(f'Cluster{k}', (1.6, rng.uniform(-0.5, 0.5), 1.0), rng.uniform(0.9, 1.5),
                          rng.uniform(0.15, 0.25), rng.uniform(0.5, 1.2), yaw - math.pi / 2, 'opal'))

for o in objs:
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    o.select_set(False)
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
deposit = bpy.context.object
deposit.name = f'OreDeposit_{variant}'
deposit.data.calc_loop_triangles()
tris = len(deposit.data.loop_triangles)
print('TRIANGLES', tris)
assert tris <= 1500, tris

bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=True, export_yup=True)

if render_dir:
    # Sparkle preview (in game: a few camera-facing glints).
    sm = bpy.data.materials.new('Sparkle'); sm.use_nodes = True
    sb = sm.node_tree.nodes['Principled BSDF']
    sb.inputs['Base Color'].default_value = (0, 0, 0, 1)
    sb.inputs['Emission Color'].default_value = (1, 0.9, 1, 1)
    sb.inputs['Emission Strength'].default_value = 12
    for _ in range(40):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.02, 0.05),
                                              location=(rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(0.1, 3.2)))
        bpy.context.object.data.materials.append(sm)
    world = bpy.data.worlds.new('W'); scene.world = world
    world.use_nodes = True
    bg = (0.09, 0.03, 0.08, 1) if variant == 'pink' else (0.02, 0.03, 0.05, 1)
    world.node_tree.nodes['Background'].inputs['Color'].default_value = bg
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    scene.collection.objects.link(sun)
    glow = bpy.data.objects.new('Glow', bpy.data.lights.new('Glow', 'POINT'))
    glow.data.energy = 900
    glow.data.color = (1.0, 0.3, 0.8) if variant == 'pink' else (0.4, 0.5, 1.0)
    glow.location = (0, -1.5, 2.5)
    scene.collection.objects.link(glow)
    bpy.ops.mesh.primitive_plane_add(size=60)
    ground = bpy.context.object
    gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
    gcol = (0.18, 0.07, 0.06, 1) if variant == 'pink' else (0.04, 0.04, 0.05, 1)
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = gcol
    ground.data.materials.append(gm)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def look(name, loc, target, lens_mm):
        cam.location = loc
        d = [t - l for t, l in zip(target, loc)]
        cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        cam.data.lens = lens_mm
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)

    look(f'ore_{variant}_front34', (8, -8, 4.5), (0, 0, 1.0), 40)
    look(f'ore_{variant}_rts', (9, -9, 16), (0, 0, 0.5), 40)
