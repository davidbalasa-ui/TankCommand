import { z } from 'zod';
import { MAX_COMMAND_IDS } from './tuning';

const baseCommand = z.object({
  tick: z.number().int().finite(),
  issuer: z.number().int().finite(),
});

const unitIds = z
  .array(z.number().int().finite())
  .min(1)
  .max(MAX_COMMAND_IDS);

const entityId = z.number().int().finite();

const commandSchema = z.discriminatedUnion('kind', [
  baseCommand.extend({
    kind: z.literal('noop'),
  }),
  baseCommand.extend({
    kind: z.literal('debug.addCounter'),
    amount: z.number().finite(),
  }),
  baseCommand.extend({
    kind: z.literal('move'),
    unitIds,
    x: z.number().finite(),
    z: z.number().finite(),
    queue: z.boolean().optional(),
  }),
  baseCommand.extend({
    kind: z.literal('attackMove'),
    unitIds,
    x: z.number().finite(),
    z: z.number().finite(),
    queue: z.boolean().optional(),
  }),
  baseCommand.extend({
    kind: z.literal('attack'),
    unitIds,
    targetId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('hold'),
    unitIds,
  }),
  baseCommand.extend({
    kind: z.literal('stop'),
    unitIds,
  }),
  baseCommand.extend({
    kind: z.literal('buy'),
    itemId: z.string().min(1),
    padId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('cancel'),
    orderId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('placeKit'),
    kitId: entityId,
    x: z.number().finite(),
    z: z.number().finite(),
  }),
  baseCommand.extend({
    kind: z.literal('mine'),
    unitIds,
    depositId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('assign'),
    unitIds,
    stationId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('haul'),
    unitIds,
    depositId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('salvage'),
    unitIds,
  }),
  baseCommand.extend({
    kind: z.literal('diplomacy.set'),
    a: entityId,
    b: entityId,
    relation: z.enum(['allied', 'neutral', 'hostile']),
    oneWay: z.boolean().optional(),
  }),
  baseCommand.extend({
    kind: z.literal('pack'),
    structureId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('deploy'),
    unitId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('dismantle'),
    structureId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('research'),
    labId: entityId,
    nodeId: z.string().min(1),
  }),
  baseCommand.extend({
    kind: z.literal('cancelResearch'),
    labId: entityId,
  }),
  baseCommand.extend({
    kind: z.literal('upgrade'),
    targetId: entityId,
    upgrade: z.enum(['fireRate', 'armor', 'stealth']),
  }),
  baseCommand.extend({
    kind: z.literal('air'),
    unitIds,
    action: z.enum(['launch', 'recall']),
  }),
  baseCommand.extend({
    kind: z.literal('repair'),
    unitIds,
    targetId: entityId,
  }),
]);

export type Command = z.infer<typeof commandSchema>;

export function validateCommand(x: unknown): Command | null {
  const parsed = commandSchema.safeParse(x);
  return parsed.success ? parsed.data : null;
}
