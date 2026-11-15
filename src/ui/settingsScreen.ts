import type { ScreenContext } from './router';
import { button } from './controls';
import { DEFAULT_SETTINGS, type SettingsState } from '../platform/settings';

function downloadText(fileName: string, text: string): void {
  const blob = new Blob([text], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}

/**
 * Settings is laid out for a 915x412 landscape phone: five sliders in a left
 * column and the toggles in a two-column grid on the right, with the action row
 * (export/import/rebind/back) underneath. As a single column the screen is over
 * 900 px tall, and because `touch-action: none` is set on <html> for TCH-04 the
 * player cannot scroll a touch screen to reach a control below the fold.
 */
export function mountSettings(root: HTMLElement, ctx: ScreenContext): () => void {
  const api = ctx.api;
  const form = document.createElement('div');
  form.className = 'settings-form';
  const status = document.createElement('p');
  status.className = 'settings-status';
  status.dataset.settingsStatus = 'true';

  const grid = document.createElement('div');
  grid.className = 'settings-grid';
  const sliders = document.createElement('div');
  sliders.className = 'settings-sliders';
  const toggles = document.createElement('div');
  toggles.className = 'settings-toggles';
  const actions = document.createElement('div');
  actions.className = 'settings-actions';
  grid.append(sliders, toggles);
  form.append(status, grid, actions);
  root.append(form);

  const current = (): Readonly<SettingsState> => api?.settings() ?? DEFAULT_SETTINGS;

  const addRange = (
    key: 'masterVolume' | 'musicVolume' | 'effectsVolume' | 'edgeScrollSpeed' | 'cameraSensitivity',
    label: string,
    min: number,
    max: number,
    step: number,
    format: (value: number) => string,
  ): void => {
    const row = document.createElement('label');
    row.className = 'setting-row';
    const text = document.createElement('span');
    const value = document.createElement('span');
    value.className = 'setting-value';
    const input = document.createElement('input');
    input.type = 'range';
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(current()[key]);
    input.dataset.setting = key;
    text.textContent = label;
    value.textContent = format(current()[key]);
    input.addEventListener('input', () => {
      const next = Number(input.value);
      api?.setSetting(key, next);
      value.textContent = format(next);
    });
    row.append(text, input, value);
    sliders.append(row);
  };

  addRange('masterVolume', 'Master volume', 0, 1, 0.05, (v) => `${Math.round(v * 100)}%`);
  addRange('musicVolume', 'Music volume', 0, 1, 0.05, (v) => `${Math.round(v * 100)}%`);
  addRange('effectsVolume', 'Effects volume', 0, 1, 0.05, (v) => `${Math.round(v * 100)}%`);
  addRange('edgeScrollSpeed', 'Edge-scroll speed', 0.2, 3, 0.1, (v) => `${v.toFixed(1)}×`);
  addRange('cameraSensitivity', 'Sensitivity', 0.2, 3, 0.1, (v) => `${v.toFixed(1)}×`);

  const quality = button('settings', 'graphicsQuality', 'Graphics: auto', () => {
    const order: SettingsState['graphicsQuality'][] = ['auto', 'low', 'medium', 'high'];
    const index = order.indexOf(current().graphicsQuality);
    const next = order[(index + 1) % order.length] ?? 'auto';
    api?.setSetting('graphicsQuality', next);
    refreshLabels();
  });
  const health = button('settings', 'healthBars', 'Health bars: damaged', () => {
    const next = current().healthBars === 'damaged' ? 'always' : 'damaged';
    api?.setSetting('healthBars', next);
    refreshLabels();
  });
  const edgeScroll = button('settings', 'edgeScroll', 'Edge scroll: on', () => {
    api?.setSetting('edgeScroll', !current().edgeScroll);
    refreshLabels();
  });
  const textSize = button('settings', 'textSize', 'Text size: normal', () => {
    const next = current().textSize === 'normal' ? 'large' : 'normal';
    api?.setSetting('textSize', next);
    refreshLabels();
  });
  const colourBlind = button('settings', 'colourBlind', 'Colour-blind: off', () => {
    api?.setSetting('colourBlind', !current().colourBlind);
    refreshLabels();
  });
  const haptics = button('settings', 'haptics', 'Haptics: on', () => {
    api?.setSetting('haptics', !current().haptics);
    refreshLabels();
  });
  const leftHanded = button('settings', 'leftHanded', 'Layout: right', () => {
    api?.setSetting('leftHanded', !current().leftHanded);
    refreshLabels();
  });
  const fog = button('settings', 'fog', 'Fog of war: on', () => {
    ctx.setFogOn?.(!(ctx.isFogOn?.() ?? true));
    refreshLabels();
  });
  const fps = button('settings', 'showFps', 'Show FPS: off', () => {
    api?.setSetting('showFps', !current().showFps);
    refreshLabels();
  });
  toggles.append(quality, health, edgeScroll, textSize, colourBlind, haptics, leftHanded, fog, fps);

  let listeningFor: 'move' | null = null;
  const rebind = button('settings', 'rebind', 'Rebind keys', () => {
    listeningFor = 'move';
    rebind.textContent = 'Press a key…';
  });
  const keyHandler = (event: KeyboardEvent): void => {
    if (!listeningFor) {
      return;
    }
    event.preventDefault();
    api?.setSetting('keyBindings', {
      ...current().keyBindings,
      [listeningFor]: event.key,
    });
    listeningFor = null;
    refreshLabels();
  };
  window.addEventListener('keydown', keyHandler);

  const exportButton = button('settings', 'export', 'Export save', () => {
    void (async () => {
      if (!api) {
        status.textContent = 'Saves are unavailable in this environment.';
        return;
      }
      const text = await api.exportSave();
      downloadText('tankcommand-save.json', text);
      status.textContent = 'Save exported.';
    })();
  });

  // A 1x1 transparent input, not `display:none`: Chromium will not open a file
  // chooser from a display-none input on every platform, and the import test
  // drives the real chooser event.
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = 'application/json,.json';
  fileInput.className = 'hidden-file-input';
  fileInput.dataset.control = 'settings.importFile';
  const importButton = button('settings', 'import', 'Import save', () => {
    fileInput.click();
  });
  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file || !api) {
      return;
    }
    void file.text().then(async (text) => {
      const result = await api.importSave(text);
      status.textContent = result.message;
    });
  });

  const back = button('settings', 'back', 'Back', () => {
    ctx.router.back();
  });

  actions.append(rebind, exportButton, importButton, back, fileInput);

  function refreshLabels(): void {
    const values = current();
    quality.textContent = `Graphics: ${values.graphicsQuality}`;
    health.textContent = `Health bars: ${values.healthBars}`;
    edgeScroll.textContent = `Edge scroll: ${values.edgeScroll ? 'on' : 'off'}`;
    fps.textContent = `Show FPS: ${values.showFps ? 'on' : 'off'}`;
    textSize.textContent = `Text size: ${values.textSize}`;
    colourBlind.textContent = `Colour-blind: ${values.colourBlind ? 'on' : 'off'}`;
    haptics.textContent = `Haptics: ${values.haptics ? 'on' : 'off'}`;
    leftHanded.textContent = `Layout: ${values.leftHanded ? 'left' : 'right'}`;
    fog.textContent = `Fog of war: ${ctx.isFogOn?.() === false ? 'revealed' : 'on'}`;
    const move = values.keyBindings['move'];
    rebind.textContent = move ? `Rebind keys (${move})` : 'Rebind keys';
  }
  refreshLabels();

  return () => {
    window.removeEventListener('keydown', keyHandler);
  };
}
