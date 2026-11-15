"""Shared kit for the Arcadian capital-ship interior concept stills (design work only, not game art).

Units are metres (a hover tank is ~8-10 m long, the game .glb units import at that size already).
Front is +X, up is +Z. Geometry is made with the forge kit (tools/art/v2/forge.py); this module adds

    init()                scene + Cycles + a space world (stars for the camera, soft studio for light)
    ZONES                 interior surface zones (silver / bronze / gold / floor / cut / glows ...)
    outlines              ellipse(), capsule(), rrect(), arc_room() -> 2D polygons for a deck plan
    deck_walls()          solid slab minus rooms (boolean) -> walls with flat tops, plus rim loops
    strip(), offset()     trims / inlays that follow those loops
    aperture()            Arcadian force aperture: thin exact rings with tick marks + dark membrane
    unit()                import a game unit .glb
    render()              render + 2D bloom / grade -> JPG
"""
import contextlib
import math
import os
import random
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'art', 'v2'))
import forge as F  # noqa: E402
import arcadian_fleet as A  # noqa: E402

GOLDGLOW = (1.0, 0.62, 0.13)
ZONES = dict(A.GOLD_ZONES)          # shell (gold), bronze, under, pale, slat, glow, core, arc, bolt
ZONES['glow'] = dict(kind='glow', emit=GOLDGLOW, strength=5.0)
ZONES['bolt'] = dict(kind='glow', emit=(1.0, 0.8, 0.4), strength=40.0)
ZONES['arc'] = dict(kind='glow', emit=(1.0, 0.7, 0.2), strength=10.0)
ZONES.update({
    'silver': dict(kind='etched', base=(0.62, 0.6, 0.58), base2=(0.44, 0.38, 0.31), rough=0.3, veins=0.12),
    'steel': dict(kind='etched', base=(0.3, 0.29, 0.29), base2=(0.2, 0.18, 0.16), rough=0.36, veins=0.0),
    'floor': dict(kind='etched', base=(0.34, 0.31, 0.28), base2=(0.22, 0.19, 0.16), rough=0.38, veins=0.0),
    'floor2': dict(kind='etched', base=(0.5, 0.47, 0.43), base2=(0.36, 0.31, 0.26), rough=0.34, veins=0.0),
    'inlay': dict(kind='etched', base=(1.0, 0.77, 0.32), base2=(0.95, 0.62, 0.2), rough=0.2, veins=0.0, fine=True),
    'cut': dict(kind='etched', base=(0.06, 0.052, 0.048), base2=(0.032, 0.028, 0.027), rough=0.5, veins=0.0),   # sectioned wall tops
    'line': dict(kind='glow', emit=(1.0, 0.56, 0.09), strength=3.2),   # thin glowing inlay lines
    'soft': dict(kind='glow', emit=(1.0, 0.62, 0.13), strength=1.8),
    'white': dict(kind='glow', emit=(1.0, 0.82, 0.5), strength=12.0),   # hot cores of rings
    'field': dict(kind='glow', emit=(0, 0, 0), strength=0.0),        # replaced by a custom material
    'hot': dict(kind='glow', emit=(1.0, 0.86, 0.6), strength=30.0),      # white-hot heart of an orb
    'wall': dict(kind='glow', emit=(0, 0, 0), strength=0.0),         # replaced by a custom material
    'vault': dict(kind='etched', base=(0.07, 0.06, 0.06), base2=(0.03, 0.027, 0.03), rough=0.42, veins=0.5),
    'thin': dict(kind='glow', emit=(1.0, 0.84, 0.5), strength=45.0),    # fine lightning
})
ST = dict(layer='main', layers={})


# ------------------------------------------------------------------ scene
def init(samples=24, res=(960, 540), threads=3, env=0.8, exposure=0.0, stars=1.0, warm=(1.0, 0.86, 0.66), wall_h=6.0,
         core_scale=0.5, core_gain=5.0, floor_mode='dark'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    F.ST.update(parts=[], mats={}, group='Hull', seq=0, faction='kesh')
    F.ZONES['kesh'].update(ZONES)
    ST.update(layer='main', layers={})
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 4
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.sample_clamp_indirect = 6.0
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = threads
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = exposure
    ST.update(wall_h=wall_h, core_scale=core_scale, core_gain=core_gain, floor_mode=floor_mode, orbs=[])
    _world(sc, env, stars, warm)
    _custom_mats()
    return sc


def _world(sc, env, stars, warm=(1.0, 0.86, 0.66)):
    w = bpy.data.worlds.new('Space')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    mix = nt.nodes.new('ShaderNodeMixShader')
    lp = nt.nodes.new('ShaderNodeLightPath')
    cam_bg = nt.nodes.new('ShaderNodeBackground')
    env_bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # stars: two voronoi layers (fine dust + fewer bright ones), a faint warm/blue nebula wash
    col = None
    for scale, thr, gain in ((420.0, 0.05, 1.6), (140.0, 0.035, 5.0)):
        vor = nt.nodes.new('ShaderNodeTexVoronoi')
        vor.inputs['Scale'].default_value = scale
        star = nt.nodes.new('ShaderNodeMapRange')
        star.inputs['From Min'].default_value = thr
        star.inputs['From Max'].default_value = 0.0
        star.inputs['To Max'].default_value = gain * stars
        nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
        nt.links.new(vor.outputs['Distance'], star.inputs['Value'])
        tint = nt.nodes.new('ShaderNodeMixRGB')
        tint.blend_type = 'MULTIPLY'
        tint.inputs['Fac'].default_value = 0.35
        nt.links.new(star.outputs[0], tint.inputs['Color1'])
        nt.links.new(vor.outputs['Color'], tint.inputs['Color2'])
        if col is None:
            col = tint.outputs[0]
        else:
            add = nt.nodes.new('ShaderNodeMixRGB')
            add.blend_type = 'ADD'
            add.inputs['Fac'].default_value = 1.0
            nt.links.new(col, add.inputs['Color1'])
            nt.links.new(tint.outputs[0], add.inputs['Color2'])
            col = add.outputs[0]
    neb = nt.nodes.new('ShaderNodeTexNoise')
    neb.inputs['Scale'].default_value = 2.2
    neb.inputs['Detail'].default_value = 6.0
    nr = nt.nodes.new('ShaderNodeValToRGB')
    nr.color_ramp.elements[0].position = 0.45
    nr.color_ramp.elements[0].color = (0.004, 0.006, 0.014, 1)
    nr.color_ramp.elements[1].position = 0.85
    nr.color_ramp.elements[1].color = (0.03, 0.035, 0.07, 1)
    nt.links.new(tc.outputs['Generated'], neb.inputs['Vector'])
    nt.links.new(neb.outputs[0], nr.inputs['Fac'])
    add = nt.nodes.new('ShaderNodeMixRGB')
    add.blend_type = 'ADD'
    add.inputs['Fac'].default_value = 1.0
    nt.links.new(col, add.inputs['Color1'])
    nt.links.new(nr.outputs['Color'], add.inputs['Color2'])
    nt.links.new(add.outputs[0], cam_bg.inputs['Color'])
    # light / reflection environment: soft warm and cool patches
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.inputs['Scale'].default_value = 1.4
    noi.inputs['Detail'].default_value = 2.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = (0.03, 0.04, 0.08, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (warm[0], warm[1], warm[2], 1)
    nt.links.new(tc.outputs['Generated'], noi.inputs['Vector'])
    nt.links.new(noi.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], env_bg.inputs['Color'])
    env_bg.inputs['Strength'].default_value = env
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(env_bg.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])


def _etched(zone, b, b2, rough, metal, line=(1.0, 0.72, 0.26), emit=0.0, scale=1.0, amount=1.0, dark=False, sparse=False):
    """Architectural metal with sparse flowing engraved lines (as on the hulls in the style
    reference): two families of gently curving bands, the lines filled with gold (or cut dark)."""
    mat = bpy.data.materials.new('zone_' + zone)
    mat.use_nodes = True
    n = F.N(mat)
    fine = n.noise(18.0, 4.0)
    col = n.mix(n.smooth(n.noise(0.3, 3.0), 0.3, 0.7), b, b2)
    w = n.wave(0.085 * scale, 3.0, 0.0, 0.12)
    l1 = n.m('SUBTRACT', 1.0, n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', w, 0.5)), 0.008, 0.018))
    if sparse:
        l1 = n.m('MULTIPLY', l1, n.smooth(n.noise(0.11 * scale, 2.0, n.vscale(n.co, (1.0, 1.3, 0.7))), 0.48, 0.56))
    w2 = n.wave(0.12 * scale, 4.0, 0.0, 0.1, n.vscale(n.co, (0.6, 1.0, 1.3)))
    l2 = n.m('MULTIPLY', n.m('SUBTRACT', 1.0, n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', w2, 0.5)), 0.006, 0.014)),
             n.smooth(n.noise(0.16 * scale, 2.0), 0.46, 0.56))
    eng = n.m('MULTIPLY', n.m('MAXIMUM', l1, l2), amount)
    lc = (b2[0] * 0.15, b2[1] * 0.15, b2[2] * 0.15) if dark else line
    col = n.mix(eng, col, lc)
    rr = n.m('ADD', rough - 0.04, n.m('MULTIPLY', fine, 0.1))
    if emit > 0:
        n.out(col, rr, metal, (1.0, 0.62, 0.13), n.m('MULTIPLY', eng, emit))
    else:
        n.out(col, rr, metal)
    n.bump(n.m('SUBTRACT', n.m('MULTIPLY', fine, 0.03), eng), 0.4, 0.03, soft=False)
    F.ST['mats'][zone] = mat
    return mat


def _custom_mats():
    H = ST.get('wall_h', 6.0)
    _etched('pale', (1.0, 0.77, 0.34), (0.95, 0.62, 0.2), 0.2, 0.95, dark=True, amount=0.8)
    _etched('shell', (1.0, 0.7, 0.26), (0.85, 0.52, 0.14), 0.24, 0.95, dark=True, amount=0.8)
    _etched('silver', (0.6, 0.62, 0.66), (0.44, 0.46, 0.5), 0.28, 0.7, emit=0.3)
    _etched('bronze', (0.5, 0.47, 0.43), (0.34, 0.31, 0.28), 0.32, 0.75, emit=0.15)
    _etched('under', (0.12, 0.115, 0.12), (0.07, 0.068, 0.075), 0.4, 0.8, line=(0.5, 0.36, 0.14))
    _etched('vault', (0.05, 0.053, 0.062), (0.028, 0.03, 0.038), 0.42, 0.7, emit=0.6, scale=0.8)
    _etched('cut', (0.05, 0.052, 0.06), (0.032, 0.034, 0.04), 0.5, 0.6, line=(0.2, 0.16, 0.09), scale=0.8)
    if ST.get('floor_mode', 'dark') == 'light':
        _etched('floor', (0.46, 0.46, 0.48), (0.36, 0.36, 0.39), 0.4, 0.3, line=(0.6, 0.38, 0.09), scale=1.2)
        _etched('floor2', (0.62, 0.61, 0.6), (0.52, 0.51, 0.5), 0.38, 0.3, line=(0.6, 0.38, 0.09), scale=1.2)
    else:
        _etched('floor', (0.13, 0.135, 0.15), (0.08, 0.083, 0.095), 0.2, 0.7, emit=0.3, scale=0.9)
        _etched('floor2', (0.24, 0.245, 0.26), (0.17, 0.173, 0.19), 0.2, 0.7, emit=0.3, scale=0.9)
    # 'wall': cool etched silver with a dark louvred band low down (thin glowing gold slats)
    mat = bpy.data.materials.new('zone_wall')
    mat.use_nodes = True
    n = F.N(mat)
    z = n.sep(n.co)[2]
    fine = n.noise(22.0, 5.0)
    col = n.mix(n.smooth(n.noise(0.5, 3.0), 0.35, 0.7), (0.7, 0.72, 0.76), (0.5, 0.52, 0.56))
    w = n.wave(0.07, 3.0, 0.0, 0.12, n.vscale(n.co, (1.0, 1.0, 2.2)))
    etch = n.m('SUBTRACT', 1.0, n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', w, 0.5)), 0.008, 0.018))
    col = n.mix(etch, col, (1.0, 0.72, 0.26))
    b0, b1 = 0.95, H * 0.4
    band = n.m('MULTIPLY', n.m('GREATER_THAN', z, b0), n.m('LESS_THAN', z, b1))
    slat = n.m('MULTIPLY', band, n.m('LESS_THAN', n.m('FRACT', n.m('MULTIPLY', z, 2.6)), 0.16))
    runs = n.m('GREATER_THAN', n.noise(0.09, 0.0, n.vscale(n.co, (1.0, 1.0, 0.0))), 0.42)
    slat = n.m('MULTIPLY', slat, runs)
    col = n.mix(band, col, (0.03, 0.03, 0.035))
    rough = n.m('ADD', 0.26, n.m('ADD', n.m('MULTIPLY', fine, 0.14), n.m('MULTIPLY', band, 0.25)))
    n.out(col, rough, 0.75, (1.0, 0.62, 0.13), n.m('ADD', n.m('MULTIPLY', slat, 4.0), n.m('MULTIPLY', etch, 0.25)))
    n.bump(n.m('SUBTRACT', n.m('MULTIPLY', fine, 0.05), n.m('ADD', etch, band)), 0.5, 0.03, soft=False)
    F.ST['mats']['wall'] = mat
    # 'core': a translucent gold shell (emission + transparency, swirling) round a white-hot heart
    # (zone 'hot', a smaller sphere inside) - so every orb has a white-hot centre and a gold limb
    mat = bpy.data.materials.new('zone_core')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (0.75, 0.6, 0.35, 1)
    em = nt.nodes.new('ShaderNodeEmission')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.inputs['Scale'].default_value = ST.get('core_scale', 0.5) * 1.6
    noi.inputs['Detail'].default_value = 5.0
    nt.links.new(tc.outputs['Object'], noi.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (1.0, 0.36, 0.015, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (1.0, 0.66, 0.16, 1)
    nt.links.new(noi.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    em.inputs['Strength'].default_value = ST.get('core_gain', 5.0) * 0.22
    addsh = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], addsh.inputs[0])
    nt.links.new(em.outputs[0], addsh.inputs[1])
    nt.links.new(addsh.outputs[0], out.inputs['Surface'])
    F.ST['mats']['core'] = mat
    # 'field': force-field membrane - almost clear, a dark crisp film with faint exact rings
    mat = bpy.data.materials.new('zone_field')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (0.72, 0.68, 0.6, 1)
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.66, 0.16, 1)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 9.0
    nt.links.new(ln.outputs['Value'], mul.inputs[0])
    fr = nt.nodes.new('ShaderNodeMath')
    fr.operation = 'FRACT'
    nt.links.new(mul.outputs[0], fr.inputs[0])
    lt = nt.nodes.new('ShaderNodeMath')
    lt.operation = 'LESS_THAN'
    lt.inputs[1].default_value = 0.06
    nt.links.new(fr.outputs[0], lt.inputs[0])
    edge = nt.nodes.new('ShaderNodeMapRange')          # brighter toward the rim
    edge.inputs['From Min'].default_value = 0.55
    edge.inputs['From Max'].default_value = 1.0
    edge.inputs['To Min'].default_value = 0.05
    edge.inputs['To Max'].default_value = 1.0
    nt.links.new(ln.outputs['Value'], edge.inputs['Value'])
    st = nt.nodes.new('ShaderNodeMath')
    st.operation = 'MULTIPLY'
    nt.links.new(lt.outputs[0], st.inputs[0])
    nt.links.new(edge.outputs[0], st.inputs[1])
    st2 = nt.nodes.new('ShaderNodeMath')
    st2.operation = 'MULTIPLY_ADD'
    st2.inputs[1].default_value = 1.6
    st2.inputs[2].default_value = 0.0
    nt.links.new(st.outputs[0], st2.inputs[0])
    nt.links.new(st2.outputs[0], em.inputs['Strength'])
    addsh = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], addsh.inputs[0])
    nt.links.new(em.outputs[0], addsh.inputs[1])
    nt.links.new(addsh.outputs[0], out.inputs['Surface'])
    F.ST['mats']['field'] = mat


def door_mat(name='doorfield', strength=1.0, clear=0.6):
    """Force-field door film: translucent gold with fine horizontal scan lines."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (clear, clear * 0.9, clear * 0.7, 1)
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.66, 0.16, 1)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sp = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sp.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 2.5
    nt.links.new(sp.outputs['Z'], mul.inputs[0])
    fr = nt.nodes.new('ShaderNodeMath')
    fr.operation = 'FRACT'
    nt.links.new(mul.outputs[0], fr.inputs[0])
    lt = nt.nodes.new('ShaderNodeMath')
    lt.operation = 'LESS_THAN'
    lt.inputs[1].default_value = 0.1
    nt.links.new(fr.outputs[0], lt.inputs[0])
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.inputs['Scale'].default_value = 0.6
    noi.inputs['Detail'].default_value = 5.0
    nt.links.new(tc.outputs['Object'], noi.inputs['Vector'])
    ma = nt.nodes.new('ShaderNodeMath')
    ma.operation = 'MULTIPLY_ADD'
    ma.inputs[1].default_value = strength * 1.2
    ma.inputs[2].default_value = strength * 0.22
    nt.links.new(lt.outputs[0], ma.inputs[0])
    mb = nt.nodes.new('ShaderNodeMath')
    mb.operation = 'MULTIPLY'
    nt.links.new(ma.outputs[0], mb.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.3
    mr.inputs['From Max'].default_value = 0.7
    mr.inputs['To Min'].default_value = 0.5
    mr.inputs['To Max'].default_value = 1.5
    nt.links.new(noi.outputs[0], mr.inputs['Value'])
    nt.links.new(mr.outputs[0], mb.inputs[1])
    nt.links.new(mb.outputs[0], em.inputs['Strength'])
    addsh = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], addsh.inputs[0])
    nt.links.new(em.outputs[0], addsh.inputs[1])
    nt.links.new(addsh.outputs[0], out.inputs['Surface'])
    return mat


def raw_mesh(name, verts, faces, mat, shadow=False):
    """Plain object outside the forge part list (membranes, films)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat)
    o.visible_shadow = shadow
    return o


@contextlib.contextmanager
def layer(name):
    """Parts made inside are joined into their own objects (so a roof can be hidden from light rays)."""
    m = F.mark()
    try:
        yield
    finally:
        for o in F.since(m):
            if 'layer' not in o:
                o['layer'] = name


def finish():
    """Join all forge parts into one object per (layer, zone). Returns {layer: [objects]}."""
    groups = {}
    for o in F.ST['parts']:
        groups.setdefault((o.get('layer', 'main'), o['zone']), []).append(o)
    out = {}
    for (lay, zone), parts in groups.items():
        for o in parts:
            o.data.materials.clear()
            o.data.materials.append(F.zone_mat(zone))
        bpy.ops.object.select_all(action='DESELECT')
        for o in parts:
            o.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        if len(parts) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        obj.name = f'{lay}_{zone}'
        if zone in ('core', 'hot', 'glow', 'line', 'soft', 'white', 'thin', 'bolt', 'arc'):
            obj.visible_shadow = False
        out.setdefault(lay, []).append(obj)
    F.ST['parts'] = []
    for lay, objs in out.items():
        ST['layers'].setdefault(lay, []).extend(objs)
    return out


def ghost(lay, camera=True, glossy=False):
    """Make a layer invisible to light (it casts no shadow and blocks no bounce light), so the world
    and suns light the deck straight through a roof the camera still sees."""
    for o in ST['layers'].get(lay, []):
        o.visible_shadow = False
        o.visible_diffuse = False
        o.visible_glossy = glossy
        o.visible_camera = camera
        o.visible_transmission = False


# ------------------------------------------------------------------ lights / camera
def sun(rot, energy, col=(1, 0.95, 0.88), angle=4.0):
    ld = bpy.data.lights.new('Sun', 'SUN')
    ld.energy = energy
    ld.color = col
    ld.angle = math.radians(angle)
    o = bpy.data.objects.new('Sun', ld)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]
    return o


def point(loc, energy, col=(1.0, 0.6, 0.25), r=0.5, cam=False):
    ld = bpy.data.lights.new('Pt', 'POINT')
    ld.energy = energy
    ld.color = col
    ld.shadow_soft_size = r
    o = bpy.data.objects.new('Pt', ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.visible_camera = cam
    return o


def area(loc, target, energy, size=(6, 6), col=(1.0, 0.85, 0.65), spread=180):
    ld = bpy.data.lights.new('Area', 'AREA')
    ld.energy = energy
    ld.color = col
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = size
    ld.spread = math.radians(spread)
    o = bpy.data.objects.new('Area', ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def camera(loc, target, lens=28, roll=0.0, clip=(0.2, 20000), shift=(0.0, 0.0)):
    sc = bpy.context.scene
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = lens
    cam.data.clip_start, cam.data.clip_end = clip
    cam.data.shift_x, cam.data.shift_y = shift
    cam.location = loc
    d = Vector(target) - Vector(loc)
    q = d.to_track_quat('-Z', 'Y')
    cam.rotation_euler = (q @ Matrix.Rotation(math.radians(roll), 4, 'Z').to_quaternion()).to_euler()
    return cam


# ------------------------------------------------------------------ 2D outlines (deck plans)
def ellipse(c, rx, ry, n=96, rot=0.0):
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        out.append((c[0] + x * cr - y * sr, c[1] + x * sr + y * cr))
    return out


def superellipse(c, rx, ry, p=3.0, n=120):
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        out.append((c[0] + rx * math.copysign(abs(ca) ** (2 / p), ca), c[1] + ry * math.copysign(abs(sa) ** (2 / p), sa)))
    return out


def capsule(p0, p1, w, n=14):
    """Corridor from p0 to p1, w wide, round ends."""
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0).normalized()
    a0 = math.atan2(d.y, d.x)
    out = []
    for k in range(n + 1):
        a = a0 - math.pi / 2 + math.pi * k / n
        out.append((p1.x + math.cos(a) * w / 2, p1.y + math.sin(a) * w / 2))
    for k in range(n + 1):
        a = a0 + math.pi / 2 + math.pi * k / n
        out.append((p0.x + math.cos(a) * w / 2, p0.y + math.sin(a) * w / 2))
    return out


def band(c, r, a0, a1, w, n=40):
    """Curved corridor: an arc band of radius r from angle a0 to a1 (degrees), w wide."""
    out = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        out.append((c[0] + (r + w / 2) * math.cos(a), c[1] + (r + w / 2) * math.sin(a)))
    for k in range(n, -1, -1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        out.append((c[0] + (r - w / 2) * math.cos(a), c[1] + (r - w / 2) * math.sin(a)))
    return out


def inside(p, poly):
    x, y = p[0], p[1]
    c = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _prism(outline, z0, z1, name='prism'):
    n = len(outline)
    area2 = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
    if area2 < 0:
        outline = outline[::-1]
    verts = [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def _boolean(a, b, op='DIFFERENCE'):
    mod = a.modifiers.new('b', 'BOOLEAN')
    mod.operation = op
    mod.solver = 'EXACT'
    mod.object = b
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(b, do_unlink=True)
    return a


def deck_walls(hull, rooms, H, z0=0.0, side='wall', top='cut'):
    """Solid slab over the hull outline (z0..H) minus every room outline: what is left is wall with a
    flat top. Registers the sides and tops as forge parts and returns the rim loops at height H:
    a list of loops, each a list of (point, normal) with the normal pointing into open space."""
    slab = _prism(hull, z0, H, 'walls')
    for r in rooms:
        _boolean(slab, _prism(r, z0 - 1.0, H + 1.0, 'cut'))
    bm = bmesh.new()
    bm.from_mesh(slab.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.normal_update()
    verts = [tuple(v.co) for v in bm.verts]
    tops = [[v.index for v in f.verts] for f in bm.faces if f.normal.z > 0.5]
    sides = [[v.index for v in f.verts] for f in bm.faces if abs(f.normal.z) <= 0.5]
    # rim: edges at z=H between a top face and a side face
    nxt = {}
    for e in bm.edges:
        if len(e.link_faces) != 2 or abs(e.verts[0].co.z - H) > 1e-3 or abs(e.verts[1].co.z - H) > 1e-3:
            continue
        fa, fb = e.link_faces
        if (fa.normal.z > 0.5) == (fb.normal.z > 0.5):
            continue
        sf = fa if abs(fa.normal.z) <= 0.5 else fb
        nrm = Vector((sf.normal.x, sf.normal.y, 0)).normalized()
        a, b = e.verts
        # orient the edge so the open side is on the left of travel
        d = (b.co - a.co)
        if Vector((0, 0, 1)).cross(d).dot(nrm) < 0:
            a, b = b, a
        nxt[a.index] = (b.index, nrm)
    loops = []
    seen = set()
    for start in list(nxt):
        if start in seen:
            continue
        loop = []
        i = start
        while i in nxt and i not in seen:
            seen.add(i)
            j, nrm = nxt[i]
            loop.append((Vector(verts[i]), nrm))
            i = j
        if len(loop) > 3:
            # smooth normals over neighbours
            n = len(loop)
            loop = [(loop[k][0], (loop[k][1] + loop[k - 1][1]).normalized() if (loop[k][1] + loop[k - 1][1]).length > 1e-6
                     else loop[k][1]) for k in range(n)]
            loops.append(loop)
    bm.free()
    bpy.data.objects.remove(slab, do_unlink=True)
    F._new(verts, sides, side, merge=False, recalc=False, sharp=30)
    F._new(verts, tops, top, merge=False, recalc=False, sharp=30)
    return loops


def slab(outline, holes, z0, z1, zone):
    """Floor slab over an outline with holes (wells open to space) cut through it."""
    o = _prism(outline, z0, z1, 'slab')
    for h in holes:
        _boolean(o, _prism(h, z0 - 1.0, z1 + 1.0, 'cut'))
    verts = [tuple(v.co) for v in o.data.vertices]
    faces = [list(p.vertices) for p in o.data.polygons]
    bpy.data.objects.remove(o, do_unlink=True)
    return F._new(verts, faces, zone, merge=False, recalc=False, sharp=30)


def resample(loop, step):
    """Even spacing along a closed (point, normal) loop."""
    n = len(loop)
    out = []
    carry = 0.0
    for i in range(n):
        a, na = loop[i]
        b, nb = loop[(i + 1) % n]
        L = (b - a).length
        t = carry
        while t < L:
            s = t / L
            out.append((a.lerp(b, s), (na.lerp(nb, s)).normalized()))
            t += step
        carry = t - L
    return out


def offset(loop, d, dz=0.0):
    """Points of a loop pushed d along the normals (into open space) and lifted dz."""
    return [p + nrm * d + Vector((0, 0, dz)) for p, nrm in loop]


def strip(pts, w, h, zone, closed=True, sides=4, power=1.0):
    """Trim / inlay band along a path (w across, h tall)."""
    pts = [tuple(p) for p in pts]
    if closed:
        pts = pts + pts[:2]
    return F.sweep(pts, [(w, h)] * len(pts), zone, sides=sides, caps=not closed, power=power)


def ring_flat(c, r, w, h, zone, n=96, a0=0.0, a1=360.0):
    """Flat ring / arc lying on the floor at c."""
    full = abs(a1 - a0) >= 359.9
    k = n if full else n + 1
    pts = [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
            c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)), c[2]) for i in range(k)]
    return strip(pts, w, h, zone, closed=full)


def ticks(c, r0, r1, count, w, h, zone, a0=0.0, a1=360.0, m=None, every=0, long=0.0):
    """Radial tick marks between radii r0 and r1 round c in the XY plane (one mesh). every/long make
    each every-th tick longer. m: optional matrix applied afterwards (to stand the dial upright)."""
    verts, faces = [], []
    for k in range(count):
        a = math.radians(a0 + (a1 - a0) * k / count)
        ca, sa = math.cos(a), math.sin(a)
        rr = r1 + (long if every and k % every == 0 else 0.0)
        ww = w * (1.6 if every and k % every == 0 else 1.0)
        b = len(verts)
        for r in (r0, rr):
            for s in (-1, 1):
                for z in (-h / 2, h / 2):
                    verts.append((c[0] + r * ca - s * ww / 2 * sa, c[1] + r * sa + s * ww / 2 * ca, c[2] + z))
        faces += [[b, b + 1, b + 3, b + 2], [b + 4, b + 6, b + 7, b + 5], [b, b + 4, b + 5, b + 1],
                  [b + 2, b + 3, b + 7, b + 6], [b, b + 2, b + 6, b + 4], [b + 1, b + 5, b + 7, b + 3]]
    o = F._new(verts, faces, zone, merge=False)
    if m is not None:
        F.xf(o, m)
    return o


def frame(c, axis, up=(0, 0, 1)):
    """Matrix taking the XY plane to the plane through c perpendicular to axis (local Z -> axis)."""
    z = Vector(axis).normalized()
    x = Vector(up).cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(c)
    return m


def aperture(c, axis, r, sq=(1.0, 1.0), membrane=True, rings=3, zone_hot='white', seed=1, bolts=6, scale_ticks=1.0):
    """Arcadian force aperture: a hot hair-thin lip, exact instrument rings with tick marks floating
    round it, and a dark near-clear membrane. Lies in the plane through c perpendicular to axis;
    sq squashes it into an ellipse (width, height)."""
    rnd = random.Random(seed)
    m = frame(c, axis) @ Matrix.Diagonal((sq[0], sq[1], 1.0, 1.0))
    mk = F.mark()
    # lip: thin hot ring + a gold metal carrier just outside it
    ring_flat((0, 0, 0), r, r * 0.012, r * 0.012, zone_hot, n=160)
    ring_flat((0, 0, 0), r * 1.035, r * 0.03, r * 0.05, 'inlay', n=160)
    ticks((0, 0, 0), r * 1.06, r * 1.09, int(180 * scale_ticks), r * 0.006, r * 0.01, 'line', every=15, long=r * 0.035)
    if rings >= 2:
        ring_flat((0, 0, 0), r * 1.2, r * 0.006, r * 0.006, 'line', n=160)
        ticks((0, 0, 0), r * 1.2, r * 1.225, int(72 * scale_ticks), r * 0.008, r * 0.008, 'line', every=6, long=r * 0.04)
    if rings >= 3:
        for k in range(4):                                   # broken outer ring: four floating arcs
            ring_flat((0, 0, 0), r * 1.36, r * 0.022, r * 0.03, 'pale', n=30, a0=k * 90 + 12, a1=k * 90 + 78)
            ring_flat((0, 0, 0), r * 1.385, r * 0.004, r * 0.004, 'line', n=30, a0=k * 90 + 14, a1=k * 90 + 76)
        ticks((0, 0, 0), r * 1.4, r * 1.43, int(240 * scale_ticks), r * 0.004, r * 0.006, 'soft', every=10, long=r * 0.03)
    for o in F.since(mk):
        F.xf(o, m)
    pts = []
    for k in range(bolts):                                    # small arcs crawling round the lip
        a = rnd.uniform(0, 2 * math.pi)
        b = a + rnd.uniform(0.25, 0.6) * rnd.choice((-1, 1))
        p0 = m @ Vector((r * 1.04 * math.cos(a), r * 1.04 * math.sin(a), 0))
        p1 = m @ Vector((r * rnd.choice((1.2, 1.36)) * math.cos(b), r * 1.3 * math.sin(b), 0))
        A.bolt(p0, p1, rnd, width=r * 0.016, jag=0.22, depth=5, branches=1, zone='thin')
        pts.append(p0)
    if membrane:
        verts = [(0, 0, 0)] + [(math.cos(2 * math.pi * k / 128), math.sin(2 * math.pi * k / 128), 0) for k in range(128)]
        faces = [[0, 1 + k, 1 + (k + 1) % 128] for k in range(128)]
        me = bpy.data.meshes.new('membrane')
        me.from_pydata(verts, [], faces)
        o = bpy.data.objects.new('membrane', me)
        bpy.context.scene.collection.objects.link(o)
        # unit disc scaled by the object matrix: the shader draws its rings on |object co| (0..1)
        o.matrix_world = frame(c, axis) @ Matrix.Diagonal((sq[0] * r, sq[1] * r, r, 1.0))
        o.data.materials.append(F.ST['mats']['field'])
        o.visible_shadow = False
        return o
    return None


# ------------------------------------------------------------------ props
def unit(name, loc, yaw=0.0, scale=1.0, pitch=0.0, roll=0.0):
    """Import a game unit (.glb under public/assets/models/alien) and place it. Returns its objects."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(REPO, 'public', 'assets', 'models', 'alien', name + '.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    piv = bpy.data.objects.new('unit_' + name, None)
    bpy.context.scene.collection.objects.link(piv)
    for r in roots:
        r.parent = piv
    piv.location = loc
    piv.rotation_euler = (math.radians(roll), math.radians(pitch), math.radians(yaw))
    piv.scale = (scale,) * 3
    for o in new:
        if o.type == 'MESH':
            for mt in o.data.materials:      # the baked game emissive is tuned for the game: lift it
                if mt and mt.use_nodes:
                    b = mt.node_tree.nodes.get('Principled BSDF')
                    if b and b.inputs['Emission Strength'].is_linked is False:
                        b.inputs['Emission Strength'].default_value = max(b.inputs['Emission Strength'].default_value, 1.0) * 3.0
    return new


def pedestal_core(c, r, rings=3, bowl=True):
    """Glowing core orb hovering over a bowl, in floating gyroscope rings (generators, consoles)."""
    c = Vector(c)
    A.gyro_core(c, r, rings=rings)
    if bowl:
        F.lathe([(r * 0.25, -r * 2.4), (r * 0.9, -r * 2.3), (r * 1.25, -r * 1.75), (r * 1.05, -r * 1.55), (r * 0.5, -r * 1.7),
                 (r * 0.01, -r * 1.75)], 32, 'bronze', center=tuple(c), caps=False)
        ring_flat((c.x, c.y, c.z - r * 1.62), r * 1.12, r * 0.05, r * 0.05, 'line', n=48)
    return c


def petals(c, n, r, h, zone='silver', lean=0.5, chord=None, thick=None, start=0.0, out=1.0):
    """Ring of crescent blades standing round c, tips curling inward (lean>0) - the floating-petal motif."""
    for k in range(n):
        a = math.radians(start + 360.0 * k / n)
        d = Vector((math.cos(a), math.sin(a), 0))
        A.blade(Vector(c) + d * r, Vector((0, 0, 1)) + d * 0.25 * out, -d, h, chord or h * 0.3, thick or h * 0.035, zone,
                lean=lean)


def fin(root, out, back, h, chord, zone='silver', thick=None, lean=0.4, curve=2.0, rib='inlay'):
    """Broad flat crescent blade (wide chord, thin section) with a raised gold midrib inlay."""
    thick = thick or max(0.12, chord * 0.05)
    A.blade(root, out, back, h, chord, thick, zone, lean=lean, curve=curve, n=14)
    if rib:
        A.blade(root, out, back, h * 0.97, chord * 0.06, thick * 1.5, rib, lean=lean, curve=curve, n=14)


def arc_band(pts, chord, thick, zone, up, edge=True, taper=0.75):
    """Floating flat arc along pts: broad across `up`, thin the other way, tapering to both ends,
    with glowing gold hairlines along both edges."""
    n = len(pts)
    upv = Vector(up).normalized()
    sect = [(thick, chord * max(0.1, max(0.0, math.sin(math.pi * (0.08 + 0.92 * k / (n - 1)) if taper else 1.0)) ** taper)) for k in range(n)]
    F.sweep([tuple(p) for p in pts], sect, zone, sides=6, up=tuple(upv), power=0.6)
    if edge:
        for s in (-1, 1):
            F.sweep([tuple(Vector(p) + upv * s * sect[k][1] * 0.97) for k, p in enumerate(pts)], [(thick * 1.3, 0.05)] * n, 'line', sides=4,
                    up=tuple(upv))


def core(c, r, rings=2, light=1.0, tilt=0.0):
    """A clean hovering orb with a few floating rings; it is recorded so light_orbs() can make it
    light its surroundings."""
    c = Vector(c)
    F.orb(tuple(c), r, 'core', seg=(40, 24))
    F.orb(tuple(c), r * 0.5, 'hot', seg=(24, 16))
    tl = [(8, 0), (62, 20), (-48, 70)]
    for k in range(rings):
        m = Matrix.Translation(c) @ Matrix.Rotation(math.radians(tl[k % 3][1] + tilt), 4, 'Z') @ Matrix.Rotation(math.radians(tl[k % 3][0]), 4, 'X')
        mk = F.mark()
        rr = r * (1.5 + 0.38 * k)
        ring_flat((0, 0, 0), rr, r * 0.22, r * 0.05, 'pale' if k != 1 else 'silver', n=96)
        ring_flat((0, 0, r * 0.035), rr, r * 0.02, r * 0.02, 'line', n=96)
        for o in F.since(mk):
            F.xf(o, m)
    ST['orbs'].append((c, r, light))
    return c


def orb(c, r, light=1.0):
    F.orb(tuple(c), r, 'core', seg=(20, 12))
    F.orb(tuple(c), r * 0.5, 'hot', seg=(14, 8))
    ST['orbs'].append((Vector(c), r, light))


def light_orbs(k=1.0, col=(1.0, 0.78, 0.42)):
    for c, r, light in ST['orbs']:
        if light > 0:
            point(c, 900.0 * r * r * light * k, col=col, r=r * 0.9)


def smooth_loop(loop, step=0.7, it=3):
    """Resample a wall loop evenly and round its corners (so trims have no mitre gaps)."""
    lp = resample(loop, step)
    for _ in range(it):
        out = []
        n = len(lp)
        for i in range(n):
            (a, na), (b, nb) = lp[i], lp[(i + 1) % n]
            out.append((a.lerp(b, 0.25), na.lerp(nb, 0.25).normalized()))
            out.append((a.lerp(b, 0.75), na.lerp(nb, 0.75).normalized()))
        lp = out
    return lp[::4] if it >= 3 else lp[::2]


def swoosh(c, r0, r1, a0, a1, w, zone='inlay', z=0.04, n=28, h=0.05):
    """Flowing inlay stroke on the floor: a spiral arc from (r0, a0) to (r1, a1), tapered at both ends."""
    pts, sect = [], []
    for k in range(n + 1):
        t = k / n
        a = math.radians(a0 + (a1 - a0) * t)
        r = r0 + (r1 - r0) * t ** 1.3
        pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a), z))
        sect.append((w * max(0.08, math.sin(math.pi * t) ** 0.6), h))
    return F.sweep(pts, sect, zone, sides=4)


def flow_pad(c, r, style=0, z=0.04):
    """Floor pad drawn with flowing engraved strokes (no tick marks): a thin ring and a pinwheel of
    nested spiral swooshes; style varies the count, the handedness and the sweep."""
    n = (3, 4, 2, 5)[style % 4]
    hand = 1 if style % 2 == 0 else -1
    turn = (150, 110, 210, 95)[style % 4]
    ring_flat((c[0], c[1], z), r, 0.16, 0.05, 'inlay', n=72)
    ring_flat((c[0], c[1], z + 0.01), r - 0.35, 0.05, 0.04, 'line', n=72)
    for k in range(n):
        a = 360.0 * k / n + 20 * style
        swoosh(c, r * 0.2, r * 0.86, a, a + hand * turn, r * 0.11, 'inlay', z)
        swoosh(c, r * 0.3, r * 0.8, a + hand * 14, a + hand * (turn - 18), r * 0.022, 'line', z + 0.02)
        swoosh(c, r * 1.12, r * 1.5, a + hand * 40, a + hand * (turn * 0.55 + 40), r * 0.05, 'inlay', z)
    F.orb((c[0], c[1], 0.0), r * 0.16, 'soft', seg=(16, 8), sq=(1, 1, 0.08))


# ------------------------------------------------------------------ render + post
def bloom(im, amount=1.0, thr=0.84):
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255.0
    lum = a.max(axis=2, keepdims=True)
    bright = np.clip((lum - thr) / (1.0 - thr), 0, 1) * a
    b = Image.fromarray((bright * 255).astype(np.uint8))
    k = im.size[0] / 1280.0
    acc = np.zeros_like(a)
    for r, wgt in ((2.0, 0.45), (7, 0.35), (22, 0.28), (60, 0.16)):
        g = np.asarray(b.filter(ImageFilter.GaussianBlur(r * k))).astype(np.float32) / 255.0
        acc += g * wgt * np.array([1.0, 0.88, 0.6], dtype=np.float32)
    o = 1.0 - (1.0 - a) * (1.0 - np.clip(acc * amount, 0, 1))
    return Image.fromarray((np.clip(o, 0, 1) * 255).astype(np.uint8))


def grade(im, vignette=0.25, contrast=1.06, lift=0.0):
    a = np.asarray(im).astype(np.float32) / 255.0
    a = np.clip((a - 0.5) * contrast + 0.5 + lift, 0, 1)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
    a *= (1.0 - vignette * d ** 2.2)[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def render(path, bloom_amt=1.0, vignette=0.25, thr=0.84, quality=92, contrast=1.06):
    sc = bpy.context.scene
    png = os.path.splitext(path)[0] + '_raw.png'
    sc.render.filepath = png
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    im = Image.open(png).convert('RGB')
    im = grade(bloom(im, bloom_amt, thr), vignette, contrast)
    im.save(path, quality=quality)
    print('WROTE', path, flush=True)
    return path


def args():
    return dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
