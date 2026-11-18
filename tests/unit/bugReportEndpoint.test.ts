import { describe, expect, it } from 'vitest';
import {
  MAX_BODY_BYTES,
  MAX_ISSUE_BODY,
  buildIssue,
  createHandlers,
  createRateLimiter,
  isAllowedOrigin,
  scrub,
  validateReport,
  type BugReportPayload,
  type HandlerDeps,
} from '../../api/bug-report';

function report(overrides: Partial<BugReportPayload> = {}): BugReportPayload {
  return {
    message: 'Tank drove through a hill.',
    version: '0.1.0',
    platform: 'android',
    device: { userAgent: 'Mozilla/5.0 (Linux; Android 14)', platform: 'Linux armv8l', language: 'en-GB', screen: '915x412' },
    lastFreeze: null,
    logs: ['[info] boot', '[warn] slow frame'],
    save: null,
    ...overrides,
  };
}

interface Sent {
  url: string;
  headers: Record<string, string>;
  body: { title: string; body: string; labels: string[] };
}

function harness(options: { env?: { token?: string; repo?: string }; status?: number; throws?: boolean } = {}) {
  const sent: Sent[] = [];
  let now = 1_000_000;
  const deps: HandlerDeps = {
    env: () => options.env ?? { token: 'secret-token', repo: 'owner/TankCommand' },
    fetch: (input, init) => {
      if (options.throws) {
        return Promise.reject(new Error('offline'));
      }
      sent.push({
        url: String(input),
        headers: init?.headers as Record<string, string>,
        body: JSON.parse(String(init?.body)) as Sent['body'],
      });
      return Promise.resolve(new Response('{}', { status: options.status ?? 201 }));
    },
    now: () => now,
    limiter: createRateLimiter({ max: 2, windowMs: 60_000 }),
  };
  return {
    handlers: createHandlers(deps),
    sent,
    advance: (ms: number) => {
      now += ms;
    },
  };
}

function post(body: unknown, headers: Record<string, string> = {}): Request {
  return new Request('https://tankcommand.vercel.app/api/bug-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-forwarded-for': '203.0.113.7, 10.0.0.1', ...headers },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

describe('[BUG-03] bug-report endpoint validation', () => {
  it('[BUG-03] accepts a well-formed report and drops unknown fields', () => {
    const result = validateReport({ ...report(), email: 'player@example.com', ip: '203.0.113.7' });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.report).not.toHaveProperty('email');
      expect(result.report).not.toHaveProperty('ip');
    }
  });

  it('[BUG-03] rejects a blank message, a bad version, an unknown platform and oversized fields', () => {
    expect(validateReport(report({ message: '   ' })).ok).toBe(false);
    expect(validateReport(report({ message: 'x'.repeat(4001) })).ok).toBe(false);
    expect(validateReport(report({ version: '<script>' })).ok).toBe(false);
    expect(validateReport({ ...report(), platform: 'desktop' }).ok).toBe(false);
    expect(validateReport(report({ logs: Array.from({ length: 201 }, () => 'line') })).ok).toBe(false);
    expect(validateReport(report({ logs: ['x'.repeat(501)] })).ok).toBe(false);
    expect(validateReport(report({ device: { ...report().device, userAgent: 'u'.repeat(401) } })).ok).toBe(false);
    expect(validateReport(null).ok).toBe(false);
    expect(validateReport('text').ok).toBe(false);
    const missing: Record<string, unknown> = { ...report() };
    delete missing['logs'];
    expect(validateReport(missing).ok).toBe(false);
  });

  it('[BUG-03] scrubs email and IP addresses from free text', () => {
    expect(scrub('mail me at someone@example.org from 192.168.1.20')).toBe('mail me at [email removed] from [ip removed]');
    expect(scrub('v6 2001:db8:85a3:0:0:8a2e:370:7334 here')).toBe('v6 [ip removed] here');
    expect(scrub('version 0.1.0 tick 12.5')).toBe('version 0.1.0 tick 12.5');
  });

  it('[BUG-03] builds an issue that fits GitHub, keeps the newest log lines and omits a save that does not fit', () => {
    const logs = Array.from({ length: 200 }, (_, i) => `line ${i} ${'x'.repeat(480)}`);
    const big = buildIssue(report({ logs, save: 'y'.repeat(300_000) }));
    expect(big.body.length).toBeLessThanOrEqual(MAX_ISSUE_BODY);
    expect(big.body).toContain('line 199');
    expect(big.body).toContain('Save file not attached');
    const small = buildIssue(report({ save: '{"world":1}' }));
    expect(small.body).toContain('{"world":1}');
    expect(small.title).toBe('Bug report (android 0.1.0): Tank drove through a hill.');
    const fence = buildIssue(report({ logs: ['```\n## injected'] }));
    expect(fence.body.match(/```/g)?.length).toBe(2);
  });

  it('[BUG-03] allows the web build and the Capacitor app origins only', () => {
    expect(isAllowedOrigin('https://tankcommand.vercel.app')).toBe(true);
    expect(isAllowedOrigin('https://localhost')).toBe(true);
    expect(isAllowedOrigin('capacitor://localhost')).toBe(true);
    expect(isAllowedOrigin('http://localhost:5173')).toBe(true);
    expect(isAllowedOrigin('https://evil.example')).toBe(false);
    expect(isAllowedOrigin('https://localhost.evil.example')).toBe(false);
  });
});

describe('[BUG-03] bug-report endpoint handler', () => {
  it('[BUG-03] creates a labelled GitHub issue without the IP address', async () => {
    const h = harness();
    const response = await h.handlers.POST(post(report(), { origin: 'https://localhost' }));
    expect(response.status).toBe(201);
    expect(response.headers.get('access-control-allow-origin')).toBe('https://localhost');
    expect(h.sent).toHaveLength(1);
    const call = h.sent[0];
    expect(call?.url).toBe('https://api.github.com/repos/owner/TankCommand/issues');
    expect(call?.headers['Authorization']).toBe('Bearer secret-token');
    expect(call?.body.labels).toEqual(['bug-report']);
    expect(call?.body.body).toContain('Tank drove through a hill.');
    expect(JSON.stringify(call?.body)).not.toContain('203.0.113.7');
  });

  it('[BUG-03] answers 503 when GITHUB_TOKEN or GITHUB_REPO is missing', async () => {
    for (const env of [{}, { token: 't' }, { repo: 'owner/repo' }, { token: 't', repo: 'not a repo' }]) {
      const h = harness({ env });
      const response = await h.handlers.POST(post(report()));
      expect(response.status).toBe(503);
      expect(h.sent).toHaveLength(0);
    }
  });

  it('[BUG-03] rejects bad JSON, invalid reports and oversized bodies', async () => {
    const h = harness();
    expect((await h.handlers.POST(post('{not json'))).status).toBe(400);
    expect((await h.handlers.POST(post(report({ message: '' })))).status).toBe(400);
    expect((await h.handlers.POST(post('x'.repeat(MAX_BODY_BYTES + 1)))).status).toBe(413);
    expect(h.sent).toHaveLength(0);
  });

  it('[BUG-03] refuses other origins and answers the CORS preflight for allowed ones', async () => {
    const h = harness();
    expect((await h.handlers.POST(post(report(), { origin: 'https://evil.example' }))).status).toBe(403);
    const preflight = h.handlers.OPTIONS(
      new Request('https://tankcommand.vercel.app/api/bug-report', { method: 'OPTIONS', headers: { origin: 'capacitor://localhost' } }),
    );
    expect(preflight.status).toBe(204);
    expect(preflight.headers.get('access-control-allow-origin')).toBe('capacitor://localhost');
    expect(preflight.headers.get('access-control-allow-headers')).toContain('Content-Type');
    const denied = h.handlers.OPTIONS(
      new Request('https://tankcommand.vercel.app/api/bug-report', { method: 'OPTIONS', headers: { origin: 'https://evil.example' } }),
    );
    expect(denied.status).toBe(403);
  });

  it('[BUG-03] rate-limits per IP in memory and lets the window pass', async () => {
    const h = harness();
    expect((await h.handlers.POST(post(report()))).status).toBe(201);
    expect((await h.handlers.POST(post(report()))).status).toBe(201);
    expect((await h.handlers.POST(post(report()))).status).toBe(429);
    // Another address is not affected.
    expect((await h.handlers.POST(post(report(), { 'x-forwarded-for': '198.51.100.4' }))).status).toBe(201);
    h.advance(60_000);
    expect((await h.handlers.POST(post(report()))).status).toBe(201);
  });

  it('[BUG-03] reports GitHub failures as 502', async () => {
    expect((await harness({ status: 401 }).handlers.POST(post(report()))).status).toBe(502);
    expect((await harness({ throws: true }).handlers.POST(post(report()))).status).toBe(502);
  });
});
