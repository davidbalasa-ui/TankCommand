"""Runs the earlier unit scripts (tools/art/aircraft2.py, hero_units.py, pads_hero.py) on forge.

Those scripts build their shapes with the old kit's primitives. This module stands in for `kit`
and `hero`, so their geometry is reused unchanged while the surface work, baking and export come
from forge. Import it before importing any of those scripts.
"""
import math
import os
import sys
import types

import bpy
import bmesh
from mathutils import Matrix, Vector

import forge as F

ZONE = {
    'terran': {'hull': 'hull', 'turret': 'armor', 'track': 'track', 'barrel': 'barrel', 'dark': 'dark',
               'glow': 'glow', 'amber': 'amber', 'canopy': 'glass'},
    'kesh': {'shell': 'shell', 'fin': 'bronze', 'under': 'under', 'barrel': 'barrel', 'dark': 'under',
             'glow': 'glow', 'core': 'core'},
}


def _z(tile):
    return ZONE.get(F.ST['faction'], {}).get(tile, tile)


def _apply(obj):
    m = obj.matrix_basis.copy()
    obj.data.transform(m)
    if m.determinant() < 0:
        obj.data.flip_normals()
    obj.matrix_basis = Matrix.Identity(4)
    return obj


def mesh_from(name, verts, faces, tile, bevel=0.0, smooth=False, merge=False):
    return F._new(verts, faces, _z(tile), bevel=bevel, sharp=60 if smooth else 30)


def prism(name, profile, y0, y1, tile, bevel=0.0, taper=1.0, smooth=False):
    return F.prism(profile, y0, y1, _z(tile), taper=taper, bevel=bevel, sharp=60 if smooth else 30)


def prism_y(name, profile, x0, x1, tile, bevel=0.0):
    return F.loft([[(x0, y, z) for y, z in profile], [(x1, y, z) for y, z in profile]], _z(tile), bevel=bevel)


def plate(name, outline, z0, z1, tile, bevel=0.0, smooth=False):
    return F.plate(outline, z0, z1, _z(tile), bevel=bevel, sharp=60 if smooth else 30)


def box(name, c, s, tile, bevel=0.0, taper=1.0):
    return F.box(c, s, _z(tile), taper=taper, bevel=bevel)


def cyl(name, p0, p1, r, sides, tile, r1=None, caps=True, smooth=False):
    r1 = r if r1 is None else r1
    return F.tube(p0, p1, [(0, r), (1, max(r1, 1e-4))], sides, _z(tile), caps=caps)


def orb(name, c, r, tile, seg=(10, 6), scale=(1, 1, 1)):
    return F.orb(c, r, _z(tile), seg=(max(seg[0], 14), max(seg[1], 9)), sq=scale)


def rot_z(obj, deg, about=(0, 0, 0)):
    return F.rot(obj, 'Z', deg, about)


def lathe(name, profile, sides, tile, center=(0, 0, 0), smooth=True, top=None, bottom=None, scale=(1, 1)):
    cx, cy, cz = center
    verts, faces = [], []
    n = len(profile)
    for r, z in profile:
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append((cx + r * math.cos(a) * scale[0], cy + r * math.sin(a) * scale[1], cz + z))
    for i in range(n - 1):
        for k in range(sides):
            j = (k + 1) % sides
            faces.append([i * sides + k, i * sides + j, (i + 1) * sides + j, (i + 1) * sides + k])
    if top is not None:
        t = len(verts)
        verts.append((cx, cy, cz + top))
        last = (n - 1) * sides
        faces += [[last + k, last + (k + 1) % sides, t] for k in range(sides)]
    if bottom is not None:
        b = len(verts)
        verts.append((cx, cy, cz + bottom))
        faces += [[(k + 1) % sides, k, b] for k in range(sides)]
    return F._new(verts, faces, _z(tile), sharp=60 if smooth else 30)


def loft(name, sections, ring, tile, smooth=True, cy=0.0):
    rings = []
    for x, w, zt, zb, zm in sections:
        row = []
        for k in range(ring):
            a = 2 * math.pi * k / ring
            c, s = math.cos(a), math.sin(a)
            z = zm + (zt - zm) * s if s > 0 else zm + (zm - zb) * s
            row.append((x, cy + w * c, z))
        rings.append(row)
    return F.loft(rings, _z(tile), sharp=60 if smooth else 30)


def lens(x0, x1, w, zt, zb, zm, n=9, nose=0.55):
    out = []
    for i in range(n):
        t = i / (n - 1)
        k = math.sin(math.pi * t ** nose) if 0 < t < 1 else 0.0
        out.append((x0 + (x1 - x0) * t, w * k, zm + (zt - zm) * k, zm - (zm - zb) * k, zm))
    return out


def join(objs, name):
    return objs[0]


def install():
    """Register this module as `kit` and a stub as `hero` so the old scripts import cleanly."""
    me = sys.modules[__name__]
    me.S = {}
    me.FACTIONS = {'terran': {}, 'kesh': {}}
    sys.modules['kit'] = me
    hero = types.ModuleType('hero')
    hero.ZONES = {'terran': {}, 'kesh': {}}
    hero.H = {}
    hero.zone_material = lambda zone: None
    hero._n = hero._math = None
    sys.modules['hero'] = hero
    old = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    if old not in sys.path:
        sys.path.append(old)
