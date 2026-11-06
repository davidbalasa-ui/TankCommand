import { generateMap, heightAt, isWaterAt } from '../sim/map';
import type { BriefingView } from './router';

export function drawMapPreview(canvas: HTMLCanvasElement, view: BriefingView['map']): void {
  const size = 128;
  canvas.width = size;
  canvas.height = size;
  const g = canvas.getContext('2d');
  if (!g) {
    return;
  }
  const map = generateMap(view.seed, view.size, view.cellSize, view.features ?? undefined);
  const image = g.createImageData(size, size);
  const half = map.size / 2;
  for (let py = 0; py < size; py += 1) {
    for (let px = 0; px < size; px += 1) {
      const x = -half + ((px + 0.5) / size) * map.size;
      const z = -half + ((py + 0.5) / size) * map.size;
      const index = (py * size + px) * 4;
      if (isWaterAt(map, x, z)) {
        image.data.set([47, 111, 159, 255], index);
        continue;
      }
      const h = Math.max(-1, Math.min(10, heightAt(map, x, z)));
      const t = (h + 1) / 11;
      image.data.set([Math.round(70 + t * 150), Math.round(100 + t * 100), Math.round(55 + t * 120), 255], index);
    }
  }
  g.putImageData(image, 0, 0);
  const toPx = (v: number): number => ((v + half) / map.size) * size;
  for (const deposit of view.deposits) {
    g.fillStyle = deposit.kind === 'metal' ? '#c8d0d8' : '#e0a030';
    g.fillRect(toPx(deposit.x) - 1, toPx(deposit.z) - 1, 3, 3);
  }
  for (const start of view.starts) {
    g.fillStyle = start.player === 1 ? '#4da3ff' : '#ff5d5d';
    g.beginPath();
    g.arc(toPx(start.x), toPx(start.z), 4, 0, Math.PI * 2);
    g.fill();
  }
}
