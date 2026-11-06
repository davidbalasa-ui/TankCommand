# WP-01 review: DeepSeek V4.1 Flash scaffolding package

Reviewer: Claude, 2026-10-27. Spec: `PACKAGE_SPEC.md`. DeepSeek's own reports: `REPORT_round1.md`, `REPORT_round2.md`.

## Verdict: keep it as the base

The output is a clean, working foundation. It does what the spec asked, the tests are real (they check
state, not just "no crash"), and the remaining problems are small, local and listed below. Starting over
would cost more than fixing them.

## How it was run

| Round | Input | Output | Wall time |
|---|---|---|---|
| 1: build the package | 8.7k tokens (spec) | 137k tokens (96k reasoning), 61 files | ~10 min |
| 2: fix from real test output | 52k tokens | 67k tokens (52k reasoning), 11 files | ~5 min |

DeepSeek cannot run code, so "self-validation" was a written report per requirement, then one fix round
fed with the real lint and e2e output from this sandbox.

## Results from actually running it

| Check | Round 1 | Round 2 |
|---|---|---|
| `npm run typecheck` | pass | pass |
| `npm test` (unit, 52 tests) | pass | pass |
| `npm run lint` (zero warnings) | 13 errors | pass |
| `npm run credits:check`, `coverage:req` | pass | pass |
| `npm run build` | pass, 702 kB chunk warning | pass, three.js split into a lazy chunk (main 81 kB) |
| `npm run test:e2e` (3 viewports) | 20 pass, 2 flaky | 21 pass, 1 fail (see below), then 22 pass after one fix by Claude |
| `npx cap add android` + `npm run cap:sync` | not run | pass |

The round-2 e2e failure was a real DeepSeek bug: the HOOK-01 test started `vite preview` through `npx`
and killed only the `npx` wrapper, leaving an orphaned server on port 4174. Every later run then failed.
Claude fixed it in `tests/e2e/production.spec.ts` (spawn vite directly, wait for exit). Three full e2e runs
were done before the fix to check for flakiness; after the fix the full suite passed.

Its root-cause analysis in round 2 was good: it correctly traced the tablet UI-05 failure to stale watchdog
beats tripping the freeze detector while the renderer chunk loaded, and fixed the cause rather than adding waits.

## What is solid

- Spec compliance is high: exact versions, scripts, folder layout, sim isolation lint rule (proven by a test),
  relative build paths, Capacitor config, credits generation with a staleness check, requirement-ID coverage script.
- The sim shell is deterministic and genuinely headless (`tsconfig.sim.json` has no DOM lib).
- Asset manifest validation covers every rejection case (non-commercial and no-derivatives licences rejected).
- The loader dedupes, refcounts, retries failures and checks byte size; the real PoC tank loads through it in the browser.
- Save envelope never throws on garbage (1,000-case fuzz), detects checksum and version problems.

## Problems found in review (none block building visuals)

| # | Where | Problem | Severity |
|---|---|---|---|
| 1 | `src/app.ts` | Watchdog spec deviation not reported: the recovery screen opens at the 2 s freeze mark, not 5 s, and no freeze report is recorded. `onRecover` does nothing. | Medium |
| 2 | `src/app.ts`, `src/platform/watchdog.ts` | The watchdog runs on the main thread, so a real JS hang (infinite loop) blocks the watchdog too. Only stalls where the thread is free are caught. This was a gap in the spec; it needs a Web Worker or native-side heartbeat later. | Medium (design) |
| 3 | `src/platform/saves.ts` | Autosave rotation cursor resets to `auto-0` on every app launch, so after a relaunch the newest autosave can be overwritten first. | Medium |
| 4 | `src/platform/saves.ts` | `SaveManager.load` throws a plain `Error` on a bad save instead of returning the typed reason; callers lose `corrupt` vs `incompatible`. | Low |
| 5 | `src/assets/loader.ts` | If an asset is released to zero while still loading, the decoded asset is never disposed (GPU memory leak). A failed load also deletes the cache slot by id, which could drop a newer entry. | Low |
| 6 | `src/app.ts` | The sim only advances while the 3D view is attached, so sim and renderer are still coupled. Fine for a shell; must change when the sim core lands. | Low |
| 7 | `eslint.config.js` | Tests and scripts aren't linted; the config carries two virtual file paths that exist only for the LINT-02 test. | Low |
| 8 | `src/render/renderer.ts` | The shadow camera covers 200×200 units at 2048 px, which shows as a visible lighter square on the ground and is too costly for phones. The tank doesn't cast shadows. Expected to be redone with the visuals work. | Low |
| 9 | `src/assets/loader.ts` | `load` returns a model/texture/audio union, so callers cast. A per-kind typed API would be cleaner. | Low |

## Recommended next steps

1. Fix #1, #3 and #4 before the save and recovery screens are built for real (about an hour of work).
2. Start the visuals work on this base: renderer, terrain, camera rig, and the asset pipeline from `blender-poc/`.
3. Schedule #2 with the simulation-core work.
