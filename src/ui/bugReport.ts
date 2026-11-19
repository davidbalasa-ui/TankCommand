import type { ScreenContext } from './router';
import { button } from './controls';
import { APP_VERSION } from '../platform/appInfo';
import { REPORT_LIMITS } from '../platform/bugReportSender';

function formatFreeze(ctx: ScreenContext): string {
  const report = ctx.api?.lastFreezeReport();
  if (!report) {
    return 'No freeze recorded.';
  }
  return `${report.channel} stalled for ${Math.round(report.stalledMs)} ms.`;
}

/**
 * Two columns so the description, the include-save checkbox, the log preview,
 * the status line and the Send and Save buttons are all on screen at 915x412. A single
 * column needs ~570 px and, with `touch-action: none` on <html> (TCH-04), the
 * player cannot scroll to the Save/Back buttons that would sit below the fold.
 */
export function mountBugReport(root: HTMLElement, ctx: ScreenContext): () => void {
  const api = ctx.api;
  const form = document.createElement('div');
  form.className = 'bug-report-form';
  const left = document.createElement('div');
  left.className = 'bug-col';
  const right = document.createElement('div');
  right.className = 'bug-col';

  const meta = document.createElement('pre');
  meta.className = 'bug-meta';
  meta.dataset.bugMeta = 'true';
  const logs = api?.logs() ?? [];
  meta.textContent = [
    `Version: ${api?.version() ?? APP_VERSION}`,
    `Device: ${navigator.userAgent}`,
    `Last freeze: ${formatFreeze(ctx)}`,
    `Log lines: ${logs.length}`,
  ].join('\n');

  const textarea = document.createElement('textarea');
  textarea.className = 'bug-text';
  textarea.placeholder = 'What went wrong?';
  textarea.setAttribute('aria-label', 'Bug description');
  textarea.maxLength = REPORT_LIMITS.message;

  const includeRow = document.createElement('label');
  includeRow.className = 'setting-row';
  const include = document.createElement('input');
  include.type = 'checkbox';
  include.dataset.setting = 'bugReport.includeSave';
  const includeText = document.createElement('span');
  includeText.textContent = 'Include save file';
  includeRow.append(include, includeText);

  const logBox = document.createElement('pre');
  logBox.className = 'bug-logs';
  logBox.textContent = logs.join('\n') || 'No log lines captured.';

  const status = document.createElement('p');
  status.className = 'bug-status';
  status.dataset.bugStatus = 'true';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');

  const note = document.createElement('p');
  note.className = 'bug-note';
  note.textContent = 'Send posts this report, with the version, device and log shown here, to the developer. Save keeps a file on this device and sends nothing.';

  const setStatus = (text: string, result: string): void => {
    status.textContent = text;
    status.dataset.bugResult = result;
  };

  let busy = false;
  const run = (job: (api: NonNullable<typeof ctx.api>) => Promise<void>): void => {
    if (busy) {
      return;
    }
    if (!api) {
      setStatus('Bug reports are unavailable in this environment.', 'error');
      return;
    }
    busy = true;
    send.disabled = true;
    save.disabled = true;
    void job(api).finally(() => {
      busy = false;
      send.disabled = false;
      save.disabled = false;
    });
  };

  const send = button('bugReport', 'send', 'Send report', () => {
    run(async (game) => {
      setStatus('Sending…', 'pending');
      const result = await game.sendBugReport({ message: textarea.value, includeSave: include.checked });
      setStatus(result.message, result.status);
    });
  });
  send.classList.add('primary');

  const save = button('bugReport', 'save', 'Save to device', () => {
    run(async (game) => {
      setStatus('Saving…', 'pending');
      const result = await game.saveBugReport({ message: textarea.value, includeSave: include.checked });
      setStatus(result.status === 'ok' ? `Saved ${result.fileName ?? ''}`.trim() : result.message, result.status);
    });
  });

  const actions = document.createElement('div');
  actions.className = 'bug-actions';
  actions.append(send, save);

  const back = button('bugReport', 'back', 'Back', () => {
    ctx.router.back();
  });

  left.append(meta, textarea, includeRow);
  right.append(logBox, note, status, actions, back);
  form.append(left, right);
  root.append(form);

  return () => {
    // Screen cleanup removes the DOM.
  };
}
