"""Capital ships for the cinematics, built with the forge kit (tools/art/v2/forge.py).

Ships are cinematic-only (never in the game), so they keep forge's live procedural zone shaders
instead of baking. Front is +X, up is +Z. Sizes are in Blender units; a fighter is about 1.4.
Each builder returns one joined object (plus named sub-objects where a shot needs them).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'art', 'v2'))
import forge as F  # noqa: E402


def _faction(name):
    F.ST['faction'] = name
    F.ST['mats'] = {}


def _join(parts, name):
    for o in parts:
        o.data.materials.clear()
        o.data.materials.append(F.zone_mat(o['zone']))
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    F.ST['parts'] = []
    return obj


# ------------------------------------------------------------------ Terran
def terran_dreadnought(name='Dreadnought'):
    """~34 long. Dark angular wedge, twin spinal guns, turret batteries, cyan strips, orange lights.
    Returns (ship, turret_muzzles) where muzzles are local points the bolts leave from."""
    _faction('terran')
    m = F.mark()
    # main wedge hull
    secs = []
    for x, w, zb, zt in [(-17, 2.6, -1.3, 1.5), (-12, 3.4, -1.7, 2.0), (-4, 3.8, -1.9, 2.2),
                         (6, 3.3, -1.6, 1.8), (13, 2.2, -1.0, 1.2), (18, 0.7, -0.3, 0.5)]:
        secs.append((x, [(0, zb), (w * 0.62, zb * 0.92), (w, zb * 0.25), (w * 0.92, zt * 0.45),
                         (w * 0.55, zt), (0, zt * 1.08)]))
    F.hull(secs, 'hull', bevel=0.06)
    # armour sponsons along both sides
    for x0, x1 in [(-14, -5), (-3, 8)]:
        F.sym(F.box(((x0 + x1) / 2, 3.75, -0.2), ((x1 - x0) / 2, 0.55, 0.85), 'armor', taper=0.8, bevel=0.06))
        # cyan strip on each sponson
        F.sym(F.box(((x0 + x1) / 2, 4.31, 0.05), ((x1 - x0) / 2 - 0.4, 0.02, 0.06), 'glow'))
    # dorsal superstructure stack + bridge
    F.box((-9, 0, 2.5), (5.0, 1.6, 0.6), 'armor', taper=0.75, bevel=0.05)
    F.box((-10.5, 0, 3.4), (2.8, 1.1, 0.5), 'plate', taper=0.7, bevel=0.05)
    F.box((-11.2, 0, 4.15), (1.4, 0.8, 0.35), 'armor', taper=0.7, bevel=0.04)
    F.box((-10.05, 0, 4.2), (0.18, 0.62, 0.12), 'glass')
    F.cyl((-12, 0, 4.4), (-12, 0, 6.2), 0.08, 6, 'barrel')        # antenna mast
    F.orb((-12, 0, 6.25), 0.12, 'amber')
    for k in range(4):                                              # vent banks
        F.sym(F.box((-13 + k * 1.6, 1.62, 2.5), (0.6, 0.04, 0.3), 'vent'))
    # twin spinal guns on the bow
    for y in (-0.75, 0.75):
        F.cyl((-2, y, 2.25), (19.5, y, 1.6), 0.32, 10, 'barrel')
        F.cyl((19.5, y, 1.6), (20.3, y, 1.57), 0.38, 10, 'armor')
        F.cyl((16, y, 1.71), (18.6, y, 1.63), 0.36, 10, 'coil')
    F.box((3, 0, 2.15), (5.5, 1.3, 0.35), 'armor', taper=0.7, bevel=0.05)
    # turret batteries (dorsal 3, plus 2 on each sponson top)
    muzzles = []
    tur = [(-2.5, 0, 2.55), (-16, 0, 2.0)] + [(x, s * 3.75, 0.7) for x in (-11, -6, 0, 5) for s in (-1, 1)]
    for (x, y, z) in tur:
        F.orb((x, y, z), 0.55, 'plate', seg=(12, 6), sq=(1, 1, 0.45))
        F.box((x + 0.1, y, z + 0.35), (0.6, 0.45, 0.22), 'armor', taper=0.7, bevel=0.03)
        for dy in (-0.17, 0.17):
            F.cyl((x + 0.4, y + dy, z + 0.38), (x + 2.0, y + dy, z + 0.42), 0.07, 6, 'barrel')
        muzzles.append(Vector((x + 2.05, y, z + 0.42)))
    # engines
    for (y, z, r) in [(0, 0.2, 1.15), (-2.1, -0.5, 0.8), (2.1, -0.5, 0.8), (0, -1.3, 0.7)]:
        F.tube((-16.6, y, z), (-18.6, y, z), [(0, r * 0.9), (0.3, r), (1, r * 1.12)], 14, 'dark', caps=False)
        F.cyl((-18.0, y, z), (-18.1, y, z), r * 0.95, 14, 'glow')
    # running lights + hangar slot glow
    for x in (-15, -7, 1, 9):
        F.sym(F.orb((x, 3.0, 1.2), 0.1, 'amber', seg=(8, 5)))
    F.sym(F.box((-1, 3.38, -1.1), (3.0, 0.04, 0.22), 'glass'))
    F.box((10, 0, -1.55), (4, 0.12, 0.05), 'glow')
    ship = _join(F.since(m), name)
    return ship, muzzles


def terran_frigate(name='Frigate'):
    """~14 long escort. Same language, smaller."""
    _faction('terran')
    m = F.mark()
    secs = []
    for x, w, zb, zt in [(-7, 1.4, -0.8, 0.9), (-2, 1.8, -1.0, 1.2), (4, 1.4, -0.7, 0.9), (8, 0.4, -0.2, 0.3)]:
        secs.append((x, [(0, zb), (w * 0.62, zb * 0.92), (w, zb * 0.25), (w * 0.92, zt * 0.45),
                         (w * 0.55, zt), (0, zt * 1.08)]))
    F.hull(secs, 'hull', bevel=0.04)
    F.box((-3.5, 0, 1.5), (2.2, 0.8, 0.4), 'armor', taper=0.7, bevel=0.04)
    F.box((-2.4, 0, 1.6), (0.1, 0.5, 0.1), 'glass')
    F.sym(F.box((-1, 1.95, 0), (4.0, 0.3, 0.45), 'armor', taper=0.8, bevel=0.03))
    F.sym(F.box((-1, 2.26, 0.05), (3.6, 0.02, 0.05), 'glow'))
    F.cyl((0, 0, 1.3), (9.0, 0, 0.75), 0.18, 8, 'barrel')
    for (y, r) in [(-0.8, 0.55), (0.8, 0.55)]:
        F.tube((-6.8, y, 0), (-8.1, y, 0), [(0, r * 0.9), (1, r * 1.1)], 12, 'dark', caps=False)
        F.cyl((-7.7, y, 0), (-7.8, y, 0), r * 0.95, 12, 'glow')
    F.sym(F.orb((-5, 1.4, 0.8), 0.08, 'amber', seg=(8, 5)))
    return _join(F.since(m), name)


# ------------------------------------------------------------------ Kesh
def kesh_mothership(name='Mothership'):
    """~46 across. Hovering lens of etched silver plates, bronze belly, crescent fins all round,
    gold core orb in a cradle. Returns (ship, core_point)."""
    _faction('kesh')
    m = F.mark()
    lens = F.lensfn(-20, 24, 13, 4.5, -3.5, 0.0, nose=0.7, tail=0.8)
    F.body(lens, 'under', nu=22, nv=24)
    for i, (u0, u1) in enumerate([(0.0, 0.32), (0.2, 0.55), (0.42, 0.78), (0.65, 1.0)]):
        for vc in (40, 90, 140):
            F.shell(lens, u0, u1, vc + (i % 2) * 8 - 4, 70, 'shell', nu=10, nv=6, thick=0.35, off=0.15,
                    lift=0.35, skew=6)
    for vc in (215, 270, 325):
        F.shell(lens, 0.15, 0.9, vc, 60, 'bronze', nu=10, nv=5, thick=0.3, off=0.1)
    # crescent fins sweeping back from the rim
    for k, (r, a0, a1, z) in enumerate([(14.2, 70, 175, 0.4), (15.4, 95, 200, -0.6), (16.6, 120, 215, -1.5)]):
        F.crescent((1, 0, z), r, a0, a1, 1.3 - k * 0.15, 0.45, 'shell', n=22, sq=(1.25, 1.0))
        F.crescent((1, 0, z), r, -a1, -a0, 1.3 - k * 0.15, 0.45, 'shell', n=22, sq=(1.25, 1.0))
    # tall dorsal fins
    for x, h in [(-6, 7.5), (2, 9.5)]:
        F.crescent((x - 8, 0, 3.0), h, -10, 80, 1.1, 0.4, 'bronze', n=14, plane='xz', up=(0, 1, 0))
    # core cradle and orb near the bow
    F.lathe([(0.0, 5.2), (3.4, 5.0), (4.6, 6.0), (4.2, 6.8), (3.8, 6.4), (2.6, 5.6)], 28, 'bronze',
            center=(8, 0, 0), caps=False)
    F.orb((8, 0, 8.4), 3.4, 'core', seg=(28, 18))
    F.orb((8, 0, 8.4), 3.9, 'glow', seg=(6, 4), sq=(1, 1, 0.05))   # glowing equator ring
    for a in range(0, 360, 60):
        x, y = 8 + 4.8 * math.cos(math.radians(a)), 4.8 * math.sin(math.radians(a))
        F.crescent((8, 0, 8.4), 4.6, a - 25, a + 25, 0.5, 0.25, 'shell', n=8, plane='xy')
    # glowing rib seams on the belly and rim slots
    F.body(F.lensfn(-18, 21, 11.9, 0.3, -3.25, 0.0, nose=0.7, tail=0.8), 'slat', nu=14, nv=16, u0=0.1, u1=0.9)
    for k in range(9):
        u = 0.1 + k * 0.1
        for v in (0, 180):
            F.orb(tuple(lens(u, v, 0.25)), 0.35, 'glow', seg=(8, 5))
    ship = _join(F.since(m), name)
    return ship, Vector((8, 0, 8.4))


def kesh_cruiser(name='Cruiser'):
    """~16 long crescent cruiser with a gold orb gun at the bow."""
    _faction('kesh')
    m = F.mark()
    lens = F.lensfn(-8, 9, 3.6, 1.6, -1.4, 0.0, nose=0.6, tail=0.9)
    F.body(lens, 'under', nu=14, nv=14)
    for u0, u1 in [(0.0, 0.45), (0.3, 0.75), (0.6, 1.0)]:
        F.shell(lens, u0, u1, 90, 120, 'shell', nu=8, nv=6, thick=0.18, off=0.06, lift=0.15)
    F.sym(F.crescent((-1, 0, -0.2), 7.5, 110, 200, 0.9, 0.3, 'shell', n=14))
    F.crescent((-4, 0, 1.0), 4.0, 0, 85, 0.6, 0.25, 'bronze', n=10, plane='xz', up=(0, 1, 0))
    F.orb((8.5, 0, 0.2), 1.0, 'core', seg=(18, 12))
    F.crescent((8.5, 0, 0.2), 1.35, 60, 300, 0.25, 0.18, 'bronze', n=12, plane='xy')
    F.body(F.lensfn(-7, 7.5, 3.3, 0.2, -1.3, 0.0, nose=0.6, tail=0.9), 'slat', nu=8, nv=10, u0=0.15, u1=0.85)
    ship = _join(F.since(m), name)
    return ship, Vector((8.5, 0, 0.2))
