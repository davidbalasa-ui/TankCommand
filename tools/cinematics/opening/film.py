"""Renders the 60 s opening video one shot at a time (approved timeline v2).

    python tools/cinematics/opening/film.py --shot=ID --out=DIR [--quality=draft|final]
                                            [--frames=A-B] [--step=N]
    python tools/cinematics/opening/film.py --stitch --out=DIR [--quality=draft|final]

A shot is a camera plus a range of the global clock (frame 1 = 0:00, 24 fps) inside one shared
scene: space.Space for the orbit fight, ground.Ground for the valley. Frames land in
DIR/<quality>/<ID>/f_NNNN.png named by global frame, so a re-render of any shot just replaces its
files and --stitch rebuilds the minute.
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FPS = 24


def fr(t):
    return int(round(1 + t * FPS))


# id: (first frame, last frame, scene, needs)
SHOTS = {
    '01': (fr(0), fr(3) - 1, 'space', ()),
    '02': (fr(3), fr(6) - 1, 'space', ('rift_open', 'arcadian')),
    '03': (fr(6), fr(10) - 1, 'space', ('arcadian',)),
    '04': (fr(10), fr(13) - 1, 'space', ('terran', 'arcadian')),
    '05a1': (fr(13), fr(14.5) - 1, 'space', ('beam',)),
    '05a2': (fr(14.5), fr(17) - 1, 'space', ('beam',)),
    '05b1': (fr(17), fr(18) - 1, 'space', ('barrage',)),
    '05b2': (fr(18), fr(19) - 1, 'space', ('barrage',)),
    '05b3': (fr(19), fr(20) - 1, 'space', ('barrage',)),
    '05b4': (fr(20), fr(22) - 1, 'space', ('barrage',)),
    '05b5': (fr(22), fr(23) - 1, 'space', ('barrage', 'beam')),
    '06': (fr(23), fr(26) - 1, 'space', ('dogfight', 'barrage')),
    '07a': (fr(26), fr(31) - 1, 'space', ('squid',)),
    '07b': (fr(31), fr(32) - 1, 'space', ('squid',)),
    '07c': (fr(32), fr(34) - 1, 'space', ('squid',)),
    '07d': (fr(34), fr(35) - 1, 'space', ('squid',)),
    '08a': (fr(35), fr(38) - 1, 'space', ('drop',)),
    '08b': (fr(38), fr(39) - 1, 'ground', ('landing',)),
    '09a': (fr(39), fr(41) - 1, 'ground', ('base',)),
    '09b': (fr(41), fr(42) - 1, 'ground', ('nests',)),
    '09c': (fr(42), fr(44) - 1, 'ground', ('armies',)),
    '09d': (fr(44), fr(47) - 1, 'ground', ('armies',)),
    '10a': (fr(47), fr(49) - 1, 'ground', ('armies', 'shard')),
    '10b': (fr(49), fr(51) - 1, 'ground', ('armies', 'shard')),
    '10c': (fr(51), fr(54) - 1, 'ground', ('armies', 'shard')),
    '10d': (fr(54), fr(55) - 1, 'ground', ('armies', 'shard')),
    '11': (fr(55), fr(60), 'space', ('ending',)),
}


# ================================================================== cameras (global frames)
def cam_keys(sid, S):
    """[(frame, pos, target[, lens])] for shot sid. S = the built scene (for live positions)."""
    from mathutils import Vector as V
    import space as SP
    R = SP.RIFT_AT
    P = SP.PLANET_C
    if sid == '01':
        # night side: opposite the sun (sun light travels along L ~ (0.60, -0.72, -0.34))
        L = V((0.604, -0.72, 0.0)).normalized()
        side = V((-L.y, L.x, 0))
        c0 = P + L * 5400 + V((0, 0, 1500))
        return [(fr(0), c0 - side * 300, P + V((0, 0, 2000)) - side * 300, 40),
                (fr(2.0), c0, P + V((0, 0, 2050)), 40),
                (fr(3.0) - 1, c0 + side * 120, P + V((0, 0, 2300)) + side * 120, 40)]
    if sid == '02':
        return [(fr(3), V((0, -300, -60)), R + V((0, 0, -100)), 16),
                (fr(5.0), V((50, -265, -52)), R + V((0, 0, -95)), 16),
                (fr(6) - 1, V((62, -256, -50)), R + V((0, 0, -93)), 16)]
    if sid == '03':
        return [(fr(6), R + V((-170, -70, -90)), R + V((-40, 0, 70)), 16),
                (fr(7.2), R + V((-230, -80, -70)), V((600, 0, 100)), 16),
                (fr(8.6), V((300, -300, 40)), V((560, 0, 90)), 20),
                (fr(10) - 1, V((280, -320, 38)), V((520, 0, 80)), 20)]
    if sid == '04':
        fp = S.T_HOLD['frigate']
        return [(fr(10), V((-265, 18, 28)), V((80, -10, 22)), 24),
                (fr(10.8), V((-250, 25, 24)), fp + V((20, -10, 0)), 24),
                (fr(11.5), fp + V((-28, -38, 10)), fp + V((12, 0, 0)), 28),
                (fr(12.3), fp + V((40, -18, 9)), fp + V((200, -30, 0)), 26),
                (fr(13) - 1, fp + V((105, -24, 9)), fp + V((400, -45, 0)), 26)]
    import bpy
    sc = bpy.context.scene

    def at(name, f, local=(0, 0, 0)):
        sc.frame_set(f)
        ob = S.obj[name]
        return ob.matrix_world @ V(local)
    Z = V((0, 0, 1))
    if sid == '05a1':
        D, Sh = at('dread', 330), at('shell', 330)
        M = (D + Sh) / 2
        return [(fr(13), M + V((-20, -430, 70)), M + V((0, 0, 5)), 24),
                (fr(14.5) - 1, M + V((-10, -415, 66)), M + V((5, 0, 5)), 24)]
    if sid == '05a2':
        b = S.beam
        d = b['d']
        perp = d.cross(Z).normalized()
        if perp.y < 0:
            perp = -perp
        en, ex = b['entry_w'], b['exit_w']
        D = at('dread', 380)
        return [(fr(14.5), en - d * 70 + perp * 60 + Z * 26, en, 26),
                (fr(15.3), (en + ex) / 2 + perp * 85 + Z * 30, (en + ex) / 2, 26),
                (fr(15.9), ex + d * 65 + perp * 60 + Z * 26, ex, 26),
                (fr(17) - 1, ex + d * 95 + perp * 90 + Z * 34, D, 26)]
    if sid == '05b1':
        B = at('bship', 409)
        return [(fr(17), B + V((-34, -58, 16)), B + V((0, 0, 0)), 24),
                (fr(18) - 1, B + V((-30, -55, 15)), B + V((2, 0, 0)), 24)]
    if sid == '05b2':
        m = sum((at('bship', 440, mz) for mz in S.muzzles), V()) / 3
        return [(fr(18), m + V((-14, -26, 7)), m + V((30, 4, 0)), 26),
                (fr(19) - 1, m + V((-12, -24, 6)), m + V((32, 4, 0)), 26)]
    if sid == '05b3':
        B, Sh = at('bship', 470), at('shell', 470)
        M = (B + Sh) / 2
        return [(fr(19), M + V((-60, -300, 70)), M + V((-20, 0, 0)), 24),
                (fr(20) - 1, M + V((-30, -290, 66)), M + V((60, 0, 0)), 24)]
    if sid == '05b4':
        Sh = at('shell', 490)
        return [(fr(20), Sh + V((-70, -125, 30)), Sh + V((0, 0, 0)), 24),
                (fr(21), Sh + V((-80, -160, 40)), Sh, 24),
                (fr(22) - 1, Sh + V((-95, -230, 55)), Sh, 24)]
    if sid == '05b5':
        D, Sh = at('dread', 540), at('shell', 540)
        return [(fr(22), D + V((-70, -150, 45)), Sh + V((40, 30, 20)), 24),
                (fr(23) - 1, D + V((-66, -146, 44)), Sh + V((40, 30, 18)), 24)]
    return S.camera_for(sid) if hasattr(S, 'camera_for') else None


def build_camera(keys, lens=28):
    import bpy
    from mathutils import Vector
    sc = bpy.context.scene
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = lens
    cam.data.clip_end = 60000
    cam.data.clip_start = 0.1
    prev = None
    for k in keys:
        f, p, tgt = k[:3]
        cam.location = p
        q = (Vector(tgt) - Vector(p)).to_track_quat('-Z', 'Y')
        if len(k) > 4 and k[4]:
            from mathutils import Quaternion
            q = q @ Quaternion((0, 0, 1), k[4])          # roll about the view axis
        e = q.to_euler()
        if prev is not None:
            e.make_compatible(prev)
        cam.rotation_euler = e
        prev = e.copy()
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
        if len(k) > 3:
            cam.data.lens = k[3]
            cam.data.keyframe_insert('lens', frame=f)
    import common as C
    C.set_interp(cam, 'BEZIER')
    return cam


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
    c.transmission_bounces = 4
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


def render_shot(sid, out, quality='draft', frames=None, step=1):
    import bpy
    f0, f1, scene, need = SHOTS[sid]
    if frames:
        a, b = frames
        f0, f1 = max(f0, a), min(f1, b)
    if scene == 'space':
        import space
        S = space.Space(need=set(need) | {'_shot_' + sid}, draft=quality == 'draft')
    else:
        import ground
        S = ground.Ground(need=set(need), draft=quality == 'draft')
    keys = cam_keys(sid, S)
    build_camera(keys)
    render_settings(QUALITY[quality])
    sc = bpy.context.scene
    d = os.path.join(out, quality, sid)
    os.makedirs(d, exist_ok=True)
    for f in range(f0, f1 + 1, step):
        final = os.path.join(d, f'f_{f:04d}.png')
        if os.path.exists(final) and os.path.getsize(final) > 0:
            print('SKIP', sid, f, flush=True)       # resumable: finished frames are never redone
            continue
        sc.frame_set(f)
        tmp = os.path.join(d, f'_part_{f:04d}.png')
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, final)                       # a frame only appears once fully written
        print('FRAME', sid, f, flush=True)


def stitch(out, quality='draft', crf=26):
    """Join every shot's frames (global numbering) into one minute, with the white-out at 0:37-0:38
    and the fade to black at the end, plus bloom (post.py style)."""
    import glob
    import shutil
    all_dir = os.path.join(out, quality, '_all')
    if os.path.isdir(all_dir):
        shutil.rmtree(all_dir)
    os.makedirs(all_dir)
    have = {}
    for sid in SHOTS:
        for p in glob.glob(os.path.join(out, quality, sid, 'f_*.png')):
            f = int(os.path.basename(p)[2:6])
            have[f] = p
    last = None
    for f in range(1, fr(60) + 1):
        p = have.get(f, last)
        if p is None:
            continue
        os.symlink(p, os.path.join(all_dir, f'f_{f:04d}.png'))
        last = p
    mp4 = os.path.join(out, f'opening-{quality}.mp4')
    w0, w1, w2 = (fr(36.85) - 1) / FPS, (fr(37.3) - 1) / FPS, (fr(38.0) - 1) / FPS
    vf = (f"fade=t=out:st={w0:.3f}:d={w1 - w0:.3f}:color=white,"
          f"fade=t=in:st={w2:.3f}:d=0.35:color=white,"
          f"fade=t=out:st={59.5:.3f}:d=0.5:color=black")
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', '1',
           '-i', os.path.join(all_dir, 'f_%04d.png'), '-vf', vf, '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
           '-crf', str(crf), '-preset', 'slow', mp4]
    subprocess.check_call(cmd)
    print('WROTE', mp4)
    return mp4


if __name__ == '__main__':
    args = dict(a.lstrip('-').split('=', 1) if '=' in a else (a.lstrip('-'), '1') for a in sys.argv[1:])
    out = args.get('out', '/mnt/project-files/cinematics/opening-film')
    q = args.get('quality', 'draft')
    if 'stitch' in args:
        stitch(out, q)
    else:
        fr_ = tuple(int(x) for x in args['frames'].split('-')) if 'frames' in args else None
        render_shot(args['shot'], out, q, fr_, int(args.get('step', 1)))
