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
    s.buoy = 8.0; s.cool = 1.5; s.vort = 14.0; s.burn_rate = 3.5; s.expand_gain = 4.0
    s.soot_gain = 0.8; s.heat_gain = 0.9; s.weight = -0.35; s.drag = 0.7

    def boom(sim):
        sim.add_blast((cx, cy, 0.45), 0.75, fuel=1.6, heat=1.0, speed=9.0, noise=0.8, soot=0.4)
        # upward kick so it towers rather than squats
        m, _ = sim.sphere((cx, cy, 0.6), 0.9)
        sim.u[2] += m * 5.0
        # satellite fuel pockets thrown outward and up: lumpy, uneven silhouette
        for k in range(9):
            a = rng.uniform(0, 2 * math.pi); el = rng.uniform(0.15, 1.1)
            d = rng.uniform(0.7, 1.3)
            p = (cx + math.cos(a) * math.cos(el) * d, cy + math.sin(a) * math.cos(el) * d, 0.3 + math.sin(el) * d)
            sim.add_blast(p, rng.uniform(0.25, 0.45), fuel=rng.uniform(0.9, 1.8), heat=0.9, speed=rng.uniform(6, 12), noise=0.9, soot=0.3)
        # dust skirt: cool, sooty ring at the ground pushed outward
        m, d = sim.sphere((cx, cy, 0.0), 1.1)
        ring = m * (sim.pos[2] < 0.35)
        sim.dens += ring * 0.25 * np.clip(1 + 0.8 * sim.noise(2.0), 0, 2)
        sim.pulse += ring * 4.0

    run(s, work, frames, 2, events=[(0.0, boom)])


RECIPES = dict(ground_blast=ground_blast)



def _base(n, h, seed):
    s = Sim(res=n, h=h, seed=seed)
    s.buoy = 8.0; s.cool = 1.5; s.vort = 14.0; s.burn_rate = 3.5; s.expand_gain = 4.0
    s.soot_gain = 0.8; s.heat_gain = 0.9; s.weight = -0.35; s.drag = 0.7
    return s


def air_blast(work, frames=48, seed=5, res=1.0):
    """Mid-air burst (aircraft): no ground skirt, lobes in all directions, smoke drifts."""
    h = 0.06 / res; n = (int(100 * res), int(100 * res), int(110 * res))
    s = _base(n, h, seed); rng = np.random.default_rng(seed)
    c = (n[0] * h / 2, n[1] * h / 2, 2.6)
    s.wind[:] = (0.8, 0, 0)

    def boom(sim):
        sim.add_blast(c, 0.6, fuel=1.6, heat=1.0, speed=9.0, noise=0.9, soot=0.15)
        for k in range(10):
            v = rng.normal(size=3); v /= np.linalg.norm(v)
            d = rng.uniform(0.6, 1.2)
            sim.add_blast(tuple(np.array(c) + v * d), rng.uniform(0.2, 0.4), fuel=rng.uniform(0.8, 1.8), heat=0.9,
                          speed=rng.uniform(6, 12), noise=0.9, soot=0.3)
    run(s, work, frames, 2, events=[(0.0, boom)])


def small_blast(work, frames=32, seed=7, res=1.0):
    """Shell impact on ground: quick flash, dirt-laden smoke, mostly dust."""
    h = 0.03 / res; n = (int(80 * res), int(80 * res), int(90 * res))
    s = _base(n, h, seed); rng = np.random.default_rng(seed)
    s.cool = 3.0; s.soot_gain = 1.0; s.buoy = 6.0
    cx, cy = n[0] * h / 2, n[1] * h / 2

    def boom(sim):
        sim.add_blast((cx, cy, 0.15), 0.3, fuel=1.2, heat=1.0, speed=6.0, noise=0.9, soot=0.4)
        # dirt thrown up in a cone of jets
        for k in range(8):
            a = rng.uniform(0, 2 * math.pi); el = rng.uniform(0.6, 1.35); d = rng.uniform(0.25, 0.6)
            p = (cx + math.cos(a) * math.cos(el) * d, cy + math.sin(a) * math.cos(el) * d, 0.1 + math.sin(el) * d)
            m, _ = sim.sphere(p, rng.uniform(0.1, 0.18))
            sim.dens += m * 1.5
            sim.u[0] += m * math.cos(a) * math.cos(el) * 5; sim.u[1] += m * math.sin(a) * math.cos(el) * 5
            sim.u[2] += m * math.sin(el) * 7
    run(s, work, frames, 2, events=[(0.0, boom)])


def big_blast(work, frames=72, seed=11, res=1.0):
    """Structure / big unit death: bigger, longer burn, secondary pops, tall smoke."""
    h = 0.1 / res; n = (int(100 * res), int(100 * res), int(130 * res))
    s = _base(n, h, seed); rng = np.random.default_rng(seed)
    s.buoy = 10.0; s.cool = 1.4; s.burn_rate = 3.5
    cx, cy = n[0] * h / 2, n[1] * h / 2
    evs = []

    def main(sim):
        sim.add_blast((cx, cy, 0.8), 1.4, fuel=1.8, heat=1.0, speed=10.0, noise=0.9, soot=0.2)
        m, _ = sim.sphere((cx, cy, 1.0), 1.6); sim.u[2] += m * 6
        for k in range(10):
            a = rng.uniform(0, 2 * math.pi); el = rng.uniform(0.1, 1.2); d = rng.uniform(1.2, 2.2)
            p = (cx + math.cos(a) * math.cos(el) * d, cy + math.sin(a) * math.cos(el) * d, 0.5 + math.sin(el) * d)
            sim.add_blast(p, rng.uniform(0.4, 0.8), fuel=rng.uniform(1.0, 1.8), heat=0.9, speed=rng.uniform(6, 12), noise=0.9, soot=0.3)
        mm, _ = sim.sphere((cx, cy, 0.0), 2.4)
        ring = mm * (sim.pos[2] < 0.6)
        sim.dens += ring * 0.5 * np.clip(1 + 0.8 * sim.noise(2.0), 0, 2); sim.pulse += ring * 4.0
    evs.append((0.0, main))
    for tt in (0.35, 0.7):
        def pop(sim, tt=tt):
            a = rng.uniform(0, 2 * math.pi)
            p = (cx + math.cos(a) * 1.0, cy + math.sin(a) * 1.0, 0.6)
            sim.add_blast(p, 0.7, fuel=1.6, heat=1.0, speed=8, noise=0.9, soot=0.2)
        evs.append((tt, pop))
    run(s, work, frames, 2, events=evs)


def fire_loop(work, frames=96, seed=13, res=1.0):
    """Burning wreck: continuous flames + smoke from a patch. Made loopable afterwards by crossfade."""
    h = 0.03 / res; n = (int(70 * res), int(70 * res), int(110 * res))
    s = _base(n, h, seed)
    s.buoy = 7.0; s.cool = 3.0; s.burn_rate = 6.0; s.soot_gain = 0.9; s.expand_gain = 2.0; s.vort = 18.0
    cx, cy = n[0] * h / 2, n[1] * h / 2
    base_m = None

    def emit(sim, t, dt):
        nonlocal base_m
        if base_m is None:
            m, _ = sim.sphere((cx, cy, 0.05), 0.45, soft=0.6)
            base_m = m * (sim.pos[2] < 0.25)
        flick = np.clip(1 + 1.2 * sim.noise(1.5), 0, 3)
        sim.fuel += base_m * flick * 9.0 * dt
        sim.temp = np.maximum(sim.temp, base_m * 0.9)
    run(s, work, frames, 2, per_step=emit)


def smoke_plume(work, frames=120, seed=17, res=1.0):
    """Lingering dark-grey smoke column from a wreck, drifting with wind. Loop by crossfade."""
    h = 0.06 / res; n = (int(70 * res), int(70 * res), int(130 * res))
    s = _base(n, h, seed)
    s.buoy = 5.0; s.cool = 0.5; s.vort = 20.0; s.weight = -0.25; s.drag = 0.3
    s.wind[:] = (0.6, 0, 0)
    cx, cy = n[0] * h * 0.4, n[1] * h / 2
    base_m = None

    def emit(sim, t, dt):
        nonlocal base_m
        if base_m is None:
            m, _ = sim.sphere((cx, cy, 0.2), 0.45)
            base_m = m
        puls = np.clip(1 + 0.8 * sim.noise(2.0), 0, 2)
        sim.dens += base_m * puls * 14.0 * dt
        sim.temp = np.maximum(sim.temp, base_m * 0.5)
        sim.u[2] += base_m * 3.0 * dt * 10
    run(s, work, frames, 2, per_step=emit)


def dust_burst(work, frames=40, seed=19, res=1.0):
    """No fire: brown dust thrown up by an impact / landing; settles and drifts."""
    h = 0.04 / res; n = (int(100 * res), int(100 * res), int(70 * res))
    s = _base(n, h, seed); rng = np.random.default_rng(seed)
    s.buoy = 0.0; s.weight = 0.6; s.vort = 12.0; s.drag = 1.2
    cx, cy = n[0] * h / 2, n[1] * h / 2

    def boom(sim):
        m, d = sim.sphere((cx, cy, 0.0), 0.7)
        ring = m * np.clip(1 + 0.9 * sim.noise(2.0), 0, 2)
        sim.dens += ring * 1.5
        sim.pulse += ring * 12.0
        sim.u[2] += ring * 2.5
    run(s, work, frames, 2, events=[(0.0, boom)])


RECIPES.update(air_blast=air_blast, small_blast=small_blast, big_blast=big_blast,
               fire_loop=fire_loop, smoke_plume=smoke_plume, dust_burst=dust_burst)


def space_blast(work, frames=40, seed=23, res=1.0):
    """Explosion in vacuum: no buoyancy or gravity, symmetric expanding shell of lobes, thin smoke that fades."""
    h = 0.06 / res; n = (int(100 * res), int(100 * res), int(100 * res))
    s = _base(n, h, seed); rng = np.random.default_rng(seed)
    s.buoy = 0.0; s.weight = 0.0; s.drag = 0.2; s.cool = 2.2; s.soot_gain = 0.45; s.dens_decay = 0.9
    c = tuple(v * h / 2 for v in n)

    def boom(sim):
        sim.add_blast(c, 0.5, fuel=1.5, heat=1.0, speed=12.0, noise=0.9, soot=0.1)
        for k in range(14):
            v = rng.normal(size=3); v /= np.linalg.norm(v)
            sim.add_blast(tuple(np.array(c) + v * rng.uniform(0.5, 1.0)), rng.uniform(0.15, 0.35), fuel=rng.uniform(0.8, 1.6),
                          heat=0.9, speed=rng.uniform(8, 14), noise=0.9, soot=0.2)
    run(s, work, frames, 2, events=[(0.0, boom)])


RECIPES['space_blast'] = space_blast


if __name__ == '__main__':
    name, work = sys.argv[1], sys.argv[2]
    kw = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    RECIPES[name](work, **kw)
