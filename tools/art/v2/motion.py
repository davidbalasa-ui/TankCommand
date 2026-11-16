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
           'slide'  move along `axis`: offset = amp * sin(2 pi * speed * t + phase) metres, plus
                    optional `snap` (+ attack, recover) metres added as snap * hit(tf) when the unit fires
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
    Whole-model idle life: the scene's extras.idle = {bob, bobSpeed, sway, swaySpeed, shake}: lift the unit
    visual by bob * sin(2 pi bobSpeed t) metres, roll it by sway * sin(2 pi swaySpeed t) radians, and add
    `shake` metres of fast engine shudder. Hover units bob and sway; tracked units only shudder.
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


def slide(axis, amp, speed, when='always', **kw):
    return dict(type='slide', axis=axis, amp=amp, speed=speed, when=when, **kw)


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
# Lancer (light tank): the two lances fire in turn, one shot every 1.8 s (build thread's gameplay timing); sensor blades sweep while idle.
for _sd, _d in (('L', 0.0), ('R', 1.8)):
    _h('lancer')[f'Flash{_sd}Pivot'] = flash(FWD, 0.09, _d)
    for _k in (1, 2, 3, 4):
        _h('lancer')[f'Barrel{_sd}{_k}Pivot'] = recoil(FWD, 0.99 * _k, attack=0.05, recover=0.5, delay=_d)
_h('lancer')['BladeLPivot'] = swing(FWD, 0.16, 0.3)
_h('lancer')['BladeRPivot'] = swing(FWD, 0.16, 0.3, phase=2.1)
_h('lancer')['@fire'] = dict(kick=0.03, slide=0.1, attack=0.05, recover=0.4, period=3.6, repeat=2, every=1.8)
def tele(spec, step, sfx='', axis=None, delay=0.0, attack=0.05, recover=0.4, fdur=0.09, n=4, **kw):
    """Telescoping cannon (terran_v3.tele_cannon): sleeve k slides back k steps; the flash rides the last sleeve."""
    for k in range(1, n + 1):
        spec[f'Barrel{sfx}{k}Pivot'] = recoil(axis or FWD, step * k, attack=attack, recover=recover, delay=delay, **kw)
    spec[f'Flash{sfx}Pivot'] = flash(axis, fdur, delay, **kw)


def blades(spec, amp=0.16, speed=0.3):
    spec['BladeLPivot'] = swing(FWD, amp, speed)
    spec['BladeRPivot'] = swing(FWD, amp, speed, phase=2.1)


# ---- Terran sci-fi units: each has its own idle life as well as its own firing rhythm ----
DOWN = [0, -1, 0]
# Outrider: restless. The sensor mast pumps up and down, the turret darts side to side, the body jitters on its suspension.
_h('outrider').update({'MastPivot': slide(UP, 0.2, 0.22), 'TurretPivot': swing(UP, 0.35, 0.45, 'idle'), '@idle': dict(shake=0.012)})
# Lancer: alert hunter. The turret sweeps steadily, blades scan out of step.
_h('lancer').update({'TurretPivot': swing(UP, 0.25, 0.16, 'idle'), '@idle': dict(shake=0.006)})
# Skimmer: floats. It bobs and rolls on its fans, turret drifting.
_h('skimmer').update({'TurretPivot': swing(UP, 0.2, 0.12, 'idle'), '@idle': dict(bob=0.09, bobSpeed=0.55, sway=0.035, swaySpeed=0.31)})
# Bulwark: heavy and slow. Barely turns its turret; the armoured lids over the shoulder missile pods kick open on each blast and settle back.
_h('bulwark').update({'TurretPivot': swing(UP, 0.12, 0.06, 'idle'), '@idle': dict(shake=0.004),
                      'CapLPivot': swing(FWD, 0.015, 0.7, snap=0.45, attack=0.08, recover=1.8),
                      'CapRPivot': swing(FWD, 0.015, 0.7, phase=1.0, snap=-0.45, attack=0.08, recover=1.8)})
# Longbow: braces itself. Anchor claws slam into the ground for the salvo, the cannon breathes up and down between salvos.
_h('longbow').update({'ClawPivot': slide(DOWN, 0.0, 0.1, snap=0.22, attack=0.06, recover=2.2),
                      'GunPivot': swing(LEFT, 0.035, 0.11), '@idle': dict(shake=0.004)})
# Javelin: the pod cradle rocks as it tracks, nods on each launch; fire-control panel spins.
_h('javelin').update({'PodsPivot': swing(LEFT, 0.05, 0.17, snap=-0.07, attack=0.05, recover=0.6), '@idle': dict(shake=0.005)})
# Support units: engine shudder; work tools carry their own motion.
for _n, _sh in (('prospector', 0.012), ('hauler', 0.008), ('mender', 0.006), ('watchman', 0.004)):
    _h(_n)['@idle'] = dict(shake=_sh)
# Outrider (scout): 3 fast shots 0.15 s apart, reload 1.3 s (1.6 s cycle); blades twitch quickly, scanner spins.
tele(_h('outrider'), 0.6, attack=0.03, recover=0.11, fdur=0.05, repeat=3, every=0.15)
blades(_h('outrider'), 0.22, 0.9)
_h('outrider')['@fire'] = dict(kick=0.012, slide=0.03, attack=0.03, recover=0.12, period=1.6, repeat=3, every=0.15)
# Skimmer (hover tank): left then right 0.25 s apart, reload 2.15 s (2.4 s cycle).
tele(_h('skimmer'), 0.7, 'L', recover=0.3)
tele(_h('skimmer'), 0.7, 'R', recover=0.3, delay=0.25)
blades(_h('skimmer'), 0.12, 0.45)
_h('skimmer')['@fire'] = dict(kick=0.02, slide=0.12, attack=0.05, recover=0.5, period=2.4, repeat=2, every=0.25)
# Bulwark (heavy): both cannons together, one devastating blast every 3.5 s, slow heavy recovery.
tele(_h('bulwark'), 1.16, 'L', attack=0.06, recover=1.6, fdur=0.14)
tele(_h('bulwark'), 1.16, 'R', attack=0.06, recover=1.6, fdur=0.14)
blades(_h('bulwark'), 0.08, 0.18)
_h('bulwark')['@fire'] = dict(kick=0.06, slide=0.3, attack=0.06, recover=1.1, period=3.5)
# Longbow (artillery): 3 shots 0.4 s apart, then a 3 s reload (3.8 s cycle, build thread's gameplay timing).
_h('longbow')['FlashPivot'] = flash(up(26), 0.1, 0.0, repeat=3, every=0.4)
for _k in (1, 2, 3, 4):   # telescoping cannon: every sleeve slams into the one behind (80% of the barrel length)
    _h('longbow')[f'Barrel{_k}Pivot'] = recoil(up(26), 1.72 * _k, attack=0.05, recover=0.33, repeat=3, every=0.4)
_h('longbow')['@fire'] = dict(kick=0.09, slide=0.35, attack=0.05, recover=0.5, period=3.8, repeat=3, every=0.4)
# Javelin (missile tank): 4-rocket ripple 0.2 s apart hopping between the pods, reload 5.0 s (5.6 s cycle).
for _k, (_s, _i, _j) in enumerate([('L', 0, 1), ('R', 2, 1), ('L', 2, 1), ('R', 0, 1)]):
    _h('javelin')[f'Msl{_s}{_i}{_j}Pivot'] = launch(up(16), 0.2 * _k, reload=4.4)
_h('javelin')['@fire'] = dict(kick=0.012, slide=0.04, attack=0.05, recover=0.25, period=5.6, repeat=4, every=0.2)
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
    if '@idle' in anims:
        j['scenes'][j.get('scene', 0)].setdefault('extras', {})['idle'] = anims['@idle']
        found.add('@idle')
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
