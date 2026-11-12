/**
 * Build drawer (UI redesign v1): a right-side "Orbital drop" drawer with Units /
 * Structures / Research tabs of cost cards and a queue strip along the bottom.
 *
 * Control ids are unchanged from the old bottom sheet (build.item.*, build.pad.*,
 * build.cancel.*, build.place.*, inGame.buildClose), so tests and the control
 * inventory keep working. Every tab is built and inactive tabs are hidden, so a
 * locked item can be found (and checked) without switching tabs.
 *
 * Like the old sheet it is rebuilt only when its structural signature changes;
 * live values (queue progress, ETA) are updated in place every HUD tick, so a
 * button is never detached under a finger or a test's tap.
 */
import { button } from './controls';
import { icon, resourceIcon } from './icons';
import { guardOpeningTap } from './widgets';
import type { BaseAction, BaseView, ResearchNodeView } from './basePanel';
import type { BuildItemView, DropQueueView, KitView } from './router';

export interface BuildDrawerHost {
  getBuildItems: () => BuildItemView[];
  getOwnPads: () => Array<{ id: number; x: number; z: number }>;
  getSelectedPadId: () => number | null;
  setSelectedPad: (id: number) => void;
  buyItem: (itemId: string) => boolean;
  getDropQueue: () => DropQueueView[];
  cancelOrder: (orderId: number) => void;
  getKits: () => KitView[];
  startPlacement: (kitId: number) => boolean;
  getBaseView: () => BaseView;
  baseAction: (action: BaseAction) => boolean;
  getResources: () => { ore: number; metal: number };
  thumbnail: (kind: 'unit' | 'structure', typeId: string) => string | null;
  close: () => void;
  openBase: () => void;
}

type Tab = 'unit' | 'structure' | 'research';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function costRow(ore: number, metal: number, seconds: number | null): HTMLSpanElement {
  const row = el('span', 'card-cost');
  if (ore > 0) {
    const part = el('span', 'cost-part');
    part.append(resourceIcon('ore', 12), String(ore));
    row.append(part);
  }
  if (metal > 0) {
    const part = el('span', 'cost-part');
    part.append(resourceIcon('metal', 12), String(metal));
    row.append(part);
  }
  if (seconds !== null) {
    row.append(el('span', 'cost-time', `${seconds.toFixed(0)}s`));
  }
  return row;
}

export class BuildDrawer {
  readonly element: HTMLDivElement;
  private readonly host: BuildDrawerHost;
  private readonly padSlot: HTMLDivElement;
  private readonly tabs = new Map<Tab, HTMLButtonElement>();
  private readonly panes = new Map<Tab, HTMLDivElement>();
  private readonly queueStrip: HTMLDivElement;
  private readonly progressRefs = new Map<number, HTMLElement>();
  private readonly thumbSlots: Array<{ slot: HTMLElement; kind: 'unit' | 'structure'; typeId: string }> = [];
  private eta: HTMLSpanElement | null = null;
  private tab: Tab = 'unit';
  private signature = '';
  private open = false;

  constructor(host: BuildDrawerHost) {
    this.host = host;
    this.element = el('div', 'hud-build-panel hud-drawer');
    this.element.dataset.hudItem = 'buildPanel';
    guardOpeningTap(this.element, () => this.open);

    const header = el('div', 'drawer-header');
    const title = el('h2', 'drawer-title', 'Orbital drop');
    this.padSlot = el('div', 'drawer-pads');
    const close = button('inGame', 'buildClose', 'Close', () => {
      this.host.close();
    });
    close.classList.add('drawer-close');
    close.setAttribute('aria-label', 'Close');
    close.replaceChildren(icon('x'));
    header.append(title, this.padSlot, close);

    const tabRow = el('div', 'drawer-tabs');
    tabRow.setAttribute('role', 'tablist');
    const labels: Array<[Tab, string]> = [
      ['unit', 'Units'],
      ['structure', 'Structures'],
      ['research', 'Research'],
    ];
    for (const [tab, label] of labels) {
      const node = el('button', 'drawer-tab', label);
      node.type = 'button';
      node.dataset.controlId = `build.tab.${tab}`;
      node.setAttribute('role', 'tab');
      node.addEventListener('click', () => {
        this.setTab(tab);
      });
      this.tabs.set(tab, node);
      tabRow.append(node);
      const pane = el('div', 'drawer-cards');
      pane.dataset.tab = tab;
      this.panes.set(tab, pane);
    }

    this.queueStrip = el('div', 'drawer-queue');
    this.element.append(header, tabRow, ...this.panes.values(), this.queueStrip);
    this.setTab('unit');
  }

  isOpen(): boolean {
    return this.open;
  }

  setOpen(open: boolean): void {
    this.open = open;
    if (!open) {
      this.element.querySelectorAll('.drawer-cards, .drawer-queue, .drawer-pads').forEach((node) => {
        node.replaceChildren();
      });
      this.progressRefs.clear();
      this.thumbSlots.length = 0;
      this.signature = '';
    }
    this.refresh();
  }

  setTab(tab: Tab): void {
    this.tab = tab;
    for (const [key, node] of this.tabs) {
      node.classList.toggle('on', key === tab);
      node.setAttribute('aria-selected', key === tab ? 'true' : 'false');
    }
    for (const [key, pane] of this.panes) {
      pane.hidden = key !== tab;
    }
  }

  private computeSignature(): string {
    const items = this.host.getBuildItems();
    const pads = this.host.getOwnPads();
    const queue = this.host.getDropQueue();
    const kits = this.host.getKits();
    const base = this.host.getBaseView();
    const parts: string[] = [`pad:${this.host.getSelectedPadId() ?? ''}`, pads.map((pad) => pad.id).join(',')];
    for (const item of items) {
      parts.push(`${item.id}|${item.name}|${item.ore}|${item.metal}|${item.deliverySec}|${item.disabledReason ?? ''}`);
    }
    parts.push('::queue::', ...queue.map((order) => `${order.id}|${order.itemId}`));
    parts.push('::kits::', ...kits.map((kit) => `${kit.id}|${kit.name}`));
    parts.push(`::lab:${base.labId ?? ''}:${base.labBusy}`);
    parts.push(...base.nodes.map((node) => `${node.id}|${node.state}|${node.reason ?? ''}`));
    // Affordability changes which reason a locked card shows.
    const res = this.host.getResources();
    parts.push(`res:${items.filter((item) => item.disabledReason === 'Cannot afford').map(() => `${res.ore}/${res.metal}`).join(',')}`);
    return parts.join(';');
  }

  refresh(): void {
    if (!this.open) {
      return;
    }
    const signature = this.computeSignature();
    if (signature !== this.signature) {
      this.signature = signature;
      this.rebuild();
    }
    this.updateLive();
  }

  private updateLive(): void {
    const queue = this.host.getDropQueue();
    for (const order of queue) {
      const bar = this.progressRefs.get(order.id);
      if (bar) {
        bar.style.width = `${Math.round(Math.min(1, Math.max(0, order.progress)) * 100)}%`;
      }
    }
    if (this.eta) {
      const first = queue[0];
      this.eta.textContent = first
        ? `${first.name} lands in ${Math.max(0, Math.ceil(first.remainingSec))}s · tap a drop to cancel it for a full refund`
        : '';
    }
    for (const entry of this.thumbSlots) {
      if (entry.slot.dataset.loaded === 'true') {
        continue;
      }
      const url = this.host.thumbnail(entry.kind, entry.typeId);
      if (url) {
        entry.slot.style.backgroundImage = `url(${url})`;
        entry.slot.dataset.loaded = 'true';
      }
    }
  }

  private thumb(className: string, kind: 'unit' | 'structure', typeId: string): HTMLSpanElement {
    const slot = el('span', className);
    slot.append(icon(kind === 'unit' ? 'unit' : 'base', 'thumb-fallback'));
    this.thumbSlots.push({ slot, kind, typeId });
    return slot;
  }

  private reasonText(item: BuildItemView, res: { ore: number; metal: number }): string | null {
    if (item.disabledReason !== 'Cannot afford') {
      return item.disabledReason;
    }
    const needs: string[] = [];
    if (item.ore > res.ore) {
      needs.push(`${item.ore - res.ore} more ore`);
    }
    if (item.metal > res.metal) {
      needs.push(`${item.metal - res.metal} more metal`);
    }
    return needs.length > 0 ? `Need ${needs.join(' and ')}` : item.disabledReason;
  }

  private rebuild(): void {
    this.progressRefs.clear();
    this.thumbSlots.length = 0;
    const items = this.host.getBuildItems();
    const queue = this.host.getDropQueue();
    const res = this.host.getResources();

    // Pad picker: one chip per own pad when there is a choice, else a label.
    const pads = this.host.getOwnPads();
    const selectedPad = this.host.getSelectedPadId();
    this.padSlot.replaceChildren();
    if (pads.length > 0) {
      this.padSlot.append(el('span', 'drawer-pad-label', 'Land at'));
    }
    for (const [index, pad] of pads.entries()) {
      const chip = el('button', `build-pad${pad.id === selectedPad ? ' active' : ''}`, `Pad ${index + 1}`);
      chip.type = 'button';
      chip.dataset.controlId = `build.pad.${pad.id}`;
      chip.addEventListener('click', () => {
        this.host.setSelectedPad(pad.id);
        this.refresh();
      });
      this.padSlot.append(chip);
    }

    const queued = new Map<string, number>();
    for (const order of queue) {
      queued.set(order.itemId, (queued.get(order.itemId) ?? 0) + 1);
    }
    for (const kind of ['unit', 'structure'] as const) {
      const pane = this.panes.get(kind);
      if (!pane) {
        continue;
      }
      pane.replaceChildren();
      for (const item of items.filter((entry) => entry.kind === kind)) {
        const card = el('button', 'build-item build-card');
        card.type = 'button';
        card.dataset.controlId = `build.item.${item.id}`;
        card.disabled = item.disabledReason !== null;
        card.append(this.thumb('card-thumb', kind, item.id), el('span', 'card-name build-item-name', item.name));
        card.append(costRow(item.ore, item.metal, item.deliverySec));
        const count = queued.get(item.id);
        if (count) {
          card.append(el('span', 'card-count', `×${count}`));
        }
        const reason = this.reasonText(item, res);
        if (reason) {
          const chip = el('span', 'card-reason build-reason');
          if (item.disabledReason !== 'Cannot afford') {
            chip.append(icon('lock'));
          } else {
            chip.classList.add('afford');
          }
          chip.append(reason);
          card.append(chip);
        }
        card.addEventListener('click', () => {
          this.host.buyItem(item.id);
          this.refresh();
        });
        pane.append(card);
      }
      if (pane.childElementCount === 0) {
        pane.append(el('p', 'build-empty', 'Nothing to order here yet.'));
      }
    }
    this.renderResearch();
    this.renderQueue(queue, this.host.getKits());
  }

  private renderResearch(): void {
    const pane = this.panes.get('research');
    if (!pane) {
      return;
    }
    pane.replaceChildren();
    const view = this.host.getBaseView();
    if (view.labId === null) {
      const note = el('div', 'research-note');
      note.append(el('span', '', 'Build a Lab to research upgrades.'));
      pane.append(note);
    }
    for (const node of view.nodes) {
      pane.append(this.researchCard(node, view));
    }
    const more = button('inGame', 'openBase', 'Open Base', () => {
      this.host.openBase();
    });
    more.classList.add('research-more');
    pane.append(more);
  }

  private researchCard(node: ResearchNodeView, view: BaseView): HTMLButtonElement {
    const card = el('button', 'build-card research-card');
    card.type = 'button';
    card.dataset.controlId = `build.research.${node.id}`;
    card.dataset.state = node.state;
    card.disabled = node.state !== 'available' || view.labId === null || view.labBusy;
    const top = el('span', 'research-icon');
    top.append(icon(node.state === 'done' ? 'star' : node.state === 'locked' ? 'lock' : 'gear'));
    card.append(top, el('span', 'card-name', node.name), costRow(node.ore, node.metal, node.timeSec));
    const status =
      node.state === 'done'
        ? 'Done'
        : node.state === 'researching'
          ? `Researching ${Math.round(node.progress * 100)}%`
          : view.labId === null
            ? (node.reason ?? 'Needs a Lab')
            : view.labBusy
              ? 'Lab busy'
              : node.reason;
    if (status) {
      card.append(el('span', `card-reason${node.state === 'done' ? ' done' : ''}`, status));
    }
    card.addEventListener('click', () => {
      this.host.baseAction({ kind: 'research', nodeId: node.id });
      this.refresh();
    });
    return card;
  }

  private renderQueue(queue: DropQueueView[], kits: KitView[]): void {
    this.queueStrip.replaceChildren();
    this.eta = null;
    if (kits.length > 0) {
      for (const kit of kits) {
        const place = el('button', 'build-place primary');
        place.type = 'button';
        place.dataset.controlId = `build.place.${kit.id}`;
        place.append(this.thumb('place-thumb', 'structure', kit.structureTypeId), el('span', '', `Place ${kit.name}`));
        place.addEventListener('click', () => {
          if (this.host.startPlacement(kit.id)) {
            this.host.close();
          }
        });
        this.queueStrip.append(place);
      }
    }
    this.queueStrip.append(el('span', 'queue-label', 'Queue'));
    if (queue.length === 0 && kits.length === 0) {
      this.queueStrip.append(el('span', 'queue-eta', 'Tap a card to order it. Drops land at the pad.'));
      return;
    }
    for (const order of queue) {
      const kind = order.itemId.startsWith('structure.') ? 'structure' : 'unit';
      const tile = el('button', 'build-cancel queue-tile');
      tile.type = 'button';
      tile.dataset.controlId = `build.cancel.${order.id}`;
      tile.setAttribute('aria-label', `Cancel ${order.name}`);
      const bar = el('span', 'queue-progress');
      this.progressRefs.set(order.id, bar);
      tile.append(this.thumb('queue-thumb', kind, order.itemId), el('span', 'queue-x', '×'), bar);
      tile.addEventListener('click', () => {
        this.host.cancelOrder(order.id);
        this.refresh();
      });
      this.queueStrip.append(tile);
    }
    this.eta = el('span', 'queue-eta');
    this.queueStrip.append(this.eta);
  }
}
