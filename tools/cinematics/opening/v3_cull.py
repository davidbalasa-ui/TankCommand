"""Shared pieces for the v3 ending (scenes 15 and 16): the two fleets near the end of the fight, the Shard's
violet columns rising from Vesper's cloud deck, ships broken in two by them, wrecks, and the planet's
violet glow for the final image.

Everything is keyed on the calling scene's own clock.
"""
import math
import random

import bpy
from mathutils import Vector, Matrix, Euler

import v3base as V
from v3base import key_loc, key_rot, key_scale, show
import space as SP
import planet as PL
import shard_fx as SF
import arcadian_fleet as AF

BLUE = (0.35, 0.7, 1.0)
GOLD = (1.0, 0.6, 0.18)
VIO = (0.55, 0.18, 1.0)
CLOUD_R = PL.R + PL.CLOUD_H
PC = SP.PLANET_C

# the battle near its end: both lines have closed in to a few hundred units.
# key: (kind, position, scale)
TERRAN = {
    'bship': ('bship', Vector((-120, -20, 10)), 1.0),
    'frig1': ('frigate', Vector((-70, -78, -2)), 1.15),
    'frig2': ('frigate', Vector((-165, 70, 28)), 1.15),
    'missile': ('missile', Vector((-185, -105, -12)), 1.0),
    'corv0': ('corvette', Vector((-55, 25, 32)), 1.6),
    'corv1': ('corvette', Vector((-75, 95, 12)), 1.6),
    'corv2': ('corvette', Vector((-110, -135, 38)), 1.6),
    'corv3': ('corvette', Vector((-150, 140, -4)), 1.6),
    'corv4': ('corvette', Vector((-40, -30, -22)), 1.6),
    'corv5': ('corvette', Vector((-205, 15, 45)), 1.6),
}
ARCAD = {
    'crescent': ('crescent', Vector((250, 45, 55)), 2.0),
    'shell': ('shell', Vector((175, -85, 8)), 1.2),
    'lens': ('lens', Vector((270, 165, 25)), 1.4),
    'acorv0': ('acorv', Vector((115, 20, 42)), 1.35),
    'acorv1': ('acorv', Vector((125, -35, -12)), 1.35),
    'acorv2': ('acorv', Vector((150, 105, 18)), 1.35),
    'acorv3': ('acorv', Vector((100, 75, -16)), 1.35),
    'acorv4': ('acorv', Vector((160, -150, 30)), 1.35),
    'acorv5': ('acorv', Vector((95, -95, 26)), 1.35),
    'acorv6': ('acorv', Vector((215, -25, 85)), 1.35),
}


def cloud_z(x, y):
    """Height of the cloud tops under (x, y)."""
    d2 = x * x + y * y
    return PC.z + math.sqrt(max(CLOUD_R * CLOUD_R - d2, 0.0))


# ================================================================== fleets
def build_fleets(nf, drift=18.0, which=None):
    """Both fleets at their end-of-fight positions, slowly closing. Returns {key: object}."""
    ob = {}
    proto = {}
    for k, (kind, p, s) in list(TERRAN.items()) + list(ARCAD.items()):
        if which is not None and k not in which:
            continue
        terran = k in TERRAN
        if kind in proto:
            o = V.copy_tree(proto[kind], f'Cull_{k}')
        elif terran:
            o, _ = V.terran_ship(kind)
            proto[kind] = o
        else:
            with AF.gold_palette():
                if kind == 'crescent':
                    o, _ = AF.crescent_mothership_v2()
                elif kind == 'shell':
                    o, _ = AF.shell_mothership_v2()
                elif kind == 'lens':
                    o, _ = AF.lens_mothership_v2()
                else:
                    o, _ = AF.arcadian_corvette()
            proto[kind] = o
        o.scale = (s,) * 3
        d = Vector((1, 0, 0)) if terran else Vector((-1, 0, 0))
        key_loc(o, [(1, p), (nf, p + d * drift)], 'LINEAR')
        key_rot(o, [(1, (0, 0, 0 if terran else 180)), (nf, (0, 0, 0 if terran else 180))])
        ob[k] = o
    bpy.context.view_layer.update()
    return ob


def add_engines(ob, nf, thr=0.8, ln=0.7):
    for k, o in ob.items():
        r = None
        if k in TERRAN:              # tighter plumes: the default halo reads as a white balloon this close
            dims = Vector(o.dimensions) / o.scale.x
            r = min(dims.y, dims.z) * 0.07
        V.engines(o, f'CEng{k}', BLUE if k in TERRAN else GOLD, thr_keys=[(1, thr), (nf, thr)],
                  len_keys=[(1, ln), (nf, ln)], r=r)


def stingrays(n, centre, spread, nf, seed=3, d=Vector((-1, 0, 0)), speed=60.0):
    """A loose flock of stingray fighters crossing the field (drawn FIGHTER_K x)."""
    rnd = random.Random(seed)
    with AF.gold_palette():
        proto, _ = AF.stingray_fighter()
    out = []
    for i in range(n):
        s = proto if i == 0 else V.copy_tree(proto, f'CSting{i}')
        s.scale = (SP.FIGHTER_K * 1.3,) * 3
        p = Vector(centre) + Vector((rnd.uniform(-1, 1) * spread.x, rnd.uniform(-1, 1) * spread.y,
                                     rnd.uniform(-1, 1) * spread.z))
        key_loc(s, [(1, p), (nf, p + d * speed * nf / 24.0 + Vector((0, rnd.uniform(-10, 10), rnd.uniform(-6, 6))))],
                'LINEAR')
        key_rot(s, [(1, (rnd.uniform(-25, 25), 0, 180 + rnd.uniform(-8, 8))),
                    (nf, (rnd.uniform(-25, 25), 0, 180 + rnd.uniform(-8, 8)))])
        out.append(s)
    return out


# ================================================================== the Shard's column
def column(x, y, f_hit, z_ship, r=6.0, name=None, seed=0, hold=14, top=1400.0, pre=22):
    """A violet column bursting up out of the clouds under (x, y): the deck glows first (pre frames),
    then the column rips up through height z_ship at f_hit, holds, and thins out. Returns the root."""
    name = name or SP._uid('Col')
    zb = cloud_z(x, y) - 25.0
    base = Vector((x, y, zb))
    L = top - zb
    root = bpy.data.objects.new(name, None)
    SP.link(root)
    root.location = base
    for o in SF.beam(Vector((0, 0, 0)), Vector((0, 0, L)), r=r, seed=seed, name=name + 'B'):
        if 'Strand' in o.name or 'Shock' in o.name or o.name.endswith('Sleeve'):
            bpy.data.objects.remove(o)          # the helix strands read as a cheap barber pole
            continue
        if o.name.endswith('Core'):
            o.scale = (o.scale.x * 0.45, o.scale.y * 0.45, o.scale.z)
        o.parent = root
    frac = max(0.05, (z_ship - zb) / L)
    f0 = f_hit - 3
    key_scale(root, [(f0, (0.35, 0.35, 0.01)), (f_hit, (0.7, 0.7, frac * 1.08)), (f_hit + 2, (1.25, 1.25, frac * 2.2)),
                     (f_hit + 6, (1.0, 1.0, 1.0)), (f_hit + hold, (1.0, 1.0, 1.0)),
                     (f_hit + hold + 8, (0.25, 0.25, 1.0)), (f_hit + hold + 12, (0.01, 0.01, 1.0))], 'LINEAR')
    show(root, f0, f_hit + hold + 12)
    # violet lightning crawling round the column while it holds
    rnd = random.Random(seed + 77)
    pairs = []
    for j in range(4):
        a = rnd.uniform(0, 6.283)
        z0 = z_ship + rnd.uniform(-60, 10)
        z1 = z0 + rnd.uniform(25, 55)
        rr = r * rnd.uniform(1.3, 2.4)
        a1 = a + rnd.uniform(-0.8, 0.8)
        pairs.append((Vector((x + rr * math.cos(a), y + rr * math.sin(a), z0)),
                      Vector((x + rr * math.cos(a1), y + rr * math.sin(a1), z1))))
    SP.flicker_lightning(pairs, seed + 5, f_hit + 1, f_hit + hold + 4, every=1, width=0.035 * r, name=name + 'Lt',
                         zone_col=(0.6, 0.3, 1.0), strength=7.0)
    # the deck under it glows first, flares as the column breaks out, and stays a smouldering scar
    nrm = (base - PC).normalized()
    q = nrm.to_track_quat('Z', 'Y')
    g = V.C.uv_sphere(name + 'Deck', 1.0, seg=(32, 12), mat=deck_mat())
    g.rotation_mode = 'QUATERNION'
    g.rotation_quaternion = q
    g.location = base + nrm * 22
    g.visible_shadow = False
    R = r * 7
    key_scale(g, [(f_hit - pre, (R * 0.2, R * 0.2, 1)), (f_hit - 4, (R * 1.4, R * 1.4, 4)), (f_hit, (R * 2.4, R * 2.4, 8)),
                  (f_hit + 3, (R * 3.2, R * 3.2, 12)), (f_hit + hold + 12, (R * 1.6, R * 1.6, 5))], 'BEZIER')
    show(g, f_hit - pre, 100000)
    # violet light on everything near it
    Lt = bpy.data.objects.new(name + 'L', bpy.data.lights.new(name + 'L', 'POINT'))
    SP.link(Lt)
    Lt.location = Vector((x, y, z_ship - 25))
    Lt.data.color = (0.6, 0.3, 1.0)
    Lt.data.shadow_soft_size = 30
    for f, e in [(1, 0), (f_hit - pre, 0), (f_hit - 1, 1.2e6), (f_hit + 1, 6e6), (f_hit + 4, 3e6), (f_hit + hold, 2.5e6), (f_hit + hold + 10, 0)]:
        Lt.data.energy = e
        Lt.data.keyframe_insert('energy', frame=max(1, f))
    SP.lin(Lt.data)
    return root


def deck_mat():
    """Glow on the cloud deck: soft radial violet falloff with a churning ring structure (object space of a
    flattened unit sphere), additive."""
    m = bpy.data.materials.get('CullDeckM')
    if m:
        return m
    m, n = V.BP._new_mat('CullDeckM')
    tc = n.node('ShaderNodeTexCoord')
    sep = n.node('ShaderNodeSeparateXYZ')
    n.set(sep.inputs[0], tc.outputs['Object'])
    rr = n.math('SQRT', n.math('ADD', n.math('MULTIPLY', sep.outputs[0], sep.outputs[0]),
                               n.math('MULTIPLY', sep.outputs[1], sep.outputs[1])))
    fall = n.math('POWER', n.maprange(rr, 0.0, 1.0, 1.0, 0.0), 2.5)
    nz = n.node('ShaderNodeTexNoise', Scale=3.0, Detail=6.0, Roughness=0.6)
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    k = n.math('MULTIPLY', fall, n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.4, 1.6))
    em = n.node('ShaderNodeEmission', Color=(0.45, 0.12, 1.0, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', k, 6.0))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


# ================================================================== breaking a ship
def _curves(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        return [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags
                for fc in bag.fcurves]


def _hide_from(ob, f):
    """Hidden from f on, for good: later visibility keys (lightning thruster flicker etc.) are dropped."""
    for o in [ob] + list(ob.children_recursive):
        was = False
        for fc in _curves(o):
            if fc.data_path == 'hide_render':
                was = fc.evaluate(f - 1) > 0.5
                for i in reversed(range(len(fc.keyframe_points))):
                    if fc.keyframe_points[i].co.x >= f - 1:
                        fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
                fc.update()
        o.hide_render = was
        o.keyframe_insert('hide_render', frame=max(1, f - 1))
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=f)
        SP._interp_where(o, 'hide_render', 'CONSTANT')


def _fire_mat():
    return bpy.data.materials.get('CullBurnM') or V.soft_glow('CullBurnM', (1.0, 0.32, 0.05), 2.5, 1.8)


def break_ship(ob, f, terran, nf, seed=0, sep=None, spin=None, burn=True):
    """At frame f the hull snaps in two where the column went through: the halves fly apart and tumble
    with burning ends; the original (and its turrets, engines, shields) is hidden from f."""
    rnd = random.Random(seed)
    sc = bpy.context.scene
    sc.frame_set(f)
    mw = ob.matrix_world.copy()
    sc.frame_set(f + 6)
    vel = (ob.matrix_world.translation - mw.translation) / 6.0
    sc.frame_set(f)
    xs = [v.co.x for v in ob.data.vertices]
    cut = (min(xs) + max(xs)) / 2 + rnd.uniform(-0.12, 0.12) * (max(xs) - min(xs))
    halves = SP.split_mesh(ob, lambda c: 0 if c.x < cut else 1, names=[ob.name + 'Aft', ob.name + 'Fore'])
    size = max(ob.dimensions)
    sep = sep if sep is not None else 0.06 * size + 1.5
    spin = spin if spin is not None else 40.0
    _hide_from(ob, f)
    loc0, rot0, sca = mw.decompose()
    e0 = rot0.to_euler()
    ax = rot0 @ Vector((1, 0, 0))
    for i, h in enumerate(halves):
        h.matrix_world = Matrix.Identity(4)
        h.rotation_mode = 'XYZ'
        sgn = -1 if i == 0 else 1
        # pivot about the cut: halves are meshes in ship-local space, so offset the object
        cutw = mw @ Vector((cut, 0, 0))
        push = ax * sgn * sep + Vector((0, 0, rnd.uniform(0.5, 1.5) * sep * 0.6))
        frames = nf - f
        h.scale = sca
        for ff, kpos, kr in ((f, 0.0, 0.0), (f + 3, 0.25, 0.08), (nf + 24, 1.0, 1.0)):
            t = (ff - f) / 24.0
            h.location = loc0 + vel * (ff - f) + push * (kpos * (1 + t * 1.5))
            h.rotation_euler = Euler((e0.x + math.radians(rnd.uniform(-1, 1) * spin * kr),
                                      e0.y + math.radians(sgn * spin * kr * rnd.uniform(0.6, 1.2)),
                                      e0.z + math.radians(rnd.uniform(-1, 1) * spin * 0.5 * kr)), 'XYZ')
            h.keyframe_insert('location', frame=ff)
            h.keyframe_insert('rotation_euler', frame=ff)
        V.C.set_interp(h, 'BEZIER')
        show(h, f, 100000, tree=False)
        if burn:
            # burning, violet-lit broken end
            for j in range(3):
                b = V.C.uv_sphere(f'{h.name}Burn{j}', 1.0, seg=(16, 8), mat=_fire_mat())
                b.parent = h
                b.location = (cut + rnd.uniform(-0.04, 0.04) * size, rnd.uniform(-0.15, 0.15) * size,
                              rnd.uniform(-0.1, 0.1) * size)
                s0 = size * rnd.uniform(0.022, 0.04) / max(sca.x, 1e-3)
                key_scale(b, [(f, s0 * 2.0), (f + 8, s0), (f + 60, s0 * 0.6), (nf + 24, s0 * 0.4)])
                b.visible_shadow = False
                show(b, f, 100000)
        h.visible_shadow = True
    return halves


def kill(ob, f_hit, terran, nf, key='', seed=0, beam_r=None, col_dx=0.0, shake=None):
    """The whole death: column up through the ship at f_hit, a few frames of it skewered and lit violet,
    then it snaps in two in a faction-coloured blast with debris."""
    sc = bpy.context.scene
    sc.frame_set(f_hit)
    p = ob.matrix_world.translation.copy()
    size = max(ob.dimensions)
    r = beam_r or max(3.5, min(10.0, size * 0.12))
    column(p.x + col_dx, p.y, f_hit, p.z, r=r, name=f'Col_{key}', seed=seed)
    fb = f_hit + 4
    halves = break_ship(ob, fb, terran, nf, seed=seed)
    if terran:
        SP.boom(p, fb, max(4.0, size * 0.16), hot=(0.3, 0.6, 1.0), cool=(0.02, 0.05, 0.3), life=1.1, light=4e6)
    else:
        SP.boom(p, fb, max(4.0, size * 0.11), hot=(1.0, 0.55, 0.12), cool=(0.35, 0.06, 0.01), life=1.1, light=4e6)
    SP.violet_boom(p + Vector((0, 0, size * 0.1)), f_hit + 1, max(3.0, size * 0.09), life=0.5)
    rnd = random.Random(seed)
    for j in range(2 if size > 40 else 1):
        q = p + Vector((rnd.uniform(-0.35, 0.35) * size, rnd.uniform(-0.2, 0.2) * size, rnd.uniform(-0.1, 0.1) * size))
        SP.boom(q, fb + 4 + 4 * j, size * 0.08, hot=(1.0, 0.5, 0.1), life=0.9, seed=seed + j)
    SP.shards(p, fb, 28, BLUE if terran else (1.0, 0.75, 0.3), 0.6 + size * 0.02, 18 + size * 0.5,
              seed=seed * 7 + 1, life=1.6, kind='tri' if terran else 'hex')
    return halves


# ================================================================== the planet's violet glow
def planet_glow(shard_dir, keys, radius=700.0):
    """A violet bloom on Vesper round the Shard (unit direction from the planet's centre), veined, plus a
    violet haze in the atmosphere. keys: [(frame, strength 0..1)]."""
    shard_dir = Vector(shard_dir).normalized()
    m, n = V.BP._new_mat('ShardGlowM')
    tc = n.node('ShaderNodeTexCoord')
    d = n.node('ShaderNodeVectorMath', operation='DISTANCE')
    n.set(d.inputs[0], tc.outputs['Object'])
    d.inputs[1].default_value = tuple(shard_dir * (CLOUD_R + 3))
    dist = d.outputs['Value']
    core = n.math('POWER', n.maprange(dist, 0.0, radius, 1.0, 0.0), 2.2)
    wide = n.math('POWER', n.maprange(dist, 0.0, radius * 1.4, 1.0, 0.0), 2.0)
    nz = n.node('ShaderNodeTexNoise', Scale=0.004, Detail=8.0, Roughness=0.62)
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    vein = n.math('POWER', n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', nz.outputs['Fac'], 0.5)), 0.0, 0.05, 1.0, 0.0), 1.5)
    hot = n.math('POWER', n.maprange(dist, 0.0, radius * 0.25, 1.0, 0.0), 2.0)
    k = n.math('ADD', n.math('ADD', n.math('MULTIPLY', core, 3.0), n.math('MULTIPLY', hot, 25.0)),
               n.math('ADD', n.math('MULTIPLY', n.math('MULTIPLY', vein, wide), 4.0), n.math('MULTIPLY', wide, 0.3)))
    lvl = SP.value_node(m, 'lvl', 0.0)
    em = n.node('ShaderNodeEmission', Color=(0.5, 0.2, 1.0, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', k, lvl.outputs[0]))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], add.outputs[0])
    sk = PL._sphere('ShardGlowSkin', CLOUD_R + 3, (384, 192))
    sk.data.materials.append(m)
    sk.location = PC
    sk.visible_shadow = False
    SP.key_node(m, 'lvl', keys, 'BEZIER')
    # violet haze in the air above it: a big soft glow hugging the limb
    m2, n2 = V.BP._new_mat('ShardHaze2M')
    tc2 = n2.node('ShaderNodeTexCoord')
    d2 = n2.node('ShaderNodeVectorMath', operation='DISTANCE')
    n2.set(d2.inputs[0], tc2.outputs['Object'])
    d2.inputs[1].default_value = tuple(shard_dir * (PL.R + 120))
    k2 = n2.math('POWER', n2.maprange(d2.outputs['Value'], 0.0, radius * 2.4, 1.0, 0.0), 2.0)
    lw = n2.node('ShaderNodeLayerWeight', Blend=0.3)
    rim = n2.math('POWER', lw.outputs['Facing'], 2.0)
    lvl2 = SP.value_node(m2, 'lvl', 0.0)
    em2 = n2.node('ShaderNodeEmission', Color=(0.55, 0.25, 1.0, 1))
    n2.set(em2.inputs['Strength'], n2.math('MULTIPLY', n2.math('MULTIPLY', n2.math('ADD', rim, 0.15), k2),
                                            n2.math('MULTIPLY', lvl2.outputs[0], 2.0)))
    tr2 = n2.node('ShaderNodeBsdfTransparent')
    add2 = n2.node('ShaderNodeAddShader')
    n2.set(add2.inputs[0], tr2.outputs[0])
    n2.set(add2.inputs[1], em2.outputs[0])
    out2 = n2.node('ShaderNodeOutputMaterial')
    n2.set(out2.inputs['Surface'], add2.outputs[0])
    hz = PL._sphere('ShardHaze', PL.R + PL.ATMO_H + 60, (256, 128))
    hz.data.materials.append(m2)
    hz.location = PC
    hz.visible_shadow = False
    SP.key_node(m2, 'lvl', keys, 'BEZIER')
    # bloom over the Shard itself
    bl = V.C.uv_sphere('ShardBloom', 1.0, seg=(32, 16), mat=V.soft_glow('ShardBloomM', (0.6, 0.3, 1.0), 2.0, 2.2))
    bl.location = PC + shard_dir * (CLOUD_R + 10)
    bl.visible_shadow = False
    key_scale(bl, [(f, max(1.0, radius * 0.35 * v)) for f, v in keys])
    return sk, hz
