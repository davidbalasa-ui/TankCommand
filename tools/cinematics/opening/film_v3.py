"""Renders the v3 two-minute opening scene by scene (plan https://claude.ai/artifact/1pcm7ezWYRDsLXWM11mjb5).

    python film_v3.py --scene=s01 --out=DIR [--quality=draft|final] [--step=N] [--frames=A-B] [--shot=ID]
    python film_v3.py --stitch --out=DIR [--quality=draft|final]

Each scene module (v3_sNN.py) builds its own Blender scene with its own clock and lists its shots.
Frames land in DIR/<quality>/v3/<scene>_<shot>/f_NNNN.png (scene frames), resumable. --stitch joins
every scene in order; missing frames (step > 1) repeat the previous one.
"""
import glob
import importlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FPS = 24
# scene id: seconds (order = film order)
SCENES = [('s01', 8.0), ('s02', 8.0), ('s03', 3.0), ('s04', 9.0), ('s05', 9.0), ('s06', 5.0), ('s07', 6.0),
          ('s08', 19.0), ('s10', 5.0), ('s11', 5.0), ('s12', 12.0), ('s13', 10.0), ('s14', 6.0),
          ('s15', 8.0), ('s16', 8.0)]
# fades baked into frames at stitch time: scene -> [(kind, seconds)]
FADES = {'s11': [('out_white', 0.5)], 's12': [('in_white', 0.4)]}
QUALITY = {
    'draft': dict(res=(640, 288), samples=8, blur=False, threshold=0.1),
    'final': dict(res=(1280, 576), samples=24, blur=True, threshold=0.05),
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


def render_scene(scene, out, quality='draft', step=1, frames=None, only=None, pick=0):
    import bpy
    import v3base
    mod = importlib.import_module('v3_' + scene)
    S = mod.build(draft=quality == 'draft')
    render_settings(QUALITY[quality])
    sc = bpy.context.scene
    for sid, f0, f1, keys, shake in S.shots:
        if only and sid not in only:
            continue
        for o in [o for o in bpy.data.objects if o.type == 'CAMERA']:
            bpy.data.objects.remove(o)
        v3base.build_camera(keys, shake)
        tmap = getattr(S, 'tmap', None)
        a, b = (max(f0, frames[0]), min(f1, frames[1])) if frames else (f0, f1)
        d = os.path.join(out, quality, 'v3', f'{scene}_{sid}')
        os.makedirs(d, exist_ok=True)
        todo = list(range(a, b + 1, step))
        if pick:
            todo = sorted({a + round(i * (b - a) / max(1, pick - 1)) for i in range(pick)})
        for f in todo:
            final = os.path.join(d, f'f_{f:04d}.png')
            if os.path.exists(final) and os.path.getsize(final) > 0:
                continue
            if tmap:                      # v2 global-clock scene played back on this scene's clock
                g = tmap(f)
                sc.frame_set(int(g), subframe=g - int(g))
            else:
                sc.frame_set(f)
            tmp = os.path.join(d, f'_part_{f:04d}.png')
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            os.replace(tmp, final)
            print('FRAME', scene, sid, f, flush=True)


def stitch(out, quality='draft', crf=24):
    import importlib.util  # noqa: F401
    all_dir = os.path.join(out, quality, 'v3', '_all')
    if os.path.isdir(all_dir):
        shutil.rmtree(all_dir)
    os.makedirs(all_dir)
    n = 0
    last = None
    for scene, secs in SCENES:
        nf = int(round(secs * FPS))
        have = {}
        for d in sorted(glob.glob(os.path.join(out, quality, 'v3', f'{scene}_*'))):
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
    for d in sorted(glob.glob(os.path.join(out, quality, 'v3', f'{scene}_*'))):
        for p in glob.glob(os.path.join(d, 'f_*.png')):
            have[int(os.path.basename(p)[2:6])] = p
    tmp = os.path.join(out, quality, 'v3', f'_clip_{scene}')
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
        stitch(out, q)
    elif 'clip' in args:
        clip(out, q, args['clip'], args['dest'])
    else:
        fr_ = tuple(int(x) for x in args['frames'].split('-')) if 'frames' in args else None
        only = set(args['shot'].split(',')) if 'shot' in args else None
        render_scene(args['scene'], out, q, int(args.get('step', 1)), fr_, only, int(args.get('pick', 0)))
