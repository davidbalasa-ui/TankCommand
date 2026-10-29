export const MAX_SLOPE = 1.2; // placeholder until Stage 0
export const UNIT_RADIUS = 1.6; // placeholder until Stage 0
export const STUCK_TICKS = 40; // placeholder until Stage 0
export const MAX_REPLANS = 3; // placeholder until Stage 0
export const MOVE_EPS = 0.05; // placeholder until Stage 0
export const STOP_DISTANCE = 0.5; // placeholder until Stage 0
export const WAYPOINT_REACHED = 1; // placeholder until Stage 0
export const FORMATION_SPACING = 4; // placeholder until Stage 0
export const PROJECTILE_TTL = 5; // placeholder until Stage 0
export const WRECK_TTL_SEC = 10; // placeholder until Stage 0
export const TURRET_ALIGN_TOLERANCE_DEG = 5; // placeholder until Stage 0
export const FIRE_MOVE_SPEED_MAX = 0.1; // placeholder until Stage 0
export const ATTACK_REPATH_TICKS = 20; // placeholder until Stage 0
export const MUZZLE_HEIGHT = 1.5; // placeholder until Stage 0
export const TARGET_HEIGHT = 1; // placeholder until Stage 0
export const MAX_COMMAND_IDS = 200; // placeholder until Stage 0
export const MAX_AIM_ERROR = 0.35; // placeholder until Stage 0
export const DEFAULT_MAP_SIZE = 160; // placeholder until Stage 0
export const DEFAULT_CELL_SIZE = 2; // placeholder until Stage 0
export const TANK_LENGTH = 4.5; // placeholder until Stage 0
export const CAMERA_MIN_DISTANCE = 12; // placeholder until Stage 0
export const CAMERA_MAX_DISTANCE = 140; // placeholder until Stage 0
export const CAMERA_DEFAULT_DISTANCE = 40; // placeholder until Stage 0
// 20° minimum pitch: at 35° the top of the frame (35 - 24° half-FOV) was still
// 11° *below* horizontal, so no pixel of sky was ever on screen and TCH-01's
// screen-space fallback was unreachable. 20° puts the top of the close 3D view
// ~4° above the horizon on flat ground.
export const CAMERA_MIN_PITCH_DEG = 20; // placeholder until Stage 0
export const CAMERA_MAX_PITCH_DEG = 80; // placeholder until Stage 0
// 0.31, not 0.5: with the pitch floor at 20 the minimum-to-maximum span is 60°,
// so 0.31 keeps the default distance-40 view at ~49° pitch (VIS-02) while still
// reaching 80° at the fit-to-map zoom ceiling.
export const CAMERA_PITCH_CURVE = 0.31; // placeholder until Stage 0
export const CAMERA_EDGE_BAND = 16; // placeholder until Stage 0
export const CAMERA_MIN_TERRAIN_CLEARANCE = 3; // placeholder until Stage 0
export const CAMERA_FOV_DEG = 48; // placeholder until Stage 0
export const CAMERA_MAP_FIT_MARGIN = 1.08; // placeholder until Stage 0
export const ATTACK_MOVE_ENGAGE_FACTOR = 1; // placeholder until Stage 0
