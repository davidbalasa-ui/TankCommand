"""Third faction (mushroom tanks) texture atlas, 512x512, painted in code. Working name: Myco.
  wood   (  0,  0)-(256,256)  pale fungus wood with carved grain (painterly strokes)
  cap    (256,  0)-(512,256)  red cap with white spots
  gill   (  0,256)-(256,384)  warm glowing gill lines (emissive)
  track  (256,256)-(512,384)  dark segmented tread with gold rivets
  wheel  (  0,384)-(128,512)  gold spoked wheel face
  banner (128,384)-(256,512)  red banner with a pale mushroom crest
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
    # Wood: pale cream with long vertical grain strokes and darker carved lines.
    d.rectangle((0, 0, 255, 255), fill=(214, 196, 160))
    strokes(d, (0, 0, 256, 256), rng, (225, 205, 165), 900, 30, 3, angle=math.pi / 2)
    strokes(d, (0, 0, 256, 256), rng, (150, 120, 85), 160, 40, 2, angle=math.pi / 2)
    for x in range(0, 256, 32):
        d.line((x, 0, x + rng.uniform(-8, 8), 255), fill=(120, 95, 65), width=2)
    # Cap: red with white spots and stroke texture.
    d.rectangle((256, 0, 511, 255), fill=(196, 50, 36))
    strokes(d, (256, 0, 512, 256), rng, (205, 60, 40), 700, 18, 3)
    for _ in range(22):
        cx, cy, r = rng.uniform(270, 500), rng.uniform(14, 242), rng.uniform(8, 18)
        d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=(245, 236, 215))
        d.ellipse((cx - r * 0.5, cy - r * 0.4, cx + r * 0.3, cy), fill=(255, 250, 238))
    # Gill: radiating warm lines (glow).
    for dd, k in ((d, 1.0), (e, 0.85)):
        dd.rectangle((0, 256, 255, 383), fill=(int(210 * k), int(120 * k), int(45 * k)))
        for x in range(0, 256, 7):
            dd.line((x, 256, 128 + (x - 128) * 0.3, 383), fill=(int(255 * k), int(225 * k), int(140 * k)), width=3)
    # Track: dark plates with gold rivets.
    d.rectangle((256, 256, 511, 383), fill=(48, 42, 40))
    for x in range(256, 512, 24):
        d.rectangle((x + 2, 262, x + 20, 377), fill=(70, 62, 56))
        d.ellipse((x + 8, 314, x + 14, 320), fill=GOLD)
    # Wheel: gold rim and spokes.
    cx, cy = 64, 448
    d.rectangle((0, 384, 127, 511), fill=(90, 60, 25))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(205, 150, 50))
    d.ellipse((cx - 48, cy - 48, cx + 48, cy + 48), fill=(120, 80, 30))
    for i in range(10):
        a = i * math.pi / 5
        d.line((cx, cy, cx + 48 * math.cos(a), cy + 48 * math.sin(a)), fill=(240, 190, 80), width=5)
    d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(250, 210, 110))
    for dd in (e,):
        dd.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(150, 100, 30))
    # Banner: red cloth, gold border, pale mushroom crest.
    d.rectangle((128, 384, 255, 511), fill=(170, 30, 30))
    d.rectangle((132, 388, 251, 507), outline=GOLD, width=3)
    d.pieslice((160, 410, 224, 470), 180, 360, fill=(240, 228, 200))
    d.rectangle((185, 440, 199, 490), fill=(240, 228, 200))
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
