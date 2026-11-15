# Gameplay specification

The complete gameplay rules for the rebuild. Anything not written here is not a requirement; anything written here must be built and proven by a test.

## How to read this spec

Public written detail on the 1998 game is thin: reviews and encyclopedia entries describe its systems, but no full unit list or stat tables are published online. So every rule here carries one of four labels, and Stage 0 must settle every Measure item before Stage 1 starts. | Label | Meaning | What happens in Stage 0 | Confirmed | Stated in a published source (see Sources) | Keep as written | Rev 3 | From the Rev 3 SOR, which cites original missions and gameplay videos but wasn't independently checked | Check against gameplay video; keep, fix or drop | Measure | Behaviour known, exact numbers unknown | Time it from gameplay video and manuals; record in the unit data sheet | New | A deliberate rebuild decision, not from the original | Keep unless you overrule it

Where the original and this spec disagree after Stage 0, the original wins for gameplay and this spec is updated.

## Factions

Two playable sides with near-identical gameplay and very different looks. Confirmed

Humans (United Terran Federation in the original). Futuristic but recognisable armour, per the art direction.

Aliens (the Vrass Empire in the original). A slaver empire that arrives through a wormhole. Fully sci-fi, organic look.

Symmetry. Both sides share the same economy, drop system, research structure and unit roles. Differences are cosmetic plus a small number of signature units. Confirmed

Signature units. The Vrass have flying saucers that are strong against both ground and air targets. Confirmed. Any other faction-unique units and stat differences: Measure.

Faction traits. The Rev 3 build gave the aliens passive hull regeneration. That isn't in any source, so it's dropped unless Stage 0 finds it in the original.

Setting. Year 2910 onward; most fighting is on planet surfaces because a nebula prevents large fleets from manoeuvring. Confirmed

## Match flow, victory and defeat

A match ends only when the game detects a win or loss condition; no menu button ends a match with a result.

Start. Each side begins with a starting force defined by the mission or skirmish settings: usually a Landing Pad, some ore and metal, and a few units. Measure per mission.

Build-up. Players mine, buy drops, research and build defences.

Conflict. Raids on supply lines, pushes on bases, defence of pads.

End. Checked every tick:

Campaign missions: win when every primary objective is complete; lose when any failure condition triggers (for example, a protected unit dies or a timer runs out). Objectives are per mission. Confirmed that missions have distinct objectives; specifics Measure.

Skirmish: a side is eliminated when it has no Landing Pads and no units able to fight or build a new pad. Last side standing wins. New (exact original rule: Measure).

Results screen. Shows the outcome, time taken, units built and lost, resources gathered, and the mission's next step (next mission, retry, or campaign branch).

Required tests: destroying the last enemy pad and units triggers victory; losing your own triggers defeat; each mission's objectives can be both completed and failed.

## Orbital drops and Landing Pads

An unseen orbiting fleet beams units, structures and supplies down to Landing Pads, which act as each side's headquarters. Confirmed

Buying. The player picks an item from the build menu. The full cost is deducted at order time; if the player can't afford it, the order is refused with a clear message. Nothing is ever free or partly paid.

Queue. Orders join a queue with a delivery time per item (Measure). The queue shows progress and can be cancelled for a full refund before delivery. New (refund rule Measure).

Delivery. The item beams down onto a chosen pad with a visible drop effect. Units appear beside the pad; structure kits appear ready to place (see Structures).

Pads required. With no pad left, nothing can be delivered. Rev 3. Whether a pad can itself be ordered with no pad (for example a free emergency drop) is Measure; without it, losing every pad is fatal in skirmish.

Multiple pads. A side may build extra pads to act as forward drop points. The player chooses which pad receives each drop; the default is the last one used. Rev 3 proposed a 15% faster delivery per extra pad, up to 3: Rev 3, check in Stage 0.

Pads as targets. Pads have high hit points and are the main objective of most attacks.

## Economy

Two resources, both mined on the map by worker units, and every unit of income has to physically travel, so supply lines can be attacked. Confirmed that there are two resources and specialised mining units. One source (Giant Bomb) names only ore, so Stage 0 must confirm metal from gameplay.

Ore (general currency)

Found in fixed deposits on the map, each with a finite amount. Deposits empty and stay empty. Rev 3 (finite deposits); amounts Measure.

Mined by a mobile miner unit. Ore is credited when the load reaches a pad, not while digging. New: the Rev 3 build credited ore twice, at the deposit and on delivery.

Miners can be packed up and moved to a new deposit. Confirmed. When a deposit runs dry, the miner dismantles for a salvage refund. Rev 3 (refund amount Measure).

Metal (advanced currency)

Used for upgrades, research and higher-tier units. Confirmed.

Extracted by a stationary mining station built on a metal deposit. A tug unit carries containers from the station to the nearest pad. Rev 3: check against gameplay video.

Destroying a tug loses the load it carries. Destroying the station stops income from that deposit.

Rules for both

Mining rate, load size and travel speed: Measure.

Income never comes from nowhere. Mission scripts may grant resources, but only as a visible, scripted event.

The HUD shows current ore and metal plus active miners and tugs.

Required tests: income stops when every miner and tug is dead; a deposit reaches zero and stays empty; resources never go negative.

## Research, tech levels and per-unit upgrades

Research unlocks new units and weapons for the whole side, and individual vehicles can be upgraded in the field. Confirmed

Research tree. Paid with metal (and ore where the original does). Each step takes time and unlocks specific units, weapons or structures. Rev 3 modelled this as 6 tech levels; whether the original uses levels or a branching tree, and its exact contents, is Measure.

Gating. A locked item is visible but greyed out in the build menu, with what unlocks it. Locked items can't be ordered.

Per-unit upgrades. Applied to one selected vehicle, for a cost. Upgrade types are fire rate, armour and stealth. Confirmed. Effect sizes and costs: Measure. Rev 3 named a "Scanning Vehicle — Upgrade Launched" message: Rev 3, check its exact meaning.

Visibility. An upgraded vehicle shows it, with a badge in the HUD and a visible change on the model where practical.

Campaign carry-over. Whether research persists between campaign missions or each mission sets its own tech: Measure.

Required tests: a locked unit can't be bought; research can't be paid for without enough metal; an upgrade changes only the chosen vehicle.

## Structures, placement, pack and relocate

Structures can go on any clear ground, with no power grid or build radius, and defences can be packed up and moved to the front. Confirmed

Placement. After delivery, the player places a structure on any spot that is clear, flat enough and inside the map. A ghost preview shows green when valid and red when blocked, with the reason. Placement on cliffs, water, units, other structures or outside the map is refused.

Placement range. Whether placement must be near a pad or inside known territory: Measure. Default: anywhere the player has explored. New

Structure types. At least: Landing Pad, metal mining station, fixed gun batteries (turrets), radar towers and an air base (heli-pad). Confirmed for turrets, radar towers and heli-pad; the full list is Measure.

Pack and relocate. Turrets (fixed gun batteries) and miners can be packed up, driven or carried elsewhere and redeployed. Confirmed. Packing takes time and the unit is vulnerable meanwhile; timing Measure (Rev 3: 4 seconds).

Sell or dismantle. A structure can be dismantled for a partial refund. Rev 3 set 70%: Rev 3, check. A structure under fire can still be dismantled; the refund is lost if it dies first.

Damage states. Structures show light, heavy and critical damage and a destruction effect, and leave rubble that blocks placement until cleared or for a set time (New).

Required tests: invalid placement is refused in every listed case; pack, move and redeploy works and keeps the turret's upgrades; the refund equals the stated percentage exactly.

## Unit roster and data sheet

All units are vehicles or aircraft; there is no infantry, and most units fire while moving. Confirmed. The roster below lists the roles known so far; Stage 0 produces the exact list per faction from gameplay video and records every unit in the data sheet. | Role | Type | Source | Notes | Landing Pad | Structure | Confirmed | Headquarters and drop point | Ore miner | Ground, worker | Confirmed | Can pack up and move | Metal mining station + tug | Structure + ground worker | Rev 3 | Tug hauls metal to a pad | Scout | Ground, light | Confirmed | Cheap; used on point to draw fire | Light tank | Ground | Rev 3 | Main early combat unit | Missile tank (light and heavy) | Ground | Rev 3 | Long range; hits air | Heavy tank | Ground | Rev 3 | Front-line armour | Artillery | Ground | Rev 3 | Very long range; can't fire on the move | Mobile radar | Ground, support | Rev 3 | Extends vision | Repair vehicle | Ground, support | Rev 3 | Repairs nearby friendly units | Fixed gun battery (turret) | Structure | Confirmed | Can pack and relocate | Radar tower | Structure | Confirmed | Reveals through fog | Air base (heli-pad) | Structure | Confirmed | Launches and rearms aircraft | Fighter | Air | Confirmed | Launched from the air base | Bomber | Air | Confirmed | Launched from the air base | Flying saucer (aliens) | Air | Confirmed | Strong against ground and air

Data sheet fields (one row per unit, per faction). Name and faction; role; tech requirement; ore and metal cost; delivery time; hit points; armour; speed (top, acceleration, turn rate); turret turn rate; weapon(s) with damage, range, reload, projectile speed, accuracy, splash radius and valid targets (ground, air, structure); fire-on-the-move yes or no; sight range and sensor range; special abilities; available upgrades; carry capacity for workers; model and animation list. Every field is filled before Stage 2 ends, each with its source (video timestamp, manual page, or "tuned").

## Combat model

Combat is real-time, vehicle against vehicle, with turrets that aim independently of the hull so most units can fight on the move. Confirmed

Targeting. Units auto-engage the nearest valid enemy in range unless given a target. A player-assigned target is kept until it dies, leaves vision, or a new order is given. Priority rules for auto-targeting (threats over workers, for example): Measure.

Aiming. Turrets rotate at a set turn rate and fire only once on target. Hulls keep following their movement order.

Projectiles. Shots travel at a set speed and can miss: a moving target can outrun a slow shell, and shots can hit terrain. Splash weapons damage everything in their radius, including friendly units. Friendly fire on or off: Measure.

Line of sight. Direct-fire weapons need a clear line to the target; hills and structures block it. Artillery and missiles may fire over obstacles at targets someone on the side can see.

Damage. Damage minus armour, with a minimum per hit. Hit points can't go below zero; at zero the unit or structure is destroyed, with a death effect and a wreck that fades after a set time.

Veterancy. None unless Stage 0 finds it in the original.

Repair. Repair vehicles restore hit points to nearby friendly units over time. Whether pads or other structures also repair: Measure.

Stealth. Units with the stealth upgrade can't be seen beyond a reduced range. Exact rule: Measure.

Required tests: each weapon's damage, range and reload match its data sheet; a unit behind a hill can't be hit by direct fire; splash hits every unit in its radius; nothing has negative hit points.

## Air units and air bases

Aircraft launch from an air base (heli-pad), fly a mission, and return to that base to rearm. Enemies can follow returning aircraft home, so careless launches reveal your base. Confirmed

Launch. The player orders an aircraft to attack a target or patrol an area. It takes off from its base and flies directly, ignoring terrain and ground hazards.

Ammunition and return. Fighters and bombers carry limited ammunition (Measure) and fly home automatically when empty, then rearm over time. If their base is destroyed, they divert to another friendly base; with none left, they're lost when fuel or ammunition runs out (New).

Being tracked. Returning aircraft can be seen and followed; nothing hides the flight path. Confirmed

Air versus ground. Only weapons marked "air" in the data sheet can hit aircraft. Bombers hit ground targets only. Fighters hit air targets (and ground: Measure).

Alien saucers. Hit both ground and air hard. Whether they rearm at a base like other aircraft: Measure.

Air units on the ground. Aircraft sitting on their base can be hit by ground weapons.

Required tests: an aircraft with no ammunition returns home; a destroyed base re-routes or loses its aircraft; ground-only weapons never hit aircraft.

## Movement, pathfinding, groups and waypoints

Units follow player-drawn paths and waypoints, move as groups, and find their own way around obstacles. Confirmed for paths, waypoints and groups.

Pathfinding. Every ground unit finds a route to any reachable point around cliffs, water, structures and other units. If the point is unreachable, it goes to the nearest reachable spot and the player is told. Units never stop permanently stuck; a unit that hasn't moved for a set time while ordered to move re-plans its route.

Map edges. Units can't leave the map. Orders outside it are clamped to the nearest valid point inside. Camera panning stops at the map edge. Nothing can be spawned, dropped or placed outside it.

Collision. Units don't overlap each other or structures. Groups spread out at the destination instead of piling onto one spot.

Waypoints. The player can queue several waypoints; the unit follows them in order. Confirmed. Patrol between points: Measure.

Groups. Units can be joined into or split from groups, and a group moves together at the speed of its slowest member. Confirmed for joining and splitting; shared speed New.

Formations. The player can set group formations (for example, scouts on point to draw fire). Confirmed that formations matter tactically; the list of formation shapes is Measure.

Stances. Hold position (fire but don't move), return fire, and attack-move. New unless the original has them.

Hover and air. Hover units cross water and hazards that stop tracked vehicles (Rev 3). Aircraft ignore terrain.

Required tests: a unit reaches every reachable point on every map; a unit ordered off the map stops at its edge; no unit stays stuck for more than the re-plan time across 1,000 AI-vs-AI matches.

## Vision: fog of war, sensors and radar

Players see only what their units and radar can see, and distant contacts show as anonymous symbols until something gets close enough to identify them. Confirmed

Three states per map area: unexplored (black), explored but not currently seen (terrain and last-known structures shown, no units), and visible (everything shown, live).

Sight range. Each unit and structure reveals a circle around it, blocked by hills. Values per unit: Measure.

Sensor range. Beyond sight but inside sensor range, enemy units show as symbols with no type. Confirmed. Moving within sight range reveals their type.

Radar. Radar towers and mobile radar units extend sensor range. Confirmed.

Information hiding. Nothing about hidden enemies is drawn, shown on the minimap, or exposed through hover text. The AI follows the same rules: it can't see through fog. New

Stealth. Stealth-upgraded units are hidden from sensors and seen only at a reduced sight range (Measure).

Required tests: a hidden enemy is never drawn or listed anywhere in the UI; the AI's decisions use only what its units can see.

## Terrain and map features

Maps are 3D landscapes with height, and terrain shapes routes, sight lines and where bases can go.

Height. Hills, ridges, valleys and cliffs. Cliffs are impassable to ground units; slopes slow them (Measure). High ground extends sight range (New unless the original has it).

Surfaces. Ground, water (passable only to hover and air units) and any special surfaces the original uses (Measure).

Resource sites. Ore and metal deposits at fixed spots per map.

Map size. Per map, from the original where measurable. A fixed square play area with a hard edge.

Precursor features (Rev 3, check every one). The Rev 3 SOR cites these from specific original missions:

Teleporter pairs that move units between linked points (cited to VS Mission 11).

"Charged ground" that damages tracked units but not hover units.

Caves holding artifacts that a radar or probe unit can find (cited to UTF Mission 9).

A central obelisk superweapon with a 60-second countdown, used as a mission objective. Each one is built only if Stage 0 finds it in gameplay video; otherwise it's dropped. The Rev 3 build's always-on 60-second obelisk that damaged only the enemy is dropped.

Map content. The original's campaign maps are rebuilt by layout and feature placement from gameplay video (Measure); skirmish maps can be new (New).

Required tests: every map's start positions can reach each other by ground (unless a mission is designed otherwise); every resource site is reachable.

## Enemy AI

The enemy plays by exactly the same rules as the player: it earns, pays for every drop, researches, scouts and fights with no hidden bonuses at normal difficulty. Reviewers rated the original's AI average and aggressive, so the rebuild should be at least as competent. Confirmed (rating); New (no-cheat rule).

Same interface. The AI issues orders through the same command channel as the player. It can't create units, money or vision.

Strategic layer (every few seconds): keep miners and tugs working; spend on research; build and move turrets to cover supply lines and pads; scout with cheap units and radar; assemble mixed attack groups and pick targets (supply lines, radar, pads).

Tactical layer (every tick): focus fire on weak targets, keep range advantage, pull back badly damaged units toward repair, avoid hazards, defend workers under attack.

Difficulty. Easy, normal, hard. Easy reacts slower and builds less; hard plays faster and smarter. Any resource bonus on hard is shown openly in the settings.

Mission AI. Campaign missions can script enemy behaviour (waves, defend a point, escort) on top of the general AI.

Personalities (New, optional). Rev 3 proposed four named AI personalities (Convoy Raider, Leapfrog Siege, Swarm, Obelisk Archon) as a skirmish extra. Build them only after the core AI passes its gate.

Required tests: AI spending never exceeds its income; across 1,000 AI-vs-AI matches every match ends with a winner within a time limit (Measure, default 45 minutes of game time); an AI with no pads and no units is declared eliminated.

## Campaigns and missions

Two separate campaigns, one per faction, with 22 missions each, plus training missions; each campaign has its own ending. Confirmed (Wikipedia gives five training missions; GameSpot gives 22 per side).

Training. Five tutorial missions that teach drops, mining, combat, research and air units in order.

Human campaign. Pushes the aliens back to the wormhole and destroys them, then studies the wormhole. Confirmed

Alien campaign. Ends with an invasion of Earth and the enslavement of its people. Confirmed

Optional missions. The original has optional side missions (for example "UTF Optional Mission 1: Encounter the Natives", seen in gameplay video). How they branch or unlock: Measure.

Known mission titles. "UTF Mission 1: Reclaim Utopia Base" and "VS Mission 1: Destroy Utopia Base", both from gameplay videos. Stage 0 records every mission's title, map, starting forces, objectives, failure conditions, triggers, timers, enemy behaviour and unlocks.

Mission scripting. A data-driven trigger system: conditions (time, area entered, unit destroyed, resource reached, objective done) and actions (spawn, message, reveal area, change objective, win, lose, grant). No mission logic in engine code.

Briefings and story. The original has full-motion cutscenes between missions. The rebuild uses briefing screens with text, a map preview, voice or captions, and static or simple animated art (New). Story text is rewritten if names are rebranded.

Progress. Completing a mission unlocks the next. Progress, difficulty and best results are saved. Any mission already reached can be replayed.

Required tests: every mission can be won and lost by an agent playtester; every trigger fires; no mission can get stuck with no way to win or lose.

## Skirmish mode

A standalone match against AI opponents on any skirmish map, standing in for the original's 2–4 player multiplayer until online play is added. New (the original's multiplayer maps and set-up choices are Confirmed).

Set-up options: map; your faction; 1–3 AI opponents, each with faction and difficulty; teams; starting resources (low, normal, high); starting units (pad only, or pad plus a small force); research limit; fog of war on or revealed.

Maps. At least 6 at launch, sized for 2 and 4 sides, including remakes of the original's multiplayer layouts where measurable.

Victory. Elimination of all enemy sides (see Match flow).

Online multiplayer. Out of scope; the deterministic simulation keeps it possible as a later stage.

## Controls and camera

Keep the original's commands but fix its controls and camera, which reviewers named as its biggest flaws. Confirmed (criticism). The rebuild uses modern RTS conventions on desktop and a designed-for-thumbs scheme on phones. New

What the original did (reference only). Left-click set a movement path, right-click picked a target, Ctrl+left-click added waypoints, Shift+right-click selected a vehicle, and Shift+left-click split or joined groups. Four views: high top-down, close top-down, low 3D and high 3D; in 3D the cursor steered the camera. The overhead map couldn't be clicked to jump, and resource and building control was keyboard-only. Confirmed

Mouse and keyboard (rebuild) | Input | Action | Left click on own unit | Select it (replaces selection) | Shift + left click on own unit | Add to or remove from selection | Left drag on ground | Box-select own units | Double-click own unit | Select all of that type on screen | Right click on ground | Move selection there | Right click on enemy | Attack that target | Right click on own damaged unit with repair unit selected | Repair it | Shift + right click | Queue a waypoint or order | A, then left click | Attack-move | H / S | Hold position / stop | Ctrl + 1–9 | Assign control group; 1–9 selects it; double-tap the number to centre the camera on it | Arrow keys, WASD, or cursor at screen edge | Pan camera | Middle-drag or Q / E | Rotate camera | Mouse wheel | Zoom, smoothly from close 3D to top-down strategic | Click or drag on minimap | Jump camera there; right click on minimap issues a move | Space | Jump to latest alert | B / build menu | Open orbital drop menu; hotkeys per item | Esc or P | Pause menu | F1 | Help and key list

Touch (phone and tablet) | Gesture | Action | Tap own unit | Select it | Tap ground or enemy with units selected | Move there or attack it | Double-tap own unit | Select all of that type on screen | Long-press then drag | Box-select | One-finger drag on ground | Pan camera | Two-finger pinch | Zoom | Two-finger twist | Rotate camera | Two-finger tap | Deselect all | Tap minimap | Jump camera | On-screen buttons | Attack-move, hold, stop, groups 1–5, build menu, pause

Camera rules. One smooth zoom from close 3D to strategic top-down (replacing the original's four fixed views). The camera never moves on its own unless the player taps an alert or a group's centre button. It stays inside the map bounds and never clips through terrain. At strategic zoom, units show as clear faction icons.

Rebinding. All keyboard bindings can be changed in Settings. Left-handed and right-handed touch layouts are available.

## HUD and information

The player must always be able to see their resources, what is selected, what is being built, and what needs attention, without the HUD covering the battlefield.

Resource bar. Ore, metal, active miners and tugs, research level, and unit count against the unit cap.

Minimap. Terrain, explored areas, own and visible enemy units, sensor symbols, pads, camera view outline, and pings for alerts.

Selection panel. For one unit: portrait, hit points, upgrades, weapons, current order. For a group: unit icons with health, clickable to narrow the selection.

Command panel. Context buttons for the selection: move, attack, attack-move, hold, stop, patrol, pack or deploy, dismantle, upgrade, repair, launch (aircraft).

Build menu. Every drop item grouped by type (the original grouped offensive and defensive units), with cost, delivery time, and locked state with its unlock requirement. Shows the queue and which pad receives drops.

Alerts. Short messages with a sound for: under attack (with location), unit lost, structure lost, pad lost, deposit empty, research done, drop arrived, objective updated, not enough resources. Tapping an alert jumps the camera there.

Objectives. The current mission's objectives with status, openable at any time.

Health bars. Over units when damaged, selected, or with a setting to always show.

Readability. Text at least 12 px on phones; no HUD element overlaps another at any supported screen size; touch targets at least 44 × 44 px.

Unit cap. A maximum unit count per side (Measure; Rev 3 used 200), shown in the HUD, with a clear message when reached.

## Game options, saving, pause and speed

Screens. Title, campaign select (with faction), mission select, briefing, skirmish set-up, loading, in-game, pause, settings, help, objectives, results (victory or defeat), credits, bug report.

Pause. Stops the simulation completely. Orders can't be given while paused (New; revisit if Stage 0 finds the original allowed it). Pauses automatically when the app goes to the background, a phone call arrives, or the Android back button is pressed.

Game speed. Slow, normal, fast in single-player.

Saving. Manual save and load anywhere in single-player, plus an autosave every few minutes and when the app is backgrounded. Loading a save restores the match exactly. Saves from older versions either load or show a clear "incompatible" message; they never crash the game.

Settings. Master, music, effects and voice volume; graphics quality (low, medium, high, auto); show health bars; edge-scroll on or off and speed; camera sensitivity; key rebinding; touch layout; text size; colour-blind faction colours; language (English at launch).

Exit and resume. Quitting mid-mission asks for confirmation and offers to save. Reopening the app offers to resume the last autosave.

Saves, backups and data (New). The game needs no accounts, no database and no game server.

Local storage. Saves, campaign progress and settings are written as files in the app's private storage through Capacitor's file and preferences plugins, not only in browser storage (localStorage or IndexedDB), so Android backup reliably includes them.

Android Auto Backup. Left on, so a player's saves are copied to their own Google Drive and restored when they reinstall or change phones. Total saved data stays well under Android's 25 MB backup limit (target under 5 MB; old autosaves are rotated out).

Web build. Saves stay in the browser, with export and import of a save file in Settings.

Cross-device sync. Out of scope. Google Play Games saved games can be added later without a database.

Server pieces. Only the bug-report endpoint, which stores nothing about players.

Required tests. Uninstall and reinstall with backup restore keeps campaign progress and saves; a backup restored from an older game version loads or is cleanly rejected; storage full is handled with a clear message.

## Audio and feedback

Every player action and important event gets a sound, so the game can be followed partly by ear.

Unit responses. A short acknowledgement when units are selected and given orders, varied so it doesn't repeat.

Weapons and effects. A distinct sound per weapon type, explosions scaled by size, the drop beam, mining, tug delivery, pack and deploy, aircraft launch and landing.

Alerts. Voice or clear tones for every alert in the HUD section.

Music. Faction-themed tracks for menus, calm play and combat, crossfading by situation.

Sources. Generated in code, made by agents, or taken from free libraries under the asset licensing rules, with credits recorded.

Haptics. Light vibration on phone for selection, orders and alerts, which can be turned off.

## Deliberate changes from the original

These depart from the 1998 game on purpose. Everything else follows the original. | Change | Why | Modern mouse, keyboard and touch controls; one smooth zoom instead of four fixed views | Reviewers named controls and camera as the original's main flaws | Clickable minimap and selection in every view | The original lacked both, which reviewers criticised | New 3D art and sound; possibly new names | Clean-room rule: no original assets; trademark question is open | Briefing screens instead of full-motion cutscenes | Can't be produced by agents at acceptable quality | Skirmish against AI instead of LAN or modem multiplayer | Multiplayer is a later stage | Phone and tablet support, autosave and pause on interruption | Play Store target | Rev 3 inventions (passive alien regeneration, always-on obelisk, free AI units) dropped unless found in the original | Not supported by any source

## Stage 0 research checklist

Stage 0 resolves every Rev 3 and Measure label in this tab. Each result goes into the repo (docs/research/) with its evidence: video link and timestamp, manual page, or screenshot. Where evidence is missing or conflicting, Fable makes the call, labels it Decided, and writes one line of reasoning.

Competitor and prior-art check first: search Google Play, Steam, itch.io, GitHub, mod sites and fan forums for any remake, fan project or close competitor (see the Launch plan tab). If an active, close remake exists, stop and report to David before any build work.

Collect gameplay videos covering both campaigns, training and multiplayer. Note any that can't be downloaded from the cloud sandbox. Find any surviving manual, strategy guide or FAQ text. Read only; never extract files from game copies.

Confirm whether metal exists as a second resource, and how it's mined and delivered.

List every unit and structure per faction, with role and what unlocks it.

Measure speeds, fire rates, ranges, mining rates, load sizes and delivery times from video, and fill the data sheet.

Record the research tree: levels or branches, costs, times, unlocks.

Record per-unit upgrade effects and costs (fire rate, armour, stealth).

Settle each Rev 3 item: tugs, pad scaling, deposit depletion and miner salvage, refund percentage, pack time, teleporters, charged ground, caves, obelisk.

Record every campaign and training mission: title, map layout, start forces, objectives, failures, triggers, branching, story beats.

Record air rules: ammunition, rearm, return behaviour, saucers.

Record skirmish victory rule and unit cap.

Pick the target Android phone and its performance budget.

Publish the finished data sheet and research notes; update this tab, replacing each label with the result.

## Sources

Checked 24 October 2026.

Armor Command — Wikipedia: factions, two resources, orbital drops via pads, no infantry, fire on the move, radar towers, 22 missions per side plus 5 training, endings, 4-player LAN or modem, camera views.

Armor Command Review — GameSpot: 22 missions per side, mouse controls, four camera views, packable miners and gun batteries, sensor symbols beyond detail range, average AI.

Armor Command — Old PC Gaming: placement anywhere without power-plant range, deconstructing defences to move forward, units grouped by type in the build menu.

Armor Command — Giant Bomb: research tree, per-unit upgrades (fire rate, armour, stealth); names only one resource.

Armor Command tips — Cheatbook: alien saucers, fighters and bombers from the heli-pad, aircraft tracked home, scouts on point.

UTF Mission 1: Reclaim Utopia Base — YouTube (jhzh), VS Mission 1: Destroy Utopia Base — YouTube, UTF Optional Mission 1: Encounter the Natives — YouTube: mission titles; primary material for Stage 0 measurement.

Rev 3 SOR (docs/Armor_Command_1998_Mobile_Rebuild_SOR.pdf in the repo): source of every Rev 3 label.
