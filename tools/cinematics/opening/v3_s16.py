"""Scene 16 (1:50-1:55): escape and final image. v2 ending 0:57.5-1:00 slowed to 5 s."""
import space as SP
import v3_wrap as W


def build(draft=True):
    S = SP.Space(need={'ending'}, draft=draft)
    w = W.Wrapped(57.5, 60.0, 5.0)
    w.shot('A', 57.5, 60.0, S.camera_for('11'))
    return w
