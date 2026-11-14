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
    nz = n.node('ShaderNodeTexNoise', Scale=5.0, Detail=6.0, Roughness=0.6)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('MULTIPLY', t, 8.0))
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    g = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), p)
    brk = n.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.25, 1.4)
    em = n.node('ShaderNodeEmission', Color=(*col, 1))
    n.set(em.inputs['Strength'], n.math('MULTIPLY', n.math('MULTIPLY', g, brk), k))
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
    mant = _flame_mat('OrbPlumeMantleM', GOLD, 4.0, 1.5)
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
