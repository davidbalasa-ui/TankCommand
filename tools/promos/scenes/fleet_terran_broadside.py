"""Terran Broadside battleship: an Arcadian Shell mothership lashes the battleship with gold
lightning while it swings its bow away to present its flank; the deck turrets roll round one
after another; then a rolling broadside ripples down the flank, stern to bow, blue deck bolts
and the three huge flank cannons booming in turn. Reverse angle from beyond the Shell: the
first ripple walks along the Shell's hull, a second ripple (bow to stern) answers, and the
mothership breaks apart, its pieces drifting off without gravity in front of the battleship.

Scale: 0.3x the models.json ship sizes (Broadside 78 m, Shell 114 m) so the kit's game-scale
effects read. The Broadside model is one mesh: the flank cannons are baked in (they fire with
flashes, a hull kick and blast smoke); the deck turrets are built here and mounted by ray casts.

Timeline (s): 0-2.25 high over the battleship's far quarter, the Shell beyond: it turns its flank
(heading -52 -> 0) under three lightning strikes, turrets swing in sequence 1.25-2.1 |
cut 2.25: low along the gun flank, ripple 2.45-3.33 stern -> bow | cut 3.75: beyond the Shell
looking back at the battleship: hits walk the Shell 3.8-4.6, ripple 2 fires 4.0-4.36 (bow ->
stern), lands 5.0-5.3, Shell destroyed 5.2 | drift to 6.0."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as WFX  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_terran_broadside', seconds=6.0, seed=23)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']

SCALE = 0.3
BS_SIZE = 260 * SCALE      # 78 m
SH_SIZE = 380 * SCALE      # 114 m

SUN = (68, 0, -30)
P.space(planet=(-1300, 1000, -150, 560, (0.12, 0.17, 0.27)), nebula=(0.07, 0.03, 0.11),
        sun=SUN, sun_energy=4.5)

CUT1 = 54 / FPS            # frame 55
CUT2 = 90 / FPS            # frame 91


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


def lerp(a, b, u):
    return a + (b - a) * u


def VV(x, y, z):
    return Vector((x, y, z))


def terran_glow(actor):
    """Scene-only tint of Terran glow: purple/magenta -> neon blue, red -> orange."""
    seen = set()
    for o in actor.meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m in seen or not m.node_tree:
                continue
            seen.add(m)
            for n in m.node_tree.nodes:
                if n.type == 'EMISSION':
                    sock = n.inputs['Color']
                elif n.type == 'BSDF_PRINCIPLED':
                    sock = n.inputs['Emission Color']
                    if n.inputs['Emission Strength'].default_value <= 0:
                        continue
                else:
                    continue
                if sock.is_linked:
                    continue
                r, g, b = sock.default_value[:3]
                if r > 0.3 and b > 0.3 and g < 0.6 * min(r, b):
                    sock.default_value = (*NEON, 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:
                    sock.default_value = (*COL['terran_orange'], 1)


# ------------------------------------------------------------------------------- Broadside
BV = Vector((2.0, 0, 0))


def C(t):
    return VV(0, 0, 0) + BV * t


def HEAD(t):
    """Heading (deg): the bow swings away so the gun flank (-Y) comes to bear on the Shell."""
    return lerp(-52.0, 0.0, ss((t - 0.05) / 2.2)) + 2.0 * math.sin(math.pi * ss((t - 1.6) / 1.2))


def ROLL(t):
    # leans into the turn, settles level for the broadside
    return math.radians(4.0) * math.sin(math.pi * ss((t - 0.05) / 2.4))


bs = P.load('terran_broadside', at=(0, 0), size=BS_SIZE, label='broadside')
terran_glow(bs)
bpy.context.view_layer.update()
HULL = max(bs.meshes, key=lambda o: len(o.data.vertices))
HULL_MW = HULL.matrix_world.copy()        # root at identity: root-local == world here
HULL_INV = HULL_MW.inverted()
K_MODEL = HULL_MW.to_scale().x


def hull_ray(origin, direction):
    o = HULL_INV @ Vector(origin)
    d = (HULL_INV.to_3x3() @ Vector(direction)).normalized()
    ok, loc, nrm, idx = HULL.ray_cast(o, d)
    return (HULL_MW @ loc) if ok else None


def model_pt(x, y, z):
    """Model-file coordinates -> Broadside root-local."""
    return HULL_MW @ VV(x, y, z)


def BM(t):
    """Broadside root matrix at time t."""
    return (Matrix.Translation(C(t)) @ Matrix.Rotation(math.radians(HEAD(t)), 4, 'Z')
            @ Matrix.Rotation(ROLL(t), 4, 'X'))


def BW(t, local):
    return BM(t) @ Vector(local)


r_ = bs.root
r_.rotation_mode = 'XYZ'
for f in range(1, NF + 1):
    t = (f - 1) / FPS
    r_.location = C(t)
    r_.rotation_euler = (ROLL(t), 0, math.radians(HEAD(t)))
    r_.keyframe_insert('location', frame=f)
    r_.keyframe_insert('rotation_euler', frame=f)
K.set_interp(r_, 'LINEAR')

# the three flank cannons baked into the hull (model x -11, 0, +11; muzzles at y -13.44)
TUBES = [model_pt(x, -13.6, 0.0) for x in (-11.0, 0.0, 11.0)]
tube_mz = []
for i, p in enumerate(TUBES):
    e = K.empty(f'TubeMuzzle{i}')
    e.parent = bs.root
    e.location = p
    e.rotation_euler = (0, 0, -math.pi / 2)     # +X of the empty points out of the flank (-Y)
    tube_mz.append(e)

# ------------------------------------------------------------------------------- Shell
SV = Vector((1.5, 0, 0))
SH0 = VV(-6, -165, 4)


def S(t):
    return SH0 + SV * t


shell = P.load('arcadian_shell', at=(0, 0), size=SH_SIZE, label='shell')
for m in {s.material for o in shell.meshes for s in o.material_slots if s.material}:
    for n in (m.node_tree.nodes if m.node_tree else []):
        if n.type == 'BSDF_PRINCIPLED' and m.name.startswith(('zone_bolt', 'zone_arc')):
            n.inputs['Emission Strength'].default_value = min(n.inputs['Emission Strength'].default_value, 3.0)
bpy.context.view_layer.update()
SHM = max(shell.meshes, key=lambda o: len(o.data.vertices))
SHM_MW = SHM.matrix_world.copy()
SHM_INV = SHM_MW.inverted()
sp = [SHM_MW @ Vector(c) for c in SHM.bound_box]
SX0, SX1 = min(p.x for p in sp), max(p.x for p in sp)


def shell_ray(origin, direction):
    o = SHM_INV @ Vector(origin)
    d = (SHM_INV.to_3x3() @ Vector(direction)).normalized()
    ok, loc, nrm, idx = SHM.ray_cast(o, d)
    return (SHM_MW @ loc) if ok else None


def shell_hit_local(x, z):
    """A point on the Shell's +Y face (local), found by a ray from the Broadside's side."""
    for dz in (0, 3, -3, 6, -6, 10):
        h = shell_ray((x, 120, z + dz), (0, -1, 0))
        if h is not None:
            return h
    return VV(x, 0, z)


SHELL_HEAD = 6.0


def SMtx(t):
    return Matrix.Translation(S(t)) @ Matrix.Rotation(math.radians(SHELL_HEAD + 1.5 * t), 4, 'Z')


def SW(t, local):
    return SMtx(t) @ Vector(local)


T_KILL = 5.2
rs = shell.root
rs.rotation_mode = 'XYZ'
for f in range(1, NF + 1):
    t = (f - 1) / FPS
    rs.location = S(t)
    rs.rotation_euler = (0, 0, math.radians(SHELL_HEAD + 1.5 * t))
    rs.keyframe_insert('location', frame=f)
    rs.keyframe_insert('rotation_euler', frame=f)
K.set_interp(rs, 'LINEAR')

# gold lightning thrusters at the spiral stern (kept thin; no lights)
for dy, dz in ((6, 4), (-6, -2), (0, 10)):
    WFX.lightning_thruster(P, shell, 2 / FPS, T_KILL + 1 / FPS, local=(SX0 + 4, dy, dz),
                           axis=(-1, 0.1 * dy / 6, 0.05), length=16.0, width=0.22, n=2, spread=0.3,
                           color=GOLD, light=False)

# ------------------------------------------------------------------------------- Shell lightning
# three strikes on the turning battleship (sound is recorded by the kit: point endpoints)
STRIKES = [(0.45, 30.0, (-8.0, 0)), (0.95, -10.0, (6.0, -2)), (1.5, 15.0, (-2.0, 2))]
for t, sx, (mx, mz) in STRIKES:
    src = SW(t, shell_hit_local(sx, 6.0) + VV(0, 2, 0))
    # hit point on the battleship's hull, seen from the Shell's side
    hl = hull_ray(model_pt(mx, -20, mz + 1.0), (0, 1, 0)) or model_pt(mx, -6, 0)
    dst = BW(t + 0.03, hl)
    L = (dst - src).length
    P.lightning(src, dst, t, t + 0.28, color=GOLD, width=0.9, jag=min(0.25, 14.0 / L), branches=3,
                segs=max(12, int(L / 6)), glow=True)
    P.impact(dst, t + 0.03, size=3.0, color=GOLD)
    WFX.sparks(P, dst, t + 0.03, n=14, speed=16.0, color=GOLD, axis=(dst - src).normalized() * -1, spread=60)

# ------------------------------------------------------------------------------- deck turrets
M_TBASE = K.pbr_mat('BSBase', (0.1, 0.11, 0.13), rough=0.45, metal=0.7)
M_TBARREL = K.pbr_mat('BSBarrel', (0.05, 0.055, 0.06), rough=0.35, metal=0.8)
M_TNEON = K.emit_mat('BSNeon', NEON, 2.5)
M_TORANGE = K.emit_mat('BSOrange', COL['terran_orange'], 2.0)


def cyl(name, r, depth, mat, verts=16):
    me_ = bpy.data.meshes.new(name)
    bm_ = bmesh.new()
    bmesh.ops.create_cone(bm_, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    bm_.to_mesh(me_)
    bm_.free()
    o = K.link(bpy.data.objects.new(name, me_))
    me_.materials.append(mat)
    return o


class Turret:
    S_ = 0.62
    BLEN = 12.6 * S_
    SY = 1.35 * S_
    BX = 1.08 * S_

    def __init__(self, i, mount):
        s = self.S_
        self.i = i
        self.mount = mount
        base = cyl(f'BS{i}_Base', 4.1 * s, 2.2 * s, M_TBASE, verts=20)
        base.parent = bs.root
        base.location = mount + Vector((0, 0, 0.7 * s))
        ring = cyl(f'BS{i}_Ring', 4.3 * s, 0.4 * s, M_TNEON, verts=20)
        ring.parent = base
        ring.location = (0, 0, 0.63 * s)
        head = K.empty(f'BS{i}_Head')
        head.parent = bs.root
        head.location = mount + Vector((0, 0, 2.7 * s))
        head.rotation_mode = 'QUATERNION'
        dome = K.sphere(f'BS{i}_Dome', 3.4 * s, M_TBASE, seg=(16, 8))
        dome.parent = head
        dome.scale = (1.25, 1.0, 0.55)
        eye = K.sphere(f'BS{i}_Sensor', 0.55 * s, M_TORANGE, seg=(8, 6))
        eye.parent = head
        eye.location = (2.5 * s, 0, 1.35 * s)
        self.head = head
        self.barrels = []
        self.muzzles = []
        for k, sy in enumerate((self.SY, -self.SY)):
            b = cyl(f'BS{i}_Barrel{k}', 0.58 * s, self.BLEN, M_TBARREL, verts=12)
            b.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y') @ Matrix.Translation((0, 0, self.BLEN / 2)))
            b.parent = head
            b.location = (self.BX, sy, 0.27 * s)
            tip = cyl(f'BS{i}_Tip{k}', 0.75 * s, 1.2 * s, M_TNEON, verts=12)
            tip.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y'))
            tip.parent = b
            tip.location = (self.BLEN - 0.5 * s, 0, 0)
            m = K.empty(f'BS{i}_Muzzle{k}')
            m.parent = b
            m.location = (self.BLEN + 0.2, 0, 0)
            self.barrels.append(b)
            self.muzzles.append(m)
        self.aims = {}

    def dir_at(self, t):
        f = max(1, min(NF, int(round(P.T(t)))))
        return self.aims.get(f, Vector((1, 0, 0)))

    def muzzle_world(self, t, k):
        d = self.dir_at(t)
        side = Vector((0, 0, 1)).cross(d).normalized()
        sy = self.SY if k == 0 else -self.SY
        return BW(t, self.head.location + d * (self.BX + self.BLEN + 0.2) + side * sy)

    def key_aim(self, dirf):
        prev = None
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            d = dirf(t).normalized()
            self.aims[f] = d
            q = d.to_track_quat('X', 'Z')
            if prev is not None:
                q.make_compatible(prev)
            prev = q
            self.head.rotation_quaternion = q
            self.head.keyframe_insert('rotation_quaternion', frame=f)
        K.set_interp(self.head, 'LINEAR')

    def recoil(self, t, k):
        b = self.barrels[k]
        f = P.T(t)
        L = self.BLEN * 0.6
        b.location.x = self.BX
        b.keyframe_insert('location', index=0, frame=f - 1)
        b.location.x = self.BX - L
        b.keyframe_insert('location', index=0, frame=f + 1)
        b.location.x = self.BX
        b.keyframe_insert('location', index=0, frame=f + 9)


# deck mounts between the flank-cannon towers (model x), on the gun side of the deck
MOUNT_MX = [-15.0, -5.5, 5.5, 16.5]
turrets = []
for i, mx in enumerate(MOUNT_MX):
    best = None
    for dx in (-0.8, 0, 0.8):
        for my in (-1.5, -2.2, -2.9):
            h = hull_ray(model_pt(mx + dx, my, 40), (0, 0, -1))
            if h is not None and (best is None or h.z > best.z):
                best = h
    if best is None:
        best = model_pt(mx, -2, 4.4)
    print('deck mount', i, tuple(round(c, 2) for c in best))
    turrets.append(Turret(i, best))

# ------------------------------------------------------------------------------- fire plan
# Ripple 1 (stern -> bow): deck turrets and flank cannons interleaved along the hull.
# Ripple 2 (bow -> stern), faster, finishes the Shell.
SLOW = 150.0        # slug speeds (m/s): slow enough that the walk of hits reads
HEAVY = 165.0
stations = sorted([('T', i, turrets[i].mount.x) for i in range(4)] + [('C', i, TUBES[i].x) for i in range(3)],
                  key=lambda s: s[2])
R1 = [(2.45 + 0.125 * n, st) for n, st in enumerate(stations)]
R2 = [(4.0 + 0.06 * n, st) for n, st in enumerate(reversed(stations))]
# aim points along the Shell's flank (local), walking with the ripple
AIM_X1 = [lerp(SX0 + 14, SX1 - 22, n / 6) for n in range(7)]
AIM_X2 = [lerp(SX1 - 30, SX0 + 18, n / 6) for n in range(7)]

REST = Vector((0.15, -1.0, 0.04))


def aim_local(tu, t, world_tgt):
    m = BM(t)
    return (m.inverted().to_3x3() @ (world_tgt - BW(t, tu.head.location))).normalized()


turret_tgt = {}
for (t, st), x1 in zip(R1, AIM_X1):
    if st[0] == 'T':
        turret_tgt.setdefault(st[1], []).append((t, x1))
for (t, st), x2 in zip(R2, AIM_X2):
    if st[0] == 'T':
        turret_tgt.setdefault(st[1], []).append((t, x2))

SWING = [1.25 + 0.2 * k for k in range(4)]       # turrets swing in sequence, stern -> bow
for k, tu in enumerate(turrets):
    plan = turret_tgt[k]

    def dirf(t, tu=tu, k=k, plan=plan):
        rest = REST.normalized()
        tx = plan[0][1] if t < plan[0][0] + 0.4 else plan[1][1]
        tgt = SW(min(t, T_KILL), shell_hit_local(tx, 4.0))
        d = aim_local(tu, t, tgt)
        u = ss((t - SWING[k]) / 0.55)
        back = ss((t - T_KILL - 0.2) / 0.5) * 0.4
        return rest.lerp(d, u * (1 - back)).normalized()
    tu.key_aim(dirf)

HITS = []      # (t, local x on the shell, size)
kicks = []
for ripple, plan, aims in ((1, R1, AIM_X1), (2, R2, AIM_X2)):
    for (t, st), ax in zip(plan, aims):
        tgt_local = shell_hit_local(ax + R.uniform(-3, 3), R.uniform(-4, 6))
        kind, i, _ = st
        if kind == 'T':
            tu = turrets[i]
            for k in (0, 1):
                tk = t + 0.035 * k
                p0 = tu.muzzle_world(tk, k)
                tof = (SW(tk, tgt_local) - p0).length / SLOW
                tp = SW(tk + tof, tgt_local) + VV(R.uniform(-1.5, 1.5), 0, R.uniform(-1.5, 1.5))
                P.projectile(p0, tp, tk, SLOW, NEON, size=0.7)
                P.muzzle_flash(tu.muzzles[k], tk, NEON, size=2.6)
                tu.recoil(tk, k)
                if tk + tof < T_KILL - 0.02:
                    HITS.append((tk + tof, tp, 4.5))
        else:
            mz = tube_mz[i]
            p0 = BW(t, TUBES[i] + VV(0, -1.5, 0))
            tof = (SW(t, tgt_local) - p0).length / HEAVY
            tp = SW(t + tof, tgt_local)
            P.projectile(p0, tp, t, HEAVY, COL['tracer'], size=1.7)
            P.muzzle_flash(mz, t, COL['fire'], size=4.0)
            P.sfx(t, 'shot_heavy', gain=1.0, rate=0.8)
            out = (BM(t).to_3x3() @ VV(0, -1, 0)).normalized()
            WFX.sparks(P, p0, t, n=18, speed=40.0, color=COL['fire'], axis=out, spread=25)
            P.light(p0 + out * 3, t, COL['fire'], energy=60000, dur=0.15, radius=2.0)
            # blast smoke pushed out of the muzzle, slowing and thinning
            for n in range(4):
                WFX.smoke_puff(P, p0 + out * (1.0 + 1.5 * n), t + 0.03 + 0.02 * n, r0=0.8, r1=3.0 + 0.8 * n,
                               life=1.8, vel=out * (9.0 - 1.8 * n), dens=0.35, hot=0.8 if n == 0 else 0.0,
                               wind=(0, 0, 0))
            kicks.append((t, 1.0))
            if t + tof < T_KILL - 0.02:
                HITS.append((t + tof, tp, 10.0))
            elif ripple == 2:
                HITS.append((t + tof, tp, 0))

for t, p, size in HITS:
    if size <= 0:
        continue
    P.explosion(p, t, size=size, debris=6 if size > 5 else 3)

# hull kick: each flank cannon shot rocks the battleship away from the target (+Y roll)
dm = bs.model_root
dm.rotation_mode = 'XYZ'
dm.rotation_euler = (0, 0, 0)
dm.keyframe_insert('rotation_euler', index=0, frame=1)
for t, k in sorted(kicks):
    f = P.T(t)
    dm.rotation_euler.x = 0.0
    dm.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    dm.rotation_euler.x = math.radians(-0.9 * k)
    dm.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    dm.rotation_euler.x = 0.0
    dm.keyframe_insert('rotation_euler', index=0, frame=f + 12)

# ------------------------------------------------------------------------------- kill
# promo_fx.destroy scales debris speed and spark count by actor.size / 4.5: at 114 m the Shell's
# pieces would leave at ~100 m/s under 600 sparks, so it is told it is smaller for the break-up
shell.size = 22.0
shell.destroy(T_KILL, size=16.0, wreck=False, debris=22)
for n in range(3):
    p = SW(T_KILL + 0.05 * n, VV(lerp(SX0 + 10, SX1 - 10, R.random()), R.uniform(-6, 6), R.uniform(-6, 6)))
    P.explosion(p, T_KILL + 0.08 + 0.1 * n, size=R.uniform(6, 8), debris=4)

# ------------------------------------------------------------------------------- camera
keys = []
# Shot A: high over the battleship's far (+Y) quarter, looking past it at the Shell.
for i in range(7):
    t = CUT1 * i / 6
    if i == 6:
        t = CUT1 - 1 / FPS
    u = t / CUT1
    c = C(t)
    pos = c + VV(lerp(-52, -40, ss(u)), lerp(62, 56, ss(u)), lerp(26, 22, ss(u)))
    look = c + VV(lerp(8, 12, ss(u)), lerp(-78, -70, ss(u)), lerp(-8, -9, u))
    keys.append((t, tuple(pos), tuple(look), 26))
# Shot B: low on the gun flank by the bow, looking aft along the hull as the ripple rolls.
for i in range(6):
    t = CUT1 + (CUT2 - CUT1) * i / 5
    if i == 5:
        t = CUT2 - 1 / FPS
    u = (t - CUT1) / (CUT2 - CUT1)
    c = C(t)
    pos = c + VV(lerp(58, 52, ss(u)), lerp(-54, -50, ss(u)), lerp(-9, -8, u))
    look = c + VV(lerp(-6, -10, ss(u)), lerp(-14, -16, u), lerp(1, 2, u))
    keys.append((t, tuple(pos), tuple(look), 26))
# Shot C: beyond the Shell, looking back at the battleship: hits walk the hull, the Shell dies.
for i in range(8):
    t = CUT2 + (6.0 - CUT2) * i / 7
    u = (t - CUT2) / (6.0 - CUT2)
    s = S(t)
    pos = s + VV(lerp(90, 82, ss(u)), lerp(-200, -188, ss(u)), lerp(70, 64, ss(u)))
    look = s + VV(lerp(0, 2, ss(u)), lerp(85, 82, ss(u)), lerp(-4, -3, u))
    keys.append((t, tuple(pos), tuple(look), lerp(52, 54, ss(u))))
P.camera(keys, shake=0.04, cuts=(CUT1, CUT2))
for t, _ in kicks:
    if t < CUT2:
        P.cam_shake(t, 0.25, dur=0.3)
P.cam_shake(T_KILL, 0.6, dur=0.5)

# ---- sound cues for effects drawn in this script
for k in range(4):
    P.sfx(SWING[k], 'turret_servo', gain=0.6, rate=0.9 + 0.05 * k)
P.sfx(2.2, 'power_up_terran', gain=0.5)

P.render()
