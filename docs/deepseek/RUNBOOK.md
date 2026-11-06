# Runbook: running a DeepSeek work package

For the Claude session that runs packages (Sonnet, low effort is enough). DeepSeek writes all the code.
Your job: start the run, read the result, do a light review, push, watch CI. Don't write game code
yourself beyond a one-line fix; send problems back to DeepSeek instead.

Owner direction (David, 2026-10-28): DeepSeek builds the engine; Claude only validates. The owner plays on
a phone, so phone behaviour matters most. Placeholder art is expected. Never merge PRs; merging to
main deploys the live site.

## Order

| Package | Spec | Needs |
| --- | --- | --- |
| WP-03 phone controls, camera, HUD shell | `packages/WP-03.md` | WP-02 (done) |
| WP-04 economy, pads, drops, victory | `packages/WP-04.md` | WP-03 |
| WP-05 structures, research, upgrades, repair | `packages/WP-05.md` | WP-04 |
| WP-06 fog of war, sensors, radar, stealth | `packages/WP-06.md` | WP-05 |
| WP-07 enemy AI, AI-vs-AI tests | `packages/WP-07.md` | WP-06 |
| WP-08 air units, air bases, water, hover | `packages/WP-08.md` | WP-07 |
| WP-09 missions, triggers, campaigns, skirmish setup | `packages/WP-09.md` | WP-08 |
| WP-10 pause, speed, saves, settings, audio, alerts, bug report | `packages/WP-10.md` | WP-09 |

Every package also gets `COMMON.md` and the SOR gameplay tab (`docs/sor/gameplay.md`) automatically.

## Run one package

From the repo root, on the working branch, with a clean tree:

```
tools/deepseek/run.sh WP-03 8          # run in the background; takes 30–120 min
tail -5 .deepseek-runs/WP-03/SUMMARY.txt
```

It does round 1 from the spec, then up to 8 fix rounds fed with real check output, then one or two
visual rounds with phone screenshots. The last line of `SUMMARY.txt` is `GREEN` or `STUCK`. Reports from
DeepSeek are in `.deepseek-runs/WP-03/REPORTS.md`, screenshots in `shots_v1/`. Runs are gitignored.

Cost: `python3 tools/deepseek/cost.py WP-03`.

## When it's GREEN: light review (keep it short)

1. `git status --short | head -50` and `git diff --stat | tail -3`: changes stay inside src/, tests/,
   docs/requirements.md, docs/progress.md, docs/decisions.md, package.json scripts, src/data/.
2. `git diff | grep -nE "eslint-disable|ts-ignore|ts-expect-error|\.skip\(|\.only\(|as any"`: must be
   empty. If not, send it back (below).
3. Skim REPORTS.md for "partial" or "not done" requirement IDs. Partial items go back to DeepSeek.
4. Look at the `shots_v*` screenshots (Read tool shows images). Anything obviously broken on the phone
   goes back to DeepSeek with a one-paragraph description.
5. If all fine: commit (`WP-03 (DeepSeek): <one line>`), push to the working branch, update the PR body's
   package list. Wait for CI (PR events wake you; don't poll).

## Sending problems back

Write the problem to a file (real CI log lines, or your review notes, plain and specific), then:

```
tools/deepseek/run.sh WP-03 6 /path/to/feedback.txt
```

It resumes DeepSeek's conversation for that package, applies the fix, re-runs all checks and loops.
For a CI failure, put the failing test names and the error lines from the job log in the file.

## When it's STUCK

- Read the last `fb_r*.txt` and the last report. If DeepSeek is fighting a test it wrote that is wrong
  or racy, say so in a feedback file and resume.
- If the same thing is stuck after a second resume, or the spec looks ambiguous or wrong, stop and
  hand the decision to the owner's thread: what is stuck, what you tried, and the options. A stronger
  model may be needed for the spec fix; don't hand-write the feature.

## Reporting to the owner

One short message per package when it's pushed and CI is green: what now works on the phone, what is
still placeholder, the preview link, DeepSeek cost. Nothing in between unless blocked.
