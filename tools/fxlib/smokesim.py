"""Small 3D fire/smoke solver (numpy) that writes OpenVDB frames for Cycles.

Blender's Mantaflow is broken in the pip bpy build, so this is a compact
stable-fluids solver: semi-Lagrangian MacCormack advection, buoyancy,
vorticity confinement, combustion with gas expansion, and an exact
Neumann pressure solve via DCT.  Collocated grid, axis order [x, y, z], z up.

Fields written per frame: density (soot), heat (0..1, normalised temp),
flame (burn rate, for the hottest emission), fuel.
"""
import math, os, sys, json
import numpy as np
from scipy import fft as sfft
from scipy.ndimage import map_coordinates, gaussian_filter

VDB_SITE = '/home/user/bvenv/lib/python3.13/site-packages/bpy/5.3/python/lib/python3.13/site-packages'


class Sim:
    def __init__(self, res=(96, 96, 128), h=0.05, seed=1):
        self.n = res
        self.h = h
        nx, ny, nz = res
        self.u = np.zeros((3, nx, ny, nz), np.float32)
        self.dens = np.zeros(res, np.float32)
        self.temp = np.zeros(res, np.float32)
        self.fuel = np.zeros(res, np.float32)
        self.flame = np.zeros(res, np.float32)
        self.expand = np.zeros(res, np.float32)  # divergence source this step (1/s)
        self.pulse = np.zeros(res, np.float32)   # blast expansion (1/s), decays
        self.pulse_decay = 10.0
        self.rng = np.random.default_rng(seed)
        self.grid = np.stack(np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing='ij')).astype(np.float32)
        self.pos = self.grid * h + h * 0.5  # world positions (metres, domain-local)
        # DCT Laplacian eigenvalues (Neumann, cell-centred)
        lam = []
        for i, m in enumerate(res):
            k = np.arange(m)
            lam.append((2 * np.cos(np.pi * k / m) - 2) / h ** 2)
        L = lam[0][:, None, None] + lam[1][None, :, None] + lam[2][None, None, :]
        L[0, 0, 0] = 1.0
        self.L = L.astype(np.float32)
        # params
        self.buoy = 4.0       # m/s^2 per unit heat
        self.weight = 0.6     # soot weight
        self.cool = 1.1       # heat decay per second
        self.vort = 6.0       # vorticity confinement
        self.ignite = 0.2
        self.burn_rate = 6.0  # fraction of fuel per second when hot
        self.heat_gain = 1.6
        self.soot_gain = 1.4
        self.expand_gain = 6.0
        self.dens_decay = 0.0
        self.drag = 0.15
        self.wind = np.zeros(3, np.float32)
        self.edge_fade = self._edge_mask()

    # --- helpers ---------------------------------------------------------
    def _edge_mask(self, w=4):
        m = np.ones(self.n, np.float32)
        for ax, nn in enumerate(self.n):
            r = np.ones(nn, np.float32)
            ramp = np.linspace(0, 1, w + 2)[1:-1]
            r[:w] = ramp
            if not (ax == 2):
                r[-w:] = ramp[::-1]
            else:
                r[-w:] = ramp[::-1]
            shape = [1, 1, 1]; shape[ax] = nn
            m = m * r.reshape(shape)
        # floor (z=0) is a solid wall: no fade there
        return m

    def sample(self, f, coords, order=1):
        return map_coordinates(f, coords, order=order, mode='nearest', prefilter=False).astype(np.float32)

    def back(self, dt, u):
        return self.grid - u * (dt / self.h)

    def _weights(self, c):
        nx, ny, nz = self.n
        cx = np.clip(c[0], 0, nx - 1.001); cy = np.clip(c[1], 0, ny - 1.001); cz = np.clip(c[2], 0, nz - 1.001)
        i = cx.astype(np.int32); j = cy.astype(np.int32); k = cz.astype(np.int32)
        fx = cx - i; fy = cy - j; fz = cz - k
        base = (i * ny + j) * nz + k
        offs = [(dx * ny + dy) * nz + dz for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]
        ws = []
        for dx in (0, 1):
            wx = fx if dx else 1 - fx
            for dy in (0, 1):
                wy = fy if dy else 1 - fy
                for dz in (0, 1):
                    wz = fz if dz else 1 - fz
                    ws.append(wx * wy * wz)
        return base, offs, ws

    def _interp(self, f, W, minmax=False):
        base, offs, ws = W
        flat = f.ravel()
        acc = None; mn = mx = None
        for o, w in zip(offs, ws):
            v = flat[base + o]
            acc = v * w if acc is None else acc + v * w
            if minmax:
                mn = v if mn is None else np.minimum(mn, v)
                mx = v if mx is None else np.maximum(mx, v)
        return acc, mn, mx

    def advect_set(self, fields, dt):
        """MacCormack advection with min/max clamping."""
        Wb = self._weights(self.back(dt, self.u))
        Wf = self._weights(self.grid + self.u * (dt / self.h))
        out = []
        for f in fields:
            a, mn, mx = self._interp(f, Wb, True)
            b, _, _ = self._interp(a, Wf)
            out.append(np.clip(a + 0.5 * (f - b), mn, mx).astype(np.float32))
        return out

    def grad(self, f):
        g = np.empty((3,) + f.shape, np.float32)
        for ax in range(3):
            g[ax] = (np.roll(f, -1, ax) - np.roll(f, 1, ax)) / (2 * self.h)
            # one-sided at walls
            sl0 = [slice(None)] * 3; sl0[ax] = 0
            sl1 = [slice(None)] * 3; sl1[ax] = -1
            g[ax][tuple(sl0)] = 0
            g[ax][tuple(sl1)] = 0
        return g

    def div(self, u):
        d = np.zeros(u.shape[1:], np.float32)
        for ax in range(3):
            up = np.roll(u[ax], -1, ax); dn = np.roll(u[ax], 1, ax)
            sl0 = [slice(None)] * 3; sl0[ax] = 0
            sl1 = [slice(None)] * 3; sl1[ax] = -1
            dn[tuple(sl0)] = -u[ax][tuple(sl0)]  # wall: mirrored normal velocity
            up[tuple(sl1)] = -u[ax][tuple(sl1)]
            d += (up - dn) / (2 * self.h)
        return d

    def project(self):
        rhs = self.div(self.u) - self.expand
        ph = sfft.dctn(rhs, type=2, norm='ortho', workers=4)
        ph /= self.L
        ph[0, 0, 0] = 0
        p = sfft.idctn(ph, type=2, norm='ortho', workers=4).astype(np.float32)
        self.u -= self.grad(p)
        # walls: zero normal velocity at floor; other walls open-ish (damped)
        self.u[2][:, :, 0] = np.maximum(self.u[2][:, :, 0], 0)

    def curl(self, u):
        g = [self.grad(u[i]) for i in range(3)]
        return np.stack([g[2][1] - g[1][2], g[0][2] - g[2][0], g[1][0] - g[0][1]])

    def vorticity(self, dt):
        w = self.curl(self.u)
        mag = np.sqrt((w ** 2).sum(0)) + 1e-6
        N = self.grad(mag)
        N /= (np.sqrt((N ** 2).sum(0)) + 1e-6)
        f = np.stack([N[1] * w[2] - N[2] * w[1], N[2] * w[0] - N[0] * w[2], N[0] * w[1] - N[1] * w[0]])
        # only where there is stuff, so empty air doesn't spin
        mask = np.clip(self.dens * 2 + self.temp * 2, 0, 1)
        self.u += dt * self.vort * self.h * f * mask

    # --- sources ---------------------------------------------------------
    def sphere(self, c, r, soft=0.5):
        d = np.sqrt(((self.pos - np.array(c, np.float32).reshape(3, 1, 1, 1)) ** 2).sum(0))
        return np.clip((r - d) / (r * soft + 1e-6), 0, 1).astype(np.float32), d

    def noise(self, sigma=2.0, amp=1.0):
        n = gaussian_filter(self.rng.standard_normal(self.n).astype(np.float32), sigma)
        return n / (n.std() + 1e-6) * amp

    def add_blast(self, c, r, fuel=1.0, heat=1.0, speed=8.0, noise=0.6, soot=0.2):
        m, d = self.sphere(c, r)
        nz = 1 + noise * self.noise(2.5)
        m = m * np.clip(nz, 0, 2)
        self.fuel += fuel * m
        self.temp += heat * m
        self.dens += soot * m
        # radial blast: a divergence pulse (projection turns it into outward flow)
        self.pulse += m * (3.0 * speed / r)

    # --- step ------------------------------------------------------------
    def step(self, dt):
        # combustion
        hot = np.clip((self.temp - self.ignite) / 0.2, 0, 1)
        burn = np.minimum(self.fuel, self.fuel * self.burn_rate * dt * hot)
        self.fuel -= burn
        self.temp += burn * self.heat_gain
        self.dens += burn * self.soot_gain
        self.flame = burn / dt * 0.15 + self.flame * 0.5
        self.expand = burn / dt * self.expand_gain * 0.1 + self.pulse
        self.pulse *= math.exp(-self.pulse_decay * dt)
        # forces
        self.u[2] += dt * (self.buoy * self.temp - self.weight * self.dens)
        self.u += dt * self.wind.reshape(3, 1, 1, 1) * np.clip(self.dens * 3, 0, 1)
        self.vorticity(dt)
        self.u *= (1 - self.drag * dt)
        self.project()
        # advect
        ux, uy, uz, d, t, f = self.advect_set([self.u[0], self.u[1], self.u[2], self.dens, self.temp, self.fuel], dt)
        self.u = np.stack([ux, uy, uz])
        self.dens = np.maximum(d, 0) * (1 - self.dens_decay * dt)
        self.temp = np.clip(t, 0, 2.0) * math.exp(-self.cool * dt)
        self.fuel = np.maximum(f, 0)
        self.dens *= self.edge_fade ** (dt * 10)
        self.temp *= self.edge_fade ** (dt * 10)

    # --- output ----------------------------------------------------------
    def write_vdb(self, path, origin=(0, 0, 0)):
        if VDB_SITE not in sys.path:
            sys.path.append(VDB_SITE)
        import openvdb as vdb
        grids = []
        tr = vdb.createLinearTransform(voxelSize=self.h)
        tr.postTranslate(tuple(float(v) for v in (np.array(origin) + self.h * 0.5)))
        for name, f in (('density', self.dens), ('heat', np.clip(self.temp, 0, 4)), ('flame', np.clip(self.flame, 0, 1.5)), ('fuel', self.fuel)):
            g = vdb.FloatGrid()
            g.copyFromArray(np.ascontiguousarray(f), tolerance=1e-4)
            g.name = name
            g.transform = tr
            grids.append(g)
        vdb.write(path, grids=grids)
