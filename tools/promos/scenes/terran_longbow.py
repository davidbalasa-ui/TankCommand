"""Longbow (Terran artillery): one salvo, a hundred metres, three hits.

The Longbow sits dug in on a desert rise, barrel already up. It nudges its turret onto the
bearing and fires three blasts inside one second: each one slams the whole hull back and up,
the barrel slams 80% into the turret, a ring of dust jumps off the ground. The camera whips up
after the shells, then rides along beside them over the desert and lets them overtake it as
they drop onto a distant Arcadian outpost (Sentinel, Corona, Oracle, two Lumens): the three land
in a walking pattern, near to far, Lumen - Sentinel - Corona. The second Lumen bolts.
Hard cut back home: smoke on the horizon over the Longbow's shoulder while it starts the long
reload, barrel dropping to the loading angle, hold... and swinging back up to the sky.

Timeline (s): 0-0.45 traverse | 0.55 / 0.88 / 1.21 shots | 1.625 cut, ride with the shells |
~2.95 / 3.25 / 3.55 impacts (walking) | 4.25 cut back | 4.4-4.9 barrel down | 5.25-5.95 back up.

The hero is loaded by model NAME ('longbow'); the barrel axis and elevation are measured from
the split-off barrel mesh, so a remodel only needs a re-render."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import Promo  # noqa: E402

P = Promo('terran_longbow', seconds=6.0, seed=7)
FPS = P.fps

TX, TY = 100.0, 0.0           # target outpost centre
P.env('desert', sun=(58, 0, -55), sun_energy=4.2, props=45,
      clear=[(0, 0, 22), (TX, TY, 22), (-10, -6, 10), (28, 1, 9), (48, 1, 9), (68, 1, 9),
             (20, -4.5, 9), (40, -3, 9), (60, -1.8, 9), (80, -0.8, 9)])
P.flatten(0, 0, 10)
P.flatten(TX, TY, 18)


def cut_t(frame):
    """Time of a whole frame (cuts land on frames)."""
    return (frame - 1) / FPS


# --------------------------------------------------------------------------- the Longbow
lb = P.load('longbow', at=(0, 0), heading=-4)
lb.root.location.z = P.ground_z(0, 0) - 0.05
lb.split_barrels()
mz = lb.muzzle()                      # measured from the barrel while it is still in host space

# Re-hinge the barrel on its own axis so the 80% collapse slides ALONG the elevated barrel
# (the kit slides along the turret's local X) and so we can lower/raise it for the reload.
ELEV = 0.0
hinge = None
if lb.barrels:
    b = lb.barrels[0]
    host = b.parent
    co = [v.co.copy() for v in b.data.vertices]
    tip_x = max(c.x for c in co)
    root_x = min(c.x for c in co)
    span = tip_x - root_x
    tipv = [c for c in co if c.x > tip_x - 0.12 * span]
    rootv = [c for c in co if c.x < root_x + 0.12 * span]
    tc = sum(tipv, Vector()) / len(tipv)
    rc = sum(rootv, Vector()) / len(rootv)
    ELEV = math.atan2(tc.z - rc.z, tc.x - rc.x)
    hinge = K.empty('BarrelHinge')
    hinge.parent = host
    hinge.rotation_mode = 'XYZ'
    hinge.location = rc
    hinge.rotation_euler = (0, -ELEV, 0)
    bpy.context.view_layer.update()
    to_hinge = (Matrix.Translation(rc) @ Matrix.Rotation(-ELEV, 4, 'Y')).inverted()
    b.data.transform(to_hinge)
    b.parent = hinge
    b.matrix_parent_inverse = Matrix()
    b.location = (0, 0, 0)
    b.rotation_euler = (0, 0, 0)
    b['barrel_len'] = (tc - rc).length * 0.95
    # muzzle rides on the barrel hinge too
    mw = mz.matrix_world.copy()
    mz.parent = hinge
    mz.matrix_world = mw
    bpy.context.view_layer.update()
print('LONGBOW ELEV deg', math.degrees(ELEV))

# --------------------------------------------------------------------------- the outpost
def deployed(a):
    for o in [a.model_root] + list(a.model_root.children_recursive):
        if o.get('hideWhenDeployed'):
            o.hide_render = True
            o.hide_viewport = True
    # keep the folded carrier out of the charred wreck copy
    a.meshes = [m for m in a.meshes if not m.get('hideWhenDeployed')]
    return a


def on_ground(a, x, y, dz=0.0):
    a.root.location.z = P.ground_z(x, y) + dz
    return a


sentinel = on_ground(deployed(P.load('sentinel', at=(TX + 1.0, TY - 1.5), heading=180)), TX + 1.0, TY - 1.5)
corona = on_ground(deployed(P.load('corona', at=(TX + 7.0, TY + 3.5), heading=200)), TX + 7.0, TY + 3.5)
oracle = on_ground(deployed(P.load('oracle', at=(TX + 9.0, TY - 6.5), heading=160)), TX + 9.0, TY - 6.5)

lumen1 = P.load('lumen', at=(TX - 7.0, TY - 4.0), heading=170, label='lumen1')
lumen2 = P.load('lumen', at=(TX - 5.0, TY + 6.0), heading=190, label='lumen2')
for a, (x, y) in ((lumen1, (TX - 7.0, TY - 4.0)), (lumen2, (TX - 5.0, TY + 6.0))):
    a.root.location.z = P.ground_z(x, y) + 0.45
lumen1.path([(0.0, (TX - 6.0, TY - 4.6)), (3.0, (TX - 7.4, TY - 3.6))], z=P.ground_z(TX - 7, TY - 4) + 0.45)
lumen1.hover_bob(0.1, 0.9)
lumen2.path([(0.0, (TX - 4.0, TY + 6.4)), (3.3, (TX - 5.0, TY + 6.0)),
             (4.2, (TX - 0.5, TY + 11.0)), (6.0, (TX + 12.0, TY + 19.0))],
            z=P.ground_z(TX - 5, TY + 6) + 0.45)
lumen2.hover_bob(0.1, 1.1)
P.dust(lumen2, 3.4, 6.0, every=0.12, size=0.8)

# --------------------------------------------------------------------------- the salvo
T_SHOTS = [0.55, 0.88, 1.21]
T_HITS = [2.95, 3.25, 3.55]
HIT_PTS = [Vector((TX - 7.2, TY - 3.8, P.ground_z(TX - 7.2, TY - 3.8) + 0.6)),
           Vector((TX + 1.0, TY - 1.5, P.ground_z(TX + 1.0, TY - 1.5) + 0.8)),
           Vector((TX + 7.0, TY + 3.5, P.ground_z(TX + 7.0, TY + 3.5) + 1.0))]
VICTIMS = [lumen1, sentinel, corona]

# small traverse onto the bearing before the first shot
lb.turret_yaw([(0.0, 9.0), (0.12, 9.0)])
lb.aim(0.45, (TX + 0.5, TY, 1.0), dur=0.33)

SHELLS = []   # (t0, dur, p0, d, arc) to let the camera ride with them
for t0, th, p1, vic in zip(T_SHOTS, T_HITS, HIT_PTS, VICTIMS):
    p0 = lb.world_at(mz, t0)
    dist = (p1 - p0).length
    horiz = math.hypot(p1.x - p0.x, p1.y - p0.y)
    # launch slope matches the barrel: 4*arc/horiz = tan(elev) (with a floor for a real lob)
    arc = max(0.25 * horiz * math.tan(max(ELEV, math.radians(28))), 12.0)
    spd = dist / (th - t0)
    lb.fire(t0, p1, kind='shell', size=1.1, kick=10.0, speed=spd, arc=arc, impact=False)
    SHELLS.append((t0, th - t0, p0, p1 - p0, arc))
    P.cam_shake(t0, 0.09, 0.3)
    # blast ring of dust off the ground around the hull
    for k in range(7):
        ang = math.radians(-4 + 180 + (k - 3) * 32)
        r = 3.4
        P.puff((r * math.cos(ang) * 0.9 + 0.8, r * math.sin(ang), 0.25), t0 + 0.02, size=1.1, n=1,
               rise=0.7, life=1.1, color=(0.62, 0.5, 0.38), opacity=0.4)
    vic.destroy(th, size=3.2 if vic is not lumen1 else 2.6)
    P.smoke_column((p1.x, p1.y, P.ground_z(p1.x, p1.y)), th + 0.3, P.seconds, size=2.4, every=0.22)


def shell_pos(i, t):
    t0, dur, p0, d, arc = SHELLS[i]
    u = max(0.0, min(1.0, (t - t0) / dur))
    return p0 + d * u + Vector((0, 0, 4 * arc * u * (1 - u)))


# --------------------------------------------------------------------------- the long reload
if hinge is not None:
    D = math.radians(22)          # drop to the loading angle
    hinge.keyframe_insert('rotation_euler', index=1, frame=P.T(4.4))
    hinge.rotation_euler.y = -ELEV + D
    hinge.keyframe_insert('rotation_euler', index=1, frame=P.T(4.95))
    hinge.keyframe_insert('rotation_euler', index=1, frame=P.T(5.25))
    hinge.rotation_euler.y = -ELEV
    hinge.keyframe_insert('rotation_euler', index=1, frame=P.T(5.95))
    K.set_interp(hinge, 'BEZIER')
# lingering muzzle smoke
for k in range(5):
    P.puff(lb.world_at(mz, 1.3 + 0.2 * k), 1.3 + 0.2 * k, size=0.6, n=1, rise=1.2, life=2.0,
           color=(0.45, 0.43, 0.4), opacity=0.3)

# --------------------------------------------------------------------------- camera
T_C1 = cut_t(40)       # 1.625: ride with the shells
T_C2 = cut_t(103)      # 4.25: back home
S1 = shell_pos(1, T_C1 - 1 / FPS)
keys = [
    (0.0, (7.5, -8.2, 0.8), (0.3, 0.0, 2.2), 30),
    (0.5, (6.6, -7.2, 0.75), (0.5, 0.0, 2.3), 30),
    (1.15, (5.9, -6.6, 0.7), (1.5, 0.0, 3.2), 29),
    (T_C1 - 1 / FPS, (5.6, -6.4, 0.7), S1, 28),
]
# ride: just behind and beside the middle shell, looking past it at the outpost on a long
# lens so the outpost fills about a third of the frame while the salvo flies in
OUTPOST = Vector((TX, TY + 0.5, 2.0))
OUT_W = 14.0                     # rough visible width of the outpost cluster (m)
for t in (T_C1, 2.0, 2.35):
    p = shell_pos(1, t)
    dvec = Vector((OUTPOST.x - p.x, OUTPOST.y - p.y, 0)).normalized()
    side = Vector((dvec.y, -dvec.x, 0))      # to the right of travel (toward -y)
    c = p - dvec * 10.0 + side * 3.5 + Vector((0, 0, 1.2))
    dist = (OUTPOST - c).length
    lens = max(32.0, min(110.0, 36.0 * dist / (3.0 * OUT_W)))
    keys.append((t, tuple(c), OUTPOST - Vector((0, 0, 1.3)), lens))
keys += [
    (2.75, (77.0, -16.0, 8.0), (TX - 1.0, TY + 0.5, 2.0), 32),
    (3.6, (80.0, -17.0, 7.6), (TX, TY + 0.5, 2.0), 34),
    (T_C2 - 1 / FPS, (82.0, -16.5, 6.8), (TX + 1.0, TY + 1.0, 2.0), 35),
    (T_C2, (-11.5, -6.8, 1.5), (30.0, 5.0, 2.6), 34),
    (6.0, (-10.2, -6.2, 1.2), (30.0, 5.5, 3.0), 34),
]
P.camera(keys, shake=0.02, cuts=(T_C1, T_C2))
for th in T_HITS:
    P.cam_shake(th, 0.07, 0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
for _t in T_SHOTS:                                    # shells screaming downrange (camera rides along)
    P.sfx(_t + 0.9, 'whoosh', gain=0.4, rate=0.7)
for _t in T_HITS:                                     # and overtaking the camera as they drop
    P.sfx(_t - 0.6, 'whoosh', gain=0.45, rate=0.8)
P.sfx(4.4, 'servo', gain=0.45, rate=0.6)              # barrel drops to the loading angle
P.sfx(4.9, 'mech_clunk', gain=0.5, rate=0.75)         # breech opens: reload
P.sfx(5.05, 'hydraulic', gain=0.3)
P.sfx(5.25, 'servo', gain=0.45, rate=0.65)            # and swings back up to the sky

P.render()
