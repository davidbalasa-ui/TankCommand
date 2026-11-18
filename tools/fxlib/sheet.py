"""Contact sheet of RGBA frames over a background. sheet.py out.jpg bg(r,g,b) files..."""
import sys
from PIL import Image
out = sys.argv[1]; bg = tuple(int(v) for v in sys.argv[2].split(','))
ims = [Image.open(p).convert('RGBA') for p in sys.argv[3:]]
w, h = ims[0].size
S = Image.new('RGB', (w * len(ims), h), bg)
for i, im in enumerate(ims):
    S.paste(im, (i * w, 0), im)
S.save(out, quality=88)
