"""One-command effect build: simulate, render, finalize.

python tools/fxlib/job.py <effect> [--test] [--work DIR] [--threads N]

Effect definitions live in jobs.json. --test renders only the 'test_frames' at 384px/32 samples
and writes a contact sheet to /mnt/project-files/fx-library/proofs/tests/<effect>.jpg.
Without --test it renders every frame at the final res/samples and finalizes into
/mnt/project-files/fx-library/flipbooks/<effect>/ (+ atlases/).
Re-running skips the sim if VDBs exist (delete <work>/<effect> to force) and skips rendered frames.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LIB = '/mnt/project-files/fx-library'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('effect'); ap.add_argument('--test', action='store_true')
    ap.add_argument('--work', default='/home/user/fxwork'); ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--resim', action='store_true')
    ap.add_argument('--rerender', action='store_true', help='clear rendered frames but reuse the sim')
    a = ap.parse_args()
    J = json.load(open(os.path.join(HERE, 'jobs.json')))[a.effect]
    sim_name = J.get('sim_as', a.effect)
    vdb = os.path.join(a.work, sim_name)
    if a.resim or not os.path.exists(os.path.join(vdb, 'sim.json')):
        subprocess.check_call([PY, os.path.join(HERE, 'make_fx.py'), J['recipe'], vdb, json.dumps(J.get('sim', {}))])
    simj = json.load(open(os.path.join(vdb, 'sim.json')))
    tag = a.effect + ('_test' if a.test else '')
    out = os.path.join(a.work, tag + '_png')
    r = dict(J['render'])
    r.update(vdb_dir=vdb, out_dir=out, domain=simj['domain'], frames=[1, simj['frames']], threads=a.threads, skip_existing=True)
    if a.test:
        r.update(only=J['test_frames'], res=384, samples=32)
    if (a.resim or a.rerender) and os.path.isdir(out):
        import shutil; shutil.rmtree(out)
    cfgp = os.path.join(a.work, tag + '.json')
    json.dump(r, open(cfgp, 'w'))
    subprocess.check_call([PY, os.path.join(HERE, 'render_vdb.py'), cfgp])
    if a.test:
        d = os.path.join(LIB, 'proofs', 'tests'); os.makedirs(d, exist_ok=True)
        fs = sorted(os.path.join(out, f) for f in os.listdir(out) if f.endswith('.png'))
        subprocess.check_call([PY, os.path.join(HERE, 'sheet.py'), os.path.join(d, a.effect + '.jpg'), '150,135,110'] + fs)
        print('sheet', os.path.join(d, a.effect + '.jpg'))
    else:
        f = J['finalize']
        args = [PY, os.path.join(HERE, 'finalize.py'), out, a.effect, '--extent', str(r['view_size']),
                '--origin_v', str(f.get('origin_v', 0.0)), '--tint', f.get('tint', 'fire'), '--note', f.get('note', '')]
        if f.get('loop'):
            args += ['--loop', str(f['loop'])]
        if f.get('drop_first'):
            args += ['--drop_first', str(f['drop_first'])]
        subprocess.check_call(args)


if __name__ == '__main__':
    main()
