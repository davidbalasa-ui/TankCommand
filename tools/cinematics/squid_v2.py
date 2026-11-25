"""Arcadian anti-fighter "squid" v2 (2026-11-14, David's brief).

A fighter, not a monster: a sleek nose with eight jointed legs on a collar behind it. Each leg carries
its own thruster pod, so the legs are how it manoeuvres: swept back behind the nose it sprints, spun
round it turns hard, flung forward it grabs a fighter and stabs into it with the leg tips.

squid_v2(variant, pose) builds one at the origin, nose along +X. variant: 'A' dart, 'B' mantis, 'C' orb.
pose: 'sprint' (legs swept back, all thrusters firing aft), 'turn' (legs spun to one side, thrusters
firing sideways), 'grab' (legs flung forward round the target, tips spread to stab).
"""
import math
import os
import sys

import bpy
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'opening'))
import ships as base  # noqa: E402
import arcadian_fleet as AF  # noqa: E402
import forge as F  # noqa: E402
import common as C  # noqa: E402

SPEC = {
    # body: length, max radius, nose sharpness, collar position (fraction from nose), leg segment lengths
    'A': dict(L=11.0, R=0.95, collar=0.32, seg=(3.2, 3.6, 3.0), ring=1.15, tip='lance'),
    'B': dict(L=9.0, R=1.25, collar=0.38, seg=(2.8, 3.0, 2.4), ring=1.45, tip='pincer'),
    'C': dict(L=7.5, R=1.7, collar=0.45, seg=(3.0, 3.4, 2.8), ring=1.85, tip='harpoon'),
}


def _flame_mat():
    m = bpy.data.materials.get('SquidFlame') or C.emit_mat('SquidFlame', (1.0, 0.5, 0.12), 9.0)
    return m


def _flame(p, d, length, r, objs):
    """Exhaust plume from p pointing along d."""
    d = Vector(d).normalized()
    o = C.uv_sphere('Flame', 1.0, seg=(12, 8), mat=_flame_mat(), scale=(length / 2, r, r))
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('X', 'Z')
    o.location = Vector(p) + d * (length / 2)
    o.visible_shadow = False
    objs.append(o)


def _body(v, s):
    L, R = s['L'], s['R']
    x0, x1 = L * (1 - s['collar']), -L * s['collar']        # nose at +x0, tail at x1
    if v == 'A':      # dart: needle nose, slim waist, flared tail cone
        F.tube((x1, 0, 0), (x0, 0, 0), [(0, R * 0.55), (0.12, R * 0.8), (0.4, R), (0.62, R * 0.85), (0.86, R * 0.45),
                                        (1.0, 0.0)], 16, 'shell', sharp=35)
        F.tube((x1 - 0.6, 0, 0), (x1 + 0.4, 0, 0), [(0, R * 0.35), (1, R * 0.6)], 16, 'under')
        for k in range(4):         # four thin keel blades along the spine
            a = math.radians(45 + 90 * k)
            off = Vector((0, math.cos(a), math.sin(a)))
            pts = [tuple(Vector((x, 0, 0)) + off * (R * f)) for x, f in
                   ((x1 + 0.6, 0.8), (x1 + L * 0.35, 1.25), (x0 - L * 0.3, 1.0), (x0 - L * 0.12, 0.6))]
            F.sweep(pts, [(0.05, 0.22)] * 4, 'bronze', sides=4)
        F.sweep([(x0 - L * 0.55, 0, R * 0.92), (x0 - L * 0.2, 0, R * 0.62)], [(0.06, 0.06)] * 2, 'glow', sides=4)
    elif v == 'B':    # mantis: flattened arrowhead with swept head blades
        F.tube((x1, 0, 0), (x0, 0, 0), [(0, R * 0.5), (0.25, R), (0.6, R * 0.9), (0.85, R * 0.5), (1.0, 0.0)], 14,
               'shell', sharp=35)
        for sgn in (-1, 1):
            pts = [(x0 - L * 0.35, sgn * R * 0.6, 0.1), (x0 - L * 0.2, sgn * R * 1.6, 0.2),
                   (x0 - L * 0.55, sgn * R * 2.4, 0.0), (x1 + L * 0.1, sgn * R * 1.9, -0.1)]
            F.sweep(pts, [(0.25, 0.04), (0.3, 0.05), (0.18, 0.04), (0.02, 0.02)], 'bronze', sides=4)
            F.orb((x0 - L * 0.12, sgn * R * 0.45, R * 0.35), 0.18, 'core', seg=(10, 6))   # twin eyes
        F.tube((x1 - 0.5, 0, 0), (x1 + 0.3, 0, 0), [(0, R * 0.3), (1, R * 0.55)], 14, 'under')
    else:             # orb: teardrop shell opened at the front round a big glowing core
        F.tube((x1, 0, 0), (x0, 0, 0), [(0, R * 0.25), (0.3, R * 0.85), (0.62, R), (0.86, R * 0.92), (1.0, R * 0.55)],
               18, 'shell', caps=False, sharp=35)
        F.orb((x0 - R * 0.35, 0, 0), R * 0.62, 'core', seg=(24, 14))
        for k in range(6):         # ribs across the open front
            a = math.radians(60 * k)
            off = Vector((0, math.cos(a), math.sin(a)))
            pts = [tuple(Vector((x0 - R * 0.2, 0, 0)) + off * R * 0.6), tuple(Vector((x0 + R * 0.45, 0, 0)) + off * R * 0.2)]
            F.sweep(pts, [(0.08, 0.08), (0.04, 0.04)], 'bronze', sides=4)
    # the collar ring the legs hang from
    for k in range(16):
        a = 2 * math.pi * k / 16
        F.orb((0, math.cos(a) * s['ring'], math.sin(a) * s['ring']), 0.12, 'bronze', seg=(6, 4))
    F.tube((-0.35, 0, 0), (0.35, 0, 0), [(0, s['ring'] * 0.95), (0.5, s['ring'] * 1.05), (1, s['ring'] * 0.95)], 24,
           'bronze')
    F.tube((-0.4, 0, 0), (0.4, 0, 0), [(0, s['ring'] * 0.85), (1, s['ring'] * 0.85)], 24, 'glow', caps=False)


def _leg_dirs(pose, k):
    """Directions of the three segments of leg k in (axial, radial, tangential) terms."""
    if pose == 'sprint':
        return [(-0.55, 0.85, 0), (-1.0, 0.12, 0), (-1.0, -0.06, 0)]
    if pose == 'grab':
        return [(0.45, 1.0, 0), (1.0, 0.35, 0), (1.0, -0.55, 0)]
    # turn: the legs spun round the body; one side swept back, the other flung out sideways
    w = math.cos(2 * math.pi * k / 8)        # +1 on the outside of the turn
    return [(-0.3, 1.0, 0.5), (-0.6 + 0.6 * w, 0.6 + 0.3 * w, 0.7), (-0.8 + 0.5 * w, 0.1, 0.5)]


def _tip(kind, p, d, up, objs):
    d = Vector(d).normalized()
    if kind == 'lance':
        F.tube(tuple(p), tuple(p + d * 1.9), [(0, 0.16), (0.25, 0.2), (1.0, 0.0)], 6, 'pale', sharp=20)
        F.tube(tuple(p + d * 0.1), tuple(p + d * 0.7), [(0, 0.09), (1, 0.09)], 6, 'glow')
    elif kind == 'pincer':
        side = d.cross(up).normalized()
        for sgn in (-1, 1):
            pts = [p, p + d * 0.6 + side * sgn * 0.45, p + d * 1.3 + side * sgn * 0.35, p + d * 1.7 - side * sgn * 0.05]
            F.sweep([tuple(q) for q in pts], [(0.15, 0.09), (0.13, 0.08), (0.08, 0.05), (0.01, 0.01)], 'pale', sides=5)
        F.orb(tuple(p), 0.2, 'glow', seg=(8, 6))
    else:   # harpoon: a long spike with two back-swept barbs
        F.tube(tuple(p), tuple(p + d * 1.6), [(0, 0.13), (0.8, 0.1), (1.0, 0.0)], 6, 'pale', sharp=20)
        side = d.cross(up).normalized()
        for sgn in (-1, 1):
            q0 = p + d * 1.05
            F.tube(tuple(q0), tuple(q0 - d * 0.55 + side * sgn * 0.4), [(0, 0.06), (1, 0.0)], 4, 'pale', sharp=20)


def squid_v2(variant='A', pose='sprint', name=None):
    s = SPEC[variant]
    name = name or f'SquidV2{variant}_{pose}'
    flames = []
    with AF.gold_palette():
        base._faction('kesh')
        m = F.mark()
        _body(variant, s)
        for k in range(8):
            a = 2 * math.pi * k / 8 + math.pi / 8
            rad = Vector((0, math.cos(a), math.sin(a)))
            tan = Vector((0, -math.sin(a), math.cos(a)))
            ax = Vector((1, 0, 0))
            p = rad * s['ring']
            dirs = _leg_dirs(pose, k)
            for j, (da, dr, dt) in enumerate(dirs):
                d = (ax * da + rad * dr + tan * dt).normalized()
                ln = s['seg'][j]
                q = p + d * ln
                r0, r1 = (0.32, 0.26, 0.2)[j], (0.26, 0.2, 0.15)[j]
                F.tube(tuple(p), tuple(q), [(0, r0), (0.5, r0 * 1.15), (1, r1)], 8, 'shell' if j != 1 else 'bronze',
                       sharp=35)
                F.orb(tuple(p), r0 * 1.3, 'bronze', seg=(10, 6))                 # joint
                F.orb(tuple(p), r0 * 0.7, 'glow', seg=(8, 6))
                if j == 0:     # thruster pod at the elbow: points back along the leg, nozzle glowing
                    pod_c = q - d * 0.2 + rad * 0.35
                    F.tube(tuple(pod_c + d * 0.8), tuple(pod_c - d * 0.9), [(0, 0.1), (0.3, 0.32), (0.85, 0.3), (1, 0.22)],
                           10, 'bronze', sharp=35)
                    F.tube(tuple(pod_c - d * 0.85), tuple(pod_c - d * 0.95), [(0, 0.2), (1, 0.2)], 10, 'glow')
                    if pose == 'sprint':
                        fd = -ax
                    elif pose == 'grab':
                        fd = -ax * 0.6 - rad * 0.4
                    else:
                        fd = -tan
                    flames.append((pod_c - d * 0.95, fd, 3.0 if pose != 'grab' else 1.8, 0.13))
                p = q
            _tip(s['tip'], p, d, ax if abs(d.dot(ax)) < 0.9 else rad, None)
        ob = base._join(F.since(m), name)
    for p, d, ln, r in flames:
        o_list = []
        _flame(p, d, ln, r, o_list)
        o_list[0].parent = ob
    # main drive glow at the tail
    tail = Vector((-s['L'] * s['collar'] - 0.6, 0, 0))
    o_list = []
    _flame(tail, (-1, 0, 0), 3.5 if pose == 'sprint' else 1.5, s['R'] * 0.35, o_list)
    o_list[0].parent = ob
    return ob
