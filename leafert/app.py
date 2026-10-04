"""
LeaFert - maize nitrogen check and fertilizer plan (Shiny for Python, scroll-driven site).

Chapters: hero (parallax field) -> story (leaf yellowing with scroll) -> how it
works -> the tool (camera, nitrogen level, fertilizer plan, AI assistant, chat)
-> evidence -> good to know.

Run:  shiny run app.py
Env:  GOOGLE_API_KEY (AI assistant; measurement and plan work without it),
      OPENWEATHER_API_KEY (optional weather check)
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from shiny import App, reactive, render, ui

import agent as ag
import quota
from explain import CONF, GROUP_YELLOW, STATUS, pct, reasoning, steps
from maize_core import REFERENCE, assess
from page import L, evidence, hero, how, limits, story, wordmark

WWW = Path(__file__).parent / "www"
SCALE = REFERENCE["scale_max_kg"]

TXT = {
    "en": {
        "empty": "Your nitrogen result and fertilizer plan appear here. Take or upload a photo of the upper part of one maize plant.",
        "retake": "Take the photo again", "noplant": "No maize plant found",
        "tips": {"no_plant": "Fill most of the frame with the upper part of one plant.",
                 "image_blurry": "Hold the phone still and tap the screen to focus.",
                 "image_too_dark": "Take the photo in daylight, ideally in the morning.",
                 "too_much_glare": "Avoid direct sun reflections; stand with the sun behind you.",
                 "unreadable": "Use a JPG or PNG photo."},
        "acc": "{a}% accurate in tests", "confirm": "confirm with a leaf check",
        "level": "Nitrogen level", "kgha": "kg N/ha", "low_zone": "low", "ok_zone": "adequate",
        "plan": "Fertilizer plan", "add": "Add {d} kg of nitrogen per hectare",
        "none": "No extra nitrogen needed now", "none_sub": "Re-check in 7–10 days, or sooner if the lower leaves start to yellow.",
        "check": "First check 5–10 plants: if the lower leaves yellow from the tip in a V along the midrib, apply this plan. If not, no nitrogen is needed now.",
        "product": "Product", "per_ha": "per hectare", "per_dunam": "per dunam", "litres": "L", "kg": "kg",
        "dunam_note": "1 dunam = 1,000 m². Urea is the most common choice; the others give the same 75 kg of nitrogen.",
        "names": {"Urea": "Urea", "Ammonium nitrate": "Ammonium nitrate", "UAN solution": "UAN (liquid)",
                  "Calcium ammonium nitrate (CAN)": "CAN", "Ammonium sulfate": "Ammonium sulfate"},
        "how": ["Apply as soon as possible, beside the rows, and water it in; urea left on the surface loses nitrogen to the air.",
                "Split into two equal applications 7–10 days apart, especially on sandy soil.",
                "Wait if more than 10 mm of rain is expected within 48 hours.",
                "If a soil test or your agronomist gives a rate for your field, use that rate."],
        "yellow": "Yellowish share of the plant", "this": "This plant", "t_n0": "No-nitrogen plants", "t_fert": "Fertilized plants",
        "tap": "Tap the photo to switch between the original and the measured plant area.",
        "how_read": "How the result was calculated",
        "w_unusual": "This photo differs from the trial photos (light, camera or growth stage), so confidence was lowered one step.",
        "w_glare": "Strong glare covered part of the plant.",
        "agent_title": "LeaFert assistant", "agent_wait": "The assistant is reviewing the photo, the result and the weather…",
        "agent_off": "The AI assistant is offline ({why}). The result and fertilizer plan above are complete.",
        "agent_err": "The assistant could not finish ({err}). The result and fertilizer plan above are complete.",
        "why": "Why", "next": "Next steps", "conf": "Confidence",
        "conf_v": {"high": "High", "medium": "Medium", "low": "Low"},
        "safety": {"amount_mismatch": "Use the amounts in the fertilizer plan above; they are calculated from the trial data.",
                   "apply_when_adequate": "The measurement shows adequate nitrogen; no fertilizer is needed now.",
                   "retake_ignored": "The measurement asked for a new photo; take one before acting.",
                   "confidence_capped": "Confidence matched to the measurement it is based on."},
        "q_day": "The free daily AI limit is used up. It resets in {t}. The result and plan above are complete.",
        "q_min": "The AI is busy (free per-minute limit). Try again in about {t}.",
        "q_retry": "Ask the assistant again",
        "q_line": "AI usage today: {rd} of {rpd} requests ({m})", "q_spare": ", plus {n} on backup models",
        "q_out": "Daily AI limit reached ({m}); resets in {t}",
        "greet": "After you check a plant, ask follow-up questions here, for example: *When should I apply the urea?*",
        "offline_chat": "The AI assistant is offline, so it can't answer questions right now.",
    },
    "ar": {
        "empty": "تظهر هنا نتيجة النيتروجين وخطة التسميد. التقط أو ارفع صورة للجزء العلوي من نبات ذرة واحد.",
        "retake": "أعد التقاط الصورة", "noplant": "لم يتم العثور على نبات ذرة",
        "tips": {"no_plant": "املأ معظم الإطار بالجزء العلوي من نبات واحد.",
                 "image_blurry": "ثبّت الهاتف واضغط على الشاشة للتركيز.",
                 "image_too_dark": "التقط الصورة في ضوء النهار، ويفضل في الصباح.",
                 "too_much_glare": "تجنب انعكاس الشمس المباشر؛ قف والشمس خلفك.",
                 "unreadable": "استخدم صورة بصيغة JPG أو PNG."},
        "acc": "دقيق بنسبة {a}٪ في الاختبارات", "confirm": "أكّد بفحص الأوراق",
        "level": "مستوى النيتروجين", "kgha": "كغ نيتروجين/هكتار", "low_zone": "منخفض", "ok_zone": "كافٍ",
        "plan": "خطة التسميد", "add": "أضف {d} كغ نيتروجين لكل هكتار",
        "none": "لا حاجة إلى نيتروجين إضافي الآن", "none_sub": "أعد الفحص بعد 7–10 أيام، أو قبل ذلك إذا بدأت الأوراق السفلية بالاصفرار.",
        "check": "افحص أولًا 5–10 نباتات: إذا اصفرّت الأوراق السفلية من الطرف بشكل V على طول العرق الأوسط فطبّق هذه الخطة، وإلا فلا حاجة إلى نيتروجين الآن.",
        "product": "السماد", "per_ha": "لكل هكتار", "per_dunam": "لكل دونم", "litres": "لتر", "kg": "كغ",
        "dunam_note": "الدونم = 1000 م². اليوريا هي الخيار الأكثر شيوعًا، والأسمدة الأخرى تعطي نفس الـ 75 كغ من النيتروجين.",
        "names": {"Urea": "يوريا", "Ammonium nitrate": "نترات الأمونيوم", "UAN solution": "محلول UAN (سائل)",
                  "Calcium ammonium nitrate (CAN)": "نترات الأمونيوم الكلسية", "Ammonium sulfate": "كبريتات الأمونيوم"},
        "how": ["أضفه في أقرب وقت بجانب الخطوط ثم اروِ؛ اليوريا المتروكة على السطح تفقد نيتروجينها في الهواء.",
                "قسّمه على دفعتين متساويتين بينهما 7–10 أيام، خاصة في التربة الرملية.",
                "انتظر إذا كان متوقعًا هطول أكثر من 10 مم من المطر خلال 48 ساعة.",
                "إذا أعطى تحليل التربة أو مهندسك الزراعي معدلًا لحقلك فاستخدمه."],
        "yellow": "نسبة الاصفرار في النبات", "this": "هذا النبات", "t_n0": "نباتات بدون نيتروجين", "t_fert": "نباتات مسمّدة",
        "tap": "اضغط على الصورة للتبديل بين الأصلية ومنطقة النبات المقاسة.",
        "how_read": "كيف حُسبت النتيجة",
        "w_unusual": "هذه الصورة تختلف عن صور التجربة (الإضاءة أو الكاميرا أو مرحلة النمو)، لذا خُفّضت الثقة درجة واحدة.",
        "w_glare": "انعكاس قوي غطّى جزءًا من النبات.",
        "agent_title": "مساعد LeaFert", "agent_wait": "المساعد يراجع الصورة والنتيجة والطقس…",
        "agent_off": "المساعد الذكي غير متصل ({why}). النتيجة وخطة التسميد أعلاه مكتملتان.",
        "agent_err": "تعذّر على المساعد الإكمال ({err}). النتيجة وخطة التسميد أعلاه مكتملتان.",
        "why": "لماذا", "next": "الخطوات التالية", "conf": "الثقة",
        "conf_v": {"high": "عالية", "medium": "متوسطة", "low": "منخفضة"},
        "safety": {"amount_mismatch": "استخدم الكميات في خطة التسميد أعلاه؛ فهي محسوبة من بيانات التجربة.",
                   "apply_when_adequate": "يُظهر القياس أن النيتروجين كافٍ؛ لا حاجة إلى سماد الآن.",
                   "retake_ignored": "طلب القياس صورة جديدة؛ التقطها قبل التصرف.",
                   "confidence_capped": "تمت مطابقة الثقة مع القياس الذي بُنيت عليه."},
        "q_day": "انتهى الحد اليومي المجاني للذكاء الاصطناعي. يتجدد بعد {t}. النتيجة والخطة أعلاه مكتملتان.",
        "q_min": "الذكاء الاصطناعي مشغول (حد الدقيقة المجاني). أعد المحاولة بعد حوالي {t}.",
        "q_retry": "اسأل المساعد مرة أخرى",
        "q_line": "استخدام الذكاء الاصطناعي اليوم: {rd} من {rpd} طلبًا ({m})", "q_spare": "، و{n} على النماذج الاحتياطية",
        "q_out": "تم بلوغ الحد اليومي ({m})؛ يتجدد بعد {t}",
        "greet": "بعد فحص النبات، اطرح أسئلة المتابعة هنا، مثل: *متى أضيف اليوريا؟*",
        "offline_chat": "المساعد الذكي غير متصل، لذلك لا يمكنه الإجابة الآن.",
    },
}

ICON_SWITCH = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h11l-3-3M20 17H9l3 3" fill="none" '
               'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
ICON_UPLOAD = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0-5 5m5-5 5 5M4 20h16" fill="none" '
               'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')

CAMERA = f"""
<div id="cam" class="cam" data-state="off">
  <div class="cam-stage">
    <video id="cam-video" playsinline muted autoplay></video>
    <img id="cam-still" alt="" hidden>
    <div class="cam-guide" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
    <div class="cam-off">
      <p>{L("Point the camera at the upper part of one maize plant. The app checks live whether a plant fills the frame.",
            "وجّه الكاميرا نحو الجزء العلوي من نبات ذرة واحد. يتحقق التطبيق مباشرة من أن النبات يملأ الإطار.")}</p>
      <button type="button" class="btn-primary" id="cam-start">{L("Start camera", "تشغيل الكاميرا")}</button>
      <p class="cam-note" id="cam-unsupported" hidden>{L("The camera is not available here. Use Upload instead.",
                                                         "الكاميرا غير متاحة هنا. استخدم الرفع بدلًا منها.")}</p>
    </div>
    <div class="cam-hud"><div class="cam-status" id="cam-status" role="status" aria-live="polite"></div>
      <div class="cam-meter" aria-hidden="true"><span id="cam-meter-fill"></span></div></div>
    <div class="cam-busy" id="cam-busy" hidden><span class="spinner"></span>{L("Analysing…", "جارٍ التحليل…")}</div>
  </div>
  <div class="cam-controls cam-live">
    <button type="button" class="btn-icon" id="cam-switch">{ICON_SWITCH}{L("Switch", "تبديل")}</button>
    <button type="button" class="shutter" id="cam-capture" aria-label="Take photo" disabled><span></span></button>
    <label class="btn-icon">{ICON_UPLOAD}{L("Upload", "رفع")}<input type="file" id="cam-file" accept="image/*" hidden></label>
  </div>
  <div class="cam-controls cam-still">
    <button type="button" class="btn-primary btn-wide" id="cam-analyze">{L("Check nitrogen", "افحص النيتروجين")}</button>
    <div class="still-row">
      <button type="button" class="btn-ghost" id="cam-retake">{L("Retake", "إعادة")}</button>
      <label class="btn-ghost">{L("Upload another", "رفع صورة أخرى")}<input type="file" id="cam-file2" accept="image/*" hidden></label>
    </div>
  </div>
  <ul class="cam-tips">
    <li>{L("Daylight, no flash", "ضوء النهار، بدون فلاش")}</li>
    <li>{L("Upper plant fills the frame", "الجزء العلوي يملأ الإطار")}</li>
    <li>{L("Sun behind you, phone still", "الشمس خلفك والهاتف ثابت")}</li>
  </ul>
</div>
"""

NAV = f"""
<header class="topnav" id="nav">
  <a class="brand" href="#top">{wordmark()}</a>
  <nav class="nav-links" aria-label="Sections">
    <a href="#story">{L("Why leaves yellow", "لماذا تصفرّ الأوراق")}</a>
    <a href="#tool">{L("Check a plant", "افحص نباتًا")}</a>
    <a href="#evidence">{L("Accuracy", "الدقة")}</a>
    <a href="#limits">{L("Good to know", "معلومات مهمة")}</a>
  </nav>
  <div class="lang" role="group" aria-label="Language">
    <button type="button" class="lang-btn is-on" data-lang="en">English</button>
    <button type="button" class="lang-btn" data-lang="ar">العربية</button>
  </div>
</header>
"""

app_ui = ui.page_fluid(
    ui.head_content(
        ui.tags.meta(name="viewport", content="width=device-width, initial-scale=1"),
        ui.tags.link(rel="icon", href="leafert-logo.png"),
        ui.tags.link(rel="preconnect", href="https://fonts.googleapis.com"),
        ui.tags.link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Readex+Pro:wght@300;400;500;600;700&display=swap"),
        ui.tags.link(rel="stylesheet", href="styles.css"),
        ui.tags.title("LeaFert – maize nitrogen and fertilizer plan"),
    ),
    ui.HTML(NAV),
    ui.HTML(hero()),
    ui.HTML(story()),
    ui.HTML(how()),
    ui.tags.section(
        ui.h2(ui.HTML(L("Check a plant", "افحص نباتًا"))),
        ui.div(
            ui.div(ui.HTML(CAMERA),
                   ui.input_text("note", None, placeholder="Optional note, e.g. growth stage or last fertilizer date", width="100%"),
                   class_="tool-left"),
            ui.div(
                ui.div(ui.div(ui.h3(ui.HTML(L("What LeaFert is doing", "ما يفعله LeaFert"))),
                              ui.span("", id="steps-title", class_="steps-title"), class_="steps-head"),
                       ui.tags.ol(id="steps", class_="steps"), class_="steps-box"),
                ui.output_ui("measurement"),
                ui.output_ui("agent_report"),
                ui.output_ui("quota_line"),
                ui.h3(ui.HTML(L("Ask a follow-up question", "اسأل سؤال متابعة")), class_="chat-h"),
                ui.chat_ui("chat", greeting=TXT["en"]["greet"] + "\n\n" + TXT["ar"]["greet"],
                           height="360px", width="100%", drawer=False, show_history=False,
                           allow_attachments=False, placeholder="Ask about this plant, fertilizer or weather…"),
                class_="tool-right"),
            class_="tool-grid"),
        id="tool", class_="tool"),
    ui.HTML(evidence()),
    ui.HTML(limits()),
    ui.tags.footer(ui.div(ui.HTML(wordmark("wm-small")), class_="foot-brand"),
                   ui.p(ui.HTML(L("Maize nitrogen check and fertilizer plan from one photo.",
                                  "فحص نيتروجين الذرة وخطة التسميد من صورة واحدة."))), class_="foot"),
    ui.tags.script(src="app.js"),
    class_="site",
)


# =============================================================================
# Rendering helpers
# =============================================================================
def _shot(a, t):
    o, m = a.get("image_jpeg_base64"), a.get("mask_overlay_jpeg_base64")
    if not o:
        return None
    if m and a.get("features"):
        A, B = f"data:image/jpeg;base64,{o}", f"data:image/jpeg;base64,{m}"
        return ui.tags.figure(ui.tags.img(src=B, class_="shot shot-toggle", alt=t["tap"], tabindex="0", role="button",
                                          **{"data-a": A, "data-b": B}),
                              ui.tags.figcaption(t["tap"]), class_="shot-fig")
    return ui.tags.figure(ui.tags.img(src=f"data:image/jpeg;base64,{o}", class_="shot", alt=""), class_="shot-fig")


def _gauge(a, t):
    pos = lambda v: f"{max(0.0, min(100.0, v / SCALE * 100)):.1f}%"
    cut, lvl = a["cut_kg"], a["level_kg"]
    ticks = [0, cut, SCALE]
    return ui.div(
        ui.div(ui.span(t["level"], class_="g-title"),
               ui.span(ui.tags.b(f"≈ {round(lvl)}"), f" {t['kgha']}", class_="g-value"), class_="g-head"),
        ui.div(ui.div(class_="gz gz-low", style=f"width:{pos(cut)}"),
               ui.div(class_="gz gz-ok", style=f"width:{100 - cut / SCALE * 100:.1f}%"),
               ui.div(class_="g-pin", style=f"inset-inline-start:{pos(lvl)}"), class_="g-track"),
        ui.div(*[ui.span(str(v), class_="g-tick", style=f"inset-inline-start:{pos(v)}") for v in ticks], class_="g-ticks"),
        ui.div(ui.span(t["low_zone"], style=f"inset-inline-start:{pos(cut / 2)}"),
               ui.span(t["ok_zone"], style=f"inset-inline-start:{pos((cut + SCALE) / 2)}"), class_="g-zones"),
        class_="gauge")


def _plan(a, t):
    plan = a["plan"]
    if plan["action"] == "none":
        return ui.div(ui.p(t["plan"], class_="plan-label"), ui.h4(t["none"], class_="plan-dose plan-none"),
                      ui.p(t["none_sub"], class_="plan-sub"), class_="plan plan-ok")
    rows = []
    for p in plan["products"]:
        kg = t["kg"]
        ha, du = [f"{p['kg_per_ha']} {kg}"], [f"{p['kg_per_1000m2']} {kg}"]
        if "litres_per_ha" in p:                       # liquid: litres on a second line
            ha.append(ui.tags.small(f"{p['litres_per_ha']} {t['litres']}"))
            du.append(ui.tags.small(f"{p['litres_per_1000m2']} {t['litres']}"))
        name = ui.span(t["names"].get(p["name"], p["name"]), ui.tags.small(f"{p['n_percent']}% N"), class_="pname")
        rows.append(ui.tags.tr(ui.tags.td(name), ui.tags.td(*ha, class_="num"), ui.tags.td(*du, class_="num"),
                               class_="main" if p["name"] == "Urea" else None))
    how = [t["how"][0]] + ([t["how"][1]] if plan.get("split") else []) + t["how"][2:]
    return ui.div(
        ui.p(t["plan"], class_="plan-label"),
        ui.h4(t["add"].format(d=plan["dose_kg_n_ha"]), class_="plan-dose"),
        ui.p(t["check"], class_="plan-check") if plan["action"] == "check_then_apply" else None,
        ui.div(ui.tags.table(ui.tags.thead(ui.tags.tr(ui.tags.th(t["product"]), ui.tags.th(t["per_ha"]), ui.tags.th(t["per_dunam"]))),
                             ui.tags.tbody(*rows), class_="plan-table"), class_="table-wrap"),
        ui.p(t["dunam_note"], class_="plan-note"),
        ui.tags.ul(*[ui.tags.li(x) for x in how], class_="plan-how"),
        class_="plan plan-low")


def _yellow(a, t):
    y = a["features"]["frac_yellowish"]
    fert = (GROUP_YELLOW["N75"] + GROUP_YELLOW["NFull"]) / 2
    rows = [(t["this"], y, "yb-this"), (t["t_fert"], fert, "yb-fert"), (t["t_n0"], GROUP_YELLOW["N0"], "yb-n0")]
    mx = max(0.5, y, GROUP_YELLOW["N0"]) * 1.05
    return ui.div(ui.p(t["yellow"], class_="g-title"),
                  *[ui.div(ui.span(lbl, class_="yb-l"),
                           ui.div(ui.div(class_=f"yb-bar {cls}", style=f"width:{v / mx * 100:.1f}%"), class_="yb-track"),
                           ui.span(f"{pct(v)}%", class_="yb-v"), class_="yb-row") for lbl, v, cls in rows],
                  class_="yellow-block")


# =============================================================================
# Server
# =============================================================================
def server(input, output, session):
    tid = session.id
    current = reactive.value(None)
    agent_wanted = reactive.value(False)
    chat = ui.Chat("chat")

    def lang():
        try:
            v = input.lang()
        except Exception:  # noqa: BLE001 - not sent yet
            v = None
        return v if v in ("en", "ar") else "en"

    async def emit(ev: dict):
        await session.send_custom_message("step", ev)

    @reactive.extended_task
    async def agent_job(image_id: str, note: str, lang_: str):
        return await ag.run_turn(tid, note or "Please check this maize plant and give me the fertilizer plan.",
                                 lang_, image_id, emit)

    @reactive.effect
    @reactive.event(input.photo_submit)
    async def _on_photo():
        payload = input.photo_submit()
        if not payload or "data" not in payload:
            return
        Lg = lang()
        try:
            data = base64.b64decode(payload["data"].split(",", 1)[-1])
        except (ValueError, TypeError):
            data = b""
        agent_job.cancel()
        agent_wanted.set(False)
        await session.send_custom_message("steps_reset", {"title": "تحليل صورة" if Lg == "ar" else "Photo check"})
        await emit(dict(id="quality", group="measure", status="running",
                        label="فحص جودة الصورة" if Lg == "ar" else "Checking photo quality"))
        a = await asyncio.to_thread(assess, data)
        for ev in steps(a, Lg):
            await emit(ev)
        image_id = ag.STORE.add_photo(tid, data, a)
        current.set({"a": a, "image_id": image_id})
        ok, why = ag.agent_status()
        if ok:
            agent_wanted.set(True)
            agent_job.invoke(image_id, input.note(), Lg)
        else:
            await emit(dict(id="think", group="agent", status="skip",
                            label="المساعد الذكي" if Lg == "ar" else "AI assistant", detail=why))
        await session.send_custom_message("analysis_done", {"decision": a.get("decision")})

    @render.ui
    def measurement():
        Lg = lang()
        t = TXT[Lg]
        c = current()
        if c is None:
            return ui.div(ui.p(t["empty"]), class_="empty")
        a = c["a"]
        if a["decision"] != "ok":
            title = t["noplant"] if "no_plant" in a["reasons"] else t["retake"]
            tips = [t["tips"][r] for r in dict.fromkeys(a["reasons"]) if r in t["tips"]]
            return ui.div(ui.h3(title, class_="verdict v-retake"),
                          ui.tags.ul(*[ui.tags.li(x) for x in tips], class_="tips-list"),
                          _shot(a, t),
                          ui.tags.details(ui.tags.summary(t["how_read"]),
                                          ui.tags.ol(*[ui.tags.li(x) for x in reasoning(a, Lg)], class_="why-list")),
                          class_="card")
        warns = []
        if "unusual_photo" in a["warnings"]:
            warns.append(t["w_unusual"])
        if "glare" in a["warnings"]:
            warns.append(t["w_glare"])
        conf = a["confidence"]
        return ui.div(
            ui.div(ui.h3(STATUS[Lg][a["status"]], class_=f"verdict v-{a['status']}"),
                   ui.span(CONF[Lg][conf],
                           ui.tags.small(" " + (t["confirm"] if conf == "low" else t["acc"].format(a=pct(a["accuracy"])))),
                           class_=f"conf-pill cp-{conf}"), class_="verdict-row"),
            *[ui.p(w, class_="warn") for w in warns],
            _gauge(a, t),
            _plan(a, t),
            _yellow(a, t),
            _shot(a, t),
            ui.tags.details(ui.tags.summary(t["how_read"]),
                            ui.tags.ol(*[ui.tags.li(x) for x in reasoning(a, Lg)], class_="why-list")),
            class_="card result")

    @render.ui
    def agent_report():
        Lg = lang()
        t = TXT[Lg]
        c = current()
        if c is None:
            return None
        ok, why = ag.agent_status()
        if not ok:
            return ui.div(ui.p(t["agent_off"].format(why=why)), class_="card card-quiet")
        if not agent_wanted():
            return None
        st = agent_job.status()
        if st == "running":
            return ui.div(ui.h3(t["agent_title"]),
                          ui.div(ui.span(class_="spinner"), ui.span(t["agent_wait"]), class_="waiting"),
                          class_="card agent")
        if st == "error":
            return ui.div(ui.p(t["agent_err"].format(err="error")), class_="card card-quiet")
        if st != "success":
            return None
        res = agent_job.result()
        if res.get("error") == "quota":
            q = res.get("quota") or {}
            if q.get("kind") == "day":
                return ui.div(ui.p(t["q_day"].format(t=quota.human_wait(q.get("reset_in_s") or 0, Lg))),
                              class_="card card-quiet")
            return ui.div(ui.p(t["q_min"].format(t=quota.human_wait(q.get("wait_s") or 60, Lg))),
                          ui.input_action_button("retry_agent", t["q_retry"], class_="btn-ghost"),
                          class_="card card-quiet")
        rep = res.get("report")
        if not rep:
            return ui.div(ui.p(t["agent_err"].format(err=res.get("error") or "no report")), class_="card card-quiet")
        conf = rep.get("confidence", "low")
        kind = {"low": "low", "adequate": "adequate"}.get(rep.get("n_status"), "neutral")
        level = {"low": 1, "medium": 2, "high": 3}[conf]
        return ui.div(
            ui.p(t["agent_title"], class_="agent-name"),
            ui.h3(rep.get("verdict", ""), class_=f"verdict v-{kind}"),
            ui.div(ui.span(t["conf"]), ui.div(*[ui.span(class_="seg on" if i < level else "seg") for i in range(3)],
                                              class_="segs"),
                   ui.span(t["conf_v"][conf], class_="conf-v"), class_="conf"),
            ui.p(rep.get("answer", ""), class_="answer"),
            ui.h4(t["why"]), ui.tags.ol(*[ui.tags.li(x) for x in rep.get("reasoning", [])], class_="why-list"),
            ui.h4(t["next"]), ui.tags.ul(*[ui.tags.li(x) for x in rep.get("next_steps", [])], class_="next-list"),
            *[ui.p(t["safety"][s], class_="warn") for s in res.get("safety", []) if s in t["safety"]],
            class_="card agent")

    @reactive.effect
    @reactive.event(input.retry_agent)
    def _retry():
        c = current()
        if c and c.get("image_id"):
            agent_job.invoke(c["image_id"], input.note(), lang())

    @render.ui
    def quota_line():
        reactive.invalidate_later(15)
        agent_job.status()
        Lg = lang()
        if not ag.agent_status()[0]:
            return None
        stats = ag.quota_status()
        m = quota.short_name(ag.MODEL)
        st = stats.get(m)
        if not st:
            return None
        spare = sum(max(0, int(v["rpd"] * quota.SAFETY) - v["rpd_used"])
                    for k, v in stats.items() if k != m and not v["exhausted"])
        t = TXT[Lg]
        txt = (t["q_out"].format(m=m, t=quota.human_wait(st["reset_in_s"], Lg)) if st["exhausted"]
               else t["q_line"].format(rd=st["rpd_used"], rpd=st["rpd"], m=m))
        if spare:
            txt += t["q_spare"].format(n=spare)
        return ui.p(txt, class_="quota-line")

    @chat.on_user_submit
    async def _(user_input: str):
        Lg = lang()
        if not ag.agent_status()[0]:
            await chat.append_message(TXT[Lg]["offline_chat"])
            return
        await session.send_custom_message("steps_reset", {"title": "سؤال متابعة" if Lg == "ar" else "Follow-up question"})
        res = await ag.run_turn(tid, user_input, Lg, None, emit)
        if res.get("error") == "quota":
            q = res.get("quota") or {}
            key = "q_day" if q.get("kind") == "day" else "q_min"
            w = q.get("reset_in_s") if key == "q_day" else q.get("wait_s")
            await chat.append_message(TXT[Lg][key].format(t=quota.human_wait(w or 60, Lg)))
            return
        rep = res.get("report")
        if not rep:
            await chat.append_message(TXT[Lg]["agent_err"].format(err=res.get("error")))
            return
        msg = rep.get("answer", "")
        why = "\n".join(f"{i + 1}. {x}" for i, x in enumerate(rep.get("reasoning", [])))
        if why:
            msg += f"\n\n**{TXT[Lg]['why']}:**\n{why}"
        for s in res.get("safety", []):
            if s in TXT[Lg]["safety"]:
                msg += f"\n\n{TXT[Lg]['safety'][s]}"
        await chat.append_message(msg)

    @session.on_ended
    def _cleanup():
        ag.STORE.forget(tid)


app = App(app_ui, server, static_assets=WWW)
