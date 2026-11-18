"""Tileable ground detail texture, art pass 8 (replaces the pass v2 output).

Same contract as before: one RGB image, each channel a greyscale detail pattern centred on mid-grey.
  R grass - dense blade strokes and small tufts (lit tips, shaded roots), homogeneous at metre scale
  G dirt  - soil grain, pebbles and stones lit from the game's sun side, small dry cracks
  B rock  - broken stone: angular plates with bevelled fracture lines, grit, lichen specks
Everything is built in the frequency domain or on a wrapped grid, so it tiles without seams.

How the game reads it (src/render/renderer.ts): the fine lookup tiles every 7 m and weights the
channels by ground kind; a broad lookup of the same image every 44 m uses R for light / dark meadow
patches and G (positive half) for a warm dry tint. So:
  - mid frequencies (features 0.3 - 2 m at the fine scale) are kept weak and even: a distinctive
    blob there repeats every 7 m and is what makes a tiled field obvious from the game camera;
  - the lowest frequencies (1 - 3 cycles per tile) carry most of R and G's large-scale energy: at
    the broad scale they become 15 - 44 m meadow and dry patches, at the fine scale only a gentle
    undulation;
  - fine detail (blades, grit) is strong but statistically uniform, so mip-mapped at distance it
    averages to the same tone everywhere.

Usage:  python3 terrain_detail.py <out.jpg> [size]
"""
import sys

import numpy as np
from PIL import Image

N = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
K = N / 512.0
rng = np.random.default_rng(23)
f1 = np.fft.fftfreq(N) * N
FX, FY = np.meshgrid(f1, f1)
FR = np.hypot(FX, FY)


def band(lo, hi, power=1.0, aniso=None, soft=0.0):
    """Unit-variance noise with energy between lo and hi cycles per tile (soft rolls the edges off)."""
    white = rng.standard_normal((N, N))
    if soft:
        mask = 1 / (1 + np.exp(-(FR - lo) / soft)) / (1 + np.exp((FR - hi) / soft))
    else:
        mask = ((FR >= lo) & (FR <= hi)).astype(float)
    mask = mask / np.maximum(FR, 1) ** power
    if aniso is not None:
        ang = np.arctan2(FY, FX)
        mask = mask * np.exp(-((np.sin(ang - aniso)) ** 2) / 0.08)
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * mask))
    return (out - out.mean()) / (out.std() + 1e-9)


def blur(a, sigma):
    f = np.fft.fftfreq(N)
    fx, fy = np.meshgrid(f, f)
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def shade(height, strength):
    """Light a height field from the game's sun side (wrapped gradients). The sun sits at +x, +z in
    the game; texture u runs along x and v along z, so light comes from +u, +v."""
    gx = np.roll(height, -1, 1) - np.roll(height, 1, 1)
    gy = np.roll(height, -1, 0) - np.roll(height, 1, 0)
    return (gx * 0.85 + gy * 0.53) * strength


def norm(a):
    return (a - a.mean()) / (a.std() + 1e-9)


def stones(count, rmin, rmax, flat=1.0):
    """Height field of rounded stones scattered on the wrapped tile."""
    h = np.zeros((N, N), np.float32)
    for _ in range(count):
        px, py, r = rng.random() * N, rng.random() * N, rng.uniform(rmin, rmax) * K
        e = rng.uniform(0.7, 1.35)
        ang = rng.uniform(0, np.pi)
        x0, x1 = int(px - r * 1.6 - 2), int(px + r * 1.6 + 3)
        y0, y1 = int(py - r * 1.6 - 2), int(py + r * 1.6 + 3)
        xs = np.arange(x0, x1) % N
        ys = np.arange(y0, y1) % N
        dx0 = (np.arange(x0, x1) - px)[None, :]
        dy0 = (np.arange(y0, y1) - py)[:, None]
        dx = (dx0 * np.cos(ang) + dy0 * np.sin(ang)) / e
        dy = (-dx0 * np.sin(ang) + dy0 * np.cos(ang)) * e
        th = np.arctan2(dy, dx)
        wob = 1 + sum(rng.uniform(0.04, 0.14) * np.sin(k * th + rng.uniform(0, 6.3)) for k in (2, 3, 5))
        d = np.sqrt(dx * dx + dy * dy) / r * wob
        facet = 1 + 0.25 * np.cos(rng.integers(3, 6) * th + rng.uniform(0, 6.3))   # angular, chipped top
        bump = np.clip(1 - d * d * facet, 0, 1) ** (0.5 * flat)
        sub = h[np.ix_(ys, xs)]
        h[np.ix_(ys, xs)] = np.maximum(sub, bump * rng.uniform(0.6, 1.0))
    return h


def strokes(count, length, width, lean=0.5):
    """Blade strokes: short tapered lines, root to tip, returned as (height, root mask)."""
    h = np.zeros((N, N), np.float32)
    for _ in range(count):
        px, py = rng.random() * N, rng.random() * N
        a = rng.normal(np.pi / 2, lean)
        ln = rng.uniform(0.45, 1.0) * length * K
        n = int(ln * 1.5) + 2
        t = np.linspace(0, 1, n)
        bend = rng.normal(0, 0.4)
        xs = px + np.cos(a + bend * t) * ln * t
        ys = py - np.sin(a + bend * t) * ln * t
        val = (0.35 + 0.65 * t) * rng.uniform(0.5, 1.0)          # tips stand higher (lit), roots low
        w = max(1, int(round(width * K)))
        for off in range(-w + 1, w):
            xi = (xs + off).astype(int) % N
            yi = ys.astype(int) % N
            np.maximum.at(h, (yi, xi), val * (1 - abs(off) / w))
    return h


def tufts(count, rmin, rmax):
    """Clump density: soft discs where blades bunch (each clump a little brighter, darker heart)."""
    h = np.zeros((N, N), np.float32)
    for _ in range(count):
        px, py, r = rng.random() * N, rng.random() * N, rng.uniform(rmin, rmax) * K
        x0, x1 = int(px - r - 2), int(px + r + 3)
        y0, y1 = int(py - r - 2), int(py + r + 3)
        xs = np.arange(x0, x1) % N
        ys = np.arange(y0, y1) % N
        d = np.sqrt(((np.arange(x0, x1) - px)[None, :]) ** 2 + ((np.arange(y0, y1) - py)[:, None]) ** 2) / r
        h[np.ix_(ys, xs)] += np.clip(1 - d, 0, 1) ** 1.5 * rng.uniform(0.5, 1.0)
    return h


def cells(count, squash=1.0, jitter=0.0):
    """Wrapped Voronoi: distance to the nearest cell border, and a random value per cell."""
    yy_, xx_ = np.mgrid[0:N, 0:N].astype(np.float32)
    if jitter:
        xx_ = xx_ + band(3, 10) * jitter * K
        yy_ = yy_ + band(3, 10) * jitter * K
    d1 = np.full((N, N), 1e9, np.float32)
    d2 = np.full((N, N), 1e9, np.float32)
    idv = np.zeros((N, N), np.float32)
    pts = rng.random((count, 2)) * N
    vals = rng.random(count)
    for (px, py), v in zip(pts, vals):
        dx = np.abs(xx_ - px)
        dx = np.minimum(dx, N - dx)
        dy = np.abs(yy_ - py)
        dy = np.minimum(dy, N - dy) * squash
        d = np.sqrt(dx * dx + dy * dy)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        idv = np.where(closer, v, idv)
        d1 = np.minimum(d1, d)
    return (d2 - d1) / K, idv


# ------------------------------------------------------------------ R: grass
blades = strokes(int(26000 * K * K / 4), 11, 1.0)
blades2 = strokes(int(12000 * K * K / 4), 6, 1.0, lean=0.9)
bl = np.maximum(blades, blades2 * 0.8)
clump = tufts(int(2200 * K * K / 4), 7, 18)
clump = blur(clump, 1.0 * K)
gaps = stones(int(500 * K * K / 4), 3, 9, 0.6)       # bare soil showing between tufts
gaps = blur(gaps, 1.5 * K)
low_r = band(1, 3.2, 0.0, soft=0.4)                 # meadow patches at the broad scale
grass = (0.5
         + 0.035 * low_r
         + 0.012 * band(4, 24, 0.6, soft=1.5)         # weak, even mid band
         + 0.06 * norm(clump - blur(clump, 10 * K)) + shade(blur(clump, 2.0 * K), 0.6)
         - 0.07 * norm(gaps) * (gaps > 0.05)
         + 0.15 * norm(bl) * 0.6 + shade(blur(bl, 0.6 * K), 0.35)
         - 0.05 * norm(blur(bl, 3 * K)) * (bl < 0.05)   # gaps between blades read as shaded soil
         + 0.03 * band(120 * K, 256 * K, 0.0))
# ------------------------------------------------------------------ G: dirt
s_h = np.maximum.reduce([stones(40, 5, 10, 1.2), stones(750, 2.2, 4.5), stones(1800, 0.9, 2.0) * 0.65])
grain = band(80 * K, 250 * K, 0.0) * 0.035
ck, _ = cells(70, 1.0, 9.0)
crack = np.clip(1 - ck / 1.0, 0, 1) * (band(2, 6) > 0.4)
low_g = band(1, 3.2, 0.0, soft=0.4)                  # dry patches at the broad scale
dirt = (0.48 + 0.055 * low_g + 0.02 * band(5, 24, 0.5, soft=1.5) + grain
        + 0.15 * s_h + shade(blur(s_h, 0.7 * K), 1.15)
        - 0.08 * blur(np.clip(s_h * 4, 0, 1), 2.0 * K) * (s_h < 0.04)   # contact shadow round stones
        - 0.05 * crack)
# ------------------------------------------------------------------ B: rock
e1, id1 = cells(34, 1.35, 3.0)
e2, _ = cells(150, 1.15, 1.5)
plate = (id1 - 0.5) * 0.08                         # each broken plate a slightly different tone
frac = np.clip(1 - e1 / 3.0, 0, 1) + 0.35 * np.clip(1 - e2 / 1.3, 0, 1) * (band(2, 5) > -0.1)
frac = np.clip(frac, 0, 1)
tilt = band(6, 20, 0.8) * 0.5
r_h = plate * 4 + tilt + band(30, 90, 0.4) * 0.25 - frac * 1.6
lichen = np.clip((band(30 * K, 90 * K, 0.3) - 1.4) * 2, 0, 1) * (band(2, 6) > 0.0)
rock = (0.5 + plate + 0.05 * tilt + 0.05 * band(10, 40, 0.5) + shade(blur(r_h, 0.8 * K), 0.22) - 0.2 * frac
        + band(100 * K, 250 * K, 0.1) * 0.04 + 0.1 * lichen + 0.03 * band(1, 3, 0.0))

img = np.stack([grass, dirt, rock], axis=-1)
img = 0.5 + (img - img.mean(axis=(0, 1), keepdims=True))   # centre each channel exactly on mid-grey
img = np.clip(img, 0, 1)
Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(sys.argv[1], quality=90)
print('mean', img.reshape(-1, 3).mean(0), 'std', img.reshape(-1, 3).std(0))
