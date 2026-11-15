/**
 * Shared building blocks for the redesigned menus (UI redesign v1): rich menu
 * buttons, small captioned icon buttons and segmented pickers. Every button is
 * still made by `button()` so it keeps its data-control-id and inventory entry,
 * and carries an aria-label so tests and screen readers see one plain name.
 */
import { button, registerControl } from './controls';
import { icon, type IconName } from './icons';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/** Large title-menu button: icon, uppercase title, subtitle, chevron. */
export function menuButton(
  screenId: string,
  name: string,
  title: string,
  subtitle: string,
  iconName: IconName,
  onClick: () => void,
  primary = false,
): HTMLButtonElement {
  const node = button(screenId, name, title, onClick);
  node.classList.add('menu-button');
  if (primary) {
    node.classList.add('primary');
  }
  node.setAttribute('aria-label', title);
  const text = el('span', 'menu-button-text');
  const sub = el('span', 'menu-button-sub', subtitle);
  text.append(el('span', 'menu-button-title', title), sub);
  node.replaceChildren(icon(iconName), text, icon('right', 'chev'));
  return node;
}

export function setMenuButtonSubtitle(node: HTMLButtonElement, subtitle: string): void {
  const sub = node.querySelector('.menu-button-sub');
  if (sub) {
    sub.textContent = subtitle;
  }
}

/** Square icon button with a caption underneath (title screen small row, HUD commands). */
export function iconButton(
  screenId: string,
  name: string,
  label: string,
  iconName: IconName,
  onClick: () => void,
  caption: string | null = label,
): HTMLButtonElement {
  const node = button(screenId, name, label, onClick);
  node.classList.add('icon-button');
  node.setAttribute('aria-label', label);
  node.replaceChildren(icon(iconName));
  if (caption) {
    node.append(el('span', 'icon-caption', caption));
  }
  return node;
}

export interface SegmentOption<T> {
  value: T;
  label: string;
  /** Optional colour dot before the label (faction colour). */
  dot?: string;
}

/**
 * One option row: label column + segmented control showing every value. The
 * row keeps the old cycling button's control id on its group element; each
 * segment gets `${name}.${value}`.
 */
export function segmentRow<T extends string | number | boolean>(
  screenId: string,
  name: string,
  label: string,
  options: ReadonlyArray<SegmentOption<T>>,
  current: T,
  onPick: (value: T) => void,
): HTMLDivElement {
  const row = el('div', 'option-row');
  const key = el('span', 'option-label', label);
  const group = el('div', 'segmented');
  group.setAttribute('role', 'radiogroup');
  group.setAttribute('aria-label', label);
  const groupId = `${screenId}.${name}`;
  registerControl(groupId);
  group.dataset.controlId = groupId;
  for (const option of options) {
    const segment = button(screenId, `${name}.${String(option.value)}`, option.label, () => {
      onPick(option.value);
    });
    segment.setAttribute('role', 'radio');
    segment.setAttribute('aria-checked', option.value === current ? 'true' : 'false');
    segment.setAttribute('aria-label', `${label}: ${option.label}`);
    segment.classList.toggle('on', option.value === current);
    if (option.dot) {
      const dot = el('span', 'dot');
      dot.style.background = option.dot;
      segment.prepend(dot);
    }
    group.append(segment);
  }
  row.append(key, group);
  return row;
}

/**
 * Tap fall-through guard for panels that open from a tap on the map. The tap that opens the panel
 * ends with a click the browser can deliver to whatever button now sits under the finger. Only a
 * click whose press began inside the panel while it was already open counts. Keyboard and
 * scripted clicks (detail 0) have no press and always pass.
 */
export function guardOpeningTap(element: HTMLElement, isOpen: () => boolean): void {
  let pressStartedInside = false;
  element.addEventListener(
    'pointerdown',
    () => {
      pressStartedInside = isOpen();
    },
    true,
  );
  element.addEventListener(
    'click',
    (event) => {
      if (event.detail > 0 && !pressStartedInside) {
        event.stopPropagation();
        event.preventDefault();
      }
      pressStartedInside = false;
    },
    true,
  );
}
