"""Weapon FX test bench (not a promo clip): one small staged shot per effect, for look-dev of
promo_fx_weapons.py. Pick the case with FXCASE=<case>:

    cannon | autocannon | missile | laser | lightning | shield | shield_gold | shell | bomb

    FXCASE=missile python tools/promos/fx/weapons_bench.py --quality preview --frames 10,20,30 --out /tmp/x
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from promo_kit import COL, Promo  # noqa: E402

CASE = os.environ.get('FXCASE', 'cannon')
P = Promo('fxbench_' + CASE, seconds=3.0)
P.env('desert', sun=(48, 0, -40), clear=[(0, 0, 30)], props=0)
P.flatten(0, 0, 30)

if CASE in ('cannon', 'autocannon'):
    a = P.load('lancer', at=(0, 0), heading=0)
    a.split_barrels()
    if CASE == 'cannon':
        a.fire(0.3, (13, 2, 0.1), kind='cannon')
        a.fire(1.4, (12, -2, 0.1), kind='heavy', size=1.1)
    else:
        for i in range(8):
            a.fire(0.3 + 0.12 * i, (17, 0.5 * (i % 3) - 0.5, 0.1), kind='autocannon', recoil=False, spread=0.6)
    P.camera([(0, (1, -15, 3.2), (7.5, 0, 0.8), 35)])
elif CASE == 'missile':
    a = P.load('javelin', at=(0, 0), heading=0)
    P.muzzle_flash(a.muzzle(), 0.3, COL['fire'], 0.8)
    th = P.missile(a.world_at(a.muzzle(), 0.3), (34, 3, 0.2), 0.3)
    P.impact((34, 3, 0.2), th, size=1.2)
    P.camera([(0, (10, -17, 4.0), (16, 2, 2.0), 28)])
elif CASE == 'laser':
    a = P.load('lancer', at=(0, 0), heading=0)
    a.split_barrels()
    a.fire(0.3, (16, 1, 0.1), kind='laser', color=COL['laser_blue'])
    P.beam(a.world_at(a.muzzle(), 1.0), (15, -2, 0.1), 1.0, 1.8, COL['terran_neon'], width=0.12)
    P.impact((15, -2, 0.1), 1.05, size=0.8, color=COL['terran_neon'])
    P.camera([(0, (5, -10, 2.4), (8, 0, 0.8), 30)])
elif CASE == 'lightning':
    a = P.load('lumen', at=(0, 0), heading=0)
    a.fire(0.3, (14, 1, 0.1), kind='lightning')
    a.fire(1.2, (13, -2, 0.1), kind='lightning', size=1.4)
    P.camera([(0, (5, -9, 2.2), (7, 0, 0.8), 30)])
elif CASE in ('shield', 'shield_gold'):
    gold = CASE == 'shield_gold'
    hits = [(0.5, (-4.2, -3.0, 2.5)), (1.1, (-5.4, 0.5, 1.2)), (1.35, (-3.0, -3.5, 3.4))]
    P.shield_dome((0, 0, 0), 6.0, 0.1, 3.0, color=COL['arc_gold'] if gold else None, hits=hits)
    a = P.load('lancer' if gold else 'lumen', at=(0, 0), heading=0)
    s = P.load('lumen' if not gold else 'lancer', at=(-20, -6), heading=15)
    for t, p in hits:
        if gold:
            P.projectile(s.world_at(s.muzzle(), t - 0.3), p, t - 0.3, 60, COL['tracer'], size=0.15)
        else:
            P.lightning(s.world_at(s.muzzle(), t - 0.05), p, t - 0.05, t + 0.12)
    P.camera([(0, (-17, -17, 4.5), (-1, 0, 2.6), 30)])
elif CASE == 'shell':
    a = P.load('longbow', at=(0, 0), heading=0)
    a.fire(0.3, (40, 4, 0.1), kind='shell')
    P.camera([(0, (18, -30, 7), (22, 3, 4), 30)])
elif CASE == 'bomb':
    a = P.load('condor', at=(0, 0, 14), heading=0)
    for i in range(3):
        a.fire(0.3 + 0.15 * i, (10 + 2.5 * i, 0, 0.1), kind='bomb', recoil=False)
    P.camera([(0, (4, -24, 5), (8, 0, 5), 30)])

P.render()
