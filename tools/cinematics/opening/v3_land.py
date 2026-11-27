"""Scene 'land' (v4 cut, after the drop): the landing, seen from the ground. David 2026-11-27: "a scene of
nothingness on ground, shaking and dirt popping up, then have tank treads roll past to get blown up by an
electric missile", with consistent close-up detail.

 0.0- 2.5  stillness: empty valley floor at a pebble's height, dust drifting; far off, the first pods
           streak down behind the hills and flash on impact.
 2.5- 5.0  the rumble builds: more impacts, the camera shakes harder, pebbles hop, dirt pops up out of the
           ground, a violet vein flickers in the cracks (the planet itself stirring: it foreshadows the Shard).
 5.0- 6.9  a Terran Lancer's treads roll past, filling the frame: link by link, road wheels turning, dirt
           thrown off the track, a dust wake behind.
 6.9       a gold Arcadian missile, crackling with lightning, streaks in from the right and hits it: gold
           blast, arcs crawl over the hull, the tank bucks, its turret jumps, it grinds to a halt.
 7.0-10.0  the camera rises and backs off: the wreck burns and arcs, smoke climbs, and behind it the next
           Terran wave rolls on toward gold flashes in the east. Cut to the ground clash.

Own clock, frame 1 = first frame. Close-up hero running gear (links, wheels) replaces the Lancer's
phone-level belt for this shot only (art rules: a close-up version only where the camera gets very close).
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector, Quaternion, noise

import v3base as V
from v3base import fr
import space as SP
import common as C
import ground as GR
import new_pieces as NP
from squid import bake, ramp

FPS = 24
GOLD = (1.0, 0.72, 0.28)
VIOLET = GR.VIOLET

X0, Y0 = -260.0, -235.0         # camera spot in the valley (Terran half, on the way to the front)
TANK_DY = 4.6                   # tank centre line this far in front of the camera (treads ~2.3 m away)
F_ENTER = fr(4.9)               # tank front enters the left of frame
F_HIT = fr(6.9)
SPEED = 6.0                     # m/s before the hit


def zg(x, y):
    return GR.height(x, y) + detail(x, y)


def detail(x, y):
    """Close ground relief: ruts, lumps and grit on top of the valley's broad shape."""
    v = Vector((x, y, 0.0))
    h = 0.16 * noise.noise(v * 0.35 + Vector((0, 0, 3.1)))
    h += 0.06 * noise.noise(v * 1.3 + Vector((0, 0, 7.7)))
    h += 0.018 * noise.noise(v * 5.0 + Vector((0, 0, 1.3)))
    d = math.hypot(x - X0, y - Y0)
    return h * max(0.15, min(1.0, 1.6 - d / 60.0))


def axis(n_side, step0, grow, back=None):
    """Grid coordinates: fine near the camera, growing geometrically away from it."""
    out, s, st = [0.0], 0.0, step0
    for _ in range(n_side):
        s += st
        st *= grow
        out.append(s)
    neg = [-v for v in reversed(out[1:(back or n_side) + 1])]
    return neg + out


# ================================================================== materials
def ground_mat():
    """The valley's palette (ground.ground_mat) with close-range grit, pebbly voronoi and a violet vein
    network whose strength is keyed by the value node 'vein'."""
    m, n = SP.BP._new_mat('LandGround')
    out = n.node('ShaderNodeOutputMaterial')
    b = n.node('ShaderNodeBsdfPrincipled', Roughness=0.95)
    tc = n.node('ShaderNodeTexCoord')
    big = n.node('ShaderNodeTexNoise', Scale=0.012, Detail=10.0)
    n.set(big.inputs['Vector'], tc.outputs['Object'])
    mid = n.node('ShaderNodeTexNoise', Scale=0.45, Detail=6.0)
    n.set(mid.inputs['Vector'], tc.outputs['Object'])
    rp = n.node('ShaderNodeValToRGB')
    n.set(rp.inputs[0], n.math('MULTIPLY_ADD', big.outputs['Fac'], 0.6, n.math('MULTIPLY', mid.outputs['Fac'], 0.4)))
    rp.color_ramp.elements[0].color = (0.15, 0.11, 0.11, 1)
    rp.color_ramp.elements[1].color = (0.5, 0.39, 0.36, 1)
    grit = n.node('ShaderNodeTexVoronoi', Scale=9.0)
    n.set(grit.inputs['Vector'], tc.outputs['Object'])
    gv = n.maprange(grit.outputs['Distance'], 0.0, 0.5, 0.75, 1.1)
    mixc = n.node('ShaderNodeMix')
    mixc.data_type = 'RGBA'
    mixc.blend_type = 'MULTIPLY'
    mixc.inputs[0].default_value = 1.0
    n.set(mixc.inputs[6], rp.outputs[0])
    cm = n.node('ShaderNodeCombineXYZ')
    n.set(cm.inputs[0], gv)
    n.set(cm.inputs[1], gv)
    n.set(cm.inputs[2], gv)
    n.set(mixc.inputs[7], cm.outputs[0])
    n.set(b.inputs['Base Color'], mixc.outputs[2])
    f1 = n.node('ShaderNodeTexNoise', Scale=3.0, Detail=8.0)
    n.set(f1.inputs['Vector'], tc.outputs['Object'])
    f2 = n.node('ShaderNodeTexNoise', Scale=22.0, Detail=4.0)
    n.set(f2.inputs['Vector'], tc.outputs['Object'])
    hgt = n.math('ADD', n.math('MULTIPLY', f1.outputs['Fac'], 1.0),
                 n.math('ADD', n.math('MULTIPLY', f2.outputs['Fac'], 0.35), n.math('MULTIPLY', grit.outputs['Distance'], 0.5)))
    bump = n.node('ShaderNodeBump', Strength=0.5, Distance=0.04)
    n.set(bump.inputs['Height'], hgt)
    n.set(b.inputs['Normal'], bump.outputs[0])
    # violet veins in the cracks
    vor = n.node('ShaderNodeTexVoronoi', Scale=0.35)
    vor.feature = 'DISTANCE_TO_EDGE'
    warp = n.node('ShaderNodeTexNoise', Scale=0.2, Detail=4.0)
    n.set(warp.inputs['Vector'], tc.outputs['Object'])
    vm = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    vm.inputs[1].default_value = (2.5, 2.5, 2.5)
    n.set(vm.inputs[0], warp.outputs['Color'])
    n.set(vm.inputs[2], tc.outputs['Object'])
    n.set(vor.inputs['Vector'], vm.outputs[0])
    vein = n.maprange(vor.outputs['Distance'], 0.0, 0.012, 1.0, 0.0)
    b.inputs['Emission Color'].default_value = (*VIOLET, 1)
    n.set(b.inputs['Emission Strength'], n.math('MULTIPLY', vein, GR._value(m.node_tree, 'vein', 0.0)))
    n.set(out.inputs['Surface'], b.outputs[0])
    return m


def steel_mat(name, dirt=0.55):
    m, n = SP.BP._new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    b = n.node('ShaderNodeBsdfPrincipled', Metallic=0.75, Roughness=0.5)
    tc = n.node('ShaderNodeTexCoord')
    nz = n.node('ShaderNodeTexNoise', Scale=6.0, Detail=8.0)
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    k = n.maprange(nz.outputs['Fac'], 0.45 - dirt * 0.2, 0.62, 0.0, 1.0)
    mx = n.node('ShaderNodeMix')
    mx.data_type = 'RGBA'
    n.set(mx.inputs[0], k)
    mx.inputs[6].default_value = (0.09, 0.09, 0.095, 1)
    mx.inputs[7].default_value = (0.3, 0.23, 0.2, 1)
    n.set(b.inputs['Base Color'], mx.outputs[2])
    n.set(b.inputs['Metallic'], n.maprange(k, 0.0, 1.0, 0.8, 0.1))
    n.set(b.inputs['Roughness'], n.maprange(k, 0.0, 1.0, 0.42, 0.95))
    sc = n.node('ShaderNodeTexNoise', Scale=60.0, Detail=3.0)
    n.set(sc.inputs['Vector'], tc.outputs['Object'])
    bump = n.node('ShaderNodeBump', Strength=0.25, Distance=0.01)
    n.set(bump.inputs['Height'], sc.outputs['Fac'])
    n.set(b.inputs['Normal'], bump.outputs[0])
    n.set(out.inputs['Surface'], b.outputs[0])
    return m


# ================================================================== running gear (close-up only)
R_RUN = 0.55
X_END = 2.75
Z_C = 0.58
PERIM = 2 * (2 * X_END) + 2 * math.pi * R_RUN
N_LINK = 74
PITCH = PERIM / N_LINK
SIDE_Y = 1.97                     # track centre |y|
TRACK_W = 0.56


def run_path(s):
    """Hull-local (x, z) and tangent angle at arc length s along the track loop. s=0 at the bottom front;
    increasing s runs backward along the ground, up round the sprocket, forward along the top."""
    s %= PERIM
    L = 2 * X_END
    A = math.pi * R_RUN
    if s < L:
        return X_END - s, Z_C - R_RUN, math.pi
    s -= L
    if s < A:
        th = -math.pi / 2 - s / R_RUN                 # rear arc, bottom -> back -> top
        return -X_END + R_RUN * math.cos(th), Z_C + R_RUN * math.sin(th), th - math.pi / 2
    s -= A
    if s < L:
        return -X_END + s, Z_C + R_RUN, 0.0
    s -= L
    th = math.pi / 2 - s / R_RUN                       # front arc, top -> front -> bottom
    return X_END + R_RUN * math.cos(th), Z_C + R_RUN * math.sin(th), th - math.pi / 2


def link_mesh(mat):
    bm = bmesh.new()

    def box(cx, cy, cz, sx, sy, sz):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r['verts']:
            v.co = Vector((cx + v.co.x * sx, cy + v.co.y * sy, cz + v.co.z * sz))
    box(0, 0, 0, 0.17, TRACK_W, 0.045)                      # shoe plate
    box(0.0, 0, -0.04, 0.045, TRACK_W * 0.96, 0.04)         # grouser bar (ground side = local -Z)
    box(0.0, 0, 0.055, 0.07, 0.06, 0.08)                    # guide horn (wheel side)
    for sy in (-1, 1):                                       # end connectors
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.032, radius2=0.032, depth=0.07)
        for v in r['verts']:
            v.co = Vector((0.095 + v.co.x, sy * (TRACK_W / 2 + 0.02) + v.co.z, v.co.y))
    me = bpy.data.meshes.new('TrackLink')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = False
    return me


def wheel_mesh(r, w, mat, mat2, spokes=6, teeth=0):
    bm = bmesh.new()

    def cyl(rad, depth, y, seg=28):
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=rad, radius2=rad, depth=depth)
        for v in res['verts']:
            v.co = Vector((v.co.x, v.co.z + y, v.co.y))
        return res
    cyl(r, w, 0.0)                                  # tyre
    cyl(r * 0.8, w * 1.12, 0.0)                     # rim face
    cyl(r * 0.3, w * 1.4, 0.0, 16)                  # hub
    for i in range(spokes):                         # hub bolts
        a = 2 * math.pi * i / spokes
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.035, radius2=0.035, depth=w * 1.55)
        for v in res['verts']:
            v.co = Vector((v.co.x + r * 0.2 * math.cos(a), v.co.z, v.co.y + r * 0.2 * math.sin(a)))
    for i in range(spokes):                         # lightening holes, read as dark dimples
        a = 2 * math.pi * (i + 0.5) / spokes
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r * 0.11, radius2=r * 0.11,
                                    depth=w * 1.16)
        for v in res['verts']:
            v.co = Vector((v.co.x + r * 0.55 * math.cos(a), v.co.z, v.co.y + r * 0.55 * math.sin(a)))
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        res = bmesh.ops.create_cube(bm, size=1.0)
        for v in res['verts']:
            p = Vector((v.co.x * 0.08, v.co.y * w * 0.5, v.co.z * 0.1 + r + 0.03))
            v.co = Vector((p.x * math.cos(a) + p.z * math.sin(a), p.y, -p.x * math.sin(a) + p.z * math.cos(a)))
    me = bpy.data.meshes.new('Wheel')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    me.materials.append(mat2)
    for p in me.polygons:
        p.use_smooth = True
        if abs(p.normal.y) > 0.9 and math.hypot(p.center.x, p.center.z) < r * 0.85:
            p.material_index = 1
    return me


def strip_running_gear(hero):
    """Hide the phone-level belt and cut the Lancer's low-poly wheels out of its hull mesh."""
    for o in [hero] + list(hero.children_recursive):
        if o.type != 'MESH':
            continue
        if o.name.startswith('Tread') or o.name.startswith('Flash'):
            o.hide_render = True
            o.keyframe_insert('hide_render', frame=1)
        elif o.name.startswith('Hull'):
            o.data = o.data.copy()
            bm = bmesh.new()
            bm.from_mesh(o.data)
            kill = [f for f in bm.faces
                    if all(abs(v.co.y) > 1.55 and v.co.z < 1.0 for v in f.verts)]
            bmesh.ops.delete(bm, geom=kill, context='FACES')
            bm.to_mesh(o.data)
            bm.free()


# ================================================================== scene
def build(draft=True):
    sc = V.Scene(10.0, draft)
    nf = sc.nf
    rnd = random.Random(2711)
    # ---------------------------------------------------------------- sky and sun: the ground scenes' look
    NP.sky(top=(0.09, 0.08, 0.2), horizon=(0.85, 0.5, 0.52), strength=1.25, below=(0.14, 0.1, 0.1))
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    SP.link(sun)
    sun.data.energy = 4.6
    sun.data.color = (1.0, 0.78, 0.58)
    sun.data.angle = math.radians(1.5)
    sun.rotation_euler = (math.radians(62), 0, math.radians(-38))   # low, behind the camera's left: lights the tank's near side
    # ---------------------------------------------------------------- ground: dense at the camera
    xs = [X0 + v for v in axis(230, 0.06, 1.028)]
    ys = [Y0 + v for v in axis(240, 0.06, 1.026, back=70)]
    me = bpy.data.meshes.new('LandGround')
    verts = [(x, y, zg(x, y)) for y in ys for x in xs]
    nx = len(xs)
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(len(ys) - 1) for i in range(nx - 1)]
    me.from_pydata(verts, [], faces)
    for p in me.polygons:
        p.use_smooth = True
    gm = ground_mat()
    me.materials.append(gm)
    g = bpy.data.objects.new('LandGround', me)
    SP.link(g)
    # ---------------------------------------------------------------- pebbles and stones
    stone_m = steel_mat('Stone', dirt=1.0)
    nt = stone_m.node_tree
    bsdf = next(nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED')
    for lk in list(bsdf.inputs['Metallic'].links):
        nt.links.remove(lk)
    bsdf.inputs['Metallic'].default_value = 0.0
    rock_meshes = []
    for k in range(6):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        r2 = random.Random(90 + k)
        for v in bm.verts:
            v.co *= 1 + 0.28 * noise.noise(v.co * 1.7 + Vector((k, 0, 0)))
            v.co.z *= r2.uniform(0.45, 0.7)
        mr = bpy.data.meshes.new(f'Rock{k}')
        bm.to_mesh(mr)
        bm.free()
        mr.materials.append(stone_m)
        rock_meshes.append(mr)
    pebbles = []
    for i in range(1800):
        d = 0.8 + 30 * rnd.random() ** 1.4
        a = rnd.uniform(-0.25, math.pi + 0.25)
        x, y = X0 + d * math.cos(a), Y0 + d * math.sin(a) * 1.4
        s = rnd.uniform(0.006, 0.026) * (1 + 3 * rnd.random() ** 8) * (1 + d / 12)
        o = bpy.data.objects.new(SP._uid('Peb'), rock_meshes[i % 6])
        SP.link(o)
        o.location = (x, y, zg(x, y) + s * 0.25)
        o.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.3))
        o.scale = (s, s * rnd.uniform(0.7, 1.2), s)
        pebbles.append((o, d))
    # ---------------------------------------------------------------- the rumble: pods landing far off
    amp = {}                                                   # rumble amplitude per frame (0..1)
    for f in range(1, nf + 1):
        amp[f] = 0.08 * ramp(f, fr(1.0), fr(2.6)) + 0.92 * ramp(f, fr(2.4), fr(5.4)) * (1 - 0.6 * ramp(f, fr(8.0), fr(10)))
    impacts = [(fr(0.7), 0.9), (fr(1.6), 0.5), (fr(2.4), 0.7), (fr(2.9), 0.3), (fr(3.4), 0.55),
               (fr(3.8), 0.15), (fr(4.2), 0.4), (fr(4.6), 0.25)]
    pod_m = SP.emit('PodHot', (1.0, 0.62, 0.25), 30.0)
    trail_m = V.soft_glow('PodTrail', (1.0, 0.55, 0.2), 9.0)
    for i, (fi, side) in enumerate(impacts):
        px = X0 - 260 + 700 * side + rnd.uniform(-40, 40)
        py = Y0 + rnd.uniform(260, 620)
        p_hit = Vector((px, py, GR.height(px, py)))
        p_top = p_hit + Vector((rnd.uniform(-160, 160), rnd.uniform(-80, 80), 900))
        f0 = fi - 22
        head = C.uv_sphere(SP._uid('PodHead'), 3.0, seg=(12, 8), mat=pod_m)
        SP.key_loc(head, [(f0, p_top), (fi, p_hit)], 'LINEAR')
        SP.show(head, f0, fi)
        head.visible_shadow = False
        tr = C.uv_sphere(SP._uid('PodTrail'), 1.0, seg=(16, 10), mat=trail_m)
        tr.parent = head
        dv = (p_top - p_hit).normalized()
        tr.location = dv * 60
        tr.rotation_mode = 'QUATERNION'
        tr.rotation_quaternion = dv.to_track_quat('Z', 'X')
        tr.scale = (6, 6, 62)
        SP.show(tr, f0, fi)
        tr.visible_shadow = False
        SP.boom(p_hit + Vector((0, 0, 10)), fi, 32.0, life=1.6, light=4e7, seed=i)
        for j in range(5):                              # dust dome rolling out
            dm = GR.dust_mat(SP._uid('PodDustM'), (0.6, 0.48, 0.42))
            d = C.uv_sphere(SP._uid('PodDust'), 1.0, seg=(16, 10), mat=dm)
            a = 2 * math.pi * j / 5 + rnd.uniform(-0.4, 0.4)
            off = Vector((math.cos(a), math.sin(a), 0))
            SP.key_loc(d, [(fi, p_hit + Vector((0, 0, 8))), (fi + 70, p_hit + off * 70 + Vector((0, 0, 30)))], 'BEZIER')
            SP.key_scale(d, [(fi, (14, 14, 10)), (fi + 70, (70, 70, 45))], 'BEZIER')
            SP.key_node(dm, 'V', [(fi, 0.9), (fi + 40, 0.6), (nf, 0.3)])
            SP.show(d, fi, nf)
            d.visible_shadow = False
    # ---------------------------------------------------------------- violet veins stir (foreshadow)
    SP.key_node(gm, 'vein', [(1, 0.0), (fr(3.3), 0.0), (fr(3.45), 2.2), (fr(3.75), 0.0), (fr(4.4), 0.0),
                             (fr(4.5), 3.0), (fr(4.65), 0.4), (fr(4.9), 0.0), (nf, 0.0)])
    # ---------------------------------------------------------------- pebbles hop, dirt pops up
    hop_f0, hop_f1 = fr(2.2), fr(9.0)
    for o, d in pebbles:
        if d > 9 or o.scale.x > 0.09:
            continue
        base = o.location.copy()
        r0 = Vector(o.rotation_euler)
        keys = [(1, base)]
        rots = [(1, r0)]
        f = hop_f0 + rnd.randint(0, 18)
        while f < hop_f1:
            a = amp[min(nf, f)]
            if a > 0.12 and rnd.random() < a:
                h = (0.008 + 0.05 * a) * rnd.uniform(0.4, 1.0) / (1 + d * 0.15)
                up = rnd.randint(3, 5)
                keys += [(f, base), (f + up, base + Vector((rnd.uniform(-1, 1) * h * 0.5, rnd.uniform(-1, 1) * h * 0.5, h))),
                         (f + 2 * up, base)]
                rots += [(f, r0), (f + 2 * up, Vector((r0[0] + rnd.uniform(-0.6, 0.6), r0[1] + rnd.uniform(-0.6, 0.6), r0[2])))]
                r0 = rots[-1][1]
                f += 2 * up + rnd.randint(1, 8)
            else:
                f += rnd.randint(2, 6)
        if len(keys) > 1:
            SP.key_loc(o, keys, 'BEZIER')
            SP.key_rot(o, [(ff, tuple(math.degrees(v) for v in r)) for ff, r in rots], 'BEZIER')
    pops = []
    f = fr(2.7)
    while f < fr(6.6):
        a = amp[f]
        d = rnd.uniform(1.2, 14.0)
        ang = rnd.uniform(0.25, math.pi - 0.25)
        pops.append((f, Vector((X0 + d * math.cos(ang), Y0 + d * math.sin(ang), 0)), a, d))
        f += max(2, int(rnd.uniform(4, 12) * (1.2 - a)))
    for fp, p, a, d in pops:
        p.z = zg(p.x, p.y)
        dm = GR.dust_mat(SP._uid('PopDustM'))
        s1 = (0.35 + 0.6 * a) * (1 + d / 12)
        o = C.uv_sphere(SP._uid('PopDust'), 1.0, seg=(14, 9), mat=dm)
        SP.key_loc(o, [(fp, p + Vector((0, 0, 0.05))), (fp + 30, p + Vector((0.4, 0, s1 * 0.9)))], 'BEZIER')
        SP.key_scale(o, [(fp, (0.08,) * 3), (fp + 8, (s1 * 0.6, s1 * 0.6, s1 * 0.5)), (fp + 40, (s1, s1, s1 * 0.8))], 'BEZIER')
        SP.key_node(dm, 'V', [(fp, 0.9), (fp + 12, 0.7), (fp + 40, 0.0)])
        SP.show(o, fp, fp + 40)
        o.visible_shadow = False
        for k in range(rnd.randint(4, 8)):              # clods thrown up
            c = bpy.data.objects.new(SP._uid('Clod'), rock_meshes[k % 6])
            SP.link(c)
            c.data = rock_meshes[k % 6]
            s = rnd.uniform(0.012, 0.035) * (1 + d / 10)
            c.scale = (s, s, s)
            v = Vector((rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(1.6, 3.4) * (0.6 + a)))
            ks = []
            for t in range(0, 40):
                pt = p + v * (t / FPS) + Vector((0, 0, -4.9 * (t / FPS) ** 2))
                ks.append((fp + t, pt))
                if pt.z < p.z and t > 2:
                    break
            SP.key_loc(c, ks, 'LINEAR')
            SP.key_rot(c, [(fp, (0, 0, 0)), (ks[-1][0], (rnd.uniform(-400, 400), rnd.uniform(-400, 400), 0))], 'LINEAR')
            SP.show(c, fp, ks[-1][0] + 30)
    # ---------------------------------------------------------------- the tank
    tank = GR.hero_unit('human/lancer', 'LandLancer')
    strip_running_gear(tank)
    hull_mat = None
    for o in tank.children_recursive:
        if o.type == 'MESH' and o.name.startswith('Hull') and o.material_slots:
            hull_mat = o.material_slots[0].material
    link_m = steel_mat('TrackSteel')
    rubber = steel_mat('WheelSteel', dirt=0.3)
    lme = link_mesh(link_m)
    ty = Y0 + TANK_DY
    x_enter = X0 - 7.5                       # centre x when its front edge reaches the left of frame
    f_stop = F_HIT + 16

    def travel(f):
        """Distance driven: steady 6 m/s, then hit and dragged to a stop in ~0.7 s."""
        if f <= F_HIT:
            return SPEED * (f - F_ENTER) / FPS
        t = min(f, f_stop) - F_HIT
        T = f_stop - F_HIT
        return SPEED * (F_HIT - F_ENTER) / FPS + SPEED / FPS * (t - t * t / (2 * T))
    frames = list(range(1, nf + 1))
    locs, quats = [], []
    for f in frames:
        x = x_enter + travel(f)
        z = GR.height(x, ty) + detail(x, ty) * 0.3
        q = Quaternion((0, 0, 1), 0.02 * math.sin(f * 0.07))
        q = q @ Quaternion((1, 0, 0), 0.012 * math.sin(f * 0.9) * (1 if f < F_HIT else 0))
        if f >= F_HIT:                        # the blow: bucks nose-up, lifts and slams back down
            t = (f - F_HIT) / FPS
            lift = 0.32 * max(0.0, math.sin(min(t / 0.42, 1.0) * math.pi))
            pitch = 0.07 * math.exp(-t * 4.5) * math.cos(t * 13) if t < 1.2 else 0.0
            roll = 0.05 * (1 - math.exp(-t * 6))
            z += lift
            q = q @ Quaternion((0, 1, 0), pitch) @ Quaternion((1, 0, 0), roll)
        locs.append(Vector((x, ty, z)))
        quats.append(q)
    bake(tank, frames, locs, quats)
    SP.show(tank, F_ENTER - 30, nf)
    # turret jumps on its ring at the hit and lands crooked
    piv = next((o for o in tank.children_recursive if o.name.startswith('TurretPivot')), None)
    if piv:
        p0 = piv.location.copy()
        piv.rotation_mode = 'XYZ'
        r0 = piv.rotation_euler.copy()
        SP.key_loc(piv, [(F_HIT + 2, p0), (F_HIT + 7, p0 + Vector((0, 0, 0.55))), (F_HIT + 14, p0 + Vector((-0.1, 0.08, 0.08)))], 'BEZIER')
        SP.key_rot(piv, [(F_HIT + 2, tuple(math.degrees(v) for v in r0)),
                         (F_HIT + 14, (math.degrees(r0.x) + 4, math.degrees(r0.y) - 3, math.degrees(r0.z) + 9))], 'BEZIER')
    # links and wheels, both sides
    gear = []
    for side in (-1, 1):
        links = []
        for i in range(N_LINK):
            o = bpy.data.objects.new(SP._uid('Link'), lme)
            SP.link(o)
            o.parent = tank
            o.rotation_mode = 'XYZ'
            links.append(o)
        gear.append((side, links))
        wheels = []
        wm = wheel_mesh(0.42, 0.3, rubber, hull_mat or rubber)
        for wx in (-2.15, -1.29, -0.43, 0.43, 1.29, 2.15):
            o = bpy.data.objects.new(SP._uid('RoadWheel'), wm)
            SP.link(o)
            o.parent = tank
            o.location = (wx, side * (SIDE_Y + 0.05), Z_C - R_RUN + 0.03 + 0.42 + 0.03)
            wheels.append((o, 0.42))
        sp = wheel_mesh(0.47, 0.26, rubber, hull_mat or rubber, spokes=8, teeth=11)
        idl = wheel_mesh(0.45, 0.28, rubber, hull_mat or rubber, spokes=5)
        for wx, m_, r_ in ((-X_END, sp, 0.47), (X_END, idl, 0.45)):
            o = bpy.data.objects.new(SP._uid('EndWheel'), m_)
            SP.link(o)
            o.parent = tank
            o.location = (wx, side * (SIDE_Y + 0.05), Z_C)
            wheels.append((o, r_))
        for rx in (-1.3, 0.0, 1.3):           # return rollers under the top run
            o = bpy.data.objects.new(SP._uid('Roller'), wheel_mesh(0.13, 0.2, rubber, hull_mat or rubber, spokes=4))
            SP.link(o)
            o.parent = tank
            o.location = (rx, side * (SIDE_Y + 0.02), Z_C + R_RUN - 0.06 - 0.13)
            wheels.append((o, 0.13))
        for f in frames:
            dist = travel(f)
            for o, r_ in wheels:
                o.rotation_euler = (0, dist / r_, 0)
                o.keyframe_insert('rotation_euler', index=1, frame=f)
        for i, o in enumerate(links):
            for f in frames:
                s = i * PITCH + travel(f)
                x, z, ang = run_path(s)
                o.location = (x, side * SIDE_Y, z)
                # local -Z (grouser) points away from the loop centre
                o.rotation_euler = (0, -ang + math.pi, 0)
                o.keyframe_insert('location', frame=f)
                o.keyframe_insert('rotation_euler', index=1, frame=f)
        for o, _ in wheels:
            C.set_interp(o, 'LINEAR')
        for o in links:
            C.set_interp(o, 'LINEAR')
    # dirt flung off the tracks and the dust wake
    for f in range(F_ENTER - 20, f_stop, 2):
        x = x_enter + travel(f)
        for side in (-1, 1):
            p = Vector((x - X_END - 0.3, ty + side * SIDE_Y, GR.height(x, ty) + 0.3))
            if side == -1:                        # near track: clods spat up off the sprocket
                for k in range(2):
                    c = bpy.data.objects.new(SP._uid('TClod'), rock_meshes[(f + k) % 6])
                    SP.link(c)
                    s = rnd.uniform(0.015, 0.04)
                    c.scale = (s, s, s)
                    v = Vector((rnd.uniform(-2.5, -0.5), rnd.uniform(-0.6, 0.3), rnd.uniform(1.0, 2.6)))
                    p1 = p + Vector((0.3, 0, 0.4))
                    ks = [(f + t, p1 + v * (t / FPS) + Vector((0, 0, -4.9 * (t / FPS) ** 2))) for t in range(0, 16)]
                    SP.key_loc(c, ks, 'LINEAR')
                    SP.show(c, f, f + 15)
            if f % 4 == 0:
                dm = GR.dust_mat(SP._uid('WakeM'))
                o = C.uv_sphere(SP._uid('Wake'), 1.0, seg=(14, 9), mat=dm)
                s1 = rnd.uniform(1.4, 2.4)
                SP.key_loc(o, [(f, p), (f + 60, p + Vector((-1.5, rnd.uniform(-1, 1.5), 1.6)))], 'BEZIER')
                SP.key_scale(o, [(f, (0.4, 0.4, 0.3)), (f + 60, (s1 * 1.2, s1 * 1.2, s1 * 0.8))], 'BEZIER')
                SP.key_node(dm, 'V', [(f, 0.5), (f + 20, 0.35), (f + 60, 0.0)])
                SP.show(o, f, f + 60)
                o.visible_shadow = False
    # ---------------------------------------------------------------- the electric missile
    x_hit = x_enter + travel(F_HIT)
    hit = Vector((x_hit + 2.2, ty - 1.4, GR.height(x_hit, ty) + 1.5))
    m0 = hit + Vector((150, -14, 30))
    mid = hit + Vector((60, -9, 9))
    f_m0 = F_HIT - 28
    msl = bpy.data.objects.new('Missile', None)
    SP.link(msl)
    pts = []
    for f in range(f_m0, F_HIT + 1):
        t = (f - f_m0) / (F_HIT - f_m0)
        t = t ** 1.25                                     # still accelerating at impact
        p = (1 - t) ** 2 * m0 + 2 * (1 - t) * t * mid + t * t * hit
        pts.append((f, p))
    msl.rotation_mode = 'QUATERNION'
    for (f, p), (_, pn) in zip(pts, pts[1:] + [(0, pts[-1][1] + (pts[-1][1] - pts[-2][1]))]):
        msl.location = p
        msl.rotation_quaternion = (pn - p).to_track_quat('X', 'Z')
        msl.keyframe_insert('location', frame=f)
        msl.keyframe_insert('rotation_quaternion', frame=f)
    C.set_interp(msl, 'LINEAR')
    body_m = SP.emit('MslBody', GOLD, 5.0)
    body = C.uv_sphere('MslBody', 1.0, seg=(16, 10), mat=body_m, scale=(1.6, 0.3, 0.3))
    body.parent = msl
    halo = C.uv_sphere('MslHalo', 1.0, seg=(16, 10), mat=V.soft_glow('MslHaloM', GOLD, 8.0), scale=(3.6, 1.5, 1.5))
    halo.parent = msl
    for o in (body, halo):
        o.visible_shadow = False
        SP.show(o, f_m0, F_HIT)
    thr = V.lightning_engines(msl, 'MslThr', [(-1.0, 0, 0)], r=0.35, length=7.0, f_end=F_HIT)
    for o in thr:
        SP.show(o, f_m0, F_HIT)
    arcs = SP.flicker_lightning([((0.8, 0, 0), (-3.5, 0.9, 0.5)), ((0.5, 0, 0), (-4.0, -0.8, -0.4)),
                                 ((0.0, 0, 0), (-2.5, 0.2, 1.0))], 4401, f_m0, F_HIT, every=1, width=0.06,
                                name='MslArc', zone_col=GOLD, strength=6.0)
    for o in arcs:
        o.parent = msl
    L = bpy.data.objects.new('MslLight', bpy.data.lights.new('MslLight', 'POINT'))
    SP.link(L)
    L.parent = msl
    L.data.color = GOLD
    L.data.energy = 4e4
    SP.show(L, f_m0, F_HIT)
    # ---------------------------------------------------------------- the hit
    SP.gold_boom(hit, F_HIT, 2.6, life=0.8, light=4e5, seed=3)
    SP.boom(hit + Vector((-1.2, 0.6, 1.2)), F_HIT + 4, 3.4, life=1.5, light=2.5e5, seed=5, follow=(0, 0, 2.5))
    SP.shards(hit, F_HIT, 30, GOLD, 0.08, 14, seed=4410, life=0.8, strength=6.0)
    bpy.context.scene.frame_set(F_HIT + 6)
    bpy.context.view_layer.update()
    mw = tank.matrix_world.copy()
    hull_pts = [mw @ Vector(v) for v in ((2.9, -2.0, 1.2), (1.0, -2.3, 0.4), (-1.4, -2.3, 1.0), (-3.2, -2.1, 0.5),
                                         (0.4, -1.2, 2.2), (-0.8, 0.9, 3.0), (2.0, 1.6, 1.4), (-2.6, -0.4, 1.9))]
    SP.flicker_lightning([(hull_pts[i], hull_pts[i + 1]) for i in range(len(hull_pts) - 1)] +
                         [(hit, hull_pts[4]), (hit, hull_pts[1])], 4420, F_HIT, F_HIT + 34, every=1, width=0.045,
                         name='HitArc', zone_col=GOLD, strength=5.0)
    for k, (fa, fb) in enumerate([(F_HIT + 50, F_HIT + 56), (F_HIT + 78, F_HIT + 81), (F_HIT + 101, F_HIT + 105)]):
        a = hull_pts[k * 2 + 1]
        SP.flicker_lightning([(a, hull_pts[k * 2 + 2]), (a, a + Vector((0.4, -0.3, -0.9)))], 4430 + k, fa, fb,
                             every=1, width=0.035, name=f'LateArc{k}', zone_col=GOLD, strength=5.0)
    # debris: dark chunks off the hull
    for k in range(14):
        c = bpy.data.objects.new(SP._uid('Debris'), rock_meshes[k % 6])
        SP.link(c)
        c.data = rock_meshes[k % 6].copy()
        c.data.materials.clear()
        c.data.materials.append(hull_mat or stone_m)
        s = rnd.uniform(0.08, 0.25)
        c.scale = (s * 1.6, s, s * 0.5)
        v = Vector((rnd.uniform(-5, 3), rnd.uniform(-6, 2), rnd.uniform(4, 10)))
        ks = []
        for t in range(0, 60):
            pt = hit + v * (t / FPS) + Vector((0, 0, -4.9 * (t / FPS) ** 2))
            gz = GR.height(pt.x, pt.y)
            if pt.z < gz:
                pt.z = gz + 0.05
                ks.append((F_HIT + t, pt))
                break
            ks.append((F_HIT + t, pt))
        SP.key_loc(c, ks, 'LINEAR')
        SP.key_rot(c, [(F_HIT, (0, 0, 0)), (ks[-1][0], (rnd.uniform(-500, 500), rnd.uniform(-500, 500), 0))], 'LINEAR')
        SP.show(c, F_HIT, nf)
    # the wreck burns: flames on the deck, smoke climbing
    deck = Vector((x_enter + travel(f_stop) - 0.8, ty, GR.height(x_hit, ty) + 2.0))
    for k, f in enumerate(range(F_HIT + 18, nf, 7)):
        SP.boom(deck + Vector((rnd.uniform(-1.6, 1.6), rnd.uniform(-1, 1), 0)), f, rnd.uniform(0.9, 1.5), life=0.9,
                light=1.5e5 if k % 3 == 0 else 0.0, seed=20 + k, follow=(0, 0, 1.4))
    for k, f in enumerate(range(F_HIT + 10, nf, 5)):
        dm = GR.dust_mat(SP._uid('SmokeM'), (0.08, 0.07, 0.07))
        o = C.uv_sphere(SP._uid('Smoke'), 1.0, seg=(14, 9), mat=dm)
        p = deck + Vector((rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.6), 0.6))
        SP.key_loc(o, [(f, p), (f + 80, p + Vector((-3.0, 2.5, 9.0)))], 'LINEAR')
        SP.key_scale(o, [(f, (0.8,) * 3), (f + 80, (4.0, 4.0, 3.2))], 'LINEAR')
        SP.key_node(dm, 'V', [(f, 0.9), (f + 80, 0.0)])
        SP.show(o, f, min(nf, f + 80))
        o.visible_shadow = False
    # ---------------------------------------------------------------- the next wave rolls on, gold flashes east
    lod = GR.load_unit('human/lancer_lod', mat_from='human/lancer')
    for k in range(9):
        o = GR.instance(lod, SP._uid('Wave'))
        y = Y0 + rnd.uniform(40, 160)
        x1 = X0 - 120 + k * 22 + rnd.uniform(-6, 6)
        ks = []
        for f in range(F_HIT - 30, nf + 1, 6):
            x = x1 + 5.5 * (f - F_HIT + 30) / FPS
            ks.append((f, Vector((x, y, GR.height(x, y)))))
        SP.key_loc(o, ks, 'LINEAR')
        SP.show(o, F_HIT - 30, nf)
    for k in range(6):
        p = Vector((X0 + rnd.uniform(150, 420), Y0 + rnd.uniform(120, 300), 0))
        p.z = GR.height(p.x, p.y) + 3
        f = F_HIT + 14 + k * 11 + rnd.randint(0, 6)
        SP.gold_boom(p, f, rnd.uniform(5, 9), life=0.8, light=3e6, seed=60 + k)
    # ---------------------------------------------------------------- camera
    z0 = zg(X0, Y0)
    cx = lambda f: x_enter + travel(f)          # noqa: E731
    keys = [(1, Vector((X0, Y0, z0 + 0.32)), Vector((X0 + 1.0, Y0 + 30, z0 + 1.0)), 22),
            (fr(2.6), Vector((X0 + 0.1, Y0 + 0.35, z0 + 0.3)), Vector((X0 + 1.2, Y0 + 30, z0 + 0.8)), 22),
            (F_ENTER - 6, Vector((X0 + 0.2, Y0 + 0.6, z0 + 0.28)), Vector((X0 - 0.5, Y0 + 30, z0 - 0.4)), 22),
            (F_ENTER + 26, Vector((X0 + 0.2, Y0 + 0.6, z0 + 0.32)), Vector((cx(F_ENTER + 26) - 1.0, ty, z0 + 0.55)), 22),
            (F_HIT, Vector((X0 + 0.6, Y0 + 0.2, z0 + 0.55)), Vector((cx(F_HIT) + 1.5, ty, z0 + 0.9)), 21),
            (F_HIT + 30, Vector((X0 + 0.7, Y0 - 2.2, z0 + 1.2)), Vector((cx(F_HIT) + 1.0, ty, z0 + 1.5)), 22),
            (nf, Vector((X0 + 0.4, Y0 - 5.0, z0 + 1.9)), Vector((cx(f_stop) + 0.5, ty + 10, z0 + 2.4)), 23)]
    shake = []
    for f in range(fr(0.6), nf, 4):                 # continuous rumble, following amp
        a = amp[f]
        if a > 0.02:
            shake.append((f, 0.012 * a, 6, 0.006 * a))
    for fi, _ in impacts:
        shake.append((fi + 6, 0.015, 14, 0.008))
    shake.append((F_HIT, 0.12, 22, 0.05))
    sc.shot('A', 1, nf, keys, shake=shake)
    return sc
