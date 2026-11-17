"""Terran Corvette (space): an Arcadian corvette knifes through the Terran battle line on gold
lightning thrusters, lashing a Broadside battleship's flank as it passes. Two Terran corvettes
are on its tail. The hero slaloms after it: down the Broadside's flank, hard across the gap,
and down the far side of the Dreadnought, its spinal coilgun hammering in three-shot bursts
(the rail slams back ~80% into the hull on every shot; the wingman fires single heavy shots on
its own beat). The third burst tears the Arcadian apart; the hero punches through the drifting
wreck and the camera settles on it against the planet.

Scale: built at 0.3x the models.json ship sizes (corvette 13.5 m, Broadside 78 m, Dreadnought
120 m; the Arcadian corvette is nudged up to 19.5 m so the target reads) so the kit's
game-scale effects read correctly.

Timeline (s): 0-1.625 low off the hero's left wing, the Broadside's flank behind, the Arcadian
ahead lashing it 0.45-1.05 | 1.625-3.92 high chase off the hero's right quarter through the
hard bank across the gap: bursts 1.95 (wide), 2.6 and 3.2 (hits), wingman 2.3 / 2.95, the
Arcadian fractures 3.55 | 3.92-6.0 from the inside of the slalom looking out: the hero punches
through the drifting wreck, push in on it big against the planet.

Ships are film placeholders: loaded by name, nose along +X (models.json kind 'ship'). Terran
glow is already neon blue + amber; red accents are tinted orange and the glass portholes are
blanked (no windows) in this scene only."""
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

P = Promo('fleet_terran_corvette', seconds=6.0, seed=23)
FPS = P.fps
NF = P.nf
R = P.rnd
GOLD = COL['arc_gold']
NEON = COL['terran_neon']
ORANGE = COL['terran_orange']

SCALE = 0.3
CV_SIZE = 45 * SCALE
AC_SIZE = 50 * SCALE * 1.3     # nudged up so the target reads at phone size
BS_SIZE = 260 * SCALE
DN_SIZE = 400 * SCALE

P.space(planet=(120, -720, -260, 520, (0.07, 0.12, 0.22)), nebula=(0.07, 0.03, 0.11),
        sun=(60, 0, 125), sun_energy=4.2)


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


def level(t, p, v, a):
    return Vector((0, 0, 1))


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


# ------------------------------------------------------------------------------- timing
CUT1, CUT2 = 39 / 24, 94 / 24            # 1.625 s, 3.92 s
T_LASH0, T_LASH1 = 0.45, 1.05
BURSTS = [(1.95, False), (2.6, True), (3.2, True)]   # (start, hits)
SHOT_GAP = 0.15
T_KILL = 3.55

# ------------------------------------------------------------------------------- capital ships
FV = Vector((4.0, 0, 0))


def BSc(t):
    return Vector((5, 0, 40)) + FV * t


def DNc(t):
    return Vector((160, -2, 42)) + FV * t


bs = P.load('terran_broadside', size=BS_SIZE, label='broadside')
dn = P.load('terran_dreadnought', size=DN_SIZE, label='dreadnought')
fly(bs, BSc, level)
fly(dn, DNc, level)

# ------------------------------------------------------------------------------- the slalom
# Hero: down the Broadside's LEFT flank, hard across the gap, down the Dreadnought's RIGHT
# flank, then out past its bow.
h_pos = spline([
    (-0.5, (-66, 15, 44)),
    (0.0, (-40, 19, 42)),
    (0.8, (0, 27, 39)),
    (1.6, (40, 26, 38)),
    (2.2, (70, 12, 40)),
    (2.7, (96, -12, 42)),
    (3.3, (126, -25, 41)),
    (4.0, (160, -28, 40)),
    (4.8, (202, -31, 42)),
    (5.5, (236, -33, 45)),
    (6.0, (262, -34, 47)),
    (6.6, (292, -35, 49)),
])


def w_pos(t):
    """Wingman: on the hero's line, ~0.55 s behind and a few metres above."""
    return h_pos(t - 0.55) + Vector((0, 0, 7.0))


def lead(t):
    return lerp(0.78, 0.42, ss((t - 0.2) / 3.4))


def a_pos(t):
    """Arcadian: running the same line ahead of the hero, jinking."""
    j = ss((t - 1.3) / 0.6)
    return h_pos(t + lead(t)) + Vector((0, 2.8 * math.sin(4.2 * t) * j, 2.2 * math.sin(3.1 * t + 1.0) * j))


hero = P.load('terran_corvette', size=CV_SIZE, label='hero')
wing = P.load('terran_corvette', size=CV_SIZE, label='wing')
arc = P.load('arcadian_corvette', size=AC_SIZE, label='arcadian')
fly(hero, h_pos, bank_up(0.7, 55))
fly(wing, w_pos, bank_up(0.7, 55))


def a_roll(t):
    return math.radians(25) * math.sin(4.2 * t - 0.6) * ss((t - 1.3) / 0.6)


fly(arc, a_pos, bank_up(1.0, 70), roll_extra=a_roll)
print('hero', h_pos(0), h_pos(6), ' arc@kill', a_pos(T_KILL))


# ------------------------------------------------------------------------------- Terran look
def terran_glow(actor):
    """Scene-only: red accents -> Terran orange, glass portholes -> dark hull (no windows)."""
    seen = set()
    for o in actor.meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m in seen or not m.node_tree:
                continue
            seen.add(m)
            base = m.name.split('.')[0]
            for n in m.node_tree.nodes:
                if base == 'zone_glass' and n.type == 'BSDF_PRINCIPLED':
                    n.inputs['Base Color'].default_value = (0.03, 0.035, 0.04, 1)
                    n.inputs['Roughness'].default_value = 0.5
                    n.inputs['Metallic'].default_value = 0.6
                    for nm in ('Transmission Weight', 'Emission Strength'):
                        if nm in n.inputs:
                            n.inputs[nm].default_value = 0.0
                    if 'Alpha' in n.inputs:
                        n.inputs['Alpha'].default_value = 1.0
                    continue
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
                    sock.default_value = (*NEON, 1)
                elif r > 0.6 and g < 0.12 and b < 0.12:                   # red accent
                    sock.default_value = (*ORANGE, 1)


for a_ in (hero, wing, bs, dn):
    terran_glow(a_)

# corvette model -> root space: (orig - C) * K
CV_C = Vector((0.286, 0.0, 0.34))
CV_K = CV_SIZE / 10.5715


def cv(x, y, z):
    return (Vector((x, y, z)) - CV_C) * CV_K


CV_MUZZLE = cv(5.35, 0, 0.03)
CV_ENGINES = [(cv(-5.0, 2.25, 0.0), 0.5), (cv(-5.0, -2.25, 0.0), 0.5), (cv(-4.25, 0, 0.05), 0.6)]
RAIL_BACK = 2.6          # model units: ~80% of the rail's exposed length


def split_rail(actor):
    """Cut the spinal coilgun (rod + coil + muzzle cap) out of the hull into its own object."""
    host = actor.meshes[0]
    me = host.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen = set()
    rail_faces = set()
    for v in bm.verts:
        if v in seen:
            continue
        st = [v]
        seen.add(v)
        comp = []
        while st:
            x = st.pop()
            comp.append(x)
            for e in x.link_edges:
                w = e.other_vert(x)
                if w not in seen:
                    seen.add(w)
                    st.append(w)
        xs = [c.co.x for c in comp]
        if all(abs(c.co.y) < 0.18 for c in comp) and min(xs) > 0.9 and max(xs) > 4.3:
            for c in comp:
                rail_faces.update(c.link_faces)
    b2 = bm.copy()
    keep = {f.index for f in rail_faces}
    bmesh.ops.delete(bm, geom=list(rail_faces), context='FACES')
    bm.to_mesh(me)
    bm.free()
    b2.faces.ensure_lookup_table()
    bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
    nme = bpy.data.meshes.new(actor.name + '_Rail')
    b2.to_mesh(nme)
    b2.free()
    for m in me.materials:
        nme.materials.append(m)
    rail = K.link(bpy.data.objects.new(actor.name + '_Rail', nme))
    rail.parent = host
    rail.matrix_parent_inverse = Matrix()
    rail.matrix_basis = Matrix()
    actor.rail = rail
    mz = K.empty(actor.name + '_Muzzle')
    mz.parent = actor.root
    mz.matrix_parent_inverse = Matrix()
    mz.location = CV_MUZZLE
    actor.mz = mz
    return rail


split_rail(hero)
split_rail(wing)


def rail_recoil(actor, t):
    r = actor.rail
    f = P.T(t)
    r.location.x = 0
    r.keyframe_insert('location', index=0, frame=f - 1)
    r.location.x = -RAIL_BACK
    r.keyframe_insert('location', index=0, frame=f + 0.7)
    r.location.x = 0
    r.keyframe_insert('location', index=0, frame=f + 3.2)


def hull_kick(actor, t, kick=2.2, back=0.6):
    m = actor.model_root
    f = P.T(t)
    m.rotation_mode = 'XYZ'
    m.location.x = 0
    m.rotation_euler.y = 0
    m.keyframe_insert('location', index=0, frame=f - 0.5)
    m.keyframe_insert('rotation_euler', index=1, frame=f - 0.5)
    m.location.x = -back
    m.rotation_euler.y = math.radians(-kick)
    m.keyframe_insert('location', index=0, frame=f + 1)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 1)
    m.location.x = 0
    m.rotation_euler.y = 0
    m.keyframe_insert('location', index=0, frame=f + 3.4)
    m.keyframe_insert('rotation_euler', index=1, frame=f + 3.4)


def coil_shot(actor, target, t, hit, miss=4.0, speed=300):
    p0 = W(actor, t, CV_MUZZLE)
    aim = W(target, t + 0.1)
    if hit:
        aim = W(target, t + 0.1, (R.uniform(-4.5, 3.5), R.uniform(-1.4, 1.4), R.uniform(-0.6, 0.8)))
    else:
        side = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-1, 1))).normalized()
        aim = p0 + (aim + side * miss - p0) * 1.8
    th = P.projectile(p0, aim, t, speed=speed, color=NEON, size=0.3)
    P.muzzle_flash(actor.mz, t, NEON, 0.9)
    rail_recoil(actor, t)
    hull_kick(actor, t)
    if hit:
        P.impact(aim, th, size=1.1, color=NEON)
    return th


for t0, hit in BURSTS:
    for i in range(3):
        coil_shot(hero, arc, t0 + i * SHOT_GAP, hit)
# the wingman fires on its own slower beat (single heavy shots)
coil_shot(wing, arc, 2.3, False)
coil_shot(wing, arc, 2.95, True)


# ------------------------------------------------------------------------------- engine glow
def exhausts(actor, flick_seed):
    """Neon-blue engine cones (low strength, saturated) parented to the ship."""
    mat = K.emit_mat('CvExhaust', NEON, 1.4, alpha=0.55)
    core = K.emit_mat('CvExhaustCore', (0.2, 0.6, 1.0), 2.0)
    for p, r in CV_ENGINES:
        for m_, rr, ll in ((mat, r * CV_K * 0.8, 2.2), (core, r * CV_K * 0.4, 1.2)):
            me = bpy.data.meshes.new('Exhaust')
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=rr, radius2=0.02, depth=1.0)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, 'Y'))
            bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-0.5, 0, 0)))
            bm.to_mesh(me)
            bm.free()
            me.materials.append(m_)
            o = K.link(bpy.data.objects.new('Exhaust', me))
            o.visible_shadow = False
            o.parent = actor.root
            o.matrix_parent_inverse = Matrix()
            o.location = p
            for f in range(0, NF + 2, 2):
                o.scale = (ll * R.uniform(0.8, 1.15), 1, 1)
                o.keyframe_insert('scale', index=0, frame=f)



# ------------------------------------------------------------------------------- Arcadian fx
AC_C = Vector((-0.575, 0, -0.005))
AC_K = AC_SIZE / 17.65


def ac(x, y, z):
    return (Vector((x, y, z)) - AC_C) * AC_K


AC_NOSE = ac(8.1, 0, 0.05)
AC_REAR = [ac(-9.2, 1.3, 0.0), ac(-9.2, -1.3, 0.0), ac(-9.0, 0, 1.0)]


def attach_new(before, parent):
    for o in bpy.data.objects:
        if o not in before and o.parent is None:
            o.parent = parent
            o.matrix_parent_inverse = Matrix()


def thrust(actor, t0, t1, length, width):
    """Gold lightning thrusters (kit lightning_thruster: crackling bolts that ride the ship)."""
    for p in AC_REAR:
        WFX.lightning_thruster(P, actor, t0, t1, local=p, axis=(-1, 0.1 * p.y, 0.08 * p.z), length=length,
                               width=width, n=2, spread=0.3, color=GOLD, light=False)


thrust(arc, 0.0, 1.4, 4.5, 0.05)
thrust(arc, 1.4, T_KILL + 0.05, 6.0, 0.06)

# Lash the Broadside's flank as it streaks past.
def lash_hit(t):
    return BSc(t) + Vector((lerp(-2, 22, (t - T_LASH0) / (T_LASH1 - T_LASH0)), 14.0, 1.5))


# one bolt with moving ends: from the Arcadian's nose, raking along the flank
P.lightning(lambda t: W(arc, t, AC_NOSE), lash_hit, T_LASH0, T_LASH1, color=GOLD, width=0.11, jag=0.16,
            branches=2, segs=12)
for i in range(4):
    t = T_LASH0 + 0.02 + i * 0.16
    P.impact(lash_hit(t), t, size=1.4, color=GOLD)


def kill(actor, t, size=5.0):
    """Space kill: the Arcadian fractures into its own pieces, which drift on without
    gravity (promo_fx.destroy handles space), with a fireball and sparks."""
    actor.destroy(t, size=size, wreck=False, debris=12)


kill(arc, T_KILL)


# ------------------------------------------------------------------------------- space dust
def dust_field(n=2600, box=((-90, 320), (-70, 70), (5, 85)), size=0.1):
    me = bpy.data.meshes.new('SpaceDust')
    bm = bmesh.new()
    for _ in range(n):
        c = Vector((R.uniform(*box[0]), R.uniform(*box[1]), R.uniform(*box[2])))
        s = size * R.uniform(0.6, 1.4)
        r = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=s)
        bmesh.ops.translate(bm, verts=r['verts'], vec=c)
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new('SpaceDust', me))
    me.materials.append(K.emit_mat('DustGlint', (0.55, 0.6, 0.75), 1.2))
    o.visible_shadow = False
    return o


dust_field()


# ------------------------------------------------------------------------------- camera
def cam_keys():
    keys = []

    def shot(t0, t1, n, fn, last=True):
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            if i == n and last:
                t = t1 - 1 / FPS
            keys.append((t,) + fn(t, (t - t0) / (t1 - t0)))

    # Shot 1: low off the hero's left wing, Broadside flank behind, Arcadian ahead.
    def s1f(t, u):
        h = h_pos(t)
        pos = h + Vector((lerp(-21, -17, ss(u)), lerp(13, 11, ss(u)), lerp(-4, -3, ss(u))))
        look = h.lerp(a_pos(t), lerp(0.15, 0.22, ss(u)))
        return pos, look, 28
    shot(0, CUT1, 12, s1f)

    # Shot 2: high chase off the hero's right quarter: hero in the foreground, the Arcadian
    # ahead taking the bursts, the Dreadnought's flank beyond.
    def s2f(t, u):
        h = h_pos(t)
        pos = h + Vector((lerp(-19, -13, ss(u)), lerp(-7, -13, ss(u)), lerp(6.5, 6.0, ss(u))))
        look = h.lerp(a_pos(min(t, T_KILL)), lerp(0.2, 0.36, ss(u)))
        return pos, look, 26
    shot(CUT1, CUT2, 10, s2f)

    # Shot 3: from the inside of the slalom, ahead and above, looking down and out past the
    # hero: the planet fills the background, the Arcadian's wreck drifts through, push in.
    def s3f(t, u):
        h = h_pos(t)
        pos = h + Vector((lerp(5, 9, ss(u)), lerp(14, 8, ss(u)), lerp(10, 3.5, ss(u))))
        look = h + Vector((lerp(-3, 0.5, ss(u)), lerp(-2, -1, ss(u)), lerp(-2, -0.5, ss(u))))
        return pos, look, 30
    shot(CUT2, 6.0, 12, s3f, last=False)
    return keys


P.camera(cam_keys(), lens=28, cuts=(CUT1, CUT2))
P.cam_shake(T_KILL, 0.25)

# ------------------------------------------------------------------------------- sound cues
# (the lash is one bolt with moving ends, which the audio recorder can't place)
P.sfx(T_LASH0, 'zap_lightning', gain=1.0, pos=lash_hit(T_LASH0))
P.sfx(T_LASH0, 'crackle_loop', gain=0.6, pos=lash_hit(0.75), dur=T_LASH1 - T_LASH0)
P.sfx(T_LASH0 + 0.05, 'shield_hit', gain=0.4, pos=lash_hit(T_LASH0))
P.sfx(1.6, 'whoosh', gain=0.8, pos=h_pos(1.8))
P.sfx(CUT2 + 0.2, 'whoosh', gain=1.0, pos=h_pos(CUT2 + 0.4))
P.sfx(5.0, 'thruster_blue', gain=0.6, pos=h_pos(5.0), dur=1.0)

P.render()
