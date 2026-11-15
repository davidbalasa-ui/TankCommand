"""Shared kit for the battle-backdrop concept stills (the fleet fight seen behind the ship-deck missions).

Design work only, nothing here goes into the game. Every still is one static Blender scene rendered at one
frame (FRAME); the animated effects of the opening film (fireballs, shields, comets) are reused by keying
them so that FRAME catches them at a good moment.

Reuses the existing fleet (terran_fleet, arcadian_fleet, ships_hd, orb_fighter) and the opening film's
effects (opening/space.py, barrage_pieces.py, portals.py, planet.py, v3base.py). Ships point along +X.

    from backdrop_kit import Kit
    k = Kit(draft=True)
    s = k.ship('bship'); k.place(s, (0, 80, 0), fwd=(1, 0, 0))
    k.camera((0, 0, 0), (0, 80, 0), lens=24)
    k.render('/path/out.jpg')
"""
import json
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402 (needs bpy first)
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CIN = os.path.dirname(HERE)
sys.path.insert(0, CIN)
sys.path.insert(0, os.path.join(CIN, 'opening'))
ARGS = dict(a.lstrip('-').split('=', 1) if '=' in a else (a.lstrip('-'), '1') for a in sys.argv[1:])
_argv, sys.argv = sys.argv, [sys.argv[0]]
import v3base as V  # noqa: E402
import space as SP  # noqa: E402
import common as C  # noqa: E402
import barrage_pieces as BP  # noqa: E402
import new_pieces as NP  # noqa: E402
import portals as PO  # noqa: E402
import planet as PL  # noqa: E402
import terran_fleet as T  # noqa: E402
import arcadian_fleet as AF  # noqa: E402
import ships_hd as HD  # noqa: E402
sys.argv = _argv

FRAME = 24                      # the frame every still is rendered at
CYAN = (0.25, 0.8, 1.0)
BLUE = (0.18, 0.55, 1.0)
GOLD = (1.0, 0.62, 0.15)
HOTGOLD = (1.0, 0.86, 0.5)
ORANGE = (1.0, 0.45, 0.08)
SCALE = {'dread': 1.8, 'crescent': 2.6, 'shell': 1.4, 'lens': 1.8, 'kesh': 1.8}
FINAL = ARGS.get('final', '0') == '1'
SCRATCH = ARGS.get('scratch', '/home/user/work/battle-backdrops')


def _mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    return BP._new_mat(name)


def glow_mat(name, col, k, p=2.5):
    return V.soft_glow(name, col, k, p)


def metal_mat(name, col, rough=0.45, metal=0.9, emit=None, emit_k=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_k
    return m


def box(name, size, mat, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, bevel=0.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=bm.verts, vec=size)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(mat)
    o.location = loc
    o.rotation_euler = rot
    if parent is not None:
        o.parent = parent
    return o


class Kit:
    def __init__(self, sun_dir=(0.5, 0.6, -0.6), sun_energy=5.0, planet=True, planet_c=None, nebula=1.0,
                 rim_dir=(-0.6, -0.5, 0.3), rim=2.0, fill_dir=(-0.3, 0.8, 0.5), fill=0.35, tint='blue',
                 planet_sun_dir=None):
        """sun_dir / rim_dir / fill_dir: the direction each light TRAVELS (world)."""
        self.final = FINAL
        self.sc = V.Scene(2.0, draft=not FINAL)
        self.sh = self.sc.sh
        self.rnd = random.Random(7)
        self._src = {}
        self._n = 0
        self.world(nebula, tint)

        def rot(d):
            return [math.degrees(a) for a in Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler()]
        self.sun = self.sh.sun(rot=rot(sun_dir), energy=sun_energy)
        self.sun.data.angle = math.radians(1.5)
        if rim:
            r = self.sh.sun(rot=rot(rim_dir), energy=rim, col=(0.5, 0.7, 1.0), name='Rim')
            r.data.angle = math.radians(6)
        if fill:
            f = self.sh.sun(rot=rot(fill_dir), energy=fill, col=(0.6, 0.65, 0.9), name='Fill')
            f.data.angle = math.radians(20)
        for o in bpy.data.objects:                  # sun lamps must not show up as white discs through refracting
            if o.type == 'LIGHT':                   # materials (the portals' lensing rings)
                o.visible_transmission = False
        bpy.context.view_layer.update()
        self.planet = None
        if planet:
            ps = self.sun
            if planet_sun_dir is not None:          # light the planet from its own direction (mood), not the ships' key
                ps = bpy.data.objects.new('PlanetSun', None)
                bpy.context.scene.collection.objects.link(ps)
                ps.rotation_euler = [math.radians(a) for a in rot(planet_sun_dir)]
                bpy.context.view_layer.update()
            self.planet = PL.build(Vector(planet_c) if planet_c is not None else SP.PLANET_C, ps, draft=not FINAL)

    def set_res(self, w, h):
        """Final picture size (drafts render at half). Call before camera() / cam_pt()."""
        self.res = (w, h)
        bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = w, h

    def uid(self, p):
        self._n += 1
        return f'{p}{self._n}'

    # ------------------------------------------------------------------ world: stars + a painted nebula
    def world(self, k=1.0, tint='blue'):
        w = bpy.data.worlds.new('BackdropSpace')
        bpy.context.scene.world = w
        w.use_nodes = True
        nt = w.node_tree
        for nd in list(nt.nodes):
            nt.nodes.remove(nd)

        def N(t, **kw):
            nd = nt.nodes.new(t)
            for a, v in kw.items():
                if a in nd.inputs:
                    nd.inputs[a].default_value = v
                else:
                    setattr(nd, a, v)
            return nd

        def M(op, a, b):
            nd = N('ShaderNodeMath', operation=op)
            for i, v in enumerate((a, b)):
                if isinstance(v, (int, float)):
                    nd.inputs[i].default_value = v
                else:
                    nt.links.new(v, nd.inputs[i])
            return nd.outputs[0]

        out = N('ShaderNodeOutputWorld')
        tc = N('ShaderNodeTexCoord')
        # stars: two sizes
        cols = []
        for scale, thr, gain in ((300.0, 0.06, 5.0), (90.0, 0.035, 9.0)):
            vor = N('ShaderNodeTexVoronoi', Scale=scale)
            nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
            sep = N('ShaderNodeSeparateColor')
            nt.links.new(vor.outputs['Color'], sep.inputs[0])
            s = M('MULTIPLY', M('LESS_THAN', vor.outputs['Distance'], thr), M('POWER', sep.outputs[0], 7.0))
            cols.append(M('MULTIPLY', s, gain))
        stars = M('ADD', cols[0], cols[1])
        # nebula: two big soft cloud layers, warped, in two tints, with dark lanes
        warp = N('ShaderNodeTexNoise', Scale=1.1, Detail=3.0)
        nt.links.new(tc.outputs['Generated'], warp.inputs['Vector'])
        mixv = N('ShaderNodeMix', data_type='VECTOR')
        mixv.inputs[0].default_value = 0.32
        nt.links.new(tc.outputs['Generated'], mixv.inputs[4])
        nt.links.new(warp.outputs['Color'], mixv.inputs[5])
        tints = {'blue': ((0.003, 0.016, 0.05), (0.012, 0.07, 0.15), (0.075, 0.018, 0.004)),
                 'warm': ((0.03, 0.012, 0.004), (0.14, 0.06, 0.018), (0.008, 0.04, 0.09)),
                 'teal': ((0.003, 0.03, 0.045), (0.02, 0.12, 0.13), (0.09, 0.05, 0.015))}[tint]
        acc = None
        for i, (scale, lo, hi, c0, c1) in enumerate(((1.7, 0.47, 0.82, tints[0], tints[1]),
                                                     (2.9, 0.56, 0.86, (0, 0, 0), tints[2]))):
            nz = N('ShaderNodeTexNoise', Scale=scale, Detail=9.0, Roughness=0.62)
            mp = N('ShaderNodeMapping')
            mp.inputs['Location'].default_value = (i * 3.7, i * 1.3, 0.4 * i)
            nt.links.new(mixv.outputs[1], mp.inputs['Vector'])
            nt.links.new(mp.outputs[0], nz.inputs['Vector'])
            rp = N('ShaderNodeValToRGB')
            e = rp.color_ramp.elements
            e[0].position, e[0].color = lo, (0, 0, 0, 1)
            e[1].position, e[1].color = hi, (*c1, 1)
            mid = e.new((lo + hi) / 2)
            mid.color = (*c0, 1)
            nt.links.new(nz.outputs['Fac'], rp.inputs[0])
            if acc is None:
                acc = rp.outputs[0]
            else:
                ad = N('ShaderNodeMix', data_type='RGBA', blend_type='ADD')
                ad.inputs[0].default_value = 1.0
                nt.links.new(acc, ad.inputs[6])
                nt.links.new(rp.outputs[0], ad.inputs[7])
                acc = ad.outputs[2]
        sc_ = N('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY')
        sc_.inputs[0].default_value = 1.0
        nt.links.new(acc, sc_.inputs[6])
        sc_.inputs[7].default_value = (k, k, k, 1)
        ad = N('ShaderNodeMix', data_type='RGBA', blend_type='ADD')
        ad.inputs[0].default_value = 1.0
        nt.links.new(sc_.outputs[2], ad.inputs[6])
        nt.links.new(stars, ad.inputs[7])
        bg = N('ShaderNodeBackground')
        nt.links.new(ad.outputs[2], bg.inputs['Color'])
        nt.links.new(bg.outputs[0], out.inputs[0])

    # ------------------------------------------------------------------ ships
    def _build(self, kind):
        """Builds a ship once, or loads it from the scratch cache (a .blend per kind) to save minutes per run."""
        cache = os.path.join(SCRATCH, '_cache', f'ship_{kind}.blend')
        if os.path.exists(cache) and ARGS.get('nocache', '0') != '1':
            with bpy.data.libraries.load(cache) as (src, dst):
                dst.objects = list(src.objects)
            root = None
            for o in dst.objects:
                bpy.context.scene.collection.objects.link(o)
                if o.parent is None:
                    root = o
            extra = json.loads(root.get('bk_extra', 'null'))
            if isinstance(extra, list):
                extra = [Vector(e) for e in extra] if extra and isinstance(extra[0], list) else Vector(extra)
            root.location = (0, 0, -90000)
            self.sh.hide_tree(root, True)
            return root, extra
        if kind in ('dread', 'bship', 'frigate', 'missile', 'corvette'):
            ob, extra = V.terran_ship(kind)
        elif kind == 'twinx':
            ob, extra = T.twin_x_fighter('TwinXSrc', seed=4)
        elif kind == 'kesh':
            ob = HD.kesh_mothership()
            ob = ob[0] if isinstance(ob, tuple) else ob
            extra = [Vector(b) for b in ob['bays']]
        else:
            fn = {'crescent': AF.crescent_mothership_v2, 'shell': AF.shell_mothership_v2, 'lens': AF.lens_mothership_v2,
                  'acorv': AF.arcadian_corvette, 'sting': AF.stingray_fighter, 'squid': AF.squid_ship}[kind]
            with AF.gold_palette():
                ob, extra = fn()
        if kind == 'dread':
            extra = [Vector(b) for b in ob['bays']]
        ob.scale = (1, 1, 1)
        ob.location = (0, 0, 0)
        ob.rotation_euler = (0, 0, 0)
        bpy.context.view_layer.update()
        if isinstance(extra, Vector):
            ob['bk_extra'] = json.dumps(list(extra))
        elif isinstance(extra, list):
            ob['bk_extra'] = json.dumps([list(e) for e in extra])
        else:
            ob['bk_extra'] = json.dumps(extra)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        bpy.data.libraries.write(cache, set([ob] + list(ob.children_recursive)), fake_user=True)
        ob.location = (0, 0, -90000)
        self.sh.hide_tree(ob, True)
        return ob, extra

    def ship(self, kind, name=None, scale=None):
        """A (linked) copy of a fleet ship. The mesh is built once per kind."""
        if kind not in self._src:
            self._src[kind] = self._build(kind)
        src, extra = self._src[kind]
        ob = SP.copy_tree(src, name or self.uid(kind))
        for o in [ob] + list(ob.children_recursive):
            o.hide_render = False
        ob.location = (0, 0, 0)
        s = scale or SCALE.get(kind, 1.0)
        ob.scale = (s, s, s)
        ob['kind'] = kind
        return ob

    def extra(self, kind):
        return self._src[kind][1]

    def place(self, ob, pos, fwd=(1, 0, 0), roll=0.0, up='Z'):
        ob.location = pos
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = Vector(fwd).normalized().to_track_quat('X', up) @ Quaternion((1, 0, 0), math.radians(roll))
        bpy.context.view_layer.update()
        return ob

    def world_pt(self, ob, local):
        bpy.context.view_layer.update()
        return ob.matrix_world @ Vector(local)

    def bounds(self, ob):
        """Local centre and size of the ship's own bounding box."""
        bb = [Vector(b) for b in ob.bound_box]
        lo = Vector([min(b[i] for b in bb) for i in range(3)])
        hi = Vector([max(b[i] for b in bb) for i in range(3)])
        return (lo + hi) / 2, hi - lo

    # ------------------------------------------------------------------ shields
    def tshield(self, ob, hit=None, hit2=None, ring=0.33, grow=(0.62, 0.75, 1.0), pad=2.5, vis=1.0):
        """Terran triangle shield round ob. hit: WORLD point the shot comes from (the impact faces it)."""
        cen, dims = self.bounds(ob)
        size = (dims.x * grow[0], dims.y * grow[1] + pad, dims.z * grow[2] + pad)
        bpy.context.view_layer.update()

        def udir(p):
            if p is None:
                return None
            l = ob.matrix_world.inverted() @ Vector(p) - cen
            return tuple(Vector((l.x / size[0], l.y / size[1], l.z / size[2])).normalized())
        name = self.uid('TSh')
        twin = hit is not None and hit2 is None      # no second impact: use its slot for a second, inner ripple
        sh = SP.tshield(name, size, hit=udir(hit), hit2=udir(hit if twin else hit2))
        sh.parent = ob
        sh.scale = size
        sh.location = cen
        nd = sh.data.materials[0].node_tree.nodes
        nd['vis'].outputs[0].default_value = vis
        if hit is not None:
            nd['hitk'].outputs[0].default_value = 1.0
            nd['ring'].outputs[0].default_value = ring
        if twin:
            nd['hitk2'].outputs[0].default_value = 0.0
            nd['ring2'].outputs[0].default_value = ring * 0.55
        elif hit2 is not None:
            nd['hitk2'].outputs[0].default_value = 0.8
            nd['ring2'].outputs[0].default_value = ring * 1.6
        sh['size'] = size
        return sh

    def shield_point(self, ob, sh, frm):
        """World point where a shot from world point `frm` toward the ship's centre meets the shield."""
        cen, _ = self.bounds(ob)
        size = Vector(sh['size'])
        mi = ob.matrix_world.inverted()
        l = mi @ Vector(frm) - cen
        u = Vector((l.x / size.x, l.y / size.y, l.z / size.z)).normalized()
        return ob.matrix_world @ (cen + Vector((u.x * size.x, u.y * size.y, u.z * size.z)))

    def gshield(self, ob, hit=None, grow=(0.62, 0.66, 0.7), pad=2.0, vis=0.6):
        """Arcadian gold honeycomb shield. hit: WORLD point the shot comes from."""
        cen, dims = self.bounds(ob)
        size = (dims.x * grow[0], dims.y * grow[1] + pad, dims.z * grow[2] + pad)
        if hit is None:
            hp = (size[0] * 5, 0, size[2] * 5)
        else:
            l = ob.matrix_world.inverted() @ Vector(hit) - cen
            u = Vector((l.x / size[0], l.y / size[1], l.z / size[2])).normalized()
            hp = (u.x * size[0], u.y * size[1], u.z * size[2])
        sh = NP.shield_dome(size=size, hit=hp, name=self.uid('GSh'))
        sh.scale = size
        sh.parent = ob
        sh.location = cen
        sh.visible_shadow = False
        SP.add_fade(sh.data.materials[0], 'vis', vis)
        sh['size'] = size
        return sh

    # ------------------------------------------------------------------ weapons and effects
    def beam(self, p0, p1, col=GOLD, core=HOTGOLD, r=0.6, strength=40.0, glow=8.0, halo=2.4):
        """Straight energy beam p0 -> p1 (tapered ends), with a soft halo."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        nm = self.uid('Beam')
        o = C.uv_sphere(nm, 1.0, seg=(24, 12), mat=C.emit_mat(nm + 'Core', core, strength),
                        scale=(d.length / 2, r * 0.45, r * 0.45))
        h = C.uv_sphere(nm + 'Halo', 1.0, seg=(32, 16), mat=glow_mat(nm + 'Glow', col, glow, 2.0),
                        scale=(d.length / 2, r * halo, r * halo))
        for x in (o, h):
            x.location = (p0 + p1) / 2
            BP.aim(x, d)
            x.visible_shadow = False
        return o

    def flare(self, p, size, col=CYAN, k=10.0, core=(1, 1, 1), core_k=30.0, light=0.0, squash=None, d=None):
        """Soft round glow with a hot core (muzzle flash, impact, engine placeholder)."""
        nm = self.uid('Flare')
        o = C.uv_sphere(nm, 1.0, seg=(24, 12), mat=glow_mat(nm + 'M', col, k, 3.0))
        o.location = p
        o.scale = (size,) * 3 if squash is None else (size * squash, size, size)
        if d is not None:
            BP.aim(o, d)
        o.visible_shadow = False
        if core_k:
            c = C.uv_sphere(nm + 'Core', 1.0, seg=(16, 8), mat=C.emit_mat(nm + 'CoreM', core, core_k))
            c.parent = o
            c.scale = (0.16,) * 3
            c.visible_shadow = False
        if light:
            self.light(p, col, light, size * 0.5)
        return o

    def impact(self, p, size, col=GOLD, core=HOTGOLD, seed=1, light=0.0, sparks=14, away=None):
        """A beam or shot striking a shield: white-hot point, coloured glare, thin star spikes and sparks."""
        rnd = random.Random(seed)
        p = Vector(p)
        nm = self.uid('Impact')
        for r, mat in ((size * 0.16, C.emit_mat(nm + 'W', (1, 1, 1), 60.0)), (size * 0.3, C.emit_mat(nm + 'C', core, 25.0)),
                       (size, glow_mat(nm + 'G', col, 9.0, 3.0)), (size * 2.2, glow_mat(nm + 'G2', col, 1.2, 4.0))):
            o = C.uv_sphere(nm, 1.0, seg=(20, 10), mat=mat, scale=(r, r, r))
            o.location = p
            o.visible_shadow = False
        sm = C.emit_mat(nm + 'S', core, 30.0)
        to_cam = (self.cam.location - p).normalized()
        ax = to_cam.orthogonal().normalized()
        for i in range(7):
            d = Quaternion(to_cam, rnd.uniform(0, 2 * math.pi)) @ ax
            L = size * rnd.uniform(1.4, 3.2)
            o = C.uv_sphere(nm + 'Sp', 1.0, seg=(8, 4), mat=sm, scale=(L / 2, size * 0.035, size * 0.035))
            o.location = p + d * L * 0.5
            BP.aim(o, d)
            o.visible_shadow = False
        if sparks:
            self.shards(p, sparks, core, size * 0.09, size * 5.0, seed + 3, age=5, strength=14.0, drift=away)
        if light:
            self.light(p, col, light, size * 0.4)

    def light(self, p, col, energy, soft=2.0):
        L = bpy.data.objects.new(self.uid('L'), bpy.data.lights.new(self.uid('L'), 'POINT'))
        SP.link(L)
        L.location = p
        L.data.color = col
        L.data.energy = energy
        L.data.shadow_soft_size = soft
        L.visible_camera = L.visible_glossy = L.visible_transmission = False     # never seen as a white ball
        return L

    def muzzle(self, ship, local, stage='fire', scale=0.78):
        """The broadside battleship's own muzzle effect at gun mouth `local` (terran_fleet.muzzle_flash):
        stage 'charge' | 'fire' | 'fired'."""
        kw = {'charge': dict(charge=True, bolt=False, scale=scale, strength=28.0),
              'fire': dict(scale=scale, bolt_at=6.0, strength=45.0),
              'fired': dict(scale=scale * 0.6, bolt=False, strength=30.0)}[stage]
        fl = T.muzzle_flash(self.uid('Muzzle'), **kw)
        fl.parent = ship
        fl.location = local
        fl.rotation_euler = (0, 0, math.radians(-90))
        return fl

    def comet(self, p, d, scale=1.0):
        """The broadside battleship's blue comet shot, head at p flying along d."""
        o = BP.comet(self.uid('Comet'), scale=scale, seed=self._n, frames=self.sc.nf + 1)
        o.location = p
        BP.aim(o, d)
        return o

    def boom(self, p, size, kind='fire', age=5, light=0.0, seed=0):
        """Fireball caught `age` frames after it went off (5 = near its brightest, 14+ = fading cloud)."""
        fn = {'fire': SP.boom, 'blue': SP.blue_boom, 'gold': SP.gold_boom}[kind]
        return fn(Vector(p), FRAME - age, size, light=light, seed=seed, life=1.4)

    def shards(self, p, n, col, size, speed, seed, age=6, kind='tri', strength=4.0, drift=None):
        return SP.shards(Vector(p), FRAME - age, n, col, size, speed, seed, life=1.6, kind=kind, strength=strength,
                         drift=drift)

    def streak(self, p, d, length, col=CYAN, r=0.25, k=6.0, head=True):
        """A fighter or bolt read as a streak of light: head at p, trail behind along -d."""
        d = Vector(d).normalized()
        nm = self.uid('Streak')
        o = C.uv_sphere(nm, 1.0, seg=(16, 8), mat=glow_mat(nm + 'M', col, k, 1.6), scale=(length / 2, r, r))
        o.location = Vector(p) - d * length / 2
        BP.aim(o, d)
        o.visible_shadow = False
        if head:
            h = C.uv_sphere(nm + 'H', 1.0, seg=(12, 6), mat=C.emit_mat(nm + 'HM', (1, 1, 1), 40.0),
                            scale=(r * 1.6, r * 0.6, r * 0.6))
            h.location = p
            BP.aim(h, d)
            h.visible_shadow = False
        return o

    def bolt(self, p, d, length, col=CYAN, r=0.18, strength=35.0):
        """Short hard laser bolt, centred at p."""
        nm = self.uid('Bolt')
        o = C.uv_sphere(nm, 1.0, seg=(10, 6), mat=C.emit_mat(nm + 'M', col, strength), scale=(length / 2, r, r))
        o.location = p
        BP.aim(o, d)
        o.visible_shadow = False
        return o

    def lightning(self, pairs, width=0.3, seed=1):
        """Gold Arcadian lightning between pairs of world points."""
        return self.sh.lightning([(Vector(a), Vector(b)) for a, b in pairs], seed, width=width, name=self.uid('Lt'))

    def debris(self, p, n, spread, size, seed=1, stretch=(1, 1, 1), embers=0.3, gold=False):
        """Tumbling hull fragments round p (dark plates, some with glowing torn edges)."""
        rnd = random.Random(seed)
        dark = metal_mat('DebrisGold' if gold else 'DebrisDark', (0.16, 0.09, 0.03) if gold else (0.05, 0.055, 0.065),
                         0.4 if gold else 0.55)
        hot = C.emit_mat(self.uid('Ember'), GOLD if gold else ORANGE, 9.0)
        out = []
        for i in range(n):
            me = bpy.data.meshes.new('debris')
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            for v in bm.verts:
                v.co *= rnd.uniform(0.55, 1.25)
            s = size * rnd.uniform(0.35, 1.0) ** 1.5
            bmesh.ops.scale(bm, verts=bm.verts, vec=(s * rnd.uniform(0.8, 2.2), s * rnd.uniform(0.5, 1.2), s * rnd.uniform(0.12, 0.45)))
            bm.to_mesh(me)
            bm.free()
            o = bpy.data.objects.new(self.uid('Debris'), me)
            SP.link(o)
            me.materials.append(hot if rnd.random() < embers * 0.35 else dark)
            g = Vector((rnd.gauss(0, 1) * stretch[0], rnd.gauss(0, 1) * stretch[1], rnd.gauss(0, 1) * stretch[2]))
            o.location = Vector(p) + g * spread * 0.5
            o.rotation_euler = (rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6))
            out.append(o)
        return out

    def haze(self, z, k=0.6, col=(0.02, 0.05, 0.12), glow=0.0, size=60000.0):
        """A huge see-through sheet at height z that dims (k = how much is taken away) and tints what lies
        beyond it: quietens the planet under a top-down view and pushes it back."""
        m, n = BP._new_mat(self.uid('Haze'))
        tr = n.node('ShaderNodeBsdfTransparent')
        em = n.node('ShaderNodeEmission', Color=(*col, 1))
        em.inputs['Strength'].default_value = glow
        mx = n.node('ShaderNodeMixShader')
        mx.inputs[0].default_value = k
        n.set(mx.inputs[1], tr.outputs[0])
        n.set(mx.inputs[2], em.outputs[0])
        out = n.node('ShaderNodeOutputMaterial')
        n.set(out.inputs['Surface'], mx.outputs[0])
        o = box(self.uid('HazeSheet'), (size, size, 0.01), m, (0, 0, z))
        o.visible_shadow = False
        o.visible_diffuse = False
        o.visible_glossy = False
        return o

    def engines(self, ob, k=1.0, length=None):
        """Placeholder engine glow at the stern (David designs engines later): a plain soft blue glow with a
        short tail for Terrans, short gold lightning for Arcadians."""
        kind = ob.get('kind', '')
        if kind in ('crescent', 'shell', 'lens', 'acorv', 'sting', 'squid', 'kesh'):
            return V.engines(ob, self.uid('Eng'), GOLD, thr_keys=[(1, k)], len_keys=[(1, k)], length=length)
        bb = [Vector(b) for b in ob.bound_box]
        x0 = min(b.x for b in bb)
        ys, zs = [b.y for b in bb], [b.z for b in bb]
        W, H = max(ys) - min(ys), max(zs) - min(zs)
        cy, cz = (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2
        n = 1 if W < 6 else (2 if W < 12 else 3)
        r = min(W, H) * (0.2 if n == 1 else 0.13)
        nm = self.uid('Eng')
        gm = glow_mat(nm + 'G', (0.2, 0.55, 1.0), 1.3 * k, 2.2)
        cm = C.emit_mat(nm + 'C', (0.6, 0.85, 1.0), 6.0 * k)
        out = []
        for i in range(n):
            y = cy + (i - (n - 1) / 2) * W * 0.3
            L = (length or r * 5.0) * (0.6 + 0.4 * k)
            for mat, sc_, dx in ((gm, (L / 2, r * 1.2, r * 1.2), -L * 0.42), (cm, (r * 0.5, r * 0.42, r * 0.42), 0.0)):
                o = C.uv_sphere(nm + f'_{i}', 1.0, seg=(20, 10), mat=mat, scale=sc_)
                o.parent = ob
                o.location = (x0 + dx, y, cz)
                o.visible_shadow = False
                out.append(o)
        return out

    # ------------------------------------------------------------------ camera
    def camera(self, pos, target, lens=28, roll=0.0):
        sc = bpy.context.scene
        cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_start = 0.05
        cam.data.clip_end = 120000
        cam.data.sensor_width = 36
        cam.data.lens = lens
        cam.location = pos
        q = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y')
        if roll:
            q = q @ Quaternion((0, 0, 1), math.radians(roll))
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = q
        bpy.context.view_layer.update()
        self.cam = cam
        return cam

    def cam_pt(self, x, y, depth):
        """World point at screen position (x, y in -1..1, x right, y up, frame edges at +-1) and distance depth."""
        cam = self.cam
        sc = bpy.context.scene
        hw = 18.0 / cam.data.lens
        hh = hw * sc.render.resolution_y / sc.render.resolution_x
        return cam.matrix_world @ Vector((x * hw * depth, y * hh * depth, -depth))

    # ------------------------------------------------------------------ render + post
    def render(self, out, res=None, samples=None, exposure=0.0, bloom=1.0, look='AgX - Punchy', vignette=0.25):
        sc = bpy.context.scene
        if res is None:
            w, h = getattr(self, 'res', (1920, 1080))
            res = (w, h) if self.final else (w // 2, h // 2)
        if samples is None:
            samples = 44 if self.final else 16
        self.sh.render_settings(res, samples, blur=False)
        sc.cycles.adaptive_threshold = 0.04 if self.final else 0.06
        sc.cycles.transparent_max_bounces = 24
        sc.cycles.max_bounces = 4
        sc.cycles.sample_clamp_direct = 0.0
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = int(ARGS.get('threads', 3))
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = look
        sc.view_settings.exposure = exposure
        sc.frame_set(FRAME)
        if 'samples' in ARGS:                       # debugging aids: --samples=N --border=x0,y0,x1,y1 --hide=Name,Name
            sc.cycles.samples = int(ARGS['samples'])
        if 'border' in ARGS:
            x0, y0, x1, y1 = (float(v) for v in ARGS['border'].split(','))
            sc.render.use_border, sc.render.use_crop_to_border = True, True
            sc.render.border_min_x, sc.render.border_min_y, sc.render.border_max_x, sc.render.border_max_y = x0, y0, x1, y1
        for sub in [h for h in ARGS.get('hide', '').split(',') if h]:
            for o in bpy.data.objects:
                if sub in o.name:
                    o.hide_render = True
                    if o.animation_data:
                        o.animation_data_clear()
        os.makedirs(SCRATCH, exist_ok=True)
        raw = os.path.join(SCRATCH, os.path.splitext(os.path.basename(out))[0] + '_raw.png')
        sc.render.filepath = raw
        bpy.ops.render.render(write_still=True)
        im = post(raw, bloom, vignette)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.save(out, quality=92)
        print('WROTE', out, flush=True)
        return out


def post(path, bloom=1.0, vignette=0.25):
    """2D glow round bright pixels (Cycles has no bloom) and a gentle vignette."""
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255.0
    lum = a.max(axis=2, keepdims=True)
    b = Image.fromarray((np.clip((lum - 0.7) / 0.3, 0, 1) * a * 255).astype(np.uint8))
    k = a.shape[1] / 1280.0
    glow = np.zeros_like(a)
    for r, w in [(3, 0.45), (10, 0.38), (28, 0.3), (70, 0.2)]:
        glow += np.asarray(b.filter(ImageFilter.GaussianBlur(r * k))).astype(np.float32) / 255.0 * w
    o = 1 - (1 - a) * (1 - np.clip(glow * bloom, 0, 1))
    if vignette:
        h, w = o.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
        o *= (1 - vignette * np.clip(r2 - 0.35, 0, 1.5) / 1.5)[..., None]
    return Image.fromarray((np.clip(o, 0, 1) * 255).astype(np.uint8))


# ====================================================================== bay doors for the fleet view
def _prim(kind, parent, loc, quat, mat, **kw):
    getattr(bpy.ops.mesh, 'primitive_' + kind + '_add')(**kw)
    o = bpy.context.active_object
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.materials.append(mat)
    o.parent = parent
    o.location = loc
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = quat
    return o


def arcadian_bay(kit, ship, c, n, r):
    """A lit bay mouth set into an Arcadian hull (all in the SHIP'S LOCAL space: centre c, outward normal n,
    radius r): bronze collar, dark throat, a glowing gold force field, a bright lip and a ring of guide lights."""
    c, n = Vector(c), Vector(n).normalized()
    q = n.to_track_quat('Z', 'Y')
    bronze = metal_mat('BayBronze', (0.32, 0.18, 0.06), 0.4, 1.0)
    gold = metal_mat('BayGoldMetal', (0.9, 0.6, 0.2), 0.3, 1.0)
    field = C.emit_mat('BayFieldG', (1.0, 0.45, 0.08), 2.0)
    lip = C.emit_mat('BayLipG', (1.0, 0.7, 0.3), 12.0)
    dark = metal_mat('BayThroat', (0.01, 0.008, 0.005), 0.8, 0.0)
    _prim('cylinder', ship, c - n * 0.5, q, bronze, radius=r * 1.22, depth=2.2, vertices=48)
    _prim('torus', ship, c + n * 0.62, q, gold, major_radius=r * 1.14, minor_radius=r * 0.13, major_segments=64, minor_segments=12)
    _prim('cylinder', ship, c + n * 0.56, q, dark, radius=r * 1.04, depth=0.1, vertices=48)
    _prim('cylinder', ship, c + n * 0.64, q, field, radius=r * 0.9, depth=0.04, vertices=48)
    _prim('torus', ship, c + n * 0.7, q, lip, major_radius=r * 0.94, minor_radius=r * 0.045, major_segments=64, minor_segments=8)
    _prim('torus', ship, c + n * 0.68, q, lip, major_radius=r * 0.5, minor_radius=r * 0.02, major_segments=48, minor_segments=6)
    for i in range(12):
        a = 2 * math.pi * i / 12
        _prim('uv_sphere', ship, c + n * 0.5 + q @ Vector((math.cos(a), math.sin(a), 0)) * r * 1.5, q, lip,
              radius=r * 0.075, segments=10, ring_count=6)
    L = kit.light((0, 0, 0), (1.0, 0.6, 0.2), 1.5e4 * r * r, r * 0.5)
    L.parent = ship
    L.location = c + n * r * 1.2
    return c


def terran_bay(kit, ship, c, side, w=4.1, h=1.45):
    """Lights up one of the dreadnought's own side bays (ship LOCAL space, c = bay centre, side = +1/-1 for the
    +Y / -Y flank): a cyan force field in the opening and a lit door frame flush with the housing."""
    c = Vector(c)
    y = Vector((0, side, 0))
    field = C.emit_mat('BayFieldT', (0.1, 0.55, 1.0), 4.5)
    neon = C.emit_mat('BayFrameT', (0.3, 0.8, 1.0), 26.0)
    plate = metal_mat('BayPlateT', (0.09, 0.1, 0.12), 0.4, 0.9)
    box('TBayField', (w, 0.02, h), field, c + y * 0.06, parent=ship)
    for dz in (-1, 1):
        box('TBayJ', (w + 0.5, 0.16, 0.16), plate, c + y * 0.1 + Vector((0, 0, dz * (h / 2 + 0.1))), parent=ship)
        box('TBayN', (w + 0.3, 0.05, 0.05), neon, c + y * 0.2 + Vector((0, 0, dz * (h / 2 + 0.02))), parent=ship)
    for dx in (-1, 1):
        box('TBayJ', (0.16, 0.16, h + 0.36), plate, c + y * 0.1 + Vector((dx * (w / 2 + 0.1), 0, 0)), parent=ship)
        box('TBayN', (0.05, 0.05, h + 0.1), neon, c + y * 0.2 + Vector((dx * (w / 2 + 0.02), 0, 0)), parent=ship)
    L = kit.light((0, 0, 0), (0.2, 0.7, 1.0), 4e5, 1.0)
    L.parent = ship
    L.location = c + y * 3.0
    return c


# ====================================================================== foreground frame placeholders
def terran_door(kit, open_w=0.90, open_h=0.83, dist=7.0, y_shift=0.03):
    """Plain dark angular hangar-door frame round the view (placeholder; the interior is designed elsewhere).
    open_w / open_h: fraction of the picture left open."""
    cam = kit.cam
    sc = bpy.context.scene
    hw = 18.0 / cam.data.lens * dist
    hh = hw * 9 / 16
    ow, oh = hw * open_w, hh * open_h
    cy = hh * y_shift
    dark = metal_mat('DoorDark', (0.035, 0.04, 0.05), 0.5, 0.85)
    plate = metal_mat('DoorPlate', (0.07, 0.08, 0.095), 0.42, 0.9)
    neon = C.emit_mat('DoorNeon', (0.18, 0.62, 1.0), 14.0)
    amber = C.emit_mat('DoorAmber', (1.0, 0.45, 0.08), 18.0)
    root = bpy.data.objects.new('TerranDoor', None)
    sc.collection.objects.link(root)
    root.parent = cam
    root.location = (0, cy, -dist)
    big = hw * 3
    D = 0.9                                     # depth of the door tunnel
    # the four sides (thick slabs) and chamfered top corners
    box('DoorL', (big, big * 2, D), dark, (-ow - big / 2, 0, 0), parent=root)
    box('DoorR', (big, big * 2, D), dark, (ow + big / 2, 0, 0), parent=root)
    box('DoorT', (big * 2, big, D), dark, (0, oh + big / 2, 0), parent=root)
    box('DoorB', (big * 2, big, D), dark, (0, -oh - big / 2, 0), parent=root)
    ch = ow * 0.2
    for s in (-1, 1):
        box(f'DoorCh{s}', (ch * 2.2, ch * 2.2, D), dark, (s * ow, oh, 0), rot=(0, 0, math.radians(45)), parent=root)
        box(f'DoorChB{s}', (ch * 1.1, ch * 1.1, D), dark, (s * ow, -oh, 0), rot=(0, 0, math.radians(45)), parent=root)
        # inner trim plates and a neon line running down each jamb
        box(f'DoorTrim{s}', (0.16, oh * 1.3, D * 1.06), plate, (s * (ow + 0.06), -oh * 0.12, 0), parent=root, bevel=0.02)
        box(f'DoorNeon{s}', (0.035, oh * 1.15, 0.035), neon, (s * (ow - 0.03), -oh * 0.14, D / 2 + 0.01), parent=root)
        for j in range(3):
            box(f'DoorAmb{s}{j}', (0.07, 0.035, 0.035), amber, (s * (ow - 0.03), -oh * 0.86 - 0.0 + j * 0.0, D / 2 + 0.02 + 0 * j),
                parent=root).location.y += j * 0.14
    box('DoorSill', (ow * 2.1, 0.14, D * 1.06), plate, (0, -oh - 0.05, 0), parent=root, bevel=0.02)
    box('DoorLintel', (ow * 1.5, 0.12, D * 1.06), plate, (0, oh + 0.04, 0), parent=root, bevel=0.02)
    box('DoorNeonT', (ow * 0.5, 0.018, 0.02), neon, (0, oh - 0.02, D / 2 + 0.01), parent=root)
    # dim cool light from inside the hangar so the frame is dark but not a black cut-out
    L = bpy.data.objects.new('DoorLight', bpy.data.lights.new('DoorLight', 'AREA'))
    sc.collection.objects.link(L)
    L.parent = cam
    L.location = (0, hh * 0.5, -1.0)
    L.data.size = hw * 1.5
    L.data.energy = 260.0 * (dist / 7.0) ** 2
    L.data.color = (0.55, 0.72, 1.0)
    return root


def arcadian_arch(kit, open_w=0.93, open_h=0.90, dist=7.0, y_shift=0.02):
    """Plain curved gold-bronze opening round the view (placeholder): an oval mouth with a rolled rim."""
    cam = kit.cam
    sc = bpy.context.scene
    hw = 18.0 / cam.data.lens * dist
    hh = hw * 9 / 16
    D = 1.0
    a, b = hw * open_w * (dist + D / 2) / dist, hh * open_h * (dist + D / 2) / dist
    root = bpy.data.objects.new('ArcadianArch', None)
    sc.collection.objects.link(root)
    root.parent = cam
    root.location = (0, hh * y_shift, -dist)
    bronze = metal_mat('ArchBronze', (0.30, 0.17, 0.06), 0.42, 1.0)
    gold = metal_mat('ArchGold', (0.9, 0.6, 0.2), 0.28, 1.0)
    glow = C.emit_mat('ArchGlow', (1.0, 0.6, 0.15), 10.0)
    N = 96

    def oval(k, power=3.4):
        pts = []
        for i in range(N):
            t = 2 * math.pi * i / N
            c, s = math.cos(t), math.sin(t)
            pts.append((a * k * math.copysign(abs(c) ** (2 / power), c), b * k * math.copysign(abs(s) ** (2 / power), s)))
        return pts
    # wall with the oval hole (flaring wider toward the camera)
    me = bpy.data.meshes.new('ArchWall')
    bm = bmesh.new()
    rings = []
    for k, z in ((1.0, -D / 2), (1.02, 0.0), (1.1, D / 2), (6.0, D / 2)):
        rings.append([bm.verts.new((x, y, z)) for x, y in oval(k)])
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for i in range(N):
            bm.faces.new((r0[i], r0[(i + 1) % N], r1[(i + 1) % N], r1[i]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    wall = bpy.data.objects.new('ArchWall', me)
    sc.collection.objects.link(wall)
    me.materials.append(bronze)
    wall.parent = root

    def tube(name, k, z, r, mat):
        pts = oval(k)
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        S = 10
        rs = []
        for i, (x, y) in enumerate(pts):
            px, py = pts[(i + 1) % N]
            qx, qy = pts[i - 1]
            tx, ty = px - qx, py - qy
            ln = math.hypot(tx, ty)
            nx, ny = ty / ln, -tx / ln
            rs.append([bm.verts.new((x + nx * r * math.cos(2 * math.pi * j / S), y + ny * r * math.cos(2 * math.pi * j / S),
                                     z + r * math.sin(2 * math.pi * j / S))) for j in range(S)])
        for i in range(N):
            for j in range(S):
                bm.faces.new((rs[i][j], rs[(i + 1) % N][j], rs[(i + 1) % N][(j + 1) % S], rs[i][(j + 1) % S]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        sc.collection.objects.link(o)
        me.materials.append(mat)
        o.parent = root
        return o
    tube('ArchRim', 1.0, -D / 2, 0.11, gold)
    tube('ArchRim2', 1.075, D * 0.3, 0.06, gold)
    tube('ArchLine', 1.022, -D / 2 + 0.22, 0.014, glow)
    tube('ArchLine2', 1.12, D * 0.5, 0.012, glow)
    L = bpy.data.objects.new('ArchLight', bpy.data.lights.new('ArchLight', 'AREA'))
    sc.collection.objects.link(L)
    L.parent = cam
    L.location = (0, hh * 0.4, -1.0)
    L.data.size = hw * 1.5
    L.data.energy = 420.0 * (dist / 7.0) ** 2
    L.data.color = (1.0, 0.72, 0.4)
    return root


def arcadian_mouth(kit, dist=7.0):
    """Arcadian bay mouth round the view, second version (placeholder for the interior team's own): the
    opening is a big oval pushed toward the upper right, so the wall shows as a CRESCENT, thick at the lower
    left and thinning to nothing at the upper right. Etched line inlay follows the curve, the lip glows
    gold, and a thin precise tick-marked force ring sits just inside the lip. Returns rim points (world)
    for lightning arcs."""
    cam = kit.cam
    sc = bpy.context.scene
    hw = 18.0 / cam.data.lens * dist
    hh = hw * sc.render.resolution_y / sc.render.resolution_x
    root = bpy.data.objects.new('ArcadianMouth', None)
    sc.collection.objects.link(root)
    root.parent = cam
    root.location = (hw * 0.17, hh * 0.22, -dist)
    a, b = hw * 1.13, hh * 1.17
    bronze = metal_mat('MouthBronze', (0.11, 0.06, 0.022), 0.55, 1.0)
    gold = metal_mat('MouthGold', (0.9, 0.6, 0.2), 0.25, 1.0)
    inlay = C.emit_mat('MouthInlay', (1.0, 0.55, 0.12), 2.2)
    glow = C.emit_mat('MouthGlow', (1.0, 0.68, 0.25), 16.0)
    ring = C.emit_mat('MouthRing', (1.0, 0.86, 0.6), 22.0)
    N = 160
    D = 0.7

    def oval(k, power=2.25):
        pts = []
        for i in range(N):
            t = 2 * math.pi * i / N
            c, s_ = math.cos(t), math.sin(t)
            pts.append(Vector((a * k * math.copysign(abs(c) ** (2 / power), c), b * k * math.copysign(abs(s_) ** (2 / power), s_), 0)))
        return pts

    me = bpy.data.meshes.new('MouthWall')
    bm = bmesh.new()
    rings = [[bm.verts.new((p.x, p.y, z)) for p in oval(kk)] for kk, z in ((1.0, -D / 2), (1.012, 0.0), (1.05, D / 2), (7.0, D / 2))]
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for i in range(N):
            bm.faces.new((r0[i], r0[(i + 1) % N], r1[(i + 1) % N], r1[i]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    wall = bpy.data.objects.new('MouthWall', me)
    sc.collection.objects.link(wall)
    me.materials.append(bronze)
    wall.parent = root

    def tube(name, kk, z, r, mat, i0=0, i1=N):
        pts = oval(kk)
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        S = 8
        rs = []
        idx = list(range(i0, i1 + (0 if i1 - i0 >= N else 1)))
        for i in idx:
            p, q, o = pts[i % N], pts[(i + 1) % N], pts[(i - 1) % N]
            t = (q - o).normalized()
            nrm = Vector((t.y, -t.x, 0))
            rs.append([bm.verts.new(p + nrm * r * math.cos(2 * math.pi * j / S) + Vector((0, 0, z + r * math.sin(2 * math.pi * j / S))))
                       for j in range(S)])
        closed = i1 - i0 >= N
        for i in range(len(rs) - (0 if closed else 1)):
            for j in range(S):
                bm.faces.new((rs[i][j], rs[(i + 1) % len(rs)][j], rs[(i + 1) % len(rs)][(j + 1) % S], rs[i][(j + 1) % S]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        sc.collection.objects.link(o)
        me.materials.append(mat)
        o.parent = root
        return o
    tube('MouthLip', 1.0, -D / 2, 0.075, gold)
    tube('MouthLipGlow', 1.008, -D / 2 + 0.11, 0.014, glow)
    # etched inlay on the wall face: long curved lines of different lengths, like the ships' hull engraving
    lo, hi = int(N * 0.40), int(N * 0.84)                   # the thick part of the crescent (left, bottom-left, bottom)
    for j, (kk, i0, i1) in enumerate(((1.075, lo - 14, hi + 12), (1.10, lo, hi), (1.135, lo + 10, hi - 12), (1.15, lo + 12, hi - 14),
                                      (1.20, lo + 22, hi - 26), (1.26, lo + 30, hi - 34))):
        tube(f'MouthInlay{j}', kk, D / 2 + 0.004, 0.007 if j % 2 else 0.011, inlay, i0, i1)
    pts = oval(1.0)
    for i in range(lo - 10, hi + 10, 4):                    # short radial strokes between the first two lines
        p = pts[i % N]
        q = oval(1.075)[i % N].lerp(oval(1.10)[i % N], 1.0 if i % 16 == 0 else 0.0)
        p0 = oval(1.075)[i % N]
        d = (q - p0)
        if d.length > 1e-4:
            bx = box('MouthStroke', (0.008, d.length, 0.008), inlay, (p0 + q) / 2 + Vector((0, 0, D / 2 + 0.004)), parent=root)
            bx.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.pi / 2)
    # the force ring: a hair-thin bright ring just inside the lip, with tick marks (every 5th one long)
    tube('MouthRing', 0.972, -D / 2 - 0.02, 0.006, ring)
    inner = oval(0.972)
    for i in range(0, N, 2):
        p = inner[i]
        inward = (-p).normalized()
        L = 0.085 if i % 10 == 0 else 0.035
        bx = box('MouthTick', (0.007, L, 0.007), ring, p + inward * L / 2 + Vector((0, 0, -D / 2 - 0.02)), parent=root)
        bx.rotation_euler = (0, 0, math.atan2(inward.y, inward.x) - math.pi / 2)
    L = bpy.data.objects.new('MouthLight', bpy.data.lights.new('MouthLight', 'AREA'))
    sc.collection.objects.link(L)
    L.parent = cam
    L.location = (-hw * 0.3, -hh * 0.2, -1.0)
    L.data.size = hw * 1.2
    L.data.energy = 170.0 * (dist / 7.0) ** 2
    L.data.color = (1.0, 0.72, 0.4)
    L.visible_transmission = False
    bpy.context.view_layer.update()
    return [root.matrix_world @ (p + Vector((0, 0, -D / 2))) for p in oval(1.0)]
