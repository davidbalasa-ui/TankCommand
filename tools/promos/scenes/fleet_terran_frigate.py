"""Terran Frigate (fleet escort): the frigate holds the screen in front of a Dreadnought. A wave
of four Arcadian Stingray fighters streaks in on gold lightning thrusters, aiming for the big
ship; the frigate's four point-defence turrets swing round and shred them one by one. The last
Stingray gets close enough to lash the hull with gold lightning before it is torn apart just
off the bow, and the camera settles on a low hero frame of the frigate with the Dreadnought
safe behind it.

Scale: the whole scene is built at 0.3x the models.json ship sizes (frigate 36 m, Stingray 3 m,
Dreadnought 120 m) so the kit's game-scale effects (tracers, flashes, lights) read correctly.

Timeline (s): 0-1.5 over the frigate's flank, gold sparks closing in, turrets swing, PD opens
up at 1.2 | cut 1.5: chase behind the Stingrays, tracer streams coming at us, #1 dies 1.9,
#2 dies 2.5, #4 fires a long bolt at 2.85 | cut 3.25: ahead of the frigate, the survivors
dive past the camera, #3 dies 3.55, #4 hits the hull 3.95 and dies 4.35 off the bow |
4.4-6 settle on the hero frame."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_terran_frigate', seconds=6.0, seed=11)
FPS = P.fps
NF = P.nf
R = P.rnd

SCALE = 0.3
FR_SIZE = 120 * SCALE
SR_SIZE = 10 * SCALE * 1.35   # fighters nudged up 35% so they read at phone size
DN_SIZE = 400 * SCALE

P.space(planet=(700, -150, -520, 480, (0.12, 0.17, 0.27)), nebula=(0.07, 0.03, 0.11),
        sun=(58, 0, 60), sun_energy=4.5)

T_CUT1 = 36 / FPS     # frame 37
T_CUT2 = 78 / FPS     # frame 79


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- fleet motion
FV = Vector((2.5, 0, 0))


def F(t):
    """Frigate centre: steady cruise along +X."""
    return Vector((-4.0, 0.0, 0.0)) + FV * t


def D(t):
    return Vector((-92.0, 24.0, 22.0)) + FV * t


frig = P.load('terran_frigate', at=(0, 0), size=FR_SIZE, label='frigate')
dread = P.load('terran_dreadnought', at=(0, 0), size=DN_SIZE, label='dreadnought')
dread.place(tuple(D(0)), heading=0)
dread.root.keyframe_insert('location', frame=1)
dread.root.location = D(6.0)
dread.root.keyframe_insert('location', frame=NF)
K.set_interp(dread.root, 'LINEAR')



def terran_glow(actor):
    """Scene-only tint of a Terran placeholder ship's glow: purple/magenta emission -> neon blue,
    red accents -> Terran orange. Model files stay untouched."""
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
                if r > 0.3 and b > 0.3 and g < 0.6 * min(r, b):          # magenta / purple
                    sock.default_value = (*COL['terran_neon'], 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:                   # red accent
                    sock.default_value = (*COL['terran_orange'], 1)


terran_glow(frig)
terran_glow(dread)

bpy.context.view_layer.update()
HULL =max(frig.meshes, key=lambda o: len(o.data.vertices))
HULL_MW = HULL.matrix_world.copy()      # frigate root at origin here
HULL_INV = HULL_MW.inverted()


def hull_ray(origin, direction):
    """Ray against the frigate hull in root space (frigate at origin). Returns hit or None."""
    o = HULL_INV @ origin
    d = (HULL_INV.to_3x3() @ direction).normalized()
    ok, loc, nrm, idx = HULL.ray_cast(o, d)
    if not ok:
        return None
    return HULL_MW @ loc


def top_at(x, y):
    h = hull_ray(Vector((x, y, 60)), Vector((0, 0, -1)))
    return h


# ------------------------------------------------------------------------------- PD turrets
M_TBASE = K.pbr_mat('PDBase', (0.09, 0.1, 0.12), rough=0.45, metal=0.7)
M_TBARREL = K.pbr_mat('PDBarrel', (0.05, 0.055, 0.06), rough=0.35, metal=0.8)
M_TNEON = K.emit_mat('PDNeon', COL['terran_neon'], 2.5)
M_TORANGE = K.emit_mat('PDOrange', COL['terran_orange'], 2.0)


def cyl(name, r, depth, mat, verts=16):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    return o


class Turret:
    def __init__(self, i, mount):
        self.i = i
        self.mount = mount                      # root-local (frigate root at origin)
        base = cyl(f'PD{i}_Base', 0.85, 0.5, M_TBASE)
        base.parent = frig.root
        base.location = mount + Vector((0, 0, 0.2))
        ring = cyl(f'PD{i}_Ring', 0.9, 0.1, M_TNEON)
        ring.parent = base
        ring.location = (0, 0, 0.12)
        head = K.empty(f'PD{i}_Head')
        head.parent = frig.root
        head.location = mount + Vector((0, 0, 0.75))
        head.rotation_mode = 'QUATERNION'
        dome = K.sphere(f'PD{i}_Dome', 0.62, M_TBASE, seg=(14, 8))
        dome.parent = head
        dome.scale = (1.1, 1.0, 0.7)
        eye = K.sphere(f'PD{i}_Sensor', 0.14, M_TORANGE, seg=(8, 6))
        eye.parent = head
        eye.location = (0.55, 0, 0.22)
        self.head = head
        self.barrels = []
        self.muzzles = []
        self.blen = 2.0
        for k, sy in enumerate((0.24, -0.24)):
            b = cyl(f'PD{i}_Barrel{k}', 0.1, self.blen, M_TBARREL, verts=10)
            b.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y') @ Matrix.Translation((0, 0, self.blen / 2)))
            b.parent = head
            b.location = (0.2, sy, 0.05)
            tip = cyl(f'PD{i}_Tip{k}', 0.13, 0.25, M_TNEON, verts=10)
            tip.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y'))
            tip.parent = b
            tip.location = (self.blen - 0.1, 0, 0)
            m = K.empty(f'PD{i}_Muzzle{k}')
            m.parent = b
            m.location = (self.blen + 0.05, 0, 0)
            self.barrels.append(b)
            self.muzzles.append(m)
        self.aims = {}                          # frame -> world direction
        self.last_shot = -9

    def muzzle_world(self, t, k):
        d = self.dir_at(t)
        side = Vector((0, 0, 1)).cross(d)
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        sy = 0.24 if k == 0 else -0.24
        return F(t) + self.head.location + d * (0.2 + self.blen + 0.05) + side * sy

    def dir_at(self, t):
        f = max(1, min(NF, int(round(P.T(t)))))
        return self.aims.get(f, Vector((1, 0, 0)))

    def key_aim(self, dirf):
        """dirf(t) -> world direction. Keys the head every frame."""
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
        L = self.blen * 0.8
        b.location.x = 0.2
        b.keyframe_insert('location', index=0, frame=f - 1)
        b.location.x = 0.2 - L
        b.keyframe_insert('location', index=0, frame=f + 1)
        b.location.x = 0.2
        b.keyframe_insert('location', index=0, frame=f + 4)


mount_xy = [(9.0, 0.0), (-5.0, 0.0), (1.0, 5.6), (1.0, -5.6)]
turrets = []
for i, (x, y) in enumerate(mount_xy):
    # best (highest) surface point near the requested spot
    best = None
    for dy in (-0.8, -0.4, 0.0, 0.4, 0.8):
        h = top_at(x, y + dy)
        if h is not None and (best is None or h.z > best.z):
            best = h
    if best is None:
        best = Vector((x, y, 3.0))
    print('PD mount', i, tuple(round(c, 2) for c in best))
    turrets.append(Turret(i, best))

frig.path([(0.0, tuple(F(0))), (6.0, tuple(F(6.0)))], interp='LINEAR')

# ------------------------------------------------------------------------------- Stingrays


def catmull(keys, t):
    """Smooth position through [(t, Vector)] keys (Catmull-Rom, clamped ends)."""
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


def VV(x, y, z):
    return Vector((x, y, z))


SR_KEYS = [
    # s1: high and wide, first to die
    [(0.0, VV(236, -6, 22)), (0.8, VV(196, -2, 20)), (1.4, VV(166, -9, 15)), (1.9, VV(142, -5, 13.5)), (2.4, VV(118, -4, 12))],
    # s2: high right, jinks
    [(0.0, VV(252, 16, 27)), (0.9, VV(204, 11, 23)), (1.7, VV(162, 12, 16)), (2.5, VV(118, 5, 12)), (3.0, VV(92, 4, 11))],
    # s3: low left, dives in, dies close to the camera
    [(0.0, VV(258, -24, 8)), (1.0, VV(204, -22, 9)), (2.0, VV(150, -18, 8)), (2.8, VV(100, -17, 7)),
     (3.25, VV(68, -15, 7)), (3.55, VV(46, -12, 7)), (4.0, VV(20, -10, 6))],
    # s4: the leader (chase target), last to die, off the bow
    [(0.0, VV(264, 2, 14)), (1.0, VV(208, 1, 13)), (2.0, VV(152, -1, 12)), (2.8, VV(108, -5, 11)),
     (3.25, VV(80, -7, 10)), (3.65, VV(56, -10, 9)), (4.0, VV(36, -13, 8)), (4.35, VV(31, -19, 3.5)),
     (4.8, VV(26, -25, 1.5))],
]
T_DIE = [1.9, 2.5, 3.55, 4.35]


# compress the far end of the approach so the wave reads in the opening shot
SR_KEYS = [[(t, VV(60 + (p.x - 60) * 0.55, p.y, p.z) if p.x > 60 else p) for t, p in ks] for ks in SR_KEYS]


def S(i, t):
    return catmull(SR_KEYS[i], t)


def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, t1, bank=0.012, roll0=0.0):
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    prev = None
    dt = 1.0 / FPS
    for f in range(1, min(NF, int(P.T(t1)) + 2) + 1):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt) - posf(t - dt)) / (2 * dt)
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        lat = a - v.normalized() * a.dot(v.normalized())
        side = Vector((0, 0, 1)).cross(v).normalized()
        roll = max(-1.0, min(1.0, lat.dot(side) * bank)) + roll0 * math.sin(t * 2.3)
        m3 = frame_from(v, Vector((0, 0, 1))) @ Matrix.Rotation(roll, 3, 'X')
        q = m3.to_quaternion()
        if prev is not None:
            q.make_compatible(prev)
        prev = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
    K.set_interp(r, 'LINEAR')


rays = []
for i in range(4):
    a = P.load('arcadian_stingray', at=(0, 0), size=SR_SIZE, label=f'stingray{i}')
    fly(a, lambda t, i=i: S(i, t), T_DIE[i], roll0=0.15)
    rays.append(a)

# local tail point of the Stingray (model nose +X, centred)
bpy.context.view_layer.update()
sm = max(rays[0].meshes, key=lambda o: len(o.data.vertices))
inv0 = rays[0].root.matrix_world.inverted()
pts0 = [inv0 @ (sm.matrix_world @ Vector(c)) for c in sm.bound_box]
SX0 = min(p.x for p in pts0)
SX1 = max(p.x for p in pts0)
SZM = (min(p.z for p in pts0) + max(p.z for p in pts0)) / 2
print('stingray local x', SX0, SX1, 'zm', SZM)


def reparent_new(before, parent):
    for o in bpy.data.objects:
        if o not in before and o.parent is None:
            o.parent = parent


# gold lightning thrusters (kit lightning, built in the ship's local space, ridden by its root)
for i, a in enumerate(rays):
    t_end = T_DIE[i] + 1 / FPS
    t = 0.0
    while t < t_end:
        t1 = min(t_end, t + 1.0)
        for sgn in (1, -1):
            before = set(bpy.data.objects)
            p0 = Vector((SX0 + 0.55 * (SX1 - SX0) * 0.35, 0.32 * sgn, SZM))
            p1 = p0 + Vector((-3.0, 0.5 * sgn, 0.0))
            P.lightning(p0, p1, t, t1, color=COL['arc_gold'], width=0.06, jag=0.18, branches=1, segs=7, glow=False)
            reparent_new(before, a.root)
        t = t1

# ------------------------------------------------------------------------------- Stingray bolts
SHOTS = [(3, 2.85), (2, 3.3), (3, 3.95)]
for i, t in SHOTS:
    a = rays[i]
    p0 = S(i, t)
    v = (S(i, t + 0.02) - S(i, t - 0.02)).normalized()
    p0 = p0 + v * (SX1 + 0.1)
    c = F(t)
    aim = c + Vector((R.uniform(-4, 6), 0, R.uniform(0, 2))) - p0
    hit_local = hull_ray(p0 - c, aim)
    p1 = (hit_local + c) if hit_local is not None else c
    L = (p1 - p0).length
    P.lightning(p0, p1, t, t + 0.22, color=COL['arc_gold'], width=0.1 if L > 40 else 0.08,
                jag=min(0.3, 6.0 / L), branches=2, segs=max(10, int(L / 3)), glow=False)
    P.impact(p1 + FV * 0.1, t + 0.02, size=1.4, color=COL['arc_gold'])

# ------------------------------------------------------------------------------- PD fire control
# Who each turret engages when (time windows), with the kill moments.
ENGAGE = [(1.2, T_DIE[0], 0), (T_DIE[0] + 0.1, T_DIE[1], 1), (T_DIE[1] + 0.1, T_DIE[2], 2),
          (T_DIE[2] + 0.08, T_DIE[3], 3)]
TRACER_SPEED = 230.0


def target_at(t):
    for a_, b_, i in ENGAGE:
        if a_ - 0.35 <= t <= b_ + 0.05:
            return i
    return None


def lead_point(i, p0, t):
    tt = t
    for _ in range(3):
        tof = (S(i, tt) - p0).length / TRACER_SPEED
        tt = t + tof
    return S(i, tt), tof


# turret pointing: rest forward-ish until 0.85, then track the current target
REST = [Vector((1, 0, 0.15)), Vector((-1, 0.2, 0.25)), Vector((0.3, 1, 0.2)), Vector((0.3, -1, 0.2))]
for k, tu in enumerate(turrets):
    def dirf(t, tu=tu, k=k):
        base = F(t) + tu.head.location
        rest = REST[k].normalized()
        i = target_at(t)
        if i is None and t < 1.2:
            i = 0
        if i is None:
            # after the last kill: ease back toward rest
            i = 3
            dl = (S(i, T_DIE[3]) - base).normalized()
            u = ss((t - T_DIE[3] - 0.4) / 0.9)
            return dl.lerp(rest, u * 0.6)
        tgt, _ = lead_point(i, base, t)
        d = (tgt - base).normalized()
        # swing-in from rest at the start, and quick slews between targets
        if t < 1.25:
            u = ss((t - 0.3) / 0.9)
            return rest.lerp(d, u).normalized()
        for a_, b_, j in ENGAGE[1:]:
            if a_ - 0.35 <= t < a_ and j == i:
                prev_i = j - 1
                dp = (S(prev_i, T_DIE[prev_i]) - base).normalized()
                u = ss((t - (a_ - 0.35)) / 0.35)
                return dp.lerp(d, u).normalized()
        return d
    tu.key_aim(dirf)

# firing: each turret alternates barrels; own rhythm per turret
RATE = [0.085, 0.095, 0.09, 0.1]
for k, tu in enumerate(turrets):
    t = 1.25 + 0.03 * k
    shot = 0
    while t < T_DIE[3] + 0.02:
        i = target_at(t)
        # short pauses between targets
        if i is None or not any(a_ <= t <= b_ for a_, b_, _ in ENGAGE):
            t += RATE[k]
            continue
        bk = shot % 2
        p0 = tu.muzzle_world(t, bk)
        tgt, tof = lead_point(i, p0, t)
        kill = T_DIE[i]
        hitting = kill - 0.22 <= t + tof <= kill + 0.01
        err = 0.6 if hitting else lerp(7.0, 2.0, ss((t + tof - (kill - 1.0)) / 1.0))
        aimp = tgt + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))) * err
        far = p0 + (aimp - p0).normalized() * (aimp - p0).length * (1.0 if hitting else 1.6)
        P.projectile(p0, far, t, TRACER_SPEED, COL['tracer'], size=0.16)
        P.muzzle_flash(tu.muzzles[bk], t, COL['fire'], size=0.7)
        tu.recoil(t, bk)
        if hitting and R.random() < 0.6:
            P.impact(aimp, t + tof, size=0.9)
        shot += 1
        t += RATE[k] * R.uniform(0.9, 1.15)
        if shot % 9 == 0:
            t += 0.12                       # breathe between bursts

# ------------------------------------------------------------------------------- kills
for i, a in enumerate(rays):
    t = T_DIE[i]
    p = S(i, t)
    before = set(bpy.data.objects)
    P.explosion(p, t, size=(2.6, 2.6, 2.4, 2.6)[i], debris=14, smoke=True)
    for o in bpy.data.objects:
        if o not in before and o.name.startswith('Scorch'):
            bpy.data.objects.remove(o, do_unlink=True)
    a.vanish(t + 1 / FPS)
    # tumbling wing fragments carry on along the flight path
    v = (S(i, t + 0.02) - S(i, t - 0.02)) / 0.04
    for n in range(3):
        frag = K.ico('SRFrag', 1.0, P.charred, sub=0)
        frag.scale = (0.7, 0.35, 0.08)
        dv = v * 0.35 + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))) * 9
        f0 = int(P.T(t))
        for f in range(f0, NF + 1, 2):
            tt = (f - f0) / FPS
            frag.location = p + dv * tt
            frag.rotation_euler = (tt * R.uniform(4, 9), tt * 6, tt * 3)
            frag.keyframe_insert('location', frame=f)
            frag.keyframe_insert('rotation_euler', frame=f)
        K.show_between(frag, f0, NF + 1)
        P.puff(p, t + 0.05 * n, size=1.2, n=1, rise=0.5, life=1.4, color=(0.18, 0.17, 0.16), opacity=0.4)

# ------------------------------------------------------------------------------- camera
keys = []
# Shot A: low on the frigate's starboard flank, dolly forward, looking up-range
for t, cp, lk, lens in [
    (0.0, VV(-52, -17, 3.0), VV(60, -4, 2.0), 44),
    (0.75, VV(-46, -16, 3.3), VV(62, -4, 2.5), 45),
    (T_CUT1 - 1 / FPS, VV(-40, -15, 3.6), VV(64, -4, 3.0), 46),
]:
    keys.append((t, tuple(cp), tuple(lk), lens))
# Shot B: chase behind the Stingray leader, frigate and Dreadnought ahead
for t in [T_CUT1, 1.85, 2.2, 2.55, 2.9, T_CUT2 - 1 / FPS]:
    s = S(3, t)
    cp = s + Vector((10.0, 4.0, 3.0))
    lk = s + (F(t) - s).normalized() * 30 + Vector((0, 2.0, -1.0))
    keys.append((t, tuple(cp), tuple(lk), 30))
# Shot C: ahead of and a little below the frigate's bow line, looking back down the attack run
for t, cp, lk, lens in [
    (T_CUT2, VV(54, -29, 4.0), VV(18, -8, 5), 28),
    (3.9, VV(51, -28, 3.0), VV(16, -6, 4), 28),
    (4.6, VV(47, -26, 2.0), VV(12, -3, 3), 29),
    (6.0, VV(41, -23, 0.5), VV(8, 0, 2), 30),
]:
    keys.append((t, tuple(cp), tuple(lk), lens))
P.camera(keys, shake=0.03, cuts=(T_CUT1, T_CUT2))
P.cam_shake(T_DIE[2], 0.35, dur=0.4)
P.cam_shake(3.95, 0.15, dur=0.25)
P.cam_shake(T_DIE[3], 0.25, dur=0.4)

P.render()
