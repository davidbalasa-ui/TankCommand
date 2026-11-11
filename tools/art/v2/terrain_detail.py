"""Tileable ground detail texture, art pass v2 (replaces tools/art/terrain_detail.py's output).

Same contract as before: one RGB image, each channel a greyscale detail pattern centred on mid-grey.
  R grass - clumps, tufts and individual blade strokes with a light side and a shadow side
  G dirt  - soil patches, stones of three sizes lit from one side, small cracks
  B rock  - layered strata, bevelled cracks, grain and lichen specks
Everything is built in the frequency domain or on a wrapped grid, so it tiles without seams.

Usage:  python3 terrain_detail.py <out.jpg> [size]
"""
import sys

import numpy as np
from PIL import Image

N = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
K = N / 512.0
rng = np.random.default_rng(11)


def band(lo, hi, power=1.0, aniso=None):
    white = rng.standard_normal((N, N))
    f = np.fft.fftfreq(N) * N
    fx, fy = np.meshgrid(f, f)
    r = np.hypot(fx, fy)
    mask = ((r >= lo) & (r <= hi)) / np.maximum(r, 1) ** power
    if aniso is not None:   # keep only frequencies across the given direction (streaks along it)
        ang = np.arctan2(fy, fx)
        mask = mask * np.exp(-((np.sin(ang - aniso)) ** 2) / 0.08)
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * mask))
    return (out - out.mean()) / (out.std() + 1e-9)


def blur(a, sigma):
    f = np.fft.fftfreq(N)
    fx, fy = np.meshgrid(f, f)
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def shade(height, strength):
    """Light a height field from the upper left (wrapped gradients)."""
    gx = np.roll(height, -1, 1) - np.roll(height, 1, 1)
    gy = np.roll(height, -1, 0) - np.roll(height, 1, 0)
    return (-gx - gy) * strength


def stones(count, rmin, rmax):
    """Height field of rounded stones scattered on the wrapped tile."""
    h = np.zeros((N, N), np.float32)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    for _ in range(count):
        px, py, r = rng.random() * N, rng.random() * N, rng.uniform(rmin, rmax) * K
        e = rng.uniform(0.7, 1.3)
        x0, x1 = int(px - r * 1.5 - 2), int(px + r * 1.5 + 3)
        y0, y1 = int(py - r * 1.5 - 2), int(py + r * 1.5 + 3)
        xs = np.arange(x0, x1) % N
        ys = np.arange(y0, y1) % N
        dx = (np.arange(x0, x1) - px)[None, :] / e
        dy = (np.arange(y0, y1) - py)[:, None] * e
        d = np.sqrt(dx * dx + dy * dy) / r
        bump = np.clip(1 - d * d, 0, 1) ** 0.6
        sub = h[np.ix_(ys, xs)]
        h[np.ix_(ys, xs)] = np.maximum(sub, bump * rng.uniform(0.6, 1.0))
    return h


def strokes(count, length, width):
    """Blade strokes: short tapered lines, returned as a height field."""
    h = np.zeros((N, N), np.float32)
    for _ in range(count):
        px, py = rng.random() * N, rng.random() * N
        a = rng.normal(np.pi / 2, 0.5)
        ln = rng.uniform(0.5, 1.0) * length * K
        n = int(ln * 1.5) + 2
        t = np.linspace(0, 1, n)
        bend = rng.normal(0, 0.35)
        xs = px + np.cos(a + bend * t) * ln * t
        ys = py - np.sin(a + bend * t) * ln * t
        val = (1 - t) ** 0.5 * rng.uniform(0.5, 1.0)
        for off in range(-int(width * K), int(width * K) + 1):
            xi = (xs + off).astype(int) % N
            yi = ys.astype(int) % N
            np.maximum.at(h, (yi, xi), val * (1 - abs(off) / (width * K + 1)))
    return h


# Grass
g_h = strokes(int(9000 * K), 14, 1.0)
grass = 0.5 + 0.1 * band(2, 8) + 0.05 * band(12, 40) + 0.16 * (g_h - g_h.mean()) + shade(blur(g_h, 0.8 * K), 0.5) \
    + 0.035 * band(60 * K, 220 * K, 0.3, aniso=0.0)

# Dirt
s_h = np.maximum(stones(int(70), 6, 13), np.maximum(stones(int(420), 2.5, 5), stones(int(1400), 1.0, 2.0) * 0.6))
soil = band(3, 12) * 0.07 + band(25 * K, 90 * K, 0.5) * 0.045
ck = band(4, 14)
crack = np.clip(1 - np.abs(ck) / 0.035, 0, 1) * (band(2, 5) > 0.3)
dirt = 0.48 + soil + 0.13 * s_h + shade(blur(s_h, 0.7 * K), 0.9) - 0.1 * blur(np.clip(s_h * 4, 0, 1), 2.5 * K) * (s_h < 0.05) - 0.16 * crack

# Rock
yy = np.mgrid[0:N, 0:N][0] / N
warp = band(2, 5) * 1.3 + band(6, 14) * 0.35
lay = np.sin(yy * 2 * np.pi * 11 + warp)
strata_h = np.tanh(lay * 2.5) * 0.5
c = band(3, 9)
c2 = band(5, 16)
cr = np.clip(1 - np.abs(c) / 0.03, 0, 1) + np.clip(1 - np.abs(c2) / 0.025, 0, 1) * (band(2, 4) > 0.2)
cr = np.clip(cr, 0, 1)
r_h = strata_h * 0.5 + band(8, 30) * 0.25 - cr * 1.2
lichen = (band(20 * K, 60 * K, 0.4) > 1.6) * 0.07
rock = 0.52 + 0.05 * strata_h + shade(blur(r_h, 0.9 * K), 0.22) - 0.2 * cr + band(90 * K, 240 * K, 0.2) * 0.035 + band(4, 12) * 0.05 + lichen

img = np.stack([np.clip(grass, 0, 1), np.clip(dirt, 0, 1), np.clip(rock, 0, 1)], axis=-1)
img = 0.5 + (img - img.mean(axis=(0, 1), keepdims=True))   # centre each channel exactly on mid-grey
Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(sys.argv[1], quality=88)
print('mean', img.reshape(-1, 3).mean(0), 'std', img.reshape(-1, 3).std(0))
