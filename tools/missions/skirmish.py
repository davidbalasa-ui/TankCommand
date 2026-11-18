"""Builds the skirmish maps: writes src/data/maps.placeholder.json. Edit this file, not the JSON.

    python3 tools/missions/skirmish.py

Every map is fair by construction: each start's home sites are laid out once, in the start's own
frame (forward = toward the map centre), and turned onto every start; the terrain is rotationally
symmetric (and four-way symmetric on the four-player maps), and contested sites come in mirrored
pairs. Starts on four-player maps sit a little off the diagonals so each landing pad's exit edge
(which snaps to the nearer axis) turns with its corner too.

Player numbering: on four-player maps starts 1 and 2 face each other across the map, so a
one-on-one match uses opposite corners; a third side takes start 3.

Checks: tests/unit/map.test.ts (MAP-03, every start reaches every other) and
tests/unit/siteSpacing.test.ts (SITE-01, sites 12 m or more from every pad's edge). To look at the
maps: npx vite-node tools/missions/dump.ts skirmish <dir> && python3 tools/missions/preview.py <dir> <png>.
"""
import json
import math
import os

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def even(v):
    """Even metres keep a metal station's footprint on the 2 m path grid."""
    return int(2 * round(v / 2))


def turn(x, z, angle):
    c, s = math.cos(angle), math.sin(angle)
    return x * c - z * s, x * s + z * c


def home_sites(start, layout):
    """layout: (kind, forward, right, amount) in the start's frame, forward pointing at the centre."""
    sx, sz = start
    length = math.hypot(sx, sz)
    fx, fz = -sx / length, -sz / length
    rx, rz = -fz, fx
    out = []
    for kind, fwd, right, amount in layout:
        out.append((kind, even(sx + fx * fwd + rx * right), even(sz + fz * fwd + rz * right), amount))
    return out


def rotations(x, z, ways):
    return [turn(x, z, 2 * math.pi * k / ways) for k in range(ways)]


# The home field every start gets: four ore fields and two metal sites behind and beside the pad,
# 18-26 m out (12 m or more clear of the pad's edge).
HOME = [
    ('ore', -2, -24, 500), ('ore', -2, 24, 500), ('ore', -22, -12, 500), ('ore', -22, 12, 500),
    ('metal', -26, 0, 250), ('metal', 4, -30, 250),
]


def make_map(map_id, name, size, starts, contested, terrain, water=None, home=HOME):
    """starts in player order; contested: list of (kind, x, z, amount) already mirrored."""
    deposits = []
    for start in starts:
        deposits += home_sites(start, home)
    deposits += contested
    features = {'waterLevel': None, 'lakes': [], 'rivers': [], 'terrain': terrain}
    if water:
        features.update(water)
    return {
        'id': map_id,
        'name': name,
        'size': size,
        'cellSize': 2,
        'starts': [{'player': i + 1, 'x': x, 'z': z} for i, (x, z) in enumerate(starts)],
        'deposits': [{'kind': k, 'x': x, 'z': z, 'amount': a} for k, x, z, a in deposits],
        'features': features,
        'placeholder': False,
    }


def mirrored(kind, x, z, amount, ways=2):
    return [(kind, even(px), even(pz), amount) for px, pz in rotations(x, z, ways)]


def flats_for(starts, radius=15):
    return [{'x': x, 'z': z, 'radius': radius} for x, z in starts]


def ridge(x0, z0, x1, z1, height=9, width=7):
    return {'x0': x0, 'z0': z0, 'x1': x1, 'z1': z1, 'height': height, 'width': width}


def ridge_both(x0, z0, x1, z1, ways=2, **kw):
    out = []
    for k in range(ways):
        a = 2 * math.pi * k / ways
        p0 = turn(x0, z0, a)
        p1 = turn(x1, z1, a)
        out.append(ridge(round(p0[0], 1), round(p0[1], 1), round(p1[0], 1), round(p1[1], 1), **kw))
    return out


MAPS = []

# ---------------------------------------------------------------- the first two (hand-made)

# Cinder Basin (was "Utopia Basin", a name from the 1998 game): the classic noise terrain with the
# diagonal centre ridge. Kept as it was, apart from the name, because many tests play on it.
MAPS.append({
    'id': 'map.wp02_skirmish', 'name': 'Cinder Basin', 'size': 160, 'cellSize': 2,
    'starts': [{'player': 1, 'x': -50, 'z': -50}, {'player': 2, 'x': 50, 'z': 50}],
    'deposits': [{'kind': k, 'x': x, 'z': z, 'amount': a} for k, x, z, a in [
        ('ore', -66, -36, 500), ('ore', -36, -66, 500), ('ore', -68, -50, 500), ('ore', -50, -68, 500),
        ('metal', -70, -56, 250), ('metal', -56, -70, 250),
        ('ore', 66, 36, 500), ('ore', 36, 66, 500), ('ore', 68, 50, 500), ('ore', 50, 68, 500),
        ('metal', 70, 56, 250), ('metal', 56, 70, 250),
    ]],
    'placeholder': True,
})

MAPS.append({
    'id': 'map.wp08_lakeside', 'name': 'Lakeside Crossing', 'size': 160, 'cellSize': 2,
    'starts': [{'player': 1, 'x': -50, 'z': -50}, {'player': 2, 'x': 50, 'z': 50}],
    'deposits': [{'kind': k, 'x': x, 'z': z, 'amount': a} for k, x, z, a in [
        ('ore', -66, -36, 500), ('ore', -36, -66, 500), ('metal', -70, -56, 250), ('metal', -56, -70, 250),
        ('ore', 66, 36, 500), ('ore', 36, 66, 500), ('metal', 70, 56, 250), ('metal', 56, 70, 250),
    ]],
    'features': {
        'waterLevel': -0.5,
        'lakes': [{'x': -25, 'z': 25, 'radius': 12, 'depth': 4}, {'x': 25, 'z': -25, 'radius': 12, 'depth': 4}],
        'rivers': [{'x0': -80, 'z0': 0, 'x1': 80, 'z1': 0, 'width': 8, 'depth': 4, 'fords': [{'from': 0.45, 'to': 0.55}]}],
        'terrain': {'centreRidge': False},
    },
    'placeholder': True,
})

# ---------------------------------------------------------------- two-player maps

# Twin Ridges: two long ridges cross the map between the bases. Each has one wide gap in the
# middle and a narrow one near an end, so armies choose between the open centre and a flank.
# A metal site and two ore fields sit in the valley between the ridges.
TR = [(-58, 54), (58, -54)]
MAPS.append(make_map(
    'map.s_twin_ridges', 'Twin Ridges', 180, TR,
    mirrored('ore', -44, -36, 600) + [('metal', 0, 0, 300)],
    {
        'seed': 2101, 'roughness': 0.7, 'centreRidge': False, 'symmetric': True,
        # Lines parallel to the x = z diagonal, one each side of the middle.
        'ridges': ridge_both(-86, -54, -52, -20) + ridge_both(-38, -6, -18, 14) + ridge_both(6, 38, 34, 66),
        'hills': [{'x': 0, 'z': 0, 'radius': 14, 'height': 2.5},
                  {'x': -60, 'z': -60, 'radius': 18, 'height': 5}, {'x': 60, 'z': 60, 'radius': 18, 'height': 5}],
        'flats': flats_for(TR) + [{'x': 0, 'z': 0, 'radius': 8, 'height': 2.5}],
    },
))

# Fordwater: a river runs down the middle with three fords; two ponds guard the flanks. Hover
# craft cross anywhere. A rich ore field waits on each bank by the middle ford.
FW = [(-58, 6), (58, -6)]
MAPS.append(make_map(
    'map.s_fordwater', 'Fordwater', 180, FW,
    mirrored('ore', -22, -12, 700) + mirrored('ore', -24, 48, 500) + mirrored('metal', -26, -60, 300),
    {
        'seed': 2202, 'roughness': 0.8, 'centreRidge': False, 'symmetric': True,
        'hills': [{'x': -48, 'z': -50, 'radius': 16, 'height': 4}, {'x': 48, 'z': 50, 'radius': 16, 'height': 4}],
        'flats': flats_for(FW),
    },
    water={
        'waterLevel': -0.5,
        'lakes': [{'x': -40, 'z': 62, 'radius': 14, 'depth': 3}, {'x': 40, 'z': -62, 'radius': 14, 'depth': 3}],
        'rivers': [{'x0': 0, 'z0': -90, 'x1': 0, 'z1': 90, 'width': 10, 'depth': 4,
                    'fords': [{'from': 0.17, 'to': 0.25}, {'from': 0.45, 'to': 0.55}, {'from': 0.75, 'to': 0.83}]}],
    },
))

# High Table: a broad raised table in the middle, walled by cliffs with four ramps, holds the
# richest ore. The bases sit low in opposite corners.
HT = [(-62, 58), (62, -58)]
TABLE_H = 7
CLIFF_R = 34
RAMP = 14  # degrees each side of a ramp's centre line
cliffs = []
# Cliff walls round the table, two straight pieces per quarter, broken by four ramps on the
# diagonals (two toward the bases, two to the sides).
for k in range(4):
    for a0, a1 in [(45 + RAMP, 90), (90, 135 - RAMP)]:
        p0 = turn(CLIFF_R, 0, math.radians(a0 + 90 * k))
        p1 = turn(CLIFF_R, 0, math.radians(a1 + 90 * k))
        cliffs.append(ridge(round(p0[0], 1), round(p0[1], 1), round(p1[0], 1), round(p1[1], 1),
                            height=TABLE_H, width=7))
MAPS.append(make_map(
    'map.s_high_table', 'High Table', 190, HT,
    mirrored('ore', -12, 12, 800) + mirrored('ore', 12, 12, 800) + mirrored('metal', -56, -40, 300),
    {
        'seed': 2303, 'roughness': 0.6, 'centreRidge': False, 'symmetric': True,
        'ridges': cliffs,
        'flats': flats_for(HT) + [{'x': 0, 'z': 0, 'radius': 22, 'height': TABLE_H}],
    },
))

# ---------------------------------------------------------------- four-player maps

# Starts a little off the diagonals: (-64, -60) and its quarter turns.
FOUR = [(-64, -60), (64, 60), (60, -64), (-60, 64)]


def four_way(x, z, kind, amount):
    return [(kind, even(px), even(pz), amount) for px, pz in rotations(x, z, 4)]


# Crossfall: ridges along both axes split the map into four quarters, one per start. Each
# ridge has a gap halfway out and the middle is open ground round a low hill with metal on it.
MAPS.append(make_map(
    'map.s_crossfall', 'Crossfall', 200, FOUR,
    four_way(-34, -16, 'ore', 600) + four_way(-16, -16, 'metal', 250),
    {
        'seed': 2404, 'roughness': 0.6, 'centreRidge': False, 'symmetric': True, 'fourWay': True,
        'ridges': [r for x0, z0, x1, z1 in [(-100, 0, -60, 0), (-44, 0, -22, 0)]
                   for r in ridge_both(x0, z0, x1, z1, ways=4, height=9, width=6)],
        'hills': [{'x': 0, 'z': 0, 'radius': 18, 'height': 3}],
        'flats': flats_for(FOUR) + [{'x': 0, 'z': 0, 'radius': 6, 'height': 3}],
    },
))

# Fourfold Fen: a lake in the middle feeds four streams that run out to the map edges between
# the bases. Every stream has a ford near the lake and one near the edge.
MAPS.append(make_map(
    'map.s_fourfold_fen', 'Fourfold Fen', 200, FOUR,
    four_way(-40, -20, 'ore', 600) + four_way(-24, -24, 'metal', 250),
    {
        'seed': 2505, 'roughness': 0.6, 'centreRidge': False, 'symmetric': True, 'fourWay': True,
        'flats': flats_for(FOUR),
    },
    water={
        'waterLevel': -0.5,
        'lakes': [{'x': 0, 'z': 0, 'radius': 18, 'depth': 3}],
        'rivers': [
            {'x0': round(px, 1), 'z0': round(pz, 1), 'x1': round(qx, 1), 'z1': round(qz, 1), 'width': 8, 'depth': 4,
             'fords': [{'from': 0.18, 'to': 0.28}, {'from': 0.72, 'to': 0.82}]}
            for (px, pz), (qx, qz) in zip(rotations(-12, 0, 4), rotations(-100, 0, 4))
        ],
    },
))


def write():
    with open(os.path.join(ROOT, 'src/data/maps.placeholder.json'), 'w') as f:
        json.dump(MAPS, f, indent=2)
        f.write('\n')
    print(f'{len(MAPS)} skirmish maps')


write()
