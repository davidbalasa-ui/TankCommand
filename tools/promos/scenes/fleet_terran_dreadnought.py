"""Terran Dreadnought (fleet flagship): the huge ship slides out of shadow, sunlight sweeping
bow to stern while a Twin-X flight streaks past the camera and two Terran corvettes hold
station beneath it. Two Arcadian corvettes dive in and lash it with gold lightning: a
translucent blue triangle shield takes every bolt, rings rippling across it (it never breaks).
The port broadside turrets roll round, ripple-fire, and blow both corvettes apart (their pieces
drift off without gravity); the camera ends on the whole flagship against the planet, shield
shimmering, escorts tiny beside it.

Scale: built at 0.3x the models.json ship sizes (Dreadnought 120 m, Terran corvettes 13.5 m,
Twin-X 2.7 m; the Arcadian corvettes are nudged up to 19.5 m so the attackers read) so the
kit's game-scale effects read. Fleet ships have no gun pivots, so the broadside turrets are
built in the scene (1.8x size so they read) and mounted on the hull by ray casts.

Timeline (s): 0-2.25 low ahead of the bow, the shadow line slides off the hull, Twin-X flight
whips past camera | cut 2.25: over the shoulder of an Arcadian corvette, both corvettes lash the
shield (hits 2.4 .. 3.7), the turrets roll toward them | cut 3.875: port side above the deck
with the planet behind, salvo 1 ripples 3.9-4.26 and kills corvette A 4.5, last bolt from B
4.62, salvo 2 4.78-5.14 kills B 5.4 | push in to 6.0."""
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

P = Promo('fleet_terran_dreadnought', seconds=6.0, seed=7)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']

SCALE = 0.3
DN_SIZE = 400 * SCALE       # 120 m
AC_SIZE = 50 * SCALE * 1.3  # 19.5 m (nudged up so the attackers read at phone size)
TC_SIZE = 45 * SCALE        # 13.5 m
TX_SIZE = 9 * SCALE         # 2.7 m

SUN = (78, 0, -25)
P.space(planet=(-900, 900, -350, 430, (0.12, 0.17, 0.27)), nebula=(0.07, 0.03, 0.11),
        sun=SUN, sun_energy=4.5)

CUT1 = 54 / FPS             # frame 55
CUT2 = 93 / FPS             # frame 94


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


def VV(x, y, z):
    return Vector((x, y, z))


# ------------------------------------------------------------------------------- flagship
DV = Vector((8.0, 0, 0))


def C(t):
    return Vector((0.0, 0.0, 0.0)) + DV * t


def terran_glow(actor):
    """Scene-only tint of Terran placeholder glow: purple/magenta -> neon blue, red -> orange."""
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
                    sock.default_value = (*COL['terran_neon'], 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:
                    sock.default_value = (*COL['terran_orange'], 1)


dread = P.load('terran_dreadnought', at=(0, 0), size=DN_SIZE, label='dreadnought')
terran_glow(dread)
bpy.context.view_layer.update()
HULL = max(dread.meshes, key=lambda o: len(o.data.vertices))
HULL_MW = HULL.matrix_world.copy()       # root at origin: root-local == world here
HULL_INV = HULL_MW.inverted()


def hull_ray(origin, direction):
    o = HULL_INV @ Vector(origin)
    d = (HULL_INV.to_3x3() @ Vector(direction)).normalized()
    ok, loc, nrm, idx = HULL.ray_cast(o, d)
    return (HULL_MW @ loc) if ok else None


dread.root.location = C(0)
dread.root.keyframe_insert('location', frame=1)
dread.root.location = C(6.0)
dread.root.keyframe_insert('location', frame=NF)
K.set_interp(dread.root, 'LINEAR')

# ------------------------------------------------------------------------------- shadow
# An invisible (camera-blind) occluder between sun and ship: its edge slides back along the hull
# so sunlight sweeps bow -> stern ("out of the planet's shadow").
rx, rz = math.radians(SUN[0]), math.radians(SUN[2])
LDIR = Vector((-math.sin(rz) * math.sin(rx), math.cos(rz) * math.sin(rx), -math.cos(rx))).normalized()
U = (Vector((1, 0, 0)) - LDIR * LDIR.x).normalized()
W_ = LDIR.cross(U).normalized()
me = bpy.data.meshes.new('Occluder')
bm = bmesh.new()
# (kept narrow: a wide plane also shadowed the planet and left it a black disc with a rim)
vs = [bm.verts.new(U * a + W_ * b) for a, b in ((-300, -500), (0, -500), (0, 500), (-300, 500))]
bm.faces.new(vs)
bm.to_mesh(me)
bm.free()
occ = K.link(bpy.data.objects.new('Occluder', me))
me.materials.append(K.pbr_mat('OccM', (0, 0, 0), rough=1.0))
occ.visible_camera = False
occ.visible_diffuse = False
occ.visible_glossy = False
occ.visible_transmission = False
occ.visible_volume_scatter = False


def edge(t):
    if t < 0.15:
        return 80.0
    if t < 2.0:
        return lerp(80.0, -80.0, ss((t - 0.15) / 1.75))
    return lerp(-80.0, -600.0, min(1.0, (t - 2.0) / 0.3))


for f in range(1, NF + 1, 2):
    t = (f - 1) / FPS
    occ.location = C(t) - LDIR * 160 + U * edge(t)
    occ.keyframe_insert('location', frame=f)
K.set_interp(occ, 'LINEAR')
K.key_hide(occ, 0, False)
K.key_hide(occ, int(P.T(2.3)), True)

# ------------------------------------------------------------------------------- flight helpers


def catmull(keys, t):
    if t <= keys[0][0]:
        t0, p0 = keys[0]
        t1, p1 = keys[1]
        return p0 + (p1 - p0) * ((t - t0) / (t1 - t0))
    if t >= keys[-1][0]:
        t0, p0 = keys[-2]
        t1, p1 = keys[-1]
        return p1 + (p1 - p0) * ((t - t1) / (t1 - t0))
    for i in range(len(keys) - 1):
        if keys[i][0] <= t <= keys[i + 1][0]:
            break
    ta, pa = keys[i]
    tb, pb = keys[i + 1]
    pm = keys[i - 1][1] if i > 0 else pa - (pb - pa)
    pn = keys[i + 2][1] if i + 2 < len(keys) else pb + (pb - pa)
    u = (t - ta) / (tb - ta)
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2 * pa) + (-pm + pb) * u + (2 * pm - 5 * pa + 4 * pb - pn) * u2 + (-pm + 3 * pa - 3 * pb + pn) * u3)


def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, t1, bank=0.01, face=None):
    """Key root location + orientation every frame. Nose along velocity (or face(t) dir)."""
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    prev = None
    dt = 1.0 / FPS
    for f in range(1, min(NF, int(P.T(t1)) + 2) + 1):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt) - posf(t - dt)) / (2 * dt)
        fwd = face(t) if face else v
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        lat = a - v.normalized() * a.dot(v.normalized())
        side = Vector((0, 0, 1)).cross(fwd).normalized()
        roll = max(-0.8, min(0.8, lat.dot(side) * bank))
        q = (frame_from(fwd, Vector((0, 0, 1))) @ Matrix.Rotation(roll, 3, 'X')).to_quaternion()
        if prev is not None:
            q.make_compatible(prev)
        prev = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
    K.set_interp(r, 'LINEAR')


def reparent_new(before, parent):
    for o in bpy.data.objects:
        if o not in before and o.parent is None:
            o.parent = parent


# ------------------------------------------------------------------------------- escorts
# Two Terran corvettes hold station under the flagship; a Twin-X flight streaks past the lens.
esc0 = P.load('terran_corvette', at=(0, 0), size=TC_SIZE, label='escort0')
terran_glow(esc0)
esc1 = P.copy(esc0, at=(0, 0), label='escort1')
ESC_OFF = [VV(22, -34, -26), VV(-38, -26, -30)]
for e, off in zip((esc0, esc1), ESC_OFF):
    fly(e, lambda t, off=off: C(t) + off + VV(0, 0, 0.6 * math.sin(t * 1.3 + off.x)), 6.0)

tx0 = P.load('terran_twinx', at=(0, 0), size=TX_SIZE, label='twinx0')
terran_glow(tx0)
txs = [tx0, P.copy(tx0, label='twinx1'), P.copy(tx0, label='twinx2')]
TX_OFF = [VV(0, 0, 0), VV(-5, -4.5, -1.5), VV(-5.5, 4.0, 0.8)]


def TXP(i, t):
    base = catmull([(0.0, VV(-70, -36, -12)), (0.8, VV(-18, -40, -16)), (1.5, VV(32, -44, -20)),
                    (2.3, VV(92, -50, -24))], t)
    return C(t) + base + TX_OFF[i]


for i, a in enumerate(txs):
    fly(a, lambda t, i=i: TXP(i, t), 2.4, bank=0.02)

# ------------------------------------------------------------------------------- Arcadian corvettes
T_DIE = [4.5, 5.4]
AC_KEYS = [
    [(0.0, VV(95, -175, 32)), (1.2, VV(70, -140, 26)), (2.3, VV(50, -110, 10)), (3.3, VV(36, -82, 0)),
     (4.5, VV(22, -56, -14))],
    [(0.0, VV(-60, -190, 0)), (1.3, VV(-46, -150, 4)), (2.5, VV(-24, -118, 2)), (3.8, VV(4, -90, -2)),
     (5.4, VV(18, -66, -10))],
]


def A(i, t):
    return C(t) + catmull(AC_KEYS[i], t)


acs = []
for i in range(2):
    a = P.load('arcadian_corvette', at=(0, 0), size=AC_SIZE, label=f'arcorvette{i}')
    # nose eases from its course toward the flagship as it commits to the attack
    def face(t, i=i):
        v = (A(i, t + 0.05) - A(i, t - 0.05)).normalized()
        tgt = (C(t) + VV(-5 + 20 * (0.5 - i), 0, -4) - A(i, t)).normalized()
        return v.lerp(tgt, 0.6).normalized()
    fly(a, lambda t, i=i: A(i, t), T_DIE[i], face=face)
    acs.append(a)

# placeholder emissive tame-down (scene only): the corvette's bolt/arc zones blow out to white
for m in {s.material for a in acs for o in a.meshes for s in o.material_slots if s.material}:
    for n in (m.node_tree.nodes if m.node_tree else []):
        if n.type == 'BSDF_PRINCIPLED' and m.name.startswith(('zone_bolt', 'zone_arc')):
            n.inputs['Emission Strength'].default_value = min(n.inputs['Emission Strength'].default_value, 3.0)

bpy.context.view_layer.update()
am = max(acs[0].meshes, key=lambda o: len(o.data.vertices))
inv0 = acs[0].root.matrix_world.inverted()
pts0 = [inv0 @ (am.matrix_world @ Vector(c)) for c in am.bound_box]
AX0 = min(p.x for p in pts0)
AX1 = max(p.x for p in pts0)

# gold lightning thrusters riding each corvette (kit lightning_thruster; no lights: a point
# light 2 m off the gold hull blows it out)
for i, a in enumerate(acs):
    for sgn in (1, -1):
        WFX.lightning_thruster(P, a, 0.0, T_DIE[i] + 1 / FPS, local=(AX0 + 0.8, 1.6 * sgn, 0.0),
                               axis=(-1, 0.12 * sgn, 0), length=5.0, width=0.08, n=2, spread=0.3,
                               color=GOLD, light=False)

# ------------------------------------------------------------------------------- shield
SH_C = VV(0, 0, -5.0)               # root-local centre
SH_AX = VV(70.0, 22.0, 17.0)        # semi-axes
SH_R = 20.0


def shield_hit_local(p_world, aim_world, t):
    """Ray from p toward aim, against the shield ellipsoid (ship-local). Returns world point."""
    c = C(t)
    o = (p_world - c - SH_C)
    d = (aim_world - p_world).normalized()
    os_ = VV(o.x / SH_AX.x, o.y / SH_AX.y, o.z / SH_AX.z)
    ds = VV(d.x / SH_AX.x, d.y / SH_AX.y, d.z / SH_AX.z)
    a_ = ds.dot(ds)
    b_ = 2 * os_.dot(ds)
    c_ = os_.dot(os_) - 1
    disc = b_ * b_ - 4 * a_ * c_
    if disc < 0:
        return aim_world
    s = (-b_ - math.sqrt(disc)) / (2 * a_)
    return p_world + d * s


BOLTS = [(0, 2.4, 0.3), (1, 2.8, 0.3), (0, 3.15, 0.25), (1, 3.45, 0.3), (0, 3.7, 0.22), (1, 4.62, 0.3)]
hits = []
for i, t, dur in BOLTS:
    a = acs[i]
    p0 = A(i, t)
    fwd = (C(t) - p0).normalized()
    p0 = p0 + fwd * (AX1 * 0.8)
    aim = C(t) + VV(R.uniform(-30, 30), R.uniform(-3, 3), R.uniform(-6, 2))
    p1 = shield_hit_local(p0, aim, t)
    L = (p1 - p0).length
    P.lightning(p0, p1, t, t + dur, color=GOLD, width=0.32, jag=min(0.3, 9.0 / L), branches=2,
                segs=max(10, int(L / 4)), glow=False)
    hits.append((t + 0.02, p1))

shield = P.shield_dome(VV(0, 0, 0), SH_R, 2.38, 6.2)
shield.parent = dread.root
shield.location = SH_C
shield.scale = (SH_AX.x / SH_R, SH_AX.y / SH_R, SH_AX.z / SH_R)   # ellipsoid hugging the hull
SH_LAT = next(c for c in shield.children if c.name.startswith('ShieldLattice'))
SH_LAT.modifiers['Wire'].thickness = SH_R * 0.004
# tone the shell down: on a hull this size the default opacity reads as a solid blue blob
for o_, k_ in ((shield, 0.22), (SH_LAT, 0.45)):
    for fc in K._fcurves(o_.animation_data.action):
        if fc.data_path == 'color' and fc.array_index == 3:
            for kp in fc.keyframe_points:
                kp.co.y *= k_
                kp.handle_left.y *= k_
                kp.handle_right.y *= k_
    o_.color[3] *= k_
# Kit ripples (rings racing over the shell from each hit; the shield never breaks). The ripple
# shader works in the shell's unscaled object space, so each hit is mapped onto the unit sphere
# of the ellipsoid; the kit's own flash/sparks/light assume a round, unparented dome, so they are
# dropped and a blue impact is placed at the true hit point instead.
for t, p in hits:
    loc = p - C(t) - SH_C
    n = VV(loc.x / SH_AX.x, loc.y / SH_AX.y, loc.z / SH_AX.z).normalized()
    before = set(bpy.data.objects)
    WFX.shield_hit(P, shield, SH_LAT, VV(0, 0, 0), SH_R, t, n * SH_R, COL['shield_blue'], False, 6.2)
    for o in list(bpy.data.objects):
        if o in before:
            continue
        if o.name.startswith('ShieldRipple'):
            if o.parent is shield:
                o.scale = (1.004,) * 3      # (the kit divides by the parent's x scale: wrong on an ellipsoid)
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    P.impact(p, t, size=2.2, color=COL['shield_blue'])

# ------------------------------------------------------------------------------- broadside turrets
M_TBASE = K.pbr_mat('BSBase', (0.1, 0.11, 0.13), rough=0.45, metal=0.7)
M_TBARREL = K.pbr_mat('BSBarrel', (0.05, 0.055, 0.06), rough=0.35, metal=0.8)
M_TNEON = K.emit_mat('BSNeon', COL['terran_neon'], 2.5)
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
    # built big (1.8x) so the turret row reads on a 120 m hull at phone size
    BLEN = 12.6
    SY = 1.35
    BX = 1.08

    def __init__(self, i, mount):
        self.i = i
        self.mount = mount
        base = cyl(f'BS{i}_Base', 4.1, 2.2, M_TBASE, verts=20)
        base.parent = dread.root
        base.location = mount + Vector((0, 0, 0.7))
        ring = cyl(f'BS{i}_Ring', 4.3, 0.4, M_TNEON, verts=20)
        ring.parent = base
        ring.location = (0, 0, 0.63)
        head = K.empty(f'BS{i}_Head')
        head.parent = dread.root
        head.location = mount + Vector((0, 0, 2.7))
        head.rotation_mode = 'QUATERNION'
        dome = K.sphere(f'BS{i}_Dome', 3.4, M_TBASE, seg=(16, 8))
        dome.parent = head
        dome.scale = (1.25, 1.0, 0.55)
        eye = K.sphere(f'BS{i}_Sensor', 0.55, M_TORANGE, seg=(8, 6))
        eye.parent = head
        eye.location = (2.5, 0, 1.35)
        self.head = head
        self.barrels = []
        self.muzzles = []
        for k, sy in enumerate((self.SY, -self.SY)):
            b = cyl(f'BS{i}_Barrel{k}', 0.58, self.BLEN, M_TBARREL, verts=12)
            b.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y') @ Matrix.Translation((0, 0, self.BLEN / 2)))
            b.parent = head
            b.location = (self.BX, sy, 0.27)
            tip = cyl(f'BS{i}_Tip{k}', 0.75, 1.2, M_TNEON, verts=12)
            tip.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y'))
            tip.parent = b
            tip.location = (self.BLEN - 0.5, 0, 0)
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
        return C(t) + self.head.location + d * (self.BX + self.BLEN + 0.2) + side * sy

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
        L = self.BLEN * 0.8
        b.location.x = self.BX
        b.keyframe_insert('location', index=0, frame=f - 1)
        b.location.x = self.BX - L
        b.keyframe_insert('location', index=0, frame=f + 1)
        b.location.x = self.BX
        b.keyframe_insert('location', index=0, frame=f + 9)


MOUNT_X = [-38.0, -16.0, 6.0, 26.0]
turrets = []
for i, x in enumerate(MOUNT_X):
    best = None
    for dx in (-2, 0, 2):
        for y in (-5.0, -6.0, -7.0):
            h = hull_ray((x + dx, y, 60), (0, 0, -1))
            if h is not None and (best is None or h.z > best.z):
                best = h
    if best is None:
        best = Vector((x, -6.0, 0.0))
    print('broadside mount', i, tuple(round(c, 2) for c in best))
    turrets.append(Turret(i, best))

# fire plan: two ripple salvos, stern -> bow on A, bow -> stern on B
SHELL_SPEED = 240.0
SALVOS = [(0, [3.9, 4.02, 4.14, 4.26], [3, 2, 1, 0]), (1, [4.78, 4.9, 5.02, 5.14], [0, 1, 2, 3])]
FIRE = {}       # turret -> [(t, target)]
for tgt, times, order in SALVOS:
    for t, k in zip(times, order):
        FIRE.setdefault(k, []).append((t, tgt))


def lead(i, p0, t):
    tt = t
    for _ in range(3):
        tof = (A(i, tt) - p0).length / SHELL_SPEED
        tt = t + tof
    return A(i, tt), tof


REST = Vector((1, -0.15, 0.06))
for k, tu in enumerate(turrets):
    def dirf(t, tu=tu, k=k):
        base = C(t) + tu.head.location
        rest = REST.normalized()
        # roll toward A 2.7-3.5 (staggered), switch to B after the A kill, ease back at the end
        u = ss((t - 2.7 - 0.12 * (3 - k)) / 0.8)
        tgt_i = 0 if t < T_DIE[0] + 0.15 else 1
        dA = (lead(0, base, min(t, T_DIE[0]))[0] - base).normalized()
        if tgt_i == 0:
            return rest.lerp(dA, u).normalized()
        dB = (lead(1, base, min(t, T_DIE[1]))[0] - base).normalized()
        w = ss((t - T_DIE[0] - 0.15) / 0.25)
        d = dA.lerp(dB, w).normalized()
        back = ss((t - T_DIE[1] - 0.2) / 0.4) * 0.35
        return d.lerp(rest, back).normalized()
    tu.key_aim(dirf)

kick = []
for k, tu in enumerate(turrets):
    for n, (t, tgt) in enumerate(FIRE[k]):
        bk = n % 2
        p0 = tu.muzzle_world(t, bk)
        tp, tof = lead(tgt, p0, t)
        tp = tp + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))) * 1.2
        P.projectile(p0, tp, t, SHELL_SPEED, COL['tracer'], size=0.75)
        P.muzzle_flash(tu.muzzles[bk], t, COL['fire'], size=3.6)
        tu.recoil(t, bk)
        if t + tof < T_DIE[tgt] - 0.03:
            P.impact(tp, t + tof, size=2.6)
        kick.append(t)

# hull kick: each heavy shot rolls the flagship a hair away from the target
dm = dread.model_root
dm.rotation_mode = 'XYZ'
for t in sorted(kick):
    f = P.T(t)
    dm.rotation_euler.x = 0.0
    dm.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    dm.rotation_euler.x = math.radians(0.5)
    dm.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    dm.rotation_euler.x = 0.0
    dm.keyframe_insert('rotation_euler', index=0, frame=f + 10)

# ------------------------------------------------------------------------------- kills
# space kills: each corvette fractures into its own pieces, which drift on without gravity
# (promo_fx.destroy handles space), with a fireball and sparks
for i, a in enumerate(acs):
    a.destroy(T_DIE[i], size=7.0, wreck=False, debris=14)

# ------------------------------------------------------------------------------- camera
keys = []
# Shot A: low and ahead of the bow on a long lens; the ship crawls overhead out of the shadow.
for i in range(7):
    t = CUT1 * i / 6
    if i == 6:
        t = CUT1 - 1 / FPS
    u = t / CUT1
    c = C(t)
    pos = c + VV(lerp(100, 84, ss(u)), lerp(-70, -60, ss(u)), lerp(-34, -30, ss(u)))
    look = c + VV(lerp(14, -4, ss(u)), lerp(-4, -8, ss(u)), lerp(-4, -6, u))
    keys.append((t, tuple(pos), tuple(look), 32))
# Shot B: over the shoulder of Arcadian corvette A, looking at the flagship's flank.
for i in range(6):
    t = CUT1 + (CUT2 - CUT1) * i / 5
    if i == 5:
        t = CUT2 - 1 / FPS
    u = (t - CUT1) / (CUT2 - CUT1)
    a = A(0, t)
    pos = a + VV(lerp(14, 10, ss(u)), lerp(-30, -26, ss(u)), lerp(12, 10, u))
    look = a.lerp(C(t) + VV(-16, 0, -4), 0.42)
    keys.append((t, tuple(pos), tuple(look), 30))
# Shot C: low front quarter, the broadside ripple-fires, push in to the hero frame.
for i in range(9):
    t = CUT2 + (6.0 - CUT2) * i / 8
    u = (t - CUT2) / (6.0 - CUT2)
    c = C(t)
    # port side, a little above the deck so the turret row reads as it ripple-fires
    pos = c + VV(lerp(88, 80, ss(u)), lerp(-100, -94, ss(u)), lerp(22, 14, ss(u)))
    look = c + VV(lerp(12, 4, ss(u)), lerp(-20, -12, ss(u)), lerp(-6, -4, u))
    keys.append((t, tuple(pos), tuple(look), lerp(25, 29, ss(u))))
P.camera(keys, shake=0.04, cuts=(CUT1, CUT2))
P.cam_shake(T_DIE[0], 0.4, dur=0.4)
P.cam_shake(T_DIE[1], 0.45, dur=0.45)
for t in (3.9, 4.78):
    P.cam_shake(t, 0.15, dur=0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
for _t in (2.4, 2.8, 3.15, 3.45, 3.7):                # triangle shield flares and shrugs every bolt off
    P.sfx(_t + 0.02, 'shield_hit', gain=0.6)

P.render()
