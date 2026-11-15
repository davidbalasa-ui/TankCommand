"""Terran attackers push through the Arcadian force aperture of the landing hall (seen from inside).

    /home/user/artenv/venv/bin/python arcadian_breach.py --frames=0-95 --outdir=DIR [--res=960x540] [--samples=10]
        [--shot=A|B|C|H]  (override the camera)   [--step=1]

96 frames at 24 fps. The beats (frame numbers):
     0-14  approach: a Terran tank closes on the aperture from space, decelerating
    14-56  press: its gun tents the skin, then the hull bows it inward; ripples run to the rim, the
           tick rings spin up and tighten, lightning snaps from the rim and crawls over the hull;
           the tank slows as if moving through thick liquid
       56  break: the skin lets go - a clean round hole, a crisp ring pulse, the rings snap outward
    56-76  the tank surges through and drops onto the deck; the skin swings back elastically
    64-78  the hole irises closed behind it with a last pulse and a few last arcs
Cameras: A (0-33) wide from behind the defenders; B (34-61) close on the bulge and the break;
C (62-95) low between the defenders as it lands. H = hero still camera.

Only the aperture end of the hall is built (the plan matches arcadian_deck.py).
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arcadian_kit as K  # noqa: E402
from arcadian_kit import F, A  # noqa: E402
import arcadian_breachfx as FX  # noqa: E402

ARGS = K.args()
RES = tuple(int(v) for v in ARGS.get('res', '960x540').split('x'))
OUTDIR = ARGS.get('outdir', '/home/user/work/arcadian-interiors/b/frames')
SHOT = ARGS.get('shot', '')
H = 7.5
HALL_C, HALL_RX, HALL_RY = (46.0, 0.0), 36.0, 27.0
THROAT, LANE = 16.0, 13.0
AP_X, AP_R, AP_SQ, AP_Z = 89.0, 15.0, 0.62, 9.6
X0 = 36.0                                   # nothing is built west of this
BREAK = 56
rnd = random.Random(7)


def hall_half(x):
    w = 0.0
    u = (x - HALL_C[0]) / HALL_RX
    if abs(u) < 1:
        w = HALL_RY * math.sqrt(1 - u * u)
    if x > 66:
        w = max(w, THROAT)
    return w


def arch(x, t, h):
    w = hall_half(x) + 0.6
    a = math.pi / 2 * t
    return Vector((x, w * math.copysign(abs(math.sin(a)) ** 0.8, t), H + (h - H) * math.cos(a) ** 0.9))


def roof_h(x):
    u = (x - 11.0) / (AP_X + 3 - 11.0)
    return 17.0 + 15.0 * math.sin(math.pi * min(1.0, max(0.0, u)) ** 0.8) ** 0.7 + (7.0 if x > 70 else 7.0 * max(0.0, (x - 55) / 15.0))


def flow_line(ctl, w, zone, h=0.03, steps=8):
    K.strip(A.smooth_pts([Vector(c) for c in ctl], steps), w, h, zone, closed=False)


def build_hall():
    K.slab([(X0 - 2, -32), (AP_X + 1.5, -32), (AP_X + 1.5, 32), (X0 - 2, 32)], [], -1.0, 0.0, 'floor')
    K.slab([(X0, -LANE), (AP_X + 1.5, -LANE), (AP_X + 1.5, LANE), (X0, LANE)], [], 0.0, 0.025, 'floor2')
    xs = [X0 + 0.75 * k for k in range(int((AP_X + 1.5 - X0) / 0.75) + 1)]
    for s in (-1, 1):
        K.strip([(X0, s * LANE, 0.03), (AP_X + 1.5, s * LANE, 0.03)], 0.1, 0.03, 'line', closed=False)
        path = [(x, s * (hall_half(x) + 0.0)) for x in xs]
        verts = [(x, y, 0.0) for x, y in path] + [(x, y, H) for x, y in path]
        n = len(path)
        faces = [[k, k + 1, n + k + 1, n + k] if s < 0 else [k + 1, k, n + k, n + k + 1] for k in range(n - 1)]
        F._new(verts, faces, 'wall', merge=False)
        K.strip([(x, y - s * 0.2, 0.4) for x, y in path], 0.4, 0.8, 'bronze', closed=False)
        K.strip([(x, y - s * 0.43, 0.62) for x, y in path], 0.06, 0.08, 'line', closed=False)
        K.strip([(x, y, H) for x, y in path], 0.6, 0.3, 'silver', closed=False)
        K.strip([(x, y - s * 0.1, H + 0.2) for x, y in path], 0.14, 0.12, 'line', closed=False)
        K.strip([(x, y - s * 1.3, 0.02) for x, y in path], 0.3, 0.04, 'inlay', closed=False)
        K.strip([(x, y - s * 1.85, 0.02) for x, y in path], 0.06, 0.04, 'line', closed=False)
    for k, x in enumerate(range(38, int(AP_X) - 3, 10)):
        for s in (-1, 1):
            flow_line([(x + 4.0, s * 0.3, 0.035), (x + 2.2, s * 4.5, 0.035), (x - 2.6, s * (LANE - 2.2), 0.035)], 0.42, 'inlay')
            if k % 2 == 0:
                flow_line([(x + 5.2, s * 0.3, 0.04), (x + 3.4, s * 4.5, 0.04), (x - 1.4, s * (LANE - 2.2), 0.04)], 0.07, 'line')
    for x in (46.0, 59.0):
        for s in (-1, 1):
            K.flow_pad((x, s * (hall_half(x) - 6.6)), 4.3, style=int(x) % 5)
    K.strip([(AP_X - 0.4, -AP_R * 0.97, 0.05), (AP_X - 0.4, AP_R * 0.97, 0.05)], 0.5, 0.05, 'white', closed=False)
    K.strip([(AP_X - 1.6, -AP_R * 0.97, 0.04), (AP_X - 1.6, AP_R * 0.97, 0.04)], 0.08, 0.04, 'line', closed=False)
    hh = 21.0
    for s in (-1, 1):
        K.fin((AP_X - 1.0, s * (THROAT - 0.25), 0.0), (0, 0, 1), (-1, 0, 0), hh, 6.0, 'pale', lean=0.3, curve=2.0, rib=None)
        K.fin((AP_X - 7.5, s * (THROAT - 0.2), 0.0), (0, 0, 1), (-1, 0, 0), hh * 0.6, 4.5, 'silver', lean=0.26, curve=2.0)
        oz = AP_Z + AP_R * AP_SQ * 0.55
        K.orb((AP_X - 1.6, s * (AP_R - 0.4), oz), 0.9, light=1.0)
        K.ring_flat((AP_X - 1.6, s * (AP_R - 0.4), oz), 1.5, 0.12, 0.08, 'silver', n=32)


def build_roof():
    xs = [X0 - 2 + 1.5 * k for k in range(40)]
    rings = [[tuple(arch(x, -1 + 2 * k / 40, roof_h(x) + 1.2)) for k in range(41)] for x in xs]
    F.loft(rings, 'vault', caps=False, closed=False)
    for s, stations in ((-1, (51.0, 68.0)), (1, (42.0, 59.0, 76.0))):
        for i, x0 in enumerate(stations):
            n = 22
            pts = []
            for k in range(n + 1):
                u = k / n
                x = x0 + 9.0 * u ** 1.6
                pts.append(arch(x, s * (0.9 - 0.62 * u), roof_h(x) - 1.6 - 0.8 * math.sin(math.pi * u)))
            K.arc_band(pts, 2.0, 0.22, 'pale' if i % 2 else 'silver', (1, 0, 0))
            K.orb(tuple(pts[-1] + Vector((1.4, -s * 1.2, 0.5))), 0.5, light=0.8)
    for x in (50.0, 64.0, 78.0):
        h = roof_h(x)
        K.orb((x, 0, h - 1.2), 0.75, light=1.6)
        K.ring_flat((x, 0, h - 1.2), 1.9, 0.3, 0.06, 'silver', n=48)
    for t in (-0.46, 0.46):
        pts = [tuple(arch(x, t, roof_h(x) + 0.95)) for x in xs]
        F.sweep(pts, [(0.07, 0.07)] * len(pts), 'line', sides=4)
    n = 72
    ro = AP_R + 1.4
    ring_o = [(AP_X + 1.2, ro * math.cos(2 * math.pi * k / n), AP_Z + ro * (AP_SQ + 0.03) * math.sin(2 * math.pi * k / n)) for k in range(n)]
    ring_b = [(AP_X + 1.2, 36 * math.cos(2 * math.pi * k / n), AP_Z + 40 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    F.loft([ring_o, ring_b], 'vault', caps=False)


# ------------------------------------------------------------------ timeline
def ease_out(s, p=2.2):
    s = min(1.0, max(0.0, s))
    return 1.0 - (1.0 - s) ** p


def state(f):
    """Everything that moves, as a function of the frame number."""
    st = {}
    if f <= 14:
        q = -26.0 * (1.0 - f / 14.0) ** 1.5                 # gun-tip penetration (negative = still outside)
    elif f <= BREAK:
        q = 10.4 * ease_out((f - 14) / (BREAK - 14.0), 2.4)
    else:
        q = 10.4 + 19.0 * ease_out((f - BREAK) / 20.0, 2.0)
    st['q'] = q
    press = max(0.0, min(1.0, (f - 14) / (BREAK - 14.0))) if f <= BREAK else 0.0
    st['strain'] = press ** 0.7 if f <= BREAK else max(0.0, 1.0 - (f - BREAK) / 5.0) * 0.6
    # height of the tank's underside: level through the field, then it drops to the deck and settles
    if f <= BREAK:
        z = 4.6 + (0.04 * math.sin(f * 2.3) * press)        # it shudders under the load
        pitch = 0.6 * math.sin(f * 1.9) * press
    else:
        s = min(1.0, (f - BREAK) / 17.0)
        z = 4.6 - 3.7 * s * s
        tau = max(0.0, (f - BREAK - 17) / 24.0)
        z = max(0.9, z) + (0.55 * math.exp(-5.0 * tau) * abs(math.sin(9.0 * tau)) if s >= 1.0 else 0.0)
        pitch = (7.0 * math.sin(math.pi * s) if s < 1.0 else -3.0 * math.exp(-5.0 * tau) * math.sin(9.0 * tau))
    st['z'], st['pitch'] = z, pitch
    # the skin
    st['hole'] = 0.0
    st['pulse'] = None
    st['wobble'] = 0.0
    if f > BREAK:
        d = f - BREAK
        open_r = 4.4 * ease_out(d / 2.5, 2.0)
        close = ease_out((f - 65) / 12.0, 1.6) if f > 65 else 0.0
        st['hole'] = open_r * (1.0 - close)
        st['pulse'] = (4.4 + 3.6 * d, max(0.0, 7.0 * (1.0 - d / 7.0))) if d < 7 else None
        if 75 <= f < 82:                                   # last pulse as it seals
            st['pulse'] = (0.3 + 2.6 * (f - 75), 6.0 * (1.0 - (f - 75) / 7.0))
        st['wobble'] = -2.6 * math.exp(-d / 6.0) * math.cos(d * 0.9)
    # the rings: spin up with the strain, tighten, then snap outward and settle
    spin = sum((0.4 + 5.5 * (max(0.0, min(1.0, (k - 14) / (BREAK - 14.0))) ** 1.5 if k <= BREAK else max(0.15, 1.0 - (k - BREAK) / 14.0)))
               for k in range(f))
    st['angles'] = (spin, -1.6 * spin, 0.7 * spin)
    if f <= BREAK:
        tight = 1.0 - 0.07 * press ** 1.2
        st['scales'] = (1.0 - 0.02 * press, tight, 1.0 - 0.1 * press ** 1.2)
    else:
        d = f - BREAK
        k = 0.1 * math.exp(-d / 5.0) * math.cos(d * 0.8)
        st['scales'] = (1.0 + 0.3 * k, 1.0 + 0.8 * k, 1.0 + 1.2 * k)
    return st


CAMS = {
    'A': dict(loc=(AP_X - 50.0, -3.0, 5.0), tgt=(AP_X, 0.5, 8.4), lens=26),
    'B': dict(loc=(AP_X - 17.0, -11.5, 4.6), tgt=(AP_X - 4.0, 0.0, 6.9), lens=26),
    'C': dict(loc=(AP_X - 41.0, -4.5, 2.3), tgt=(AP_X - 21.0, 0.0, 4.4), lens=27),
    'H': dict(loc=(AP_X - 19.0, -10.5, 4.2), tgt=(AP_X - 4.5, 0.3, 7.1), lens=24),
}


def shot_for(f):
    return SHOT or ('A' if f < 34 else ('B' if f < 62 else 'C'))


def main():
    frames = []
    for part in ARGS.get('frames', '0-95').split(','):
        if '-' in part:
            a, b = part.split('-')
            frames += list(range(int(a), int(b) + 1, int(ARGS.get('step', 1))))
        else:
            frames.append(int(part))
    K.init(samples=int(ARGS.get('samples', 10)), res=RES, env=0.2, wall_h=H, warm=(0.72, 0.8, 0.95), floor_mode='dark', stars=1.5, core_gain=6.0,
           threads=int(ARGS.get('threads', 3)))
    build_hall()
    with K.layer('roof'):
        build_roof()
    K.finish()
    ap_c = Vector((AP_X, 0.0, AP_Z))
    rings = FX.Rings(ap_c, AP_R, (1.0, AP_SQ))
    mem = FX.Membrane(ap_c, AP_R, AP_SQ)
    # defenders, facing the aperture
    K.unit('carapace', (AP_X - 31.0, 8.6, 0.95), yaw=-6)
    K.unit('stinger', (AP_X - 29.0, -8.8, 0.95), yaw=7)
    K.unit('mortar_beast', (AP_X - 24.0, 13.2, 0.9), yaw=-14)
    for (x, y) in ((AP_X - 31.0, 8.6), (AP_X - 29.0, -8.8)):
        K.point((x + 3, y, 3.2), 500, col=(1.0, 0.8, 0.45), r=0.8)
    intr = FX.Intruder('bulwark')
    tent_len = intr.tip - intr.front
    # more Terrans waiting outside
    w1 = FX.Intruder('lancer')
    w1.place(AP_X + 46, 9.0, 9.0, yaw=186)
    w2 = FX.Intruder('bulwark')
    w2.place(AP_X + 70, -11.0, 3.0, yaw=176)
    w3 = FX.Intruder('condor')
    w3.place(AP_X + 60, -2.0, 19.0, yaw=180, roll=12)
    K.ghost('roof')
    K.light_orbs(0.7)
    K.sun((25, 0, 250), 0.25, col=(0.85, 0.9, 1.0), angle=30)
    for x in (52, 68, 82):
        K.point((x, 0, roof_h(x) - 5), 1800, col=(0.9, 0.93, 1.0), r=2.0)
    for x in (46, 59):
        for s in (-1, 1):
            K.point((x, s * (hall_half(x) - 6.6), 5.5), 900, col=(1.0, 0.9, 0.75), r=1.2)
    fxl = bpy.data.lights.new('fx', 'POINT')
    fxl.color = (1.0, 0.78, 0.4)
    fxl.shadow_soft_size = 1.0
    fxo = bpy.data.objects.new('fx', fxl)
    bpy.context.scene.collection.objects.link(fxo)
    cyl = bpy.data.lights.new('cy', 'POINT')
    cyl.color = (0.3, 0.8, 1.0)
    cyl.shadow_soft_size = 1.0
    cyo = bpy.data.objects.new('cy', cyl)
    bpy.context.scene.collection.objects.link(cyo)
    cam = None
    os.makedirs(OUTDIR, exist_ok=True)
    for f in frames:
        out = os.path.join(OUTDIR, f'f_{f:03d}.jpg')
        if os.path.exists(out) and not ARGS.get('force'):
            continue
        st = state(f)
        q = st['q']
        loc = intr.place(AP_X - q, 0.0, st['z'], pitch=st['pitch'])
        contact = Vector((AP_X, 0.0, st['z'] + intr.gun_z))
        tent = max(0.0, min(q + 0.6, tent_len - 0.2)) / 0.8 if f <= BREAK else 0.0
        depth = max(0.0, q + 1.0 - tent_len) if f <= BREAK else 0.0
        hullc = Vector((AP_X, 0.0, st['z'] + intr.h * 0.5))
        mem.update(hullc if depth > 0.2 else contact, depth, tent=tent, tent_at=contact, a=4.0, strain=st['strain'] if q > -0.2 else 0.0, t=f / 24.0,
                   hole=st['hole'], pulse=st['pulse'], wobble=st['wobble'])
        if tent > 0 and depth > 0.2:                        # the tent sits at gun height, not hull centre
            pass
        rings.update(st['angles'], st['scales'])
        strain = st['strain'] if q > -0.2 else 0.0
        specs = FX.breach_bolts(mem, intr, strain if f <= BREAK else strain * 1.4, seed=f // 2, n_rim=5, n_crawl=14)
        if BREAK < f < BREAK + 8:                           # the snap: arcs fly round the hole
            r2 = random.Random(f)
            for _ in range(5):
                a = r2.uniform(0, 2 * math.pi)
                specs.append((mem.rim(a), hullc + Vector((0, 4.4 * math.cos(a), 3.2 * math.sin(a))), 0.07, 0.22, 2))
        if 66 <= f <= 84:                                   # last arcs across the closing hole
            r2 = random.Random(f // 2)
            for _ in range(2 if f < 78 else 1):
                a = r2.uniform(0, 2 * math.pi)
                b = a + math.pi + r2.uniform(-0.6, 0.6)
                rr = max(0.6, st['hole']) + 0.3
                specs.append((hullc + Vector((0, rr * math.cos(a), 0.72 * rr * math.sin(a))), hullc + Vector((0, rr * math.cos(b), 0.72 * rr * math.sin(b))),
                              0.06, 0.3, 1))
            if f < 76:
                a = r2.uniform(0, 2 * math.pi)
                specs.append((mem.rim(a), intr.surface(r2), 0.07, 0.22, 1))
        if f >= 86:                                         # the defenders open up
            r2 = random.Random(f // 2)
            for (dx, dy) in ((AP_X - 26.5, 8.6), (AP_X - 24.5, -8.8)):
                specs.append((Vector((dx, dy, 2.6)), intr.surface(r2), 0.06, 0.14, 2))
        FX.dyn_bolts(specs, seed=f // 2)
        fxo.location = (AP_X - max(0.0, depth) - 2.0, 0.0, st['z'] + 2.5)
        fxl.energy = 300 + 9000 * strain + (60000 * max(0.0, 1.0 - abs(f - BREAK - 1) / 3.0) if f > BREAK else 0.0)
        cyo.location = loc + Vector((0, 0, -0.3))
        cyl.energy = 2500
        c = CAMS[shot_for(f)]
        push = 1.0
        if not SHOT:                                         # slow push-in inside each shot
            k0 = {'A': 0, 'B': 34, 'C': 62}[shot_for(f)]
            push = (f - k0) / 30.0
        lc, tg = Vector(c['loc']), Vector(c['tgt'])
        lc = lc + (tg - lc) * 0.05 * push
        if cam is not None:
            bpy.data.objects.remove(cam, do_unlink=True)
        cam = K.camera(tuple(lc), tuple(tg), lens=c['lens'])
        K.render(out, bloom_amt=float(ARGS.get('bloom', 0.8)))
        raw = out.replace('.jpg', '_raw.png')
        if os.path.exists(raw):
            os.remove(raw)


main()
