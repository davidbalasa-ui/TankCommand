// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { createScreens } from '../../src/ui/screens';
import { ControlInventory } from '../../src/ui/controls';
import {
  ScreenRouter,
  type RendererHandle,
  type ScreenContext,
  type ScreenId,
} from '../../src/ui/router';

function makeContext(router: ScreenRouter): ScreenContext {
  return {
    router,
    go: (id) => {
      router.go(id);
    },
    pauseSim: () => undefined,
    attachRenderer: () =>
      Promise.resolve<RendererHandle>({ error: null, dispose: () => undefined }),
  };
}

const stubRouter = {
  go: () => undefined,
  back: () => undefined,
  current: () => 'title',
} as unknown as ScreenRouter;

function makeRoot(): HTMLDivElement {
  const root = document.createElement('div');
  document.body.append(root);
  return root;
}

describe('ui shell', () => {
  it('[UI-01] every screen mounts and unmounts without leaving nodes behind', () => {
    const screens = createScreens();
    const ids = Object.keys(screens) as ScreenId[];
    const ctx = makeContext(stubRouter);

    for (const id of ids) {
      const holder = document.createElement('div');
      document.body.append(holder);
      const screen = screens[id];
      const unmount = screen.mount(holder, ctx);
      unmount();
      expect(holder.childNodes.length).toBe(0);
      holder.remove();
    }
  });

  it('[UI-02] overlays stack and back pops settings then pause to inGame', () => {
    const root = makeRoot();
    const screens = createScreens();
    const router = new ScreenRouter(root, screens, (r) => makeContext(r));

    router.start('title');
    router.go('skirmishSetup');
    router.go('loading');
    router.go('inGame');
    router.go('pause');
    router.go('settings');

    expect(router.current()).toBe('settings');
    expect(root.querySelectorAll('[data-screen-id]').length).toBe(3);

    router.back();
    expect(router.current()).toBe('pause');
    expect(root.querySelectorAll('[data-screen-id="settings"]').length).toBe(0);

    router.back();
    expect(router.current()).toBe('inGame');
  });

  it('[UI-03] rapid repeated go to settings mounts only one settings root', () => {
    const root = makeRoot();
    const screens = createScreens();
    const router = new ScreenRouter(root, screens, (r) => makeContext(r));
    router.start('title');

    for (let i = 0; i < 20; i += 1) {
      router.go('settings');
    }

    expect(root.querySelectorAll('[data-screen-id="settings"]').length).toBe(1);
  });

  it('[UI-04] every registered control id is listed in the inventory file', () => {
    ControlInventory.clear();
    const screens = createScreens();
    const ctx = makeContext(stubRouter);
    const ids = Object.keys(screens) as ScreenId[];

    for (const id of ids) {
      const holder = document.createElement('div');
      document.body.append(holder);
      const unmount = screens[id].mount(holder, ctx);
      unmount();
      holder.remove();
    }

    const registered = ControlInventory.all();
    const listed = JSON.parse(
      readFileSync('tests/controls.inventory.json', 'utf8'),
    ) as string[];
    const missing = registered.filter((id) => !listed.includes(id));
    expect(missing).toEqual([]);
  });
});
