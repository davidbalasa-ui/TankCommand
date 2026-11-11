import { button } from './controls';
import { Hud } from './hud';
import { drawMapPreview } from './mapPreview';
import type {
  CampaignId,
  RendererHandle,
  ScreenContext,
  ScreenId,
  ScreenModule,
  SkirmishConfig,
} from './router';
import { mountBugReport } from './bugReport';
import { mountSaveSlots } from './saveSlots';
import { mountSettings } from './settingsScreen';
import { mountSpeedButton } from './speedButton';
import { SIM_SPEED_FAST, SIM_SPEED_NORMAL, SIM_SPEED_SLOW } from '../sim/tuning';
import { SIM_TICK_HZ } from '../sim/constants';

// Working faction names (C-03). Final public names need David's approval.
export const FACTION_NAMES = { human: 'Terran Coalition', alien: 'Kesh' } as const;

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

function addButtonTo(
  parent: HTMLElement,
  screenId: string,
  name: string,
  label: string,
  onClick: () => void,
): void {
  parent.append(button(screenId, name, label, onClick));
}

function addButton(
  root: HTMLElement,
  screenId: string,
  name: string,
  label: string,
  onClick: () => void,
): void {
  addButtonTo(root, screenId, name, label, onClick);
}

function emit(name: string): void {
  window.dispatchEvent(new CustomEvent(`tc:${name}`));
}

function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

export function createScreens(): Record<ScreenId, ScreenModule> {
  const screens: Record<ScreenId, ScreenModule> = {
    title: makeScreen('title', 'TankCommand', (root, ctx) => {
      if (ctx.api) {
        const resume = button('title', 'resume', 'Resume last game', () => {
          void ctx.api?.resumeLastGame();
        });
        resume.style.display = 'none';
        root.append(resume);
        void ctx.api
          .latestAutosave()
          .then((latest) => {
            if (latest) {
              resume.style.display = '';
            } else {
              resume.remove();
            }
          })
          .catch(() => {
            resume.remove();
          });
      }
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

    campaignSelect: makeScreen('campaignSelect', 'Campaign', (root, ctx) => {
      const choices: Array<[CampaignId, string]> = [
        ['training', 'Training'],
        ['human', `${FACTION_NAMES.human} campaign`],
        ['alien', `${FACTION_NAMES.alien} campaign`],
      ];
      for (const [id, label] of choices) {
        addButton(root, 'campaignSelect', id, label, () => {
          ctx.chooseCampaign?.(id);
          ctx.go('missionSelect');
        });
      }
      addButton(root, 'campaignSelect', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    missionSelect: makeScreen('missionSelect', 'Select Mission', (root, ctx) => {
      const list = ctx.getMissionList?.() ?? [];
      for (const item of list) {
        const label = `${item.order}. ${item.title}${item.status === 'done' ? ' ✓' : item.status === 'locked' ? ' (locked)' : ''}`;
        const entry = button('missionSelect', 'mission', label, () => {
          if (item.status !== 'locked' && ctx.chooseMission?.(item.id)) {
            ctx.go('briefing');
          }
        });
        entry.disabled = item.status === 'locked';
        entry.dataset.missionId = item.id;
        entry.dataset.status = item.status;
        root.append(entry);
      }
      addButton(root, 'missionSelect', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    briefing: makeScreen('briefing', 'Briefing', (root, ctx) => {
      const view = ctx.getBriefing?.() ?? null;
      const heading = root.querySelector('h1');
      if (view && heading) {
        heading.textContent = view.title;
      }
      const body = document.createElement('div');
      body.className = 'briefing-body';
      if (view) {
        const preview = document.createElement('canvas');
        preview.className = 'briefing-map';
        preview.setAttribute('aria-label', 'Map preview');
        drawMapPreview(preview, view.map);
        const text = document.createElement('div');
        text.className = 'briefing-text';
        const paragraph = document.createElement('p');
        paragraph.textContent = view.text;
        const objectives = document.createElement('ul');
        objectives.className = 'briefing-objectives';
        for (const objective of view.objectives) {
          const item = document.createElement('li');
          item.textContent = objective.kind === 'optional' ? `Optional: ${objective.text}` : objective.text;
          objectives.append(item);
        }
        text.append(paragraph, objectives);
        body.append(preview, text);
      }
      root.append(body);
      const row = document.createElement('div');
      row.className = 'button-row';
      row.append(
        button('briefing', 'start', 'Start mission', () => {
          ctx.go('loading');
        }),
        button('briefing', 'back', 'Back', () => {
          ctx.router.back();
        }),
      );
      root.append(row);
    }),

    skirmishSetup: makeScreen('skirmishSetup', 'Skirmish Setup', (root, ctx) => {
      const fallback: SkirmishConfig = {
        mapId: '',
        faction: 'human',
        opponents: [{ faction: 'alien', difficulty: 'normal' }],
        resources: 'normal',
        force: 'padForce',
        fog: true,
      };
      let config: SkirmishConfig = ctx.getSkirmishConfig?.() ?? fallback;
      const maps = ctx.getSkirmishMaps?.() ?? [];
      const grid = document.createElement('div');
      grid.className = 'setup-grid';
      root.append(grid);
      const cycle = <T,>(values: readonly T[], current: T): T => {
        const index = values.indexOf(current);
        return values[(index + 1) % values.length] ?? current;
      };
      const label = (text: string): string =>
        text === 'human' || text === 'alien' ? FACTION_NAMES[text] : text.charAt(0).toUpperCase() + text.slice(1);
      const render = (): void => {
        grid.replaceChildren();
        const set = (next: SkirmishConfig): void => {
          config = next;
          ctx.setSkirmishConfig?.(next);
          render();
        };
        const map = maps.find((m) => m.id === config.mapId) ?? maps[0];
        const add = (name: string, text: string, onClick: () => void): void => {
          grid.append(button('skirmishSetup', name, text, onClick));
        };
        add('map', `Map: ${map?.name ?? 'Default'}`, () => {
          const ids = maps.map((m) => m.id);
          set({ ...config, mapId: cycle(ids, config.mapId || (ids[0] ?? '')) });
        });
        add('faction', `You: ${label(config.faction)}`, () => {
          set({ ...config, faction: config.faction === 'human' ? 'alien' : 'human' });
        });
        add('opponents', `Opponents: ${config.opponents.length}`, () => {
          const count = (config.opponents.length % 3) + 1;
          const opponents = Array.from({ length: count }, (_, i) => config.opponents[i] ?? { faction: 'alien' as const, difficulty: 'normal' as const });
          set({ ...config, opponents });
        });
        config.opponents.forEach((opponent, index) => {
          add(`opp${index + 1}Faction`, `AI ${index + 1}: ${label(opponent.faction)}`, () => {
            const opponents = config.opponents.map((o, i) =>
              i === index ? { ...o, faction: o.faction === 'human' ? ('alien' as const) : ('human' as const) } : o,
            );
            set({ ...config, opponents });
          });
          add(`opp${index + 1}Difficulty`, `AI ${index + 1} level: ${label(opponent.difficulty)}`, () => {
            const opponents = config.opponents.map((o, i) =>
              i === index ? { ...o, difficulty: cycle(['easy', 'normal', 'hard'] as const, o.difficulty) } : o,
            );
            set({ ...config, opponents });
          });
        });
        add('resources', `Resources: ${label(config.resources)}`, () => {
          set({ ...config, resources: cycle(['low', 'normal', 'high'] as const, config.resources) });
        });
        add('force', `Start: ${config.force === 'padOnly' ? 'Pad only' : 'Pad + force'}`, () => {
          set({ ...config, force: config.force === 'padOnly' ? 'padForce' : 'padOnly' });
        });
        add('fog', `Fog: ${config.fog ? 'On' : 'Revealed'}`, () => {
          set({ ...config, fog: !config.fog });
        });
      };
      render();
      const row = document.createElement('div');
      row.className = 'button-row';
      row.append(
        button('skirmishSetup', 'start', 'Start', () => {
          ctx.beginSkirmish?.();
          ctx.go('loading');
        }),
        button('skirmishSetup', 'back', 'Back', () => {
          ctx.router.back();
        }),
      );
      root.append(row);
    }),

    loading: makeScreen('loading', 'Loading', (_root, ctx) => {
      const timer = window.setTimeout(() => {
        ctx.go('inGame');
      }, 200);
      return () => {
        window.clearTimeout(timer);
      };
    }),

    inGame: makeScreen('inGame', '', (root, ctx) => {
      const heading = root.querySelector('h1');
      heading?.remove();

      const canvas = document.createElement('canvas');
      canvas.className = 'game-canvas';
      root.append(canvas);

      const getWorld = ctx.getWorld;
      let hud: Hud | null = null;
      if (getWorld) {
        hud = new Hud(root, {
          getWorld,
          getSelection: () => ctx.selection?.() ?? [],
          setSelection: (ids) => {
            ctx.setSelection?.(ids);
          },
          sendCommand: (command) => ctx.sendCommand?.(command) ?? false,
          getCamera: () =>
            ctx.getCamera?.() ?? {
              targetX: 0,
              targetZ: 0,
              distance: 40,
              yaw: 0,
              pitch: 0,
            },
          cameraFootprint: () => ctx.cameraFootprint?.() ?? [],
          setCameraTarget: (x, z) => {
            ctx.setCameraTarget?.(x, z);
          },
          isLeftHanded: () => ctx.isLeftHanded?.() ?? false,
          setLeftHanded: (value) => {
            ctx.setLeftHanded?.(value);
          },
          isQueueMode: () => ctx.isQueueMode?.() ?? false,
          setQueueMode: (value) => {
            ctx.setQueueMode?.(value);
          },
          isAttackMoveArmed: () => ctx.isAttackMoveArmed?.() ?? false,
          setAttackMoveArmed: (value) => {
            ctx.setAttackMoveArmed?.(value);
          },
          assignGroup: (group) => {
            ctx.assignGroup?.(group);
          },
          selectGroup: (group) => {
            ctx.selectGroup?.(group);
          },
          centerGroup: (group) => {
            ctx.centerGroup?.(group);
          },
          groupMembers: (group) => ctx.groupMembers?.(group) ?? [],
          pause: () => {
            ctx.go('pause');
          },
          openObjectives: () => {
            ctx.go('objectives');
          },
          getBuildItems: () => ctx.getBuildItems?.() ?? [],
          getOwnPads: () => ctx.getOwnPads?.() ?? [],
          getSelectedPadId: () => ctx.getSelectedPadId?.() ?? null,
          setSelectedPad: (id) => {
            ctx.setSelectedPad?.(id);
          },
          buyItem: (itemId) => ctx.buyItem?.(itemId) ?? false,
          getDropQueue: () => ctx.getDropQueue?.() ?? [],
          cancelOrder: (orderId) => {
            ctx.cancelOrder?.(orderId);
          },
          getKits: () => ctx.getKits?.() ?? [],
          startPlacement: (kitId) => ctx.startPlacement?.(kitId) ?? false,
          getPlacement: () => ctx.getPlacement?.() ?? null,
          confirmPlacement: () => ctx.confirmPlacement?.() ?? false,
          cancelPlacement: () => {
            ctx.cancelPlacement?.();
          },
          getWorkerActions: () =>
            ctx.getWorkerActions?.() ?? {
              canMine: false,
              canAssign: false,
              canSalvage: false,
            },
          getBaseView: () => ctx.getBaseView?.() ?? { labId: null, labBusy: false, nodes: [], structures: [], units: [], ore: 0, metal: 0 },
          baseAction: (action) => ctx.baseAction?.(action) ?? false,
          salvageSelected: () => {
            ctx.salvageSelected?.();
          },
        });
        ctx.registerHud?.(hud);
      }

      const disposeSpeedButton = mountSpeedButton(root, ctx.api);

      let disposed = false;
      let handle: RendererHandle | null = null;
      let resultShown = false;

      const updateResult = (): void => {
        const world = ctx.getWorld?.();
        if (!world) {
          return;
        }
        if (world.result && !resultShown) {
          resultShown = true;
          ctx.go('results');
        }
      };

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

      updateResult();
      const timer = window.setInterval(updateResult, 200);

      return () => {
        disposed = true;
        window.clearInterval(timer);
        ctx.registerHud?.(null);
        hud?.dispose();
        handle?.dispose();
        disposeSpeedButton();
      };
    }),

    // The pause menu has more controls than fit in a 412 px-tall phone viewport
    // as a single column, and the page-wide `touch-action: none` (TCH-04) means
    // the player cannot scroll to reach a control that is below the fold. Two
    // columns put every button on screen at 915x412; the quit confirmation is a
    // single inline row so it fits under the grid.
    pause: makeScreen('pause', 'Paused', (root, ctx) => {
      ctx.pauseSim(true);
      const grid = document.createElement('div');
      grid.className = 'pause-grid';
      root.append(grid);
      const add = (name: string, label: string, onClick: () => void): void => {
        grid.append(button('pause', name, label, onClick));
      };

      add('resume', 'Resume', () => {
        ctx.router.back();
      });
      add('save', 'Save game', () => {
        ctx.go('saveSlots');
      });
      add('load', 'Load game', () => {
        ctx.go('saveSlots');
      });
      add('settings', 'Settings', () => {
        ctx.go('settings');
      });
      add('bugReport', 'Report bug', () => {
        ctx.go('bugReport');
      });
      add('speedSlow', 'Speed slow', () => {
        ctx.api?.setSpeedMultiplier(SIM_SPEED_SLOW);
      });
      add('speedNormal', 'Speed normal', () => {
        ctx.api?.setSpeedMultiplier(SIM_SPEED_NORMAL);
      });
      add('speedFast', 'Speed fast', () => {
        ctx.api?.setSpeedMultiplier(SIM_SPEED_FAST);
      });

      let confirmPanel: HTMLDivElement | null = null;
      add('quit', 'Quit to title', () => {
        if (confirmPanel) {
          return;
        }
        confirmPanel = document.createElement('div');
        confirmPanel.className = 'pause-confirm';
        const text = document.createElement('p');
        text.textContent = 'Quit this mission? Save before leaving?';
        const actions = document.createElement('div');
        actions.className = 'pause-confirm-actions';
        const saveQuit = button('pause', 'confirmSaveQuit', 'Save & quit', () => {
          void (async () => {
            await ctx.api?.saveToSlot('manual-1');
            ctx.go('title');
          })();
        });
        const quit = button('pause', 'confirmQuit', 'Quit without saving', () => {
          ctx.go('title');
        });
        const cancel = button('pause', 'cancelQuit', 'Cancel', () => {
          confirmPanel?.remove();
          confirmPanel = null;
        });
        actions.append(saveQuit, quit, cancel);
        confirmPanel.append(text, actions);
        root.append(confirmPanel);
      });
      return () => {
        confirmPanel?.remove();
        confirmPanel = null;
        ctx.pauseSim(false);
      };
    }),

    settings: makeScreen('settings', 'Settings', (root, ctx) => mountSettings(root, ctx)),

    help: makeScreen('help', 'Help', (root, ctx) => {
      addButton(root, 'help', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    objectives: makeScreen('objectives', 'Objectives', (root, ctx) => {
      ctx.pauseSim(true);
      const list = document.createElement('ul');
      list.className = 'objective-list';
      for (const objective of ctx.getObjectives?.() ?? []) {
        const item = document.createElement('li');
        item.dataset.status = objective.status;
        const mark = objective.status === 'done' ? '✓' : objective.status === 'failed' ? '✗' : '•';
        item.textContent = `${mark} ${objective.kind === 'optional' ? 'Optional: ' : ''}${objective.text}`;
        list.append(item);
      }
      root.append(list);
      addButton(root, 'objectives', 'close', 'Close', () => {
        ctx.router.back();
      });
      return () => {
        ctx.pauseSim(false);
      };
    }),

    results: makeScreen('results', 'Results', (root, ctx) => {
      const world = ctx.getWorld?.();
      const winner = world?.result?.winner ?? null;
      const view = ctx.getResultView?.() ?? null;
      const heading = root.querySelector('h1');
      if (heading) {
        heading.textContent = view?.mission
          ? view.won
            ? 'Mission complete'
            : 'Mission failed'
          : winner === 1
            ? 'Victory'
            : winner === null
              ? 'Draw'
              : 'Defeat';
      }
      if (view?.mission) {
        const note = document.createElement('p');
        note.className = 'results-mission';
        note.textContent = view.won ? (view.title ?? '') : (view.reason ?? 'Try again.');
        root.append(note);
      }
      if (world) {
        const stats = world.resources.find((item) => item.player === 1);
        const detail = document.createElement('p');
        detail.className = 'results-stats';
        detail.textContent = [
          `Time ${formatClock(world.tick / SIM_TICK_HZ)}`,
          `Units built ${stats?.unitsBuilt ?? 0}`,
          `Units lost ${stats?.unitsLost ?? 0}`,
          `Ore gathered ${stats?.oreGathered ?? 0}`,
          `Metal gathered ${stats?.metalGathered ?? 0}`,
        ].join(' · ');
        root.append(detail);
      }
      if (view?.mission) {
        if (view.won && view.hasNext) {
          addButton(root, 'results', 'next', 'Next mission', () => {
            if (ctx.chooseNextMission?.()) {
              ctx.go('loading');
            }
          });
        }
        addButton(root, 'results', 'retry', 'Retry', () => {
          ctx.go('loading');
        });
        addButton(root, 'results', 'missions', 'Mission list', () => {
          ctx.go('missionSelect');
        });
      } else {
        addButton(root, 'results', 'playAgain', 'Play again', () => {
          ctx.go('loading');
        });
      }
      addButton(root, 'results', 'title', 'Title', () => {
        ctx.go('title');
      });
    }),

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

    bugReport: makeScreen('bugReport', 'Report Bug', (root, ctx) => mountBugReport(root, ctx)),

    saveSlots: makeScreen('saveSlots', 'Save / Load', (root, ctx) => mountSaveSlots(root, ctx)),

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
