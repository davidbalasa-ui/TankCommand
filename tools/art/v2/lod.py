"""Make low-detail versions of the unit models.

    python lod.py <models dir> [name ...]

Writes <name>_lod.glb next to each unit model: same node names, pivots and UVs, geometry reduced
to about 2,500 triangles (5,000 for the big units). The files carry no textures; the game puts
the full model's material on them.
"""
import glob
import json
import os
import sys

import bpy

BIG = {'bulwark', 'longbow', 'carapace', 'mortar_beast', 'condor'}


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


def main():
    root = sys.argv[1]
    names = sys.argv[2:]
    paths = sorted(glob.glob(os.path.join(root, 'human', '*.glb')) + glob.glob(os.path.join(root, 'alien', '*.glb')))
    for p in paths:
        n = os.path.basename(p)[:-4]
        if n.endswith('_lod') or n == 'poc_tank' or (names and n not in names):
            continue
        print('LOD', json.dumps(make(p, 5000 if n in BIG else 2500)))


if __name__ == '__main__':
    main()
