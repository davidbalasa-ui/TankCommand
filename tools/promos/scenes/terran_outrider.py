"""Outrider (Terran scout): a hit-and-run peek.

The Outrider launches over a desert rise, lands in a spray of dust and power-slides broadside
in front of an Arcadian mining camp (two Lumens guarding a Sifter at an ore seam). It snaps
off three quick 3-round autocannon bursts (pings, not kills), the Lumens wheel round, and it
is already gone: gold lightning slams into the dirt where it was, chases its rooster tail, and
the scout leaps back over the rise with its turret turned round for one last cheeky burst.

All the hero's motion is keyed per frame by a small vehicle sim in this script (terrain
following, jumps with real airtime, drift yaw, body roll, wheel spin + steering)."""
import math
import os
import sys

import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('terran_outrider', seconds=6.0)
FPS = P.fps
NF = int(P.seconds * FPS) + 1

# Sand-coloured default for every puff (the kit's muzzle-smoke default reads as grey balls
# in this sunlit desert).
SAND = (0.84, 0.72, 0.56)
_kit_puff = P.puff


def _sand_puff(pos, t, size=0.6, n=3, rise=1.0, life=1.2, color=None, opacity=0.65):
    return _kit_puff(pos, t, size=size, n=n, rise=rise, life=life, color=color or SAND,
                     opacity=min(opacity, 0.4))


P.puff = _sand_puff

GOLD = COL['arc_gold']
_bolt_mats = {}


def _bmat(key, col, strength, alpha=None):
    if key not in _bolt_mats:
        _bolt_mats[key] = K.emit_mat('Gold' + key, col, strength, alpha=alpha)
    return _bolt_mats[key]


def gold_bolt(p0, p1, t0, t1, width=0.07, jag=0.2, branches=2, segs=10, glow=True, light=True):
    """Arcadian lightning that stays GOLD: thin white-gold core inside a gold body and a soft
    gold glow sleeve, re-shaped every frame, with forks."""
    p0, p1 = Vector(p0), Vector(p1)
    core = _bmat('Core', (1.0, 0.85, 0.55), 5.0)
    body = _bmat('Body', GOLD, 3.2)
    halo = _bmat('Halo', (1.0, 0.6, 0.12), 1.6, alpha=0.3)
    d = p1 - p0
    L = d.length
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    f0 = int(round(P.T(t0)))
    f1 = max(f0 + 1, int(round(P.T(t1))))
    for fr in range(f0, f1):
        pts = []
        for i in range(segs + 1):
            u = i / segs
            off = (side * P.rnd.uniform(-1, 1) + up * P.rnd.uniform(-1, 1)) * jag * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
            pts.append(p0 + d * u + off)
        obs = [K.polyline('BoltB', pts, width, body), K.polyline('BoltC', pts, width * 0.35, core)]
        if glow:
            obs.append(K.polyline('BoltH', pts, width * 2.6, halo))
        for b in range(branches):
            k = P.rnd.randint(2, segs - 2)
            a = pts[k]
            dirb = (d.normalized() * 0.6 + side * P.rnd.uniform(-1, 1) + up * P.rnd.uniform(-0.5, 0.5)).normalized()
            bl = L * P.rnd.uniform(0.08, 0.2)
            obs.append(K.polyline('BoltF', [a, a + dirb * bl * 0.5 + side * P.rnd.uniform(-.1, .1) * bl, a + dirb * bl],
                                  width * 0.5, body))
        for ob in obs:
            K.show_between(ob, fr, fr + 1)
    if light:
        P.light((p0 + p1) / 2, t0, GOLD, energy=120 + 12 * L, dur=t1 - t0 + 0.05, radius=L * 0.2)


def gold_sparks(pos, t, n=9, size=1.0):
    """Small gold spark spray (streaks thrown up and out, falling back)."""
    pos = Vector(pos)
    m = _bmat('Spark', (1.0, 0.68, 0.2), 4.0)
    f0 = P.T(t)
    for i in range(n):
        v = Vector((P.rnd.uniform(-1, 1), P.rnd.uniform(-1, 1), P.rnd.uniform(0.6, 1.6))).normalized() * size * P.rnd.uniform(2.5, 4.5)
        sp = K.sphere('GSpk', 1.0, m, seg=(6, 4))
        sp.rotation_mode = 'QUATERNION'
        sp.scale = (0.1 * size, 0.022 * size, 0.022 * size)
        life = P.rnd.uniform(0.25, 0.4)
        for k in range(4):
            tt = life * k / 3
            sp.location = pos + v * tt + Vector((0, 0, -6 * tt * tt))
            vel = v + Vector((0, 0, -12 * tt))
            sp.rotation_quaternion = vel.to_track_quat('X', 'Z')
            sp.keyframe_insert('location', frame=f0 + tt * FPS)
            sp.keyframe_insert('rotation_quaternion', frame=f0 + tt * FPS)
        K.show_between(sp, f0, f0 + life * FPS)

# ------------------------------------------------------------------------------ the rise
RIDGE_X = 24.0
RIDGE_S = 4.4      # gaussian width (m)
RIDGE_H = 1.35     # crest height (m)


def ridge_h(x, y):
    """Height of the rise: a long gaussian ridge running along Y, tapering out at its ends."""
    taper = K.smoothstep((34 - abs(y + 4)) / 8.0)
    wob = 0.12 * math.sin(y * 0.31) + 0.08 * math.sin(y * 0.77 + 1.3)
    return (RIDGE_H + wob) * taper * math.exp(-((x - RIDGE_X - 0.6 * math.sin(y * 0.11)) / RIDGE_S) ** 2)


def ground(x, y):
    return ridge_h(x, y)


P.env('desert', sun=(38, 0, -150), clear=[(10, -2, 20), (RIDGE_X, -4, 18), (34, -14, 12)], props=40,
      deposits=[('ore', (-3.5, 6.0), 1.1)])
P.flatten(14, -4, 26)

# ridge mesh, sharing the ground material (Object coords line up: both at the origin)
me = bpy.data.meshes.new('Rise')
bm = bmesh.new()
nx, ny = 60, 110
x0, x1, y0, y1 = RIDGE_X - 14, RIDGE_X + 14, -44, 36
verts = []
for j in range(ny + 1):
    row = []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        y = y0 + (y1 - y0) * j / ny
        h = ridge_h(x, y)
        row.append(bm.verts.new((x, y, h if h > 0.03 else h - 0.08)))
    verts.append(row)
for j in range(ny):
    for i in range(nx):
        f = bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
        f.smooth = True
bm.to_mesh(me)
bm.free()
rise = K.link(bpy.data.objects.new('Rise', me))
me.materials.append(P.ground.data.materials[0])

# ------------------------------------------------------------------------------ the camp
sifter = P.load('sifter', at=(-1.5, 4.2), heading=-150)
sifter.spin('GrinderPivot', 540, 0.0, 6.0, axis=1)
for k in range(9):
    P.puff((-3.4 + 0.4 * math.sin(k), 4.6, 0.3), 0.15 + k * 0.62, size=0.7, n=1, rise=0.9,
           life=1.4, color=(0.55, 0.35, 0.2), opacity=0.5)

lumA = P.load('lumen', at=(3.0, -1.5), heading=95, label='lumenA')
lumB = P.load('lumen', at=(-4.5, -5.5), heading=40, label='lumenB')
HOVER = 1.1
# A idles, gets pinged, swings round and gives chase. B wheels round and fires from the camp.
lumA.path([(0.0, (3.0, -1.5), 95), (2.2, (3.3, -1.0), 115), (2.75, (3.6, -1.2), 10),
           (3.4, (5.2, -2.6), -15), (4.6, (8.6, -6.5), -40), (6.0, (11.5, -10.5), -45)],
          z=HOVER, face=False)
lumB.path([(0.0, (-4.5, -5.5), 40), (2.6, (-4.2, -5.0), 45), (3.1, (-3.6, -4.8), 15),
           (6.0, (0.5, -6.8), -5)], z=HOVER, face=False)
for a, ph in ((lumA, 0.0), (lumB, 0.6)):
    a.hover_bob(0.12, 0.8)


def lifter_crackle(a, t0, t1, every=0.35):
    """Arcadian lifters: short gold arcs flicking from the hull down to the ground."""
    t = t0
    i = 0
    while t < t1:
        p = a.pos_at(t)
        for side in (-1, 1):
            off = Vector((P.rnd.uniform(-0.8, 0.8), side * 0.7, 0.35))
            gold_bolt(p + off, Vector((p.x + off.x * 1.3, p.y + off.y * 1.5, 0.02)), t, t + 0.08,
                      width=0.02, jag=0.35, branches=1, segs=5, glow=False, light=False)
        t += every + 0.05 * (i % 3)
        i += 1


lifter_crackle(lumA, 0.05, 6.0)
lifter_crackle(lumB, 0.22, 6.0)

# ------------------------------------------------------------------------------ the hero
hero = P.load('outrider', at=(40, 6), heading=180)
hero.split_barrels()
WHEEL_R = 0.4

# (t, x, y): driven ground track. Hermite in time, so spacing = speed.
TRACK = [
    (0.0, (33.5, 5.6)),
    (0.4, (25.0, 4.7)),
    (0.7, (19.6, 4.0)),
    (1.0, (15.9, 3.2)),
    (1.3, (13.4, 2.55)),
    (1.65, (12.2, 2.2)),
    (2.1, (11.75, 2.0)),
    (2.9, (11.6, 1.8)),
    (3.15, (11.55, 0.7)),
    (3.45, (11.9, -2.0)),
    (3.85, (13.0, -6.4)),
    (4.3, (15.6, -11.2)),
    (4.65, (19.0, -14.4)),
    (4.9, (22.8, -16.3)),
    (5.15, (27.6, -17.6)),
    (5.4, (31.6, -18.6)),
    (5.65, (34.4, -19.4)),
    (5.85, (35.8, -19.8)),
    (6.0, (36.4, -20.0)),
]
# yaw relative to the direction of travel (the drift), degrees, keyed in time
DRIFT = [(0.0, 0), (0.85, 0), (1.15, 35), (1.55, 74), (2.0, 87), (2.9, 90), (3.2, 15), (3.5, 0),
         (5.45, 0), (5.6, -18), (5.85, -62), (6.0, -70)]
# absolute heading is the travel heading + drift; while nearly stopped we hold the last heading


def herm(keys, t):
    ts = [k[0] for k in keys]
    ps = [Vector(k[1]) for k in keys]
    n = len(keys)
    if t <= ts[0]:
        return ps[0].copy(), (ps[1] - ps[0]) / (ts[1] - ts[0])
    if t >= ts[-1]:
        return ps[-1].copy(), (ps[-1] - ps[-2]) / (ts[-1] - ts[-2])
    i = max(k for k in range(n - 1) if ts[k] <= t)
    t0_, t1_ = ts[i], ts[i + 1]
    h = t1_ - t0_

    def tan(k):
        if k == 0:
            return (ps[1] - ps[0]) / (ts[1] - ts[0])
        if k == n - 1:
            return (ps[-1] - ps[-2]) / (ts[-1] - ts[-2])
        return (ps[k + 1] - ps[k - 1]) / (ts[k + 1] - ts[k - 1])
    m0, m1 = tan(i) * h, tan(i + 1) * h
    u = (t - t0_) / h
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    p = h00 * ps[i] + h10 * m0 + h01 * ps[i + 1] + h11 * m1
    dh00 = 6 * u ** 2 - 6 * u
    dh10 = 3 * u ** 2 - 4 * u + 1
    dh01 = -6 * u ** 2 + 6 * u
    dh11 = 3 * u ** 2 - 2 * u
    v = (dh00 * ps[i] + dh10 * m0 + dh01 * ps[i + 1] + dh11 * m1) / h
    return p, v


def lerp_keys(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, a), (tb, b) in zip(keys, keys[1:]):
        if ta <= t <= tb:
            return a + (b - a) * K.smoothstep((t - ta) / (tb - ta))
    return keys[-1][1]


GRAV = 9.81 * 2.1
SUB = 4
sim = []  # per frame: dict(t, pos, yaw, pitch, roll, air, speed)
z, vz = 0.0, 0.0
air = False
last_head = 180.0
prev_g = None
prev_xy = None
dist = 0.0
yaw_prev = None
for f in range(1, NF + 1):
    t = (f - 1) / FPS
    for s in range(SUB):
        ts = t - (SUB - 1 - s) / (FPS * SUB)
        p2, v2 = herm(TRACK, max(0, ts))
        g = ground(p2.x, p2.y)
        if prev_g is None:
            z, vz, prev_g = g, 0.0, g
        dt = 1 / (FPS * SUB)
        if air:
            vz -= GRAV * dt
            z += vz * dt
            if z <= g:
                z = g
                air = False
                vz = (g - prev_g) / dt
        else:
            gv = (g - prev_g) / dt
            # leave the ground when it falls away faster than gravity can follow
            if gv < vz - GRAV * dt * 1.0 and vz > 1.0:
                air = True
                vz -= GRAV * dt
                z += vz * dt
            else:
                vz = gv
                z = g
        prev_g = g
    p2, v2 = herm(TRACK, t)
    sp = v2.length
    if sp > 1.2:
        last_head = math.degrees(math.atan2(v2.y, v2.x))
    head = last_head + lerp_keys(DRIFT, t)
    if yaw_prev is not None:
        while head - yaw_prev > 180:
            head -= 360
        while head - yaw_prev < -180:
            head += 360
    yaw_prev = head
    # pitch: along the slope on the ground, along the flight path in the air
    fwd = Vector((math.cos(math.radians(head)), math.sin(math.radians(head))))
    if air:
        pitch = -math.degrees(math.atan2(vz, max(sp, 1.0))) * 0.8
    else:
        e = 0.9
        pitch = -math.degrees(math.atan2(ground(p2.x + fwd.x * e, p2.y + fwd.y * e) - ground(p2.x - fwd.x * e, p2.y - fwd.y * e), 2 * e))
    if prev_xy is not None:
        dist += (p2 - prev_xy).dot(fwd)  # rolling distance (sideways slide doesn't turn wheels)
    prev_xy = p2.copy()
    sim.append(dict(t=t, f=f, x=p2.x, y=p2.y, z=z, head=head, pitch=pitch, air=air, speed=sp, dist=dist,
                    drift=lerp_keys(DRIFT, t)))

# smooth pitch a little (suspension), then roll from drift rate / lateral accel
for i, s in enumerate(sim):
    lo, hi = max(0, i - 2), min(len(sim), i + 3)
    s['pitch_s'] = sum(q['pitch'] for q in sim[lo:hi]) / (hi - lo)
for i, s in enumerate(sim):
    a = sim[max(0, i - 1)]
    b = sim[min(len(sim) - 1, i + 1)]
    dh = (b['head'] - a['head']) / max(1e-3, b['t'] - a['t'])
    s['roll'] = max(-9, min(9, dh * s['speed'] * 0.012)) if not s['air'] else 0.0

r = hero.root
r.rotation_mode = 'XYZ'
for s in sim:
    r.location = (s['x'], s['y'], s['z'])
    r.rotation_euler = (math.radians(s['roll']), math.radians(s['pitch_s']), math.radians(s['head']))
    r.keyframe_insert('location', frame=s['f'])
    r.keyframe_insert('rotation_euler', frame=s['f'])
K.set_interp(r, 'LINEAR')

# wheels: spin from rolling distance, front pair steers into the slide, airborne wheels droop
for side in 'LR':
    for wi in range(3):
        pv = hero.parts.get(f'Wheel{wi}{side}Pivot')
        if pv is None:
            continue
        pv.rotation_mode = 'XYZ'
        base = pv.rotation_euler.copy()
        bz = pv.location.z
        ang = 0.0
        prev_d = sim[0]['dist']
        for s in sim:
            # cap the visible spin at 26 deg/frame: real spin (up to ~120 deg/frame) strobes
            # at 24 fps; capped it still reads as fast, in the right direction
            step = (s['dist'] - prev_d) / WHEEL_R
            prev_d = s['dist']
            ang += max(-math.radians(26), min(math.radians(26), step))
            pv.rotation_euler.y = base.y + ang
            steer = 0.0
            if wi == 2:
                steer = -max(-30, min(30, s['drift'] * 0.4))
            pv.rotation_euler.z = base.z + math.radians(steer)
            pv.keyframe_insert('rotation_euler', frame=s['f'])
            pv.location.z = bz - (0.12 if s['air'] else 0.0)
            pv.keyframe_insert('location', index=2, frame=s['f'])
        K.set_interp(pv, 'LINEAR')


def sim_at(t):
    return sim[min(len(sim) - 1, max(0, int(round(t * FPS))))]


# landing: suspension squash, dust burst, little camera jolt
landings = [s['t'] for a_, s in zip(sim, sim[1:]) if a_['air'] and not s['air']]
takeoffs = [s['t'] for a_, s in zip(sim, sim[1:]) if not a_['air'] and s['air']]
print('OUTRIDER takeoffs', takeoffs, 'landings', landings)
m = hero.model_root
for tl in landings:
    f = P.T(tl)
    m.location.z = 0
    m.keyframe_insert('location', index=2, frame=f - 1)
    m.location.z = -0.18
    m.keyframe_insert('location', index=2, frame=f + 1)
    m.location.z = 0.05
    m.keyframe_insert('location', index=2, frame=f + 4)
    m.location.z = 0
    m.keyframe_insert('location', index=2, frame=f + 7)
    s = sim_at(tl)
    for k in range(9):
        a = k * 2 * math.pi / 9
        P.puff((s['x'] + 1.2 * math.cos(a), s['y'] + 1.2 * math.sin(a), s['z'] + 0.2), tl + 0.01 * k,
               size=0.85, n=1, rise=0.8, life=1.3, opacity=0.3)

# rooster-tail dust from the rear wheels while on the ground and moving
col_d = SAND
for s in sim:
    if s['air'] or s['speed'] < 2.0:
        continue
    hr = math.radians(s['head'])
    back = Vector((-math.cos(hr), -math.sin(hr), 0)) * 1.5
    side = Vector((-math.sin(hr), math.cos(hr), 0)) * 0.85
    sz = 0.32 + min(1.0, s['speed'] / 18) * 0.35 + (0.25 if abs(s['drift']) > 20 else 0)
    for sg in (-1, 1):
        p = Vector((s['x'], s['y'], s['z'] + 0.25)) + back + side * sg
        P.puff(p + Vector((P.rnd.uniform(-.2, .2), P.rnd.uniform(-.2, .2), 0)), s['t'], size=sz, n=1, rise=0.5, life=0.9, color=col_d, opacity=0.24)


# ------------------------------------------------------------------------------ guns
def turret_track(keys):
    """keys: [(t, target)] target is a point or an Actor; the turret yaw is keyed every frame
    between key times, tracking the target as the hull slides and turns. Smoothly blends."""
    tu = hero.turret
    tu.rotation_mode = 'XYZ'
    yaws = []
    for s in sim:
        t = s['t']
        # pick the active target (last key whose time <= t)
        tgt = keys[0][1]
        for tk, tg in keys:
            if tk <= t:
                tgt = tg
        tp = tgt.pos_at(t) if isinstance(tgt, K.Actor) else Vector(tgt)
        d = Vector((tp.x - s['x'], tp.y - s['y']))
        yaw = math.degrees(math.atan2(d.y, d.x)) - s['head']
        if yaws:
            while yaw - yaws[-1] > 180:
                yaw -= 360
            while yaw - yaws[-1] < -180:
                yaw += 360
        yaws.append(yaw)
    # rate-limit the turret (fast, it is a scout: 540 deg/s)
    out = [yaws[0]]
    lim = 540 / FPS
    for y in yaws[1:]:
        out.append(out[-1] + max(-lim, min(lim, y - out[-1])))
    for s, y in zip(sim, out):
        tu.rotation_euler.z = math.radians(y)
        tu.keyframe_insert('rotation_euler', index=2, frame=s['f'])
    K.set_interp(tu, 'LINEAR')


FORWARD = None  # sentinel: point ahead of the hull


def ahead(t, dist_=10):
    s = sim_at(t)
    hr = math.radians(s['head'])
    return Vector((s['x'] + math.cos(hr) * dist_, s['y'] + math.sin(hr) * dist_, 1))


turret_track([
    (0.0, (5, 3, 1)),                     # already eyeing the camp as it crests
    (1.5, lumA),
    (2.4, sifter),
    (2.78, lumB),
    (3.2, (14, -20, 1)),                  # faces the way out as it bolts
    (4.4, (40, -20, 1)),
    (5.4, lumA),                          # swings round for the parting shot
])


def burst(t, target, n=3, gap=3, spread=0.35):
    """A scout's burst: n weak autocannon rounds `gap` frames apart, barrel snapping back
    ~80% each round, tiny hull twitch, small pings on the target."""
    fr0 = P.T(t)
    b = hero.barrels[0] if hero.barrels else None
    L = b['barrel_len'] * 0.8 if b else 0
    for k in range(n):
        tk = t + k * gap / FPS
        hero.fire(tk, target, kind='autocannon', recoil=False, spread=spread, size=1.15, impact_size=0.55)
        if b:
            fk = fr0 + k * gap
            b.location.x = 0 if k == 0 else -L * 0.25
            b.keyframe_insert('location', index=0, frame=fk - 1)
            b.location.x = -L
            b.keyframe_insert('location', index=0, frame=fk)
            b.location.x = -L * 0.25
            b.keyframe_insert('location', index=0, frame=fk + 2)
    if b:
        b.location.x = 0
        b.keyframe_insert('location', index=0, frame=fr0 + (n - 1) * gap + 6)
    return t + (n - 1) * gap / FPS


def ping(actor, t, amt=4.0):
    """A weak hit: the target flinches."""
    mr = actor.model_root
    mr.rotation_mode = 'XYZ'
    f = P.T(t)
    mr.keyframe_insert('rotation_euler', index=0, frame=f - 1)
    mr.rotation_euler.x = math.radians(amt)
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 2)
    mr.rotation_euler.x = math.radians(-amt * 0.4)
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 6)
    mr.rotation_euler.x = 0
    mr.keyframe_insert('rotation_euler', index=0, frame=f + 10)


burst(2.0, lumA)
ping(lumA, 2.08)
burst(2.45, sifter)
ping(sifter, 2.52, 2.5)
burst(2.85, lumB)
ping(lumB, 2.92)
burst(5.72, (13.0, -10.5, 2.2), spread=0.5)


# ------------------------------------------------------------------------------ lightning
def strike(src, t, at, aim_dur=0.25):
    """Lumen fires gold lightning that hits the dirt at `at`: flash, sparks, scorch, dirt."""
    src.aim(t, at, dur=aim_dur)
    at = Vector(at)
    at.z = ground(at.x, at.y) + 0.05
    mz = src.world_at(src.muzzle(), t)
    P.muzzle_flash(src.muzzle(), t, GOLD, 0.8)
    src.recoil(t, kick=1.5, back=0.08)
    gold_bolt(mz, at, t, t + 0.2, width=0.075)
    gold_sparks(at + Vector((0, 0, 0.1)), t + 0.02)
    P.light(at + Vector((0, 0, 0.6)), t, GOLD, energy=450, dur=0.12)
    for k in range(6):  # dirt kick: a ring of small sand puffs thrown up
        a = k * math.pi / 3 + P.rnd.uniform(0, 0.5)
        P.puff(at + Vector((0.5 * math.cos(a), 0.5 * math.sin(a), 0.15)), t + 0.02 + 0.015 * k,
               size=0.55, n=1, rise=1.1, life=1.1, opacity=0.38)
    f0 = P.T(t)
    sc = K.sphere('Scorch', 1.0, K.pbr_mat('ScorchM', (0.02, 0.016, 0.012), 1.0), seg=(16, 6))
    sc.location = (at.x, at.y, at.z - 0.01)
    sc.scale = (0.75, 0.75, 0.02)
    K.show_between(sc, f0 + 1, P.T(P.seconds) + 2)
    glow = K.sphere('ScorchGlow', 1.0, K.emit_mat('ScorchGlowM', COL['arc_ember'], 0.8), seg=(16, 6))
    glow.location = (at.x, at.y, at.z + 0.01)
    glow.scale = (0.35, 0.35, 0.02)
    K.show_between(glow, f0 + 1, f0 + 7)
    P.puff(at + Vector((0, 0, 0.3)), t + 0.06, size=0.9, n=2, rise=1.2, life=1.4, opacity=0.3)


def where(t):
    s = sim_at(t)
    return (s['x'], s['y'], 0)


strike(lumA, 3.25, where(2.95))
strike(lumB, 3.55, (where(3.3)[0] - 0.3, where(3.3)[1], 0))
strike(lumA, 3.9, where(3.68))
strike(lumB, 4.3, where(4.05))
strike(lumA, 4.95, where(4.72))
strike(lumB, 5.3, (24.2, -16.4, 0))
strike(lumA, 5.82, (25.0, -17.6, 0))

# ------------------------------------------------------------------------------ camera
CUT = 4.75
P.camera([
    (0.0, (13.2, -3.2, 0.6), (24.5, 4.6, 2.1), 28),
    (0.5, (13.6, -3.0, 0.75), (21.0, 4.2, 1.9), 28),
    (0.95, (14.4, -2.9, 1.1), (15.5, 3.0, 1.0), 28),
    (1.5, (17.6, -1.8, 2.0), (11.5, 2.2, 0.9), 28),
    (2.2, (17.8, 3.4, 2.6), (6.0, 0.6, 1.0), 28),
    (2.9, (16.9, 3.6, 2.4), (5.0, 0.0, 1.0), 31),
    (3.5, (17.6, 0.6, 2.2), (11.0, -2.5, 0.9), 28),
    (CUT - 1 / FPS, (18.8, -5.0, 1.8), (13.8, -9.5, 0.9), 27),
    (CUT, (38.6, -12.6, 0.7), (24.0, -16.2, 2.0), 40),
    (5.3, (41.0, -13.8, 0.85), (29.5, -18.0, 1.6), 36),
    (6.0, (43.4, -17.0, 1.0), (33.6, -19.1, 1.15), 36),
], shake=0.03, cuts=[CUT])
# hard cut: hold the pre-cut key constant into the cut frame
for ob in (P.cam, P.cam_target, P.cam.data):
    ad = ob.animation_data
    for fc in K._fcurves(ad.action):
        for kp in fc.keyframe_points:
            if abs(kp.co.x - P.T(CUT - 1 / FPS)) < 0.01:
                kp.interpolation = 'CONSTANT'
                kp.handle_left_type = 'VECTOR'
                kp.handle_right_type = 'VECTOR'
            if abs(kp.co.x - P.T(CUT)) < 0.01:
                kp.handle_left_type = 'VECTOR'
                kp.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
for tl in landings:
    P.cam_shake(tl, 0.07, 0.3)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
_on = False                                           # power-slides: a skid each time the drift kicks in
for _s in sim:
    _d = abs(_s['drift']) > 20 and not _s['air'] and _s['speed'] > 4
    if _d and not _on:
        P.sfx(_s['t'], 'skid', gain=0.7, pos=(_s['x'], _s['y'], _s['z']))
    _on = _d
for _t in takeoffs:                                   # wheels leave the ground: engine flares
    P.sfx(_t, 'whoosh', gain=0.3, rate=1.2)

P.render()
