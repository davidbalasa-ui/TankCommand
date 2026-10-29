# WP-01 self-validation report

## 1. Requirement table

| ID | Test file(s) and title(s) | Confidence | Why a stub would fail |
| --- | --- | --- | --- |
| SIM-01 | `tests/unit/sim.test.ts` — `[SIM-01] same seed same command list produces identical hash after 10000 steps` | High | Two independent 10,000-step runs are hashed; a stub or missing RNG state would diverge. |
| SIM-02 | `tests/unit/sim.test.ts` — `[SIM-02] different seeds produce different hashes after 100 steps` | High | Compares hashes from seeds 1 and 2; constant/stubbed RNG would collide. |
| SIM-03 | `tests/unit/sim.test.ts` — `[SIM-03] step does not mutate its input and accepts frozen input` | High | Uses a frozen input and deep-equal before/after; mutation would throw or change the object. |
| SIM-04 | `tests/unit/sim.test.ts` — `[SIM-04] debug.addCounter applies only on its tick and past ticks are ignored` | High | Compares against baseline steps with and without the command. |
| SIM-05 | `tests/unit/sim.test.ts` — `[SIM-05] validateCommand rejects unknown kind, fractional tick, infinite amount, missing issuer and null` | High | Each malformed value is rejected by zod; a permissive stub returns a command. |
| SIM-06 | `tests/unit/sim.test.ts` — `[SIM-06] fixed-step loop accumulates, caps and ignores invalid elapsed time` | High | Checks exact step counts and alpha; a no-op loop fails immediately. |
| SIM-07 | `tests/unit/sim.test.ts` — `[SIM-07] Rng is reproducible, state resumes, and int upper bound is exclusive` | High | Compares 1,000 values, resumes from saved state, and draws 100,000 integers. |
| ASSET-01 | `tests/unit/assets.test.ts` — `[ASSET-01] real public asset manifest validates` | High | Parses the real committed manifest. |
| ASSET-02 | `tests/unit/assets.test.ts` — eight `[ASSET-02] ...` cases plus `[ASSET-02] manifest errors expose a stable error class` | High | Each rejection case asserts a thrown message containing the offending id. |
| ASSET-03 | `tests/unit/assets.test.ts` — `[ASSET-03] every real manifest file exists and has the recorded byte size` | High | Reads the actual file and compares `statSync().size` with `bytes`. |
| ASSET-04 | `tests/unit/assets.test.ts` — `[ASSET-04] concurrent loads for one id share one fetch` | High | Five concurrent loads must leave the fetch spy called once. |
| ASSET-05 | `tests/unit/assets.test.ts` — `[ASSET-05] failed loads are not cached and retry can succeed` | High | First fetch fails, second succeeds, and fetch call count is 2. |
| ASSET-06 | `tests/unit/assets.test.ts` — `[ASSET-06] refcount keeps cache until the final release and disposes once` | High | Checks no dispose after first release, dispose once after second, and a refetch after eviction. |
| ASSET-07 | `tests/unit/assets.test.ts` — `[ASSET-07] preload reports each id, rejects with all failures and caches successes` | High | Aggregates one failure while successful assets remain cached. |
| ASSET-08 | `tests/unit/assets.test.ts` — `[ASSET-08] byte size mismatch rejects with AssetLoadError` | High | Fetches 3 bytes for a 4-byte entry and asserts the typed error. |
| ASSET-09 | `tests/unit/assets.test.ts` — `[ASSET-09] credits check passes on committed files and fails when the manifest changes` | High | Runs the real script on committed files, generates in a temp dir, then mutates the temp manifest and expects failure. |
| ASSET-10 | `tests/e2e/game.spec.ts` — `[ASSET-10] the real PoC tank loads through the registry, loader and GLTF decoder` | High | Reads `renderStats().loadedModels` and requires the real asset id and mesh count > 1. |
| DATA-01 | `tests/unit/data.test.ts` — `[DATA-01] placeholder table loads against the real asset manifest` | High | Loads the committed table with the real registry. |
| DATA-02 | `tests/unit/data.test.ts` — seven `[DATA-02] ...` cases | High | Each specified malformed row is rejected. |
| DATA-03 | `tests/unit/data.test.ts` — `[DATA-03] placeholderReport lists placeholder rows and drops tuned rows` | High | Checks both placeholder ids and removal after changing one source. |
| SAVE-01 | `tests/unit/saves.test.ts` — `[SAVE-01] save after 500 steps and continue 500 more matches an uninterrupted run` | High | Save/load is followed by 500 more steps and hash comparison. |
| SAVE-02 | `tests/unit/saves.test.ts` — `[SAVE-02] decodeSave returns correct reasons for malformed input and never throws` | High | Covers random, truncated, checksum-flipped, schema-999, `{}`, and 1,000 fuzz cases. |
| SAVE-03 | `tests/unit/saves.test.ts` — `[SAVE-03] autosave rotation keeps exactly three slots and latestAutosave is the fifth` | High | Five autosaves must leave three auto slots and return counter 4. |
| SAVE-04 | `tests/unit/saves.test.ts` — `[SAVE-04] exceeding maxBytes rejects and leaves previous saves intact` | High | Saves one slot, rejects the second, and reloads the first. |
| SAVE-05 | `tests/unit/saves.test.ts` — `[SAVE-05] WebKvStore maps quota failures to StorageFullError` | High | Mocked storage throws a quota-named error. |
| LIFE-01 | `tests/unit/lifecycle.test.ts` — `[LIFE-01] hidden pauses, visible resumes, duplicate pauses collapse, back emits pause plus back` | High | Fake source dispatches visibility and back signals and checks deduplication. |
| WD-01 | `tests/unit/watchdog.test.ts` — `[WD-01] freeze fires once at the threshold, recover once, and a beat starts a new episode` | High | Fake clock checks thresholds, repeat suppression, and a new episode after beats. |
| WD-02 | `tests/unit/watchdog.test.ts` — `[WD-02] suspended mode suppresses freezes and unsuspending resets clocks` | High | Suspended checks produce no freeze; unsuspend resets, then a stall fires. |
| WD-03 | `tests/unit/watchdog.test.ts` — `[WD-03] global error capture records thrown errors and rejected promises` | High | Fake target dispatches error and unhandledrejection events. |
| WD-04 | `tests/e2e/game.spec.ts` — `[WD-04] frozen sim shows the recovery screen with three buttons` | High | Freezes sim and waits for the recovery overlay plus all three buttons. |
| UI-01 | `tests/unit/ui.test.ts` — `[UI-01] every screen mounts and unmounts without leaving nodes behind` | High | Mounts every screen id and checks the holder is empty after unmount. |
| UI-02 | `tests/unit/ui.test.ts` — `[UI-02] overlays stack and back pops settings then pause to inGame` | High | Checks settings as a pause overlay, then back order. |
| UI-03 | `tests/unit/ui.test.ts` — `[UI-03] rapid repeated go to settings mounts only one settings root` | High | Twenty rapid calls must leave one settings root. |
| UI-04 | `tests/unit/ui.test.ts` — `[UI-04] every registered control id is listed in the inventory file` | High | Mounts all screens and fails if a registered id is missing from `tests/controls.inventory.json`. |
| UI-05 | `tests/e2e/game.spec.ts` — `[UI-05] all controls meet touch size and do not overlap across the main flow` | Medium-high | Clicks every listed control in the main flow, checks 44×44 minimum and pairwise overlap. The recovery buttons are event-only and stay on-screen, which matches the spec. |
| LINT-01 | `tests/unit/lint.test.ts` — `[LINT-01] lint script is zero-warning and the flat config exists` | Medium-high | Checks the script flag and config presence; the actual `npm run lint` step is the enforcing command. |
| LINT-02 | `tests/unit/lint.test.ts` — `[LINT-02] sim restrictions fire on sim files and not on render files` | Medium-high | Runs ESLint programmatically on virtual sim/render paths and checks the restricted rule ids. |
| LINT-03 | `tests/unit/lint.test.ts` — `[LINT-03] sim tsconfig excludes the DOM lib` | High | Reads `tsconfig.sim.json` and asserts no DOM lib. |
| REQ-01 | `tests/unit/config.test.ts` — `[REQ-01] requirement coverage passes and fails when an untested id is appended` | High | Runs the real coverage script, then appends `FAKE-99` in a temp copy and expects nonzero. |
| CI-01 | `tests/unit/config.test.ts` — `[CI-01] github workflow runs the full ci and e2e commands` | High | Reads the workflow and checks the required command strings and Node version. |
| CAP-01 | `tests/unit/config.test.ts` — `[CAP-01] capacitor config has the required app id, web dir and no server url` | High | Imports the config and checks fields. |
| BUILD-01 | `tests/e2e/game.spec.ts` — `[BUILD-01] built index uses relative urls and copies public assets` | High | Reads the built `dist/index.html` and copied public assets after the web server build. |
| HOOK-01 | `tests/e2e/production.spec.ts` — `[HOOK-01] production build has no test hook marker or window hook` | Medium-high | Builds into a temp outDir with the test flag unset, greps JS files for the marker, and checks the served page has no window hook. |
| HOOK-02 | `tests/e2e/game.spec.ts` — `[HOOK-02] test hook validates commands and invalid commands change nothing` | Medium-high | Valid command changes the counter; invalid Infinity command returns false and leaves the frozen counter unchanged. |
| REND-01 | `tests/e2e/game.spec.ts` — `[REND-01] canvas is non-blank and frames increase` | Medium | Screenshots the canvas, decodes PNG scanlines, requires > 2 distinct colours, and checks frame growth. |
| REND-02 | `tests/e2e/game.spec.ts` — `[REND-02] hidden page stops frames and resumes without sim-time jump` | Medium-high | Mocks `document.hidden`, checks frame stop/resume and bounds the tick increase. |

## 2. Self-review pass

Defects found and fixed during construction/re-read:

- The legacy `index.html` needed both a delete marker and the new Vite entry. I emitted a delete marker before the replacement file so the new entry is the final state.
- The initial router design would have treated `settings` opened from pause as a replacement screen. I special-cased `settings` as an overlay only when the current screen is `pause` and the base is `inGame`.
- Overlays could have left underlying buttons visible to Playwright, causing false overlap failures. The router now sets lower screens to `visibility: hidden` while an overlay is on top.
- A naive watchdog that reports every stalled channel would fire twice when both sim and render are idle. The implementation suppresses simultaneous channel reports for the same threshold crossing while still allowing a later episode after a beat.
- The test hook must not be present in production. It is only a conditional dynamic import behind `__TEST_HOOK__`, and the production e2e test checks both built JS text and the served window.
- `src/sim` must not use DOM/Node globals. The sim tsconfig uses only `ES2022`, and the ESLint restricted block covers imports, globals, `Math.random`, `Date.now` and `performance`.
- The credits screen needs a browser-fetchable copy. The credits script writes both `CREDITS.md` and `public/CREDITS.md` when using default paths, and `credits:check` checks both.
- The `AssetLoader` cache-entry creation needed to avoid `any` while assigning a promise after constructing the entry. It uses a `Partial<CacheEntry>` plus a narrow cast.
- The save envelope decode path needed to reject schema 999 before checksum validation, and to wrap all parsing in a catch so it never throws. Both are implemented.
- The UI inventory was reduced to the controls that screens actually register, and the e2e flow explicitly clicks every listed control, including the event-only recovery buttons.

Known risks that remain:

- I cannot run the code. The largest remaining uncertainty is exact API surface for `@capacitor/filesystem` `readdir` result typing; I cast the entries to a string-or-`{name}` union so both common shapes typecheck. Native storage is not unit tested, as allowed.
- The PNG decoder in `tests/e2e/helpers.ts` assumes Playwright canvas screenshots are 8-bit RGB/RGBA non-interlaced PNGs. That is the normal Playwright output, but it is the most brittle e2e helper.
- `npm run lint` may surface a type-aware ESLint rule complaint I did not anticipate. The code intentionally avoids `any`, uses `void` for intentionally ignored promises, and keeps restricted rules only on `src/sim`.

## 3. Commands expected to pass

In order:

1. `npm ci`
2. `npm run ci`
3. `npm run test:e2e`

I am least certain about:

- `@capacitor/filesystem` `readdir` result shape in the pinned v8 API.
- `typescript-eslint` project-service behavior for virtual `lintText` paths; `allowDefaultProject` is configured for the two virtual files.
- Playwright `vite preview --outDir` support for the production-build check.
- The PNG screenshot decoder assumptions.

## 4. Deviations

- The legacy `index.html` is both marked for deletion and emitted as the new Vite entry. The spec asked for a delete marker while also requiring the new Vite entry at the same path, so the replacement file is the final state.
- The `settings` screen is an overlay only when entered from `pause`; from `title` it replaces the title screen. This is required by the overlay/back acceptance flow.
- The `recovery` buttons emit custom events and do not themselves navigate, as the spec says they only emit events in this package.
- Extra harmless API surface was added for testing and clarity: `AssetLoader.isCached`, `ScreenRouter.current`, `App.snapshot`, and public `migrations`.

## 5. File list

- `package.json` — pinned dependencies and exact npm scripts.
- `tsconfig.json` — app/test TypeScript config with strict and unchecked-index checks.
- `tsconfig.sim.json` — headless sim config with `ES2022` only.
- `vite.config.ts` — relative base and `__TEST_HOOK__` define.
- `vitest.config.ts` — unit test runner config.
- `playwright.config.ts` — three viewports and test-hook preview server.
- `eslint.config.js` — type-checked lint plus sim restriction block.
- `capacitor.config.ts` — app id, web dir, Android background, splash duration.
- `vercel.json` — static build settings.
- `.gitignore` — build, test and Android ignores.
- `index.html` — Vite entry.
- `public/manifest.webmanifest` — PWA manifest.
- `public/assets/manifest.json` — real one-entry asset manifest.
- `public/CREDITS.md` — browser-served credits copy.
- `CREDITS.md` — generated credits.
- `src/env.d.ts` — Vite types and test-hook flag.
- `src/sim/constants.ts` — tick rate.
- `src/sim/rng.ts` — mulberry32 seeded RNG.
- `src/sim/commands.ts` — command union and zod validation.
- `src/sim/world.ts` — world state, step, snapshot, canonical hash.
- `src/sim/loop.ts` — fixed-step loop.
- `src/sim/index.ts` — sim exports.
- `src/assets/manifestSchema.ts` — asset manifest validation and cross-entry checks.
- `src/assets/registry.ts` — asset registry and unknown-asset error.
- `src/assets/loader.ts` — deduping, refcounted, retrying asset loader.
- `src/assets/threeDecoders.ts` — GLTF, texture and audio decoders plus fallback box.
- `src/data/unitSchema.ts` — unit row schema and cross-field rules.
- `src/data/units.placeholder.json` — two placeholder unit rows.
- `src/data/dataRegistry.ts` — unit table loading and placeholder reporting.
- `src/platform/kv.ts` — memory, web and native KV stores.
- `src/platform/saves.ts` — save envelope, decode reasons, migrations, autosave manager.
- `src/platform/lifecycle.ts` — lifecycle deduplication and real-source binding.
- `src/platform/watchdog.ts` — freeze/recover watchdog and global error capture.
- `src/render/renderer.ts` — three.js renderer, scene, camera, tank load and stats.
- `src/ui/controls.ts` — control inventory and button factory.
- `src/ui/router.ts` — screen ids, transitions, overlays and back behavior.
- `src/ui/screens.ts` — all 15 screens and controls.
- `src/ui/styles.css` — dark layout and touch-size buttons.
- `src/testhook/testhook.ts` — conditional browser test hook.
- `src/app.ts` — app composition, render loop, watchdog and save simulation.
- `src/main.ts` — boot and conditional hook import.
- `scripts/credits.mjs` — credits generator/checker.
- `scripts/req-coverage.mjs` — requirement traceability checker.
- `tests/controls.inventory.json` — all registered control ids.
- `tests/unit/sim.test.ts` — SIM requirements.
- `tests/unit/assets.test.ts` — ASSET requirements.
- `tests/unit/data.test.ts` — DATA requirements.
- `tests/unit/saves.test.ts` — SAVE requirements.
- `tests/unit/lifecycle.test.ts` — LIFE requirement.
- `tests/unit/watchdog.test.ts` — WD unit requirements.
- `tests/unit/ui.test.ts` — UI unit requirements.
- `tests/unit/config.test.ts` — CAP, CI and REQ requirements.
- `tests/unit/lint.test.ts` — LINT requirements.
- `tests/e2e/helpers.ts` — Playwright helpers, controls layout, PNG decoder.
- `tests/e2e/game.spec.ts` — ASSET-10, HOOK-02, REND, WD-04, UI-05, BUILD-01.
- `tests/e2e/production.spec.ts` — HOOK-01.
- `docs/requirements.md` — requirement ID table.
- `docs/decisions.md` — decision log.
- `docs/progress.md` — WP-01 progress entry.
- `README.md` — project, scripts, folders, e2e and Android notes.
- `.github/workflows/ci.yml` — CI workflow.
