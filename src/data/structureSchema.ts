import { z } from 'zod';

export const structureRowSchema = z
  .object({
    id: z.string().regex(/^structure\.[a-z0-9]+(\.[a-z0-9_]+)+$/),
    name: z.string(),
    faction: z.enum(['human', 'alien']),
    kind: z.enum(['pad', 'metalStation']),
    cost: z.object({
      ore: z.number().int().nonnegative(),
      metal: z.number().int().nonnegative(),
    }),
    deliverySec: z.number().positive(),
    hp: z.number().int().positive(),
    armor: z.number().nonnegative(),
    footprint: z.object({
      cellsX: z.number().int().positive(),
      cellsZ: z.number().int().positive(),
    }),
    sightRange: z.number().positive(),
    modelId: z.string().min(1),
    buildOnMetalDeposit: z.boolean(),
    metalRatePerSec: z.number().nonnegative().optional(),
    containerSize: z.number().int().positive().optional(),
    maxContainers: z.number().int().nonnegative().optional(),
    placeholder: z.boolean(),
  })
  .superRefine((row, ctx) => {
    if (row.kind === 'metalStation') {
      if (row.metalRatePerSec === undefined) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['metalRatePerSec'],
          message: 'metalRatePerSec is required for metal stations',
        });
      }
      if (row.containerSize === undefined) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['containerSize'],
          message: 'containerSize is required for metal stations',
        });
      }
      if (row.maxContainers === undefined) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['maxContainers'],
          message: 'maxContainers is required for metal stations',
        });
      }
      if (!row.buildOnMetalDeposit) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['buildOnMetalDeposit'],
          message: 'metal stations must build on a metal deposit',
        });
      }
    }
  });

export type StructureRow = z.infer<typeof structureRowSchema>;
