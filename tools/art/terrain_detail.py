"""Tileable ground detail texture for the terrain shader.

One 512x512 RGB image, each channel a greyscale detail pattern centred on mid-grey:
  R  grass  - fine blade speckle over soft clumps
  G  dirt   - pebbles and small stones over patchy soil
  B  rock   - cracks and grainy strata
The terrain shader tiles it across the map and multiplies the vertex colour by whichever channel
fits the ground there, so one small image textures every surface. Every pattern is built in the
frequency domain or on a wrapped grid, so the image tiles without seams.

Usage:  python3 terrain_detail.py <out.jpg>
"""
import sys

import numpy as np
from PIL import Image

N = 512
rng = np.random.default_rng(7)


def band(lo, hi, power=1.0):
    """Tileable noise containing only spatial frequencies between lo and hi cycles per tile."""
    white = rng.standard_normal((N, N))
    f = np.fft.fftfreq(N) * N
    r = np.hypot(*np.meshgrid(f, f))
    mask = ((r >= lo) & (r <= hi)) / np.maximum(r, 1) ** power
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * mask))
    return (out - out.mean()) / (out.std() + 1e-9)


def wrapped_cells(count):
    """Distance to the nearest of `count` random points on a wrapped tile, and to the second nearest."""
    pts = rng.random((count, 2)) * N
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    d1 = np.full((N, N), 1e9, np.float32)
    d2 = np.full((N, N), 1e9, np.float32)
    for px, py in pts:
        dx = np.abs(xx - px); dx = np.minimum(dx, N - dx)
        dy = np.abs(yy - py); dy = np.minimum(dy, N - dy)
        d = np.hypot(dx, dy)
        d2 = np.where(d < d1, d1, np.minimum(d2, d))
        d1 = np.minimum(d1, d)
    return d1, d2


def norm(a, lo=0.0, hi=1.0):
    a = (a - a.min()) / (a.max() - a.min() + 1e-9)
    return lo + a * (hi - lo)


# Grass: soft clumps, then fine blade speckle stretched a little so it reads as blades.
clumps = band(3, 10)
blades = band(60, 200, 0.3)
grass = 0.5 + 0.11 * clumps + 0.09 * blades + 0.05 * band(20, 50)

# Dirt: patchy soil with pebbles (small bright-topped stones with a dark rim).
soil = band(4, 16) * 0.08 + band(30, 90, 0.5) * 0.05
d1, d2 = wrapped_cells(260)
pebble = np.clip(1.0 - d1 / 7.0, 0, 1) ** 1.5
rim = np.clip(1.0 - np.abs(d1 - 7.0) / 1.5, 0, 1)
dirt = 0.5 + soil + 0.16 * pebble - 0.1 * rim

# Rock: grainy strata with dark cracks along cell edges, warped so they wander.
grain = band(80, 220, 0.2) * 0.05
strata = np.sin((np.mgrid[0:N, 0:N][0] / N) * 2 * np.pi * 9 + band(2, 6) * 1.5) * 0.06
c1, c2 = wrapped_cells(40)
crack = np.clip(1.0 - (c2 - c1) / 2.5, 0, 1)
patch = band(2, 8)
rock = 0.52 + grain + strata + band(6, 20) * 0.07 - 0.28 * crack * (patch > -0.2)

img = np.stack([np.clip(grass, 0, 1), np.clip(dirt, 0, 1), np.clip(rock, 0, 1)], axis=-1)
Image.fromarray((img * 255).astype(np.uint8)).save(sys.argv[1], quality=88)
print('mean', img.reshape(-1, 3).mean(0))
