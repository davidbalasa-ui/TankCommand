"""v3 ground battle on Vesper (scenes 12, 13, 14), rebuilt 2026-11-17 to the v3 shot plan.

One battle clock G (global frames) shared by the three scenes, so armies, fire and the Shard stay
continuous across the cuts:
    s12 ground clash     G   1..288   (12 s)
    s13 the Shard rises  G 289..528   (10 s)
    s14 the Shard strikes G 529..672  ( 6 s)
Each scene builds only what its own window needs (Field(scene=...)) and plays back through tmap.

Layout: the valley runs along X. Terrans come from the west (-X), Arcadians from the east (+X); their
front ranks close from +-255 m to +-80 m and stop either side of the origin, where the ground splits
and the Shard rises. Everything is computed analytically from fixed seeds (no scene evaluation), so the
build is quick.

Look (David's direction): dark basalt ground with rocks, crystals, dust and long low-sun shadows; a
loose, mixed army on each side (every game unit, aircraft over the tanks); every unit type has its own
fire rhythm (scouts fast and light, heavies one big blast a second, artillery three shells in a second
then reload); Terran blue fire, Arcadian gold (Arcadian propulsion is lightning, never flame).
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Vector, Quaternion, Matrix, noise

import space as SP
import common as C
import barrage_pieces as BP
import ground as GR
import shard_fx as SFX
from squid import bake, ramp

FPS = 24
SCENES = {'s12': (0, 288), 's13': (288, 240), 's14': (528, 144)}   # offset, frames
MODELS = GR.MODELS

BLUE = (0.25, 0.65, 1.0)
BLUE_HOT = (0.75, 0.92, 1.0)
GOLD = (1.0, 0.62, 0.15)
GOLD_HOT = (1.0, 0.9, 0.6)
VIOLET = (0.42, 0.1, 1.0)
HAZE = (0.30, 0.15, 0.10)

SHARD_K = 3.8
SUN_X, SUN_Z = 76.0, 40.0      # sun 14 deg up, from the east and a little south: long shadows across the lanes
BRK = 288                  # armies coast to a stop
G_SPLIT = 298              # the crack opens
G_BREACH = 336             # the Shard's tip breaks the ground
G_RISEN = 470
G_PULSE = 238              # first violet pulse through the ground (s12)
G_PULSE2 = 486             # the risen Shard pulses (s13)
G_STRIKE_T = 545           # lightning into the Terran line (s14)
G_STRIKE_A = 606           # ... into the Arcadians


# ================================================================== terrain
def height(x, y):
    """Gently rolling valley floor; walls beyond |y| = 300; the ends of the valley rise too."""
    h = 5.0 * noise.noise(Vector((x * 0.0035, y * 0.0035, 0.3))) + 1.6 * noise.noise(Vector((x * 0.014, y * 0.014, 1.7)))
    h += 0.35 * noise.noise(Vector((x * 0.07, y * 0.07, 4.1)))
    ay = abs(y)
    w = max(0.0, min(1.0, (ay - 300) / 420.0))
    h += 230.0 * (w * w * (3 - 2 * w)) * (0.75 + 0.5 * noise.noise(Vector((x * 0.002, y * 0.002, 9.0))))
    h += 60.0 * w * abs(noise.noise(Vector((x * 0.006, y * 0.006, 5.0))))
    ax = abs(x)
    e = max(0.0, min(1.0, (ax - 1300) / 700.0))
    h += 90.0 * e * e * (0.7 + 0.6 * abs(noise.noise(Vector((x * 0.003, y * 0.003, 2.0)))))
    return h


def _haze_mix(n, shader_sock, k=2200.0):
    """Mix a surface shader toward the dusk haze with camera distance."""
    cd = n.node('ShaderNodeCameraData')
    f = n.math('SUBTRACT', 1.0, n.math('EXPONENT', n.math('DIVIDE', n.math('MULTIPLY', cd.outputs['View Distance'], -1.0), k)))
    em = n.node('ShaderNodeEmission', Color=(*HAZE, 1), Strength=1.0)
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], n.math('MULTIPLY', f, 0.85))
    n.set(mx.inputs[1], shader_sock)
    n.set(mx.inputs[2], em.outputs[0])
    return mx.outputs[0]


def _val(m, name, v):
    nd = m.node_tree.nodes.new('ShaderNodeValue')
    nd.name = name
    nd.outputs[0].default_value = v
    return nd.outputs[0]


def _pulse(m, n, pos):
    """Violet pulse ring (ringR, ringK keyed) and spread disc (sprR keyed) around the origin, from world pos."""
    sep = n.node('ShaderNodeSeparateXYZ')
    n.set(sep.inputs[0], pos)
    d = n.math('SQRT', n.math('ADD', n.math('MULTIPLY', sep.outputs[0], sep.outputs[0]),
                              n.math('MULTIPLY', sep.outputs[1], sep.outputs[1])))
    ring = n.math('MULTIPLY', n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', d, _val(m, 'ringR', -999.0))), 0.0, 30.0, 1.0, 0.0),
                  _val(m, 'ringK', 0.0))
    tail = n.math('MULTIPLY', n.maprange(n.math('SUBTRACT', _val(m, 'ringR2', -999.0), d), 0.0, 160.0, 1.0, 0.0),
                  n.math('MULTIPLY', n.math('GREATER_THAN', _val(m, 'ringR2', -999.0), d), 0.35))
    spr = n.maprange(n.math('SUBTRACT', d, _val(m, 'sprR', -10.0)), 0.0, 40.0, 1.0, 0.0)
    return n.math('ADD', ring, n.math('MULTIPLY', tail, _val(m, 'ringK2', 0.0))), spr, d


def ground_mat():
    """Dark basalt and rust dust: big colour patches, cracked plates, pebbles, wheel-worn dust; violet
    veins that light where a pulse ring passes or the spread has reached."""
    m, n = BP._new_mat('Vesper3Ground')
    geo = n.node('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.93)
    big = n.node('ShaderNodeTexNoise', Scale=0.004, Detail=6.0, Roughness=0.55)
    n.set(big.inputs['Vector'], pos)
    mid = n.node('ShaderNodeTexNoise', Scale=0.05, Detail=8.0, Roughness=0.6)
    n.set(mid.inputs['Vector'], pos)
    rmp = n.node('ShaderNodeValToRGB')
    n.set(rmp.inputs[0], n.math('ADD', n.math('MULTIPLY', big.outputs['Fac'], 0.7), n.math('MULTIPLY', mid.outputs['Fac'], 0.3)))
    cr = rmp.color_ramp
    cr.elements[0].position = 0.35
    cr.elements[0].color = (0.022, 0.019, 0.02, 1)       # basalt
    cr.elements[1].position = 0.62
    cr.elements[1].color = (0.16, 0.08, 0.05, 1)         # rust dust
    e = cr.elements.new(0.5)
    e.color = (0.07, 0.05, 0.04, 1)
    # cracked plates: voronoi edges darker, cells slightly varied
    wn = n.node('ShaderNodeTexNoise', Scale=0.25, Detail=3.0)
    n.set(wn.inputs['Vector'], pos)
    wpos = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    wpos.inputs[1].default_value = (2.2, 2.2, 2.2)
    n.set(wpos.inputs[0], wn.outputs['Color'])
    n.set(wpos.inputs[2], pos)
    vor = n.node('ShaderNodeTexVoronoi', Scale=0.22)
    vor.feature = 'DISTANCE_TO_EDGE'
    n.set(vor.inputs['Vector'], wpos.outputs[0])
    pm = n.node('ShaderNodeTexNoise', Scale=0.03, Detail=3.0)
    n.set(pm.inputs['Vector'], pos)
    plate = n.maprange(pm.outputs['Fac'], 0.48, 0.6, 0.0, 1.0)
    edge = n.math('ADD', n.maprange(vor.outputs['Distance'], 0.0, 0.035, 0.0, 1.0), n.math('SUBTRACT', 1.0, plate))
    edge = n.math('MINIMUM', edge, 1.0)
    vc = n.node('ShaderNodeTexVoronoi', Scale=0.22)
    n.set(vc.inputs['Vector'], wpos.outputs[0])
    cellv = n.maprange(vc.outputs['Distance'], 0.0, 1.0, 0.8, 1.15)
    fine = n.node('ShaderNodeTexNoise', Scale=3.0, Detail=10.0, Roughness=0.7)
    n.set(fine.inputs['Vector'], pos)
    speck = n.maprange(fine.outputs['Fac'], 0.3, 0.75, 0.7, 1.3)
    k = n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY_ADD', edge, 0.45, 0.55), cellv), speck)
    col = n.node('ShaderNodeMix')
    col.data_type = 'RGBA'
    col.blend_type = 'MULTIPLY'
    col.inputs[0].default_value = 1.0
    n.set(col.inputs[6], rmp.outputs[0])
    n.set(col.inputs[7], n.node('ShaderNodeCombineXYZ', X=k, Y=k, Z=k).outputs[0])
    n.set(b.inputs['Base Color'], col.outputs[2])
    hb = n.math('ADD', n.math('MULTIPLY', edge, 0.35), n.math('MULTIPLY', fine.outputs['Fac'], 0.6))
    bump = n.node('ShaderNodeBump', Strength=0.6, Distance=0.3)
    n.set(bump.inputs['Height'], hb)
    n.set(b.inputs['Normal'], bump.outputs[0])
    # violet veins (warped voronoi edges, ~16 m cells) with a soft glow round them
    tc = pos
    warp = n.node('ShaderNodeTexNoise', Scale=0.02, Detail=5.0)
    n.set(warp.inputs['Vector'], tc)
    vm = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    vm.inputs[1].default_value = (34.0, 34.0, 34.0)
    n.set(vm.inputs[0], warp.outputs['Color'])
    n.set(vm.inputs[2], tc)
    vv = n.node('ShaderNodeTexVoronoi', Scale=0.06, Randomness=1.0)
    vv.feature = 'DISTANCE_TO_EDGE'
    n.set(vv.inputs['Vector'], vm.outputs[0])
    core = n.maprange(vv.outputs['Distance'], 0.006, 0.02, 1.0, 0.0)
    soft = n.math('MULTIPLY', n.maprange(vv.outputs['Distance'], 0.0, 0.07, 1.0, 0.0), 0.08)
    vein = n.math('ADD', core, soft)
    ring, spr, d = _pulse(m, n, pos)
    crack = n.math('MULTIPLY', _val(m, 'crackK', 0.0), n.maprange(d, 20.0, 200.0, 1.0, 0.0))
    kk = n.math('ADD', n.math('ADD', n.math('MULTIPLY', ring, 6.0), n.math('MULTIPLY', spr, 0.5)), crack)
    b.inputs['Emission Color'].default_value = (*VIOLET, 1)
    n.set(b.inputs['Emission Strength'], n.math('MULTIPLY', vein, kk))
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], _haze_mix(n, b.outputs[0]))
    return m


def rock_mat():
    m, n = BP._new_mat('Vesper3Rock')
    geo = n.node('ShaderNodeNewGeometry')
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.85)
    nz = n.node('ShaderNodeTexNoise', Scale=0.9, Detail=8.0, Roughness=0.65)
    n.set(nz.inputs['Vector'], geo.outputs['Position'])
    n.set(b.inputs['Base Color'], n.mix(nz.outputs['Fac'], (0.018, 0.016, 0.017), (0.09, 0.055, 0.04)))
    bump = n.node('ShaderNodeBump', Strength=0.5)
    n.set(bump.inputs['Height'], nz.outputs['Fac'])
    n.set(b.inputs['Normal'], bump.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], _haze_mix(n, b.outputs[0]))
    return m


def crystal_mat():
    """Valley crystals: dark smoky violet glass, faint inner glow; flare violet when a pulse passes."""
    m, n = BP._new_mat('Vesper3Crystal')
    geo = n.node('ShaderNodeNewGeometry')
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.1, IOR=1.6)
    b.inputs['Base Color'].default_value = (0.16, 0.07, 0.3, 1)
    b.inputs['Transmission Weight'].default_value = 0.75
    ring, spr, d = _pulse(m, n, geo.outputs['Position'])
    lw = n.node('ShaderNodeLayerWeight', Blend=0.3)
    s = n.maprange(lw.outputs['Facing'], 0.0, 1.0, 0.04, 0.3)
    s = n.math('ADD', s, n.math('ADD', n.math('MULTIPLY', ring, 2.5), n.math('MULTIPLY', spr, 1.5)))
    s = n.math('MINIMUM', n.math('MULTIPLY', s, _val(m, 'glowK', 1.0)), 1.2)
    b.inputs['Emission Color'].default_value = (0.4, 0.1, 1.0, 1)
    n.set(b.inputs['Emission Strength'], s)
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], b.outputs[0])
    return m


def _rock_mesh(name, seed, sq=(1, 1, 0.7), sub=2):
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    cuts = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 1))).normalized(), rnd.uniform(0.6, 0.9))
            for _ in range(5)]
    for v in bm.verts:
        p = v.co.copy()
        p *= 1 + 0.35 * noise.noise(p * 1.3 + off) + 0.15 * noise.noise(p * 3.1 + off)
        for nrm, dd in cuts:
            if p.dot(nrm) > dd:
                p -= nrm * (p.dot(nrm) - dd)
        p.x *= sq[0]
        p.y *= sq[1]
        p.z *= sq[2]
        if p.z < -0.25:
            p.z = -0.25 + (p.z + 0.25) * 0.3
        v.co = p
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    SP.link(ob)
    ob.hide_render = True
    ob.location = (0, 0, -5000)
    return ob


def _crystal_mesh(name, seed, mat):
    import shard_hd
    rnd = random.Random(seed)
    bm = bmesh.new()
    for i in range(rnd.randint(4, 9)):
        h = rnd.uniform(0.5, 1.4)
        d = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 1.0)
        shard_hd._spire(bm, (rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), -0.2), d, h, h * rnd.uniform(0.12, 0.2), rnd)
    ob = shard_hd._obj(name, bm)
    ob.data.materials.append(mat)
    ob.hide_render = True
    ob.location = (0, 0, -5000)
    return ob


def _join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


# ================================================================== unit roster
# kind: (faction dir, model, role, muzzle local (x, z), fire spec or None, hover height)
# fire spec: (pattern, period, burst, gap, weapon) ; pattern 'single' | 'burst'
ROSTER = {
    -1: {
        'lancer':     ('human', 'tank',  (6.4, 2.6), ('burst', 19, 1, 0, 'bolt'), 0.0, 26),
        'bulwark':    ('human', 'heavy', (8.5, 2.9), ('burst', 24, 1, 0, 'heavy'), 0.0, 9),
        'outrider':   ('human', 'scout', (3.2, 2.3), ('burst', 14, 3, 3, 'light'), 0.0, 8),
        'skimmer':    ('human', 'tank',  (4.3, 2.4), ('burst', 20, 1, 0, 'bolt'), 0.6, 7),
        'javelin':    ('human', 'missile', (0.5, 3.6), ('burst', 52, 2, 5, 'missile'), 0.0, 8),
        'longbow':    ('human', 'arty',  (7.4, 6.8), ('burst', 66, 3, 8, 'shell'), 0.0, 7),
        'hauler':     ('human', 'support', None, None, 0.0, 3),
        'mender':     ('human', 'support', None, None, 0.0, 3),
        'watchman':   ('human', 'support', None, None, 0.0, 2),
        'prospector': ('human', 'support', None, None, 0.0, 2),
    },
    1: {
        'stinger':      ('alien', 'tank',  (5.2, 2.6), ('burst', 19, 1, 0, 'bolt'), 1.4, 24),
        'carapace':     ('alien', 'heavy', (7.0, 3.0), ('burst', 24, 1, 0, 'heavy'), 1.2, 9),
        'darter':       ('alien', 'scout', (3.8, 1.8), ('burst', 14, 3, 3, 'light'), 1.6, 9),
        'glider':       ('alien', 'tank',  (4.2, 1.9), ('burst', 20, 1, 0, 'bolt'), 1.8, 8),
        'spitter':      ('alien', 'missile', (2.8, 3.6), ('burst', 52, 2, 5, 'missile'), 1.3, 8),
        'mortar_beast': ('alien', 'arty',  (2.4, 4.4), ('burst', 66, 3, 8, 'shell'), 1.3, 7),
        'ferrier':      ('alien', 'support', None, None, 1.5, 3),
        'weaver':       ('alien', 'support', None, None, 1.5, 3),
        'gorger':       ('alien', 'support', None, None, 1.4, 2),
        'seer':         ('alien', 'support', None, None, 1.5, 2),
    },
}
BACK = {'scout': (-22, 0), 'tank': (0, 45), 'heavy': (0, 30), 'missile': (25, 65), 'arty': (95, 140),
        'support': (60, 125)}
AIR = {-1: [('falcon', 10), ('condor', 5)], 1: [('dragonfly', 9), ('disc', 6), ('halo', 5)]}
WEAPON = {   # speed m/frame, core width, length, colour boost
    'light': (11.0, 0.08, 4.0), 'bolt': (10.0, 0.12, 8.0), 'heavy': (9.0, 0.24, 11.0),
    'missile': (5.0, 0.35, 1.2), 'shell': (0.0, 0.5, 1.0),
}
HERO_Y = 8.0


class Unit:
    __slots__ = ('side', 'kind', 'role', 'y0', 'back', 'ph', 'lag', 'hover', 'muzzle', 'fire', 'obj', 'tmpl',
                 'freeze', 'drop', 'name', 'sway')


def front(G):
    """x of a side's front rank: fast roll-out, slowing as the lines close, stopped at ~81 m."""
    if G <= BRK:
        return 80.0 + 175.0 * (1 - G / 330.0) ** 2
    v = 2 * 175.0 * (1 - BRK / 330.0) / 330.0
    t = min(G - BRK, 30)
    return 80.0 + 175.0 * (1 - BRK / 330.0) ** 2 - v * (t - t * t / 60.0)


class Field:
    def __init__(self, scene='s12', draft=True, air_plan=(), focus=None):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        self.scene = scene
        self.draft = draft
        self.air_plan = list(air_plan)
        self.focus = focus or {-1: (-95.0, 0.0), 1: (95.0, 0.0)}
        off, nf = SCENES[scene]
        self.off, self.nf = off, nf
        self.G0, self.G1 = off + 1, off + nf
        self.sh = C.Shot(nf / FPS, FPS, draft)
        sc = bpy.context.scene
        sc.frame_start, sc.frame_end = 1, nf
        SP.OS.NF = off + nf + 30
        self.shots = []
        self.fx = []
        self.rnd = random.Random(4400)
        self.lights_budget = 70
        self.boom_budget = 120 if scene == 's12' else 30
        self.world()
        self.terrain()
        self.scatter()
        self.army()
        self.hover_fx()
        if scene in ('s12', 's13'):
            self.dust_trails()
        self.aircraft()
        if scene in ('s12', 's13'):
            self.gunfire()
        self.pulses()
        if scene in ('s13', 's14'):
            self.shard()
        if scene == 's13':
            self.split()
        if scene == 's14':
            self.strikes()
        bpy.context.scene.frame_set(self.G0)

    # ------------------------------------------------------------ clock
    def tmap(self, f):
        return f + self.off

    def in_win(self, G, pad=40):
        return self.G0 - pad <= G <= self.G1 + 5

    # ------------------------------------------------------------ sky and sun
    def sky(self):
        """Dusk: rust horizon glowing toward the sun, deep blue-violet overhead, thin high cloud bands."""
        w = bpy.data.worlds.new('Vesper3Sky')
        bpy.context.scene.world = w
        w.use_nodes = True
        nt = w.node_tree
        for nd in list(nt.nodes):
            nt.nodes.remove(nd)
        n = BP._NT(w)
        tc = n.node('ShaderNodeTexCoord')
        d = n.node('ShaderNodeVectorMath', operation='NORMALIZE')
        n.set(d.inputs[0], tc.outputs['Generated'])
        sep = n.node('ShaderNodeSeparateXYZ')
        n.set(sep.inputs[0], d.outputs[0])
        z = n.math('MAXIMUM', sep.outputs[2], 0.0)
        g = n.math('POWER', n.maprange(z, 0.0, 0.85, 0.0, 1.0), 0.55)
        col = n.mix(g, (0.55, 0.24, 0.13), (0.03, 0.03, 0.08))
        sd = Vector((math.sin(math.radians(SUN_Z)) * math.sin(math.radians(SUN_X)),
                     -math.cos(math.radians(SUN_Z)) * math.sin(math.radians(SUN_X)), math.cos(math.radians(SUN_X))))
        dp = n.node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
        n.set(dp.inputs[0], d.outputs[0])
        dp.inputs[1].default_value = tuple(sd)
        sg = n.math('POWER', n.math('MAXIMUM', dp.outputs['Value'], 0.0), 8.0)
        col = n.mix(n.math('MULTIPLY', sg, 0.7), col, (1.0, 0.5, 0.22))
        # high cloud streaks, lit warm on the sun side
        cn = n.node('ShaderNodeTexNoise', Scale=2.5, Detail=6.0, Roughness=0.55)
        sv = n.node('ShaderNodeVectorMath', operation='MULTIPLY')
        n.set(sv.inputs[0], d.outputs[0])
        sv.inputs[1].default_value = (0.6, 2.2, 6.0)
        n.set(cn.inputs['Vector'], sv.outputs[0])
        cl = n.math('MULTIPLY', n.maprange(cn.outputs['Fac'], 0.52, 0.72, 0.0, 0.55),
                    n.maprange(z, 0.02, 0.3, 0.0, 1.0))
        col = n.mix(cl, col, (0.35, 0.17, 0.12))
        bg = n.node('ShaderNodeBackground')
        n.set(bg.inputs['Color'], col)
        bg.inputs['Strength'].default_value = 1.0
        out = n.node('ShaderNodeOutputWorld')
        n.set(out.inputs['Surface'], bg.outputs[0])

    def cull_near_camera(self, r=10.0):
        """Drop shots/flashes that would pass right through the lens (they read as white smears)."""
        def cam_at(keys, G):
            for (fa, pa, *_), (fb, pb, *_) in zip(keys, keys[1:]):
                if fa <= G <= fb:
                    return pa.lerp(pb, (G - fa) / max(1, fb - fa))
            return None
        dead = 0
        for o, f0, f1, posf, rad in self.fx:
            if o.name not in bpy.data.objects:
                continue
            hit = False
            for sid, a, b, keys, shake in self.shots:
                ga, gb = a + self.off, b + self.off
                for G in range(max(f0, ga), min(f1, gb) + 1):
                    c = cam_at(keys, G)
                    if c is not None and (posf(G) - c).length < r + rad:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                for x in [o] + list(o.children_recursive):
                    bpy.data.objects.remove(x)
                dead += 1
        print('culled', dead, 'of', len(self.fx))

    def world(self):
        self.sky()
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        SP.link(sun)
        sun.data.energy = 5.5
        sun.data.color = (1.0, 0.6, 0.36)
        sun.data.angle = math.radians(1.2)
        sun.rotation_euler = (math.radians(SUN_X), 0, math.radians(SUN_Z))     # low, from the Arcadian end
        self.sun = sun
        # cool fill from the other side so shadows are not black
        fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'SUN'))
        SP.link(fill)
        fill.data.energy = 0.25
        fill.data.color = (0.45, 0.5, 1.0)
        fill.data.angle = math.radians(20)
        fill.rotation_euler = (math.radians(50), 0, math.radians(-70))
        fill.data.use_shadow = False
        # a sun disc low over the east ridge
        d = Vector((math.sin(math.radians(SUN_Z)) * math.sin(math.radians(SUN_X)),
                    -math.cos(math.radians(SUN_Z)) * math.sin(math.radians(SUN_X)), math.cos(math.radians(SUN_X))))
        p = d * 30000
        disc = C.uv_sphere('SunDisc3', 260, seg=(24, 12), mat=SP.emit('SunDisc3M', (1.0, 0.7, 0.45), 30.0))
        disc.location = p
        glow = C.uv_sphere('SunGlow3', 1400, seg=(24, 12), mat=BP._halo_mat('SunGlow3M', (1.0, 0.45, 0.2), 1.2))
        glow.location = p
        for o in (disc, glow):
            o.visible_shadow = False

    def terrain(self):
        self.gmat = ground_mat()

        def grid(name, x0, x1, y0, y1, nx, ny, sink=None):
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=nx, y_subdivisions=ny, size=1)
            g = bpy.context.active_object
            g.name = name
            me = g.data
            co = [0.0] * (len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            for i in range(0, len(co), 3):
                x = x0 + (co[i] + 0.5) * (x1 - x0)
                y = y0 + (co[i + 1] + 0.5) * (y1 - y0)
                z = height(x, y)
                if sink:
                    z -= sink(x, y)
                co[i], co[i + 1], co[i + 2] = x, y, z
            me.vertices.foreach_set('co', co)
            me.update()
            for p in me.polygons:
                p.use_smooth = True
            me.materials.append(self.gmat)
            return g
        # fine patch where the cameras are, coarse valley round it (sunk under the patch)
        nf = 2.0 if not self.draft else 2.5
        self.fine = grid('Valley3Fine', -480, 480, -280, 280, int(960 / nf), int(560 / nf))

        def sink(x, y):
            kx = max(0.0, min(1.0, (470 - abs(x)) / 20.0))
            ky = max(0.0, min(1.0, (270 - abs(y)) / 20.0))
            return 1.5 * kx * ky
        self.coarse = grid('Valley3', -3000, 3000, -1600, 1600, 300, 160, sink)

    def zat(self, x, y):
        return height(x, y)

    # ------------------------------------------------------------ rocks, boulders, crystals
    def scatter(self):
        rnd = random.Random(4401)
        rm = rock_mat()
        self.rock_mat = rm
        rocks = []
        for k in range(10):
            r = _rock_mesh(f'RockT{k}', 4410 + k, sq=(rnd.uniform(0.8, 1.3), rnd.uniform(0.7, 1.1), rnd.uniform(0.45, 0.9)))
            r.data.materials.append(rm)
            rocks.append(r)
        self.rock_t = rocks
        cm = crystal_mat()
        self.cmat = cm
        crys = [_crystal_mesh(f'CrysT{k}', 4430 + k, cm) for k in range(8)]
        n = 0

        def put(t, x, y, s, sink=0.3, tilt=0.25):
            nonlocal n
            o = bpy.data.objects.new(f'Sc{n}', t.data)
            SP.link(o)
            o.location = (x, y, self.zat(x, y) - sink * s)
            o.rotation_euler = (rnd.uniform(-tilt, tilt), rnd.uniform(-tilt, tilt), rnd.uniform(0, 6.3))
            o.scale = (s, s, s)
            n += 1
            return o

        def in_army(x, y):
            return abs(x) < 380 and abs(y) < 200
        # pebbles and small rocks everywhere in the fine patch (units roll over them)
        for i in range(4200):
            x, y = rnd.uniform(-470, 470), rnd.uniform(-270, 270)
            s = rnd.uniform(0.2, 1.0) if in_army(x, y) else rnd.uniform(0.3, 1.8)
            put(rocks[rnd.randrange(10)], x, y, s)
        # boulders and outcrops off the army lanes, in clusters
        for c in range(70):
            cx, cy = rnd.uniform(-1300, 1300), rnd.choice((-1, 1)) * rnd.uniform(205, 520)
            if abs(cx) < 120 and abs(cy) < 260:
                continue
            for j in range(rnd.randint(3, 9)):
                x, y = cx + rnd.gauss(0, 18), cy + rnd.gauss(0, 14)
                if in_army(x, y):
                    continue
                put(rocks[rnd.randrange(10)], x, y, rnd.uniform(2.0, 9.0) * (2.0 if j == 0 else 1.0), sink=0.35)
        # a few boulders inside the battlefield, between lanes (units steer round them: kept out of lanes)
        for i in range(40):
            x, y = rnd.uniform(-420, 420), rnd.uniform(-195, 195)
            if abs(x) < 70:
                continue
            put(rocks[rnd.randrange(10)], x, y, rnd.uniform(1.0, 2.2), sink=0.4)
        # crystal clumps: patches across the field, a ring of them round where the Shard will rise
        for p in range(55):
            cx, cy = rnd.uniform(-900, 900), rnd.uniform(-330, 330)
            for i in range(rnd.randint(4, 14)):
                x, y = cx + rnd.gauss(0, 10), cy + rnd.gauss(0, 10)
                s = rnd.uniform(0.6, 2.2) if in_army(x, y) else rnd.uniform(1.5, 6.0)
                put(crys[rnd.randrange(8)], x, y, s, sink=0.15, tilt=0.35)
        for i in range(160):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(25, 75)
            put(crys[rnd.randrange(8)], r * math.cos(a), r * math.sin(a), rnd.uniform(1.0, 4.0), sink=0.15, tilt=0.4)

    # ------------------------------------------------------------ the armies
    def upos(self, u, G):
        """World position of unit u at battle frame G (analytic)."""
        Gc = min(G, BRK + 30)
        x = front(G) + u.back + u.lag * math.sin(Gc * 0.012 + u.ph)
        y = u.y0 + u.sway * math.sin(Gc * 0.018 + u.ph * 1.7)
        x *= u.side
        z = self.zat(x, y)
        if u.hover:
            z += u.hover + 0.25 * math.sin(G * 0.11 + u.ph)
            if u.drop and G > u.drop:
                k = ramp(G, u.drop, u.drop + 10)
                z -= (u.hover + 0.25) * k
        return Vector((x, y, z))

    def uquat(self, u, G):
        yaw = 0.0 if u.side < 0 else math.pi
        brake = 0.06 * math.sin(math.pi * ramp(G, G_SPLIT - 2, G_SPLIT + 20)) if G > G_SPLIT - 2 else 0.0
        bump = 0.012 * math.sin(G * 0.9 + u.ph * 3) * (0 if u.hover else 1) * (1 - ramp(G, BRK, BRK + 20))
        roll = 0.0
        if u.hover:
            roll = 0.03 * math.sin(G * 0.07 + u.ph)
            bump = 0.02 * math.sin(G * 0.05 + u.ph * 2)
        q = Quaternion((0, 0, 1), yaw) @ Quaternion((0, 1, 0), bump + brake) @ Quaternion((1, 0, 0), roll)
        if u.drop and G > u.drop:
            q = q @ Quaternion((1, 0, 0), 0.12 * math.sin(u.ph) * ramp(G, u.drop, u.drop + 10))
        return q

    def muzzle(self, u, G):
        p = self.upos(u, G)
        mx, mz = u.muzzle
        return p + Vector((mx * (1 if u.side < 0 else -1), 0, mz))

    def army(self):
        rnd = random.Random(4402)
        self.units = {-1: [], 1: []}
        self.tmpl = {}
        self.mats = {-1: set(), 1: set()}
        for side in (-1, 1):
            placed = []
            plan = []
            for kind, spec in ROSTER[side].items():
                fac, role, mz, fire, hv, count = spec
                for i in range(count):
                    plan.append((kind, role, mz, fire, hv))
            # big ones first so they get the good slots
            order = {'heavy': 0, 'tank': 1, 'scout': 2, 'missile': 3, 'arty': 4, 'support': 5}
            plan.sort(key=lambda t: order[t[1]])
            for kind, role, mz, fire, hv in plan:
                lo, hi = BACK[role]
                for attempt in range(80):
                    back = rnd.uniform(lo, hi)
                    y = rnd.uniform(-185, 185)
                    if role == 'heavy':
                        y = rnd.gauss(0, 70)
                    if side < 0 and abs(y - HERO_Y) < 8 and back < 12:
                        continue
                    if all((back - b) ** 2 + ((y - yy) / 1.0) ** 2 > 15.0 ** 2 for b, yy in placed):
                        break
                placed.append((back, y))
                u = Unit()
                u.side, u.kind, u.role = side, kind, role
                u.y0, u.back = y, back
                u.ph = rnd.uniform(0, 6.3)
                u.lag = rnd.uniform(1.5, 5.0)
                u.sway = rnd.uniform(0.5, 2.5)
                u.hover = hv
                u.muzzle = mz
                u.fire = fire
                u.freeze = None
                u.drop = None
                u.name = f'{kind}{len(self.units[side])}'
                self.units[side].append(u)
        # our Lancer: front rank, the cameras ride with it
        h = Unit()
        h.side, h.kind, h.role, h.y0, h.back, h.ph, h.lag, h.sway, h.hover = -1, 'lancer', 'tank', HERO_Y, -2.0, 0.3, 0.6, 0.4, 0.0
        h.muzzle, h.fire = ROSTER[-1]['lancer'][2], ('burst', 22, 1, 0, 'bolt')
        h.freeze, h.drop, h.name = None, None, 'Hero'
        self.units[-1].append(h)
        self.hero = h
        # bake: every 2 frames over the scene window
        frames = list(range(self.G0 - 2, self.G1 + 3, 2))
        for side in (-1, 1):
            for u in self.units[side]:
                fac = ROSTER[side][u.kind][0]
                key = f'{fac}/{u.kind}'
                if key not in self.tmpl:
                    t = GR.load_unit(key)
                    self.tmpl[key] = t
                    for s in t.material_slots:
                        if s.material:
                            self.mats[side].add(s.material)
                o = bpy.data.objects.new(f'U_{"T" if side < 0 else "A"}_{u.name}', self.tmpl[key].data)
                SP.link(o)
                bake(o, frames, [self.upos(u, f) for f in frames], [self.uquat(u, f) for f in frames])
                u.obj = o
        # brighter running lights on both armies
        for side, k in ((-1, 2.2), (1, 2.0)):
            for m in self.mats[side]:
                b = next((nd for nd in m.node_tree.nodes if nd.type == 'BSDF_PRINCIPLED'), None)
                if b is not None:
                    b.inputs['Emission Strength'].default_value *= k

    def near_units(self, side, x, y, r):
        G = self.G0
        return [u for u in self.units[side] if (self.upos(u, G).xy - Vector((x, y))).length < r]

    # ------------------------------------------------------------ Arcadian hover: gold lightning to the ground
    def hover_fx(self):
        rnd = random.Random(4403)
        gm = SP.emit('HoverArcM', (1.0, 0.62, 0.18), 5.0)
        hm = BP._halo_mat('HoverGlowM', GOLD, 0.45)
        arcs = []
        for v in range(4):
            bm = bmesh.new()
            pts_all = []
            for a in range(3):
                ang = rnd.uniform(0, 2 * math.pi)
                p0 = Vector((math.cos(ang) * rnd.uniform(0.5, 2.0), math.sin(ang) * rnd.uniform(0.4, 1.3), 0.3))
                p1 = Vector((p0.x * 1.3 + rnd.uniform(-0.8, 0.8), p0.y * 1.3 + rnd.uniform(-0.8, 0.8), -1.0))
                pts_all.append(SFX._jag(p0, p1, rnd, 3, 0.3))
            objs = [SFX._tube_path(f'HArcPart{v}_{i}', pts, 0.02, gm, sides=4) for i, pts in enumerate(pts_all)]
            ob = _join(objs, f'HoverArcT{v}')
            ob.hide_render = True
            ob.location = (0, 0, -5000)
            arcs.append(ob)
        G0 = self.G0 - 2
        for u in self.units[1]:
            if not u.hover:
                continue
            o = bpy.data.objects.new(u.obj.name + 'Arc', arcs[rnd.randrange(4)].data)
            SP.link(o)
            o.parent = u.obj
            o.location = (0.3, 0, u.hover * 0.55)
            o.visible_shadow = False
            o.rotation_mode = 'XYZ'
            for f in range(G0, self.G1 + 3, 2):
                o.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
                o.scale = (rnd.uniform(0.8, 1.2), rnd.uniform(0.8, 1.2), max(0.4, u.hover / 1.4))
                o.keyframe_insert('rotation_euler', frame=f)
                o.keyframe_insert('scale', frame=f)
            C.set_interp(o, 'CONSTANT')
            g = C.uv_sphere(u.obj.name + 'Glow', 1.0, seg=(16, 8), mat=hm, scale=(2.6, 1.6, 0.35))
            g.parent = u.obj
            g.location = (0.3, 0, 0.1)
            g.visible_shadow = False
            u.obj['arc'] = o.name
            u.obj['glow'] = g.name

    # ------------------------------------------------------------ aircraft
    def plane(self, side, kind, name, f0, dur, path, bank=0.0, rnd=None):
        """path(s) -> world position for s in 0..1; heading follows the path."""
        rnd = rnd or random.Random(hash(name) & 0xffff)
        rel = f'{"human" if side < 0 else "alien"}/{kind}'
        t = GR.load_unit(rel)
        o = bpy.data.objects.new(name, t.data)
        SP.link(o)
        frames = list(range(f0, f0 + dur + 1, 2))
        locs, quats = [], []
        for f in frames:
            s = (f - f0) / dur
            p = path(s)
            p.z = max(p.z, self.zat(p.x, p.y) + 6)
            d = path(min(1.0, s + 0.01)) - path(max(0.0, s - 0.01))
            yaw = math.atan2(d.y, d.x)
            pitch = math.atan2(d.z, max(1e-3, d.xy.length))
            quats.append(Quaternion((0, 0, 1), yaw) @ Quaternion((0, 1, 0), -pitch) @ Quaternion((1, 0, 0), bank * math.sin(math.pi * s)))
            locs.append(p)
        bake(o, frames, locs, quats)
        SP.show(o, f0, f0 + dur)
        o.scale = (1.3,) * 3
        self.air.append((side, kind, o, frames, locs))
        # engines: Terran blue jets; Arcadian gold lightning (never flame)
        if side < 0:
            jm = BP._halo_mat('AirJetTM', (0.4, 0.75, 1.0), 4.0)
            for dy in ((-1.2, 1.2) if kind == 'condor' else (0.0,)):
                j = C.uv_sphere(o.name + f'Jet{dy}', 1.0, seg=(12, 6), mat=jm, scale=(2.6, 0.55, 0.55))
                j.parent = o
                j.location = (-5.6 if kind == 'condor' else -5.0, dy, 1.0)
                j.visible_shadow = False
        else:
            gm = BP._halo_mat('AirArcGlowM', GOLD, 1.5)
            back = {'dragonfly': -6.4, 'disc': -3.0, 'halo': -2.8}.get(kind, -3.5)
            j = C.uv_sphere(o.name + 'Glow', 1.0, seg=(12, 6), mat=gm, scale=(2.2, 1.0, 0.6))
            j.parent = o
            j.location = (back, 0, 1.2)
            j.visible_shadow = False
            arc = None
            if arc:
                a = bpy.data.objects.new(o.name + 'Arc', arc.data)
                SP.link(a)
                a.parent = o
                a.location = (back + 0.4, 0, 1.2)
                a.rotation_mode = 'XYZ'
                for f in range(f0, f0 + dur + 1, 2):
                    a.rotation_euler = (rnd.uniform(0, 6.3), math.radians(90), 0)
                    a.keyframe_insert('rotation_euler', frame=f)
                C.set_interp(a, 'CONSTANT')
                a.visible_shadow = False
        return o

    def aircraft(self):
        rnd = random.Random(4404)
        self.air = []
        if self.scene == 's14':
            return
        n = 0
        for side in (-1, 1):
            for kind, count in AIR[side]:
                for i in range(count):
                    # passes: start behind their own army, cross the valley over the enemy
                    f0 = rnd.randint(self.G0 - 60, self.G1 - 30)
                    dur = rnd.randint(70, 110)
                    alt = rnd.choice((rnd.uniform(14, 24), rnd.uniform(24, 40), rnd.uniform(40, 70)))
                    if kind in ('condor', 'disc'):
                        alt = rnd.uniform(30, 55)
                    y = rnd.uniform(-170, 170)
                    x0 = side * rnd.uniform(380, 520)
                    x1 = -side * rnd.uniform(250, 520)
                    curve = rnd.uniform(-60, 60)
                    ph = rnd.uniform(0, 6)

                    def path(s, x0=x0, x1=x1, y=y, curve=curve, alt=alt, ph=ph):
                        return Vector((x0 + (x1 - x0) * s, y + curve * math.sin(math.pi * s), alt + 4 * math.sin(6 * s + ph)))
                    self.plane(side, kind, f'Air_{kind}{n}', f0, dur, path, bank=rnd.uniform(-0.5, 0.5), rnd=rnd)
                    n += 1
        for k, (side, kind, f0, dur, p0, p1, bank) in enumerate(self.air_plan):
            p0, p1 = Vector(p0), Vector(p1)
            self.plane(side, kind, f'AirP_{kind}{k}', f0, dur, lambda s, p0=p0, p1=p1: p0.lerp(p1, s), bank=bank, rnd=rnd)

    # ------------------------------------------------------------ fire
    _mcache = {}

    def m(self, key, fn):
        if key not in self._mcache or self._mcache[key].name not in bpy.data.materials:
            self._mcache[key] = fn()
        return self._mcache[key]

    def bolt(self, p0, p1, f0, f1, side, w, L):
        col, hot = (BLUE, BLUE_HOT) if side < 0 else (GOLD, GOLD_HOT)
        core_m = self.m(('core', side), lambda: SP.emit(SP._uid('BoltCore'), (0.15, 0.5, 1.0) if side < 0 else (1.0, 0.55, 0.1), 3.0))
        halo_m = self.m(('halo', side), lambda: BP._halo_mat(SP._uid('BoltHalo'), col, 0.6))
        d = (p1 - p0)
        q = d.normalized().to_track_quat('X', 'Z')
        o = C.uv_sphere(SP._uid('Bolt'), 1.0, seg=(12, 8), mat=core_m, scale=(L, w, w))
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = q
        h = C.uv_sphere(o.name + 'H', 1.0, seg=(12, 8), mat=halo_m, scale=(1.1, 2.2, 2.2))
        h.parent = o
        for x in (o, h):
            x.visible_shadow = False
        a = p0 + d.normalized() * L
        SP.key_loc(o, [(f0, a), (f1, p1)], 'LINEAR')
        SP.show(o, f0, f1)
        self.fx.append((o, f0, f1, lambda G, a=a, f0=f0, f1=f1: a.lerp(p1, (G - f0) / max(1, f1 - f0)), L + 1.0))
        return o

    def flash(self, p, f, size, side, life=3, light=0.0, aim=None):
        col = {-1: BLUE, 1: GOLD, 0: (1.0, 0.55, 0.2), 'v': (0.6, 0.35, 1.0)}[side]
        mt = self.m(('flash', side), lambda: BP._halo_mat(SP._uid('FlashM'), col, 2.0))
        o = C.uv_sphere(SP._uid('Flash'), 1.0, seg=(16, 8), mat=mt)
        o.location = p
        o.visible_shadow = False
        if aim is not None:      # muzzle flash: a short cone of fire along the barrel
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = Vector(aim).normalized().to_track_quat('X', 'Z')
            o.location = p + Vector(aim).normalized() * size * 0.8
            SP.key_scale(o, [(f, (size * 0.6, size * 0.2, size * 0.2)), (f + 1, (size * 1.6, size * 0.45, size * 0.45)),
                             (f + life, (size * 0.5, size * 0.1, size * 0.1))], 'LINEAR')
        else:
            SP.key_scale(o, [(f, size * 0.3), (f + 1, size), (f + life, size * 0.2)], 'LINEAR')
        SP.show(o, f, f + life)
        self.fx.append((o, f, f + life, lambda G, p=p: p, size * 1.5))
        if light > 0 and self.lights_budget > 0:
            self.lights_budget -= 1
            L_ = bpy.data.objects.new(SP._uid('FlL'), bpy.data.lights.new(SP._uid('FlL'), 'POINT'))
            SP.link(L_)
            L_.location = p + Vector((0, 0, 1.0))
            L_.data.color = col
            L_.data.shadow_soft_size = size * 0.4
            for ff, e in [(f - 1, 0), (f, light), (f + life + 2, 0)]:
                L_.data.energy = e
                L_.data.keyframe_insert('energy', frame=ff)
            SP.lin(L_.data)
        return o

    def sparks(self, p, f, side, n, size):
        """Hot streaks flying off a hit (shared material, 4-6 frames)."""
        rnd = random.Random(int(p.x * 13 + p.y * 7 + f))
        mt = self.m(('spark', side), lambda: SP.emit(SP._uid('SparkM'), (0.5, 0.8, 1.0) if side < 0 else (1.0, 0.7, 0.3), 6.0))
        for i in range(n):
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), abs(rnd.gauss(0.6, 0.6)))).normalized()
            L = size * rnd.uniform(0.25, 0.6)
            o = C.uv_sphere(SP._uid('Spk'), 1.0, seg=(6, 4), mat=mt, scale=(L, 0.04, 0.04))
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = d.to_track_quat('X', 'Z')
            o.visible_shadow = False
            life = rnd.randint(4, 7)
            SP.key_loc(o, [(f, p + d * L), (f + life, p + d * (L + size * rnd.uniform(1.5, 3.5)) - Vector((0, 0, 0.5)))], 'LINEAR')
            SP.key_scale(o, [(f, (L, 0.04, 0.04)), (f + life, (L * 0.3, 0.02, 0.02))], 'LINEAR')
            SP.show(o, f, f + life)
            self.fx.append((o, f, f + life, lambda G, p=p: p, size * 2))

    def dust_trails(self):
        """Dust kicked up behind the moving units (churning, lit, see-through)."""
        rnd = random.Random(4408)
        mats = [GR.dust_mat(f'TrailDust{k}', (0.2, 0.12, 0.08)) for k in range(3)]
        for m_ in mats:
            SP.key_node(m_, 'V', [(1, 0.55), (BRK, 0.55), (BRK + 30, 0.0)])
        for side in (-1, 1):
            for u in self.units[side]:
                if rnd.random() > (0.75 if not u.hover else 0.4):
                    continue
                L = 4.5 if u.role != 'scout' else 3.5
                for j in range(3):
                    d = C.uv_sphere(u.obj.name + f'Dust{j}', 1.0, seg=(14, 8), mat=mats[rnd.randrange(3)])
                    d.parent = u.obj
                    d.location = (-L - j * 3.2, rnd.uniform(-0.8, 0.8), 0.9 + j * 0.5 - (u.hover * 0.6))
                    k = 1.4 + j * 1.0
                    d.scale = (k * 1.3, k, k * 0.6)
                    d.visible_shadow = False

    def dirt(self, p, f, size, seed):
        """Dirt kicked up by an impact: clods thrown out and a dust puff."""
        rnd = random.Random(seed)
        for i in range(6):
            t = self.rock_t[rnd.randrange(len(self.rock_t))]
            o = bpy.data.objects.new(SP._uid('Clod'), t.data)
            SP.link(o)
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), 0)).normalized()
            v = rnd.uniform(4, 9) * size / 4
            vz = rnd.uniform(6, 14) * size / 4
            s = rnd.uniform(0.15, 0.4) * size / 3
            o.scale = (s, s, s)
            keys = []
            for k in range(0, 21, 4):
                tt = k / FPS
                keys.append((f + k, p + d * v * tt + Vector((0, 0, vz * tt - 9.8 * tt * tt))))
            SP.key_loc(o, keys, 'LINEAR')
            SP.key_rot(o, [(f, (0, 0, 0)), (f + 20, (rnd.uniform(-300, 300), rnd.uniform(-300, 300), 0))], 'LINEAR')
            SP.show(o, f, f + 20)
        if self.boom_budget > 0:
            dm = GR.dust_mat(SP._uid('ImpDust'), (0.16, 0.1, 0.07))
            dd = C.uv_sphere(SP._uid('ImpDustO'), 1.0, seg=(16, 8), mat=dm)
            dd.visible_shadow = False
            SP.key_loc(dd, [(f, p + Vector((0, 0, size * 0.3))), (f + 40, p + Vector((0, 0, size * 1.3)))], 'BEZIER')
            SP.key_scale(dd, [(f, (size * 0.4, size * 0.4, size * 0.3)), (f + 8, (size * 1.2, size * 1.2, size)),
                              (f + 40, (size * 2.0, size * 2.0, size * 1.4))], 'BEZIER')
            SP.key_node(dm, 'V', [(f, 0.9), (f + 14, 0.6), (f + 40, 0.0)])
            SP.show(dd, f, f + 40)

    def gunfire(self):
        rnd = random.Random(4405)
        g_start = {'shell': 15, 'heavy': 100, 'missile': 105, 'bolt': 112, 'light': 120}
        g_stop = G_SPLIT + 6
        lo, hi = self.G0 - 40, min(self.G1, g_stop)
        for side in (-1, 1):
            enemies = self.units[-side]
            for u in self.units[side]:
                if not u.fire:
                    continue
                pat, period, burst, gap, weapon = u.fire
                period = int(period * rnd.uniform(0.85, 1.15))
                G = rnd.randint(g_start[weapon], g_start[weapon] + period)
                while G < hi:
                    for b in range(burst):
                        Gf = G + b * gap
                        if lo <= Gf < hi:
                            self.fire_one(u, Gf, weapon, enemies, rnd)
                    G += period + rnd.randint(-2, 2)
        # aircraft: Falcons/Halos/Dragonflies strafe, Condors and Discs drop heavy blasts
        for side, kind, o, frames, locs in self.air:
            enemies = self.units[-side]
            per = {'falcon': 6, 'halo': 6, 'dragonfly': 5, 'condor': 18, 'disc': 16}.get(kind, 8)
            weapon = 'light' if per < 10 else 'heavy'
            for i in range(0, len(frames), max(1, per // 2)):
                f, p = frames[i], locs[i]
                if not (lo <= f < hi) or f < 100:
                    continue
                if side * p.x > -40:          # only once over the enemy side
                    continue
                tgt = min(enemies, key=lambda e: (self.upos(e, f).xy - (p.xy + Vector((-side * 60, 0)))).length)
                tp = self.upos(tgt, f + 6) + Vector((rnd.uniform(-5, 5), rnd.uniform(-5, 5), 1.0))
                fl = max(3, int((tp - p).length / 12))
                self.bolt(p + Vector((0, 0, -1)), tp, f, f + fl, side, 0.18 if weapon == 'light' else 0.38,
                          2.5 if weapon == 'light' else 5.0)
                self.impact(tp, f + fl, side, weapon, rnd)

    def fire_one(self, u, G, weapon, enemies, rnd):
        p0 = self.muzzle(u, G)
        ex = self.upos(u, G)
        cands = [e for e in enemies if abs(self.upos(e, G).y - ex.y) < 45]
        if not cands:
            cands = enemies
        cands.sort(key=lambda e: abs(self.upos(e, G).x))
        tgt = cands[min(len(cands) - 1, int(abs(rnd.gauss(0, 4))))]
        if weapon == 'shell':
            fl = rnd.randint(30, 38)
            tp = self.upos(tgt, G + fl) + Vector((rnd.uniform(-10, 10), rnd.uniform(-10, 10), 0))
            tp.z = self.zat(tp.x, tp.y)
            apex = (p0 + tp) / 2 + Vector((0, 0, 45 + 0.12 * (tp - p0).length))
            col = BLUE if u.side < 0 else GOLD
            sm = self.m(('shell', u.side), lambda: BP._halo_mat(SP._uid('ShellM'), col, 3.0))
            tm_ = self.m(('trail', u.side), lambda: BP._halo_mat(SP._uid('TrailM'), col, 1.2))

            def bez(t):
                t = max(0.0, min(1.0, t))
                return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * apex + t * t * tp
            for j, (lagf, r) in enumerate(((0, 0.32), (1.0, 0.26), (2.0, 0.21), (3.0, 0.16), (4.5, 0.11))):
                o = C.uv_sphere(SP._uid('Shell'), 1.0, seg=(10, 6), mat=sm if j == 0 else tm_, scale=(r, r, r))
                o.visible_shadow = False
                keys = [(G + k, bez((k - lagf) / fl)) for k in range(0, fl + 1, 2)] + [(G + fl, bez((fl - lagf) / fl))]
                SP.key_loc(o, keys, 'LINEAR')
                SP.show(o, G, G + fl)
            self.flash(p0, G, 2.2, u.side, life=2, light=4e4)
            self.impact(tp + Vector((0, 0, 0.5)), G + fl, u.side, 'shell', rnd)
            return
        spd, w, L = WEAPON[weapon]
        miss = rnd.random() < 0.35
        tp = self.upos(tgt, G + 8) + Vector((0, rnd.uniform(-1.2, 1.2), 1.6 + rnd.uniform(-0.4, 0.6)))
        if miss:
            tp += Vector((-u.side * rnd.uniform(-14, 6), rnd.uniform(-6, 6), 0))
            tp.z = self.zat(tp.x, tp.y) + 0.2
        fl = max(2, int((tp - p0).length / spd))
        if weapon == 'missile':
            mm = self.m(('miss', u.side), lambda: BP._halo_mat(SP._uid('MissM'), BLUE if u.side < 0 else GOLD, 4.0))
            o = C.uv_sphere(SP._uid('Missile'), 1.0, seg=(12, 6), mat=mm, scale=(0.4, 0.4, 0.4))
            o.visible_shadow = False
            apex = (p0 + tp) / 2 + Vector((rnd.uniform(-8, 8), rnd.uniform(-8, 8), 14))
            keys = [(G + k, (1 - k / fl) ** 2 * p0 + 2 * (1 - k / fl) * (k / fl) * apex + (k / fl) ** 2 * tp)
                    for k in range(0, fl + 1, 2)] + [(G + fl, tp)]
            SP.key_loc(o, keys, 'LINEAR')
            SP.show(o, G, G + fl)
            self.flash(p0, G, 0.8, u.side, life=2)
        else:
            self.bolt(p0, tp, G, G + fl, u.side, w, L)
            self.flash(p0, G, {'light': 0.7, 'bolt': 1.1, 'heavy': 2.0}[weapon], u.side, life=2, aim=tp - p0,
                       light=6e4 if weapon == 'heavy' else 0)
        self.impact(tp, G + fl, u.side, weapon, rnd, ground=miss)

    def fire_now(self, u, G, weapon=None, seed=0):
        """An extra shot from u at G (scene modules use it so the hero units fire on camera)."""
        rnd = random.Random(seed or G * 31 + int(u.y0 * 7))
        self.fire_one(u, G, weapon or u.fire[4], self.units[-u.side], rnd)

    def near_miss(self, u, G, off, weapon='heavy', seed=0):
        """An enemy round landing next to u: flash, fireball, clods and dust."""
        rnd = random.Random(seed or G * 17)
        p = self.upos(u, G) + Vector(off)
        p.z = self.zat(p.x, p.y) + 0.4
        src = p + Vector((u.side * -220, rnd.uniform(-30, 30), 6))
        spd, w, L = WEAPON[weapon]
        fl = max(3, int((p - src).length / spd))
        self.bolt(src, p, G - fl, G, -u.side, w, L)
        self.boom_budget += 2
        self.impact(p, G, -u.side, weapon, rnd, ground=True)

    def impact(self, p, f, side, weapon, rnd, ground=False):
        if not self.in_win(f, pad=0):
            return
        size = {'light': 1.0, 'bolt': 1.6, 'heavy': 3.0, 'missile': 2.5, 'shell': 4.0}[weapon]
        self.flash(p + Vector((0, 0, 0.6)), f, size * 0.45, side, life=3 if weapon in ('light', 'bolt') else 4,
                   light=(8e4 if weapon in ('heavy', 'shell') else 0))
        if not ground:
            self.sparks(p, f, side, 3 if weapon in ('light', 'bolt') else 6, size)
        if weapon in ('heavy', 'shell', 'missile') and self.boom_budget > 0:
            self.boom_budget -= 1
            SP.boom(p + Vector((0, 0, 0.8)), f, size * 0.9, life=0.9, seed=rnd.randrange(999))
            if ground or weapon == 'shell':
                self.dirt(p, f, size, rnd.randrange(99999))

    # ------------------------------------------------------------ violet pulses
    def pulses(self):
        for m in (self.gmat, self.cmat):
            SP.key_node(m, 'ringR', [(1, -999.0), (G_PULSE - 1, -999.0), (G_PULSE, 0.0), (G_PULSE + 90, 600.0),
                                     (G_PULSE + 91, -999.0), (G_PULSE2 - 1, -999.0), (G_PULSE2, 40.0), (G_PULSE2 + 40, 900.0),
                                     (G_PULSE2 + 41, -999.0)])
            SP.key_node(m, 'ringK', [(1, 1.0), (G_PULSE + 60, 1.0), (G_PULSE + 90, 0.2), (G_PULSE2, 1.6), (G_PULSE2 + 40, 0.5)])
            SP.key_node(m, 'ringR2', [(1, -999.0), (G_PULSE - 1, -999.0), (G_PULSE, 0.0), (G_PULSE + 90, 600.0),
                                      (G_PULSE + 91, -999.0), (G_PULSE2 - 1, -999.0), (G_PULSE2, 40.0), (G_PULSE2 + 40, 900.0)])
            SP.key_node(m, 'ringK2', [(1, 1.0), (G_PULSE + 40, 0.6), (G_PULSE + 90, 0.0), (G_PULSE2, 1.0), (G_PULSE2 + 60, 0.3)])
            SP.key_node(m, 'sprR', [(1, -10.0), (G_SPLIT, -10.0), (G_SPLIT + 60, 60.0), (G_RISEN, 110.0), (G_STRIKE_A + 40, 170.0)])
        # violet light riding the ring, so units and rocks catch it as it passes under them
        for gp, R1, dur, e in ((G_PULSE, 600.0, 90, 8e3), (G_PULSE2, 900.0, 40, 2e4)):
            if not self.in_win(gp, pad=0) and not self.in_win(gp + dur // 2, pad=0):
                continue
            emp = bpy.data.objects.new(SP._uid('PulseRing'), None)
            SP.link(emp)
            SP.key_scale(emp, [(gp, (1.0, 1.0, 1.0)), (gp + dur, (R1, R1, 1.0))], 'LINEAR')
            for i in range(28):
                a = 2 * math.pi * i / 28
                L_ = bpy.data.objects.new(SP._uid('PulseL'), bpy.data.lights.new(SP._uid('PulseL'), 'POINT'))
                SP.link(L_)
                L_.parent = emp
                L_.location = (math.cos(a), math.sin(a), 4.0)
                L_.data.color = (0.5, 0.2, 1.0)
                L_.data.shadow_soft_size = 10
                for f, en in [(gp - 1, 0), (gp, e * 0.2), (gp + 8, e), (gp + dur - 20, e * 0.6), (gp + dur, 0)]:
                    L_.data.energy = en
                    L_.data.keyframe_insert('energy', frame=f)
        SP.key_node(self.gmat, 'crackK', [(1, 0.0), (G_SPLIT, 0.0), (G_SPLIT + 20, 0.5), (G_PULSE2, 0.8), (G_STRIKE_T, 1.0)])
        SP.key_node(self.cmat, 'glowK', [(1, 1.0), (G_SPLIT, 1.0), (G_RISEN, 1.6), (G_STRIKE_T, 2.2)])

    # ------------------------------------------------------------ the Shard
    def shard(self):
        import shard_hd
        crystal = shard_hd.shard_hd('Shard', height=42.0)
        root = bpy.data.objects.new('ShardRoot', None)
        SP.link(root)
        for nm in ('Shard', 'Shard_Core', 'Shard_Splinters', 'Shard_Inner', 'Shard_Veins', 'Shard_Light'):
            o = bpy.data.objects.get(nm)
            if o:
                o.parent = root
        root.scale = (SHARD_K,) * 3
        K = SHARD_K
        SP.key_loc(root, [(1, (0, 0, -72 * K)), (G_BREACH - 6, (0, 0, -66 * K)), (G_BREACH + 30, (0, 0, -44 * K)),
                          (G_RISEN - 30, (0, 0, -10 * K)), (G_RISEN, (0, 0, -6.5 * K)), (700, (0, 0, -6.0 * K))], 'BEZIER')
        SP.key_rot(root, [(1, (0, 0, 0)), (700, (0, 0, 25))], 'LINEAR')
        self.shard_root = root
        spl = bpy.data.objects.get('Shard_Splinters')
        if spl:
            spl.data.materials.clear()
            spl.data.materials.append(crystal.data.materials[0])
        # tone the interior down: violet, never white glare
        core = bpy.data.objects.get('Shard_Core')
        cm = core.data.materials[0]
        em = next(nd for nd in cm.node_tree.nodes if nd.type == 'EMISSION')
        em.inputs[0].default_value = (0.45, 0.15, 1.0, 1)
        for f, s in [(1, 3.0), (G_PULSE2 - 6, 3.0), (G_PULSE2, 8.0), (G_PULSE2 + 20, 3.5), (G_STRIKE_T - 14, 3.5),
                     (G_STRIKE_T, 8.0), (G_STRIKE_A + 40, 8.0)]:
            em.inputs[1].default_value = s
            em.inputs[1].keyframe_insert('default_value', frame=f)
        for nm in ('Shard_Inner', 'Shard_Veins'):
            o = bpy.data.objects.get(nm)
            mt = o.data.materials[0]
            for nd in mt.node_tree.nodes:
                if nd.type == 'EMISSION':
                    c = nd.inputs[0].default_value
                    nd.inputs[0].default_value = (c[0] * 0.7, c[1] * 0.35, c[2], 1)
            for nd in mt.node_tree.nodes:
                if nd.type == 'MAP_RANGE':
                    nd.inputs[3].default_value *= 0.3
                    nd.inputs[4].default_value *= 0.35
        sl = bpy.data.objects.get('Shard_Light')
        for f, e in [(1, 0), (G_BREACH, 0), (G_BREACH + 30, 6e5), (G_PULSE2 - 6, 1.2e6), (G_PULSE2, 5e6), (G_PULSE2 + 24, 1.5e6),
                     (G_STRIKE_T - 14, 1.5e6), (G_STRIKE_T, 4e6)]:
            sl.data.energy = e
            sl.data.keyframe_insert('energy', frame=f)
        # violet light spilling from the breach round the root
        for k, (dx, dy) in enumerate(((40, 0), (-40, 0), (0, 40), (0, -40))):
            L_ = bpy.data.objects.new(f'BreachL{k}', bpy.data.lights.new(f'BreachL{k}', 'POINT'))
            SP.link(L_)
            L_.location = (dx, dy, 6)
            L_.data.color = (0.4, 0.1, 1.0)
            L_.data.shadow_soft_size = 12
            for f, e in [(1, 0), (G_SPLIT, 0), (G_SPLIT + 20, 3e4), (G_BREACH + 20, 1.2e5), (G_PULSE2, 2e5), (G_STRIKE_T, 1.5e5)]:
                L_.data.energy = e
                L_.data.keyframe_insert('energy', frame=f)
        self.tip_z = lambda G: -6.0 * K + 58 * K

    # ------------------------------------------------------------ the ground splits (s13)
    def split(self):
        rnd = random.Random(4406)
        # fissures: jagged glowing slits, a main one across the gap and forks, opening outward from the origin
        fm, n = BP._new_mat('FissureM')
        tc = n.node('ShaderNodeTexCoord')
        uv = n.node('ShaderNodeSeparateXYZ')
        n.set(uv.inputs[0], tc.outputs['UV'])
        across = n.math('ABSOLUTE', n.math('SUBTRACT', uv.outputs[1], 0.5))
        coreb = n.math('POWER', n.maprange(across, 0.0, 0.5, 1.0, 0.0), 5.0)
        geo = n.node('ShaderNodeNewGeometry')
        sp = n.node('ShaderNodeSeparateXYZ')
        n.set(sp.inputs[0], geo.outputs['Position'])
        d = n.math('SQRT', n.math('ADD', n.math('MULTIPLY', sp.outputs[0], sp.outputs[0]), n.math('MULTIPLY', sp.outputs[1], sp.outputs[1])))
        openR = _val(fm, 'openR', 0.0)
        vis = n.maprange(n.math('SUBTRACT', openR, d), 0.0, 8.0, 0.0, 1.0)
        nz = n.node('ShaderNodeTexNoise', Scale=0.15, Detail=4.0)
        n.set(nz.inputs['Vector'], geo.outputs['Position'])
        flick = n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.6, 1.4)
        em = n.node('ShaderNodeEmission')
        n.set(em.inputs['Color'], n.mix(coreb, (0.2, 0.03, 0.7), (0.6, 0.35, 1.0)))
        n.set(em.inputs['Strength'], n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY', coreb, 5.0), vis), flick))
        dark = n.node('ShaderNodeBsdfDiffuse', Color=(0.01, 0.005, 0.01, 1))
        add = n.node('ShaderNodeAddShader')
        n.set(add.inputs[0], dark.outputs[0])
        n.set(add.inputs[1], em.outputs[0])
        tr = n.node('ShaderNodeBsdfTransparent')
        mx = n.node('ShaderNodeMixShader')
        n.set(mx.inputs[0], vis)
        n.set(mx.inputs[1], tr.outputs[0])
        n.set(mx.inputs[2], add.outputs[0])
        out = n.node('ShaderNodeOutputMaterial')
        n.set(out.inputs['Surface'], mx.outputs[0])
        self.fissure_mat = fm

        def ribbon(name, pts, w0, w1):
            bm = bmesh.new()
            uvl = bm.loops.layers.uv.new()
            prev = None
            N = len(pts)
            for i, p in enumerate(pts):
                a = pts[max(i - 1, 0)]
                b = pts[min(i + 1, N - 1)]
                t = (b - a)
                t.z = 0
                t.normalize()
                side = Vector((-t.y, t.x, 0))
                w = (w0 + (w1 - w0) * i / (N - 1)) * rnd.uniform(0.7, 1.3)
                l = bm.verts.new((p.x + side.x * w / 2, p.y + side.y * w / 2, self.zat(p.x + side.x * w / 2, p.y + side.y * w / 2) + 0.12))
                r = bm.verts.new((p.x - side.x * w / 2, p.y - side.y * w / 2, self.zat(p.x - side.x * w / 2, p.y - side.y * w / 2) + 0.12))
                if prev:
                    f = bm.faces.new((prev[0], prev[1], r, l))
                    for lp in f.loops:
                        lp[uvl].uv = (0.0, 0.0 if lp.vert in (prev[0], l) else 1.0)
                prev = (l, r)
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            o = bpy.data.objects.new(name, me)
            SP.link(o)
            me.materials.append(fm)
            o.visible_shadow = False
            return o
        k = 0
        for sgn in (-1, 1):                      # main fissure across the valley (along y)
            pts = SFX._jag(Vector((0, 0, 0)), Vector((rnd.uniform(-30, 30), sgn * 300, 0)), rnd, 6, 0.08)
            ribbon(f'Fissure{k}', pts, 4.5, 0.6)
            k += 1
        for b in range(14):                      # forks toward both armies
            a = rnd.uniform(0, 2 * math.pi)
            r0 = rnd.uniform(5, 30)
            L = rnd.uniform(60, 170)
            p0 = Vector((math.cos(a) * r0, math.sin(a) * r0, 0))
            p1 = p0 + Vector((math.cos(a), math.sin(a), 0)) * L
            ribbon(f'Fissure{k}', SFX._jag(p0, p1, rnd, 5, 0.12), rnd.uniform(0.8, 1.8), 0.2)
            k += 1
        SP.key_node(fm, 'openR', [(1, 0.0), (G_SPLIT, 0.0), (G_SPLIT + 30, 300.0)], 'LINEAR')
        # ground slabs heaving up round the breach and tilting away as the Shard pushes through
        gm = self.gmat
        for i in range(46):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(18, 62)
            p = Vector((math.cos(a) * r, math.sin(a) * r, 0))
            p.z = self.zat(p.x, p.y)
            t = self.rock_t[rnd.randrange(len(self.rock_t))]
            o = bpy.data.objects.new(f'Slab{i}', t.data.copy())
            SP.link(o)
            o.data.materials.clear()
            o.data.materials.append(self.rock_mat)
            s = rnd.uniform(2.5, 6)
            o.scale = (s * 1.4, s, s * 0.45)
            outward = Vector((math.cos(a), math.sin(a), 0))
            f0 = G_BREACH - 30 + int(r * 0.4) + rnd.randint(0, 10)
            tilt = rnd.uniform(25, 70)
            lift = rnd.uniform(2, 10) * (70 - r) / 50
            rot0 = (0, 0, math.degrees(a))
            o.rotation_mode = 'XYZ'
            SP.key_loc(o, [(f0, p - Vector((0, 0, s * 0.3))), (f0 + 25, p + outward * (6 + lift) + Vector((0, 0, lift))),
                           (f0 + 60, p + outward * (10 + lift * 1.5) + Vector((0, 0, lift * 0.6)))], 'BEZIER')
            SP.key_rot(o, [(f0, rot0), (f0 + 25, (0, tilt * 0.8, math.degrees(a))), (f0 + 60, (0, tilt, math.degrees(a)))], 'BEZIER')
            # face outward: tilt about the tangential axis -> rotate in local after yaw
        # rocks thrown up and sliding off the rising crystal
        for i in range(60):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(5, 45)
            p0 = Vector((math.cos(a) * r, math.sin(a) * r, self.zat(math.cos(a) * r, math.sin(a) * r)))
            t = self.rock_t[rnd.randrange(len(self.rock_t))]
            o = bpy.data.objects.new(f'Lift{i}', t.data)
            SP.link(o)
            s = rnd.uniform(0.8, 3.5)
            o.scale = (s, s, s)
            f0 = G_BREACH + rnd.randint(-8, 70)
            up = rnd.uniform(20, 90)
            out = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(10, 40)
            keys = []
            for kf in range(0, 61, 6):
                tt = kf / 60
                keys.append((f0 + kf, p0 + out * tt + Vector((0, 0, up * math.sin(math.pi * min(1.0, tt * 1.1)) * (1 - tt * 0.3)))))
            SP.key_loc(o, keys, 'BEZIER')
            SP.key_rot(o, [(f0, (0, 0, 0)), (f0 + 60, (rnd.uniform(-200, 200), rnd.uniform(-200, 200), 0))], 'LINEAR')
            SP.show(o, f0, f0 + 60)
        # dust rolling out of the breach
        for i in range(12):
            dm = GR.dust_mat(SP._uid('BreachDust'), (0.2, 0.12, 0.09))
            d = C.uv_sphere(SP._uid('BreachDustO'), 1.0, seg=(18, 10), mat=dm)
            d.visible_shadow = False
            a = i / 12 * 2 * math.pi + rnd.uniform(-0.2, 0.2)
            v = Vector((math.cos(a), math.sin(a), 0))
            f0 = G_BREACH - 6 + rnd.randint(0, 20)
            SP.key_loc(d, [(f0, v * 25 + Vector((0, 0, 4))), (f0 + 90, v * rnd.uniform(70, 110) + Vector((0, 0, rnd.uniform(10, 30))))],
                       'BEZIER')
            SP.key_scale(d, [(f0, (8, 8, 5)), (f0 + 90, (rnd.uniform(28, 40),) * 2 + (18,))], 'BEZIER')
            SP.key_node(dm, 'V', [(f0, 0.75), (f0 + 50, 0.45), (f0 + 100, 0.0)])
            SP.show(d, f0, f0 + 100)

    # ------------------------------------------------------------ lightning and crystal crust (s14)
    def strikes(self):
        rnd = random.Random(4407)
        import shard_hd
        crust_m = shard_hd.glass_mat('CrustGlassM')
        # crust templates: a few shared meshes, grown over each unit
        tm = []
        for k in range(6):
            o = SFX.crust((0, 0, 1.0), 4.5, seed=4450 + k, name=f'CrustT{k}', mat=crust_m)
            o.hide_render = True
            o.location = (0, 0, -5000)
            tm.append(o)
        K = SHARD_K
        root_z = -6.0 * K
        # charge at the crown before it fires
        tip = Vector((0, 0, root_z + 54 * K))
        objs = SFX.charge(tip, r=9.0, seed=4460, name='Charge')
        for o in objs:
            SP.show(o, 1, G_STRIKE_T + 2) if o.type != 'LIGHT' else None
            o.visible_shadow = False
        orb = next(o for o in objs if o.name.endswith('Orb'))
        for o in objs:
            if o is not orb and o.parent is None:
                o.parent = orb
                o.matrix_parent_inverse = orb.matrix_world.inverted()
        SP.key_scale(orb, [(self.G0, 0.2), (G_STRIKE_T - 4, 1.0), (G_STRIKE_T + 2, 0.3)], 'BEZIER')
        for side, f0 in ((-1, G_STRIKE_T), (1, G_STRIKE_A)):
            us = [u for u in self.units[side]]
            # who gets hit first: nearest to the camera's view of each side
            fx, fy = self.focus[side]
            us.sort(key=lambda u: (self.upos(u, f0).xy - Vector((fx, fy))).length)
            # volleys of thick forked bolts from the lower spires into the line
            for v in range(7):
                fv = f0 + v * 5
                for q in range(3 if v < 5 else 2):
                    u = us[min(len(us) - 1, int(abs(rnd.gauss(0, 7))))]
                    tgt = self.upos(u, fv) + Vector((0, 0, 1.8))
                    a = math.atan2(tgt.y, tgt.x) + rnd.uniform(-0.3, 0.3)
                    src = Vector((math.cos(a) * rnd.uniform(15, 35), math.sin(a) * rnd.uniform(15, 35),
                                  root_z + rnd.uniform(20, 45) * K / 2))
                    for o in SFX.lightning(src, tgt, seed=4500 + v * 10 + q + (0 if side < 0 else 300), width=1.6,
                                           name=SP._uid('Strike')):
                        if o.type == 'LIGHT':
                            for f, e in [(fv - 1, 0), (fv, o.data.energy * 30), (fv + 4, 0)]:
                                o.data.energy = e
                                o.data.keyframe_insert('energy', frame=f)
                        else:
                            SP.show(o, fv, fv + 3)
                    if u.freeze is None or u.freeze > fv + 1:
                        u.freeze = fv + 1
            # the crust: from the struck units outward, every unit frozen within ~1.5 s
            for u in us:
                p = self.upos(u, f0)
                fz = u.freeze or (f0 + 4 + int((p.xy - Vector((fx, fy))).length / 5) + rnd.randint(0, 16))
                u.freeze = fz
                o = bpy.data.objects.new(f'Crust_{u.obj.name}', tm[rnd.randrange(len(tm))].data)
                SP.link(o)
                o.parent = u.obj
                o.rotation_euler = (0, 0, rnd.uniform(-0.3, 0.3))
                big = 1.0 if u.role in ('heavy', 'arty') else 0.85
                SP.key_scale(o, [(fz, 0.05), (fz + 4, 0.7 * big), (fz + 10, big)], 'BEZIER')
                SP.show(o, fz, self.G1 + 5)
                o.location = (0.5, 0, -0.2)
                if side > 0:
                    u.drop = fz + 3
            # flash where each unit is caught
            for u in us[:18]:
                self.flash(self.upos(u, u.freeze) + Vector((0, 0, 2)), u.freeze, 4.0, 'v', life=4)
        self.tame_bolts()
        # re-bake the Arcadians: frozen hover units drop to the ground
        frames = list(range(self.G0 - 2, self.G1 + 3, 2))
        for u in self.units[1]:
            if u.drop:
                u.obj.animation_data_clear()
                bake(u.obj, frames, [self.upos(u, f) for f in frames], [self.uquat(u, f) for f in frames])
                for nm in ('arc', 'glow'):
                    o = bpy.data.objects.get(u.obj.get(nm, ''))
                    if o:
                        SP.show(o, 1, u.freeze)
        # their lights go out
        for side, f0 in ((-1, G_STRIKE_T), (1, G_STRIKE_A)):
            for mt in self.mats[side]:
                b = next((nd for nd in mt.node_tree.nodes if nd.type == 'BSDF_PRINCIPLED'), None)
                if b is None:
                    continue
                s0 = b.inputs['Emission Strength'].default_value
                for f, kk in ((1, 1.0), (f0 + 8, 1.0), (f0 + 30, 0.05)):
                    b.inputs['Emission Strength'].default_value = s0 * kk
                    b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)

    def tame_bolts(self):
        """shard_fx bolts are built for a dark sky: here they blew out white. Keep them violet, the halo thin,
        the spark spray short."""
        def setk(name, col=None, k=None):
            m = bpy.data.materials.get(name)
            if not m:
                return
            for nd in m.node_tree.nodes:
                if nd.type == 'EMISSION':
                    if col:
                        nd.inputs['Color'].default_value = (*col, 1)
                    if k is not None and not nd.inputs['Strength'].is_linked:
                        nd.inputs['Strength'].default_value = k
                if nd.type == 'MATH' and nd.operation == 'MULTIPLY' and k is not None and nd.inputs[1].is_linked is False \
                        and nd.inputs[0].is_linked and nd.inputs[1].default_value > 0.1 and name != 'BoltCoreM':
                    nd.inputs[1].default_value = k
        setk('BoltCoreM', (0.8, 0.65, 1.0), 9.0)
        setk('BoltSleeveM', (0.45, 0.15, 1.0), 2.2)
        setk('BoltHaloM', (0.35, 0.08, 1.0), 0.3)
        setk('BoltFlashM', (0.5, 0.25, 1.0), 0.8)
        setk('BoltSparkM', (0.6, 0.4, 1.0), 4.0)
        for o in list(bpy.data.objects):
            nm = o.name
            if 'Sp' in nm and nm.startswith('Strike') and nm.rsplit('Sp', 1)[-1].isdigit():
                if int(nm.rsplit('Sp', 1)[-1]) >= 14:
                    bpy.data.objects.remove(o)
                else:
                    o.scale = (o.scale.x * 0.5, o.scale.y, o.scale.z)
            elif nm.startswith('Strike') and nm.endswith('Halo'):
                bpy.data.objects.remove(o)            # the wide halo tube read as smoke here
            elif nm.startswith('Strike') and nm.endswith('Flash'):
                o.scale = o.scale * 0.55

    # ------------------------------------------------------------ cameras
    def shot(self, sid, a, b, keys, shake=()):
        """a, b: scene-local frames; keys in battle frames G."""
        self.shots.append((sid, a, b, keys, list(shake)))

    def pick(self, side, role=None, y=0.0, back=0.0, kinds=None):
        """The unit of a side (optionally of a role/kinds) closest to lane y and depth back."""
        us = [u for u in self.units[side] if u is not self.hero and (role is None or u.role == role)
              and (kinds is None or u.kind in kinds)]
        return min(us, key=lambda u: (u.y0 - y) ** 2 + (u.back - back) ** 2)

    def follow(self, u, G0, G1, off, look, lens, step=2, roll=0.0):
        """Camera keys riding with unit u: off(G) / look(G) are offsets from its position (or callables)."""
        keys = []
        for G in list(range(G0, G1, step)) + [G1]:
            p = self.upos(u, G)
            o = off(G) if callable(off) else Vector(off)
            t = look(G) if callable(look) else Vector(look)
            cam = p + o
            cam.z = max(cam.z, self.zat(cam.x, cam.y) + 0.8)
            keys.append((G, cam, p + t, lens(G) if callable(lens) else lens, roll))
        return keys
