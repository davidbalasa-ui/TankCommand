import type { KvStore } from './kv';

export type CampaignId = 'training' | 'human' | 'alien';

/** Campaign difficulty, chosen on the campaign screen and kept with the progress. */
export type CampaignDifficulty = 'easy' | 'normal' | 'hard';

const DIFFICULTIES: readonly CampaignDifficulty[] = ['easy', 'normal', 'hard'];

export interface MissionRecord {
  bestTimeSec: number;
  wins: number;
  /** The hardest difficulty the mission has been won on (absent in progress saved before difficulty). */
  bestDifficulty?: CampaignDifficulty;
}

export interface CampaignProgress {
  version: 1;
  completed: Record<string, MissionRecord>;
  difficulty: CampaignDifficulty;
}

export const PROGRESS_KEY = 'progress.campaign';

export function emptyProgress(): CampaignProgress {
  return { version: 1, completed: {}, difficulty: 'normal' };
}

function isDifficulty(value: unknown): value is CampaignDifficulty {
  return typeof value === 'string' && (DIFFICULTIES as readonly string[]).includes(value);
}

export function parseProgress(raw: string | null): CampaignProgress {
  if (!raw) {
    return emptyProgress();
  }
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== 'object' || value === null) {
      return emptyProgress();
    }
    const completed = (value as { completed?: unknown }).completed;
    const difficulty = (value as { difficulty?: unknown }).difficulty;
    const result = emptyProgress();
    if (isDifficulty(difficulty)) {
      result.difficulty = difficulty;
    }
    if (typeof completed === 'object' && completed !== null) {
      for (const [id, entry] of Object.entries(completed)) {
        if (typeof entry !== 'object' || entry === null) {
          continue;
        }
        const e = entry as { bestTimeSec?: unknown; wins?: unknown; bestDifficulty?: unknown };
        if (typeof e.bestTimeSec === 'number' && typeof e.wins === 'number') {
          result.completed[id] = {
            bestTimeSec: e.bestTimeSec,
            wins: e.wins,
            ...(isDifficulty(e.bestDifficulty) ? { bestDifficulty: e.bestDifficulty } : {}),
          };
        }
      }
    }
    return result;
  } catch {
    return emptyProgress();
  }
}

export async function loadProgress(store: KvStore): Promise<CampaignProgress> {
  try {
    return parseProgress(await store.get(PROGRESS_KEY));
  } catch {
    return emptyProgress();
  }
}

export async function saveProgress(store: KvStore, progress: CampaignProgress): Promise<void> {
  await store.set(PROGRESS_KEY, JSON.stringify(progress));
}

function harder(a: CampaignDifficulty | undefined, b: CampaignDifficulty): CampaignDifficulty {
  return a !== undefined && DIFFICULTIES.indexOf(a) > DIFFICULTIES.indexOf(b) ? a : b;
}

export function recordWin(
  progress: CampaignProgress,
  missionId: string,
  timeSec: number,
  difficulty: CampaignDifficulty = 'normal',
): CampaignProgress {
  const previous = progress.completed[missionId];
  return {
    ...progress,
    completed: {
      ...progress.completed,
      [missionId]: {
        bestTimeSec: previous ? Math.min(previous.bestTimeSec, timeSec) : timeSec,
        wins: (previous?.wins ?? 0) + 1,
        // A win recorded before difficulty existed was a Normal win.
        bestDifficulty: harder(previous ? (previous.bestDifficulty ?? 'normal') : undefined, difficulty),
      },
    },
  };
}

export function setCampaignDifficulty(progress: CampaignProgress, difficulty: CampaignDifficulty): CampaignProgress {
  return { ...progress, difficulty };
}

// A mission is open when it is first in its campaign or the one before it has been won.
export function missionStatus(
  progress: CampaignProgress,
  missions: ReadonlyArray<{ id: string; order: number }>,
  id: string,
): 'locked' | 'open' | 'done' {
  if (progress.completed[id]) {
    return 'done';
  }
  const index = missions.findIndex((mission) => mission.id === id);
  if (index <= 0) {
    return 'open';
  }
  const before = missions[index - 1];
  return before && progress.completed[before.id] ? 'open' : 'locked';
}
