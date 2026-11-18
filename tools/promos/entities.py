"""Master list of promo clips: one ~6 s clip per entity, each with its own brief.

    python tools/promos/entities.py      # writes briefs/<id>.md and CHECKLIST.md from this file

Status lives in status.json ({id: {"state": ..., "note": ...}}), states:
    todo | scripted | preview | sample-shown | approved | final
`model_state` says whether the model is settled (render final now) or may still change (script now,
re-render once the art is approved): settled | pending-terran-restore | pending-arcadian-readability |
film-placeholder.

Every brief is a starting point, not a script: the worker should think about what this thing is
for and stage the most characterful 6 seconds it can. The cast list may hold more than needed.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

RULES = """\
Standing rules for every clip (from David):
- About 6 seconds, 24 fps, no words or titles on screen.
- A real little combat or work story, never a straight line demo. The camera moves with intent
  (orbit, push in, follow, low hero angles) and ends on a strong frame.
- Every gun: barrel collapses ~80% into the turret on each shot, muzzle flash, hull kick (mortar
  and artillery kick hugely). Each unit fires at its OWN rhythm (scouts fast and weak, heavy tanks
  one devastating blast about once a second, artillery 3 quick blasts then a long reload, rocket
  units pause then ripple-fire).
- Arcadians use LIGHTNING for thrusters and lifters (gold lightning, never flames). Arcadian
  weapons are gold lightning or gold energy. Terran glow is neon blue with orange accents.
- Shields NEVER shatter. Anything pushing through a shield makes it stretch and wrap around it.
- No vehicle has a pilot: no cockpits, canopies or windows anywhere, including props you add.
- The Dragonfly is an anti-air-only interceptor: it never attacks ground targets.
- Ore buys everything; metal is only for research.
"""

T, A = 'Terran', 'Arcadian'

# id, title, faction, kind, hero model (models.json), model_state, brief, cast
CLIPS = [
    # ------------------------------------------------------------------ Terran ground
    ('terran_lancer', 'Lancer (light tank)', T, 'tank', 'lancer', 'pending-terran-restore',
     'The workhorse. A pair of Lancers advance through broken ground, fire on the move (cannon, ~1.8 s '
     'reload) and trade shots with a Lumen; one Lancer takes a lightning hit, rocks, keeps rolling and '
     'finishes the Lumen. Show it is cheap, quick and dependable in numbers.',
     ['lancer x2-3', 'lumen x1-2']),
    ('terran_outrider', 'Outrider (scout)', T, 'scout', 'outrider', 'pending-terran-restore',
     'Fast six-wheeled scout. It rushes in over a rise, slides sideways to peek at an Arcadian camp '
     '(a couple of Lumens and a Sifter), snaps off a few autocannon bursts (3-round bursts, weak, fast), '
     'and races back out as lightning lands where it just was. Speed, wheel spin, dust, cheek.',
     ['outrider', 'lumen x2-3', 'sifter']),
    ('terran_prospector', 'Prospector (ore miner)', T, 'worker', 'prospector', 'pending-terran-restore',
     'Ore miner. It rolls up to an ore deposit, its drum spins up, chunks of glowing ore fly into its '
     'hopper and the load visibly grows; a Hauler waits nearby. Industrial, satisfying, no combat.',
     ['prospector', 'deposit_ore', 'hauler (optional)']),
    ('terran_hauler', 'Hauler (tug)', T, 'worker', 'hauler', 'pending-terran-restore',
     'Hauler with its crane. It picks up a loaded cargo container from a Prospector at the ore field, '
     'swings it aboard, then drives to the Landing Pad delivery spot and sets the cargo down for lift. '
     'Show the cargo clearly.',
     ['hauler', 'prospector', 'deposit_ore', 'terran_landing_pad']),
    ('terran_mender', 'Mender (repair)', T, 'support', 'mender', 'pending-terran-restore',
     'Field repair. A battered, smoking Bulwark limps back; the Mender pulls alongside, its arm swings '
     'over and a blue-green repair beam knits the damage while the smoke thins out. Calm in the middle '
     'of a fight in the background (distant flashes).',
     ['mender', 'bulwark (damaged)', 'distant explosions']),
    ('terran_watchman', 'Watchman (radar truck)', T, 'support', 'watchman', 'pending-terran-restore',
     'Radar truck parks on a hill, dish spinning. A radar ping sweeps out across the ground (expanding '
     'ring of light), revealing hidden Arcadian units in the haze that flash an outline; a Longbow '
     'barrage then falls on what it found.',
     ['watchman', 'lumen/flare hidden', 'shells from off screen']),
    ('terran_skimmer', 'Skimmer (hover tank)', T, 'tank', 'skimmer', 'pending-terran-restore',
     'Hover tank with four fans. It skims across shallow water or a dry riverbed spraying dust, swings '
     'round fast, fires a 2-round burst on the move at Arcadian Gliders and drifts sideways to dodge '
     'return fire. Agile and slippery.',
     ['skimmer x1-2', 'glider x2']),
    ('terran_bulwark', 'Bulwark (heavy tank)', T, 'tank', 'bulwark', 'pending-terran-restore',
     'Heavy tank. Lightning bolts splash off its front armour as it grinds forward unbothered; it stops, '
     'turret settles, ONE devastating blast (huge recoil, barrel slams back 80%, dust ring) obliterates '
     'an Aegis. Slow, inevitable, heavy.',
     ['bulwark', 'aegis', 'lumen (optional)']),
    ('terran_javelin', 'Javelin (missile tank)', T, 'tank', 'javelin', 'pending-terran-restore',
     'Missile tank. Its launcher raises, a pause, then a rapid back-and-forth ripple of 4 missiles '
     'arcing into the sky, smoke trails curling, hitting a Halo flight overhead (anti-air) or a '
     'Flare on the ground. Show it hits air.',
     ['javelin', 'halo x2 or flare']),
    ('terran_longbow', 'Longbow (artillery)', T, 'artillery', 'longbow', 'pending-terran-restore',
     'Long-range artillery. Camera starts on the Longbow, barrel elevated: 3 blasts within one second '
     '(huge hull kick each time, barrel collapses 80%), shells arc away; cut/sweep along the shells to '
     'the far target, an Arcadian structure group, where the three land in a walking pattern. Then the '
     'long reload.',
     ['longbow', 'sentinel or arcadian structures', 'lumen x2']),
    ('terran_falcon', 'Falcon (fighter)', T, 'air', 'falcon', 'settled',
     'Air superiority fighter. Two Falcons bank hard through a valley, chase a Halo, fire twin blue '
     'laser bursts (2-shot), the Halo breaks and falls trailing smoke, Falcons pull up past camera.',
     ['falcon x2', 'halo']),
    ('terran_condor', 'Condor (bomber)', T, 'air', 'condor', 'settled',
     'Bomber run. The Condor flies a straight steady line high over an Arcadian base, bay opens, a '
     'stick of 3 bombs walks across the target, chain of explosions below while it flies on unharmed. '
     'Camera looks up at it, then down at the carpet of fire.',
     ['condor', 'arcadian structures (aerie, sentinel)', 'lumen x2']),
    # ------------------------------------------------------------------ Arcadian ground
    ('arcadian_lumen', 'Lumen (light tank)', A, 'tank', 'lumen', 'pending-arcadian-readability',
     'Arcadian light tank, hovering on lightning lifters. A pack of three Lumens glides in a tight '
     'formation, splits around a rock, and bolts of gold lightning converge on a Lancer. Fluid and '
     'coordinated, like a school of fish.',
     ['lumen x3', 'lancer']),
    ('arcadian_darter', 'Darter (scout)', A, 'scout', 'darter', 'pending-arcadian-readability',
     'Needle-fast scout. It darts zig-zag between Terran Lancers too fast to track, their shots '
     'missing behind it, flicks a few weak lightning shots and vanishes over a ridge. Speed and '
     'insolence.',
     ['darter', 'lancer x2-3']),
    ('arcadian_sifter', 'Sifter (ore miner)', A, 'worker', 'sifter', 'pending-arcadian-readability',
     'Organic-machine miner. Its stag-beetle jaws close round an ore deposit, the glowing grinder '
     'spins, ore dissolves into gold motes streaming into its body, ember-orange glow pulses brighter '
     'as it fills.',
     ['sifter', 'deposit_ore']),
    ('arcadian_ferrier', 'Ferrier (tug)', A, 'worker', 'ferrier', 'pending-arcadian-readability',
     'Barge-like hauler. It lifts a glowing cargo pod in its claws from a Sifter and floats it to the '
     'Landing Ring, where the pod is set down and rises away on a column of light.',
     ['ferrier', 'sifter', 'landing_ring']),
    ('arcadian_weaver', 'Weaver (repair)', A, 'support', 'weaver', 'pending-arcadian-readability',
     'Repair unit with three turning arms. It circles a damaged Aegis, arms spinning faster, threads of '
     'pale gold light weave the armour back together, scorch marks fading.',
     ['weaver', 'aegis (damaged)']),
    ('arcadian_seer', 'Seer (radar)', A, 'support', 'seer', 'pending-arcadian-readability',
     'Sensor unit. Its crescent dish turns, the great eye opens; a wave of pale light washes outward '
     'and Terran units hidden behind a ridge light up as gold outlines; Sunfall orbs then fall on them.',
     ['seer', 'lancer/bulwark hidden', 'sunfall shots']),
    ('arcadian_glider', 'Glider (hover tank)', A, 'tank', 'glider', 'pending-arcadian-readability',
     'Manta-winged hover tank. It sweeps low over a crater lip in a banking curve, wingtip lights '
     'trailing, fires a 2-shot burst at a Skimmer and outmanoeuvres its reply.',
     ['glider x1-2', 'skimmer']),
    ('arcadian_aegis', 'Aegis (heavy tank)', A, 'tank', 'aegis', 'pending-arcadian-readability',
     'Heavy hover tank. Terran tank shells burst against its horned front; it lowers, four cores '
     'brighten one by one, then one massive gold blast destroys a Bulwark. Heavy and regal.',
     ['aegis', 'bulwark', 'lancer']),
    ('arcadian_flare', 'Flare (missile)', A, 'tank', 'flare', 'pending-arcadian-readability',
     'Six glowing pods in an arch. A pause as the pods charge, then a ripple of gold seeker orbs launch '
     'in sequence and curve up to swat a Falcon out of the sky (anti-air) and the rest rain on a Lancer.',
     ['flare', 'falcon', 'lancer']),
    ('arcadian_sunfall', 'Sunfall (artillery)', A, 'artillery', 'sunfall', 'pending-arcadian-readability',
     'Giant-orb artillery. The orb draws in light, the whole body heaves (huge kick) three times in a '
     'second, three small suns arc high over a ridge and crash down on a Terran gun line.',
     ['sunfall', 'bastion', 'lancer x2']),
    ('arcadian_halo', 'Halo (fighter)', A, 'air', 'halo', 'settled',
     'Arcadian fighter with its blade ring spinning. It dives on a Falcon, lightning thrusters crackling, '
     'gold lightning bursts, then rolls away as the Falcon spirals down.',
     ['halo x2', 'falcon']),
    ('arcadian_disc', 'Disc (heavy gunship)', A, 'air', 'disc', 'pending-arcadian-readability',
     'Saucer gunship squad. Three Discs drift over a Terran mining site; their under-beams sweep the '
     'ground in 4 quick pulses and a Prospector and its Hauler go up in fire. Ominous, slow and total.',
     ['disc x2-3', 'prospector', 'hauler', 'deposit_ore']),
    ('arcadian_dragonfly', 'Dragonfly (interceptor)', A, 'air', 'dragonfly', 'settled',
     'Anti-air only. A swarm of Dragonflies, wings a blur, surges up at a Terran Condor bomber, curls '
     'round it and strikes with scorpion-tail lightning stings until it breaks apart. They never shoot '
     'the ground.',
     ['dragonfly x4-6', 'condor', 'falcon escort (optional)']),
    # ------------------------------------------------------------------ Terran structures
    ('terran_bastion', 'Bastion Gun (gun tower)', T, 'structure', 'bastion', 'settled',
     'Pilot clip (written by the orchestrator). Packed Bastion rolls in, unfolds into the gun tower and '
     'holds against a Lumen rush, one heavy blast every ~1.1 s.',
     ['bastion', 'lumen x3']),
    ('terran_harpoon', 'Harpoon Battery (missile tower)', T, 'structure', 'harpoon', 'settled',
     'Packed Harpoon drives up, stops, digs in and unfolds the launcher. Halos come in low; the battery '
     'pauses, then ripples missiles that knock two out of the sky.',
     ['harpoon', 'halo x2-3']),
    ('terran_radar', 'Radar Tower', T, 'structure', 'terran_radar', 'settled',
     'Packed radar drives to a hilltop, unfolds the mast tall, the dish starts turning and a radar '
     'sweep washes out over the map, lighting up distant contacts.',
     ['terran_radar', 'distant arcadian units']),
    ('terran_metal_station', 'Metal Station', T, 'structure', 'terran_metal_station', 'settled',
     'Packed station rolls onto a metal deposit, unfolds: smelter, hopper and stack rise, fan spins, '
     'sparks and glow as the first metal pours. Research is powered by metal.',
     ['terran_metal_station', 'deposit_metal']),
    ('terran_airfield', 'Airfield', T, 'structure', 'terran_airfield', 'settled',
     'Packed airfield unfolds hangar, tower and fuel tanks; the dish turns and a Falcon rolls out and '
     'takes off over camera.',
     ['terran_airfield', 'falcon']),
    ('terran_lab', 'Research Lab', T, 'structure', 'terran_lab', 'settled',
     'The lab at night-ish dusk: lights blink on, a Hauler of metal arrives, energy hums, the building '
     'pulses blue as a research breakthrough completes (a beam of light up from the roof).',
     ['terran_lab', 'hauler']),
    ('terran_landing_pad', 'Landing Pad', T, 'structure', 'terran_landing_pad', 'settled',
     'The pad itself drops from the sky on thrusters, lands with a dust ring, unfolds its deck; then a '
     'dropship delivery lands units one at a time (a Lancer drives off, clears, the next lands). Ordered, '
     'busy, the heart of the base.',
     ['terran_landing_pad', 'lancer', 'outrider', 'hauler']),
    # ------------------------------------------------------------------ Arcadian structures
    ('arcadian_sentinel', 'Sentinel (gun tower)', A, 'structure', 'sentinel', 'settled',
     'Packed Sentinel glides in on lightning lifters, settles, and grows its thorny tower open; '
     'Lancers advance and gold lightning arcs from the crown, chaining between them.',
     ['sentinel', 'lancer x2-3']),
    ('arcadian_corona', 'Corona (missile tower)', A, 'structure', 'corona', 'settled',
     'Packed Corona arrives and blooms open; Falcons scream overhead and the Corona looses a spray of '
     'gold seeker orbs that curl up after them.',
     ['corona', 'falcon x2']),
    ('arcadian_oracle', 'Oracle (radar spire)', A, 'structure', 'oracle', 'settled',
     'Packed Oracle settles and the spire rises, horns unfolding, its eye turning; parts float '
     'suspended. A pulse of pale light sweeps the land.',
     ['oracle']),
    ('arcadian_metal_siphon', 'Metal Siphon', A, 'structure', 'metal_siphon', 'settled',
     'Packed Siphon settles on a metal deposit, basin and horns unfold; the metal is drawn up as '
     'liquid light spiralling into the basin.',
     ['metal_siphon', 'deposit_metal']),
    ('arcadian_aerie', 'Aerie (air base)', A, 'structure', 'aerie', 'settled',
     'Packed Aerie unfolds its ribs and perches; Dragonflies and a Halo lift off from the perches '
     'into the sky.',
     ['aerie', 'dragonfly x3', 'halo']),
    ('arcadian_star_vault', 'Star Vault (research)', A, 'structure', 'star_vault', 'settled',
     'The vault\'s crown turns; metal streams in as motes of light, the vault glows brighter and a '
     'crown of light flares as research completes.',
     ['star_vault']),
    ('arcadian_landing_ring', 'Landing Ring', A, 'structure', 'landing_ring', 'settled',
     'The ring descends and settles, crown and halo begin turning; a column of light delivers units one '
     'at a time (a Lumen glides out, clears, the next arrives).',
     ['landing_ring', 'lumen', 'darter', 'ferrier']),
    # ------------------------------------------------------------------ World
    ('world_shard', 'The Shard (end-game crystal)', 'Neutral', 'structure', 'shard', 'settled',
     'The Shard attacks BOTH sides. Terran and Arcadian units fight near it; it wakes, spires glow '
     'violet, and it lashes out at both armies. Awe and menace. (Its old beam attack looked bad: '
     'make the attack look good.)',
     ['shard', 'shard_spire x2', 'lancer x2', 'lumen x2']),
    ('world_ore', 'Ore field', 'Neutral', 'resource', 'deposit_ore', 'settled',
     'A slow, beautiful orbit round an ore deposit at dawn; a Prospector and a Sifter arrive from '
     'opposite sides and both start mining. Ore buys everything.',
     ['deposit_ore', 'prospector', 'sifter']),
    ('world_metal', 'Metal deposit', 'Neutral', 'resource', 'deposit_metal', 'settled',
     'A metal deposit glinting; a Terran Metal Station and an Arcadian Siphon unfold on two nearby '
     'veins. Metal is only for research.',
     ['deposit_metal', 'terran_metal_station', 'metal_siphon']),
    # ------------------------------------------------------------------ Fleet (space)
    ('fleet_terran_dreadnought', 'Terran Dreadnought', T, 'ship', 'terran_dreadnought', 'film-placeholder',
     'Huge flagship emerging from shadow into sunlight, broadside guns rolling to fire, a translucent '
     'blue triangle shield shrugging off Arcadian lightning.',
     ['terran_dreadnought', 'arcadian_corvette x2']),
    ('fleet_terran_broadside', 'Terran Broadside battleship', T, 'ship', 'terran_broadside', 'film-placeholder',
     'Battleship turns its flank, all turrets swing in sequence and fire a ripple broadside into an '
     'Arcadian Shell mothership.',
     ['terran_broadside', 'arcadian_shell']),
    ('fleet_terran_frigate', 'Terran Frigate', T, 'ship', 'terran_frigate', 'film-placeholder',
     'Frigate escort screening the fleet: its point defence shreds a wave of Stingray fighters.',
     ['terran_frigate', 'arcadian_stingray x4', 'terran_dreadnought (background)']),
    ('fleet_terran_missile_ship', 'Terran Missile ship', T, 'ship', 'terran_missile_ship', 'film-placeholder',
     'Missile ship launch: a pause, then dozens of missiles ripple out, curl and converge on an Arcadian '
     'corvette.',
     ['terran_missile_ship', 'arcadian_corvette']),
    ('fleet_terran_corvette', 'Terran Corvette', T, 'ship', 'terran_corvette', 'film-placeholder',
     'Small and fast: the corvette slaloms between capital ships, strafing an Arcadian corvette.',
     ['terran_corvette x2', 'arcadian_corvette']),
    ('fleet_terran_twinx', 'Terran Twin-X fighter', T, 'ship', 'terran_twinx', 'film-placeholder',
     'Twin-X fighter squadron peels off from the fleet and dives on a Stingray in a dogfight.',
     ['terran_twinx x3', 'arcadian_stingray x2']),
    ('fleet_arcadian_crescent', 'Arcadian Crescent mothership', A, 'ship', 'arcadian_crescent', 'film-placeholder',
     'Vast crescent turns slowly in front of the planet, lightning thrusters crackling along its back, '
     'and unleashes a lightning storm on a Terran frigate.',
     ['arcadian_crescent', 'terran_frigate']),
    ('fleet_arcadian_shell', 'Arcadian Shell mothership', A, 'ship', 'arcadian_shell', 'film-placeholder',
     'Nautilus-like Shell opens and launches a swarm of Stingrays and Orbs.',
     ['arcadian_shell', 'arcadian_stingray x4', 'arcadian_orb']),
    ('fleet_arcadian_lens', 'Arcadian Lens mothership', A, 'ship', 'arcadian_lens', 'film-placeholder',
     'The Lens focuses sunlight into a single gold beam that slices a Terran Broadside\'s shield, which '
     'stretches and holds (shields never shatter).',
     ['arcadian_lens', 'terran_broadside']),
    ('fleet_arcadian_corvette', 'Arcadian Corvette', A, 'ship', 'arcadian_corvette', 'film-placeholder',
     'Arcadian corvettes run a lightning gauntlet past a Terran corvette pair.',
     ['arcadian_corvette x2', 'terran_corvette']),
    ('fleet_arcadian_stingray', 'Arcadian Stingray fighter', A, 'ship', 'arcadian_stingray', 'film-placeholder',
     'Stingray fighters ripple through a Twin-X formation, lightning thrusters flaring, picking two off.',
     ['arcadian_stingray x3', 'terran_twinx x3']),
    ('fleet_arcadian_orb', 'Arcadian Orb (anti-fighter)', A, 'ship', 'arcadian_orb', 'film-placeholder',
     'The Orb, 8 independent tentacle legs (thrusters only on the tentacles), lunges at a Twin-X fighter, '
     'legs whipping, and catches it.',
     ['arcadian_orb', 'terran_twinx x2']),
]

SAMPLES = ['terran_bastion', 'terran_outrider', 'arcadian_dragonfly', 'arcadian_disc', 'terran_landing_pad']


def main():
    os.makedirs(os.path.join(HERE, 'briefs'), exist_ok=True)
    st_path = os.path.join(HERE, 'status.json')
    status = json.load(open(st_path)) if os.path.exists(st_path) else {}
    lines = ['# Promo clip checklist', '', f'{len(CLIPS)} clips. Generated by entities.py; status from status.json.', '',
             '| # | Clip | Faction | Model state | Status |', '|---|---|---|---|---|']
    for i, (cid, title, fac, kind, hero, mstate, brief, cast) in enumerate(CLIPS, 1):
        s = status.setdefault(cid, {'state': 'todo', 'note': ''})
        lines.append(f'| {i} | {title} (`{cid}`) | {fac} | {mstate} | {s["state"]} |')
        with open(os.path.join(HERE, 'briefs', cid + '.md'), 'w') as fh:
            fh.write(f'# {title}\n\nClip id: `{cid}` · Faction: {fac} · Kind: {kind} · Hero model: `{hero}` '
                     f'· Model state: {mstate}\n\n## Brief\n\n{brief}\n\n## Cast available (models.json names)\n\n'
                     + '\n'.join(f'- {c}' for c in cast) + '\n\n' + RULES)
    json.dump(status, open(st_path, 'w'), indent=1)
    open(os.path.join(HERE, 'CHECKLIST.md'), 'w').write('\n'.join(lines) + '\n')
    print(len(CLIPS), 'clips')


if __name__ == '__main__':
    main()
