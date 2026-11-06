"""Apply a DeepSeek answer: apply.py ANSWER_FILE REPO_ROOT REPORT_OUT. Prints '<n> files <m> deletes'."""
import os, re, sys
src = open(sys.argv[1]).read(); root = sys.argv[2]
PROTECTED_PREFIX = ('android/', 'tools/deepseek/', 'docs/deepseek/', 'docs/sor/', 'public/assets/models/', '.github/workflows/')
PROTECTED = {'docs/Armor_Command_1998_Mobile_Rebuild_SOR.pdf', 'package-lock.json'}

def blocked(p):
    return p in PROTECTED or p.startswith(PROTECTED_PREFIX) or '..' in p or p.startswith('/')

files = re.findall(r'<<<FILE (.+?)>>>\n(.*?)<<<END FILE>>>', src, re.S)
dels = re.findall(r'<<<DELETE (.+?)>>>', src)
rep = re.search(r'<<<REPORT>>>\n(.*?)<<<END REPORT>>>', src, re.S)
n = 0
for p, c in files:
    p = p.strip()
    if blocked(p):
        print('SKIP protected', p); continue
    fp = os.path.join(root, p); os.makedirs(os.path.dirname(fp) or '.', exist_ok=True)
    open(fp, 'w').write(c); n += 1
for p in dels:
    p = p.strip()
    if blocked(p):
        print('SKIP delete', p); continue
    fp = os.path.join(root, p)
    if os.path.exists(fp) and not any(p == f[0].strip() for f in files):
        os.remove(fp)
open(sys.argv[3], 'w').write(rep.group(1) if rep else '(no report)')
print(n, 'files', len(dels), 'deletes', 'report' if rep else 'NO REPORT')
