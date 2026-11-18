import { expect, test, type Page } from '@playwright/test';
import { assertButtonLayout, gotoQuiet, waitForHook } from './helpers';

async function waitScreen(page: Page, screen: string): Promise<void> {
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe(screen);
}

function control(page: Page, id: string) {
  return page.locator(`[data-control-id="${id}"]`);
}

test('[IAP-03] locked full-game missions and maps open the unlock screen, and Back returns', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'Phone flow');
  await gotoQuiet(page);
  await waitForHook(page);
  // The web build is fully unlocked; the test hook stands in for a phone that has not bought it.
  expect(await page.evaluate(() => window.__TC_TEST__?.fullGameUnlocked())).toBe(true);
  await page.evaluate(() => {
    window.__TC_TEST__?.setFullGameUnlocked(false);
  });

  // Mission list: missions 1-5 are free, 6 on show "Full game" with a lock.
  await page.getByRole('button', { name: 'Campaign', exact: true }).click();
  await waitScreen(page, 'campaignSelect');
  await control(page, 'campaignSelect.human').click();
  await waitScreen(page, 'missionSelect');
  const rows = page.locator('.mission-row');
  await expect(rows.first()).toBeVisible();
  const first = page.locator('.mission-row').filter({ has: page.locator('.mission-order', { hasText: /^1$/ }) });
  await expect(first).not.toHaveAttribute('data-full-game', 'true');
  await expect(first.locator('.mission-state')).not.toHaveText('Full game');
  const sixth = page.locator('.mission-row').filter({ has: page.locator('.mission-order', { hasText: /^6$/ }) });
  await expect(sixth).toHaveAttribute('data-full-game', 'true');
  await expect(sixth.locator('.mission-state')).toHaveText('Full game');
  await expect(sixth).toBeEnabled();
  await assertButtonLayout(page);

  await sixth.click();
  await waitScreen(page, 'unlock');
  await expect(page.locator('.unlock-pitch')).toContainText('first 5 missions');
  // On the web there is no store: the price line says where to buy and Buy is off.
  await expect(page.locator('[data-unlock-price]')).toContainText('Android app');
  await expect(control(page, 'unlock.buy')).toBeDisabled();
  await expect(control(page, 'unlock.restore')).toBeEnabled();
  await assertButtonLayout(page);
  await control(page, 'unlock.restore').click();
  await expect(page.locator('[data-unlock-status]')).toContainText('restored in the Android app');
  await control(page, 'unlock.back').click();
  await waitScreen(page, 'missionSelect');

  // Skirmish: Cinder Basin is free; a locked map shows the badge and Start becomes Unlock.
  await page.evaluate(() => {
    window.__TC_TEST__?.go('campaignSelect');
    window.__TC_TEST__?.go('title');
    window.__TC_TEST__?.go('skirmishSetup');
  });
  await waitScreen(page, 'skirmishSetup');
  await expect(page.locator('.map-name b')).toHaveText('Cinder Basin');
  await expect(page.locator('.full-game-badge')).toHaveCount(0);
  await expect(control(page, 'skirmishSetup.start')).toHaveAttribute('aria-label', 'Start');
  let found = false;
  for (let i = 0; i < 8 && !found; i += 1) {
    await control(page, 'skirmishSetup.map').click();
    found = (await page.locator('.full-game-badge').count()) > 0;
  }
  expect(found).toBe(true);
  await expect(page.locator('.full-game-badge')).toContainText('Full game');
  await expect(control(page, 'skirmishSetup.start')).toHaveAttribute('aria-label', 'Unlock full game');
  await assertButtonLayout(page);
  await control(page, 'skirmishSetup.start').click();
  await waitScreen(page, 'unlock');
  await page.evaluate(() => {
    window.__TC_TEST__?.pressAndroidBack();
  });
  await waitScreen(page, 'skirmishSetup');

  // Settings offers Restore purchases.
  await page.evaluate(() => {
    window.__TC_TEST__?.go('title');
    window.__TC_TEST__?.go('settings');
  });
  await waitScreen(page, 'settings');
  await control(page, 'settings.restorePurchases').click();
  await expect(page.locator('[data-settings-status]')).toContainText('restored in the Android app');
  await assertButtonLayout(page);

  // Unlocked, nothing is marked.
  await page.evaluate(() => {
    window.__TC_TEST__?.setFullGameUnlocked(null);
    window.__TC_TEST__?.go('title');
    window.__TC_TEST__?.go('campaignSelect');
  });
  await control(page, 'campaignSelect.alien').click();
  await waitScreen(page, 'missionSelect');
  await expect(page.locator('.mission-row').first()).toBeVisible();
  await expect(page.locator('.mission-row[data-full-game="true"]')).toHaveCount(0);
});
