"""Scene 15 (1:45-1:50): the cull. v2 ending 0:55-0:57.5 slowed to 5 s: beams rise from the planet through
both fleets."""
import space as SP
import v3_wrap as W


def build(draft=True):
    S = SP.Space(need={'ending'}, draft=draft)
    w = W.Wrapped(55.0, 57.5, 5.0)
    w.shot('A', 55.0, 57.5, S.camera_for('11'))
    return w
