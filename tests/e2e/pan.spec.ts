import { expect, test, type Page } from '@playwright/test';
import { enterGame } from './helpers';

/** A touch drag spread over real time: `holdMs` is how long the finger rests before lifting. */
async function timedTouchDrag(page: Page, dx: number, durationMs: number, holdMs: number): Promise<{ x: number; z: number }> {
  return page.evaluate(
    ({ dx, durationMs, holdMs }) => {
      const canvas = document.querySelector('canvas.game-canvas');
      if (!canvas) return { x: 0, z: 0 };
      const rect = canvas.getBoundingClientRect();
      const sx = rect.left + rect.width * 0.5;
      const sy = rect.top + rect.height * 0.55;
      const fire = (type: string, x: number, buttons: number): void => {
        canvas.dispatchEvent(
          new PointerEvent(type, {
            bubbles: true,
            cancelable: true,
            pointerId: 7,
            pointerType: 'touch',
            isPrimary: true,
            clientX: x,
            clientY: sy,
            button: 0,
            buttons,
          }),
        );
      };
      // Touch moves arrive about every 16 ms. The test browser draws so slowly that waiting on
      // timers would bunch them up, so the gaps are kept by spinning instead.
      const spin = (ms: number): void => {
        const until = performance.now() + ms;
        while (performance.now() < until) {
          // wait
        }
      };
      fire('pointerdown', sx, 1);
      const steps = Math.max(2, Math.round(durationMs / 16));
      let x = sx;
      for (let i = 1; i <= steps; i += 1) {
        spin(16);
        x = sx + (dx * i) / steps;
        fire('pointermove', x, 1);
      }
      spin(holdMs);
      fire('pointerup', x, 0);
      // Where the camera was the moment the finger lifted.
      const cam = window.__TC_TEST__?.camera();
      return { x: cam?.targetX ?? 0, z: cam?.targetZ ?? 0 };
    },
    { dx, durationMs, holdMs },
  );
}

async function target(page: Page): Promise<{ x: number; z: number }> {
  return page.evaluate(() => {
    const cam = window.__TC_TEST__?.camera();
    return { x: cam?.targetX ?? 0, z: cam?.targetZ ?? 0 };
  });
}

test.setTimeout(120_000);

test('[PAN-01] a flick keeps the map gliding and slows to a stop; resting the finger first does not', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch');
  await enterGame(page);
  await page.evaluate(() => {
    window.__TC_TEST__?.setCamera({ targetX: 0, targetZ: 0, distance: 60, yaw: 0 });
  });

  // A quick flick: the camera carries on after the finger lifts, then settles.
  const released = await timedTouchDrag(page, -220, 120, 0);
  // The test browser draws only a few frames a second, so give the glide a moment to show.
  await page.waitForTimeout(900);
  const gliding = await target(page);
  expect(Math.hypot(gliding.x - released.x, gliding.z - released.z)).toBeGreaterThan(1);
  // Then it slows to a stop (polled, as the test browser draws only a few frames a second).
  await expect
    .poll(
      async () => {
        const a = await target(page);
        await page.waitForTimeout(700);
        const b = await target(page);
        return Math.hypot(b.x - a.x, b.z - a.z);
      },
      { timeout: 40_000 },
    )
    .toBeLessThan(0.05);

  // The same drag, but the finger rests before lifting: the map stays where it was put.
  await page.evaluate(() => window.__TC_TEST__?.setCamera({ targetX: 0, targetZ: 0, distance: 60, yaw: 0 }));
  const placed = await timedTouchDrag(page, -220, 120, 150);
  await page.waitForTimeout(900);
  const after = await target(page);
  expect(Math.hypot(after.x - placed.x, after.z - placed.z)).toBeLessThan(0.05);

  // A touch on the map stops a glide at once.
  await page.evaluate(() => window.__TC_TEST__?.setCamera({ targetX: 0, targetZ: 0, distance: 60, yaw: 0 }));
  await timedTouchDrag(page, -220, 120, 0);
  await page.evaluate(() => {
    const canvas = document.querySelector('canvas.game-canvas');
    const rect = canvas?.getBoundingClientRect();
    if (!canvas || !rect) return;
    canvas.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 8, pointerType: 'touch', isPrimary: true, clientX: rect.left + 200, clientY: rect.top + 200, buttons: 1 }));
  });
  const caught = await target(page);
  await page.waitForTimeout(900);
  const held = await target(page);
  expect(Math.hypot(held.x - caught.x, held.z - caught.z)).toBeLessThan(0.05);
});
