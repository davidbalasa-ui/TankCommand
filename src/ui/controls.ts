const registered = new Set<string>();

export const ControlInventory = {
  all(): string[] {
    return [...registered].sort();
  },
  clear(): void {
    registered.clear();
  },
};

export function button(
  screenId: string,
  name: string,
  label: string,
  onClick: () => void,
): HTMLButtonElement {
  const id = `${screenId}.${name}`;
  registered.add(id);
  const element = document.createElement('button');
  element.type = 'button';
  element.textContent = label;
  element.dataset.controlId = id;
  element.addEventListener('click', () => {
    onClick();
  });
  return element;
}
