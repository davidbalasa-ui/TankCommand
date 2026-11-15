import { z } from 'zod';

export const gameplayConfigSchema = z.object({
  autosaveMinutes: z.number().positive(),
  placeholder: z.boolean().optional(),
});

export type GameplayConfig = z.infer<typeof gameplayConfigSchema>;

export function parseGameplayConfig(input: unknown): GameplayConfig {
  return gameplayConfigSchema.parse(input);
}
