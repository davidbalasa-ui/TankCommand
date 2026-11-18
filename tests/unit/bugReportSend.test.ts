// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GameServices, type GameServicesHost } from '../../src/game/services';
import {
  BUG_REPORT_ENDPOINT,
  REPORT_LIMITS,
  fitPayload,
  sendBugReport,
  type BugReportPayload,
  type SendResult,
} from '../../src/platform/bugReportSender';
import { MemoryKvStore } from '../../src/platform/kv';
import { SettingsStore } from '../../src/platform/settings';
import { validateReport } from '../../api/bug-report';
import { createWorld } from '../../src/sim/world';

function payload(overrides: Partial<BugReportPayload> = {}): BugReportPayload {
  return {
    message: 'Stuck tank',
    version: '0.1.0',
    platform: 'web',
    device: { userAgent: 'ua', platform: 'Linux', language: 'en', screen: '915x412' },
    lastFreeze: null,
    logs: [],
    save: null,
    ...overrides,
  };
}

const respond = (status: number): typeof fetch => () => Promise.resolve(new Response('{}', { status }));

describe('[BUG-02] sending a bug report', () => {
  it('[BUG-02] posts JSON to the report endpoint and maps each answer', async () => {
    let url = '';
    let init: RequestInit | undefined;
    const ok = await sendBugReport(payload(), {
      fetch: (input, options) => {
        url = String(input);
        init = options;
        return Promise.resolve(new Response('{}', { status: 201 }));
      },
      isOnline: () => true,
    });
    expect(ok).toEqual({ ok: true });
    expect(url).toBe(BUG_REPORT_ENDPOINT);
    expect(BUG_REPORT_ENDPOINT).toBe('https://tankcommand.vercel.app/api/bug-report');
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('omit');

    const cases: Array<[number, SendResult]> = [
      [503, { ok: false, reason: 'notConfigured' }],
      [429, { ok: false, reason: 'rateLimited' }],
      [400, { ok: false, reason: 'rejected' }],
      [502, { ok: false, reason: 'server' }],
    ];
    for (const [status, expected] of cases) {
      expect(await sendBugReport(payload(), { fetch: respond(status), isOnline: () => true })).toEqual(expected);
    }
    const thrown = await sendBugReport(payload(), { fetch: () => Promise.reject(new TypeError('Failed to fetch')), isOnline: () => true });
    expect(thrown).toEqual({ ok: false, reason: 'unreachable' });
  });

  it('[BUG-02] offline sends nothing', async () => {
    let calls = 0;
    const result = await sendBugReport(payload(), {
      fetch: () => {
        calls += 1;
        return Promise.resolve(new Response('{}', { status: 201 }));
      },
      isOnline: () => false,
    });
    expect(result).toEqual({ ok: false, reason: 'offline' });
    expect(calls).toBe(0);
  });

  it('[BUG-02] a request that hangs times out as unreachable', async () => {
    const result = await sendBugReport(payload(), {
      isOnline: () => true,
      timeoutMs: 20,
      fetch: (_input, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(new DOMException('aborted', 'AbortError'));
          });
        }),
    });
    expect(result).toEqual({ ok: false, reason: 'unreachable' });
  });

  it('[BUG-02] the trimmed payload always passes the endpoint validation', () => {
    const fitted = fitPayload(
      payload({
        message: 'm'.repeat(9000),
        device: { userAgent: 'u'.repeat(900), platform: 'p'.repeat(90), language: 'l'.repeat(90), screen: 's'.repeat(90) },
        lastFreeze: 'f'.repeat(900),
        logs: Array.from({ length: 450 }, (_, i) => `${i} ${'x'.repeat(900)}`),
        save: 's'.repeat(REPORT_LIMITS.save + 1),
      }),
    );
    expect(fitted.logs).toHaveLength(REPORT_LIMITS.logLines);
    expect(fitted.logs.at(-1)?.startsWith('449 ')).toBe(true);
    expect(fitted.save).toBeNull();
    expect(validateReport(fitted).ok).toBe(true);
  });
});

describe('[BUG-02] game services send with a local fallback', () => {
  const open: GameServices[] = [];
  beforeEach(() => {
    // jsdom has no blob URLs; the web build's local save is a file download.
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:report', revokeObjectURL: () => undefined }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    for (const services of open.splice(0)) {
      services.dispose();
    }
  });

  function services(sender: (p: BugReportPayload) => Promise<SendResult>): { game: GameServices; sent: BugReportPayload[] } {
    const sent: BugReportPayload[] = [];
    const world = createWorld(3);
    const host: GameServicesHost = {
      getWorld: () => world,
      loadWorld: () => undefined,
      currentScreen: () => 'bugReport',
      inMatch: () => true,
      setCameraTarget: () => undefined,
      setSimSpeed: () => undefined,
      getSimSpeed: () => 1,
      freezeReport: () => ({ channel: 'sim', stalledMs: 2400.4 }) as ReturnType<GameServicesHost['freezeReport']>,
      applySettings: () => undefined,
    };
    const game = new GameServices(host, {
      kv: new MemoryKvStore(),
      settings: new SettingsStore(null),
      mount: document.body,
      sendReport: (p) => {
        sent.push(p);
        return sender(p);
      },
    });
    open.push(game);
    return { game, sent };
  }

  it('[BUG-02] a sent report is not also saved, and carries what the form shows', async () => {
    const { game, sent } = services(() => Promise.resolve({ ok: true }));
    const result = await game.sendBugReport({ message: 'Hill clipping', includeSave: true });
    expect(result.status).toBe('sent');
    expect(result.message).toContain('sent');
    expect(game.lastBugReport()).toBeNull();
    expect(sent[0]?.message).toBe('Hill clipping');
    expect(sent[0]?.platform).toBe('web');
    expect(sent[0]?.lastFreeze).toBe('sim stalled for 2400 ms');
    expect(sent[0]?.save).toContain('"format":"tcsave"');
  });

  it('[BUG-02] a failed send keeps the report as a local file and says it was not sent', async () => {
    const { game } = services(() => Promise.resolve({ ok: false, reason: 'notConfigured' }));
    const result = await game.sendBugReport({ message: 'Hill clipping', includeSave: false });
    expect(result.status).toBe('notSent');
    expect(result.message).toContain('Not sent: the report server is not set up yet');
    expect(result.message).toContain('Saved on this device');
    expect(game.lastBugReport()?.content).toContain('Hill clipping');
  });

  it('[BUG-02] an empty description is not sent', async () => {
    const { game, sent } = services(() => Promise.resolve({ ok: true }));
    const result = await game.sendBugReport({ message: '  ', includeSave: false });
    expect(result.status).toBe('error');
    expect(sent).toHaveLength(0);
  });
});
