/**
 * Build queue strip (overhaul step 3): a row of tiles along the top of the match screen, one per
 * order on its way down and one per structure kit waiting to be placed.
 *
 * - An order tile shows a picture, a thin progress bar and the cost. Tapping it cancels the order
 *   for a full refund, and an Undo chip stays for 3 seconds in case the tap was a slip.
 * - A kit tile ("Place") goes straight to the placement ghost.
 * - The strip is the only place orders show; when one lands its tile simply leaves.
 *
 * Control ids match the old drawer queue (build.cancel.<orderId>, build.place.<kitId>) so tests
 * and the control inventory keep working.
 */
import { resourceIcon } from './icons';
import type { DropQueueView, KitView } from './router';

export interface QueueStripHost {
  getDropQueue: () => DropQueueView[];
  getKits: () => KitView[];
  cancelOrder: (orderId: number) => void;
  /** Orders the same item again (Undo after a cancel). */
  buyItem: (itemId: string) => boolean;
  startPlacement: (kitId: number) => boolean;
  /** Ore and metal price of an item, for the tile's cost line. */
  itemCost: (itemId: string) => { ore: number; metal: number } | null;
  thumbnail: (kind: 'unit' | 'structure', typeId: string) => string | null;
  /** Called after a tap changed something, so the HUD can refresh at once. */
  changed: () => void;
}

export const UNDO_MS = 3000;

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

export class QueueStrip {
  readonly element: HTMLDivElement;
  private readonly host: QueueStripHost;
  private readonly tiles: HTMLDivElement;
  private readonly undoButton: HTMLButtonElement;
  private readonly progress = new Map<number, HTMLElement>();
  private readonly thumbs: Array<{ slot: HTMLElement; kind: 'unit' | 'structure'; typeId: string }> = [];
  private signature = '';
  private undo: { itemId: string; name: string; until: number } | null = null;

  constructor(host: QueueStripHost) {
    this.host = host;
    this.element = el('div', 'hud-queue');
    this.element.dataset.hudItem = 'queue';
    this.tiles = el('div', 'hud-queue-tiles');
    this.undoButton = el('button', 'hud-queue-undo');
    this.undoButton.type = 'button';
    this.undoButton.dataset.controlId = 'inGame.queueUndo';
    this.undoButton.hidden = true;
    this.undoButton.addEventListener('click', () => {
      const undo = this.undo;
      this.undo = null;
      if (undo && performance.now() <= undo.until) {
        this.host.buyItem(undo.itemId);
      }
      this.host.changed();
    });
    this.element.append(this.tiles, this.undoButton);
  }

  /** True while the strip has anything to show (it takes no room otherwise). */
  isShown(): boolean {
    return !this.element.hidden;
  }

  refresh(): void {
    const queue = this.host.getDropQueue();
    const kits = this.host.getKits();
    const now = performance.now();
    if (this.undo && now > this.undo.until) {
      this.undo = null;
    }
    const signature = [
      ...kits.map((kit) => `k${kit.id}`),
      ...queue.map((order) => `o${order.id}|${order.itemId}`),
    ].join(',');
    if (signature !== this.signature) {
      this.signature = signature;
      this.rebuild(queue, kits);
    }
    for (const order of queue) {
      const bar = this.progress.get(order.id);
      if (bar) {
        bar.style.width = `${Math.round(Math.min(1, Math.max(0, order.progress)) * 100)}%`;
      }
    }
    for (const entry of this.thumbs) {
      if (entry.slot.dataset.loaded === 'true') {
        continue;
      }
      const url = this.host.thumbnail(entry.kind, entry.typeId);
      if (url) {
        entry.slot.replaceChildren();
        entry.slot.style.backgroundImage = `url(${url})`;
        entry.slot.dataset.loaded = 'true';
      }
    }
    this.undoButton.hidden = this.undo === null;
    if (this.undo) {
      const text = `Undo · ${this.undo.name}`;
      if (this.undoButton.textContent !== text) {
        this.undoButton.textContent = text;
      }
    }
    this.element.hidden = queue.length === 0 && kits.length === 0 && this.undo === null;
  }

  private thumb(kind: 'unit' | 'structure', typeId: string): HTMLSpanElement {
    const slot = el('span', 'hud-queue-thumb');
    this.thumbs.push({ slot, kind, typeId });
    return slot;
  }

  private rebuild(queue: DropQueueView[], kits: KitView[]): void {
    this.progress.clear();
    this.thumbs.length = 0;
    this.tiles.replaceChildren();
    for (const kit of kits) {
      const tile = el('button', 'hud-queue-tile place');
      tile.type = 'button';
      tile.dataset.controlId = `build.place.${kit.id}`;
      tile.setAttribute('aria-label', `Place ${kit.name}`);
      tile.append(this.thumb('structure', kit.structureTypeId), el('span', 'hud-queue-cost', 'Place'));
      tile.addEventListener('click', () => {
        this.host.startPlacement(kit.id);
        this.host.changed();
      });
      this.tiles.append(tile);
    }
    for (const order of queue) {
      const kind = order.itemId.startsWith('structure.') ? 'structure' : 'unit';
      const tile = el('button', 'hud-queue-tile');
      tile.type = 'button';
      tile.dataset.controlId = `build.cancel.${order.id}`;
      tile.setAttribute('aria-label', `Cancel ${order.name}`);
      const bar = el('span', 'hud-queue-progress');
      const track = el('span', 'hud-queue-track');
      track.append(bar);
      this.progress.set(order.id, bar);
      const cost = el('span', 'hud-queue-cost');
      const price = this.host.itemCost(order.itemId);
      if (price && price.ore > 0) {
        cost.append(resourceIcon('ore', 10), String(price.ore));
      }
      if (price && price.metal > 0) {
        cost.append(resourceIcon('metal', 10), String(price.metal));
      }
      tile.append(this.thumb(kind, order.itemId), track, cost);
      tile.addEventListener('click', () => {
        this.host.cancelOrder(order.id);
        this.undo = { itemId: order.itemId, name: order.name, until: performance.now() + UNDO_MS };
        this.host.changed();
      });
      this.tiles.append(tile);
    }
  }
}
