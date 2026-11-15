import type { ScreenContext } from './router';
import { button } from './controls';

function formatDate(iso: string | null): string {
  if (!iso) {
    return 'Empty';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return 'Saved';
  }
  return `Saved ${date.toLocaleString()}`;
}

export function mountSaveSlots(root: HTMLElement, ctx: ScreenContext): () => void {
  const api = ctx.api;
  const status = document.createElement('p');
  status.className = 'save-status';
  status.dataset.saveStatus = 'true';
  status.textContent = 'Choose a slot.';
  const list = document.createElement('div');
  list.className = 'save-list';
  root.append(status, list);

  interface Row {
    slot: string;
    info: HTMLSpanElement;
    save: HTMLButtonElement;
    load: HTMLButtonElement;
  }
  const rows: Row[] = [];

  for (let index = 1; index <= 5; index += 1) {
    const slot = `manual-${index}`;
    const row = document.createElement('div');
    row.className = 'save-row';
    const label = document.createElement('strong');
    label.textContent = `Slot ${index}`;
    const info = document.createElement('span');
    info.className = 'save-info';
    info.textContent = 'Loading…';
    const save = button('saveSlots', `save${index}`, 'Save', () => {
      void (async () => {
        if (!api) {
          status.textContent = 'Saves are unavailable in this environment.';
          return;
        }
        status.textContent = `Saving slot ${index}…`;
        const result = await api.saveToSlot(slot);
        status.textContent = result.message;
        await refresh();
      })();
    });
    const load = button('saveSlots', `load${index}`, 'Load', () => {
      void (async () => {
        if (!api) {
          status.textContent = 'Saves are unavailable in this environment.';
          return;
        }
        status.textContent = `Loading slot ${index}…`;
        const result = await api.loadFromSlot(slot);
        status.textContent = result.message;
      })();
    });
    save.disabled = !api;
    load.disabled = !api;
    row.append(label, info, save, load);
    list.append(row);
    rows.push({ slot, info, save, load });
  }

  async function refresh(): Promise<void> {
    if (!api) {
      return;
    }
    const summaries = await api.listSaveSlots();
    const bySlot = new Map(summaries.map((summary) => [summary.slot, summary]));
    for (const row of rows) {
      const summary = bySlot.get(row.slot);
      if (!summary || summary.status === 'missing') {
        row.info.textContent = 'Empty';
      } else if (summary.status === 'ok') {
        row.info.textContent = formatDate(summary.savedAtIso);
      } else if (summary.status === 'corrupt') {
        row.info.textContent = 'Corrupt save';
      } else {
        row.info.textContent = 'Incompatible save';
      }
      row.load.disabled = !summary || summary.status === 'missing';
    }
  }

  void refresh();
  const back = button('saveSlots', 'back', 'Back', () => {
    ctx.router.back();
  });
  root.append(back);

  return () => {
    // Screen cleanup removes the DOM.
  };
}
