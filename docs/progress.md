# Progress

## WP-01

Built the project foundation: Vite/TypeScript scaffolding, Capacitor config, headless deterministic sim shell, asset manifest/registry/loader with browser three.js decoders, placeholder unit data schema and table, save envelopes and autosave rotation, key-value storage adapters, lifecycle and watchdog services, DOM screen router and screens, three.js render shell, test hook, credits and requirement-coverage scripts, unit tests, Playwright flows, CI workflow, and project documentation. No gameplay rules or final balance data were added.

## WP-02

Added the first playable slice: deterministic heightmap terrain with a ridge and gap, A* movement with formation goals and separation, unit commands and validation, turret tracking, projectiles with accuracy, splash and wrecks, win/lose detection, save round-tripping of the new state, an RTS camera, terrain and tank rendering with turret pivots and enemy tinting, selection and health overlays, projectile and wreck visuals, desktop and touch input, a full-screen skirmish HUD, results flow with Play again, WP-02 unit and browser tests, and updated documentation and control inventory.

## WP-02 readability pass

Play-test follow-up: the tank model was being scaled against a hidden 200×200 ground plane inside the glb, so tanks rendered as a few pixels; scaling now measures only visible meshes. The camera starts on the player's tanks at distance 40 with an eased ~49° pitch, the scene has a sky gradient plus a ground skirt and far plane instead of black void, the terrain uses a valley/slope/rock colour ramp with flat shading for legible hills, and ground picking raycasts the skirt as well so a right-click on any visible ground issues an order. Added `unitScreenBounds()` to the test hook plus `PLAY-02` (drag-select then right-click moves every tank) and `VIS-02` (a tank is at least 30 px on its longer side).
