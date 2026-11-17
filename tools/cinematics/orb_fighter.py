"""Arcadian anti-fighter "Orb" (squid v2 variant C, detailed build, 2026-11-14, David picked the Orb).

A teardrop hull opened at the front round a glowing gold core, eight jointed legs on a collar behind it.
Every leg carries a thruster nacelle at its elbow: swept back it sprints, spun round it turns hard,
flung forward it grabs a fighter and drives harpoon tips into it.

orb_fighter(pose) builds one at the origin, nose along +X, and returns the root object. Children are the
exhaust plumes (named *Plume*) so a shot can scale/hide them. pose: 'sprint', 'turn', 'grab', 'spread'.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'opening'))
import ships as base  # noqa: E402
import arcadian_fleet as AF  # noqa: E402
import forge as F  # noqa: E402
import shard_fx as SFX  # noqa: E402

L_, R_ = 7.5, 1.7
X0, X1 = L_ * 0.55, -L_ * 0.45          # nose rim at +X0, tail at X1
RING = 1.9
SEG = (3.0, 3.4, 3.0)
GOLD = (1.0, 0.62, 0.18)
HOTG = (1.0, 0.9, 0.7)


def _ax_ring(x, r, zone, w=0.08, sides=32):
    F.tube((x - w, 0, 0), (x + w, 0, 0), [(0, r), (0.5, r * 1.012), (1, r)], sides, zone, caps=False)


def _body():
    # main hull: teardrop, open at the front
    prof = [(0, R_ * 0.22), (0.12, R_ * 0.62), (0.32, R_ * 0.92), (0.6, R_), (0.84, R_ * 0.93), (1.0, R_ * 0.6)]
    F.tube((X1, 0, 0), (X0, 0, 0), prof, 24, 'shell', caps=False, sharp=35)
    F.tube((X1 + 0.05, 0, 0), (X0 - 0.05, 0, 0), [(t, r * 0.94) for t, r in prof], 24, 'under', caps=False)

    def rad_at(x):
        t = (x - X1) / (X0 - X1)
        for (ta, ra), (tb, rb) in zip(prof, prof[1:]):
            if ta <= t <= tb:
                return ra + (rb - ra) * (t - ta) / (tb - ta)
        return prof[-1][1]
    # raised armour bands and glowing seams between the hull plates
    for x in (X1 + 1.3, -0.9, 0.9, X0 - 0.9):
        _ax_ring(x, rad_at(x) * 1.03, 'bronze', 0.12)
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        pts = [(x, math.cos(a) * rad_at(x) * 1.012, math.sin(a) * rad_at(x) * 1.012)
               for x in [X1 + 0.6 + i * (X0 - X1 - 1.0) / 11 for i in range(12)]]
        F.sweep(pts, [(0.035, 0.035)] * 12, 'glow', sides=4)
    # rim of the open mouth: heavy lip, glowing inner ring, eight iris blades curling in front of the core
    F.tube((X0 - 0.25, 0, 0), (X0 + 0.12, 0, 0), [(0, R_ * 0.66), (0.5, R_ * 0.66), (1, R_ * 0.58)], 32, 'bronze')
    _ax_ring(X0 + 0.02, R_ * 0.55, 'glow', 0.05)
    for k in range(8):
        a = 2 * math.pi * k / 8
        rv = Vector((0, math.cos(a), math.sin(a)))
        tv = Vector((0, -math.sin(a), math.cos(a)))
        base_p = Vector((X0 - 0.1, 0, 0)) + rv * R_ * 0.6
        pts = [base_p, base_p + Vector((0.5, 0, 0)) + rv * 0.05 + tv * 0.15,
               base_p + Vector((0.95, 0, 0)) - rv * 0.35 + tv * 0.35,
               base_p + Vector((1.15, 0, 0)) - rv * 0.75 + tv * 0.4]
        F.sweep([tuple(p) for p in pts], [(0.22, 0.05), (0.2, 0.05), (0.12, 0.04), (0.02, 0.02)], 'bronze',
                sides=4, up=tuple(rv))
    # the core: gold orb with an inner lattice and a cage of six ribs
    cx = X0 - R_ * 0.45
    F.orb((cx, 0, 0), R_ * 0.6, 'core', seg=(32, 18))
    for k in range(6):
        a = math.radians(60 * k)
        off = Vector((0, math.cos(a), math.sin(a)))
        pts = [tuple(Vector((cx + R_ * 0.6 * math.cos(t), 0, 0)) + off * R_ * 0.68 * math.sin(t))
               for t in [i * math.pi / 10 for i in range(1, 8)]]
        F.sweep(pts, [(0.05, 0.05)] * 7, 'bronze', sides=4)
    # crescent fins: dorsal and ventral blades sweeping back over the hull
    for sgn in (1, -1):
        F.crescent((X1 + 1.4, 0, 0), 3.0, math.radians(15), math.radians(160), 0.6, 0.08, 'bronze', n=18, plane='xz',
                   sq=(1.1, sgn * 0.95))
        F.crescent((X1 + 1.4, 0, 0), 2.85, math.radians(30), math.radians(140), 0.12, 0.1, 'glow', n=14,
                   plane='xz', sq=(1.1, sgn * 0.95))
    # tail drive: flared bell with a glowing throat and three stabiliser vanes
    F.tube((X1 - 0.9, 0, 0), (X1 + 0.3, 0, 0), [(0, R_ * 0.55), (0.35, R_ * 0.42), (1, R_ * 0.3)], 20, 'bronze',
           caps=False)
    F.tube((X1 - 0.75, 0, 0), (X1 + 0.2, 0, 0), [(0, R_ * 0.48), (1, R_ * 0.25)], 20, 'glow', caps=False)
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.pi / 2
        o = Vector((0, math.cos(a), math.sin(a)))
        pts = [tuple(Vector((X1 + 0.9, 0, 0)) + o * R_ * 0.5), tuple(Vector((X1 - 0.2, 0, 0)) + o * R_ * 0.9),
               tuple(Vector((X1 - 0.8, 0, 0)) + o * R_ * 0.85)]
        F.sweep(pts, [(0.04, 0.3), (0.05, 0.35), (0.02, 0.1)], 'bronze', sides=4, up=tuple(o))
    # collar the legs hang from: thick ring, glowing groove, sixteen studs, eight hinge brackets
    F.tube((-0.42, 0, 0), (0.42, 0, 0), [(0, RING * 0.92), (0.5, RING * 1.06), (1, RING * 0.92)], 32, 'bronze')
    F.tube((-0.48, 0, 0), (0.48, 0, 0), [(0, RING * 0.84), (1, RING * 0.84)], 32, 'glow', caps=False)
    for k in range(16):
        a = 2 * math.pi * k / 16
        F.orb((0.3, math.cos(a) * RING * 1.04, math.sin(a) * RING * 1.04), 0.09, 'pale', seg=(6, 4))
        F.orb((-0.3, math.cos(a) * RING * 1.04, math.sin(a) * RING * 1.04), 0.09, 'pale', seg=(6, 4))


def _leg_dirs(pose, k):
    if pose == 'sprint':
        return [(-0.55, 0.85, 0), (-1.0, 0.12, 0), (-1.0, -0.06, 0)]
    if pose == 'grab':
        return [(0.45, 1.0, 0), (1.0, 0.35, 0), (1.0, -0.55, 0)]
    if pose == 'spread':
        return [(0.05, 1.0, 0.1), (-0.15, 1.0, 0.15), (-0.25, 0.9, 0.2)]
    w = math.cos(2 * math.pi * k / 8)
    return [(-0.3, 1.0, 0.5), (-0.6 + 0.6 * w, 0.6 + 0.3 * w, 0.7), (-0.8 + 0.5 * w, 0.1, 0.5)]


def _segment(p, q, j, up):
    d = (q - p).normalized()
    ln = (q - p).length
    r0, r1 = (0.3, 0.25, 0.19)[j], (0.25, 0.19, 0.13)[j]
    F.tube(tuple(p), tuple(q), [(0, r0), (0.15, r0 * 1.1), (0.5, r0 * 1.15), (0.85, r1 * 1.05), (1, r1)], 10, 'shell',
           sharp=35)
    # armour sleeve over the upper half and two clamp bands
    F.tube(tuple(p + d * ln * 0.12), tuple(p + d * ln * 0.55),
           [(0, r0 * 1.12), (0.2, r0 * 1.3), (0.8, r0 * 1.25), (1, r0 * 1.1)], 10, 'bronze', sharp=35)
    for f in (0.62, 0.8):
        c = p + d * ln * f
        F.tube(tuple(c - d * 0.06), tuple(c + d * 0.06), [(0, r0 * 1.12), (1, r0 * 1.12)], 10, 'pale')
    # glowing tendon along the top of the segment
    side = d.cross(up)
    if side.length < 1e-4:
        side = d.orthogonal()
    nrm = side.normalized().cross(d).normalized()
    pts = [tuple(p + d * ln * f + nrm * (r0 * 1.0 * (1 - f) + r1 * f + 0.02)) for f in (0.08, 0.3, 0.55, 0.8, 0.95)]
    F.sweep(pts, [(0.04, 0.04)] * 5, 'glow', sides=4)
    # the joint: ball, glowing ring, clevis plates either side
    F.orb(tuple(p), r0 * 1.35, 'bronze', seg=(14, 8))
    F.tube(tuple(p - side.normalized() * r0 * 0.2), tuple(p + side.normalized() * r0 * 0.2),
           [(0, r0 * 1.45), (1, r0 * 1.45)], 16, 'glow', caps=False)
    for sgn in (-1, 1):
        c = p + side.normalized() * sgn * r0 * 1.15
        F.tube(tuple(c - side.normalized() * 0.05), tuple(c + side.normalized() * 0.05),
               [(0, r0 * 1.2), (1, r0 * 1.2)], 12, 'pale')
    return d, nrm


def _nacelle(c, d, rad):
    """Thruster nacelle at the elbow, intake forward along d, nozzle aft. Returns the nozzle exit point."""
    a, b = c + d * 1.0, c - d * 1.0
    F.tube(tuple(a), tuple(b), [(0, 0.12), (0.08, 0.3), (0.2, 0.38), (0.7, 0.36), (0.88, 0.3), (1, 0.27)], 14,
           'bronze', sharp=35)
    F.tube(tuple(a + d * 0.02), tuple(a - d * 0.12), [(0, 0.24), (1, 0.27)], 14, 'glow', caps=False)   # intake
    for f in (0.3, 0.5):
        q = a + (b - a) * f
        F.tube(tuple(q - d * 0.04), tuple(q + d * 0.04), [(0, 0.4), (1, 0.4)], 14, 'pale')
    # nozzle bell and glowing throat
    F.tube(tuple(b + d * 0.05), tuple(b - d * 0.4), [(0, 0.24), (0.5, 0.3), (1, 0.38)], 14, 'shell', caps=False)
    F.tube(tuple(b + d * 0.1), tuple(b - d * 0.32), [(0, 0.16), (1, 0.32)], 14, 'glow', caps=False)
    # two small crescent fins on the nacelle
    s = d.cross(rad).normalized()
    for sgn in (-1, 1):
        o = (rad * 0.6 + s * sgn).normalized()
        pts = [tuple(c + d * 0.6 + o * 0.3), tuple(c + o * 0.62), tuple(c - d * 0.9 + o * 0.55)]
        F.sweep(pts, [(0.02, 0.18), (0.03, 0.22), (0.01, 0.06)], 'bronze', sides=4, up=tuple(o))
    return b - d * 0.4


def _harpoon(p, d, up):
    """Long serrated spike with back-swept barbs and a glowing blood-groove."""
    side = d.cross(up)
    if side.length < 1e-4:
        side = d.orthogonal()
    side.normalize()
    top = side.cross(d).normalized()
    F.tube(tuple(p - d * 0.1), tuple(p + d * 0.35), [(0, 0.2), (0.5, 0.26), (1, 0.18)], 10, 'bronze')
    F.tube(tuple(p + d * 0.3), tuple(p + d * 2.3), [(0, 0.15), (0.6, 0.11), (0.9, 0.06), (1.0, 0.0)], 6, 'pale',
           sharp=20)
    F.sweep([tuple(p + d * f + top * 0.1) for f in (0.5, 1.2, 1.9)], [(0.03, 0.03)] * 3, 'glow', sides=4)
    for i, f in enumerate((0.75, 1.15, 1.55)):
        for sgn in (-1, 1):
            q0 = p + d * f
            o = (side * sgn).lerp(top * sgn * (1 if i % 2 else -1), 0.3).normalized()
            F.tube(tuple(q0), tuple(q0 - d * 0.42 + o * (0.32 - 0.06 * i)), [(0, 0.055), (1, 0.0)], 4, 'pale',
                   sharp=20)


def _flame_mat(name, col, k, p):
    m = bpy.data.materials.get(name)
    if m:
        return m
    BP = SFX.BP
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    # streaky noise: stretched along the flame (local X), churning fast
    vm = n.node('ShaderNodeVectorMath')
    vm.operation = 'MULTIPLY'
    n.set(vm.inputs[0], tc.outputs['Object'])
    vm.inputs[1].default_value = (0.35, 3.0, 3.0)
    nz = n.node('ShaderNodeTexNoise', Scale=4.0, Detail=6.0, Roughness=0.65)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], vm.outputs[0])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 14.0))
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), p)
    brk = n.maprange(nz.outputs['Fac'], 0.35, 0.7, 0.05, 1.5)
    # fade out toward the tail (generated X runs 0 at the tail .. 1 at the nozzle)
    sx = n.node('ShaderNodeSeparateXYZ')
    n.set(sx.inputs[0], tc.outputs['Generated'])
    fade = n.math('POWER', sx.outputs['X'], 1.8)
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY', g, brk), fade), k))
    tr = n.node('ShaderNodeBsdfTransparent')
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], tr.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], add.outputs[0])
    return m


def _plume(p, d, length, r, name):
    """Exhaust: white-gold core, gold mantle, wide soft glow, three shock diamonds. Returns objects."""
    d = Vector(d).normalized()
    pts = [Vector(p) + d * length * f for f in (0, 0.06, 0.2, 0.4, 0.6, 0.8, 1.0)]
    core = _flame_mat('OrbPlumeCoreM', HOTG, 5.0, 0.8)
    mant = _flame_mat('OrbPlumeMantleM', GOLD, 2.6, 1.5)
    soft = _flame_mat('OrbPlumeSoftM', (1.0, 0.45, 0.1), 0.8, 2.5)
    objs = [SFX._tube_path(name + 'Core', pts[:4], [r * 0.3, r * 0.26, r * 0.12, 0.01], core, sides=16),
            SFX._tube_path(name + 'Mantle', pts, [r * 0.85, r * 1.05, r * 1.05, r * 0.9, r * 0.65, r * 0.35, 0.02], mant, sides=24),
            SFX._tube_path(name + 'Soft', pts, [r * 1.0, r * 1.5, r * 1.8, r * 1.7, r * 1.3, r * 0.8, 0.05], soft, sides=24)]
    for i, f in enumerate((0.18, 0.33, 0.48)):
        s = SFX.C.uv_sphere(f'{name}Dia{i}', 1.0, seg=(10, 6), mat=SFX._emit('OrbDiamondM', HOTG, 10.0 - 2.5 * i),
                            scale=(r * 0.5, r * 0.32, r * 0.32))
        s.rotation_mode = 'QUATERNION'
        s.rotation_quaternion = d.to_track_quat('X', 'Z')
        s.location = Vector(p) + d * length * f
        s.visible_shadow = False
        objs.append(s)
    return objs


def orb_fighter(pose='sprint', name=None, thrust=1.0):
    name = name or f'OrbFighter_{pose}'
    plumes = []
    ax = Vector((1, 0, 0))
    with AF.gold_palette():
        base._faction('kesh')
        m = F.mark()
        _body()
        for k in range(8):
            a = 2 * math.pi * k / 8 + math.pi / 8
            rad = Vector((0, math.cos(a), math.sin(a)))
            tan = Vector((0, -math.sin(a), math.cos(a)))
            p = rad * RING
            # hinge bracket on the collar
            F.tube(tuple(rad * RING * 0.9), tuple(rad * RING * 1.2), [(0, 0.34), (1, 0.28)], 8, 'bronze')
            d = ax
            for j, (da, dr, dt) in enumerate(_leg_dirs(pose, k)):
                d = (ax * da + rad * dr + tan * dt).normalized()
                q = p + d * SEG[j]
                _, nrm = _segment(p, q, j, ax if abs(d.dot(ax)) < 0.9 else rad)
                if j == 0:
                    c = q - d * 0.55 + nrm * 0.55
                    exitp = _nacelle(c, d, nrm)
                    if pose == 'sprint':
                        fd = -ax
                    elif pose == 'grab':
                        fd = (-ax * 0.6 - rad * 0.4).normalized()
                    elif pose == 'spread':
                        fd = -d
                    else:
                        fd = -tan
                    plumes.append((exitp, fd, (5.0 if pose != 'grab' else 2.6) * thrust, 0.24, k))
                p = q
            _harpoon(p, d, ax if abs(d.dot(ax)) < 0.9 else rad)
        ob = base._join(F.since(m), name)
    # the living core: churning gold plasma just inside the caged orb, and the light it throws
    cx = X0 - R_ * 0.45
    pl = SFX.C.uv_sphere(name + 'CorePlasma', R_ * 0.57, seg=(32, 16), mat=SFX._plasma('OrbCorePlasmaM', GOLD, 6.0, 3.0))
    pl.location = (cx, 0, 0)
    pl.parent = ob
    gl = SFX.C.uv_sphere(name + 'CoreGlow', R_ * 0.72, seg=(32, 16), mat=SFX._halo('OrbCoreGlowM', GOLD, 0.6, 4.0))
    gl.location = (cx + 0.15, 0, 0)
    gl.visible_shadow = False
    gl.parent = ob
    lt = SFX._link(bpy.data.objects.new(name + 'CoreLight', bpy.data.lights.new(name + 'CoreLight', 'POINT')))
    lt.location = (X0 + 0.6, 0, 0)
    lt.data.color = GOLD
    lt.data.energy = 600
    lt.parent = ob
    if thrust > 0:
        for p, d, ln, r, k in plumes:
            for o in _plume(p, d, ln, r, f'{name}Plume{k}'):
                o.parent = ob
        for o in _plume(Vector((X1 - 0.8, 0, 0)), (-1, 0, 0), (8.0 if pose == 'sprint' else 3.0) * thrust, R_ * 0.32,
                        f'{name}PlumeMain'):
            o.parent = ob
    return ob


# ------------------------------------------------------------------ rigged Orb: every leg moves on its own
# David 2026-11-14: thrusters ONLY on the tentacles; Arcadian thrusters are LIGHTNING; every arm moves completely
# independently with its own calculations, graceful and hyper-dextrous.
import random  # noqa: E402

N_VAR = 4                     # lightning variants per thruster, flickered between


def _part(build, name):
    """Run build() (forge calls at the origin) and join the result into one object with its origin at 0."""
    m = F.mark()
    build()
    ob = base._join(F.since(m), name)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.location = (0, 0, 0)
    ob.rotation_mode = 'QUATERNION'
    return ob


def _frame_q(x, ref, alt):
    """Rotation whose +X is x and whose +Z leans toward ref."""
    from mathutils import Matrix
    x = x.normalized()
    z = ref - x * x.dot(ref)
    if z.length < 1e-3:
        z = alt - x * x.dot(alt)
    z.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_quaternion()


def _bolt_thruster(name, length, seed):
    """Gold lightning out of a nozzle at the origin, firing along -X. Returns (empty, [variant lists]).
    Each variant is 3 jagged bolts fanning back with forks; the shot flickers between variants."""
    from mathutils import Quaternion
    core_m = SFX._emit('OrbBoltCoreM', HOTG, 12.0)
    sleeve_m = SFX._halo('OrbBoltSleeveM', (1.0, 0.55, 0.12), 4.0, 1.5)
    halo_m = SFX._halo('OrbBoltHaloM', (1.0, 0.55, 0.15), 0.5, 3.0)
    root = SFX._link(bpy.data.objects.new(name, None))
    rnd = random.Random(seed)
    variants = []
    for v in range(N_VAR):
        objs = []
        for b in range(3):
            d = Vector((-1, 0, 0))
            d.rotate(Quaternion(Vector((0, rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized(),
                                math.radians(rnd.uniform(3, 16))))
            ln = length * rnd.uniform(0.6, 1.0)
            pts = SFX._jag(Vector((0, 0, 0)), d * ln, rnd, 4, 0.16)
            n = len(pts)
            w = 0.16 if b == 0 else 0.1
            tp = [w * (1 - 0.85 * i / (n - 1)) for i in range(n)]
            objs.append(SFX._tube_path(f'{name}V{v}B{b}C', pts, [t * 0.35 for t in tp], core_m))
            objs.append(SFX._tube_path(f'{name}V{v}B{b}S', pts, [t * 1.3 for t in tp], sleeve_m, sides=8))
            if b == 0:
                objs.append(SFX._tube_path(f'{name}V{v}B{b}H', pts, [t * 6.0 for t in tp], halo_m, sides=10))
            for fk in range(2):
                j = rnd.randint(2, n - 3)
                side = d.orthogonal().normalized()
                side.rotate(Quaternion(d, rnd.uniform(0, 6.283)))
                e = pts[j] + (d * 0.5 + side).normalized() * ln * rnd.uniform(0.12, 0.25)
                br = SFX._jag(pts[j], e, rnd, 3, 0.22)
                objs.append(SFX._tube_path(f'{name}V{v}B{b}F{fk}', br,
                                           [tp[j] * 0.5 * (1 - k / len(br)) + 0.01 for k in range(len(br))], sleeve_m))
        for o in objs:
            o.parent = root
        variants.append(objs)
    glow = SFX.C.uv_sphere(name + 'Glow', 0.45, seg=(16, 8), mat=SFX._halo('OrbNozzleGlowM', GOLD, 1.2, 3.0))
    glow.visible_shadow = False
    glow.parent = root
    return root, variants


def orb_rig(name='Orb'):
    """The Orb built as a rig: body + 8 legs of 3 jointed segments, a swivelling nacelle per leg firing gold
    lightning. Returns (root, legs). Animate with animate_orb()."""
    ax = Vector((1, 0, 0))
    up = Vector((0, 0, 1))
    with AF.gold_palette():
        base._faction('kesh')

        def body():
            _body()
            for k in range(8):
                a = 2 * math.pi * k / 8 + math.pi / 8
                rad = Vector((0, math.cos(a), math.sin(a)))
                F.tube(tuple(rad * RING * 0.9), tuple(rad * RING * 1.2), [(0, 0.34), (1, 0.28)], 8, 'bronze')
        root = _part(body, name)
        segs_mesh = []
        for j in range(3):
            def seg(j=j):
                _segment(Vector((0, 0, 0)), Vector((SEG[j], 0, 0)), j, up)
                if j == 2:
                    _harpoon(Vector((SEG[2], 0, 0)), ax, up)
            segs_mesh.append(_part(seg, f'{name}SegMesh{j}').data)
        nac_mesh = _part(lambda: _nacelle(Vector((0, 0, 0)), ax, up), f'{name}NacMesh').data
    for o in [o for o in bpy.data.objects if o.name.startswith(f'{name}SegMesh') or o.name == f'{name}NacMesh']:
        bpy.data.objects.remove(o)
    cx = X0 - R_ * 0.45
    pl = SFX.C.uv_sphere(name + 'CorePlasma', R_ * 0.57, seg=(32, 16), mat=SFX._plasma('OrbCorePlasmaM', GOLD, 6.0, 3.0))
    pl.location = (cx, 0, 0)
    pl.parent = root
    gl = SFX.C.uv_sphere(name + 'CoreGlow', R_ * 0.72, seg=(32, 16), mat=SFX._halo('OrbCoreGlowM', GOLD, 0.6, 4.0))
    gl.location = (cx + 0.15, 0, 0)
    gl.visible_shadow = False
    gl.parent = root
    lt = SFX._link(bpy.data.objects.new(name + 'CoreLight', bpy.data.lights.new(name + 'CoreLight', 'POINT')))
    lt.location = (X0 + 0.6, 0, 0)
    lt.data.color = GOLD
    lt.data.energy = 600
    lt.parent = root
    legs = []
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        rad = Vector((0, math.cos(a), math.sin(a)))
        tan = Vector((0, -math.sin(a), math.cos(a)))
        segs = []
        parent = root
        for j in range(3):
            s_ = bpy.data.objects.new(f'{name}Leg{k}Seg{j}', segs_mesh[j])
            SFX._link(s_)
            s_.rotation_mode = 'QUATERNION'
            s_.parent = parent
            s_.location = rad * RING if j == 0 else Vector((SEG[j - 1], 0, 0))
            segs.append(s_)
            parent = s_
        nac = bpy.data.objects.new(f'{name}Leg{k}Nacelle', nac_mesh)
        SFX._link(nac)
        nac.rotation_mode = 'QUATERNION'
        pe, variants = _bolt_thruster(f'{name}Leg{k}Plume', 6.0, 100 + k)
        pe.parent = nac
        pe.location = (-1.4, 0, 0)
        lamp = SFX._link(bpy.data.objects.new(f'{name}Leg{k}PlumeLight', bpy.data.lights.new(f'{name}Leg{k}PlumeL', 'POINT')))
        lamp.data.color = GOLD
        lamp.data.energy = 0
        lamp.data.shadow_soft_size = 0.6
        lamp.parent = pe
        lamp.location = (-1.0, 0, 0)
        nac.parent = segs[0]
        nac.location = (SEG[0] - 0.55, 0, 0.55)      # elbow, on the outer (+Z) side
        legs.append(dict(seg=segs, nac=nac, plume=pe, var=variants, lamp=lamp, rad=rad, tan=tan, k=k,
                         base=rad * RING))
    return root, legs


def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _fabrik(base_p, tgt, pts, lens, pole, iters=14, avoid=None, max_reach=0.97):
    """N-bone FABRIK in body space, warm-started from last frame's joints, bent toward pole, kept off the body.
    avoid(p, pole) -> p pushes a joint out of the body (default: the hull of the original Orb)."""
    n = len(lens)
    total = sum(lens)
    d = tgt - base_p
    if d.length > total * max_reach:
        tgt = base_p + d.normalized() * total * max_reach
    if d.length < total * 0.23:
        tgt = base_p + (d.normalized() if d.length > 1e-4 else pole) * total * 0.23

    def hull_avoid(p, pole):
        r = Vector((0, p.y, p.z))
        if X1 - 1.0 < p.x < X0 + 0.8 and r.length < R_ + 0.7:
            return Vector((p.x, 0, 0)) + (r.normalized() if r.length > 1e-4 else pole) * (R_ + 0.7)
        return p
    avoid = avoid or hull_avoid
    pts = [p.copy() for p in pts]
    for it in range(iters):
        bias = 0.25 * 3.0 / n if it < iters - 3 else 0.0
        for i in range(1, n):
            pts[i] = pts[i] + pole * bias * math.sin(math.pi * i / n)
        pts[n] = tgt.copy()
        for i in range(n - 1, -1, -1):
            pts[i] = pts[i + 1] + (pts[i] - pts[i + 1]).normalized() * lens[i]
        pts[0] = base_p.copy()
        for i in range(1, n + 1):
            pts[i] = pts[i - 1] + (pts[i] - pts[i - 1]).normalized() * lens[i - 1]
            pts[i] = avoid(pts[i], pole)
    return pts


def animate_orb(root, legs, f0, f1, grabs=(), f_die=None, seed=3, fps=24, scale=1.0, arm=None, tethers=None):
    """Bake the legs. Every leg is its own little creature: its own stroke clock (re-rolled every stroke), its
    own spring (stiffness, damping), its own reaction to the body's acceleration and spin, its own thruster
    that fires lightning when (and where) that leg pushes. Grabs: dicts(f_reach, f_grab, f_tear, hold, legs)."""
    rnd = random.Random(seed)
    sc = bpy.context.scene
    ax = Vector((1, 0, 0))
    lens = list(SEG) if arm is None else arm_dims()[0]
    L = sum(lens)
    NJ = len(lens)
    avoid = None
    if arm is not None:
        from mathutils import Matrix
        cc = Vector((ORB_X, 0, 0))

        def avoid(p, pole):                                # keep every joint clear of the core and its glow
            r = p - cc
            if r.length < ORB_RC * 2.0:
                return cc + (r.normalized() if r.length > 1e-4 else pole) * ORB_RC * 2.0
            return p
        rest_m = {L_['k']: [arm.data.bones[bn].matrix_local.to_3x3() for bn in L_['bones']] for L_ in legs}
        for L_ in legs:
            for bn in L_['bones']:
                arm.pose.bones[bn].rotation_mode = 'QUATERNION'
        teth = [v for kind, v in (tethers or []) if kind == 'tether']
    # body motion, sampled
    M, P = {}, {}
    for f in range(f0 - 2, f1 + 3):
        sc.frame_set(f)
        M[f] = root.matrix_world.copy()
        P[f] = M[f].translation.copy()
    dt = 1.0 / fps

    def accel_local(f):
        a = (P[f + 1] - 2 * P[f] + P[f - 1]) / (dt * dt)
        al = M[f].to_3x3().normalized().inverted() @ a / scale
        cap = 900 if arm is None else 320      # arms: jinks pull the arms, but never all-at-once flings
        if al.length > cap:
            al = al.normalized() * cap
        return al

    def vel_local(f):
        v = (P[f + 1] - P[f - 1]) / (2 * dt)
        return M[f].to_3x3().normalized().inverted() @ v / scale
    st = []
    for Lg in legs:
        cyc, t = [], rnd.uniform(-1.0, 0.0)
        while t < (f1 - f0) / fps + 2:
            dur = rnd.uniform(0.42, 1.05)
            cyc.append((t, dur, rnd.uniform(0.6, 1.0), rnd.uniform(-1.0, 1.0), rnd.uniform(0.45, 0.72)))
            t += dur * rnd.uniform(0.95, 1.35)        # sometimes it glides a beat before the next stroke
        b = Lg['base']
        rest = b + (-ax * 0.9 + Lg['rad'] * 0.45).normalized() * L * 0.9
        st.append(dict(cyc=cyc, w=rnd.uniform(10.0, 17.0), z=rnd.uniform(0.32, 0.55), x=rest.copy(), v=Vector(),
                       pts=[b + (rest - b) * (i_ / NJ) for i_ in range(NJ + 1)], thr=0.0,
                       jv=[Vector() for _ in range(NJ + 1)],
                       ph=rnd.uniform(0, 6.283), gk=rnd.uniform(0.7, 1.3), q_prev=None, flick=rnd.randrange(N_VAR)))
    grab_of = {}
    for g in grabs:
        for k in g['legs']:
            grab_of.setdefault(k, []).append(dict(g, d=rnd.randint(-5, 3), spin=rnd.uniform(-0.5, 0.5)))
    vis_prev = {}
    for f in range(f0, f1 + 1):
        t = (f - f0) / fps
        al = accel_local(f)
        vl = vel_local(f)
        lat = al - ax * al.dot(ax)
        R_prev, R_now = M[f - 1].to_3x3().normalized(), M[f].to_3x3().normalized()
        R_delta = R_now.inverted() @ R_prev                 # how last frame's body space looks from this frame
        spin = R_delta.to_quaternion().angle * fps          # rad/s
        speed = vl.length
        for Lg, S in zip(legs, st):
            k, rad, tan, b = Lg['k'], Lg['rad'], Lg['tan'], Lg['base']
            # ---- its own stroke: reach forward-out (slow, curled), then sweep back hard (fast, straight)
            c = next((c for c in reversed(S['cyc']) if c[0] <= t), S['cyc'][0])
            u = (t - c[0]) / c[1]
            amp = c[2] * (0.6 + 0.4 * min(1.0, (lat.length / 260 + spin / 2.5)))   # harder work in turns / dodges
            if speed > 60 and lat.length < 80:
                amp *= 0.85                                     # a little streamlining at full sprint
            # each stroke this leg works out its OWN three points (reach, curl, trail) from what the body needs
            # right now plus its own randomness, and keeps clear of the points its neighbours have picked
            ci = S['cyc'].index(c)
            if S.get('plan_i') != ci:
                need = ax * (0.6 if speed > 30 else 0.25) + (lat.normalized() * min(1.0, lat.length / 250) if lat.length > 1 else Vector())
                for _try in range(6):
                    rr = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
                    rd = (need * (0.6 + 0.9 * amp) + rad * 0.85 + tan * c[3] * 0.7 + rr * 0.55)
                    if rd.dot(rad) < 0.15:
                        rd = rd + rad * (0.15 - rd.dot(rad) + 0.2)
                    reach_p = b + rd.normalized() * L * rnd.uniform(0.55, 0.86)
                    if all((reach_p - o_['plan'][0]).length > 2.6 for o_ in st if o_ is not S and 'plan' in o_):
                        break
                rt = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
                trail_p = b + (-ax * 0.95 + rad * rnd.uniform(0.25, 0.6) - need * 0.35 + rt * 0.3).normalized() * L * \
                    (rnd.uniform(0.78, 0.95) if arm is None else rnd.uniform(0.6, 0.76))   # long arms: never a straight rod
                rc = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
                curl_p = b + (rad + rc * 0.6 - ax * 0.2).normalized() * L * rnd.uniform(0.32, 0.5)
                S['plan'], S['plan_i'] = (reach_p, curl_p, trail_p), ci
            reach, curl, trail = S['plan']
            pw = c[4]
            if u >= 1.0:                                       # gliding between strokes: drift trailing
                tgt, stroking = trail, 0.0
            elif u < pw:                                       # recovery: curl in past its own via-point, then out
                e = _ease(u / pw)
                tgt = trail * (1 - e) ** 2 + curl * 2 * e * (1 - e) + reach * e * e
                stroking = 0.0
            else:                                              # power: whip back to its own trail point
                e = (u - pw) / (1 - pw)
                e = 1 - (1 - e) ** 2.4
                tgt = reach.lerp(trail, e) + rad * math.sin(math.pi * e) * L * 0.1 * amp
                stroking = math.sin(math.pi * min(1.0, e * 1.1)) * amp
            # its own idle life: slow wander of the tip
            tgt = tgt + (rad * math.sin(t * 1.7 * S['gk'] + S['ph']) + tan * math.sin(t * 2.3 * S['gk'] + S['ph'] * 1.7)) * 0.9
            w, z = S['w'], S['z']
            S['wave_k'] = 1.0
            # ---- grabs: this leg reaches for its own point on the target, on its own beat
            for g in grab_of.get(k, []):
                fa, fg, ft = g['f_reach'] + g['d'], g['f_grab'] + g['d'] // 2, g['f_tear']
                hold = g['hold']
                wrap = hold + rad * 1.2 + tan * g['spin'] * 0.6 - ax * 0.4
                if fa <= f < fg:
                    e = _ease((f - fa) / max(1, fg - fa))
                    wide = hold + rad * 3.6 + ax * 1.2 + tan * g['spin'] * 2.0
                    tgt = wide.lerp(wrap, e ** 1.6)
                    w, z, stroking = S['w'] * 1.4, 0.5, 0.45
                elif fg <= f < ft:
                    tgt = wrap + rad * 0.12 * math.sin(f * 2.1 + k)  # clutching, flexing
                    w, z, stroking = 22.0, 0.8, 0.25
                    S['wave_k'] = 0.3
                elif ft <= f < ft + 9:
                    tgt = hold + rad * 6.5 - ax * 1.8 + tan * g['spin'] * 3.0   # rip it apart
                    w, z, stroking = 26.0, 0.5, 0.9
            if f_die is not None and f >= f_die:
                S.setdefault('dtan', rnd.random() - 0.5)          # one fling direction per leg (no per-frame jitter)
                if f < f_die + 14:                                # the blast flings every arm out
                    tgt = b + (rad * 1.0 + tan * S['dtan']).normalized() * L * 1.1
                    w, z, stroking = 18.0, 0.3, 0.0
                else:                                            # then dead: limp, slowly folding and drifting
                    td = (f - f_die - 14) / fps
                    tgt = b + (rad * 0.8 - ax * 0.45 + tan * (S['dtan'] + 0.35 * math.sin(td * 0.7 + S['ph']))
                               ).normalized() * L * 0.62
                    w, z, stroking = 3.2, 0.22, 0.0
                    S['wave_k'] = 0.35
            # ---- its own physics: carry last frame's tip through the body's spin, push it with the body's
            # acceleration, then spring toward where the leg wants to be
            x = R_delta @ S['x']
            vv = R_delta @ S['v']
            for _ss in range(4):                               # sub-stepped: stiff springs stay stable (no frame flicker)
                acc = (tgt - x) * (w * w) - vv * (2 * z * w) - al * 0.55
                vv = vv + acc * (dt / 4)
                x = x + vv * (dt / 4)
            S['x'], S['v'] = x, vv
            pole = (rad * 1.0 + ax * 0.45 * math.sin(t * 1.3 * S['gk'] + S['ph']) + tan * 0.35 * math.sin(t * 0.9 + S['ph'] * 2.3)).normalized()
            prev_pts = [R_delta @ p for p in S['pts']]
            # long arms keep a living curve: never pulled out to a straight rod (except the death fling)
            mr = 0.97 if arm is None or (f_die is not None and f >= f_die) else 0.84
            pts = _fabrik(b, x, prev_pts, lens, pole, avoid=avoid, max_reach=mr)
            if arm is None:
                S['pts'] = pts
                qs = [_frame_q(pts[j + 1] - pts[j], rad, ax) for j in range(3)]
                for j, s_ in enumerate(Lg['seg']):
                    s_.rotation_quaternion = qs[0] if j == 0 else qs[j - 1].inverted() @ qs[j]
                    s_.keyframe_insert('rotation_quaternion', frame=f)
            else:
                # every joint follows the solved shape on its own spring, stiff at the shoulder, loose at the
                # tip: a fast move ripples down the arm and the harpoon trails and settles after it
                # a travelling bend runs from shoulder to tip on this leg's own clock (zero at both ends, widest
                # mid-arm), quieter while it whips through a power stroke or clutches a target
                wa = 0.62 * (1.0 - 0.55 * stroking) * S.get('wave_k', 1.0)
                wf, wl = 3.4 * S['gk'], 6.5 + 1.5 * S['gk']
                pts = list(pts)
                for j_ in range(1, NJ):
                    u_ = j_ / NJ
                    sd = (pts[j_ + 1] - pts[j_ - 1])
                    sd = sd.normalized() if sd.length > 1e-5 else ax
                    ph_ = t * wf - u_ * wl + S['ph']
                    dv = tan * math.sin(ph_) + rad * 0.45 * math.sin(t * 2.2 * S['gk'] - u_ * 5.0 + S['ph'] * 1.9)
                    dv = dv - sd * sd.dot(dv)
                    env = math.sin(math.pi * u_) ** 2
                    for g in grab_of.get(k, []):              # the snap after a tear rolls back up the arm
                        el = (f - g['f_tear']) / fps - (1.0 - u_) * 0.45
                        if 0 < el < 1.6:
                            dv = dv + rad * 1.1 * math.sin(el * 11) * math.exp(-el * 3.0)
                    pts[j_] = pts[j_] + dv * wa * env
                jp = list(prev_pts)
                for j_ in range(1, NJ + 1):
                    wj = 34.0 * (1.0 - 0.6 * j_ / NJ)
                    jv_ = R_delta @ S['jv'][j_]
                    for _ss in range(6):                       # sub-stepped (w*dt would be > 1 per frame)
                        a_ = (pts[j_] - jp[j_]) * (wj * wj) - jv_ * (2 * 0.6 * wj) - al * 0.25
                        jv_ = jv_ + a_ * (dt / 6)
                        jp[j_] = jp[j_] + jv_ * (dt / 6)
                    S['jv'][j_] = jv_
                # spread the curvature: a light smoothing pass so no single joint carries the whole bend
                for _it in range(2):
                    jp = [jp[0]] + [jp[i_] * 0.5 + (jp[i_ - 1] + jp[i_ + 1]) * 0.25 for i_ in range(1, NJ)] + [jp[NJ]]
                # arms never pass through each other: push this arm's joints clear of every other arm (legs
                # already solved this frame use their new shape, the rest last frame's carried through the spin)
                _, rads_ = arm_dims()
                others_ = []
                for o_ in st:
                    if o_ is S:
                        continue
                    op = o_.get('pts_now') if o_.get('pts_f') == f else [R_delta @ q_ for q_ in o_['pts']]
                    others_.append(op)
                    for j_ in range(2, NJ + 1):
                        for i_ in range(2, NJ + 1):
                            dd = jp[j_] - op[i_]
                            need_ = (rads_[j_] + rads_[i_]) * 1.35 + 0.08
                            if dd.length < need_:
                                jp[j_] = op[i_] + (dd.normalized() if dd.length > 1e-5 else pole) * need_
                # re-chain from the shoulder with exact segment lengths. Each joint bends at most 24 degrees
                # (curls, never knots), each segment turns at most 13-30 degrees a frame (stiff near the shoulder,
                # quick at the harpoon: no snaps or pops), and nothing passes through the core.
                from mathutils import Quaternion as _Q

                def _turn_to(a_, b_, lim_):
                    ang_ = a_.angle(b_) if a_.dot(b_) < 0.99999 else 0.0
                    if ang_ <= lim_:
                        return b_
                    ax_ = a_.cross(b_)
                    if ax_.length < 1e-6:
                        return a_
                    return _Q(ax_.normalized(), lim_) @ a_
                out_ = [b.copy()]
                dprev = None
                for j_ in range(NJ):
                    dj = (jp[j_ + 1] - out_[-1])
                    dj = dj.normalized() if dj.length > 1e-5 else (dprev or (prev_pts[1] - b).normalized())
                    dold = prev_pts[j_ + 1] - prev_pts[j_]
                    nxt = out_[-1] + dj * lens[j_]
                    if j_ > 0 and avoid is not None and (nxt - cc).length < ORB_RC * 1.7:
                        push = (nxt - cc).normalized()
                        dj = (dj + push * 0.8).normalized()
                    if j_ >= 1:                                # deflect around the other arms' joints
                        for _rep in range(2):
                            for op_ in others_:
                                for i_ in range(2, NJ + 1):
                                    dd = nxt - op_[i_]
                                    need_ = (rads_[j_ + 1] + rads_[i_]) * 1.35 + 0.08
                                    if dd.length < need_:
                                        nxt = op_[i_] + (dd.normalized() if dd.length > 1e-5 else pole) * need_
                            dj = (nxt - out_[-1]).normalized()
                            nxt = out_[-1] + dj * lens[j_]
                    # limits last, so nothing after them can snap a segment
                    if dold.length > 1e-5:
                        dj = _turn_to(dold.normalized(), dj, math.radians(11 + 14 * j_ / (NJ - 1)))
                    if dprev is not None:
                        dj = _turn_to(dprev, dj, math.radians(24))
                    nxt = out_[-1] + dj * lens[j_]
                    out_.append(nxt)
                    dprev = dj
                S['pts'] = out_
                S['pts_now'], S['pts_f'] = out_, f
                # bones: parallel-transport the crest side down the chain so the arm never twists
                Rr = rest_m[k]
                zref = rad.copy()
                Dprev = None
                for j_, bn in enumerate(Lg['bones']):
                    y_ = (out_[j_ + 1] - out_[j_]).normalized()
                    z_ = zref - y_ * y_.dot(zref)
                    if z_.length < 1e-4:
                        z_ = ax - y_ * y_.dot(ax)
                    z_.normalize()
                    x_ = y_.cross(z_)
                    D = Matrix((x_, y_, z_)).transposed()
                    if j_ == 0:
                        B = Rr[0].inverted() @ D
                    else:
                        B = Rr[j_].inverted() @ Rr[j_ - 1] @ Dprev.transposed() @ D
                    pb = arm.pose.bones[bn]
                    pb.rotation_quaternion = B.to_quaternion()
                    pb.keyframe_insert('rotation_quaternion', frame=f)
                    Dprev, zref = D, z_
                if teth:                                     # its lightning tether crackles: new strike each frame
                    tv = teth[k]
                    pick = (f * 7 + k * 3) % len(tv)
                    if f_die is not None and f >= f_die:
                        pick = -1                              # dead: the tethers go dark, the arms come loose
                    for vi, objs in enumerate(tv):
                        for o in objs:
                            o.hide_render = vi != pick
                            o.keyframe_insert('hide_render', frame=f)
            # ---- its own thruster: exhaust opposite to where this leg wants to push the body
            need = -lat * (1.0 / 300) + ax * (0.25 + (0.6 if speed > 30 else 0.2))
            push_dir = need + (-vv.normalized() * 0.6 * stroking if vv.length > 1 else Vector())
            if push_dir.length < 1e-3:
                push_dir = ax.copy()
            exhaust = -push_dir.normalized()
            share = 0.5 + 0.5 * max(0.0, -rad.dot(lat.normalized())) if lat.length > 20 else 0.6
            thr = min(1.0, 0.15 + stroking * 0.9 + min(1.0, lat.length / 400) * share + (0.25 if speed > 60 else 0))
            if f_die is not None and f >= f_die:
                thr = 0.0
            S['thr'] += (thr - S['thr']) * 0.45
            if arm is None:
                qn = _frame_q(-exhaust, rad, ax)               # nacelle +X = intake, so -X points down the exhaust
                Lg['nac'].rotation_quaternion = qs[0].inverted() @ qn
                Lg['nac'].keyframe_insert('rotation_quaternion', frame=f)
            th = S['thr']
            ps_ = 1.0 if arm is None else 0.6            # small arm nacelles: shorter bolts
            Lg['plume'].scale = (max(0.02, th) * ps_, (0.5 + 0.5 * th) * ps_, (0.5 + 0.5 * th) * ps_)
            Lg['plume'].keyframe_insert('scale', frame=f)
            Lg['lamp'].data.energy = 250 * th
            Lg['lamp'].data.keyframe_insert('energy', frame=f)
            # lightning flickers: a new variant every 1-2 frames, nothing when idle
            if f % 2 == 0 or rnd.random() < 0.4:
                S['flick'] = (S['flick'] + 1 + rnd.randrange(N_VAR - 1)) % N_VAR
            on = S['flick'] if th > (0.08 if arm is None else 0.32) else -1   # arms: only legs that are pushing fire
            if vis_prev.get(k) != on:
                for vi, objs in enumerate(Lg['var']):
                    for o in objs:
                        o.hide_render = vi != on
                        o.keyframe_insert('hide_render', frame=f)
                vis_prev[k] = on
    extra = [o for tv in (teth if arm is not None else []) for objs in tv for o in objs]
    for Lg in legs:
        for o in [Lg['plume']] + list(Lg['plume'].children_recursive) + (extra if Lg is legs[0] else []):
            ad = o.animation_data
            if not ad or not ad.action:
                continue
            try:
                curves = ad.action.fcurves
            except AttributeError:
                curves = [fc for layer in ad.action.layers for strip in layer.strips
                          for bag in strip.channelbags for fc in bag.fcurves]
            for fc in curves:
                if fc.data_path == 'hide_render':
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
    sc.frame_set(f0)
    return root


# ================================================================== arm v2 (2026-11-15): many short sleeved segments
# on real Blender bones. David: mechanical joints that flow and bend naturally. Three long rigid segments could only
# make spider-leg angles; a dozen short tapering segments, each sleeved into the next like vertebrae / armour
# plates, add up to a continuous curve while every joint still reads as machined.
ARM_N = 12
ARM_LEN = 10.6
ORB_X, ORB_RC, ORB_RS = 0.0, 1.25, 3.4     # orb-core design: core centre, core radius, shoulder ring radius


def arm_dims(n=ARM_N, total=ARM_LEN):
    w = [1.0 - 0.45 * i / (n - 1) for i in range(n)]               # segments shorten toward the tip
    k = total / sum(w)
    lens = [x * k for x in w]
    rad = [0.36 - 0.26 * (i / (n - 1)) ** 0.9 for i in range(n + 1)]  # radius at each joint, base -> tip
    return lens, rad


def _vertebra(l, r0, r1, last=False):
    """One arm segment along +X from its joint (0) to the next joint (l). Rear sleeve flares back over the
    previous joint so a bend never shows a gap."""
    F.tube((0, 0, 0), (l, 0, 0), [(0, r0 * 0.78), (0.12, r0 * 0.92), (0.88, r1 * 0.95), (1, r1 * 0.8)], 12, 'shell',
           sharp=40)
    # armour sleeve: cup over the previous joint, tapering to the waist before the next
    F.tube((-0.22 * l, 0, 0), (0.68 * l, 0, 0),
           [(0, r0 * 1.22), (0.08, r0 * 1.34), (0.55, (r0 + r1) * 0.62), (1, r1 * 1.12)], 12, 'bronze', sharp=35)
    # clamp band and a glowing joint ring sitting in the gap
    F.tube((0.74 * l, 0, 0), (0.8 * l, 0, 0), [(0, r1 * 1.18), (1, r1 * 1.18)], 12, 'pale')
    F.tube((-0.02 * l, 0, 0), (0.03 * l, 0, 0), [(0, r0 * 1.02), (1, r0 * 1.02)], 16, 'glow', caps=False)
    # dorsal crest plate (outer side = +Z) and the glowing tendon under it
    F.sweep([(-0.1 * l, 0, r0 * 1.25), (0.3 * l, 0, r0 * 1.48), (0.62 * l, 0, r1 * 1.25)],
            [(0.03, 0.05), (0.05, 0.1), (0.02, 0.04)], 'pale', sides=4)
    F.sweep([(0.05 * l, 0, r0 * 0.95), (0.5 * l, 0, (r0 + r1) * 0.5), (0.95 * l, 0, r1 * 0.92)],
            [(0.035, 0.035)] * 3, 'glow', sides=4)
    # ventral grip studs
    for f in (0.3, 0.55):
        F.orb((f * l, 0, -(r0 * (1 - f) + r1 * f) * 1.05), 0.05 + r1 * 0.12, 'pale', seg=(6, 4))
    if last:
        _harpoon(Vector((l, 0, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)))



def _core_mat(name, hot=(1.0, 0.42, 0.0), rim=(1.0, 0.2, 0.0), kh=1.0, kr=0.4):
    """Orb core: churning molten gold. Emission stays near 1 so the colour survives the AgX view transform."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    BP = SFX.BP
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.0)
    nz = n.node('ShaderNodeTexNoise', Scale=3.0, Detail=10.0, Roughness=0.65)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 1.5))
    rid = n.math('POWER', n.math('SUBTRACT', 1.0, n.math('ABSOLUTE', n.math('SUBTRACT', nz.outputs['Fac'], 0.5))), 90.0)
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    fac = n.math('POWER', lw.outputs['Facing'], 0.8)
    mix = n.node('ShaderNodeMix')
    mix.data_type = 'RGBA'
    n.set(mix.inputs['Factor'], fac)
    mix.inputs[6].default_value = (*hot, 1)
    mix.inputs[7].default_value = (*rim, 1)
    em = n.node('ShaderNodeEmission')
    n.set(em.inputs['Color'], mix.outputs[2])
    st = n.math('ADD', n.math('MULTIPLY', n.math('SUBTRACT', 1.0, fac), kh - kr), kr)
    n.set(em.inputs['Strength'], n.math('MULTIPLY', st, n.math('ADD', 1.0, n.math('MULTIPLY', rid, 2.5))))
    out = n.node('ShaderNodeOutputMaterial')
    n.set(out.inputs['Surface'], em.outputs[0])
    return m


def orb_rig2(name='Orb', core='hull'):
    """Body + armature with 8 bone chains (ARM_N bones each); one sleeved segment mesh per bone, a compact lightning
    nacelle on bone 1. Returns (arm_obj, root_body, legs) where legs[k] = dict(bones=[names], rad, tan, base, nac,
    plume, var, lamp)."""
    from mathutils import Matrix
    ax = Vector((1, 0, 0))
    lens, rads = arm_dims()
    with AF.gold_palette():
        base._faction('kesh')

        def body():
            if core == 'orb':
                # no hull: eight floating shoulder sockets hang round the core, held only by lightning
                for k in range(8):
                    a = 2 * math.pi * k / 8 + math.pi / 8
                    rad = Vector((0, math.cos(a), math.sin(a)))
                    c = Vector((ORB_X, 0, 0)) + rad * ORB_RS
                    F.orb(tuple(c), 0.42, 'bronze', seg=(14, 10))
                    F.tube(tuple(c - rad * 0.32), tuple(c - rad * 0.18), [(0, 0.5), (1, 0.5)], 16, 'pale')
                    F.tube(tuple(c - rad * 0.36), tuple(c - rad * 0.3), [(0, 0.36), (1, 0.36)], 16, 'glow', caps=False)
                    for s_ in (-1, 1):                                  # two little fins either side
                        tn = Vector((0, -math.sin(a), math.cos(a)))
                        F.sweep([tuple(c + tn * s_ * 0.3), tuple(c + tn * s_ * 0.62 - rad * 0.15 + Vector((-0.3, 0, 0))),
                                 tuple(c + tn * s_ * 0.75 - rad * 0.4 + Vector((-0.7, 0, 0)))],
                                [(0.02, 0.12), (0.03, 0.14), (0.01, 0.04)], 'pale', sides=4)
                return
            _body()
            for k in range(8):
                a = 2 * math.pi * k / 8 + math.pi / 8
                rad = Vector((0, math.cos(a), math.sin(a)))
                F.tube(tuple(rad * RING * 0.88), tuple(rad * RING * 1.12), [(0, 0.42), (1, 0.38)], 10, 'bronze')
                F.orb(tuple(rad * RING * 1.12), 0.4, 'bronze', seg=(12, 8))
        root = _part(body, name)
        seg_mesh = []
        for j in range(ARM_N):
            ob = _part(lambda j=j: _vertebra(lens[j], rads[j], rads[j + 1], last=j == ARM_N - 1), f'{name}V{j}')
            ob.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Z'))       # build axis +X -> bone axis +Y
            seg_mesh.append(ob.data)
            bpy.data.objects.remove(ob)
        nac = _part(lambda: _nacelle(Vector((0, 0, 0)), ax, Vector((0, 0, 1))), f'{name}Nac')
        nac.data.transform(Matrix.Scale(0.62, 4))
        nac_mesh = nac.data
        bpy.data.objects.remove(nac)
    cx, cr = (X0 - R_ * 0.45, R_ * 0.57) if core != 'orb' else (ORB_X, ORB_RC)
    pl = SFX.C.uv_sphere(name + 'CorePlasma', cr, seg=(48, 24),
                         mat=SFX._plasma('OrbCorePlasmaM' if core != 'orb' else 'OrbCorePlasmaM2', GOLD if core != 'orb' else (1.0, 0.40, 0.04),
                                         6.0 if core != 'orb' else 1.7, 3.0))
    pl.location = (cx, 0, 0)
    pl.parent = root
    if core == 'orb':     # molten gold: hot gold face, deep orange limb, thin bright filaments (kept dim enough
        pl.data.materials[0] = _core_mat('OrbCoreMoltenM')   # that AgX keeps it gold instead of washing to beige)
    gl = SFX.C.uv_sphere(name + 'CoreGlow', cr * (1.3 if core != 'orb' else 1.9), seg=(32, 16),
                         mat=SFX._halo('OrbCoreGlowM' if core != 'orb' else 'OrbCoreGlowM2', GOLD if core != 'orb' else (1.0, 0.35, 0.0),
                                       0.6 if core != 'orb' else 0.12, 4.0 if core != 'orb' else 2.5))
    gl.location = (cx, 0, 0)
    gl.visible_shadow = False
    gl.parent = root
    lt = SFX._link(bpy.data.objects.new(name + 'CoreLight', bpy.data.lights.new(name + 'CoreLight', 'POINT')))
    lt.location = (cx + (0.6 if core != 'orb' else 0.0), 0, 0)
    lt.data.color = GOLD
    lt.data.energy = 600 if core != 'orb' else 1500
    lt.parent = root
    tethers = []
    if core == 'orb':
        # two thin gold gyro rings round the core, and lightning tethers from core to every shoulder
        import random as _r
        with AF.gold_palette():
            base._faction('kesh')
            for i, (axis, rr) in enumerate((((1, 0, 0), cr * 1.45), ((0.3, 1, 0.2), cr * 1.6))):
                ro = _part(lambda axis=axis, rr=rr: AF.oriented_ring((0, 0, 0), axis, rr, 0.07, 0.05, 'pale', gaps=4),
                           f'{name}Gyro{i}')
                ro.parent = root
                ro.location = (cx, 0, 0)
                tethers.append(('gyro', ro))
        core_m = SFX._emit('OrbBoltCoreM', HOTG, 12.0)
        sleeve_m = SFX._halo('OrbBoltSleeveM', (1.0, 0.55, 0.12), 4.0, 1.5)
        for k in range(8):
            a = 2 * math.pi * k / 8 + math.pi / 8
            rad = Vector((0, math.cos(a), math.sin(a)))
            c0 = Vector((cx, 0, 0)) + rad * cr * 0.95
            c1 = Vector((ORB_X, 0, 0)) + rad * (ORB_RS - 0.4)
            var = []
            for v in range(N_VAR):
                rnd = _r.Random(k * 17 + v)
                objs = []
                for b in range(3):
                    off = Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3)))
                    pts = SFX._jag(c0 + off * 0.5, c1 + off * 0.3, rnd, 4, 0.22)
                    objs.append(SFX._tube_path(f'{name}Teth{k}V{v}B{b}C', pts, 0.035, core_m))
                    objs.append(SFX._tube_path(f'{name}Teth{k}V{v}B{b}S', pts, 0.11, sleeve_m, sides=8))
                for o in objs:
                    o.parent = root
                var.append(objs)
            tethers.append(('tether', var))
    # ---- armature
    ad = bpy.data.armatures.new(name + 'Arms')
    arm = SFX._link(bpy.data.objects.new(name + 'Arms', ad))
    arm.parent = root
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    legs = []
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        rad = Vector((0, math.cos(a), math.sin(a)))
        tan = Vector((0, -math.sin(a), math.cos(a)))
        d0 = (-ax * 0.75 + rad * 0.66).normalized()                    # rest: swept back and out
        p0 = rad * RING * 1.12 if core != 'orb' else Vector((ORB_X, 0, 0)) + rad * ORB_RS
        p = rad * RING * 1.12 if core != 'orb' else Vector((ORB_X, 0, 0)) + rad * ORB_RS
        names, prev = [], None
        for j in range(ARM_N):
            b = ad.edit_bones.new(f'L{k}_{j}')
            b.head = p
            b.tail = p + d0 * lens[j]
            b.align_roll(rad - d0 * d0.dot(rad))                         # bone Z = outward (crest side)
            if prev is not None:
                b.parent = prev
                b.use_connect = True
            prev = b
            names.append(b.name)
            p = b.tail.copy()
        legs.append(dict(bones=names, rad=rad, tan=tan, base=p0, k=k, d0=d0))
    bpy.ops.object.mode_set(mode='OBJECT')
    for L in legs:
        for j, bn in enumerate(L['bones']):
            o = SFX._link(bpy.data.objects.new(f'{name}Leg{L["k"]}Seg{j}', seg_mesh[j]))
            o.parent = arm
            o.parent_type = 'BONE'
            o.parent_bone = bn
            o.matrix_world = arm.matrix_world @ ad.bones[bn].matrix_local
        nb = L['bones'][1]
        nac = SFX._link(bpy.data.objects.new(f'{name}Leg{L["k"]}Nacelle', nac_mesh))
        nac.rotation_mode = 'QUATERNION'
        nac.parent = arm
        nac.parent_type = 'BONE'
        nac.parent_bone = nb
        # nacelle rides on the outer side of bone 1, nozzle aft (down the bone toward the body)
        bm = arm.matrix_world @ ad.bones[nb].matrix_local
        nac.matrix_world = bm @ Matrix.Translation((0, lens[1] * 0.5, rads[1] * 1.9)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z')
        pe, variants = _bolt_thruster(f'{name}Leg{L["k"]}Plume', 5.0, 300 + L['k'])
        pe.parent = nac
        pe.location = (-1.4 * 0.62, 0, 0)
        pe.scale = (0.7, 0.7, 0.7)
        lamp = SFX._link(bpy.data.objects.new(f'{name}Leg{L["k"]}PlumeLight', bpy.data.lights.new(f'{name}Leg{L["k"]}PL', 'POINT')))
        lamp.data.color = GOLD
        lamp.data.energy = 0
        lamp.parent = pe
        lamp.location = (-1.0, 0, 0)
        L.update(nac=nac, plume=pe, var=variants, lamp=lamp)
    root['tethers'] = len(tethers)
    return arm, root, legs, tethers


def pose_arm(arm, leg, bends, twist=0.0):
    """Stills / tests: bend every joint of one leg. bends = list of (about_x, about_z) degrees per joint."""
    from mathutils import Quaternion
    for j, bn in enumerate(leg['bones']):
        pb = arm.pose.bones[bn]
        pb.rotation_mode = 'QUATERNION'
        bx, bz = bends[j] if j < len(bends) else (0, 0)
        pb.rotation_quaternion = Quaternion((1, 0, 0), math.radians(bx)) @ Quaternion((0, 0, 1), math.radians(bz)) @ \
            Quaternion((0, 1, 0), math.radians(twist))
