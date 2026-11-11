"""Scenery and resource sites, art pass v2. One mesh each, origin at ground level in the centre."""
import math
import random

import forge as F
from forge import box, cyl, lathe, orb, rock, sweep, tube

ASSETS = {}


def asset(path, label, size=256):
    def deco(fn):
        def run(glb, render, report):
            F.begin('nature')
            kw = fn() or {}
            F.finish(kw.pop('name'), glb, render=render, report=report, label=label, size=kw.pop('size', size),
                     single=True, ao_floor=0.45, **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='props')
        return run
    return deco


@asset('props/boulder.glb', 'Boulder', size=512)
def boulder():
    rock((0, 0, 0.55), 1.2, 'rock', sq=(1.1, 0.95, 0.8), seed=3, sub=3, floor=-0.05)
    rock((0.75, -0.55, 0.3), 0.6, 'rock', sq=(1.1, 0.9, 0.75), seed=5, floor=-0.05)
    rock((-0.85, 0.5, 0.22), 0.42, 'rock', seed=8, floor=-0.05)
    return dict(name='Boulder')


@asset('props/rock_cluster.glb', 'Rock cluster', size=512)
def rock_cluster():
    rnd = random.Random(4)
    for i, (x, y, r) in enumerate(((0, 0, 0.85), (1.0, 0.45, 0.6), (-0.95, 0.5, 0.52), (0.3, -0.95, 0.5), (-0.7, -0.75, 0.36), (1.35, -0.6, 0.3))):
        rock((x, y, r * 0.5), r, 'rock', sq=(1.0, 0.9, 0.85 + rnd.random() * 0.5), seed=20 + i, floor=-0.05)
    return dict(name='RockCluster')


@asset('props/slab.glb', 'Rock slab', size=512)
def slab():
    rock((0, 0, 0.16), 1.7, 'rock', sq=(1.1, 0.75, 0.2), seed=11, cuts=3, floor=-0.05)
    o = rock((0.4, 0.15, 0.42), 1.1, 'rock', sq=(1.0, 0.7, 0.17), seed=12, cuts=3)
    F.rot(o, 'Y', -9, about=(0.4, 0.15, 0.42))
    o = rock((-0.6, -0.3, 0.36), 0.6, 'rock', sq=(1.0, 0.8, 0.22), seed=13, cuts=3)
    F.rot(o, 'X', 12, about=(-0.6, -0.3, 0.36))
    return dict(name='Slab')


@asset('props/cliff.glb', 'Cliff crag', size=512)
def cliff():
    # A crag of leaning columns with strata, tallest in the middle.
    for i, (x, y, r, h, lx, ly) in enumerate(((0, 0, 1.25, 3.3, 4, -3), (1.6, 0.3, 1.0, 2.3, -8, 4), (-1.5, 0.2, 1.05, 2.6, 9, 3),
                                              (0.6, -1.0, 0.8, 1.5, -4, -10), (-0.8, -0.9, 0.7, 1.1, 6, -8), (2.5, -0.3, 0.6, 1.0, -12, 2),
                                              (-2.4, -0.3, 0.6, 1.2, 12, 0))):
        o = rock((x, y, h * 0.5), r, 'cliff', sq=(1.0, 0.8, h / r * 0.55), seed=40 + i, sub=3 if i < 3 else 2, cuts=7, floor=-0.05)
        F.rot(o, 'X', ly, about=(x, y, 0))
        F.rot(o, 'Y', lx, about=(x, y, 0))
    return dict(name='Cliff')


def leaf(base, length, width, yaw, pitch, zone, curl=0.5, n=5):
    pts, sect = [], []
    for k in range(n):
        t = k / (n - 1)
        a = math.radians(pitch) * (1 - curl * t)
        pts.append((t * length * math.cos(a), 0, t * length * math.sin(a) - curl * 0.25 * length * t * t))
        w = width * (0.25 + math.sin(math.pi * min(t * 1.15, 1)) * 0.75) * (1 - t * 0.85)
        sect.append((max(w, 0.006), max(w * 0.14, 0.004)))
    o = sweep(pts, sect, zone, sides=4, up=(0, 0, 1), sharp=60)
    F.rot(o, 'Z', yaw)
    F.move(o, base)
    return o


@asset('props/shrub.glb', 'Shrub')
def shrub():
    # A spray of broad blades round a low dark heart, like a desert agave thicket.
    rnd = random.Random(9)
    rock((0, 0, 0.14), 0.36, 'leaf', sq=(1, 1, 0.6), seed=60, rough=0.4, cuts=0, sharp=70, floor=0.0)
    for ring, (count, pitch, ln, wd) in enumerate(((7, 78, 0.95, 0.2), (10, 58, 1.0, 0.24), (12, 36, 0.9, 0.24), (10, 16, 0.7, 0.2))):
        for k in range(count):
            a = 360.0 * k / count + rnd.uniform(-14, 14) + ring * 17
            leaf((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0.05), ln * rnd.uniform(0.8, 1.15), wd, a,
                 pitch + rnd.uniform(-8, 8), 'leaf' if (k + ring) % 3 else 'grass', curl=rnd.uniform(0.5, 0.9), n=5)
    return dict(name='Shrub')


@asset('props/grass.glb', 'Grass tuft')
def grass():
    rnd = random.Random(2)
    for k in range(16):
        a = 360.0 * k / 16 + rnd.uniform(-12, 12)
        leaf((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0), rnd.uniform(0.5, 0.95), rnd.uniform(0.05, 0.08), a,
             rnd.uniform(48, 84), 'grass', curl=rnd.uniform(0.3, 0.8), n=5)
    return dict(name='Grass')


@asset('props/dead_tree.glb', 'Dead tree')
def dead_tree():
    rnd = random.Random(6)
    trunk = [(0, 0, -0.05), (0.06, 0.02, 0.5), (-0.03, 0.05, 1.1), (0.08, -0.02, 1.7), (0.02, 0.03, 2.3)]
    sweep(trunk, [0.2, 0.15, 0.12, 0.08, 0.02], 'bark', sides=7, up=(1, 0, 0))
    for k, (h, a, ln) in enumerate(((0.9, 30, 0.9), (1.25, 160, 1.0), (1.55, 265, 0.75), (1.9, 80, 0.6), (0.6, 210, 0.5))):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        p0 = (0.03, 0.03, h)
        p1 = (ca * ln * 0.5, sa * ln * 0.5, h + ln * 0.25)
        p2 = (ca * ln, sa * ln, h + ln * 0.75)
        sweep([p0, p1, p2], [0.07, 0.045, 0.012], 'bark', sides=5)
        q = (ca * ln * 0.5 - sa * 0.3, sa * ln * 0.5 + ca * 0.3, h + ln * 0.55)
        sweep([p1, q], [0.035, 0.008], 'bark', sides=4)
    for k in range(5):   # root flares
        a = math.radians(72 * k + 10)
        sweep([(0, 0, 0.25), (math.cos(a) * 0.25, math.sin(a) * 0.25, 0.06), (math.cos(a) * 0.5, math.sin(a) * 0.5, -0.04)], [0.1, 0.07, 0.02], 'bark', sides=5)
    return dict(name='DeadTree')


@asset('props/tendril.glb', 'Glowing alien fronds')
def tendril():
    rnd = random.Random(12)
    rock((0, 0, 0.12), 0.42, 'rockdark', sq=(1, 1, 0.5), seed=70, floor=-0.03)
    for k in range(7):
        a = math.radians(360.0 * k / 7 + rnd.uniform(-15, 15))
        ln = rnd.uniform(1.0, 1.7)
        reach = rnd.uniform(0.5, 1.0)
        pts, sect = [], []
        for i in range(8):
            t = i / 7
            curl = math.sin(t * math.pi * 1.2) * 0.25
            r = reach * t + curl * 0.3
            pts.append((math.cos(a) * r - math.sin(a) * curl, math.sin(a) * r + math.cos(a) * curl, ln * (t ** 0.8)))
            sect.append(0.07 * (1 - t) + 0.015)
        sweep(pts, sect, 'frond', sides=5)
        orb(pts[-1], 0.1, 'frond', seg=(8, 6))
    return dict(name='Tendril')


def crystal(base, h, r, yaw, lean, zone, sides=6):
    """Faceted shard: a six-sided column with a slanted point, leaning out from its base."""
    a, l = math.radians(yaw), math.radians(lean)
    d = (math.cos(a) * math.sin(l), math.sin(a) * math.sin(l), math.cos(l))
    p0 = (base[0] - d[0] * 0.15, base[1] - d[1] * 0.15, base[2] - d[2] * 0.15)
    p1 = (base[0] + d[0] * h, base[1] + d[1] * h, base[2] + d[2] * h)
    o = tube(p0, p1, [(0, r * 0.8), (0.72, r), (0.86, r * 0.6), (1, r * 0.04)], sides, zone, sharp=15)
    return o


def cluster(c, n, h, r, zone, rnd, lean=28):
    crystal(c, h, r, rnd.uniform(0, 360), rnd.uniform(0, 8), zone)
    for k in range(n):
        yaw = 360.0 * k / n + rnd.uniform(-20, 20)
        a = math.radians(yaw)
        hh = h * rnd.uniform(0.4, 0.8)
        rr = r * rnd.uniform(0.5, 0.8)
        crystal((c[0] + math.cos(a) * r * 0.8, c[1] + math.sin(a) * r * 0.8, c[2]), hh, rr, yaw, lean + rnd.uniform(-10, 14), zone)


def deposit(gem, rockzone, seed, big, n_small, spread):
    rnd = random.Random(seed)
    # Broken ground, a main spray of crystal columns, satellite sprays and loose shards.
    for k in range(8):
        a = math.radians(360.0 * k / 8 + rnd.uniform(-20, 20))
        d = rnd.uniform(spread * 0.25, spread * 0.8)
        r = rnd.uniform(0.5, 0.95)
        rock((math.cos(a) * d, math.sin(a) * d, r * 0.3), r, rockzone, sq=(1.1, 0.9, 0.6), seed=seed + k, floor=-0.05)
    rock((0, 0, 0.3), big * 0.75, rockzone, sq=(1.1, 1.0, 0.5), seed=seed + 30, floor=-0.05)
    cluster((0, 0, 0.25), 7, big * 1.9, big * 0.34, gem, rnd)
    for k in range(n_small):
        a = math.radians(360.0 * k / n_small + rnd.uniform(-25, 25))
        d = rnd.uniform(spread * 0.45, spread)
        cluster((math.cos(a) * d, math.sin(a) * d, 0.0), rnd.randint(2, 4), rnd.uniform(0.7, 1.4), rnd.uniform(0.16, 0.26), gem, rnd, lean=34)


@asset('props/deposit_ore.glb', 'Ore site (pink crystal)', size=512)
def deposit_ore():
    deposit('gem_pink', 'redrock', 100, 1.7, 9, 4.2)
    return dict(name='OreDeposit_pink', gem='gem_pink')


@asset('props/deposit_metal.glb', 'Metal site (blue opal)', size=512)
def deposit_metal():
    deposit('gem_opal', 'rockdark', 200, 1.55, 6, 3.2)
    return dict(name='OreDeposit_opal', gem='gem_opal')
