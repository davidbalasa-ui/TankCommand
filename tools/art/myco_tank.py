"""Third faction (mushroom tanks, working name Myco) sample tank, phone budget <= 2,500 triangles.

Style target: David's reference, made completely organic at his request (no wheels, tracks or
banner): a lumpy fungal bulb that crawls on thick mycelium root legs, a big red white-spotted cap
on a stalk, a chanterelle-like gill funnel blowing golden spore clouds, glowing spore sacs, small
mushrooms sprouting all over, and a crest of purple bracket fungus instead of a banner.
The spore cloud is a cheap particle effect in game; the render adds one only as a preview.

Run with Blender's Python (pip bpy):
  python myco_tank.py <atlas_dir> <out.glb> [render_dir]
Nodes: Hull (body, roots), TurretPivot (empty at the stalk base) > Turret (stalk, cap, funnel).
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
    'flesh': (0.0, 0.5, 0.5, 1.0),
    'cap': (0.5, 0.5, 1.0, 1.0),
    'gill': (0.0, 0.25, 0.5, 0.5),
    'myc': (0.5, 0.25, 1.0, 0.5),
    'bulb': (0.0, 0.0, 0.25, 0.25),
    'ruffle': (0.25, 0.0, 0.5, 0.25),
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


def lathe(name, profile, sides, tile, center=(0, 0, 0), axis='z', smooth=True, close=True, uvs=None):
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
    return link(name, me, tile, smooth, uvs)


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
    stem = lathe(f'{name}Stem', [(0.12 * s, 0), (0.09 * s, 0.45 * s)], 6, 'flesh', (x, y, z), smooth=False)
    cap = lathe(f'{name}Cap', [(0.0, 0.38 * s), (0.36 * s, 0.4 * s), (0.28 * s, 0.6 * s), (0.0, 0.72 * s)],
                8, tile, (x, y, z))
    return [stem, cap]


rng = random.Random(9)


def tube(name, pts, r0, r1, sides, tile):
    """A tapered organic tube along a polyline (root legs, tendrils)."""
    import mathutils
    P = [mathutils.Vector(p) for p in pts]
    verts, faces = [], []
    n = len(P)
    for i, p in enumerate(P):
        t = i / (n - 1)
        fwd = (P[min(n - 1, i + 1)] - P[max(0, i - 1)]).normalized()
        side = fwd.cross(mathutils.Vector((0, 0, 1)))
        if side.length < 1e-3:
            side = mathutils.Vector((1, 0, 0))
        side.normalize()
        up = side.cross(fwd)
        r = r0 + (r1 - r0) * t
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append(tuple(p + (side * math.cos(a) + up * math.sin(a)) * r))
    for i in range(n - 1):
        for k in range(sides):
            j = (k + 1) % sides
            faces.append([i * sides + k, i * sides + j, (i + 1) * sides + j, (i + 1) * sides + k])
    faces.append(list(range(sides))[::-1])
    tip = len(verts)
    verts.append(tuple(P[-1] + (P[-1] - P[-2]).normalized() * r1))
    for k in range(sides):
        j = (k + 1) % sides
        faces.append([(n - 1) * sides + k, (n - 1) * sides + j, tip])
    return mesh_from(name, verts, faces, tile, smooth=True)


def orb(name, c, r, tile, squash=1.0):
    return lathe(name, [(0, -r * squash), (r * 0.7, -r * 0.7 * squash), (r, 0), (r * 0.7, r * 0.7 * squash),
                        (0, r * squash)], 8, tile, c)


parts = []
# --- Body: a soft, lumpy volva (the bulb a mushroom grows from), longer than wide. No wheels or tracks.
body = lathe('Body', [(0.0, 0.55), (1.6, 0.6), (2.1, 0.95), (2.15, 1.35), (1.85, 1.7), (1.2, 1.95), (0.0, 2.0)],
             14, 'flesh')
for v in body.data.vertices:  # stretch along X and add lumps, so it reads as grown, not turned
    a = math.atan2(v.co.y, v.co.x)
    bump = 1 + 0.07 * math.sin(5 * a) + 0.05 * math.sin(3 * a + v.co.z * 2)
    v.co.x *= 1.45 * bump
    v.co.y *= 1.0 * bump
parts.append(body)
# Root legs: thick mycelium roots splay out and grip the ground; the tank crawls on them.
for side in (1, -1):
    for i, x in enumerate((-2.4, -1.2, 0.0, 1.2, 2.4)):
        lean = 0.35 * x / 2.4
        pts = [(x * 0.9, side * 1.3, 1.1),
               (x * 0.95 + lean * 0.3, side * 1.95, 0.95),
               (x + lean * 0.6, side * 2.45, 0.55),
               (x + lean, side * 2.7, 0.18),
               (x + lean * 1.3, side * 2.85, 0.02)]
        parts.append(tube(f'Root{side}{i}', pts, 0.32, 0.08, 6, 'myc'))
# Mycelium mat spreading on the ground under the body.
mat_pts = []
for k in range(16):
    a = 2 * math.pi * k / 16
    r = rng.uniform(2.6, 3.4)
    mat_pts.append((1.25 * r * math.cos(a), r * math.sin(a) * 0.95, 0.03))
parts.append(mesh_from('Mat', mat_pts, [list(range(16))], 'myc'))
# Glowing spore sacs along the flanks, and small mushrooms sprouting all over the back.
for side in (1, -1):
    for x in (-1.6, 0.2, 1.8):
        parts.append(orb(f'Sac{side}{x}', (x, side * 1.95, 1.25), 0.24, 'bulb', squash=0.8))
for i, (x, y, z, s_) in enumerate(((2.2, 0.8, 1.55, 1.1), (2.5, -0.6, 1.45, 0.9), (-2.3, 0.8, 1.6, 1.0),
                                   (-2.1, -0.9, 1.6, 1.3), (1.5, 1.2, 1.6, 0.7), (-1.4, -1.2, 1.7, 0.8),
                                   (2.8, 0.1, 1.3, 0.6), (-2.8, 0.1, 1.4, 0.75), (0.9, -1.3, 1.65, 0.6),
                                   (-0.9, 1.3, 1.7, 0.65))):
    parts += mini_mushroom(f'Mini{i}', x, y, z, s_, 'cap' if i % 3 else 'ruffle')

# --- Turret: stalk, spotted cap with glowing gills, a chanterelle-like funnel that blows spores.
tz = 1.85
turret = []
turret.append(lathe('Stalk', [(1.05, 0.0), (0.85, 0.4), (0.72, 1.1), (0.7, 1.7), (0.85, 1.95)], 10, 'flesh',
                    (-0.3, 0, tz), smooth=True))
cap_z = tz + 1.85
turret.append(lathe('Cap', [(2.15, 0.0), (2.75, 0.15), (2.7, 0.55), (2.25, 1.05), (1.4, 1.45), (0.0, 1.6)],
                    16, 'cap', (-0.3, 0, cap_z), uvs=lambda co: ((co.x + 0.3) / 5.6 + 0.5, co.y / 5.6 + 0.5)))
turret.append(lathe('Gills', [(2.6, 0.12), (0.8, 0.02)], 16, 'gill', (-0.3, 0, cap_z), close=False))
for i, (dx, dy) in enumerate(((0.6, 0.9), (-0.9, -0.6), (-0.4, 1.0))):
    turret.append(lathe(f'PuffStem{i}', [(0.12, 0), (0.1, 0.5)], 6, 'flesh', (-0.3 + dx, dy, cap_z + 1.2), smooth=False))
    turret.append(lathe(f'Puff{i}', [(0, 0.35), (0.3, 0.45), (0.36, 0.7), (0.28, 0.95), (0, 1.05)], 8, 'flesh',
                        (-0.3 + dx, dy, cap_z + 1.2)))
# Funnel: grows out of the stalk, flesh outside, glowing gills inside, wavy ruffled lip.
funnel = lathe('Funnel', [(0.36, 0.0), (0.3, 1.0), (0.34, 1.9), (0.55, 2.6), (0.9, 3.0), (1.15, 3.15)],
               12, 'flesh', (0.2, 0, tz + 1.0), axis='x', close=False)
funnel_in = lathe('FunnelGills', [(1.1, 3.13), (0.85, 2.95), (0.5, 2.6), (0.25, 2.2), (0.0, 2.1)], 12, 'gill',
                  (0.2, 0, tz + 1.0), axis='x', close=False)
for o in (funnel, funnel_in):  # ruffle the lip
    for v in o.data.vertices:
        if v.co.x > 0.2 + 2.7:
            dy, dz = v.co.y, v.co.z - (tz + 1.0)
            a = math.atan2(dz, dy)
            k = 1 + 0.12 * math.sin(6 * a)
            v.co.y, v.co.z = dy * k, (tz + 1.0) + dz * k
            v.co.x += 0.12 * math.sin(6 * a)
turret += [funnel, funnel_in]
# A crest of purple bracket fungus shelves up the back of the stalk (the faction's living banner).
for k, (z, r) in enumerate(((0.5, 0.75), (1.0, 0.65), (1.45, 0.55))):
    shelf = lathe(f'Shelf{k}', [(0.0, 0.08), (r * 0.6, 0.06), (r, 0.0), (r * 0.6, -0.05), (0.0, -0.06)], 8,
                  'ruffle', (-0.3 - 0.75, 0, tz + z))
    for v in shelf.data.vertices:  # keep only the half that sticks out backwards
        if v.co.x > -0.3 - 0.75:
            v.co.x = -0.3 - 0.75 + (v.co.x - (-0.3 - 0.75)) * 0.15
    turret.append(shelf)


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
