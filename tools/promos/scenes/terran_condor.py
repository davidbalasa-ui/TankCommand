"""Condor (Terran heavy bomber): a bomber run over an Arcadian base.

Two Lumens on the edge of the base hear it coming and crack gold lightning straight up at it: the
bolts fizzle out far below. The Condor rumbles overhead on a dead straight line, huge against the
sky, belly bay doors swinging open. Chase shot over its shoulder: three bombs drop out one after
another and fall away toward the domes. Crane down from high over the base: the stick walks
across it, Sentinel, Aerie, Star Vault, each one a fireball with gold cores rupturing, a sifter
and a lumen caught in the blasts. The camera settles low behind the burning line as the Condor,
bay closing, flies on unharmed into the sky.

Timeline (s): 0-1.45 ground camera looks up, lumens fire (0.45, 0.8), bay opens 0.75-1.15 |
1.45-2.85 chase, drops 1.55/2.0/2.45 | 2.85-6 crane down over the base, impacts ~2.9/3.35/3.8,
secondaries, bay closes 3.3, end: low frame along the burning line, Condor departing."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_condor', seconds=6.0, seed=7)
FPS = P.fps
NF = P.nf
R = P.rnd

GOLD = COL['arc_gold']
NEON = COL['terran_neon']

# ------------------------------------------------------------------------------- flight plan
SPEED = 20.0
ALT = 16.0
X0 = -54.0
T_DROP = [1.55, 2.0, 2.45]
G = 16.0              # a touch heavier than real gravity: keeps the fall inside the clip
DRAG = 5.0            # bombs lose forward speed and trail behind the bomber
T_BAY0, T_BAY1 = 0.75, 1.15
T_BAYC0, T_BAYC1 = 3.2, 3.6


def plane_pos(t):
    return Vector((X0 + SPEED * t, 0.0, ALT))


def ss(x):
    return K.smoothstep(x)


# Condor local points (root space: +X nose, root at hull mid-height)
C_H = None  # set after load
TARGET_H = [2.4, 3.6, 2.6]   # sentinel / aerie / star vault roof heights where bombs burst


def bomb_state(i, t, z0):
    """Bomb i world position + velocity at time t (after release)."""
    td = T_DROP[i]
    tau = max(0.0, t - td)
    x0 = plane_pos(td).x
    x = x0 + SPEED * tau - 0.5 * DRAG * tau * tau
    z = z0 - 0.5 * G * tau * tau - 1.2 * tau
    vel = Vector((SPEED - DRAG * tau, 0.0, -G * tau - 1.2))
    return Vector((x, 0.0, z)), vel


def bomb_impact(i, z0, h):
    t = T_DROP[i]
    while True:
        p, _ = bomb_state(i, t, z0)
        if p.z <= h:
            return t, p
        t += 1 / 240


# ------------------------------------------------------------------------------- world
condor = P.load('condor', label='condor')
C_H = condor.entry['height']
condor.model_root.location.z = -C_H / 2
ZC = -C_H / 2
BELLY = 0.37 + ZC                       # fuselage underside between the nacelles
BOMB_Z0 = ALT + BELLY - 0.2
IMPACTS = [bomb_impact(i, BOMB_Z0, TARGET_H[i]) for i in range(3)]
print('IMPACTS', IMPACTS)
TX = [p.x for _, p in IMPACTS]

P.env('alien', sun=(55, 0, 140), sun_energy=4.2, props=30,
      clear=[(TX[1], 0, 22), (-26, 0, 14)])
P.flatten(TX[1], 0, 22)
P.flatten(-26, 0, 12)

# ------------------------------------------------------------------------------- the base
sentinel = P.load('sentinel', at=(TX[0], 0.0), heading=20, label='sentinel')
aerie = P.load('aerie', at=(TX[1], 0.0), heading=-15, label='aerie')
vault = P.load('star_vault', at=(TX[2], 0.0), heading=40, label='star_vault')
sifter = P.load('sifter', at=(TX[1] + 1.5, -6.6), heading=160, label='sifter')
sifter.spin('GrinderPivot', 540, 0.0, 6.0, axis=1)
lumen_base = P.load('lumen', at=(TX[2] + 1.0, 6.4), heading=-120, label='lumen_base')
lumen_base.hover_bob(0.07, 0.8)
print('target heights', sentinel.entry['height'], aerie.entry['height'], vault.entry['height'])

# gold glow on the domes (living base before the strike)
for s_, h_ in ((sentinel, 2.0), (aerie, 3.2), (vault, 2.4)):
    L = K.link(bpy.data.objects.new('DomeGlow', bpy.data.lights.new('DomeGlow', 'POINT')))
    L.location = s_.pos_at(0) + Vector((0, 0, h_))
    L.data.color = GOLD
    L.data.energy = 250
    L.data.shadow_soft_size = 1.0

# two lumens on the outskirts, under the bomber's approach
lumA = P.load('lumen', at=(-29.0, -6.5), heading=170, label='lumenA')
lumB = P.copy(lumA, at=(-24.5, 5.0), heading=-160, label='lumenB')
for a in (lumA, lumB):
    a.hover_bob(0.08, 0.9)

# ------------------------------------------------------------------------------- materials
_mats = {}


def mat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('C_' + key, col, strength, alpha=alpha)
    return _mats[key]


HULL = K.pbr_mat('BayDoor', (0.05, 0.052, 0.058), rough=0.45, metal=0.6)
BAY_IN = K.pbr_mat('BayInside', (0.012, 0.012, 0.014), rough=0.8)
BOMB_M = K.pbr_mat('BombBody', (0.16, 0.165, 0.17), rough=0.4, metal=0.7)
BAND = mat('BombBand', COL['terran_orange'], 2.0)
TIP = mat('BombTip', NEON, 2.0)
M_ENG = mat('Eng', NEON, 2.0)
M_ENG_GLOW = mat('EngGlow', NEON, 1.0, alpha=0.15)
BOLT_M = mat('Bolt', GOLD, 2.4)
BOLT_CORE = mat('BoltCore', (1.0, 0.72, 0.35), 3.0)
BOLT_GLOW = mat('BoltGlow', GOLD, 1.2, alpha=0.3)


# ------------------------------------------------------------------------------- flight
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, rollf=None, pitchf=None):
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev = None
    dt = 1.0 / FPS
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
        m3 = frame_from(v, Vector((0, 0, 1)))
        if pitchf:
            m3 = m3 @ Matrix.Rotation(pitchf(t), 3, 'Y')
        if rollf:
            m3 = m3 @ Matrix.Rotation(rollf(t), 3, 'X')
        q = m3.to_quaternion()
        if prev is not None:
            q.make_compatible(prev)
        prev = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.Translation(p) @ m3.to_4x4()
    K.set_interp(r, 'LINEAR')
    actor.mats = mats


# a heavy aircraft: slow gentle porpoise and wing rock; a little lift as each bomb leaves
def c_roll(t):
    return math.radians(1.2 * math.sin(1.3 * t + 0.4))


def c_pitch(t):
    p = 0.8 * math.sin(0.9 * t)
    for td in T_DROP:
        p -= 1.4 * math.exp(-((t - td - 0.12) / 0.12) ** 2)   # nose rises (negative Y-rot)
    return math.radians(p)


def c_pos(t):
    p = plane_pos(t)
    p.z += 0.15 * math.sin(1.1 * t)
    for td in T_DROP:
        p.z += 0.18 * ss((t - td) / 0.3)       # lighter after each release
    return p


fly(condor, c_pos, c_roll, c_pitch)


def W(t, local):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return condor.mats[f] @ Vector(local)


# ------------------------------------------------------------------------------- bomb bay
BX0, BX1 = -1.75, 0.35          # bay length along the belly (model x)
BW = 0.42                       # half width (between the nacelles)
bay_len = BX1 - BX0
bay_cx = (BX0 + BX1) / 2

inside = K.cube('BayInside', 1.0, BAY_IN)
inside.parent = condor.root
inside.location = (bay_cx, 0, BELLY + 0.02)
inside.scale = (bay_len / 2, BW * 0.98, 0.04)
K.show_between(inside, P.T(T_BAY0), P.T(T_BAYC1) + 1)
bay_light = K.link(bpy.data.objects.new('BayLight', bpy.data.lights.new('BayLight', 'POINT')))
bay_light.parent = condor.root
bay_light.location = (bay_cx, 0, BELLY - 0.15)
bay_light.data.color = COL['terran_orange']
bay_light.data.shadow_soft_size = 0.3
for t, e in ((0, 0), (T_BAY0, 0), (T_BAY1, 60), (T_BAYC0, 60), (T_BAYC1, 0)):
    bay_light.data.energy = e
    bay_light.data.keyframe_insert('energy', frame=P.T(t))

# bay edge strip lights (orange accents) visible when open
for sgn in (1, -1):
    st = K.cube('BayStrip', 1.0, BAND)
    st.parent = condor.root
    st.location = (bay_cx, sgn * (BW - 0.02), BELLY - 0.01)
    st.scale = (bay_len / 2, 0.025, 0.02)
    K.show_between(st, P.T(T_BAY0), P.T(T_BAYC1) + 1)

doors = []
for sgn in (1, -1):
    hinge = K.empty('BayHinge')
    hinge.parent = condor.root
    hinge.location = (bay_cx, sgn * BW, BELLY - 0.03)
    hinge.rotation_mode = 'XYZ'
    d = K.cube('BayDoor', 1.0, HULL)
    d.parent = hinge
    d.location = (0, -sgn * BW / 2, 0)
    d.scale = (bay_len / 2, BW / 2, 0.03)
    # neon seam along the door edge (always visible: a closed bay outline)
    seam = K.cube('BaySeam', 1.0, TIP)
    seam.parent = hinge
    seam.location = (0, -sgn * (BW - 0.02), -0.032)
    seam.scale = (bay_len / 2 * 0.96, 0.012, 0.006)
    for t, a in ((0, 0), (T_BAY0, 0), (T_BAY1, 105), (T_BAYC0, 105), (T_BAYC1, 0)):
        hinge.rotation_euler.x = math.radians(a * sgn)
        hinge.keyframe_insert('rotation_euler', index=0, frame=P.T(t))
    doors.append(hinge)

# ------------------------------------------------------------------------------- bombs
BOMB_L = 1.25
BOMB_R = 0.19
SLOTS = [-1.25, -0.7, -0.15]   # rack positions along the bay (model x); dropped rear first
BOMB_Y = [0.0, 0.0, 0.0]


def make_bomb(name):
    root = K.empty(name)
    root.rotation_mode = 'QUATERNION'
    body = K.sphere('BombBody', 1.0, BOMB_M, seg=(16, 10))
    body.parent = root
    body.scale = (BOMB_L / 2, BOMB_R, BOMB_R)
    band = K.sphere('BombBand', 1.0, BAND, seg=(16, 4))
    band.parent = root
    band.location = (BOMB_L * 0.12, 0, 0)
    band.scale = (0.06, BOMB_R * 1.04, BOMB_R * 1.04)
    tip = K.sphere('BombTip', 1.0, TIP, seg=(10, 6))
    tip.parent = root
    tip.location = (BOMB_L * 0.43, 0, 0)
    tip.scale = (0.1, 0.07, 0.07)
    for k in range(4):
        fin = K.cube('BombFin', 1.0, BOMB_M)
        fin.parent = root
        fin.rotation_mode = 'XYZ'
        fin.rotation_euler.x = math.radians(45 + 90 * k)
        fin.location = (-BOMB_L * 0.42, 0, 0)
        fin.scale = (0.16, 0.012, BOMB_R * 1.5)
    return root


bombs = []
for i in range(3):
    b = make_bomb(f'Bomb{i}')
    td = T_DROP[i]
    t_hit, p_hit = IMPACTS[i]
    f_vis = P.T(T_BAY0 + 0.15)
    f_drop = int(round(P.T(td)))
    f_hit = int(round(P.T(t_hit)))
    # hanging in the bay: follow the bomber
    local = Vector((SLOTS[i], BOMB_Y[i], BELLY - BOMB_R * 0.55))
    prev = None
    z0 = None
    for f in range(0, f_hit + 1):
        t = (f - 1) / FPS
        if f <= f_drop:
            m = condor.mats[max(0, min(NF + 1, f))]
            p = m @ local
            q = m.to_quaternion()
            if f == f_drop:
                z0 = p.z
        else:
            tau = t - td
            x0w = (condor.mats[f_drop] @ local).x
            x = x0w + SPEED * tau - 0.5 * DRAG * tau * tau
            z = z0 - 0.5 * G * tau * tau - 1.2 * tau
            p = Vector((x, 0.0, z))
            vel = Vector((SPEED - DRAG * tau, 0.0, -G * tau - 1.2))
            # nose follows velocity, lagging a little at first; slight wobble
            dirv = Vector((1, 0, 0)).lerp(vel.normalized(), min(1.0, tau / 0.5) * 0.9 + 0.1 * min(1.0, tau / 1.2))
            q = dirv.to_track_quat('X', 'Z')
            q = q @ Matrix.Rotation(0.05 * math.sin(tau * 14 + i), 3, 'Z').to_quaternion()
        if prev is not None:
            q.make_compatible(prev)
        prev = q
        b.location = p
        b.rotation_quaternion = q
        b.keyframe_insert('location', frame=f)
        b.keyframe_insert('rotation_quaternion', frame=f)
    K.set_interp(b, 'LINEAR')
    for o in [b] + list(b.children_recursive):
        K.key_hide(o, 0, True)
        K.key_hide(o, f_vis, False)
        K.key_hide(o, f_hit + 1, True)
    # actual impact point of this bomb (it dropped from the rack, not the bay centre)
    tau_h = (f_hit - 1) / FPS - td
    bombs.append(b)
    # release: clamp clunk puff of hot air + small light
    P.light(W(td, (SLOTS[i], 0, BELLY - 0.3)), td, COL['terran_orange'], energy=300, dur=0.1)

# ------------------------------------------------------------------------------- engines
for sgn in (1, -1):
    eng = Vector((-3.95, 0.5 * sgn, 0.9 + ZC))
    plume = K.sphere('EngPlume', 1.0, M_ENG, seg=(10, 6))
    plume.parent = condor.root
    glow = K.sphere('EngGlow', 1.0, M_ENG_GLOW, seg=(12, 8))
    glow.parent = condor.root
    for f in range(0, NF + 2, 2):
        fl = R.uniform(0.85, 1.12)
        plume.location = eng + Vector((-0.45 * fl, 0, 0))
        plume.scale = (0.55 * fl, 0.16, 0.16)
        glow.location = eng + Vector((-0.5 * fl, 0, 0))
        glow.scale = (1.0 * fl, 0.38, 0.38)
        for o in (plume, glow):
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('scale', frame=f)


# ------------------------------------------------------------------------------- lightning
def jag(p0, p1, segs, amt):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * amt * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
        pts.append(p0 + d * u + off)
    return pts


def bolt_objs(pts, f, width, glow=True, core=True, step=1):
    obs = [K.polyline('CBolt', pts, width, BOLT_M)]
    if core:
        obs.append(K.polyline('CBoltC', pts, width * 0.4, BOLT_CORE))
    if glow:
        obs.append(K.polyline('CBoltG', pts, width * 2.8, BOLT_GLOW))
    for o in obs:
        K.show_between(o, f, f + step)
    return obs


def lumen_shot(lum, t, aim_t, reach=0.55, dur=0.2):
    """Lumen cracks gold lightning up at the bomber; out of range, it frays and fizzles."""
    p0 = lum.pos_at(t) + Vector((0, 0, 1.3))
    tgt = plane_pos(aim_t) + Vector((0, 0, -1.0))
    p1 = p0 + (tgt - p0) * reach
    f0 = int(round(P.T(t)))
    f1 = int(round(P.T(t + dur)))
    for f in range(f0, f1 + 1):
        fade = 1.0 - 0.5 * (f - f0) / max(1, f1 - f0)
        bolt_objs(jag(p0, p1, 12, 0.22), f, 0.07 * fade)
        # fraying tips at the top end
        for _ in range(3):
            dv = ((p1 - p0).normalized() + Vector((R.uniform(-.9, .9), R.uniform(-.9, .9), R.uniform(-.3, .4)))).normalized()
            bolt_objs(jag(p1, p1 + dv * R.uniform(1.2, 2.5), 4, 0.5), f, 0.035, glow=False, core=False)
    P.light(p0 + Vector((0, 0, 0.5)), t, GOLD, energy=1200, dur=dur, radius=0.5)
    P.light(p1, t, GOLD, energy=900, dur=dur, radius=1.0)
    # turret glow flash
    o = K.sphere('LumFlash', 1.0, P.soft_fire_mat(), seg=(10, 8))
    o.color = (*GOLD, 0.9)
    o.location = p0
    for df_, s in ((0, 0.05), (1, 0.6), (4, 0.02)):
        o.scale = (s, s, s)
        o.keyframe_insert('scale', frame=f0 + df_)
    K.show_between(o, f0, f0 + 4)



for a, t in ((lumA, 0.42), (lumB, 0.78), (lumA, 1.12)):
    a.aim(t - 0.3, plane_pos(t + 0.3), dur=0.25)
    lumen_shot(a, t, t + 0.25)


# ------------------------------------------------------------------------------- explosions
def quiet_explosion(pos, t, size, debris=8, scorch=True, smoke=True):
    before = set(bpy.data.objects)
    P.explosion(pos, t, size=size, debris=debris, smoke=smoke)
    for o in set(bpy.data.objects) - before:
        nm = o.name.split('.')[0]
        if nm == 'Core':
            o.data.materials[0] = mat('CoreSoft', (1.0, 0.42, 0.06), 2.5)
            o.scale = o.scale * 0.6
        elif nm == 'Scorch' and not scorch:
            bpy.data.objects.remove(o)


def quiet_destroy(actor, t, size, debris=10):
    before = set(bpy.data.objects)
    actor.destroy(t, size=size, debris=debris)
    for o in set(bpy.data.objects) - before:
        if o.name.split('.')[0] == 'Core' and o.type == 'MESH':
            o.data.materials[0] = mat('CoreSoft', (1.0, 0.42, 0.06), 2.5)
            o.scale = o.scale * 0.6


SAND = (0.42, 0.3, 0.3)


def dust_ring(center, t, r0, r1, n=18, size=1.1, life=1.4, opacity=0.35, rise=0.5):
    c = Vector(center)
    for k, r in enumerate((r0, r1)):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + R.uniform(-0.1, 0.1)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * R.uniform(0.9, 1.1)
            p.z = P.ground_z(p.x, p.y) + 0.25
            P.puff(p, t + 0.08 * k + R.uniform(0, 0.04), size=size * (1 + 0.3 * k),
                   n=1, rise=rise * (1 + k), life=life, color=SAND, opacity=opacity)


def core_rupture(pos, t, n=6, reach=(2.5, 4.5)):
    f0 = int(round(P.T(t)))
    for f in range(f0, f0 + 4):
        for k in range(n):
            dv = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.2, 1))).normalized()
            bolt_objs(jag(pos, pos + dv * R.uniform(*reach), 6, 0.5), f, 0.05, core=(k == 0))
    P.light(pos, t, GOLD, energy=5000, dur=0.25, radius=1.5)


def flash_ring(pos, t, r1):
    """Fast low shock ring of hot air hugging the ground."""
    o = K.sphere('Shock', 1.0, P.soft_fire_mat(), seg=(24, 6))
    o.color = (1.0, 0.45, 0.12, 0.55)
    f0 = P.T(t)
    o.location = (pos.x, pos.y, P.ground_z(pos.x, pos.y) + 0.3)
    for df_, r, h, a in ((0, 0.5, 0.3, 0.7), (3, r1 * 0.6, 0.5, 0.5), (8, r1, 0.4, 0.0)):
        o.scale = (r, r, h)
        o.color = (1.0, 0.45, 0.12, a)
        o.keyframe_insert('scale', frame=f0 + df_)
        o.keyframe_insert('color', frame=f0 + df_)
    K.show_between(o, f0, f0 + 8)


TARGETS = [sentinel, aerie, vault]
SIZES = [4.2, 5.4, 4.6]
for i, (t_hit, p_hit) in enumerate(IMPACTS):
    tgt = TARGETS[i]
    gp = Vector((p_hit.x, 0, P.ground_z(p_hit.x, 0)))
    quiet_explosion(p_hit, t_hit, SIZES[i] * 0.75, debris=6, scorch=False, smoke=False)
    quiet_destroy(tgt, t_hit + 0.04, SIZES[i], debris=16)
    flash_ring(gp, t_hit, SIZES[i] * 1.6)
    core_rupture(gp + Vector((0, 0, TARGET_H[i] * 0.6)), t_hit + 0.12)
    dust_ring(gp, t_hit + 0.05, SIZES[i] * 0.9, SIZES[i] * 1.5, n=14, size=1.3, life=1.6, opacity=0.32)
    # secondary blast a beat later, off to one side
    off = Vector((R.uniform(-1.5, 1.5), R.choice((-1, 1)) * R.uniform(1.5, 2.5), 0.4))
    quiet_explosion(gp + off, t_hit + 0.32, 2.4, debris=6, smoke=True)
    P.fire_patch(gp + Vector((0, 0, 0.6)), t_hit + 0.15, 6.0, size=1.6)
    P.cam_shake(t_hit, 0.28, dur=0.45)

# units caught by the blasts
quiet_destroy(sifter, IMPACTS[1][0] + 0.1, 2.2, debris=8)
quiet_destroy(lumen_base, IMPACTS[2][0] + 0.12, 2.0, debris=8)

# ------------------------------------------------------------------------------- camera
T_C1 = 1.45
T_C2 = 2.85
keys = []
# shot A: on the ground among the lumens, looking up; the bomber passes over, bay opening
CA = Vector((-31.0, -8.5, 1.3))
keys += [
    (0.0, tuple(CA), plane_pos(0.0) * 0.55 + lumA.pos_at(0.0) * 0.45 + Vector((0, 0, 1.0)), 22),
    (0.5, tuple(CA + Vector((0.3, 0.2, 0.05))), plane_pos(0.5) * 0.75 + lumA.pos_at(0.5) * 0.25, 22),
    (1.0, tuple(CA + Vector((0.6, 0.4, 0.1))), plane_pos(1.0) + Vector((0, 0, -0.5)), 24),
    (T_C1 - 1 / FPS, tuple(CA + Vector((0.9, 0.6, 0.1))), plane_pos(T_C1) + Vector((-1.0, 0, -0.5)), 26),
]


# shot B: chase over its shoulder, looking down past the belly at the bombs and the base
def chase(t, u):
    p = plane_pos(t)
    off = Vector((-10.5, -7.5, 4.0)).lerp(Vector((-7.0, -9.5, 2.2)), u)
    look = p + Vector((5.0, 0.0, -6.0)).lerp(Vector((7.0, 0.0, -8.5)), u)
    return p + off, look


n = 6
for k in range(n + 1):
    u = k / n
    t = T_C1 + (T_C2 - 1 / FPS - T_C1) * u
    cp, lk = chase(t, u)
    keys.append((t, tuple(cp), lk, 26))

# shot C: high over the base, craning down and round to a low frame along the burning line
mid = TX[1]
keys += [
    (T_C2, (mid - 20.0, -19.0, 15.0), (mid - 2.0, 0.0, 2.0), 26),
    (3.6, (mid - 22.0, -16.0, 10.0), (mid + 1.0, 0.0, 2.5), 26),
    (4.6, (mid - 23.0, -11.5, 5.0), (mid + 7.0, 0.0, 4.5), 27),
    (6.0, (mid - 24.0, -8.5, 2.6), (mid + 20.0, 0.0, 8.0), 28),
]
P.camera(keys, shake=0.02, cuts=(T_C1, T_C2))
P.cam_shake(1.1, 0.06, dur=0.6)   # engine rumble as it passes over

# effects never cast shadows
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.active_material is not None:
        m = o.active_material
        if 'emit_node' in m or m.name.startswith(('SoftFire', 'Fireball', 'SoftPuff')):
            o.visible_shadow = False

P.render()
