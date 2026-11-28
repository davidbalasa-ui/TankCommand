"""The shared ground battle scene of the opening film (0:38 to 0:55): the crystal valley on Vesper.

One saved layout; each shot is only a camera and a frame range inside it (see film.py).
Valley runs along X. Terran forward base at the west end (x ~ -640), Arcadian seed pods at the east
end (x ~ +700). The armies roll toward each other and stop either side of x = 0, where the ground
splits and the Shard rises.

  0:38  drop ship falls into the valley, landing thrusters, a violet pulse under the crystals
  0:39  it slams onto a pad (dust wall); 0:40 Lancers roll out; more drop ships land
  0:41  seed pods split open into nests, Stingers hover out
  0:42  wide: a few hundred units each side roll; second violet pulse
  0:43  both lines fire; Condors and Dragonflies cross overhead
  0:44  our Lancer charges; 0:45 its neighbour is flipped, it kills a Stinger; 0:46 crystals turn violet
  0:47  the ground splits, tanks brake; 0:48-0:50 the Shard rises and pulses once
  0:51  barrels lift, the Shard glows; 0:52 lightning crusts the Terran line; 0:53 the Arcadians
  0:54  a fan of violet beams goes straight up through the clouds
Everything is keyed on the global clock, fixed seeds only.
"""
import math
import os
import random

import bpy
from mathutils import Vector, Quaternion, Matrix, noise

import space as SP
import common as C
import forge as F
import ships as base
import arcadian_fleet as AF
import new_pieces as NP
from squid import bake, catmull, look_quat, ramp

fr = SP.fr
FPS = SP.FPS
NF = SP.NF
MODELS = os.environ.get('TC_MODELS', '/home/user/scratch/models84/public/assets/models')
if not os.path.isdir(MODELS):
    MODELS = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'public', 'assets', 'models')

VIOLET = (0.45, 0.1, 1.0)
PINK = (1.0, 0.62, 0.8)
CYAN = (0.3, 0.85, 1.0)
GOLD = (1.0, 0.65, 0.18)
DS_K = 2.8          # drop ship scale (its clamped Lancer then matches the game Lancer)
PAD_K = 2.6
POD_K = 3.0
SHARD_K = 5.5

T_DROP, T_LAND, T_ROLL = fr(38.0), fr(39.0) + 5, fr(40.0)
T_PODS, T_WIDE, T_FIRE = fr(41.0), fr(42.0), fr(43.0)
T_CHARGE, T_MEET, T_SPREAD = fr(44.0), fr(45.0), fr(46.0)
T_SPLIT, T_RISE, T_WIDE2, T_PULSE = fr(47.0), fr(48.0), fr(49.0), fr(50.0)
T_GLOW, T_STRIKE_T, T_STRIKE_A, T_BEAMS = fr(51.0), fr(52.0), fr(53.0), fr(54.0)
G_END = fr(55.0)

HERO_Y = 46.0
BASE_X = -640.0


# ================================================================== terrain
def height(x, y):
    """Valley floor ~0, walls rising beyond |y| = 330, gentle noise, pod craters."""
    ay = abs(y)
    w = max(0.0, min(1.0, (ay - 330) / 380.0))
    h = 170.0 * (w * w * (3 - 2 * w))
    h += 3.2 * noise.noise(Vector((x * 0.006, y * 0.006, 0.3))) + 1.2 * noise.noise(Vector((x * 0.03, y * 0.03, 1.7)))
    h += 40.0 * w * noise.noise(Vector((x * 0.004, y * 0.004, 5.0)))
    for px, py in POD_SITES:
        d = math.hypot(x - px, y - py)
        if d < 26:
            h -= 3.5 * (1 - (d / 26) ** 2)
    if x < BASE_X + 170 and ay < 170:                     # the base sits on levelled ground
        k = max(0.0, min(1.0, (BASE_X + 170 - x) / 60.0)) * max(0.0, min(1.0, (170 - ay) / 40.0))
        h *= (1 - k)
    return h


POD_SITES = [(650, -150), (700, -60), (660, 30), (720, 110), (640, 190), (760, -200), (780, 10), (770, 170)]
PADS = [(BASE_X, 40), (BASE_X, -40), (BASE_X - 60, 80), (BASE_X - 60, 0), (BASE_X - 60, -80), (BASE_X - 120, 40),
        (BASE_X - 120, -40)]


def _value(nt, name, v):
    n = nt.nodes.new('ShaderNodeValue')
    n.name = name
    n.outputs[0].default_value = v
    return n.outputs[0]


def _pulse_nodes(m, n):
    """Shared violet-pulse logic: world position, keyed ring radius/strength, keyed spread radius.
    Returns (ring 0..1, spread 0..1) sockets. Value nodes: ringX, ringY, ringR, ringK, sprX, sprY, sprR."""
    nt = m.node_tree
    geo = n.node('ShaderNodeNewGeometry')
    sep = n.node('ShaderNodeSeparateXYZ')
    n.set(sep.inputs[0], geo.outputs['Position'])

    def dist(xn, yn):
        dx = n.math('SUBTRACT', sep.outputs[0], _value(nt, xn, 0.0))
        dy = n.math('SUBTRACT', sep.outputs[1], _value(nt, yn, 0.0))
        return n.math('SQRT', n.math('ADD', n.math('MULTIPLY', dx, dx), n.math('MULTIPLY', dy, dy)))
    d1 = dist('ringX', 'ringY')
    ring = n.math('MULTIPLY', n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', d1, _value(nt, 'ringR', -999.0))),
                                          0.0, 22.0, 1.0, 0.0), _value(nt, 'ringK', 0.0))
    d2 = dist('sprX', 'sprY')
    spr = n.maprange(n.math('SUBTRACT', d2, _value(nt, 'sprR', -10.0)), 0.0, 25.0, 1.0, 0.0)
    return ring, spr


def sep2x(n):
    sp = n.node('ShaderNodeSeparateXYZ')
    n.set(sp.inputs[0], n.node('ShaderNodeNewGeometry').outputs['Position'])
    return sp.outputs[0]


def ground_mat():
    m, n = SP.BP._new_mat('ValleyGround')
    out = n.node('ShaderNodeOutputMaterial')
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.92)
    tc = n.node('ShaderNodeTexCoord')
    nz = n.node('ShaderNodeTexNoise', Scale=0.012, Detail=10.0)
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    ramp_ = n.node('ShaderNodeValToRGB')
    n.set(ramp_.inputs[0], nz.outputs['Fac'])
    ramp_.color_ramp.elements[0].color = (0.15, 0.11, 0.11, 1)
    ramp_.color_ramp.elements[1].color = (0.5, 0.39, 0.36, 1)
    n.set(b.inputs['Base Color'], ramp_.outputs[0])
    fine = n.node('ShaderNodeTexNoise', Scale=0.6, Detail=8.0)
    n.set(fine.inputs['Vector'], tc.outputs['Object'])
    bump = n.node('ShaderNodeBump', Strength=0.35)
    n.set(bump.inputs['Height'], fine.outputs['Fac'])
    n.set(b.inputs['Normal'], bump.outputs[0])
    # violet veins: thin warped voronoi edges, dark until a pulse or the spread lights them
    vor = n.node('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 0.06
    warp = n.node('ShaderNodeTexNoise', Scale=0.02, Detail=5.0)
    n.set(warp.inputs['Vector'], tc.outputs['Object'])
    vm = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    vm.inputs[1].default_value = (14.0, 14.0, 14.0)
    n.set(vm.inputs[0], warp.outputs['Color'])
    n.set(vm.inputs[2], tc.outputs['Object'])
    n.set(vor.inputs['Vector'], vm.outputs[0])
    vein = n.math('LESS_THAN', vor.outputs['Distance'], 0.006)
    ring, spr = _pulse_nodes(m, n)
    crack = _value(m.node_tree, 'crackK', 0.0)
    k = n.math('ADD', n.math('MULTIPLY', ring, 4.0), n.math('MULTIPLY', spr, 0.9))
    nearx = n.maprange(n.math('ABSOLUTE', sep2x(n)), 0.0, 70.0, 1.0, 0.0)
    k = n.math('ADD', k, n.math('MULTIPLY', crack, nearx))
    zsep = n.node('ShaderNodeSeparateXYZ')
    n.set(zsep.inputs[0], n.node('ShaderNodeNewGeometry').outputs['Position'])
    k = n.math('MULTIPLY', k, n.maprange(zsep.outputs[2], 6.0, 30.0, 1.0, 0.0))
    b.inputs['Emission Color'].default_value = (*VIOLET, 1)
    n.set(b.inputs['Emission Strength'], n.math('MULTIPLY', vein, k))
    n.set(out.inputs['Surface'], b.outputs[0])
    return m


def crystal_mat_pink():
    """Pale pink-white valley crystal that turns violet where the spread has reached, and flares when
    a pulse ring passes under it."""
    m, n = SP.BP._new_mat('ValleyCrystal')
    out = n.node('ShaderNodeOutputMaterial')
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.12, IOR=1.6)
    b.inputs['Transmission Weight'].default_value = 0.55
    ring, spr = _pulse_nodes(m, n)
    vv = _value(m.node_tree, 'allViolet', 0.0)
    v = n.math('MINIMUM', n.math('ADD', spr, vv), 1.0)
    col = n.mix(v, (1.0, 0.86, 0.93), (0.5, 0.18, 1.0))
    n.set(b.inputs['Base Color'], col)
    ecol = n.mix(v, PINK, VIOLET)
    n.set(b.inputs['Emission Color'], ecol)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.3)
    base_s = n.maprange(lw.outputs['Facing'], 0.0, 1.0, 0.35, 1.2)
    s = n.math('ADD', base_s, n.math('MULTIPLY', ring, 5.0))
    s = n.math('ADD', s, n.math('MULTIPLY', v, 1.6))
    s = n.math('MULTIPLY', s, _value(m.node_tree, 'glowK', 1.0))
    n.set(b.inputs['Emission Strength'], s)
    n.set(out.inputs['Surface'], b.outputs[0])
    return m


def dust_mat(name, col=(0.55, 0.45, 0.38)):
    """Lit (not glowing) billowing dust: churning noise, soft ragged edges, keyed 'V' visibility."""
    m, n = SP.BP._new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    t = SP.BP.time_value(m, 'time', 0.8)
    nz = n.node('ShaderNodeTexNoise', Scale=1.7, Detail=6.0, Distortion=0.3)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], t)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    body = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 2.4)     # soft, edgeless
    st = n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.0, 1.0)
    vv = _value(m.node_tree, 'V', 1.0)
    alpha = n.math('MINIMUM', n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY_ADD', st, 0.5, 0.5),
                                                                      n.math('MULTIPLY', body, 1.5)), vv), 1.0)
    d0 = n.node('ShaderNodeBsdfDiffuse')
    d0.inputs['Color'].default_value = (*col, 1)
    tl = n.node('ShaderNodeBsdfTranslucent')
    tl.inputs['Color'].default_value = (*col, 1)
    d = n.node('ShaderNodeMixShader')
    d.inputs[0].default_value = 0.45
    n.set(d.inputs[1], d0.outputs[0])
    n.set(d.inputs[2], tl.outputs[0])
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], alpha)
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], d.outputs[0])
    n.set(out.inputs['Surface'], mx.outputs[0])
    return m


def V_soft(name, col, k):
    import v3base
    return v3base.soft_glow(name, col, k, 2.0)


# ================================================================== loading game units
_unit_cache = {}


def load_unit(rel, joined=True, mat_from=None):
    """Import a game GLB. joined=True: one mesh object (template, hidden), for instancing.
    joined=False: the hierarchy root (for hero units with a turret pivot)."""
    key = (rel, joined)
    if key in _unit_cache:
        return _unit_cache[key]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS, rel + '.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    if mat_from:
        src = load_unit(mat_from, joined=False)
        srcm = {o.name.split('.')[0]: [s.material for s in o.material_slots]
                for o in [src] + list(src.children_recursive) if o.type == 'MESH'}
        for o in meshes:
            if not o.material_slots:
                for mt in srcm.get(o.name.split('.')[0], []):
                    o.data.materials.append(mt)
    for o in meshes:
        o.visible_shadow = True
    if not joined:
        root = next(o for o in new if o.parent is None)
        _unit_cache[key] = root
        root.location = (0, 0, -5000)
        for o in [root] + list(root.children_recursive):
            o.hide_render = True
        return root
    others = [o.name for o in new if o.type != 'MESH']
    for o in [o for o in meshes if o.name.startswith('Flash')]:   # muzzle flash: never part of a static unit
        meshes.remove(o)
        bpy.data.objects.remove(o)
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = 'T_' + rel.replace('/', '_')
    for nm in others:
        if nm in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[nm])
    ob.hide_render = True
    ob.location = (0, 0, -5000)
    _unit_cache[key] = ob
    return ob


def instance(tmpl, name):
    o = bpy.data.objects.new(name, tmpl.data)
    SP.link(o)
    return o


def hero_unit(rel, name):
    root = load_unit(rel, joined=False)
    c = SP.copy_tree(root, name)
    for o in [c] + list(c.children_recursive):
        o.hide_render = False
    for o in c.children_recursive:          # muzzle flashes stay shut until the gun fires (see fire())
        if o.name.startswith('Flash') and o.type == 'EMPTY':
            o.scale = (0.001,) * 3
            o.keyframe_insert('scale', frame=1)
    return c


def gun_parts(root):
    """{side: [[barrel pivots], flash pivot]} for a hero unit; side 'L'/'R', or '' for a single gun."""
    out = {}
    for o in root.children_recursive:
        if o.type != 'EMPTY':
            continue
        nm = o.name.split('.')[0]
        if nm.startswith('Barrel') and nm.endswith('Pivot'):
            sd = nm[6] if nm[6] in 'LR' else ''
            out.setdefault(sd, [[], None])[0].append(o)
        elif nm.startswith('Flash') and nm.endswith('Pivot'):
            sd = nm[5] if nm[5] in 'LR' else ''
            out.setdefault(sd, [[], None])[1] = o
    return out


def fire(root, f, side='', recoil=0.55, light=None, col=(0.4, 0.85, 1.0)):
    """One shot as in the game: the muzzle flash pops for two frames, the barrel snaps back and kicks up,
    then eases home. Shots from one barrel need at least 8 frames between them. Returns the flash pivot."""
    parts = gun_parts(root)
    if side not in parts:
        side = sorted(parts)[0]
    barrels, flash = parts[side]
    for k, b in enumerate(sorted(barrels, key=lambda o: o.name)):
        if 'rest_x' not in b:
            b.rotation_mode = 'XYZ'
            b['rest_x'] = b.location.x
            b['rest_ry'] = b.rotation_euler.y
        x0, ry0 = b['rest_x'], b['rest_ry']
        back = recoil * (0.45 + 0.55 * (k + 1) / max(1, len(barrels)))     # the tip slides furthest
        for fk, dx, ry in ((f - 1, 0.0, 0.0), (f, -back, -0.05), (f + 2, -back * 0.8, -0.035), (f + 7, 0.0, 0.0)):
            b.location.x = x0 + dx
            b.keyframe_insert('location', index=0, frame=fk)
            b.rotation_euler.y = ry0 + ry
            b.keyframe_insert('rotation_euler', index=1, frame=fk)
        b.location.x = x0
        b.rotation_euler.y = ry0
    if flash is not None:
        for fk, s_ in ((f - 1, 0.001), (f, 1.35), (f + 1, 0.9), (f + 2, 0.001)):
            flash.scale = (s_,) * 3
            flash.keyframe_insert('scale', frame=fk)
        SP._interp_where(flash, 'scale', 'CONSTANT')
        flash.scale = (0.001,) * 3
        if light:
            L = bpy.data.objects.new(SP._uid('MuzzleL'), bpy.data.lights.new(SP._uid('MuzzleL'), 'POINT'))
            SP.link(L)
            L.parent = flash
            L.data.color = col
            L.data.shadow_soft_size = 0.4
            for fk, e in ((1, 0), (f - 1, 0), (f, light), (f + 1, light * 0.4), (f + 3, 0)):
                L.data.energy = e
                L.data.keyframe_insert('energy', frame=fk)
            SP.lin(L.data)
    return flash


def unit_material(tmpl):
    return [s.material for s in tmpl.material_slots if s.material]


def key_emission(mats, keys):
    for m in mats:
        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b is None:
            continue
        s0 = b.inputs['Emission Strength'].default_value
        for f, k in keys:
            b.inputs['Emission Strength'].default_value = s0 * k
            b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)


# ================================================================== the scene
class Ground:
    def __init__(self, need=(), draft=True):
        self.need = set(need)
        self.draft = draft
        self.sh = C.Shot(NF / FPS, FPS, draft)
        SP.OS.NF = NF
        self.rnd = random.Random(3800)
        self.world()
        self.terrain()
        self.crystals()
        self.base()
        self.pods()
        self.armies()
        self.hero()
        self.gunfire()
        self.aircraft()
        self.shard()
        self.strikes()
        self.violet_keys()
        bpy.context.scene.frame_set(T_DROP)

    # ------------------------------------------------------------ sky, sun, clouds
    def world(self):
        NP.sky(top=(0.09, 0.08, 0.2), horizon=(0.85, 0.5, 0.52), strength=1.25, below=(0.14, 0.1, 0.1))
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        SP.link(sun)
        sun.data.energy = 4.6
        sun.data.color = (1.0, 0.78, 0.58)
        sun.data.angle = math.radians(1.5)
        sun.rotation_euler = (math.radians(69), 0, math.radians(70))   # low, from the Arcadian end: long shadows toward us
        self.sun = sun
        # cloud deck high above; a ring is blown open over the Shard at 0:54
        cl = C.uv_sphere('CloudDeck', 1.0, seg=(8, 4))
        bpy.data.objects.remove(cl)
        bpy.ops.mesh.primitive_plane_add(size=1)
        deck = bpy.context.active_object
        deck.name = 'CloudDeck'
        deck.scale = (12000, 12000, 1)
        deck.location = (0, 0, 1400)
        m, n = SP.BP._new_mat('Clouds')
        out = n.node('ShaderNodeOutputMaterial')
        geo = n.node('ShaderNodeNewGeometry')
        nz = n.node('ShaderNodeTexNoise', Scale=0.0012, Detail=8.0, Roughness=0.6)
        n.set(nz.inputs['Vector'], geo.outputs['Position'])
        dens = n.maprange(nz.outputs['Fac'], 0.42, 0.7, 0.0, 1.0)
        sep = n.node('ShaderNodeSeparateXYZ')
        n.set(sep.inputs[0], geo.outputs['Position'])
        r = n.math('SQRT', n.math('ADD', n.math('MULTIPLY', sep.outputs[0], sep.outputs[0]),
                                  n.math('MULTIPLY', sep.outputs[1], sep.outputs[1])))
        hr = _value(m.node_tree, 'holeR', 0.0)
        hole = n.maprange(n.math('SUBTRACT', r, hr), -50.0, 150.0, 0.0, 1.0)
        rim = n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', r, hr)), 0.0, 200.0, 1.0, 0.0)
        dens = n.math('MULTIPLY', dens, hole)
        d = n.node('ShaderNodeBsdfDiffuse')
        d.inputs['Color'].default_value = (0.9, 0.75, 0.8, 1)
        em = n.node('ShaderNodeEmission')
        rk = n.math('MULTIPLY', rim, _value(m.node_tree, 'rimK', 0.0))
        n.set(em.inputs['Color'], n.mix(n.math('MINIMUM', rk, 1.0), (0.85, 0.55, 0.6), VIOLET))
        n.set(em.inputs['Strength'], n.math('ADD', 0.5, rk))
        add = n.node('ShaderNodeAddShader')
        n.set(add.inputs[0], d.outputs[0])
        n.set(add.inputs[1], em.outputs[0])
        tr = n.node('ShaderNodeBsdfTransparent')
        mx = n.node('ShaderNodeMixShader')
        n.set(mx.inputs[0], dens)
        n.set(mx.inputs[1], tr.outputs[0])
        n.set(mx.inputs[2], add.outputs[0])
        n.set(out.inputs['Surface'], mx.outputs[0])
        deck.data.materials.append(m)
        deck.visible_shadow = False
        self.cloud_mat = m

    def terrain(self):
        nx, ny = 300, 150
        Lx, Ly = 3200.0, 1700.0
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=nx, y_subdivisions=ny, size=1)
        g = bpy.context.active_object
        g.name = 'Valley'
        for v in g.data.vertices:
            x, y = v.co.x * Lx, v.co.y * Ly
            v.co = (x, y, height(x, y))
        for p in g.data.polygons:
            p.use_smooth = True
        self.gmat = ground_mat()
        g.data.materials.append(self.gmat)
        self.ground = g

    def zat(self, x, y):
        return height(x, y)

    # ------------------------------------------------------------ crystals
    def crystals(self):
        rnd = random.Random(3801)
        self.cmat = crystal_mat_pink()
        tmpls = []
        with AF.gold_palette():
            base._faction('kesh')
            for k in range(12):
                ob = NP.crystal_cluster((0, 0, 0), 1.0, rnd, self.cmat)
                ob.name = f'CrystalT{k}'
                ob.hide_render = True
                ob.location = (0, 0, -5000)
                tmpls.append(ob)
        self.ctmpl = tmpls
        patches = [(rnd.uniform(-900, 900), rnd.uniform(-320, 320)) for _ in range(80)]
        n = 0
        for (cx, cy) in patches:
            if cx < BASE_X + 140 and abs(cy) < 160:
                continue
            for i in range(rnd.randint(18, 40)):
                r = 38 * math.sqrt(rnd.random())
                a = rnd.uniform(0, 2 * math.pi)
                x, y = cx + r * math.cos(a), cy + r * math.sin(a)
                s = rnd.uniform(3.0, 9.0) * (1.4 - r / 38)
                o = instance(tmpls[rnd.randrange(len(tmpls))], f'Crys{n}')
                o.location = (x, y, self.zat(x, y) - 0.3)
                o.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
                o.scale = (s, s, s)
                n += 1
        for i in range(900):                   # loose shards everywhere
            x, y = rnd.uniform(-1100, 1100), rnd.uniform(-420, 420)
            if x < BASE_X + 140 and abs(y) < 160:
                continue
            s = rnd.uniform(1.2, 3.2)
            o = instance(tmpls[rnd.randrange(len(tmpls))], f'CrysL{i}')
            o.location = (x, y, self.zat(x, y) - 0.2)
            o.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
            o.scale = (s, s, s)

    # ------------------------------------------------------------ the Terran forward base and drop ships
    def base(self):
        rnd = random.Random(3802)
        pad = load_unit('structures/terran_landing_pad')
        self.pads = []
        for i, (x, y) in enumerate(PADS):
            o = instance(pad, f'Pad{i}')
            o.location = (x, y, self.zat(x, y))
            o.scale = (PAD_K,) * 3
            self.pads.append(Vector((x, y, self.zat(x, y) + 4.47 * PAD_K * 0.35)))
        for rel, pts, k in (('structures/terran_turret', [(BASE_X + 90, 120), (BASE_X + 90, -120), (BASE_X - 190, 150),
                                                           (BASE_X - 190, -150)], 1.8),
                            ('structures/terran_radar', [(BASE_X - 200, 0)], 1.8),
                            ('structures/terran_metal_station', [(BASE_X - 30, 150)], 1.8)):
            t = load_unit(rel)
            for j, (x, y) in enumerate(pts):
                o = instance(t, f'BaseStr_{rel.split("/")[-1]}{j}')
                o.location = (x, y, self.zat(x, y))
                o.rotation_euler = (0, 0, math.radians(180 if x > BASE_X else 0))
                o.scale = (k,) * 3
        # drop ships: the hero ship comes down into shot 8b and lands at 0:39, others behind it
        self.ds_src = NP.drop_ship('DropSrc', cargo=True, hot=False)
        self.ds_src.location = (0, 0, -6000)
        for o in [self.ds_src] + list(self.ds_src.children_recursive):
            o.hide_render = True
        self.drops = []
        plan = [(0, T_LAND, Vector((-1250, 260, 520))), (2, T_LAND + 34, Vector((-1150, 330, 480))),
                (4, T_LAND + 58, Vector((-1250, -300, 520))), (3, T_LAND + 80, Vector((-1350, 120, 560))),
                (5, T_LAND + 100, Vector((-1300, 40, 500)))]
        for k, (pi, f_land, start) in enumerate(plan):
            ds = SP.copy_tree(self.ds_src, f'Drop{k}')
            for o in [ds] + list(ds.children_recursive):
                o.hide_render = False
            padp = self.pads[pi]
            land = padp + Vector((0, 0, 2.05 * DS_K))
            # David 2026-11-28: it came down far too fast. Now it arrives at speed, lights its landing jets
            # high up and brakes hard all the way down: ~4 s of visibly slowing descent, a gentle settle.
            f0 = f_land - 125
            fi = f_land - 102                                   # ignition
            keys = [(f0 - 35, start + (start - land) * 0.6), (f0, start), (f_land - 100, land + Vector((150, 0, 260))),
                    (f_land - 76, land + Vector((60, 0, 130))), (f_land - 52, land + Vector((18, 0, 58))),
                    (f_land - 30, land + Vector((4, 0, 22))), (f_land - 13, land + Vector((0.5, 0, 6))),
                    (f_land - 4, land + Vector((0, 0, 1.2))), (f_land, land),
                    (f_land + 3, land - Vector((0, 0, 0.15 * DS_K))), (f_land + 9, land), (G_END, land)]
            frames = list(range(f0 - 35, G_END + 1))
            locs = [catmull(keys, f) for f in frames]
            quats = []
            for i, f in enumerate(frames):
                v = locs[min(i + 1, len(locs) - 1)] - locs[max(i - 1, 0)]
                flat = Vector((v.x, v.y, 0))
                yaw = math.atan2(flat.y, flat.x) if flat.length > 0.05 else 0.0
                pitch = -math.atan2(v.z, max(flat.length, 1e-3)) * (1 - ramp(f, fi - 6, fi + 10))
                pitch = max(-0.35, min(0.35, pitch))
                # nose comes up as the jets bite (braking flare), levels off for the last metres
                pitch -= 0.2 * ramp(f, fi - 4, fi + 12) * (1 - ramp(f, f_land - 40, f_land - 10))
                yaw = yaw * (1 - ramp(f, fi, f_land - 40))
                shake = (0.012 + 0.02 * ramp(f, fi, fi + 4) * (1 - ramp(f, fi + 4, fi + 30))) * \
                    math.sin(f * 2.3) * (1 - ramp(f, f_land, f_land + 3))
                quats.append(Quaternion((0, 0, 1), yaw) @ Quaternion((0, 1, 0), -pitch + shake))
            bake(ds, frames, locs, quats)
            ds.scale = (DS_K,) * 3
            SP.show(ds, f0 - 35, G_END)
            # landing thrusters: four blue jets under the stub-wing pods; they light with a burst high up and
            # burn hard, flickering, all the way down
            jm = SP.emit(f'JetM{k}', (0.45, 0.78, 1.0), 5.0)
            hm = V_soft('JetHalo', (0.3, 0.6, 1.0), 3.0)
            jr = random.Random(3830 + k)
            base_ks = [(fi - 2, 0.2), (fi + 2, 3.6), (fi + 8, 3.1), (f_land - 50, 2.9), (f_land - 20, 2.3),
                       (f_land - 4, 1.5), (f_land + 4, 0.4), (f_land + 10, 0.02)]
            ks = []
            for f_ in range(fi - 2, f_land + 11, 2):
                L_ = catmull([(a_, Vector((b_, 0, 0))) for a_, b_ in base_ks], f_).x
                ks.append((f_, max(0.02, L_ * (jr.uniform(0.86, 1.1) if f_ < f_land + 4 else 1.0))))
            for (lx, ly) in ((-3.1, 3.2), (-3.1, -3.2), (1.5, 3.2), (1.5, -3.2)):
                for nm, mat, wk in (('Core', jm, 1.0), ('Halo', hm, 2.4)):
                    j = C.uv_sphere(f'Jet{nm}{k}_{lx}_{ly}', 1.0, seg=(12, 6), mat=mat)
                    j.parent = ds
                    for f_, L_ in ks:
                        w_ = 0.2 * wk * (0.6 + 0.4 * min(1.0, L_))
                        j.scale = (w_, w_, L_ * (1.0 if wk == 1.0 else 0.7))
                        j.location = (lx, ly, -1.5 - j.scale.z)
                        j.keyframe_insert('scale', frame=f_)
                        j.keyframe_insert('location', frame=f_)
                    C.set_interp(j, 'LINEAR')
                    SP.show(j, fi - 2, f_land + 10)
                    j.visible_shadow = False
            # their glow on the ground below as it comes down
            JL = bpy.data.objects.new(f'JetLight{k}', bpy.data.lights.new(f'JetLight{k}', 'POINT'))
            SP.link(JL)
            JL.parent = ds
            JL.location = (-0.8, 0, -5.0)
            JL.data.color = (0.45, 0.75, 1.0)
            JL.data.shadow_soft_size = 2.0
            for f_, L_ in [(1, 0.0)] + ks:
                JL.data.energy = 6e4 * min(L_, 3.0) / 3.0
                JL.data.keyframe_insert('energy', frame=f_)
            SP.lin(JL.data)
            # touchdown: shockwave ring + dust wall
            self.touchdown(land - Vector((0, 0, 2.05 * DS_K)), f_land, big=(k == 0))
            self.drops.append(ds)
        # Lancers rolling off the pads out of the dust (0:40)
        lt = load_unit('human/lancer')
        self.rollers = []
        for k, (pi, dx) in enumerate([(0, 0), (1, 10), (0, -12), (1, -6)]):
            p = self.pads[pi]
            o = instance(lt, f'Roller{k}')
            f0 = T_ROLL - 14 + 6 * k
            z = self.zat(p.x, p.y)
            pts = [(T_LAND, Vector((p.x - 20 + dx, p.y, z + 1.0))), (f0, Vector((p.x - 20 + dx, p.y, z + 1.0))),
                   (f0 + 70, Vector((p.x + 95 + dx, p.y + (k - 1.5) * 12, self.zat(p.x + 95, p.y))))]
            SP.key_loc(o, pts, 'LINEAR')
            SP.show(o, f0 - 4, G_END)

    def touchdown(self, p, f, big=False):
        ring_m = SP.emit(SP._uid('ShockM'), (0.8, 0.9, 1.0), 3.0)
        base._faction('terran')
        ring = base._join([F.lathe([(0.9, 0.1), (1.0, 0.0), (0.92, -0.05)], 48, 'glow')], SP._uid('Shock'))
        ring.data.materials.clear()
        ring.data.materials.append(ring_m)
        ring.location = p + Vector((0, 0, 1))
        SP.key_scale(ring, [(f, (2, 2, 1)), (f + 10, (140 if big else 80, 140 if big else 80, 4))], 'LINEAR')
        SP.show(ring, f, f + 10)
        ring.visible_shadow = False
        rnd = random.Random(int(p.x * 7 + p.y))
        n_ = 26 if big else 12
        for i in range(n_):
            dm = dust_mat(SP._uid('DustM'))
            d = C.uv_sphere(SP._uid('Dust'), 1.0, seg=(18, 10), mat=dm)
            a = (i + rnd.uniform(-0.4, 0.4)) / n_ * 2 * math.pi
            v = Vector((math.cos(a), math.sin(a), 0))
            reach = rnd.uniform(38, 58) * (1.0 if big else 0.6)
            s0 = rnd.uniform(3, 5)
            s1 = rnd.uniform(8, 13) * (1.0 if big else 0.7)
            fd = f - 22 + rnd.randint(0, 10)
            SP.key_loc(d, [(fd, p + v * 10 + Vector((0, 0, 3))), (fd + 14, p + v * reach * 0.7 + Vector((0, 0, 6))),
                           (fd + 60, p + v * reach + Vector((0, 0, 10)))], 'BEZIER')
            SP.key_scale(d, [(fd, (s0, s0, s0 * 0.6)), (fd + 14, (s1 * 0.8, s1 * 0.8, s1 * 0.45)),
                             (fd + 60, (s1, s1, s1 * 0.6))], 'BEZIER')
            SP.key_node(dm, 'V', [(fd, 0.7), (fd + 16, 0.5), (fd + 50, 0.0)])
            SP.show(d, fd, fd + 50)
            d.visible_shadow = False

    # ------------------------------------------------------------ seed pods split into nests (0:41)
    def pods(self):
        rnd = random.Random(3803)
        nest = load_unit('structures/kesh_landing_nest')
        self.pod_objs = []
        self.nest_pos = []
        st_t = load_unit('alien/stinger')
        for k, (x, y) in enumerate(POD_SITES):
            z = self.zat(x, y)
            pod = NP.seed_pod(f'Pod{k}')
            pod.scale = (POD_K,) * 3
            pod.rotation_euler = (0, math.radians(70), rnd.uniform(0, 6.3))     # nose down in its crater
            pod.location = (x, y, z + 5.5)
            f_open = T_PODS + 2 + k * 2
            # petals: split the pod round its axis and swing them open
            bpy.context.view_layer.update()
            parts = SP.split_mesh(pod, lambda c: int(((math.atan2(c.z, c.y) + math.pi) / (2 * math.pi)) * 6) % 6,
                                  [f'Pod{k}_Petal{j}' for j in range(6)])
            for j, p in enumerate(parts):
                a = (j + 0.5) / 6 * 2 * math.pi - math.pi
                axis_l = Vector((0, -math.sin(a), math.cos(a)))
                axis_w = (pod.matrix_world.to_3x3() @ axis_l).normalized()
                q0 = pod.matrix_world.to_quaternion()
                frames = [f_open - 1, f_open + 8, f_open + 20]
                quats = [q0, Quaternion(axis_w, math.radians(-75)) @ q0, Quaternion(axis_w, math.radians(-100)) @ q0]
                bake(p, frames, [pod.location.copy()] * 3, quats)
                p.scale = (POD_K,) * 3
                SP.show(p, f_open, G_END)
            SP.show(pod, 1, f_open - 1)
            n = instance(nest, f'Nest{k}')
            n.location = (x, y, z - 1.0)
            n.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
            SP.key_scale(n, [(f_open, 0.6), (f_open + 14, 2.0)], 'BEZIER')
            SP.show(n, f_open, G_END)
            gl = C.uv_sphere(f'NestGlow{k}', 1.0, seg=(16, 8), mat=SP.BP._halo_mat(f'NestGlowM{k}', GOLD, 3.0))
            gl.location = (x, y, z + 6)
            SP.key_scale(gl, [(f_open, 2.0), (f_open + 4, 9.0), (f_open + 16, 2.0)], 'LINEAR')
            SP.show(gl, f_open, f_open + 16)
            gl.visible_shadow = False
            L = bpy.data.objects.new(f'NestLight{k}', bpy.data.lights.new(f'NestLight{k}', 'POINT'))
            SP.link(L)
            L.location = (x, y, z + 7)
            L.data.color = GOLD
            L.data.shadow_soft_size = 4
            for f_, e in [(1, 0), (f_open, 0), (f_open + 4, 6e4), (f_open + 40, 2e4), (f_open + 70, 0)]:
                L.data.energy = e
                L.data.keyframe_insert('energy', frame=f_)
            self.nest_pos.append(Vector((x, y, z)))
            # Stingers hover up out of the nest and head west
            for s in range(2):
                o = instance(st_t, f'NestSting{k}_{s}')
                p0 = Vector((x, y, z + 1))
                p1 = p0 + Vector((-10, (s - 0.5) * 16, 9))
                p2 = p1 + Vector((-120, (s - 0.5) * 20, -7))
                SP.key_loc(o, [(f_open + 8 + 6 * s, p0), (f_open + 26 + 6 * s, p1), (G_END, p2)], 'BEZIER')
                o.rotation_euler = (0, 0, math.pi)
                SP.show(o, f_open + 8 + 6 * s, G_END)

    # ------------------------------------------------------------ the two armies
    def front_x(self, side, f):
        """x of a side's front rank (side -1 = Terran, +1 = Arcadian)."""
        if f <= T_PODS:
            x = 170.0
        elif f <= T_MEET:
            x = 170.0 - 130.0 * (f - T_PODS) / float(T_MEET - T_PODS)
        elif f <= T_SPLIT - 4:
            x = 40.0 - 15.0 * (f - T_MEET) / float(T_SPLIT - 4 - T_MEET)
        else:
            x = 25.0 - 3.0 * ramp(f, T_SPLIT - 4, T_SPLIT + 8)
        return side * x

    def armies(self):
        rnd = random.Random(3804)
        lan = load_unit('human/lancer_lod', mat_from='human/lancer')
        sti = load_unit('alien/stinger_lod', mat_from='alien/stinger')
        self.lancer_mats = unit_material(lan) + unit_material(load_unit('human/lancer'))
        self.stinger_mats = unit_material(sti) + unit_material(load_unit('alien/stinger'))
        # v3 (David 2026-11-14): the full unit mix on both sides, not just Lancers and Stingers
        mix = {-1: [lan], 1: [sti]}
        for side, fac, names in ((-1, 'human', ('bulwark', 'javelin', 'longbow', 'outrider')),
                                 (1, 'alien', ('carapace', 'gorger', 'spitter', 'mortar_beast', 'weaver'))):
            for nm in names:
                if not os.path.exists(os.path.join(MODELS, f'{fac}/{nm}_lod.glb')):
                    continue
                t = load_unit(f'{fac}/{nm}_lod', mat_from=f'{fac}/{nm}')
                mix[side].append(t)
                ms = unit_material(t) + unit_material(load_unit(f'{fac}/{nm}'))
                (self.lancer_mats if side < 0 else self.stinger_mats).extend(ms)
        self.units = {-1: [], 1: []}
        self.fire_sched = {-1: [], 1: []}       # per unit: [(frame, muzzle world pos)]
        self.kills = {-1: [], 1: []}            # (unit index, frame, world pos) of units destroyed in the clash
        base_frames = list(range(T_PODS - 30, G_END + 1, 2))
        if base_frames[-1] != G_END:
            base_frames.append(G_END)
        bm = {-1: SP.emit('BeaconT', CYAN, 4.0), 1: SP.emit('BeaconA', GOLD, 4.0)}
        self.beacon_mats = bm
        KICK = [0.0, 0.42, 0.33, 0.22, 0.12, 0.05, 0.0]       # recoil shove after a shot, metres
        for side in (-1, 1):
            for row in range(4):
                for j in range(52):
                    tm = mix[side][0] if (row == 0 and j % 4) or rnd.random() < 0.35 else \
                        mix[side][rnd.randrange(len(mix[side]))]
                    y = -365 + j * 14.3 + rnd.uniform(-3, 3) + (7 if row % 2 else 0)
                    if side == -1 and abs(y - HERO_Y) < 9 and row == 0:
                        continue                     # the hero's own slot
                    back = row * 19 + rnd.uniform(-4, 4)
                    o = instance(tm, f'{"Lan" if side < 0 else "Sti"}{row}_{j}')
                    ph = rnd.uniform(0, 6.3)
                    lag = rnd.uniform(-5, 5)
                    # destroyed in the clash? (front rows, away from the hero's lane)
                    f_kill = None
                    if row < 2 and abs(y - HERO_Y) > 30 and rnd.random() < 0.09:
                        f_kill = rnd.randint(T_FIRE + 8, T_SPLIT - 6)
                    # its own fire rhythm: each kind of gun keeps its own beat
                    period = {0: 30, 1: 38, 2: 46, 3: 56}[mix[side].index(tm) % 4] + rnd.randint(-3, 3)
                    shots = []
                    if rnd.random() < (0.95 if row < 2 else 0.5):
                        f = T_FIRE + rnd.randint(0, period)
                        while f < T_SPLIT + 2 and (f_kill is None or f < f_kill - 3):
                            if f < T_SPREAD + 6 or rnd.random() < 0.5:
                                shots.append(f)
                            f += period + rnd.randint(-4, 4)

                    def pose(f):
                        fd = min(f, f_kill) if f_kill else f           # a dead unit stops where it died
                        x = self.front_x(side, fd) + side * (back + lag)
                        yy = y + 2.0 * math.sin(fd * 0.02 + ph)
                        z = self.zat(x, yy)
                        if side > 0:
                            hover = 1.6 + 0.4 * math.sin(fd * 0.13 + ph)
                            drop = ramp(f, T_STRIKE_A + int(abs(x) / 30) + 2, T_STRIKE_A + int(abs(x) / 30) + 10)
                            if f_kill and f >= f_kill:
                                drop = ramp(f, f_kill, f_kill + 8)      # its hover dies, it drops
                            z += hover * (1 - drop) - 0.3 * drop
                        brake = ramp(f, T_SPLIT - 2, T_SPLIT + 4) * math.sin(math.pi * ramp(f, T_SPLIT - 2, T_SPLIT + 10))
                        tilt = (0.06 * brake) * (-side)
                        if side > 0:
                            tilt += 0.12 * ramp(f, T_STRIKE_A + 2, T_STRIKE_A + 12) * math.sin(ph)
                        roll = 0.0
                        if f_kill and f >= f_kill:                     # knocked askew by the hit
                            tilt = 0.10 * math.sin(ph * 3) * ramp(f, f_kill, f_kill + 6)
                            roll = 0.14 * math.cos(ph * 5) * ramp(f, f_kill, f_kill + 6)
                        sx = 0.0
                        for fs in shots:
                            if 0 <= f - fs < len(KICK):
                                sx = KICK[f - fs]
                                tilt -= 0.05 * sx / 0.42                  # nose kicks up
                        x += side * sx                                    # shoved back along its own axis
                        yaw = 0.0 if side < 0 else math.pi
                        q = Quaternion((0, 0, 1), yaw) @ Quaternion((0, 1, 0), tilt) @ Quaternion((1, 0, 0), roll)
                        return Vector((x, yy, z)), q
                    fset = set(base_frames)
                    for fs in shots:
                        fset.update(range(fs - 1, fs + len(KICK)))
                    if f_kill:
                        fset.update(range(f_kill - 1, f_kill + 8))
                    frames = sorted(fset)
                    pq = [pose(f) for f in frames]
                    bake(o, frames, [p for p, q in pq], [q for p, q in pq])
                    SP.show(o, T_PODS - 30, G_END)
                    # running light, so a line of hundreds reads as a line of cyan or gold lights from afar
                    bc = C.uv_sphere(f'Beacon{side}_{row}_{j}', 0.38, seg=(8, 4), mat=bm[side])
                    bc.parent = o
                    bc.location = (-1.0, 0, 3.4) if side < 0 else (-0.5, 0, 1.6)
                    bc.visible_shadow = False
                    SP.show(bc, T_PODS - 30, f_kill or G_END)
                    mz = Vector((5, 0, 2.6)) if side < 0 else Vector((-5, 0, 2.2))
                    self.fire_sched[side].append([(fs, pose(fs)[0] + mz) for fs in shots])
                    if f_kill:
                        self.kills[side].append((len(self.units[side]), f_kill, pose(f_kill)[0]))
                    self.units[side].append(o)

    # ------------------------------------------------------------ our Lancer, its neighbour, its kill
    def hero_path(self, f):
        x = self.front_x(-1, f) - 2.0
        return Vector((x, HERO_Y, self.zat(x, HERO_Y)))

    def hero(self):
        h = hero_unit('human/lancer', 'HeroLancer')
        fk = fr(45.6)
        # it fires as in the game: twin barrels in turn, each shot kicking the hull (kill shot at fk - 4)
        hshots = [f for f in range(T_FIRE + 4, T_SPLIT - 4, 9) if abs(f - (fk - 4)) >= 9] + [fk - 4]
        hshots.sort()
        KICK = [0.0, 0.035, 0.026, 0.016, 0.008, 0.003]
        frames = list(range(T_PODS - 30, G_END + 1))
        locs, quats = [], []
        for f in frames:
            jolt = 0.025 * math.sin(f * 1.9) * (1 - ramp(f, T_SPLIT, T_SPLIT + 6))
            brake = 0.07 * math.sin(math.pi * ramp(f, T_SPLIT - 2, T_SPLIT + 10))
            kick = sum(KICK[f - fs] for fs in hshots if 0 <= f - fs < len(KICK))
            locs.append(self.hero_path(f) - Vector((kick * 9, 0, 0)))
            quats.append(Quaternion((0, 1, 0), jolt + brake - kick))
        bake(h, frames, locs, quats)
        self.hero_obj = h
        rs = random.Random(3811)
        for i, fs in enumerate(hshots):
            fl = fire(h, fs, 'LR'[i % 2], recoil=0.6, light=3e4 if fs == fk - 4 else 1.2e4)
            if fs == fk - 4:
                continue                            # the kill shot's tracer is drawn below
            bpy.context.scene.frame_set(fs)
            mp = fl.matrix_world.translation.copy()
            tg = self.hero_path(fs) + Vector((rs.uniform(70, 130), rs.uniform(-25, 25), 2.0))
            tg.z = self.zat(tg.x, tg.y) + 1.5
            self.shot(mp, tg, fs, fs + max(3, int((tg - mp).length / 22)), CYAN, width=0.35)
        piv = next((o for o in h.children_recursive if o.name.startswith('TurretPivot')), None)
        if piv:
            piv.rotation_mode = 'XYZ'
            r0 = piv.rotation_euler.copy()
            SP.key_rot(piv, [(1, tuple(math.degrees(a) for a in r0)),
                             (T_GLOW, tuple(math.degrees(a) for a in r0)),
                             (T_GLOW + 30, (math.degrees(r0.x), math.degrees(r0.y) - 14, math.degrees(r0.z)))])
        # the neighbour that gets flipped end over end past the camera (0:45)
        nb = hero_unit('human/lancer', 'FlipLancer')
        f_hit = T_MEET + 2
        frames = list(range(T_PODS - 30, G_END + 1))
        locs, quats = [], []
        for f in frames:
            p = self.hero_path(f) + Vector((6, 15, 0))
            if f >= f_hit:
                t = (f - f_hit) / FPS
                p0 = self.hero_path(f_hit) + Vector((6, 15, 0))
                p = p0 + Vector((-14 * t, 8 * t, 24 * t - 26 * t * t))
                p.z = max(p.z, self.zat(p.x, p.y) + 0.5)
                ang = min(t, 1.05) * 2 * math.pi * 1.25
            else:
                ang = 0.0
            locs.append(p)
            quats.append(Quaternion((0, 1, 0), -ang) @ Quaternion((1, 0, 0), -0.3 * min(1.0, max(0.0, (f - f_hit) / 20.0))))
        bake(nb, frames, locs, quats)
        hp = self.hero_path(f_hit) + Vector((6, 15, 1.5))
        SP.gold_boom(hp, f_hit, 5.0, life=1.0, light=1e5)
        SP.boom(locs[frames.index(f_hit + 26)], f_hit + 26, 6.0, life=1.4, light=1.2e5)
        # gold shot that hits it
        self.shot(Vector((60, 20, 3)), hp, f_hit - 5, f_hit, GOLD)
        # our Lancer kills a Stinger at close range (0:45.5)
        st = instance(load_unit('alien/stinger'), 'KillSting')
        sp0 = Vector((22, HERO_Y + 10, 0))
        frames2 = list(range(T_PODS, fk + 1))
        sl = [Vector((sp0.x - 0.6 * (f - T_MEET) / 2, sp0.y, self.zat(sp0.x, sp0.y) + 1.8)) for f in frames2]
        bake(st, frames2, sl, [Quaternion((0, 0, 1), math.pi)] * len(frames2))
        SP.show(st, T_PODS, fk)
        bpy.context.scene.frame_set(fk - 4)
        fl = gun_parts(h)['R' if hshots.index(fk - 4) % 2 else 'L'][1]
        muzzle = fl.matrix_world.translation.copy()
        self.shot(muzzle, sl[-1] + Vector((0, 0, 1.5)), fk - 4, fk, CYAN, width=0.35)
        SP.gold_boom(sl[-1] + Vector((0, 0, 1.5)), fk, 9.0, life=1.1, light=1.5e5)
        SP.shards(sl[-1] + Vector((0, 0, 1.5)), fk, 24, GOLD, 0.6, 30, seed=3810, life=1.0, strength=5.0)

    # ------------------------------------------------------------ shots, blasts
    def shot(self, p0, p1, f0, f1, col, width=0.25, name=None):
        m = self._shot_mat(col)
        d = p1 - p0
        o = C.uv_sphere(name or SP._uid('Shot'), 1.0, seg=(8, 5), mat=m, scale=(3.2, width * 0.3, width * 0.3))
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = look_quat(d)
        SP.key_loc(o, [(f0, p0), (f1, p1)], 'LINEAR')
        SP.show(o, f0, f1)
        o.visible_shadow = False
        return o

    _shot_mats = {}

    def _shot_mat(self, col):
        if col not in self._shot_mats:
            self._shot_mats[col] = SP.emit(SP._uid('ShotM'), col, 9.0)
        return self._shot_mats[col]

    def unit_pos(self, side, i, f):
        o = self.units[side][i]
        bpy.context.scene.frame_set(f)
        return o.matrix_world.translation.copy()

    def gunfire(self):
        rnd = random.Random(3805)
        sc = bpy.context.scene
        nT, nA = len(self.units[-1]), len(self.units[1])
        # precompute unit positions on the frames we need (evaluating the scene is slow)
        need = sorted({f for f in range(T_FIRE, T_SPLIT + 6)})
        posT, posA = {}, {}
        for f in need[::2]:
            sc.frame_set(f)
            posT[f] = [o.matrix_world.translation.copy() for o in self.units[-1]]
            posA[f] = [o.matrix_world.translation.copy() for o in self.units[1]]
        keys = sorted(posT)

        def near(f):
            return min(keys, key=lambda k: abs(k - f))
        dead = {sd: {i: fk for i, fk, _ in self.kills[sd]} for sd in (-1, 1)}

        def target(sd, f):
            alive = [i for i in range(len(self.units[sd])) if dead[sd].get(i, 10 ** 6) > f + 4]
            return (posT if sd < 0 else posA)[near(f)][rnd.choice(alive)]
        fm = {-1: SP.emit('MuzzleT', (0.4, 0.85, 1.0), 14.0), 1: SP.emit('MuzzleA', (1.0, 0.7, 0.3), 14.0)}
        n = 0
        # every shot comes from a live unit on its own beat (armies() keeps the schedule and the recoil)
        for side in (-1, 1):
            col = CYAN if side < 0 else GOLD
            for shots in self.fire_sched[side]:
                for f, a in shots:
                    b = target(-side, f + 7) + Vector((0, 0, 1.6)) + Vector((rnd.uniform(-6, 6), rnd.uniform(-6, 6), 0))
                    fl = max(4, int((b - a).length / 22))
                    self.shot(a, b, f + 1, f + 1 + fl, col, width=0.45, name=f'Gun{n}')
                    d = (b - a).normalized()
                    mf = C.uv_sphere(f'Muzzle{n}', 1.0, seg=(12, 8), mat=fm[side])
                    mf.rotation_mode = 'QUATERNION'
                    mf.rotation_quaternion = look_quat(d)
                    mf.location = a + d * 0.5
                    SP.key_scale(mf, [(f, (1.1, 0.38, 0.38)), (f + 1, (0.6, 0.22, 0.22))], 'CONSTANT')
                    SP.show(mf, f, f + 1)
                    mf.visible_shadow = False
                    n += 1
        # units destroyed in the clash: a hit, a burst, then a burning wreck that never fires again
        fire_m = SP.gas_fireball_mat('WreckFire', (1.0, 0.5, 0.1), (0.4, 0.05, 0.01))
        C.key_value(fire_m, 'S', 1, 3.0)
        C.key_value(fire_m, 'V', 1, 1.0)
        for side in (-1, 1):
            for k, (i, fk, p) in enumerate(self.kills[side]):
                hp = p + Vector((0, 0, 2.0))
                (SP.gold_boom if side < 0 else SP.blue_boom)(hp, fk, rnd.uniform(5, 7), life=1.0,
                                                              light=8e4 if k % 2 == 0 else 0, seed=3900 + k)
                SP.shards(hp, fk, 12, PINK if side < 0 else (0.6, 0.85, 1.0), 0.4, 18, seed=3940 + k, life=1.0,
                          strength=2.5)
                fo = C.uv_sphere(SP._uid('WreckFire'), 1.0, seg=(12, 8), mat=fire_m, scale=(1.3, 1.3, 1.6))
                fo.location = p + Vector((0, 0, 2.6))
                SP.show(fo, fk + 2, G_END)
                fo.visible_shadow = False
                for q in range(3):                      # dark smoke rolling up off it
                    f0 = fk + 4 + q * 9
                    dm = dust_mat(SP._uid('WreckSmokeM'), col=(0.07, 0.06, 0.06))
                    sm = C.uv_sphere(SP._uid('WreckSmoke'), 1.0, seg=(14, 9), mat=dm)
                    SP.key_loc(sm, [(f0, p + Vector((0, 0, 3))), (f0 + 50, p + Vector((-4, 2, 16)))], 'BEZIER')
                    SP.key_scale(sm, [(f0, (1.2,) * 3), (f0 + 50, (5.5, 5.5, 4.5))], 'BEZIER')
                    SP.key_node(dm, 'V', [(f0, 0.9), (f0 + 30, 0.6), (f0 + 50, 0.0)])
                    SP.show(sm, f0, f0 + 50)
                    sm.visible_shadow = False
        # blasts along the meeting zone, dirt and crystal shards
        for k in range(30):
            f = rnd.randint(T_FIRE + 6, T_SPLIT - 2)
            side = rnd.choice((-1, 1))
            x = self.front_x(side, f) + side * rnd.uniform(-10, 60)
            y = rnd.uniform(-360, 360)
            p = Vector((x, y, self.zat(x, y) + 2))
            (SP.gold_boom if side < 0 else SP.blue_boom)(p, f, rnd.uniform(6, 12), life=1.0,
                                                          light=6e4 if k % 4 == 0 else 0)
            SP.shards(p, f, 10, PINK, 0.5, 26, seed=3820 + k, life=1.0, strength=2.0)
        # hits near our Lancer while it charges
        for k in range(8):
            f = T_CHARGE + 4 + k * 5
            hp = self.hero_path(f) + Vector((rnd.uniform(18, 45), rnd.choice((-1, 1)) * rnd.uniform(14, 30), 1))
            hp.z = self.zat(hp.x, hp.y) + 1.5
            SP.boom(hp, f, rnd.uniform(3.5, 5.5), life=0.9, light=5e4 if k % 2 else 0)
            SP.shards(hp, f, 14, PINK, 0.45, 24, seed=3870 + k, life=1.1, strength=2.5)

    # ------------------------------------------------------------ aircraft overhead (0:43)
    def aircraft(self):
        """v3: many more and of every kind: Condors, Falcons and Skimmers over the Terran line; Dragonflies,
        saucers (Discs), Darters and Gliders over the Arcadians. Several height bands, some low and close."""
        rnd = random.Random(3806)
        kinds = {-1: [n for n in ('condor', 'falcon', 'skimmer') if os.path.exists(os.path.join(MODELS, f'human/{n}.glb'))],
                 1: [n for n in ('dragonfly', 'disc', 'darter', 'glider') if os.path.exists(os.path.join(MODELS, f'alien/{n}.glb'))]}
        for side in (-1, 1):
            fac = 'human' if side < 0 else 'alien'
            tm = [load_unit(f'{fac}/{n}') for n in kinds[side]]
            for i in range(26):
                t = tm[i % len(tm)]
                f0 = T_ROLL + rnd.randint(0, T_SPLIT - T_ROLL - 30)
                y = rnd.uniform(-260, 260)
                z = rnd.choice((rnd.uniform(18, 35), rnd.uniform(40, 70), rnd.uniform(70, 110)))
                dur = rnd.randint(50, 80)
                p0 = Vector((-side * 700, y, z))
                p1 = Vector((side * 500 * rnd.uniform(0.3, 1.0), y + rnd.uniform(-90, 90), z + rnd.uniform(-12, 12)))
                o = instance(t, f'Air{side}_{i}')
                o.rotation_euler = (rnd.uniform(-0.25, 0.25), 0, 0 if side < 0 else math.pi)
                SP.key_loc(o, [(f0, p0), (f0 + dur, p1)], 'LINEAR')
                SP.show(o, f0, f0 + dur)
                o.scale = (1.4,) * 3

    # ------------------------------------------------------------ the crack and the Shard
    def shard(self):
        rnd = random.Random(3807)
        # the crack across the valley at x = 0
        base._faction('terran')
        cm = SP.emit('CrackGlowM', (0.42, 0.1, 1.0), 7.0)
        crack = []
        for i in range(40):
            y = -420 + i * 21
            w = 0.35 + 1.2 * math.sin(math.pi * i / 39) + rnd.uniform(-0.2, 0.2)
            o = C.uv_sphere(f'Crack{i}', 1.0, seg=(10, 6), mat=cm)
            o.location = (rnd.uniform(-3, 3), y, self.zat(0, y) - 0.45)
            SP.key_scale(o, [(T_SPLIT - 1 + int(abs(y) / 60), (0.2, 12, 0.5)),
                             (T_SPLIT + 10 + int(abs(y) / 60), (w, 13, 0.55)), (T_RISE + 10, (w * 1.5, 13, 0.65))], 'BEZIER')
            SP.show(o, T_SPLIT - 1 + int(abs(y) / 60), G_END)
            o.visible_shadow = False
        # rocks lifting out of the crack
        for i in range(30):
            y = rnd.uniform(-200, 200)
            p0 = Vector((rnd.uniform(-8, 8), y, self.zat(0, y)))
            F.ST['faction'] = 'nature'
            F.ST['mats'] = {}
            r = F.rock((0, 0, 0), rnd.uniform(1.0, 3.5), 'rock', seed=i)
            r = base._join([r], f'LiftRock{i}')
            f0 = T_RISE + rnd.randint(-4, 26)
            out = Vector((rnd.uniform(4, 12) * (1 if p0.x >= 0 else -1), rnd.uniform(-4, 4), 0))
            vz = rnd.uniform(9, 20)
            ks = []
            for t_ in range(0, 80, 2):
                tt = t_ / FPS
                q = p0 + out * tt + Vector((0, 0, vz * tt - 9.8 * tt * tt))
                gz = self.zat(q.x, q.y)
                if q.z < gz and t_ > 4:
                    q.z = gz
                    ks.append((f0 + t_, q))
                    break
                ks.append((f0 + t_, q))
            SP.key_loc(r, ks + [(G_END, ks[-1][1])], 'LINEAR')
            SP.key_rot(r, [(f0, (0, 0, 0)), (ks[-1][0], (rnd.uniform(-200, 200), rnd.uniform(-200, 200), rnd.uniform(-90, 90)))],
                       'LINEAR')
            SP.boom(ks[-1][1] + Vector((0, 0, 1)), ks[-1][0], 2.0, hot=(0.55, 0.45, 0.4), cool=(0.3, 0.25, 0.22), life=0.8)
            SP.show(r, f0, G_END)
        lt = bpy.data.objects.new('CrackLight', bpy.data.lights.new('CrackLight', 'POINT'))
        SP.link(lt)
        lt.location = (0, 0, 8)
        lt.data.color = VIOLET
        lt.data.shadow_soft_size = 30
        for f, e in [(1, 0), (T_SPLIT, 0), (T_SPLIT + 12, 1.5e6), (T_RISE + 20, 2e6)]:
            lt.data.energy = e
            lt.data.keyframe_insert('energy', frame=f)
        # the Shard itself (cinematic build, without its ruin ring), rising out of the crack
        import shard_hd
        crystal = shard_hd.shard_hd('Shard', height=42.0)
        for nm in ('Shard_Ruins', 'Shard_Lightning'):
            o = bpy.data.objects.get(nm)
            if o:
                bpy.data.objects.remove(o)
        root = bpy.data.objects.new('ShardRoot', None)
        SP.link(root)
        for nm in ('Shard', 'Shard_Core', 'Shard_Splinters', 'Shard_Ribbons', 'Shard_Light'):
            o = bpy.data.objects.get(nm)
            if o:
                o.parent = root
        root.scale = (SHARD_K,) * 3
        spl = bpy.data.objects.get('Shard_Splinters')      # its orbiting splinters only once it stands (v4)
        if spl:
            SP.show(spl, T_PULSE, G_END)
        SP.key_loc(root, [(1, (0, 0, -70 * SHARD_K)), (T_RISE - 4, (0, 0, -60 * SHARD_K)), (T_RISE + 12, (0, 0, -30 * SHARD_K)),
                          (T_PULSE - 6, (0, 0, -8 * SHARD_K)), (T_PULSE, (0, 0, -6 * SHARD_K)), (G_END, (0, 0, -5.5 * SHARD_K))],
                   'BEZIER')
        SP.key_rot(root, [(1, (0, 0, 0)), (G_END, (0, 0, 40))], 'LINEAR')
        SP.show(root, T_RISE - 6, G_END)
        self.shard_root = root
        self.tip = lambda f: Vector((0, 0, -5.5 * SHARD_K + 52 * SHARD_K))
        core = bpy.data.objects.get('Shard_Core')
        cm_ = core.data.materials[0]
        em = next(n for n in cm_.node_tree.nodes if n.type == 'EMISSION')
        for f, s in [(1, 4.0), (T_GLOW, 4.0), (T_STRIKE_T, 30.0), (T_BEAMS, 45.0), (G_END, 50.0)]:
            em.inputs[1].default_value = s
            em.inputs[1].keyframe_insert('default_value', frame=f)
        sl = bpy.data.objects.get('Shard_Light')
        if sl:
            for f, e in [(1, 0), (T_RISE, 0), (T_RISE + 20, 1e6), (T_GLOW, 1e6), (T_STRIKE_T, 4e6), (G_END, 5e6)]:
                sl.data.energy = e
                sl.data.keyframe_insert('energy', frame=f)
        # dust and rock sliding off as it rises
        for i in range(8):
            dm = dust_mat(SP._uid('ShardDustM'), (0.38, 0.3, 0.3))
            d = C.uv_sphere(SP._uid('ShardDust'), 1.0, seg=(18, 10), mat=dm)
            a = i / 8 * 2 * math.pi
            p = Vector((math.cos(a) * 30, math.sin(a) * 30, 6))
            SP.key_loc(d, [(T_RISE, p), (T_RISE + 60, p * 2.2 + Vector((0, 0, 30)))], 'BEZIER')
            SP.key_scale(d, [(T_RISE, 9.0), (T_RISE + 60, 30.0)], 'BEZIER')
            SP.key_node(dm, 'V', [(T_RISE, 0.4), (T_RISE + 70, 0.0)])
            SP.show(d, T_RISE, T_RISE + 70)
            d.visible_shadow = False
        # the fan of violet beams straight up (0:54)
        top = Vector((0, 0, -5.5 * SHARD_K + 52 * SHARD_K))
        for k in range(9):
            a = k / 9 * 2 * math.pi
            d = Vector((math.cos(a) * 0.22, math.sin(a) * 0.22, 1.0)).normalized() if k else Vector((0, 0, 1))
            SP.beam(top, d, f'SkyBeam{k}', VIOLET, (0.8, 0.6, 1.0), 9.0 if k == 0 else 5.0,
                    [(T_BEAMS + k % 3, 5.0, 1.0), (T_BEAMS + 6 + k % 3, 2400.0, 1.0), (G_END, 2400.0, 1.0)],
                    strength=12.0, glow=4.0)
        SP.key_node(self.cloud_mat, 'holeR', [(1, 0.0), (T_BEAMS + 4, 0.0), (G_END, 1500.0)])
        SP.key_node(self.cloud_mat, 'rimK', [(1, 0.0), (T_BEAMS + 4, 0.0), (T_BEAMS + 8, 3.0), (G_END, 1.5)])

    # ------------------------------------------------------------ lightning and the crystal crust (0:52-0:53)
    def strikes(self):
        rnd = random.Random(3808)
        crust_m = NP.crystal_mat()
        ctm = self.ctmpl
        top = Vector((0, 0, 75))
        sc = bpy.context.scene
        for side, f0 in ((-1, T_STRIKE_T), (1, T_STRIKE_A)):
            us = self.units[side]
            sc.frame_set(f0)
            pos = [o.matrix_world.translation.copy() for o in us]
            if side < 0:
                pos.append(self.hero_path(f0))
            # lightning: a few forked bolts per 2 frames from the Shard's lower spikes into the line
            for n_, f in enumerate(range(f0, f0 + 18, 2)):
                pairs = []
                for q in range(5):
                    tgt = pos[rnd.randrange(len(pos))] + Vector((0, 0, 2))
                    src = top + Vector((side * 22, rnd.uniform(-12, 12), rnd.uniform(-10, 25)))
                    pairs.append((src, tgt))
                SP.flicker_lightning(pairs, 3900 + n_ + (0 if side < 0 else 50), f, f + 1, every=1, width=0.5,
                                     name=SP._uid('ShardBolt'), zone_col=(0.7, 0.45, 1.0), strength=30.0)
            # v3: the big forked bolts (shard_fx): thick violet channels with branches, impact flash and
            # scorched glowing ground, three volleys of three
            import shard_fx
            for v in range(3):
                fv = f0 + v * 5
                for q in range(3):
                    tgt = pos[rnd.randrange(len(pos))] + Vector((0, 0, 1.5))
                    src = top + Vector((side * rnd.uniform(14, 26), rnd.uniform(-14, 14), rnd.uniform(-20, 20)))
                    for o in shard_fx.lightning(src, tgt, seed=5000 + v * 10 + q + (0 if side < 0 else 500), width=0.9,
                                                name=SP._uid('HeroBolt')):
                        SP.show(o, fv, fv + 3)
            # crust: violet crystal clusters growing over every tank, nearest the Shard first
            for i, p in enumerate(pos):
                fc = f0 + 2 + int(abs(p.x) / 25) + rnd.randint(0, 6)
                o = bpy.data.objects.new(f'Crust{side}_{i}', ctm[rnd.randrange(len(ctm))].data)
                SP.link(o)
                if o.material_slots:
                    o.material_slots[0].link = 'OBJECT'
                    o.material_slots[0].material = crust_m
                if i < len(us):
                    o.parent = us[i]
                    o.location = (0, 0, 0.5)
                else:
                    o.parent = self.hero_obj
                    o.location = (0, 0, 0.5)
                o.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
                s = rnd.uniform(3.2, 4.5)
                SP.key_scale(o, [(fc, 0.05), (fc + 7, s)], 'BEZIER')
                SP.show(o, fc, G_END)
                if i % 9 == 0:
                    SP.violet_boom(p + Vector((0, 0, 2)), fc, 3.0, life=0.3)
        # their lights go out
        key_emission(set(self.lancer_mats), [(1, 1.0), (T_STRIKE_T + 6, 1.0), (T_STRIKE_T + 16, 0.0)])
        key_emission(set(self.stinger_mats), [(1, 1.0), (T_STRIKE_A + 6, 1.0), (T_STRIKE_A + 16, 0.0)])
        for side, f0 in ((-1, T_STRIKE_T), (1, T_STRIKE_A)):
            em = next(n for n in self.beacon_mats[side].node_tree.nodes if n.type in ('EMISSION', 'BSDF_PRINCIPLED'))
            sock = em.inputs['Strength'] if em.type == 'EMISSION' else em.inputs['Emission Strength']
            for f, v in ((1, sock.default_value), (f0 + 6, sock.default_value), (f0 + 16, 0.0)):
                sock.default_value = v
                sock.keyframe_insert('default_value', frame=f)

    # ------------------------------------------------------------ violet pulses and the spread
    def violet_keys(self):
        mats = [self.gmat, self.cmat]
        for m in mats:
            # pulse 1 (0:38): under the crystals below the falling drop ship, a quarter second
            # pulse 2 (0:42): a ripple across the valley floor, half a second
            # pulse 3 (0:50): the Shard's pulse rolling across both armies
            keys = {'ringX': [(1, -700.0), (T_WIDE, -700.0), (T_WIDE + 1, 0.0), (T_PULSE, 0.0)],
                    'ringY': [(1, 60.0), (T_WIDE, 60.0), (T_WIDE + 1, -150.0), (T_PULSE - 1, -150.0), (T_PULSE, 0.0)],
                    'ringR': [(1, -999.0), (T_DROP - 1, -999.0), (T_DROP, 0.0), (T_DROP + 6, 260.0), (T_DROP + 7, -999.0),
                              (T_WIDE, 0.0), (T_WIDE + 12, 900.0), (T_WIDE + 13, -999.0),
                              (T_PULSE, 0.0), (T_PULSE + 24, 1400.0)],
                    'ringK': [(1, 1.0), (T_WIDE - 1, 1.0), (T_WIDE, 0.4), (T_WIDE + 13, 0.4), (T_WIDE + 14, 1.0),
                              (T_PULSE, 1.4), (T_PULSE + 24, 0.4)]}
            for name, ks in keys.items():
                SP.key_node(m, name, ks, 'CONSTANT' if name in ('ringX', 'ringY') else 'LINEAR')
            hx = self.hero_path(T_SPREAD)
            SP.key_node(m, 'sprX', [(1, hx.x)], 'CONSTANT')
            SP.key_node(m, 'sprY', [(1, hx.y)], 'CONSTANT')
            SP.key_node(m, 'sprR', [(1, -10.0), (T_SPREAD + 4, -10.0), (T_SPREAD + 24, 1600.0)])
        SP.key_node(self.gmat, 'crackK', [(1, 0.0), (T_SPLIT, 0.0), (T_SPLIT + 12, 1.0), (T_PULSE, 2.0)])
        SP.key_node(self.cmat, 'glowK', [(1, 1.0), (T_PULSE, 1.0), (T_PULSE + 6, 2.2), (T_STRIKE_T, 1.6)])

    # ------------------------------------------------------------ cameras
    def camera_for(self, sid):
        sc = bpy.context.scene
        H = self.hero_path
        if sid == '08b':
            ds = self.drops[0]
            keys = []
            for f in range(fr(34.6), fr(39), 2):
                sc.frame_set(f)
                p = ds.matrix_world.translation.copy()
                c = ramp(f, fr(34.6), fr(39))
                keys.append((f, p + Vector((30, -62, -16)) * (1.25 - 0.45 * c), p + Vector((10, 0, -6 - 4 * (1 - c))),
                             30 - 2 * c))
            keys.append((fr(39) - 1,) + keys[-1][1:])
            return keys
        if sid == '09a':
            pad = self.pads[0]
            c = pad + Vector((78, -34, 3.5))
            return [(fr(39), c, pad + Vector((0, 0, 11)), 24), (fr(40), c + Vector((2, -3, 0)), pad + Vector((10, 0, 6)), 24),
                    (fr(41) - 1, c + Vector((4, -6, 0)), pad + Vector((30, 2, 4)), 24)]
        if sid == '09b':
            c = Vector((606, -205, self.zat(606, -205) + 3.5))
            return [(fr(41), c, Vector((680, -90, 8)), 30), (fr(42) - 1, c + Vector((4, 3, 0.5)), Vector((675, -85, 11)), 30)]
        if sid == '09c':
            return [(fr(42), Vector((-430, -70, 105)), Vector((160, 0, 0)), 24),
                    (fr(44) - 1, Vector((-360, -60, 95)), Vector((180, 0, 0)), 24)]
        if sid == '09d':
            keys = []
            for f in range(fr(44), fr(47), 2):
                h = H(f)
                tilt = ramp(f, fr(46.0), fr(46.6))
                pos = h + Vector((-9, -12, 3.2)) + Vector((4, 2, -1.2)) * tilt
                tgt = h + Vector((35, 2, 2)).lerp(Vector((2, 0, -0.5)), tilt)
                keys.append((f, pos, tgt, 22))
            keys.append((fr(47) - 1,) + keys[-1][1:])
            return keys
        if sid == '10a':
            c = Vector((4, -110, 3))
            return [(fr(47), c, Vector((0, 60, 4)), 24), (fr(48), c, Vector((0, 20, 8)), 24),
                    (fr(49) - 1, c + Vector((-2, -5, 0)), Vector((0, 0, 90)), 22)]
        if sid == '10b':
            c = Vector((-470, -190, self.zat(-470, -190) + 18))
            return [(fr(49), c, Vector((0, 0, 140)), 28), (fr(51) - 1, c + Vector((6, 2, 0)), Vector((0, 0, 145)), 28)]
        if sid == '10c':
            keys = []
            for f in range(fr(51), fr(54), 2):
                h = H(f)
                swing = ramp(f, fr(52.8), fr(53.3))
                ax = Vector((-h.x, -h.y, 0)).normalized()          # from our Lancer toward the Shard
                pos = h - ax * 15 + Vector((0, 0, 3.0))
                pos = pos.lerp(Vector((90, -60, 14)), swing)
                tgt = Vector((0, 0, 16)).lerp(h + ax * 40 + Vector((0, 0, 2)), ramp(f, fr(51.9), fr(52.3)) * (1 - swing))
                tgt = tgt.lerp(Vector((60, 30, 2)), swing)
                keys.append((f, pos, tgt, 18 + 4 * swing))
            keys.append((fr(54) - 1,) + keys[-1][1:])
            return keys
        if sid == '10d':
            c = Vector((-1000, -200, self.zat(-1000, -200) + 40))
            return [(fr(54), c, Vector((0, 0, 420)), 24), (fr(55) - 1, c, Vector((0, 0, 440)), 24)]
        return None
