"""Effect recipes: simulate -> VDB frames.  Usage: python make_fx.py <recipe> <work_dir> [frames]"""
import json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smokesim import Sim

FPS = 24


def run(sim, work, frames, substeps, events=None, per_step=None):
    os.makedirs(work, exist_ok=True)
    dt = 1.0 / FPS / substeps
    stats = {}
    t0 = time.time()
    for f in range(1, frames + 1):
        for s in range(substeps):
            t = ((f - 1) * substeps + s) * dt
            if events:
                for ev in events:
                    if ev[0] <= t < ev[0] + dt:
                        ev[1](sim)
            if per_step:
                per_step(sim, t, dt)
            sim.step(dt)
        fl = sim.flame + 0.2 * np.clip(sim.temp - 0.3, 0, None)
        tot = float(fl.sum() * sim.h ** 3)
        if tot > 1e-6:
            c = [float((sim.pos[i] * fl).sum() / fl.sum()) for i in range(3)]
        else:
            c = [sim.n[0] * sim.h / 2, sim.n[1] * sim.h / 2, 0.5]
        stats[f] = dict(flame_sum=tot, flame_center=c, dens_max=float(sim.dens.max()))
        sim.write_vdb(os.path.join(work, 'f%04d.vdb' % f))
        print('frame', f, 'max dens %.2f heat %.2f |u| %.1f  %.0fs' % (sim.dens.max(), sim.temp.max(), np.abs(sim.u).max(), time.time() - t0), flush=True)
    json.dump(stats, open(os.path.join(work, 'stats.json'), 'w'))
    dom = [n * sim.h for n in sim.n]
    json.dump(dict(domain=dom, frames=frames), open(os.path.join(work, 'sim.json'), 'w'))


def ground_blast(work, frames=56, seed=3, scale=1.0, res=1.0):
    h = 0.06 / res
    n = (int(100 * res), int(100 * res), int(116 * res))
    s = Sim(res=n, h=h, seed=seed)
    rng = np.random.default_rng(seed)
    cx, cy = n[0] * h / 2, n[1] * h / 2
    s.buoy = 8.0; s.cool = 1.9; s.vort = 14.0; s.burn_rate = 5.0; s.expand_gain = 4.0
    s.soot_gain = 0.8; s.heat_gain = 0.9; s.weight = -0.35; s.drag = 0.7

    def boom(sim):
        sim.add_blast((cx, cy, 0.45), 0.75, fuel=1.6, heat=1.0, speed=9.0, noise=0.8, soot=0.15)
        # upward kick so it towers rather than squats
        m, _ = sim.sphere((cx, cy, 0.6), 0.9)
        sim.u[2] += m * 5.0
        # satellite fuel pockets thrown outward and up: lumpy, uneven silhouette
        for k in range(7):
            a = rng.uniform(0, 2 * math.pi); el = rng.uniform(0.15, 1.1)
            d = rng.uniform(0.5, 0.95)
            p = (cx + math.cos(a) * math.cos(el) * d, cy + math.sin(a) * math.cos(el) * d, 0.3 + math.sin(el) * d)
            sim.add_blast(p, rng.uniform(0.22, 0.4), fuel=rng.uniform(0.8, 1.6), heat=0.8, speed=rng.uniform(4, 9), noise=0.7, soot=0.3)
        # dust skirt: cool, sooty ring at the ground pushed outward
        m, d = sim.sphere((cx, cy, 0.0), 1.1)
        ring = m * (sim.pos[2] < 0.35)
        sim.dens += ring * 0.5 * np.clip(1 + 0.8 * sim.noise(2.0), 0, 2)
        sim.pulse += ring * 6.0

    run(s, work, frames, 2, events=[(0.0, boom)])


RECIPES = dict(ground_blast=ground_blast)

if __name__ == '__main__':
    name, work = sys.argv[1], sys.argv[2]
    kw = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    RECIPES[name](work, **kw)
