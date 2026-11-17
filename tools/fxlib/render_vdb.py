"""Render a folder of VDB frames (from smokesim.py) to RGBA PNG flipbook frames.

Usage: python render_vdb.py config.json
config keys:
  vdb_dir, out_dir, frames [first,last], res (px), samples,
  domain [x,y,z] metres (sim domain size), view_center [x,z], view_size (metres, ortho),
  elev (deg camera elevation), style {...} see STYLE below.
"""
import bpy, json, math, os, sys
from mathutils import Vector

STYLE = dict(
    smoke_color=(0.8, 0.77, 0.73),   # albedo of soot (grey, slightly warm)
    smoke_density=3.0,                # multiplier on the density grid
    detail=0.35,                      # noise modulation of density (upres look)
    detail_scale=6.0,
    fire_strength=7.0,               # emission strength at heat=1
    flame_boost=2.5,                 # extra emission from active burning
    heat_lo=0.6, heat_hi=2.0,        # heat -> ramp position
    # fire ramp: dark red -> orange -> yellow -> near white (no purple ever)
    ramp=[(0.0, (0.0, 0.0, 0.0)), (0.1, (0.4, 0.04, 0.0)), (0.35, (1.0, 0.2, 0.01)),
          (0.7, (1.0, 0.4, 0.03)), (1.0, (1.0, 0.56, 0.1))],
    sun=3.5, sun_rot=(50, 0, 35), world=0.8, world_color=(0.7, 0.68, 0.64),
    inner_light=0.0,                  # point light inside fireball (W per unit flame)
    dust=False,
)


def build_scene(cfg):
    st = dict(STYLE); st.update(cfg.get('style', {}))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = cfg.get('samples', 64)
    sc.cycles.use_denoising = True
    sc.cycles.volume_bounces = cfg.get('volume_bounces', 2)
    sc.cycles.transparent_max_bounces = 64
    sc.cycles.volume_step_rate = cfg.get('step_rate', 0.35)
    sc.cycles.volume_max_steps = 512
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = cfg.get('res', 512)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = cfg.get('threads', 4)
    # world
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (*st['world_color'], 1); bg.inputs[1].default_value = st['world']
    # sun
    sd = bpy.data.lights.new('Sun', 'SUN'); sd.energy = st['sun']; sd.angle = math.radians(3)
    so = bpy.data.objects.new('Sun', sd); sc.collection.objects.link(so)
    so.rotation_euler = [math.radians(a) for a in st['sun_rot']]
    # camera (ortho, looking along +y, slight elevation)
    dom = cfg['domain']
    cx, cz = cfg.get('view_center', [dom[0] / 2, dom[2] / 2])
    vs = cfg.get('view_size', dom[2])
    cam = bpy.data.cameras.new('Cam'); cam.type = 'ORTHO'; cam.ortho_scale = vs
    cam.clip_end = 200
    co = bpy.data.objects.new('Cam', cam); sc.collection.objects.link(co); sc.camera = co
    el = math.radians(cfg.get('elev', 12))
    dist = 40
    target = Vector((cx, dom[1] / 2, cz))
    co.location = target + Vector((0, -math.cos(el) * dist, math.sin(el) * dist))
    co.rotation_euler = (math.pi / 2 - el, 0, 0)
    # material
    m = bpy.data.materials.new('FXVol'); m.use_nodes = True
    try:
        m.cycles.volume_interpolation = 'CUBIC'
    except Exception:
        pass
    nt = m.node_tree; N = nt.nodes; Lk = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    pv = N.new('ShaderNodeVolumePrincipled')
    Lk.new(pv.outputs[0], out.inputs['Volume'])
    pv.inputs['Color'].default_value = (*st['smoke_color'], 1)
    pv.inputs['Anisotropy'].default_value = 0.3
    pv.inputs['Blackbody Intensity'].default_value = 0.0
    a_d = N.new('ShaderNodeAttribute'); a_d.attribute_name = 'density'
    a_h = N.new('ShaderNodeAttribute'); a_h.attribute_name = 'heat'
    a_f = N.new('ShaderNodeAttribute'); a_f.attribute_name = 'flame'
    # detail noise on density (fake upres), coordinates in object space
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = st['detail_scale']
    nz.inputs['Detail'].default_value = 6; nz.inputs['Roughness'].default_value = 0.6
    nz.inputs['W'].default_value = cfg.get('_frame', 0) * 0.02
    Lk.new(tc.outputs['Object'], nz.inputs['Vector'])
    det = N.new('ShaderNodeMapRange')
    det.inputs['From Min'].default_value = 0.3; det.inputs['From Max'].default_value = 0.7
    det.inputs['To Min'].default_value = 1 - st['detail']; det.inputs['To Max'].default_value = 1 + st['detail']
    Lk.new(nz.outputs['Fac'], det.inputs['Value'])
    md = N.new('ShaderNodeMath'); md.operation = 'MULTIPLY'
    Lk.new(a_d.outputs['Fac'], md.inputs[0]); Lk.new(det.outputs['Result'], md.inputs[1])
    md2 = N.new('ShaderNodeMath'); md2.operation = 'MULTIPLY'; md2.inputs[1].default_value = st['smoke_density']
    Lk.new(md.outputs[0], md2.inputs[0])
    # fire: ramp over heat (+ flame boost)
    hm = N.new('ShaderNodeMapRange')
    hm.inputs['From Min'].default_value = st['heat_lo']; hm.inputs['From Max'].default_value = st['heat_hi']
    fb = N.new('ShaderNodeMath'); fb.operation = 'MULTIPLY_ADD'
    fb.inputs[1].default_value = 0.25
    Lk.new(a_f.outputs['Fac'], fb.inputs[0]); Lk.new(a_h.outputs['Fac'], fb.inputs[2])
    Lk.new(fb.outputs[0], hm.inputs['Value'])
    ramp = N.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    pts = st['ramp']
    els[0].position = pts[0][0]; els[0].color = (*pts[0][1], 1)
    els[1].position = pts[-1][0]; els[1].color = (*pts[-1][1], 1)
    for p, c in pts[1:-1]:
        e = els.new(p); e.color = (*c, 1)
    Lk.new(hm.outputs['Result'], ramp.inputs['Fac'])
    Lk.new(ramp.outputs['Color'], pv.inputs['Emission Color'])
    es = N.new('ShaderNodeMath'); es.operation = 'MULTIPLY_ADD'
    es.inputs[1].default_value = st['flame_boost']
    Lk.new(a_f.outputs['Fac'], es.inputs[0])
    hs = N.new('ShaderNodeMath'); hs.operation = 'MULTIPLY'; hs.inputs[1].default_value = st['fire_strength']
    # emission ~ heat^2: cooling gas stops glowing quickly instead of tinting the smoke salmon/pink
    hp = N.new('ShaderNodeMath'); hp.operation = 'POWER'; hp.inputs[1].default_value = st.get('heat_power', 2.0)
    Lk.new(hm.outputs['Result'], hp.inputs[0])
    Lk.new(hp.outputs[0], hs.inputs[0])
    Lk.new(hs.outputs[0], es.inputs[2])
    # break the fire up: second noise, high contrast, so flames come in licks and pockets
    nz2 = N.new('ShaderNodeTexNoise'); nz2.noise_dimensions = '4D'
    nz2.inputs['Scale'].default_value = st.get('fire_noise_scale', 3.0)
    nz2.inputs['Detail'].default_value = 4; nz2.inputs['Roughness'].default_value = 0.55
    Lk.new(tc.outputs['Object'], nz2.inputs['Vector'])
    br = N.new('ShaderNodeMapRange')
    br.inputs['From Min'].default_value = 0.35; br.inputs['From Max'].default_value = 0.65
    br.inputs['To Min'].default_value = st.get('fire_breakup_lo', 0.25); br.inputs['To Max'].default_value = st.get('fire_breakup_hi', 1.8)
    Lk.new(nz2.outputs['Fac'], br.inputs['Value'])
    em = N.new('ShaderNodeMath'); em.operation = 'MULTIPLY'
    Lk.new(es.outputs[0], em.inputs[0]); Lk.new(br.outputs['Result'], em.inputs[1])
    # soft clip: x / (1 + x / cap) keeps the hot core from blowing out to flat white
    sc1 = N.new('ShaderNodeMath'); sc1.operation = 'DIVIDE'; sc1.inputs[1].default_value = st.get('emit_cap', 2.5)
    Lk.new(em.outputs[0], sc1.inputs[0])
    sc2 = N.new('ShaderNodeMath'); sc2.operation = 'ADD'; sc2.inputs[1].default_value = 1.0
    Lk.new(sc1.outputs[0], sc2.inputs[0])
    sc3 = N.new('ShaderNodeMath'); sc3.operation = 'DIVIDE'
    Lk.new(em.outputs[0], sc3.inputs[0]); Lk.new(sc2.outputs[0], sc3.inputs[1])
    Lk.new(sc3.outputs[0], pv.inputs['Emission Strength'])
    nz2.name = 'FireNoise'
    # soot near the fire is dark (it is lit from inside by the flames, not by the sun); only cooled smoke is pale grey.
    # Without this, orange emission + sunlit grey soot reads as pastel salmon / cream.
    hf = N.new('ShaderNodeMath'); hf.operation = 'MULTIPLY'; hf.use_clamp = True
    hf.inputs[1].default_value = st.get('hot_soot_gain', 3.0)
    Lk.new(hm.outputs['Result'], hf.inputs[0])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[6].default_value = (*st['smoke_color'], 1)
    mix.inputs[7].default_value = (*st.get('hot_soot', (0.06, 0.045, 0.035)), 1)
    Lk.new(hf.outputs[0], mix.inputs['Factor'])
    Lk.new(mix.outputs[2], pv.inputs['Color'])
    # soot inside the burning core is thin: fire shows saturated instead of a grey wash
    inv = N.new('ShaderNodeMath'); inv.operation = 'MULTIPLY_ADD'
    inv.inputs[1].default_value = -st.get('core_clear', 0.8); inv.inputs[2].default_value = 1.0
    Lk.new(hm.outputs['Result'], inv.inputs[0])
    dd = N.new('ShaderNodeMath'); dd.operation = 'MULTIPLY'; dd.use_clamp = False
    Lk.new(md2.outputs[0], dd.inputs[0]); Lk.new(inv.outputs[0], dd.inputs[1])
    Lk.new(dd.outputs[0], pv.inputs['Density'])
    # inner light
    il = None
    if st['inner_light'] > 0:
        ld = bpy.data.lights.new('Inner', 'POINT'); ld.shadow_soft_size = 0.8
        ld.color = (1.0, 0.45, 0.12)
        il = bpy.data.objects.new('Inner', ld); sc.collection.objects.link(il)
    return sc, m, nz, il, st


def main():
    cfg = json.load(open(sys.argv[1]))
    sc, mat, nz, il, st = build_scene(cfg)
    f0, f1 = cfg['frames']
    os.makedirs(cfg['out_dir'], exist_ok=True)
    stats = {}
    if os.path.exists(os.path.join(cfg['vdb_dir'], 'stats.json')):
        stats = json.load(open(os.path.join(cfg['vdb_dir'], 'stats.json')))
    only = cfg.get('only')
    prev = None
    for f in range(f0, f1 + 1):
        if only and f not in only:
            continue
        outp = os.path.join(cfg['out_dir'], '%04d.png' % (f - f0 + 1))
        if cfg.get('skip_existing') and os.path.exists(outp):
            continue
        p = os.path.join(cfg['vdb_dir'], 'f%04d.vdb' % f)
        vol = bpy.data.volumes.new('V%d' % f)
        vol.filepath = p
        ob = bpy.data.objects.new('FX', vol)
        sc.collection.objects.link(ob)
        ob.data.materials.append(mat)
        vol.render.space = 'WORLD'
        nz.inputs['W'].default_value = f * 0.03
        mat.node_tree.nodes['FireNoise'].inputs['W'].default_value = 3.7 + f * 0.05
        if il is not None:
            s = stats.get(str(f), {})
            il.location = s.get('flame_center', [cfg['domain'][0] / 2, cfg['domain'][1] / 2, 1.0])
            il.data.energy = st['inner_light'] * s.get('flame_sum', 0.0)
        if prev is not None:
            bpy.data.objects.remove(prev[0]); bpy.data.volumes.remove(prev[1])
        prev = (ob, vol)
        sc.render.filepath = outp
        bpy.ops.render.render(write_still=True)
        print('rendered', outp, flush=True)


if __name__ == '__main__':
    main()
