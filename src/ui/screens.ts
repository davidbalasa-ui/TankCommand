import { button } from './controls';
import { Hud } from './hud';
import { drawMapPreview } from './mapPreview';
import { icon, type IconName } from './icons';
import { emblem } from './emblem';
import { iconButton, menuButton, segmentRow, setMenuButtonSubtitle } from './widgets';
import { playIntroFilm } from './introFilm';
import { APP_VERSION } from '../platform/appInfo';
import { openPrivacyPolicy } from '../platform/links';
import type {
  CampaignDifficulty,
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
import { mountUnlock } from './unlockScreen';
import { SIM_SPEED_FAST, SIM_SPEED_NORMAL, SIM_SPEED_SLOW } from '../sim/tuning';
import { SIM_TICK_HZ } from '../sim/constants';

/** Full screen plus a landscape lock, where the browser allows it. */
async function lockLandscape(): Promise<void> {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
    }
    const orientation = screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> };
    await orientation.lock?.('landscape');
  } catch {
    // Not supported (desktop, iOS Safari): the hint stays until the phone is turned.
  }
}

// Working faction names (C-03). Final public names need David's approval.
export const FACTION_NAMES = { human: 'Terran Coalition', alien: 'Arcadians' } as const;

const MAX_AI_OPPONENTS = 2;

const DIFFICULTY_LABELS: Record<CampaignDifficulty, string> = { easy: 'Easy', normal: 'Normal', hard: 'Hard' };
// Matches DIFFICULTY_TUNING in src/data/missions.ts.
const DIFFICULTY_NOTES: Record<CampaignDifficulty, string> = {
  easy: 'You start with 25% more ore, and enemy commanders of normal skill play one level easier.',
  normal: 'Every mission as designed. Training is the same on every difficulty.',
  hard: 'Enemy commanders play one level harder and start with 25% more ore and metal. You start with 20% less ore.',
};

type Build = (root: HTMLElement, ctx: ScreenContext) => void | (() => void);

function makeScreen(id: ScreenId, title: string, build?: Build): ScreenModule {
  return {
    id,
    mount(root, ctx) {
      root.replaceChildren();
      const header = document.createElement('div');
      header.className = 'screen-header';
      const heading = document.createElement('h1');
      heading.textContent = title;
      header.append(heading);
      root.append(header);
      const cleanup = build?.(root, ctx);
      // Redesign v1: the screen's Back (or Close) button becomes the arrow at
      // the left of the header, keeping its control id and accessible name.
      const back = root.querySelector<HTMLButtonElement>(
        `[data-control-id="${id}.back"], [data-control-id="${id}.close"]`,
      );
      if (back && header.isConnected && header.parentElement === root) {
        const name = back.textContent ?? 'Back';
        back.classList.add('header-back');
        back.setAttribute('aria-label', name);
        back.replaceChildren(icon('left'));
        header.prepend(back);
      }
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

/** Renders the generated CREDITS.md (headings, paragraphs, pipe tables) as plain DOM. */
function renderCredits(target: HTMLElement, markdown: string): void {
  target.replaceChildren();
  let table: HTMLTableElement | null = null;
  for (const raw of markdown.split('\n')) {
    const line = raw.trim();
    if (line.startsWith('|')) {
      const cells = line
        .slice(1, line.endsWith('|') ? -1 : undefined)
        .split(/(?<!\\)\|/)
        .map((cell) => cell.trim().replace(/\\\|/g, '|'));
      if (cells.every((cell) => /^-+$/.test(cell))) {
        continue;
      }
      const header = !table;
      table ??= document.createElement('table');
      const row = document.createElement('tr');
      for (const cell of cells) {
        const node = document.createElement(header ? 'th' : 'td');
        node.textContent = cell.replace(/`/g, '');
        row.append(node);
      }
      table.append(row);
      target.append(table);
      continue;
    }
    table = null;
    if (!line) {
      continue;
    }
    const heading = /^(#+)\s+(.*)$/.exec(line);
    const node = document.createElement(heading ? 'h2' : 'p');
    node.textContent = (heading ? heading[2] ?? '' : line).replace(/`/g, '');
    target.append(node);
  }
}

function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

/** How many embers drift across the title picture. */
const TITLE_EMBERS = 14;
let titleIntroPlayed = false;

export function createScreens(): Record<ScreenId, ScreenModule> {
  const screens: Record<ScreenId, ScreenModule> = {
    title: makeScreen('title', 'TankCommand', (root, ctx) => {
      root.querySelector('.screen-header')?.remove();
      const backdrop = document.createElement('div');
      backdrop.className = 'title-backdrop';
      const shade = document.createElement('div');
      shade.className = 'title-shade';
      // Drifting embers off the battlefield, in front of the picture and behind the menu.
      const embers = document.createElement('div');
      embers.className = 'title-embers';
      embers.setAttribute('aria-hidden', 'true');
      for (let i = 0; i < TITLE_EMBERS; i += 1) {
        embers.append(document.createElement('i'));
      }
      const logo = document.createElement('div');
      logo.className = 'title-logo';
      const wordmark = document.createElement('div');
      wordmark.className = 'title-wordmark';
      const name = document.createElement('h1');
      name.className = 'title-name';
      const accent = document.createElement('span');
      accent.textContent = 'COMMAND';
      name.append('TANK', accent);
      name.setAttribute('aria-label', 'TankCommand');
      // A thin rule under the name, with a lit segment that sweeps across it now and then.
      const rule = document.createElement('div');
      rule.className = 'title-rule';
      rule.setAttribute('aria-hidden', 'true');
      wordmark.append(name, rule);
      logo.append(emblem('emblem title-emblem'), wordmark);
      // The opening plays once per launch; coming back from another screen is a quick fade.
      // Automated browsers skip it unless asked, like the live backdrop below.
      let intro = !navigator.webdriver;
      try {
        intro = intro || window.localStorage.getItem('tc.titleIntro') === 'on';
      } catch {
        // No storage: keep the default.
      }
      root.classList.add(intro && !titleIntroPlayed ? 'title-intro' : 'title-return');
      titleIntroPlayed = true;
      const curtain = document.createElement('div');
      curtain.className = 'title-curtain';
      curtain.setAttribute('aria-hidden', 'true');

      const menu = document.createElement('div');
      menu.className = 'title-menu';
      if (ctx.api) {
        const resume = menuButton('title', 'resume', 'Continue', 'Resume your last game', 'play', () => {
          void ctx.api?.resumeLastGame();
        }, true);
        resume.style.display = 'none';
        menu.append(resume);
        void ctx.api
          .latestAutosave()
          .then((latest) => {
            if (latest) {
              const parts = [latest.title ?? (latest.mode === 'mission' ? 'Campaign' : 'Skirmish')];
              if (latest.playSeconds !== undefined) {
                parts.push(`${formatClock(latest.playSeconds)} played`);
              }
              setMenuButtonSubtitle(resume, parts.join(' · '));
              resume.style.display = '';
              campaign.classList.remove('lead');
            } else {
              resume.remove();
            }
          })
          .catch(() => {
            resume.remove();
          });
      }
      // With no game to continue, Campaign is the lit entry.
      const campaign = menuButton('title', 'campaign', 'Campaign', `Training · ${FACTION_NAMES.human.split(' ')[0]} · ${FACTION_NAMES.alien}`, 'flag', () => {
        ctx.go('campaignSelect');
      });
      campaign.classList.add('lead');
      menu.append(
        campaign,
        menuButton('title', 'skirmish', 'Skirmish', 'You vs 1 or 2 AI opponents', 'swords', () => {
          ctx.go('skirmishSetup');
        }),
      );

      const small = document.createElement('div');
      small.className = 'title-small-row';
      small.append(
        iconButton('title', 'load', 'Load game', 'save', () => {
          ctx.go('saveSlots');
        }, 'Load'),
        iconButton('title', 'settings', 'Settings', 'gear', () => {
          ctx.go('settings');
        }),
        iconButton('title', 'help', 'Help', 'help', () => {
          ctx.go('help');
        }),
        iconButton('title', 'credits', 'Credits', 'star', () => {
          ctx.go('credits');
        }),
        iconButton('title', 'intro', 'Intro', 'play', () => {
          void playIntroFilm();
        }),
      );
      const version = document.createElement('div');
      version.className = 'title-version';
      version.textContent = `v${APP_VERSION}`;
      root.append(backdrop, shade, embers, logo, menu, small, version, curtain);

      // Live 3D background. Automated browsers skip it unless asked (keeps e2e runs fast).
      let disposeBackdrop: (() => void) | null = null;
      let closed = false;
      let wanted = true;
      try {
        wanted = !navigator.webdriver || window.localStorage.getItem('tc.titleBackdrop') === 'on';
      } catch {
        wanted = !navigator.webdriver;
      }
      if (wanted && ctx.attachTitleBackdrop) {
        const canvas = document.createElement('canvas');
        canvas.className = 'title-canvas';
        backdrop.append(canvas);
        void ctx
          .attachTitleBackdrop(canvas)
          .then((dispose) => {
            if (closed) {
              dispose();
            } else {
              disposeBackdrop = dispose;
              backdrop.classList.add('live');
            }
          })
          .catch(() => {
            canvas.remove();
          });
      }
      return () => {
        closed = true;
        disposeBackdrop?.();
      };
    }),

    campaignSelect: makeScreen('campaignSelect', 'Campaign', (root, ctx) => {
      const choices: Array<[CampaignId, string, string, IconName, string]> = [
        ['training', 'Training', 'Five short lessons: drops, mining, combat, research, air', 'help', 'training'],
        ['human', FACTION_NAMES.human, 'Hold the line with heavy armour', 'unit', 'human'],
        ['alien', FACTION_NAMES.alien, 'Strike fast with hover craft', 'star', 'alien'],
      ];
      const cards = document.createElement('div');
      cards.className = 'choice-cards';
      for (const [id, title, sub, iconName, tone] of choices) {
        const card = button('campaignSelect', id, id === 'training' ? 'Training' : `${title} campaign`, () => {
          ctx.chooseCampaign?.(id);
          ctx.go('missionSelect');
        });
        card.classList.add('choice-card', `tone-${tone}`);
        card.setAttribute('aria-label', id === 'training' ? 'Training' : `${title} campaign`);
        const name = document.createElement('span');
        name.className = 'choice-title';
        name.textContent = title;
        const text = document.createElement('span');
        text.className = 'choice-sub';
        text.textContent = sub;
        card.replaceChildren(icon(iconName, 'choice-icon'), name, text);
        cards.append(card);
      }
      root.append(cards);
      // Difficulty applies to every campaign mission and is kept with the campaign progress.
      const levels = (['easy', 'normal', 'hard'] as const).map((value) => ({ value, label: DIFFICULTY_LABELS[value] }));
      const levelHolder = document.createElement('div');
      levelHolder.className = 'campaign-difficulty';
      const renderLevel = (): void => {
        const level = ctx.getDifficulty?.() ?? 'normal';
        // Any edge either side gets is stated openly here.
        const note = document.createElement('p');
        note.className = 'difficulty-note';
        note.textContent = DIFFICULTY_NOTES[level];
        levelHolder.replaceChildren(
          segmentRow('campaignSelect', 'difficulty', 'Difficulty', levels, level, (value) => {
            ctx.setDifficulty?.(value);
            renderLevel();
          }),
          note,
        );
      };
      renderLevel();
      root.append(levelHolder);
      addButton(root, 'campaignSelect', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    missionSelect: makeScreen('missionSelect', 'Select Mission', (root, ctx) => {
      const list = ctx.getMissionList?.() ?? [];
      const rows = document.createElement('div');
      rows.className = 'mission-list';
      for (const item of list) {
        // A mission of the full game the player has not unlocked shows "Full game" and opens the
        // unlock screen, whatever its campaign progress.
        const fullGame = item.fullGame === true;
        const label = `${item.order}. ${item.title}${
          fullGame ? ' (full game)' : item.status === 'done' ? ' ✓' : item.status === 'locked' ? ' (locked)' : ''
        }`;
        const entry = button('missionSelect', 'mission', label, () => {
          if (fullGame) {
            ctx.go('unlock');
            return;
          }
          if (item.status !== 'locked' && ctx.chooseMission?.(item.id)) {
            ctx.go('briefing');
          }
        });
        entry.disabled = item.status === 'locked' && !fullGame;
        entry.dataset.missionId = item.id;
        entry.dataset.status = item.status;
        if (fullGame) {
          entry.dataset.fullGame = 'true';
        }
        entry.classList.add('mission-row');
        entry.setAttribute('aria-label', label);
        const order = document.createElement('span');
        order.className = 'mission-order';
        order.textContent = String(item.order);
        const name = document.createElement('span');
        name.className = 'mission-name';
        name.textContent = item.title;
        const state = document.createElement('span');
        state.className = 'mission-state';
        state.textContent = fullGame
          ? 'Full game'
          : item.status === 'done'
            ? `Complete${item.bestDifficulty ? ` · ${DIFFICULTY_LABELS[item.bestDifficulty]}` : ''}`
            : item.status === 'locked'
              ? 'Locked'
              : 'Ready';
        entry.replaceChildren(order, name, state, icon(item.status === 'locked' || fullGame ? 'lock' : 'right', 'chev'));
        rows.append(entry);
      }
      root.append(rows);
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
        preview.className = 'briefing-map panel';
        preview.setAttribute('aria-label', 'Map preview');
        drawMapPreview(preview, view.map, 256);
        const text = document.createElement('div');
        text.className = 'briefing-text panel';
        const paragraph = document.createElement('p');
        paragraph.textContent = view.text;
        const label = document.createElement('div');
        label.className = 'section-label';
        label.textContent = 'Objectives';
        const objectives = document.createElement('ul');
        objectives.className = 'briefing-objectives';
        for (const objective of view.objectives) {
          const item = document.createElement('li');
          item.textContent = objective.kind === 'optional' ? `Optional: ${objective.text}` : objective.text;
          item.dataset.kind = objective.kind;
          objectives.append(item);
        }
        text.append(paragraph, label, objectives);
        if (view.difficulty) {
          const level = document.createElement('p');
          level.className = 'briefing-difficulty';
          level.dataset.difficulty = view.difficulty;
          level.textContent = `Difficulty: ${DIFFICULTY_LABELS[view.difficulty]}`;
          text.append(level);
        }
        body.append(preview, text);
      }
      root.append(body);
      const start = button('briefing', 'start', 'Start mission', () => {
        ctx.go('loading');
      });
      start.classList.add('primary', 'corner-action');
      root.append(
        start,
        button('briefing', 'back', 'Back', () => {
          ctx.router.back();
        }),
      );
    }),

    skirmishSetup: makeScreen('skirmishSetup', 'Skirmish', (root, ctx) => {
      const fallback: SkirmishConfig = {
        mapId: '',
        faction: 'human',
        opponents: [{ faction: 'alien', difficulty: 'normal' }],
        resources: 'normal',
        force: 'padForce',
        fog: true,
      };
      let config: SkirmishConfig = ctx.getSkirmishConfig?.() ?? fallback;
      // Up to two AI opponents (David's cap: 64 units per side, at most two AI sides).
      if (config.opponents.length > MAX_AI_OPPONENTS) {
        config = { ...config, opponents: config.opponents.slice(0, MAX_AI_OPPONENTS) };
        ctx.setSkirmishConfig?.(config);
      }
      const maps = ctx.getSkirmishMaps?.() ?? [];
      // A map seats as many sides as it has starts: one AI on a two-player map, up to the cap on
      // a four-player one.
      const seatsFor = (mapId: string): number => {
        const map = maps.find((m) => m.id === mapId) ?? maps[0];
        const starts = map?.preview?.starts.length ?? MAX_AI_OPPONENTS + 1;
        return Math.max(1, Math.min(MAX_AI_OPPONENTS, starts - 1));
      };
      const fitted = (next: SkirmishConfig): SkirmishConfig =>
        next.opponents.length > seatsFor(next.mapId)
          ? { ...next, opponents: next.opponents.slice(0, seatsFor(next.mapId)) }
          : next;
      if (fitted(config) !== config) {
        config = fitted(config);
        ctx.setSkirmishConfig?.(config);
      }
      const set = (next: SkirmishConfig): void => {
        config = next;
        ctx.setSkirmishConfig?.(next);
        render();
      };
      const factionOptions = [
        { value: 'human' as const, label: FACTION_NAMES.human.split(' ')[0] ?? 'Terran', dot: '#3fd8ff' },
        { value: 'alien' as const, label: FACTION_NAMES.alien, dot: '#ffc24a' },
      ];
      const levelOptions = [
        { value: 'easy' as const, label: 'Easy' },
        { value: 'normal' as const, label: 'Normal' },
        { value: 'hard' as const, label: 'Hard' },
      ];

      // Left: map card with preview, numbered spawns and arrows to change map.
      const card = document.createElement('div');
      card.className = 'panel map-card';
      const preview = document.createElement('div');
      preview.className = 'map-preview';
      const canvas = document.createElement('canvas');
      canvas.setAttribute('aria-label', 'Map preview');
      preview.append(canvas);
      const nav = document.createElement('div');
      nav.className = 'map-nav';
      const mapName = document.createElement('div');
      mapName.className = 'map-name';
      const step = (delta: number): void => {
        if (maps.length === 0) {
          return;
        }
        const index = Math.max(0, maps.findIndex((m) => m.id === config.mapId));
        const next = maps[(index + delta + maps.length) % maps.length];
        if (next) {
          set(fitted({ ...config, mapId: next.id }));
        }
      };
      const prev = iconButton('skirmishSetup', 'mapPrev', 'Previous map', 'left', () => {
        step(-1);
      }, null);
      const nextButton = iconButton('skirmishSetup', 'map', 'Next map', 'right', () => {
        step(1);
      }, null);
      nav.append(prev, mapName, nextButton);
      card.append(preview, nav);

      // Right: one segmented row per option.
      const options = document.createElement('div');
      options.className = 'setup-options';

      const currentMap = (): (typeof maps)[number] | undefined => maps.find((m) => m.id === config.mapId) ?? maps[0];
      const start = button('skirmishSetup', 'start', 'Start', () => {
        // A full-game map the player has not unlocked opens the unlock screen instead.
        if (currentMap()?.fullGame) {
          ctx.go('unlock');
          return;
        }
        ctx.beginSkirmish?.();
        ctx.go('loading');
      });
      start.classList.add('primary', 'start-button');
      const lockBadge = document.createElement('div');
      lockBadge.className = 'full-game-badge';
      lockBadge.dataset.fullGame = 'true';
      lockBadge.replaceChildren(icon('lock'), 'Full game');

      const render = (): void => {
        const map = currentMap();
        const locked = map?.fullGame === true;
        start.setAttribute('aria-label', locked ? 'Unlock full game' : 'Start');
        start.replaceChildren(icon(locked ? 'lock' : 'play'), locked ? 'UNLOCK' : 'START');
        start.dataset.fullGame = locked ? 'true' : 'false';
        if (locked) {
          preview.append(lockBadge);
        } else {
          lockBadge.remove();
        }
        const title = document.createElement('b');
        title.textContent = map?.name ?? 'Default';
        const info = document.createElement('div');
        if (map?.preview) {
          const ore = map.preview.deposits.filter((d) => d.kind !== 'metal').length;
          const metal = map.preview.deposits.length - ore;
          // A match seats you and at most MAX_AI_OPPONENTS AI (the stress-tested unit cap), so a
          // four-start map holds up to three sides; the spare start is drawn faded.
          const sides = Math.min(map.preview.starts.length, MAX_AI_OPPONENTS + 1);
          const seats = sides > 2 ? `Up to ${sides} sides` : `${sides} sides`;
          info.textContent = `${seats} · ${ore} ore · ${metal} metal`;
        }
        mapName.replaceChildren(title, info);
        preview.querySelectorAll('.spawn').forEach((node) => {
          node.remove();
        });
        if (map?.preview) {
          drawMapPreview(canvas, map.preview, 256);
          const half = map.preview.size / 2;
          for (const s of map.preview.starts) {
            const marker = document.createElement('span');
            // Starts no side uses in this match are dimmed (1 is you, then one per AI).
            const spare = s.player > config.opponents.length + 1;
            marker.className = `spawn${s.player === 1 ? ' you' : ''}${spare ? ' spare' : ''}`;
            marker.textContent = String(s.player);
            marker.style.left = `${((s.x + half) / map.preview.size) * 100}%`;
            marker.style.top = `${((s.z + half) / map.preview.size) * 100}%`;
            preview.append(marker);
          }
        }

        const rows: HTMLElement[] = [
          segmentRow('skirmishSetup', 'faction', 'Your side', factionOptions, config.faction, (faction) => {
            set({ ...config, faction });
          }),
          segmentRow(
            'skirmishSetup',
            'opponents',
            'Opponents',
            Array.from({ length: seatsFor(config.mapId) }, (_, i) => ({ value: i + 1, label: `${i + 1} AI` })),
            config.opponents.length,
            (count) => {
              const opponents = Array.from(
                { length: count },
                (_, i) => config.opponents[i] ?? { faction: 'alien' as const, difficulty: 'normal' as const },
              );
              set({ ...config, opponents });
            },
          ),
        ];
        const many = config.opponents.length > 1;
        config.opponents.forEach((opponent, index) => {
          const n = index + 1;
          const row = document.createElement('div');
          row.className = 'option-row option-pair';
          const label = document.createElement('span');
          label.className = 'option-label';
          label.textContent = many ? `AI ${n}` : 'AI';
          row.append(
            label,
            segmentRow('skirmishSetup', `opp${n}Faction`, many ? `AI ${n} side` : 'AI side', factionOptions, opponent.faction, (faction) => {
              set({ ...config, opponents: config.opponents.map((o, i) => (i === index ? { ...o, faction } : o)) });
            }),
            segmentRow('skirmishSetup', `opp${n}Difficulty`, many ? `AI ${n} level` : 'AI level', levelOptions, opponent.difficulty, (difficulty) => {
              set({ ...config, opponents: config.opponents.map((o, i) => (i === index ? { ...o, difficulty } : o)) });
            }),
          );
          rows.push(row);
        });
        rows.push(
          segmentRow(
            'skirmishSetup',
            'resources',
            'Resources',
            [
              { value: 'low' as const, label: 'Low' },
              { value: 'normal' as const, label: 'Normal' },
              { value: 'high' as const, label: 'High' },
            ],
            config.resources,
            (resources) => {
              set({ ...config, resources });
            },
          ),
          segmentRow(
            'skirmishSetup',
            'force',
            'Start with',
            [
              { value: 'padOnly' as const, label: 'Pad only' },
              { value: 'padForce' as const, label: 'Pad + force' },
            ],
            config.force,
            (force) => {
              set({ ...config, force });
            },
          ),
          segmentRow(
            'skirmishSetup',
            'fog',
            'Fog of war',
            [
              { value: 'on', label: 'On' },
              { value: 'off', label: 'Off' },
            ],
            config.fog ? 'on' : 'off',
            (value) => {
              set({ ...config, fog: value === 'on' });
            },
          ),
        );
        options.replaceChildren(...rows);
        options.classList.toggle('compact', config.opponents.length > 1);
      };
      render();
      const back = button('skirmishSetup', 'back', 'Back', () => {
        ctx.router.back();
      });
      root.append(back, card, options, start);
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
      root.querySelector('.screen-header')?.remove();

      const canvas = document.createElement('canvas');
      canvas.className = 'game-canvas';
      root.append(canvas);

      // On a phone, a match goes full screen and locks sideways by itself. The
      // tap on Start/Continue still counts as the user gesture browsers require.
      // (The Play Store build locks landscape in the Android manifest instead.)
      if (window.matchMedia?.('(pointer: coarse)').matches && !navigator.webdriver) {
        void lockLandscape();
      }

      // Shown only on an upright phone (CSS): the match is played sideways.
      const rotate = document.createElement('div');
      rotate.className = 'rotate-hint';
      rotate.setAttribute('role', 'status');
      const hintText = document.createElement('span');
      hintText.textContent = 'Turn your phone sideways to play';
      const hintSub = document.createElement('small');
      hintSub.textContent = 'The battlefield and controls are laid out for landscape.';
      const hintActions = document.createElement('div');
      hintActions.className = 'rotate-hint-actions';
      // Phones only allow an orientation lock in full screen; best effort.
      const landscape = button('inGame', 'rotateLandscape', 'Full screen sideways', () => {
        void lockLandscape();
      });
      landscape.classList.add('primary');
      const menu = button('inGame', 'rotateMenu', 'Menu', () => {
        ctx.go('pause');
      });
      hintActions.append(landscape, menu);
      rotate.append(icon('phone'), hintText, hintSub, hintActions);
      root.append(rotate);

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
          getResearchQueue: () => ctx.getResearchQueue?.() ?? [],
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
          getBaseView: () => ctx.getBaseView?.() ?? { researchBusy: false, nodes: [], structures: [], units: [], ore: 0, metal: 0 },
          baseAction: (action) => ctx.baseAction?.(action) ?? false,
          salvageSelected: () => {
            ctx.salvageSelected?.();
          },
          getAlerts: () => ctx.api?.alerts() ?? [],
          simSpeed: () => ctx.api?.simSpeed() ?? 1,
          cycleSpeed: () => {
            ctx.api?.cycleSpeed();
          },
          thumbnail: (kind, typeId) => ctx.thumbnail?.(kind, typeId) ?? null,
          itemName: (typeId) => ctx.itemName?.(typeId) ?? typeId,
          itemRole: (typeId) => ctx.itemRole?.(typeId),
          isSelectMode: () => ctx.isSelectMode?.() ?? false,
          setSelectMode: (value) => {
            ctx.setSelectMode?.(value);
          },
        });
        ctx.registerHud?.(hud);
      }


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

      // Covers the battlefield until its models are in, so placeholder boxes never show.
      const veil = document.createElement('div');
      veil.className = 'game-loading';
      veil.setAttribute('role', 'status');
      veil.textContent = 'Loading battlefield…';
      root.append(veil);

      void ctx
        .attachRenderer(canvas)
        .then((resolved) => {
          if (disposed) {
            resolved.dispose();
            return;
          }
          handle = resolved;
          if (resolved.error) {
            veil.remove();
            showError(resolved.error);
            return;
          }
          void (resolved.ready ?? Promise.resolve()).then(() => {
            veil.classList.add('done');
            window.setTimeout(() => {
              veil.remove();
            }, 500);
          });
        })
        .catch(() => {
          if (!disposed) {
            veil.remove();
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
      };
    }),

    // Pause menu (redesign v2): a card over the dimmed, blurred battlefield. Resume and game
    // speed on the left, everything else in a list on the right, so every control fits a
    // 412 px-tall phone screen without scrolling (the page is touch-action: none, TCH-04).
    pause: makeScreen('pause', 'Paused', (root, ctx) => {
      ctx.pauseSim(true);
      root.querySelector('.screen-header')?.remove();
      const card = document.createElement('div');
      card.className = 'pause-card';
      root.append(card);

      const head = document.createElement('div');
      head.className = 'pause-head';
      const title = document.createElement('h1');
      title.textContent = 'Paused';
      head.append(title);
      // The match clock lives here rather than on the battlefield.
      const world = ctx.getWorld?.();
      if (world) {
        const seconds = Math.floor(world.tick / SIM_TICK_HZ);
        const clock = document.createElement('p');
        clock.className = 'pause-clock';
        clock.append(icon('clock'), document.createTextNode(`Match time ${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`));
        head.append(clock);
        const objective = world.mission?.objectives.find((item) => item.kind === 'primary' && item.status === 'active');
        if (objective) {
          const goal = document.createElement('p');
          goal.className = 'pause-goal';
          goal.append(icon('flag'), document.createTextNode(objective.text));
          head.append(goal);
        }
      }

      const body = document.createElement('div');
      body.className = 'pause-body';
      const main = document.createElement('div');
      main.className = 'pause-main';
      const list = document.createElement('div');
      list.className = 'pause-list';
      body.append(main, list);
      card.append(head, body);
      // Kept for the layout tests and older styles that look for the grid.
      const grid = list;
      grid.classList.add('pause-grid');

      const resume = button('pause', 'resume', 'Resume', () => {
        ctx.router.back();
      });
      resume.classList.add('primary', 'pause-resume');
      resume.replaceChildren(icon('play'), document.createTextNode('Resume'));
      main.append(resume);

      // Game speed: one segmented control; the lit segment is the current speed.
      const speedBox = document.createElement('div');
      speedBox.className = 'pause-speed';
      const speedLabel = document.createElement('span');
      speedLabel.className = 'pause-speed-label';
      speedLabel.append(icon('speed'), document.createTextNode('Game speed'));
      const speedRow = document.createElement('div');
      speedRow.className = 'segmented pause-speed-row';
      speedBox.append(speedLabel, speedRow);
      main.append(speedBox);
      const speeds: Array<[string, string, string, number]> = [
        ['speedSlow', 'Speed slow', 'Slow', SIM_SPEED_SLOW],
        ['speedNormal', 'Speed normal', 'Normal', SIM_SPEED_NORMAL],
        ['speedFast', 'Speed fast', 'Fast', SIM_SPEED_FAST],
      ];
      const speedButtons: Array<[HTMLButtonElement, number]> = [];
      const markSpeed = (): void => {
        const current = ctx.api?.simSpeed() ?? SIM_SPEED_NORMAL;
        for (const [node, value] of speedButtons) {
          const on = Math.abs(value - current) < 1e-6;
          node.classList.toggle('on', on);
          node.setAttribute('aria-pressed', on ? 'true' : 'false');
        }
      };
      for (const [name, label, short, value] of speeds) {
        const node = button('pause', name, label, () => {
          ctx.api?.setSpeedMultiplier(value);
          markSpeed();
        });
        node.classList.add('speed-option');
        node.setAttribute('aria-label', label);
        node.textContent = short;
        speedRow.append(node);
        speedButtons.push([node, value]);
      }
      markSpeed();

      const add = (name: string, label: string, iconName: IconName, onClick: () => void): HTMLButtonElement => {
        const node = button('pause', name, label, onClick);
        node.classList.add('pause-item');
        node.setAttribute('aria-label', label);
        node.replaceChildren(icon(iconName), document.createTextNode(label));
        grid.append(node);
        return node;
      };
      if (world?.mission) {
        add('objectives', 'Objectives', 'flag', () => {
          ctx.go('objectives');
        });
      }
      add('help', 'Help', 'help', () => {
        ctx.go('help');
      });
      add('save', 'Save game', 'save', () => {
        ctx.go('saveSlots');
      });
      add('load', 'Load game', 'list', () => {
        ctx.go('saveSlots');
      });
      add('settings', 'Settings', 'gear', () => {
        ctx.go('settings');
      });
      add('bugReport', 'Report bug', 'bug', () => {
        ctx.go('bugReport');
      });

      // Restart and Quit swap the menu for a question with large buttons (no browser dialogs).
      let confirmPanel: HTMLDivElement | null = null;
      const closeConfirm = (): void => {
        confirmPanel?.remove();
        confirmPanel = null;
        card.classList.remove('confirming');
      };
      const confirm = (question: string, buttons: HTMLButtonElement[], cancelName: string): HTMLParagraphElement => {
        const text = document.createElement('p');
        text.textContent = question;
        const actions = document.createElement('div');
        actions.className = 'pause-confirm-actions';
        actions.append(...buttons, button('pause', cancelName, 'Cancel', closeConfirm));
        confirmPanel = document.createElement('div');
        confirmPanel.className = 'pause-confirm';
        confirmPanel.append(text, actions);
        card.classList.add('confirming');
        card.append(confirmPanel);
        return text;
      };

      // A skirmish saved before setups were kept with saves can't be rebuilt: no Restart then.
      const restart = (): void => {
        if (confirmPanel) {
          return;
        }
        const again = button('pause', 'confirmRestart', 'Restart', () => {
          // The old match's autosaves go first, so Continue never offers the abandoned run.
          again.disabled = true;
          void (async () => {
            // Storage trouble must not leave the player stuck on the pause menu.
            await ctx.api?.discardMatch().catch(() => undefined);
            ctx.go('loading');
          })();
        });
        again.classList.add('danger');
        confirm(`${world?.mission ? 'Restart this mission' : 'Restart this match'} from the beginning? Progress since the start is lost.`, [again], 'cancelRestart');
      };
      if (ctx.canRestart?.() ?? true) {
        add('restart', world?.mission ? 'Restart mission' : 'Restart match', 'restart', restart);
      }

      const quit = add('quit', 'Quit to title', 'x', () => {
        if (confirmPanel) {
          return;
        }
        // Save & quit keeps the match for Continue on the title screen; it never touches the
        // player's own save slots.
        const saveQuit = button('pause', 'confirmSaveQuit', 'Save & quit', () => {
          void (async () => {
            const result = await ctx.api?.quitSave();
            if (result && result.status !== 'ok') {
              question.textContent = result.message;
              return;
            }
            ctx.go('title');
          })();
        });
        saveQuit.classList.add('primary');
        const quitNow = button('pause', 'confirmQuit', 'Quit without saving', () => {
          // Nor does Continue offer a match quit without saving (its earlier autosaves go too).
          quitNow.disabled = true;
          void (async () => {
            // Storage trouble must not leave the player stuck on the pause menu.
            await ctx.api?.discardMatch().catch(() => undefined);
            ctx.go('title');
          })();
        });
        quitNow.classList.add('danger');
        const question = confirm('Quit this match? Save & quit lets you continue it from the title screen.', [saveQuit, quitNow], 'cancelQuit');
      });
      quit.classList.add('pause-quit');
      return () => {
        closeConfirm();
        ctx.pauseSim(false);
      };
    }),

    settings: makeScreen('settings', 'Settings', (root, ctx) => mountSettings(root, ctx)),

    help: makeScreen('help', 'Help', (root, ctx) => {
      const sections: Array<[IconName, string, string[]]> = [
        ['target', 'Camera', [
          'Drag one finger to pan.',
          'Pinch to zoom, twist to rotate.',
          'Tap the minimap to jump there.',
        ]],
        ['unit', 'Units', [
          'Tap a unit to select it; tap the ground to move.',
          'Double-tap selects every unit of that type on screen.',
          'Long-press and drag draws a selection box.',
          'Two-finger tap clears the selection.',
        ]],
        ['attack', 'Orders', [
          'Attack: move, but fight anything met on the way.',
          'Hold: stay put and fire at anything in range.',
          'Waypoints: queue several moves in a row.',
          'Buttons only appear when the selection can use them.',
          'Hold a group tile to save the selection in it; tap the tile to pick them, double-tap to look at them.',
        ]],
        ['build', 'Base', [
          'Tap your landing pad to open Build: units and structure kits arrive by orbital drop.',
          'Structure kits drive to the spot you tap and unpack there; they are weak until unpacked.',
          'Tap any other building of yours to open Base: research, upgrades, pack up or dismantle.',
        ]],
        ['worker', 'Ore and metal', [
          'Ore pays for everything you buy. Metal pays only for research and upgrades.',
          'Miners dig pink ore and stack it in crates beside the deposit.',
          'Haulers carry the crates to your pad, and carry metal home from metal stations.',
          'Build a metal station on a blue metal site so haulers have metal to fetch.',
        ]],
        ['star', 'Research', [
          'Locked cards in Build show what research unlocks them.',
          'Tap a locked card to research it. Research costs ore and metal and takes time.',
          'Research also opens upgrades: select vehicles, tap Upgrade, and buy one for each vehicle.',
        ]],
        ['air', 'Air and sight', [
          'Aircraft need a free slot at an air base (Airfield or Aerie). Tap an aircraft, then Launch, then tap where to fly.',
          'Many ground weapons cannot hit aircraft: bring anti-air units or towers.',
          'Dark ground is unexplored; you only see what your units, buildings and radar can see.',
        ]],
      ];
      const grid = document.createElement('div');
      grid.className = 'help-grid';
      for (const [iconName, title, lines] of sections) {
        const card = document.createElement('section');
        card.className = 'help-card panel';
        const head = document.createElement('h2');
        head.append(icon(iconName), title);
        const list = document.createElement('ul');
        for (const line of lines) {
          const item = document.createElement('li');
          item.textContent = line;
          list.append(item);
        }
        card.append(head, list);
        grid.append(card);
      }
      root.append(grid);
      addButton(root, 'help', 'back', 'Back', () => {
        ctx.router.back();
      });
    }),

    objectives: makeScreen('objectives', 'Objectives', (root, ctx) => {
      // Opened from the pause menu the match is already paused, and stays paused on return.
      const overPause = ctx.router.current() === 'pause';
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
        if (!overPause) {
          ctx.pauseSim(false);
        }
      };
    }),

    results: makeScreen('results', 'Results', (root, ctx) => {
      const world = ctx.getWorld?.();
      const winner = world?.result?.winner ?? null;
      const view = ctx.getResultView?.() ?? null;
      const heading = root.querySelector('h1');
      if (heading) {
        heading.textContent = view?.mission
          ? view.campaignComplete
            ? 'Campaign complete'
            : view.won
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
        if (view.difficulty) {
          const level = document.createElement('p');
          level.className = 'results-difficulty';
          level.dataset.difficulty = view.difficulty;
          level.textContent = `Difficulty: ${DIFFICULTY_LABELS[view.difficulty]}`;
          root.append(level);
        }
        if (view.campaignComplete && view.epilogue) {
          const epilogue = document.createElement('p');
          epilogue.className = 'results-epilogue';
          epilogue.textContent = view.epilogue;
          root.append(epilogue);
        }
      }
      if (world) {
        const stats = world.resources.find((item) => item.player === 1);
        const detail = document.createElement('div');
        detail.className = 'results-stats';
        const tiles: Array<[string, string]> = [
          ['Time', formatClock(world.tick / SIM_TICK_HZ)],
          ['Units built', String(stats?.unitsBuilt ?? 0)],
          ['Units lost', String(stats?.unitsLost ?? 0)],
          ['Ore gathered', String(stats?.oreGathered ?? 0)],
          ['Metal gathered', String(stats?.metalGathered ?? 0)],
        ];
        for (const [label, value] of tiles) {
          const tile = document.createElement('div');
          tile.className = 'stat-tile panel';
          const number = document.createElement('b');
          number.textContent = value;
          const caption = document.createElement('span');
          caption.textContent = label;
          tile.append(number, caption);
          detail.append(tile);
        }
        root.append(detail);
      }
      const actions = document.createElement('div');
      actions.className = 'button-row results-actions';
      root.append(actions);
      const action = (name: string, label: string, onClick: () => void, primary = false): void => {
        const node = button('results', name, label, onClick);
        if (primary) {
          node.classList.add('primary');
        }
        actions.append(node);
      };
      if (view?.mission && view.campaignComplete) {
        // The story is over: no retry, just back to the campaigns.
        action('missions', 'Mission list', () => {
          ctx.go('missionSelect');
        }, true);
      } else if (view?.mission) {
        if (view.won && view.hasNext) {
          action('next', view.nextNeedsFullGame ? 'Next mission (full game)' : 'Next mission', () => {
            if (view.nextNeedsFullGame) {
              ctx.go('unlock');
              return;
            }
            if (ctx.chooseNextMission?.()) {
              ctx.go('briefing');
            }
          }, true);
        }
        if (ctx.canRestart?.() ?? true) {
          action('retry', 'Retry', () => {
            ctx.go('loading');
          }, !(view.won && view.hasNext));
        }
        action('missions', 'Mission list', () => {
          ctx.go('missionSelect');
        });
      } else if (ctx.canRestart?.() ?? true) {
        action('playAgain', 'Play again', () => {
          ctx.go('loading');
        }, true);
      }
      action('title', 'Title', () => {
        ctx.go('title');
      });
      root.classList.toggle('won', Boolean(view?.mission ? view.won : winner === 1));
    }),

    credits: makeScreen('credits', 'Credits', (root, ctx) => {
      const text = document.createElement('div');
      text.className = 'credits-text';
      text.textContent = 'Loading credits...';
      // The privacy policy sits above the (long) credits so it is reachable without scrolling.
      const privacy = button('credits', 'privacy', 'Privacy policy', () => {
        openPrivacyPolicy();
      });
      privacy.classList.add('credits-privacy');
      root.append(privacy, text);
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
            renderCredits(text, content);
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

    unlock: makeScreen('unlock', 'Full game', (root, ctx) => mountUnlock(root, ctx)),

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
