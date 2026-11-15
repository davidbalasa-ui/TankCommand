// The skirmish played out behind the title screen: Arcadian raiders roll in on a Terran landing
// pad and its defenders, and the two sides fight it out. When either side is nearly gone a fresh
// wave drives in, so there is always something happening. The pad cannot fall, so the scene never
// ends. Nothing here is saved or scored; it is scenery that happens to run on the real sim.
import { SIM_TICK_HZ } from './sim/constants';
import { addUnit } from './sim/spawn';
import { step } from './sim/world';
import type { Command } from './sim/commands';
import type { PlayerId, WorldState } from './sim/types';

const DEFENDER: PlayerId = 1;
const RAIDER: PlayerId = 2;
const DEFENDERS = ['unit.human.light_tank', 'unit.human.heavy_tank', 'unit.human.light_tank', 'unit.human.missile_tank'];
const RAIDERS = ['unit.alien.light_tank', 'unit.alien.heavy_tank', 'unit.alien.missile_tank', 'unit.alien.light_tank', 'unit.alien.light_tank'];
/** Raiders appear this far from the pad, toward the enemy side. */
const RAID_DISTANCE = 34;
/** Longest the sim may catch up in one frame (after a hitch or a hidden tab). */
const MAX_CATCH_UP_TICKS = 6;

export interface TitleBattleFocus {
  x: number;
  z: number;
  /** Direction the raiders come from, in radians (world x/z plane). */
  approach: number;
}

export class TitleBattle {
  private world: WorldState;
  private carry = 0;
  private waves = 0;
  /** The units this scene sent in, by side (the starting pad forces are left out). */
  private readonly cast = new Map<PlayerId, Set<number>>([
    [DEFENDER, new Set()],
    [RAIDER, new Set()],
  ]);
  readonly focus: TitleBattleFocus;

  constructor(world: WorldState) {
    this.world = world;
    // The scene needs no AI: units engage whatever comes in range on their own.
    this.world.aiStates = [];
    const pad = world.structures.find((item) => item.owner === DEFENDER) ?? null;
    const enemy = world.structures.find((item) => item.owner === RAIDER) ?? null;
    const x = pad?.x ?? 0;
    const z = pad?.z ?? 0;
    const approach = enemy ? Math.atan2(enemy.z - z, enemy.x - x) : Math.atan2(-z, -x);
    this.focus = { x, z, approach };
    this.topUpDefenders();
    this.sendRaid();
  }

  current(): WorldState {
    return this.world;
  }

  /** How many raids have been sent (the first one counts). */
  raids(): number {
    return this.waves;
  }

  /** Runs the sim forward by `seconds` of real time; returns the fraction into the next tick. */
  advance(seconds: number): number {
    this.carry += Math.max(0, seconds) * SIM_TICK_HZ;
    let ticks = Math.floor(this.carry);
    this.carry -= ticks;
    ticks = Math.min(ticks, MAX_CATCH_UP_TICKS);
    for (let i = 0; i < ticks; i += 1) {
      this.tick();
    }
    return this.carry;
  }

  private tick(): void {
    // The pad is the stage; it never falls, so the match never ends.
    for (const structure of this.world.structures) {
      const type = this.world.structureTypes.get(structure.typeId);
      if (type && structure.owner === DEFENDER) {
        structure.hp = type.hp;
      }
    }
    const commands: Command[] = [];
    if (this.alive(RAIDER) <= 1) {
      commands.push(...this.sendRaid());
    }
    if (this.alive(DEFENDER) <= 1) {
      this.topUpDefenders();
    }
    this.world = step(this.world, commands);
  }

  private alive(player: PlayerId): number {
    const ids = this.cast.get(player) ?? new Set<number>();
    return this.world.units.filter((unit) => ids.has(unit.id) && unit.hp > 0).length;
  }

  private topUpDefenders(): void {
    const { x, z, approach } = this.focus;
    DEFENDERS.forEach((typeId, index) => {
      // A loose line between the pad and the raiders' side.
      const side = (index - (DEFENDERS.length - 1) / 2) * 4.5;
      const ux = x + Math.cos(approach) * 11 - Math.sin(approach) * side;
      const uz = z + Math.sin(approach) * 11 + Math.cos(approach) * side;
      const unit = addUnit(this.world, { owner: DEFENDER, typeId, x: ux, z: uz, heading: approach });
      if (unit) {
        this.cast.get(DEFENDER)?.add(unit.id);
      }
    });
  }

  private sendRaid(): Command[] {
    const { x, z, approach } = this.focus;
    const ids: number[] = [];
    const wobble = ((this.waves * 37) % 9) / 9 - 0.5;
    RAIDERS.forEach((typeId, index) => {
      const side = (index - (RAIDERS.length - 1) / 2) * 4;
      const angle = approach + wobble * 0.5;
      const ux = x + Math.cos(angle) * RAID_DISTANCE - Math.sin(angle) * side;
      const uz = z + Math.sin(angle) * RAID_DISTANCE + Math.cos(angle) * side;
      const unit = addUnit(this.world, { owner: RAIDER, typeId, x: ux, z: uz, heading: angle + Math.PI });
      if (unit) {
        ids.push(unit.id);
        this.cast.get(RAIDER)?.add(unit.id);
      }
    });
    this.waves += 1;
    if (ids.length === 0) {
      return [];
    }
    const command: Command = { kind: 'attackMove', tick: this.world.tick + 1, issuer: RAIDER, unitIds: ids, x, z };
    // Issued straight away for the first wave (before any tick), else with the coming tick.
    if (this.waves === 1) {
      this.world = step(this.world, [command]);
      return [];
    }
    return [command];
  }
}
