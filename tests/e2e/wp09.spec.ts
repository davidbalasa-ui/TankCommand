import { expect, test } from '@playwright/test';
import { gotoQuiet, waitForHook } from './helpers';

async function openTrainingMission(page: import('@playwright/test').Page, shots = false): Promise<void> {
  await page.getByRole('button', { name: 'Campaign', exact: true }).click();
  if (shots) {
    await page.screenshot({ path: 'test-results/shots/wp09-1-campaign-select.png' });
  }
  await page.getByRole('button', { name: 'Training', exact: true }).click();
  if (shots) {
    await page.screenshot({ path: 'test-results/shots/wp09-2-mission-select.png' });
  }
  await page.locator('[data-mission-id="mission.training.1_drops"]').click();
  if (shots) {
    await page.screenshot({ path: 'test-results/shots/wp09-3-briefing.png' });
  }
}

test('[MSN-05] locked missions are greyed, the next one unlocks on a win and progress survives a reload', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await gotoQuiet(page);
  await waitForHook(page);
  await page.getByRole('button', { name: 'Campaign', exact: true }).click();
  await page.getByRole('button', { name: 'Training', exact: true }).click();
  await expect(page.locator('[data-mission-id="mission.training.2_mining"]')).toBeDisabled();
  await page.locator('[data-mission-id="mission.training.1_drops"]').click();
  await page.getByRole('button', { name: 'Start mission', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');

  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  const padId = await page.evaluate(
    () => window.__TC_TEST__?.structures().find((s) => s.owner === 1 && s.kind === 'pad')?.id ?? 0,
  );
  // The Drops lesson, step by step: a Lancer, two Outriders, a drive to the ring, a Bastion Gun.
  const buy = async (itemId: string): Promise<void> => {
    await page.evaluate(
      ({ id, item }) => {
        const hook = window.__TC_TEST__;
        hook?.sendCommand({ kind: 'buy', itemId: item, padId: id, tick: (hook?.snapshot().tick ?? 0) + 1, issuer: 1 });
      },
      { id: padId, item: itemId },
    );
  };
  const ownUnits = async (): Promise<number> =>
    page.evaluate(() => window.__TC_TEST__?.units().filter((u) => u.owner === 1).length ?? 0);
  await buy('unit.human.light_tank');
  await expect.poll(ownUnits, { timeout: 30_000 }).toBeGreaterThanOrEqual(1);
  await buy('unit.human.scout');
  await expect.poll(ownUnits, { timeout: 30_000 }).toBeGreaterThanOrEqual(2);
  await buy('unit.human.scout');
  await expect.poll(ownUnits, { timeout: 30_000 }).toBeGreaterThanOrEqual(3);
  await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    const ids = hook?.units().filter((u) => u.owner === 1).map((u) => u.id) ?? [];
    hook?.sendCommand({ kind: 'move', unitIds: ids, x: -6, z: 10, tick: (hook?.snapshot().tick ?? 0) + 1, issuer: 1 });
  });
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.units().some((u) => u.owner === 1 && Math.hypot(u.x + 6, u.z - 10) < 7) ?? false), {
      timeout: 30_000,
    })
    .toBe(true);
  // Once the drive step is done, Command tops the ore up to the Bastion Gun's price.
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const snap = window.__TC_TEST__?.snapshot() as unknown as { resources: Array<{ player: number; ore: number }> };
          return snap.resources.find((r) => r.player === 1)?.ore ?? 0;
        }),
      { timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(150);
  await buy('structure.human.turret');
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'results', undefined, { timeout: 60_000 });
  await expect(page.getByRole('heading', { name: 'Mission complete' })).toBeVisible();
  await page.screenshot({ path: 'test-results/shots/wp09-6-mission-results.png' });
  await expect(page.getByRole('button', { name: 'Next mission', exact: true })).toBeVisible();

  await page.reload();
  await waitForHook(page);
  await page.getByRole('button', { name: 'Campaign', exact: true }).click();
  await page.getByRole('button', { name: 'Training', exact: true }).click();
  await expect(page.locator('[data-mission-id="mission.training.2_mining"]')).toBeEnabled();
  await expect(page.locator('[data-mission-id="mission.training.1_drops"]')).toBeEnabled();
});

test('[MSN-06] trigger messages show as a toast and the objectives sheet works by touch', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await gotoQuiet(page);
  await waitForHook(page);
  await openTrainingMission(page, true);
  // The toast lasts 6 s of wall time, which a slow runner's long frames can use up before the
  // next check gets a turn, so the page records every toast as it is added.
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { seenToasts: string[] }).seenToasts = seen;
    new MutationObserver(() => {
      for (const toast of document.querySelectorAll('.hud-toast')) {
        const text = toast.textContent ?? '';
        if (!seen.includes(text)) seen.push(text);
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  await page.getByRole('button', { name: 'Start mission', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await expect
    .poll(async () => page.evaluate(() => (window as unknown as { seenToasts: string[] }).seenToasts.join('\n')), {
      timeout: 30_000,
    })
    .toContain('Command');
  const open = page.getByRole('button', { name: 'Objectives', exact: true });
  await open.tap();
  // Lessons add each step's objective as the one before is done: the first is listed at the start.
  await expect(page.locator('.objective-list li')).toHaveCount(1);
  await page.screenshot({ path: 'test-results/shots/wp09-4-objectives-sheet.png' });
  await page.getByRole('button', { name: 'Close', exact: true }).tap();
  await expect(page.locator('.objective-list')).toHaveCount(0);
});

test('[HINT-01] the objective bubble grows to fit a full-length message instead of cutting it off', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only layout');
  await gotoQuiet(page);
  await waitForHook(page);
  await openTrainingMission(page);
  await page.getByRole('button', { name: 'Start mission', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await page.waitForFunction(() => (window.__TC_TEST__?.renderStats().frame ?? 0) > 0);
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(true));
  const line = page.locator('.hud-objective');
  await expect(line).toBeVisible();
  // A message at the word limit (20 words), with a speaker, as the longest a mission may send.
  const words = 'Station up. Send the spare Hauler to it, then tap the locked Mender in the drop menu to research it.';
  // Put the message in and measure in one go, before the HUD's next refresh can swap it back.
  const fit = await page.evaluate((text) => {
    const node = document.querySelector('.hud-objective') as HTMLElement;
    const target = node.querySelector('.hud-objective-text') as HTMLElement;
    target.innerHTML = `<span class="hud-toast"><strong>Command: </strong>${text}</span>`;
    node.classList.add('message', 'expanded');
    const box = node.getBoundingClientRect();
    return {
      clipped: target.scrollHeight > target.clientHeight + 1 || target.scrollWidth > target.clientWidth + 1,
      left: box.left,
      right: box.right,
      viewport: window.innerWidth,
      lines: Math.round(target.clientHeight / parseFloat(getComputedStyle(target).lineHeight)),
      shown: target.textContent ?? '',
    };
  }, words);
  await page.screenshot({ path: 'test-results/shots/hint-01-objective.png' });
  expect(fit.clipped).toBe(false);
  // Top right, in the right half of the screen, clear of the centre where the units are.
  expect(fit.left).toBeGreaterThanOrEqual(fit.viewport / 2);
  expect(fit.right).toBeLessThanOrEqual(fit.viewport - 4);
  expect(fit.lines).toBeLessThanOrEqual(3);
  expect(fit.shown).toContain('to research it.');
});

test('[SKR-01] every skirmish setup option takes effect in the started match', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem('setting.ai', 'off');
    } catch {
      // storage unavailable
    }
  });
  await page.goto('/');
  await waitForHook(page);
  await page.getByRole('button', { name: 'Skirmish', exact: true }).click();
  // Two AIs need a four-player map; the last map in the list is one.
  await page.getByRole('button', { name: 'Previous map', exact: true }).click();
  await expect(page.locator('.map-name')).toContainText('Up to 3 sides');
  await page.getByRole('radio', { name: 'Opponents: 2 AI' }).click();
  await expect(page.getByRole('radio', { name: 'Opponents: 2 AI' })).toHaveAttribute('aria-checked', 'true');
  await page.getByRole('radio', { name: 'Your side: Arcadians' }).click();
  await page.getByRole('radio', { name: 'Resources: High' }).click();
  await page.getByRole('radio', { name: 'Start with: Pad only' }).click();
  await page.getByRole('radio', { name: 'Fog of war: Off' }).click();
  await page.screenshot({ path: 'test-results/shots/wp09-5-skirmish-setup.png' });
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  const state = await page.evaluate(() => {
    const snap = window.__TC_TEST__?.snapshot() as unknown as {
      players: number[];
      fogEnabled: boolean;
      factions: Array<{ player: number; faction: string }>;
      resources: Array<{ player: number; ore: number }>;
    };
    return {
      players: snap.players.length,
      fog: snap.fogEnabled,
      faction: snap.factions.find((f) => f.player === 1)?.faction,
      ore: snap.resources.find((r) => r.player === 1)?.ore,
      units: window.__TC_TEST__?.units().filter((u) => u.owner === 1).length ?? -1,
    };
  });
  expect(state.players).toBe(3);
  expect(state.fog).toBe(false);
  expect(state.faction).toBe('alien');
  // High resources doubles the 600 starting ore (units cost ore only; see docs/decisions.md).
  expect(state.ore).toBe(1200);
  expect(state.units).toBe(0);
});
