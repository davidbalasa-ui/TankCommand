"""Builds the campaign and training maps and missions from the approved outline.

Writes src/data/maps.campaign.json, src/data/missions/campaign/*.json and the import list
src/data/missions/campaign.ts, and the training lessons src/data/missions/training_*.json with
their import list src/data/missions/training.ts. Edit this file, not the generated JSON.

    python3 tools/missions/build.py

Pacing (David, 2026-11-12): mission 1 is easy and short; every later mission adds at most one new
idea and a little more enemy pressure. Speakers and briefings are original text.
"""
import json
import math
import os

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SEC = 20  # sim ticks per second

# ---------------------------------------------------------------- factions and roles

ROLE = {
    'human': {
        'light': 'unit.human.light_tank', 'scout': 'unit.human.scout', 'miner': 'unit.human.ore_miner',
        'tug': 'unit.human.tug', 'repair': 'unit.human.repair', 'radar': 'unit.human.radar',
        'hover': 'unit.human.hover_tank', 'heavy': 'unit.human.heavy_tank', 'missile': 'unit.human.missile_tank',
        'artillery': 'unit.human.artillery', 'fighter': 'unit.human.fighter', 'bomber': 'unit.human.bomber',
        'pad': 'structure.human.landing_pad', 'station': 'structure.human.metal_station',
        'turret': 'structure.human.turret', 'tower_radar': 'structure.human.radar', 'lab': 'structure.human.lab',
        'air_base': 'structure.human.air_base', 'battery': 'structure.human.missile_battery',
    },
    'alien': {
        'light': 'unit.alien.light_tank', 'scout': 'unit.alien.light_skimmer', 'miner': 'unit.alien.ore_miner',
        'tug': 'unit.alien.tug', 'repair': 'unit.alien.repair', 'radar': 'unit.alien.radar',
        'hover': 'unit.alien.glider', 'heavy': 'unit.alien.heavy_tank', 'missile': 'unit.alien.missile_tank',
        'artillery': 'unit.alien.artillery', 'fighter': 'unit.alien.fighter', 'saucer': 'unit.alien.saucer',
        'dragonfly': 'unit.alien.dragonfly',
        'pad': 'structure.alien.landing_pad', 'station': 'structure.alien.metal_station',
        'turret': 'structure.alien.turret', 'tower_radar': 'structure.alien.radar', 'lab': 'structure.alien.lab',
        'air_base': 'structure.alien.air_base', 'battery': 'structure.alien.missile_battery',
    },
}
OTHER = {'human': 'alien', 'alien': 'human'}
# The voices on the radio: the Terran player's commanding officer, and the Matriarch who leads the
# broods on Vesper and speaks to the player's young brood-mind. Each is the other campaign's
# mission-13 target (A13 calls Daska "the Iron Colonel").
SPEAKER = {'human': 'Col. Daska', 'alien': 'Matriarch'}

# Research each step of the campaign hands the player for free, so new items arrive by mission.
# The basic gun tower needs no research. Fortifications brings the armour upgrade and Missiles the
# fire-rate upgrade, so each group keeps the upgrades it gave before the step-4 tree.
RESEARCH = {
    'towers': ['fortifications'],
    'sensors': ['missiles', 'sensors'],
    'heavy': ['fortifications', 'heavy_armor'],
    'artillery': ['missiles', 'heavy_ordnance'],
    'hover': ['hover_drive'],
    'repair': ['fortifications', 'field_repair'],
    'air': ['sensors', 'aviation'],
    'disc': ['sensors', 'aviation'],
}


def research(faction, *groups):
    names = []
    for group in groups:
        for name in RESEARCH[group]:
            if name not in names:
                names.append(name)
    return [f'research.{faction}.{name}' for name in names]


def avail(faction, *roles):
    return [ROLE[faction][role] for role in roles]


def heading_to(x0, z0, x1, z1):
    return round(math.atan2(z1 - z0, x1 - x0), 3)


# ---------------------------------------------------------------- maps

MAPS = []


def add_map(map_id, name, size, starts, deposits, terrain, water=None):
    features = {'waterLevel': None, 'lakes': [], 'rivers': [], 'terrain': terrain}
    if water:
        features.update(water)
    MAPS.append({
        'id': map_id, 'name': name, 'size': size, 'cellSize': 2,
        'starts': [{'player': i + 1, 'x': x, 'z': z} for i, (x, z) in enumerate(starts)],
        'deposits': [{'kind': k, 'x': x, 'z': z, 'amount': a} for k, x, z, a in deposits],
        'features': features, 'placeholder': False, 'campaignOnly': True,
    })


# Halden Outpost: landing field south-west, the colony outpost north-east, two ridges making a
# central lane. Missions 1-4 of both campaigns.
LAND = (-52, 48)
OUTPOST = (45, -45)
add_map('map.c_halden', 'Halden Outpost', 160, [LAND, OUTPOST], [
    ('ore', -68, 36, 600), ('ore', -40, 64, 600), ('ore', -68, 60, 500), ('metal', -36, 34, 250),
    ('ore', 60, -30, 500), ('ore', 30, -60, 500), ('metal', 62, -58, 250), ('ore', 6, 8, 400),
], {
    'seed': 101, 'roughness': 0.8, 'centreRidge': False, 'symmetric': False,
    'ridges': [
        {'x0': -32, 'z0': -76, 'x1': -12, 'z1': -18, 'height': 8, 'width': 7},
        {'x0': 8, 'z0': 18, 'x1': 72, 'z1': 36, 'height': 8, 'width': 7},
    ],
    'hills': [{'x': 2, 'z': -50, 'radius': 18, 'height': 4}, {'x': -48, 'z': -8, 'radius': 15, 'height': 3.5},
              {'x': 32, 'z': 58, 'radius': 16, 'height': 4}],
    'flats': [{'x': LAND[0], 'z': LAND[1], 'radius': 14}, {'x': OUTPOST[0], 'z': OUTPOST[1], 'radius': 14},
              {'x': 2, 'z': 6, 'radius': 9}],
})

# Blind Ridge: tall hills hide three small posts; the player has to scout to find them.
RIDGE_START = (-66, 62)
RIDGE_POSTS = [(-58, -58), (62, -50), (58, 52)]
add_map('map.c_blind_ridge', 'Blind Ridge', 180, [RIDGE_START, (60, -50)], [
    ('ore', -78, 50, 600), ('ore', -52, 78, 600), ('metal', -76, 76, 250), ('ore', 0, 0, 500),
    ('ore', -70, -40, 400), ('ore', 70, -70, 400), ('ore', 76, 40, 400),
], {
    'seed': 202, 'roughness': 0.9, 'centreRidge': False, 'symmetric': False,
    'hills': [
        {'x': -38, 'z': -30, 'radius': 24, 'height': 12}, {'x': 30, 'z': -28, 'radius': 22, 'height': 12},
        {'x': 30, 'z': 32, 'radius': 22, 'height': 12}, {'x': -20, 'z': 40, 'radius': 14, 'height': 7},
    ],
    'flats': [{'x': RIDGE_START[0], 'z': RIDGE_START[1], 'radius': 14}, {'x': 0, 'z': 0, 'radius': 10}]
             + [{'x': x, 'z': z, 'radius': 9} for x, z in RIDGE_POSTS],
})

# Relay Road: a long road between broken ridges to the relay station in the far corner.
ROAD_START = (-76, 72)
RELAY = (72, -72)
add_map('map.c_relay_road', 'Relay Road', 200, [ROAD_START, RELAY], [
    ('ore', -86, 58, 500), ('ore', -62, 86, 500), ('ore', 80, -60, 400), ('metal', 58, -86, 250),
], {
    'seed': 303, 'roughness': 0.7, 'centreRidge': False, 'symmetric': False,
    'ridges': [
        {'x0': -58, 'z0': 92, 'x1': -12, 'z1': 46, 'height': 9, 'width': 7},
        {'x0': 8, 'z0': 26, 'x1': 92, 'z1': -58, 'height': 9, 'width': 7},
        {'x0': -92, 'z0': 56, 'x1': -46, 'z1': 10, 'height': 9, 'width': 7},
        {'x0': -26, 'z0': -10, 'x1': 56, 'z1': -92, 'height': 9, 'width': 7},
    ],
    'flats': [{'x': ROAD_START[0], 'z': ROAD_START[1], 'radius': 12}, {'x': RELAY[0], 'z': RELAY[1], 'radius': 12},
              {'x': -2, 'z': 0, 'radius': 10}],
})

# Kessra Valley: the enemy base sits in a valley ringed by ridges with two ways in.
VALLEY_HOME = (-62, 62)
VALLEY_ENEMY = (56, -56)
add_map('map.c_kessra_valley', 'Kessra Valley', 200, [VALLEY_HOME, VALLEY_ENEMY], [
    ('ore', -80, 48, 600), ('ore', -48, 80, 600), ('ore', -82, 80, 500), ('metal', -44, 46, 250),
    ('ore', 72, -40, 600), ('ore', 40, -74, 600), ('metal', 76, -76, 250),
    ('ore', -6, 6, 500), ('ore', 30, 40, 400), ('ore', -40, -30, 400),
], {
    'seed': 404, 'roughness': 0.9, 'centreRidge': False, 'symmetric': False,
    'ridges': [
        {'x0': 10, 'z0': -96, 'x1': 14, 'z1': -40, 'height': 9, 'width': 8},
        {'x0': 14, 'z0': -22, 'x1': 30, 'z1': -14, 'height': 9, 'width': 8},
        {'x0': 48, 'z0': -10, 'x1': 96, 'z1': -14, 'height': 9, 'width': 8},
    ],
    'hills': [{'x': -20, 'z': 30, 'radius': 18, 'height': 4}, {'x': 10, 'z': 60, 'radius': 16, 'height': 5}],
    'flats': [{'x': VALLEY_HOME[0], 'z': VALLEY_HOME[1], 'radius': 15},
              {'x': VALLEY_ENEMY[0], 'z': VALLEY_ENEMY[1], 'radius': 15}],
})

# ---------------------------------------------------------------- act 2 maps

# Quiet Fields: a farming colony in rolling ground. Two metal seams by the colony, three more out
# east that both sides want. Missions 8, 11 and 12.
FIELDS_HOME = (-62, 58)
FIELDS_SITES = [(38, -6), (58, 46), (8, -58)]
add_map('map.c_quiet_fields', 'Quiet Fields', 180, [FIELDS_HOME, (66, -66)], [
    ('ore', -78, 44, 700), ('ore', -50, 78, 700), ('ore', -30, 44, 500), ('metal', -42, 72, 300),
    ('metal', -76, 30, 300), ('ore', 0, 10, 500), ('ore', 66, -40, 500), ('ore', 30, 70, 400),
] + [('metal', x, z, 300) for x, z in FIELDS_SITES], {
    'seed': 505, 'roughness': 0.6, 'centreRidge': False, 'symmetric': False,
    'hills': [{'x': -10, 'z': 40, 'radius': 16, 'height': 3}, {'x': 30, 'z': 20, 'radius': 14, 'height': 3},
              {'x': -40, 'z': -30, 'radius': 20, 'height': 4}, {'x': 64, 'z': 0, 'radius': 12, 'height': 3}],
    'ridges': [{'x0': -88, 'z0': -10, 'x1': -50, 'z1': -6, 'height': 7, 'width': 6}],
    'flats': [{'x': FIELDS_HOME[0], 'z': FIELDS_HOME[1], 'radius': 16}]
             + [{'x': x, 'z': z, 'radius': 8} for x, z in FIELDS_SITES],
})

# Long Reach: the enemy holds a broad hill in the middle of the map with towers that outrange
# tanks. Artillery can outrange the towers. Missions 9 and 13.
REACH_HOME = (-74, 74)
REACH_HILL = (14, -14)
REACH_CAMP = (66, -66)
REACH_GUNS = [(2, -2), (24, -2), (2, -26), (26, -24)]
add_map('map.c_long_reach', 'Long Reach', 200, [REACH_HOME, REACH_CAMP], [
    ('ore', -88, 58, 700), ('ore', -58, 88, 700), ('metal', -86, 86, 300), ('ore', -40, 50, 500),
    ('ore', 80, -48, 500), ('ore', 48, -82, 500), ('ore', -50, -50, 500), ('ore', 50, 50, 500),
], {
    'seed': 606, 'roughness': 0.7, 'centreRidge': False, 'symmetric': False,
    'hills': [{'x': REACH_HILL[0], 'z': REACH_HILL[1], 'radius': 30, 'height': 6},
              {'x': -40, 'z': 10, 'radius': 14, 'height': 4}, {'x': 10, 'z': 60, 'radius': 14, 'height': 4}],
    'ridges': [{'x0': -100, 'z0': -36, 'x1': -36, 'z1': -36, 'height': 8, 'width': 6},
               {'x0': 36, 'z0': 36, 'x1': 36, 'z1': 100, 'height': 8, 'width': 6}],
    'flats': [{'x': REACH_HOME[0], 'z': REACH_HOME[1], 'radius': 15}, {'x': REACH_CAMP[0], 'z': REACH_CAMP[1], 'radius': 14},
              {'x': REACH_HILL[0], 'z': REACH_HILL[1], 'radius': 16, 'height': 6}],
})

# Delta: two river channels split the map. Tracked units must go round by the southern ford;
# hover units cross anywhere. Mission 10.
DELTA_HOME = (-78, 10)
DELTA_CAMP = (72, -6)
add_map('map.c_delta', 'Sallow Delta', 200, [DELTA_HOME, DELTA_CAMP], [
    ('ore', -88, -10, 700), ('ore', -70, 34, 700), ('metal', -90, 30, 300), ('ore', -50, -40, 500),
    ('ore', 84, 20, 500), ('ore', 60, -40, 500), ('ore', 8, 0, 400),
], {
    'seed': 707, 'roughness': 0.5, 'centreRidge': False, 'symmetric': False,
    'hills': [{'x': -60, 'z': -70, 'radius': 18, 'height': 4}, {'x': 70, 'z': 60, 'radius': 18, 'height': 4}],
    'flats': [{'x': DELTA_HOME[0], 'z': DELTA_HOME[1], 'radius': 15}, {'x': DELTA_CAMP[0], 'z': DELTA_CAMP[1], 'radius': 15}],
}, water={
    'waterLevel': -0.5, 'lakes': [{'x': 6, 'z': -70, 'radius': 22, 'depth': 3}],
    'rivers': [
        {'x0': -22, 'z0': -100, 'x1': -16, 'z1': 100, 'width': 12, 'depth': 4, 'fords': [{'from': 0.88, 'to': 0.97}]},
        {'x0': 28, 'z0': -100, 'x1': 34, 'z1': 100, 'width': 10, 'depth': 4, 'fords': [{'from': 0.88, 'to': 0.97}]},
    ],
})

# Iron Gate: the enemy forward base behind a ring of ridges with three ways in. Mission 14.
GATE_HOME = (-84, 84)
GATE_ENEMY = (66, -66)
add_map('map.c_iron_gate', 'Iron Gate', 220, [GATE_HOME, GATE_ENEMY], [
    ('ore', -96, 66, 700), ('ore', -66, 96, 700), ('ore', -96, 96, 500), ('metal', -62, 66, 300),
    ('ore', 86, -48, 700), ('ore', 48, -86, 700), ('metal', 90, -90, 300),
    ('ore', 0, 0, 600), ('ore', -40, -40, 500), ('ore', 40, 40, 500), ('metal', -70, -10, 300),
], {
    'seed': 808, 'roughness': 0.9, 'centreRidge': False, 'symmetric': False,
    'ridges': [
        {'x0': 10, 'z0': -110, 'x1': 14, 'z1': -56, 'height': 9, 'width': 8},
        {'x0': 16, 'z0': -36, 'x1': 30, 'z1': -14, 'height': 9, 'width': 8},
        {'x0': 50, 'z0': -10, 'x1': 110, 'z1': -14, 'height': 9, 'width': 8},
    ],
    'hills': [{'x': -20, 'z': 30, 'radius': 20, 'height': 5}, {'x': 20, 'z': 70, 'radius': 18, 'height': 5},
              {'x': -60, 'z': 20, 'radius': 14, 'height': 4}],
    'flats': [{'x': GATE_HOME[0], 'z': GATE_HOME[1], 'radius': 16}, {'x': GATE_ENEMY[0], 'z': GATE_ENEMY[1], 'radius': 18}],
})

# ---------------------------------------------------------------- act 3 maps

# Highwater: a high open plain with a lake; room for air war. Missions 15-17.
HIGH_HOME = (-74, 74)
HIGH_ENEMY = (68, -68)
add_map('map.c_highwater', 'Highwater', 200, [HIGH_HOME, HIGH_ENEMY], [
    ('ore', -88, 58, 700), ('ore', -58, 88, 700), ('metal', -88, 88, 300), ('ore', -40, 40, 500),
    ('ore', 84, -50, 600), ('ore', 50, -84, 600), ('metal', 86, -86, 300), ('ore', 30, 30, 500),
], {
    'seed': 909, 'roughness': 0.6, 'centreRidge': False, 'symmetric': False,
    'hills': [{'x': -30, 'z': -40, 'radius': 20, 'height': 5}, {'x': 40, 'z': 50, 'radius': 18, 'height': 5},
              {'x': 10, 'z': -70, 'radius': 14, 'height': 4}],
    'flats': [{'x': HIGH_HOME[0], 'z': HIGH_HOME[1], 'radius': 16}, {'x': HIGH_ENEMY[0], 'z': HIGH_ENEMY[1], 'radius': 16}],
}, water={'waterLevel': -0.5, 'lakes': [{'x': 0, 'z': 4, 'radius': 18, 'depth': 3}], 'rivers': []})

# Twin Colonies: two friendly settlements far apart, the enemy comes from the far corner. Mission 18.
TWIN_A = (-86, -10)
TWIN_B = (-10, 86)
TWIN_ENEMY = (80, -80)
add_map('map.c_twin_colonies', 'Twin Colonies', 220, [TWIN_A, TWIN_ENEMY, TWIN_B], [
    ('ore', -98, -28, 700), ('ore', -98, 8, 600), ('metal', -70, -30, 300),
    ('ore', -28, 98, 700), ('ore', 8, 98, 600), ('metal', -30, 70, 300),
    ('ore', 96, -60, 600), ('ore', 60, -96, 600), ('ore', 0, 0, 500),
], {
    'seed': 1010, 'roughness': 0.8, 'centreRidge': False, 'symmetric': False,
    'ridges': [{'x0': -60, 'z0': 20, 'x1': -20, 'z1': 60, 'height': 8, 'width': 7}],
    'hills': [{'x': 30, 'z': -10, 'radius': 18, 'height': 4}, {'x': -10, 'z': 30, 'radius': 12, 'height': 3}],
    'flats': [{'x': TWIN_A[0], 'z': TWIN_A[1], 'radius': 15}, {'x': TWIN_B[0], 'z': TWIN_B[1], 'radius': 15},
              {'x': TWIN_ENEMY[0], 'z': TWIN_ENEMY[1], 'radius': 15}],
})

# Crystal Fields: the ground near the rift, studded with Shard spires that shoot at anything. 19, 21.
FIELD_HOME = (-90, 90)
FIELD_EDGE = (82, -82)
FIELD_SPIRES = [(-40, 30), (-10, -10), (20, 30), (30, -40), (60, -10)]
add_map('map.c_crystal_fields', 'Crystal Fields', 220, [FIELD_HOME, FIELD_EDGE], [
    ('ore', -100, 72, 700), ('ore', -72, 100, 700), ('metal', -100, 100, 300), ('ore', -60, 60, 500),
    ('ore', 96, -60, 600), ('ore', 60, -96, 600), ('metal', 96, -96, 300), ('ore', 0, 60, 500), ('ore', 60, 0, 500),
], {
    'seed': 1111, 'roughness': 1.0, 'centreRidge': False, 'symmetric': False,
    'hills': [{'x': -60, 'z': -30, 'radius': 22, 'height': 6}, {'x': 40, 'z': 70, 'radius': 20, 'height': 6},
              {'x': 10, 'z': 0, 'radius': 14, 'height': 3}],
    'flats': [{'x': FIELD_HOME[0], 'z': FIELD_HOME[1], 'radius': 16}, {'x': FIELD_EDGE[0], 'z': FIELD_EDGE[1], 'radius': 16}]
             + [{'x': x, 'z': z, 'radius': 6} for x, z in FIELD_SPIRES],
})

# The Rift: the Shard sits in the middle; two enemy bases flank it. Missions 20 and 22.
RIFT_HOME = (-100, 100)
RIFT_SHARD = (10, -10)
RIFT_ENEMY_A = (96, -40)
RIFT_ENEMY_B = (40, -96)
add_map('map.c_rift', 'The Rift', 240, [RIFT_HOME, RIFT_ENEMY_A, RIFT_ENEMY_B], [
    ('ore', -110, 80, 800), ('ore', -80, 110, 800), ('metal', -110, 110, 300), ('ore', -60, 60, 600),
    # Two more home sites: the finale is long, and the home field must outlast it.
    ('ore', -116, 44, 700), ('ore', -44, 116, 700),
    ('ore', 108, -20, 600), ('ore', 108, -64, 600), ('metal', 80, -20, 300),
    ('ore', 20, -108, 600), ('ore', 64, -108, 600), ('metal', 20, -80, 300),
    ('ore', -40, -20, 500), ('ore', 20, 40, 500),
], {
    'seed': 1212, 'roughness': 0.9, 'centreRidge': False, 'symmetric': False,
    'ridges': [{'x0': -30, 'z0': -60, 'x1': -10, 'z1': -30, 'height': 8, 'width': 7},
               {'x0': 30, 'z0': 10, 'x1': 60, 'z1': 30, 'height': 8, 'width': 7}],
    'hills': [{'x': -50, 'z': 20, 'radius': 18, 'height': 4}, {'x': 60, 'z': 70, 'radius': 20, 'height': 5}],
    'flats': [{'x': RIFT_HOME[0], 'z': RIFT_HOME[1], 'radius': 16}, {'x': RIFT_SHARD[0], 'z': RIFT_SHARD[1], 'radius': 12},
              {'x': RIFT_ENEMY_A[0], 'z': RIFT_ENEMY_A[1], 'radius': 15}, {'x': RIFT_ENEMY_B[0], 'z': RIFT_ENEMY_B[1], 'radius': 15}],
})

# ---------------------------------------------------------------- mission helpers

MISSIONS = []


def T(id_, when, *do, repeat=False):
    t = {'id': id_, 'when': when, 'do': list(do)}
    if repeat:
        t['repeat'] = True
    return t


def at(sec):
    return {'t': 'time', 'tick': int(sec * SEC)}


def area(side, x, z, r, **kw):
    return {'t': 'areaEntered', 'side': side, 'x': x, 'z': z, 'radius': r, **kw}


def msg(text, faction):
    return {'t': 'message', 'speaker': SPEAKER[faction], 'text': text}


def reveal(x, z, radius=12, sec=90):
    return {'t': 'revealArea', 'x': x, 'z': z, 'radius': radius, 'forSec': sec}


def done(id_):
    return {'t': 'setObjective', 'id': id_, 'status': 'done'}


def failed(id_):
    return {'t': 'setObjective', 'id': id_, 'status': 'failed'}


def spawn(side, unit, count, x, z, tag=None, drop=False, launch=False):
    a = {'t': 'spawn', 'side': side, 'unitType': unit, 'count': count, 'x': x, 'z': z}
    if tag:
        a['tag'] = tag
    if drop:
        a['drop'] = True
    if launch:
        a['launch'] = True
    return a


def attack(tag, x, z):
    return {'t': 'aiOrder', 'tag': tag, 'mode': 'attack', 'x': x, 'z': z}


def U(side, unit, x, z, heading=0.0, tag=None):
    u = {'side': side, 'unitType': unit, 'x': x, 'z': z, 'heading': heading}
    if tag:
        u['tag'] = tag
    return u


def S(side, structure, x, z):
    return {'side': side, 'structureType': structure, 'x': x, 'z': z}


def player_side(faction, ore, metal=0, available=None, research_done=None):
    s = {'player': 1, 'faction': faction, 'controller': 'human', 'ore': ore, 'metal': metal}
    if available is not None:
        s['available'] = available
    if research_done:
        s['researchDone'] = research_done
    return s


def enemy_side(faction, controller='none', ore=0, metal=0, difficulty=None, player=2, team=None):
    s = {'player': player, 'faction': faction, 'controller': controller, 'ore': ore, 'metal': metal}
    if difficulty:
        s['difficulty'] = difficulty
    if team:
        s['team'] = team
    return s


def at_war(a, b):
    """Both directions of a hostile relation."""
    return [{'a': a, 'b': b, 'relation': 'hostile'}, {'a': b, 'b': a, 'relation': 'hostile'}]


# What the player could buy (and had researched) by the end of the campaign's previous mission.
# A campaign's buy list only ever grows: nothing the player has met vanishes in a later mission.
ROSTER = {}


def grow_roster(campaign, sides):
    seen = ROSTER.setdefault(campaign, {'available': [], 'researchDone': []})
    for side in sides:
        if side['controller'] != 'human':
            continue
        for key in ('available', 'researchDone'):
            if key not in side and key == 'available':
                continue
            merged = list(seen[key])
            for item in side.get(key, []):
                if item not in merged:
                    merged.append(item)
            if merged:
                side[key] = merged
            seen[key] = merged


def mission(faction, order, slug, title, briefing, map_id, sides, units, structures, objectives, triggers,
            time_limit=None, relations=(), neutral=(), epilogue=None):
    campaign = 'human' if faction == 'human' else 'alien'
    grow_roster(campaign, sides)
    m = {
        'id': f'mission.{campaign}.{order:02d}_{slug}', 'campaign': campaign, 'order': order, 'title': title,
        'briefing': briefing, 'mapId': map_id, 'sides': sides, 'units': units, 'structures': structures,
        'objectives': [{'id': i, 'text': t, 'kind': k} for i, t, k in objectives], 'triggers': triggers,
        'placeholder': False,
    }
    if time_limit:
        m['timeLimitSec'] = time_limit
    if epilogue:
        m['epilogue'] = epilogue
    # Sides without an AI default to neutral; every enemy side here fights the player from the start.
    # `neutral` sides start out of the fight (a trigger may turn them later); `relations` adds more.
    m['relations'] = [r for side in sides
                      if side['controller'] != 'human' and side.get('team', side['player']) != 1
                      and side['player'] not in neutral
                      for r in ({'a': 1, 'b': side['player'], 'relation': 'hostile'},
                                {'a': side['player'], 'b': 1, 'relation': 'hostile'})] + list(relations)
    MISSIONS.append(m)


def spread(cx, cz, n, gap=4.0):
    """n positions in a small block around a centre."""
    cols = max(1, math.ceil(math.sqrt(n)))
    out = []
    for i in range(n):
        out.append((round(cx + (i % cols - (cols - 1) / 2) * gap, 1), round(cz + (i // cols - (cols - 1) / 2) * gap, 1)))
    return out


# ---------------------------------------------------------------- act 1 (both sides)

def act1(f):
    e = OTHER[f]
    R, E = ROLE[f], ROLE[e]
    terran = f == 'human'
    lx, lz = LAND
    ox, oz = OUTPOST
    face = heading_to(lx, lz, ox, oz)

    # 1: one objective, a handful of weak enemies, nothing to build. About five minutes.
    mission(f, 1, 'signal_lost' if terran else 'first_seed',
            'Signal Lost' if terran else 'First Seed',
            ('Last night a rift tore open in the sky over Vesper. An hour later our Halden outpost stopped '
             'answering. Take four Lancers to the outpost and clear out whatever is there.') if terran else
            ('The rift is open, and the first seeds of the swarm have fallen on Vesper. Wake, young brood-mind. '
             'A Terran outpost watches our landing field: take four Lumens across and silence its three guards.'),
            'map.c_halden',
            [player_side(f, 0, available=[]), enemy_side(e)],
            [U(1, R['light'], x, z, face) for x, z in spread(lx, lz, 4)]
            + [U(2, E['scout'], x, z, -face) for x, z in [(ox - 6, oz + 4), (ox + 4, oz - 6), (ox + 2, oz + 6)]],
            [],
            [('reach', 'Reach the outpost', 'primary'), ('clear', 'Destroy the three guards', 'primary')],
            [
                T('intro', at(0), msg('Head north-east to the outpost. Drag to select, tap the ground to move.'
                                      if terran else 'The outpost is north-east. Drag to select, tap the ground to move.', f)),
                T('reach', area(1, ox, oz, 16), done('reach'),
                  msg('Unknown machines at the outpost. Tap one to attack it.' if terran else
                      'Its guards are weak and alone. Tap one to attack it.', f)),
                T('clear', {'t': 'allDestroyed', 'side': 2}, done('clear')),
            ],
            time_limit=15 * 60)

    # 2: the economy, with a small raid half way through.
    mission(f, 2, 'ore_line' if terran else 'feeding_ground',
            'Ore Line' if terran else 'Feeding Ground',
            ('The machines at Halden came through the rift. We are calling them Arcadians, and there will be '
             'more. Put the Prospector to work and bank 400 ore so we can call down reinforcements.') if terran else
            ('The swarm is hungry, and Vesper is rich. Set the Sifter on the ore and gather 400. Terran scouts '
             'will come sniffing.'),
            'map.c_halden',
            [player_side(f, 100, available=avail(f, 'light', 'scout', 'miner', 'tug')), enemy_side(e)],
            [U(1, R['light'], lx + 6, lz - 4, face), U(1, R['light'], lx + 2, lz - 8, face),
             U(1, R['miner'], lx - 6, lz - 2, face), U(1, R['tug'], lx - 4, lz + 4, face)],
            [S(1, R['pad'], lx, lz)],
            [('ore', 'Bank 400 ore', 'primary'),
             ('pad', 'Keep your landing pad' if terran else 'Keep your Landing Ring', 'primary')],
            [
                T('intro', at(0), msg('Select the Prospector, then tap an ore field. The Hauler carries the ore home '
                                      'by itself.' if terran else
                                      'Select the Sifter, then tap an ore field. The Ferrier carries the ore home '
                                      'by itself.', f)),
                T('raid', at(150), msg('Arcadian raiders coming from the north-east!' if terran else
                                       'Terran raiders, from the north-east. Feed them to the brood.', f),
                  spawn(2, E['scout'], 2, ox - 10, oz + 10, tag='raid'), attack('raid', lx, lz)),
                T('ore', {'t': 'resourceReached', 'side': 1, 'ore': 400}, done('ore')),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, failed('pad'),
                  {'t': 'lose', 'reason': 'padLost'}),
                T('padKept', {'t': 'objectiveDone', 'id': 'ore'}, done('pad')),
            ],
            time_limit=15 * 60)

    # 3: hold out, with the first defence tower.
    tower = 'Bastion Gun' if terran else 'Sentinel'
    mission(f, 3, 'dig_in' if terran else 'thorns',
            'Dig In' if terran else 'Thorns',
            (f'Arcadian raiders are probing the outpost. Hold it for six minutes. A {tower} is now in Build: '
             'place it where the raids come in.') if terran else
            (f'The outpost is ours, and the Terrans want it back. Hold it for six minutes. Grow a {tower} where '
             'they attack.'),
            'map.c_halden',
            [player_side(f, 450, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret'),
                         research_done=research(f, 'towers')), enemy_side(e)],
            [U(1, R['light'], ox - 8, oz + 8, -face), U(1, R['light'], ox - 2, oz + 10, -face),
             U(1, R['light'], ox - 10, oz + 2, -face), U(1, R['miner'], ox + 8, oz + 4), U(1, R['tug'], ox + 6, oz + 8)],
            [S(1, R['pad'], ox, oz)],
            [('hold', 'Hold the outpost for 6 minutes', 'primary')],
            [
                T('intro', at(0), msg(f'First raid in one minute. Buy a {tower} and place it facing south-west.' if terran
                                      else f'They come in one minute. Grow a {tower} facing south-west.', f)),
                T('w1', at(60), spawn(2, E['scout'], 2, lx, lz, tag='w1'), attack('w1', ox, oz)),
                T('w2', at(140), spawn(2, E['scout'], 2, -70, -40, tag='w2'), spawn(2, E['light'], 1, -66, -44, tag='w2'),
                  attack('w2', ox, oz)),
                T('w3', at(220), msg('A bigger group is coming.' if terran else 'A bigger pack is coming. Hold.', f),
                  spawn(2, E['light'], 4, lx + 6, lz - 6, tag='w3'), attack('w3', ox, oz)),
                T('w4', at(300), spawn(2, E['light'], 3, 20, 70, tag='w4'), spawn(2, E['scout'], 2, 26, 66, tag='w4'),
                  attack('w4', ox, oz)),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, failed('hold'),
                  {'t': 'lose', 'reason': 'padLost'}),
                T('held', at(360), done('hold')),
            ])

    # 4: the first enemy base (Terran) / a fleeing convoy (Arcadian).
    if terran:
        mission(f, 4, 'first_strike', 'First Strike',
                ('The outpost fell to a night attack while we regrouped at the landing field, and the Arcadians '
                 'have planted a Landing Ring on it. Take it back: destroy their camp and keep the supply Hauler '
                 'alive.'),
                'map.c_halden',
                [player_side(f, 900, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret', 'station'),
                             research_done=research(f, 'towers')),
                 enemy_side(e, 'ai', ore=200, metal=50, difficulty='easy')],
                [U(1, R['light'], lx + 4, lz - 2, face), U(1, R['light'], lx + 2, lz - 6, face),
                 U(1, R['light'], lx + 8, lz - 6, face), U(1, R['tug'], lx - 4, lz + 2, face, tag='vip'),
                 U(1, R['miner'], lx - 2, lz + 6, face),
                 U(2, E['light'], ox - 4, oz + 2, -face), U(2, E['light'], ox - 2, oz + 4, -face)],
                [S(1, R['pad'], lx, lz), S(2, E['pad'], ox, oz)],
                [('base', 'Destroy the Arcadian camp at the outpost', 'primary'),
                 ('vip', 'Keep the supply Hauler alive', 'primary'),
                 ('station', 'Build a Metal Station', 'optional')],
                [
                    T('intro', at(0), msg('The camp is north-east, on the outpost. Keep the supply Hauler away from the '
                                          'fighting.', f)),
                    T('wave', at(180), msg('Arcadian reinforcements are landing at the outpost.', f),
                      spawn(2, E['light'], 3, ox, oz, tag='wave', drop=True), attack('wave', lx, lz)),
                    T('vipLost', {'t': 'unitDestroyed', 'tag': 'vip'}, failed('vip'), {'t': 'lose', 'reason': 'vipLost'}),
                    T('station', {'t': 'structureBuilt', 'side': 1, 'structureType': R['station']}, done('station')),
                    T('baseDown', {'t': 'allDestroyed', 'side': 2}, done('base'), done('vip')),
                ],
                time_limit=25 * 60)
    else:
        # Haulers drive from the outpost to the far road; destroy them before they get there.
        convoy_from, convoy_to = (OUTPOST[0], OUTPOST[1]), (-70, -66)
        mission(f, 4, 'prey', 'Prey',
                ('While the brood fed at the landing field, the Terrans crept back into the outpost to save its '
                 'stores. Now their convoy is running for the north-west road. Catch it and destroy all three '
                 'Haulers.'),
                'map.c_halden',
                [player_side(f, 300, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret'),
                             research_done=research(f, 'towers')), enemy_side(e)],
                [U(1, R['scout'], x, z, face) for x, z in spread(lx + 4, lz - 4, 4)]
                + [U(1, R['light'], x, z, face) for x, z in spread(lx - 4, lz + 2, 2)]
                + [U(1, R['miner'], lx - 8, lz + 6), U(1, R['tug'], lx - 10, lz + 2)]
                + [U(2, E['tug'], x, z, 3.0, tag='convoy') for x, z in spread(convoy_from[0], convoy_from[1], 3, 5)]
                + [U(2, E['light'], x, z, 3.0, tag='escort') for x, z in [(convoy_from[0] - 8, convoy_from[1]),
                                                                            (convoy_from[0], convoy_from[1] - 8)]],
                [S(1, R['pad'], lx, lz)],
                [('convoy', 'Destroy the three Haulers', 'primary'), ('escape', 'Let none of them escape', 'primary')],
                [
                    T('intro', at(0), msg('Darters are fast. Send them ahead to cut the convoy off.', f)),
                    # The convoy moves in legs and stops to regroup, so a player has about four minutes.
                    T('leg1', at(40), msg('The prey is moving west. It stops to regroup on the way.', f),
                      attack('convoy', 20, -60), attack('escort', 20, -60)),
                    T('leg2', at(120), attack('convoy', -15, -45), attack('escort', -15, -45)),
                    T('leg3', at(200), msg('They run again. Catch them before the road!', f),
                      attack('convoy', -45, -65), attack('escort', -45, -65)),
                    T('leg4', at(270), attack('convoy', convoy_to[0], convoy_to[1]), attack('escort', convoy_to[0], convoy_to[1])),
                    T('escaped', {'t': 'unitEscorted', 'tag': 'convoy', 'x': convoy_to[0], 'z': convoy_to[1], 'radius': 10},
                      failed('escape'), {'t': 'lose', 'reason': 'convoyEscaped'}),
                    T('caught', {'t': 'unitDestroyed', 'tag': 'convoy'}, done('convoy'), done('escape')),
                ],
                time_limit=12 * 60)

    # 5: scouting with radar to find hidden posts.
    sx, sz = RIDGE_START
    post = E['tower_radar']
    mission(f, 5, 'blind_ridge' if terran else 'eyes_of_the_brood',
            'Blind Ridge' if terran else 'Eyes of the Brood',
            ('Three hidden Arcadian posts in these hills are watching our supply roads, and each has a guard. A '
             'Watchman radar truck can spot them from far off. Find and destroy all three.') if terran else
            ('Three Terran listening posts hide in these hills, telling the colonies where we feed. A Seer can see '
             'them from far off. Find and destroy all three.'),
            'map.c_blind_ridge',
            [player_side(f, 600, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret', 'radar', 'tower_radar'),
                         research_done=research(f, 'towers', 'sensors')), enemy_side(e)],
            [U(1, R['light'], x, z, -0.7) for x, z in spread(sx + 8, sz - 8, 4)]
            + [U(1, R['radar'], sx + 2, sz - 2, -0.7), U(1, R['miner'], sx - 6, sz + 2), U(1, R['tug'], sx - 2, sz + 6)]
            + [U(2, E['light'], px + 5, pz + 5) for px, pz in RIDGE_POSTS]
            + [U(2, E['scout'], px - 5, pz + 5) for px, pz in RIDGE_POSTS[1:]],
            [S(1, R['pad'], sx, sz)] + [S(2, post, px, pz) for px, pz in RIDGE_POSTS],
            [('posts', 'Destroy the three hidden posts', 'primary')],
            [
                T('intro', at(0), msg('Move the Watchman ahead of your tanks. It spots enemies far beyond your guns.'
                                      if terran else 'Send the Seer ahead of the Lumens. It sees far beyond their reach.', f)),
                T('patrol', at(240), spawn(2, E['light'], 2, 0, 0, tag='patrol'), attack('patrol', sx, sz)),
                T('posts', {'t': 'allDestroyed', 'side': 2, 'unitType': post}, done('posts')),
            ],
            time_limit=25 * 60)

    # 6: heavy tanks, an escort or a breakthrough.
    rx, rz = ROAD_START
    vx, vz = RELAY
    if terran:
        mission(f, 6, 'heavy_metal', 'Heavy Metal',
                ('The relay station at the end of the road links the colonies to orbit. Two Bulwark heavy tanks are '
                 'going to guard it, but ambushes wait in the gaps between the ridges. Get both Bulwarks there.'),
                'map.c_relay_road',
                [player_side(f, 700, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret', 'radar', 'heavy'),
                             research_done=research(f, 'heavy', 'sensors')), enemy_side(e)],
                [U(1, R['heavy'], rx + 6, rz - 6, -0.785, tag='convoy'), U(1, R['heavy'], rx + 2, rz - 10, -0.785, tag='convoy')]
                + [U(1, R['light'], x, z, -0.785) for x, z in spread(rx + 10, rz - 2, 3)]
                + [U(1, R['miner'], rx - 6, rz + 2), U(1, R['tug'], rx - 2, rz + 6)],
                [S(1, R['pad'], rx, rz), S(1, R['tower_radar'], vx + 4, vz - 4)],
                [('relay', 'Bring both Bulwarks to the relay station', 'primary'),
                 ('convoy', 'Keep both Bulwarks alive', 'primary')],
                [
                    T('intro', at(0), msg('Send the Lancers ahead to spring the ambushes before the Bulwarks arrive.', f)),
                    T('amb1', area(1, -30, 30, 18), msg('Ambush in the first gap!', f),
                      spawn(2, E['light'], 2, -14, 2, tag='amb1'), spawn(2, E['scout'], 2, -40, 12, tag='amb1'),
                      attack('amb1', -30, 30)),
                    T('amb2', area(1, 10, -10, 18), msg('More of them at the second gap.', f),
                      spawn(2, E['light'], 3, 30, 4, tag='amb2'), spawn(2, E['missile'], 1, 0, -26, tag='amb2'),
                      attack('amb2', 10, -10)),
                    T('amb3', area(1, 50, -50, 18), spawn(2, E['heavy'], 1, 78, -48, tag='amb3'),
                      spawn(2, E['light'], 2, 50, -80, tag='amb3'), attack('amb3', 50, -50)),
                    T('lost', {'t': 'unitsAlive', 'tag': 'convoy', 'op': '<=', 'count': 1}, failed('convoy'),
                      {'t': 'lose', 'reason': 'convoyLost'}),
                    T('arrived', {'t': 'unitEscorted', 'tag': 'convoy', 'x': vx, 'z': vz, 'radius': 12},
                      done('relay'), done('convoy')),
                ],
                time_limit=20 * 60)
    else:
        guard = [(vx - 18, vz + 2), (vx - 2, vz + 18)]
        mission(f, 6, 'shell_and_spine', 'Shell and Spine',
                ('The Terrans hold a checkpoint at the end of the road: two Bastion Guns and a Radar Tower. Bring '
                 'your new Aegis tanks up the road and break it.'),
                'map.c_relay_road',
                [player_side(f, 700, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret', 'radar', 'heavy'),
                             research_done=research(f, 'heavy', 'sensors')), enemy_side(e)],
                [U(1, R['heavy'], x, z, -0.785) for x, z in spread(rx + 6, rz - 8, 2)]
                + [U(1, R['light'], x, z, -0.785) for x, z in spread(rx + 10, rz - 2, 3)]
                + [U(1, R['miner'], rx - 6, rz + 2), U(1, R['tug'], rx - 2, rz + 6)]
                + [U(2, E['light'], vx - 10, vz + 10), U(2, E['light'], vx - 14, vz + 6), U(2, E['missile'], vx - 6, vz + 14)],
                [S(1, R['pad'], rx, rz), S(2, E['turret'], *guard[0]), S(2, E['turret'], *guard[1]),
                 S(2, E['tower_radar'], vx, vz)],
                [('guns', 'Destroy both Bastion Guns', 'primary'), ('radar', 'Destroy the Radar Tower', 'primary')],
                [
                    T('intro', at(0), msg('Aegis tanks shrug off gunfire. Lead with them; keep the Lumens behind.', f)),
                    T('amb1', area(1, -30, 30, 18), spawn(2, E['light'], 2, -14, 2, tag='amb1'),
                      attack('amb1', -30, 30)),
                    T('amb2', area(1, 10, -10, 18), spawn(2, E['light'], 2, 30, 4, tag='amb2'),
                      spawn(2, E['scout'], 2, 0, -26, tag='amb2'), attack('amb2', 10, -10)),
                    T('guns', {'t': 'allDestroyed', 'side': 2, 'unitType': E['turret']}, done('guns')),
                    T('radar', {'t': 'allDestroyed', 'side': 2, 'unitType': E['tower_radar']}, done('radar')),
                ],
                time_limit=20 * 60)

    # 7: act 1 finale, a full match against an easy enemy.
    hx, hz = VALLEY_HOME
    ex, ez = VALLEY_ENEMY
    mission(f, 7, 'landfall_broken' if terran else 'root_and_ruin',
            'Landfall Broken' if terran else 'Root and Ruin',
            ('Every raid on Halden comes from the Arcadian landing nest in Kessra Valley. Javelin missile tanks are '
             'now in Build. Break the nest and everything defending it.') if terran else
            ('The colonies land their supplies in Kessra Valley. Flares are ready to grow. Tear down their Landing '
             'Pad, and the plains are ours to feed on.'),
            'map.c_kessra_valley',
            [player_side(f, 800, available=avail(f, 'light', 'scout', 'miner', 'tug', 'turret', 'radar', 'tower_radar',
                                                 'heavy', 'station', 'missile'),
                         research_done=research(f, 'heavy', 'sensors')),
             enemy_side(e, 'ai', ore=100, metal=0, difficulty='easy')],
            [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 8, hz - 8, 6)]
            + [U(1, R['miner'], hx - 8, hz + 2), U(1, R['tug'], hx - 4, hz + 8), U(1, R['radar'], hx + 2, hz - 4), U(1, R['heavy'], hx + 14, hz - 2, -0.785)]
            + [U(2, E['light'], x, z, 2.356) for x, z in spread(ex - 8, ez + 8, 3)]
            + [U(2, E['miner'], ex + 6, ez - 4), U(2, E['tug'], ex + 2, ez - 8)],
            [S(1, R['pad'], hx, hz), S(2, E['pad'], ex, ez), S(2, E['turret'], ex - 22, ez + 4)],
            [('pad', 'Destroy the Arcadian Landing Ring' if terran else 'Destroy the Terran Landing Pad', 'primary')]
            + ([('all', 'Destroy every enemy unit and building', 'primary')] if terran else []),
            [
                T('intro', at(0), msg('Mine, build up, then strike. The valley has two ways in.' if terran else
                                      'Feed first, then swarm. Two paths lead into the valley.', f)),
                T('pad', {'t': 'allDestroyed', 'side': 2, 'unitType': E['pad']}, done('pad')),
            ] + ([T('all', {'t': 'allDestroyed', 'side': 2}, done('all'))] if terran else []),
            time_limit=40 * 60)


act1('human')
act1('alien')


# ---------------------------------------------------------------- act 2 (both sides)

ACT2_BASE = ('towers', 'sensors', 'heavy')
# The lab is not bought any more (research starts from a locked card); missions may still place one.
ACT2_UNITS = ('light', 'scout', 'miner', 'tug', 'turret', 'radar', 'tower_radar', 'heavy', 'station')


def built(side, structure, count=1, x=None, z=None, radius=None):
    c = {'t': 'structureBuilt', 'side': side, 'structureType': structure, 'count': count}
    if radius is not None:
        c.update({'x': x, 'z': z, 'radius': radius})
    return c


def act2(f):
    e = OTHER[f]
    R, E = ROLE[f], ROLE[e]
    terran = f == 'human'

    def say(human_text, alien_text):
        return human_text if terran else alien_text

    # 8: breather. Metal and the first research of the player's own, started from a locked card
    # (the repair vehicle) or from the research building the colony already has.
    hx, hz = FIELDS_HOME
    start8 = research(f, *ACT2_BASE)
    lab = say('Research Lab', 'Star Vault')
    mender = say('Mender', 'Weaver')
    station = say('Metal Station', 'Metal Siphon')
    mission(f, 8, say('quiet_fields', 'gene_vault'), say('Quiet Fields', 'The Star Vault'),
            say('The Kessra nest is ash, but the rift still hangs over Vesper and more of them will come. We dig in '
                'for a long war. Use the quiet: put a Metal Station on the seam by Tallis colony, then research the '
                'Mender repair truck.',
                'The colony pad at Kessra burned, and the swarm spreads across the plains. While the Terrans lick '
                'their wounds, grow a Metal Siphon on the seam by the nest, then wake the Star Vault and research '
                'the Weaver.'),
            'map.c_quiet_fields',
            [player_side(f, 900, available=avail(f, *ACT2_UNITS, 'repair'), research_done=start8), enemy_side(e)],
            [U(1, R['light'], x, z, -0.7) for x, z in spread(hx + 10, hz - 10, 4)]
            + [U(1, R['heavy'], hx + 14, hz - 2, -0.7), U(1, R['miner'], hx - 10, hz - 4), U(1, R['tug'], hx + 4, hz + 10),
               U(1, R['tug'], hx + 8, hz + 8, tag='metalHauler')],
            [S(1, R['pad'], hx, hz), S(1, R['lab'], hx - 12, hz + 10)],
            [('station', say('Build a Metal Station', 'Grow a Metal Siphon'), 'primary'),
             ('research', f'Research the {mender}', 'primary'), ('raid', 'Drive off the scouting party', 'optional')],
            [
                T('intro', at(0), msg(say('Metal pays for research. Buy a Metal Station; it drives to the metal seam by itself.',
                                          'Metal feeds the Star Vault. Grow a Metal Siphon; it crawls to the seam by itself.'), f)),
                T('station', built(1, R['station']), done('station'),
                  msg(say(f'Station up. Send the spare Hauler to it, then tap the locked {mender} in Build to research it.',
                          f'Siphon grown. Send the spare Ferrier to it, then tap the locked {mender} in Build to research it.'), f)),
                T('research', {'t': 'researchDone', 'side': 1, 'node': f'research.{f}.field_repair'}, done('research')),
                T('scouts', at(240), msg(say('A small scouting party is coming in from the east.',
                                             'Terran scouts are sniffing around.'), f),
                  spawn(2, E['scout'], 3, 70, -10, tag='scouts'), spawn(2, E['light'], 1, 74, -4, tag='scouts'),
                  attack('scouts', hx, hz)),
                T('raid', {'t': 'and', 'conds': [at(250), {'t': 'unitDestroyed', 'tag': 'scouts'}]}, done('raid')),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']},
                  {'t': 'lose', 'reason': 'padLost'}),
            ],
            time_limit=20 * 60)

    # 9: artillery against towers on a hill.
    hx, hz = REACH_HOME
    gx, gz = REACH_HILL
    cx, cz = REACH_CAMP
    mission(f, 9, say('long_reach', 'slow_rain'), say('Long Reach', 'Slow Rain'),
            say('The Arcadians have dug guns into the hill at the centre of the valley. They outrange our tanks, but '
                'not our new Longbow artillery. Shell the hill until every gun is gone.',
                'The Terrans have fortified the hill in the middle of the valley. Their guns outrange our Lumens, '
                'but not our new Sunfalls. Rain on the hill until every gun is gone.'),
            'map.c_long_reach',
            [player_side(f, 700, available=avail(f, *ACT2_UNITS, 'artillery'),
                         research_done=research(f, *ACT2_BASE, 'artillery', 'repair')), enemy_side(e)],
            [U(1, R['artillery'], x, z, -0.785) for x, z in spread(hx + 4, hz - 4, 2)]
            + [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 14, hz - 12, 4)]
            + [U(1, R['heavy'], hx + 18, hz - 4, -0.785), U(1, R['miner'], hx - 8, hz - 2), U(1, R['tug'], hx - 2, hz + 8)]
            + [U(2, E['light'], x, z, 2.356) for x, z in spread(gx + 4, gz + 4, 3)]
            + [U(2, E['missile'], gx + 14, gz - 12, 2.356), U(2, E['light'], cx - 6, cz + 6), U(2, E['light'], cx + 4, cz - 2)],
            [S(1, R['pad'], hx, hz)] + [S(2, E['turret'], x, z) for x, z in REACH_GUNS] + [S(2, E['battery'], gx, gz)],
            [('guns', say('Destroy the Sentinels on the hill', 'Destroy the Bastion Guns on the hill'), 'primary'),
             ('battery', say('Destroy the Corona missile tower', 'Destroy the Harpoon Battery'), 'primary'),
             ('camp', 'Scout the camp behind the hill', 'optional')],
            [
                T('intro', at(0), msg(say('Longbows hit from far beyond the guns. Keep tanks in front of them to spot targets.',
                                          'Sunfalls strike from beyond the guns. Keep Lumens ahead of them to spot.'), f)),
                T('ca1', at(300), msg(say('Counter-attack coming off the hill!', 'They pour down off the hill at us!'), f),
                  spawn(2, E['light'], 3, gx - 10, gz + 10, tag='ca1'), attack('ca1', hx, hz)),
                T('ca2', at(560), spawn(2, E['light'], 2, gx - 10, gz + 10, tag='ca2'),
                  spawn(2, E['heavy'], 1, gx - 14, gz + 6, tag='ca2'), attack('ca2', hx, hz)),
                T('guns', {'t': 'allDestroyed', 'side': 2, 'unitType': E['turret']}, done('guns')),
                T('battery', {'t': 'allDestroyed', 'side': 2, 'unitType': E['battery']}, done('battery')),
                T('campDone', area(1, cx, cz, 14), done('camp')),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
            ],
            time_limit=25 * 60)

    # 10: hover units across water.
    hx, hz = DELTA_HOME
    cx, cz = DELTA_CAMP
    hover = say('Skimmers', 'Gliders')
    mission(f, 10, say('river_run', 'over_the_water'), say('River Run', 'Over the Water'),
            say(f'An Arcadian camp sits on the far side of the delta. Tanks must go the long way round by the southern '
                f'ford; our new {hover} float straight across the water. Take the far bank and destroy the camp.',
                f'A Terran camp sits beyond the river channels. Lumens must crawl round by the southern ford; '
                f'our new {hover} skim straight over the water. Reach the far bank and raze the camp.'),
            'map.c_delta',
            [player_side(f, 600, available=avail(f, *ACT2_UNITS, 'hover', 'missile'),
                         research_done=research(f, *ACT2_BASE, 'hover', 'artillery')), enemy_side(e)],
            [U(1, R['hover'], x, z, 0.0) for x, z in spread(hx + 10, hz, 6)]
            + [U(1, R['light'], x, z, 0.0) for x, z in spread(hx + 4, hz + 12, 2)]
            + [U(1, R['miner'], hx - 8, hz - 8), U(1, R['tug'], hx - 6, hz + 8)]
            + [U(2, E['light'], x, z, 3.14) for x, z in spread(cx - 6, cz, 2)]
            + [U(2, E['scout'], 50, -60), U(2, E['scout'], 54, 50)],
            [S(1, R['pad'], hx, hz), S(1, R['turret'], hx + 14, hz - 4), S(2, E['turret'], cx - 16, cz),
             S(2, E['tower_radar'], cx + 8, cz + 6), S(2, E['lab'], cx + 6, cz - 10)],
            [('bank', 'Reach the far bank', 'primary'), ('camp', 'Destroy the camp', 'primary')],
            [
                T('intro', at(0), msg(say('Skimmers ride over water. Select them and tap the far bank.',
                                          'Gliders ride over water. Select them and tap the far bank.'), f)),
                T('bank', area(1, cx - 26, cz, 14), done('bank'),
                  msg(say('Far bank taken. Now the camp.', 'The far bank is ours. Now the camp.'), f)),
                T('raid', at(200), msg(say('Raiders crossing toward the colony. The Bastion Gun will help.',
                                          'Raiders crossing toward the nest. The Sentinel will help.'), f),
                  spawn(2, E['scout'], 3, 50, 10, tag='raid'), attack('raid', hx, hz)),
                T('raid2', at(420), spawn(2, E['hover'], 2, 50, -20, tag='raid2'), spawn(2, E['light'], 2, 30, 90, tag='raid2'),
                  attack('raid2', hx, hz)),
                T('camp', {'t': 'and', 'conds': [{'t': 'allDestroyed', 'side': 2, 'unitType': E['turret']},
                                                  {'t': 'allDestroyed', 'side': 2, 'unitType': E['tower_radar']},
                                                  {'t': 'allDestroyed', 'side': 2, 'unitType': E['lab']}]}, done('camp')),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
            ],
            time_limit=20 * 60)

    # 11: five timed waves, with repair units.
    hx, hz = FIELDS_HOME
    mender = say('Mender', 'Weaver')
    wave_from = [(70, -70), (76, 6), (-4, -80), (70, -70), (40, 70)]
    waves = [
        [('light', 3)],
        [('light', 3), ('scout', 2)],
        [('heavy', 1), ('light', 3)],
        [('missile', 2), ('light', 2), ('artillery', 1)],
        [('heavy', 2), ('light', 3), ('artillery', 1)],
    ]
    wave_triggers = []
    for i, (group, (wx, wz)) in enumerate(zip(waves, wave_from)):
        tag = f'w{i + 1}'
        acts = [spawn(2, E[role], n, wx, wz, tag=tag) for role, n in group]
        if i == 0:
            acts.insert(0, msg(say('First wave inbound.', 'The first wave comes.'), f))
        if i == 4:
            acts.insert(0, msg(say('Last wave. Everything they have left.', 'The last wave. Break it and they are spent.'), f))
        wave_triggers.append(T(tag, at(60 + i * 110), *acts, attack(tag, hx, hz)))
    mission(f, 11, say('siege_of_tallis', 'the_long_hunger'), say('Siege of Tallis', 'The Long Hunger'),
            say('Tallis colony is about to be hit by five waves, each bigger than the last. Hold for ten minutes. '
                'Harpoon Battery missile towers are now in Build, and they outrange tanks.',
                'The Terrans will throw five waves at our siphon nest, each bigger than the last. Hold for ten '
                'minutes. Coronas are ready to grow, and they outrange Terran tanks.'),
            'map.c_quiet_fields',
            [player_side(f, 1100, available=avail(f, *ACT2_UNITS, 'missile', 'artillery', 'battery', 'repair'),
                         research_done=research(f, *ACT2_BASE, 'artillery', 'repair')), enemy_side(e)],
            [U(1, R['light'], x, z, -0.7) for x, z in spread(hx + 14, hz - 14, 4)]
            + [U(1, R['heavy'], hx + 20, hz - 8, -0.7), U(1, R['repair'], hx + 8, hz - 6),
               U(1, R['miner'], hx - 10, hz - 4), U(1, R['tug'], hx + 4, hz + 10)],
            [S(1, R['pad'], hx, hz), S(1, R['turret'], hx + 18, hz - 20), S(1, R['station'], -42, 72)],
            [('hold', 'Hold the colony for 10 minutes' if terran else 'Hold the nest for 10 minutes', 'primary')],
            [
                T('intro', at(0), msg(say(f'Waves come from the east and north. Keep the {mender} behind your line.',
                                          f'They come from the east and north. Keep the {mender} behind the brood.'), f)),
                *wave_triggers,
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, failed('hold'),
                  {'t': 'lose', 'reason': 'padLost'}),
                T('held', at(600), done('hold')),
            ])

    # 12: claim three metal sites the enemy also wants.
    hx, hz = FIELDS_HOME
    held = [S(2, E['station'], x, z) for x, z in FIELDS_SITES[:2]]
    guards = [U(2, E['light'], x + 6, z + 4, 3.14) for x, z in FIELDS_SITES[:2]] + \
             [U(2, E['light'], x - 6, z - 4, 3.14) for x, z in FIELDS_SITES]
    mission(f, 12, say('salvage_rights', 'metal_veins'), say('Salvage Rights', 'Metal Veins'),
            say('Three rich metal seams lie east of Tallis, and the Arcadians have siphoned two of them to feed '
                'their research. Destroy their Metal Siphons and put our own Metal Stations on all three seams.',
                'Three rich metal seams lie east of the nest, and the Terrans mine two of them for their research. '
                'Tear their Metal Stations down and grow our siphons on all three.'),
            'map.c_quiet_fields',
            [player_side(f, 1000, available=avail(f, *ACT2_UNITS, 'missile', 'artillery', 'battery', 'repair'),
                         research_done=research(f, *ACT2_BASE, 'artillery', 'repair')), enemy_side(e)],
            [U(1, R['light'], x, z, -0.7) for x, z in spread(hx + 14, hz - 14, 4)]
            + [U(1, R['heavy'], x, z, -0.7) for x, z in spread(hx + 22, hz - 4, 2)]
            + [U(1, R['miner'], hx - 10, hz - 4), U(1, R['tug'], hx + 4, hz + 10), U(1, R['tug'], hx + 8, hz + 8)]
            + guards,
            # Both home seams already have a station, so every new one heads for an eastern seam.
            [S(1, R['pad'], hx, hz), S(1, R['station'], -42, 72), S(1, R['station'], -76, 30)] + held,
            [('sites', say('Put a Metal Station on all three eastern seams', 'Grow a Metal Siphon on all three eastern seams'),
              'primary'),
             ('keep', 'Keep your landing pad' if terran else 'Keep your Landing Ring', 'primary')],
            [
                T('intro', at(0), msg(say('Our home seams are taken, so new stations head east. Tap a marked seam to send one there.',
                                          'Our home seams are full, so new siphons crawl east. Tap a marked seam to steer one.'), f)),
                T('shard', at(120), msg(say('Survey teams report crystal spires growing under the rift. Nobody knows what they are.',
                                            'Something sings beneath the rift. Crystal grows there, and it is not ours.'), f)),
                T('r1', at(240), msg(say('Raiders heading for the seams.', 'Terran raiders are making for the seams.'), f),
                  spawn(2, E['light'], 3, 80, -30, tag='r1'), attack('r1', *FIELDS_SITES[0])),
                T('r2', at(480), spawn(2, E['light'], 2, 20, -85, tag='r2'), spawn(2, E['missile'], 2, 26, -85, tag='r2'),
                  attack('r2', *FIELDS_SITES[2])),
                T('r3', at(720), spawn(2, E['heavy'], 2, 80, 60, tag='r3'), spawn(2, E['light'], 2, 84, 54, tag='r3'),
                  attack('r3', *FIELDS_SITES[1])),
                T('sites', {'t': 'and', 'conds': [built(1, R['station'], 1, x, z, 10) for x, z in FIELDS_SITES]},
                  done('sites'), done('keep')),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, failed('keep'),
                  {'t': 'lose', 'reason': 'padLost'}),
            ],
            time_limit=25 * 60)

    # 13: hunt a commander that keeps moving, before it slips away.
    hx, hz = REACH_HOME
    route = [(66, -66), (70, 20), (20, 70), (-40, -10), (-70, -70), (40, -70)]
    legs = [T(f'leg{i}', at(40 + i * 100), attack('boss', x, z), attack('court', x, z), reveal(x, z))
            for i, (x, z) in enumerate(route[1:], start=1)]
    exit_x, exit_z = 96, -96
    mission(f, 13, say('the_matriarch', 'the_iron_colonel'), say('The Matriarch', 'The Iron Colonel'),
            say('Intercepts name the Arcadian leader on Vesper: the Matriarch. She rides an Aegis heavy tank and is '
                'touring the valley with her guard. Destroy her before she leaves through the north-east pass in ten '
                'minutes.',
                'Colonel Daska, the one his troops call the Iron Colonel, commands the Terrans on Vesper. He is touring '
                'the valley in a Bulwark with an escort. Destroy him before he leaves through the north-east pass in '
                'ten minutes.'),
            'map.c_long_reach',
            [player_side(f, 900, available=avail(f, *ACT2_UNITS, 'missile', 'artillery', 'battery', 'repair', 'hover'),
                         research_done=research(f, *ACT2_BASE, 'artillery', 'repair', 'hover')), enemy_side(e)],
            [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 14, hz - 12, 4)]
            + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(hx + 22, hz - 2, 2)]
            + [U(1, R['missile'], hx + 6, hz - 16, -0.785), U(1, R['radar'], hx + 4, hz - 4, -0.785),
               U(1, R['miner'], hx - 8, hz - 2), U(1, R['tug'], hx - 2, hz + 8)]
            + [U(2, E['heavy'], 66, -66, 2.356, tag='boss')]
            # The boss is the only heavy tank on the map, so the player can tell it from its guard.
            + [U(2, E['missile'], 60, -60, 2.356, tag='court'), U(2, E['missile'], 72, -60, 2.356, tag='court'),
               U(2, E['light'], 60, -72, 2.356, tag='court'), U(2, E['light'], 72, -72, 2.356, tag='court')]
            + [U(2, E['light'], x, z) for x, z in [(10, 10), (-30, 30), (40, 40)]],
            [S(1, R['pad'], hx, hz), S(2, E['turret'], 60, -40)],
            [('boss', say("Destroy the Matriarch's Aegis", "Destroy the Iron Colonel's Bulwark"), 'primary')],
            [
                T('intro', at(0), msg(say('She rides the only Aegis in her guard. We will flag each place she heads for.',
                                          'His is the only Bulwark in the escort. I will show you where he goes next.'), f),
                  reveal(66, -66)),
                *legs,
                T('flee', at(560), msg(say('She is making for the pass!', 'He is making for the pass!'), f),
                  attack('boss', exit_x, exit_z), attack('court', exit_x, exit_z)),
                T('escaped', {'t': 'unitEscorted', 'tag': 'boss', 'x': exit_x, 'z': exit_z, 'radius': 8},
                  failed('boss'), {'t': 'lose', 'reason': 'bossEscaped'}),
                T('boss', {'t': 'unitDestroyed', 'tag': 'boss'}, done('boss')),
            ],
            time_limit=15 * 60)

    # 14: act 2 finale, a normal enemy with a fortified forward base.
    hx, hz = GATE_HOME
    ex, ez = GATE_ENEMY
    mission(f, 14, say('counterpunch', 'breach'), say('Counterpunch', 'Breach'),
            say('With the Matriarch dead, the broods are fighting without a plan. Hit them before they find one: '
                'their forward base sits behind the Iron Gate ridges. Destroy every building in it.',
                'With the Iron Colonel dead, the Terrans are leaderless and afraid. Their forward base hides behind '
                'the Iron Gate ridges. Break through and leave nothing standing.'),
            'map.c_iron_gate',
            [player_side(f, 1200, available=avail(f, *ACT2_UNITS, 'missile', 'artillery', 'battery', 'repair', 'hover'),
                         research_done=research(f, *ACT2_BASE, 'artillery', 'repair', 'hover')),
             enemy_side(e, 'ai', ore=0, metal=100, difficulty='normal')],
            [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 14, hz - 14, 4)]
            + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(hx + 24, hz - 4, 2)]
            + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10), U(1, R['radar'], hx + 4, hz - 4)]
            + [U(2, E['light'], x, z, 2.356) for x, z in spread(ex - 12, ez + 12, 4)]
            + [U(2, E['heavy'], ex - 18, ez + 2, 2.356), U(2, E['miner'], ex + 8, ez - 4), U(2, E['tug'], ex + 4, ez - 10)],
            [S(1, R['pad'], hx, hz), S(2, E['pad'], ex, ez), S(2, E['turret'], ex - 26, ez + 6),
             S(2, E['turret'], ex - 6, ez + 26), S(2, E['battery'], ex - 18, ez + 18), S(2, E['tower_radar'], ex + 14, ez + 10)],
            [('base', 'Destroy every enemy building', 'primary')],
            [
                T('intro', at(0), msg(say('Three ways in. The guns cover the west gap; artillery can open it.',
                                          'Three paths in. Their guns watch the west one; Sunfalls can open it.'), f)),
                T('base', {'t': 'and', 'conds': [{'t': 'allDestroyed', 'side': 2, 'unitType': E[k]}
                                                  for k in ('pad', 'turret', 'battery', 'tower_radar', 'station', 'lab')]},
                  done('base')),
            ],
            time_limit=45 * 60)


act2('human')
act2('alien')


# ---------------------------------------------------------------- act 3 (both sides)

# The finale's enemy AI (hard, per the outline: the last three missions use hard AI). The Terran
# finale also starts with more ore: against a hard AI and the Shard, 2000 lost on some seeds.
def FINALE_AI(e):
    return enemy_side(e, 'ai', ore=500, metal=200, difficulty='hard')


SHARD_CORE = 'structure.alien.shard_core'
SHARD_SPIRE = 'structure.alien.shard_spire'
ACT3_UNITS = ACT2_UNITS + ('missile', 'artillery', 'battery', 'repair', 'hover', 'air_base', 'fighter')


def act3(f):
    e = OTHER[f]
    R, E = ROLE[f], ROLE[e]
    terran = f == 'human'

    def say(human_text, alien_text):
        return human_text if terran else alien_text

    base_research = research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'air')
    # Arcadians also get the Dragonfly, an interceptor that only hits aircraft.
    units3 = ACT3_UNITS + (() if terran else ('dragonfly',))

    # 15: breather. The first air base and fighters.
    hx, hz = HIGH_HOME
    ex, ez = HIGH_ENEMY
    mission(f, 15, say('wings', 'hive_roost'), say('Wings', 'Aerie'),
            say('Survey drones over the rift saw something pulsing at its heart: a crystal we are calling the '
                'Shard. Before we can get near it, we need the sky. Build an Airfield, buy Falcon fighters and clear '
                'four Arcadian raiders out of the air.',
                'At the heart of the rift the Shard has stirred, and its crystals now burn Arcadian and Terran alike. '
                'Terran fighters keep stinging the brood. Grow an Aerie, raise Halos and bring down the four raiders; '
                'Dragonflies hunt only fliers.'),
            'map.c_highwater',
            [player_side(f, 1100, available=avail(f, *units3), research_done=base_research), enemy_side(e)],
            [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 14, hz - 12, 3)]
            + [U(1, R['missile'], x, z, -0.785) for x, z in spread(hx + 20, hz - 4, 2)]
            + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10), U(1, R['tug'], hx + 2, hz + 10)]
            + [U(2, E['light'], x, z, 2.356) for x, z in spread(ex - 12, ez + 10, 2)],
            [S(1, R['pad'], hx, hz), S(2, E['air_base'], ex, ez)],
            [('roost', say('Build an Airfield', 'Grow an Aerie'), 'primary'),
             ('sky', 'Destroy the four enemy raiders', 'primary')],
            [
                T('intro', at(0), msg(say('Buy an Airfield first: aircraft need it to land and rearm.',
                                          'Grow an Aerie first: fliers need it to land and feed.'), f)),
                T('raid1', at(90), msg(say('Raiders inbound!', 'Terran fighters, coming in fast!'), f),
                  spawn(2, E['fighter'], 2, ex - 20, ez, tag='sky', launch=True), attack('sky', hx, hz)),
                T('raid2', at(300), spawn(2, E['fighter'], 2, ex, ez - 20, tag='sky', launch=True), attack('sky', hx, hz)),
                T('roost', built(1, R['air_base']), done('roost')),
                T('sky', {'t': 'and', 'conds': [at(301), {'t': 'unitDestroyed', 'tag': 'sky'}]}, done('sky')),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
            ],
            time_limit=25 * 60)

    # 16: strike targets from the air past anti-air.
    targets = [(40, -20), (20, -50), (60, -40), (50, 10)]
    if terran:
        mission(f, 16, 'bombing_run', 'Bombing Run',
                'Four Arcadian Sentinels guard the eastern plain on the road to the rift, covered by two Corona '
                'missile towers. Condor bombers can level them from above; Falcons keep the sky clear.',
                'map.c_highwater',
                [player_side(f, 900, available=avail(f, *units3, 'bomber'), research_done=base_research),
                 enemy_side(e)],
                [U(1, R['bomber'], hx + 6, hz - 6), U(1, R['bomber'], hx + 8, hz - 2), U(1, R['fighter'], hx + 4, hz - 10)]
                + [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 16, hz - 14, 4)]
                + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10)]
                + [U(2, E['light'], x + 6, z + 6, 2.356) for x, z in targets[:2]],
                [S(1, R['pad'], hx, hz), S(1, R['air_base'], hx + 10, hz - 18)]
                + [S(2, E['turret'], x, z) for x, z in targets]
                + [S(2, E['battery'], 30, -30), S(2, E['battery'], 64, -16)],
                [('towers', 'Destroy the four Sentinels', 'primary'), ('aa', 'Destroy both Corona towers', 'optional')],
                [
                    T('intro', at(0), msg('Select the Condors and tap a Sentinel to bomb it. Stay clear of the Coronas.', f)),
                    T('patrol', at(200), msg('Enemy fliers scrambled.', f),
                      spawn(2, E['fighter'], 2, ex, ez, tag='patrol', launch=True), attack('patrol', hx, hz)),
                    T('towers', {'t': 'allDestroyed', 'side': 2, 'unitType': E['turret']}, done('towers')),
                    T('aa', {'t': 'allDestroyed', 'side': 2, 'unitType': E['battery']}, done('aa')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
                ],
                time_limit=25 * 60)
    else:
        mission(f, 16, 'burning_sky', 'Burning Sky',
                'Four Terran Harpoon Batteries cover the eastern plain, and their Falcons patrol above. Halos rule the '
                'sky: sweep the Falcons away so the Sunfalls and Gliders can burn all four batteries.',
                'map.c_highwater',
                [player_side(f, 900, available=avail(f, *units3), research_done=base_research), enemy_side(e)],
                [U(1, R['fighter'], hx + 6, hz - 6), U(1, R['fighter'], hx + 8, hz - 2), U(1, R['fighter'], hx + 4, hz - 10)]
                + [U(1, R['artillery'], x, z, -0.785) for x, z in spread(hx + 12, hz - 20, 2)]
                + [U(1, R['hover'], x, z, -0.785) for x, z in spread(hx + 18, hz - 12, 3)]
                + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10)]
                + [U(2, E['light'], x + 6, z + 6, 2.356) for x, z in targets[:2]],
                [S(1, R['pad'], hx, hz), S(1, R['air_base'], hx + 10, hz - 18), S(2, E['air_base'], ex, ez)]
                + [S(2, E['battery'], x, z) for x, z in targets],
                [('towers', 'Destroy the four Harpoon Batteries', 'primary')],
                [
                    T('intro', at(0), msg('Launch the Halos to clear the sky, then send the ground brood in.', f)),
                    T('patrol', at(60), spawn(2, E['fighter'], 2, ex, ez, tag='patrol', launch=True), attack('patrol', hx, hz)),
                    T('patrol2', at(260), spawn(2, E['fighter'], 2, ex, ez, tag='patrol2', launch=True),
                      attack('patrol2', hx, hz)),
                    T('towers', {'t': 'allDestroyed', 'side': 2, 'unitType': E['battery']}, done('towers')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
                ],
                time_limit=25 * 60)

    # 17: saucers.
    if terran:
        mission(f, 17, 'saucer_season', 'Saucer Season',
                'The Arcadians have grown Discs: heavy saucers that burn whatever is under them. Waves of them will '
                'come at the colony. Shoot down six, then destroy the two Aeries they fly from. Falcons and Javelins '
                'can reach them.',
                'map.c_highwater',
                [player_side(f, 1200, available=avail(f, *units3, 'bomber'), research_done=base_research),
                 enemy_side(e)],
                [U(1, R['missile'], x, z, -0.785) for x, z in spread(hx + 14, hz - 12, 3)]
                + [U(1, R['fighter'], hx + 6, hz - 6), U(1, R['fighter'], hx + 8, hz - 2)]
                + [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 20, hz - 2, 2)]
                + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10)],
                [S(1, R['pad'], hx, hz), S(1, R['air_base'], hx + 10, hz - 18), S(2, E['air_base'], ex, ez),
                 S(2, E['air_base'], ex - 14, ez + 6)],
                [('saucers', 'Shoot down six Discs', 'primary'), ('roosts', 'Destroy both Aeries', 'primary')],
                [
                    T('intro', at(0), msg('Discs must fly right over a target to hit it. Meet them with missiles.', f)),
                    *[T(f's{i}', at(60 + i * 90), spawn(2, E['saucer'], 2, ex - 10, ez + 10, tag='saucers', launch=True),
                        attack('saucers', hx, hz)) for i in range(4)],
                    T('saucers', {'t': 'and', 'conds': [at(331), {'t': 'unitsAlive', 'tag': 'saucers', 'op': '<=', 'count': 2}]},
                      done('saucers')),
                    T('roosts', {'t': 'allDestroyed', 'side': 2, 'unitType': E['air_base']}, done('roosts')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
                ],
                time_limit=20 * 60)
    else:
        route = [(60, 60), (0, 70), (-60, 20), (-80, -40)]
        mission(f, 17, 'the_disc', 'The Disc',
                'The brood has grown its first Discs, heavy saucers that burn whatever lies beneath them. A Terran tank '
                'column is crossing the plain toward the western pass. Burn it before it gets through.',
                'map.c_highwater',
                [player_side(f, 1000, available=avail(f, *units3, 'saucer'), research_done=research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'disc')),
                 enemy_side(e)],
                [U(1, R['saucer'], hx + 6, hz - 6), U(1, R['saucer'], hx + 8, hz - 2), U(1, R['saucer'], hx + 4, hz - 10)]
                + [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 16, hz - 14, 3)]
                + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10)]
                + [U(2, E['light'], x, z, 2.356, tag='column') for x, z in spread(ex, ez + 20, 4)]
                + [U(2, E['heavy'], ex - 10, ez + 12, 2.356, tag='column'), U(2, E['missile'], ex + 8, ez + 28, 2.356, tag='column')],
                [S(1, R['pad'], hx, hz), S(1, R['air_base'], hx + 10, hz - 18), S(1, R['air_base'], hx + 22, hz - 10)],
                [('column', 'Destroy the tank column', 'primary')],
                [
                    T('intro', at(0), msg('Discs fly over the column and burn it. The Javelin missile tank can shoot back: '
                                          'kill it first.', f)),
                    *[T(f'leg{i}', at(30 + i * 110), attack('column', x, z)) for i, (x, z) in enumerate(route)],
                    T('escaped', {'t': 'unitEscorted', 'tag': 'column', 'x': -80, 'z': -40, 'radius': 12},
                      failed('column'), {'t': 'lose', 'reason': 'columnEscaped'}),
                    T('column', {'t': 'unitDestroyed', 'tag': 'column'}, done('column')),
                ],
                time_limit=15 * 60)

    # 18: two places to defend at once.
    ax, az = TWIN_A
    bx, bz = TWIN_B
    ex, ez = TWIN_ENEMY
    waves = [(60, 'a'), (150, 'b'), (240, 'a'), (330, 'b'), (420, 'a'), (510, 'b'), (600, 'a'), (660, 'b')]
    wave_triggers = []
    for i, (sec, which) in enumerate(waves):
        tx, tz = (ax, az) if which == 'a' else (bx, bz)
        group = [spawn(2, E['light'], 2 + i // 3, ex, ez, tag=f'w{i}')]
        if i >= 2:
            group.append(spawn(2, E['heavy'], 1 + i // 5, ex - 6, ez + 6, tag=f'w{i}'))
        if i >= 4:
            group.append(spawn(2, E['missile'], 1, ex + 6, ez - 6, tag=f'w{i}'))
        wave_triggers.append(T(f'w{i}', at(sec), *group, attack(f'w{i}', tx, tz)))
    if terran:
        mission(f, 18, 'two_fronts', 'Two Fronts',
                'The swarm is pushing for two colonies: Ashby in the west and Corran in the south. Hold both for '
                'twelve minutes. The waves switch between them, so split your forces or move fast.',
                'map.c_twin_colonies',
                [player_side(f, 1400, available=avail(f, *units3, 'bomber'), research_done=base_research),
                 enemy_side(e)],
                [U(1, R['light'], x, z, 0.0) for x, z in spread(ax + 14, az, 3)]
                + [U(1, R['light'], x, z, -1.57) for x, z in spread(bx, bz - 14, 3)]
                + [U(1, R['heavy'], ax + 18, az + 8), U(1, R['heavy'], bx + 8, bz - 18)]
                + [U(1, R['miner'], ax - 8, az - 10), U(1, R['tug'], ax - 4, az + 8), U(1, R['miner'], bx - 10, bz + 8),
                   U(1, R['tug'], bx + 8, bz + 4)],
                [S(1, R['pad'], ax, az), S(1, R['pad'], bx, bz), S(1, R['turret'], ax + 16, az - 8), S(1, R['turret'], bx + 8, bz - 16)],
                [('hold', 'Hold both colonies for 12 minutes', 'primary')],
                [
                    T('intro', at(0), msg('Watch both colonies. The first wave hits Ashby in one minute.', f)),
                    *wave_triggers,
                    T('padLost', {'t': 'not', 'cond': built(1, R['pad'], 2)}, failed('hold'), {'t': 'lose', 'reason': 'colonyLost'}),
                    T('held', at(720), done('hold')),
                ])
    else:
        rx, rz = 30, 40
        mission(f, 18, 'orbital_relay', 'Orbital Relay',
                'The Terran orbital relay stands on the plain south-west of our nest; through it the colonies call to '
                'orbit for help. Destroy the relay tower and its guns while both colonies send raids at the nest.',
                'map.c_twin_colonies',
                [player_side(f, 1300, available=avail(f, *units3, 'saucer'),
                             research_done=research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'disc')),
                 enemy_side(e)],
                [U(1, R['light'], x, z, -0.785) for x, z in spread(ex - 18, ez + 14, 4)]
                + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(ex - 24, ez + 4, 2)]
                + [U(1, R['artillery'], ex - 10, ez + 20), U(1, R['miner'], ex + 10, ez + 2), U(1, R['tug'], ex + 4, ez + 10)]
                + [U(2, E['light'], x, z) for x, z in spread(rx - 8, rz - 8, 3)] + [U(2, E['missile'], rx + 10, rz)],
                [S(1, R['pad'], ex, ez), S(1, R['turret'], ex - 14, ez + 14),
                 S(2, E['tower_radar'], rx, rz), S(2, E['turret'], rx - 12, rz - 6), S(2, E['turret'], rx + 6, rz - 12),
                 S(2, E['pad'], ax, az), S(2, E['pad'], bx, bz)],
                [('relay', 'Destroy the relay tower', 'primary'), ('guns', "Destroy the relay's Bastion Guns", 'primary'),
                 ('nest', 'Keep your Landing Ring', 'primary')],
                [
                    T('intro', at(0), msg('The relay is south-west of the nest. Raids will come from both colonies.', f)),
                    *[T(t['id'], t['when'], *[a if a['t'] != 'spawn' else {**a, 'x': ax if i % 2 == 0 else bx,
                                                                         'z': az if i % 2 == 0 else bz}
                                              for a in t['do'] if a['t'] != 'aiOrder'],
                        attack(f'w{i}', ex, ez)) for i, t in enumerate(wave_triggers[:6])],
                    T('relay', {'t': 'allDestroyed', 'side': 2, 'unitType': E['tower_radar']}, done('relay')),
                    T('guns', {'t': 'allDestroyed', 'side': 2, 'unitType': E['turret']}, done('guns')),
                    T('nestKept', {'t': 'and', 'conds': [{'t': 'objectiveDone', 'id': 'relay'}, {'t': 'objectiveDone', 'id': 'guns'}]},
                      done('nest')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, failed('nest'),
                      {'t': 'lose', 'reason': 'padLost'}),
                ],
                time_limit=25 * 60)

    # 19: the Shard wakes. Spires shoot at everyone.
    hx, hz = FIELD_HOME
    gx, gz = FIELD_EDGE
    spires = [S(3, SHARD_SPIRE, x, z) for x, z in FIELD_SPIRES]
    if terran:
        mission(f, 19, 'dead_zone', 'Dead Zone',
                'The Shard has grown spires across the ground near the rift, and they fire on anything that moves, '
                'Arcadian or Terran. Get a Watchman to the rift\'s edge in the north-east so we can see what lies '
                'beyond. Keep it alive.',
                'map.c_crystal_fields',
                [player_side(f, 1200, available=avail(f, *units3, 'bomber'), research_done=base_research),
                 enemy_side(e), enemy_side('alien', player=3)],
                [U(1, R['radar'], hx + 8, hz - 8, -0.785, tag='eye')]
                + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(hx + 18, hz - 10, 3)]
                + [U(1, R['artillery'], x, z, -0.785) for x, z in spread(hx + 10, hz - 22, 2)]
                + [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 24, hz - 22, 3)]
                + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10)]
                + [U(2, E['light'], x, z) for x, z in spread(40, 10, 3)] + [U(2, E['heavy'], gx - 16, gz + 10)],
                [S(1, R['pad'], hx, hz)] + spires,
                [('edge', 'Bring the Watchman to the rift\'s edge', 'primary'), ('eye', 'Keep the Watchman alive', 'primary')],
                [
                    T('intro', at(0), msg('Spires hit hard and far. Artillery can break them from outside their reach.', f)),
                    T('patrol', at(240), spawn(2, E['light'], 3, gx - 10, gz + 10, tag='patrol'), attack('patrol', hx, hz)),
                    T('eyeLost', {'t': 'unitDestroyed', 'tag': 'eye'}, failed('eye'), {'t': 'lose', 'reason': 'radarLost'}),
                    T('edge', {'t': 'unitEscorted', 'tag': 'eye', 'x': gx, 'z': gz, 'radius': 12}, done('edge'), done('eye')),
                ],
                time_limit=25 * 60, relations=at_war(2, 3))
    else:
        mission(f, 19, 'shard_song', 'Shard Song',
                'The brood has nested among the Shard\'s crystals at the rift. Learn its song and the rift will open '
                'wide for the whole swarm, but the Shard grows restless and serves no one. Hold the nest for ten '
                'minutes against the Terrans and the spires both.',
                'map.c_crystal_fields',
                [player_side(f, 1200, available=avail(f, *units3, 'saucer'),
                             research_done=research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'disc')),
                 enemy_side(e), enemy_side('alien', player=3)],
                [U(1, R['heavy'], x, z, 2.356) for x, z in spread(gx - 16, gz + 14, 3)]
                + [U(1, R['artillery'], x, z, 2.356) for x, z in spread(gx - 8, gz + 22, 2)]
                + [U(1, R['light'], x, z, 2.356) for x, z in spread(gx - 24, gz + 4, 3)]
                + [U(1, R['repair'], gx - 4, gz + 10), U(1, R['miner'], gx + 10, gz - 2), U(1, R['tug'], gx + 4, gz - 10)],
                [S(1, R['pad'], gx, gz), S(1, R['turret'], gx - 18, gz + 2)] + spires,
                [('hold', 'Hold the nest for 10 minutes', 'primary'), ('spires', 'Shatter all five spires', 'optional')],
                [
                    T('intro', at(0), msg('The spires are quiet for the moment. Get ready.', f)),
                    T('wake', at(120), msg('The Shard is singing. The spires are turning on us!', f),
                      {'t': 'setRelation', 'a': 1, 'b': 3, 'relation': 'hostile'}),
                    *[T(f't{i}', at(90 + i * 110), spawn(2, E['light'], 2 + i, hx + 10, hz - 10, tag=f't{i}'),
                        spawn(2, E['heavy'], 1 + i // 3, hx + 16, hz - 4, tag=f't{i}'),
                        *([spawn(2, E['missile'], 1, hx + 4, hz - 16, tag=f't{i}')] if i >= 3 else []),
                        attack(f't{i}', gx, gz))
                      for i in range(5)],
                    T('spires', {'t': 'allDestroyed', 'side': 3, 'unitType': SHARD_SPIRE}, done('spires')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, failed('hold'),
                      {'t': 'lose', 'reason': 'padLost'}),
                    T('held', at(600), done('hold')),
                ],
                relations=at_war(2, 3), neutral=(3,))

    # 20: two enemy teams at once (allied with each other).
    hx, hz = RIFT_HOME
    a_x, a_z = RIFT_ENEMY_A
    b_x, b_z = RIFT_ENEMY_B
    sx, sz = RIFT_SHARD
    mission(f, 20, say('brood_war', 'two_banners'), say('Brood War', 'Two Banners'),
            say('Without the Matriarch two broods hold the rift, each on its own: one to the east, one '
                'to the north. Destroy both of their Landing Rings.',
                'With their relay gone, the Coalition has hired a mercenary company to hold the rift against us. The '
                'Coalition base lies east of it, the mercenaries to the north. Destroy both Landing Pads.'),
            'map.c_rift',
            [player_side(f, 1600, available=avail(f, *units3, *(('bomber',) if terran else ('saucer',))),
                         research_done=base_research if terran else research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'disc')),
             enemy_side(e, 'ai', ore=300, metal=100, difficulty='hard', team=2),
             enemy_side(e, 'ai', ore=200, metal=100, difficulty='easy', player=3, team=2)],
            [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 16, hz - 14, 4)]
            + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(hx + 26, hz - 4, 3)]
            + [U(1, R['artillery'], hx + 10, hz - 22), U(1, R['missile'], hx + 20, hz - 20)]
            + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10), U(1, R['miner'], hx + 2, hz + 12),
               U(1, R['tug'], hx + 8, hz + 8)]
            + [U(2, E['light'], x, z) for x, z in spread(a_x - 12, a_z, 3)] + [U(2, E['miner'], a_x + 8, a_z + 4)]
            + [U(3, E['light'], x, z) for x, z in spread(b_x, b_z + 12, 3)] + [U(3, E['miner'], b_x + 4, b_z + 8)],
            [S(1, R['pad'], hx, hz), S(2, E['pad'], a_x, a_z), S(2, E['turret'], a_x - 18, a_z + 4),
             S(3, E['pad'], b_x, b_z), S(3, E['turret'], b_x - 4, b_z + 18)],
            [('a', say('Destroy the eastern brood\'s Landing Ring', 'Destroy the eastern Coalition pad'), 'primary'),
             ('b', say('Destroy the northern brood\'s Landing Ring', 'Destroy the northern mercenary pad'), 'primary')],
            [
                T('intro', at(0), msg(say('Two broods, one each side of the rift. The northern one is weaker: take it first.',
                                          'The northern mercenaries are the weaker pack. Break them first.'), f)),
                T('a', {'t': 'allDestroyed', 'side': 2, 'unitType': E['pad']}, done('a')),
                T('b', {'t': 'allDestroyed', 'side': 3, 'unitType': E['pad']}, done('b')),
            ],
            time_limit=50 * 60)

    # 21: the anchors (Terran) / the citadel's outer ring (Arcadian).
    hx, hz = FIELD_HOME
    gx, gz = FIELD_EDGE
    if terran:
        mission(f, 21, 'anchor_point', 'Anchor Point',
                'The Shard\'s spires anchor the rift to Vesper. The Arcadians are trying to bend the Shard to their '
                'will and hold the rift open for the swarm, though it burns them too. They will throw everything they '
                'have at you. Shatter all five spires.',
                'map.c_crystal_fields',
                [player_side(f, 1600, available=avail(f, *units3, 'bomber'), research_done=base_research),
                 enemy_side(e, 'ai', ore=800, metal=150, difficulty='hard'), enemy_side('alien', player=3)],
                [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 16, hz - 14, 4)]
                + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(hx + 26, hz - 4, 3)]
                + [U(1, R['artillery'], x, z, -0.785) for x, z in spread(hx + 10, hz - 24, 2)]
                + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10), U(1, R['miner'], hx + 2, hz + 12),
                   U(1, R['tug'], hx + 8, hz + 8)]
                + [U(2, E['light'], x, z) for x, z in spread(gx - 14, gz + 14, 4)] + [U(2, E['miner'], gx + 8, gz + 4)],
                [S(1, R['pad'], hx, hz), S(2, E['pad'], gx, gz), S(2, E['turret'], gx - 20, gz + 6)] + spires,
                [('anchors', 'Shatter all five spires', 'primary')],
                [
                    T('intro', at(0), msg('Artillery outranges the spires. Keep tanks back until they are down.', f)),
                    T('anchors', {'t': 'allDestroyed', 'side': 3, 'unitType': SHARD_SPIRE}, done('anchors')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
                ],
                time_limit=45 * 60, relations=at_war(2, 3))
    else:
        ring = [(-50, 30), (-30, 50), (-60, 60), (-20, 20), (-70, 10), (-10, 70)]
        mission(f, 21, 'citadel_walls', 'Citadel Walls',
                'Only the Coalition citadel still stands between the swarm and Vesper. It is ringed by gun towers: '
                'break the outer ring and destroy every Bastion Gun.',
                'map.c_crystal_fields',
                [player_side(f, 1600, available=avail(f, *units3, 'saucer'),
                             research_done=research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'disc')),
                 enemy_side(e, 'ai', ore=800, metal=150, difficulty='hard')],
                [U(1, R['light'], x, z, 2.356) for x, z in spread(gx - 16, gz + 14, 4)]
                + [U(1, R['heavy'], x, z, 2.356) for x, z in spread(gx - 26, gz + 4, 3)]
                + [U(1, R['artillery'], x, z, 2.356) for x, z in spread(gx - 10, gz + 24, 2)]
                + [U(1, R['miner'], gx + 10, gz + 2), U(1, R['tug'], gx + 4, gz - 10), U(1, R['miner'], gx - 2, gz - 12),
                   U(1, R['tug'], gx - 8, gz - 8)]
                + [U(2, E['light'], x, z) for x, z in spread(hx + 14, hz - 14, 4)] + [U(2, E['miner'], hx - 8, hz - 4)],
                [S(1, R['pad'], gx, gz), S(2, E['pad'], hx, hz)] + [S(2, E['turret'], x, z) for x, z in ring],
                [('walls', 'Destroy every Bastion Gun', 'primary')],
                [
                    T('intro', at(0), msg('Sunfalls outrange the guns. Shell them from a distance.', f)),
                    T('walls', {'t': 'allDestroyed', 'side': 2, 'unitType': E['turret']}, done('walls')),
                    T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
                ],
                time_limit=35 * 60)

    # 22: finale. The Shard sits in the middle and fires on everyone.
    hx, hz = RIFT_HOME
    shard = [S(3, SHARD_CORE, sx, sz)] + [S(3, SHARD_SPIRE, sx + dx, sz + dz) for dx, dz in [(-16, 0), (0, 16), (14, -12)]]
    mission(f, 22, say('close_the_rift', 'vesper_falls'), say('Close the Rift', 'Vesper Falls'),
            say('The anchor spires are down and the rift is failing. The Shard and its last spires still hold it open, and the last Arcadian '
                'hive has dug in beside it to feed on its power. Destroy the Shard and the hive, and the rift closes '
                'for good.',
                'The citadel\'s walls are down. Destroy its two Radar Towers, which carry its commands, and every '
                'Landing Pad, and Vesper belongs to the swarm. Keep clear of the Shard: it burns us still.'),
            'map.c_rift',
            [player_side(f, 2600 if terran else 2000, available=avail(f, *units3, *(('bomber',) if terran else ('saucer',))),
                         research_done=base_research if terran else research(f, *ACT2_BASE, 'artillery', 'repair', 'hover', 'disc')),
             FINALE_AI(e), enemy_side('alien', player=3)],
            [U(1, R['light'], x, z, -0.785) for x, z in spread(hx + 16, hz - 14, 4)]
            + [U(1, R['heavy'], x, z, -0.785) for x, z in spread(hx + 26, hz - 4, 4)]
            + [U(1, R['artillery'], x, z, -0.785) for x, z in spread(hx + 10, hz - 24, 3)]
            + [U(1, R['miner'], hx - 10, hz - 2), U(1, R['tug'], hx - 4, hz + 10), U(1, R['miner'], hx + 2, hz + 12),
               U(1, R['tug'], hx + 8, hz + 8)]
            + [U(2, E['light'], x, z) for x, z in spread(a_x - 12, a_z, 4)] + [U(2, E['heavy'], a_x - 16, a_z + 10)]
            + [U(2, E['miner'], a_x + 8, a_z + 4), U(2, E['tug'], a_x + 4, a_z + 10)],
            [S(1, R['pad'], hx, hz), S(2, E['pad'], a_x, a_z), S(2, E['pad'], b_x, b_z),
             S(2, E['turret'], a_x - 20, a_z + 4), S(2, E['turret'], b_x - 4, b_z + 20), S(2, E['tower_radar'], a_x + 12, a_z - 12),
             S(2, E['tower_radar'], b_x + 14, b_z + 6)] + shard,
            ([('shard', 'Destroy the Shard', 'primary'), ('hive', "Destroy the hive's two Landing Rings", 'primary')]
             if terran else
             [('towers', 'Destroy both Radar Towers', 'primary'), ('pads', 'Destroy every Landing Pad', 'primary')]),
            [
                T('intro', at(0), msg(say('The Shard fires on anything near it. Break its spires with artillery first.',
                                          'The Shard fires on anything near it. Go round it; the swarm needs it whole.'), f)),
                # Terran: with the Shard gone, the reserves can land for the last push. Arcadian: the
                # brood's reserves hatch at the ten-minute mark instead (the swarm leaves the Shard be).
                (T('shard', {'t': 'allDestroyed', 'side': 3, 'unitType': SHARD_CORE}, done('shard'),
                   msg('The Shard is down and the way to the hive is open. Reserves are landing at your pad.', f),
                   spawn(1, R['heavy'], 4, hx + 18, hz - 8, drop=True), spawn(1, R['light'], 4, hx + 8, hz - 18, drop=True))
                 if terran else
                 T('reserves', at(600), msg('The brood reserves have hatched. They are landing at your Landing Ring.', f),
                   spawn(1, R['heavy'], 4, hx + 18, hz - 8, drop=True), spawn(1, R['light'], 4, hx + 8, hz - 18, drop=True))),
                *([T('hive', {'t': 'allDestroyed', 'side': 2, 'unitType': E['pad']}, done('hive'))] if terran else
                  [T('towers', {'t': 'allDestroyed', 'side': 2, 'unitType': E['tower_radar']}, done('towers')),
                   T('pads', {'t': 'allDestroyed', 'side': 2, 'unitType': E['pad']}, done('pads'))]),
                T('padLost', {'t': 'allDestroyed', 'side': 1, 'unitType': R['pad']}, {'t': 'lose', 'reason': 'padLost'}),
            ],
            time_limit=60 * 60, relations=at_war(2, 3),
            epilogue=say('The Shard shattered, and with nothing to hold it open, the rift collapsed. Across Vesper the '
                         'last Arcadian machines fell still. For the first time since Halden went silent, the sky over '
                         'the colonies is clear.',
                         'The citadel\'s last tower fell silent, and the Coalition\'s hold on Vesper broke with it. '
                         'Above the plains the rift opened wide, and the rest of the swarm began its descent. Vesper '
                         'is ours.'))


act3('human')
act3('alien')

# ---------------------------------------------------------------- training

# Five short lessons, one idea each, all Terran (the outline: drops, mining, combat, research,
# air). Every lesson is a chain of steps: the objective line always says what to do next, a
# step's goal ring only shows once the step before it is done, and Command tops up the ore a
# step needs, so a player who spent it elsewhere can't get stuck. There is no time limit and
# nothing in them can destroy the landing pad. The text matches the touch controls (see the
# Help screen and src/ui/input.ts).

TRAINING = []
COACH = 'Command'
H = ROLE['human']
A = ROLE['alien']

# Drill Yard: a small practice ground. The pad sits in the south-west with ore and a metal site
# round it; a low ridge with a gap crosses the middle, and the target range is beyond it.
YARD_PAD = (-40, 32)
add_map('map.t_drill_yard', 'Drill Yard', 150, [YARD_PAD, (44, -40)], [
    ('ore', -60, 12, 1500), ('ore', -62, 50, 1500), ('ore', -22, 58, 1200), ('metal', -64, 32, 400),
], {
    'seed': 1301, 'roughness': 0.5, 'centreRidge': False, 'symmetric': False,
    'ridges': [{'x0': -8, 'z0': -74, 'x1': 2, 'z1': -10, 'height': 6, 'width': 6},
               {'x0': 6, 'z0': 14, 'x1': 14, 'z1': 74, 'height': 6, 'width': 6}],
    'hills': [{'x': 40, 'z': 40, 'radius': 18, 'height': 3}, {'x': -40, 'z': -40, 'radius': 20, 'height': 4}],
    'flats': [{'x': YARD_PAD[0], 'z': YARD_PAD[1], 'radius': 15}, {'x': 4, 'z': 2, 'radius': 8}],
})

# Kestrel Field: open ground for the research and air lessons. Metal by the pad, a target range
# out to the north-east.
FIELD_PAD = (-44, 40)
add_map('map.t_kestrel_field', 'Kestrel Field', 160, [FIELD_PAD, (50, -46)], [
    ('ore', -64, 22, 1500), ('ore', -26, 62, 1500), ('metal', -66, 58, 600), ('metal', -64, 40, 600),
], {
    'seed': 1402, 'roughness': 0.5, 'centreRidge': False, 'symmetric': False,
    'hills': [{'x': 10, 'z': 20, 'radius': 20, 'height': 3}, {'x': 40, 'z': 50, 'radius': 18, 'height': 4},
              {'x': -30, 'z': -40, 'radius': 22, 'height': 4}],
    'flats': [{'x': FIELD_PAD[0], 'z': FIELD_PAD[1], 'radius': 16}, {'x': 34, 'z': -30, 'radius': 12}],
})


def coach(text):
    return {'t': 'message', 'speaker': COACH, 'text': text}


def grant(ore=0, metal=0):
    g = {'t': 'grant', 'side': 1}
    if ore:
        g['ore'] = ore
    if metal:
        g['metal'] = metal
    return g


def has(unit, count=1):
    return {'t': 'unitsAlive', 'side': 1, 'unitType': unit, 'op': '>=', 'count': count}


def lesson(order, slug, title, briefing, map_id, player, units, structures, steps, intro, enemy=True,
           extra=()):
    """steps: (id, objective text, condition, actions when the step starts). The first step's
    actions run with the intro; a step's condition is only checked once the step before is done."""
    triggers = [T('intro', at(0), coach(intro), *steps[0][3])]
    for i, (sid, _text, cond, _start) in enumerate(steps):
        when = cond if i == 0 else {'t': 'and', 'conds': [{'t': 'objectiveDone', 'id': steps[i - 1][0]}, cond]}
        do = [done(sid)]
        if i + 1 < len(steps):
            nid, ntext, _c, nstart = steps[i + 1]
            do += [{'t': 'setObjective', 'id': nid, 'status': 'add', 'text': ntext, 'kind': 'primary'}, *nstart]
        triggers.append(T(sid, when, *do))
    triggers += list(extra)
    TRAINING.append({
        'id': f'mission.training.{order}_{slug}', 'campaign': 'training', 'order': order, 'title': title,
        'briefing': briefing, 'mapId': map_id, 'sides': [player, enemy_side('alien')], 'units': units,
        'structures': structures,
        'objectives': [{'id': steps[0][0], 'text': steps[0][1], 'kind': 'primary'}],
        'triggers': triggers,
        'relations': at_war(1, 2) if enemy else [],
        'placeholder': False,
    })


def ring(x, z, r=7):
    return area(1, x, z, r)


# 1. Drops: everything arrives by orbital drop onto the landing pad.
px, pz = YARD_PAD
lesson(1, 'drops', 'Drops',
       'Welcome, Commander. Nothing is built on Vesper: everything you buy is dropped from orbit onto your '
       'landing pad. Buy a few units, drive one about, and order your first building.',
       'map.t_drill_yard',
       player_side('human', 250, available=avail('human', 'light', 'scout', 'turret')),
       [], [S(1, H['pad'], px, pz)],
       [
           ('buy', 'Tap your landing pad to open Build, then tap the Lancer card', has(H['light']), []),
           ('more', 'Buy two Outriders. They land one at a time; the strip at the top shows the queue',
            has(H['scout'], 2),
            [coach('Lancer down! Everything you buy lands on the pad, then drives off it.'), grant(150)]),
           ('drive', 'Tap one of your units to select it, then tap inside the ring to drive there',
            ring(-6, 10), [coach('All landed. Close Build with the X to see the whole map again.')]),
           ('tower', 'Buildings come by drop too. Open Build, tap Structures, buy a Bastion Gun. It sets itself up',
            {'t': 'structureBuilt', 'side': 1, 'structureType': H['turret']},
            [coach('Nicely driven. Command has sent 150 ore for a gun tower.'), grant(150)]),
       ],
       'Your landing pad is the big square platform. Tap it to see what you can buy.',
       enemy=False)

# 2. Mining: miners dig ore, haulers carry it home, ore pays for everything.
lesson(2, 'mining', 'Mining',
       'Ore pays for everything you buy. A Prospector digs ore and stacks it in crates by the field; a '
       'Hauler carries the crates home to your landing pad. Get the ore flowing and bank some.',
       'map.t_drill_yard',
       player_side('human', 0, available=avail('human', 'light', 'miner', 'tug')),
       [U(1, H['miner'], px - 10, pz - 2, 0.0), U(1, H['tug'], px - 10, pz + 6, 0.0)],
       [S(1, H['pad'], px, pz)],
       [
           ('dig', 'Tap the Prospector, then tap a pink ore field to start digging',
            {'t': 'resourceReached', 'side': 1, 'ore': 10}, []),
           ('crew', 'Buy a second Prospector and a second Hauler. Send the new Prospector to dig too',
            {'t': 'and', 'conds': [has(H['miner'], 2), has(H['tug'], 2)]},
            [coach('First load home! Haulers fetch the crates by themselves. Here is 150 ore for more workers.'),
             grant(150)]),
           ('bank', 'Bank 400 ore. Your ore count is at the top left',
            {'t': 'resourceReached', 'side': 1, 'ore': 400},
            [coach('Two crews dig twice as fast. Keep an idle miner busy: tap it, then an ore field.')]),
           ('spend', 'Ore buys everything. Spend some: buy a Lancer', has(H['light']),
            [coach('400 ore banked. Tanks, buildings and workers are all paid in ore.')]),
       ],
       'Your Prospector and Hauler are beside the pad. Ore fields are the pink rocks.',
       enemy=False)

# 3. Combat: select, move, attack, attack-move, hold, groups.
targets = [(30, 4), (34, -4)]
road = [(30, -24), (36, -20)]
end_ring = (46, -40)
lesson(3, 'combat', 'Combat',
       'Four Lancers are yours to command. Learn to pick them, move them and fight with them. The '
       'Arcadian Darters on the range are light scouts, no match for four Lancers.',
       'map.t_drill_yard',
       player_side('human', 0, available=[]),
       [U(1, H['light'], x, z, 0.0, tag='squad') for x, z in spread(px + 12, pz - 4, 4, 5)]
       + [U(2, A['scout'], x, z, 3.1, tag='targets') for x, z in targets]
       + [U(2, A['scout'], x, z, 2.3, tag='road') for x, z in road],
       [S(1, H['pad'], px, pz)],
       [
           ('move', 'Tap a Lancer to select it, then tap inside the ring to move it', ring(-14, 18, 6), []),
           ('all', 'Double-tap a Lancer to pick all four, or tap All army at the bottom. Move them to the ring',
            ring(4, 2, 8), [coach('Well done. Drag one finger on the map to look around.')]),
           ('attack', 'Two Darters on the range. With your Lancers selected, tap a Darter to attack it',
            {'t': 'unitDestroyed', 'tag': 'targets'}, [coach('Through the gap is the target range.')]),
           ('advance', 'Tap Attack, then tap inside the far ring. Your Lancers fight anything on the way',
            ring(*end_ring, 8), [coach('Targets down. A plain move drives past enemies; an Attack move fights them.')]),
           ('hold', 'Select your Lancers and tap Hold: they stay put and fire at anything in range. Beat the raid',
            {'t': 'unitDestroyed', 'tag': 'raid'},
            [coach('Well fought. Arcadian raiders are coming through the gap behind you!'),
             spawn(2, A['scout'], 3, -46, -56, tag='raid'), attack('raid', end_ring[0], end_ring[1])]),
           ('group', 'Tap All army, then hold tile 1 to save them as a group. Tap 1, then tap the ring',
            ring(-14, 6, 8), [coach('Raid beaten. Groups let you pick a squad again with one tap.')]),
       ],
       'Units are selected by tapping them. Move by tapping the ground.',
       extra=[
           # Never run out of tanks: reinforcements land whenever only one is left.
           T('reinforce', {'t': 'unitsAlive', 'side': 1, 'op': '<=', 'count': 1},
             coach('Reinforcements are landing at your pad.'), spawn(1, H['light'], 3, px + 10, pz - 6, drop=True),
             repeat=True),
       ])

# 4. Research: metal from a metal station pays for research and upgrades.
fx, fz = FIELD_PAD
lesson(4, 'research', 'Research',
       'New weapons need research, and research is paid in metal as well as ore. Set up a Metal Station, '
       'let a Hauler bring the metal home, then research a new tank and upgrade an old one.',
       'map.t_kestrel_field',
       player_side('human', 250, available=avail('human', 'light', 'missile', 'station', 'tug')),
       [U(1, H['light'], fx + 12, fz - 6, -0.7), U(1, H['light'], fx + 14, fz + 2, -0.7),
        U(1, H['tug'], fx - 2, fz - 12, 0.0)],
       [S(1, H['pad'], fx, fz)],
       [
           ('station', 'Open Build, tap Structures and buy a Metal Station. It drives to a blue metal site',
            {'t': 'structureBuilt', 'side': 1, 'structureType': H['station']}, []),
           ('metal', 'Bank 50 metal. Your Hauler fetches it from the station by itself',
            {'t': 'resourceReached', 'side': 1, 'metal': 50},
            [coach('Station up. Haulers carry metal home just like ore.')]),
           ('research', 'Open Build and tap the locked Javelin card to research Missiles',
            {'t': 'researchDone', 'side': 1, 'node': 'research.human.missiles'},
            [coach('Metal pays for research. Here is 100 ore for the rest of the cost.'), grant(100)]),
           ('upgrade', 'Missiles also unlock Fire rate. Select a Lancer, tap Upgrade, then tap Fire rate',
            {'t': 'upgraded', 'side': 1, 'upgrade': 'fireRate'},
            [coach('Missiles researched! Upgrades cost a little ore and metal. Here is 100 ore.'), grant(100)]),
           ('javelin', 'Buy a Javelin. Units cost only ore; metal is for research and upgrades',
            has(H['missile']), [coach('That Lancer fires faster for the rest of the match.'), grant(200)]),
       ],
       'Metal sites are the blue rocks by your pad. Tap your landing pad to open Build.',
       enemy=False)

# 5. Air: an airfield, fighters, and the few weapons that can hit aircraft.
range_ring = (34, -30)
lesson(5, 'air', 'Air',
       'Aircraft fly over hills and water, but they need an Airfield to land, refuel and rearm. Only '
       'some weapons can hit them: missiles and fighters. Build an air wing and put it to work.',
       'map.t_kestrel_field',
       player_side('human', 300, available=avail('human', 'light', 'missile', 'air_base', 'fighter'),
                   research_done=research('human', 'air', 'artillery')),
       [U(1, H['light'], fx + 12, fz - 6, -0.7), U(1, H['light'], fx + 14, fz + 2, -0.7)]
       + [U(2, A['scout'], x, z, 2.3, tag='darters') for x, z in [(range_ring[0] + 3, range_ring[1] - 2),
                                                                 (range_ring[0] - 3, range_ring[1] + 3)]],
       [S(1, H['pad'], fx, fz)],
       [
           ('airfield', 'Open Build, tap Structures and buy an Airfield. Aircraft land, refuel and rearm there',
            {'t': 'structureBuilt', 'side': 1, 'structureType': H['air_base']}, []),
           ('antiair', 'Lancers cannot hit aircraft. Buy a Javelin: its missiles can. Shoot down the Dragonflies',
            {'t': 'and', 'conds': [has(H['missile']), {'t': 'unitDestroyed', 'tag': 'drones'}]},
            [coach('Arcadian Dragonflies overhead! They only hunt aircraft, but our Lancers cannot touch them.'),
             grant(200), spawn(2, A['dragonfly'], 2, 60, -60, tag='drones', launch=True), attack('drones', fx, fz)]),
           ('falcon', 'Buy a Falcon. It parks on the Airfield until you launch it', has(H['fighter']),
            [coach('Only missiles, missile towers and fighters can hit aircraft.'), grant(300)]),
           ('fly', 'Tap the Falcon on the Airfield, tap Launch, then tap inside the ring',
            area(1, range_ring[0], range_ring[1], 10, unitType=H['fighter']), []),
           ('strike', 'Falcons hit ground units too. Destroy both Darters. Empty Falcons fly home; launch them again',
            {'t': 'unitDestroyed', 'tag': 'darters'},
            [coach('Falcons carry little fuel and ammunition. They return to the Airfield by themselves.')]),
       ],
       'Aviation research is done for you. Tap your landing pad to open Build.',
       extra=[
           # Dragonflies run out of fuel and crash after a minute: send more until a Javelin is here.
           T('moreDrones', {'t': 'and', 'conds': [{'t': 'objectiveDone', 'id': 'airfield'},
                                                  {'t': 'not', 'cond': {'t': 'objectiveDone', 'id': 'antiair'}},
                                                  {'t': 'unitsAlive', 'tag': 'drones', 'op': '<=', 'count': 0},
                                                  {'t': 'not', 'cond': has(H['missile'])}]},
             spawn(2, A['dragonfly'], 2, 60, -60, tag='drones', launch=True), attack('drones', fx, fz), repeat=True),
       ])


# ---------------------------------------------------------------- site spacing

# Ore and metal sites stay 12-14 m clear of every landing pad's edge, so pad traffic (arrivals
# driving off, haulers queueing at the three delivery spots) has room. Sites closer than that are
# pushed straight out from the pad; a station built on a moved site moves with it.
PAD_HALF = 6
SITE_GAP_MIN = 12
SITE_GAP_STEP = 1  # targets cycle 12, 13, 14 so sites don't all sit on one ring


# Hand-picked spots where pushing straight out would land a site on a cliff or in water
# (the generator can't see terrain; tests/unit/siteSpacing.test.ts checks every site).
SITE_SPOTS = {
    ('map.c_relay_road', -86, 58): (-78, 54),
    ('map.c_relay_road', -62, 86): (-68, 90),
}


def pad_gap(px, pz, x, z):
    return math.hypot(max(0.0, abs(x - px) - PAD_HALF), max(0.0, abs(z - pz) - PAD_HALF))


def space_sites():
    for m in MAPS:
        # The pads the missions actually place (map starts are only camera spots in the campaign).
        pads = []
        users = [ms for ms in MISSIONS + TRAINING if ms['mapId'] == m['id']]
        for ms in users:
            for st in ms['structures']:
                if st['structureType'].endswith('landing_pad') and (st['x'], st['z']) not in pads:
                    pads.append((st['x'], st['z']))
        if not pads:
            continue
        for i, dep in enumerate(m['deposits']):
            x0, z0 = dep['x'], dep['z']
            x, z = SITE_SPOTS.get((m['id'], x0, z0), (x0, z0))
            for _ in range(4):
                near = min(pads, key=lambda p: pad_gap(p[0], p[1], x, z))
                if pad_gap(near[0], near[1], x, z) >= SITE_GAP_MIN - 1e-6:
                    break
                # +1.5 so rounding to even metres never lands inside the minimum. Even
                # coordinates keep a station's footprint on the 2 m path grid, so haulers can
                # park within reach of it.
                target = SITE_GAP_MIN + SITE_GAP_STEP * (i % 3) + 1.5
                dx, dz = x - near[0], z - near[1]
                length = math.hypot(dx, dz)
                if length < 1e-6:
                    dx, dz, length = -near[0] or 1.0, -near[1], math.hypot(-near[0] or 1.0, -near[1])
                base = math.atan2(dz, dx)
                half = m['size'] / 2 - 6
                # Straight out from the pad; if the map edge is in the way, swing round the pad.
                for turn in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6]:
                    angle = base + turn * math.radians(15)
                    ux, uz = math.cos(angle), math.sin(angle)
                    lo, hi = 0.0, 80.0
                    for _ in range(50):
                        mid = (lo + hi) / 2
                        if pad_gap(near[0], near[1], near[0] + ux * mid, near[1] + uz * mid) < target:
                            lo = mid
                        else:
                            hi = mid
                    x = 2 * round((near[0] + ux * hi) / 2)
                    z = 2 * round((near[1] + uz * hi) / 2)
                    if abs(x) <= half and abs(z) <= half:
                        break
                x = int(max(-half, min(half, x)))
                z = int(max(-half, min(half, z)))
            if (x, z) != (x0, z0):
                dep['x'], dep['z'] = x, z
                for ms in users:
                    for st in ms['structures']:
                        if (st['x'], st['z']) == (x0, z0):
                            st['x'], st['z'] = x, z
                print(f"  {m['id']}: {dep['kind']} ({x0},{z0}) -> ({x},{z})")


space_sites()

# ---------------------------------------------------------------- write

def write():
    with open(os.path.join(ROOT, 'src/data/maps.campaign.json'), 'w') as f:
        json.dump(MAPS, f, indent=2)
        f.write('\n')
    out_dir = os.path.join(ROOT, 'src/data/missions/campaign')
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.endswith('.json'):
            os.remove(os.path.join(out_dir, name))
    lines = ['// Generated by tools/missions/build.py. Do not edit by hand.']
    names = []
    for i, m in enumerate(MISSIONS):
        file = m['id'].split('.', 1)[1].replace('.', '_') + '.json'
        with open(os.path.join(out_dir, file), 'w') as f:
            json.dump(m, f, indent=2)
            f.write('\n')
        lines.append(f"import m{i} from './campaign/{file}';")
        names.append(f'm{i}')
    lines.append('')
    lines.append(f"export const CAMPAIGN_MISSIONS: readonly unknown[] = [{', '.join(names)}];")
    with open(os.path.join(ROOT, 'src/data/missions/campaign.ts'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    # Training lessons: src/data/missions/training_<n>_<slug>.json and the import list training.ts.
    for name in os.listdir(os.path.join(ROOT, 'src/data/missions')):
        if name.startswith('training_') and name.endswith('.json'):
            os.remove(os.path.join(ROOT, 'src/data/missions', name))
    lines = ['// Generated by tools/missions/build.py. Do not edit by hand.']
    names = []
    for i, m in enumerate(TRAINING):
        file = 'training_' + m['id'].split('.')[-1] + '.json'
        with open(os.path.join(ROOT, 'src/data/missions', file), 'w') as f:
            json.dump(m, f, indent=2)
            f.write('\n')
        lines.append(f"import t{i} from './{file}';")
        names.append(f't{i}')
    lines.append('')
    lines.append(f"export const TRAINING_MISSIONS: readonly unknown[] = [{', '.join(names)}];")
    with open(os.path.join(ROOT, 'src/data/missions/training.ts'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'{len(MAPS)} maps, {len(MISSIONS)} missions, {len(TRAINING)} training missions')


write()
