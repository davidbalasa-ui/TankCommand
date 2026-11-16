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
                 lp, modal, norm, osc, peak, pink, reverb_ir, sat, secs, slapback, smooth_random,
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


def debris_patter(rng, dur=2.5, t0=0.25, rate0=60, rate1=4, metal=0.5):
    """Bits of rock and metal landing: sparse filtered clicks + a few metal 'tinks'."""
    n = secs(dur)
    t = np.arange(n) / SR
    rate = np.where(t > t0, rate0 * np.exp(-(t - t0) / (dur * 0.35)) + rate1, 0)
    imp = impulses(n, rng, rate, 2.5)
    rocks = bp(conv(imp, np.hanning(secs(0.004)))[:n], 300, 3500, 2)
    rocks += 0.5 * bp(imp, 2000, 7000, 1)
    out = rocks * np.exp(-np.clip(t - t0, 0, None) / (dur * 0.6))
    # metal tinks
    for _ in range(int(metal * 7)):
        ti = rng.uniform(t0 + 0.05, dur * 0.7)
        f = rng.uniform(900, 2600)
        tk = modal(secs(0.35), rng, [f, f * 2.76, f * 5.4], [0.09, 0.05, 0.03], [1, 0.5, 0.25])
        out += at(tk * rng.uniform(0.04, 0.12) * np.exp(-ti), ti, dur)
    return out


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
    """Motor whine whose pitch follows `speed` (0..1 per-sample)."""
    f = base * (0.45 + 0.75 * speed)
    m = osc(f, shape='saw') * 0.5 + 0.35 * osc(f * 2.0, shape='sine') + 0.25 * osc(f * 3.97, shape='sine')
    # gear teeth: AM at a fraction of the motor freq + gritty noise
    teeth = 0.75 + 0.25 * osc(f / 7.0, shape='square')
    grit = bp(white(n, rng), 1500, 6000, 2) * 0.15 * speed
    y = bp(m * teeth, 150, 3000, 2) + gear * grit
    return y * np.clip(speed * 1.3, 0, 1)


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
    deb = debris_patter(rng, 3.0, 0.3, 70, 3, 0.8)
    x = mix(sub * 0.7, cr * 0.8, body * 1.0, low * 0.6, lowmid * 0.9, rum * 0.45, deb * 0.45)
    x = sat(x * 1.3, 1.6)
    x = slapback(x, rng, ((0.16, 0.32), (0.34, 0.2), (0.6, 0.1)), 1400)
    x = pad(x, D)
    y = room(x, rng, 0.22, 1.8, (3500, 500))
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
    deb = debris_patter(rng, 2.2, 0.2, 50, 2, 0.5)
    x = mix(sub * 0.7, cr * 0.8, body * 1.0, lowmid * 0.8, rum * 0.35, deb * 0.4)
    x = sat(x * 1.2, 1.5)
    x = slapback(x, rng, ((0.14, 0.25), (0.3, 0.13)), 1600)
    y = room(pad(x, D), rng, 0.2, 1.5)
    return fade(pad(y, D), 0.0005, 0.25)


@sound('boom_small', 5, desc='small blast / shell landing')
def boom_small(rng):
    D = 2.0
    sub = sub_thump(rng, rng.uniform(95, 120), rng.uniform(40, 50), 0.8, 0.07, 0.25, 1.8)
    cr = crack(rng, 0.08, 1000, 12000, 0.015)
    body = fireball_roar(rng, 1.0, 7000, 300, 0.28, 0.5)
    dirt = debris_patter(rng, 1.4, 0.08, 80, 3, 0.1)
    x = mix(sub * 0.7, cr * 0.8, body * 1.0, dirt * 0.5)
    x = sat(x * 1.2, 1.4)
    y = room(pad(x, D), rng, 0.2, 1.2)
    return fade(pad(y, D), 0.0005, 0.2)


@sound('sub_boom', 4, desc='camera-shake low boom (felt more than heard)')
def sub_boom(rng):
    D = 2.2
    s = sub_thump(rng, rng.uniform(55, 65), rng.uniform(22, 27), 2.0, 0.2, 0.8, 2.5)
    r = rumble(rng, 2.2, 90, 0.9, 0.02)
    x = mix(s, r * 0.5)
    x = lp(x, 400)
    return fade(st(pad(x, D), rng, 0.2), 0.001, 0.3)


@sound('debris_metal', 4, desc='destroyed vehicle: metal crunch + falling parts')
def debris_metal(rng):
    D = 2.6
    n = secs(D)
    # crunch: dense band noise burst with metallic resonances
    cr = bp(white(secs(0.35), rng), 400, 5000, 2) * env_ad(secs(0.35), 0.002, 0.12, 4)
    for f in rng.uniform(300, 1400, 4):
        cr = peak(cr, f, 12, 12)
    hits = np.zeros(n)
    for _ in range(9):
        ti = rng.uniform(0.15, 1.8)
        f = rng.uniform(250, 1600)
        tk = modal(secs(0.5), rng, [f, f * 2.32, f * 4.25, f * 6.8], [0.14, 0.08, 0.05, 0.03])
        tk += 0.6 * lp(white(len(tk), rng), 3000) * env_exp(len(tk), 0.01)
        hits += at(tk * rng.uniform(0.15, 0.5) * np.exp(-ti * 0.9), ti, D)
    x = mix(sat(cr * 1.5, 2), hits)
    return fade(room(pad(x, D), rng, 0.25, 1.2), 0.001, 0.2)[:n]


@sound('impact_dirt', 5, desc='round hitting ground: thud + dirt spray')
def impact_dirt(rng):
    D = 1.3
    th = sub_thump(rng, rng.uniform(120, 150), 55, 0.4, 0.04, 0.12, 1.6)
    cr = crack(rng, 0.06, 1200, 9000, 0.01)
    spray = debris_patter(rng, 1.1, 0.03, 160, 6, 0.0)
    hiss = lp(pink(secs(0.6), rng), 4000) * env_ad(secs(0.6), 0.005, 0.18, 3)
    x = mix(th, cr * 0.6, spray * 0.6, hiss * 0.35)
    return fade(room(pad(x, D), rng, 0.15, 0.9), 0.0005, 0.15)[:secs(D)]


@sound('impact_metal', 5, desc='round hitting armour: clang + sparks')
def impact_metal(rng):
    D = 1.4
    f = rng.uniform(380, 700)
    ring = modal(secs(1.0), rng, [f, f * 1.83, f * 2.71, f * 4.33, f * 6.1], [0.09, 0.07, 0.05, 0.035, 0.025])
    th = sub_thump(rng, 140, 60, 0.3, 0.03, 0.08, 1.5)
    cr = crack(rng, 0.05, 2000, 12000, 0.008)
    sparks = electric_crackle(rng, 0.4, 600, (3000, 12000)) * env_exp(secs(0.4), 0.08)
    x = mix(ring * 0.3, th * 0.8, cr * 0.8, sparks * 0.3)
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
    f = rng.uniform(900, 1500)
    clank = modal(secs(0.25), rng, [f, f * 1.7, f * 2.9], [0.05, 0.035, 0.02]) * mech
    x = mix(cr * 1.1, sat(blast * 1.3, 2) * 1.1, sub * 0.65, tail * 0.4, at(clank, 0.025, D))
    x = sat(x * 1.2, 1.6)
    if echo:
        x = slapback(x, rng, ((0.12, 0.22), (0.27, 0.12)), 2200)
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
@sound('servo', 6, desc='servo/actuator move: whine rising and settling')
def servo(rng):
    D = rng.uniform(0.6, 1.1)
    n = secs(D)
    u = np.linspace(0, 1, n)
    speed = np.clip(np.sin(np.pi * u) ** 0.6, 0, 1)
    y = servo_tone(rng, n, speed, rng.uniform(260, 420), gear=1.2)
    return fade(room(st(y * 0.6, rng, 0.4), rng, 0.15, 0.8), 0.01, 0.05)


@sound('turret_servo', 4, desc='short turret traverse whir')
def turret_servo(rng):
    D = 0.5
    n = secs(D)
    u = np.linspace(0, 1, n)
    speed = np.clip(np.sin(np.pi * u) ** 0.5, 0, 1)
    y = servo_tone(rng, n, speed, rng.uniform(550, 750), gear=0.6)
    return fade(st(y * 0.5, rng, 0.3), 0.01, 0.05)


@sound('mech_clunk', 6, desc='heavy mechanical lock: thud + metal')
def mech_clunk(rng):
    D = 0.9
    f = rng.uniform(180, 320)
    m = modal(secs(0.6), rng, [f, f * 2.1, f * 3.6, f * 5.9], [0.09, 0.05, 0.035, 0.02])
    th = sub_thump(rng, rng.uniform(85, 110), 45, 0.4, 0.03, 0.1, 2)
    click = crack(rng, 0.02, 2000, 9000, 0.003)
    x = mix(m * 0.5, th, click * 0.4)
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


@sound('whoosh', 4, desc='fast fly-by whoosh (peak at 0.6 s)')
def whoosh(rng):
    D = 1.2
    n = secs(D)
    t = np.arange(n) / SR
    e = np.exp(-((t - 0.6) / 0.22) ** 2)
    fc = 400 + 3000 * e
    x = tv_bandpass(pink(n, rng), fc, 1.5) * e
    return fade(st(x * 0.8, rng, 0.8), 0.01, 0.05)


# =================================================================== engines (loops, modulated at mix)
@sound('eng_tracked', 2, loop=True, desc='Terran ground vehicle: diesel-turbine rumble + tread clatter')
def eng_tracked(rng):
    D = 3.4
    n = secs(D)
    t = np.arange(n) / SR
    fire_hz = rng.uniform(28, 34)
    # combustion: pulse train with jitter, each pulse a low thump
    pulses = np.zeros(n)
    tt = 0.0
    while tt < D:
        i = secs(tt)
        if i < n:
            pulses[i] = rng.uniform(0.6, 1.0)
        tt += (1 / (fire_hz * (1 + 0.06 * np.sin(2 * np.pi * 0.6 * tt)))) * rng.uniform(0.92, 1.08)
    k = np.sin(2 * np.pi * 70 * np.arange(secs(0.03)) / SR) * env_exp(secs(0.03), 0.008)
    eng = lp(conv(pulses, k)[:n], 500)
    whine = osc(1150 * (1 + 0.01 * smooth_random(n, rng, 3, -1, 1)), n, 'sine') * 0.015
    # tread: track links clacking on sprockets
    links = np.zeros(n)
    tt = 0.0
    while tt < D:
        i = secs(tt)
        if i < n:
            links[i] = rng.uniform(0.3, 1.0)
        tt += (1 / 13.0) * rng.uniform(0.85, 1.15)
    clack = bp(conv(links, np.hanning(secs(0.004)))[:n], 900, 4000) * 2
    squeal = bp(white(n, rng), 2500, 3200) * 0.06 * smooth_random(n, rng, 2, 0, 1)
    body = lp(brown(n, rng), 160) * 0.5
    growl = sat(bp(osc(fire_hz * 3 * (1 + 0.02 * smooth_random(n, rng, 4, -1, 1)), n, 'saw'), 90, 900) * 2, 2)
    x = mix(sat(eng * 2.5, 2) * 0.5, growl * 0.35, whine, clack * 0.9, squeal, body * 0.4)
    del t
    return loopify(st(x, rng, 0.5), 0.4)


@sound('eng_wheeled', 2, loop=True, desc='Terran wheeled scout: higher revving engine + tyre/gravel roar')
def eng_wheeled(rng):
    D = 3.4
    n = secs(D)
    f = rng.uniform(58, 66) * (1 + 0.02 * smooth_random(n, rng, 2, -1, 1))
    eng = osc(f, shape='saw') + 0.5 * osc(f * 0.5, shape='square')
    eng = sat(bp(eng, 60, 2500), 2.2)
    tyres = bp(pink(n, rng), 200, 1800) * 0.35
    gravel = bp(conv(impulses(n, rng, 120, 2.5), np.hanning(secs(0.002)))[:n], 1500, 6000) * 1.5
    x = mix(eng * 0.5, tyres, gravel * 0.3)
    return loopify(st(x, rng, 0.5), 0.4)


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


@sound('jet_terran', 2, loop=True, desc='Terran aircraft: turbine whine + jet roar')
def jet_terran(rng):
    D = 3.4
    n = secs(D)
    roar = bp(pink(n, rng), 150, 5000) * 0.7 + bp(brown(n, rng), 60, 300) * 0.3
    f = rng.uniform(1800, 2300)
    wh = sum(a * osc(f * r * (1 + 0.003 * smooth_random(n, rng, 2, -1, 1)), n, 'sine') for r, a in ((1, 1), (1.33, .5), (2.1, .3)))
    x = mix(roar, wh * 0.035)
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
