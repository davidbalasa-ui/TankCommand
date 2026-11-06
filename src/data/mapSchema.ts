import { z } from 'zod';

const depositSchema = z.object({
  kind: z.enum(['ore', 'metal']),
  x: z.number().finite(),
  z: z.number().finite(),
  amount: z.number().positive(),
});

const startSchema = z.object({
  player: z.number().int().positive(),
  x: z.number().finite(),
  z: z.number().finite(),
});

const featuresSchema = z.object({
  waterLevel: z.number().finite().nullable(),
  lakes: z.array(
    z.object({
      x: z.number().finite(),
      z: z.number().finite(),
      radius: z.number().positive(),
      depth: z.number().positive(),
    }),
  ),
  rivers: z.array(
    z.object({
      x0: z.number().finite(),
      z0: z.number().finite(),
      x1: z.number().finite(),
      z1: z.number().finite(),
      width: z.number().positive(),
      depth: z.number().positive(),
      fords: z.array(z.object({ from: z.number().min(0).max(1), to: z.number().min(0).max(1) })),
    }),
  ),
});

export const mapRowSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  size: z.number().positive(),
  cellSize: z.number().positive(),
  starts: z.array(startSchema).min(2),
  deposits: z.array(depositSchema),
  features: featuresSchema.optional(),
  placeholder: z.boolean(),
});

export type MapRow = z.infer<typeof mapRowSchema>;
export type MapDepositRow = z.infer<typeof depositSchema>;
