/**
 * POST /api/bug-report: the game's only server piece (Vercel function).
 *
 * It takes a bug report the player chose to send, checks and trims it, and opens a GitHub issue
 * labelled `bug-report` in GITHUB_REPO using GITHUB_TOKEN. Nothing is stored here: no database,
 * no logs of reports, and the sender's IP address is used only, salted and hashed, as the key of
 * an in-memory rate limit that disappears with the function instance. Unknown fields are dropped,
 * and email addresses and IP addresses found in the free text are blanked out before the issue
 * is written.
 *
 * Status codes: 201 sent; 204 CORS preflight; 400 invalid report; 403 origin not allowed;
 * 413 too large; 429 rate limited; 502 GitHub refused; 503 not configured (env vars missing).
 */
import { createHash, randomBytes } from 'node:crypto';
import { z } from 'zod';

/** Largest request body accepted, in bytes (a report with a mid-match save fits well inside). */
export const MAX_BODY_BYTES = 512 * 1024;
/** GitHub caps an issue body at 65536 characters; stay safely below it. */
export const MAX_ISSUE_BODY = 60_000;
export const RATE_LIMIT = { max: 5, windowMs: 10 * 60_000 } as const;

/** Origins that may call the endpoint from a browser: the web build and the Android app's WebView. */
export function isAllowedOrigin(origin: string): boolean {
  return (
    origin === 'https://tankcommand.vercel.app' ||
    origin === 'https://localhost' ||
    origin === 'capacitor://localhost' ||
    /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/.test(origin)
  );
}

const text = (max: number) => z.string().max(max);

export const reportSchema = z
  .object({
    message: text(4000).refine((value) => value.trim().length > 0, 'Describe the problem.'),
    version: z.string().regex(/^[0-9A-Za-z.+-]{1,32}$/),
    platform: z.enum(['web', 'android', 'ios']),
    device: z
      .object({
        userAgent: text(400),
        platform: text(64),
        language: text(35),
        screen: text(20),
      })
      .strip(),
    lastFreeze: text(300).nullable(),
    logs: z.array(text(500)).max(200),
    save: z.string().max(MAX_BODY_BYTES).nullable(),
  })
  .strip();

export type BugReportPayload = z.infer<typeof reportSchema>;

export type ValidationResult = { ok: true; report: BugReportPayload } | { ok: false; error: string };

export function validateReport(input: unknown): ValidationResult {
  const parsed = reportSchema.safeParse(input);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    const where = issue?.path.join('.') || 'report';
    return { ok: false, error: `${where}: ${issue?.message ?? 'invalid'}` };
  }
  return { ok: true, report: parsed.data };
}

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const IPV4 = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;
const IPV6 = /\b(?:[0-9A-Fa-f]{1,4}:){4,7}[0-9A-Fa-f]{1,4}\b/g;

/** Blanks out anything in free text that could identify the sender (emails, IP addresses). */
export function scrub(value: string): string {
  return value.replace(EMAIL, '[email removed]').replace(IPV4, '[ip removed]').replace(IPV6, '[ip removed]');
}

/** Text that cannot break out of a Markdown code fence. */
function fenced(value: string): string {
  return value.replace(/```/g, '`​``');
}

export function buildIssue(report: BugReportPayload): { title: string; body: string } {
  const message = scrub(report.message.trim());
  const firstLine = message.split('\n')[0] ?? '';
  const title = `Bug report (${report.platform} ${report.version}): ${
    firstLine.length > 60 ? `${firstLine.slice(0, 57)}...` : firstLine
  }`;
  const head = [
    '### What went wrong',
    '',
    message,
    '',
    '### App',
    '',
    `- Version: ${report.version}`,
    `- Platform: ${report.platform}`,
    `- Device: ${scrub(report.device.userAgent)}`,
    `- Screen: ${scrub(report.device.screen)} · Language: ${scrub(report.device.language)} · ${scrub(report.device.platform)}`,
    `- Last freeze: ${report.lastFreeze ? scrub(report.lastFreeze) : 'none'}`,
    '',
  ].join('\n');
  const tail = '\n\n_Sent from the in-game bug report. No IP address or account is stored._';
  let budget = MAX_ISSUE_BODY - head.length - tail.length;

  const sections: string[] = [];
  // Logs: newest lines are the useful ones, so keep the end when trimming.
  const logLines = report.logs.map(scrub);
  let logText = logLines.join('\n');
  const logBudget = Math.max(0, Math.floor(budget * 0.4));
  if (logText.length > logBudget) {
    logText = `[older lines trimmed]\n${logText.slice(logText.length - logBudget)}`;
  }
  const logs = `<details><summary>Log (${logLines.length} lines)</summary>\n\n\`\`\`\n${fenced(logText || 'No log lines.')}\n\`\`\`\n</details>`;
  sections.push(logs);
  budget -= logs.length;

  if (report.save !== null) {
    const save = `\n\n<details><summary>Save file</summary>\n\n\`\`\`json\n${fenced(report.save)}\n\`\`\`\n</details>`;
    if (save.length <= budget) {
      sections.push(save);
    } else {
      sections.push(`\n\nSave file not attached: ${Math.ceil(report.save.length / 1024)} KB is over the issue size limit.`);
    }
  }
  return { title, body: `${head}\n${sections.join('')}${tail}` };
}

export interface RateLimiter {
  /** True when the caller may send now (and counts this send). */
  take(ip: string, now: number): boolean;
}

/** A per-IP sliding window kept only in memory. Keys are salted hashes, never the raw address. */
export function createRateLimiter(limit: { max: number; windowMs: number } = RATE_LIMIT): RateLimiter {
  const salt = randomBytes(16).toString('hex');
  const hits = new Map<string, number[]>();
  return {
    take(ip, now) {
      const key = createHash('sha256').update(salt).update(ip).digest('hex');
      if (hits.size > 5000) {
        for (const [other, times] of hits) {
          if (times.every((time) => now - time >= limit.windowMs)) {
            hits.delete(other);
          }
        }
      }
      const recent = (hits.get(key) ?? []).filter((time) => now - time < limit.windowMs);
      if (recent.length >= limit.max) {
        hits.set(key, recent);
        return false;
      }
      recent.push(now);
      hits.set(key, recent);
      return true;
    },
  };
}

export interface HandlerDeps {
  env: () => { token?: string; repo?: string };
  fetch: typeof fetch;
  now: () => number;
  limiter: RateLimiter;
}

function clientIp(request: Request): string {
  const forwarded = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim();
  return forwarded || request.headers.get('x-real-ip') || 'unknown';
}

function corsHeaders(request: Request): Record<string, string> {
  const origin = request.headers.get('origin');
  const headers: Record<string, string> = { Vary: 'Origin' };
  if (origin && isAllowedOrigin(origin)) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS';
    headers['Access-Control-Allow-Headers'] = 'Content-Type';
    headers['Access-Control-Max-Age'] = '86400';
  }
  return headers;
}

function json(request: Request, status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...corsHeaders(request) },
  });
}

export function createHandlers(deps: HandlerDeps): {
  OPTIONS: (request: Request) => Response;
  POST: (request: Request) => Promise<Response>;
} {
  return {
    OPTIONS(request) {
      const origin = request.headers.get('origin');
      if (origin && !isAllowedOrigin(origin)) {
        return new Response(null, { status: 403, headers: { Vary: 'Origin' } });
      }
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    },

    async POST(request) {
      const origin = request.headers.get('origin');
      if (origin && !isAllowedOrigin(origin)) {
        return json(request, 403, { error: 'origin_not_allowed' });
      }
      const { token, repo } = deps.env();
      if (!token || !repo || !/^[\w.-]+\/[\w.-]+$/.test(repo)) {
        return json(request, 503, { error: 'not_configured' });
      }
      const declared = Number(request.headers.get('content-length') ?? '0');
      if (declared > MAX_BODY_BYTES) {
        return json(request, 413, { error: 'too_large' });
      }
      const raw = await request.text();
      if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) {
        return json(request, 413, { error: 'too_large' });
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        return json(request, 400, { error: 'invalid_json' });
      }
      const result = validateReport(parsed);
      if (!result.ok) {
        return json(request, 400, { error: 'invalid_report', detail: result.error });
      }
      // Counted only for well-formed reports, so a player whose first try was rejected can retry.
      if (!deps.limiter.take(clientIp(request), deps.now())) {
        return json(request, 429, { error: 'rate_limited' });
      }
      const issue = buildIssue(result.report);
      let response: Response;
      try {
        response = await deps.fetch(`https://api.github.com/repos/${repo}/issues`, {
          method: 'POST',
          headers: {
            Accept: 'application/vnd.github+json',
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
            'User-Agent': 'tankcommand-bug-report',
            'X-GitHub-Api-Version': '2022-11-28',
          },
          body: JSON.stringify({ title: issue.title, body: issue.body, labels: ['bug-report'] }),
        });
      } catch {
        return json(request, 502, { error: 'github_unreachable' });
      }
      if (!response.ok) {
        return json(request, 502, { error: 'github_error', status: response.status });
      }
      return json(request, 201, { status: 'sent' });
    },
  };
}

const handlers = createHandlers({
  env: () => ({ token: process.env.GITHUB_TOKEN, repo: process.env.GITHUB_REPO }),
  fetch: (input, init) => fetch(input, init),
  now: () => Date.now(),
  limiter: createRateLimiter(),
});

export const OPTIONS = handlers.OPTIONS;
export const POST = handlers.POST;
