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
    targetId: z.number().int().finite(),
  }),
  baseCommand.extend({
    kind: z.literal('hold'),
    unitIds,
  }),
  baseCommand.extend({
    kind: z.literal('stop'),
    unitIds,
  }),
]);

export type Command = z.infer<typeof commandSchema>;

export function validateCommand(x: unknown): Command | null {
  const parsed = commandSchema.safeParse(x);
  return parsed.success ? parsed.data : null;
}
