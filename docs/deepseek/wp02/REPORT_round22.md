# Fix report

## 1. The watchdog showed the recovery screen at the 2 s *freeze* mark (product bug — the root cause of `[INP-05]`, and a real bug on low-end devices)

`App` wired `onFreeze` to `this.router.go('recovery')`. The router mounts `recovery` as a **full-screen overlay and hides the base screen**, so the in-game HUD — including the Pause button — disappears. On GitHub Actions (2 vCPU, SwiftShader at 1920×1080) a single frame routinely exceeds 2 s, so the freeze detector fired during ordinary play and `[INP-05]`'s `pause.click()` then waited forever on a hidden button. WP-01 §5.4 says the 2 s threshold only records a report and the recovery screen is the 5 s threshold — so this was wrong on its own terms, and it would have hit low-end phones exactly the same way.

Fixed in `src/app.ts`:
- `onFreeze` now only stores the report in `lastFreeze` (exposed read-only as `App.lastFreezeReport()`, and through the test hook).
- `onRecover` performs the `router.go('recovery')` navigation.
- The report is cleared when a fresh skirmish starts, so it always describes the current match.

## 2. The render channel was not clocked from the frame start (product bug)

`beat('render')` ran *after* `fixed.advance(...)`, i.e. after up to 20 fixed steps. A frame that spent its budget in the sim looked identical to a stalled renderer, and any frame longer than the gap pushed the render channel past its threshold. Per the brief, the render channel is now judged by **time since the last frame started**: `beat('render')` is the first thing `frame` does, before the fixed steps and before the draw. With that, one long frame contributes at most `elapsed` of stall and can never reach the 5 s recover threshold on hardware that is merely slow.

`docs/requirements.md` WD-04 is reworded to state both thresholds explicitly, and `[WD-04]` now asserts the 2 s report (via `lastFreezeReport()`, with `stalledMs ≥ 2000`) *before* asserting that the recovery screen and its three controls appear by the 5 s mark — so the two thresholds can no longer be conflated.

## 3. `[INP-04]` asserted 350 ms after each key press (test bug — assumes a frame lands in 350 ms)

On the CI desktop runner a frame costs up to ~1.2 s (the 31.2 s run of ~25 round trips implies that), so `keyboard.down('w')` → `waitForTimeout(350)` → read can legitimately observe *zero* frames of movement, and the fixed sleeps plus every round trip then exhaust the 30 s default budget.

Rewritten to be frame-driven, not sleep-driven:
- Each held key is released as soon as `camera()` reports the movement (`expect.poll` on the real camera state), so a fast machine finishes in a few hundred ms and a slow one as soon as its next frame lands.
- The touch branches drop the three `waitForTimeout(150)` calls: every gesture handler mutates `rtsCamera` synchronously, so there is nothing to wait for.
- Two redundant `camera()` round trips removed by reusing state that the previous gesture provably cannot change (`panned.distance` for the pinch baseline, `zoomed.yaw` for the twist baseline).
- The edge-clamp assertion is now stronger: it polls until the target is clamped on the west border (`|targetX + 80| ≤ 0.5`) and then also asserts `targetX ≤ -79.5`, i.e. panning was both applied and stopped by the clamp.
- **Justified budget:** `test.setTimeout(90_000)`. The revised test performs ~18 Playwright round trips plus three poll windows; at the measured ~1.2 s/round trip on that runner the worst case is ~60 s. 90 s leaves headroom without masking a genuine hang, and no other test's timeout was touched.

No test was skipped, no tolerance loosened (the INP-04 assertions are stricter than before), no lint/tsconfig rule relaxed and no dependency added. `docs/decisions.md` records all three decisions.
