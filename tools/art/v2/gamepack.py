"""Pack built Arcadian unit models for the game.

    python gamepack.py <models dir> [name ...]      (run after motion.apply, before lod.py)

The game plays recoil, missile launches and spins, and draws its own muzzle blasts from the
Flash* nodes, but it does not play 'flicker' lightning, so it would show both slots of every
lightning pair at once. Here:
- the second slot of each lightning pair (LiftB, ThrustB) is removed;
- every static mesh that hangs off the model root (LiftA, ThrustA, Ore, root-level parts with no
  motion of their own) joins the Hull, one mesh fewer per part.
Everything that moves (turret, barrels, pods, flashes, spinning parts) is left as built.
"""
import json
import os
import struct
import sys

import bpy

ALIEN = ['stinger', 'darter', 'glider', 'carapace', 'spitter', 'mortar_beast', 'gorger', 'ferrier', 'weaver', 'seer', 'disc']


def anim(o):
    a = o.get('anim')
    try:
        return a.to_dict() if hasattr(a, 'to_dict') else dict(a) if a else {}
    except (TypeError, ValueError):
        return {}


def chain(o):
    while o is not None:
        yield o
        o = o.parent


def pack(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = list(bpy.context.scene.objects)
    for o in [o for o in objs if o.name in ('LiftB', 'ThrustB')]:
        bpy.data.objects.remove(o, do_unlink=True)
    objs = list(bpy.context.scene.objects)
    hull = bpy.context.scene.objects.get('Hull')
    # Static: a mesh whose whole parent chain (up to the root empty) carries no motion and no turret.
    static = [o for o in objs if o.type == 'MESH' and o is not hull
              and all(anim(p).get('type') in (None, 'flicker') and p.name != 'TurretPivot' for p in chain(o) if p.parent is not None)]
    if hull is not None and static:
        bpy.ops.object.select_all(action='DESELECT')
        for m in static + [hull]:
            m.select_set(True)
        bpy.context.view_layer.objects.active = hull
        bpy.ops.object.join()
        if 'anim' in hull:
            del hull['anim']
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True, export_apply=True,
                              export_image_format='JPEG', export_jpeg_quality=88, export_animations=False,
                              export_extras=True)
    meshes = [o.name for o in bpy.context.scene.objects if o.type == 'MESH']
    dedupe_images(path)
    print('PACK', os.path.basename(path), meshes, os.path.getsize(path))


def dedupe_images(path):
    """Blender writes the see-through material's base colour (texture times alpha factor) as a new
    PNG; point it back at the shared base-colour JPEG (the alpha factor still applies) and drop it."""
    data = open(path, 'rb').read()
    jlen = struct.unpack('<I', data[12:16])[0]
    j = json.loads(data[20:20 + jlen])
    binc = data[20 + jlen + 8:]
    shared = {}
    for m in j['materials']:
        pbr = m.get('pbrMetallicRoughness', {})
        if 'baseColorTexture' in pbr and m.get('alphaMode') != 'BLEND':
            shared = j['textures'][pbr['baseColorTexture']['index']]['source']
    dropped = []
    for m in j['materials']:
        pbr = m.get('pbrMetallicRoughness', {})
        if m.get('alphaMode') == 'BLEND' and 'baseColorTexture' in pbr and shared != {}:
            tex = j['textures'][pbr['baseColorTexture']['index']]
            if tex['source'] != shared and j['images'][tex['source']].get('mimeType') == 'image/png':
                dropped.append(tex['source'])
                tex['source'] = shared
    if not dropped:
        return
    # Rebuild images and buffer without the dropped images' bytes.
    keep_img = [i for i in range(len(j['images'])) if i not in dropped]
    remap_img = {old: new for new, old in enumerate(keep_img)}
    dead_views = {j['images'][i]['bufferView'] for i in dropped}
    j['images'] = [j['images'][i] for i in keep_img]
    for t in j['textures']:
        t['source'] = remap_img[t['source']]
    views, remap_view, blob = [], {}, bytearray()
    for i, v in enumerate(j['bufferViews']):
        if i in dead_views:
            continue
        chunk = binc[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
        while len(blob) % 4:
            blob.append(0)
        v = dict(v, byteOffset=len(blob))
        blob += chunk
        remap_view[i] = len(views)
        views.append(v)
    j['bufferViews'] = views
    for a in j.get('accessors', []):
        if 'bufferView' in a:
            a['bufferView'] = remap_view[a['bufferView']]
    for im in j['images']:
        im['bufferView'] = remap_view[im['bufferView']]
    while len(blob) % 4:
        blob.append(0)
    j['buffers'][0]['byteLength'] = len(blob)
    js = json.dumps(j, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob))
    out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(blob), 0x004E4942) + bytes(blob)
    open(path, 'wb').write(out)


def main():
    root = sys.argv[1]
    for name in sys.argv[2:] or ALIEN:
        pack(os.path.join(root, 'alien', name + '.glb'))


if __name__ == '__main__':
    main()
