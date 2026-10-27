import { copyFileSync, mkdtempSync, appendFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { describe, expect, it } from 'vitest';
import capacitorConfig from '../../capacitor.config';

describe('project configuration', () => {
  it('[CAP-01] capacitor config has the required app id, web dir and no server url', () => {
    expect(capacitorConfig.appId).toBe('com.davidbalasa.tankcommand');
    expect(capacitorConfig.webDir).toBe('dist');
    expect(capacitorConfig.server?.url).toBeUndefined();
  });

  it('[CI-01] github workflow runs the full ci and e2e commands', () => {
    const yaml = readFileSync('.github/workflows/ci.yml', 'utf8');
    expect(yaml).toContain('node-version: 22');
    expect(yaml).toContain('npm ci');
    expect(yaml).toContain('npm run ci');
    expect(yaml).toContain('npm run test:e2e');
  });

  it('[REQ-01] requirement coverage passes and fails when an untested id is appended', () => {
    const root = process.cwd();
    const real = spawnSync(process.execPath, ['scripts/req-coverage.mjs'], {
      cwd: root,
      encoding: 'utf8',
    });
    expect(real.status).toBe(0);

    const temp = mkdtempSync(join(tmpdir(), 'tc-req-'));
    try {
      const tempRequirements = join(temp, 'requirements.md');
      copyFileSync('docs/requirements.md', tempRequirements);
      appendFileSync(tempRequirements, '\n| FAKE-99 | Uncovered fake requirement |\n');
      const failing = spawnSync(
        process.execPath,
        ['scripts/req-coverage.mjs', '--requirements', tempRequirements],
        { cwd: root, encoding: 'utf8' },
      );
      expect(failing.status).not.toBe(0);
      expect(`${failing.stdout}${failing.stderr}`).toContain('FAKE-99');
    } finally {
      rmSync(temp, { recursive: true, force: true });
    }
  });
});
