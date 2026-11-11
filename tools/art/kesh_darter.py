"""Kesh scout ("Darter"; David picked the first Stinger sample as the scout look), phone budget: <= 2,500 triangles, one shared 512px atlas.

Style target: David's alien reference (hovering lens-shaped silver-bronze hull with etched
pattern, layered side petals with gold slots, dark purple obsidian chips and insets that catch light, swept crescent fin, long gold-slotted barrel,
glowing core orb). Lightning is NOT geometry: in game it is a cheap animated sprite; the
render adds a few emissive strands after export only to preview the look.

Run with Blender's Python (pip bpy):
  python kesh_darter.py <atlas_dir> <out.glb> [render_dir]
Front is +X, up is +Z (Blender); glTF export turns it into +X forward, +Y up.
Nodes: Hull (body), TurretPivot (empty at the turret ring) > Turret.
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

TILES = {  # u0, v0, u1, v1 in UV space (v up), from tools/art/atlas_kesh.py
    'shell': (0.0, 0.5, 0.5, 1.0),
    'fin': (0.5, 0.5, 1.0, 1.0),
    'under': (0.0, 0.25, 0.5, 0.5),
    'barrel': (0.5, 0.25, 1.0, 0.5),
    'glow': (0.0, 0.0, 0.25, 0.25),
    'core': (0.25, 0.0, 0.5, 0.25),
    'dark': (0.5, 0.0, 0.75, 0.25),
    'obsidian': (0.75, 0.0, 1.0, 0.25),
}

mat = bpy.data.materials.new('KeshAtlas')
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes['Principled BSDF']
base = nt.nodes.new('ShaderNodeTexImage')
base.image = bpy.data.images.load(f'{atlas_dir}/kesh_atlas.png')
emi = nt.nodes.new('ShaderNodeTexImage')
emi.image = bpy.data.images.load(f'{atlas_dir}/kesh_emissive.png')
nt.links.new(base.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(emi.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = 2.5
bsdf.inputs['Metallic'].default_value = 0.85
bsdf.inputs['Roughness'].default_value = 0.32

# Obsidian: same atlas, but glossy glass-like so the facets catch light (second material).
obs = mat.copy()
obs.name = 'KeshObsidian'
ob = obs.node_tree.nodes['Principled BSDF']
ob.inputs['Metallic'].default_value = 0.2
ob.inputs['Roughness'].default_value = 0.04
ob.inputs['Specular IOR Level'].default_value = 1.0
ob.inputs['Coat Weight'].default_value = 1.0


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


def mesh_from(name, verts, faces, tile, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    fit_uv(obj, tile)
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    return obj


def loft(name, sections, ring, tile, smooth=True, cy=0.0, top_scale=1.0):
    """Lens-like body along X. sections: list of (x, half_width, z_top, z_bottom, z_mid).
    The first and last sections may have half_width 0 (pointed tip)."""
    verts, faces = [], []
    rows = []
    for x, w, zt, zb, zm in sections:
        row = []
        for k in range(ring):
            a = 2 * math.pi * k / ring
            c, s = math.cos(a), math.sin(a)
            z = zm + (zt - zm) * s if s > 0 else zm + (zm - zb) * s
            row.append(len(verts))
            verts.append((x, cy + w * c, z))
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(ring):
            j = (k + 1) % ring
            faces.append([r0[k], r0[j], r1[j], r1[k]])
    faces.append(rows[0][::-1])
    faces.append(rows[-1])
    obj = mesh_from(name, verts, faces, tile, smooth)
    # Merge the collapsed tip vertices so the ends are clean points.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def prism(name, profile, y0, y1, tile, smooth=False):
    n = len(profile)
    verts = [(x, y0, z) for x, z in profile] + [(x, y1, z) for x, z in profile]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return mesh_from(name, verts, faces, tile, smooth)


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
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.select_set(False)
    obj.data.materials.append(mat)
    fit_uv(obj, tile)
    return obj


def orb(name, c, r, tile):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r)
    bmesh.ops.translate(bm, verts=bm.verts, vec=c)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    fit_uv(obj, tile)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def shard(name, c, size, rng, elong=2.2, sides=5):
    """A faceted obsidian chip: a squat bipyramid, randomly turned, flat shaded."""
    import mathutils
    verts = [(0, 0, size * elong), (0, 0, -size * 0.4)]
    for k in range(sides):
        a = 2 * math.pi * k / sides + rng.uniform(-0.2, 0.2)
        r = size * rng.uniform(0.8, 1.15)
        verts.append((r * math.cos(a), r * math.sin(a), size * rng.uniform(0.1, 0.5)))
    faces = []
    for k in range(sides):
        j = (k + 1) % sides
        faces.append([0, 2 + k, 2 + j])
        faces.append([1, 2 + j, 2 + k])
    rot = mathutils.Euler((rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(0, 6.3))).to_matrix()
    verts = [tuple(rot @ mathutils.Vector(v) + mathutils.Vector(c)) for v in verts]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(obs)
    fit_uv(obj, 'obsidian')
    return obj


def lens(x0, x1, w, zt, zb, zm, n=9, nose=0.55):
    """Sections for a pointed lens: widest a bit forward of centre, sharper nose."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + (x1 - x0) * t
        k = math.sin(math.pi * (t ** nose if t < 1 else 1)) if 0 < t < 1 else 0.0
        out.append((x, w * k, zm + (zt - zm) * k, zm - (zm - zb) * k, zm))
    return out


HOVER = 0.75  # hull floats; the ground shadow sells it
rng_obs = random.Random(5)
parts = []
# --- Hull: a wide pointed lens, flatter underneath.
parts.append(loft('HullCore', lens(-3.4, 3.6, 1.55, HOVER + 1.05, HOVER + 0.05, HOVER + 0.45), 12, 'shell'))
# Underside hover plate with the gold ring.
under = []
for k in range(14):
    a = 2 * math.pi * k / 14
    under.append((0.2 + 2.2 * math.cos(a), 1.1 * math.sin(a)))
verts = [(x, y, HOVER + 0.02) for x, y in under]
parts.append(mesh_from('HoverPlate', verts, [list(range(len(verts)))[::-1]], 'under'))

# Layered side petals: overlapping curved armour plates with gold slots beneath.
for side in (1, -1):
    for i, (x0, x1, y, zm) in enumerate(((-3.0, 0.5, 1.25, HOVER + 0.45), (-0.7, 3.2, 1.35, HOVER + 0.4))):
        petal = loft(f'Petal{side}{i}', lens(x0, x1, 0.38, zm + 0.5, zm - 0.3, zm, n=7, nose=1.0),
                     8, 'fin', cy=side * y)
        parts.append(petal)
        # Gold slot glow tucked under each petal.
        slot = [(x0 + 0.5, zm - 0.12), (x1 - 0.6, zm - 0.12), (x1 - 0.9, zm - 0.02), (x0 + 0.8, zm - 0.02)]
        yy = side * (y + 0.18)
        parts.append(prism(f'Slot{side}{i}', slot, min(yy, yy + side * 0.05), max(yy, yy + side * 0.05), 'glow'))
    # Glowing core orb on each flank, between the petals (as in the reference).
    parts.append(orb(f'Core{side}', (0.6, side * 1.6, HOVER + 0.5), 0.36, 'core'))
    # Obsidian inset along each petal's outer face, and chips clustered round the core orb.
    for i, (x0, x1, y, zm) in enumerate(((-2.6, 0.1, 1.62, HOVER + 0.6), (-0.2, 2.7, 1.72, HOVER + 0.55))):
        o = loft(f'Inset{side}{i}', lens(x0, x1, 0.12, zm + 0.3, zm - 0.16, zm, n=6, nose=1.0), 6, 'obsidian',
                 smooth=False, cy=side * y)
        o.data.materials.clear(); o.data.materials.append(obs)
        parts.append(o)
    for k in range(5):
        a = 2 * math.pi * k / 5
        parts.append(shard(f'CoreChip{side}{k}', (0.6 + 0.5 * math.cos(a), side * 1.55, HOVER + 0.5 + 0.45 * math.sin(a)),
                           0.16, rng_obs, elong=1.6))
# Dorsal spine of obsidian shards along the hull top, behind and ahead of the turret.
for k, x in enumerate((-3.0, -2.6, -2.2, 2.2, 2.65, 3.05)):
    parts.append(shard(f'Spine{k}', (x, 0, HOVER + 1.0 - 0.12 * abs(x - 0.1) / 3), 0.22, rng_obs, elong=2.6))
# Two small rear tail fins.
for side in (1, -1):
    tail = [(-3.3, HOVER + 0.6), (-2.4, HOVER + 0.8), (-3.0, HOVER + 1.6), (-3.6, HOVER + 1.9)]
    parts.append(prism(f'Tail{side}', tail, side * 0.55 - 0.05, side * 0.55 + 0.05, 'fin'))

# --- Turret: an elongated swept pod, a rising crescent fin, one long gold-slotted barrel.
tz = HOVER + 1.0
turret = [loft('TurretBody', lens(-2.0, 1.8, 0.75, tz + 0.75, tz - 0.05, tz + 0.25, n=8, nose=0.7), 10, 'shell')]
# Shoulder plates.
for side in (1, -1):
    turret.append(loft(f'Shoulder{side}', lens(-1.4, 1.2, 0.3, tz + 0.55, tz + 0.05, tz + 0.3, n=6),
                       6, 'fin', cy=side * 0.78))
# Crescent fin: thick at the root behind the turret, sweeping up and forward to a point.
outer, inner = [], []
for i in range(9):
    a = math.radians(200 - 150 * i / 8)  # from low-back, over the top, toward the front
    outer.append((-1.3 + 1.7 * math.cos(a), tz + 0.3 + 1.7 * math.sin(a) * 0.85))
    th = 0.5 * math.sin(math.pi * i / 8) ** 0.7 + 0.03
    inner.append((-1.3 + (1.7 - th) * math.cos(a), tz + 0.3 + (1.7 - th) * math.sin(a) * 0.85))
fin_profile = [p for p in outer] + inner[::-1]
turret.append(prism('Crescent', fin_profile, -0.1, 0.1, 'shell', smooth=False))
# Mantlet collar, barrel sleeve with gold slots, slim barrel, muzzle ring.
turret.append(cylinder_x('Collar', 1.3, 2.3, 0, tz + 0.3, 0.3, 10, 'dark'))
turret.append(cylinder_x('Sleeve', 2.2, 4.4, 0, tz + 0.3, 0.16, 8, 'shell'))
turret.append(cylinder_x('Barrel', 4.3, 7.1, 0, tz + 0.3, 0.1, 8, 'shell'))
turret.append(cylinder_x('BarrelGlow', 4.7, 6.6, 0, tz + 0.3, 0.105, 8, 'barrel'))
turret.append(cylinder_x('Muzzle', 6.9, 7.3, 0, tz + 0.3, 0.14, 8, 'fin'))
turret.append(orb('MuzzleCore', (7.35, 0, tz + 0.3), 0.1, 'glow'))
# Obsidian chips set into the turret crown and along the crescent fin.
for k, (x, y, z) in enumerate(((-0.6, 0.35, tz + 0.72), (-0.1, -0.3, tz + 0.74), (0.5, 0.2, tz + 0.66),
                               (-1.1, -0.1, tz + 0.66))):
    turret.append(shard(f'Crown{k}', (x, y, z), 0.19, rng_obs, elong=1.8))
for i in (2, 4, 6):
    x, z = outer[i]
    turret.append(shard(f'FinChip{i}', (x, 0, z), 0.17, rng_obs, elong=1.4))


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
pivot.location = (0.0, 0, tz)
turret_obj.parent = pivot
turret_obj.location = (0, 0, -tz)
root = bpy.data.objects.new('Darter', None)
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
    # Preview of the in-game lightning effect (a few emissive strands). Not part of the GLB.
    lm = bpy.data.materials.new('Lightning'); lm.use_nodes = True
    ln = lm.node_tree.nodes['Principled BSDF']
    ln.inputs['Base Color'].default_value = (1, 0.8, 0.3, 1)
    ln.inputs['Emission Color'].default_value = (1, 0.75, 0.25, 1)
    ln.inputs['Emission Strength'].default_value = 12
    rng = random.Random(4)
    for s in range(5):
        a0 = rng.uniform(0, 2 * math.pi)
        pts = []
        for i in range(30):
            a = a0 + i * 0.09
            r = 2.1 + rng.uniform(-0.2, 0.2)
            pts.append((0.2 + 1.5 * r * math.cos(a), 0.75 * r * math.sin(a), HOVER + 0.2 + rng.uniform(-0.25, 0.2)))
        if s < 2:  # one strand earthing to the ground
            x, y, z = pts[-1]
            pts += [(x + rng.uniform(-0.25, 0.25), y + rng.uniform(-0.25, 0.25), z * t) for t in (0.8, 0.6, 0.4, 0.2, 0.0)]
        cu = bpy.data.curves.new(f'Bolt{s}', 'CURVE'); cu.dimensions = '3D'
        cu.bevel_depth = 0.007
        sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
        for p, (x, y, z) in zip(sp.points, pts):
            p.co = (x, y, z, 1)
        ob = bpy.data.objects.new(f'Bolt{s}', cu); ob.data.materials.append(lm)
        scene.collection.objects.link(ob)

    world = bpy.data.worlds.new('W'); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.06, 0.04, 0.09, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 3.0
    sun.data.color = (1.0, 0.92, 0.85)
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    scene.collection.objects.link(sun)
    rim = bpy.data.objects.new('Rim', bpy.data.lights.new('Rim', 'AREA'))
    rim.data.energy = 700; rim.data.size = 6; rim.location = (-6, 6, 5); rim.data.color = (0.75, 0.6, 1.0)
    rim.rotation_euler = (math.radians(60), 0, math.radians(-135))
    scene.collection.objects.link(rim)
    bpy.ops.mesh.primitive_plane_add(size=60)
    ground = bpy.context.object
    gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.08, 0.07, 0.09, 1)
    ground.data.materials.append(gm)
    pivot.rotation_euler = (0, 0, math.radians(-12))
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def look(name, loc, target=(0.6, 0, 1.4), lens_mm=50):
        cam.location = loc
        d = [t - l for t, l in zip(target, loc)]
        cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        cam.data.lens = lens_mm
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)

    look('darter_front34', (11, -9, 5.0))
    look('darter_side', (0.8, -15, 2.6))
    look('darter_rts', (9, -9, 16), lens_mm=40)
