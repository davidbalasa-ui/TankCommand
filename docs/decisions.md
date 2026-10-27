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
