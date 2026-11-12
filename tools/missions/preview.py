"""Draws mission dumps (tools/missions/dump.ts) as top-down maps: height shading, blocked cells
red, hover-only cells cyan, water blue, deposits, units, structures and goal areas.
Usage: python3 tools/missions/preview.py <dump dir> <out.png>"""
import json, sys, glob, math
from PIL import Image, ImageDraw

S = 3  # pixels per metre
def draw(d):
    size, cols = d['size'], d['cols']
    cell = size / cols
    img = Image.new('RGB', (int(size * S), int(size * S) + 18), (20, 20, 20))
    g = ImageDraw.Draw(img)
    hs = d['heights']; stride = cols + 1
    lo, hi = min(hs), max(hs)
    blocked, hover, water = set(d['blocked']), set(d['hoverOnly']), set(d['water'])
    for cz in range(cols):
        for cx in range(cols):
            h = hs[cz * stride + cx]
            v = int(60 + 150 * (h - lo) / max(1e-6, hi - lo))
            c = (v // 2, v, v // 2)
            i = cz * cols + cx
            if i in water: c = (30, 60, 160)
            elif i in hover: c = (40, 170, 190)
            elif i in blocked: c = (150, 50, 40)
            x0, y0 = cx * cell * S, cz * cell * S
            g.rectangle([x0, y0, x0 + cell * S - 1, y0 + cell * S - 1], fill=c)
    P = lambda x, z: ((x + size / 2) * S, (z + size / 2) * S)
    for a in d['goal']:
        x, y = P(a['x'], a['z']); r = a['r'] * S
        col = (255, 255, 0) if a['side'] == 1 else (255, 140, 0) if a['side'] > 0 else (255, 0, 255)
        g.ellipse([x - r, y - r, x + r, y + r], outline=col, width=2)
    for dp in d['deposits']:
        x, y = P(dp['x'], dp['z'])
        g.rectangle([x - 4, y - 4, x + 4, y + 4], fill=(240, 120, 220) if dp['kind'] == 'ore' else (200, 200, 220))
    for s in d['structures']:
        x, y = P(s['x'], s['z'])
        col = (60, 140, 255) if s['owner'] == 1 else (255, 60, 60) if s['owner'] == 2 else (200, 200, 60)
        g.rectangle([x - 7, y - 7, x + 7, y + 7], outline=col, width=3)
    for u in d['units']:
        x, y = P(u['x'], u['z'])
        col = (60, 140, 255) if u['owner'] == 1 else (255, 60, 60) if u['owner'] == 2 else (200, 200, 60)
        g.ellipse([x - 3, y - 3, x + 3, y + 3], fill=col)
    g.text((4, size * S + 3), f"{d['id']}  {d['title']}", fill=(255, 255, 255))
    return img

files = sorted(glob.glob(sys.argv[1] + '/*.json'))
ims = [draw(json.load(open(f))) for f in files]
n = len(ims); cols = min(4, n); rows = math.ceil(n / cols)
w, h = ims[0].size
sheet = Image.new('RGB', (w * cols, h * rows), (0, 0, 0))
for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(sys.argv[2])
