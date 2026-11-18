"""Sunfall (Arcadian artillery): it draws in the light, heaves three times, and the sun falls.

Dusk. The Sunfall glides into its firing spot behind a low ridge and sinks onto its lightning
skirt. Threads of gold light stream in from the air and pour into the great orb in its cage until
it burns. Three blasts inside one second: each one heaves the whole body back and up and throws a
ring of dust off the ground, and a small sun climbs out of the cradle into the evening sky.
Over the ridge a Terran gun line (Bastion gun tower, two Lancers) waits with its guns on the
crest; the three suns come down out of the sky on it, far to near. Back home the orb is dark and
the long reload begins: light trickles back into it while three smoke columns rise over the ridge.

0-1.5     low front 3/4: the Sunfall glides in, brakes, sinks onto its skirt; light streams into
          the orb and it swells bright (turret swings onto the bearing).
1.5-2.75  low on its left front, close: three blasts (1.70 / 2.08 / 2.46), huge heaves, dust
          rings, three suns climb out of frame; the camera tilts up after them.
2.75-4.38 low behind the Terran gun line looking back at the ridge: the suns arc over the crest
          and crash down: Lancer A (3.25, reversing away), the Bastion (3.63), Lancer B (4.01,
          closest to camera).
4.38-6    high over the Sunfall's shoulder: the orb is dark and slowly refills; beyond the crest
          three burning wrecks and their smoke."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
from mathutils import Vector  # noqa: E402

import promo_kit as K  # noqa: E402
import promo_fx_weapons as W  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link, sphere  # noqa: E402

P = Promo('arcadian_sunfall', seconds=6.0, seed=5)
FPS = P.fps
R = P.rnd
GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)


def ss(x):
    return K.smoothstep(max(0.0, min(1.0, x)))


# --------------------------------------------------------------------------- terrain: a low ridge
CREST = 17.0


def crest_x(y):
    return CREST + 0.8 * math.sin(y * 0.13) + 0.4 * math.sin(y * 0.37 + 1.0)


def ridge(x, y):
    taper = ss((70 - abs(y)) / 20.0)
    return 2.7 * math.exp(-((x - crest_x(y)) / 4.8) ** 2) * taper


P.env('dusk', sun=(70, 0, 145), sun_energy=4.0, props=30,
      clear=[(0, 0, 10), (37, -4, 12), (-6, -2, 6)])
g = P.ground
for v in g.data.vertices:
    v.co.z += ridge(v.co.x, v.co.y)
g.data.update()
P.flatten(0, 0, 8)
P.flatten(37, -4, 10)
bpy.context.view_layer.update()


def gz(x, y):
    return P.ground_z(x, y)


# --------------------------------------------------------------------------- the Terran gun line
def deployed(a):
    for o in [a.model_root] + list(a.model_root.children_recursive):
        if o.get('hideWhenDeployed'):
            o.hide_render = True
            o.hide_viewport = True
    a.meshes = [m for m in a.meshes if not m.get('hideWhenDeployed')]
    return a


BA = (36.8, -7.1)
LA = (31.2, 0.0)
LB = (44.0, -4.0)
bastion = deployed(P.load('bastion', at=(*BA, gz(*BA)), heading=165, label='bastion'))
bastion.split_barrels()
lancA = P.load('lancer', at=(*LA, gz(*LA)), heading=185, label='lancerA')
lancA.split_barrels()
lancB = P.load('lancer', at=(*LB, gz(*LB)), heading=170, label='lancerB')
lancB.split_barrels()
# Lancer A sees something coming and starts to back off; too late
lancA.path([(0.0, LA), (2.85, LA), (3.3, (LA[0] + 1.3, LA[1] + 0.1))], face=False)

# --------------------------------------------------------------------------- the Sunfall
HOV = 0.5
LOW = 0.3
SX, SY = 0.0, 0.0
HEAD = -8.0
sunfall = P.load('sunfall', at=(-9, -2.5), heading=HEAD, label='sunfall')
sunfall.path([
    (0.0, (-8.0, -2.2, gz(-8, -2.2) + HOV)),
    (0.55, (-2.6, -0.6, HOV)),
    (0.95, (SX, SY, HOV), HEAD),
    (1.35, (SX, SY, LOW), HEAD),
    (2.6, (SX - 0.1, SY, LOW), HEAD),
    (3.4, (SX - 0.15, SY, HOV - 0.05), HEAD),
    (6.0, (SX - 0.15, SY, HOV - 0.05), HEAD),
])
sunfall.hover_bob(0.03, 0.7)
bpy.context.view_layer.update()
f_hull = [o for o in sunfall.meshes if o.name.startswith('Hull')][0]
f_tur = [o for o in sunfall.meshes if o.name.startswith('Turret')][0]
finv = sunfall.model_root.matrix_world.inverted()
fbelly = [p for p in (finv @ (f_hull.matrix_world @ v.co) for v in f_hull.data.vertices) if p.z < 0.3]
tv = [finv @ (f_tur.matrix_world @ v.co) for v in f_tur.data.vertices]
ztop = max(p.z for p in tv)
orbv = [p for p in tv if p.z > ztop - 1.1 and abs(p.y) < 0.7]
ORB_C = Vector((sum(p.x for p in orbv) / len(orbv), 0.0, sum(p.z for p in orbv) / len(orbv)))
print('SUNFALL orb centre', ORB_C)
orb_anchor = K.empty('SunfallOrbAnchor')
orb_anchor.parent = sunfall.turret
bpy.context.view_layer.update()
orb_anchor.matrix_parent_inverse = sunfall.turret.matrix_world.inverted() @ sunfall.model_root.matrix_world
orb_anchor.location = ORB_C
# launch "muzzle": the orb leaves the cradle up and forward
LAUNCH_PITCH = 55.0
mz = K.empty('SunfallMuzzle')
mz.parent = orb_anchor
mz.rotation_euler = (0, math.radians(-LAUNCH_PITCH), 0)
mz.location = (0.2, 0, 0.35)


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


# ----- lightning lifters: short, dense crackle tucked under the belly (Darter/Aegis skirt)
bolt_mat = emit_mat('SunLiftBolt', DEEP_GOLD, 1.9)
glow_mat = emit_mat('SunLiftGlow', DEEP_GOLD, 0.7, alpha=0.2)


def crackle(a, pts, n_lift, light_e, tag):
    rnd = P.rnd
    X0, X1 = min(p.x for p in pts) * 0.7, max(p.x for p in pts) * 0.7
    BY = max(abs(p.y) for p in pts) * 0.55
    for f in range(1, P.nf + 2):
        objs = []
        for k in range(n_lift):
            p0 = Vector((rnd.uniform(X0, X1), rnd.uniform(-BY, BY), 0.06))
            if k % 3 == 0:
                p1 = p0 + Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.2, 0.2), -rnd.uniform(0.0, 0.08)))
            else:
                side = 1 if p0.y > 0 else -1
                p1 = p0 + Vector((rnd.uniform(-0.25, 0.15), side * rnd.uniform(0.1, 0.3), -rnd.uniform(0.14, 0.3)))
            pp = jag(p0, p1, 4, 0.07, rnd)
            objs += [polyline(tag + 'Lift', pp, 0.015, bolt_mat), polyline(tag + 'LiftHalo', pp, 0.05, glow_mat)]
        for o in objs:
            o.parent = a.model_root
            o.visible_shadow = False
            show_between(o, f, f + 1)
    L = link(bpy.data.objects.new(tag + 'LiftLight', bpy.data.lights.new(tag + 'LiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.2)
    L.data.color = GOLD
    L.data.energy = light_e
    L.data.shadow_soft_size = 0.8


crackle(sunfall, fbelly, 14, 150, 'F')
P.dust(sunfall, 0.0, 1.2, every=0.12, size=0.65)

# --------------------------------------------------------------------------- timing
T_CH0 = 0.35                         # light starts streaming in
T_SHOTS = [1.70, 2.08, 2.46]         # three blasts inside one second (0.38 s apart: full heave each)
FLIGHT = 1.55
TARGETS = [lancA, bastion, lancB]    # far to near from the gun-line camera
T_RELOAD = 3.0                       # light starts trickling back in

sunfall.aim(1.25, bastion, dur=0.55)

# ----- the orb's own glow (unit material): swells on the charge, drains per shot, refills slowly
fmat = bpy.data.materials['MortarBeastMat']
fb = fmat.node_tree.nodes.get('Principled BSDF')
E0 = fb.inputs['Emission Strength'].default_value
orb_keys = [(0.0, 0.7), (T_CH0, 0.7), (1.45, 1.25), (T_SHOTS[0] - 0.02, 1.35),
            (T_SHOTS[0] + 0.06, 0.6), (T_SHOTS[1] - 0.04, 0.95), (T_SHOTS[1] + 0.06, 0.45),
            (T_SHOTS[2] - 0.04, 0.75), (T_SHOTS[2] + 0.06, 0.12), (T_RELOAD, 0.15), (4.6, 0.4),
            (5.4, 0.75), (5.9, 1.05), (6.0, 1.1)]
for t, k in orb_keys:
    fb.inputs['Emission Strength'].default_value = E0 * k
    fb.inputs['Emission Strength'].keyframe_insert('default_value', frame=P.T(t))

oL = link(bpy.data.objects.new('SunOrbCoreLight', bpy.data.lights.new('SunOrbCoreLight', 'POINT')))
oL.parent = orb_anchor
oL.location = (0, 0, 0.2)
oL.data.color = GOLD
oL.data.shadow_soft_size = 0.6
for t, e in [(0.0, 60), (T_CH0, 60), (1.45, 700), (T_SHOTS[0] - 0.02, 850), (T_SHOTS[0] + 0.06, 250),
             (T_SHOTS[1] - 0.04, 450), (T_SHOTS[1] + 0.06, 180), (T_SHOTS[2] - 0.04, 320),
             (T_SHOTS[2] + 0.06, 0), (T_RELOAD, 0), (4.6, 120), (5.4, 300), (6.0, 480)]:
    oL.data.energy = e
    oL.data.keyframe_insert('energy', frame=P.T(t))


def orb_w(t):
    return sunfall.world_at(orb_anchor, t)


# ----- light streaming into the orb: gold threads converging from the air around it
M_TH = emit_mat('SunThread', (1.0, 0.66, 0.25), 1.8)
M_THG = emit_mat('SunThreadGlow', GOLD, 0.7, alpha=0.18)


def draw_in(t0, t1, n0, n1, r0, r1):
    t = t0
    while t < t1:
        u = (t - t0) / max(1e-3, t1 - t0)
        f = int(round(P.T(t)))
        pe = orb_w(t)
        n = int(round(n0 + (n1 - n0) * u))
        for _ in range(n):
            a = R.uniform(0, 2 * math.pi)
            el = R.uniform(-0.45, 1.0)
            rr = R.uniform(r0, r1) * (1.0 - 0.3 * u)
            d = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)))
            p0 = pe + d * rr
            p1 = pe + d * max(0.6, rr - R.uniform(0.45, 1.0))   # short streak pointing at the orb
            pts = jag(p0, p1, 3, 0.03 * rr, R)
            for o in (polyline('SunTh', pts, 0.011, M_TH), polyline('SunThG', pts, 0.045, M_THG)):
                o.visible_shadow = False
                show_between(o, f, f + 1)
        t += 1 / FPS


draw_in(T_CH0, T_SHOTS[0], 6, 18, 1.0, 2.6)        # the big draw before the volley
draw_in(T_RELOAD + 0.2, 6.0, 2, 7, 0.9, 2.0)      # slow trickle on the reload

# --------------------------------------------------------------------------- the three suns
M_ORB = emit_mat('SunOrb', (1.0, 0.75, 0.35), 2.6)
AIM_PTS = {
    lancA.name: Vector((LA[0] + 1.3, LA[1] + 0.1, 0)),
    bastion.name: Vector((BA[0] + 0.3, BA[1], 0)),
    lancB.name: Vector((LB[0], LB[1], 0)),
}
ORBS = []


def fly_orb(t0, target, dur):
    p0 = sunfall.world_at(mz, t0)
    th = t0 + dur
    q = AIM_PTS[target.name]
    p1 = Vector((q.x, q.y, gz(q.x, q.y) + 0.8))
    apex = max(p0.z, p1.z) + 15.0
    hgt = apex - (p0.z + p1.z) / 2

    def at(u):
        return p0.lerp(p1, u) + Vector((0, 0, 4 * hgt * u * (1 - u)))

    core = sphere('SunOrb', 0.42, M_ORB, seg=(14, 10))
    core.visible_shadow = False
    halo = W.glow(P, 'SunOrbHalo', (1.0, 0.7, 0.25), scale=(1.1, 1.1, 1.1), fx_e=2.2, fx_p=1.6)
    cor = W.glow(P, 'SunOrbCorona', GOLD, scale=(2.0, 2.0, 2.0), alpha=0.3, fx_e=1.6, fx_p=2.4)
    halo.parent = core
    cor.parent = core
    # the corona grows as the sun climbs away (no blow-out right at the cradle)
    for dt, k in ((0.0, 0.25), (0.35, 1.0)):
        for o, s0 in ((cor, 2.0), (halo, 1.1)):
            o.scale = (s0 * k,) * 3
            o.keyframe_insert('scale', frame=P.T(t0 + dt))
    Lt = link(bpy.data.objects.new('SunOrbLight', bpy.data.lights.new('SunOrbLight', 'POINT')))
    Lt.parent = core
    Lt.data.color = GOLD
    Lt.data.energy = 900
    Lt.data.shadow_soft_size = 0.5
    n = int(dur * FPS) + 1
    for i in range(n + 1):
        u = i / n
        core.location = at(u)
        core.keyframe_insert('location', frame=P.T(t0 + dur * u))
    K.set_interp(core, 'LINEAR')
    for o in (core, halo, cor):
        show_between(o, P.T(t0), P.T(th) + 1)
    # glowing wake: fading blobs left behind each frame
    for i in range(1, n):
        u = i / n
        b = W.glow(P, 'SunWake', GOLD, alpha=0.7, fx_e=1.8, fx_p=1.8)
        b.location = at(u)
        f = P.T(t0 + dur * u)
        for df, s in ((0, 0.6), (3, 0.32), (7, 0.03)):
            b.scale = (s, s, s)
            b.keyframe_insert('scale', frame=f + df)
        show_between(b, f, f + 7)
    ORBS.append(at)
    return p1, th


T_HITS = []
for i, (t0, tgt) in enumerate(zip(T_SHOTS, TARGETS)):
    sunfall.recoil(t0, kick=22.0, back=0.9)                 # the whole body heaves
    P.muzzle_flash(mz, t0, GOLD, size=1.5)
    P.light(orb_w(t0), t0, GOLD, energy=2600, dur=0.18, radius=1.0)
    P.cam_shake(t0, 0.1, 0.35)
    # ring of dust thrown off the ground by the heave
    base = sunfall.pos_at(t0)
    for k in range(8):
        ang = 2 * math.pi * k / 8 + R.uniform(-0.2, 0.2)
        r = 3.3
        p = (base.x + r * math.cos(ang), base.y + r * math.sin(ang) * 0.8, gz(base.x, base.y) + 0.2)
        P.puff(p, t0 + 0.02, size=1.0, n=1, rise=0.6, life=1.0, color=(0.42, 0.28, 0.18), opacity=0.32)
    p1, th = fly_orb(t0, tgt, FLIGHT)
    T_HITS.append(th)
    P.impact(p1, th, size=1.8, color=GOLD)
    P.light(p1 + Vector((0, 0, 1.2)), th, GOLD, energy=3000, dur=0.3, radius=0.9)
    for k in range(3):
        a = R.uniform(0, 2 * math.pi)
        q = p1 + Vector((2.4 * math.cos(a), 2.4 * math.sin(a), 0))
        q.z = gz(q.x, q.y) + 0.05
        P.lightning(p1 + Vector((0, 0, 0.3)), q, th + 0.01 * k, th + 0.2, width=0.035, jag=0.25,
                    branches=1, segs=7)
    tgt.destroy(th + 0.03, size=2.4 if tgt is bastion else 2.0)
    P.cam_shake(th, 0.08, 0.3)

# Bastion swings its gun up at the sky: nothing it can do
bastion.aim(3.4, (BA[0] - 15, BA[1] + 4, 6.0), dur=0.6)
lancB.aim(3.85, (LB[0] - 12, LB[1] + 5, 3.0), dur=0.5)

# --------------------------------------------------------------------------- camera
C1, C2, C3 = 37 / FPS, 67 / FPS, 106 / FPS          # 1.5, 2.75, 4.375 s
ORB0 = orb_w(1.4)


def cz(x, y, h):
    return (x, y, gz(x, y) + h)


keys = [
    # A: low front 3/4 on the right: it glides in, sinks, the orb drinks the light
    (0.0, cz(5.5, 7.0, 1.1), sunfall.pos_at(0.0) + Vector((0, 0, 1.8)), 42),
    (0.8, cz(5.2, 6.6, 1.15), sunfall.pos_at(0.8) + Vector((0, 0, 2.0)), 33),
    (C1 - 1 / FPS, cz(4.7, 5.9, 1.2), ORB0 - Vector((0, 0, 0.6)), 34),
    # B: low on its left front, close: three heaves, the suns climb out of frame
    (C1, cz(5.6, -5.2, 0.9), ORB0 - Vector((0.3, 0, 1.2)), 27),
    (T_SHOTS[2], cz(5.4, -5.0, 0.9), ORB0 + Vector((0.4, 0, -0.4)), 27),
    (C2 - 1 / FPS, cz(5.2, -4.9, 0.95), ORB0 + Vector((1.0, 0, 0.3)), 26),
    # C: low behind the Terran line, looking back over the crest at the falling suns
    (C2, cz(52.0, -12.0, 2.3), (24.0, 3.0, 7.5), 26),
    (3.45, cz(51.6, -11.7, 2.3), (25.0, 2.0, 3.6), 27),
    (C3 - 1 / FPS, cz(51.2, -11.4, 2.3), (26.0, 1.0, 2.4), 28),
    # D: high over the Sunfall's shoulder: the orb is dark and fills again; wrecks over the ridge
    (C3, cz(-21.0, -12.0, 7.2), (14.0, 0.5, 0.8), 45),
    (6.0, cz(-19.6, -11.2, 6.9), (15.0, 1.2, 0.9), 50),
]
P.camera(keys, cuts=(C1, C2, C3), shake=0.015)

if os.environ.get('SFDBG'):      # framing check: where each unit / sun sits in frame
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    for f in (1, 20, 36, 40, 54, 66, 70, 84, 96, 105, 108, 144):
        sc.frame_set(f)
        t = (f - 1) / FPS
        row = []
        for a_ in (sunfall, lancA, bastion, lancB):
            c = world_to_camera_view(sc, P.cam, a_.root.matrix_world.translation + Vector((0, 0, 1.0)))
            row.append(f'{a_.name}=({c.x:.2f},{c.y:.2f},{c.z:.0f})')
        for i, at_ in enumerate(ORBS):
            u = (t - T_SHOTS[i]) / FLIGHT
            if 0 <= u <= 1:
                c = world_to_camera_view(sc, P.cam, at_(u))
                row.append(f'sun{i}=({c.x:.2f},{c.y:.2f})')
        print('FRAME', f, ' '.join(row))

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.35, dur=6.0)                 # lightning skirt
P.sfx(T_CH0, 'charge_gold', gain=0.8, rate=0.7)                # the orb drinks the light
P.sfx(T_CH0 + 0.4, 'power_up_arc', gain=0.6, rate=0.75)
for _t in T_SHOTS:
    P.sfx(_t, 'sub_boom', gain=0.9)                            # the heave
    P.sfx(_t + 0.12, 'whoosh', gain=0.5, rate=0.65)            # sun climbing away
for _th in T_HITS:
    P.sfx(_th - 0.45, 'whoosh', gain=0.45, rate=0.8)           # and falling
    P.sfx(_th, 'impact_gold', gain=0.9)
P.sfx(T_RELOAD + 0.2, 'charge_gold', gain=0.4, rate=0.55)      # long reload: light trickles back

P.render()
