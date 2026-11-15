import { z } from 'zod';

export const researchRowSchema = z.object({
  id: z.string().regex(/^research\.[a-z0-9]+(\.[a-z0-9_]+)+$/),
  name: z.string(),
  faction: z.enum(['human', 'alien']),
  cost: z.object({
    ore: z.number().int().nonnegative(),
    metal: z.number().int().nonnegative(),
  }),
  timeSec: z.number().positive(),
  requires: z.array(z.string()),
  // Unit and structure ids that stay locked until this node is researched.
  unlocks: z.array(z.string()),
  // Per-unit upgrades this node makes available.
  upgrades: z.array(z.enum(['fireRate', 'armor', 'stealth'])),
  placeholder: z.boolean(),
});

export type ResearchRow = z.infer<typeof researchRowSchema>;
