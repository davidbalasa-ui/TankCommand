"""Arcadian portal arrival: the ship's OWN hull is drawn out of the portal like pulled glass.

Shared by backdrop_05_portals.py (hero still) and backdrop_05c_stretch.py (stage stills, contact sheet, draft
clip). Nothing here goes into the game: it is concept art for the look of the effect.

The idea, in the portal's own frame (z = distance in front of the portal plane along its normal n):
  * every hull vertex has a "true" place z0 for a rigid ship whose nose is x_nose in front of the plane;
  * in front of the free line (z0 >= zf * L, L = ship length) the hull is untouched;
  * behind it, with d = zf * L - z0: the hull is squeezed toward the lane axis by q = 1 / (1 + (d / (w L))^2)
    and drawn out along the axis, d' = d (1 + a (d / L)^2), so the part still in the throat is a thread many
    ship lengths long that converges on the tunnel's vanishing point, and the part that has come out eases
    back to its true proportions;
  * the squeezed part glows gold (vertex attribute 'bk_st' = how squeezed, added to the hull material);
  * thin gold hairlines follow the same flow from the hull's outline back into the black;
  * gold lightning crawls along the neck and snaps from the innermost tick ring to the hull;
  * when the tail comes free the ship is its true shape and a crisp thin ring pulse leaves the portal.
"""
import math
import random

import backdrop_kit as K
import bpy
import numpy as np
from mathutils import Vector


def portal(k, AT, n, S, frames, ring_k=3.5, seed=11, arcs=2):
    """The Arcadian portal (opening/portals.arcadian_portal) at AT facing n, void diameter S."""
    n = Vector(n).normalized()
    rf = K.PO.arcadian_portal(frames=frames + 1)
    rf.location = AT
    rf.rotation_mode = 'QUATERNION'
    rf.rotation_quaternion = n.to_track_quat('Z', 'Y')
    rf.scale = (S, S, 1)
    if arcs:
        K.PO.arcadian_arcs(AT, n, S * 0.5, 1, frames, seed=seed, every=arcs)
    for i in range(4):                                     # the instrument rings read too faint at still size
        nt = bpy.data.materials[f'RiftRingM{i}'].node_tree
        for nd in nt.nodes:
            if nd.type == 'EMISSION' and nd.inputs['Strength'].links:
                s0 = nd.inputs['Strength'].links[0].from_socket
                mul = nt.nodes.new('ShaderNodeMath')
                mul.operation = 'MULTIPLY'
                mul.inputs[1].default_value = ring_k
                mul.name = 'BKRingK'
                nt.links.new(s0, mul.inputs[0])
                nt.links.new(mul.outputs[0], nd.inputs['Strength'])
    return rf


def ring_boost(v):
    """Brightness of the tick rings (they flash when a ship snaps free)."""
    for i in range(4):
        nd = bpy.data.materials[f'RiftRingM{i}'].node_tree.nodes.get('BKRingK')
        if nd:
            nd.inputs[1].default_value = v


def _glow_copy(mat, strength):
    """A copy of a hull material that also glows gold where the vertex attribute 'bk_st' is high."""
    m = mat.copy()
    nt = m.node_tree
    out = next((x for x in nt.nodes if x.type == 'OUTPUT_MATERIAL' and x.is_active_output), None)
    if out is None or not out.inputs['Surface'].links:
        return m
    src = out.inputs['Surface'].links[0].from_socket
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'bk_st'
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = strength
    nt.links.new(at.outputs['Fac'], mul.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.6, 0.2, 1)
    nt.links.new(mul.outputs[0], em.inputs['Strength'])
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(src, add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    return m


def nose_at(L, f, f0, dur, zf):
    """Where the nose is (distance in front of the portal plane) at frame f, for a ship that starts to show at
    f0 and whose tail comes free at f0 + dur. None before it shows. After the snap it coasts on, slower."""
    s = (f - f0) / float(dur)
    if s < 0:
        return None
    span = L * (zf + 1.03)
    if s <= 1:
        return -0.03 * L + span * s ** 1.25
    v = span * 1.25 / dur
    return -0.03 * L + span + 0.5 * v * (f - f0 - dur)


class Stretcher:
    """One ship coming through the portal. set(x_nose) poses it (and rebuilds its lines and lightning)."""

    def __init__(self, k, kind, AT, n, S, scale=None, roll=0.0, off=(0.0, 0.0), a=3.0, zf=0.4, w=0.2, glow=5.0,
                 seed=1, depth=240.0, lines=10, line_r=None, bolt_w=None):
        self.k = k
        self.AT = np.array(AT, dtype=np.float64)
        nv = Vector(n).normalized()
        e2 = (Vector((0, 0, 1)) - nv * nv.z).normalized()     # lane offsets: e2 = up, e1 = sideways
        e1 = e2.cross(nv).normalized()
        self.nv, self.e1v, self.e2v = nv, e1, e2
        self.n = np.array(nv, dtype=np.float64)
        self.S, self.R = S, S * 0.5
        self.off = np.array(e1 * (off[0] * self.R) + e2 * (off[1] * self.R), dtype=np.float64)
        self.a, self.zf, self.w, self.Dm = a, zf, w, depth * 0.85
        self.seed = seed
        self.line_r = line_r or S * 0.0014
        self.bolt_w = bolt_w or 0.15 * self.R / 107.0
        self.nlines = lines
        ob = k.ship(kind, scale=scale)
        ob.data = ob.data.copy()                       # this ship gets its own mesh: its vertices are moved
        me = ob.data
        for i, m in enumerate(list(me.materials)):
            if m is not None:
                me.materials[i] = _glow_copy(m, glow)
        if 'bk_st' not in me.attributes:
            me.attributes.new('bk_st', 'FLOAT', 'POINT')
        self.ob, self.me = ob, me
        nv_ = len(me.vertices)
        co = np.empty(nv_ * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        self.co0 = co.reshape(-1, 3).astype(np.float64)
        k.place(ob, (0, 0, 0), fwd=nv, roll=roll)
        self.M3 = np.array(ob.matrix_world.to_3x3(), dtype=np.float64)
        self.M3i = np.linalg.inv(self.M3)
        sx = ob.scale.x
        self.xmax = float(self.co0[:, 0].max()) * sx
        self.L = float(self.co0[:, 0].max() - self.co0[:, 0].min()) * sx
        rnd = np.random.default_rng(seed)
        self.sub = rnd.choice(nv_, size=min(nv_, 6000), replace=False)
        # outline anchors for the hairlines: the outermost vertex in each direction round the axis, at a few
        # stations along the hull (rigid coordinates relative to the ship's origin, world axes)
        rel = self.co0[self.sub] @ self.M3.T
        ax = rel @ self.n
        rad = rel - np.outer(ax, self.n)
        ang = np.arctan2(rad @ np.array(e2), rad @ np.array(e1))
        rr = np.linalg.norm(rad, axis=1)
        self.anchors = []
        for i in range(lines):
            sel = np.where(np.abs(((ang - (i + 0.5) / lines * 2 * math.pi + math.pi) % (2 * math.pi)) - math.pi)
                           < math.pi / lines)[0]
            if len(sel):
                self.anchors.append(rel[sel[np.argmax(rr[sel])]])
        self.anchors.append(rel[np.argmin(ax)])
        self.fx = []
        self.lmat = K.C.emit_mat(k.uid('HairM'), (1.0, 0.66, 0.26), 9.0)
        self.bmat = K.C.emit_mat(k.uid('ZapM'), (1.0, 0.74, 0.36), 16.0)
        self.q = None

    # ------------------------------------------------------------------ the flow
    def warp(self, W):
        """World points of the rigid ship -> where the portal has drawn them to. Returns (points, q)."""
        L = self.L
        rel = W - self.AT
        z0 = rel @ self.n
        rl = rel - np.outer(z0, self.n) - self.off
        d = np.clip(self.zf * L - z0, 0.0, None)
        q = 1.0 / (1.0 + (d / (self.w * L)) ** 2)
        z = z0 - self.a * d * (d / L) ** 2                         # (z0 itself where d = 0: the free part)
        dep = np.clip(-z, 0.0, None)
        zc = np.where(z < 0, -self.Dm * (1.0 - np.exp(-dep / self.Dm)), z)
        c = q ** 0.4                                              # lanes off the axis close on the vanishing point
        out = self.AT + np.outer(c, self.off) + rl * q[:, None] + np.outer(zc, self.n)
        return out, q

    def clear_fx(self):
        for o in self.fx:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if d is not None and d.users == 0:
                (bpy.data.curves if isinstance(d, bpy.types.Curve) else bpy.data.meshes).remove(d)
        self.fx = []

    def set(self, x_nose, fx=True, lines=1.0, bolts=1.0, tick=0):
        """Pose the ship with its nose x_nose in front of the portal plane. x_nose None hides it."""
        self.clear_fx()
        ob = self.ob
        if x_nose is None:
            ob.hide_render = True
            return
        ob.hide_render = False
        loc = self.AT + self.off + self.n * (x_nose - self.xmax)
        self.loc = loc
        W = self.co0 @ self.M3.T + loc
        Wd, q = self.warp(W)
        self.W, self.q = Wd, q
        local = (Wd - loc) @ self.M3i.T
        ob.location = Vector(loc)
        self.me.vertices.foreach_set('co', local.astype(np.float32).ravel())
        self.me.attributes['bk_st'].data.foreach_set('value', ((1.0 - q) ** 3.0).astype(np.float32))
        self.me.update()
        self.free = bool(q.min() > 0.999)
        if not fx:
            return
        if lines > 0.02:
            self._lines(loc, lines)
        if bolts > 0.02 and not self.free:
            self._bolts(tick)

    # ------------------------------------------------------------------ hairlines
    def _lines(self, loc, strength):
        L = self.L
        cu = bpy.data.curves.new(self.k.uid('Hair'), 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = self.line_r * (0.5 + 0.5 * strength)
        cu.bevel_resolution = 0
        cu.use_fill_caps = True
        N = 70
        s = (np.arange(N) / (N - 1.0)) ** 2.2 * 5.0 * L
        zline = self.zf * L
        for an in self.anchors:
            p0 = an + loc
            z0 = float((p0 - self.AT) @ self.n)
            start = p0 - self.n * max(0.0, z0 - zline)           # only the part inside the pull, not speed lines
            pts = start[None, :] - np.outer(s, self.n)
            pw, _ = self.warp(pts)
            sp = cu.splines.new('POLY')
            sp.points.add(N - 1)
            sp.points.foreach_set('co', np.concatenate([pw, np.ones((N, 1))], axis=1).ravel())
        cu.materials.append(self.lmat)
        o = bpy.data.objects.new(cu.name, cu)
        bpy.context.scene.collection.objects.link(o)
        o.visible_shadow = False
        self.fx.append(o)

    # ------------------------------------------------------------------ lightning
    def _bolts(self, tick):
        rnd = random.Random(self.seed * 977 + tick)
        W, q = self.W[self.sub], self.q[self.sub]
        z = (W - self.AT) @ self.n
        pairs = []
        neck = np.where((q > 0.05) & (q < 0.85) & (z > -self.Dm * 0.5))[0]
        if len(neck) > 40:                                        # crawling along the drawn-out section
            order = neck[np.argsort(z[neck])]
            for chain in range(1):
                m = rnd.randint(3, 4)
                k0 = rnd.uniform(0.0, 0.6)
                ks = sorted(k0 + rnd.uniform(0.0, 0.4) for _ in range(m))
                idx = [order[min(len(order) - 1, int(kk * len(order)))] for kk in ks]
                for i0, i1 in zip(idx, idx[1:]):
                    if np.linalg.norm(W[i0] - W[i1]) > 0.02 * self.L:
                        pairs.append((W[i0], W[i1]))
        near = np.where((z > self.zf * self.L * 0.35) & (z < self.zf * self.L * 1.25))[0]
        if len(near) > 10:                                        # snapping from the tick ring to the hull
            for _ in range(2):
                a = rnd.uniform(0, 2 * math.pi)
                rp = np.array(Vector(self.AT) + (self.e1v * math.cos(a) + self.e2v * math.sin(a)) * (0.545 * self.S)
                              + self.nv * 4.0)
                j = near[np.argmin(np.linalg.norm(W[near] - rp, axis=1))]
                pairs.append((rp, W[j]))
        if pairs:
            self.fx.append(_bolt_curve(self.k, pairs, rnd, self.bolt_w, self.bmat))


def _jag(p0, p1, rnd, jag, depth):
    pts = [np.array(p0, dtype=np.float64), np.array(p1, dtype=np.float64)]
    for _ in range(depth):
        new = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            d = b - a
            ln = np.linalg.norm(d)
            r = np.array([rnd.uniform(-1, 1) for _ in range(3)])
            if ln > 1e-6:
                r -= d * (r @ d) / (ln * ln)
            new += [(a + b) / 2 + r * ln * jag * rnd.uniform(0.3, 1.0), b]
        pts = new
    return pts


def _bolt_curve(k, pairs, rnd, width, mat, jag=0.19):
    """Crisp lightning: thin jagged tapering lines (one curve object), a short fork on some."""
    cu = bpy.data.curves.new(k.uid('Zap'), 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = width
    cu.bevel_resolution = 0
    lines = []
    for a, b in pairs:
        pts = _jag(a, b, rnd, jag, 5)
        lines.append((pts, 1.0))
        n = len(pts)
        if rnd.random() < 0.7:
            i = rnd.randrange(n // 4, 3 * n // 4)
            d = pts[min(i + 3, n - 1)] - pts[max(i - 3, 0)]
            r = np.array([rnd.uniform(-1, 1) for _ in range(3)])
            ln = float(np.linalg.norm(np.array(b) - np.array(a)))
            end = pts[i] + (d / (np.linalg.norm(d) + 1e-9) + r * 0.7) * ln * rnd.uniform(0.12, 0.25)
            lines.append((_jag(pts[i], end, rnd, jag, 3), 0.55))
    for pts, wk in lines:
        n = len(pts)
        sp = cu.splines.new('POLY')
        sp.points.add(n - 1)
        sp.points.foreach_set('co', np.concatenate([np.array(pts), np.ones((n, 1))], axis=1).ravel())
        sp.points.foreach_set('radius', [wk * (1.0 - 0.6 * i / (n - 1)) for i in range(n)])
    cu.materials.append(mat)
    o = bpy.data.objects.new(cu.name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.visible_shadow = False
    return o


class Pulse:
    """The crisp ring pulse that leaves the portal when a ship snaps free: thin flat rings in the portal plane."""

    def __init__(self, k, AT, n, S, rings=2):
        self.rings = rings
        self.k, self.AT, self.nv, self.S = k, Vector(AT), Vector(n).normalized(), S
        self.obs = []

    def set(self, age, life=16.0, z0=0.0, speed=0.0):
        """age: frames since the snap (None or past life: nothing). The rings start at z0 in front of the portal
        plane (where the tail came free) and are thrown forward at `speed` per frame while they open."""
        for o in self.obs:
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)
        self.obs = []
        if age is None or age < 0 or age > life:
            return
        t = age / life
        R = self.S * 0.5
        for j, (lag, wd, st) in enumerate(((0.0, 0.0065, 60.0), (0.22, 0.0028, 22.0))[:self.rings]):
            tt = t - lag
            if tt <= 0:
                continue
            r = R * (0.16 + 1.25 * (1 - (1 - tt) ** 2.0))
            fade = (1 - tt) ** 1.5
            w = self.S * wd * (0.6 + 0.4 * fade)
            nm = self.k.uid('Pulse')
            o = K.PO._annulus(nm, r - w, r + w, 0.0, segs=256)
            o.data.materials.append(K.C.emit_mat(nm + 'M', K.HOTGOLD, st * fade))
            o.location = self.AT + self.nv * (z0 + speed * age * (1.0 - 0.45 * j))
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = self.nv.to_track_quat('Z', 'Y')
            o.visible_shadow = False
            self.obs.append(o)
