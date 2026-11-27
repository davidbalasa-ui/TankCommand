import { expect, test } from '@playwright/test';
import { enterGame } from './helpers';

test('[GRP-02] holding a filled group tile offers Clear, which empties it', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await enterGame(page);
  const own = await page.evaluate(() => (window.__TC_TEST__?.units() ?? []).filter((u) => u.owner === 1).map((u) => u.id));
  expect(own.length).toBeGreaterThan(0);
  await page.evaluate((ids) => window.__TC_TEST__?.setSelection(ids), own);
  const hold = async (): Promise<void> => {
    await page.evaluate(async () => {
      const tile = document.querySelector<HTMLButtonElement>('[data-control-id="inGame.group1"]');
      if (!tile) return;
      const fire = (type: string): void => {
        tile.dispatchEvent(
          new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 1, pointerType: 'touch', button: 0, buttons: type === 'pointerup' ? 0 : 1 }),
        );
      };
      fire('pointerdown');
      await new Promise<void>((resolve) => window.setTimeout(resolve, 520));
      fire('pointerup');
    });
  };
  const caption = page.locator('[data-control-id="inGame.group1"] .group-caption');
  // Empty tile: holding saves straight away.
  await hold();
  await expect(caption).not.toHaveText('hold to save');
  // Filled tile: holding opens the menu.
  await hold();
  const clear = page.locator('[data-control-id="inGame.groupClear"]');
  await expect(clear).toBeVisible();
  await expect(page.locator('[data-control-id="inGame.groupSave"]')).toBeVisible();
  await page.screenshot({ path: 'test-results/shots/grp-02-menu.png' });
  await clear.click();
  await expect(clear).toBeHidden();
  await expect(caption).toHaveText('hold to save');
});
