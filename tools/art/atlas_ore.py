"""Ore deposit texture atlas, 512x512, painted in code (David's two ore references).
  pink   (  0,  0)-(256,256)  magenta crystal with a swirling glowing vortex (emissive)
  opal   (256,  0)-(512,256)  iridescent blue / violet / gold opal swirl (emissive)
  red    (  0,256)-(256,512)  rough red-brown rock
  wet    (256,256)-(512,512)  dark wet rock with glints
Usage: python3 atlas_ore.py <outdir>  -> ore_atlas.png, ore_emissive.png
"""
import math
import random
import sys
from PIL import Image, ImageDraw, ImageFilter


def swirl(img, emit, box, colours, glow, rng):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    px, pe = img.load(), emit.load()
    n = len(colours)
    for y in range(y0, y1):
        for x in range(x0, x1):
            dx, dy = (x - cx) / 128, (y - cy) / 128
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx) + 8.0 * r  # spiral arms
            t = (math.sin(a * 4) + 1) / 2
            band = ((math.sin(a * 4 + r * 14) + 1) / 2) ** 1.5
            i = int(band * (n - 1))
            c0, c1 = colours[i], colours[min(n - 1, i + 1)]
            f = band * (n - 1) - i
            c = [c0[k] + (c1[k] - c0[k]) * f for k in range(3)]
            core = max(0.0, 1 - r * 2.2) ** 2
            bright = 0.35 + 0.65 * t ** 2 + core
            col = tuple(min(255, int(v * bright + 255 * core * 0.6)) for v in c)
            px[x, y] = col
            pe[x, y] = tuple(int(v * glow) for v in col)
    d, e = ImageDraw.Draw(img), ImageDraw.Draw(emit)
    for _ in range(10):  # bright crackling veins
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        pts = [(x, y)]
        for _ in range(9):
            x = min(x1 - 1, max(x0, x + rng.uniform(-18, 18)))
            y = min(y1 - 1, max(y0, y + rng.uniform(-18, 18)))
            pts.append((x, y))
        for dd in (d, e):
            dd.line(pts, fill=(255, 235, 250), width=1)
    for _ in range(140):  # sparkles
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        for dd in (d, e):
            dd.point((x, y), fill=(255, 250, 255))


def rock(img, box, base, rng, glints=0):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=base)
    for _ in range(900):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(2, 9)
        k = rng.uniform(0.6, 1.3)
        d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(min(255, int(v * k)) for v in base))
    for _ in range(glints):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        d.point((x, y), fill=(200, 210, 255))


def main(out):
    rng = random.Random(13)
    img = Image.new('RGB', (512, 512))
    emit = Image.new('RGB', (512, 512))
    swirl(img, emit, (0, 0, 256, 256), [(70, 0, 45), (190, 15, 130), (255, 50, 180), (255, 160, 225)], 0.9, rng)
    swirl(img, emit, (256, 0, 512, 256), [(30, 40, 160), (60, 140, 255), (150, 70, 230), (255, 200, 80), (80, 220, 230)],
          0.7, rng)
    rock(img, (0, 256, 256, 512), (110, 45, 38), rng)
    rock(img, (256, 256, 512, 512), (34, 34, 42), rng, glints=260)
    img = img.filter(ImageFilter.SMOOTH)
    img.save(f'{out}/ore_atlas.png')
    emit.save(f'{out}/ore_emissive.png')


if __name__ == '__main__':
    main(sys.argv[1])
