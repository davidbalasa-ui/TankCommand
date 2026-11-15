import { expect, test } from '@playwright/test';
import { enterGame, openBuildMenu } from './helpers';

// Overhaul step 4: no Research tab and no lab to buy. A locked card is its own unlock.
test('[RES-01] a locked card shows its research and starts it by touch; upgrades open Base by touch', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  // The Base sheet over the detailed models renders at a few frames a second in software.
  test.setTimeout(120_000);
  await enterGame(page);

  await openBuildMenu(page);
  await expect(page.locator('[data-control-id="build.tab.research"]')).toHaveCount(0);
  await page.locator('[data-control-id="build.tab.structure"]').tap();
  // The basic gun tower needs no research; the lab is not for sale.
  const turret = page.locator('[data-control-id="build.item.structure.human.turret"]');
  await expect(turret).not.toHaveAttribute('data-research-node', /.+/);
  await expect(page.locator('[data-control-id="build.item.structure.human.lab"]')).toHaveCount(0);
  await expect(page.locator('[data-control-id="build.item.unit.human.turret_packed"]')).toHaveCount(0);
  // A tier-2 card names its parent too.
  await expect(page.locator('[data-control-id="build.item.unit.human.artillery"]')).toContainText(
    'Research Missiles, then Heavy Ordnance',
  );
  const tower = page.locator('[data-control-id="build.item.structure.human.missile_battery"]');
  await expect(tower).toHaveAttribute('data-research-node', 'research.human.fortifications');
  await expect(tower).toContainText('Research Fortifications');
  await expect(tower).toBeEnabled();
  await page.screenshot({ path: 'test-results/shots/wp05-1-locked-card.png' });

  await tower.tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.research.map((step) => step.nodeId) ?? []))
    .toEqual(['research.human.fortifications']);
  await expect(page.locator('.hud-queue [data-control-id="research.cancel.research.human.fortifications"]')).toBeVisible();
  // One research at a time: other locked cards wait.
  await expect(page.locator('[data-control-id="build.item.unit.human.missile_tank"]')).toHaveAttribute(
    'data-research-state',
    'busy',
  );
  await page.screenshot({ path: 'test-results/shots/wp05-2-researching.png' });
  await page.locator('[data-control-id="inGame.buildClose"]').tap();

  // Fortifications brings the armour upgrade: the Upgrade command opens Base for the tanks.
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.research.length ?? 1), { timeout: 90_000 })
    .toBe(0);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(1));
  const tank = await page.evaluate(
    () => window.__TC_TEST__?.units().find((unit) => unit.owner === 1 && unit.typeId === 'unit.human.light_tank')?.id ?? null,
  );
  expect(tank).not.toBeNull();
  await page.evaluate((id) => window.__TC_TEST__?.setSelection([id ?? 0]), tank);
  const upgrade = page.locator('[data-control-id="inGame.upgrade"]');
  await expect(upgrade).toBeVisible();
  await upgrade.tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.baseOpen ?? false)).toBe(true);
  await expect(page.locator(`[data-control-id="inGame.upgrade.${tank}.armor"]`)).toBeEnabled();
  await page.screenshot({ path: 'test-results/shots/wp05-3-upgrade-sheet.png' });
  await page.locator('[data-control-id="inGame.baseClose"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.baseOpen ?? true)).toBe(false);
});
