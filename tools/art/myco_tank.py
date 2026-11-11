"""Third faction (mushroom tanks, working name Myco) sample tank, phone budget <= 2,500 triangles.

Style target: David's reference (tracked hull carved from pale fungus wood, gold spoked wheels,
a big red white-spotted cap on a thick stalk, a trumpet-shaped gill cannon firing golden spore
clouds, small mushrooms sprouting on the hull, a red banner with a mushroom crest).
The spore cloud is a cheap particle effect in game; the render adds one only as a preview.

Run with Blender's Python (pip bpy):
  python myco_tank.py <atlas_dir> <out.glb> [render_dir]
Nodes: Hull (body), TurretPivot (empty at the stalk base) > Turret (stalk, cap, cannon).
"""
import math
import random
import sys

import bpy
import bmesh

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
atlas_dir, out_glb = args[0], args[1]
render_dir = args[2] if len(args) > 2 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

TILES = {  # u0, v0, u1, v1 in UV space (v up), from tools/art/atlas_myco.py
    'wood': (0.0, 0.5, 0.5, 1.0),
    'cap': (0.5, 0.5, 1.0, 1.0),
    'gill': (0.0, 0.25, 0.5, 0.5),
    'track': (0.5, 0.25, 1.0, 0.5),
    'wheel': (0.0, 0.0, 0.25, 0.25),
    'banner': (0.25, 0.0, 0.5, 0.25),
    'moss': (0.5, 0.0, 0.75, 0.25),
    'spore': (0.75, 0.0, 1.0, 0.25),
}

mat = bpy.data.materials.new('MycoAtlas')
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes['Principled BSDF']
base = nt.nodes.new('ShaderNodeTexImage')
base.image = bpy.data.images.load(f'{atlas_dir}/myco_atlas.png')
emi = nt.nodes.new('ShaderNodeTexImage')
emi.image = bpy.data.images.load(f'{atlas_dir}/myco_emissive.png')
nt.links.new(base.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(emi.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = 2.0
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.75


def squeeze(obj, tile, margin=0.01):
    u0, v0, u1, v1 = TILES[tile]
    u0 += margin; v0 += margin; u1 -= margin; v1 -= margin
    for loop in obj.data.uv_layers.active.data:
        u, v = loop.uv
        loop.uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def fit_uv(obj, tile):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    squeeze(obj, tile)


def link(name, me, tile, smooth, uvs=None):
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    if uvs is None:
        fit_uv(obj, tile)
    else:
        layer = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                layer.data[li].uv = uvs(me.vertices[vi].co)
        squeeze(obj, tile)
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    return obj


def mesh_from(name, verts, faces, tile, smooth=False, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return link(name, me, tile, smooth, uvs)


def prism(name, profile, y0, y1, tile, smooth=False):
    n = len(profile)
    verts = [(x, y0, z) for x, z in profile] + [(x, y1, z) for x, z in profile]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return mesh_from(name, verts, faces, tile, smooth)


def box(name, c, s, tile):
    (cx, cy, cz), (sx, sy, sz) = c, s
    return prism(name, [(cx - sx, cz - sz), (cx + sx, cz - sz), (cx + sx, cz + sz), (cx - sx, cz + sz)],
                 cy - sy, cy + sy, tile)


def lathe(name, profile, sides, tile, center=(0, 0, 0), axis='z', smooth=True, close=True):
    """Revolve a profile of (radius, height) around an axis. Radius 0 points become poles."""
    cx, cy, cz = center
    verts, faces, rows = [], [], []
    for r, h in profile:
        row = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            u, v = r * math.cos(a), r * math.sin(a)
            if axis == 'z':
                p = (cx + u, cy + v, cz + h)
            else:  # along +X
                p = (cx + h, cy + u, cz + v)
            row.append(len(verts))
            verts.append(p)
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(sides):
            j = (k + 1) % sides
            faces.append([r0[k], r0[j], r1[j], r1[k]])
    if close:
        faces.append(rows[0][::-1])
        faces.append(rows[-1])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(me)
    bm.free()
    return link(name, me, tile, smooth)


def wheel(name, x, y, z, r, w, sides=12):
    """A short cylinder along Y with planar UVs so the gold spokes land on the faces."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=r, radius2=r, depth=w)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=__import__('mathutils').Matrix.Rotation(math.pi / 2, 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, z))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(name, me, 'wheel', False, uvs=lambda co: ((co.x - x) / (2 * r) + 0.5, (co.z - z) / (2 * r) + 0.5))


def mini_mushroom(name, x, y, z, s, tile='cap'):
    stem = lathe(f'{name}Stem', [(0.12 * s, 0), (0.09 * s, 0.45 * s)], 6, 'wood', (x, y, z), smooth=False)
    cap = lathe(f'{name}Cap', [(0.0, 0.38 * s), (0.36 * s, 0.4 * s), (0.28 * s, 0.6 * s), (0.0, 0.72 * s)],
                8, tile, (x, y, z))
    return [stem, cap]


rng = random.Random(9)
parts = []
# --- Hull: carved fungus-wood body, chunky and rounded at the corners.
hull_profile = [(-2.9, 0.55), (2.5, 0.55), (3.1, 0.95), (2.6, 1.5), (-2.5, 1.55), (-3.0, 1.2)]
parts.append(prism('HullCore', hull_profile, -1.2, 1.2, 'wood'))
for side, y in (('L', 1.55), ('R', -1.55)):
    pod = [(-3.2, 0.1), (2.9, 0.1), (3.35, 0.55), (2.9, 1.0), (-3.15, 1.0), (-3.45, 0.55)]
    parts.append(prism(f'Track{side}', pod, y - 0.4, y + 0.4, 'track'))
    sign = 1 if y > 0 else -1
    for i, x in enumerate((-2.4, -1.2, 0.0, 1.2, 2.4)):
        parts.append(wheel(f'Wheel{side}{i}', x, y + sign * 0.43, 0.55, 0.48, 0.1))
    # Moss and vines along the upper hull edge.
    parts.append(box(f'Moss{side}', (-0.2, sign * 1.15, 1.5), (2.3, 0.08, 0.06), 'moss'))
# Little mushrooms sprouting on the deck.
for i, (x, y, s) in enumerate(((2.0, 0.8, 1.1), (2.3, -0.7, 0.9), (-2.2, 0.85, 1.0), (-2.0, -0.9, 1.3),
                               (1.4, 1.0, 0.7), (-1.5, -1.05, 0.8), (2.6, 0.2, 0.6), (-2.6, 0.1, 0.75),
                               (0.9, -1.05, 0.6), (-0.9, 1.05, 0.65))):
    parts += mini_mushroom(f'Mini{i}', x, y, 1.52, s, 'cap' if i % 2 == 0 else 'gill')

# --- Turret: thick stalk, big spotted cap with glowing gills, trumpet gill cannon.
tz = 1.55
turret = []
turret.append(lathe('Stalk', [(1.15, 0.0), (0.95, 0.4), (0.75, 1.2), (0.7, 1.9), (0.85, 2.15)], 10, 'wood',
                    (-0.3, 0, tz), smooth=True))
cap_z = tz + 2.0
turret.append(lathe('Cap', [(2.15, 0.0), (2.75, 0.15), (2.7, 0.55), (2.25, 1.05), (1.4, 1.45), (0.0, 1.6)],
                    16, 'cap', (-0.3, 0, cap_z)))
turret.append(lathe('Gills', [(2.6, 0.12), (0.8, 0.02)], 16, 'gill', (-0.3, 0, cap_z), close=False))
# Round gold window set in each side of the stalk (as in the reference).
for side in (1, -1):
    turret.append(wheel(f'Window{side}', -0.3, side * 0.86, tz + 0.95, 0.36, 0.08, sides=10))
# Puffball sprouts on the cap (morel-like knobs), on short stems.
for i, (dx, dy) in enumerate(((0.6, 0.9), (-0.9, -0.6), (-0.4, 1.0))):
    turret.append(lathe(f'PuffStem{i}', [(0.12, 0), (0.1, 0.5)], 6, 'wood', (-0.3 + dx, dy, cap_z + 1.2), smooth=False))
    turret.append(lathe(f'Puff{i}', [(0, 0.35), (0.3, 0.45), (0.36, 0.7), (0.28, 0.95), (0, 1.05)], 8, 'wood',
                        (-0.3 + dx, dy, cap_z + 1.2)))
# Trumpet cannon: a flared bell along +X, gills inside the mouth.
turret.append(lathe('Trumpet', [(0.4, 0.0), (0.3, 1.2), (0.33, 2.2), (0.52, 2.85), (0.85, 3.2), (1.05, 3.35)],
                    12, 'wood', (0.2, 0, tz + 1.15), axis='x', close=False))
turret.append(lathe('TrumpetGills', [(0.99, 3.33), (0.78, 3.15), (0.47, 2.85), (0.25, 2.45), (0.0, 2.35)], 12,
                    'gill', (0.2, 0, tz + 1.15), axis='x', close=False))
# Banner pole with a mushroom-crest flag at the back of the cap.
turret.append(box('Pole', (-2.0, -0.9, cap_z + 1.6), (0.05, 0.05, 1.7), 'wood'))
flag = [(-2.0, cap_z + 1.9), (-0.9, cap_z + 1.9), (-0.9, cap_z + 3.2), (-2.0, cap_z + 3.2)]
fx0, fz0 = flag[0]
turret.append(mesh_from('Flag', [(x, -0.9, z) for x, z in flag], [[0, 1, 2, 3]], 'banner',
                        uvs=lambda co: ((co.x - fx0) / 1.1, (co.z - fz0) / 1.3)))


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    return obj


hull = join(parts, 'Hull')
turret_obj = join(turret, 'Turret')
pivot = bpy.data.objects.new('TurretPivot', None)
scene.collection.objects.link(pivot)
pivot.location = (-0.3, 0, tz)
turret_obj.parent = pivot
turret_obj.location = (0.3, 0, -tz)
root = bpy.data.objects.new('Sporecaller', None)
scene.collection.objects.link(root)
hull.parent = root
pivot.parent = root

tris = 0
for o in (hull, turret_obj):
    o.data.calc_loop_triangles()
    tris += len(o.data.loop_triangles)
print('TRIANGLES', tris)
assert tris <= 2500, tris

bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=True, export_yup=True)

if render_dir:
    # Preview of the in-game spore cloud: a cone of glowing puffs out of the trumpet. Not in the GLB.
    sm = bpy.data.materials.new('Spores'); sm.use_nodes = True
    sb = sm.node_tree.nodes['Principled BSDF']
    sb.inputs['Base Color'].default_value = (0.05, 0.03, 0.0, 1)
    sb.inputs['Emission Color'].default_value = (1, 0.42, 0.04, 1)
    sb.inputs['Emission Strength'].default_value = 3.0
    sb.inputs['Roughness'].default_value = 1.0
    sb.inputs['Specular IOR Level'].default_value = 0.0
    for i in range(90):
        t = rng.uniform(0, 1)
        x = 3.6 + t * 6
        spread = 0.4 + t * 1.6
        r = rng.uniform(0.04, 0.09) + t * rng.uniform(0.02, 0.18)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r,
                                              location=(x, rng.uniform(-spread, spread), tz + 1.15 + rng.uniform(-spread, spread) * 0.6))
        bpy.context.object.data.materials.append(sm)
        for p in bpy.context.object.data.polygons:
            p.use_smooth = True

    world = bpy.data.worlds.new('W'); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.12, 0.2, 0.42, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.9, 0.7)
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    scene.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=60)
    ground = bpy.context.object
    gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.2, 0.3, 0.1, 1)
    ground.data.materials.append(gm)
    pivot.rotation_euler = (0, 0, math.radians(-12))
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def look(name, loc, target=(0.6, 0, 2.4), lens_mm=45):
        cam.location = loc
        d = [t - l for t, l in zip(target, loc)]
        cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        cam.data.lens = lens_mm
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)

    look('myco_front34', (13, -11, 6.5), target=(0.8, 0, 3.0), lens_mm=38)
    look('myco_side', (1.5, -17, 3.5), target=(1.5, 0, 3.0), lens_mm=38)
    look('myco_rts', (10, -10, 18), target=(0.6, 0, 1.5), lens_mm=40)
