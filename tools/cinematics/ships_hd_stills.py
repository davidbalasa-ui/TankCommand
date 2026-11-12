"""Still renders of the high-detail capital ships.

    python tools/cinematics/ships_hd_stills.py --ship=terran|kesh --out=DIR [--res=1600x900] [--samples=48]
          [--views=hero,side,top,close]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ships_hd as S  # noqa: E402
import forge as F  # noqa: E402

args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
SHIP = args.get('ship', 'terran')
OUT = args.get('out', '/tmp/ships')
RES = [int(v) for v in args.get('res', '1600x900').split('x')]
SAMPLES = int(args.get('samples', 48))
VIEWS = args.get('views', 'hero,side,top,close').split(',')
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
F.ST.update(parts=[], mats={}, group='Hull', seq=0)
if SHIP == 'terran':
    ship, _ = S.terran_dreadnought()
else:
    ship, _ = S.kesh_mothership()
tris = sum(len(p.vertices) - 2 for p in ship.data.polygons)
print(f'SHAPES {ship["shapes"]} TRIS {tris}', flush=True)
for p in ship.data.polygons:
    p.use_smooth = True

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = RES
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Punchy'
sc.view_settings.exposure = float(args.get('exposure', 1.2 if SHIP == 'terran' else 0.0))
w = bpy.data.worlds.new('Space')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.012, 0.014, 0.025, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 1.0


def light(name, rot, energy, col):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = energy
    ld.color = col
    ld.angle = math.radians(2)
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]


light('Key', (50, 10, 140), 9.0, (1.0, 0.95, 0.88))
light('Rim', (-60, 0, -40), 5.0, (0.55, 0.7, 1.0))
light('Fill', (120, 0, 60), 1.5, (0.6, 0.55, 0.7))

cam_d = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam_d.clip_end = 2000

size = max(ship.dimensions)
ctr = sum((ship.matrix_world @ Vector(b) for b in ship.bound_box), Vector()) / 8
VIEW = {
    'hero': (Vector((0.55, -0.85, 0.5)), 1.15, 40, ctr),
    'side': (Vector((0.0, -1.0, 0.12)), 1.25, 35, ctr),
    'top': (Vector((0.05, -0.35, 1.0)), 1.2, 35, ctr),
    'close': (Vector((0.9, -0.6, 0.35)), 0.42, 40, ctr + Vector((size * 0.12, -size * 0.1, size * 0.05))),
}
for v in VIEWS:
    d, dist, lens, tgt = VIEW[v]
    cam_d.lens = lens
    cam.location = tgt + d.normalized() * size * dist * (35 / lens) * (1.05 if SHIP == 'terran' else 1.5)
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, f'{SHIP}_{v}.png')
    bpy.ops.render.render(write_still=True)
    print('WROTE', sc.render.filepath, flush=True)
