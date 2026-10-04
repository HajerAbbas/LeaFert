"""
agent.py - the LangChain agent behind LeaFert (maize nitrogen + fertilizer plan).

    photo ──► maize_core.assess (deterministic: quality, plant detection,
              colour features, calibrated model) ──► sent inside the message
                         │
    Gemini agent (create_agent) ── sees the photo + measurement + rules, may call:
        get_weather_forecast   OpenWeather 48 h summary
    ──► PlantReport (structured: verdict, status, confidence, reasoning, next steps)
    ──► safety_review (deterministic)

Free-tier friendly (see quota.py): 1-2 requests per photo, old photos stripped
from the history, RPM/TPM/RPD checked before every call, fallback models,
Google's 429 retry hints respected, identical requests cached.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Awaitable, Callable, List, Literal, Optional

from pydantic import BaseModel, Field

import quota
from leaf_core import _preview_jpeg_b64, decode_image
from maize_core import slim

# Main model: Gemini 3.5 Flash-Lite. It accepts images and supports function calling
# and structured output, and on the free tier it allows 15 requests/min and 500/day
# (Flash models allow only 5/min and 20/day).
MODEL = os.getenv("LEAFERT_AGENT_MODEL", "google_genai:gemini-3.5-flash-lite")
# Tried in order when the main model is out of quota; each model has its own quota.
#   gemini-3.1-flash-lite : another 500 requests/day
#   gemini-3.8-flash      : strongest Flash, but only 20/day, so it is the last resort
FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "LEAFERT_AGENT_FALLBACK_MODELS",
    "google_genai:gemini-3.1-flash-lite,google_genai:gemini-3.8-flash").split(",") if m.strip()]
KEEP_TURNS = 3          # history sent to the model: last N user turns
DEFAULT_LAT = float(os.getenv("FARM_LAT", "24.7136"))     # Riyadh
DEFAULT_LON = float(os.getenv("FARM_LON", "46.6753"))

Emit = Callable[[dict], Awaitable[None]]


# =============================================================================
# Per-session storage (photos and their measurements)
# =============================================================================
class _Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.images: dict[str, bytes] = {}
        self.analysis: dict[str, dict] = {}
        self.counter = defaultdict(int)

    def add_photo(self, thread_id: str, data: bytes, analysis: dict) -> str:
        with self.lock:
            self.counter[thread_id] += 1
            image_id = f"{thread_id}:{self.counter[thread_id]}"
            self.images[image_id] = data
            self.analysis[image_id] = analysis
        return image_id

    def forget(self, thread_id: str):
        with self.lock:
            for k in [k for k in self.images if k.startswith(thread_id + ":")]:
                self.images.pop(k, None)
                self.analysis.pop(k, None)


STORE = _Store()


# =============================================================================
# Tools
# =============================================================================
RULES = {
    "model": "estimates the plant's nitrogen level from colour as the N rate (kg N/ha) a trial plant of "
             "that colour typically received; below cut_kg = low nitrogen",
    "fertilizer": [
        "Use ONLY the doses and product amounts in measurement.fertilizer_plan. Never invent or change numbers.",
        "action 'apply': recommend the plan. action 'check_then_apply': tell the farmer to first check 5-10 plants "
        "for yellowing that starts at the tip of lower leaves in a V along the midrib; apply the plan only if seen.",
        "action 'none': no nitrogen needed now; suggest re-checking in 7-10 days.",
        "If split is true, suggest two equal applications 7-10 days apart, especially on sandy soil.",
        "Apply beside the rows and water it in (urea left on the surface loses nitrogen to the air).",
        "If more than 10 mm of rain is forecast within 48 hours, advise waiting until after the rain.",
        "If a soil test or local agronomist recommends a different rate, theirs takes priority.",
    ],
    "other_causes": "Drought, heat, waterlogging, sulfur/magnesium/potassium shortage, disease or natural "
                    "ageing of lower leaves can also cause yellowing.",
}


def _make_tools():
    from langchain.tools import tool

    @tool
    def get_weather_forecast(latitude: float = DEFAULT_LAT, longitude: float = DEFAULT_LON) -> str:
        """48-hour weather summary (rain, temperature, humidity) for the farm.
        Call before recommending fertilizer or irrigation. Defaults to Riyadh."""
        key = os.getenv("OPENWEATHER_API_KEY")
        if not key:
            return json.dumps({"available": False, "reason": "weather service not configured"})
        q = urllib.parse.urlencode({"lat": latitude, "lon": longitude, "units": "metric",
                                    "cnt": 16, "appid": key})
        try:
            with urllib.request.urlopen(
                    f"https://api.openweathermap.org/data/2.5/forecast?{q}", timeout=10) as resp:
                d = json.load(resp)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"available": False, "reason": str(e)})
        items = d.get("list", [])
        if not items:
            return json.dumps({"available": False, "reason": "empty forecast"})
        temps = [i["main"]["temp"] for i in items]
        return json.dumps({
            "available": True, "location": d.get("city", {}).get("name"),
            "hours_covered": 3 * len(items),
            "rain_total_mm": round(sum(i.get("rain", {}).get("3h", 0) for i in items), 1),
            "temp_max_c": max(temps), "temp_min_c": min(temps),
            "humidity_mean_pct": round(sum(i["main"]["humidity"] for i in items) / len(items)),
        })

    return [get_weather_forecast]


# =============================================================================
# Structured report = the agent's visible reasoning
# =============================================================================
class PlantReport(BaseModel):
    """Final report for the user. Always fill every field."""
    verdict: str = Field(description="One short, clear headline, e.g. 'Low nitrogen: add 75 kg N per hectare'.")
    n_status: Literal["low", "adequate", "retake", "not_maize", "question"] = Field(
        description="'question' when answering a follow-up question without a new photo.")
    confidence: Literal["high", "medium", "low"]
    reasoning: List[str] = Field(
        description="2-5 short steps explaining the verdict, each citing concrete evidence "
                    "(a measured value, the weather, or what you saw in the photo).")
    next_steps: List[str] = Field(description="1-3 concrete actions, including the fertilizer plan when there is one.")
    answer: str = Field(description="Clear, direct reply to the user, max ~6 lines.")


SYSTEM_PROMPT = """You are the LeaFert assistant. You help farmers read the nitrogen status of a maize
(corn) plant from a daylight photo of the upper plant and act on it with the right fertilizer.

A photo message contains the photo and a MEASUREMENT block computed by LeaFert's model, trained on
1,200 field-trial photos (0, 75 and 136 kg N/ha). The measurement is the only source of numbers.

For a photo:
1. If the photo clearly does not show a maize plant, use n_status "not_maize" and ask for a photo
   of the upper part of one maize plant.
2. decision "retake": n_status "retake"; explain the reasons and how to fix them.
3. Otherwise report status ("low" or "adequate"), the nitrogen level in kg N/ha, and the confidence
   with its tested accuracy. Be clear and direct; do not hedge beyond the stated confidence.
4. Present the fertilizer plan following the fertilizer rules. Mention the main product (urea) and
   its amount per hectare and per 1,000 m2 (one dunam).
5. Say what you see in the photo: nitrogen shortage shows as yellowing from the TIP of LOWER leaves
   along the MIDRIB in a V. Yellow tassels, pollen or glare are not signs of nitrogen shortage.
6. Call get_weather_forecast once only when the plan says to apply nitrogen.

RULES (always follow): """ + json.dumps(RULES) + """

For follow-up questions without a photo use n_status "question".
The reasoning field is shown to the user as "Why": short, factual, evidence-based steps.
Write every text field in the language requested in the message (Arabic or English)."""


# =============================================================================
# Agent construction
# =============================================================================
_AGENT = None
_MODEL_OVERRIDE = None
_LOCK = threading.Lock()
_EMIT: contextvars.ContextVar = contextvars.ContextVar("emit", default=None)
_LANG: contextvars.ContextVar = contextvars.ContextVar("lang", default="en")


def set_model(model):
    """Inject a chat model (tests / other providers)."""
    global _MODEL_OVERRIDE, _AGENT
    _MODEL_OVERRIDE, _AGENT = model, None


def model_chain() -> list[str]:
    return [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]


def agent_status() -> tuple[bool, str]:
    if _MODEL_OVERRIDE is not None:
        return True, "custom model"
    if MODEL.startswith("google") and not os.getenv("GOOGLE_API_KEY"):
        return False, "GOOGLE_API_KEY is not set"
    return True, MODEL


def quota_preflight(est_tokens: int = 3000) -> tuple[bool, str, float]:
    """Before starting a turn: is ANY model usable soon? -> (ok, kind, wait_s)."""
    if _MODEL_OVERRIDE is not None and getattr(_MODEL_OVERRIDE, "_skip_quota", False):
        return True, "", 0.0
    best = (float("inf"), "rpd")
    for m in model_chain():
        w, kind = quota.GUARD.wait_needed(m, est_tokens)
        if w < best[0]:
            best = (w, kind)
    if best[0] == float("inf"):
        return False, "day", float("inf")
    if best[0] > quota.MAX_WAIT_S:
        return False, "minute", best[0]
    return True, best[1], best[0]


def _strip_old_images(messages: list) -> list:
    """Keep the photo only in the newest user message, and only the last
    KEEP_TURNS user turns (cut at a user message so tool pairs stay intact)."""
    human_idx = [i for i, m in enumerate(messages) if m.type == "human"]
    if len(human_idx) > KEEP_TURNS:
        messages = messages[human_idx[-KEEP_TURNS]:]
        human_idx = [i for i, m in enumerate(messages) if m.type == "human"]
    last = human_idx[-1] if human_idx else -1
    out = []
    for i, m in enumerate(messages):
        if m.type == "human" and i != last and not isinstance(m.content, str):
            blocks = [b for b in m.content if not (isinstance(b, dict) and b.get("type") in ("image", "image_url"))]
            if len(blocks) != len(m.content):
                blocks.append({"type": "text", "text": "[earlier photo removed to save tokens]"})
                m = m.model_copy(update={"content": blocks})
        out.append(m)
    return out


_LIMIT_NAMES = {
    "rpm": ("requests per minute", "الطلبات في الدقيقة"),
    "tpm": ("tokens per minute", "الرموز في الدقيقة"),
    "retry": ("Google asked to wait", "طلبت Google الانتظار"),
}


def _wait_text(kind: str, wait: float, ar: bool) -> str:
    en, a = _LIMIT_NAMES.get(kind, (kind, kind))
    return f"{a}: استئناف بعد {wait:.0f} ث" if ar else f"Free-tier limit ({en}): resuming in {wait:.0f} s"


def _make_middleware(models: dict):
    from langchain.agents.middleware import AgentMiddleware

    class QuotaMiddleware(AgentMiddleware):
        """Before every model call: trim history, check RPM/TPM/RPD, wait or switch
        model. After a 429: read Google's quota type + retry delay and react."""

        async def awrap_model_call(self, request, handler):
            emit = _EMIT.get()
            ar = _LANG.get() == "ar"
            msgs = _strip_old_images(list(request.messages))
            sys_text = getattr(request.system_message, "content", "") or ""
            est = quota.estimate_tokens(msgs, str(sys_text))
            last_err = None
            for name in models:
                for attempt in range(2):                      # one retry per model
                    if not getattr(models[name], "_skip_quota", False):
                        wait, kind = quota.GUARD.wait_needed(name, est)
                        if wait == float("inf"):
                            last_err = quota.QuotaUnavailable("day", wait, name)
                            break                             # next model
                        if wait > quota.MAX_WAIT_S:
                            last_err = quota.QuotaUnavailable("minute", wait, name)
                            break
                        if wait > 0:
                            if emit:
                                await emit(dict(id="quota_wait", group="agent", status="running",
                                                label="انتظار حصة الذكاء الاصطناعي" if ar else "Waiting for AI quota",
                                                detail=_wait_text(kind, wait, ar)))
                            await asyncio.sleep(wait)
                            if emit:
                                await emit(dict(id="quota_wait", status="done"))
                        quota.GUARD.reserve(name, est)
                    try:
                        resp = await handler(request.override(model=models[name], messages=msgs))
                    except Exception as e:  # noqa: BLE001
                        if not quota.is_rate_limit(e):
                            raise
                        kind, retry = quota.classify_rate_limit(e)
                        quota.GUARD.on_rate_limit(name, kind, retry)
                        last_err = quota.QuotaUnavailable(kind, retry or 60, name)
                        if emit:
                            await emit(dict(id=f"q429_{name}_{attempt}", group="agent", status="warn",
                                            label="حد الطلبات (429)" if ar else "Rate limit hit (429)",
                                            detail=f"{quota.short_name(name)}: "
                                                   + ("daily quota used up" if kind == "day"
                                                      else f"per-minute limit, retry after {retry or 60:.0f} s")))
                        if kind == "day":
                            break                             # next model
                        continue                              # wait + retry same model
                    usage = None
                    for m in getattr(resp, "result", []) or []:
                        um = getattr(m, "usage_metadata", None)
                        if um:
                            usage = um.get("input_tokens")
                    quota.GUARD.settle(name, est, usage)
                    if name != next(iter(models)) and emit:
                        await emit(dict(id="fallback", group="agent", status="warn",
                                        label="تم التحويل إلى نموذج احتياطي" if ar else "Switched to fallback model",
                                        detail=quota.short_name(name)))
                    return resp
            raise last_err or quota.QuotaUnavailable("minute", 60)

    return QuotaMiddleware()


def _agent():
    global _AGENT
    with _LOCK:
        if _AGENT is None:
            from langchain.agents import create_agent
            from langchain.agents.structured_output import ToolStrategy
            from langgraph.checkpoint.memory import InMemorySaver
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            if _MODEL_OVERRIDE is not None:
                models = {"custom": _MODEL_OVERRIDE}
            else:
                from langchain.chat_models import init_chat_model
                # max_retries=0: QuotaMiddleware decides when to wait or switch
                models = {m: init_chat_model(m, max_retries=0, timeout=60) for m in model_chain()}
            serde = JsonPlusSerializer(allowed_msgpack_modules=[("agent", "PlantReport")])
            _AGENT = create_agent(
                model=next(iter(models.values())),
                tools=_make_tools(),
                system_prompt=SYSTEM_PROMPT,
                response_format=ToolStrategy(PlantReport),
                middleware=[_make_middleware(models)],
                checkpointer=InMemorySaver(serde=serde),
            )
        return _AGENT


# =============================================================================
# Safety review (deterministic)
# =============================================================================
_APPLY_RE = re.compile(
    r"(\b(apply|add|spread|give)\b[^.\n]{0,30}\b(fertili[sz]er|nitrogen|urea|npk)\b"
    r"|\bfertili[sz]e\b|سمّد|ضع سماد|أضف سماد|أضف السماد|أضف النيتروجين)", re.I)


_AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:kg|kilo|l\b|litre|liter|كغ|كجم|كيلو|لتر)", re.I)


def _allowed_amounts(analysis: Optional[dict]) -> set:
    plan = (analysis or {}).get("plan") or {}
    vals = {float(plan.get("dose_kg_n_ha") or 0), 136.0, 75.0}
    if (analysis or {}).get("cut_kg") is not None:
        vals.add(float(analysis["cut_kg"]))
    if (analysis or {}).get("level_kg") is not None:
        vals.add(round(float(analysis["level_kg"])))
    for p in plan.get("products", []):
        for k in ("kg_per_ha", "kg_per_1000m2", "litres_per_ha", "litres_per_1000m2"):
            if k in p:
                vals.add(float(p[k]))
        if plan.get("split"):
            vals.add(round(p["kg_per_ha"] / 2))
            vals.add(round(p["kg_per_1000m2"] / 2, 1))
    if plan.get("split"):
        vals.add(plan.get("dose_kg_n_ha", 0) / 2)
    return vals


def safety_review(report: dict, analysis: Optional[dict]) -> List[str]:
    """Deterministic checks on the assistant's reply."""
    text = " ".join([report.get("answer", ""), report.get("verdict", "")] + report.get("next_steps", []))
    notes = []
    allowed = _allowed_amounts(analysis)
    for m in _AMOUNT_RE.finditer(text):
        v = float(m.group(1).replace(",", "."))
        if not any(abs(v - a) <= max(1.0, 0.03 * a) for a in allowed):
            notes.append("amount_mismatch")
            break
    if analysis and analysis.get("status") == "adequate" and _APPLY_RE.search(text):
        notes.append("apply_when_adequate")
    if analysis and analysis.get("decision") == "retake" and report.get("n_status") not in ("retake", "not_maize"):
        notes.append("retake_ignored")
    return notes


# =============================================================================
# Running a turn with live step events
# =============================================================================
TOOL_LABELS = {
    "get_weather_forecast": ("weather", "Checking the 48-hour weather", "فحص الطقس لـ 48 ساعة"),
    "PlantReport": ("report", "Writing the report", "كتابة التقرير"),
}


def _summarize_tool(name: str, content: str, lang: str) -> str:
    try:
        d = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return ""
    ar = lang == "ar"
    if name == "get_weather_forecast":
        if not d.get("available"):
            return "الطقس غير متاح" if ar else "Weather unavailable"
        return (f"{d.get('location') or ''} مطر {d['rain_total_mm']} مم، {d['temp_min_c']:.0f}–{d['temp_max_c']:.0f}°م"
                if ar else
                f"{d.get('location') or ''} rain {d['rain_total_mm']} mm, {d['temp_min_c']:.0f}–{d['temp_max_c']:.0f} °C")
    return ""


_CACHE: dict[str, dict] = {}


def _cache_key(thread_id, text, lang, image_id) -> Optional[str]:
    if not image_id or image_id not in STORE.images:
        return None
    h = hashlib.sha1(STORE.images[image_id]).hexdigest()
    return f"{thread_id}|{h}|{lang}|{text}"


async def run_turn(thread_id: str, text: str, lang: str = "en",
                   image_id: Optional[str] = None, emit: Optional[Emit] = None) -> dict:
    """One user turn. Returns {"report", "safety", "error", "quota"}."""
    from langchain.messages import HumanMessage

    async def _emit(**ev):
        if emit:
            await emit(ev)

    ar = lang == "ar"
    cache_key = _cache_key(thread_id, text, lang, image_id)
    if cache_key and cache_key in _CACHE:
        await _emit(id="cache", group="agent", status="done",
                    label="إجابة محفوظة (بدون طلب جديد)" if ar else "Reused earlier answer (no new request)",
                    detail="same photo and language" if not ar else "نفس الصورة واللغة")
        return _CACHE[cache_key]

    ok, kind, wait = quota_preflight()
    if not ok:
        await _emit(id="think", group="agent", status="skip",
                    label="الوكيل الذكي" if ar else "AI agent",
                    detail=("انتهت الحصة اليومية" if ar else "daily AI quota used up") if kind == "day"
                    else ((f"الحصة ممتلئة، أعد المحاولة بعد {wait:.0f} ث") if ar else f"quota busy, retry in {wait:.0f} s"))
        return {"report": None, "safety": [], "error": "quota",
                "quota": {"kind": kind, "wait_s": wait if wait != float("inf") else None,
                          "reset_in_s": (quota.next_reset() - quota.datetime.now(quota.PACIFIC)).total_seconds()}}

    parts = [f"[Reply language: {'Arabic' if ar else 'English'}]"]
    if image_id and image_id in STORE.analysis:
        meas = slim(STORE.analysis[image_id])
        parts.append("MEASUREMENT (Python, authoritative): " + json.dumps(meas, ensure_ascii=False, default=str))
    if text:
        parts.append(("User note: " if image_id else "") + text)
    content = [{"type": "text", "text": "\n".join(parts)}]
    if image_id and image_id in STORE.images:
        try:
            prev = _preview_jpeg_b64(decode_image(STORE.images[image_id]), max_side=768)
            content.append({"type": "image", "base64": prev, "mime_type": "image/jpeg"})
        except ValueError:
            pass

    _EMIT.set(emit)
    _LANG.set(lang)
    await _emit(id="think", group="agent", status="running",
                label="الوكيل يفحص الصورة ويخطط" if ar and image_id else
                "الوكيل يقرأ سؤالك" if ar else
                "Agent looks at the photo and plans" if image_id else "Agent reads your question")
    t0 = time.perf_counter()
    report, think_done = None, False
    try:
        async for chunk in _agent().astream(
                {"messages": [HumanMessage(content=content)]},
                {"configurable": {"thread_id": thread_id}, "recursion_limit": 14},
                stream_mode="updates"):
            for node, upd in chunk.items():
                if not isinstance(upd, dict):
                    continue
                for m in upd.get("messages", []) or []:
                    if not think_done and m.type == "ai":
                        think_done = True
                        await _emit(id="think", group="agent", status="done",
                                    ms=int((time.perf_counter() - t0) * 1000))
                    if m.type == "ai":
                        for tc in getattr(m, "tool_calls", []) or []:
                            key, en, a = TOOL_LABELS.get(tc["name"], (tc["name"], tc["name"], tc["name"]))
                            await _emit(id=tc["id"] or key, group="agent", status="running",
                                        label=a if ar else en)
                    elif m.type == "tool":
                        status = "done" if getattr(m, "status", "success") != "error" else "error"
                        await _emit(id=m.tool_call_id, group="agent", status=status,
                                    detail=_summarize_tool(m.name, m.content, lang))
                if upd.get("structured_response") is not None:
                    sr = upd["structured_response"]
                    report = sr.model_dump() if hasattr(sr, "model_dump") else dict(sr)
    except quota.QuotaUnavailable as e:
        await _emit(id="think", group="agent", status="skip",
                    detail=("انتهت الحصة اليومية" if ar else "daily AI quota used up") if e.kind == "day"
                    else (f"الحصة ممتلئة، أعد المحاولة بعد {e.wait_s:.0f} ث" if ar else f"quota busy, retry in {e.wait_s:.0f} s"))
        return {"report": None, "safety": [], "error": "quota",
                "quota": {"kind": e.kind, "wait_s": e.wait_s if e.kind != "day" else None,
                          "reset_in_s": (quota.next_reset() - quota.datetime.now(quota.PACIFIC)).total_seconds()}}
    except Exception as e:  # noqa: BLE001
        await _emit(id="think", group="agent", status="error", detail=type(e).__name__)
        return {"report": None, "safety": [], "error": f"{type(e).__name__}: {e}"}

    analysis = STORE.analysis.get(image_id) if image_id else None
    safety = safety_review(report or {}, analysis)
    # The AI may never sound more certain than the measurement it is based on.
    order = {"low": 0, "medium": 1, "high": 2}
    meas_conf = (analysis or {}).get("confidence")
    if report and meas_conf in order and order.get(report.get("confidence"), 0) > order[meas_conf]:
        report["confidence"] = meas_conf
        safety.append("confidence_capped")
    await _emit(id="safety", group="agent", status="warn" if safety else "done",
                label="مراجعة السلامة" if ar else "Safety review",
                detail=(", ".join(safety) if safety else ("لا توجد مخاوف" if ar else "No issues found")))
    result = {"report": report, "safety": safety, "error": None if report else "no report"}
    if cache_key and report:
        if len(_CACHE) > 200:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[cache_key] = result
    return result


def quota_status() -> dict:
    """Usage of every model in the chain (main first)."""
    return quota.GUARD.status(model_chain())
