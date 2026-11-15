export const BOX_DRAG_THRESHOLD = 6; // placeholder until Stage 0
export const TAP_MAX_MOVE = 8; // placeholder until Stage 0
export const TAP_MAX_MS = 500; // placeholder until Stage 0
export const DOUBLE_TAP_MS = 300; // placeholder until Stage 0
export const DOUBLE_TAP_DISTANCE = 30; // placeholder until Stage 0
export const LONG_PRESS_MS = 400; // placeholder until Stage 0
export const TWO_FINGER_TAP_MAX_MOVE = 10; // placeholder until Stage 0
export const TWO_FINGER_TAP_MS = 400; // placeholder until Stage 0
export const MIN_PINCH_DISTANCE = 0.01; // placeholder until Stage 0
export const GROUP_LONG_PRESS_MS = 450; // placeholder until Stage 0
export const GROUP_DOUBLE_TAP_MS = 600; // placeholder until Stage 0
export const KEY_ROTATE_SPEED = 1.2; // placeholder until Stage 0
export const MOUSE_ROTATE_SPEED = 0.005; // placeholder until Stage 0
export const CLEAR_ATTACK_MOVE_AFTER_MS = 4000; // placeholder until Stage 0

// Camera glide after a flick. Speeds are in camera-distances per second, so a flick feels the
// same zoomed in or out.
/** Only the last part of a drag counts toward the flick speed. */
export const FLING_WINDOW_MS = 100;
/** A finger that rests this long before lifting means "stop here": no glide. */
export const FLING_HOLD_MS = 60;
/** Slower than this is a drag, not a flick. */
export const FLING_MIN_SPEED = 0.35;
export const FLING_MAX_SPEED = 4;
/** The glide slows by e every this many seconds. */
export const FLING_DECAY_SEC = 0.3;
export const FLING_STOP_SPEED = 0.04;
/** The drag samples behind a flick must cover at least this long. */
export const FLING_MIN_SPAN_MS = 24;
