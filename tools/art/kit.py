"""Shared modelling kit for the faction asset sets (Blender Python, pip bpy).

One material per faction (base + emissive from the faction's 512px atlas). Every part's UVs are
squeezed into one atlas tile, so a whole unit is a single material and a handful of meshes.
Conventions (same as the first samples): front is +X, up is +Z in Blender; the glTF export turns
that into +X forward, +Y up. A rotating weapon sits under an empty called TurretPivot.

Usage from a set script:
    import kit
    kit.begin('terran', atlas_dir)
    hull = [kit.box(...), kit.prism(...)]
    kit.assemble('Outrider', {'Hull': hull}, turret=(tparts, (x, 0, z)))
    kit.finish(out_glb, budget=2500)
    kit.preview(render_dir, 'outrider')
"""
import math

import bpy
import bmesh
from mathutils import Vector

FACTIONS = {
    'terran': dict(
        atlas='terran_atlas.png', emissive='terran_emissive.png', metallic=0.55, roughness=0.5, emission=1.0,
        tiles={'hull': (0.0, 0.5, 0.5, 1.0), 'turret': (0.5, 0.5, 1.0, 1.0), 'track': (0.0, 0.25, 0.5, 0.5),
               'barrel': (0.5, 0.25, 1.0, 0.5), 'glow': (0.0, 0.0, 0.25, 0.25), 'amber': (0.25, 0.0, 0.5, 0.25),
               'dark': (0.5, 0.0, 1.0, 0.25)},
        world=(0.02, 0.025, 0.035), world_strength=0.6, rim=(1.0, 1.0, 1.0), ground=(0.09, 0.08, 0.07)),
    'kesh': dict(
        atlas='kesh_atlas.png', emissive='kesh_emissive.png', metallic=0.85, roughness=0.32, emission=2.5,
        tiles={'shell': (0.0, 0.5, 0.5, 1.0), 'fin': (0.5, 0.5, 1.0, 1.0), 'under': (0.0, 0.25, 0.5, 0.5),
               'barrel': (0.5, 0.25, 1.0, 0.5), 'glow': (0.0, 0.0, 0.25, 0.25), 'core': (0.25, 0.0, 0.5, 0.25),
               'dark': (0.5, 0.0, 0.75, 0.25)},
        world=(0.06, 0.04, 0.09), world_strength=0.8, rim=(0.75, 0.6, 1.0), ground=(0.08, 0.07, 0.09)),
}

S = {}  # current scene state: scene, mat, tiles, faction, nodes


def begin(faction, atlas_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    f = FACTIONS[faction]
    mat = bpy.data.materials.new(f'{faction}Atlas')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    base = nt.nodes.new('ShaderNodeTexImage'); base.image = bpy.data.images.load(f"{atlas_dir}/{f['atlas']}")
    emi = nt.nodes.new('ShaderNodeTexImage'); emi.image = bpy.data.images.load(f"{atlas_dir}/{f['emissive']}")
    nt.links.new(base.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(emi.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = f['emission']
    bsdf.inputs['Metallic'].default_value = f['metallic']
    bsdf.inputs['Roughness'].default_value = f['roughness']
    S.clear()
    S.update(scene=bpy.context.scene, mat=mat, tiles=f['tiles'], faction=faction, cfg=f, nodes=[])


def _fit_uv(obj, tile, margin=0.01):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    u0, v0, u1, v1 = S['tiles'][tile]
    u0 += margin; v0 += margin; u1 -= margin; v1 -= margin
    for loop in obj.data.uv_layers.active.data:
        u, v = loop.uv
        loop.uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def _link(name, me, tile, smooth):
    obj = bpy.data.objects.new(name, me)
    S['scene'].collection.objects.link(obj)
    obj.data.materials.append(S['mat'])
    _fit_uv(obj, tile)
    for p in obj.data.polygons:
        p.use_smooth = smooth
    return obj


def mesh_from(name, verts, faces, tile, bevel=0.0, smooth=False, merge=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    if bevel > 0 or merge:
        bm = bmesh.new(); bm.from_mesh(me)
        if merge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        if bevel > 0:  # chamfer every edge once: kills the boxy look for a few triangles
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect='EDGES', profile=0.5)
        bm.to_mesh(me); bm.free()
    return _link(name, me, tile, smooth)


def prism(name, profile, y0, y1, tile, bevel=0.0, taper=1.0, smooth=False):
    """Extrude a side profile [(x, z)...] (counter-clockwise seen from -Y) between y0 and y1.
    taper < 1 pulls the upper part of the sides inward (sloped armour)."""
    n = len(profile)
    zs = [z for _, z in profile]
    zlo, zhi = min(zs), max(zs)
    yc = (y0 + y1) / 2

    def ty(y, z):
        k = 1 - (1 - taper) * max(0.0, (z - zlo) / (zhi - zlo + 1e-9))
        return yc + (y - yc) * k
    verts = [(x, ty(y0, z), z) for x, z in profile] + [(x, ty(y1, z), z) for x, z in profile]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return mesh_from(name, verts, faces, tile, bevel, smooth)


def prism_y(name, profile, x0, x1, tile, bevel=0.0):
    """Extrude a front profile [(y, z)...] between x0 and x1 (for wings seen from the front etc.)."""
    n = len(profile)
    verts = [(x0, y, z) for y, z in profile] + [(x1, y, z) for y, z in profile]
    faces = [list(range(n)), list(range(n, 2 * n))[::-1]]
    for i in range(n):
        j = (i + 1) % n
        faces.append([j, i, n + i, n + j])
    return mesh_from(name, verts, faces, tile, bevel)


def plate(name, outline, z0, z1, tile, bevel=0.0, smooth=False):
    """Extrude a top-down outline [(x, y)...] (counter-clockwise from above) from z0 up to z1: wings, pads."""
    n = len(outline)
    verts = [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return mesh_from(name, verts, faces, tile, bevel, smooth)


def box(name, c, s, tile, bevel=0.0, taper=1.0):
    (cx, cy, cz), (sx, sy, sz) = c, s
    prof = [(cx - sx, cz - sz), (cx + sx, cz - sz), (cx + sx, cz + sz), (cx - sx, cz + sz)]
    return prism(name, prof, cy - sy, cy + sy, tile, bevel, taper)


def cyl(name, p0, p1, r, sides, tile, r1=None, caps=True, smooth=False):
    """Cylinder or cone from point p0 (radius r) to p1 (radius r1)."""
    a, b = Vector(p0), Vector(p1)
    d = b - a
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=sides, radius1=r, radius2=r if r1 is None else r1,
                          depth=d.length)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    obj = _link(name, me, tile, smooth)
    obj.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    obj.location = (a + b) / 2
    _apply(obj)
    return obj


def orb(name, c, r, tile, seg=(10, 6), scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=r)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2])) + Vector(c)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    return _link(name, me, tile, True)


def lathe(name, profile, sides, tile, center=(0, 0, 0), smooth=True, top=None, bottom=None, scale=(1, 1)):
    """Revolve [(r, z)...] around the vertical axis through center. Optional point caps."""
    cx, cy, cz = center
    verts, faces = [], []
    n = len(profile)
    for r, z in profile:
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append((cx + r * math.cos(a) * scale[0], cy + r * math.sin(a) * scale[1], cz + z))
    for i in range(n - 1):
        for k in range(sides):
            j = (k + 1) % sides
            faces.append([i * sides + k, i * sides + j, (i + 1) * sides + j, (i + 1) * sides + k])
    if top is not None:
        t = len(verts); verts.append((cx, cy, cz + top)); last = (n - 1) * sides
        faces += [[last + k, last + (k + 1) % sides, t] for k in range(sides)]
    if bottom is not None:
        b = len(verts); verts.append((cx, cy, cz + bottom))
        faces += [[(k + 1) % sides, k, b] for k in range(sides)]
    return mesh_from(name, verts, faces, tile, smooth=smooth)


def loft(name, sections, ring, tile, smooth=True, cy=0.0):
    """Lens-like body along X. sections: [(x, half_width, z_top, z_bottom, z_mid)]; ends may have width 0."""
    verts, faces, rows = [], [], []
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
    return mesh_from(name, verts, faces, tile, smooth=smooth, merge=True)


def lens(x0, x1, w, zt, zb, zm, n=9, nose=0.55):
    """Sections for a pointed lens, widest a bit forward of centre."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        k = math.sin(math.pi * t ** nose) if 0 < t < 1 else 0.0
        out.append((x0 + (x1 - x0) * t, w * k, zm + (zt - zm) * k, zm - (zm - zb) * k, zm))
    return out


def _apply(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.select_set(False)


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name; o.data.name = name
    return o


def assemble(name, body, pivots=None):
    """body: list of parts joined into 'Hull'. pivots: {pivot_name: (parts, (x, y, z), mesh_name, parent)}
    where parent is None (root) or another pivot name. Returns the root empty."""
    root = bpy.data.objects.new(name, None)
    S['scene'].collection.objects.link(root)
    meshes = [join(body, 'Hull')]
    meshes[0].parent = root
    empties = {}
    for pname, (parts, loc, mname, parent) in (pivots or {}).items():
        e = bpy.data.objects.new(pname, None)
        S['scene'].collection.objects.link(e)
        par = empties[parent] if parent else root
        e.parent = par
        world = Vector(loc)
        pw = Vector((0, 0, 0))
        p = parent
        while p:
            pw += Vector(pivots[p][1]); p = pivots[p][3]
        e.location = world - pw
        m = join(parts, mname)
        m.parent = e
        m.location = -world
        empties[pname] = e
        meshes.append(m)
    S['root'], S['meshes'], S['empties'] = root, meshes, empties
    return root


def tris():
    n = 0
    for o in S['meshes']:
        o.data.calc_loop_triangles()
        n += len(o.data.loop_triangles)
    return n


def finish(out_glb, budget):
    n = tris()
    print('TRIANGLES', S['root'].name, n)
    assert n <= budget, (S['root'].name, n, budget)
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=True, export_yup=True)
    return n


def stage(ground=True):
    """Lights, world and ground for previews (not exported)."""
    cfg = S['cfg']
    sc = S['scene']
    world = bpy.data.worlds.new('W'); sc.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (*cfg['world'], 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = cfg['world_strength']
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 3.4
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    sc.collection.objects.link(sun)
    rim = bpy.data.objects.new('Rim', bpy.data.lights.new('Rim', 'AREA'))
    rim.data.energy = 650; rim.data.size = 6; rim.location = (-6, 6, 5); rim.data.color = cfg['rim']
    rim.rotation_euler = (math.radians(60), 0, math.radians(-135))
    sc.collection.objects.link(rim)
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=200)
        g = bpy.context.object
        gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
        gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*cfg['ground'], 1)
        g.data.materials.append(gm)
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    S['cam'] = cam


def bounds():
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in S['meshes']:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


def preview(render_dir, name, samples=32, res=(900, 560), views=('front34', 'rts'), turret_yaw=-12, lift=0.0):
    """Renders standard views framed to the model's size: <name>_front34.png, <name>_rts.png, <name>_side.png."""
    bpy.context.view_layer.update()
    if 'TurretPivot' in S.get('empties', {}):
        S['empties']['TurretPivot'].rotation_euler = (0, 0, math.radians(turret_yaw))
    if lift:
        S['root'].location.z += lift
    bpy.context.view_layer.update()
    stage()
    sc, cam = S['scene'], S['cam']
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = res
    lo, hi = bounds()
    c = (lo + hi) / 2
    size = max(hi.x - lo.x, hi.y - lo.y, (hi.z - lo.z) * 1.4)
    out = []
    for v in views:
        if v == 'front34':
            d = Vector((1.0, -0.82, 0.5)).normalized() * size * 1.75
            lens_mm = 50
        elif v == 'side':
            d = Vector((0.03, -1.0, 0.18)).normalized() * size * 2.1
            lens_mm = 50
        else:  # rts: the in-game camera angle
            d = Vector((0.75, -0.75, 1.3)).normalized() * size * 2.0
            lens_mm = 40
        cam.location = c + d
        dd = c - cam.location
        cam.rotation_euler = (math.atan2(math.hypot(dd.x, dd.y), -dd.z), 0, math.atan2(dd.y, dd.x) - math.pi / 2)
        cam.data.lens = lens_mm
        sc.render.filepath = f'{render_dir}/{name}_{v}.png'
        bpy.ops.render.render(write_still=True)
        out.append(sc.render.filepath)
    return out
