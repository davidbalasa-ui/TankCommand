// Optional on-screen frame rate readout (Settings > Show FPS), for checking speed on a real phone.
// Shows the average fps and the slowest frame over the last half second, plus a detail line.

const REFRESH_MS = 500;

export class FpsMeter {
  private element: HTMLDivElement | null = null;
  private enabled = false;
  private frames = 0;
  private worstMs = 0;
  private windowStart = 0;
  private last = 0;

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.element?.remove();
      this.element = null;
    }
  }

  /** Call once per rendered frame. `detail` is only evaluated when the readout refreshes. */
  frame(now: number, detail: () => string): void {
    if (!this.enabled) {
      return;
    }
    if (this.last > 0) {
      this.worstMs = Math.max(this.worstMs, now - this.last);
    }
    this.last = now;
    this.frames += 1;
    if (this.windowStart === 0) {
      this.windowStart = now;
      return;
    }
    const span = now - this.windowStart;
    if (span < REFRESH_MS) {
      return;
    }
    const fps = (this.frames * 1000) / span;
    const element = this.ensureElement();
    element.textContent = `${fps.toFixed(0)} fps (slowest ${this.worstMs.toFixed(0)} ms)\n${detail()}`;
    this.frames = 0;
    this.worstMs = 0;
    this.windowStart = now;
  }

  private ensureElement(): HTMLDivElement {
    if (!this.element) {
      const element = document.createElement('div');
      element.className = 'fps-meter';
      element.dataset.testid = 'fps-meter';
      element.setAttribute('aria-hidden', 'true');
      document.body.append(element);
      this.element = element;
    }
    return this.element;
  }
}
