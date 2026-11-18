"""Procedural sound library for the unit promo clips.

    /home/user/artenv/venv/bin/python tools/promos/audio/sfx_gen.py            # bake everything
    /home/user/artenv/venv/bin/python tools/promos/audio/sfx_gen.py boom_big   # bake some

Writes /mnt/project-files/promos/sfx/<name>_<n>.wav (48 kHz, 16-bit stereo) plus manifest.json.
All sounds are synthesised here (numpy/scipy): no recordings, no licences needed (we own them).
Each generator gets its own seeded RNG, so a re-bake is deterministic.

Design notes (what makes these read as 'trailer' rather than 'beeps'): every sound is layered
(transient + body + tail), noise is always shaped/filtered and amplitude-modulated, low end comes
from pitch-dropping sines that are softly saturated (harmonics make subs audible on phones),
tails get darker as they decay, and big hits get distant valley slapback.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsp import (SR, bp, brown, conv, env_ad, env_exp, fade, glide, hp, impulses, loopify,  # noqa: E402
                 lp, modal, norm, osc, pink, reverb_ir, sat, secs, smooth_random,
                 stereoize, sweep_lp, tv_bandpass, white)

OUT = os.environ.get('PROMO_SFX', '/mnt/project-files/promos/sfx')

LIB = {}


def sound(name, variants=3, loop=False, desc=''):
    def deco(fn):
        LIB[name] = dict(fn=fn, variants=variants, loop=loop, desc=desc)
        return fn
    return deco


def pad(x, dur):
    n = secs(dur)
    if len(x) >= n:
        return x[:n]
    if x.ndim == 2:
        return np.vstack([x, np.zeros((n - len(x), 2))])
    return np.concatenate([x, np.zeros(n - len(x))])


def mix(*parts):
    n = max(len(p) for p in parts)
    st = any(p.ndim == 2 for p in parts)
    out = np.zeros((n, 2) if st else n)
    for p in parts:
        if st and p.ndim == 1:
            p = np.stack([p, p], axis=1)
        out[:len(p)] += p
    return out


def at(x, t, total):
    """Place x at time t inside a buffer of `total` seconds."""
    n = secs(total)
    y = np.zeros(n) if x.ndim == 1 else np.zeros((n, 2))
    i = secs(t)
    m = min(len(x), n - i)
    if m > 0:
        y[i:i + m] = x[:m]
    return y


def st(x, rng, width=0.6):
    return stereoize(x, rng, width) if x.ndim == 1 else x


def room(x, rng, wet=0.18, dur=1.4, dark=(4500, 700)):
    """Light synthetic reverb (stereo)."""
    ir = reverb_ir(dur, rng, damp_hz=dark)
    xs = st(x, rng, 0.3)
    w = np.stack([conv(xs[:, c], ir[:, c]) for c in range(2)], axis=1)
    out = np.zeros_like(w)
    out[:len(xs)] = xs
    return out * (1 - wet * 0.5) + w * wet


# =================================================================== building blocks
def sub_thump(rng, f0=75, f1=28, dur=1.2, tau=0.12, decay=0.55, drive=2.0):
    n = secs(dur)
    f = glide(f0, f1, n, tau)
    s = osc(f, shape='sine') * env_ad(n, 0.004, decay, 3.5)
    return sat(s, drive)


def crack(rng, dur=0.08, lo=900, hi=9000, decay=0.018):
    n = secs(dur)
    x = white(n, rng)
    x = bp(x, lo, hi, 2) * env_ad(n, 0.0005, decay, 5)
    return sat(x * 1.6, 2.5)


def fireball_roar(rng, dur=2.2, f_start=4000, f_end=250, decay=0.9, grit=0.6):
    """Rolling noise body: pink noise, sweeping lowpass, lumpy amplitude."""
    n = secs(dur)
    x = pink(n, rng)
    lumps = 1 + grit * (smooth_random(n, rng, 28, -1, 1))
    x = sweep_lp(x * lumps, f_start, f_end)
    return x * env_ad(n, 0.006, decay, 3.0)


def rumble(rng, dur=3.0, cutoff=160, decay=1.4, attack=0.05):
    n = secs(dur)
    x = lp(brown(n, rng), cutoff, 2)
    x *= 0.7 + 0.6 * smooth_random(n, rng, 6, 0, 1)
    return x * env_ad(n, attack, decay, 2.6)


def metal_hit(rng, f0=None, dur=0.5, bright=0.5, damp=0.08, n_modes=10, noise=0.5):
    """Noise-excited struck metal: many inharmonic modes that die faster the higher they are,
    excited by a short filtered noise burst (not a sine 'ping'), plus the click of the contact.
    bright 0..1 = hardness of the strike; damp = decay time of the lowest mode (s)."""
    n = secs(dur)
    f0 = f0 or rng.uniform(250, 900)
    t = np.arange(n) / SR
    # plate/shell-like mode spread: ratios cluster irregularly (no clean harmonic series)
    ratios = np.sort(np.concatenate([[1.0], rng.uniform(1.3, 2.6, 3), rng.uniform(2.6, 6.5, n_modes - 4)]))
    ir = np.zeros(n)
    for k, r in enumerate(ratios):
        f = f0 * r
        if f > SR / 2.4:
            continue
        tau = damp / (1 + 0.9 * k) * rng.uniform(0.6, 1.4)
        a = rng.uniform(0.4, 1.0) / (1 + 0.35 * k) * (1 + bright * k * 0.15)
        # slight beating: each mode is a close pair (real objects are never perfectly symmetric)
        d = rng.uniform(0.5, 4.0)
        ir += a * (np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) + 0.6 * np.sin(2 * np.pi * (f + d) * t)) * np.exp(-t / tau)
    exc_n = secs(rng.uniform(0.001, 0.004))
    exc = rng.standard_normal(exc_n) * np.hanning(exc_n)
    exc = lp(exc, 2500 + 9000 * bright, 2)
    ring = conv(exc, ir)[:n]
    ring /= (np.max(np.abs(ring)) + 1e-9)
    click = hp(rng.standard_normal(secs(0.012)), 1500 + 3000 * bright, 2) * env_exp(secs(0.012), 0.0018)
    rattle = bp(rng.standard_normal(n), f0 * 1.5, min(f0 * 8, 15000), 1) * env_exp(n, damp * 0.4)
    return mix(ring, click * noise * 1.2, rattle * noise * 0.35)


def grain_debris(rng, dur=2.5, t0=0.2, n_grains=90, rock=1.0, metal=0.3, chunks=4, spread=0.7):
    """Granular debris rain: each grain is synthesised on its own (rock tick, pebble, metal bit,
    heavy chunk thud) with its own pitch, length, level and distance (darker when far), with a
    density that peaks as things come back down and thins out."""
    n = secs(dur)
    out = np.zeros(n)
    for _ in range(n_grains):
        # most debris lands 0.3-1.2 s after the blast, a long thin trickle after
        ti = t0 + abs(rng.normal(0.45, 0.35)) * spread * dur / 1.6 + (rng.exponential(0.4) if rng.random() < 0.3 else 0)
        if ti >= dur - 0.05:
            continue
        far = rng.uniform(0, 1)
        g = rng.uniform(0.15, 1.0) ** 1.6 * (1 - 0.6 * far)
        kind = rng.random()
        if kind < metal * 0.35:
            x = metal_hit(rng, rng.uniform(700, 3500), 0.25, rng.uniform(0.4, 1.0), rng.uniform(0.02, 0.07), 8, 0.6) * 0.5
        else:
            L = secs(rng.uniform(0.003, 0.025))
            x = rng.standard_normal(L) * env_exp(L, L / SR / 4)
            fc = rng.uniform(500, 5000)
            x = bp(x, fc * 0.5, min(fc * 2, 20000), 1) * rock
        x = lp(x, 14000 - 10000 * far, 1) if len(x) > 32 else x
        out += at(x * g, ti, dur)
    for _ in range(chunks):  # a few big pieces thudding into the ground
        ti = t0 + rng.uniform(0.35, 1.3) * spread
        if ti >= dur - 0.2:
            continue
        L = secs(0.18)
        th = np.sin(2 * np.pi * rng.uniform(55, 110) * np.arange(L) / SR) * env_exp(L, 0.04)
        th += lp(rng.standard_normal(L), 900, 2) * env_exp(L, 0.02) * 0.8
        out += at(th * rng.uniform(0.3, 0.8), ti, dur)
    return out


def outdoor(x, rng, size=1.0, dur_extra=1.6):
    """Outdoor acoustics for a loud event: a ground reflection, a handful of terrain echoes
    (each later one quieter, darker and more smeared by distance and air absorption), and a
    low 'rolling' tail like distant thunder."""
    n = len(x)
    extra = secs(dur_extra * size)
    y = np.zeros(n + extra)
    y[:n] += x
    d = secs(rng.uniform(0.004, 0.012))  # ground bounce
    y[d:d + n] += lp(x, 6000, 1) * 0.35
    nt = int(4 + 3 * size)
    for k in range(nt):
        delay = rng.uniform(0.09, 0.35) + k * rng.uniform(0.08, 0.22) * size
        i = secs(delay)
        if i >= len(y) - 10:
            continue
        g = 0.3 * np.exp(-delay / (0.55 * size)) * rng.uniform(0.6, 1.2)
        cut = 3500 / (1 + delay * 3)
        smear_n = secs(rng.uniform(0.02, 0.08) * (1 + delay))
        smear = rng.standard_normal(smear_n) * np.hanning(smear_n)
        smear /= np.sqrt(np.sum(smear ** 2)) + 1e-9
        e = conv(lp(x, cut, 2), smear)
        m = min(len(e), len(y) - i)
        y[i:i + m] += e[:m] * g
    # rolling low tail
    roll_n = len(y)
    rl = lp(rng.standard_normal(roll_n), 120, 2)
    env = np.interp(np.arange(roll_n), [0, secs(0.15), secs(0.5 * size), roll_n], [0, 1, 0.7, 0])
    lumpy = 0.6 + 0.4 * smooth_random(roll_n, rng, 3, 0, 1)
    pk = np.max(np.abs(x)) + 1e-9
    y += rl / (np.max(np.abs(rl)) + 1e-9) * env * lumpy * pk * 0.25 * size
    return y


def debris_patter(rng, dur=2.5, t0=0.25, rate0=60, rate1=4, metal=0.5):
    """Back-compat wrapper: granular debris with a density roughly matching rate0."""
    return grain_debris(rng, dur, t0, n_grains=int(rate0 * 1.4), metal=metal, chunks=int(2 + 3 * metal))


def electric_crackle(rng, dur, rate=900, color=(1500, 9000), buzz_hz=None, buzz=0.0, amp_pow=3.2):
    """Granular electric crackle (many tiny sparks) + optional mains-like arc buzz."""
    n = secs(dur)
    r = rate * (0.5 + smooth_random(n, rng, 18, 0, 1.2))
    imp = impulses(n, rng, r, amp_pow)
    # each spark is a tiny damped resonance -> 'sizzle' rather than white clicks
    k = np.exp(-np.arange(secs(0.0015)) / SR / 0.0003)
    sp = conv(imp, k)[:n]
    y = bp(sp, *color, 2) * 3.0
    if buzz and buzz_hz:
        f = buzz_hz * (1 + 0.04 * smooth_random(n, rng, 30, -1, 1))
        b = osc(f, shape='saw') + 0.4 * osc(f * 2.01, shape='square')
        b = sat(b * (0.6 + 0.8 * smooth_random(n, rng, 40, 0, 1)), 3)
        y += buzz * bp(b, 80, 4000, 1)
    return y


def gold_shimmer(rng, dur, base=None, decay=0.5, trem=23):
    """The 'gold' in Arcadian lightning: bright inharmonic bell partials with fast flutter."""
    n = secs(dur)
    base = base or rng.uniform(1700, 2100)
    ratios = [1.0, 1.5, 2.24, 2.98, 4.1]
    y = np.zeros(n)
    t = np.arange(n) / SR
    for i, r in enumerate(ratios):
        f = base * r * (1 + 0.003 * np.sin(2 * np.pi * rng.uniform(4, 7) * t))
        y += np.sin(2 * np.pi * np.cumsum(f) / SR + rng.uniform(0, 6)) / (i + 1.2)
    fl = 0.55 + 0.45 * np.sin(2 * np.pi * trem * t + rng.uniform(0, 6)) * smooth_random(n, rng, 15, 0.4, 1)
    return y * fl * env_ad(n, 0.004, decay, 3.5)


def servo_tone(rng, n, speed, base=420, gear=0.4):
    """Electric actuator: the motor is noise-band-limited around its commutation harmonics (a
    rough, breathy whine, not a pure saw), the gearbox is a train of tiny metallic tooth ticks,
    plus friction rasp; pitch wobbles with load."""
    jitter = 1 + 0.03 * smooth_random(n, rng, 9, -1, 1)
    f = base * (0.4 + 0.75 * speed) * jitter
    motor = np.zeros(n)
    for k, a in ((1, 1.0), (2, 0.5), (3, 0.35), (5, 0.2)):
        car = np.sin(2 * np.pi * np.cumsum(f * k) / SR + rng.uniform(0, 6))
        nb = lp(rng.standard_normal(n), 180 + 120 * k, 2)        # noise band around each harmonic = rough tone
        nb /= np.std(nb) + 1e-9
        motor += a * car * (0.15 + 0.85 * np.abs(nb))
    motor = bp(motor, 120, 3500, 2)
    # gear mesh ticks at the tooth rate (motor / reduction), each a tiny metal tick
    tooth = f / rng.uniform(3.5, 6.0)
    ph = np.cumsum(tooth) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
    # worn gears: teeth never land on an exact grid (that would ring as a pitch), and each tooth
    # pair sounds a bit different
    gap = np.diff(np.concatenate([[0], idx]))
    idx = np.clip(idx + (rng.uniform(-0.3, 0.3, len(idx)) * gap).astype(int), 0, n - 1)
    mesh = np.zeros(n)
    irs = [metal_hit(rng, rng.uniform(1500, 3800), 0.03, 0.8, 0.005, 6, 0.4) for _ in range(4)]
    for k in range(4):
        tk = np.zeros(n)
        sel = idx[k::4]
        tk[sel] = rng.uniform(0.2, 1.0, len(sel))
        mesh += conv(tk, irs[k])[:n]
    mesh *= 0.25
    rasp = bp(rng.standard_normal(n), 900, 5000, 2) * (0.3 + 0.7 * smooth_random(n, rng, 25, 0, 1))
    y = motor * 0.35 + gear * (mesh * 1.2 + rasp * 0.3)
    return y * np.clip(speed * 1.4, 0, 1)


# =================================================================== explosions & impacts
@sound('boom_big', 5, desc='large explosion: crack + pitch-dropping sub + rolling fireball + debris tail + valley echo')
def boom_big(rng):
    D = 4.5
    sub = sub_thump(rng, rng.uniform(68, 82), rng.uniform(33, 38), 2.0, 0.14, 0.7, 2.6)
    n2 = secs(2.0)
    lowmid = bp(pink(n2, rng), 70, 260, 2) * env_ad(n2, 0.004, 0.55, 3) * 2.2
    cr = crack(rng, 0.12, 700, 10000, 0.03)
    body = fireball_roar(rng, 2.6, rng.uniform(5000, 7000), 180, 0.75, 0.7)
    low = lp(fireball_roar(rng, 2.6, 900, 90, 1.0, 0.5), 300)
    rum = rumble(rng, 4.2, 120, 1.6, 0.08)
    deb = grain_debris(rng, 3.4, 0.3, 140, rock=1.0, metal=0.6, chunks=7, spread=1.0)
    x = mix(sub * 0.7, cr * 0.8, body * 1.0, low * 0.6, lowmid * 0.9, rum * 0.45)
    x = sat(x * 1.3, 1.6)
    x = outdoor(x, rng, 1.3, 1.4)          # terrain echoes + rolling thunder tail
    x = mix(x, deb * 0.55)                 # debris lands after, dry-ish and close
    x = pad(x, D)
    y = room(x, rng, 0.16, 1.6, (3500, 500))
    return fade(pad(y, D), 0.0005, 0.3)


@sound('boom_med', 5, desc='medium explosion')
def boom_med(rng):
    D = 3.2
    sub = sub_thump(rng, rng.uniform(80, 100), rng.uniform(38, 44), 1.4, 0.1, 0.45, 2.4)
    n2 = secs(1.4)
    lowmid = bp(pink(n2, rng), 80, 300, 2) * env_ad(n2, 0.003, 0.35, 3) * 2.2
    cr = crack(rng, 0.1, 900, 11000, 0.022)
    body = fireball_roar(rng, 1.8, rng.uniform(5500, 8000), 220, 0.5, 0.6)
    rum = rumble(rng, 2.8, 150, 0.9, 0.05)
    deb = grain_debris(rng, 2.6, 0.2, 90, rock=1.0, metal=0.4, chunks=4, spread=0.8)
    x = mix(sub * 0.7, cr * 0.8, body * 1.0, lowmid * 0.8, rum * 0.35)
    x = sat(x * 1.2, 1.5)
    x = mix(outdoor(x, rng, 1.0, 1.1), deb * 0.5)
    y = room(pad(x, D), rng, 0.16, 1.4)
    return fade(pad(y, D), 0.0005, 0.25)


@sound('boom_small', 5, desc='small blast / shell landing')
def boom_small(rng):
    D = 2.0
    sub = sub_thump(rng, rng.uniform(95, 120), rng.uniform(40, 50), 0.8, 0.07, 0.25, 1.8)
    cr = crack(rng, 0.08, 1000, 12000, 0.015)
    body = fireball_roar(rng, 1.0, 7000, 300, 0.28, 0.5)
    dirt = grain_debris(rng, 1.6, 0.06, 60, rock=1.0, metal=0.1, chunks=1, spread=0.5)
    x = mix(sub * 0.7, cr * 0.8, body * 1.0)
    x = sat(x * 1.2, 1.4)
    x = mix(outdoor(x, rng, 0.6, 0.6), dirt * 0.55)
    y = room(pad(x, D), rng, 0.15, 1.1)
    return fade(pad(y, D), 0.0005, 0.2)


@sound('sub_boom', 4, desc='camera-shake low boom (felt more than heard)')
def sub_boom(rng):
    D = 2.2
    s = sub_thump(rng, rng.uniform(55, 65), rng.uniform(22, 27), 2.0, 0.2, 0.8, 2.5)
    r = rumble(rng, 2.2, 90, 0.9, 0.02)
    x = mix(s, r * 0.5)
    x = lp(x, 400)
    return fade(st(pad(x, D), rng, 0.2), 0.001, 0.3)


@sound('debris_metal', 5, desc='destroyed vehicle: metal crunch + rain of parts, each part its own metal/rock grain')
def debris_metal(rng):
    D = 2.8
    n = secs(D)
    crunch = np.zeros(secs(0.5))
    for _ in range(int(rng.integers(5, 9))):  # the hull tearing: a quick cluster of heavy hits
        h = metal_hit(rng, rng.uniform(150, 600), 0.45, rng.uniform(0.3, 0.8), rng.uniform(0.05, 0.12), 12, 0.9)
        crunch += at(h * rng.uniform(0.3, 1.0), rng.uniform(0, 0.12), 0.5)
    crunch += bp(white(len(crunch), rng), 300, 4000, 2) * env_ad(len(crunch), 0.002, 0.1, 4) * 0.6
    rain = grain_debris(rng, D, 0.25, 70, rock=0.6, metal=1.0, chunks=4, spread=0.9)
    x = mix(sat(crunch * 0.8, 1.5), rain * 0.8)
    return fade(room(pad(x, D), rng, 0.22, 1.2), 0.001, 0.2)[:n]


@sound('impact_dirt', 5, desc='round hitting ground: thud + dirt spray')
def impact_dirt(rng):
    D = 1.3
    th = sub_thump(rng, rng.uniform(120, 150), 55, 0.4, 0.04, 0.12, 1.6)
    cr = crack(rng, 0.06, 1200, 9000, 0.01)
    spray = debris_patter(rng, 1.1, 0.03, 160, 6, 0.0)
    hiss = lp(pink(secs(0.6), rng), 4000) * env_ad(secs(0.6), 0.005, 0.18, 3)
    x = mix(th, cr * 0.6, spray * 0.6, hiss * 0.35)
    return fade(room(pad(x, D), rng, 0.15, 0.9), 0.0005, 0.15)[:secs(D)]


@sound('impact_metal', 6, desc='round hitting armour: hard clang (noisy, damped) + sparks')
def impact_metal(rng):
    D = 1.3
    h = metal_hit(rng, rng.uniform(300, 800), 0.8, rng.uniform(0.6, 1.0), rng.uniform(0.05, 0.11), 12, 1.0)
    th = sub_thump(rng, 140, 60, 0.3, 0.03, 0.08, 1.5)
    cr = crack(rng, 0.05, 2000, 12000, 0.008)
    sparks = electric_crackle(rng, 0.4, 600, (3000, 12000)) * env_exp(secs(0.4), 0.06)
    bits = grain_debris(rng, 1.0, 0.05, 14, rock=0.4, metal=0.8, chunks=0, spread=0.3)
    x = mix(h * 0.45, th * 0.8, cr * 0.8, sparks * 0.25, bits * 0.3)
    return fade(room(pad(sat(x, 1.3), D), rng, 0.18, 1.0), 0.0005, 0.15)[:secs(D)]


@sound('impact_energy', 4, desc='Terran laser hit: clean zap-burn with a sizzle tail')
def impact_energy(rng):
    D = 1.0
    n = secs(0.5)
    zap = osc(glide(2400, 300, n, 0.03), shape='saw') * env_ad(n, 0.001, 0.08, 4)
    burn = bp(white(secs(0.8), rng), 2500, 9000) * env_ad(secs(0.8), 0.003, 0.25, 3) * 0.3
    th = sub_thump(rng, 160, 70, 0.3, 0.03, 0.08, 1.4)
    x = mix(lp(zap, 7000) * 0.5, burn, th * 0.8)
    return fade(room(pad(x, D), rng, 0.2, 0.9), 0.0005, 0.1)[:secs(D)]


@sound('impact_gold', 5, desc='Arcadian lightning strike landing: crack + crackle splash + gold shimmer')
def impact_gold(rng):
    D = 1.6
    cr = crack(rng, 0.09, 800, 12000, 0.02)
    th = sub_thump(rng, rng.uniform(100, 130), 45, 0.6, 0.05, 0.18, 2.0)
    ck = electric_crackle(rng, 0.9, 1400, (1500, 11000), 110, 0.15) * env_ad(secs(0.9), 0.002, 0.25, 3)
    sh = gold_shimmer(rng, 0.9, decay=0.35)
    x = mix(cr * 0.8, th * 0.75, ck * 0.85, sh * 0.14)
    return fade(room(pad(sat(x, 1.4), D), rng, 0.2, 1.1), 0.0005, 0.15)[:secs(D)]


# =================================================================== weapons
def gun(rng, D, crack_amt, sub_f, sub_dec, body_dec, tail_dec, mech=0.3, echo=True, bright=10000):
    cr = crack(rng, 0.05, 1500, bright, 0.006) * crack_amt
    blast = bp(white(secs(0.25), rng), 200, 4000, 1) * env_ad(secs(0.25), 0.0008, body_dec, 5)
    sub = sub_thump(rng, sub_f, sub_f * 0.45, 0.8, 0.05, sub_dec, 2.2)
    tail = lp(pink(secs(D), rng), 1800) * env_ad(secs(D), 0.01, tail_dec, 3.0)
    clank = metal_hit(rng, rng.uniform(500, 1400), 0.25, 0.7, rng.uniform(0.02, 0.05), 10, 0.9) * mech  # breech
    x = mix(cr * 1.1, sat(blast * 1.3, 2) * 1.1, sub * 0.65, tail * 0.4, at(clank, rng.uniform(0.02, 0.05), D))
    x = sat(x * 1.2, 1.6)
    if echo:
        x = outdoor(x, rng, 0.8 if D > 2 else 0.6, 0.8)
    return fade(room(pad(x, D), rng, 0.18, 1.1), 0.0003, 0.15)[:secs(D)]


@sound('shot_cannon', 5, desc='tank cannon: sharp crack, low body, short rolling tail')
def shot_cannon(rng):
    return gun(rng, 1.6, 0.9, rng.uniform(85, 100), 0.18, 0.06, 0.45)


@sound('shot_heavy', 4, desc='heavy gun: bigger crack, deep body, long tail + echo')
def shot_heavy(rng):
    return gun(rng, 2.4, 1.0, rng.uniform(60, 72), 0.32, 0.1, 0.8, mech=0.45)


@sound('shot_autocannon', 8, desc='autocannon round: short punchy bark')
def shot_autocannon(rng):
    return gun(rng, 0.7, 0.9, rng.uniform(120, 140), 0.06, 0.025, 0.14, mech=0.12, echo=False, bright=12000)


@sound('shot_shell', 3, desc='artillery launch: deep boom with long echo')
def shot_shell(rng):
    return gun(rng, 2.8, 0.7, rng.uniform(55, 62), 0.4, 0.12, 1.0, mech=0.3)


@sound('shot_laser', 6, desc='Terran laser: clean synthetic zap with a punchy low end')
def shot_laser(rng):
    D = 0.9
    n = secs(0.45)
    t = np.arange(n) / SR
    f0 = rng.uniform(2600, 3400)
    fc = glide(f0, rng.uniform(260, 380), n, rng.uniform(0.035, 0.05))
    mod = osc(fc * 1.5, shape='sine') * 2.5 * np.exp(-t / 0.05)
    car = np.sin(2 * np.pi * np.cumsum(fc) / SR + mod)
    zap = car * env_ad(n, 0.001, 0.12, 4)
    det = np.sin(2 * np.pi * np.cumsum(fc * 1.012) / SR) * env_ad(n, 0.001, 0.1, 4)
    th = sub_thump(rng, 150, 60, 0.3, 0.03, 0.08, 1.5)
    air = hp(white(secs(0.15), rng), 5000) * env_ad(secs(0.15), 0.0005, 0.03, 5) * 0.4
    x = mix(np.stack([zap, det], 1) * 0.6, th * 0.7, air)
    return fade(room(pad(x, D), rng, 0.3, 1.0, (7000, 1500)), 0.0003, 0.1)[:secs(D)]


@sound('shot_missile', 4, desc='missile launch: ignition thump + rocket hiss whooshing away')
def shot_missile(rng):
    D = 1.8
    n = secs(D)
    th = sub_thump(rng, 110, 45, 0.5, 0.05, 0.15, 1.8)
    pop = crack(rng, 0.05, 600, 6000, 0.012)
    hiss = pink(n, rng)
    roar = sweep_lp(hiss, 6000, 900) * env_ad(n, 0.02, 0.8, 2.5)
    crackle = electric_crackle(rng, D, 300, (400, 3000)) * env_ad(n, 0.02, 0.6, 2.5)
    x = mix(th * 0.8, pop * 0.5, roar * 0.7, crackle * 0.3)
    return fade(room(pad(x, D), rng, 0.2, 1.0), 0.0005, 0.3)


@sound('shot_bomb', 2, desc='bomb release clunk + falling whistle')
def shot_bomb(rng):
    D = 1.6
    n = secs(D)
    f = rng.uniform(500, 700)
    clunk = modal(secs(0.3), rng, [f * 0.3, f, f * 2.3], [0.06, 0.04, 0.02]) + sub_thump(rng, 120, 60, 0.3, 0.02, 0.05)
    wh = bp(white(n, rng), 1500, 3500) * env_ad(n, 0.4, 0.8, 1.5) * 0.25
    whistle = osc(glide(1800, 700, n, 1.2), shape='sine') * env_ad(n, 0.5, 0.9, 1.5) * 0.08
    return fade(room(pad(mix(clunk, wh, whistle), D), rng, 0.2), 0.0005, 0.2)


@sound('zap_lightning', 8, desc='Arcadian gold lightning shot: snap + electric sizzle + gold shimmer + arc buzz')
def zap_lightning(rng):
    D = 1.3
    snap = crack(rng, 0.06, 1500, 14000, 0.01)
    th = sub_thump(rng, rng.uniform(90, 120), 40, 0.4, 0.04, 0.12, 2.5)
    L = rng.uniform(0.22, 0.35)
    ck = electric_crackle(rng, L + 0.3, 2200, (1200, 12000), rng.uniform(95, 130), 0.35) \
        * env_ad(secs(L + 0.3), 0.001, L * 0.6, 2.5)
    sh = gold_shimmer(rng, 0.9, decay=0.3)
    # 'zzzap' down-chirp body gives it the whip
    n = secs(0.25)
    whip = bp(osc(glide(3000, 500, n, 0.05), shape='saw'), 300, 8000) * env_ad(n, 0.001, 0.08, 4)
    x = mix(snap * 0.9, th * 0.6, ck * 1.0, sh * 0.18, whip * 0.3)
    return fade(room(pad(sat(x, 1.5), D), rng, 0.25, 1.1), 0.0003, 0.15)[:secs(D)]


@sound('zap_small', 6, desc='short Arcadian arc spark (charge arcs, lifter pops)')
def zap_small(rng):
    D = 0.6
    snap = crack(rng, 0.03, 2500, 14000, 0.005)
    L = rng.uniform(0.06, 0.14)
    ck = electric_crackle(rng, L + 0.1, 2500, (2000, 12000), 120, 0.2) * env_ad(secs(L + 0.1), 0.001, L, 2.5)
    sh = gold_shimmer(rng, 0.4, decay=0.15)
    x = mix(snap * 0.6, ck * 0.7, sh * 0.08)
    return fade(room(pad(x, D), rng, 0.2, 0.8), 0.0003, 0.08)[:secs(D)]


@sound('crackle_loop', 3, loop=True, desc='sustained Arcadian lightning crackle (beams, long bolts)')
def crackle_loop(rng):
    D = 3.4
    n = secs(D)
    ck = electric_crackle(rng, D, 1800, (1200, 11000), 100, 0.3)
    sh = gold_shimmer(rng, D, decay=99)  # no decay: sustained shimmer bed
    hum = sat(osc(100 * (1 + 0.02 * smooth_random(n, rng, 8, -1, 1)), shape='saw') * 0.6, 2)
    x = mix(ck * 0.7, sh * 0.06, bp(hum, 80, 1500) * 0.25)
    return loopify(st(x, rng, 0.8), 0.4)


@sound('beam_blue_loop', 2, loop=True, desc='Terran energy beam: clean detuned synth hum with ripple')
def beam_blue_loop(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    f = rng.uniform(140, 170)
    y = np.zeros(n)
    for k, a in ((1, 1), (2, .5), (3, .35), (5, .2), (8, .1)):
        y += a * (np.sin(2 * np.pi * f * k * t) + np.sin(2 * np.pi * f * k * 1.004 * t))
    y *= 0.8 + 0.2 * np.sin(2 * np.pi * 11 * t)
    hiss = hp(white(n, rng), 6000) * 0.05
    return loopify(st(mix(lp(y, 5000) * 0.3, hiss), rng, 0.8), 0.4)


@sound('beam_start', 3, desc='beam ignition whoomp (both factions; pitch-shifted at mix)')
def beam_start(rng):
    D = 0.8
    n = secs(0.6)
    sw = osc(glide(90, 300, n, 0.08), shape='saw') * env_ad(n, 0.005, 0.2, 3)
    th = sub_thump(rng, 130, 50, 0.4, 0.04, 0.12, 2)
    x = mix(lp(sw, 3000) * 0.5, th, crack(rng, 0.04, 2000, 10000, 0.006) * 0.4)
    return fade(room(pad(x, D), rng, 0.2), 0.0003, 0.1)


@sound('charge_gold', 3, desc='Arcadian charge-up: rising crackle + rising shimmer')
def charge_gold(rng):
    D = 0.55
    n = secs(D)
    t = np.arange(n) / SR
    rise = (t / D) ** 1.5
    ck = electric_crackle(rng, D, 300 + 3000 * rise.mean(), (2000, 12000)) * rise
    f = 300 + 1600 * rise
    tone = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 2.24) / SR)) * rise
    x = mix(ck * 0.5, tone * 0.15)
    return fade(st(x, rng, 0.6), 0.01, 0.02)


# =================================================================== shields
@sound('shield_hit', 5, desc='shield takes a hit: resonant hum ripple and a soft energy whomp (never glass)')
def shield_hit(rng):
    D = 1.6
    n = secs(D)
    t = np.arange(n) / SR
    base = rng.uniform(95, 115)
    y = np.zeros(n)
    for r, a in ((1, 1), (1.5, .7), (2.0, .55), (3.0, .3), (4.02, .18)):
        f = base * r * (1 + 0.04 * np.exp(-t / 0.08))  # slight bend-down
        y += a * np.sin(2 * np.pi * np.cumsum(f) / SR + rng.uniform(0, 6))
    ripple_rate = 6 + 16 * np.exp(-t / 0.25)
    rip = 0.6 + 0.4 * np.sin(2 * np.pi * np.cumsum(ripple_rate) / SR)
    hum = sat(y * 0.4, 1.5) * rip * env_ad(n, 0.01, 0.6, 2.6)
    whomp = sweep_lp(pink(n, rng), 2500, 150) * env_ad(n, 0.004, 0.25, 3)
    th = sub_thump(rng, 90, 40, 0.6, 0.05, 0.2, 1.6)
    x = mix(lp(hum, 3500) * 0.7, whomp * 0.35, th * 0.6)
    return fade(room(pad(x, D), rng, 0.35, 1.6, (3000, 600)), 0.001, 0.25)[:n]


@sound('shield_loop', 2, loop=True, desc='shield dome idle hum')
def shield_loop(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    base = rng.uniform(82, 90)
    y = sum(a * np.sin(2 * np.pi * base * r * t + rng.uniform(0, 6)) for r, a in ((1, 1), (2, .6), (3, .4), (3.01, .3), (5, .15)))
    y *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.7 * t)
    return loopify(st(lp(y, 900) * 0.4, rng, 0.7), 0.4)


# =================================================================== mechanics
@sound('servo', 8, desc='servo/actuator move: rough motor + gear-tooth ticks + friction, start/stop clicks')
def servo(rng):
    D = rng.uniform(0.6, 1.1)
    n = secs(D)
    u = np.linspace(0, 1, n)
    speed = np.clip(np.sin(np.pi * u) ** 0.6 * (1 + 0.15 * smooth_random(n, rng, 4, -1, 1)), 0, 1)
    y = servo_tone(rng, n, speed, rng.uniform(180, 380), gear=1.0)
    clk = metal_hit(rng, rng.uniform(1200, 2500), 0.06, 0.7, 0.01, 6, 0.6) * 0.25
    x = mix(y * 0.6, clk, at(clk * 0.7, D - 0.04, D))
    return fade(room(st(x, rng, 0.4), rng, 0.15, 0.8), 0.005, 0.05)


@sound('turret_servo', 6, desc='short turret traverse: geared slewing ring grind')
def turret_servo(rng):
    D = 0.5
    n = secs(D)
    u = np.linspace(0, 1, n)
    speed = np.clip(np.sin(np.pi * u) ** 0.5, 0, 1)
    y = servo_tone(rng, n, speed, rng.uniform(350, 600), gear=1.4)
    ring = bp(pink(n, rng), 80, 700, 2) * speed * (0.6 + 0.4 * smooth_random(n, rng, 30, 0, 1)) * 0.25
    clat = np.zeros(n)                       # ball race / ring rollers knocking round
    for _ in range(int(rng.integers(4, 9))):
        h = metal_hit(rng, rng.uniform(400, 1200), 0.08, 0.5, 0.015, 6, 0.6)
        clat += at(h * rng.uniform(0.05, 0.2), rng.uniform(0.02, D - 0.1), D)
    return fade(st(mix(y * 0.4, ring, clat * speed), rng, 0.3), 0.005, 0.05)


@sound('mech_clunk', 8, desc='heavy mechanical lock: latch click, then thud + damped metal')
def mech_clunk(rng):
    D = 0.9
    latch = metal_hit(rng, rng.uniform(1500, 3000), 0.08, 0.9, 0.01, 6, 0.8) * 0.35
    body = metal_hit(rng, rng.uniform(120, 300), 0.6, rng.uniform(0.2, 0.5), rng.uniform(0.04, 0.09), 12, 0.8)
    th = sub_thump(rng, rng.uniform(80, 110), 45, 0.4, 0.03, 0.09, 2)
    pre = rng.uniform(0.015, 0.05)
    x = mix(latch, at(body * 0.6, pre, D), at(th, pre, D))
    return fade(room(pad(sat(x, 1.3), D), rng, 0.2, 0.8), 0.0003, 0.1)


@sound('hydraulic', 4, desc='hydraulic hiss / pressure release')
def hydraulic(rng):
    D = rng.uniform(0.6, 1.0)
    n = secs(D)
    x = bp(white(n, rng), 2500, 9000) * env_ad(n, 0.02, D * 0.5, 2.5)
    x *= 0.8 + 0.2 * smooth_random(n, rng, 30, 0, 1)
    return fade(st(x * 0.4, rng, 0.8), 0.005, 0.05)


@sound('power_up_terran', 3, desc='Terran structure powers up: rising neon hum that settles')
def power_up_terran(rng):
    D = 1.6
    n = secs(D)
    t = np.arange(n) / SR
    f = glide(55, 110, n, 0.25)
    y = sum(a * np.sin(2 * np.pi * np.cumsum(f * r) / SR) for r, a in ((1, 1), (2, .6), (3, .4), (4, .25), (6, .12)))
    y *= env_ad(n, 0.3, 0.9, 2)
    zz = bp(white(n, rng), 4000, 9000) * env_ad(n, 0.15, 0.4, 3) * 0.04
    blip = osc(glide(900, 1800, secs(0.2), 0.05), shape='sine') * env_ad(secs(0.2), 0.002, 0.08, 3)
    x = mix(lp(y, 2500) * 0.4, zz, at(blip * 0.15, 0.35, D))
    del t
    return fade(room(st(x, rng, 0.6), rng, 0.25, 1.2), 0.01, 0.2)


@sound('power_up_arc', 3, desc='Arcadian structure awakens: crackle bloom + gold shimmer chord')
def power_up_arc(rng):
    D = 1.8
    n = secs(D)
    sh = gold_shimmer(rng, D, base=rng.uniform(900, 1100), decay=0.8) * env_ad(n, 0.25, 1.0, 2)
    ck = electric_crackle(rng, D, 900, (1500, 10000), 90, 0.2) * env_ad(n, 0.05, 0.5, 2.5)
    low = sat(osc(glide(40, 80, n, 0.3), shape='saw'), 2) * env_ad(n, 0.2, 0.8, 2)
    x = mix(sh * 0.15, ck * 0.4, lp(low, 600) * 0.4)
    return fade(room(st(x, rng, 0.7), rng, 0.3, 1.4), 0.01, 0.2)


@sound('whirr_loop', 2, loop=True, desc='spinning rotor/blades whirr')
def whirr_loop(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    blade = 0.6 + 0.4 * np.sin(2 * np.pi * 18 * t) ** 2
    x = bp(pink(n, rng), 300, 2500) * blade
    tone = osc(240, n, 'saw') * 0.15
    return loopify(st(mix(x * 0.5, lp(tone, 1500)), rng, 0.6), 0.4)


@sound('grind_loop', 2, loop=True, desc='mining drum / grinder chewing rock')
def grind_loop(rng):
    D = 3.4
    n = secs(D)
    rocks = conv(impulses(n, rng, 260, 2), np.hanning(secs(0.003)))[:n]
    rocks = bp(rocks, 250, 4000) * 3
    motor = servo_tone(rng, n, np.full(n, 0.7), 180, 0.8)
    rum = bp(brown(n, rng), 60, 300) * 0.4
    return loopify(st(mix(rocks * 0.9, motor * 0.4, rum), rng, 0.6), 0.4)


@sound('fire_loop', 2, loop=True, desc='burning wreck: low roar + pops')
def fire_loop(rng):
    D = 3.4
    n = secs(D)
    roar = bp(pink(n, rng), 90, 1200) * (0.6 + 0.4 * smooth_random(n, rng, 5, 0, 1))
    pops = bp(conv(impulses(n, rng, 60, 3), np.hanning(secs(0.002)))[:n], 800, 7000) * 6
    hiss = bp(pink(n, rng), 1500, 5000) * 0.15
    return loopify(st(mix(roar * 0.6, pops * 0.5, hiss), rng, 0.8), 0.4)


@sound('crystal_spike', 5, desc='crystal spike bursting out of the ground: rock heave + crunch, then a cold '
       'inharmonic crystalline ring that shimmers away (struck, not glass breaking)')
def crystal_spike(rng):
    D = 2.2
    heave = sub_thump(rng, f0=rng.uniform(70, 95), f1=35, dur=0.8, tau=0.06, decay=0.3) * 0.5
    crunch = grain_debris(rng, 1.4, 0.0, 70, rock=1.0, metal=0.0, chunks=2, spread=0.35) * 0.6
    ring = np.zeros(secs(D))
    for _ in range(3):  # a few facets, each its own pitch, ringing long
        h = metal_hit(rng, rng.uniform(900, 2400), 1.6, 0.9, rng.uniform(0.35, 0.7), 10, 0.25)
        ring += at(h * rng.uniform(0.3, 0.6), rng.uniform(0.0, 0.05), D)
    t = np.arange(len(ring)) / SR
    ring *= 1 + 0.25 * np.sin(2 * np.pi * rng.uniform(5, 8) * t)
    x = mix(pad(heave, D), pad(crunch, D), hp(ring, 700, 2) * 0.35)
    return fade(st(outdoor(x, rng, 0.7)[:secs(D + 0.8)], rng, 0.7), 0.001, 0.4)


@sound('shard_wake', 2, desc='the Shard wakes: deep inharmonic swell, crystalline shimmer rising, ends in a low whoomp')
def shard_wake(rng):
    D = 2.5
    n = secs(D)
    t = np.arange(n) / SR
    sw = np.clip(t / 0.5, 0, 1) ** 2 * np.exp(-np.clip(t - 0.5, 0, None) / 0.9)
    drone = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f, a in ((43, 1), (61.7, .7), (97.3, .4), (151, .2)))
    sh = np.zeros(n)
    for k in range(8):
        f = rng.uniform(1200, 4200) * (1 + 0.15 * t)
        sh += np.sin(2 * np.pi * np.cumsum(np.full(n, 1.0) * f) / SR) * np.exp(-((t - rng.uniform(0.3, 0.9)) / 0.4) ** 2)
    whoomp = sub_thump(rng, f0=80, f1=30, dur=1.2, tau=0.1, decay=0.5)
    x = mix(sat(drone * 0.8, 2) * sw * 0.5, sh * sw * 0.03, at(whoomp * 0.5, 0.45, D))
    return fade(st(x, rng, 0.7), 0.01, 0.3)


@sound('whoosh', 4, desc='fast fly-by whoosh (peak at 0.6 s)')
def whoosh(rng):
    D = 1.2
    n = secs(D)
    t = np.arange(n) / SR
    e = np.exp(-((t - 0.6) / 0.22) ** 2)
    fc = 400 + 3000 * e
    x = tv_bandpass(pink(n, rng), fc, 1.5) * e
    return fade(st(x * 0.8, rng, 0.8), 0.01, 0.05)


@sound('skid', 4, desc='tracks/tyres braking hard: gravel scrape + rubber/metal squeal + spray')
def skid(rng):
    D = 0.9
    n = secs(D)
    e = env_ad(n, 0.02, 0.45, 2.2)
    scrape = bp(pink(n, rng), 300, 4000, 2) * (0.6 + 0.4 * smooth_random(n, rng, 30, 0, 1))
    gravel = grain_debris(rng, D, 0.0, 70, rock=1.0, metal=0.05, chunks=0, spread=0.4)
    f = rng.uniform(700, 1200) * (1 - 0.15 * np.linspace(0, 1, n))
    squeal = bp(np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.abs(lp(white(n, rng), 120, 2)) / 0.1), 400, 5000, 1)
    x = mix(scrape * e * 0.6, gravel * 0.5, squeal * e * 0.05)
    return fade(room(st(x, rng, 0.6), rng, 0.15, 0.8), 0.005, 0.1)


@sound('shockwave', 4, desc='energy/ground shockwave: whoomp with an air-pressure sweep and low thump (no crack)')
def shockwave(rng):
    D = 2.0
    n = secs(1.6)
    th = sub_thump(rng, rng.uniform(70, 90), 35, 1.2, 0.12, 0.45, 2.2)
    sweep = sweep_lp(pink(n, rng), 3500, 120) * env_ad(n, 0.01, 0.5, 2.5)
    air = tv_bandpass(pink(n, rng), 300 + 2500 * np.exp(-np.arange(n) / SR / 0.25), 1.2) * env_ad(n, 0.005, 0.4, 3)
    x = mix(th, sweep * 0.8, air * 0.5)
    return fade(room(pad(outdoor(x, rng, 0.7, 0.6), D), rng, 0.2, 1.3), 0.002, 0.2)


@sound('lock_pulse', 3, desc='Terran target-lock: three soft synthetic thrums rising (no beeps, no words)')
def lock_pulse(rng):
    D = 0.9
    out = np.zeros(secs(D))
    base = rng.uniform(140, 180)
    for i in range(3):
        L = secs(0.14)
        t = np.arange(L) / SR
        f = base * (1 + 0.25 * i)
        y = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) + 0.2 * np.sin(2 * np.pi * 3.01 * f * t))
        y *= env_ad(L, 0.01, 0.08, 3)
        out += at(y, 0.22 * i, D)
    return fade(room(st(lp(out, 3000), rng, 0.5), rng, 0.25, 0.9), 0.003, 0.1)


@sound('tractor_loop', 2, loop=True, desc='Terran neon tractor/repair beam: smooth phasing hum with a fizzing edge')
def tractor_loop(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    f = rng.uniform(95, 120)
    y = sum(a * np.sin(2 * np.pi * f * r * t + rng.uniform(0, 6)) * (0.7 + 0.3 * np.sin(2 * np.pi * rng.uniform(0.5, 2) * t))
            for r, a in ((1, 1), (2, .6), (3.01, .35), (5, .15)))
    fizz = bp(white(n, rng), 3000, 9000) * (0.5 + 0.5 * smooth_random(n, rng, 12, 0, 1)) * 0.08
    return loopify(st(mix(lp(y, 2500) * 0.3, fizz), rng, 0.7), 0.4)


@sound('motes_loop', 2, loop=True, desc='stream of gold motes / liquid light: glittering granular sparkle over a soft whoosh')
def motes_loop(rng):
    D = 3.4
    n = secs(D)
    sparkle = np.zeros(n)
    for _ in range(int(D * 70)):
        L = secs(rng.uniform(0.03, 0.12))
        f = rng.uniform(1800, 6000)
        g = np.sin(2 * np.pi * f * np.arange(L) / SR) * np.hanning(L)
        sparkle += at(g * rng.uniform(0.05, 0.4), rng.uniform(0, D - 0.13), D)
    flow = bp(pink(n, rng), 400, 3000, 1) * (0.6 + 0.4 * smooth_random(n, rng, 2, 0, 1)) * 0.3
    ck = electric_crackle(rng, D, 250, (2000, 10000)) * 0.3
    return loopify(st(mix(sparkle * 0.5, flow, ck), rng, 0.9), 0.4)


# =================================================================== engines (loops, modulated at mix)
def piston(rng, D, cyl, rpm_hz, tone=(250, 700), bark=0.035, wob=0.05, misfire=0.015):
    """Firing pulses of a multi-cylinder engine: each cylinder its own strength and exhaust colour
    (the 'lope'), crank speed wandering, rare misfires. Returns (exhaust, wander)."""
    n = secs(D)
    fire_hz = rpm_hz * cyl / 2
    prof = rng.uniform(0.55, 1.0, cyl)
    tones = rng.uniform(tone[0], tone[1], cyl)
    wander = 1 + wob * smooth_random(n, rng, 0.8, -1, 1)
    out = np.zeros(n)
    tt, k = 0.0, 0
    L = secs(bark)
    while tt < D:
        i = secs(tt)
        c = k % cyl
        if i + L < n and rng.random() > misfire:
            b = rng.standard_normal(L) * env_exp(L, bark * 0.23)
            b = lp(b, tones[c] * rng.uniform(0.85, 1.15), 2)
            b += 0.25 * np.sin(2 * np.pi * rng.uniform(55, 80) * np.arange(L) / SR) * env_exp(L, 0.01)
            out[i:i + L] += b * prof[c] * rng.uniform(0.85, 1.1)
        tt += 1 / (fire_hz * wander[min(i, n - 1)]) * rng.uniform(0.97, 1.03)
        k += 1
    return sat(out / (np.max(np.abs(out)) + 1e-9) * 2.0, 1.8), wander


def crunch_bed(rng, D, rate):
    """Gravel/dirt being rolled over: short independent grit grains spread evenly in time."""
    n = secs(D)
    out = np.zeros(n)
    for _ in range(int(D * rate)):
        L = secs(rng.uniform(0.002, 0.015))
        x = rng.standard_normal(L) * env_exp(L, L / SR / 4)
        fc = rng.uniform(600, 6000)
        x = bp(x, fc * 0.5, min(fc * 2, 20000), 1)
        i = secs(rng.uniform(0, D - 0.02))
        out[i:i + L] += x[:n - i] * rng.uniform(0.1, 1.0) ** 1.5
    return out


def tick_train(rng, D, rate_hz, wander=None, jitter=0.0):
    n = secs(D)
    x = np.zeros(n)
    tt = 0.0
    while tt < D:
        i = secs(tt)
        if i < n:
            x[i] = rng.uniform(0.2, 1.0)
        w = wander[min(i, n - 1)] if wander is not None else 1.0
        tt += 1 / (rate_hz * w) * (1 + jitter * rng.uniform(-1, 1))
    return x


@sound('eng_tracked', 4, loop=True, desc='Terran tracked vehicle engine: lopey multi-cylinder diesel (per-cylinder '
       'exhaust barks), valve ticks, blower hiss, transmission whine that comes and goes; running gear is tracks_loop')
def eng_tracked(rng):
    D = 4.4
    n = secs(D)
    cyl = int(rng.choice([4, 6, 8]))
    rpm_hz = rng.uniform(13, 17)           # crank revs/s at the mixer's 1.0 rate
    exhaust, wander = piston(rng, D, cyl, rpm_hz)
    valves = tick_train(rng, D, rpm_hz * cyl * 0.5, wander)
    valves = bp(conv(valves, np.hanning(secs(0.0015)))[:n], 2500, 7000, 2) * 0.6
    gf = rng.uniform(500, 900) * wander     # transmission: rough, mostly buried, swells now and then
    whine = np.sin(2 * np.pi * np.cumsum(gf) / SR) * np.clip(0.3 + np.abs(lp(rng.standard_normal(n), 30, 2)) / 0.4, 0, 2)
    whine *= smooth_random(n, rng, 0.7, 0, 1) ** 2
    whine = bp(whine, 300, 3000, 1) * 0.012
    blower = bp(pink(n, rng), 1800, 6000, 2) * (0.7 + 0.3 * smooth_random(n, rng, 3, 0, 1)) * 0.06
    knock = np.zeros(n)                     # loose panels/tools buzzing on the hull with the engine
    for _ in range(int(D * 3)):
        h = metal_hit(rng, rng.uniform(700, 2500), 0.12, 0.6, 0.02, 6, 0.7)
        knock += at(h * rng.uniform(0.04, 0.15), rng.uniform(0, D - 0.15), D)
    body = bp(brown(n, rng), 35, 140, 2) * 0.35
    x = mix(exhaust * 0.55, valves * 0.15, whine, blower, knock * 0.4, body * 0.6)
    return loopify(st(x, rng, 0.5), 0.4)


@sound('tracks_loop', 4, loop=True, desc='running gear of a tracked vehicle: links slapping sprockets (damped metal), '
       'road-wheel rumble, gravel crunch, rattles and squeaks; the mixer drives it from ground speed')
def tracks_loop(rng):
    D = 4.4
    n = secs(D)
    link_rate = rng.uniform(10, 15)
    link_irs = [metal_hit(rng, rng.uniform(500, 1500), 0.07, rng.uniform(0.35, 0.75), 0.012, 8, 0.85) for _ in range(6)]
    links = np.zeros(n)
    tt = 0.0
    sway = smooth_random(n, rng, 1.5, 0.5, 1.0)
    while tt < D:
        ir = link_irs[int(rng.integers(0, 6))] * rng.uniform(0.3, 1.0) * sway[min(secs(tt), n - 1)]
        i = secs(tt)
        m = min(len(ir), n - i)
        if m > 0:
            links[i:i + m] += ir[:m]
        tt += 1 / link_rate * rng.uniform(0.85, 1.15)
    road = bp(pink(n, rng), 60, 350, 2) * (0.6 + 0.4 * smooth_random(n, rng, 6, 0, 1))
    thumps = conv(tick_train(rng, D, rng.uniform(3, 5), jitter=0.4), env_exp(secs(0.08), 0.02))[:n]
    thumps = lp(thumps, 180, 2) * 6
    crunch = crunch_bed(rng, D, 160)
    rattle = np.zeros(n)
    for _ in range(int(D * 7)):
        h = metal_hit(rng, rng.uniform(900, 4000), 0.1, 0.8, 0.015, 6, 0.6)
        rattle += at(h * rng.uniform(0.05, 0.25), rng.uniform(0, D - 0.1), D)
    squeak = np.zeros(n)
    for _ in range(int(rng.integers(1, 4))):
        L = secs(rng.uniform(0.08, 0.2))
        f = np.linspace(rng.uniform(1400, 2200), rng.uniform(1800, 3000), L)
        sq = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.hanning(L) * (0.6 + 0.4 * rng.standard_normal(L).clip(-1, 1))
        squeak += at(sq * 0.035, rng.uniform(0.1, D - 0.3), D)
    x = mix(links * 0.55, road * 0.25, thumps * 0.08, crunch * 0.25, rattle * 0.45, squeak)
    r = np.sqrt(np.mean(x ** 2)) * 5           # tame the odd stray spike so the clatter sits at level
    x = np.tanh(x / r) * r
    return loopify(st(x, rng, 0.6), 0.4)


@sound('eng_wheeled', 3, loop=True, desc='Terran wheeled scout engine: revvy 4/5-cylinder with a raspy exhaust, '
       'intake roar and turbo whistle; running gear is tyres_loop')
def eng_wheeled(rng):
    D = 3.4
    n = secs(D)
    cyl = int(rng.choice([4, 5]))
    rpm_hz = rng.uniform(32, 40)
    exhaust, wander = piston(rng, D, cyl, rpm_hz, tone=(600, 1600), bark=0.02, wob=0.03, misfire=0.0)
    rasp = bp(exhaust, 900, 4500, 1) * 0.35
    intake = bp(pink(n, rng), 300, 1500, 2) * (0.7 + 0.3 * smooth_random(n, rng, 5, 0, 1)) * 0.25
    ft = rng.uniform(2600, 3400) * wander
    turbo = np.sin(2 * np.pi * np.cumsum(ft) / SR) * smooth_random(n, rng, 0.6, 0.2, 1) * 0.006
    body = bp(brown(n, rng), 50, 200, 2) * 0.25
    x = mix(exhaust * 0.45, rasp, intake, turbo, body)
    return loopify(st(x, rng, 0.5), 0.4)


@sound('tyres_loop', 3, loop=True, desc='wheeled running gear: tyre roar on dirt, gravel crunch and pings off the '
       'arches, suspension knocks; driven from ground speed')
def tyres_loop(rng):
    D = 3.4
    n = secs(D)
    roar = bp(pink(n, rng), 150, 1600, 2) * (0.7 + 0.3 * smooth_random(n, rng, 4, 0, 1))
    crunch = crunch_bed(rng, D, 260)
    pings = np.zeros(n)
    for _ in range(int(D * 10)):
        h = metal_hit(rng, rng.uniform(1800, 5000), 0.05, 0.9, 0.006, 5, 0.5)
        pings += at(h * rng.uniform(0.03, 0.15), rng.uniform(0, D - 0.06), D)
    knocks = conv(tick_train(rng, D, rng.uniform(1.5, 3), jitter=0.5), env_exp(secs(0.1), 0.025))[:n]
    knocks = lp(knocks, 220, 2) * 5
    x = mix(roar * 0.35, crunch * 0.4, pings * 0.5, knocks * 0.3)
    r = np.sqrt(np.mean(x ** 2)) * 5
    x = np.tanh(x / r) * r
    return loopify(st(x, rng, 0.7), 0.4)


@sound('hover_terran', 2, loop=True, desc='Terran hover/neon hum: clean phasing chord + fan air')
def hover_terran(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    f = rng.uniform(52, 58)
    y = np.zeros(n)
    for r, a in ((1, 1), (2, .7), (3, .45), (4, .3), (6, .15), (8, .08)):
        y += a * (np.sin(2 * np.pi * f * r * t) + np.sin(2 * np.pi * f * r * 1.003 * t + 1))
    fan = bp(pink(n, rng), 300, 3000) * (0.8 + 0.2 * np.sin(2 * np.pi * 9 * t))
    return loopify(st(mix(lp(y, 3000) * 0.25, fan * 0.25), rng, 0.6), 0.4)


@sound('hover_arc', 3, loop=True, desc='Arcadian lightning lifters: crackling gold hum')
def hover_arc(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    f = rng.uniform(70, 85)
    throb = 0.75 + 0.25 * np.sin(2 * np.pi * rng.uniform(3, 5) * t)
    hum = sum(a * np.sin(2 * np.pi * f * r * t + rng.uniform(0, 6)) for r, a in ((1, 1), (1.5, .5), (2, .45), (3, .3), (4.5, .15)))
    hum = sat(hum * 0.5, 1.8) * throb
    ck = electric_crackle(rng, D, 700, (1500, 10000), f * 1.5, 0.12)
    sh = gold_shimmer(rng, D, base=rng.uniform(1300, 1600), decay=99) * 0.05
    return loopify(st(mix(lp(hum, 1500) * 0.35, ck * 0.45, sh), rng, 0.7), 0.4)


@sound('wings_arc', 2, loop=True, desc='Arcadian winged flyer: insect-like wing buzz + crackle thrust')
def wings_arc(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    f = rng.uniform(95, 115)
    buzz = osc(f * (1 + 0.03 * smooth_random(n, rng, 4, -1, 1)), shape='saw')
    buzz = bp(buzz * (0.6 + 0.4 * np.sin(2 * np.pi * 10.5 * t)), 90, 3000)
    ck = electric_crackle(rng, D, 1100, (1500, 11000), 120, 0.15)
    air = bp(pink(n, rng), 500, 3000) * 0.2
    return loopify(st(mix(buzz * 0.35, ck * 0.45, air), rng, 0.7), 0.4)


@sound('jet_terran', 3, loop=True, desc='Terran aircraft: turbulent jet roar, fan blade-pass buzz, rough turbine tones, '
       'combustion rumble')
def jet_terran(rng):
    D = 4.4
    n = secs(D)
    pk = pink(n, rng)
    roar = np.zeros(n)
    for lo, hi in ((120, 400), (400, 1200), (1200, 3500), (3500, 9000)):  # turbulence: bands breathe independently
        roar += bp(pk, lo, hi, 1) * (0.55 + 0.45 * smooth_random(n, rng, rng.uniform(3, 9), 0, 1))
    bpf = rng.uniform(170, 260) * (1 + 0.01 * smooth_random(n, rng, 1.5, -1, 1))     # fan blade-pass
    buzz = 0.7 + 0.3 * np.sign(np.sin(2 * np.pi * np.cumsum(bpf) / SR)) * (0.5 + 0.5 * smooth_random(n, rng, 4, 0, 1))
    fan = bp(white(n, rng), 600, 4000, 2) * buzz * 0.4
    tones = np.zeros(n)
    for f, a in ((rng.uniform(900, 1300), 1.0), (rng.uniform(2200, 2800), 0.6), (rng.uniform(4200, 5200), 0.35)):
        fv = f * (1 + 0.004 * smooth_random(n, rng, 2, -1, 1))
        rough = 0.4 + 0.6 * np.abs(lp(rng.standard_normal(n), 80, 2)) / 0.2
        tones += a * np.sin(2 * np.pi * np.cumsum(fv) / SR) * np.clip(rough, 0, 2)
    combust = lp(brown(n, rng), 200, 2) * (0.6 + 0.4 * smooth_random(n, rng, 2, 0, 1))
    pops = bp(conv(impulses(n, rng, 8, 2), np.hanning(secs(0.01)))[:n], 80, 600, 2) * 3
    # shock 'crackle' of a real jet exhaust: sparse sharp one-sided spikes in bursts
    dens = smooth_random(n, rng, 2.5, 0, 1) ** 2
    spikes = (rng.random(n) < 0.004 * dens) * rng.uniform(0.3, 1.0, n) ** 2
    crackle = bp(conv(spikes, env_exp(secs(0.003), 0.0006))[:n], 900, 9000, 1)
    tones *= smooth_random(n, rng, 0.8, 0.1, 1) ** 2      # turbine tones come and go with the airflow
    x = mix(roar * 0.6, fan, bp(tones, 500, 7000, 1) * 0.01, combust * 0.35, pops * 0.3, crackle * 0.5)
    return loopify(st(x, rng, 0.7), 0.4)


@sound('ship_terran', 2, loop=True, desc='Terran warship in space: deep reactor drone + engine roar')
def ship_terran(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    drone = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((41, 1), (82, .6), (123.5, .3), (246, .1)))
    roar = bp(pink(n, rng), 120, 1500) * 0.5
    x = mix(sat(drone * 0.8, 2.5) * 0.6, roar)
    return loopify(st(x, rng, 0.6), 0.4)


@sound('ship_arc', 2, loop=True, desc='Arcadian ship: crackling gold drone')
def ship_arc(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    drone = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f, a in ((55, 1), (82.5, .6), (110, .4), (165, .2)))
    ck = electric_crackle(rng, D, 500, (1200, 9000), 110, 0.1)
    sh = gold_shimmer(rng, D, base=1000, decay=99) * 0.04
    return loopify(st(mix(drone * 0.35, ck * 0.4, sh), rng, 0.7), 0.4)


@sound('thruster_blue', 2, loop=True, desc='Terran retro-thruster roar (landing)')
def thruster_blue(rng):
    D = 3.4
    n = secs(D)
    roar = bp(pink(n, rng), 120, 5000) * (0.85 + 0.15 * smooth_random(n, rng, 20, 0, 1))
    low = lp(brown(n, rng), 200)
    hiss = hp(white(n, rng), 5000) * 0.1
    return loopify(st(mix(roar * 0.6, low * 0.5, hiss), rng, 0.8), 0.4)


# =================================================================== ambience
def wind(rng, D, lo=180, hi=900, gust_rate=0.35, whistle=0.0):
    n = secs(D)
    fc = lo + (hi - lo) * smooth_random(n, rng, gust_rate, 0, 1)
    w = tv_bandpass(pink(n, rng), fc, 0.9)
    g = 0.5 + 0.5 * smooth_random(n, rng, gust_rate * 1.3, 0, 1)
    w *= g
    if whistle:
        fw = 900 + 500 * smooth_random(n, rng, 0.2, 0, 1)
        w += whistle * tv_bandpass(white(n, rng), fw, 25) * g
    return hp(w, 70, 2)


def amb(rng, layers):
    x = mix(*layers)
    return loopify(x, 0.8)


@sound('amb_desert', 2, loop=True, desc='desert: dry gusting wind, sand hiss')
def amb_desert(rng):
    D = 8.8
    L = wind(rng, D, 200, 1100, 0.35)
    R = wind(rng, D, 200, 1100, 0.35)
    sand = hp(pink(secs(D), rng), 3000) * 0.08 * smooth_random(secs(D), rng, 0.5, 0.3, 1)
    lowr = bp(brown(secs(D), rng), 50, 140) * 0.12
    x = np.stack([L + sand + lowr, R + sand * 0.8 + lowr], 1)
    return amb(rng, [x])


@sound('amb_highland', 2, loop=True, desc='highland: cool open wind with a faint whistle')
def amb_highland(rng):
    D = 8.8
    L = wind(rng, D, 250, 1300, 0.25, 0.04)
    R = wind(rng, D, 250, 1300, 0.25, 0.04)
    lowr = bp(brown(secs(D), rng), 50, 140) * 0.1
    return amb(rng, [np.stack([L + lowr, R + lowr], 1)])


@sound('amb_alien', 2, loop=True, desc='alien world: wind + eerie slow-beating drone')
def amb_alien(rng):
    D = 8.8
    n = secs(D)
    t = np.arange(n) / SR
    L = wind(rng, D, 150, 700, 0.25) * 0.7
    R = wind(rng, D, 150, 700, 0.25) * 0.7
    drone = np.zeros(n)
    for f, a in ((73.4, 1), (73.9, 0.8), (110.2, .5), (164.8, .25), (220.9, .12)):
        drone += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (0.7 + 0.3 * smooth_random(n, rng, 0.3, 0, 1))
    eerie = gold_shimmer(rng, D, base=620, decay=99, trem=3) * smooth_random(n, rng, 0.25, 0, 1) * 0.08
    dr = lp(drone, 1200) * 0.18 + eerie
    return amb(rng, [np.stack([L + dr, R + np.roll(dr, secs(0.003))], 1)])


@sound('amb_dusk', 2, loop=True, desc='dusk: calm low wind, distant low drone')
def amb_dusk(rng):
    D = 8.8
    n = secs(D)
    t = np.arange(n) / SR
    L = wind(rng, D, 150, 600, 0.2) * 0.75
    R = wind(rng, D, 150, 600, 0.2) * 0.75
    drone = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.6 * t)) * (0.6 + 0.4 * smooth_random(n, rng, 0.2, 0, 1)) * 0.06
    lowr = bp(brown(n, rng), 50, 140) * 0.1
    return amb(rng, [np.stack([L + drone + lowr, R + drone + lowr], 1)])


@sound('amb_ash', 2, loop=True, desc='ash waste: heavy low wind and distant rumble')
def amb_ash(rng):
    D = 8.8
    n = secs(D)
    L = wind(rng, D, 120, 600, 0.3)
    R = wind(rng, D, 120, 600, 0.3)
    rum = bp(brown(n, rng), 45, 120) * 0.35 * (0.6 + 0.4 * smooth_random(n, rng, 0.3, 0, 1))
    return amb(rng, [np.stack([L + rum, R + rum], 1)])


@sound('amb_space', 2, loop=True, desc='space: deep cabin-less void hum, faint radiation hiss')
def amb_space(rng):
    D = 8.8
    n = secs(D)
    t = np.arange(n) / SR
    hum = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f, a in
              ((55.1, 1), (110.3, .6), (165.2, .35), (220.6, .25), (330.4, .12), (441.1, .06)))
    hum *= 0.7 + 0.3 * smooth_random(n, rng, 0.2, 0, 1)
    air = bp(pink(n, rng), 150, 900) * 0.25 * (0.6 + 0.4 * smooth_random(n, rng, 0.3, 0, 1))
    hiss = hp(pink(n, rng), 4000) * 0.03
    Lc = hum * 0.2 + air + hiss
    Rc = np.roll(hum, secs(0.002)) * 0.2 + bp(pink(n, rng), 150, 900) * 0.25 + hiss
    return amb(rng, [np.stack([Lc, Rc], 1)])


# =================================================================== bake
def write_wav(path, x):
    x = np.asarray(x, float)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    import wave
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def bake(names=None, out=OUT):
    os.makedirs(out, exist_ok=True)
    man_path = os.path.join(out, 'manifest.json')
    man = json.load(open(man_path)) if os.path.exists(man_path) else {}
    for name, spec in LIB.items():
        if names and name not in names:
            continue
        files = []
        for v in range(spec['variants']):
            rng = np.random.default_rng([sum(map(ord, name)), v])
            x = spec['fn'](rng)
            if x.ndim == 1:
                x = stereoize(x, rng, 0.4)
            # nothing useful below ~30 Hz; it only eats headroom. Loops are filtered circularly
            # (run over two copies, keep the second) so the wrap point stays seamless.
            if spec['loop']:
                x = hp(np.concatenate([x, x]), 28, 2)[len(x):]
            else:
                x = hp(x, 28, 2)
                k = secs(0.001)  # 1 ms fade-in: still a sharp attack, but no step click
                x[:k] *= np.linspace(0, 1, k)[:, None]
            x = norm(x, 0.89)
            fn = f'{name}_{v}.wav'
            write_wav(os.path.join(out, fn), x)
            files.append(fn)
        man[name] = dict(files=files, loop=spec['loop'], desc=spec['desc'], sr=SR,
                         licence='procedurally synthesised by tools/promos/audio/sfx_gen.py (project-owned, no third-party material)')
        print(f'{name}: {len(files)} variants', flush=True)
    json.dump(man, open(man_path, 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    bake(set(sys.argv[1:]) or None)
