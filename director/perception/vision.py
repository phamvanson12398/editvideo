"""Single-pass visual analysis on downscaled frames: genre, faces, characters, burned-in text, motion."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from ..utils.ffmpeg import ffmpeg_bin
from ..utils.log import log, warn
from .schema import Character, FaceBox, FaceSample, Scene, TextRegion

ASSETS = Path(__file__).resolve().parents[2] / "assets"
ANIME_CASCADE = ASSETS / "models" / "lbpcascade_animeface.xml"

# Distinct, readable caption colors for characters (kept stable per series).
CHARACTER_COLORS = [
    "#FFD400", "#4FC3F7", "#FF6B9D", "#7CFC8A", "#FFA040", "#C792EA",
    "#FF5252", "#80CBC4", "#F48FB1", "#AED581", "#FFE082", "#90CAF9",
]


def iter_frames(src: str | Path, fps: float, width: int) -> Iterator[tuple[float, np.ndarray]]:
    """Yield (t, BGR frame) sampled at `fps`, scaled to `width`."""
    probe_h = None
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-i", str(src), "-an",
        "-vf", f"fps={fps},scale={width}:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
    ]
    # learn output height from a single frame first
    first = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True,
    ).stdout
    if not first:
        return
    probe_h = len(first) // (width * 3)
    frame_size = width * probe_h * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    i = 0
    try:
        while True:
            buf = proc.stdout.read(frame_size)
            if len(buf) < frame_size:
                break
            yield i / fps, np.frombuffer(buf, np.uint8).reshape(probe_h, width, 3)
            i += 1
    finally:
        proc.stdout.close()
        proc.wait()


# ---------------------------------------------------------------- genre


def frame_style_stats(frame: np.ndarray) -> tuple[float, float, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean = cv2.blur(gray, (5, 5))
    sq = cv2.blur(gray * gray, (5, 5))
    std = np.sqrt(np.maximum(sq - mean * mean, 0))
    flat = float((std < 3.0).mean())
    q = (frame // 32).reshape(-1, 3)
    codes = q[:, 0].astype(np.int32) * 64 + q[:, 1].astype(np.int32) * 8 + q[:, 2].astype(np.int32)
    counts = np.bincount(codes, minlength=512)
    top = np.sort(counts)[::-1]
    concentration = float(top[:12].sum() / max(1, counts.sum()))  # few dominant flat colors -> drawn
    edges = cv2.Canny(gray.astype(np.uint8), 80, 160)
    edge = float((edges > 0).mean())
    return flat, concentration, edge


def classify_genre(stats: list[tuple[float, float, float]]) -> tuple[str, float]:
    if not stats:
        return "unknown", 0.0
    arr = np.array(stats)
    flat, conc, edge = np.median(arr[:, 0]), np.median(arr[:, 1]), np.median(arr[:, 2])
    score = 0.0
    score += np.clip((flat - 0.30) / 0.30, -1, 1)
    score += np.clip((conc - 0.55) / 0.25, -1, 1)
    score += 0.5 * np.clip((edge - 0.03) / 0.05, -1, 1)
    if score > 0.6:
        return "anime", float(min(1.0, 0.5 + score / 4))
    if score < -0.4:
        return "live", float(min(1.0, 0.5 - score / 4))
    return "unknown", 0.3


# ---------------------------------------------------------------- faces


class FaceDetector:
    def __init__(self, genre: str):
        self.anime = None
        self.real = None
        if genre in ("anime", "cartoon3d", "unknown") and ANIME_CASCADE.exists():
            self.anime = cv2.CascadeClassifier(str(ANIME_CASCADE))
        if genre in ("live", "unknown"):
            path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if path.exists():
                self.real = cv2.CascadeClassifier(str(path))

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        h, w = gray.shape
        min_side = max(20, int(min(w, h) * 0.06))
        out: list[tuple[int, int, int, int, float]] = []
        for det, neighbors in ((self.anime, 4), (self.real, 6)):
            if det is None:
                continue
            rects = det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=neighbors, minSize=(min_side, min_side))
            for (x, y, fw, fh) in rects:
                out.append((int(x), int(y), int(fw), int(fh), 1.0))
        return _nms(out)


def _nms(boxes: list[tuple[int, int, int, int, float]], iou_thr: float = 0.4) -> list[tuple[int, int, int, int, float]]:
    boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
    keep: list[tuple[int, int, int, int, float]] = []
    for b in boxes:
        if all(_iou(b, k) < iou_thr for k in keep):
            keep.append(b)
    return keep


def _iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    ix = max(0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def appearance_feature(frame: np.ndarray, box: tuple[int, int, int, int, float]) -> np.ndarray:
    """Color signature of a face + hair region (hair color is very distinctive in animation)."""
    x, y, w, h, _ = box
    H, W = frame.shape[:2]
    x0, x1 = max(0, x - w // 3), min(W, x + w + w // 3)
    y0, y1 = max(0, y - h // 2), min(H, y + h)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return np.zeros(64, np.float32)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    top = hsv[: max(1, hsv.shape[0] // 3)]
    h1 = cv2.calcHist([top], [0, 1], None, [8, 4], [0, 180, 0, 256]).flatten()
    h2 = cv2.calcHist([hsv], [0, 1], None, [8, 4], [0, 180, 0, 256]).flatten()
    f = np.concatenate([h1 / (h1.sum() + 1e-6), h2 / (h2.sum() + 1e-6)]).astype(np.float32)
    return f / (np.linalg.norm(f) + 1e-6)


def cluster_characters(feats: list[np.ndarray], thr: float = 0.86) -> list[int]:
    centroids: list[np.ndarray] = []
    counts: list[int] = []
    labels: list[int] = []
    for f in feats:
        if centroids:
            sims = [float(f @ (c / (np.linalg.norm(c) + 1e-6))) for c in centroids]
            j = int(np.argmax(sims))
            if sims[j] >= thr:
                centroids[j] = centroids[j] + f
                counts[j] += 1
                labels.append(j)
                continue
        centroids.append(f.copy())
        counts.append(1)
        labels.append(len(centroids) - 1)
    # relabel by frequency, drop rare clusters into "unknown" (-1)
    order = sorted(range(len(counts)), key=lambda k: -counts[k])
    total = max(1, len(feats))
    remap = {}
    for rank, k in enumerate(order):
        remap[k] = rank if counts[k] >= max(3, 0.03 * total) else -1
    return [remap[l] for l in labels]


# ---------------------------------------------------------------- burned-in text


def text_mask_band(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Find horizontal text-like blobs (subtitles) in a grayscale band."""
    h, w = gray.shape
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k)
    grad = cv2.max(tophat, blackhat)
    _, th = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, w // 40), 3)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(th, 8)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if bw > w * 0.15 and bw > 3 * bh and h * 0.06 < bh < h * 0.5 and area > 0.35 * bw * bh:
            out.append((int(x), int(y), int(bw), int(bh)))
    return out


def detect_text_regions(frames: list[np.ndarray]) -> TextRegion:
    if not frames:
        return TextRegion()
    H, W = frames[0].shape[:2]
    bands = {"bottom": (int(H * 0.62), H), "top": (0, int(H * 0.30))}
    best = TextRegion()
    for name, (y0, y1) in bands.items():
        hits, boxes, sigs = 0, [], []
        for f in frames:
            g = cv2.cvtColor(f[y0:y1], cv2.COLOR_BGR2GRAY)
            found = text_mask_band(g)
            if found:
                hits += 1
                for (x, y, bw, bh) in found:
                    boxes.append((x, y + y0, bw, bh))
                sigs.append(cv2.resize(g, (64, 8)).astype(np.float32))
        coverage = hits / len(frames)
        if coverage < 0.18 or not boxes:
            continue
        # static overlays (logos) don't change; subtitles do
        if len(sigs) >= 3:
            groups: list[np.ndarray] = []
            for sg in sigs:
                if all(float(np.abs(sg - g0).mean()) > 3.0 for g0 in groups):
                    groups.append(sg)
            if len(groups) < 3:
                continue
        arr = np.array(boxes, dtype=np.float32)
        x0 = np.percentile(arr[:, 0], 10)
        x1 = np.percentile(arr[:, 0] + arr[:, 2], 90)
        yy0 = np.percentile(arr[:, 1], 10)
        yy1 = np.percentile(arr[:, 1] + arr[:, 3], 90)
        region = TextRegion(
            present=True,
            x=float(x0 / W), y=float(yy0 / H), w=float((x1 - x0) / W), h=float((yy1 - yy0) / H),
            coverage=round(coverage, 3),
        )
        if region.coverage > best.coverage:
            best = region
    return best


# ---------------------------------------------------------------- main


def analyze_vision(
    src: str | Path,
    duration: float,
    scenes: list[Scene],
    face_fps: float = 2.0,
    width: int = 480,
    genre_hint: str | None = None,
    thumb_dir: str | Path | None = None,
) -> dict:
    """Returns dict with genre, genre_confidence, faces, characters, hardsub, motion per scene."""
    frames: list[tuple[float, np.ndarray]] = list(iter_frames(src, face_fps, width))
    if not frames:
        warn("Không đọc được khung hình nào để phân tích hình ảnh.")
        return {"genre": "unknown", "genre_confidence": 0.0, "faces": [], "characters": [], "hardsub": TextRegion()}

    step = max(1, len(frames) // 40)
    stats = [frame_style_stats(f) for _, f in frames[::step]]
    genre, conf = classify_genre(stats)
    if genre_hint:
        genre, conf = genre_hint, 1.0
    log(f"Thể loại hình ảnh: {genre} (độ tin cậy {conf:.2f})")

    det = FaceDetector(genre)
    H, W = frames[0][1].shape[:2]
    samples: list[FaceSample] = []
    feats: list[np.ndarray] = []
    feat_refs: list[tuple[int, int]] = []
    thumbs: dict[int, np.ndarray] = {}
    for fi, (t, f) in enumerate(frames):
        boxes = det.detect(f)
        fbs = []
        for bi, b in enumerate(boxes):
            fbs.append(FaceBox(x=b[0] / W, y=b[1] / H, w=b[2] / W, h=b[3] / H, score=b[4]))
            feats.append(appearance_feature(f, b))
            feat_refs.append((fi, bi))
            thumbs[len(feats) - 1] = f[max(0, b[1]):b[1] + b[3], max(0, b[0]):b[0] + b[2]]
        samples.append(FaceSample(t=round(t, 3), boxes=fbs))

    characters: list[Character] = []
    if feats:
        labels = cluster_characters(feats)
        groups: dict[int, list[int]] = {}
        for k, lab in enumerate(labels):
            fi, bi = feat_refs[k]
            if lab >= 0:
                samples[fi].boxes[bi].character = f"C{lab}"
                groups.setdefault(lab, []).append(k)
        for lab in sorted(groups):
            idx = groups[lab]
            centroid = np.mean([feats[k] for k in idx], axis=0)
            thumb_path = None
            if thumb_dir is not None:
                best_k = max(idx, key=lambda k: thumbs[k].size)
                if thumbs[best_k].size:
                    Path(thumb_dir).mkdir(parents=True, exist_ok=True)
                    thumb_path = str(Path(thumb_dir) / f"char_C{lab}.jpg")
                    cv2.imwrite(thumb_path, thumbs[best_k])
            characters.append(Character(
                id=f"C{lab}",
                color=CHARACTER_COLORS[lab % len(CHARACTER_COLORS)],
                appearances=len(idx),
                feature=[round(float(v), 5) for v in centroid],
                thumbnail=thumb_path,
            ))
        log(f"Phát hiện {len(characters)} nhân vật/người xuất hiện thường xuyên.")

    text_frames = [f for _, f in frames[:: max(1, len(frames) // 80)]]
    hardsub = detect_text_regions(text_frames)
    if hardsub.present:
        log(f"Video có chữ/phụ đề sẵn trên hình (vùng y={hardsub.y:.2f}..{hardsub.y + hardsub.h:.2f}).")

    # motion per scene
    diffs = [0.0]
    for (_, a), (_, b) in zip(frames[:-1], frames[1:]):
        diffs.append(float(np.abs(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.int16)
                                  - cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.int16)).mean()))
    for s in scenes:
        i0, i1 = int(s.t0 * face_fps), max(int(s.t0 * face_fps) + 1, int(s.t1 * face_fps))
        seg = diffs[i0:i1]
        s.motion = round(float(np.mean(seg)) / 30.0, 3) if seg else 0.0
        lap = []
        for (_, f) in frames[i0:i1][:5]:
            lap.append(cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_32F).var())
        s.quality = round(float(np.clip(np.mean(lap) / 300.0, 0, 1)), 3) if lap else 1.0

    return {
        "genre": genre,
        "genre_confidence": conf,
        "faces": samples,
        "characters": characters,
        "hardsub": hardsub,
    }
