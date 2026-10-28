import { expect, type Page } from '@playwright/test';
import { inflateSync } from 'node:zlib';

export interface TestSnapshot {
  tick: number;
  seed: number;
  rngState: number;
  counter: number;
}

export interface TestUnit {
  id: number;
  owner: number;
  x: number;
  z: number;
  hp: number;
  selected: boolean;
  orderX: number | null;
  orderZ: number | null;
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
  kind: 'move' | 'attack';
  x: number | null;
  z: number | null;
  targetId: number | null;
  unitIds: number[];
}

export interface FreezeReport {
  channel: 'sim' | 'render';
  stalledMs: number;
  lastBeats: { sim: number; render: number };
}

export interface RenderStats {
  loadedModels: string[];
  meshCount: number;
  drawCalls: number;
  frame: number;
  units: number;
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
  worldToScreen(x: number, z: number): { x: number; y: number };
  lastGroundPick(): GroundPick | null;
  lastIssuedCommand(): IssuedCommand | null;
  lastFreezeReport(): FreezeReport | null;
  unitScreenCentre(id: number): { x: number; y: number } | null;
  unitScreenBounds(id: number): ScreenBounds | null;
  selection(): number[];
  camera(): TestCamera;
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
