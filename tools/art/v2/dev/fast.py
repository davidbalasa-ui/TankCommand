"""Quick low-quality build for silhouette iteration: python fast.py <asset,...> <outdir>"""
import os, sys, time
sys.path.insert(0, '/home/user/TankCommand/tools/art/v2')
import bpy
import forge as F
_finish, _bake = F.finish, F._bake
def finish(name, glb, **kw):
    kw['size'] = 256; kw['supersample'] = 1; kw['render'] = None
    return _finish(name, glb, **kw)
def bake(obj, kind, size, **kw):
    if kind == 'AO':
        bpy.context.scene.cycles.samples = 6
    return _bake(obj, kind, size, **kw)
F.finish, F._bake = finish, bake
import build
reg = build.registry()
out = sys.argv[2]
for key in sys.argv[1].split(','):
    a = reg[key]; t = time.time()
    glb = os.path.join(out, a['path']); os.makedirs(os.path.dirname(glb), exist_ok=True)
    a['fn'](glb, None, os.path.join(out, 'reports', key + '.json'))
    print('TIME', key, round(time.time() - t))
