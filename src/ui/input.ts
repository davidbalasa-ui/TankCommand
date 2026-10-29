import type { RenderView } from '../render/renderer';
import type { WorldState } from '../sim/types';
import { CAMERA_EDGE_BAND, CAMERA_FOV_DEG } from '../sim/tuning';
import {
  BOX_DRAG_THRESHOLD,
  DOUBLE_TAP_DISTANCE,
  DOUBLE_TAP_MS,
  KEY_ROTATE_SPEED,
  LONG_PRESS_MS,
  MIN_PINCH_DISTANCE,
  MOUSE_ROTATE_SPEED,
  TAP_MAX_MOVE,
  TAP_MAX_MS,
  TWO_FINGER_TAP_MAX_MOVE,
  TWO_FINGER_TAP_MS,
} from './inputTuning';

export interface IssuedCommand {
  kind: 'move' | 'attackMove' | 'attack' | 'hold' | 'stop';
  x: number | null;
  z: number | null;
  targetId: number | null;
  unitIds: number[];
  queue: boolean;
}

export interface InputHost {
  canvas: HTMLCanvasElement;
  renderView: RenderView;
  getWorld: () => WorldState;
  getSelection: () => number[];
  setSelection: (ids: number[]) => void;
  sendCommand: (command: unknown) => boolean;
  getQueueMode?: () => boolean;
  getAttackMoveArmed?: () => boolean;
  clearAttackMove?: () => void;
  setAttackMoveArmed?: (value: boolean) => void;
  assignGroup?: (group: number) => void;
  selectGroup?: (group: number) => void;
  centerGroup?: (group: number) => void;
  jumpToLatestAlert?: () => void;
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
  alt: boolean;
  dragged: boolean;
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
  private edgeScrollEnabled = true;
  private lastMouse: { x: number; y: number } | null = null;
  private boxStart: { x: number; y: number } | null = null;
  private boxSelecting = false;
  private panPointerId: number | null = null;
  private panGrab: { x: number; z: number } | null = null;
  private longPressTimer: number | null = null;
  private longPressReady = false;
  private pinch: { distance: number; angle: number; midX: number; midY: number } | null = null;
  private multiTouch = false;
  private suppressSingleUntilAllUp = false;
  private twoFingerStart = 0;
  private twoFingerMoved = 0;
  private lastTap: { time: number; x: number; y: number; unitId: number } | null = null;
  private lastClick: { time: number; unitId: number } | null = null;
  private lastGroupKey: { group: number; time: number } | null = null;
  private lastGroundPick: { x: number; z: number } | null = null;
  private lastIssued: IssuedCommand | null = null;
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
    window.addEventListener('contextmenu', this.onWindowContextMenu);
  }

  setEdgeScroll(enabled: boolean): void {
    this.edgeScrollEnabled = enabled;
  }

  getLastGroundPick(): { x: number; z: number } | null {
    return this.lastGroundPick ? { ...this.lastGroundPick } : null;
  }

  getLastIssuedCommand(): IssuedCommand | null {
    if (!this.lastIssued) {
      return null;
    }
    return { ...this.lastIssued, unitIds: [...this.lastIssued.unitIds] };
  }

  isLongPressReady(): boolean {
    return this.longPressReady;
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
      camera.rotate(KEY_ROTATE_SPEED * seconds);
    }
    if (this.keys.has('e')) {
      camera.rotate(-KEY_ROTATE_SPEED * seconds);
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
    window.removeEventListener('contextmenu', this.onWindowContextMenu);
    this.selectionBox.remove();
  }

  private readonly onContextMenu = (event: Event): void => {
    event.preventDefault();
  };

  private readonly onWindowContextMenu = (event: Event): void => {
    event.preventDefault();
  };

  private readonly onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    this.zoomAt(event.clientX, event.clientY, Math.exp(event.deltaY * 0.001));
    this.host.renderView.getCamera().clampTarget();
    this.host.renderView.applyCamera();
  };

  private readonly onPointerDown = (event: PointerEvent): void => {
    event.preventDefault();
    const canvas = this.host.canvas;
    try {
      canvas.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort in synthetic environments.
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
      alt: event.altKey,
      dragged: false,
    };
    this.pointers.set(event.pointerId, info);
    if (event.pointerType === 'mouse') {
      this.lastMouse = { x: event.clientX, y: event.clientY };
    }

    if (event.pointerType === 'touch') {
      if (this.pointers.size === 1) {
        info.downUnit = this.host.renderView.pickUnit(event.clientX, event.clientY, true, true);
        info.downGround = this.host.renderView.pickGround(event.clientX, event.clientY);
        this.startLongPress();
      } else if (this.pointers.size === 2) {
        this.multiTouch = true;
        this.suppressSingleUntilAllUp = true;
        this.twoFingerStart = performance.now();
        this.twoFingerMoved = 0;
        this.clearLongPress();
        this.longPressReady = false;
        this.panPointerId = null;
        this.panGrab = null;
        this.updatePinch();
      }
      return;
    }

    info.downGround = this.host.renderView.pickGround(event.clientX, event.clientY);
    if (event.button === 2 || event.button === 1) {
      event.preventDefault();
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
      if (this.suppressSingleUntilAllUp) {
        return;
      }
      if (this.panPointerId === event.pointerId) {
        info.dragged = true;
        this.panBy(event.clientX, event.clientY, dx, dy);
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
      if (total > BOX_DRAG_THRESHOLD) {
        this.panPointerId = event.pointerId;
        this.panGrab = info.downGround;
        this.clearLongPress();
        this.longPressReady = false;
        info.dragged = true;
        this.panBy(event.clientX, event.clientY, dx, dy);
      }
      return;
    }

    if (
      (info.button === 1 || info.button === 2) &&
      total > BOX_DRAG_THRESHOLD
    ) {
      info.dragged = true;
      this.panBy(event.clientX, event.clientY, dx, dy);
      return;
    }

    if (info.button === 0 && info.alt && total > BOX_DRAG_THRESHOLD) {
      info.dragged = true;
      const camera = this.host.renderView.getCamera();
      camera.rotate(-dx * MOUSE_ROTATE_SPEED);
      camera.clampTarget();
      this.host.renderView.applyCamera();
      return;
    }

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
      if (this.suppressSingleUntilAllUp && this.pointers.size > 0) {
        return;
      }
      if (this.pointers.size < 2) {
        this.pinch = null;
      }
      if (this.pointers.size === 0 && this.multiTouch) {
        const elapsed = performance.now() - this.twoFingerStart;
        if (this.twoFingerMoved < TWO_FINGER_TAP_MAX_MOVE && elapsed < TWO_FINGER_TAP_MS) {
          this.host.setSelection([]);
        }
        this.multiTouch = false;
        this.suppressSingleUntilAllUp = false;
        this.clearLongPress();
        this.longPressReady = false;
        this.boxSelecting = false;
        this.boxStart = null;
        return;
      }
      if (this.boxSelecting) {
        this.finishBox(event.clientX, event.clientY);
      } else if (this.panPointerId === event.pointerId) {
        this.panPointerId = null;
        this.panGrab = null;
      } else if (!this.longPressReady && total < TAP_MAX_MOVE && duration < TAP_MAX_MS) {
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

    if (info.button === 2 && !info.dragged && total < BOX_DRAG_THRESHOLD) {
      this.handleOrder(info.startX, info.startY, event.shiftKey);
      return;
    }

    if (info.button === 0 && !info.dragged && total < BOX_DRAG_THRESHOLD) {
      this.handleLeftClick(info.startX, info.startY, event.shiftKey);
    }
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    const key = event.key.toLowerCase();
    if (key >= '1' && key <= '9') {
      const group = Number(key);
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        this.host.assignGroup?.(group);
        return;
      }
      const now = performance.now();
      if (this.lastGroupKey && this.lastGroupKey.group === group && now - this.lastGroupKey.time < 350) {
        this.host.centerGroup?.(group);
        this.lastGroupKey = null;
      } else {
        this.host.selectGroup?.(group);
        this.lastGroupKey = { group, time: now };
      }
      return;
    }

    if (key === 's') {
      event.preventDefault();
      const selection = this.host.getSelection();
      if (selection.length > 0) {
        const world = this.host.getWorld();
        this.lastIssued = {
          kind: 'stop',
          x: null,
          z: null,
          targetId: null,
          unitIds: [...selection],
          queue: false,
        };
        this.host.sendCommand({
          kind: 'stop',
          unitIds: selection,
          tick: world.tick + 1,
          issuer: 1,
        });
      }
      return;
    }

    if (key === 'h') {
      event.preventDefault();
      const selection = this.host.getSelection();
      if (selection.length > 0) {
        const world = this.host.getWorld();
        this.lastIssued = {
          kind: 'hold',
          x: null,
          z: null,
          targetId: null,
          unitIds: [...selection],
          queue: false,
        };
        this.host.sendCommand({
          kind: 'hold',
          unitIds: selection,
          tick: world.tick + 1,
          issuer: 1,
        });
      }
      return;
    }

    if (key === ' ') {
      event.preventDefault();
      this.host.jumpToLatestAlert?.();
      return;
    }

    if (key === 'a') {
      event.preventDefault();
      this.keys.add(key);
      this.host.setAttackMoveArmed?.(true);
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

  /**
   * Zooms by `factor` while keeping the ground point under `(clientX, clientY)`
   * where it was. The correction is iterated because `applyCamera` re-anchors
   * the camera on the terrain height beneath the *new* target, so pan is not a
   * pure translation on uneven ground; a single pass leaves a residual.
   */
  private zoomAt(clientX: number, clientY: number, factor: number): void {
    if (!Number.isFinite(factor) || factor <= 0) {
      return;
    }
    const view = this.host.renderView;
    const camera = view.getCamera();
    const before = view.pickGround(clientX, clientY);
    camera.zoomBy(factor);
    view.applyCamera();
    if (!before) {
      return;
    }
    for (let i = 0; i < 4; i += 1) {
      const after = view.pickGround(clientX, clientY);
      if (!after) {
        break;
      }
      const dx = before.x - after.x;
      const dz = before.z - after.z;
      if (Math.hypot(dx, dz) < 0.05) {
        break;
      }
      camera.pan(dx, dz);
      view.applyCamera();
    }
  }

  private panBy(clientX: number, clientY: number, dx: number, dy: number): void {
    const view = this.host.renderView;
    const camera = view.getCamera();
    const current = view.pickGround(clientX, clientY);
    if (this.panGrab && current) {
      camera.pan(this.panGrab.x - current.x, this.panGrab.z - current.z);
    } else {
      this.screenPan(dx, dy);
    }
    camera.clampTarget();
    view.applyCamera();
  }

  private screenPan(dx: number, dy: number): void {
    const view = this.host.renderView;
    const camera = view.getCamera();
    const rect = this.host.canvas.getBoundingClientRect();
    if (rect.height <= 0) {
      return;
    }
    const worldPerPixel =
      (2 * camera.distance * Math.tan((CAMERA_FOV_DEG * Math.PI) / 360)) / rect.height;
    const rightX = Math.cos(camera.yaw);
    const rightZ = -Math.sin(camera.yaw);
    const forwardX = Math.sin(camera.yaw);
    const forwardZ = Math.cos(camera.yaw);
    camera.pan(
      -(rightX * dx + forwardX * dy) * worldPerPixel,
      -(rightZ * dx + forwardZ * dy) * worldPerPixel,
    );
  }

  private startLongPress(): void {
    this.clearLongPress();
    this.longPressReady = false;
    this.longPressTimer = window.setTimeout(() => {
      this.longPressTimer = null;
      if (this.panPointerId === null && this.pointers.size === 1) {
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
    const midX = (a.lastX + b.lastX) / 2;
    const midY = (a.lastY + b.lastY) / 2;
    if (!this.pinch) {
      this.pinch = { distance, angle, midX, midY };
      return;
    }

    if (distance > MIN_PINCH_DISTANCE && this.pinch.distance > MIN_PINCH_DISTANCE) {
      const camera = this.host.renderView.getCamera();
      this.zoomAt(midX, midY, this.pinch.distance / distance);
      camera.rotate(angleDiff(angle, this.pinch.angle));
      camera.clampTarget();
      this.host.renderView.applyCamera();
    }
    this.pinch = { distance, angle, midX, midY };
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

  private selectSameTypeOnScreen(unitId: number): void {
    const world = this.host.getWorld();
    const original = world.units.find((unit) => unit.id === unitId);
    if (!original) {
      return;
    }
    const ids = world.units
      .filter(
        (unit) =>
          unit.owner === 1 &&
          unit.typeId === original.typeId &&
          this.host.renderView.unitIsOnScreen(unit.id),
      )
      .map((unit) => unit.id);
    this.host.setSelection(ids.length > 0 ? ids : [unitId]);
  }

  private handleLeftClick(x: number, y: number, shift: boolean): void {
    this.lastGroundPick = this.host.renderView.pickGround(x, y);
    const unitId = this.host.renderView.pickUnit(x, y, true, false);
    const world = this.host.getWorld();
    const unit = unitId === null ? null : world.units.find((item) => item.id === unitId);
    if (unit && unit.owner === 1) {
      const current = this.host.getSelection();
      const now = performance.now();
      if (
        !shift &&
        this.lastClick &&
        this.lastClick.unitId === unit.id &&
        now - this.lastClick.time < DOUBLE_TAP_MS
      ) {
        this.selectSameTypeOnScreen(unit.id);
        this.lastClick = null;
        return;
      }
      if (shift) {
        if (current.includes(unit.id)) {
          this.host.setSelection(current.filter((id) => id !== unit.id));
        } else {
          this.host.setSelection([...current, unit.id]);
        }
      } else {
        this.host.setSelection([unit.id]);
      }
      this.lastClick = { time: now, unitId: unit.id };
      return;
    }
    if (!unit) {
      const selection = this.host.getSelection();
      const ground = this.lastGroundPick;
      if (this.host.getAttackMoveArmed?.() && ground && selection.length > 0) {
        this.issueMove(selection, ground.x, ground.z, false, 'attackMove');
        this.host.clearAttackMove?.();
        return;
      }
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
      const now = performance.now();
      if (
        this.lastTap &&
        this.lastTap.unitId === ownUnit.id &&
        now - this.lastTap.time < DOUBLE_TAP_MS &&
        Math.hypot(x - this.lastTap.x, y - this.lastTap.y) < DOUBLE_TAP_DISTANCE
      ) {
        this.selectSameTypeOnScreen(ownUnit.id);
        this.lastTap = null;
        return;
      }
      this.host.setSelection([ownUnit.id]);
      this.lastTap = { time: now, x, y, unitId: ownUnit.id };
      return;
    }

    const selection = this.host.getSelection();
    const enemy = this.host.renderView.pickUnit(x, y, false, true);
    const enemyUnit = enemy === null ? null : world.units.find((unit) => unit.id === enemy);
    if (enemyUnit && enemyUnit.owner !== 1 && selection.length > 0) {
      this.issueAttack(selection, enemyUnit.id);
      return;
    }

    const queue = this.host.getQueueMode?.() ?? false;
    if (ground && selection.length > 0) {
      if (this.host.getAttackMoveArmed?.()) {
        this.issueMove(selection, ground.x, ground.z, queue, 'attackMove');
        this.host.clearAttackMove?.();
      } else {
        this.issueMove(selection, ground.x, ground.z, queue, 'move');
      }
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
      this.issueMove(
        selection,
        ground.x,
        ground.z,
        queue || (this.host.getQueueMode?.() ?? false),
        'move',
      );
    }
  }

  private issueMove(
    ids: number[],
    x: number,
    z: number,
    queue: boolean,
    kind: 'move' | 'attackMove',
  ): void {
    this.lastIssued = { kind, x, z, targetId: null, unitIds: [...ids], queue };
    const world = this.host.getWorld();
    this.host.sendCommand({
      kind,
      unitIds: ids,
      x,
      z,
      queue,
      tick: world.tick + 1,
      issuer: 1,
    });
  }

  private issueAttack(ids: number[], targetId: number): void {
    this.lastIssued = {
      kind: 'attack',
      x: null,
      z: null,
      targetId,
      unitIds: [...ids],
      queue: false,
    };
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
