import { describe, expect, it } from 'vitest';
import { RtsCamera } from '../../src/render/camera';
import { generateMap, heightAt } from '../../src/sim/map';
import {
  CAMERA_MAX_DISTANCE,
  CAMERA_MAX_PITCH_DEG,
  CAMERA_MIN_DISTANCE,
  CAMERA_MIN_PITCH_DEG,
} from '../../src/sim/tuning';

describe('camera', () => {
  it('[CAM-01] target, distance and pitch clamp and interpolate', () => {
    const camera = new RtsCamera(160);
    camera.setTarget(1000, -1000);
    expect(camera.targetX).toBe(80);
    expect(camera.targetZ).toBe(-80);

    camera.setDistance(1);
    expect(camera.distance).toBe(CAMERA_MIN_DISTANCE);
    expect((camera.pitch * 180) / Math.PI).toBeCloseTo(CAMERA_MIN_PITCH_DEG, 5);

    camera.setDistance(1000);
    expect(camera.distance).toBe(CAMERA_MAX_DISTANCE);
    expect((camera.pitch * 180) / Math.PI).toBeCloseTo(CAMERA_MAX_PITCH_DEG, 5);

    camera.setDistance((CAMERA_MIN_DISTANCE + CAMERA_MAX_DISTANCE) / 2);
    const pitch = (camera.pitch * 180) / Math.PI;
    expect(pitch).toBeGreaterThan(CAMERA_MIN_PITCH_DEG);
    expect(pitch).toBeLessThan(CAMERA_MAX_PITCH_DEG);
  });

  it('[CAM-02] the camera never goes below terrain plus three', () => {
    const map = generateMap(42);
    const camera = new RtsCamera(map.size);
    for (let i = 0; i < 1000; i += 1) {
      const targetX = -75 + (i % 151);
      const targetZ = -75 + ((i * 7) % 151);
      camera.setTarget(targetX, targetZ);
      camera.setDistance(CAMERA_MIN_DISTANCE + (i % 129));
      camera.rotate(i * 0.37);
      const position = camera.position((x, z) => heightAt(map, x, z));
      expect(position.y).toBeGreaterThanOrEqual(heightAt(map, position.x, position.z) + 3 - 0.000001);
    }
  });
});
