"""Shared scene kit for the 60 s opening video shots (drafts and finals).

Each shot is its own script run in a fresh Blender process:
    python tools/cinematics/opening/shot.py --shot=N --out=DIR [--draft]
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
CIN = os.path.dirname(HERE)
sys.path.insert(0, CIN)
sys.path.insert(0, os.path.join(CIN, '..', 'art', 'v2'))
_argv = sys.argv
sys.argv = [sys.argv[0]]           # orbit_sample parses argv at import
import orbit_sample as OS  # noqa: E402
sys.argv = _argv
import forge as F  # noqa: E402
import ships as base  # noqa: E402

REPO = os.path.abspath(os.path.join(CIN, '..', '..'))
MODELS = os.path.join(REPO, 'public', 'assets', 'models')

emit_mat, fireball_mat, key_value, set_interp, uv_sphere, show_between = (
    OS.emit_mat, OS.fireball_mat, OS.key_value, OS.set_interp, OS.uv_sphere, OS.show_between)


class Shot:
    def __init__(self, seconds, fps, draft):
        self.fps = fps
        self.seconds = seconds
        self.nf = int(round(seconds * fps))
        self.draft = draft
        self.rnd = random.Random(1)
        F.begin('terran')
        sc = bpy.context.scene
        sc.render.fps = fps
        sc.frame_start, sc.frame_end = 1, self.nf
        OS.NF = self.nf
        OS.FPS = fps

    def T(self, sec):
        return 1 + sec * self.fps

    # ---------------------------------------------------------------- render
    def render_settings(self, res, samples, blur=True):
        sc = bpy.context.scene
        r = sc.render
        r.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        sc.cycles.samples = samples
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.adaptive_threshold = 0.05
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 3
        sc.cycles.diffuse_bounces = 1
        sc.cycles.glossy_bounces = 1
        sc.cycles.transparent_max_bounces = 8
        sc.cycles.caustics_reflective = False
        sc.cycles.caustics_refractive = False
        sc.cycles.sample_clamp_indirect = 4.0
        r.resolution_x, r.resolution_y = res
        r.resolution_percentage = 100
        r.use_motion_blur = blur
        r.motion_blur_shutter = 0.45
        r.image_settings.file_format = 'PNG'
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.exposure = 0.0

    def render(self, out):
        sc = bpy.context.scene
        os.makedirs(os.path.join(out, 'frames'), exist_ok=True)
        sc.render.filepath = os.path.join(out, 'frames', 'f_')
        bpy.ops.render.render(animation=True)

    # ---------------------------------------------------------------- environment
    def space(self, planet_at=None, planet_r=2400.0, rift_at=None, rift_scale=300.0, rift_rot=None):
        OS.world()
        if planet_at is not None:
            p = OS.planet()
            a = bpy.data.objects['Atmosphere']
            k = planet_r / 2400.0
            for o in (p, a):
                o.location = planet_at
                o.scale = (k, k, k)
        if rift_at is not None:
            rf = OS.rift()
            rf.location = rift_at
            rf.scale = (rift_scale,) * 3
            if rift_rot is not None:
                rf.rotation_euler = rift_rot
            return rf
        return None

    def sun(self, rot=(58, 0, -128), energy=4.0, col=(1.0, 0.95, 0.88), name='Sun'):
        o = bpy.data.objects.new(name, bpy.data.lights.new(name, 'SUN'))
        bpy.context.scene.collection.objects.link(o)
        o.data.energy = energy
        o.data.color = col
        o.data.angle = math.radians(0.6)
        o.rotation_euler = [math.radians(a) for a in rot]
        return o

    # ---------------------------------------------------------------- camera
    def camera(self, keys, lens=28, interp='BEZIER', roll=None):
        """keys: [(sec, pos, target)]; optional per-key lens as 4th item."""
        sc = bpy.context.scene
        cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.lens = lens
        cam.data.clip_end = 30000
        cam.data.clip_start = 0.05
        for i, k in enumerate(keys):
            t, p, tgt = k[:3]
            cam.location = p
            e = (Vector(tgt) - Vector(p)).to_track_quat('-Z', 'Y').to_euler()
            if i:
                prev = cam.rotation_euler
                e.make_compatible(prev)
            if roll:
                e.rotate_axis('Z', math.radians(roll[i]))
            cam.rotation_euler = e
            cam.keyframe_insert('location', frame=self.T(t))
            cam.keyframe_insert('rotation_euler', frame=self.T(t))
            if len(k) > 3:
                cam.data.lens = k[3]
                cam.data.keyframe_insert('lens', frame=self.T(t))
        set_interp(cam, interp)
        set_interp(cam.data, interp)
        return cam

    # ---------------------------------------------------------------- objects
    def key_path(self, obj, keys, interp='LINEAR', face=False):
        """keys: [(sec, pos)] or [(sec, pos, euler_deg)]."""
        for i, k in enumerate(keys):
            t, p = k[0], k[1]
            obj.location = p
            obj.keyframe_insert('location', frame=self.T(t))
            if len(k) > 2:
                obj.rotation_euler = [math.radians(a) for a in k[2]]
                obj.keyframe_insert('rotation_euler', frame=self.T(t))
            elif face:
                nxt = keys[min(i + 1, len(keys) - 1)][1]
                prv = keys[max(i - 1, 0)][1]
                d = Vector(nxt) - Vector(prv)
                obj.rotation_mode = 'QUATERNION'
                obj.rotation_quaternion = d.to_track_quat('X', 'Z')
                obj.keyframe_insert('rotation_quaternion', frame=self.T(t))
        set_interp(obj, interp)

    def dup(self, obj, name=None):
        """Linked copy of obj and all its children (hierarchy kept)."""
        sc = bpy.context.scene

        def rec(o, parent):
            c = o.copy()
            c.animation_data_clear()
            sc.collection.objects.link(c)
            if parent is not None:
                c.parent = parent
                c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
            for ch in o.children:
                rec(ch, c)
            return c
        c = rec(obj, None)
        if name:
            c.name = name
        c.hide_render = False
        return c

    def hide_tree(self, obj, hide=True):
        obj.hide_render = hide
        for ch in obj.children_recursive:
            ch.hide_render = hide

    def glb(self, rel, length, name=None):
        o = OS.load_glb(os.path.join(MODELS, rel), length)
        if name:
            o.name = name
        return o

    def spin_child(self, ship, child_name, turns, t0, t1, axis=0):
        w = bpy.data.objects[child_name]
        w.rotation_mode = 'XYZ'
        w.keyframe_insert('rotation_euler', frame=self.T(t0))
        w.rotation_euler[axis] += turns * 2 * math.pi
        w.keyframe_insert('rotation_euler', frame=self.T(t1))
        set_interp(w)

    # ---------------------------------------------------------------- effects
    def bolt(self, mat, p_from, p_to, t0, speed, size=(3.6, 0.08, 0.08), name='bolt'):
        d = Vector(p_to) - Vector(p_from)
        dur = d.length / speed
        o = uv_sphere(name, 1.0, seg=(10, 6), mat=mat, scale=size)
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = d.to_track_quat('X', 'Z')
        o.location = p_from
        o.keyframe_insert('location', frame=self.T(t0))
        o.location = p_to
        o.keyframe_insert('location', frame=self.T(t0 + dur))
        show_between(o, int(self.T(t0)), int(self.T(t0 + dur)) + 1)
        set_interp(o)
        o.visible_shadow = False
        return t0 + dur

    _nb = 0

    def boom(self, p, t, size, hot=(1.0, 0.45, 0.06), cool=(0.35, 0.03, 0.005), life=1.2, light=0.0, follow=None):
        Shot._nb += 1
        k = Shot._nb
        m = fireball_mat(f'boom{k}', hot, cool)
        o = uv_sphere(f'Boom{k}', 1.0, seg=(24, 14), mat=m)
        o.visible_shadow = False
        o.rotation_euler = (self.rnd.uniform(0, 6), self.rnd.uniform(0, 6), self.rnd.uniform(0, 6))
        f0, f1 = self.T(t), self.T(t + life)
        step = max(1, self.fps // 8)
        for f, s in [(f0, size * 0.15), (f0 + step, size * 0.75), (f1, size * 1.25)]:
            o.scale = (s, s, s)
            o.keyframe_insert('scale', frame=f)
        o.location = p
        o.keyframe_insert('location', frame=f0)
        if follow is not None:
            o.location = Vector(p) + Vector(follow) * life
            o.keyframe_insert('location', frame=f1)
        key_value(m, 'S', 1, 0.0)
        key_value(m, 'S', f0, 0.0)
        key_value(m, 'S', f0 + 1, 7.0)
        key_value(m, 'S', f0 + 2 * step, 3.5)
        key_value(m, 'S', f1, 0.8)
        key_value(m, 'V', 1, 1.0)
        key_value(m, 'V', f0 + 2 * step, 1.0)
        key_value(m, 'V', f1, 0.0)
        show_between(o, int(f0), int(f1) + 1)
        set_interp(o)
        set_interp(m.node_tree)
        if light > 0:
            L = bpy.data.objects.new(f'Flash{k}', bpy.data.lights.new(f'Flash{k}', 'POINT'))
            bpy.context.scene.collection.objects.link(L)
            L.location = p
            L.data.color = hot
            L.data.shadow_soft_size = size * 0.5
            for f, e in [(1, 0), (f0, 0), (f0 + 1, light), (f0 + 3 * step, light * 0.25), (f1, 0)]:
                L.data.energy = e
                L.data.keyframe_insert('energy', frame=f)
            set_interp(L.data)
        return o

    def lightning(self, pairs, seed, width=0.14, flicker=None, name='Lightning'):
        """Static bolt sets that flicker: builds `len(seeds)` variants and shows one at a time.
        pairs: [(p0, p1)]; flicker: (t0, t1, every_frames)."""
        import arcadian_fleet as AF
        objs = []
        variants = 3 if flicker else 1
        with AF.gold_palette():
            base._faction('kesh')
            for v in range(variants):
                rnd = random.Random(seed * 31 + v)
                m = F.mark()
                for a, b in pairs:
                    AF.bolt(a, b, rnd, width=width, jag=0.22, depth=5, branches=2)
                objs.append(base._join(F.since(m), f'{name}{v}'))
        if flicker:
            t0, t1, every = flicker
            f0, f1 = int(self.T(t0)), int(self.T(t1))
            for i, o in enumerate(objs):
                o.hide_render = True
                o.keyframe_insert('hide_render', frame=1)
            for f in range(f0, f1 + 1, every):
                pick = ((f - f0) // every) % len(objs)
                for i, o in enumerate(objs):
                    o.hide_render = (i != pick)
                    o.keyframe_insert('hide_render', frame=f)
            for o in objs:
                o.hide_render = True
                o.keyframe_insert('hide_render', frame=f1 + 1)
                set_interp(o)
        return objs
