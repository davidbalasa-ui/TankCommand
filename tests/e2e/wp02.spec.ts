import { expect, test, type Page, type TestInfo } from '@playwright/test';
import {
  countDistinctPngColors,
  enterGame,
  type GroundPick,
  type IssuedCommand,
  type TestCamera,
  type TestUnit,
} from './helpers';

function isTouch(testInfo: TestInfo): boolean {
  return testInfo.project.name !== 'desktop';
}

async function units(page: Page): Promise<TestUnit[]> {
  return page.evaluate(() => window.__TC_TEST__?.units() ?? []);
}

async function selectUnit(page: Page, x: number, y: number, touch: boolean): Promise<void> {
  if (touch) {
    await page.touchscreen.tap(x, y);
  } else {
    await page.mouse.click(x, y);
  }
}

async function orderAt(page: Page, x: number, y: number, touch: boolean): Promise<void> {
  if (touch) {
    await page.touchscreen.tap(x, y);
  } else {
    await page.mouse.click(x, y, { button: 'right' });
  }
}

/**
 * The camera hook applies the new view synchronously (`applyCamera` updates the
 * camera matrices), so `worldToScreen` and the pick raycast are already valid on
 * the next evaluate — no settle time is needed between them.
 */
async function setCamera(page: Page, info: Partial<TestCamera>): Promise<void> {
  await page.evaluate((camera) => {
    window.__TC_TEST__?.setCamera(camera);
  }, info);
}

async function camera(page: Page): Promise<TestCamera> {
  return page.evaluate(() => window.__TC_TEST__?.camera() ?? {
    targetX: 0,
    targetZ: 0,
    distance: 60,
    yaw: 0,
    pitch: 0,
  });
}

/**
 * Presses a registered HUD control by dispatching a real `click` on the button
 * inside the page. `locator.click()` first runs Playwright's actionability
 * checks, whose latency can be hundreds of milliseconds on a loaded runner and
 * is not part of anything under test.
 */
async function pressControl(page: Page, controlId: string): Promise<void> {
  await page
    .locator(`[data-control-id="${controlId}"]`)
    .first()
    .evaluate((element) => {
      if (element instanceof HTMLElement) {
        element.click();
      }
    });
}

type CanvasAction = 'left' | 'right' | 'touch';

/**
 * Delivers one complete press/release on the canvas in a single task, exactly
 * like a real finger or mouse button, and returns the ground point the input
 * layer resolved for it.
 *
 * The down and the up happen in the same task, so no wall-clock gap elapses
 * between them — a slow runner cannot turn a tap into a long-press (which would
 * box-select instead of acting), and `lastGroundPick()` is read in that same
 * task so the assertion can never accidentally observe the pick left behind by
 * an earlier sample.
 */
async function pressCanvas(
  page: Page,
  x: number,
  y: number,
  action: CanvasAction,
): Promise<GroundPick | null> {
  return page.evaluate(
    (input: { px: number; py: number; mode: CanvasAction }) => {
      const hook = window.__TC_TEST__;
      const canvas = document.querySelector('canvas');
      if (!hook || !canvas) {
        return null;
      }
      const pointerType = input.mode === 'touch' ? 'touch' : 'mouse';
      const button = input.mode === 'right' ? 2 : 0;
      const fire = (type: string, buttons: number): void => {
        canvas.dispatchEvent(
          new PointerEvent(type, {
            bubbles: true,
            cancelable: true,
            pointerId: 1,
            pointerType,
            isPrimary: true,
            clientX: input.px,
            clientY: input.py,
            button,
            buttons,
          }),
        );
      };
      fire('pointerdown', button === 2 ? 2 : 1);
      fire('pointerup', 0);
      return hook.lastGroundPick();
    },
    { px: x, py: y, mode: action },
  );
}

/**
 * Waits until at least one fixed step has run since the order was issued and then
 * freezes the sim, so the order can be read without racing the unit's arrival.
 */
async function freezeAfterNextStep(page: Page): Promise<void> {
  await page.evaluate(async () => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return;
    }
    const start = hook.snapshot().tick;
    for (let i = 0; i < 900 && hook.snapshot().tick === start; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    hook.pauseSim(true);
  });
}

interface TouchStep {
  type: string;
  id: number;
  x: number;
  y: number;
}

/**
 * Delivers one complete touch gesture in a single task.
 *
 * The events of a real gesture arrive back to back; dispatching them through
 * separate `page.evaluate` round trips inserts an uncontrolled amount of wall
 * clock time between them, which on a loaded runner can exceed the 400 ms
 * long-press threshold — turning a two-frame drag into a long-press box-select
 * and making a camera test fail purely because the machine was busy.
 */
async function dispatchTouch(page: Page, steps: readonly TouchStep[]): Promise<void> {
  await page.evaluate((events) => {
    const canvas = document.querySelector('canvas');
    if (!canvas) {
      return;
    }
    for (const event of events) {
      canvas.dispatchEvent(
        new PointerEvent(event.type, {
          bubbles: true,
          cancelable: true,
          pointerId: event.id,
          pointerType: 'touch',
          clientX: event.x,
          clientY: event.y,
          button: 0,
          buttons: event.type === 'pointerup' ? 0 : 1,
        }),
      );
    }
  }, steps as TouchStep[]);
}

interface OriginPoint {
  x: number;
  z: number;
}

interface LocatedPoint {
  world: OriginPoint;
  screen: { x: number; y: number };
}

/**
 * Finds a world point near `origin`, visible at the given camera framing and at
 * least `minClearance` screen pixels from every unit's pick centre, and returns
 * it along with its screen position. If `origin` is too close to a unit (or off
 * screen), a spiral of small offsets is tried — this is what "nudge the sample
 * point and record the actual point used" means in practice. The test asserts
 * against the returned `world`, so the recorded point is exactly what was
 * pressed.
 */
async function findSafeSample(
  page: Page,
  origin: OriginPoint,
  yaw: number,
  distance: number,
  minClearance: number,
): Promise<LocatedPoint | null> {
  const candidates: OriginPoint[] = [origin];
  for (const radius of [4, 8, 12]) {
    for (let i = 0; i < 12; i += 1) {
      const angle = (i / 12) * Math.PI * 2;
      candidates.push({
        x: origin.x + Math.cos(angle) * radius,
        z: origin.z + Math.sin(angle) * radius,
      });
    }
  }

  for (const point of candidates) {
    if (Math.abs(point.x) > 78 || Math.abs(point.z) > 78) {
      continue;
    }
    await setCamera(page, { targetX: point.x, targetZ: point.z, distance, yaw });
    const located = await page.evaluate(
      (input: OriginPoint) => {
        const hook = window.__TC_TEST__;
        const canvas = document.querySelector('canvas');
        if (!hook || !canvas) {
          return null;
        }
        const rect = canvas.getBoundingClientRect();
        const screen = hook.worldToScreen(input.x, input.z);
        if (screen.x < rect.left + 30 || screen.x > rect.right - 30) {
          return null;
        }
        if (screen.y < rect.top + 64 || screen.y > rect.bottom - 30) {
          return null;
        }
        let closest = Number.POSITIVE_INFINITY;
        for (const unit of hook.units()) {
          const centre = hook.unitScreenCentre(unit.id);
          if (!centre) {
            continue;
          }
          closest = Math.min(closest, Math.hypot(centre.x - screen.x, centre.y - screen.y));
        }
        return { screen, clearance: Number.isFinite(closest) ? closest : 0 };
      },
      point,
    );
    if (located && located.clearance >= minClearance) {
      return { world: point, screen: located.screen };
    }
  }
  return null;
}

async function readLastIssued(page: Page): Promise<IssuedCommand | null> {
  return page.evaluate(() => window.__TC_TEST__?.lastIssuedCommand() ?? null);
}

const ORIGIN_POINTS: readonly OriginPoint[] = [
  { x: -68, z: -58 },
  { x: -58, z: -68 },
  { x: -64, z: -64 },
  { x: 74, z: 74 }, // 8.5 units from the (80, 80) corner
  { x: -74, z: 74 }, // 8.5 units from the (-80, 80) corner
];

const SAMPLE_CAMERAS = [
  { distance: 20, yaw: 0 },
  { distance: 60, yaw: 1 },
  { distance: 120, yaw: 2 },
];

test('[INP-01] ground picks land at the picked point at every zoom and near the map corners', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await enterGame(page);
  const touch = isTouch(testInfo);
  const pickRadius = touch ? 36 : 24;
  const minClearance = pickRadius + 10;

  // No orders are issued in this test, so tanks never move: every sample sees
  // the same unit positions and the clearance from a point to a unit's pick
  // centre is stable across zoom settings.
  await pressControl(page, 'inGame.deselect');
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
    .toEqual([]);

  for (const setting of SAMPLE_CAMERAS) {
    for (const origin of ORIGIN_POINTS) {
      const label = `origin (${origin.x}, ${origin.z}) at distance ${setting.distance}`;
      const sample = await findSafeSample(
        page,
        origin,
        setting.yaw,
        setting.distance,
        minClearance,
      );
      expect(
        sample,
        `${label}: a visible point at least ${minClearance} px from every unit`,
      ).not.toBeNull();
      if (!sample) {
        return;
      }

      const picked = await pressCanvas(
        page,
        sample.screen.x,
        sample.screen.y,
        touch ? 'touch' : 'left',
      );
      expect(picked, `${label}: press reached the canvas`).not.toBeNull();
      expect(
        Math.hypot((picked?.x ?? 0) - sample.world.x, (picked?.z ?? 0) - sample.world.z),
        `${label}: ground pick (${picked?.x ?? 0}, ${picked?.z ?? 0}) vs requested (${sample.world.x}, ${sample.world.z})`,
      ).toBeLessThanOrEqual(1);
    }
  }
});

test('[INP-01] a right-click issues a move whose target is the picked ground point', async ({
  page,
}, testInfo) => {
  test.setTimeout(60_000);
  await enterGame(page);
  const touch = isTouch(testInfo);
  const all = await units(page);
  const own = all.filter((unit) => unit.owner === 1);
  expect(own.length).toBe(4);
  const unit = own[0];
  expect(unit).toBeDefined();
  if (!unit) {
    return;
  }

  // The sim is paused for the whole order exercise, so neither the tank nor
  // anything else moves between selecting the tank, pressing the ground, and
  // reading the command. No order-derived drive time can race the assertion.
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(true));

  await setCamera(page, { targetX: unit.x, targetZ: unit.z, distance: 60, yaw: 0 });
  const centre = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    unit.id,
  );
  expect(centre).not.toBeNull();
  if (!centre) {
    return;
  }
  await pressCanvas(page, centre.x, centre.y, touch ? 'touch' : 'left');
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
    .toContain(unit.id);

  // A destination inside the flat disc around the player start. `generateMap`
  // flattens that disc to height 0 out to radius 14, so the sim accepts the
  // destination verbatim — no nearest-reachable redirect applies. The search
  // also keeps the point well clear of every unit so the press is ground, not
  // a unit pick.
  await setCamera(page, { targetX: -50, targetZ: -50, distance: 60, yaw: 0 });
  const orderPoint = await page.evaluate(
    (tanks) => {
      const hook = window.__TC_TEST__;
      const canvas = document.querySelector('canvas');
      if (!hook || !canvas) {
        return null;
      }
      const rect = canvas.getBoundingClientRect();
      for (const radius of [10, 12, 8, 6]) {
        for (let i = 0; i < 24; i += 1) {
          const angle = (i / 24) * Math.PI * 2;
          const wx = -50 + Math.cos(angle) * radius;
          const wz = -50 + Math.sin(angle) * radius;
          const screen = hook.worldToScreen(wx, wz);
          if (screen.x < rect.left + 40 || screen.x > rect.right - 40) {
            continue;
          }
          if (screen.y < rect.top + 64 || screen.y > rect.bottom - 40) {
            continue;
          }
          let screenClearance = Number.POSITIVE_INFINITY;
          let worldClearance = Number.POSITIVE_INFINITY;
          for (const tank of tanks) {
            const c = hook.unitScreenCentre(tank.id);
            if (c) {
              screenClearance = Math.min(
                screenClearance,
                Math.hypot(c.x - screen.x, c.y - screen.y),
              );
            }
            worldClearance = Math.min(worldClearance, Math.hypot(wx - tank.x, wz - tank.z));
          }
          if (!Number.isFinite(screenClearance)) {
            screenClearance = 0;
          }
          if (screenClearance < 60) {
            continue;
          }
          if (worldClearance < 8) {
            continue;
          }
          return { world: { x: wx, z: wz }, screen };
        }
      }
      return null;
    },
    own.map((t) => ({ id: t.id, x: t.x, z: t.z })),
  );

  expect(orderPoint, 'a reachable point clear of every unit').not.toBeNull();
  if (!orderPoint) {
    return;
  }

  await pressCanvas(
    page,
    orderPoint.screen.x,
    orderPoint.screen.y,
    touch ? 'touch' : 'right',
  );
  const issued = await readLastIssued(page);
  expect(issued, 'a command was issued').not.toBeNull();
  if (!issued) {
    return;
  }
  expect(issued.kind).toBe('move');
  expect(issued.unitIds).toContain(unit.id);
  expect(
    Math.hypot((issued.x ?? 0) - orderPoint.world.x, (issued.z ?? 0) - orderPoint.world.z),
    `command target (${issued.x ?? 0}, ${issued.z ?? 0}) vs clicked (${orderPoint.world.x}, ${orderPoint.world.z})`,
  ).toBeLessThanOrEqual(1);

  await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
});

test('[INP-02] box selection selects exactly the own tanks in the box', async ({ page }) => {
  await enterGame(page);
  const own = (await units(page)).filter((unit) => unit.owner === 1);
  expect(own.length).toBe(4);

  // The box is built from the same screen point that clicking a tank tests
  // (`unitScreenCentre`), because box selection and click selection must agree
  // on where a tank is; `worldToScreen` returns the ground base, a model-height
  // lower, and a tight box around it can miss the tank's pick centre.
  const screens = await page.evaluate(
    (ids) =>
      ids
        .map((id) => ({
          id,
          screen: window.__TC_TEST__?.unitScreenCentre(id) ?? null,
        }))
        .filter(
          (entry): entry is { id: number; screen: { x: number; y: number } } =>
            entry.screen !== null,
        ),
    own.map((unit) => unit.id),
  );
  expect(screens.length).toBe(4);

  let chosen: { ids: number[]; start: { x: number; y: number }; end: { x: number; y: number } } | null =
    null;
  for (let i = 0; i < screens.length && !chosen; i += 1) {
    for (let j = i + 1; j < screens.length && !chosen; j += 1) {
      const a = screens[i];
      const b = screens[j];
      if (!a || !b) {
        continue;
      }
      const minX = Math.min(a.screen.x, b.screen.x) - 12;
      const maxX = Math.max(a.screen.x, b.screen.x) + 12;
      const minY = Math.min(a.screen.y, b.screen.y) - 12;
      const maxY = Math.max(a.screen.y, b.screen.y) + 12;
      const inside = screens.filter(
        (entry) =>
          entry.screen.x >= minX &&
          entry.screen.x <= maxX &&
          entry.screen.y >= minY &&
          entry.screen.y <= maxY,
      );
      if (inside.length === 2) {
        chosen = {
          ids: [a.id, b.id],
          start: { x: minX, y: minY },
          end: { x: maxX, y: maxY },
        };
      }
    }
  }
  expect(chosen).not.toBeNull();
  if (!chosen) {
    return;
  }
  await page.mouse.move(chosen.start.x, chosen.start.y);
  await page.mouse.down();
  await page.mouse.move(chosen.end.x, chosen.end.y, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(120);
  const selection = await page.evaluate(() => window.__TC_TEST__?.selection() ?? []);
  expect([...selection].sort((a, b) => a - b)).toEqual([...chosen.ids].sort((a, b) => a - b));
  const selectedUnits = (await units(page)).filter((unit) => unit.selected);
  expect(selectedUnits.every((unit) => unit.owner === 1)).toBe(true);
});

test('[INP-03] clicking an enemy with a selection lowers its HP', async ({ page }, testInfo) => {
  await enterGame(page);
  const touch = isTouch(testInfo);
  const all = await units(page);
  const own = all.filter((unit) => unit.owner === 1);
  const enemy = all.find((unit) => unit.owner === 2);
  const unit = own[0];
  expect(unit).toBeDefined();
  expect(enemy).toBeDefined();
  if (!unit || !enemy) {
    return;
  }
  const unitScreen = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    unit.id,
  );
  expect(unitScreen).not.toBeNull();
  if (!unitScreen) {
    return;
  }
  await selectUnit(page, unitScreen.x, unitScreen.y, touch);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toContain(
    unit.id,
  );

  await setCamera(page, { targetX: enemy.x, targetZ: enemy.z, distance: 45, yaw: 0 });
  const enemyScreen = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    enemy.id,
  );
  expect(enemyScreen).not.toBeNull();
  if (!enemyScreen) {
    return;
  }
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  await orderAt(page, enemyScreen.x, enemyScreen.y, touch);
  await expect
    .poll(
      async () => {
        const current = await units(page);
        return current.find((item) => item.id === enemy.id)?.hp ?? 0;
      },
      { timeout: 15000 },
    )
    .toBeLessThan(enemy.hp);
});

test('[INP-04] camera pan, zoom, rotate and edge clamping work', async ({ page }, testInfo) => {
  await enterGame(page);
  const touch = isTouch(testInfo);
  const start = await camera(page);

  if (touch) {
    await dispatchTouch(page, [
      { type: 'pointerdown', id: 1, x: 400, y: 300 },
      { type: 'pointermove', id: 1, x: 500, y: 300 },
      { type: 'pointerup', id: 1, x: 500, y: 300 },
    ]);
    await page.waitForTimeout(150);
    const panned = await camera(page);
    expect(Math.hypot(panned.targetX - start.targetX, panned.targetZ - start.targetZ)).toBeGreaterThan(0.1);

    const beforeZoom = await camera(page);
    await dispatchTouch(page, [
      { type: 'pointerdown', id: 2, x: 350, y: 300 },
      { type: 'pointerdown', id: 3, x: 450, y: 300 },
      { type: 'pointermove', id: 2, x: 300, y: 300 },
      { type: 'pointermove', id: 3, x: 500, y: 300 },
      { type: 'pointerup', id: 2, x: 300, y: 300 },
      { type: 'pointerup', id: 3, x: 500, y: 300 },
    ]);
    await page.waitForTimeout(150);
    const zoomed = await camera(page);
    expect(Math.abs(zoomed.distance - beforeZoom.distance)).toBeGreaterThan(0.1);

    const beforeTwist = await camera(page);
    await dispatchTouch(page, [
      { type: 'pointerdown', id: 4, x: 350, y: 300 },
      { type: 'pointerdown', id: 5, x: 450, y: 300 },
      { type: 'pointermove', id: 5, x: 400, y: 250 },
      { type: 'pointerup', id: 4, x: 350, y: 300 },
      { type: 'pointerup', id: 5, x: 400, y: 250 },
    ]);
    await page.waitForTimeout(150);
    const twisted = await camera(page);
    expect(Math.abs(twisted.yaw - beforeTwist.yaw)).toBeGreaterThan(0.01);
  } else {
    await page.keyboard.down('w');
    await page.waitForTimeout(350);
    await page.keyboard.up('w');
    const panned = await camera(page);
    expect(Math.hypot(panned.targetX - start.targetX, panned.targetZ - start.targetZ)).toBeGreaterThan(0.1);

    const beforeZoom = await camera(page);
    await page.mouse.move(800, 400);
    await page.mouse.wheel(0, -500);
    await page.waitForTimeout(150);
    const zoomed = await camera(page);
    expect(zoomed.distance).toBeLessThan(beforeZoom.distance);

    const beforeRotate = await camera(page);
    await page.keyboard.down('e');
    await page.waitForTimeout(350);
    await page.keyboard.up('e');
    const rotated = await camera(page);
    expect(Math.abs(rotated.yaw - beforeRotate.yaw)).toBeGreaterThan(0.01);
  }

  await setCamera(page, { targetX: -79, targetZ: -79, distance: 40, yaw: 0 });
  if (touch) {
    for (let i = 0; i < 4; i += 1) {
      const id = 10 + i;
      await dispatchTouch(page, [
        { type: 'pointerdown', id, x: 400, y: 300 },
        { type: 'pointermove', id, x: 100, y: 100 },
        { type: 'pointerup', id, x: 100, y: 100 },
      ]);
    }
  } else {
    await page.keyboard.down('a');
    await page.keyboard.down('w');
    await page.waitForTimeout(1200);
    await page.keyboard.up('a');
    await page.keyboard.up('w');
  }
  const clamped = await camera(page);
  expect(clamped.targetX).toBeGreaterThanOrEqual(-80);
  expect(clamped.targetX).toBeLessThanOrEqual(80);
  expect(clamped.targetZ).toBeGreaterThanOrEqual(-80);
  expect(clamped.targetZ).toBeLessThanOrEqual(80);
});

test('[INP-05] HUD button presses never issue map orders', async ({ page }, testInfo) => {
  await enterGame(page);
  const touch = isTouch(testInfo);
  const own = (await units(page)).filter((unit) => unit.owner === 1);
  const unit = own[0];
  expect(unit).toBeDefined();
  if (!unit) {
    return;
  }
  const unitScreen = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    unit.id,
  );
  expect(unitScreen).not.toBeNull();
  if (!unitScreen) {
    return;
  }
  await selectUnit(page, unitScreen.x, unitScreen.y, touch);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toContain(
    unit.id,
  );

  const pause = page.getByRole('button', { name: 'Pause', exact: true });
  const stop = page.getByRole('button', { name: 'Stop', exact: true });
  const deselect = page.getByRole('button', { name: 'Deselect', exact: true });
  if (touch) {
    await stop.tap();
  } else {
    await stop.click();
  }
  await page.waitForTimeout(120);
  const afterStop = (await units(page)).find((item) => item.id === unit.id);
  expect(afterStop?.orderX).toBeNull();

  if (touch) {
    await deselect.tap();
  } else {
    await deselect.click();
  }
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toEqual([]);

  await selectUnit(page, unitScreen.x, unitScreen.y, touch);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toContain(
    unit.id,
  );
  if (touch) {
    await pause.tap();
  } else {
    await pause.click();
  }
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'pause');
  const selectionInPause = await page.evaluate(() => window.__TC_TEST__?.selection() ?? []);
  expect(selectionInPause).toContain(unit.id);
  const orderInPause = (await units(page)).find((item) => item.id === unit.id);
  expect(orderInPause?.orderX).toBeNull();
  await page.getByRole('button', { name: 'Resume', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
});

test('[PLAY-01] full skirmish flow reaches results and Play again starts a fresh 4v4', async ({
  page,
}) => {
  // The spec allows up to 90 s of real time for the battle to resolve; the
  // project default (30 s) would kill the assertion before its own timeout.
  test.setTimeout(180_000);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return;
    }
    const current = hook.units();
    const own = current.filter((unit) => unit.owner === 1).map((unit) => unit.id);
    const enemy = current.find((unit) => unit.owner === 2);
    if (!enemy) {
      return;
    }
    hook.sendCommand({
      kind: 'attack',
      unitIds: own,
      targetId: enemy.id,
      tick: hook.snapshot().tick + 1,
      issuer: 1,
    });
  });
  await expect(page.locator('[data-screen-id="results"]')).toBeVisible({ timeout: 90_000 });
  const heading = await page.locator('[data-screen-id="results"] h1').textContent();
  expect(['Victory', 'Defeat', 'Draw']).toContain(heading ?? '');
  await page.getByRole('button', { name: 'Play again', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await expect.poll(async () => (await units(page)).length).toBe(8);
});

interface OrderCandidate {
  screen: { x: number; y: number };
  world: { x: number; z: number };
  minTankDistance: number;
}

async function findOrderCandidates(page: Page, tanks: TestUnit[]): Promise<OrderCandidate[]> {
  return page.evaluate((list) => {
    const hook = window.__TC_TEST__;
    const canvas = document.querySelector('canvas');
    if (!hook || !canvas) {
      return [];
    }
    const rect = canvas.getBoundingClientRect();
    const cam = hook.camera();
    const candidates: OrderCandidate[] = [];
    for (let dx = -48; dx <= 48; dx += 2) {
      for (let dz = -48; dz <= 48; dz += 2) {
        const wx = cam.targetX + dx;
        const wz = cam.targetZ + dz;
        if (Math.abs(wx) > 78 || Math.abs(wz) > 78) {
          continue;
        }
        const screen = hook.worldToScreen(wx, wz);
        if (screen.x < rect.left + 50 || screen.x > rect.right - 50) {
          continue;
        }
        if (screen.y < rect.top + 58 || screen.y > rect.bottom - 40) {
          continue;
        }
        if ((screen.y - rect.top) / rect.height > 0.45) {
          continue;
        }
        let minDistance = Number.POSITIVE_INFINITY;
        for (const tank of list) {
          minDistance = Math.min(minDistance, Math.hypot(wx - tank.x, wz - tank.z));
        }
        if (minDistance < 9) {
          continue;
        }
        candidates.push({ screen, world: { x: wx, z: wz }, minTankDistance: minDistance });
      }
    }
    candidates.sort((a, b) => b.minTankDistance - a.minTankDistance);
    return candidates.slice(0, 10);
  }, tanks.map((tank) => ({ x: tank.x, z: tank.z })));
}

test('[PLAY-02] drag-select then right-click a visible ground point moves every tank', async ({
  page,
}) => {
  test.setTimeout(180_000);
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().units ?? 0))
    .toBe(8);

  const own = (await units(page)).filter((unit) => unit.owner === 1);
  expect(own.length).toBe(4);

  const centres = await page.evaluate(
    (ids) => ids.map((id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null),
    own.map((unit) => unit.id),
  );
  const points = centres.filter((entry): entry is { x: number; y: number } => entry !== null);
  expect(points.length).toBe(4);
  if (points.length !== 4) {
    return;
  }

  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));

  await page.mouse.move(minX - 18, minY - 18);
  await page.mouse.down();
  await page.mouse.move(maxX + 18, maxY + 18, { steps: 8 });
  await page.mouse.up();

  await expect
    .poll(async () => (await page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).length)
    .toBe(4);
  const selected = await page.evaluate(() => window.__TC_TEST__?.selection() ?? []);
  expect(selected).toHaveLength(4);

  const candidates = await findOrderCandidates(page, own);
  expect(candidates.length, 'a visible ground point clear of the tanks').toBeGreaterThan(0);
  if (candidates.length === 0) {
    return;
  }

  const goals = new Map<number, { x: number; z: number }>();
  let chosen: OrderCandidate | null = null;
  for (const candidate of candidates) {
    if (candidate.minTankDistance < 12) {
      continue;
    }
    await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
    await page.mouse.click(candidate.screen.x, candidate.screen.y, { button: 'right' });
    await freezeAfterNextStep(page);
    const snapshot = await units(page);
    const attempt = new Map<number, { x: number; z: number }>();
    let accepted = true;
    for (const id of selected) {
      const start = snapshot.find((unit) => unit.id === id);
      if (!start || start.orderX === null || start.orderZ === null) {
        accepted = false;
        break;
      }
      const goal = { x: start.orderX, z: start.orderZ };
      if (Math.hypot(goal.x - candidate.world.x, goal.z - candidate.world.z) > 8.5) {
        accepted = false;
        break;
      }
      if (Math.hypot(goal.x - start.x, goal.z - start.z) < 4.5) {
        accepted = false;
        break;
      }
      attempt.set(id, goal);
    }
    await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
    if (accepted) {
      chosen = candidate;
      goals.clear();
      for (const [id, goal] of attempt) {
        goals.set(id, goal);
      }
      break;
    }
  }

  expect(chosen, 'the right-click issued a move order for the whole group').not.toBeNull();
  if (!chosen) {
    return;
  }

  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(4));
  const before = await units(page);
  await page.waitForTimeout(3000);
  const after = await units(page);

  for (const id of selected) {
    const start = before.find((unit) => unit.id === id);
    const end = after.find((unit) => unit.id === id);
    const goal = goals.get(id);
    expect(start, `tank ${id} exists before`).toBeDefined();
    expect(end, `tank ${id} exists after`).toBeDefined();
    expect(goal, `tank ${id} was given a goal`).toBeDefined();
    if (!start || !end || !goal) {
      return;
    }

    const closedOnGoal =
      Math.hypot(start.x - goal.x, start.z - goal.z) -
      Math.hypot(end.x - goal.x, end.z - goal.z);
    expect(closedOnGoal, `tank ${id} drove toward its ordered goal`).toBeGreaterThan(3);

    const closedOnClick =
      Math.hypot(start.x - chosen.world.x, start.z - chosen.world.z) -
      Math.hypot(end.x - chosen.world.x, end.z - chosen.world.z);
    expect(closedOnClick, `tank ${id} moved toward the clicked point`).toBeGreaterThan(3);
  }
});

test('[VIS-01] in-game screenshot is non-blank, colourful and shows eight units', async ({ page }) => {
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels ?? []))
    .toContain('unit.human.poc_tank');
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().units ?? 0))
    .toBe(8);
  const canvas = page.locator('canvas');
  const screenshot = await canvas.screenshot();
  expect(countDistinctPngColors(screenshot)).toBeGreaterThan(20);
  const stats = await page.evaluate(() => window.__TC_TEST__?.renderStats());
  expect(stats?.units).toBe(8);
});

test('[VIS-02] a player tank is at least 30 px on its longer side at the default camera', async ({
  page,
}) => {
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels ?? []))
    .toContain('unit.human.poc_tank');
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().units ?? 0))
    .toBe(8);

  const cam = await camera(page);
  expect(cam.distance).toBeCloseTo(40, 0);
  const pitchDeg = (cam.pitch * 180) / Math.PI;
  expect(pitchDeg).toBeGreaterThan(45);
  expect(pitchDeg).toBeLessThan(55);

  const own = (await units(page)).filter((unit) => unit.owner === 1);
  expect(own.length).toBe(4);
  for (const unit of own) {
    const bounds = await page.evaluate(
      (id) => window.__TC_TEST__?.unitScreenBounds(id) ?? null,
      unit.id,
    );
    expect(bounds, `bounds for tank ${unit.id}`).not.toBeNull();
    if (!bounds) {
      return;
    }
    const longerSide = Math.max(bounds.width, bounds.height);
    expect(
      longerSide,
      `tank ${unit.id} projects to ${bounds.width.toFixed(1)}x${bounds.height.toFixed(1)} px`,
    ).toBeGreaterThanOrEqual(30);
  }
});
