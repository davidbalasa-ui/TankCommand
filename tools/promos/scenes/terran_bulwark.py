"""Bulwark (Terran heavy tank): slow, inevitable, heavy.

An Aegis and a Lumen hold a ridge line and pour gold lightning into the Bulwark as it grinds
toward them. The bolts splash off its front armour in crawling arcs and spark showers; it does
not flinch, turret still turned off to the side. It brakes to a stop, the turret swings round
and settles on the Aegis. Hold. ONE blast: the hull slams back on its tracks, the barrel slams
80% into the turret, a ring of dust jumps off the ground. The Aegis is torn apart, its hover
wreck crashes and burns. The Lumen bolts; the Bulwark grinds on toward the wreck.

0.00-1.75  low front 3/4, dollying back: the Bulwark grinds at us, bolts splashing off its front.
1.75-2.92  reverse, long lens from behind the Arcadian line: the Aegis fires again; the Bulwark
           stops and its turret swings round onto the lens.
2.92-4.67  low over its left shoulder looking down the barrel at the Aegis: settle... BLAST
           (3.25): recoil, dust ring, the Aegis breaks apart and its wreck crashes.
4.67-6.00  from beyond the burning wreck, long lens: the Bulwark rolls on toward us.

Models by name only (bulwark, aegis, lumen)."""
import math
import os
import sys

# promo_fx.destroy seeds its fracture from hash(str): pin the hash seed so every run (stills,
# preview, final) breaks the Aegis the same way
if os.environ.get('PYTHONHASHSEED') != '3':
    os.environ['PYTHONHASHSEED'] = '3'
    os.execv(sys.executable, [sys.executable] + sys.argv)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx  # noqa: E402
import promo_fx_weapons as W  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('terran_bulwark', seconds=6.0, seed=11)
FPS = P.fps
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)

AEG = (18.0, 1.5)
LUM = (14.0, 9.0)
P.env('dusk', sun=(66, 0, -150), sun_energy=4.2,
      clear=[(-4, 0, 9), (12, 1, 9), (AEG[0], AEG[1], 8), (LUM[0], LUM[1], 5), (6, -6, 4),
             (40, 12, 4), (30, 8, 4), (-7.5, 5.5, 4), (1, -2.6, 3)], props=34)
P.flatten(-3, 0, 10)
P.flatten(12, 1, 10)
P.flatten(AEG[0], AEG[1], 8)
P.flatten(LUM[0], LUM[1], 5)


def gz(x, y):
    return P.ground_z(x, y)


def frame_t(fr):
    """Time of a whole frame (cuts land on frames)."""
    return (fr - 1) / FPS


# --------------------------------------------------------------------------- timeline
T_STOP = 2.75       # Bulwark at rest
T_SETTLE = 3.0      # turret settled on the Aegis
T_FIRE = 3.25       # the one blast
C1, C2, C3 = frame_t(43), frame_t(71), frame_t(113)     # 1.75, 2.917, 4.667

# --------------------------------------------------------------------------- the Bulwark
bul = P.load('bulwark', at=(-7.5, 0), heading=0, label='bulwark')
bul.split_barrels()
mzb = bul.muzzle()
bul.path([
    (0.0, (-7.5, 0.0)),
    (1.0, (-4.9, 0.0)),
    (2.0, (-2.3, 0.0)),
    (2.5, (-1.05, 0.0)),
    (T_STOP, (-0.75, 0.0)),
    (T_FIRE, (-0.75, 0.0)),
    (T_FIRE + 0.12, (-1.3, 0.0)),          # the shot shoves 50 t back on its tracks
    (T_FIRE + 0.7, (-1.2, 0.0)),
    (4.4, (-1.2, 0.0)),
    (5.1, (-0.4, 0.0)),
    (6.0, (1.7, 0.0)),
    (7.0, (4.2, 0.0)),
], face=False)
bul.motion['scale'] = 1.3
P.dust(bul, 0.0, T_STOP - 0.1, every=0.12, size=0.75)
P.dust(bul, 4.6, 6.0, every=0.14, size=0.7)

bpy.context.view_layer.update()
inv = bul.root.matrix_world.inverted()
hullv = []
for o in bul.meshes:
    if o.parent and 'Turret' in o.parent.name:
        continue
    hullv += [inv @ (o.matrix_world @ v.co) for v in o.data.vertices]
FX = max(v.x for v in hullv)
TOPZ = max(v.z for v in hullv)
print('BULWARK hull front x', FX, 'top z', TOPZ)


def armour(y, z):
    """Root-local point on the front armour at (y, z): the front-most hull vertex in that band."""
    band = [v for v in hullv if abs(v.y - y) < 0.3 and abs(v.z - z) < 0.18] or hullv
    v = max(band, key=lambda c: c.x)
    return Vector((v.x + 0.03, y, v.z))


# glacis points (root-local) where bolts land
HITS = [armour(0.45, 0.55), armour(-0.6, 0.7), armour(0.05, 0.4), armour(0.8, 0.65), armour(-0.3, 0.5),
        armour(0.35, 0.72)]
print('HITS', [tuple(round(c, 2) for c in h) for h in HITS])

# --------------------------------------------------------------------------- the Arcadians
HOV = 0.75
aegis = P.load('aegis', at=(AEG[0] + 4, AEG[1] + 0.5), heading=180, label='aegis')
aegis.split_barrels(thin=0.46)
aegis.path([(0.0, (AEG[0] + 3.0, AEG[1] + 0.4, HOV)), (1.6, (AEG[0] + 0.6, AEG[1] + 0.1, HOV)),
            (2.4, (AEG[0], AEG[1], HOV)), (6.0, (AEG[0], AEG[1], HOV))], face=False)
aegis.hover_bob(0.04, 0.9)
mza = aegis.muzzle()

lumen = P.load('lumen', at=LUM, heading=212, label='lumen')
lumen.split_barrels()
mzl = lumen.muzzle()
LZ = 0.7
lumen.path([(0.0, (LUM[0] + 1.2, LUM[1] + 0.6, LZ), 212), (2.0, (LUM[0], LUM[1], LZ), 212),
            (3.7, (LUM[0] + 0.2, LUM[1] + 0.1, LZ), 212), (4.4, (LUM[0] + 2.2, LUM[1] + 1.2, LZ), 230),
            (5.2, (LUM[0] + 6.5, LUM[1] + 3.2, LZ), 340), (6.0, (LUM[0] + 12.0, LUM[1] + 4.6, LZ), 350),
            (7.0, (LUM[0] + 19.0, LUM[1] + 5.6, LZ), 352)])
lumen.hover_bob(0.08, 1.1)

# Aegis lifters: a short dense crackle of gold bolts under the belly (from arcadian_aegis)
bolt_mat = emit_mat('AegisLiftBolt', DEEP_GOLD, 1.9)
glow_m = emit_mat('AegisLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)
bpy.context.view_layer.update()
hull = [o for o in aegis.meshes if o.name.startswith('Hull')][0]
ainv = aegis.model_root.matrix_world.inverted()
belly = [ainv @ (hull.matrix_world @ v.co) for v in hull.data.vertices if v.co.z < 0.25]
BX0, BX1 = min(p.x for p in belly) * 0.7, max(p.x for p in belly) * 0.7
BY = max(abs(p.y) for p in belly) * 0.55


def jag(p0, p1, segs, amp, rnd):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            e = math.sin(math.pi * u)
            q += Vector((rnd.uniform(-amp, amp), rnd.uniform(-amp, amp), rnd.uniform(-amp, amp) * 0.5)) * e
        pts.append(q)
    return pts


def crackle(a, f_end, n_lift=12, bx=(BX0, BX1), by=BY):
    rnd = P.rnd
    for f in range(1, f_end):
        objs = []
        for k in range(n_lift):
            p0 = Vector((rnd.uniform(*bx), rnd.uniform(-by, by), 0.06))
            side = 1 if p0.y > 0 else -1
            p1 = p0 + Vector((rnd.uniform(-0.25, 0.15), side * rnd.uniform(0.1, 0.35), -rnd.uniform(0.2, 0.4)))
            pts = jag(p0, p1, 4, 0.08, rnd)
            objs += [polyline('ALift', pts, 0.016, bolt_mat), polyline('ALiftHalo', pts, 0.055, glow_m)]
        for o in objs:
            o.parent = a.model_root
            show_between(o, f, f + 1)


def lift_light(a, f_end, energy=160):
    L = link(bpy.data.objects.new(a.name + 'LiftLight', bpy.data.lights.new(a.name + 'LiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.25)
    L.data.color = GOLD
    L.data.shadow_soft_size = 1.0
    L.data.energy = energy
    L.data.keyframe_insert('energy', frame=f_end - 1)
    L.data.energy = 0
    L.data.keyframe_insert('energy', frame=f_end)


# --------------------------------------------------------------------------- bolts on the armour
def front(t, local):
    """t -> world point riding the Bulwark's armour (followed per frame)."""
    return bul.world_at(bul.root, t, local=local)


def splash(t, local, size=1.0):
    """A bolt lands on the glacis: arcs crawl over the plate and earth into the dirt, gold sparks
    glance off forward and up; the armour shrugs it off."""
    rnd = P.rnd
    p = front(t, local)
    for k in range(3):
        off = Vector((rnd.uniform(-0.9, -0.2), rnd.uniform(-1.1, 1.1), rnd.uniform(-0.35, 0.45)))
        P.lightning(lambda tt, l=local: front(tt, l), lambda tt, l=local + off: front(tt, l),
                    t + 0.01 * k, t + 0.13 + 0.03 * k, width=0.02 * size, jag=0.35, branches=0, segs=5, glow=False)
    # one arc grounds out in front of the tracks
    g = local + Vector((rnd.uniform(0.6, 1.2), rnd.uniform(-0.8, 0.8), 0))
    gw = bul.world_at(bul.root, t, local=g)
    gw.z = gz(gw.x, gw.y) + 0.02
    P.lightning(p, gw, t + 0.02, t + 0.12, width=0.022 * size, jag=0.3, branches=1, segs=6, glow=False)
    W.sparks(P, p, t, n=int(18 * size), speed=8.5 * size, color=DEEP_GOLD,
             axis=Vector((0.8, 0, 0.6)), spread=55, life=(0.2, 0.5))
    W.flash(P, p, t, 0.22 * size, DEEP_GOLD, frames=(1, 2, 4), e=2.2, hot=0.25)
    W.star(P, p, t, 0.8 * size, DEEP_GOLD, n=5)
    P.light(p + Vector((0.6, 0, 0.3)), t, GOLD, energy=260 * size, dur=0.1, radius=0.2)
    P.sfx(t, 'impact_gold', gain=0.55 * size, pos=tuple(p))


def bolt(src_actor, mz, t, local, size=1.0, kick=2.0):
    """Arcadian gold lightning from `mz` onto the Bulwark's front at `local`."""
    tgt = K.empty('BoltTarget')
    tgt.parent = bul.root
    tgt.location = local
    src_actor.aim(t, front(t, local), dur=0.4)
    P.shot(mz, tgt, 'lightning', t, size=size, impact=False, dur=0.16, branches=2, jag=0.22)
    if src_actor.barrels:
        src_actor.recoil(t, collapse=0.5, kick=kick, back=0.1, settle=0.4)
    P.sfx(t, 'zap_lightning', gain=0.6 * size, pos=tuple(src_actor.pos_at(t)))
    splash(t + 0.02, local, size=size)


# Aegis: heavy bolts every ~1.1 s; Lumen: quicker, lighter
bolt(aegis, mza, 0.30, HITS[0], size=1.5, kick=3)
bolt(lumen, mzl, 0.80, HITS[1], size=1.0)
bolt(aegis, mza, 1.35, HITS[2], size=1.5, kick=3)
bolt(lumen, mzl, 1.62, HITS[3], size=1.0)
bolt(aegis, mza, 2.35, HITS[4], size=1.6, kick=3)
bolt(lumen, mzl, 2.62, HITS[5], size=1.0)
lumen.aim(3.2, front(3.2, HITS[1]), dur=0.4)

# --------------------------------------------------------------------------- turret: unbothered, then settle
bul.turret_yaw([(0.0, 20), (2.3, 20)])
bul.aim(T_SETTLE, aegis, dur=0.7)
P.sfx(2.3, 'turret_servo', gain=0.7, rate=0.7)
P.sfx(T_SETTLE, 'mech_clunk', gain=0.6, rate=0.7)

# --------------------------------------------------------------------------- THE blast
AIM_PT = aegis.pos_at(T_FIRE) + Vector((0, 0, HOV + 0.9))
t_hit = bul.fire(T_FIRE, AIM_PT, kind='heavy', size=2.2, speed=160, recoil=False, impact=False)
bul.recoil(T_FIRE, collapse=0.8, kick=16.0, back=1.0, settle=1.0)
P.cam_shake(T_FIRE, 0.22, 0.5)
P.sfx(T_FIRE, 'shot_heavy', gain=1.0, rate=0.8)
P.sfx(T_FIRE + 0.01, 'sub_boom', gain=1.0, rate=0.85)
P.sfx(T_FIRE + 0.05, 'shockwave', gain=0.6)
P.sfx(T_FIRE + 0.55, 'hydraulic', gain=0.45, rate=0.8)
P.sfx(T_FIRE + 0.95, 'mech_clunk', gain=0.45, rate=0.8)

# dust ring: the muzzle blast slams the ground all round the hull
bpy.context.view_layer.update()
pal = getattr(P, 'palette', None)
g1 = pal['g1'] if pal and 'g1' in pal else (0.36, 0.29, 0.21)
DUST = tuple(min(1.0, 0.5 * (0.06 + c * 1.5) + 0.5 * w) for c, w in zip(g1, (0.7, 0.58, 0.44)))
bc = bul.pos_at(T_FIRE)
for k in range(22):
    a = 2 * math.pi * (k + P.rnd.uniform(-0.25, 0.25)) / 22
    d = Vector((math.cos(a), math.sin(a), 0.0))
    r0 = 3.2 if abs(math.cos(a)) > 0.5 else 2.4
    p = Vector((bc.x, bc.y, 0)) + Vector((d.x * r0 * 1.15, d.y * r0, 0))
    p.z = gz(p.x, p.y) + 0.18
    W.smoke_puff(P, p, T_FIRE + 0.01 + P.rnd.uniform(0, 0.03), r0=0.3, r1=P.rnd.uniform(1.0, 1.4),
                 life=P.rnd.uniform(1.8, 2.4), vel=d * P.rnd.uniform(8.0, 11.0) + Vector((0, 0, 0.3)),
                 color=DUST, dens=1.8, wind=(0.3, 0.1, 0.25))
# the blast cone under the muzzle tears the ground ahead
mw = bul.world_at(mzb, T_FIRE - 1 / FPS)
fwd = (AIM_PT - mw)
fwd.z = 0
fwd.normalize()
for i in range(6):
    p = mw + fwd * (0.8 + 0.9 * i)
    p.z = gz(p.x, p.y) + 0.2
    side = Vector((-fwd.y, fwd.x, 0)) * P.rnd.choice((-1, 1))
    W.smoke_puff(P, p, T_FIRE + 0.02 + 0.015 * i, r0=0.3, r1=1.1 + 0.15 * i, life=1.8,
                 vel=side * P.rnd.uniform(3, 6) + fwd * 3 + Vector((0, 0, 1.2)), color=DUST, dens=1.0)
# big muzzle smoke drifting off the barrel tip afterwards
for i in range(5):
    W.smoke_puff(P, mw + fwd * (0.6 + 0.7 * i) + Vector((0, 0, 0.1)), T_FIRE + 0.04 + 0.02 * i,
                 r0=0.25, r1=0.9 + 0.2 * i, life=2.4, vel=fwd * (6 - i) + Vector((0, 0, 0.6)),
                 color=(0.62, 0.6, 0.58), dens=0.8, hot=1.2 if i < 2 else 0.0)
for k in range(6):
    tk = T_FIRE + 0.6 + 0.35 * k
    P.puff(bul.world_at(mzb, tk), tk, size=0.35, n=1, rise=0.9, life=1.4, color=(0.4, 0.39, 0.38), opacity=0.3)


# --------------------------------------------------------------------------- the Aegis dies
def big_blast(pos, t, size):
    """Fireball of ragged glows, a burst of gold arcs as the cores rupture, sparks, smoke."""
    rnd = P.rnd
    pos = Vector(pos)
    W.flash(P, pos, t, 0.35 * size, (1.0, 0.5, 0.12), frames=(1, 2, 4), e=2.2, hot=0.3)
    for i in range(9):
        d = W._cone_dir(P, Vector((0, 0, 1)), 85)
        o = W.flash(P, pos + d * 0.3 * size, t + 0.012 * i, rnd.uniform(0.55, 0.85) * size,
                    (1.0, rnd.uniform(0.3, 0.45), 0.06), frames=(2, 5, 13), e=2.2, hot=0.15, name='BlastFire')
        o['fx_noise'] = 1.0
        o['fx_p'] = 1.0
        W.kprop(o, 'fx_w', P.T(t), rnd.uniform(0, 5))
        W.kprop(o, 'fx_w', P.T(t) + 13, rnd.uniform(6, 9))
        o.keyframe_insert('location', frame=P.T(t))
        o.location = o.location + d * 1.2 * size + Vector((0, 0, 0.8 * size))
        o.keyframe_insert('location', frame=P.T(t) + 13)
    for i in range(7):
        a = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 0.9))).normalized()
        P.lightning(pos, pos + a * rnd.uniform(2.2, 3.6) * size * 0.6, t + 0.01 * i, t + 0.16 + 0.02 * i,
                    width=0.035, jag=0.3, branches=1, segs=7, glow=False)
    W.sparks(P, pos, t, n=34, speed=14, color=(1.0, 0.5, 0.1), axis=Vector((0, 0, 1)), spread=100, life=(0.4, 1.1))
    W.sparks(P, pos, t + 0.03, n=14, speed=9, color=DEEP_GOLD, axis=Vector((0, 0, 1)), spread=120, life=(0.3, 0.7))
    P.light(pos + Vector((0, 0, size * 0.5)), t, (1.0, 0.55, 0.2), energy=5000 * size, dur=0.5, radius=size * 0.5)
    for i in range(7):
        d = W._cone_dir(P, Vector((0, 0, 1)), 60)
        W.smoke_puff(P, pos + d * 0.5 * size, t + 0.12 + 0.03 * i, r0=0.4 * size, r1=rnd.uniform(1.0, 1.5) * size,
                     life=rnd.uniform(2.2, 2.8), vel=d * rnd.uniform(3, 6) + Vector((0, 0, 1.5)),
                     color=(0.3, 0.29, 0.28), dens=1.2, hot=1.6 if i < 3 else 0.0)
    W.dirt_kick(P, Vector((pos.x, pos.y, gz(pos.x, pos.y))), t, size=1.0)


T_KILL = t_hit
F_KILL = P.T(T_KILL)
crackle(aegis, int(F_KILL) + 1)
lift_light(aegis, int(F_KILL) + 1)
crackle(lumen, P.nf + 2, n_lift=6, bx=(-1.2, 1.0), by=0.8)
lift_light(lumen, P.nf + 3, energy=90)
P.dust(lumen, 3.9, 6.0, every=0.12, size=0.7)

ok = promo_fx.destroy(aegis, T_KILL, size=3.2, wreck=True, debris=18)
print('FRACTURE', ok, 'flipbooks', bool(promo_fx.find_flipbook('explo_ground')))
if ok:
    aegis.vanish(T_KILL + 1 / FPS)
    aegis.alive_until = T_KILL
else:
    aegis.destroy(T_KILL, size=3.2)
ap = aegis.pos_at(T_KILL) + Vector((0, 0, 1.4))
if not promo_fx.find_flipbook('explo_ground'):
    big_blast(ap, T_KILL, 2.6)
P.sfx(T_KILL, 'boom_big', gain=1.0)
P.sfx(T_KILL + 0.02, 'zap_lightning', gain=0.6, rate=0.8)
P.sfx(T_KILL + 0.08, 'debris_metal', gain=0.8)
P.sfx(T_KILL + 0.6, 'debris_metal', gain=0.6, rate=0.8)
P.cam_shake(T_KILL, 0.12, 0.4)

def flames(pos, t0, t1, size=1.0):
    """Burning wreck: small hot volumetric puffs licking up (fire colour from emission), a
    flickering light."""
    rnd = P.rnd
    pos = Vector(pos)
    tt = t0
    while tt < t1:
        off = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.6 * size
        life = rnd.uniform(0.5, 0.75)
        o = W.smoke_puff(P, pos + off, tt, r0=0.18 * size, r1=0.5 * size, life=life,
                         vel=(0, 0, rnd.uniform(2.0, 3.0) * size), color=(0.25, 0.2, 0.18), dens=1.4,
                         wind=(0.3, 0.1, 0.4))
        f0 = P.T(tt)
        W.kprop(o, 'fx_e', f0, 7.0)
        W.kprop(o, 'fx_e', f0 + life * 0.5 * P.fps, 3.0)
        W.kprop(o, 'fx_e', f0 + life * P.fps, 0.0)
        tt += 0.05
    W.flicker_light(P, pos + Vector((0, 0, 1.0)), t0, t1, (1.0, 0.45, 0.12), 300 * size, radius=0.6, every=2)
    P.sfx(t0, 'fire_loop', gain=0.4, pos=tuple(pos), dur=t1 - t0)


# the wreck burns where its biggest piece came to rest (fire/smoke flipbooks may be missing)
frags = [o for o in bpy.data.objects if o.name.startswith('aegis_Frag')]
if frags and not promo_fx.find_flipbook('fire_loop'):
    sc = bpy.context.scene
    sc.frame_set(P.nf)
    big = max(frags, key=lambda o: max(o.dimensions))
    sc.frame_set(int(F_KILL) + 14)
    rest = big.matrix_world.translation.copy()
    sc.frame_set(1)
    rest.z = gz(rest.x, rest.y) + 0.5
    flames(rest, T_KILL + 0.45, 6.2, size=1.0)
    tt = T_KILL + 0.6
    while tt < 6.0:
        W.smoke_puff(P, rest + Vector((P.rnd.uniform(-0.5, 0.5), P.rnd.uniform(-0.5, 0.5), 0.6)), tt,
                     r0=0.4, r1=1.4, life=2.4, vel=(0, 0, 2.2), color=(0.24, 0.23, 0.22), dens=1.1,
                     wind=(0.6, 0.3, 0.6))
        tt += 0.16
    print('WRECK REST', rest)

# --------------------------------------------------------------------------- camera
P.camera([
    # shot 1: low front 3/4, dollying back as it grinds at us; bolts come past the lens
    (0.0, (2.2, -2.0, 0.45), (-7.0, 0.4, 1.0), 30),
    (C1 - 1 / FPS, (3.4, -2.9, 0.5), (-2.6, 0.4, 1.0), 30),
    # shot 2: reverse, long lens from behind the Arcadian line, the Aegis in the foreground
    (C1, (40.0, 12.0, gz(40.0, 12.0) + 2.6), (8.0, 0.2, 1.0), 90),
    (C2 - 1 / FPS, (39.4, 11.8, gz(39.4, 11.8) + 2.5), (8.0, 0.3, 1.0), 96),
    # shot 3: low over the Bulwark's left shoulder, down the barrel at the Aegis
    (C2, (-9.2, 6.6, 2.2), (6.0, -1.0, 1.2), 26),
    (T_FIRE, (-9.0, 6.5, 2.2), (6.3, -1.0, 1.2), 26),
    (C3 - 1 / FPS, (-8.3, 6.1, 2.25), (8.5, -0.2, 1.3), 34),
    # shot 4: from beyond the burning wreck, long lens: it rolls on toward us
    (C3, (30.0, 8.0, gz(30.0, 8.0) + 2.2), (2.0, 0.0, 1.0), 60),
    (6.0, (29.4, 7.8, gz(29.4, 7.8) + 2.0), (3.5, 0.9, 1.0), 72),
], cuts=(C1, C2, C3), shake=0.015)

P.render()
