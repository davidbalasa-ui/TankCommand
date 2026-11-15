"""Moving parts: which nodes of which models the game should animate, and how.

    python motion.py <models dir>

Writes an `anim` entry into the glTF extras of each listed node (and of the same node in the
model's _lod file). The game reads it from node.userData.anim:

    type   'spin'   turn about `axis` at `speed` rad/s
           'swing'  rock about `axis`: angle = amp * sin(2 pi * speed * t), speed in Hz
                    optional `phase` (radians) offsets it so paired parts move out of step
                    optional `snap` (+ attack, recover): add snap * hit(tf) radians when the unit fires
                    (flicker parts may carry `fireOn` seconds: always shown that long after firing)
           'flicker' electricity: of the nodes sharing `slots`, show only one at a time (or none),
                    re-picked at random `rate` times a second; `duty` is the chance one shows.
                    `idle` replaces duty while `when` is not met.
           'scroll' on the mesh node 'Tread': slide its material's texture along U
                    (map.offset.x) by `speed` tiles per second while moving
    Firing (all timed from tf = seconds since the unit's weapon last fired):
           'recoil' slide the node back along -`axis` by dist * hit(tf - delay), where
                    hit(x) = x / attack while x < attack, then (1 - (x - attack) / recover)^2 until 0.
                    optional `repeat` + `every`: the same hit again n times, `every` seconds apart (bursts)
           'flash'  node hidden except while delay <= tf < delay + dur (also honours repeat/every);
                    give it a random roll about `axis` and scale 0.8..1.2 each time it shows
           'launch' a missile part: hidden-in-tube until tf >= delay, then it flies out along `axis`
                    (distance = travel * (x / dur)^2 for x = tf - delay < dur), is hidden until
                    tf >= reload, then sits back in its tube. Delays are staggered per tube so a volley
                    ripples across the launcher after a short pause.
    Whole-model firing kick: the glTF scene's extras.fire = {kick, slide, attack, recover}: pitch the
    whole unit visual nose-up by kick radians and shove it back by slide metres, both times
    exp(-4u) * cos(6u) with u = (tf - attack) / recover after a linear rise over `attack`; apply it
    opposite to the direction the weapon is pointing.
    axis   in the node's own glTF space (Y up, model front +X)
    when   'always' | 'mining' | 'working' (repairing or building) | 'moving'
    busySpeed  optional: speed to use instead while the unit is working

Nodes are pivots placed on the part's axis, so the game only ever rotates the node itself.
"""
import json
import math
import os
import struct
import sys

UP, FWD, LEFT = [0, 1, 0], [1, 0, 0], [0, 0, -1]


def spin(axis, speed, when='always', **kw):
    return dict(type='spin', axis=axis, speed=speed, when=when, **kw)


def swing(axis, amp, speed, when='always', **kw):
    return dict(type='swing', axis=axis, amp=amp, speed=speed, when=when, **kw)


def flicker(slot, slots, rate=18.0, duty=0.75, idle=0.12, when='moving'):
    return dict(type='flicker', slot=slot, slots=slots, rate=rate, duty=duty, idle=idle, when=when)



def recoil(axis, dist, attack=0.04, recover=0.45, delay=0.0, **kw):
    return dict(type='recoil', axis=axis, dist=dist, attack=attack, recover=recover, delay=delay, **kw)


def flash(axis=None, dur=0.08, delay=0.0, **kw):
    return dict(type='flash', axis=axis or FWD, dur=dur, delay=delay, **kw)


def launch(axis, delay, travel=9.0, dur=0.45, reload=2.4):
    return dict(type='launch', axis=axis, delay=delay, travel=travel, dur=dur, reload=reload)


def up(deg):
    r = math.radians(deg)
    return [round(math.cos(r), 4), round(math.sin(r), 4), 0]


def gun(spec, sfx='', dist=0.3, kick=None, axis=None, delay=0.0, recover=0.45, fdur=0.08, **kw):
    spec['Barrel' + sfx + 'Pivot'] = recoil(axis or FWD, dist, recover=recover, delay=delay, **kw)
    spec['Flash' + sfx + 'Pivot'] = flash(axis, fdur, delay, **kw)
    if kick:
        spec['@fire'] = dict(kick=kick[0], slide=kick[1], attack=0.05, recover=kick[2] if len(kick) > 2 else 0.6)


SPEC = {
    'human/prospector': {'DrumPivot': spin(LEFT, 6.0, 'mining')},
    'alien/gorger': {'GrinderPivot': spin(FWD, 8.0, 'mining')},
    'human/watchman': {'TurretPivot': spin(UP, 1.2)},
    'alien/seer': {'TurretPivot': spin(UP, 0.8)},
    'alien/weaver': {'TurretPivot': spin(UP, 1.0, busySpeed=4.0)},
    'human/mender': {'TurretPivot': swing(UP, 0.6, 0.5, 'working')},
    'alien/disc': {'BladesPivot': spin(UP, 1.5)},
    'alien/dragonfly': {
        'WingFLPivot': swing(FWD, 0.3, 14.0), 'WingFRPivot': swing([-1, 0, 0], 0.3, 14.0),
        'WingHLPivot': swing(FWD, 0.26, 14.0, phase=1.6), 'WingHRPivot': swing([-1, 0, 0], 0.26, 14.0, phase=1.6),
        # Firing: the tail whips up and over the back like a scorpion, sting aimed forward (snap = extra radians, eased like a recoil hit) and the sting discharges.
        'Tail1Pivot': swing(LEFT, 0.07, 0.7, snap=0.85, attack=0.12, recover=0.55), 'Tail2Pivot': swing(LEFT, 0.1, 0.7, phase=-0.9, snap=0.95, attack=0.12, recover=0.55),
        'Tail3Pivot': swing(LEFT, 0.14, 0.7, phase=-1.8, snap=1.0, attack=0.12, recover=0.55),
        'StingPivot': flash([-1, 0, 0], 0.12, 0.1),
        'ThrustAPivot': flicker(0, 3, rate=24.0, duty=1.0, idle=0.3), 'ThrustBPivot': flicker(1, 3, rate=24.0, duty=1.0, idle=0.3),
        'ThrustCPivot': flicker(2, 3, rate=24.0, duty=1.0, idle=0.3),
        'LiftA': flicker(0, 2, rate=20.0, duty=0.9, idle=0.9, when='always'), 'LiftB': flicker(1, 2, rate=20.0, duty=0.9, idle=0.9, when='always'),
        'ArcA': flicker(0, 4), 'ArcB': flicker(1, 4), 'ArcC': flicker(2, 4), 'ArcD': flicker(3, 4),
        **{f'Arc{w}{v}Pivot': dict(flicker((i + 2 * v) % 4, 4), fireOn=0.25) for i, w in enumerate(('FL', 'HR', 'FR', 'HL')) for v in (1, 2)},
    },
    'structures/terran_radar': {'TurretPivot': spin(UP, 1.0)},
    'structures/terran_air_base': {'DishPivot': spin(UP, 1.0)},
    'structures/kesh_seer_spire': {'TurretPivot': spin(UP, 0.6)},
    'structures/kesh_metal_siphon': {'TurretPivot': spin(UP, 0.5)},
    'structures/kesh_hive_roost': {'TurretPivot': spin(UP, 0.3)},
    'structures/kesh_gene_vault': {'CrownPivot': spin(UP, 0.5)},
    'structures/terran_metal_station': {'FanPivot': spin(UP, 9.0)},
    'structures/terran_landing_pad': {'ScannerPivot': spin(UP, 1.6)},
    'structures/kesh_landing_nest': {'CrownPivot': spin(UP, 0.7), 'HaloPivot': spin(UP, -0.25)},
}

WHEELS = {f'Wheel{i}{s}Pivot': spin(LEFT, 7.0, 'moving') for i in range(3) for s in 'LR'}
FANS = {f'Fan{a}{s}Pivot': spin(UP, 14.0) for a in 'FB' for s in 'LR'}
TREAD = dict(type='scroll', speed=3.0, when='moving')
for _n in ['lancer', 'bulwark', 'javelin', 'longbow', 'prospector', 'hauler', 'mender', 'watchman', 'bastion_packed', 'spire_packed', 'radar_tower_packed', 'metal_station_packed', 'air_base_packed']:
    SPEC.setdefault('human/' + _n, {})['Tread'] = TREAD
SPEC.setdefault('human/outrider', {}).update(WHEELS)
SPEC.setdefault('human/skimmer', {}).update(FANS)
SPEC.setdefault('human/hauler', {})['CranePivot'] = swing(UP, 0.5, 0.3, 'working')
SPEC.setdefault('human/mender', {})['SparkPivot'] = flicker(0, 1, rate=20.0, duty=0.7, idle=0.0, when='working')
for _n in ('outrider', 'javelin', 'longbow', 'watchman'):
    SPEC.setdefault('human/' + _n, {})['RadarPivot'] = spin(UP, 2.2)

for _n in ('stinger', 'darter', 'glider', 'carapace', 'spitter', 'mortar_beast', 'gorger', 'ferrier', 'weaver', 'seer', 'disc'):
    _s = SPEC.setdefault('alien/' + _n, {})
    _s.update({'LiftA': flicker(0, 2, rate=20.0, duty=0.9, idle=0.9, when='always'), 'LiftB': flicker(1, 2, rate=20.0, duty=0.9, idle=0.9, when='always'),
               'ThrustA': flicker(0, 2, rate=24.0, duty=1.0, idle=0.0), 'ThrustB': flicker(1, 2, rate=24.0, duty=1.0, idle=0.0)})

# Firing: recoil, muzzle flash, hull kick, missile ripples.
_h = lambda n: SPEC.setdefault('human/' + n, {})
_a = lambda n: SPEC.setdefault('alien/' + n, {})
_h('lancer')['FlashPivot'] = flash(FWD, 0.1, 0.0)
for _k in (1, 2, 3, 4):
    _h('lancer')[f'Barrel{_k}Pivot'] = recoil(FWD, 1.0 * _k, attack=0.05, recover=0.9)
_h('lancer')['@fire'] = dict(kick=0.04, slide=0.14, attack=0.05, recover=0.7)
gun(_h('outrider'), dist=0.14, kick=(0.012, 0.03, 0.3), recover=0.1, fdur=0.05, repeat=3, every=0.13)
gun(_h('skimmer'), 'L', dist=0.3, kick=(0.02, 0.08))
gun(_h('skimmer'), 'R', dist=0.3, delay=0.18)
gun(_h('bulwark'), 'L', dist=0.5, kick=(0.035, 0.1, 0.7), recover=0.6)
gun(_h('bulwark'), 'R', dist=0.5, delay=0.22, recover=0.6)
_h('longbow')['FlashPivot'] = flash(up(26), 0.14, 0.0)
for _k in (1, 2, 3, 4):   # telescoping cannon: every sleeve slams into the one behind (80% of the barrel length)
    _h('longbow')[f'Barrel{_k}Pivot'] = recoil(up(26), 1.76 * _k, attack=0.07, recover=1.5)
_h('longbow')['@fire'] = dict(kick=0.1, slide=0.4, attack=0.06, recover=1.2)
_order = [(s, i, j) for j in (1, 0) for i, s in ((0, 'L'), (2, 'R'), (1, 'L'), (0, 'R'), (2, 'L'), (1, 'R'))]
for _k, (_s, _i, _j) in enumerate(_order):   # pause, then a ripple hopping back and forth between the two pods
    _h('javelin')[f'Msl{_s}{_i}{_j}Pivot'] = launch(up(16), 0.5 + 0.09 * _k)
_h('javelin')['@fire'] = dict(kick=0.012, slide=0.03, attack=0.5, recover=1.2)
gun(_a('stinger'), dist=0.2, kick=(0.015, 0.04))
gun(_a('darter'), 'L', dist=0.12, kick=(0.008, 0.02, 0.3), recover=0.2)
gun(_a('darter'), 'R', dist=0.12, delay=0.1, recover=0.2)
gun(_a('glider'), 'L', dist=0.15)
gun(_a('glider'), 'R', dist=0.15, delay=0.12)
gun(_a('carapace'), dist=0.4, kick=(0.03, 0.1, 0.7), recover=0.6)
for _k, (_i, _r) in enumerate([(0, 'F'), (1, 'F'), (2, 'F'), (2, 'B'), (1, 'B'), (0, 'B')]):   # sweep across the front arch, then back along the rear
    _a('spitter')[f'Pod{_i}{_r}Pivot'] = launch(up(22), 0.5 + 0.11 * _k)
_a('spitter')['@fire'] = dict(kick=0.012, slide=0.03, attack=0.5, recover=1.2)
_a('mortar_beast')['FlashPivot'] = flash(up(66), 0.12)
_a('mortar_beast')['@fire'] = dict(kick=0.14, slide=0.35, attack=0.05, recover=1.1)

def patch(path, anims):
    d = open(path, 'rb').read()
    jl = struct.unpack('<I', d[12:16])[0]
    j = json.loads(d[20:20 + jl])
    rest = d[20 + jl:]
    found = set()
    if '@fire' in anims:
        j['scenes'][j.get('scene', 0)].setdefault('extras', {})['fire'] = anims['@fire']
        found.add('@fire')
    for n in j['nodes']:
        if n.get('name') in anims:
            n.setdefault('extras', {})['anim'] = anims[n['name']]
            found.add(n['name'])
    js = json.dumps(j, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + len(rest)) + struct.pack('<I', len(js)) + b'JSON' + js + rest
    open(path, 'wb').write(out)
    return sorted(set(anims) - found)


def apply(root):
    for key, anims in SPEC.items():
        for suffix in ('', '_lod'):
            p = os.path.join(root, key + suffix + '.glb')
            if not os.path.exists(p):
                if not suffix:
                    print('motion: missing', p)
                continue
            miss = patch(p, anims)
            if miss:
                print('motion: no node', miss, 'in', key + suffix)


if __name__ == '__main__':
    apply(sys.argv[1])
