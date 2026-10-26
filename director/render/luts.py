"""Built-in color LUTs generated as .cube files (no licensing issues)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

SIZE = 33


def _grid() -> np.ndarray:
    v = np.linspace(0, 1, SIZE)
    b, g, r = np.meshgrid(v, v, v, indexing="ij")  # .cube order: r fastest
    return np.stack([r, g, b], axis=-1)


def _luma(rgb):
    return (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])[..., None]


def _sat(rgb, s):
    y = _luma(rgb)
    return y + (rgb - y) * s


def _contrast(rgb, c, pivot=0.5):
    return (rgb - pivot) * c + pivot


def warm(rgb):
    out = rgb * np.array([1.06, 1.0, 0.9])
    return _sat(_contrast(out, 1.05), 1.08)


def cool(rgb):
    out = rgb * np.array([0.92, 1.0, 1.08])
    return _sat(_contrast(out, 1.04), 0.98)


def teal_orange(rgb):
    y = _luma(rgb)
    shadows = np.array([0.0, 0.05, 0.08]) * (1 - y)
    highlights = np.array([0.08, 0.03, -0.06]) * y
    return _sat(_contrast(rgb + shadows + highlights, 1.08), 1.12)


def pop(rgb):
    return _sat(_contrast(rgb, 1.1), 1.3)


def moody(rgb):
    out = _contrast(rgb, 1.15, 0.45) * 0.92
    return _sat(out, 0.8) + np.array([0.0, 0.01, 0.03])


def pastel(rgb):
    out = rgb * 0.85 + 0.12
    return _sat(out, 0.85)


def vintage(rgb):
    out = _sat(rgb, 0.75) * np.array([1.05, 0.98, 0.85]) + np.array([0.04, 0.03, 0.02])
    return _contrast(out, 0.92)


def sepia(rgb):
    y = _luma(rgb)
    return np.concatenate([y * 1.07 + 0.05, y * 0.95 + 0.02, y * 0.75], axis=-1)


def bw(rgb):
    y = _contrast(_luma(rgb), 1.1)
    return np.repeat(y, 3, axis=-1)


def cinematic(rgb):
    return _contrast(teal_orange(rgb) * 0.97, 1.06)


def anime_vivid(rgb):
    """Brighter, cleaner flat colors for animation."""
    out = _contrast(rgb, 1.06, 0.4) * 1.03
    return _sat(out, 1.18)


def night(rgb):
    out = _sat(rgb, 0.6) * np.array([0.75, 0.85, 1.05]) * 0.75
    return out


LUTS = {
    "warm": warm, "cool": cool, "teal_orange": teal_orange, "pop": pop, "moody": moody, "pastel": pastel,
    "vintage": vintage, "sepia": sepia, "bw": bw, "cinematic": cinematic, "anime_vivid": anime_vivid, "night": night,
}


def write_cube(name: str, fn, path: Path) -> Path:
    rgb = np.clip(fn(_grid()), 0, 1).reshape(-1, 3)
    lines = [f'TITLE "{name}"', f"LUT_3D_SIZE {SIZE}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in rgb]
    path.write_text("\n".join(lines) + "\n")
    return path


def lut_path(name_or_path: str | None, assets: Path, cache: Path, intensity: float = 1.0) -> Path | None:
    """Built-in LUTs are generated pre-blended with the identity at `intensity` (no runtime cost).
    User .cube files are used as-is."""
    if not name_or_path:
        return None
    p = Path(name_or_path)
    if p.suffix.lower() == ".cube" and p.exists():
        return p
    user = assets / "luts" / f"{name_or_path}.cube"
    if user.exists():
        return user
    fn = LUTS.get(name_or_path)
    if fn is None:
        return None
    k = round(float(min(max(intensity, 0.0), 1.0)), 2)
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{name_or_path}_{int(k * 100)}.cube"
    if not out.exists():
        write_cube(name_or_path, lambda rgb: rgb * (1 - k) + fn(rgb) * k, out)
    return out
