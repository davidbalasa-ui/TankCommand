# Decisions

| Date | Question | Choice | Evidence | Who |
| --- | --- | --- | --- | --- |
| 2026-10-27 | Separate Vitest config or embed in Vite config? | Separate `vitest.config.ts`. | Keeps Vite build flags separate from unit-runner settings. | DeepSeek (WP-01) |
| 2026-10-27 | How should large native saves and small settings be separated? | Native keys prefixed `setting.` use Preferences; other keys use Filesystem under `saves/<key>.json`. | Matches the platform storage split without changing the public KvStore interface. | DeepSeek (WP-01) |
| 2026-10-27 | How is settings treated when opened from pause? | Settings is an overlay when opened from pause and a normal screen from title. | Required by the overlay/back acceptance flow. | DeepSeek (WP-01) |
| 2026-10-27 | How is the credits file made available to the in-app screen? | Generate both `CREDITS.md` and `public/CREDITS.md` from the same script. | The screen can fetch a static local copy without importing build-specific raw text. | DeepSeek (WP-01) |
| 2026-10-27 | How is the test hook excluded from production builds? | Conditional dynamic import behind `__TEST_HOOK__`. | Rollup removes the dead branch and the test asserts the marker is absent from built JS. | DeepSeek (WP-01) |
| 2026-10-27 | How are autosave slots ordered? | Internal rotating cursor plus `latestAutosave` using the manager and saved timestamps. | Gives deterministic rotation in tests while remaining recoverable after reload. | DeepSeek (WP-01) |
| 2026-10-27 | How is the production-build Playwright check isolated? | Runs only in the desktop project and builds into a temp directory. | Avoids concurrent preview-server and out-dir collisions. | DeepSeek (WP-01) |
| 2026-11-03 | Where do WP-02 game rules live? | Entirely in `src/sim`, with plain `SimUnitType` data passed in by the app. | Keeps the sim headless and prevents JSON/asset imports in sim modules. | DeepSeek (WP-02) |
| 2026-11-03 | How is the map saved? | Save payloads store the seed only and regenerate heights with `generateMap`. | Meets the no-heights-in-saves rule and keeps saves small. | DeepSeek (WP-02) |
| 2026-11-03 | How are group move goals formed? | Golden-angle spiral offsets spaced by `FORMATION_SPACING`. | Gives distinct goals without a table and satisfies the non-pileup rule. | DeepSeek (WP-02) |
| 2026-11-03 | How are HUD clicks kept off the map? | Input listeners attach to the canvas; HUD buttons live in sibling overlays. | Buttons never bubble through the canvas regardless of pointer type. | DeepSeek (WP-02) |
| 2026-11-03 | How does Play again work? | Results routes to `loading`, which the App intercepts to build a fresh 4v4 skirmish. | Reuses the existing loading transition and guarantees a new skirmish. | DeepSeek (WP-02) |
| 2026-11-03 | How are camera test settings applied? | Test builds expose `setCamera(partial)` in the hook. | Lets pick tests use the real camera at several zoom/yaw values without back-door stepping. | DeepSeek (WP-02) |
| 2026-11-04 | What happens when an attack order's target dies? | The order stays active against the nearest surviving enemy. | Idle units only auto-engage inside weapon range, so a squad that stopped at the edge of range would otherwise park outside every survivor and the skirmish would never resolve. | DeepSeek (WP-02) |
| 2026-11-04 | Does the stuck rule apply to a tank holding position to fire? | No. `isHoldingFirePosition` clears the stuck counter and re-plan budget while an attack order is in range with line of sight. | A stationary firing tank registers `moved < MOVE_EPS` every tick, so it would spend its three re-plans and lose the attack order, after which it only auto-engages inside weapon range and never closes on the survivors. | DeepSeek (WP-02) |
