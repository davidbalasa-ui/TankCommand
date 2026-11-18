"""Bastion Gun (Terran gun tower): drives in packed, digs in and unfolds, then holds a ridge
against an Arcadian Lumen rush, killing two before the third breaks off.

Pilot clip for the promo toolkit."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from promo_kit import Promo  # noqa: E402

P = Promo('terran_bastion', seconds=6.0)
P.env('desert', sun=(48, 0, -40), clear=[(0, 0, 14), (22, 8, 12)], props=35)
P.flatten(0, 0, 10)
P.flatten(20, 6, 14)

# The gun tower: packed until 1.2 s (rolls in), unfolds 1.2-2.4 s.
bastion = P.load('bastion', at=(0, 0), heading=20)
bastion.root.location.x = -7
bastion.path([(0.0, (-7, -2.5)), (1.1, (0, 0))], face=False)
bastion.unfold(1.15, 2.4)
P.dust(bastion, 0.0, 1.1, every=0.15)

# Three Lumens rushing in from the north-east
lumens = []
for i, (sx, sy) in enumerate([(34, 16), (37, 9), (31, 22)]):
    a = P.load('lumen', at=(sx, sy), label=f'lumen{i}')
    lumens.append(a)
lumens[0].path([(0.0, (30, 14)), (2.8, (14, 7)), (6.0, (9, 5))])
lumens[1].path([(0.0, (33, 6)), (3.9, (15, 2)), (6.0, (12, 0))])
lumens[2].path([(0.0, (27, 20)), (3.6, (13, 12)), (4.8, (15, 15)), (6.0, (26, 22))])
for a in lumens:
    a.hover_bob(0.08, 0.9)

# Lumens shoot back: lightning bolts landing short / on the tower
lumens[0].fire(2.7, (2.5, 1.5, 0.3), kind='lightning')
lumens[2].fire(3.4, (3.0, 2.8, 0.3), kind='lightning')

# Bastion: one devastating shot about every 1.1 s once deployed
bastion.split_barrels()
bastion.aim(2.75, lumens[0], dur=0.45)
th = bastion.fire(2.8, lumens[0], kind='heavy', size=1.1)
lumens[0].destroy(th)
P.cam_shake(th, 0.08)
bastion.aim(3.9, lumens[1], dur=0.4)
th = bastion.fire(3.95, lumens[1], kind='heavy', size=1.1)
lumens[1].destroy(th)
bastion.aim(5.1, lumens[2], dur=0.35)
bastion.fire(5.15, (17.5, 16.5, 0.2), kind='heavy', size=1.1)

# Camera: low, close start on the rolling tower, swing round behind the gun as it opens,
# end over its shoulder looking down the firing line.
P.camera([
    (0.0, (-4, -11, 2.0), (-4, -1.5, 1.0), 32),
    (1.6, (5, -10, 3.2), (0, 0, 1.6), 32),
    (2.6, (-5, -6.5, 3.6), (7, 4, 1.4), 32),
    (4.2, (-5.5, 0.5, 3.4), (10, 6, 1.0), 34),
    (6.0, (-3.5, -7.5, 2.8), (6, 6, 1.2), 26),
], shake=0.02)

P.render()
