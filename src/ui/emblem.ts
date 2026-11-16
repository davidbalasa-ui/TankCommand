// The game's emblem: a cut-corner shield holding a turret and barrel above two command chevrons.
// Drawn as strokes, so the opening can trace it in line by line. The same markup is inlined in
// index.html for the loading splash; keep the two in step.

const NS = 'http://www.w3.org/2000/svg';

/** Each stroke of the emblem, in the order the opening traces them. */
export const EMBLEM_PATHS: readonly { d: string; part: string }[] = [
  { d: 'M32 3 L58 14 L58 38 L32 61 L6 38 L6 14 Z', part: 'shield' },
  { d: 'M32 9 L52 17.5 L52 35.5 L32 53.5 L12 35.5 L12 17.5 Z', part: 'inner' },
  { d: 'M32 22 L32 11', part: 'barrel' },
  { d: 'M37 25 A5 5 0 1 1 27 25 A5 5 0 1 1 37 25 Z', part: 'turret' },
  { d: 'M19 38 L32 31 L45 38', part: 'chevron' },
  { d: 'M19 46 L32 39 L45 46', part: 'chevron' },
];

export function emblem(className = 'emblem'): SVGSVGElement {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 64 64');
  svg.setAttribute('class', className);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('fill', 'none');
  EMBLEM_PATHS.forEach((item, index) => {
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', item.d);
    path.setAttribute('class', `emblem-${item.part}`);
    path.setAttribute('pathLength', '1');
    path.style.setProperty('--i', String(index));
    svg.append(path);
  });
  return svg;
}
