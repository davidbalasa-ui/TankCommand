import { expect, test } from '@playwright/test';
import { gotoQuiet, waitForHook } from './helpers';

test('[PRIV-01] the privacy policy is served and Settings and Credits open it', async ({ page, context }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'Phone flow');
  const response = await page.goto('/privacy.html');
  expect(response?.status()).toBe(200);
  const body = page.locator('body');
  await expect(body).toContainText('No accounts of our own, no ads, no analytics and no tracking');
  await expect(body).toContainText('Google Play');
  await expect(body).toContainText('does not store your IP address');
  await expect(body).toContainText('[contact email]');

  await gotoQuiet(page);
  await waitForHook(page);
  for (const [screen, control] of [
    ['settings', 'settings.privacy'],
    ['credits', 'credits.privacy'],
  ] as const) {
    await page.evaluate((id) => {
      window.__TC_TEST__?.go('title');
      window.__TC_TEST__?.go(id);
    }, screen);
    const opened = context.waitForEvent('page');
    await page.locator(`[data-control-id="${control}"]`).click();
    const policy = await opened;
    await policy.waitForLoadState();
    expect(policy.url()).toMatch(/\/privacy\.html$/);
    await expect(policy.locator('h1')).toHaveText('TankCommand privacy policy');
    await policy.close();
  }
});
