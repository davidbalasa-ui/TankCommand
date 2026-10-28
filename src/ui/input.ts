import type { RenderView } from '../render/renderer';
import type { WorldState } from '../sim/types';
import { CAMERA_EDGE_BAND } from '../sim/tuning';

const BOX_DRAG_THRESHOLD = 6;
const LONG_PRESS_MS = 400;

export interface InputHost {
  canvas: HTMLCanvasElement;
  renderView: RenderView;
  getWorld: () => WorldState;
  getSelection: () => number[];
  setSelection: (ids: number[]) => void;
  sendCommand: (command: unknown) => boolean;
}

interface PointerInfo {
  id: number;
  type: string;
  button: number;
  startX: number;
  startY: number;
  lastX: number;
  lastY: number;
  startTime: number;
  downUnit: number | null;
  downGround: { x: number; z: number } | null;
}

function angleDiff(a: number, b: number): number {
  let diff = a - b;
  while (diff > Math.PI) {
    diff -= Math.PI * 2;
  }
  while (diff < -Math.PI) {
    diff += Math.PI * 2;
  }
  return diff;
}

export class InputController {
  private readonly host: InputHost;
  private readonly selectionBox: HTMLDivElement;
  private readonly pointers = new Map<number, PointerInfo>();
  private readonly keys = new Set<string>();
  private readonly groups = new Map<number, number[]>();
  private edgeScrollEnabled = true;
  private lastMouse: { x: number; y: number } | null = null;
  private boxStart: { x: number; y: number } | null = null;
  private boxSelecting = false;
  private panPointerId: number | null = null;
  private panGrab: { x: number; z: number } | null = null;
  private longPressTimer: number | null = null;
  private longPressReady = false;
  private pinch: { distance: number; angle: number } | null = null;
  private twoFingerCandidate = false;
  private twoFingerStart = 0;
  private twoFingerMoved = 0;
  private lastGroundPick: { x: number; z: number } | null = null;
  private disposed = false;

  constructor(host: InputHost) {
    this.host = host;
    this.selectionBox = document.createElement('div');
    this.selectionBox.className = 'selection-box';
    document.body.append(this.selectionBox);

    const canvas = host.canvas;
    canvas.addEventListener('pointerdown', this.onPointerDown);
    canvas.addEventListener('pointermove', this.onPointerMove);
    canvas.addEventListener('pointerup', this.onPointerUp);
    canvas.addEventListener('pointercancel', this.onPointerUp);
    canvas.addEventListener('contextmenu', this.onContextMenu);
    canvas.addEventListener('wheel', this.onWheel, { passive: false });
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
  }

  setEdgeScroll(enabled: boolean): void {
    this.edgeScrollEnabled = enabled;
  }

  /**
   * The ground point this controller resolved for the most recent click or tap,
   * or null before the first one. Read-only observability for acceptance tests:
   * it reports what picking produced, independently of whether that landing spot
   * turned out to be a reachable destination.
   */
  getLastGroundPick(): { x: number; z: number } | null {
    return this.lastGroundPick ? { ...this.lastGroundPick } : null;
  }

  update(elapsedMs: number): void {
    if (this.disposed) {
      return;
    }
    const seconds = Math.max(0, elapsedMs) / 1000;
    if (seconds <= 0) {
      return;
    }
    const camera = this.host.renderView.getCamera();
    const forward = { x: Math.sin(camera.yaw), z: Math.cos(camera.yaw) };
    const right = { x: Math.cos(camera.yaw), z: -Math.sin(camera.yaw) };
    let mx = 0;
    let mz = 0;

    if (this.keys.has('w') || this.keys.has('arrowup')) {
      mx += forward.x;
      mz += forward.z;
    }
    if (this.keys.has('arrowdown')) {
      mx -= forward.x;
      mz -= forward.z;
    }
    if (this.keys.has('a') || this.keys.has('arrowleft')) {
      mx -= right.x;
      mz -= right.z;
    }
    if (this.keys.has('d') || this.keys.has('arrowright')) {
      mx += right.x;
      mz += right.z;
    }

    if (this.edgeScrollEnabled && this.lastMouse) {
      const rect = this.host.canvas.getBoundingClientRect();
      const inCanvas =
        this.lastMouse.x >= rect.left &&
        this.lastMouse.x <= rect.right &&
        this.lastMouse.y >= rect.top &&
        this.lastMouse.y <= rect.bottom;
      if (inCanvas) {
        if (this.lastMouse.x - rect.left <= CAMERA_EDGE_BAND) {
          mx -= right.x;
          mz -= right.z;
        }
        if (rect.right - this.lastMouse.x <= CAMERA_EDGE_BAND) {
          mx += right.x;
          mz += right.z;
        }
        if (this.lastMouse.y - rect.top <= CAMERA_EDGE_BAND) {
          mx += forward.x;
          mz += forward.z;
        }
        if (rect.bottom - this.lastMouse.y <= CAMERA_EDGE_BAND) {
          mx -= forward.x;
          mz -= forward.z;
        }
      }
    }

    if (mx !== 0 || mz !== 0) {
      const speed = camera.distance * 0.9 * seconds;
      camera.pan(mx * speed, mz * speed);
    }

    if (this.keys.has('q')) {
      camera.rotate(1.2 * seconds);
    }
    if (this.keys.has('e')) {
      camera.rotate(-1.2 * seconds);
    }

    camera.clampTarget();
    this.host.renderView.applyCamera();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.clearLongPress();
    const canvas = this.host.canvas;
    canvas.removeEventListener('pointerdown', this.onPointerDown);
    canvas.removeEventListener('pointermove', this.onPointerMove);
    canvas.removeEventListener('pointerup', this.onPointerUp);
    canvas.removeEventListener('pointercancel', this.onPointerUp);
    canvas.removeEventListener('contextmenu', this.onContextMenu);
    canvas.removeEventListener('wheel', this.onWheel);
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    this.selectionBox.remove();
  }

  private readonly onContextMenu = (event: Event): void => {
    event.preventDefault();
  };

  private readonly onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    const view = this.host.renderView;
    const before = view.pickGround(event.clientX, event.clientY);
    const camera = view.getCamera();
    camera.zoomBy(Math.exp(event.deltaY * 0.001));
    view.applyCamera();
    const after = view.pickGround(event.clientX, event.clientY);
    if (before && after) {
      camera.pan(before.x - after.x, before.z - after.z);
    }
    camera.clampTarget();
    view.applyCamera();
  };

  private readonly onPointerDown = (event: PointerEvent): void => {
    event.preventDefault();
    const canvas = this.host.canvas;
    try {
      canvas.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort.
    }
    const info: PointerInfo = {
      id: event.pointerId,
      type: event.pointerType,
      button: event.button,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      startTime: performance.now(),
      downUnit: null,
      downGround: null,
    };
    this.pointers.set(event.pointerId, info);
    if (event.pointerType === 'mouse') {
      this.lastMouse = { x: event.clientX, y: event.clientY };
    }

    if (event.pointerType === 'touch') {
      if (this.pointers.size === 2) {
        this.clearLongPress();
        this.panPointerId = null;
        this.panGrab = null;
        this.twoFingerCandidate = true;
        this.twoFingerStart = performance.now();
        this.twoFingerMoved = 0;
        this.updatePinch();
      } else if (this.pointers.size === 1) {
        const unit = this.host.renderView.pickUnit(event.clientX, event.clientY, true, true);
        info.downUnit = unit;
        info.downGround = this.host.renderView.pickGround(event.clientX, event.clientY);
        if (unit === null && info.downGround) {
          this.startLongPress();
        }
      }
      return;
    }

    if (event.button === 2) {
      this.handleOrder(event.clientX, event.clientY, event.shiftKey);
    }
  };

  private readonly onPointerMove = (event: PointerEvent): void => {
    const info = this.pointers.get(event.pointerId);
    if (event.pointerType === 'mouse') {
      this.lastMouse = { x: event.clientX, y: event.clientY };
    }
    if (!info) {
      return;
    }

    const dx = event.clientX - info.lastX;
    const dy = event.clientY - info.lastY;
    const total = Math.hypot(event.clientX - info.startX, event.clientY - info.startY);
    info.lastX = event.clientX;
    info.lastY = event.clientY;

    if (event.pointerType === 'touch') {
      if (this.pointers.size >= 2) {
        this.twoFingerMoved += Math.abs(dx) + Math.abs(dy);
        this.updatePinch();
        return;
      }

      // A gesture is classified exactly once. If the finger is already panning,
      // it keeps panning even if the long-press timer fires afterwards: flipping
      // a running drag into a box-select throws away the camera movement the
      // player has already made and is never what they asked for.
      if (this.panPointerId !== null) {
        this.panBy(event.clientX, event.clientY);
        return;
      }

      if (this.longPressReady) {
        if (total > BOX_DRAG_THRESHOLD) {
          if (!this.boxSelecting) {
            this.boxSelecting = true;
            this.boxStart = { x: info.startX, y: info.startY };
          }
          this.updateBox(event.clientX, event.clientY);
        }
        return;
      }

      if (info.downGround && total > BOX_DRAG_THRESHOLD) {
        this.panPointerId = event.pointerId;
        this.panGrab = info.downGround;
        // The pan owns the gesture from here on; disarm the long press so it can
        // never turn this same drag into a selection box.
        this.clearLongPress();
        this.longPressReady = false;
        this.panBy(event.clientX, event.clientY);
      }
      return;
    }

    if (info.button === 1) {
      const camera = this.host.renderView.getCamera();
      camera.rotate(-dx * 0.005);
      camera.clampTarget();
      this.host.renderView.applyCamera();
      return;
    }

    // A left drag box-selects regardless of what was under the press point: an
    // RTS drag that starts on a tank must still rubber-band, otherwise a box
    // whose corner happens to sit within the pick radius of a unit does nothing.
    if (info.button === 0 && total > BOX_DRAG_THRESHOLD) {
      if (!this.boxSelecting) {
        this.boxSelecting = true;
        this.boxStart = { x: info.startX, y: info.startY };
      }
      this.updateBox(event.clientX, event.clientY);
    }
  };

  private readonly onPointerUp = (event: PointerEvent): void => {
    const info = this.pointers.get(event.pointerId);
    this.pointers.delete(event.pointerId);
    if (!info) {
      return;
    }

    const total = Math.hypot(event.clientX - info.startX, event.clientY - info.startY);
    const duration = performance.now() - info.startTime;

    if (event.pointerType === 'touch') {
      if (this.pointers.size < 2) {
        this.pinch = null;
      }
      if (this.pointers.size === 0 && this.twoFingerCandidate) {
        const elapsed = performance.now() - this.twoFingerStart;
        if (this.twoFingerMoved < 10 && elapsed < LONG_PRESS_MS) {
          this.host.setSelection([]);
        }
        this.twoFingerCandidate = false;
        this.twoFingerMoved = 0;
        return;
      }
      if (this.boxSelecting) {
        this.finishBox(event.clientX, event.clientY);
      } else if (this.panPointerId === event.pointerId) {
        this.panPointerId = null;
        this.panGrab = null;
      } else if (!this.longPressReady && total < 8 && duration < 500) {
        this.handleTap(info.startX, info.startY);
      }
      this.clearLongPress();
      this.longPressReady = false;
      this.boxSelecting = false;
      this.boxStart = null;
      return;
    }

    if (this.boxSelecting) {
      this.finishBox(event.clientX, event.clientY);
      this.boxSelecting = false;
      this.boxStart = null;
      return;
    }

    if (info.button === 0 && total < BOX_DRAG_THRESHOLD) {
      this.handleLeftClick(info.startX, info.startY, event.shiftKey);
    }
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    const key = event.key.toLowerCase();
    if (key >= '1' && key <= '5') {
      const group = Number(key);
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        this.groups.set(group, this.host.getSelection());
        return;
      }
      const ids = this.groups.get(group);
      if (ids) {
        this.host.setSelection(ids);
      }
      return;
    }

    if (key === 's') {
      event.preventDefault();
      const selection = this.host.getSelection();
      if (selection.length > 0) {
        const world = this.host.getWorld();
        this.host.sendCommand({
          kind: 'stop',
          unitIds: selection,
          tick: world.tick + 1,
          issuer: 1,
        });
      }
      return;
    }

    if (['w', 'a', 'd', 'q', 'e', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
      event.preventDefault();
      this.keys.add(key);
    }
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    this.keys.delete(event.key.toLowerCase());
  };

  private panBy(clientX: number, clientY: number): void {
    if (!this.panGrab) {
      return;
    }
    const current = this.host.renderView.pickGround(clientX, clientY);
    if (!current) {
      return;
    }
    const camera = this.host.renderView.getCamera();
    camera.pan(this.panGrab.x - current.x, this.panGrab.z - current.z);
    camera.clampTarget();
    this.host.renderView.applyCamera();
  }

  private startLongPress(): void {
    this.clearLongPress();
    this.longPressReady = false;
    this.longPressTimer = window.setTimeout(() => {
      this.longPressTimer = null;
      // A pan that started first owns the gesture.
      if (this.panPointerId === null) {
        this.longPressReady = true;
      }
    }, LONG_PRESS_MS);
  }

  private clearLongPress(): void {
    if (this.longPressTimer !== null) {
      window.clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
  }

  private updatePinch(): void {
    const values = [...this.pointers.values()];
    const a = values[0];
    const b = values[1];
    if (!a || !b) {
      return;
    }
    const distance = Math.hypot(b.lastX - a.lastX, b.lastY - a.lastY);
    const angle = Math.atan2(b.lastY - a.lastY, b.lastX - a.lastX);
    if (!this.pinch) {
      this.pinch = { distance, angle };
      return;
    }
    if (distance > 0 && this.pinch.distance > 0) {
      const camera = this.host.renderView.getCamera();
      camera.zoomBy(this.pinch.distance / distance);
      camera.rotate(angleDiff(angle, this.pinch.angle));
      camera.clampTarget();
      this.host.renderView.applyCamera();
    }
    this.pinch = { distance, angle };
  }

  private updateBox(x: number, y: number): void {
    if (!this.boxStart) {
      return;
    }
    const left = Math.min(this.boxStart.x, x);
    const top = Math.min(this.boxStart.y, y);
    const width = Math.abs(x - this.boxStart.x);
    const height = Math.abs(y - this.boxStart.y);
    this.selectionBox.style.display = 'block';
    this.selectionBox.style.left = `${left}px`;
    this.selectionBox.style.top = `${top}px`;
    this.selectionBox.style.width = `${width}px`;
    this.selectionBox.style.height = `${height}px`;
  }

  /**
   * Box selection tests the same point that `pickUnit` uses for click selection,
   * so a box drawn around a tank always selects it. Testing the ground base
   * instead put the box a model-height away from the clickable point, and a
   * tight box could then select three of four tanks.
   */
  private finishBox(x: number, y: number): void {
    this.selectionBox.style.display = 'none';
    if (!this.boxStart) {
      return;
    }
    const left = Math.min(this.boxStart.x, x);
    const right = Math.max(this.boxStart.x, x);
    const top = Math.min(this.boxStart.y, y);
    const bottom = Math.max(this.boxStart.y, y);
    const world = this.host.getWorld();
    const selected: number[] = [];
    for (const unit of world.units) {
      if (unit.owner !== 1) {
        continue;
      }
      const screen = this.host.renderView.unitScreenCentre(unit.id);
      if (!screen) {
        continue;
      }
      if (screen.x >= left && screen.x <= right && screen.y >= top && screen.y <= bottom) {
        selected.push(unit.id);
      }
    }
    this.host.setSelection(selected);
  }

  private handleLeftClick(x: number, y: number, shift: boolean): void {
    this.lastGroundPick = this.host.renderView.pickGround(x, y);
    const unitId = this.host.renderView.pickUnit(x, y, true, false);
    const world = this.host.getWorld();
    const unit = unitId === null ? null : world.units.find((item) => item.id === unitId);
    if (unit && unit.owner === 1) {
      const current = this.host.getSelection();
      if (shift) {
        if (current.includes(unit.id)) {
          this.host.setSelection(current.filter((id) => id !== unit.id));
        } else {
          this.host.setSelection([...current, unit.id]);
        }
      } else {
        this.host.setSelection([unit.id]);
      }
      return;
    }
    if (!unit) {
      this.host.setSelection([]);
    }
  }

  private handleTap(x: number, y: number): void {
    const ground = this.host.renderView.pickGround(x, y);
    this.lastGroundPick = ground;

    const own = this.host.renderView.pickUnit(x, y, true, true);
    const world = this.host.getWorld();
    const ownUnit = own === null ? null : world.units.find((unit) => unit.id === own);
    if (ownUnit && ownUnit.owner === 1) {
      this.host.setSelection([ownUnit.id]);
      return;
    }

    const selection = this.host.getSelection();
    const enemy = this.host.renderView.pickUnit(x, y, false, true);
    const enemyUnit = enemy === null ? null : world.units.find((unit) => unit.id === enemy);
    if (enemyUnit && enemyUnit.owner !== 1 && selection.length > 0) {
      this.issueAttack(selection, enemyUnit.id);
      return;
    }

    if (ground && selection.length > 0) {
      this.issueMove(selection, ground.x, ground.z, false);
    } else if (!ground) {
      this.host.setSelection([]);
    }
  }

  private handleOrder(x: number, y: number, queue: boolean): void {
    const ground = this.host.renderView.pickGround(x, y);
    this.lastGroundPick = ground;

    const selection = this.host.getSelection();
    if (selection.length === 0) {
      return;
    }
    const enemyId = this.host.renderView.pickUnit(x, y, false, false);
    const world = this.host.getWorld();
    const enemy = enemyId === null ? null : world.units.find((unit) => unit.id === enemyId);
    if (enemy && enemy.owner !== 1) {
      this.issueAttack(selection, enemy.id);
      return;
    }
    if (ground) {
      this.issueMove(selection, ground.x, ground.z, queue);
    }
  }

  private issueMove(ids: number[], x: number, z: number, queue: boolean): void {
    const world = this.host.getWorld();
    this.host.sendCommand({
      kind: 'move',
      unitIds: ids,
      x,
      z,
      queue,
      tick: world.tick + 1,
      issuer: 1,
    });
  }

  private issueAttack(ids: number[], targetId: number): void {
    const world = this.host.getWorld();
    this.host.sendCommand({
      kind: 'attack',
      unitIds: ids,
      targetId,
      tick: world.tick + 1,
      issuer: 1,
    });
  }
}
