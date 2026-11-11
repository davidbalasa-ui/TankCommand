"""Hero-quality pipeline: kit geometry + procedural surface shaders baked into one 512 texture set.

The kit builds the shape (front +X, up +Z) and tags every part with its zone (the kit "tile":
hull, turret, glow, amber, dark, shell, fin, core ...). Here each zone gets a procedural shader
working in object space: panel seams, etching, bevelled-edge shading, edge wear and glowing veins.
Everything is then baked into a fresh non-overlapping UV layout:
  base colour (lighting-free, with ambient occlusion multiplied in), tangent-space normal map
  (bump + bevel shading, so flat plates read as machined panels), roughness/metal (glTF ORM layout)
  and emission. The final model has one material with four 512 maps.

Usage from a unit script:
    import hero
    hero.begin('terran')            # instead of kit.begin
    parts = [kit.box(...), ...]
    hero.finish('out.glb', 'Falcon', parts, budget=(2300, 2500), bake_dir=..., size=512)
"""
import math
import os

import bpy
import numpy as np

import kit

ZONES = {
    'terran': {
        'hull': dict(kind='panel', base=(0.045, 0.05, 0.058), rough=0.42, metal=0.75, seam=1.7, wear=0.10),
        'turret': dict(kind='panel', base=(0.07, 0.075, 0.085), rough=0.38, metal=0.8, seam=2.6, wear=0.14),
        'track': dict(kind='panel', base=(0.03, 0.032, 0.036), rough=0.6, metal=0.6, seam=3.5, wear=0.05),
        'barrel': dict(kind='panel', base=(0.09, 0.095, 0.1), rough=0.3, metal=0.9, seam=6.0, wear=0.25),
        'dark': dict(kind='panel', base=(0.018, 0.02, 0.024), rough=0.55, metal=0.5, seam=4.0, wear=0.04),
        'glow': dict(kind='glow', base=(0.05, 0.25, 0.3), emit=(0.25, 0.9, 1.0), strength=6.0),
        'amber': dict(kind='glow', base=(0.3, 0.12, 0.02), emit=(1.0, 0.42, 0.08), strength=5.0),
        'canopy': dict(kind='canopy', base=(0.02, 0.06, 0.08), emit=(0.15, 0.6, 0.85), strength=1.6),
    },
    'kesh': {
        'shell': dict(kind='etched', base=(0.62, 0.5, 0.36), rough=0.28, metal=0.95, veins=0.35),
        'fin': dict(kind='etched', base=(0.5, 0.36, 0.22), rough=0.3, metal=0.95, veins=0.55),
        'under': dict(kind='etched', base=(0.2, 0.15, 0.11), rough=0.45, metal=0.85, veins=0.2),
        'barrel': dict(kind='etched', base=(0.7, 0.58, 0.4), rough=0.22, metal=1.0, veins=0.0),
        'dark': dict(kind='etched', base=(0.08, 0.06, 0.05), rough=0.4, metal=0.8, veins=0.6),
        'glow': dict(kind='glow', base=(0.4, 0.28, 0.05), emit=(1.0, 0.72, 0.18), strength=6.0),
        'core': dict(kind='orb', base=(0.5, 0.35, 0.05), emit=(1.0, 0.78, 0.3), strength=7.0),
    },
}

H = {}


def begin(faction):
    """Start a scene. The kit still needs an atlas material to hang the parts on; we replace it."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = bpy.data.materials.new('placeholder')
    mat.use_nodes = True
    cfg = kit.FACTIONS[faction]
    kit.S.clear()
    kit.S.update(scene=bpy.context.scene, mat=mat, tiles=cfg['tiles'] | {'canopy': (0, 0, 1, 1)},
                 faction=faction, cfg=cfg, nodes=[])
    H.clear()
    H.update(faction=faction, zone_mats={})
    # Remember each part's zone: wrap the kit's linker once.
    if not getattr(kit, '_hero_wrapped', False):
        original = kit._link

        def tagged(name, me, tile, smooth):
            obj = original(name, me, tile, smooth)
            obj['zone'] = tile
            return obj
        kit._link = tagged
        kit._hero_wrapped = True


# ---------------------------------------------------------------- procedural zone shaders
def _n(nt, kind, loc, **inputs):
    node = nt.nodes.new(kind)
    node.location = loc
    for key, value in inputs.items():
        node.inputs[key].default_value = value
    return node


def _math(nt, op, a, b=None, loc=(0, 0), clamp=False):
    node = nt.nodes.new('ShaderNodeMath')
    node.operation = op
    node.location = loc
    node.use_clamp = clamp
    for i, src in enumerate((a, b)):
        if src is None:
            continue
        if isinstance(src, (int, float)):
            node.inputs[i].default_value = src
        else:
            nt.links.new(src, node.inputs[i])
    return node.outputs[0]


def _seams(nt, coord, scale):
    """Panel seams: thin lines of a staggered grid in object space on all three axes (0..1 mask)."""
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord, sep.inputs[0])
    masks = []
    for i, k in enumerate((scale, scale * 1.37, scale * 0.83)):
        c = _math(nt, 'MULTIPLY', sep.outputs[i], k)
        if i == 1:  # stagger
            c = _math(nt, 'ADD', c, _math(nt, 'MULTIPLY', _math(nt, 'FLOOR', _math(nt, 'MULTIPLY', sep.outputs[0], scale)), 0.5))
        f = _math(nt, 'FRACT', c)
        d = _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', f, 0.5))
        masks.append(_math(nt, 'GREATER_THAN', d, 0.475))
    m = _math(nt, 'MAXIMUM', masks[0], masks[1])
    return _math(nt, 'MAXIMUM', m, masks[2])


def _edge_wear(nt):
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.52
    ramp.color_ramp.elements[1].position = 0.6
    nt.links.new(geo.outputs['Pointiness'], ramp.inputs[0])
    return ramp.outputs[0]


def zone_material(zone):
    key = zone if zone in ZONES[H['faction']] else ('hull' if H['faction'] == 'terran' else 'shell')
    if key in H['zone_mats']:
        return H['zone_mats'][key]
    z = ZONES[H['faction']][key]
    mat = bpy.data.materials.new(f'zone_{key}')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    coord = tc.outputs['Object']
    bevel = _n(nt, 'ShaderNodeBevel', (-200, -500), Radius=0.035)
    bevel.samples = 6
    bump = _n(nt, 'ShaderNodeBump', (0, -400), Strength=0.6, Distance=0.02)
    nt.links.new(bevel.outputs[0], bump.inputs['Normal'])
    nt.links.new(bump.outputs[0], bsdf.inputs['Normal'])
    noise = _n(nt, 'ShaderNodeTexNoise', (-600, 200), Scale=6.0, Detail=6.0)
    nt.links.new(coord, noise.inputs['Vector'])
    if z['kind'] == 'panel':
        seams = _seams(nt, coord, z['seam'])
        # Height: seams cut in, fine noise for cast/brushed texture.
        height = _math(nt, 'SUBTRACT', _math(nt, 'MULTIPLY', noise.outputs['Fac'], 0.15), seams)
        nt.links.new(height, bump.inputs['Height'])
        wear = _edge_wear(nt)
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
        mix.inputs['A'].default_value = (*z['base'], 1)
        mix.inputs['B'].default_value = (z['base'][0] * 4 + 0.08, z['base'][1] * 4 + 0.08, z['base'][2] * 4 + 0.09, 1)
        nt.links.new(_math(nt, 'MULTIPLY', wear, z['wear'] * 6, clamp=True), mix.inputs['Factor'])
        dark = nt.nodes.new('ShaderNodeMix'); dark.data_type = 'RGBA'
        nt.links.new(mix.outputs['Result'], dark.inputs['A'])
        dark.inputs['B'].default_value = (0.004, 0.004, 0.005, 1)
        nt.links.new(seams, dark.inputs['Factor'])
        nt.links.new(dark.outputs['Result'], bsdf.inputs['Base Color'])
        rough = _math(nt, 'ADD', _math(nt, 'MULTIPLY', noise.outputs['Fac'], 0.25), z['rough'] - 0.12)
        nt.links.new(rough, bsdf.inputs['Roughness'])
        bsdf.inputs['Metallic'].default_value = z['metal']
    elif z['kind'] == 'etched':
        etch = _n(nt, 'ShaderNodeTexVoronoi', (-600, 0), Scale=5.5)
        etch.feature = 'DISTANCE_TO_EDGE'
        nt.links.new(coord, etch.inputs['Vector'])
        lines = _math(nt, 'LESS_THAN', etch.outputs['Distance'], 0.025)
        vein = _n(nt, 'ShaderNodeTexVoronoi', (-600, -200), Scale=2.2)
        vein.feature = 'DISTANCE_TO_EDGE'
        nt.links.new(coord, vein.inputs['Vector'])
        vmask = _math(nt, 'LESS_THAN', vein.outputs['Distance'], 0.03)
        vsel = _math(nt, 'GREATER_THAN', noise.outputs['Fac'], 1.0 - z['veins'] * 0.9)
        veins = _math(nt, 'MULTIPLY', vmask, vsel)
        height = _math(nt, 'SUBTRACT', _math(nt, 'MULTIPLY', noise.outputs['Fac'], 0.1),
                       _math(nt, 'MAXIMUM', lines, veins))
        nt.links.new(height, bump.inputs['Height'])
        col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'
        col.inputs['A'].default_value = (*z['base'], 1)
        col.inputs['B'].default_value = (z['base'][0] * 0.35, z['base'][1] * 0.3, z['base'][2] * 0.28, 1)
        nt.links.new(lines, col.inputs['Factor'])
        tint = nt.nodes.new('ShaderNodeMix'); tint.data_type = 'RGBA'
        nt.links.new(col.outputs['Result'], tint.inputs['A'])
        tint.inputs['B'].default_value = (z['base'][0] * 1.25, z['base'][1] * 1.1, z['base'][2] * 0.85, 1)
        nt.links.new(noise.outputs['Fac'], tint.inputs['Factor'])
        nt.links.new(tint.outputs['Result'], bsdf.inputs['Base Color'])
        bsdf.inputs['Metallic'].default_value = z['metal']
        nt.links.new(_math(nt, 'ADD', _math(nt, 'MULTIPLY', noise.outputs['Fac'], 0.2), z['rough'] - 0.1),
                     bsdf.inputs['Roughness'])
        bsdf.inputs['Emission Color'].default_value = (1.0, 0.7, 0.18, 1)
        nt.links.new(_math(nt, 'MULTIPLY', veins, 5.0), bsdf.inputs['Emission Strength'])
    else:  # glow / orb / canopy
        bsdf.inputs['Base Color'].default_value = (*z['base'], 1)
        bsdf.inputs['Emission Color'].default_value = (*z['emit'], 1)
        bsdf.inputs['Roughness'].default_value = 0.25 if z['kind'] != 'canopy' else 0.08
        bsdf.inputs['Metallic'].default_value = 0.0
        if z['kind'] == 'canopy':
            # Glass: dark with a bright band along the top.
            sep = nt.nodes.new('ShaderNodeSeparateXYZ')
            nt.links.new(tc.outputs['Generated'], sep.inputs[0])
            band = _math(nt, 'POWER', sep.outputs[2], 3.0)
            nt.links.new(_math(nt, 'MULTIPLY', band, z['strength'] * 2), bsdf.inputs['Emission Strength'])
        elif z['kind'] == 'orb':
            lw = nt.nodes.new('ShaderNodeLayerWeight')
            lw.inputs['Blend'].default_value = 0.35
            core = _math(nt, 'SUBTRACT', 1.0, lw.outputs['Facing'])
            nt.links.new(_math(nt, 'ADD', _math(nt, 'MULTIPLY', core, z['strength']), 1.5),
                         bsdf.inputs['Emission Strength'])
        else:
            # Light strips: brighter in the middle of each strip, with faint segmenting.
            seg = _math(nt, 'GREATER_THAN', _math(nt, 'FRACT', _math(nt, 'MULTIPLY', noise.outputs['Fac'], 9.0)), 0.12)
            nt.links.new(_math(nt, 'MULTIPLY', seg, z['strength']), bsdf.inputs['Emission Strength'])
    H['zone_mats'][key] = mat
    return mat


# ---------------------------------------------------------------- bake
def _unwrap(obj):
    me = obj.data
    while len(me.uv_layers) > 0:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name='UVMap')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.006, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


def _target(obj, image):
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        node = nt.nodes.get('BakeTarget') or nt.nodes.new('ShaderNodeTexImage')
        node.name = 'BakeTarget'
        node.image = image
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node


def _bake(obj, kind, size, margin=6, **kw):
    img = bpy.data.images.new(f'bake_{kind}', size, size, alpha=False, float_buffer=True)
    if kind == 'NORMAL':
        img.colorspace_settings.name = 'Non-Color'
    _target(obj, img)
    bpy.ops.object.bake(type=kind, margin=margin, use_clear=True, **kw)
    return np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)


def _metal_emit_swap(obj, on):
    """Temporarily route Metallic into emission so it can be baked with an EMIT pass."""
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        bsdf = nt.nodes['Principled BSDF']
        if on:
            for link in list(nt.links):
                if link.to_socket in (bsdf.inputs['Emission Color'], bsdf.inputs['Emission Strength']):
                    nt.links.remove(link)
            m = bsdf.inputs['Metallic'].default_value
            bsdf.inputs['Emission Color'].default_value = (m, m, m, 1)
            bsdf.inputs['Emission Strength'].default_value = 1.0


def _save(arr, path, srgb):
    size = arr.shape[0]
    img = bpy.data.images.new(os.path.basename(path), size, size, alpha=False)
    img.pixels = np.clip(arr, 0, 1).ravel().tolist()
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


def bake_unit(name, parts, out_glb, bake_dir, size=512, samples=24):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    # Zone materials.
    for obj in parts:
        obj.data.materials.clear()
        obj.data.materials.append(zone_material(obj.get('zone', 'hull')))
    obj = kit.join(parts, name)
    _unwrap(obj)
    os.makedirs(bake_dir, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    # Need a world for AO.
    if scene.world is None:
        scene.world = bpy.data.worlds.new('w')
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    diffuse = _bake(obj, 'DIFFUSE', size, pass_filter={'COLOR'})
    scene.cycles.samples = 64
    ao = _bake(obj, 'AO', size)
    scene.cycles.samples = samples
    rough = _bake(obj, 'ROUGHNESS', size)
    normal = _bake(obj, 'NORMAL', size, normal_space='TANGENT')
    emit = _bake(obj, 'EMIT', size)
    # Metallic: bake via emission after swapping the zone materials' emission inputs.
    _metal_emit_swap(obj, True)
    metal = _bake(obj, 'EMIT', size)
    a = np.clip(0.35 + 0.65 * ao[..., :3], 0, 1)
    base = diffuse[..., :3] * a
    # Diffuse bake returns linear values; store sRGB.
    base_srgb = np.where(base <= 0.0031308, base * 12.92, 1.055 * np.power(np.clip(base, 0, 1), 1 / 2.4) - 0.055)
    em = np.clip(emit[..., :3] / 6.0, 0, 1)  # 6 = emission strength we restore in the material
    em_srgb = np.where(em <= 0.0031308, em * 12.92, 1.055 * np.power(em, 1 / 2.4) - 0.055)
    orm = np.stack([ao[..., 0], rough[..., 0], metal[..., 0]], axis=-1)

    def rgba(x):
        return np.concatenate([x, np.ones(x.shape[:2] + (1,), np.float32)], axis=-1)
    stem = os.path.join(bake_dir, name.lower())
    i_base = _save(rgba(base_srgb), f'{stem}_base.png', True)
    i_norm = _save(normal, f'{stem}_normal.png', False)
    i_orm = _save(rgba(orm), f'{stem}_orm.png', False)
    i_emit = _save(rgba(em_srgb), f'{stem}_emissive.png', True)

    # Final single material.
    mat = bpy.data.materials.new(f'{name}Mat')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = i_base
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = i_norm
    to = nt.nodes.new('ShaderNodeTexImage'); to.image = i_orm
    te = nt.nodes.new('ShaderNodeTexImage'); te.image = i_emit
    nm = nt.nodes.new('ShaderNodeNormalMap')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tb.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(to.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
    nt.links.new(te.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 6.0
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def export(obj, out_glb):
    for o in bpy.context.view_layer.objects:
        o.select_set(o == obj)
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', use_selection=True,
                              export_yup=True, export_image_format='WEBP' if False else 'AUTO')
