import * as THREE from 'three';
import { AssetLoader } from '../assets/loader';
import type { AssetRegistry } from '../assets/registry';
import { createThreeDecoders, fallbackModel } from '../assets/threeDecoders';

const TANK_ASSET_ID = 'unit.human.poc_tank';

export interface RenderStats {
  loadedModels: string[];
  meshCount: number;
  drawCalls: number;
  frame: number;
}

export function createRenderer(canvas: HTMLCanvasElement): THREE.WebGLRenderer {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  return renderer;
}

export class RenderView {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera: THREE.PerspectiveCamera;
  private readonly observer: ResizeObserver;
  private readonly loader: AssetLoader<THREE.Object3D, THREE.Texture, ArrayBuffer>;
  private readonly loadedModels: string[] = [];
  private frame = 0;
  private disposed = false;

  constructor(canvas: HTMLCanvasElement, registry: AssetRegistry) {
    this.renderer = createRenderer(canvas);
    this.camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
    this.camera.position.set(35, 40, 35);
    this.camera.lookAt(0, 0, 0);

    this.scene.background = new THREE.Color('#090D16');
    this.buildScene();

    this.observer = new ResizeObserver(() => {
      this.resize(canvas);
    });
    this.observer.observe(canvas);
    this.resize(canvas);

    const baseUrl = new URL('.', document.baseURI).toString();
    this.loader = new AssetLoader<THREE.Object3D, THREE.Texture, ArrayBuffer>({
      registry,
      baseUrl,
      decoders: createThreeDecoders(),
      fetchBytes: async (url) => {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} for ${url}`);
        }
        return response.arrayBuffer();
      },
    });

    void this.loadTank();
  }

  render(alpha: number): void {
    void alpha;
    this.frame += 1;
    this.renderer.render(this.scene, this.camera);
  }

  stats(): RenderStats {
    let meshCount = 0;
    this.scene.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        meshCount += 1;
      }
    });
    return {
      loadedModels: [...this.loadedModels],
      meshCount,
      drawCalls: this.renderer.info.render.calls,
      frame: this.frame,
    };
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.observer.disconnect();
    this.renderer.dispose();
  }

  private buildScene(): void {
    const hemisphere = new THREE.HemisphereLight(0xffffff, 0x223322, 1.2);
    this.scene.add(hemisphere);

    const directional = new THREE.DirectionalLight(0xffffff, 2.2);
    directional.position.set(30, 50, 20);
    directional.castShadow = true;
    directional.shadow.mapSize.set(2048, 2048);
    directional.shadow.camera.left = -100;
    directional.shadow.camera.right = 100;
    directional.shadow.camera.top = 100;
    directional.shadow.camera.bottom = -100;
    this.scene.add(directional);

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(200, 200),
      new THREE.MeshStandardMaterial({ color: 0x24302a }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);
  }

  private resize(canvas: HTMLCanvasElement): void {
    const width = Math.max(1, canvas.clientWidth);
    const height = Math.max(1, canvas.clientHeight);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  private async loadTank(): Promise<void> {
    try {
      const asset = await this.loader.load(TANK_ASSET_ID);
      if (this.disposed) {
        return;
      }
      if (asset instanceof THREE.Object3D) {
        this.scene.add(asset);
        this.loadedModels.push(TANK_ASSET_ID);
      } else {
        this.scene.add(fallbackModel());
      }
    } catch {
      if (!this.disposed) {
        this.scene.add(fallbackModel());
      }
    }
  }
}
