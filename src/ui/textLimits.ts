/**
 * Word limits for the HUD's hint bubbles. Bubbles grow to fit their text (they never cut it
 * short), so these limits are what keeps their size predictable on a phone. Change a number here
 * and the data test (tests/unit/textLimits.test.ts) checks every mission text against it.
 *
 * - objective: the current goal on the top-centre line ("Destroy the enemy pad").
 * - message: a mission message shown on that same line for a few seconds (the speaker's name
 *   is not counted).
 * - hint: the small help bubble on the side of the screen.
 */
export const HINT_WORD_LIMITS = {
  objective: 20,
  message: 20,
  hint: 24,
} as const;

/** The one-time selection hint bubble. */
export const SELECT_HINT_TEXT = 'Double-tap a unit to pick all of its kind. Hold, then drag, for a box. Or turn on Select.';

export type HintTextKind = keyof typeof HINT_WORD_LIMITS;

export function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter((word) => word.length > 0).length;
}

/** True when the text fits its bubble's word limit. */
export function fitsHintLimit(kind: HintTextKind, text: string): boolean {
  return wordCount(text) <= HINT_WORD_LIMITS[kind];
}
