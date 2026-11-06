# Fix round 1

## Fixes

### 1. Lint errors (13 → 0)

- **`src/app.ts:5`** — `ScreenId` was imported but never referenced. Removed it from the import.
- **`src/assets/threeDecoders.ts:17`** (`prefer-promise-reject-errors`) — the GLTF parse error callback forwarded a possibly-non-Error rejection reason. Wrapped it: `reject(error instanceof Error ? error : new Error(String(error)))`.
- **`src/assets/threeDecoders.ts:28`** (`require-await`) — `audio` was declared `async` but never awaited. Changed to `(buffer) => Promise.resolve(buffer)`.
- **`src/platform/kv.ts`** (`require-await` × 8) — `MemoryKvStore` and `WebKvStore` methods were `async` with no `await`. Rewrote them as plain methods returning `Promise.resolve(...)` / `Promise.reject(...)` (with a `toError` helper so non-Error throws become rejection reasons). Quota detection/extraction is unchanged.
- **`src/platform/watchdog.ts:133,143`** (`no-unsafe-assignment`) — `ErrorEvent.error` and `PromiseRejectionEvent.reason` are typed `any` in `lib.dom`, and assigning to a `const` triggered the rule. Replaced with `const rawError: unknown = errorEvent.error;` / `const reason: unknown = rejection.reason;` and narrowed with `instanceof Error` before building the report.

### 2. E2E determinism

- **`freezeSim` semantics decided.** `freezeSim(ms)` keeps its exact meaning: a timed freeze that suppresses sim steps **and** sim watchdog beats, used only by WD-04 to make the watchdog trip within a bounded window. It is not a general-purpose "pause".
- **New hook method `pauseSim(paused)`.** Added to `TestHook` (`src/testhook/testhook.ts`, `tests/e2e/helpers.ts`) and to `App` (`pauseSim(paused: boolean)`) which delegates to the same UI-pause path the pause screen now uses (`ScreenContext.pauseSim`). Internally `App` now tracks `uiPaused` and `lifecyclePaused` separately and derives the effective `paused` flag (`applyPauseState`), so the pause screen and the visibility lifecycle don't clobber each other. `pause()`’s `watchdog.setSuspended(true)` + `stopLoop()` and `resume()`’s `setSuspended(false)` + `startLoop()` are preserved.
- **`src/ui/screens.ts` pause screen** now actually pauses the sim: `ctx.pauseSim(true)` on mount, `ctx.pauseSim(false)` in its unmount cleanup (which the router runs when the pause overlay is popped or replaced). This makes the "same path the pause screen uses" true.
- **HOOK-02 rewritten** to use `pauseSim(true)` instead of `freezeSim`. Root cause of the flake: `freezeSim(1000)` only guaranteed "no sim steps for the next second"; each `page.evaluate` round-trip cost tens to hundreds of ms, so on some runs the 1 s budget expired mid-test, the sim resumed, ~2 extra ticks ran (counter 90 → 110), and the `afterInvalid === beforeInvalid` assertion tripped. With `pauseSim`, the sim is genuinely stopped (rAF cancelled, `paused` flag set), and the counter cannot move. Test amount was raised to 1000 so that even if the command were silently dropped the RNG-driven counter could not reach the threshold within the 5 s poll budget — the assertion is now strict, not permissive.
- **UI-05 root cause: stale watchdog beats.** After the async renderer chunk resolves and `startLoop()` runs, the watchdog constructor's `lastBeat` (set at page load) could already be >2 s old — the first frames run at ~60 Hz so no sim step (and thus no `beat('sim')`) happens until 50 ms elapsed. On the tablet viewport (higher resolution → slightly slower render startup) the very first `check()` crossed the 2 s threshold and `onFreeze` navigated to `recovery`, which hides the `inGame` base (`visibility: hidden`) and removed the Pause button from the accessibility tree before the click could land. Fix: `startLoop()` now calls `watchdog.beat('sim')` and `watchdog.beat('render')` before starting the interval, so every loop start (initial mount, resume from lifecycle pause, resume from UI pause) begins a fresh watchdog window.

### 3. Bundle split

`src/app.ts` no longer statically imports `RenderView`. `App.attachRenderer` now returns `Promise<RendererHandle>` and does `import('./render/renderer')` — a lazy chunk containing three.js and the decoders. `ScreenContext.attachRenderer`, the `inGame` screen, and the unit-test mock were updated to the async shape (screen awaits, then either stores the handle or renders the "3D rendering is unavailable" message). To keep the build warning-free with a lazily-loaded `three` chunk (~700 kB minified) the `vite.config.ts` `build.chunkSizeWarningLimit` was raised to 1000 with an inline comment. The main chunk no longer contains three.js, and `dist/index.html` remains relative.

### 4. Ripple changes

- `src/ui/router.ts` — `ScreenContext.attachRenderer` type is now `(canvas) => Promise<RendererHandle>`; added `pauseSim: (paused: boolean) => void` to the context.
- `src/ui/screens.ts` — `inGame` handles the async renderer (and shows the fallback message on rejection); pause screen uses `ctx.pauseSim(true|false)` on mount/unmount.
- `tests/unit/ui.test.ts` — mock context updated with `pauseSim` and `Promise.resolve`-returning `attachRenderer`; imports `RendererHandle` for the typed promise.
- `tests/e2e/helpers.ts` — `TestHook` interface gained `pauseSim(paused: boolean): void`.
- `tests/e2e/game.spec.ts` — HOOK-02 only.

## Files changed

- `vite.config.ts` — `chunkSizeWarningLimit: 1000` for the three.js lazy chunk.
- `src/app.ts` — dynamic renderer import, `pauseSim`, watchdog beat reset in `startLoop`, split `uiPaused`/`lifecyclePaused`, removed unused import.
- `src/assets/threeDecoders.ts` — wrap rejection reason, non-async audio decoder.
- `src/platform/kv.ts` — sync methods returning `Promise.resolve`/`Promise.reject`, `toError` helper.
- `src/platform/watchdog.ts` — `unknown` narrowing in error capture.
- `src/ui/router.ts` — `attachRenderer` returns `Promise`, `pauseSim` added to context.
- `src/ui/screens.ts` — async inGame attach, pause screen truly pauses the sim.
- `src/testhook/testhook.ts` — `pauseSim` on the hook.
- `tests/unit/ui.test.ts` — mock context for new `ScreenContext` shape.
- `tests/e2e/helpers.ts` — `pauseSim` in the `TestHook` type.
- `tests/e2e/game.spec.ts` — HOOK-02 rewritten deterministically.

## Expected results

- `npm run lint` — 0 errors, 0 warnings.
- `npm test` — 52/52 pass (no test-code changes to sim/assets/data/saves/watchdog/lifecycle/config/lint suites).
- `npm run build` — no chunk-size warning; three.js in its own lazy chunk.
- `npm run test:e2e` — HOOK-02 and UI-05 both deterministic; the desktop-only HOOK-01 remains skipped on phone/tablet as designed.

## Remaining uncertainty

- `@capacitor/filesystem` `readdir` result typing is still cast defensively; not exercised by unit tests (as allowed).
- The PNG screenshot decoder in `tests/e2e/helpers.ts` still assumes Playwright emits 8-bit RGB/RGBA non-interlaced PNGs — unchanged, and REND-01 passed in all three viewports on the last run.
