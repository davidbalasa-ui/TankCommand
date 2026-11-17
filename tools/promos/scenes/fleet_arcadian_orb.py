"""Arcadian Orb (anti-fighter, space): the Orb hangs over a blue planet, its eight tentacle legs
drifting like a jellyfish, each leg's own small gold lightning thruster ticking. Far ahead two
Terran Twin-X fighters run. The Orb throws its legs forward, then snaps them back in one power
stroke: every leg thruster flares and it lunges. Twin-X B turns and makes a head-on strafing
pass (3-round bursts that spark off the hull); the Orb ignores it. Its legs swing open like a
claw, close round Twin-X A and drag it in. Three pulses of gold lightning crackle from the leg
tips into the fighter, which bursts inside the cage; the legs fling open and the Orb drifts on
through the debris, legs settling.

Timeline (s): 0-2.0 behind the Orb, Twin-X far ahead; coil 1.15, power stroke 1.45 |
2.0-3.5 side tracking shot of the lunge, B's head-on pass 2.2-2.9 | 3.5-6.0 front 3/4: claw
opens 3.3, closes 3.9, crush pulses 4.15 / 4.4 / 4.65, burst 4.85, legs fling, end on the Orb.

The Orb file is rigged (8 legs x 3 segments, a swivelling nacelle with lightning plume on each
leg). Its baked sample animation is replaced here by a per-frame verlet sim of every leg
(independent phases, real lag and whip against the body's motion)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('fleet_arcadian_orb', seconds=6.0, seed=83)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

P.space(planet=(260, 520, -620, 560, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(58, 0, 150), sun_energy=4.0)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


def win(t, a, b, fade=0.12):
    """1 inside [a, b], smooth ramps of `fade` s outside."""
    return ss((t - a) / fade + 1) * (1 - ss((t - b) / fade))


# ------------------------------------------------------------------------------- flight helpers
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def spline(keys):
    """Catmull-Rom through (t, (x, y, z)) keys, linear extrapolation outside."""
    ks = [(t, Vector(p)) for t, p in keys]
    vel = []
    for i, (t, p) in enumerate(ks):
        a = ks[max(i - 1, 0)]
        b = ks[min(i + 1, len(ks) - 1)]
        vel.append((b[1] - a[1]) / max(1e-4, b[0] - a[0]))

    def f(t):
        if t <= ks[0][0]:
            return ks[0][1] + vel[0] * (t - ks[0][0])
        if t >= ks[-1][0]:
            return ks[-1][1] + vel[-1] * (t - ks[-1][0])
        for i in range(len(ks) - 1):
            t0, p0 = ks[i]
            t1, p1 = ks[i + 1]
            if t0 <= t <= t1:
                h = t1 - t0
                u = (t - t0) / h
                h00 = 2 * u ** 3 - 3 * u ** 2 + 1
                h10 = u ** 3 - 2 * u ** 2 + u
                h01 = -2 * u ** 3 + 3 * u ** 2
                h11 = u ** 3 - u ** 2
                return p0 * h00 + vel[i] * (h10 * h) + p1 * h01 + vel[i + 1] * (h11 * h)
    return f


def bank_up(k=1.0, clamp=55):
    def up(t, p, v, a):
        vn = v.normalized()
        lat = a - vn * a.dot(vn)
        u = (Vector((0, 0, 9.8)) + lat * k).normalized()
        ang = math.degrees(math.acos(max(-1, min(1, u.z))))
        if ang > clamp:
            h = Vector((u.x, u.y, 0)).normalized()
            c = math.radians(clamp)
            u = h * math.sin(c) + Vector((0, 0, math.cos(c)))
        return u
    return up


def mat_at(posf, upf, t, roll_extra=None, fwd_override=None):
    dt = 1.0 / FPS
    p = posf(t)
    v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
    a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
    fwd = fwd_override(t, v) if fwd_override else v
    m3 = frame_from(fwd, upf(t, p, v, a))
    if roll_extra:
        m3 = m3 @ Matrix.Rotation(roll_extra(t), 3, 'X')
    return Matrix.Translation(p) @ m3.to_4x4()


def key_mats(actor, matf):
    """Key root location + quaternion every frame from matf(t) -> 4x4."""
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        m = matf(t)
        q = m.to_quaternion()
        if prev_q is not None:
            q.make_compatible(prev_q)
        prev_q = q
        r.location = m.translation
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.LocRotScale(m.translation, q, None)
    K.set_interp(r, 'LINEAR')
    actor.mats = mats
    return mats


def W(actor, t, local=(0, 0, 0)):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


# Everything is keyed in a frame cruising along +X.
U = Vector((20, 0, 0))


def F(t):
    return U * t


def rel(keys):
    return spline([(t, F(t) + Vector(p)) for t, p in keys])


# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 48 / 24, 84 / 24          # 2.0, 3.5
T_COIL, T_STROKE = 1.15, 1.45
T_OPEN, T_CATCH = 3.25, 3.9
T_PULSES = (4.15, 4.4, 4.65)
T_BURST = 4.85

# ------------------------------------------------------------------------------- the Orb
S = 1.3                                  # model units -> metres (body ~12 m, legs ~15 m)
orb = P.load('arcadian_orb', label='orb')
inner = orb.model_root.children[0]
inner.scale = (S, S, S)
inner.location = (0, 0, 0)
BODY = bpy.data.objects['Orb']
BODY.animation_data_clear()
BODY.rotation_mode = 'QUATERNION'
BODY.location = (0, 0, 0)
BODY.rotation_quaternion = Quaternion()

orb_pos = rel([
    (-0.6, (-2.5, 0, -0.3)),
    (0.0, (0, 0, 0)),
    (0.8, (1.6, 0.2, 0.2)),
    (T_COIL, (2.2, 0.3, 0.3)),
    (T_STROKE, (2.0, 0.3, 0.4)),
    (2.1, (9, 0.8, 1.2)),
    (3.0, (34, 1.8, 2.0)),
    (T_CATCH, (56, 2.0, 2.2)),
    (4.5, (63, 2.2, 2.4)),
    (5.2, (66.5, 2.6, 2.9)),
    (6.0, (68.5, 3.0, 3.4)),
    (6.6, (69.8, 3.2, 3.6)),
])


def orb_fwd(t, v):
    # keep the nose roughly ahead while it drifts slowly (no flip on near-zero speed)
    return v + Vector((14, 0, 0))


orb_up = bank_up(0.5, 30)


def orb_mat(t):
    m = mat_at(orb_pos, orb_up, t, fwd_override=orb_fwd)
    # a little body pitch: nose dips into the power stroke, kicks back at the burst
    pitch = math.radians(-6) * win(t, T_STROKE, 2.0, 0.2) + math.radians(8) * math.exp(-max(0, t - T_BURST) * 3) * (t > T_BURST)
    yaw = math.radians(5) * math.sin(1.3 * t)
    return m @ (Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'Y'))


key_mats(orb, orb_mat)

# Arcadian hull: etched silver-bronze with gold glow (the file's shell is all gold).
SHELL_RECOL = {
    'zone_shell': ((0.80, 0.78, 0.74), (0.52, 0.40, 0.26)),
    'zone_pale': ((0.78, 0.76, 0.72), (0.56, 0.46, 0.32)),
    'zone_bronze': ((0.58, 0.40, 0.20), (0.40, 0.26, 0.12)),
    'zone_under': ((0.42, 0.33, 0.22), (0.28, 0.20, 0.11)),
}
for m in bpy.data.materials:
    base = m.name.split('.')[0]
    if not m.node_tree:
        continue
    if base in SHELL_RECOL:
        a, b = SHELL_RECOL[base]
        for n in m.node_tree.nodes:
            if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA':
                ia, ib = n.inputs[6], n.inputs[7]
                if not ia.is_linked and tuple(ia.default_value)[0] > 0.2:
                    ia.default_value = (*a, 1)
                if not ib.is_linked and tuple(ib.default_value)[0] > 0.2:
                    ib.default_value = (*b, 1)
    if base in SHELL_RECOL or base == 'zone_glow':
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Emission Color'].default_value = (*GOLD, 1)
    if base == 'zone_core':
        # the rear core disc must not read as a body thruster (thrusters are on the legs only)
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                sock = n.inputs['Emission Strength']
                for l in list(sock.links):
                    m.node_tree.links.remove(l)
                sock.default_value = 0.6
                n.inputs['Emission Color'].default_value = (*GOLD, 1)
    elif base == 'zone_glow':
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Emission Color'].default_value = (*GOLD, 1)
                n.inputs['Emission Strength'].default_value = 2.6
    elif base == 'OrbBoltCoreM':
        for n in m.node_tree.nodes:
            if n.type == 'EMISSION':
                n.inputs['Strength'].default_value = 2.6
# the big zone_glow disc on the tail read as a body engine: thrusters are on the legs only, so
# the tail cap gets a dim bronze with a faint gold glow
_me = BODY.data
_gi = [i for i, m_ in enumerate(_me.materials) if m_ and m_.name.split('.')[0] == 'zone_glow']
if _gi:
    _me.materials.append(K.pbr_mat('OrbTailCap', (0.30, 0.20, 0.10), rough=0.35, metal=0.85,
                                   emit=GOLD, emit_strength=0.35))
    _ti = len(_me.materials) - 1
    for pl in _me.polygons:
        if pl.material_index in _gi and pl.center.x < -3.6:
            pl.material_index = _ti
for o in bpy.data.objects:
    if o.type == 'LIGHT' and o.name.startswith('OrbLeg'):
        o.data.energy = min(o.data.energy, 60)

# ------------------------------------------------------------------------------- leg rig
NL = 8
LENS = (3.0, 3.4, 5.3)                    # model units: seg0 -> seg1 -> seg2 -> tip
legs = []
for i in range(NL):
    s0 = bpy.data.objects[f'OrbLeg{i}Seg0']
    a = s0.location.copy()
    r = Vector((0, a.y, a.z)).normalized()
    legs.append(dict(i=i, anchor=a, r=r, tang=Vector((1, 0, 0)).cross(r),
                     segs=[bpy.data.objects[f'OrbLeg{i}Seg{k}'] for k in range(3)],
                     nac=bpy.data.objects[f'OrbLeg{i}Nacelle'], plume=bpy.data.objects[f'OrbLeg{i}Plume'],
                     ph=R.uniform(0, 2 * math.pi), hz=R.uniform(0.55, 0.95), amp=R.uniform(0.7, 1.15),
                     ph2=R.uniform(0, 2 * math.pi)))
    for o in legs[-1]['segs'] + [legs[-1]['nac'], legs[-1]['plume']]:
        o.animation_data_clear()
        o.rotation_mode = 'QUATERNION'

X = Vector((1, 0, 0))


def dirv(r, tang, back, out, side=0.0):
    """Body-local direction: back (-X) / forward (+X) by `back` sign, radial `out`, swirl `side`."""
    return (X * back + r * out + tang * side).normalized()


def pose(L, t):
    """Target body-local directions of the three segments of leg L at time t."""
    r, tg = L['r'], L['tang']
    w = 2 * math.pi * L['hz']
    und = [L['amp'] * math.sin(w * t + L['ph'] - k * 1.1) for k in range(3)]
    sw = [0.35 * L['amp'] * math.sin(0.7 * w * t + L['ph2'] - k * 0.9) for k in range(3)]
    # drift: open jellyfish, legs trailing loosely
    drift = [dirv(r, tg, -0.55, 1.0 + 0.25 * und[0], sw[0]),
             dirv(r, tg, -1.0, 0.55 + 0.35 * und[1], sw[1]),
             dirv(r, tg, -1.0, 0.15 + 0.45 * und[2], sw[2])]
    # coil: legs thrown forward and wide before the stroke
    coil = [dirv(r, tg, 0.45, 1.0), dirv(r, tg, 0.2, 1.0), dirv(r, tg, -0.3, 1.0)]
    # stream: tight trailing bundle while lunging, small whipping waves
    stream = [dirv(r, tg, -1.0, 0.45, 0.1 * sw[0]),
              dirv(r, tg, -1.0, 0.12 + 0.12 * und[1], 0.25 * sw[1]),
              dirv(r, tg, -1.0, -0.02 + 0.2 * und[2], 0.4 * sw[2])]
    # claw: swung forward, splayed open
    claw = [dirv(r, tg, 0.55, 1.0), dirv(r, tg, 1.0, 0.75), dirv(r, tg, 1.0, 0.12)]
    # grab: wrapped round the fighter ahead of the nose, tips curling in
    grab = [dirv(r, tg, 0.65, 0.85), dirv(r, tg, 1.0, 0.18), dirv(r, tg, 0.75, -0.62)]
    # fling: blown open by the burst
    fling = [dirv(r, tg, 0.15, 1.0, 0.2), dirv(r, tg, -0.2, 1.0, 0.3), dirv(r, tg, -0.6, 1.0, 0.3)]
    st = L['i'] * 0.018                   # each leg moves on its own beat
    wts = [
        (drift, 1.0),
        (coil, win(t, T_COIL + st, T_STROKE - 0.06 + st, 0.12)),
        (stream, ss((t - T_STROKE - st) / 0.08) * (1 - ss((t - T_OPEN - st) / 0.25))),
        (claw, ss((t - T_OPEN - st) / 0.25) * (1 - ss((t - T_CATCH + 0.12 - st) / 0.2))),
        (grab, ss((t - T_CATCH + 0.12 - st) / 0.2) * (1 - ss((t - T_BURST - 0.02) / 0.06))),
        (fling, win(t, T_BURST, T_BURST + 0.35, 0.06)),
    ]
    out = []
    for k in range(3):
        acc = Vector()
        tot = 0.0
        for dirs, wt in wts:
            if wt > 1e-4:
                if dirs is drift:
                    wt = max(0.0, 1.0 - sum(w_ for d_, w_ in wts[1:]))
                acc += dirs[k] * wt
                tot += wt
        out.append(acc.normalized() if acc.length > 1e-6 else drift[k])
    return out


def stiff(t):
    """Spring stiffness towards the pose (1/s^2): soft drifting, hard during the claw/grab."""
    k = 30.0
    k += 90.0 * win(t, T_COIL, T_STROKE + 0.15, 0.1)
    k += 40.0 * win(t, T_STROKE + 0.15, T_OPEN, 0.2)
    k += 160.0 * win(t, T_OPEN, T_BURST, 0.12)
    k += 60.0 * win(t, T_BURST, T_BURST + 0.3, 0.05)
    return k


def body_M(t):
    return orb_mat(t) @ Matrix.Scale(S, 4)


def simulate_legs():
    """Verlet chains in world space: each joint springs to its pose target, lags the body's
    motion and whips; lengths are held exactly. Returns per-frame world joint lists."""
    SUB = 6
    dt = 1.0 / FPS / SUB
    t0 = -30 / FPS
    res = {L['i']: {} for L in legs}
    state = {}
    for L in legs:
        M = body_M(t0)
        d = pose(L, t0)
        p = [L['anchor'].copy()]
        for k in range(3):
            p.append(p[-1] + d[k] * LENS[k])
        w = [M @ q for q in p]
        state[L['i']] = (w, [q.copy() for q in w])
    nsteps = int(round((6.1 - t0) * FPS * SUB))
    for s in range(nsteps + 1):
        t = t0 + s * dt
        M = body_M(t)
        R3 = M.to_3x3()
        kk = stiff(t)
        for L in legs:
            cur, prev = state[L['i']]
            d = pose(L, t)
            tgt = [M @ L['anchor']]
            q = L['anchor'].copy()
            for k in range(3):
                q = q + d[k] * LENS[k]
                tgt.append(M @ q)
            new = [tgt[0]]
            for j in range(1, 4):
                vel = (cur[j] - prev[j]) * (1 - 5.0 * dt)
                # stiffer near the root, looser at the tip (whip)
                kj = kk * (1.25, 0.9, 0.6)[j - 1]
                acc = (tgt[j] - cur[j]) * kj
                new.append(cur[j] + vel + acc * dt * dt)
            # length constraints (anchor fixed)
            for _ in range(3):
                for j in range(1, 4):
                    Lk = LENS[j - 1] * S
                    dv = new[j] - new[j - 1]
                    n_ = dv.length or 1e-6
                    new[j] = new[j - 1] + dv * (Lk / n_)
            # keep out of the body (ellipsoid in body space)
            Minv = M.inverted()
            for j in range(1, 4):
                bl = Minv @ new[j]
                rr = math.hypot(bl.y, bl.z)
                e = ((bl.x - 0.45) / 5.4) ** 2 + (rr / 2.7) ** 2
                if e < 1.0 and rr > 1e-4:
                    sc_ = 1.0 / math.sqrt(e)
                    bl = Vector((0.45 + (bl.x - 0.45) * sc_, bl.y * sc_, bl.z * sc_))
                    new[j] = M @ bl
            state[L['i']] = (new, cur)
            if s % SUB == 0:
                res[L['i']][int(round(P.T(t0))) + s // SUB] = [v.copy() for v in new]
        del R3
    return res


SIM = simulate_legs()
TIPS = {}            # (leg, frame) -> world tip point (FK, matches the render)
NACS = {}


def key_legs():
    for L in legs:
        i = L['i']
        segs = L['segs']
        for f in range(0, NF + 2):
            t = (f - 1) / FPS
            M = body_M(t)
            Mr = orb_mat(t).to_3x3().normalized()
            j = SIM[i].get(f)
            if j is None:
                continue
            rad_w = (Mr @ L['r']).normalized()
            up = rad_w
            parent_rot = Mr
            p = j[0]
            for k in range(3):
                xd = (j[k + 1] - j[k]).normalized()
                z = (up - xd * up.dot(xd))
                if z.length < 1e-4:
                    z = rad_w - xd * rad_w.dot(xd)
                z.normalize()
                y = z.cross(xd)
                Wk = Matrix((xd, y, z)).transposed()
                loc = parent_rot.inverted() @ Wk
                q = loc.to_quaternion()
                if f > 0:
                    q.make_compatible(segs[k].rotation_quaternion)
                segs[k].rotation_quaternion = q
                segs[k].keyframe_insert('rotation_quaternion', frame=f)
                if k == 0:
                    W0 = Wk
                parent_rot = Wk
                up = z
                p = p + xd * LENS[k] * S
            TIPS[(i, f)] = p
            # nacelle: thrust direction in body space; the plume streams the opposite way
            lunge = win(t, T_STROKE, T_OPEN + 0.2, 0.08)
            brake = win(t, T_CATCH, T_BURST, 0.1)
            back = 0.55 + 0.45 * lunge - 0.25 * brake
            jit = 0.25 * math.sin(2 * math.pi * 1.7 * t + L['ph'] * 3)
            thrust_b = (X * back - L['r'] * (1 - back) * 0.9 + L['tang'] * jit).normalized()
            thrust_w = Mr @ thrust_b
            zt = rad_w - thrust_w * rad_w.dot(thrust_w)
            zt.normalize()
            Wn = Matrix((thrust_w, zt.cross(thrust_w), zt)).transposed()
            qn = (W0.inverted() @ Wn).to_quaternion()
            if f > 0:
                qn.make_compatible(L['nac'].rotation_quaternion)
            L['nac'].rotation_quaternion = qn
            L['nac'].keyframe_insert('rotation_quaternion', frame=f)
            # plume throttle (X scale = length), each leg flickering on its own
            idle = 0.22 + 0.06 * math.sin(2 * math.pi * 2.3 * t + L['ph'])
            thr = idle
            thr += 0.55 * win(t, T_STROKE + i * 0.02, T_OPEN, 0.06)
            thr -= 0.12 * win(t, T_COIL, T_STROKE, 0.05)
            thr += 0.18 * win(t, T_CATCH, T_BURST, 0.08)
            thr *= R.uniform(0.85, 1.12)
            wd = 0.55 + 0.3 * min(1.0, thr)
            L['plume'].scale = (max(0.08, thr), wd, wd)
            L['plume'].keyframe_insert('scale', frame=f)
        for o in segs + [L['nac'], L['plume']]:
            K.set_interp(o, 'LINEAR')


key_legs()


def tip(i, t):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return TIPS[(i, f)]


# ------------------------------------------------------------------------------- Twin-X
CATCH_LOCAL = Vector((12.0, 0, 0.2))
twA = P.load('terran_twinx', size=8.5, label='twinA')
twB = P.load('terran_twinx', label='twinB')

_catch_w = orb_mat(T_CATCH) @ CATCH_LOCAL
_cw = _catch_w - F(T_CATCH)
a_pos_free = rel([
    (-0.6, (40, -7, 5.5)),
    (0.0, (42, -6, 4.5)),
    (0.9, (47, 3, 3.0)),
    (1.8, (55, -3, 4.5)),
    (2.6, (63, 3.5, 2.5)),
    (3.3, (66.5, -1.0, 2.8)),
    (T_CATCH, tuple(_cw)),
    (4.3, tuple(_cw + Vector((4, 0, 0)))),
])


def a_roll(t):
    return math.radians(55) * math.sin(2.6 * (t - 0.3)) * ss(t / 0.6) + 2 * math.pi * ss((t - 2.55) / 0.6)


def twA_mat(t):
    free = mat_at(a_pos_free, bank_up(0.8, 65), t, roll_extra=a_roll)
    held = orb_mat(t) @ Matrix.Translation(CATCH_LOCAL) @ (
        Matrix.Rotation(math.radians(14) * math.sin(31 * t), 4, 'X') @
        Matrix.Rotation(math.radians(6) * math.sin(23 * t + 1), 4, 'Z') @
        Matrix.Rotation(math.radians(5) * math.sin(19 * t + 2), 4, 'Y'))
    u = ss((t - T_CATCH + 0.06) / 0.14)
    if u <= 0:
        return free
    if u >= 1:
        return held
    q = free.to_quaternion().slerp(held.to_quaternion(), u)
    return Matrix.LocRotScale(free.translation.lerp(held.translation, u), q, None)


key_mats(twA, twA_mat)

# B: far ahead, turns back and makes a head-on strafing pass beside the Orb.
b_pos = rel([
    (-0.6, (112, 22, 9)),
    (0.0, (110, 20, 8)),
    (1.2, (100, 16, 7)),
    (2.0, (78, 12, 6.5)),
    (2.6, (52, 9, 6.5)),
    (3.0, (30, 9.5, 8)),
    (3.5, (4, 14, 11)),
    (4.2, (-26, 22, 14)),
    (6.0, (-100, 40, 20)),
])
key_mats(twB, lambda t: mat_at(b_pos, bank_up(0.6, 60), t))

# Terran glow: the placeholder ships glow violet; tint scene copies to neon blue + orange.
TINT = {'twinx_arc': (NEON, 3.0), 'twinx_haze': (NEON, 0.7), 'twinx_orb': (ORANGE, 2.6)}
for m in bpy.data.materials:
    base = m.name.split('.')[0]
    if not m.node_tree or not base.startswith('twinx'):
        continue
    for n in m.node_tree.nodes:
        if n.type == 'EMISSION':
            c = n.inputs['Color'].default_value
            if base in TINT:
                n.inputs['Color'].default_value = (*TINT[base][0], 1)
                n.inputs['Strength'].default_value = TINT[base][1]
            elif c[2] > 0.6 and c[0] > 0.2 and c[1] < 0.3 * c[2]:
                n.inputs['Color'].default_value = (*NEON, 1)
        elif n.type == 'BSDF_PRINCIPLED':
            c = n.inputs['Emission Color'].default_value
            if c[2] > 0.6 and c[0] > 0.2 and c[1] < 0.3 * c[2]:
                n.inputs['Emission Color'].default_value = (*NEON, 1)

# ------------------------------------------------------------------------------- Twin-X B guns
GTIPS = [(1, 1), (-1, -1), (1, -1), (-1, 1)]
GUN_Y = GUN_Z = 3.79
GUN_TIP_X = 4.45


def split_guns(actor):
    """Cut the four wingtip barrels out of the wing mesh onto rear pivots (telescoping recoil)."""
    wing = [o for o in actor.meshes if o.name.startswith('TwinX_Wings')][0]
    me = wing.data
    mi = [i for i, m in enumerate(me.materials) if m and 'barrel' in m.name][0]
    bpy.context.view_layer.update()
    mw = wing.matrix_world.copy()
    to_root = actor.root.matrix_world.inverted() @ mw
    bm = bmesh.new()
    bm.from_mesh(me)
    groups = {k: [] for k in GTIPS}
    for f in bm.faces:
        if f.material_index != mi:
            continue
        c = to_root @ f.calc_center_median()
        groups[(1 if c.y > 0 else -1, 1 if c.z > 0 else -1)].append(f.index)
    pivots = {}
    for key, idx in groups.items():
        if not idx:
            continue
        b2 = bm.copy()
        b2.faces.ensure_lookup_table()
        keep = set(idx)
        bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
        vs = [v.co.copy() for v in b2.verts]
        xr = [(to_root @ v).x for v in vs]
        x0, x1 = min(xr), max(xr)
        rear = [v for v, x in zip(vs, xr) if x < x0 + 0.1 * (x1 - x0)]
        front = [v for v, x in zip(vs, xr) if x > x1 - 0.1 * (x1 - x0)]
        rc = sum(rear, Vector()) / len(rear)
        fc = sum(front, Vector()) / len(front)
        axis = (fc - rc).normalized()
        nme = bpy.data.meshes.new(actor.name + '_Gun')
        b2.to_mesh(nme)
        b2.free()
        for m in me.materials:
            nme.materials.append(m)
        piv = K.empty(actor.name + '_GunPivot')
        piv.parent = wing
        piv.matrix_parent_inverse = Matrix()
        piv.matrix_basis = Matrix.Translation(rc) @ axis.to_track_quat('X', 'Z').to_matrix().to_4x4()
        gun = K.link(bpy.data.objects.new(actor.name + '_Gun', nme))
        gun.parent = piv
        gun.matrix_parent_inverse = Matrix()
        gun.matrix_basis = piv.matrix_basis.inverted()
        pivots[key] = piv
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == mi], context='FACES')
    bm.to_mesh(me)
    bm.free()
    mz = {}
    for key in GTIPS:
        e = K.empty(actor.name + '_Muzzle')
        e.parent = actor.root
        e.matrix_parent_inverse = Matrix()
        e.location = (GUN_TIP_X, key[0] * GUN_Y, key[1] * GUN_Z)
        mz[key] = e
    actor.gun_pivots = pivots
    actor.gun_muzzles = mz


bpy.context.scene.frame_set(1)
split_guns(twB)


def gun_recoil(actor, key, t):
    piv = actor.gun_pivots.get(key)
    if piv is None:
        return
    f = P.T(t)
    piv.scale = (1, 1, 1)
    piv.keyframe_insert('scale', index=0, frame=f - 1)
    piv.scale = (0.2, 1, 1)
    piv.keyframe_insert('scale', index=0, frame=f + 0.6)
    piv.scale = (1, 1, 1)
    piv.keyframe_insert('scale', index=0, frame=f + 3.5)


def hull_kick(actor, t, kick=1.6, back=0.35):
    m = actor.model_root
    f = P.T(t)
    m.rotation_mode = 'XYZ'
    for v_x, v_r, fr in ((0, 0, f - 0.5), (-back, math.radians(-kick), f + 0.8), (0, 0, f + 2.6)):
        m.location.x = v_x
        m.rotation_euler.y = v_r
        m.keyframe_insert('location', index=0, frame=fr)
        m.keyframe_insert('rotation_euler', index=1, frame=fr)


HULL_HITS = [Vector((3.5, 1.6, 1.2)), Vector((1.0, -2.0, 0.8)), Vector((4.2, 0.4, 1.9)),
             Vector((-1.5, 1.9, -0.6)), Vector((2.4, -1.2, 2.0)), Vector((0.2, 2.1, 0.4))]


def strafe_b(t0, bursts=3, every=2, gap=5):
    """B's rhythm: 3-round bursts, alternating diagonal pairs; the first burst goes wide."""
    f = int(round(P.T(t0)))
    k = 0
    hits = 0
    pairs = (GTIPS[:2], GTIPS[2:])
    for b in range(bursts):
        for r_ in range(3):
            t = (f - 1) / FPS
            for key in pairs[k % 2]:
                p0 = W(twB, t, twB.gun_muzzles[key].location)
                th_guess = t + (p0 - W(orb, t)).length / 240
                if b == 0:
                    aim = W(orb, th_guess, (0, 0, 7)) + Vector((R.uniform(-2, 2), R.uniform(-3, 3), R.uniform(2, 5)))
                    aim = p0 + (aim - p0) * 1.5
                    P.projectile(p0, aim, t, speed=240, color=NEON, size=0.3)
                else:
                    hp = HULL_HITS[hits % len(HULL_HITS)] * S
                    aim = W(orb, th_guess, hp)
                    th = P.projectile(p0, aim, t, speed=240, color=NEON, size=0.3)
                    if hits % 2 == 0:
                        P.impact(W(orb, th, hp), th, size=0.7, color=NEON)
                    hits += 1
                P.muzzle_flash(twB.gun_muzzles[key], t, NEON, 0.55)
                gun_recoil(twB, key, t)
            hull_kick(twB, t)
            k += 1
            f += every
        f += gap


strafe_b(2.05)

# ------------------------------------------------------------------------------- the crush
PULSE_LEGS = ((0, 3, 5), (1, 4, 6, 2), (7, 2, 5, 0, 3))


def tipf(i):
    return lambda t: tip(i, t)


def hitf(local):
    return lambda t: W(twA, t, local)


for k, (tp, ls) in enumerate(zip(T_PULSES, PULSE_LEGS)):
    dur = 0.17 + 0.04 * k
    for n, i in enumerate(ls):
        loc = Vector((R.uniform(-2.5, 2.5), R.uniform(-1.2, 1.2), R.uniform(-1.2, 1.2)))
        P.lightning(tipf(i), hitf(loc), tp + n * 0.015, tp + dur, color=GOLD,
                    width=0.11 + 0.02 * k, jag=0.24, branches=2, segs=10)
    P.impact(W(twA, tp + 0.03), tp + 0.03, size=1.1 + 0.35 * k, color=GOLD)
    P.light(W(twA, tp + 0.03) + Vector((0, 0, 3)), tp + 0.03, GOLD, energy=4000, dur=0.15)
    P.sfx(tp, 'zap_lightning', gain=0.8 + 0.15 * k, pos=W(twA, tp))
P.sfx(T_PULSES[0], 'crackle_loop', gain=0.5, pos=W(twA, T_PULSES[0]), dur=T_BURST - T_PULSES[0])

twA.destroy(T_BURST, size=5.5, wreck=False, debris=12)
P.cam_shake(T_BURST + 0.02, 0.3, dur=0.4)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2000, box=((-60, 260), (-80, 80), (-50, 50)), size=0.09, avoid=()):
    me = bpy.data.meshes.new('SpaceDust')
    bm = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        if any((c - q).length < 6.0 for q in avoid):
            continue
        s = size * R.uniform(0.6, 1.4)
        r = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=s)
        bmesh.ops.translate(bm, verts=r['verts'], vec=c)
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new('SpaceDust', me))
    me.materials.append(K.emit_mat('DustGlint', (0.55, 0.6, 0.75), 1.2))
    o.visible_shadow = False
    return o


# ------------------------------------------------------------------------------- camera
def cam_keys():
    keys = []

    def shot(t0, t1, n, fn, last=True):
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            if i == n and last:
                t = t1 - 1 / FPS
            keys.append((t,) + fn(t, (t - t0) / (t1 - t0)))

    # Shot 1: behind and above the Orb, the Twin-X far ahead; drift in as it coils.
    def s1f(t, u):
        o = orb_pos(t)
        pos = o + Vector((lerp(-34, -29, ss(u)), lerp(-12, -10, ss(u)), lerp(9, 7.5, ss(u))))
        look = o + Vector((lerp(22, 26, ss(u)), 1.0, lerp(1.5, 2.0, ss(u))))
        return pos, look, lerp(36, 38, ss(u))
    shot(0, CUT1, 12, s1f)

    # Shot 2: alongside, a little below, tracking the lunge; B whips past overhead.
    def s2f(t, u):
        o = orb_pos(t)
        pos = o + Vector((lerp(2, 0, ss(u)), lerp(-36, -31, ss(u)), lerp(-4.5, -3, ss(u))))
        look = o + Vector((lerp(-3, 3, ss(u)), 0, 2.0))
        return pos, look, 28
    shot(CUT1, CUT2, 10, s2f)

    # Shot 3: front 3/4 of the catch, easing round and in as the cage closes and bursts.
    def s3f(t, u):
        o = orb_pos(t)
        a = lerp(-38, -74, ss(u))
        rad = lerp(34, 22, ss(u))
        c = o + Vector((lerp(9, 6, ss(u)), 0, 0))
        pos = c + Vector((rad * math.cos(math.radians(a)) * -1 + lerp(20, 12, ss(u)), rad * math.sin(math.radians(a)), lerp(6, 5.5, ss(u))))
        look = o + Vector((lerp(9, 0, ss(u)), 0, lerp(1.2, 0.5, ss(u))))
        return pos, look, lerp(30, 30, ss(u))
    shot(CUT2, 6.0, 12, s3f, last=False)
    return keys


P.camera(cam_keys(), lens=30, cuts=(CUT1, CUT2))

_cam_path = []
for _f in range(1, NF + 1):
    bpy.context.scene.frame_set(_f)
    _cam_path.append(P.cam.matrix_world.translation.copy())
dust_field(avoid=_cam_path)

# ------------------------------------------------------------------------------- sound cues
P.sfx(T_COIL - 0.05, 'servo', gain=0.5, pos=W(orb, T_COIL))
P.sfx(T_STROKE - 0.04, 'whoosh', gain=1.0, pos=W(orb, T_STROKE))
P.sfx(T_STROKE, 'power_up_arc', gain=0.7, pos=W(orb, T_STROKE))
P.sfx(T_STROKE, 'crackle_loop', gain=0.45, pos=W(orb, 2.0), dur=T_OPEN - T_STROKE)
P.sfx(2.6, 'whoosh', gain=0.9, pos=W(twB, 2.75))
P.sfx(T_OPEN, 'servo', gain=0.6, pos=W(orb, T_OPEN))
P.sfx(T_CATCH, 'impact_metal', gain=1.0, pos=W(twA, T_CATCH))
P.sfx(T_CATCH + 0.03, 'mech_clunk', gain=0.8, pos=W(twA, T_CATCH))
P.sfx(T_BURST + 0.25, 'debris_metal', gain=0.6, pos=W(orb, T_BURST + 0.3))

print('orb', orb_pos(0), orb_pos(T_CATCH), 'A catch', _catch_w, 'B', b_pos(2.6))
P.render()
