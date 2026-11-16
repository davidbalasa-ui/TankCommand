# Unit promo clips

One ~6 second Blender clip per entity (54 clips), each a small combat or work story with a moving
camera. See `CHECKLIST.md` for the list and `briefs/<id>.md` for each clip's brief.

- `entities.py`: master list + briefs (regenerates `briefs/` and `CHECKLIST.md`). Status in `status.json`.
- `models.json`: model NAME -> file. Scripts only ever use names, so remodels only need a re-render.
  Lookup order: `$PROMO_MODELS`, `/mnt/project-files/promos/models`, `public/assets/models`.
- `promo_kit.py`: shared toolkit (environment, model loading, camera, weapons, effects, unfold, render).
- `scenes/<id>.py`: one script per clip. `scenes/terran_bastion.py` is the reference example.

## Running

Blender is the pip `bpy` module (5.3): `python3 -m venv /home/user/artenv/venv && /home/user/artenv/venv/bin/pip install bpy`.

```
PY=/home/user/artenv/venv/bin/python
$PY tools/promos/scenes/<id>.py --quality preview --frames 1,24,48,72,96,120,144 --out /tmp/x   # key stills sheet (fast)
$PY tools/promos/scenes/<id>.py --quality preview --out /tmp/x                                   # whole clip, 640x360, every 2nd frame
$PY tools/promos/scenes/<id>.py --quality final                                                  # 1280x720, ~10 s/frame
```
Finals land in `/mnt/project-files/promos/clips/<id>/` (`<id>.mp4`, a contact sheet and the `.blend`).

## Kit cheat sheet

```python
P = Promo('clip_id', seconds=6.0)
P.env("desert"|"highland"|"alien"|"dusk"|"ash", sun=(tilt_from_vertical_deg, 0, azimuth_deg), clear=[(x,y,r)], props=35,
      deposits=[('ore', (x, y), scale)])
P.flatten(x, y, r)                      # keep the action area flat
P.space(planet=(x, y, z, r, rgb))       # space scenes instead of env()
a = P.load('lancer', at=(x, y), heading=deg, label='lancer1')   # names from models.json
b = P.copy(a, at=(x, y), heading=deg)  # cheap extra instance
a.path([(t, (x, y)), ...])             # drive; faces travel direction. z=... or (x,y,z) for air; bank=, pitch=True
a.hover_bob(amp, hz)                    # hover units
a.split_barrels(); a.aim(t, target); a.fire(t, target, kind='cannon'|'heavy'|'autocannon'|'laser'|'missile'|'shell'|'lightning'|'beam'|'bomb')
a.recoil(t, collapse=0.8, kick=deg)
a.destroy(t)                            # explosion + charred smoking wreck
a.spin('DrumPivot', deg_per_s, t0, t1) # named pivots: TurretPivot, DrumPivot, GrinderPivot, BladesPivot, FanFLPivot, Wheel0LPivot, ...
s.unfold(t0, t1)                        # structures: packed pose -> deployed (from the glTF extras)
a.appear(t); a.vanish(t)
P.camera([(t, cam_pos, look_at_point_or_actor, lens), ...], shake=0.02)
P.orbit(center, radius, height, deg0, deg1, t0, t1, lens, radius1=, height1=)
P.cam_shake(t, amount)
P.explosion(p, t, size); P.impact(p, t, size, color); P.lightning(p0, p1, t0, t1, color); P.beam(...)
P.missile(p0, p1, t0); P.projectile(p0, p1, t0, speed, color); P.puff(...); P.dust(actor, t0, t1)
P.shield_dome(center, r, t0, t1, hits=[(t, p)])   # shields never shatter (gold colour = Arcadian honeycomb)
# promo_fx_weapons (bodies of the weapon effects above) also offers:
#   P.lightning(src, dst, t0, t1)  src/dst may be points, Actors, Objects or t->point callables (followed per frame)
#   W.lightning_thruster(P, actor, t0, t1, local=(-x, 0, 0), length=)   Arcadian thrust as crackling gold bolts
#   W.shield_push(P, shell, actor, t0, t1)   unit pushing out through a shield stretches it, then it snaps back
#   look-dev bench: FXCASE=<case> python tools/promos/fx/weapons_bench.py --quality preview --frames ...
P.render()
```
Colours: `promo_kit.COL` (terran_neon, arc_gold, repair_green, shard_violet, ...).
