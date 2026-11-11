"""Kesh (alien) faction texture atlas, 512x512, painted in code. Same tile layout as Terran:
  shell  (  0,  0)-(256,256)  silver-bronze with etched filigree and gold veins
  fin    (256,  0)-(512,256)  darker bronze, etched, gold edge
  under  (  0,256)-(256,384)  dark underside with a gold hover glow ring
  barrel (256,256)-(512,384)  dark metal with glowing gold slots
  glow   (  0,384)-(128,512)  solid gold (emissive)
  core   (128,384)-(256,512)  radial white-gold orb (emissive)
  dark   (256,384)-(512,512)  dark bronze
Usage: python3 atlas_kesh.py <outdir>  -> kesh_atlas.png, kesh_emissive.png
"""
import math
import random
import sys
from PIL import Image, ImageDraw, ImageFilter

S = 512
GOLD = (255, 196, 70)


def etched(draw, emit, box, rng, base, veins=6):
    x0, y0, x1, y1 = box
    # Brushed metal gradient.
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        k = 1.12 - 0.35 * t
        draw.line((x0, y, x1, y), fill=tuple(int(min(255, c * k)) for c in base))
    # Etched filigree: many short dark curves (engraving), a few gold veins that glow.
    for _ in range(140):
        cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(6, 26)
        a0 = rng.uniform(0, 360)
        draw.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + rng.uniform(60, 200),
                 fill=tuple(int(c * 0.55) for c in base), width=1)
    for _ in range(veins):
        pts = []
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        for _ in range(8):
            pts.append((x, y))
            x = min(x1, max(x0, x + rng.uniform(-22, 22)))
            y = min(y1, max(y0, y + rng.uniform(-22, 22)))
        for d in (draw, emit):
            d.line(pts, fill=GOLD, width=1)


def main(out):
    rng = random.Random(11)
    img = Image.new('RGB', (S, S), (30, 26, 22))
    emit = Image.new('RGB', (S, S), (0, 0, 0))
    d, e = ImageDraw.Draw(img), ImageDraw.Draw(emit)
    etched(d, e, (0, 0, 256, 256), rng, (178, 168, 160), veins=7)
    etched(d, e, (256, 0, 512, 256), rng, (128, 104, 80), veins=4)
    for dd in (d, e):
        dd.rectangle((256, 0, 512, 6), fill=GOLD)
        dd.rectangle((256, 250, 512, 256), fill=GOLD)
    d.rectangle((0, 256, 256, 384), fill=(34, 30, 28))
    for dd in (d, e):
        dd.ellipse((40, 268, 216, 372), outline=GOLD, width=5)
    x0, y0, x1, y1 = 256, 256, 512, 384
    for x in range(x0, x1):
        t = (x - x0) / (x1 - x0)
        v = int(38 + 26 * (1 - abs(t - 0.5) * 2))
        d.line((x, y0, x, y1), fill=(v + 6, v, v - 6))
    for y in range(y0 + 20, y1 - 10, 22):
        for dd in (d, e):
            dd.rectangle((x0 + 70, y, x1 - 70, y + 6), fill=GOLD)
    d.rectangle((0, 384, 128, 512), fill=GOLD)
    e.rectangle((0, 384, 128, 512), fill=GOLD)
    for r in range(64, 0, -1):
        t = r / 64
        c = (255, int(255 - 70 * t), int(230 - 200 * t))
        for dd in (d, e):
            dd.ellipse((192 - r, 448 - r, 192 + r, 448 + r), fill=c)
    d.rectangle((256, 384, 512, 512), fill=(70, 56, 44))
    img = img.filter(ImageFilter.SMOOTH)
    img.save(f'{out}/kesh_atlas.png')
    emit.save(f'{out}/kesh_emissive.png')


if __name__ == '__main__':
    main(sys.argv[1])
