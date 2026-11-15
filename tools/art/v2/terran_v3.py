"""Terran sci-fi language (v3): dart hulls, blade track pods, rail lances, telescoping cannon.
Sharp raked edges, neon cyan energy lines, orange markers; no present-day tank clutter."""
import forge as F
from forge import box, cyl, hull, prism, tube
import terran_kit as K


def blade_pod(x0, x1, y, side, w=0.42, nwheels=5, top=1.3, prow=1.2, fin=0.6, claws=()):
    """Track pod under a knife-edged shroud: pointed prow, forward-raked skirt slashes, swept tail fin."""
    s = side
    K.track_unit(x0, x1, y, w=w, side=s, nwheels=nwheels, skirt=False)
    yo = y + s * (w + 0.03)
    a, b = min(yo, yo + s * 0.1), max(yo, yo + s * 0.1)
    full = (min(y - s * w * 0.9, yo + s * 0.1), max(y - s * w * 0.9, yo + s * 0.1))
    L = x1 - x0
    # Prow blade: a long chisel that runs out ahead of the track.
    prism([(x1 - 1.0, 0.62), (x1 + prow * 0.55, 0.6), (x1 + prow, 0.74), (x1 - 0.1, top + 0.06), (x1 - 1.0, top + 0.06)],
          full[0], full[1], 'armor', bevel=0.03)
    box((x1 + prow * 0.2, yo + s * 0.105, 0.86), (prow * 0.42, 0.012, 0.02), 'glow')
    box((x1 + prow * 0.86, y, 0.75), (0.07, w * 0.5, 0.025), 'amber')
    # Top deck with a recessed energy channel.
    box(((x0 + x1) / 2 - 0.3, y, top + 0.03), (L / 2 - 0.75, w + 0.12, 0.045), 'armor', bevel=0.025)
    box(((x0 + x1) / 2 - 0.3, y, top + 0.08), (L / 2 - 1.2, w * 0.2, 0.012), 'dark')
    box(((x0 + x1) / 2 - 0.3, y, top + 0.092), (L / 2 - 1.3, w * 0.07, 0.008), 'glow')
    # Skirt: forward-raked slashes with knife gaps between them.
    n = 4
    seg = (L - 1.7) / n
    for i in range(n):
        p0 = x0 + 0.55 + seg * i
        p1 = p0 + seg - 0.1
        low = 0.66 if i % 2 else 0.78
        prism([(p0 + 0.42, low), (p1 + 0.42, low), (p1 - 0.05, top), (p0 - 0.05, top)], a, b, 'plate' if i % 2 else 'armor', bevel=0.022)
        box(((p0 + p1) / 2 + 0.1, b + 0.008 if s > 0 else a - 0.008, top - 0.16), (seg * 0.3, 0.01, 0.016), 'glow')
    # Swept tail fin.
    prism([(x0 - 0.1, 0.86), (x0 + 0.62, 0.86), (x0 + 0.9, top + 0.06), (x0 + 0.1, top + 0.1), (x0 - 0.75, top + fin)],
          a, b, 'armor', bevel=0.022)
    prism([(x0 - 0.1, 0.86), (x0 + 0.5, 0.86), (x0 + 0.5, top), (x0, top)], full[0], full[1], 'dark')
    box((x0 - 0.35, (a + b) / 2 + s * 0.06, top + fin * 0.45), (0.2, 0.01, 0.025), 'amber')
    for cx in claws:   # ground anchor claws, folded against the pod
        prism([(cx - 0.34, top - 0.1), (cx + 0.3, top - 0.1), (cx + 0.2, 0.62), (cx + 0.02, 0.2), (cx - 0.16, 0.62)], b if s > 0 else a - 0.09, (b + 0.09) if s > 0 else a,
              'steel', bevel=0.02)
        box((cx, (b + 0.1) if s > 0 else (a - 0.1), top - 0.3), (0.16, 0.012, 0.03), 'hazard')


def dart_hull(L=6.4, hw=1.22, top=1.42, nose=0.9, zone='hull'):
    """Faceted dart: hard chine, raised reactor hump at the rear, long chisel prow."""
    x0, x1 = -L / 2, L / 2
    hull([
        (x0 - 0.25, [(0, 0.7), (hw * 0.6, 0.7), (hw * 0.72, 1.0), (hw * 0.42, top), (0, top)]),
        (x0 + 0.45, [(0, 0.5), (hw * 0.86, 0.5), (hw, 1.0), (hw * 0.6, top + 0.16), (0, top + 0.16)]),
        (x0 + 1.5, [(0, 0.46), (hw * 0.86, 0.46), (hw, 1.0), (hw * 0.62, top), (0, top)]),
        (x1 - 2.5, [(0, 0.46), (hw * 0.86, 0.46), (hw, 1.0), (hw * 0.62, top), (0, top)]),
        (x1 - 0.8, [(0, 0.5), (hw * 0.66, 0.5), (hw * 0.8, 0.9), (hw * 0.36, 1.1), (0, 1.13)]),
        (x1 + nose, [(0, 0.66), (hw * 0.1, 0.66), (hw * 0.14, 0.74), (hw * 0.06, 0.8), (0, 0.81)]),
    ], zone, bevel=0.035)
    # Centre spine ridge running down the glacis to the prow tip, with a visor slit either side.
    prism([(x1 - 2.6, top - 0.02), (x1 + nose - 0.3, 0.8), (x1 - 0.9, 1.26), (x1 - 2.6, top + 0.12)], -0.09, 0.09, 'armor', bevel=0.02)
    for s in (1, -1):
        v = box((0, 0, 0), (0.42, 0.11, 0.012), 'glass')
        F.rot(v, 'Y', 10.5)
        F.rot(v, 'Z', s * 9)
        F.move(v, (x1 - 1.75, s * hw * 0.3, top - 0.085))
        # Chine energy line and raked side strakes.
        box((-0.2, s * hw * 0.995, 1.0), (L / 2 - 1.9, 0.014, 0.018), 'glow')
        for k in range(3):
            px = x0 + 1.7 + k * 0.5
            p = prism([(px, 1.05), (px + 0.3, 1.05), (px + 0.12, top - 0.03), (px - 0.18, top - 0.03)], 0, 0.03, 'dark')
            F.rot(p, 'X', -41 * 1, about=(0, 0, 1.05))
            F.move(p, (0, hw * 0.985, 0))
            if s < 0:
                F.mirror(p)
        box((x1 + nose - 0.55, s * hw * 0.16, 0.8), (0.12, 0.02, 0.014), 'amber')
        box((x1 - 1.15, s * hw * 0.68, 0.98), (0.2, 0.015, 0.03), 'glow')   # running lights
    # Reactor block: cooling blades with the core glowing between them.
    box((x0 + 0.5, 0, top + 0.12), (0.5, hw * 0.44, 0.07), 'dark')
    box((x0 + 0.5, 0, top + 0.15), (0.46, hw * 0.4, 0.05), 'coil')
    for k in range(6):
        fy = (k - 2.5) * hw * 0.15
        prism([(x0 - 0.05, top + 0.05), (x0 + 1.05, top + 0.05), (x0 + 0.8, top + 0.3), (x0 - 0.3, top + 0.36)], fy - 0.022, fy + 0.022, 'plate', bevel=0.008)
    box((x0 - 0.26, 0, 1.08), (0.02, hw * 0.34, 0.1), 'vent')
    box((x0 - 0.275, 0, 1.28), (0.02, hw * 0.3, 0.022), 'glow')
    for s in (1, -1):
        box((x0 - 0.27, s * hw * 0.5, 0.86), (0.02, 0.1, 0.03), 'amber')


def scifi_chassis(L=6.4, hw=1.22, top=1.42, pod=1.68, w=0.42, nwheels=5, nose=0.9, prow=1.2, fin=0.6, claws=()):
    dart_hull(L, hw, top, nose)
    for s in (1, -1):
        blade_pod(-L / 2 - 0.15, L / 2 - 0.1, s * pod, s, w=w, nwheels=nwheels, prow=prow, fin=fin, claws=claws)
        box((-0.1, s * (hw + 0.02), 1.08), (L / 2 - 0.9, pod - w - hw + 0.1, 0.17), 'dark')
    return top


def rail_lance(x0, x1, y, z, r=0.12, group=None, flash_group=None):
    """Open rail accelerator: glowing core held between an upper and a lower blade that end in points."""
    def build():
        box((x0 + 0.35, y, z), (0.4, r * 1.9, r * 2.3), 'armor', bevel=0.03)
        cyl((x0 + 0.6, y, z), (x1 - 0.25, y, z), r * 0.62, 8, 'coil')
        for sg in (1, -1):
            prism([(x0 + 0.5, z + sg * r * 0.95), (x1 + 0.55, z + sg * r * 0.95), (x1 - 0.5, z + sg * r * 1.75), (x0 + 0.5, z + sg * r * 2.5)]
                  if sg > 0 else
                  [(x0 + 0.5, z - r * 2.5), (x1 - 0.5, z - r * 1.75), (x1 + 0.55, z - r * 0.95), (x0 + 0.5, z - r * 0.95)],
                  y - r * 0.75, y + r * 0.75, 'barrel', bevel=0.012)
        n = 4
        for k in range(n):
            px = x0 + 1.1 + (x1 - x0 - 1.7) * k / (n - 1)
            hgt = r * (2.6 - 0.8 * k / (n - 1))
            box((px, y, z), (0.05, r * 1.0, hgt), 'dark', bevel=0.01)
        box((x1 - 0.1, y, z), (0.03, r * 0.5, r * 0.8), 'glow')
    if group:
        with F.group(group):
            build()
    else:
        build()
    if flash_group:
        K.flash(x1 + 0.5, y, z, r, flash_group)


def arrow_turret(x0, x1, w, tz, h, zone='armor'):
    """Low arrowhead turret: wide faceted shoulders narrowing to a needle nose, twin swept sensor blades."""
    L = x1 - x0
    hull([
        (x0 - 0.45, [(0, tz + 0.3), (w * 0.45, tz + 0.3), (w * 0.5, tz + h * 0.52), (w * 0.26, tz + h * 0.72), (0, tz + h * 0.72)]),
        (x0 + 0.35, [(0, tz + 0.06), (w, tz + 0.06), (w * 1.1, tz + h * 0.4), (w * 0.5, tz + h), (0, tz + h)]),
        (x0 + L * 0.6, [(0, tz + 0.06), (w * 0.78, tz + 0.06), (w * 0.85, tz + h * 0.38), (w * 0.36, tz + h * 0.84), (0, tz + h * 0.87)]),
        (x1 + 0.6, [(0, tz + 0.12), (w * 0.08, tz + 0.12), (w * 0.1, tz + h * 0.28), (w * 0.04, tz + h * 0.38), (0, tz + h * 0.4)]),
    ], zone, bevel=0.035)
    # Roof spine with an energy slot, visor band across the brow.
    prism([(x0 + 0.1, tz + h - 0.02), (x0 + L * 0.62, tz + h * 0.86), (x0 + L * 0.5, tz + h + 0.1), (x0 + 0.2, tz + h + 0.14)], -0.16, 0.16, 'plate', bevel=0.02)
    box((x0 + L * 0.3, 0, tz + h + 0.125), (L * 0.14, 0.035, 0.012), 'glow')
    for s in (1, -1):
        v = box((0, 0, 0), (0.3, 0.012, 0.045), 'glass')
        F.rot(v, 'Z', -s * 17)
        F.move(v, (x0 + L * 0.78, s * w * 0.6, tz + h * 0.42))
        box((x0 + L * 0.3, s * w * 1.07, tz + h * 0.4), (L * 0.2, 0.012, 0.018), 'glow')
        # Swept sensor blade leaning out from each shoulder.
        p = prism([(x0 + 0.1, tz + h * 0.7), (x0 + 0.95, tz + h * 0.7), (x0 + 0.3, tz + h + 0.5), (x0 - 0.7, tz + h + 0.95)], -0.025, 0.025, 'plate', bevel=0.01)
        F.rot(p, 'X', -24, about=(0, 0, tz + h * 0.7))
        F.move(p, (0, w * 0.72, 0))
        if s < 0:
            F.mirror(p)
        box((x0 - 0.45, s * w * 0.3, tz + h * 0.5), (0.02, 0.07, 0.03), 'amber')
    box((x0 - 0.46, 0, tz + h * 0.5), (0.02, w * 0.16, 0.05), 'coil')


def tele_cannon(x0, x1, z, r=0.5, n=4, flash_group='Flash'):
    """Telescoping rail cannon along +X from x0 to x1: n nested box sleeves (groups Barrel1..n, widest first)
    that slam into each other when it fires, a jaw emitter at the muzzle and a recoil piston out the back.
    Returns the travel of one sleeve relative to the next."""
    seg = (x1 - x0) / n
    step = seg * 0.8
    for k in range(n):
        m = F.mark()
        rr = r * (1 - 0.17 * k)
        a, b = x0 + seg * k - (0.35 if k else 0.0), x0 + seg * (k + 1)
        box(((a + b) / 2, 0, z), ((b - a) / 2, rr, rr * 0.82), 'armor', bevel=0.035)
        box(((a + b) / 2, 0, z), ((b - a) / 2 - 0.2, rr + 0.012, rr * 0.2), 'coil')           # side energy windows
        box(((a + b) / 2, 0, z + rr * 0.84), ((b - a) / 2 - 0.12, rr * 0.3, 0.03), 'dark')    # top rail
        box(((a + b) / 2, 0, z - rr * 0.84), ((b - a) / 2 - 0.12, rr * 0.3, 0.03), 'dark')
        box((b - 0.09, 0, z), (0.09, rr + 0.07, rr * 0.82 + 0.07), 'plate', bevel=0.03)       # front collar
        box((b - 0.2, 0, z), (0.02, rr + 0.075, rr * 0.82 + 0.075), 'glow')
        if k == 0:   # recoil piston, hidden in the housing until the gun fires
            cyl((x0 - 1.75, 0, z), (x0 + 0.1, 0, z), r * 0.5, 8, 'steel')
            cyl((x0 - 1.8, 0, z), (x0 - 1.75, 0, z), r * 0.56, 8, 'heat')
            for q in range(3):
                cyl((x0 - 1.5 + q * 0.4, 0, z), (x0 - 1.44 + q * 0.4, 0, z), r * 0.53, 8, 'glow')
        if k == n - 1:   # jaw emitter: upper and lower fangs round a bright core
            for sg in (1, -1):
                pf = [(b - 0.5, z + sg * rr * 0.5), (b + 1.25, z + sg * rr * 0.42), (b + 0.5, z + sg * rr * 1.6), (b - 0.5, z + sg * rr * 1.75)]
                prism(pf if sg > 0 else pf[::-1], -rr * 0.85, rr * 0.85, 'armor', bevel=0.03)
                box((b + 0.2, 0, z + sg * rr * 0.44), (0.5, rr * 0.5, 0.015), 'glow')
            for sy in (1, -1):
                prism([(b - 0.45, z - rr * 0.6), (b + 0.25, z - rr * 0.25), (b + 0.25, z + rr * 0.25), (b - 0.45, z + rr * 0.6)],
                      min(sy * rr * 0.85, sy * (rr * 0.85 + 0.06)), max(sy * rr * 0.85, sy * (rr * 0.85 + 0.06)), 'plate', bevel=0.015)
            cyl((b - 0.1, 0, z), (b + 0.3, 0, z), rr * 0.3, 8, 'glow')
        F.regroup(m, f'Barrel{k + 1}')
    K.flash(x1 + 1.3, 0, z, r * 0.6, flash_group)
    return step
