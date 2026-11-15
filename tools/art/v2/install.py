"""Copy built models into public/assets and refresh their sizes in the manifest.

    python install.py <build dir>     (the --out directory given to build.py)
Then run `npm run credits`.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
src = sys.argv[1]
man_path = os.path.join(ROOT, 'public', 'assets', 'manifest.json')
man = json.load(open(man_path))
done = 0
for a in man['assets']:
    rel = a['path']
    if rel.startswith('assets/models/'):
        s = os.path.join(src, rel[len('assets/models/'):])
    elif rel == 'assets/textures/terrain_detail.jpg':
        s = os.path.join(src, 'terrain_detail.jpg')
    else:
        continue
    if not os.path.exists(s):
        print('not built, kept as is:', rel)
        continue
    dst = os.path.join(ROOT, 'public', rel)
    shutil.copyfile(s, dst)
    a['bytes'] = os.path.getsize(dst)
    done += 1
import motion
motion.apply(os.path.join(ROOT, 'public', 'assets', 'models'))
for a in man['assets']:
    p = os.path.join(ROOT, 'public', a['path'])
    if os.path.exists(p):
        a['bytes'] = os.path.getsize(p)
with open(man_path, 'w') as f:
    json.dump(man, f, indent=2)
    f.write('\n')
print('installed', done)
