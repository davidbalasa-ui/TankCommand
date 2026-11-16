"""Finishing look for the promo clips: lens (depth of field) and image finish (bloom, a
hue-preserving highlight shoulder, per-biome colour grade, contrast curve, vignette).

promo_kit.Promo.render() calls apply(promo, quality) just before rendering. Everything here is
optional and switchable:

    P.render(grade=False, dof=False, bloom=False, vignette=False)   # per clip
    P.look = dict(bloom=0.6, dof_blur=0.004, ...)                    # tweak (see DEFAULTS)
    PROMO_LOOK=0  (environment)                                       # switch the whole finish off

Grade: chosen from P.env_kind ('desert' | 'highland' | 'alien' | 'dusk' | 'ash' | 'space'),
read with getattr so it works when the environment code does not set it; it is then guessed
from the world (space) or the env palette.

Bloom comes from the Emit pass (only emissive things glow: neon trims, gold cores, fire, bolts;
never bright sand or sky), so the image never goes milky.

Depth of field: focus follows the camera's subject over time. Each frame the subjects are the
look-at target and the most prominent loaded unit on screen (bigger on screen = more
prominent; the usual "hero in the foreground, looking past it at the action" shot). Focus is
set between them (harmonic mean) and the f-stop solved so both stay within dof_sharp of the
frame width, while the far background gets about dof_blur of blur, so a wide lens and a long
lens look alike. Near and far distances are smoothed (no focus pumping) and snap at camera
cuts (cuts= of P.camera plus detected camera jumps). Cost: ~1-5 s setup, nothing per frame.
Overrides: P.camera(keys, fstop=2.8) (fixed f-stop), P.camera(keys, focus=actor_or_point),
or per key a trailing dict: (t, pos, look, lens, {'fstop': 4, 'focus': actor}). A per-key
override holds until the next key.
"""
import math
import os

import bpy
from mathutils import Vector

_DEBUG = bool(os.environ.get('PROMO_LOOK_DEBUG'))

# Strengths are deliberately modest: the clips are watched on phones, units must stay readable.
DEFAULTS = dict(
    bloom=0.7,              # glow strength (0 disables)
    bloom_threshold=0.4,    # emission level where glow starts
    bloom_hot=2.5,          # non-emissive pixels glow only above this level (sun glints)
    bloom_size=0.5,         # 0..1, relative glow radius
    knee=0.72,              # highlight shoulder start (hue preserving above it)
    preserve=0.5,           # 1 = fully hue-preserving highlights, 0 = per-channel roll-off
    vignette=0.3,           # corner darkening
    dof_blur=0.0035,        # background (infinity) blur circle, fraction of the frame width
    dof_sharp=0.0011,       # max blur on the subjects (hero and look-at), fraction of width
    fstop_min=0.5, fstop_max=16.0,
    focus_smooth=0.22,      # seconds, focus pull time constant
    ca=0.0,                 # chromatic aberration (lens dispersion); 0 = off
)

# Per-biome grade. gain/gamma/lift are multipliers per channel (lift is added, small), sat is
# saturation, contrast the strength of the S curve, exposure in stops.
GRADES = {
    'desert':   dict(lift=(0.000, 0.003, 0.010), gamma=(1.0, 1.0, 0.99), gain=(1.02, 1.0, 0.97), sat=1.06, contrast=0.6, exposure=-0.05),
    'highland': dict(lift=(0.000, 0.003, 0.008), gamma=(0.99, 1.0, 1.0), gain=(1.0, 1.01, 0.99), sat=1.08, contrast=0.55, exposure=0.0),
    'alien':    dict(lift=(0.008, 0.000, 0.012), gamma=(1.0, 0.99, 1.0), gain=(1.02, 0.99, 0.99), sat=1.08, contrast=0.55, exposure=0.0),
    'dusk':     dict(lift=(0.000, 0.004, 0.016), gamma=(1.0, 1.0, 1.0), gain=(1.0, 0.99, 0.98), sat=1.0, contrast=0.5, exposure=0.05),
    'ash':      dict(lift=(0.004, 0.005, 0.010), gamma=(1.0, 1.0, 1.01), gain=(1.01, 1.0, 0.98), sat=0.92, contrast=0.65, exposure=0.0),
    'space':    dict(lift=(0.000, 0.002, 0.008), gamma=(1.0, 1.0, 1.0), gain=(1.0, 1.0, 1.0), sat=1.06, contrast=0.6, exposure=0.0, bloom=1.3),
    None:       dict(lift=(0.0, 0.002, 0.006), gamma=(1.0, 1.0, 1.0), gain=(1.01, 1.0, 0.99), sat=1.04, contrast=0.5, exposure=0.0),
}

# sky colours of promo_kit.env() palettes, to guess the kind when env_kind is not set
_SKY_GUESS = {
    (0.42, 0.6, 0.85): 'desert', (0.38, 0.55, 0.8): 'highland', (0.3, 0.45, 0.62): 'alien',
    (0.18, 0.22, 0.42): 'dusk', (0.3, 0.32, 0.36): 'ash',
}


def env_kind(P):
    k = getattr(P, 'env_kind', None)
    if k:
        return k
    w = bpy.context.scene.world
    if w is not None and w.name.startswith('Space'):
        return 'space'
    pal = getattr(P, 'palette', None)
    if isinstance(pal, dict) and 'sky' in pal:
        sky = tuple(round(c, 3) for c in pal['sky'])
        for s, kind in _SKY_GUESS.items():
            if tuple(round(c, 3) for c in s) == sky:
                return kind
    return None


def settings(P, flags):
    cfg = dict(DEFAULTS)
    cfg.update(getattr(P, 'look', None) or {})
    on = os.environ.get('PROMO_LOOK', '1') not in ('0', 'off', 'no')
    for f in ('grade', 'dof', 'bloom', 'vignette'):
        v = flags.get(f)
        if v is None:
            v = getattr(P, 'look_' + f, None)
        cfg['use_' + f] = on and (True if v is None else bool(v))
    return cfg


# -- compositor ------------------------------------------------------------------------------
class _NB:
    """Tiny node-building helper for a compositor node group."""

    def __init__(self, ng):
        self.ng = ng
        self.x = 0

    def node(self, kind, **inputs):
        n = self.ng.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            self.set(n, k, v)
        return n

    def set(self, n, k, v):
        sock = n.inputs[k] if isinstance(k, int) else next(s for s in n.inputs if s.enabled and (s.identifier == k or s.name == k))
        if isinstance(v, bpy.types.NodeSocket):
            self.ng.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, clamp=False):
        n = self.node('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        self.set(n, 0, a)
        if b is not None:
            self.set(n, 1, b)
        return n.outputs[0]

    def mix(self, a, b, fac, blend='MIX'):
        n = self.node('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        n.clamp_result = False
        self.set(n, 'Factor_Float', fac)
        self.set(n, 'A_Color', a)
        self.set(n, 'B_Color', b)
        return n.outputs['Result_Color'] if 'Result_Color' in n.outputs else n.outputs[2]

    def gray(self, v):
        c = self.node('CompositorNodeCombineColor')
        for i in range(3):
            self.set(c, i, v)
        return c.outputs[0]


def _rgb_mul(nb, img, rgb):
    """img * per-channel constant."""
    sep = nb.node('CompositorNodeSeparateColor', Image=img)
    comb = nb.node('CompositorNodeCombineColor')
    for i, ch in enumerate(('Red', 'Green', 'Blue')):
        nb.set(comb, i, nb.math('MULTIPLY', sep.outputs[ch], rgb[i]))
    nb.set(comb, 3, sep.outputs['Alpha'])
    return comb.outputs[0]


def build_compositor(P, cfg, quality, source=None):
    sc = bpy.context.scene
    ng = bpy.data.node_groups.new('PromoLook', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    sc.render.compositor_device = 'CPU'  # default is GPU, which aborts headless
    sc.render.compositor_precision = 'FULL'
    bpy.context.view_layer.use_pass_emit = True
    nb = _NB(ng)
    rl = source(nb) if source else nb.node('CompositorNodeRLayers')
    img = rl.outputs[0]  # 'Image' (Render Layers) / 'Combined' (multilayer EXR)
    emit = next((o for o in rl.outputs if o.name in ('Emission', 'Emit') and o.enabled), None)
    kind = env_kind(P)
    g = dict(GRADES.get(kind, GRADES[None]))

    # 1. bloom, on scene-linear HDR before anything is compressed, so glow keeps its hue.
    #    Source: the Emit pass (only emissive things glow: neon trims, gold cores, fire, bolts;
    #    never bright sand or sky) plus very hot image values (sun glints, explosion cores).
    strength = cfg['bloom'] * g.get('bloom', 1.0)
    if cfg['use_bloom'] and strength > 0:
        src = img
        if emit is not None:
            hot = nb.node('CompositorNodeExposure', Image=img, Exposure=math.log2(cfg['bloom_threshold'] / cfg['bloom_hot'])).outputs[0]
            src = nb.mix(emit, hot, 1.0, 'LIGHTEN')
        gl = nb.node('CompositorNodeGlare', Image=src)
        nb.set(gl, 'Type', 'Bloom')
        nb.set(gl, 'Quality', 'High' if quality == 'final' else 'Medium')
        nb.set(gl, 'Threshold', cfg['bloom_threshold'])
        nb.set(gl, 'Smoothness', 0.6)
        nb.set(gl, 'Strength', 1.0)
        nb.set(gl, 'Saturation', 1.0)
        nb.set(gl, 'Size', cfg['bloom_size'])
        glow = nb.mix(gl.outputs['Glare'], nb.gray(strength), 1.0, 'MULTIPLY')
        img = nb.mix(img, glow, 1.0, 'ADD')

    # 2. exposure + white balance / lift-gamma-gain, still in linear
    if cfg['use_grade']:
        if g.get('exposure'):
            img = nb.node('CompositorNodeExposure', Image=img, Exposure=g['exposure']).outputs[0]
        img = _rgb_mul(nb, img, g['gain'])
        lift = nb.node('CompositorNodeCombineColor')
        for i in range(3):
            nb.set(lift, i, g['lift'][i])
        img = nb.mix(img, lift.outputs[0], 1.0, 'ADD')

    # 3. highlight shoulder. Two soft roll-offs above the knee, blended:
    #    - hue preserving: compress max(r,g,b) and scale the colour by the same factor, so
    #      saturated emitters (Arcadian gold, neon blue, fire) roll off as themselves;
    #    - per channel: each channel rolls off on its own, which drifts hot things toward
    #      yellow/white like film (a hot core, but alone it turns gold into lemon/cream).
    #    `preserve` sets the mix; ~0.5 keeps gold golden with a brighter core.
    k = cfg['knee']

    def shoulder(v):
        over = nb.math('MAXIMUM', nb.math('SUBTRACT', v, k), 0.0)
        comp = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, nb.math('EXPONENT', nb.math('DIVIDE', over, -(1 - k)))), 1 - k)
        return nb.math('ADD', nb.math('MINIMUM', v, k), comp)
    sep = nb.node('CompositorNodeSeparateColor', Image=img)
    m = nb.math('MAXIMUM', nb.math('MAXIMUM', sep.outputs['Red'], sep.outputs['Green']), sep.outputs['Blue'])
    scale = nb.math('DIVIDE', shoulder(m), nb.math('MAXIMUM', m, 1e-5))
    scaled = nb.mix(img, nb.gray(scale), 1.0, 'MULTIPLY')
    perch = nb.node('CompositorNodeCombineColor')
    for i, ch in enumerate(('Red', 'Green', 'Blue')):
        nb.set(perch, i, shoulder(sep.outputs[ch]))
    img = nb.mix(perch.outputs[0], scaled, cfg['preserve'])

    if cfg['use_grade']:
        # 4. saturation, then a gentle filmic-ish S curve in display space (gamma 2.2 sandwich)
        hs = nb.node('CompositorNodeHueSat', Image=img)
        nb.set(hs, 'Saturation', g['sat'])
        img = hs.outputs[0]
        disp = _pow_rgb(nb, img, [1 / 2.2 / gg for gg in g['gamma']])
        cv = nb.node('CompositorNodeCurveRGB', Image=disp)
        _s_curve(cv, g['contrast'])
        img = _pow_rgb(nb, cv.outputs[0], (2.2, 2.2, 2.2))

    # 5. vignette: darken toward the corners, in linear (multiply)
    if cfg['use_vignette'] and cfg['vignette'] > 0:
        co = nb.node('CompositorNodeImageCoordinates', Image=rl.outputs[0])
        uv = co.outputs['Normalized']
        sepv = nb.node('CompositorNodeSeparateColor', Image=uv)
        # normalized coords are 0..1; centred, x stretched a little so the falloff is a wide
        # oval; 0 in the middle, 1 in the corners, smooth (no visible edge)
        dx = nb.math('MULTIPLY', nb.math('SUBTRACT', sepv.outputs['Red'], 0.5), 2.0 * 1.2)
        dy = nb.math('MULTIPLY', nb.math('SUBTRACT', sepv.outputs['Green'], 0.5), 2.0)
        r2 = nb.math('ADD', nb.math('MULTIPLY', dx, dx), nb.math('MULTIPLY', dy, dy))
        r0, rc = 0.3, 1.2 * 1.2 + 1.0
        fall = nb.math('POWER', nb.math('DIVIDE', nb.math('MAXIMUM', nb.math('SUBTRACT', r2, r0), 0.0), rc - r0), 1.5)
        v = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', fall, cfg['vignette']))
        img = nb.mix(img, nb.gray(v), 1.0, 'MULTIPLY')

    if cfg.get('ca'):
        ld = nb.node('CompositorNodeLensdist', Image=img)
        nb.set(ld, 'Dispersion', cfg['ca'])
        img = ld.outputs[0]

    out = nb.node('NodeGroupOutput')
    ng.links.new(img, out.inputs[0])
    return ng


def _pow_rgb(nb, img, p):
    sep = nb.node('CompositorNodeSeparateColor', Image=img)
    comb = nb.node('CompositorNodeCombineColor')
    for i, ch in enumerate(('Red', 'Green', 'Blue')):
        nb.set(comb, i, nb.math('POWER', nb.math('MAXIMUM', sep.outputs[ch], 0.0), p[i]))
    nb.set(comb, 3, sep.outputs['Alpha'])
    return comb.outputs[0]


def _s_curve(cv, amount):
    """Soft S curve on the combined channel: deeper shadows, a little more mid contrast,
    highlights rolled (never clipped harder than before)."""
    c = cv.mapping.curves[3]
    a = amount
    pts = [(0.0, 0.0), (0.18, 0.18 - 0.03 * a), (0.5, 0.5 + 0.01 * a), (0.82, 0.82 + 0.04 * a), (1.0, 1.0)]
    while len(c.points) < len(pts):
        c.points.new(0.5, 0.5)
    for p, (x, y) in zip(c.points, pts):
        p.location = (x, y)
    cv.mapping.update()


# -- depth of field --------------------------------------------------------------------------
def _key_opts(k):
    return k[-1] if len(k) > 3 and isinstance(k[-1], dict) else {}


def _point_of(P, f, target):
    """World point of a focus target (Actor, object or point) at frame f (scene already set)."""
    if target is None:
        return None
    if hasattr(target, 'root'):
        h = target.entry.get('height', 1.5) if hasattr(target, 'entry') else 1.5
        return target.root.matrix_world.translation + Vector((0, 0, min(h * 0.5, 2.0)))
    if hasattr(target, 'matrix_world'):
        return target.matrix_world.translation.copy()
    if isinstance(target, (int, float)):
        return float(target)
    return Vector(target)


def _visible(a):
    if a.root.hide_render or a.model_root.hide_render:
        return False
    ms = [m for m in a.meshes if m.name in bpy.data.objects]
    if not ms:
        return False
    if all(m.hide_render for m in ms):
        return False
    s = a.root.matrix_world.to_scale()
    return max(s) > 0.05


def setup_dof(P, cfg, quality):
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        return
    camd = cam.data
    if not cfg['use_dof']:
        camd.dof.use_dof = False
        return
    info = getattr(P, 'look_cam', None) or {}
    keys = info.get('keys') or []
    cuts = list(info.get('cuts') or ())
    fixed_fstop = info.get('fstop')
    fixed_focus = info.get('focus')
    fps = sc.render.fps
    res_x = sc.render.resolution_x
    actors = list(getattr(P, 'actors', []))
    camd.dof.use_dof = True
    camd.dof.aperture_blades = 7
    camd.dof.aperture_rotation = math.radians(12)
    sensor = camd.sensor_width
    blur_mm = cfg['dof_blur'] * sensor  # circle of confusion at infinity on the sensor (mm)

    def key_at(t):
        """Index of the camera key segment containing time t."""
        i = 0
        for j, k in enumerate(keys):
            if k[0] <= t + 1e-6:
                i = j
        return i

    f0, f1 = sc.frame_start, sc.frame_end
    frames = list(range(f0, f1 + 1))
    raw = []
    fst = []
    pos = []
    lenses = []
    cur = None  # currently chosen subject (hysteresis)
    for f in frames:
        sc.frame_set(f)
        t = (f - 1) / fps
        mw = cam.matrix_world
        cpos = mw.translation.copy()
        fwd = -(mw.to_3x3() @ Vector((0, 0, 1))).normalized()
        right = (mw.to_3x3() @ Vector((1, 0, 0))).normalized()
        up = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
        pos.append(cpos)
        lens = camd.lens
        lenses.append(lens)
        half_w = sensor / 2 / lens
        half_h = half_w * sc.render.resolution_y / res_x
        opts = _key_opts(keys[key_at(t)]) if keys else {}
        target = opts.get('focus', fixed_focus)
        near = far = None
        if target is not None:
            p = _point_of(P, f, target)
            near = far = p if isinstance(p, float) else (p - cpos).dot(fwd)
        else:
            look = getattr(P, 'cam_target', None)
            look_d = (look.matrix_world.translation - cpos).dot(fwd) if look else 20.0
            # most prominent visible unit near the frame centre
            best, best_s = None, 0.0
            for a in actors:
                try:
                    if not _visible(a):
                        continue
                except ReferenceError:
                    continue
                c = _point_of(P, f, a)
                v = c - cpos
                d = v.dot(fwd)
                if d < 1.0:
                    continue
                x, y = v.dot(right) / d / half_w, v.dot(up) / d / half_h
                # distance of the unit's bounding circle from the frame centre (0 = centre,
                # 1 = touching the edge): a hero filling the foreground may have its centre
                # off frame while most of it is on screen
                rad = 0.5 * a.size / d
                cen = max(0.0, max(abs(x) - rad / half_w, abs(y) - rad / half_h))
                if _DEBUG and f % 12 == 10:
                    print('PROMO_FOCUS_DBG', f, a.name, f'd={d:.1f} x={x:.2f} y={y:.2f} cen={cen:.2f}')
                if cen > 0.75:
                    continue
                score = a.size / d * (1.0 - 0.6 * cen)
                if a is cur:
                    score *= 1.35  # hysteresis: don't flip between similar subjects
                if score > best_s:
                    best, best_s = a, score
            near = far = look_d
            cur = None
            if best is not None:
                d_best = (_point_of(P, f, best) - cpos).dot(fwd)
                # the subject range spans the look-at point and the hero unit (typically a hero
                # in the foreground looking past it at the action): both are kept sharp
                if d_best < look_d * 1.6:
                    near, far = min(look_d, d_best), max(look_d, d_best)
                    cur = best
        raw.append((max(0.5, near), max(0.5, far)))
        fs = opts.get('fstop', fixed_fstop)
        fst.append(fs)

    # cut detection: explicit cuts + camera jumps
    cut_frames = set(int(round(1 + c * fps)) for c in cuts)
    steps = [(pos[i] - pos[i - 1]).length for i in range(1, len(pos))]
    if steps:
        med = sorted(steps)[len(steps) // 2]
        for i, s in enumerate(steps):
            if s > max(1.5, 6 * med):
                cut_frames.add(frames[i + 1])

    # zero-phase exponential smoothing in log distance, separately within each shot
    a = 1.0 - math.exp(-1.0 / (cfg['focus_smooth'] * fps))
    seg = [0] + [i for i, f in enumerate(frames) if f in cut_frames and i > 0] + [len(frames)]

    def smooth(vals):
        sm = [math.log(v) for v in vals]
        for s0, s1 in zip(seg, seg[1:]):
            for order in (range(s0, s1), range(s1 - 1, s0 - 1, -1)):
                prev = None
                for i in order:
                    prev = sm[i] if prev is None else prev + a * (sm[i] - prev)
                    sm[i] = prev
        return [math.exp(v) for v in sm]
    near = smooth([r[0] for r in raw])
    far = smooth([r[1] for r in raw])
    sharp_mm = cfg['dof_sharp'] * sensor
    focus = []
    for i, f in enumerate(frames):
        n_mm, s_mm = near[i] * 1000.0, max(far[i], near[i]) * 1000.0
        # focus between the two subjects (harmonic mean: equal blur on both) ...
        x_mm = 2.0 / (1.0 / n_mm + 1.0 / s_mm)
        fl = lenses[i]
        fs = fst[i]
        if fs is None:
            # ... an aperture that keeps both within dof_sharp, and that otherwise gives the
            # far background (infinity) a fixed blur: c_inf = f^2 / (N * x)
            n_bg = fl * fl / (x_mm * blur_mm)
            n_sharp = fl * fl * (1.0 / n_mm - 1.0 / x_mm) / sharp_mm
            fs = max(n_bg, n_sharp)
        camd.dof.focus_distance = x_mm / 1000.0
        camd.dof.keyframe_insert('focus_distance', frame=f)
        camd.dof.aperture_fstop = max(cfg['fstop_min'], min(cfg['fstop_max'], fs))
        camd.dof.keyframe_insert('aperture_fstop', frame=f)
        focus.append((f, x_mm / 1000.0, camd.dof.aperture_fstop, near[i], far[i]))
    ad = camd.animation_data
    if ad and ad.action:
        from promo_kit import _fcurves
        for fc in _fcurves(ad.action):
            if fc.data_path.startswith('dof.'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    sc.frame_set(f0)
    P.look_focus = focus
    print('PROMO_FOCUS', ' '.join(f'{f}:{d:.1f}m/f{n:.1f}({a:.0f}-{b:.0f})' for f, d, n, a, b in focus[::6]))


def apply(P, quality, **flags):
    """Called by Promo.render(). flags: grade/dof/bloom/vignette = True/False/None."""
    import time
    t0 = time.time()
    cfg = settings(P, flags)
    sc = bpy.context.scene
    any_post = cfg['use_grade'] or cfg['use_bloom'] or cfg['use_vignette']
    if any_post:
        build_compositor(P, cfg, quality)
    setup_dof(P, cfg, quality)
    print('PROMO_LOOK', env_kind(P), {k: v for k, v in cfg.items() if k.startswith('use_')},
          f'setup {time.time() - t0:.1f}s')
    return cfg
