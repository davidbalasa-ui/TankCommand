"""Terran light tank ("Lancer"), phone budget: <= 2,500 triangles, one shared 512px atlas.

Style target: David's reference (dark angular armour, twin long barrels, cyan energy coils,
orange running lights). Detail lives in the atlas (tools/art/atlas_terran.py), not in geometry.

Run with Blender's Python (pip bpy):
  python tank.py <atlas_dir> <out.glb> [render_dir]
Front is +X, up is +Z (Blender); glTF export turns it into +X forward, +Y up.
Nodes: Hull (body), TurretPivot (empty at the turret ring) > Turret, Barrels.
"""
import math
import sys

import bpy
import bmesh

atlas_dir, out_glb = sys.argv[-3], sys.argv[-2]
render_dir = sys.argv[-1] if sys.argv[-1] != out_glb else None
if not render_dir or render_dir.endswith('.glb'):
    atlas_dir, out_glb, render_dir = sys.argv[-2], sys.argv[-1], None

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

TILES = {  # u0, v0, u1, v1 in UV space (v up), from the atlas layout
    'hull': (0.0, 0.5, 0.5, 1.0),
    'turret': (0.5, 0.5, 1.0, 1.0),
    'track': (0.0, 0.25, 0.5, 0.5),
    'barrel': (0.5, 0.25, 1.0, 0.5),
    'glow': (0.0, 0.0, 0.25, 0.25),
    'amber': (0.25, 0.0, 0.5, 0.25),
    'dark': (0.5, 0.0, 1.0, 0.25),
}

# One material for everything: base colour + emissive from the shared faction atlas.
mat = bpy.data.materials.new('TerranAtlas')
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes['Principled BSDF']
base = nt.nodes.new('ShaderNodeTexImage')
base.image = bpy.data.images.load(f'{atlas_dir}/terran_atlas.png')
emi = nt.nodes.new('ShaderNodeTexImage')
emi.image = bpy.data.images.load(f'{atlas_dir}/terran_emissive.png')
nt.links.new(base.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(emi.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = 1.0
bsdf.inputs['Metallic'].default_value = 0.55
bsdf.inputs['Roughness'].default_value = 0.5


def fit_uv(obj, tile, margin=0.01):
    """Box-project the object's UVs, then squeeze them into one atlas tile."""
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


def finish(obj, tile):
    obj.data.materials.append(mat)
    fit_uv(obj, tile)
    for poly in obj.data.polygons:
        poly.use_smooth = False
    return obj


def mesh_from(name, verts, faces, tile):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    return finish(obj, tile)


def prism(name, profile, y0, y1, tile):
    """Extrude a side profile (list of (x, z), counter-clockwise) between y0 and y1."""
    n = len(profile)
    verts = [(x, y0, z) for x, z in profile] + [(x, y1, z) for x, z in profile]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return mesh_from(name, verts, faces, tile)


def box(name, c, s, tile):
    (cx, cy, cz), (sx, sy, sz) = c, s
    prof = [(cx - sx, cz - sz), (cx + sx, cz - sz), (cx + sx, cz + sz), (cx - sx, cz + sz)]
    return prism(name, prof, cy - sy, cy + sy, tile)


def cylinder_x(name, x0, x1, y, z, r, sides, tile):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=r, radius2=r, depth=x1 - x0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.rotation_euler = (0, math.radians(90), 0)
    obj.location = ((x0 + x1) / 2, y, z)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)
    return finish(obj, tile)


parts = []
# --- Hull: low, wide, angular. Side profile in (x, z), front +X.
hull_profile = [(-3.0, 0.55), (2.6, 0.55), (3.2, 0.95), (2.4, 1.45), (-2.7, 1.45), (-3.1, 1.15)]
parts.append(prism('HullCore', hull_profile, -1.25, 1.25, 'hull'))
# Upper deck plate with a sloped glacis, slightly narrower.
deck = [(-2.6, 1.45), (2.2, 1.45), (1.6, 1.75), (-2.3, 1.75)]
parts.append(prism('HullDeck', deck, -1.05, 1.05, 'hull'))
# Track pods: chamfered ends, outside the hull.
pod = [(-3.25, 0.05), (2.95, 0.05), (3.4, 0.55), (3.0, 1.05), (-3.2, 1.05), (-3.45, 0.55)]
for side, y in (('L', 1.62), ('R', -1.62)):
    parts.append(prism(f'Track{side}', pod, y - 0.42, y + 0.42, 'track'))
    # Angled side skirt over the upper track.
    skirt = [(-3.1, 0.7), (2.8, 0.7), (3.15, 1.0), (2.7, 1.32), (-3.0, 1.32)]
    y_out = y + (0.48 if y > 0 else -0.48)
    parts.append(prism(f'Skirt{side}', skirt, min(y, y_out), max(y, y_out), 'hull'))
    # Orange running light at the front of each skirt, cyan strip along it.
    parts.append(box(f'Amber{side}', (3.0, y_out, 1.1), (0.12, 0.05, 0.06), 'amber'))
    parts.append(box(f'Seam{side}', (0.0, y_out + (0.02 if y > 0 else -0.02), 0.95), (2.2, 0.02, 0.03), 'glow'))
# Headlights.
for y in (0.8, -0.8):
    parts.append(box(f'Head{y}', (3.05, y, 1.05), (0.06, 0.18, 0.06), 'glow'))
# Rear engine block.
parts.append(box('Engine', (-2.75, 0, 1.6), (0.35, 0.8, 0.2), 'dark'))

# --- Turret: wedge, set back of centre; everything above the ring rotates.
tx = -0.4
turret_profile = [(tx - 1.6, 1.75), (tx + 1.5, 1.75), (tx + 2.0, 2.15), (tx + 1.4, 2.6), (tx - 1.4, 2.6), (tx - 1.8, 2.2)]
turret = [prism('TurretBody', turret_profile, -1.0, 1.0, 'turret')]
cheek = [(tx + 0.4, 1.85), (tx + 2.2, 1.95), (tx + 1.6, 2.45), (tx + 0.4, 2.45)]
for y in (0.95, -0.95):
    turret.append(prism(f'Cheek{y}', cheek, y - 0.18, y + 0.18, 'turret'))
turret.append(box('Sensor', (tx - 0.6, 0.55, 2.8), (0.25, 0.2, 0.2), 'dark'))
turret.append(box('SensorLens', (tx - 0.33, 0.55, 2.82), (0.03, 0.12, 0.09), 'glow'))
turret.append(box('TurretSeam', (tx + 0.3, 0, 2.62), (1.2, 0.03, 0.02), 'glow'))
# Twin barrels with energy coils (coil band is in the barrel tile's middle third).
for y in (0.32, -0.32):
    turret.append(cylinder_x(f'Barrel{y}', tx + 1.6, tx + 6.6, y, 2.2, 0.17, 8, 'barrel'))
    turret.append(cylinder_x(f'Muzzle{y}', tx + 6.4, tx + 7.0, y, 2.2, 0.23, 8, 'dark'))
    turret.append(cylinder_x(f'Coil{y}', tx + 2.2, tx + 3.6, y, 2.2, 0.22, 8, 'glow'))

# Join into two meshes: Hull and Turret (fewer draw calls), pivot at the turret ring.
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
pivot.location = (tx, 0, 1.75)
turret_obj.parent = pivot
turret_obj.location = (-tx, 0, -1.75)
root = bpy.data.objects.new('Lancer', None)
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
    world = bpy.data.worlds.new('W'); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.025, 0.035, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    scene.collection.objects.link(sun)
    rim = bpy.data.objects.new('Rim', bpy.data.lights.new('Rim', 'AREA'))
    rim.data.energy = 600; rim.data.size = 6; rim.location = (-6, 6, 5)
    rim.rotation_euler = (math.radians(60), 0, math.radians(-135))
    scene.collection.objects.link(rim)
    bpy.ops.mesh.primitive_plane_add(size=60)
    ground = bpy.context.object
    gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.09, 0.08, 0.07, 1)
    ground.data.materials.append(gm)
    pivot.rotation_euler = (0, 0, math.radians(-12))
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    def look(name, loc, target=(0.3, 0, 1.3), lens=50):
        cam.location = loc
        d = [t - l for t, l in zip(target, loc)]
        cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        cam.data.lens = lens
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)
    look('lancer_front34', (11, -9, 5.5))
    look('lancer_side', (0.5, -15, 3.2))
    look('lancer_rts', (9, -9, 16), lens=40)
