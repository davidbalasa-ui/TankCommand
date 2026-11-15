# Work package WP-02: first playable slice

You built WP-01 (the project foundation). The full current repository is attached after this spec.
Now turn it into something a person can actually play with for a minute: a 3D battlefield with hills,
a camera they can move, tanks they can select and drive, and enemy tanks they can shoot and destroy.
All numbers are placeholders (from `src/data/units.placeholder.json` or constants you define in one file,
`src/sim/tuning.ts`, each commented `// placeholder until Stage 0`).

All WP-01 hard rules still apply (§0 of the WP-01 spec): pinned versions (no new dependencies at all),
strict TypeScript, `src/sim` headless and deterministic (no Math.random, no clocks, no DOM, no three),
every requirement ID has a test that fails if the feature is stubbed, `npm run ci` and `npm run test:e2e`
must pass, no eslint-disable comments, no weakening lint or tsconfig. Keep all WP-01 tests passing; you may
change a WP-01 test only where this spec changes the behaviour it tests, and say so in the report.

## 1. Simulation (src/sim) — all game rules live here

### 1.1 Map
- `MapDef { size: number (world units, square, origin at centre, so x,z in [-size/2, size/2]); cellSize: number; heights: Float32Array (grid (n+1)×(n+1) of vertex heights); }`
- `generateMap(seed, size=160, cellSize=2)`: deterministic heightmap from the seeded `Rng` (sum of a few octaves of value noise is fine), flattened near the two start areas (player start around (-50, -50), enemy start around (50, 50)), with at least one steep ridge between them that has at least one gap.
- `heightAt(map, x, z)` bilinear. `slopeAt` per cell. A cell is **blocked** if its max slope exceeds `MAX_SLOPE` (tuning) or it is outside the map.
- The map lives in `WorldState` by reference to its seed (regenerate it from the seed on load; do not serialise the heights into saves).

### 1.2 Units
- `UnitState { id: number; owner: PlayerId; typeId: string; x; z; heading (radians); turretHeading (radians, world space); hp; order: Order; path: {x,z}[]; reloadLeft (s); stuckTicks }`.
- Unit ids are assigned sequentially by the sim (`world.nextId`), never reused.
- Stats come from the unit data table (WP-01 `loadUnitTable`). Pass the table into the sim as plain data at world creation (`createWorld(seed, { unitTypes, startUnits })`) so the sim never imports JSON or assets itself.
- Skirmish start (default `startUnits`): player 1 gets 4 `unit.human.light_tank` near its start; player 2 gets 4 `unit.human.light_tank` near its start (we only have one model). Player 2 has no AI in this package: its units hold position and auto-fire at anything in range.

### 1.3 Commands (extend the WP-01 union; keep `noop` and `debug.addCounter`)
- `{ kind:'move', unitIds:number[], x, z, queue?: boolean }`
- `{ kind:'attack', unitIds:number[], targetId:number }`
- `{ kind:'stop', unitIds:number[] }`
- Validation rejects non-finite coordinates, empty `unitIds`, more than 200 ids. In `step`, a command may only control units whose `owner` equals the command's `issuer`; ids that are not owned by the issuer, or dead, are ignored silently.

### 1.4 Movement
- Grid A* over map cells (8-neighbour, no corner cutting across blocked cells). Path is smoothed (string-pulling / line-of-sight check) before use.
- Destination outside the map is clamped inside. Destination on a blocked cell or unreachable → go to the nearest reachable cell (BFS from the target outward, bounded).
- Group moves: when several units get one move, give each a distinct goal in a small formation around the clicked point (e.g. spiral of offsets ≥ 2.5 units apart) so they don't pile up.
- Units turn toward their next waypoint at `turnDegPerSec`, accelerate to `top` speed with `accel`, slow down near the final waypoint and stop within 0.5 units.
- Separation: units never end a tick overlapping (radius from tuning, e.g. 1.6): resolve with simple pairwise push-apart, and never push a unit into a blocked cell or off the map.
- Unit y is always `heightAt(x,z)`; units can never be outside the map.
- Stuck rule: a unit with a move order that moved less than 0.05 units per tick for `STUCK_TICKS` re-plans its path; after 3 re-plans it stops and its order becomes idle.

### 1.5 Combat
- Each tank has one weapon (from its data row). The turret rotates toward its target at `turretTurnDegPerSec` independently of the hull. It fires only when the turret is within 5° of the target bearing, the target is within range, and `reloadLeft <= 0`. `fireOnMove: false` means it doesn't fire while its speed > 0.1.
- Target selection: an explicit attack order's target, else the nearest enemy within range (auto-engage). An attack order on a target out of range moves the unit toward it (re-path every 20 ticks).
- Line of sight: direct fire is blocked if the terrain between muzzle (unit y + 1.5) and target (target y + 1) rises above the line at any sample point (sample every cellSize/2).
- Projectiles are sim entities: `{ id, owner, x,y,z, vx,vy,vz, damage, ttl }`, travel at `projectileSpeed`, and are aimed at the target's position with an angular error from `accuracy` drawn from the seeded RNG (accuracy 1 = perfect). A projectile hits the first unit (any owner except the shooter's own units) whose radius it passes within, or the terrain, or expires. Splash damage applies to all units within `splashRadius` of the impact, own units included.
- Damage = max(1, damage − armor). HP never below 0. A unit at 0 HP is removed at the end of that tick and leaves a `wrecks` entry `{x,z,ttl}` that disappears after 10 s.
- Win/lose for this skirmish: when one side has no units left, `world.result` becomes `{ winner: PlayerId }`; when both lose their last unit on the same tick, `{ winner: null }` (draw). After a result, `step` keeps advancing tick but ignores commands.

### 1.6 Determinism and saves
- Everything above uses only the seeded RNG and integer tick time. `hashWorld` must cover units, projectiles, wrecks, result.
- WP-01 save/load must round-trip the new state (the map is regenerated from the seed).

## 2. Rendering (src/render)
- Terrain mesh from the heightmap, vertex-coloured by height and slope (low = dusty olive, high = grey rock, blocked cells visibly darker/rockier). Map edge shown with a thin border.
- One tank model instance per unit, cloned from the loaded PoC tank. In the glb, the turret parts are separate root-level nodes: `Turret, Mantlet, Barrel, Brake, Hatch, Sensor, Lens, Rack, Antenna`. Re-parent them under a turret pivot `Object3D` placed at glTF position (x=-0.3, z=0) (keep their world positions when re-parenting) and rotate the pivot for turret heading. The barrel points along +X in the model. Hide the node named `Plane` (it's a ground plane from the render setup). Scale the model to a sensible size against the unit radius.
- Player 2's tanks get a red tint (clone materials and multiply the base colour), player 1's keep their colours.
- Position, hull heading and turret heading are interpolated between the previous and current sim state using `alpha` from the fixed-step loop.
- Selected units: a ground ring. Damaged or selected units: a small health bar above them (sprite or HTML overlay; must stay readable at all zooms).
- Projectiles drawn as short bright tracers; impacts show a quick flash; destroyed units are replaced by a dark wreck (the model darkened and lowered) until the wreck expires.
- Move order feedback: a marker pulse on the ground where the order landed.
- Shadows: one directional light whose shadow camera follows the camera target with a small frustum (≈ 60×60 units), 1024 map. Remove the WP-01 200×200 shadow frustum.
- Keep the WP-01 render stats and add `units: number` drawn.

## 3. Camera (src/render/camera.ts, pure maths testable in Node where possible)
- RTS camera with a target point on the ground, a distance (zoom), a yaw, and a pitch that goes from ~35° when zoomed in to ~80° (near top-down) when zoomed out, smoothly.
- Pan: WASD, arrow keys, mouse at screen edge (16 px band, on by default, can be toggled by a `setEdgeScroll(bool)` function — settings UI is not in scope), and one-finger drag on the ground (touch) which keeps the grabbed ground point under the finger.
- Zoom: mouse wheel (zoom toward the cursor point), two-finger pinch. Clamp distance to [12, 140].
- Rotate: Q/E, middle-mouse drag, two-finger twist.
- Pan speed scales with zoom distance. The camera target is clamped inside the map; the camera is always at least 3 units above the terrain beneath it.

## 4. Input (src/ui/input.ts) — one module that turns pointer/keyboard events into commands via the App
Desktop:
- Left click own unit: select (replace). Shift+left click: toggle in selection. Left drag on ground (> 6 px): box select own units (screen-space rectangle on projected unit positions). Left click empty ground: deselect.
- Right click ground with a selection: `move` there. Right click an enemy unit: `attack`. Shift+right click: queued move (append waypoint).
- `S`: stop. Ctrl+1–5 assign group, 1–5 select group.
Touch:
- Tap own unit: select. Tap ground with selection: move. Tap enemy with selection: attack. Two-finger tap: deselect all. Long-press (≥ 400 ms) then drag: box select. One-finger drag: pan. Pinch/twist: zoom/rotate.
- Ground picking must raycast against the actual terrain mesh (not a flat plane), so orders land where clicked at every zoom, pitch and yaw.
- Unit picking: nearest unit whose screen-space projected centre is within 24 px (touch: 36 px), preferring own units for selection taps and enemy units for orders.
- The HUD buttons still work and touches/clicks on HUD elements never reach the map.

## 5. UI changes (src/ui)
- The `inGame` screen becomes full-screen: canvas fills the viewport; the title text is removed; the Pause button and a small top bar overlay the canvas (top bar: "Your tanks: N · Enemy tanks: M").
- Add on-screen buttons (touch-friendly, also clickable): Stop, Deselect. Register them in the control inventory like all others.
- When `world.result` is set, go to the `results` screen showing "Victory", "Defeat" or "Draw", with buttons Play again (starts a fresh skirmish) and Title.
- Starting a skirmish from `skirmishSetup` → `loading` → `inGame` creates a fresh world each time.

## 6. Test hook additions (test builds only)
`units()` → array of `{id, owner, x, z, hp, selected}`; `worldToScreen(x,z)` → `{x,y}` CSS pixels of that ground point (using the real camera); `selection()` → ids; `camera()` → `{targetX, targetZ, distance, yaw, pitch}`; `stepUntil(predicate-name, maxTicks)` is NOT allowed (no back doors) — tests advance by waiting real time or by game speed. Add `setSimSpeed(multiplier)` (1–8) that scales elapsed time fed to the fixed-step loop, test builds only.

## 7. Acceptance tests (IDs)

Sim (Vitest, node):
- `MAP-01` same seed → identical heights; different seeds differ.
- `MAP-02` start areas are flat (max slope below MAX_SLOPE in a 10-unit radius) and connected: A* finds a path between the two starts.
- `MOVE-01` a single tank ordered to a reachable point arrives within 0.5 units in under (distance / top speed × 2 + 5) seconds of sim time.
- `MOVE-02` a tank ordered to a point behind the ridge goes around it (path length > straight-line distance, never enters a blocked cell on any tick).
- `MOVE-03` orders outside the map are clamped; no unit is ever outside the map over 5,000 ticks of random move orders (seeded).
- `MOVE-04` 12 tanks ordered to one point: after settling, no two overlap (centres ≥ 2×radius − 0.05 apart) and none is stuck with an active order.
- `MOVE-05` a destination inside a blocked area → unit stops at the nearest reachable cell.
- `MOVE-06` commands for units the issuer doesn't own change nothing.
- `CMB-01` turret turns at its turn rate independently of the hull (assert turret heading change per tick ≤ rate × dt while hull heading is unchanged).
- `CMB-02` a tank won't fire until its turret is aligned and its reload elapsed; reload interval matches `reloadSec` within one tick.
- `CMB-03` damage = max(1, damage − armor); HP never negative; a unit at 0 HP is removed and leaves a wreck that expires after 10 s.
- `CMB-04` a target behind the ridge cannot be hit by direct fire (no projectile spawned, or every projectile hits terrain) while one in the open can.
- `CMB-05` accuracy < 1 produces some misses over 200 shots (seeded) and accuracy 1 produces none against a stationary target in range.
- `CMB-06` splash hits every unit in its radius including the shooter's own side.
- `CMB-07` 4 vs 4 with player 1 ordered to attack-move into player 2: the match ends with a result within 10 minutes of sim time; destroying all enemy units yields `{winner:1}`; simultaneous last kills yield a draw (construct that case).
- `DET-01` a full 4v4 battle with a scripted command list is bit-identical (same `hashWorld`) across two runs, and across a save/load at tick 600.

Camera (Vitest, node, pure maths):
- `CAM-01` target clamps inside the map; distance clamps to [12,140]; pitch interpolates between its limits with zoom.
- `CAM-02` camera never goes below terrain + 3 at any yaw/zoom on the generated map (sample 1,000 positions).

Browser (Playwright, phone/tablet/desktop):
- `INP-01` For 5 sample ground points (including near map corners) at 3 different zoom/yaw settings: select a tank, right-click (desktop) or tap (touch) at `worldToScreen(p)`, and the resulting move target lands within 1.0 unit of `p` (read the unit's order/path end from `units()`; expose the order target in `units()` as `orderX, orderZ`).
- `INP-02` box-select covering 2 of the 4 own tanks selects exactly those 2; it never selects enemy tanks.
- `INP-03` clicking/tapping an enemy with a selection issues an attack; within 20 s of sim time at speed 8 the enemy's hp has dropped.
- `INP-04` camera: WASD/arrow (desktop) or one-finger drag (touch) moves the target; wheel/pinch changes distance; Q/E or twist changes yaw; panning hard into each edge keeps the target inside the map.
- `INP-05` touches on the Pause/Stop/Deselect buttons never issue map orders (selection and orders unchanged except for the button's own effect).
- `PLAY-01` full flow: title → skirmish → loading → inGame; at speed 8, order all player tanks to attack the enemy; the results screen appears with Victory or Defeat within 90 s real time; Play again starts a fresh match with 4 v 4.
- `VIS-01` in-game screenshot is not blank, shows more than 20 distinct colours, and `renderStats().units` = 8 at start.

Update `docs/requirements.md`, `tests/controls.inventory.json`, `docs/decisions.md` and `docs/progress.md`.

## 8. Output format
Same as WP-01: full files only, `<<<FILE path>>> … <<<END FILE>>>`, `<<<DELETE path>>>`, then one `<<<REPORT>>> … <<<END REPORT>>>`
with: requirement table (ID → test → confidence → why a stub fails), self-review defects found and fixed, APIs you're unsure of, deviations, file list.
Do not write `package-lock.json`, `public/assets/**` binaries, or anything under `android/`.
