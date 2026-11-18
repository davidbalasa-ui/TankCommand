import { describe, expect, it } from 'vitest';
import { missionsOf } from '../../src/data/missions';

const CAMPAIGNS = ['human', 'alien'] as const;

describe('[CMP-02] campaign story and roster', () => {
  for (const campaign of CAMPAIGNS) {
    const rows = missionsOf(campaign);

    it(`[CMP-02] ${campaign}: the buy list only grows from mission to mission`, () => {
      let before: string[] = [];
      for (const row of rows) {
        const player = row.sides.find((side) => side.controller === 'human');
        const now = player?.available ?? [];
        const lost = before.filter((item) => !now.includes(item));
        expect(lost, `${row.id} drops items the previous mission sold`).toEqual([]);
        before = now;
      }
    });

    it(`[CMP-02] ${campaign}: only the last mission carries the epilogue`, () => {
      const last = rows[rows.length - 1];
      expect(last?.epilogue?.length ?? 0).toBeGreaterThan(0);
      expect(rows.slice(0, -1).filter((row) => row.epilogue !== undefined).map((row) => row.id)).toEqual([]);
    });

    it(`[CMP-02] ${campaign}: the last three missions use hard AI`, () => {
      for (const row of rows.slice(-3)) {
        const ai = row.sides.filter((side) => side.controller === 'ai');
        expect(ai.length, row.id).toBeGreaterThan(0);
        expect(ai.some((side) => side.difficulty === 'hard'), row.id).toBe(true);
      }
    });
  }

  it('[CMP-02] each campaign keeps one radio voice', () => {
    for (const campaign of CAMPAIGNS) {
      const speakers = new Set<string>();
      for (const row of missionsOf(campaign)) {
        for (const trigger of row.triggers) {
          for (const action of trigger.do) {
            if (action.t === 'message' && action.speaker) {
              speakers.add(action.speaker);
            }
          }
        }
      }
      expect([...speakers], campaign).toHaveLength(1);
    }
  });
});
