# Datasheet proposal

Source key for every number: "placeholder" = carried from src/data/*.placeholder.json (scout, light tank, ore miner, landing pad, metal station rows where they match); everything else "tuned" (RTS-standard relative values chosen here). NO number comes from the original game: no stat table was reachable (see sources.md). Original unit names: Unknown for all, so that column says Unknown.

Units: ore/metal cost, delivery seconds, speed in m/s, range in metres, accuracy 0-1. Armor is subtracted from damage per hit (minimum 1 per hit, Decided).

Balance logic (all "tuned"): scouts fast and fragile; heavy tanks slow and tough; missiles (range 18-20) outrange tank cannon (12-13) and are the only ground answer to air besides fighters/saucers; artillery (34) outranges turrets (14-20) but cannot fire on the move and is fragile; fighters beat bombers; bombers beat static defence; saucer is a premium all-round aircraft.

Mining (tuned): ore miner carry 20, 4 ore/s digging, packs in 4 s, salvage 50%; metal station 1.5 metal/s into 10-metal containers, up to 5 stored, tug carries 2 containers (20 metal).

Research (tuned, 3 tiers, same both sides; cost ore/metal, seconds): T1 Armor Plating 80/20 20s; Fire Control 80/20 20s. T2 Fortifications 120/40 30s (gun battery, needs Armor Plating); Sensors 120/40 30s (radar tower, mobile radar, needs Fire Control); Missiles 120/50 30s (missile tank, missile battery; needs Fire Control); Metal Extraction 100/0 25s (station, tug). T3 Heavy Armor 200/80 40s (heavy tank, repair; needs Fortifications); Heavy Ordnance 200/100 40s (artillery, heavy missile; needs Missiles); Aviation 220/100 45s (heli-pad, fighter, bomber; needs Sensors); Advanced Aviation 300/150 60s (alien: saucer; human: no unlock, Decided: grants +10% air hp as a mild counterpart).

## Human faction
| ID (generic) | Original name | Role | Ore | Metal | Delivery s | HP | Armor | Speed m/s | Sight | Weapon | Dmg | Range | Reload s | Proj m/s | Acc | Splash | Targets | Fire on move |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unit.human.scout | Unknown | ground light | 50 | 0 | 6 | 80 | 1 | 11 | 12 | autocannon | 10 | 8 | 1.2 | 55 | 0.85 | 0 | ground,structure | yes |
| unit.human.light_tank | Unknown | ground | 100 | 50 | 12 | 220 | 4 | 8 | 14 | cannon | 30 | 12 | 2.5 | 40 | 0.85 | 0.5 | ground,structure | yes |
| unit.human.heavy_tank | Unknown | ground | 220 | 120 | 20 | 520 | 9 | 5 | 14 | heavy cannon | 60 | 13 | 3.0 | 38 | 0.85 | 1.0 | ground,structure | no |
| unit.human.light_missile_tank | Unknown | ground | 140 | 80 | 14 | 150 | 2 | 7 | 16 | missile | 28 | 18 | 3.5 | 30 | 0.9 | 0.8 | ground,air,structure | no |
| unit.human.heavy_missile_tank | Unknown | ground | 240 | 140 | 20 | 300 | 5 | 5 | 16 | missile salvo | 45 | 20 | 4.0 | 30 | 0.9 | 1.2 | ground,air,structure | no |
| unit.human.artillery | Unknown | ground | 260 | 160 | 22 | 140 | 2 | 4 | 12 | shell | 90 | 34 | 6.0 | 25 | 0.6 | 3.0 | ground,structure | no |
| unit.human.mobile_radar | Unknown | ground support | 120 | 60 | 12 | 100 | 1 | 7 | 10 | none | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| unit.human.repair_vehicle | Unknown | ground support | 120 | 40 | 12 | 120 | 2 | 8 | 10 | repair beam (heals 15 hp/s) | 0 | 6 | 0 | 0 | 1 | 0 | friendly | yes |
| unit.human.ore_miner | Unknown | worker | 80 | 0 | 8 | 120 | 1 | 6 | 10 | none | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| unit.human.metal_tug | Unknown | worker | 90 | 0 | 8 | 100 | 1 | 7 | 10 | none | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| unit.human.fighter | Unknown | air | 180 | 100 | 15 | 90 | 2 | 18 | 18 | air missiles | 18 | 14 | 1.5 | 45 | 0.9 | 0 | air,ground | yes |
| unit.human.bomber | Unknown | air | 220 | 120 | 18 | 130 | 2 | 12 | 14 | bombs | 120 | 2 | 4.0 | 0 | 0.8 | 3.0 | ground,structure | yes |

### Structures
| ID | Original name | Ore | Metal | Delivery s | HP | Armor | Sight | Weapon | Notes |
|---|---|---|---|---|---|---|---|---|---|
| structure.human.landing_pad | Unknown | 300 | 0 | 15 | 1200 | 8 | 10-18 | - | drop point |
| structure.human.metal_station | Unknown | 200 | 50 | 12 | 600 | 4 | 10-18 | - | on metal deposit, 1.5 metal/s |
| structure.human.gun_battery | Unknown | 150 | 40 | 10 | 400 | 6 | 10-18 | cannon 25 dmg, range 14, reload 2.0, ground | packable 4 s |
| structure.human.missile_battery | Unknown | 180 | 70 | 12 | 350 | 5 | 10-18 | missile 25 dmg, range 20, reload 3.0, air+ground | packable 4 s |
| structure.human.radar_tower | Unknown | 120 | 40 | 8 | 250 | 3 | 10-18 | - | sensor range 30, sight 14 |
| structure.human.heli_pad | Unknown | 250 | 60 | 14 | 500 | 5 | 10-18 | - | 4 aircraft slots, rearm 10 s |

## Alien faction
Same numbers as human (Decided: symmetry per spec); extra row for the saucer. Alien names and looks differ only visually.
| ID (generic) | Original name | Role | Ore | Metal | Delivery s | HP | Armor | Speed m/s | Sight | Weapon | Dmg | Range | Reload s | Proj m/s | Acc | Splash | Targets | Fire on move |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unit.alien.scout | Unknown | ground light | 50 | 0 | 6 | 80 | 1 | 11 | 12 | autocannon | 10 | 8 | 1.2 | 55 | 0.85 | 0 | ground,structure | yes |
| unit.alien.light_tank | Unknown | ground | 100 | 50 | 12 | 220 | 4 | 8 | 14 | cannon | 30 | 12 | 2.5 | 40 | 0.85 | 0.5 | ground,structure | yes |
| unit.alien.heavy_tank | Unknown | ground | 220 | 120 | 20 | 520 | 9 | 5 | 14 | heavy cannon | 60 | 13 | 3.0 | 38 | 0.85 | 1.0 | ground,structure | no |
| unit.alien.light_missile_tank | Unknown | ground | 140 | 80 | 14 | 150 | 2 | 7 | 16 | missile | 28 | 18 | 3.5 | 30 | 0.9 | 0.8 | ground,air,structure | no |
| unit.alien.heavy_missile_tank | Unknown | ground | 240 | 140 | 20 | 300 | 5 | 5 | 16 | missile salvo | 45 | 20 | 4.0 | 30 | 0.9 | 1.2 | ground,air,structure | no |
| unit.alien.artillery | Unknown | ground | 260 | 160 | 22 | 140 | 2 | 4 | 12 | shell | 90 | 34 | 6.0 | 25 | 0.6 | 3.0 | ground,structure | no |
| unit.alien.mobile_radar | Unknown | ground support | 120 | 60 | 12 | 100 | 1 | 7 | 10 | none | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| unit.alien.repair_vehicle | Unknown | ground support | 120 | 40 | 12 | 120 | 2 | 8 | 10 | repair beam (heals 15 hp/s) | 0 | 6 | 0 | 0 | 1 | 0 | friendly | yes |
| unit.alien.ore_miner | Unknown | worker | 80 | 0 | 8 | 120 | 1 | 6 | 10 | none | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| unit.alien.metal_tug | Unknown | worker | 90 | 0 | 8 | 100 | 1 | 7 | 10 | none | 0 | 0 | 0 | 0 | 0 | 0 | - | - |
| unit.alien.fighter | Unknown | air | 180 | 100 | 15 | 90 | 2 | 18 | 18 | air missiles | 18 | 14 | 1.5 | 45 | 0.9 | 0 | air,ground | yes |
| unit.alien.bomber | Unknown | air | 220 | 120 | 18 | 130 | 2 | 12 | 14 | bombs | 120 | 2 | 4.0 | 0 | 0.8 | 3.0 | ground,structure | yes |
| unit.alien.saucer | Unknown | air (alien only) | 320 | 200 | 24 | 260 | 4 | 14 | 16 | plasma | 35 | 14 | 1.5 | 45 | 0.9 | 0.5 | ground,air,structure | yes |

### Structures
| ID | Original name | Ore | Metal | Delivery s | HP | Armor | Sight | Weapon | Notes |
|---|---|---|---|---|---|---|---|---|---|
| structure.alien.landing_pad | Unknown | 300 | 0 | 15 | 1200 | 8 | 10-18 | - | drop point |
| structure.alien.metal_station | Unknown | 200 | 50 | 12 | 600 | 4 | 10-18 | - | on metal deposit, 1.5 metal/s |
| structure.alien.gun_battery | Unknown | 150 | 40 | 10 | 400 | 6 | 10-18 | cannon 25 dmg, range 14, reload 2.0, ground | packable 4 s |
| structure.alien.missile_battery | Unknown | 180 | 70 | 12 | 350 | 5 | 10-18 | missile 25 dmg, range 20, reload 3.0, air+ground | packable 4 s |
| structure.alien.radar_tower | Unknown | 120 | 40 | 8 | 250 | 3 | 10-18 | - | sensor range 30, sight 14 |
| structure.alien.heli_pad | Unknown | 250 | 60 | 14 | 500 | 5 | 10-18 | - | 4 aircraft slots, rearm 10 s |
