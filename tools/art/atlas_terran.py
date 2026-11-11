"""Terran (human) faction texture atlas, 512x512, painted in code.

Layout (pixels, origin top-left):
  hull    (  0,  0)-(256,256)  dark armour plates, panel lines, cyan seams, orange chevrons
  turret  (256,  0)-(512,256)  same family, larger plates and a stencil
  track   (  0,256)-(256,384)  tread links
  barrel  (256,256)-(512,384)  gunmetal with a cyan coil band in the middle third
  glow    (  0,384)-(128,512)  solid cyan (emissive)
  amber   (128,384)-(256,512)  solid orange (emissive)
  dark    (256,384)-(512,512)  plain dark metal (undersides, wheels)
Writes <out>/terran_atlas.png (base colour) and <out>/terran_emissive.png.
Usage: python3 atlas_terran.py <outdir>
"""
import random
import sys
from PIL import Image, ImageDraw

S = 512
CYAN = (60, 220, 255)
AMBER = (255, 150, 40)
TILES = {
    'hull': (0, 0, 256, 256),
    'turret': (256, 0, 512, 256),
    'track': (0, 256, 256, 384),
    'barrel': (256, 256, 512, 384),
    'glow': (0, 384, 128, 512),
    'amber': (128, 384, 256, 512),
    'dark': (256, 384, 512, 512),
}


def plates(draw, emit, box, rng, base, size_range, stencil=False):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=base)
    # Plates: slightly varied tone, dark seams, highlight on the top edge (baked light).
    y = y0
    while y < y1:
        h = rng.randint(*size_range)
        x = x0
        while x < x1:
            w = rng.randint(size_range[0], size_range[1] * 2)
            tone = rng.randint(-10, 14)
            c = tuple(max(0, min(255, v + tone)) for v in base)
            r = (x + 1, y + 1, min(x + w, x1) - 2, min(y + h, y1) - 2)
            if r[2] > r[0] and r[3] > r[1]:
                draw.rectangle(r, fill=c)
                draw.line((r[0], r[1], r[2], r[1]), fill=tuple(min(255, v + 40) for v in c), width=2)
                draw.line((r[0], r[3], r[2], r[3]), fill=(14, 15, 18), width=2)
                draw.line((r[2], r[1], r[2], r[3]), fill=(14, 15, 18))
                if rng.random() < 0.35:  # bolts
                    for bx, by in ((r[0] + 3, r[1] + 3), (r[2] - 3, r[1] + 3), (r[0] + 3, r[3] - 3), (r[2] - 3, r[3] - 3)):
                        draw.point((bx, by), fill=(90, 96, 104))
            x += w
        y += h
    # Cyan seams and orange chevrons: these glow.
    for _ in range(4):
        sx = rng.randint(x0 + 10, x1 - 60)
        sy = rng.randint(y0 + 10, y1 - 10)
        ln = rng.randint(30, 70)
        for d in (draw, emit):
            d.line((sx, sy, sx + ln, sy), fill=CYAN, width=2)
            d.line((sx + ln, sy, sx + ln + 8, sy - 8), fill=CYAN, width=2)
    for _ in range(3):
        cx = rng.randint(x0 + 12, x1 - 24)
        cy = rng.randint(y0 + 12, y1 - 16)
        for d in (draw, emit):
            d.line((cx, cy, cx + 6, cy + 6, cx + 12, cy), fill=AMBER, width=2)
    if stencil:
        draw.text((x0 + 18, y1 - 30), 'TC-07', fill=(150, 160, 170))


def main(out):
    rng = random.Random(7)
    img = Image.new('RGB', (S, S), (20, 22, 26))
    emit = Image.new('RGB', (S, S), (0, 0, 0))
    d = ImageDraw.Draw(img)
    e = ImageDraw.Draw(emit)
    plates(d, e, TILES['hull'], rng, (46, 50, 58), (24, 56))
    plates(d, e, TILES['turret'], rng, (52, 56, 64), (32, 72), stencil=True)
    x0, y0, x1, y1 = TILES['track']
    d.rectangle(TILES['track'], fill=(24, 24, 26))
    for y in range(y0, y1, 12):
        d.rectangle((x0, y, x1, y + 7), fill=(44, 44, 46))
        d.line((x0, y, x1, y), fill=(70, 70, 72))
    x0, y0, x1, y1 = TILES['barrel']
    for x in range(x0, x1):
        t = (x - x0) / (x1 - x0)
        v = int(40 + 30 * (1 - abs(t - 0.5) * 2))
        d.line((x, y0, x, y1), fill=(v, v + 3, v + 8))
    third = (y1 - y0) // 3
    for y in range(y0 + third, y0 + 2 * third, 6):
        for dd in (d, e):
            dd.rectangle((x0, y, x1, y + 2), fill=CYAN)
    d.rectangle(TILES['glow'], fill=CYAN)
    e.rectangle(TILES['glow'], fill=CYAN)
    d.rectangle(TILES['amber'], fill=AMBER)
    e.rectangle(TILES['amber'], fill=AMBER)
    d.rectangle(TILES['dark'], fill=(26, 28, 32))
    img.save(f'{out}/terran_atlas.png')
    emit.save(f'{out}/terran_emissive.png')


if __name__ == '__main__':
    main(sys.argv[1])
