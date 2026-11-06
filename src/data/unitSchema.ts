import { z } from 'zod';

const weaponSchema = z.object({
  id: z.string(),
  damage: z.number().nonnegative(),
  range: z.number().positive(),
  reloadSec: z.number().positive(),
  projectileSpeed: z.number().positive(),
  accuracy: z.number().min(0).max(1),
  splashRadius: z.number().nonnegative(),
  targets: z.array(z.enum(['ground', 'air', 'structure'])).min(1),
});

export const unitRowSchema = z
  .object({
    id: z.string().regex(/^unit\.[a-z0-9]+(\.[a-z0-9_]+)+$/),
    name: z.string(),
    faction: z.enum(['human', 'alien']),
    role: z.enum(['worker', 'scout', 'tank', 'artillery', 'support', 'air', 'structure']),
    techLevel: z.number().int().nonnegative(),
    cost: z.object({
      ore: z.number().int().nonnegative(),
      metal: z.number().int().nonnegative(),
    }),
    deliverySec: z.number().positive(),
    hp: z.number().int().positive(),
    armor: z.number().nonnegative(),
    speed: z.object({
      top: z.number().nonnegative(),
      accel: z.number().nonnegative(),
      turnDegPerSec: z.number().nonnegative(),
    }),
    turretTurnDegPerSec: z.number().nonnegative(),
    weapons: z.array(weaponSchema),
    fireOnMove: z.boolean(),
    sightRange: z.number().positive(),
    sensorRange: z.number(),
    abilities: z.array(z.string()),
    upgrades: z.array(z.enum(['fireRate', 'armor', 'stealth'])),
    carryCapacity: z.number().int().nonnegative().optional(),
    workerKind: z.enum(['oreMiner', 'tug']).optional(),
    miningRatePerSec: z.number().positive().optional(),
    salvageRefundPercent: z.number().min(0).max(100).optional(),
    repair: z
      .object({ radius: z.number().positive(), ratePerSec: z.number().positive() })
      .optional(),
    deploysTo: z.string().optional(),
    deploySec: z.number().positive().optional(),
    modelAssetId: z.string(),
    source: z.object({
      kind: z.enum(['placeholder', 'video', 'manual', 'tuned']),
      ref: z.string().optional(),
    }),
  })
  .superRefine((row, ctx) => {
    if (row.sensorRange < row.sightRange) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['sensorRange'],
        message: 'sensorRange must be >= sightRange',
      });
    }
    if (row.role === 'worker' && row.carryCapacity === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['carryCapacity'],
        message: 'carryCapacity is required for workers',
      });
    }
    if (row.workerKind && row.carryCapacity === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['carryCapacity'],
        message: 'carryCapacity is required for worker units',
      });
    }
    if (row.workerKind === 'oreMiner' && row.miningRatePerSec === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['miningRatePerSec'],
        message: 'miningRatePerSec is required for ore miners',
      });
    }
    if (row.source.kind !== 'placeholder' && !row.source.ref) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['source', 'ref'],
        message: 'source.ref is required unless source.kind is placeholder',
      });
    }
  });

export type UnitRow = z.infer<typeof unitRowSchema>;
