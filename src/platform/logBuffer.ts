export interface LogLine {
  level: string;
  text: string;
}

const MAX_LINES = 200;
const lines: LogLine[] = [];

export function pushLog(level: string, text: string): void {
  lines.push({ level, text });
  while (lines.length > MAX_LINES) {
    lines.shift();
  }
}

export function recentLogs(limit = MAX_LINES): string[] {
  const count = Math.max(0, Math.min(limit, MAX_LINES));
  return lines.slice(-count).map((line) => `[${line.level}] ${line.text}`);
}
