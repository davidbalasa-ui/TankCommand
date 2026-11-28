"""Renders the v3 two-minute opening scene by scene (plan https://claude.ai/artifact/1pcm7ezWYRDsLXWM11mjb5).

    python film_v3.py --scene=s01 --out=DIR [--quality=draft|final] [--step=N] [--frames=A-B] [--shot=ID]
    python film_v3.py --stitch --out=DIR [--quality=draft|final]

Each scene module (v3_sNN.py) builds its own Blender scene with its own clock and lists its shots.
Frames land in DIR/<quality>/v3/<scene>_<shot>/f_NNNN.png (scene frames), resumable. --stitch joins
every scene in order; missing frames (step > 1) repeat the previous one.
"""
import glob
import importlib
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FPS = 24
# v4 cut (2026-11-27, David: "lacks intention and clarity", "a few more seconds per scene", "missing
# acceleration, things move one speed", "landing looks rushed"). scene id: output seconds (film order).
SCENES = [('s01', 11.0), ('s02', 10.0), ('s03', 6.0), ('s04', 9.0), ('s05', 9.0), ('s06', 7.5), ('s07', 9.0),
          ('s08', 17.0), ('s10', 7.0), ('s11', 6.5), ('land', 10.0), ('s12', 15.0), ('s13', 12.5), ('s14', 8.0),
          ('s15', 13.0), ('s16', 11.0)]
# each scene's own clock length in seconds (what its module animates)
ORIG = {'s01': 8.0, 's02': 8.0, 's03': 3.0, 's04': 9.0, 's05': 9.0, 's06': 5.0, 's07': 6.0, 's08': 19.0,
        's10': 5.0, 's11': 5.0, 'land': 10.0, 's12': 12.0, 's13': 10.0, 's14': 6.0, 's15': 13.0, 's16': 11.0}
# scenes kept exactly as approved: frames come from their final mp4 (David's favourites s04, plus s05/s08)
REUSE = {'s04': 'v3-final-s04.mp4', 's08': 'v3-s08-orb-pass4.mp4'}
REUSE_UPTO = {'s08': 343}        # s08: approved up to the Orb's kill; its explosion is re-rendered (v4 pass 2)
# eased retimes: (output second, scene-clock second) knots, monotone cubic between them. Slope < 1 is slow
# motion. Each scene: a slow build so the viewer can read what is there, the key moment slowed so it
# lands, then a hold on the consequence.
RETIME = {
    # dawn and the portal opening read slowly; the ships come out at speed, the last ones ease past
    's01': [(0, 0), (4.2, 2.3), (5.2, 2.8), (9.4, 7.3), (11.0, 8.0)],
    # the three groups climb and converge; they brake into line (decelerate) and the shields come on slowly
    's02': [(0, 0), (4.0, 3.6), (6.0, 5.0), (10.0, 8.0)],
    # long charge: energy creeps up the hook, then the beam leaves at full speed
    's03': [(0, 0), (3.6, 1.5), (4.6, 2.1), (6.0, 3.0)],
    # engines light slowly (ships barely moving), then the fleet surges: real acceleration
    's06': [(0, 0), (2.6, 1.1), (4.0, 2.2), (4.8, 2.6), (6.6, 4.4), (7.5, 5.0)],
    # the lines close; the corvette kills are slowed so they land
    's07': [(0, 0), (2.5, 1.6), (4.5, 2.8), (6.0, 3.4), (7.8, 5.2), (9.0, 6.0)],
    # clamps blow one after another, slow; pods leave fast
    's10': [(0, 0), (1.8, 1.1), (3.4, 2.5), (5.2, 3.6), (7.0, 5.0)],
    # pods fall, accelerating as the air thickens
    's11': [(0, 0), (2.5, 1.2), (5.0, 3.5), (6.5, 5.0)],
    's12': [(0, 0), (3.0, 2.0), (6.5, 4.5), (10.0, 7.5), (12.5, 9.8), (15.0, 12.0)],
    # the ground splits slowly; the Shard heaves up (slow start, fast middle, slow settle)
    's13': [(0, 0), (3.5, 2.2), (6.0, 4.6), (9.0, 7.6), (12.5, 10.0)],
    's14': [(0, 0), (2.5, 1.4), (5.0, 3.8), (8.0, 6.0)],
}
# fades baked into frames at stitch time: scene -> [(kind, seconds)]
FADES = {'s11': [('out_white', 0.6)], 'land': [('in_white', 0.8)]}
QUALITY = {
    'draft': dict(res=(640, 288), samples=8, blur=False, threshold=0.1),
    'final': dict(res=(1280, 576), samples=24, blur=True, threshold=0.05),
    'ship': dict(res=(960, 432), samples=12, blur=True, threshold=0.06),
}


def render_settings(q):
    import bpy
    sc = bpy.context.scene
    c = sc.cycles
    sc.render.engine = 'CYCLES'
    c.device = 'CPU'
    c.samples = q['samples']
    c.use_adaptive_sampling = True
    c.adaptive_threshold = q['threshold']
    c.use_denoising = True
    c.max_bounces = 4
    c.diffuse_bounces = 1
    c.glossy_bounces = 1
    c.transmission_bounces = 6
    c.transparent_max_bounces = 12
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 4.0
    sc.render.resolution_x, sc.render.resolution_y = q['res']
    sc.render.resolution_percentage = 100
    sc.render.use_motion_blur = q['blur']
    sc.render.motion_blur_shutter = 0.3
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.render.use_persistent_data = True


def out_frames(scene):
    return int(round(dict(SCENES)[scene] * FPS))


def src_frame(scene, F):
    """Output frame F (1-based) of the v4 cut -> fractional frame on the scene's own clock (eased retime)."""
    t = (F - 1) / FPS
    knots = RETIME.get(scene) or [(0.0, 0.0), (dict(SCENES)[scene], ORIG[scene])]
    return 1.0 + smooth_map(knots, t) * FPS


def smooth_map(knots, t):
    """Monotone cubic (Fritsch-Carlson) through (out_sec, src_sec) knots: speed changes are eased, never
    stepped, so things accelerate and decelerate instead of moving at one rate."""
    xs = [k[0] for k in knots]
    ys = [k[1] for k in knots]
    n = len(xs)
    if t <= xs[0]:
        return ys[0]
    if t >= xs[-1]:
        return ys[-1]
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        h = a * a + b * b
        if h > 9:
            k = 3 / math.sqrt(h)
            m[i], m[i + 1] = k * a * d[i], k * b * d[i]
    i = max(j for j in range(n - 1) if xs[j] <= t)
    hh = xs[i + 1] - xs[i]
    u = (t - xs[i]) / hh
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    return h00 * ys[i] + h10 * hh * m[i] + h01 * ys[i + 1] + h11 * hh * m[i + 1]


def render_scene(scene, out, quality='draft', step=1, frames=None, only=None, pick=0):
    import time
    import bpy
    import v3base
    mod = importlib.import_module('v3_' + scene)
    S = mod.build(draft=quality == 'draft')
    render_settings(QUALITY[quality])
    sc = bpy.context.scene
    nout = out_frames(scene)
    srcs = {F: src_frame(scene, F) for F in range(1, nout + 1)}
    for si, (sid, f0, f1, keys, shake) in enumerate(S.shots):
        if only and sid not in only:
            continue
        last = si == len(S.shots) - 1
        mine = [F for F, s in srcs.items() if f0 - 0.5 <= s and (last or s < S.shots[si + 1][1] - 0.5)]
        if not mine:
            continue
        for o in [o for o in bpy.data.objects if o.type == 'CAMERA']:
            bpy.data.objects.remove(o)
        v3base.build_camera(keys, shake)
        tmap = getattr(S, 'tmap', None)
        a, b = (max(mine[0], frames[0]), min(mine[-1], frames[1])) if frames else (mine[0], mine[-1])
        d = os.path.join(out, quality, VER, f'{scene}_{sid}')
        os.makedirs(d, exist_ok=True)
        todo = list(range(a, b + 1, step))
        if pick:
            todo = sorted({a + round(i * (b - a) / max(1, pick - 1)) for i in range(pick)})
        for f in todo:
            final = os.path.join(d, f'f_{f:04d}.png')
            if os.path.exists(final) and os.path.getsize(final) > 0:
                continue
            t0 = time.time()
            s = srcs[f]
            g = tmap(s) if tmap else s        # wrapped v2 scenes: local clock -> global clock
            sc.frame_set(int(g), subframe=g - int(g))
            tmp = os.path.join(d, f'_part_{f:04d}.png')
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            os.replace(tmp, final)
            print('FRAME', scene, sid, f, f'{time.time() - t0:.1f}s', flush=True)


VER = 'v4'
REUSE_DIR = '/mnt/project-files/cinematics/opening-film'


def extract_reuse(out, quality):
    """Approved scenes kept as they are: decode their final mp4 into this cut's frame folders."""
    w, h = QUALITY[quality]['res']
    for scene, mp4 in REUSE.items():
        d = os.path.join(out, quality, VER, f'{scene}_R')
        if os.path.isdir(d) and len(os.listdir(d)) >= min(out_frames(scene), REUSE_UPTO.get(scene, 10 ** 6)):
            continue
        os.makedirs(d, exist_ok=True)
        subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(REUSE_DIR, mp4),
                               '-vf', f'scale={w}:{h}:flags=lanczos', '-start_number', '1',
                               os.path.join(d, 'f_%04d.png')])
        for f in range(REUSE_UPTO.get(scene, 10 ** 6) + 1, 10 ** 4):
            p = os.path.join(d, f'f_{f:04d}.png')
            if os.path.exists(p):
                os.remove(p)


def stitch(out, quality='draft', crf=24):
    import importlib.util  # noqa: F401
    all_dir = os.path.join(out, quality, VER, '_all')
    if os.path.isdir(all_dir):
        shutil.rmtree(all_dir)
    os.makedirs(all_dir)
    n = 0
    last = None
    for scene, secs in SCENES:
        nf = int(round(secs * FPS))
        have = {}
        for d in sorted(glob.glob(os.path.join(out, quality, VER, f'{scene}_*'))):
            for p in glob.glob(os.path.join(d, 'f_*.png')):
                have[int(os.path.basename(p)[2:6])] = p
        fades = FADES.get(scene, [])
        for f in range(1, nf + 1):
            p = have.get(f, last)
            last = p
            n += 1
            if p is None:
                continue
            dst = os.path.join(all_dir, f'f_{n:05d}.png')
            k = 0.0
            for kind, sec in fades:
                m = int(round(sec * FPS))
                if kind == 'out_white' and f > nf - m:
                    k = max(k, (f - (nf - m)) / m)
                if kind == 'in_white' and f <= m:
                    k = max(k, 1.0 - (f - 1) / m)
            if k > 0:
                from PIL import Image
                im = Image.open(p).convert('RGB')
                Image.blend(im, Image.new('RGB', im.size, (255, 255, 255)), min(1.0, k)).save(dst)
            else:
                os.symlink(p, dst)
    mp4 = os.path.join(out, f'opening-v3-{quality}.mp4')
    total = n / FPS
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', '1',
           '-i', os.path.join(all_dir, 'f_%05d.png'),
           '-vf', f'fade=t=in:st=0:d=0.6,fade=t=out:st={total - 1.0:.2f}:d=1.0',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', str(crf), '-preset', 'slow', mp4]
    subprocess.check_call(cmd)
    print('WROTE', mp4, total)
    return mp4


def clip(out, quality, scene, dest, crf=18):
    """One scene on its own as an mp4 (for review)."""
    secs = dict(SCENES)[scene]
    nf = int(round(secs * FPS))
    have = {}
    for d in sorted(glob.glob(os.path.join(out, quality, VER, f'{scene}_*'))):
        for p in glob.glob(os.path.join(d, 'f_*.png')):
            have[int(os.path.basename(p)[2:6])] = p
    tmp = os.path.join(out, quality, VER, f'_clip_{scene}')
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    last = None
    for f in range(1, nf + 1):
        last = have.get(f, last)
        if last:
            os.symlink(last, os.path.join(tmp, f'f_{f:04d}.png'))
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', '1',
           '-i', os.path.join(tmp, 'f_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', str(crf),
           '-preset', 'slow', dest]
    subprocess.check_call(cmd)
    print('WROTE', dest)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = dict(a.lstrip('-').split('=', 1) if '=' in a else (a.lstrip('-'), '1') for a in argv)
    out = args.get('out', '/home/user/scratch/film')
    q = args.get('quality', 'draft')
    if 'stitch' in args:
        extract_reuse(out, q)
        stitch(out, q, int(args.get('crf', 24)))
    elif 'clip' in args:
        clip(out, q, args['clip'], args['dest'])
    else:
        fr_ = tuple(int(x) for x in args['frames'].split('-')) if 'frames' in args else None
        only = set(args['shot'].split(',')) if 'shot' in args else None
        render_scene(args['scene'], out, q, int(args.get('step', 1)), fr_, only, int(args.get('pick', 0)))
