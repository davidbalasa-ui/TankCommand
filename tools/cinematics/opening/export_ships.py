"""Save every current film ship as its own .blend (model + materials at the origin, nose along +X).
    python export_ships.py -- OUTDIR"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
out = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out, exist_ok=True)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def save(name):
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    p = os.path.join(out, name + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=p, compress=True, copy=True)
    print('SAVED', p, os.path.getsize(p), flush=True)


def terran(kind, fname):
    import v3base as V
    clear()
    ob, _ = V.terran_ship(kind)
    ob.location = (0, 0, 0)
    save(fname)


def arcadian(fn, fname):
    import arcadian_fleet as AF
    clear()
    with AF.gold_palette():
        ob, _ = getattr(AF, fn)()
    ob.location = (0, 0, 0)
    save(fname)


for kind, fname in [('dread', 'terran_dreadnought'), ('bship', 'terran_broadside_battleship'),
                    ('frigate', 'terran_frigate'), ('missile', 'terran_missile_ship'),
                    ('corvette', 'terran_corvette'), ('twinx', 'terran_twinx_fighter')]:
    terran(kind, fname)
for fn, fname in [('crescent_mothership_v2', 'arcadian_crescent_mothership'),
                  ('shell_mothership_v2', 'arcadian_shell_mothership'),
                  ('lens_mothership_v2', 'arcadian_lens_mothership'),
                  ('arcadian_corvette', 'arcadian_corvette'), ('stingray_fighter', 'arcadian_stingray_fighter')]:
    arcadian(fn, fname)
# the Orb: rigged, with a 7-second sample of its leg physics and lightning thrusters baked in
clear()
import orb_fighter as OF  # noqa: E402
from mathutils import Vector  # noqa: E402
import math  # noqa: E402
root, legs = OF.orb_rig('Orb')
sc = bpy.context.scene
sc.frame_start, sc.frame_end, sc.render.fps = 1, 168, 24
root.rotation_mode = 'QUATERNION'
prev = None
pts = {f: Vector((60 * f / 24, 14 * math.sin(f / 24 * 1.1), 10 * math.sin(f / 24 * 0.8 + 1))) for f in range(-4, 175)}
for f in range(-1, 171):
    root.location = pts[f]
    root.keyframe_insert('location', frame=f)
    q = (pts[f + 2] - pts[f - 2]).normalized().to_track_quat('X', 'Z')
    if prev is not None and q.dot(prev) < 0:
        q = -q
    root.rotation_quaternion = q
    root.keyframe_insert('rotation_quaternion', frame=f)
    prev = q
OF.animate_orb(root, legs, 1, 168, grabs=[dict(f_reach=118, f_grab=128, f_tear=146,
                                               hold=Vector((OF.X0 + 2.4, 0, 0)), legs=[0, 1, 3, 4, 6])], seed=5)
save('arcadian_orb_rigged_animated')
