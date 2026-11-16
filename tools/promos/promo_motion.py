"""Secondary motion for promo actors: weight and life on top of the scene's keyed motion.

The scene animates `actor.root` (path(), place(), its own per-frame sim). Nothing here touches
those keys. At render time (Promo.render -> bake) every actor gets an extra empty between its
root and its model (`actor.motion_obj`, named <label>_Motion) and that empty is keyed per frame
with physically driven offsets, so the root path stays exact and aim()/fire() world positions
still work (offsets are a few cm / degrees):

  ground units  nose dip on braking, squat on accelerating, body roll leaning out of turns,
                suspension bounce scaled to speed, settle wobble when stopping (damped springs),
                terrain-following pitch/roll/height sampled under the hull footprint (ground_z),
                Wheel*Pivot spin from distance travelled, whole-hull rock when firing
  hover units   bank into turns, lag/sway behind acceleration, drift settle when stopping,
                pitch forward when accelerating, slow idle sway
  aircraft      banking from lateral acceleration, pitch with climb (smoothed), light turbulence
  structures    hull rock on firing (much stiffer and smaller), thunk when an unfold lands

Plus, keyed directly where they happen: turret overshoot in Actor.aim(), part rebound at the
end of Actor.unfold().

Opt-out (set right after P.load()/P.copy(), before aim/fire/unfold calls):
    actor.motion['enabled'] = False        # everything off for this actor
    actor.motion['roll'] = False           # one feature: pitch, roll, jitter, terrain, wheels,
                                           # recoil, sway, overshoot, settle (unfold thunk)
    actor.motion['scale'] = 0.5            # global amplitude for this actor
    actor.motion['kind'] = 'ground'        # force a class: ground | hover | air | static
    PROMO_MOTION=0 in the environment       # whole layer off (old behaviour, for A/B)
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Quaternion, Vector

ENABLED = os.environ.get('PROMO_MOTION', '1') != '0'

DEFAULTS = dict(enabled=True, pitch=True, roll=True, jitter=True, terrain=True, wheels=True,
                recoil=True, sway=True, overshoot=True, settle=True, scale=1.0, kind=None)

SUB = 4           # spring sub-steps per frame
MAX_WHEEL = math.radians(26)   # visible wheel spin cap per frame (higher strobes at 24 fps)


def _fc(action):
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                out.extend(bag.fcurves)
    return out


def _curves(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return {}
    return {(f.data_path, f.array_index): f for f in _fc(ad.action)}


def on(actor, feature='enabled'):
    m = getattr(actor, 'motion', None)
    return ENABLED and bool(m) and m.get('enabled', True) and m.get(feature, True)


# ------------------------------------------------------------------------- hooks from the kit
def init(actor):
    actor.motion = dict(DEFAULTS)
    actor.motion_obj = None
    actor._mo_events = []      # (kind, t, a, b)
    actor._mo_hover = False
    actor._mo_path = None


def handles_recoil(actor, t, kick, back):
    """Called by Actor.recoil(). Returns True when the hull rock is done by the motion layer
    (the kit then only keys the barrel)."""
    if not on(actor, 'recoil') or actor.entry.get('kind') in ('ship', 'prop'):
        return False
    actor._mo_events.append(('recoil', t, kick, back))
    return True


def barrel_axis(b):
    """Unit vector along a split barrel's own axis, in its parent's space (cached on the object
    as b['axis']). Principal axis of the barrel vertices, pointing to the muzzle (+X side), so
    raised / elevated barrels (artillery) recoil along the tube, not along the turret's X."""
    if 'axis' in b.keys():
        return Vector(b['axis'])
    vs = [v.co for v in b.data.vertices]
    ax = Vector((1, 0, 0))
    if len(vs) >= 4:
        c = sum(vs, Vector()) / len(vs)
        cov = [[0.0] * 3 for _ in range(3)]
        for v in vs:
            d = v - c
            for i in range(3):
                for j in range(3):
                    cov[i][j] += d[i] * d[j]
        M = Matrix(cov)
        x = Vector((1.0, 0.1, 0.1))
        for _ in range(40):            # power iteration: dominant eigenvector
            x = M @ x
            if x.length < 1e-12:
                x = Vector((1, 0, 0))
                break
            x.normalize()
        if x.x < 0:
            x = -x
        # a stubby barrel has no clear long axis: keep +X unless the fit is clearly along it
        if x.x > 0.35:
            ax = x
    # the barrel's own matrix (identity when split) maps mesh space -> parent space
    ax = (b.matrix_basis.to_3x3() @ ax).normalized()
    b['axis'] = tuple(ax)
    return ax


def turret_overshoot(actor, tu, start, yaw, t, dur):
    """Called by Actor.aim() after it keyed start (t-dur) and yaw (t): adds a key shortly
    before t that swings slightly past the target, so the turret eases out, overshoots and
    settles back onto the target exactly at t."""
    if not on(actor, 'overshoot') or dur < 0.15:
        return
    d = yaw - start
    if abs(d) < math.radians(4):
        return
    os_ = math.copysign(min(math.radians(3.5), 0.07 * abs(d)), d)
    P = actor.P
    ft = P.T(t)
    fo = P.T(t - min(0.12, dur * 0.3))
    if fo <= P.T(t - dur) + 1:
        return
    tu.rotation_euler.z = yaw + os_
    tu.keyframe_insert('rotation_euler', index=2, frame=fo)
    tu.rotation_euler.z = yaw
    for f in _fc(tu.animation_data.action):
        if f.data_path == 'rotation_euler' and f.array_index == 2:
            for k in f.keyframe_points:
                if abs(k.co.x - fo) < 0.01 or abs(k.co.x - ft) < 0.01 or abs(k.co.x - P.T(t - dur)) < 0.01:
                    k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
            f.update()


def unfold_settle(actor, o, fa, fb, packed, deployed):
    """Called by Actor.unfold() per part after its packed (fa) and deployed (fb) keys: the part
    eases out of the packed pose, arrives at speed, hits its stop and rebounds a little."""
    if not on(actor, 'settle'):
        return
    P = actor.P
    pl, pr, ps = packed
    dl, dr, ds = deployed
    fps = P.fps
    k = 0.045
    # rebound toward the packed pose, translation capped
    dloc = Vector(pl) - Vector(dl)
    cap = 0.1 * max(1.0, actor.size / 5.0)
    rl = Vector(dl) + (dloc * k if dloc.length * k < cap else dloc.normalized() * cap)
    rr = Quaternion(dr).slerp(Quaternion(pr), k)
    rs = Vector(ds).lerp(Vector(ps), k)
    f1 = fb + round(fps * 0.11)
    f2 = fb + round(fps * 0.3)
    o.location, o.rotation_quaternion, o.scale = rl, rr, rs
    for attr in ('location', 'rotation_quaternion', 'scale'):
        o.keyframe_insert(attr, frame=f1)
    o.location, o.rotation_quaternion, o.scale = dl, dr, ds
    for attr in ('location', 'rotation_quaternion', 'scale'):
        o.keyframe_insert(attr, frame=f2)
    for f in _fc(o.animation_data.action):
        if f.data_path not in ('location', 'rotation_quaternion', 'scale'):
            continue
        for kp in f.keyframe_points:
            kp.interpolation = 'BEZIER'
            if abs(kp.co.x - fb) < 0.01:
                # arrive at speed (ease-in only), then the stop
                kp.handle_left_type = 'VECTOR'
                kp.handle_right_type = 'VECTOR'
            elif abs(kp.co.x - fa) < 0.01 or kp.co.x in (f1, f2):
                kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        f.update()
    ev = ('unfold', fb / fps - 1.0 / fps, 0, 0)
    if ev not in actor._mo_events:
        actor._mo_events.append(ev)


# ------------------------------------------------------------------------- sampling
def _sample_roots(P, actors, f0, f1, step):
    """Root world matrices on a fine frame grid. Fast path: evaluate the root's own f-curves;
    otherwise (parented / constrained / quaternion) a frame_set sweep, linearly interpolated."""
    grid = []
    f = f0
    while f <= f1 + 1e-6:
        grid.append(f)
        f += step
    out = {}
    slow = []
    for a in actors:
        r = a.root
        if r.parent is None and not r.constraints and r.rotation_mode == 'XYZ':
            cv = _curves(r)
            loc0, rot0 = r.location.copy(), r.rotation_euler.copy()
            mats = []
            for fr in grid:
                l = [cv[('location', i)].evaluate(fr) if ('location', i) in cv else loc0[i] for i in range(3)]
                e = [cv[('rotation_euler', i)].evaluate(fr) if ('rotation_euler', i) in cv else rot0[i] for i in range(3)]
                mats.append((Vector(l), e))
            out[a] = mats
        else:
            slow.append(a)
    if slow:
        sc = bpy.context.scene
        cur = sc.frame_current
        ints = list(range(int(math.floor(f0)), int(math.ceil(f1)) + 2))
        per = {a: [] for a in slow}
        for fr in ints:
            sc.frame_set(fr)
            for a in slow:
                per[a].append(a.root.matrix_world.copy())
        sc.frame_set(cur)
        for a in slow:
            mats = []
            for fr in grid:
                i = min(len(ints) - 2, max(0, int(math.floor(fr)) - ints[0]))
                u = fr - ints[i]
                m0, m1 = per[a][i], per[a][i + 1]
                l = m0.translation.lerp(m1.translation, u)
                q = m0.to_quaternion().slerp(m1.to_quaternion(), u)
                e = q.to_euler('XYZ')
                mats.append((l, [e.x, e.y, e.z], True))
            out[a] = mats
    return grid, out


def _gauss(xs, sigma_n):
    if sigma_n < 0.5:
        return xs[:]
    r = int(sigma_n * 2.5)
    w = [math.exp(-0.5 * (i / sigma_n) ** 2) for i in range(-r, r + 1)]
    n = len(xs)
    out = []
    for i in range(n):
        s = ws = 0.0
        for j, wj in enumerate(w):
            k = i + j - r
            if k < 0:     # odd reflection: keeps linear trends at the clip edges
                x = 2 * xs[0] - xs[min(n - 1, -k)]
            elif k > n - 1:
                x = 2 * xs[-1] - xs[max(0, 2 * (n - 1) - k)]
            else:
                x = xs[k]
            s += x * wj
            ws += wj
        out.append(s / ws)
    return out


def _deriv(xs, dt):
    n = len(xs)
    return [(xs[min(n - 1, i + 1)] - xs[max(0, i - 1)]) / (dt * (min(n - 1, i + 1) - max(0, i - 1))) for i in range(n)]


class Noise:
    """Smooth 1D value noise (cubic between random knots), zero mean, amplitude ~1."""

    def __init__(self, seed, hz):
        self.r = random.Random(seed)
        self.hz = hz
        self.k = [self.r.uniform(-1, 1) for _ in range(400)]

    def __call__(self, t):
        x = max(0.0, t * self.hz + 3)
        i = int(x)
        u = x - i
        k = self.k
        a, b, c, d = k[(i - 1) % 400], k[i % 400], k[(i + 1) % 400], k[(i + 2) % 400]
        # Catmull-Rom: C1 continuous, no pops
        return 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)


def _spring(target, dt, hz, zeta, impulses=None, x0=None):
    """Damped spring following `target` (list on the grid). impulses: {index: dv}."""
    w = 2 * math.pi * hz
    x = target[0] if x0 is None else x0
    v = 0.0
    out = []
    for i, tg in enumerate(target):
        if impulses and i in impulses:
            v += impulses[i]
        a = w * w * (tg - x) - 2 * zeta * w * v
        v += a * dt
        x += v * dt
        out.append(x)
    return out


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _clamp(x, lim):
    return max(-lim, min(lim, x))


def _soft(x, lim):
    """Soft clamp (tanh), keeps curves smooth at the limit."""
    return lim * math.tanh(x / lim) if lim > 0 else 0.0


def _footprint(a):
    """Hull half-length / half-width / height in root space (rest pose)."""
    bpy.context.view_layer.update()
    inv = a.root.matrix_world.inverted()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    meas = [o for o in a.meshes if not o.get('hideWhenDeployed')] or a.meshes
    for o in meas:
        try:
            m = inv @ o.matrix_world
        except Exception:
            continue
        for c in o.bound_box:
            w = m @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    if lo.x > hi.x:
        s = a.size / 2
        return s, s * 0.6, a.entry.get('height', 1.5)
    # a packed carrier (structure rolling in) is measured too
    carr = [o for o in a.meshes if o.get('hideWhenDeployed')]
    for o in carr:
        m = inv @ o.matrix_world
        for c in o.bound_box:
            w = m @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return max(0.3, (hi.x - lo.x) / 2), max(0.3, (hi.y - lo.y) / 2), max(0.3, hi.z - lo.z)


# ------------------------------------------------------------------------- classification
def _classify(a, pos, eul, gz, quat_root):
    m = a.motion
    if m.get('kind'):
        return m['kind']
    kind = a.entry.get('kind')
    if kind in ('ship', 'prop'):
        return 'skip'
    moved = sum((pos[i + 1] - pos[i]).length for i in range(len(pos) - 1))
    alien = a.entry.get('file', '').startswith('alien/')
    hgt = [p.z - g for p, g in zip(pos, gz)]
    mean_h = sum(hgt) / len(hgt)
    if a._mo_hover:
        return 'hover'
    if mean_h > 2.5 and (a._mo_path is not None or quat_root):
        return 'air'
    if alien and kind == 'unit' and mean_h > 0.35:
        return 'hover'
    if moved < 0.4:
        return 'static'
    return 'ground'


# ------------------------------------------------------------------------- bake
def _insert_layer(a):
    if a.motion_obj is not None:
        return a.motion_obj
    mo = bpy.data.objects.new(a.name + '_Motion', None)
    bpy.context.scene.collection.objects.link(mo)
    mo.empty_display_size = 0.3
    mo.parent = a.root
    mr = a.model_root
    mw = mr.matrix_parent_inverse.copy()
    mr.parent = mo
    mr.matrix_parent_inverse = mw
    mo.rotation_mode = 'XYZ'
    a.motion_obj = mo
    return mo


def bake(P):
    if getattr(P, '_motion_baked', False):
        return
    P._motion_baked = True
    if not ENABLED or getattr(P, 'motion', True) is False:
        return
    actors = [a for a in P.actors if getattr(a, 'motion', None) and a.motion.get('enabled', True)]
    if not actors:
        return
    fps = P.fps
    nf = P.nf
    step = 1.0 / SUB
    f0, f1 = 1.0, float(nf + 1)
    grid, samp = _sample_roots(P, actors, f0, f1, step)
    dt = step / fps
    report = []
    for a in actors:
        try:
            info = _bake_actor(P, a, grid, samp[a], dt)
        except Exception as ex:  # never break a render over secondary motion
            info = f'FAILED {ex!r}'
        report.append(f'{a.name}:{info}')
    print('PROMO_MOTION', '; '.join(report))


def _bake_actor(P, a, grid, sm, dt):
    fps = P.fps
    m = a.motion
    sc_amp = m.get('scale', 1.0)
    quat_root = a.root.rotation_mode != 'XYZ' or a.root.parent is not None
    pos = [s[0] for s in sm]
    eul = [s[1] for s in sm]
    # ground under the root on whole frames (ray casts are not free), interpolated
    n = len(grid)
    gz_f = {}

    def gz_at(x, y):
        return P.ground_z(x, y)
    for i in range(0, n, SUB):
        gz_f[i] = gz_at(pos[i].x, pos[i].y)
    gz = []
    keys = sorted(gz_f)
    for i in range(n):
        j = min(keys, key=lambda k: abs(k - i)) if i not in gz_f else i
        gz.append(gz_f[j])
    cls = _classify(a, pos, eul, gz, quat_root)
    if cls == 'skip':
        return 'skip'
    yaw = [e[2] for e in eul]
    own_pitch = any(abs(e[1]) > math.radians(0.5) for e in eul) or quat_root
    own_roll = any(abs(e[0]) > math.radians(0.5) for e in eul) or quat_root
    zr = [p.z for p in pos]
    z_range = max(zr) - min(zr)
    custom = a._mo_path is None
    events = list(a._mo_events)
    if cls == 'static' and not events and not a._mo_hover:
        return 'static-none'
    if cls == 'air' and quat_root:
        # a scene-built flight (own orientation frames): only recoil, no added banking
        dyn = False
    else:
        dyn = True

    # kinematics in the body frame (smoothed so linear keys don't spike)
    sig = 0.05 * fps * SUB   # 50 ms gaussian
    px = _gauss([p.x for p in pos], sig * 0.5)
    py = _gauss([p.y for p in pos], sig * 0.5)
    pz = _gauss([p.z for p in pos], sig * 0.5)
    vx, vy, vz = _deriv(px, dt), _deriv(py, dt), _deriv(pz, dt)
    ax, ay, az = _gauss(_deriv(vx, dt), sig), _gauss(_deriv(vy, dt), sig), _gauss(_deriv(vz, dt), sig)
    along, alat, spd, vh = [], [], [], []
    for i in range(n):
        c, s = math.cos(yaw[i]), math.sin(yaw[i])
        along.append(ax[i] * c + ay[i] * s)
        alat.append(-ax[i] * s + ay[i] * c)
        spd.append(math.sqrt(vx[i] ** 2 + vy[i] ** 2 + vz[i] ** 2))
        vh.append(math.hypot(vx[i], vy[i]))

    Lh, Wh, H = _footprint(a)
    mass = max(0.5, (a.size / 4.5) ** 1.5)
    seed = sum(map(ord, a.name)) * 7919
    nz = [Noise(seed + k, hz) for k, hz in enumerate((3.4, 4.1, 2.9, 0.45, 0.38, 0.52))]
    ts = [(g - 1) / fps for g in grid]
    zeros = [0.0] * n
    pitch, roll, heave, surge, sway = zeros[:], zeros[:], zeros[:], zeros[:], zeros[:]
    pivot = Vector((0, 0, 0))
    D = math.radians

    # --- per class drive
    if dyn and cls == 'ground':
        hz = 1.55 / math.sqrt(mass)
        if m['pitch']:
            tgt = [_soft(-D(0.4) * x, D(2.2)) for x in along]
            pitch = _spring(tgt, dt, hz, 0.38)
        if m['roll'] and not own_roll:
            tgt = [_soft(D(0.5) * x, D(3.0)) for x in alat]
            roll = _spring(tgt, dt, hz * 1.1, 0.4)
        # squat: the body sinks a touch under any hard acceleration
        tgt = [-0.006 * min(6.0, math.hypot(al, at)) * min(1.0, H / 1.6) for al, at in zip(along, alat)]
        heave = _spring(tgt, dt, hz * 1.4, 0.45)
        if m['jitter']:
            for i in range(n):
                k = min(1.0, spd[i] / 8.0) ** 0.8
                k *= min(1.0, 1.0 / mass ** 0.35)
                pitch[i] += D(0.35) * k * nz[0](ts[i])
                roll[i] += D(0.3) * k * nz[1](ts[i])
                heave[i] += 0.012 * k * nz[2](ts[i])
        # lift so the dynamic tilt rocks about the suspension rather than burying an end
        for i in range(n):
            heave[i] += 0.5 * (Lh * math.sqrt(math.sin(pitch[i]) ** 2 + 1e-6) + Wh * math.sqrt(math.sin(roll[i]) ** 2 + 1e-6) - (Lh + Wh) * 1e-3)
        # terrain under the footprint (only when the scene keeps the root at a constant height)
        if m['terrain'] and not own_pitch and z_range < 0.05 and pos[0].z - gz[0] < 0.3:
            tp, tr, th = [], [], []
            for i in range(0, n, SUB):
                c, s = math.cos(yaw[i]), math.sin(yaw[i])
                x, y = pos[i].x, pos[i].y
                fx, fy = c * Lh * 0.85, s * Lh * 0.85
                lx, ly = -s * Wh * 0.85, c * Wh * 0.85
                zf = (gz_at(x + fx + lx, y + fy + ly) + gz_at(x + fx - lx, y + fy - ly)) / 2
                zb = (gz_at(x - fx + lx, y - fy + ly) + gz_at(x - fx - lx, y - fy - ly)) / 2
                zl = (gz_at(x + fx + lx, y + fy + ly) + gz_at(x - fx + lx, y - fy + ly)) / 2
                zrr = (gz_at(x + fx - lx, y + fy - ly) + gz_at(x - fx - lx, y - fy - ly)) / 2
                zc = gz[i]
                tp.append(math.atan2(zb - zf, 2 * Lh * 0.85))
                tr.append(math.atan2(zl - zrr, 2 * Wh * 0.85))
                th.append(max(zc, (zf + zb) / 2) - pos[i].z)
            def up(xs):
                o = []
                for i in range(n):
                    j = i / SUB
                    k = min(len(xs) - 2, int(j))
                    u = j - k
                    o.append(xs[k] * (1 - u) + xs[k + 1] * u if len(xs) > 1 else xs[0])
                return o
            tp, tr, th = up(tp), up(tr), up(th)
            tp = _spring(tp, dt, 3.0, 0.6)
            tr = _spring(tr, dt, 3.0, 0.6)
            th = _spring(th, dt, 3.5, 0.65)
            for i in range(n):
                pitch[i] += tp[i]
                roll[i] += tr[i]
                heave[i] += th[i]
        pivot = Vector((0, 0, 0.3 * H))
        # off the ground (carried, dropped, mid-jump): no suspension, no road forces
        for i in range(n):
            h = pos[i].z - gz[i]
            w = 1.0 - _smooth((h - 1.6) / 1.0)
            if w < 1.0:
                pitch[i] *= w
                roll[i] *= w
                heave[i] *= w
    elif dyn and cls == 'hover':
        hz = 0.95 / math.sqrt(mass)
        g_ = 1.0 / mass ** 0.7     # big saucers lean less
        if m['pitch']:
            pitch = _spring([_soft(D(1.2) * g_ * x, D(8) * g_) for x in along], dt, hz, 0.4)
        if m['roll'] and not own_roll:
            roll = _spring([_soft(-D(1.4) * g_ * x, D(12) * g_) for x in alat], dt, hz, 0.4)
        if m['sway']:
            surge = _spring([_soft(-0.03 * x, 0.35) for x in along], dt, hz * 0.85, 0.32)
            sway = _spring([_soft(-0.03 * x, 0.35) for x in alat], dt, hz * 0.85, 0.32)
            for i in range(n):
                pitch[i] += D(1.1) * nz[3](ts[i])
                roll[i] += D(1.3) * nz[4](ts[i])
        pivot = Vector((0, 0, 0.5 * H))
    elif dyn and cls == 'air':
        hz = 1.0
        if m['roll'] and not own_roll and not (a._mo_path or {}).get('bank'):
            roll = _spring([_soft(-math.atan2(x, 9.81) * 0.9, D(55)) for x in alat], dt, hz, 0.75)
        if m['pitch'] and not own_pitch:
            tgt = [_soft(-math.atan2(vz[i], max(vh[i], 2.0)) * 0.6 + D(0.4) * along[i], D(25)) for i in range(n)]
            pitch = _spring(tgt, dt, hz, 0.75)
        if m['jitter']:
            for i in range(n):
                k = min(1.0, spd[i] / 15.0)
                roll[i] += D(1.2) * k * nz[4](ts[i] * 2)
                pitch[i] += D(0.6) * k * nz[3](ts[i] * 2)
        pivot = Vector((0, 0, 0.5 * H))
    elif cls in ('static', 'hover') and a._mo_hover and m['sway']:
        for i in range(n):
            pitch[i] += D(1.0) * nz[3](ts[i])
            roll[i] += D(1.2) * nz[4](ts[i])
        pivot = Vector((0, 0, 0.5 * H))
    elif cls == 'static' or not dyn:
        pivot = Vector((0, 0, 0.3 * H))

    # --- impulses: recoil rock, unfold thunk
    struct = a.entry.get('kind') == 'structure'   # a dug-in gun tower barely rocks
    imp_p, imp_s, imp_h, imp_r = {}, {}, {}, {}
    rng = random.Random(seed)
    for ev, t, k1, k2 in events:
        i = int(round((P.T(t) + 1 - grid[0]) * SUB))   # one frame after the shot: the kick
        if not (0 <= i < n):
            continue
        if ev == 'recoil' and m['recoil']:
            kick = D(k1)
            if struct:
                g, back = 0.4, k2 * 0.15
            elif cls == 'hover':
                g, back = 0.7, k2 * 0.6
            elif cls == 'air':
                g, back = 0.35, k2 * 0.3
            else:
                g, back = 0.75 / mass ** 0.3, k2 * 0.7
            # a spring with peak response ~ v0/w*0.64 (zeta .3): solve v0 for the wanted peak
            imp_p[i] = imp_p.get(i, 0) - kick * g * (2 * math.pi * 2.4) / 0.64
            imp_s[i] = imp_s.get(i, 0) - back * (2 * math.pi * 2.0) / 0.64
            imp_h[i] = imp_h.get(i, 0) - 0.02 * k1 / 7.0 * (2 * math.pi * 3.0) / 0.64 * (0.5 if struct else 1)
            imp_r[i] = imp_r.get(i, 0) + rng.choice((-1, 1)) * kick * g * 0.18 * (2 * math.pi * 2.4) / 0.64
        elif ev == 'unfold' and m['settle']:
            imp_h[i] = imp_h.get(i, 0) - 0.025 * (2 * math.pi * 3.0) / 0.64 * min(2.0, a.size / 5.0)
            imp_p[i] = imp_p.get(i, 0) + D(0.5) * rng.choice((-1, 1)) * (2 * math.pi * 2.4) / 0.64
    if imp_p or imp_h:
        stiff = 1.5 if struct else 1.0
        rp = _spring(zeros, dt, 2.4 * stiff, 0.3, imp_p, 0.0)
        rr = _spring(zeros, dt, 2.6 * stiff, 0.3, imp_r, 0.0)
        rs = _spring(zeros, dt, 2.0 * stiff, 0.45, imp_s, 0.0)
        rh = _spring(zeros, dt, 3.0 * stiff, 0.35, imp_h, 0.0)
        for i in range(n):
            pitch[i] += rp[i]
            roll[i] += rr[i]
            surge[i] += rs[i]
            heave[i] += rh[i]

    if not any(abs(x) > 1e-5 for x in pitch + roll + heave + surge + sway):
        return f'{cls}-none'

    # --- key the motion layer on whole frames
    mo = _insert_layer(a)
    for i in range(0, n, SUB):
        fr = grid[i]
        R = Matrix.Rotation(roll[i] * sc_amp, 3, 'X')
        R = Matrix.Rotation(pitch[i] * sc_amp, 3, 'Y') @ R
        e = R.to_euler('XYZ')
        loc = pivot - R @ pivot + Vector((surge[i], sway[i], heave[i])) * sc_amp
        mo.location = loc
        mo.rotation_euler = e
        mo.keyframe_insert('location', frame=fr)
        mo.keyframe_insert('rotation_euler', frame=fr)
    for f in _fc(mo.animation_data.action):
        for kp in f.keyframe_points:
            kp.interpolation = 'LINEAR'

    # --- wheels from rolling distance
    nw = 0
    if m['wheels'] and dyn and cls == 'ground':
        for name, pv in a.parts.items():
            if not (name.startswith('Wheel') and name.endswith('Pivot')):
                continue
            if pv.animation_data and pv.animation_data.action:
                continue  # the scene drives it
            kids = [c for c in pv.children_recursive if c.type == 'MESH']
            rad = 0.0
            for c in kids:
                zs = [(c.matrix_world @ Vector(b)).z for b in c.bound_box]
                rad = max(rad, (max(zs) - min(zs)) / 2)
            rad = rad or 0.35
            pv.rotation_mode = 'XYZ'
            base = pv.rotation_euler.y
            ang = 0.0
            for i in range(0, n, SUB):
                if i >= SUB:
                    j = i - SUB
                    d = (pos[i] - pos[j])
                    c, s = math.cos(yaw[i]), math.sin(yaw[i])
                    ang += _clamp((d.x * c + d.y * s) / rad, MAX_WHEEL)
                pv.rotation_euler.y = base + ang
                pv.keyframe_insert('rotation_euler', index=1, frame=grid[i])
            for f in _fc(pv.animation_data.action):
                for kp in f.keyframe_points:
                    kp.interpolation = 'LINEAR'
            nw += 1
    dump = os.environ.get('PROMO_MOTION_DUMP')
    if dump:
        os.makedirs(dump, exist_ok=True)
        with open(os.path.join(dump, a.name + '.csv'), 'w') as fh:
            fh.write('frame,speed,along,alat,pitch_deg,roll_deg,heave,surge,sway\n')
            for i in range(0, n, SUB):
                fh.write(f'{grid[i]:.0f},{spd[i]:.3f},{along[i]:.3f},{alat[i]:.3f},{math.degrees(pitch[i]):.3f},'
                         f'{math.degrees(roll[i]):.3f},{heave[i]:.4f},{surge[i]:.4f},{sway[i]:.4f}\n')
    mx_p = max(abs(x) for x in pitch)
    mx_r = max(abs(x) for x in roll)
    return f'{cls}{"" if dyn else "(fixed)"} pitch<={math.degrees(mx_p):.1f} roll<={math.degrees(mx_r):.1f} wheels={nw} ev={len(events)}'
