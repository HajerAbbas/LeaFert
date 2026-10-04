"""
explain.py - turns a maize_core.assess() result into (a) step events for the
live timeline and (b) plain-language reasoning, in English and Arabic.
"""

from __future__ import annotations

from typing import List

from maize_core import REFERENCE, TEST

N_PHOTOS = REFERENCE["dataset"]["photos"]
GROUP_YELLOW = {g: REFERENCE["groups"][g]["frac_yellowish"] for g in REFERENCE["groups"]}

STATUS = {"en": {"low": "Low nitrogen", "adequate": "Nitrogen adequate"},
          "ar": {"low": "نيتروجين منخفض", "adequate": "النيتروجين كافٍ"}}
CONF = {"en": {"high": "High confidence", "medium": "Medium confidence", "low": "Low confidence"},
        "ar": {"high": "ثقة عالية", "medium": "ثقة متوسطة", "low": "ثقة منخفضة"}}

T = {
    "en": {
        "s_quality": "Checking photo quality", "s_detect": "Finding the plant",
        "s_measure": "Measuring leaf colour", "s_level": "Estimating nitrogen level", "s_plan": "Building the fertilizer plan",
        "sharp": "sharpness {b:.0f}, brightness {m:.2f}", "blurry": " (blurry)", "dark": " (too dark)",
        "covers": "Plant covers {p}% of the photo", "no_plant": "Not enough plant in the photo ({p}%)",
        "colour": "Yellow share {y}%, glare {g}%", "skipped": "Skipped",
        "level": "≈ {n} kg N/ha → {s}, {c}",
        "plan_apply": "Add {d} kg N/ha", "plan_check": "Add {d} kg N/ha after a leaf check", "plan_none": "No nitrogen needed now",
        "unreadable": "The file is not a readable image",
        "r_ok": "The photo is sharp and bright enough to measure.",
        "r_blurry": "The photo is blurry, so colour cannot be measured reliably.",
        "r_dark": "The photo is too dark; colour readings would be wrong.",
        "r_plant": "Green plant tissue covers {p}% of the photo.",
        "r_noplant": "Less than 12% of the photo is plant, so there is too little to measure.",
        "r_glare": "{g}% of the plant had glare and was left out.",
        "r_yellow": "{y}% of the plant is yellowish. In the field trial, unfertilized plants had {n0}% and "
                    "fertilized plants {nf}%.",
        "r_level": "From 17 colour measures, the plant's nitrogen level matches a crop given about {n} kg N/ha.",
        "r_low": "That is below the {cut} kg N/ha line where trial plants were short of nitrogen.",
        "r_ok_n": "That is above the {cut} kg N/ha line, in the range of well-fertilized trial plants.",
        "r_conf": "{c}: on {t} test photos, results like this were right {a}% of the time.",
        "r_plan": "In the trial, plants given 75 kg N/ha looked as green as plants given the full 136 kg N/ha, "
                  "so 75 kg N/ha is the corrective dose.",
        "r_unusual": "This photo differs from the trial photos (light, camera or growth stage), so confidence was lowered one step.",
        "r_brown": "Some tissue looks brown: check for disease or drought as well.",
    },
    "ar": {
        "s_quality": "فحص جودة الصورة", "s_detect": "العثور على النبات",
        "s_measure": "قياس لون الأوراق", "s_level": "تقدير مستوى النيتروجين", "s_plan": "إعداد خطة التسميد",
        "sharp": "الوضوح {b:.0f}، الإضاءة {m:.2f}", "blurry": " (غير واضحة)", "dark": " (مظلمة)",
        "covers": "النبات يغطي {p}٪ من الصورة", "no_plant": "لا يوجد ما يكفي من النبات في الصورة ({p}٪)",
        "colour": "نسبة الاصفرار {y}٪، الانعكاس {g}٪", "skipped": "تم التخطي",
        "level": "≈ {n} كغ نيتروجين/هكتار ← {s}، {c}",
        "plan_apply": "أضف {d} كغ نيتروجين/هكتار", "plan_check": "أضف {d} كغ نيتروجين/هكتار بعد فحص الأوراق",
        "plan_none": "لا حاجة إلى نيتروجين الآن",
        "unreadable": "الملف ليس صورة يمكن قراءتها",
        "r_ok": "الصورة واضحة ومضاءة بما يكفي للقياس.",
        "r_blurry": "الصورة غير واضحة، لذا لا يمكن قياس اللون بدقة.",
        "r_dark": "الصورة مظلمة جدًا، وقراءات اللون ستكون خاطئة.",
        "r_plant": "أنسجة النبات الخضراء تغطي {p}٪ من الصورة.",
        "r_noplant": "أقل من 12٪ من الصورة نبات، وهذا قليل جدًا للقياس.",
        "r_glare": "{g}٪ من النبات عليه انعكاس وتم استبعاده.",
        "r_yellow": "{y}٪ من النبات مصفرّ. في التجربة الحقلية كانت النسبة {n0}٪ للنباتات غير المسمّدة و{nf}٪ للمسمّدة.",
        "r_level": "من 17 مقياسًا لونيًا، يطابق مستوى النيتروجين في النبات محصولًا حصل على حوالي {n} كغ نيتروجين/هكتار.",
        "r_low": "وهذا أقل من خط {cut} كغ نيتروجين/هكتار الذي كانت النباتات دونه ناقصة النيتروجين في التجربة.",
        "r_ok_n": "وهذا أعلى من خط {cut} كغ نيتروجين/هكتار، ضمن نطاق النباتات جيدة التسميد في التجربة.",
        "r_conf": "{c}: على {t} صورة اختبار، كانت نتائج كهذه صحيحة بنسبة {a}٪.",
        "r_plan": "في التجربة، بدت النباتات التي حصلت على 75 كغ نيتروجين/هكتار بنفس اخضرار التي حصلت على 136 كغ كاملة، "
                  "لذا فإن 75 كغ نيتروجين/هكتار هي الجرعة التصحيحية.",
        "r_unusual": "هذه الصورة تختلف عن صور التجربة (الإضاءة أو الكاميرا أو مرحلة النمو)، لذا خُفّضت الثقة درجة واحدة.",
        "r_brown": "بعض الأنسجة تبدو بنية: افحص أيضًا وجود مرض أو جفاف.",
    },
}


def pct(v: float) -> str:
    return f"{v * 100:.0f}"


def steps(a: dict, lang: str) -> List[dict]:
    t = T[lang]
    q, det, f = a.get("quality"), a.get("detection") or {}, a.get("features")
    if not q:
        return [dict(id="quality", group="measure", status="error", label=t["s_quality"], detail=t["unreadable"])]
    ev = []
    bad = q["is_blurry"] or q["is_too_dark"]
    d = t["sharp"].format(b=q["blur_score"], m=q["mean_brightness"])
    d += (t["blurry"] if q["is_blurry"] else "") + (t["dark"] if q["is_too_dark"] else "")
    ev.append(dict(id="quality", group="measure", status="warn" if bad else "done", label=t["s_quality"], detail=d))
    p = pct(det.get("green_fraction", 0))
    no_plant = "no_plant" in a.get("reasons", [])
    ev.append(dict(id="detect", group="measure", status="error" if no_plant else "done", label=t["s_detect"],
                   detail=(t["no_plant"] if no_plant else t["covers"]).format(p=p)))
    if not f:
        for sid, key in (("measure", "s_measure"), ("level", "s_level"), ("plan", "s_plan")):
            ev.append(dict(id=sid, group="measure", status="skip", label=t[key], detail=t["skipped"]))
        return ev
    g = (a.get("pixel_quality") or {}).get("glare_fraction", 0)
    ev.append(dict(id="measure", group="measure", status="done", label=t["s_measure"],
                   detail=t["colour"].format(y=pct(f["frac_yellowish"]), g=f"{g * 100:.1f}")))
    ev.append(dict(id="level", group="measure", status="done", label=t["s_level"],
                   detail=t["level"].format(n=round(a["level_kg"]), s=STATUS[lang][a["status"]],
                                            c=CONF[lang][a["confidence"]].lower() if lang == "en" else CONF[lang][a["confidence"]])))
    plan = a["plan"]
    key = {"apply": "plan_apply", "check_then_apply": "plan_check"}.get(plan["action"], "plan_none")
    ev.append(dict(id="plan", group="measure", status="done", label=t["s_plan"],
                   detail=t[key].format(d=plan["dose_kg_n_ha"])))
    return ev


def reasoning(a: dict, lang: str) -> List[str]:
    t = T[lang]
    q, det, f = a.get("quality") or {}, a.get("detection") or {}, a.get("features")
    out = []
    if q:
        if q["is_blurry"]:
            out.append(t["r_blurry"])
        if q["is_too_dark"]:
            out.append(t["r_dark"])
        if not (q["is_blurry"] or q["is_too_dark"]):
            out.append(t["r_ok"])
    if det:
        out.append(t["r_noplant"] if "no_plant" in a.get("reasons", []) else t["r_plant"].format(p=pct(det["green_fraction"])))
    if not f:
        return out
    g = (a.get("pixel_quality") or {}).get("glare_fraction", 0)
    if g > 0.02:
        out.append(t["r_glare"].format(g=pct(g)))
    out.append(t["r_yellow"].format(y=pct(f["frac_yellowish"]), n0=pct(GROUP_YELLOW["N0"]),
                                    nf=pct((GROUP_YELLOW["N75"] + GROUP_YELLOW["NFull"]) / 2)))
    out.append(t["r_level"].format(n=round(a["level_kg"])))
    out.append((t["r_low"] if a["status"] == "low" else t["r_ok_n"]).format(cut=a["cut_kg"]))
    out.append(t["r_conf"].format(c=CONF[lang][a["confidence"]], t=TEST["n_photos"], a=pct(a["accuracy"])))
    if "unusual_photo" in a.get("warnings", []):
        out.append(t["r_unusual"])
    if a["status"] == "low":
        out.append(t["r_plan"])
    if "brown_tissue" in a.get("warnings", []):
        out.append(t["r_brown"])
    return out
