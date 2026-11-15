import { expect, test } from '@playwright/test';
import { enterGame, tapUnit, tapWorldPoint } from './helpers';

// Overhaul step 5: buildings land packed, drive out and unpack; tap the ground to send one elsewhere.
test('[PACK-02] a packed tower drives out by itself and a ground tap sends it elsewhere to unpack', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  test.setTimeout(120_000);
  await enterGame(page);
  const padId = await page.evaluate(
    () => window.__TC_TEST__?.structures().find((s) => s.owner === 1 && s.kind === 'pad')?.id ?? null,
  );
  expect(padId).not.toBeNull();
  await page.evaluate((id) => {
    const hook = window.__TC_TEST__;
    hook?.setSimSpeed(4);
    hook?.sendCommand({ kind: 'buy', itemId: 'structure.human.turret', padId: id, tick: hook.snapshot().tick + 1, issuer: 1 });
  }, padId);
  // It comes down as a packed vehicle, not a kit to place.
  await expect
    .poll(async () => page.evaluate(() => {
      // Hold the sim the moment it lands, before it can reach its spot and unpack.
      const hook = window.__TC_TEST__;
      const id = hook?.units().find((u) => u.owner === 1 && u.typeId === 'unit.human.turret_packed')?.id ?? null;
      if (id !== null) {
        hook?.pauseSim(true);
      }
      return id;
    }), {
      timeout: 60_000,
    })
    .not.toBeNull();
  expect(await page.evaluate(() => window.__TC_TEST__?.dropState().kits.length ?? 1)).toBe(0);
  await page.evaluate(() => {
    window.__TC_TEST__?.setSimSpeed(1);
    window.__TC_TEST__?.pauseSim(true);
  });
  const packed = await page.evaluate(() => window.__TC_TEST__?.units().find((u) => u.owner === 1 && u.typeId === 'unit.human.turret_packed') ?? null);
  expect(packed).not.toBeNull();
  if (!packed) return;
  await tapUnit(page, packed.id);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toEqual([packed.id]);
  // Send it 20 m to the side of where it is.
  const goal = { x: packed.x + 20, z: packed.z };
  await tapWorldPoint(page, goal.x, goal.z);
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
  const orderOf = async (): Promise<{ x: number; z: number } | null> =>
    page.evaluate((id) => {
      const unit = window.__TC_TEST__?.units().find((u) => u.id === id);
      return unit && unit.orderX !== null && unit.orderZ !== null ? { x: unit.orderX, z: unit.orderZ } : null;
    }, packed.id);
  // Its unpack spot moves to the tapped point (or the nearest free spot to it).
  await expect
    .poll(async () => {
      const spot = await orderOf();
      return spot ? Math.hypot(spot.x - goal.x, spot.z - goal.z) : 999;
    })
    .toBeLessThan(18.5);
  const order = await orderOf();
  await page.screenshot({ path: 'test-results/shots/pack-1-redirect.png' });
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(4));
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.structures().filter((s) => s.owner === 1 && s.kind === 'turret').length ?? 0), {
      timeout: 60_000,
    })
    .toBe(1);
  const tower = await page.evaluate(() => window.__TC_TEST__?.structures().find((s) => s.owner === 1 && s.kind === 'turret') ?? null);
  expect(Math.hypot((tower?.x ?? 0) - (order?.x ?? 0), (tower?.z ?? 0) - (order?.z ?? 0))).toBeLessThan(0.5);
});
