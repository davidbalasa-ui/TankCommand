"""Towers that travel packed on a carrier and unfold where they deploy.

Each tower is built once from three rigid groups: Carrier (the vehicle), Base (the footing) and
Turret (the weapon). The packed unit model bakes the folded poses into one mesh. The deployed
structure keeps the groups as separate nodes; each node carries its folded pose in glTF extras
(`packed`: p, r, s) so the game can glide every part from one shape to the other.
"""
import forge as F
from forge import box, cyl, prism, tube, trs
import terran_kit as TK
import kesh_kit as KK
import terran_units as TU
import terran_structures as TS
import kesh_units as KU
import kesh_structures as KS

ASSETS = {}
HIDE = trs(t=(0, 0, 0.03), s=(0.5, 0.5, 0.08))   # the carrier settles flat inside the footing


def register(key, faction, build, unit, structure):
    """unit / structure = (path, label, name)."""
    crev = dict(crevice=(0.75, 0.55, 0.4)) if faction == 'kesh' else {}

    def run_unit(glb, render, report):
        F.begin(faction)
        info = build()
        F.apply_poses(info['packed'])
        F.finish(unit[2], glb, render=render, report=report, label=unit[1], size=512, **crev)

    def run_structure(glb, render, report):
        F.begin(faction)
        info = build()
        for o in F.ST['parts']:
            if o['group'] == 'Carrier':
                o['uv'] = float(o.get('uv', F.UV_PRIORITY.get(o['zone'], 1.0))) * 0.5
        poses = {g: dict(packed=m) for g, m in info['packed'].items()}
        poses['Carrier'] = dict(deployed=HIDE)
        F.finish(structure[2], glb, render=render, report=report, label=structure[1], size=1024,
                 pivot=('Turret', (0, 0, info['tz'])), poses=poses, bake_offset={'Carrier': (40.0, 0, 0)},
                 clip=render[:-4] + '_unfold.mp4', **crev)

    ASSETS[key + '_packed'] = dict(fn=run_unit, path=unit[0], set=faction)
    ASSETS[structure[0].split('/')[-1][:-4]] = dict(fn=run_structure, path=structure[0], set='structures')


def terran_carrier():
    L, hw, top = 6.2, 1.22, 1.25
    with F.group('Carrier'):
        TK.chassis(L, hw, top, stowage=False, nose=0.9)
        TU.cab(2.1, 0.0, top + 0.02, 0.6, 0.8, 0.5)
        box((-0.9, 0, top + 0.06), (2.1, 1.5, 0.07), 'armor', bevel=0.03)
    return top + 0.13


def bastion():
    deck = terran_carrier()
    with F.group('Base'):
        z = TS.foundation(2.0, 0.34)
        tube((0, 0, z), (0, 0, z + 0.7), [(0, 1.35), (0.25, 1.35), (0.45, 1.05), (1, 0.98)], 8, 'armor', sharp=30, bevel=0.03)
        for a in range(4):
            b = prism([(0.9, z), (1.75, z), (1.1, z + 0.6)], -0.1, 0.1, 'plate', bevel=0.025)
            F.rot(b, 'Z', 45 + 90 * a)
            v = box((1.2, 0, z + 0.45), (0.012, 0.3, 0.12), 'vent')
            F.rot(v, 'Z', 90 * a + 90)
    tz = z + 0.7
    with F.group('Turret'):
        tube((0, 0, tz - 0.03), (0, 0, tz + 0.1), [(0, 1.0), (1, 0.95)], 20, 'dark')
        TU.turret_shell(-1.35, 1.05, 1.05, tz, 0.86)
        F.plate([(-0.9, -0.6), (0.3, -0.55), (0.55, 0), (0.3, 0.55), (-0.9, 0.6)], tz + 0.85, tz + 0.92, 'plate', inset=0.05, bevel=0.02)
        box((1.12, 0, tz + 0.4), (0.2, 0.72, 0.26), 'dark', bevel=0.05)
        for s in (1, -1):
            TK.railgun(1.1, 4.3, s * 0.4, tz + 0.4, 0.13)
            cyl((-0.5, s * 1.0, tz + 0.42), (-0.5, s * 1.32, tz + 0.42), 0.36, 12, 'plate')
            cyl((-0.5, s * 1.32, tz + 0.42), (-0.5, s * 1.35, tz + 0.42), 0.16, 8, 'amber')
            box((-0.2, s * 1.07, tz + 0.75), (0.5, 0.012, 0.02), 'glow')
        box((-0.3, 0.45, tz + 1.0), (0.2, 0.16, 0.1), 'dark', bevel=0.03)
        box((-0.1, 0.45, tz + 1.01), (0.012, 0.1, 0.06), 'glass')
        TK.antenna(-1.0, -0.5, tz + 0.75, 1.0)
    sb = (0.68, 0.68, 0.55)
    return dict(tz=tz, packed={
        'Base': trs(t=(-0.8, 0, deck), s=sb),
        # Gun turned to the rear and drawn in, seated on the folded footing.
        'Turret': trs(t=(-0.8, 0, deck + tz * sb[2] - tz), r=(0, 0, 180), s=(0.78, 0.78, 0.78), about=(0, 0, tz)),
    })


def spire():
    deck = terran_carrier()
    with F.group('Base'):
        z = TS.foundation(2.0, 0.34)
        tube((0, 0, z), (0, 0, z + 0.9), [(0, 1.2), (0.3, 1.2), (0.5, 0.8), (1, 0.72)], 8, 'armor', sharp=30, bevel=0.03)
        for a in range(4):
            b = prism([(0.7, z), (1.7, z), (0.85, z + 0.75)], -0.1, 0.1, 'plate', bevel=0.025)
            F.rot(b, 'Z', 45 + 90 * a)
    tz = z + 0.9
    with F.group('Turret'):
        tube((0, 0, tz - 0.03), (0, 0, tz + 0.12), [(0, 0.82), (1, 0.75)], 16, 'dark')
        box((-0.1, 0, tz + 0.6), (0.5, 0.42, 0.5), 'armor', bevel=0.06)
        cyl((0, -1.1, tz + 0.75), (0, 1.1, tz + 0.75), 0.15, 10, 'dark')
        for s in (1, -1):
            m = F.mark()
            TK.missile_box((0.2, s * 1.05, tz + 0.75), (1.35, 0.52, 0.52), nx=2, nz=2)
            box((0.2, s * 1.585, tz + 0.75), (1.0, 0.012, 0.02), 'glow')
            box((1.0, s * 1.05, tz + 1.29), (0.3, 0.35, 0.012), 'hazard')
            F.rot_all(m, 'Y', -38, about=(0, 0, tz + 0.75))
        box((0.25, 0, tz + 1.2), (0.22, 0.2, 0.12), 'dark', bevel=0.04)
        box((0.48, 0, tz + 1.2), (0.012, 0.14, 0.07), 'glass')
        tube((-0.5, 0, tz + 1.1), (-0.5, 0, tz + 1.5), [(0, 0.05), (0.7, 0.05), (0.7, 0.3), (1, 0.22)], 10, 'plate')
        TK.beacon(-0.5, 0, tz + 1.5, 'red')
    sb = (0.68, 0.68, 0.5)
    return dict(tz=tz, packed={
        'Base': trs(t=(-0.8, 0, deck), s=sb),
        # Launchers laid level, noses to the rear.
        'Turret': trs(t=(-0.8, 0, deck + tz * sb[2] - tz), r=(0, 38, 180), s=(0.8, 0.8, 0.8), about=(0, 0, tz + 0.75)),
    })


def kesh_carrier():
    with F.group('Carrier'):
        KU.carrier()
    return 1.3


def thornmound():
    deck = kesh_carrier()
    with F.group('Base'):
        z = KS.dais(2.0, 0.42)
        KK.claws((0, 0, z - 0.15), 3, 1.45, 0.95, width=0.34, zone='bronze', start=60)
    tz = z + 1.0
    with F.group('Turret'):
        KS.thorn_turret(tz)
    sb = (0.6, 0.6, 0.5)
    return dict(tz=tz, packed={
        'Base': trs(t=(-0.6, 0, deck), s=sb),
        'Turret': trs(t=(-0.6, 0, deck + 0.75 - tz), r=(0, 0, 180), s=(0.74, 0.74, 0.74), about=(0, 0, tz)),
    })


def spore_tower():
    deck = kesh_carrier()
    with F.group('Base'):
        z = KS.dais(1.9, 0.42)
        for k in range(3):
            KS.horn((0, 0, z - 0.2), 2.3, 1.5, 'bronze', 0.4, -8, 78, yaw=120 * k + 60)
    tz = z + 1.3
    with F.group('Turret'):
        KS.spore_pod(tz)
    return dict(tz=tz, packed={
        'Base': trs(t=(-0.4, 0, deck), s=(0.58, 0.58, 0.4)),
        # The pod travels lying down, crown to the rear, seekers pointing up.
        'Turret': trs(t=(0.75, 0, 1.95 - tz), r=(0, -90, 0), s=(0.68, 0.68, 0.68), about=(0, 0, tz)),
    })


register('bastion', 'terran', bastion,
         ('human/bastion_packed.glb', 'Terran Bastion Gun, packed for transport', 'BastionPacked'),
         ('structures/terran_turret.glb', 'Terran Bastion Gun (turret)', 'TerranTurret'))
register('spire', 'terran', spire,
         ('human/spire_packed.glb', 'Terran Spire Missile Battery, packed for transport', 'SpirePacked'),
         ('structures/terran_missile_battery.glb', 'Terran Spire Missile Battery', 'TerranMissileBattery'))
register('thornmound', 'kesh', thornmound,
         ('alien/thornmound_packed.glb', 'Kesh Thornmound, packed for transport', 'ThornmoundPacked'),
         ('structures/kesh_thornmound.glb', 'Kesh Thornmound (turret)', 'KeshThornmound'))
register('spore_tower', 'kesh', spore_tower,
         ('alien/spore_tower_packed.glb', 'Kesh Spore Tower, packed for transport', 'SporeTowerPacked'),
         ('structures/kesh_spore_tower.glb', 'Kesh Spore Tower (missile battery)', 'KeshSporeTower'))
