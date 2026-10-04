"""
page.py - the static chapters of the LeaFert site, as HTML strings.

Every text exists in English and Arabic (<span class="en"> / <span class="ar">);
CSS shows the active language, so switching never rebuilds the page or resets
the scroll animations. All illustrations are inline SVG drawn here.
"""

from __future__ import annotations

import random

from maize_core import REFERENCE


def L(en: str, ar: str, tag: str = "span", cls: str = "") -> str:
    c = f" {cls}" if cls else ""
    return f'<{tag} class="en{c}">{en}</{tag}><{tag} class="ar{c}" lang="ar" dir="rtl">{ar}</{tag}>'


# ============================================================================ maize plant symbol
def _leaf(x: float, y: float, length: float, side: int, lift: float, width: float) -> str:
    """One arching maize leaf from the stalk point (x, y). side=-1 left, +1 right."""
    tx, ty = x + side * length, y - lift + length * 0.55          # tip droops below its rise
    c1x, c1y = x + side * length * 0.35, y - lift * 1.6
    c2x, c2y = x + side * length * 0.8, y - lift * 1.2
    # upper edge out, lower edge back: a long tapering crescent
    return (f"M{x:.1f} {y:.1f} C{c1x:.1f} {c1y - width:.1f} {c2x:.1f} {c2y - width * 0.6:.1f} {tx:.1f} {ty:.1f} "
            f"C{c2x - side * 4:.1f} {c2y + width * 0.5:.1f} {c1x:.1f} {c1y + width * 0.9:.1f} {x:.1f} {y + width * 1.4:.1f}Z")


def maize_symbol() -> str:
    leaves = []
    specs = [(330, -1, 120, 60, 9), (285, 1, 130, 66, 9), (240, -1, 125, 70, 8),
             (195, 1, 115, 66, 8), (152, -1, 95, 60, 7), (115, 1, 75, 52, 6)]
    for y, side, length, lift, w in specs:
        leaves.append(f'<path d="{_leaf(100, y, length, side, lift, w)}"/>')
    tassel = []
    for i, (dx, dy) in enumerate([(-22, -30), (-12, -40), (0, -48), (12, -40), (22, -30), (-30, -18), (30, -18)]):
        tassel.append(f'<path d="M100 62 Q{100 + dx * 0.4:.0f} {62 + dy * 0.5:.0f} {100 + dx} {62 + dy}" '
                      f'stroke="#D9BE6A" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    return (
        '<symbol id="maize" viewBox="0 0 200 400" overflow="visible">'
        '<path d="M96.5 400 L95 78 L100 60 L105 78 L103.5 400Z"/>'
        + "".join(leaves)
        + '<path d="M104 236 C118 222 121 196 112 182 C106 196 103 214 104 236Z" fill="#9BB862"/>'
        + '<path d="M112 182 C114 176 118 172 120 168" stroke="#C9A55A" stroke-width="2" fill="none"/>'
        + "".join(tassel)
        + "</symbol>"
    )


def _row(n: int, y: float, scale: float, fill: str, seed: int, spread: float = 1.0) -> str:
    rnd = random.Random(seed)
    out = []
    step = 1440 / n
    for i in range(n + 2):
        x = (i - 0.5) * step + rnd.uniform(-step * 0.3, step * 0.3) * spread
        s = scale * rnd.uniform(0.86, 1.12)
        w, h = 200 * s, 400 * s
        out.append(f'<use href="#maize" x="{x - w / 2:.1f}" y="{y - h:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"/>')
    return "".join(out)


# ============================================================================ brand
def wordmark(cls: str = "") -> str:
    """The LeaFert logo exactly as supplied (www/leafert-logo.png)."""
    return f'<img class="logo {cls}" src="leafert-logo.png" alt="LeaFert" width="483" height="139">'


# ============================================================================ hero
def hero() -> str:
    t = REFERENCE["held_out_test"]
    hi = t["by_confidence"]["high"]["accuracy"]
    return f"""
<section id="top" class="hero" aria-labelledby="hero-title">
  <svg class="hero-art" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <defs>
      {maize_symbol()}
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#1D2C16"/><stop offset=".5" stop-color="#3E5E2A"/>
        <stop offset=".78" stop-color="#7FA24F"/><stop offset="1" stop-color="#C9DE86"/>
      </linearGradient>
      <radialGradient id="sun" cx=".5" cy=".5" r=".5">
        <stop offset="0" stop-color="#F3FBC4"/><stop offset=".4" stop-color="#C8EB6A" stop-opacity=".75"/>
        <stop offset="1" stop-color="#9FD848" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect width="1440" height="900" fill="url(#sky)"/>
    <g class="layer" data-depth="0.55"><circle cx="1080" cy="600" r="260" fill="url(#sun)"/></g>
    <g class="layer" data-depth="0.45">
      <path d="M0 650 C220 612 420 640 640 622 C880 602 1100 634 1440 606 L1440 900 L0 900Z" fill="#6F9A4A"/>
    </g>
    <g class="layer" data-depth="0.36">{_row(34, 668, 0.30, "#5C8A3E", 3)}
      <path d="M0 663 L1440 663 L1440 900 L0 900Z" fill="#5E8B40"/></g>
    <g class="layer" data-depth="0.24">{_row(20, 752, 0.55, "#40692D", 7)}
      <path d="M0 747 L1440 747 L1440 900 L0 900Z" fill="#456F31"/></g>
    <g class="layer" data-depth="0.12">{_row(11, 900, 0.86, "#2A4A1F", 11)}
      <path d="M0 880 L1440 880 L1440 900 L0 900Z" fill="#22401B"/></g>
    <g class="layer" data-depth="-0.08">
      <path d="M-40 900 C40 760 150 700 300 690 C180 730 110 800 90 900Z" fill="#132A15"/>
      <path d="M1480 900 C1400 740 1270 680 1110 676 C1240 720 1330 800 1352 900Z" fill="#132A15"/>
      <path d="M1440 900 C1380 800 1290 760 1190 770 C1290 790 1350 840 1362 900Z" fill="#7FDD3A"/>
    </g>
  </svg>
  <div class="hero-copy" data-depth="0.3">
    <h1 id="hero-title">{L("Know your maize's nitrogen from one photo.", "اعرف نيتروجين ذرتك من صورة واحدة.")}</h1>
    <p class="lede">{L("LeaFert estimates the nitrogen level of your maize, tells you if it is low, and gives you "
                       "the fertilizer amount to add per hectare and per dunam.",
                       "يقدّر LeaFert مستوى النيتروجين في ذرتك، ويخبرك إن كان منخفضًا، ويعطيك كمية السماد "
                       "المطلوبة لكل هكتار ولكل دونم.")}</p>
    <div class="hero-actions">
      <a class="btn-lime" href="#tool">{L("Check a plant", "افحص نباتًا")}</a>
      <p class="proof">{L(f"Trained on 1,200 field-trial photos and right {hi * 100:.0f}% of the time on high-confidence results.",
                          f"مدرَّب على 1200 صورة من تجربة حقلية، ودقيق بنسبة {hi * 100:.0f}٪ في النتائج عالية الثقة.")}</p>
    </div>
  </div>
  <a class="scroll-cue" href="#story" aria-label="Scroll down"><span></span></a>
</section>
"""


# ============================================================================ story: the yellowing leaf
def story() -> str:
    n0 = REFERENCE["groups"]["N0"]["frac_yellowish"]
    nf = (REFERENCE["groups"]["N75"]["frac_yellowish"] + REFERENCE["groups"]["NFull"]["frac_yellowish"]) / 2
    leaf = ("M30 122 C200 70 470 58 700 86 C830 104 930 138 985 162 "
            "C930 172 830 192 700 206 C470 236 200 228 30 180Z")
    steps = [
        ("Nitrogen moves to new growth",
         "When a maize plant runs short of nitrogen, it takes nitrogen out of its older, lower leaves "
         "and sends it to the young leaves at the top.",
         "النيتروجين ينتقل إلى النمو الجديد",
         "عندما ينقص النيتروجين في نبات الذرة، يسحبه من الأوراق السفلية الأقدم ويرسله إلى الأوراق الصغيرة في الأعلى."),
        ("Yellowing starts at the tip",
         "The lower leaves turn yellow from the tip inward, along the midrib, in a V shape. "
         "Keep scrolling to watch it spread.",
         "الاصفرار يبدأ من الطرف",
         "تصفرّ الأوراق السفلية من الطرف نحو الداخل على طول العرق الأوسط بشكل حرف V. "
         "تابع التمرير لترى كيف ينتشر."),
        ("The camera counts the yellow",
         f"In the field photos, unfertilized plants had about {n0 * 100:.0f}% yellowish leaf pixels and "
         f"fertilized plants about {nf * 100:.0f}%. The app measures this, and more, in your photo.",
         "الكاميرا تحسب الاصفرار",
         f"في الصور الحقلية كانت نسبة البكسلات المصفرّة حوالي {n0 * 100:.0f}٪ في النباتات غير المسمّدة "
         f"وحوالي {nf * 100:.0f}٪ في المسمّدة. يقيس التطبيق ذلك وأكثر في صورتك."),
    ]
    items = "".join(
        f'<li class="story-step" data-step="{i}"><h3>{L(a, c)}</h3><p>{L(b, d)}</p></li>'
        for i, (a, b, c, d) in enumerate(steps))
    return f"""
<section id="story" class="story" data-n0="{n0:.4f}" data-nf="{nf:.4f}" aria-label="How nitrogen shortage looks">
  <div class="story-sticky">
    <figure class="story-leaf">
      <svg viewBox="0 0 1000 300" role="img" aria-label="A maize leaf turning yellow from the tip along the midrib">
        <defs>
          <clipPath id="leafclip"><path d="{leaf}"/></clipPath>
          <linearGradient id="leafgreen" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="#2E7D3E"/><stop offset="1" stop-color="#3E8E45"/>
          </linearGradient>
        </defs>
        <path d="{leaf}" fill="url(#leafgreen)"/>
        <g clip-path="url(#leafclip)">
          <g id="vgroup" transform="translate(985 162) scale(0.001 1) translate(-985 -162)">
            <path d="M985 40 L260 158 L985 290 Z" fill="#E8CB6A" opacity=".75"/>
            <path d="M985 60 L400 158 L985 270 Z" fill="#E0A82E"/>
            <path d="M985 162 L110 152 C96 156 96 164 110 168 Z" fill="#EBCD5C"/>
            <path d="M985 110 L860 162 L985 214 Z" fill="#B7832A"/>
          </g>
          <path d="M30 151 C300 147 700 152 985 162" stroke="#F4F1D0" stroke-width="4" fill="none" opacity=".75"/>
          <g stroke="#1F5E2E" stroke-width="1.2" opacity=".3" fill="none">
            <path d="M40 136 C300 118 700 110 960 156"/><path d="M40 166 C300 184 700 192 960 166"/>
            <path d="M50 124 C300 98 700 94 940 150"/><path d="M50 178 C300 202 700 208 940 172"/>
            <path d="M60 112 C300 84 690 78 900 136"/><path d="M60 190 C300 216 690 222 900 186"/>
          </g>
        </g>
      </svg>
      <figcaption>
        <span class="yshare"><b id="yshare-num">{nf * 100:.0f}%</b> {L("yellowish pixels", "بكسلات مصفرّة")}</span>
        <span class="yscale" aria-hidden="true"><i id="yshare-bar"></i></span>
        <span class="yends">{L("like fertilized plants", "مثل النباتات المسمّدة")}{L("like unfertilized plants", "مثل غير المسمّدة")}</span>
      </figcaption>
    </figure>
    <ol class="story-steps">{items}</ol>
  </div>
</section>
"""


# ============================================================================ how it works
def how() -> str:
    steps = [
        ("Take a photo", "The upper part of one plant in daylight, filling most of the frame.",
         "التقط صورة", "الجزء العلوي من نبات واحد في ضوء النهار، يملأ معظم الإطار."),
        ("Find the plant", "Plant pixels are separated from sky, soil and glare.",
         "العثور على النبات", "تُفصل بكسلات النبات عن السماء والتربة والانعكاسات."),
        ("Estimate nitrogen", "Seventeen colour measures give the nitrogen level in kg N per hectare.",
         "تقدير النيتروجين", "سبعة عشر مقياسًا لونيًا تعطي مستوى النيتروجين بالكيلوغرام لكل هكتار."),
        ("Get the fertilizer plan", "How much nitrogen to add, in urea and four other common products, "
         "per hectare and per dunam.",
         "خطة التسميد", "كمية النيتروجين المطلوبة باليوريا وأربعة أسمدة شائعة أخرى، لكل هكتار ولكل دونم."),
    ]
    li = "".join(f'<li><span class="how-n">{i + 1}</span><h3>{L(a, c)}</h3><p>{L(b, d)}</p></li>'
                 for i, (a, b, c, d) in enumerate(steps))
    return f"""
<section id="how" class="how">
  <h2>{L("From photo to fertilizer plan", "من الصورة إلى خطة التسميد")}</h2>
  <ol class="how-steps">{li}</ol>
</section>
"""


# ============================================================================ evidence
def evidence() -> str:
    t = REFERENCE["held_out_test"]
    names = {"N0": ("No nitrogen (0 kg)", "بدون نيتروجين (0 كغ)"),
             "N75": ("75 kg N/ha", "75 كغ نيتروجين/هكتار"),
             "NFull": ("136 kg N/ha", "136 كغ نيتروجين/هكتار")}
    order = {"high": 0, "medium": 1, "low": 2}
    rows, k = [], 0
    for g in ("N0", "N75", "NFull"):
        ds = sorted([d for d in t["dots"] if d["group"] == g],
                    key=lambda d: (d["answer"] != "low", order[d["confidence"]] if d["answer"] == "low" else -order[d["confidence"]]))
        dots = []
        for d in ds:
            dots.append(f'<i class="dot d-{d["answer"]} c-{d["confidence"]}" style="--i:{k}"></i>')
            k += 1
        n_low, n_ok = t["table"][g]["low"], t["table"][g]["adequate"]
        count = L(f"{n_low} low, {n_ok} adequate", f"{n_low} منخفض، {n_ok} كافٍ")
        dots_html = "".join(dots)
        rows.append(f'<div class="ev-row"><div class="ev-label">{L(*names[g])}</div>'
                    f'<div class="ev-dots">{dots_html}</div>'
                    f'<div class="ev-count">{count}</div></div>')
    bc = t["by_confidence"]
    kpis = [
        (f'{t["balanced_accuracy"] * 100:.0f}%', "overall accuracy on 240 photos it never saw (balanced)",
         "الدقة الإجمالية على 240 صورة لم يرها (متوازنة)"),
        (f'{bc["high"]["accuracy"] * 100:.0f}%', f'accuracy on high-confidence results, {bc["high"]["share"] * 100:.0f}% of all photos',
         f'الدقة في النتائج عالية الثقة، وهي {bc["high"]["share"] * 100:.0f}٪ من كل الصور'),
        (f'{t["detects_low_n"] * 100:.0f}%', "of nitrogen-short plants detected",
         "من النباتات ناقصة النيتروجين تم اكتشافها"),
    ]
    kp = "".join(f'<div class="kpi"><b>{v}</b><span>{L(a, b)}</span></div>' for v, a, b in kpis)
    return f"""
<section id="evidence" class="evidence">
  <div class="ev-inner">
    <h2>{L("Proven on photos it had never seen", "مُثبت على صور لم يرها من قبل")}</h2>
    <div class="kpis">{kp}</div>
    <p class="ev-lede">{L("Every dot is one test photo, grouped by the nitrogen the plot really received and coloured by "
                          "LeaFert's answer. Faded dots are low-confidence results.",
                          "كل نقطة صورة اختبار واحدة، مجمّعة حسب النيتروجين الذي حصلت عليه القطعة فعلًا وملوّنة حسب "
                          "إجابة LeaFert. النقاط الباهتة نتائج منخفضة الثقة.")}</p>
    <div class="ev-legend">
      <span><i class="dot d-low"></i>{L("low nitrogen", "نيتروجين منخفض")}</span>
      <span><i class="dot d-adequate"></i>{L("nitrogen adequate", "النيتروجين كافٍ")}</span>
      <span><i class="dot d-adequate c-low"></i>{L("low confidence", "ثقة منخفضة")}</span>
    </div>
    <div class="ev-chart">{"".join(rows)}</div>
    <div class="ev-notes">
      <p>{L(f"High-confidence results cover {bc['high']['share'] * 100:.0f}% of photos and are right {bc['high']['accuracy'] * 100:.0f}% of the time; "
            f"medium {bc['medium']['accuracy'] * 100:.0f}%. Low-confidence results ask you to check the leaves before fertilizing.",
            f"النتائج عالية الثقة تغطي {bc['high']['share'] * 100:.0f}٪ من الصور وصحيحة بنسبة {bc['high']['accuracy'] * 100:.0f}٪، "
            f"والمتوسطة {bc['medium']['accuracy'] * 100:.0f}٪. النتائج منخفضة الثقة تطلب منك فحص الأوراق قبل التسميد.")}</p>
      <p>{L("Plants given 75 kg and 136 kg of nitrogen look the same in colour. That is why LeaFert's corrective "
            "dose is 75 kg N/ha: in the trial it was enough to reach full colour.",
            "النباتات التي حصلت على 75 و136 كغ نيتروجين متشابهة في اللون. لهذا فإن الجرعة التصحيحية في LeaFert "
            "هي 75 كغ نيتروجين/هكتار: كانت كافية في التجربة للوصول إلى اللون الكامل.")}</p>
      <p>{L(f"It detects {t['detects_low_n'] * 100:.0f}% of nitrogen-short plants and correctly clears "
            f"{t['clears_fertilized'] * 100:.0f}% of fertilized ones, so most plants that need nitrogen get it and "
            "most that don't are left alone.",
            f"يكتشف {t['detects_low_n'] * 100:.0f}٪ من النباتات ناقصة النيتروجين ويؤكد سلامة "
            f"{t['clears_fertilized'] * 100:.0f}٪ من المسمّدة، فتحصل معظم النباتات المحتاجة على النيتروجين وتُترك "
            "معظم غير المحتاجة.")}</p>
    </div>
  </div>
</section>
"""


# ============================================================================ good to know + sources
def limits() -> str:
    d = REFERENCE["dataset"]
    items = [
        ("Best photo.", "Upper plant, morning daylight, no flash, around flowering: the conditions of the trial photos.",
         "أفضل صورة.", "الجزء العلوي من النبات، ضوء الصباح، بدون فلاش، حول فترة الإزهار: ظروف صور التجربة."),
        ("Your soil test comes first.", "The plan is a corrective dose from the trial. If a soil or tissue test or "
         "your agronomist gives a rate for your field, use that.",
         "تحليل تربتك أولًا.", "الخطة جرعة تصحيحية من التجربة. إذا أعطى تحليل التربة أو الأنسجة أو مهندسك الزراعي معدلًا لحقلك فاستخدمه."),
        ("Other causes of yellowing.", "Drought, heat, waterlogging and other nutrient shortages can look similar; "
         "the assistant points them out when it sees them.",
         "أسباب أخرى للاصفرار.", "الجفاف والحرارة والتشبع بالماء ونقص العناصر الأخرى قد تبدو مشابهة، ويشير إليها المساعد عندما يراها."),
    ]
    li = "".join(f"<li><b>{L(a, c)}</b> {L(b, e)}</li>" for a, b, c, e in items)
    return f"""
<section id="limits" class="limits">
  <h2>{L("Good to know", "معلومات مهمة")}</h2>
  <ul class="limit-list">{li}</ul>
  <h3>{L("Data source", "مصدر البيانات")}</h3>
  <p class="source">{d['authors']} ({d['year']}). <i>{d['title']}</i>. Mendeley Data.
     <a href="https://doi.org/{d['doi']}" target="_blank" rel="noopener">doi.org/{d['doi']}</a></p>
</section>
"""
