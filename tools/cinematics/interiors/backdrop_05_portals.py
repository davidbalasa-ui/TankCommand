"""Battle backdrop still 5: a portal arrival in the background of a battle. Two variants:

    /home/user/artenv/venv/bin/python tools/cinematics/interiors/backdrop_05_portals.py --variant=terran|arcadian --out=FILE.jpg [--final=1]

terran:   a Terran tear (violent, jagged, blue-white rip in space, opening/portals.terran_tear) behind a fight
          between a dreadnought and a crescent mothership; reinforcements come through it, drawn out long
          and thin until they clear the edge: a broadside battleship half out, a frigate snapping back to
          shape ahead of it, corvettes still streaks inside.
arcadian: an Arcadian portal (black, crisp thin rings with tick marks, electric, opening/portals.arcadian_portal)
          behind a Terran battleship and its screen; a crescent mothership is drawn out of it (its own hull
          tapered to a gold thread in the throat, backdrop_stretch.py), corvettes at other stages on side lanes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
import backdrop_stretch as ST  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

VAR = K.ARGS.get('variant', 'terran')
OUT = K.ARGS.get('out', os.path.join(K.SCRATCH, f'05_portal_{VAR}.jpg'))
ICE = (0.6, 0.82, 1.0)


def stretched(k, kind, at, d, stretch, col, scale=None, roll=0.0, tail=1.0):
    """A ship coming out of a portal along d, drawn out `stretch` times along its length and squeezed
    across, with a streak of light trailing back toward the portal."""
    ob = k.ship(kind, scale=scale)
    s = ob.scale.x
    sq = 1.0 / stretch ** 0.5 * 1.25 if stretch > 1.05 else 1.0
    k.place(ob, at, fwd=d, roll=roll)
    _, dims = k.bounds(ob)
    ob.scale = (s * stretch, s * min(1.0, sq), s * min(1.0, sq))
    L = dims.x * s * stretch
    if stretch > 1.05 and tail:
        dn = Vector(d).normalized()
        r = min(dims.y, dims.z) * s * 0.16
        nm = k.uid('PStreak')
        o = K.C.uv_sphere(nm, 1.0, seg=(24, 10), mat=K.glow_mat(nm + 'M', col, 4.5, 1.6), scale=(L * 0.75 * tail, r * 1.3, r * 1.3))
        o.location = Vector(at) - dn * L * 0.55 * tail
        K.BP.aim(o, dn)
        o.visible_shadow = False
    return ob


def terran():
    k = K.Kit(sun_dir=(0.6, 0.5, -0.45), sun_energy=5.5, planet_c=(0, 0, -2545), rim_dir=(-0.3, -0.9, 0.1), rim=1.5,
              fill_dir=(0.1, 1, -0.2), fill=2.4, tint='blue', nebula=2.2)
    k.camera((0, 0, 0), (0, 100, -4), lens=24)
    P = k.cam_pt
    # ------------------------------------------------ the tear, and what comes through it
    AT = P(0.12, 0.36, 390)
    n = Vector((-0.42, -1.0, -0.04)).normalized()
    K.PO.terran_tear('Tear', AT, n, 98.0, 2, 400, seed=21)
    wm = bpy.data.materials['TearWarpM'].node_tree       # calm the glints of the crumpled space round the tear:
    for nd in wm.nodes:                                   # at still-picture size they clump into white balls
        if nd.type == 'EMISSION' and nd.inputs['Strength'].links:
            src_ = nd.inputs['Strength'].links[0].from_socket
            mul = wm.nodes.new('ShaderNodeMath')
            mul.operation = 'MULTIPLY'
            mul.inputs[1].default_value = 0.12
            wm.links.new(src_, mul.inputs[0])
            wm.links.new(mul.outputs[0], nd.inputs['Strength'])
    k.light(AT + n * 330 + Vector((0, 0, 60)), ICE, 2.5e7, 30)          # the tear's glare on the ships leaving it
    stretched(k, 'bship', AT + n * 80 + Vector((6, 0, -4)), n, 4.2, ICE, scale=1.7, roll=-24)
    stretched(k, 'frigate', AT + n * 215 + Vector((-40, 0, 16)), n, 1.8, ICE, scale=2.2, roll=10)
    cv = stretched(k, 'corvette', AT + n * 270 + Vector((46, 0, -30)), n, 1.0, ICE, scale=2.2, roll=-10)
    k.engines(cv, 0.8)
    for off, st in ((Vector((36, 0, 50)), 9.0), (Vector((-30, 0, -56)), 11.0), (Vector((50, 0, -14)), 8.0)):
        stretched(k, 'corvette', AT - n * 10 + off, n, st, ICE, scale=1.8, tail=0.6)
    # ------------------------------------------------ the fight in front of it
    CR = P(-0.56, 0.0, 170)
    cr = k.ship('crescent', scale=1.9)
    k.place(cr, CR, fwd=(0.9, 0.3, 0.05), roll=-55)
    dr = k.ship('dread')
    k.place(dr, P(0.52, -0.34, 120), fwd=(-0.88, 0.46, 0.05), roll=-14)
    k.engines(dr, 0.6)
    src = k.world_pt(cr, (20, 0, 2))
    ts = k.tshield(dr, hit=src, ring=0.42)
    hit = k.shield_point(dr, ts, src)
    k.beam(src, hit, r=0.6, glow=4.0, halo=2.0)
    k.flare(src, 5, K.GOLD, 5.0, core=K.HOTGOLD, core_k=14.0)
    k.flare(hit, 2.4, K.GOLD, 5.0, core=K.HOTGOLD, core_k=10.0, light=5e5)
    gs = k.gshield(cr, hit=dr.location, vis=0.5)
    for i in range(2):
        a = k.world_pt(dr, (-4 - i * 12, 1.5, 3.0))
        b = k.shield_point(cr, gs, a + Vector((0, 0, -60 - i * 50)))
        k.beam(a, b, col=K.BLUE, core=(0.8, 0.95, 1.0), r=0.28, glow=4.0, halo=2.0)
        k.flare(b, 2.2, K.CYAN, 5.0, core_k=10.0)
    for x, y, dpt, roll in ((-0.12, -0.40, 60, 20), (0.06, -0.52, 75, -15)):
        s = k.ship('sting', scale=5.0)
        k.place(s, P(x, y, dpt), fwd=(0.9, 0.3, 0.1), roll=roll)
        k.engines(s, 0.5)
    return k


def arcadian():
    k = K.Kit(sun_dir=(-0.6, 0.5, -0.45), sun_energy=5.5, planet_c=(0, 0, -2640), rim_dir=(0.3, -0.9, 0.1), rim=1.5,
              fill_dir=(-0.1, 1, -0.2), fill=2.4, tint='teal', nebula=2.2)
    k.camera((0, 0, 0), (0, 100, -4), lens=24)
    P = k.cam_pt
    # ------------------------------------------------ the portal
    AT = P(float(K.ARGS.get('atx', -0.24)), 0.37, 520)
    n = Vector((0.80, -0.60, -0.03)).normalized()
    S = 215.0
    DZ = 0.45                                              # a short throat: its far end stays hidden behind the mouth
    rf = ST.portal(k, AT, n, S, k.sc.nf, seed=11)
    rf.scale = (S, S, DZ)
    k.light(AT + n * 260 + Vector((0, 0, 60)), (1.0, 0.85, 0.6), 3e7, 30)
    # the crescent mothership at the most dramatic moment: horns and core out and opening, the hull behind
    # them still a drawn-out gold thread in the throat (backdrop_stretch.py: its own geometry, tapered)
    cr = ST.Stretcher(k, 'crescent', AT, n, S, scale=2.5, roll=-80, depth=240 * DZ, seed=3, lines=12, glow=2.2,
                      zf=0.55, w=0.2)
    cr.set(float(K.ARGS.get('nose', 1.0)) * cr.L, tick=3)
    # corvettes on side lanes at other moments: thread-thin, half out, almost free
    for i, (off, xn, roll) in enumerate((((-0.5, 0.86), 0.50, 20), ((-0.3, -0.88), 1.50, -15))):
        cv = ST.Stretcher(k, 'acorv', AT, n, S, scale=2.8, roll=roll, off=off, a=7.0, zf=0.7, w=0.17,
                          depth=240 * DZ, seed=20 + i, lines=6, line_r=S * 0.0009, bolt_w=0.09, glow=2.2)
        cv.set(xn * cv.L, tick=5 + i)
    ac = k.ship('acorv', scale=2.6)                         # one already through and fighting
    k.place(ac, AT + n * 330 + Vector((30, 0, -34)), fwd=n, roll=15)
    k.engines(ac, 0.5)
    # ------------------------------------------------ the Terrans it is arriving on top of
    bs = k.ship('bship')
    BS = P(-0.52, -0.30, 100)
    CRP = AT + n * 120
    e = CRP - BS
    e.z = 0
    e.normalize()
    k.place(bs, BS, fwd=(-e.y, e.x, 0), roll=-28)          # broadside on to the portal, guns raised at it
    k.tshield(bs, vis=0.7)
    k.engines(bs, 0.4, length=4.0)
    loc = k.extra('bship')
    k.muzzle(bs, loc[0], 'fire', scale=0.6)
    k.muzzle(bs, loc[2], 'charge', scale=0.5)
    muz = [k.world_pt(bs, m) for m in loc]
    d = (CRP + Vector((0, 0, -20)) - muz[1]).normalized()
    k.comet(muz[1] + d * 92, d, scale=3.0)
    k.comet(muz[0] + d * 40 + Vector((0, 0, 4)), d, scale=2.2)
    k.boom(ac.location + Vector((-14, -8, 4)), 16, 'blue', age=5, light=2e5)
    k.shards(ac.location + Vector((-14, -8, 4)), 16, K.CYAN, 0.9, 30, 3, age=7)
    fgt = k.ship('frigate', scale=1.3)
    k.place(fgt, P(0.50, -0.42, 70), fwd=(-0.5, 0.86, 0.08), roll=14)
    k.engines(fgt, 0.6)
    fts = k.tshield(fgt, hit=ac.location, ring=0.4)
    fh = k.shield_point(fgt, fts, ac.location)
    k.beam(k.world_pt(ac, (7, 0, 0)), fh, r=0.45, glow=4.0, halo=2.0)
    k.impact(fh, 1.8, seed=5, light=1e5)
    for x, y, dpt in ((0.74, 0.30, 150), (0.60, 0.52, 190)):
        c = k.ship('corvette', scale=1.6)
        k.place(c, P(x, y, dpt), fwd=(-0.6, 0.8, 0.0), roll=-10)
        k.engines(c, 0.6)
    return k


k = {'terran': terran, 'arcadian': arcadian}[VAR]()
k.render(OUT)
