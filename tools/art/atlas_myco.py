"""Third faction (mushroom tanks) texture atlas, 512x512, painted in code. Working name: Myco.
  flesh  (  0,  0)-(256,256)  pale cream fungal skin with soft fibres (painterly strokes)
  cap    (256,  0)-(512,256)  red cap with white spots
  gill   (  0,256)-(256,384)  warm glowing gill lines (emissive)
  myc    (256,256)-(512,384)  mycelium: pale root threads on dark brown
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
    d.rectangle((0, 0, 255, 255), fill=(226, 212, 190))
    strokes(d, (0, 0, 256, 256), rng, (232, 218, 196), 1100, 26, 3, jitter=14, angle=math.pi / 2)
    strokes(d, (0, 0, 256, 256), rng, (214, 180, 170), 220, 30, 3, jitter=12, angle=math.pi / 2)
    strokes(d, (0, 0, 256, 256), rng, (190, 170, 140), 120, 40, 1, jitter=10, angle=math.pi / 2)
    # Cap: red with white spots and stroke texture.
    d.rectangle((256, 0, 511, 255), fill=(196, 50, 36))
    strokes(d, (256, 0, 512, 256), rng, (205, 60, 40), 700, 18, 3)
    for _ in range(46):
        cx, cy, r = rng.uniform(268, 502), rng.uniform(12, 244), rng.uniform(9, 17)
        d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=(245, 236, 215))
        d.ellipse((cx - r * 0.5, cy - r * 0.4, cx + r * 0.3, cy), fill=(255, 250, 238))
    # Gill: radiating warm lines (glow).
    for dd, k in ((d, 1.0), (e, 0.85)):
        dd.rectangle((0, 256, 255, 383), fill=(int(210 * k), int(120 * k), int(45 * k)))
        for x in range(0, 256, 7):
            dd.line((x, 256, 128 + (x - 128) * 0.3, 383), fill=(int(255 * k), int(225 * k), int(140 * k)), width=3)
    # Mycelium: pale root threads over dark soil-brown.
    d.rectangle((256, 256, 511, 383), fill=(70, 52, 38))
    strokes(d, (256, 256, 512, 384), rng, (225, 215, 195), 500, 30, 1, jitter=20)
    strokes(d, (256, 256, 512, 384), rng, (160, 140, 110), 300, 20, 2, jitter=20)
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
