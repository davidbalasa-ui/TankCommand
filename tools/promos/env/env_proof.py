"""Close-up proof render of the clip environment: ground, scatter and rocks, no units.

    /home/user/artenv/venv/bin/python tools/promos/env/env_proof.py --kind desert --quality still \
        --frames 1,2 --out /tmp/envproof/desert

Frame 1 looks at the biggest rock group near the middle from 7 m; frame 2 is a low wide view
across the ground toward the horizon."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402
from promo_kit import Promo  # noqa: E402
import promo_env  # noqa: E402
import promo_kit  # noqa: E402

kind = 'desert'
if '--kind' in sys.argv:
    kind = sys.argv[sys.argv.index('--kind') + 1]
sun = {'desert': (48, 0, -40), 'highland': (46, 0, -55), 'alien': (55, 0, -40), 'dusk': (72, 0, 140),
       'ash': (35, 0, -150)}[kind]
P = Promo('env_' + kind, seconds=2 / 24)
P.env(kind, sun=sun, props=45, clear=[(0, 0, 5)], seed=7)
P.flatten(0, 0, 5)
# a provisional camera so the scatter/cover centre on the origin, then place props
P.camera([(0, (0, -10, 2), (0, 0, 0)), (1 / 24, (0, -10, 2), (0, 0, 0))])
promo_env.finalize(P)
best = None
for o in bpy.data.objects:
    if o.name.startswith('prop_') and o.parent is None and ('boulder' in o.name or 'rock_cluster' in o.name):
        p = o.location
        score = o.scale.x * 3 - p.length / 15
        if best is None or score > best[0]:
            best = (score, o)
o = best[1]
c = o.location.copy()
d = Vector((c.x, c.y, 0)).normalized() if c.length > 1 else Vector((1, 0, 0))
cam1 = c - d * (6 + 3 * o.scale.x) + Vector((0, 0, 1.6 + 0.4 * o.scale.x))
cam1.z = max(cam1.z, P.ground_z(cam1.x, cam1.y) + 1.4)
cam2 = Vector((0, -12, P.ground_z(0, -12) + 1.8))
cam = P.cam
tgt = P.cam_target
cam.animation_data_clear()
tgt.animation_data_clear()
for f, p, look in ((1, cam1, c + Vector((0, 0, 0.6 * o.scale.x))), (2, cam2, Vector((0, 40, 1.5)))):
    cam.location = p
    cam.keyframe_insert('location', frame=f)
    tgt.location = look
    tgt.keyframe_insert('location', frame=f)
for ob in (cam, tgt):
    for fc in promo_kit._fcurves(ob.animation_data.action):
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT'
P.render()
