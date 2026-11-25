"""Scene 11 (1:12-1:17): the drop. v2 drop shot (0:35-0:38) slowed to 5 s: Terran drop ships and Arcadian
seed pods fall side by side into Vesper's air, heat shields flaring orange and gold; white-out at the end."""
import space as SP
import v3_wrap as W


def build(draft=True):
    S = SP.Space(need={'drop'}, draft=draft)
    w = W.Wrapped(35.0, 38.0, 5.0)
    w.shot('A', 35.0, 38.0, S.camera_for('08a'))
    return w
