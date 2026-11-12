export const MAX_SLOPE = 1.2; // placeholder until Stage 0
export const UNIT_RADIUS = 1.6; // placeholder until Stage 0
export const STUCK_TICKS = 20; // 1 s without progress: plan the route again (round whatever is in the way)
export const MAX_REPLANS = 6; // give up the order after this many fruitless re-plans (about 6 s)
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

export const SIM_SPEED_SLOW = 0.5; // placeholder until Stage 0
export const SIM_SPEED_NORMAL = 1; // placeholder until Stage 0
export const SIM_SPEED_FAST = 2; // placeholder until Stage 0

export const AUTOSAVE_CHECK_INTERVAL_MS = 15_000; // placeholder until Stage 0
export const ALERT_RATE_LIMIT_MS = 2_000; // placeholder until Stage 0
export const ALERT_TOAST_TTL_MS = 6_000; // placeholder until Stage 0
export const ALERT_MAX_TOASTS = 3; // placeholder until Stage 0
export const AUDIO_MUSIC_CROSSFADE_SEC = 0.25; // placeholder until Stage 0
export const UNIT_CAP = 200; // placeholder until Stage 0
export const DEPOSIT_REACH = 2; // placeholder until Stage 0
export const PAD_REACH = 4; // placeholder until Stage 0
// Ore crates: miners pack ore into crates of this size beside the deposit, up to this many per
// side; haulers carry them to the pad. A miner with a full stack stops digging until one is taken.
export const ORE_CRATE_SIZE = 10;
export const ORE_MAX_CRATES = 5;
export const CRATE_REACH = 4;
export const STATION_REACH = 4; // placeholder until Stage 0
export const DEPOSIT_PICK_RADIUS = 3; // placeholder until Stage 0
export const STRUCTURE_PICK_PADDING = 1; // placeholder until Stage 0
export const DROP_SPAWN_RADIUS = 6; // placeholder until Stage 0
export const DROP_SPAWN_TRIES = 32; // placeholder until Stage 0
export const PLACEMENT_CLEARANCE = 0.25; // placeholder until Stage 0
export const PLACEMENT_SAMPLE_STEPS = 3; // placeholder until Stage 0
export const ALERT_TTL_SEC = 6; // placeholder until Stage 0
export const DROP_BEAM_TTL_SEC = 1; // placeholder until Stage 0
// Units and buildings cost ore only (metal pays for research), so the start gets the old
// metal's worth in ore on top: 500 + 100.
export const SKIRMISH_ORE = 600; // placeholder until Stage 0
export const SKIRMISH_METAL = 100; // placeholder until Stage 0

export const SKIRMISH_TANK_OFFSETS: ReadonlyArray<{ x: number; z: number }> = [
  { x: 4, z: -10 },
  { x: -4, z: -10 },
]; // placeholder until Stage 0
export const SKIRMISH_MINER_OFFSET = { x: -10, z: 0 }; // placeholder until Stage 0
export const SKIRMISH_TUG_OFFSET = { x: -10, z: -6 }; // placeholder until Stage 0
export const SKIRMISH_TANK_HEADING = Math.PI / 4; // placeholder until Stage 0
export const DEFAULT_DISMANTLE_SEC = 4; // placeholder until Stage 0
export const DEFAULT_DISMANTLE_REFUND_PERCENT = 70; // placeholder until Stage 0
export const RUBBLE_TTL_SEC = 30; // placeholder until Stage 0
export const RUBBLE_PADDING = 0.5; // placeholder until Stage 0
export const MAX_PLACEMENT_SLOPE = 1.6; // placeholder until Stage 0
export const UPGRADE_COST_ORE = 60; // placeholder until Stage 0
export const UPGRADE_COST_METAL = 30; // placeholder until Stage 0
export const UPGRADE_FIRE_RATE_FACTOR = 0.7; // placeholder until Stage 0
export const UPGRADE_ARMOR_BONUS = 3; // placeholder until Stage 0
export const STRUCTURE_DAMAGE_LIGHT = 0.75; // placeholder until Stage 0
export const STRUCTURE_DAMAGE_HEAVY = 0.5; // placeholder until Stage 0
export const STRUCTURE_DAMAGE_CRITICAL = 0.25; // placeholder until Stage 0
export const REPAIR_IDLE_ONLY = false; // placeholder until Stage 0

export const VISION_INTERVAL_TICKS = 4; // placeholder until Stage 0
export const STEALTH_SIGHT_FACTOR = 0.35; // placeholder until Stage 0
export const VIEWER_EYE_HEIGHT = 1.5; // placeholder until Stage 0
