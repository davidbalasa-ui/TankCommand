import type { ScreenContext } from './router';
import type { SaveSlotSummary } from '../game/api';
import { button } from './controls';

const SLOTS = 5;

function formatDate(iso: string | null): string {
  if (!iso) {
    return '';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function formatPlayed(seconds: number | undefined): string {
  if (seconds === undefined) {
    return '';
  }
  const total = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')} played`;
}

/**
 * Save / Load. Over a running match every slot offers Save, Load and Delete; opened from the
 * title screen there is nothing to save, so a slot offers Load and Delete. Overwriting a slot
 * and deleting one each ask first, in place of the row's buttons (no browser dialogs).
 */
export function mountSaveSlots(root: HTMLElement, ctx: ScreenContext): () => void {
  const api = ctx.api;
  const inMatch = ctx.inMatch?.() ?? true;
  const status = document.createElement('p');
  status.className = 'save-status';
  status.dataset.saveStatus = 'true';
  status.textContent = inMatch ? 'Choose a slot.' : 'Choose a saved game to load.';
  const list = document.createElement('div');
  list.className = 'save-list';
  root.append(status, list);

  interface Row {
    index: number;
    slot: string;
    el: HTMLDivElement;
    title: HTMLSpanElement;
    detail: HTMLSpanElement;
    actions: HTMLDivElement;
    save: HTMLButtonElement | null;
    load: HTMLButtonElement;
    remove: HTMLButtonElement;
    summary: SaveSlotSummary | null;
  }
  const rows: Row[] = [];
  let closeConfirm: (() => void) | null = null;

  const unavailable = (): boolean => {
    if (!api) {
      status.textContent = 'Saves are unavailable in this environment.';
      return true;
    }
    return false;
  };

  /** Swaps a row's buttons for a question with large Confirm / Cancel buttons. */
  const ask = (row: Row, question: string, confirmName: string, confirmLabel: string, onConfirm: () => void): void => {
    closeConfirm?.();
    const panel = document.createElement('div');
    panel.className = 'save-confirm';
    const text = document.createElement('span');
    text.className = 'save-confirm-text';
    text.textContent = question;
    const yes = button('saveSlots', confirmName, confirmLabel, () => {
      close();
      onConfirm();
    });
    yes.classList.add('danger');
    const no = button('saveSlots', 'cancelConfirm', 'Cancel', () => {
      close();
    });
    panel.append(text, yes, no);
    row.actions.hidden = true;
    row.el.classList.add('confirming');
    row.el.append(panel);
    const close = (): void => {
      panel.remove();
      row.actions.hidden = false;
      row.el.classList.remove('confirming');
      closeConfirm = null;
    };
    closeConfirm = close;
  };

  const doSave = async (row: Row): Promise<void> => {
    if (!api) {
      return;
    }
    status.textContent = `Saving slot ${row.index}…`;
    const result = await api.saveToSlot(row.slot);
    status.textContent = result.message;
    await refresh();
  };

  const doDelete = async (row: Row): Promise<void> => {
    if (!api) {
      return;
    }
    const result = await api.deleteSlot(row.slot);
    status.textContent = result.status === 'ok' ? `Slot ${row.index} deleted.` : result.message;
    await refresh();
  };

  for (let index = 1; index <= SLOTS; index += 1) {
    const slot = `manual-${index}`;
    const el = document.createElement('div');
    el.className = 'save-row';
    el.dataset.slot = slot;
    const label = document.createElement('strong');
    label.className = 'save-label';
    label.textContent = `Slot ${index}`;
    const info = document.createElement('span');
    info.className = 'save-info';
    const title = document.createElement('span');
    title.className = 'save-title';
    title.textContent = 'Loading…';
    const detail = document.createElement('span');
    detail.className = 'save-detail';
    info.append(title, detail);
    const actions = document.createElement('div');
    actions.className = 'save-actions';

    const row: Row = {
      index,
      slot,
      el,
      title,
      detail,
      actions,
      save: null,
      load: button('saveSlots', `load${index}`, 'Load', () => {
        if (unavailable()) {
          return;
        }
        void (async () => {
          status.textContent = `Loading slot ${index}…`;
          const result = await api?.loadFromSlot(slot);
          if (result) {
            status.textContent = result.message;
          }
        })();
      }),
      remove: button('saveSlots', `delete${index}`, 'Delete', () => {
        if (unavailable()) {
          return;
        }
        ask(row, `Delete slot ${index}?`, 'confirmDelete', 'Delete', () => {
          void doDelete(row);
        });
      }),
      summary: null,
    };
    row.remove.setAttribute('aria-label', `Delete slot ${index}`);
    row.load.setAttribute('aria-label', `Load slot ${index}`);
    if (inMatch) {
      const save = button('saveSlots', `save${index}`, 'Save', () => {
        if (unavailable()) {
          return;
        }
        // Writing over a saved game asks first; an empty slot saves straight away.
        if (row.summary && row.summary.status !== 'missing') {
          ask(row, `Overwrite slot ${index}?`, 'confirmOverwrite', 'Overwrite', () => {
            void doSave(row);
          });
          return;
        }
        void doSave(row);
      });
      save.setAttribute('aria-label', `Save to slot ${index}`);
      row.save = save;
      actions.append(save);
    }
    actions.append(row.load, row.remove);
    for (const node of [row.save, row.load, row.remove]) {
      if (node) {
        node.disabled = !api;
      }
    }
    el.append(label, info, actions);
    list.append(el);
    rows.push(row);
  }

  async function refresh(): Promise<void> {
    if (!api) {
      for (const row of rows) {
        row.title.textContent = 'Unavailable';
      }
      return;
    }
    const summaries = await api.listSaveSlots();
    const bySlot = new Map(summaries.map((summary) => [summary.slot, summary]));
    for (const row of rows) {
      const summary = bySlot.get(row.slot) ?? null;
      row.summary = summary;
      const empty = !summary || summary.status === 'missing';
      row.el.dataset.empty = empty ? 'true' : 'false';
      if (empty) {
        row.title.textContent = 'Empty';
        row.detail.textContent = '';
      } else if (summary.status === 'ok') {
        row.title.textContent = summary.title ?? 'Saved game';
        row.detail.textContent = [formatPlayed(summary.playSeconds), formatDate(summary.savedAtIso)]
          .filter(Boolean)
          .join(' · ');
      } else {
        row.title.textContent = summary.status === 'corrupt' ? 'Corrupt save' : 'Incompatible save';
        row.detail.textContent = '';
      }
      row.load.disabled = empty;
      row.remove.disabled = empty;
    }
  }

  void refresh();
  const back = button('saveSlots', 'back', 'Back', () => {
    ctx.router.back();
  });
  root.append(back);

  return () => {
    closeConfirm = null;
  };
}
