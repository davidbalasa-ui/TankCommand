import { z } from 'zod';

const side = z.number().int().positive();
const relationSchema = z.enum(['allied', 'neutral', 'hostile']);
const area = { x: z.number().finite(), z: z.number().finite(), radius: z.number().positive() };

export type Condition =
  | { t: 'time'; tick: number }
  | { t: 'areaEntered'; side: number; x: number; z: number; radius: number; unitType?: string; tag?: string }
  | { t: 'unitDestroyed'; tag: string }
  | { t: 'allDestroyed'; side: number; unitType?: string }
  | { t: 'resourceReached'; side: number; ore?: number; metal?: number }
  | { t: 'objectiveDone'; id: string }
  | { t: 'structureBuilt'; side: number; structureType: string; count?: number }
  | { t: 'relationIs'; a: number; b: number; relation: 'allied' | 'neutral' | 'hostile' }
  | { t: 'unitsAlive'; side?: number; tag?: string; op: '>=' | '<='; count: number }
  | { t: 'unitEscorted'; tag: string; x: number; z: number; radius: number }
  | { t: 'and'; conds: Condition[] }
  | { t: 'or'; conds: Condition[] }
  | { t: 'not'; cond: Condition };

export const conditionSchema: z.ZodType<Condition> = z.lazy(() =>
  z.discriminatedUnion('t', [
    z.object({ t: z.literal('time'), tick: z.number().int().nonnegative() }),
    z.object({
      t: z.literal('areaEntered'),
      side,
      ...area,
      unitType: z.string().optional(),
      tag: z.string().optional(),
    }),
    z.object({ t: z.literal('unitDestroyed'), tag: z.string().min(1) }),
    z.object({ t: z.literal('allDestroyed'), side, unitType: z.string().optional() }),
    z.object({
      t: z.literal('resourceReached'),
      side,
      ore: z.number().nonnegative().optional(),
      metal: z.number().nonnegative().optional(),
    }),
    z.object({ t: z.literal('objectiveDone'), id: z.string().min(1) }),
    z.object({
      t: z.literal('structureBuilt'),
      side,
      structureType: z.string().min(1),
      count: z.number().int().positive().optional(),
    }),
    z.object({ t: z.literal('relationIs'), a: side, b: side, relation: relationSchema }),
    z.object({
      t: z.literal('unitsAlive'),
      side: side.optional(),
      tag: z.string().optional(),
      op: z.enum(['>=', '<=']),
      count: z.number().int().nonnegative(),
    }),
    z.object({ t: z.literal('unitEscorted'), tag: z.string().min(1), ...area }),
    z.object({ t: z.literal('and'), conds: z.array(conditionSchema).min(1) }),
    z.object({ t: z.literal('or'), conds: z.array(conditionSchema).min(1) }),
    z.object({ t: z.literal('not'), cond: conditionSchema }),
  ]),
) as z.ZodType<Condition>;

export const actionSchema = z.discriminatedUnion('t', [
  z.object({
    t: z.literal('spawn'),
    side,
    unitType: z.string().min(1),
    count: z.number().int().positive().max(20),
    x: z.number().finite(),
    z: z.number().finite(),
    tag: z.string().optional(),
    drop: z.boolean().optional(),
  }),
  z.object({ t: z.literal('message'), text: z.string().min(1), speaker: z.string().optional() }),
  z.object({
    t: z.literal('revealArea'),
    ...area,
    forSec: z.number().positive().optional(),
  }),
  z.object({
    t: z.literal('setObjective'),
    id: z.string().min(1),
    status: z.enum(['add', 'done', 'failed']),
    text: z.string().optional(),
    kind: z.enum(['primary', 'optional']).optional(),
  }),
  z.object({
    t: z.literal('grant'),
    side,
    ore: z.number().nonnegative().optional(),
    metal: z.number().nonnegative().optional(),
  }),
  z.object({ t: z.literal('win') }),
  z.object({ t: z.literal('lose'), reason: z.string().optional() }),
  z.object({
    t: z.literal('aiOrder'),
    tag: z.string().min(1),
    mode: z.enum(['attack', 'defend']),
    x: z.number().finite(),
    z: z.number().finite(),
  }),
  z.object({ t: z.literal('setRelation'), a: side, b: side, relation: relationSchema }),
]);

export type Action = z.infer<typeof actionSchema>;

export const triggerSchema = z.object({
  id: z.string().min(1),
  when: conditionSchema,
  do: z.array(actionSchema).min(1),
  repeat: z.boolean().optional(),
});

export type Trigger = z.infer<typeof triggerSchema>;

const objectiveDef = z.object({
  id: z.string().min(1),
  text: z.string().min(1),
  kind: z.enum(['primary', 'optional']),
});

const missionSide = z.object({
  player: side,
  faction: z.enum(['human', 'alien']),
  controller: z.enum(['human', 'ai', 'scripted', 'none']),
  team: z.number().int().positive().optional(),
  difficulty: z.enum(['easy', 'normal', 'hard']).optional(),
  provokable: z.boolean().optional(),
  forgiveAfterSec: z.number().positive().optional(),
  groupId: z.string().optional(),
  ore: z.number().int().nonnegative(),
  metal: z.number().int().nonnegative(),
  researchDone: z.array(z.string()).optional(),
  /** Only these items can be bought by this side in the mission (all when absent). */
  available: z.array(z.string().min(1)).optional(),
});

export const missionSchema = z.object({
  id: z.string().regex(/^mission\.[a-z0-9_.]+$/),
  campaign: z.enum(['training', 'human', 'alien']),
  order: z.number().int().positive(),
  title: z.string().min(1),
  briefing: z.string().min(1),
  mapId: z.string().min(1),
  sides: z.array(missionSide).min(2),
  relations: z
    .array(z.object({ a: side, b: side, relation: relationSchema }))
    .optional(),
  units: z.array(
    z.object({
      side,
      unitType: z.string().min(1),
      x: z.number().finite(),
      z: z.number().finite(),
      heading: z.number().finite().optional(),
      tag: z.string().optional(),
    }),
  ),
  structures: z.array(
    z.object({ side, structureType: z.string().min(1), x: z.number().finite(), z: z.number().finite() }),
  ),
  objectives: z.array(objectiveDef),
  triggers: z.array(triggerSchema),
  timeLimitSec: z.number().positive().optional(),
  placeholder: z.boolean(),
});

export type MissionRow = z.infer<typeof missionSchema>;

export function parseMission(json: unknown): MissionRow {
  const parsed = missionSchema.safeParse(json);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    const path = issue ? issue.path.join('.') : '';
    throw new Error(`Invalid mission at ${path || '(root)'}: ${issue?.message ?? 'unknown'}`);
  }
  return parsed.data;
}
