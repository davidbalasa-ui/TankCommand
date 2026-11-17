"""Scene 12 (1:17-1:29): ground clash, rebuilt on ground3 (2026-11-17).

  A  1- 72  low beside a Bulwark as the Terran column rolls out; Longbow shells arc overhead
  B 73-130  low in front of the Arcadian line: hover tanks bear down on us, Dragonflies and Discs overhead
  C 131-210 behind the Terran front: fire crosses the valley both ways (C2 reverse from the Arcadian side)
  D 211-288 riding with our Lancer as it fires; the first violet pulse runs through the ground under it
"""
from mathutils import Vector
import ground3 as G3
from squid import ramp


def build(draft=True):
    # aircraft placed for the cameras: Dragonflies and Discs low over the Arcadian line in B,
    # Falcons over our heads in A and D
    plan = [(1, 'dragonfly', 70, 70, (330, -40, 22), (-80, -10, 18), 0.3),
            (1, 'dragonfly', 76, 70, (340, -5, 28), (-60, 20, 24), -0.3),
            (1, 'disc', 72, 90, (300, -60, 36), (40, -30, 30), 0.0),
            (1, 'halo', 92, 60, (300, -25, 16), (-40, -40, 14), 0.4),
            (-1, 'falcon', 30, 60, (-420, -20, 20), (-40, 30, 26), 0.4),
            (-1, 'falcon', 36, 60, (-430, -40, 24), (-30, 0, 30), -0.4),
            (-1, 'condor', 200, 80, (-260, 20, 34), (200, 40, 40), 0.0),
            (-1, 'falcon', 214, 50, (-250, -10, 18), (80, 30, 22), 0.5),
            (1, 'dragonfly', 140, 70, (260, 40, 20), (-200, 0, 26), 0.3)]
    F = G3.Field('s12', draft, air_plan=plan)
    # A: the Terran column rolls out past a low camera
    bw = F.pick(-1, 'heavy', y=-30, back=10)
    F.shot('A', 1, 72, F.follow(bw, 1, 72, lambda G: Vector((16 - 0.3 * G, -11, 1.3)),
                                lambda G: Vector((4, 0, 3.2)), 22), shake=[(20, 0.05, 50)])
    # B: an Arcadian Carapace bearing down on a low camera
    ca = F.pick(1, 'heavy', y=-15, back=5)
    F.shot('B', 73, 130, F.follow(ca, 73, 130, lambda G: Vector((-34 + 0.25 * (G - 73), -8, 1.0)),
                                  lambda G: Vector((0, 0, 4.5)), 24))
    # C: behind the Terran front, fire across the valley (long lens compresses the far line)
    tf = F.pick(-1, 'heavy', y=-50, back=4)
    F.shot('C', 131, 170, F.follow(tf, 131, 170, lambda G: Vector((24 - 0.1 * (G - 131), -15, 1.3)),
                                   lambda G: Vector((0, 5, 2.6)), 24), shake=[(140, 0.06, 30)])
    af = F.pick(1, 'heavy', y=35, back=4)
    F.shot('C2', 171, 210, F.follow(af, 171, 210, lambda G: Vector((12, 6.5, 3.4)),
                                    lambda G: Vector((-60, -12, 0.0)), 24), shake=[(180, 0.05, 30)])
    # D: our Lancer; the violet pulse comes at us through the ground and runs underneath
    h = F.hero
    F.shot('D', 211, 288, F.follow(h, 211, 288,
                                   lambda G: Vector((-10, -5.5, 3.0)).lerp(Vector((-7, -7, 2.2)), ramp(G, 246, 268)),
                                   lambda G: Vector((40, 3, 0.5)).lerp(Vector((18, -2, -1.0)), ramp(G, 246, 268)), 22),
           shake=[(252, 0.12, 20)])
    # the units the cameras ride with fire on camera, and the enemy answers around them
    for G in (104, 127):
        F.fire_now(ca, G, 'heavy')
    F.near_miss(ca, 116, (-18, -14, 0))
    for G in (139, 163):
        F.fire_now(tf, G, 'heavy')
    F.near_miss(tf, 151, (-6, 16, 0))
    F.near_miss(tf, 168, (14, 10, 0), 'bolt')
    for G in (176, 200):
        F.fire_now(af, G, 'heavy')
    F.near_miss(af, 188, (-16, 18, 0))
    for G in (217, 239, 261, 283):
        F.fire_now(h, G, 'bolt')
    F.near_miss(h, 226, (20, 9, 0))
    F.near_miss(h, 274, (14, 12, 0), 'heavy')
    F.cull_near_camera()
    return F
