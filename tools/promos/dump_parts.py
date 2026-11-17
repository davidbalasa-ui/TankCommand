"""Dump node names, sizes and anim tags of every model file given: python dump_parts.py out.json file..."""
import bpy, sys, json, mathutils
out, files = sys.argv[1], sys.argv[2:]
res = {}
def plain(v):
    try: return v.to_dict()
    except Exception:
        try: return list(v)
        except Exception: return v
for f in files:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        if f.endswith('.glb'): bpy.ops.import_scene.gltf(filepath=f)
        else:
            with bpy.data.libraries.load(f) as (src, dst): dst.objects = src.objects
            for o in dst.objects:
                if o: bpy.context.scene.collection.objects.link(o)
    except Exception as e:
        res[f] = {'error': str(e)}; continue
    bpy.context.view_layer.update()
    lo = mathutils.Vector((1e9,)*3); hi = -lo; tris = 0; nodes = []
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for c in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(c)
                lo = mathutils.Vector(map(min, lo, w)); hi = mathutils.Vector(map(max, hi, w))
            tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
        ex = {k: plain(o[k]) for k in o.keys() if k not in ('_RNA_UI',)}
        nodes.append(dict(name=o.name, type=o.type, parent=o.parent.name if o.parent else None, extras=ex,
                          loc=[round(v, 3) for v in o.matrix_world.translation]))
    sc = {k: plain(bpy.context.scene[k]) for k in bpy.context.scene.keys()}
    res[f] = dict(lo=[round(v, 3) for v in lo], hi=[round(v, 3) for v in hi], tris=tris, nodes=nodes, scene=sc,
                  actions=[a.name for a in bpy.data.actions], armatures=[a.name for a in bpy.data.armatures])
json.dump(res, open(out, 'w'), indent=1, default=str)
