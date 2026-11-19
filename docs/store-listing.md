# Google Play store listing (draft)

First draft for the Play Console **Main store listing**. The store name is not final: the text
says "TankCommand" everywhere, and neither the icon nor the feature graphic has the name in it,
so a rename only touches this text.

Numbers were checked against the repo: `src/data/missions/campaign/` (22 `human_*` and 22
`alien_*` missions), `src/data/missions/training_*.json` (5 lessons),
`src/data/maps.placeholder.json` (7 skirmish maps; Crossfall and Fourfold Fen have four
start positions) and `src/data/fullGame.ts` (what is free).

## App name

TankCommand (working name, up to 30 characters)

## Short description (80 characters max)

> Command tanks, aircraft and alien hovercraft in a real-time strategy war.

(73 characters.)

## Full description (under 4000 characters)

> Two armies. One scorched frontier. You give the orders.
>
> TankCommand is a real-time strategy game built for your phone. Call in units by drop ship,
> mine ore and metal to pay for them, research new weapons and lead armoured columns, aircraft
> and artillery against an enemy who is doing exactly the same.
>
> TWO SIDES, TWO WAYS TO FIGHT
> • The Terrans: dark, heavily armoured tanks, long-barrelled guns, missile batteries and jets.
> • The Arcadians: hovering, curved silver-and-bronze craft with crescent fins and golden
>   lightning weapons.
> Each side has its own units, buildings and research.
>
> TWO CAMPAIGNS, 44 MISSIONS
> • A Terran campaign of 22 missions and an Arcadian campaign of 22 missions, each with its
>   own briefings and objectives.
> • 5 training lessons teach the basics step by step: drops, mining, combat, research and air
>   power.
>
> SKIRMISH
> • 7 skirmish maps, 2 of them for four sides.
> • Play against 1 or 2 AI opponents on Easy, Normal or Hard.
> • Choose your side, the AI's side, starting resources, starting force and fog of war.
>
> MADE FOR TOUCH
> • Tap a unit to select it, tap the ground to move, or select the whole army in one tap.
> • Control groups, waypoints, hold and attack orders, a minimap and a left-handed layout.
> • Adjustable graphics quality and text size, and a colour-blind option.
>
> FAIR TO PLAY
> • Offline single player: no account, no internet connection needed to play.
> • No ads.
> • Free to try: all 5 training lessons, the first 5 missions of each campaign and 2 skirmish
>   maps.
> • One in-app purchase, "Full game unlock", opens every mission and every skirmish map. It is
>   a one-time purchase, not a subscription, and it can be restored after a reinstall.

(About 1,600 characters, well under the 4,000 limit.)

## Category and tags

- **App or game:** Game
- **Category:** Strategy
- **Tags (pick up to 5 in Play Console):** Real-time strategy, Strategy, Tanks, Offline,
  Single player (alternatives: Sci-fi, War)

## Contact details

- Email: the address David uses in `public/privacy.html` (fill in before publishing)
- Website: `https://tankcommand.vercel.app/`
- Privacy policy: `https://tankcommand.vercel.app/privacy.html`

## Content rating note

For the IARC questionnaire (details in `docs/play-release.md` section 7):

- Violence: fantasy / unrealistic only. Tanks, aircraft and alien craft fire at and destroy each
  other, seen from a distance. No blood, no gore, no people shown being hurt.
- No sexual content, language, drugs, alcohol, tobacco or gambling.
- No user interaction, chat or sharing; no location sharing.
- Contains digital purchases (the one-time full game unlock).
- Expected outcome: a low rating (around PEGI 7 / ESRB Everyone 10+). Target audience: 13 and
  over, to stay out of the Families programme.

## Graphics

All files are in `store/` and are made by the project (re-render steps in `tools/branding/`).

| Play Console field | File | Size |
| --- | --- | --- |
| App icon | `store/icon-512.png` | 512 x 512, 32-bit PNG |
| Feature graphic | `store/feature-graphic.png` | 1024 x 500, no text |
| Phone screenshot 1 | `store/screenshot-1-battle.png` | 1920 x 1080 |
| Phone screenshot 2 | `store/screenshot-2-build-menu.png` | 1920 x 1080 |
| Phone screenshot 3 | `store/screenshot-3-briefing.png` | 1920 x 1080 |
| Phone screenshot 4 | `store/screenshot-4-skirmish-setup.png` | 1920 x 1080 |

Suggested screenshot captions, if captions are added later in an image editor:

1. Lead Terran armour against the Arcadians.
2. Call in tanks, aircraft and buildings by drop ship.
3. Two campaigns, 44 missions, each with its own briefing.
4. Skirmish on 7 maps against Easy, Normal or Hard AI.

### Re-rendering

```
npm ci
node tools/branding/render.mjs        # hero renders of the Bulwark and Aegis models
python3 tools/branding/compose.py     # app icons, adaptive layers, splash screens, web icons, feature graphic
VITE_TEST_HOOK=1 npm run build && npm run preview -- --host 127.0.0.1 --port 4255 --strictPort
node tools/branding/screenshots.mjs   # store screenshots (in a second terminal)
```
