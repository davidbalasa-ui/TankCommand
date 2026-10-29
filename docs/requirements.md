# Requirements

| ID | Description |
| --- | --- |
| SIM-01 | Same seed and command list produce the same world hash after 10,000 steps. |
| SIM-02 | Different seeds produce different world hashes after 100 steps. |
| SIM-03 | World stepping does not mutate its input and accepts frozen input. |
| SIM-04 | Counter commands apply only on their tick and past ticks are ignored. |
| SIM-05 | Command validation rejects malformed commands. |
| SIM-06 | Fixed-step loop accumulates, caps and ignores invalid elapsed time. |
| SIM-07 | Seeded RNG is reproducible, resumable and respects exclusive upper bounds. |
| ASSET-01 | The real asset manifest validates. |
| ASSET-02 | Manifest rejection cases name the offending asset id. |
| ASSET-03 | Every manifest file exists and matches the recorded byte size. |
| ASSET-04 | Concurrent loads for one asset share one fetch. |
| ASSET-05 | Failed loads are not cached and can retry. |
| ASSET-06 | Refcounting keeps cached assets until final release and disposes once. |
| ASSET-07 | Preload reports progress, caches successes and reports every failure. |
| ASSET-08 | Byte size mismatches reject with AssetLoadError. |
| ASSET-09 | Credits check passes on committed files and fails when the manifest changes. |
| ASSET-10 | The browser loads the real tank model through registry, loader and GLTF decoder. |
| DATA-01 | The placeholder unit table loads against the real asset manifest. |
| DATA-02 | Unit data validation rejects the specified malformed rows. |
| DATA-03 | Placeholder reporting lists placeholder rows and drops tuned rows. |
| SAVE-01 | Save round trip preserves deterministic simulation state. |
| SAVE-02 | Save decoding returns specific failure reasons and never throws. |
| SAVE-03 | Autosave rotation keeps three slots and identifies the newest. |
| SAVE-04 | Exceeding the byte cap rejects without destroying previous saves. |
| SAVE-05 | Web storage quota failures map to StorageFullError. |
| LIFE-01 | Lifecycle events deduplicate pause and map back to pause plus back. |
| WD-01 | Watchdog freeze and recover fire once per episode and reset on beat. |
| WD-02 | Suspended watchdog suppresses freezes and resets clocks on unsuspend. |
| WD-03 | Global error capture records errors and rejects promises. |
| WD-04 | A frozen sim records a freeze report at the 2 s threshold and shows the recovery screen, with all recovery controls, at the 5 s recover mark. |
| UI-01 | Every screen mounts and unmounts without leaving DOM nodes behind. |
| UI-02 | Overlays stack and back pops settings then pause to inGame. |
| UI-03 | Rapid repeated navigation to one screen mounts only one DOM root. |
| UI-04 | Every registered control id is listed in the control inventory file. |
| UI-05 | E2E controls meet touch target size and do not overlap across the main flow. |
| LINT-01 | Lint runs with zero warnings. |
| LINT-02 | Sim lint restrictions fire on sim files and not on render files. |
| LINT-03 | The sim TypeScript config excludes the DOM library. |
| REQ-01 | Requirement coverage passes and fails when an untested id is appended. |
| CI-01 | The GitHub workflow runs the full CI and E2E commands. |
| CAP-01 | Capacitor config has the required app id, web dir and no server URL. |
| BUILD-01 | The built app uses relative asset URLs and copies public assets. |
| HOOK-01 | Production builds contain no test hook marker or window hook. |
| HOOK-02 | Test hook commands are validated and invalid commands do nothing. |
| REND-01 | The canvas is non-blank and frame count increases. |
| REND-02 | Hiding the page stops frames and resuming does not jump sim time. |
| PERF-01 | Sustained slow frames step quality down in order, fast frames step it back up, and quality never changes more than once per second. |
| MAP-01 | Same seed produces identical heights and different seeds differ. |
| MAP-02 | Start areas are flat and connected by an A* path. |
| MOVE-01 | A single tank ordered to a reachable point arrives within 0.5 units in time. |
| MOVE-02 | A tank ordered behind the ridge routes around it and never enters a blocked cell. |
| MOVE-03 | Orders outside the map are clamped and units never leave the map. |
| MOVE-04 | Twelve tanks ordered to one point settle without overlaps or active orders. |
| MOVE-05 | A destination inside a blocked area stops at the nearest reachable cell. |
| MOVE-06 | Commands for units the issuer does not own change nothing. |
| CMB-01 | Turrets turn at their turn rate independently of the hull. |
| CMB-02 | A tank fires only when aligned and reloaded, with the configured reload interval. |
| CMB-03 | Damage uses armor with a minimum of one, HP clamps and wrecks expire after ten seconds. |
| CMB-04 | Terrain blocks direct fire while open ground does not. |
| CMB-05 | Inaccuracy produces misses while perfect accuracy does not. |
| CMB-06 | Splash damage hits every unit in range including friendly units. |
| CMB-07 | A skirmish ends with a result, a wipe yields a winner and simultaneous last kills draw. |
| DET-01 | Scripted battles are bit-identical across runs and save/load. |
| CAM-01 | Camera target, distance and pitch clamp and interpolate. |
| CAM-02 | The camera never goes below terrain plus three units. |
| CAM-03 | Fully zoomed out on the phone viewport, all four map corners are on screen. |
| CAM-04 | Every map corner can be brought into the centre half of the screen at min and max zoom; the view never leaves more than a quarter screen of empty space. |
| INP-01 | Ground picks land within one unit of the picked point at multiple camera settings, and a right-click issues a move whose target is that point. |
| INP-02 | Box selection selects exactly the own tanks inside the box. |
| INP-03 | Clicking an enemy with a selection lowers its HP. |
| INP-04 | Camera pan, zoom, rotate and edge clamping work by keyboard, mouse and touch. |
| INP-05 | HUD button presses never issue map orders. |
| PLAY-01 | Full skirmish flow reaches results and Play again starts a fresh 4v4 match. |
| PLAY-02 | A real drag-select then right-click on a visible ground point moves every selected tank. |
| VIS-01 | The in-game view renders the 8-unit battlefield with many colours. |
| VIS-02 | At the default camera a player tank projects to at least 30 px on its longer side. |
| TCH-01 | One-finger drag pans the camera from any start point (ground, unit, sky, map edge); ground under the finger moves with it when pickable. |
| TCH-02 | Pinch zooms around the midpoint; twist rotates; both in one gesture; lifting a finger never issues an order. |
| TCH-03 | Two-finger tap deselects; double-tap selects same-type units on screen; long-press-drag box-selects. |
| TCH-04 | No page scroll, browser zoom, text selection or context menu during any gesture. |
| MM-01 | Minimap shows terrain, own and visible enemy units, and the camera footprint, and updates as the camera moves. |
| MM-02 | Tapping/clicking or dragging the minimap moves the camera target to that map point; right click orders a move. |
| HUD-01 | Command bar buttons (attack-move, hold, stop, queue, groups) work by touch and are disabled with no selection. |
| HUD-02 | On phone, tablet and desktop, no two HUD elements overlap, touch targets are ≥ 44×44 px and text is ≥ 12 px (measured from bounding boxes in e2e). |
| HUD-03 | Left-handed layout mirrors minimap and command bar and persists across reload. |
| HUD-04 | Selection panel shows selected units and narrows selection on tap. |
| ORD-01 | Hold: unit fires at enemies in range and never moves, even when attacked. |
| ORD-02 | Attack-move: unit moves to the point but engages enemies met on the way, then continues. |
| ORD-03 | Queued waypoints are followed in order and shown on screen. |
| GRP-01 | Control groups 1–5 by touch and 1–9 by keyboard: assign, select, double-select centres camera. |
| DESK-01 | Right/middle-drag pans, Alt+drag and Q/E rotate, wheel zooms to cursor, H/S/A keys work. |
