"""Arcadian boarders forcing the Terran triangle force field of the hangar bay door (design study).

Everything is a stateless function of time t (seconds), so any frame can be rendered on its own.

  --mode=frames --times=0.4,1.0,1.3 [--cam=A|B|H|auto] [--full=1]   stills (drafts)
  --mode=clip   [--f0=0 --f1=87]                                     frames for the draft clip
  --mode=game   [--t=1.45]                                           the same breach from the game camera

Timeline: approach -> touch (T_TOUCH) -> press / flex / strain -> break (T_BREAK) -> push through -> settle -> seal.
"""
import math
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import terran_interior_kit as K  # noqa: E402

A = K.args()
OUT = A.get('out', '/home/user/work/terran-interiors/breach')
MODE = A.get('mode', 'frames')
RES = tuple(int(v) for v in A.get('res', '960x540').split('x'))
FPS = 24.0
T_TOUCH, T_BREAK = 0.5, 1.25
DUR = 3.625                       # 87 frames
GOLD = (1.0, 0.36, 0.02)
HOTC = (0.3, 0.68, 1.0)


def sstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def press(t):
    """0..1 how hard the attacker leans on the field (only before the break)."""
    if t <= T_TOUCH:
        return 0.0
    s = min((t - T_TOUCH) / (T_BREAK - T_TOUCH), 1.0)
    return (0.25 * s + 0.75 * sstep(s)) * (1 + 0.05 * math.sin(t * 61.0) * s)


def rodrigues(p, axis, ang):
    """Rotate rows of p (n,3) around a unit axis."""
    c, s = math.cos(ang), math.sin(ang)
    return p * c + np.cross(axis, p) * s + np.outer(p @ axis, axis) * (1 - c)


# ====================================================================== the field
class Field:
    """Triangle field in the plane y = origin.y (u = +x, v = +z). Inside of the ship is -y."""
    DIRS = [(0, 2), (1, 1), (1, -1), (0, -2), (-1, -1), (-1, 1)]     # lattice steps (row, col), 60 deg apart

    def __init__(self, name, origin, w, h, tri, inside, contact, R, depth, sigma, strength, edge, alpha, gap,
                 seed, t_clear, t_seal=(0.15, 1.3), shard_speed=1.0, hot_gain=1.5):
        self.hot_gain = hot_gain
        self.o = np.array(origin, float)
        self.w, self.h, self.tri, self.hh = w, h, tri, tri * math.sqrt(3) / 2
        self.inside = inside or (lambda a, b: True)
        self.c = np.array(contact, float)             # plane coords of the contact point
        self.R, self.depth, self.sigma, self.gap = R, depth, sigma, gap
        self.t_clear = t_clear
        rnd = random.Random(seed)
        tris, rr = [], []
        rows = int(math.ceil(h / self.hh))
        cols = int(math.ceil(w / (tri / 2))) + 1
        for r in range(rows):
            for c in range(-1, cols):
                up = (r + c) % 2 == 0
                x0 = c * tri / 2
                if up:
                    t3 = [(x0, r * self.hh), (x0 + tri, r * self.hh), (x0 + tri / 2, (r + 1) * self.hh)]
                else:
                    t3 = [(x0, (r + 1) * self.hh), (x0 + tri / 2, r * self.hh), (x0 + tri, (r + 1) * self.hh)]
                cx = sum(p[0] for p in t3) / 3
                cy = sum(p[1] for p in t3) / 3
                if not (0 <= cx <= w and 0 <= cy <= h) or not self.inside(cx, cy):
                    continue
                tris.append([(min(max(a, 0), w), min(max(b, 0), h)) for a, b in t3])
                rr.append(rnd.random() ** 1.6)
        W = np.array(tris, float)                      # (Nw, 3, 2)
        cen = W.mean(axis=1)
        d = np.linalg.norm(cen - self.c, axis=1)
        ang = np.arctan2(cen[:, 1] - self.c[1], cen[:, 0] - self.c[0])
        Rr = R * (1 + 0.13 * np.sin(ang * 3 + 1.0) + 0.09 * np.sin(ang * 7 + 2.0))
        brk = d < Rr
        self.nw = len(W)
        self.wd = d
        self.brk = brk
        rn = np.array([rnd.random() for _ in range(self.nw)])
        self.tc = np.where(brk, T_BREAK + 0.032 * d + 0.05 * rn, 1e9)
        # sealing order: rim first, spiralling inwards, one by one
        idx = [i for i in range(self.nw) if brk[i]]
        idx.sort(key=lambda i: -(d[i] + 0.25 * math.sin(ang[i] * 2) + 0.4 * rn[i]))
        self.ts = np.full(self.nw, 1e9)
        t0, t1 = t_clear + t_seal[0], t_clear + t_seal[1]
        for k, i in enumerate(idx):
            self.ts[i] = t0 + (t1 - t0) * k / max(len(idx) - 1, 1)
        self.t_sealed = t1 + 0.2
        # shards: every breaking triangle cracks into four irregular pieces
        S, sp, sr = [], [], []
        for i in idx:
            a, b, c = W[i]
            f = [rnd.uniform(0.32, 0.68) for _ in range(3)]
            ab, bc, ca = a + (b - a) * f[0], b + (c - b) * f[1], c + (a - c) * f[2]
            for t3 in ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)):
                S.append(t3)
                sp.append(i)
                sr.append(rr[i])
        S = np.array(S, float).reshape(-1, 3, 2)
        self.ns = len(S)
        self.sp = np.array(sp, int)
        sc = S.mean(axis=1)
        sd = np.linalg.norm(sc - self.c, axis=1)
        rad = (sc - self.c) / np.maximum(sd, 0.2)[:, None]
        n = self.ns
        R_ = lambda lo, hi: np.array([rnd.uniform(lo, hi) for _ in range(n)])
        near = np.clip(1 - sd / (R * 1.2), 0, 1)
        self.sv = np.stack([rad[:, 0] * R_(2, 8) + R_(-1.5, 1.5),
                            -(R_(7, 13) + near * R_(4, 12)) * shard_speed,
                            rad[:, 1] * R_(2, 7) + R_(0, 3.5)], axis=1)
        ax = np.stack([R_(-1, 1), R_(-1, 1), R_(-1, 1)], axis=1)
        self.sax = ax / np.linalg.norm(ax, axis=1)[:, None]
        self.sw = R_(4, 15) * np.where(R_(0, 1) < 0.5, -1, 1)
        self.slife = R_(0.65, 1.45)
        self.base = np.concatenate([self.to3(W), self.to3(S)])        # (P, 3, 3) world
        self.r = np.array(rr + sr, float)
        self.np_ = len(self.base)
        self.rn = np.array([rnd.random() for _ in range(self.np_)])
        self._mesh(name, strength, edge, alpha)
        self.rnd = rnd
        self._strain_paths()
        self._sparks()

    # -------------------------------------------------------------- helpers
    def to3(self, p2):
        p2 = np.asarray(p2, float)
        out = np.zeros(p2.shape[:-1] + (3,))
        out[..., 0] = self.o[0] + p2[..., 0]
        out[..., 1] = self.o[1]
        out[..., 2] = self.o[2] + p2[..., 1]
        return out

    def bulge_amp(self, t):
        if t <= T_BREAK:
            return self.depth * press(t)
        tau = t - T_BREAK
        return self.depth * math.exp(-tau * 6.5) * math.cos(tau * 27.0)

    def bulge(self, p3, t):
        """Inward (-y) displacement of world points p3 (...,3)."""
        dx = p3[..., 0] - (self.o[0] + self.c[0])
        dz = p3[..., 2] - (self.o[2] + self.c[1])
        return self.bulge_amp(t) * np.exp(-(dx * dx + dz * dz) / (2 * self.sigma ** 2))

    def lat(self, r, c):
        return (c * self.tri / 2, r * self.hh)

    def lat_ok(self, r, c):
        a, b = self.lat(r, c)
        return -0.01 <= a <= self.w + 0.01 and -0.01 <= b <= self.h + 0.01 and self.inside(a, max(b - 0.3, 0))

    def lat_near(self, a, b):
        r = int(round(b / self.hh))
        c = int(round(a / (self.tri / 2)))
        if (r + c) % 2:
            c += 1
        return r, c

    def walk(self, rnd, start, steps, straight=0.75, away=None):
        """Random walk over lattice vertices, biased away from the contact point. Returns plane coords."""
        away = self.c if away is None else away
        r, c = start
        pts = [self.lat(r, c)]

        def gain(k):
            a, b = self.lat(r + self.DIRS[k][0], c + self.DIRS[k][1])
            return math.hypot(a - away[0], b - away[1])
        ks = sorted(range(6), key=gain, reverse=True)
        k = ks[0] if rnd.random() < 0.5 else ks[1] if rnd.random() < 0.7 else ks[2]
        for _ in range(steps):
            if rnd.random() > straight:
                k = max(((k + 1) % 6, (k - 1) % 6), key=lambda q: gain(q) + rnd.uniform(0, self.tri))
            r2, c2 = r + self.DIRS[k][0], c + self.DIRS[k][1]
            if not self.lat_ok(r2, c2):
                break
            r, c = r2, c2
            pts.append(self.lat(r, c))
        return pts

    # -------------------------------------------------------------- meshes
    def _mesh(self, name, strength, edge, alpha):
        P = self.np_
        me = bpy.data.meshes.new(name + '_faces')
        me.from_pydata([(0, 0, 0)] * (3 * P), [], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(P)])
        for an in ('r', 'hot', 'life'):
            me.attributes.new(an, 'FLOAT', 'FACE')
        m = bpy.data.materials.new(name + '_face')
        t = K.NT(m)
        ar = t.n('ShaderNodeAttribute', attribute_name='r').outputs['Fac']
        ah = t.n('ShaderNodeAttribute', attribute_name='hot').outputs['Fac']
        al = t.n('ShaderNodeAttribute', attribute_name='life').outputs['Fac']
        colm = t.n('ShaderNodeMixRGB')
        colm.inputs[1].default_value = (*K.NEON, 1)
        colm.inputs[2].default_value = (*HOTC, 1)
        t.link(t.m('MINIMUM', t.m('MULTIPLY', ah, 0.5), 0.75), colm.inputs[0])
        em = t.n('ShaderNodeEmission')
        t.link(colm.outputs[0], em.inputs[0])
        base = t.m('MULTIPLY', t.m('ADD', 0.35, ar), strength)
        t.link(t.m('MULTIPLY', t.m('MULTIPLY', base, t.m('ADD', 1.0, t.m('MULTIPLY', ah, self.hot_gain))), al), em.inputs[1])
        mix = t.n('ShaderNodeMixShader')
        a0 = t.m('ADD', alpha[0], t.m('MULTIPLY', ar, alpha[1] - alpha[0]))
        t.link(t.m('MULTIPLY', t.m('ADD', a0, t.m('MULTIPLY', ah, 0.22), clamp=True), al), mix.inputs[0])
        t.link(t.n('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        t.link(em.outputs[0], mix.inputs[2])
        t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
        me.materials.append(m)
        self.mf = me
        me = bpy.data.meshes.new(name + '_edges')
        ef = []
        for i in range(P):
            n = 6 * i
            ef += [(n + j, n + (j + 1) % 3, n + 3 + (j + 1) % 3, n + 3 + j) for j in range(3)]
        me.from_pydata([(0, 0, 0)] * (6 * P), [], ef)
        for an in ('hot', 'life'):
            me.attributes.new(an, 'FLOAT', 'FACE')
        m = bpy.data.materials.new(name + '_edge')
        t = K.NT(m)
        ah = t.n('ShaderNodeAttribute', attribute_name='hot').outputs['Fac']
        al = t.n('ShaderNodeAttribute', attribute_name='life').outputs['Fac']
        colm = t.n('ShaderNodeMixRGB')
        colm.inputs[1].default_value = (*[0.6 * c + 0.4 * k for c, k in zip(K.NEON, K.CYAN)], 1)
        colm.inputs[2].default_value = (0.5, 0.82, 1.0, 1)
        t.link(t.m('MULTIPLY', ah, 0.8, clamp=True), colm.inputs[0])
        em = t.n('ShaderNodeEmission')
        t.link(colm.outputs[0], em.inputs[0])
        t.link(t.m('MULTIPLY', edge, t.m('ADD', 1.0, t.m('MULTIPLY', ah, self.hot_gain * 1.07))), em.inputs[1])
        mix = t.n('ShaderNodeMixShader')
        t.link(al, mix.inputs[0])
        t.link(t.n('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        t.link(em.outputs[0], mix.inputs[2])
        t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
        me.materials.append(m)
        self.me = me
        self.objs = []
        for me in (self.mf, self.me):
            ob = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(ob)
            ob.visible_shadow = False
            K.NOFOG.append(ob)
            self.objs.append(ob)
        # line meshes: strain (white-blue), lightning + sparks (gold)
        self.lines = {}
        for key, col, st in (('strain', (0.55, 0.85, 1.0), float(A.get('strain_e', 20))),
                             ('gold', GOLD, float(A.get('gold_e', 6)))):
            me = bpy.data.meshes.new(f'{name}_{key}')
            me.materials.append(K._emit(f'{name}_{key}', col, st))
            ob = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(ob)
            ob.visible_shadow = False
            K.NOFOG.append(ob)
            self.lines[key] = me

    @staticmethod
    def _tubes(me, segs):
        """segs: list of (p0, p1, radius) -> three-sided tubes."""
        me.clear_geometry()
        if not segs:
            me.update()
            return
        vs, fs = [], []
        for p0, p1, r in segs:
            p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
            d = p1 - p0
            L = np.linalg.norm(d)
            if L < 1e-5:
                continue
            d /= L
            a = np.cross(d, (0.0, 0.3, 1.0))
            a /= max(np.linalg.norm(a), 1e-6)
            b = np.cross(d, a)
            n = len(vs)
            for p in (p0, p1):
                for k in range(3):
                    an = k * 2.0944
                    vs.append(tuple(p + (a * math.cos(an) + b * math.sin(an)) * r))
            fs += [(n + k, n + (k + 1) % 3, n + 3 + (k + 1) % 3, n + 3 + k) for k in range(3)]
        me.from_pydata(vs, [], fs)
        me.update()

    # -------------------------------------------------------------- strain lines + sparks (precomputed)
    def _strain_paths(self):
        rnd = self.rnd
        self.strain = []
        for k in range(22):
            s = T_TOUCH + 0.04 + (T_BREAK - T_TOUCH - 0.04) * (k / 21.0) ** 0.7
            st = self.lat_near(self.c[0] + rnd.uniform(-1.3, 1.3), self.c[1] + rnd.uniform(-1.3, 1.3))
            self.strain.append((s, self.walk(rnd, st, rnd.randint(7, 15), 0.82)))
        for k in range(14):                              # the break itself throws cracks out from the rim
            an = rnd.uniform(0, 6.283)
            st = self.lat_near(self.c[0] + math.cos(an) * self.R, max(self.c[1] + math.sin(an) * self.R, 0))
            self.strain.append((T_BREAK + rnd.uniform(0, 0.12), self.walk(rnd, st, rnd.randint(6, 12), 0.85)))

    def _sparks(self):
        rnd = self.rnd
        self.sparks = []
        for k in range(260):
            burst = k < 170
            t0 = T_BREAK + (rnd.uniform(0, 0.16) if burst else rnd.uniform(0.1, max(self.t_clear - T_BREAK, 0.3)))
            an = rnd.uniform(0, 6.283)
            rr = self.R * (rnd.uniform(0.1, 1.0) if burst else rnd.uniform(0.75, 1.0))
            p = self.to3((self.c[0] + math.cos(an) * rr, max(self.c[1] + math.sin(an) * rr * 0.8, 0.2)))
            sp = rnd.uniform(6, 24) if burst else rnd.uniform(3, 12)
            v = np.array([math.cos(an) * rnd.uniform(1, 9), -sp, math.sin(an) * rnd.uniform(1, 8) + rnd.uniform(0, 4)])
            self.sparks.append((t0, p, v, rnd.uniform(0.25, 0.8), 'gold' if rnd.random() < 0.6 else 'strain'))

    # -------------------------------------------------------------- per-frame update
    def update(self, t, hull=None):
        """hull: (centre a, centre b, half-width, half-height) of the attacker cross-section in the field
        plane while it spans the plane, else None."""
        frame = int(round(t * FPS))
        frnd = np.random.RandomState(1000 + frame)
        P, nw = self.np_, self.nw
        out = self.base.copy()
        hot = np.zeros(P)
        life = np.ones(P)
        pr = press(t)
        d = self.wd
        # ---- whole triangles: flex with the bulge
        out[:nw, :, 1] -= self.bulge(out[:nw], t)
        flick = 0.82 + 0.36 * frnd.rand(nw)
        after = math.exp(-max(t - T_BREAK, 0) * 3.5) if t > T_BREAK else pr
        hot[:nw] = 1.7 * after * np.exp(-d * d / (2 * (self.sigma * 1.15) ** 2)) * flick
        for tk, amp in ((T_TOUCH, 1.0), (0.74, 0.7), (0.93, 0.8), (1.07, 0.9), (1.17, 1.0), (T_BREAK, 2.4)):
            if t > tk:
                front = (t - tk) * 27.0
                hot[:nw] += amp * np.clip(1 - np.abs(d - front) / 1.7, 0, 1) * math.exp(-(t - tk) * 2.0)
        # the lip of the open hole stays hot and flickers
        opened = sstep((t - T_BREAK) / 0.1) * (1 - sstep((t - self.t_clear) / 0.5))
        hot[:nw] += opened * np.clip(1 - (d - self.R) / 3.0, 0, 1) * (0.9 + 0.8 * frnd.rand(nw)) * (~self.brk)
        # breaking triangles: shake and glow before they go
        pre = np.clip((t - (self.tc[:nw] - 0.3)) / 0.3, 0, 1) * self.brk
        hot[:nw] += 1.6 * pre
        shake = (0.05 * pr + 0.16 * pre)[:, None] * (frnd.rand(nw, 3) - 0.5) * 2 * self.brk[:, None]
        out[:nw, :, 1] += shake
        gone = self.brk & (t >= self.tc[:nw]) & (t < self.ts[:nw])
        life[:nw][gone] = 0
        # sealing: replacement triangles flip in around one edge
        for i in np.nonzero(self.brk & (t >= self.ts[:nw]))[0]:
            tau = t - self.ts[i]
            s = min(tau / 0.17, 1.0)
            e = 1 - (1 - s) ** 3
            ang = math.radians(118) * (1 - e) - math.radians(9) * math.sin(s * math.pi) * (1 - s)
            p = out[i]
            k = int(self.rn[i] * 3)
            a, b = p[k], p[(k + 1) % 3]
            axis = (b - a) / np.linalg.norm(b - a)
            q = rodrigues(p - a, axis, ang)
            if q[(k + 2) % 3][1] > 0:               # always swing in from the hangar side
                q = rodrigues(p - a, axis, -ang)
            out[i] = q + a
            life[i] = min(1.0, 0.25 + tau / 0.06)
            hot[i] += 2.6 * math.exp(-tau * 6.0)
        # ---- shards
        if self.ns:
            sb = self.base[nw:]
            tc = self.tc[self.sp]
            tau = t - tc
            live = (tau >= 0) & (tau < self.slife)
            tt = np.clip(tau, 0, None)
            cen = sb.mean(axis=1)
            cen0 = cen.copy()
            cen0[:, 1] -= self.depth * np.exp(-((cen[:, 0] - self.o[0] - self.c[0]) ** 2 +
                                                (cen[:, 2] - self.o[2] - self.c[1]) ** 2) / (2 * self.sigma ** 2))
            kd = 1.1
            trav = (1 - np.exp(-kd * tt)) / kd
            pos = cen0 + self.sv * trav[:, None]
            pos[:, 2] -= 0.5 * 7.0 * tt * tt
            pos[:, 2] = np.maximum(pos[:, 2], self.o[2] + 0.12)
            fr = np.clip(tt / self.slife, 0, 1)
            sc = 1 - 0.35 * fr
            for j in np.nonzero(live)[0]:
                q = rodrigues(sb[j] - cen[j], self.sax[j], self.sw[j] * tt[j]) * sc[j]
                out[nw + j] = q + pos[j]
            life[nw:] = np.where(live, (1 - fr ** 1.6), 0)
            hot[nw:] = 2.6 * np.exp(-tt * 4.5) + 0.35
        # ---- write
        dead = life <= 0
        out[dead] = self.o + np.array([0, 0, -60.0])
        cen = out.mean(axis=1, keepdims=True)
        inner = cen + (out - cen) * (1 - self.gap)
        self.mf.vertices.foreach_set('co', inner.reshape(-1))
        self.mf.attributes['r'].data.foreach_set('value', self.r)
        self.mf.attributes['hot'].data.foreach_set('value', hot)
        self.mf.attributes['life'].data.foreach_set('value', life)
        self.mf.update()
        self.me.vertices.foreach_set('co', np.concatenate([out, inner], axis=1).reshape(-1))
        self.me.attributes['hot'].data.foreach_set('value', np.repeat(hot, 3))
        self.me.attributes['life'].data.foreach_set('value', np.repeat(life, 3))
        self.me.update()
        self._lines(t, frame, hull)

    def _surf(self, pts2, t, off=0.05):
        p = self.to3(pts2)
        p[..., 1] -= self.bulge(p, t) + off
        return p

    def _lines(self, t, frame, hull):
        strain, gold = [], []
        # strain lines racing along the seams
        for s, pts in self.strain:
            head = (t - s) * 30.0
            if head <= 0 or head > len(pts) + 6:
                continue
            p3 = self._surf(pts, t)
            for k in range(len(pts) - 1):
                age = head - k
                if 0 < age <= 6:
                    a, b = p3[k], p3[k + 1]
                    if age < 1:
                        b = a + (b - a) * age
                    strain.append((a, b, 0.085 * (1 - age / 7.0)))
        # gold lightning crawling out from the attacker (re-struck every two frames)
        rnd = random.Random(77 + frame // 2)
        pr = press(t)
        bolts = []
        if T_TOUCH < t <= T_BREAK + 0.06:
            for k in range(3 + int(pr * 6)):
                st = self.lat_near(self.c[0] + rnd.uniform(-1.6, 1.6), self.c[1] + rnd.uniform(-1.4, 1.4))
                bolts.append((None, self.walk(rnd, st, 1 + int(rnd.uniform(0.4, 1.0) * (1 + pr * 7)), 0.45)))
        elif hull is not None:
            ha, hb, hw, hh_ = hull
            for k in range(6):
                an = rnd.uniform(-0.5, 3.64)
                hp = (ha + math.cos(an) * hw, max(hb + math.sin(an) * hh_, 0.3))
                st = self.lat_near(self.c[0] + math.cos(an) * (self.R + 1.2), max(self.c[1] + math.sin(an) * (self.R + 1.2), 0))
                bolts.append((hp, self.walk(rnd, st, rnd.randint(1, 3), 0.45)))
        elif self.t_clear <= t < self.t_clear + 0.35:
            for k in range(3):
                an = rnd.uniform(0, 3.14)
                st = self.lat_near(self.c[0] + math.cos(an) * (self.R + 1), self.c[1] + math.sin(an) * (self.R + 1))
                bolts.append((None, self.walk(rnd, st, rnd.randint(1, 3), 0.45)))
        for hp, pts in bolts:
            if hp is not None:
                pts = [hp] + pts
            fine = []
            for a, b in zip(pts[:-1], pts[1:]):
                n = 3
                for k in range(n):
                    f = k / n
                    j = 0.0 if k == 0 else 0.2
                    fine.append((a[0] + (b[0] - a[0]) * f + rnd.uniform(-j, j), a[1] + (b[1] - a[1]) * f + rnd.uniform(-j, j)))
            fine.append(pts[-1])
            p3 = self._surf(fine, t, off=0.09)
            if hp is not None:
                p3[0, 1] = self.o[1] - 0.3
            n = len(p3)
            for k in range(n - 1):
                gold.append((p3[k], p3[k + 1], 0.075 * (1 - 0.75 * k / n)))
        # sparks
        for t0, p, v, lf, key in self.sparks:
            tau = t - t0
            if 0 < tau < lf:
                trav = (1 - math.exp(-1.6 * tau)) / 1.6
                q = p + v * trav + np.array([0, 0, -4.0 * tau * tau])
                if q[2] < self.o[2] + 0.05:
                    continue
                tail = q - v * 0.03 * math.exp(-1.6 * tau)
                (gold if key == 'gold' else strain).append((tail, q, 0.03 * (1 - tau / lf) + 0.008))
        self._tubes(self.lines['strain'], strain)
        self._tubes(self.lines['gold'], gold)


# ====================================================================== the attacker
class Attacker:
    def __init__(self, kind, x, y_field, depth, hover=0.9, end_centre=13.5, t_move=1.55):
        new = K.tank(kind, (0, 0, 0), rz=0, faction='alien')
        lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
        bpy.context.view_layer.update()
        for o in new:
            if o.type == 'MESH':
                for c in o.bound_box:
                    w = o.matrix_world @ Vector(c)
                    lo = Vector(map(min, lo, w))
                    hi = Vector(map(max, hi, w))
        self.lo, self.hi = lo, hi
        print('ATTACKER BBOX', kind, tuple(lo), tuple(hi), flush=True)
        self.nose, self.tail = hi.x, -lo.x
        self.root = bpy.data.objects.new('Attacker', None)
        bpy.context.scene.collection.objects.link(self.root)
        for o in new:
            if o.parent is None:
                o.parent = self.root
        self.root.rotation_mode = 'XYZ'
        self.x, self.yf, self.depth, self.hover = x, y_field, depth, hover
        self.travel = end_centre + self.nose - depth
        self.t_move = t_move
        self.t_clear = next(k / 200.0 for k in range(200, 2000) if self.nose_y(k / 200.0) + self.nose + self.tail < y_field - 0.3)
        self.glow = K.point('AttGlow', (0, 0, 0), 0, GOLD, r=1.2)
        self.under = K.point('AttUnder', (0, 0, 0), 0, GOLD, r=1.5)

    def nose_y(self, t):
        if t <= T_TOUCH:
            return self.yf + 12.0 * (1 - t / T_TOUCH) ** 1.5 + 0.1
        if t <= T_BREAK:
            return self.yf - self.depth * press(t) + 0.1
        s = min((t - T_BREAK) / self.t_move, 1.0)
        e = 1 - (1 - s ** 1.25) ** 2
        return self.yf - self.depth - self.travel * e

    def update(self, t):
        ny = self.nose_y(t)
        s = min(max((t - T_BREAK) / self.t_move, 0), 1.0)
        land = sstep((s - 0.55) / 0.4)
        z = self.hover * (1 - land) + 0.12 * math.sin(t * 7.0) * (1 - land)
        z += 0.18 * math.exp(-max(s - 0.95, 0) * 30) * math.sin(max(s - 0.95, 0) * 60) if s > 0.95 else 0
        pitch = math.radians(5.0) * math.sin(min(s / 0.8, 1.0) * math.pi) * (1 if s > 0 else 0)
        pr = press(t)
        jit = 0.05 * pr * math.sin(t * 173.0) if t < T_BREAK else 0.0
        cy = ny + self.nose
        self.root.location = (self.x + jit, cy, z)
        self.root.rotation_euler = (0, pitch, math.radians(-90))
        self.glow.location = (self.x, ny - 0.4, z + 2.2)
        self.under.location = (self.x, cy, max(z, 0.2) + 0.5)
        return ny, cy, z

    def hull(self, t, origin):
        """Cross-section at the field plane (plane coords) while the hull spans it."""
        ny = self.nose_y(t)
        if t > T_BREAK and ny < self.yf - 0.5 and ny + self.nose + self.tail > self.yf:
            z = self.root.location[2]
            return (self.x - origin[0], z + (self.hi.z + self.lo.z) / 2 - origin[2],
                    (self.hi.y - self.lo.y) / 2 * 0.92, (self.hi.z - self.lo.z) / 2 * 0.9)
        return None


# ====================================================================== hangar scene
def build_hangar(full):
    import terran_hangar as H
    K.E.update(neon=1.0, cyan=1.0, orange=1.8, white=1.0)
    K.MATDEF['neon'] = lambda n: K._emit(n, (0.012, 0.19, 1.0), 4.5)
    K.MATDEF['neon_dim'] = lambda n: K._emit(n, (0.012, 0.19, 1.0), 2.0)
    K.MATDEF['slot'] = lambda n: K._emit(n, (0.2, 0.5, 1.0), 4.0)
    K.MATDEF['alarm'] = lambda n: K._emit(n, (1.0, 0.3, 0.03), 1.0)
    sc, cam = K.reset(samples=int(A.get('samples', 8)), exposure=float(A.get('exposure', 0.6)),
                      threads=int(A.get('threads', 3)))
    if full:
        H.outside(sc)
    else:
        K.space_world(sc, nebula=0.5)
        sun = bpy.data.lights.new('Sun', 'SUN')
        sun.energy, sun.color, sun.angle = 5.0, (1.0, 0.93, 0.85), math.radians(1.5)
        o = bpy.data.objects.new('Sun', sun)
        sc.collection.objects.link(o)
        o.rotation_euler = (math.radians(-64), 0, math.radians(14))
    H.shell()
    H.ribs()
    H.ceiling()
    H.gallery()
    H.bay_door()
    H.floor_marks()
    if full:
        H.crane()
        H.props()
        H.detail()
    L, W2 = H.LEN, H.DOOR_W2
    bpy.data.objects['Sun'].data.energy = float(A.get('sun', 2.2))
    # alarm beacons on the door frame and the last ribs
    y0 = L - 3.56
    for s in (-1, 1):
        for z in (6.0, 10.0, 14.0):
            K.box('dark', (s * (W2 + 1.5), y0 - 0.1, z), (1.3, 0.3, 0.9))
            K.box('alarm', (s * (W2 + 1.5), y0 - 0.28, z), (1.0, 0.08, 0.55))
        for x in (6.5, 15.5):
            K.box('dark', (s * x, y0 - 0.1, H.DOOR_H + 1.3), (2.4, 0.3, 0.8))
            K.box('alarm', (s * x, y0 - 0.28, H.DOOR_H + 1.3), (2.0, 0.08, 0.45))
    K.flush()
    for n in ('BayField_faces', 'BayField_edges'):
        ob = bpy.data.objects.get(n)
        if ob:
            if ob in K.NOFOG:
                K.NOFOG.remove(ob)
            bpy.data.objects.remove(ob)
    # parked tanks in the bays nearest the door + their lights
    kinds = ['lancer', 'bulwark', 'javelin', 'longbow', 'outrider', 'bulwark']
    i = 0
    for yb in (H.RIBS[-2], H.RIBS[-3]) + ((H.RIBS[-4],) if full else ()):
        for s in (-1, 1):
            yc = yb + 7.5
            K.tank(kinds[i % 6], (s * 18.0, yc, 0.0), rz=(0 if s < 0 else 180) + (i * 37 % 7 - 3))
            i += 1
            K.spot('Bay', (s * 26.0, yc, 8.2), (s * 17.5, yc, 0), 5200, (0.78, 0.9, 1.0), angle=100, blend=0.6, r=0.5)
            K.area('Wash', (s * 29.5, yc, 10.2), (1.0, 9.0), 900, (0.25, 0.5, 1.0), rot=(0, s * 150, 0), spread=140)
    yf = L + 0.5
    # defenders facing the door
    for kind, x, dy, rz in (('bulwark', 9.5, -7.0, 128), ('lancer', -13.2, -7.0, 70), ('bulwark', -14.0, -20.5, 72),
                            ('lancer', 10.5, -24.0, 104)):
        K.tank(kind, (x, yf + dy, 0), rz=rz)
        K.spot('Head', (x * 0.93, yf + dy + 3.0, 2.3), (0, yf, 3.0), 700, (0.8, 0.9, 1.0), angle=42, blend=0.7, r=0.15)
    # more boarders queueing outside
    K.tank('darter', (-9.5, yf + 19, 2.2), rz=-84, faction='alien')
    K.tank('stinger', (10.5, yf + 26, 3.0), rz=-97, faction='alien')

    def inside(a, b):
        return abs(a - W2) + b < W2 + H.DOOR_H - H.DOOR_CH
    contact = (W2 + 0.0, 2.9)
    depth = 2.3
    att = Attacker('carapace', 0.0, yf, depth)
    fld = Field('BayField', (-W2, yf, 0), 2 * W2, H.DOOR_H, 2.3, inside, contact, R=float(A.get('R', 4.2)),
                depth=depth, sigma=2.8, strength=float(A.get('field', 0.7)), edge=1.5, alpha=(0.05, 0.3), gap=0.055,
                seed=1, t_clear=att.t_clear)
    print('T_CLEAR', att.t_clear, 'SEALED', fld.t_sealed, 'pieces', fld.np_, 'shards', fld.ns, flush=True)
    flare = K.point('Flare', (0, yf - 1.2, 2.9), 0, (0.6, 0.85, 1.0), r=0.8)
    alarms = [K.spot('Alarm', (s * 15, L - 6, 17.5), (s * 6, L - 14, 0), 0, (1.0, 0.3, 0.04), angle=95, blend=0.8, r=0.6)
              for s in (-1, 1)]
    alarms += [K.area('AlarmW', (s * (W2 + 1.5), L - 4.2, 10), (1.0, 9.0), 0, (1.0, 0.3, 0.04), rot=(90, 0, 0), spread=160)
               for s in (-1, 1)]
    ceil = [(o, o.data.energy) for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith(('Ceil', 'Bay'))]
    fglow = bpy.data.objects.get('FieldGlow')
    am = K.mat('alarm').node_tree.nodes
    aem = next(n for n in am if n.type == 'EMISSION')

    def update(t):
        ny, cy, z = att.update(t)
        fld.update(t, att.hull(t, fld.o))
        pr = press(t)
        tb = t - T_BREAK
        flash = math.exp(-tb * 7.0) if tb >= 0 else 0.0
        fr = random.Random(int(round(t * FPS)))
        flare.data.energy = 2200 * pr * fr.uniform(0.8, 1.2) + 22000 * flash
        inside_amt = sstep((yf + 2 - ny) / 6.0)
        att.glow.data.energy = (8000 * pr + 6000 * (1 if tb >= 0 else 0)) * fr.uniform(0.8, 1.2)
        att.under.data.energy = 3500 * inside_amt
        # alarm: off until contact, then a hard two-per-second pulse
        al = 0.0
        if t > T_TOUCH + 0.12:
            ph = ((t - T_TOUCH - 0.12) * 2.4) % 1.0
            al = 0.12 + 0.88 * max(0.0, 1 - ph * 1.8) ** 1.5
        aem.inputs[1].default_value = 0.4 + 14.0 * al
        for k, o in enumerate(alarms):
            o.data.energy = (16000 if k < 2 else 4000) * al
        # main lights sag while the field fights, drop to emergency level when it breaks
        dim = 1.0 - 0.3 * pr * fr.uniform(0.6, 1.0)
        if tb >= 0:
            dim = 0.34 + 0.12 * math.exp(-tb * 3) * fr.uniform(0, 1)
        for o, e in ceil:
            o.data.energy = e * dim
        if fglow:
            hole = 1.0
            fglow.data.energy = 14000 * hole * (1 + 0.5 * pr + 0.8 * flash)
    return sc, cam, update, dict(yf=yf, att=att, fld=fld)


def camera(cam, name, t, yf):
    tb = t - T_BREAK
    shake = 0.0
    if tb >= 0:
        shake = 0.16 * math.exp(-tb * 5.0)
    elif t > T_TOUCH:
        shake = 0.02 * press(t)
    r = random.Random(int(round(t * FPS)) + 5)
    sx, sz = r.uniform(-shake, shake), r.uniform(-shake, shake)
    if name == 'A':        # low and close on the contact point, pushing in
        s = t / 1.7
        loc = Vector((-11.2 + 1.0 * s, yf - 9.6 + 1.2 * s, 2.0))
        tgt = Vector((1.2, yf - 0.8, 3.5))
        lens = 24
    elif name == 'B':      # among the defenders as it comes through
        s = (t - 1.6) / 2.0
        loc = Vector((10.2 - 0.6 * s, yf - 30.5 - 1.2 * s, 3.9))
        tgt = Vector((-0.5, yf - 6.0, 3.7))
        lens = 30
    else:                  # hero
        loc = Vector((-11.3, yf - 9.9, 1.85))
        tgt = Vector((1.5, yf - 1.1, 3.9))
        lens = 22
    K.look(cam, loc + Vector((sx, 0, sz)), tgt + Vector((sx * 0.5, 0, sz * 0.5)), lens=lens)


CUT = 1.625        # shot A -> shot B


def still(sc, cam, update, info, t, name, tag, depth=False):
    update(t)
    camera(cam, name if name != 'auto' else ('A' if t < CUT else 'B'), t, info['yf'])
    raw = os.path.join(OUT, '_raw', tag + '.png')
    K.render(sc, raw, RES, depth_far=130.0 if depth else None)
    return K.post(raw, os.path.join(OUT, tag + '.jpg'), haze=float(A.get('haze', 0.4)) if depth else 0,
                  scatter=float(A.get('scatter', 0.2)) if depth else 0, haze_col=(0.08, 0.25, 0.6),
                  bloom=float(A.get('bloom', 0.85)), thresh=float(A.get('thresh', 0.7)))


def main():
    full = A.get('full', '0') == '1'
    if MODE == 'game':
        return game()
    sc, cam, update, info = build_hangar(full)
    sc.render.use_persistent_data = True
    if MODE == 'frames':
        for ts in A.get('times', '1.0').split(','):
            t = float(ts)
            still(sc, cam, update, info, t, A.get('cam', 'auto'), '%s_t%04d' % (A.get('name', 'br'), round(t * 1000)),
                  depth=A.get('depth', '0') == '1')
    elif MODE == 'clip':
        for f in range(int(A.get('f0', 0)), int(A.get('f1', round(DUR * FPS))) + 1):
            tag = 'clip/f%03d' % f
            if os.path.exists(os.path.join(OUT, tag + '.jpg')):
                continue
            still(sc, cam, update, info, f / FPS, 'auto', tag)


# ====================================================================== game view
def game():
    sys.argv += ['--view=close']
    import terran_deck as Dk
    Dk.VIEW = 'close'
    Dk.RES = RES
    Dk.NAME = A.get('name', 'breach_game')
    Dk.OUT = OUT
    t = float(A.get('t', 1.5))

    def hook(sc):
        for o in list(bpy.data.objects):
            if o.name.startswith('Field_bay'):
                if o in K.NOFOG:
                    K.NOFOG.remove(o)
                bpy.data.objects.remove(o)
        T = lambda k, x, y, rz: K.tank(k, (x, y, 0), rz)
        Al = lambda k, x, y, rz: K.tank(k, (x, y, 0), rz, faction='alien')
        T('bulwark', 53.5, 58, 0)
        T('lancer', 86.5, 68, 180)
        T('lancer', 53.5, 68, 0)
        T('javelin', 86.5, 58, 180)
        T('bulwark', 70, 64, 90)       # defenders facing the bay door
        T('lancer', 62.5, 70, 78)
        T('lancer', 77.5, 69, 104)
        T('bulwark', 61, 80, 62)
        T('outrider', 79.5, 79, 118)
        Al('darter', 63.5, 97, -80)    # next boarders on the lip
        Al('stinger', 76.5, 99, -95)
        yf, x0 = 90.0, 56.7
        depth = 1.4
        att = Attacker('carapace', 70.0, yf, depth, hover=0.6, end_centre=11.0)
        fld = Field('Field_bay', (x0, yf, 0.1), 26.6, Dk.H + 0.6, 2.0, None, (70.0 - x0, 2.5), R=3.9, depth=depth,
                    sigma=2.4, strength=1.7, edge=5.0, alpha=(0.1, 0.45), gap=0.07, seed=3, t_clear=att.t_clear,
                    shard_speed=0.8, hot_gain=0.45)
        ny, cy, z = att.update(t)
        fld.update(t, att.hull(t, fld.o))
        tb = t - T_BREAK
        flash = math.exp(-max(tb, 0) * 7.0) if tb >= 0 else 0
        K.point('Flare', (70, yf - 1.5, 3.0), 1200 * press(t) + 8000 * flash + 800, (0.6, 0.85, 1.0), r=0.8)
        att.glow.data.energy = 5000
        att.under.data.energy = 3000
        for x in (57.5, 82.5):
            K.point('Alarm', (x, 87.5, 4.5), 9000, (1.0, 0.3, 0.04), r=0.5)
    Dk.main(hook=hook, units_on=False)


if __name__ == '__main__':
    main()
