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
        pivot = info['pivot'] if 'pivot' in info else (0, 0, info['tz'])
        plist = ([('Turret', pivot, 'TurretPivot')] if pivot else []) + list(info.get('more', []))
        F.finish(structure[2], glb, render=render, report=report, label=structure[1], size=1024,
                 pivot=plist or None, poses=poses, bake_offset={'Carrier': (40.0, 0, 0)},
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


# ------------------------------------------------------------------ packed buildings
# Radar, metal station and airfield also travel folded on a carrier. They reuse the finished
# building: its parts are sorted into a few rigid groups, and each group has a stowed pose.
import contextlib


def centre(o):
    vs = o.data.vertices
    n = max(len(vs), 1)
    return (sum(v.co.x for v in vs) / n, sum(v.co.y for v in vs) / n, sum(v.co.z for v in vs) / n)


@contextlib.contextmanager
def tagged(mod, **names):
    """While active, parts made by mod.<function> go into the given group."""
    saved = {}
    for fname, grp in names.items():
        orig = getattr(mod, fname)
        saved[fname] = orig

        def wrap(*a, _o=orig, _g=grp, **k):
            with F.group(_g):
                return _o(*a, **k)
        setattr(mod, fname, wrap)
    try:
        yield
    finally:
        for fname, orig in saved.items():
            setattr(mod, fname, orig)


def sort_rest(rule, rename=None):
    """Give every part still in the 'Rest' group its real group, from where it sits."""
    for o in F.ST['parts']:
        if o['group'] == 'Rest':
            o['group'] = rule(*centre(o))
        elif rename and o['group'] in rename:
            o['group'] = rename[o['group']]


def stow(c, to, s, r=(0, 0, 0)):
    """Pose that scales and turns a group about c and carries c to `to`."""
    if isinstance(s, (int, float)):
        s = (s, s, s)
    return trs(t=(to[0] - c[0], to[1] - c[1], to[2] - c[2]), r=r, s=s, about=c)


def terran_radar_tower():
    deck = terran_carrier()
    with tagged(TS, foundation='Base'), F.group('Rest'):
        TS.terran_radar.build()
    z, top = 0.34, 0.34 + 4.6
    sort_rest(lambda x, y, zz: 'Mast' if zz > 1.3 else 'Base', rename={'Dish': 'Turret'})
    tz = top + 0.16
    return dict(tz=tz, packed={
        'Base': trs(t=(-0.8, 0, deck), s=(0.68, 0.68, 0.55)),
        # The lattice mast telescopes down over the equipment hut; the dish rides on top, facing aft.
        'Mast': stow((0, 0, z + 0.1), (-0.8, 0, deck + 0.19), (0.62, 0.62, 0.2)),
        'Turret': stow((0, 0, tz), (-0.8, 0, deck + 1.14), 0.55, r=(0, 0, 180)),
    })


def terran_metal_station():
    deck = terran_carrier()
    with tagged(TS, foundation='Base'), F.group('Rest'):
        TS.terran_metal_station.build()
    z = 0.32

    def rule(x, y, zz):
        if y < -1.2:
            return 'Hopper'
        if x > 1.9:
            return 'Tanks'
        if abs(x - 0.6) < 0.6 and abs(y - 1.3) < 0.6 and zz > z + 2.3:
            return 'Stack'
        return 'Smelter'
    sort_rest(rule)
    zb = deck + 0.1
    return dict(pivot=None, packed={
        'Base': trs(t=(-0.9, 0, deck), s=(0.5, 0.3, 0.3)),
        'Smelter': stow((-0.6, 1.0, z), (-2.0, 0.1, zb), 0.45),
        'Hopper': stow((0, -2.3, z), (0.5, 0.2, zb), 0.42),
        'Tanks': stow((2.6, 0.75, z), (-0.7, 0.75, zb), 0.45),
        # The chimney is carried lying down along the deck.
        'Stack': stow((0.6, 1.3, z + 2.2), (-1.0, -0.78, zb + 0.36), 0.6, r=(0, 90, 0)),
    })


def terran_air_base():
    deck = terran_carrier()
    with tagged(TS, foundation='Base'), F.group('Rest'):
        TS.terran_air_base.build()
    z = 0.3

    def rule(x, y, zz):
        if (x - 3.8) ** 2 + (y + 3.6) ** 2 < 1.6 ** 2:
            return 'Tower'
        if x < -1.0 and y < -1.2:
            return 'Hangar'
        if -0.2 <= x <= 2.6 and y < -1.3:
            return 'Fuel'
        return 'Base'
    sort_rest(rule)
    zb = deck + 0.1
    tower = stow((3.8, -3.6, z), (1.0, -0.6, zb + 0.56), 0.4, r=(0, -90, 0))
    return dict(pivot=None, more=[('TowerDish', (4.3, -3.1, z + 4.5), 'DishPivot')], packed={
        'Base': trs(t=(-0.9, 0, deck), s=(0.34, 0.2, 0.3)),
        'Hangar': stow((-3.1, -3.4, z), (-2.0, 0, zb), 0.42),
        # The control tower is carried lying down, cab to the rear.
        'Tower': tower,
        'TowerDish': tower,
        'Fuel': stow((1.4, -3.95, z), (-0.2, 0.62, zb), 0.5),
    })


def kesh_seer_spire():
    deck = kesh_carrier()
    with tagged(KS, dais='Base'), F.group('Rest'):
        KS.kesh_seer_spire.build()
    z = 0.56
    sort_rest(lambda x, y, zz: 'Horns', rename={'Eye': 'Turret'})
    tz = z + 3.4
    return dict(tz=tz, packed={
        'Base': trs(t=(-0.6, 0, deck), s=(0.55, 0.55, 0.5)),
        # Horns drawn in low, cradling the eye.
        'Horns': stow((0, 0, z), (-0.6, 0, deck + z * 0.5), (0.55, 0.55, 0.3)),
        'Turret': stow((0, 0, tz), (-0.6, 0, deck + 1.25), 0.65),
    })


def kesh_metal_siphon():
    deck = kesh_carrier()
    with tagged(KS, dais='Base', horn='Horns'), F.group('Rest'):
        KS.kesh_metal_siphon.build()
    z = 0.59

    def rule(x, y, zz):
        if y < -1.0:
            return 'Basin'
        if x > 1.8 or zz < z + 0.8:
            return 'Base'
        return 'Turret'
    sort_rest(rule)
    pv = (0, 0.5, z + 3.9)
    return dict(pivot=pv, packed={
        'Base': trs(t=(-0.7, 0, deck), s=(0.32, 0.32, 0.4)),
        'Horns': stow((0, 0.5, z), (-0.7, 0.16, deck + z * 0.4), (0.3, 0.3, 0.26)),
        # The core sinks down its column into the folded horns.
        'Turret': stow(pv, (-0.7, 0.16, deck + 1.3), (0.42, 0.42, 0.28)),
        'Basin': stow((0, -2.2, z), (0.9, 0, deck + 0.02), 0.4),
    })


def kesh_hive_roost():
    deck = kesh_carrier()
    with tagged(KS, dais='Base', horn='Ribs'), F.group('Rest'):
        KS.kesh_hive_roost.build()
    z = 0.59

    def rule(x, y, zz):
        if zz > z + 4.5:
            return 'Turret'
        if zz > z + 1.2:
            return 'Perches'
        return 'Base'
    sort_rest(rule)
    pv = (0, 0, z + 4.9)
    return dict(pivot=pv, packed={
        'Base': trs(t=(-0.6, 0, deck), s=(0.21, 0.21, 0.4)),
        'Ribs': stow((0, 0, z), (-0.6, 0, deck + z * 0.4), (0.24, 0.24, 0.3)),
        'Turret': stow(pv, (-0.6, 0, deck + 1.65), 0.45),
        'Perches': stow((0, 0, z + 2.7), (-0.6, 0, deck + 0.8), 0.3),
    })


register('terran_radar_tower', 'terran', terran_radar_tower,
         ('human/radar_tower_packed.glb', 'Terran Radar Tower, packed for transport', 'RadarTowerPacked'),
         ('structures/terran_radar.glb', 'Terran Radar Tower', 'TerranRadar'))
register('terran_metal_station', 'terran', terran_metal_station,
         ('human/metal_station_packed.glb', 'Terran Metal Station, packed for transport', 'MetalStationPacked'),
         ('structures/terran_metal_station.glb', 'Terran Metal Station (refinery)', 'TerranMetalStation'))
register('terran_air_base', 'terran', terran_air_base,
         ('human/air_base_packed.glb', 'Terran Airfield, packed for transport', 'AirBasePacked'),
         ('structures/terran_air_base.glb', 'Terran Airfield', 'TerranAirBase'))
register('kesh_seer_spire', 'kesh', kesh_seer_spire,
         ('alien/radar_tower_packed.glb', 'Arcadian Seer Spire, packed for transport', 'SeerSpirePacked'),
         ('structures/kesh_seer_spire.glb', 'Kesh Seer Spire (sensor)', 'KeshSeerSpire'))
register('kesh_metal_siphon', 'kesh', kesh_metal_siphon,
         ('alien/metal_station_packed.glb', 'Arcadian Metal Siphon, packed for transport', 'MetalSiphonPacked'),
         ('structures/kesh_metal_siphon.glb', 'Kesh Metal Siphon (refinery)', 'KeshMetalSiphon'))
register('kesh_hive_roost', 'kesh', kesh_hive_roost,
         ('alien/air_base_packed.glb', 'Arcadian Hive Roost, packed for transport', 'HiveRoostPacked'),
         ('structures/kesh_hive_roost.glb', 'Kesh Hive Roost (air base)', 'KeshHiveRoost'))
