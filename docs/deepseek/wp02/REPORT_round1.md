# WP-02 report

## Requirement table

| ID | Test | Confidence | Why a stub fails |
| --- | --- | --- | --- |
| MAP-01 | `tests/unit/map.test.ts` | high | Stub heightmap would not vary by seed or would be non-deterministic. |
| MAP-02 | `tests/unit/map.test.ts` | high | Stub flatten/path would leave the starts unreachable or sloped. |
| MOVE-01 | `tests/unit/movement.test.ts` | high | No movement/path code would never reach the goal. |
| MOVE-02 | `tests/unit/movement.test.ts` | medium | A straight-line stub would enter the ridge or have no path length. |
| MOVE-03 | `tests/unit/movement.test.ts` | high | No clamp would exceed map bounds after random orders. |
| MOVE-04 | `tests/unit/movement.test.ts` | medium | No formation/separation would leave overlaps or active orders. |
| MOVE-05 | `tests/unit/movement.test.ts` | medium | No nearest-reachable resolution would enter or stop far from blocked cells. |
| MOVE-06 | `tests/unit/movement.test.ts` | high | Missing issuer filtering would change the hash. |
| CMB-01 | `tests/unit/combat.test.ts` | high | Stub turret linked to hull would not turn independently. |
| CMB-02 | `tests/unit/combat.test.ts` | medium | No alignment/reload gate would fire on tick one or with wrong interval. |
| CMB-03 | `tests/unit/combat.test.ts` | high | No armor/wreck code fails the damage and expiry assertions. |
| CMB-04 | `tests/unit/combat.test.ts` | medium | No LOS sampling would let ridge shots through. |
| CMB-05 | `tests/unit/combat.test.ts` | medium | No aim error would make inaccurate shots identical to perfect shots. |
| CMB-06 | `tests/unit/combat.test.ts` | high | Splash restricted to enemies would leave the friendly HP unchanged. |
| CMB-07 | `tests/unit/combat.test.ts` | medium | No result evaluation would never set a winner or draw. |
| DET-01 | `tests/unit/determinism.test.ts` | high | Missing serialised units/projectiles or non-seeded RNG would change hashes. |
| CAM-01 | `tests/unit/camera.test.ts` | high | No clamping or pitch interpolation fails direct assertions. |
| CAM-02 | `tests/unit/camera.test.ts` | high | No terrain-clearance adjustment can put the camera below terrain + 3. |
| INP-01 | `tests/e2e/wp02.spec.ts` | medium | Flat-plane or wrong picking would miss the requested ground point at extreme zoom. |
| INP-02 | `tests/e2e/wp02.spec.ts` | medium | No box select or enemy filtering would select the wrong set. |
| INP-03 | `tests/e2e/wp02.spec.ts` | medium | Missing attack command handling leaves enemy HP unchanged. |
| INP-04 | `tests/e2e/wp02.spec.ts` | medium | Missing pan/zoom/rotate handlers fail camera changes and edge clamping. |
| INP-05 | `tests/e2e/wp02.spec.ts` | high | Canvas-level input would issue orders from HUD button presses. |
| PLAY-01 | `tests/e2e/wp02.spec.ts` | medium | No result flow or fresh-world creation fails the full journey. |
| VIS-01 | `tests/e2e/wp02.spec.ts` | high | A blank or unit-less renderer fails colour and unit-count checks. |

## Self-review defects found and fixed

- Fixed the initial `selectTarget` helper stub by replacing it with a real explicit/auto target selector.
- Fixed save round-tripping to regenerate the map from the seed and to serialise units, projectiles, wrecks and result.
- Fixed the initial renderer plan that kept the WP-01 200×200 shadow frustum; replaced it with a 60×60 camera-following shadow frustum.
- Fixed in-game HUD placement so Pause/Stop/Deselect are sibling overlay buttons and never share the canvas pointer target.
- Fixed touch box-select to require the 400 ms long-press before starting a selection rectangle.
- Fixed movement path smoothing to use actual cell centres and blocked-cell sampling rather than straight world coordinates.
- Fixed selection cleanup after units die so dead ids do not remain in `selection()`.
- Fixed the results route to allow `loading`, enabling Play again to build a fresh skirmish.

## APIs I am unsure of

- The exact glTF node hierarchy of `poc_tank.glb` is not inspectable from this environment. The code uses `Object3D.getObjectByName` for the documented root-level turret names and `attach` to preserve world transforms.
- Playwright touch drag/pinch/twist is simulated with `PointerEvent` dispatch because `page.touchscreen` only exposes taps. The real browser path is the same pointer-event handler.
- The camera test hook returns `pitch` in radians (the internal unit); tests only compare it to degree-converted limits.

## Deviations

- `S` is bound to Stop as specified; WASD down movement is therefore available through the Down Arrow rather than the S key.
- `setCamera(partial)` and `setEdgeScroll(bool)` are additional test-only/host helpers beyond the explicitly listed hook additions.
- `sendCommand` pulses the move marker from the App so test-hook-issued moves also provide feedback.

## File list

New:
- `src/sim/tuning.ts`
- `src/sim/types.ts`
- `src/sim/map.ts`
- `src/sim/pathfinding.ts`
- `src/render/camera.ts`
- `src/ui/input.ts`
- `tests/unit/simHelpers.ts`
- `tests/unit/map.test.ts`
- `tests/unit/movement.test.ts`
- `tests/unit/combat.test.ts`
- `tests/unit/determinism.test.ts`
- `tests/unit/camera.test.ts`
- `tests/e2e/wp02.spec.ts`

Modified:
- `src/sim/commands.ts`
- `src/sim/world.ts`
- `src/sim/index.ts`
- `src/sim/loop.ts`
- `src/platform/saves.ts`
- `src/render/renderer.ts`
- `src/app.ts`
- `src/ui/router.ts`
- `src/ui/screens.ts`
- `src/ui/styles.css`
- `src/testhook/testhook.ts`
- `tests/e2e/helpers.ts`
- `tests/controls.inventory.json`
- `docs/requirements.md`
- `docs/decisions.md`
- `docs/progress.md`
