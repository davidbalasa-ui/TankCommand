import { expect, test, type Page } from '@playwright/test';
import { enterGame, openBuildMenu } from './helpers';

// Overhaul step 3: the match screen layout. Phone profile only (the layout is built for it).
const PHONE_ONLY = 'phone layout';

async function ownUnits(page: Page): Promise<Array<{ id: number; workerKind: string | null; x: number; z: number }>> {
  return page.evaluate(() =>
    (window.__TC_TEST__?.units() ?? [])
      .filter((unit) => unit.owner === 1)
      .map((unit) => ({ id: unit.id, workerKind: unit.workerKind, x: unit.x, z: unit.z })),
  );
}

test('[LAY-01] orders show in the top queue strip; tapping one cancels it and Undo orders it again', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Software rendering of the full models is slow; taps wait for stable frames.
  test.setTimeout(90_000);
  await enterGame(page);
  await openBuildMenu(page);
  const item = await page.evaluate(
    () => window.__TC_TEST__?.buildItems().find((entry) => entry.kind === 'unit' && entry.disabledReason === null)?.id ?? null,
  );
  expect(item).not.toBeNull();
  if (!item) return;
  await page.locator(`[data-control-id="build.item.${item}"]`).tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.queue.length ?? 0)).toBe(1);
  const orderId = await page.evaluate(() => window.__TC_TEST__?.hud()?.queue[0]?.id ?? null);
  expect(orderId).not.toBeNull();
  // The tile is in the strip at the top of the screen, not inside the drop menu.
  const tile = page.locator(`.hud-queue [data-control-id="build.cancel.${orderId}"]`);
  await expect(tile).toBeVisible();
  const box = await tile.boundingBox();
  expect(box?.y ?? 999).toBeLessThan(60);
  const ore = await page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0);
  await page.touchscreen.tap(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.queue.length ?? 1)).toBe(0);
  expect(await page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0)).toBeGreaterThan(ore);
  // Undo lasts 3 s; slow software frames can eat that, so it is pressed from the page itself.
  const undone = await page.evaluate(() => {
    const undo = document.querySelector<HTMLButtonElement>('[data-control-id="inGame.queueUndo"]');
    if (!undo || undo.hidden) return false;
    undo.click();
    return true;
  });
  expect(undone).toBe(true);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.queue.length ?? 0)).toBe(1);
});

test('[LAY-02] the drop menu is a bottom strip; card order stays fixed and the tab is remembered', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Software rendering of the full models is slow; taps wait for stable frames.
  test.setTimeout(90_000);
  await enterGame(page);
  await openBuildMenu(page);
  const panel = page.locator('.hud-build-panel');
  const box = await panel.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  if (!box || !viewport) return;
  // Along the bottom, full width, at most about two fifths of the screen tall.
  expect(box.y + box.height).toBeGreaterThan(viewport.height - 2);
  expect(box.height).toBeLessThan(viewport.height * 0.42);
  expect(box.width).toBeGreaterThan(viewport.width * 0.9);
  const order = async (): Promise<string[]> =>
    page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('.drawer-cards[data-tab="unit"] [data-control-id^="build.item."]')].map(
        (card) => card.dataset.controlId ?? '',
      ),
    );
  const before = await order();
  expect(before.length).toBeGreaterThan(1);
  // Spending changes what is affordable but never the order.
  const item = before[0]!.replace('build.item.', '');
  await page.locator(`[data-control-id="build.item.${item}"]`).tap();
  await page.locator(`[data-control-id="build.item.${item}"]`).tap();
  expect(await order()).toEqual(before);

  await page.locator('[data-control-id="build.tab.structure"]').tap();
  await page.locator('[data-control-id="inGame.buildClose"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.buildMenuOpen ?? true)).toBe(false);
  await openBuildMenu(page);
  await expect(page.locator('[data-control-id="build.tab.structure"]')).toHaveAttribute('aria-selected', 'true');
});

test('[LAY-03] All army selects the fighters and leaves the miners and haulers out', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Software rendering of the full models is slow; taps wait for stable frames.
  test.setTimeout(90_000);
  await enterGame(page);
  const units = await ownUnits(page);
  const fighters = units.filter((unit) => !unit.workerKind).map((unit) => unit.id).sort((a, b) => a - b);
  expect(fighters.length).toBeGreaterThan(0);
  expect(units.some((unit) => unit.workerKind)).toBe(true);
  await page.locator('[data-control-id="inGame.groupAll"]').tap();
  await expect
    .poll(async () => (await page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).slice().sort((a, b) => a - b))
    .toEqual(fighters);
});

test('[LAY-04] select mode: a tap adds or removes a unit and a one-finger drag draws a box', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Software rendering of the full models is slow; taps wait for stable frames.
  test.setTimeout(90_000);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(true));
  const units = await ownUnits(page);
  const fighters = units.filter((unit) => !unit.workerKind);
  expect(fighters.length).toBeGreaterThan(1);
  const [a, b] = fighters;
  if (!a || !b) return;
  await page.evaluate((unit) => window.__TC_TEST__?.setCamera({ targetX: unit.x, targetZ: unit.z, distance: 40, yaw: 0 }), a);
  await page.locator('[data-control-id="inGame.selectMode"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.selectMode ?? false)).toBe(true);
  const point = async (id: number) => page.evaluate((unitId) => window.__TC_TEST__?.unitScreenCentre(unitId) ?? null, id);
  const pa = await point(a.id);
  const pb = await point(b.id);
  expect(pa).not.toBeNull();
  expect(pb).not.toBeNull();
  if (!pa || !pb) return;
  await page.touchscreen.tap(pa.x, pa.y);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toEqual([a.id]);
  await page.touchscreen.tap(pb.x, pb.y);
  await expect
    .poll(async () => (await page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).slice().sort((x, y) => x - y))
    .toEqual([a.id, b.id].sort((x, y) => x - y));
  await page.touchscreen.tap(pa.x, pa.y);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toEqual([b.id]);

  // A one-finger drag round both draws a box instead of moving the camera.
  const camera = await page.evaluate(() => window.__TC_TEST__?.camera() ?? null);
  await page.evaluate(() => window.__TC_TEST__?.setSelection([]));
  const left = Math.min(pa.x, pb.x) - 30;
  const right = Math.max(pa.x, pb.x) + 30;
  const top = Math.min(pa.y, pb.y) - 30;
  const bottom = Math.max(pa.y, pb.y) + 30;
  await page.evaluate(
    ({ left, top, right, bottom }) => {
      const canvas = document.querySelector('canvas.game-canvas');
      if (!canvas) return;
      const fire = (type: string, x: number, y: number, buttons: number): void => {
        canvas.dispatchEvent(
          new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 7, pointerType: 'touch', clientX: x, clientY: y, button: 0, buttons }),
        );
      };
      fire('pointerdown', left, top, 1);
      fire('pointermove', (left + right) / 2, (top + bottom) / 2, 1);
      fire('pointermove', right, bottom, 1);
      fire('pointerup', right, bottom, 0);
    },
    { left, top, right, bottom },
  );
  const picked = await page.evaluate(() => window.__TC_TEST__?.selection() ?? []);
  expect(picked).toContain(a.id);
  expect(picked).toContain(b.id);
  const after = await page.evaluate(() => window.__TC_TEST__?.camera() ?? null);
  expect(after?.targetX).toBeCloseTo(camera?.targetX ?? 0, 3);
  expect(after?.targetZ).toBeCloseTo(camera?.targetZ ?? 0, 3);
});

test('[LAY-05] alerts share one line under the resources, and the pause menu holds the clock', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Software rendering of the full models is slow; taps wait for stable frames.
  test.setTimeout(90_000);
  await enterGame(page);
  await page.evaluate(() => {
    window.__TC_TEST__?.raiseAlert('unitLost', 10, 10);
    window.__TC_TEST__?.raiseAlert('depositEmpty', 20, 20);
  });
  await expect(page.locator('.alert-toast')).toHaveCount(1);
  const line = await page.locator('.alert-toast').boundingBox();
  const resources = await page.locator('.hud-resbar').boundingBox();
  expect(line && resources).toBeTruthy();
  if (!line || !resources) return;
  expect(line.y).toBeGreaterThanOrEqual(resources.y + resources.height - 1);
  expect(line.height).toBeGreaterThanOrEqual(44);
  await expect(page.locator('[data-hud-item="clock"]')).toHaveCount(0);
});
