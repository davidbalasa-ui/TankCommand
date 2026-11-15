import type { ScreenContext } from './router';
import { button } from './controls';

function formatFreeze(ctx: ScreenContext): string {
  const report = ctx.api?.lastFreezeReport();
  if (!report) {
    return 'No freeze recorded.';
  }
  return `${report.channel} stalled for ${Math.round(report.stalledMs)} ms.`;
}

/**
 * Two columns so the description, the include-save checkbox, the log preview,
 * the status line and both buttons are all on screen at 915x412. A single
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
    `Version: ${api?.version() ?? '0.1.0'}`,
    `Device: ${navigator.userAgent}`,
    `Last freeze: ${formatFreeze(ctx)}`,
    `Log lines: ${logs.length}`,
  ].join('\n');

  const textarea = document.createElement('textarea');
  textarea.className = 'bug-text';
  textarea.placeholder = 'What went wrong?';
  textarea.setAttribute('aria-label', 'Bug description');

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

  const save = button('bugReport', 'save', 'Save report', () => {
    void (async () => {
      if (!api) {
        status.textContent = 'Bug reports are unavailable in this environment.';
        return;
      }
      save.disabled = true;
      status.textContent = 'Saving…';
      const result = await api.saveBugReport({
        message: textarea.value,
        includeSave: include.checked,
      });
      status.textContent =
        result.status === 'ok' ? `Saved ${result.fileName ?? ''}`.trim() : result.message;
      save.disabled = false;
    })();
  });

  const back = button('bugReport', 'back', 'Back', () => {
    ctx.router.back();
  });

  left.append(meta, textarea, includeRow);
  right.append(logBox, status, save, back);
  form.append(left, right);
  root.append(form);

  return () => {
    // Screen cleanup removes the DOM.
  };
}
