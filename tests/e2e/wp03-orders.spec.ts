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

  // A long first leg so the order is still in flight when the second waypoint is
  // queued: the drawn path then covers both, and the assertion cannot race the
  // unit's arrival.
  await expect
    .poll(async () =>
      page.evaluate(
        (input) => {
          const hook = window.__TC_TEST__;
          const unit = hook?.units().find((item) => item.id === input.id);
          if (!hook || !unit) {
            return false;
          }
          return hook.sendCommand({
            kind: 'move',
            unitIds: [input.id],
            x: unit.x + input.dx,
            z: unit.z,
            queue: false,
            tick: hook.snapshot().tick + 1,
            issuer: 1,
          });
        },
        { id: ownId, dx: FIRST_LEG },
      ),
    )
    .toBe(true);

  await expect
    .poll(async () =>
      page.evaluate((id) => {
        const unit = window.__TC_TEST__?.units().find((item) => item.id === id);
        return unit ? unit.pathPoints : 0;
      }, ownId),
    )
    .toBeGreaterThan(0);

  await expect
    .poll(async () =>
      page.evaluate(
        (input) => {
          const hook = window.__TC_TEST__;
          const unit = hook?.units().find((item) => item.id === input.id);
          if (!hook || !unit) {
            return false;
          }
          return hook.sendCommand({
            kind: 'move',
            unitIds: [input.id],
            x: unit.x,
            z: unit.z + input.dz,
            queue: true,
            tick: hook.snapshot().tick + 1,
            issuer: 1,
          });
        },
        { id: ownId, dz: SECOND_LEG },
      ),
    )
    .toBe(true);

  await expect
    .poll(async () =>
      page.evaluate((id) => {
        const entry = window.__TC_TEST__?.orderPaths().find((path) => path.unitId === id);
        return entry ? entry.points : 0;
      }, ownId),
    )
    .toBeGreaterThan(2);

  const drawn = await page.evaluate((id) => {
    const entry = window.__TC_TEST__?.orderPaths().find((path) => path.unitId === id);
    return entry ? entry.queued : null;
  }, ownId);
  expect(drawn, 'the drawn path is marked as a queued path').toBe(true);
});
