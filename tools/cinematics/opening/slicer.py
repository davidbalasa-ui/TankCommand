"""The Shard's beams and what they do to ships (v4 ending, David 2026-11-28: "We need to see it slicing
through ships").

    column(keys, f_on, f_off, ...)   a violet beam rising out of the planet; keys move its foot so it sweeps
    slice_ship(ob, ...)              cut a ship mesh along a plane: a glowing seam runs across as the beam
                                     passes, then the two halves drift apart with molten faces
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion

import space as SP
import common as C
import v3base as V

VIO = (0.62, 0.25, 1.0)
VCORE = (0.78, 0.6, 1.0)
HOT = (1.0, 0.55, 0.2)
BASE_Z = -260.0


def column(foot_keys, f_on, f_off, top_z=400.0, r=6.0, name=None, twist=True, light=3e6):
    """foot_keys: [(frame, (x, y))]: where the beam stands (linear between keys). It erupts up out of the
    clouds over 4 frames from f_on, holds, thins out over 8 frames to f_off."""
    name = name or SP._uid('Cull')
    piv = bpy.data.objects.new(name + 'Foot', None)
    SP.link(piv)
    for f, (x, y) in foot_keys:
        piv.location = (x, y, BASE_Z)
        piv.keyframe_insert('location', frame=f)
    C.set_interp(piv, 'LINEAR')
    L = top_z - BASE_Z + 1500.0
    keys = [(f_on - 1, 1.0, 0.3), (f_on + 4, L, 1.25), (f_on + 8, L, 1.0), (f_off - 8, L, 1.0), (f_off, L, 0.0)]
    b = SP.beam(Vector((0, 0, 0)), Vector((0, 0, 1)), name, VIO, VCORE, r, keys, strength=3.5, glow=1.3)
    b.data.materials[0] = SP.flow_emit(name + 'Flow', VCORE, 4.5, scale=0.04, speed=14.0, lo=0.5, hi=1.8)
    b.parent = piv
    for ch in b.children:
        ch.scale = (1, 3.2, 3.2)
    if twist:
        tw = SP.beam_twist(Vector((0, 0, 0)), Vector((0, 0, 1)), name + 'Tw', VIO,
                           [(k[0], k[1] if k[2] > 0 else 0.0) for k in keys], keys[0][0], keys[-1][0],
                           radius=r * 1.5, pitch=r * 9, strands=3, width=r * 0.07, turns_per_s=2.5, length=L)
        tw.parent = piv
    Lt = bpy.data.objects.new(name + 'L', bpy.data.lights.new(name + 'L', 'POINT'))
    SP.link(Lt)
    Lt.parent = piv
    Lt.location = (0, 0, top_z - BASE_Z - 60)
    Lt.data.color = VIO
    Lt.data.shadow_soft_size = r * 4
    for f, e in [(1, 0), (f_on, 0), (f_on + 4, light * 1.6), (f_on + 10, light), (f_off - 6, light), (f_off, 0)]:
        Lt.data.energy = e
        Lt.data.keyframe_insert('energy', frame=f)
    SP.lin(Lt.data)
    return piv


def underglow(p, f0, f1, k=1.5e6, r=30.0):
    """Violet light swelling under a ship before the beam bursts up beneath it."""
    L = bpy.data.objects.new(SP._uid('UnderGlow'), bpy.data.lights.new(SP._uid('UnderGlow'), 'POINT'))
    SP.link(L)
    L.location = p
    L.data.color = VIO
    L.data.shadow_soft_size = r
    for f, e in [(1, 0), (f0, 0), (f1, k), (f1 + 6, 0)]:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=f)
    SP.lin(L.data)


def _molten_mat(name, f_cut):
    m, n = SP.BP._new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.6)
    b.inputs['Base Color'].default_value = (0.05, 0.03, 0.03, 1)
    tc = n.node('ShaderNodeTexCoord')
    nz = n.node('ShaderNodeTexNoise', Scale=0.4, Detail=6.0)
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    rp = n.node('ShaderNodeValToRGB')
    n.set(rp.inputs[0], nz.outputs['Fac'])
    rp.color_ramp.elements[0].color = (1.0, 0.25, 0.05, 1)
    rp.color_ramp.elements[1].color = (1.0, 0.85, 0.55, 1)
    n.set(b.inputs['Emission Color'], rp.outputs[0])
    from ground import _value
    heat = _value(m.node_tree, 'heat', 0.0)
    n.set(b.inputs['Emission Strength'], n.math('MULTIPLY', heat, n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.4, 1.6)))
    n.set(out.inputs['Surface'], b.outputs[0])
    SP.key_node(m, 'heat', [(1, 0.0), (f_cut - 1, 0.0), (f_cut, 30.0), (f_cut + 12, 14.0), (f_cut + 48, 4.0),
                            (f_cut + 120, 1.2)])
    return m


def _half(src_me, plane_co, plane_no, keep_pos, mat_cap, name):
    bm = bmesh.new()
    bm.from_mesh(src_me)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=plane_co, plane_no=plane_no,
                                 clear_inner=keep_pos, clear_outer=not keep_pos, dist=1e-4)
    cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge) and e.is_valid and e.is_boundary]
    me = bpy.data.meshes.new(name)
    n_mat = len(src_me.materials)
    if cut_edges:
        try:
            r = bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
            faces = r.get('faces', [])
        except Exception:
            faces = []
        if not faces:
            try:
                r = bmesh.ops.contextual_create(bm, geom=cut_edges)
                faces = r.get('faces', [])
            except Exception:
                faces = []
        for f in faces:
            f.material_index = n_mat
            f.smooth = False
    bm.to_mesh(me)
    bm.free()
    for m in src_me.materials:
        me.materials.append(m)
    me.materials.append(mat_cap)
    return me


def slice_ship(ob, plane_no_l, f_cut, plane_off_l=Vector((0, 0, 0)), sweep_l=None, f_sweep0=None,
               sep=4.0, spin=8.0, end_f=None, seed=0, terran=True, boom=True, extra_hide=(), follow=False, move=(1.0, 1.0)):
    """Cut ob (a single-mesh ship) along the plane through plane_off_l with normal plane_no_l (both in
    ob's local space). sweep_l: direction (local, in the plane) the beam crosses the hull; the seam glows
    from one side to the other between f_sweep0 and f_cut. Halves drift apart from f_cut, keeping ob's
    velocity. Returns (half_pos, half_neg) objects."""
    rnd = random.Random(seed)
    sc = bpy.context.scene
    end_f = end_f or sc.frame_end
    sc.frame_set(f_cut)
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    sc.frame_set(f_cut + 1)
    bpy.context.view_layer.update()
    vel = ob.matrix_world.translation - mw.translation       # per frame
    sc.frame_set(f_cut)
    no = Vector(plane_no_l).normalized()
    cap = _molten_mat(SP._uid('Molten'), f_cut)
    src = ob.data
    halves = []
    anchor = bpy.data.objects.new(SP._uid('SliceAnchor'), None)
    SP.link(anchor)
    track = {}
    if follow:                     # the bigger part flies on with the ship
        for f in range(f_cut, end_f + 1):
            sc.frame_set(f)
            bpy.context.view_layer.update()
            track[f] = ob.matrix_world.copy()
        sc.frame_set(f_cut)
    for f in (sorted(track) if follow else (f_cut, end_f)):
        anchor.matrix_world = track[f] if follow else Matrix.Translation(vel * (f - f_cut)) @ mw
        anchor.keyframe_insert('location', frame=f)
        anchor.keyframe_insert('rotation_euler', frame=f)
        anchor.keyframe_insert('scale', frame=f)
    C.set_interp(anchor, 'LINEAR')
    loose = anchor
    if follow:
        loose = bpy.data.objects.new(SP._uid('SliceLoose'), None)
        SP.link(loose)
        for f in (f_cut, end_f):
            loose.matrix_world = Matrix.Translation(vel * (f - f_cut)) @ mw
            loose.keyframe_insert('location', frame=f)
            loose.keyframe_insert('rotation_euler', frame=f)
            loose.keyframe_insert('scale', frame=f)
        C.set_interp(loose, 'LINEAR')
    span = max(ob.dimensions) / max(ob.scale)
    for sgn in (1, -1):
        me = _half(src, Vector(plane_off_l), no, sgn > 0, cap, SP._uid('Half'))
        h = bpy.data.objects.new(SP._uid('Half'), me)
        SP.link(h)
        h.parent = anchor
        h.rotation_mode = 'XYZ'
        # each half pivots about its own middle: shift geometry so the origin sits at its centroid
        cen = sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices))
        me.transform(Matrix.Translation(-cen))
        axis = no.cross(Vector((0, 0, 1)) if abs(no.z) < 0.9 else Vector((1, 0, 0))).normalized()
        mk = move[0] if sgn > 0 else move[1]
        d = no * sgn * sep * mk
        tumble = axis * math.radians(spin) * sgn * rnd.uniform(0.7, 1.3) * mk
        if mk > 0:                 # the cut-off piece is left behind on the ship's speed at the cut
            h.parent = loose
        f1 = f_cut + 8
        keys = [(f_cut, cen), (f1, cen + d * 0.18), (end_f, cen + d * (1 + (end_f - f1) / 24.0))]
        SP.key_loc(h, keys, 'LINEAR')
        h.rotation_euler = (0, 0, 0)
        h.keyframe_insert('rotation_euler', frame=f_cut)
        h.rotation_euler = tumble * max(1.0, (end_f - f_cut) / 24.0)
        h.keyframe_insert('rotation_euler', frame=end_f)
        C.set_interp(h, 'LINEAR')
        SP.show(h, f_cut, end_f)
        halves.append(h)
    # the original goes when the halves appear (with its children: shield, plumes)
    for o in [ob] + list(ob.children_recursive) + list(extra_hide):
        sc.frame_set(f_cut - 1)
        was = o.hide_render
        o.keyframe_insert('hide_render', frame=f_cut - 1)
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=f_cut)
        o.hide_render = was
        SP._interp_where(o, 'hide_render', 'CONSTANT')
    sc.frame_set(f_cut)
    # sparks spraying off the cut as the beam crosses
    if sweep_l is not None and f_sweep0 is not None:
        cut_w = mw @ Vector(plane_off_l)
        SP.spark_stream(cut_w, f_sweep0, f_cut + 6, (1.0, 0.75, 0.9), tuple(mw.to_3x3() @ no * 0.6), seed + 3,
                        every=1, n=6, size=span * 0.006, speed=span * 0.5, life=0.6, strength=14.0)
    # the burst as it parts
    p = mw @ Vector(plane_off_l)
    if boom:
        SP.violet_boom(p, f_cut, span * 0.12, life=0.7, light=1e6, seed=seed)
        (SP.blue_boom if terran else SP.gold_boom)(p + vel * 6, f_cut + 5, span * 0.22, life=1.3,
                                                     light=2e6, seed=seed + 1, follow=tuple(vel * 24))
    SP.shards(p, f_cut, 26, (0.55, 0.8, 1.0) if terran else (1.0, 0.75, 0.3), span * 0.02, span * 0.6,
              seed=seed + 7, life=1.6, kind='tri' if terran else 'hex', drift=tuple(vel.normalized() if vel.length else (0, 0, 0)))
    return halves
