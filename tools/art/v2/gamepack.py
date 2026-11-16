"""Pack built Arcadian unit models for the game: fewer meshes, so fewer draw calls per unit type.

    python gamepack.py <models dir> [name ...]      (run after motion.apply, before lod.py)

The art models keep every moving part separate for the viewer (recoil, muzzle flashes, missile
launches, two-slot lightning). The game plays none of the firing motion yet and draws each mesh of
a unit type as one instanced call, so here:
- muzzle flashes (anim 'flash') are removed: the game draws its own;
- the second slot of each lightning pair (LiftB, ThrustB) is removed; the first (LiftA, ThrustA)
  joins the hull as a still bolt (a flickering part would cost two more draw calls per unit type);
- every other mesh joins the mesh of its nearest moving anchor: the hull, an aimed turret
  (TurretPivot) or a spinning part (spin/swing pivots), one mesh per anchor.
Node names the game looks up (TurretPivot, spin pivots) are kept.
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
    doomed = [o for o in objs if o.name in ('LiftB', 'ThrustB') or any(anim(p).get('type') == 'flash' for p in chain(o))]
    for o in doomed:
        bpy.data.objects.remove(o, do_unlink=True)
    objs = list(bpy.context.scene.objects)
    roots = [o for o in objs if o.parent is None]
    anchors = set(o.name for o in objs if o.name == 'TurretPivot' or anim(o).get('type') in ('spin', 'swing'))
    groups = {}
    for o in objs:
        if o.type != 'MESH':
            continue
        anchor = next((p for p in chain(o.parent) if p.name in anchors), None)
        groups.setdefault(anchor.name if anchor else '', []).append(o)
    for key, meshes in groups.items():
        if len(meshes) < 2:
            continue
        # Keep the anchor's own direct child mesh (Hull, Turret, Eye ...) as the target.
        meshes.sort(key=lambda m: (0 if m.name == 'Hull' else 1, len(list(chain(m))), m.name))
        target = meshes[0]
        bpy.ops.object.select_all(action='DESELECT')
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.join()
    # Pivots left with nothing under them (recoil and launch pivots) go too.
    for o in list(bpy.context.scene.objects):
        if o.type == 'EMPTY' and not o.children and o.name not in anchors and o.parent is not None:
            bpy.data.objects.remove(o, do_unlink=True)
    del roots
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
