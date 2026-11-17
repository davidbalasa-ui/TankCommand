"""Bastion Gun promo: a packed Bastion drives in, unfolds into the gun tower and shreds a pair of Darter scouts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from promo_kit import *  # noqa

P = Promo('terran_turret', env='ground', tod='golden', ground='dry', seed=3)

# The packed Bastion rolls in from the left and stops on the spot it will hold.
packed = P.load('bastion_packed', at=(-13, -2), heading=8)
packed.drive([(0.0, -13, -2), (1.5, 0, 0)])
tower = P.deploy(packed, 'terran_turret', t0=1.55, t1=3.0)

# Two Darter scouts sweep in from the far side, firing on the move.
d1 = P.load('darter', at=(42, 14), heading=200)
d2 = P.load('darter', at=(48, 6), heading=195)
d1.drive([(2.0, 42, 14), (4.1, 13, 6), (6.0, 4, 16)], keep_speed=True)
d2.drive([(2.2, 48, 6), (4.9, 15, -3), (6.5, -2, -12)], keep_speed=True)
d1.fire(3.5, tower, miss=(1.5, -2.0, -1.2))
d2.fire(4.2, tower, miss=(-1.0, 2.2, -1.2))

# Bastion Gun: two-shot bursts 0.3 s apart, 2.0 s reload.
tower.aim(d1, 2.9, 3.3)
tower.fire(3.4, d1, weapon='cannon', burst=2, interval=0.3, kills=True)
tower.aim(d2, 4.2, 4.7)
tower.fire(5.4, d2, weapon='cannon', burst=2, interval=0.3, kills=True)

P.camera_orbit(target=(1, 0, 1.2), radius=(8.5, 11), height=(1.6, 3.6), angle=(-150, 15), lens=(30, 34))
P.render()
