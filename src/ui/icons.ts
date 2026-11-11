/**
 * Line icons for the menus and HUD (UI redesign v1).
 *
 * One SVG sprite holds every icon as a <symbol>; `icon(name)` returns an <svg>
 * that references it. Swapping in faction-styled icons later only means
 * replacing the paths in ICON_PATHS.
 */
const SVG_NS = 'http://www.w3.org/2000/svg';

export const ICON_PATHS = {
  attack: '<path d="M4 20 L14 10"/><path d="M11 6 L18 6 L18 13"/><path d="M14 10 L18 6"/><path d="M3 15 l3 3"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>',
  hold: '<path d="M12 3 L19 6 V12 C19 16 16 19 12 21 C8 19 5 16 5 12 V6 Z"/>',
  way: '<circle cx="5" cy="18" r="2"/><circle cx="12" cy="8" r="2"/><circle cx="19" cy="16" r="2"/><path d="M6.5 16.5 L10.5 9.5 M13.5 9.5 L17.5 14.5" stroke-dasharray="2 2"/>',
  group: '<rect x="3" y="4" width="8" height="7" rx="1.5"/><rect x="13" y="4" width="8" height="7" rx="1.5"/><rect x="3" y="13" width="8" height="7" rx="1.5"/><path d="M17 14 v6 M14 17 h6"/>',
  mine: '<path d="M4 20 L13 11"/><path d="M9 5 C13 3 18 5 20 9 C17 8 14 8 12 9"/><path d="M9 5 L15 11"/>',
  haul: '<path d="M2 16 h12 V7 H2 Z"/><path d="M14 10 h4 l3 3 v3 h-7"/><circle cx="6" cy="18" r="1.8"/><circle cx="17" cy="18" r="1.8"/>',
  salvage: '<path d="M14 4 a5 5 0 0 0 -4 7 L4 17 l3 3 6-6 a5 5 0 0 0 7-4 l-3 1-2-2 1-3 Z"/>',
  air: '<path d="M12 3 L14 10 L21 13 L14 14 L12 21 L10 14 L3 13 L10 10 Z"/>',
  build: '<path d="M12 2 V14"/><path d="M7 9 L12 14 L17 9"/><path d="M4 18 h16 M6 22 h12"/>',
  base: '<path d="M9 3 h6 M10 3 v6 L5 19 a1.5 1.5 0 0 0 1.4 2 H17.6 a1.5 1.5 0 0 0 1.4-2 L14 9 V3"/><path d="M7.5 14 h9"/>',
  pause: '<path d="M8 5 v14 M16 5 v14" stroke-width="3"/>',
  bell: '<path d="M6 16 V11 a6 6 0 0 1 12 0 V16 L20 18 H4 Z"/><path d="M10 21 h4"/>',
  x: '<path d="M6 6 L18 18 M18 6 L6 18"/>',
  play: '<path d="M7 4 L19 12 L7 20 Z"/>',
  flag: '<path d="M5 21 V4 M5 4 h12 l-3 4 3 4 H5"/>',
  swords: '<path d="M4 4 L14 14 M14 14 l-2 4 M14 14 l4 -2 M20 4 L10 14 M10 14 l2 4 M10 14 l-4-2 M3 21 l3-3 M21 21 l-3-3"/>',
  gear: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2 v3 M12 19 v3 M2 12 h3 M19 12 h3 M4.9 4.9 l2.1 2.1 M17 17 l2.1 2.1 M4.9 19.1 L7 17 M17 7 l2.1-2.1"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5 a2.5 2.5 0 1 1 3.5 2.3 c-.7.3-1 1-1 1.7 V14"/><path d="M12 17.5 v.1"/>',
  star: '<path d="M12 3 l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7Z"/>',
  left: '<path d="M15 5 L8 12 L15 19"/>',
  right: '<path d="M9 5 L16 12 L9 19"/>',
  down: '<path d="M6 9 L12 15 L18 9"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11 V8 a4 4 0 0 1 8 0 v3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7 v5 l3 2"/>',
  unit: '<rect x="4" y="11" width="16" height="7" rx="2"/><rect x="8" y="7" width="7" height="4" rx="1"/><path d="M15 9 h6"/>',
  worker: '<path d="M4 18 h16 l-2-6 H9 l-2 3 H4 Z"/><circle cx="8" cy="19" r="1.6"/><circle cx="16" cy="19" r="1.6"/><path d="M11 12 l2-5 h4"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2 v4 M12 18 v4 M2 12 h4 M18 12 h4"/>',
  bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M9 8 a3 3 0 0 1 6 0 M3 13 h4 M17 13 h4 M4 19 l3-2 M20 19 l-3-2 M4 7 l3 2 M20 7 l-3 2"/>',
  save: '<path d="M5 4 h11 l3 3 v13 H5 Z"/><path d="M8 4 v5 h7 V4 M8 20 v-6 h8 v6"/>',
  list: '<path d="M9 6 h11 M9 12 h11 M9 18 h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
  speed: '<path d="M4 6 L11 12 L4 18 Z"/><path d="M12 6 L19 12 L12 18 Z"/>',
} as const;

export type IconName = keyof typeof ICON_PATHS;

const SPRITE_ID = 'tc-icon-sprite';

/** Adds the sprite to the document once. Safe to call repeatedly. */
export function ensureIconSprite(doc: Document = document): void {
  if (doc.getElementById(SPRITE_ID)) {
    return;
  }
  const sprite = doc.createElementNS(SVG_NS, 'svg');
  sprite.id = SPRITE_ID;
  sprite.setAttribute('width', '0');
  sprite.setAttribute('height', '0');
  sprite.setAttribute('aria-hidden', 'true');
  sprite.style.position = 'absolute';
  sprite.innerHTML = `<defs>${Object.entries(ICON_PATHS)
    .map(([name, body]) => `<symbol id="i-${name}" viewBox="0 0 24 24">${body}</symbol>`)
    .join('')}</defs>`;
  doc.body.append(sprite);
}

/** An inline icon. Size and colour come from CSS (`.ico`, `currentColor`). */
export function icon(name: IconName, className = ''): SVGSVGElement {
  ensureIconSprite();
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', `ico${className ? ` ${className}` : ''}`);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

/** Filled resource glyphs: pink ore gem and grey metal ingot. */
export function resourceIcon(kind: 'ore' | 'metal', size = 16): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'res-ico');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML =
    kind === 'ore'
      ? '<path d="M8 1 L14 6 L8 15 L2 6 Z" fill="#ff5fc8"/><path d="M2 6 H14 M8 1 L6 6 L8 15 L10 6 Z" fill="none" stroke="#ffc2ec" stroke-width=".6" opacity=".7"/>'
      : '<rect x="2" y="4" width="12" height="8" rx="1" fill="#b8c7d9"/><path d="M2 7 h12" stroke="#6b7c90"/>';
  return svg;
}
