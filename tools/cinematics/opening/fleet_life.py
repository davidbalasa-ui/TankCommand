"""Fleet life (David 2026-11-15): every ship type fires on its OWN rhythm set by its weapon, and has its own
animation outside of firing.

Terran turrets are split out of the hull meshes (capture_turrets) into live parts: a base that yaws and a gun
that pitches and recoils. They slew at their own speed toward targets, scan when idle and kick back when they fire.

Weapon rhythms (seconds), per mount:
  rapid      twin-X fighter blasters  ~8 small shots/s
  flak       corvette / point defence bursts of 4 at 0.09 s, then 0.6-0.9 s pause
  cannon     frigate twin cannons     ~0.5 s per gun, guns alternate
  heavy      battleship main guns     one devastating blast every ~1.1 s
  artillery  missile ship tubes       3 missiles within 1 s, then 3 s reload (tube doors open/close)
  needle     Arcadian stingray        gold needles ~6/s
  arc        Arcadian corvette        3 lightning pulses 0.2 s apart, 1.5 s recharge
  lance      Arcadian motherships     0.8 s beam, ~2.2 s charge between (charge rings spin up)
"""
import math
import random
from contextlib import contextmanager

import bpy
from mathutils import Vector, Euler

import space as SP

BLUE = (0.35, 0.7, 1.0)
GOLD = (1.0, 0.6, 0.18)


# ------------------------------------------------------------------ rhythms
def shot_times(profile, t0, t1, rnd, phase=None):
    """Firing times for one mount between t0 and t1 (seconds), on that weapon's rhythm, own phase."""
    out = []
    t = t0 + (phase if phase is not None else rnd.uniform(0, 0.8))
    while t < t1:
        if profile == 'rapid':
            out.append(t)
            t += rnd.uniform(0.1, 0.15)
        elif profile == 'needle':
            out.append(t)
            t += rnd.uniform(0.14, 0.2)
        elif profile == 'flak':
            for i in range(4):
                out.append(t + i * 0.09)
            t += 0.27 + rnd.uniform(0.6, 0.9)
        elif profile == 'cannon':
            out.append(t)
            t += rnd.uniform(0.46, 0.56)
        elif profile == 'heavy':
            out.append(t)
            t += rnd.uniform(1.0, 1.2)
        elif profile == 'artillery':
            for i in range(3):
                out.append(t + i * 0.33)
            t += 0.66 + 3.0
        elif profile == 'arc':
            for i in range(3):
                out.append(t + i * 0.2)
            t += 0.4 + rnd.uniform(1.4, 1.7)
        elif profile == 'lance':
            out.append(t)
            t += 0.8 + rnd.uniform(2.0, 2.5)
        else:
            raise KeyError(profile)
    return [x for x in out if x < t1]


SHOT_LOOK = {   # bolt size (length, radius), strength, impact size
    'rapid': ((1.6, 0.07), 20.0, 0.0),
    'needle': ((1.4, 0.06), 18.0, 0.0),
    'flak': ((2.2, 0.12), 22.0, 1.5),
    'cannon': ((4.0, 0.22), 26.0, 3.0),
    'heavy': ((8.0, 0.55), 34.0, 7.0),
}


# ------------------------------------------------------------------ turrets out of the hull
@contextmanager
def capture_turrets():
    """While active, terran_fleet._turret records its turrets instead of building them into the hull."""
    import terran_fleet as T
    orig = T._turret
    specs = []

    def rec(x, y, z, r, barrels=2, up=1):
        specs.append((x, y, z, r, barrels, up))
    T._turret = rec
    try:
        yield specs
    finally:
        T._turret = orig


def _build_turret_parts(r, barrels, up, name):
    import forge as F
    import ships as base
    base._faction('terran')
    m = F.mark()
    F.orb((0, 0, 0), r, 'plate', seg=(12, 6), sq=(1, 1, 0.45))
    bo = base._join(F.since(m), name + 'Base')
    m = F.mark()
    px, pz = 0.18 * r, up * 0.62 * r                     # gun pivot (relative to the base)
    F.box((0.0, 0, 0.0), (1.1 * r, 0.8 * r, 0.4 * r), 'armor', taper=0.7 if up > 0 else 1.0, bevel=0.03 * r)
    offs = [0] if barrels == 1 else [(-0.3 + 0.6 * i / (barrels - 1)) * r for i in range(barrels)]
    for dy in offs:
        F.cyl((0.7 * r - px, dy, up * 0.08 * r), (3.6 * r - px, dy, up * 0.13 * r), 0.12 * r, 6, 'barrel')
        F.cyl((3.3 * r - px, dy, up * 0.13 * r), (3.7 * r - px, dy, up * 0.14 * r), 0.16 * r, 6, 'dark')
    F.box((0.95 * r - px, 0, up * 0.33 * r), (0.15 * r, 0.3 * r, 0.03 * r), 'glow')
    gun = base._join(F.since(m), name + 'Gun')
    for o in (bo, gun):                                  # origin at (0,0,0): the yaw / pitch pivots
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        o.location = (0, 0, 0)
    gun.parent = bo
    gun.location = (px, 0, pz)
    bo.rotation_mode = gun.rotation_mode = 'XYZ'
    gun['gun'] = 1
    gun['muzzle'] = (3.7 * r - px, 0.0, up * 0.14 * r)
    gun['offs'] = offs
    return bo, gun


def add_turrets(ship, specs):
    """Turn recorded specs into live turret parts parented to ship."""
    from v3base import link  # noqa: F401
    out = []
    cache = {}
    for i, (x, y, z, r, barrels, up) in enumerate(specs):
        key = (round(r, 3), barrels, up)
        if key not in cache:
            cache[key] = _build_turret_parts(r, barrels, up, f'{ship.name}T{i}')
            bo, gun = cache[key]
        else:
            b0, g0 = cache[key]
            bo = b0.copy()
            bo.data = b0.data
            gun = g0.copy()
            bpy.context.scene.collection.objects.link(bo)
            bpy.context.scene.collection.objects.link(gun)
            gun.parent = bo
            gun.location = g0.location.copy()
            bo.name, gun.name = f'{ship.name}T{i}Base', f'{ship.name}T{i}Gun'
        bo.parent = ship
        bo.location = (x, y, z)
        bo['turret'] = 1
        bo['r'] = r
        bo['up'] = up
        out.append(bo)
    return out


def turrets_of(ship):
    return [c for c in ship.children if c.get('turret')]


def gun_of(base_ob):
    return next(c for c in base_ob.children if c.get('gun'))


def muzzle_world(base_ob, k=0):
    g = gun_of(base_ob)
    m = Vector(g['muzzle'])
    offs = list(g['offs'])
    m.y += offs[k % len(offs)]
    return g.matrix_world @ m


# ------------------------------------------------------------------ aiming + idle, baked per frame
def bake_turrets(ships, f0, f1, aim=None, seed=1, step=2):
    """ships: {key: ship}. aim(key, turret_index, frame) -> world point or None (idle scan).
    Each turret slews at its own rate (small fast, big slow), scans on its own sweep when idle."""
    rnd = random.Random(seed)
    sc = bpy.context.scene
    st = {}
    for k, s in ships.items():
        for i, t in enumerate(turrets_of(s)):
            r = t['r']
            st[(k, i)] = dict(t=t, g=gun_of(t), yaw=rnd.uniform(-0.4, 0.4), pit=0.0,
                              rate=math.radians(150 if r < 0.25 else (80 if r < 0.5 else 40)),
                              sw=rnd.uniform(0.25, 0.7), ph=rnd.uniform(0, 6.28), amp=rnd.uniform(0.5, 1.4))
    for f in range(f0, f1 + 1, step):
        sc.frame_set(f)
        for (k, i), S in st.items():
            t = S['t']
            tgt = aim(k, i, f) if aim else None
            if tgt is not None:
                d = (t.parent.matrix_world.inverted() @ Vector(tgt)) - t.location
                yaw_w = math.atan2(d.y, d.x)
                pit_w = math.atan2(d.z, max(1e-4, math.hypot(d.x, d.y)))
            else:
                tt = f / 24.0
                yaw_w = S['amp'] * math.sin(tt * S['sw'] * 2 * math.pi + S['ph'])
                pit_w = 0.15 * math.sin(tt * S['sw'] * 1.3 * 2 * math.pi + S['ph'] * 2)
            up = t['up']
            pit_w = max(math.radians(-8), min(math.radians(55), pit_w * up)) * up
            dy = (yaw_w - S['yaw'] + math.pi) % (2 * math.pi) - math.pi
            lim = S['rate'] * step / 24.0
            S['yaw'] += max(-lim, min(lim, dy))
            S['pit'] += max(-lim, min(lim, pit_w - S['pit']))
            t.rotation_euler = (0, 0, S['yaw'])
            t.keyframe_insert('rotation_euler', frame=f)
            S['g'].rotation_euler = (0, -S['pit'], 0)
            S['g'].keyframe_insert('rotation_euler', frame=f)
    sc.frame_set(f0)


def recoil(base_ob, f, kick=None):
    """Barrel kick-back at frame f (keys on the gun's location)."""
    g = gun_of(base_ob)
    r = base_ob['r']
    p0 = g.location.copy()
    kick = kick or 0.35 * r
    g.keyframe_insert('location', frame=f - 1)
    g.location = p0 - Vector((kick, 0, 0))
    g.keyframe_insert('location', frame=f)
    g.location = p0
    g.keyframe_insert('location', frame=f + 4)


def muzzle_flash(p, d, f, col, size):
    o = SP.C.uv_sphere(SP._uid('Mflash'), 1.0, seg=(10, 6), mat=SP.emit(SP._uid('MflashM'), col, 40.0),
                       scale=(size * 1.6, size * 0.7, size * 0.7))
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = SP.aim_quat(d)
    o.location = p + d * size * 0.8
    o.visible_shadow = False
    SP.show(o, f, f + 1)
    return o


def fire_bolt(src, tgt, f, profile, col=BLUE, speed=420.0, impact=True, seed=0):
    size, strength, boom = SHOT_LOOK[profile]
    n = max(2, int((tgt - src).length / speed * 24))
    SP.bolt(src, tgt, f, n, col, size=(size[0], size[1], size[1]), strength=strength)
    d = (tgt - src).normalized()
    muzzle_flash(src, d, f, col, size[1] * 3)
    if impact and boom > 0:
        (SP.blue_boom if col == BLUE else SP.gold_boom)(tgt, f + n, boom, life=0.35 + boom * 0.05)
    return f + n


# ------------------------------------------------------------------ idle life of a hull
def hull_life(ob, f0, f1, seed, roll_deg=2.0, pitch_deg=1.0, period=(5.0, 8.0), rcs=True, col=(0.8, 0.9, 1.0)):
    """Own slow banking/pitching on top of its keyed rotation (delta rotation), plus occasional RCS puffs."""
    rnd = random.Random(seed)
    pr, pp = rnd.uniform(*period), rnd.uniform(*period)
    ph1, ph2 = rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)
    ob.delta_rotation_euler = (0, 0, 0)
    for f in range(f0, f1 + 1, 4):
        t = f / 24.0
        ob.delta_rotation_euler = (math.radians(roll_deg) * math.sin(2 * math.pi * t / pr + ph1),
                                   math.radians(pitch_deg) * math.sin(2 * math.pi * t / pp + ph2), 0)
        ob.keyframe_insert('delta_rotation_euler', frame=f)
    if rcs:
        bb = [Vector(b) for b in ob.bound_box]
        lo = Vector((min(b.x for b in bb), min(b.y for b in bb), min(b.z for b in bb)))
        hi = Vector((max(b.x for b in bb), max(b.y for b in bb), max(b.z for b in bb)))
        f = f0 + rnd.randint(6, 30)
        while f < f1:
            side = rnd.choice((-1, 1))
            p = Vector((rnd.uniform(lo.x, hi.x), hi.y if side > 0 else lo.y, rnd.uniform(lo.z, hi.z) * 0.6))
            o = SP.C.uv_sphere(SP._uid('Rcs'), 1.0, seg=(8, 6), mat=SP.emit(SP._uid('RcsM'), col, 6.0),
                               scale=(0.3, 0.6, 0.3))
            o.parent = ob
            o.location = p + Vector((0, side * 0.5, 0))
            o.visible_shadow = False
            SP.key_scale(o, [(f, (0.1, 0.2, 0.1)), (f + 2, (0.35, 0.9, 0.35)), (f + 6, (0.6, 1.6, 0.6))])
            SP.show(o, f, f + 6)
            f += rnd.randint(24, 60)


# ------------------------------------------------------------------ missile ship tube doors
def tube_doors(ship, tubes, salvos, r=1.3):
    """Iris shutter over each tube mouth: opens 0.3 s before a salvo, closes 0.5 s after (frames)."""
    out = []
    for i, p in enumerate(tubes):
        for s in (-1, 1):
            o = SP.C.uv_sphere(SP._uid('Door'), 1.0, seg=(16, 8), mat=None, scale=(0.12, r, r * 0.5))
            o.data.materials.clear()
            mats = [m for m in ship.data.materials if m]
            if mats:
                o.data.materials.append(mats[0])
            o.parent = ship
            out.append((o, Vector(p), s))
    for o, p, s in out:
        shut = p + Vector((0.1, 0, s * r * 0.5))
        opened = p + Vector((0.1, 0, s * r * 1.45))
        keys = [(1, shut)]
        for fa, fb in salvos:
            keys += [(fa - 8, shut), (fa - 1, opened), (fb + 6, opened), (fb + 14, shut)]
        keys.sort(key=lambda k: k[0])
        SP.key_loc(o, keys, 'BEZIER')
    return [o for o, _, _ in out]


# ------------------------------------------------------------------ Arcadian life
def wing_flex(ob, f0, f1, seed, deg=14.0, period=0.9):
    """Stingray wings ripple: a bend deformer swinging on its own beat."""
    rnd = random.Random(seed)
    m = ob.modifiers.new('Flex', 'SIMPLE_DEFORM')
    m.deform_method = 'BEND'
    m.deform_axis = 'Y'
    per, ph = period * rnd.uniform(0.8, 1.25), rnd.uniform(0, 6.28)
    for f in range(f0, f1 + 1, 2):
        m.angle = math.radians(deg) * math.sin(2 * math.pi * (f / 24.0) / per + ph)
        m.keyframe_insert('angle', frame=f)


def orbiters(ob, f0, f1, seed, n=3, radius=None, size=0.22, col=GOLD):
    """Small gold floating parts circling the hull, each on its own orbit plane and speed."""
    rnd = random.Random(seed)
    bb = [Vector(b) for b in ob.bound_box]
    R = radius or max(max(b.y for b in bb), max(b.z for b in bb)) * 1.35
    out = []
    for i in range(n):
        piv = bpy.data.objects.new(SP._uid('OrbitPiv'), None)
        SP.link(piv)
        piv.parent = ob
        piv.location = (rnd.uniform(-2, 2), 0, 0)
        piv.rotation_euler = (rnd.uniform(-0.8, 0.8), rnd.uniform(-0.5, 0.5), 0)
        o = SP.C.uv_sphere(SP._uid('Orbiter'), size, seg=(10, 6), mat=SP.emit(SP._uid('OrbiterM'), col, 8.0))
        o.parent = piv
        o.location = (0, R * rnd.uniform(0.85, 1.15), 0)
        w = rnd.choice((-1, 1)) * rnd.uniform(0.6, 1.4)
        piv.keyframe_insert('rotation_euler', frame=f0)
        e = piv.rotation_euler.copy()
        piv.rotation_euler = (e.x + w * (f1 - f0) / 24.0 * 2.0, e.y, e.z)
        piv.keyframe_insert('rotation_euler', frame=f1)
        SP.lin(piv)
        out.append(o)
    return out


def charge_rings(p, d, f_charge, f_fire, f_end, r=6.0, col=GOLD, name='Ring', n=3):
    """Rings round a beam emitter: spin up and brighten through the charge, flare at fire, fade after."""
    out = []
    for i in range(n):
        o = SP.C.uv_sphere(SP._uid(name), 1.0, seg=(32, 6), mat=SP.emit(SP._uid(name + 'M'), col, 10.0),
                           scale=(0.06, r * (1 + 0.35 * i), r * (1 + 0.35 * i)))
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = SP.aim_quat(d)
        o.location = p + d * (2.0 + 2.5 * i)
        o.visible_shadow = False
        SP.key_scale(o, [(f_charge, (0.02, r * 0.4, r * 0.4)), (f_fire - 2, (0.06, r * (1 + 0.35 * i), r * (1 + 0.35 * i))),
                         (f_fire + 2, (0.1, r * (1.3 + 0.35 * i), r * (1.3 + 0.35 * i))),
                         (f_end, (0.01, r * (1.6 + 0.35 * i), r * (1.6 + 0.35 * i)))])
        SP.show(o, f_charge, f_end)
        out.append(o)
    return out


def arc_shot(src, tgt, f, frames=3, seed=0, width=0.18, name='Arc'):
    """Arcadian corvette lightning shot: one tight crackling channel src -> tgt (a few short forks), re-struck
    every frame for `frames` frames, gold-white core in a gold sleeve."""
    import shard_fx as SFX
    rnd = random.Random(seed)
    core_m = SFX._emit('ArcCoreM', (1.0, 0.92, 0.75), 18.0)
    sleeve_m = SFX._halo('ArcSleeveM', (1.0, 0.6, 0.15), 5.0, 1.5)
    src, tgt = Vector(src), Vector(tgt)
    L = (tgt - src).length
    out = []
    for v in range(frames):
        pts = SFX._jag(src, tgt, rnd, 6, 0.05)
        objs = [SFX._tube_path(SP._uid(name + 'C'), pts, width * 0.3, core_m),
                SFX._tube_path(SP._uid(name + 'S'), pts, width, sleeve_m, sides=8)]
        for b in range(3):
            j = rnd.randint(len(pts) // 5, len(pts) - 3)
            d = (pts[j + 1] - pts[j]).normalized()
            side = d.orthogonal().normalized()
            side.rotate(SP.Quaternion(d, rnd.uniform(0, 6.28)))
            e = pts[j] + (d + side * 0.8).normalized() * L * rnd.uniform(0.03, 0.07)
            br = SFX._jag(pts[j], e, rnd, 3, 0.2)
            objs.append(SFX._tube_path(SP._uid(name + 'F'), br, width * 0.5, sleeve_m, sides=6))
        for o in objs:
            SP.show(o, f + v, f + v)
        out += objs
    return out
