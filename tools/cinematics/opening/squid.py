"""Shot 7 of the opening film: the squid hunt (0:26 to 0:35), built into the shared space scene.

Everything is computed here in Python, frame by frame, and baked to keyframes, so any frame renders
identically on any day:
  * the squid's path (Catmull-Rom through key points chosen so the claws meet the fighters),
  * three Twin-X fighters (crossing, weaving chase, grabbed, torn apart, one escapes),
  * ten segment-rigid tentacles: each tentacle is a chain of rigid armoured segments placed along a
    curve from its root to a tip target, resampled by arc length so segments never stretch,
  * the frigate's run-in, charge ribbons and beam, the core blast and the scattering segments.

Global clock: frame = 1 + round(t * 24). Squid-local units are the model's own (scaled by K).
"""
import math
import random

import bpy
import bmesh  # noqa: F401
from mathutils import Vector, Quaternion, Matrix

import space as SP
import common as C
import forge as F
import ships as base
import arcadian_fleet as AF
import terran_fleet as T

fr = SP.fr
FPS = SP.FPS
K = 3.0                      # squid drawn 3x (body ~60 long, arms ~55 more)
FX_K = 4.5                   # the three fighters in this shot are drawn a bit larger so they read
SEG_L = 1.45                 # tentacle segment length (squid-local)
NSEG = 12                    # normal arm segments
NSEG_FEED = 15               # the two feeder arms
NARM = 10
FEEDERS = (0, 5)
GROUP_A = (0, 1, 9, 2)       # arms on the first fighter (body, three wing groups)
GROUP_B = (5, 4, 6)          # arms on the second fighter (body, front half, back half)
SPREAD = (3, 7, 8)           # arms spread wide and crackling so the shape stays readable
FLICKER = 2                  # the arm that flicks at the passing fighters

F0, F1 = fr(26.0), fr(35.0)          # 625, 841
T_CROSS = fr(27.0)                    # 649 first fighter enters
T_TURN, T_LUNGE = fr(28.0), fr(28.5)  # 673, 685
T_GRAB_A, T_TWIST = fr(30.0), fr(30.25)
T_BREAK, T_GRAB_B = fr(31.0), fr(31.5)
T_PULL_A, T_BURST_A = fr(32.0), fr(32.5)
T_RIP_B, T_LOOK = fr(33.0), fr(33.5)
T_BEAM, T_BLOW, T_PASS = fr(34.0), fr(34.25), fr(34.5)
END = fr(36.5)


# ================================================================== small maths
def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def ramp(f, a, b):
    return smooth((f - a) / float(b - a)) if b != a else (1.0 if f >= b else 0.0)


def catmull(keys, f):
    """keys: sorted [(frame, Vector)]; Catmull-Rom through them, clamped at the ends."""
    if f <= keys[0][0]:
        return keys[0][1].copy()
    if f >= keys[-1][0]:
        return keys[-1][1].copy()
    for i in range(len(keys) - 1):
        fa, pa = keys[i]
        fb, pb = keys[i + 1]
        if fa <= f <= fb:
            break
    p0 = keys[i - 1][1] if i > 0 else pa - (pb - pa)
    p3 = keys[i + 2][1] if i + 2 < len(keys) else pb + (pb - pa)
    fa0 = keys[i - 1][0] if i > 0 else fa - (fb - fa)
    fb3 = keys[i + 2][0] if i + 2 < len(keys) else fb + (fb - fa)
    t = (f - fa) / float(fb - fa)
    # tangents scaled for uneven spacing
    m1 = (pb - p0) / float(fb - fa0) * (fb - fa)
    m2 = (p3 - pa) / float(fb3 - fa) * (fb - fa)
    t2, t3 = t * t, t * t * t
    return (pa * (2 * t3 - 3 * t2 + 1) + m1 * (t3 - 2 * t2 + t) + pb * (-2 * t3 + 3 * t2) + m2 * (t3 - t2))


def yaw_quat(yaw, pitch=0.0, roll=0.0):
    return (Quaternion((0, 0, 1), yaw) @ Quaternion((0, 1, 0), -pitch) @ Quaternion((1, 0, 0), roll))


def look_quat(d, up=Vector((0, 0, 1))):
    return Vector(d).normalized().to_track_quat('X', 'Z')


# ================================================================== fast baking
def _curves(idblock):
    ad = idblock.animation_data
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        return [fc for layer in ad.action.layers for strip in layer.strips
                for bag in strip.channelbags for fc in bag.fcurves]


def bake(obj, frames, locs=None, quats=None, scales=None):
    """Key loc/quaternion/scale on every given frame (linear), quickly via foreach_set."""
    obj.rotation_mode = 'QUATERNION'
    paths = []
    if locs is not None:
        obj.location = locs[0]
        obj.keyframe_insert('location', frame=frames[0])
        paths.append(('location', 3, locs))
    if quats is not None:
        obj.rotation_quaternion = quats[0]
        obj.keyframe_insert('rotation_quaternion', frame=frames[0])
        paths.append(('rotation_quaternion', 4, quats))
    if scales is not None:
        obj.scale = scales[0]
        obj.keyframe_insert('scale', frame=frames[0])
        paths.append(('scale', 3, scales))
    curves = _curves(obj)
    for path, n, vals in paths:
        for i in range(n):
            fc = next(c for c in curves if c.data_path == path and c.array_index == i)
            fc.keyframe_points.clear()
            fc.keyframe_points.add(len(frames))
            co = []
            for f, v in zip(frames, vals):
                co += [float(f), float(v[i])]
            fc.keyframe_points.foreach_set('co', co)
            fc.keyframe_points.foreach_set('interpolation', [1] * len(frames))   # 1 = LINEAR
            fc.update()


# ================================================================== tentacle segments
def _segment_meshes(nseg, r0, r1, claw, tag):
    """Build one straight tentacle along +X and cut it into nseg rigid segment meshes, each with its
    origin at the segment's root joint. Returns [mesh] (claw joined into the last one)."""
    J = [(k * SEG_L, 0.0, 0.0) for k in range(nseg + 1)]
    with AF.gold_palette():
        base._faction('kesh')
        parts = AF.build_tentacle(J, f'Tent_{tag}', r0=r0, r1=r1, claw=claw, join=False)
        for o in parts:
            o.data.materials.clear()
            o.data.materials.append(F.zone_mat(o['zone']))
    del F.ST['parts'][-len(parts):]
    groups = [[] for _ in range(nseg)]
    for o in parts:
        xs = [(o.matrix_world @ v.co).x for v in o.data.vertices]
        if not xs:
            bpy.data.objects.remove(o)
            continue
        if max(xs) - min(xs) > 2.2 * SEG_L:       # the thread running the whole length: drop it
            bpy.data.objects.remove(o)
            continue
        cx = (max(xs) + min(xs)) / 2
        k = min(nseg - 1, max(0, int((cx + 0.02) // SEG_L)))
        groups[k].append(o)
    meshes = []
    for k, g in enumerate(groups):
        bpy.ops.object.select_all(action='DESELECT')
        for o in g:
            o.select_set(True)
        bpy.context.view_layer.objects.active = g[0]
        if len(g) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
        ob.data.transform(Matrix.Translation((-k * SEG_L, 0, 0)))
        me = ob.data
        me.name = f'TentSeg_{tag}_{k:02d}'
        bpy.data.objects.remove(ob)
        meshes.append(me)
    return meshes


def _bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return p0 * (u ** 3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t ** 3)


def chain(b, t0, tip, t1, L, nseg, wave_a, wave_ph, side, up):
    """Joint points (nseg+1) along a curve of arc length L from b (leaving along t0) to tip
    (arriving along t1), with a travelling wave that vanishes at both ends."""
    tip = Vector(tip)
    d = tip - b
    if d.length > L * 0.985:                   # out of reach: straight toward the tip
        tip = b + d.normalized() * L * 0.985
        d = tip - b
    N = 64

    def pts(h):
        p1, p2 = b + t0 * h, tip - t1 * h
        out = []
        for i in range(N + 1):
            t = i / N
            p = _bezier(b, p1, p2, tip, t)
            env = math.sin(math.pi * t)
            p = p + side * (wave_a * env * math.sin(2 * math.pi * 1.4 * t - wave_ph)) \
                  + up * (0.6 * wave_a * env * math.sin(2 * math.pi * 1.1 * t - wave_ph * 0.8 + 1.0))
            out.append(p)
        return out

    def length(ps):
        return sum((ps[i + 1] - ps[i]).length for i in range(len(ps) - 1))
    lo, hi = 0.0, L * 1.5
    ps = pts(hi)
    for _ in range(26):
        mid = (lo + hi) / 2
        ps = pts(mid)
        if length(ps) < L:
            lo = mid
        else:
            hi = mid
    ps = pts((lo + hi) / 2)
    # arc-length resample
    acc = [0.0]
    for i in range(len(ps) - 1):
        acc.append(acc[-1] + (ps[i + 1] - ps[i]).length)
    J, j = [], 0
    for k in range(nseg + 1):
        s = min(k * SEG_L, acc[-1])
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        seg = acc[j + 1] - acc[j]
        t = 0.0 if seg < 1e-9 else (s - acc[j]) / seg
        J.append(ps[j].lerp(ps[j + 1], t))
    if (J[-1] - J[-2]).length < 0.5 * SEG_L:     # curve ran short (rare): extend straight
        dd = (J[-2] - J[-3]).normalized()
        J[-1] = J[-2] + dd * SEG_L
    return J


def frames_along(J, up0):
    """Rotation of each rigid segment (+X along the segment) by parallel transport from the root."""
    qs = []
    d0 = (J[1] - J[0]).normalized()
    q = d0.to_track_quat('X', 'Z')
    # roll the root frame so its local Z leans toward up0 (the arm's outward direction)
    z = q @ Vector((0, 0, 1))
    upp = (up0 - d0 * up0.dot(d0))
    if upp.length > 1e-4:
        upp.normalize()
        ang = z.angle(upp)
        if (z.cross(upp)).dot(d0) < 0:
            ang = -ang
        q = Quaternion(d0, ang) @ q
    prev = d0
    qs.append(q.copy())
    for k in range(1, len(J) - 1):
        dk = (J[k + 1] - J[k]).normalized()
        q = prev.rotation_difference(dk) @ q
        prev = dk
        qs.append(q.copy())
    return qs


# ================================================================== the sequence
class SquidHunt:
    def __init__(self, S):
        self.S = S
        self.frames = list(range(F0 - 24, END + 1))
        self.rnd = random.Random(707)
        self.paths()
        self.build_squid()
        self.build_fighters()
        self.pose_arms()
        self.bake_all()
        self.effects()
        self.frigate()
        S.squid = self

    # ------------------------------------------------------------ paths
    def fighter_base(self, i):
        """Free-flight path of fighter i (world), before any grab."""
        Q = SP.SQUID_ZONE
        xline = Q.x - 72.0
        z0 = Q.z + 6.0 + i * 3.0
        t_in = T_CROSS + 4 * i
        pts = {}
        y = -70.0
        for f in range(F0 - 24, END + 1):
            if f < t_in:
                yy = -70.0 - 140.0 * (t_in - f) / FPS
            else:
                v = 140.0 if f < fr(28.2) else (110.0 if f < T_GRAB_A else 78.0)
                if i == 1 and f >= T_BREAK:
                    v = 78.0 + 95.0 * ramp(f, T_BREAK, T_BREAK + 8)       # flat out
                if i == 0 and f >= T_GRAB_B:
                    v = 120.0
                y += v / FPS
                yy = y
            wx = 9.0 * math.sin(2 * math.pi * f / 30.0 + i * 2.1) * ramp(f, fr(28.2), fr(28.8))
            wz = 6.0 * math.sin(2 * math.pi * f / 22.0 + i * 1.3) * ramp(f, fr(28.2), fr(28.8))
            up = 0.0
            if i == 0 and f >= T_GRAB_B:                                  # escapes upward
                up = 150.0 * ((f - T_GRAB_B) / FPS) ** 1.5
            pts[f] = Vector((xline + wx - (6 if i == 1 else 0), Q.y + yy, z0 + wz + up))
        return pts

    def paths(self):
        self.fb = [self.fighter_base(i) for i in range(3)]
        Q = SP.SQUID_ZONE
        A = self.fb[2][T_GRAB_A]
        B0 = self.fb[1][T_BREAK]
        B = self.fb[1][T_GRAB_B]
        reachA, reachB = 47.0, 52.0
        keys = [(F0 - 24, Q + Vector((4, 0, 0))), (F0, Q), (T_TURN, Q + Vector((-5, 0, 0))),
                (T_LUNGE + 2, Q + Vector((-8, 6, 0))),
                (T_GRAB_A, Vector((A.x + 1.0, A.y - reachA, A.z - 6.0))),
                (T_BREAK, Vector((B0.x + 2.0, B0.y - 50.0, B0.z - 4.0))),
                (T_GRAB_B, Vector((B.x + 2.0, B.y - reachB, B.z - 4.0)))]
        last = keys[-1][1]
        keys += [(T_LOOK, last + Vector((-2, 52, 0))), (T_BEAM, last + Vector((-6, 64, 0))),
                 (END, last + Vector((-14, 80, 0)))]
        self.sq_keys = keys
        self.sq_pos = {f: catmull(keys, f) for f in self.frames}
        # heading: yaw 180 (-X) drifting, snap round to +Y, follow travel, turn to look at the frigate
        yaws = {}
        for f in self.frames:
            y = math.pi + math.radians(-90) * ramp(f, T_TURN, T_TURN + 13)
            y += math.radians(8) * math.sin(math.pi * ramp(f, T_TURN + 8, T_TURN + 20))     # overshoot
            y += math.radians(-6) * math.sin(2 * math.pi * f / 40.0) * ramp(f, T_LUNGE, T_LUNGE + 12) * \
                (1 - ramp(f, T_GRAB_A, T_GRAB_A + 10))
            y += math.radians(38) * ramp(f, T_LOOK, T_BEAM)              # turns to look at the frigate
            yaws[f] = y
        self.yaw = yaws
        self.roll = {f: math.radians(-28) * math.sin(math.pi * ramp(f, T_TURN, T_TURN + 16)) +
                     math.radians(4) * math.sin(2 * math.pi * f / 70.0) for f in self.frames}
        self.pitch = {f: math.radians(3) * math.sin(2 * math.pi * f / 90.0) for f in self.frames}
        self.M = {}
        for f in self.frames:
            q = yaw_quat(self.yaw[f], self.pitch[f], self.roll[f])
            self.M[f] = Matrix.Translation(self.sq_pos[f]) @ q.to_matrix().to_4x4() @ Matrix.Scale(K, 4)
        self.Minv = {f: m.inverted() for f, m in self.M.items()}

    def local(self, f, p):
        return self.Minv[f] @ Vector(p)

    def world(self, f, p):
        return self.M[f] @ Vector(p)

    # ------------------------------------------------------------ squid body
    def build_squid(self):
        J = [(AF.SQUID_BASE_X + k * 2.0, AF.SQUID_BASE_R, 0) for k in range(3)]
        ship, core = AF.squid_ship('Squid', joints=[J, [(x, -y, z) for x, y, z in J]])
        for nm in list(ship['tentacles']) + [ship['claw_arc']]:
            ob = bpy.data.objects.get(nm)
            if ob:
                bpy.data.objects.remove(ob)
        self.ship = ship
        self.core_l = Vector(core)
        ship.visible_shadow = True
        # arm segments: normal and feeder meshes, shared between arms
        self.mesh_n = _segment_meshes(NSEG, 0.8, 0.22, 0.9, 'n')
        self.mesh_f = _segment_meshes(NSEG_FEED, 1.0, 0.32, 1.4, 'f')
        self.arms = []
        for i in range(NARM):
            feed = i in FEEDERS
            meshes = self.mesh_f if feed else self.mesh_n
            segs = []
            for k, me in enumerate(meshes):
                ob = bpy.data.objects.new(f'SquidArm{i:02d}_{k:02d}', me)
                SP.link(ob)
                ob.parent = ship
                segs.append(ob)
            phi = 2 * math.pi * (i + 0.25) / NARM
            o = Vector((0, math.cos(phi), math.sin(phi)))
            b = Vector((AF.SQUID_BASE_X, 0, 0)) + o * AF.SQUID_BASE_R
            self.arms.append(dict(i=i, feed=feed, segs=segs, o=o, b=b, L=len(meshes) * SEG_L,
                                  side=Vector((0, -o.z, o.y)), ph=self.rnd.uniform(0, 6.28),
                                  len=self.rnd.uniform(0.75, 0.9)))
        # glows: core flash, stern drive burst
        self.core_glow = C.uv_sphere('SquidCoreGlow', 1.0, seg=(20, 10),
                                     mat=SP.BP._halo_mat('SquidCoreGlowM', (1.0, 0.65, 0.2), 2.5))
        self.core_glow.parent = ship
        self.core_glow.location = self.core_l
        SP.key_scale(self.core_glow, [(F0 - 24, 1.2), (T_TURN, 1.2), (T_TURN + 3, 3.6), (T_TURN + 12, 1.4),
                                      (T_BEAM, 1.4), (T_BLOW - 2, 4.0)], 'LINEAR')
        self.core_glow.visible_shadow = False
        drive = C.uv_sphere('SquidDrive', 1.0, seg=(20, 10), mat=SP.BP._halo_mat('SquidDriveM', (1.0, 0.5, 0.1), 4.0))
        drive.parent = ship
        drive.location = (-18.5, 0, 0)
        SP.key_scale(drive, [(F0 - 24, (0.9, 0.7, 0.7)), (T_LUNGE - 1, (0.9, 0.7, 0.7)), (T_LUNGE + 2, (4.5, 1.3, 1.3)),
                             (T_LUNGE + 18, (3.0, 1.0, 1.0)), (T_GRAB_A + 6, (1.1, 0.8, 0.8))], 'LINEAR')
        drive.visible_shadow = False

    # ------------------------------------------------------------ fighters
    def build_fighters(self):
        S = self.S
        self.fx = []
        wname = S.twinx_wings
        for i in range(3):
            c = SP.copy_tree(S.twinx_src, f'SqX{i}')
            c.scale = (FX_K,) * 3
            for ob in [c] + list(c.children_recursive):
                ob.hide_render = False
            wings = next(ch for ch in c.children if ch.name.startswith(wname))
            trail = C.uv_sphere(f'SqX{i}Trail', 1.0, seg=(12, 6), mat=SP.emit(f'SqX{i}TrailM', (0.3, 0.65, 1.0), 14.0),
                                scale=(2.2, 0.07, 0.07))
            trail.parent = c
            trail.location = (-2.9, 0, 0)
            trail.visible_shadow = False
            self.fx.append(dict(obj=c, wings=wings))
        # fighter world transforms: free flight, then held in a claw
        held = {2: (T_GRAB_A, Vector((AF.SQUID_BASE_X + 9.0, 0.0, 5.0)), T_GRAB_A + 26),
                1: (T_GRAB_B, Vector((AF.SQUID_BASE_X + 9.5, 0.0, -5.0)), T_GRAB_B + 22)}
        for i, fd in enumerate(self.fx):
            path = self.fb[i]
            locs, quats = [], []
            qprev = None
            hold = held.get(i)
            for f in self.frames:
                if hold and f >= hold[0]:
                    g, H, g2 = hold
                    if f == g:
                        fd['grab_local'] = self.local(g, path[g])
                        fd['grab_q'] = (yaw_quat(self.yaw[g], self.pitch[g], self.roll[g]).inverted() @ qprev)
                    pl = fd['grab_local'].lerp(H, ramp(f, g, g2))
                    # wrenched sideways and shaken, engines still burning
                    twist = Quaternion((0, 0, 1), math.radians(75) * ramp(f, g, g + 6)) @ \
                        Quaternion((1, 0, 0), math.radians(10) * math.sin(f * 1.7))
                    qs = yaw_quat(self.yaw[f], self.pitch[f], self.roll[f])
                    locs.append(self.world(f, pl))
                    q = qs @ twist @ fd['grab_q']
                else:
                    p = path[f]
                    v = path[min(f + 1, END)] - path[max(f - 1, F0 - 24)]
                    acc = path[min(f + 2, END)] - 2 * p + path[max(f - 2, F0 - 24)]
                    bank = max(-1.2, min(1.2, -acc.x * 0.25))
                    q = look_quat(v) @ Quaternion((1, 0, 0), bank)
                    locs.append(p)
                if qprev is not None and q.dot(qprev) < 0:
                    q = -q
                quats.append(q)
                qprev = q
            fd['locs'] = dict(zip(self.frames, locs))
            fd['quats'] = dict(zip(self.frames, quats))
            fd['hold'] = hold

    # ------------------------------------------------------------ arm poses
    def tip_pose(self, a, f, name, **kw):
        """(tip, t0, t1, wave) of a named pose, squid-local."""
        X = Vector((1, 0, 0))
        b, o, L = a['b'], a['o'], a['L']
        if name == 'idle':
            tip = b + X * L * 0.9 * a['len'] + o * L * 0.16
            return tip, (X * 0.8 + o * 0.6).normalized(), (X + o * 0.3).normalized(), 1.6
        if name == 'bundle':
            tip = Vector((AF.SQUID_BASE_X + L * 0.93, 0, 0)) + o * 0.9
            return tip, (X * 0.9 + o * 0.25).normalized(), X, 0.35
        if name == 'fan':
            tip = b + X * L * 0.62 + o * L * 0.52
            return tip, (X * 0.7 + o * 0.5).normalized(), (X * 0.35 + o).normalized(), 0.9
        if name == 'spread':
            tip = b + X * L * 0.3 + o * L * 0.82
            return tip, (X * 0.4 + o).normalized(), (o - X * 0.2).normalized(), 1.4
        if name == 'target':
            tip = kw['tip_fn'](f)
            to = (tip - b)
            return tip, (X * 0.7 + o * 0.45).normalized(), (to.normalized() * 0.6 + X * 0.4).normalized(), 0.6
        raise ValueError(name)

    def arm_schedule(self, i):
        """[(frame, pose, kwargs)] key poses; between keys the poses blend smoothly."""
        sch = [(F0 - 24, 'idle', {}), (T_TURN, 'idle', {}), (T_TURN + 12, 'bundle', {}), (T_LUNGE + 18, 'bundle', {}),
               (T_GRAB_A - 10, 'fan', {})]
        if i == FLICKER:
            sch = [(F0 - 24, 'idle', {}), (T_CROSS + 3, 'idle', {}),
                   (T_CROSS + 8, 'target', dict(tip_fn=lambda f: self._clamp(i, self.local(f, self.fb[1][f]), 0.8))),
                   (T_CROSS + 18, 'idle', {}), (T_TURN, 'idle', {}), (T_TURN + 12, 'bundle', {}),
                   (T_LUNGE + 18, 'bundle', {}), (T_GRAB_A - 10, 'fan', {})]
        if i in GROUP_A:
            j = GROUP_A.index(i)
            sch += [(T_GRAB_A, 'target', dict(tip_fn=lambda f, j=j: self.part_local('A', j, f))),
                    (T_BURST_A + 2, 'target', dict(tip_fn=lambda f, j=j: self.part_local('A', j, f))),
                    (T_BURST_A + 14, 'spread', {}), (END, 'spread', {})]
        elif i in GROUP_B:
            j = GROUP_B.index(i)
            sch += [(T_GRAB_A + 8, 'spread', {}), (T_BREAK + 2, 'fan', {}),
                    (T_GRAB_B, 'target', dict(tip_fn=lambda f, j=j: self.part_local('B', j, f))),
                    (T_RIP_B + 6, 'target', dict(tip_fn=lambda f, j=j: self.part_local('B', j, f))),
                    (T_RIP_B + 18, 'spread', {}), (END, 'spread', {})]
        else:
            sch += [(T_GRAB_A + 4, 'spread', {}), (END, 'spread', {})]
        return sch

    def _clamp(self, i, p, k):
        a = self.arms[i]
        d = p - a['b']
        if d.length > a['L'] * k:
            return a['b'] + d.normalized() * a['L'] * k
        return p

    # positions of the held pieces, squid-local (claw tips follow these)
    def part_offsets(self, which, j, f):
        """Offset (squid-local) of piece j of a held fighter from the fighter's centre."""
        if which == 'A':
            if j == 0:
                return Vector((-0.5, 0, 0))
            a = 2 * math.pi * (j - 1) / 3 + 0.4 + math.pi / 3
            u = Vector((0.15, math.cos(a), math.sin(a)))
            pull = 0.55 + 7.5 * ramp(f, T_PULL_A, T_BURST_A)
            return u * pull
        if j == 0:
            return Vector((0, 0, -0.4))
        s = 1 if j == 1 else -1
        return Vector((s * (0.7 + 6.5 * ramp(f, T_RIP_B - 4, T_RIP_B + 4)), 0, 0.3 * s))

    def part_local(self, which, j, f):
        fd = self.fx[2 if which == 'A' else 1]
        c = self.local(f, fd['locs'][f])
        return c + self.part_offsets(which, j, f)

    def pose_arms(self):
        self.J = {}          # (arm, frame) -> joints (squid-local)
        for a in self.arms:
            i = a['i']
            sch = self.arm_schedule(i)
            nseg = len(a['segs'])
            for f in self.frames:
                if f <= sch[0][0]:
                    k0 = k1 = 0
                    w = 0.0
                elif f >= sch[-1][0]:
                    k0 = k1 = len(sch) - 1
                    w = 0.0
                else:
                    k0 = max(k for k in range(len(sch)) if sch[k][0] <= f)
                    k1 = min(k0 + 1, len(sch) - 1)
                    w = smooth((f - sch[k0][0]) / float(max(1, sch[k1][0] - sch[k0][0])))
                pa = self.tip_pose(a, f, sch[k0][1], **sch[k0][2])
                pb = self.tip_pose(a, f, sch[k1][1], **sch[k1][2])
                tip = pa[0].lerp(pb[0], w)
                t0 = pa[1].lerp(pb[1], w).normalized()
                t1 = pa[2].lerp(pb[2], w).normalized()
                wa = pa[3] + (pb[3] - pa[3]) * w
                ph = a['ph'] + 2 * math.pi * f / (26.0 if i not in SPREAD else 18.0)
                self.J[(i, f)] = chain(a['b'], t0, tip, t1, a['L'], nseg, wa, ph, a['side'], a['o'])

    # ------------------------------------------------------------ bake
    def bake_all(self):
        fr_ = self.frames
        ship = self.ship
        bake(ship, fr_, [self.sq_pos[f] for f in fr_],
             [yaw_quat(self.yaw[f], self.pitch[f], self.roll[f]) for f in fr_])
        ship.scale = (K, K, K)
        self.seg_world_last = {}
        for a in self.arms:
            i = a['i']
            # per-frame transport for the whole arm
            qs_all = {f: frames_along(self.J[(i, f)], a['o']) for f in fr_}
            for k, ob in enumerate(a['segs']):
                locs = [self.J[(i, f)][k] for f in fr_]
                quats, qprev = [], None
                for f in fr_:
                    q = qs_all[f][k]
                    if qprev is not None and q.dot(qprev) < 0:
                        q = -q
                    quats.append(q)
                    qprev = q
                bake(ob, fr_, locs, quats)
        for fd in self.fx:
            bake(fd['obj'], fr_, [fd['locs'][f] for f in fr_], [fd['quats'][f] for f in fr_])
            fd['obj'].scale = (FX_K,) * 3
            w = fd['wings']
            w.rotation_mode = 'XYZ'
            stop = fd['hold'][0] if fd['hold'] else END
            SP.key_rot(w, [(F0 - 24, (0, 0, 0)), (stop, (360 * 5 * (stop - F0 + 24) / 216.0, 0, 0))], 'LINEAR')
        bpy.context.scene.frame_set(F0)

    # ------------------------------------------------------------ tearing the fighters apart
    def split_fighter_A(self):
        """At 0:32 the first fighter's wings come off in three directions; its core bursts at 0:32.5."""
        fd = self.fx[2]
        wings = fd['wings']
        bpy.context.scene.frame_set(T_PULL_A)
        pieces = SP.split_mesh(wings, lambda c: int(((math.atan2(c.z, c.y) - 0.4) % (2 * math.pi)) // (2 * math.pi / 3)),
                               [f'SqXA_Wing{j}' for j in range(3)])
        SP.show(wings, F0 - 24, T_PULL_A - 1)
        for j, p in enumerate(pieces):
            p.parent = None
            locs, quats = [], []
            q0 = wings.matrix_world.to_quaternion()
            spin = Vector((self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1))).normalized()
            frames = list(range(T_PULL_A, END + 1))
            vel = None

            def held(f):
                return self.world(f, self.local(f, fd['locs'][f]) + self.part_offsets('A', j + 1, f))
            for f in frames:
                if f <= T_BURST_A + 2:
                    pw = held(f)
                    q = Quaternion(spin, 0.05 * (f - T_PULL_A)) @ q0
                    last, lastf, lastq = pw, f, q
                else:
                    if vel is None:
                        vel = (last - held(lastf - 1)) + (last - fd['locs'][lastf]).normalized() * 1.4
                    pw = last + vel * (f - lastf)
                    q = Quaternion(spin, 0.3 * (f - lastf)) @ lastq
                locs.append(pw)
                quats.append(q)
            p.scale = (FX_K,) * 3
            bake(p, frames, locs, quats)
            p.scale = (FX_K,) * 3
            SP.show(p, T_PULL_A, END)
        # core bursts violet, body gone
        pb = fd['locs'][T_BURST_A]
        SP.violet_boom(pb, T_BURST_A, 7.0, life=0.8, light=1.5e5)
        SP.spark_stream(pb, T_BURST_A, T_BURST_A + 1, (0.75, 0.45, 1.0), Vector((0, 0, 0)), 711, n=40, size=0.4,
                        speed=60, life=0.8)
        SP.show(fd['obj'], F0 - 24, T_BURST_A, tree=False)
        for ch in fd['obj'].children_recursive:
            if ch is not wings and wings not in ch.children_recursive and ch not in wings.children_recursive:
                SP.show(ch, F0 - 24, T_BURST_A, tree=False)

    def split_fighter_B(self):
        """At 0:33 the second fighter is ripped in two; its core bursts."""
        fd = self.fx[1]
        c = fd['obj']
        g = T_RIP_B - 4
        bpy.context.scene.frame_set(g)
        cm = c.matrix_world.copy()
        meshes = [o for o in [c] + list(c.children_recursive) if o.type == 'MESH']
        for s, nm in ((1, 'Front'), (-1, 'Back')):
            root = bpy.data.objects.new(f'SqXB_{nm}', None)
            SP.link(root)
            parts = []
            for o in meshes:
                ow = o.matrix_world.copy()
                ps = SP.split_mesh(o, lambda cc, s=s: 0 if (cc.x * s) >= 0 else 1, [f'SqXB_{nm}_{o.name}', f'_x{nm}{o.name}'])
                for extra in ps[1:]:
                    bpy.data.objects.remove(extra)
                p = ps[0]
                p.parent = root
                p.matrix_parent_inverse = Matrix.Identity(4)
                p.matrix_basis = cm.inverted() @ ow
                parts.append(p)
            frames = list(range(g, END + 1))
            locs, quats = [], []
            spin = Vector((0, 1, s * 0.3)).normalized()
            qg = yaw_quat(self.yaw[g], self.pitch[g], self.roll[g])
            q0 = cm.to_quaternion()
            jj = 1 if s > 0 else 2

            def held(f):
                return self.world(f, self.local(f, fd['locs'][f]) + self.part_offsets('B', jj, f))
            vel = None
            for f in frames:
                if f <= T_RIP_B + 6:
                    pw = held(f)
                    q = yaw_quat(self.yaw[f], self.pitch[f], self.roll[f]) @ qg.inverted() @ \
                        Quaternion(spin, s * 0.04 * (f - g)) @ q0
                    last, lastf, lastq = pw, f, q
                else:
                    if vel is None:
                        vel = (last - held(lastf - 1)) * 1.6
                    pw = last + vel * (f - lastf)
                    q = Quaternion(spin, s * 0.3 * (f - lastf)) @ lastq
                locs.append(pw)
                quats.append(q)
            bake(root, frames, locs, quats)
            root.scale = (FX_K,) * 3
            # the split moment shows the fighter's centre at its held spot; the halves start there
            SP.show(root, g + 1, END)
        SP.show(c, F0 - 24, g)
        pb = fd['locs'][T_RIP_B]
        SP.violet_boom(pb, T_RIP_B, 6.0, life=0.8, light=1.2e5)
        SP.spark_stream(pb, T_RIP_B, T_RIP_B + 1, (0.75, 0.45, 1.0), Vector((0, 0, 0)), 712, n=34, size=0.4,
                        speed=55, life=0.8)

    # ------------------------------------------------------------ effects
    def claw_tip_world(self, i, f):
        return self.world(f, self.J[(i, f)][-1])

    def bolt_between(self, pa, pb, f0, f1, seed, width=0.16, col=(1.0, 0.7, 0.25), strength=14.0):
        rnd = random.Random(seed)
        with AF.gold_palette():
            base._faction('kesh')
            m = F.mark()
            AF.bolt(pa, pb, rnd, width=width, jag=0.22, depth=4, branches=1)
            ob = base._join(F.since(m), SP._uid('SqBolt'))
        ob.data.materials.clear()
        ob.data.materials.append(SP.emit(SP._uid('SqBoltM'), col, strength))
        ob.visible_shadow = False
        SP.show(ob, f0, f1)
        return ob

    def effects(self):
        S = self.S
        self.split_fighter_A()
        self.split_fighter_B()
        # gold lightning between the feeder claws while the arms fan open (0:29)
        for n_, f in enumerate(range(T_LUNGE + 14, T_GRAB_A, 2)):
            self.bolt_between(self.claw_tip_world(0, f), self.claw_tip_world(5, f), f, f + 1, 900 + n_, width=0.3)
        # crackling between the spread arms (0:31 - 0:34)
        for n_, f in enumerate(range(T_GRAB_A + 6, T_BLOW, 3)):
            for a_, b_ in ((3, 7), (7, 8)):
                if (n_ + a_) % 2 == 0:
                    self.bolt_between(self.claw_tip_world(a_, f), self.claw_tip_world(b_, f), f, f + 2,
                                      1000 + n_ * 10 + a_, width=0.22)
        # blue bolts fired backward by the fleeing fighters glance off the squid (0:29)
        for n_ in range(7):
            f = T_LUNGE + 10 + n_ * 4
            fi = n_ % 3
            p0 = self.fb[fi][f]
            hit = self.world(f + 4, Vector((self.rnd.uniform(-6, 4), self.rnd.uniform(-3, 3), self.rnd.uniform(1, 4))))
            d = hit - p0
            bo = C.uv_sphere(SP._uid('XBolt'), 1.0, seg=(8, 6), mat=SP.emit(SP._uid('XBoltM'), (0.35, 0.7, 1.0), 25.0),
                             scale=(2.6, 0.18, 0.18))
            bo.rotation_mode = 'QUATERNION'
            bo.rotation_quaternion = look_quat(d)
            SP.key_loc(bo, [(f, p0), (f + 4, hit)], 'LINEAR')
            SP.show(bo, f, f + 4)
            bo.visible_shadow = False
            SP.spark_stream(hit, f + 4, f + 5, (0.4, 0.75, 1.0), (hit - self.sq_pos[f + 4]).normalized(), 720 + n_,
                            n=8, size=0.3, speed=40, life=0.4)
        # a dead stingray tumbling past the camera at the start
        with AF.gold_palette():
            st, _ = AF.stingray_fighter('SqDeadSting')
        st.scale = (FX_K,) * 3
        p0 = self.world(F0, Vector((-28, -9, 6)))
        p1 = self.world(F0 + 30, Vector((-34, 14, 3)))
        SP.key_loc(st, [(F0 - 6, p0), (F0 + 30, p1)], 'LINEAR')
        SP.key_rot(st, [(F0 - 6, (20, 0, 40)), (F0 + 30, (200, 120, 260))], 'LINEAR')
        SP.show(st, F0 - 6, F0 + 30)
        # far-off battle flashes
        rnd = random.Random(730)
        for n_ in range(7):
            f = F0 + rnd.randint(0, 200)
            p = Vector((rnd.uniform(-150, 120), rnd.uniform(-60, 250), rnd.uniform(-40, 60)))
            (SP.gold_boom if n_ % 2 else SP.blue_boom)(p, f, rnd.uniform(10, 18), life=0.8)

    # ------------------------------------------------------------ frigate: charge, beam, run through
    def frigate(self):
        S = self.S
        fg = S.obj['frigate']
        fz = SP.SQUID_ZONE + Vector((-260, 60, 30))
        target = self.sq_pos[T_PASS]
        start = fz + Vector((5, -2, 0))
        d = (target - start).normalized()
        fire_at = target - d * 75
        SP.key_loc(fg, [(fr(25.5), fz), (T_BREAK, start), (T_BREAK + 20, start + d * 25), (T_BEAM, fire_at),
                        (T_PASS, target + Vector((0, 0, 6))), (END, target + d * 170 + Vector((0, 0, 14)))], 'BEZIER')
        yaw = math.degrees(math.atan2(d.y, d.x))
        SP.key_rot(fg, [(1, (0, 0, 0)), (T_BREAK, (0, 0, 0)), (T_BREAK + 22, (0, 0, yaw)), (END, (0, 0, yaw))])
        # blue lines brighten
        for sl in fg.material_slots:
            m = sl.material
            if not m or not m.name.endswith('_neon'):
                continue
            e = [n for n in m.node_tree.nodes if n.type == 'EMISSION'][-1]
            s0 = e.inputs['Strength'].default_value
            for f, k in ((1, 1.0), (T_BREAK, 1.0), (T_BREAK + 16, 2.2), (T_BEAM + 6, 2.6), (END, 1.6)):
                e.inputs['Strength'].default_value = s0 * k
                e.inputs['Strength'].keyframe_insert('default_value', frame=f)
        # nose point and size
        bpy.context.scene.frame_set(T_BEAM)
        nose_l = max((v.co for v in fg.data.vertices), key=lambda c: c.x).copy()
        xs = [v.co.x for v in fg.data.vertices]
        length = max(xs) - min(xs)
        # charge ribbons coiling round the frigate (0:33)
        tw = SP.beam_twist(Vector((min(xs), 0, 0)), Vector((1, 0, 0)), 'FrigateCharge', SP.BLUE,
                           [(T_RIP_B, 0.0), (T_RIP_B + 14, length * 1.05), (T_BEAM + 6, length * 1.05),
                            (T_BEAM + 8, 0.0)], T_RIP_B, T_BEAM + 8, radius=6.5, pitch=9.0, width=0.3,
                           turns_per_s=2.0, length=length * 1.1)
        tw.parent = fg
        # the beam: on at 0:34 for six frames, from the nose to the squid's middle
        nose_w = fg.matrix_world @ nose_l
        hit = self.world(T_BEAM + 3, self.core_l + Vector((-6, 0, 0)))
        dd = (hit - nose_w)
        bm = SP.beam(nose_w, dd.normalized(), 'FrigateBeam', SP.BLUE, (0.75, 0.9, 1.0), 1.6,
                     [(T_BEAM, 2.0, 1.0), (T_BEAM + 2, dd.length + 4, 1.0), (T_BLOW + 2, dd.length + 4, 1.1),
                      (T_BLOW + 4, dd.length + 4, 0.0)], strength=12.0, glow=3.0)
        mw = bm.matrix_world.copy()
        bm.parent = fg
        bm.matrix_parent_inverse = fg.matrix_world.inverted()
        SP.impact_flare(hit, dd.normalized(), T_BEAM + 2, T_BLOW, (0.4, 0.75, 1.0), 9.0, 'SquidBeamSplash')
        # core blast, mantle cracks open, arm segments scatter like beads
        cw = self.world(T_BLOW, self.core_l)
        SP.boom(cw, T_BLOW, 26.0, hot=(1.0, 0.85, 0.45), cool=(0.6, 0.25, 0.03), life=1.6, light=2e6)
        SP.gold_boom(cw + Vector((0, 0, 4)), T_BLOW + 3, 40.0, life=2.0)
        SP.spark_stream(cw, T_BLOW, T_BLOW + 6, (1.0, 0.75, 0.3), Vector((0, 0, 0)), 740, n=16, size=0.8,
                        speed=110, life=1.3)
        self.scatter()

    def scatter(self):
        """At the core blast the body breaks into chunks and every arm segment flies free."""
        ship = self.ship
        frames = list(range(T_BLOW, END + 1))
        cw = self.world(T_BLOW, self.core_l)
        bpy.context.scene.frame_set(T_BLOW)
        chunks = SP.split_mesh(ship, lambda c: (int((math.atan2(c.z, c.y) + math.pi) // (math.pi / 3)) % 6) +
                               (6 if c.x < -8 else 0), [f'SquidChunk{j}' for j in range(12)])
        rnd = random.Random(741)
        for j, ch in enumerate(chunks):
            if not len(ch.data.polygons):
                bpy.data.objects.remove(ch)
                continue
            mw = ship.matrix_world.copy()
            vs = list(ch.data.vertices)[::max(1, len(ch.data.vertices) // 50)]
            cen = sum((mw @ v.co for v in vs), Vector()) / len(vs)
            v = (cen - cw).normalized() * rnd.uniform(25, 45) / FPS
            spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
            q0 = mw.to_quaternion()
            # rotate about the chunk's own centre: bake object origin at the ship origin moving with it
            locs, quats = [], []
            for f in frames:
                q = Quaternion(spin, 0.03 * (f - T_BLOW)) @ q0
                off = q @ (q0.inverted() @ (mw.translation - cen))
                locs.append(cen + v * (f - T_BLOW) + off)
                quats.append(q)
            ch.scale = (K, K, K)
            bake(ch, frames, locs, quats)
            ch.scale = (K, K, K)
            SP.show(ch, T_BLOW + 1, END)
        SP.show(ship, F0 - 24, T_BLOW)
        # arm segments: keep their last pose, then drift outward and tumble
        for a in self.arms:
            for k, ob in enumerate(a['segs']):
                mw0 = self.M[T_BLOW]
                pl = self.J[(a['i'], T_BLOW)][k]
                pl1 = self.J[(a['i'], T_BLOW - 1)][k]
                p0 = mw0 @ pl
                vel = (p0 - self.M[T_BLOW - 1] @ pl1) * 0.6 + (p0 - cw).normalized() * rnd.uniform(14, 30) / FPS
                q0 = yaw_quat(self.yaw[T_BLOW], self.pitch[T_BLOW], self.roll[T_BLOW]) @ \
                    frames_along(self.J[(a['i'], T_BLOW)], a['o'])[k]
                spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
                w = rnd.uniform(0.04, 0.12)
                fly = bpy.data.objects.new(ob.name + '_free', ob.data)
                SP.link(fly)
                locs = [p0 + vel * (f - T_BLOW) for f in frames]
                quats = [Quaternion(spin, w * (f - T_BLOW)) @ q0 for f in frames]
                fly.scale = (K, K, K)
                bake(fly, frames, locs, quats)
                fly.scale = (K, K, K)
                SP.show(fly, T_BLOW + 1, END)
                SP.show(ob, F0 - 24, T_BLOW)

    # ------------------------------------------------------------ cameras
    def cam_rel(self, f, off, look, lens):
        """Camera offset in the squid's yaw-only frame (world units), smoothed over a few frames."""
        acc_p, acc_t = Vector(), Vector()
        n = 0
        for df in (-2, -1, 0, 1, 2):
            g = max(self.frames[0], min(self.frames[-1], f + df))
            q = Quaternion((0, 0, 1), self.yaw[g])
            acc_p += self.sq_pos[g] + q @ Vector(off)
            acc_t += self.sq_pos[g] + q @ Vector(look)
            n += 1
        return (f, acc_p / n, acc_t / n, lens)

    def camera(self, sid):
        keys = []
        if sid == '07a':
            for f in range(fr(26), fr(31), 2):
                keys.append(self.cam_rel(f, (-120, -38, 30), (64, 0, 0), 24))
        elif sid == '07b':
            for f in range(fr(31), fr(32), 2):
                w = ramp(f, fr(31), fr(32) - 1)
                off = Vector((-120, -38, 30)).lerp(Vector((-10, -150, 22)), w)
                keys.append(self.cam_rel(f, off, (28, 0, 0), 24))
        elif sid == '07c':
            for f in range(fr(32), fr(34), 2):
                keys.append(self.cam_rel(f, (44, -140, 12), (30, 0, 0), 28))
        elif sid == '07d':
            for f in range(fr(34), fr(35), 2):
                w = ramp(f, fr(34), fr(34.6))
                off = Vector((44, -140, 12)).lerp(Vector((60, -260, 70)), w)
                tl = ramp(f, fr(34.75), fr(35))
                look = Vector((20, 0, 0)).lerp(Vector((120, -200, -420)), tl)
                keys.append(self.cam_rel(f, off, look, 24))
        f_last = {'07a': fr(31) - 1, '07b': fr(32) - 1, '07c': fr(34) - 1, '07d': fr(35) - 1}[sid]
        if keys and keys[-1][0] != f_last:
            k = keys[-1]
            keys.append((f_last,) + k[1:])
        return keys
