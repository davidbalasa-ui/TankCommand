"""Scene 7 (0:42-0:48): exchange of fire. The lines close; gold beams lance out of the crescent and lens,
blue bolts and comets pour back; shields flare, a corvette on each side blows apart. Wide between the
fleets, then low over a Terran ship with the gold beams coming at the camera."""
import random

import bpy

from mathutils import Vector

import v3base as V
from v3base import fr, key_loc
import space as SP
import v3_battle as B

BLUE = (0.35, 0.7, 1.0)
GOLD = (1.0, 0.6, 0.18)
SHIFT_T, SHIFT_A = Vector((70, 0, 0)), Vector((-60, 0, 0))


def build(draft=True):
    sc = V.Scene(6.0, draft)
    sc.env()
    ships = {'bship', 'frigate', 'missile', 'corv0', 'corv1', 'corv2', 'crescent', 'lens', 'acorv0', 'acorv1',
             'acorv2'}
    R = B.Rig(sc, ships, drift=False)
    nf = sc.nf
    rnd = random.Random(7)
    R.terran_shields(('bship', 'frigate', 'missile'), 1)
    R.gold_shields(('crescent', 'lens'), vis=0.35)
    pos = {}
    for k, ob in R.obj.items():
        terran = k in B.HOLD_T
        p = (B.HOLD_T[k] + SHIFT_T) if terran else (B.HOLD_A[k][0] + SHIFT_A)
        d = Vector((1, 0, 0)) if terran else Vector((-1, 0, 0))
        key_loc(ob, [(1, p), (nf, p + d * 70)], 'LINEAR')
        pos[k] = (p, d * 70 / (nf - 1))
        if k == 'bship':
            V.key_rot(ob, [(1, (0, 0, 90)), (nf, (0, 0, 90))])
        else:
            V.engines(ob, f'Eng{k}', BLUE if terran else GOLD, thr_keys=[(1, 1.2), (nf, 1.2)])

    def at(k, f):
        p, v = pos[k]
        return p + v * (f - 1)
    T = [k for k in R.obj if k in B.HOLD_T]
    A = [k for k in R.obj if k not in B.HOLD_T]
    # ---------------------------------------------------------------- every ship on its own weapon rhythm
    import fleet_life as FL
    import terran_fleet as TF
    sc_ = bpy.context.scene
    dead = {'corv2': fr(3.4), 'acorv2': fr(4.3)}
    tgt_of = {}
    for k in T:
        for i_, t_ in enumerate(FL.turrets_of(R.obj[k])):
            tgt_of[(k, i_)] = A[rnd.randrange(len(A))] if k != 'corv2' else 'acorv2'

    def aim(k, i_, f):
        if k in dead and f >= dead[k]:
            return None
        tk = tgt_of[(k, i_)]
        if tk in dead and f >= dead[tk] - 2:
            tk = 'crescent'
        return at(tk, f)
    FL.bake_turrets({k: R.obj[k] for k in T}, 1, nf, aim=aim, seed=17)

    def mounts(k):
        ts = FL.turrets_of(R.obj[k])
        big = [t for t in ts if t['r'] >= 0.3]
        small = [t for t in ts if t['r'] < 0.3]
        rnd.shuffle(small)
        if k == 'bship':
            return [(t, 'heavy') for t in big] + [(t, 'flak') for t in small[:8]]
        if k == 'frigate':
            return [(t, 'cannon') for t in big] + [(t, 'flak') for t in small[:6]]
        if k == 'missile':
            return [(t, 'flak') for t in ts[:3]]
        return [(t, 'flak') for t in ts]
    shots = []
    for k in T:
        for t_, prof in mounts(k):
            i_ = FL.turrets_of(R.obj[k]).index(t_)
            for ts_ in FL.shot_times(prof, 0.2, 5.8, rnd):
                f = fr(ts_)
                if k in dead and f >= dead[k]:
                    continue
                shots.append((f, k, i_, t_, prof))
    shots.sort(key=lambda x: x[0])
    for n_, (f, k, i_, t_, prof) in enumerate(shots):
        sc_.frame_set(f)
        src = FL.muzzle_world(t_, n_)
        tgt = aim(k, i_, f + 8)
        if tgt is None:
            continue
        spread = {'flak': 9, 'cannon': 6, 'heavy': 4}[prof]
        tgt = tgt + Vector((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), rnd.uniform(-spread, spread) * 0.6))
        FL.fire_bolt(src, tgt, f, prof, BLUE, speed={'flak': 520, 'cannon': 420, 'heavy': 300}[prof], seed=n_)
        FL.recoil(t_, f, kick=t_['r'] * (0.7 if prof == 'heavy' else 0.35))
    # missile ship: artillery salvos, 3 missiles in 1 s from alternating tubes, 3 s reload; doors open/close
    ms = R.obj['missile']
    salvos = []
    for ts_ in FL.shot_times('artillery', 0.5, 5.6, rnd, phase=0.0):
        salvos.append(fr(ts_))
    groups = [(salvos[i_], salvos[min(i_ + 2, len(salvos) - 1)]) for i_ in range(0, len(salvos), 3)]
    FL.tube_doors(ms, R.tubes, groups)
    for n_, f in enumerate(salvos):
        sc_.frame_set(f)
        tube = ms.matrix_world @ (R.tubes[n_ % len(R.tubes)] + Vector((1.5, 0, 0)))
        tk = ('crescent', 'lens', 'acorv0')[n_ % 3]
        hit = at(tk, f + 30) + Vector((rnd.uniform(-10, 10), rnd.uniform(-8, 8), rnd.uniform(-5, 5)))
        mo = TF.missile(SP._uid('Msl'), scale=1.6, plume=True)
        mid = tube.lerp(hit, 0.5) + Vector((0, 0, 30 + rnd.uniform(-8, 8)))
        SP.key_loc(mo, [(f, tube), (f + 15, mid), (f + 30, hit)], 'BEZIER')
        mo.rotation_mode = 'QUATERNION'
        for ff, a_, b_ in ((f, tube, mid), (f + 15, mid, hit), (f + 30, mid, hit)):
            mo.rotation_quaternion = SP.aim_quat(b_ - a_, up='Z') if hasattr(SP, 'aim_quat') else mo.rotation_quaternion
            mo.keyframe_insert('rotation_quaternion', frame=ff)
        SP.show(mo, f, f + 30)
        FL.muzzle_flash(tube, (hit - tube).normalized(), f, (1.0, 0.75, 0.4), 1.2)
        SP.boom(hit, f + 30, 7.0, life=0.9, seed=n_)
        SP.impact_flare(hit, (hit - tube).normalized(), f + 30, f + 36, (1.0, 0.7, 0.3), 6.0, SP._uid('MslHit'))
    # Arcadian motherships: lances on their own long rhythm, charge rings spinning up between
    for src_k, ph in (('crescent', 0.1), ('lens', 1.3)):
        for i_, ts_ in enumerate(FL.shot_times('lance', 0.0, 5.6, rnd, phase=ph)):
            f0 = fr(ts_ + 1.6)
            if f0 > nf - 6:
                continue
            tgt_k = T[(i_ * 2 + (0 if src_k == 'crescent' else 1)) % len(T)]
            if tgt_k in dead and f0 >= dead[tgt_k]:
                tgt_k = 'bship'
            src = at(src_k, f0) + Vector((-30, 0, 0))
            tgt = at(tgt_k, f0 + 6) + Vector((0, rnd.uniform(-4, 4), rnd.uniform(-3, 3)))
            d = (tgt - src).normalized()
            L = (tgt - src).length
            FL.charge_rings(src, d, max(1, f0 - 38), f0, f0 + 20, r=7.0, name=f'{src_k}Ring{i_}')
            SP.beam(src, d, f'XBeam{src_k}{i_}', GOLD, (1.0, 0.9, 0.6), 1.3,
                    [(f0, 0.5, 1.0), (f0 + 3, L, 1.0), (f0 + 17, L, 1.05), (f0 + 19, L, 0.0)], strength=18.0, glow=3.0)
            SP.impact_flare(tgt - d * 4, d, f0 + 3, f0 + 17, (1.0, 0.65, 0.25), 7.0, f'XHit{src_k}{i_}')
            SP.spark_stream(tgt - d * 3, f0 + 3, f0 + 17, (1.0, 0.7, 0.3), -d, 400 + i_, n=5, size=0.5, speed=40)
    # Arcadian corvettes: lightning arcs, 3 crackling pulses then recharge
    for k in ('acorv0', 'acorv1', 'acorv2'):
        for i_, ts_ in enumerate(FL.shot_times('arc', 0.3, 5.6, rnd)):
            f = fr(ts_)
            if k in dead and f >= dead[k]:
                continue
            tgt_k = T[rnd.randrange(len(T))]
            if tgt_k in dead and f >= dead[tgt_k]:
                tgt_k = 'frigate'
            src = at(k, f) + Vector((-9, 0, 1.5))
            tgt = at(tgt_k, f + 1) + Vector((rnd.uniform(-5, 5), rnd.uniform(-5, 5), rnd.uniform(-3, 3)))
            SP.flicker_lightning([(src, tgt)], seed=f * 7 + i_, f0=f, f1=f + 3, every=1, width=0.5,
                                 name=SP._uid(f'Arc{k}'), zone_col=(1.0, 0.75, 0.35), strength=22.0)
            SP.impact_flare(tgt, (tgt - src).normalized(), f + 1, f + 5, (1.0, 0.7, 0.3), 4.0, SP._uid('ArcHit'))
    # every hull has its own slow bank / pitch and RCS puffs; Arcadian corvettes have orbiting parts
    for n_, (k, ob) in enumerate(R.obj.items()):
        if k == 'bship':
            continue
        FL.hull_life(ob, 1, nf, seed=50 + n_, roll_deg=2.5 if 'corv' in k else 1.2, pitch_deg=1.0,
                     rcs=k in T, col=(0.8, 0.9, 1.0))
        if k.startswith('acorv'):
            FL.orbiters(ob, 1, nf, seed=60 + n_, n=3)
    # a corvette on each side dies
    for k, t in (('corv2', 3.4), ('acorv2', 4.3)):
        f = fr(t)
        p = at(k, f)
        (SP.blue_boom if k.startswith('c') else SP.gold_boom)(p, f, 14.0, life=1.4, light=4e5)
        SP.boom(p, f + 2, 10.0, life=1.6, follow=Vector((0, 0, 4)), seed=3)
        SP.shards(p, f, 60, (0.4, 0.75, 1.0) if k.startswith('c') else (1.0, 0.7, 0.3), 1.0, 50, seed=f, life=1.8)
        SP.show(R.obj[k], 1, f + 1)
    mid = (at('bship', 1) + at('crescent', 1)) / 2
    sc.shot('A', 1, fr(3.0) - 1,
            [(1, mid + Vector((-20, -330, 60)), mid + Vector((0, 0, 10)), 18),
             (fr(3.0) - 1, mid + Vector((0, -300, 55)), mid + Vector((10, 0, 10)), 19)],
            shake=[(fr(1.0), 0.8, 40)])
    fp = at('frigate', fr(3.0))
    sc.shot('B', fr(3.0), nf,
            [(fr(3.0), fp + Vector((-30, -26, 12)), fp + Vector((200, -40, 30)), 22),
             (nf, at('frigate', nf) + Vector((-26, -24, 11)), at('frigate', nf) + Vector((200, -30, 30)), 22)],
            shake=[(fr(3.4), 3.0, 20), (fr(4.0), 1.5, 30)])
    return sc
