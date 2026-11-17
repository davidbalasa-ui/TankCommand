"""Turn rendered RGBA frames into a library flipbook.

python finalize.py <png_dir> <name> --extent M --origin_v V [--loop K] [--atlas N] [--lib DIR]

- Frames are straight-alpha RGBA PNGs (Cycles film_transparent output).
- --loop K : make frames seamless by cross-fading the last K frames into the first K
  (output has len-K frames).
- Writes <lib>/flipbooks/<name>/0001.png..., manifest.json, preview.gif (over sand),
  and a game atlas <lib>/atlases/<name>.png (grid, N px cells) + .json.
"""
import argparse, glob, json, math, os
import numpy as np
from PIL import Image

LIB = '/mnt/project-files/fx-library'


def load(d):
    fs = sorted(glob.glob(os.path.join(d, '*.png')))
    return [np.asarray(Image.open(f).convert('RGBA')).astype(np.float32) / 255 for f in fs]


def premul(a):
    o = a.copy(); o[..., :3] *= o[..., 3:4]; return o


def unpremul(a):
    o = a.copy(); al = np.maximum(o[..., 3:4], 1e-4); o[..., :3] = np.where(o[..., 3:4] > 0, o[..., :3] / al, 0); return o


def crossfade_loop(frames, k):
    n = len(frames)
    pm = [premul(f) for f in frames]
    out = []
    for i in range(n - k):
        if i < k:
            w = (i + 1) / (k + 1)
            mixed = pm[i] * w + pm[n - k + i] * (1 - w)
            out.append(unpremul(mixed))
        else:
            out.append(frames[i])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('png_dir'); ap.add_argument('name')
    ap.add_argument('--extent', type=float, required=True, help='metres covered by the full square frame width')
    ap.add_argument('--origin_v', type=float, default=0.0, help='ground/emitter height in the image, 0=bottom')
    ap.add_argument('--loop', type=int, default=0)
    ap.add_argument('--drop_first', type=int, default=0)
    ap.add_argument('--atlas', type=int, default=128)
    ap.add_argument('--lib', default=LIB)
    ap.add_argument('--tint', default='', help='neutral|fire|gold : hint for users')
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    fr = load(a.png_dir)[a.drop_first:]
    if a.loop:
        fr = crossfade_loop(fr, a.loop)
    od = os.path.join(a.lib, 'flipbooks', a.name)
    os.makedirs(od, exist_ok=True)
    for f in glob.glob(os.path.join(od, '*.png')):
        os.remove(f)
    imgs = []
    for i, f in enumerate(fr):
        im = Image.fromarray((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
        im.save(os.path.join(od, '%04d.png' % (i + 1)), optimize=True)
        imgs.append(im)
    W = imgs[0].size[0]
    man = dict(name=a.name, frames=len(imgs), fps=24, size_px=W, extent_m=a.extent,
               origin_uv=[0.5, a.origin_v], loop=bool(a.loop), alpha='straight', tint=a.tint, note=a.note)
    json.dump(man, open(os.path.join(od, 'manifest.json'), 'w'), indent=1)
    # preview gif over sand
    pv = []
    for im in imgs[::1]:
        bg = Image.new('RGBA', im.size, (150, 135, 110, 255)); bg.alpha_composite(im)
        pv.append(bg.convert('RGB').resize((W // 2, W // 2)))
    pv[0].save(os.path.join(od, 'preview.gif'), save_all=True, append_images=pv[1:], duration=42, loop=0)
    # game atlas
    n = len(imgs); cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols); c = a.atlas
    at = Image.new('RGBA', (cols * c, rows * c), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        at.paste(im.resize((c, c), Image.LANCZOS), ((i % cols) * c, (i // cols) * c))
    ad = os.path.join(a.lib, 'atlases'); os.makedirs(ad, exist_ok=True)
    at.save(os.path.join(ad, a.name + '.png'), optimize=True)
    json.dump(dict(man, cols=cols, rows=rows, cell_px=c), open(os.path.join(ad, a.name + '.json'), 'w'), indent=1)
    print('wrote', od, n, 'frames')


if __name__ == '__main__':
    main()
