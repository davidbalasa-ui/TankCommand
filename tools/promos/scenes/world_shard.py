"""The Shard (neutral end-game crystal): it does not take sides.

Two Lancers and two Lumens are trading fire in the open in front of a dormant Shard. A Lumen's
gold lightning, aimed at a Lancer, is dragged sideways into a Shard spire. The Shard wakes: the
spire flares, the world dims, violet cracks race out across the ground, a shock ring rolls over
both armies and a ring of crystal fragments lifts off the ground to orbit the floating core.

Then it answers both sides at once, with crystal instead of a beam:
  - Terrans: a violet fissure races from the left spire to the Lancers, crystal spikes erupt
    along it in a running wave and a crown of huge spikes bursts up under each Lancer,
    skewering one and flipping the other.
  - Arcadians: the orbiting fragments swing round, point at the fleeing Lumens and fire as a
    volley of crystal javelins with violet ribbons, spearing them out of the air.
Ending: low orbit round the Shard through the new crystal field, a Lancer wreck skewered on
spikes, the fragments re-forming their slow orbit.

Timeline (s): 0-1.35 skirmish | 1.35 bolt dragged into the spire | 1.45-2.2 wake |
2.2-3.0 fissure + spike eruption (Lancers die 2.75 / 2.95) | 3.0-4.0 javelin volley (Lumens die
~3.9 / 4.05) | 4.2 cut | 4.2-6.0 hero orbit."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
from promo_kit import COL, Promo  # noqa: E402

P = Promo('world_shard', seconds=6.0, seed=11)
FPS = P.fps
NF = P.nf
R = P.rnd

VIOLET = COL['shard_violet']            # (0.75, 0.35, 1.0)
DEEP_V = (0.5, 0.16, 1.0)               # deeper violet for halos / lights
GOLD = COL['arc_gold']

SHARD_AT = Vector((0.0, 4.0, 0.0))
SPIRE_L = Vector((-9.0, 0.5, 0.0))
SPIRE_R = Vector((9.5, 1.0, 0.0))
T_TRIG = 1.35       # bolt dragged into the right spire
T_WAKE = 1.5        # shard wakes
T_ERUPT = 2.2       # fissure leaves the left spire
T_VOLLEY = 3.3      # first javelin launches
CUTS = [52 / 24, 77 / 24, 103 / 24]   # hard cuts, on exact frames

P.env('dusk', sun=(68, 0, 155), sun_energy=3.0, props=34,
      clear=[(0, -2, 26)])
P.flatten(0, -2, 26)


def ss(x):
    return K.smoothstep(x)


def lerp(a, b, u):
    return a + (b - a) * u


# Lighter, thinner smoke everywhere (dark kit puffs pile into black balls).
_kit_puff = P.puff


def _thin_puff(pos, t, size=0.6, n=3, rise=1.0, life=1.2, color=None, opacity=0.65):
    if color is None:
        color, size, opacity = (0.3, 0.27, 0.3), size * 0.55, opacity * 0.5
    return _kit_puff(pos, t, size=size, n=n, rise=rise, life=life, color=color, opacity=opacity)


P.puff = _thin_puff
DUST = (0.42, 0.39, 0.37)

# ------------------------------------------------------------------------------- materials
_mats = {}


def emat(key, col, strength, alpha=None):
    if key not in _mats:
        _mats[key] = K.emit_mat('WS' + key, col, strength, alpha=alpha)
    return _mats[key]


def crystal_mat():
    """Faceted violet crystal for spikes / fragments. Glow level comes from Object Color (rgb),
    so every spike can flash on its own and settle. Edges glow a little brighter."""
    if 'crystal' in _mats:
        return _mats['crystal']
    m = bpy.data.materials.new('WSCrystal')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (0.16, 0.05, 0.42, 1)
    b.inputs['Roughness'].default_value = 0.32
    b.inputs['Specular IOR Level'].default_value = 0.3
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.65
    mr.inputs['To Max'].default_value = 1.05
    nt.links.new(lw.outputs['Facing'], mr.inputs['Value'])
    nt.links.new(oi.outputs['Color'], b.inputs['Emission Color'])
    nt.links.new(mr.outputs['Result'], b.inputs['Emission Strength'])
    _mats['crystal'] = m
    return m


def crystal_mesh(name, r, h, sides=6, tip=0.28, base_tip=0.0):
    """Hexagonal crystal: prism with a pointed tip (origin at the base, axis +Z). base_tip>0
    makes a double-ended crystal (for the flying fragments)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    lo = []
    hi = []
    z0 = h * base_tip
    z1 = h * (1 - tip)
    for i in range(sides):
        a = 2 * math.pi * i / sides + R.uniform(-0.12, 0.12)
        rr = r * R.uniform(0.85, 1.1)
        lo.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z0)))
        hi.append(bm.verts.new((rr * 0.82 * math.cos(a), rr * 0.82 * math.sin(a), z1)))
    apex = bm.verts.new((R.uniform(-0.1, 0.1) * r, R.uniform(-0.1, 0.1) * r, h))
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
        bm.faces.new((hi[i], hi[j], apex))
    if base_tip > 0:
        bot = bm.verts.new((0, 0, 0))
        for i in range(sides):
            j = (i + 1) % sides
            bm.faces.new((lo[j], lo[i], bot))
    else:
        bm.faces.new(list(reversed(lo)))
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = K.link(bpy.data.objects.new(name, me))
    me.materials.append(crystal_mat())
    return o


def glow_level(o, f, k):
    """Object colour drives the crystal's emission: k ~0.6 calm glow, ~1.4 flash."""
    o.color = (DEEP_V[0] * k, DEEP_V[1] * k, DEEP_V[2] * k, 1)
    o.keyframe_insert('color', frame=f)


# ------------------------------------------------------------------------------- the Shard
shard = P.load('shard', at=SHARD_AT[:2], heading=-90)
spireL = P.load('shard_spire', at=SPIRE_L[:2], heading=20, label='spireL')
spireR = P.load('shard_spire', at=SPIRE_R[:2], heading=-35, label='spireR')
for a in (shard, spireL, spireR):
    a.root.location.z = -0.25

# Each actor gets its own copy of its crystal material so the right spire can flare first.
shard_mats = []
for a in (shard, spireL, spireR):
    mats = []
    for o in a.meshes:
        for s in o.material_slots:
            if s.material and s.material.name not in [m.name for m in mats]:
                nm = s.material.copy()
                s.material = nm
                mats.append(nm)
    shard_mats.append(mats)


def key_emit(mats, keys):
    for m in mats:
        b = m.node_tree.nodes['Principled BSDF']
        for t, v in keys:
            b.inputs['Emission Strength'].default_value = v
            b.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))


DORMANT = 0.8
AWAKE = 2.3
key_emit(shard_mats[0], [(0, DORMANT), (T_WAKE + 0.1, DORMANT), (T_WAKE + 0.35, 3.4), (T_WAKE + 0.8, AWAKE),
                         (T_VOLLEY - 0.25, AWAKE), (T_VOLLEY, 3.4), (T_VOLLEY + 0.5, AWAKE), (6, AWAKE)])
key_emit(shard_mats[1], [(0, DORMANT), (T_WAKE + 0.25, DORMANT), (T_WAKE + 0.5, AWAKE), (T_ERUPT - 0.15, AWAKE),
                         (T_ERUPT, 4.0), (T_ERUPT + 0.6, AWAKE), (6, AWAKE)])
key_emit(shard_mats[2], [(0, DORMANT), (T_TRIG, DORMANT), (T_TRIG + 0.06, 4.2), (T_TRIG + 0.5, AWAKE), (6, AWAKE)])

# Floating core gem: lazy turn while dormant, wakes with a lurch up and a fast spin.
core = shard.parts.get('TurretPivot')
core.rotation_mode = 'XYZ'
z_core0 = core.location.z
NORM_K = next(o for o in shard.model_root.children_recursive if o.name.startswith('shard_Norm')).scale.z
for f in range(1, NF + 2, 2):
    t = (f - 1) / FPS
    w = ss((t - T_WAKE) / 0.6)
    ang = 25 * t + 160 * max(0.0, t - T_WAKE) * w
    core.rotation_euler.z = math.radians(ang)
    lift = 0.06 * math.sin(t * 2.2) + w * (0.55 + 0.12 * math.sin(t * 3.1))
    if T_VOLLEY - 0.05 < t < T_VOLLEY + 0.5:  # recoil dip as the volley leaves
        lift -= 0.25 * math.sin(math.pi * (t - T_VOLLEY + 0.05) / 0.55)
    core.location.z = z_core0 + lift / NORM_K
    core.keyframe_insert('rotation_euler', index=2, frame=f)
    core.keyframe_insert('location', index=2, frame=f)

CORE_W = Vector((SHARD_AT.x, SHARD_AT.y, 8.6))   # world position of the floating gem (approx)


def vlight(pos, keys, radius=1.5, color=VIOLET):
    L = K.link(bpy.data.objects.new('VLight', bpy.data.lights.new('VLight', 'POINT')))
    L.location = pos
    L.data.color = color
    L.data.shadow_soft_size = radius
    for t, e in keys:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=P.T(t))
    return L


vlight(CORE_W + Vector((0, -2.5, 0)), [(0, 600), (T_WAKE + 0.1, 600), (T_WAKE + 0.4, 9000), (T_WAKE + 0.9, 5000),
                                       (T_VOLLEY - 0.05, 5000), (T_VOLLEY + 0.05, 11000), (T_VOLLEY + 0.6, 5000), (6, 5000)], radius=3)
vlight(SPIRE_R + Vector((0, -1.5, 3.0)), [(0, 80), (T_TRIG, 80), (T_TRIG + 0.05, 6000), (T_TRIG + 0.5, 1800), (6, 1800)])
vlight(SPIRE_L + Vector((0, -1.5, 3.0)), [(0, 80), (T_WAKE + 0.3, 80), (T_WAKE + 0.5, 1800), (T_ERUPT - 0.1, 1800),
                                         (T_ERUPT + 0.02, 8000), (T_ERUPT + 0.6, 1800), (6, 1800)])

# The world dims as it wakes, so the violet takes over.
sun = P.sun
for t, e in [(0, 3.2), (T_WAKE, 3.2), (T_WAKE + 0.6, 1.5), (6, 1.4)]:
    sun.data.energy = e
    sun.data.keyframe_insert('energy', frame=P.T(t))
bg = bpy.context.scene.world.node_tree.nodes['Background']
for t, e in [(0, 0.9), (T_WAKE, 0.9), (T_WAKE + 0.6, 0.5), (6, 0.45)]:
    bg.inputs['Strength'].default_value = e
    bg.inputs['Strength'].keyframe_insert('default_value', frame=P.T(t))


# ------------------------------------------------------------------------------- ground cracks
def jag_ground(p0, p1, segs, jag):
    d = p1 - p0
    side = Vector((-d.y, d.x, 0)).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        q = p0 + d * u
        if 0 < i < segs:
            q = q + side * R.uniform(-1, 1) * jag
        q.z = P.ground_z(q.x, q.y) + 0.02
        pts.append(q)
    return pts


def crack(pts, t0, t1, width=0.07, fade=None):
    """Glowing violet crack racing along `pts` from t0 to t1 (curve bevel reveal)."""
    objs = [K.polyline('Crack', pts, width, emat('Crack', VIOLET, 1.25)),
            K.polyline('CrackHalo', pts, width * 4.0, emat('CrackHalo', DEEP_V, 0.9, alpha=0.22))]
    for o in objs:
        cu = o.data
        cu.bevel_factor_mapping_end = 'SPLINE'
        cu.bevel_factor_end = 0.0
        cu.keyframe_insert('bevel_factor_end', frame=P.T(t0))
        cu.bevel_factor_end = 1.0
        cu.keyframe_insert('bevel_factor_end', frame=P.T(t1))
        for fc in K._fcurves(cu.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        K.show_between(o, P.T(t0), NF + 2)
    return objs


# Wake cracks: radiating out from the Shard's base.
for i in range(9):
    a = math.radians(-90 + (i - 4) * 33 + R.uniform(-8, 8))
    d = Vector((math.cos(a), math.sin(a), 0))
    p0 = SHARD_AT + d * 4.0
    p1 = SHARD_AT + d * R.uniform(13, 22)
    tt = T_WAKE + 0.12 + R.uniform(0, 0.08)
    crack(jag_ground(p0, p1, 9, 0.7), tt, tt + 0.45, width=0.06)

# Shock ring rolling out over both armies.
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.018, major_segments=64, minor_segments=8,
                                 location=(SHARD_AT.x, SHARD_AT.y, 0.25))
ring = bpy.context.active_object
ring.data.materials.append(emat('Ring', VIOLET, 1.0, alpha=0.28))
fr = P.T(T_WAKE + 0.2)
ring.scale = (4, 4, 6)
ring.keyframe_insert('scale', frame=fr)
ring.scale = (24, 24, 10)
ring.keyframe_insert('scale', frame=fr + 10)
K.show_between(ring, fr, fr + 10)
for k in range(16):  # dust lifted by the ring
    a = 2 * math.pi * k / 16 + R.uniform(0, 0.3)
    for rr, dt in ((9, 0.12), (16, 0.3)):
        p = SHARD_AT + Vector((rr * math.cos(a), rr * math.sin(a), 0.2))
        P.puff(p, T_WAKE + 0.2 + dt, size=1.2, n=1, rise=0.7, life=1.2, color=DUST, opacity=0.28)


# ------------------------------------------------------------------------------- Arcadian bits
_bm = {}


def bmat(key, col, strength, alpha=None):
    if key not in _bm:
        _bm[key] = K.emit_mat('Gold' + key, col, strength, alpha=alpha)
    return _bm[key]


def jag_pts(p0, p1, segs, jag, ctrl=None):
    d = p1 - p0
    L = max(d.length, 1e-3)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    pts = []
    for i in range(segs + 1):
        u = i / segs
        base = p0 * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + p1 * u * u if ctrl is not None else p0 + d * u
        off = (side * R.uniform(-1, 1) + up * R.uniform(-1, 1)) * jag * L * 0.25 * math.sin(math.pi * u) if 0 < i < segs else Vector()
        pts.append(base + off)
    return pts


def gold_bolt(p0, p1, t0, t1, width=0.07, jag=0.2, branches=2, segs=10, glow=True, light=True, ctrl=None,
              col=None):
    p0, p1 = Vector(p0), Vector(p1)
    core_m = bmat('Core', (1.0, 0.85, 0.55), 4.0)
    body = bmat('Body', GOLD, 3.0) if col is None else emat('BodyV', col, 1.3)
    halo = bmat('Halo', (1.0, 0.6, 0.12), 1.5, alpha=0.3)
    d = p1 - p0
    L = d.length
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-4 else Vector((0, 1, 0))
    up = side.cross(d).normalized()
    f0 = int(round(P.T(t0)))
    f1 = max(f0 + 1, int(round(P.T(t1))))
    for fr in range(f0, f1):
        pts = jag_pts(p0, p1, segs, jag, ctrl)
        obs = [K.polyline('BoltB', pts, width, body), K.polyline('BoltC', pts, width * 0.35, core_m)]
        if glow:
            obs.append(K.polyline('BoltH', pts, width * 2.6, halo))
        for b in range(branches):
            k = R.randint(2, segs - 2)
            a = pts[k]
            dirb = (d.normalized() * 0.6 + side * R.uniform(-1, 1) + up * R.uniform(-0.5, 0.5)).normalized()
            bl = L * R.uniform(0.06, 0.16)
            obs.append(K.polyline('BoltF', [a, a + dirb * bl * 0.5 + side * R.uniform(-.1, .1) * bl, a + dirb * bl],
                                  width * 0.5, body))
        for ob in obs:
            K.show_between(ob, fr, fr + 1)
    if light:
        P.light((p0 + p1) / 2, t0, GOLD, energy=150 + 14 * L, dur=t1 - t0 + 0.05, radius=L * 0.2)


def sparks(pos, t, n=9, size=1.0, col=(1.0, 0.68, 0.2), key='Spark', strength=4.0):
    pos = Vector(pos)
    m = emat(key, col, strength)
    f0 = P.T(t)
    for i in range(n):
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(0.6, 1.6))).normalized() * size * R.uniform(2.5, 4.5)
        sp = K.sphere('Spk', 1.0, m, seg=(6, 4))
        sp.rotation_mode = 'QUATERNION'
        sp.scale = (0.1 * size, 0.022 * size, 0.022 * size)
        life = R.uniform(0.25, 0.4)
        for k in range(4):
            tt = life * k / 3
            sp.location = pos + v * tt + Vector((0, 0, -6 * tt * tt))
            vel = v + Vector((0, 0, -12 * tt))
            sp.rotation_quaternion = vel.to_track_quat('X', 'Z')
            sp.keyframe_insert('location', frame=f0 + tt * FPS)
            sp.keyframe_insert('rotation_quaternion', frame=f0 + tt * FPS)
        K.show_between(sp, f0, f0 + life * FPS)


# ------------------------------------------------------------------------------- the armies
HOVER = 1.15
L1 = P.load('lancer', at=(-19, -8), heading=5, label='lancer1')
L2 = P.load('lancer', at=(-21, -13), heading=5, label='lancer2')
for a in (L1, L2):
    a.split_barrels()
L1.path([(0.0, (-19.0, -8.2)), (1.6, (-14.6, -7.6)), (2.1, (-13.6, -7.4)), (2.35, (-13.4, -7.35))])
L2.path([(0.0, (-21.0, -13.4)), (1.6, (-16.8, -12.8)), (2.1, (-15.8, -12.6)), (2.6, (-15.5, -12.55))])
P.dust(L1, 0.0, 2.1, every=0.14, size=0.8, color=DUST)
P.dust(L2, 0.0, 2.3, every=0.14, size=0.8, color=DUST)

U1 = P.load('lumen', at=(14, -6.5), heading=180, label='lumen1')
U2 = P.copy(U1, at=(17.5, -11.5), heading=180, label='lumen2')
for a in (U1, U2):
    a.turret = a.turret or next(o for o in a.model_root.children_recursive if o.name.startswith('TurretPivot'))

T_HIT1 = T_VOLLEY + 0.5      # javelins reach Lumen 1
T_HIT2 = T_VOLLEY + 0.62     # javelins reach Lumen 2
# Lumens drift, turn to face the Shard when it wakes, then bolt for it at 3.0 and get speared.
U1_keys = [(0.0, (14.0, -6.5, HOVER), 180), (1.5, (12.6, -6.9, HOVER), 182), (2.3, (12.2, -6.9, HOVER), 150),
           (2.95, (12.4, -7.0, HOVER), 130), (3.35, (14.0, -8.6, HOVER + 0.3), -30), (T_HIT1, (16.6, -10.6, HOVER + 0.4), -38),
           (T_HIT1 + 0.12, (17.6, -11.2, HOVER - 0.1), -20), (T_HIT1 + 0.3, (18.3, -11.6, 0.35), 10)]
U2_keys = [(0.0, (17.5, -11.5, HOVER), 180), (1.5, (16.4, -11.8, HOVER), 178), (2.3, (16.1, -11.8, HOVER), 150),
           (2.95, (16.3, -11.9, HOVER), 140), (3.4, (18.0, -13.6, HOVER + 0.3), -40), (T_HIT2, (20.2, -15.6, HOVER + 0.4), -45),
           (T_HIT2 + 0.12, (21.0, -16.2, HOVER - 0.1), -60), (T_HIT2 + 0.32, (21.6, -16.7, 0.35), -80)]
U1.path(U1_keys, face=False)
U2.path(U2_keys, face=False)
for a, ph in ((U1, 0.0), (U2, 0.7)):
    a.hover_bob(0.12, 0.8)
# tumble as they fall
for a, tf, rl in ((U1, T_HIT1, 35), (U2, T_HIT2, -40)):
    m = a.model_root
    m.rotation_mode = 'XYZ'
    m.keyframe_insert('rotation_euler', frame=P.T(tf))
    m.rotation_euler = (math.radians(rl), math.radians(-18), 0)
    m.keyframe_insert('rotation_euler', frame=P.T(tf + 0.3))


def lifter_crackle(a, t0, t1, every=0.3):
    t = t0
    i = 0
    while t < t1:
        p = a.pos_at(t)
        side = 1 if i % 2 else -1
        off = Vector((R.uniform(-1.2, 1.2), side * 0.8, 0.45))
        gold_bolt(p + off, Vector((p.x + off.x * 1.6, p.y + off.y * 1.9, 0.05)), t, t + 0.04,
                  width=0.016, jag=0.5, branches=1, segs=6, glow=False, light=False)
        t += R.uniform(0.1, 0.22)
        i += 1


lifter_crackle(U1, 0.05, T_HIT1)
lifter_crackle(U2, 0.2, T_HIT2)


def lumen_bolt(src, t, at, aim_dur=0.25, ctrl=None, hit=True):
    src.aim(t, at, dur=aim_dur)
    at = Vector(at)
    mz = src.world_at(src.muzzle(), t)
    P.muzzle_flash(src.muzzle(), t, GOLD, 0.7)
    src.recoil(t, kick=1.5, back=0.08)
    gold_bolt(mz, at, t, t + 0.2, width=0.075, ctrl=ctrl)
    if hit:
        sparks(at + Vector((0, 0, 0.1)), t + 0.02)
        P.light(at + Vector((0, 0, 0.6)), t, GOLD, energy=450, dur=0.12)


def ping(actor, t, amt=4.0):
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


# The skirmish. Lancer cannon ~1.8 s reload; Lumens snap gold lightning.
L1.aim(0.3, U1, dur=0.3)
L1.fire(0.3, U1, kind='cannon')
ping(U1, 0.37)
L2.aim(0.75, U2, dur=0.4)
L2.fire(0.75, U2, kind='cannon', spread=1.2)
lumen_bolt(U1, 0.55, L1.pos_at(0.6) + Vector((0, 0, 1.0)))
ping(L1, 0.58, 2.5)
lumen_bolt(U2, 1.0, L2.pos_at(1.05) + Vector((0.8, 0.6, 0.6)))
# THE TRIGGER: Lumen 1's bolt at Lancer 1 is dragged sideways into the right spire.
SPIRE_HIT = SPIRE_R + Vector((-0.6, -0.8, 3.4))
U1.aim(T_TRIG, L1.pos_at(T_TRIG), dur=0.3)
mz = U1.world_at(U1.muzzle(), T_TRIG)
P.muzzle_flash(U1.muzzle(), T_TRIG, GOLD, 0.8)
U1.recoil(T_TRIG, kick=1.5, back=0.08)
toward = (L1.pos_at(T_TRIG) - mz)
toward.z = 0
ctrl = mz + toward.normalized() * 5.0 + Vector((0, 0, 1.2))
gold_bolt(mz, SPIRE_HIT, T_TRIG, T_TRIG + 0.3, width=0.08, jag=0.15, ctrl=ctrl, branches=3, segs=14)
sparks(SPIRE_HIT, T_TRIG + 0.02, n=12, size=1.1, col=VIOLET, key='VSpark', strength=1.4)
# violet arcs answer back over the spire for a few frames
for k in range(3):
    tt = T_TRIG + 0.08 + 0.06 * k
    a = R.uniform(0, 6.28)
    gold_bolt(SPIRE_HIT, SPIRE_HIT + Vector((1.6 * math.cos(a), 1.6 * math.sin(a), R.uniform(-1.6, 0.4))), tt, tt + 0.06,
              width=0.04, jag=0.3, branches=0, segs=6, glow=False, light=False, col=VIOLET)
L1.fire(1.95, (CORE_W.x - 2.2, CORE_W.y - 2.5, 3.5), kind='cannon')   # defiant shot at the Shard: it sparks off
sparks((CORE_W.x - 2.2, CORE_W.y - 2.5, 3.5), 1.95 + 0.3, n=8, size=0.8, col=VIOLET, key='VSpark', strength=1.4)
# Lumens turn to face the Shard
for a, t in ((U1, 2.25), (U2, 2.35)):
    a.aim(t, SHARD_AT + Vector((0, 0, 4)), dur=0.4)
lumen_bolt(U2, 2.55, (CORE_W.x + 2.0, CORE_W.y - 2.2, 4.0), hit=False)
sparks((CORE_W.x + 2.0, CORE_W.y - 2.2, 4.0), 2.57, n=8, size=0.8, col=VIOLET, key='VSpark', strength=1.4)
L2.aim(2.45, SHARD_AT + Vector((0, 0, 3)), dur=0.4)


# ------------------------------------------------------------------------------- crystal spikes
def debris(pos, t, n=5, size=1.0):
    """Rock chunks thrown out of the ground by an erupting spike."""
    pos = Vector(pos)
    f0 = P.T(t)
    for i in range(n):
        o = K.ico('Rock', 1.0, P.charred if i % 2 else K.pbr_mat('RockM', (0.12, 0.11, 0.1), 0.95), sub=0)
        s = size * R.uniform(0.08, 0.18)
        o.scale = (s, s * R.uniform(0.6, 1.3), s * R.uniform(0.5, 1))
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(1.2, 2.4))) * size * 2.2
        life = R.uniform(0.5, 0.8)
        for k in range(6):
            tt = life * k / 5
            o.location = pos + Vector((v.x * tt, v.y * tt, max(0.05, v.z * tt - 9.8 * tt * tt)))
            o.rotation_euler = (tt * 9, tt * 7, tt * 5)
            o.keyframe_insert('location', frame=f0 + tt * FPS)
            o.keyframe_insert('rotation_euler', frame=f0 + tt * FPS)
        K.show_between(o, f0, f0 + life * FPS)


def spike(pos, t, h, r, lean=Vector((0, 0, 1)), dust=True, rocks=3, light=0.0):
    """A crystal spike bursting out of the ground at `pos` at time t (overshoot then settle)."""
    pos = Vector(pos)
    pos.z = P.ground_z(pos.x, pos.y) - 0.3
    o = crystal_mesh('Spike', r, h, sides=R.choice((5, 6, 6, 7)))
    o.location = pos
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = lean.normalized().to_track_quat('Z', 'Y')
    f0 = P.T(t)
    o.scale = (0.4, 0.4, 0.01)
    o.keyframe_insert('scale', frame=f0 - 1)
    o.scale = (1.05, 1.05, 1.18)
    o.keyframe_insert('scale', frame=f0 + 2)
    o.scale = (1, 1, 1)
    o.keyframe_insert('scale', frame=f0 + 5)
    glow_level(o, f0 - 1, 1.15)
    glow_level(o, f0 + 3, 1.0)
    glow_level(o, f0 + 14, 0.6)
    glow_level(o, NF + 1, 0.5)
    K.show_between(o, f0, NF + 2)
    if dust:
        P.puff(pos + Vector((0, 0, 0.4)), t + 0.02, size=0.8 + 0.25 * h, n=2, rise=0.6, life=1.0,
               color=DUST, opacity=0.35)
    if rocks:
        debris(pos + Vector((0, 0, 0.3)), t, n=rocks, size=0.6 + 0.15 * h)
    if light:
        P.light(pos + Vector((0, 0, h * 0.6)), t, VIOLET, energy=light, dur=0.35, radius=1.0)
    return o


def eruption(p0, p1, t0, t1, h0, h1, step=0.85, side=0.6):
    """Fissure from p0 to p1 with a running wave of spikes behind its tip."""
    pts = jag_ground(p0, p1, 12, 0.45)
    crack(pts, t0, t1, width=0.09)
    d = p1 - p0
    n = max(2, int(d.length / step))
    sd = Vector((-d.y, d.x, 0)).normalized()
    for i in range(1, n):
        u = i / n
        q = p0 + d * u + sd * R.uniform(-side, side)
        lean = Vector((R.uniform(-0.35, 0.35), R.uniform(-0.35, 0.35), 1)) + d.normalized() * 0.25
        h = lerp(h0, h1, u) * R.uniform(0.75, 1.15)
        spike(q, t0 + (t1 - t0) * u + 0.03, h, 0.18 + 0.07 * h, lean=lean, rocks=2 if i % 2 else 0,
              light=900 if i % 4 == 0 else 0)


def crown(center, t, n, hmin, hmax, rad, toward=None):
    """A crown of big spikes bursting up around/under a target, leaning out."""
    center = Vector(center)
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n + R.uniform(-0.3, 0.3)
        rr = rad * R.uniform(0.2, 1.0)
        q = center + Vector((rr * math.cos(a), rr * math.sin(a), 0))
        lean = Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, 1))
        h = R.uniform(hmin, hmax)
        out.append(spike(q, t + R.uniform(0, 0.05), h, 0.3 + 0.07 * h, lean=lean, rocks=3))
    P.light(center + Vector((0, 0, 2.0)), t, VIOLET, energy=3500, dur=0.4, radius=1.5)
    P.puff(center + Vector((0, 0, 0.5)), t + 0.03, size=2.4, n=4, rise=1.4, life=1.6, color=DUST, opacity=0.3)
    sparks(center + Vector((0, 0, 1.0)), t + 0.02, n=10, size=1.3, col=VIOLET, key='VSpark', strength=1.4)
    return out


# Terran punishment: fissure from the left spire to the Lancers.
pL1 = L1.pos_at(2.6)
pL2 = L2.pos_at(2.8)
src = SPIRE_L + Vector((-1.2, -1.6, 0))
T_L1 = 2.62
T_L2 = 2.82
eruption(src, pL1 + Vector((1.2, 0.3, 0)), T_ERUPT, T_L1 - 0.02, 0.9, 2.6)
mid = src.lerp(pL1, 0.45)
eruption(mid, pL2 + Vector((1.2, 0.6, 0)), T_ERUPT + 0.2, T_L2 - 0.02, 0.8, 2.2, side=0.4)
crown(pL1, T_L1, 7, 2.6, 5.0, 2.6)
crown(pL2, T_L2, 6, 2.2, 4.2, 2.3)


# Lancer 1 is skewered and lifted; Lancer 2 is flipped onto its side.
def heave(a, t, lift, roll, pitch, yaw_add, slide=Vector()):
    r = a.root
    r.rotation_mode = 'XYZ'
    f = P.T(t)
    r.keyframe_insert('location', frame=f)
    r.keyframe_insert('rotation_euler', frame=f)
    loc = r.location.copy()
    rot = r.rotation_euler.copy()
    r.location = loc + slide + Vector((0, 0, lift * 1.15))
    r.rotation_euler = (rot.x + math.radians(roll) * 1.1, rot.y + math.radians(pitch) * 1.1, rot.z + math.radians(yaw_add))
    r.keyframe_insert('location', frame=f + 3)
    r.keyframe_insert('rotation_euler', frame=f + 3)
    r.location = loc + slide + Vector((0, 0, lift))
    r.rotation_euler = (rot.x + math.radians(roll), rot.y + math.radians(pitch), rot.z + math.radians(yaw_add))
    r.keyframe_insert('location', frame=f + 6)
    r.keyframe_insert('rotation_euler', frame=f + 6)


bpy.context.scene.frame_set(int(P.T(T_L1)))
heave(L1, T_L1, 1.9, 18, -24, 8)
bpy.context.scene.frame_set(int(P.T(T_L2)))
heave(L2, T_L2, 1.0, 62, 10, -15, slide=Vector((-0.6, -1.0, 0)))
L1.destroy(T_L1 + 0.16, size=2.1, debris=12)
L2.destroy(T_L2 + 0.18, size=2.0, debris=12)


# ------------------------------------------------------------------------------- the fragments
N_FRAG = 11
N_VOLLEY = 8
frags = []
for i in range(N_FRAG):
    o = crystal_mesh(f'Frag{i}', 0.2 if i < N_VOLLEY else 0.17, 2.1 if i < N_VOLLEY else 1.5, sides=5,
                     tip=0.3, base_tip=0.22)
    o.rotation_mode = 'QUATERNION'
    frags.append(o)

ORB_R = 6.2


def orbit_pos(i, t):
    a = math.radians(i * 360 / N_FRAG + 70 * t + 40 * max(0, t - T_WAKE))
    rr = ORB_R + 0.4 * math.sin(i * 1.7 + t * 2)
    z = 7.6 + 1.1 * math.sin(i * 2.3) + 0.25 * math.sin(t * 2.5 + i)
    return SHARD_AT + Vector((rr * math.cos(a), rr * math.sin(a) * 0.8, z))


def ground_pos(i):
    a = math.radians(i * 360 / N_FRAG + 15)
    return SHARD_AT + Vector((7.5 * math.cos(a), 7.5 * math.sin(a), 0.1))


targets = [U1] * 4 + [U2] * 4
t_hits = [T_HIT1 - 0.06 + 0.04 * k for k in range(4)] + [T_HIT2 - 0.06 + 0.04 * k for k in range(4)]
launch = [T_VOLLEY + 0.035 * i for i in range(N_VOLLEY)]
aim_pts = []
for i in range(N_VOLLEY):
    tg = targets[i]
    aim_pts.append(tg.pos_at(t_hits[i]) + Vector((R.uniform(-0.6, 0.6), R.uniform(-0.6, 0.6), 0.6)))

# per-frame keys
T_RISE0 = T_WAKE + 0.15
T_RISE1 = T_WAKE + 0.85
flight = {}
for i, o in enumerate(frags):
    gp = ground_pos(i)
    prev = None
    fl_pts = []
    for f in range(1, NF + 2):
        t = (f - 1) / FPS
        if t < T_RISE0 + 0.03 * i:
            p = gp + Vector((0, 0, -1.6))
            fwd = Vector((0, 0, 1))
            vis = False
        elif t < T_RISE1 + 0.03 * i:
            u = ss((t - T_RISE0 - 0.03 * i) / (T_RISE1 - T_RISE0))
            op = orbit_pos(i, t)
            p = gp.lerp(op, u) + Vector((0, 0, 2.0 * math.sin(math.pi * u)))
            fwd = Vector((0, 0, 1)).lerp((op - SHARD_AT).normalized(), u)
            vis = True
        elif i >= N_VOLLEY or t < launch[i] - 0.45:
            p = orbit_pos(i, t)
            tang = orbit_pos(i, t + 0.05) - p
            fwd = tang.normalized().lerp(Vector((0, 0, 1)), 0.3)
            vis = True
        elif t < launch[i]:
            # wind-up: slide back toward the gem and swing the point onto the target
            u = ss((t - (launch[i] - 0.45)) / 0.45)
            op = orbit_pos(i, launch[i] - 0.45)
            hold = op.lerp(CORE_W + (op - CORE_W).normalized() * 4.2 + Vector((0, 0, 0.6)), u)
            p = hold
            tang = (orbit_pos(i, launch[i] - 0.4) - op).normalized()
            fwd = tang.lerp((aim_pts[i] - hold).normalized(), u)
            vis = True
            flight[i] = hold
        elif t <= t_hits[i]:
            p0 = flight[i]
            p1 = aim_pts[i]
            u = (t - launch[i]) / (t_hits[i] - launch[i])
            arc = 2.2
            p = p0.lerp(p1, u) + Vector((0, 0, 4 * arc * u * (1 - u)))
            u2 = min(1.0, u + 0.03)
            fwd = (p0.lerp(p1, u2) + Vector((0, 0, 4 * arc * u2 * (1 - u2)))) - p
            if fwd.length < 1e-4:
                fwd = p1 - p0
            fl_pts.append(p.copy())
            vis = True
        else:
            # stuck in the target (it is destroyed right after)
            p = aim_pts[i]
            fwd = prev[1] if prev else Vector((0, 0, -1))
            vis = t < t_hits[i] + 0.2
        o.location = p
        o.rotation_quaternion = fwd.normalized().to_track_quat('Z', 'Y')
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_quaternion', frame=f)
        prev = (p, fwd.normalized())
    # glow: calm in orbit, bright in flight
    glow_level(o, 1, 0.7)
    if i < N_VOLLEY:
        glow_level(o, P.T(launch[i] - 0.3), 0.8)
        glow_level(o, P.T(launch[i]), 1.35)
    K.set_interp(o, 'LINEAR')

for i, o in enumerate(frags):
    t_on = T_RISE0 + 0.03 * i
    t_off = t_hits[i] + 0.2 if i < N_VOLLEY else 99
    K.key_hide(o, 1, True)
    K.key_hide(o, P.T(t_on), False)
    if t_off < 7:
        K.key_hide(o, P.T(t_off), True)

# Ribbon trails behind each javelin in flight (curve reveal with a trailing start).
for i in range(N_VOLLEY):
    p0, p1 = flight[i], aim_pts[i]
    pts = []
    for k in range(17):
        u = k / 16
        pts.append(p0.lerp(p1, u) + Vector((0, 0, 4 * 2.2 * u * (1 - u))))
    for w, mat in ((0.09, emat('Trail', VIOLET, 1.1)), (0.3, emat('TrailHalo', DEEP_V, 0.9, alpha=0.22))):
        o = K.polyline('Trail', pts, w, mat)
        cu = o.data
        cu.bevel_factor_mapping_start = 'SPLINE'
        cu.bevel_factor_mapping_end = 'SPLINE'
        fa, fb = P.T(launch[i]), P.T(t_hits[i])
        for f in range(int(fa), int(fb) + 8):
            u = min(1.0, (f - fa) / (fb - fa))
            cu.bevel_factor_end = u
            cu.bevel_factor_start = max(0.0, min(u, (f - fa) / (fb - fa) - 0.45))
            cu.keyframe_insert('bevel_factor_end', frame=f)
            cu.keyframe_insert('bevel_factor_start', frame=f)
        K.show_between(o, fa, fb + 7)
    # launch flash at the gem side
    P.light(flight[i], launch[i], VIOLET, energy=2500, dur=0.15, radius=0.6)


def shatter(pos, t, size=1.0):
    """Javelin strike: violet flash, a spray of crystal splinters, violet sparks."""
    pos = Vector(pos)
    f0 = P.T(t)
    fl = K.sphere('VFlash', 1.0, P.soft_fire_mat(), seg=(14, 10))
    fl.color = (*DEEP_V, 0.45)
    fl.location = pos
    fl.scale = (0.1,) * 3
    fl.keyframe_insert('scale', frame=f0)
    fl.scale = (1.3 * size,) * 3
    fl.keyframe_insert('scale', frame=f0 + 2)
    fl.scale = (0.05,) * 3
    fl.keyframe_insert('scale', frame=f0 + 6)
    K.show_between(fl, f0, f0 + 6)
    for k in range(7):
        s = crystal_mesh('Splinter', 0.06 * size, R.uniform(0.3, 0.6) * size, sides=4, base_tip=0.3)
        s.rotation_mode = 'XYZ'
        v = Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(0.3, 1.5))).normalized() * R.uniform(4, 7) * size
        life = R.uniform(0.4, 0.7)
        glow_level(s, 1, 1.1)
        for j in range(6):
            tt = life * j / 5
            s.location = pos + v * tt + Vector((0, 0, -7 * tt * tt))
            s.rotation_euler = (tt * 14, tt * 9, tt * 11)
            s.keyframe_insert('location', frame=f0 + tt * FPS)
            s.keyframe_insert('rotation_euler', frame=f0 + tt * FPS)
        K.show_between(s, f0, f0 + life * FPS)
    sparks(pos, t, n=8, size=1.0 * size, col=VIOLET, key='VSpark', strength=1.4)
    P.light(pos + Vector((0, 0, 0.6)), t, VIOLET, energy=5000 * size, dur=0.25, radius=0.8)


for i in range(N_VOLLEY):
    shatter(aim_pts[i], t_hits[i], size=0.8)
U1.destroy(T_HIT1 + 0.3, size=2.4, debris=10)
U2.destroy(T_HIT2 + 0.32, size=2.4, debris=10)

# ------------------------------------------------------------------------------- camera
C1, C2, C3 = CUTS
PRE = 1 / FPS
P.camera([
    # 1: low, off the Lumens' flank: both armies and the dormant Shard; the trigger bolt;
    #    tilt up and push in on the waking Shard
    (0.0, (22.0, -30.0, 1.9), (10.5, -11.0, 2.5), 26),
    (1.2, (21.2, -29.0, 1.9), (9.5, -9.5, 2.8), 26),
    (1.6, (20.5, -28.0, 1.8), (3.0, 0.0, 4.5), 30),
    (C1 - PRE, (17.0, -23.0, 1.5), (0.0, 4.0, 6.2), 34),
    # 2: behind the Lancers: the fissure races at camera, crowns burst under them
    (C1, (-24.0, -22.0, 2.4), (-9.5, -4.0, 2.4), 28),
    (C2 - PRE, (-25.2, -24.0, 3.4), (-11.0, -6.0, 2.4), 28),
    # 3: reverse angle from behind the Shard's flank: the javelin volley arcs across frame
    #    from the gem onto the fleeing Lumens
    (C2, (30.0, 16.0, 3.5), (11.5, -0.8, 5.0), 26),
    (3.75, (30.4, 15.4, 3.4), (12.5, -2.5, 4.0), 26),
    (C3 - PRE, (30.8, 15.0, 3.2), (14.5, -5.0, 2.6), 26),
    # 4: aftermath: the skewered Lancer in the foreground, the Shard beyond
    (C3, (-14.0, -32.0, 1.0), (-9.0, -7.5, 3.2), 31),
    (6.0, (-9.0, -33.0, 1.8), (-9.8, -8.0, 3.8), 31),
], shake=0.025, cuts=CUTS)
for ob in (P.cam, P.cam_target, P.cam.data):
    ad = ob.animation_data
    for fc in K._fcurves(ad.action):
        for kp in fc.keyframe_points:
            for c in CUTS:
                if abs(kp.co.x - P.T(c - PRE)) < 0.01:
                    kp.interpolation = 'CONSTANT'
                    kp.handle_left_type = 'VECTOR'
                    kp.handle_right_type = 'VECTOR'
                if abs(kp.co.x - P.T(c)) < 0.01:
                    kp.handle_left_type = 'VECTOR'
                    kp.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
P.cam_shake(T_WAKE + 0.25, 0.12, 0.5)
P.cam_shake(T_L1, 0.18, 0.4)
P.cam_shake(T_L2, 0.12, 0.35)
P.cam_shake(T_HIT1, 0.1, 0.3)

# Explosion cores and wreck flames: deepen so they don't flash white.
for m in bpy.data.materials:
    if m.name.startswith('Core') and 'emit_node' in m.keys():
        em = m.node_tree.nodes[m['emit_node']]
        em.inputs['Color'].default_value = (1.0, 0.35, 0.05, 1)
        em.inputs['Strength'].default_value = 1.2
for m in bpy.data.materials:   # cannon slugs: tracer orange, not white
    if m.name.startswith('Slug') and 'emit_node' in m.keys():
        m.node_tree.nodes[m['emit_node']].inputs['Strength'].default_value = 2.2
fb = P.fireball_mat()
cr = next(n for n in fb.node_tree.nodes if n.type == 'VALTORGB')
cr.color_ramp.elements[0].color = (0.6, 0.06, 0.01, 1)
cr.color_ramp.elements[1].color = (1.0, 0.38, 0.06, 1)
fb.node_tree.nodes[fb['emit_node']].inputs['Strength'].default_value = 1.8

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(T_WAKE, 'shard_wake', gain=0.9)                 # the Shard wakes, world dims
P.sfx(T_WAKE + 0.3, 'shockwave', gain=0.8, rate=0.8)  # shock ring rolls over both armies
P.sfx(T_RISE0, 'whirr_loop', gain=0.2, dur=6.0 - T_RISE0, rate=0.55)  # fragments orbiting the core
for _k in range(6):                                   # fissure: running wave of spikes toward the Lancers
    _u = _k / 6
    P.sfx(T_ERUPT + (T_L1 - T_ERUPT) * _u, 'crystal_spike', gain=0.25 + 0.06 * _k, pos=src.lerp(pL1, _u), rate=1.25)
P.sfx(T_L1, 'crystal_spike', gain=1.0, pos=pL1, rate=0.8)  # crowns burst up under each Lancer
P.sfx(T_L2, 'crystal_spike', gain=0.9, pos=pL2, rate=0.85)
for _k in range(4):                                   # javelin volley leaves the core
    P.sfx(T_VOLLEY - 0.55 + 0.05 * _k, 'whoosh', gain=0.4, rate=1.3 + 0.1 * _k)
P.sfx(T_HIT1, 'crystal_spike', gain=0.6, rate=1.3)    # javelins spear the Lumens
P.sfx(T_HIT2, 'crystal_spike', gain=0.6, rate=1.4)

P.render()
