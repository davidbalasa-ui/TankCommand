"""Scene 13 (1:29-1:39): the Shard rises. v2 ground 0:47-0:51 slowed to 10 s (the ground splits, the new
detailed Shard rises out of it and pulses)."""
import ground as GR
import v3_wrap as W

SHOTS = [('10a', 47.0, 49.0), ('10b', 49.0, 51.0)]


def build(draft=True):
    G = GR.Ground(draft=draft)
    w = W.Wrapped(47.0, 51.0, 10.0)
    for sid, a, b in SHOTS:
        w.shot(sid, a, b, G.camera_for(sid))
    return w
