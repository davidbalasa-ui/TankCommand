"""Landing Pad (Terran logistics structure): the pad drops out of the sky on blue-white retro
thrusters folded up like a crate, slams down in a ring of dust, swings its side decks and ramp
open and powers up its deck lights. Then the deliveries start, strictly one at a time: a
windowless lifter drops a Lancer on the pad, the Lancer rolls down the ramp and clears, the next
lifter is already lowering an Outrider, then a Hauler. Ordered, busy, the heart of the base.

Everything that moves on the pad (side-deck flaps, ramp, thrusters, delivery lifters) is built in
this script: the pad model has no packed pose."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from promo_kit import (COL, Promo, _fcurves, cube, emit_mat, empty, key_hide, link,  # noqa: E402
                       pbr_mat, set_interp, show_between, sphere)

P = Promo('terran_landing_pad', seconds=6.0)
P.env('highland', sun=(46, 0, -55), clear=[(0, 0, 16), (16, 0, 14), (22, 6, 10)], props=30)
P.flatten(0, 0, 13)
P.flatten(16, 2, 13)

DECK = 0.9      # landing circle height (pad landed at z=0)
HINGE_NS = 3.3  # side decks hinge at y = +-3.3
HINGE_E = 3.6   # ramp hinge at x = 3.6

# ------------------------------------------------------------------------------ the pad
pad = P.load('terran_landing_pad', at=(0, 0), heading=0)
bpy.context.view_layer.update()
hull = pad.parts['Hull']
root = pad.root


def split_hull():
    """Cut the hull into core / north deck / south deck / ramp along the hinge lines."""
    bm = bmesh.new()
    bm.from_mesh(hull.data)
    bm.transform(hull.matrix_world)
    for co, no in [((0, HINGE_NS, 0), (0, 1, 0)), ((0, -HINGE_NS, 0), (0, 1, 0)), ((HINGE_E, 0, 0), (1, 0, 0))]:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-4)

    def region(c):
        if c.y > HINGE_NS:
            return 'north'
        if c.y < -HINGE_NS:
            return 'south'
        if c.x > HINGE_E:
            return 'ramp'
        return 'core'
    out = {}
    for nm in ('core', 'north', 'south', 'ramp'):
        b2 = bm.copy()
        kill = [f for f in b2.faces if region(f.calc_center_median()) != nm]
        bmesh.ops.delete(b2, geom=kill, context='FACES')
        me = bpy.data.meshes.new('Pad_' + nm)
        b2.to_mesh(me)
        b2.free()
        for m in hull.data.materials:
            me.materials.append(m)
        o = link(bpy.data.objects.new('Pad_' + nm, me))
        out[nm] = o
    bm.free()
    return out


pieces = split_hull()
hull.hide_render = True
hull.hide_viewport = True


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    child.matrix_world = mw


parent_keep(pieces['core'], root)
pivots = {}
for nm, loc in [('north', (0, HINGE_NS, 0.39)), ('south', (0, -HINGE_NS, 0.39)), ('ramp', (HINGE_E, 0, 0.39))]:
    pv = empty('Hinge_' + nm)
    pv.parent = root
    pv.location = loc
    pv.rotation_mode = 'XYZ'
    pivots[nm] = pv
    parent_keep(pieces[nm], pv)
# the scanner mast sits on the north deck: ride with it
scanner = pad.parts['ScannerPivot']
parent_keep(scanner, pivots['north'])


def hinge(pv, axis, folded_deg, t0, t1, overshoot=6):
    """Folded up until t0, swings flat by t1 with a little bounce."""
    pv.rotation_euler[axis] = math.radians(folded_deg)
    pv.keyframe_insert('rotation_euler', index=axis, frame=0)
    pv.keyframe_insert('rotation_euler', index=axis, frame=P.T(t0))
    pv.rotation_euler[axis] = math.radians(-overshoot * (1 if folded_deg > 0 else -1))
    pv.keyframe_insert('rotation_euler', index=axis, frame=P.T(t1))
    pv.rotation_euler[axis] = 0
    pv.keyframe_insert('rotation_euler', index=axis, frame=P.T(t1 + 0.18))
    set_interp(pv, 'BEZIER')


T_LAND = 1.25
hinge(pivots['north'], 0, 92, T_LAND + 0.15, T_LAND + 0.75)
hinge(pivots['south'], 0, -92, T_LAND + 0.25, T_LAND + 0.85)
hinge(pivots['ramp'], 1, -95, T_LAND + 0.55, T_LAND + 1.1, overshoot=4)

# descent: falls fast, retro-burns hard, settles; slight sway while braking
desc = [(0.0, (-3.0, 2.0, 34.0)), (0.55, (-0.8, 0.5, 11.0)), (0.95, (0, 0, 2.2)),
        (T_LAND, (0, 0, 0.0))]
for t, p in desc:
    root.location = p
    root.keyframe_insert('location', frame=P.T(t))
root.keyframe_insert('location', frame=P.T(T_LAND + 0.06))
root.location = (0, 0, -0.12)          # suspension squash on impact
root.keyframe_insert('location', frame=P.T(T_LAND + 0.03))
root.location = (0, 0, 0)
root.keyframe_insert('location', frame=P.T(T_LAND + 0.2))
for t, rx, ry in [(0.0, 6, -5), (0.55, -4, 3), (0.95, 1.5, -1), (T_LAND, 0, 0)]:
    root.rotation_euler = (math.radians(rx), math.radians(ry), 0)
    root.keyframe_insert('rotation_euler', frame=P.T(t))
set_interp(root, 'BEZIER')

# deck lights: dim in flight, flare on when the decks open, then a steady glow
padmat = bpy.data.materials['TerranLandingPadMat']
bsdf = padmat.node_tree.nodes['Principled BSDF']
es = bsdf.inputs['Emission Strength']
for t, v in [(0, 0.4), (T_LAND + 0.7, 0.4), (T_LAND + 0.95, 14), (T_LAND + 1.4, 5), (6, 5)]:
    es.default_value = v
    es.keyframe_insert('default_value', frame=P.T(t))

# landing-circle power ring (neon blue) lighting up after the ramp drops
ring_m = emit_mat('PadRing', COL['terran_neon'], 0.0)
bpy.ops.mesh.primitive_torus_add(major_radius=3.15, minor_radius=0.06, major_segments=64, minor_segments=6)
ring = bpy.context.active_object
ring.data.materials.append(ring_m)
ring.parent = root
ring.location = (0, 0, DECK + 0.03)
from promo_kit import key_strength  # noqa: E402
key_strength(ring_m, 0, 0.0)
key_strength(ring_m, P.T(T_LAND + 0.9), 0.0)
key_strength(ring_m, P.T(T_LAND + 1.05), 30.0)
key_strength(ring_m, P.T(T_LAND + 1.5), 9.0)
# pulse the ring each time a lifter is on approach
for tl in (2.35, 3.5, 4.65):
    key_strength(ring_m, P.T(tl - 0.3), 9.0)
    key_strength(ring_m, P.T(tl), 26.0)
    key_strength(ring_m, P.T(tl + 0.3), 9.0)

# scanner mast spins up once powered
scanner.rotation_mode = 'XYZ'
z0 = scanner.rotation_euler.z
scanner.keyframe_insert('rotation_euler', index=2, frame=P.T(T_LAND + 0.9))
scanner.rotation_euler.z = z0 + math.radians(160 * (6 - T_LAND - 0.9))
scanner.keyframe_insert('rotation_euler', index=2, frame=P.T(6.0))
for fc in _fcurves(scanner.animation_data.action):
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'


# ------------------------------------------------------------------------------ thrusters
def cone_mesh(name, r, depth, verts=16):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=verts, radius1=r, radius2=0.0, depth=depth)
    # move so the wide end is at z=0 and the tip points down -Z
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -depth / 2))
    for v in bm.verts:
        v.co.z = -v.co.z - depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def flame_mat(name, col, strength, power=2.0):
    """Emission that fades to transparent toward the silhouette edges (soft plume)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = power
    pw.use_clamp = True
    nt.links.new(inv.outputs[0], pw.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*col, 1)
    em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(pw.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


FLAME_CORE = flame_mat('ThrustCore', (0.6, 0.85, 1.0), 9, power=2.5)
FLAME_OUT = flame_mat('ThrustGlow', (0.1, 0.4, 1.0), 4, power=4.0)
NOZZLE = emit_mat('Nozzle', (0.7, 0.9, 1.0), 30)


def thruster(name, parent, loc, r, length, keys):
    """A down-firing blue-white plume. keys: [(t, power 0..1)]; flickers between keys."""
    base = empty(name)
    base.parent = parent
    base.location = loc
    core = sphere(name + '_core', 1.0, FLAME_CORE, seg=(16, 10))
    core.parent = base
    core.scale = (r * 0.4, r * 0.4, length * 0.32)
    core.location = (0, 0, -length * 0.25)
    glow = sphere(name + '_glow', 1.0, FLAME_OUT, seg=(16, 10))
    glow.parent = base
    glow.scale = (r * 0.85, r * 0.85, length * 0.6)
    glow.location = (0, 0, -length * 0.45)
    disc = sphere(name + '_disc', 1.0, NOZZLE, seg=(12, 6))
    disc.parent = base
    disc.scale = (r * 0.7, r * 0.7, 0.06)
    # flicker
    t_first, t_last = keys[0][0], keys[-1][0]
    f = P.T(t_first)
    while f <= P.T(t_last) + 0.01:
        t = (f - 1) / P.fps
        # interpolate power
        pw = 0.0
        for (ta, pa), (tb, pb) in zip(keys, keys[1:]):
            if ta <= t <= tb:
                u = (t - ta) / max(1e-4, tb - ta)
                pw = pa + (pb - pa) * u
                break
        s = max(0.001, pw)
        jit = P.rnd.uniform(0.85, 1.15)
        base.scale = (s ** 0.5, s ** 0.5, max(0.001, s * jit))
        base.keyframe_insert('scale', frame=f)
        f += 2
    show_between(base, P.T(t_first), P.T(t_last) + 1)
    return base


for i, (x, y) in enumerate([(-2.6, -2.4), (2.6, -2.4), (-2.6, 2.4), (2.6, 2.4)]):
    thruster(f'PadJet{i}', root, (x, y, 0.05), 0.85, 4.0,
             [(0.0, 0.35), (0.5, 0.6), (0.6, 1.25), (0.95, 1.05), (1.15, 0.45), (T_LAND + 0.08, 0.0)])
# under-glow light while burning
jl = link(bpy.data.objects.new('PadJetLight', bpy.data.lights.new('PadJetLight', 'POINT')))
jl.parent = root
jl.location = (0, 0, -1.5)
jl.data.color = (0.45, 0.7, 1.0)
jl.data.shadow_soft_size = 2.0
for t, e in [(0.0, 8000), (0.6, 30000), (1.0, 26000), (T_LAND, 9000), (T_LAND + 0.15, 0)]:
    jl.data.energy = e
    jl.data.keyframe_insert('energy', frame=P.T(t))


# ------------------------------------------------------------------------------ folded-face lights
# The undersides of the side decks and ramp become the crate's outer walls while folded: give
# them Terran neon strips and orange marker lights so the falling crate reads as Terran tech.
ACC_NEON = emit_mat('PadAccNeon', COL['terran_neon'], 7)
ACC_ORANGE = emit_mat('PadAccOrange', COL['terran_orange'], 7)


def acc_box(name, dims, loc, mat, parent):
    o = cube(name, 1.0, mat, loc=loc)
    o.scale = dims
    o.parent = parent
    return o


ZU = -0.39 - 0.03   # just under the deck plate, in hinge-local space
for nm, sgn in (('north', 1), ('south', -1)):
    pv = pivots[nm]
    for k, yy in enumerate((1.1, 2.5)):
        acc_box(f'Acc_{nm}_bar{k}', (11.5, 0.16, 0.05), (0, sgn * yy, ZU), ACC_NEON, pv)
    acc_box(f'Acc_{nm}_chev', (4.0, 0.3, 0.05), (0, sgn * 1.8, ZU), ACC_ORANGE, pv)
    for xx in (-6.3, 6.3):
        acc_box(f'Acc_{nm}_lamp{xx}', (0.45, 0.45, 0.08), (xx, sgn * 3.2, ZU), ACC_ORANGE, pv)
pv = pivots['ramp']
for k, xx in enumerate((1.0, 2.4)):
    acc_box(f'Acc_ramp_bar{k}', (0.16, 5.6, 0.05), (xx, 0, ZU), ACC_NEON, pv)
for yy in (-2.7, 2.7):
    acc_box(f'Acc_ramp_lamp{yy}', (0.45, 0.45, 0.08), (3.1, yy, ZU), ACC_ORANGE, pv)
# core flanks (west face and the strip of south/north faces between the hinges)
acc_box('Acc_west_bar', (0.05, 5.6, 0.1), (-7.25, 0, 0.2), ACC_NEON, root)


# ------------------------------------------------------------------------------ dust
SAND = (0.46, 0.42, 0.34)


def dust_wave(center, t, r0, r1, rings=3, n=28, size=1.2, life=1.4, color=SAND, opacity=0.35,
              rise=0.5, dt=0.12):
    """Soft kit puffs in expanding rings: reads as dust blasting outward."""
    c = Vector(center)
    for k in range(rings):
        u = k / max(1, rings - 1)
        r = r0 + (r1 - r0) * u
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * k) / n + P.rnd.uniform(-0.08, 0.08)
            p = c + Vector((math.cos(a), math.sin(a), 0)) * r * P.rnd.uniform(0.92, 1.08)
            P.puff(p + Vector((0, 0, 0.25)), t + dt * k + P.rnd.uniform(0, 0.04),
                   size=size * (0.8 + 0.5 * u), n=1, rise=rise * (1 + u), life=life,
                   color=color, opacity=opacity * (1 - 0.3 * u))


# thruster wash as it nears the ground, then the touchdown ring
dust_wave((0, 0, 0), 0.85, 3.0, 6.5, rings=2, n=16, size=1.4, life=1.0, opacity=0.45)
dust_wave((0, 0, 0), T_LAND - 0.03, 7.0, 15.0, rings=4, n=32, size=1.8, life=1.7, opacity=0.6, dt=0.1)
P.cam_shake(T_LAND, 0.22, dur=0.45)

# ------------------------------------------------------------------------------ delivery lifters
HULL_M = pbr_mat('LifterHull', (0.07, 0.075, 0.085), rough=0.4, metal=0.7)
PANEL_M = pbr_mat('LifterPanel', (0.15, 0.16, 0.18), rough=0.45, metal=0.6)
ORANGE_M = emit_mat('LifterOrange', COL['terran_orange'], 6)
NEON_M = emit_mat('LifterNeon', COL['terran_neon'], 8)


def blob(name, scale, loc, mat, parent, seg=(32, 16)):
    o = sphere(name, 1.0, mat, seg=seg)
    o.scale = scale
    o.location = loc
    o.parent = parent
    return o


def unit_halfwidth(unit):
    bpy.context.view_layer.update()
    ys = []
    inv = unit.root.matrix_world.inverted()
    for m in unit.meshes:
        for c in m.bound_box:
            ys.append(abs((inv @ (m.matrix_world @ Vector(c))).y))
    return max(ys) if ys else 1.3


def build_lifter(name, hw, h_unit):
    """Windowless heavy-lift drone: one sleek lozenge hull with two integrated side thruster
    nacelles and four hinged clamp arms. Origin = underside of the hull (cargo roof)."""
    r = empty(name)
    blob(name + '_hull', (3.3, max(1.35, hw + 0.15), 0.42), (0, 0, 0.45), HULL_M, r)
    blob(name + '_ridge', (2.4, 0.55, 0.3), (-0.3, 0, 0.8), PANEL_M, r)
    blob(name + '_fin', (0.8, 0.08, 0.45), (-2.3, 0, 0.95), PANEL_M, r, seg=(16, 8))
    acc_box(name + '_spine', (3.0, 0.1, 0.05), (-0.2, 0, 1.1), NEON_M, r)
    ny = hw + 0.55
    for s in (1, -1):
        blob(name + f'_nac{s}', (1.9, 0.6, 0.38), (0.1, s * ny, 0.4), PANEL_M, r)
        acc_box(name + f'_stripe{s}', (2.6, 0.04, 0.08), (0.1, s * (ny + 0.58), 0.45), ORANGE_M, r)
        blob(name + f'_well{s}', (0.5, 0.42, 0.05), (0.1, s * ny, 0.03), NEON_M, r, seg=(16, 6))
    clamps = []
    for sx in (1.3, -1.3):
        for s in (1, -1):
            pv = empty(f'{name}_clampPv{sx}{s}')
            pv.parent = r
            pv.location = (sx, s * (hw + 0.1), 0.1)
            pv.rotation_mode = 'XYZ'
            pv['side'] = s
            acc_box(f'{name}_clamp{sx}{s}', (0.28, 0.12, h_unit * 0.6), (0, 0, -h_unit * 0.3), HULL_M, pv)
            acc_box(f'{name}_claw{sx}{s}', (0.34, 0.3, 0.12), (0, -s * 0.1, -h_unit * 0.6), ORANGE_M, pv)
            clamps.append(pv)
    return r, clamps, ny


def lifter_jets(lifter, name, ny, keys):
    for s in (1, -1):
        thruster(f'{name}_jet{s}', lifter, (0.1, s * ny, 0.02), 0.6, 1.9, keys)


def key_path(obj, keys):
    """keys: [(t, (x, y, z), heading_deg)]"""
    obj.rotation_mode = 'XYZ'
    for t, p, h in keys:
        obj.location = p
        obj.rotation_euler = (0, 0, math.radians(h))
        obj.keyframe_insert('location', frame=P.T(t))
        obj.keyframe_insert('rotation_euler', frame=P.T(t))
    set_interp(obj, 'BEZIER')


def ramp_drive(unit, t_go, exit_pts, speed, heading0=0.0):
    """Unit sitting on the landing circle from t_go: rolls down the +X ramp, then follows
    exit_pts [(t, (x, y))] on the ground. Pitches nose-down on the ramp."""
    keys = [(t_go, (0, 0, DECK), heading0)]
    # deck -> ramp lip -> ramp foot -> ground
    ramp = [(2.4, DECK - 0.05), (3.6, 0.72), (5.2, 0.42), (7.6, 0.05), (9.5, 0.0)]
    x_prev, t = 0.0, t_go
    for x, z in ramp:
        dt = (x - x_prev) / speed
        # accelerate from standstill over the first metres
        if x_prev == 0.0:
            dt *= 1.7
        t += dt
        keys.append((t, (x, 0, z), 0.0))
        x_prev = x
    for te, p in exit_pts:
        keys.append((te, (p[0], p[1], 0.0), None))
    # headings from travel direction for the exit legs
    out = []
    for i, (te, p, h) in enumerate(keys):
        if h is None:
            a = keys[i - 1][1]
            b = keys[min(i + 1, len(keys) - 1)][1] if i + 1 < len(keys) else p
            d = (Vector(b) - Vector(a)) if i + 1 < len(keys) else (Vector(p) - Vector(a))
            h = math.degrees(math.atan2(d.y, d.x))
        out.append((te, p, h))
    root_ = unit.root
    root_.rotation_mode = 'XYZ'
    prev = None
    for i, (te, p, h) in enumerate(out):
        if prev is not None:
            while h - prev > 180:
                h -= 360
            while h - prev < -180:
                h += 360
        prev = h
        pitch = 0.0
        if 0 < i < len(out) - 1:
            a, b = Vector(out[i - 1][1]), Vector(out[i + 1][1])
            d = b - a
            pitch = -math.degrees(math.atan2(d.z, max(1e-3, math.hypot(d.x, d.y))))
        root_.location = p
        root_.rotation_euler = (0, math.radians(pitch), math.radians(h))
        root_.keyframe_insert('location', frame=P.T(te))
        root_.keyframe_insert('rotation_euler', frame=P.T(te))
    set_interp(root_, 'BEZIER')
    return out


def delivery(unit, label, t_arrive, t_touch, src, heading_in, exit_pts, speed, leave_to):
    """Lifter flies in from src carrying `unit`, sets it on the landing circle at t_touch
    (the unit settles with a small bounce), opens its clamps, climbs away to leave_to. The
    unit then drives down the ramp."""
    h_unit = unit.entry['height']
    hw = unit_halfwidth(unit)
    lift, clamps, ny = build_lifter(label, hw, h_unit)
    hang = h_unit + 0.1                 # lifter origin height above the unit's base
    t_rel = t_touch + 0.16
    t_go = t_touch + 0.42
    sx, sy, sz = src
    carry = [
        (t_arrive, (sx, sy, sz), heading_in),
        (t_touch - 0.45, (sx * 0.12, sy * 0.12, DECK + 3.0), heading_in * 0.15),
        (t_touch, (0, 0, DECK), 0.0),
    ]
    key_path(unit.root, carry + [(t_touch + 0.07, (0, 0, DECK - 0.09), 0.0),
                                 (t_touch + 0.18, (0, 0, DECK + 0.03), 0.0),
                                 (t_touch + 0.3, (0, 0, DECK), 0.0)])
    # lifter: same path + hang, holds, then climbs away
    lk = [(t, (p[0], p[1], p[2] + hang), h) for t, p, h in carry]
    lk += [(t_rel, (0, 0, DECK + hang + 0.05), 0.0),
           (t_rel + 0.4, (0.4, 0, DECK + hang + 2.6), 6.0),
           (t_rel + 1.6, leave_to, 40.0)]
    key_path(lift, lk)
    # clamps swing open on release
    for pv in clamps:
        s = pv['side']
        pv.keyframe_insert('rotation_euler', index=0, frame=P.T(t_rel - 0.06))
        pv.rotation_euler.x = math.radians(-s * 55)
        pv.keyframe_insert('rotation_euler', index=0, frame=P.T(t_rel + 0.12))
        pv.rotation_euler.x = math.radians(-s * 48)
        pv.keyframe_insert('rotation_euler', index=0, frame=P.T(t_rel + 0.25))
    show_between(lift, P.T(t_arrive), P.T(6.0) + 1)
    unit.appear(t_arrive)
    lifter_jets(lift, label, ny, [(t_arrive, 0.7), (t_touch - 0.4, 1.2), (t_touch, 0.75), (t_rel + 0.1, 1.3),
                                  (t_rel + 0.6, 1.0), (min(6.0, t_rel + 1.6), 0.8)])
    # jet wash across the deck as it sets down
    dust_wave((0, 0, DECK), t_touch - 0.12, 2.5, 5.5, rings=2, n=12, size=0.7, life=0.7,
              color=(0.5, 0.55, 0.62), opacity=0.25, rise=0.3)
    ramp_drive(unit, t_go, exit_pts, speed)
    P.dust(unit, t_go + 0.8, min(6.0, exit_pts[-1][0]), every=0.12, size=0.75)
    return lift


lancer = P.load('lancer', at=(0, 0), label='lancer_d')
outrider = P.load('outrider', at=(0, 0), label='outrider_d')
hauler = P.load('hauler', at=(0, 0), label='hauler_d')

# 1) Lancer: first down, rolls off, swings round and parks covering the pad's flank
L1 = delivery(lancer, 'LifterA', 1.5, 2.35, (-20, -16, 16), -35,
              [(4.3, (12.0, -3.5)), (5.2, (10.5, -6.6)), (5.75, (10.0, -7.2)), (6.0, (9.95, -7.25))],
              speed=11.0, leave_to=(14, 22, 26))
lancer.turret_yaw([(5.0, 0), (5.7, 80), (6.0, 84)])
# 2) Outrider: quick scout, set down as the Lancer clears the circle, swings round the far side
L2 = delivery(outrider, 'LifterB', 2.55, 3.5, (-18, 16, 15), 40,
              [(4.95, (12.5, 3.2)), (5.5, (11.0, 6.4)), (6.0, (9.6, 7.6))], speed=15.0,
              leave_to=(-6, 30, 28))
# 3) Hauler: last one in, still rolling down the ramp at the end
L3 = delivery(hauler, 'LifterC', 3.7, 4.65, (-22, -4, 17), 5,
              [(7.3, (12.5, 0.5))], speed=7.5,
              leave_to=(-12, 16, 20))

# ------------------------------------------------------------------------------ camera
# 0-1.3 low, wide, looking up as the crate-pad plunges in; touchdown shake;
# 1.3-2.6 push in close on the first lifter setting the Lancer down (clamps opening);
# 2.6-4.6 track round the pad with each delivery; 6.0 end on the ramp side, pad big in frame
# with the Lancer and Outrider parked either side and the Hauler on the ramp.
P.camera([
    (0.0, (-15, -20, 1.6), (-3, 2, 27.0), 22),
    (0.7, (-14, -19, 2.0), (-0.6, 0.3, 7.0), 22),
    (1.3, (-12.5, -17.5, 3.0), (0, 0, 1.6), 24),
    (2.0, (-9.5, -15, 6.8), (-1.0, -1.0, 3.0), 27),
    (2.6, (-5, -13.5, 7.4), (0.8, 0, 1.4), 28),
    (3.5, (5, -14.5, 7.0), (2, 0, 1.6), 28),
    (4.6, (15, -12.5, 5.8), (3.5, 0, 1.8), 27),
    (6.0, (22, -3, 4.8), (2.5, 0, 1.4), 26),
], shake=0.02)

P.render()
