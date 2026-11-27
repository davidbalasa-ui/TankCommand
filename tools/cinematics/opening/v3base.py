"""Shared pieces for the v3 two-minute opening (2026-11-14 plan, David's direction).

Unlike v2 (one global clock for the whole minute), every v3 scene is its own Blender scene with its own
clock: frame 1 is the scene's first frame. A scene module exposes build(draft) -> Scene, and the Scene
carries .shots = [(shot_id, f0, f1, camera_keys, shake_events)]. film_v3.py renders and stitches them.

Rules for every scene (from the plan): a few seconds of build-up, then the moment big and close; the
camera is close, ships are large in frame; readable on a phone.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector, Quaternion, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common as C  # noqa: E402
import space as SP  # noqa: E402
import barrage_pieces as BP  # noqa: E402

FPS = 24
OS = C.OS
key_loc, key_rot, key_scale, show, link, copy_tree = SP.key_loc, SP.key_rot, SP.key_scale, SP.show, SP.link, SP.copy_tree
emit, boom, lin = SP.emit, SP.boom, SP.lin


def fr(t):
    return int(round(1 + t * FPS))


def soft_glow(name, col, k, p=2.5):
    """Bright head-on, fading to nothing at the silhouette (for flares, plumes, halos)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, n = BP._new_mat(name)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), p)
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', g, k))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


def fade_value(mat, name='fade'):
    """Adds a multiplier on every emission strength of mat, returns nothing; key it with SP.key_node."""
    SP.add_fade(mat, name, 1.0)


class Scene:
    def __init__(self, seconds, draft=True):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        self.sh = C.Shot(seconds, FPS, draft)
        self.nf = self.sh.nf
        SP.OS.NF = self.nf
        self.draft = draft
        self.shots = []
        self.obj = {}

    # -------------------------------------------------------------- environment
    def env(self, sun_rot=(70, 0, -140), sun_energy=4.0, planet=True, stars=1.0):
        OS.world()
        bg = bpy.context.scene.world.node_tree.nodes['Background']
        bg.inputs['Strength'].default_value = stars
        self.sun_obj = self.sh.sun(rot=sun_rot, energy=sun_energy)
        bpy.context.view_layer.update()
        if planet:
            import planet as PL
            self.planet = PL.build(SP.PLANET_C, self.sun_obj, draft=self.draft)
        return self.sun_obj

    def sun_disc(self, cam, toward, dist=40000.0, r=520.0, keys=None):
        """A proper sun: white-hot disc, two layers of glow and a horizontal lens streak.
        keys: optional [(frame, direction)] to move it (e.g. rising over the limb)."""
        objs = []
        disc = C.uv_sphere('SunDisc', r, seg=(32, 16), mat=emit('SunDiscM', (1.0, 0.95, 0.85), 80.0))
        g1 = C.uv_sphere('SunGlow1', r * 2.6, seg=(32, 16), mat=soft_glow('SunGlow1M', (1.0, 0.85, 0.6), 6.0, 2.0))
        g2 = C.uv_sphere('SunGlow2', r * 7.0, seg=(32, 16), mat=soft_glow('SunGlow2M', (1.0, 0.6, 0.35), 0.35, 5.0))
        st = C.uv_sphere('SunStreak', 1.0, seg=(24, 8), mat=soft_glow('SunStreakM', (0.85, 0.9, 1.0), 3.0, 1.5),
                         scale=(r * 30, r * 0.18, r * 0.18))
        for o in (disc, g1, g2, st):
            o.visible_shadow = False
            objs.append(o)
        ks = keys or [(1, toward)]
        for f, d in ks:
            d = Vector(d).normalized()
            p = Vector(cam) + d * dist
            for o in (disc, g1, g2, st):
                o.location = p
                o.keyframe_insert('location', frame=f)
            # streak lies across the view, horizontal on screen
            side = d.cross(Vector((0, 0, 1))).normalized()
            st.rotation_mode = 'QUATERNION'
            st.rotation_quaternion = side.to_track_quat('X', 'Z')
            st.keyframe_insert('rotation_quaternion', frame=f)
        for o in objs:
            lin(o)
        return objs

    # -------------------------------------------------------------- arrivals through a portal
    def stretch_through(self, ob, d, p_in, p_out, p_hold, f_in, f_out, f_hold, k=9.0, col=(1.0, 0.75, 0.35),
                        name=None, streak_r=None):
        """Ship pulled through a portal along world direction d: it comes out as a long thin streak
        (scaled k times along d, squeezed across), and snaps back to shape as it clears the rim, with a
        flash. p_in: well inside the portal, p_out: just clear of the rim, p_hold: where it settles.
        Ships are assumed to point along their local +X; d is their travel direction."""
        name = name or ob.name
        d = Vector(d).normalized()
        s0 = Vector(ob.scale)
        sq = 1.0 / math.sqrt(k) * 1.4
        # orientation must already be keyed; stretch is along local X, which points along d
        key_loc(ob, [(f_in, p_in), (f_out, p_out), (f_hold, p_hold)], 'BEZIER')
        snap = f_out + 4
        key_scale(ob, [(f_in, (s0.x * k, s0.y * sq, s0.z * sq)), (f_out - 2, (s0.x * k * 0.7, s0.y * sq, s0.z * sq)),
                       (f_out + 1, (s0.x * 0.8, s0.y * 1.12, s0.z * 1.12)), (snap, (s0.x * 1.04, s0.y * 0.97, s0.z * 0.97)),
                       (snap + 4, tuple(s0))], 'BEZIER')
        dims = Vector(ob.dimensions)
        L = max(dims.x, 1.0) / max(ob.scale.x, 1e-6) * s0.x
        r = streak_r or min(dims.y, dims.z) / max(ob.scale.y, 1e-6) * s0.y * 0.12
        # light streak trailing back into the portal, fading out as the ship snaps to shape
        sm = soft_glow(f'{name}StreakM', col, 3.0, 1.6)
        SP.add_fade(sm, 'vis', 1.0)
        streak = C.uv_sphere(f'{name}Streak', 1.0, seg=(24, 10), mat=sm, scale=(L * k * 0.6, r, r))
        streak.rotation_mode = 'QUATERNION'
        streak.rotation_quaternion = d.to_track_quat('X', 'Z')
        streak.visible_shadow = False
        key_loc(streak, [(f_in, p_in - d * L * k * 0.3), (f_out, p_out - d * L * k * 0.45)], 'LINEAR')
        SP.key_node(sm, 'vis', [(f_in, 0.6), (f_out - 3, 1.0), (f_out + 1, 1.4), (f_out + 6, 0.0)])
        show(streak, f_in, f_out + 6)
        # flash where it breaks out of the rim
        fl = C.uv_sphere(f'{name}Flash', 1.0, seg=(24, 12), mat=soft_glow(f'{name}FlashM', (1.0, 0.85, 0.6), 2.5, 3.5))
        fl.location = p_out - d * L * 0.4
        fl.visible_shadow = False
        key_scale(fl, [(f_out - 2, r * 0.5), (f_out + 1, r * 4.0), (f_out + 8, r * 1.5), (f_out + 12, 0.01)])
        show(fl, f_out - 2, f_out + 12)
        return streak

    # -------------------------------------------------------------- shots
    def shot(self, sid, f0, f1, keys, shake=()):
        """keys: [(frame, pos, target, lens[, roll_rad])] in scene frames; shake: [(frame, amp, frames)]."""
        self.shots.append((sid, f0, f1, keys, list(shake)))


def build_camera(keys, shake=(), seed=7):
    """Camera on a path; shake events add a decaying jitter (camera-local) on top."""
    sc = bpy.context.scene
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_end = 80000
    cam.data.clip_start = 0.1
    cam.data.sensor_width = 36
    prev = None
    for k in keys:
        f, p, tgt = k[:3]
        cam.location = p
        q = (Vector(tgt) - Vector(p)).to_track_quat('-Z', 'Y')
        if len(k) > 4 and k[4]:
            q = q @ Quaternion((0, 0, 1), k[4])
        e = q.to_euler()
        if prev is not None:
            e.make_compatible(prev)
        cam.rotation_euler = e
        prev = e.copy()
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
        if len(k) > 3:
            cam.data.lens = k[3]
            cam.data.keyframe_insert('lens', frame=f)
    C.set_interp(cam, 'BEZIER')
    if shake:
        # bake the path, then add jitter frame by frame
        rnd = random.Random(seed)
        f_lo, f_hi = min(k[0] for k in keys), max(k[0] for k in keys)
        base = {}
        for f in range(f_lo, f_hi + 1):
            sc.frame_set(f)
            base[f] = (cam.location.copy(), cam.rotation_euler.copy())
        cam.animation_data_clear()
        for f in range(f_lo, f_hi + 1):
            amp = ramp_ = 0.0
            for ev in shake:              # (frame, amp, frames[, rotation amp in radians])
                fe, a, n = ev[:3]
                if fe <= f < fe + n:
                    k = (1 - (f - fe) / n) ** 2
                    amp += a * k
                    ramp_ += (ev[3] if len(ev) > 3 else a * 0.004) * k
            loc, rot = base[f]
            off = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * amp
            cam.location = loc + rot.to_matrix() @ off
            cam.rotation_euler = (rot.x + rnd.uniform(-1, 1) * ramp_, rot.y + rnd.uniform(-1, 1) * ramp_,
                                  rot.z + rnd.uniform(-1, 1) * ramp_)
            cam.keyframe_insert('location', frame=f)
            cam.keyframe_insert('rotation_euler', frame=f)
        C.set_interp(cam, 'LINEAR')
    if len(keys[0]) > 3:
        C.set_interp(cam.data, 'BEZIER')
    return cam


# ================================================================== engines
def flame_mat(name, col, k, p=1.6):
    """Flickering exhaust glow with a 'thr' (throttle) value node to key brightness."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    nz = n.node('ShaderNodeTexNoise', Scale=0.6, Detail=5.0, Roughness=0.6)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 9.0))
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), p)
    brk = n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.45, 1.3)
    thr = SP.value_node(m, 'thr', 1.0)
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY', g, brk), k), thr.outputs[0]))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


def engines(ob, name, col, hot=(0.85, 0.95, 1.0), n=None, length=None, r=None, thr_keys=None, len_keys=None):
    """Exhaust plumes at the back (local -X) of ob, parented. thr_keys: [(frame, throttle 0..2)] keys
    brightness; len_keys: [(frame, length factor)] keys plume length. Returns the plume objects."""
    bb = [Vector(b) for b in ob.bound_box]
    x0 = min(b.x for b in bb)
    ys = [b.y for b in bb]
    zs = [b.z for b in bb]
    W, H = max(ys) - min(ys), max(zs) - min(zs)
    cy, cz = (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2
    n = n or (1 if W < 12 else (2 if W < 30 else 3))
    r = r or min(W, H) * (0.22 if n == 1 else 0.14)
    length = length or r * 9
    if col[2] < col[0] * 0.5:            # Arcadian (warm gold): their thrusters are lightning, never flame
        return lightning_engines(ob, name, [(x0, cy + (i - (n - 1) / 2) * W * 0.32, cz) for i in range(n)],
                                 r, length, thr_keys, len_keys)
    mant = flame_mat(name + 'MantM', col, 2.2, 2.0)
    core = flame_mat(name + 'CoreM', hot, 4.0, 1.4)
    out = []
    for i in range(n):
        y = cy + (i - (n - 1) / 2) * W * 0.32
        for nm, mat, rr, ll in (('Mant', mant, r, length), ('Core', core, r * 0.45, length * 0.45),
                                ('Halo', mant, r * 1.5, length * 0.3)):
            o = C.uv_sphere(f'{name}{nm}{i}', 1.0, seg=(20, 10), mat=mat, scale=(ll / 2, rr, rr))
            o.parent = ob
            o.location = (x0 - ll / 2 + r * 0.3, y, cz)
            o.visible_shadow = False
            if len_keys:
                for f, k in len_keys:
                    o.scale = (ll / 2 * k, rr * (0.6 + 0.4 * min(k, 1.5)), rr * (0.6 + 0.4 * min(k, 1.5)))
                    o.location = (x0 - ll / 2 * k + r * 0.3, y, cz)
                    o.keyframe_insert('scale', frame=f)
                    o.keyframe_insert('location', frame=f)
            out.append(o)
    if thr_keys:
        SP.key_node(mant, 'thr', thr_keys)
        SP.key_node(core, 'thr', thr_keys)
    return out


def lightning_engines(ob, name, nozzles, r, length, thr_keys=None, len_keys=None, seed=0, f_end=None):
    """Arcadian thrusters (David 2026-11-14: ALL Arcadian ships use lightning for thrusters): crackling gold
    bolts out of each nozzle (local -X of ob), flickering between variants every frame or two. thr_keys /
    len_keys as engines(). Returns the thruster roots."""
    import random
    import orb_fighter as OF
    rnd = random.Random(hash(name) & 0xffff ^ seed)
    k = max(0.2, r / 0.3)                         # bolt meshes are built for a 0.3-radius nozzle
    thr_keys = thr_keys or [(1, 1.0)]
    len_keys = len_keys or [(1, 1.0)]
    frames = sorted({f for f, _ in thr_keys} | {f for f, _ in len_keys})
    f_end = f_end or max(frames + [bpy.context.scene.frame_end])

    def val(keys, f):
        if f <= keys[0][0]:
            return keys[0][1]
        for (fa, a), (fb, b) in zip(keys, keys[1:]):
            if fa <= f <= fb:
                return a + (b - a) * (f - fa) / max(1, fb - fa)
        return keys[-1][1]
    out = []
    for i, p in enumerate(nozzles):
        root, variants = OF._bolt_thruster(f'{name}Bolt{i}', length / k, rnd.randrange(1 << 16))
        root.parent = ob
        root.location = Vector(p)
        out.append(root)
        for f in frames:
            th = min(1.0, val(thr_keys, f) / 1.5)
            lk = val(len_keys, f)
            if th < 0.04 or lk < 0.08:
                root.scale = (0.001,) * 3
            else:
                root.scale = (k * lk * (0.35 + 0.65 * th), k * (0.5 + 0.5 * th), k * (0.5 + 0.5 * th))
            root.keyframe_insert('scale', frame=f)
        cur, prev = rnd.randrange(OF.N_VAR), None
        for f in range(1, f_end + 1):
            if f % 2 == 0 or rnd.random() < 0.4:
                cur = (cur + 1 + rnd.randrange(OF.N_VAR - 1)) % OF.N_VAR
            if cur != prev:
                for vi, objs in enumerate(variants):
                    for o in objs:
                        o.hide_render = vi != cur
                        o.keyframe_insert('hide_render', frame=f)
                prev = cur
        for objs in variants:
            for o in objs:
                SP._interp_where(o, 'hide_render', 'CONSTANT')
    return out


# ================================================================== Terran ships
def terran_ship(kind, name=None):
    """kind: dread | bship | frigate | missile | corvette | twinx. Returns (object, extra)."""
    import terran_fleet as T
    import ships_hd as hd
    if kind == 'dread':
        ob, _ = hd.terran_dreadnought()
        for p in ob.data.polygons:
            p.use_smooth = True
        T.neon_lines(ob)
        ob.scale = (1.8,) * 3
        return ob, None
    if kind == 'bship':
        ob, muz = T.broadside_battleship()
        T.neon_lines(ob)
        return ob, [Vector(m) for m in muz]
    if kind == 'frigate':
        ob = T.terran_frigate_v2()
        T.neon_lines(ob)
        return ob, None
    if kind == 'missile':
        ob, tubes = T.missile_ship()
        T.neon_lines(ob)
        return ob, [Vector(t) for t in tubes]
    if kind == 'corvette':
        ob = T.terran_corvette()
        T.neon_lines(ob)
        return ob, None
    if kind == 'twinx':
        core, wname = T.twin_x_fighter(name or 'TwinX', seed=4)
        return core, wname
    raise KeyError(kind)


def terran_shield(ob, name, f_on, flicker=True):
    dims = Vector(ob.dimensions) / ob.scale.x
    size = (dims.x * 0.62, dims.y * 0.75 + 2.5, dims.z * 1.0 + 2.5)
    cen = sum((Vector(b) for b in ob.bound_box), Vector()) / 8
    sh = SP.tshield(name, size)
    sh.parent = ob
    sh.scale = size
    sh.location = cen
    SP.shield_on(sh, f_on, flicker)
    return sh
