import {
  CAMERA_DEFAULT_DISTANCE,
  CAMERA_FOV_DEG,
  CAMERA_MAP_FIT_MARGIN,
  CAMERA_MAX_DISTANCE,
  CAMERA_MAX_PITCH_DEG,
  CAMERA_MIN_DISTANCE,
  CAMERA_MIN_PITCH_DEG,
  CAMERA_MIN_TERRAIN_CLEARANCE,
  CAMERA_PITCH_CURVE,
} from '../sim/tuning';

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function degToRad(value: number): number {
  return (value * Math.PI) / 180;
}

export interface CameraInfo {
  targetX: number;
  targetZ: number;
  distance: number;
  yaw: number;
  pitch: number;
}

export interface CameraPosition {
  x: number;
  y: number;
  z: number;
}

export class RtsCamera {
  public targetX: number;
  public targetZ: number;
  public distance: number;
  public yaw: number;
  private readonly mapSize: number;
  private aspect = 16 / 9;
  private fovDeg = CAMERA_FOV_DEG;
  private viewportSet = false;

  constructor(mapSize: number) {
    this.mapSize = mapSize;
    this.targetX = 0;
    this.targetZ = 0;
    this.distance = CAMERA_DEFAULT_DISTANCE;
    this.yaw = Math.PI / 4;
  }

  /**
   * The viewport supplies the aspect and field of view that decide how far the
   * camera has to stand back for the whole map to fit. Keeping this out of the
   * constructor preserves the unit-level fallback (`CAMERA_MAX_DISTANCE`) for
   * callers that do not have a rendered viewport.
   */
  setViewport(aspect: number, fovDeg: number): void {
    if (Number.isFinite(aspect) && aspect > 0) {
      this.aspect = aspect;
    }
    if (Number.isFinite(fovDeg) && fovDeg > 1 && fovDeg < 179) {
      this.fovDeg = fovDeg;
    }
    this.viewportSet = true;
    this.setDistance(this.distance);
    this.clampTarget();
  }

  /** Maximum distance at which the whole map can be kept on screen. */
  get maxDistance(): number {
    if (!this.viewportSet) {
      return CAMERA_MAX_DISTANCE;
    }
    const vFov = degToRad(this.fovDeg);
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * this.aspect);
    const limiting = Math.min(vFov, hFov);
    const radius = (this.mapSize * Math.SQRT2 * 0.5) * CAMERA_MAP_FIT_MARGIN;
    const fit = radius / Math.sin(Math.max(0.01, limiting / 2));
    return Math.max(CAMERA_MAX_DISTANCE, fit);
  }

  /**
   * Pitch rises from `CAMERA_MIN_PITCH_DEG` when fully zoomed in to
   * `CAMERA_MAX_PITCH_DEG` when fully zoomed out. The interpolation is eased
   * (`CAMERA_PITCH_CURVE`) rather than linear so the default zoom sits at a
   * readable ~50 degrees instead of a flat, top-down-looking 45.
   */
  get pitch(): number {
    const max = this.maxDistance;
    const distance = clamp(this.distance, CAMERA_MIN_DISTANCE, max);
    const t = (distance - CAMERA_MIN_DISTANCE) / Math.max(0.001, max - CAMERA_MIN_DISTANCE);
    const eased = Math.pow(clamp(t, 0, 1), CAMERA_PITCH_CURVE);
    return degToRad(
      CAMERA_MIN_PITCH_DEG + eased * (CAMERA_MAX_PITCH_DEG - CAMERA_MIN_PITCH_DEG),
    );
  }

  setDistance(distance: number): void {
    this.distance = clamp(distance, CAMERA_MIN_DISTANCE, this.maxDistance);
  }

  zoomBy(factor: number): void {
    if (!Number.isFinite(factor) || factor <= 0) {
      return;
    }
    this.setDistance(this.distance * factor);
  }

  rotate(delta: number): void {
    if (!Number.isFinite(delta)) {
      return;
    }
    this.yaw += delta;
    while (this.yaw > Math.PI) {
      this.yaw -= Math.PI * 2;
    }
    while (this.yaw < -Math.PI) {
      this.yaw += Math.PI * 2;
    }
  }

  setTarget(x: number, z: number): void {
    this.targetX = x;
    this.targetZ = z;
    this.clampTarget();
  }

  pan(dx: number, dz: number): void {
    this.targetX += dx;
    this.targetZ += dz;
    this.clampTarget();
  }

  clampTarget(): void {
    const half = this.mapSize / 2;
    // The map edge is the hard stop. The rendered skirt and far plane continue
    // beyond it visually, so this both keeps every corner reachable and never
    // lets the camera wander several screens into nowhere.
    this.targetX = clamp(this.targetX, -half, half);
    this.targetZ = clamp(this.targetZ, -half, half);
  }

  info(): CameraInfo {
    return {
      targetX: this.targetX,
      targetZ: this.targetZ,
      distance: this.distance,
      yaw: this.yaw,
      pitch: this.pitch,
    };
  }

  position(terrainHeightAt?: (x: number, z: number) => number): CameraPosition {
    const pitch = this.pitch;
    const horizontal = this.distance * Math.cos(pitch);
    const x = this.targetX - Math.sin(this.yaw) * horizontal;
    const z = this.targetZ - Math.cos(this.yaw) * horizontal;
    const targetGround = terrainHeightAt ? terrainHeightAt(this.targetX, this.targetZ) : 0;
    let y = targetGround + this.distance * Math.sin(pitch);
    if (terrainHeightAt) {
      const ground = terrainHeightAt(x, z);
      if (y < ground + CAMERA_MIN_TERRAIN_CLEARANCE) {
        y = ground + CAMERA_MIN_TERRAIN_CLEARANCE;
      }
    }
    return { x, y, z };
  }
}
