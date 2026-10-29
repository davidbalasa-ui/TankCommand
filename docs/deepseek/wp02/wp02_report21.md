# Fix report

**Failure: `npm run typecheck` — 5 × `TS2304 Cannot find name` in `tests/e2e/wp02.spec.ts`.**

Root cause: when I rewrote the spec to split `INP-01` into the pick test and the order test, I replaced the whole file and dropped two helper definitions that the untouched tests still call:

- `dispatchTouch` — used by `[INP-04]` for the one-finger pan, pinch, twist and the edge-clamp drags (lines 500/510/523/559).
- `freezeAfterNextStep` — used by `[PLAY-02]` to read the queued order after exactly one fixed step (line 771).

Those are the only two call sites, and both functions existed and worked before the rewrite; nothing about them was part of the redesign, so this was a pure edit regression. Restored both, verbatim:

- `dispatchTouch(page, steps)` dispatches every event of one gesture in a single `page.evaluate`, so no wall-clock gap can elapse between them (the property that stopped a fast drag being read as a long-press).
- `freezeAfterNextStep(page)` waits for one fixed step and then pauses, so `[PLAY-02]` can inspect the order before the tank drives.

No test logic, assertion, tolerance, timeout or coverage changed; no source file was touched; `npm test` (70/70) was already green and is unaffected.

Also removed a malformed row I had left in `docs/decisions.md` (`| 2026-11-10 | Why does [INP-01] say order targets are guaranteed? | | | |` — empty choice/evidence/who) and replaced it with the two decisions that actually apply: why the order targets are restricted to the flat start disc, and why `INP-01` dispatches the pointer events directly rather than through `locator.click()`.

No test was skipped, no tolerance loosened, no lint/tsconfig rule relaxed, no dependency added.
