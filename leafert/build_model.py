"""
build_model.py - build LeaFert's maize model and reference from per_image.csv
(the measurements of the 1,200 dataset photos made by build_maize_reference.py).

    python build_model.py per_image.csv

Model
-----
* Gradient-boosted regression from 17 lighting-robust colour features to the
  nitrogen rate the plot received (0 / 75 / 136 kg N/ha). Its output is the
  plant's "nitrogen level": the rate a plant with this colour typically got.
* One cut-off on that level (chosen on training photos) gives a decisive
  answer for every photo: low nitrogen or adequate nitrogen.
* Confidence comes from the distance to the cut-off (bands chosen on training
  photos, accuracy measured on held-out photos).
* Fertilizer: in the trial, 75 kg N/ha already gave the same colour as the full
  136 kg N/ha, so 75 kg N/ha is the corrective dose for low-nitrogen plants.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import balanced_accuracy_score, mean_absolute_error, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

HERE = Path(__file__).parent
FEATURES = ["lab_hue", "hue_deg", "ngrdi", "vari", "mgrvi", "r_chrom", "g_chrom", "b_chrom",
            "frac_yellowish", "dgci_iqr", "saturation", "lab_a", "exg", "gli", "exgr", "rgbvi",
            "frac_brownish"]
RATES = {"N0": 0, "N75": 75, "NFull": 136}
BANDS = [("low", 0, 10), ("medium", 10, 25), ("high", 25, 1e9)]       # kg N/ha from the cut-off
FERTILIZERS = [  # name, % N
    ("Urea", 46), ("Ammonium nitrate", 34), ("UAN solution", 32),
    ("Calcium ammonium nitrate (CAN)", 27), ("Ammonium sulfate", 21)]


def make_model():
    return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=300, random_state=0)


def band_of(level, cut):
    d = abs(level - cut)
    return next(n for n, a, b in BANDS if a <= d < b)


def band_stats(level, is_low, cut):
    out = {}
    d = np.abs(level - cut)
    for name, lo, hi in BANDS:
        m = (d >= lo) & (d < hi)
        out[name] = {"share": round(float(m.mean()), 3),
                     "accuracy": round(float(((level[m] < cut) == is_low[m]).mean()), 3) if m.any() else None}
    return out


def main(csv_path: str):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df = df[df["ok"].astype(str) == "True"].copy()
    df["rate"] = df["label"].map(RATES)
    df["low"] = df["rate"] == 0
    tr, te = df[df["split"] != "test"], df[df["split"] == "test"]

    # 1) cut-off chosen on training photos only (out-of-fold predictions)
    skf = StratifiedKFold(5, shuffle=True, random_state=1)
    oof = cross_val_predict(make_model(), tr[FEATURES].values, tr["rate"].values,
                            cv=list(skf.split(tr, tr["label"])))
    cut = max((balanced_accuracy_score(tr["low"], oof < t), int(t)) for t in range(30, 120))[1]

    # 2) one honest test on the untouched photos
    m = make_model().fit(tr[FEATURES].values, tr["rate"].values)
    lvl = np.clip(m.predict(te[FEATURES].values), 0, 136)
    pred_low = lvl < cut
    is_low = te["low"].values
    test = {
        "n_photos": int(len(te)),
        "balanced_accuracy": round(float(balanced_accuracy_score(is_low, pred_low)), 3),
        "auc": round(float(roc_auc_score(is_low, -lvl)), 3),
        "level_mae_kg": round(float(mean_absolute_error(te["rate"], lvl)), 1),
        "level_correlation": round(float(np.corrcoef(lvl, te["rate"])[0, 1]), 2),
        "mean_level_by_group": {g: round(float(lvl[te["label"].values == g].mean()), 1) for g in RATES},
        "by_confidence": band_stats(lvl, is_low, cut),
        "detects_low_n": round(float(pred_low[is_low].mean()), 3),          # sensitivity
        "clears_fertilized": round(float((~pred_low)[~is_low].mean()), 3),  # specificity
        "table": {g: {"low": int(((te["label"] == g).values & pred_low).sum()),
                      "adequate": int(((te["label"] == g).values & ~pred_low).sum())} for g in RATES},
        "dots": [{"group": g, "answer": "low" if l < cut else "adequate", "confidence": band_of(l, cut)}
                 for g, l in zip(te["label"].values, lvl)],
    }

    # 3) final model on ALL photos
    final = make_model().fit(df[FEATURES].values, df["rate"].values)
    joblib.dump({"model": final, "features": FEATURES, "cut": cut, "bands": BANDS,
                 "sklearn": sklearn.__version__}, HERE / "maize_model.joblib")

    ref = {
        "type": "leafert_maize_reference", "version": 3,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {"title": "Nitrogen deficiency in maize: annotated image classification dataset",
                    "authors": "Galic, Podnar Zarko, Novoselnik, Salaic", "year": 2023,
                    "doi": "10.17632/g7xnn2bm4g.1", "photos": int(len(df)),
                    "groups": {g: int((df["label"] == g).sum()) for g in RATES},
                    "conditions": "field trial, July 2023, around flowering, morning daylight, 238 genotypes"},
        "cut_kg": cut,
        "scale_max_kg": 136,
        "bands": [{"name": n, "from_kg": a, "to_kg": (None if b > 1e8 else b)} for n, a, b in BANDS],
        "training_oof": {"balanced_accuracy": round(float(balanced_accuracy_score(tr["low"], oof < cut)), 3),
                         "by_confidence": band_stats(oof, tr["low"].values, cut)},
        "held_out_test": test,
        "fertilizer": {
            "corrective_dose_kg_n_ha": 75,
            "basis": "In the trial, plants given 75 kg N/ha already had the same colour as plants given the "
                     "full 136 kg N/ha, while unfertilized plants were clearly paler.",
            "full_rate_kg_n_ha": 136,
            "products": [{"name": n, "n_percent": p} for n, p in FERTILIZERS],
        },
        "groups": {g: {f: round(float(np.median(df.loc[df["label"] == g, f])), 4)
                       for f in ("frac_yellowish", "lab_hue")} for g in RATES},
        "range": {f: [round(float(v), 4) for v in np.percentile(df[f], [0.1, 99.9])]
                  for f in FEATURES + ["green_fraction"]},
        "features": FEATURES,
    }
    (HERE / "maize_reference.json").write_text(json.dumps(ref, indent=1), encoding="utf-8")
    summary = {k: test[k] for k in ("balanced_accuracy", "auc", "level_mae_kg", "mean_level_by_group",
                                    "by_confidence", "detects_low_n", "clears_fertilized", "table")}
    print(json.dumps({"cut_kg": cut, "test": summary}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "per_image.csv")
