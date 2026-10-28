import { expect, test, type Page, type TestInfo } from '@playwright/test';
import {
  countDistinctPngColors,
  enterGame,
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

async function setCamera(page: Page, info: Partial<TestCamera>): Promise<void> {
  await page.evaluate((camera) => {
    window.__TC_TEST__?.setCamera(camera);
  }, info);
  await page.waitForTimeout(80);
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

async function dispatchPointer(
  page: Page,
  type: string,
  id: number,
  x: number,
  y: number,
): Promise<void> {
  await page.evaluate(
    ({ eventType, pointerId, clientX, clientY }) => {
      const canvas = document.querySelector('canvas');
      if (!canvas) {
        return;
      }
      canvas.dispatchEvent(
        new PointerEvent(eventType, {
          bubbles: true,
          cancelable: true,
          pointerId,
          pointerType: 'touch',
          clientX,
          clientY,
          button: 0,
          buttons: eventType === 'pointerup' ? 0 : 1,
        }),
      );
    },
    { eventType: type, pointerId: id, clientX: x, clientY: y },
  );
}

interface SamplePoint {
  x: number;
  z: number;
  reachable: boolean;
}

/**
 * Two points sit within 10 world units of opposite map corners — the case where
 * ground picking is most likely to break (extreme zoom-out, camera far outside
 * the terrain bounds) — and three sit in the flattened start area at a known
 * distance from every tank, where the sim is guaranteed to accept the
 * destination exactly, so the resulting move order can be asserted too.
 */
const SAMPLE_POINTS: readonly SamplePoint[] = [
  { x: -68, z: -58, reachable: true },
  { x: -58, z: -68, reachable: true },
  { x: -64, z: -64, reachable: true },
  { x: 74, z: 74, reachable: false }, // 8.5 units from the (80, 80) corner
  { x: -74, z: 74, reachable: false }, // 8.5 units from the (-80, 80) corner
];

const CAMERA_SETTINGS = [
  { distance: 20, yaw: 0 },
  { distance: 60, yaw: 1 },
  { distance: 120, yaw: 2 },
];

test('[INP-01] ground picks and ground orders land at the picked point across camera settings', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await enterGame(page);
  const touch = isTouch(testInfo);
  const own = (await units(page)).filter((unit) => unit.owner === 1);
  const unit = own[0];
  expect(unit).toBeDefined();
  if (!unit) {
    return;
  }

  const deselect = page.getByRole('button', { name: 'Deselect', exact: true });
  const stop = page.getByRole('button', { name: 'Stop', exact: true });

  for (const setting of CAMERA_SETTINGS) {
    for (const point of SAMPLE_POINTS) {
      const label = `(${point.x}, ${point.z}) at distance ${setting.distance}`;

      if (touch) {
        await deselect.tap();
      } else {
        await deselect.click();
      }
      await expect
        .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
        .toEqual([]);

      if (point.reachable) {
        const current = (await units(page)).find((item) => item.id === unit.id);
        expect(current, label).toBeDefined();
        if (!current) {
          return;
        }
        await setCamera(page, {
          targetX: current.x,
          targetZ: current.z,
          distance: 60,
          yaw: 0,
        });
        const unitScreen = await page.evaluate(
          (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
          unit.id,
        );
        expect(unitScreen, label).not.toBeNull();
        if (!unitScreen) {
          return;
        }
        await selectUnit(page, unitScreen.x, unitScreen.y, touch);
        await expect
          .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
          .toContain(unit.id);
      }

      await setCamera(page, {
        targetX: point.x,
        targetZ: point.z,
        distance: setting.distance,
        yaw: setting.yaw,
      });

      const screen = await page.evaluate(
        ({ x, z }) => window.__TC_TEST__?.worldToScreen(x, z) ?? { x: 0, y: 0 },
        point,
      );
      await orderAt(page, screen.x, screen.y, touch);
      await freezeAfterNextStep(page);

      const picked = await page.evaluate(() => window.__TC_TEST__?.lastGroundPick() ?? null);
      expect(picked, label).not.toBeNull();
      expect(
        Math.hypot((picked?.x ?? 0) - point.x, (picked?.z ?? 0) - point.z),
        `${label}: ground pick (${picked?.x ?? 0}, ${picked?.z ?? 0})`,
      ).toBeLessThanOrEqual(1);

      if (point.reachable) {
        const ordered = (await units(page)).find((item) => item.id === unit.id);
        expect(ordered?.orderX, label).not.toBeNull();
        expect(ordered?.orderZ, label).not.toBeNull();
        expect(
          Math.hypot((ordered?.orderX ?? 0) - point.x, (ordered?.orderZ ?? 0) - point.z),
          `${label}: order (${ordered?.orderX ?? 0}, ${ordered?.orderZ ?? 0})`,
        ).toBeLessThanOrEqual(1);
        if (touch) {
          await stop.tap();
        } else {
          await stop.click();
        }
      }

      await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
    }
  }
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
    await dispatchPointer(page, 'pointerdown', 1, 400, 300);
    await dispatchPointer(page, 'pointermove', 1, 500, 300);
    await dispatchPointer(page, 'pointerup', 1, 500, 300);
    await page.waitForTimeout(150);
    const panned = await camera(page);
    expect(Math.hypot(panned.targetX - start.targetX, panned.targetZ - start.targetZ)).toBeGreaterThan(0.1);

    const beforeZoom = await camera(page);
    await dispatchPointer(page, 'pointerdown', 2, 350, 300);
    await dispatchPointer(page, 'pointerdown', 3, 450, 300);
    await dispatchPointer(page, 'pointermove', 2, 300, 300);
    await dispatchPointer(page, 'pointermove', 3, 500, 300);
    await dispatchPointer(page, 'pointerup', 2, 300, 300);
    await dispatchPointer(page, 'pointerup', 3, 500, 300);
    await page.waitForTimeout(150);
    const zoomed = await camera(page);
    expect(Math.abs(zoomed.distance - beforeZoom.distance)).toBeGreaterThan(0.1);

    const beforeTwist = await camera(page);
    await dispatchPointer(page, 'pointerdown', 4, 350, 300);
    await dispatchPointer(page, 'pointerdown', 5, 450, 300);
    await dispatchPointer(page, 'pointermove', 5, 400, 250);
    await dispatchPointer(page, 'pointerup', 4, 350, 300);
    await dispatchPointer(page, 'pointerup', 5, 400, 250);
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
      await dispatchPointer(page, 'pointerdown', 10 + i, 400, 300);
      await dispatchPointer(page, 'pointermove', 10 + i, 100, 100);
      await dispatchPointer(page, 'pointerup', 10 + i, 100, 100);
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

/**
 * Visible ground points in the upper part of the screen, farthest from the tanks
 * first. A player picks somewhere ahead of their units, so the candidates are
 * restricted to that band; ordering by clearance guarantees the tanks have room
 * to drive and cannot be at their destination already.
 */
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

  // Group moves give every tank its own formation slot, so the ordered goal is
  // near the click but not necessarily on it. Try the clearest visible points
  // until the simulation accepts the whole group's order with enough room for
  // every tank to make a visible move.
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
