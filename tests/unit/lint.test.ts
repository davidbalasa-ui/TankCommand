import { existsSync, readFileSync } from 'node:fs';
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';

const root = process.cwd();

describe('lint and type isolation', () => {
  it('[LINT-01] lint script is zero-warning and the flat config exists', () => {
    const pkg = JSON.parse(readFileSync('package.json', 'utf8')) as {
      scripts: Record<string, string>;
    };
    expect(pkg.scripts.lint).toContain('--max-warnings 0');
    expect(existsSync('eslint.config.js')).toBe(true);
  });

  it(
    '[LINT-02] sim restrictions fire on sim files and not on render files',
    async () => {
      const eslint = new ESLint({ cwd: root });
      const code = [
        "import * as THREE from 'three';",
        'export function sample(): number {',
        '  const n = Math.random() + Date.now();',
        "  if (typeof window !== 'undefined') {",
        '    return n + window.innerWidth;',
        '  }',
        '  return n + THREE.MathUtils.floorPowerOfTwo(1);',
        '}',
      ].join('\n');

      const sim = await eslint.lintText(code, { filePath: 'src/sim/bad.ts' });
      const simRules = (sim[0]?.messages ?? []).map((message) => message.ruleId);
      expect(simRules).toContain('no-restricted-imports');
      expect(simRules).toContain('no-restricted-properties');
      expect(simRules).toContain('no-restricted-globals');

      const render = await eslint.lintText(code, { filePath: 'src/render/ok.ts' });
      const restricted = (render[0]?.messages ?? [])
        .map((message) => message.ruleId)
        .filter((ruleId) => ruleId?.startsWith('no-restricted'));
      expect(restricted).toEqual([]);
    },
    // Typed linting has to build a TypeScript program before it can evaluate any
    // rule; on a cold machine that alone can take 5-7 s, which is longer than
    // vitest's default 5 s per-test budget. The requirement under test is *which*
    // rules fire, not how fast ESLint starts, so the budget is raised rather than
    // the assertion relaxed.
    60_000,
  );

  it('[LINT-03] sim tsconfig excludes the DOM lib', () => {
    const sim = JSON.parse(readFileSync('tsconfig.sim.json', 'utf8')) as {
      compilerOptions?: { lib?: string[] };
    };
    expect(sim.compilerOptions?.lib ?? []).not.toContain('DOM');
  });
});
