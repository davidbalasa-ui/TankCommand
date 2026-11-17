"""Scene 14 (1:39-1:45): the Shard strikes, rebuilt on ground3 (2026-11-17).

  A  1- 72  medium on the Terran line: the Shard's crown charges, thick violet lightning forks into the
            tanks and crystal bursts over them, spreading down the line; their lights die
  B 73-144  medium on the Arcadian hover line: the same, the frozen hover units drop to the ground
"""
from mathutils import Vector
import ground3 as G3
from squid import ramp


def build(draft=True):
    F = G3.Field('s14', draft, focus={-1: (-92.0, -18.0), 1: (92.0, 18.0)})
    o = F.off
    F.shot('A', 1, 72, [(o + 1, Vector((-134, -56, 3.8)), Vector((-88, -12, 11)), 22),
                        (o + 72, Vector((-128, -52, 3.4)), Vector((-86, -12, 9)), 22)],
           shake=[(G3.G_STRIKE_T, 0.2, 30)])
    F.shot('B', 73, 144, [(o + 73, Vector((130, 50, 3.6)), Vector((90, 16, 8)), 22),
                          (o + 144, Vector((125, 47, 3.2)), Vector((88, 15, 7)), 22)],
           shake=[(G3.G_STRIKE_A, 0.2, 30)])
    F.cull_near_camera()
    return F
