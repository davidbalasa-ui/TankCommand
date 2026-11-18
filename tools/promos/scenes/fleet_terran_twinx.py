"""Terran Twin-X fighter (space): three Twin-X fighters cruise in echelon over the back of a
Terran Dreadnought. Far below, two gold Arcadian Stingrays slide across the planet. The Twin-X
peel off one after another, each with a barrel roll, and dive on them. The lead Twin-X runs
down the first Stingray, its four wingtip guns hammering in alternating pairs, and blows it
apart; the second ray lashes the right wingman with gold lightning but is caught in a pincer
by both wingmen (B: slow four-gun salvos, C: 3-round bursts) and dies. The three re-form and
come at the camera, the Dreadnought behind them and the rays' wreckage drifting past.

Timeline (s): 0-1.75 high over the Dreadnought behind the echelon, peel-offs at 0.5 / 0.75 /
1.0 | 1.75-3.5 chase cam behind the lead: guns open 2.05, hits from 2.6, ray 1 fractures 3.0 |
3.5-4.5 the pincer: ray 2 lashes C 3.6, B and C open fire 3.85, ray 2 fractures 4.35 |
4.5-6.0 front 3/4 on the re-formed trio, push in, end on the lead big with the Dreadnought
behind.

Ships are film placeholders: loaded by name, nose along +X (models.json kind 'ship').
Twin-X glow materials are tinted to Terran neon blue + orange in this scene only."""
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

P = Promo('fleet_terran_twinx', seconds=6.0, seed=47)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

P.space(planet=(700, -150, -900, 760, (0.16, 0.26, 0.42)), nebula=(0.07, 0.03, 0.11),
        sun=(55, 0, 140), sun_energy=4.0)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------- flight helpers
def frame_from(fwd, up_hint):
    x = fwd.normalized()
    y = up_hint.cross(x)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)).cross(x)
    y.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def fly(actor, posf, upf, roll_extra=None):
    """Key root location + quaternion every frame. Nose along velocity."""
    r = actor.root
    r.rotation_mode = 'QUATERNION'
    mats = {}
    prev_q = None
    dt = 1.0 / FPS
    for f in range(0, NF + 2):
        t = (f - 1) / FPS
        p = posf(t)
        v = (posf(t + dt * 0.5) - posf(t - dt * 0.5)) / dt
        a = (posf(t + dt) - 2 * p + posf(t - dt)) / (dt * dt)
        m3 = frame_from(v, upf(t, p, v, a))
        if roll_extra:
            m3 = m3 @ Matrix.Rotation(roll_extra(t), 3, 'X')
        q = m3.to_quaternion()
        if prev_q is not None:
            q.make_compatible(prev_q)
        prev_q = q
        r.location = p
        r.rotation_quaternion = q
        r.keyframe_insert('location', frame=f)
        r.keyframe_insert('rotation_quaternion', frame=f)
        mats[f] = Matrix.Translation(p) @ m3.to_4x4()
    K.set_interp(r, 'LINEAR')
    actor.mats = mats
    actor.posf = posf
    return mats


def W(actor, t, local=(0, 0, 0)):
    f = max(0, min(NF + 1, int(round(P.T(t)))))
    return actor.mats[f] @ Vector(local)


def bank_up(k=1.0, clamp=55):
    """Bank into turns: back points along +Z plus k * lateral acceleration."""
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


# Everything is keyed in a frame cruising along +X with the fleet.
U = Vector((30, 0, 0))


def F(t):
    return U * t


def rel(keys):
    return spline([(t, F(t) + Vector(p)) for t, p in keys])


# ------------------------------------------------------------------------------- timing
CUT1, CUT2, CUT3 = 42 / 24, 84 / 24, 108 / 24     # 1.75, 3.5, 4.5 s
PEEL = (0.5, 0.75, 1.0)
T_FIRE_A0, T_FIRE_A1 = 2.05, 2.95
T_KILL1 = 3.0
T_LASH, T_LASH1 = 3.6, 3.85
T_FIRE_BC0, T_FIRE_BC1 = 3.85, 4.3
T_KILL2 = 4.35

# ------------------------------------------------------------------------------- the fleet
DN = P.load('terran_dreadnought', size=170, label='dreadnought')
dn_pos = rel([(0.0, (-10, -60, -52)), (6.0, (-58, -60, -52))])
fly(DN, dn_pos, lambda t, p, v, a: Vector((0, 0, 1)))

# ------------------------------------------------------------------------------- Stingrays
s1_pos = rel([
    (-0.5, (88, -92, -82)),
    (0.0, (90, -74, -80)),
    (1.0, (98, -40, -72)),
    (2.0, (118, -8, -62)),
    (2.5, (134, 4, -58)),
    (3.0, (124, 2, -54)),
    (3.5, (116, -4, -52)),
])
s2_pos = rel([
    (-0.5, (102, -68, -96)),
    (0.0, (105, -50, -95)),
    (1.5, (125, 10, -88)),
    (2.5, (142, 38, -80)),
    (3.5, (140, 56, -74)),
    (4.0, (134, 62, -70)),
    (4.5, (128, 66, -66)),
])
RAY_SIZE = 13.0   # nudged up from 10 so the rays read at phone size
s1 = P.load('arcadian_stingray', size=RAY_SIZE, label='ray1')
s2 = P.load('arcadian_stingray', size=RAY_SIZE, label='ray2')


def s1_roll(t):
    # evasive jinks while the lead closes
    return math.radians(38) * math.sin(5.5 * (t - 1.9)) * ss((t - 1.9) / 0.4)


fly(s1, s1_pos, bank_up(1.4, 60), roll_extra=s1_roll)
fly(s2, s2_pos, bank_up(1.4, 60))

# ------------------------------------------------------------------------------- Twin-X
# Hero frame: camera low and ahead-right of the lead; wingmen set behind it in camera space so
# the end frame is a balanced arrowhead.
# 3/4 front, a little above: the X-wings read in profile and the Dreadnought fills the
# background behind the trio (they are heading home past the fleet)
S4_OFF0 = Vector((21, 15, 6.5))
S4_OFF1 = Vector((14, 9, 4.5))
A_END = Vector((152, 22, -47))
A_END_V = Vector((20, 4, 0))
_fw = -S4_OFF1.normalized()
_rt = _fw.cross(Vector((0, 0, 1))).normalized()
_up = _rt.cross(_fw).normalized()
WING_B = A_END + _fw * 17 + _rt * 10 + _up * 1.0
WING_C = A_END + _fw * 19 - _rt * 9 - _up * 3.5
a_pos = rel([
    (-0.5, (-2, 0, 0.3)),
    (0.0, (0, 0, 0)),
    (0.5, (2, 0, 0)),
    (1.1, (20, -8, -14)),
    (1.75, (46, -10, -34)),
    (2.3, (70, -6, -48)),
    (2.8, (90, -2, -52)),
    (3.1, (102, 0, -50)),
    (3.5, (114, 4, -44)),
    (4.5, (128, 12, -44)),
    (5.3, (140, 18, -46)),
    (6.0, (152, 22, -47)),
    (6.5, (162, 24, -47)),
])
b_pos = rel([
    (-0.5, (-12, 12, 1.8)),
    (0.0, (-10, 12, 1.5)),
    (0.75, (-6, 13, 1.5)),
    (1.4, (12, 22, -14)),
    (2.5, (52, 40, -40)),
    (3.5, (86, 50, -54)),
    (4.0, (102, 54, -58)),
    (4.4, (114, 54, -60)),
    (5.0, (126, 38, -51)),
    (6.0, tuple(WING_B)),
    (6.5, tuple(WING_B + A_END_V * 0.5)),
])
c_pos = rel([
    (-0.5, (-22, 24, 3.3)),
    (0.0, (-20, 24, 3)),
    (1.0, (-14, 25, 3)),
    (1.7, (4, 36, -18)),
    (2.6, (44, 52, -56)),
    (3.5, (82, 62, -70)),
    (4.0, (100, 64, -72)),
    (4.4, (114, 62, -70)),
    (5.0, (127, 34, -60)),
    (6.0, tuple(WING_C)),
    (6.5, tuple(WING_C + A_END_V * 0.5)),
])


def peel_roll(tp, d=0.7):
    return lambda t: 2 * math.pi * ss((t - tp) / d)


twA = P.load('terran_twinx', label='twinA')
twB = P.load('terran_twinx', label='twinB')
twC = P.load('terran_twinx', label='twinC')
fly(twA, a_pos, bank_up(0.6, 60), roll_extra=peel_roll(PEEL[0]))
fly(twB, b_pos, bank_up(0.6, 60), roll_extra=peel_roll(PEEL[1]))
fly(twC, c_pos, bank_up(0.6, 60), roll_extra=peel_roll(PEEL[2]))
TWINS = (twA, twB, twC)

# Terran glow: the placeholder ships glow violet; tint scene copies to neon blue + orange.
TINT = {'twinx_arc': (NEON, 3.0), 'twinx_haze': (NEON, 0.7), 'twinx_orb': (ORANGE, 2.6)}
for m in bpy.data.materials:
    base = m.name.split('.')[0]
    if not m.use_nodes or not m.node_tree:
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

# ------------------------------------------------------------------------------- wingtip guns
TIPS = [(1, 1), (-1, -1), (1, -1), (-1, 1)]       # (y sign, z sign); fired as two diagonal pairs
GUN_Y = GUN_Z = 3.79
GUN_TIP_X = 4.45


def split_guns(actor):
    """Cut the four wingtip barrels out of the wing mesh; each hangs on a pivot at its rear so
    it can telescope ~80% back into the wing on every shot."""
    wing = [o for o in actor.meshes if o.name.startswith('TwinX_Wings')][0]
    me = wing.data
    mi = [i for i, m in enumerate(me.materials) if m and 'barrel' in m.name][0]
    bpy.context.view_layer.update()
    mw = wing.matrix_world.copy()
    root_inv = actor.root.matrix_world.inverted()
    to_root = root_inv @ mw
    bm = bmesh.new()
    bm.from_mesh(me)
    groups = {k: [] for k in TIPS}
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
    # remove barrel faces from the wing
    dead = [f for f in bm.faces if f.material_index == mi]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bm.to_mesh(me)
    bm.free()
    # muzzle empties on the root (fixed at the extended tip)
    mz = {}
    for key in TIPS:
        e = K.empty(actor.name + '_Muzzle')
        e.parent = actor.root
        e.matrix_parent_inverse = Matrix()
        e.location = (GUN_TIP_X, key[0] * GUN_Y, key[1] * GUN_Z)
        mz[key] = e
    actor.gun_pivots = pivots
    actor.gun_muzzles = mz
    return pivots


for tw in TWINS:
    tw.root.rotation_mode = 'QUATERNION'
    bpy.context.scene.frame_set(1)
    split_guns(tw)


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
    m.location.x = 0
    m.rotation_euler.y = 0
    m.keyframe_insert('location', index=0, frame=f - 0.5)
    m.keyframe_insert('rotation_euler', index=1, frame=f - 0.5)
    m.location.x = -back
    m.rotation_euler.y = math.radians(-kick)
    m.keyframe_insert('location', index=0, frame=f + 0.8)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 0.8)
    m.location.x = 0
    m.rotation_euler.y = 0
    m.keyframe_insert('location', index=0, frame=f + 2.6)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 2.6)


def strafe(actor, target, t0, t1, every=3, hit_from=None, miss=3.0, bolt_speed=260, salvo=False,
           burst=0, gap=0):
    """Each pilot has its own rhythm: alternating diagonal pairs every `every` frames, or all
    four guns at once (salvo), optionally in bursts of `burst` shots with `gap` frames between.
    Shots before hit_from go wide."""
    pairs = (TIPS,) if salvo else (TIPS[:2], TIPS[2:])
    f = int(round(P.T(t0)))
    k = 0
    hits = []
    while f < P.T(t1):
        t = (f - 1) / FPS
        tgt = W(target, t + 0.12)
        hit = hit_from is not None and t >= hit_from
        for key in pairs[k % len(pairs)]:
            p0 = W(actor, t, actor.gun_muzzles[key].location)
            aim = tgt.copy()
            if not hit:
                aim += Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))).normalized() * miss
                aim = p0 + (aim - p0) * 1.6           # misses fly on past the target
            else:
                aim += Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.3, 0.3))) * 0.8
            th = P.projectile(p0, aim, t, speed=bolt_speed, color=NEON, size=0.3)
            P.muzzle_flash(actor.gun_muzzles[key], t, NEON, 0.55)
            gun_recoil(actor, key, t)
            if hit:
                hits.append((th, aim))
        hull_kick(actor, t, kick=2.4 if salvo else 1.6, back=0.5 if salvo else 0.35)
        k += 1
        f += every
        if burst and k % burst == 0:
            f += gap
    for i, (th, p) in enumerate(hits):
        if i % 2 == 0:
            P.impact(p, th, size=0.9, color=NEON)
    return hits


# lead: fast alternating pairs; B: slow four-gun salvos; C: 3-round bursts
strafe(twA, s1, T_FIRE_A0, T_FIRE_A1, every=3, hit_from=2.6)
strafe(twB, s2, T_FIRE_BC0, T_FIRE_BC1, every=6, hit_from=4.05, salvo=True)
strafe(twC, s2, T_FIRE_BC0 + 0.1, T_FIRE_BC1, every=2, hit_from=4.1, burst=3, gap=5)

# ------------------------------------------------------------------------------- Stingray fx
_rk = RAY_SIZE / 10.0
RAY_NOSE = Vector((4.6, 0, -0.5)) * _rk
RAY_TRAIL = [Vector((-1.2, 0.9, -0.35)) * _rk, Vector((-1.2, -0.9, -0.35)) * _rk]
RAY_TIPS = [Vector((-0.9, 4.7, 0.2)) * _rk, Vector((-0.9, -4.7, 0.2)) * _rk]


def attach_new(before, parent):
    for o in bpy.data.objects:
        if o not in before and o.parent is None:
            o.parent = parent
            o.matrix_parent_inverse = Matrix()


def thrust(actor, t0, t1, length, width, tips=False):
    """Gold lightning thrusters (kit lightning_thruster: crackling bolts that ride the ray)."""
    for p in RAY_TRAIL:
        WFX.lightning_thruster(P, actor, t0, t1, local=p, axis=(-1, 0.04 * p.y, 0), length=length,
                               width=width * 0.6, n=2, spread=0.25, color=GOLD, light=False)
    if tips:
        for p in RAY_TIPS:
            WFX.lightning_thruster(P, actor, t0, t1, local=p, axis=(-1, 0.03 * p.y, 0), length=length * 0.45,
                                   width=width * 0.4, n=1, spread=0.3, color=GOLD, light=False)


thrust(s1, 0.0, 1.9, 6.5, 0.12, False)
thrust(s1, 1.9, T_KILL1 + 0.05, 9.0, 0.14, True)
thrust(s2, 0.0, 3.4, 6.5, 0.12, False)
thrust(s2, 3.4, T_KILL2 + 0.05, 9.0, 0.14, True)


def lash(src, dst, t0, t1, hit_local=(0, 0, 0)):
    # one bolt whose ends ride both ships (the kit follows callables per frame)
    P.lightning(lambda t: W(src, t, RAY_NOSE), lambda t: W(dst, t, hit_local), t0, t1, color=GOLD,
                width=0.11, jag=0.16, branches=2, segs=12)
    P.impact(W(dst, t0 + 0.05, hit_local), t0 + 0.05, size=1.2, color=GOLD)


# ray 2 turns on its hunters and scorches C's upper wing; C rides it out
lash(s2, twC, T_LASH, T_LASH1, hit_local=(0.5, 2.6, 2.6))


def kill(actor, t, size=5.0):
    """Space kill: the ray fractures into its own pieces, which drift on without gravity
    (promo_fx.destroy handles space), plus a fireball and sparks."""
    actor.destroy(t, size=size, wreck=False, debris=12)
    P.cam_shake(t + 0.02, 0.25, dur=0.35)


kill(s1, T_KILL1)
kill(s2, T_KILL2)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2200, box=((-120, 420), (-120, 140), (-130, 40)), size=0.1, avoid=()):
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

    # Shot 1: high behind the echelon, Dreadnought below right; tilt down with the peel-offs.
    def s1f(t, u):
        base = F(t)
        pos = base + Vector((lerp(-50, -36, ss(u)), lerp(32, 24, ss(u)), lerp(22, 14, ss(u))))
        mid = (a_pos(t) + b_pos(t) + c_pos(t)) / 3
        look = (base + Vector((22, -26, -24))).lerp(mid, 0.6 * ss(u * 1.2))
        return pos, look, lerp(24, 28, ss(u))
    shot(0, CUT1, 14, s1f)

    # Shot 2: chase high and wide of the lead, ray 1 ahead of it in frame.
    def s2f(t, u):
        a = a_pos(t)
        pos = a + Vector((lerp(-22, -18, ss(u)), lerp(-18, -14, ss(u)), lerp(12, 10, ss(u))))
        look = a.lerp(W(s1, min(t, T_KILL1)), lerp(0.5, 0.55, ss(u)))
        return pos, look, 30
    shot(CUT1, CUT2, 12, s2f)

    # Shot 3: behind and between the wingmen as they pincer ray 2.
    def s3f(t, u):
        mid = (b_pos(t) + c_pos(t)) / 2
        s = W(s2, min(t, T_KILL2))
        pos = mid + Vector((lerp(-30, -22, ss(u)), lerp(-8, -6, ss(u)), 4))
        look = mid.lerp(s, 0.6)
        return pos, look, 26
    shot(CUT2, CUT3, 10, s3f)

    # Shot 4: ahead of the re-formed trio, low, pushing in on the lead.
    def s4f(t, u):
        a = a_pos(t)
        o = S4_OFF0.lerp(S4_OFF1, ss(u))
        pos = a + o
        w = 0.12 * ss(u * 1.3)       # open on the lead, let the wingmen into the frame as they arrive
        look = a * (1 - 2 * w) + (b_pos(t) + c_pos(t)) * w + Vector((0, 0, lerp(1.0, 3.0, ss(u))))
        return pos, look, lerp(34, 38, ss(u))
    shot(CUT3, 6.0, 10, s4f, last=False)
    return keys


P.camera(cam_keys(), lens=28, cuts=(CUT1, CUT2, CUT3))

# dust specks are generated after the camera so none sits on its path (a speck right at the lens
# renders as a big pale polygon)
_cam_path = []
for _f in range(1, NF + 1):
    bpy.context.scene.frame_set(_f)
    _cam_path.append(P.cam.matrix_world.translation.copy())
dust_field(avoid=_cam_path)

# ------------------------------------------------------------------------------- sound cues
for tp, tw in zip(PEEL, TWINS):
    P.sfx(tp + 0.1, 'whoosh', gain=0.8, pos=W(tw, tp + 0.3))
P.sfx(T_FIRE_A0 - 0.25, 'lock_pulse', gain=0.5)
# the lash is one bolt with moving ends (callables), which the audio recorder can't place
P.sfx(T_LASH, 'zap_lightning', gain=1.0, pos=W(twC, T_LASH))
P.sfx(T_LASH, 'crackle_loop', gain=0.5, pos=W(twC, T_LASH), dur=T_LASH1 - T_LASH)
P.sfx(CUT3, 'whoosh', gain=0.9, pos=W(twA, CUT3 + 0.3))
P.sfx(5.3, 'thruster_blue', gain=0.6, pos=W(twA, 5.3), dur=0.7)

P.render()
