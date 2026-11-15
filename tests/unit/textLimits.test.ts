import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { HINT_WORD_LIMITS, SELECT_HINT_TEXT, fitsHintLimit, wordCount } from '../../src/ui/textLimits';

function missionFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? missionFiles(path) : name.endsWith('.json') ? [path] : [];
  });
}

/** Every text a mission puts on the top-centre line: objectives, and messages from triggers. */
function bubbleTexts(): Array<{ kind: 'objective' | 'message'; where: string; text: string }> {
  const out: Array<{ kind: 'objective' | 'message'; where: string; text: string }> = [];
  for (const file of missionFiles('src/data/missions')) {
    const mission = JSON.parse(readFileSync(file, 'utf8')) as {
      objectives?: Array<{ id: string; text: string }>;
      triggers?: unknown[];
    };
    for (const objective of mission.objectives ?? []) {
      out.push({ kind: 'objective', where: `${file} objective ${objective.id}`, text: objective.text });
    }
    const visit = (node: unknown): void => {
      if (Array.isArray(node)) {
        node.forEach(visit);
      } else if (node && typeof node === 'object') {
        const item = node as Record<string, unknown>;
        if (item.t === 'message' && typeof item.text === 'string') {
          out.push({ kind: 'message', where: file, text: item.text });
        }
        Object.values(item).forEach(visit);
      }
    };
    visit(mission.triggers ?? []);
  }
  return out;
}

describe('hint bubble word limits', () => {
  it('[HINT-01] counts words and has a limit for every bubble', () => {
    expect(wordCount('  Destroy   the enemy pad ')).toBe(4);
    expect(HINT_WORD_LIMITS.objective).toBeGreaterThan(0);
    expect(HINT_WORD_LIMITS.message).toBeGreaterThan(0);
    expect(HINT_WORD_LIMITS.hint).toBeGreaterThan(0);
  });

  it('[HINT-01] every mission objective and message fits its word limit', () => {
    const texts = bubbleTexts();
    expect(texts.length).toBeGreaterThan(100);
    const tooLong = texts
      .filter((item) => !fitsHintLimit(item.kind, item.text))
      .map((item) => `${item.where}: ${wordCount(item.text)} words (limit ${HINT_WORD_LIMITS[item.kind]}): ${item.text}`);
    expect(tooLong).toEqual([]);
  });

  it('[HINT-01] the selection hint fits its word limit', () => {
    expect(fitsHintLimit('hint', SELECT_HINT_TEXT)).toBe(true);
  });
});
