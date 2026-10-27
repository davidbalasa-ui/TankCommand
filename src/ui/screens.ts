import { button } from './controls';
import type { RendererHandle, ScreenContext, ScreenId, ScreenModule } from './router';

type Build = (root: HTMLElement, ctx: ScreenContext) => void | (() => void);

function makeScreen(id: ScreenId, title: string, build?: Build): ScreenModule {
  return {
    id,
    mount(root, ctx) {
      root.replaceChildren();
      const heading = document.createElement('h1');
      heading.textContent = title;
      root.append(heading);
      const cleanup = build?.(root, ctx);
      return () => {
        cleanup?.();
        root.replaceChildren();
      };
    },
  };
}

function addButton(
  root: HTMLElement,
  screenId: string,
  name: string,
  label: string,
  onClick: () => void,
): void {
  root.append(button(screenId, name, label, onClick));
}

function emit(name: string): void {
  window.dispatchEvent(new CustomEvent(`tc:${name}`));
}

export function createScreens(): Record<ScreenId, ScreenModule> {
  const screens: Record<ScreenId, ScreenModule> = {
    title: makeScreen('title', 'TankCommand', (root, ctx) => {
      addButton(root, 'title', 'campaign', 'Campaign', () => {
        ctx.go('campaignSelect');
      });
      addButton(root, 'title', 'skirmish', 'Skirmish', () => {
        ctx.go('skirmishSetup');
      });
      addButton(root, 'title', 'settings', 'Settings', () => {
        ctx.go('settings');
      });
      addButton(root, 'title', 'credits', 'Credits', () => {
        ctx.go('credits');
      });
      addButton(root, 'title', 'help', 'Help', () => {
        ctx.go('help');
      });
    }),

    campaignSelect: makeScreen('campaignSelect', 'Campaign'),

    missionSelect: makeScreen('missionSelect', 'Select Mission'),

    briefing: makeScreen('briefing', 'Briefing'),

    skirmishSetup: makeScreen('skirmishSetup', 'Skirmish Setup', (root, ctx) => {
      addButton(root, 'skirmishSetup', 'start', 'Start', () => {
        ctx.go('loading');
      });
    }),

    loading: makeScreen('loading', 'Loading', (_root, ctx) => {
      const timer = window.setTimeout(() => {
        ctx.go('inGame');
      }, 200);
      return () => {
        window.clearTimeout(timer);
      };
    }),

    inGame: makeScreen('inGame', 'In Game', (root, ctx) => {
      const canvas = document.createElement('canvas');
      canvas.className = 'game-canvas';
      root.append(canvas);

      let disposed = false;
      let handle: RendererHandle | null = null;

      const showError = (message: string): void => {
        canvas.remove();
        const errorEl = document.createElement('p');
        errorEl.className = 'render-error';
        errorEl.textContent = message;
        root.prepend(errorEl);
      };

      void ctx
        .attachRenderer(canvas)
        .then((resolved) => {
          if (disposed) {
            resolved.dispose();
            return;
          }
          handle = resolved;
          if (resolved.error) {
            showError(resolved.error);
          }
        })
        .catch(() => {
          if (!disposed) {
            showError('3D rendering is unavailable on this device.');
          }
        });

      addButton(root, 'inGame', 'pause', 'Pause', () => {
        ctx.go('pause');
      });

      return () => {
        disposed = true;
        handle?.dispose();
      };
    }),

    pause: makeScreen('pause', 'Paused', (root, ctx) => {
      ctx.pauseSim(true);
      addButton(root, 'pause', 'resume', 'Resume', () => {
        ctx.router.back();
      });
      addButton(root, 'pause', 'settings', 'Settings', () => {
        ctx.go('settings');
      });
      addButton(root, 'pause', 'bugReport', 'Report bug', () => {
        ctx.go('bugReport');
      });
      addButton(root, 'pause', 'quit', 'Quit to title', () => {
        ctx.go('title');
      });
      return () => {
        ctx.pauseSim(false);
      };
    }),

    settings: makeScreen('settings', 'Settings', (root, ctx) => {
      addButton(root, 'settings', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    help: makeScreen('help', 'Help', (root, ctx) => {
      addButton(root, 'help', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    objectives: makeScreen('objectives', 'Objectives'),

    results: makeScreen('results', 'Results'),

    credits: makeScreen('credits', 'Credits', (root, ctx) => {
      const text = document.createElement('pre');
      text.className = 'credits-text';
      text.textContent = 'Loading credits...';
      root.append(text);
      let cancelled = false;
      void Promise.resolve()
        .then(() => fetch('./CREDITS.md'))
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.text();
        })
        .then((content) => {
          if (!cancelled) {
            text.textContent = content;
          }
        })
        .catch(() => {
          if (!cancelled) {
            text.textContent = 'Credits are unavailable in this environment.';
          }
        });
      addButton(root, 'credits', 'back', 'Back', () => {
        ctx.router.back();
      });
      return () => {
        cancelled = true;
      };
    }),

    bugReport: makeScreen('bugReport', 'Report Bug', (root, ctx) => {
      addButton(root, 'bugReport', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    recovery: makeScreen('recovery', 'Recovery', (root) => {
      addButton(root, 'recovery', 'resume', 'Resume', () => {
        emit('recovery-resume');
      });
      addButton(root, 'recovery', 'loadAutosave', 'Load autosave', () => {
        emit('recovery-load-autosave');
      });
      addButton(root, 'recovery', 'reportBug', 'Send bug report & return to menu', () => {
        emit('recovery-report-bug');
      });
    }),
  };

  return screens;
}
