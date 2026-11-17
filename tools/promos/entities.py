"""Master list of promo clips: one entry per entity, with the orchestrator's brief.

    python tools/promos/entities.py            # writes briefs/<id>.md and CHECKLIST.md

Each brief deliberately gives more than a 6 second clip can hold. The scene author picks what serves the shot.
`models` are promo_kit registry names (file stems), so a remodel only needs a re-render.
`settled` says whether the hero model is final enough to render now:
  yes      in the game and not under revision
  terran   Terran ground unit: being restored to the pass6 look with the new firing animations
  arcadian Arcadian unit: readability pass awaiting David's OK
  film     fleet ship from the opening film (David will redo engines and lighting later)
"""
import json
import os

RULES = """Standing rules (David):
- Shields never shatter. Anything pushing through makes the shield dent, stretch and wrap around it, then spring back.
- Arcadians use lightning for thrusters and lift, never flame. Arcadian weapons and lightning are gold.
- No vehicle has a pilot: no cockpits, canopies, hatches or viewports anywhere.
- Terran cannons telescope back 80% of their length when they fire, then run out again.
- Every tank shot has recoil, a muzzle flash and a hull kick. Mortars and artillery kick the hull hard. Rockets pause, then ripple-fire back and forth across the launcher.
- Every unit fires on its own rhythm (given below). Recoil and flash must finish inside the shot spacing.
- Terran look: dark angular armor, cyan/neon blue energy, orange accent lights. Arcadian look: hovering etched silver-bronze hulls, crescent fins, gold cores. No purple.
- Orb arms each move independently. The Dragonfly is anti-air only and never attacks ground targets.
- Not a straight-line demo: a real little combat or work story, with a camera that circles the action. About 6 seconds, 24 fps.
- Build up for a second or two, then make the key moment big and close in frame. The hero unit must be the clear star."""

E = []


def add(id, name, group, models, settled, role, weapon, cast, story, extra='', setting=''):
    E.append(dict(id=id, name=name, group=group, models=models, settled=settled, role=role, weapon=weapon,
                  cast=cast, story=story, extra=extra, setting=setting))


# ---------------------------------------------------------------- Terran ground
G = 'Terran ground units'
add('lancer', 'Lancer', G, ['lancer'], 'terran',
    'Terran light tank, the backbone of every early push. 220 hp, top speed 8, turret turns 120 deg/s, fires on the move.',
    'Twin lances fire in turn: one shell every 1.8 s, alternating left and right barrel. Range 12, small splash. Each barrel telescopes 80% on its own shot; light hull kick.',
    'Allies: 2-3 more Lancers in a loose wedge. Enemies: 3 Arcadian Lumens (stinger) or a pair of Darters. Optional: an Arcadian Sentinel tower (kesh_thornmound) they are pushing toward.',
    'A wedge of three or four Lancers crests a low rise at speed, turrets already tracking, and lights up a small group of Arcadian light tanks: alternating barrels, shells crossing the gap, one Lumen brewing up while the hero Lancer slews its turret to the next target without slowing down.',
    'This is the "three or four tanks light up a group of light tanks" clip David described. Show the left-right barrel alternation clearly on the hero. Fire on the move.',
    'Dry open ground, late afternoon sun, dust off the treads.')
add('outrider', 'Outrider', G, ['outrider'], 'terran',
    'Terran scout: six wheels, fastest ground unit (top 11, accel 6, turns 150 deg/s), 80 hp, long sight. Sees first, dies fast.',
    'Autocannon: bursts of 3 rounds 0.15 s apart, then 1.3 s pause. Range 8. Weak: 6 damage a round. Tracers.',
    'Enemies: an Arcadian base corner: a Landing Ring (kesh_landing_nest), a Sentinel (kesh_thornmound) and a Sifter (gorger) working an ore deposit, plus one Lumen that turns to chase. No allies: the scout is alone.',
    'The scout rushes in flat out, slides round a rock, sees the enemy base, sprays a few three-round pot shots at the miner as it passes, then jinks away as the Sentinel wakes up and its shots land in the dust behind it. In fast, look, out fast.',
    'David asked for exactly this: rush in, see what is going on, pot shots along the way, rush out. Speed and wheel spin are the point; spinning radar dish. The shots should barely scratch the target.',
    'Rocky ground with boulders to weave through, bright midday.')
add('skimmer', 'Skimmer', G, ['skimmer'], 'terran',
    'Terran hover tank on four lift fans: fast flanker (top 10, accel 6), 180 hp, lighter gun than the Lancer. Crosses ground others must go round.',
    'Cannon in two-round bursts 0.25 s apart, then 2.15 s. Range 11. Barrel collapses 80% each shot, hull dips on its fans.',
    'Allies: one more Skimmer as wingman. Enemies: an Arcadian Sunfall artillery piece (mortar_beast) shelling something off screen, guarded by a slow Aegis (carapace).',
    'Two Skimmers sweep in a wide curving flank, sliding sideways with fans howling and dust rings under them, round the slow Aegis whose turret cannot keep up, and double-tap the artillery from behind.',
    'Show the drift: hull facing differs from travel direction, strafing while the turret stays on target. Fans spin always.',
    'Flat salt pan or shallow water sheen, low sun.')
add('bulwark', 'Bulwark', G, ['bulwark'], 'terran',
    'Terran heavy tank: 520 hp, slow (top 5, turns 60 deg/s), the wall of an assault. Soaks fire that would kill three Lancers.',
    'One devastating heavy shell every 3.5 s. Range 13, splash 1. Barrel telescopes 80%, big hull rock, ground dust blown out, long recovery.',
    'Enemies: 3 Arcadian Lumens whose shots spark off the Bulwark armor, a Sentinel tower. Allies: a Mender behind it, optional.',
    'The Bulwark grinds forward under fire, shots sparking off its glacis without slowing it. The turret comes round with slow menace, a beat of stillness, then one shot that deletes a Lumen outright. Dust rolls off the hull as the barrel runs back out and it keeps coming.',
    'Only one, at most two shots in 6 s: make the single shot the event. Low camera, heavy feel, slight camera shake.',
    'Scorched battlefield, overcast or dusk, wreck smoke in the distance.')
add('javelin', 'Javelin', G, ['javelin'], 'terran',
    'Terran missile tank: long range (18), fragile (150 hp), the only Terran ground unit that also hits aircraft.',
    'Four missiles rippling 0.2 s apart after a short pause, then 5 s reload. Missiles home; smoke trails; launcher rocks back and forth with each launch.',
    'Enemies: 2-3 Arcadian Discs (saucers) inbound, or Halo fighters. Allies: a Lancer or Prospector the saucers were heading for.',
    'Saucers come in over the ridge. The Javelin halts, launcher elevates and swings, a held breath, then four missiles ripple out left-right-left-right and corkscrew up on smoke trails. Two saucers are hit and fall burning, the last breaks off.',
    'Pause then ripple is the rule. Missiles should curve to their targets, not fly straight. Radar dish spins.',
    'Open plain, clear sky so the trails read, morning light.')
add('longbow', 'Longbow', G, ['longbow'], 'terran',
    'Terran artillery: range 34, far beyond sight, slow and fragile (140 hp). Needs a spotter. Inaccurate, big splash 3.',
    'Three shells 0.4 s apart, then 3 s reload. Each shot collapses the long cannon 80% and slams the whole hull back and down on its suspension.',
    'Allies: a Watchman radar vehicle beside it, or an Outrider spotting far away. Enemies: a distant Arcadian tower cluster (Sentinel, Corona) and Lumens that never get to shoot back.',
    'The Longbow sits well back, barrel elevating. Three thunderclaps in one second, the hull slamming back each time. The camera swings round and follows the shells over the hill to see them land on an Arcadian position in three walking blasts.',
    'Huge hull kick is the point. Shells fly a high arc. Try a camera that starts on the gun and ends looking down range at the impacts.',
    'Hill line between gun and target, golden hour.')
add('prospector', 'Prospector', G, ['prospector', 'deposit_ore'], 'terran',
    'Terran ore miner: unarmed worker, 120 hp, top speed 6. Drives to an ore site, lowers its drum drill and grinds ore that Haulers carry away.',
    'No weapon. Mining drum spins (6 rad/s) while working; visible ore fills its hopper.',
    'Props: a rich ore deposit (deposit_ore, pink crystal style). Allies: a Hauler waiting to load, a Lancer on guard in the background. Optional distant threat: an enemy scout watching from a ridge.',
    'The Prospector trundles up to a glittering ore site, settles, lowers its drill drum which spins up and bites: sparks, crystal chips and dust fly, ore glow builds in the hopper. A Hauler backs in beside it to take the first load.',
    'David: "miners lower their drills and start working". Make the work satisfying and readable: status is visible (ore in the hopper).',
    'Crystal field, low warm light glinting off the ore.')
add('hauler', 'Hauler', G, ['hauler', 'terran_landing_pad'], 'terran',
    'Terran tug: unarmed hauler with a crane, 100 hp, top speed 7. Carries ore crates from miners to the Landing Pad delivery spot; cargo goes onto the pad and is lifted off.',
    'No weapon. Crane swings while working.',
    'Allies: a Prospector at an ore site (deposit_ore), the Terran Landing Pad with its cargo lift. Optional: a second Hauler passing the other way.',
    'A loaded Hauler runs the ore road from the miner to the pad, passing its empty twin going back. It swings into the delivery spot, the crane lifts the glowing crate over onto the pad lift, the crate rises away and the Hauler is already turning for the next run.',
    'It is the economy heartbeat: show the loop, cargo clearly visible on its back then gone.',
    'Base interior, mid-morning, tread marks on the ground.')
add('mender', 'Mender', G, ['mender'], 'terran',
    'Terran repair vehicle: unarmed, 120 hp, top 7. Repairs damaged units and structures with an arm and welding sparks.',
    'No weapon. Repair arm swings (0.6 rad at 0.5 Hz) while working, spark flicker at the tip.',
    'Allies: a battered, smoking Bulwark holding a line under fire. Enemies: Lumens at range keeping the pressure on.',
    'A Bulwark is smoking and sparking under fire. The Mender races up behind it, tucks in under the armor shadow, arm out, weld sparks showering: the smoke thins, glow lines come back on, and the Bulwark fires again.',
    'Visible before/after on the patient (smoke stops, lights return).',
    'Front line at dusk so the weld sparks light the hulls.')
add('watchman', 'Watchman', G, ['watchman'], 'terran',
    'Terran mobile radar: unarmed, 100 hp, top 7. Long sensor range, reveals enemies through fog for the guns behind it.',
    'No weapon. Radar head spins continuously (1.2 rad/s).',
    'Allies: a Longbow or Javelin behind it that fires on what it finds. Enemies: Arcadian Gliders creeping up in haze, unseen until swept.',
    'The Watchman rolls to a hilltop and stops, dish turning. A visible sweep ring of blue light pulses out across the dark ground and paints three hidden Gliders in outline. A beat later friendly shells arrive on them from off screen.',
    'Find a tasteful way to show "it sees": a pulse ring, outlines, a flicker on the revealed hulls.',
    'Night or thick dusk haze so the reveal reads.')

# ---------------------------------------------------------------- Terran air
G = 'Terran aircraft'
add('falcon', 'Falcon', G, ['falcon'], 'yes',
    'Terran fighter: fastest thing in the game (top 18, turns 200 deg/s), 90 hp. Hits air and ground. Flies from the Airfield, limited ammo per sortie.',
    'Twin lasers: 2 bolts 0.15 s apart, then 1.7 s. Range 14. Neon blue bolts.',
    'Wingman: one more Falcon. Enemies: 2 Arcadian Halo fighters (lightning weapons), or a Disc saucer they are protecting.',
    'A pair of Falcons in a turning fight with two Halos: hard banking break, the hero rolls in behind a Halo, two blue bolts, the Halo comes apart in gold sparks, and the Falcon pulls up through the debris.',
    'Bank into turns, engine glow, no cockpit. Camera can chase then swing round the nose.',
    'High over the battlefield, clouds below, strong sun.')
add('condor', 'Condor', G, ['condor'], 'yes',
    'Terran bomber: slow for an aircraft (top 12), 130 hp. Ground and structures only; defenceless against fighters.',
    'Stick of 3 bombs 0.25 s apart, then 4 s. Splash 3 each: the biggest area damage Terrans have.',
    'Enemies on the ground: an Arcadian Corona missile tower (kesh_spore_tower) firing up at it, a Sentinel, a Metal Siphon as the target. Optional: Dragonflies closing from behind (they hunt bombers). Escort: one Falcon.',
    'The Condor runs in low and level through gold tracer from the towers, bay opens, three bombs fall away in a neat stick and walk across an Arcadian Metal Siphon in three overlapping blasts as it banks away.',
    'Bombs fall with forward momentum. Show the weight of the aircraft.',
    'Over an Arcadian base at sunset.')

# ---------------------------------------------------------------- Arcadian ground
G = 'Arcadian ground units'
add('stinger', 'Lumen', G, ['stinger'], 'arcadian',
    'Arcadian light tank (model file: stinger). Hovering teardrop hull with one lance and a ring of light round the turret. 220 hp, top 8, fires on the move.',
    'Gold lance bolt every 1.8 s. Range 12. Lance recoils; lightning lifters flicker under the hull.',
    'Allies: 2-3 more Lumens gliding in line abreast. Enemies: a Terran Lancer pair, or a Terran Bastion Gun (terran_turret).',
    'Three Lumens glide silently out of morning mist in a line, lightning crawling beneath them, and open fire together on a Terran outpost gun: gold bolts converge, the hero drifts sideways while firing and the gun goes up.',
    'Hover feel: no ground contact, gentle bob, lean into moves. Lightning lift under the hull at all times.',
    'Misty dawn, wet ground reflecting gold.')
add('darter', 'Darter', G, ['darter'], 'arcadian',
    'Arcadian scout: needle hull with a two-pronged fork past the nose and a line of light down its spine. Top 11, 80 hp. No purple anywhere.',
    'Three-pulse gold burst 0.15 s apart, then 1.3 s. Range 8. Weak.',
    'Enemies: a Terran convoy: two Haulers and a Prospector with a single Lancer escort. Alone or with one wingman.',
    'A Darter streaks along a dry riverbed, pops over the bank beside a Terran ore convoy, rakes a Hauler with a three-pulse burst as it crosses their line, and is gone down the far side before the escort turret finishes turning.',
    'Different from the Outrider clip: this is a hit-and-run on a convoy seen from the convoy side. It skims very low and very fast, lightning thrusters streaming.',
    'Dry riverbed, noon, heat haze.')
add('glider', 'Glider', G, ['glider'], 'arcadian',
    'Arcadian fast hover tank: wide manta wings with a light on each wingtip. Top 10, 180 hp. Flanker.',
    'Two gold bolts 0.25 s apart, then 2.15 s. Range 11.',
    'Wing of 3 Gliders. Enemies: a Terran Longbow battery (2 Longbows) and a Watchman behind the lines.',
    'Three Gliders bank like rays over a ridge in formation, wings tilting, sweep down on a Terran artillery park from the side and tear through it in one pass, double-tapping as they go.',
    'They should feel like manta rays: banked, swooping, wingtip lights drawing lines.',
    'Rolling dunes, blue hour.')
add('carapace', 'Aegis', G, ['carapace'], 'arcadian',
    'Arcadian heavy tank (model file: carapace): thick horns, four glowing cores in a square, short thick gun. 520 hp, top 5.',
    'One heavy gold blast every 3.5 s. Range 13, splash 1. The cores charge in sequence before it fires.',
    'Enemies: Terran Lancers (3) firing at it, a Bastion Gun. Allies: Lumens behind it using it as cover.',
    'Terran shells burst against the Aegis and it does not care. The four cores light one-two-three-four, the air hums, and a single heavy bolt punches straight through a Lancer. Lumens slide out from behind it to finish the rest.',
    'Use the four-core charge-up as the build-up beat. Massive, serene, unstoppable.',
    'Storm light, dark sky, gold glow dominant.')
add('spitter', 'Flare', G, ['spitter'], 'arcadian',
    'Arcadian missile tank (model file: spitter): an arch of six fat pods with glowing noses. Range 18, 150 hp, hits air too.',
    'Four gold seekers rippling 0.2 s apart after a pause, then 5 s. Seekers arc and home, leaving thin lightning trails rather than smoke.',
    'Enemies: 2 Terran Falcons strafing, or a Condor bomber on its run. Allies: an Arcadian Metal Siphon it is defending.',
    'A Condor lines up on an Arcadian siphon. The Flare rises on its lifters, pod noses brighten one after another, pause, then four seekers ripple up in a fan, curl in and swat the bomber out of the sky before it can drop.',
    'Pause then ripple. Pods visibly empty and dim after launch.',
    'Dusk, seekers bright against a dark blue sky.')
add('mortar_beast', 'Sunfall', G, ['mortar_beast'], 'arcadian',
    'Arcadian artillery (model file: mortar_beast): carries a giant glowing orb. Range 34, 140 hp, slow.',
    'Three sun-like orbs lobbed 0.4 s apart, then 3 s. High arc, splash 3. The hull is slammed down toward the ground on its lifters by each launch.',
    'Enemies: a Terran base far off: Landing Pad, Research Lab, Bastion Gun. Allies: a Seer spotting on a ridge.',
    'The great orb swells white-gold, and the Sunfall heaves three small suns into the sky, hull bucking down each time, lifter lightning flaring. They climb, hang, and fall on a distant Terran base as three blooms of light.',
    'Mortar = huge hull kick even though it hovers: push it down and back, lightning lifters surge to catch it.',
    'Night, so the orbs light the landscape as they fly.')
add('gorger', 'Sifter', G, ['gorger', 'deposit_ore'], 'arcadian',
    'Arcadian ore miner (model file: gorger): bronze hull with big silver stag-beetle jaws round a glowing grinder. Unarmed, 120 hp, ember-orange role glow.',
    'No weapon. Grinder spins (8 rad/s) while mining.',
    'Props: an opal-style ore deposit. Allies: a Ferrier waiting, a Sentinel tower watching over the site.',
    'The Sifter drifts over an ore outcrop, lowers itself, jaws spreading then closing round a crystal; the grinder spins up, ore dissolves into streams of glowing motes drawn into the hull, and its ember glow brightens as it fills.',
    'Alien, elegant mining: it feeds rather than drills. Clear contrast with the Prospector clip.',
    'Opal ore field, twilight.')
add('ferrier', 'Ferrier', G, ['ferrier', 'kesh_landing_nest'], 'arcadian',
    'Arcadian tug: long bronze barge with two bowed side rails and tall claws. Unarmed, 100 hp. Carries ore from Sifters to the Landing Ring.',
    'No weapon.',
    'Allies: a Sifter at a deposit, the Landing Ring (kesh_landing_nest) with its floating crown, a Lumen escort.',
    'A Ferrier glides in with a glowing cargo pod cradled in its claws, slides under the Landing Ring crown, the pod is drawn up into the ring on a thread of lightning and vanishes skyward, and the barge peels away empty.',
    'Cargo visible, then visibly gone. Floating, disconnected structure parts are part of the Arcadian look.',
    'Arcadian base, soft morning light.')
add('weaver', 'Weaver', G, ['weaver'], 'arcadian',
    'Arcadian repair unit: round hull with three long arms with bright tips that turn. Unarmed, 120 hp, pale white-gold glow.',
    'No weapon. Arms rotate (1 rad/s, 4 rad/s while working); repair is threads of light.',
    'Allies: a damaged Aegis with dark cores, or a scorched Sentinel tower. Enemies: Terran shells still landing nearby.',
    'A wounded Aegis sits dark and listing. The Weaver slides alongside, arms spin up, and threads of white-gold light stitch across the cracked hull; the cores relight one by one and the Aegis rises back to full hover.',
    'Repair as weaving light, distinct from the Mender welding clip.',
    'After-battle haze, late day.')
add('seer', 'Seer', G, ['seer'], 'arcadian',
    'Arcadian sensor unit: slim hull, tall mast, a big crescent dish round a glowing eye. Unarmed, 100 hp. Reveals what is hidden.',
    'No weapon. Dish turns (0.8 rad/s).',
    'Allies: a Sunfall or Flares behind it. Enemies: Terran Outriders sneaking past in the dark, a Javelin lying in wait.',
    'The Seer rises above a dune crest, eye opening wide. A fan of pale light sweeps the valley and Terran scouts that thought they were hidden are suddenly lit up gold. Seekers arc in from behind the Seer.',
    'A different "it sees" treatment from the Watchman: a sweeping eye-beam rather than a pulse ring.',
    'Moonlit desert.')

# ---------------------------------------------------------------- Arcadian air
G = 'Arcadian aircraft'
add('halo', 'Halo', G, ['halo'], 'yes',
    'Arcadian fighter: ring-shaped craft. Top 18, 90 hp, hits air and ground.',
    'Lightning: two gold forks 0.15 s apart, then 1.7 s. Range 14.',
    'Wing of 2-3 Halos. Enemies: Terran Falcons, or a ground column of Outriders they strafe.',
    'Three Halos roll in out of the sun, rings tilting edge-on as they turn, and the hero forks lightning into a jinking Falcon, which trails blue fire and spins away. The Halos flip and reverse direction in a way no winged craft could.',
    'Sell alien flight: edge-on turns, sudden reversals, lightning thrusters.',
    'Bright high sky above cloud.')
add('disc', 'Disc', G, ['disc'], 'arcadian',
    'Arcadian saucer bomber: 260 hp, top 14. Spinning blade ring, bright rim lights. Ground and structures only.',
    'Ground beam: 4 pulses 0.12 s apart straight down, then 3.5 s. Range 4, so it must fly right over the target. Splash 3.5.',
    'Squad of 3 Discs. Target: a Terran Prospector at an ore site with a Hauler beside it. Optional: a Javelin too far away to help in time.',
    'A squad of saucers drifts over a Terran mining site, blades spinning, rim lights pulsing. They stop dead above the miner, and four hammering beam pulses each turn the Prospector into a crater. The Hauler flees. The saucers move on.',
    'David named this one: a saucer squad destroys a miner. Hovering directly over the target is what makes it menacing.',
    'Ore field at dusk, beams lighting the ground.')
add('dragonfly', 'Dragonfly', G, ['dragonfly'], 'yes',
    'Arcadian anti-air fighter, newly official. ANTI-AIR ONLY: it cannot attack ground targets, ever. Four long barbed gold-edged wings, a three-joint tail with a sting, lightning thrusters.',
    'Scorpion tail strike: the tail whips up and over the back and the sting discharges forward. Fast, close-range, in swarms. Wings beat at 14 Hz.',
    'Swarm of 4-6 Dragonflies. Enemy: one Terran Condor bomber, with a Falcon escort that cannot cover every side.',
    'A Condor lumbers toward its target. Dragonflies rise around it like a disturbed nest, darting, hovering, sliding sideways, and strike with their tails one after another from every angle until the bomber breaks up. Nothing on the ground is touched.',
    'David named this one: dragonflies swarm a bomber. Insect flight: hover, dart, hover. Each one moves on its own.',
    'Low over marshy ground, hazy gold evening.')

# ---------------------------------------------------------------- Terran structures
G = 'Terran structures and towers'
add('terran_landing_pad', 'Landing Pad', G, ['terran_landing_pad', 'lancer', 'hauler'], 'yes',
    'The Terran base: 6x6 cells, 1200 hp. Dropped from orbit. Every unit ordered is delivered here one at a time: a unit lands, drives off, the pad clears, then the next. Haulers bring cargo to its delivery spot; cargo goes onto the pad and is lifted away.',
    'No weapon. Scanner spins (1.6 rad/s). Exit is +X, cargo lift on -Y.',
    'Units delivered: a Lancer, then an Outrider or Bulwark. A drop craft or descent thrusters. Optional: a Hauler at the delivery spot.',
    'The pad comes down out of the sky on braking thrusters, slams into the dust, legs and deck panels unfold and lock, lights run round the deck edge. A Lancer is lowered onto the deck, rolls off down the ramp and clears, and the next delivery is already descending.',
    'David: "the landing pad landing on land, unfolding, and vehicles coming off of it". If the model has no unfold tags, animate its top-level parts in (scale/slide/rotate from a folded pose). Ordered, one at a time delivery.',
    'Empty plain at dawn, big dust ring on touchdown.')
add('terran_metal_station', 'Metal Station', G, ['metal_station_packed', 'terran_metal_station', 'deposit_metal'], 'yes',
    'Terran metal extractor: drives in packed as a slow vehicle (top 2.5), deploys on a metal deposit, then produces metal, which only pays for research. Parts: smelter, hopper, tanks, stack, spinning fan.',
    'No weapon. Fan spins 9 rad/s when running.',
    'Props: a metal deposit (deposit_metal). Allies: a Bastion Gun guarding, a Research Lab in the background that the metal feeds.',
    'The packed station crawls onto a metal deposit, stops, and unfolds: stack telescopes up, tanks swing out, hopper opens, the drill goes down, fan spins up, the stack starts to breathe heat and the first glowing ingot rolls out.',
    'Use the packed -> deployed unfold contract. "Starts mining" is the payoff.',
    'Bare metallic rock, cool morning.')
add('terran_turret', 'Bastion Gun', G, ['bastion_packed', 'terran_turret'], 'yes',
    'Terran gun tower: drives in packed (Bastion, top 2.5), unfolds in 1.5 s into a 2x2 turret.',
    'Two shots 0.3 s apart, then 2.0 s. Range 14. Ground only.',
    'Enemies: a pair of Darters, then Lumens. Allies: the Landing Pad behind it.',
    'Packed Bastion drives to a choke point, unfolds into the gun, and opens up on approaching Arcadian scouts.',
    'This is the pilot scene already written by the toolkit builder (scenes/terran_turret.py). Improve it rather than start over.',
    'Canyon mouth, afternoon.')
add('terran_missile_battery', 'Harpoon Battery', G, ['spire_packed', 'terran_missile_battery'], 'yes',
    'Terran missile tower: drives in packed (spire_packed), unfolds. Range 20, hits ground and air: the base air defence.',
    'Three missiles 0.25 s apart, then 2.7 s. Pause then ripple.',
    'Enemies: Arcadian Discs coming for the base, Halos. Allies: Research Lab or Airfield it protects.',
    'Air raid: saucers closing on the base. The packed battery brakes hard, unfolds with the launcher racks rising and splitting, and fires three missiles in a ripple before the dust has settled. The lead saucer staggers and falls.',
    'Race against time feel: the unfold finishes just as the enemy arrives.',
    'Base edge under a red evening sky.')
add('terran_radar', 'Radar Tower', G, ['radar_tower_packed', 'terran_radar'], 'yes',
    'Terran radar tower: packed vehicle unfolds into a tall mast with a turning dish. Big sensor range for the whole base.',
    'No weapon. Dish spins 1 rad/s.',
    'Allies: Harpoon Battery and Bastion Gun nearby that react. Enemies: Arcadian Halos approaching from far away.',
    'The packed radar parks, outriggers drop, the mast climbs section by section, the dish unfurls and starts to turn. On its second sweep it catches incoming fighters far out, and the base guns swing round to face them.',
    'Tall vertical reveal: the camera can rise with the mast.',
    'Hilltop at blue hour, dish lights blinking.')
add('terran_air_base', 'Airfield', G, ['air_base_packed', 'terran_air_base', 'falcon', 'condor'], 'yes',
    'Terran airfield: packed vehicle unfolds into hangar, tower, fuel and dish. Falcons and Condors launch from it, return to re-arm.',
    'No weapon. Dish spins.',
    'Allies: 2 Falcons scrambling, a Condor parked or landing.',
    'The airfield finishes unfolding, hangar doors part, and two Falcons lift out and scream away over the camera while a Condor settles in behind them to re-arm.',
    'Launch is the money shot. Engine glow and heat, dust blown across the apron.',
    'Sunrise, long shadows.')
add('terran_lab', 'Research Lab', G, ['terran_lab'], 'yes',
    'Terran research lab: spends metal to unlock upgrades (fire rate, armor) and higher tech units.',
    'No weapon.',
    'Allies: a Metal Station feeding it, a Lancer nearby that visibly receives the upgrade.',
    'The lab hums at night, energy building through its coils and conduits to a crescendo: a pulse of blue light races out along the ground, and a waiting Lancer flares as new armor plates and brighter glow lines switch on.',
    'It has no moving action of its own in the game, so make the research moment visible: build-up, pulse, upgrade landing on a unit.',
    'Night, lab lights and neon blue.')

# ---------------------------------------------------------------- Arcadian structures
G = 'Arcadian structures and towers'
add('kesh_landing_nest', 'Landing Ring', G, ['kesh_landing_nest', 'stinger'], 'yes',
    'The Arcadian base (model file: kesh_landing_nest). Floating crown and halo over a base ring; units are delivered through it one at a time.',
    'No weapon. Crown spins 0.7 rad/s, halo counter-rotates.',
    'Units delivered: a Lumen, then a Darter. Optional Ferrier bringing cargo.',
    'A point of gold light falls from the sky and blooms. The ring pieces descend separately and assemble in mid-air without touching, the crown starts to turn, lightning ties the parts together, and a Lumen is lowered through the ring on a column of light and glides away.',
    'Counterpart to the Terran pad but nothing mechanical: parts float, suspended and disconnected. Arcadian portals are dark, crisp, electric.',
    'Still desert night, the ring lighting the sand.')
add('kesh_metal_siphon', 'Metal Siphon', G, ['metal_station_packed', 'kesh_metal_siphon', 'deposit_metal'], 'yes',
    'Arcadian metal extractor: drifts in packed, deploys over a metal deposit and draws metal up as light.',
    'No weapon. Top part spins 0.5 rad/s.',
    'Props: metal deposit. Allies: a Sentinel on guard, a Star Vault in the background.',
    'The packed siphon floats over a metal vein and blossoms open: horns rise, the basin drops, the crown lifts free and spins, and a thread of molten metal is pulled up out of the ground into its core.',
    'The packed model here is the alien one (alien/metal_station_packed). Unfold contract applies.',
    'Dark metallic ground, pre-dawn.')
add('kesh_thornmound', 'Sentinel', G, ['thornmound_packed', 'kesh_thornmound'], 'yes',
    'Arcadian gun tower (model file: kesh_thornmound): drifts in packed and unfolds.',
    'Two gold bolts 0.3 s apart, then 2.0 s. Range 14. Ground only.',
    'Enemies: Terran Outriders probing, then a Lancer. Allies: Landing Ring behind it.',
    'A Terran scout pair think the pass is open. The packed Sentinel settles between the rocks ahead of them, unfolds like a flower with thorns locking outward, and its first double bolt flips the lead Outrider end over end.',
    'Told from the ambush side: the tower is the trap.',
    'Narrow rocky pass, hard noon shadows.')
add('kesh_spore_tower', 'Corona', G, ['spore_tower_packed', 'kesh_spore_tower'], 'yes',
    'Arcadian missile tower (model file: kesh_spore_tower): unfolds from its packed form. Range 20, hits air and ground.',
    'Three gold seekers 0.25 s apart, then 2.7 s. Pause then ripple.',
    'Enemies: Terran Falcons and a Condor on a raid. Allies: an Aerie it protects.',
    'Falcons dive on an Arcadian base. The Corona unfolds, its crown opening like a sunburst, and three seekers ripple out and chase a Falcon through a hard turn until they catch it.',
    'Follow one seeker for a moment if it helps.',
    'Sunset with long gold light.')
add('kesh_seer_spire', 'Oracle', G, ['radar_tower_packed', 'kesh_seer_spire'], 'yes',
    'Arcadian radar tower (model file: kesh_seer_spire): unfolds into a tall spire with a turning eye.',
    'No weapon. Top turns 0.6 rad/s.',
    'Allies: Coronas and Sentinels that respond. Enemies: Terran Skimmers flanking in the dark.',
    'The spire rises out of its packed shell in floating segments that stack themselves, the eye at the top opens and turns, and rings of pale light ripple outward revealing a Terran flanking force. The towers turn toward them.',
    'Alien packed model: alien/radar_tower_packed.',
    'Night with stars.')
add('kesh_hive_roost', 'Aerie', G, ['air_base_packed', 'kesh_hive_roost', 'halo', 'disc', 'dragonfly'], 'yes',
    'Arcadian air base (model file: kesh_hive_roost): perches round a central spire. Halos, Discs and Dragonflies launch from it.',
    'No weapon. Top turns slowly.',
    'Allies: Dragonflies lifting off the perches, a Disc rising from the centre, Halos circling.',
    'The Aerie opens its perches and aircraft pour out: Dragonflies unhook and drop into flight one after another, a Disc rises from the core, and Halos already aloft form up overhead.',
    'A swarm leaving a hive. Each craft on its own timing.',
    'Golden evening.')
add('kesh_gene_vault', 'Star Vault', G, ['kesh_gene_vault'], 'yes',
    'Arcadian research building (model file: kesh_gene_vault): spends metal to unlock upgrades. Crown spins 0.5 rad/s.',
    'No weapon.',
    'Allies: a Lumen or Aegis nearby receiving the upgrade, a Metal Siphon feeding it.',
    'The vault crown spins faster and faster, floating pieces aligning like an orrery until they click into one figure; a gold ring of light drops to the ground and rolls outward, and a waiting Aegis lights a fifth, brighter glow.',
    'Research made visible, in an astronomical, precise way. Distinct from the Terran lab pulse.',
    'Deep night, gold on black.')

# ---------------------------------------------------------------- Neutral
G = 'Neutral and world'
add('shard', 'The Shard and its Spires', G, ['shard_core', 'shard_spire'], 'yes',
    'The end-game crystal: hostile to BOTH sides. Core: range 26, 70 damage, splash 2.5, every 3 s. Spires: range 18, 30 damage, every 2 s. Hits ground, air and structures.',
    'Its old beam attack looked bad and is being reworked: design a better one here. Think refracted light gathering through the crystal facets, then a hard, thin, blinding discharge.',
    'Enemies: a mixed truce force: Terran Lancers and a Bulwark alongside Arcadian Lumens and an Aegis, Falcons and Halos overhead, all attacking it together.',
    'Terrans and Arcadians, side by side for once, advance on the Shard. Light gathers inside the crystal, spires answer in sequence, and it lashes out at both: a Bulwark and an Aegis die in the same second. The allied fire sparks off its facets.',
    'The only clip where both factions are on the same side. Scale: it should tower over everything.',
    'Storm sky, the crystal lighting everything from inside.')
add('deposit_ore', 'Ore Site', G, ['deposit_ore', 'prospector', 'gorger'], 'yes',
    'Ore deposit: the resource that buys everything normal. Crystal clusters in many pieces. Both factions want the same sites.',
    'None.',
    'A Terran Prospector and an Arcadian Sifter arriving at the same site from opposite sides, with one escort each (Lancer, Lumen).',
    'A slow, beautiful reveal of an untouched ore field glittering in low sun, then miners from both sides arrive at opposite ends at the same moment, and their escorts turn their guns on each other.',
    'The ore is the star: light, sparkle, scale. The fight is only promised.',
    'Golden hour, long shadows through the crystals.')
add('deposit_metal', 'Metal Deposit', G, ['deposit_metal', 'metal_station_packed'], 'yes',
    'Metal deposit: rarer, pays only for research. Metal Stations and Siphons are built on top.',
    'None.',
    'A packed Terran Metal Station approaching with a Bastion escort; a Darter watching from a ridge.',
    'The camera skims low across broken ground to a seam of raw metal gleaming like spilled mercury. A packed Metal Station crawls into frame toward it while an Arcadian scout watches from the ridge, then turns and runs to report.',
    'Mood piece about what the deposit means. Keep the metal look distinct from ore.',
    'Cold overcast light, metallic highlights.')

# ---------------------------------------------------------------- Fleet
G = 'Terran fleet'
add('terran_twinx_fighter', 'Twin-X Fighter', G, ['terran_twinx_fighter'], 'film',
    'Terran space fighter. Fast, fragile, flies in pairs.',
    'Blasters: about 8 small blue shots a second.',
    'Pair of fighters. Enemies: an Arcadian corvette with a gold honeycomb shield, Arcadian stingray fighters, the Orb in the distance.',
    'Two Twin-X fighters dive along the flank of an Arcadian corvette hammering its shield, shots rippling the honeycomb, then break in opposite directions as stingrays drop onto their tails.',
    'Neon blue engine lines. Shield ripples, never shatters.',
    'Space above the planet, sun low on the limb.')
add('terran_corvette', 'Terran Corvette', G, ['terran_corvette'], 'film',
    'Small Terran escort: point defence for the big ships.',
    'Flak: bursts of 4 at 0.09 s, then 0.6-0.9 s. Turrets track on their own.',
    'Allies: a Terran frigate or battleship it screens. Enemies: 4-5 Arcadian stingray fighters attacking the big ship.',
    'Stingrays swarm a Terran capital ship. The corvette slides in between, turrets snapping from target to target, flak bursts stitching space, and two stingrays vanish in gold flashes.',
    'Busy, protective, turrets with a life of their own.',
    'Inside a fleet formation, engine glows all round.')
add('terran_frigate', 'Terran Frigate', G, ['terran_frigate'], 'film',
    'Triple-hull Terran frigate: the fleet workhorse. Killed the Orb in the opening film.',
    'Twin cannons, about 0.5 s per gun, guns alternating.',
    'Enemy: an Arcadian corvette (arc weapon, 3 lightning pulses then 1.5 s). Optional: the Orb closing.',
    'A frigate and an Arcadian corvette circle each other at knife range, trading alternating cannon fire for triple lightning pulses; the frigate blue triangle shield flares and holds, and its guns finally crack the corvette open.',
    'Terran shields are translucent blue triangles. A duel.',
    'Near a moon or debris field, hard light.')
add('terran_missile_ship', 'Terran Missile Ship', G, ['terran_missile_ship'], 'film',
    'Terran missile ship: long range fleet artillery.',
    'Three missiles within 1 s, then 3 s reload. Tube doors open before and close after.',
    'Enemy: an Arcadian shell mothership far off with corvette escorts. Allies: corvette close by.',
    'Tube doors snap open along its spine. Pause. Three heavy missiles punch out, engines lighting a moment later, and the camera swings to follow them across the gulf to an Arcadian mothership, whose shield stretches inward around each warhead.',
    'Pause then ripple applies in space too. The shield wraps the missiles; it does not break.',
    'Wide dark space, planet glow from below.')
add('terran_broadside_battleship', 'Broadside Battleship', G, ['terran_broadside_battleship'], 'film',
    'Terran battleship built around its broadside. Cannons extend from one third to full length as it turns side-on.',
    'Heavy guns: one devastating blast about every 1.1 s per gun, boom-boom-boom down the line. Slow visible charge first.',
    'Enemy: an Arcadian crescent mothership at distance (kept out of the background for the build-up).',
    'Close on the battleship, alone. One slow deliberate turn of less than 90 degrees brings its flank round, cannons running out as it turns, charge glow climbing, then the broadside: heavy boom, boom, boom rolling down the hull, recoil rocking the whole ship.',
    'David: close, one deliberate turn, slow visible charge, then heavy boom-boom-boom. Its shield drops in a visible wave just before it fires.',
    'Open space, strong side light raking the hull.')
add('terran_dreadnought', 'Terran Dreadnought', G, ['terran_dreadnought'], 'film',
    'The largest Terran warship. Arrives through a Terran portal: a terrifying ragged tear ripped open in space.',
    'Many turrets firing on mixed rhythms; main guns heavy.',
    'Allies: frigates and corvettes for scale. Enemy: Arcadian fleet ahead.',
    'Space is grabbed and torn open in jerks: a tall ragged slit with blue-white veins. The dreadnought is pulled and stretched through it, snaps to true shape, and its escorts are dwarfed as every turret trains forward.',
    'Ships are visibly pulled and stretched through portals, never pop in. Scale is everything.',
    'Deep space, the tear lighting the hull blue.')
G = 'Arcadian fleet'
add('arcadian_stingray_fighter', 'Stingray Fighter', G, ['arcadian_stingray_fighter'], 'film',
    'Arcadian space fighter, ray-shaped.',
    'Gold needles, about 6 a second. Lightning thrusters.',
    'Flight of 3. Enemies: a Terran missile ship with a corvette escort.',
    'Three stingrays peel off like a school of rays, undulating, and rake a Terran missile ship from stern to bow with gold needles while its escort flak chases them.',
    'Graceful, organic flight; lightning thrusters crackle.',
    'Sunlit side of the planet below.')
add('arcadian_corvette', 'Arcadian Corvette', G, ['arcadian_corvette'], 'film',
    'Arcadian escort ship with a gold honeycomb shield.',
    'Arc weapon: 3 lightning pulses 0.2 s apart, then about 1.5 s recharge.',
    'Enemies: a pair of Twin-X fighters attacking, a Terran corvette.',
    'Twin-X fighters strafe the corvette and its honeycomb shield ripples gold. One fighter clips the shield: it stretches and wraps round the hull, then flings it off. Three lightning pulses reach out and take the second fighter.',
    'The shield wrap is the showpiece of this clip.',
    'Dark side of the planet, gold light on black.')
add('orb', 'The Orb', G, ['orb', 'terran_twinx_fighter'], 'film',
    'Arcadian anti-fighter: a glowing molten-gold core with 8 arms of many joints on floating shoulders, lightning tethers from core to shoulders. Thrusters only on the arms.',
    'It grabs fighters and tears them apart. Every arm moves completely independently, graceful, hyper-dexterous, like swinging while dodging bullets.',
    'Enemies: 2-3 Twin-X fighters shooting at it. Optional: a Terran frigate in the far background.',
    'Fighters open fire. The Orb flows between the shots, arms swinging it through space each on its own path, snatches one fighter out of its dive with two arms and pulls it apart, and is already reaching for the next.',
    'Deliberate, readable moves. Use the rigged file and its arm physics rather than re-rigging. David is still refining the arms, so keep arm motion smooth: no 180 degree flips.',
    'Open space, core glow as key light.')
add('arcadian_shell_mothership', 'Shell Mothership', G, ['arcadian_shell_mothership'], 'film',
    'Arcadian mothership with a layered shell hull.',
    'Lance: 0.8 s gold beam, about 2.2 s charge between, charge rings spin up first.',
    'Enemies: Terran frigates in a line. Allies: stingrays streaming out.',
    'Charge rings spin up along the shell, light running to the tip, then a lance beam holds on a Terran frigate for most of a second: shield wraps, flares, and the beam goes through. Stingrays pour out past the camera.',
    'Close gold beam hit and hold.',
    'Planet limb sunrise.')
add('arcadian_crescent_mothership', 'Crescent Mothership', G, ['arcadian_crescent_mothership'], 'film',
    'Crescent-shaped Arcadian mothership: carrier for the ground invasion. Drop pods leave from it.',
    'Lance beam as above; mainly launches pods.',
    'Allies: drop pods, corvette escorts. Enemies: Terran flak in the distance.',
    'The crescent hangs over the planet, horns glowing. Pods blast off its inner curve in a rippling sequence, lightning trails drawing a fan toward the surface, as it turns slowly to cover them with a lance shot.',
    'Pod trails are lightning, not flame.',
    'High orbit, planet filling the lower frame.')
add('arcadian_lens_mothership', 'Lens Mothership', G, ['arcadian_lens_mothership'], 'film',
    'The great lens-shaped Arcadian flagship. Arrives through an Arcadian portal: black, crisp, precise, electric, almost scientific.',
    'Lance beam focused through the lens.',
    'Allies: corvettes and stingrays arriving beside it. Enemy: Terran dreadnought far away.',
    'A perfect black disc opens with fine electric arcs. The lens ship is drawn through, stretched thin then settling to shape, light gathering across its lens face until it focuses one long lance across space.',
    'Counterpart to the dreadnought clip: precise where that one is violent.',
    'Black space, minimal stars, gold and white only.')


def brief_md(e):
    return f"""# Promo brief: {e['name']}

Promo id: `{e['id']}`   Group: {e['group']}   Models (registry names): {', '.join(e['models'])}

## What it is
{e['role']}

## Weapon and rhythm
{e['weapon']}

## Who else can be in the scene
{e['cast']}

## Suggested story (yours to improve)
{e['story']}

## Notes
{e['extra']}

## Setting
{e['setting']}

## {RULES}
"""


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, 'briefs'), exist_ok=True)
    status_path = os.path.join(here, 'status.json')
    status = json.load(open(status_path)) if os.path.exists(status_path) else {}
    for e in E:
        open(os.path.join(here, 'briefs', e['id'] + '.md'), 'w').write(brief_md(e))
    lines = ['# Promo clip checklist', '',
             'One 6 second clip per entity. Columns: script written, draft reviewed, final rendered, shown to David.',
             'Status lives in status.json (edited by the orchestrator); this file is generated by entities.py.', '']
    group = None
    for e in E:
        if e['group'] != group:
            group = e['group']
            lines += ['', f'## {group}', '', '| Entity | Promo id | Model state | Script | Draft OK | Final | Shown |', '|---|---|---|---|---|---|---|']
        s = status.get(e['id'], {})
        mark = lambda k: 'yes' if s.get(k) else ''
        lines.append(f"| {e['name']} | {e['id']} | {e['settled']} | {mark('script')} | {mark('draft')} | {mark('final')} | {mark('shown')} |")
    lines += ['', f'{len(E)} clips.']
    open(os.path.join(here, 'CHECKLIST.md'), 'w').write('\n'.join(lines) + '\n')
    print(len(E), 'briefs written')
