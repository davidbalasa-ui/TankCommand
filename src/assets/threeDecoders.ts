import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { AssetDecoders } from './loader';

export function createThreeDecoders(): AssetDecoders<THREE.Object3D, THREE.Texture, ArrayBuffer> {
  return {
    model: async (buffer) => {
      const loader = new GLTFLoader();
      return new Promise<THREE.Object3D>((resolve, reject) => {
        loader.parse(
          buffer,
          '',
          (gltf) => {
            resolve(gltf.scene);
          },
          (error: unknown) => {
            reject(error instanceof Error ? error : new Error(String(error)));
          },
        );
      });
    },
    texture: async (buffer) => {
      const bitmap = await createImageBitmap(new Blob([buffer]));
      const texture = new THREE.Texture(bitmap);
      texture.needsUpdate = true;
      return texture;
    },
    audio: (buffer) => Promise.resolve(buffer),
  };
}

export function fallbackModel(): THREE.Mesh {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(2, 2, 2),
    new THREE.MeshStandardMaterial({ color: 0xff00ff }),
  );
  mesh.position.set(0, 1, 0);
  return mesh;
}
