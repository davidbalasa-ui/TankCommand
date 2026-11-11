# Content phase plan (after the engine)

Started 2026-11-11. The engine (WP-01..10) is done and merged on this branch. This plan takes the game to Play Store readiness. Packages run in order unless marked parallel; at most two build agents at a time. Each package ends with tests green, a reviewer pass by an agent that did not write it, a push, and an entry in `docs/progress.md`.

| ID | Package | Owner | Notes |
|----|---------|-------|-------|
| C-01 | Stage 0 research: roster, rules, missions, proposed data sheet (`docs/research/`) | Sonnet researcher | Text sources only; videos can't be watched in the sandbox |
| C-02 | Engine gaps: AI builds and uses aircraft and hover tanks; training/mission areas drawn in 3D; loading a mission save restores mission mode | Opus (lead) | Parallel with C-01 |
| C-03 | Working names (game, factions, units) and real unit/structure/research data from C-01 | Opus + Sonnet | Final public names need David's approval (SOR hard limit) |
| C-04 | Basic art: low-poly models per role, one shared atlas per faction, phone budgets | Sonnet + Blender scripts | Art rules in project instructions |
| C-05 | Five training missions | Sonnet | Teach drops, mining, combat, research, air |
| C-06 | Human campaign (22) and alien campaign (22) missions, briefings | Sonnet in batches, Opus reviews | Mission data only, no engine code per mission |
| C-07 | Skirmish maps (at least 6, 2 and 4 sides) | Sonnet | |
| C-08 | Balance: AI-vs-AI soak, no unit/strategy over 65% of mirror matches | Opus | |
| C-09 | Performance: low-end phone profile fps check, memory budget | Opus | |
| C-10 | Play readiness: Capacitor Android build, one-time unlock purchase, privacy policy, store listing drafts | Sonnet | David's one-time tasks gate upload |
