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
