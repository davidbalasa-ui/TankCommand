"""Arcadian boarders pushing THROUGH the Terran triangle force field of the hangar bay door (design study, v2).

Rule: the field never breaks. It is one continuous tessellated skin the whole time. The attacker presses in, the
skin hinges at its shared edges and wraps the hull (the lattice subdivides near the contact), then the hull
passes through the surface: a tight cyan contour line marks the cut and slides from nose to tail. When the tail
clears, the skin springs back flat with a ripple.

Everything is a stateless function of time t (seconds), so any frame can be rendered on its own.

  --mode=frames --times=0.4,1.0,1.3 [--cam=A|B|H|auto] [--full=1]   stills (drafts)
  --mode=clip   [--f0=0 --f1=95]                                     frames for the draft clip
  --mode=game   [--t=2.0]                                            the same from the game camera
"""
import math
import os
import random
import sys

import bpy
import numpy as np
from scipy import ndimage as ndi
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import terran_interior_kit as K  # noqa: E402

A = K.args()
OUT = A.get('out', '/home/user/work/terran-interiors/breach2')
MODE = A.get('mode', 'frames')
RES = tuple(int(v) for v in A.get('res', '960x540').split('x'))
FPS = 24.0
T_TOUCH = 0.6
DUR = float(A.get('dur', 4.7))
GOLD = (1.0, 0.36, 0.02)
INFL = 0.13          # the skin rides this far proud of the hull
SLEEVE_W = float(A.get('sleeve_w', 0.75))   # how far the sleeve wall reaches out from the hull before it meets the plane


def sstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def hermite(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for (t0, p0, m0), (t1, p1, m1) in zip(keys[:-1], keys[1:]):
        if t <= t1:
            h = t1 - t0
            s = (t - t0) / h
            return ((2 * s ** 3 - 3 * s ** 2 + 1) * p0 + (s ** 3 - 2 * s ** 2 + s) * h * m0 +
                    (-2 * s ** 3 + 3 * s ** 2) * p1 + (s ** 3 - s ** 2) * h * m1)


def tubes(me, segs):
    """segs: list of (p0, p1, radius) -> three-sided tubes."""
    me.clear_geometry()
    vs, fs = [], []
    for p0, p1, r in segs:
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = p1 - p0
        L = np.linalg.norm(d)
        if L < 1e-5:
            continue
        d /= L
        a = np.cross(d, (0.0, 0.3, 1.0))
        if np.linalg.norm(a) < 1e-4:
            a = np.cross(d, (1.0, 0, 0))
        a /= np.linalg.norm(a)
        b = np.cross(d, a)
        n = len(vs)
        for p in (p0, p1):
            for k in range(3):
                an = k * 2.0944
                vs.append(tuple(p + (a * math.cos(an) + b * math.sin(an)) * r))
        fs += [(n + k, n + (k + 1) % 3, n + 3 + (k + 1) % 3, n + 3 + k) for k in range(3)]
    if vs:
        me.from_pydata(vs, [], fs)
    me.update()


def line_obj(name, col, strength):
    me = bpy.data.meshes.new(name)
    me.materials.append(K._emit(name, col, strength))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.visible_shadow = False
    K.NOFOG.append(ob)
    return me


# ====================================================================== the attacker
class Attacker:
    def __init__(self, kind, x, y_field, hover=0.9, end_centre=13.5, c0=2.4, cdrag=0.8):
        new = K.tank(kind, (0, 0, 0), rz=0, faction='alien')
        bpy.context.view_layer.update()
        rs = np.random.RandomState(4)
        pts = []
        mats = set()
        for o in new:
            if o.type != 'MESH':
                continue
            me = o.data
            mats.update(m for m in me.materials if m)
            me.calc_loop_triangles()
            v = np.zeros(len(me.vertices) * 3)
            me.vertices.foreach_get('co', v)
            v = v.reshape(-1, 3)
            M = np.array(o.matrix_world)
            v = v @ M[:3, :3].T + M[:3, 3]
            ti = np.zeros(len(me.loop_triangles) * 3, dtype=np.int32)
            me.loop_triangles.foreach_get('vertices', ti)
            tr = v[ti.reshape(-1, 3)]
            ar = 0.5 * np.linalg.norm(np.cross(tr[:, 1] - tr[:, 0], tr[:, 2] - tr[:, 0]), axis=1)
            n = np.maximum((ar / 0.0012).astype(int), 1)          # ~ one sample per 12 cm^2
            idx = np.repeat(np.arange(len(tr)), n)
            u, w = rs.rand(len(idx)), rs.rand(len(idx))
            f = u + w > 1
            u[f], w[f] = 1 - u[f], 1 - w[f]
            pts.append(tr[idx, 0] + (tr[idx, 1] - tr[idx, 0]) * u[:, None] + (tr[idx, 2] - tr[idx, 0]) * w[:, None])
            pts.append(v)
        self.pts = np.concatenate(pts)
        lo, hi = self.pts.min(axis=0), self.pts.max(axis=0)
        self.lo, self.hi = lo, hi
        print('ATTACKER', kind, lo, hi, len(self.pts), flush=True)
        self.nose, self.tail = hi[0], -lo[0]
        self.len = self.nose + self.tail
        # keep the Arcadian hull reading gold under the blue light
        for m in mats:
            if not m.use_nodes:
                continue
            for nd in m.node_tree.nodes:
                if nd.type == 'BSDF_PRINCIPLED':
                    bc = nd.inputs['Base Color']
                    mix = m.node_tree.nodes.new('ShaderNodeMixRGB')
                    mix.blend_type = 'MULTIPLY'
                    mix.inputs[0].default_value = float(A.get('goldtint', 0.85))
                    mix.inputs[2].default_value = (1.0, 0.62, 0.22, 1)
                    if bc.is_linked:
                        m.node_tree.links.new(bc.links[0].from_socket, mix.inputs[1])
                    else:
                        mix.inputs[1].default_value = bc.default_value[:]
                    m.node_tree.links.new(mix.outputs[0], bc)
        self.root = bpy.data.objects.new('Attacker', None)
        bpy.context.scene.collection.objects.link(self.root)
        for o in new:
            if o.parent is None:
                o.parent = self.root
        self.root.rotation_mode = 'XYZ'
        self.x, self.yf, self.hover = x, y_field, hover
        self.c0, self.cdrag = c0, cdrag
        clear_pen = self.len + c0 + cdrag + INFL + 0.3
        end_pen = max(end_centre + self.nose, clear_pen + 1.5)
        self.keys = [(0.0, -9.0, 22.0), (T_TOUCH, 0.0, 6.0), (1.3, 2.5, 3.0), (1.9, 5.6, 6.5),
                     (3.0, clear_pen, 8.0), (3.8, end_pen, 0.0)]
        self.t_pierce = next(k / 200.0 for k in range(100, 800) if self.pen(k / 200.0) > c0 + 0.05)
        self.t_clear = next(k / 200.0 for k in range(200, 800) if self.xc(k / 200.0) < -self.tail)
        self.glow = K.point('AttGlow', (0, 0, 0), 0, (1.0, 0.5, 0.12), r=1.2)
        self.under = K.point('AttUnder', (0, 0, 0), 0, (1.0, 0.5, 0.12), r=1.5)

    def pen(self, t):
        """How far the nose tip is past the rest plane of the field (negative = still outside)."""
        return hermite(self.keys, t)

    def c(self, t):
        """Depth the skin is dragged inward where it grips the hull."""
        p = self.pen(t)
        return min(max(p, 0.0), self.c0 + self.cdrag * sstep((p - 5.0) / 9.0))

    def xc(self, t):
        """Model-space x (forward) of the hull slice that is passing through the skin right now."""
        return self.nose - (self.pen(t) - self.c(t) - INFL)

    def update(self, t):
        p = self.pen(t)
        tau = t - self.t_clear
        land = sstep(tau / 0.75)
        z = self.hover * (1 - land)
        if tau > 0.75:
            z += 0.12 * math.exp(-(tau - 0.75) * 9) * math.sin((tau - 0.75) * 26)
        pitch = math.radians(4.0) * math.sin(min(max(tau, 0) / 0.8, 1.0) * math.pi)
        strain = sstep((p + 0.2) / 1.5) * (1 - sstep(tau / 0.2))
        jit = strain * (0.05 * math.sin(t * 173.0) + 0.03 * math.sin(t * 61.0))
        pitch += math.radians(1.6) * strain * math.sin(t * 23.0) - math.radians(1.2) * strain   # bucking against the field
        roll = math.radians(1.3) * strain * math.sin(t * 17.0 + 1.0)
        ny = self.yf - p
        cy = ny + self.nose
        vs = sstep(tau / 0.85)                    # once clear it peels off to the side, out of the doorway
        vx = -float(A.get('veer', 4.5)) * vs
        yaw = math.radians(float(A.get('veer_yaw', 24))) * math.sin(min(max(tau, 0) / 0.85, 1.0) * math.pi * 0.75)
        self.cx_now = self.x + vx
        self.root.location = (self.x + vx + jit, cy, z)
        self.root.rotation_euler = (roll, pitch, math.radians(-90) - yaw)
        self.strain = strain
        self.glow.location = (self.cx_now, cy - 2.0, z + 5.2)
        self.under.location = (self.cx_now, cy, max(z, 0.2) + 0.45)
        return ny, cy, z


# ====================================================================== the field (one continuous skin)
class Field:
    """Triangle field in the plane y = origin.y (u = +x, v = +z). Inside of the ship is -y."""
    CELL = 0.1

    def __init__(self, name, origin, w, h, tri, inside, att, strength, edge, alpha, seed=1, rsub=8.0, nsub=6,
                 slope=1.6, line=0.038):
        self.o = np.array(origin, float)
        self.w, self.h, self.tri = w, h, tri
        self.att = att
        self.slope = slope
        self.cx = att.x - origin[0]
        self.cz = att.hover + (att.lo[2] + att.hi[2]) / 2 - origin[2]
        self.rwin = (rsub - 1.6, rsub - 0.3)
        hh = tri * math.sqrt(3) / 2
        rnd = random.Random(seed)
        T, R, PE, PC, IN = [], [], [], [], []          # triangles, r, parent-edge flags, parent centroid, inset
        rows = int(math.ceil(h / hh))
        cols = int(math.ceil(w / (tri / 2))) + 1
        for r in range(rows):
            for c in range(-1, cols):
                up = (r + c) % 2 == 0
                x0 = c * tri / 2
                if up:
                    t3 = [(x0, r * hh), (x0 + tri, r * hh), (x0 + tri / 2, (r + 1) * hh)]
                else:
                    t3 = [(x0, (r + 1) * hh), (x0 + tri / 2, r * hh), (x0 + tri, (r + 1) * hh)]
                cx = sum(p[0] for p in t3) / 3
                cy = sum(p[1] for p in t3) / 3
                if not (0 <= cx <= w and 0 <= cy <= h) or (inside and not inside(cx, cy)):
                    continue
                t3 = np.array([(min(max(a, 0), w), min(max(b, 0), h)) for a, b in t3])
                rv = rnd.random() ** 1.6
                n = nsub if math.hypot(cx - self.cx, cy - self.cz) < rsub else 1
                P = lambda i, j: t3[0] + (t3[1] - t3[0]) * (i / n) + (t3[2] - t3[0]) * (j / n)
                for i in range(n):
                    for j in range(n - i):
                        subs = [((i, j), (i + 1, j), (i, j + 1))]
                        if i + j < n - 1:
                            subs.append(((i + 1, j), (i + 1, j + 1), (i, j + 1)))
                        for s3 in subs:
                            T.append([P(*q) for q in s3])
                            R.append(rv)
                            PC.append((cx, cy))
                            IN.append(1.0 / (tri / n / (2 * math.sqrt(3))))
                            fl = []
                            for k in range(3):
                                (i0, j0), (i1, j1) = s3[k], s3[(k + 1) % 3]
                                fl.append(1.0 if (j0 == 0 and j1 == 0) or (i0 == 0 and i1 == 0) or
                                          (i0 + j0 == n and i1 + j1 == n) else 0.0)
                            PE.append(fl)
        self.P2 = np.array(T, float)                  # (N, 3, 2) plane coords
        self.N = len(self.P2)
        self.r = np.array(R)
        self.pe = np.array(PE)
        self.inv_inr = np.array(IN)
        self.line = line
        pc = np.array(PC)
        self.rp = np.hypot(pc[:, 0] - self.cx, pc[:, 1] - self.cz)
        self.rn = np.array([rnd.random() for _ in range(self.N)])
        base = np.zeros((self.N, 3, 3))
        base[..., 0] = self.o[0] + self.P2[..., 0]
        base[..., 1] = self.o[1]
        base[..., 2] = self.o[2] + self.P2[..., 1]
        self.base = base
        rv = np.hypot(self.P2[..., 0] - self.cx, self.P2[..., 1] - self.cz)
        self.win = 1 - np.clip((rv - self.rwin[0]) / (self.rwin[1] - self.rwin[0]), 0, 1)
        self.rv = rv
        print('FIELD', name, 'triangles', self.N, flush=True)
        self._hull_maps()
        self._mesh(name, strength, edge, alpha)
        self.ml = {'ring': line_obj(name + '_ring', (0.12, 0.75, 1.0), float(A.get('ring_e', 10))),
                   'gold': line_obj(name + '_gold', GOLD, float(A.get('gold_e', 7))),
                   'spark': line_obj(name + '_spark', (0.2, 0.7, 1.0), float(A.get('spark_e', 10)))}
        self.extra = []                                # extra cyan segments (tracers), set by the scene

    # -------------------------------------------------------------- hull height maps on the field grid
    def _hull_maps(self):
        att, c = self.att, self.CELL
        self.gx0 = self.cx - 9.0
        self.nx, self.nz = 180, int(min(self.h, 11.0) / c)
        F = np.full((self.nx, self.nz), -1e9)
        B = np.full((self.nx, self.nz), 1e9)
        p = att.pts
        i = np.round((p[:, 1] + 9.0) / c).astype(int)
        j = np.round((p[:, 2] + att.hover - self.o[2]) / c).astype(int)
        ok = (i >= 0) & (i < self.nx) & (j >= 0) & (j < self.nz)
        np.maximum.at(F, (i[ok], j[ok]), p[ok, 0])
        np.minimum.at(B, (i[ok], j[ok]), p[ok, 0])
        F0, B0 = F.copy(), B.copy()
        for di in range(-2, 3):                         # inflate a little so flat facets clear the hull
            for dj in range(-2, 3):
                if di * di + dj * dj <= 5:
                    F = np.maximum(F, np.roll(np.roll(F0, di, 0), dj, 1))
                    B = np.minimum(B, np.roll(np.roll(B0, di, 0), dj, 1))
        self.F, self.B = F, B
        self.sil = F > -1e8

    def samp(self, G, p2):
        c = self.CELL
        a = np.clip((p2[..., 0] - self.gx0) / c, 0, self.nx - 1.001)
        b = np.clip(p2[..., 1] / c, 0, self.nz - 1.001)
        i, j = a.astype(int), b.astype(int)
        fa, fb = a - i, b - j
        return (G[i, j] * (1 - fa) * (1 - fb) + G[i + 1, j] * fa * (1 - fb) +
                G[i, j + 1] * (1 - fa) * fb + G[i + 1, j + 1] * fa * fb)

    @staticmethod
    def blur(S):
        return (S * 4 + np.roll(S, 1, 0) + np.roll(S, -1, 0) + np.roll(S, 1, 1) + np.roll(S, -1, 1)) / 8.0

    def glove(self, G):
        """Skin depth everywhere: the gripped hull columns, plus a short steep wall that hugs the hull outline and
        fillets into the rest plane within SLEEVE_W (a glove, not a funnel)."""
        grip = G > 1e-3
        if not grip.any():
            return np.zeros_like(G)
        d, (ii, jj) = ndi.distance_transform_edt(~grip, sampling=self.CELL, return_indices=True)
        Gn = G[ii, jj]
        w = SLEEVE_W + 0.08 * Gn
        prof = np.clip(1 - d / w, 0, 1)
        prof = prof * prof * (1.6 - 0.6 * prof)          # steep at the hull, soft fillet at the plane
        S = np.where(grip, G, Gn * prof)
        S = S + INFL * np.clip(S / 0.3, 0, 1)
        S = 0.5 * S + 0.5 * self.blur(S)
        S[:, -3:] = 0
        S[0, :] = S[-1, :] = 0
        return S

    def snap_ref(self):
        if not hasattr(self, '_snap'):
            S, _, _, dep = self.sheet(self.att.t_clear - 0.04)
            self._snap = (S, max(float(S.max()), 0.5))
        return self._snap

    def sheet(self, t):
        """Inward displacement of the skin on the grid, the gripped region and the contour segments."""
        att = self.att
        pen, c = att.pen(t), att.c(t)
        xc = att.xc(t)
        if pen <= 0:
            Z = np.zeros((self.nx, self.nz))
            return Z, Z, [], 0.0
        prot = np.where(self.sil, pen - (att.nose - self.F), 0.0)
        G = np.where(self.B > xc, 0.0, np.clip(prot, 0, c))
        S = self.glove(G)
        # contour: the hull slice passing through the skin (marching squares on phi = 0)
        segs = []
        if xc < att.nose:
            phi = np.where(self.sil, np.minimum(self.F - xc, xc - self.B), -0.6)
            phi = self.blur(np.clip(phi, -0.6, 0.6))
            s = phi > 0
            mix = (s[:-1, :-1] | s[1:, :-1] | s[1:, 1:] | s[:-1, 1:]) & ~(s[:-1, :-1] & s[1:, :-1] & s[1:, 1:] & s[:-1, 1:])
            for i, j in zip(*np.nonzero(mix)):
                cr = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                pts = []
                for k in range(4):
                    (i0, j0), (i1, j1) = cr[k], cr[(k + 1) % 4]
                    v0, v1 = phi[i0, j0], phi[i1, j1]
                    if (v0 > 0) != (v1 > 0):
                        f = v0 / (v0 - v1)
                        pts.append((i0 + (i1 - i0) * f, j0 + (j1 - j0) * f))
                for k in range(0, len(pts) - 1, 2):
                    segs.append((pts[k], pts[k + 1]))
        return S, G, segs, c + INFL

    # -------------------------------------------------------------- meshes
    def _mesh(self, name, strength, edge, alpha):
        N = self.N
        me = bpy.data.meshes.new(name + '_faces')
        me.from_pydata([(0, 0, 0)] * (3 * N), [], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(N)])
        for an in ('r', 'hot', 'pulse'):
            me.attributes.new(an, 'FLOAT', 'FACE')
        m = bpy.data.materials.new(name + '_face')
        t = K.NT(m)
        ar = t.n('ShaderNodeAttribute', attribute_name='r').outputs['Fac']
        ah = t.n('ShaderNodeAttribute', attribute_name='hot').outputs['Fac']
        ap = t.n('ShaderNodeAttribute', attribute_name='pulse').outputs['Fac']
        colm = t.n('ShaderNodeMixRGB')
        colm.inputs[1].default_value = (*K.NEON, 1)
        colm.inputs[2].default_value = (0.0, 0.33, 1.0, 1)           # hot stays BLUE (towards cyan, never white)
        t.link(t.m('MINIMUM', t.m('MULTIPLY', ah, 0.6), 1.0), colm.inputs[0])
        em = t.n('ShaderNodeEmission')
        t.link(colm.outputs[0], em.inputs[0])
        base = t.m('MULTIPLY', t.m('ADD', 0.35, ar), strength)
        gain = t.m('ADD', t.m('ADD', 1.0, t.m('MULTIPLY', ah, float(A.get('hotgain', 0.25)))), t.m('MULTIPLY', ap, 3.0))
        t.link(t.m('MULTIPLY', base, gain), em.inputs[1])
        mix = t.n('ShaderNodeMixShader')
        a0 = t.m('ADD', alpha[0], t.m('MULTIPLY', ar, alpha[1] - alpha[0]))
        t.link(t.m('MINIMUM', t.m('ADD', t.m('ADD', a0, t.m('MULTIPLY', ah, 0.22)), t.m('MULTIPLY', ap, 0.35)), 0.7), mix.inputs[0])
        t.link(t.n('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        t.link(em.outputs[0], mix.inputs[2])
        t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
        me.materials.append(m)
        self.mf = me
        me = bpy.data.meshes.new(name + '_edges')
        me.from_pydata([(0, 0, 0)] * (12 * N), [], [(4 * q, 4 * q + 1, 4 * q + 2, 4 * q + 3) for q in range(3 * N)])
        for an in ('hot', 'life', 'pulse'):
            me.attributes.new(an, 'FLOAT', 'FACE')
        m = bpy.data.materials.new(name + '_edge')
        t = K.NT(m)
        ah = t.n('ShaderNodeAttribute', attribute_name='hot').outputs['Fac']
        al = t.n('ShaderNodeAttribute', attribute_name='life').outputs['Fac']
        ap = t.n('ShaderNodeAttribute', attribute_name='pulse').outputs['Fac']
        colm = t.n('ShaderNodeMixRGB')
        colm.inputs[1].default_value = (*[0.8 * c + 0.2 * k for c, k in zip(K.NEON, K.CYAN)], 1)
        colm.inputs[2].default_value = (0.02, 0.55, 1.0, 1)
        t.link(t.m('MINIMUM', t.m('MULTIPLY', ah, 0.6), 1.0), colm.inputs[0])
        em = t.n('ShaderNodeEmission')
        t.link(colm.outputs[0], em.inputs[0])
        t.link(t.m('MULTIPLY', edge, t.m('ADD', t.m('ADD', 1.0, t.m('MULTIPLY', ah, 0.25)), t.m('MULTIPLY', ap, 4.0))), em.inputs[1])
        mix = t.n('ShaderNodeMixShader')
        t.link(al, mix.inputs[0])
        t.link(t.n('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        t.link(em.outputs[0], mix.inputs[2])
        t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
        me.materials.append(m)
        self.me = me
        for me in (self.mf, self.me):
            ob = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(ob)
            ob.visible_shadow = False
            K.NOFOG.append(ob)

    # -------------------------------------------------------------- per-frame update
    def update(self, t):
        att = self.att
        frame = int(round(t * FPS))
        frnd = np.random.RandomState(1000 + frame)
        S, G, segs, depth = self.sheet(t)
        disp = self.samp(S, self.P2) * self.win
        tau = t - att.t_clear
        strain = sstep(att.pen(t) / 1.0) * (1 - sstep(tau / 0.15))
        if tau > 0:                                    # SNAP: the released sleeve whips back, overshoots outward, rings
            Sr, dmax = self.snap_ref()
            sig = (0.4 + float(A.get('snap_spread', 5.0)) * tau) / self.CELL
            Sw = ndi.gaussian_filter(Sr, sig, mode='constant')
            Sw = Sw / max(float(Sw.max()), 1e-6)
            amp = min(dmax, float(A.get('snap_amp', 2.4))) * math.exp(-tau * float(A.get('snap_decay', 2.3))) * math.cos(2 * math.pi * float(A.get('snap_hz', 1.9)) * tau)
            snapd = amp * self.samp(Sw, self.P2) * self.win
            disp += snapd
            self._snapglow = np.clip(np.abs(snapd).max(axis=1) / 0.9, 0, 1.2)
            rip = 0.8 * math.exp(-tau * 2.4) * min(tau / 0.08, 1.0)
            disp += rip * np.sin(2 * math.pi * (self.rv / 3.4 - 3.0 * tau)) * np.exp(-self.rv / 9.0) * self.win
        out = self.base.copy()
        out[..., 1] -= disp
        cen = out.mean(axis=1)
        nrm = np.cross(out[:, 1] - out[:, 0], out[:, 2] - out[:, 0])
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)[:, None]
        tilt = 1 - np.abs(nrm[:, 1])
        c2 = self.P2.mean(axis=1)
        Gc = self.samp(G, c2)
        Sc = self.samp(S, c2)
        act = np.clip(np.abs(disp).max(axis=1) / 0.18, 0, 1)
        hot = (0.8 * np.clip(Gc / 0.15, 0, 1) + 0.6 * np.clip(Sc / max(depth, 0.5), 0, 1)) * (0.85 + 0.3 * frnd.rand(self.N))
        hot += float(A.get('tiltgain', 0.9)) * np.clip(tilt, 0, 0.6)
        hot = np.minimum(hot, 1.5)
        # brightness waves rippling outward, big triangle by big triangle
        k = 0
        while True:
            tk = T_TOUCH + 0.24 * k
            k += 1
            if tk > min(t, att.t_clear):
                break
            front = 2.0 + (t - tk) * 13.0
            hot += 0.9 * np.clip(1 - np.abs(self.rp - front) / 1.5, 0, 1) * math.exp(-(t - tk) * 1.5)
        pulse = np.zeros(self.N)
        if tau > 0 and hasattr(self, '_snapglow'):
            pulse += float(A.get('bulge_glow', 0.9)) * self._snapglow      # the bulging skin lights up as it rings
        if tau > 0:                                    # snap: a bright shock ring races out across the whole door
            for k, (spd, amp) in enumerate(((17.0, 1.6), (11.0, 0.8))):
                front = 0.5 + tau * spd
                pulse += amp * np.clip(1 - np.abs(self.rp - front) / 1.8, 0, 1) ** 1.5 * math.exp(-tau * 1.3)
            pulse += 1.2 * math.exp(-tau * 8.0) * np.exp(-self.rp / 3.5)          # flash at the exit point
            pulse += 0.25 * math.exp(-tau * 5.0)                                 # whole field flickers bright
        # ---- faces
        self.mf.vertices.foreach_set('co', out.reshape(-1))
        self.mf.attributes['r'].data.foreach_set('value', self.r)
        self.mf.attributes['hot'].data.foreach_set('value', hot)
        self.mf.attributes['pulse'].data.foreach_set('value', pulse)
        self.mf.update()
        # ---- seam lines: parent seams always, the finer hinges only where the skin is working
        wgt = np.where(self.pe > 0.5, 1.0, 0.3 * act[:, None])              # (N, 3)
        g = self.line * wgt                                                  # line half-width per edge (m)
        O = out.copy()
        O[..., 1] -= 0.02
        cn = O.mean(axis=1, keepdims=True)
        quads = np.zeros((self.N, 3, 4, 3))
        for e in range(3):
            a, b = O[:, e], O[:, (e + 1) % 3]
            ge = g[:, e][:, None]
            quads[:, e, 0] = a
            quads[:, e, 1] = b
            ed = b - a
            ed /= np.maximum(np.linalg.norm(ed, axis=1), 1e-9)[:, None]
            pp = cn[:, 0] - a
            pp -= ed * (pp * ed).sum(axis=1)[:, None]
            pp /= np.maximum(np.linalg.norm(pp, axis=1), 1e-9)[:, None]
            quads[:, e, 2] = b + pp * ge
            quads[:, e, 3] = a + pp * ge
        self.me.vertices.foreach_set('co', quads.reshape(-1))
        self.me.attributes['hot'].data.foreach_set('value', np.repeat(hot, 3))
        self.me.attributes['pulse'].data.foreach_set('value', np.repeat(pulse, 3))
        self.me.attributes['life'].data.foreach_set('value', np.where(self.pe > 0.5, 1.0, 0.35 * act[:, None]).reshape(-1))
        self.me.update()
        # ---- contour line where the hull passes through
        c = self.CELL
        y = self.o[1] - depth - 0.05
        W = lambda p: (self.o[0] + self.gx0 + p[0] * c, y, self.o[2] + p[1] * c)
        rr = float(A.get('ring_r', 0.045))
        tubes(self.ml['ring'], [(W(a), W(b), rr) for a, b in segs] + self.extra)
        # ---- gold lightning + sparks skittering over the skin around the contact
        gold, spark = [], []
        cand = np.argwhere((S > 0.2) & (S < max(depth * 0.75, 0.3)))
        if len(cand) and strain > 0:
            rnd = random.Random(77 + frame // 2)

            def P3(a, b):
                s = float(self.samp(S, np.array([a, b])))
                return (self.o[0] + a, self.o[1] - s - 0.08, self.o[2] + b)
            for _ in range(int(3 + 6 * strain)):
                i, j = cand[rnd.randrange(len(cand))]
                a, b = self.gx0 + i * c, j * c
                an = math.atan2(b - self.cz, a - self.cx) + rnd.uniform(-0.9, 0.9)
                n = rnd.randint(3, 9)
                p = P3(a, b)
                for q in range(n):
                    an += rnd.uniform(-0.7, 0.7)
                    a, b = a + math.cos(an) * 0.4, max(b + math.sin(an) * 0.4, 0.05)
                    p2 = P3(a, b)
                    gold.append((p, p2, 0.05 * (1 - 0.7 * q / n)))
                    p = p2
            for q in range(140):
                pr = random.Random(q * 7919)
                t0 = T_TOUCH + pr.uniform(0, 0.33) + 0.33 * int((t - T_TOUCH) / 0.33)
                if t0 > t:
                    t0 -= 0.33
                age, life = t - t0, pr.uniform(0.12, 0.33)
                if not (0 < age < life) or t0 > att.t_clear + 0.1:
                    continue
                i, j = cand[int(pr.random() * len(cand)) % len(cand)]
                a, b = self.gx0 + i * c, j * c
                an = math.atan2(b - self.cz, a - self.cx) + pr.uniform(-0.6, 0.6)
                v = np.array([math.cos(an) * pr.uniform(1, 6), -pr.uniform(2, 9), math.sin(an) * pr.uniform(1, 6) + 1.5])
                p = np.array(P3(a, b)) + v * age + np.array([0, 0, -4.0 * age * age])
                (gold if q % 3 == 0 else spark).append((p - v * 0.035, p, 0.022 * (1 - age / life) + 0.008))
        tubes(self.ml['gold'], gold)
        tubes(self.ml['spark'], spark)
        return depth, strain


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
    y0 = L - 3.56
    for s in (-1, 1):                                   # alarm beacons on the door frame
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
    defenders = []
    for kind, x, dy, rz in (('bulwark', 9.5, -7.0, 128), ('lancer', -13.2, -7.0, 70), ('bulwark', -14.0, -20.5, 72),
                            ('lancer', 10.5, -24.0, 131)):
        new = K.tank(kind, (x, yf + dy, 0), rz=rz)
        piv = next((o for o in new if o.name.startswith('TurretPivot')), None)
        defenders.append(dict(x=x, y=yf + dy, rz=rz, piv=piv, yaw=None, late=(x < -13 and dy > -10)))
        K.spot('Head', (x * 0.93, yf + dy + 3.0, 2.3), (0, yf, 3.0), 700, (0.8, 0.9, 1.0), angle=42, blend=0.7, r=0.15)
    K.tank('darter', (-9.5, yf + 19, 2.2), rz=-84, faction='alien')
    K.tank('stinger', (10.5, yf + 26, 3.0), rz=-97, faction='alien')

    def inside(a, b):
        return abs(a - W2) + b < W2 + H.DOOR_H - H.DOOR_CH
    att = Attacker('carapace', 0.0, yf)
    fld = Field('BayField', (-W2, yf, 0), 2 * W2, H.DOOR_H, 2.3, inside, att, strength=float(A.get('field', 0.5)),
                edge=float(A.get('edge', 1.2)), alpha=(0.06, 0.3))
    print('T_PIERCE', att.t_pierce, 'T_CLEAR', att.t_clear, flush=True)
    glow = K.point('SkinGlow', (0, yf - 4.5, 3.0), 0, (0.08, 0.45, 1.0), r=1.0)
    muzzle = K.point('Muzzle', (0, 0, 0), 0, (0.3, 0.75, 1.0), r=0.3)
    hit = K.point('Hit', (0, 0, 0), 0, (1.0, 0.6, 0.2), r=0.4)
    alarms = [K.spot('Alarm', (s * 15, L - 6, 17.5), (s * 6, L - 14, 0), 0, (1.0, 0.3, 0.04), angle=95, blend=0.8, r=0.6)
              for s in (-1, 1)]
    alarms += [K.area('AlarmW', (s * (W2 + 1.5), L - 4.2, 10), (1.0, 9.0), 0, (1.0, 0.3, 0.04), rot=(90, 0, 0), spread=160)
               for s in (-1, 1)]
    ceil = [(o, o.data.energy) for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith(('Ceil', 'Bay'))]
    fglow = bpy.data.objects.get('FieldGlow')
    aem = next(n for n in K.mat('alarm').node_tree.nodes if n.type == 'EMISSION')
    MUZ = 5.0                                                # muzzle distance from the tank centre
    shots = ((3, 3.30), (0, 3.45), (3, 3.62), (1, 3.78), (2, 3.95), (0, 4.15))   # (defender, time)

    def aim(t, cy, z):
        """Turrets slew (with lag) onto the contact point, then onto the boarder once it is inside."""
        for d in defenders:
            tgt = (att.cx_now, min(cy, yf - 0.5), z + 2.0) if t > T_TOUCH else (0.0, yf, 3.0)
            want = math.atan2(tgt[1] - d['y'], tgt[0] - d['x'])
            yaw = math.radians(d['rz']) + 0.0
            t0 = CUT if d.get('late') else T_TOUCH          # the one beside camera A waits for the cut
            if t > t0:
                lag = sstep((t - t0) / 0.9)
                want = yaw + lag * math.atan2(math.sin(want - yaw), math.cos(want - yaw))
            else:
                want = yaw
            d['yaw'] = want
            if d['piv'] is not None:
                d['piv'].rotation_mode = 'XYZ'
                d['piv'].rotation_euler = (0, 0, want - yaw)
            d['gun'] = np.array([d['x'] + MUZ * math.cos(want), d['y'] + MUZ * math.sin(want), 2.25])

    def update(t):
        ny, cy, z = att.update(t)
        fld.extra = []
        muzzle.data.energy = hit.data.energy = 0
        aim(t, cy, z)
        for di, ts in shots:                                # defenders open fire once it is inside
            a = t - ts
            gun = defenders[di]['gun']
            if -0.001 <= a < 0.13:
                tgt = np.array([att.cx_now + 2.2, cy - 1.0, z + 2.0])
                d = tgt - gun
                Ld = np.linalg.norm(d)
                d /= Ld
                h0, h1 = min(a * 150.0, Ld), min(a * 150.0 + 6.0, Ld)
                if h1 - h0 > 0.3:
                    fld.extra.append((gun + d * h0, gun + d * h1, 0.07))
                muzzle.location = gun
                muzzle.data.energy = 9000 * max(0.0, 1 - a / 0.07)
                if a * 150.0 + 6.0 >= Ld:
                    hit.location = tgt - d * 0.5
                    hit.data.energy = 12000
        depth, strain = fld.update(t)
        fr = random.Random(int(round(t * FPS)))
        tau = t - att.t_clear
        glow.location = (0, yf - depth - 2.2, 3.2)
        glow.data.energy = 2600 * strain * fr.uniform(0.85, 1.15) + 2200 * max(0, math.exp(-max(tau, 0) * 4)) * (tau > 0)
        ins = sstep((yf + 1 - ny) / 6.0)
        att.glow.data.energy = 4000 + 4000 * ins
        att.under.data.energy = 3000 * ins
        al = 0.0
        if t > T_TOUCH + 0.12:
            ph = ((t - T_TOUCH - 0.12) * 2.4) % 1.0
            al = 0.12 + 0.88 * max(0.0, 1 - ph * 1.8) ** 1.5
        aem.inputs[1].default_value = 0.4 + 14.0 * al
        for k, o in enumerate(alarms):
            o.data.energy = (14000 if k < 2 else 4000) * al
        dim = 1.0 - 0.45 * sstep((t - T_TOUCH) / 0.5) - 0.18 * sstep((t - att.t_pierce) / 0.3)
        dim *= 1 - 0.12 * strain * fr.uniform(0, 1)
        for o, e in ceil:
            o.data.energy = e * dim
        if fglow:
            fglow.data.energy = 14000 * (1 + 0.5 * strain)
    return sc, cam, update, dict(yf=yf, att=att, fld=fld)


CUT = 2.7        # shot A -> shot B
T_CLEAR_CAM = 99.0
ATT_X = [0.0]


def camera(cam, name, t, yf):
    r = random.Random(int(round(t * FPS)) + 5)
    shake = 0.015 * sstep((t - T_TOUCH) / 0.4) * (1 - sstep((t - 3.3) / 0.3))
    tc = t - T_CLEAR_CAM
    if tc > 0:
        shake += 0.06 * math.exp(-tc * 9.0)                  # the snap kicks the camera
    sx, sz = r.uniform(-shake, shake), r.uniform(-shake, shake)
    if name == 'A':        # low and close on the contact, pushing in, then following the hull through
        s = t / CUT
        f = sstep((t - 1.5) / 1.0)
        loc = Vector((-11.6 + 0.9 * s, yf - 10.6 + 1.0 * s, 2.0))
        tgt = Vector((1.0 - 0.6 * f, yf - 1.2 - 3.0 * f, 3.5))
        lens = 23
    elif name == 'B':      # among the defenders: tail clears, the skin snaps flat, the boarder settles
        s = (t - CUT) / (DUR - CUT)
        fx = 0.45 * ATT_X[0]                              # drift with the boarder as it peels off
        loc = Vector((10.4 - 0.6 * s + 0.5 * fx, yf - 30.0 - 1.2 * s, float(A.get('bz', 6.6))))
        tgt = Vector((-0.5 + fx, yf - 6.0, float(A.get('btz', 3.6))))
        lens = 29
    else:                  # hero
        loc = Vector((-11.4, yf - 10.3, 1.85))
        tgt = Vector((0.6, yf - 3.2, 3.6))
        lens = 21
    K.look(cam, loc + Vector((sx, 0, sz)), tgt + Vector((sx * 0.5, 0, sz * 0.5)), lens=lens)


def still(sc, cam, update, info, t, name, tag, depth=False):
    update(t)
    ATT_X[0] = info['att'].cx_now - info['att'].x
    camera(cam, name if name != 'auto' else ('A' if t < CUT else 'B'), t, info['yf'])
    raw = os.path.join(OUT, '_raw', tag + '.png')
    K.render(sc, raw, RES, depth_far=130.0 if depth else None)
    return K.post(raw, os.path.join(OUT, tag + '.jpg'), haze=float(A.get('haze', 0.4)) if depth else 0,
                  scatter=float(A.get('scatter', 0.2)) if depth else 0, haze_col=(0.08, 0.25, 0.6),
                  bloom=float(A.get('bloom', 0.8)), thresh=float(A.get('thresh', 0.72)))


def main():
    full = A.get('full', '0') == '1'
    if MODE == 'game':
        return game()
    global T_CLEAR_CAM
    sc, cam, update, info = build_hangar(full)
    T_CLEAR_CAM = info['att'].t_clear
    sc.render.use_persistent_data = True
    if MODE == 'frames':
        for ts in A.get('times', '1.0').split(','):
            t = float(ts)
            still(sc, cam, update, info, t, A.get('cam', 'auto'), '%s_t%04d' % (A.get('name', 'br'), round(t * 1000)),
                  depth=A.get('depth', '0') == '1')
    elif MODE == 'clip':
        for f in range(int(A.get('f0', 0)), int(A.get('f1', round(DUR * FPS) - 1)) + 1):
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
    t = float(A.get('t', 2.0))

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
        T('bulwark', 70, 62, 90)       # defenders facing the bay door
        T('lancer', 62.5, 70, 78)
        T('lancer', 77.5, 69, 104)
        T('bulwark', 60.5, 80, 62)
        T('outrider', 79.5, 79, 118)
        Al('darter', 63.5, 97, -80)    # next boarders on the lip
        Al('stinger', 76.5, 99, -95)
        yf, x0 = 90.0, 56.7
        att = Attacker('carapace', 70.0, yf, hover=0.6, end_centre=11.0, c0=2.0, cdrag=0.6)
        fld = Field('Field_bay', (x0, yf, 0.1), 26.6, Dk.H + 0.6, 2.0, None, att, strength=float(A.get('field', 1.5)),
                    edge=4.5, alpha=(0.1, 0.45), seed=3, rsub=7.5, nsub=5, line=0.045)
        ny, cy, z = att.update(t)
        depth, strain = fld.update(t)
        K.point('SkinGlow', (70, yf - depth - 2.0, 4.0), 1500 * strain, (0.08, 0.45, 1.0), r=0.8)
        att.glow.data.energy = 4000
        att.under.data.energy = 2000
        for x in (57.5, 82.5):
            K.point('Alarm', (x, 87.5, 4.5), 9000, (1.0, 0.3, 0.04), r=0.5)
    Dk.main(hook=hook, units_on=False)


if __name__ == '__main__':
    main()
