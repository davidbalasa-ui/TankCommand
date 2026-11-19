/**
 * What the free download includes and what the "full game unlock" in-app purchase adds.
 *
 * This table is the one place the split is decided: the mission list, the skirmish map picker,
 * "Next mission" on the results screen and the app's start checks all ask `isFreeContent`.
 * Change the numbers or the map list here and everything follows.
 */
export interface FreeContentRule {
  /** Campaigns whose every mission is free. */
  readonly freeCampaigns: readonly string[];
  /** In every other campaign, missions with order 1..this number are free. */
  readonly freeMissionsPerCampaign: number;
  /** Skirmish maps that are free (map ids from src/data/maps.placeholder.json). */
  readonly freeSkirmishMaps: readonly string[];
}

export const FREE_CONTENT: FreeContentRule = {
  freeCampaigns: ['training'],
  freeMissionsPerCampaign: 5,
  freeSkirmishMaps: ['map.wp02_skirmish', 'map.wp08_lakeside'], // Cinder Basin, Lakeside Crossing
};

export type ContentRef =
  | { kind: 'mission'; campaign: string; order: number }
  | { kind: 'skirmishMap'; mapId: string };

/** True when the item can be played without the full game unlock. */
export function isFreeContent(item: ContentRef, rule: FreeContentRule = FREE_CONTENT): boolean {
  if (item.kind === 'mission') {
    return rule.freeCampaigns.includes(item.campaign) || item.order <= rule.freeMissionsPerCampaign;
  }
  return rule.freeSkirmishMaps.includes(item.mapId);
}

/** True when the item is locked behind the purchase for a player who has (or has not) unlocked. */
export function needsFullGame(item: ContentRef, unlocked: boolean, rule: FreeContentRule = FREE_CONTENT): boolean {
  return !unlocked && !isFreeContent(item, rule);
}
