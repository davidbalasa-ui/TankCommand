"""Sound for the unit promo clips: event capture + mixer + mux. No scene edits needed.

How it works
  * promo_kit imports this module at its end and calls install(): Promo/Actor methods are wrapped
    (functools.wraps, *args/**kwargs pass-through) so every fire/destroy/explosion/lightning/
    unfold/... call is recorded as a sound event with its time and position. Recording never
    changes what the method does or returns, and any recording error is swallowed (printed once).
  * Continuous beds (engines, hover hums, lifters, jets) are not events: at mix time every actor's
    root is sampled per frame; speed drives each bed's pitch and loudness, acceleration adds
    engine load (revs + level), fast fliers get Doppler, ground vehicles get a separate running-
    gear bed (tracks_loop / tyres_loop) that follows ground speed only, and hard stops get a skid.
    Each unit has its own 'voice' (pitch, variant rotation, tone) hashed from its label.
  * mix(P) builds a 48 kHz stereo mix (panning + distance from the keyed camera, ambience ducked
    under big hits, reverb send, bus glue, loudness to about -14 LUFS, true-peak limiter at
    -1.5 dBFS); mix_and_mux(P, mp4) puts it into the mp4 as AAC 192k (video stream copied).
  * Sounds come from the baked library in $PROMO_SFX (default /mnt/project-files/promos/sfx),
    made by audio/sfx_gen.py (baked automatically if missing).

  * P.shot and the promo_fx_weapons helpers that scenes call directly (W.lightning, W.beam,
    W.missile, W.projectile, W.impact, W.muzzle_flash, W.lightning_thruster) record too
    ('auto' events). An auto event is dropped when the scene already cues the same kind of
    sound itself at that moment (a P.sfx of the same family within ~0.1 s / overlapping a loop),
    so scenes that hand-cued these effects don't get doubled sounds.

Explicit cues from a scene (for effects the scene draws itself, which the wrappers can't see):
  P.sfx(t, 'boom_big', gain=1.0, pos=(x, y, z), dur=None, rate=1.0)
  (name = a library sound, e.g. zap_lightning, servo, thruster_blue; dur for loops; gain linear;
  list: audio/sfx_gen.py or the manifest.json in the library.) Scenes keep them in one block
  just before P.render().

CLI (add sound to an already rendered clip without re-rendering video):
  /home/user/artenv/venv/bin/python tools/promos/promo_audio.py <scene_id> [--mp4 in.mp4] [--out out.mp4]
        [--wav out.wav] [--png spectrogram.png] [--events]
  Default --mp4 is /mnt/project-files/promos/clips/<id>/<id>.mp4 and default --out is
  /mnt/project-files/promos/sound-proof/<id>_sound.mp4 (the original is never overwritten unless
  --out points at it).

PROMO_AUDIO=0 switches the render-time mux off.
"""
import functools
import inspect
import json
import math
import os
import subprocess
import sys
import tempfile
import wave
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(HERE, 'audio')
if AUDIO_DIR not in sys.path:
    sys.path.insert(0, AUDIO_DIR)

SR = 48000
SFX_DIR = os.environ.get('PROMO_SFX', '/mnt/project-files/promos/sfx')
TARGET_LUFS = -14.0
CEILING_DB = -1.5   # sample/4x peak ceiling; AAC (PNS off) adds ~0.2-0.6 dB, checked again after encoding
MAX_GR_DB = 8.0      # most limiting allowed on the loudest hit (more audibly pumps the beds)

if __name__ == '__main__':  # one module instance whether run as a script or imported by the kit
    sys.modules.setdefault('promo_audio', sys.modules[__name__])

_stack = []          # [(method name, bound args dict)] of wrapped calls in progress
_warned = set()
_LAST = {}           # CLI collect mode: the Promo the scene built


def _warn(key, msg):
    if key not in _warned:
        _warned.add(key)
        print(f'[promo_audio] {msg}', file=sys.stderr)


# ===================================================================================== capture
def _vec(p):
    try:
        return tuple(float(c) for c in p)[:3] + (0.0,) * max(0, 3 - len(p))
    except Exception:
        return None


def _pt(P, x, t):
    """World point of an effect endpoint at time t: a point, an Actor (body centre), a bpy Object
    (its world origin) or a callable t -> point. None if it can't be evaluated."""
    v = None
    try:
        if hasattr(x, 'pos_at') and hasattr(x, 'root'):
            v = _vec(x.pos_at(t))
        elif callable(x):
            v = _vec(x(t))
        elif hasattr(x, 'matrix_world'):
            import bpy
            sc = bpy.context.scene
            cur = sc.frame_current
            f = int(round(1 + t * P.fps))
            if f != cur:
                sc.frame_set(f)
            v = _vec(x.matrix_world.translation)
            if f != cur:
                sc.frame_set(cur)
        else:
            v = _vec(x)
    except Exception:
        v = None
    return v


def _is_point(x):
    return not (callable(x) or hasattr(x, 'matrix_world') or hasattr(x, 'root')) and _vec(x) is not None


def _events(P):
    ev = getattr(P, '_audio_events', None)
    if ev is None:
        ev = P._audio_events = []
    return ev


def _bind(orig, self, a, k):
    try:
        b = inspect.signature(orig).bind(self, *a, **k)
        b.apply_defaults()
        d = dict(b.arguments)
        d.pop('self', None)
        if 'kwargs' in d and isinstance(d['kwargs'], dict):
            d.update(d.pop('kwargs'))
        return d
    except Exception:
        return dict(k)


def _wrap(cls, name, rec):
    orig = cls.__dict__.get(name)
    if orig is None or getattr(orig, '_audio_wrapped', False):
        return
    if not callable(orig):
        return

    @functools.wraps(orig)
    def w(self, *a, **k):
        args = _bind(orig, self, a, k)
        parents = list(_stack)
        _stack.append((name, args))
        try:
            res = orig(self, *a, **k)
        finally:
            _stack.pop()
        try:
            rec(self, args, res, parents)
        except Exception as e:  # recording must never break a render
            _warn(name, f'could not record {name}: {e!r}')
        return res

    w._audio_wrapped = True
    w._audio_orig = orig
    setattr(cls, name, w)


_FIRE_LIKE = ('fire', 'shot', 'W.shot')   # weapon calls whose sub-effects are voiced by the call itself


def _fire_like(par):
    return any(n in _FIRE_LIKE for n in par)


def _parent_names(parents):
    return [n for n, _ in parents]


def _P(obj):
    return getattr(obj, 'P', obj)


def _add(obj, kind, t, parents, **kw):
    P = _P(obj)
    e = dict(kind=kind, t=float(t), parents=_parent_names(parents), **kw)
    # remember what the outermost fire() was shooting with (impact sound choice)
    for n, a in parents:
        if n in _FIRE_LIKE:
            e['fire_kind'] = a.get('kind', 'cannon')
            e['fire_target_actor'] = hasattr(a.get('target'), 'root')
    _events(P).append(e)
    return e


def _r_env(P, a, res, parents):
    P._audio_env = a.get('kind', 'desert')


def _r_space(P, a, res, parents):
    P._audio_env = 'space'


def _r_explosion(P, a, res, parents):
    _add(P, 'explosion', a['t'], parents, pos=_vec(a['pos']), size=float(a.get('size', 2.0)))


def _r_impact(P, a, res, parents):
    _add(P, 'impact', a['t'], parents, pos=_vec(a['pos']), size=float(a.get('size', 1.0)),
         color=_vec(a['color']) if a.get('color') is not None else None)


def _r_lightning(P, a, res, parents):
    # endpoints may be points, Actors, Objects or callables: evaluate at the strike time (an
    # unreadable end falls back to the other one)
    t0 = float(a['t0'])
    p0, p1 = _pt(P, a['p0'], t0), _pt(P, a['p1'], t0)
    p0 = p0 or p1 or (0.0, 0.0, 0.0)
    p1 = p1 or p0
    mid = tuple((x + y) / 2 for x, y in zip(p0, p1))
    # moving ends used to fail to record (no sound): scenes may have cued those themselves
    auto = not (_is_point(a['p0']) and _is_point(a['p1']))
    _add(P, 'lightning', t0, parents, pos=mid, p1=p1, dur=float(a['t1']) - t0,
         length=math.dist(p0, p1), width=float(a.get('width', 0.05) or 0.05), auto=auto)


def _r_beam(P, a, res, parents):
    t0 = float(a['t0'])
    p0, p1 = _pt(P, a['p0'], t0), _pt(P, a['p1'], t0)
    _add(P, 'beam', t0, parents, pos=p1 or p0, p0=p0 or p1, dur=float(a['t1']) - t0,
         color=_vec(a['color']), auto=not (_is_point(a['p0']) and _is_point(a['p1'])))


def _r_missile(P, a, res, parents):
    _add(P, 'missile', a['t0'], parents, pos=_vec(a['p0']), t_hit=float(res) if res is not None else None)


def _r_projectile(P, a, res, parents):
    _add(P, 'projectile', a['t0'], parents, pos=_vec(a['p0']), speed=float(a.get('speed', 60)),
         size=float(a.get('size', 0.15)), color=_vec(a['color']) if a.get('color') is not None else None)


def _r_muzzle_flash(P, a, res, parents):
    mo = a.get('muzzle_obj')
    pos = _vec(mo.matrix_world.translation) if mo is not None else None
    _add(P, 'muzzle', a['t'], parents, pos=pos, color=_vec(a['color']) if a.get('color') is not None else None,
         size=float(a.get('size', 1.0)))


def _r_light(P, a, res, parents):
    _add(P, 'light', a['t'], parents, pos=_vec(a['pos']), color=_vec(a['color']),
         energy=float(a.get('energy', 2000)), dur=float(a.get('dur', 0.2)))


def _r_cam_shake(P, a, res, parents):
    _add(P, 'shake', a['t'], parents, amount=float(a.get('amount', 0.15)), dur=float(a.get('dur', 0.4)))


def _r_shield(P, a, res, parents):
    _add(P, 'shield', a['t0'], parents, pos=_vec(a['center']), dur=float(a['t1']) - float(a['t0']),
         radius=float(a.get('radius', 4)))


def _r_fire_patch(P, a, res, parents):
    _add(P, 'burn', a['t0'], parents, pos=_vec(a['pos']), dur=float(a['t1']) - float(a['t0']),
         size=float(a.get('size', 0.6)))


def _r_shot(P, a, res, parents):
    """P.shot / W.shot: the weapon sound at the origin (like Actor.fire); its tracer, beam,
    lightning and impact record themselves beneath it (the impact keeps its own sound)."""
    t = float(a['t'])
    kind = a.get('kind', 'cannon')
    src = a.get('src', a.get('p0'))
    if isinstance(src, tuple) and len(src) == 2 and not isinstance(src[0], (int, float)):
        host, off = src
        ob = host.root if hasattr(host, 'root') else host
        pos = None
        try:
            import bpy
            from mathutils import Vector
            sc = bpy.context.scene
            cur = sc.frame_current
            sc.frame_set(int(round(1 + t * P.fps)))
            pos = _vec(ob.matrix_world @ Vector(off))
            sc.frame_set(cur)
        except Exception:
            pos = None
    else:
        pos = _pt(P, src.root if hasattr(src, 'root') and not hasattr(src, 'pos_at') else src, t)
    dur = a.get('dur')
    _add(P, 'shot', t, parents, pos=pos, weapon=kind, size=float(a.get('size', 1.0) or 1.0),
         t_hit=float(res) if res is not None else None, dur=float(dur) if dur else None,
         color=_vec(a['color']) if a.get('color') is not None else None, auto=True)


def _r_thruster(P, a, res, parents):
    obj = a.get('obj')
    ob = obj.root if hasattr(obj, 'root') else obj
    t0, t1 = float(a['t0']), float(a['t1'])
    _add(P, 'thruster', t0, parents, pos=_pt(P, ob, (t0 + t1) / 2), dur=t1 - t0,
         host=getattr(ob, 'name', '?'), auto=True)


def _auto(rec):
    """Recorder variant for the direct W.* helpers: its events are marked auto (see build)."""
    def r(P, a, res, parents):
        ev = _events(P)
        n = len(ev)
        rec(P, a, res, parents)
        for e in ev[n:]:
            e['auto'] = True
    return r


def _wrap_fn(mod, name, rec, only_top=False):
    """Wrap module function mod.<name> (first arg P). It records only when called straight from
    a scene, or under P.shot / W.shot (whose sub-effects the kit methods' wrappers never see);
    inside any other recorded call (P.lightning -> W.lightning, Actor.fire -> W.beam, ...) the
    outer call already carries the sound. only_top: record only when nothing is in progress."""
    orig = mod.__dict__.get(name)
    if orig is None or getattr(orig, '_audio_wrapped', False) or not callable(orig):
        return None
    tag = 'W.' + name.lstrip('_')

    @functools.wraps(orig)
    def w(P, *a, **k):
        args = _bind(orig, P, a, k)
        parents = list(_stack)
        on = (not parents) if only_top else all(n in _FIRE_LIKE for n, _ in parents)
        _stack.append((tag, args))
        try:
            res = orig(P, *a, **k)
        finally:
            _stack.pop()
        if on:
            try:
                rec(P, args, res, parents)
            except Exception as e:  # recording must never break a render
                _warn(tag, f'could not record {tag}: {e!r}')
        return res

    w._audio_wrapped = True
    w._audio_orig = orig
    setattr(mod, name, w)
    return w


def _install_weapons():
    """Record the promo_fx_weapons helpers scenes call directly (and P.shot's sub-effects)."""
    try:
        import promo_fx_weapons as W
    except Exception as e:  # bpy-less tooling: nothing to wrap
        _warn('wfx', f'promo_fx_weapons not wrapped: {e!r}')
        return
    if getattr(W, '_audio_installed', False) or not callable(W.__dict__.get('shot')):
        return      # (half-imported module: promo_fx_weapons installs itself when it finishes)
    for n, r in [('lightning', _auto(_r_lightning)), ('beam', _auto(_r_beam)), ('missile', _auto(_r_missile)),
                 ('projectile', _auto(_r_projectile)), ('muzzle_flash', _auto(_r_muzzle_flash)),
                 ('impact', _auto(_r_impact)), ('lightning_thruster', _r_thruster)]:
        _wrap_fn(W, n, r)
    _wrap_fn(W, 'shot', _r_shot, only_top=True)
    # W.shot calls its impact through the module alias _impact
    if getattr(W.impact, '_audio_wrapped', False):
        W._impact = W.impact
    W._audio_installed = True


def _r_load(P, a, res, parents):
    if res is not None and hasattr(res, 'root'):
        res._audio_model = a.get('name')


def _r_copy(P, a, res, parents):
    if res is not None and hasattr(res, 'root'):
        res._audio_model = getattr(a.get('actor'), '_audio_model', None)
        if getattr(a.get('actor'), '_audio_hover', False):
            res._audio_hover = True


def _r_fire(A, a, res, parents):
    _add(A, 'fire', a['t'], parents, actor=A, weapon=a.get('kind', 'cannon'), size=float(a.get('size', 1.0) or 1.0),
         t_hit=float(res) if res is not None else None)


def _r_destroy(A, a, res, parents):
    _add(A, 'destroy', a['t'], parents, actor=A, size=float(a.get('size') or A.size * 0.5))


def _r_unfold(A, a, res, parents):
    _add(A, 'unfold', a['t0'], parents, actor=A, t1=float(a['t1']))


def _r_spin(A, a, res, parents):
    t1 = a.get('t1')
    t1 = A.P.seconds if t1 is None else t1
    if A.parts.get(a.get('part')) is None:
        return
    _add(A, 'spin', a.get('t0', 0.0), parents, actor=A, part=str(a.get('part')), rate=float(a.get('rate_deg_s', 360)),
         dur=float(t1) - float(a.get('t0', 0.0)))


def _r_aim(A, a, res, parents):
    if not getattr(A, 'turret', None):
        return
    dur = float(a.get('dur', 0.35) or 0.35)
    _add(A, 'aim', float(a['t']) - dur, parents, actor=A, dur=dur)


def _r_hover(A, a, res, parents):
    A._audio_hover = True


def sfx(self, t, name, gain=1.0, pos=None, dur=None, rate=1.0):
    """Explicit sound cue: library sound `name` at time t (seconds). gain is linear; pos a world
    point (None = centred, no distance falloff); dur for looping sounds; rate = pitch/speed.
    Unknown names (not in the library's manifest.json) print a warning: they stay silent."""
    lib = None
    try:      # only read an existing library here (never bake from a cue)
        if _manifest is not None or os.path.exists(os.path.join(SFX_DIR, 'manifest.json')):
            lib = _lib()
    except Exception:
        lib = None
    if lib is not None and name not in lib and ('sfx_unknown', name) not in _warned:
        _warned.add(('sfx_unknown', name))
        import difflib
        near = difflib.get_close_matches(str(name), list(lib), n=3, cutoff=0.5)
        print(f'[promo_audio] WARNING: P.sfx({t}, {name!r}): no such sound in '
              f'{os.path.join(SFX_DIR, "manifest.json")} - this cue will be SILENT.'
              + (f' Did you mean: {", ".join(near)}?' if near else ''), file=sys.stderr)
    _events(self).append(dict(kind='sfx', t=float(t), name=name, gain=float(gain), pos=_vec(pos) if pos is not None else None,
                              dur=dur, rate=float(rate), parents=[]))
    return self


def install(kit):
    """Wrap the kit's methods (idempotent)."""
    Promo, Actor = kit.Promo, kit.Actor
    if getattr(Promo, '_audio_installed', False):
        return
    for n, r in [('env', _r_env), ('space', _r_space), ('explosion', _r_explosion), ('impact', _r_impact),
                 ('lightning', _r_lightning), ('beam', _r_beam), ('missile', _r_missile),
                 ('projectile', _r_projectile), ('muzzle_flash', _r_muzzle_flash), ('light', _r_light),
                 ('cam_shake', _r_cam_shake), ('shield_dome', _r_shield), ('fire_patch', _r_fire_patch),
                 ('load', _r_load), ('copy', _r_copy)]:
        _wrap(Promo, n, r)
    for n, r in [('fire', _r_fire), ('destroy', _r_destroy), ('unfold', _r_unfold), ('spin', _r_spin),
                 ('aim', _r_aim), ('hover_bob', _r_hover)]:
        _wrap(Actor, n, r)
    _wrap(Promo, 'shot', _r_shot)
    _install_weapons()
    if 'sfx' not in Promo.__dict__:
        Promo.sfx = sfx
    _wrap_render(Promo)
    Promo._audio_installed = True


def _wrap_render(Promo):
    orig = Promo.__dict__.get('render')
    if orig is None or getattr(orig, '_audio_wrapped', False):
        return

    @functools.wraps(orig)
    def render(self, *a, **k):
        if os.environ.get('PROMO_AUDIO_COLLECT'):
            # CLI collect mode: the scene is fully built; stash it and skip the image render.
            _LAST['P'] = self
            return None
        return orig(self, *a, **k)

    render._audio_wrapped = True
    Promo.render = render


# ===================================================================================== library
_cache = {}
_manifest = None


def _lib():
    global _manifest
    if _manifest is None:
        mp = os.path.join(SFX_DIR, 'manifest.json')
        if not os.path.exists(mp):
            print('[promo_audio] sound library missing: baking it (one-off, ~30 s)', file=sys.stderr)
            import sfx_gen
            sfx_gen.bake(out=SFX_DIR)
        _manifest = json.load(open(mp))
    return _manifest


def load(name, variant):
    files = _lib()[name]['files']
    fn = files[variant % len(files)]
    if fn not in _cache:
        with wave.open(os.path.join(SFX_DIR, fn)) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
            _cache[fn] = x.reshape(-1, w.getnchannels())
    return _cache[fn]


def is_loop(name):
    return _lib()[name].get('loop', False)


def n_variants(name):
    return len(_lib()[name]['files'])


# ===================================================================================== scene sampling
def _sample(P):
    """Per-frame camera pose and actor root positions/visibility."""
    import bpy
    sc = bpy.context.scene
    nf = int(P.nf)
    cam = getattr(P, 'cam', None) or sc.camera
    acts = [a for a in getattr(P, 'actors', []) if a.entry.get('kind') != 'prop']
    S = dict(nf=nf, cam_pos=np.zeros((nf, 3)), cam_rot=np.tile(np.eye(3), (nf, 1, 1)),
             apos={}, avis={}, actors=acts)
    for a in acts:
        S['apos'][id(a)] = np.zeros((nf, 3))
        S['avis'][id(a)] = np.ones(nf, bool)
    cur = sc.frame_current
    for i in range(nf):
        sc.frame_set(i + 1)
        if cam is not None:
            mw = cam.matrix_world
            S['cam_pos'][i] = tuple(mw.translation)
            m3 = mw.to_3x3().normalized()
            S['cam_rot'][i] = np.array([[m3[r][c] for c in range(3)] for r in range(3)])
        for a in acts:
            S['apos'][id(a)][i] = tuple(a.model_root.matrix_world.translation)
            vis = not (a.root.hide_render or a.model_root.hide_render)
            S['avis'][id(a)][i] = vis
    sc.frame_set(cur)
    if cam is None:
        S['cam_pos'][:] = (0, -25, 6)
    return S


def _at_frame(arr, t, fps):
    i = int(round(t * fps))
    return arr[min(max(i, 0), len(arr) - 1)]


# ===================================================================================== spatialisation
REF_DIST = 9.0


def _spatial(S, pos, fps, t, rolloff=0.85):
    """(gain, pan[-1..1], cutoff_hz, behind) of a static source at time t. rolloff: distance
    exponent (big sounds carry: explosions use a softer law)."""
    if pos is None:
        return 1.0, 0.0, 20000.0, False
    c = _at_frame(S['cam_pos'], t, fps)
    R = _at_frame(S['cam_rot'], t, fps)
    rel = np.asarray(pos, float) - c
    d = float(np.linalg.norm(rel)) + 1e-6
    right = R[:, 0]
    fwd = -R[:, 2]
    pan = float(np.dot(rel, right) / d)
    front = float(np.dot(rel, fwd) / d)
    g = (REF_DIST / max(d, REF_DIST)) ** rolloff
    cutoff = float(np.clip(20000 * (REF_DIST * 1.5 / max(d, REF_DIST * 1.5)) ** 0.9, 2500, 20000))
    if front < -0.2:
        cutoff = min(cutoff, 7000)
    return g, float(np.clip(pan * 0.8, -0.8, 0.8)), cutoff, front < -0.2


def _spatial_track(S, P_pos, fps, rolloff=0.65):
    """Per-frame gain/pan/cutoff for a moving source (P_pos: (nf, 3)). Beds fall off more gently
    than one-shots: an engine 30 m away is still part of the picture."""
    rel = P_pos - S['cam_pos']
    d = np.linalg.norm(rel, axis=1) + 1e-6
    right = S['cam_rot'][:, :, 0]
    fwd = -S['cam_rot'][:, :, 2]
    pan = np.einsum('ij,ij->i', rel, right) / d
    front = np.einsum('ij,ij->i', rel, fwd) / d
    g = (REF_DIST / np.maximum(d, REF_DIST)) ** rolloff
    cutoff = np.clip(20000 * (REF_DIST * 1.5 / np.maximum(d, REF_DIST * 1.5)) ** 0.9, 2500, 20000)
    cutoff = np.where(front < -0.2, np.minimum(cutoff, 7000), cutoff)
    return g, np.clip(pan * 0.8, -0.8, 0.8), cutoff, d


def _pan_gains(pan):
    a = (np.asarray(pan) + 1) * np.pi / 4
    return np.cos(a) * np.sqrt(2) * 0.85, np.sin(a) * np.sqrt(2) * 0.85  # equal power, 0.85 at centre


def _lp1(x, fc):
    """One-pole lowpass (2 poles) on a stereo buffer, static cutoff."""
    if fc >= 19000:
        return x
    import dsp
    return dsp.lp(x.astype(np.float64), fc, 2)


def _resample(x, rate):
    if abs(rate - 1.0) < 1e-3:
        return x
    n = int(len(x) / rate)
    src = np.arange(n) * rate
    i = np.arange(len(x))
    return np.stack([np.interp(src, i, x[:, c]) for c in range(x.shape[1])], axis=1).astype(np.float32)


# ===================================================================================== mixer
class Mix:
    def __init__(self, P, S):
        self.P = P
        self.S = S
        self.fps = P.fps
        self.dur = P.nf / P.fps
        self.n = int(round(self.dur * SR))
        self.bus = {b: np.zeros((self.n, 2), np.float32) for b in ('amb', 'bed', 'fx', 'hit')}
        self.rng = np.random.default_rng(sum(map(ord, P.id)))
        self.rr = {}
        self.log = []

    def variant(self, name):
        k = self.rr.get(name)
        if k is None:
            k = int(self.rng.integers(0, 64))
        self.rr[name] = k + 1 + int(self.rng.integers(0, 2))
        return k

    def voice(self, key):
        """Stable per-unit voice from its label: (rate, variant offset, darkness 0..0.6). Two units
        with the same weapon get a different pitch/size, their own variant rotation and EQ."""
        h = zlib.crc32(str(key).encode())
        rate = 0.91 + 0.18 * ((h & 0xFF) / 255.0)
        dark = 0.6 * (((h >> 8) & 0xFF) / 255.0) ** 1.5
        return rate, (h >> 16) & 0xFF, dark

    def place(self, name, t, gain_db=0.0, pos=None, bus='fx', rate=1.0, dur=None, gain_min=0.1, var=None,
              fade_out=0.05, width=1.0, voice=None):
        """One-shot (or a loop for `dur` s) at time t, spatialised at pos at time t. voice: a unit
        label; its sounds get that unit's own pitch, variant rotation and tone, plus a small
        per-shot pitch jitter so bursts don't machine-gun."""
        dark = 0.0
        if voice is not None:
            vr, off, dark = self.voice(voice)
            rate = rate * vr * float(self.rng.uniform(0.975, 1.025))
            if var is None:
                k = (name, voice)
                c = self.rr.get(k, off)
                self.rr[k] = c + 1
                var = c
        try:
            x = load(name, self.variant(name) if var is None else var)
        except KeyError:
            _warn('nosound' + name, f'no library sound {name!r}')
            return
        if dark > 0.05:
            x = (x * (1 - dark) + _lp1(x, 3500).astype(np.float32) * dark).astype(np.float32)
        if dur is not None and is_loop(name):
            x = self._loop(x, dur * rate + 0.05)
        x = _resample(x, rate)
        if dur is not None:
            m = int((dur + fade_out) * SR)
            x = x[:m].copy()
            k = min(len(x), int(fade_out * SR))
            if k > 1:
                x[-k:] *= np.linspace(1, 0, k)[:, None]
            k = min(len(x), int(0.01 * SR))
            x[:k] *= np.linspace(0, 1, k)[:, None]
        g, pan, cutoff, _ = _spatial(self.S, pos, self.fps, t, 0.5 if bus == 'hit' else 0.85)
        g = max(g, gain_min)
        if cutoff < 19000:
            x = _lp1(x, cutoff).astype(np.float32)
        gl, gr = _pan_gains(pan)
        if width < 1:
            mono = x.mean(axis=1, keepdims=True)
            x = x * width + mono * (1 - width)
        amp = 10 ** (gain_db / 20) * g
        i0 = int(round(t * SR))
        if i0 < 0:
            x = x[-i0:]
            i0 = 0
        m = min(len(x), self.n - i0)
        if m <= 0:
            return
        self.bus[bus][i0:i0 + m, 0] += x[:m, 0] * amp * gl
        self.bus[bus][i0:i0 + m, 1] += x[:m, 1] * amp * gr
        self.log.append((round(t, 3), name, round(gain_db + 20 * math.log10(max(g, 1e-6)), 1), bus))

    def _loop(self, x, dur):
        need = int(dur * SR) + 1
        reps = need // len(x) + 1
        return np.tile(x, (reps, 1))[:need]

    def bed(self, name, gain, pan, cutoff, rate, t0=0.0, gain_db=0.0, bus='bed', var=None):
        """Continuous loop with per-frame gain/pan/cutoff/rate arrays (len nf)."""
        x = load(name, self.variant(name) if var is None else var)
        nf = self.S['nf']
        fr = np.arange(self.n) / SR * self.fps
        fi = np.clip(fr, 0, nf - 1)
        idx = np.arange(nf)
        g = np.interp(fi, idx, gain)
        p = np.interp(fi, idx, pan)
        r = np.interp(fi, idx, rate)
        c = np.interp(fi, idx, cutoff)
        # read position follows the playback rate (pitch + speed)
        start = self.rng.uniform(0, len(x) - 1)
        pos = (start + np.cumsum(r)) % (len(x) - 1)
        i0 = pos.astype(int)
        fr_ = (pos - i0)[:, None]
        y = x[i0] * (1 - fr_) + x[i0 + 1] * fr_
        # distance darkening: blend with a lowpassed copy
        dark = _lp1(y, 1800).astype(np.float32)
        wdark = np.clip((20000 - c) / 17500, 0, 1)[:, None]
        y = y * (1 - wdark) + dark * wdark
        gl, gr = _pan_gains(p)
        amp = 10 ** (gain_db / 20) * g
        y[:, 0] *= amp * gl
        y[:, 1] *= amp * gr
        self.bus[bus] += y.astype(np.float32)
        self.log.append((t0, name + ' (bed)', round(gain_db + 20 * math.log10(max(float(np.max(g)), 1e-6)), 1), bus))


# ------------------------------------------------------------------------------------- faction
ARC_STRUCTURES = {'sentinel', 'corona', 'oracle', 'metal_siphon', 'aerie', 'star_vault', 'landing_ring',
                  'shard', 'shard_spire'}


def actor_faction(a, clip_id):
    f = a.entry.get('file', '')
    model = getattr(a, '_audio_model', '') or ''
    if f.startswith('alien/') or model.startswith('arcadian_') or model in ARC_STRUCTURES:
        return 'arc'
    if f.startswith('human/') or model.startswith('terran_'):
        return 'terran'
    if f.startswith('structures/') or f.startswith('fleet/'):
        return 'arc' if clip_id.startswith('arcadian') else 'terran'
    return 'arc' if clip_id.startswith('arcadian') else 'terran'


def clip_faction(P):
    return 'arc' if P.id.startswith('arcadian') else ('fleet' if P.id.startswith('fleet') else 'terran')


def _is_gold(c):
    return c is not None and c[0] > 0.8 and 0.25 < c[1] < 0.75 and c[2] < 0.3


def _is_blue(c):
    return c is not None and c[2] > c[0] + 0.2


def _is_green(c):
    return c is not None and c[1] > c[0] + 0.3 and c[1] > c[2] + 0.2


def _db(x):
    return 20 * math.log10(max(x, 1e-6))


# ------------------------------------------------------------------------------------- rules
# sounds that count as "the same cue" when an auto event yields to a scene's own P.sfx
SFX_FAMILY = dict(zap_lightning='zap', zap_small='zap', impact_gold='impact', impact_energy='impact',
                  impact_metal='impact', impact_dirt='impact', shield_hit='impact', crackle_loop='crackle',
                  beam_start='beam', beam_blue_loop='beam_loop', tractor_loop='beam_loop',
                  shot_cannon='shot', shot_heavy='shot', shot_autocannon='shot', shot_laser='shot',
                  shot_missile='shot', shot_shell='shot', shot_bomb='shot',
                  boom_small='boom', boom_med='boom', boom_big='boom')

FIRE_SOUND = dict(cannon=('shot_cannon', 0.0), heavy=('shot_heavy', 1.0), autocannon=('shot_autocannon', -4.0),
                  laser=('shot_laser', -2.0), missile=('shot_missile', -2.0), shell=('shot_shell', 0.0),
                  lightning=('zap_lightning', -1.0), beam=('beam_start', -2.0), bomb=('shot_bomb', -4.0))


def build(P, S):
    M = Mix(P, S)
    fps = P.fps
    ev = sorted(_events(P), key=lambda e: e['t'])

    def apos(a, t):
        p = _at_frame(S['apos'].get(id(a), np.zeros((S['nf'], 3))), t, fps)
        return tuple(p)

    # ---- ambience
    envk = getattr(P, '_audio_env', None) or getattr(P, 'env_kind', None) or 'desert'
    amb = 'amb_' + envk
    if amb not in _lib():
        amb = 'amb_desert'
    nf = S['nf']
    M.bed(amb, np.ones(nf), np.zeros(nf), np.full(nf, 20000.0), np.ones(nf), gain_db=-19.0, bus='amb')

    # ---- engine / hover beds from sampled motion
    beds = []
    for a in S['actors']:
        pos = S['apos'][id(a)]
        vis = S['avis'][id(a)].astype(float)
        if vis.max() == 0:
            continue
        kind = a.entry.get('kind')
        model = getattr(a, '_audio_model', '') or a.name
        f = actor_faction(a, P.id)
        vel = np.gradient(pos, axis=0) * fps
        # big jumps (teleports / hidden placement) are not motion
        spd = np.linalg.norm(vel, axis=1)
        spd = np.where(spd > 80, 0, spd)
        spd = np.convolve(spd, np.ones(5) / 5, mode='same')
        try:
            gz = np.array([P.ground_z(float(x), float(y)) for x, y, _ in pos[::12]])
        except Exception:
            gz = np.zeros(len(pos[::12]))
        alt = float(np.median(pos[::12, 2] - gz))
        moving = spd.max() > 0.8
        air = alt > 2.5
        hover = getattr(a, '_audio_hover', False)
        if kind == 'structure' and not moving:
            continue
        if kind == 'ship' or a.entry.get('file', '').startswith('fleet/'):
            name, vref, idle, r0, r1 = ('ship_arc' if f == 'arc' else 'ship_terran'), 30, 0.7, 0.9, 1.15
        elif f == 'arc':
            if air and 'dragonfly' in model:
                name, vref, idle, r0, r1 = 'wings_arc', 25, 0.7, 0.9, 1.2
            else:
                name, vref, idle, r0, r1 = 'hover_arc', 14, 0.65, 0.92, 1.12
        else:
            if air or any(k in model for k in ('falcon', 'condor')):
                name, vref, idle, r0, r1 = 'jet_terran', 30, 0.6, 0.85, 1.2
            elif hover:
                name, vref, idle, r0, r1 = 'hover_terran', 14, 0.6, 0.9, 1.2
            elif model in ('outrider', 'skimmer', 'watchman'):
                name, vref, idle, r0, r1 = 'eng_wheeled', 16, 0.35, 0.8, 1.45
            else:
                name, vref, idle, r0, r1 = 'eng_tracked', 10, 0.35, 0.8, 1.35
        s = np.clip(spd / vref, 0, 1)
        if kind == 'structure':
            idle = 0.0  # a structure on the move (rolling in packed) is silent once it stops
        gain_lin = (idle + (1 - idle) * s) * vis
        # short fades on visibility changes
        gain_lin = np.convolve(gain_lin, np.ones(3) / 3, mode='same')
        rate = r0 + (r1 - r0) * s
        g, pan, cut, d = _spatial_track(S, pos, fps)
        g = np.maximum(g, 0.06)
        size_db = 3.0 * math.log2(max(a.size, 1.0) / 4.5)
        hero = P.id.split('_', 1)[-1]
        if model == hero or model == P.id or model.startswith(hero):
            size_db += 5.0  # the clip's star unit is mixed forward
        loud = float(np.max(g * gain_lin))
        # engine load: pulling away revs up and gets louder, coasting/braking drops off
        acc = np.gradient(spd) * fps
        acc = np.where(np.abs(acc) > 60, 0, acc)
        acc = np.convolve(acc, np.ones(7) / 7, mode='same')
        load = np.clip(acc / (vref * 0.8), -1, 1)
        if name.startswith('eng_'):
            rate = rate * (1 + 0.07 * load)
            gain_lin = gain_lin * 10 ** (np.where(load > 0, 3.5, 2.0) * load / 20)
        # Doppler on fast movers (cuts excluded): fly-bys bend down in pitch as they pass
        vrad = np.gradient(d) * fps
        vrad = np.where(np.abs(vrad) > 150, 0, vrad)
        vrad = np.convolve(vrad, np.ones(5) / 5, mode='same')
        if air or kind == 'ship':
            rate = rate * np.clip(343.0 / (343.0 + 1.6 * vrad), 0.8, 1.25)
        beds.append((loud, a, name, g * gain_lin, pan, cut, rate, size_db, d, spd, air, g * vis))
        # hard braking from speed: tracks/tyres skid (the kit's dust ring has no sound of its own)
        if name in ('eng_tracked', 'eng_wheeled') and kind != 'ship':
            # a real stop: from a good clip down to a crawl inside ~0.6 s; the skid sits on the
            # hardest deceleration of that window
            w = int(0.6 * fps)
            i = w
            while i < nf:
                if spd[i] < 0.12 * vref and spd[i - w:i].max() > 0.5 * vref and vis[i - w:i + 1].min() > 0:
                    j = i - w + int(np.argmin(acc[i - w:i + 1]))
                    if any(e.get('kind') == 'sfx' and e.get('name') == 'skid' and abs(e['t'] - j / fps) < 0.4
                           for e in ev):
                        i += int(1.5 * fps)
                        continue  # the scene cued this one itself
                    M.place('skid', j / fps - 0.1, -9.0 + size_db * 0.5, tuple(pos[j]), voice=a.name, gain_min=1.0)
                    i += int(1.5 * fps)
                i += 1
    beds.sort(key=lambda b: -b[0])
    nb = max(1, len(beds))
    for k, (loud, a, name, g, pan, cut, rate, size_db, d, spd, air, gpos) in enumerate(beds[:8]):
        crowd = -10 * math.log10(max(1, min(nb, 6)) ** 0.5)  # many units: each a bit quieter
        vr, voff, _ = M.voice(a.name)
        gdb = -18.0 + size_db + crowd - (3.0 if k >= 3 else 0.0)
        M.bed(name, g, pan, cut, rate * (0.5 + 0.5 * vr), gain_db=gdb, var=voff)
        # running gear is its own layer: it follows ground speed only (silent at a standstill)
        gear = {'eng_tracked': ('tracks_loop', 8.0), 'eng_wheeled': ('tyres_loop', 14.0)}.get(name)
        if gear:
            sg = np.clip(spd / gear[1], 0, 1.3)
            M.bed(gear[0], gpos * sg, pan, cut, (0.7 + 0.45 * np.clip(sg, 0, 1)) * (0.5 + 0.5 * vr),
                  gain_db=gdb + 1.0, var=voff)
        # close, fast fly-bys get a whoosh centred on the closest approach
        if air:
            dm = d.copy()
            for i in range(1, nf - 1):
                if dm[i] < dm[i - 1] and dm[i] <= dm[i + 1] and dm[i] < 12 and spd[i] > 6:
                    M.place('whoosh', i / fps - 0.6, -6.0 - 0.5 * dm[i], tuple(S['apos'][id(a)][i]), rate=1.0, gain_min=1.0)
            M.log.append((0.0, f'  [{a.name}: min dist {d.min():.1f} m, max speed {spd.max():.1f} m/s]', 0.0, '-'))

    # ---- one-shot events
    seen_strike = []
    in_space = getattr(P, "_audio_env", "") == "space"
    cues = [e for e in ev if e['kind'] == 'sfx']

    def cued(name, t, dur=None, tol=0.12):
        """The scene cues this kind of sound itself around t (or over the loop t..t+dur)."""
        fam = SFX_FAMILY.get(name, name)
        a0, a1 = t - tol, t + (dur or 0.0) + tol
        for c in cues:
            if SFX_FAMILY.get(c['name'], c['name']) != fam:
                continue
            c0 = c['t']
            c1 = c0 + float(c.get('dur') or 0.0)
            if c0 <= a1 and c1 >= a0:
                return True
        return False

    def put(e, name, t, *a, **k):
        """M.place for an event; auto events yield to the scene's own cue of the same sound."""
        if e.get('auto') and cued(name, t, k.get('dur')):
            M.log.append((round(t, 3), name + ' (auto, scene cues it)', 0.0, '-'))
            return
        M.place(name, t, *a, **k)

    def near_strike(t, tol=0.07):
        return any(abs(t - u) < tol for u in seen_strike)

    for e in ev:
        k = e['kind']
        t = e['t']
        par = e.get('parents', [])
        if k == 'fire':
            a = e['actor']
            wk = e.get('weapon', 'cannon')
            name, gdb = FIRE_SOUND.get(wk, ('shot_cannon', 0.0))
            gdb += 0.5 * _db(e.get('size', 1.0))
            p = apos(a, t)
            M.place(name, t, gdb, p, bus='hit' if wk in ('heavy', 'shell', 'cannon') else 'fx', voice=a.name)
            if wk == 'lightning':
                seen_strike.append(t)
        elif k == 'shot':
            # P.shot: voiced like Actor.fire, at the origin (sub-effects record beneath it)
            wk = e.get('weapon', 'cannon')
            name, gdb = FIRE_SOUND.get(wk, ('shot_cannon', 0.0))
            gdb += 0.5 * _db(e.get('size', 1.0))
            put(e, name, t, gdb, e.get('pos'), bus='hit' if wk in ('heavy', 'shell', 'cannon') else 'fx',
                gain_min=0.15)
            if wk == 'lightning':
                seen_strike.append(t)
                if (e.get('dur') or 0.18) > 0.25:
                    put(e, 'crackle_loop', t, -9.0, e.get('pos'), dur=e['dur'], gain_min=0.15)
        elif k == 'thruster':
            # lightning thrusters: one quiet crackle per host (several thrusters on a ship merge)
            if any(o is not e and o['kind'] == 'thruster' and o.get('host') == e.get('host')
                   and o['t'] <= t and o['t'] + o['dur'] >= t and ev.index(o) < ev.index(e) for o in ev):
                continue
            put(e, 'crackle_loop', t, -20.0, e.get('pos'), dur=e['dur'], gain_min=0.1)
        elif k == 'explosion':
            s = e['size'] * (1.3 if 'destroy' in par else 1.0)
            name, gdb = ('boom_big', 3.0) if s >= 2.4 else (('boom_med', 2.0) if s >= 1.3 else ('boom_small', 0.0))
            rate = float(np.clip(1.12 - 0.06 * s, 0.82, 1.1))
            M.place(name, t, gdb, e['pos'], bus='hit', rate=rate, gain_min=0.35)
        elif k == 'destroy':
            M.place('debris_metal', t + 0.04, -5.0, apos(e['actor'], t), bus='fx', gain_min=0.2, voice=e['actor'].name)
        elif k == 'impact':
            c = e.get('color')
            size = max(0.3, min(2.5, e.get('size', 1.0)))
            gdb = -4.0 + 12 * math.log10(size)
            if 'shield_dome' in par:
                put(e, 'shield_hit', t, -1.0, e['pos'], gain_min=0.3)
            elif _is_gold(c):
                put(e, 'impact_gold', t, gdb, e['pos'], gain_min=0.15)
                seen_strike.append(t)
            elif _is_blue(c) or _is_green(c):
                put(e, 'impact_energy', t, gdb, e['pos'], rate=1.15 if _is_green(c) else 1.0, gain_min=0.15)
            else:
                fk = e.get('fire_kind')
                if (e.get('fire_target_actor') and fk not in ('shell', 'bomb', 'missile')) or in_space:
                    put(e, 'impact_metal', t, gdb, e['pos'], gain_min=0.15)  # (no dirt in space)
                else:
                    put(e, 'impact_dirt', t, gdb, e['pos'], gain_min=0.15)
                if fk in ('shell', 'bomb', 'missile', 'heavy') or size >= 1.5:
                    put(e, 'boom_small', t, gdb - 2, e['pos'], bus='hit', gain_min=0.2)
        elif k == 'lightning':
            if _fire_like(par):
                continue
            dur = e['dur']
            # a looping bolt (thruster lightning re-issued every second) continues, it doesn't re-strike
            cont = any(o is not e and o['kind'] == 'lightning' and abs(o['t'] + o['dur'] - t) < 0.06
                       and np.linalg.norm(np.subtract(o['pos'], e['pos'])) < 4.0 for o in ev)
            if cont or dur >= 0.9:   # (a second-long bolt is a sustained effect: thrusters, tethers)
                put(e, 'crackle_loop', t, -12.0, e['pos'], dur=dur, gain_min=0.15)
                continue
            if dur < 0.12 and e.get('length', 5) < 6:
                put(e, 'zap_small', t, -9.0, e['pos'], gain_min=0.1)
            else:
                if not near_strike(t, 0.04):
                    if not (e.get('auto') and cued('zap_lightning', t)):
                        M.place('zap_lightning', t, -2.0, e.get('p1') or e['pos'], gain_min=0.2)
                    seen_strike.append(t)
                if dur > 0.25:
                    put(e, 'crackle_loop', t, -9.0, e['pos'], dur=dur, gain_min=0.15)
                if dur >= 0.25 and e.get('length', 0) >= 6:  # a long fat bolt: add a beam-like whomp
                    put(e, 'beam_start', t, -5.0, e.get('p1') or e['pos'], rate=0.8, gain_min=0.2)
        elif k == 'beam':
            gold = _is_gold(e.get('color'))
            if not _fire_like(par):
                put(e, 'beam_start', t, -3.0, e['pos'], rate=0.85 if gold else 1.1, gain_min=0.2)
            elif 'fire' not in par and e['dur'] < 0.25:
                continue   # a P.shot laser zap: its shot sound carries it (as Actor.fire's lasers)
            put(e, 'crackle_loop' if gold else 'beam_blue_loop', t, -6.0, e['pos'], dur=e['dur'], gain_min=0.2)
        elif k == 'missile':
            if _fire_like(par):
                continue
            put(e, 'shot_missile', t, -4.0, e['pos'], gain_min=0.15)
        elif k == 'projectile':
            if _fire_like(par) or 'missile' in par or 'W.missile' in par:
                continue
            if e['speed'] >= 100:
                put(e, 'shot_autocannon', t, -9.0, e['pos'], rate=1.08, gain_min=0.08)
            else:
                put(e, 'shot_cannon', t, -5.0, e['pos'], gain_min=0.12)
        elif k == 'muzzle':
            if _fire_like(par):
                continue
            gun = any(abs(o['t'] - t) < 0.03 and o['kind'] == 'projectile' for o in ev if o is not e)
            # Terran orange and Arcadian gold are nearly the same colour: an orange flash with a
            # tracer is a gun, and in a Terran clip a bare orange flash is a launcher tube
            arc_clip = P.id.startswith(('arcadian', 'fleet_arcadian', 'world'))
            if gun:
                continue  # the tracer's own event already carries the shot
            if _is_gold(e.get('color')) and not gun and arc_clip:
                put(e, 'zap_lightning', t, 0.0 + 6 * math.log10(max(e.get('size', 1.0), 0.2)), e['pos'], gain_min=0.25)
                seen_strike.append(t)
            elif _is_gold(e.get('color')) and not gun:
                put(e, 'shot_missile', t, -4.0, e['pos'], gain_min=0.15)
            else:
                put(e, 'shot_autocannon', t, -6.0, e['pos'], gain_min=0.15)
        elif k == 'light':
            if par or not _is_gold(e.get('color')):
                continue
            if e['energy'] < 2500:
                # small gold light right after a scene-built strike: where the bolt lands
                if near_strike(t, 0.06):
                    M.place('impact_gold', t + 0.01, -5.0, e['pos'], gain_min=0.15)
                continue
            # scene-built gold strikes (custom bolts) announce themselves with a gold light
            if any(abs(o['t'] - t) < 0.07 and o['kind'] in ('lightning', 'impact', 'fire', 'beam')
                   for o in ev if o is not e):
                continue
            if near_strike(t, 0.07):
                continue
            seen_strike.append(t)
            gdb = 0.0 if e['energy'] >= 8000 else -5.0
            M.place('zap_lightning', t, gdb, e['pos'], gain_min=0.25)
            if e['dur'] > 0.25:
                M.place('crackle_loop', t, gdb - 8, e['pos'], dur=e['dur'], gain_min=0.2)
        elif k == 'shake':
            amt = e['amount']
            if amt < 0.04:
                continue
            gdb = float(np.clip(_db(amt / 0.25) * 0.8, -14, 1.0))
            M.place('sub_boom', t, gdb - 5.0 - (4.0 if amt < 0.1 else 0.0), None, bus='hit', width=0.3)
            # a jolt with nothing exploding nearby is a landing/slam: add a heavy suspension thud
            if not in_space and not any(abs(o['t'] - t) < 0.12 and o['kind'] in ('explosion', 'impact', 'fire', 'light',
                                                                                    'lightning', 'destroy')
                                        for o in ev if o is not e):
                M.place('mech_clunk', t, gdb - 1.0, None, rate=0.7, width=0.5)
                M.place('impact_dirt', t + 0.01, gdb - 4.0, None, rate=0.8, width=0.6)
        elif k == 'shield':
            M.place('shield_loop', t, -14.0, e['pos'], dur=e['dur'], gain_min=0.2)
        elif k == 'burn':
            pass  # collected below (only the nearest few)
        elif k == 'unfold':
            a = e['actor']
            p = apos(a, t)
            t1 = e['t1']
            span = max(0.2, t1 - t)
            if actor_faction(a, P.id) == 'arc':
                M.place('zap_small', t, -6.0, p, voice=a.name)
                M.place('crackle_loop', t, -14.0, p, dur=span, voice=a.name)
                M.place('servo', t + span * 0.1, -12.0, p, voice=a.name, rate=0.75)
                M.place('mech_clunk', t1 - 0.02, -8.0, p, voice=a.name, rate=0.8)
                M.place('power_up_arc', t1 - 0.05, -4.0, p, voice=a.name)
            else:
                M.place('mech_clunk', t, -5.0, p, voice=a.name)
                M.place('hydraulic', t + 0.06, -12.0, p, voice=a.name)
                for i, u in enumerate((0.05, 0.35, 0.62)):
                    M.place('servo', t + span * u, -14.0 - i, p, voice=a.name, rate=0.85 + 0.1 * i)
                M.place('hydraulic', t1 - 0.25, -14.0, p, voice=a.name)
                M.place('mech_clunk', t1 - 0.03, -3.0, p, voice=a.name)
                M.place('mech_clunk', t1 + 0.1, -8.0, p, voice=a.name, rate=1.2)
                M.place('power_up_terran', t1 + 0.05, -10.0, p, voice=a.name)
        elif k == 'spin':
            part = e['part'].lower()
            p = apos(e['actor'], t)
            if 'turret' in part or 'wheel' in part:
                continue
            rate = float(np.clip(abs(e['rate']) / 400.0, 0.75, 1.35))
            if 'drum' in part or 'grind' in part or 'drill' in part:
                M.place('grind_loop', t, -14.0, p, rate=rate, dur=e['dur'], voice=e['actor'].name)
            else:
                M.place('whirr_loop', t, -20.0, p, rate=rate, dur=e['dur'], voice=e['actor'].name)
        elif k == 'aim':
            rate = float(np.clip(0.5 / max(e['dur'], 0.1), 0.8, 1.4))
            M.place('turret_servo', t, -17.0, apos(e['actor'], t), rate=rate, voice=e['actor'].name)
        elif k == 'sfx':
            name = e['name']
            M.place(name, t, _db(e['gain']), e['pos'], dur=e.get('dur'), rate=e.get('rate', 1.0),
                    gain_min=0.2 if e['pos'] is not None else 1.0)

    burns = [e for e in ev if e['kind'] == 'burn']
    burns.sort(key=lambda e: -_spatial(S, e['pos'], fps, e['t'])[0])
    for e in burns[:2]:
        M.place('fire_loop', e['t'], -13.0 + 6 * math.log10(max(e['size'], 0.2) / 0.6), e['pos'], dur=e['dur'], gain_min=0.1)
    return M


# ===================================================================================== master
def _kweight(x):
    try:
        from scipy.signal import lfilter
    except Exception:
        return x
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745483398, 0.99007225036621]
    return lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)


def lufs(x):
    """Integrated loudness (BS.1770, gated) of a stereo buffer at 48 kHz."""
    y = _kweight(x.astype(np.float64))
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    ms = []
    for i in range(0, max(1, len(y) - blk + 1), hop):
        ms.append(np.sum(np.mean(y[i:i + blk] ** 2, axis=0)))
    ms = np.array(ms) + 1e-12
    L = -0.691 + 10 * np.log10(ms)
    g = ms[L > -70]
    if len(g) == 0:
        return -70.0
    rel = -0.691 + 10 * np.log10(np.mean(g)) - 10
    g2 = ms[(L > -70) & (L > rel)]
    return float(-0.691 + 10 * np.log10(np.mean(g2 if len(g2) else g)))


def true_peak(x):
    try:
        from scipy.signal import resample_poly
        y = resample_poly(x, 4, 1, axis=0)
    except Exception:
        y = x
    return float(np.max(np.abs(y)))


def _envelope(x, attack, release):
    """Peak envelope follower on |x| (mono), block-wise for speed."""
    a = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    B = 64
    nb = (len(a) + B - 1) // B
    pk = np.array([a[i * B:(i + 1) * B].max() for i in range(nb)])
    env = np.zeros(nb)
    ca = math.exp(-B / (attack * SR))
    cr = math.exp(-B / (release * SR))
    e = 0.0
    for i, v in enumerate(pk):
        e = v + (e - v) * (ca if v > e else cr)
        env[i] = e
    return np.repeat(env, B)[:len(a)]


def limiter(x, ceiling, look=0.003, release=0.12):
    """Look-ahead peak limiter (gain computed on a 4x oversampled peak estimate)."""
    try:
        from scipy.signal import resample_poly
        os4 = np.abs(resample_poly(x, 4, 1, axis=0)).max(axis=1)
        pk = os4[: len(x) * 4].reshape(-1, 4).max(axis=1)
    except Exception:
        pk = np.abs(x).max(axis=1)
    req = np.minimum(1.0, ceiling / np.maximum(pk, 1e-9))
    L = max(1, int(look * SR))
    # forward-looking minimum over the look-ahead window
    try:
        from scipy.ndimage import minimum_filter1d
        gmin = minimum_filter1d(req, size=2 * L + 1, mode='nearest')
    except Exception:
        gmin = req
    # release smoothing (block-wise), attack already handled by the window
    B = 32
    nb = (len(gmin) + B - 1) // B
    blocks = np.array([gmin[i * B:(i + 1) * B].min() for i in range(nb)])
    cr = math.exp(-B / (release * SR))
    out = np.empty(nb)
    g = 1.0
    for i, v in enumerate(blocks):
        g = v if v < g else v + (g - v) * cr
        out[i] = g
    gs = np.repeat(out, B)[:len(x)]
    # smooth the steps (moving average over the look-ahead) without exceeding the requirement
    k = np.ones(L) / L
    gs = np.minimum(np.convolve(gs, k, mode='same'), gs)
    y = x * gs[:, None]
    return np.clip(y, -ceiling, ceiling), gs


def master(M):
    import dsp
    amb, bed, fx, hit = (M.bus[b].astype(np.float64) for b in ('amb', 'bed', 'fx', 'hit'))
    if os.environ.get('PROMO_AUDIO_STEMS'):  # debug: raw bus stems for analysis
        for nm, x in (('amb', amb), ('bed', bed), ('fx', fx), ('hit', hit)):
            write_wav(os.path.join(os.environ['PROMO_AUDIO_STEMS'], f'{M.P.id}_{nm}.wav'), x * 0.5)
    # sidechain: ambience and beds duck under big hits
    key = _envelope(hit + 0.5 * fx, 0.005, 0.45)
    ref = np.percentile(key, 99.5) + 1e-9
    duck = 1.0 / (1.0 + 2.2 * (key / ref) ** 1.2)            # up to ~ -10 dB under the biggest hits
    duck_bed = 1.0 / (1.0 + 1.0 * (key / ref) ** 1.2)
    dry = amb * duck[:, None] + bed * duck_bed[:, None] + fx + hit
    # reverb send (shots/hits ring out over the landscape; space gets a shorter, darker tail)
    space = getattr(M.P, '_audio_env', '') == 'space'
    ir = dsp.reverb_ir(1.1 if space else 1.7, np.random.default_rng(3), damp_hz=(4000, 600) if space else (5500, 800))
    send = (fx + hit * 0.7 + bed * 0.15)
    send = dsp.hp(send, 180, 2)
    wet = np.stack([dsp.conv(send[:, c], ir[:, c])[:len(send)] for c in range(2)], axis=1)
    mix = dry + wet * (0.10 if space else 0.14)
    mix = dsp.hp(mix, 30, 2)
    # low band (<110 Hz): soft-saturated rather than limited. Sub peaks stop pumping the whole
    # mix, and the harmonics the saturation adds are what makes booms audible on phone speakers.
    lo = dsp.lp(dsp.lp(mix, 110, 2), 110, 2)
    hi = mix - lo
    lo_ceiling = np.percentile(np.abs(lo), 99.5) * 0.45 + 1e-9
    lo = lo_ceiling * np.tanh(lo / lo_ceiling)
    mix = lo + hi
    # band-limit like the AAC encoder will (it cuts ~16-17 kHz): otherwise its lowpass makes the
    # sharp cracks ring over the limiter's ceiling after encoding
    mix = dsp.lp(dsp.hp(mix, 32, 2), 15500, 4)
    mix = mix - 0.3 * dsp.lp(mix, 60, 2)  # ~-3 dB shelf under 60 Hz: subs eat headroom, phones can't play them
    # hit compressor on only the loudest moments (above a high percentile of the envelope), so the
    # limiter has less to do and the beds between hits are untouched. Sparse clips (one big slam
    # in a quiet scene) can't reach the loudness target that way, so the compressor gets firmer
    # step by step until the loudness lands within ~1.5 dB of the target.
    env = _envelope(mix, 0.012, 0.25)
    ceiling = 10 ** (CEILING_DB / 20)
    pre = mix
    for pct, ratio in ((95, 3.0), (90, 4.0), (80, 5.0), (65, 6.0)):
        thr = np.percentile(env, pct) * 0.8 + 1e-9
        over = np.maximum(env / thr, 1.0)
        mix = pre * (over ** (1 / ratio - 1))[:, None]
        # loudness -> target, then limit; iterate to make up what the limiter took
        gain = 10 ** ((TARGET_LUFS - lufs(mix)) / 20)
        for _ in range(4):
            out, gr = limiter(mix * gain, ceiling)
            L = lufs(out)
            worst = _db(float(gr.min()))
            if worst < -MAX_GR_DB:  # don't squash the hits flat for the last dB of loudness
                gain *= 10 ** ((worst + MAX_GR_DB) / 20)
                out, gr = limiter(mix * gain, ceiling)
                L = lufs(out)
                break
            if abs(L - TARGET_LUFS) < 0.4:
                break
            gain *= 10 ** ((TARGET_LUFS - L) / 20)
        if L > TARGET_LUFS - 1.5:
            break
    # clip-edge fades: no click at the cut in / out
    a, b = int(0.004 * SR), int(0.03 * SR)
    out[:a] *= np.linspace(0, 1, a)[:, None]
    out[-b:] *= np.linspace(1, 0, b)[:, None]
    M.stats = dict(lufs=round(lufs(out), 2), true_peak_db=round(_db(true_peak(out)), 2),
                   max_gr_db=round(_db(float(gr.min())), 2), duck_min_db=round(_db(float(duck.min())), 2),
                   comp=f'{ratio:g}:1 above p{pct}')
    return out


def mix(P):
    S = _sample(P)
    M = build(P, S)
    out = master(M)
    return out, M


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def measure(path):
    """(integrated LUFS, true peak dBTP) of a file's audio, measured by ffmpeg's ebur128."""
    r = subprocess.run(['ffmpeg', '-nostats', '-i', path, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    tail = r[r.rfind('Summary'):]
    I = tp = None
    for line in tail.splitlines():
        line = line.strip()
        if line.startswith('I:'):
            I = float(line.split()[1])
        if line.startswith('Peak:'):
            tp = float(line.split()[1])
    return I, tp


def mux(video, wav, out, max_tp=-1.0):
    """Mux wav into video as AAC 192k. Perceptual noise substitution and intensity stereo are
    off: these sounds are mostly shaped, decorrelated noise, and both tools replace it with
    generic/mono noise (duller, narrower, and up to +2 dB peak errors after decoding).
    The decoded true peak is measured; the audio is pulled down and re-encoded if over max_tp."""
    tmp = out + '.tmp.mp4'
    src = wav
    for _ in range(3):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', src, '-map', '0:v:0', '-map', '1:a:0',
                        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-aac_pns', '0', '-aac_is', '0', '-ar', str(SR), '-shortest',
                        '-movflags', '+faststart', tmp], check=True)
        I, tp = measure(tmp)
        if tp is None or tp <= max_tp:
            break
        with wave.open(src) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64).reshape(-1, 2) / 32768
        src = wav[:-4] + '_tp.wav'
        write_wav(src, x * 10 ** ((max_tp - 0.1 - tp) / 20))
    os.replace(tmp, out)
    print(f'[promo_audio] {os.path.basename(out)}: {I} LUFS, true peak {tp} dBTP (AAC 192k)')
    return out


def mix_and_mux(P, mp4, out=None, wav=None):
    """Mix the clip's sound and mux it into `mp4` (in place unless `out`). Never raises: a
    sound failure must not cost a render."""
    if os.environ.get('PROMO_AUDIO', '1') == '0':
        return None
    try:
        audio, M = mix(P)
        with tempfile.TemporaryDirectory(prefix='promo_audio_') as tmp:
            wav = wav or os.path.join(tmp, P.id + '.wav')
            write_wav(wav, audio)
            res = mux(mp4, wav, out or mp4)
        print('PROMO_AUDIO', res, M.stats)
        return res
    except Exception as e:  # pragma: no cover
        import traceback
        traceback.print_exc()
        _warn('mux', f'sound mix failed for {getattr(P, "id", "?")}: {e!r}')
        return None


# ===================================================================================== CLI
def collect(scene_id):
    """Build a scene without rendering and return its Promo (events recorded)."""
    import runpy
    path = scene_id if scene_id.endswith('.py') else os.path.join(HERE, 'scenes', scene_id + '.py')
    os.environ['PROMO_AUDIO_COLLECT'] = '1'
    tmp = tempfile.mkdtemp(prefix='promo_audio_scene_')
    argv = sys.argv
    sys.argv = [path, '--no-render', '--quality', 'preview', '--out', tmp]
    try:
        runpy.run_path(path, run_name='__main__')
    finally:
        sys.argv = argv
        os.environ.pop('PROMO_AUDIO_COLLECT', None)
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    P = _LAST.get('P')
    if P is None:
        raise RuntimeError(f'{scene_id}: the scene never called P.render()')
    return P


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Add sound to a promo clip (no video re-render).')
    ap.add_argument('scene')
    ap.add_argument('--mp4', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--wav', default=None)
    ap.add_argument('--png', default=None, help='spectrogram/waveform PNG of the mix (event marks in red)')
    ap.add_argument('--events', action='store_true', help='print the placed sound cues')
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    P = collect(a.scene)
    audio, M = mix(P)
    cid = P.id
    tmpd = tempfile.TemporaryDirectory(prefix='promo_audio_')
    wav = a.wav or os.path.join(tmpd.name, cid + '.wav')
    write_wav(wav, audio)
    print('stats', M.stats)
    if a.events:
        for row in sorted(M.log):
            print('  %6.3f  %-26s %6.1f dB  %s' % row)
    mp4 = a.mp4 or f'/mnt/project-files/promos/clips/{cid}/{cid}.mp4'
    if os.path.exists(mp4):
        out = a.out or f'/mnt/project-files/promos/sound-proof/{cid}_sound.mp4'
        os.makedirs(os.path.dirname(out), exist_ok=True)
        mux(mp4, wav, out)
        print('wrote', out)
    else:
        print('no video at', mp4, '- audio only' + (f': {wav}' if a.wav else ' (pass --wav to keep it)'))
    if a.png:
        import sfx_report
        marks = sorted({round(r[0], 3) for r in M.log if r[3] == 'hit'})
        sfx_report.clip_png(wav, a.png, marks, seconds=P.nf / P.fps)
        print('wrote', a.png)
    tmpd.cleanup()


if __name__ == '__main__':
    main()
