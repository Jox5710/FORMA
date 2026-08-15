#!/usr/bin/env python3
"""
Build the published image assets from the originals in images/.

The originals are 4000x3000 phone shots (~172MB in total) and are gitignored.
This script cuts the coach out of two of them, trims and de-halos the result,
and writes the handful of small WebP files the site actually ships.

    pip install rembg pillow opencv-python
    python3 tools/build-assets.py

Re-run it whenever you swap a source photo. Output goes to assets/.
"""

import os
import sys
import io

import numpy as np
import cv2
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "images")
OUT = os.path.join(ROOT, "assets")

# Everything is composited on this. Edge pixels are pre-blended against it so the
# light concrete background of the original does not survive as a bright halo.
BG = (0x0F, 0x0F, 0x11)

CUTOUTS = [
    # (source, output, target height, label)
    ("file_00000000ba2881f4aede039268af5b9d.png", "coach-hero.webp", 900, "overhead victory"),
    ("file_00000000a99c81f48281a76a84a800a3.png", "coach-alt.webp", 700, "front double-biceps"),
    ("file_00000000f94481f4b3c0aa163ac2da9c.png", "coach-stand.webp", 700, "standing"),
]
AVATAR_FROM = "file_00000000a99c81f48281a76a84a800a3.png"
TEXTURE_FROM = "20260730_115759.jpg"

# The gallery: rectangular crops used as day thumbnails in a training plan and
# as the strip on the intake form. Chosen for variety — gym, wooden backdrop,
# cable work, free weights — so a six-day plan does not repeat itself.
SHOTS = [
    "20260803_214442(1).jpg",
    "IMG-20260725-WA0013.jpg",
    "20260729_131101.jpg",
    "20260730_130328.jpg",
    "20260809_145750.jpg",
    "20260729_134055.jpg",
    "20260730_115759.jpg",
    "IMG-20260727-WA0022.jpg",
]
# Wide enough to run full width as a day banner without upscaling, and still
# crop well down to a thumbnail in a three-up strip.
SHOT_W, SHOT_H = 760, 320


MODEL = os.path.expanduser("~/.u2net/isnet-general-use.onnx")
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"


def session():
    """
    The isnet matting model, run straight on onnxruntime.

    rembg itself is not imported: it pulls in pymatting/numba for an alpha
    refinement step we do not use, and that dependency chain is a slow install
    for no gain here. The pre/post-processing below matches rembg's DisSession
    exactly, so the mask is identical.
    """
    import onnxruntime as ort
    if not hasattr(session, "s"):
        if not os.path.exists(MODEL):
            sys.exit("model missing — download it once:\n  mkdir -p ~/.u2net && curl -L -o %s %s" % (MODEL, MODEL_URL))
        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        session.s = ort.InferenceSession(MODEL, providers=providers)
    return session.s


def load(path):
    """
    Open a photo the right way up.

    Every shot off the phone is stored landscape with an EXIF orientation flag
    of 6, so anything that ignores the flag gets a subject lying on its side.
    """
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def cover(im, w, h):
    """Scale-and-centre-crop to exactly w x h, like CSS object-fit: cover."""
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 3          # bias up: heads matter more than floors
    return im.crop((x, y, x + w, y + h))


def cutout(path):
    """Segment the subject and return an RGBA array at full resolution."""
    s = session()
    src = load(path)

    im = np.array(src.resize((1024, 1024), Image.LANCZOS)).astype(np.float32)
    im = im / max(im.max(), 1e-6)
    im = (im - 0.5) / 1.0
    x = np.expand_dims(im.transpose(2, 0, 1), 0).astype(np.float32)

    pred = s.run(None, {s.get_inputs()[0].name: x})[0][:, 0, :, :]
    lo, hi = pred.min(), pred.max()
    pred = (pred - lo) / max(hi - lo, 1e-6)

    mask = Image.fromarray((np.squeeze(pred) * 255).astype(np.uint8), mode="L")
    mask = mask.resize(src.size, Image.LANCZOS)

    rgba = np.dstack([np.array(src), np.array(mask)])
    return rgba


def clean_edges(rgba, erode=1, feather=1.0):
    """
    Segmentation leaves a fringe of background-coloured pixels. Pull the matte in
    slightly, soften it, then pre-composite the partially transparent pixels onto
    BG so no light rim survives against the dark UI.
    """
    rgb = rgba[..., :3].astype(np.float32)
    a = rgba[..., 3].astype(np.float32)

    if erode:
        k = np.ones((3, 3), np.uint8)
        a = cv2.erode(a, k, iterations=erode)
    if feather:
        a = cv2.GaussianBlur(a, (0, 0), feather)

    an = (a / 255.0)[..., None]
    bg = np.array(BG, np.float32)
    rgb = rgb * an + bg * (1.0 - an)          # solid pixels untouched (an == 1)

    out = np.dstack([rgb, a]).clip(0, 255).astype(np.uint8)
    return out


def trim(rgba, pad=2, thresh=6):
    ys, xs = np.where(rgba[..., 3] > thresh)
    if not len(ys):
        return rgba
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + 1 + pad)
    return rgba[y0:y1, x0:x1]


def to_height(rgba, h):
    im = Image.fromarray(rgba)
    if im.height <= h:
        return im
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def save_webp(im, name, quality=72, lossless=False):
    p = os.path.join(OUT, name)
    im.save(p, "WEBP", quality=quality, method=6, lossless=lossless)
    kb = os.path.getsize(p) / 1024
    print("  %-22s %4dx%-4d %7.1f KB" % (name, im.width, im.height, kb))
    return p


def center_run(row, cx, thresh=40):
    """The horizontal run of subject that contains (or is nearest) cx."""
    xs = np.where(row > thresh)[0]
    if not len(xs):
        return None
    # split into contiguous runs
    breaks = np.where(np.diff(xs) > 1)[0]
    runs = np.split(xs, breaks + 1)
    best = min(runs, key=lambda r: 0 if r[0] <= cx <= r[-1] else min(abs(r[0] - cx), abs(r[-1] - cx)))
    return best[0], best[-1]


def find_head(rgba):
    """
    Locate a square around the head.

    Face detection is tried first but the coach is wearing sunglasses in both
    shots, so it usually misses. The fallback walks the *central* column of the
    silhouette down from the top: in a double-biceps or overhead pose the fists
    are the topmost pixels, so "topmost" and "narrowest" both find an arm. The
    run containing the horizontal centre of mass is the head, and the row where
    that run suddenly widens is the shoulders.
    """
    rgb = rgba[..., :3]
    alpha = rgba[..., 3]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces):
        x, y, w, h = sorted(faces, key=lambda f: f[2] * f[3])[-1]
        print("    face detected at (%d,%d) %dx%d" % (x, y, w, h))
        return x + w / 2, y + h / 2, max(w, h) * 2.2

    H, W = alpha.shape
    ys, xs = np.where(alpha > 40)
    cx = float(np.median(xs))

    # width of the central run for every row, from the crown down
    prof = []
    top = None
    for y in range(0, int(H * 0.45)):
        r = center_run(alpha[y], cx)
        w = 0 if r is None else (r[1] - r[0] + 1)
        if w < W * 0.03:
            w = 0
        if top is None and w:
            top = y
        if top is not None:
            prof.append(w)
    if top is None or len(prof) < 20:
        return W / 2, H * 0.12, H * 0.22

    prof = np.array(prof, np.float32)
    prof[prof == 0] = prof.max()          # gaps are not necks

    # The neck is the narrowest point between the crown and the shoulders: the
    # head above it is wider, the shoulders below it are much wider. Skip the
    # crown itself, which tapers to nothing.
    lo = max(3, int(H * 0.025))
    hi = min(len(prof), max(lo + 5, int(H * 0.28)))
    neck = lo + int(np.argmin(prof[lo:hi]))

    head_h = neck
    if head_h < H * 0.03:                 # implausible — fall back to proportion
        print("    neck unclear; using proportional head box")
        return cx, top + H * 0.055, H * 0.19
    print("    crown=%d neck=+%d (head %dpx, neck width %d)" % (top, neck, head_h, prof[neck]))
    # frame head plus a little shoulder, with no dead space above the crown
    return cx, top + head_h * 0.62, head_h * 1.30


def crop_square(rgba, cx, cy, side):
    H, W = rgba.shape[:2]
    side = int(max(32, side))
    x0 = int(round(cx - side / 2))
    y0 = int(round(cy - side / 2))
    canvas = np.zeros((side, side, 4), np.uint8)
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(W, x0 + side), min(H, y0 + side)
    if sx1 > sx0 and sy1 > sy0:
        canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = rgba[sy0:sy1, sx0:sx1]
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)
    if not os.path.isdir(SRC):
        sys.exit("images/ not found — the originals are gitignored; restore them to rebuild.")

    total = 0
    print("cutouts")
    alt_rgba = None
    for src, name, height, label in CUTOUTS:
        p = os.path.join(SRC, src)
        if not os.path.exists(p):
            print("  ! missing %s — skipped" % src)
            continue
        print("  %s (%s)" % (src, label))
        rgba = trim(clean_edges(cutout(p)))
        if src == AVATAR_FROM:
            alt_rgba = rgba
        total += os.path.getsize(save_webp(to_height(rgba, height), name))

    print("avatar")
    if alt_rgba is not None:
        cx, cy, side = find_head(alt_rgba)
        av = crop_square(alt_rgba, cx, cy, side)
        im = Image.fromarray(av).resize((320, 320), Image.LANCZOS)
        total += os.path.getsize(save_webp(im, "coach-avatar.webp", quality=80))

    print("gallery")
    n = 0
    for i, src in enumerate(SHOTS):
        p = os.path.join(SRC, src)
        if not os.path.exists(p):
            print("  ! missing %s — skipped" % src)
            continue
        im = cover(load(p), SHOT_W, SHOT_H)
        total += os.path.getsize(save_webp(im, "shot-%d.webp" % (n + 1), quality=70))
        n += 1
    print("  %d gallery shots" % n)

    print("texture")
    tp = os.path.join(SRC, TEXTURE_FROM)
    if os.path.exists(tp):
        im = cover(load(tp), 1400, 900)
        # darken so text stays readable over it without another CSS layer
        arr = (np.array(im).astype(np.float32) * 0.38).clip(0, 255).astype(np.uint8)
        total += os.path.getsize(save_webp(Image.fromarray(arr), "texture.webp", quality=66))

    # a manifest so the pages know how many shots exist without hardcoding it
    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        fh.write('{"shots":%d}\n' % n)

    print("\ntotal shipped: %.1f KB across %d files" % (total / 1024, len(os.listdir(OUT))))


if __name__ == "__main__":
    main()
