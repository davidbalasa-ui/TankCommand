"""Build v2 art assets.

    python build.py <asset[,asset...]|all|terran|kesh|structures|props> [--out DIR] [--renders DIR]

Writes <out>/<path>.glb (same layout as public/assets/models), a preview sheet per asset and a
JSON line with the triangle count in <renders>/reports/.
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def registry():
    reg = {}
    for modname in ('terran_units', 'kesh_units', 'terran_structures', 'kesh_structures', 'props'):
        try:
            mod = __import__(modname)
        except ModuleNotFoundError as e:
            if e.name != modname:
                raise
            continue
        reg.update(mod.ASSETS)
    return reg


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opts = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
    out = opts.get('out', os.path.join(HERE, '..', '..', '..', 'public', 'assets', 'models'))
    renders = opts.get('renders', '/tmp/forge_renders')
    reg = registry()
    want = args[0].split(',') if args else ['all']
    names = []
    for w in want:
        if w == 'all':
            names += list(reg)
        elif w in reg:
            names.append(w)
        else:
            names += [k for k, v in reg.items() if v['set'] == w]
    failed = []
    for key in names:
        a = reg[key]
        glb = os.path.join(out, a['path'])
        os.makedirs(os.path.dirname(glb), exist_ok=True)
        os.makedirs(os.path.join(renders, 'reports'), exist_ok=True)
        try:
            a['fn'](glb, os.path.join(renders, f'{key}.jpg'), os.path.join(renders, 'reports', f'{key}.json'))
        except Exception:
            traceback.print_exc()
            failed.append(key)
    if failed:
        print('FAILED', failed)
        sys.exit(1)


if __name__ == '__main__':
    main()
