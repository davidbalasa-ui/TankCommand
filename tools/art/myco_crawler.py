"""Third faction (mushroom, working name Myco) heavy crawler, big-unit phone budget <= 5,000 triangles.

David's direction: a massive organic bush tearing itself out of the ground, completely organic,
nothing toy-like. Following the style reference: a fibrous pale stem under a broad red cap with
glowing gills and a ruffled spore fan. The stem flares into buttresses at the base and each buttress
continues as a huge tapering root, so the whole unit reads as one plant. Roots fan out all round
like an uprooted tree, rip out of the soil at the back and drive back in at the front.
In game each root is 3 rigid segments on a cycle; dirt clods and dust are cheap particles.

Run with Blender's Python (pip bpy):
  python myco_crawler.py <atlas_dir> <out.glb> [render_dir] [anim_dir]
"""
import math
import random
import sys

import bpy
import mathutils
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
atlas_dir, out_glb = args[0], args[1]
render_dir = args[2] if len(args) > 2 else None
anim_dir = args[3] if len(args) > 3 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
TILES = {
    'flesh': (0.0, 0.5, 0.5, 1.0), 'cap': (0.5, 0.5, 1.0, 1.0), 'gill': (0.0, 0.25, 0.5, 0.5),
    'myc': (0.5, 0.25, 1.0, 0.5), 'bulb': (0.0, 0.0, 0.25, 0.25), 'ruffle': (0.25, 0.0, 0.5, 0.25),
    'moss': (0.5, 0.0, 0.75, 0.25), 'spore': (0.75, 0.0, 1.0, 0.25),
}
mat = bpy.data.materials.new('MycoAtlas')
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes['Principled BSDF']
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(f'{atlas_dir}/myco_atlas.png')
emi = nt.nodes.new('ShaderNodeTexImage'); emi.image = bpy.data.images.load(f'{atlas_dir}/myco_emissive.png')
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(emi.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = 1.6
bsdf.inputs['Roughness'].default_value = 0.75
rng = random.Random(31)


def build(name, verts, faces, fuvs, tile, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    layer = me.uv_layers.new(name='UVMap')
    u0, v0, u1, v1 = TILES[tile]
    u0 += 0.01; v0 += 0.01; u1 -= 0.01; v1 -= 0.01
    for poly, uvs in zip(me.polygons, fuvs):
        for li, (u, v) in zip(poly.loop_indices, uvs):
            layer.data[li].uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))
        poly.use_smooth = smooth
    return obj


def rings_obj(name, rings, tile, top=None, bottom=None, urep=1, uv_fn=None, smooth=True):
    """Quads between rings of equal size; u runs round the ring (repeated urep times), v along the rings."""
    n, R = len(rings[0]), len(rings)
    verts = [Vector(p) for ring in rings for p in ring]
    faces, fuvs = [], []

    def uv(r, k, kk):
        base = math.floor(k * urep / n)
        return (kk * urep / n - base, r / (R - 1))

    for r in range(R - 1):
        for k in range(n):
            j = (k + 1) % n
            faces.append([r * n + k, r * n + j, (r + 1) * n + j, (r + 1) * n + k])
            fuvs.append([uv(r, k, k), uv(r, k, k + 1), uv(r + 1, k, k + 1), uv(r + 1, k, k)])
    if top is not None:
        t = len(verts); verts.append(Vector(top)); last = (R - 1) * n
        for k in range(n):
            faces.append([last + k, last + (k + 1) % n, t])
            u = uv(R - 1, k, k)[0]
            fuvs.append([uv(R - 1, k, k), uv(R - 1, k, k + 1), (u + 0.5 * urep / n, 1.0)])
    if bottom is not None:
        b = len(verts); verts.append(Vector(bottom))
        for k in range(n):
            faces.append([(k + 1) % n, k, b])
            u = uv(0, k, k)[0]
            fuvs.append([uv(0, k, k + 1), uv(0, k, k), (u + 0.5 * urep / n, 0.0)])
    if uv_fn is not None:
        fuvs = [[uv_fn(verts[vi]) for vi in f] for f in faces]
    return build(name, verts, faces, fuvs, tile, smooth)


def frame_at(P, i):
    n = len(P)
    fwd = (P[min(n - 1, i + 1)] - P[max(0, i - 1)]).normalized()
    side = fwd.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    return fwd, side, side.cross(fwd)


def tube(name, pts, r0, r1, sides, tile, twist=0.0, lump=0.0, seed=0, taper=1.4, flat=1.0):
    """Tapered, twisted, lumpy tube along a polyline ending in a point: roots, stems, rootlets."""
    rr = random.Random(seed)
    P = [Vector(p) for p in pts]
    n = len(P)
    rings = []
    for i, p in enumerate(P):
        t = i / (n - 1)
        _, side, up = frame_at(P, i)
        r = r1 + (r0 - r1) * (1 - t) ** taper
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + twist * t
            rk = r * (1 + lump * rr.uniform(-1, 1))
            ring.append(p + (side * math.cos(a) + up * math.sin(a) * flat) * rk)
        rings.append(ring)
    end = P[-1] + (P[-1] - P[-2]).normalized() * max(r1 * 2.0, 0.05)
    return rings_obj(name, rings, tile, top=end)


def bezier(p0, p1, p2, p3, t):
    s = 1 - t
    return s ** 3 * p0 + 3 * s * s * t * p1 + 3 * s * t * t * p2 + t ** 3 * p3


def lathe(name, profile, sides, tile, center, noise, seed, wave=0.0, lobes=5, tilt=(0, 0), top=None, urep=1,
          uv_fn=None, twist=0.0):
    """Turned shape. profile: (radius, height[, wave amp]). Noise and a lobed rim keep it organic."""
    rr = random.Random(seed)
    c = Vector(center)
    rot = mathutils.Euler((tilt[0], tilt[1], 0)).to_matrix()
    rings = []
    for ri, pr in enumerate(profile):
        r, h = pr[0], pr[1]
        amp = pr[2] if len(pr) > 2 else wave
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            w = 1 + amp * math.cos(lobes * a + ri * 0.35 * (1 if wave else 0)) + noise * rr.uniform(-1, 1)
            aa = a + twist * h
            ring.append(c + rot @ Vector((r * w * math.cos(aa), r * w * math.sin(aa), h + noise * 0.4 * rr.uniform(-1, 1))))
        rings.append(ring)
    t = None
    if top is not None:
        t = c + rot @ Vector((0, 0, top))
    return rings_obj(name, rings, tile, top=t, urep=urep, uv_fn=uv_fn)


parts = []
NMAIN = 10
MAIN_ANG = [2 * math.pi * (k + 0.5) / NMAIN for k in range(NMAIN)]

# --- Stem: fibrous, twisting, flaring at the base into one buttress per main root.
stem_prof = [(1.0, 0.55, 0.15), (1.95, 0.95, 0.36), (2.2, 1.45, 0.32), (1.7, 2.3, 0.2), (1.3, 3.2, 0.1),
             (1.15, 4.1, 0.05), (1.3, 4.9, 0.02), (1.6, 5.25, 0.0)]
# lobes peak where cos(10a) = -1, i.e. at MAIN_ANG; negative amp gives that.
stem = lathe('Stem', [(r, h, -a) for r, h, a in stem_prof], 30, 'flesh', (0, 0, 0), 0.03, 2, lobes=NMAIN,
             top=5.3, twist=0.0)
parts.append(stem)
# close the underside so it reads solid from low angles
for o in [rings_obj('StemBase', [[Vector((1.0 * (1 + 0.15 * math.cos(NMAIN * a + math.pi)) * math.cos(a),
                                          1.0 * (1 + 0.15 * math.cos(NMAIN * a + math.pi)) * math.sin(a), 0.55))
                                   for a in [2 * math.pi * k / 30 for k in range(30)]],
                                  [Vector((0.5 * math.cos(a), 0.5 * math.sin(a), 0.42)) for a in
                                   [2 * math.pi * k / 30 for k in range(30)]]], 'myc', top=(0, 0, 0.4))]:
    for p in o.data.polygons:
        p.flip()
    parts.append(o)

# --- Cap: broad weathered dome with an overhanging, slightly wavy rim; glowing gills beneath.
CAP_C = Vector((0.0, 0.0, 5.15))
CAP_TILT = (0.05, -0.07)
cap_prof = [(3.45, -0.42), (3.9, -0.12), (4.02, 0.28), (3.7, 0.95), (2.95, 1.55), (1.85, 2.0), (0.7, 2.2)]


def cap_uv(co):
    """Polar map from the cap crown so the warts are not smeared down the steep sides."""
    d = co - CAP_C
    h = math.hypot(d.x, d.y)
    phi = math.atan2(h, d.z + 0.6)
    if h < 1e-4:
        return (0.5, 0.5)
    k = 0.48 * phi / 1.8 / h
    return (0.5 + d.x * k, 0.5 + d.y * k)


parts.append(lathe('Cap', cap_prof, 26, 'cap', CAP_C, 0.02, 3, wave=0.04, lobes=7, tilt=CAP_TILT, top=2.24,
                   uv_fn=cap_uv))
gills = lathe('Gills', [(1.45, 0.3), (2.5, 0.0), (3.47, -0.4)], 26, 'gill', CAP_C, 0.0, 3, wave=0.04, lobes=7,
              tilt=CAP_TILT, urep=4)
for p in gills.data.polygons:
    p.flip()
parts.append(gills)

rot_cap = mathutils.Euler((CAP_TILT[0], CAP_TILT[1], 0)).to_matrix()


def cap_surface(r, a):
    """Point on top of the cap at radius r, angle a, with its outward normal (approx)."""
    for (r0, h0), (r1, h1) in zip(cap_prof[1:], cap_prof[2:]):
        if r1 <= r <= r0:
            t = (r0 - r) / (r0 - r1)
            h = h0 + (h1 - h0) * t
            break
    else:
        h = 2.2
    p = CAP_C + rot_cap @ Vector((r * math.cos(a), r * math.sin(a), h - 0.05))
    nrm = rot_cap @ Vector((math.cos(a) * r / 4.0 * 0.9, math.sin(a) * r / 4.0 * 0.9, 1.0)).normalized()
    return p, nrm


# Small mushrooms sprouting from the cap top, leaning outward, plus two glowing morel spore balls.
MINI = ((3.1, 0.55, 1.15), (3.4, 0.95, 0.8), (2.6, 0.2, 0.7), (3.0, 3.6, 1.0), (3.35, 3.25, 0.7))
for k, (r, a, s) in enumerate(MINI):
    p, nrm = cap_surface(r, a)
    nrm = (nrm + Vector((math.cos(a), math.sin(a), 0)) * 0.35).normalized()
    top = p + nrm * 0.85 * s
    parts.append(tube(f'MiniStem{k}', [p - nrm * 0.15, p + nrm * 0.42 * s + Vector((0, 0, 0.08 * s)), top],
                      0.3 * s, 0.2 * s, 6, 'flesh', lump=0.06, seed=20 + k, taper=1.0))
    tilt = (-math.asin(max(-1, min(1, nrm.y))) * 0.7, math.asin(max(-1, min(1, nrm.x))) * 0.7)
    mc = lathe(f'MiniCap{k}', [(0.5 * s, -0.22 * s), (0.85 * s, -0.08 * s), (0.82 * s, 0.14 * s), (0.5 * s, 0.38 * s)],
               10, 'cap', top, 0.03, 30 + k, wave=0.05, lobes=5, tilt=tilt, top=0.46 * s,
               uv_fn=lambda co, c=top, s=s: (0.5 + (co.x - c.x) / (2.2 * s), 0.5 + (co.y - c.y) / (2.2 * s)))
    parts.append(mc)
# Bracket fungi climbing the back of the stem.
for k, (z, ang, r, tile) in enumerate(((2.7, 2.7, 1.0, 'ruffle'), (3.5, 3.5, 0.8, 'ruffle'), (2.2, -2.5, 0.9, 'ruffle'))):
    rad = 1.55 if z < 3 else 1.2
    c = (rad * math.cos(ang), rad * math.sin(ang), z)
    parts.append(lathe(f'Shelf{k}', [(r, 0.0), (r * 0.8, 0.18)], 12, tile, c, 0.05, 10 + k, wave=0.14, lobes=4,
                       top=0.24, tilt=(0.18 * math.sin(ang), -0.18 * math.cos(ang))))

# --- Spore fan (turret): a ruffled chanterelle trumpet growing out of the stem front, glowing gills inside.
fan_rings, fan_in = [], []
FAN_PROF = ((0.75, 0.6), (0.7, 1.5), (0.85, 2.4), (1.12, 3.2), (1.5, 3.9), (2.0, 4.35))
for ri, (r, x) in enumerate(FAN_PROF):
    ring, ring_in = [], []
    for k in range(18):
        a = 2 * math.pi * k / 18
        frill = ri >= 4
        w = 1 + 0.05 * math.sin(9 * a) + (0.06 * math.sin(9 * a) if frill else 0.0) + (0.12 * math.sin(a) if frill else 0.0)
        y, z = r * w * math.cos(a), r * w * 0.72 * math.sin(a)
        xr = x + (0.14 * math.sin(9 * a + 0.6) if ri == 5 else 0.0) + (0.3 * math.sin(a) if ri >= 4 else 0.0)
        lift = 0.3 * xr
        ring.append(Vector((0.4 + xr, y, 2.85 + lift + z)))
        ring_in.append(Vector((0.4 + xr - 0.05, y * 0.9, 2.85 + lift + z * 0.9)))
    fan_rings.append(ring)
    fan_in.append(ring_in)
fan = rings_obj('Fan', fan_rings, 'ruffle', urep=3)
fan_g = rings_obj('FanGills', fan_in[2:], 'gill', urep=8, top=Vector((0.4 + 2.0, 0, 2.85 + 0.6)))
for p in fan_g.data.polygons:
    p.flip()


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name; o.data.name = name
    return o


# --- Roots: one massive root per buttress, plus smaller roots between them, all round like an uprooted tree.
# ROOTS entries: (angle, size, phase); index 1 is the size, so tail code reads ROOTS[i][1].
ROOTS = [(a, 1.0, ((k * 3) % NMAIN) / NMAIN) for k, a in enumerate(MAIN_ANG)]
ROOTS += [(2 * math.pi * k / 6 + 0.31, 0.5, (k * 0.37 + 0.2) % 1.0) for k in range(6)]
STRIDE, T, DUTY = 4.5, 48, 0.62
GN = [[(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(12)] for _ in ROOTS]
SUB_TIPS = []  # ground points of planted sub-roots for the current pose (soil rings)


def root_pose(i, f):
    a, sz, ph = ROOTS[i]
    p = (f / T + ph) % 1.0
    if p < DUTY:
        return STRIDE / 2 - STRIDE * p / DUTY, -0.9, 0.0
    s = (p - DUTY) / (1 - DUTY)
    e = s * s * (3 - 2 * s)
    return -STRIDE / 2 + STRIDE * e, -0.9 + (1.0 + 2.6 * sz) * math.sin(math.pi * s), math.sin(math.pi * s)


def tip_point(i, bx, rel, tz):
    a, sz, _ = ROOTS[i]
    reach = 6.6 if sz >= 1 else 4.6
    return Vector((bx + reach * 1.08 * math.cos(a) + rel, reach * math.sin(a), tz))


def make_root(i, bx, rel, tz, lift):
    a, sz, _ = ROOTS[i]
    u = Vector((math.cos(a), math.sin(a), 0))
    perp = Vector((-u.y, u.x, 0))
    hr, hz = (2.0, 1.25) if sz >= 1 else (1.55, 1.0)
    hip = Vector((bx, 0, 0)) + u * hr + Vector((0, 0, hz))
    tip = tip_point(i, bx, rel, tz)
    # leaves the buttress outward and up, arches, then drives (near) vertically into the ground
    c1 = hip + u * 1.7 * sz + Vector((0, 0, 0.7 * sz + 0.6 * lift))
    c2 = tip + Vector((0, 0, 2.0 * sz + 0.8 * lift)) - u * 0.6 * sz
    n = 10 if sz >= 1 else 7
    pts = []
    for k in range(n):
        t = k / (n - 1)
        p = bezier(hip, c1, c2, tip, t)
        gx, gz = GN[i][k]
        w = math.sin(math.pi * t) * 0.28 * sz
        pts.append(p + perp * gx * w + Vector((0, 0, gz * w * 0.6)))
    objs = [tube(f'Root{i}', pts, 0.95 * sz, 0.06, 7 if sz >= 1 else 5, 'myc', twist=1.6, lump=0.09,
                 seed=100 + i, taper=0.85)]
    # Sub-roots fork off the arch and dive into the earth beside the main tip (or dangle when lifted).
    planted = tz < 0
    for j, (tt, sd) in enumerate(((0.55, 1), (0.72, -1)) if sz >= 1 else ((0.62, 1),)):
        k = int(tt * (n - 1))
        b = pts[k]
        gx = GN[i][8 + j][0]
        end_ground = Vector((b.x, b.y, 0)) + perp * sd * (0.9 + 0.3 * gx) * (sz + 0.3) + u * 0.5
        if planted:
            end = Vector((end_ground.x, end_ground.y, -0.6))
            SUB_TIPS.append((Vector((end.x, end.y, 0)), 0.45 * sz))
        else:
            end = b + perp * sd * 0.8 * sz + Vector((0, 0, -1.4 * sz))
        mid = (b + end) / 2 + perp * sd * 0.35 * sz + Vector((0, 0, 0.35 * sz))
        objs.append(tube(f'Sub{i}_{j}', [b, mid, end], 0.36 * sz, 0.03, 5, 'myc', twist=1.0, lump=0.1,
                         seed=200 + i * 3 + j, taper=1.2))
    if not planted and tz > -0.2:  # tip torn free: frayed rootlets dangle from it
        d0 = (pts[-1] - pts[-2]).normalized()
        for k in range(4):
            dd = (d0 * 0.6 + Vector((GN[i][k][0], GN[i][k][1], -1.0)) * 0.7).normalized()
            ln = (0.5 + 0.35 * k / 3) * (sz + 0.4)
            q = pts[-2 - (k % 2)]
            cv = perp * 0.25 * GN[i][k][0] * ln
            objs.append(tube(f'Fray{i}_{k}', [q, q + dd * ln * 0.35 + cv, q + dd * ln * 0.7 - cv,
                                              q + dd * ln + Vector((0, 0, -0.2)) + cv * 0.5],
                             0.07 * (sz + 0.3), 0.015, 3, 'myc', seed=300 + k, taper=1.0))
    return objs


body = join(parts, 'Body')
fan_obj = join([fan, fan_g], 'SporeFan')
static_roots = []
for i in range(len(ROOTS)):
    rel, tz, lift = root_pose(i, 0)
    static_roots += make_root(i, 0.0, rel, tz, lift)
roots_obj = join(static_roots, 'Roots')
root = bpy.data.objects.new('Myco_Crawler', None)
scene.collection.objects.link(root)
for o in (body, fan_obj, roots_obj):
    o.parent = root

tris = 0
for o in (body, fan_obj, roots_obj):
    o.data.calc_loop_triangles()
    print('TRIS', o.name, len(o.data.loop_triangles))
    tris += len(o.data.loop_triangles)
print('TRIANGLES', tris)
assert tris <= 5000, tris
bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=True, export_yup=True)

if not render_dir:
    sys.exit(0)

# ---------------- render setup ----------------
world = bpy.data.worlds.new('W'); scene.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes['Background'].inputs['Color'].default_value = (0.36, 0.5, 0.78, 1)
wn.nodes['Background'].inputs['Strength'].default_value = 0.8
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
sun.data.energy = 5.0; sun.data.color = (1.0, 0.88, 0.7); sun.data.angle = math.radians(4)
sun.rotation_euler = (math.radians(52), math.radians(10), math.radians(-30))
scene.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=300)
ground = bpy.context.object
gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
gt = gm.node_tree
gb = gt.nodes['Principled BSDF']
n1 = gt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.3; n1.inputs['Detail'].default_value = 6
n2 = gt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 9.0; n2.inputs['Detail'].default_value = 6
ramp = gt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.65
ramp.color_ramp.elements[0].color = (0.08, 0.06, 0.03, 1)
ramp.color_ramp.elements[1].color = (0.12, 0.22, 0.04, 1)
mix = gt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs['Fac'].default_value = 0.5
gt.links.new(n1.outputs['Fac'], ramp.inputs['Fac'])
gt.links.new(ramp.outputs['Color'], mix.inputs['Color1']); gt.links.new(n2.outputs['Color'], mix.inputs['Color2'])
gt.links.new(mix.outputs['Color'], gb.inputs['Base Color'])
bump = gt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.5
gt.links.new(n2.outputs['Fac'], bump.inputs['Height']); gt.links.new(bump.outputs['Normal'], gb.inputs['Normal'])
gb.inputs['Roughness'].default_value = 1.0
ground.data.materials.append(gm)


def flat_mat(name, col, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = col; b.inputs['Roughness'].default_value = 1.0
    b.inputs['Alpha'].default_value = alpha
    return m


dirt = flat_mat('Dirt', (0.075, 0.05, 0.03, 1))
dirt_lt = flat_mat('DirtLight', (0.075, 0.055, 0.032, 1))
dust = flat_mat('Dust', (0.3, 0.24, 0.16, 1), 0.3)
scar = flat_mat('Scar', (0.035, 0.022, 0.013, 1))

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.use_denoising = True
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
scene.collection.objects.link(cam)
scene.camera = cam


def aim(loc, tgt, lens):
    cam.location = loc
    d = [t - l for t, l in zip(tgt, loc)]
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    cam.data.lens = lens


def blob(name, c, r, material, seed, squash=1.0, sub=2, jag=0.16):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=r, location=c)
    o = bpy.context.object
    rr = random.Random(seed)
    for v in o.data.vertices:
        v.co *= rr.uniform(1 - jag, 1 + jag)
        v.co.z *= squash
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.materials.append(material)
    return o


def soil_ring(c, sz, seed):
    """Torn earth where a root enters the ground: a heaved mound, a dark hole and broken clods."""
    out = []
    rr = random.Random(seed)
    out.append(blob('Mound', (c.x, c.y, 0.0), 0.65 * sz + 0.4, dirt_lt, seed, squash=0.18, jag=0.35))
    out.append(blob('Hole', (c.x, c.y, 0.08), 0.45 * sz + 0.2, scar, seed + 1, squash=0.15))
    for k in range(9):
        a = 2 * math.pi * k / 9 + rr.uniform(-0.4, 0.4)
        d = (0.8 + rr.uniform(0, 0.6)) * (0.5 + 0.6 * sz)
        out.append(blob('Clod', (c.x + d * math.cos(a), c.y + d * math.sin(a), 0.05),
                        rr.uniform(0.1, 0.24) * (0.6 + 0.6 * sz), dirt, seed * 7 + k, squash=0.7, sub=1))
    return out


def ground_set(bx, f_seed):
    out = []
    for i in range(len(ROOTS)):
        rel, tz, lift = root_pose(i, F_NOW[0])
        if tz < 0:
            out += soil_ring(tip_point(i, bx, rel, 0), ROOTS[i][1], 500 + i * 31 + f_seed)
    for c, s in SUB_TIPS:
        out += soil_ring(c, s, int(abs(c.x * 97 + c.y * 13)) + 9000)
    return out


F_NOW = [0]
if not anim_dir:
    live = ground_set(0.0, 0)
    scene.cycles.samples = 48
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    for name, loc, tgt, lens in (('mycrawl_front34', (17, -17, 6.5), (0.5, 0, 2.8), 30),
                                 ('mycrawl_side', (0.5, -24, 3.2), (0.5, 0, 3.0), 30),
                                 ('mycrawl_rts', (14, -14, 24), (0, 0, 1.5), 36)):
        aim(loc, tgt, lens)
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)
    sys.exit(0)

# ---------------- crawl animation ----------------
bpy.data.objects.remove(roots_obj, do_unlink=True)
N = 96
v = STRIDE / (DUTY * T)
X0 = -v * N / 2
events = []  # (frame, x, y, sz, kind, i)
for f in range(-60, N):
    for i in range(len(ROOTS)):
        _, tz0, _ = root_pose(i, f - 1)
        rel, tz, _ = root_pose(i, f)
        if (tz0 < 0 <= tz) or (tz0 >= 0 > tz):
            c = tip_point(i, X0 + v * f, rel, 0)
            events.append((f, c.x, c.y, ROOTS[i][1], 'rip' if tz >= 0 else 'plunge', i))
scene.cycles.samples = 20
scene.render.resolution_x, scene.render.resolution_y = 960, 540
aim((3, -30, 9.0), (0, 0, 2.2), 26)
live = []
for f in range(N):
    for o in live:
        bpy.data.objects.remove(o, do_unlink=True)
    live = []
    SUB_TIPS.clear()
    F_NOW[0] = f
    bx = X0 + v * f
    sway = math.sin(2 * math.pi * f / (T / 2))
    root.location = (bx, 0, 0.1 * sway)
    root.rotation_euler = (0.025 * math.sin(2 * math.pi * f / T), 0.02 * sway, 0)
    for i in range(len(ROOTS)):
        rel, tz, lift = root_pose(i, f)
        live += make_root(i, bx, rel, tz, lift)
    live += ground_set(bx, int((f + 1000) // T))
    for (e, ex, ey, sz, kind, i) in events:
        age = f - e
        if age < 0:
            continue
        if kind == 'rip':  # the hole a root tore out stays behind as a scar
            live.append(blob('Scar', (ex, ey, 0.0), 0.6 * sz + 0.35, scar, e * 13 + i, squash=0.06, sub=1))
        if age < 20:
            rr = random.Random(e * 101 + i)
            cnt = 18 if kind == 'rip' else 10
            for k in range(cnt):
                vx, vy = rr.uniform(-2.2, 2.2), rr.uniform(-2.2, 2.2)
                vz = rr.uniform(4, 8.5) if kind == 'rip' else rr.uniform(2, 4.5)
                t = age / 24
                z = 0.1 + vz * t - 9.8 * t * t / 2
                if z > 0:
                    live.append(blob('Chunk', (ex + vx * t, ey + vy * t, z), rr.uniform(0.08, 0.25) * (0.6 + 0.6 * sz),
                                     dirt, e * 7 + k, sub=1))
            if age < 16:
                for k in range(3):  # dust puff that swells and fades
                    rad = (0.5 + age * 0.11) * (0.6 + 0.6 * sz)
                    live.append(blob('Dust', (ex + rr.uniform(-0.6, 0.6), ey + rr.uniform(-0.6, 0.6), 0.3 + age * 0.05),
                                     rad, dust, e * 3 + k, sub=1))
    scene.render.filepath = f'{anim_dir}/f_{f:04d}.png'
    bpy.ops.render.render(write_still=True)
