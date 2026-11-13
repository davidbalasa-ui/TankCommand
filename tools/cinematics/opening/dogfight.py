"""Shot 6 of the opening film: dogfight and missiles (0:23 to 0:26), built into the shared space scene.

0:23  ride behind one Twin-X as it dives through the shell ship's wreckage into a Stingray swarm
      (blue bolts out, gold bolts in, gold debris tumbling past)
0:24  it shoots a Stingray apart (gold fireball); the camera lets it go and settles on the missile
      ship, both front tubes firing
0:25  the missiles curve into a Stingray flock and an Arcadian corvette: a line of blasts across the
      screen, the corvette's shield flickering
All paths are computed here and baked to keys (fixed seeds).
"""
import math
import random

import bpy
from mathutils import Vector, Quaternion

import space as SP
import common as C
import arcadian_fleet as AF
import new_pieces as NP
from squid import catmull, bake, look_quat, ramp

fr = SP.fr
FPS = SP.FPS
F0, F1 = fr(23.0), fr(26.0)          # 553, 625
T_SHOT = fr(24.0) - 1                # 576 the Twin-X fires the killing burst
T_KILL = fr(24.0) + 2                # 579 the Stingray blows apart
T_LAUNCH = fr(24.15)                 # first missile
DX_K = 3.6                           # hero fighter drawn a little larger


class Dogfight:
    def __init__(self, S):
        self.S = S
        self.rnd = random.Random(606)
        sc = bpy.context.scene
        sc.frame_set(F0)
        self.W = S.obj['shell'].matrix_world.translation.copy()          # wreck centre
        self.Fc = self.W + Vector((-62, -52, -8))                         # stingray flock centre
        self.frames = list(range(F0 - 12, F1 + 30))
        self.hero()
        self.flock()
        self.missiles()
        S.dogfight_data = self

    # ------------------------------------------------------------ the Twin-X and its victim
    def hero(self):
        S, W, Fc = self.S, self.W, self.Fc
        keys = [(F0 - 12, W + Vector((95, 70, 34))), (F0 + 10, W + Vector((8, 10, 5))),
                (T_SHOT - 4, Fc + Vector((30, 6, 3))), (T_KILL + 8, Fc + Vector((-26, -8, -4))),
                (F1 + 30, Fc + Vector((-190, -60, -20)))]
        self.hx = {f: catmull(keys, f) for f in self.frames}
        c = SP.copy_tree(S.twinx_src, 'DogX')
        for ob in [c] + list(c.children_recursive):
            ob.hide_render = False
        quats, qprev, self.hroll = [], None, {}
        for f in self.frames:
            v = self.hx[min(f + 1, self.frames[-1])] - self.hx[max(f - 1, self.frames[0])]
            roll = math.radians(200) * ramp(f, F0 + 8, F0 + 22) + math.radians(25) * math.sin(f * 0.21)
            self.hroll[f] = roll
            q = look_quat(v) @ Quaternion((1, 0, 0), roll)
            if qprev is not None and q.dot(qprev) < 0:
                q = -q
            quats.append(q)
            qprev = q
        bake(c, self.frames, [self.hx[f] for f in self.frames], quats)
        c.scale = (DX_K,) * 3
        wings = next(ch for ch in c.children if ch.name.startswith(S.twinx_wings))
        wings.rotation_mode = 'XYZ'
        SP.key_rot(wings, [(self.frames[0], (0, 0, 0)), (self.frames[-1], (360 * 7, 0, 0))], 'LINEAR')
        self.dogx = c
        # the doomed stingray, weaving ahead of it
        with AF.gold_palette():
            st, _ = AF.stingray_fighter('DogVictim')
        st.scale = (SP.FIGHTER_K,) * 3
        vk = [(F0 - 12, Fc + Vector((60, 30, 10))), (F0 + 14, Fc + Vector((22, 4, 4))),
              (T_KILL, Fc + Vector((2, -2, 0)))]
        vf = list(range(F0 - 12, T_KILL + 1))
        vl = [catmull(vk, f) for f in vf]
        vq = [look_quat(catmull(vk, f + 1) - catmull(vk, f - 1)) @ Quaternion((1, 0, 0), 0.5 * math.sin(f * 0.3))
              for f in vf]
        bake(st, vf, vl, vq)
        st.scale = (SP.FIGHTER_K,) * 3
        SP.show(st, F0 - 12, T_KILL)
        pk = vl[-1]
        SP.gold_boom(pk, T_KILL, 9.0, life=1.0, light=1.5e5)
        SP.spark_stream(pk, T_KILL, T_KILL + 1, (1.0, 0.7, 0.25), Vector((0, 0, 0)), 620, n=40, size=0.45,
                        speed=55, life=0.9)
        SP.shards(pk, T_KILL, 26, (1.0, 0.65, 0.2), 0.7, 40, seed=621, life=1.2, strength=6.0)
        # blue bolts out of the Twin-X's wing guns (every 3 frames), gold bolts coming back
        bm = SP.emit('DogBoltBlue', (0.35, 0.7, 1.0), 26.0)
        gm = SP.emit('DogBoltGold', (1.0, 0.7, 0.25), 26.0)
        for n_, f in enumerate(range(F0 + 3, T_SHOT + 2, 3)):
            p0 = self.hx[f]
            aim = (pk if f > T_SHOT - 8 else self.hx[min(f + 8, self.frames[-1])]) - p0
            for side in (-1, 1):
                q = look_quat(aim)
                off = q @ Vector((1.0, side * 1.6, 0))
                b = C.uv_sphere(f'DogBolt{n_}_{side}', 1.0, seg=(8, 5), mat=bm, scale=(2.0, 0.09, 0.09))
                b.rotation_mode = 'QUATERNION'
                b.rotation_quaternion = q
                SP.key_loc(b, [(f, p0 + off), (f + 6, p0 + off + aim.normalized() * 70)], 'LINEAR')
                SP.show(b, f, f + 6)
                b.visible_shadow = False
        for n_ in range(9):
            f = F0 + 2 + n_ * 3
            tgt = self.hx[f + 4] + Vector((self.rnd.uniform(-5, 5), self.rnd.uniform(-5, 5), self.rnd.uniform(-3, 3)))
            src = Fc + Vector((self.rnd.uniform(-30, 30), self.rnd.uniform(-30, 30), self.rnd.uniform(-10, 10)))
            d = tgt - src
            b = C.uv_sphere(f'DogGold{n_}', 1.0, seg=(8, 5), mat=gm, scale=(2.2, 0.1, 0.1))
            b.rotation_mode = 'QUATERNION'
            b.rotation_quaternion = look_quat(d)
            SP.key_loc(b, [(f, src + d * 0.6), (f + 6, tgt + d.normalized() * 30)], 'LINEAR')
            SP.show(b, f, f + 6)
            b.visible_shadow = False
        # gold debris tumbling through the hero's path
        for n_ in range(18):
            f = F0 + self.rnd.randint(0, 22)
            p = self.hx[f] + Vector((self.rnd.uniform(-12, 12), self.rnd.uniform(-12, 12), self.rnd.uniform(-6, 6)))
            SP.shards(p, F0 - 12, 1, (0.9, 0.55, 0.15), self.rnd.uniform(0.8, 2.2), 6, seed=640 + n_, life=4.0,
                      strength=1.5)

    # ------------------------------------------------------------ flock and missiles
    def flock(self):
        Fc = self.Fc
        with AF.gold_palette():
            src, _ = AF.stingray_fighter('FlockSrc')
        src.location = (0, 0, -9999)
        src.hide_render = True
        self.flk = []
        for i in range(7):
            s = SP.copy_tree(src, f'Flock{i}')
            for ob in [s] + list(s.children_recursive):
                ob.hide_render = False
            s.scale = (SP.FIGHTER_K,) * 3
            off = Vector((self.rnd.uniform(-22, 22), self.rnd.uniform(-22, 22), self.rnd.uniform(-8, 8)))
            p0 = Fc + off + Vector((-30, -40, 0))
            v = Vector((-1.0, -0.6, 0.05)).normalized() * 40 / FPS
            self.flk.append(dict(obj=s, p0=p0, v=v))
            fs = list(range(F0 - 12, F1 + 30))
            bake(s, fs, [p0 + v * (f - F0) + Vector((0, 0, 2 * math.sin(f * 0.1 + i))) for f in fs],
                 [look_quat(v) @ Quaternion((1, 0, 0), 0.3 * math.sin(f * 0.12 + i)) for f in fs])
            s.scale = (SP.FIGHTER_K,) * 3

    def flock_pos(self, i, f):
        d = self.flk[i]
        return d['p0'] + d['v'] * (f - F0)

    def missiles(self):
        S = self.S
        ms = S.obj['missile_ship']
        sc = bpy.context.scene
        acv = S.obj['acorv1']
        sc.frame_set(T_LAUNCH)
        cv_hit_f = []
        mm = SP.emit('MissileM', (0.85, 0.95, 1.0), 30.0)
        tm = SP.emit('MissileTrailM', (0.25, 0.55, 1.0), 4.0)
        targets = [('flock', 1), ('cv', 0), ('flock', 3), ('cv', 1), ('flock', 5), ('flock', 0), ('cv', 2), ('flock', 6)]
        for k, (kind, idx) in enumerate(targets):
            f0 = T_LAUNCH + 3 * k
            tube = S.tubes[k % 2]
            sc.frame_set(f0)
            p0 = ms.matrix_world @ tube
            fwd = (ms.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
            fl = 16 + (k % 3) * 2
            f1 = f0 + fl
            if kind == 'flock':
                tgt = self.flock_pos(idx, f1)
            else:
                sc.frame_set(f1)
                cen = acv.matrix_world @ (sum((Vector(b) for b in acv.bound_box), Vector()) / 8)
                tgt = cen + Vector(((idx - 1) * 3.0, (idx - 1) * -2.0, 1.5 * idx))
                cv_hit_f.append(f1)
            side = Vector((0, 0, 1)).cross(fwd).normalized()
            c1 = p0 + fwd * 70
            c2 = tgt + (side * (14 if k % 2 else -14)) + Vector((0, 0, 18 * ((k % 3) - 1))) - (tgt - p0).normalized() * 40
            path = [_bez(p0, c1, c2, tgt, i / fl) for i in range(fl + 1)]
            m_ = C.uv_sphere(f'Missile{k}', 1.0, seg=(10, 6), mat=mm, scale=(1.4, 0.28, 0.28))
            frames = list(range(f0, f1 + 1))
            bake(m_, frames, path, [look_quat(path[min(i + 1, fl)] - path[max(i - 1, 0)]) for i in range(fl + 1)])
            m_.scale = (1.4, 0.28, 0.28)
            SP.show(m_, f0, f1)
            m_.visible_shadow = False
            # trail: short glowing segments that linger a few frames each
            for i in range(fl):
                a, b = path[i], path[i + 1]
                seg = C.uv_sphere(f'MTrail{k}_{i}', 1.0, seg=(8, 4), mat=tm)
                seg.location = (a + b) / 2
                seg.rotation_mode = 'QUATERNION'
                seg.rotation_quaternion = look_quat(b - a)
                L = (b - a).length / 2 + 0.6
                SP.key_scale(seg, [(f0 + i, (L, 0.14, 0.14)), (f0 + i + 8, (L, 0.5, 0.5))], 'LINEAR')
                SP.show(seg, f0 + i + 1, f0 + i + 8)
                seg.visible_shadow = False
            # launch flash at the tube, blast at the target
            SP.blue_boom(p0 + fwd * 2, f0, 3.5, life=0.3, light=6e4)
            SP.boom(tgt, f1, 9.0 if kind == 'flock' else 7.0, life=1.0, light=1.2e5)
            SP.spark_stream(tgt, f1, f1 + 1, (1.0, 0.6, 0.2), Vector((0, 0, 0)), 650 + k, n=20, size=0.4,
                            speed=45, life=0.8)
            if kind == 'flock':
                SP.show(self.flk[idx]['obj'], F0 - 12, f1)
        # the corvette's gold shield flickers with each hit
        dx, dy, dz = (v / acv.scale.x for v in acv.dimensions)
        size = (dx * 0.62, dy * 0.7 + 1.5, dz * 0.8 + 1.5)
        sh = NP.shield_dome(size=size, hit=(size[0] * 0.8, -size[1] * 0.3, 0), name='GShield_acorv1')
        sh.scale = size
        sh.parent = acv
        sh.location = sum((Vector(b) for b in acv.bound_box), Vector()) / 8
        m = sh.data.materials[0]
        SP.add_fade(m, 'vis', 0.0)
        keys = [(1, 0.0)]
        for f in cv_hit_f:
            keys += [(f - 1, 0.0), (f, 0.9), (f + 1, 0.2), (f + 2, 0.7), (f + 4, 0.0)]
        SP.key_node(m, 'vis', sorted(keys), 'CONSTANT')
        self.cv_hits = cv_hit_f

    # ------------------------------------------------------------ camera
    def camera(self, sid):
        keys = []
        S = self.S
        sc = bpy.context.scene
        ms = S.obj['missile_ship']
        for f in range(F0, F1, 2):
            if f <= T_SHOT + 2:
                # riding behind and a little above the fighter, rolling with it
                p = self.hx[f]
                v = (self.hx[f + 2] - self.hx[f - 2]).normalized()
                qf = look_quat(v) @ Quaternion((1, 0, 0), self.hroll[f])
                pos = p + qf @ Vector((-16, 0, 3.2))
                tgt = p + qf @ Vector((30, 0, 0))
                keys.append((f, pos, tgt, 22, self.hroll[f]))
            else:
                sc.frame_set(f)
                m = ms.matrix_world.translation
                w = ramp(f, T_SHOT + 2, T_LAUNCH + 8)
                v = (self.hx[T_SHOT + 2] - self.hx[T_SHOT - 2]).normalized()
                qf = look_quat(v) @ Quaternion((1, 0, 0), self.hroll[T_SHOT + 2])
                p_a = self.hx[T_SHOT + 2] + qf @ Vector((-16, 0, 3.2))
                t_a = self.hx[T_SHOT + 2] + qf @ Vector((30, 0, 0))
                p_b = m + Vector((-38, -70, 16))
                t_b = m + Vector((50, 18, 0))
                # then follow the missile stream across the frame toward the flock
                w2 = ramp(f, T_LAUNCH + 10, F1 - 2)
                t_c = self.Fc + Vector((-20, -30, 0))
                p_c = m + Vector((10, -110, 22))
                pos = p_a.lerp(p_b, w).lerp(p_c, w2)
                tgt = t_a.lerp(t_b, w).lerp(t_c, w2)
                roll = self.hroll[T_SHOT + 2] * (1 - w)
                keys.append((f, pos, tgt, 22 + 4 * w, roll))
        keys.append((F1 - 1,) + keys[-1][1:])
        return keys


def _bez(p0, p1, p2, p3, t):
    u = 1 - t
    return p0 * (u ** 3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t ** 3)
