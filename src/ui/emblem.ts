// The game's emblem: one shield, two halves. The left half is Terran (hard chevrons, blue), the
// right half is Arcadian (a crescent around a core, gold). Drawn as inline SVG so it stays sharp
// at any size and costs nothing to download.
const SVG_NS = 'http://www.w3.org/2000/svg';

const EMBLEM_BODY = `
<defs>
  <linearGradient id="emblem-metal" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#f4f8fc"/><stop offset="0.5" stop-color="#8794a6"/><stop offset="1" stop-color="#dfe7f0"/>
  </linearGradient>
  <linearGradient id="emblem-terran" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#b6f2ff"/><stop offset="1" stop-color="#1a95c0"/>
  </linearGradient>
  <linearGradient id="emblem-arcadian" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffe9a8"/><stop offset="1" stop-color="#d98a1c"/>
  </linearGradient>
</defs>
<path class="emblem-plate" d="M32 3 L57 15 V39 L32 61 L7 39 V15 Z" fill="rgba(6,11,20,0.72)"/>
<path class="emblem-edge" d="M32 3 L57 15 V39 L32 61 L7 39 V15 Z" fill="none" stroke="url(#emblem-metal)" stroke-width="2.4" stroke-linejoin="miter" pathLength="1"/>
<path class="emblem-split" d="M32 9 V55" stroke="url(#emblem-metal)" stroke-width="1.2" opacity="0.55"/>
<g class="emblem-terran" fill="url(#emblem-terran)">
  <path d="M13 29 L28 15 V24 L13 38 Z"/>
  <path d="M13 43 L28 29 V38 L18.5 46.9 Z"/>
  <path d="M22 50 L28 44.4 V55.3 Z"/>
</g>
<g class="emblem-arcadian" fill="url(#emblem-arcadian)">
  <path d="M36 15 C50 19 53 36 36 54 C45 40 45 28 36 15 Z"/>
  <circle cx="39.5" cy="33" r="3.1"/>
</g>`;

/** The emblem as an inline SVG element (decorative: hidden from screen readers). */
export function emblem(className = 'emblem'): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 64 64');
  svg.setAttribute('class', className);
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = EMBLEM_BODY;
  return svg;
}
