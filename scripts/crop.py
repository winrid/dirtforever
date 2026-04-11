"""Crop helper: python crop.py <source> <out> <x1> <y1> <x2> <y2> [scale]"""
import sys
from PIL import Image

src, out, x1, y1, x2, y2 = sys.argv[1:7]
scale = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
im = Image.open(src)
c = im.crop((int(x1), int(y1), int(x2), int(y2)))
if scale != 1.0:
    c = c.resize((int(c.size[0]*scale), int(c.size[1]*scale)))
c.save(out)
print(c.size)
