import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

function arg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const requirementsPath = arg('--requirements') ?? 'docs/requirements.md';
const testsDir = arg('--tests') ?? 'tests';

const requirements = readFileSync(requirementsPath, 'utf8');
const ids = [...new Set(requirements.match(/\b[A-Z]{2,}-\d{2}\b/g) ?? [])].sort();

function walk(dir) {
  const files = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const info = statSync(full);
    if (info.isDirectory()) {
      files.push(...walk(full));
    } else if (name.endsWith('.ts')) {
      files.push(full);
    }
  }
  return files;
}

const testText = walk(testsDir)
  .map((file) => readFileSync(file, 'utf8'))
  .join('\n');

const rows = ids.map((id) => ({ id, covered: testText.includes(`[${id}]`) }));

console.log('Requirement | Covered');
console.log('--- | ---');
for (const row of rows) {
  console.log(`${row.id} | ${row.covered ? 'yes' : 'NO'}`);
}

const missing = rows.filter((row) => !row.covered).map((row) => row.id);
if (missing.length > 0) {
  console.error(`Missing requirement tests: ${missing.join(', ')}`);
  process.exit(1);
}
