# TankCommand (Orbital Drop Command)

Modernized 3D mobile & web real-time strategy rebuild inspired by the 1998 classic *Armor Command* (Ronin Entertainment / Ripcord Games), architected by David Balasa.

## Key Features
- **Orbital Drop Pad Production Loop**: Queue vehicles and structure kits in orbit aboard the Seed Ship and beam them down to planetary **Landing Pads**.
- **Dual-Resource Economy & Physical Tug Convoys**: Harvest surface **Ore** with mobile Resource Miners (auto-dismantling on vein depletion) and refine high-tier **Metal / Precursor Metal** using a two-part **Mining Platform + Resource Tug** supply convoy.
- **Untethered Map-Wide Placement & Pack/Relocate Defenses**: Place turrets and structures anywhere on clear terrain with zero power-grid tether, or dismantle/relocate turrets (4s timer, 70% Ore refund) to leapfrog with the front line.
- **100% Vehicular Fire-on-the-Move Roster**: 12 mechanical unit/structure classes across **Tech Levels 1–6**, featuring decoupled 360-degree turret tracking, per-vehicle field upgrades (*"Scanning Vehicle — Upgrade Launched"*), and active **Long-Range Radar** piercing the Fog of War.
- **Continuous 3-Tier Camera Rig**: Smoothly interpolate along `z in [0.0, 1.0]` between **Tier 1 Satellite Strategic View (MSDF Tactical Icons)**, **Tier 2 Tactical 3D PBR View**, and **Tier 3 Action Close-Up Chase Cam**—plus a 1-click **1998 Retro CRT/Affine Mode**.
- **Two-Layer Utility AI & Special "Overpower: Orbital Director" Mode**: Battle 4 distinct AI Commander personalities (*Convoy Raider*, *Leapfrog Siege*, *Xenomorphic Swarm*, and *Obelisk Archon*) across Precursor Teleporters, Charged Ground conduits, and the 60-second Superweapon Obelisk race.
- **Autonomous Headless Browser E2E Swim Suite (`tests/e2e_headless_swim.py`)**: Verifies all 9 screens across 3 mobile/tablet viewports, economy/combat loops, 20,000-tick AI-vs-AI soak tests, and 4 visual camera modes via `window.__QA_BRIDGE__`.

## Playing it / Deploying
The whole game is one self-contained `index.html` (no build step). It deploys to Vercel as a static site using `vercel.json` (no framework, no build, output directory `.`).

- **Locally:** `npx serve .` then open http://localhost:3000
- **Vercel:** import this repo at https://vercel.com/new, leave Framework Preset as "Other", and deploy. Every push to `main` redeploys.

The original design spec is in `docs/Armor_Command_1998_Mobile_Rebuild_SOR.pdf`.
