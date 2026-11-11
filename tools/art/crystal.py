"""End-game super weapon crystal, big-unit budget: <= 5,000 triangles, one 512px atlas.

Style target: David's reference (a tall floating faceted violet crystal, a swirling glowing
core, violet energy ribbons spiralling around it). Neutral: it attacks both factions.
Ribbons are a few cheap emissive strips; in game they spin and their texture scrolls.

Run with Blender's Python (pip bpy):
  python crystal.py <atlas_dir> <out.glb> [render_dir]
Nodes: Base (ruined plinth with claws), Crystal (spins slowly), Core, Ribbons (spin faster), Shards (orbit).
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
TILES = {
    'facet': (0.0, 0.5, 0.5, 1.0),
    'core': (0.5, 0.5, 1.0, 1.0),
    'ribbon': (0.0, 0.0, 0.5, 0.5),
    'stone': (0.5, 0.0, 1.0, 0.5),
}


def make_mat(name, glass=False, emit_strength=1.0, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    b = t.nodes['Principled BSDF']
    base = t.nodes.new('ShaderNodeTexImage')
    base.image = bpy.data.images.load(f'{atlas_dir}/crystal_atlas.png')
    emi = t.nodes.new('ShaderNodeTexImage')
    emi.image = bpy.data.images.load(f'{atlas_dir}/crystal_emissive.png')
    t.links.new(base.outputs['Color'], b.inputs['Base Color'])
    t.links.new(emi.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = emit_strength
    b.inputs['Roughness'].default_value = 0.08 if glass else 0.8
    if glass:
        b.inputs['Transmission Weight'].default_value = 0.3
        b.inputs['IOR'].default_value = 1.6
    if alpha is not None:
        # Pure glow: dark base, emission does the work, brightness drives the alpha.
        b.inputs['Base Color'].default_value = (0, 0, 0, 1)
        t.links.remove(b.inputs['Base Color'].links[0])
        bw = t.nodes.new('ShaderNodeRGBToBW')
        t.links.new(emi.outputs['Color'], bw.inputs['Color'])
        t.links.new(bw.outputs['Val'], b.inputs['Alpha'])
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
    return m


glass = make_mat('CrystalGlass', glass=True, emit_strength=0.5)
glow = make_mat('CrystalGlow', emit_strength=10.0, alpha=True)
core_mat = make_mat('CrystalCore', emit_strength=30.0)
stone = make_mat('CrystalStone', emit_strength=2.0)


def fit_uv(obj, tile, margin=0.01, project=True):
    if project:
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


def mesh_from(name, verts, faces, tile, material, smooth=False, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if uvs is not None:
        layer = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                layer.data[li].uv = uvs[vi]
        fit_uv(obj, tile, project=False)
    else:
        fit_uv(obj, tile)
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    return obj


rng = random.Random(3)
FLOAT = 3.0   # gap between plinth and crystal tip
H = 14.0      # crystal height
R = 1.9       # widest radius
SIDES = 8

# --- Crystal: stacked rings, every other ring turned half a step, so the facets are triangles.
rings = [0.0, 0.1, 0.24, 0.4, 0.55, 0.7, 0.84, 1.0]
verts, faces = [], []
verts.append((0, 0, FLOAT))  # bottom tip
ring_idx = []
for k, t in enumerate(rings[1:-1]):
    r = R * math.sin(math.pi * t ** 0.85) ** 0.9 * rng.uniform(0.85, 1.1)
    off = (k % 2) * math.pi / SIDES
    row = []
    for i in range(SIDES):
        a = off + 2 * math.pi * i / SIDES
        rr = r * rng.uniform(0.8, 1.15)
        row.append(len(verts))
        verts.append((rr * math.cos(a), rr * math.sin(a), FLOAT + H * t + rng.uniform(-0.15, 0.15)))
    ring_idx.append(row)
top = len(verts)
verts.append((0, 0, FLOAT + H))
for i in range(SIDES):
    j = (i + 1) % SIDES
    faces.append([0, ring_idx[0][j], ring_idx[0][i]])
    faces.append([top, ring_idx[-1][i], ring_idx[-1][j]])
for a, b in zip(ring_idx, ring_idx[1:]):
    for i in range(SIDES):
        j = (i + 1) % SIDES
        faces.append([a[i], a[j], b[i]])
        faces.append([a[j], b[j], b[i]])
crystal = mesh_from('Crystal', verts, faces, 'facet', glass)


def spike(name, base_c, tip, w, sides, material, tile):
    """A jagged spike from a small base ring (around base_c) to a tip point."""
    import mathutils
    b, t = mathutils.Vector(base_c), mathutils.Vector(tip)
    axis = (t - b).normalized()
    side = axis.cross(mathutils.Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = mathutils.Vector((1, 0, 0))
    side.normalize()
    up = axis.cross(side)
    vs = [tuple(t)]
    for k in range(sides):
        a = 2 * math.pi * k / sides
        vs.append(tuple(b + (side * math.cos(a) + up * math.sin(a)) * w * rng.uniform(0.8, 1.2)))
    vs.append(tuple(b - axis * w * 0.6))
    fs = []
    for k in range(sides):
        j = (k + 1) % sides
        fs.append([0, 1 + k, 1 + j])
        fs.append([sides + 1, 1 + j, 1 + k])
    return mesh_from(name, vs, fs, tile, material)


# Orbiting shards: broken-off splinters that circle the crystal, points turned outward like blades.
shard_objs = []
for k in range(7):
    a = 2 * math.pi * k / 7 + rng.uniform(-0.2, 0.2)
    z = FLOAT + H * rng.uniform(0.25, 0.75)
    r0 = R + 1.6
    c = (r0 * math.cos(a), r0 * math.sin(a), z)
    tip = (c[0] + 1.6 * math.cos(a + 0.5), c[1] + 1.6 * math.sin(a + 0.5), z + rng.uniform(0.6, 1.4))
    shard_objs.append(spike(f'Shard{k}', c, tip, rng.uniform(0.22, 0.32), 4, glass, 'facet'))

# --- Core: a glowing orb at the crystal's heart (an icosphere, low).
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, FLOAT + H * 0.48))
me = bpy.data.meshes.new('Core'); bm.to_mesh(me); bm.free()
core = bpy.data.objects.new('Core', me); scene.collection.objects.link(core)
core.data.materials.append(core_mat); fit_uv(core, 'core')
for p in core.data.polygons:
    p.use_smooth = True

# --- Ribbons: three spiral strips around the crystal. U across the strip, V along it.
rverts, rfaces, ruvs = [], [], []
for s in range(3):
    seg = 48
    a0 = s * 2 * math.pi / 3
    tilt = rng.uniform(-0.35, 0.35)
    base_i = len(rverts)
    for i in range(seg + 1):
        t = i / seg
        a = a0 + t * 1.7 * math.pi
        z = FLOAT + H * (0.12 + 0.76 * t) + math.sin(a) * tilt * 2
        r = R * 1.25 + 0.9 * math.sin(math.pi * t)
        w = 0.5 * math.sin(math.pi * t) + 0.05
        cx, cy = r * math.cos(a), r * math.sin(a)
        rverts.append((cx, cy, z - w))
        rverts.append((cx, cy, z + w))
        ruvs += [(0.0, t), (1.0, t)]
    for i in range(seg):
        p = base_i + 2 * i
        rfaces.append([p, p + 2, p + 3, p + 1])
ribbons = mesh_from('Ribbons', rverts, rfaces, 'ribbon', glow, smooth=True, uvs=ruvs)

# --- Plinth: a cracked octagonal stone slab with broken pillar stumps.
pverts, pfaces = [], []
for z, r in ((0.0, 4.6), (0.6, 4.3), (0.6, 3.2), (1.0, 2.8)):
    for i in range(SIDES):
        a = 2 * math.pi * (i + 0.5) / SIDES
        pverts.append((r * math.cos(a), r * math.sin(a), z))
for ring in range(3):
    for i in range(SIDES):
        j = (i + 1) % SIDES
        a, b = ring * SIDES, (ring + 1) * SIDES
        pfaces.append([a + i, a + j, b + j, b + i])
pfaces.append(list(range(3 * SIDES, 4 * SIDES)))
plinth = [mesh_from('Slab', pverts, pfaces, 'stone', stone)]
# Claws: tall curved stone fangs rising from the plinth and leaning in toward the crystal.
for i in range(6):
    a = 2 * math.pi * (i + 0.25) / 6
    base_c = (3.9 * math.cos(a), 3.9 * math.sin(a), 0.6)
    tip = (2.6 * math.cos(a + 0.25), 2.6 * math.sin(a + 0.25), rng.uniform(4.0, 6.0))
    plinth.append(spike(f'Claw{i}', base_c, tip, 0.5, 5, stone, 'stone'))
for i in range(0, SIDES, 4):
    a = 2 * math.pi * (i + 0.5) / SIDES
    hgt = rng.uniform(0.8, 1.6)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=bm.verts, vec=(0.7, 0.7, hgt))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=__import__('mathutils').Matrix.Rotation(a + rng.uniform(-0.2, 0.2), 3, 'Z'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(3.9 * math.cos(a), 3.9 * math.sin(a), 0.6 + hgt / 2))
    me = bpy.data.meshes.new(f'Pillar{i}'); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(f'Pillar{i}', me); scene.collection.objects.link(o)
    o.data.materials.append(stone); fit_uv(o, 'stone')
    plinth.append(o)


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


base = join(plinth, 'Base')
shards = join(shard_objs, 'Shards')
root = bpy.data.objects.new('SuperCrystal', None)
scene.collection.objects.link(root)
for o in (base, crystal, core, ribbons, shards):
    o.parent = root

tris = 0
for o in (base, crystal, core, ribbons, shards):
    o.data.calc_loop_triangles()
    tris += len(o.data.loop_triangles)
print('TRIANGLES', tris)
assert tris <= 5000, tris

bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=True, export_yup=True)

if render_dir:
    world = bpy.data.worlds.new('W'); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.025, 0.015, 0.05, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 2.5
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    scene.collection.objects.link(sun)
    inner = bpy.data.objects.new('CoreLight', bpy.data.lights.new('CoreLight', 'POINT'))
    inner.data.energy = 6000; inner.data.color = (0.7, 0.4, 1.0)
    inner.location = (0, 0, FLOAT + H * 0.48)
    scene.collection.objects.link(inner)
    bpy.ops.mesh.primitive_plane_add(size=80)
    ground = bpy.context.object
    gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.12, 0.13, 0.1, 1)
    ground.data.materials.append(gm)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def look(name, loc, target=(0, 0, 8.0), lens_mm=40):
        cam.location = loc
        d = [t - l for t, l in zip(target, loc)]
        cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        cam.data.lens = lens_mm
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)

    look('crystal_front', (15, -15, 2.5), target=(0, 0, 8.0), lens_mm=26)
    look('crystal_rts', (16, -16, 30), target=(0, 0, 4), lens_mm=35)
