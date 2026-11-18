/**
 * Sends a bug report to the game's one server piece, the Vercel function in api/bug-report.ts,
 * which turns it into a GitHub issue. Used only when the player taps Send; the plain Save button
 * never touches the network (BUG-01).
 */

/** The same address from the web build and from the Android app (its WebView is https://localhost). */
export const BUG_REPORT_ENDPOINT = 'https://tankcommand.vercel.app/api/bug-report';

/** Field limits, matching the endpoint's schema so a report is never rejected for length. */
export const REPORT_LIMITS = {
  message: 4000,
  userAgent: 400,
  platform: 64,
  language: 35,
  screen: 20,
  lastFreeze: 300,
  logLines: 200,
  logLine: 500,
  /** A bigger save is left out of the sent report (it stays in the local file). */
  save: 400_000,
  /** The whole request body in bytes, under the endpoint's 512 KiB limit with room to spare. */
  body: 480_000,
} as const;

export interface BugReportPayload {
  message: string;
  version: string;
  platform: 'web' | 'android' | 'ios';
  device: { userAgent: string; platform: string; language: string; screen: string };
  lastFreeze: string | null;
  logs: string[];
  save: string | null;
}

export type SendFailure = 'offline' | 'notConfigured' | 'rateLimited' | 'rejected' | 'server' | 'unreachable';

export type SendResult = { ok: true } | { ok: false; reason: SendFailure };

export interface SendOptions {
  fetch?: typeof fetch;
  endpoint?: string;
  timeoutMs?: number;
  isOnline?: () => boolean;
}

/** Why a report was not sent, in the player's terms. */
export const SEND_FAILURE_TEXT: Record<SendFailure, string> = {
  offline: 'you are offline',
  notConfigured: 'the report server is not set up yet',
  rateLimited: 'too many reports were sent from this connection; try again later',
  rejected: 'the report server did not accept it',
  server: 'the report server had a problem',
  unreachable: 'the report server could not be reached',
};

function clip(value: string, max: number): string {
  return value.length > max ? value.slice(0, max) : value;
}

/** Trims every field to the endpoint's limits. */
export function fitPayload(payload: BugReportPayload): BugReportPayload {
  const fitted = fitFields(payload);
  // A save is escaped again inside the JSON body; if the body still runs over, send it without.
  if (fitted.save !== null && new TextEncoder().encode(JSON.stringify(fitted)).length > REPORT_LIMITS.body) {
    return { ...fitted, save: null };
  }
  return fitted;
}

function fitFields(payload: BugReportPayload): BugReportPayload {
  return {
    message: clip(payload.message, REPORT_LIMITS.message),
    version: payload.version,
    platform: payload.platform,
    device: {
      userAgent: clip(payload.device.userAgent, REPORT_LIMITS.userAgent),
      platform: clip(payload.device.platform, REPORT_LIMITS.platform),
      language: clip(payload.device.language, REPORT_LIMITS.language),
      screen: clip(payload.device.screen, REPORT_LIMITS.screen),
    },
    lastFreeze: payload.lastFreeze === null ? null : clip(payload.lastFreeze, REPORT_LIMITS.lastFreeze),
    logs: payload.logs.slice(-REPORT_LIMITS.logLines).map((line) => clip(line, REPORT_LIMITS.logLine)),
    save: payload.save !== null && payload.save.length <= REPORT_LIMITS.save ? payload.save : null,
  };
}

function defaultOnline(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

export async function sendBugReport(payload: BugReportPayload, options: SendOptions = {}): Promise<SendResult> {
  const online = options.isOnline ?? defaultOnline;
  if (!online()) {
    return { ok: false, reason: 'offline' };
  }
  const doFetch = options.fetch ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
  }, options.timeoutMs ?? 15_000);
  try {
    const response = await doFetch(options.endpoint ?? BUG_REPORT_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fitPayload(payload)),
      signal: controller.signal,
      credentials: 'omit',
    });
    if (response.ok) {
      return { ok: true };
    }
    if (response.status === 503) {
      return { ok: false, reason: 'notConfigured' };
    }
    if (response.status === 429) {
      return { ok: false, reason: 'rateLimited' };
    }
    if (response.status >= 400 && response.status < 500) {
      return { ok: false, reason: 'rejected' };
    }
    return { ok: false, reason: 'server' };
  } catch {
    return { ok: false, reason: 'unreachable' };
  } finally {
    clearTimeout(timer);
  }
}
