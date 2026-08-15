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
# The avatar comes from a clear frontal shot rather than a cutout: in a small
# circle a lit, colour photograph of the face reads far better than a
# silhouette. This is the same frame as shot-3.
AVATAR_FROM = "20260729_131101.jpg"
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
# Portrait, because these frames hold the whole figure. A wide banner cannot
# show a standing person head to foot without shrinking them to a sliver.
SHOT_W, SHOT_H = 600, 800


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


def face_of(im):
    """
    (cx, cy) of the largest plausible face, in source pixels.

    Haar happily reports a knee or a water bottle as a face. In a standing
    portrait the head is in the upper half and is a small fraction of the
    frame, so anything else is discarded rather than trusted.
    """
    gray = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    side = max(24, int(im.height * 0.025))
    faces = cascade.detectMultiScale(gray, 1.08, 6, minSize=(side, side))

    ok = [f for f in faces
          if (f[1] + f[3] / 2.0) < im.height * 0.55         # upper half only
          and im.height * 0.03 < f[3] < im.height * 0.28]   # head-sized
    if not ok:
        return None
    x, y, w, h = sorted(ok, key=lambda f: f[2] * f[3])[-1]
    return (x + w / 2.0, y + h / 2.0, float(h))


def subject_top(im):
    """Row where the subject starts, via the same matte used for the cutouts."""
    try:
        alpha = cutout_mask(im)
    except Exception:
        return None
    ys = np.where(alpha.max(axis=1) > 60)[0]
    return float(ys.min()) if len(ys) else None


def cover(im, w, h):
    """
    Frame the whole subject — head to feet — inside a w x h crop.

    Cropping to a fixed rectangle cut the coach off at the chest, and aiming at
    the face only traded that for a head-and-shoulders portrait. Instead the
    matte gives the subject's real bounding box, which is padded out to the
    target aspect so nothing of them is lost.
    """
    target = w / float(h)
    box = None
    try:
        alpha = cutout_mask(im)
        ys, xs = np.where(alpha > 60)
        if len(ys):
            box = [xs.min(), ys.min(), xs.max(), ys.max()]
    except Exception:
        pass

    if box is None:
        r = max(w / im.width, h / im.height)
        sc = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
        print("      frame=fallback")
        return sc.crop(((sc.width - w) // 2, 0, (sc.width - w) // 2 + w, h))

    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    pad = 0.06
    x0 -= bw * pad; x1 += bw * pad
    y0 -= bh * pad * 1.4; y1 += bh * pad          # a little more air above the head
    bw, bh = x1 - x0, y1 - y0

    # grow the short side until the box matches the frame's aspect
    if bw / bh < target:
        need = bh * target
        cx = (x0 + x1) / 2.0
        x0, x1 = cx - need / 2.0, cx + need / 2.0
    else:
        need = bw / target
        cy = (y0 + y1) / 2.0
        y0, y1 = cy - need / 2.0, cy + need / 2.0

    # keep it inside the photo, sliding rather than squashing
    def fit(a, b, limit):
        if b - a > limit:
            return 0.0, float(limit)
        if a < 0:
            b -= a; a = 0.0
        if b > limit:
            a -= (b - limit); b = float(limit)
        return max(0.0, a), min(float(limit), b)

    x0, x1 = fit(x0, x1, im.width)
    y0, y1 = fit(y0, y1, im.height)
    print("      frame=subject  %dx%d" % (x1 - x0, y1 - y0))
    return im.crop((int(x0), int(y0), int(x1), int(y1))).resize((w, h), Image.LANCZOS)


def cutout_mask(src):
    """Run the matting model over a PIL image and return an alpha array."""
    s = session()
    im = np.array(src.resize((1024, 1024), Image.LANCZOS)).astype(np.float32)
    im = im / max(im.max(), 1e-6)
    im = (im - 0.5) / 1.0
    x = np.expand_dims(im.transpose(2, 0, 1), 0).astype(np.float32)

    pred = s.run(None, {s.get_inputs()[0].name: x})[0][:, 0, :, :]
    lo, hi = pred.min(), pred.max()
    pred = (pred - lo) / max(hi - lo, 1e-6)

    mask = Image.fromarray((np.squeeze(pred) * 255).astype(np.uint8), mode="L")
    return np.array(mask.resize(src.size, Image.LANCZOS))


def cutout(path):
    """Segment the subject and return an RGBA array at full resolution."""
    src = load(path)
    return np.dstack([np.array(src), cutout_mask(src)])


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
    ap = os.path.join(SRC, AVATAR_FROM)
    if os.path.exists(ap):
        src = load(ap)
        f = face_of(src)
        if f is not None:
            cx, cy, fh = f
            side = fh * 2.05                   # face plus hair and a little neck
            cy += fh * 0.10                    # sit the eyes above centre
            print("    face at (%d,%d) h=%d -> %dpx box" % (cx, cy, fh, side))
        else:
            print("    no face; falling back to the cutout head finder")
            cx, cy, side = find_head(np.dstack([np.array(src), cutout_mask(src)]))
        av = crop_square(np.dstack([np.array(src), np.full(src.size[::-1], 255, np.uint8)]), cx, cy, side)
        im = Image.fromarray(av).convert("RGB").resize((320, 320), Image.LANCZOS)
        total += os.path.getsize(save_webp(im, "coach-avatar.webp", quality=82))

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
