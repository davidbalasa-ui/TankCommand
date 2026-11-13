"""Design sheet (hero view large + side + top small) of one Arcadian fleet ship.

    /home/user/artenv/bin/python tools/cinematics/arcadian_fleet_stills.py --ship=NAME --out=DIR
        [--samples=28] [--file=01-crescent-mothership] [--pose=reach] [--views=hero,side,top]

NAME is a key of arcadian_fleet.BUILDERS (crescent, shell, lens, squid, corvette, stingray) or 'all'.
Writes DIR/<file>.jpg (1920x720). Cycles has no bloom, so the glow is added here in 2D.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arcadian_fleet as A  # noqa: E402
import forge as F  # noqa: E402

args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
OUT = args.get('out', '/tmp/fleet')
os.makedirs(OUT, exist_ok=True)
TMP = args.get('tmp', os.path.join(OUT, '_views'))
os.makedirs(TMP, exist_ok=True)

FILES = {'crescent': '01-crescent-mothership', 'shell': '02-shell-mothership', 'lens': '03-lens-mothership',
         'squid': '04-squid-ship', 'corvette': '05-corvette', 'stingray': '06-stingray-fighter'}
LABEL = {'crescent': 'Crescent mothership v2', 'shell': 'Shell mothership v2', 'lens': 'Lens mothership v2',
         'squid': 'Squid ship', 'corvette': 'Corvette', 'stingray': 'Stingray fighter'}
# per-ship camera directions (from the ship toward the camera)
VIEWS = {
    'default': dict(hero=(0.62, -0.78, 0.42), side=(0.03, -1, 0.06), top=(0.0, -0.18, 1)),
    'crescent': dict(hero=(0.55, -0.72, 0.62), side=(0.03, -1, 0.1), top=(0.0, -0.12, 1)),
    'shell': dict(hero=(0.66, -0.75, 0.3), side=(0.0, -1, 0.04), top=(0.0, -0.2, 1)),
    'lens': dict(hero=(0.7, -0.7, 0.2), side=(0.03, -1, 0.05), top=(0.0, -0.2, 1)),
    'squid': dict(hero=(0.5, -0.8, 0.38), side=(0.0, -1, 0.06), top=(0.0, -0.15, 1)),
    'stingray': dict(hero=(0.6, -0.7, 0.55), side=(0.05, -1, 0.12), top=(0.0, -0.12, 1)),
}


def scene_setup(samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    F.ST.update(parts=[], mats={}, group='Hull', seq=0)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = int(args.get('threads', 3))
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    # world: near-black space with faint stars for the camera, a soft warm/cool studio for the
    # reflections so the gold metal has something to mirror.
    w = bpy.data.worlds.new('Space')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    mix = nt.nodes.new('ShaderNodeMixShader')
    lp = nt.nodes.new('ShaderNodeLightPath')
    cam_bg = nt.nodes.new('ShaderNodeBackground')
    env_bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 260.0
    star = nt.nodes.new('ShaderNodeMapRange')
    star.inputs['From Min'].default_value = 0.035
    star.inputs['From Max'].default_value = 0.0
    star.inputs['To Min'].default_value = 0.0
    star.inputs['To Max'].default_value = 0.9
    nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
    nt.links.new(vor.outputs['Distance'], star.inputs['Value'])
    addc = nt.nodes.new('ShaderNodeMixRGB')
    addc.blend_type = 'ADD'
    addc.inputs['Fac'].default_value = 1.0
    addc.inputs['Color1'].default_value = (0.008, 0.01, 0.02, 1)
    nt.links.new(star.outputs[0], addc.inputs['Color2'])
    nt.links.new(addc.outputs[0], cam_bg.inputs['Color'])
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.inputs['Scale'].default_value = 1.6
    noi.inputs['Detail'].default_value = 2.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.38
    ramp.color_ramp.elements[0].color = (0.01, 0.014, 0.03, 1)
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (1.0, 0.78, 0.5, 1)
    nt.links.new(tc.outputs['Generated'], noi.inputs['Vector'])
    nt.links.new(noi.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], env_bg.inputs['Color'])
    env_bg.inputs['Strength'].default_value = float(args.get('env', 0.7))
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(env_bg.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])

    def light(n, rot, e, col, ang=3):
        ld = bpy.data.lights.new(n, 'SUN')
        ld.energy = e
        ld.color = col
        ld.angle = math.radians(ang)
        o = bpy.data.objects.new(n, ld)
        sc.collection.objects.link(o)
        o.rotation_euler = [math.radians(a) for a in rot]
        return o
    light('Key', (50, 10, 140), 3.2, (1.0, 0.94, 0.84))
    light('Rim', (-62, 0, -35), 4.0, (1.0, 0.88, 0.72), ang=6)
    light('Fill', (120, 0, 60), 1.0, (0.55, 0.6, 0.8))
    cl = light('CamKey', (0, 0, 0), 1.5, (1.0, 0.93, 0.85), ang=8)
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.01
    cam.data.clip_end = 4000
    cam.data.lens = 42
    return sc, cam, cl


def corners(ship):
    """A sample of the ship's world-space vertices (for framing) and its bounding box."""
    pts = []
    for o in [ship] + [c for c in ship.children if c.type == 'MESH']:
        co = np.empty(len(o.data.vertices) * 3, dtype=np.float32)
        o.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        step = max(1, len(co) // 3000)
        pts += [o.matrix_world @ Vector(c) for c in co[::step].tolist()]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return pts, lo, hi


def frame(cam, cl, pts, ctr, d, aspect, fill=0.9, flat=False):
    """Aim the camera along -d and pull it in until the sampled vertices fill the frame. flat = top
    view: keep the ship's +X pointing right."""
    from mathutils import Matrix
    d = Vector(d).normalized()
    th = math.atan(18.0 / cam.data.lens)             # half horizontal fov (36 mm sensor)
    tx, ty = math.tan(th), math.tan(th) / aspect
    if flat:
        right = (Vector((1, 0, 0)) - d * d.x).normalized()
        rot = Matrix((right, d.cross(right), d)).transposed().to_euler()
    else:
        rot = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.rotation_euler = rot
    dist = (Vector([max(p[i] for p in pts) for i in range(3)]) - Vector([min(p[i] for p in pts) for i in range(3)])).length
    off = Vector((0, 0, 0))
    for _ in range(14):
        cam.location = ctr + off + d * dist
        bpy.context.view_layer.update()
        inv = cam.matrix_world.inverted()
        qs = [inv @ p for p in pts]
        xs = [q.x / (-q.z * tx) for q in qs]
        ys = [q.y / (-q.z * ty) for q in qs]
        k = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
        # re-centre on what is actually seen, then scale
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        m = cam.matrix_world.to_3x3()
        off += (m @ Vector((cx * tx, cy * ty, 0))) * dist * 0.8
        dist *= (k / fill) ** 0.9
    cl.rotation_euler = cam.rotation_euler.copy()
    cl.rotation_euler[0] -= 0.45


def bloom(im, amount=1.0):
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255.0
    lum = (a * np.array([0.3, 0.55, 0.15], dtype=np.float32)).sum(axis=2, keepdims=True)
    bright = np.clip((lum - 0.8) / 0.2, 0, 1) * a
    b = Image.fromarray((bright * 255).astype(np.uint8))
    k = im.size[0] / 1280.0
    acc = np.zeros_like(a)
    for r, wgt in ((2.5, 0.4), (8, 0.4), (24, 0.32)):
        g = np.asarray(b.filter(ImageFilter.GaussianBlur(r * k))).astype(np.float32) / 255.0
        acc += g * wgt * np.array([1.0, 0.82, 0.5], dtype=np.float32)
    o = 1.0 - (1.0 - a) * (1.0 - np.clip(acc * amount, 0, 1))
    return Image.fromarray((np.clip(o, 0, 1) * 255).astype(np.uint8))


def render_ship(key):
    sc, cam, cl = scene_setup(int(args.get('samples', 28)))
    kw = {}
    if key == 'squid' and 'pose' in args:
        kw['pose'] = args['pose']
    ship, core = A.BUILDERS[key](**kw)
    tris = A.tri_count(ship)
    pts, lo, hi = corners(ship)
    print(f'SHIP {key} SHAPES {ship["shapes"]} TRIS {tris} BOX {tuple(round(v, 2) for v in lo)} '
          f'{tuple(round(v, 2) for v in hi)}', flush=True)
    ctr = (lo + hi) / 2
    views = dict(VIEWS['default'])
    views.update(VIEWS.get(key, {}))
    want = args.get('views', 'hero,side,top').split(',')
    scale = float(args.get('scale', 1.0))
    ims = {}
    for v in want:
        big = v == 'hero'
        sc.render.resolution_x, sc.render.resolution_y = (int(1280 * scale), int(720 * scale)) if big \
            else (int(640 * scale), int(360 * scale))
        frame(cam, cl, pts, ctr, views[v], 16 / 9, fill=0.86 if big else 0.88, flat=(v == 'top'))
        sc.render.filepath = os.path.join(TMP, f'{key}_{v}.png')
        bpy.ops.render.render(write_still=True)
        ims[v] = bloom(Image.open(sc.render.filepath), float(args.get('bloom', 1.0)))
    if set(want) >= {'hero', 'side', 'top'}:
        W, H = int(1920 * scale), int(720 * scale)
        sheet = Image.new('RGB', (W, H), (2, 3, 6))
        sheet.paste(ims['hero'], (0, 0))
        sheet.paste(ims['side'], (int(1280 * scale), 0))
        sheet.paste(ims['top'], (int(1280 * scale), int(360 * scale)))
        dr = ImageDraw.Draw(sheet)
        size = hi - lo
        dr.text((14, H - 24), f'{LABEL[key]}  -  {tris:,} triangles  -  {size.x:.1f} x {size.y:.1f} x {size.z:.1f} units',
                fill=(200, 170, 110))
        path = os.path.join(OUT, args.get('file', FILES[key]) + '.jpg')
        sheet.save(path, quality=90)
        print('WROTE', path, flush=True)


keys = list(A.BUILDERS) if args.get('ship', 'all') == 'all' else args['ship'].split(',')
for k in keys:
    render_ship(k)
