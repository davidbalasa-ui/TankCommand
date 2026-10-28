"""Build the first-round prompt for a package: pack.py WP-03 OUT_FILE.
Prompt = COMMON rules + package spec + SOR gameplay tab + every tracked text file the code needs."""
import subprocess, sys
pkg, out = sys.argv[1], sys.argv[2]
parts = [open('docs/deepseek/COMMON.md').read(),
         open(f'docs/deepseek/packages/{pkg}.md').read(),
         '# SOR GAMEPLAY SPECIFICATION (reference; the package spec above decides scope)\n\n' + open('docs/sor/gameplay.md').read(),
         '# CURRENT REPOSITORY']
files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], capture_output=True, text=True).stdout.split()
SKIP_PREFIX = ('docs/deepseek/', 'docs/sor/', 'tools/', 'android/', 'public/assets/models/', 'node_modules/')
TEXT = ('.ts', '.js', '.mjs', '.cjs', '.json', '.css', '.html', '.md', '.yml', '.yaml')
for f in sorted(files):
    if f.startswith(SKIP_PREFIX) or f == 'package-lock.json' or not f.endswith(TEXT) or f.endswith('.pdf'):
        continue
    try:
        body = open(f).read()
    except (UnicodeDecodeError, FileNotFoundError):
        continue
    parts.append(f'<<<FILE {f}>>>\n{body}<<<END FILE>>>')
open(out, 'w').write('\n\n'.join(parts))
print(out, sum(len(p) for p in parts) // 4, 'approx tokens')
