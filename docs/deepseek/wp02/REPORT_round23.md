# Fix report

## Root cause

`[INP-05]` is not a test bug — it is the product behaving as written on slow hardware. Playwright found the Pause button, found it visible/enabled/stable, dispatched the click, and then the *page* never processed the input: a `click` is delivered on the main thread, and on the CI runner (2 vCPU, SwiftShader, 1920×1080, shadows on) each frame occupies that thread for a second or more. The queue simply never drains inside the test's 30 s budget.

The SOR already required the remedy: "A dynamic quality setting lowers effects, shadows and resolution automatically when frame rate drops below budget." That was missing, so a slow device stayed slow.

## What was added

**`src/render/quality.ts` (new, pure — no DOM, no three.js).**
- `QUALITY_LADDER`: full → half shadow map (×0.5) → shadows off → pixel-ratio cap 1 → 0.75 → 0.5 (`MIN_PIXEL_RATIO`), ordered by cost. Shadows go first because they cost an extra full terrain pass; resolution is reduced afterwards for the remaining headroom.
- `QualityController`: a 1 s rolling average over injected frame times. Above 50 ms average it accumulates toward a step down; above 25 ms it holds. Steady slow frames for 1 s step down; steady fast frames for 3 s step up. `minChangeIntervalMs` (1 s) is an absolute floor between any two changes, and each change clears the measurement window, so one bad second can cost at most one level.
- `qualityViewFor(level, basePixelRatio)` maps a level to the concrete `{ level, pixelRatio, shadows }` the renderer is actually using, so a test can assert the drop without knowing the device DPR.

**`src/render/renderer.ts`.**
- `render()` measures the frame delta against the previous rendered frame and feeds it to the controller; a change applies once.
- `applyQuality()` sets `setPixelRatio`, toggles `shadowMap.enabled` / `light.castShadow`, resizes and disposes the shadow render target (so three allocates a new size), and recompiles materials when the shadow flag flips.
- Frame gaps larger than `MAX_FRAME_SAMPLE_MS` (2 s) are ignored: a pause, a hidden tab or a navigation is not a rendering-cost signal, and treating it as one would degrade quality exactly when the player is about to resume.
- `quality()` returns the current `{ level, pixelRatio, shadows }`.

**Hook.** `App.quality()` → `TestHook.quality()` → `TestHook`/`TestHook` type in `tests/e2e/helpers.ts`. Read-only; nothing in the game reads it.

**`PERF-01` (`tests/unit/quality.test.ts`).** Five cases over synthetic frame times: sustained 100 ms frames step down 1 → 2 → 3 → 4 → 5 one level at a time with ≥1000 ms between changes; 10 ms frames step back up 2 → 1 → 0 with the same spacing; 35 ms frames (between the two thresholds) never change anything; the ladder halves the shadow map, then disables shadows, then reaches exactly 0.5 while its caps stay non-increasing; and non-positive/NaN samples are ignored.

## Why this fixes CI rather than hiding it

The degraded state is *materially* cheaper: shadows are a second full scene pass at 1024² over 1920×1080, and pixel ratio 0.5 quarters the fragment count. Within ~3 s of sustained slow frames the renderer is drawing at a fraction of the original cost, so the main thread drains between frames and input — including `pause.click()` — is delivered well inside the budget. `[INP-05]` is unchanged precisely because it encodes the real requirement: on a slow device, HUD buttons must still respond.

No test was skipped or weakened, no timeout was raised to paper over this, no lint/tsconfig rule relaxed and no dependency added. `docs/requirements.md`, `docs/decisions.md` and `docs/progress.md` record `PERF-01` and the ladder/threshold reasoning.
