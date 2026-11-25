"""Hero + side + top stills of one Arcadian design option.
    python tools/cinematics/design_stills.py --design=A|B|C --out=DIR [--samples=32]
"""
import math, os, sys
import bpy
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arcadian_designs as D  # noqa
import forge as F  # noqa
args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
OUT = args.get('out', '/tmp/designs'); os.makedirs(OUT, exist_ok=True)
key = args.get('design', 'A')
bpy.ops.wm.read_factory_settings(use_empty=True)
F.ST.update(parts=[], mats={}, group='Hull', seq=0)
ship, core = D.DESIGNS[key]()
tris = sum(len(p.vertices) - 2 for p in ship.data.polygons)
print(f'DESIGN {key} SHAPES {ship["shapes"]} TRIS {tris} DIMS {tuple(round(d,1) for d in ship.dimensions)}', flush=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(args.get('samples', 32)); sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Punchy'
w = bpy.data.worlds.new('Space'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.012, 0.014, 0.025, 1)
def light(n, rot, e, col):
    ld = bpy.data.lights.new(n, 'SUN'); ld.energy = e; ld.color = col; ld.angle = math.radians(2)
    o = bpy.data.objects.new(n, ld); sc.collection.objects.link(o); o.rotation_euler = [math.radians(a) for a in rot]
light('Key', (50, 10, 140), 6.0, (1.0, 0.95, 0.88)); light('Rim', (-60, 0, -40), 4.0, (0.55, 0.7, 1.0))
light('Fill', (120, 0, 60), 1.2, (0.6, 0.55, 0.7))
ld = bpy.data.lights.new('CamKey', 'SUN'); ld.energy = 3.0; ld.color = (1.0, 0.93, 0.85)
cl = bpy.data.objects.new('CamKey', ld); sc.collection.objects.link(cl)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.clip_end = 2000; cam.data.lens = 40
size = max(ship.dimensions)
ctr = sum((ship.matrix_world @ Vector(b) for b in ship.bound_box), Vector()) / 8
DK = float(args.get('dist', 1.0))
for v, d, k in [('hero', Vector((0.6, -0.8, 0.45)), 1.6 * DK), ('side', Vector((0.05, -1, 0.08)), 1.5 * DK), ('top', Vector((-0.3, -0.25, 1)), 1.5 * DK)]:
    p = ctr + d.normalized() * size * k
    cam.location = p; cam.rotation_euler = (ctr - p).to_track_quat('-Z', 'Y').to_euler()
    cl.rotation_euler = cam.rotation_euler.copy(); cl.rotation_euler[0] -= 0.5
    sc.render.filepath = os.path.join(OUT, f'{key}_{v}.png'); bpy.ops.render.render(write_still=True)
