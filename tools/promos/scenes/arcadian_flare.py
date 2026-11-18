"""Flare (Arcadian rocket artillery): six pods, one breath, one ripple, two kills.

The Flare glides in on its skirt of gold lightning and settles. A Terran Lancer's shell bursts
behind it; a Falcon is diving in on a strafing run. The arch swings onto the bearing and the six
pod noses light one by one, crackling to each other... a beat of stillness... then the ripple:
six gold seeker orbs, one every few frames, each pod slamming back into the arch and the hull
rocking under the salvo. The first two curl straight up and swat the Falcon out of the sky; the
other four loft high over the field and rain down on the Lancer. End low beside the Flare, its
pods dark and reloading one by one, the Lancer burning behind it and the Falcon's wreckage
smoking down the sky.

Timeline (s): 0-1.1 glide in + settle | 0.85 Lancer shell bursts behind | 0.7-1.5 arch slews |
1.15-1.75 pods charge one by one | 1.75-2.05 the pause | 2.08-2.53 ripple (6 orbs) | ~2.95
Falcon dies | ~3.7-4.0 four orbs rain on the Lancer | 4.5-5.9 the reload, noses refill.

0-2.0     low front 3/4 push-in: the Flare settles, slews, the pods charge.
2.0-3.5   low behind its shoulder, wide: the ripple, orbs curl up, the Falcon bursts.
3.5-6     low beside the Flare looking down-range: orbs rain on the Lancer; the reload."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as W  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('arcadian_flare', seconds=6.0, seed=5)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)

LX, LY = 12.5, 9.0          # the Lancer
P.env('dusk', sun=(68, 0, -150), props=30, clear=[(0, 0, 9), (LX, LY, 6), (6, 4, 6)])
P.flatten(0, 0, 10)
P.flatten(LX, LY, 7)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


# --------------------------------------------------------------------------- the Flare
HOV = 0.12
flare = P.load('flare', at=(-7.5, -2.6), heading=12, label='flare')
flare.path([
    (0.0, (-7.5, -2.6, HOV)),
    (0.55, (-2.6, -0.7, HOV)),
    (1.05, (0.0, 0.0, HOV), 6.0),
    (6.0, (0.0, 0.0, HOV), 6.0),
])
flare.hover_bob(0.025, 0.9)
bpy.context.view_layer.update()
tu = flare.parts['Turret']
hull = flare.parts['Hull']
inv_m = flare.model_root.matrix_world.inverted()
T2M = inv_m @ tu.matrix_world             # turret local -> model space
M2T = T2M.inverted()

# --- cut the six pods out of the arch so each can slam back on its own shot
# pod axes (model space, measured from the emissive noses): front arch x>0.69, rear arch below
POD_AX = [((0.73, 1.96), 'F'), ((0.0, 2.3), 'F'), ((-0.73, 1.96), 'F'),
          ((0.73, 1.91), 'B'), ((0.0, 2.15), 'B'), ((-0.73, 1.91), 'B')]
POD_R = 0.36
bm = bmesh.new()
bm.from_mesh(tu.data)
bm.faces.ensure_lookup_table()
sel = {i: [] for i in range(6)}
for fc in bm.faces:
    c = T2M @ fc.calc_center_median()
    for i, ((y, z), row) in enumerate(POD_AX):
        inx = c.x > 0.69 if row == 'F' else (-0.22 < c.x < 0.6)
        if inx and math.hypot(c.y - y, c.z - z) < POD_R:
            sel[i].append(fc.index)
            break
pods = []
for i in range(6):
    b2 = bm.copy()
    b2.faces.ensure_lookup_table()
    keep = set(sel[i])
    bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
    me = bpy.data.meshes.new(f'FlarePod{i}')
    b2.to_mesh(me)
    b2.free()
    for m in tu.data.materials:
        me.materials.append(m)
    slide = K.empty(f'FlarePodSlide{i}')
    slide.parent = tu
    po = link(bpy.data.objects.new(me.name, me))
    po.parent = slide
    ms = [T2M @ v.co for v in me.vertices]
    xs = [p.x for p in ms]
    x0, x1 = min(xs), max(xs)
    tipv = [p for p in ms if p.x > x1 - 0.12 * (x1 - x0)]
    basev = [p for p in ms if p.x < x0 + 0.2 * (x1 - x0)]
    tip = sum(tipv, Vector()) / len(tipv)
    base = sum(basev, Vector()) / len(basev)
    ax = (tip - base).normalized()
    pods.append(dict(obj=po, slide=slide, tip=Vector((x1, tip.y, tip.z)), axis=ax, len=x1 - x0))
    print('POD', i, len(sel[i]), 'tip', tuple(round(c, 2) for c in (x1, tip.y, tip.z)),
          'axis', tuple(round(c, 2) for c in ax), 'len', round(x1 - x0, 2))
all_idx = set().union(*sel.values())
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in all_idx], context='FACES')
bm.to_mesh(tu.data)
bm.free()

# nose empties (ride the pod slides), pointing along each pod
noses = []
for i, pd in enumerate(pods):
    e = K.empty(f'FlareNose{i}')
    e.parent = pd['slide']
    e.location = M2T @ (pd['tip'] + pd['axis'] * 0.02)
    e.rotation_mode = 'QUATERNION'
    dirt = (M2T.to_3x3() @ pd['axis']).normalized()
    e.rotation_quaternion = dirt.to_track_quat('X', 'Z')
    noses.append(e)
bpy.context.view_layer.update()
for e in noses:      # unit world scale, so glows and flashes hung on the noses are sized in metres
    e.scale = (1 / e.parent.matrix_world.to_scale().x,) * 3
bpy.context.view_layer.update()
print('NOSE world scale', noses[0].matrix_world.to_scale())

# --------------------------------------------------------------------------- lightning lifters
# Short, dense crackle tucked right under the belly (the Darter / Aegis skirt).
bolt_mat = emit_mat('FlareLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('FlareLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)
BX0, BX1, BY, BZ = -1.3, 1.7, 0.75, 0.36


def jag(p0, p1, segs, amp):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            e = math.sin(math.pi * u)
            q += Vector((R.uniform(-amp, amp), R.uniform(-amp, amp), R.uniform(-amp, amp) * 0.5)) * e
        pts.append(q)
    return pts


def crackle(a, n_lift=12):
    for f in range(1, NF + 2):
        objs = []
        for k in range(n_lift):
            p0 = Vector((R.uniform(BX0, BX1), R.uniform(-BY, BY), BZ))
            if k % 3 == 0:
                p1 = p0 + Vector((R.uniform(-0.5, 0.5), R.uniform(-0.2, 0.2), -R.uniform(0.0, 0.1)))
            else:
                side = 1 if p0.y > 0 else -1
                p1 = p0 + Vector((R.uniform(-0.25, 0.15), side * R.uniform(0.1, 0.3), -R.uniform(0.15, 0.3)))
            pts = jag(p0, p1, 4, 0.07)
            objs += [polyline('FLift', pts, 0.013, bolt_mat), polyline('FLiftHalo', pts, 0.045, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            o.visible_shadow = False
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('FlareLiftLight', bpy.data.lights.new('FlareLiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, 0.15)
    L.data.color = GOLD
    L.data.energy = 120
    L.data.shadow_soft_size = 0.8


crackle(flare)
P.dust(flare, 0.0, 1.2, every=0.09, size=0.55)

# --------------------------------------------------------------------------- the threats
lancer = P.load('lancer', at=(LX, LY), heading=216, label='lancer')
lancer.split_barrels()
lancer.path([(0.0, (LX + 1.9, LY + 1.4)), (2.4, (LX + 0.25, LY + 0.2)), (3.2, (LX, LY))])

# the Falcon: diving in from down-range on a strafing run
falcon = P.load('falcon', label='falcon')
F_KEYS = [(0.0, (72.0, 31.0, 24.0)), (1.0, (51.0, 21.5, 19.5)), (2.0, (31.0, 12.5, 14.5)),
          (3.0, (13.0, 4.5, 11.0)), (4.0, (-5.0, -3.5, 9.0))]
falcon.path(F_KEYS, pitch=True, interp='LINEAR')


def falcon_at(t):
    for (ta, pa), (tb, pb) in zip(F_KEYS, F_KEYS[1:]):
        if ta <= t <= tb:
            return Vector(pa).lerp(Vector(pb), (t - ta) / (tb - ta))
    return Vector(F_KEYS[-1][1])


# the Falcon opens its strafing run: twin laser bursts walking through the dirt toward the Flare
for t_, x_, y_ in ((1.78, 5.2, 1.6), (1.86, 4.0, -1.2), (1.98, 3.0, 1.1), (2.04, 2.3, -0.9)):
    P.shot((falcon, (2.4, 0.0, 0.3)), Vector((x_, y_, gz(x_, y_) + 0.05)), 'laser', t_, size=0.9)

# Lancer shell bursts in the dirt behind the Flare (it is under fire)
T_SHELL = 0.85
miss = Vector((-4.6, 2.4, gz(-4.6, 2.4) + 0.05))
lancer.aim(T_SHELL, miss, dur=0.5)
lancer.fire(T_SHELL, miss, kind='cannon', impact_size=1.0)

# --------------------------------------------------------------------------- slew + charge
T_CHG = [1.15, 1.25, 1.35, 1.45, 1.55, 1.65]
T_RIP = [2.08, 2.17, 2.26, 2.35, 2.44, 2.53]
ORDER = [1, 0, 2, 4, 3, 5]       # which pod fires on each shot: front top, front sides, rear...
TGT = ['F', 'F', 'L', 'L', 'L', 'L']
T_RELOAD = [4.55, 4.78, 5.01, 5.24, 5.47, 5.70]

flare.aim(1.5, falcon_at(2.9).lerp(Vector((LX, LY, 1.0)), 0.5), dur=0.8)
flare.aim(5.9, Vector((LX + 3.0, LY - 6.0, 1.0)), dur=1.2)

sc = bpy.context.scene
nose_glow = []
for i, e in enumerate(noses):
    k = ORDER.index(i)
    core = W.glow(P, 'NoseCore', GOLD, alpha=0.0, fx_e=2.6, fx_p=0.9, fx_hot=0.55)
    core.parent = e
    core.scale = (0.12, 0.12, 0.12)
    halo = W.glow(P, 'NoseHalo', DEEP_GOLD, alpha=0.0, fx_e=1.3, fx_p=2.6)
    halo.parent = e
    halo.scale = (0.24, 0.24, 0.24)
    tc, tf, tr = T_CHG[i], T_RIP[k], T_RELOAD[i]
    for o, full in ((core, 2.4), (halo, 0.6)):
        for fr, v in [(1, 0.0), (P.T(tc) - 1, 0.0), (P.T(tc) + 1, full * 1.4), (P.T(tc) + 4, full),
                      (P.T(tf) - 3, full), (P.T(tf) - 1, full * 1.35), (P.T(tf), 0.0),
                      (P.T(tr), 0.0), (P.T(tr) + 3, full * 1.3), (P.T(tr) + 7, full * 0.9), (NF + 2, full)]:
            # dark = transparent (alpha 0), never a black emitter
            W.kprop(o, 'fx_e', fr, full * max(1.0, v / full))
            W.kcol(o, fr, a=min(1.0, v / full))
    L = link(bpy.data.objects.new('NoseLight', bpy.data.lights.new('NoseLight', 'POINT')))
    L.parent = e
    L.location = (0.15, 0, 0)
    L.data.color = GOLD
    L.data.shadow_soft_size = 0.2
    for fr, v in [(1, 0), (P.T(tc) - 1, 0), (P.T(tc) + 1, 60), (P.T(tf) - 1, 60), (P.T(tf), 0),
                  (P.T(tr), 0), (P.T(tr) + 4, 50), (NF + 2, 50)]:
        L.data.energy = v
        L.data.keyframe_insert('energy', frame=fr)
    nose_glow.append((core, halo))
    P.sfx(tc, 'power_up_arc', gain=0.35, rate=1.0 + 0.1 * i)


def nose_pt(i):
    return noses[i].matrix_world.translation.copy()


# charge crackle: little gold arcs jumping between lit noses while it holds the breath
for t0 in (1.5, 1.62, 1.74, 1.86, 1.96):
    a, b = R.sample(range(6), 2)
    sc.frame_set(int(round(P.T(t0))))
    P.lightning(nose_pt(a), nose_pt(b), t0, t0 + 0.08, width=0.018, jag=0.35, branches=0, segs=6)

# --------------------------------------------------------------------------- seeker orbs
M_TRAIL = emit_mat('FlareTrail', GOLD, 1.8, alpha=0.55)
M_TRAIL_GLOW = emit_mat('FlareTrailGlow', DEEP_GOLD, 0.9, alpha=0.14)
HAZE = (0.95, 0.8, 0.6)
LANCER_PTS = [Vector((LX - 0.9, LY + 0.2, 0.9)), Vector((LX + 0.4, LY - 0.4, 1.1)),
              Vector((LX + 1.6, LY + 0.9, 0.3)), Vector((LX - 2.0, LY - 1.3, 0.2))]


def seeker(k, t0, target, loft=None):
    """Homing orb: leaves along the pod, slow first turn, then hard pursuit with a dying curl.
    target: t -> point. loft: a high waypoint it climbs to before diving on the target."""
    e = noses[ORDER[k]]
    sc.frame_set(int(round(P.T(t0))))
    p = e.matrix_world.translation.copy()
    v = (e.matrix_world.to_3x3().normalized() @ Vector((1, 0, 0))).normalized()
    if ORDER[k] >= 3:          # rear pods sit behind the front row: their orbs pop up over it
        p = p + Vector((0, 0, 0.35))
        v = (v + Vector((0, 0, 1.4))).normalized()
    ph = R.uniform(0, 6.28)
    curl_amp = R.uniform(1.8, 3.0)
    sub = 4
    dt = 1.0 / (FPS * sub)
    t = t0
    frames = [(t0, p.copy())]
    lofted = loft is None
    for step in range(int(3.0 * FPS * sub)):
        age = t - t0
        if not lofted:
            tgt = loft
            if (p - loft).length < 4.0 or age > 1.2:
                lofted = True
        else:
            tgt = target(t + 0.06)
        want = tgt - p
        dist = want.length
        want.normalize()
        speed = min(62.0, 16.0 + 70.0 * age)
        turn = 1.8 if age < 0.12 else 3.2 + 8.0 * ss((age - 0.12) / 0.4)
        vn = v.normalized()
        ang = vn.angle(want) if vn.dot(want) < 0.99999 else 0.0
        if ang > 1e-5:
            axis = vn.cross(want)
            if axis.length < 1e-6:
                axis = Vector((0, 0, 1))
            vn = Matrix.Rotation(min(ang, turn * dt), 3, axis.normalized()) @ vn
        side = vn.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
        upv = side.cross(vn).normalized()
        cw = curl_amp * math.exp(-age * 2.2)
        lat = (side * math.cos(ph + age * 12) + upv * math.sin(ph + age * 12)) * cw
        v = vn * speed
        p = p + (v + lat) * dt
        t += dt
        if step % sub == sub - 1:
            frames.append((t, p.copy()))
        if lofted and dist < 0.9 and age > 0.2:
            break
    return t, p.copy(), frames


def draw_orb(frames):
    f0 = int(round(P.T(frames[0][0])))
    rig = K.empty('Seeker')
    for i, (t, p) in enumerate(frames):
        rig.location = p
        rig.keyframe_insert('location', frame=f0 + i)
    K.set_interp(rig, 'LINEAR')
    f1 = f0 + len(frames) - 1
    core = W.glow(P, 'SeekerCore', GOLD, scale=(0.24,) * 3, fx_e=2.8, fx_p=0.9, fx_hot=0.6)
    halo = W.glow(P, 'SeekerHalo', DEEP_GOLD, scale=(0.75,) * 3, fx_e=1.4, fx_p=2.6)
    for o in (core, halo):
        o.parent = rig
        show_between(o, f0, f1 + 1)
    L = link(bpy.data.objects.new('OrbLight', bpy.data.lights.new('OrbLight', 'POINT')))
    L.parent = rig
    L.data.color = GOLD
    L.data.energy = 200
    L.data.shadow_soft_size = 0.4
    show_between(L, f0, f1 + 1)
    pts = [p for _, p in frames]
    if len(pts) < 3:
        return
    n = len(pts) - 1
    for name, width, m, tail in (('OrbTrail', 0.07, M_TRAIL, 5), ('OrbTrailGlow', 0.22, M_TRAIL_GLOW, 8)):
        tr = polyline(name, pts, width, m)
        tr.visible_shadow = False
        cu = tr.data
        cu.bevel_factor_mapping_start = 'SPLINE'
        cu.bevel_factor_mapping_end = 'SPLINE'
        for i in range(n + 1 + tail):
            cu.bevel_factor_end = min(1.0, i / n)
            cu.bevel_factor_start = max(0.0, min(1.0, (i - tail) / n))
            cu.keyframe_insert('bevel_factor_end', frame=f0 + i)
            cu.keyframe_insert('bevel_factor_start', frame=f0 + i)
        show_between(tr, f0, f0 + n + tail)
    # faint warm haze trail that lingers in the sky
    hz = polyline('OrbHaze', pts, 0.1, P.soft_mat())
    hz.visible_shadow = False
    cu = hz.data
    cu.bevel_resolution = 3
    cu.bevel_factor_mapping_end = 'SPLINE'
    for i in range(n + 1):
        cu.bevel_factor_end = max(0.0, (i - 1) / n)
        cu.keyframe_insert('bevel_factor_end', frame=f0 + i)
    cu.bevel_depth = 0.08
    cu.keyframe_insert('bevel_depth', frame=f0)
    cu.bevel_depth = 0.28
    cu.keyframe_insert('bevel_depth', frame=f0 + FPS)
    cu.bevel_depth = 0.42
    cu.keyframe_insert('bevel_depth', frame=NF + 2)
    for fr, a in ((f0, 0.45), (f0 + int(1.2 * FPS), 0.26), (NF + 2, 0.12)):
        hz.color = (*HAZE, a)
        hz.keyframe_insert('color', frame=fr)
    show_between(hz, f0, NF + 2)


def pod_kick(i, t):
    """The pod slams back into the arch and springs out again."""
    s = pods[i]['slide']
    ax = M2T.to_3x3() @ pods[i]['axis']
    d = ax.normalized() * (0.55 * pods[i]['len'] / T2M.to_scale().x)
    f = P.T(t)
    for fr, k in ((f - 1, 0.0), (f + 1, -0.8), (f + 4, -0.55), (f + 10, 0.0)):
        s.location = d * k
        s.keyframe_insert('location', frame=fr)


hits = []
for k, (t0, tg) in enumerate(zip(T_RIP, TGT)):
    i = ORDER[k]
    if tg == 'F':
        th, ph, frames = seeker(k, t0, lambda t, k=k: falcon_at(t) + Vector((0, 0, 0.3 * k)))
    else:
        j = k - 2
        aim = LANCER_PTS[j]
        loft = Vector((LX * 0.45 + R.uniform(-2, 2), LY * 0.4 + (j - 1.5) * 2.2, 24.0 + R.uniform(-1.5, 1.5)))
        th, ph, frames = seeker(k, t0, lambda t, a=aim: Vector((a.x, a.y, gz(a.x, a.y) + a.z)), loft=loft)
    draw_orb(frames)
    hits.append((tg, th, ph))
    pod_kick(i, t0)
    P.muzzle_flash(noses[i], t0, GOLD, 0.8)
    flare.recoil(t0, kick=2.2, back=0.06)
    P.cam_shake(t0, 0.025, dur=0.12)
print('HITS', [(tg, round(th, 2), tuple(round(c, 1) for c in ph)) for tg, th, ph in hits])

# --------------------------------------------------------------------------- the kills
f_hits = [(th, ph) for tg, th, ph in hits if tg == 'F']
l_hits = sorted([(th, ph) for tg, th, ph in hits if tg == 'L'])
P.impact(f_hits[0][1], f_hits[0][0], size=1.2, color=GOLD)
falcon.destroy(f_hits[0][0] + 0.02, size=2.6)
P.cam_shake(f_hits[0][0], 0.05, dur=0.3)
for th, ph in f_hits[1:]:
    P.impact(ph, th, size=0.9, color=GOLD)
for n_, (th, ph) in enumerate(l_hits):
    P.impact(ph, th, size=1.3, color=GOLD)
    if n_ == 1:
        lancer.destroy(th + 0.02, size=2.4)
        P.cam_shake(th, 0.1, dur=0.35)

# --------------------------------------------------------------------------- the reload
# a thread of gold from the core under the arch into each pod as its nose refills
CORE = Vector((0.18, 0.0, 1.51))
for i, tr in enumerate(T_RELOAD):
    sc.frame_set(int(round(P.T(tr))))
    core_w = tu.matrix_world @ (M2T @ CORE)
    P.lightning(core_w, nose_pt(i), tr - 0.1, tr + 0.08, width=0.02, jag=0.3, branches=0, segs=6)
    P.sfx(tr, 'power_up_arc', gain=0.3, rate=0.85 + 0.06 * i)

# --------------------------------------------------------------------------- camera
C1, C2 = 48 / FPS, 78 / FPS      # cuts at 2.0 s and 3.25 s
P.camera([
    # shot 1: low front 3/4, close, tracking it in; it settles, slews and charges
    (0.0, (4.6, -5.4, 0.7), (-6.2, -2.2, 1.2), 36),
    (0.6, (4.8, -5.2, 0.7), (-2.4, -0.7, 1.3), 32),
    (1.1, (5.0, -5.2, 0.72), (0.3, 0.0, 1.5), 30),
    (C1 - 1 / FPS, (4.7, -4.6, 0.75), (0.5, 0.1, 1.7), 31),
    # shot 2: low on its right flank, wide: the pods fire across frame, the camera tilts up
    # after the orbs to the Falcon
    (C1, (-2.5, 5.9, 0.85), (1.5, 0.2, 2.6), 21),
    (2.3, (-2.6, 6.0, 0.85), (2.6, 0.6, 3.6), 21),
    (2.6, (-2.7, 6.1, 0.9), (7.0, 2.0, 6.5), 22),
    (2.85, (-2.8, 6.2, 0.95), (11.0, 3.0, 8.5), 22),
    (C2 - 1 / FPS, (-2.9, 6.3, 1.0), (11.5, 3.2, 8.0), 22),
    # shot 3: low on its left, the Flare big in the foreground, the Lancer down-range
    (C2, (0.6, -7.5, 0.95), (1.6, 0.5, 3.0), 24),
    (4.6, (0.65, -7.2, 0.92), (1.6, 0.8, 2.2), 24),
    (6.0, (0.7, -6.8, 0.9), (1.6, 1.15, 1.9), 23),
], cuts=(C1, C2), shake=0.012)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.35, dur=6.0)          # lightning lifter skirt
P.sfx(0.7, 'servo', gain=0.4, rate=0.75)                # the arch slews onto the bearing
P.sfx(1.45, 'charge_gold', gain=0.7)                    # pods charge, the held breath
for _t in T_RIP:
    P.sfx(_t, 'zap_small', gain=0.6, rate=1.1)          # each orb leaves its pod
P.sfx(2.15, 'motes_loop', gain=0.45, dur=1.6)           # orbs streaming up and over
P.sfx(2.6, 'whoosh', gain=0.5, rate=1.2)
P.sfx(3.2, 'whoosh', gain=0.45, rate=0.8)               # the lofted four dropping in
P.sfx(4.5, 'mech_clunk', gain=0.4, rate=0.8)            # reload
P.sfx(5.3, 'servo', gain=0.35, rate=0.7)

P.render()
