"""End-game crystal texture atlas, 512x512, painted in code.
  facet  (  0,  0)-(256,256)  deep violet glass with lighter streaks
  core   (256,  0)-(512,256)  swirling violet-white vortex (emissive)
  ribbon (  0,256)-(256,512)  soft violet strip, bright centre line (emissive)
  stone  (256,256)-(512,512)  weathered pale stone with violet cracks
Usage: python3 atlas_crystal.py <outdir>  -> crystal_atlas.png, crystal_emissive.png
"""
import math
import random
import sys
from PIL import Image, ImageDraw, ImageFilter

S = 512
VIOLET = (170, 90, 255)


def main(out):
    rng = random.Random(7)
    img = Image.new('RGB', (S, S), (0, 0, 0))
    emit = Image.new('RGB', (S, S), (0, 0, 0))
    d, e = ImageDraw.Draw(img), ImageDraw.Draw(emit)
    # Facet: vertical violet gradient plus diagonal light streaks.
    for y in range(256):
        t = y / 255
        d.line((0, y, 255, y), fill=(int(55 + 40 * t), int(18 + 12 * t), int(95 + 55 * t)))
    for _ in range(18):
        x = rng.uniform(-60, 256)
        w = rng.uniform(2, 10)
        c = (int(130 + rng.uniform(0, 50)), int(80 + rng.uniform(0, 40)), int(200 + rng.uniform(0, 55)))
        d.polygon([(x, 0), (x + w, 0), (x + w + 90, 256), (x + 90, 256)], fill=c)
        e.polygon([(x, 0), (x + w, 0), (x + w + 90, 256), (x + 90, 256)], fill=(40, 15, 70))
    # Core: a spiral vortex.
    cx, cy = 384, 128
    for r in range(120, 0, -1):
        t = r / 120
        c = (int(255 - 150 * t), int(235 - 200 * t), 255)
        for dd in (d, e):
            dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c if t < 0.25 else (int(60 + 60 * (1 - t)), 20, int(110 + 100 * (1 - t))))
    for arm in range(5):
        pts = []
        for i in range(60):
            a = arm * 2 * math.pi / 5 + i * 0.09
            r = 4 + i * 1.9
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        for dd in (d, e):
            dd.line(pts, fill=(220, 170, 255), width=3)
    # Ribbon: soft strip across V with a bright centre (glow everywhere).
    for x in range(256):
        t = abs(x - 128) / 128
        k = max(0.0, 1 - t) ** 1.6
        c = (int(VIOLET[0] * k + 70 * k ** 6), int(VIOLET[1] * k + 120 * k ** 6), int(VIOLET[2] * k))
        for dd in (d, e):
            dd.line((x, 256, x, 511), fill=c)
    # Stone with violet cracks.
    for y in range(256, 512):
        for x in range(256, 512, 4):
            v = int(150 + rng.uniform(-18, 18))
            d.line((x, y, x + 3, y), fill=(v, v - 6, v - 14))
    for _ in range(8):
        x, y = rng.uniform(256, 512), rng.uniform(256, 512)
        pts = [(x, y)]
        for _ in range(10):
            x = min(511, max(256, x + rng.uniform(-24, 24)))
            y = min(511, max(256, y + rng.uniform(-24, 24)))
            pts.append((x, y))
        for dd in (d, e):
            dd.line(pts, fill=VIOLET, width=2)
    img = img.filter(ImageFilter.SMOOTH)
    img.save(f'{out}/crystal_atlas.png')
    emit.save(f'{out}/crystal_emissive.png')


if __name__ == '__main__':
    main(sys.argv[1])
