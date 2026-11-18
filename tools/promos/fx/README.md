# Promo VFX flipbooks (work in progress)

`bake_fx.py` simulates and renders a small library of effects ONCE as RGBA PNG sequences.
Scenes are meant to play them back on camera-facing cards. Playback is not in `promo_kit.py` yet.

Output: `/mnt/project-files/promos/fx/<effect>/0001.png ...` (straight alpha, sRGB) and
`/mnt/project-files/promos/fx/manifest.json`. Each manifest entry holds `frames, fps, size [w,h],
extent` (metres across the image at size 1), `origin [u,v]` (where the effect's origin/ground contact
sits in the image, v measured from the bottom), `loop, kind, notes`. An effect is added to the
manifest only after its bake finishes.

```
PY=/home/user/artenv/venv/bin/python
$PY tools/promos/fx/bake_fx.py                         # whole library
$PY tools/promos/fx/bake_fx.py --only explo_ground_a   # one effect
$PY tools/promos/fx/bake_fx.py --only sparks --test    # 6 frames at half res -> fx/_test/
```

## Method
Mantaflow does not work in this pip bpy 5.3: the `LevelsetGrid` binding lost its `Grid<Real>`
base, so the solver script crashes on `setConst` and the type can't be patched. Instead, each effect
is a hand-written puff simulation. It handles drag, buoyancy from heat, cooling into soot, growth
and ground contact. Each puff is an icosphere with one shared Principled Volume shader. Its density
comes from a soft sphere eroded by 4D fBm noise, and the noise W is keyed so the puff boils. Its
emission comes from heat through a fire colour ramp, and soot darkens it. Per-puff state is set in the
Object Color: R heat, G density, B soot, A noise time. Cycles renders each frame to an EXR with
transparent film and an orthographic side view. The EXR is then converted to PNG, and glowing pixels
get their alpha from luminance so thin fire is not lost. Loops repeat their emission schedule with a
period equal to the loop length, and the render covers one period after a warm-up.

## Effects (LIB in bake_fx.py)
| name | frames | what |
|---|---|---|
| explo_ground_a / _b | 48 | ground blast: fireball rolling up into dark smoke, plus a dust skirt |
| explo_air | 40 | spherical air burst into smoke (no ground) |
| explo_small | 28 | small hit: fire pop and dirt |
| smoke_plume | 48 loop | rising dark smoke column |
| fire_loop | 32 loop | burning wreck flames |
| dust_burst / dust_ring | 32 | tan dust burst / outward ground ring |
| muzzle_a/b/c | 4 | Terran orange muzzle flash, side view pointing +X (play on an axis-locked card) |
| muzzle_blue | 4 | laser muzzle flash |
| flash_star | 6 | orange radial star flash (barrel seen head-on) |
| impact_flash | 6 | near-neutral white-hot star flash, for tinting (gold/cyan beam hits) |
| sparks | 16 | near-neutral spark streak burst, for tinting |

Status: only `explo_ground_a` has been tuned and judged good. Its fireball reads as real at 384 px,
about 3 s per frame. The bake was stopped after 13 of 48 frames. The other effects are coded but
not yet baked or tuned.
