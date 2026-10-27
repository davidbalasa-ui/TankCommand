export type ScreenId =
  | 'title'
  | 'campaignSelect'
  | 'missionSelect'
  | 'briefing'
  | 'skirmishSetup'
  | 'loading'
  | 'inGame'
  | 'pause'
  | 'settings'
  | 'help'
  | 'objectives'
  | 'results'
  | 'credits'
  | 'bugReport'
  | 'recovery';

export interface RendererHandle {
  error: string | null;
  dispose: () => void;
}

export interface ScreenContext {
  router: ScreenRouter;
  go: (id: ScreenId) => void;
  pauseSim: (paused: boolean) => void;
  attachRenderer: (canvas: HTMLCanvasElement) => Promise<RendererHandle>;
}

export interface ScreenModule {
  id: ScreenId;
  mount(root: HTMLElement, ctx: ScreenContext): () => void;
}

interface MountedScreen {
  id: ScreenId;
  el: HTMLDivElement;
  unmount: () => void;
}

const OVERLAY_IDS = new Set<ScreenId>(['pause', 'objectives', 'help', 'recovery', 'bugReport']);

const ALLOWED: Record<ScreenId, readonly ScreenId[]> = {
  title: ['campaignSelect', 'skirmishSetup', 'settings', 'credits', 'help'],
  campaignSelect: ['title', 'missionSelect'],
  missionSelect: ['campaignSelect', 'briefing'],
  briefing: ['missionSelect', 'loading'],
  skirmishSetup: ['title', 'loading'],
  loading: ['inGame', 'title'],
  inGame: ['pause', 'objectives', 'help', 'bugReport', 'recovery', 'results', 'title'],
  pause: ['settings', 'bugReport', 'title', 'inGame'],
  settings: ['title', 'pause', 'inGame'],
  help: ['title', 'inGame'],
  objectives: ['inGame'],
  results: ['title', 'missionSelect'],
  credits: ['title'],
  bugReport: ['title', 'inGame', 'pause'],
  recovery: ['inGame', 'title'],
};

const PARENT: Partial<Record<ScreenId, ScreenId>> = {
  campaignSelect: 'title',
  missionSelect: 'campaignSelect',
  briefing: 'missionSelect',
  skirmishSetup: 'title',
  loading: 'title',
  settings: 'title',
  help: 'title',
  objectives: 'inGame',
  results: 'title',
  credits: 'title',
  bugReport: 'inGame',
  recovery: 'inGame',
  pause: 'inGame',
};

export class ScreenRouter {
  private readonly root: HTMLElement;
  private readonly screens: Record<ScreenId, ScreenModule>;
  private readonly contextFactory: (router: ScreenRouter) => ScreenContext;
  private context: ScreenContext | null = null;
  private base: MountedScreen | null = null;
  private overlays: MountedScreen[] = [];

  constructor(
    root: HTMLElement,
    screens: Record<ScreenId, ScreenModule>,
    contextFactory: (router: ScreenRouter) => ScreenContext,
  ) {
    this.root = root;
    this.screens = screens;
    this.contextFactory = contextFactory;
  }

  start(id: ScreenId = 'title'): void {
    this.mountBase(id);
  }

  current(): ScreenId {
    return this.overlays.at(-1)?.id ?? this.base?.id ?? 'title';
  }

  go(id: ScreenId): void {
    const current = this.current();
    if (id === current) {
      return;
    }

    const overlay = this.isOverlayTarget(id, current);
    if (!this.canGo(current, id)) {
      this.reject(id);
      return;
    }

    if (overlay) {
      this.mountOverlay(id);
    } else {
      this.mountBase(id);
    }
  }

  back(): void {
    if (this.overlays.length > 0) {
      this.popOverlay();
      return;
    }
    if (!this.base) {
      return;
    }
    if (this.base.id === 'inGame') {
      this.go('pause');
      return;
    }
    const parent = PARENT[this.base.id];
    if (parent) {
      this.go(parent);
    }
  }

  private isOverlayTarget(id: ScreenId, current: ScreenId): boolean {
    if (id === 'settings') {
      return current === 'pause' && this.base?.id === 'inGame';
    }
    return OVERLAY_IDS.has(id) && this.base?.id === 'inGame';
  }

  private canGo(from: ScreenId, to: ScreenId): boolean {
    return ALLOWED[from].includes(to);
  }

  private reject(id: ScreenId): void {
    const message = `Screen transition not allowed: ${id}`;
    if (import.meta.env.DEV) {
      throw new Error(message);
    }
    console.warn(message);
  }

  private mountBase(id: ScreenId): void {
    for (const overlay of [...this.overlays].reverse()) {
      this.unmountScreen(overlay);
    }
    this.overlays = [];
    if (this.base) {
      this.unmountScreen(this.base);
    }
    const mounted = this.createScreen(id, false);
    mounted.el.style.visibility = 'visible';
    this.base = mounted;
  }

  private mountOverlay(id: ScreenId): void {
    const top = this.currentMounted();
    if (top) {
      top.el.style.visibility = 'hidden';
    }
    const mounted = this.createScreen(id, true);
    mounted.el.style.visibility = 'visible';
    this.overlays.push(mounted);
  }

  private popOverlay(): void {
    const mounted = this.overlays.pop();
    if (!mounted) {
      return;
    }
    this.unmountScreen(mounted);
    const top = this.currentMounted();
    if (top) {
      top.el.style.visibility = 'visible';
    }
  }

  private currentMounted(): MountedScreen | null {
    return this.overlays.at(-1) ?? this.base;
  }

  private createScreen(id: ScreenId, overlay: boolean): MountedScreen {
    const el = document.createElement('div');
    el.className = `screen screen-${id}${overlay ? ' overlay' : ''}`;
    el.dataset.screenId = id;
    this.root.append(el);
    const screen = this.screens[id];
    const unmount = screen.mount(el, this.ensureContext());
    return { id, el, unmount };
  }

  private unmountScreen(mounted: MountedScreen): void {
    mounted.unmount();
    mounted.el.remove();
  }

  private ensureContext(): ScreenContext {
    if (!this.context) {
      this.context = this.contextFactory(this);
    }
    return this.context;
  }
}
