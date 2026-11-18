"""Bake the promo VFX flipbook library (run once; scenes only play the results back).

    /home/user/artenv/venv/bin/python tools/promos/fx/bake_fx.py              # everything
    /home/user/artenv/venv/bin/python tools/promos/fx/bake_fx.py --only explo_ground_a,fire_loop
    /home/user/artenv/venv/bin/python tools/promos/fx/bake_fx.py --only explo_ground_a --test   # 6 frames, low res

Output: $PROMO_FX (default /mnt/project-files/promos/fx)/<name>/0001.png ... (RGBA, straight
alpha, sRGB) and <root>/manifest.json (merged per effect).

How it works. Mantaflow cannot run in this pip bpy build (its LevelsetGrid python binding lost
its Grid<Real> base, so the generated solver script dies on setConst()), so every effect is a
small hand-written particle simulation of "puffs". Each puff is an icosphere carrying a shared
volumetric shader: density = soft sphere eroded by 4D fBm noise (the noise's W coordinate is
keyed so the puff boils; its rotation is keyed so it rolls), heat drives a fire colour ramp in
the volume emission, soot darkens the scattering colour. The puffs are rendered once with
Cycles volumes (sun + sky light, transparent film) into premultiplied EXRs, then converted to
straight-alpha PNG: glowing pixels get alpha from their luminance so thin fire survives the
conversion. Loops (smoke plume, wreck fire) are made seamless by emitting puffs on a schedule
whose period is the loop length and rendering one period after a warm-up.

Frame of reference for every flipbook: orthographic side view (looking +Y), the effect's origin
(ground contact or burst centre) at manifest 'origin' (u, v in 0..1 of the image, v from the
bottom), the image spanning manifest 'extent' metres for an effect of size 1.
"""
import argparse
import json
import math
import os
import random
import struct
import sys
import time
import zlib

import bpy  # noqa: I001
import bmesh
import numpy as np
from mathutils import Euler, Vector

ROOT = os.environ.get('PROMO_FX', '/mnt/project-files/promos/fx')
FPS = 24
TMP = os.environ.get('PROMO_FX_TMP', '/tmp/promo_fx_exr')


# ------------------------------------------------------------------------------- png writer
def write_png(path, rgba8):
    """rgba8: (h, w, 4) uint8, top row first."""
    h, w, _ = rgba8.shape
    raw = b''.join(b'\x00' + rgba8[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as fh:
        fh.write(png)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def exr_to_png(exr, png, glow_alpha=1.4, gain=1.0):
    img = bpy.data.images.load(exr)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]          # blender rows are bottom-up
    c = px[..., :3] * gain                  # premultiplied linear
    a = np.clip(px[..., 3], 0, 1)
    lum = c @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    a2 = np.clip(np.maximum(a, lum * glow_alpha), 0, 1)
    st = c / np.maximum(a2, 1e-4)[..., None]
    out = np.concatenate([srgb(st), a2[..., None]], axis=-1)
    write_png(png, (out * 255 + 0.5).astype(np.uint8))
    return float(a2.max())


# ------------------------------------------------------------------------------- scene
def reset(res, extent, origin, samples=24, sun=(40, 0, -30), sun_energy=4.0, sky=0.55):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'CPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.03
    cy.use_denoising = True
    cy.max_bounces = 4
    cy.volume_bounces = 1
    cy.diffuse_bounces = 0
    cy.transparent_max_bounces = 16
    cy.volume_step_rate = 1.5
    cy.volume_max_steps = 256
    if hasattr(cy, 'volume_biased'):
        cy.volume_biased = True
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '16'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    sc.render.fps = FPS
    w = bpy.data.worlds.new('W')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs['Strength'].default_value = sky
    s = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sc.collection.objects.link(s)
    s.data.energy = sun_energy
    s.data.color = (1.0, 0.95, 0.88)
    s.data.angle = math.radians(3)
    s.rotation_euler = [math.radians(a) for a in sun]
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    W = extent
    H = extent * res[1] / res[0]
    cam.data.ortho_scale = max(W, H)
    # origin (u, v) of the image sits at world (0, 0, 0)
    ou, ov = origin
    cam.location = ((0.5 - ou) * W, -40, (0.5 - ov) * H)
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_end = 200
    return sc


_MAT = {}


def puff_mat(kind='smoke', albedo=(0.5, 0.5, 0.5), dark=(0.035, 0.032, 0.03), dens=6.0, fire=6.0,
             noise_scale=1.4, erosion=1.1, edge=0.28, ramp=None):
    """Volumetric puff. Object colour drives it per puff: R heat 0..1, G density scale, B soot
    0..1 (scatter albedo -> dark), A noise evolution (keyed: boiling)."""
    key = (kind, albedo, dark, dens, fire, noise_scale, erosion, edge)
    if key in _MAT:
        return _MAT[key]
    m = bpy.data.materials.new('Puff_' + kind)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    Lk = nt.links.new
    out = N('ShaderNodeOutputMaterial')
    oi = N('ShaderNodeObjectInfo')
    sep = N('ShaderNodeSeparateColor')
    Lk(oi.outputs['Color'], sep.inputs[0])
    tc = N('ShaderNodeTexCoord')
    ln = N('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    Lk(tc.outputs['Object'], ln.inputs[0])
    # noise: 4D fbm, W = random seed + keyed evolution
    wv = N('ShaderNodeMath')
    wv.operation = 'MULTIPLY_ADD'
    Lk(oi.outputs['Random'], wv.inputs[0])
    wv.inputs[1].default_value = 37.0
    Lk(oi.outputs['Alpha'], wv.inputs[2])
    nz = N('ShaderNodeTexNoise')
    nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = noise_scale
    nz.inputs['Detail'].default_value = 7.0
    nz.inputs['Roughness'].default_value = 0.58
    nz.inputs['Distortion'].default_value = 0.25
    Lk(tc.outputs['Object'], nz.inputs['Vector'])
    Lk(wv.outputs[0], nz.inputs['W'])
    # shape = (1 - r) + (noise - 0.5) * erosion
    a1 = N('ShaderNodeMath')
    a1.operation = 'SUBTRACT'
    a1.inputs[0].default_value = 1.0
    Lk(ln.outputs['Value'], a1.inputs[1])
    a2 = N('ShaderNodeMath')
    a2.operation = 'SUBTRACT'
    Lk(nz.outputs['Fac'], a2.inputs[0])
    a2.inputs[1].default_value = 0.5
    a3 = N('ShaderNodeMath')
    a3.operation = 'MULTIPLY_ADD'
    Lk(a2.outputs[0], a3.inputs[0])
    a3.inputs[1].default_value = erosion
    Lk(a1.outputs[0], a3.inputs[2])
    sh = N('ShaderNodeMapRange')
    sh.interpolation_type = 'SMOOTHSTEP'
    sh.inputs['From Min'].default_value = 0.0
    sh.inputs['From Max'].default_value = edge
    Lk(a3.outputs[0], sh.inputs['Value'])
    dm = N('ShaderNodeMath')
    dm.operation = 'MULTIPLY'
    Lk(sh.outputs['Result'], dm.inputs[0])
    Lk(sep.outputs['Green'], dm.inputs[1])
    dk = N('ShaderNodeMath')
    dk.operation = 'MULTIPLY'
    Lk(dm.outputs[0], dk.inputs[0])
    dk.inputs[1].default_value = dens
    pv = N('ShaderNodeVolumePrincipled')
    Lk(dk.outputs[0], pv.inputs['Density'])
    # albedo: light -> soot
    mx = N('ShaderNodeMix')
    mx.data_type = 'RGBA'
    mx.inputs['A'].default_value = (*albedo, 1)
    mx.inputs['B'].default_value = (*dark, 1)
    Lk(sep.outputs['Blue'], mx.inputs['Factor'])
    Lk(mx.outputs['Result'], pv.inputs['Color'])
    # fire: heat * deeper shape (core of each puff burns hotter), noisy
    hs = N('ShaderNodeMapRange')
    hs.inputs['From Min'].default_value = 0.05
    hs.inputs['From Max'].default_value = 0.75
    a4 = N('ShaderNodeMath')
    a4.operation = 'MULTIPLY_ADD'
    Lk(a2.outputs[0], a4.inputs[0])
    a4.inputs[1].default_value = erosion * 1.6
    Lk(a1.outputs[0], a4.inputs[2])
    Lk(a4.outputs[0], hs.inputs['Value'])
    ht = N('ShaderNodeMath')
    ht.operation = 'MULTIPLY'
    ht.use_clamp = True
    Lk(hs.outputs['Result'], ht.inputs[0])
    Lk(sep.outputs['Red'], ht.inputs[1])
    hp = N('ShaderNodeMath')     # heat^0.8 so mid heat still glows
    hp.operation = 'POWER'
    Lk(ht.outputs[0], hp.inputs[0])
    hp.inputs[1].default_value = 0.8
    cr = N('ShaderNodeValToRGB')
    el = cr.color_ramp.elements
    stops = ramp or [(0.0, (0, 0, 0)), (0.12, (0.25, 0.015, 0.0)), (0.35, (0.9, 0.12, 0.01)),
                     (0.6, (1.0, 0.38, 0.04)), (0.85, (1.0, 0.62, 0.16)), (1.0, (1.0, 0.85, 0.5))]
    el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
    el[1].position, el[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p_, c_ in stops[1:-1]:
        e = el.new(p_)
        e.color = (*c_, 1)
    Lk(hp.outputs[0], cr.inputs['Fac'])
    Lk(cr.outputs['Color'], pv.inputs['Emission Color'])
    es = N('ShaderNodeMath')
    es.operation = 'MULTIPLY'
    Lk(hp.outputs[0], es.inputs[0])
    es.inputs[1].default_value = fire
    es2 = N('ShaderNodeMath')
    es2.operation = 'MULTIPLY'
    Lk(es.outputs[0], es2.inputs[0])
    Lk(sh.outputs['Result'], es2.inputs[1])
    Lk(es2.outputs[0], pv.inputs['Emission Strength'])
    Lk(pv.outputs[0], out.inputs['Volume'])
    _MAT[key] = m
    return m


_ICO = {}


def puff_obj(mat, sub=2):
    if sub not in _ICO:
        me = bpy.data.meshes.new('PuffMesh')
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        bm.to_mesh(me)
        bm.free()
        _ICO[sub] = me
    o = bpy.data.objects.new('Puff', _ICO[sub].copy())
    o.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(o)
    return o


class Puff:
    """Kinematic puff: position/velocity integrated with drag + buoyancy, keyed every frame."""

    def __init__(self, mat, t0, pos, vel, r0, r1, grow, heat, cool, dens=1.0, soot0=0.0,
                 buoy=2.0, drag=3.0, spin=None, evolve=0.9, fade=None, life=99, rnd=None,
                 ground=True, soot_rate=1.6, wind=(0, 0, 0), drag_late=1.2, spread=0.0):
        self.o = puff_obj(mat)
        self.t0, self.p, self.v = t0, Vector(pos), Vector(vel)
        self.r0, self.r1, self.grow = r0, r1, grow
        self.heat0, self.cool, self.dens, self.soot0 = heat, cool, dens, soot0
        self.buoy, self.drag, self.evolve = buoy, drag, evolve
        rnd = rnd or random
        self.rot0 = Euler((rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)))
        self.spin = spin or Vector((rnd.uniform(-1.5, 1.5), rnd.uniform(-1.5, 1.5), rnd.uniform(-1.5, 1.5)))
        self.fade = fade      # (t_start, t_end) density fade-out relative to t0
        self.life = life
        self.ground = ground
        self.soot_rate = soot_rate
        self.wind = Vector(wind)
        self.drag_late = drag_late
        self.spread = spread

    def state(self, t):
        a = t - self.t0
        return a

    def run(self, frames, dt=1.0 / FPS, substeps=4):
        """Integrate from t0 and key frames (list of (frame_number, t))."""
        o = self.o
        t = self.t0
        p = self.p.copy()
        v = self.v.copy()
        h = 1.0 / (FPS * substeps)
        hidden_keyed = False
        for fr, tf in frames:
            if tf < self.t0 or tf > self.t0 + self.life:
                if not hidden_keyed or True:
                    o.hide_render = True
                    o.keyframe_insert('hide_render', frame=fr)
                continue
            while t < tf - 1e-6:
                age = t - self.t0
                heat = self.heat0 * math.exp(-age / self.cool) if self.cool > 0 else 0
                dr = self.drag * math.exp(-age / 0.35) + min(self.drag, self.drag_late)
                acc = Vector((0, 0, self.buoy * (0.5 + heat))) - (v - self.wind) * dr
                v += acc * h
                p += v * h
                if self.ground:
                    r_ = self.radius(age)
                    if p.z < r_ * 0.35:
                        p.z = r_ * 0.35
                        v.z = max(v.z, 0)
                t += h
            age = tf - self.t0
            heat = self.heat0 * math.exp(-age / self.cool) if self.cool > 0 else 0
            soot = min(1.0, self.soot0 + (1 - heat) * self.soot_rate * min(1, age * 4)) if self.heat0 > 0 else self.soot0
            d = self.dens
            if self.fade:
                f0, f1 = self.fade
                d *= 1 - max(0.0, min(1.0, (age - f0) / max(1e-3, f1 - f0)))
            d *= min(1.0, age * FPS / 1.5 + 0.35)
            o.location = p
            r = self.radius(age)
            o.scale = (r, r, r)
            o.rotation_euler = Euler((self.rot0.x + self.spin.x * age, self.rot0.y + self.spin.y * age,
                                      self.rot0.z + self.spin.z * age))
            o.color = (heat, d, soot, self.evolve * age)
            o.hide_render = False
            for dp in ('location', 'scale', 'rotation_euler', 'color', 'hide_render'):
                o.keyframe_insert(dp, frame=fr)
        ad = o.animation_data
        if ad and ad.action:
            for fc in fcurves(ad.action):
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT' if fc.data_path == 'hide_render' else 'LINEAR'

    def radius(self, age):
        return self.r1 + (self.r0 - self.r1) * math.exp(-age / self.grow) + self.spread * age


def fcurves(action):
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                out.extend(bag.fcurves)
    return out


def hemi(rnd, up=0.4):
    while True:
        v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        if 0.05 < v.length <= 1:
            v.normalize()
            v.z = abs(v.z) * (1 - up) + up
            return v.normalized()


def sphere_dir(rnd):
    while True:
        v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        if 0.05 < v.length <= 1:
            return v.normalized()


# ------------------------------------------------------------------------------- effects
# Every builder returns a dict of manifest fields; it creates puffs that run on frames
# [(1, t0), (2, t0 + 1/FPS), ...].

def frames_for(n, t_start=0.0):
    return [(i + 1, t_start + i / FPS) for i in range(n)]


def fx_ground_explosion(seed, n, scale=1.0, smoke_body=True):
    rnd = random.Random(seed)
    fm = puff_mat('fire', albedo=(0.45, 0.43, 0.41), dark=(0.05, 0.046, 0.043), dens=6.0, fire=24.0, noise_scale=1.7, erosion=1.5, edge=0.32)
    dm = puff_mat('dust', albedo=(0.55, 0.45, 0.34), dark=(0.2, 0.16, 0.12), dens=3.0, fire=0.0, erosion=1.3)
    fr = frames_for(n)
    s = scale
    # fireball: fast outward hemisphere, rolls up with buoyancy, cools to black smoke
    for i in range(26):
        d = hemi(rnd, up=0.25)
        sp = rnd.uniform(7, 13) * s
        Puff(fm, rnd.uniform(0, 0.06), (d.x * 0.2 * s, d.y * 0.2 * s, 0.25 * s), d * sp,
             r0=0.15 * s, r1=rnd.uniform(0.55, 0.9) * s, grow=0.12, heat=rnd.uniform(0.85, 1.0),
             cool=rnd.uniform(0.22, 0.42), dens=1.0, buoy=rnd.uniform(2.5, 4.0) * s, drag=rnd.uniform(5, 7),
             spin=None, evolve=1.1, rnd=rnd, fade=(1.2, 2.4), spread=0.3 * s).run(fr)
    # hot core column that punches up (mushroom stem)
    for i in range(7):
        Puff(fm, 0.02 + i * 0.03, (rnd.uniform(-.15, .15) * s, rnd.uniform(-.15, .15) * s, 0.3 * s),
             (rnd.uniform(-1, 1) * s, rnd.uniform(-1, 1) * s, rnd.uniform(9, 13) * s),
             r0=0.2 * s, r1=rnd.uniform(0.5, 0.75) * s, grow=0.18, heat=1.0, cool=rnd.uniform(0.3, 0.5),
             buoy=4.0 * s, drag=4.0, evolve=1.2, rnd=rnd, fade=(1.3, 2.4), spread=0.3 * s).run(fr)
    if smoke_body:
        # dark smoke that takes over as the fire dies, rising and spreading
        for i in range(12):
            d = hemi(rnd, up=0.6)
            Puff(fm, rnd.uniform(0.12, 0.35), (d.x * 0.6 * s, d.y * 0.6 * s, rnd.uniform(0.6, 1.4) * s), d * 3 * s,
                 r0=0.4 * s, r1=rnd.uniform(0.8, 1.15) * s, grow=0.5, heat=0.35, cool=0.12, soot0=0.55,
                 dens=0.8, buoy=2.2 * s, drag=2.5, evolve=0.7, rnd=rnd, fade=(0.9, 1.9), spread=0.35 * s).run(fr)
    # ground skirt of dust shooting sideways
    for i in range(12):
        a = rnd.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a), math.sin(a), 0.15))
        Puff(dm, rnd.uniform(0.0, 0.05), (0, 0, 0.15 * s), d * rnd.uniform(9, 14) * s,
             r0=0.15 * s, r1=rnd.uniform(0.45, 0.7) * s, grow=0.25, heat=0.0, cool=0, soot0=0.15,
             dens=0.9, buoy=0.25 * s, drag=5.5, evolve=0.8, rnd=rnd, fade=(0.5, 1.6)).run(fr)
    return dict(kind='explosion', loop=False)


def fx_air_explosion(seed, n):
    rnd = random.Random(seed)
    fm = puff_mat('fire', albedo=(0.45, 0.43, 0.41), dark=(0.05, 0.046, 0.043), dens=6.0, fire=24.0, noise_scale=1.7, erosion=1.5, edge=0.32)
    fr = frames_for(n)
    for i in range(30):
        d = sphere_dir(rnd)
        Puff(fm, rnd.uniform(0, 0.05), d * 0.15, d * rnd.uniform(8, 13),
             r0=0.15, r1=rnd.uniform(0.5, 0.8), grow=0.12, heat=rnd.uniform(0.85, 1.0),
             cool=rnd.uniform(0.2, 0.38), buoy=2.0, drag=rnd.uniform(5.5, 7.5), evolve=1.1, rnd=rnd,
             ground=False, fade=(0.9, 1.7), spread=0.3).run(fr)
    for i in range(8):
        d = sphere_dir(rnd)
        Puff(fm, rnd.uniform(0.1, 0.25), d * 0.6, d * 2.5, r0=0.4, r1=rnd.uniform(0.8, 1.05), grow=0.4,
             heat=0.3, cool=0.1, soot0=0.6, dens=0.7, buoy=1.2, drag=3, evolve=0.7, rnd=rnd,
             ground=False, fade=(0.7, 1.6)).run(fr)
    return dict(kind='explosion', loop=False)


def fx_small_hit(seed, n):
    rnd = random.Random(seed)
    fm = puff_mat('fire', albedo=(0.45, 0.43, 0.41), dark=(0.05, 0.046, 0.043), dens=6.0, fire=24.0, noise_scale=1.7, erosion=1.5, edge=0.32)
    dm = puff_mat('dust', albedo=(0.55, 0.45, 0.34), dark=(0.2, 0.16, 0.12), dens=3.0, fire=0.0, erosion=1.3)
    fr = frames_for(n)
    for i in range(10):
        d = hemi(rnd, up=0.35)
        Puff(fm, rnd.uniform(0, 0.03), d * 0.1, d * rnd.uniform(6, 9), r0=0.1, r1=rnd.uniform(0.35, 0.55),
             grow=0.08, heat=1.0, cool=rnd.uniform(0.1, 0.18), buoy=2.0, drag=8, evolve=1.3, rnd=rnd,
             fade=(0.5, 1.0)).run(fr)
    for i in range(9):
        d = hemi(rnd, up=0.55)
        Puff(dm, rnd.uniform(0, 0.06), d * 0.1, d * rnd.uniform(6, 10), r0=0.12, r1=rnd.uniform(0.4, 0.65),
             grow=0.2, heat=0, cool=0, soot0=0.3, dens=0.9, buoy=0.6, drag=5, evolve=0.8, rnd=rnd,
             fade=(0.3, 1.0)).run(fr)
    return dict(kind='explosion', loop=False)


def fx_smoke_plume(seed, n_loop, warm=3.0, rate=8):
    """Seamless rising smoke: emission schedule repeats every n_loop frames."""
    rnd = random.Random(seed)
    sm = puff_mat('smoke', albedo=(0.3, 0.29, 0.28), dark=(0.04, 0.037, 0.035), dens=4.0, fire=0.0, erosion=1.25)
    period = n_loop / FPS
    per = [dict(dx=rnd.uniform(-.25, .25), dy=rnd.uniform(-.25, .25), r1=rnd.uniform(0.9, 1.3),
                soot=rnd.uniform(0.25, 0.6), sp=Vector((rnd.uniform(-.6, .6), rnd.uniform(-.6, .6), rnd.uniform(-.6, .6))),
                vz=rnd.uniform(1.6, 2.2), rot=Euler((rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6))),
                rid=rnd.uniform(0, 1))
           for _ in range(rate)]
    life = 3.4
    t_first = -life
    k = 0
    fr = frames_for(n_loop, t_start=warm)
    t = t_first
    while t < warm + period:
        q = per[k % rate]
        # shift so that schedule repeats with period; t = base + k*period/rate
        p = Puff(sm, t, (q['dx'], q['dy'], 0.2), (0, 0, q['vz']), r0=0.25, r1=q['r1'], grow=1.4,
                 heat=0, cool=0, soot0=q['soot'], dens=1.0, buoy=0.0, drag=0.4, spin=q['sp'],
                 evolve=0.35, life=life, fade=(life * 0.45, life), wind=(0.5, 0, q['vz']))
        p.rot0 = q['rot']
        p.o.pass_index = 0
        p.run(fr)
        k += 1
        t = t_first + k * period / rate
    return dict(kind='smoke', loop=True)


def fx_fire_loop(seed, n_loop, warm=1.5, rate=16):
    rnd = random.Random(seed)
    fm = puff_mat('flame', albedo=(0.3, 0.28, 0.26), dark=(0.05, 0.045, 0.04), dens=3.0, fire=9.0,
                  noise_scale=2.0, erosion=1.4, edge=0.35)
    period = n_loop / FPS
    per = [dict(dx=rnd.uniform(-.45, .45), dy=rnd.uniform(-.3, .3), r1=rnd.uniform(0.22, 0.36),
                vz=rnd.uniform(2.2, 3.4), heat=rnd.uniform(0.75, 1.0), cool=rnd.uniform(0.18, 0.3),
                sp=Vector((rnd.uniform(-3, 3), rnd.uniform(-3, 3), rnd.uniform(-3, 3))),
                rot=Euler((rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6))))
           for _ in range(rate)]
    life = 0.9
    fr = frames_for(n_loop, t_start=warm)
    k = 0
    t = -life
    while t < warm + period:
        q = per[k % rate]
        p = Puff(fm, t, (q['dx'], q['dy'], 0.15), (q['dx'] * -0.5, 0, q['vz']), r0=q['r1'] * 1.2, r1=q['r1'] * 0.55,
                 grow=0.5, heat=q['heat'], cool=q['cool'], soot0=0.0, soot_rate=0.6, dens=0.6, buoy=1.5,
                 drag=1.0, spin=q['sp'], evolve=1.6, life=life, fade=(life * 0.5, life), ground=False,
                 wind=(0, 0, q['vz']))
        p.rot0 = q['rot']
        p.run(fr)
        k += 1
        t = -life + k * period / rate
    return dict(kind='fire', loop=True)


def fx_dust_burst(seed, n, ring=False):
    rnd = random.Random(seed)
    dm = puff_mat('dustlight', albedo=(0.62, 0.54, 0.44), dark=(0.3, 0.26, 0.21), dens=2.6, fire=0.0, erosion=1.3)
    fr = frames_for(n)
    cnt = 18 if ring else 14
    for i in range(cnt):
        if ring:
            a = 2 * math.pi * i / cnt + rnd.uniform(-.1, .1)
            d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.0, 0.12)))
            sp = rnd.uniform(9, 12)
            r1 = rnd.uniform(0.4, 0.6)
        else:
            d = hemi(rnd, up=0.45)
            sp = rnd.uniform(5, 9)
            r1 = rnd.uniform(0.45, 0.75)
        Puff(dm, rnd.uniform(0, 0.05), d * 0.1, d * sp, r0=0.15, r1=r1, grow=0.3, heat=0, cool=0,
             soot0=rnd.uniform(0, 0.35), dens=0.9, buoy=0.35, drag=4.5, evolve=0.7, rnd=rnd,
             fade=(0.35, 1.3)).run(fr)
    return dict(kind='dust', loop=False)


# --- emissive (non-volume) effects: muzzle flashes, impact flash, sparks -----------------
def emit_mat(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*col, 1)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


def glow_vol_mat(name, core, edge, strength, noise=2.5):
    """Emission-only volume: hot core colour fading to edge colour, noisy soft edge."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    Lk = nt.links.new
    out = N('ShaderNodeOutputMaterial')
    tc = N('ShaderNodeTexCoord')
    ln = N('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    Lk(tc.outputs['Object'], ln.inputs[0])
    oi = N('ShaderNodeObjectInfo')
    nz = N('ShaderNodeTexNoise')
    nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = noise
    nz.inputs['Detail'].default_value = 5
    Lk(tc.outputs['Object'], nz.inputs['Vector'])
    wv = N('ShaderNodeMath')
    wv.operation = 'MULTIPLY'
    Lk(oi.outputs['Random'], wv.inputs[0])
    wv.inputs[1].default_value = 50
    Lk(wv.outputs[0], nz.inputs['W'])
    a1 = N('ShaderNodeMath')
    a1.operation = 'SUBTRACT'
    a1.inputs[0].default_value = 1.0
    Lk(ln.outputs['Value'], a1.inputs[1])
    a2 = N('ShaderNodeMath')
    a2.operation = 'MULTIPLY_ADD'
    Lk(nz.outputs['Fac'], a2.inputs[0])
    a2.inputs[1].default_value = 0.9
    a2.inputs[2].default_value = -0.45
    a3 = N('ShaderNodeMath')
    a3.operation = 'ADD'
    a3.use_clamp = True
    Lk(a1.outputs[0], a3.inputs[0])
    Lk(a2.outputs[0], a3.inputs[1])
    cr = N('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.0
    cr.color_ramp.elements[0].color = (0, 0, 0, 1)
    e = cr.color_ramp.elements.new(0.3)
    e.color = (*edge, 1)
    cr.color_ramp.elements[1].position = 0.75
    cr.color_ramp.elements[1].color = (*core, 1)
    Lk(a3.outputs[0], cr.inputs['Fac'])
    em = N('ShaderNodeEmission')
    Lk(cr.outputs['Color'], em.inputs['Color'])
    st = N('ShaderNodeMath')
    st.operation = 'MULTIPLY'
    Lk(oi.outputs['Alpha'], st.inputs[0])
    st.inputs[1].default_value = strength
    Lk(st.outputs[0], em.inputs['Strength'])
    pv = N('ShaderNodeVolumePrincipled')  # noqa  (keep for parity)
    nt.nodes.remove(pv)
    vol = N('ShaderNodeEmission')
    Lk(cr.outputs['Color'], vol.inputs['Color'])
    Lk(st.outputs[0], vol.inputs['Strength'])
    Lk(vol.outputs[0], out.inputs['Volume'])
    nt.nodes.remove(em)
    return m


def blob(mat, loc, scale, rot=(0, 0, 0), alpha=1.0):
    o = puff_obj(mat)
    o.location = loc
    o.scale = scale
    o.rotation_euler = rot
    o.color = (1, 1, 1, alpha)
    return o


def key_all(objs, fr):
    for o in objs:
        for dp in ('location', 'scale', 'rotation_euler', 'color', 'hide_render'):
            o.keyframe_insert(dp, frame=fr)


def fx_muzzle_side(seed, n, core, edge, strength=5.0, length=1.0):
    """Side-view flash pointing +X from the origin: a few elongated hot lobes + side petals.
    Each frame is re-drawn (flashes don't move, they flicker)."""
    rnd = random.Random(seed)
    m = glow_vol_mat('Flash', core, edge, strength)
    objs = [puff_obj(m) for _ in range(7)]
    for f in range(1, n + 1):
        k = [1.0, 0.75, 0.4, 0.2][min(f - 1, 3)]
        L = length * [0.85, 1.0, 0.75, 0.5][min(f - 1, 3)]
        lobes = [  # (x, y, z, sx, sy, sz)
            (L * 0.55, 0, 0, L * 0.55, 0.16 * L, 0.16 * L),
            (L * 0.95, 0, 0, L * 0.3, 0.11 * L, 0.11 * L),
            (L * 0.18, 0, 0, 0.22 * L, 0.24 * L, 0.24 * L),
        ]
        for s_ in (-1, 1):  # side petals angled ~60 deg
            a = math.radians(rnd.uniform(50, 70)) * s_
            lobes.append((0.2 * L, 0, math.sin(a) * 0.25 * L, 0.3 * L, 0.08 * L, 0.08 * L, a))
        lobes.append((0.32 * L, 0, 0, 0.28 * L, 0.2 * L, 0.2 * L))
        lobes.append((L * 1.25, 0, rnd.uniform(-.05, .05) * L, 0.18 * L, 0.07 * L, 0.07 * L))
        for o, lb in zip(objs, lobes):
            o.location = (lb[0], lb[1], lb[2])
            o.scale = (lb[3] * rnd.uniform(0.85, 1.15), lb[4], lb[5] * rnd.uniform(0.85, 1.15))
            o.rotation_euler = (rnd.uniform(0, 6), -(lb[6] if len(lb) > 6 else 0), 0)
            o.color = (1, 1, 1, k * rnd.uniform(0.85, 1.0))
        key_all(objs, f)
    return dict(kind='flash', loop=False)


def fx_flash_front(seed, n, core, edge, strength=5.0):
    """Radial star flash (seen down the barrel / impact flash)."""
    rnd = random.Random(seed)
    m = glow_vol_mat('FlashF', core, edge, strength)
    nb = 7
    objs = [puff_obj(m) for _ in range(nb + 1)]
    for f in range(1, n + 1):
        k = [1.0, 0.85, 0.55, 0.3, 0.15, 0.07][min(f - 1, 5)]
        R = [0.8, 1.0, 1.05, 1.0, 0.95, 0.9][min(f - 1, 5)]
        objs[0].location = (0, 0, 0)
        objs[0].scale = (0.35 * R,) * 3
        objs[0].color = (1, 1, 1, k)
        for i in range(nb):
            a = 2 * math.pi * i / nb + rnd.uniform(-.3, .3)
            L = rnd.uniform(0.35, 0.6) * R
            o = objs[i + 1]
            o.location = (math.cos(a) * L * 0.8, 0, math.sin(a) * L * 0.8)
            o.scale = (L, 0.07, 0.07)
            o.rotation_euler = (0, -a, 0)
            o.color = (1, 1, 1, k * rnd.uniform(0.6, 1.0))
        key_all(objs, f)
    return dict(kind='flash', loop=False)


def fx_sparks(seed, n, col=(1.0, 0.85, 0.6), count=40, strength=4.0, up=0.2):
    """Bright streaks flying out ballistically: emissive thin capsules aligned with velocity,
    stretched by speed (motion streaks)."""
    rnd = random.Random(seed)
    m = emit_mat('Spark', col, strength)
    me = bpy.data.meshes.new('SparkMesh')
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    for i in range(count):
        o = bpy.data.objects.new('Spark', me)
        bpy.context.scene.collection.objects.link(o)
        me.materials.append(m) if not me.materials else None
        d = sphere_dir(rnd)
        d.z = d.z * (1 - up) + up
        v = d.normalized() * rnd.uniform(4, 11)
        life = rnd.uniform(0.25, 0.6)
        p = Vector((0, 0, 0))
        o.rotation_mode = 'QUATERNION'
        th = rnd.uniform(0.012, 0.025)
        for f in range(1, n + 1):
            t = (f - 1) / FPS
            if t > life:
                o.scale = (0, 0, 0)
                o.keyframe_insert('scale', frame=f)
                break
            vt = v + Vector((0, 0, -9.8 * t))
            vt *= math.exp(-1.2 * t)
            pos = v * (1 - math.exp(-1.2 * t)) / 1.2 + Vector((0, 0, -4.9 * t * t))
            fade = 1 - t / life
            o.location = pos
            o.rotation_quaternion = vt.to_track_quat('X', 'Z')
            ln = max(0.04, vt.length / FPS * 0.9)
            o.scale = (ln, th * (0.4 + fade), th * (0.4 + fade))
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('rotation_quaternion', frame=f)
            o.keyframe_insert('scale', frame=f)
            o.location = pos  # noqa
    return dict(kind='sparks', loop=False)


# ------------------------------------------------------------------------------- library
# name: (builder, kwargs, frames, res, extent, origin(u,v), samples, glow_alpha, notes)
LIB = {
    'explo_ground_a': (fx_ground_explosion, dict(seed=11), 48, (384, 384), 7.0, (0.5, 0.08), 20, 1.3,
                       'ground blast: fireball rolling up into dark smoke + dust skirt; size 1 ~ 4 m fireball'),
    'explo_ground_b': (fx_ground_explosion, dict(seed=23), 48, (384, 384), 7.0, (0.5, 0.08), 20, 1.3,
                       'variant of explo_ground_a'),
    'explo_air': (fx_air_explosion, dict(seed=5), 40, (320, 320), 8.0, (0.5, 0.45), 20, 1.3,
                  'air burst: spherical fireball into dark smoke, no ground contact'),
    'explo_small': (fx_small_hit, dict(seed=7), 28, (256, 256), 4.5, (0.5, 0.1), 20, 1.3,
                    'small hit: quick fire pop + dirt'),
    'smoke_plume': (fx_smoke_plume, dict(seed=3), 48, (256, 384), 6.0, (0.42, 0.05), 16, 1.0,
                    'seamless loop: dark smoke column rising (with drift to +X)'),
    'fire_loop': (fx_fire_loop, dict(seed=9), 32, (256, 256), 2.6, (0.5, 0.08), 20, 1.6,
                  'seamless loop: burning wreck flames'),
    'dust_burst': (fx_dust_burst, dict(seed=13), 32, (320, 256), 7.0, (0.5, 0.08), 16, 1.0,
                   'light dust burst (tan; can be tinted by multiply)'),
    'dust_ring': (fx_dust_burst, dict(seed=17, ring=True), 32, (384, 192), 9.0, (0.5, 0.1), 16, 1.0,
                  'dust ring pushed outward along the ground (landing / shockwave)'),
    'muzzle_a': (fx_muzzle_side, dict(seed=1, core=(1.0, 0.8, 0.45), edge=(1.0, 0.3, 0.03)), 4, (256, 128), 2.6,
                 (0.06, 0.5), 16, 1.6, 'Terran muzzle flash side view, points +X, 4 frames'),
    'muzzle_b': (fx_muzzle_side, dict(seed=2, core=(1.0, 0.75, 0.4), edge=(1.0, 0.25, 0.02), length=0.85), 4,
                 (256, 128), 2.6, (0.06, 0.5), 16, 1.6, 'variant'),
    'muzzle_c': (fx_muzzle_side, dict(seed=4, core=(1.0, 0.82, 0.5), edge=(1.0, 0.35, 0.05), length=1.1), 4,
                 (256, 128), 2.6, (0.06, 0.5), 16, 1.6, 'variant'),
    'muzzle_blue': (fx_muzzle_side, dict(seed=6, core=(0.75, 0.9, 1.0), edge=(0.1, 0.4, 1.0), length=0.9), 4,
                    (256, 128), 2.6, (0.06, 0.5), 16, 1.6, 'laser muzzle flash, blue'),
    'flash_star': (fx_flash_front, dict(seed=8, core=(1.0, 0.8, 0.5), edge=(1.0, 0.32, 0.04)), 6, (192, 192),
                   2.6, (0.5, 0.5), 16, 1.6, 'radial star flash, orange (muzzle seen head-on)'),
    'impact_flash': (fx_flash_front, dict(seed=10, core=(1.0, 0.97, 0.92), edge=(0.75, 0.72, 0.68)), 6, (192, 192),
                     2.6, (0.5, 0.5), 16, 1.6, 'near-neutral white-hot star flash: tint at playback'),
    'sparks': (fx_sparks, dict(seed=12, col=(1.0, 0.95, 0.85)), 16, (256, 256), 6.0, (0.5, 0.35), 16, 1.6,
               'near-neutral spark streak burst: tint at playback'),
}


def bake(name, test=False):
    fn, kw, n, res, extent, origin, spp, glow, notes = LIB[name]
    if test:
        res = (res[0] // 2, res[1] // 2)
        spp = max(8, spp // 2)
    _MAT.clear()
    _ICO.clear()
    sc = reset(res, extent, origin, samples=spp)
    t0 = time.time()
    if fn in (fx_smoke_plume, fx_fire_loop):
        info = fn(kw['seed'], n)
    else:
        info = fn(n=n, **kw)
    sc.frame_start, sc.frame_end = 1, n
    out = os.path.join(ROOT if not test else os.path.join(ROOT, '_test'), name)
    os.makedirs(out, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    frames = range(1, n + 1)
    if test:
        frames = sorted(set([1, 3, 6, 12, n // 2, n]) & set(range(1, n + 1)))
    for f in frames:
        sc.frame_set(f)
        exr = os.path.join(TMP, f'{name}_{f:04d}.exr')
        sc.render.filepath = exr
        bpy.ops.render.render(write_still=True)
        exr_to_png(exr, os.path.join(out, f'{f:04d}.png'), glow_alpha=glow)
        os.remove(exr)
    dt = time.time() - t0
    entry = dict(frames=n, fps=FPS, size=list(res), extent=extent, origin=list(origin),
                 loop=info.get('loop', False), kind=info.get('kind'), notes=notes,
                 bake_seconds=round(dt, 1))
    print(f'BAKED {name}: {len(frames)} frames in {dt:.0f}s ({dt / len(frames):.1f}s/frame)', flush=True)
    if not test:
        mf = os.path.join(ROOT, 'manifest.json')
        data = json.load(open(mf)) if os.path.exists(mf) else {}
        data[name] = entry
        json.dump(data, open(mf, 'w'), indent=1, sort_keys=True)
    return entry


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    ap.add_argument('--test', action='store_true')
    args, _ = ap.parse_known_args(sys.argv[1:])
    names = args.only.split(',') if args.only else list(LIB)
    for nm in names:
        bake(nm, test=args.test)
