"""Make low-detail versions of the unit models and the scenery props.

    python lod.py <models dir> [name ...]
    python lod.py <models dir> --props [name ...]

Writes <name>_lod.glb next to each unit model: same node names, pivots and UVs, geometry reduced
to about 2,500 triangles (5,000 for the big units). The files carry no textures; the game puts
the full model's material on them.
"""
import glob
import json
import os
import sys

import bpy

BIG = {'bulwark', 'longbow', 'carapace', 'mortar_beast', 'condor', 'metal_station_packed', 'air_base_packed'}


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def make(path, target):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    total = sum(tris(o) for o in meshes)
    ratio = min(1.0, target / total)
    for o in meshes:
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new('lod', 'DECIMATE')
        m.ratio = ratio
        m.delimit = {'UV'}
        bpy.ops.object.modifier_apply(modifier=m.name)
    after = sum(tris(o) for o in meshes)
    out = path[:-4] + '_lod.glb'
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True, export_animations=False,
                              export_materials='PLACEHOLDER')
    return dict(file=os.path.basename(out), before=total, triangles=after, bytes=os.path.getsize(out))


# Scenery props: triangle budget for the low-detail version. The game draws these far from the
# camera and on the lower quality levels with the full model's material (same UVs), so the baked
# normal map still carries the surface detail.
PROP_LOD = {
    'cliff': 1700, 'boulder': 700, 'rock_cluster': 800, 'slab': 560, 'dead_tree': 380,
    'tendril': 700, 'shrub': 560, 'grass': 320, 'deposit_ore': 2000, 'deposit_metal': 2000,
}


def make_prop(path, target):
    """Decimate a prop, keeping UVs, mesh names, pivots and material names (deposits keep OreGem);
    materials are written bare (the game uses the full model's)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    total = sum(tris(o) for o in meshes)
    ratio = min(1.0, target / total)
    for o in meshes:
        # Keep the full mesh's shading normals: the baked normal map was made against them, so the
        # low-detail mesh copies them from the original (nearest face, interpolated).
        src = o.copy()
        src.data = o.data.copy()
        bpy.context.scene.collection.objects.link(src)
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new('lod', 'DECIMATE')
        m.ratio = ratio
        m.delimit = {'UV', 'MATERIAL'}
        bpy.ops.object.modifier_apply(modifier=m.name)
        t = o.modifiers.new('normals', 'DATA_TRANSFER')
        t.object = src
        t.use_loop_data = True
        t.data_types_loops = {'CUSTOM_NORMAL'}
        t.loop_mapping = 'POLYINTERP_NEAREST'
        bpy.ops.object.modifier_apply(modifier=t.name)
        bpy.data.objects.remove(src, do_unlink=True)
    for mat in bpy.data.materials:
        mat.use_nodes = True
        nt = mat.node_tree
        for node in list(nt.nodes):
            if node.type == 'TEX_IMAGE':
                nt.nodes.remove(node)
    after = sum(tris(o) for o in meshes)
    out = path[:-4] + '_lod.glb'
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True, export_animations=False,
                              export_materials='EXPORT', export_image_format='NONE')
    return dict(file=os.path.basename(out), before=total, triangles=after, bytes=os.path.getsize(out))


def main():
    root = sys.argv[1]
    names = sys.argv[2:]
    if names and names[0] == '--props':
        names = names[1:]
        for n, target in PROP_LOD.items():
            if names and n not in names:
                continue
            print('LOD', json.dumps(make_prop(os.path.join(root, 'props', n + '.glb'), target)))
        return
    paths = sorted(glob.glob(os.path.join(root, 'human', '*.glb')) + glob.glob(os.path.join(root, 'alien', '*.glb')))
    for p in paths:
        n = os.path.basename(p)[:-4]
        if n.endswith('_lod') or n == 'poc_tank' or (names and n not in names):
            continue
        print('LOD', json.dumps(make(p, 5000 if n in BIG else 2500)))


if __name__ == '__main__':
    main()
