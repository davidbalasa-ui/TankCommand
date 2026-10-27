import { execFileSync, spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

function walk(dir: string): string[] {
  const files: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const info = statSync(full);
    if (info.isDirectory()) {
      files.push(...walk(full));
    } else {
      files.push(full);
    }
  }
  return files;
}

async function waitForUrl(url: string): Promise<void> {
  for (let i = 0; i < 80; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // Server may still be starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Server did not start at ${url}`);
}

test('[HOOK-01] production build has no test hook marker or window hook', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'production build check runs once');
  test.setTimeout(180_000);

  const root = process.cwd();
  const temp = mkdtempSync(join(tmpdir(), 'tc-prod-'));
  const outDir = join(temp, 'dist');
  const env = { ...process.env };
  delete env.VITE_TEST_HOOK;
  const port = 4174;
  let server: ReturnType<typeof spawn> | null = null;

  try {
    execFileSync('npx', ['vite', 'build', '--outDir', outDir, '--emptyOutDir'], {
      cwd: root,
      env,
      stdio: 'pipe',
    });

    const jsFiles = walk(outDir).filter((file) => file.endsWith('.js'));
    expect(jsFiles.length).toBeGreaterThan(0);
    for (const file of jsFiles) {
      expect(readFileSync(file, 'utf8')).not.toContain('__TC_TEST__');
    }

    server = spawn(
      'npx',
      ['vite', 'preview', '--outDir', outDir, '--port', String(port), '--strictPort'],
      { cwd: root, env, stdio: 'ignore' },
    );
    await waitForUrl(`http://127.0.0.1:${port}/`);
    await page.goto(`http://127.0.0.1:${port}/`);
    await page.waitForTimeout(500);
    const hasHook = await page.evaluate(() => '__TC_TEST__' in window);
    expect(hasHook).toBe(false);
  } finally {
    server?.kill('SIGTERM');
    rmSync(temp, { recursive: true, force: true });
  }
});
