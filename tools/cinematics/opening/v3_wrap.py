"""Plays a v2 global-clock scene (space.Space / ground.Ground) back on a v3 scene's own clock, slowed:
local frame f shows global time g0 + (f - 1) * speed / 24 s. Camera keys stay in global frames (the
render evaluates the global frame, sub-frames included)."""
FPS = 24


class Wrapped:
    def __init__(self, g0, g1, seconds):
        self.nf = int(round(seconds * FPS))
        self.G0 = 1 + g0 * FPS
        self.G1 = 1 + g1 * FPS
        self.k = (self.G1 - self.G0) / max(1, self.nf - 1)
        self.shots = []

    def tmap(self, f):
        return self.G0 + (f - 1) * self.k

    def local(self, g_sec):
        G = 1 + g_sec * FPS
        return max(1, min(self.nf, int(round(1 + (G - self.G0) / self.k))))

    def shot(self, sid, ga, gb, keys, shake=()):
        a, b = self.local(ga), self.local(gb)
        if b > a:
            self.shots.append((sid, a, b if gb < (self.G1 - 1) / FPS else self.nf, keys, list(shake)))
