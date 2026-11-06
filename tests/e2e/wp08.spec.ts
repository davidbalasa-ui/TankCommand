import { expect, test } from '@playwright/test';
import { enterGame } from './helpers';

test('[TER-01] the lakeside map renders water and the Launch button stays hidden without aircraft', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await enterGame(page, { map: 'map.wp08_lakeside' });
  const level = await page.evaluate(
    () => (window.__TC_TEST__?.snapshot() as { mapFeatures?: { waterLevel: number | null } } | undefined)?.mapFeatures?.waterLevel,
  );
  expect(level).not.toBeNull();
  expect(level).toBeDefined();
  await expect(page.getByRole('button', { name: 'Launch', exact: true })).toBeHidden();
  await page.screenshot({ path: 'test-results/shots/wp08-1-lakeside.png' });
});
