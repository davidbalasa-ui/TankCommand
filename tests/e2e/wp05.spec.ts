import { expect, test } from '@playwright/test';
import { enterGame, openBuildMenu } from './helpers';

test('[RES-01] locked build items show their requirement and the Base sheet opens by touch', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  // The Base sheet over the detailed models renders at a few frames a second in software.
  test.setTimeout(60_000);
  await enterGame(page);

  await openBuildMenu(page);
  const turret = page.locator('[data-control-id="build.item.structure.human.turret"]');
  await expect(turret).toBeDisabled();
  await expect(turret).toContainText('Needs:');
  await expect(page.locator('[data-control-id="build.item.unit.human.turret_packed"]')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/shots/wp05-1-locked-build-item.png' });
  // Base opens from the Build drawer (or by tapping any other of your buildings).
  await page.locator('[data-control-id="build.tab.research"]').tap();
  await page.locator('[data-control-id="inGame.openBase"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.baseOpen ?? false)).toBe(true);
  const node = page.locator('[data-research-node="research.human.armor_plating"]');
  await expect(node).toBeVisible();
  await expect(node.locator('button')).toBeDisabled();
  await page.screenshot({ path: 'test-results/shots/wp05-2-research-sheet.png' });
  await page.locator('[data-control-id="inGame.baseClose"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.baseOpen ?? true)).toBe(false);
});
