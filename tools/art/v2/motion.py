"""Moving parts: which nodes of which models the game should animate, and how.

    python motion.py <models dir>

Writes an `anim` entry into the glTF extras of each listed node (and of the same node in the
model's _lod file). The game reads it from node.userData.anim:

    type   'spin'   turn about `axis` at `speed` rad/s
           'swing'  rock about `axis`: angle = amp * sin(2 pi * speed * t), speed in Hz
    axis   in the node's own glTF space (Y up, model front +X)
    when   'always' | 'mining' | 'working' (repairing or building) | 'moving'
    busySpeed  optional: speed to use instead while the unit is working

Nodes are pivots placed on the part's axis, so the game only ever rotates the node itself.
"""
import json
import os
import struct
import sys

UP, FWD, LEFT = [0, 1, 0], [1, 0, 0], [0, 0, -1]


def spin(axis, speed, when='always', **kw):
    return dict(type='spin', axis=axis, speed=speed, when=when, **kw)


def swing(axis, amp, speed, when='always', **kw):
    return dict(type='swing', axis=axis, amp=amp, speed=speed, when=when, **kw)


SPEC = {
    'human/prospector': {'DrumPivot': spin(LEFT, 6.0, 'mining')},
    'alien/gorger': {'GrinderPivot': spin(FWD, 8.0, 'mining')},
    'human/watchman': {'TurretPivot': spin(UP, 1.2)},
    'alien/seer': {'TurretPivot': spin(UP, 0.8)},
    'alien/weaver': {'TurretPivot': spin(UP, 1.0, busySpeed=4.0)},
    'human/mender': {'TurretPivot': swing(UP, 0.6, 0.5, 'working')},
    'alien/disc': {'BladesPivot': spin(UP, 1.5)},
    'alien/dragonfly': {'WingLPivot': swing(FWD, 0.2, 9.0), 'WingRPivot': swing([-1, 0, 0], 0.2, 9.0)},
    'structures/terran_radar': {'TurretPivot': spin(UP, 1.0)},
    'structures/terran_air_base': {'DishPivot': spin(UP, 1.0)},
    'structures/kesh_seer_spire': {'TurretPivot': spin(UP, 0.6)},
    'structures/kesh_metal_siphon': {'TurretPivot': spin(UP, 0.5)},
    'structures/kesh_hive_roost': {'TurretPivot': spin(UP, 0.3)},
    'structures/kesh_gene_vault': {'CrownPivot': spin(UP, 0.5)},
}


def patch(path, anims):
    d = open(path, 'rb').read()
    jl = struct.unpack('<I', d[12:16])[0]
    j = json.loads(d[20:20 + jl])
    rest = d[20 + jl:]
    found = set()
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
