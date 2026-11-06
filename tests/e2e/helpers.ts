import { expect, type Page } from '@playwright/test';
import { inflateSync } from 'node:zlib';

export interface TestSnapshot {
  tick: number;
  seed: number;
  rngState: number;
  counter: number;
  result: { winner: number | null } | null;
}

export interface TestUnit {
  id: number;
  owner: number;
  typeId: string;
  x: number;
  z: number;
  hp: number;
  selected: boolean;
  stance: 'free' | 'hold';
  orderKind: 'idle' | 'move' | 'attackMove' | 'attack';
  pathPoints: number;
  queued: boolean;
  orderX: number | null;
  orderZ: number | null;
  jobKind: string | null;
  jobStage: string | null;
  load: number;
  workerKind: string | null;
}

export interface TestStructure {
  id: number;
  owner: number;
  typeId: string;
  kind: string;
  x: number;
  z: number;
  hp: number;
  maxHp: number;
}

export interface TestDeposit {
  id: number;
  kind: 'ore' | 'metal';
  x: number;
  z: number;
  amount: number;
  maxAmount: number;
}

export interface TestResources {
  player: number;
  ore: number;
  metal: number;
  oreGathered: number;
  metalGathered: number;
  unitsBuilt: number;
  unitsLost: number;
}

export interface TestDropQueue {
  id: number;
  itemId: string;
  name: string;
  remainingSec: number;
  totalSec: number;
  progress: number;
}

export interface TestKit {
  id: number;
  structureTypeId: string;
  name: string;
}

export interface TestPlacement {
  kitId: number;
  structureTypeId: string;
  name: string;
  x: number;
  z: number;
  valid: boolean;
}

export interface TestBuildItem {
  id: string;
  name: string;
  kind: 'unit' | 'structure';
  ore: number;
  metal: number;
  deliverySec: number;
  disabledReason: string | null;
}

export interface TestDropState {
  queue: TestDropQueue[];
  kits: TestKit[];
  selectedPadId: number | null;
  unitCount: number;
  unitCap: number;
}

export interface TestCamera {
  targetX: number;
  targetZ: number;
  distance: number;
  yaw: number;
  pitch: number;
}

export interface GroundPick {
  x: number;
  z: number;
}

export interface ScreenBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface IssuedCommand {
  kind: 'move' | 'attackMove' | 'attack' | 'hold' | 'stop';
  x: number | null;
  z: number | null;
  targetId: number | null;
  unitIds: number[];
  queue: boolean;
}

export interface FreezeReport {
  channel: 'sim' | 'render';
  stalledMs: number;
  lastBeats: { sim: number; render: number };
}

export interface TestQuality {
  level: number;
  pixelRatio: number;
  shadows: boolean;
}

export interface RenderStats {
  loadedModels: string[];
  meshCount: number;
  drawCalls: number;
  frame: number;
  units: number;
}

export interface HudSnapshot {
  leftHanded: boolean;
  groupsOpen: boolean;
  queueMode: boolean;
  attackMoveArmed: boolean;
  selectedCount: number;
  ownUnits: number;
  enemyUnits: number;
  minimapFootprint: Array<{ x: number; z: number }>;
  minimapRedraws: number;
  commandButtonsDisabled: boolean;
  buildMenuOpen: boolean;
  baseOpen: boolean;
  ore: number;
  metal: number;
  workers: number;
  unitCount: number;
  unitCap: number;
  queue: TestDropQueue[];
  kits: TestKit[];
  selectedPadId: number | null;
  placementActive: boolean;
}

export interface TestHook {
  snapshot(): TestSnapshot;
  sendCommand(command: unknown): boolean;
  screen(): string;
  renderStats(): RenderStats;
  freezeSim(ms: number): void;
  pauseSim(paused: boolean): void;
  controls(): string[];
  go(screenId: string): void;
  units(): TestUnit[];
  structures(): TestStructure[];
  deposits(): TestDeposit[];
  resources(): TestResources[];
  worldToScreen(x: number, z: number): { x: number; y: number };
  lastGroundPick(): GroundPick | null;
  lastIssuedCommand(): IssuedCommand | null;
  lastFreezeReport(): FreezeReport | null;
  lastCommandOutcome(): {
    tick: number;
    kind: string;
    ok: boolean;
    reason: string;
  } | null;
  quality(): TestQuality;
  unitScreenCentre(id: number): { x: number; y: number } | null;
  unitScreenBounds(id: number): ScreenBounds | null;
  unitIsOnScreen(id: number): boolean;
  groundPickAt(x: number, y: number): GroundPick | null;
  selection(): number[];
  setSelection(ids: number[]): void;
  camera(): TestCamera;
  cameraFootprint(): Array<{ x: number; z: number }>;
  orderPaths(): Array<{ unitId: number; points: number; queued: boolean }>;
  inputState(): { longPressReady: boolean };
  hud(): HudSnapshot | null;
  buildItems(): TestBuildItem[];
  dropState(): TestDropState;
  placement(): TestPlacement | null;
  startPlacement(kitId: number): boolean;
  previewPlacement(x: number, z: number): void;
  confirmPlacement(): boolean;
  cancelPlacement(): void;
  alerts(): Array<{ x: number; z: number }>;
  setSimSpeed(multiplier: number): void;
  setCamera(info: Partial<TestCamera>): void;
}

declare global {
  interface Window {
    __TC_TEST__?: TestHook;
  }
}

export async function waitForHook(page: Page): Promise<void> {
  await page.waitForFunction(() => window.__TC_TEST__ !== undefined);
}

export async function enterGame(page: Page): Promise<void> {
  await page.goto('/');
  await waitForHook(page);
  await page.getByRole('button', { name: 'Skirmish', exact: true }).click();
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await page.waitForFunction(() => (window.__TC_TEST__?.renderStats().frame ?? 0) > 0);
}

export async function assertButtonLayout(page: Page): Promise<void> {
  const boxes = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('button')).filter(
      (element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return (
          style.visibility !== 'hidden' &&
          style.display !== 'none' &&
          rect.width > 0 &&
          rect.height > 0
        );
      },
    );

    return buttons.map((element) => {
      const rect = element.getBoundingClientRect();
      return {
        id: element.dataset.controlId ?? element.textContent ?? 'button',
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      };
    });
  });

  for (const box of boxes) {
    expect(box.width, `${box.id} width`).toBeGreaterThanOrEqual(44);
    expect(box.height, `${box.id} height`).toBeGreaterThanOrEqual(44);
  }

  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const a = boxes[i];
      const b = boxes[j];
      if (!a || !b) {
        continue;
      }
      const overlaps =
        a.x < b.x + b.width &&
        a.x + a.width > b.x &&
        a.y < b.y + b.height &&
        a.y + a.height > b.y;
      expect(overlaps, `${a.id} overlaps ${b.id}`).toBe(false);
    }
  }
}

export async function winSkirmish(page: Page): Promise<void> {
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  const padId = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return null;
    }
    return hook
      .structures()
      .find((structure) => structure.owner === 1 && structure.kind === 'pad')?.id ?? null;
  });
  if (padId === null) {
    throw new Error('No own landing pad');
  }
  await page.evaluate((id) => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return;
    }
    for (let i = 0; i < 10; i += 1) {
      hook.sendCommand({
        kind: 'buy',
        itemId: 'unit.human.scout',
        padId: id,
        tick: hook.snapshot().tick + 1,
        issuer: 1,
      });
    }
  }, padId);

  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const hook = window.__TC_TEST__;
          if (!hook) {
            return 0;
          }
          return hook.units().filter((unit) => unit.owner === 1 && unit.typeId === 'unit.human.scout').length;
        }),
      { timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(10);

  for (let attempt = 0; attempt < 80; attempt += 1) {
    const hasResult = await page.evaluate(() => window.__TC_TEST__?.snapshot().result !== null);
    if (hasResult) {
      break;
    }
    const targetId = await page.evaluate(() => {
      const hook = window.__TC_TEST__;
      if (!hook) {
        return null;
      }
      const enemyUnit = hook.units().find((unit) => unit.owner !== 1 && unit.hp > 0);
      if (enemyUnit) {
        return enemyUnit.id;
      }
      const enemyPad = hook
        .structures()
        .find((structure) => structure.owner !== 1 && structure.kind === 'pad' && structure.hp > 0);
      return enemyPad?.id ?? null;
    });
    if (targetId === null) {
      await expect
        .poll(async () => page.evaluate(() => window.__TC_TEST__?.snapshot().result !== null), {
          timeout: 10_000,
        })
        .toBe(true);
      break;
    }
    await page.evaluate((id) => {
      const hook = window.__TC_TEST__;
      if (!hook) {
        return;
      }
      const combat = hook
        .units()
        .filter(
          (unit) =>
            unit.owner === 1 &&
            (unit.typeId === 'unit.human.light_tank' || unit.typeId === 'unit.human.scout'),
        )
        .map((unit) => unit.id);
      if (combat.length === 0) {
        return;
      }
      hook.sendCommand({
        kind: 'attack',
        unitIds: combat,
        targetId: id,
        tick: hook.snapshot().tick + 1,
        issuer: 1,
      });
    }, targetId);
    await expect
      .poll(
        async () =>
          page.evaluate((id) => {
            const hook = window.__TC_TEST__;
            if (!hook) {
              return true;
            }
            const unitAlive = hook.units().some((unit) => unit.id === id && unit.hp > 0);
            const structureAlive = hook
              .structures()
              .some((structure) => structure.id === id && structure.hp > 0);
            return !unitAlive && !structureAlive ? true : hook.snapshot().result !== null;
          }, targetId),
        { timeout: 60_000 },
      )
      .toBe(true);
  }

  await expect(page.locator('[data-screen-id="results"]')).toBeVisible({ timeout: 60_000 });
}

export function countDistinctPngColors(buffer: Buffer): number {
  const signature = buffer.subarray(0, 8).toString('hex');
  if (signature !== '89504e470d0a1a0a') {
    throw new Error('Not a PNG');
  }

  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idat: Buffer[] = [];

  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8] ?? 0;
      colorType = data[9] ?? 0;
    } else if (type === 'IDAT') {
      idat.push(data);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }

  if (bitDepth !== 8 || (colorType !== 6 && colorType !== 2)) {
    throw new Error(`Unsupported PNG format: bitDepth=${bitDepth} colorType=${colorType}`);
  }

  const bpp = colorType === 6 ? 4 : 3;
  const stride = width * bpp;
  const raw = inflateSync(Buffer.concat(idat));
  const out = Buffer.alloc(stride * height);
  let pos = 0;

  for (let y = 0; y < height; y += 1) {
    const filter = raw[pos];
    pos += 1;
    if (filter === undefined) {
      throw new Error('Truncated PNG');
    }
    const rowStart = y * stride;
    for (let x = 0; x < stride; x += 1) {
      const rawByte = raw[pos];
      pos += 1;
      if (rawByte === undefined) {
        throw new Error('Truncated PNG');
      }
      const left = x >= bpp ? out[rowStart + x - bpp] ?? 0 : 0;
      const up = y > 0 ? out[rowStart - stride + x] ?? 0 : 0;
      const upLeft = y > 0 && x >= bpp ? out[rowStart - stride + x - bpp] ?? 0 : 0;
      let value = 0;
      if (filter === 0) {
        value = rawByte;
      } else if (filter === 1) {
        value = rawByte + left;
      } else if (filter === 2) {
        value = rawByte + up;
      } else if (filter === 3) {
        value = rawByte + Math.floor((left + up) / 2);
      } else if (filter === 4) {
        const p = left + up - upLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - upLeft);
        const predictor = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
        value = rawByte + predictor;
      } else {
        throw new Error(`Unsupported PNG filter ${filter}`);
      }
      out[rowStart + x] = value & 0xff;
    }
  }

  const colors = new Set<string>();
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * stride + x * bpp;
      colors.add(`${out[index] ?? 0},${out[index + 1] ?? 0},${out[index + 2] ?? 0}`);
    }
  }
  return colors.size;
}
