"""Save each v3 scene as a self-contained .blend: all objects and baked animation, one camera per shot,
timeline markers switching cameras at each cut, final render settings.
    python export_blend.py -- s01,s02,... OUTDIR"""
import importlib
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import film_v3  # noqa: E402
import v3base  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
scenes, out = args[0].split(','), args[1]
os.makedirs(out, exist_ok=True)
for scene in scenes:
    mod = importlib.import_module('v3_' + scene)
    S = mod.build(draft=False)
    film_v3.render_settings(film_v3.QUALITY['final'])
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, S.nf
    sc.render.fps = film_v3.FPS
    if getattr(S, 'tmap', None):
        print('SKIP (time-mapped scene, not exportable as-is)', scene)
        continue
    sc.timeline_markers.clear()
    for sid, f0, f1, keys, shake in S.shots:
        cam = v3base.build_camera(keys, shake)
        cam.name = cam.data.name = f'Cam_{scene}_{sid}'
        m = sc.timeline_markers.new(f'shot {sid}', frame=f0)
        m.camera = cam
    sc.frame_set(1)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:  # noqa: BLE001
        print('pack', e)
    p = os.path.join(out, f'opening_v3_{scene}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
    print('SAVED', p, os.path.getsize(p))
