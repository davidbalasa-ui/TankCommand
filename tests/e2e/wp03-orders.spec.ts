import { expect, test } from '@playwright/test';
import { enterGame } from './helpers';

const FIRST_LEG = 40;
const SECOND_LEG = 12;

test('[ORD-03] a queued waypoint is drawn as an extended order path', async ({ page }) => {
  test.setTimeout(60_000);
  await enterGame(page);

  const ownId = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.units().find((unit) => unit.owner === 1)?.id ?? null;
  });
  expect(ownId).not.toBeNull();
  if (ownId === null) {
    return;
  }

  await page.evaluate((id) => window.__TC_TEST__?.setSelection([id]), ownId);
  await expect
    .poll(async () =>
      page.evaluate((id) => window.__TC_TEST__?.selection().includes(id) ?? false, ownId),
    )
    .toBe(true);

  // Both orders go in from one page call (the second a tick after the first), so a slow runner
  // cannot let the unit finish the first leg between two separate page reads.
  await expect
    .poll(async () =>
      page.evaluate(
        (input) => {
          const hook = window.__TC_TEST__;
          const unit = hook?.units().find((item) => item.id === input.id);
          if (!hook || !unit) {
            return false;
          }
          const tick = hook.snapshot().tick;
          const first = hook.sendCommand({
            kind: 'move',
            unitIds: [input.id],
            x: unit.x + input.dx,
            z: unit.z,
            queue: false,
            tick: tick + 1,
            issuer: 1,
          });
          const second = hook.sendCommand({
            kind: 'move',
            unitIds: [input.id],
            x: unit.x,
            z: unit.z + input.dz,
            queue: true,
            tick: tick + 2,
            issuer: 1,
          });
          return first && second;
        },
        { id: ownId, dx: FIRST_LEG, dz: SECOND_LEG },
      ),
    )
    .toBe(true);

  // Freeze the sim as soon as the queued leg is in, so a slow runner (whose page reads can take
  // seconds) cannot let the unit finish the first leg before the drawn path is read.
  await expect
    .poll(async () =>
      page.evaluate((id) => {
        const hook = window.__TC_TEST__;
        const queued = hook?.units().find((item) => item.id === id)?.queued ?? false;
        if (queued) {
          hook?.pauseSim(true);
        }
        return queued;
      }, ownId),
    )
    .toBe(true);

  // Read the drawn path and its queued flag together: the unit re-plans its path as it drives
  // (avoidance), so the entry can be missing for a frame between two separate reads.
  await expect
    .poll(
      async () =>
        page.evaluate((id) => {
          const entry = window.__TC_TEST__?.orderPaths().find((path) => path.unitId === id);
          return entry ? { extended: entry.points > 2, queued: entry.queued } : null;
        }, ownId),
      { message: 'the drawn path covers both legs and is marked as a queued path' },
    )
    .toEqual({ extended: true, queued: true });
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
});
