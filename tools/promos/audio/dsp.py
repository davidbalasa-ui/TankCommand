"""Small DSP toolkit for the promo sound library and mixer (numpy; scipy when available).

Everything is mono float64 at SR unless a function says otherwise. Stereo is (n, 2).
"""
import numpy as np

try:  # scipy makes the filters exact and fast; the fallbacks are FFT-domain approximations
    from scipy import signal as _sig
except Exception:  # pragma: no cover
    _sig = None

SR = 48000


def secs(n):
    return int(round(n * SR))


def tvec(dur):
    return np.arange(secs(dur)) / SR


# ---------------------------------------------------------------------------- noise
def white(n, rng):
    return rng.standard_normal(n)


def colored(n, rng, slope_db_oct=-3.0):
    """Noise with a spectral slope (pink=-3 dB/oct, brown=-6)."""
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    X *= (f / 1000.0) ** (slope_db_oct / 6.0206)
    y = np.fft.irfft(X, n)
    return y / (np.std(y) + 1e-12)


def pink(n, rng):
    return colored(n, rng, -3.0)


def brown(n, rng):
    return colored(n, rng, -6.0)


# ---------------------------------------------------------------------------- filters
def _sos(kind, f, order=2):
    f = np.atleast_1d(np.asarray(f, float))
    f = np.clip(f, 10, SR / 2 * 0.98)
    return _sig.butter(order, f if len(f) > 1 else f[0], btype=kind, fs=SR, output='sos')


def _fft_filter(x, kind, f, order):
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(len(x), 1 / SR) + 1e-6
    f = np.atleast_1d(f)
    if kind == 'low':
        H = 1 / np.sqrt(1 + (fr / f[0]) ** (2 * order))
    elif kind == 'high':
        H = 1 / np.sqrt(1 + (f[0] / fr) ** (2 * order))
    else:
        H = (1 / np.sqrt(1 + (fr / f[1]) ** (2 * order))) * (1 / np.sqrt(1 + (f[0] / fr) ** (2 * order)))
    return np.fft.irfft(X * H, len(x))


def lp(x, f, order=2):
    if _sig is None:
        return _fft_filter(x, 'low', f, order)
    return _sig.sosfilt(_sos('lowpass', f, order), x, axis=0)


def hp(x, f, order=2):
    if _sig is None:
        return _fft_filter(x, 'high', f, order)
    return _sig.sosfilt(_sos('highpass', f, order), x, axis=0)


def bp(x, f0, f1, order=2):
    if _sig is None:
        return _fft_filter(x, 'band', (f0, f1), order)
    return _sig.sosfilt(_sos('bandpass', (f0, f1), order), x, axis=0)


def peak(x, f, q=4.0, gain_db=6.0):
    """RBJ peaking EQ."""
    if _sig is None:
        return x
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return _sig.lfilter(np.array(b) / a[0], np.array(a) / a[0], x, axis=0)


def sweep_lp(x, f_start, f_end, block=256, curve='exp'):
    """Lowpass whose cutoff moves from f_start to f_end over the signal (block-wise one-pole
    cascade, 2 poles). Gives the 'fireball rolling off' and whoosh sweeps."""
    n = len(x)
    nb = (n + block - 1) // block
    u = np.linspace(0, 1, nb)
    if curve == 'exp':
        fc = f_start * (f_end / f_start) ** u
    else:
        fc = f_start + (f_end - f_start) * u
    return tv_onepole(x, np.repeat(fc, block)[:n], poles=2)


def tv_onepole(x, fc, poles=2):
    """Time-varying one-pole lowpass cascade with per-sample cutoff array fc."""
    a = np.exp(-2 * np.pi * np.clip(fc, 5, SR / 2.2) / SR)
    y = np.asarray(x, float)
    for _ in range(poles):
        y = _tv_filter(y, a)
    return y


def _tv_filter(x, a):
    # y[n] = (1-a[n]) x[n] + a[n] y[n-1]; done in chunks with scipy when the coefficient is
    # roughly constant per chunk (256 samples): fast and smooth enough for sweeps.
    n = len(x)
    y = np.empty(n)
    zi = 0.0
    B = 256
    for i in range(0, n, B):
        aa = float(np.mean(a[i:i + B]))
        seg = x[i:i + B]
        if _sig is not None:
            out, zf = _sig.lfilter([1 - aa], [1, -aa], seg, zi=[zi * aa])
            y[i:i + B] = out
            zi = out[-1]
        else:
            acc = zi
            for k, v in enumerate(seg):
                acc = (1 - aa) * v + aa * acc
                y[i + k] = acc
            zi = acc
    return y


def tv_bandpass(x, fc, q=2.0, block=256):
    """Time-varying band-pass (state-variable filter, block-constant coefficients)."""
    n = len(x)
    y = np.empty(n)
    low = band = 0.0
    fc = np.broadcast_to(np.asarray(fc, float), (n,))
    for i in range(0, n, block):
        f = float(np.mean(fc[i:i + block]))
        F = 2 * np.sin(np.pi * min(f, SR / 6) / SR)
        Q = 1.0 / q
        seg = x[i:i + block]
        out = np.empty(len(seg))
        for k, v in enumerate(seg):
            low += F * band
            high = v - low - Q * band
            band += F * high
            out[k] = band
        y[i:i + block] = out
    return y


# ---------------------------------------------------------------------------- envelopes
def env_ad(n, attack, decay, curve=4.0):
    """Attack (linear) then exponential-ish decay to 0 over `decay` seconds."""
    a = max(1, secs(attack))
    t = np.arange(n) / SR
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    td = np.clip((t - attack) / max(decay, 1e-4), 0, None)
    e[a:] = np.exp(-curve * td[a:])
    e[t > attack + decay * 1.6] *= np.clip(1 - (td[t > attack + decay * 1.6] - 1.6) / 0.4, 0, 1)
    return e


def env_exp(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


def fade(x, fin=0.002, fout=0.01):
    x = x.copy()
    a, b = secs(fin), secs(fout)
    if a:
        x[:a] *= np.linspace(0, 1, a)[:, None] if x.ndim == 2 else np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)[:, None] if x.ndim == 2 else np.linspace(1, 0, b)
    return x


def smooth_random(n, rng, rate_hz, lo=0.0, hi=1.0):
    """Slow random curve (random points every 1/rate_hz s, cosine interpolated)."""
    m = max(2, int(n / SR * rate_hz) + 2)
    pts = rng.uniform(lo, hi, m)
    xp = np.linspace(0, n, m)
    i = np.arange(n)
    k = np.clip(np.searchsorted(xp, i) - 1, 0, m - 2)
    u = (i - xp[k]) / (xp[k + 1] - xp[k])
    u = (1 - np.cos(np.pi * u)) / 2
    return pts[k] * (1 - u) + pts[k + 1] * u


# ---------------------------------------------------------------------------- oscillators
def osc(freq, n=None, shape='sine', phase0=0.0):
    """freq: scalar or per-sample array (Hz). shape: sine | saw | square | tri (saw/square are
    soft, few-harmonic versions so they don't alias into fizz)."""
    if np.isscalar(freq):
        freq = np.full(n, float(freq))
    ph = 2 * np.pi * np.cumsum(freq) / SR + phase0
    if shape == 'sine':
        return np.sin(ph)
    if shape == 'saw':
        y = np.zeros_like(ph)
        for k in range(1, 16):
            mask = (freq * k) < SR / 2.5
            y += mask * np.sin(k * ph) / k
        return y * 0.6
    if shape == 'square':
        y = np.zeros_like(ph)
        for k in range(1, 16, 2):
            mask = (freq * k) < SR / 2.5
            y += mask * np.sin(k * ph) / k
        return y * 0.8
    if shape == 'tri':
        return 2 / np.pi * np.arcsin(np.sin(ph))
    raise ValueError(shape)


def glide(f0, f1, n, tau=None):
    """Exponential frequency glide f0 -> f1 (tau = time constant in s, default ~len/4)."""
    t = np.arange(n) / SR
    tau = tau or (n / SR / 4)
    return f1 + (f0 - f1) * np.exp(-t / tau)


def modal(n, rng, freqs, decays, amps=None, jitter=0.01):
    """Struck-metal modal synthesis: sum of decaying sines (inharmonic partials)."""
    y = np.zeros(n)
    t = np.arange(n) / SR
    amps = amps or [1.0 / (i + 1) ** 0.6 for i in range(len(freqs))]
    for f, d, a in zip(freqs, decays, amps):
        f = f * (1 + rng.uniform(-jitter, jitter))
        y += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / d)
    return y


def impulses(n, rng, rate, amp_pow=3.0):
    """Sparse random impulse train (Poisson), rate: per-sample array or scalar (events/s).
    Heavy-tailed amplitudes so a few clicks pop out like real crackle."""
    rate = np.broadcast_to(np.asarray(rate, float), (n,))
    p = np.clip(rate / SR, 0, 1)
    hits = rng.random(n) < p
    y = np.zeros(n)
    k = np.nonzero(hits)[0]
    y[k] = rng.uniform(0.05, 1.0, len(k)) ** amp_pow * rng.choice([-1, 1], len(k))
    return y


def conv(x, ir):
    """FFT convolution, output length len(x) + len(ir) - 1. x mono or (n, c); ir mono."""
    if x.ndim == 2:
        return np.stack([conv(x[:, c], ir) for c in range(x.shape[1])], axis=1)
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:n]


# ---------------------------------------------------------------------------- dynamics/colour
def sat(x, drive=1.5):
    """tanh saturation normalised so small signals keep their level."""
    return np.tanh(x * drive) / np.tanh(drive)


def norm(x, peak_val=0.89):
    m = np.max(np.abs(x)) + 1e-12
    return x * (peak_val / m)


def stereoize(x, rng, width=0.5, delay_ms=(3.0, 11.0)):
    """Mono -> stereo with decorrelating short delays (Haas-like) and a width blend."""
    n = len(x)
    out = np.zeros((n, 2))
    for c in range(2):
        d = secs(rng.uniform(*delay_ms) / 1000)
        wet = np.zeros(n)
        wet[d:] = x[:n - d]
        out[:, c] = x * (1 - width * 0.5) + wet * width * 0.5
    return out


def reverb_ir(dur=1.6, rng=None, predelay=0.012, damp_hz=(5000, 900), early=True, stereo=True):
    """Synthetic outdoor/hall impulse response: early reflections + exponentially decaying,
    progressively darker noise tail (decorrelated per channel)."""
    rng = rng or np.random.default_rng(7)
    n = secs(dur)
    t = np.arange(n) / SR
    chans = []
    for c in range(2 if stereo else 1):
        tail = rng.standard_normal(n) * np.exp(-6.9 * t / dur)
        # darker as it decays
        lo = sweep_lp(tail, damp_hz[0], damp_hz[1], curve='exp')
        ir = np.zeros(n)
        pd = secs(predelay)
        ir[pd:] = lo[:n - pd] * 0.35
        if early:
            for k in range(9):
                d = secs(predelay + rng.uniform(0.008, 0.09))
                ir[d] += rng.uniform(0.15, 0.5) * rng.choice([-1, 1])
        chans.append(ir / (np.sqrt(np.sum(ir ** 2)) + 1e-12))
    return np.stack(chans, axis=1) if stereo else chans[0]


def slapback(x, rng, taps=((0.13, 0.35), (0.29, 0.22), (0.47, 0.12)), lp_hz=1800):
    """Distant valley echoes (the 'trailer boom' rolling reflections)."""
    n = len(x)
    extra = secs(max(t for t, _ in taps) * 1.15) + 1
    y = np.zeros(n + extra)
    y[:n] += x
    dark = lp(x, lp_hz, 2)
    for t, g in taps:
        d = secs(t * rng.uniform(0.9, 1.1))
        y[d:d + n] += dark * g
    return y


def loopify(x, xfade=0.4):
    """Make a seamless loop: crossfade the last `xfade` s into the start; drops that much."""
    k = secs(xfade)
    body = x[:-k].copy()
    w = np.linspace(0, 1, k)
    if x.ndim == 2:
        w = w[:, None]
    body[:k] = body[:k] * w + x[-k:] * (1 - w)
    return body
