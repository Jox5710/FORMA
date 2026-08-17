#!/usr/bin/env python3
"""
Turn forma_cuts/ into real transparent assets.

Those files arrive as JPEGs with a checkerboard *painted into the pixels* — the
pattern an editor draws to mean "transparent", flattened into a format that has
no alpha channel at all. Used as they are, every one of them shows a grey grid
behind the coach. So the alpha has to be rebuilt.

Keying the checkerboard out directly is the obvious approach and the wrong one:
it is two near-greys, and so are black shorts, so a colour key takes the shorts
with it. The segmentation model already in the pipeline has no such problem — it
finds the person and ignores whatever is behind them — so this reuses it, then
crops each pose to its own bounding box and writes WebP with real alpha.

    python3 tools/build-cuts.py
"""

import os
import sys
import hashlib

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "forma_cuts")
OUT = os.path.join(ROOT, "assets")

# reuse the matting model, edge cleanup and writer from the main pipeline rather
# than growing a second copy of them
spec = importlib.util.spec_from_file_location("ba", os.path.join(HERE, "build-assets.py"))
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)

TALL = 900          # the hero sizes, tall enough for a full-bleed plan cover
WIDE = 520          # the smaller badge/tile sizes


def checker_fraction(im):
    """
    How much of this frame is the painted transparency grid.

    The grid is a regular pair of desaturated greys, so a pixel belongs to it if
    its channels agree closely and it sits in the light-grey band. Used only to
    report what was found — the matte itself comes from the model.
    """
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    spread = a.max(axis=2) - a.min(axis=2)
    lum = a.mean(axis=2)
    grid = (spread <= 6) & (lum > 140) & (lum < 250)
    return float(grid.mean())


def main():
    if not os.path.isdir(SRC):
        sys.exit("no forma_cuts/ directory next to the pages")
    os.makedirs(OUT, exist_ok=True)

    # the folder ships an exact duplicate; hash so it is not processed twice
    seen, files = set(), []
    for name in sorted(os.listdir(SRC)):
        if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        p = os.path.join(SRC, name)
        h = hashlib.md5(open(p, "rb").read()).hexdigest()
        if h in seen:
            print("  skipping duplicate: %s" % name)
            continue
        seen.add(h)
        files.append(p)

    print("%d unique poses" % len(files))
    made = []
    for i, path in enumerate(files, 1):
        src = ba.load(path)
        grid = checker_fraction(src)
        rgba = np.dstack([np.array(src), ba.cutout_mask(src)])
        rgba = ba.clean_edges(rgba, erode=1, feather=1.0)
        rgba = ba.trim(rgba, pad=2)

        cov = float((rgba[..., 3] > 8).mean())
        if cov < 0.04:
            print("  %-42s dropped: matte found almost nothing" % os.path.basename(path)[:42])
            continue

        im = ba.to_height(rgba, TALL)
        name = "cut-%d.webp" % i
        ba.save_webp(im, name, quality=76)
        made.append(name)
        print("        (grid was %.0f%% of the source, subject fills %.0f%% of the crop)"
              % (grid * 100, cov * 100))

    print("\n%d cutouts written to assets/" % len(made))
    print("names: %s" % ", ".join(made))


if __name__ == "__main__":
    main()
