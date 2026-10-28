# Rules for every DeepSeek work package

You are building the engine of a mobile real-time strategy game: a rebuild of Armor Command (1998), for
Android phones first (Capacitor-wrapped web build), then desktop browsers. The SOR gameplay specification
is attached after the package spec as reference. **The package spec decides scope**: build what it asks,
nothing more. Art is placeholder for now (simple shapes, flat colours, the one PoC tank model); a later
stage replaces it, so keep rendering of each thing in one place that is easy to swap.

You cannot run code. A script applies your files, runs every check below for real, and sends you the
real failures. Get it right first time: mentally type-check and run every test you write.

## The player is on a phone

- The primary target is a phone in landscape, 915×412 CSS px, touch only. Design and test for it first;
  tablet (1280×800 touch) and desktop (1920×1080 mouse) must also work.
- Touch targets at least 44×44 CSS px. Text at least 12 px. No HUD element overlaps another or covers
  more than about 20% of the battlefield on the phone.
- Every gesture or button the package adds gets an e2e test on the phone project that performs the real
  gesture (Playwright touch/pointer events) and checks the resulting state through the test hook.

## Fixed stack (do not change versions or add dependencies)

Vite 7, TypeScript 5.9 strict (noUncheckedIndexedAccess), Vitest 3, Playwright 1.63, ESLint 9 with
typescript-eslint recommendedTypeChecked, three 0.186, Capacitor 8, zod 3.25, jsdom 26. Everything
needed is already in package.json.

## Architecture rules (already enforced by lint and tests; keep them true)

- `src/sim` is the whole game rulebook: headless and deterministic. No DOM, no three, no Math.random,
  no Date.now, no performance.now. Randomness only through the seeded Rng in the world state. Fixed
  20 Hz step. Commands in, state out. `hashWorld` must stay stable for identical command streams.
- All player and AI actions go through validated commands (`src/sim/commands.ts`, zod). The renderer
  and UI never change world state directly.
- Split the sim into system modules (for example `src/sim/economy.ts`, `src/sim/vision.ts`) called from
  the world step in a fixed order. Do not grow `world.ts` past about 1,200 lines; move code out of it
  when you touch it.
- Every gameplay number lives in data: unit and structure stats in `src/data/*.json` validated by the
  zod schemas in `src/data/`, other numbers in `src/sim/tuning.ts`. Each placeholder value carries the
  comment `// placeholder until Stage 0` (or a `"placeholder": true` field in JSON). No magic numbers in
  logic.
- Rendering in `src/render`, input in `src/ui/input.ts` (split it into modules if it grows past about
  800 lines), screens and HUD in `src/ui`. HUD is DOM over the canvas, styled in `src/ui/styles.css`.
- The test hook (`src/testhook/testhook.ts`, test builds only via `__TEST_HOOK__`) exposes whatever the
  e2e tests need to read. Add to it; never ship it in production builds.
- Saves: anything added to world state must survive `serialize`/`deserialize` and keep determinism
  (a save loaded and run forward gives the same hash as the unsaved run).

## Checks the script runs (all must pass)

`npm run typecheck`, `npm run lint` (zero warnings), `npm test` (Vitest), `npm run credits:check`,
`npm run coverage:req`, `npm run build`, then `npx playwright test` on phone, tablet and desktop.
Never use eslint-disable, ts-ignore, `any` casts to dodge types, `.skip`, `.only`, or weakened
assertions. Do not edit the lint config, tsconfig, or CI workflow.

CI desktop uses software WebGL and is slow: e2e tests must wait on state through the test hook
(`expect.poll`), never on fixed sleeps, and must not depend on frame rate.

## Requirements and tests

- Each package lists requirement IDs. Add each as a row of the table in `docs/requirements.md`
  (`| ID | Description |`) and put `[ID]` (with the square brackets) in at least one test title, so
  `npm run coverage:req` passes. Never reuse or renumber an existing ID.
- Unit-test sim rules in Vitest; e2e-test what the player does on screen.
- Add or update `tests/e2e/screens.spec.ts`: in the **phone project only**, drive the game to each new
  screen or state this package adds and save `page.screenshot({ path: 'test-results/shots/<pkg>-<n>-<name>.png' })`
  (at most 6 per package, numbered in viewing order). These go to a visual review.
- Update `docs/progress.md` with one short section for the package, and `docs/decisions.md` for any
  choice the spec left open.

## Output format (strict)

Return full file contents only, in this exact format, any number of blocks:

```
<<<FILE path/from/repo/root.ts>>>
...entire file...
<<<END FILE>>>
<<<DELETE path/to/remove.ts>>>
```

Then exactly one report block:

```
<<<REPORT>>>
For each requirement ID: done / partial / not done, and the test that proves it.
Anything you deviated from, and why. Known risks.
<<<END REPORT>>>
```

Never output partial files or diffs. Do not touch `android/`, `tools/`, `docs/deepseek/`, `docs/sor/`,
`.github/workflows/`, `package-lock.json` or binary assets (writes there are discarded).
