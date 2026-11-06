import type { KvStore } from './kv';

export type CampaignId = 'training' | 'human' | 'alien';

export interface MissionRecord {
  bestTimeSec: number;
  wins: number;
}

export interface CampaignProgress {
  version: 1;
  completed: Record<string, MissionRecord>;
}

export const PROGRESS_KEY = 'progress.campaign';

export function emptyProgress(): CampaignProgress {
  return { version: 1, completed: {} };
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
    const result = emptyProgress();
    if (typeof completed === 'object' && completed !== null) {
      for (const [id, entry] of Object.entries(completed)) {
        if (typeof entry !== 'object' || entry === null) {
          continue;
        }
        const e = entry as { bestTimeSec?: unknown; wins?: unknown };
        if (typeof e.bestTimeSec === 'number' && typeof e.wins === 'number') {
          result.completed[id] = { bestTimeSec: e.bestTimeSec, wins: e.wins };
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

export function recordWin(progress: CampaignProgress, missionId: string, timeSec: number): CampaignProgress {
  const previous = progress.completed[missionId];
  return {
    version: 1,
    completed: {
      ...progress.completed,
      [missionId]: {
        bestTimeSec: previous ? Math.min(previous.bestTimeSec, timeSec) : timeSec,
        wins: (previous?.wins ?? 0) + 1,
      },
    },
  };
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
