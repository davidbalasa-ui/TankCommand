"""Terran (human) fleet for the pre-rendered cinematics. Never used in the game, so no phone budget.

    broadside_battleship() -> (ship, muzzles)   three huge fixed cannons on the -Y side; muzzles are
                                                local points, ship['fire_dir'] = (0, -1, 0)
    terran_corvette()      -> ship              fork-prowed fast attack ship, ~10 long
    terran_frigate_v2()    -> ship              trimaran gun frigate, ~21 long
    twin_x_fighter()       -> (ship, wings)     ship = the central core; wings = name of the child object
                                                holding all 8 free-floating wings (plasma arcs are its
                                                children); spin it round its local X axis
    missile_ship()         -> (ship, tubes)     tubes = local centre points of the two bow tube mouths
    missile()              -> missile object    points along +X, origin at its middle
    muzzle_flash()         -> emissive flash    fires along +X from its origin (for the cannon shots)

Front is +X, up is +Z. Each builder joins its parts into one object with the live forge zone
shaders and stores the number of separate shapes in ship['shapes'].
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'art', 'v2'))
import forge as F  # noqa: E402
import ships as base  # noqa: E402
import ships_hd as hd  # noqa: E402

_finish = hd._finish
_greeble = hd._greeble


# ------------------------------------------------------------------ shared pieces
def _prof(kind, w, zb, zt):
    """Half cross-section. 'wedge' is the dreadnought family, 'slab' has flat vertical sides."""
    if kind == 'slab':
        return [(0, zb), (w * 0.7, zb), (w, zb * 0.45), (w, zt * 0.45), (w * 0.7, zt), (0, zt)]
    return [(0, zb), (w * 0.62, zb * 0.92), (w, zb * 0.25), (w * 0.92, zt * 0.45), (w * 0.55, zt), (0, zt * 1.08)]


def _hull(secs, kind, zone='hull', bevel=0.05, y=0.0):
    o = F.hull([(x, _prof(kind, w, zb, zt)) for x, w, zb, zt in secs], zone, bevel=bevel)
    if y:
        F.move(o, (0, y, 0))
    return o


def _sec(secs, x):
    if x <= secs[0][0]:
        return secs[0][1:]
    for a, b in zip(secs, secs[1:]):
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
    return secs[-1][1:]


def _nozzle(p, d, r, L, glow='glow', sides=14, zone='dark'):
    """Thruster bell opening along direction d from point p, with a glowing throat."""
    p, d = Vector(p), Vector(d).normalized()
    F.tube(p, p + d * L, [(0, r * 0.55), (0.25, r * 0.8), (1, r)], sides, zone, caps=False)
    F.tube(p + d * L * 0.02, p + d * L, [(0, r * 0.62), (0.25, r * 0.88), (1, r * 1.08)], sides, 'armor', caps=False)
    F.cyl(p + d * L * 0.3, p + d * L * 0.36, r * 0.8, sides, glow)


def _engine(x, y, z, r, L=None, sides=16, glow='glow'):
    """Main engine pointing aft (-X) with ribbed shroud, vanes and a glowing core."""
    L = L or r * 1.9
    F.tube((x, y, z), (x - L, y, z), [(0, r * 0.9), (0.3, r), (1, r * 1.12)], sides, 'dark', caps=False)
    F.cyl((x - L * 0.68, y, z), (x - L * 0.74, y, z), r * 0.97, sides, glow)
    for k in range(4):
        F.cyl((x - L * (0.08 + 0.2 * k), y, z), (x - L * (0.15 + 0.2 * k), y, z), r * (1.05 + 0.03 * k), sides, 'armor')
    for a in range(0, 360, 45):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        F.box((x - L * 0.9, y + ca * r * 0.5, z + sa * r * 0.5),
              (0.03 * r + 0.02, 0.02 * r + abs(sa) * r * 0.4, 0.02 * r + abs(ca) * r * 0.4), 'plate')


def _turret(x, y, z, r, barrels=2, up=1):
    """Small conventional turret (the dreadnought's design); up=-1 hangs it under the hull."""
    F.orb((x, y, z), r, 'plate', seg=(12, 6), sq=(1, 1, 0.45))
    F.box((x + 0.18 * r, y, z + up * 0.62 * r), (1.1 * r, 0.8 * r, 0.4 * r), 'armor', taper=0.7 if up > 0 else 1.0,
          bevel=0.03 * r)
    offs = [0] if barrels == 1 else [(-0.3 + 0.6 * i / (barrels - 1)) * r for i in range(barrels)]
    for dy in offs:
        F.cyl((x + 0.7 * r, y + dy, z + up * 0.7 * r), (x + 3.6 * r, y + dy, z + up * 0.75 * r), 0.12 * r, 6, 'barrel')
        F.cyl((x + 3.3 * r, y + dy, z + up * 0.75 * r), (x + 3.7 * r, y + dy, z + up * 0.76 * r), 0.16 * r, 6, 'dark')
    F.box((x + 0.95 * r, y, z + up * 0.95 * r), (0.15 * r, 0.3 * r, 0.03 * r), 'glow')


def _dress(rnd, secs, kind, x0, x1, k=1.0, greebles=0, deck_ok=None, side_ok=None, rows=2, y=0.0, belly=0):
    """Surface detail for a hull built with _hull: deck armour plates, window rows, panel seams,
    deck greebles, keel ribs, running lights. k scales the detail size; y offsets (outriggers)."""
    slab = kind == 'slab'
    tf, sy, slo = (0.68, 1.0, 0.45) if slab else (0.5, 0.965, 0.25)
    x = x0
    while x < x1:
        w, zb, zt = _sec(secs, x)
        L = rnd.uniform(0.7, 1.5) * k
        n = max(2, int(w * 2 * tf / (0.6 * k)))
        for j in range(n):
            py = -w * tf + (j + 0.5) * (2 * w * tf / n)
            if rnd.random() < 0.85 and (deck_ok is None or deck_ok(x + L / 2, py)):
                F.box((x + L / 2, py + y, zt * (1.0 if slab else 1.04)), (L / 2 - 0.04 * k, w * tf / n - 0.04 * k, 0.05 * k),
                      rnd.choice(('armor', 'plate', 'hull')), taper=0.85)
        x += L
    for s in (-1, 1):
        for r in range(rows):
            x = x0 + 0.3 * k
            while x < x1 - 0.3 * k:
                w, zb, zt = _sec(secs, x)
                z = zb * slo + (zt * 0.45 - zb * slo) * (r + 0.7) / (rows + 0.4)
                if (side_ok is None or side_ok(x, s)) and rnd.random() < 0.8:
                    F.box((x, s * w * sy + y, z), (0.06 * k, 0.03 * k, 0.035 * k),
                          rnd.choice(('amber', 'glass', 'glass', 'glow')))
                x += 0.32 * k
        x = x0 + 0.5 * k
        while x < x1:
            w, zb, zt = _sec(secs, x)
            if side_ok is None or side_ok(x, s):
                F.box((x, s * w * (sy + 0.015) + y, (zb * slo + zt * 0.45) / 2), (0.02 * k, 0.02 * k, (zt * 0.45 - zb * slo) * 0.42),
                      'dark')
            F.box((x, s * w * 0.82 + y, zb * (0.72 if slab else 0.6)), (0.08 * k, 0.06 * k, 0.25 * k), 'armor')
            x += rnd.uniform(0.9, 1.6) * k
        x = x0
        while x < x1:
            w, zb, zt = _sec(secs, x)
            F.orb((x, s * w * (1.0 if slab else 0.92) + y, zt * 0.45), 0.06 * k, 'amber' if int(x / k) % 3 else 'red',
                  seg=(6, 4))
            x += 1.0 * k
    for _ in range(greebles):
        gx = rnd.uniform(x0, x1)
        w, zb, zt = _sec(secs, gx)
        gy = rnd.uniform(-w * tf, w * tf)
        if deck_ok is None or deck_ok(gx, gy):
            _greeble(rnd, gx, gy + y, zt * (1.0 if slab else 1.09) + 0.05 * k, 0.55 * k)
    for _ in range(belly):
        gx = rnd.uniform(x0, x1)
        w, zb, zt = _sec(secs, gx)
        gy = rnd.uniform(-w * 0.55, w * 0.55)
        F.box((gx, gy + y, zb * (1.0 if slab else 0.95)), (rnd.uniform(0.1, 0.5) * k, rnd.uniform(0.08, 0.3) * k, 0.06 * k),
              rnd.choice(('armor', 'dark', 'plate', 'vent')))


def _bridge(x, z, k=1.0):
    """Stepped command tower with a glass band and a sensor mast, front face at +X."""
    F.box((x, 0, z + 0.55 * k), (2.6 * k, 1.5 * k, 0.55 * k), 'armor', taper=0.75, bevel=0.05 * k)
    F.box((x - 0.5 * k, 0, z + 1.5 * k), (1.7 * k, 1.05 * k, 0.45 * k), 'plate', taper=0.7, bevel=0.05 * k)
    F.box((x - 0.8 * k, 0, z + 2.25 * k), (1.0 * k, 0.75 * k, 0.33 * k), 'armor', taper=0.7, bevel=0.04 * k)
    F.box((x + 0.2 * k, 0, z + 2.3 * k), (0.06 * k, 0.6 * k, 0.11 * k), 'glass')
    F.box((x + 0.21 * k, 0, z + 2.3 * k), (0.06 * k, 0.5 * k, 0.03 * k), 'glow')
    for j in range(10):
        F.sym(F.box((x - 2.0 * k + j * 0.42 * k, 1.5 * k, z + 0.5 * k), (0.12 * k, 0.03 * k, 0.04 * k),
                    'glass' if j % 3 else 'amber'))
        F.sym(F.box((x - 1.7 * k + j * 0.26 * k, 1.03 * k, z + 1.5 * k), (0.07 * k, 0.03 * k, 0.03 * k), 'glass'))
    F.cyl((x - 1.3 * k, 0, z + 2.5 * k), (x - 1.3 * k, 0, z + 4.4 * k), 0.06 * k, 6, 'barrel')
    F.orb((x - 1.3 * k, 0, z + 4.45 * k), 0.1 * k, 'amber', seg=(8, 5))
    for j in range(5):
        F.sym(F.cyl((x - 1.3 * k, 0, z + (2.9 + j * 0.3) * k), (x - 1.3 * k, (0.35 + j * 0.05) * k, z + (2.9 + j * 0.3) * k),
                    0.018 * k, 4, 'barrel'))
    F.lathe([(0.0, 0.0), (0.4 * k, 0.1 * k), (0.45 * k, 0.18 * k)], 12, 'plate', center=(x - 0.2 * k, 0.6 * k, z + 1.98 * k))
    F.cyl((x - 0.2 * k, 0.6 * k, z + 1.95 * k), (x - 0.2 * k, 0.6 * k, z + 2.25 * k), 0.025 * k, 4, 'barrel')


def _emit_mat(name, col, strength, soft=0.0, alpha=1.0):
    """Emission-only material. soft > 0 fades it out towards the silhouette (power of the facing
    angle), so a simple cone or ball renders as a soft-edged flame instead of a hard shape."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value = (*col, 1)
    em.inputs[1].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    if soft > 0:
        lw = nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.5
        inv = nt.nodes.new('ShaderNodeMath')
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        nt.links.new(lw.outputs['Facing'], inv.inputs[1])
        pw = nt.nodes.new('ShaderNodeMath')
        pw.operation = 'POWER'
        nt.links.new(inv.outputs[0], pw.inputs[0])
        pw.inputs[1].default_value = soft
        mu = nt.nodes.new('ShaderNodeMath')
        mu.operation = 'MULTIPLY'
        mu.use_clamp = True
        nt.links.new(pw.outputs[0], mu.inputs[0])
        mu.inputs[1].default_value = alpha
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(mu.outputs[0], mix.inputs[0])
        nt.links.new(nt.nodes.new('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
    return mat


def _soft(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.visible_shadow = False
    return obj


# ================================================================== broadside battleship
B_SECS = [(-22, 3.6, -2.7, 2.8), (-16, 4.4, -3.2, 3.3), (-4, 4.6, -3.4, 3.4), (10, 4.4, -3.2, 3.2),
          (17, 3.4, -2.4, 2.4), (21, 2.3, -1.6, 1.5), (23.5, 1.1, -0.7, 0.7)]
B_GUNS = (11.0, 0.0, -11.0)   # x of each cannon, bow first
B_GUN_R, B_GUN_L = 0.78, 0.6        # cannon diameter / length factors (1, 1 = the first, oversized design)
B_ROOT_Y = 4.2
B_MUZZLE_Y = B_ROOT_Y + (19.6 - B_ROOT_Y) * B_GUN_L


def _broadside_gun(gx, s=-1, gz=0.0):
    """One giant fixed cannon firing sideways (s = -1: towards -Y). Returns the muzzle point."""
    c = (gx, 0, gz)
    m0 = F.mark()
    o = F.tube((gx, s * 4.2, gz), (gx, s * 7.0, gz), [(0, 3.15), (0.55, 2.95), (1, 2.15)], 8, 'armor', bevel=0.08)
    F.rot(o, 'Y', 22.5, c)                                                    # casemate collar
    F.cyl((gx, s * 6.98, gz), (gx, s * 7.25, gz), 2.2, 20, 'hazard')
    F.cyl((gx, s * 7.2, gz), (gx, s * 9.2, gz), 1.8, 20, 'plate')              # recoil sleeve
    for a in range(0, 360, 30):                                                # sleeve bolts
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        F.cyl((gx + ca * 1.95, s * 7.3, gz + sa * 1.95), (gx + ca * 1.95, s * 8.8, gz + sa * 1.95), 0.11, 6, 'barrel')
    F.cyl((gx, s * 9.2, gz), (gx, s * 17.8, gz), 1.22, 20, 'armor')            # barrel
    for j in range(7):                                                         # charging coils
        y0 = 9.75 + j * 1.12
        F.cyl((gx, s * y0, gz), (gx, s * (y0 + 0.36), gz), 1.48, 20, 'plate')
        F.cyl((gx, s * (y0 + 0.52), gz), (gx, s * (y0 + 0.7), gz), 1.3, 20, 'glow')
        F.cyl((gx, s * (y0 + 0.78), gz), (gx, s * (y0 + 0.92), gz), 1.36, 20, 'dark')
    for a in (45, 135, 225, 315):                                              # accelerator rails
        m = F.mark()
        F.box((gx, s * 13.5, gz + 1.66), (0.26, 3.9, 0.16), 'plate', bevel=0.03)
        F.box((gx, s * 13.5, gz + 1.84), (0.06, 3.6, 0.025), 'glow')
        F.box((gx, s * 9.5, gz + 1.9), (0.36, 0.4, 0.32), 'armor', bevel=0.03)
        F.box((gx, s * 17.3, gz + 1.72), (0.34, 0.3, 0.22), 'armor', bevel=0.03)
        F.rot_all(m, 'Y', a, c)
    F.tube((gx, s * 17.8, gz), (gx, s * 19.6, gz), [(0, 1.4), (0.14, 1.82), (0.86, 1.82), (1, 1.62)], 20, 'armor',
           caps=False)                                                         # muzzle brake
    F.tube((gx, s * 19.6, gz), (gx, s * 16.4, gz), [(0, 1.62), (0.06, 1.08), (1, 1.02)], 20, 'dark', caps=False)
    F.cyl((gx, s * 17.0, gz), (gx, s * 16.9, gz), 1.04, 20, 'glow')            # charge glow deep in the bore
    for a in range(0, 360, 45):                                                # brake vents
        m = F.mark()
        F.box((gx, s * 18.7, gz + 1.81), (0.3, 0.5, 0.05), 'vent')
        F.box((gx, s * 19.42, gz + 1.82), (0.12, 0.05, 0.04), 'amber')
        F.rot_all(m, 'Y', a + 22.5, c)
    for a in (0, 90, 180, 270):                                                # braces to the hull
        m = F.mark()
        F.cyl((gx, s * 5.6, gz + 3.0), (gx, s * 11.2, gz + 1.45), 0.2, 8, 'barrel')
        F.rot_all(m, 'Y', a, c)
    for o in F.since(m0):                       # the gun is modelled full size, then scaled about its root
        F.scale(o, (B_GUN_R, B_GUN_L, B_GUN_R), about=(gx, s * B_ROOT_Y, gz))
    # far side: breech block and recoil thruster
    F.box((gx, -s * 5.1, gz), (2.5, 1.0, 2.5), 'armor', bevel=0.08)
    F.box((gx, -s * 6.0, gz), (1.9, 0.35, 1.9), 'plate', bevel=0.06)
    _nozzle((gx, -s * 6.2, gz), (0, -s, 0), 1.5, 1.9, glow='amber', sides=18)
    for dx in (-1.9, 1.9):
        for dz in (-1.5, 1.5):
            _nozzle((gx + dx, -s * 6.0, gz + dz), (0, -s, 0), 0.38, 0.6, glow='amber', sides=10)
    return Vector((gx, s * B_MUZZLE_Y, gz))


def broadside_battleship(name='Broadside'):
    """~46 long, ~25 across. A slab-sided gun carriage built round three giant cannons that run
    straight through the beam and fire out of the -Y side: casemate collar, coil-ringed barrel
    and muzzle brake on the gun side, breech block and a recoil thruster on the far side. Big
    amber manoeuvring thrusters at all eight corners roll the ship to aim.
    Returns (ship, muzzles); muzzles = local points, bow gun first. ship['fire_dir'] = (0,-1,0)."""
    rnd = random.Random(23)
    base._faction('terran')
    m = F.mark()
    _hull(B_SECS, 'slab', bevel=0.07)

    def deck_ok(x, y):
        if -21 < x < -13 and abs(y) < 2.2:
            return False                                   # bridge
        if any(abs(x - g) < 2.1 for g in B_GUNS):
            return False                                   # power conduits
        if any(abs(x - t) < 1.6 for t in (-5.5, 5.5, 15.5)) and abs(y) < 1.6:
            return False                                   # turrets
        return True

    def side_ok(x, s):
        return not any(abs(x - g) < (2.9 if s < 0 else 2.8) for g in B_GUNS) and not (abs(x - 18) < 1.6 or abs(x + 19.3) < 1.6)

    _dress(rnd, B_SECS, 'slab', -21.5, 21.5, k=1.0, greebles=2600, deck_ok=deck_ok, side_ok=side_ok, rows=4, belly=700)

    muzzles = [_broadside_gun(gx) for gx in B_GUNS]

    # power conduits over the deck feeding each cannon, with a capacitor drum
    for gx in B_GUNS:
        w, zb, zt = _sec(B_SECS, gx)
        for dx in (-1.25, 0, 1.25):
            F.cyl((gx + dx, -w * 0.72, zt + 0.32), (gx + dx, w * 0.72, zt + 0.32), 0.3, 10, 'armor')
            for j in range(6):
                yy = -w * 0.6 + j * w * 0.24
                F.cyl((gx + dx, yy, zt + 0.32), (gx + dx, yy + 0.16, zt + 0.32), 0.345, 10, 'glow' if j % 2 else 'plate')
            F.cyl((gx + dx, -w * 0.72, zt + 0.32), (gx + dx, -w * 0.98, zt * 0.5), 0.3, 10, 'armor')
        F.lathe([(0.0, 0.95), (0.9, 0.9), (1.25, 0.6), (1.3, 0.0)], 12, 'plate', center=(gx, 1.2, zt + 0.5))
        F.lathe([(1.34, 0.25), (1.34, 0.4)], 12, 'glow', center=(gx, 1.2, zt + 0.5))
        for dx in (-1.9, 1.9):                               # radiator fins either side
            for j in range(7):
                F.box((gx + dx, -2.4 + j * 0.8, zt + 0.5), (0.05, 0.3, 0.5), 'vent')

    # manoeuvring thruster clusters at the eight corners
    for tx in (18.0, -19.3):
        w, zb, zt = _sec(B_SECS, tx)
        for sy in (-1, 1):
            for sz in (-1, 1):
                zc = sz * abs(zt) * 0.72
                F.box((tx, sy * (w + 0.35), zc), (1.5, 0.75, 0.75), 'armor', bevel=0.06)
                F.box((tx, sy * (w + 0.35), zc), (1.56, 0.5, 0.5), 'plate', bevel=0.04)
                for dx in (-0.75, 0.75):
                    _nozzle((tx + dx, sy * (w + 1.0), zc), (0, sy, 0), 0.52, 0.7, glow='amber', sides=12)
                    _nozzle((tx + dx, sy * (w + 0.35), zc + sz * 0.7), (0, 0, sz), 0.52, 0.7, glow='amber', sides=12)
                F.box((tx, sy * (w + 1.12), zc + sz * 0.6), (1.3, 0.02, 0.05), 'amber')

    # bridge tower aft, dorsal turrets, point defence along the deck edges
    _bridge(-16.5, 3.2, 1.15)
    for tx in (-5.5, 5.5, 15.5):
        w, zb, zt = _sec(B_SECS, tx)
        F.cyl((tx, 0, zt), (tx, 0, zt + 0.25), 1.1, 12, 'armor')
        _turret(tx, 0, zt + 0.3, 0.75, barrels=3)
    x = -21
    while x < 20:
        w, zb, zt = _sec(B_SECS, x)
        for s in (-1, 1):
            _turret(x, s * w * 0.6, zt + 0.05, 0.2, barrels=rnd.choice((1, 2)))
            _turret(x + 0.9, s * w * 0.6, zb - 0.05, 0.2, barrels=2, up=-1)
        x += 2.3

    # armoured prow: ram plates and a bow sensor slit
    F.sym(F.prism([(15.5, -1.9), (23.9, -0.35), (23.9, 0.35), (15.5, 1.9)], 3.55, 3.85, 'armor', bevel=0.05))
    F.box((23.6, 0, 0), (0.25, 0.9, 0.12), 'glow')
    F.box((20.5, 0, 1.75), (2.0, 0.9, 0.22), 'armor', taper=0.7, bevel=0.04)
    # keel: ventral fin with a long cyan strip
    F.prism([(-17, -3.2), (12, -3.2), (9, -4.3), (-15, -4.3)], -0.8, 0.8, 'armor', bevel=0.06)
    F.sym(F.box((-3, 0.82, -3.8), (10.5, 0.02, 0.07), 'glow'))
    # long cyan strips on the far side and under the gun side chamfer
    for (x0, x1) in [(-18.5, -14.2), (-7.6, -3.3), (3.3, 7.6), (14.2, 16.2)]:
        F.sym(F.box(((x0 + x1) / 2, 4.5, 0.0), ((x1 - x0) / 2, 0.16, 0.5), 'armor', bevel=0.04))
        F.sym(F.box(((x0 + x1) / 2, 4.67, 0.0), ((x1 - x0) / 2 - 0.25, 0.02, 0.07), 'glow'))

    # engines: three large, four small
    for (y, z, r) in [(0, 0.3, 1.5), (-2.3, -0.5, 1.0), (2.3, -0.5, 1.0), (-1.7, 1.9, 0.5), (1.7, 1.9, 0.5),
                      (-1.3, -1.9, 0.5), (1.3, -1.9, 0.5)]:
        _engine(-21.6, y, z, r)

    ship = _finish(m, name)
    ship['fire_dir'] = (0.0, -1.0, 0.0)
    ship['muzzles'] = [tuple(p) for p in muzzles]
    return ship, muzzles


def muzzle_flash(name='Flash', scale=1.0, bolt_at=7.0, bolt=True, charge=False, col=(0.45, 0.85, 1.0), strength=40.0):
    """Emissive cannon blast firing along +X from the origin: white-hot core flare inside a soft
    cyan halo, four jets thrown forward out of the brake vents and (bolt=True) the slug at bolt_at
    units downrange. charge=True gives only the ball of light building in the muzzle. Sized for the
    broadside cannon at scale 1. Returns the core object; the see-through halo is its child."""
    base._faction('terran')
    k = scale
    F.ST['parts'] = []
    if charge:
        F.orb((-0.5 * k, 0, 0), 1.0 * k, 'glow', seg=(16, 10))
    else:
        F.tube((-0.4 * k, 0, 0), (10 * k, 0, 0), [(0, 0.5 * k), (0.03, 1.3 * k), (0.08, 1.7 * k), (0.16, 1.3 * k), (0.3, 0.8 * k), (0.6, 0.35 * k), (1, 0.0)], 24, 'glow')
    if bolt:
        F.tube((bolt_at, 0, 0), (bolt_at + 15 * k, 0, 0), [(0, 0.0), (0.02, 0.3 * k), (0.06, 0.55 * k), (0.4, 0.5 * k), (0.8, 0.3 * k), (1, 0.0)], 16, 'glow')
    core = base._join(F.since(0), name)
    _soft(core, _emit_mat(f'flash_{strength:.0f}', (0.75, 0.93, 1.0), strength * 0.4, soft=2.5))
    if charge:
        F.orb((-0.3 * k, 0, 0), 1.7 * k, 'glow', seg=(16, 10))
    else:
        F.tube((-0.6 * k, 0, 0), (14 * k, 0, 0), [(0, 0.8 * k), (0.03, 1.9 * k), (0.08, 2.4 * k), (0.16, 2.1 * k), (0.3, 1.5 * k), (0.6, 0.8 * k), (1, 0.0)], 24, 'glow')
        for a in range(0, 360, 45):          # short puffs out of the eight brake vents
            o = F.tube((-1.1 * k, 0, 1.7 * k), (-0.4 * k, 0, 3.3 * k), [(0, 0.25 * k), (0.3, 0.42 * k), (0.6, 0.3 * k), (1, 0.0)], 10, 'glow')
            F.rot(o, 'X', a + 22.5)
    if bolt:
        F.tube((bolt_at - 4 * k, 0, 0), (bolt_at + 17 * k, 0, 0), [(0, 0.0), (0.1, 0.8 * k), (0.25, 1.3 * k), (0.6, 1.1 * k), (0.85, 0.6 * k), (1, 0.0)], 16, 'glow')
    halo = base._join(F.since(0), name + '_Halo')
    _soft(halo, _emit_mat(f'halo_{strength:.0f}', (0.05, 0.42, 1.0), strength * 0.07, soft=2.0, alpha=0.8))
    halo.parent = core
    return core


# ================================================================== corvette
C_SECS = [(-4.2, 0.8, -0.5, 0.55), (-2.5, 1.15, -0.7, 0.8), (0.5, 1.05, -0.62, 0.7), (2.8, 0.78, -0.42, 0.46)]


def terran_corvette(name='Corvette'):
    """~10 long fast attack ship: dagger hull that splits into a forked prow with a rail gun
    slung between the prongs, two big engine nacelles on swept pylons, blade fins."""
    rnd = random.Random(5)
    base._faction('terran')
    m = F.mark()
    _hull(C_SECS, 'wedge', bevel=0.035)
    _dress(rnd, C_SECS, 'wedge', -4.0, 2.6, k=0.45, greebles=260,
           deck_ok=lambda x, y: not (-2.9 < x < -0.3 and abs(y) < 0.7) and not (abs(x - 1.2) < 0.5 and abs(y) < 0.45),
           rows=2, belly=90)
    # forked prow and the rail gun between the prongs
    F.sym(F.prism([(1.9, -0.42), (5.3, -0.08), (5.6, 0.02), (5.3, 0.12), (1.9, 0.46)], 0.34, 0.8, 'armor', taper=0.8, bevel=0.03))
    F.sym(F.prism([(2.2, -0.2), (5.0, -0.02), (5.0, 0.08), (2.2, 0.26)], 0.78, 0.86, 'plate', bevel=0.02))
    F.sym(F.box((3.7, 0.325, 0.03), (1.5, 0.012, 0.045), 'glow'))
    F.sym(F.box((3.7, 0.87, 0.03), (1.1, 0.012, 0.03), 'glow'))
    F.cyl((1.0, 0, 0.03), (4.9, 0, 0.03), 0.12, 10, 'barrel')
    F.cyl((2.4, 0, 0.03), (4.4, 0, 0.03), 0.155, 10, 'coil')
    F.cyl((4.9, 0, 0.03), (5.15, 0, 0.03), 0.17, 10, 'armor')
    for xx in (2.5, 3.4, 4.3):
        F.box((xx, 0, 0.03), (0.07, 0.34, 0.05), 'plate')
    # bridge
    F.box((-1.6, 0, 0.98), (1.15, 0.55, 0.2), 'armor', taper=0.7, bevel=0.03)
    F.box((-1.95, 0, 1.3), (0.6, 0.38, 0.14), 'plate', taper=0.7, bevel=0.02)
    F.box((-1.34, 0, 1.31), (0.03, 0.3, 0.055), 'glass')
    F.box((-1.33, 0, 1.31), (0.03, 0.25, 0.015), 'glow')
    for j in range(8):
        F.sym(F.box((-2.4 + j * 0.22, 0.56, 0.98), (0.06, 0.015, 0.025), 'glass' if j % 3 else 'amber'))
    # nacelles on swept pylons
    for s in (-1, 1):
        F.plate([(-0.7, s * 0.9), (-1.7, s * 2.0), (-3.3, s * 2.0), (-3.5, s * 0.9)], -0.09, 0.09, 'plate', bevel=0.02)
        F.plate([(-1.05, s * 1.0), (-1.9, s * 1.95), (-2.0, s * 1.95), (-1.2, s * 1.0)], -0.105, 0.105, 'glow')
        F.tube((-0.6, s * 2.25, 0), (-4.2, s * 2.25, 0), [(0, 0.2), (0.14, 0.48), (0.8, 0.55), (1, 0.5)], 12, 'armor', bevel=0.02)
        F.cyl((-0.62, s * 2.25, 0), (-0.55, s * 2.25, 0), 0.17, 10, 'amber')
        _engine(-4.0, s * 2.25, 0, 0.5, L=1.0, sides=14)
        for xx in (-1.6, -2.3, -3.0):
            F.cyl((xx, s * 2.25, 0), (xx - 0.1, s * 2.25, 0), 0.585, 12, 'plate')
        F.box((-2.4, s * 2.82, 0), (1.0, 0.012, 0.04), 'glow')
        for u in (-1, 1):
            F.prism([(-4.0, u * 0.45), (-2.6, u * 0.45), (-3.6, u * 1.25), (-4.15, u * 1.25)], s * 2.25 - 0.04, s * 2.25 + 0.04,
                    'armor', bevel=0.012)
        F.cyl((-1.6, s * 2.25, 0.5), (0.7, s * 2.25, 0.5), 0.05, 6, 'barrel')        # nacelle gun
        F.box((-1.9, s * 2.25, 0.5), (0.45, 0.12, 0.1), 'armor', bevel=0.02)
    _engine(-4.0, 0, 0.02, 0.5, L=0.9, sides=14)
    # blade fins
    F.prism([(-4.0, 0.5), (-2.5, 0.5), (-3.5, 1.9), (-4.2, 1.9)], -0.05, 0.05, 'armor', bevel=0.015)
    F.box((-3.72, 0, 1.2), (0.02, 0.06, 0.55), 'glow')
    F.prism([(-3.8, -0.5), (-2.4, -0.5), (-3.2, -1.3), (-3.9, -1.3)], -0.05, 0.05, 'armor', bevel=0.015)
    F.orb((-3.85, 0, 1.93), 0.05, 'red', seg=(8, 5))
    # turrets
    _turret(1.2, 0, 0.72, 0.26)
    _turret(-0.4, 0, -0.68, 0.24, up=-1)
    return _finish(m, name)


# ================================================================== frigate
FR_SECS = [(-9, 1.5, -1.0, 1.1), (-3, 2.0, -1.3, 1.5), (4, 1.6, -1.0, 1.1), (8.5, 0.9, -0.5, 0.6), (10.6, 0.3, -0.15, 0.2)]
FR_OUT = [(-7.5, 0.75, -0.7, 0.75), (-3, 0.95, -0.85, 0.9), (3, 0.8, -0.65, 0.7), (5.6, 0.35, -0.25, 0.3)]
FR_Y = 3.9


def terran_frigate_v2(name='FrigateV2'):
    """~21 long trimaran gun frigate: dreadnought-family wedge hull flanked by two outrigger hulls
    on swept struts, each outrigger a long heavy cannon with its own engine; twin spinal guns,
    stepped bridge tower, turrets, cyan strips."""
    rnd = random.Random(8)
    base._faction('terran')
    m = F.mark()
    _hull(FR_SECS, 'wedge', bevel=0.05)
    _dress(rnd, FR_SECS, 'wedge', -8.8, 9.0, k=0.6, greebles=900,
           deck_ok=lambda x, y: not (-7.6 < x < -2.6 and abs(y) < 1.1) and not (-1.5 < x < 7.5 and abs(y) < 0.75),
           rows=2, belly=220)
    # outrigger hulls (built on +Y, then mirrored)
    mo = F.mark()
    _hull(FR_OUT, 'wedge', zone='armor', bevel=0.04, y=FR_Y)
    _dress(rnd, FR_OUT, 'wedge', -7.2, 4.8, k=0.45, greebles=160, rows=1, y=FR_Y,
           deck_ok=lambda x, y: not (abs(x + 2.5) < 0.6))
    F.cyl((0.5, FR_Y, 0.1), (9.6, FR_Y, 0.1), 0.24, 12, 'barrel')                 # outrigger cannon
    for (c0, c1) in [(3.2, 3.9), (4.75, 5.4), (5.95, 6.6), (7.15, 7.8)]:
        F.cyl((c0, FR_Y, 0.1), (c1, FR_Y, 0.1), 0.275, 12, 'coil')
    for xx in (4.4, 5.6, 6.8, 8.0):
        F.cyl((xx, FR_Y, 0.1), (xx + 0.18, FR_Y, 0.1), 0.34, 12, 'armor')
    F.cyl((9.5, FR_Y, 0.1), (10.2, FR_Y, 0.1), 0.34, 12, 'armor')
    F.cyl((10.15, FR_Y, 0.1), (10.22, FR_Y, 0.1), 0.2, 12, 'glow')
    F.box((-1.5, FR_Y + 0.93, 0.05), (4.0, 0.015, 0.05), 'glow')
    _engine(-7.3, FR_Y, 0, 0.62, L=1.3, sides=14)
    F.prism([(-7.4, 0.6), (-4.6, 0.6), (-6.6, 2.1), (-7.6, 2.1)], FR_Y - 0.06, FR_Y + 0.06, 'armor', bevel=0.02)   # blade fins
    F.prism([(-7.2, -0.6), (-4.9, -0.6), (-6.4, -1.7), (-7.3, -1.7)], FR_Y - 0.06, FR_Y + 0.06, 'armor', bevel=0.02)
    F.box((-6.75, FR_Y, 1.4), (0.03, 0.075, 0.6), 'glow')
    _turret(-2.5, FR_Y, 0.95, 0.3)
    for (xa, xb) in [(-5.6, -3.4), (0.2, 1.8)]:                                    # swept struts
        F.plate([(xa, 1.6), (xa + 0.9, FR_Y - 0.6), (xb + 0.6, FR_Y - 0.6), (xb, 1.6)], -0.16, 0.16, 'plate', bevel=0.03)
        F.plate([(xa + 0.5, 1.9), (xa + 1.2, FR_Y - 0.9), (xa + 1.4, FR_Y - 0.9), (xa + 0.7, 1.9)], -0.18, 0.18, 'glow')
        F.cyl(((xa + xb) / 2, 1.7, -0.6), ((xa + xb) / 2 + 0.6, FR_Y - 0.5, -0.3), 0.07, 6, 'barrel')
    F.mirror_all(mo)
    # twin spinal guns in a dorsal housing
    for y in (-0.38, 0.38):
        F.cyl((-1, y, 1.42), (11.2, y, 0.78), 0.16, 10, 'barrel')
        F.cyl((11.2, y, 0.78), (11.7, y, 0.755), 0.2, 10, 'armor')
        F.cyl((8.6, y, 0.92), (10.4, y, 0.82), 0.19, 10, 'coil')
        for xx in (5.0, 6.2, 7.4):
            F.cyl((xx, y, 1.42 - 0.0525 * (xx + 1)), (xx + 0.25, y, 1.42 - 0.0525 * (xx + 1.25)), 0.21, 10, 'armor')
    F.box((3, 0, 1.3), (4.2, 0.7, 0.22), 'armor', taper=0.7, bevel=0.04)
    for j in range(12):
        F.sym(F.box((-0.6 + j * 0.6, 0.66, 1.3), (0.12, 0.04, 0.14), 'plate'))
    _bridge(-5.0, 1.45, 0.7)
    _turret(-1.9, 0, 1.6, 0.36)
    _turret(-8.3, 0, 1.25, 0.32)
    _turret(1.0, 0, -1.2, 0.34, up=-1)
    x = -8
    while x < 7:
        w, zb, zt = _sec(FR_SECS, x)
        for s in (-1, 1):
            _turret(x, s * w * 0.66, zt + 0.03, 0.13, barrels=2)
        x += 1.9
    # ventral hangar slot with a cyan field, belly strip
    F.box((-3.5, 0, -1.33), (2.2, 0.9, 0.12), 'armor', bevel=0.03)
    F.box((-3.5, 0, -1.46), (1.9, 0.6, 0.01), 'glass')
    for j in range(8):
        F.sym(F.box((-5.2 + j * 0.5, 0.75, -1.46), (0.05, 0.03, 0.02), 'glow'))
    F.box((5.5, 0, -0.93), (2.4, 0.07, 0.03), 'glow')
    F.prism([(0.5, -1.1), (7.5, -0.6), (5.2, -2.2), (2.2, -2.2)], -0.09, 0.09, 'armor', bevel=0.03)             # keel blade
    F.sym(F.box((3.9, 0.1, -1.75), (1.3, 0.01, 0.04), 'glow'))
    # engines
    for (y, z, r) in [(0, 0.15, 0.85), (-0.95, -0.5, 0.4), (0.95, -0.5, 0.4), (-0.85, 0.8, 0.3), (0.85, 0.8, 0.3)]:
        _engine(-8.7, y, z, r, sides=14)
    return _finish(m, name)


# ================================================================== twin-X fighter
def twin_x_fighter(name='TwinX', seed=4):
    """~1.5 long, no fuselage and no cockpit. A compact reactor core (violet plasma orb in an
    armoured cage, sensor spike in front, short engine behind) with eight free-floating wings
    round it: a long gun-tipped set of four and, further aft and turned 45 degrees, a shorter
    forward-swept set with amber tip thrusters. Nothing solid joins wings to core; crackling
    violet plasma arcs and a faint plasma haze hold them in place.
    Returns (ship, wings_name). ship is the core. The wings are one child object whose origin is
    on the spin axis: rotate it about its local X and all eight wings, their arcs and the haze
    turn as one (arcs and haze are children of the wings object: <name>_Arcs, <name>_Haze).
    The orb is <name>_Orb, a child of the core. Duplicate the ship with its children."""
    rnd = random.Random(seed)
    base._faction('terran')
    CX = -0.08                                                        # orb centre
    m = F.mark()
    # cage round the orb: three hoops and four ribs
    for xx in (-0.2, CX, 0.04):
        F.tube((xx - 0.014, 0, 0), (xx + 0.014, 0, 0), [(0, 0.128), (1, 0.128)], 16, 'plate', caps=False)
        F.tube((xx - 0.014, 0, 0), (xx + 0.014, 0, 0), [(0, 0.118), (1, 0.118)], 16, 'dark', caps=False)
    for a in (0, 90, 180, 270):
        o = F.box((CX, 0, 0.126), (0.15, 0.014, 0.008), 'armor')
        F.rot(o, 'X', a)
    # nose: angular sensor spike (no canopy)
    o = F.tube((0.05, 0, 0), (0.52, 0, 0), [(0, 0.118), (0.12, 0.105), (0.5, 0.055), (0.93, 0.014), (1, 0.008)], 8, 'hull',
               bevel=0.004)
    F.rot(o, 'X', 22.5)
    F.cyl((0.05, 0, 0), (0.035, 0, 0), 0.1, 12, 'dark')
    for a in (0, 90, 180, 270):
        mm = F.mark()
        F.box((0.24, 0, 0.083), (0.12, 0.012, 0.004), 'glow')
        F.box((0.13, 0, 0.112), (0.05, 0.03, 0.008), 'plate')
        F.rot_all(mm, 'X', a)
    F.orb((0.525, 0, 0), 0.014, 'amber', seg=(8, 5))
    # tail: reactor block and a short engine
    F.cyl((-0.22, 0, 0), (-0.2, 0, 0), 0.1, 12, 'dark')
    o = F.tube((-0.21, 0, 0), (-0.5, 0, 0), [(0, 0.118), (0.2, 0.125), (0.8, 0.11), (1, 0.09)], 8, 'armor', bevel=0.004)
    F.rot(o, 'X', 22.5)
    for xx in (-0.3, -0.38):
        F.cyl((xx, 0, 0), (xx - 0.02, 0, 0), 0.128, 16, 'coil')
    F.tube((-0.5, 0, 0), (-0.7, 0, 0), [(0, 0.075), (0.3, 0.095), (1, 0.115)], 14, 'dark', caps=False)
    F.cyl((-0.56, 0, 0), (-0.57, 0, 0), 0.085, 14, 'glow')
    for a in range(0, 360, 60):
        o = F.box((-0.62, 0, 0.108), (0.07, 0.012, 0.008), 'plate')
        F.rot(o, 'X', a)
    ship = _finish(m, name)
    for p in ship.data.polygons:
        p.use_smooth = True
    F.orb((CX, 0, 0), 0.098, 'glow', seg=(20, 12))
    orb = base._join(F.since(0), f'{name}_Orb')
    _soft(orb, _emit_mat('twinx_orb', (0.4, 0.08, 1.0), 5.0))
    orb.parent = ship

    # (x of the root middle, root radius, tip radius, root chord, sweep back, first angle, gun tip?)
    sets = ((0.0, 0.37, 0.86, 0.4, 0.13, 45, True), (-0.34, 0.33, 0.66, 0.3, -0.07, 0, False))

    def wing(x0, r0, span, chord, sweep, gun):
        xt = x0 - sweep
        F.plate([(x0 + chord * 0.5, r0), (xt + chord * 0.2, span), (xt - chord * 0.2, span), (x0 - chord * 0.5, r0)],
                -0.012, 0.012, 'armor', bevel=0.003)
        rm = r0 + (span - r0) * 0.42
        F.plate([(x0 + chord * 0.5, r0), (x0 + chord * 0.36 - sweep * 0.42, rm), (x0 - chord * 0.36 - sweep * 0.42, rm),
                 (x0 - chord * 0.5, r0)], -0.019, 0.019, 'plate', bevel=0.003)                      # root armour
        F.box((x0, r0 + 0.012, 0), (chord * 0.42, 0.016, 0.03), 'dark', bevel=0.004)                # field emitter bar
        t0, t1 = 0.5, 0.93
        F.plate([(x0 + (xt - x0) * t0 + 0.013, r0 + (span - r0) * t0), (x0 + (xt - x0) * t1 + 0.013, r0 + (span - r0) * t1),
                 (x0 + (xt - x0) * t1 - 0.013, r0 + (span - r0) * t1), (x0 + (xt - x0) * t0 - 0.013, r0 + (span - r0) * t0)],
                -0.0145, 0.0145, 'glow')
        if gun:
            F.cyl((xt - 0.15, span, 0), (xt + 0.14, span, 0), 0.03, 8, 'plate')
            F.cyl((xt + 0.12, span, 0), (xt + 0.86, span, 0), 0.012, 6, 'barrel')
            F.cyl((xt + 0.5, span, 0), (xt + 0.7, span, 0), 0.018, 6, 'coil')
            F.orb((xt + 0.86, span, 0), 0.015, 'glow', seg=(8, 5))
            F.cyl((xt - 0.15, span, 0), (xt - 0.16, span, 0), 0.022, 8, 'glow')
        else:
            F.tube((xt + 0.12, span, 0), (xt - 0.16, span, 0), [(0, 0.01), (0.25, 0.028), (1, 0.034)], 10, 'plate', caps=False)
            F.cyl((xt - 0.1, span, 0), (xt - 0.11, span, 0), 0.028, 10, 'amber')
            F.orb((xt + 0.12, span, 0), 0.013, 'amber', seg=(8, 5))

    def arcs(x0, r0, chord):
        """Jagged plasma bolts from the wing's emitter bar in to the orb, with a few forks."""
        for _ in range(4):
            a = Vector((x0 + rnd.uniform(-0.4, 0.4) * chord, r0 - 0.004, rnd.uniform(-0.02, 0.02)))
            b = Vector((CX + rnd.uniform(-0.07, 0.07), 0.09, rnd.uniform(-0.03, 0.03)))
            n = rnd.randint(5, 7)
            pts = [a]
            for i in range(1, n):
                p = a.lerp(b, i / n)
                pts.append(p + Vector((rnd.uniform(-1, 1), rnd.uniform(-0.4, 0.4), rnd.uniform(-1, 1))) * 0.03)
            pts.append(b)
            w = rnd.uniform(0.0035, 0.006)
            for p, q in zip(pts, pts[1:]):
                F.cyl(p, q, w, 4, 'glow')
            if rnd.random() < 0.6:                                   # a fork that dies in the gap
                p = pts[rnd.randint(1, n - 1)]
                for _ in range(2):
                    q = p + Vector((rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.2), rnd.uniform(-1, 1))) * 0.045
                    F.cyl(p, q, w * 0.6, 4, 'glow')
                    p = q
        F.box((x0, r0 - 0.006, 0), (chord * 0.4, 0.004, 0.02), 'glow')        # emitter face glows violet

    def haze(x0, r0, chord):
        F.tube((x0, r0 - 0.005, 0), (CX, 0.07, 0), [(0, chord * 0.16), (0.4, 0.03), (1, 0.05)], 10, 'glow', caps=False)

    def ring(fn, label):
        F.ST['parts'] = []
        for (x0, r0, span, chord, sweep, a0, gun) in sets:
            for q in range(4):
                mm = F.mark()
                fn(x0, r0, span, chord, sweep, gun)
                F.rot_all(mm, 'X', a0 + 90 * q)
        if label == 'Haze':
            F.orb((CX, 0, 0), 0.17, 'glow', seg=(16, 10))
        n = len(F.ST['parts'])
        o = base._join(F.since(0), f'{name}_{label}')
        for p in o.data.polygons:
            p.use_smooth = True
        return o, n

    wings, n = ring(wing, 'Wings')
    wings.parent = ship
    ship['shapes'] += n
    arc, n = ring(lambda x0, r0, span, chord, sweep, gun: arcs(x0, r0, chord), 'Arcs')
    _soft(arc, _emit_mat('twinx_arc', (0.33, 0.04, 1.0), 14.0))
    arc.parent = wings
    ship['shapes'] += n
    hz, n = ring(lambda x0, r0, span, chord, sweep, gun: haze(x0, r0, chord), 'Haze')
    _soft(hz, _emit_mat('twinx_haze', (0.3, 0.03, 1.0), 1.4, soft=2.2, alpha=0.22))
    hz.parent = wings
    ship['wings'], ship['arcs'], ship['haze'], ship['orb'] = wings.name, arc.name, hz.name, orb.name
    return ship, wings.name


# ================================================================== missile ship + missile
def missile(name='Missile', scale=1.0, plume=False):
    """~4.2 long heavy anti-ship missile pointing +X, origin at its middle. plume=True adds an
    emissive exhaust cone behind it (for stills; animate your own trail in a shot)."""
    base._faction('terran')
    m = F.mark()
    k = scale
    F.cyl((-1.7 * k, 0, 0), (1.1 * k, 0, 0), 0.4 * k, 12, 'armor')
    F.tube((1.1 * k, 0, 0), (2.2 * k, 0, 0), [(0, 0.4 * k), (0.5, 0.3 * k), (0.9, 0.1 * k), (1, 0.03 * k)], 12, 'plate')
    F.cyl((0.95 * k, 0, 0), (1.1 * k, 0, 0), 0.415 * k, 12, 'hazard')
    F.cyl((2.12 * k, 0, 0), (2.2 * k, 0, 0), 0.07 * k, 8, 'red')
    for xx in (-0.2, -0.9):
        F.cyl((xx * k, 0, 0), ((xx - 0.08) * k, 0, 0), 0.42 * k, 12, 'glow')
    for a in (45, 135, 225, 315):
        o = F.prism([(-1.9 * k, 0.35 * k), (-0.9 * k, 0.35 * k), (-1.5 * k, 0.85 * k), (-1.95 * k, 0.85 * k)], -0.03 * k, 0.03 * k,
                    'plate')
        F.rot(o, 'X', a)
        o = F.prism([(0.2 * k, 0.38 * k), (0.75 * k, 0.38 * k), (0.35 * k, 0.6 * k), (0.2 * k, 0.6 * k)], -0.025 * k, 0.025 * k,
                    'plate')
        F.rot(o, 'X', a)
    F.tube((-1.7 * k, 0, 0), (-2.05 * k, 0, 0), [(0, 0.3 * k), (1, 0.38 * k)], 12, 'dark', caps=False)
    F.cyl((-1.8 * k, 0, 0), (-1.82 * k, 0, 0), 0.31 * k, 12, 'amber')
    n = len(F.since(m))
    obj = base._join(F.since(m), name)
    obj['shapes'] = n
    for p in obj.data.polygons:
        p.use_smooth = True
    if plume:
        F.tube((-1.85 * k, 0, 0), (-10 * k, 0, 0), [(0, 0.28 * k), (0.06, 0.4 * k), (0.15, 0.42 * k), (0.4, 0.3 * k), (0.7, 0.15 * k),
                                                    (1, 0.0)], 16, 'glow')
        F.tube((-1.85 * k, 0, 0), (-5 * k, 0, 0), [(0, 0.2 * k), (0.2, 0.26 * k), (0.6, 0.14 * k), (1, 0.0)], 12, 'glow')
        pl = _soft(base._join(F.since(0), name + '_Plume'), _emit_mat('missile_plume', (1.0, 0.42, 0.1), 16.0, soft=2.0))
        pl.parent = obj
    return obj


M_AFT = [(-15.5, 3.0, -2.2, 2.3), (-13, 4.0, -2.8, 2.9), (-7, 4.2, -2.8, 2.9), (-5.2, 3.2, -2.1, 2.2)]
M_TY, M_TZ = 2.3, 0.55          # launch tube axis
M_MOUTH = 15.0


def missile_ship(name='MissileShip'):
    """~31 long, slow and heavy. Two huge launch tubes run the length of the bow like a
    double-barrelled gun; behind each sits an open revolver magazine (two drums in tandem) with
    the missiles visible in their cradles, fed from an armoured store in the bulky aft hull.
    Returns (ship, tube_points): local centres of the two tube mouths (+Y first); missiles leave
    along +X."""
    rnd = random.Random(31)
    base._faction('terran')
    m = F.mark()
    _hull(M_AFT, 'slab', bevel=0.07)
    _dress(rnd, M_AFT, 'slab', -15.2, -5.4, k=0.9, greebles=700, rows=3, belly=200,
           deck_ok=lambda x, y: not (-14.5 < x < -9.5 and abs(y) < 1.9))
    _bridge(-11.5, 2.85, 0.95)
    # keel beam and armoured spine roof running forward between the tubes
    F.box((2.5, 0, -0.6), (8.0, 0.22, 1.7), 'hull', bevel=0.04)
    F.box((4.2, 0, M_TZ + 1.25), (9.6, 1.1, 0.3), 'armor', taper=0.8, bevel=0.05)
    F.box((4.2, 0, M_TZ + 1.58), (9.0, 0.5, 0.1), 'plate', taper=0.8, bevel=0.03)
    for j in range(16):
        F.box((-4.0 + j * 1.1, 0, M_TZ + 1.7), (0.3, 0.36, 0.035), 'vent')
        F.sym(F.box((-4.0 + j * 1.1, 1.08, M_TZ + 1.25), (0.2, 0.03, 0.05), 'amber' if j % 4 == 0 else 'glass'))
    for _ in range(160):
        _greeble(rnd, rnd.uniform(-4.8, 13), rnd.choice((-1, 1)) * rnd.uniform(0.55, 0.95), M_TZ + 1.55, 0.45)

    ms = F.mark()                                     # everything below is built on +Y and mirrored
    DZ = M_TZ - 1.45                                  # drum axis: its top chamber lines up with the tube
    for (d0, d1) in [(-4.9, -2.2), (-1.7, 1.0)]:      # two revolver drums in tandem
        F.cyl((d0 - 0.2, M_TY, DZ), (d1 + 0.2, M_TY, DZ), 0.55, 12, 'armor')
        for xx in (d0, (d0 + d1) / 2, d1):
            F.tube((xx - 0.13, M_TY, DZ), (xx + 0.13, M_TY, DZ), [(0, 2.02), (1, 2.02)], 24, 'plate')
            F.cyl((xx - 0.15, M_TY, DZ), (xx + 0.15, M_TY, DZ), 0.95, 12, 'armor')
        F.cyl(((d0 + d1) / 2 - 0.05, M_TY, DZ), ((d0 + d1) / 2 + 0.05, M_TY, DZ), 2.06, 24, 'glow')
        for q in range(8):
            a = math.radians(90 + q * 45)
            cy, cz = M_TY + math.cos(a) * 1.45, DZ + math.sin(a) * 1.45
            if q == 7 and d0 > -3:                    # an empty cradle on the front drum (already fired)
                F.cyl((d0, cy, cz), (d1, cy, cz), 0.06, 6, 'barrel')
                continue
            F.cyl((d0 + 0.05, cy, cz), (d1 - 0.55, cy, cz), 0.4, 10, 'plate')
            F.tube((d1 - 0.55, cy, cz), (d1 - 0.02, cy, cz), [(0, 0.4), (0.6, 0.27), (1, 0.06)], 10, 'hazard')
            F.cyl((d0 + 0.5, cy, cz), (d0 + 0.62, cy, cz), 0.415, 10, 'glow')
            F.cyl((d0 - 0.02, cy, cz), (d0 + 0.05, cy, cz), 0.3, 10, 'dark')
    # feed housing from the aft store into the rear drum, and the breech between drum and tube
    F.box((-5.3, M_TY, M_TZ - 0.2), (0.45, 1.75, 1.9), 'armor', bevel=0.06)
    F.box((-1.95, M_TY, M_TZ), (0.2, 0.75, 0.75), 'armor', bevel=0.04)
    F.box((1.5, M_TY, M_TZ), (0.6, 1.5, 1.45), 'armor', bevel=0.06)
    F.box((1.5, M_TY + 1.52, M_TZ), (0.4, 0.02, 0.9), 'hazard')
    # the launch tube
    F.tube((1.9, M_TY, M_TZ), (M_MOUTH, M_TY, M_TZ), [(0, 1.45), (0.05, 1.22), (0.9, 1.22), (0.915, 1.5), (1, 1.5)], 20, 'hull',
           caps=False)
    F.tube((M_MOUTH, M_TY, M_TZ), (10.5, M_TY, M_TZ), [(0, 1.5), (0.03, 0.98), (1, 0.95)], 20, 'dark', caps=False)
    F.cyl((11.0, M_TY, M_TZ), (10.9, M_TY, M_TZ), 0.97, 20, 'amber')
    F.tube((M_MOUTH - 0.9, M_TY, M_TZ), (M_MOUTH - 0.6, M_TY, M_TZ), [(0, 1.53), (1, 1.53)], 20, 'hazard', caps=False)
    F.tube((M_MOUTH - 0.25, M_TY, M_TZ), (M_MOUTH - 0.15, M_TY, M_TZ), [(0, 1.53), (1, 1.53)], 20, 'glow', caps=False)
    for j in range(7):
        xx = 3.2 + j * 1.45
        F.cyl((xx, M_TY, M_TZ), (xx + 0.3, M_TY, M_TZ), 1.36, 20, 'armor')
        F.cyl((xx + 0.36, M_TY, M_TZ), (xx + 0.44, M_TY, M_TZ), 1.27, 20, 'glow' if j % 2 == 0 else 'plate')
    # outer armour cheek along the tube, with a cyan strip and thrusters
    F.box((7.8, M_TY + 1.42, M_TZ), (4.6, 0.26, 0.85), 'armor', taper=0.8, bevel=0.05)
    F.box((7.8, M_TY + 1.69, M_TZ + 0.05), (4.2, 0.02, 0.07), 'glow')
    F.box((7.8, M_TY - 0.2, M_TZ - 1.25), (4.4, 0.9, 0.22), 'armor', bevel=0.04)       # tube cradle underneath
    for xx in (12.4, 4.0):
        F.box((xx, M_TY + 1.75, M_TZ - 0.1), (0.7, 0.3, 0.45), 'plate', bevel=0.04)
        _nozzle((xx, M_TY + 2.0, M_TZ - 0.1), (0, 1, 0), 0.34, 0.45, glow='amber', sides=10)
    # side store pods on the aft hull: rows of reload hatches
    F.box((-10, 4.55, 0.1), (3.6, 0.5, 1.5), 'armor', taper=0.85, bevel=0.06)
    for j in range(6):
        for dz in (-0.7, 0.2, 1.0):
            F.box((-12.6 + j * 1.05, 5.02, dz), (0.38, 0.03, 0.3), 'plate', bevel=0.02)
            F.box((-12.6 + j * 1.05, 5.05, dz - 0.36), (0.3, 0.02, 0.03), 'hazard')
    F.box((-10, 5.06, 1.52), (3.3, 0.02, 0.05), 'glow')
    _turret(-7.0, 3.0, 2.95, 0.4)
    _turret(-8.5, 2.6, -2.85, 0.36, up=-1)
    F.mirror_all(ms)
    # bow yoke tying the tube mouths together, sensor nose
    F.box((12.6, 0, M_TZ), (1.5, 1.05, 0.7), 'armor', taper=0.8, bevel=0.05)
    F.prism([(14.0, M_TZ - 0.5), (15.6, M_TZ - 0.12), (15.6, M_TZ + 0.12), (14.0, M_TZ + 0.6)], -0.6, 0.6, 'plate', taper=0.7,
            bevel=0.04)
    F.box((15.55, 0, M_TZ), (0.08, 0.4, 0.08), 'glow')
    _turret(9.0, 0, M_TZ + 1.7, 0.42)
    _turret(3.0, 0, M_TZ + 1.7, 0.36)
    # engines: four modest ones for a ship this size (it is slow)
    for (y, z, r) in [(-1.6, 0.9, 0.95), (1.6, 0.9, 0.95), (-1.6, -1.1, 0.8), (1.6, -1.1, 0.8)]:
        _engine(-15.2, y, z, r, sides=14)
    ship = _finish(m, name)
    tubes = [Vector((M_MOUTH, M_TY, M_TZ)), Vector((M_MOUTH, -M_TY, M_TZ))]
    ship['tubes'] = [tuple(p) for p in tubes]
    return ship, tubes


BUILDERS = {
    'battleship': broadside_battleship,
    'corvette': terran_corvette,
    'frigate': terran_frigate_v2,
    'fighter': twin_x_fighter,
    'missile_ship': missile_ship,
}
