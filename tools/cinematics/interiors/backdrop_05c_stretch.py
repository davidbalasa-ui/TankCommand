"""Battle backdrop 5c/5d: the Arcadian portal stretch as a sequence (stage stills, contact sheet, draft clip).

    PY=/home/user/artenv/venv/bin/python ; S=tools/cinematics/interiors/backdrop_05c_stretch.py
    $PY $S --frame=31 --out=FILE.jpg [--final=1]      one still at clip frame 31
    $PY $S --stages=1 --dir=DIR [--final=1]            the six stage stills (stage_1.jpg ...) in one process
    $PY $S --sheet=1 --dir=DIR --out=SHEET.jpg         compose the stage stills into the contact sheet
    $PY $S --clip=1 --dir=DIR [--f0=1 --f1=72]         every frame of the 3 s draft clip as DIR/f_0001.jpg ...

One crescent mothership is drawn out of the portal over frames 8..48 (thread-thin, half out, nearly free, snap
with a ring pulse), Arcadian corvettes come through on side lanes at other moments. See backdrop_stretch.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
import backdrop_stretch as ST  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

A = K.ARGS
DIR = A.get('dir', os.path.join(K.SCRATCH, 'stretch'))
NF = 72
STAGES = [int(v) for v in A.get('stage_frames', '13,22,30,36,41,51').split(',')]
F0, DUR = 8, 40                       # the crescent starts to show / its tail comes free at F0 + DUR


def build():
    k = K.Kit(sun_dir=(-0.6, 0.5, -0.45), sun_energy=5.0, planet=False, rim_dir=(0.3, -0.9, 0.1), rim=1.5,
              fill_dir=(-0.1, 1, -0.2), fill=2.2, tint='teal', nebula=1.6)
    sc = bpy.context.scene
    sc.frame_end = NF
    k.camera((0, 0, 0), (0, 100, 0), lens=float(A.get('lens', 30)))
    P = k.cam_pt
    AT = P(-0.54, 0.0, 440)
    n = Vector((0.974, -0.225, 0.02)).normalized()
    S = 215.0
    DZ = 0.45                                                # a shorter throat, so its far end stays behind the mouth
    rf = ST.portal(k, AT, n, S, NF, seed=11)
    rf.scale = (S, S, DZ)
    k.light(AT + n * 300 + Vector((0, 0, 60)), (1.0, 0.85, 0.6), 2.5e7, 30)
    ships = []
    cr = ST.Stretcher(k, 'crescent', AT, n, S, scale=2.8, roll=-82, depth=240 * DZ, seed=3, lines=12, glow=2.2, zf=0.55, w=0.2)
    ships.append((cr, F0, DUR, ST.Pulse(k, AT, n, S)))
    # corvettes on side lanes: (lane offset in void radii, first frame, frames to come free, roll)
    for i, (off, f0, dur, roll) in enumerate((((-0.5, 0.74), -16, 20, 20), ((-0.3, -0.8), 0, 20, -15),
                                              ((0.2, 0.84), 26, 22, 10), ((-0.6, -0.62), 46, 24, -25))):
        cv = ST.Stretcher(k, 'acorv', AT, n, S, scale=3.6, roll=roll, off=off, a=7.0, zf=0.7, w=0.26,
                          depth=240 * DZ, seed=20 + i, lines=6, line_r=S * 0.0009, bolt_w=0.09, glow=2.2)
        lane = Vector(AT) + cv.e1v * off[0] * S * 0.5 + cv.e2v * off[1] * S * 0.5
        ships.append((cv, f0, dur, None))
    return k, ships


def pose(ships, f):
    boost = 3.5
    for i, (st, f0, dur, pulse) in enumerate(ships):
        x = ST.nose_at(st.L, f, f0, dur, st.zf)
        after = f - (f0 + dur)
        st.set(x, lines=1.0 if after <= 0 else max(0.0, 1.0 - after / 5.0), tick=f // 2)
        if pulse:
            v = st.L * (st.zf + 1.03) * 1.25 / dur
            pulse.set(after if after >= 0 else None, life=16.0, z0=st.zf * st.L, speed=0.3 * v)
        if i == 0 and 0 <= after < 12:
            boost = 3.5 + 6.0 * (1 - after / 12.0) ** 2
    ST.ring_boost(boost)


def render(k, f, out, final):
    sc = bpy.context.scene
    res = (1280, 720) if final else (960, 540)
    samples = int(A.get('samples', 40 if final else 14))
    k.sh.render_settings(res, samples, blur=False)
    sc.cycles.adaptive_threshold = 0.04 if final else 0.08
    sc.cycles.transparent_max_bounces = 24
    sc.cycles.max_bounces = 4
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = int(A.get('threads', 3))
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.frame_set(f)
    raw = os.path.splitext(out)[0] + '_raw.png'
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    im = K.post(raw, 1.0, 0.2)
    im.save(out, quality=92)
    os.remove(raw)
    print('WROTE', out, flush=True)


def sheet(out):
    """Six stage stills, reading order, on black with thin gold stage pips (no text)."""
    ims = [Image.open(os.path.join(DIR, f'stage_{i + 1}.jpg')).convert('RGB') for i in range(len(STAGES))]
    w, h = ims[0].size
    g = 14
    cols = 3
    rows = (len(ims) + cols - 1) // cols
    sh = Image.new('RGB', (cols * w + (cols + 1) * g, rows * h + (rows + 1) * g), (6, 7, 9))
    dr = ImageDraw.Draw(sh)
    for i, im in enumerate(ims):
        x, y = g + (i % cols) * (w + g), g + (i // cols) * (h + g)
        sh.paste(im, (x, y))
        dr.rectangle((x, y, x + w - 1, y + h - 1), outline=(70, 56, 30))
        for j in range(i + 1):                               # i + 1 pips: which stage this is
            dr.rectangle((x + 22 + j * 20, y + h - 34, x + 22 + j * 20 + 11, y + h - 23), fill=(255, 205, 110))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sh.save(out, quality=92)
    print('WROTE', out, sh.size, flush=True)


if A.get('sheet') == '1':
    sheet(A['out'])
else:
    os.makedirs(DIR, exist_ok=True)
    k, ships = build()
    if A.get('clip') == '1':
        for f in range(int(A.get('f0', 1)), int(A.get('f1', NF)) + 1, int(A.get('step', 1))):
            o = os.path.join(DIR, f'f_{f:04d}.jpg')
            if os.path.exists(o):
                continue
            pose(ships, f)
            render(k, f, o, False)
    elif A.get('stages') == '1':
        for i, f in enumerate(STAGES):
            pose(ships, f)
            render(k, f, os.path.join(DIR, f'stage_{i + 1}.jpg'), K.FINAL)
    else:
        f = int(A.get('frame', 31))
        pose(ships, f)
        render(k, f, A.get('out', os.path.join(DIR, f'test_{f:03d}.jpg')), K.FINAL)
