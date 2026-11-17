"""Rebuild models.json and model_parts.md from the model files and the game data.

    /home/user/artenv/venv/bin/python tools/promos/build_registry.py

Run it again after models are added or renamed. Sizes follow the game: a unit is scaled so the larger of its
length and width is 4.5 m x visualScale; a plain structure fills its footprint (cells x 2 m); a tower (a structure
with packed parts) uses the same scale as its packed vehicle, because the two models share units.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
GAME = os.path.join(REPO, 'public', 'assets', 'models')
FLEET = '/mnt/project-files/promos/models/fleet/'
CELL = 2.0

HOVER = {'skimmer'}
PACKED_OF = {  # deployed structure -> packed vehicle model
    'terran_turret': 'bastion_packed', 'terran_missile_battery': 'spire_packed', 'terran_radar': 'radar_tower_packed',
    'terran_metal_station': 'metal_station_packed', 'terran_air_base': 'air_base_packed',
    'kesh_thornmound': 'thornmound_packed', 'kesh_spore_tower': 'spore_tower_packed', 'kesh_seer_spire': 'radar_tower_packed',
    'kesh_metal_siphon': 'metal_station_packed', 'kesh_hive_roost': 'air_base_packed',
}
SHIPS = {  # promo name -> (file stem, faction, game name)
    'terran_fighter': ('terran_twinx_fighter', 'terran', 'Twin-X fighter'), 'terran_corvette': ('terran_corvette', 'terran', 'Corvette'),
    'terran_frigate': ('terran_frigate', 'terran', 'Frigate'), 'terran_missile_ship': ('terran_missile_ship', 'terran', 'Missile ship'),
    'terran_battleship': ('terran_broadside_battleship', 'terran', 'Broadside battleship'),
    'terran_dreadnought': ('terran_dreadnought', 'terran', 'Dreadnought'),
    'arcadian_fighter': ('arcadian_stingray_fighter', 'arcadian', 'Stingray fighter'), 'arcadian_corvette': ('arcadian_corvette', 'arcadian', 'Corvette'),
    'orb': ('arcadian_orb_rigged_animated', 'arcadian', 'Orb anti-fighter'),
    'arcadian_shell_mothership': ('arcadian_shell_mothership', 'arcadian', 'Shell mothership'),
    'arcadian_crescent_mothership': ('arcadian_crescent_mothership', 'arcadian', 'Crescent mothership'),
    'arcadian_lens_mothership': ('arcadian_lens_mothership', 'arcadian', 'Lens mothership'),
}


def main():
    units = json.load(open(os.path.join(REPO, 'src/data/units.placeholder.json')))
    units = units if isinstance(units, list) else units['units']
    structs = json.load(open(os.path.join(REPO, 'src/data/structures.placeholder.json')))
    structs = structs if isinstance(structs, list) else structs['structures']
    manifest = json.load(open(os.path.join(REPO, 'public/assets/manifest.json')))
    assets = manifest.get('assets', manifest)
    assets = assets if isinstance(assets, dict) else {a['id']: a for a in assets}
    stem_of = {k: os.path.splitext(os.path.basename(v.get('path') or v.get('url') or ''))[0] for k, v in assets.items() if isinstance(v, dict)}
    by_stem = {}
    for u in units:
        st = stem_of.get(u['modelAssetId'], u['modelAssetId'].split('.')[-1])
        by_stem.setdefault(('alien' if u['faction'] == 'alien' else 'human', st), u)
    sby = {stem_of.get(s['modelId']): s for s in structs}

    files = []
    for d in ('human', 'alien', 'props', 'structures'):
        for f in sorted(os.listdir(os.path.join(GAME, d))):
            if f.endswith('.glb') and not f.endswith('_lod.glb') and f != 'poc_tank.glb':
                files.append(os.path.join(GAME, d, f))
    ships = [os.path.join(FLEET, v[0] + '.blend') for v in SHIPS.values()]
    tmp = os.path.join(HERE, '_parts.json')
    subprocess.run([sys.executable, os.path.join(HERE, 'dump_parts.py'), tmp] + files + ships, check=True, stdout=subprocess.DEVNULL)
    parts = json.load(open(tmp))
    os.remove(tmp)

    reg, dims = {}, {}
    for f in files:
        d, stem = os.path.basename(os.path.dirname(f)), os.path.splitext(os.path.basename(f))[0]
        p = parts[f]
        sx, sy, sz = (h - l for l, h in zip(p['lo'], p['hi']))
        big = max(sx, sy)
        name = stem
        fac = {'human': 'terran', 'alien': 'arcadian', 'props': 'neutral'}.get(d)
        if d == 'structures':
            fac = 'terran' if stem.startswith('terran') else 'shard' if stem.startswith('shard') else 'arcadian'
        if d in ('human', 'alien') and stem.endswith('_packed') and stem in ('radar_tower_packed', 'metal_station_packed', 'air_base_packed'):
            name = ('terran_' if d == 'human' else 'arcadian_') + stem
        e = dict(files=[f'{d}/{stem}.glb'], faction=fac, native=round(big, 3))
        if d in ('human', 'alien'):
            u = by_stem.get((d, stem))
            vs = (u or {}).get('visualScale') or (1.2 if stem in ('halo', 'dragonfly') else 1.0)
            role = (u or {}).get('role', 'air')
            e['kind'] = 'air' if role == 'air' else 'hover' if (d == 'alien' or stem in HOVER) else 'ground'
            if stem.endswith('_packed'):
                e['kind'] = 'hover' if d == 'alien' else 'ground'
                e['packed'] = True
            e['game'] = 'Dragonfly' if stem == 'dragonfly' else 'Halo' if stem == 'halo' else (u or {}).get('name', stem.title())
            e['role'] = role
            e['size'] = round(4.5 * vs, 3)
            if u and u.get('weapons'):
                w = u['weapons'][0]
                e['weapon'] = {k: w[k] for k in ('id', 'range', 'reloadSec', 'projectileSpeed', 'burst', 'burstIntervalSec', 'targets') if k in w}
            if u:
                e['speed'] = u['speed']['top']
        elif d == 'props':
            e.update(kind='prop', game=stem, size=round(big * 0.45, 3))
        else:
            s = sby.get(stem)
            e.update(kind='structure', game=(s or {}).get('name', stem))
            fp = (s or {}).get('footprint', {'cellsX': 2, 'cellsZ': 2})
            e['size'] = round(max(fp['cellsX'], fp['cellsZ']) * CELL, 3)
            e['footprint_m'] = e['size']
            if s and s.get('weapon'):
                w = s['weapon']
                e['weapon'] = {k: w[k] for k in ('range', 'reloadSec', 'projectileSpeed', 'burst', 'burstIntervalSec', 'targets') if k in w}
            if any('packed' in n['extras'] for n in p['nodes']):
                e['kind'] = 'tower'
        reg[name] = e
        dims[name] = (d, stem, big)
    # towers share units with their packed vehicle: use the vehicle's scale so the unfold needs no size change
    for name, e in reg.items():
        if e['kind'] == 'tower':
            d, stem, big = dims[name]
            pk = PACKED_OF.get(stem)
            pname = pk if pk in reg else ('terran_' if stem.startswith('terran') else 'arcadian_') + (pk or '')
            if pname in reg:
                scale = reg[pname]['size'] / reg[pname]['native']
                e['size'] = round(big * scale, 3)
                e['packed_model'] = pname
    for name, (stem, fac, game) in SHIPS.items():
        f = os.path.join(FLEET, stem + '.blend')
        p = parts[f]
        big = max(h - l for l, h in zip(p['lo'], p['hi']))
        reg[name] = dict(files=[f'fleet/{stem}.blend'], faction=fac, kind='ship', game=game, native=round(big, 3), size=round(big, 3))
    json.dump(reg, open(os.path.join(HERE, 'models.json'), 'w'), indent=1)

    out = ['# Model parts', '', 'Generated by build_registry.py. Node names and `anim` / `packed` tags of every registered model.',
           'Sizes are native model units (x = length, front is +X; y = width; z = height).', '']
    inv = {}
    for name, e in reg.items():
        inv[e['files'][0]] = name
    for f in files + ships:
        rel = os.path.relpath(f, GAME) if f.startswith(GAME) else 'fleet/' + os.path.basename(f)
        name = inv.get(rel, rel)
        p = parts[f]
        e = reg[name]
        out.append(f"## {name}  ({e['game']}, {e['faction']}, {e['kind']})")
        out.append(f"file `{rel}`, native size {[round(h - l, 2) for l, h in zip(p['lo'], p['hi'])]}, scene size {e['size']} m, {p['tris']} triangles")
        if e.get('weapon'):
            out.append(f"weapon: `{json.dumps(e['weapon'])}`")
        nodes = p['nodes']
        if len(nodes) > 40:
            out.append(f"{len(nodes)} nodes; first 40 shown.")
        for n in nodes[:40]:
            tags = {k: v for k, v in n['extras'].items() if k in ('anim', 'packed', 'hideWhenDeployed')}
            other = [k for k in n['extras'] if k not in tags]
            tag = ''
            if 'anim' in tags:
                tag += ' anim=' + json.dumps(tags['anim'], default=str)
            if 'packed' in tags:
                tag += ' packed-pose'
            if 'hideWhenDeployed' in tags:
                tag += ' hideWhenDeployed'
            if other:
                tag += ' props=' + ','.join(other)
            out.append(f"- `{n['name']}` ({n['type'].lower()}{', child of ' + n['parent'] if n['parent'] else ''}) at {n['loc']}{tag}")
        out.append('')
    open(os.path.join(HERE, 'model_parts.md'), 'w').write('\n'.join(out))
    print(len(reg), 'models registered')


if __name__ == '__main__':
    main()
