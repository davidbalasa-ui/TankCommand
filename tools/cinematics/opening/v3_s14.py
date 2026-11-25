"""Scene 14 (1:39-1:45): the Shard strikes. v2 ground 0:51-0:55 slowed to 6 s, with the new forked lightning
and crystal crust."""
import ground as GR
import v3_wrap as W

SHOTS = [('10c', 51.0, 54.0), ('10d', 54.0, 55.0)]


def build(draft=True):
    G = GR.Ground(draft=draft)
    w = W.Wrapped(51.0, 55.0, 6.0)
    for sid, a, b in SHOTS:
        w.shot(sid, a, b, G.camera_for(sid))
    return w
