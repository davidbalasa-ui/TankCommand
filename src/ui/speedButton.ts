import type { GameApi } from '../game/api';
import { button } from './controls';

function formatSpeed(multiplier: number): string {
  return multiplier % 1 === 0 ? multiplier.toFixed(0) : multiplier.toFixed(1);
}

export function mountSpeedButton(host: HTMLElement, api?: GameApi): () => void {
  let element: HTMLButtonElement | null = null;
  const update = (): void => {
    if (!element) {
      return;
    }
    const multiplier = api?.simSpeed() ?? 1;
    element.textContent = `Speed ${formatSpeed(multiplier)}×`;
  };

  element = button('inGame', 'speed', 'Speed 1×', () => {
    if (!api) {
      return;
    }
    api.cycleSpeed();
    update();
  });
  element.className = 'hud-speed-button';
  host.append(element);
  update();

  return () => {
    element?.remove();
  };
}
