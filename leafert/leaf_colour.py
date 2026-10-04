"""
leaf_colour.py - colour measurement of leaf pixels (crop independent).

    extract_features(image, leaf_mask) -> {"features": {...}, "quality": {...}}

Removes glare (flash/sun reflections) and shadow pixels, optionally corrects
colour with a gray card or colour checker, then computes the median of each
colour index over the usable leaf pixels: DGCI, NGRDI, ExG, ExGR, GLI, VARI,
MGRVI, RGBVI, chromatic r/g/b, CIELAB L*a*b*, CIELAB hue and chroma, HSV hue,
saturation, brightness, and the shares of yellowish and brownish pixels.
These are exactly the measurements the maize model was trained on.
"""

from __future__ import annotations

from typing import Dict, Optional, Union

import numpy as np

ArrayLike = Union[np.ndarray, str]


# =============================================================================
# Colour utilities
# =============================================================================
def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def linear_rgb_to_lab(lin: np.ndarray) -> np.ndarray:
    """Linear sRGB (N,3) in 0..1 -> CIELAB (N,3), D65 white."""
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    d = 6 / 29
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4 / 29)
    L = 116 * f[:, 1] - 16
    a = 500 * (f[:, 0] - f[:, 1])
    b = 200 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """sRGB (N,3) 0..1 -> H in degrees [0,360), S, V in 0..1."""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = rgb.max(axis=1)
    mn = rgb.min(axis=1)
    d = mx - mn
    h = np.zeros_like(mx)
    nz = d > 1e-12
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    h *= 60.0
    s = np.where(mx > 1e-12, d / np.maximum(mx, 1e-12), 0.0)
    return np.stack([h, s, mx], axis=1)


# =============================================================================
# Input handling
# =============================================================================
def _load_image(img: ArrayLike) -> np.ndarray:
    """Return float sRGB image HxWx3 in 0..1."""
    if isinstance(img, str):
        from PIL import Image  # lazy import
        img = np.asarray(Image.open(img).convert("RGB"))
    img = np.asarray(img)
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("image must be HxWx3 (RGB)")
    img = img[:, :, :3]
    if np.issubdtype(img.dtype, np.integer):
        return img.astype(np.float64) / 255.0
    img = img.astype(np.float64)
    return img / 255.0 if img.max() > 1.0 else img


def _load_mask(mask: ArrayLike, shape) -> np.ndarray:
    if isinstance(mask, str):
        from PIL import Image
        mask = np.asarray(Image.open(mask).convert("L"))
    mask = np.asarray(mask)
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    mask = mask > 0
    if mask.shape != tuple(shape[:2]):
        raise ValueError(f"mask shape {mask.shape} != image shape {shape[:2]}")
    return mask


# =============================================================================
# Colour correction (critical for flash photos)
# =============================================================================
def color_correct(
    img: np.ndarray,
    gray_card_mask: Optional[ArrayLike] = None,
    gray_card_reflectance: float = 0.18,
    checker_measured_srgb: Optional[np.ndarray] = None,
    checker_reference_srgb: Optional[np.ndarray] = None,
) -> (np.ndarray, str):
    """
    Returns (corrected sRGB image 0..1, method name).

    - Colour checker (preferred): 3x3 matrix fitted by least squares in linear
      space from N measured patches -> reference patch values (both sRGB 0..255).
    - Gray card: per-channel gains in linear space so the card becomes neutral
      at its known reflectance (0.18 for an 18% card). Also normalizes exposure,
      which removes most of the flash-distance effect.
    """
    lin = srgb_to_linear(img)
    if checker_measured_srgb is not None and checker_reference_srgb is not None:
        meas = srgb_to_linear(np.asarray(checker_measured_srgb, float) / 255.0)
        ref = srgb_to_linear(np.asarray(checker_reference_srgb, float) / 255.0)
        if meas.shape[0] < 4:
            raise ValueError("need >= 4 colour-checker patches")
        M, *_ = np.linalg.lstsq(meas, ref, rcond=None)
        out = lin.reshape(-1, 3) @ M
        return linear_to_srgb(out.reshape(img.shape)), "color_checker_3x3"
    if gray_card_mask is not None:
        gm = _load_mask(gray_card_mask, img.shape)
        if gm.sum() < 50:
            raise ValueError("gray card mask too small (< 50 px)")
        card = np.median(lin[gm], axis=0)
        if np.any(card < 1e-4) or np.any(card > 0.98):
            raise ValueError("gray card is black or clipped; re-shoot")
        gains = gray_card_reflectance / card
        return linear_to_srgb(lin * gains), "gray_card"
    return img, "none"


# =============================================================================
# Feature extraction
# =============================================================================
def _pixel_quality(raw: np.ndarray, leaf: np.ndarray):
    """Glare (flash specular / sensor clipping) and shadow masks on RAW pixels."""
    hsv = rgb_to_hsv(raw.reshape(-1, 3)).reshape(raw.shape)
    clipped = (raw >= 250 / 255).any(axis=2)
    specular = (hsv[..., 2] > 0.92) & (hsv[..., 1] < 0.20)
    glare = (clipped | specular) & leaf
    shadow = (hsv[..., 2] < 0.08) & leaf
    return glare, shadow


def extract_features(
    image: ArrayLike,
    leaf_mask: ArrayLike,
    gray_card_mask: Optional[ArrayLike] = None,
    gray_card_reflectance: float = 0.18,
    checker_measured_srgb: Optional[np.ndarray] = None,
    checker_reference_srgb: Optional[np.ndarray] = None,
) -> Dict:
    """
    Compute colour features on valid leaf pixels.
    Use THIS function both for calibration photos and for prediction, so the
    pipeline is identical.
    """
    raw = _load_image(image)
    leaf = _load_mask(leaf_mask, raw.shape)
    n_leaf = int(leaf.sum())
    if n_leaf == 0:
        raise ValueError("leaf mask is empty")

    glare, shadow = _pixel_quality(raw, leaf)
    valid = leaf & ~glare & ~shadow
    n_valid = int(valid.sum())

    img, cc_method = color_correct(raw, gray_card_mask, gray_card_reflectance,
                                   checker_measured_srgb, checker_reference_srgb)

    px = img[valid]                         # (N,3) corrected sRGB 0..1
    R, G, B = px[:, 0], px[:, 1], px[:, 2]
    eps = 1e-9
    tot = R + G + B + eps
    r, g, b = R / tot, G / tot, B / tot

    hsv = rgb_to_hsv(px)
    H, S, V = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    lab = linear_rgb_to_lab(srgb_to_linear(px))

    # DGCI (Karcher & Richardson 2003): higher = darker green
    dgci = ((H - 60.0) / 60.0 + (1.0 - S) + (1.0 - V)) / 3.0

    exg = 2 * g - r - b
    exr = 1.4 * r - g
    vari_den = G + R - B
    vari_ok = np.abs(vari_den) > 0.02

    per_pixel = {
        "dgci": dgci,
        "ngrdi": (G - R) / (G + R + eps),
        "exg": exg,
        "exgr": exg - exr,
        "gli": (2 * G - R - B) / (2 * G + R + B + eps),
        "vari": np.where(vari_ok, (G - R) / np.where(vari_ok, vari_den, 1), np.nan),
        "mgrvi": (G ** 2 - R ** 2) / (G ** 2 + R ** 2 + eps),
        "rgbvi": (G ** 2 - B * R) / (G ** 2 + B * R + eps),
        "r_chrom": r, "g_chrom": g, "b_chrom": b,
        "lab_L": lab[:, 0], "lab_a": lab[:, 1], "lab_b": lab[:, 2],
        # CIELAB hue angle: ~95-105 deg yellow-green, ~120-135 deg deep green.
        # It barely changes with exposure, so it is used for comparisons with
        # photos taken under other lighting (built-in reference).
        "lab_hue": np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360,
        "lab_chroma": np.hypot(lab[:, 1], lab[:, 2]),
        "hue_deg": H, "saturation": S, "brightness": V,
    }

    feats = {k: (float(np.nanmedian(v)) if n_valid else float("nan"))
             for k, v in per_pixel.items()}
    if n_valid:
        q25, q75 = np.percentile(dgci, [25, 75])
        feats["dgci_iqr"] = float(q75 - q25)          # patchiness / chlorosis spread
        feats["frac_yellowish"] = float(np.mean((H > 35) & (H < 75)))
        feats["frac_brownish"] = float(np.mean(H <= 35))
    quality = {
        "leaf_pixels": n_leaf,
        "valid_pixels": n_valid,
        "valid_fraction": round(n_valid / n_leaf, 4),
        "glare_fraction": round(float(glare.sum()) / n_leaf, 4),
        "shadow_fraction": round(float(shadow.sum()) / n_leaf, 4),
        "color_correction": cc_method,
    }
    return {"features": feats, "quality": quality}
