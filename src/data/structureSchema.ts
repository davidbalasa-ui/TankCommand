import { z } from 'zod';

export const structureRowSchema = z
  .object({
    id: z.string().regex(/^structure\.[a-z0-9]+(\.[a-z0-9_]+)+$/),
    name: z.string(),
    faction: z.enum(['human', 'alien']),
    kind: z.enum(['pad', 'metalStation', 'turret', 'radar', 'lab', 'airBase']),
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
    weapon: z
      .object({
        damage: z.number().nonnegative(),
        range: z.number().positive(),
        reloadSec: z.number().positive(),
        projectileSpeed: z.number().positive(),
        accuracy: z.number().min(0).max(1),
        splashRadius: z.number().nonnegative(),
        targets: z.array(z.enum(['ground', 'air', 'structure'])).min(1).optional(),
        /** Render-only effect name (e.g. 'shard'); the sim never reads it. */
        kind: z.string().min(1).optional(),
      })
      .optional(),
    turretTurnDegPerSec: z.number().positive().optional(),
    packSec: z.number().positive().optional(),
    packedUnitId: z.string().optional(),
    dismantleSec: z.number().positive().optional(),
    dismantleRefundPercent: z.number().min(0).max(100).optional(),
    sensorRange: z.number().positive().optional(),
    airCapacity: z.number().int().positive().optional(),
    upgrades: z.array(z.enum(['fireRate', 'armor', 'stealth'])).optional(),
    /** False for mission-only structures (the Shard): never offered for sale. Default true. */
    buyable: z.boolean().optional(),
    placeholder: z.boolean(),
  })
  .superRefine((row, ctx) => {
    if (row.kind === 'turret' && row.buyable !== false) {
      for (const key of ['weapon', 'turretTurnDegPerSec', 'packSec', 'packedUnitId'] as const) {
        if (row[key] === undefined) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: [key],
            message: `${key} is required for turrets`,
          });
        }
      }
    }
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
