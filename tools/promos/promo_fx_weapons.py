"""Weapon-shot, impact and shield effects for the promo clips (bodies behind the kit's
Promo.muzzle_flash / projectile / missile / lightning / beam / impact / shield_dome and Actor.fire).

Everything is geometry + shared shaders: no per-frame materials, no image sprites, so the
effects work without the flipbook library. Per-object parameters live in Object Color (rgb,
alpha = opacity) and object custom properties read by Attribute(Object) nodes:

    fx_e     emission strength (keep 1.5-3.5: Standard view transform clips above ~1)
    fx_p     facing falloff power (1 = hard rod, 3 = soft haze)
    fx_tail  0..1 fade from local +X (head, bright) to -X (tail, gone)
    fx_hot   0..1 how much the centre of the glow goes white-hot
    fx_band, fx_bandk, fx_scroll   scrolling energy along local X (beams)
    fx_w     smoke noise evolution, fx_d smoke density

Shared materials (one each per scene): FxGlow (soft emissive glow), FxSmoke (light grey
volumetric puff), FxScorch (ground scorch decal with cooling ember), FxShield* (shield shell,
lattice and hit ripple). Glow-type materials carry 'emit_node' so scene shadow-off sweeps
catch them; every FX object also turns its own shadow visibility off.

Time arguments are seconds; P is the kit Promo.
"""
import math

import bpy  # noqa: I001
import bmesh
from mathutils import Matrix, Vector

import promo_kit as K

TAU = 2 * math.pi
UP = Vector((0, 0, 1))
HOT_WHITE = (1.0, 0.93, 0.8)
SMOKE_GREY = (0.74, 0.73, 0.71)
FIRE_COLS = ((1.0, 0.45, 0.1), (1.0, 0.62, 0.22))   # COL['fire'], COL['tracer']: ballistic


def _c(P):
    """Per-scene cache (materials, meshes)."""
    if not hasattr(P, '_wfx'):
        P._wfx = {}
    return P._wfx


def _is_ballistic_col(col):
    return col is None or any(sum(abs(a - b) for a, b in zip(col, f)) < 0.02 for f in FIRE_COLS)


def _gz(P, x, y):
    try:
        return P.ground_z(x, y) if getattr(P, 'ground', None) else 0.0
    except Exception:
        return 0.0


def _rand_perp(P, d):
    d = d.normalized()
    a = d.cross(UP if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized()
    b = d.cross(a).normalized()
    ang = P.rnd.uniform(0, TAU)
    return a * math.cos(ang) + b * math.sin(ang)


def _basis(d):
    d = d.normalized()
    s = d.cross(UP)
    s = s.normalized() if s.length > 1e-4 else Vector((0, 1, 0))
    u = s.cross(d).normalized()
    return d, s, u


def _cone_dir(P, axis, spread_deg):
    """Random unit vector within spread_deg of axis."""
    axis = axis.normalized()
    c = math.cos(math.radians(spread_deg))
    z = P.rnd.uniform(c, 1.0)
    r = math.sqrt(max(0.0, 1 - z * z))
    p = _rand_perp(P, axis)
    return (axis * z + p * r).normalized()


# ----------------------------------------------------------------------------- node helper
class _NT:
    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        self.m.use_nodes = True
        self.nt = self.m.node_tree
        self.nt.nodes.clear()
        self.out = self.node('ShaderNodeOutputMaterial')

    def node(self, kind, **kw):
        n = self.nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        elif isinstance(v, (tuple, list)) and len(v) == 3 and sock.type == 'RGBA':
            sock.default_value = (*v, 1.0)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op)
        n.use_clamp = clamp
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        if c is not None:
            self.put(n.inputs[2], c)
        return n.outputs[0]

    def vmath(self, op, a, b=None, out=0):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return n.outputs[out]

    def attr(self, name, out='Fac'):
        return self.node('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=name).outputs[out]

    def mixc(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='RGBA')
        self.put(n.inputs[0], fac)
        self.put(n.inputs[6], a)
        self.put(n.inputs[7], b)
        return n.outputs[2]

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.put(n.inputs[0], v)
        return n.outputs

    def comb(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self.put(n.inputs[0], x)
        self.put(n.inputs[1], y)
        self.put(n.inputs[2], z)
        return n.outputs[0]

    def mixsh(self, fac, a, b):
        n = self.node('ShaderNodeMixShader')
        self.put(n.inputs[0], fac)
        self.link(a, n.inputs[1])
        self.link(b, n.inputs[2])
        return n.outputs[0]


# ----------------------------------------------------------------------------- materials
def glow_mat(P):
    """Soft emissive glow. Brightness falls off with |N.I|^fx_p, so spheres read as glows and
    rods as soft light lines (never as solid tubes)."""
    c = _c(P)
    if 'glow' in c:
        return c['glow']
    b = _NT('FxGlow')
    geo = b.node('ShaderNodeNewGeometry')
    oi = b.node('ShaderNodeObjectInfo')
    tc = b.node('ShaderNodeTexCoord')
    d = b.math('ABSOLUTE', b.vmath('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming'], out=1))
    fac = b.math('POWER', d, b.attr('fx_p'))
    fac = b.math('MULTIPLY', fac, b.math('SUBTRACT', 1.0, geo.outputs['Backfacing']))
    ox = b.sep(tc.outputs['Object'])
    g = b.math('MULTIPLY_ADD', ox[0], 0.5, 0.5)  # 0 at tail (-X) .. 1 at head (+X)
    g = b.math('MINIMUM', b.math('MAXIMUM', g, 0.0), 1.0)
    tail = b.math('SUBTRACT', 1.0, b.math('MULTIPLY', b.attr('fx_tail'), b.math('SUBTRACT', 1.0, b.math('POWER', g, 0.7))))
    fac = b.math('MULTIPLY', fac, tail)
    # scrolling energy bands along X
    nz = b.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = 2.0
    bx = b.math('SUBTRACT', b.math('MULTIPLY', ox[0], b.attr('fx_bandk')), b.attr('fx_scroll'))
    b.put(nz.inputs['Vector'], b.comb(bx, b.math('MULTIPLY', ox[1], 1.5), b.math('MULTIPLY', ox[2], 1.5)))
    band = b.math('MULTIPLY_ADD', b.math('SUBTRACT', nz.outputs['Fac'], 0.5), b.math('MULTIPLY', b.attr('fx_band'), 2.4), 1.0)
    fac = b.math('MULTIPLY', fac, b.math('MAXIMUM', band, 0.0))
    # noisy breakup (fire blossoms): fac *= lerp(1, eroded noise, fx_noise)
    nz2 = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    nz2.inputs['Scale'].default_value = 1.8
    nz2.inputs['Detail'].default_value = 4.0
    b.put(nz2.inputs['Vector'], tc.outputs['Object'])
    b.put(nz2.inputs['W'], b.math('MULTIPLY_ADD', oi.outputs['Random'], 30.0, b.attr('fx_w')))
    ero = b.math('MULTIPLY_ADD', nz2.outputs['Fac'], 2.6, -0.75, clamp=True)
    fac = b.math('MULTIPLY', fac, b.math('MULTIPLY_ADD', b.math('SUBTRACT', ero, 1.0), b.attr('fx_noise'), 1.0))
    fac = b.math('MULTIPLY', fac, oi.outputs['Alpha'], clamp=True)
    hot = b.math('MULTIPLY', b.math('POWER', d, b.math('MULTIPLY', b.attr('fx_p'), 3.0)), b.attr('fx_hot'), clamp=True)
    col = b.mixc(hot, oi.outputs['Color'], HOT_WHITE)
    em = b.node('ShaderNodeEmission')
    b.put(em.inputs['Color'], col)
    b.put(em.inputs['Strength'], b.attr('fx_e'))
    tr = b.node('ShaderNodeBsdfTransparent')
    b.link(b.mixsh(fac, tr.outputs[0], em.outputs[0]), b.out.inputs['Surface'])
    b.m['emit_node'] = em.name
    c['glow'] = b.m
    return b.m


def slug_mat(P):
    """Tracer material: FxGlow under the kit's old 'Slug' name (scenes that look materials
    up by that name and tweak their emit_node keep working; strength is driven per object)."""
    c = _c(P)
    if 'slug' not in c:
        m = glow_mat(P).copy()
        m.name = 'Slug'
        c['slug'] = m
    return c['slug']


def smoke_mat(P):
    """Light volumetric puff: density = eroded 4D noise inside a soft ball, never black."""
    c = _c(P)
    if 'smoke' in c:
        return c['smoke']
    # ray-marched (biased) volumes: ~10x faster than the default null-scattering for these
    # small heterogeneous puffs, visually identical at this scale
    bpy.context.scene.cycles.volume_biased = True
    b = _NT('FxSmoke')
    oi = b.node('ShaderNodeObjectInfo')
    tc = b.node('ShaderNodeTexCoord')
    co = tc.outputs['Object']
    r = b.vmath('LENGTH', co, out=1)
    fall = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, r), 2.6, clamp=True)
    fall = b.math('MULTIPLY', fall, fall)
    nz = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    nz.inputs['Scale'].default_value = 1.6
    nz.inputs['Detail'].default_value = 3.0
    nz.inputs['Roughness'].default_value = 0.55
    b.put(nz.inputs['Vector'], co)
    b.put(nz.inputs['W'], b.math('MULTIPLY_ADD', oi.outputs['Random'], 40.0, b.attr('fx_w')))
    ero = b.math('MULTIPLY_ADD', nz.outputs['Fac'], 2.4, -0.8)
    dens = b.math('MULTIPLY', b.math('MAXIMUM', ero, 0.0), fall)
    dens = b.math('MULTIPLY', dens, b.math('MULTIPLY', oi.outputs['Alpha'], b.attr('fx_d')))
    pv = b.node('ShaderNodeVolumePrincipled')
    b.put(pv.inputs['Color'], oi.outputs['Color'])
    b.put(pv.inputs['Density'], dens)
    pv.inputs['Anisotropy'].default_value = 0.3
    pv.inputs['Absorption Color'].default_value = (0.85, 0.85, 0.85, 1)
    pv.inputs['Emission Color'].default_value = (1.0, 0.42, 0.1, 1)
    b.put(pv.inputs['Emission Strength'], b.math('MULTIPLY', b.attr('fx_e'), b.math('MINIMUM', dens, 1.0)))
    b.link(pv.outputs[0], b.out.inputs['Volume'])
    c['smoke'] = b.m
    return b.m


def scorch_mat(P):
    c = _c(P)
    if 'scorch' in c:
        return c['scorch']
    b = _NT('FxScorch')
    oi = b.node('ShaderNodeObjectInfo')
    tc = b.node('ShaderNodeTexCoord')
    co = tc.outputs['Object']
    nz = b.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 2.2
    nz.inputs['Detail'].default_value = 5.0
    b.put(nz.inputs['Vector'], b.vmath('ADD', co, b.comb(oi.outputs['Random'], b.math('MULTIPLY', oi.outputs['Random'], 7.0), 0.0)))
    r = b.math('ADD', b.vmath('LENGTH', co, out=1), b.math('MULTIPLY', b.math('SUBTRACT', nz.outputs['Fac'], 0.5), 0.7))
    a = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, r), 2.2, clamp=True)
    a = b.math('MULTIPLY', a, oi.outputs['Alpha'])
    df = b.node('ShaderNodeBsdfDiffuse')
    df.inputs['Color'].default_value = (0.018, 0.015, 0.012, 1)
    tr = b.node('ShaderNodeBsdfTransparent')
    base = b.mixsh(a, tr.outputs[0], df.outputs[0])
    # cooling ember speckle inside
    ember = b.math('MULTIPLY', b.math('MULTIPLY', b.math('SUBTRACT', nz.outputs['Fac'], 0.45), 4.0, clamp=True),
                   b.math('MULTIPLY', b.math('SUBTRACT', 0.85, r), 3.0, clamp=True))
    em = b.node('ShaderNodeEmission')
    b.put(em.inputs['Color'], oi.outputs['Color'])
    b.put(em.inputs['Strength'], b.math('MULTIPLY', ember, b.attr('fx_e')))
    add = b.node('ShaderNodeAddShader')
    b.link(base, add.inputs[0])
    b.link(em.outputs[0], add.inputs[1])
    b.link(add.outputs[0], b.out.inputs['Surface'])
    c['scorch'] = b.m
    return b.m


# ----------------------------------------------------------------------------- meshes
def _mesh(P, kind):
    c = _c(P)
    key = 'mesh_' + kind
    if key in c:
        return c[key]
    me = bpy.data.meshes.new('Fx' + kind)
    bm = bmesh.new()
    if kind in ('sphere', 'slug'):
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
    elif kind == 'ball':      # volume puffs: shape comes from the shader
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    elif kind == 'rod':       # along X, -1..1, radius 1, open ends
        bmesh.ops.create_cone(bm, cap_ends=False, segments=20, radius1=1.0, radius2=1.0, depth=2.0)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    elif kind == 'disk':
        bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    if kind in ('sphere', 'rod', 'slug'):
        for p in me.polygons:
            p.use_smooth = True
    if kind == 'ball':
        me.materials.append(smoke_mat(P))
    elif kind == 'disk':
        me.materials.append(scorch_mat(P))
    elif kind == 'slug':
        me.materials.append(slug_mat(P))
    else:
        me.materials.append(glow_mat(P))
    c[key] = me
    return me


def _fxobj(o):
    o.visible_shadow = False
    try:
        o.visible_diffuse = False
        o.visible_glossy = False
    except AttributeError:
        pass
    return o


GLOW_DEFAULTS = dict(fx_e=2.5, fx_p=2.0, fx_tail=0.0, fx_hot=0.0, fx_band=0.0, fx_bandk=1.0, fx_scroll=0.0,
                     fx_noise=0.0, fx_w=0.0)


def glow(P, name, color, kind='sphere', loc=(0, 0, 0), scale=(1, 1, 1), alpha=1.0, **params):
    o = K.link(bpy.data.objects.new(name, _mesh(P, kind)))
    o.location = loc
    o.scale = scale
    o.color = (*color, alpha)
    for k, v in GLOW_DEFAULTS.items():
        o[k] = float(params.get(k, v))
    return _fxobj(o)


_glow = glow


def kprop(o, name, frame, value, const=False):
    o[name] = float(value)
    o.keyframe_insert(f'["{name}"]', frame=frame)
    if const:
        _const(o, f'["{name}"]')


def kcol(o, frame, rgb=None, a=None):
    c = list(o.color)
    if rgb is not None:
        c[:3] = rgb
    if a is not None:
        c[3] = a
    o.color = c
    o.keyframe_insert('color', frame=frame)


def _const(o, path):
    ad = o.animation_data
    if ad and ad.action:
        for fc in K._fcurves(ad.action):
            if fc.data_path == path:
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT'


def flicker_light(P, pos, t0, t1, color, energy, radius=0.3, every=1, lo=0.55, hi=1.1, parent=None):
    L = K.link(bpy.data.objects.new('FxLight', bpy.data.lights.new('FxLight', 'POINT')))
    L.location = pos
    if parent is not None:
        L.parent = parent
    L.data.color = color
    L.data.shadow_soft_size = radius
    f0, f1 = int(round(P.T(t0))), int(round(P.T(t1)))
    L.data.energy = 0
    L.data.keyframe_insert('energy', frame=f0 - 1)
    for f in range(f0, f1 + 1, every):
        L.data.energy = energy * P.rnd.uniform(lo, hi)
        L.data.keyframe_insert('energy', frame=f)
    L.data.energy = 0
    L.data.keyframe_insert('energy', frame=f1 + 1)
    return L


# ----------------------------------------------------------------------------- building blocks
def smoke_puff(P, pos, t, r0=0.15, r1=0.8, life=1.6, vel=(0, 0, 0), color=None, dens=1.0,
               hot=0.0, stretch=None, wind=(0.35, 0.15, 0.25), fade_in=0.06):
    """One volumetric puff: grows r0 -> r1 (ease-out), coasts along vel (decelerating), drifts
    with the wind and rises, thins out. stretch=(dir, length): starts elongated along dir."""
    o = K.link(bpy.data.objects.new('FxPuff', _mesh(P, 'ball')))
    _fxobj(o)
    col = color or SMOKE_GREY
    o.color = (*col, 0.0)
    o['fx_e'] = 0.0
    o['fx_d'] = 3.0 * dens
    o['fx_w'] = 0.0
    vel = Vector(vel)
    wind = Vector(wind) * (1.0 if getattr(P, 'ground', None) else 0.25)
    pos = Vector(pos)
    o.rotation_mode = 'QUATERNION'
    if stretch is not None:
        o.rotation_quaternion = stretch[0].to_track_quat('X', 'Z')
    else:
        o.rotation_quaternion = _rand_perp(P, UP).to_track_quat('X', 'Z')
    f0 = P.T(t)
    n = 6
    for i in range(n + 1):
        u = i / n
        tt = life * u
        e = 1 - (1 - u) ** 2.2
        # coast: v * tau * (1 - exp(-t/tau))
        tau = 0.35
        o.location = pos + vel * tau * (1 - math.exp(-tt / tau)) + wind * tt
        r = r0 + (r1 - r0) * e
        if stretch is not None:
            sx = max(r, stretch[1] * (1 - u) ** 3)
            o.scale = (sx, r, r)
        else:
            o.scale = (r, r * 0.95, r * 0.9)
        fr = f0 + tt * P.fps
        o.keyframe_insert('location', frame=fr)
        o.keyframe_insert('scale', frame=fr)
        kprop(o, 'fx_w', fr, 0.25 * tt + 0.08 * u)
    kcol(o, f0 - 1, a=0.0)
    kcol(o, f0 + fade_in * P.fps, a=1.0)
    kcol(o, f0 + life * 0.35 * P.fps, a=0.55)
    kcol(o, f0 + life * P.fps, a=0.0)
    if hot:
        kprop(o, 'fx_e', f0, hot)
        kprop(o, 'fx_e', f0 + 0.16 * P.fps, 0.0)
    K.show_between(o, int(f0) - 1, int(f0 + life * P.fps) + 1)
    return o


def sparks(P, pos, t, n=10, speed=10.0, color=None, axis=UP, spread=70, life=(0.25, 0.6),
           width=0.025, gravity=9.8, drag=1.2, bounce=True):
    """Hot sparks: thin streaks stretched along their velocity, ballistic, cooling, bouncing."""
    pos = Vector(pos)
    col = color or (1.0, 0.5, 0.12)
    gz = _gz(P, pos.x, pos.y)
    if not getattr(P, 'ground', None):   # space: no gravity, nothing to bounce on
        gravity, bounce = 0.0, False
    f0 = P.T(t)
    dt = 1.0 / P.fps
    out = []
    for i in range(n):
        o = glow(P, 'Spk', HOT_WHITE, fx_e=3.2, fx_p=1.2, fx_hot=0.0, fx_tail=0.6)
        o.rotation_mode = 'QUATERNION'
        w = width * P.rnd.uniform(0.6, 1.3)
        v = _cone_dir(P, Vector(axis), spread) * speed * P.rnd.uniform(0.45, 1.25)
        L = P.rnd.uniform(*life)
        p = pos.copy()
        steps = max(2, int(L * P.fps))
        for k in range(steps + 1):
            fr = f0 + k
            o.location = p
            if v.length > 1e-3:
                o.rotation_quaternion = v.to_track_quat('X', 'Z')
            o.scale = (max(w * 2, 0.5 * v.length * dt), w, w)
            o.keyframe_insert('location', frame=fr)
            o.keyframe_insert('rotation_quaternion', frame=fr)
            o.keyframe_insert('scale', frame=fr)
            v = v * (1 - drag * dt) - Vector((0, 0, gravity * dt))
            p = p + v * dt
            if bounce and p.z < gz + 0.02 and v.z < 0:
                p.z = gz + 0.02
                v = Vector((v.x * 0.55, v.y * 0.55, -v.z * 0.3))
        u1 = f0 + steps
        kcol(o, f0, rgb=HOT_WHITE)
        kcol(o, f0 + steps * 0.3, rgb=col)
        kcol(o, u1, rgb=tuple(c * 0.6 for c in col))
        kprop(o, 'fx_e', f0, 3.4)
        kprop(o, 'fx_e', u1, 0.6)
        K.set_interp(o, 'LINEAR')
        K.show_between(o, int(f0), int(u1) + 1)
        out.append(o)
    return out


def flash(P, pos, t, radius, color, frames=(1, 2, 4), e=3.0, hot=0.7, parent=None, name='HitFlash'):
    """Expanding glow ball: grows for frames[0], holds to frames[1], fades out by frames[2]."""
    o = glow(P, name, color, loc=pos, fx_e=e, fx_p=1.6, fx_hot=hot)
    if parent is not None:
        o.parent = parent
    f0 = P.T(t)
    o.scale = (radius * 0.35,) * 3
    o.keyframe_insert('scale', frame=f0)
    o.scale = (radius,) * 3
    o.keyframe_insert('scale', frame=f0 + frames[0])
    o.scale = (radius * 1.15,) * 3
    o.keyframe_insert('scale', frame=f0 + frames[1])
    o.scale = (radius * 1.25,) * 3
    o.keyframe_insert('scale', frame=f0 + frames[2])
    kcol(o, f0, a=1.0)
    kcol(o, f0 + frames[1], a=0.8)
    kcol(o, f0 + frames[2], a=0.0)
    K.show_between(o, int(f0), int(f0 + frames[2]) + 1)
    return o


def star(P, pos, t, length, color, axis=None, n=6, frames=3, name='HitStar'):
    """Brief spiky star of tapered light petals (impact / contact flash)."""
    pos = Vector(pos)
    f0 = P.T(t)
    for i in range(n):
        d = _cone_dir(P, axis, 75) if axis is not None else _cone_dir(P, UP, 180)
        L = length * P.rnd.uniform(0.5, 1.0) * 0.5
        o = glow(P, name, color, fx_e=3.0, fx_p=1.2, fx_tail=1.0, fx_hot=0.5)
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = (-d).to_track_quat('X', 'Z')
        w = 0.05 * length
        o.location = pos + d * L * 0.8
        o.scale = (L * 0.6, w, w)
        o.keyframe_insert('scale', frame=f0)
        o.keyframe_insert('location', frame=f0)
        o.location = pos + d * L * 1.1
        o.scale = (L, w * 0.7, w * 0.7)
        o.keyframe_insert('scale', frame=f0 + frames)
        o.keyframe_insert('location', frame=f0 + frames)
        kcol(o, f0, a=1.0)
        kcol(o, f0 + frames, a=0.0)
        K.show_between(o, int(f0), int(f0 + frames) + 1)


def scorch(P, pos, t, radius, ember=None, ember_time=1.2):
    """Ground scorch decal (irregular soft edge), optional cooling embers."""
    pos = Vector(pos)
    o = K.link(bpy.data.objects.new('HitScorch', _mesh(P, 'disk')))
    _fxobj(o)
    o.location = (pos.x, pos.y, _gz(P, pos.x, pos.y) + 0.025)
    o.rotation_euler.z = P.rnd.uniform(0, TAU)
    o.scale = (radius * P.rnd.uniform(0.9, 1.1), radius * P.rnd.uniform(0.75, 1.0), 1)
    o.color = (*(ember or (1.0, 0.35, 0.06)), 0.9)
    f0 = P.T(t)
    o['fx_e'] = 0.0
    if ember:
        kprop(o, 'fx_e', f0, 3.0)
        kprop(o, 'fx_e', f0 + ember_time * 0.3 * P.fps, 1.5)
        kprop(o, 'fx_e', f0 + ember_time * P.fps, 0.0)
    K.show_between(o, int(f0) + 1, P.T(P.seconds) + 1)
    return o


def dirt_kick(P, pos, t, size=1.0, color=None):
    """Ground hit: dark clods thrown in arcs, a dust crown and a low ground ring of dust."""
    pos = Vector(pos)
    gz = _gz(P, pos.x, pos.y)
    base = Vector((pos.x, pos.y, gz))
    pal = getattr(P, 'palette', None)
    g = (pal['g1'] if pal and 'g1' in pal else (0.36, 0.29, 0.21))
    dust = tuple(min(1.0, 0.5 * (0.06 + c * 1.5) + 0.5 * w) for c, w in zip(g, (0.66, 0.53, 0.38)))
    clod_m = _c(P).get('clod') or K.pbr_mat('FxClod', tuple(c * 0.45 for c in g), rough=1.0)
    _c(P)['clod'] = clod_m
    f0 = P.T(t)
    for i in range(int(5 + 5 * size)):
        o = K.ico('FxClod', 1.0, clod_m, sub=0)
        s = 0.05 * size * P.rnd.uniform(0.5, 1.4)
        o.scale = (s, s * P.rnd.uniform(0.6, 1.3), s * P.rnd.uniform(0.5, 1.0))
        v = _cone_dir(P, UP, 40) * P.rnd.uniform(4, 9) * math.sqrt(size)
        L = 2 * v.z / 9.8
        n = max(3, int(L * P.fps / 2))
        for k in range(n + 1):
            tt = L * k / n
            o.location = base + Vector((v.x * tt, v.y * tt, max(0.03, v.z * tt - 4.9 * tt * tt)))
            o.rotation_euler = (tt * 11, tt * 7, tt * 5)
            o.keyframe_insert('location', frame=f0 + tt * P.fps)
            o.keyframe_insert('rotation_euler', frame=f0 + tt * P.fps)
        K.show_between(o, int(f0), int(f0 + L * P.fps) + 1)
    # crown: puffs thrown up and out, slowing
    for i in range(4 + int(3 * size)):
        d = _cone_dir(P, UP, 38)
        smoke_puff(P, base + Vector((0, 0, 0.15 * size)), t + P.rnd.uniform(0, 0.05),
                   r0=0.2 * size, r1=P.rnd.uniform(0.85, 1.25) * size, life=P.rnd.uniform(1.5, 2.2),
                   vel=d * P.rnd.uniform(2.5, 6.5) * size, color=dust, dens=1.3,
                   wind=(0.25, 0.1, 0.3))
    # low ring rolling outward
    for i in range(4):
        a = TAU * (i + P.rnd.uniform(-0.2, 0.2)) / 4
        d = Vector((math.cos(a), math.sin(a), 0.08))
        smoke_puff(P, base + d * 0.3 * size + Vector((0, 0, 0.12)), t + 0.03,
                   r0=0.2 * size, r1=0.8 * size, life=1.7, vel=d * 4.0 * size,
                   color=dust, dens=1.0, wind=(0.2, 0.1, 0.12))


# ----------------------------------------------------------------------------- impact
def impact(P, pos, t, size=1.0, color=None):
    """Hit: hot flash, spark spray, light; on the ground also dirt kick + scorch; energy hits
    (color given) are tinted and leave a glowing scorch."""
    pos = Vector(pos)
    energy = color is not None and not _is_ballistic_col(color)
    gz = _gz(P, pos.x, pos.y)
    ground = bool(getattr(P, 'ground', None)) and (pos.z - gz) < 0.35 + 0.3 * size
    fcol = color if energy else (1.0, 0.5, 0.14)
    lift = Vector((0, 0, 0.4 * size)) if ground else Vector()
    flash(P, pos + lift * (0.5 if energy else 1.0), t, (0.3 if energy else 0.5) * size, fcol, frames=(1, 2, 4),
          e=3.2, hot=0.9)
    star(P, pos + lift * 0.6, t, (0.8 if energy else 1.3) * size, fcol, axis=UP if ground else None,
         n=6 if ground else 7)
    if not energy:   # short-lived ragged fire blossom
        for i in range(3):
            d = _cone_dir(P, UP, 70) if ground else _cone_dir(P, UP, 180)
            o = flash(P, pos + lift + d * 0.25 * size, t + 0.01 * i, P.rnd.uniform(0.35, 0.5) * size,
                      (1.0, 0.36, 0.06), frames=(2, 3, 7), e=2.4, hot=0.3, name='HitFire')
            o['fx_noise'] = 1.0
            o['fx_p'] = 1.0
            kprop(o, 'fx_w', P.T(t), 0.0)
            kprop(o, 'fx_w', P.T(t) + 8, 0.6)
            o.keyframe_insert('location', frame=P.T(t))
            o.location = o.location + d * 0.5 * size + Vector((0, 0, 0.3 * size))
            o.keyframe_insert('location', frame=P.T(t) + 7)
    sparks(P, pos + Vector((0, 0, 0.05)), t, n=int(min(22, 8 + 7 * size)), speed=9 * math.sqrt(size),
           color=fcol if energy else (1.0, 0.45, 0.1), axis=UP if ground else Vector((0, 0, 0.3)),
           spread=65 if ground else 140, life=(0.2, 0.55))
    P.light(pos + Vector((0, 0, 0.6 * size)), t, fcol, energy=(600 if energy else 1400) * size, dur=0.15,
            radius=0.3 * size)
    if ground:
        dirt_kick(P, pos, t, size=size * (0.6 if energy else 1.0))
        scorch(P, pos, t, 0.75 * size, ember=fcol if energy else (1.0, 0.33, 0.06),
               ember_time=1.6 if energy else 0.7)
    else:
        for i in range(2):
            smoke_puff(P, pos + _rand_perp(P, UP) * 0.2 * size, t + 0.05 + 0.04 * i, r0=0.15 * size,
                       r1=0.7 * size, life=1.4, vel=(0, 0, 1.0), dens=0.7)


_impact = impact


# ----------------------------------------------------------------------------- muzzle flash
def muzzle_flash(P, muzzle_obj, t, color, size=1.0):
    """Multi-petal flash along the barrel (+X of the muzzle empty): white-hot core, a long
    forward petal, 4-5 side petals in a star, a light and (for guns) a short smoke puff."""
    sc = bpy.context.scene
    f0 = P.T(t)
    cur = sc.frame_current
    sc.frame_set(int(round(f0)) - 1)          # pose just before the barrel starts recoiling
    mw = muzzle_obj.matrix_world.copy()
    # anchor: a muzzle riding a split barrel would drag the flash back into the turret as the
    # barrel collapses, so hang the flash on the barrel's parent at the pre-recoil muzzle pose
    par = muzzle_obj.parent
    anchor = par.parent if (par is not None and 'barrel_len' in par.keys() and par.parent) else muzzle_obj
    rig = K.empty('MuzzleFx')
    rig.parent = anchor
    loc, rot, _ = mw.decompose()
    rig.matrix_world = Matrix.LocRotScale(loc, rot, Vector((1, 1, 1)))
    sc.frame_set(cur)
    gun = _is_ballistic_col(color)
    pcol = (1.0, 0.42, 0.08) if gun else color
    s = size
    parts = []
    # small hot core at the muzzle
    core = glow(P, 'MuzzleCore', pcol, fx_e=2.8, fx_p=1.8, fx_hot=0.6)
    core.parent = rig
    core.location = (0.06 * s, 0, 0)
    parts.append((core, (0.13 * s, 0.1 * s, 0.1 * s)))
    # tight forward cone of flame: 3 slightly divergent tapered tongues (bright at the muzzle,
    # fading toward the tip; spindle +X points back at the muzzle), one with ragged noise
    for k in range(3):
        Lf = s * (0.42 if k == 0 else P.rnd.uniform(0.22, 0.34))
        wdt = s * (0.075 if k == 0 else P.rnd.uniform(0.045, 0.065))
        dv = Vector((1.0, P.rnd.uniform(-0.12, 0.12), P.rnd.uniform(-0.12, 0.12))).normalized() if k else Vector((1, 0, 0))
        o = glow(P, 'MuzzleTongue', pcol, fx_e=2.6, fx_p=1.5, fx_tail=0.95, fx_hot=0.3 if k == 0 else 0.15,
                 fx_noise=0.0 if k == 0 else 0.6, fx_w=P.rnd.uniform(0, 9))
        o.parent = rig
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = (-dv).to_track_quat('X', 'Z')
        o.location = Vector((0.05 * s, 0, 0)) + dv * Lf
        parts.append((o, (Lf, wdt, wdt)))
    # 2-3 short irregular side petals, leaning forward, at random (not evenly spaced) rolls
    npet = P.rnd.choice((2, 3, 3)) if gun else 2
    rolls = sorted(P.rnd.uniform(0, TAU) for _ in range(npet))
    for a in rolls:
        el = math.radians(P.rnd.uniform(30, 58))   # angle from the barrel axis
        d = Vector((math.cos(el), math.sin(el) * math.cos(a), math.sin(el) * math.sin(a)))
        Ls = s * P.rnd.uniform(0.09, 0.2)
        o = glow(P, 'MuzzlePetal', pcol, fx_e=2.4, fx_p=1.3, fx_tail=0.95, fx_hot=0.2)
        o.parent = rig
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = (-d).to_track_quat('X', 'Z')
        o.location = Vector((0.06 * s, 0, 0)) + d * Ls
        w_ = s * P.rnd.uniform(0.035, 0.055)
        parts.append((o, (Ls, w_, w_)))
    for o, sc_ in parts:   # 2-3 frames: full, stretched and dimmer, gone
        o.scale = tuple(x * 0.5 for x in sc_)
        o.keyframe_insert('scale', frame=f0 - 1)
        o.scale = sc_
        o.keyframe_insert('scale', frame=f0)
        o.scale = (sc_[0] * 1.25, sc_[1] * 0.7, sc_[2] * 0.7)
        o.keyframe_insert('scale', frame=f0 + 1)
        o.scale = (sc_[0] * 1.35, sc_[1] * 0.35, sc_[2] * 0.35)
        o.keyframe_insert('scale', frame=f0 + 2)
        kcol(o, f0, a=1.0)
        kcol(o, f0 + 1, a=0.55)
        kcol(o, f0 + 2, a=0.0)
        K.show_between(o, int(f0), int(f0) + 2 + (1 if s > 1.2 else 0))
    P.light(mw.translation + mw.to_3x3().normalized() @ Vector((0.3 * s, 0, 0)), t, pcol, energy=110 * s, dur=0.07,
            radius=0.2 * s)
    if gun:
        fwd = (mw.to_3x3().normalized() @ Vector((1, 0, 0))).normalized()
        base = mw.translation
        for i in range(4):   # quick puff that pushes out, slows and drifts off
            smoke_puff(P, base + fwd * (0.2 + 0.15 * i) * s + _rand_perp(P, fwd) * 0.05 * s, t + 0.03 + 0.012 * i,
                       r0=0.12 * s, r1=(0.45 + 0.07 * i) * s, life=P.rnd.uniform(0.9, 1.3),
                       vel=fwd * (3.5 - 0.6 * i) * s + _rand_perp(P, fwd) * 0.3 + Vector((0, 0, 0.35)),
                       dens=0.4, hot=0.8 if i == 0 else 0.0, wind=(0.6, 0.25, 0.35))
    return rig


# ----------------------------------------------------------------------------- projectiles
def _path(p0, p1, arc):
    d = p1 - p0

    def at(u):
        return p0 + d * u + Vector((0, 0, 4 * arc * u * (1 - u)))
    return at


def projectile(P, p0, p1, t0, speed, color, size=0.15, arc=0.0, streak=True, style=None):
    """Tracer: white-hot slug + short motion-streak + soft glow. style: None/'tracer',
    'shell' (arcing, faint smoke wake), 'bomb' (dark falling body, no glow)."""
    p0, p1 = K.V(p0), K.V(p1)
    d = p1 - p0
    at = _path(p0, p1, arc)
    dur = max(0.04, d.length / speed)
    if style is None:
        style = 'shell' if (arc and streak) else ('bomb' if not streak and not arc and _is_ballistic_col(color) and speed < 25 else 'tracer')
    if style == 'bomb' and d.z < -1.0:
        # released level: carries forward and accelerates down (gravity-shaped drop)
        def at(u):
            return p0 + Vector((d.x * u, d.y * u, d.z * u * u))
    col = color
    n = max(2, int(math.ceil(dur * P.fps)))
    rig = K.empty('Slug')
    rig.rotation_mode = 'QUATERNION'
    objs = []
    v_frame = speed / P.fps
    if style == 'bomb':
        body = K.sphere('Bomb', 1.0, _c(P).get('bomb') or K.pbr_mat('FxBomb', (0.12, 0.12, 0.12), rough=0.5, metal=0.6), seg=(12, 8))
        _c(P)['bomb'] = body.data.materials[0]
        body.parent = rig
        body.scale = (size * 2.2, size, size)
        objs.append(body)
    else:
        sat = (col[0], col[1] * 0.7, col[2] * 0.45)     # glow/streak stay saturated, core goes white
        head = glow(P, 'SlugHead', col, kind='slug', fx_e=3.2, fx_p=0.8, fx_hot=1.0)
        head.parent = rig
        head.scale = (size * 1.5, size * 0.42, size * 0.42)
        glo = glow(P, 'SlugGlow', sat, kind='slug', alpha=0.8, fx_e=1.2, fx_p=2.6, fx_hot=0.0)
        glo.parent = rig
        glo.scale = (size * 2.6, size * 1.2, size * 1.2)
        # motion streak: about one frame of travel (plus motion blur in finals)
        Ls = min(max(size * 4, v_frame * (0.6 if streak else 0.4)), 4.0) * 0.5
        st = glow(P, 'SlugStreak', sat, kind='slug', fx_e=2.4, fx_p=1.3, fx_tail=1.0, fx_hot=0.25)
        st.parent = rig
        st.location = (-Ls + size, 0, 0)
        st.scale = (Ls, size * 0.45, size * 0.45)
        objs += [head, glo, st]
    for i in range(n + 1):
        u = i / n
        p = at(u)
        q = at(min(1.0, u + 0.01)) - at(max(0.0, u - 0.01))
        rig.location = p
        rig.rotation_quaternion = q.to_track_quat('X', 'Z')
        fr = P.T(t0 + dur * u)
        rig.keyframe_insert('location', frame=fr)
        rig.keyframe_insert('rotation_quaternion', frame=fr)
    K.set_interp(rig, 'LINEAR')
    f0, f1 = P.T(t0), P.T(t0 + dur) + 1
    for o in objs:
        K.show_between(o, f0, f1)
    if style == 'shell':      # faint smoke wake behind an arcing shell
        k = 0
        for i in range(1, 2 * n):
            u = i / (2 * n)
            p = at(u)
            smoke_puff(P, p, t0 + dur * u, r0=0.08, r1=0.55, life=1.4, dens=0.9, wind=(0.3, 0.1, 0.2))
            k += 1
    elif style == 'bomb':
        for i in range(1, n, 2):
            u = i / n
            smoke_puff(P, at(u), t0 + dur * u, r0=0.04, r1=0.2, life=0.6, dens=0.25)
    return t0 + dur


def missile(P, p0, p1, t0, speed=32, color=None, arc=2.5, wobble=0.4, trail=True):
    """Missile: metal body, white-hot motor with a flickering flame and a light, a lingering
    volumetric smoke trail that expands, drifts and fades, corkscrew wobble, accelerating."""
    p0, p1 = K.V(p0), K.V(p1)
    d = p1 - p0
    dist = d.length
    dur = max(0.2, dist / speed * 1.25)
    col = color or (1.0, 0.45, 0.1)
    fwd, side, up = _basis(d)
    ph = P.rnd.uniform(0, TAU)
    turns = P.rnd.uniform(2.0, 3.0)

    def U(tau):   # accelerating: slow off the rail
        return 0.3 * tau + 0.7 * tau * tau

    def at(u):
        env = 4 * u * (1 - u)
        cork = min(1.0, u * 6) * (1 - u) * 0.18
        a = ph + TAU * turns * u
        return (p0 + d * u + Vector((0, 0, arc * env)) + side * wobble * math.sin(ph + u * 9) * env
                + side * cork * math.cos(a) + up * cork * math.sin(a))

    rig = K.empty('Missile')
    rig.rotation_mode = 'QUATERNION'
    bm_ = _c(P).get('mbody') or K.pbr_mat('MissileBody', (0.72, 0.72, 0.74), 0.35, 0.6)
    _c(P)['mbody'] = bm_
    body = K.sphere('MissileBody', 1.0, bm_, seg=(12, 8))
    body.parent = rig
    body.scale = (0.38, 0.075, 0.075)
    band = K.sphere('MissileBand', 1.0, _c(P).get('mband') or K.pbr_mat('MissileBand', (0.9, 0.35, 0.06), 0.5), seg=(12, 8))
    _c(P)['mband'] = band.data.materials[0]
    band.parent = rig
    band.location = (0.22, 0, 0)
    band.scale = (0.08, 0.079, 0.079)
    fins = []
    for k in range(4):
        fn = K.cube('MissileFin', 1.0, bm_)
        fn.parent = rig
        a = k * math.pi / 2
        fn.location = (-0.3, 0.08 * math.cos(a), 0.08 * math.sin(a))
        fn.rotation_euler = (a, 0, 0)
        fn.scale = (0.12, 0.08, 0.008)
        fins.append(fn)
    motor = glow(P, 'MissileMotor', col, loc=(-0.42, 0, 0), scale=(0.11, 0.09, 0.09), fx_e=3.4, fx_p=1.0, fx_hot=1.0)
    motor.parent = rig
    flame = glow(P, 'MissileFlame', col, fx_e=2.8, fx_p=1.4, fx_tail=1.0, fx_hot=0.6)
    flame.parent = rig
    halo = glow(P, 'MissileHalo', col, loc=(-0.5, 0, 0), scale=(0.45, 0.32, 0.32), fx_e=1.0, fx_p=3.0)
    halo.parent = rig
    n = max(4, int(math.ceil(dur * P.fps)))
    pts = []
    for i in range(n + 1):
        tau = i / n
        pts.append((tau, at(U(tau))))
    for i, (tau, p) in enumerate(pts):
        q = pts[min(i + 1, n)][1] - pts[max(i - 1, 0)][1]
        rig.location = p
        rig.rotation_quaternion = q.to_track_quat('X', 'Z')
        fr = P.T(t0 + dur * tau)
        rig.keyframe_insert('location', frame=fr)
        rig.keyframe_insert('rotation_quaternion', frame=fr)
        Lf = P.rnd.uniform(0.45, 0.75) * min(1.0, 0.4 + tau * 3)
        flame.location = (-0.45 - Lf, 0, 0)
        flame.scale = (Lf, 0.1 * P.rnd.uniform(0.85, 1.15), 0.1)
        flame.keyframe_insert('location', frame=fr)
        flame.keyframe_insert('scale', frame=fr)
    K.set_interp(rig, 'LINEAR')
    f0, f1 = P.T(t0), P.T(t0 + dur) + 1
    for o in [body, band, motor, flame, halo] + fins:
        K.show_between(o, f0, f1)
    L = flicker_light(P, (-0.6, 0, 0), t0, t0 + dur, col, 260, radius=0.15, lo=0.75, hi=1.1, parent=rig)
    if trail:
        # emit by distance (not time) so the fast end of the flight has no gaps
        spacing = 0.32
        acc = 0.0
        ns = 600
        prev = at(U(0.0))
        for i in range(1, ns):
            tau = i / ns
            p = at(U(tau))
            acc += (p - prev).length
            prev = p
            if acc < spacing:
                continue
            acc = 0.0
            q = at(U(min(1.0, tau + 0.005))) - at(U(max(0.0, tau - 0.005)))
            q = q.normalized() if q.length > 1e-6 else fwd
            tp = t0 + dur * tau
            smoke_puff(P, p - q * 0.5, tp, r0=0.1, r1=P.rnd.uniform(0.9, 1.35),
                       life=P.rnd.uniform(2.8, 3.6), vel=-q * 1.0 + _rand_perp(P, q) * 0.35, dens=1.1,
                       hot=1.6, stretch=(q, spacing * 1.3), wind=(0.45, 0.2, 0.3), fade_in=0.0)
    return t0 + dur


# ----------------------------------------------------------------------------- lightning
def _jag(P, a, b, jag, depth, perp_bias=None):
    """Midpoint-displacement jagged path a -> b (list of Vectors)."""
    pts = [a, b]
    amp = (b - a).length * jag
    for lvl in range(depth):
        new = [pts[0]]
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            m = (p + q) / 2 + _rand_perp(P, q - p) * amp * P.rnd.uniform(-1, 1)
            new += [m, q]
        pts = new
        amp *= 0.62
    return pts


def _curve(P, name, pts, radius, radii=None, res=2):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = res
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1)
        if radii:
            sp.points[i].radius = radii[i]
    sp.use_smooth = True
    o = K.link(bpy.data.objects.new(name, cu))
    cu.materials.append(glow_mat(P))
    for k, v in GLOW_DEFAULTS.items():
        o[k] = float(v)
    return _fxobj(o)


def _endpoint(P, x, lift=True):
    """Endpoint -> function(frame) -> world Vector. Accepts a point, an Actor (its body centre,
    following it), an Object (its world origin, following it) or a callable f(t_seconds)."""
    if hasattr(x, 'pos_at') and hasattr(x, 'root'):          # Actor
        ship = getattr(x, 'entry', {}).get('kind') == 'ship'     # ships hang centred on their root
        off = Vector((0, 0, x.size * 0.18 if (lift and not ship) else 0.0))
        return (lambda f: _world_at_frame(x.root, f) + off), True
    if isinstance(x, bpy.types.Object):
        return (lambda f: _world_at_frame(x, f)), True
    if callable(x):
        return (lambda f: Vector(x((f - 1) / P.fps))), True
    v = K.V(x)
    return (lambda f: v), False


def _world_at_frame(obj, f):
    sc = bpy.context.scene
    if sc.frame_current != f:
        sc.frame_set(int(f))
    return obj.matrix_world.translation.copy()


def _pool_light(P, f0, f1, color, energy, radius, pos_fn, lo=0.5, hi=1.0):
    """Borrow one of at most 4 shared point lights for frames f0..f1 (lightning is called
    every few frames by some scenes; one light per call is too heavy). Skips when all busy."""
    c = _c(P)
    pool = c.setdefault('lpool', [])
    L = None
    for ent in pool:
        if ent[1] < f0 - 1:
            L = ent
            break
    if L is None:
        if len(pool) >= 4:
            return None
        ob = K.link(bpy.data.objects.new('FxBoltLight', bpy.data.lights.new('FxBoltLight', 'POINT')))
        ob.data.energy = 0
        ob.data.keyframe_insert('energy', frame=0)
        L = [ob, -99]
        pool.append(L)
    ob, _ = L
    L[1] = f1 + 1
    d = ob.data
    d.color = color
    d.shadow_soft_size = radius
    d.keyframe_insert('color', frame=f0 - 1)
    d.energy = 0
    d.keyframe_insert('energy', frame=f0 - 1)
    for f in range(f0, f1 + 1):
        ob.location = pos_fn(f)
        ob.keyframe_insert('location', frame=f)
        d.energy = energy * P.rnd.uniform(lo, hi)
        d.keyframe_insert('energy', frame=f)
    d.energy = 0
    d.keyframe_insert('energy', frame=f1 + 1)
    for idb, path in ((ob, 'location'), (d, 'energy'), (d, 'color')):
        ad = idb.animation_data
        for fc in K._fcurves(ad.action):
            if fc.data_path == path:
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT'
    return ob


def bolt(P, p0, p1, f0, nframes, color, width=0.05, jag=0.18, branches=2, glow_=True, flick=None,
         follow=None):
    """One lightning strike visible for frames [f0, f0+nframes): thin white-gold core, gold
    glow, soft haze on the trunk, tapered jagged forks and twigs. follow=(fn0, fn1) frame ->
    point: the strike is re-aimed every frame so it stays attached to moving ends."""
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    depth = max(3, min(7, int(math.log2(max(2.0, L / 0.15)))))
    trunk = _jag(P, p0, p1, jag * 0.6, depth)
    if getattr(P, 'ground', None):
        for q in trunk:      # never dive into the ground between the ends
            q.z = max(q.z, _gz(P, q.x, q.y) + 0.06)
    hot = tuple(0.3 * c + 0.7 * w for c, w in zip(color, HOT_WHITE))
    objs = []
    nn = len(trunk)
    taper = [0.75 + 0.25 * math.sin(math.pi * i / (nn - 1)) for i in range(nn)]
    core = _curve(P, 'BoltCore', trunk, width * 0.4, taper, res=1)
    core.color = (*hot, 1)
    core['fx_e'], core['fx_p'], core['fx_hot'] = 3.4, 0.5, 1.0
    objs.append(core)
    if glow_:
        g = _curve(P, 'BoltGlow', trunk, width * 2.8, taper, res=3)
        g.color = (*color, 1)
        g['fx_e'], g['fx_p'] = 2.2, 3.0
        tap_h = [0.12 + 0.88 * math.sin(math.pi * i / (nn - 1)) for i in range(nn)]   # haze pinches at the ends
        h = _curve(P, 'BoltGlow', trunk, width * 8.0, tap_h, res=3)
        h.color = (*color, 0.5)
        h['fx_e'], h['fx_p'] = 0.8, 3.5
        objs += [g, h]
    nb = branches + P.rnd.randint(0, 2) if branches else 0
    for b in range(nb):
        k = P.rnd.randint(int(nn * 0.15), int(nn * 0.8))
        a = trunk[k]
        main = (trunk[min(k + 2, nn - 1)] - trunk[max(k - 2, 0)]).normalized()
        dirb = (main + _rand_perp(P, main) * P.rnd.uniform(0.5, 1.1)).normalized()
        bl = L * P.rnd.uniform(0.12, 0.3)
        bp = _jag(P, a, a + dirb * bl, jag * 0.7, max(2, depth - 2))
        m = len(bp)
        rad = [1.0 - 0.85 * i / (m - 1) for i in range(m)]
        c2 = _curve(P, 'BoltFork', bp, width * 0.3, rad, res=1)
        c2.color = (*hot, 1)
        c2['fx_e'], c2['fx_p'], c2['fx_hot'] = 3.0, 0.6, 0.6
        objs.append(c2)
        if glow_:
            g2 = _curve(P, 'BoltForkGlow', bp, width * 1.5, rad)
            g2.color = (*color, 0.8)
            g2['fx_e'], g2['fx_p'] = 1.8, 2.0
            objs.append(g2)
        if P.rnd.random() < 0.5 and m > 4:   # twig
            k2 = P.rnd.randint(1, m - 3)
            a2 = bp[k2]
            d2 = (dirb + _rand_perp(P, dirb)).normalized()
            tw = _jag(P, a2, a2 + d2 * bl * 0.45, jag * 0.7, 2)
            c3 = _curve(P, 'BoltFork', tw, width * 0.2, [1.0 - 0.9 * i / (len(tw) - 1) for i in range(len(tw))], res=1)
            c3.color = (*hot, 1)
            c3['fx_e'], c3['fx_p'] = 2.6, 0.6
            objs.append(c3)
    if follow is not None and nframes > 1:
        # rig: maps the strike's own p0->p1 onto the live ends each frame (stretch along X)
        fn0, fn1 = follow
        q0 = (p1 - p0).to_track_quat('X', 'Z')
        T0 = Matrix.LocRotScale(p0, q0, Vector((1, 1, 1)))
        rig = K.empty('BoltRig')
        rig.rotation_mode = 'QUATERNION'
        for f in range(f0, f0 + nframes):
            a, b_ = fn0(f), fn1(f)
            d = b_ - a
            rig.location = a
            rig.rotation_quaternion = d.to_track_quat('X', 'Z') if d.length > 1e-5 else q0
            rig.scale = (d.length / max(L, 1e-4), 1, 1)
            for path in ('location', 'rotation_quaternion', 'scale'):
                rig.keyframe_insert(path, frame=f)
        for path in ('location', 'rotation_quaternion', 'scale'):
            _const(rig, path)
        inv = T0.inverted()
        for o in objs:
            o.parent = rig
            o.matrix_parent_inverse = inv
    # brightness: snap on, then flicker down (constant per frame)
    for o in objs:
        base = o['fx_e']
        seq = flick or [1.0, 0.6, 0.85, 0.45]
        for i in range(nframes):
            kprop(o, 'fx_e', f0 + i, base * seq[i % len(seq)] * P.rnd.uniform(0.9, 1.05), const=True)
        K.show_between(o, f0, f0 + nframes)
    return objs


def lightning(P, p0, p1, t0, t1, color=None, width=0.05, jag=0.18, branches=2, segs=10, glow=True,
              sparks_=True, light=True):
    """Arcadian gold lightning p0 -> p1: re-strikes every 2-3 frames with a new jagged,
    branching shape; contact glow + sparks each strike; flickering pooled light. p0 / p1 may
    be points, Actors, Objects or callables t -> point: moving ends are followed per frame.
    All bolts share the FxGlow material, so calling this every frame stays cheap."""
    color = color or K.COL['arc_gold']
    fn0, mv0 = _endpoint(P, p0, lift=False)
    fn1, mv1 = _endpoint(P, p1)
    moving = mv0 or mv1
    cur = bpy.context.scene.frame_current
    f0 = int(round(P.T(t0)))
    f1 = max(f0 + 1, int(round(P.T(t1))))
    f = f0
    first = True
    while f < f1:
        nfr = min(f1 - f, P.rnd.choice((2, 2, 3)))
        a, b = fn0(f), fn1(f)
        bolt(P, a, b, f, nfr, color, width=width, jag=jag, branches=branches, glow_=glow,
             flick=[1.0, 0.55, 0.8] if not first else [1.0, 0.7, 0.9],
             follow=(fn0, fn1) if moving else None)
        if sparks_ and width >= 0.03:
            sparks(P, b, (f - 1) / P.fps, n=4 if not first else 7, speed=6.0, color=color,
                   axis=UP if getattr(P, 'ground', None) else (b - a), spread=80,
                   life=(0.15, 0.4), width=0.018, gravity=9.8 if getattr(P, 'ground', None) else 0.0)
        first = False
        f += nfr
    # contact + source glows (flickering, following the ends)
    for fn, r, nm in ((fn1, 0.1 + width * 2, 'BoltContact'), (fn0, 0.08 + width * 1.5, 'BoltSource')):
        o = _glow(P, nm, color, loc=fn(f0), scale=(r,) * 3, fx_e=3.0, fx_p=2.2, fx_hot=0.9)
        for fr in range(f0, f1 + 2):
            kprop(o, 'fx_e', fr, 3.0 * P.rnd.uniform(0.55, 1.0) if fr < f1 else 1.2, const=True)
            if moving:
                o.location = fn(fr)
                o.keyframe_insert('location', frame=fr)
        K.show_between(o, f0, f1 + 2)
    if light:
        L = (fn1(f0) - fn0(f0)).length
        _pool_light(P, f0, f1, color, 110 + 5 * L, 0.1, lambda fr: fn1(fr) + Vector((0, 0, 0.28)), lo=0.45, hi=1.0)   # low + weak: tight hotspot, no ground smear
    bpy.context.scene.frame_set(cur)
    return t1


def lightning_thruster(P, obj, t0, t1, local=(0, 0, 0), axis=(-1, 0, 0), length=1.6, width=0.03,
                       n=2, spread=0.35, color=None, light=True):
    """Arcadian thrust: n short crackling gold bolts streaming from a point on `obj` (Object
    or Actor; local offset/axis in its space) and re-striking every 2 frames, following the
    ship. Same shared materials as lightning(); one pooled light."""
    color = color or K.COL['arc_gold']
    ob = obj.root if hasattr(obj, 'root') else obj
    loc = Vector(local)
    ax = Vector(axis).normalized()

    def start(f):
        _world_at_frame(ob, f)
        return ob.matrix_world @ loc
    cur = bpy.context.scene.frame_current
    f0, f1 = int(round(P.T(t0))), int(round(P.T(t1)))
    for k in range(n):
        f = f0 + k % 2
        while f < f1:
            nfr = min(f1 - f, P.rnd.choice((2, 2, 3)))
            end_local = loc + (ax + _rand_perp(P, ax) * P.rnd.uniform(0, spread)).normalized() * length * P.rnd.uniform(0.6, 1.1)

            def endf(fr, e=end_local):
                _world_at_frame(ob, fr)
                return ob.matrix_world @ e
            bolt(P, start(f), endf(f), f, nfr, color, width=width, jag=0.22, branches=1, glow_=True,
                 flick=[1.0, 0.65, 0.85], follow=(start, endf))
            f += nfr
    o = _glow(P, 'ThrustCore', color, scale=(width * 6,) * 3, fx_e=3.0, fx_p=1.5, fx_hot=0.9)
    o.parent = ob
    o.location = loc
    K.show_between(o, f0, f1)
    if light:
        _pool_light(P, f0, f1, color, 300, 0.2, start, lo=0.6, hi=1.0)
    bpy.context.scene.frame_set(cur)


# ----------------------------------------------------------------------------- beams
def beam(P, p0, p1, t0, t1, color, width=0.15, strength=10):
    """Energy beam: white-hot core, coloured glow with energy scrolling source -> target,
    wide haze, snap-on / pinch-off, gentle flicker, bright contact with sparks and smoke.
    p0 / p1 may be points, Actors, Objects or callables t -> point (followed per frame)."""
    fn0, mv0 = _endpoint(P, p0, lift=False)
    fn1, mv1 = _endpoint(P, p1)
    moving = mv0 or mv1
    cur = bpy.context.scene.frame_current
    f0, f1 = P.T(t0), P.T(t1)
    fa = int(math.floor(f0))
    a0, b0 = fn0(fa), fn1(fa)
    d = b0 - a0
    Lh = max(d.length / 2, 1e-3)
    k = max(0.6, min(1.4, strength / 10.0))
    rig = K.empty('BeamRig')
    rig.location = (a0 + b0) / 2
    rig.rotation_mode = 'QUATERNION'
    rig.rotation_quaternion = d.to_track_quat('X', 'Z')
    hot = tuple(0.45 * c + 0.55 * w for c, w in zip(color, HOT_WHITE))
    parts = [
        glow(P, 'BeamCore', hot, kind='rod', scale=(Lh, width * 0.3, width * 0.3), fx_e=3.3 * k, fx_p=0.7, fx_hot=0.5,
             fx_band=0.12, fx_bandk=Lh / 0.6, fx_scroll=0.0),
        glow(P, 'BeamGlow', color, kind='rod', scale=(Lh, width, width), fx_e=2.4 * k, fx_p=1.8,
             fx_band=0.45, fx_bandk=Lh / 1.1, fx_scroll=0.0),
        glow(P, 'BeamHaze', color, kind='rod', scale=(Lh, width * 3.2, width * 3.2), alpha=0.6, fx_e=1.0, fx_p=2.8,
             fx_band=0.3, fx_bandk=Lh / 2.5, fx_scroll=0.0),
    ]
    for o in parts:
        o.parent = rig
    # width envelope on the rig (y/z), per-frame flicker; x stretches to follow moving ends
    rig.scale = (1, 0.05, 0.05)
    rig.keyframe_insert('scale', frame=f0 - 1)
    fr = fa
    first = True
    while fr <= int(f1):
        w = 1.35 if first else P.rnd.uniform(0.9, 1.08)
        sx = 1.0
        if moving:
            a, b = fn0(fr), fn1(fr)
            rig.location = (a + b) / 2
            if (b - a).length > 1e-4:
                rig.rotation_quaternion = (b - a).to_track_quat('X', 'Z')
            sx = (b - a).length / (2 * Lh)
            rig.keyframe_insert('location', frame=max(fr, f0))
            rig.keyframe_insert('rotation_quaternion', frame=max(fr, f0))
        rig.scale = (sx, w, w)
        rig.keyframe_insert('scale', frame=max(fr, f0))
        first = False
        fr += 1
    rig.scale = (rig.scale.x, 0.02, 0.02)
    rig.keyframe_insert('scale', frame=f1 + 2)
    flow = 24.0   # m/s the energy pattern travels source -> target
    for o in parts:
        o.keyframe_insert('["fx_scroll"]', frame=f0)
        o['fx_scroll'] = flow * o['fx_bandk'] / Lh * (f1 + 2 - f0) / P.fps
        o.keyframe_insert('["fx_scroll"]', frame=f1 + 2)
        ad = o.animation_data
        for fc in K._fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        K.show_between(o, int(f0), int(f1) + 3)
    # end glows (follow the ends)
    src = glow(P, 'BeamSource', color, loc=a0, scale=(width * 1.8,) * 3, fx_e=2.8, fx_p=1.5, fx_hot=0.6)
    hit = glow(P, 'BeamContact', color, loc=b0 + Vector((0, 0, width)), scale=(width * 3.0,) * 3, fx_e=2.6, fx_p=1.5,
               fx_hot=0.6)
    for o, fn in ((src, fn0), (hit, fn1)):
        for fr in range(int(f0), int(f1) + 2):
            kcol(o, fr, a=P.rnd.uniform(0.75, 1.0) if fr <= f1 else 0.3)
            if moving:
                o.location = fn(fr)
                o.keyframe_insert('location', frame=fr)
        _const(o, 'color')
        K.show_between(o, int(f0), int(f1) + 2)
    tt = t0
    space = not getattr(P, 'ground', None)
    while tt < t1:
        b = fn1(int(round(P.T(tt))))
        sparks(P, b, tt, n=3, speed=7.0, color=color, axis=(fn0(int(round(P.T(tt)))) - b) if space else UP,
               spread=75, life=(0.15, 0.4), width=0.018)
        tt += 2.0 / P.fps
    tt = t0 + 0.05
    while tt < t1:
        b = fn1(int(round(P.T(tt))))
        smoke_puff(P, b + Vector((0, 0, 0.1)), tt, r0=0.08, r1=0.4, life=1.2, vel=(0, 0, 0.8), dens=0.35)
        tt += 0.12
    fi0, fi1 = int(round(f0)), int(round(f1))
    _pool_light(P, fi0, fi1, color, 600 * k, 0.3, lambda fr: fn1(fr) + Vector((0, 0, 0.3)), lo=0.75, hi=1.0)
    _pool_light(P, fi0, fi1, color, 400 + 40 * d.length, d.length * 0.2,
                lambda fr: (fn0(fr) + fn1(fr)) / 2, lo=0.8, hi=1.0)
    bpy.context.scene.frame_set(cur)
    return t1


# ----------------------------------------------------------------------------- fire from a point
SHOT_SPEC = dict(   # colour, speed, flash, impact size  (same table as Actor.fire)
    cannon=('tracer', 60, 0.9, 1.0), heavy=('tracer', 50, 1.6, 1.8), autocannon=('tracer', 80, 0.45, 0.45),
    laser=('laser_blue', 140, 0.6, 0.5), missile=('fire', 32, 0.7, 1.2), shell=('tracer', 35, 1.0, 1.6),
    lightning=('arc_gold', 0, 0.6, 0.45), beam=('arc_gold', 0, 1.0, 1.4), bomb=('fire', 18, 0.0, 2.2))


def _source(P, src):
    """Shot origin -> (fn(frame) -> point, host object or None, local offset)."""
    if isinstance(src, tuple) and len(src) == 2 and not isinstance(src[0], (int, float)):
        host, off = src
        ob = host.root if hasattr(host, 'root') else host
        off = Vector(off)

        def fn(f):
            _world_at_frame(ob, f)
            return ob.matrix_world @ off
        return fn, ob, off
    if hasattr(src, 'root'):
        return (lambda f: _world_at_frame(src.root, f)), src.root, Vector()
    if isinstance(src, bpy.types.Object):
        return (lambda f: _world_at_frame(src, f)), src, Vector()
    v = K.V(src)
    return (lambda f: v), None, None


def shot(P, src, target, kind, t, color=None, size=1.0, speed=None, impact=True, impact_size=None,  # noqa: C901
         arc=None, spread=0.0, jag=None, branches=None, width=None, flash=True, dur=None):
    """Fire one shot from a point (no turret needed): src = point, Actor, Object, or
    (actor_or_object, local_offset) to ride a moving ship; target = point, Actor or Object.
    Kinds as Actor.fire. Projectiles lead a moving target. Returns the hit time."""
    cur = bpy.context.scene.frame_current
    spec = SHOT_SPEC[kind]
    col = color or K.COL[spec[0]]
    spd = speed or spec[1]
    isz = (impact_size or spec[3]) * size
    fn0, host, off = _source(P, src)
    fn1, moving_t = _endpoint(P, target)
    f = int(round(P.T(t)))
    p0 = fn0(f)
    # lead the target for travelling shots
    t_hit = t
    p1 = fn1(f)
    if spd:
        for _ in range(3):
            t_hit = t + (p1 - p0).length / spd * (1.25 if kind == 'missile' else 1.0)
            p1 = fn1(int(round(P.T(t_hit))))
    if spread:
        p1 = p1 + Vector((P.rnd.uniform(-spread, spread), P.rnd.uniform(-spread, spread), P.rnd.uniform(-spread, spread) * 0.5))
    # a muzzle empty at the origin, +X toward the target, riding the host
    if flash and spec[2] > 0:
        mz = K.empty('ShotMuzzle')
        d = (p1 - p0)
        q = d.to_track_quat('X', 'Z') if d.length > 1e-4 else Vector((1, 0, 0)).to_track_quat('X', 'Z')
        Mw = Matrix.LocRotScale(p0, q, Vector((1, 1, 1)))
        if host is not None:
            _world_at_frame(host, f)
            mz.parent = host
            mz.matrix_parent_inverse = host.matrix_world.inverted()
        mz.matrix_basis = Mw
        energy = kind in ('laser', 'lightning', 'beam')
        muzzle_flash(P, mz, t + 1.0 / P.fps, col if energy else K.COL['fire'], spec[2] * size)
    if kind == 'lightning':
        lightning(P, (lambda tt: fn0(int(round(P.T(tt))))) if host is not None else p0,
                  target if moving_t else p1, t, t + (dur or 0.18), color=col,
                  width=width if width is not None else 0.05 * size,
                  jag=0.18 if jag is None else jag, branches=2 if branches is None else branches)
        t_hit = t + 0.02
    elif kind in ('beam', 'laser'):
        d_ = dur or (0.45 if kind == 'beam' else 0.14 * max(1.0, size))
        w_ = width if width is not None else (0.18 if kind == 'beam' else 0.07) * size
        beam(P, (lambda tt: fn0(int(round(P.T(tt))))) if host is not None else p0,
             target if moving_t else p1, t, t + d_, col, width=w_, strength=10 if kind == 'beam' else 9)
        t_hit = t + 0.03
    elif kind == 'missile':
        t_hit = missile(P, p0, p1, t, speed=spd, color=col, arc=arc if arc is not None else 2.5)
    elif kind in ('shell', 'bomb'):
        t_hit = projectile(P, p0, p1, t, spd, col, size=0.18 * size,
                           arc=arc if arc is not None else (0.35 * (p1 - p0).length if kind == 'shell' else 0),
                           streak=kind == 'shell', style=kind)
    else:
        t_hit = projectile(P, p0, p1, t, spd, col, size=(0.1 if kind == 'autocannon' else 0.16) * size)
    if impact:
        hit_at = fn1(int(round(P.T(t_hit)))) if (moving_t and not spd) else p1
        _impact(P, hit_at, t_hit, size=isz, color=col if kind in ('laser', 'lightning', 'beam') else None)
    bpy.context.scene.frame_set(cur)
    return t_hit


# ----------------------------------------------------------------------------- shields
def _is_gold(col):
    return col is not None and col[0] > 0.8 and col[2] < 0.3


def _shield_masks(b, oi, tc):
    """Shared shield maths: facing d, normalised object position n, power-up mask."""
    geo = b.node('ShaderNodeNewGeometry')
    d = b.math('ABSOLUTE', b.vmath('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming'], out=1))
    n = b.vmath('NORMALIZE', tc.outputs['Object'])
    nz = b.sep(n)[2]
    up = b.math('SUBTRACT', b.math('MULTIPLY_ADD', b.attr('fx_up'), 2.4, -1.2), nz)
    mask = b.math('MULTIPLY', up, 5.0, clamp=True)
    front = b.math('EXPONENT', b.math('MULTIPLY', b.math('MULTIPLY', up, up), -40.0))
    return d, n, mask, front


def shield_shell_mat(P):
    """Faint shell: fresnel rim, per-triangle tint variation, slow shimmer; fx_dark tints what
    is behind it (Arcadian smoked-gold glass)."""
    c = _c(P)
    if 'sh_shell' in c:
        return c['sh_shell']
    b = _NT('FxShieldShell')
    oi = b.node('ShaderNodeObjectInfo')
    tc = b.node('ShaderNodeTexCoord')
    d, n, mask, front = _shield_masks(b, oi, tc)
    rim = b.math('POWER', b.math('SUBTRACT', 1.0, d), 3.0)
    face = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='fx_face').outputs['Fac']
    nz = b.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 1.2
    nz.inputs['Detail'].default_value = 2.0
    b.put(nz.inputs['Vector'], b.vmath('ADD', tc.outputs['Object'], b.comb(0.0, 0.0, b.attr('fx_t'))))
    shim = b.math('MULTIPLY_ADD', nz.outputs['Fac'], 1.2, 0.4)
    base = b.math('MULTIPLY_ADD', face, b.attr('fx_facek'), 0.04)
    fac = b.math('MULTIPLY', b.math('ADD', base, b.math('MULTIPLY', rim, 0.45)), shim)
    fac = b.math('MULTIPLY', b.math('MULTIPLY', fac, mask), oi.outputs['Alpha'], clamp=True)
    em = b.node('ShaderNodeEmission')
    b.put(em.inputs['Color'], oi.outputs['Color'])
    b.put(em.inputs['Strength'], b.attr('fx_e'))
    tr = b.node('ShaderNodeBsdfTransparent')
    tint = b.mixc(b.math('MULTIPLY', b.attr('fx_dark'), mask), (1.0, 1.0, 1.0), b.vmath('SCALE', oi.outputs['Color'], None))
    # SCALE uses inputs[3]; set it below
    sc_node = [nd for nd in b.nt.nodes if nd.bl_idname == 'ShaderNodeVectorMath' and nd.operation == 'SCALE'][-1]
    sc_node.inputs[3].default_value = 0.5
    b.put(tr.inputs['Color'], tint)
    b.link(b.mixsh(fac, tr.outputs[0], em.outputs[0]), b.out.inputs['Surface'])
    b.m['emit_node'] = em.name
    c['sh_shell'] = b.m
    return b.m


def shield_lattice_mat(P):
    c = _c(P)
    if 'sh_lat' in c:
        return c['sh_lat']
    b = _NT('FxShieldLattice')
    oi = b.node('ShaderNodeObjectInfo')
    tc = b.node('ShaderNodeTexCoord')
    d, n, mask, front = _shield_masks(b, oi, tc)
    rim = b.math('POWER', b.math('SUBTRACT', 1.0, d), 2.0)
    fac = b.math('MULTIPLY', b.math('ADD', b.math('MULTIPLY_ADD', rim, 0.7, 0.3), b.math('MULTIPLY', front, 3.0)), mask)
    fac = b.math('MULTIPLY', fac, oi.outputs['Alpha'], clamp=True)
    em = b.node('ShaderNodeEmission')
    b.put(em.inputs['Color'], oi.outputs['Color'])
    b.put(em.inputs['Strength'], b.attr('fx_e'))
    tr = b.node('ShaderNodeBsdfTransparent')
    b.link(b.mixsh(fac, tr.outputs[0], em.outputs[0]), b.out.inputs['Surface'])
    b.m['emit_node'] = em.name
    c['sh_lat'] = b.m
    return b.m


def shield_ripple_mat(P):
    """Hit overlay: impact spot + expanding rings measured along the dome surface from fx_hit
    (object-space unit vector), age fx_age seconds, radius fx_R."""
    c = _c(P)
    if 'sh_rip' in c:
        return c['sh_rip']
    b = _NT('FxShieldRipple')
    oi = b.node('ShaderNodeObjectInfo')
    tc = b.node('ShaderNodeTexCoord')
    n = b.vmath('NORMALIZE', tc.outputs['Object'])
    cs = b.vmath('DOT_PRODUCT', n, b.attr('fx_hit', 'Vector'), out=1)
    cs = b.math('MAXIMUM', b.math('MINIMUM', cs, 1.0), -1.0)
    dist = b.math('MULTIPLY', b.math('ARCCOSINE', cs), b.attr('fx_R'))
    age = b.attr('fx_age')
    front = b.math('MULTIPLY', age, b.attr('fx_v'))
    w = b.attr('fx_w')

    def gauss(x, width):
        q = b.math('DIVIDE', x, width)
        return b.math('EXPONENT', b.math('MULTIPLY', b.math('MULTIPLY', q, q), -1.0))
    ring1 = gauss(b.math('SUBTRACT', dist, front), w)
    ring2 = b.math('MULTIPLY', gauss(b.math('SUBTRACT', dist, b.math('MULTIPLY', front, 0.62)), b.math('MULTIPLY', w, 0.8)), 0.6)
    ring3 = b.math('MULTIPLY', gauss(b.math('SUBTRACT', dist, b.math('MULTIPLY', front, 0.3)), b.math('MULTIPLY', w, 0.6)), 0.35)
    life = b.math('SUBTRACT', 1.0, b.math('DIVIDE', age, b.attr('fx_life')), clamp=True)
    rings = b.math('MULTIPLY', b.math('ADD', b.math('ADD', ring1, ring2), ring3), b.math('MULTIPLY', life, life))
    # rings only light up once they have left the impact point (no soft blob at the centre)
    rings = b.math('MULTIPLY', rings, b.math('DIVIDE', dist, b.math('MULTIPLY', b.attr('fx_R'), 0.14), clamp=True))
    spot = b.math('MULTIPLY', gauss(dist, b.attr('fx_sr')), b.math('EXPONENT', b.math('MULTIPLY', age, -5.0)))
    local = b.math('MULTIPLY', gauss(dist, b.math('MULTIPLY', b.attr('fx_R'), 0.28)),
                   b.math('MULTIPLY', b.math('EXPONENT', b.math('MULTIPLY', age, -2.2)), b.attr('fx_local')))
    v = b.math('ADD', b.math('ADD', rings, b.math('MULTIPLY', spot, b.attr('fx_spot'))), local)
    fac = b.math('MULTIPLY', v, oi.outputs['Alpha'], clamp=True)
    col = b.mixc(b.math('MULTIPLY', spot, 0.8, clamp=True), oi.outputs['Color'], HOT_WHITE)
    em = b.node('ShaderNodeEmission')
    b.put(em.inputs['Color'], col)
    b.put(em.inputs['Strength'], b.attr('fx_e'))
    tr = b.node('ShaderNodeBsdfTransparent')
    b.link(b.mixsh(fac, tr.outputs[0], em.outputs[0]), b.out.inputs['Surface'])
    b.m['emit_node'] = em.name
    c['sh_rip'] = b.m
    return b.m


def _dual_mesh(name, bm_src):
    """Hex/pent dual of a triangulated sphere (Arcadian honeycomb lattice)."""
    bm_src.faces.ensure_lookup_table()
    cent = {f.index: f.calc_center_median() for f in bm_src.faces}
    bm = bmesh.new()
    vmap = {i: bm.verts.new(c) for i, c in cent.items()}
    for v in bm_src.verts:
        fs = list(v.link_faces)
        nrm = v.co.normalized()
        a = (fs[0].calc_center_median() - v.co)
        a = (a - nrm * a.dot(nrm)).normalized()
        bb = nrm.cross(a)
        fs.sort(key=lambda f: math.atan2((cent[f.index] - v.co).dot(bb), (cent[f.index] - v.co).dot(a)))
        try:
            bm.faces.new([vmap[f.index] for f in fs])
        except ValueError:
            pass
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def shield_dome(P, center, radius, t0, t1, color=None, hits=()):
    """Shield bubble that never shatters. Terran: translucent blue triangles; Arcadian (gold
    colour): dark smoked-gold glass with a crisp gold honeycomb. Each hit: bright spot, rings
    racing across the surface, the lattice lighting up locally, deflected sparks."""
    color = color or K.COL['shield_blue']
    arc = _is_gold(color)
    center = K.V(center)
    R = radius
    # shell: icosphere, per-face random attribute for the triangle tint
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=R)
    lat_me = _dual_mesh('ShieldLattice', bm) if arc else None
    me = bpy.data.meshes.new('Shield')
    bm.to_mesh(me)
    bm.free()
    if not arc:
        lat_me = me.copy()
        lat_me.name = 'ShieldLattice'
    at = me.attributes.new('fx_face', 'FLOAT', 'FACE')
    for i in range(len(me.polygons)):
        at.data[i].value = P.rnd.random() ** 2
    me.materials.append(shield_shell_mat(P))
    shell = _fxobj(K.link(bpy.data.objects.new('Shield', me)))
    shell.location = center
    shell.color = (*color, 1.0)
    shell['fx_e'] = 1.4 if not arc else 0.8
    shell['fx_dark'] = 0.0 if not arc else 0.75
    shell['fx_facek'] = 0.22 if not arc else 0.04
    shell['fx_R'] = float(R)
    lat_me.materials.append(shield_lattice_mat(P))
    lat = _fxobj(K.link(bpy.data.objects.new('ShieldLattice', lat_me)))
    lat.parent = shell
    lat.scale = (1.002,) * 3
    wf = lat.modifiers.new('Wire', 'WIREFRAME')
    wf.thickness = R * (0.006 if arc else 0.008)
    wf.use_even_offset = False
    lat.color = (*color, 0.35 if not arc else 0.9)
    lat['fx_e'] = 0.9 if not arc else 2.4
    f0, f1 = P.T(t0), P.T(t1)
    for o in (shell, lat):
        o['fx_up'] = 0.0
        o['fx_t'] = 0.0
        kprop(o, 'fx_up', f0, 0.0)
        kprop(o, 'fx_up', f0 + 0.35 * P.fps, 1.0)
        kprop(o, 'fx_t', f0, 0.0)
        kprop(o, 'fx_t', f1, 0.25 * (f1 - f0) / P.fps)
        kcol(o, f1 - 0.25 * P.fps, a=o.color[3])
        kcol(o, f1, a=0.0)
        K.show_between(o, f0, f1)
    for t, p in hits:
        shield_hit(P, shell, lat, center, R, t, K.V(p), color, arc, t1)
    return shell


def shield_hit(P, shell, lat, center, R, t, p, color, arc, t_end):
    n = (p - center)
    n = n.normalized() if n.length > 1e-4 else UP
    surf = center + n * R
    life = 1.1
    f0 = P.T(t)
    f1 = min(P.T(t + life), P.T(t_end))
    rip = shield_ripple_mat(P)
    if arc:   # Arcadian: crisper, thinner rings, the honeycomb carries the light
        layers = ((shell, 1.004, 1.5, 0.8, 0.6, 0.04, 0.045), (lat, 1.006, 3.2, 1.0, 0.8, 0.45, 0.06))
    else:
        layers = ((shell, 1.004, 2.2, 0.85, 0.7, 0.06, 0.06), (lat, 1.006, 3.0, 1.0, 0.8, 0.5, 0.06))
    for src, scale, e, a, spot, local, wk in layers:
        o = src.copy()
        K.link(o)
        o.animation_data_clear()
        o.parent = src
        o.matrix_parent_inverse.identity()
        o.location = (0, 0, 0)
        o.scale = (scale / (src.scale.x or 1),) * 3
        o.name = 'ShieldRipple'
        for s in o.material_slots:
            s.link = 'OBJECT'
            s.material = rip
        o.color = (*color, a)
        o['fx_hit'] = tuple(n)
        o['fx_R'] = float(R)
        o['fx_v'] = R * 2.4
        o['fx_w'] = R * wk
        o['fx_life'] = life
        o['fx_sr'] = R * 0.022
        o['fx_e'] = e
        o['fx_spot'] = spot
        o['fx_local'] = local
        o['fx_age'] = 0.0
        o.keyframe_insert('["fx_age"]', frame=f0)
        o['fx_age'] = life
        o.keyframe_insert('["fx_age"]', frame=f0 + life * P.fps)
        K.set_interp(o, 'LINEAR')
        K.show_between(o, int(f0), int(f1) + 1)
    # surface flash + sparks glancing off along the surface
    flash(P, surf, t, 0.12 + R * 0.012, color, frames=(1, 1, 3), e=3.0, hot=0.7, name='ShieldFlash')
    sparks(P, surf, t, n=10, speed=8.0, color=color, axis=n, spread=75, life=(0.15, 0.45), width=0.02,
           gravity=4.0)
    P.light(surf + n * 0.6, t, color, energy=900, dur=0.15, radius=0.25)


def shield_push(P, shell, actor, t0, t1, release=0.6, reach=None, stretch=None):
    """A unit pushing out through a shield stretches it instead of breaking it: where the unit
    meets the membrane, the surface is pulled outward with it (Warp modifier), until the
    stretch reaches `stretch` metres (default ~0.7 x unit size) or time t1; then the membrane
    lets go behind the unit and snaps back with a damped wobble. shell: the object
    shield_dome() returned; actor: an Actor (or a callable t -> Vector). Scan window t0..t1."""
    pos = actor.pos_at if hasattr(actor, 'pos_at') else actor
    size = getattr(actor, 'size', 4.0)
    up_off = Vector((0, 0, size * 0.15))
    c = shell.matrix_world.translation.copy()
    R = shell.get('fx_R') or (max(shell.dimensions) / 2) or 5.0
    stretch = stretch or size * 0.7
    f0, f1 = int(P.T(t0)), int(P.T(t1))
    track = [(fr, pos((fr - 1) / P.fps) + up_off) for fr in range(f0, f1 + 1)]
    hit = next((k for k, (fr, p) in enumerate(track) if (p - c).length >= R - size * 0.35), None)
    if hit is None:
        return None
    n = (track[hit][1] - c).normalized()
    contact = c + n * R
    src = K.empty('ShieldPushFrom', contact)
    tgt = K.empty('ShieldPushTo', contact)
    fr_hit = track[hit][0]
    fr_rel = f1
    for fr, p in track[hit:]:
        out = (p - c).dot(n) - R + size * 0.35       # how far the unit's nose is past the surface
        lat = (p - c) - n * (p - c).dot(n)
        lat = lat - (contact - c - n * (contact - c).dot(n))
        tgt.location = contact + n * max(0.0, min(out, stretch)) + lat * 0.8
        tgt.keyframe_insert('location', frame=fr)
        if out >= stretch:
            fr_rel = fr
            break
    mods = []
    for o in [shell] + list(shell.children_recursive):
        if o.type != 'MESH':
            continue
        w = o.modifiers.new('Push', 'WARP')
        w.object_from = src
        w.object_to = tgt
        w.falloff_radius = reach or size * 0.75
        w.falloff_type = 'SMOOTH'
        w.use_volume_preserve = False
        while o.modifiers[0] != w:
            with bpy.context.temp_override(object=o):
                bpy.ops.object.modifier_move_up(modifier=w.name)
        mods.append(w)
    for w in mods:   # on at contact, hold while it stretches, then let go with a damped wobble
        w.strength = 0.0
        w.keyframe_insert('strength', frame=fr_hit - 1)
        w.strength = 1.0
        w.keyframe_insert('strength', frame=fr_hit + 1)
        w.keyframe_insert('strength', frame=fr_rel)
        for i, v in enumerate((-0.3, 0.15, -0.06, 0.0)):
            w.strength = v
            w.keyframe_insert('strength', frame=fr_rel + (i + 1) * release * P.fps / 4)
    # a ripple ring where the membrane lets go
    lat_o = next((ch for ch in shell.children if ch.name.startswith('ShieldLattice')), None)
    if lat_o is not None:
        col = tuple(shell.color)[:3]
        shield_hit(P, shell, lat_o, c, R, (fr_rel - 1) / P.fps, contact, col, _is_gold(col), P.seconds)
    return tgt
