"""Pieces for David's barrage beat (2026-11-13): the Terran triangle shield, a Terran flagship
punched through by an Arcadian laser, and the broadside battleship's blue comet cannonballs.

    python tools/cinematics/opening/barrage_pieces.py --piece=tshield|flagship|comet|all --out=DIR

Builders (importable): tri_shield(), comet(), gold_beam(), flagship_wound().
"""
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402  (pip bpy: import after bpy)
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import new_pieces as NP  # noqa: E402  (also sets up common / forge paths)
import common as C  # noqa: E402
import forge as F  # noqa: E402
import ships as base  # noqa: E402
import ships_hd as hd  # noqa: E402
import terran_fleet as T  # noqa: E402

BLUE_DEEP = (0.0, 0.1, 0.85)
BLUE_LIGHT = (0.5, 0.82, 1.0)


class _NT:
    """Tiny node-building helper."""

    def __init__(self, mat):
        self.nt = mat.node_tree

    def node(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            if k in ('operation', 'feature', 'data_type'):
                setattr(n, k, v)
            else:
                self.set(n.inputs[k], v)
        return n

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.nt.nodes.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(n.inputs[i], v)
        return n.outputs[0]

    def maprange(self, v, a, b, c, d):
        n = self.nt.nodes.new('ShaderNodeMapRange')
        self.set(n.inputs[0], v)
        for i, x in enumerate((a, b, c, d)):
            n.inputs[i + 1].default_value = x
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.nt.nodes.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a if not isinstance(a, tuple) else (*a, 1))
        self.set(n.inputs[7], b if not isinstance(b, tuple) else (*b, 1))
        return n.outputs[2]


def _new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    for n in list(m.node_tree.nodes):
        m.node_tree.nodes.remove(n)
    return m, _NT(m)


# ================================================================== Terran triangle shield
def tri_shield(size, hits=(), hole=None, name='TShield', subdiv=3):
    """Ellipsoid shield of flat translucent blue triangles: deep blue and more solid along each
    triangle's edges, pale and clear in its middle. hits: unit-sphere directions of impacts (those
    triangles darken and a bright ring runs out along the edges). hole: direction of a punched
    hole (clear centre, white-hot rim)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    faces = list(bm.faces)
    inner_verts = set()
    for f in faces:
        for v in f.verts:
            pass
    bmesh.ops.inset_individual(bm, faces=faces, thickness=0.042 * (2 ** (3 - subdiv)), depth=0.0,
                               use_even_offset=True)
    for f in faces:                       # the original faces are now the inner triangles
        inner_verts.update(v.index for v in f.verts)
    bm.verts.index_update()
    inner_verts = {v.index for f in faces for v in f.verts}
    bm.to_mesh(me)
    bm.free()
    at = me.attributes.new('mid', 'FLOAT', 'POINT')
    for v in me.vertices:
        at.data[v.index].value = 1.0 if v.index in inner_verts else 0.0
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.scale = size
    o.visible_shadow = False

    m, n = _new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    mid = n.node('ShaderNodeAttribute')
    mid.attribute_name = 'mid'
    mid = mid.outputs['Fac']
    edge = n.math('SUBTRACT', 1.0, mid)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.25)
    fres = n.math('POWER', lw.outputs['Facing'], 3.0)
    col = n.mix(mid, BLUE_DEEP, BLUE_LIGHT)
    opa = n.math('MULTIPLY_ADD', n.math('POWER', edge, 1.6), 0.6, 0.03)
    opa = n.math('MULTIPLY_ADD', fres, 0.25, opa)
    strength = n.math('MULTIPLY_ADD', edge, 1.2, 0.8)
    for h in hits:                        # darker, more solid triangles + a ring along the edges
        d = n.node('ShaderNodeVectorMath', operation='DISTANCE')
        n.set(d.inputs[0], tc.outputs['Object'])
        d.inputs[1].default_value = tuple(Vector(h).normalized())
        dist = d.outputs['Value']
        zone = n.maprange(dist, 0.05, 0.42, 1.0, 0.0)
        col = n.mix(n.math('MULTIPLY', zone, 0.85), col, (0.0, 0.03, 0.5))
        opa = n.math('MULTIPLY_ADD', zone, 0.4, opa)
        ring = n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', dist, 0.3)), 0.0, 0.05, 1.0, 0.0)
        strength = n.math('MULTIPLY_ADD', n.math('MULTIPLY', ring, edge), 9.0, strength)
        flash = n.maprange(dist, 0.0, 0.07, 18.0, 0.0)
        strength = n.math('ADD', strength, flash)
        opa = n.math('ADD', opa, n.maprange(dist, 0.0, 0.07, 1.0, 0.0))
    if hole is not None:                  # punched hole: clear inside, white-hot torn rim
        d = n.node('ShaderNodeVectorMath', operation='DISTANCE')
        n.set(d.inputs[0], tc.outputs['Object'])
        d.inputs[1].default_value = tuple(Vector(hole).normalized())
        dist = d.outputs['Value']
        zone = n.maprange(dist, 0.06, 0.4, 1.0, 0.0)
        col = n.mix(n.math('MULTIPLY', zone, 0.9), col, (0.0, 0.03, 0.5))
        opa = n.math('MULTIPLY_ADD', zone, 0.4, opa)
        rim = n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', dist, 0.075)), 0.0, 0.025, 1.0, 0.0)
        strength = n.math('MULTIPLY_ADD', rim, 25.0, strength)
        opa = n.math('ADD', opa, rim)
        inside = n.math('LESS_THAN', dist, 0.065)
        opa = n.math('MULTIPLY', opa, n.math('SUBTRACT', 1.0, inside))
    opa = n.math('MINIMUM', opa, 1.0)
    em = n.node('ShaderNodeEmission')
    n.set(em.inputs['Color'], col)
    n.set(em.inputs['Strength'], strength)
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], opa)
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], em.outputs[0])
    n.set(out.inputs['Surface'], mx.outputs[0])
    o.data.materials.append(m)
    return o


def ellipsoid_hit(center, size, p0, d):
    """Where the ray p0 + t d enters the ellipsoid (world point, unit-sphere direction)."""
    c, s = Vector(center), Vector(size)
    q = Vector(((p0[0] - c.x) / s.x, (p0[1] - c.y) / s.y, (p0[2] - c.z) / s.z))
    dd = Vector((d[0] / s.x, d[1] / s.y, d[2] / s.z))
    a, b, cc = dd.dot(dd), 2 * q.dot(dd), q.dot(q) - 1
    t = (-b - math.sqrt(max(b * b - 4 * a * cc, 0))) / (2 * a)
    u = q + dd * t
    return Vector(p0) + Vector(d) * t, u


# ================================================================== comet cannonball
def comet(name='Comet', scale=1.0, seed=1):
    """Giant blue energy ball flying +X: white-hot core, blue halo, long streaky tail toward -X
    and a few trailing sparks. ~2 units across at scale 1, tail ~16 long."""
    k = scale
    rnd = random.Random(seed)
    core = C.uv_sphere(name, 1.0 * k, seg=(32, 16), mat=C.emit_mat(name + 'Core', (0.78, 0.93, 1.0), 35.0))
    core.visible_shadow = False
    # halo
    m, n = _new_mat(name + 'Halo')
    out = n.node('ShaderNodeOutputMaterial')
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    glow = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 3.5)
    em = n.node('ShaderNodeEmission', Color=(0.25, 0.6, 1.0, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', glow, 3.0))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    n.set(out.inputs['Surface'], add.outputs[0])
    halo = C.uv_sphere(name + 'Halo', 2.4 * k, seg=(32, 16), mat=m)
    halo.parent = core
    halo.visible_shadow = False
    # tail: open cone behind the head, streaks along its length, fading out
    L = 16.0 * k
    base._faction('terran')
    tail_o = F.lathe([(0.0, 0.6 * k), (1.15 * k, 0.0), (1.5 * k, -0.25 * L), (1.0 * k, -0.6 * L), (0.0, -L)], 32,
                     'glow')
    tail = base._join([tail_o], name + 'Tail')
    tail.rotation_euler = (0, math.radians(90), 0)       # lathe axis (-z) -> -X
    tail.parent = core
    m, n = _new_mat(name + 'TailMat')
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    sep = n.node('ShaderNodeSeparateXYZ')
    n.set(sep.inputs[0], tc.outputs['Object'])
    along = n.maprange(sep.outputs[2], -L, 0.0, 0.0, 1.0)       # 1 at the head, 0 at the tail end
    st = n.node('ShaderNodeVectorMath', operation='MULTIPLY')
    n.set(st.inputs[0], tc.outputs['Object'])
    st.inputs[1].default_value = (2.2 / k, 2.2 / k, 0.12 / k)
    nz = n.node('ShaderNodeTexNoise', Scale=1.0, Detail=5.0)
    n.set(nz.inputs['Vector'], st.outputs[0])
    streak = n.maprange(nz.outputs['Fac'], 0.35, 0.75, 0.0, 1.0)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.4)
    body = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 2.5)
    s = n.math('MULTIPLY', n.math('POWER', along, 1.8), n.math('MULTIPLY_ADD', streak, 0.8, 0.25))
    s = n.math('MULTIPLY', n.math('MULTIPLY', s, body), 9.0)
    ramp = n.node('ShaderNodeValToRGB')
    n.set(ramp.inputs[0], along)
    ramp.color_ramp.elements[0].color = (0.05, 0.15, 0.9, 1)
    ramp.color_ramp.elements[1].color = (0.7, 0.9, 1.0, 1)
    e = ramp.color_ramp.elements.new(0.6)
    e.color = (0.2, 0.55, 1.0, 1)
    em = n.node('ShaderNodeEmission')
    n.set(em.inputs['Color'], ramp.outputs[0])
    n.set(em.inputs['Strength'], s)
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    n.set(out.inputs['Surface'], add.outputs[0])
    tail.data.materials.clear()
    tail.data.materials.append(m)
    tail.visible_shadow = False
    # sparks
    sm = C.emit_mat(name + 'Spark', (0.55, 0.85, 1.0), 20.0)
    for i in range(6):
        x = -rnd.uniform(1.5, 0.7 * L)
        r = rnd.uniform(0.6, 2.0) * k * (1 + abs(x) / L)
        a = rnd.uniform(0, 2 * math.pi)
        sp = C.uv_sphere(f'{name}Spark{i}', 1.0, seg=(8, 5), mat=sm, scale=(0.9 * k, 0.04 * k, 0.04 * k))
        sp.location = (x, r * math.cos(a), r * math.sin(a))
        sp.parent = core
        sp.visible_shadow = False
    lt = bpy.data.objects.new(name + 'Light', bpy.data.lights.new(name + 'Light', 'POINT'))
    bpy.context.scene.collection.objects.link(lt)
    lt.data.energy = 4000 * k * k
    lt.data.color = (0.4, 0.7, 1.0)
    lt.data.shadow_soft_size = 1.0 * k
    lt.parent = core
    return core


def _halo_mat(name, col, k):
    m, n = _new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 3.0)
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', g, k))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


def aim(obj, d):
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector(d).to_track_quat('X', 'Z')


# ================================================================== Arcadian gold laser
def gold_beam(p0, p1, r=0.55, name='GoldBeam'):
    d = Vector(p1) - Vector(p0)
    core = C.uv_sphere(name, 1.0, seg=(24, 12), mat=C.emit_mat(name + 'Core', (1.0, 0.85, 0.5), 40.0),
                       scale=(d.length / 2, r * 0.45, r * 0.45))
    glow_m, n = _new_mat(name + 'Glow')
    out = n.node('ShaderNodeOutputMaterial')
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 2.0)
    em = n.node('ShaderNodeEmission', Color=(1.0, 0.6, 0.12, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', g, 8.0))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    n.set(out.inputs['Surface'], add.outputs[0])
    glow = C.uv_sphere(name + 'Halo', 1.0, seg=(32, 16), mat=glow_m, scale=(d.length / 2, r * 2.2, r * 2.2))
    for o in (core, glow):
        o.location = (Vector(p0) + Vector(p1)) / 2
        aim(o, d)
        o.visible_shadow = False
    return core


def flagship_wound(ship, entry, exit_, d, rnd, normal=None):
    """Glowing molten hole where the beam enters, a blast of sparks/debris where it exits."""
    hot = C.emit_mat('Molten', (1.0, 0.28, 0.03), 4.0)
    base._faction('terran')
    ring = F.lathe([(1.0, 0.25), (1.9, 0.0), (2.4, -0.05), (1.5, 0.15)], 24, 'glow')
    rim = base._join([ring], 'EntryGlow')
    rim.data.materials.clear()
    rim.data.materials.append(hot)
    rim.location = entry
    rim.rotation_mode = 'QUATERNION'
    rim.rotation_quaternion = Vector(normal if normal is not None else -Vector(d)).to_track_quat('Z', 'Y')
    flare = C.uv_sphere('ExitFlare', 1.0, seg=(24, 12), mat=_halo_mat('ExitMat', (1.0, 0.55, 0.15), 6.0),
                        scale=(3.0, 3.0, 3.0))
    flare.location = Vector(exit_) + Vector(d) * 1.2
    base._faction('terran')
    m = F.mark()
    for i in range(22):     # debris thrown out of the exit wound
        p = Vector(exit_) + Vector(d) * rnd.uniform(2, 16) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                                                                     rnd.uniform(-1, 1))) * rnd.uniform(1, 5)
        F.rock(tuple(p), rnd.uniform(0.2, 0.9), 'dark', seed=i)
    deb = base._join(F.since(m), 'Debris')
    sm = C.emit_mat('Spark', (1.0, 0.6, 0.2), 18.0)
    for i in range(26):
        p = Vector(exit_) + Vector(d) * rnd.uniform(1, 12) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                                                                     rnd.uniform(-1, 1))) * rnd.uniform(0.5, 4)
        s = C.uv_sphere(f'Sp{i}', 1.0, seg=(6, 4), mat=sm, scale=(0.5, 0.05, 0.05))
        s.location = p
        aim(s, Vector(p) - Vector(exit_))
        s.visible_shadow = False
    for o in (rim, flare):
        o.visible_shadow = False
    for p, nm in ((entry, 'EntryLight'), (flare.location, 'ExitLight')):
        lt = bpy.data.objects.new(nm, bpy.data.lights.new(nm, 'POINT'))
        bpy.context.scene.collection.objects.link(lt)
        lt.data.energy = 2.5e4
        lt.data.color = (1.0, 0.55, 0.2)
        lt.data.shadow_soft_size = 1.5
        lt.location = Vector(p) - Vector(d) * 2.0 if nm == 'EntryLight' else p
    return deb


# ================================================================== stills
def still(piece, out):
    tmp = os.path.join(out, '_views')
    os.makedirs(tmp, exist_ok=True)
    F.begin('terran')
    shots = []
    rnd = random.Random(5)
    if piece == 'tshield':
        C.OS.world()
        ship = T.terran_frigate_v2()
        for p in ship.data.polygons:
            p.use_smooth = True
        T.neon_lines(ship)
        dx, dy, dz = ship.dimensions
        size = (dx * 0.62, dy * 0.7 + 2, dz * 0.95 + 1.5)
        cen = Vector(ship.matrix_world @ (sum((Vector(b) for b in ship.bound_box), Vector()) / 8))
        sh = tri_shield(size, hits=[(0.55, -0.75, 0.35), (-0.4, -0.85, -0.2)])
        sh.location = cen
        NP._studio()
        for v, p, t, lens in [('hero', (30, -32, 12), (0, 0, 0), 35), ('side', (4, -42, 3), (0, 0, 0), 40)]:
            NP._cam(Vector(p) + cen, cen + Vector(t), lens=lens)
            shots.append(os.path.join(tmp, f'tshield_{v}.png'))
            NP._render(shots[-1], samples=32)
    elif piece == 'flagship':
        C.OS.world()
        ship, _ = hd.terran_dreadnought()
        for p in ship.data.polygons:
            p.use_smooth = True
        T.neon_lines(ship)
        bpy.context.view_layer.update()
        dx, dy, dz = ship.dimensions
        cen = sum((Vector(b) for b in ship.bound_box), Vector()) / 8
        size = (dx * 0.68, dy * 0.95 + 4, dz * 1.3 + 4)
        src = Vector((-50, -115, 70))
        target = cen + Vector((2.0, 0, 0.3))
        d = (target - src).normalized()
        ok, entry, nrm, _ = ship.ray_cast(src, d)
        far = target + d * 200
        ok2, exit_, _, _ = ship.ray_cast(far, -d)
        sp, u = ellipsoid_hit(cen, size, src, d)
        sh = tri_shield(size, hole=u)
        sh.location = cen
        gold_beam(src, far)
        flagship_wound(ship, entry if ok else target, exit_ if ok2 else target, d, rnd, nrm if ok else None)
        NP._studio()
        for v, p, t, lens in [('hero', (26, -44, 16), (0, 0, 0), 30),
                              ('close', None, None, 35)]:
            if p is None:
                p = entry + Vector(nrm) * 12 + Vector((10, -4, 4))
                t = entry
            else:
                p, t = cen + Vector(p), cen + Vector(t)
            NP._cam(p, t, lens=lens)
            shots.append(os.path.join(tmp, f'flag_{v}.png'))
            NP._render(shots[-1], samples=32)
    elif piece == 'comet':
        C.OS.world()
        ship, muzzles = T.broadside_battleship()
        for p in ship.data.polygons:
            p.use_smooth = True
        T.neon_lines(ship)
        fire = Vector((0, -1, 0))
        for i, (mz, dist) in enumerate(zip(muzzles, (5, 34, 70))):
            c = comet(f'Comet{i}', scale=1.8, seed=i)
            c.location = Vector(mz) + fire * dist
            aim(c, fire)
        flash = T.muzzle_flash('Flash', scale=1.6, bolt=False)
        flash.location = muzzles[0]
        aim(flash, fire)
        NP._studio(0.8)
        hero = C.OS  # noqa
        c1 = Vector(muzzles[1]) + fire * 34
        for v, p, t, lens in [('hero', c1 + Vector((22, -14, 6)), c1 + Vector((-4, 2, 0)), 35),
                              ('wide', (60, -95, 30), (0, -30, 0), 30)]:
            NP._cam(p, t, lens=lens)
            shots.append(os.path.join(tmp, f'comet_{v}.png'))
            NP._render(shots[-1], samples=32)
    return shots


if __name__ == '__main__':
    args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
    out = args.get('out', '/tmp/barrage')
    names = {'tshield': '06-terran-shield', 'flagship': '07-flagship-laser-hit', 'comet': '08-comet-barrage'}
    todo = list(names) if args.get('piece', 'all') == 'all' else args['piece'].split(',')
    for pc in todo:
        shots = still(pc, out)
        NP.bloom_sheet(shots, os.path.join(out, names[pc] + '.jpg'))
        print('DONE', pc, flush=True)
