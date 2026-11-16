"""Lancer (Terran light tank): the workhorse, in numbers.

Two Lancers advance through broken ground toward an Arcadian Lumen hovering across the flat.
Both fire on the move, each on its own ~1.8 s reload, staggered so the pair keeps up a steady
beat. The Lumen answers with gold lightning: the lead Lancer takes the hit, rocks hard, smokes,
and keeps rolling. Its next shot finishes the Lumen, and the pair (with a third Lancer coming
up behind) roll on past the burning wreck.

Models are used by name only (lancer, lumen), so remodels just need a re-render."""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_lancer', seconds=6.0)
FPS = P.fps

# The action corridor runs along +X; the fight closes from ~30 m to ~15 m.
CORRIDOR = [(-30, 3, 9), (-18, 3, 9), (-6, 3, 9), (6, 4, 9), (16, 5, 8), (22, 7, 7), (27, 9, 7)]
P.env('ash', sun=(60, 0, -140), sun_energy=4.4, clear=CORRIDOR, props=44)
for x, y, r in CORRIDOR:
    P.flatten(x, y, r - 1.5)

LUMEN_Z = 1.0


def lancer(label, at, heading):
    a = P.load('lancer', at=at, heading=heading, label=label)
    # the kit's barrel-split heuristic is tuned for single thin barrels; retry looser so the
    # barrel always collapses on recoil whatever the current lancer model looks like
    a.split_barrels() or a.split_barrels(max_frac=0.6, thin=0.65)
    return a


# broken ground: rocks hugging the corridor (foreground parallax, cover the tanks weave past)
ROCKS = [('boulder', (-17.5, -5.5), 0.8), ('rock_cluster', (-2.5, -10.5), 0.8), ('boulder', (5.5, -3.6), 0.6),
         ('rock_cluster', (-12.0, 9.5), 1.0), ('boulder', (2.0, 11.0), 1.1), ('rock_cluster', (15.0, -12.0), 0.7),
         ('boulder', (17.0, 12.5), 0.9), ('rock_cluster', (24.0, 3.0), 0.7), ('boulder', (-24.0, -1.5), 1.0)]
for i, (kd, at, k) in enumerate(ROCKS):
    r_ = P.load(kd, at=at, heading=i * 67, size=K.resolve(kd)['size'] * k, label=f'rock{i}')
    r_.root.location.z = -0.15

# --------------------------------------------------------------------------------- cast
# (paths run a key past the clip end so nobody brakes on the last frame)
A = lancer('lancerA', (-14, 0), 3)        # hero, lead tank (nearest the camera)
B = lancer('lancerB', (-17.5, 4.6), 3)    # wingman, a little behind and to the left
C = lancer('lancerC', (-34, 3.0), 2)      # third tank, coming up late (end frame)
A.path([(0.0, (-14, 0.0)), (2.0, (-6.6, 0.4)), (4.0, (0.8, 1.0)), (6.0, (13.0, 2.4)), (7.0, (19.5, 2.8))])   # surges on after the kill
B.path([(0.0, (-17.5, 4.6)), (2.0, (-10.2, 5.0)), (4.0, (-2.9, 5.6)), (6.0, (7.6, 7.2)), (7.0, (13.0, 7.8))])
C.path([(0.0, (-34, 3.0)), (3.0, (-23, 3.0)), (6.0, (-12.0, 3.2)), (7.0, (-8.3, 3.3))])
for a in (A, B, C):
    P.dust(a, 0.0, 6.0, every=0.14, size=0.6)

L = P.load('lumen', at=(22, 6), heading=190, label='lumen')
L.path([(0.0, (19.4, 4.2), 195), (2.0, (18.9, 4.7), 192), (4.0, (18.5, 5.1), 190),
        (6.0, (18.2, 5.4), 188)], z=LUMEN_Z, face=False)
L.hover_bob(0.1, 0.8)


def lifter_crackle(a, t0, t1, every=0.4):
    """Arcadian lifters: short gold arcs flicking from the hull down to the ground."""
    t = t0
    while t < t1:
        p = a.pos_at(t)
        side = 1 if int(t / every) % 2 else -1
        off = Vector((P.rnd.uniform(-0.8, 0.6), side * 0.75, 0.3))
        P.lightning(p + off, Vector((p.x + off.x * 1.2, p.y + off.y * 1.4, 0.02)), t, t + 0.08,
                    width=0.02, jag=0.35, branches=0, segs=5, glow=False)
        t += every


# --------------------------------------------------------------------------------- helpers
def rock(actor, t, roll=9.0, pitch=4.0, settle=0.7):
    """A hard hit: the hull rocks over onto its suspension and settles, keeps driving."""
    m = actor.model_root
    m.rotation_mode = 'XYZ'
    f = P.T(t)
    m.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    m.rotation_euler.x = math.radians(roll)
    m.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    m.rotation_euler.x = math.radians(-roll * 0.45)
    m.keyframe_insert('rotation_euler', index=0, frame=f + 2 + FPS * settle * 0.35)
    m.rotation_euler.x = math.radians(roll * 0.15)
    m.keyframe_insert('rotation_euler', index=0, frame=f + 2 + FPS * settle * 0.65)
    m.rotation_euler.x = 0
    m.keyframe_insert('rotation_euler', index=0, frame=f + 2 + FPS * settle)


def flinch(actor, t, amt=6.0):
    m = actor.model_root
    m.rotation_mode = 'XYZ'
    f = P.T(t)
    m.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    m.rotation_euler.x = math.radians(amt)
    m.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    m.rotation_euler.x = math.radians(-amt * 0.4)
    m.keyframe_insert('rotation_euler', index=0, frame=f + 7)
    m.rotation_euler.x = 0
    m.keyframe_insert('rotation_euler', index=0, frame=f + 12)


def shoot(actor, t, target, aim_dur=0.4, **kw):
    actor.aim(t, target, dur=aim_dur)
    return actor.fire(t, target, kind='cannon', **kw)


# --------------------------------------------------------------------------------- the fight
# Each Lancer on its own ~1.8 s reload, staggered so the pair keeps a steady beat:
#   A: 0.6, 2.4 (fires straight through the hit), 4.2 (the kill)    B: 1.5, 3.3
A.turret_yaw([(0.0, 6)])
B.turret_yaw([(0.0, 4)])
C.turret_yaw([(0.0, 0)])

# A's first round lands just short of the Lumen: kicks dirt under it
th = shoot(A, 0.6, (17.6, 3.4, 0.05), aim_dur=0.5)
flinch(L, th, 3)
# B connects: the Lumen jolts
th = shoot(B, 1.5, L, aim_dur=0.6)
flinch(L, th, 7)

# The Lumen answers: gold lightning into the lead Lancer, which rocks and keeps going
T_ZAP = 2.1
L.split_barrels()
L.aim(T_ZAP, A, dur=0.45)
L.fire(T_ZAP, A, kind='lightning', size=2.0, kick=2.5)
rock(A, T_ZAP + 0.02)
P.cam_shake(T_ZAP + 0.02, 0.12, 0.35)
# smoulder from the hit point for a while (it is hurt, not stopped)
for k in range(12):
    tk = T_ZAP + 0.15 + k * 0.3
    P.puff(A.pos_at(tk) + Vector((-0.4, 0.5, 1.3)), tk, size=0.45, n=1, rise=1.0, life=1.2,
           color=(0.22, 0.21, 0.2), opacity=0.35)

th = shoot(A, 2.4, L, aim_dur=0.3)
flinch(L, th, 6)
th = shoot(B, 3.3, L, aim_dur=0.3)
flinch(L, th, 6)

# Lumen's second bolt goes wide, into the dirt in front of the wingman
MISS = (-1.0, 4.0, 0.0)
L.aim(3.7, MISS, dur=0.35)
L.fire(3.7, MISS, kind='lightning', size=1.6, kick=2.5)

# The finisher
T_KILL_SHOT = 4.2
th = shoot(A, T_KILL_SHOT, L, aim_dur=0.3, size=1.15)
T_KILL = th
L.destroy(th, size=2.6)
P.cam_shake(th, 0.06, 0.4)
lifter_crackle(L, 0.1, th - 0.05)
# the Lumen hovered: drop its wreck to the dirt
wreck = bpy.data.objects.get(L.name + '_Wreck')
if wreck:
    z0 = wreck.location.z
    wreck.keyframe_insert('location', index=2, frame=P.T(th) + 1)
    wreck.location.z = -0.1
    wreck.keyframe_insert('location', index=2, frame=P.T(th + 0.3))
    wreck.location.z = z0
    K.set_interp(wreck, 'BEZIER')

# after the kill the turrets swing back to the front: job done, keep rolling
A.turret_yaw([(T_KILL + 0.5, 15), (T_KILL + 1.2, 0)])
B.aim(T_KILL + 0.3, L.pos_at(T_KILL), dur=0.6)
B.turret_yaw([(T_KILL + 1.4, 0)])

# --------------------------------------------------------------------------------- camera
CUT1 = 2.0
CUT2 = 5.0
P.camera([
    # shot 1: low, just ahead and right of the pair as they roll at us; A's first round goes
    # past, B fires; we pan with them as they pass
    (0.0, (-5.0, -3.6, 1.1), (-15.0, 2.4, 1.0), 40),
    (1.0, (-3.8, -4.2, 1.1), (-12.0, 2.6, 1.0), 38),
    (CUT1 - 1 / FPS, (-2.8, -4.8, 1.05), (-8.8, 2.8, 1.0), 34),
    # shot 2: behind A's right shoulder, Lumen across the flat: the bolt crosses the frame, A
    # rocks, keeps going, and the dolly settles in tight behind it, lens longer, for the kill
    (CUT1, (-14.5, -6.0, 1.9), (5.0, 3.6, 1.4), 32),
    (3.2, (-9.0, -4.4, 2.0), (10.0, 4.8, 1.4), 36),
    (CUT2 - 1 / FPS, (-5.0, -2.2, 2.2), (16.0, 6.6, 1.3), 46),
    # shot 3: low and close beside the lead tank, panning with it to reveal the burning wreck
    (CUT2, (9.6, -5.6, 0.6), (6.2, 5.9, 1.3), 25),
    (6.0, (15.8, -5.8, 0.55), (13.8, 6.0, 1.3), 26),
], shake=0.025, cuts=[CUT1, CUT2])

P.render()
