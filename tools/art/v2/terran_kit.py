"""Shared Terran pieces: track units, wheels, rail guns, hull fittings."""
import math

import forge as F
from forge import box, cyl, hull, loft, plate, prism, sym, tube


def wheel(c, r, w, side=1, zone='wheel', sides=12, glow=False):
    """Road wheel with a dished face and hub, axle along Y, detailed face on `side`."""
    x, y, z = c
    y0, y1 = y - side * w / 2, y + side * w / 2
    prof = [(0, r), (0.8, r), (0.86, r * 0.62), (0.7, r * 0.56), (0.7, r * 0.3), (1.0, r * 0.26), (1.1, r * 0.14)]
    out = [tube((x, y0, z), (x, y1, z), prof, sides, zone, sharp=40)]
    if glow:
        out.append(cyl((x, y1, z), (x, y1 + side * 0.035, z), r * 0.13, 8, 'glow'))
    return out


def track_path(x0, x1, r=0.44, zs=0.68, zb=0.4, rb=0.4, n=7):
    """Closed side-view path of a track run: (x, z) points and tangent angles."""
    pts = []
    for cx, cz, rr, a0, a1 in ((x1 - r, zs, r, 90, -40), (x1 - 1.15, zb, rb, -40, -90),
                               (x0 + 1.15, zb, rb, -90, -140), (x0 + r, zs, r, -140, -270)):
        for k in range(n):
            a = math.radians(a0 + (a1 - a0) * k / (n - 1))
            pts.append((cx + rr * math.cos(a), cz + rr * math.sin(a)))
    return pts


def track_unit(x0, x1, y, w=0.42, side=1, nwheels=5, skirt=True, zs=0.68, cleat=0.3, accent=True, skirt_top=1.28):
    """One complete track pod centred on y: band with cleats, sprocket, idler, road wheels, skirt."""
    path = track_path(x0, x1, zs=zs)
    cx = sum(p[0] for p in path) / len(path)
    cz = sum(p[1] for p in path) / len(path)
    inner = []
    for px, pz in path:
        d = math.hypot(px - cx, pz - cz)
        k = (d - 0.13) / d
        inner.append((cx + (px - cx) * k, cz + (pz - cz) * k * 0.82 + 0.03))
    n = len(path)
    rings = [[(px, y - w, pz) for px, pz in path], [(px, y + w, pz) for px, pz in path],
             [(px, y + w, pz) for px, pz in inner], [(px, y - w, pz) for px, pz in inner]]
    verts = [p for r in rings for p in r]
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        for k in range(n):
            m = (k + 1) % n
            faces.append([i * n + k, i * n + m, j * n + m, j * n + k])
    scroll = F.ST.get('tread')
    if scroll:   # units: a plain band with its own scrolling cleat texture (see forge._tread_surface)
        with F.group('Tread'):
            F._new(verts, faces, 'track', sharp=40)
        F.ST['tread_paths'].append(dict(path=list(path), y=y, w=w))
    else:
        F._new(verts, faces, 'track', sharp=40)
    # Cleats along the outer run.
    acc = 0.0
    for k in range(0 if scroll else n):
        ax, az = path[k]
        bx, bz = path[(k + 1) % n]
        seg = math.hypot(bx - ax, bz - az)
        while acc < seg:
            t = acc / seg
            px, pz = ax + (bx - ax) * t, az + (bz - az) * t
            ang = math.degrees(math.atan2(bz - az, bx - ax))
            c = box((0, 0, 0.0), (0.085, w + 0.03, 0.05), 'track')
            c['uv'] = 0.3
            F.rot(c, 'Y', -ang)
            F.move(c, (px, y, pz))
            acc += cleat
        acc -= seg
    yo = y + side * (w * 0.55)
    ww = w * 0.9
    # Sprocket (front) and idler (rear), then road wheels.
    wheel((x1 - 0.44, yo, zs), 0.36, ww, side, glow=True)
    wheel((x0 + 0.44, yo, zs), 0.36, ww, side)
    span = (x1 - 1.15) - (x0 + 1.15)
    for i in range(nwheels):
        wx = x0 + 1.15 + span * i / (nwheels - 1)
        wheel((wx, yo, 0.42), 0.34, ww, side, glow=(i % 2 == 1))
    # Suspension beam behind the wheels.
    box(((x0 + x1) / 2, y - side * w * 0.2, 0.5), ((x1 - x0) / 2 - 0.5, w * 0.5, 0.16), 'dark')
    if skirt:
        ys = y + side * (w + 0.02)
        ye = ys + side * 0.09
        a, b = min(ys, ye), max(ys, ye)
        L = x1 - x0
        m = 4
        for i in range(m):  # segmented armour skirts with a stepped lower edge
            sx0 = x0 + 0.25 + (L - 0.75) * i / m
            sx1 = x0 + 0.25 + (L - 0.75) * (i + 1) / m - 0.05
            low = 0.72 + (0.08 if i % 2 else 0.0)
            prof = [(sx0, low + 0.1), (sx0 + 0.12, low), (sx1 - 0.12, low), (sx1, low + 0.1), (sx1, skirt_top), (sx0, skirt_top)]
            prism(prof, a, b, 'armor', bevel=0.025)
        # Front fender wedge.
        prism([(x1 - 0.5, 0.95), (x1 + 0.05, 1.02), (x1 - 0.05, skirt_top), (x1 - 0.5, skirt_top)], a, b, 'armor', bevel=0.02)
        prism([(x0 - 0.02, 1.0), (x0 + 0.22, 0.92), (x0 + 0.22, skirt_top), (x0 + 0.05, skirt_top)], a, b, 'armor', bevel=0.02)
        if accent:
            yl = ye + side * 0.012
            box((x0 + L * 0.3, yl, skirt_top - 0.12), (L * 0.1, 0.012, 0.018), 'glow')
            box((x0 + L * 0.62, yl, skirt_top - 0.12), (L * 0.1, 0.012, 0.018), 'glow')
            box((x1 - 0.72, yl, skirt_top - 0.26), (0.2, 0.012, 0.03), 'amber')
            box((x0 + 0.6, yl, skirt_top - 0.26), (0.12, 0.012, 0.03), 'amber')
        # Fender top.
        box(((x0 + x1) / 2, y + side * 0.03, skirt_top + 0.03), ((x1 - x0) / 2 - 0.05, w + 0.1, 0.035), 'armor', bevel=0.02)


def railgun(x0, x1, y, z, r=0.13, coil=True, muzzle=True):
    """Long rail barrel: octagonal sleeve, glowing coil cage, twin rails and a slotted muzzle block."""
    L = x1 - x0
    xs = x0 + L * 0.2
    xc = x0 + L * 0.44
    tube((x0, y, z), (xs, y, z), [(0, r * 1.9), (0.85, r * 1.9), (1, r * 1.5)], 8, 'armor', sharp=30)
    if coil:
        cyl((xs, y, z), (xc, y, z), r * 0.95, 10, 'coil')
        for k in range(4):
            px = xs + (xc - xs) * (k + 0.5) / 4
            tube((px - 0.045, y, z), (px + 0.045, y, z), [(0, r * 1.45), (1, r * 1.45)], 8, 'dark', sharp=30)
        for a in (45, 135, 225, 315):
            dy, dz = math.cos(math.radians(a)) * r * 1.3, math.sin(math.radians(a)) * r * 1.3
            box(((xs + xc) / 2, y + dy, z + dz), ((xc - xs) / 2, 0.022, 0.022), 'dark')
    else:
        xc = xs
    tube((xc, y, z), (x1, y, z), [(0, r * 1.5), (0.06, r * 1.5), (0.08, r), (1, r * 0.92)], 8, 'barrel', sharp=30)
    for dz in (r * 1.05, -r * 1.05):
        box(((xc + x1) / 2 + 0.05, y, z + dz), ((x1 - xc) / 2 - 0.1, r * 0.34, r * 0.2), 'dark', bevel=0.01)
    if muzzle:
        # Slotted muzzle brake: flared octagonal sleeve with dark vent slots and a thin glow ring.
        tube((x1 - 0.42, y, z), (x1 + 0.12, y, z), [(0, r * 1.0), (0.12, r * 1.5), (0.8, r * 1.5), (1, r * 1.25)], 8, 'armor', sharp=30)
        for dx in (-0.25, -0.12, 0.01):
            box((x1 + dx, y, z), (0.035, r * 1.56, r * 0.42), 'dark')
        cyl((x1 - 0.46, y, z), (x1 - 0.42, y, z), r * 1.2, 8, 'glow')
        cyl((x1 + 0.115, y, z), (x1 + 0.125, y, z), r * 0.8, 8, 'dark')


def gun(x0, x1, y, z, r=0.07, zone='barrel'):
    """Plain autocannon barrel with a flash hider."""
    tube((x0, y, z), (x1, y, z), [(0, r * 1.7), (0.25, r * 1.7), (0.27, r), (0.9, r), (0.9, r * 1.5), (1, r * 1.5)], 8, zone)


def antenna(x, y, z, h, tip='amber'):
    cyl((x, y, z), (x, y, z + 0.12), 0.05, 6, 'dark')
    cyl((x, y, z + 0.12), (x, y, z + h), 0.018, 4, 'dark')
    box((x, y, z + h), (0.03, 0.03, 0.03), tip)


def vent(c, s, zone='vent'):
    """Louvred grille with a raised frame (s = half sizes)."""
    (x, y, z), (sx, sy, sz) = c, s
    box((x, y, z - sz * 0.5), (sx + 0.04, sy + 0.04, sz * 0.5), 'armor', bevel=0.015)
    box((x, y, z + sz * 0.05), (sx, sy, sz * 0.5), zone)


def hatch(x, y, z, r=0.3, sides=8):
    tube((x, y, z), (x, y, z + 0.1), [(0, r), (0.6, r), (1, r * 0.82)], sides, 'armor', sharp=30)
    box((x + r * 0.5, y, z + 0.11), (r * 0.25, 0.04, 0.02), 'dark')


def light(c, s, zone='glow'):
    (x, y, z), (sx, sy, sz) = c, s
    box((x - sx * 0.6, y, z), (sx, sy + 0.025, sz + 0.025), 'dark', bevel=0.012)
    box((x + sx * 0.5, y, z), (0.012, sy, sz), zone)


def stow(c, s):
    box(c, s, 'armor', bevel=0.03)
    box((c[0], c[1], c[2] + s[2]), (s[0] * 0.9, s[1] * 0.25, 0.012), 'dark')


def smoke(x, y, z, side=1, n=3):
    for k in range(n):
        o = cyl((x + k * 0.17, y, z), (x + k * 0.17 + 0.2, y + side * 0.12, z + 0.16), 0.06, 6, 'dark')
        _ = o


def chevron(x, y, z, s=0.14, zone='amber', axis='z'):
    """Small V marking lying on a top surface."""
    for sgn in (1, -1):
        b = box((0, 0, 0), (s, 0.018, 0.008), zone)
        F.rot(b, 'Z', sgn * 35)
        F.move(b, (x, y + sgn * s * 0.5, z))


def tank_hull(L=6.4, hw=1.22, top=1.42, nose=0.95, zone='hull'):
    """Low angular hull with a long sloped glacis and sponson undercut."""
    x0, x1 = -L / 2, L / 2
    return hull([
        (x0, [(0, 0.62), (hw * 0.82, 0.62), (hw * 0.95, 0.95), (hw * 0.88, top - 0.2), (0, top - 0.2)]),
        (x0 + 0.5, [(0, 0.48), (hw * 0.86, 0.48), (hw, 0.95), (hw * 0.92, top), (0, top)]),
        (x1 - 2.1, [(0, 0.46), (hw * 0.86, 0.46), (hw, 0.95), (hw * 0.92, top), (0, top)]),
        (x1 - 0.55, [(0, 0.5), (hw * 0.84, 0.5), (hw * 0.96, 0.9), (hw * 0.86, nose + 0.12), (0, nose + 0.16)]),
        (x1, [(0, 0.72), (hw * 0.76, 0.72), (hw * 0.82, 0.84), (hw * 0.76, nose), (0, nose)]),
    ], zone, bevel=0.04)


def hull_fittings(L=6.4, hw=1.22, top=1.42, nose=0.95):
    """Engine deck, glacis plate, lights and tow gear common to the tracked family."""
    x0, x1 = -L / 2, L / 2
    # Applique glacis plate and lower-front grille.
    g0, g1 = x1 - 2.0, x1 - 0.62
    gz0, gz1 = top + 0.035, nose + 0.165
    loft([[(g0, -hw * 0.7, gz0), (g0, hw * 0.7, gz0), (g1, hw * 0.66, gz1), (g1, -hw * 0.66, gz1)],
          [(g0, -hw * 0.7, gz0 + 0.05), (g0, hw * 0.7, gz0 + 0.05), (g1, hw * 0.66, gz1 + 0.05), (g1, -hw * 0.66, gz1 + 0.05)]],
         'armor', bevel=0.02)
    box((x1 + 0.03, 0, 0.82), (0.03, hw * 0.6, 0.085), 'grille')
    for s in (1, -1):
        light((x1 - 0.28, s * hw * 0.62, nose + 0.2), (0.07, 0.15, 0.045))
        box((x1 + 0.05, s * hw * 0.5, 0.62), (0.07, 0.06, 0.09), 'dark', bevel=0.02)  # tow lugs
        vent((x0 + 0.95, s * hw * 0.45, top + 0.03), (0.5, hw * 0.3, 0.05), 'vent')
        cyl((x0 - 0.02, s * hw * 0.55, top - 0.42), (x0 - 0.22, s * hw * 0.55, top - 0.42), 0.09, 8, 'dark')  # exhausts
        box((x0 - 0.02, s * hw * 0.55, top - 0.7), (0.02, 0.14, 0.04), 'red')
    box((x0 + 0.95, 0, top + 0.05), (0.42, 0.07, 0.035), 'armor', bevel=0.015)
    box((x0 - 0.03, 0, 0.9), (0.03, hw * 0.35, 0.16), 'vent')


def chassis(L=6.4, hw=1.22, top=1.42, pod=1.68, w=0.42, nwheels=5, nose=0.95, stowage=True, fittings=True):
    """Complete tracked chassis: hull, fittings, both track pods, sponsons and fender stowage."""
    tank_hull(L, hw, top, nose)
    if fittings:
        hull_fittings(L, hw, top, nose)
    for s in (1, -1):
        track_unit(-L / 2 - 0.15, L / 2 - 0.1, s * pod, w=w, side=s, nwheels=nwheels)
        box((0.0, s * (hw + 0.02), 1.1), (L / 2 - 0.5, pod - w - hw + 0.08, 0.2), 'dark')
        if stowage:
            stow((-L / 2 + 1.0, s * pod, 1.43), (0.5, w * 0.62, 0.1))
            # Tool rail and spare links on the fender.
            box((0.6, s * pod, 1.37), (0.7, 0.03, 0.03), 'dark')
            for k in range(3):
                box((L / 2 - 1.4 + k * 0.2, s * pod, 1.37), (0.08, w * 0.5, 0.03), 'track')
    return top


def tire(c, r, w, side=1, sides=14, glow=True):
    """Big off-road tyre with a deep armoured hub."""
    x, y, z = c
    y0, y1 = y - side * w / 2, y + side * w / 2
    tube((x, y0, z), (x, y1, z), [(0, r * 0.86), (0.12, r), (0.88, r), (1, r * 0.86), (1, r * 0.62), (0.85, r * 0.6)], sides, 'track', sharp=40)
    tube((x, y0, z), (x, y1 - side * w * 0.12, z), [(0, r * 0.62), (1, r * 0.62), (1, r * 0.3), (1.12, r * 0.24)], 10, 'wheel', sharp=40)
    for k in range(sides):  # tread lugs
        a = 2 * math.pi * k / sides
        b = box((0, 0, r + 0.01), (0.07, w * 0.5, 0.035), 'track')
        b['uv'] = 0.3
        F.rot(b, 'Y', math.degrees(a))
        F.move(b, (x, y, z))
    if glow:
        cyl((x, y1 - side * w * 0.12, z), (x, y1 - side * w * 0.06, z), r * 0.12, 8, 'glow')


def missile_box(c, s, nx=2, nz=2, tip='red', zone='armor'):
    """Box launcher facing +X with a grid of tubes and coloured missile tips."""
    (x, y, z), (sx, sy, sz) = c, s
    box(c, s, zone, bevel=0.035)
    box((x + sx + 0.005, y, z), (0.01, sy * 0.92, sz * 0.9), 'dark')
    for i in range(nx):
        for j in range(nz):
            py = y - sy + sy * 2 * (i + 0.5) / nx
            pz = z - sz + sz * 2 * (j + 0.5) / nz
            r = min(sy / nx, sz / nz) * 0.72
            tube((x + sx - 0.02, py, pz), (x + sx + 0.03, py, pz), [(0, r * 1.12), (1, r * 1.12), (1, r * 0.9), (0.3, r * 0.88)], 8, 'plate')
            tube((x + sx - 0.05, py, pz), (x + sx + 0.07, py, pz), [(0, r * 0.7), (0.4, r * 0.7), (1, r * 0.12)], 8, tip)
    box((x - sx - 0.01, y, z), (0.012, sy * 0.8, sz * 0.75), 'vent')
    box((x, y, z + sz + 0.012), (sx * 0.8, sy * 0.12, 0.012), 'dark')


def beacon(x, y, z, zone='amber'):
    cyl((x, y, z), (x, y, z + 0.05), 0.09, 8, 'dark')
    tube((x, y, z + 0.05), (x, y, z + 0.2), [(0, 0.075), (0.7, 0.075), (1, 0.03)], 8, zone)


def plus(x, y, z, s=0.22, zone='glow'):
    """Repair cross lying flat on a top surface."""
    box((x, y, z), (s, s * 0.3, 0.01), zone)
    box((x, y, z), (s * 0.3, s, 0.01), zone)
