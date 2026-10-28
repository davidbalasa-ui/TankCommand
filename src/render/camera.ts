import {
  CAMERA_MAX_DISTANCE,
  CAMERA_MAX_PITCH_DEG,
  CAMERA_MIN_DISTANCE,
  CAMERA_MIN_PITCH_DEG,
  CAMERA_MIN_TERRAIN_CLEARANCE,
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

  constructor(mapSize: number) {
    this.mapSize = mapSize;
    this.targetX = -50;
    this.targetZ = -50;
    this.distance = 60;
    this.yaw = Math.PI / 4;
  }

  get pitch(): number {
    const distance = clamp(this.distance, CAMERA_MIN_DISTANCE, CAMERA_MAX_DISTANCE);
    const t =
      (distance - CAMERA_MIN_DISTANCE) / (CAMERA_MAX_DISTANCE - CAMERA_MIN_DISTANCE);
    return degToRad(CAMERA_MIN_PITCH_DEG + t * (CAMERA_MAX_PITCH_DEG - CAMERA_MIN_PITCH_DEG));
  }

  setDistance(distance: number): void {
    this.distance = clamp(distance, CAMERA_MIN_DISTANCE, CAMERA_MAX_DISTANCE);
  }

  zoomBy(factor: number): void {
    this.setDistance(this.distance * factor);
  }

  rotate(delta: number): void {
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
