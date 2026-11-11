import { AUDIO_MUSIC_CROSSFADE_SEC } from '../sim/tuning';

export type SoundEvent =
  | { type: 'selection' }
  | { type: 'orderAck' }
  | { type: 'weapon'; weapon: string }
  | { type: 'explosion'; size: number }
  | { type: 'dropBeam' }
  | { type: 'mining' }
  | { type: 'delivery' }
  | { type: 'pack' }
  | { type: 'deploy' }
  | { type: 'aircraftLaunch' }
  | { type: 'aircraftLand' }
  | { type: 'alert'; kind: string };

export interface AudioStatusView {
  unlocked: boolean;
  contextAvailable: boolean;
  masterVolume: number;
  musicVolume: number;
  effectsVolume: number;
  played: string[];
}

interface MusicLayer {
  calmGain: GainNode;
  combatGain: GainNode;
  nodes: OscillatorNode[];
}

export interface AudioEngineOptions {
  contextFactory?: () => AudioContext | null;
  random?: () => number;
}

function clampVolume(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(1, Math.max(0, value));
}

function defaultContextFactory(): AudioContext | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return new window.AudioContext();
}

const ORDER_ACK_NOTES = [660, 780, 880, 990] as const;

export class AudioEngine {
  private readonly contextFactory: () => AudioContext | null;
  private readonly random: () => number;
  private context: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private musicGain: GainNode | null = null;
  private effectsGain: GainNode | null = null;
  private unlocked = false;
  private masterVolume = 0.8;
  private musicVolume = 0.45;
  private effectsVolume = 0.75;
  private lastOrderAck = -1;
  private musicRequest: { faction: 'human' | 'alien'; combat: boolean } | null = null;
  private music: MusicLayer | null = null;
  private played: string[] = [];

  constructor(options: AudioEngineOptions = {}) {
    this.contextFactory = options.contextFactory ?? defaultContextFactory;
    this.random = options.random ?? Math.random;
  }

  isUnlocked(): boolean {
    return this.unlocked;
  }

  status(): AudioStatusView {
    return {
      unlocked: this.unlocked,
      contextAvailable: this.context !== null,
      masterVolume: this.masterVolume,
      musicVolume: this.musicVolume,
      effectsVolume: this.effectsVolume,
      played: [...this.played],
    };
  }

  unlock(): void {
    if (this.unlocked) {
      return;
    }
    let context: AudioContext | null = null;
    try {
      context = this.contextFactory();
    } catch {
      context = null;
    }
    if (!context) {
      return;
    }

    this.context = context;
    this.masterGain = context.createGain();
    this.musicGain = context.createGain();
    this.effectsGain = context.createGain();
    this.masterGain.connect(context.destination);
    this.musicGain.connect(this.masterGain);
    this.effectsGain.connect(this.masterGain);
    this.applyGains();
    void context.resume().catch(() => undefined);
    this.unlocked = true;
    this.rebuildMusic();
  }

  setMasterVolume(volume: number): void {
    this.masterVolume = clampVolume(volume);
    this.applyGains();
  }

  setMusicVolume(volume: number): void {
    this.musicVolume = clampVolume(volume);
    this.applyGains();
  }

  setEffectsVolume(volume: number): void {
    this.effectsVolume = clampVolume(volume);
    this.applyGains();
  }

  nextOrderAckVariant(): number {
    const raw = Math.floor(this.random() * ORDER_ACK_NOTES.length);
    const index = Math.max(0, Math.min(ORDER_ACK_NOTES.length - 1, raw));
    const chosen = index === this.lastOrderAck ? (index + 1) % ORDER_ACK_NOTES.length : index;
    this.lastOrderAck = chosen;
    return chosen;
  }

  play(event: SoundEvent): void {
    if (!this.unlocked || !this.context) {
      return;
    }
    this.played.push(event.type);
    while (this.played.length > 80) {
      this.played.shift();
    }

    switch (event.type) {
      case 'selection':
        this.tone(520, 0.06, 'sine', 0.18);
        this.tone(780, 0.07, 'sine', 0.12, 0.04);
        break;
      case 'orderAck': {
        const variant = this.nextOrderAckVariant();
        const note = ORDER_ACK_NOTES[variant] ?? ORDER_ACK_NOTES[0];
        this.tone(note, 0.075, 'square', 0.14);
        this.tone(note * 1.25, 0.09, 'triangle', 0.08, 0.055);
        break;
      }
      case 'weapon': {
        const weapon = event.weapon.toLowerCase();
        const base = weapon.includes('missile') ? 180 : weapon.includes('artillery') ? 110 : weapon.includes('pulse') ? 420 : 260;
        this.tone(base, 0.09, 'sawtooth', 0.22);
        this.noise(0.045, 0.08);
        break;
      }
      case 'explosion': {
        const size = Math.min(2, Math.max(0.2, event.size));
        this.noise(0.16 + size * 0.1, 0.18 + size * 0.08);
        this.tone(90 / size, 0.18 + size * 0.08, 'sine', 0.16);
        break;
      }
      case 'dropBeam':
        this.tone(840, 0.45, 'sine', 0.14);
        this.tone(420, 0.45, 'triangle', 0.1, 0.08);
        break;
      case 'mining':
        this.tone(220, 0.05, 'square', 0.08);
        this.tone(180, 0.05, 'square', 0.06, 0.08);
        break;
      case 'delivery':
        this.tone(440, 0.09, 'triangle', 0.12);
        this.tone(660, 0.12, 'triangle', 0.1, 0.09);
        break;
      case 'pack':
        this.noise(0.08, 0.12);
        this.tone(160, 0.12, 'sawtooth', 0.1);
        break;
      case 'deploy':
        this.tone(180, 0.12, 'sawtooth', 0.1);
        this.tone(360, 0.1, 'square', 0.12, 0.11);
        break;
      case 'aircraftLaunch':
        this.tone(220, 0.3, 'sawtooth', 0.1);
        this.tone(330, 0.3, 'triangle', 0.08, 0.15);
        break;
      case 'aircraftLand':
        this.tone(300, 0.24, 'triangle', 0.1);
        this.tone(180, 0.24, 'sine', 0.08, 0.12);
        break;
      case 'alert': {
        const frequency = event.kind === 'underAttack' ? 980 : 720;
        this.tone(frequency, 0.12, 'square', 0.14);
        this.tone(frequency * 0.75, 0.12, 'square', 0.11, 0.15);
        break;
      }
    }
  }

  setMusic(faction: 'human' | 'alien', combat: boolean): void {
    this.musicRequest = { faction, combat };
    if (this.unlocked) {
      this.rebuildMusic();
    }
  }

  private applyGains(): void {
    const context = this.context;
    if (!context) {
      return;
    }
    const now = context.currentTime;
    this.masterGain?.gain.setTargetAtTime(this.masterVolume, now, 0.02);
    this.musicGain?.gain.setTargetAtTime(this.musicVolume, now, 0.02);
    this.effectsGain?.gain.setTargetAtTime(this.effectsVolume, now, 0.02);
  }

  private tone(
    frequency: number,
    duration: number,
    type: OscillatorType,
    volume: number,
    delay = 0,
  ): void {
    const context = this.context;
    const effects = this.effectsGain;
    if (!context || !effects) {
      return;
    }
    const start = context.currentTime + delay;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume), start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(gain);
    gain.connect(effects);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
  }

  private noise(duration: number, volume: number): void {
    const context = this.context;
    const effects = this.effectsGain;
    if (!context || !effects) {
      return;
    }
    const length = Math.max(1, Math.floor(context.sampleRate * duration));
    const buffer = context.createBuffer(1, length, context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let index = 0; index < data.length; index += 1) {
      data[index] = (this.random() * 2 - 1) * (1 - index / Math.max(1, data.length));
    }
    const source = context.createBufferSource();
    const gain = context.createGain();
    source.buffer = buffer;
    gain.gain.value = volume;
    source.connect(gain);
    gain.connect(effects);
    source.start();
  }

  private rebuildMusic(): void {
    const request = this.musicRequest;
    const context = this.context;
    const musicGain = this.musicGain;
    if (!request || !context || !musicGain) {
      return;
    }
    this.stopMusic();
    const calmGain = context.createGain();
    const combatGain = context.createGain();
    calmGain.gain.value = 0.0001;
    combatGain.gain.value = 0.0001;
    calmGain.connect(musicGain);
    combatGain.connect(musicGain);

    const base = request.faction === 'alien' ? 110 : 130;
    const nodes: OscillatorNode[] = [];
    const addOsc = (frequency: number, target: GainNode, type: OscillatorType): void => {
      const oscillator = context.createOscillator();
      oscillator.type = type;
      oscillator.frequency.value = frequency;
      oscillator.connect(target);
      oscillator.start();
      nodes.push(oscillator);
    };
    addOsc(base, calmGain, 'triangle');
    addOsc(base * 1.5, calmGain, 'sine');
    addOsc(base * 2, combatGain, 'sawtooth');
    addOsc(base * 3, combatGain, 'square');
    this.music = { calmGain, combatGain, nodes };
    this.applyMusicMix(request.combat);
  }

  private applyMusicMix(combat: boolean): void {
    const context = this.context;
    const music = this.music;
    if (!context || !music) {
      return;
    }
    const now = context.currentTime;
    music.calmGain.gain.setTargetAtTime(combat ? 0.0001 : 0.045, now, AUDIO_MUSIC_CROSSFADE_SEC);
    music.combatGain.gain.setTargetAtTime(combat ? 0.05 : 0.0001, now, AUDIO_MUSIC_CROSSFADE_SEC);
  }

  private stopMusic(): void {
    const music = this.music;
    if (!music) {
      return;
    }
    for (const node of music.nodes) {
      try {
        node.stop();
      } catch {
        // Already stopped.
      }
    }
    music.calmGain.disconnect();
    music.combatGain.disconnect();
    this.music = null;
  }
}
