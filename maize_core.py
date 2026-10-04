"""
maize_core.py - one photo -> LeaFert's maize nitrogen assessment and fertilizer plan.

    assess(photo_bytes) -> dict

decode -> quality (blur, darkness) -> plant detection -> colour features
(leaf_colour.extract_features, identical to the training photos) -> model ->
nitrogen level (kg N/ha equivalent, 0-136) -> status (low / adequate) ->
confidence (distance from the cut-off) -> fertilizer plan.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

from leaf_colour import extract_features
from leaf_core import _preview_jpeg_b64, check_quality, decode_image, detect_leaf, overlay_jpeg_b64

HERE = Path(__file__).parent
REFERENCE = json.loads((HERE / "maize_reference.json").read_text(encoding="utf-8"))
TEST = REFERENCE["held_out_test"]
FERT = REFERENCE["fertilizer"]
MIN_PLANT_FRACTION = 0.12        # training photos: 20-71% of the frame is plant
UNUSUAL_LIMIT = 5                # features outside the training range -> lower confidence
ORDER = ["low", "medium", "high"]
UAN_DENSITY = 1.32               # kg per litre for UAN 32

_MODEL = None
_LOCK = threading.Lock()


def model() -> dict:
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            import joblib
            _MODEL = joblib.load(HERE / "maize_model.joblib")
        return _MODEL


def fertilizer_plan(status: str, confidence: str) -> dict:
    """Corrective dose from the trial (75 kg N/ha matched the full rate), as product amounts."""
    if status != "low":
        return {"action": "none", "dose_kg_n_ha": 0, "products": []}
    dose = FERT["corrective_dose_kg_n_ha"]
    products = []
    for p in FERT["products"]:
        per_ha = dose / (p["n_percent"] / 100)
        item = {"name": p["name"], "n_percent": p["n_percent"], "kg_per_ha": int(round(per_ha)),
                "kg_per_1000m2": round(per_ha / 10, 1)}                 # 1,000 m2 = 1 dunam = 0.1 ha
        if p["name"].startswith("UAN"):                                 # liquid: also in litres
            item["litres_per_ha"] = int(round(per_ha / UAN_DENSITY))
            item["litres_per_1000m2"] = round(per_ha / UAN_DENSITY / 10, 1)
        products.append(item)
    return {"action": "check_then_apply" if confidence == "low" else "apply",
            "dose_kg_n_ha": dose, "split": dose > 50, "products": products}


def assess(data: bytes, previews: bool = True) -> dict:
    out = {"decision": "retake", "reasons": [], "quality": None, "detection": None, "features": None,
           "level_kg": None, "cut_kg": None, "status": None, "confidence": None, "accuracy": None, "plan": None,
           "unusual": [], "warnings": []}
    try:
        rgb = decode_image(data)
    except ValueError:
        out["reasons"].append("unreadable")
        return out

    q = check_quality(rgb)
    det, mask = detect_leaf(rgb)
    out["quality"], out["detection"] = q, det
    if previews:
        out["image_jpeg_base64"] = _preview_jpeg_b64(rgb)
        out["mask_overlay_jpeg_base64"] = overlay_jpeg_b64(rgb, mask)
    if q["is_blurry"]:
        out["reasons"].append("image_blurry")
    if q["is_too_dark"]:
        out["reasons"].append("image_too_dark")
    if not det["leaf_detected"] or det["green_fraction"] < MIN_PLANT_FRACTION:
        out["reasons"].append("no_plant")
    if out["reasons"]:
        return out

    ex = extract_features(rgb, mask)
    f, fq = dict(ex["features"]), ex["quality"]
    if fq["valid_pixels"] < 500:
        out["reasons"].append("too_much_glare")
        return out
    f["green_fraction"] = det["green_fraction"]
    out["features"] = {k: (round(float(v), 5) if v is not None else None) for k, v in f.items()}
    out["pixel_quality"] = fq

    m = model()
    x = np.array([[f[k] for k in m["features"]]], float)
    level = float(np.clip(m["model"].predict(x)[0], 0, REFERENCE["scale_max_kg"]))
    cut = m["cut"]
    status = "low" if level < cut else "adequate"
    dist = abs(level - cut)
    confidence = next(name for name, a, b in m["bands"] if a <= dist < b)

    rng = REFERENCE["range"]
    unusual = [k for k in m["features"] + ["green_fraction"]
               if k in rng and f.get(k) is not None and not (rng[k][0] <= f[k] <= rng[k][1])]
    out["unusual"] = unusual
    if len(unusual) >= UNUSUAL_LIMIT and confidence != "low":
        confidence = ORDER[ORDER.index(confidence) - 1]            # flexible: lower, never refuse
        out["warnings"].append("unusual_photo")
    if fq.get("glare_fraction", 0) > 0.15:
        out["warnings"].append("glare")
    if f.get("frac_brownish", 0) > 0.05:
        out["warnings"].append("brown_tissue")

    out.update(decision="ok", level_kg=round(level, 1), cut_kg=cut, status=status,
               confidence=confidence, accuracy=TEST["by_confidence"][confidence]["accuracy"],
               plan=fertilizer_plan(status, confidence))
    return out


def slim(a: dict) -> dict:
    """What the AI agent sees (no images, no per-photo test data)."""
    f = a.get("features") or {}
    return {
        "decision": a.get("decision"), "reasons": a.get("reasons"),
        "nitrogen_level_kg_n_ha_equivalent": a.get("level_kg"), "cut_kg": a.get("cut_kg"),
        "status": a.get("status"), "confidence": a.get("confidence"),
        "accuracy_at_this_confidence": a.get("accuracy"),
        "fertilizer_plan": a.get("plan"), "warnings": a.get("warnings"),
        "plant_fraction": (a.get("detection") or {}).get("green_fraction"),
        "yellow_share": f.get("frac_yellowish"), "brown_share": f.get("frac_brownish"),
        "typical_yellow_share": {g: REFERENCE["groups"][g]["frac_yellowish"] for g in REFERENCE["groups"]},
        "model_test": {k: TEST[k] for k in ("balanced_accuracy", "auc", "by_confidence", "mean_level_by_group")},
    }
