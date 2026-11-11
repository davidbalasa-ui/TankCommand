# Progress

## WP-01

Built the project foundation: Vite/TypeScript scaffolding, Capacitor config, headless deterministic sim shell, asset manifest/registry/loader with browser three.js decoders, placeholder unit data schema and table, save envelopes and autosave rotation, key-value storage adapters, lifecycle and watchdog services, DOM screen router and screens, three.js render shell, test hook, credits and requirement-coverage scripts, unit tests, Playwright flows, CI workflow, and project documentation. No gameplay rules or final balance data were added.

## WP-02

Added the first playable slice: deterministic heightmap terrain with a ridge and gap, A* movement with formation goals and separation, unit commands and validation, turret tracking, projectiles with accuracy, splash and wrecks, win/lose detection, save round-tripping of the new state, an RTS camera, terrain and tank rendering with turret pivots and enemy tinting, selection and health overlays, projectile and wreck visuals, desktop and touch input, a full-screen skirmish HUD, results flow with Play again, WP-02 unit and browser tests, and updated documentation and control inventory.

## WP-02 readability pass

Play-test follow-up: the tank model was being scaled against a hidden 200×200 ground plane inside the glb, so tanks rendered as a few pixels; scaling now measures only visible meshes. The camera starts on the player's tanks at distance 40 with an eased ~49° pitch, the scene has a sky gradient plus a ground skirt and far plane instead of black void, the terrain uses a valley/slope/rock colour ramp with flat shading for legible hills, and ground picking raycasts the skirt as well so a right-click on any visible ground issues an order. Added `unitScreenBounds()` to the test hook plus `PLAY-02` (drag-select then right-click moves every tank) and `VIS-02` (a tank is at least 30 px on its longer side).

## WP-02 performance guard

Added the dynamic quality controller from the SOR ("a dynamic quality setting lowers effects, shadows and resolution automatically when frame rate drops below budget"). `src/render/quality.ts` holds a pure controller over a 1 s rolling average of frame times: above 50 ms for 1 s steps the level down, below 25 ms for 3 s steps it back up, and never twice within 1 s. The renderer applies each level by halving the shadow map, then disabling shadows, then lowering the pixel ratio in three steps to 0.5; frame gaps that mean "frames stopped" are ignored. `quality()` is exposed read-only through the test hook and the controller is covered by `PERF-01`. Kept input latency the acceptance criterion: `[INP-05]` (HUD clicks on a busy main thread) is unchanged and now passes on a 2 vCPU software-rendered runner.

## WP-03

Phone-first controls, camera and HUD shell.

- **Camera.** One smooth zoom from close 3D to strategic top-down. The maximum distance is derived from map size, the viewport's field of view and aspect rather than a constant, and recomputed on every resize, so the whole map fits at full zoom-out on 915×412, 1280×800 and 1920×1080 (CAM-03). Pan clamps to the map square (CAM-04). `CAMERA_PITCH_CURVE` was re-fit from 0.75 to 0.5 so the WP-02 default view (distance 40, ~49° pitch) survives the new, larger zoom ceiling. Panning speed scales with the camera distance (`camera.distance * 0.9 * seconds`). `setViewport(aspect, fov)` in `src/render/camera.ts` pushes the fit inputs from the renderer's `ResizeObserver`.
- **Touch.** One-finger drag pans from ground, from over a unit, from the sky (screen-space fallback scaled by distance) and from any point at the map edge; pressing on a tank still selects if the finger is released without moving, but any drag past 6 px pans and never issues an order. Two-finger pinch (around the midpoint) and twist run in one gesture; lifting one finger pins the camera and never produces a tap. Two-finger tap deselects; double-tap selects same-type units on screen; long-press (400 ms) then drag box-selects. `touch-action: none`, `overscroll-behavior: none`, `user-select: none` and a `contextmenu` handler lock the page down. Thresholds live in `src/ui/inputTuning.ts`.
- **Mouse and keyboard.** Right-drag and middle-drag pan; Alt+left-drag and Q/E rotate (middle-drag rotation moved to Alt+left-drag); wheel zooms towards the cursor; WASD/arrows pan; S stops, H holds, A then left click attack-moves; Ctrl+1-9 assign control groups, 1-9 select, double-press recentres; Space is wired to a stub alert list; the minimap accepts click/drag to jump and right click to order.
- **Sim orders.** Added `hold` and `attackMove` to `src/sim/commands.ts`, plus `queue: true` on `move`/`attackMove` so waypoints append. Unit stance (`free` / `hold`) is world state and survives `serialize`/`deserialize`. `hold` keeps the turret tracking and firing but clears the path every tick; `attackMove` stops and engages any enemy inside sight range.
- **HUD shell.** DOM over the canvas: top bar (placeholder resources, game clock, deselect, left-handed toggle, pause), a 2D-canvas minimap (terrain height colours, unit dots, camera footprint quad, redrawn on a 200 ms timer), a vertical command bar (attack-move, hold, stop, queue, groups) that disables with no selection, a selection panel with per-unit icons, a groups strip of tiles 1-5 with long-press assign and double-tap centre, and per-unit health bars when damaged or selected. Left-handed mode mirrors minimap and command bar and is stored in `localStorage` under `setting.leftHanded` so it survives reload.
- **Tests.** New `tests/e2e/wp03.spec.ts` covers TCH-01, TCH-02, TCH-03, TCH-04, CAM-03, CAM-04, MM-01, MM-02, HUD-01, HUD-02, HUD-03, HUD-04, GRP-01 and DESK-01 with real pointer/touch gestures and hook assertions; new `tests/unit/orders.test.ts` covers ORD-01, ORD-02, ORD-03 headless. New `tests/e2e/screens.spec.ts` writes the five `test-results/shots/wp03-*.png` screenshots for visual review on the phone project only. `src/testhook/testhook.ts` grew `groundPickAt()`, `unitIsOnScreen()`, `cameraFootprint()`, `orderPaths()`, `hud()` and `setSelection()`; `HudSnapshot` grew `queueMode` and `attackMoveArmed` so buttons can be asserted through the state they change rather than DOM classes.

## WP-10

Game shell, saves, settings, generated audio, alerts and bug reporting.

- **Pause and speed.** Pause now freezes the sim and blocks commands in `App.sendCommand`; lifecycle pause stops the loop, and Android back opens the pause menu (a second back resumes). Speed is slow/normal/fast (0.5×, 1×, 2×) from the pause menu and a separate top-bar speed button mounted outside `hud.ts`.
- **Saves.** Manual save/load uses five slots; autosaves rotate three slots and persist their cursor in the KV store so a relaunch never overwrites the newest autosave first. `SaveManager.load` now returns typed `ok` / `missing` / `corrupt` / `incompatible` results, and the save-slot UI shows a message for each. Export/import exists in Settings and storage-full is surfaced as a message. Quit offers save-and-quit or quit-without-saving.
- **Settings.** New settings screen and persisted settings store: volumes, graphics quality, health bars, edge scroll and speed, camera sensitivity, key rebinding, left/right-handed layout, text size, colour-blind colours and haptics. Graphics quality is wired to the existing quality ladder; health bars and colour-blind tones are applied by the renderer; text size and edge scroll apply immediately.
- **Audio and haptics.** New generated Web Audio engine (oscillators/noise, no audio files) with selection, order acknowledgements, weapons, explosions, drop beam, mining, delivery, pack/deploy, aircraft and alert sounds plus generated faction music with a combat crossfade. Audio unlocks on the first user gesture only. Haptics call the Capacitor Haptics plugin through `registerPlugin` (no new dependency) and are a no-op on web.
- **Alerts.** UI-layer alert centre compares world state between frames and fires under-attack and unit-lost alerts, rate-limited; structure/pad/deposit/research/drop/objective/not-enough-resources are typed stubs with a public `raiseAlert(kind,x,z)` entry point. Toasts are touch-sized and tap-to-jump; Space jumps to the latest.
- **Bug report.** Pause → Report bug collects description, include-save checkbox, device info, version, last freeze report and the last 200 log lines. It writes a JSON file via Capacitor Filesystem on native or a browser download on web and makes no network request.

- **Tests.** New `tests/e2e/wp03.spec.ts` covers TCH-01, TCH-02, TCH-03, TCH-04, CAM-03, CAM-04, MM-01, MM-02, HUD-01, HUD-02, HUD-03, HUD-04, GRP-01 and DESK-01 with real pointer/touch gestures and hook assertions; new `tests/unit/orders.test.ts` covers ORD-01, ORD-02 and ORD-03 headless. New `tests/e2e/screens.spec.ts` writes the five `test-results/shots/wp03-*.png` screenshots for visual review on the phone project only. `src/testhook/testhook.ts` grew `groundPickAt()`, `unitIsOnScreen()`, `cameraFootprint()`, `orderPaths()`, `hud()` and `setSelection()`; `HudSnapshot` grew `queueMode` and `attackMoveArmed` so buttons can be asserted through the state they change rather than DOM classes.

## WP-04

Economy, Landing Pads and orbital drops.

- **Data.** Added a structure data sheet, map data with fixed symmetric ore/metal deposits, and a full placeholder roster per faction: Landing Pad, Ore Miner, Metal Station, Tug, tank and Scout. Unit/structure economy values (costs, delivery, mining rate, load sizes, salvage percentage, metal extraction) live in JSON; match/economy timing constants live in `src/sim/tuning.ts`.
- **Economy.** `src/sim/economy.ts` owns side resources, ore credit, metal credit, station extraction, nearest-pad selection, salvage and worker-assignment commands. `src/sim/workers.ts` runs miner and tug jobs: ore is credited only at a pad, metal only at a pad, deposits run empty, an empty deposit raises a `depositEmpty` alert, and a destroyed tug loses its load. Ore and metal are integer resources and are never deducted below zero.
- **Drops.** `src/sim/drops.ts` validates and applies `buy`, `cancel` and `placeKit`. Buying deducts the full cost at order time; refusals carry a reason. Queued items progress per side, pause when a side has no pad, deliver units beside the chosen pad, deliver structures as pending kits, and cancel for a full refund before delivery. Structure kits validate ground, overlap and metal-deposit placement.
- **Match flow.** `src/sim/match.ts` eliminates a side with no pads, no fighting units and no pending Landing Pad kit, then declares the last side alive or a draw. Starting skirmish setup in `src/sim/skirmishSetup.ts` gives each side a pad, miner, tug, two tanks, 500 ore and 100 metal.
- **Combat.** Units and projectiles can now target and damage structures, so pads are real objectives; splash also damages structures. Existing unit combat behaviour is unchanged.
- **UI.** The top bar shows live ore, metal, worker count and unit count/cap. The command bar gained Build, Mine, Assign and Salvage. The build sheet is a grouped phone bottom sheet (side panel on desktop) with costs, delivery times, disabled reasons, pad selection, queue progress and cancel. Structure kits enter a ghost-placement mode with green/red validity, confirm and cancel. Tapping a miner then a deposit issues a mine order; tapping a tug then a metal station assigns it.
- **Render.** Placeholder structure meshes, deposit markers, drop-beam columns and the structure placement ghost are rendered in `src/render/renderer.ts`.
- **Tests.** Added WP-04 unit suites for ECO-01..06, DROP-01..04, MATCH-01 and DET-02, plus phone e2e coverage for HUD-05, DROP-04, worker orders, salvage, touch placement and MATCH-02 results. `tests/e2e/screens.spec.ts` writes the six `wp04-*` visual-review screenshots.

## WP-05

Turrets, radar, labs, packing, research, upgrades and repair (written directly by Claude).

- **Sim.** `structures.ts` (pack, deploy, dismantle, turret fire, damage states, rubble), `research.ts` (tree, lab jobs, unlocks), `upgrades.ts` (fire rate, armor, stealth) and `repair.ts` (repair vehicles). New commands: pack, deploy, dismantle, research, cancelResearch, upgrade, repair. Placement now also checks slope and rubble.
- **Data.** Repair and packed-turret units plus turret, radar and lab structures per faction; `research.placeholder.json` with six nodes per faction. All numbers are placeholders until Stage 0.
- **UI.** A Base button opens a bottom sheet with the research tree (cost, time, state, progress), structure Pack/Dismantle buttons and per-vehicle Deploy/Upgrade buttons. Locked build items show "Needs: <research>"; packed turret units are hidden from the build list. Structures draw per kind, darken with damage, and rubble shows as a mound.
- **Tests.** `tests/unit/wp05.test.ts` covers STR-01..05, RES-01..02, UPG-01..02, REP-01 and DET-03; `tests/e2e/wp05.spec.ts` checks locked items and the Base sheet by touch.

## WP-06

Diplomacy and vision (written directly by Claude).

- **Diplomacy.** `src/sim/diplomacy.ts`: sides (controller, team, group), ordered-pair relations, `diplomacy.set`, provocation with group and forgive timer. Targeting, projectiles, splash, turrets and repair use relation queries; match result counts only human and AI sides with team victory.
- **Vision.** `src/sim/vision.ts`: per-side explored/visible grid every 4 ticks with terrain line of sight, allied shared viewers, sensor contacts, radar (tower and mobile unit), stealth, remembered structure ghosts, and `perceivedUnits`. State is saved and hashed.
- **Rendering/UI.** The app hands the renderer, HUD, minimap and test hook a player-view world with hidden enemies removed and ghosts added. Terrain is darkened by a fog texture, contacts are pulsing rings, the minimap shows fog and contacts. Settings has a fog on/revealed toggle.
- **Not done yet.** FOG-07 frame-cost measurement and the wp06 screenshots 2 to 4.

## WP-07

Enemy AI (written directly by Claude).

- **Structure.** `src/ai/` (ai.ts, aiData.ts, driver.ts). The AI reads only `perceivedUnits` plus its own side's state and returns commands through `stepWithAi`, which feeds them to the normal validated command channel. AI state (rng, scout, attack group) lives in `world.aiStates`, saved and hashed. `src/ai` has the same lint isolation as `src/sim`.
- **Behaviour.** Miners and tugs kept working, up to two metal stations, a lab with research, turrets by army size, an armed mix of tanks, one scout until an enemy structure is found, ghost-based targeting, defence of workers and base, attack groups with retreat on heavy losses, focus fire on normal and hard, and an all-in fallback when metal runs out. Easy, normal and hard differ only in data (reaction time, army threshold, stations, lab, defence, focus fire); none gets a resource bonus.
- **Hookup.** Skirmish gives player 2 a normal AI (setting `setting.ai=off` disables it for e2e). Terrain is now rotationally symmetric so both bases are equal.
- **Tests.** `tests/unit/ai.test.ts` plays 10 fixed-seed hard-vs-easy matches (about 30 s) and checks AI-01 to AI-09 and DET-05. `npm run ai:soak` runs more matches (not part of CI).
- **Not done.** The debug route to watch AI-vs-AI in test builds, and wp07 screenshots.

## WP-08 Air units and water

- **Terrain.** Maps can carry lakes and rivers (with fords) via `features` on the map row. Water is carved into the heightmap and saved as `mapSpec`. Movement classes (`tracked`, `hover`, `air`) are a view of the map (`mapFor`), so pathing and collision need no special cases. Second map `map.wp08_lakeside`; pick it with `localStorage setting.map` until the WP-09 skirmish setup screen.
- **Air.** `src/sim/air.ts`: parked / flying / returning / rearming. Aircraft are bought only with a free air base slot, launch and recall by command, burn fuel, go home when fuel is short or ammo is out, rearm at base, and crash when dry with no base. Aircraft never push or get pushed by other units.
- **Combat.** `weapon.targets` is honoured by units and turrets: ground-only guns cannot hit flying aircraft, parked aircraft are ground targets, bombers cannot target air.
- **Data.** Hover tank, fighter and bomber per faction (alien: glider, saucer, dropper), air base / hangar structures, an Aviation research node per faction.
- **UI.** Launch/Recall button and ammo/fuel line appear when aircraft are selected; renderer draws a water plane and lifts flying aircraft.
- **Tests.** `tests/unit/wp08.test.ts` (TER-01/02, AIR-01..05, DET-06), `tests/e2e/wp08.spec.ts`.
- **Not done.** AI does not build or use aircraft or hover units; parked aircraft stack on the base centre visually; more wp08 screenshots.

## WP-09 Missions, campaigns and skirmish setup

- **Mission data.** `src/sim/missionSchema.ts` (zod) defines missions, conditions, actions and triggers; invalid files name the failing field. Four placeholder missions live in `src/data/missions/` (two training, Human 1 and Alien 1). `buildMissionWorld` turns a mission row into a world (sides, relations, tagged units, research done, AI sides).
- **Trigger engine.** `src/sim/triggers.ts`, run every tick inside `step` in place of the normal elimination rule. Conditions: time, areaEntered, unitDestroyed, allDestroyed, resourceReached, objectiveDone, structureBuilt, relationIs, unitsAlive, unitEscorted, and/or/not. Actions: spawn (with drop beam), message, revealArea, setObjective, grant, win, lose, aiOrder, setRelation. Mission state is saved and hashed. Win is all primary objectives done; lose is a failed primary objective, a lose action, the time limit, or the player's base falling.
- **Screens.** Campaign select, mission select (locked greyed), briefing with a heightmap preview, in-game Objectives sheet and message toast, results with Next/Retry/Mission list, and a skirmish setup screen (map, faction, 1-3 AI with faction and level, resources, start force, fog). Campaign progress is saved through the kv layer.
- **Skirmish.** `createSkirmishWorld` now takes map, resources and start force, and adds corner starts for a third and fourth side.
- **Tests.** `tests/unit/wp09.test.ts` (MSN-01..05, 07, DET-07), `tests/e2e/wp09.spec.ts` (MSN-05, MSN-06, SKR-01). MSN-03 wins use a scripted command stream (explicit attack on structures).
- **Not done.** The training area is not marked in the 3D view yet; revealArea uses a circle, not a rectangle; best result per difficulty is just best time; mission AI is not shown any briefing art.

## WP-10 merge (2026-11-11)

WP-10 (pause, speed, five save slots, settings, generated audio, alerts, offline bug report) was built against WP-04 and is now merged on top of WP-05..09. The settings screen keeps WP-06's fog toggle; units are tinted by hostility with the colour-blind palette; the controls inventory is the union of both.

## C-01 Stage 0 research, first pass (2026-11-11)

`docs/research/` holds the first pass. The sandbox could only see search-result summaries (page fetches to Wikipedia, GameSpot, MobyGames and similar were refused), so almost every Measure item is settled as **Decided** with a reason, and `datasheet-proposal.md` is a tuned balance rather than measured values. A second pass is worth doing if those sites become reachable.

## C-02 Engine gaps (2026-11-11)

- **AI air.** Normal and hard AIs build an air base once their army reaches 5 / 4 fighting units (and aviation is researched), buy aircraft while a slot is free (an anti-air type first when enemy aircraft have been seen), launch interceptors at enemy aircraft near the base, and launch strikes of two or more at radar, turrets, stations, then pads (or workers when no structure is known). Easy never uses aircraft. Hover tanks were already bought as tanks once unlocked. Kits now try six rings around the pad, so large structures such as the air base are placed instead of blocking all further building. Test: `tests/unit/ai-air.test.ts` (AI-10).
- **Goal markers.** `missionMarkers()` in `sim/triggers.ts` lists the player's unfired areaEntered and unitEscorted areas; the 3D view draws a pulsing ring with a tall beam, and the minimap a yellow circle. Test: `tests/unit/markers.test.ts` (MSN-08).
- **Mission saves.** Loading a save restores mission mode, the selected mission and campaign, so Retry, Next and progress recording work after a load.

## C-03 Roster, data and working names (2026-11-11)

- **Data.** Every unit and structure row is now `tuned` from `docs/research/datasheet-proposal.md` (no placeholders left). New per faction: heavy tank, missile tank (hits air), artillery (range 34, can't fire on the move), missile battery (packable, hits air) and its packed unit. Aliens get the saucer as their signature aircraft behind Disc Flight; humans keep fighter and bomber. Turret weapons now carry `targets`.
- **Research.** Three tiers (see decisions log). Aviation now needs Sensors.
- **Names.** Working names: Terran Coalition vs the Kesh, unit call-signs in the data. Final public names need David's approval.
- **AI.** Builds a missile battery for every other defence once enemy aircraft have been seen; desperation counts only metal it can still reach.
- **Sim fix.** A tug at a dry station moves itself to a station that still has metal.
- **Tests.** DATA-01/03 updated for the new roster; AI-02 waits until an enemy is genuinely hidden; MSN-03's scripted player finishes off stray units; the two placeholder combat missions start with 300 metal.

## C-04 Art: faction sets (2026-11-11)

- **Approved looks.** David approved the Terran Lancer and Kesh Darter samples ("we should be able to make assets for the 2 factions now"). Every model is scripted Blender (`tools/art/`), one 512px atlas per faction, phone budgets (2,500 triangles, 5,000 for big units).
- **Kit.** `tools/art/kit.py` holds the shared modelling helpers (prisms with chamfer and taper, lofts, lathes, orbs mapped onto the glow tiles, assemble with TurretPivot, previews framed to size).
- **Units.** `terran_set.py` (13 new units: Outrider, Prospector, Hauler, Mender, Watchman, Skimmer, Bulwark, Javelin, Longbow, Falcon, Condor, packed Bastion and Spire) and `kesh_set.py` (13 new units, including a new Stinger light tank with a scorpion-tail weapon, since the old Stinger look became the Darter scout). All 28 unit types now point at their own model.
- **Structures.** `structures_set.py` builds the 7 structures per faction sized to their footprints; the renderer draws the model in place of the box (the box stays invisible for picking) and turns its TurretPivot.
- **Loading.** Models now load in parallel (sequential loading took about 30 seconds on a busy machine).
- **Open.** The renderer still scales every unit to one tank length; a per-type visual size is next. The third faction (mushroom crawler, `myco_crawler.py`) and the crystal superweapon are samples only.

## C-05 Landing pad traffic (2026-11-11)

- Pads are 6x6 cells with the exit facing the map centre. Deliveries come down one at a time in order (`src/sim/pad.ts`), drive off the exit to a rally grid, and the next waits until the deck is clear. Cancelling is refused once a delivery is descending.
- Loaded workers line up at one dock beside the pad and unload one at a time; the cargo lifts off to the ships. New pad and nest models with ramp, deck ring and cargo lift. The game now has soft environment reflections.

## C-06 Economy: miners dig, haulers deliver (2026-11-11)

David's rule: one unit mines out of the ground, another delivers to the landing pad for the ships. Miners no longer drive to the pad.

- **Miners** grind ore into their hopper and pack each full load into an ore crate beside the deposit (`ORE_CRATE_SIZE` 10, up to `ORE_MAX_CRATES` 5 per side per deposit, stored on `DepositState.crates`). With the stack full the miner stops until a crate is taken. When the deposit runs out, the last part-filled crate is packed and the miner reports the deposit empty.
- **Haulers** (tugs) are the only units that deliver. They collect ore crates from deposits or metal containers from stations, as many as they hold (30), and unload at the pad's single dock line. Idle haulers find work by themselves; a new `haul` command (tap an ore deposit with haulers selected) points them at one deposit. Unserved stations are preferred so metal does not stall.
- **Balance.** Tug carry 10 -> 30 and metal cost 20 -> 0, so a side can always rebuy a hauler and restart its income. The AI buys about one hauler per miner, plus one for metal.
- **Visuals.** Ore heap in the miner's hopper grows with its load and the miner judders while grinding; haulers carry painted crates or containers on their back; crate stacks sit beside each deposit facing the owner's pad.
- **Missions.** Mining training mission gets a hauler and new briefing text.
- **Tests.** ECO-01/02 rewritten for the new flow, ECO-01b (full stack stops digging), ECO-01c (save/load hash with crates), ECO-01d (haul command validation); PAD-04 uses haulers. AI-07 hard beats easy 10/10.
