"""The Shard: the end-game rift crystal and its spires. Black glass crystal with a violet-white inner
light, heaved up through broken obsidian. Centre at the origin, ground at z = 0. The floating heart
is its own node ('Core') so the game can bob and spin it and fire the beam from its tip."""
import math
import random

import forge as F
from forge import rock, tube
from props import cluster, crystal

ASSETS = {}
GEM, STONE = 'gem_shard', 'obsidian'


def asset(path, label, size=1024):
    def deco(fn):
        def run(glb, render, report):
            F.begin('nature')
            kw = fn() or {}
            F.finish(kw.pop('name'), glb, render=render, report=report, label=label, size=kw.pop('size', size),
                     ao_floor=0.45, **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='structures')
        return run
    return deco


def heart(c, h, r, sides=6):
    """Double-pointed crystal hanging in the air, long point down."""
    return tube((c[0], c[1], c[2] - h * 0.6), (c[0], c[1], c[2] + h * 0.4),
                [(0, r * 0.03), (0.42, r * 0.8), (0.62, r), (0.8, r * 0.7), (1, r * 0.04)], sides, 'gem_heart', sharp=15)


def splinters(c, n, ring_r, h, r, rnd, spin=0.0):
    """Small loose crystals hanging round the heart, each tipped a different way."""
    for k in range(n):
        a = math.radians(spin + 360.0 * k / n + rnd.uniform(-12, 12))
        p = (c[0] + math.cos(a) * ring_r, c[1] + math.sin(a) * ring_r, c[2] + rnd.uniform(-0.5, 0.5) * h)
        o = heart(p, h * rnd.uniform(0.7, 1.1), r * rnd.uniform(0.7, 1.0), sides=5)
        F.rot(o, 'X', rnd.uniform(-25, 25), about=p)
        F.rot(o, 'Y', rnd.uniform(-25, 25), about=p)


def upheaval(R, n, rnd, seed, size=1.0):
    """Ring of obsidian slabs levered up and outward by whatever came through the ground."""
    for k in range(n):
        yaw = 360.0 * k / n + rnd.uniform(-14, 14)
        a = math.radians(yaw)
        d = R * rnd.uniform(0.82, 1.0)
        r = size * rnd.uniform(0.75, 1.15)
        p = (d, 0, r * 0.22)
        o = rock(p, r, STONE, sq=(1.15, 0.8, 0.32), seed=seed + k, cuts=4)
        F.rot(o, 'Y', -rnd.uniform(14, 34), about=p)
        F.rot(o, 'Z', yaw)


@asset('structures/shard_core.glb', 'Shard core (rift crystal)')
def shard_core():
    rnd = random.Random(31)
    rock((0, 0, 0.35), 2.6, STONE, sq=(1.1, 1.0, 0.3), seed=300, sub=3, floor=-0.05)
    upheaval(3.2, 9, rnd, 310, 1.25)
    # Crown of great leaning columns round an open throat.
    for k, (h, r, lean) in enumerate(((7.4, 0.82, 17), (5.6, 0.7, 24), (6.6, 0.76, 20), (4.6, 0.66, 28), (6.0, 0.72, 22))):
        yaw = 72.0 * k + rnd.uniform(-10, 10)
        a = math.radians(yaw)
        base = (math.cos(a) * 1.25, math.sin(a) * 1.25, 0.3)
        crystal(base, h, r, yaw, lean, GEM)
        b2 = (math.cos(a + 0.5) * 1.9, math.sin(a + 0.5) * 1.9, 0.25)
        crystal(b2, h * 0.42, r * 0.55, yaw + 28, lean + 14, GEM)
    for k in range(6):   # sprays breaking through between the slabs
        a = math.radians(60.0 * k + 30 + rnd.uniform(-15, 15))
        cluster((math.cos(a) * 3.1, math.sin(a) * 3.1, 0.05), rnd.randint(2, 3), rnd.uniform(0.9, 1.5), rnd.uniform(0.18, 0.26), GEM, rnd, lean=36)
    tz = 6.0
    with F.group('Core'):
        heart((0, 0, tz), 3.6, 0.95)
        splinters((0, 0, tz + 0.2), 5, 1.75, 0.95, 0.2, rnd)
    return dict(name='ShardCore', pivot=('Core', (0, 0, tz)))


@asset('structures/shard_spire.glb', 'Shard spire (crystal tower)', size=512)
def shard_spire():
    rnd = random.Random(47)
    rock((0, 0, 0.25), 1.35, STONE, sq=(1.1, 1.0, 0.32), seed=340, floor=-0.05)
    upheaval(1.5, 6, rnd, 350, 0.7)
    for k, (h, r, lean) in enumerate(((4.4, 0.42, 9), (3.0, 0.36, 21), (2.3, 0.32, 27))):
        yaw = 120.0 * k + rnd.uniform(-12, 12)
        a = math.radians(yaw)
        crystal((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.2), h, r, yaw, lean, 'gem_shard_s')
    for k in range(3):
        a = math.radians(120.0 * k + 60)
        cluster((math.cos(a) * 1.35, math.sin(a) * 1.35, 0.05), 2, rnd.uniform(0.6, 0.9), 0.16, 'gem_shard_s', rnd, lean=36)
    tz = 4.9
    with F.group('Core'):
        heart((0.15, 0, tz), 1.5, 0.4)
        splinters((0.15, 0, tz), 3, 0.75, 0.5, 0.11, rnd, spin=40)
    return dict(name='ShardSpire', pivot=('Core', (0.15, 0, tz)))
