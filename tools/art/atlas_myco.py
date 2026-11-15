"""Third faction (mushroom tanks) texture atlas, 512x512, painted in code. Working name: Myco.
  flesh  (  0,  0)-(256,256)  pale cream fungal skin with soft fibres (painterly strokes)
  cap    (256,  0)-(512,256)  red cap with white spots
  gill   (  0,256)-(256,384)  warm glowing gill lines (emissive)
  myc    (256,256)-(512,384)  root bark: lengthwise fibres, cream at the stem end to soil brown at tips
  bulb   (  0,384)-(128,512)  glowing gold spore sac (emissive)
  ruffle (128,384)-(256,512)  purple bracket fungus with growth rings
  moss   (256,384)-(384,512)  green vine and moss
  spore  (384,384)-(512,512)  gold glow (emissive)
Usage: python3 atlas_myco.py <outdir>  -> myco_atlas.png, myco_emissive.png
"""
import math
import random
import sys
from PIL import Image, ImageDraw, ImageFilter

S = 512
GOLD = (255, 200, 80)


def strokes(d, box, rng, base, n, length, width, jitter=26, angle=None):
    """Painterly short brush strokes."""
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        a = angle if angle is not None else rng.uniform(0, math.pi)
        a += rng.uniform(-0.25, 0.25)
        L = rng.uniform(length * 0.5, length)
        c = tuple(max(0, min(255, int(v + rng.uniform(-jitter, jitter)))) for v in base)
        d.line((x, y, x + L * math.cos(a), y + L * math.sin(a)), fill=c, width=width)


def main(out):
    rng = random.Random(21)
    img = Image.new('RGB', (S, S), (0, 0, 0))
    emit = Image.new('RGB', (S, S), (0, 0, 0))
    d, e = ImageDraw.Draw(img), ImageDraw.Draw(emit)
    # Flesh: pale cream fungal skin, soft fibrous streaks, faint pink blush (fully organic, no carving).
    d.rectangle((0, 0, 255, 255), fill=(190, 170, 140))
    strokes(d, (0, 0, 256, 256), rng, (200, 182, 152), 1100, 26, 3, jitter=16, angle=math.pi / 2)
    strokes(d, (0, 0, 256, 256), rng, (150, 118, 92), 320, 30, 3, jitter=14, angle=math.pi / 2)
    strokes(d, (0, 0, 256, 256), rng, (110, 88, 62), 160, 40, 2, jitter=10, angle=math.pi / 2)
    # Cap: red with white spots and stroke texture.
    # Deep, weathered red; warts are small, irregular and off-white (not cartoon polka dots).
    d.rectangle((256, 0, 511, 255), fill=(132, 34, 26))
    strokes(d, (256, 0, 512, 256), rng, (150, 44, 32), 900, 18, 3, jitter=20)
    strokes(d, (256, 0, 512, 256), rng, (105, 28, 22), 110, 16, 2, jitter=10)
    # Warts: soft rounded flakes (irregular ellipses with a lighter centre), some in small clusters.
    for _ in range(46):
        cx, cy = rng.uniform(266, 502), rng.uniform(10, 246)
        for _ in range(rng.choice((1, 1, 2, 3))):
            x, y = cx + rng.uniform(-9, 9), cy + rng.uniform(-9, 9)
            rx, ry = rng.uniform(3, 8), rng.uniform(3, 7)
            d.ellipse((x - rx, y - ry, x + rx, y + ry), fill=(186, 170, 140))
            d.ellipse((x - rx * 0.6, y - ry * 0.6, x + rx * 0.5, y + ry * 0.5), fill=(222, 210, 182))
    # Gill: radiating warm lines (glow).
    # Emission is strong on the gill ridges and weak between them, so the gill folds still read in depth.
    for dd, kb, kl in ((d, 1.0, 1.0), (e, 0.25, 0.85)):
        dd.rectangle((0, 256, 255, 383), fill=(int(190 * kb), int(95 * kb), int(35 * kb)))
        for x in range(0, 256, 7):
            dd.line((x, 256, 128 + (x - 128) * 0.3, 383), fill=(int(255 * kl), int(185 * kl), int(70 * kl)), width=3)
    # Root bark: lengthwise fibres, pale cream at the stem end (bottom of tile) fading to soil-stained
    # brown at the tips (top of tile), so roots read as the stem splitting into the earth.
    for yy in range(256, 384):
        t = (383 - yy) / 127  # 0 at stem end, 1 at tip
        c = tuple(int(a + (b - a) * t ** 0.8) for a, b in zip((182, 160, 128), (62, 44, 30)))
        d.line((256, yy, 511, yy), fill=c)
    for _ in range(900):
        x, y = rng.uniform(256, 512), rng.uniform(256, 384)
        t = (383 - y) / 127
        base = tuple(int(a + (b - a) * t) for a, b in zip((205, 185, 150), (85, 62, 42)))
        L = rng.uniform(10, 30)
        c = tuple(max(0, min(255, int(v + rng.uniform(-18, 18)))) for v in base)
        d.line((x, y, x + rng.uniform(-1.5, 1.5), y + L), fill=c, width=2)
    strokes(d, (256, 256, 512, 384), rng, (40, 28, 18), 260, 26, 2, jitter=8, angle=math.pi / 2)
    # Bulb: glowing gold spore sac (emissive), with soft rings.
    for r in range(64, 0, -2):
        t = r / 64
        c = (255, int(230 - 90 * t), int(150 - 120 * t))
        for dd in (d, e):
            dd.ellipse((64 - r, 448 - r, 64 + r, 448 + r), fill=c)
    # Ruffle: purple bracket fungus with pale growth rings.
    d.rectangle((128, 384, 255, 511), fill=(120, 70, 150))
    for k in range(8):
        y = 390 + k * 15
        d.arc((110, y - 30, 275, y + 30), 0, 180, fill=(200, 170, 220), width=2)
    strokes(d, (128, 384, 256, 512), rng, (140, 85, 170), 200, 14, 2, jitter=18)
    # Moss.
    d.rectangle((256, 384, 383, 511), fill=(60, 110, 40))
    strokes(d, (256, 384, 384, 512), rng, (90, 150, 50), 300, 10, 2)
    # Spore gold.
    for dd in (d, e):
        dd.rectangle((384, 384, 511, 511), fill=GOLD)
    img = img.filter(ImageFilter.SMOOTH)
    img.save(f'{out}/myco_atlas.png')
    emit.save(f'{out}/myco_emissive.png')


if __name__ == '__main__':
    main(sys.argv[1])
