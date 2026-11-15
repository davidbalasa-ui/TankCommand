import { describe, expect, it } from 'vitest';
import { AudioEngine, type SoundEvent } from '../../src/audio/audio';

interface FakeParam {
  value: number;
  setValueAtTime(value: number, time: number): void;
  exponentialRampToValueAtTime(value: number, time: number): void;
  setTargetAtTime(value: number, time: number, constant: number): void;
}

function fakeParam(): FakeParam {
  return {
    value: 0,
    setValueAtTime: () => undefined,
    exponentialRampToValueAtTime: () => undefined,
    setTargetAtTime: () => undefined,
  };
}

function fakeAudioContext(): AudioContext {
  const starts: number[] = [];
  const context = {
    currentTime: 0,
    sampleRate: 8000,
    destination: {},
    resume: () => Promise.resolve(),
    createGain: () => ({
      gain: fakeParam(),
      connect: () => undefined,
      disconnect: () => undefined,
    }),
    createOscillator: () => ({
      type: 'sine',
      frequency: fakeParam(),
      connect: () => undefined,
      start: () => {
        starts.push(1);
      },
      stop: () => undefined,
    }),
    createBuffer: (_channels: number, length: number) => ({
      getChannelData: () => new Float32Array(length),
    }),
    createBufferSource: () => ({
      buffer: null,
      connect: () => undefined,
      start: () => {
        starts.push(1);
      },
    }),
  };
  return context as unknown as AudioContext;
}

describe('audio', () => {
  it('[AUD-02] no audio context is created before the first user gesture', () => {
    let created = 0;
    const engine = new AudioEngine({
      contextFactory: () => {
        created += 1;
        return null;
      },
      random: () => 0,
    });
    expect(engine.isUnlocked()).toBe(false);
    engine.play({ type: 'selection' });
    expect(created).toBe(0);
    engine.unlock();
    expect(created).toBe(1);
    expect(engine.isUnlocked()).toBe(false);
  });

  it('[AUD-01] every sound event schedules audio, order acks do not repeat, volumes apply live', () => {
    const engine = new AudioEngine({
      contextFactory: () => fakeAudioContext(),
      random: () => 0,
    });
    engine.unlock();
    expect(engine.isUnlocked()).toBe(true);
    const events: SoundEvent[] = [
      { type: 'selection' },
      { type: 'orderAck' },
      { type: 'weapon', weapon: 'cannon' },
      { type: 'explosion', size: 1.5 },
      { type: 'dropBeam' },
      { type: 'mining' },
      { type: 'delivery' },
      { type: 'pack' },
      { type: 'deploy' },
      { type: 'aircraftLaunch' },
      { type: 'aircraftLand' },
      { type: 'alert', kind: 'underAttack' },
    ];
    for (const event of events) {
      engine.play(event);
    }
    expect(engine.status().played).toEqual(events.map((event) => event.type));

    const first = engine.nextOrderAckVariant();
    const second = engine.nextOrderAckVariant();
    expect(second).not.toBe(first);

    engine.setMasterVolume(0.2);
    engine.setMusicVolume(0.3);
    engine.setEffectsVolume(0.4);
    const status = engine.status();
    expect(status.masterVolume).toBe(0.2);
    expect(status.musicVolume).toBe(0.3);
    expect(status.effectsVolume).toBe(0.4);
  });
});
