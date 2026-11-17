"""Promo effects: flipbook cards, explosions, fire, smoke and real fractured destruction.

promo_kit.py keeps the public API (Actor.destroy, Promo.explosion / fire_patch / smoke_column) and
calls into this module. Nothing here is meant to be called by scenes directly, except `card()`.

Flipbook cards
--------------
    card(P, name, pos, t, size=1.0, mode='camera'|'z_locked', speed=1.0, tint=None,
         rot_jitter=True, opacity=1.0, t1=None, ...)

plays /mnt/project-files/fx-library/flipbooks/<name>/0001.png... (manifest.json beside them) on a
card that faces the camera (TRACK_TO, keeps world Z up) or only turns about Z ('z_locked', for
ground blasts). With t1 the card runs from t to t1 and loops if the flipbook loops (fire, smoke).
Extra search dirs: $PROMO_FLIPBOOKS (os.pathsep separated). If a flipbook is missing, card()
returns None and callers fall back to the old procedural effect.

Destruction
-----------
destroy(actor, t, ...) fractures the unit's OWN meshes (power-diagram Voronoi cells cut with
bmesh.bisect_plane, caps filled with a charred / glowing-hot material, outer faces keep their
materials with soot and powered-down emission), then flies the pieces with a small scripted
rigid-body solver (gravity, tumbling, impulse contacts with the terrain and with already settled
big pieces, friction, sleep). Pieces cool from orange to dark; sparks fly; the wreck burns with
looping fire cards and a smoke plume. Air units break up in the air and trail smoke; structures
keep their lower core and shed big chunks.
"""
import glob
import json
import math
import os
import random

import bpy  # noqa: I001
import bmesh
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

import promo_kit as K

LIB_DIRS = [d for d in os.environ.get('PROMO_FLIPBOOKS', '').split(os.pathsep) if d] + [
    '/mnt/project-files/fx-library/flipbooks']

# Wanted effect -> flipbook names to try (first found wins). Globs allowed.
ALIASES = {
    'explo_ground': ['explo_ground_a', 'explo_ground_b', 'explosion_ground*'],
    'explo_air': ['explo_air*', 'explosion_air*', 'explo_ground_a', 'explo_ground*'],
    'explo_space': ['explo_space*', 'explosion_space*', 'explo_air*', 'explosion_air*', 'explo_ground_a', 'explo_ground*'],
    'explo_small': ['explo_small*', 'explosion_small*', 'explo_ground'],
    'explo_ground_arc': ['explo_ground_arc'],
    'explo_big': ['explo_big*'],
    'fire_loop': ['fire_loop*', 'fire_*'],
    'smoke_plume': ['smoke_plume*', 'smoke_column*'],
    'smoke_puff': ['smoke_puff*', 'smoke_burst*', 'smoke_trail*', 'smoke_small*'],
    'dust_ring': ['dust_ring*', 'dust_burst*'],
    'dust_burst': ['dust_burst*', 'dust_ring*'],
    'sparks': ['sparks*', 'spark_*'],
    'flash': ['impact_flash*', 'flash_star*', 'flash*'],
}

_MAN_CACHE = {}


# ============================================================================ flipbooks
def find_flipbook(name):
    """Manifest dict (with 'dir', normalised field names) for a flipbook name or alias, or None."""
    if name in _MAN_CACHE:
        return _MAN_CACHE[name]
    pats = ALIASES.get(name, []) if name in ALIASES else [name]
    if name in ALIASES:
        pats = [name] + pats
    found = None
    for pat in pats:
        for d in LIB_DIRS:
            for path in sorted(glob.glob(os.path.join(d, pat, 'manifest.json'))):
                found = _read_manifest(path)
                if found:
                    break
            if found:
                break
        if found:
            break
    _MAN_CACHE[name] = found
    return found


def _read_manifest(path):
    try:
        m = json.load(open(path))
    except (OSError, ValueError):
        return None
    d = os.path.dirname(path)
    first = os.path.join(d, '0001.png')
    if not os.path.exists(first):
        return None
    n = m.get('frames') or len(glob.glob(os.path.join(d, '[0-9][0-9][0-9][0-9].png')))
    px = m.get('size_px', m.get('size', [512, 512]))
    if isinstance(px, (int, float)):
        px = [int(px), int(px)]
    return dict(
        name=m.get('name', os.path.basename(d)), dir=d, first=first, frames=int(n),
        fps=float(m.get('fps', 24)), size_px=list(px), tint=m.get('tint', ''),
        extent_m=float(m.get('extent_m', m.get('extent', 6.0))),
        origin_uv=list(m.get('origin_uv', m.get('origin', [0.5, 0.5]))),
        loop=bool(m.get('loop', False)), alpha=m.get('alpha', 'straight'),
        emission=float(m.get('emission', 1.0)))


def _image(man):
    key = 'FxSeq_' + man['name']
    img = bpy.data.images.get(key)
    if img is None:
        img = bpy.data.images.load(man['first'], check_existing=False)
        img.name = key
        img.source = 'SEQUENCE'
        img.alpha_mode = 'PREMUL' if man['alpha'].startswith('premul') else 'STRAIGHT'
    return img


def _plane_mesh(man, size):
    w = man['extent_m'] * size
    px = man['size_px']
    h = w * px[1] / px[0]
    u, v = man['origin_uv']
    key = f'FxCardMesh_{man["name"]}_{size:.3f}'
    me = bpy.data.meshes.get(key)
    if me:
        return me
    me = bpy.data.meshes.new(key)
    x0, x1 = -u * w, (1 - u) * w
    z0, z1 = -v * h, (1 - v) * h
    me.from_pydata([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name='UVMap')
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uvl.data[i].uv = c
    return me


def _card_mat(man, f_start, loop, rate, f_end, tint, opacity, emission, phase):
    m = bpy.data.materials.new('FxCardM_' + man['name'])
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = _image(man)
    tex.extension = 'CLIP'
    tex.interpolation = 'Linear'
    iu = tex.image_user
    iu.frame_duration = man['frames']
    # loop phase: start the sequence earlier (frame_offset is applied after the cyclic wrap and
    # would run past the last file)
    ph = int(phase * man['frames']) if loop else 0
    iu.frame_start = int(round(f_start)) - ph
    iu.use_cyclic = loop
    iu.use_auto_refresh = True
    off0 = 0
    iu.frame_offset = 0
    if loop:
        rate = 1.0
    if abs(rate - 1.0) > 1e-3:
        # displayed = (f - start) + 1 + offset; want 1 + rate * (f - start)
        span = max(1, int(f_end - f_start))
        iu.frame_offset = off0
        iu.keyframe_insert('frame_offset', frame=f_start)
        iu.frame_offset = off0 + int(round((rate - 1.0) * span))
        iu.keyframe_insert('frame_offset', frame=f_start + span)
        ad = nt.animation_data
        if ad and ad.action:
            for fc in K._fcurves(ad.action):
                for k in fc.keyframe_points:
                    k.interpolation = 'LINEAR'
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    col = tex.outputs['Color']
    if tint:
        mul = nt.nodes.new('ShaderNodeVectorMath')
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = tuple(tint[:3])
        nt.links.new(col, mul.inputs[0])
        col = mul.outputs[0]
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = emission
    nt.links.new(col, em.inputs['Color'])
    a1 = nt.nodes.new('ShaderNodeMath')
    a1.operation = 'MULTIPLY'
    a1.use_clamp = True
    nt.links.new(tex.outputs['Alpha'], a1.inputs[0])
    nt.links.new(oi.outputs['Alpha'], a1.inputs[1])
    # soft frame edges: effects that outgrow the baked frame (smoke tops) never show a hard cut
    tcn = nt.nodes.new('ShaderNodeTexCoord')
    sx = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tcn.outputs['UV'], sx.inputs[0])
    top = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 1.0, sx.outputs['Y']), 1 / 0.22, clamp=True)
    lft = _math(nt, 'MULTIPLY', sx.outputs['X'], 1 / 0.1, clamp=True)
    rgt = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 1.0, sx.outputs['X']), 1 / 0.1, clamp=True)
    edge = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', top, lft), rgt)
    edge = _math(nt, 'MULTIPLY', edge, edge)
    a1b = _math(nt, 'MULTIPLY', a1.outputs[0], edge)
    a2 = nt.nodes.new('ShaderNodeMath')
    a2.operation = 'MULTIPLY'
    a2.use_clamp = True
    a2.inputs[1].default_value = opacity
    nt.links.new(a1b, a2.inputs[0])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(a2.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m['fx_card'] = True
    return m


def _cards(P):
    if not hasattr(P, '_fx_cards'):
        P._fx_cards = []
    return P._fx_cards


def card(P, name, pos, t, size=1.0, mode='camera', speed=1.0, tint=None, rot_jitter=True,
         opacity=1.0, t1=None, emission=None, fade_in=None, fade_out=None, parent=None,
         push=0.0, phase=None, flip=None):
    """Play flipbook `name` on a card at `pos` from time t. Returns the card empty (or None if the
    flipbook is missing). mode 'camera' faces the camera with Z kept up; 'z_locked' only turns
    about Z (ground blasts). t1: end time (loops repeat; default = one play). push: slide the card
    this many metres toward the camera (keeps a fireball in front of the wreck it hides).
    parent: object the card rides on (pos is then local to it)."""
    man = find_flipbook(name)
    if man is None:
        return None
    rnd = P.rnd
    rate = speed * man['fps'] / P.fps
    f0 = P.T(t)
    dur_f = man['frames'] / rate
    loop = man['loop'] and t1 is not None
    f1 = P.T(t1) if t1 is not None else f0 + dur_f
    if not man['loop']:
        f1 = min(f1, f0 + dur_f)
    if phase is None:
        phase = rnd.random()
    em_val = emission if emission is not None else man['emission']
    mat = _card_mat(man, f0, loop, rate, f1, tint, opacity, em_val, phase)
    e = K.link(bpy.data.objects.new('FxCard_' + man['name'], None))
    e.empty_display_size = 0.3
    if parent is not None:
        e.parent = parent
    e.location = K.V(pos)
    me = _plane_mesh(man, size)
    pl = K.link(bpy.data.objects.new('FxCardPlane_' + man['name'], me))
    pl.parent = e
    if not me.materials:
        me.materials.append(mat)
    pl.material_slots[0].link = 'OBJECT'
    pl.material_slots[0].material = mat
    for attr in ('visible_shadow', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
                 'visible_volume_scatter'):
        setattr(pl, attr, False)
    u, v = man['origin_uv']
    if rot_jitter:
        wild = (0.3 < v < 0.7) and not man['loop'] and mode == 'camera'
        rng = math.pi if wild else math.radians(5)
        pl.rotation_euler.y = rnd.uniform(-rng, rng)
    if flip is None:
        flip = rot_jitter and rnd.random() < 0.5
    if flip:
        pl.scale.x = -1
    pl.location.y = -push
    if mode == 'z_locked':
        c = e.constraints.new('LOCKED_TRACK')
        c.lock_axis = 'LOCK_Z'
        c.track_axis = 'TRACK_NEGATIVE_Y'
    else:
        c = e.constraints.new('TRACK_TO')
        c.track_axis = 'TRACK_NEGATIVE_Y'
        c.up_axis = 'UP_Z'
    cam = bpy.context.scene.camera
    if cam is not None:
        c.target = cam
    _cards(P).append(e)
    # fades via Object Color alpha
    fi = fade_in if fade_in is not None else (0.25 * P.fps if loop else 0)
    fo = fade_out if fade_out is not None else (0.4 * P.fps if loop else 0)
    pl.color = (1, 1, 1, 1)
    if fi > 0:
        pl.color[3] = 0.0
        pl.keyframe_insert('color', index=3, frame=f0)
        pl.color[3] = 1.0
        pl.keyframe_insert('color', index=3, frame=f0 + fi)
    if not loop and fade_out is None and man['frames'] > 12:
        # one-shots dissolve from 28% to 68% of their run: the fireball reads, the baked dark smoke
        # tail never lingers as a blob (smoke plumes take over)
        d = f1 - f0
        pl.color[3] = 1.0
        pl.keyframe_insert('color', index=3, frame=f0 + max(fi, 0.28 * d))
        pl.color[3] = 0.0
        pl.keyframe_insert('color', index=3, frame=f0 + 0.68 * d)
        fo = 0
    if fo > 0 and (t1 is not None or not loop):
        pl.color[3] = 1.0
        pl.keyframe_insert('color', index=3, frame=max(f0 + fi, f1 - fo))
        pl.color[3] = 0.0
        pl.keyframe_insert('color', index=3, frame=f1)
    K.show_between(e, f0, f1 + 1)
    e['fx_card'] = man['name']
    return e


def before_render(P):
    """Hook all cards up to the render camera (scenes create the camera after their effects)."""
    sc = bpy.context.scene
    cam = sc.camera or getattr(P, 'cam', None)
    for e in getattr(P, '_fx_cards', []):
        try:
            for c in e.constraints:
                if c.type in ('TRACK_TO', 'LOCKED_TRACK') and c.target is None:
                    c.target = cam
        except ReferenceError:
            pass
    th = os.environ.get('PROMO_THREADS')
    if th:
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = int(th)


# ============================================================================ materials
def _sep_objcolor(nt):
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(oi.outputs['Color'], sep.inputs[0])
    return oi, sep


def _math(nt, op, a=None, b=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def hot_mat(P, accent='orange'):
    """Fracture faces: charred metal with molten veins. Object Color R = heat (1 hot .. 0 cold)."""
    key = '_fx_hot_' + accent
    if getattr(P, key, None):
        return getattr(P, key)
    m = bpy.data.materials.new('FxCharHot_' + accent)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.8
    b.inputs['Metallic'].default_value = 0.3
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 5.0
    nz.inputs['Detail'].default_value = 8.0
    nz.inputs['Roughness'].default_value = 0.62
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    # base: dark char with a little noise
    cr0 = nt.nodes.new('ShaderNodeValToRGB')
    cr0.color_ramp.elements[0].color = (0.012, 0.011, 0.010, 1)
    cr0.color_ramp.elements[1].color = (0.06, 0.05, 0.045, 1)
    nt.links.new(nz.outputs['Fac'], cr0.inputs['Fac'])
    nt.links.new(cr0.outputs['Color'], b.inputs['Base Color'])
    oi, sep = _sep_objcolor(nt)
    heat = sep.outputs['Red']
    # glow = clamp((noise + heat - 1) * 2.6 + heat * 0.15)
    a = _math(nt, 'ADD', nz.outputs['Fac'], heat)
    a = _math(nt, 'SUBTRACT', a, 1.0)
    a = _math(nt, 'MULTIPLY', a, 2.6)
    h2 = _math(nt, 'MULTIPLY', heat, 0.15)
    g = _math(nt, 'ADD', a, h2, clamp=True)
    cr = nt.nodes.new('ShaderNodeValToRGB')
    els = cr.color_ramp.elements
    if accent == 'gold':
        stops = [(0.0, (0, 0, 0)), (0.3, (0.35, 0.08, 0.0)), (0.65, (1.0, 0.36, 0.03)), (1.0, (1.6, 0.8, 0.1))]
    else:
        stops = [(0.0, (0, 0, 0)), (0.3, (0.4, 0.02, 0.0)), (0.65, (1.2, 0.18, 0.01)), (1.0, (2.0, 0.5, 0.06))]
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = els.new(p)
        e.color = (*c, 1)
    nt.links.new(g, cr.inputs['Fac'])
    nt.links.new(cr.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 1.0
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    setattr(P, key, m)
    return m


def soot_variant(P, m):
    """Copy of an original unit material: Object Color G = soot amount (noise-masked charring),
    B = power off (kills the material's own emission: neon strips die)."""
    cache = P.__dict__.setdefault('_fx_soot', {})
    if m is None:
        return None
    if m.name in cache:
        return cache[m.name]
    n = m.copy()
    n.name = 'FxSoot_' + m.name
    cache[m.name] = n
    if not n.use_nodes or not n.node_tree:
        return n
    nt = n.node_tree
    outs = [x for x in nt.nodes if x.type == 'OUTPUT_MATERIAL']
    out = next((x for x in outs if x.is_active_output), outs[0] if outs else None)
    if out is None or not out.inputs['Surface'].links:
        return n
    src = out.inputs['Surface'].links[0].from_socket
    oi, sep = _sep_objcolor(nt)
    alive = _math(nt, 'SUBTRACT', 1.0, sep.outputs['Blue'], clamp=True)
    for nd in list(nt.nodes):
        if nd.type == 'BSDF_PRINCIPLED':
            s = nd.inputs['Emission Strength']
        elif nd.type == 'EMISSION':
            s = nd.inputs['Strength']
        else:
            continue
        if s.links:
            f = s.links[0].from_socket
            mul = _math(nt, 'MULTIPLY', f, alive)
        else:
            mul = _math(nt, 'MULTIPLY', s.default_value, alive)
        nt.links.new(mul, s)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 2.2
    nz.inputs['Detail'].default_value = 6.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.32
    mr.inputs['From Max'].default_value = 0.55
    nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
    # soot: noise mask scaled by G, plus an overall darkening by G
    k1 = _math(nt, 'MULTIPLY', mr.outputs['Result'], sep.outputs['Green'])
    k2 = _math(nt, 'MULTIPLY', sep.outputs['Green'], 0.3)
    fac = _math(nt, 'MAXIMUM', k1, k2, clamp=True)
    ch = nt.nodes.new('ShaderNodeBsdfPrincipled')
    ch.inputs['Base Color'].default_value = (0.018, 0.016, 0.014, 1)
    ch.inputs['Roughness'].default_value = 0.95
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fac, mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(ch.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return n


def spark_mat(P):
    if getattr(P, '_fx_spark', None):
        return P._fx_spark
    m = bpy.data.materials.new('FxSpark')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 2.5
    nt.links.new(oi.outputs['Color'], em.inputs['Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(oi.outputs['Alpha'], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m['emit_node'] = em.name
    P._fx_spark = m
    return m


def scorch_mat(P):
    if getattr(P, '_fx_scorch', None):
        return P._fx_scorch
    m = bpy.data.materials.new('ScorchM')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (0.02, 0.017, 0.014, 1)
    b.inputs['Roughness'].default_value = 1.0
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # radial falloff (object coords: unit disc) broken up by noise
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 3.0
    nz.inputs['Detail'].default_value = 6.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    d = _math(nt, 'ADD', ln.outputs['Value'], _math(nt, 'MULTIPLY', nz.outputs['Fac'], 0.55))
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 1.15
    mr.inputs['From Max'].default_value = 0.45
    mr.inputs['To Max'].default_value = 0.92
    nt.links.new(d, mr.inputs['Value'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(mr.outputs['Result'], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(b.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    P._fx_scorch = m
    return m


# ============================================================================ terrain + solver
class Terrain:
    """Ground height (lazy cached ray casts on the env ground, bilinear) plus static colliders
    (settled big pieces, active from their settle time)."""

    def __init__(self, P, step=0.5):
        self.P = P
        self.step = step
        self.cache = {}
        g = getattr(P, 'ground', None)
        self.ev = None
        if g is not None:
            dg = bpy.context.evaluated_depsgraph_get()
            self.ev = g.evaluated_get(dg)
            self.inv = g.matrix_world.inverted()
        self.colliders = []

    @property
    def has_ground(self):
        return self.ev is not None or getattr(self.P, '_fx_flat_ground', False)

    def _s(self, i, j):
        k = (i, j)
        v = self.cache.get(k)
        if v is None:
            v = 0.0
            if self.ev is not None:
                o = self.inv @ Vector((i * self.step, j * self.step, 300.0))
                ok, loc, n, idx = self.ev.ray_cast(o, Vector((0, 0, -1)))
                v = loc.z if ok else 0.0
            self.cache[k] = v
        return v

    def ground(self, x, y):
        s = self.step
        fx, fy = x / s, y / s
        i, j = math.floor(fx), math.floor(fy)
        u, v = fx - i, fy - j
        a = self._s(i, j) * (1 - u) + self._s(i + 1, j) * u
        b = self._s(i, j + 1) * (1 - u) + self._s(i + 1, j + 1) * u
        return a * (1 - v) + b * v

    def normal(self, x, y):
        s = self.step
        dx = self.ground(x + s, y) - self.ground(x - s, y)
        dy = self.ground(x, y + s) - self.ground(x, y - s)
        return Vector((-dx / (2 * s), -dy / (2 * s), 1.0)).normalized()

    def at(self, x, y, t):
        h = self.ground(x, y)
        n = None
        for c in self.colliders:
            if t < c['t'] or not (c['x0'] <= x <= c['x1'] and c['y0'] <= y <= c['y1']):
                continue
            loc, nrm, idx, dist = c['bvh'].ray_cast(Vector((x, y, c['z1'] + 1.0)), Vector((0, 0, -1)))
            if loc is not None and loc.z > h:
                h = loc.z
                n = nrm if nrm.z > 0.2 else Vector((0, 0, 1))
        return h, n

    def add_collider(self, verts_world, faces, t):
        bvh = BVHTree.FromPolygons(verts_world, faces)
        xs = [v.x for v in verts_world]
        ys = [v.y for v in verts_world]
        zs = [v.z for v in verts_world]
        self.colliders.append(dict(bvh=bvh, t=t, x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys), z1=max(zs)))


class Body:
    def __init__(self, hull_local, hull_faces, mass, x, v, w, q=None):
        self.r = hull_local
        self.faces = hull_faces
        self.m = mass
        # inertia from the hull point cloud (solid-ish correction 0.45)
        C = Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
        for p in hull_local:
            for i in range(3):
                for j in range(3):
                    C[i][j] += p[i] * p[j]
        n = max(1, len(hull_local))
        tr = (C[0][0] + C[1][1] + C[2][2]) / n
        I = Matrix(((tr, 0, 0), (0, tr, 0), (0, 0, tr)))
        for i in range(3):
            for j in range(3):
                I[i][j] = (I[i][j] - C[i][j] / n) * mass * 0.45
        for i in range(3):
            I[i][i] = max(I[i][i], 1e-4 * mass)
        self.Iinv = I.inverted_safe()
        self.x = x.copy()
        self.v = v.copy()
        self.w = w.copy()
        self.q = q.copy() if q else Quaternion()
        self.asleep = False
        self.calm = 0
        self.landed = None      # first ground contact time
        self.settle_t = None
        self.static = False
        self.keys = []          # (frame, x, q)

    def world_hull(self):
        R = self.q.to_matrix()
        return [self.x + R @ p for p in self.r]


def simulate(P, bodies, terr, t0, t_end, gravity=9.81, substeps=8, rest=0.28, mu=0.55,
             drag=0.05, record_from=None):
    """Step bodies from time t0 to t_end, recording a pose at every integer frame."""
    fps = P.fps
    f_first = math.floor(P.T(t0)) + 1
    f_last = int(P.T(t_end))
    dt = 1.0 / (fps * substeps)
    g = Vector((0, 0, -gravity))
    up = Vector((0, 0, 1))
    for b in bodies:
        b.keys.append((P.T(t0), b.x.copy(), b.q.copy()))
    t = t0
    for f in range(f_first, f_last + 1):
        t_target = (f - 1) / fps
        while t < t_target - 1e-9:
            h = min(dt, t_target - t)
            t += h
            for b in bodies:
                if b.asleep or b.static:
                    continue
                b.v += g * h
                b.v *= (1 - drag * h)
                b.w *= (1 - 0.6 * drag * h)
                b.x += b.v * h
                wl = b.w.length
                if wl > 1e-7:
                    b.q = Quaternion(b.w / wl, wl * h) @ b.q
                    b.q.normalize()
                if not terr.has_ground and not terr.colliders:
                    continue
                R = b.q.to_matrix()
                pens = []
                for r in b.r:
                    rw = R @ r
                    p = b.x + rw
                    gz, nrm = terr.at(p.x, p.y, t)
                    d = gz - p.z
                    if d > 0:
                        pens.append((d, rw, nrm))
                if not pens:
                    b.calm = 0
                    continue
                if b.landed is None:
                    b.landed = t
                pens.sort(key=lambda e: -e[0])
                Iw = R @ b.Iinv @ R.transposed()
                n = pens[0][2] or terr.normal(b.x.x, b.x.y)
                for d, rw, nrm in pens[:4]:
                    nn = nrm or n
                    vr = b.v + b.w.cross(rw)
                    vn = vr.dot(nn)
                    if vn >= 0:
                        continue
                    rn = rw.cross(nn)
                    den = 1.0 / b.m + nn.dot((Iw @ rn).cross(rw))
                    e = rest if vn < -1.2 else 0.0
                    j = -(1 + e) * vn / den
                    b.v += nn * (j / b.m)
                    b.w += Iw @ (rw.cross(nn * j))
                    vr = b.v + b.w.cross(rw)
                    vt = vr - nn * vr.dot(nn)
                    vtl = vt.length
                    if vtl > 1e-5:
                        td = -vt / vtl
                        rt = rw.cross(td)
                        dent = 1.0 / b.m + td.dot((Iw @ rt).cross(rw))
                        jt = min(vtl / dent, mu * j)
                        b.v += td * (jt / b.m)
                        b.w += Iw @ (rw.cross(td * jt))
                b.x += n * (pens[0][0] * 0.9)
                b.w *= (1 - 2.5 * h)
                b.v.x *= (1 - 1.5 * h)
                b.v.y *= (1 - 1.5 * h)
                if b.v.length < 0.12 and b.w.length < 0.25:
                    b.calm += 1
                    if b.calm > substeps * 3:
                        b.asleep = True
                        b.settle_t = t
                        b.v = Vector()
                        b.w = Vector()
                else:
                    b.calm = 0
        for b in bodies:
            if b.asleep:
                if getattr(b, 'keyed_sleep', False):
                    continue
                b.keyed_sleep = True
            b.keys.append((f, b.x.copy(), b.q.copy()))


def key_body(obj, b, P):
    """Write a body's recorded poses as linear keys on location / rotation_quaternion."""
    obj.rotation_mode = 'QUATERNION'
    prev = None
    for f, x, q in b.keys:
        if prev is not None and prev.dot(q) < 0:
            q = -q
        prev = q
        obj.location = x
        obj.rotation_quaternion = q
        obj.keyframe_insert('location', frame=f)
        obj.keyframe_insert('rotation_quaternion', frame=f)
    ad = obj.animation_data
    if ad and ad.action:
        for fc in K._fcurves(ad.action):
            if fc.data_path in ('location', 'rotation_quaternion'):
                for k in fc.keyframe_points:
                    k.interpolation = 'LINEAR'


def pose_at(b, frame):
    """Interpolated recorded pose of a body at a (float) frame."""
    ks = b.keys
    if not ks:
        return b.x, b.q
    if frame <= ks[0][0]:
        return ks[0][1], ks[0][2]
    for i in range(1, len(ks)):
        if ks[i][0] >= frame:
            f0, x0, q0 = ks[i - 1]
            f1, x1, q1 = ks[i]
            u = (frame - f0) / max(1e-6, f1 - f0)
            return x0.lerp(x1, u), q0.slerp(q1, u)
    return ks[-1][1], ks[-1][2]


# ============================================================================ fracture
def _ancestors(o, stop):
    p = o.parent
    while p is not None and p is not stop:
        yield p
        p = p.parent


def _collect_meshes(actor, t):
    """Visible mesh objects of the actor at time t, grouped: 'hull' and pivot sub-trees."""
    P = actor.P
    bpy.context.scene.frame_set(int(round(P.T(t))))
    groups = {}
    for o in [actor.model_root] + list(actor.model_root.children_recursive):
        if o.type != 'MESH':
            continue
        if o.hide_render or 'shield' in o.name.lower():
            continue
        # the folded carrier / packed-only parts of structures never join the wreck
        chain = [o] + list(_ancestors(o, actor.model_root))
        if any(c.get('hideWhenDeployed') or c.hide_render for c in chain):
            continue
        if abs(o.matrix_world.to_3x3().determinant()) < 1e-9:
            continue
        if len(o.data.polygons) == 0:
            continue
        g = 'hull'
        p = o.parent
        while p is not None and p is not actor.model_root:
            base = p.name.split('.')[0]
            if base.endswith('Pivot'):
                g = base
            p = p.parent
        groups.setdefault(g, []).append(o)
    return groups


def _group_bmesh(objs):
    """One world-space bmesh for a list of objects; returns (bm, materials)."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me = me.copy()
        ev.to_mesh_clear()
        me.transform(o.matrix_world)
        if o.matrix_world.determinant() < 0:
            me.flip_normals()
        remap = []
        for s in o.material_slots:
            m = s.material
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        if not remap:
            if None not in mats:
                mats.append(None)
            remap = [mats.index(None)]
        idx = [0] * len(me.polygons)
        me.polygons.foreach_get('material_index', idx)
        idx = [remap[min(i, len(remap) - 1)] for i in idx]
        me.polygons.foreach_set('material_index', idx)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    # game meshes are split at every UV seam / hard edge: weld so cuts produce closed loops
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    for e in bm.edges:      # keep the hard edges the split encoded
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > 0.6:
            e.smooth = False
    return bm, mats


def _cut_cell(bm_src, seeds, weights, i, inner_idx):
    """Power-diagram cell i of bm_src (copy), caps filled with material inner_idx."""
    bm = bm_src.copy()
    si = seeds[i]
    wi = weights[i]
    order = sorted(range(len(seeds)), key=lambda j: (seeds[j] - si).length)
    for j in order:
        if j == i:
            continue
        sj = seeds[j]
        d = sj - si
        L = d.length
        if L < 1e-6:
            continue
        n = d / L
        off = (sj.length_squared - si.length_squared - weights[j] + wi) / (2 * L)
        co = n * off
        if not bm.verts:
            break
        # skip planes that miss the remaining geometry
        if all((v.co - co).dot(n) <= 0 for v in bm.verts):
            continue
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=n,
                                     clear_outer=True, clear_inner=False)
        cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        cut_edges = [e for e in cut_edges if e.is_valid and e.is_boundary]
        if len(cut_edges) >= 3:
            try:
                fr = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=cut_edges, normal=n)
                faces = [f for f in fr['geom'] if isinstance(f, bmesh.types.BMFace)]
                for f in faces:
                    f.material_index = inner_idx
                    f.smooth = False
                    f.normal_update()
                    if f.normal.dot(n) < 0:
                        f.normal_flip()
            except Exception:  # noqa: BLE001 - a failed cap just leaves the cell hollow
                pass
    return bm


def _hull(points):
    """Convex hull (verts, faces) of points, decimated to <= 40 verts for the solver."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    try:
        bmesh.ops.convex_hull(bm, input=bm.verts[:])
    except Exception:  # noqa: BLE001
        pass
    used = [v for v in bm.verts if v.link_faces]
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bm.verts.index_update()
    verts = [v.co.copy() for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    if not verts:
        verts = [p.copy() for p in points[:8]]
        faces = []
    pts = verts
    if len(pts) > 40:
        # keep extremes in many directions
        rnd = random.Random(len(pts))
        keep = set()
        dirs = [Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() for _ in range(60)]
        for d in dirs:
            keep.add(max(range(len(pts)), key=lambda k: pts[k].dot(d)))
        pts = [pts[k] for k in sorted(keep)][:40]
    return verts, faces, pts


def _faction(actor):
    f = actor.entry.get('file', '')
    return 'gold' if ('alien/' in f or 'kesh_' in f or 'arcadian' in f) else 'orange'


def _fx_col(accent):
    return K.COL['arc_gold'] if accent == 'gold' else (1.0, 0.36, 0.06)


# ============================================================================ sparks / embers
def _spark_mesh():
    me = bpy.data.meshes.get('FxSparkMesh')
    if me:
        return me
    me = bpy.data.meshes.new('FxSparkMesh')
    # thin tapered streak along -X (tail) from the origin (head)
    r = 0.5
    verts = [(0, 0, 0), (-1, r, 0), (-1, -r * 0.5, r * 0.87), (-1, -r * 0.5, -r * 0.87), (-3.5, 0, 0)]
    faces = [(0, 1, 2), (0, 2, 3), (0, 3, 1), (4, 2, 1), (4, 3, 2), (4, 1, 3)]
    me.from_pydata(verts, [], faces)
    return me


def sparks(P, pos, t, n=24, speed=9.0, color=None, life=(0.35, 1.0), size=1.0, up=0.6, terr=None,
           extra_v=None):
    """Glowing streaks thrown out ballistically (orange/gold), bouncing off the ground."""
    col = color or (1.0, 0.42, 0.08)
    mat = spark_mat(P)
    me = _spark_mesh()
    rnd = P.rnd
    pos = K.V(pos)
    terr = terr or Terrain(P)
    space = _space(P)
    for i in range(n):
        o = K.link(bpy.data.objects.new('FxSpark', me))
        if not me.materials:
            me.materials.append(mat)
        for attr in ('visible_shadow', 'visible_diffuse', 'visible_glossy'):
            setattr(o, attr, False)
        d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), (rnd.gauss(0, 1) if space else abs(rnd.gauss(0, 1)) + up))).normalized()
        v = d * speed * rnd.uniform(0.35, 1.0)
        if extra_v is not None:
            v = v + extra_v
        L = rnd.uniform(*life)
        w = 0.022 * size * rnd.uniform(0.6, 1.3)
        c = col if rnd.random() > 0.15 else (1.0, min(1, col[1] * 1.5), col[2])
        o.rotation_mode = 'QUATERNION'
        x = pos.copy()
        f0 = P.T(t)
        nstep = max(2, int(L * P.fps))
        o.color = (*c, 0.0)
        o.keyframe_insert('color', frame=f0 - 1)
        for k in range(nstep + 1):
            tt = k / P.fps
            if k:
                for _ in range(4):
                    h = 1 / (P.fps * 4)
                    if not space:
                        v.z -= 9.81 * h
                    v *= (1 - (0.6 if space else 1.2) * h)
                    x += v * h
                    gz = terr.ground(x.x, x.y) if terr.has_ground else -1e9
                    if x.z < gz:
                        x.z = gz + 0.01
                        v.z = abs(v.z) * 0.3
                        v.x *= 0.6
                        v.y *= 0.6
            fr = f0 + k
            o.location = x
            sp = max(v.length, 0.5)
            o.rotation_quaternion = v.to_track_quat('X', 'Z')
            # streak length ~ distance moved in ~1/40 s
            o.scale = (max(w * 1.5, sp / 40 / 3.5 * 1.6), w, w)
            fade = 1.0 - (tt / L) ** 2
            o.color = (*c, max(0.0, fade))
            o.keyframe_insert('location', frame=fr)
            o.keyframe_insert('rotation_quaternion', frame=fr)
            o.keyframe_insert('scale', frame=fr)
            o.keyframe_insert('color', frame=fr)
        K.show_between(o, f0, f0 + nstep + 1)


# ============================================================================ explosion & co
def _is_air(P, pos, size):
    gz = P.ground_z(pos.x, pos.y) if getattr(P, 'ground', None) else (0.0 if not _space(P) else -1e9)
    return pos.z - gz > max(1.2, size * 0.45), gz


def _space(P):
    return getattr(P, 'ground', 'x') is None


def explosion(P, pos, t, size=2.0, debris=8, smoke=True, light=True, style=None):
    """Flipbook explosion. Returns False (caller falls back to the old effect) when the library
    has nothing usable."""
    pos = K.V(pos)
    air, gz = _is_air(P, pos, size)
    if _space(P):
        air = True
    space = _space(P)
    want = ('explo_space' if space else 'explo_air') if air else 'explo_ground'
    # library variants: gold Arcadian blast, big structure blast, small shell impact
    if not air:
        if style == 'gold' and find_flipbook('explo_ground_arc'):
            want = 'explo_ground_arc'
        elif size >= 4.0 and find_flipbook('explo_big'):
            want = 'explo_big'
        elif size <= 1.0 and find_flipbook('explo_small'):
            want = 'explo_small'
    man = find_flipbook(want)
    if man is None:
        return False
    rnd = P.rnd
    # card size: fireball ~ 1.6 * size across
    k = size * 1.15 / (man['extent_m'] * 0.55)
    if air:
        card(P, want, pos, t, size=k, mode='camera', push=min(0.6, size * 0.1))
    else:
        base = Vector((pos.x, pos.y, gz))
        card(P, want, base, t, size=k, mode='z_locked', push=min(0.8, size * 0.15))
        if find_flipbook('dust_ring') and size > 1.2:
            card(P, 'dust_ring', base, t + 0.02, size=k * 0.9, mode='z_locked', push=size * 0.1,
                 opacity=0.8)
    fl = find_flipbook('flash')
    if fl is not None:
        card(P, 'flash', pos, t, size=size * 1.1 / fl['extent_m'], tint=(1.0, 0.55, 0.2), emission=1.4,
             push=size * 0.3)
    if light:
        P.light(pos + Vector((0, 0, size * 0.6)), t, (1.0, 0.5, 0.18), energy=500 * size * size, dur=0.4,
                radius=size * 0.5)
    sparks(P, pos + Vector((0, 0, size * 0.1)), t, n=int(10 + 6 * size), speed=5 + 3 * size, size=size * 0.6,
           up=0.0 if space else 0.6)
    if debris:
        _dirt_chunks(P, pos if air else Vector((pos.x, pos.y, gz + 0.1)), t, size, debris, air)
    if smoke and not space and find_flipbook('smoke_puff'):
        card(P, 'smoke_puff', pos + Vector((0, 0, size * 0.4)), t + 0.35, size=size * 0.5,
             opacity=0.7, t1=t + 2.6)
    if not air:
        sc_ = K.sphere('Scorch', 1.0, scorch_mat(P), seg=(24, 6))
        sc_.location = (pos.x, pos.y, gz + 0.02)
        sc_.scale = (size * 0.9, size * 0.9, 0.01)
        sc_.rotation_euler.z = rnd.uniform(0, 6.28)
        sc_.visible_shadow = False
        K.show_between(sc_, P.T(t) + 2, P.T(P.seconds) + 1)
    return True


def _dirt_chunks(P, pos, t, size, n, air):
    """Irregular rock / scrap chunks with tumbling flight and real bounces."""
    terr = Terrain(P)
    rnd = P.rnd
    mat = P.charred if air else _dirt_mat(P)
    bodies, objs = [], []
    for i in range(n):
        s = min(size, 3.0) * rnd.uniform(0.03, 0.075)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        sx, sy, sz = rnd.uniform(0.6, 1.4), rnd.uniform(0.5, 1.2), rnd.uniform(0.3, 0.8)
        for v in bm.verts:
            v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz)) * s * rnd.uniform(0.75, 1.2)
        me = bpy.data.meshes.new('FxChunk')
        bm.to_mesh(me)
        pts = [v.co.copy() for v in bm.verts]
        bm.free()
        me.materials.append(mat)
        o = K.link(bpy.data.objects.new('Debris', me))
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.7, 2.0) if not air else rnd.uniform(-1, 1)))
        v = d.normalized() * (size ** 0.5) * rnd.uniform(2.2, 5.0)
        w = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 8
        b = Body(pts, [], max(0.01, s ** 3 * 8), pos + d * 0.1 * size, v, w)
        bodies.append(b)
        objs.append(o)
    space = _space(P)
    simulate(P, bodies, terr, t, P.seconds + 1 / P.fps if space else min(P.seconds, t + 3.0),
             gravity=0.0 if space else 9.81, drag=0.25 if space else 0.05)
    for o, b in zip(objs, bodies):
        key_body(o, b, P)
        K.show_between(o, P.T(t), P.T(P.seconds) + 1)


def _dirt_mat(P):
    if getattr(P, '_fx_dirt', None):
        return P._fx_dirt
    col = P.palette['g1'] if hasattr(P, 'palette') else (0.3, 0.24, 0.18)
    P._fx_dirt = K.pbr_mat('FxDirt', tuple(c * 0.7 for c in col), rough=1.0)
    return P._fx_dirt


def fire_patch(P, pos, t0, t1, size=0.6, parent=None, light=True):
    """Looping fire cards (+ a flickering point light). False if no fire flipbook."""
    man = find_flipbook('fire_loop')
    if man is None:
        return False
    pos = K.V(pos)
    k = size * 2.2 / man['extent_m']
    card(P, 'fire_loop', pos, t0, size=k, t1=t1, parent=parent, mode='camera')
    rnd = P.rnd
    if size > 0.5:
        off = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * size * 0.45
        card(P, 'fire_loop', pos + off, t0 + 0.1, size=k * 0.7, t1=t1, parent=parent, mode='camera')
    if light:
        L = K.link(bpy.data.objects.new('FxFireLight', bpy.data.lights.new('FxFireLight', 'POINT')))
        L.data.color = (1.0, 0.45, 0.12)
        L.data.shadow_soft_size = size * 0.6
        if parent is not None:
            L.parent = parent
        L.location = pos + Vector((0, 0, size * 0.8))
        f = P.T(t0)
        L.data.energy = 0
        L.data.keyframe_insert('energy', frame=f - 1)
        base = 260 * size * size + 60
        while f < P.T(t1):
            L.data.energy = base * rnd.uniform(0.7, 1.15)
            L.data.keyframe_insert('energy', frame=f + 3)
            f += 3
        L.data.energy = 0
        L.data.keyframe_insert('energy', frame=P.T(t1) + 1)
    return True


def smoke_column(P, pos, t0, t1, size=1.0):
    man = find_flipbook('smoke_plume')
    if man is None:
        return False
    k = size * 3.0 / man['extent_m']
    card(P, 'smoke_plume', K.V(pos), t0, size=k, t1=t1, opacity=0.75, mode='camera')
    return True


# ============================================================================ destroy
def destroy(actor, t, size=None, wreck=True, debris=14):
    P = actor.P
    rnd = random.Random(hash((actor.name, round(t, 3))) & 0xffffffff)
    size = size or actor.size * 0.5
    f_t = P.T(t)
    groups = _collect_meshes(actor, t)
    if not groups:
        return False
    sc = bpy.context.scene
    sc.frame_set(int(round(f_t)))
    terr = Terrain(P)
    space = _space(P)
    kind = actor.entry.get('kind', 'unit')
    accent = _faction(actor)
    M = actor.root.matrix_world.copy()
    Mr = M.to_quaternion().to_matrix().to_4x4()
    Mr.translation = M.translation
    Minv = Mr.inverted()
    # unit velocity (air units keep flying)
    p_prev = actor.pos_at(max(0.0, t - 0.1))
    p_now = actor.pos_at(t)
    v_unit = (p_now - p_prev) / 0.1 if t > 0.1 else Vector()
    # bbox of everything (world)
    allpts = []
    gbm = {}
    for g, objs in groups.items():
        bm, mats = _group_bmesh(objs)
        gbm[g] = (bm, mats)
        allpts += [v.co.copy() for v in list(bm.verts)[::max(1, len(bm.verts) // 400)]]
    lo = Vector((min(p.x for p in allpts), min(p.y for p in allpts), min(p.z for p in allpts)))
    hi = Vector((max(p.x for p in allpts), max(p.y for p in allpts), max(p.z for p in allpts)))
    center = (lo + hi) / 2
    R = max(0.5, max(hi.x - lo.x, hi.y - lo.y) / 2)
    H = max(0.3, hi.z - lo.z)
    gz = terr.ground(center.x, center.y) if terr.has_ground else lo.z
    # hover units (a metre or two up) are ground units whose wreck drops and crashes; only real
    # flyers break up in the air
    air = space or (lo.z - gz > max(2.5, 0.8 * H) and kind != 'structure')
    S = max(0.4, actor.size / 4.5)
    blast_dir = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized()
    blast = center + blast_dir * R * 0.35 - Vector((0, 0, H * 0.15))
    # ---------------------------------------------------------------- cells per group
    hot = hot_mat(P, accent)
    pieces = []   # dict(bm, mats, role)
    for g, (bm, mats) in gbm.items():
        verts = [v.co.copy() for v in bm.verts]
        if not verts:
            continue
        glo = Vector((min(p.x for p in verts), min(p.y for p in verts), min(p.z for p in verts)))
        ghi = Vector((max(p.x for p in verts), max(p.y for p in verts), max(p.z for p in verts)))
        gsize = (ghi - glo).length
        gc = (glo + ghi) / 2
        mats_ext = mats + [hot]
        inner = len(mats_ext) - 1
        if g != 'hull':
            role = 'turret' if g == 'TurretPivot' else 'part'
            if kind == 'structure':
                role = 'topple'
            nseed = 2 if gsize > 0.75 * actor.size and kind != 'structure' else 1
            if nseed == 1:
                pieces.append(dict(bm=bm, mats=mats_ext, role=role))
                continue
            seeds = [verts[rnd.randrange(len(verts))].lerp(gc, 0.4) for _ in range(nseed)]
            weights = [0.0] * nseed
            roles = [role] + ['medium'] * (nseed - 1)
        else:
            seeds, weights, roles = _hull_seeds(rnd, verts, gc, glo, ghi, R, H, kind, air, wreck, debris,
                                                blast, Minv, Mr)
        for i in range(len(seeds)):
            cb = _cut_cell(bm, seeds, weights, i, inner)
            if len(cb.faces) < 4:
                cb.free()
                continue
            # split far-apart islands of a cell only when tiny (keeps chunks coherent)
            pieces.append(dict(bm=cb, mats=mats_ext, role=roles[i]))
        bm.free()
    if not pieces:
        return False
    # ---------------------------------------------------------------- bodies
    bodies = []
    for pc in pieces:
        bm = pc['bm']
        bm.normal_update()
        com = Vector()
        area = 0.0
        for f in bm.faces:
            a = f.calc_area()
            com += f.calc_center_median() * a
            area += a
        com = com / area if area > 0 else sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        for v in bm.verts:
            v.co -= com
        hv, hf, hpts = _hull([v.co for v in bm.verts])
        ext = [max(p[i] for p in hv) - min(p[i] for p in hv) for i in range(3)]
        vol = max(1e-4, ext[0] * ext[1] * ext[2] * 0.45)
        pc.update(com=com, hull_v=hv, hull_f=hf, hull_pts=hpts, vol=vol, ext=max(ext))
    vmax = max(pc['vol'] for pc in pieces)
    # role by size inside hull cells: 'core' already marked; big ones -> medium
    for pc in pieces:
        role = pc['role']
        out = pc['com'] - blast
        out.z = max(out.z, 0.0)
        dirn = out.normalized() if out.length > 1e-4 else Vector((0, 0, 1))
        small = pc['vol'] < vmax * 0.08
        if role == 'core':
            v = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(1.2, 2.2) * S))
            w = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3))) * 0.9
            if kind == 'structure':
                v = Vector((0, 0, 0.6 * S))
                w = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.25
        elif role == 'turret':
            pop = rnd.random() < 0.8
            hd = Vector((dirn.x, dirn.y, 0))
            hd = hd.normalized() if hd.length > 1e-3 else Vector((1, 0, 0))
            v = hd * rnd.uniform(2.4, 3.6) * S + Vector((0, 0, (rnd.uniform(4.5, 6.2) if pop else 2.2) * S ** 0.5))
            w = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.6))).normalized() * rnd.uniform(2.5, 5.0)
        elif role == 'part':
            v = dirn * rnd.uniform(2.0, 4.0) * S + Vector((0, 0, rnd.uniform(3.0, 6.0) * S ** 0.5))
            w = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(3, 7)
        elif role == 'topple':
            v = dirn * rnd.uniform(0.6, 1.8) * S + Vector((0, 0, rnd.uniform(0.5, 2.0)))
            axis = Vector((0, 0, 1)).cross(dirn)
            w = (axis.normalized() if axis.length > 1e-4 else Vector((1, 0, 0))) * rnd.uniform(0.6, 1.6)
        elif small or role == 'small':
            v = dirn * rnd.uniform(3.0, 7.0) * S + Vector((0, 0, rnd.uniform(2.5, 6.5) * S ** 0.5))
            w = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(6, 14)
        else:
            v = dirn * rnd.uniform(1.5, 4.0) * S + Vector((0, 0, rnd.uniform(2.5, 5.5) * S ** 0.5))
            w = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(2.5, 7)
        if air:
            v = v_unit * rnd.uniform(0.75, 1.0) + dirn * (v.length * 0.6) + Vector((0, 0, rnd.uniform(0, 2)))
        elif kind != 'structure':
            v = v + Vector((v_unit.x, v_unit.y, 0)) * rnd.uniform(0.4, 0.7)   # keep some momentum
        if space:
            v = v_unit + dirn * rnd.uniform(1.0, 4.0) * S
            w = w * 0.5
        b = Body(pc['hull_pts'], pc['hull_f'], pc['vol'] * 2.0, pc['com'], v, w)
        pc['body'] = b
        bodies.append(b)
    # ---------------------------------------------------------------- simulate: big first, then
    # the rest with settled big pieces as colliders
    t_end = P.seconds + 1 / P.fps
    order = sorted(pieces, key=lambda pc: -pc['vol'])
    nbig = 1 if kind != 'structure' else 2
    gravity = 0.0 if space else 9.81
    big = [pc['body'] for pc in order[:nbig]]
    rest = [pc['body'] for pc in order[nbig:]]
    if pieces[0].get('role') == 'core' and kind == 'structure':
        pass
    drag = 0.18 if space else 0.05      # space: debris drifts, tumbles and slows slightly
    simulate(P, big, terr, t, t_end, gravity=gravity, drag=drag)
    if not space:
        for pc in order[:nbig]:
            b = pc['body']
            ts = b.settle_t if b.settle_t is not None else t + 1.2
            R_ = b.q.to_matrix()
            terr.add_collider([b.x + R_ @ p for p in pc['hull_v']], pc['hull_f'], ts)
    simulate(P, rest, terr, t, t_end, gravity=gravity, drag=drag)
    # ---------------------------------------------------------------- objects
    f_show = f_t + 1
    tag = actor.name
    objs = []
    for i, pc in enumerate(pieces):
        me = bpy.data.meshes.new(f'{tag}_FragMesh')
        pc['bm'].to_mesh(me)
        pc['bm'].free()
        for m in pc['mats']:
            me.materials.append(m if m is hot else soot_variant(P, m))
        o = K.link(bpy.data.objects.new(f'{tag}_Frag', me))
        o['fx_role'] = pc['role']
        key_body(o, pc['body'], P)
        _key_heat(o, P, t, pc, rnd)
        K.show_between(o, f_show, P.T(P.seconds) + 2)
        pc['obj'] = o
        objs.append(o)
    # ---------------------------------------------------------------- fx
    col = _fx_col(accent)
    if air:
        epos = center
    else:
        epos = Vector((blast.x, blast.y, max(gz + min(0.5, H * 0.2), lo.z + 0.3 * H)))   # hover: at the unit
    explosion(P, epos, t, size=size, debris=0, smoke=False, light=True,
              style='gold' if accent == 'gold' else None)
    sparks(P, center, t, n=int(26 * S + 10), speed=10 * S, color=col, size=S, terr=terr,
           extra_v=v_unit if air else None)
    if accent == 'orange':   # a few cyan electrical sparks as Terran power systems short out
        sparks(P, center + Vector((0, 0, H * 0.3)), t + 0.05, n=6, speed=5 * S, color=K.COL['terran_neon'],
               life=(0.15, 0.4), size=S * 0.8, terr=terr)
    if space:
        return True
    big_pc = order[0]
    bb = big_pc['body']
    if wreck:
        _burn(P, big_pc, t, size, terr, air)
        # secondary fires on the next big pieces
        for pc in order[1:3]:
            if pc['vol'] > vmax * 0.25 and rnd.random() < 0.7:
                b2 = pc['body']
                t2 = max(t + rnd.uniform(0.2, 0.6), (b2.settle_t or b2.landed or t) + 0.05)
                if t2 < P.seconds - 0.3:
                    _burn(P, pc, t2, size * 0.45, terr, air, smoke=False, light=False, delay=False)
    if air:
        for pc in order[:4]:
            _smoke_trail(P, pc, t, size)
    return True


def _hull_seeds(rnd, verts, gc, glo, ghi, R, H, kind, air, wreck, debris, blast, Minv, Mr):
    seeds, weights, roles = [], [], []
    nv = len(verts)

    def sample(pred=None, pull=0.25):
        for _ in range(60):
            p = verts[rnd.randrange(nv)]
            if pred is None or pred(p):
                return p.lerp(gc, pull + rnd.uniform(0, 0.25))
        return verts[rnd.randrange(nv)].lerp(gc, pull)

    n_small = max(3, min(12, int(debris * 0.6)))
    if kind == 'structure':
        z_cut = glo.z + (ghi.z - glo.z) * 0.38
        seeds.append(Vector((gc.x, gc.y, glo.z + (ghi.z - glo.z) * 0.12)))
        weights.append((0.62 * max(R, (ghi.z - glo.z) * 0.35)) ** 2)
        roles.append('core')
        for _ in range(5):
            seeds.append(sample(lambda p: p.z > z_cut, 0.15))
            weights.append(0.0)
            roles.append('topple')
    elif air or not wreck:
        for _ in range(4):
            seeds.append(sample(None, 0.2))
            weights.append(0.0)
            roles.append('medium')
    else:
        # core keeps the lower chassis; the upper deck / sides tear off in medium chunks
        seeds.append(Vector((gc.x, gc.y, glo.z + (ghi.z - glo.z) * 0.2)))
        weights.append((0.42 * R) ** 2)
        roles.append('core')
        zmid = glo.z + (ghi.z - glo.z) * 0.45
        for _ in range(5):
            seeds.append(sample(lambda p: p.z > zmid, 0.05))
            weights.append(0.0)
            roles.append('medium')
    # small cluster on the blast side
    bside = blast + (blast - gc).normalized() * R * 0.5 if (blast - gc).length > 1e-4 else blast
    for _ in range(n_small):
        p = sample(lambda p: (p - bside).length < R * 0.9, 0.0)
        seeds.append(p + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * R * 0.08)
        weights.append(-(0.05 * R) ** 2)
        roles.append('small')
    return seeds, weights, roles


def _key_heat(o, P, t, pc, rnd):
    """Object Color: R heat (cools ~1-2 s), G soot, B power-off (neon flickers out)."""
    f0 = P.T(t)
    small = pc['role'] == 'small'
    cool = rnd.uniform(0.8, 1.3) if small else rnd.uniform(1.4, 2.2)
    if pc['role'] == 'core':
        cool = 2.6
    resid = 0.12 if pc['role'] == 'core' else 0.0
    soot = rnd.uniform(0.55, 0.8)
    pts = [(0.0, 0.88, 0.0, 0.0), (0.06, 0.88, 0.25 * soot, 1.0), (0.12, 0.85, 0.5 * soot, 0.3),
           (0.2, 0.8, 0.7 * soot, 1.0), (0.3, 0.72, soot, 0.6), (0.42, 0.62, soot, 1.0)]
    for u in (0.35, 0.6, 0.85, 1.0):
        pts.append((cool * u + 0.4, max(resid, 0.62 * (1 - u) ** 1.6), soot, 1.0))
    for tt, h, s, b in pts:
        o.color = (h, s, b, 1.0)
        o.keyframe_insert('color', frame=f0 + tt * P.fps)


def _top_point(pc, frame):
    b = pc['body']
    x, q = pose_at(b, frame)
    R = q.to_matrix()
    pts = [x + R @ p for p in pc['hull_v']]
    zt = max(p.z for p in pts)
    near = [p for p in pts if p.z > zt - 0.35] or pts
    c = sum(near, Vector()) / len(near)
    return Vector((c.x, c.y, zt)), x, q


def _burn(P, pc, t, size, terr, air, smoke=True, light=True, delay=True):
    """Fire riding on a piece (local to it) from just after the blast; smoke plume from where it
    comes to rest."""
    b = pc['body']
    o = pc['obj']
    f_end = P.T(P.seconds) + 1
    t_fire = t + 0.12 if delay else t
    if air:
        t_fire = b.landed if b.landed is not None else t + 0.2
    rest_f = P.T(b.settle_t) if b.settle_t is not None else f_end
    top, x, q = _top_point(pc, min(rest_f, f_end))
    local = q.to_matrix().transposed() @ (top - x)
    local.z -= 0.12 * pc['ext']
    fs = max(0.4, min(1.8, pc['ext'] * 0.58))
    fire_patch(P, local, t_fire, P.seconds + 0.5, size=fs, parent=o, light=light)
    if smoke:
        smoke_column(P, top + Vector((0, 0, 0.1)), t_fire + 0.25, P.seconds + 0.5, size=max(0.7, fs * 1.4))


def _smoke_trail(P, pc, t, size):
    """Smoke puffs left behind a falling piece until it lands."""
    if find_flipbook('smoke_puff') is None and find_flipbook('smoke_plume') is None:
        return
    name = 'smoke_puff' if find_flipbook('smoke_puff') else 'smoke_plume'
    b = pc['body']
    t_land = b.landed if b.landed is not None else P.seconds
    tt = t + 0.05
    k = max(0.25, pc['ext'] * 0.35)
    while tt < min(t_land, P.seconds):
        x, q = pose_at(b, P.T(tt))
        e = card(P, name, x, tt, size=k * 0.8, t1=min(P.seconds + 0.5, tt + 1.4), opacity=0.4,
                 fade_in=1, fade_out=0.8 * P.fps)
        if e is not None:
            e.scale = (0.5,) * 3
            e.keyframe_insert('scale', frame=P.T(tt))
            e.scale = (1.6,) * 3
            e.keyframe_insert('scale', frame=P.T(tt + 1.4))
        tt += 0.09
