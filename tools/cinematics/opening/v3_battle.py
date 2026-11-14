"""The fleet stand-off used by v3 scenes 3-7: both fleets at their holding positions, static apart from a
slow drift, plus the v2 beam / shield / gun machinery from space.Space re-timed onto a scene's own clock.

    R = Rig(sc, ships={'dread', 'bship', 'shell', ...})
    R.beam(F_GLOW, F_BEAM, F_BREAK, F_EXIT, F_OFF)     # the gold beam on the Terran flagship
"""
import math

import bpy
from mathutils import Vector

import v3base as V
import space as SP
import arcadian_fleet as AF

DREAD_YAW = SP.DREAD_YAW
HOLD_T = {
    'dread': Vector((-150, 0, 18)), 'bship': Vector((-135, -70, -4)), 'frigate': Vector((-170, 62, 6)),
    'missile': Vector((-190, 120, -14)), 'corv0': Vector((-120, 34, 30)), 'corv1': Vector((-118, -36, 34)),
    'corv2': Vector((-125, 95, 26)), 'corv3': Vector((-128, -110, 22)),
}
HOLD_A = {'crescent': (Vector((390, 30, 70)), 2.6, 180), 'shell': (Vector((300, -70, 10)), 1.4, 171),
          'lens': (Vector((420, 150, 90)), 1.8, 180),
          'acorv0': (Vector((330, 40, 30)), 1.0, 180), 'acorv1': (Vector((315, -90, 18)), 1.0, 180),
          'acorv2': (Vector((300, 140, 6)), 1.0, 180)}


class Rig(SP.Space):
    """Borrows Space's methods without its global-clock build."""

    def __init__(self, sc, ships, shields_on=1, drift=True):
        self.sc = sc
        self.sh = sc.sh
        self.draft = sc.draft
        self.obj = {}
        self.tsh = {}
        self.gsh = {}
        SP.NF = sc.nf
        o = self.obj
        nf = sc.nf
        if 'dread' in ships:
            o['dread'], _ = V.terran_ship('dread')
            SP.key_rot(o['dread'], [(1, (0, 0, DREAD_YAW)), (nf, (0, 0, DREAD_YAW))])
        for k, kind in (('bship', 'bship'), ('frigate', 'frigate'), ('missile', 'missile')):
            if k in ships:
                o[k], extra = V.terran_ship(kind)
                if k == 'bship':
                    self.muzzles = extra
                if k == 'missile':
                    self.tubes = extra
        cv = None
        for i in range(4):
            if f'corv{i}' in ships:
                if cv is None:
                    cv, _ = V.terran_ship('corvette')
                    o[f'corv{i}'] = cv
                else:
                    o[f'corv{i}'] = V.copy_tree(cv, f'TCorv{i}')
        for k, ob in o.items():
            if k in HOLD_T:
                p = HOLD_T[k]
                SP.key_loc(ob, [(1, p), (nf, p + Vector((6, 0, 0)) if drift else p)], 'LINEAR')
        with AF.gold_palette():
            if 'crescent' in ships:
                o['crescent'], _ = AF.crescent_mothership_v2()
            if 'shell' in ships:
                o['shell'], _ = AF.shell_mothership_v2()
            if 'lens' in ships:
                o['lens'], _ = AF.lens_mothership_v2()
            ac = None
            for i in range(3):
                if f'acorv{i}' in ships:
                    if ac is None:
                        ac, _ = AF.arcadian_corvette()
                        o[f'acorv{i}'] = ac
                    else:
                        o[f'acorv{i}'] = V.copy_tree(ac, f'ACorv{i}')
        for k, (p, s, yaw) in HOLD_A.items():
            if k in o:
                ob = o[k]
                ob.scale = (s,) * 3
                SP.key_loc(ob, [(1, p), (nf, p - Vector((5, 0, 0)) if drift else p)], 'LINEAR')
                SP.key_rot(ob, [(1, (0, 0, yaw)), (nf, (0, 0, yaw))])
        if 'shell' in o:
            self.shell_tip_local = max((v.co for v in o['shell'].data.vertices), key=lambda c: c.x).copy()
        bpy.context.view_layer.update()
        self.shields_on = shields_on

    def terran_shields(self, keys=('bship', 'frigate', 'missile'), f_on=1):
        for k in keys:
            if k in self.obj:
                self.tsh[k] = V.terran_shield(self.obj[k], f'TSh_{k}', f_on, flicker=False)

    def gold_shields(self, keys=('crescent', 'shell', 'lens'), vis=0.45):
        import new_pieces as NP
        for k in keys:
            if k not in self.obj:
                continue
            ob = self.obj[k]
            dx, dy, dz = (v / ob.scale.x for v in ob.dimensions)
            size = (dx * 0.62, dy * 0.66 + 2, dz * 0.7 + 2)
            cen = sum((Vector(b) for b in ob.bound_box), Vector()) / 8
            hitp = (size[0] * 0.9, -size[1] * 0.3, size[2] * 0.2)
            sh = NP.shield_dome(size=size, hit=hitp, name=f'GShield_{k}')
            sh.scale = size
            sh.parent = ob
            sh.location = cen
            m = sh.data.materials[0]
            SP.add_fade(m, 'vis', vis)
            self.gsh[k] = sh

    def beam(self, f_glow, f_beam, f_break, f_exit, f_off):
        """The gold beam from the shell ship's hook onto the Terran flagship (v2 code, re-timed)."""
        self.F_GLOW, self.F_BEAM, self.F_BREAK, self.F_EXIT, self.F_OFF = f_glow, f_beam, f_break, f_exit, f_off
        self.F_CUT = f_break - 12
        self.beam_geom()
        ob = self.obj['dread']
        dims = Vector(ob.dimensions) / ob.scale.x
        size = (dims.x * 0.62, dims.y * 0.75 + 2.5, dims.z * 1.0 + 2.5)
        cen = sum((Vector(b) for b in ob.bound_box), Vector()) / 8
        sh = SP.tshield('TShield_dread', size, hit=self.dread_hit_u, hit2=self.dread_hit2_u)
        sh.parent = ob
        sh.scale = size
        sh.location = cen
        SP.shield_on(sh, 1, flicker=False)
        self.tsh['dread'] = sh
        self.flagship_beam()
