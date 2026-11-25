"""Design sheets of the Terran cinematic fleet (tools/cinematics/terran_fleet.py).

    python tools/cinematics/terran_fleet_stills.py --ship=NAME --out=DIR [--samples=32] [--views=hero,side,top]
          [--tmp=DIR] [--exposure=1.3]

NAME: battleship | corvette | frigate | fighter | missile_ship | all
Writes one sheet JPG per ship into DIR (hero view large, side + top small). The battleship also
gets NN-broadside-battleship-firing.jpg (--views=fire for that shot only).
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Vector
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import terran_fleet as T  # noqa: E402
import forge as F  # noqa: E402

args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
OUT = args.get('out', '/tmp/terran_fleet')
TMP = args.get('tmp', os.path.join(OUT, '_raw'))
SAMPLES = int(args.get('samples', 40))
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

SHEETS = {
    'battleship': ('01-broadside-battleship', 'Terran broadside battleship'),
    'corvette': ('02-corvette', 'Terran corvette'),
    'frigate': ('03-frigate', 'Terran frigate'),
    'fighter': ('04-twin-x-fighter', 'Terran twin-X fighter'),
    'missile_ship': ('05-missile-ship', 'Terran missile ship'),
}
VIEWS = {   # direction to the camera, lens
    'hero': (Vector((0.62, -0.8, 0.42)), 40),
    'side': (Vector((0.0, -1.0, 0.1)), 50),
    'top': (Vector((0.0, -0.02, 1.0)), 50),
}
HERO = {'fighter': Vector((0.8, -0.5, 0.33)), 'missile_ship': Vector((0.8, -0.62, 0.36)),
        'battleship': Vector((0.5, -0.85, 0.5))}


def tris_of(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def setup(exposure):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    F.ST.update(parts=[], mats={}, group='Hull', seq=0)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = int(args.get('threads', 3))
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = exposure
    w = bpy.data.worlds.new('Space')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    bg.inputs[0].default_value = (0.012, 0.014, 0.025, 1)
    if args.get('stars', '1') == '1':                      # sparse procedural star field
        tc = nt.nodes.new('ShaderNodeTexCoord')
        vo = nt.nodes.new('ShaderNodeTexVoronoi')
        vo.inputs['Scale'].default_value = 140.0
        nt.links.new(tc.outputs['Generated'], vo.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = 0.0
        mr.inputs['From Max'].default_value = 0.045
        mr.inputs['To Min'].default_value = 1.0
        mr.inputs['To Max'].default_value = 0.0
        nt.links.new(vo.outputs['Distance'], mr.inputs['Value'])
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(vo.outputs['Color'], sep.inputs[0])
        gt = nt.nodes.new('ShaderNodeMath')
        gt.operation = 'GREATER_THAN'
        gt.inputs[1].default_value = 0.55
        nt.links.new(sep.outputs[0], gt.inputs[0])
        mu = nt.nodes.new('ShaderNodeMath')
        mu.operation = 'MULTIPLY'
        nt.links.new(mr.outputs[0], mu.inputs[0])
        nt.links.new(gt.outputs[0], mu.inputs[1])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.inputs[6].default_value = (0.012, 0.014, 0.025, 1)
        mx.inputs[7].default_value = (0.5, 0.55, 0.7, 1)
        nt.links.new(mu.outputs[0], mx.inputs[0])
        nt.links.new(mx.outputs[2], bg.inputs[0])

    def sun(name, rot, energy, col):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.color = col
        ld.angle = math.radians(2)
        o = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(o)
        o.rotation_euler = [math.radians(a) for a in rot]
        return o

    sun('Key', (50, 10, 140), 8.0, (1.0, 0.95, 0.88))
    sun('Rim', (-60, 0, -40), 6.0, (0.55, 0.7, 1.0))
    sun('Fill', (120, 0, 60), 1.5, (0.6, 0.55, 0.7))
    camkey = sun('CamKey', (0, 0, 0), 3.0, (1.0, 0.93, 0.85))
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.02
    cam.data.clip_end = 5000
    return sc, cam, camkey


def aim(sc, cam, camkey, objs, d, lens, margin=1.08, target=None):
    """Point the camera along -d at the objects and back off until they just fit the frame."""
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(b) for o in objs for b in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr = target or (lo + hi) / 2
    d = d.normalized()
    q = (-d).to_track_quat('-Z', 'Y')
    right, up = q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0))
    cam.data.lens = lens
    th = cam.data.sensor_width / 2 / lens
    tv = th * sc.render.resolution_y / sc.render.resolution_x
    D = 0.0
    for p in pts:
        v = p - ctr
        D = max(D, abs(v.dot(right)) * margin / th + v.dot(d), abs(v.dot(up)) * margin / tv + v.dot(d))
    cam.location = ctr + d * D
    cam.rotation_euler = q.to_euler()
    camkey.rotation_euler = cam.rotation_euler.copy()
    camkey.rotation_euler[0] -= 0.45
    camkey.rotation_euler[2] += 0.35


def bloom(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255.0
    lum = a.max(axis=2, keepdims=True)
    b = Image.fromarray((np.clip((lum - 0.72) / 0.28, 0, 1) * a * 255).astype(np.uint8))
    k = a.shape[1] / 1280.0
    glow = np.zeros_like(a)
    for r, w in [(4, 0.45), (12, 0.35), (32, 0.3)]:
        glow += np.asarray(b.filter(ImageFilter.GaussianBlur(r * k))).astype(np.float32) / 255.0 * w
    return Image.fromarray((np.clip(1 - (1 - a) * (1 - np.clip(glow, 0, 1)), 0, 1) * 255).astype(np.uint8))


def render(sc, name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(TMP, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('WROTE', sc.render.filepath, flush=True)
    return sc.render.filepath


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12 + 7 * len(text), 22], fill=(0, 0, 0))
    d.text((6, 5), text, fill=(235, 235, 235))
    return im


def build(key):
    """Returns (ship, extra objects to frame, all triangles)."""
    extra = []
    if key == 'battleship':
        ship, _ = T.broadside_battleship()
    elif key == 'fighter':
        ship, wname = T.twin_x_fighter()
        extra += [bpy.data.objects[wname]] + list(ship.children_recursive)
        extra = list(dict.fromkeys(extra))
    elif key == 'missile_ship':
        ship, tubes = T.missile_ship()
        # a stream leaving both tubes: one still half inside, the rest downrange
        for i, (tube, dx) in enumerate([(0, -1.2), (1, 3.5), (0, 9.5), (1, 16.0), (0, 24.0), (1, 33.0)]):
            ms = T.missile(f'Missile{i}', plume=dx > 2)
            ms.location = tubes[tube] + Vector((dx, (0.25 if tube == 0 else -0.25) * max(dx, 0) * 0.06, max(dx, 0) * 0.012))
            if dx < 12:
                extra.append(ms)
    else:
        ship = T.BUILDERS[key]()
    for p in ship.data.polygons:
        p.use_smooth = True
    if key != 'fighter' and args.get('neon', '1') != '0':
        T.neon_lines(ship)
    tris = tris_of(ship) + sum(tris_of(o) for o in extra if key == 'fighter')
    return ship, extra, tris


def sheet(key):
    fname, title = SHEETS[key]
    sc, cam, camkey = setup(float(args.get('exposure', 1.3)))
    ship, extra, tris = build(key)
    dims = tuple(round(v, 1) for v in ship.dimensions)
    if key == 'fighter':                # the core alone is short; measure core + wings + guns
        xs = [(o.matrix_world @ Vector(b)).x for o in [ship] + extra for b in o.bound_box]
        dims = (round(max(xs) - min(xs), 1),) + dims[1:]
    print(f'SHIP {key} SHAPES {ship["shapes"]} TRIS {tris} DIMS {dims}', flush=True)
    views = args.get('views', 'hero,side,top' + (',fire' if key == 'battleship' else '')).split(',')
    ims = {}
    for v in ('hero', 'side', 'top'):
        if v not in views:
            continue
        d, lens = VIEWS[v]
        if v == 'hero':
            d = HERO.get(key, d)
        aim(sc, cam, camkey, [ship] + extra, d, lens, margin=0.84 if v == 'hero' else 1.1)
        ims[v] = bloom(render(sc, f'{key}_{v}', (1280, 720) if v == 'hero' else (640, 360)))
    if len(ims) == 3:
        rows = []
        if key == 'fighter':            # extra row: front view, and the wings caught mid-spin
            wings = bpy.data.objects[ship['wings']]
            fit = [ship, wings]
            aim(sc, cam, camkey, fit, Vector((1.0, -0.12, 0.1)), 50, margin=1.1)
            rows.append(label(bloom(render(sc, 'fighter_front', (640, 360))), 'front'))
            wings.rotation_mode = 'XYZ'
            for fr, ang in ((0, -22.0), (2, 22.0)):
                wings.rotation_euler = (math.radians(ang), 0, 0)
                wings.keyframe_insert('rotation_euler', frame=fr)
            for o in [wings] + list(wings.children):
                o.cycles.motion_steps = 5
            sc.render.use_motion_blur = True
            sc.render.motion_blur_shutter = 0.9
            sc.frame_set(1)
            rows.append(label(bloom(render(sc, 'fighter_spin_front', (640, 360))), 'front, mid-spin (motion blur)'))
            aim(sc, cam, camkey, fit, HERO[key], 40, margin=0.95)
            rows.append(label(bloom(render(sc, 'fighter_spin', (640, 360))), 'mid-spin (motion blur)'))
            sc.render.use_motion_blur = False
        out = Image.new('RGB', (1920, 720 + (360 if rows else 0)))
        for i, im in enumerate(rows):
            out.paste(im, (i * 640, 720))
        out.paste(ims['hero'], (0, 0))
        out.paste(label(ims['side'], 'side'), (1280, 0))
        out.paste(label(ims['top'], 'top'), (1280, 360))
        label(out, f'{title}  -  {tris:,} triangles  -  {dims[0]:g} long')
        out.save(os.path.join(OUT, fname + '.jpg'), quality=90)
        print('SHEET', os.path.join(OUT, fname + '.jpg'), flush=True)
    if 'fire' in views and key == 'battleship':
        fire(sc, cam, camkey, ship, os.path.join(OUT, fname + '-firing.jpg'))


def fire(sc, cam, camkey, ship, out):
    """The battleship rolled gun-side down, mid salvo: bow gun has fired (slug far downrange),
    middle gun is firing, aft gun is charging."""
    ship.rotation_euler = Euler((math.radians(38), math.radians(-6), math.radians(8)), 'XYZ')
    stages = [dict(scale=0.47, bolt_at=20.0, strength=30.0), dict(scale=0.78, bolt_at=6.0, strength=45.0),
              dict(charge=True, bolt=False, scale=0.78, strength=28.0)]
    for i, (mz, st) in enumerate(zip(ship['muzzles'], stages)):
        fl = T.muzzle_flash(f'Flash{i}', **st)
        fl.parent = ship
        fl.location = mz
        fl.rotation_euler = (0, 0, math.radians(-90))          # +X of the flash -> ship's fire direction
        ld = bpy.data.lights.new(f'FlashLight{i}', 'POINT')
        ld.energy = (0.5e5, 2e5, 0.6e5)[i]
        ld.color = (0.45, 0.8, 1.0)
        ld.shadow_soft_size = 1.5
        lo = bpy.data.objects.new(f'FlashLight{i}', ld)
        sc.collection.objects.link(lo)
        lo.parent = ship
        lo.location = Vector(mz) + Vector((0, -2.4, 0))
    bpy.data.objects['Key'].data.energy = 4.0
    bpy.data.objects['CamKey'].data.energy = 1.5
    aim(sc, cam, camkey, [ship], Vector((0.5, -0.8, -0.3)), 35, margin=0.93)
    cam.location += (cam.matrix_world.to_quaternion() @ Vector((0.03, -0.1, 0))) * max(ship.dimensions)
    bloom(render(sc, 'battleship_fire', (1280, 720))).save(out, quality=90)
    print('SHEET', out, flush=True)


for key in (list(SHEETS) if args.get('ship', 'all') == 'all' else [args['ship']]):
    sheet(key)
