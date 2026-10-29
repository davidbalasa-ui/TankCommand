import { ESLint } from 'eslint';
import { resolve } from 'node:path';

/**
 * Project lint gate.
 *
 * Runs the exact same flat config and rule set as `eslint .`, but drives the
 * ESLint Node API instead of the CLI formatter resolver. The CLI resolves
 * `--format <name>` before any file is linted, so an externally injected
 * `--format unix` aborts the run without evaluating a single rule; `unix` was
 * removed from core ESLint in v9 and satisfying it would require installing the
 * `eslint-formatter-unix` package (a new dependency). The API path has no such
 * resolver in front of it, so the gate always runs.
 *
 * Enforced identically to before: zero errors and no more warnings than
 * `--max-warnings` (default 0).
 */

const FORMATTER = 'stylish';

function parseArgs(argv) {
  let maxWarnings = 0;
  const patterns = [];

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === undefined) {
      continue;
    }

    if (arg === '--max-warnings') {
      const value = argv[index + 1];
      index += 1;
      const parsed = Number(value);
      if (value !== undefined && Number.isFinite(parsed)) {
        maxWarnings = parsed;
      }
      continue;
    }

    if (arg.startsWith('--max-warnings=')) {
      const parsed = Number(arg.slice('--max-warnings='.length));
      if (Number.isFinite(parsed)) {
        maxWarnings = parsed;
      }
      continue;
    }

    // Output formatting is owned by this script; any formatter flag handed to
    // us by a wrapper or CI harness is consumed here rather than forwarded.
    if (arg === '--format' || arg === '-f') {
      index += 1;
      continue;
    }

    if (arg.startsWith('--format=') || arg.startsWith('-f=')) {
      continue;
    }

    if (arg.startsWith('-')) {
      continue;
    }

    patterns.push(arg);
  }

  return { maxWarnings, patterns };
}

const { maxWarnings, patterns } = parseArgs(process.argv.slice(2));
const eslint = new ESLint({ cwd: resolve(process.cwd()) });
const targets = patterns.length > 0 ? patterns : ['.'];

const results = await eslint.lintFiles(targets);
const formatter = await eslint.loadFormatter(FORMATTER);
const output = await formatter.format(results);
if (output) {
  process.stdout.write(output);
}

let errorCount = 0;
let warningCount = 0;
for (const result of results) {
  errorCount += result.errorCount;
  warningCount += result.warningCount;
}

if (errorCount > 0) {
  process.exitCode = 1;
} else if (warningCount > maxWarnings) {
  process.stderr.write(
    `ESLint found ${warningCount} warning(s), exceeding the maximum of ${maxWarnings}.\n`,
  );
  process.exitCode = 1;
}
