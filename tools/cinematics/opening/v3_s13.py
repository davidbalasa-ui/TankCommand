"""Scene 13 (1:29-1:39): the Shard rises, rebuilt on ground3 (2026-11-17).

  A  1-120  low behind a Terran Lancer: the ground splits ahead in glowing violet fissures, the tanks
            brake, the Shard's crown breaks through and climbs; the camera tilts up with it
  B 121-240 low and wide beside a Bulwark at the Terran front: the dark crystal towers over both stopped
            armies, lit violet from inside, and pulses once
"""
from mathutils import Vector
import ground3 as G3
from squid import ramp


def build(draft=True):
    plan = [(1, 'dragonfly', 300, 90, (260, -60, 40), (-300, 40, 46), 0.4),
            (-1, 'falcon', 296, 80, (-300, 30, 34), (260, -50, 40), -0.4),
            (-1, 'condor', 420, 110, (-320, -120, 70), (300, -20, 80), 0.0)]
    F = G3.Field('s13', draft, air_plan=plan)
    o = F.off
    u = F.pick(-1, 'tank', y=-28, back=6)

    def look_a(G):
        p = F.upos(u, G)
        z = 4 + 40 * ramp(G, G3.G_BREACH - 4, 400)
        return Vector((0, p.y * 0.35, z)) - p
    F.shot('A', 1, 120, F.follow(u, o + 1, o + 120, lambda G: Vector((-11, 3.2, 1.9)), look_a,
                                  lambda G: 20 - 4 * ramp(G, 330, 400)),
           shake=[(G3.G_SPLIT, 0.12, 30), (G3.G_BREACH, 0.25, 50)])
    b = F.pick(-1, None, y=-100, back=85, kinds=('javelin', 'hauler', 'mender', 'longbow', 'watchman', 'prospector'))

    def look_b(G):
        return Vector((0, 0, 72 + 6 * ramp(G, 409, 528))) - F.upos(b, G)
    F.shot('B', 121, 240, F.follow(b, o + 121, o + 240,
                                    lambda G: Vector((-7, -13, 1.6)).lerp(Vector((-6, -11, 1.4)), ramp(G, 409, 528)),
                                    look_b, 17), shake=[(G3.G_PULSE2, 0.15, 24)])
    F.cull_near_camera()
    return F
