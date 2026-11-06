import { button } from './controls';

export interface ResearchNodeView {
  id: string;
  name: string;
  ore: number;
  metal: number;
  timeSec: number;
  state: 'done' | 'researching' | 'available' | 'locked';
  reason: string | null;
  progress: number;
}

export interface StructureActionView {
  id: number;
  name: string;
  kind: string;
  hpPercent: number;
  busy: 'pack' | 'dismantle' | null;
  canPack: boolean;
  canDismantle: boolean;
}

export interface UpgradeView {
  kind: 'fireRate' | 'armor' | 'stealth';
  label: string;
  have: boolean;
  reason: string | null;
}

export interface UnitActionView {
  id: number;
  name: string;
  hpPercent: number;
  canDeploy: boolean;
  deployReason: string | null;
  upgrades: UpgradeView[];
}

export interface BaseView {
  labId: number | null;
  labBusy: boolean;
  nodes: ResearchNodeView[];
  structures: StructureActionView[];
  units: UnitActionView[];
  ore: number;
  metal: number;
}

export type BaseAction =
  | { kind: 'research'; nodeId: string }
  | { kind: 'cancelResearch'; nodeId?: string }
  | { kind: 'pack'; structureId: number }
  | { kind: 'dismantle'; structureId: number }
  | { kind: 'deploy'; unitId: number }
  | { kind: 'upgrade'; targetId: number; upgrade: 'fireRate' | 'armor' | 'stealth' };

export interface BasePanelHost {
  getView: () => BaseView;
  act: (action: BaseAction) => boolean;
}

function dyn(id: string, label: string, onClick: () => void): HTMLButtonElement {
  const element = document.createElement('button');
  element.type = 'button';
  element.textContent = label;
  element.dataset.controlId = id;
  element.addEventListener('click', onClick);
  return element;
}

const REASONS: Record<string, string> = {
  prerequisite: 'Needs earlier research',
  unaffordable: 'Cannot afford',
  labBusy: 'Lab busy',
  noLab: 'Build a Lab first',
  notResearched: 'Not researched',
  alreadyHave: 'Owned',
};

export function reasonText(code: string | null): string | null {
  if (code === null) {
    return null;
  }
  return REASONS[code] ?? code;
}

// Bottom sheet for research, structure actions and per-vehicle actions. It is rebuilt only when
// its structure changes so taps stay stable across the HUD timer (see Hud.computeBuildSignature).
export class BasePanel {
  readonly element: HTMLDivElement;
  private readonly content: HTMLDivElement;
  private readonly host: BasePanelHost;
  private signature = '';
  private readonly bars = new Map<string, HTMLSpanElement>();
  private open = false;

  constructor(host: BasePanelHost, onClose: () => void) {
    this.host = host;
    this.element = document.createElement('div');
    this.element.className = 'hud-base-panel';
    this.element.dataset.hudItem = 'basePanel';
    const header = document.createElement('div');
    header.className = 'build-header';
    const title = document.createElement('span');
    title.textContent = 'Base and research';
    header.append(
      title,
      button('inGame', 'baseClose', 'Close', () => {
        onClose();
      }),
    );
    this.content = document.createElement('div');
    this.content.className = 'build-content';
    this.element.append(header, this.content);
  }

  setOpen(open: boolean): void {
    this.open = open;
    if (!open) {
      this.content.replaceChildren();
      this.signature = '';
    }
  }

  refresh(): void {
    if (!this.open) {
      return;
    }
    const view = this.host.getView();
    const signature = JSON.stringify(view, (key, value: unknown) =>
      key === 'progress' || key === 'hpPercent' ? undefined : value,
    );
    if (signature === this.signature) {
      for (const node of view.nodes) {
        const bar = this.bars.get(node.id);
        if (bar) {
          bar.style.width = `${Math.round(node.progress * 100)}%`;
        }
      }
      return;
    }
    this.signature = signature;
    this.bars.clear();
    this.content.replaceChildren();
    this.renderResearch(view);
    this.renderStructures(view);
    this.renderUnits(view);
  }

  private section(text: string): void {
    const title = document.createElement('div');
    title.className = 'build-section-title';
    title.textContent = text;
    this.content.append(title);
  }

  private act(action: BaseAction): void {
    this.host.act(action);
    this.signature = '';
    this.refresh();
  }

  private row(label: string, detail: string): { row: HTMLDivElement; bar: HTMLSpanElement } {
    const row = document.createElement('div');
    row.className = 'base-row';
    const text = document.createElement('span');
    text.className = 'base-row-text';
    text.textContent = label;
    const small = document.createElement('small');
    small.textContent = detail;
    text.append(small);
    const track = document.createElement('span');
    track.className = 'base-bar';
    const bar = document.createElement('span');
    track.append(bar);
    row.append(text, track);
    return { row, bar };
  }

  private renderResearch(view: BaseView): void {
    this.section(view.labId === null ? 'Research (build a Lab to research)' : 'Research');
    for (const node of view.nodes) {
      const cost = `${node.ore} O · ${node.metal} M · ${node.timeSec}s`;
      const state =
        node.state === 'done' ? 'Done' : node.state === 'researching' ? 'Researching' : (node.reason ?? '');
      const { row, bar } = this.row(node.name, `${cost}${state ? ` · ${state}` : ''}`);
      row.dataset.researchNode = node.id;
      row.dataset.researchState = node.state;
      this.bars.set(node.id, bar);
      bar.style.width = `${Math.round(node.progress * 100)}%`;
      if (node.state === 'researching') {
        const cancel = dyn(`inGame.cancelResearch.${node.id}`, 'Cancel', () => {
          this.act({ kind: 'cancelResearch', nodeId: node.id });
        });
        row.append(cancel);
      } else if (node.state !== 'done') {
        const start = dyn(`inGame.research.${node.id}`, 'Research', () => {
          this.act({ kind: 'research', nodeId: node.id });
        });
        start.disabled = node.state === 'locked' || view.labId === null || view.labBusy;
        row.append(start);
      }
      this.content.append(row);
    }
  }

  private renderStructures(view: BaseView): void {
    if (view.structures.length === 0) {
      return;
    }
    this.section('Structures');
    for (const item of view.structures) {
      const { row } = this.row(item.name, `${item.hpPercent}% hp${item.busy ? ` · ${item.busy}ing` : ''}`);
      row.dataset.structureId = String(item.id);
      if (item.canPack) {
        const pack = dyn(`inGame.pack.${item.id}`, 'Pack', () => {
          this.act({ kind: 'pack', structureId: item.id });
        });
        pack.disabled = item.busy !== null;
        row.append(pack);
      }
      if (item.canDismantle) {
        const dismantle = dyn(`inGame.dismantle.${item.id}`, 'Dismantle', () => {
          this.act({ kind: 'dismantle', structureId: item.id });
        });
        dismantle.disabled = item.busy !== null;
        row.append(dismantle);
      }
      this.content.append(row);
    }
  }

  private renderUnits(view: BaseView): void {
    if (view.units.length === 0) {
      return;
    }
    this.section('Selected vehicles');
    for (const unit of view.units) {
      const { row } = this.row(unit.name, `${unit.hpPercent}% hp`);
      row.dataset.unitId = String(unit.id);
      if (unit.canDeploy || unit.deployReason !== null) {
        const deploy = dyn(`inGame.deploy.${unit.id}`, 'Deploy', () => {
          this.act({ kind: 'deploy', unitId: unit.id });
        });
        deploy.disabled = !unit.canDeploy;
        row.append(deploy);
      }
      for (const upgrade of unit.upgrades) {
        const label = upgrade.have ? `${upgrade.label} ✓` : upgrade.label;
        const up = dyn(`inGame.upgrade.${unit.id}.${upgrade.kind}`, label, () => {
          this.act({ kind: 'upgrade', targetId: unit.id, upgrade: upgrade.kind });
        });
        up.disabled = upgrade.have || upgrade.reason !== null;
        if (upgrade.reason !== null && !upgrade.have) {
          up.title = upgrade.reason;
        }
        row.append(up);
      }
      this.content.append(row);
    }
  }
}
