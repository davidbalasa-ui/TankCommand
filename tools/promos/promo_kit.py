"""Shared scene toolkit for the 6-second unit promo clips.

Every clip is one script in scenes/<clip_id>.py that builds its scene with this kit and renders:

    /home/user/artenv/venv/bin/python tools/promos/scenes/<clip_id>.py --quality preview
    /home/user/artenv/venv/bin/python tools/promos/scenes/<clip_id>.py --quality final

Models are loaded BY NAME from models.json, never by path, so a remodelled unit only needs a
re-render. The file named in models.json is looked up in, in order:
    $PROMO_MODELS, /mnt/project-files/promos/models, <repo>/public/assets/models
so dropping a newer human/lancer.glb into /mnt/project-files/promos/models/human/ overrides the
game's copy without touching any script.

Conventions (Blender space): Z up, metres, ground at z=0. A heading of 0 deg faces +X, 90 deg
faces +Y. Ground units are about 4.5 m long (game scale), structures ~2.5 m per game cell.
Times are in seconds from the clip start; P.T(sec) turns them into frames.
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys

import bpy  # noqa: I001  (bpy must come before bmesh)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
REGISTRY = json.load(open(os.path.join(HERE, 'models.json')))
SEARCH = [p for p in [os.environ.get('PROMO_MODELS'), '/mnt/project-files/promos/models',
                      os.path.join(REPO, 'public', 'assets', 'models')] if p]
OUT_ROOT = os.environ.get('PROMO_OUT', '/mnt/project-files/promos')

QUALITY = {
    # res, samples, frame step, motion blur
    'still': ((960, 540), 12, 1, False),
    'preview': ((640, 360), 6, 2, False),
    'final': ((1280, 720), 10, 1, True),
}

# Faction / weapon colours (linear RGB). Terran: neon blue + orange accents. Arcadian: gold
# lightning, gold cores. Role glows on Arcadians: miner/tug ember orange, repair/sensor pale gold.
COL = {
    'terran_neon': (0.15, 0.55, 1.0),
    'terran_orange': (1.0, 0.42, 0.08),
    'tracer': (1.0, 0.62, 0.22),
    'laser_blue': (0.25, 0.65, 1.0),
    'arc_gold': (1.0, 0.5, 0.06),
    'arc_white': (1.0, 0.92, 0.7),
    'arc_ember': (1.0, 0.38, 0.08),
    'fire': (1.0, 0.45, 0.1),
    'shield_blue': (0.3, 0.6, 1.0),
    'repair_green': (0.35, 1.0, 0.55),
    'shard_violet': (0.75, 0.35, 1.0),
}


def resolve(name):
    """Registry entry for `name` with an absolute 'path'."""
    if name not in REGISTRY:
        raise KeyError(f'{name!r} is not in models.json')
    e = dict(REGISTRY[name])
    for root in SEARCH:
        p = os.path.join(root, e['file'])
        if os.path.exists(p):
            e['path'] = p
            return e
    raise FileNotFoundError(f'{e["file"]} not found in {SEARCH}')


# ------------------------------------------------------------------------------------- helpers
def link(o, col=None):
    (col or bpy.context.scene.collection).objects.link(o)
    return o


def set_interp(obj, kind='BEZIER'):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    for fc in _fcurves(ad.action):
        for k in fc.keyframe_points:
            k.interpolation = kind


def _fcurves(action):
    """F-curves of an action (Blender 5 keeps them in layered channelbags)."""
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                out.extend(bag.fcurves)
    return out


def key_hide(obj, frame, hidden):
    """Key render (and viewport) visibility with constant interpolation."""
    obj.hide_render = hidden
    obj.hide_viewport = False
    obj.keyframe_insert('hide_render', frame=frame)
    ad = obj.animation_data
    if ad and ad.action:
        for fc in _fcurves(ad.action):
            if fc.data_path == 'hide_render':
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT'


def show_between(obj, f0, f1):
    """Visible only from frame f0 up to (not including) f1. Applies to children too."""
    for o in [obj] + list(obj.children_recursive):
        key_hide(o, 0, True)
        key_hide(o, f0, False)
        key_hide(o, f1, True)


def emit_mat(name, col, strength=8.0, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*col, 1)
    em.inputs['Strength'].default_value = strength
    if alpha is None:
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    else:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    return m


def key_strength(mat, frame, value):
    em = mat.node_tree.nodes[mat['emit_node']]
    em.inputs['Strength'].default_value = value
    em.inputs['Strength'].keyframe_insert('default_value', frame=frame)


def pbr_mat(name, col, rough=0.6, metal=0.0, alpha=1.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    return m


def sphere(name, r=1.0, mat=None, seg=(12, 8), loc=(0, 0, 0), scale=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=r)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = link(bpy.data.objects.new(name, me))
    o.location = loc
    if scale:
        o.scale = scale
    if mat:
        me.materials.append(mat)
    return o


def ico(name, r=1.0, mat=None, sub=1, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(name, me))
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def cube(name, size=1.0, mat=None, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(name, me))
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def empty(name, loc=(0, 0, 0)):
    o = link(bpy.data.objects.new(name, None))
    o.location = loc
    o.empty_display_size = 0.5
    return o


def polyline(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 1
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1)
    o = link(bpy.data.objects.new(name, cu))
    cu.materials.append(mat)
    return o


def V(p):
    return Vector((p[0], p[1], p[2] if len(p) > 2 else 0.0))


def heading_of(d):
    return math.degrees(math.atan2(d[1], d[0]))


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------------------------- Actor
class Actor:
    """A loaded model: `root` is an empty you animate; the model hangs under it, normalised to
    its registry size, centred, standing on z=0 and facing +X."""

    def __init__(self, promo, name, entry, root, model_root, meshes):
        self.P = promo
        self.name = name
        self.entry = entry
        self.root = root
        self.model_root = model_root
        self.meshes = meshes
        self.size = entry['size']
        self.parts = {}
        for o in [model_root] + list(model_root.children_recursive):
            base = o.name.split('.')[0]
            self.parts.setdefault(base, o)
        self.turret = self.parts.get('TurretPivot')
        self.barrels = []
        self._muzzles = []
        self.alive_until = None

    # -- placement & motion --------------------------------------------------------------
    def place(self, at, heading=0.0, z=0.0, t=None):
        self.root.location = (at[0], at[1], at[2] if len(at) > 2 else z)
        self.root.rotation_euler = (0, 0, math.radians(heading))
        if t is not None:
            self.root.keyframe_insert('location', frame=self.P.T(t))
            self.root.keyframe_insert('rotation_euler', frame=self.P.T(t))
        return self

    def path(self, keys, face=True, interp='BEZIER', z=None, bank=0.0, pitch=False, lead=0.05):
        """keys: [(sec, (x, y[, z])), ...]. Faces along the direction of travel unless face=False.
        Heading at each key is taken from the path tangent; give a 3rd item (heading deg) in a
        key to override it there. bank: degrees of roll per unit of turn rate (aircraft)."""
        P = self.P
        pts = [(k[0], V(k[1]) if z is None else Vector((k[1][0], k[1][1], z))) for k in keys]
        prev_h = None
        heads = []
        for i, (t, p) in enumerate(pts):
            if len(keys[i]) > 2 and keys[i][2] is not None:
                h = keys[i][2]
            elif face and len(pts) > 1:
                a = pts[max(i - 1, 0)][1]
                b = pts[min(i + 1, len(pts) - 1)][1]
                d = b - a
                h = heading_of(d) if d.length > 1e-4 else (prev_h if prev_h is not None else math.degrees(self.root.rotation_euler.z))
            else:
                h = math.degrees(self.root.rotation_euler.z)
            if prev_h is not None:
                while h - prev_h > 180:
                    h -= 360
                while h - prev_h < -180:
                    h += 360
            heads.append(h)
            prev_h = h
        for i, (t, p) in enumerate(pts):
            self.root.location = p
            roll = 0.0
            pit = 0.0
            if bank and 0 < i < len(pts) - 1:
                dh = (heads[i + 1] - heads[i - 1]) / max(1e-3, pts[i + 1][0] - pts[i - 1][0])
                roll = max(-60, min(60, -dh * bank))
            if pitch and 0 < i < len(pts) - 1:
                d = pts[i + 1][1] - pts[i - 1][1]
                horiz = math.hypot(d.x, d.y)
                pit = -math.degrees(math.atan2(d.z, max(horiz, 1e-3)))
            self.root.rotation_euler = (math.radians(roll), math.radians(pit), math.radians(heads[i]))
            self.root.keyframe_insert('location', frame=P.T(t))
            self.root.keyframe_insert('rotation_euler', frame=P.T(t))
        set_interp(self.root, interp)
        return self

    def hover_bob(self, amp=0.12, hz=0.7, t0=0.0, t1=None):
        """Gentle float for hover units: adds a sine on the model (not the root), so it stacks
        with path()."""
        P = self.P
        t1 = P.seconds if t1 is None else t1
        m = self.model_root
        base = m.location.z
        n = int((t1 - t0) * hz * 4) + 1
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            m.location.z = base + amp * math.sin(2 * math.pi * hz * t)
            m.keyframe_insert('location', index=2, frame=P.T(t))
        return self

    def pos_at(self, t):
        """World position of the root at time t (evaluates the animation)."""
        P = self.P
        sc = bpy.context.scene
        cur = sc.frame_current
        sc.frame_set(int(round(P.T(t))))
        p = self.root.matrix_world.translation.copy()
        sc.frame_set(cur)
        return p

    def world_at(self, obj, t, local=(0, 0, 0)):
        sc = bpy.context.scene
        cur = sc.frame_current
        sc.frame_set(int(round(self.P.T(t))))
        p = obj.matrix_world @ Vector(local)
        sc.frame_set(cur)
        return p

    # -- turret ------------------------------------------------------------------------------
    def aim(self, t, target, dur=0.35, t_hold=None):
        """Turn the turret to face `target` (point, or Actor) arriving at time t. Starts turning
        `dur` seconds earlier from wherever it was."""
        if not self.turret:
            return self
        P = self.P
        tgt = target.pos_at(t) + Vector((0, 0, 1.0)) if isinstance(target, Actor) else V(target)
        sc = bpy.context.scene
        cur = sc.frame_current
        tu = self.turret
        tu.rotation_mode = 'XYZ'
        sc.frame_set(int(round(P.T(max(0, t - dur)))))
        start = tu.rotation_euler.z
        sc.frame_set(int(round(P.T(t))))
        parent_inv = tu.parent.matrix_world.inverted() if tu.parent else Matrix()
        local = parent_inv @ tgt
        piv = tu.matrix_basis.translation
        d = local - piv
        yaw = math.atan2(d.y, d.x)
        while yaw - start > math.pi:
            yaw -= 2 * math.pi
        while yaw - start < -math.pi:
            yaw += 2 * math.pi
        sc.frame_set(cur)
        tu.rotation_euler.z = start
        tu.keyframe_insert('rotation_euler', index=2, frame=P.T(max(0, t - dur)))
        tu.rotation_euler.z = yaw
        tu.keyframe_insert('rotation_euler', index=2, frame=P.T(t))
        if t_hold is not None:
            tu.keyframe_insert('rotation_euler', index=2, frame=P.T(t_hold))
        return self

    def turret_yaw(self, keys):
        """keys: [(sec, deg)] turret yaw relative to the hull."""
        if not self.turret:
            return self
        self.turret.rotation_mode = 'XYZ'
        for t, d in keys:
            self.turret.rotation_euler.z = math.radians(d)
            self.turret.keyframe_insert('rotation_euler', index=2, frame=self.P.T(t))
        return self

    def split_barrels(self, max_frac=0.45, thin=0.42):
        """Cut the gun barrel(s) off the turret mesh into their own object(s) so they can
        collapse back on recoil. Heuristic: the front-most run of thin cross-sections along +X.
        Returns the barrel objects (also self.barrels)."""
        if self.barrels:
            return self.barrels
        host = None
        if self.turret:
            kids = [c for c in self.turret.children if c.type == 'MESH']
            host = max(kids, key=lambda o: len(o.data.vertices)) if kids else None
        if host is None:
            return []
        if host.data.users > 1:     # P.copy shares mesh data: cut a private copy
            host.data = host.data.copy()
        me = host.data
        xs = [v.co.x for v in me.vertices]
        x0, x1 = min(xs), max(xs)
        L = x1 - x0
        if L <= 0:
            return []
        n = 40
        ext = []
        for i in range(n):
            a = x0 + L * i / n
            b = x0 + L * (i + 1) / n
            vs = [v.co for v in me.vertices if a <= v.co.x < b]
            if not vs:
                ext.append(0)
                continue
            ext.append(max(max(v.y for v in vs) - min(v.y for v in vs), max(v.z for v in vs) - min(v.z for v in vs)))
        full = max(ext)
        cut = None
        for i in range(n - 1, int(n * (1 - max_frac)) - 1, -1):
            if ext[i] > thin * full:
                cut = x0 + L * (i + 1) / n
                break
        if cut is None:
            cut = x0 + L * (1 - max_frac)
        if x1 - cut < 0.08 * L:
            return []
        bm = bmesh.new()
        bm.from_mesh(me)
        front = [f for f in bm.faces if f.calc_center_median().x > cut]
        if not front:
            bm.free()
            return []
        bm2 = bm.copy()
        bmesh.ops.delete(bm, geom=front, context='FACES')
        bm.to_mesh(me)
        bm.free()
        back = [f for f in bm2.faces if f.calc_center_median().x <= cut]
        bmesh.ops.delete(bm2, geom=back, context='FACES')
        me2 = bpy.data.meshes.new(host.name + '_Barrel')
        bm2.to_mesh(me2)
        bm2.free()
        for m in me.materials:
            me2.materials.append(m)
        b = link(bpy.data.objects.new(host.name + '_Barrel', me2))
        b.parent = host
        b['barrel_len'] = x1 - cut
        b['tip_x'] = x1
        self.barrels = [b]
        return self.barrels

    def muzzle(self):
        """Muzzle point object (parented so it follows the turret/hull)."""
        if self._muzzles:
            return self._muzzles[0]
        host = None
        if self.turret:
            kids = [c for c in self.turret.children if c.type == 'MESH']
            host = max(kids, key=lambda o: len(o.data.vertices)) if kids else None
        if host is None:
            host = max(self.meshes, key=lambda o: len(o.data.vertices))
        vs = [v.co for v in host.data.vertices]
        if self.barrels:
            bvs = [v.co for v in self.barrels[0].data.vertices]
            tip = max(bvs, key=lambda c: c.x)
            yz = [c for c in bvs if c.x > tip.x - 0.05 * (tip.x - min(v.x for v in bvs))]
            loc = Vector((tip.x, sum(c.y for c in yz) / len(yz), sum(c.z for c in yz) / len(yz)))
        else:
            mx = max(v.x for v in vs)
            front = [c for c in vs if c.x > mx - 0.08]
            loc = Vector((mx, sum(c.y for c in front) / len(front), sum(c.z for c in front) / len(front)))
        m = empty(self.name + '_Muzzle')
        # ride on the barrel when it is split (raises / recoils with it; the barrel shares the
        # host's local frame), else on the turret/hull mesh
        m.parent = self.barrels[0] if self.barrels else host
        m.location = loc
        self._muzzles = [m]
        return m

    def recoil(self, t, collapse=0.8, kick=4.0, back=0.25, settle=0.45):
        """Firing motion: barrel collapses `collapse` of its length into the turret and slides
        back out, turret jolts back, hull pitches nose-up by `kick` degrees and settles."""
        P = self.P
        f = P.T(t)
        last = getattr(self, '_last_recoil', -99)
        burst = (t - last) < settle  # previous shot still settling: don't key a rest pose before
        self._last_recoil = t
        for b in self.barrels:
            L = b['barrel_len'] * collapse
            b.location.x = -L * 0.3 if burst else 0
            b.keyframe_insert('location', index=0, frame=f - 1)
            b.location.x = -L
            b.keyframe_insert('location', index=0, frame=f + 1)
            b.location.x = 0
            b.keyframe_insert('location', index=0, frame=f + P.fps * settle)
        m = self.model_root
        m.rotation_mode = 'XYZ'
        base_y = getattr(self, '_rest_pitch', None)
        if base_y is None:
            base_y = self._rest_pitch = m.rotation_euler.y
            self._rest_x = m.location.x
        base_x = self._rest_x
        if not burst:
            m.rotation_euler.y = base_y
            m.location.x = base_x
            m.keyframe_insert('rotation_euler', index=1, frame=f - 1)
            m.keyframe_insert('location', index=0, frame=f - 1)
        m.rotation_euler.y = base_y - math.radians(kick)
        m.location.x = base_x - back
        m.keyframe_insert('rotation_euler', index=1, frame=f + 2)
        m.keyframe_insert('location', index=0, frame=f + 2)
        m.rotation_euler.y = base_y + math.radians(kick) * 0.25
        m.keyframe_insert('rotation_euler', index=1, frame=f + 2 + P.fps * settle * 0.5)
        m.rotation_euler.y = base_y
        m.location.x = base_x
        m.keyframe_insert('rotation_euler', index=1, frame=f + P.fps * settle)
        m.keyframe_insert('location', index=0, frame=f + P.fps * settle)
        return self

    def fire(self, t, target, kind='cannon', color=None, speed=None, size=1.0, recoil=True,
             kick=None, impact=True, impact_size=None, arc=None, muzzle=None, spread=0.0,
             jag=None, branches=None, width=None):
        """Fire one shot at `target` (point or Actor) at time t. Returns the impact time.
        kind: cannon | heavy | autocannon | laser | missile | shell | lightning | beam | bomb
        jag / branches / width: lightning shape (defaults 0.18 / 2 / 0.05 x size); width also
        sets beam and laser thickness."""
        P = self.P
        mz = muzzle or self.muzzle()
        p0 = self.world_at(mz, t - 1.0 / P.fps)   # the muzzle just before recoil starts
        if isinstance(target, Actor):
            p1 = target.pos_at(t + 0.15) + Vector((0, 0, target.size * 0.18))
        else:
            p1 = V(target)
        if spread:
            p1 = p1 + Vector((P.rnd.uniform(-spread, spread), P.rnd.uniform(-spread, spread), 0))
        spec = dict(
            cannon=(COL['tracer'], 60, 0.9, 4.0, 1.0),
            heavy=(COL['tracer'], 50, 1.6, 7.0, 1.8),
            autocannon=(COL['tracer'], 80, 0.45, 1.5, 0.45),
            laser=(COL['laser_blue'], 140, 0.6, 1.5, 0.5),
            missile=(COL['fire'], 32, 0.7, 2.5, 1.2),
            shell=(COL['tracer'], 35, 1.0, 5.0, 1.6),
            lightning=(COL['arc_gold'], 0, 0.6, 1.5, 0.45),
            beam=(COL['arc_gold'], 0, 1.0, 1.0, 1.4),
            bomb=(COL['fire'], 18, 0.0, 0.0, 2.2),
        )[kind]
        col = color or spec[0]
        spd = speed or spec[1]
        flash = spec[2] * size
        kk = spec[3] if kick is None else kick
        isz = (impact_size or spec[4]) * size
        if flash > 0:
            P.muzzle_flash(mz, t, col if kind in ('laser', 'lightning', 'beam') else COL['fire'], flash)
        if recoil and kk > 0:
            self.recoil(t, kick=kk, back=0.05 * kk)
        if kind in ('lightning',):
            P.lightning(p0, p1, t, t + 0.18, color=col, width=width if width is not None else 0.05 * size,
                        jag=0.18 if jag is None else jag, branches=2 if branches is None else branches)
            t_hit = t + 0.02
        elif kind == 'beam':
            P.beam(p0, p1, t, t + 0.45, color=col, width=width if width is not None else 0.18 * size)
            t_hit = t + 0.05
        elif kind == 'missile':
            t_hit = P.missile(p0, p1, t, speed=spd, color=col, arc=arc if arc is not None else 2.5)
        elif kind == 'laser':
            # Terran laser: a short beam zap that lands instantly (core + glow + scrolling energy)
            import promo_fx_weapons as W
            t_hit = t + 0.02
            W.beam(P, p0, p1, t, t + 0.14 * max(1.0, size), color=col,
                   width=width if width is not None else 0.07 * size, strength=9)
        elif kind in ('shell', 'bomb'):
            import promo_fx_weapons as W
            t_hit = W.projectile(P, p0, p1, t, spd, col, size=0.18 * size,
                                 arc=arc if arc is not None else (0.35 * (p1 - p0).length if kind == 'shell' else 0),
                                 streak=kind == 'shell', style=kind)
        else:
            t_hit = P.projectile(p0, p1, t, speed=spd, color=col, size=(0.1 if kind == 'autocannon' else 0.16) * size)
        if impact:
            P.impact(p1, t_hit, size=isz, color=col if kind in ('laser', 'lightning', 'beam') else None)
        return t_hit

    # -- life & death ------------------------------------------------------------------------
    def appear(self, t):
        for o in [self.root] + list(self.root.children_recursive):
            key_hide(o, 0, True)
            key_hide(o, self.P.T(t), False)
        return self

    def vanish(self, t):
        for o in [self.root] + list(self.root.children_recursive):
            key_hide(o, 0, o.hide_render)
            key_hide(o, self.P.T(t), True)
        return self

    def destroy(self, t, size=None, wreck=True, debris=14):
        """Big explosion; the unit breaks into pieces of its own model (promo_fx): a burning,
        smoking wreck plus flying debris (wreck=False: debris only, no fire)."""
        P = self.P
        import promo_fx
        if promo_fx.find_flipbook('explo_ground') and promo_fx.destroy(self, t, size=size, wreck=wreck, debris=debris):
            self.vanish(t + 1 / P.fps)
            self.alive_until = t
            return self
        size = size or self.size * 0.5
        p = self.pos_at(t)
        P.explosion(p + Vector((0, 0, self.size * 0.15)), t, size=size, debris=debris)
        if wreck:
            sc = bpy.context.scene
            sc.frame_set(int(round(P.T(t))))
            w = empty(self.name + '_Wreck')
            w.matrix_world = self.root.matrix_world.copy()
            w.rotation_euler.x += math.radians(P.rnd.uniform(-6, 6))
            w.rotation_euler.y += math.radians(P.rnd.uniform(-6, 6))
            for m in self.meshes:
                c = m.copy()
                link(c)
                c.animation_data_clear()
                mw = m.matrix_world.copy()
                c.parent = w
                c.matrix_world = mw
                for s in c.material_slots:
                    s.link = 'OBJECT'
                    s.material = P.charred
            for b in self.barrels:
                pass
            w.location.z = P.ground_z(w.location.x, w.location.y) - 0.15   # hover units crash down
            for o in [w] + list(w.children_recursive):
                key_hide(o, 0, True)
                key_hide(o, P.T(t) + 1, False)
            P.smoke_column(p, t + 0.2, P.seconds, size=size * 0.35)
            P.fire_patch(p + Vector((0, 0, 0.4)), t + 0.1, P.seconds, size=size * 0.35)
        self.vanish(t + 1 / P.fps)
        self.alive_until = t
        return self

    def spin(self, part, rate_deg_s, t0=0.0, t1=None, axis=2):
        """Spin a named pivot (e.g. 'DrumPivot', 'BladesPivot') at rate deg/s."""
        P = self.P
        t1 = P.seconds if t1 is None else t1
        o = self.parts.get(part)
        if o is None:
            return self
        o.rotation_mode = 'XYZ'
        base = o.rotation_euler[axis]
        o.keyframe_insert('rotation_euler', index=axis, frame=P.T(t0))
        o.rotation_euler[axis] = base + math.radians(rate_deg_s * (t1 - t0))
        o.keyframe_insert('rotation_euler', index=axis, frame=P.T(t1))
        ad = o.animation_data
        for fc in _fcurves(ad.action):
            if fc.data_path == 'rotation_euler' and fc.array_index == axis:
                for k in fc.keyframe_points:
                    if k.co.x in (P.T(t0), P.T(t1)):
                        k.interpolation = 'LINEAR'
        return self

    # -- structures ---------------------------------------------------------------------------
    def unfold(self, t0, t1, stagger=0.0):
        """Animate a structure from its packed pose (glTF extras) to deployed. Parts unfold one
        after another (`stagger` of the span each), the folded Carrier hull hides at the end."""
        P = self.P
        parts = []
        for o in [self.model_root] + list(self.model_root.children_recursive):
            if 'packed' in o.keys():
                parts.append(o)
        if not parts:
            return self
        order = sorted(parts, key=lambda o: (o.name.split('.')[0] != 'Base', o.name.split('.')[0] == 'TurretPivot'))
        span = t1 - t0
        for i, o in enumerate(order):
            pk = o['packed']
            p = pk['p']
            r = pk['r']
            s = pk['s']
            dep_loc = o.location.copy()
            dep_rot = o.rotation_quaternion.copy()
            dep_scale = o.scale.copy()
            o.rotation_mode = 'QUATERNION'
            # glTF (Y up) -> Blender (Z up): (x, y, z) -> (x, -z, y); quat (x,y,z,w) -> (w, x, -z, y)
            o.location = (p[0], -p[2], p[1])
            o.rotation_quaternion = (r[3], r[0], -r[2], r[1])
            o.scale = (s[0], s[2], s[1])
            n = len(order)
            # stagger 0: all parts move together (no floating gaps); >0: each part starts
            # stagger*span after the previous one.
            a = t0 + min(span * 0.8, span * stagger * i)
            b = t1
            for attr in ('location', 'rotation_quaternion', 'scale'):
                o.keyframe_insert(attr, frame=0)
                o.keyframe_insert(attr, frame=P.T(a))
            o.location, o.rotation_quaternion, o.scale = dep_loc, dep_rot, dep_scale
            for attr in ('location', 'rotation_quaternion', 'scale'):
                o.keyframe_insert(attr, frame=P.T(b))
            set_interp(o, 'BEZIER')
            if o.get('hideWhenDeployed'):
                for c in [o] + list(o.children_recursive):
                    key_hide(c, 0, False)
                    key_hide(c, P.T(t1), True)
        return self

    def packed_pose(self):
        """Hide deployed-only look at frame 0 (call unfold() for the animation)."""
        return self


# ------------------------------------------------------------------------------------- Promo
class Promo:
    def __init__(self, clip_id, seconds=6.0, fps=24, seed=1):
        ap = argparse.ArgumentParser()
        ap.add_argument('--quality', default='preview', choices=list(QUALITY))
        ap.add_argument('--out', default=None)
        ap.add_argument('--frames', default=None, help='a-b, or a single frame for a still')
        ap.add_argument('--no-render', action='store_true')
        ap.add_argument('--blend', action='store_true', help='also save the .blend')
        ap.add_argument('--resume', action='store_true', help='keep already rendered frames, render only missing ones')
        self.args, _ = ap.parse_known_args(sys.argv[1:])
        self.id = clip_id
        self.seconds = seconds
        self.fps = fps
        self.nf = int(round(seconds * fps))
        self.rnd = random.Random(seed)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.fps = fps
        sc.frame_start, sc.frame_end = 1, self.nf
        self.cam = None
        self.actors = []
        self.charred = pbr_mat('Charred', (0.025, 0.022, 0.02), rough=0.9)
        self.smoke_mat = pbr_mat('Smoke', (0.05, 0.048, 0.045), rough=1.0)
        self.dust_mat = pbr_mat('Dust', (0.38, 0.31, 0.24), rough=1.0)
        self._fireball = None
        self._clear = []

    def T(self, sec):
        return 1 + sec * self.fps

    # -- loading ---------------------------------------------------------------------------
    def load(self, name, at=(0, 0), heading=0.0, z=0.0, size=None, label=None):
        e = resolve(name)
        if e['kind'] == 'ship':
            return self._load_ship(name, e, at, heading, z, size, label)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=e['path'])
        new = [o for o in bpy.data.objects if o not in before]
        tops = [o for o in new if o.parent is None]
        model_root = empty((label or name) + '_Model')
        for o in tops:
            o.parent = model_root
        meshes = [o for o in new if o.type == 'MESH']
        bpy.context.view_layer.update()
        # normalise: max(length, width) -> size; centred; base on z=0. Structures ignore the
        # folded Carrier hull when measuring.
        meas = [o for o in meshes if not o.get('hideWhenDeployed')] or meshes
        lo = Vector((1e9, 1e9, 1e9))
        hi = -lo
        for o in meas:
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, w))
                hi = Vector(map(max, hi, w))
        ext = max(hi.x - lo.x, hi.y - lo.y)
        target = size or e['size']
        k = target / ext if ext > 0 else 1.0
        e['size'] = target
        e['height'] = (hi.z - lo.z) * k
        inner = empty((label or name) + '_Norm')
        inner.parent = model_root
        for o in tops:
            o.parent = inner
        inner.scale = (k, k, k)
        inner.location = (-(lo.x + hi.x) / 2 * k, -(lo.y + hi.y) / 2 * k, -lo.z * k)
        root = empty(label or name)
        model_root.parent = root
        a = Actor(self, label or name, e, root, model_root, meshes)
        a.place(at, heading, z)
        self.actors.append(a)
        return a

    def _load_ship(self, name, e, at, heading, z, size, label):
        with bpy.data.libraries.load(e['path'], link=False) as (src, dst):
            dst.objects = list(src.objects) if e['object'] == '*' else [n for n in src.objects]
        objs = [o for o in dst.objects if o is not None]
        for o in objs:
            link(o)
        tops = [o for o in objs if o.parent is None or o.parent not in objs]
        if e['object'] != '*':
            tops = [o for o in objs if o.name.split('.')[0] == e['object']] or tops
        model_root = empty((label or name) + '_Model')
        for o in tops:
            o.parent = model_root
        meshes = [o for o in objs if o.type == 'MESH']
        bpy.context.view_layer.update()
        lo = Vector((1e9, 1e9, 1e9))
        hi = -lo
        for o in meshes:
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, w))
                hi = Vector(map(max, hi, w))
        ext = max(hi.x - lo.x, hi.y - lo.y)
        target = size or e['size']
        k = target / ext if ext > 0 else 1.0
        e['size'] = target
        inner = empty((label or name) + '_Norm')
        inner.parent = model_root
        for o in tops:
            o.parent = inner
        inner.scale = (k, k, k)
        inner.location = (-(lo.x + hi.x) / 2 * k, -(lo.y + hi.y) / 2 * k, -(lo.z + hi.z) / 2 * k)
        root = empty(label or name)
        model_root.parent = root
        a = Actor(self, label or name, e, root, model_root, meshes)
        a.place(at, heading, z)
        self.actors.append(a)
        return a

    # -- environment -----------------------------------------------------------------------
    def env(self, kind='desert', sun=(42, 0, -35), sun_energy=4.0, radius=160, props=40,
            clear=None, deposits=None, seed=None):
        """Ground, sky and sun. kind: desert | highland | alien | dusk | ash.
        clear: [(x, y, r)] circles kept free of scattered props (the action area).
        deposits: [('ore'|'metal', (x, y), scale)] resource sites to place."""
        pal = {
            'desert': dict(g1=(0.33, 0.22, 0.13), g2=(0.18, 0.12, 0.075), sky=(0.42, 0.6, 0.85), hor=(0.85, 0.75, 0.62), sunc=(1.0, 0.93, 0.82)),
            'highland': dict(g1=(0.2, 0.2, 0.14), g2=(0.1, 0.11, 0.08), sky=(0.38, 0.55, 0.8), hor=(0.7, 0.74, 0.75), sunc=(1.0, 0.95, 0.88)),
            'alien': dict(g1=(0.3, 0.2, 0.22), g2=(0.13, 0.09, 0.12), sky=(0.3, 0.45, 0.62), hor=(0.85, 0.65, 0.6), sunc=(1.0, 0.88, 0.78)),
            'dusk': dict(g1=(0.28, 0.17, 0.1), g2=(0.12, 0.07, 0.05), sky=(0.18, 0.22, 0.42), hor=(1.0, 0.5, 0.25), sunc=(1.0, 0.62, 0.35)),
            'ash': dict(g1=(0.17, 0.16, 0.15), g2=(0.07, 0.065, 0.06), sky=(0.3, 0.32, 0.36), hor=(0.62, 0.55, 0.5), sunc=(1.0, 0.85, 0.7)),
        }[kind]
        self.palette = pal
        rnd = random.Random(seed if seed is not None else self.rnd.random())
        sc = bpy.context.scene
        # world: horizon -> zenith gradient
        w = bpy.data.worlds.new('World')
        sc.world = w
        w.use_nodes = True
        nt = w.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputWorld')
        bg = nt.nodes.new('ShaderNodeBackground')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = (*pal['hor'], 1)
        ramp.color_ramp.elements[1].position = 0.35
        ramp.color_ramp.elements[1].color = (*pal['sky'], 1)
        nt.links.new(tc.outputs['Generated'], sep.inputs[0])
        nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.9
        nt.links.new(bg.outputs[0], out.inputs[0])
        # Generated coords for world are the view direction normalised to 0..1? use Z of
        # direction remapped: (z+1)/2 -> bias so horizon (0.5) sits at ramp 0.
        mp = nt.nodes.new('ShaderNodeMapRange')
        mp.inputs['From Min'].default_value = 0.0
        mp.inputs['From Max'].default_value = 0.55
        nt.links.new(sep.outputs['Z'], mp.inputs['Value'])
        nt.links.new(mp.outputs['Result'], ramp.inputs['Fac'])
        # sun
        s = link(bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')))
        s.data.energy = sun_energy
        s.data.color = pal['sunc']
        s.data.angle = math.radians(2.0)
        s.rotation_euler = [math.radians(a) for a in sun]
        self.sun = s
        # ground: big subdivided plane, gentle displacement, procedural dirt + haze by distance
        me = bpy.data.meshes.new('Ground')
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=160, y_segments=160, size=radius)
        bm.to_mesh(me)
        bm.free()
        g = link(bpy.data.objects.new('Ground', me))
        tex = bpy.data.textures.new('GroundNoise', 'CLOUDS')
        tex.noise_scale = 18.0
        d = g.modifiers.new('Displace', 'DISPLACE')
        d.texture = tex
        d.strength = 1.2
        d.mid_level = 0.5
        self._ground_tex = tex
        for p in me.polygons:
            p.use_smooth = True
        m = bpy.data.materials.new('GroundMat')
        m.use_nodes = True
        n = m.node_tree.nodes
        L = m.node_tree.links
        b = n.get('Principled BSDF')
        b.inputs['Roughness'].default_value = 0.95
        coord = n.new('ShaderNodeTexCoord')
        nz = n.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 0.08
        nz.inputs['Detail'].default_value = 8
        L.new(coord.outputs['Object'], nz.inputs['Vector'])
        cr = n.new('ShaderNodeValToRGB')
        cr.color_ramp.elements[0].color = (*pal['g2'], 1)
        cr.color_ramp.elements[1].color = (*pal['g1'], 1)
        cr.color_ramp.elements[0].position = 0.35
        cr.color_ramp.elements[1].position = 0.65
        L.new(nz.outputs['Fac'], cr.inputs['Fac'])
        vo = n.new('ShaderNodeTexVoronoi')
        vo.inputs['Scale'].default_value = 1.6
        L.new(coord.outputs['Object'], vo.inputs['Vector'])
        mixc = n.new('ShaderNodeMix')
        mixc.data_type = 'RGBA'
        mixc.blend_type = 'MULTIPLY'
        mixc.inputs['Factor'].default_value = 0.25
        L.new(cr.outputs['Color'], mixc.inputs['A'])
        L.new(vo.outputs['Distance'], mixc.inputs['B'])
        # haze toward horizon colour with camera distance
        cam_d = n.new('ShaderNodeCameraData')
        hz = n.new('ShaderNodeMapRange')
        hz.inputs['From Min'].default_value = 45
        hz.inputs['From Max'].default_value = radius * 1.4
        L.new(cam_d.outputs['View Distance'], hz.inputs['Value'])
        hm = n.new('ShaderNodeMix')
        hm.data_type = 'RGBA'
        L.new(hz.outputs['Result'], hm.inputs['Factor'])
        L.new(mixc.outputs['Result'], hm.inputs['A'])
        hm.inputs['B'].default_value = (*[c * 0.8 for c in pal['hor']], 1)
        L.new(hm.outputs['Result'], b.inputs['Base Color'])
        bump = n.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.35
        nz2 = n.new('ShaderNodeTexNoise')
        nz2.inputs['Scale'].default_value = 2.5
        L.new(coord.outputs['Object'], nz2.inputs['Vector'])
        L.new(nz2.outputs['Fac'], bump.inputs['Height'])
        L.new(bump.outputs['Normal'], b.inputs['Normal'])
        me.materials.append(m)
        self.ground = g
        self._clear = list(clear or [])
        # resource deposits
        for kind_, at, k in (deposits or []):
            nm = 'deposit_ore' if kind_ == 'ore' else 'deposit_metal'
            a = self.load(nm, at=at, heading=rnd.uniform(0, 360), size=resolve(nm)['size'] * k)
            a.root.location.z = self.ground_z(at[0], at[1]) - 0.2
        # scatter props as linked duplicates of one import each
        if props:
            kinds = ['boulder', 'rock_cluster', 'shrub', 'dead_tree'] if kind != 'alien' else ['boulder', 'rock_cluster', 'tendril', 'slab']
            protos = {}
            for kd in kinds:
                protos[kd] = self.load(kd, at=(0, 0), label='proto_' + kd)
                for o in [protos[kd].root] + list(protos[kd].root.children_recursive):
                    o.hide_render = True
                    o.hide_viewport = True
            placed = 0
            tries = 0
            while placed < props and tries < props * 20:
                tries += 1
                r = rnd.uniform(8, radius * 0.55)
                th = rnd.uniform(0, 2 * math.pi)
                x, y = r * math.cos(th), r * math.sin(th)
                if any((x - cx) ** 2 + (y - cy) ** 2 < cr_ ** 2 for cx, cy, cr_ in self._clear):
                    continue
                kd = rnd.choice(kinds)
                pr = protos[kd]
                h = empty(f'prop_{kd}_{placed}')
                for o in pr.root.children_recursive:
                    pass
                inst = self._instance(pr.root, h)
                h.location = (x, y, self.ground_z(x, y) - 0.1)
                h.rotation_euler.z = rnd.uniform(0, 6.28)
                s_ = rnd.uniform(0.6, 1.5)
                h.scale = (s_, s_, s_)
                placed += 1
        return self

    def _instance(self, src_root, parent):
        """Linked-data copy of a hierarchy (cheap)."""
        def rec(o, par):
            c = o.copy()
            link(c)
            c.animation_data_clear()
            c.hide_render = False
            c.hide_viewport = False
            c.parent = par
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
            for ch in o.children:
                rec(ch, c)
            return c
        return rec(src_root, parent)

    def copy(self, actor, at=(0, 0), heading=0.0, z=0.0, label=None):
        """Another instance of an already loaded actor (shares mesh data, cheap). Animations
        are not copied."""
        root = empty(label or actor.name + '_copy')
        rec = self._instance(actor.model_root, root)
        meshes = [o for o in [rec] + list(rec.children_recursive) if o.type == 'MESH']
        a = Actor(self, label or actor.name + '_copy', dict(actor.entry), root, rec, meshes)
        a.place(at, heading, z)
        self.actors.append(a)
        return a

    def ground_z(self, x, y):
        """Approximate ground height at (x, y) (matches the Displace modifier)."""
        if not getattr(self, 'ground', None):
            return 0.0
        g = self.ground
        dg = bpy.context.evaluated_depsgraph_get()
        ev = g.evaluated_get(dg)
        origin = Vector((x, y, 50))
        ok, loc, nrm, idx = ev.ray_cast(origin, Vector((0, 0, -1)))
        return loc.z if ok else 0.0

    def flatten(self, x, y, r):
        """Keep the ground flat (z~0) inside a circle: the action area. Call before load()."""
        self._clear.append((x, y, r))
        g = self.ground
        mod = g.modifiers['Displace']
        vg = g.vertex_groups.get('Flat') or g.vertex_groups.new(name='Flat')
        mod.vertex_group = 'Flat'
        mod.invert_vertex_group = False
        # weight 1 = displaced, 0 = flat
        for v in g.data.vertices:
            d = math.hypot(v.co.x - x, v.co.y - y)
            wcur = 1.0
            try:
                wcur = vg.weight(v.index)
            except RuntimeError:
                wcur = 1.0
            w = min(wcur, smoothstep((d - r) / (r * 0.8 + 4)))
            vg.add([v.index], w, 'REPLACE')
        return self

    def space(self, stars=True, planet=None, nebula=(0.08, 0.03, 0.12), sun=(30, 0, 40), sun_energy=3.5):
        """Space backdrop: black with stars and a soft nebula; optional planet
        planet=(x, y, z, radius, (r, g, b))."""
        sc = bpy.context.scene
        w = bpy.data.worlds.new('Space')
        sc.world = w
        w.use_nodes = True
        nt = w.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputWorld')
        bg = nt.nodes.new('ShaderNodeBackground')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        vo = nt.nodes.new('ShaderNodeTexVoronoi')
        vo.inputs['Scale'].default_value = 420
        nt.links.new(tc.outputs['Generated'], vo.inputs['Vector'])
        st = nt.nodes.new('ShaderNodeMapRange')
        st.inputs['From Min'].default_value = 0.025
        st.inputs['From Max'].default_value = 0.0
        st.inputs['To Max'].default_value = 6.0
        nt.links.new(vo.outputs['Distance'], st.inputs['Value'])
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 2.2
        nz.inputs['Detail'].default_value = 6
        nt.links.new(tc.outputs['Generated'], nz.inputs['Vector'])
        neb = nt.nodes.new('ShaderNodeMix')
        neb.data_type = 'RGBA'
        neb.inputs['A'].default_value = (0.002, 0.002, 0.004, 1)
        neb.inputs['B'].default_value = (*nebula, 1)
        pw = nt.nodes.new('ShaderNodeMath')
        pw.operation = 'POWER'
        pw.inputs[1].default_value = 3.0
        nt.links.new(nz.outputs['Fac'], pw.inputs[0])
        nt.links.new(pw.outputs[0], neb.inputs['Factor'])
        add = nt.nodes.new('ShaderNodeMix')
        add.data_type = 'RGBA'
        add.blend_type = 'ADD'
        add.inputs['Factor'].default_value = 1.0
        nt.links.new(neb.outputs['Result'], add.inputs['A'])
        nt.links.new(st.outputs['Result'], add.inputs['B'])
        nt.links.new(add.outputs['Result'], bg.inputs['Color'])
        nt.links.new(bg.outputs[0], out.inputs[0])
        s = link(bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')))
        s.data.energy = sun_energy
        s.rotation_euler = [math.radians(a) for a in sun]
        self.sun = s
        self.ground = None
        if planet:
            x, y, z, r, c = planet
            pm = pbr_mat('Planet', c, rough=0.8)
            sphere('Planet', r, pm, seg=(64, 32), loc=(x, y, z))
            am = emit_mat('Atmo', (0.35, 0.55, 1.0), 0.6, alpha=0.25)
            sphere('Atmosphere', r * 1.02, am, seg=(64, 32), loc=(x, y, z))
        return self

    # -- camera ----------------------------------------------------------------------------
    def camera(self, keys, lens=35, shake=0.0, interp='BEZIER', cuts=()):
        """keys: [(sec, (x,y,z) position, (x,y,z) look-at[, lens])]. Look-at may also be an Actor
        (tracks it with a z offset of 1 m). shake: handheld wobble in metres."""
        sc = bpy.context.scene
        cam = link(bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')))
        sc.camera = cam
        cam.data.lens = lens
        cam.data.clip_start = 0.1
        cam.data.clip_end = 20000
        tgt = empty('CamTarget')
        con = cam.constraints.new('TRACK_TO')
        con.target = tgt
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        for k in keys:
            t, p, look = k[0], k[1], k[2]
            cam.location = p
            cam.keyframe_insert('location', frame=self.T(t))
            if isinstance(look, Actor):
                look = look.pos_at(t) + Vector((0, 0, 1.0))
            tgt.location = look
            tgt.keyframe_insert('location', frame=self.T(t))
            if len(k) > 3:
                cam.data.lens = k[3]
                cam.data.keyframe_insert('lens', frame=self.T(t))
        set_interp(cam, interp)
        set_interp(tgt, interp)
        # hard cuts: give a key just before the cut (e.g. t-1/24) and one at the cut; the
        # segment before it then holds still instead of drifting/overshooting into the next.
        for ob in (cam, tgt, cam.data):
            ad = ob.animation_data
            if not ad or not ad.action:
                continue
            for fc in _fcurves(ad.action):
                for k in fc.keyframe_points:
                    k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
                    for c in cuts:
                        fcut = self.T(c)
                        if fcut - 1.5 <= k.co.x < fcut - 0.01:
                            k.interpolation = 'CONSTANT'
        if shake:
            for i in range(3):
                fc = cam.animation_data.action and [f for f in _fcurves(cam.animation_data.action)
                                                    if f.data_path == 'location' and f.array_index == i]
                if fc:
                    md = fc[0].modifiers.new('NOISE')
                    md.scale = 12
                    md.strength = shake
                    md.phase = self.rnd.uniform(0, 100)
        self.cam = cam
        self.cam_target = tgt
        return cam

    def orbit(self, center, radius, height, deg0, deg1, t0=0.0, t1=None, lens=35, look_z=1.2,
              radius1=None, height1=None, steps=12, shake=0.0):
        """Camera circling `center` from deg0 to deg1 (counter-clockwise if deg1 > deg0) while
        optionally pushing in (radius1) or rising (height1)."""
        t1 = self.seconds if t1 is None else t1
        radius1 = radius if radius1 is None else radius1
        height1 = height if height1 is None else height1
        c = V(center)
        keys = []
        for i in range(steps + 1):
            u = i / steps
            a = math.radians(deg0 + (deg1 - deg0) * u)
            r = radius + (radius1 - radius) * smoothstep(u)
            h = height + (height1 - height) * smoothstep(u)
            keys.append((t0 + (t1 - t0) * u, (c.x + r * math.cos(a), c.y + r * math.sin(a), h),
                         (c.x, c.y, c.z + look_z)))
        return self.camera(keys, lens=lens, shake=shake, interp='BEZIER')

    def cam_shake(self, t, amount=0.15, dur=0.4):
        """A jolt (e.g. on a big explosion or heavy shot)."""
        cam = self.cam
        if cam is None:
            return
        f0 = self.T(t)
        n = int(dur * self.fps)
        base = [cam.matrix_world.translation]  # noqa
        for i in range(n + 1):
            k = amount * (1 - i / n)
            off = Vector((self.rnd.uniform(-k, k), self.rnd.uniform(-k, k), self.rnd.uniform(-k, k)))
            cam.delta_location = off if i < n else Vector()
            cam.keyframe_insert('delta_location', frame=f0 + i)
        cam.delta_location = Vector()
        cam.keyframe_insert('delta_location', frame=f0 - 1)

    # -- effects ---------------------------------------------------------------------------
    def light(self, pos, t, color, energy=2000, dur=0.2, radius=0.3):
        L = link(bpy.data.objects.new('FxLight', bpy.data.lights.new('FxLight', 'POINT')))
        L.location = pos
        L.data.color = color
        L.data.shadow_soft_size = radius
        L.data.energy = 0
        L.data.keyframe_insert('energy', frame=self.T(t) - 1)
        L.data.energy = energy
        L.data.keyframe_insert('energy', frame=self.T(t))
        L.data.energy = 0
        L.data.keyframe_insert('energy', frame=self.T(t + dur))
        return L

    def muzzle_flash(self, muzzle_obj, t, color, size=1.0):
        """Short star-shaped flash at a muzzle empty (follows it)."""
        import promo_fx_weapons as W
        return W.muzzle_flash(self, muzzle_obj, t, color, size)

    def projectile(self, p0, p1, t0, speed, color, size=0.15, arc=0.0, streak=True):
        """Glowing slug flying p0 -> p1 (with an optional ballistic arc). Returns hit time."""
        import promo_fx_weapons as W
        return W.projectile(self, p0, p1, t0, speed, color, size=size, arc=arc, streak=streak)

    def missile(self, p0, p1, t0, speed=32, color=None, arc=2.5, wobble=0.4, trail=True):
        """Missile with a smoke trail, flying a lofted path. Returns hit time."""
        import promo_fx_weapons as W
        return W.missile(self, p0, p1, t0, speed=speed, color=color, arc=arc, wobble=wobble, trail=trail)

    def lightning(self, p0, p1, t0, t1, color=None, width=0.05, jag=0.18, branches=2, segs=10, glow=True):
        """Arcadian gold lightning p0 -> p1, re-striking every 2-3 frames with forks. p0/p1 may be
        points, Actors, Objects or callables t -> point (moving ends are followed per frame)."""
        import promo_fx_weapons as W
        return W.lightning(self, p0, p1, t0, t1, color=color, width=width, jag=jag, branches=branches,
                           segs=segs, glow=glow)

    def beam(self, p0, p1, t0, t1, color, width=0.15, strength=10):
        """Solid energy beam with a flickering width."""
        import promo_fx_weapons as W
        return W.beam(self, p0, p1, t0, t1, color, width=width, strength=strength)

    def shot(self, p0, target, kind, t, color=None, **kw):
        """Fire from a point (ships without turrets): p0 = point, Actor, Object or
        (actor, local_offset) riding a moving ship; target = point, Actor or Object. Kinds and
        keywords as Actor.fire (size, speed, impact, impact_size, arc, spread, jag, branches,
        width, flash, dur). Returns the hit time."""
        import promo_fx_weapons as W
        return W.shot(self, p0, target, kind, t, color=color, **kw)

    def soft_mat(self):
        """Shared soft smoke/dust material: colour and opacity come from each object's
        Object Color (rgba), edges fade with the facing ratio so balls read as puffs."""
        if getattr(self, '_soft', None):
            return self._soft
        m = bpy.data.materials.new('SoftPuff')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        oi = nt.nodes.new('ShaderNodeObjectInfo')
        lw = nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.55
        inv = nt.nodes.new('ShaderNodeMath')
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        nt.links.new(lw.outputs['Facing'], inv.inputs[1])
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 2.5
        nz.inputs['Detail'].default_value = 3
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        m1 = nt.nodes.new('ShaderNodeMath')
        m1.operation = 'MULTIPLY'
        nt.links.new(inv.outputs[0], m1.inputs[0])
        nt.links.new(nz.outputs['Fac'], m1.inputs[1])
        m2 = nt.nodes.new('ShaderNodeMath')
        m2.operation = 'MULTIPLY'
        m2.use_clamp = True
        nt.links.new(m1.outputs[0], m2.inputs[0])
        nt.links.new(oi.outputs['Alpha'], m2.inputs[1])
        m3 = nt.nodes.new('ShaderNodeMath')
        m3.operation = 'MULTIPLY'
        m3.inputs[1].default_value = 1.5
        m3.use_clamp = True
        nt.links.new(m2.outputs[0], m3.inputs[0])
        df = nt.nodes.new('ShaderNodeBsdfDiffuse')
        nt.links.new(oi.outputs['Color'], df.inputs['Color'])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(m3.outputs[0], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(df.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        self._soft = m
        return m

    def puff(self, pos, t, size=0.6, n=3, rise=1.0, life=1.2, color=None, opacity=0.65):
        """A few soft smoke/dust puffs that grow, rise, drift and fade out."""
        mat = self.soft_mat()
        col = color or (0.3, 0.28, 0.26)
        for i in range(n):
            o = sphere('Puff', 1.0, mat, seg=(16, 10))
            p = V(pos) + Vector((self.rnd.uniform(-.3, .3), self.rnd.uniform(-.3, .3), self.rnd.uniform(0, .2))) * size
            f0 = self.T(t + i * 0.03)
            f1 = self.T(t + life)
            o.rotation_euler = (self.rnd.uniform(0, 6), self.rnd.uniform(0, 6), self.rnd.uniform(0, 6))
            o.location = p
            o.scale = (size * 0.3,) * 3
            o.color = (*col, opacity)
            o.keyframe_insert('location', frame=f0)
            o.keyframe_insert('scale', frame=f0)
            o.keyframe_insert('color', frame=f0)
            o.location = p + Vector((self.rnd.uniform(-.4, .4) * size, self.rnd.uniform(-.4, .4) * size, rise))
            o.scale = (size * 1.3,) * 3
            o.color = (*col, 0.0)
            o.keyframe_insert('location', frame=f1)
            o.keyframe_insert('scale', frame=f1)
            o.keyframe_insert('color', frame=f1)
            show_between(o, f0, f1)

    def dust(self, actor, t0, t1, every=0.1, size=0.7, color=None):
        """Dust kicked up behind a moving ground unit."""
        col = color or (self.palette['g1'] if hasattr(self, 'palette') else (0.35, 0.28, 0.2))
        t = t0
        while t < t1:
            p = actor.pos_at(t)
            back = actor.root.matrix_world.to_3x3() @ Vector((-actor.size * 0.45, 0, 0))
            self.puff(p + back + Vector((0, 0, 0.2)), t, size=size, n=1, rise=0.5, life=0.9,
                      color=tuple(min(1, c * 1.5) for c in col), opacity=0.45)
            t += every

    def fireball_mat(self):
        if self._fireball:
            return self._fireball
        m = bpy.data.materials.new('Fireball')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        em = nt.nodes.new('ShaderNodeEmission')
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 3.0
        nz.inputs['Detail'].default_value = 4
        cr = nt.nodes.new('ShaderNodeValToRGB')
        cr.color_ramp.elements[0].color = (0.9, 0.12, 0.01, 1)
        cr.color_ramp.elements[1].color = (1.0, 0.55, 0.12, 1)
        cr.color_ramp.elements[0].position = 0.4
        cr.color_ramp.elements[1].position = 0.7
        nt.links.new(nz.outputs['Fac'], cr.inputs['Fac'])
        nt.links.new(cr.outputs['Color'], em.inputs['Color'])
        em.inputs['Strength'].default_value = 3.5
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        m['emit_node'] = em.name
        self._fireball = m
        return m

    def explosion(self, pos, t, size=2.0, debris=8, smoke=True, light=True):
        """Fireball + flash + smoke + flying debris + scorch (flipbook cards via promo_fx; the
        procedural fallback below runs only when the flipbook library is missing)."""
        pos = V(pos)
        import promo_fx
        if promo_fx.explosion(self, pos, t, size=size, debris=debris, smoke=smoke, light=light):
            return self
        fm = self.fireball_mat()
        f0 = self.T(t)
        for i in range(5):
            o = ico('Fireball', 1.0, fm, sub=2)
            off = Vector((self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1), self.rnd.uniform(0, 0.8))) * size * 0.35
            o.location = pos + off
            o.rotation_euler = (self.rnd.uniform(0, 6), self.rnd.uniform(0, 6), self.rnd.uniform(0, 6))
            o.scale = (0.05,) * 3
            d = i * 0.025
            o.keyframe_insert('scale', frame=f0 + d * self.fps)
            o.scale = (size * self.rnd.uniform(0.45, 0.7),) * 3
            o.keyframe_insert('scale', frame=f0 + (d + 0.12) * self.fps)
            o.location = o.location + Vector((0, 0, size * 0.4))
            o.keyframe_insert('location', frame=f0 + (d + 0.5) * self.fps)
            o.scale = (0.02,) * 3
            o.keyframe_insert('scale', frame=f0 + (d + 0.55) * self.fps)
            show_between(o, f0 + d * self.fps, f0 + (d + 0.56) * self.fps)
        # white-hot core flash
        core = ico('Core', 1.0, emit_mat('Core', (1, 0.45, 0.1), 5), sub=2)
        core.location = pos
        core.scale = (0.1,) * 3
        core.keyframe_insert('scale', frame=f0)
        core.scale = (size * 0.5,) * 3
        core.keyframe_insert('scale', frame=f0 + 2)
        core.scale = (0.01,) * 3
        core.keyframe_insert('scale', frame=f0 + 5)
        show_between(core, f0, f0 + 5)
        if light:
            self.light(pos + Vector((0, 0, size * 0.5)), t, (1.0, 0.55, 0.2), energy=4000 * size, dur=0.5, radius=size * 0.5)
        if smoke:
            self.puff(pos + Vector((0, 0, size * 0.3)), t + 0.25, size=size * 0.9, n=4, rise=size * 1.2, life=2.2)
        for i in range(debris):
            o = ico('Debris', 1.0, self.charred, sub=0)
            s = size * self.rnd.uniform(0.02, 0.06)
            o.scale = (s, s * self.rnd.uniform(0.5, 1.5), s * self.rnd.uniform(0.3, 1))
            v = Vector((self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1), self.rnd.uniform(0.8, 2.2))) * size * 2.2
            life = self.rnd.uniform(0.6, 1.2)
            n = 6
            for k in range(n + 1):
                tt = life * k / n
                o.location = pos + Vector((v.x * tt, v.y * tt, max(-pos.z + 0.05, v.z * tt - 4.9 * tt * tt * 1.5)))
                o.rotation_euler = (tt * 9, tt * 7, tt * 5)
                o.keyframe_insert('location', frame=f0 + tt * self.fps)
                o.keyframe_insert('rotation_euler', frame=f0 + tt * self.fps)
            show_between(o, f0, f0 + life * self.fps)
        # scorch decal (ground bursts only)
        if hasattr(self, 'ground') and self.ground is None:     # space: no ground, no scorch
            return self
        if getattr(self, 'ground', None) and pos.z - self.ground_z(pos.x, pos.y) > max(1.2, size * 0.45):
            return self
        sc_ = sphere('Scorch', 1.0, pbr_mat('ScorchM', (0.015, 0.012, 0.01), 1.0), seg=(16, 6))
        sc_.location = (pos.x, pos.y, self.ground_z(pos.x, pos.y) + 0.02 if getattr(self, 'ground', None) else pos.z)
        sc_.scale = (size * 0.8, size * 0.8, 0.02)
        show_between(sc_, f0 + 2, self.T(self.seconds) + 1)
        return self

    def impact(self, pos, t, size=1.0, color=None):
        """Smaller hit: spark burst + dirt kick + flash. color tints energy hits."""
        import promo_fx_weapons as W
        return W.impact(self, pos, t, size=size, color=color)

    def smoke_column(self, pos, t0, t1, size=1.0, every=0.3):
        import promo_fx
        if promo_fx.smoke_column(self, pos, t0, t1, size=size):
            return
        t = t0
        while t < t1:
            self.puff(V(pos) + Vector((0, 0, 0.6)), t, size=size, n=1, rise=size * 3, life=2.0)
            t += every

    def soft_fire_mat(self):
        """Soft-edged emissive flame: colour from Object Color rgb, brightness from its alpha."""
        if getattr(self, '_softfire', None):
            return self._softfire
        m = bpy.data.materials.new('SoftFire')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        oi = nt.nodes.new('ShaderNodeObjectInfo')
        lw = nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.6
        inv = nt.nodes.new('ShaderNodeMath')
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        nt.links.new(lw.outputs['Facing'], inv.inputs[1])
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.use_clamp = True
        nt.links.new(inv.outputs[0], mul.inputs[0])
        nt.links.new(oi.outputs['Alpha'], mul.inputs[1])
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = 3.0
        nt.links.new(oi.outputs['Color'], em.inputs['Color'])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(mul.outputs[0], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        self._softfire = m
        return m

    def fire_patch(self, pos, t0, t1, size=0.6):
        """Flickering flames licking up off a wreck (looping flipbook cards via promo_fx)."""
        import promo_fx
        if promo_fx.fire_patch(self, pos, t0, t1, size=size):
            return
        fm = self.soft_fire_mat()
        for i in range(4):
            o = sphere('Flame', 1.0, fm, seg=(12, 8))
            o.location = V(pos) + Vector((self.rnd.uniform(-.4, .4), self.rnd.uniform(-.4, .4), 0)) * size * 2
            f = self.T(t0)
            while f < self.T(t1):
                s_ = size * self.rnd.uniform(0.25, 0.45)
                o.scale = (s_, s_, s_ * 2.0)
                o.color = (1.0, self.rnd.uniform(0.22, 0.4), 0.04, self.rnd.uniform(0.5, 0.9))
                o.keyframe_insert('scale', frame=f)
                o.keyframe_insert('color', frame=f)
                f += 2
            show_between(o, self.T(t0), self.T(t1) + 1)

    def shield_dome(self, center, radius, t0, t1, color=None, hits=()):
        """Terran shield: translucent blue triangulated dome. hits: [(t, point)] ripple flashes.
        Shields NEVER shatter."""
        import promo_fx_weapons as W
        return W.shield_dome(self, center, radius, t0, t1, color=color, hits=hits)

    def label(self, text, t0=0.0, t1=None):
        """No on-screen words in promo clips (David: no words). Kept as a no-op on purpose."""
        return None

    # -- render ----------------------------------------------------------------------------
    def render(self):
        a = self.args
        q = a.quality
        res, spp, step, blur = QUALITY[q]
        sc = bpy.context.scene
        import promo_fx
        promo_fx.before_render(self)
        r = sc.render
        r.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        sc.cycles.samples = spp
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.adaptive_threshold = 0.06
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 3
        sc.cycles.diffuse_bounces = 1
        sc.cycles.glossy_bounces = 1
        sc.cycles.transmission_bounces = 2
        sc.cycles.transparent_max_bounces = 64
        sc.cycles.caustics_reflective = False
        sc.cycles.caustics_refractive = False
        sc.cycles.sample_clamp_indirect = 4.0
        r.use_persistent_data = True
        r.resolution_x, r.resolution_y = res
        r.resolution_percentage = 100
        r.use_motion_blur = blur
        r.motion_blur_shutter = 0.4
        r.image_settings.file_format = 'PNG'
        sc.view_settings.view_transform = os.environ.get('PROMO_VIEW', 'Standard')
        sc.view_settings.look = 'None'
        sc.frame_step = step
        out = a.out or os.path.join(OUT_ROOT, 'clips' if q == 'final' else 'previews', self.id)
        os.makedirs(out, exist_ok=True)
        frames = os.path.join(out, 'frames')
        if os.path.isdir(frames) and not a.resume:
            shutil.rmtree(frames)
        r.use_overwrite = not a.resume
        os.makedirs(frames, exist_ok=True)
        if a.blend or q == 'final':
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, self.id + '.blend'), compress=True)
            if os.path.exists(os.path.join(out, self.id + '.blend1')):
                os.remove(os.path.join(out, self.id + '.blend1'))
        if a.no_render:
            return out
        if a.frames and ',' in a.frames:
            # list of single stills, then one contact sheet
            picks = [int(x) for x in a.frames.split(',')]
            for fr in picks:
                sc.frame_set(fr)
                r.filepath = os.path.join(frames, f'f_{fr:04d}.png')
                bpy.ops.render.render(write_still=True)
            ins = []
            for fr in picks:
                ins += ['-i', os.path.join(frames, f'f_{fr:04d}.png')]
            cols = min(4, len(picks))
            rows = (len(picks) + cols - 1) // cols
            w, h = res
            lay = '|'.join(f'{(i % cols) * w}_{(i // cols) * h}' for i in range(len(picks)))
            sheet = os.path.join(out, f'{self.id}_stills.jpg')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *ins, '-filter_complex',
                            ''.join(f'[{i}]' for i in range(len(picks))) + f'xstack=inputs={len(picks)}:layout={lay}:fill=black',
                            '-q:v', '3', sheet], check=True)
            print('PROMO_OUT', sheet)
            return out
        if a.frames:
            parts = a.frames.split('-')
            sc.frame_start = int(parts[0])
            sc.frame_end = int(parts[-1])
        r.filepath = os.path.join(frames, 'f_')
        bpy.ops.render.render(animation=True)
        # encode
        files = sorted(f for f in os.listdir(frames) if f.endswith('.png'))
        if len(files) > 1:
            lst = os.path.join(frames, 'list.txt')
            with open(lst, 'w') as fh:
                for f_ in files:
                    fh.write(f"file '{f_}'\nduration {step / self.fps:.5f}\n")
            mp4 = os.path.join(out, f'{self.id}.mp4' if q == 'final' else f'{self.id}_{q}.mp4')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                            '-vf', f'fps={self.fps},format=yuv420p', '-c:v', 'libx264', '-crf', '18',
                            '-movflags', '+faststart', mp4], check=True)
            # contact sheet of 8 frames for review
            pick = [files[int(i * (len(files) - 1) / 7)] for i in range(8)]
            sheet = os.path.join(out, f'{self.id}_{q}_sheet.jpg')
            ins = []
            for p_ in pick:
                ins += ['-i', os.path.join(frames, p_)]
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *ins, '-filter_complex',
                            ''.join(f'[{i}]' for i in range(8)) + 'xstack=inputs=8:layout=0_0|w0_0|w0+w1_0|w0+w1+w2_0|0_h0|w0_h0|w0+w1_h0|w0+w1+w2_h0',
                            '-q:v', '3', sheet], check=True)
        print('PROMO_OUT', out)
        return out
