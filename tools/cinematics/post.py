"""Bloom + encode for cinematic frames.

    /home/user/artenv/bin/python tools/cinematics/post.py FRAMES_DIR OUT.mp4 [--crf=24] [--fps=24]

Adds a soft glow around bright pixels (Cycles has no bloom), then encodes H.264 (High profile,
yuv420p, faststart) which every Android WebView plays. Also writes OUT_sheet.jpg (6 frames).
"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opts = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if a.startswith('--'))
src, out = args
crf = opts.get('crf', '24')
fps = opts.get('fps', '24')
tmp = os.path.join(os.path.dirname(os.path.abspath(out)), '_bloom')
os.makedirs(tmp, exist_ok=True)

files = sorted(glob.glob(os.path.join(src, '*.png')))
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB')
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a.max(axis=2, keepdims=True)
    bright = np.clip((lum - 0.72) / 0.28, 0, 1) * a
    b = Image.fromarray((bright * 255).astype(np.uint8))
    glow = np.zeros_like(a)
    for r, w in [(4, 0.45), (12, 0.35), (32, 0.3)]:
        glow += np.asarray(b.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255.0 * w
    o = 1 - (1 - a) * (1 - np.clip(glow, 0, 1))      # screen blend
    Image.fromarray((np.clip(o, 0, 1) * 255).astype(np.uint8)).save(os.path.join(tmp, f'b_{i:04d}.png'))

subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', fps, '-i', os.path.join(tmp, 'b_%04d.png'),
                '-c:v', 'libx264', '-preset', 'slow', '-profile:v', 'high', '-crf', crf, '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart', out], check=True)
picks = [int(k * (len(files) - 1) / 5) for k in range(6)]
ims = [Image.open(os.path.join(tmp, f'b_{k:04d}.png')) for k in picks]
W, H = ims[0].size
sheet = Image.new('RGB', (W * 2, H * 3))
for k, im in enumerate(ims):
    sheet.paste(im, ((k % 2) * W, (k // 2) * H))
sheet.resize((W, int(H * 1.5))).save(out.rsplit('.', 1)[0] + '_sheet.jpg', quality=85)
print(out, os.path.getsize(out), 'bytes,', len(files), 'frames')
