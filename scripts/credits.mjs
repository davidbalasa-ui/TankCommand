import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

function arg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const manifestPath =
  arg('--manifest') ?? process.env.TC_MANIFEST_PATH ?? 'public/assets/manifest.json';
const outPath = arg('--out') ?? process.env.TC_CREDITS_PATH ?? 'CREDITS.md';
const check = process.argv.includes('--check');
const customOut = Boolean(arg('--out') ?? process.env.TC_CREDITS_PATH);

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
if (!manifest || !Array.isArray(manifest.assets)) {
  console.error('Invalid asset manifest');
  process.exit(1);
}

const assets = [...manifest.assets].sort((a, b) => String(a.id).localeCompare(String(b.id)));

function escapeCell(value) {
  return String(value ?? '').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

const lines = [
  '# Credits',
  '',
  'TankCommand asset credits. Generated from `public/assets/manifest.json`; do not edit by hand.',
  '',
  '| Asset | Author | Licence | Source | Used for |',
  '| --- | --- | --- | --- | --- |',
];

for (const asset of assets) {
  const credit = asset.credit ?? {};
  lines.push(
    `| ${escapeCell(asset.id)} | ${escapeCell(credit.author)} | ${escapeCell(
      credit.license,
    )} | ${escapeCell(credit.source ?? '-')} | ${escapeCell(credit.usedFor)} |`,
  );
}

const content = `${lines.join('\n')}\n`;

function writeOrCheck(path) {
  if (check) {
    const current = existsSync(path) ? readFileSync(path, 'utf8') : '';
    if (current !== content) {
      console.error(`Stale credits: ${path}`);
      const currentLines = new Set(current.split('\n'));
      for (const line of content.split('\n')) {
        if (!currentLines.has(line)) {
          console.error(`+ ${line}`);
        }
      }
      process.exitCode = 1;
    }
    return;
  }
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content);
}

writeOrCheck(outPath);
if (!customOut) {
  writeOrCheck('public/CREDITS.md');
}

if (process.exitCode) {
  process.exit(process.exitCode);
}
