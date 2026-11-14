"""The Shard's weapons, cinematic build v2 (2026-11-14, David: "way more detail in the weapon effect").

Static, seed-fixed builders (animation is keyed by the callers):
  lightning(p0, p1, seed)        forked violet bolt: white-hot core, violet sleeve, soft halo, branches,
                                 impact flash, scorched glowing ground and spark spray
  charge(tip, r)                 energy gathering at the Shard's tip: a blazing orb, converging streaks, rings
  beam(base, top, r, seed)       the column: blinding core, violet sleeve, halo, three spiral energy strands,
                                 shock rings along it, heat-shimmer sheath, root flare
  crust(centre, size, seed)      crystal spires bursting out over a vehicle
"""
import math
import random

import bpy
from mathutils import Vector

import barrage_pieces as BP
import common as C
import new_pieces as NP
import shard_hd

VIO = (0.5, 0.18, 1.0)
HOT = (0.92, 0.85, 1.0)


def _link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def _emit(name, col, s):
    return bpy.data.materials.get(name) or C.emit_mat(name, col, s)


def _halo(name, col, k, p=2.5):
    """Soft glow: bright where the surface faces the camera, fading to nothing at the silhouette."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, n = BP._new_mat(name)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), p)   # Facing is 0 head-on
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', g, k))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


def _plasma(name, col, k, scale=4.0):
    """Churning plasma surface: bright filaments over a dimmer body."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    nz = n.node('ShaderNodeTexNoise', Scale=scale, Detail=10.0, Roughness=0.65)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 1.5))
    rid = n.math('POWER', n.math('SUBTRACT', 1.0, n.math('ABSOLUTE', n.math('SUBTRACT', nz.outputs['Fac'], 0.5))), 18.0)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    body = n.math('ADD', n.math('MULTIPLY', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 0.25), n.math('MULTIPLY', rid, 1.0))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', body, k))
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], em.outputs[0])
    return m


def _tube_path(name, pts, r, mat, sides=6):
    """A tube through pts with radius list r (or a float), as a mesh (no forge zones needed)."""
    import bmesh
    rs = r if isinstance(r, (list, tuple)) else [r] * len(pts)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        p = Vector(p)
        d = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        a = d.orthogonal().normalized()
        b = d.cross(a)
        rings.append([bm.verts.new(p + (a * math.cos(t) + b * math.sin(t)) * rs[i])
                      for t in (2 * math.pi * k / sides for k in range(sides))])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = _link(bpy.data.objects.new(name, me))
    o.data.materials.append(mat)
    o.visible_shadow = False
    return o


def _jag(p0, p1, rnd, depth, rough):
    """Midpoint-displaced path p0 -> p1."""
    pts = [Vector(p0), Vector(p1)]
    for _ in range(depth):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            m = (a + b) / 2
            L = (b - a).length
            d = (b - a).normalized()
            perp = d.orthogonal().normalized()
            perp.rotate(__import__('mathutils').Quaternion(d, rnd.uniform(0, 2 * math.pi)))
            out += [m + perp * L * rough * rnd.uniform(-1, 1), b]
        pts = out
    return pts


def lightning(p0, p1, seed=1, width=0.6, name='ShardBolt'):
    """Returns the list of objects (parent them / key their visibility)."""
    rnd = random.Random(seed)
    objs = []
    core_m = _emit('BoltCoreM', HOT, 25.0)
    sleeve_m = _halo('BoltSleeveM', (0.62, 0.35, 1.0), 6.0, 1.5)
    halo_m = _halo('BoltHaloM', VIO, 0.6, 3.0)
    main = _jag(p0, p1, rnd, 7, 0.2)
    n = len(main)
    taper = [width * (0.55 + 0.45 * (1 - i / (n - 1))) for i in range(n)]
    objs.append(_tube_path(name + 'Core', main, [t * 0.16 for t in taper], core_m))
    objs.append(_tube_path(name + 'Sleeve', main, [t * 0.6 for t in taper], sleeve_m, sides=8))
    objs.append(_tube_path(name + 'Halo', main, [t * 5.0 for t in taper], halo_m, sides=10))
    # branches: forks off the main channel, each with its own small forks
    for b in range(14):
        i = rnd.randint(n // 8, n - n // 5)
        a = main[i]
        d = (main[min(i + 3, n - 1)] - a).normalized()
        side = d.orthogonal().normalized()
        side.rotate(__import__('mathutils').Quaternion(d, rnd.uniform(0, 2 * math.pi)))
        L = (Vector(p1) - Vector(p0)).length * rnd.uniform(0.08, 0.25)
        e = a + (d * 0.6 + side * rnd.uniform(0.5, 1.0)).normalized() * L
        br = _jag(a, e, rnd, 4, 0.25)
        w = taper[i] * rnd.uniform(0.25, 0.45)
        objs.append(_tube_path(f'{name}Br{b}', br, [w * 0.7 * (1 - k / len(br)) + 0.02 for k in range(len(br))], sleeve_m, sides=6))
        objs.append(_tube_path(f'{name}BrC{b}', br, [w * 0.15 * (1 - k / len(br)) + 0.008 for k in range(len(br))], core_m))
        for s in range(3):
            j = rnd.randint(1, len(br) - 2)
            e2 = br[j] + (br[j] - a).normalized().lerp(side, 0.6).normalized() * L * 0.35
            tw = _jag(br[j], e2, rnd, 3, 0.3)
            objs.append(_tube_path(f'{name}Tw{b}_{s}', tw, [w * 0.4 * (1 - k / len(tw)) + 0.01 for k in range(len(tw))],
                                   sleeve_m))
    # impact: flash sphere, scorched glowing ground, spark spray
    flash = C.uv_sphere(name + 'Flash', 1.0, seg=(16, 8), mat=_halo('BoltFlashM', (0.65, 0.45, 1.0), 1.4, 4.0),
                        scale=(width * 4,) * 3)
    flash.location = p1
    objs.append(flash)
    sc_m, n_ = BP._new_mat(name + 'ScorchM')
    tc = n_.node('ShaderNodeTexCoord')
    nz = n_.node('ShaderNodeTexNoise', Scale=2.5, Detail=8.0, Roughness=0.7)
    n_.set(nz.inputs['Vector'], tc.outputs['Object'])
    ln = n_.node('ShaderNodeVectorMath', operation='LENGTH')
    n_.set(ln.inputs[0], tc.outputs['Object'])
    fall = n_.maprange(ln.outputs['Value'], 0.2, 1.0, 1.0, 0.0)
    cracks = n_.math('POWER', n_.maprange(nz.outputs['Fac'], 0.45, 0.62, 0.0, 1.0), 3.0)
    BP._add_out(n_, n_.math('MULTIPLY', n_.math('MULTIPLY', fall, cracks), 6.0), VIO)
    sc = C.uv_sphere(name + 'Scorch', 1.0, seg=(24, 6), mat=sc_m, scale=(width * 14, width * 14, 0.05))
    sc.location = Vector(p1) + Vector((0, 0, 0.08))
    objs.append(sc)
    sp_m = _emit('BoltSparkM', (0.8, 0.6, 1.0), 12.0)
    for k in range(40):
        d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), abs(rnd.gauss(0.8, 0.6)))).normalized()
        L = width * rnd.uniform(2, 9)
        s = C.uv_sphere(f'{name}Sp{k}', 1.0, seg=(6, 4), mat=sp_m, scale=(L / 2, 0.025, 0.025))
        s.rotation_mode = 'QUATERNION'
        s.rotation_quaternion = d.to_track_quat('X', 'Z')
        s.location = Vector(p1) + d * (L / 2 + width * rnd.uniform(0.5, 6))
        s.visible_shadow = False
        objs.append(s)
    L = _link(bpy.data.objects.new(name + 'Light', bpy.data.lights.new(name + 'Light', 'POINT')))
    L.location = Vector(p1) + Vector((0, 0, width * 4))
    L.data.color = VIO
    L.data.energy = 6e3 * width
    L.data.shadow_soft_size = width * 3
    objs.append(L)
    return objs


def charge(tip, r=3.0, seed=2, name='ShardCharge'):
    """Energy gathering at the tip before it fires."""
    rnd = random.Random(seed)
    objs = []
    orb = C.uv_sphere(name + 'Orb', r, seg=(32, 16), mat=_plasma('ChargeOrbM', (0.75, 0.55, 1.0), 5.0))
    orb.location = tip
    objs.append(orb)
    for k, (rr, kk) in enumerate([(1.5, 1.2), (3.0, 0.5), (6.0, 0.2)]):
        h = C.uv_sphere(f'{name}Halo{k}', r * rr, seg=(32, 16), mat=_halo(f'ChargeHalo{k}M', VIO, kk, 2.0))
        h.location = tip
        objs.append(h)
    st_m = _emit('ChargeStreakM', (0.7, 0.5, 1.0), 4.0)
    st_g = _halo('ChargeStreakGlowM', (0.6, 0.35, 1.0), 2.0, 1.5)
    for k in range(48):   # filaments of energy spiralling in to the orb
        d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        ax = d.orthogonal().normalized()
        R0, R1 = r * rnd.uniform(4, 11), r * rnd.uniform(1.2, 1.8)
        turn = rnd.uniform(0.6, 1.4) * rnd.choice((-1, 1))
        pts = []
        for i in range(13):
            f = i / 12
            v = d.copy()
            v.rotate(__import__('mathutils').Quaternion(ax, turn * f))
            pts.append(Vector(tip) + v * (R0 + (R1 - R0) * f ** 0.7))
        pts = sum((_jag(x, y, rnd, 1, 0.1)[:-1] for x, y in zip(pts, pts[1:])), []) + [pts[-1]]
        n = len(pts)
        objs.append(_tube_path(f'{name}St{k}', pts, [0.004 + 0.035 * r / 3 * (i / (n - 1)) ** 2 for i in range(n)],
                               st_m, sides=4))
        objs.append(_tube_path(f'{name}StG{k}', pts, [0.02 + 0.2 * r / 3 * (i / (n - 1)) ** 2 for i in range(n)],
                               st_g, sides=6))
    for k in range(3):    # tilted spinning rings round it
        ring = []
        tilt = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 1)).normalized()
        a = tilt.orthogonal().normalized()
        b = tilt.cross(a)
        R = r * (2.0 + k * 0.7)
        for i in range(65):
            t = 2 * math.pi * i / 64
            ring.append(Vector(tip) + (a * math.cos(t) + b * math.sin(t)) * R)
        objs.append(_tube_path(f'{name}Ring{k}', ring, 0.02 * r, st_m, sides=4))
    for k in range(10):   # arcs crawling over the orb's surface
        a = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        b = (a + Vector((rnd.gauss(0, 0.8), rnd.gauss(0, 0.8), rnd.gauss(0, 0.8)))).normalized()
        pts = [Vector(tip) + (a.lerp(b, i / 8)).normalized() * r * 1.05 for i in range(9)]
        pts = sum((_jag(x, y, rnd, 2, 0.15)[:-1] for x, y in zip(pts, pts[1:])), []) + [pts[-1]]
        objs.append(_tube_path(f'{name}Arc{k}', pts, 0.03 * r, _emit('BoltCoreM', HOT, 25.0), sides=4))
    return objs


def beam(base, top, r=4.0, seed=3, name='ShardBeam'):
    rnd = random.Random(seed)
    objs = []
    base, top = Vector(base), Vector(top)
    d = (top - base).normalized()
    L = (top - base).length
    q = d.to_track_quat('Z', 'Y')

    def cyl(nm, rad, mat, seg=24):
        o = C.uv_sphere(nm, 1.0, seg=(seg, 8), mat=mat, scale=(rad, rad, L / 2))
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = q
        o.location = (base + top) / 2
        o.visible_shadow = False
        objs.append(o)
        return o
    cyl(name + 'Core', r * 0.28, _emit('BeamCoreM', HOT, 30.0))
    # violet sleeve whose brightness churns as energy pours up it
    sm, n_ = BP._new_mat(name + 'SleeveM')
    tc = n_.node('ShaderNodeTexCoord')
    t = BP.time_value(sm, 'time', 1.0)
    sep = n_.node('ShaderNodeSeparateXYZ')
    n_.set(sep.inputs[0], tc.outputs['Object'])
    nz = n_.node('ShaderNodeTexNoise', Scale=3.0, Detail=6.0)
    nz.noise_dimensions = '4D'
    n_.set(nz.inputs['Vector'], tc.outputs['Object'])
    n_.set(nz.inputs['W'], n_.math('SUBTRACT', n_.math('MULTIPLY', sep.outputs[2], 2.0), n_.math('MULTIPLY', t, 6.0)))
    lw = n_.node('ShaderNodeLayerWeight', Blend=0.4)
    edge = n_.math('POWER', n_.math('SUBTRACT', 1.0, lw.outputs['Facing']), 1.5)
    k = n_.math('MULTIPLY', n_.maprange(nz.outputs['Fac'], 0.3, 0.75, 0.5, 2.5), n_.math('SUBTRACT', 1.0, n_.math('MULTIPLY', edge, 0.8)))
    em = n_.node('ShaderNodeEmission', Color=(*VIO, 1))
    n_.set(em.inputs['Strength'], n_.math('MULTIPLY', k, 3.0))
    tr = n_.node('ShaderNodeBsdfTransparent')
    add = n_.node('ShaderNodeAddShader')
    n_.set(add.inputs[0], tr.outputs[0])
    n_.set(add.inputs[1], em.outputs[0])
    out = n_.node('ShaderNodeOutputMaterial')
    n_.set(out.inputs['Surface'], add.outputs[0])
    cyl(name + 'Sleeve', r * 0.75, sm)
    cyl(name + 'Halo', r * 3.0, _halo('BeamHaloM', VIO, 1.2, 2.0))
    cyl(name + 'Outer', r * 7.0, _halo('BeamOuterM', VIO, 0.35, 3.0))
    # three spiral strands climbing round it
    st_m = _emit('BeamStrandM', (0.8, 0.6, 1.0), 10.0)
    for s in range(3):
        pts = []
        a0 = 2 * math.pi * s / 3
        for i in range(int(L / 2) + 1):
            z = i * 2.0
            a = a0 + z / (r * 1.8)
            rr = r * (1.05 + 0.15 * math.sin(z * 0.11 + s))
            pts.append(base + q @ Vector((math.cos(a) * rr, math.sin(a) * rr, z)))
        objs.append(_tube_path(f'{name}Strand{s}', pts, r * 0.07, st_m, sides=5))
    # shock rings at intervals up the column
    for i in range(6):
        z = L * (0.08 + 0.16 * i) + rnd.uniform(-2, 2)
        R = r * rnd.uniform(1.6, 2.6)
        ring = [base + q @ Vector((math.cos(2 * math.pi * k / 48) * R, math.sin(2 * math.pi * k / 48) * R, z))
                for k in range(49)]
        objs.append(_tube_path(f'{name}Shock{i}', ring, r * 0.06, _halo('BeamShockM', (0.8, 0.65, 1.0), 6.0, 1.0), sides=4))
    # root flare where it leaves the tip
    fl = C.uv_sphere(name + 'Root', r * 1.6, seg=(32, 16), mat=_halo('BeamRootM', (0.7, 0.5, 1.0), 1.5, 3.0))
    fl.location = base
    objs.append(fl)
    return objs


def crust(centre, size, seed=4, name='Crust', mat=None):
    """Crystal spires bursting outward over a vehicle-sized area (size = vehicle half-length)."""
    import bmesh
    rnd = random.Random(seed)
    bm = bmesh.new()
    c = Vector(centre)
    for k in range(70):
        p = c + Vector((rnd.uniform(-1, 1) * size, rnd.uniform(-0.6, 0.6) * size, rnd.uniform(0, 0.7) * size))
        d = (p - c + Vector((0, 0, size * 0.6))).normalized()
        d = (d + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 0.4)))).normalized()
        h = size * rnd.uniform(0.15, 0.7)
        shard_hd._spire(bm, p, d, h, h * rnd.uniform(0.1, 0.17), rnd, broken=rnd.random() < 0.25)
    o = shard_hd._obj(name, bm)
    o.data.materials.append(mat or shard_hd.glass_mat(name + 'M'))
    return o
