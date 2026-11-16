# Promo clip worker instructions

You write ONE ~6 s Blender promo clip for the mobile RTS TankCommand. Your clip id is given to you.

Read first: tools/promos/README.md, tools/promos/briefs/<id>.md (brief + standing rules: obey every
rule), tools/promos/promo_kit.py (the API you use), and the finished sample scenes in
tools/promos/scenes/ (terran_bastion, terran_outrider, arcadian_dragonfly, arcadian_disc,
terran_landing_pad) for patterns: custom vehicle sims, gold bolts, aircraft orientation, break-apart,
dust waves, camera cuts. Reuse their ideas by copying helpers into your own script.

Write tools/promos/scenes/<id>.py (run from /home/user/TankCommand with
/home/user/artenv/venv/bin/python; bpy 5.3, already installed). Think as a director: what is this
thing FOR, and what 6 seconds show that best? A real little story with a moving camera, readable at
phone size, ending on a strong frame. Improve on the brief if you have a better idea within the rules.

Do AT LEAST 3 full refinement passes. Each pass: render key stills
  --quality preview --frames 1,18,36,54,72,90,108,126,144 --out /tmp/promo_work/<id>
Read the stills sheet and critique it hard, like a picky art director: hero big and readable? action
clear? effects good, or blobs/white blowouts? anything clipping, floating, cropped? camera purposeful?
end frame strong? Fix everything you find. After the last pass render one full preview
(--quality preview --out /tmp/promo_work/<id>) and check its contact sheet. A full preview takes
~10-15 min: run it in the background with a long timeout, or in two --frames ranges. NEVER render
--quality final (the orchestrator renders finals one at a time).

Effects lessons already learned: the render uses the Standard view transform, so emission strength
above ~2-4 clips colours to yellow/white: keep glows low and saturated. Arcadian gold is
(1.0, 0.5, 0.06). Smoke and dust: kit P.puff (soft) with light, low-opacity, smaller puffs; avoid big
dark balls. No white blob impacts.

Rules: do NOT edit promo_kit.py, models.json, entities.py, status.json or other workers' scenes; no
git. Several workers share 4 CPUs. Don't install anything. Name helper scripts carefully (a file
called inspect.py breaks the glTF importer).

Final report (short): the clip second by second, what each pass changed, paths of the final stills
sheet and preview mp4, honest remaining weaknesses, kit problems you hit.
