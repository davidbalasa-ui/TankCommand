"""Estimate DeepSeek spend for a package run: cost.py WP-03. Off-peak list prices (USD per 1M tokens):
cache hit 0.003, cache miss 0.15, output 0.60; peak hours cost double. Prints the off-peak estimate."""
import re, sys
s = open(f'.deepseek-runs/{sys.argv[1]}/SUMMARY.txt').read()
hit = miss = out = 0
for m in re.finditer(r'in=(\d+) cached=(\d+) out=(\d+)', s):
    i, c, o = map(int, m.groups()); hit += c; miss += i - c; out += o
usd = hit * 0.003e-6 + miss * 0.15e-6 + out * 0.60e-6
print(f'cache hit {hit:,}  miss {miss:,}  out {out:,}  ~${usd:.2f} off-peak (x2 at peak)')
