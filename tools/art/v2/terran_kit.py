"""Shared Terran pieces: track units, wheels, rail guns, hull fittings."""
import math

import forge as F
from forge import box, cyl, hull, loft, plate, prism, sym, tube, sweep, orb


def wheel(c, r, w, side=1, zone='wheel', sides=12, glow=False):
    """Road wheel with a dished face and hub, axle along Y, detailed face on `side`."""
    x, y, z = c
    y0, y1 = y - side * w / 2, y + side * w / 2
    prof = [(0, r), (0.8, r), (0.86, r * 0.62), (0.7, r * 0.56), (0.7, r * 0.3), (1.0, r * 0.26), (1.1, r * 0.14)]
    out = [tube((x, y0, z), (x, y1, z), prof, sides, zone, sharp=40)]
    out.append(cyl((x, y1 - side * w * 0.14, z), (x, y1 - side * w * 0.1, z), r * 0.5, sides, 'steel'))
    for k in range(6):   # bolt ring, so rotation reads
        a = math.pi * k / 3
        box((x + math.cos(a) * r * 0.4, y1 - side * w * 0.08, z + math.sin(a) * r * 0.4), (r * 0.055, 0.012, r * 0.055), 'dark')
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
        # Fender top: stepped angled segments over the inner two thirds, so the track run shows from above.
        fy, fw = y - side * w * 0.32, w * 0.74
        segs = [(x1 - 1.35, x1 + 0.06, 11, 0.0, 'armor'), (x1 - 3.1, x1 - 1.41, 0, 0.035, 'plate'),
                (x0 + 1.25, x1 - 3.16, 0, 0.0, 'armor'), (x0 - 0.04, x0 + 1.19, 9, 0.02, 'armor')]
        for fa, fb, tilt, dz, zn in segs:
            if fb - fa < 0.3:
                continue
            b = box(((fa + fb) / 2, fy, skirt_top + 0.03 + dz), ((fb - fa) / 2, fw, 0.04), zn, bevel=0.025)
            if tilt:
                F.rot(b, 'Y', tilt, about=((fa if fb > x1 - 0.5 else fb), 0, skirt_top + 0.03))
            # outer lip rail and a bracket down to the skirt
            box(((fa + fb) / 2, fy + side * fw, skirt_top + 0.0 + dz), ((fb - fa) / 2 - 0.08, 0.025, 0.05), 'dark')
            box(((fa + fb) / 2, y + side * w * 0.72, skirt_top - 0.03), (0.05, w * 0.32, 0.03), 'steel')
        box((x0 + 0.62, fy, skirt_top + 0.085), (0.42, fw * 0.8, 0.012), 'hazard')
        # Return rollers and bare track links seen through the gap.
        for k in range(3):
            rx = x0 + (x1 - x0) * (0.3 + 0.2 * k)
            cyl((rx, y - side * w * 0.2, 0.9), (rx, y + side * w * 0.9, 0.9), 0.11, 8, 'steel')


def _railgun(x0, x1, y, z, r=0.13, coil=True, muzzle=True, evac=False):
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
    if evac:   # bore evacuator bulge and a thermal sleeve with clamp rings
        xe = xc + (x1 - xc) * 0.52
        tube((xe - r * 2.2, y, z), (xe + r * 2.2, y, z), [(0, r), (0.18, r * 1.75), (0.82, r * 1.75), (1, r)], 10, 'plate', sharp=30)
        for kk in range(3):
            px = xc + (x1 - xc) * (0.14 + 0.1 * kk)
            cyl((px - 0.03, y, z), (px + 0.03, y, z), r * 1.25, 10, 'steel')
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
    box((x + (n - 1) * 0.085, y - side * 0.02, z - 0.02), (n * 0.1, 0.03, 0.07), 'plate', bevel=0.015)
    for k in range(n):
        for j in (0, 1):
            p0 = (x + k * 0.17, y + side * j * 0.02, z + j * 0.13)
            p1 = (p0[0] + 0.24, p0[1] + side * 0.16, p0[2] + 0.17)
            tube(p0, p1, [(0, 0.062), (0.8, 0.062), (0.82, 0.075), (1, 0.075), (1, 0.05), (0.85, 0.045)], 8, 'dark')
            cyl(p1, (p1[0] + 0.004, p1[1] + side * 0.003, p1[2] + 0.003), 0.045, 8, 'steel')


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
        box((x1 + 0.05, s * hw * 0.5, 0.62), (0.07, 0.06, 0.09), 'dark', bevel=0.02)  # tow lugs
        vent((x0 + 0.95, s * hw * 0.45, top + 0.03), (0.5, hw * 0.3, 0.05), 'vent')
        cyl((x0 - 0.02, s * hw * 0.55, top - 0.42), (x0 - 0.22, s * hw * 0.55, top - 0.42), 0.09, 8, 'dark')  # exhausts
        box((x0 - 0.02, s * hw * 0.55, top - 0.7), (0.02, 0.14, 0.04), 'red')
    box((x0 + 0.95, 0, top + 0.05), (0.42, 0.07, 0.035), 'armor', bevel=0.015)
    box((x0 - 0.03, 0, 0.9), (0.03, hw * 0.35, 0.16), 'vent')
    box((x0 - 0.045, 0, 1.16), (0.02, hw * 0.42, 0.028), 'glow')          # reactor vent slot
    box((x0 - 0.03, 0, 1.16), (0.03, hw * 0.48, 0.06), 'dark', bevel=0.01)
    tow_cable(g0 + 0.25, g1 - 0.2, hw * 0.42, gz0 + 0.055, gz1 + 0.055)
    periscopes(g0 + 0.02, 0.0, gz0 + 0.05, 3, 0.22)
    for s in (1, -1):
        exhaust(x0 + 0.28, s * hw * 0.74, top - 0.02, s, h=0.46, r=0.085)
        headlamp(x1 - 0.2, s * hw * 0.6, nose + 0.33, s)
        prism([(x1 + 0.02, 0.56), (x1 + 0.22, 0.56), (x1 + 0.26, 0.66), (x1 + 0.16, 0.74), (x1 + 0.1, 0.66), (x1 + 0.02, 0.7)],
              s * hw * 0.5 - 0.03, s * hw * 0.5 + 0.03, 'steel', bevel=0.01)   # tow hook
        box((0.3, s * hw * 0.955, 1.12), (0.5, 0.012, 0.012), 'steel')       # hand rail
        box((x0 + 1.9, s * hw * 0.6, top + 0.02), (0.3, hw * 0.22, 0.025), 'olive', bevel=0.012)


def chassis(L=6.4, hw=1.22, top=1.42, pod=1.68, w=0.42, nwheels=5, nose=0.95, stowage=True, fittings=True):
    """Complete tracked chassis: hull, fittings, both track pods, sponsons and fender stowage."""
    tank_hull(L, hw, top, nose)
    if fittings:
        hull_fittings(L, hw, top, nose)
    for s in (1, -1):
        track_unit(-L / 2 - 0.15, L / 2 - 0.1, s * pod, w=w, side=s, nwheels=nwheels)
        box((0.0, s * (hw + 0.02), 1.1), (L / 2 - 0.5, pod - w - hw + 0.08, 0.2), 'dark')
        if stowage:
            fy = s * (pod - w * 0.32)
            stow((-L / 2 + 2.0, fy, 1.43), (0.45, w * 0.5, 0.1))
            # Shovel, pry bar and spare links on the fender.
            box((0.4, fy, 1.385), (0.6, 0.02, 0.02), 'olive')
            box((1.05, fy, 1.385), (0.14, 0.09, 0.012), 'steel')
            box((0.5, fy - s * 0.12, 1.385), (0.75, 0.014, 0.014), 'steel')
            for k in range(3):
                box((L / 2 - 2.9 + k * 0.2, fy, 1.42), (0.08, w * 0.45, 0.03), 'track')
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
    tube((x, y1 - side * w * 0.14, z), (x, y1 - side * w * 0.08, z), [(0, r * 0.4), (1, r * 0.4), (1, r * 0.28), (0, r * 0.28)], 10, 'steel')
    for kk in range(5):
        a = 2 * math.pi * kk / 5
        box((x + math.cos(a) * r * 0.5, y1 - side * w * 0.1, z + math.sin(a) * r * 0.5), (r * 0.045, 0.014, r * 0.045), 'steel')
    if glow:
        cyl((x, y1 - side * w * 0.12, z), (x, y1 - side * w * 0.06, z), r * 0.12, 8, 'glow')


def missile_box(c, s, nx=2, nz=2, tip='red', zone='armor', group=None):
    """Box launcher facing +X: hooded front with deep tubes and pointed warheads, exhaust ports at the back."""
    (x, y, z), (sx, sy, sz) = c, s
    box(c, s, zone, bevel=0.035)
    box((x + sx + 0.005, y, z), (0.01, sy * 0.92, sz * 0.9), 'dark')
    for dy, dz, hy, hz in ((0, sz, sy, 0.03), (0, -sz, sy, 0.03), (sy, 0, 0.03, sz), (-sy, 0, 0.03, sz)):   # blast hood
        box((x + sx + 0.07, y + dy * 0.98, z + dz * 0.98), (0.09, hy, hz), 'plate', bevel=0.012)
    r = min(sy / nx, sz / nz) * 0.72
    made = []
    for i in range(nx):
        for j in range(nz):
            py = y - sy + sy * 2 * (i + 0.5) / nx
            pz = z - sz + sz * 2 * (j + 0.5) / nz
            tube((x + sx - 0.02, py, pz), (x + sx + 0.05, py, pz), [(0, r * 1.14), (1, r * 1.14), (1, r * 0.92), (0.2, r * 0.9)], 6, 'plate')
            mm = F.mark()
            x0m = x + sx - (sx * 0.85 if group else 0.12)
            tube((x0m, py, pz), (x + sx + 0.1, py, pz), [(0, r * 0.74), (1 - 0.12 / (x + sx + 0.1 - x0m), r * 0.74), (1, r * 0.08)], 8, 'steel')
            cyl((x + sx - 0.035, py, pz), (x + sx - 0.005, py, pz), r * 0.78, 8, 'amber' if tip == 'red' else tip)
            if group:   # the whole missile is its own part so the game can launch it; a flame rides its tail
                tube((x0m, py, pz), (x0m - r * 5, py, pz), [(0, r * 0.7), (0.2, r * 0.9), (1, 0.01)], 6, 'flash')
                F.regroup(mm, f'{group}{i}{j}')
                made.append((f'{group}{i}{j}', (x + sx, py, pz)))
            # exhaust port at the back
            tube((x - sx - 0.05, py, pz), (x - sx + 0.02, py, pz), [(0, r * 0.95), (1, r * 0.95), (1, r * 0.7), (0.1, r * 0.66)], 8, 'heat')
            cyl((x - sx - 0.012, py, pz), (x - sx - 0.008, py, pz), r * 0.68, 8, 'dark')
    box((x, y, z + sz + 0.012), (sx * 0.8, sy * 0.12, 0.012), 'dark')
    for kk in (-0.6, 0.0, 0.6):   # strengthening ribs
        box((x + sx * kk, y, z), (0.04, sy + 0.025, sz + 0.025), 'plate', bevel=0.012)
    box((x - sx * 0.3, y, z + sz + 0.03), (sx * 0.18, sy * 0.5, 0.008), 'mark')
    return made


def beacon(x, y, z, zone='amber'):
    cyl((x, y, z), (x, y, z + 0.05), 0.09, 8, 'dark')
    tube((x, y, z + 0.05), (x, y, z + 0.2), [(0, 0.075), (0.7, 0.075), (1, 0.03)], 8, zone)


def plus(x, y, z, s=0.22, zone='glow'):
    """Repair cross lying flat on a top surface."""
    box((x, y, z), (s, s * 0.3, 0.01), zone)
    box((x, y, z), (s * 0.3, s, 0.01), zone)


def cupola(x, y, z, r=0.3, sides=8, mg=True):
    """Commander cupola: armoured ring with vision blocks, domed lid, handle and a pintle gun."""
    tube((x, y, z), (x, y, z + 0.17), [(0, r * 1.08), (0.25, r * 1.08), (0.3, r), (0.85, r), (1, r * 0.9)], sides, 'armor', sharp=30)
    for k in range(sides):
        a = 2 * math.pi * (k + 0.5) / sides
        b = box((r * 0.98, 0, 0.1), (0.02, r * 0.24, 0.035), 'glass')
        F.rot(b, 'Z', math.degrees(a))
        F.move(b, (x, y, z))
    tube((x, y, z + 0.17), (x, y, z + 0.24), [(0, r * 0.86), (0.5, r * 0.8), (1, r * 0.5)], sides, 'plate', sharp=30)
    box((x - r * 0.3, y, z + 0.25), (r * 0.2, 0.03, 0.02), 'steel')
    box((x - r * 0.95, y, z + 0.2), (0.05, r * 0.3, 0.03), 'dark')   # hinge
    if mg:
        cyl((x + r * 0.7, y + r * 0.7, z + 0.15), (x + r * 0.7, y + r * 0.7, z + 0.36), 0.03, 6, 'steel')
        box((x + r * 0.7, y + r * 0.7, z + 0.4), (0.16, 0.05, 0.05), 'dark', bevel=0.015)
        gun(x + r * 0.7 + 0.1, x + r * 0.7 + 0.85, y + r * 0.7, z + 0.4, 0.022)
        box((x + r * 0.7 - 0.02, y + r * 0.7 - 0.11, z + 0.36), (0.09, 0.05, 0.07), 'olive', bevel=0.01)


def basket(x0, x1, yh, z, h=0.3):
    """Open bustle basket of bars, loaded with rolled tarps, a crate and jerry cans."""
    for zz in (z, z + h):
        for sgn in (1, -1):
            box(((x0 + x1) / 2, sgn * yh, zz), ((x1 - x0) / 2, 0.018, 0.018), 'steel')
        box((x0, 0, zz), (0.018, yh, 0.018), 'steel')
    n = 5
    for k in range(n + 1):
        yy = -yh + 2 * yh * k / n
        box((x0, yy, z + h / 2), (0.014, 0.014, h / 2), 'steel')
    for sgn in (1, -1):
        box((x1 - 0.02, sgn * yh, z + h / 2), (0.014, 0.014, h / 2), 'steel')
    box(((x0 + x1) / 2, 0, z - 0.01), ((x1 - x0) / 2, yh, 0.012), 'dark')
    cyl((x0 + 0.12, -yh * 0.85, z + 0.12), (x0 + 0.12, yh * 0.2, z + 0.12), 0.1, 8, 'olive')
    cyl((x0 + 0.13, -yh * 0.7, z + 0.3), (x0 + 0.13, 0.0, z + 0.3), 0.085, 8, 'rubber')
    box((x0 + 0.16, yh * 0.6, z + 0.14), (0.11, yh * 0.3, 0.13), 'olive', bevel=0.02)
    for k in range(2):
        box((x1 - 0.14, -yh * 0.5 + k * yh * 0.5, z + 0.16), (0.07, yh * 0.18, 0.15), 'olive', bevel=0.025)
        box((x1 - 0.14, -yh * 0.5 + k * yh * 0.5, z + 0.33), (0.03, yh * 0.1, 0.02), 'dark')


def mantlet(x, z, yh, h, guns=(), r=0.12, length=0.9):
    """Layered gun mantlet: outer armour block, inner collar, recoil sleeves and exposed recoil cylinders."""
    box((x, 0, z), (0.2, yh, h), 'armor', bevel=0.06)
    box((x + 0.16, 0, z), (0.1, yh * 0.86, h * 0.8), 'plate', bevel=0.04)
    box((x - 0.05, 0, z + h + 0.01), (0.2, yh * 0.7, 0.02), 'rubber')    # dust cover on top
    for gy in guns:
        off = math.copysign(r * 1.9, gy) if gy else r * 1.9
        tube((x + 0.2, gy, z), (x + 0.2 + length, gy, z), [(0, r * 2.3), (0.7, r * 2.2), (0.72, r * 2.5), (0.9, r * 2.5), (1, r * 1.9)], 10, 'armor', sharp=30)
        for dz in (1, -1):
            cyl((x + 0.25, gy + off, z + dz * r * 1.9), (x + 0.2 + length * 1.25, gy + off, z + dz * r * 1.9), r * 0.34, 8, 'steel')
            cyl((x + 0.25, gy + off, z + dz * r * 1.9), (x + 0.2 + length * 0.6, gy + off, z + dz * r * 1.9), r * 0.55, 8, 'dark')
    # cable loom slung underneath
    sweep([(x - 0.1, -yh * 0.5, z - h - 0.02), (x + 0.3, -yh * 0.3, z - h - 0.1), (x + 0.6, 0.0, z - h * 0.6)],
          [(0.035, 0.035), (0.035, 0.035), (0.03, 0.03)], 'rubber', sides=6)


def exhaust(x, y, z, side=1, h=0.5, r=0.1):
    """Angled exhaust stack: heat-stained pipe with a perforated shield and a flapper cap."""
    tube((x, y, z), (x - 0.22, y, z + h), [(0, r * 1.3), (0.15, r * 1.3), (0.18, r), (0.9, r), (0.92, r * 1.15), (1, r * 1.15), (1, r * 0.8), (0.7, r * 0.75)], 10, 'heat', sharp=30)
    box((x - 0.06, y + side * r * 1.25, z + h * 0.45), (0.1, 0.015, h * 0.32), 'vent')
    box((x - 0.24, y, z + h + 0.03), (r * 1.1, r * 1.1, 0.012), 'steel')


def tow_cable(x0, x1, y, z0, z1, loops=3):
    """Steel tow cable stowed in neat long loops on a sloped plate, held by clamps, eyes at the ends."""
    def zat(x):
        return z0 + (z1 - z0) * (x - x0) / (x1 - x0) + 0.03
    xa, xb = x0 + 0.1, x1 - 0.1
    for k in range(loops):
        w = y * (1.0 - 0.24 * k)
        e = 0.12 * k
        n = 6
        pts = [(xa + e, -w + 0.1, zat(xa + e)), (xb - e - 0.1, -w + 0.02, zat(xb - e - 0.1))]
        pts += [(xb - e - 0.1 + 0.1 * math.sin(math.pi * i / n), -w * math.cos(math.pi * i / n), zat(xb - e)) for i in range(1, n)]
        pts += [(xb - e - 0.1, w - 0.02, zat(xb - e - 0.1)), (xa + e, w - 0.1, zat(xa + e))]
        sweep(pts, [(0.024, 0.024)] * len(pts), 'steel', sides=5)
    for s in (1, -1):
        tube((xa - 0.04, s * (y - 0.1), zat(xa) - 0.03), (xa - 0.04, s * (y - 0.1), zat(xa) + 0.02), [(0, 0.075), (1, 0.075), (1, 0.04), (0, 0.04)], 8, 'steel')
        xm = (xa + xb) / 2
        box((xm, s * y * 0.76, zat(xm) + 0.005), (0.05, y * 0.3, 0.03), 'plate', bevel=0.008)


def headlamp(x, y, z, side=1):
    """Guarded headlight cluster: one white-cyan lamp, one small orange marker, steel guard bars."""
    box((x - 0.05, y, z), (0.09, 0.17, 0.085), 'dark', bevel=0.02)
    cyl((x + 0.03, y - side * 0.06, z), (x + 0.05, y - side * 0.06, z), 0.06, 8, 'glow')
    cyl((x + 0.03, y + side * 0.09, z), (x + 0.05, y + side * 0.09, z), 0.035, 8, 'amber')
    for dz in (-0.05, 0.05):
        box((x + 0.07, y, z + dz), (0.012, 0.18, 0.01), 'steel')
    for dy in (-0.17, 0.17):
        box((x + 0.02, y + dy, z), (0.06, 0.01, 0.07), 'steel')


def periscopes(x, y, z, n=3, spread=0.2):
    for k in range(n):
        yy = y + (k - (n - 1) / 2) * spread
        box((x, yy, z + 0.035), (0.06, spread * 0.36, 0.04), 'armor', bevel=0.012)
        box((x + 0.06, yy, z + 0.045), (0.008, spread * 0.28, 0.022), 'glass')


def applique(x0, x1, y, z0, z1, side=1, n=4, zone='plate'):
    """Row of bolt-on armour blocks standing proud of a side wall, with gaps between."""
    L = (x1 - x0) / n
    a, b = sorted((y, y + side * 0.07))
    for k in range(n):
        xa = x0 + k * L + 0.03
        xb = x0 + (k + 1) * L - 0.03
        prism([(xa, z0 + 0.04), (xa + 0.05, z0), (xb - 0.05, z0), (xb, z0 + 0.04), (xb, z1 - 0.04), (xb - 0.05, z1), (xa + 0.05, z1), (xa, z1 - 0.04)],
              a, b, zone if k % 2 == 0 else 'armor', bevel=0.02)
        for bx in (xa + 0.09, xb - 0.09):
            for bz in (z0 + 0.07, z1 - 0.07):
                box((bx, y + side * 0.075, bz), (0.02, 0.008, 0.02), 'steel')


def ram(p0, p1, r=0.06, split=0.55):
    """Hydraulic ram between two points: dark sleeve, bright rod, end eyes."""
    m = tuple(p0[i] + (p1[i] - p0[i]) * split for i in range(3))
    cyl(p0, m, r * 1.5, 8, 'dark')
    cyl(m, p1, r * 0.8, 8, 'steel')
    for p in (p0, p1):
        box(p, (r * 1.6, r * 1.6, r * 1.6), 'dark', bevel=r * 0.4)


def outrigger(x, y, z, side=1, L=1.4, dirn=1):
    """Folded stabiliser leg lying along the hull: knuckle, box arm, ram, upright hazard foot with teeth."""
    cyl((x, y, z - 0.13), (x, y, z + 0.13), 0.16, 10, 'steel')
    box((x + dirn * L / 2, y, z), (L / 2, 0.09, 0.1), 'armor', bevel=0.03)
    box((x + dirn * L * 0.45, y, z + 0.105), (L * 0.3, 0.06, 0.012), 'hazard')
    ram((x + dirn * 0.2, y + side * 0.12, z + 0.03), (x + dirn * L * 0.82, y + side * 0.12, z + 0.03), 0.04)
    fx = x + dirn * (L + 0.03)
    box((fx, y, z + 0.14), (0.05, 0.3, 0.3), 'plate', bevel=0.02)
    box((fx + dirn * 0.055, y, z + 0.14), (0.008, 0.25, 0.25), 'hazard')
    for kk in (-1, 0, 1):
        box((fx, y + kk * 0.2, z + 0.47), (0.04, 0.05, 0.05), 'steel')


def radar_bar(x, y, z, w=0.6, post=0.3):
    """Rotating bar antenna on a short post (call inside its own group)."""
    cyl((x, y, z), (x, y, z + post), 0.045, 6, 'steel')
    box((x, y, z + post + 0.06), (0.07, w, 0.06), 'plate', bevel=0.02)
    box((x - 0.08, y, z + post + 0.06), (0.03, w * 0.8, 0.03), 'dark')
    box((x + 0.075, y, z + post + 0.06), (0.008, w * 0.85, 0.022), 'glow')
    cyl((x, y, z + post + 0.12), (x, y, z + post + 0.17), 0.06, 8, 'dark')


def id_marks(x, y, z, side=1, n=2, s=0.16):
    """Unit tally marks painted on a vertical side face."""
    for kk in range(n):
        box((x + kk * s * 0.9, y, z), (s * 0.28, 0.008, s), 'mark')


def ore_load(x0, x1, yh, z0, h, seed=3):
    """Heaped ore: faceted dark rocks with glowing crystal shards (call inside group 'Ore')."""
    import random
    rnd = random.Random(seed)
    n = int((x1 - x0) * yh * 9)
    for i in range(n):
        u, v = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        hump = max(0.0, 1 - 0.75 * (u * u + v * v))
        c = ((x0 + x1) / 2 + u * (x1 - x0) / 2 * 0.92, v * yh * 0.9, z0 + h * hump * rnd.uniform(0.75, 1.0))
        r = rnd.uniform(0.16, 0.3)
        o = orb(c, r, 'ore', seg=(5, 3), sq=(rnd.uniform(0.8, 1.4), rnd.uniform(0.8, 1.3), rnd.uniform(0.6, 1.0)))
        F.rot(o, 'Z', rnd.uniform(0, 360), about=c)
        F.rot(o, 'X', rnd.uniform(-40, 40), about=c)
        if i % 4 == 0:
            t = tube(c, (c[0] + rnd.uniform(-0.15, 0.15), c[1] + rnd.uniform(-0.15, 0.15), c[2] + r + rnd.uniform(0.12, 0.26)),
                     [(0, 0.07), (0.5, 0.055), (1, 0.008)], 5, 'glow')


# ---- aircraft pieces ----
def wing_panel(y0, y1, le0, te0, le1, te1, z0, z1, t0, t1, zone='armor', bevel=0.0):
    """Tapered wing slab between two span stations: thick diamond-ish aerofoil at y0, thin at y1."""
    def ring(y, le, te, z, t):
        c = le - te
        return [(le, y, z), (le - 0.2 * c, y, z + t * 0.5), (te + 0.38 * c, y, z + t * 0.42), (te, y, z),
                (te + 0.38 * c, y, z - t * 0.4), (le - 0.2 * c, y, z - t * 0.5)]
    return F.loft([ring(y0, le0, te0, z0, t0), ring(y1, le1, te1, z1, t1)], zone, bevel=bevel)


def nozzle(x, y, z, r, L=0.7, petals=8, fan=None):
    """Jet exhaust pointing -X: armoured shroud, hinged petal plates, glowing core, turbine wheel
    (in its own group when `fan` names one)."""
    tube((x + L * 0.5, y, z), (x - L * 0.22, y, z), [(0, r * 1.06), (0.15, r * 1.14), (0.8, r * 1.14), (1, r * 1.02), (1, r * 0.9), (0.1, r * 0.88)], 14, 'armor', sharp=40, bevel=0.012)
    tube((x + L * 0.1, y, z), (x - L * 0.2, y, z), [(0, r * 1.16), (1, r * 1.16), (1, r * 1.1), (0, r * 1.1)], 14, 'steel')
    for k in range(petals):
        hz = z + r * 0.9
        b = box((x - L * 0.52, y, hz), (L * 0.32, r * 0.74 * math.pi / petals, 0.018), 'heat', bevel=0.006)
        F.rot(b, 'Y', -13, about=(x - L * 0.2, y, hz))
        F.rot(b, 'X', 360.0 * k / petals, about=(0, y, z))
    cyl((x + L * 0.12, y, z), (x + L * 0.08, y, z), r * 0.86, 14, 'glow')
    def wheel_():
        cyl((x - L * 0.02, y, z), (x - L * 0.42, y, z), r * 0.24, 8, 'steel', r1=r * 0.06)
        for k in range(9):
            c = (x - L * 0.1, y, z + r * 0.52)
            b = box(c, (0.012, r * 0.1, r * 0.32), 'dark')
            F.rot(b, 'Z', 28, about=c)
            F.rot(b, 'X', 40.0 * k, about=(0, y, z))
    if fan:
        with F.group(fan):
            wheel_()
    else:
        wheel_()


def intake_fan(x, y, z, r, group=None, blades=11):
    """Front-facing turbofan face: lip ring, dark throat, spinner and pitched blades (own group if named)."""
    tube((x, y, z), (x - 0.34, y, z), [(0, r * 0.94), (0.25, r * 1.08), (1, r * 1.08), (1, r * 0.9), (0.2, r * 0.88)], 16, 'plate', sharp=40)
    cyl((x - 0.3, y, z), (x - 0.34, y, z), r * 0.9, 12, 'dark')
    tube((x - 0.02, y, z), (x - 0.05, y, z), [(0, r * 0.93), (1, r * 0.93), (1, r * 0.87), (0, r * 0.87)], 16, 'glow')
    def wheel_():
        tube((x + 0.12, y, z), (x - 0.28, y, z), [(0, 0.01), (0.3, r * 0.2), (1, r * 0.28)], 10, 'steel')
        for k in range(blades):
            c = (x - 0.2, y, z + r * 0.56)
            b = box(c, (0.014, r * 0.11, r * 0.31), 'steel')
            F.rot(b, 'Z', 32, about=c)
            F.rot(b, 'X', 360.0 * k / blades, about=(0, y, z))
    if group:
        with F.group(group):
            wheel_()
    else:
        wheel_()


def missile(x, y, z, L=1.3, r=0.065, rail=True):
    """Slim air-to-air missile hung from a launch rail (nose +X)."""
    tube((x - L / 2, y, z), (x + L / 2, y, z), [(0, r * 0.8), (0.04, r), (0.8, r), (0.92, r * 0.7), (1, r * 0.12)], 8, 'steel')
    cyl((x + L * 0.22, y, z), (x + L * 0.27, y, z), r * 1.04, 8, 'amber')
    cyl((x - L / 2 - 0.02, y, z), (x - L / 2, y, z), r * 0.6, 6, 'heat')
    for k in range(4):
        for fx, fl, fh in ((-L * 0.4, L * 0.1, r * 1.5), (L * 0.1, L * 0.06, r * 1.0)):
            b = box((x + fx, y, z + r + fh * 0.5), (fl, 0.008, fh * 0.5), 'dark')
            F.rot(b, 'X', 45 + 90 * k, about=(0, y, z))
    if rail:
        box((x - L * 0.05, y, z + r + 0.035), (L * 0.36, 0.03, 0.03), 'dark', bevel=0.008)


def bomb(x, y, z, L=1.3, r=0.16, band='amber'):
    """Finned free-fall bomb, nose +X."""
    tube((x - L / 2, y, z), (x + L / 2, y, z), [(0, r * 0.3), (0.2, r * 0.75), (0.45, r), (0.75, r), (0.92, r * 0.6), (1, r * 0.1)], 10, 'steel', sharp=30)
    cyl((x + L * 0.26, y, z), (x + L * 0.31, y, z), r * 0.93, 10, band)
    tube((x - L * 0.52, y, z), (x - L * 0.36, y, z), [(0, r * 0.98), (1, r * 0.98), (1, r * 0.9), (0, r * 0.9)], 10, 'dark')
    for k in range(4):
        b = box((x - L * 0.42, y, z + r * 0.6), (L * 0.09, 0.01, r * 0.42), 'dark')
        F.rot(b, 'X', 45 + 90 * k, about=(0, y, z))


def canted_fin(profile, y, z, lean, t=0.05, zone='armor', light=None):
    """Vertical fin from a side profile [(x, z)], leaned outward by `lean` degrees about its root."""
    m = F.mark()
    prism(profile, y - t, y + t, zone, bevel=0.015)
    x0 = min(p[0] for p in profile); x1 = max(p[0] for p in profile); zt = max(p[1] for p in profile)
    prism([(px * 0.55 + (x0 + x1) * 0.225, z + (pz - z) * 0.62 + 0.1) for px, pz in profile], y - t - 0.012, y + t + 0.012, 'plate', bevel=0.008)
    if light:
        xt = [p[0] for p in profile if p[1] == zt]
        box((sum(xt) / len(xt), y, zt + 0.02), (0.1, t * 0.7, 0.02), light)
    F.rot_all(m, 'X', -lean, about=(0, y, z))


# ---- firing ----
def flash(x, y, z, r, group, zone='flash'):
    """Muzzle flash pointing +X in its own group: a forward spike with a four-point star round it.
    The game shows it for an instant when the gun fires."""
    with F.group(group):
        tube((x, y, z), (x + r * 13, y, z), [(0, r * 0.9), (0.08, r * 1.7), (0.3, r * 1.1), (1, 0.01)], 8, zone)
        tube((x, y, z), (x + r * 6, y, z), [(0, r * 0.5), (0.1, r * 0.9), (1, 0.01)], 6, 'flashw')        # white-hot core
        for dy, dz in ((1, 0.25), (-1, 0.25), (0.25, 1), (0.25, -1), (-0.6, -0.7), (0.7, 0.7)):
            tube((x + r * 0.5, y, z), (x + r * 2.4, y + dy * r * 3.6, z + dz * r * 3.6), [(0, r * 0.6), (1, 0.01)], 4, zone)


def railgun(x0, x1, y, z, r=0.13, coil=True, muzzle=True, evac=False, group=None, flash_group=None):
    """Rail barrel; group= makes it its own part (it recoils when fired), flash_group= adds a muzzle flash."""
    if group:
        with F.group(group):
            _railgun(x0, x1, y, z, r, coil, muzzle, evac)
    else:
        _railgun(x0, x1, y, z, r, coil, muzzle, evac)
    if flash_group:
        flash(x1 + 0.14, y, z, r, flash_group)


def gun_pivots(specs, parent='Turret'):
    """Pivot entries for recoiling barrels: specs = [(suffix, breech point, muzzle point)]."""
    out = []
    for sfx, b, mz in specs:
        out += [('Barrel' + sfx, b, 'Barrel' + sfx + 'Pivot', parent), ('Flash' + sfx, mz, 'Flash' + sfx + 'Pivot', 'Barrel' + sfx)]
    return out
