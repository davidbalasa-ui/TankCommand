import { z } from 'zod';

export type PlayerId = number;

const baseCommand = z.object({
  tick: z.number().int().finite(),
  issuer: z.number().int().finite(),
});

const commandSchema = z.discriminatedUnion('kind', [
  baseCommand.extend({
    kind: z.literal('noop'),
  }),
  baseCommand.extend({
    kind: z.literal('debug.addCounter'),
    amount: z.number().finite(),
  }),
]);

export type Command = z.infer<typeof commandSchema>;

export function validateCommand(x: unknown): Command | null {
  const parsed = commandSchema.safeParse(x);
  return parsed.success ? parsed.data : null;
}
