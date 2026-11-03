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

export const mapRowSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  size: z.number().positive(),
  cellSize: z.number().positive(),
  starts: z.array(startSchema).min(2),
  deposits: z.array(depositSchema),
  placeholder: z.boolean(),
});

export type MapRow = z.infer<typeof mapRowSchema>;
export type MapDepositRow = z.infer<typeof depositSchema>;
