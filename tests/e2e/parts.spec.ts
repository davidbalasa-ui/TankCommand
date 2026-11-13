import { expect, test } from '@playwright/test';
import { enterGame } from './helpers';

test('[PART-01] the miner drum spins only while digging,', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only');
  test.setTimeout(120_000);
  await enterGame(page);
  const miner = await page.evaluate(
    () => window.__TC_TEST__?.units().find((u) => u.owner === 1 && u.workerKind === 'oreMiner') ?? null,
  );
  const deposit = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    const own = hook?.units().find((u) => u.owner === 1 && u.workerKind === 'oreMiner');
    return (
      hook
        ?.deposits()
        .filter((d) => d.kind === 'ore')
        .sort((a, b) => Math.hypot(a.x - (own?.x ?? 0), a.z - (own?.z ?? 0)) - Math.hypot(b.x - (own?.x ?? 0), b.z - (own?.z ?? 0)))[0] ?? null
    );
  });
  expect(miner).not.toBeNull();
  expect(deposit).not.toBeNull();
  if (!miner || !deposit) {
    return;
  }
  const drum = `${miner.typeId} DrumPivot`;
  const moving = async (): Promise<string[]> =>
    page.evaluate(() => window.__TC_TEST__?.renderStats().movingParts ?? []);
  expect(await moving()).not.toContain(drum);
  await page.evaluate(({ unitId, depositId }) => {
    const hook = window.__TC_TEST__;
    hook?.setSimSpeed(4);
    hook?.sendCommand({ kind: 'mine', unitIds: [unitId], depositId, tick: (hook?.snapshot().tick ?? 0) + 1, issuer: 1 });
  }, { unitId: miner.id, depositId: deposit.id });
  await expect
    .poll(async () => page.evaluate((id) => window.__TC_TEST__?.units().find((u) => u.id === id)?.jobStage ?? null, miner.id), {
      timeout: 60_000,
    })
    .toBe('digging');
  await expect.poll(moving, { timeout: 5_000 }).toContain(drum);
  await page.evaluate((id) => {
    const hook = window.__TC_TEST__;
    const unit = hook?.units().find((u) => u.id === id);
    if (hook && unit) {
      hook.setCamera({ targetX: unit.x, targetZ: unit.z, distance: 18, yaw: 0.6 });
    }
  }, miner.id);
  await page.screenshot({ path: 'test-results/shots/part-01-drum.png' });
});
