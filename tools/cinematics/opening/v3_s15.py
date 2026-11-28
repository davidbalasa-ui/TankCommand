"""Scene 15 (v4): the cull, close enough to see it. David 2026-11-28: the beams and the retreat were rushed;
"we need to see it slicing through ships".

 0.0- 3.0  A  both fleets still trading fire across the gap; violet beams burst up out of the clouds between
              them, one after another, taller than anything there.
 3.0- 6.5  B  close on a Terran frigate: violet light swells beneath it, a beam erupts under its midships and
              sweeps across the hull: a white-hot seam runs side to side, the ship falls apart in two halves
              with molten faces, the aft half blows.
 6.5- 9.5  C  close on the Arcadian lens ship: a beam slices diagonally through its disc; a third of the
              ship slides away, gold lightning spilling out of the cut.
 9.5-13.0  D  along the Terran line: one beam walks down the whole line, cutting four corvettes in turn,
              a second takes the missile ship.
Own clock.
"""
import math

import bpy
from mathutils import Vector

import v3base as V
from v3base import fr
import v3_battle as B
import space as SP
import slicer as SL

Z = Vector((0, 0, 1))
GOLD = (1.0, 0.72, 0.28)


def bounds(ob, f):
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    pts = [ob.matrix_world @ Vector(b) for b in ob.bound_box]
    c = sum(pts, Vector()) / 8
    size = max((p - c).length for p in pts) * 2 / math.sqrt(3)
    return c, size


def sweep_cut(ob, s_world, off_frac, f_on, f0, f1, f_off, seed, terran=True, top_z=None, r=None,
              end_f=None, sep=None):
    """A beam crossing ob along world direction s (horizontal) on a line offset from its centre by
    off_frac * size (perpendicular). Cuts at the moment it leaves the hull."""
    c, size = bounds(ob, f1)
    s = Vector((s_world[0], s_world[1], 0)).normalized()
    n = s.cross(Z).normalized()
    pc = c + n * off_frac * size
    D = size * 0.75
    a, b = pc - s * D, pc + s * D
    SL.column([(f0, (a.x, a.y)), (f1, (b.x, b.y)), (f_off, (b.x + s.x * D * 0.6, b.y + s.y * D * 0.6))],
              f_on, f_off, top_z=top_z or c.z + 400, r=r or max(2.5, size * 0.022), name=SP._uid('Cut'))
    rinv = ob.matrix_world.to_3x3().inverted()
    n_l = (rinv @ n).normalized()
    s_l = (rinv @ s).normalized()
    off_l = ob.matrix_world.inverted() @ pc
    f_cut = f0 + int((f1 - f0) * 0.62)
    SL.underglow(c - Z * size * 0.6, f_on - 18, f_on, k=size * size * 400)
    return SL.slice_ship(ob, n_l, f_cut, plane_off_l=off_l, sweep_l=s_l, f_sweep0=f0 + int((f1 - f0) * 0.3),
                         sep=sep or size * 0.05, spin=10.0, end_f=end_f, seed=seed, terran=terran), c, size, f_cut


def build(draft=True):
    sc = V.Scene(13.0, draft)
    nf = sc.nf
    sc.env()
    R = B.Rig(sc, {'bship', 'frigate', 'missile', 'corv0', 'corv1', 'corv2', 'corv3', 'crescent', 'lens',
                   'acorv0', 'acorv1', 'acorv2'})
    R.terran_shields(keys=('bship',))
    R.gold_shields(keys=('crescent',), vis=0.2)
    o = R.obj
    # ---------------------------------------------------------------- A: fire across the gap, then the beams
    import random
    rnd = random.Random(1500)
    for i in range(10):
        a = rnd.choice(['corv0', 'corv1', 'corv2', 'frigate', 'bship'])
        b = rnd.choice(['acorv0', 'acorv1', 'acorv2', 'lens', 'crescent'])
        f0 = 2 + i * 5
        pa, _ = bounds(o[a], f0)
        pb, _ = bounds(o[b], f0)
        if i % 2:
            SP.bolt(pa, pb, f0, 14, (0.3, 0.7, 1.0))
        else:
            SP.bolt(pb, pa, f0, 14, (1.0, 0.7, 0.3))
    for (x, y), f in [((70, 30), fr(1.2)), ((150, -70), fr(1.55)), ((10, -150), fr(1.85)), ((210, 110), fr(2.1)),
                      ((40, 160), fr(2.35))]:
        SL.column([(1, (x, y)), (nf, (x + 5, y))], f, fr(5.0), top_z=300, r=4.5)
    camA = Vector((-265, 190, 45))
    sc.shot('A', 1, fr(3.0),
            [(1, camA, Vector((120, -40, 20)), 24), (fr(3.0), camA + Vector((25, -20, 10)), Vector((120, -40, 45)), 23)],
            shake=[(fr(1.2), 1.2, 14)])
    # ---------------------------------------------------------------- B: the frigate cut in two
    fB0, fB1 = fr(3.0) + 1, fr(6.5)
    fr_ob = o['frigate']
    cB, sB = bounds(fr_ob, fB0 + 30)
    (hB, _, _, fcB) = sweep_cut(fr_ob, (0, 1), 0.06, fB0 + 18, fB0 + 20, fB0 + 40, fB0 + 64, 1510, end_f=nf, r=2.2)
    camB = cB + Vector((-0.35 * sB, -1.25 * sB, -0.28 * sB))
    sc.shot('B', fB0, fB1,
            [(fB0, camB, cB + Vector((0, 0, -0.1 * sB)), 30),
             (fcB, camB + Vector((0.05 * sB, 0.1 * sB, 0.02 * sB)), cB, 30),
             (fB1, camB + Vector((0.1 * sB, -0.15 * sB, 0.08 * sB)), cB + Vector((0.1 * sB, 0, 0)), 28)],
            shake=[(fB0 + 20, 0.02 * sB, 12), (fcB, 0.05 * sB, 20)])
    # ---------------------------------------------------------------- C: the lens sliced, gold spills out
    fC0, fC1 = fB1 + 1, fr(9.5)
    lens = o['lens']
    cC, sC = bounds(lens, fC0 + 20)
    (hC, _, _, fcC) = sweep_cut(lens, (0.45, 1.0), 0.22, fC0 + 10, fC0 + 12, fC0 + 36, fC0 + 58, 1520,
                                terran=False, end_f=nf, sep=sC * 0.08, r=3.0)
    SP.flicker_lightning([(cC + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3))) * sC * 0.3,
                           cC + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3))) * sC * 0.45)
                          for _ in range(6)], 1525, fcC, fcC + 40, every=1, width=sC * 0.004, name='LensSpill',
                         zone_col=GOLD, strength=6.0)
    camC = cC + Vector((-1.15 * sC, -0.55 * sC, 0.32 * sC))
    sc.shot('C', fC0, fC1,
            [(fC0, camC, cC, 30), (fcC, camC + Vector((0.05 * sC, 0.05 * sC, 0)), cC, 30),
             (fC1, camC + Vector((-0.12 * sC, -0.05 * sC, 0.05 * sC)), cC, 28)],
            shake=[(fcC, 0.03 * sC, 18)])
    # ---------------------------------------------------------------- D: a beam walks down the Terran line
    fD0 = fC1 + 1
    # the corvettes close up into a tight screen in front of the battleship
    line = ['corv3', 'corv1', 'corv0', 'corv2']
    x_line = -118.0
    for i, k in enumerate(line):
        ob = o[k]
        ob.animation_data_clear()
        p = Vector((x_line + rnd.uniform(-2, 2), -27 + 18 * i, 27 + rnd.uniform(-3, 3)))
        SP.key_loc(ob, [(1, p - Vector((4, 0, 0))), (nf, p + Vector((4, 0, 0)))], 'LINEAR')
    y0, y1 = -48.0, 48.0
    fs0, fs1 = fD0 + 6, nf - 12
    SL.column([(1, (x_line, y0)), (fs0, (x_line, y0)), (fs1, (x_line, y1))], fs0 - 4, nf, top_z=260, r=1.6)
    for i, k in enumerate(line):
        ob = o[k]
        c, size = bounds(ob, fD0)
        fc = int(fs0 + (fs1 - fs0) * (y0 - c.y) / (y0 - y1))
        rinv = ob.matrix_world.to_3x3().inverted()
        SL.slice_ship(ob, (rinv @ Vector((1, 0, 0))).normalized(), fc,
                      plane_off_l=ob.matrix_world.inverted() @ Vector((x_line, c.y, c.z)),
                      sweep_l=(rinv @ Vector((0, 1, 0))).normalized(), f_sweep0=fc - 5, sep=size * 0.06,
                      spin=12.0, end_f=nf, seed=1530 + i)
    ms = o['missile']
    (_, cM, sM, _) = sweep_cut(ms, (0.2, -1.0), -0.05, fD0 + 30, fD0 + 32, fD0 + 52, nf, 1540, end_f=nf)
    camD = Vector((x_line - 38, -58, 40))
    sc.shot('D', fD0, nf,
            [(fD0, camD, Vector((x_line, -12, 27)), 36), (nf, camD + Vector((-6, 14, 4)), Vector((x_line, 14, 27)), 33)],
            shake=[(fD0 + 20, 0.3, 10), (fD0 + 40, 0.35, 10), (fD0 + 60, 0.3, 10)])
    return sc
