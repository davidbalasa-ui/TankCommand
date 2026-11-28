"""Scene 12: ground clash. v4 pass 3: opens 3.4 s earlier so the drop ship's long braking burn is seen. v2 ground 0:38-0:47 slowed to 12 s, now with the full unit mix on
both sides and many more aircraft (see ground.py)."""
import ground as GR
import v3_wrap as W

SHOTS = [('08b', 34.6, 39.0), ('09a', 39.0, 41.0), ('09b', 41.0, 42.0), ('09c', 42.0, 44.0), ('09d', 44.0, 47.0)]


def build(draft=True):
    G = GR.Ground(draft=draft)
    w = W.Wrapped(34.6, 47.0, 12.4)
    for sid, a, b in SHOTS:
        w.shot(sid, a, b, G.camera_for(sid))
    return w
