"""
nodes.py — Full-Scan RAG with 2 nodes: Logic + Formatter.
No vector DB, no embeddings. LLM evaluates platforms.json directly.
"""

import json
import os
import re
import time
from typing import Any

from langchain_groq import ChatGroq  # type: ignore[import-untyped]
from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]


# ─── Config ───────────────────────────────────────────────────────────────────

_PRIMARY = "llama-3.3-70b-versatile"
_FALLBACK = "llama-3.1-8b-instant"
_PLATFORMS_PATH = os.path.join(os.path.dirname(__file__), "data", "platforms.json")

# ─── Platforms Cache ──────────────────────────────────────────────────────────

_platforms_cache: list[dict[str, Any]] | None = None
_platforms_text_cache: str | None = None


def _load_platforms() -> list[dict[str, Any]]:
    global _platforms_cache
    if _platforms_cache is None:
        with open(_PLATFORMS_PATH, "r", encoding="utf-8") as f:
            _platforms_cache = json.load(f)
    return _platforms_cache


def _platforms_as_text() -> str:
    global _platforms_text_cache
    if _platforms_text_cache is None:
        lines: list[str] = []
        for i, p in enumerate(_load_platforms(), 1):
            gts = ", ".join(p.get("giving_types", []))
            svcs = " | ".join(p.get("services", []))
            lines.append(f"{i}. {p['name']} [{gts}]: {svcs}")
        _platforms_text_cache = "\n".join(lines)
    return _platforms_text_cache


# ─── Smart LLM with Auto-Fallback ────────────────────────────────────────────

def _invoke_llm(
    messages: list,
    temperature: float = 0,
    primary: str = _PRIMARY,
    max_tokens: int | None = None,
) -> Any:
    kwargs: dict[str, Any] = {}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    for model in (primary, _FALLBACK):
        try:
            llm = ChatGroq(model=model, temperature=temperature)
            return llm.invoke(messages, **kwargs)
        except Exception as e:
            err = str(e).lower()
            is_rate = "rate" in err or "429" in err or "limit" in err
            if is_rate and model == primary and model != _FALLBACK:
                time.sleep(1)
                continue
            raise


def get_llm_fast(temperature: float = 0) -> ChatGroq:
    return ChatGroq(model=_FALLBACK, temperature=temperature)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_general_platforms() -> list[dict[str, Any]]:
    return [
        {
            "name": p["name"], "url": p["url"], "direct_url": p["direct_url"],
            "supervisor": p["supervisor"], "intervention_type": p["intervention_type"],
            "giving_types": p["giving_types"], "services": p["services"],
            "emergency": p.get("emergency", False),
        }
        for p in _load_platforms()
        if p["name"] in ("منصة إحسان (المنصة الوطنية)", "منصة تبرع (وزارة الموارد)")
    ]


# ═════════════════════════════════════════════
#  Node 1 — Logic (Strict Filter + Full Scan)
# ═════════════════════════════════════════════

def logic_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Full-Scan Logic — يحلل الطلب ضد كل المنصات ويختار فقط
    المنصات ذات الارتباط المباشر والقوي بطلب المستخدم.
    """
    user_input: str = state["user_input"]

    try:
        system_prompt = f"""أنت خبير عطاء خيري سعودي في منصة «دالّ». مهمتك تحليل طلب المستخدم واختيار المنصات المناسبة بدقة عالية.

═══ المهام ═══
1. صنّف الطلب: استفسار | طبي | سكني | مالي | جهدي | مشاريع | غير_ذي_صلة
2. أعد صياغة الطلب بالفصحى
3. اختر كل المنصات اللي خدماتها تطابق الطلب مباشرة وبقوة

═══ ⚠️ أولاً: هل الطلب استفسار؟ (أهم قاعدة) ═══
صنّف كـ "استفسار" إذا المستخدم يسأل عن دالّ نفسه أو عن المنصات المتاحة أو عن الخدمات — وليس يطلب مساعدة خيرية محددة.
كلمات تدل على استفسار: "وش عندك" / "كم منصة" / "وش المنصات" / "اعرض لي" / "وش تقدر تسوي" / "كيف تشتغل" / "وش هو دالّ" / "عندك منصة...؟" / "هل تدعم...؟" / "وش الخدمات" / "وش أنواع" / "المنصات اللي عندك" / "ورّني" / "بيّن لي"
→ إذا السؤال عام (كل المنصات / وش عندك) أرجع أسماء كل الـ {len(_load_platforms())} منصة.
→ إذا السؤال عن نوع معين (عندك منصة طبية؟) أرجع المنصات ذات الصلة فقط.

═══ قواعد التصنيف (إذا ليس استفسار) ═══
- "جهدي" = فقط التطوع بالجهد البدني (أتطوع، أخدم، أبي أساعد بنفسي)
- تبرع بأشياء عينية (ملابس، طعام، عفش، أغراض) = "مشاريع"
- "أتبرع" بفلوس / زكاة / صدقة = "مالي"
- "أتبرع" بأشياء = "مشاريع"
- "أبي وظيفة" أو طلب لا علاقة له بالعمل الخيري إطلاقاً = "غير_ذي_صلة"

═══ الفلترة الصارمة (Strict Filter) ═══
- اختر فقط المنصات ذات الارتباط المباشر والقوي بالطلب
- إذا الطلب "سكن" → اختر منصات السكن فقط، لا تضيف منصات طبية
- إذا الطلب "طعام" → اختر منصات الإطعام فقط، لا تضيف منصات تطوع
- إذا الطلب "ملابس/كسوة" → اختر منصات الكسوة فقط
- إذا إحسان أو تبرع تغطي الطلب + جمعية متخصصة، أدرجهم كلهم
- لا تضيف منصة إلا إذا خدماتها المذكورة تخدم الطلب تحديداً
- استثناء: إذا التصنيف "استفسار" عام → أرجع كل المنصات

═══ إتقان اللهجة السعودية ═══
- "عفش/أثاث" = أثاث منزلي
- "قش" = أغراض/أشياء قديمة
- "فزعة" = مساعدة عاجلة
- "فرّج همي/فرجت" = تسديد ديون/فك كربة
- "أبي أعطي/وابي اعطيها" = أبي أتبرع
- "زايد/زايدة" = فائض للتبرع
- "أكل" = طعام/إطعام
- "حلال" = زكاة أو صدقة (حسب السياق)

═══ كل المنصات ({len(_load_platforms())}) ═══
{_platforms_as_text()}

═══ أجب بـ JSON فقط — بدون أي نص إضافي ═══
{{"category": "التصنيف", "rewritten": "إعادة الصياغة", "platforms": ["اسم1", "اسم2"]}}

إذا "استفسار" عام: {{"category": "استفسار", "rewritten": "...", "platforms": ["كل أسماء المنصات"]}}
إذا "غير_ذي_صلة": {{"category": "غير_ذي_صلة", "rewritten": "...", "platforms": []}}"""

        response = _invoke_llm(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_input)],
            temperature=0,
            primary=_PRIMARY,
        )

        raw: str = response.content.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            parsed = json.loads(match.group()) if match else {}

        category = parsed.get("category", "غير_ذي_صلة")
        valid_cats = {"طبي", "سكني", "مالي", "جهدي", "مشاريع", "استفسار", "غير_ذي_صلة"}
        if category not in valid_cats:
            category = "غير_ذي_صلة"

        rewritten = parsed.get("rewritten", user_input)
        selected_names: set[str] = set(parsed.get("platforms", []))

        all_platforms = _load_platforms()

        def _platform_dict(p: dict[str, Any]) -> dict[str, Any]:
            return {
                "name": p["name"], "url": p["url"], "direct_url": p["direct_url"],
                "supervisor": p["supervisor"], "intervention_type": p["intervention_type"],
                "giving_types": p["giving_types"], "services": p["services"],
                "emergency": p.get("emergency", False),
            }

        # For general "استفسار" queries, return ALL platforms directly
        # (LLM name matching is unreliable — names don't match exactly)
        if category == "استفسار":
            validated = [_platform_dict(p) for p in all_platforms]
        else:
            validated = [
                _platform_dict(p)
                for p in all_platforms
                if p["name"] in selected_names
            ]

        return {
            "category": category,
            "rewritten_query": rewritten,
            "validated_platforms": validated,
        }

    except Exception:
        return {
            "category": "مالي",
            "rewritten_query": user_input,
            "validated_platforms": _get_general_platforms(),
        }


# ═════════════════════════════════════════════
#  Node 2 — Formatter (Short Saudi Response)
# ═════════════════════════════════════════════

# ─── Static responses (no LLM needed) ────────────────────────────────────────

_IRRELEVANT_RESPONSE = (
    "نعتذر منك، «دالّ» مخصص للمنصات الخيرية الرسمية فقط.\n"
    "كيف أقدر أخدمك في هذا المجال؟"
)

_NOT_FOUND_TEMPLATE = (
    "عذراً، بحثت في المنصات الرسمية ولم أجد جهة متخصصة حصراً في ({query}).\n"
    "لكن تقدر تطلع على منصة إحسان الشاملة: ehsan.sa\n\n"
    "الله يوفقك ويسهّل أمرك 🤲"
)


def formatter_node(state: dict[str, Any]) -> dict[str, Any]:
    """رد ثابت — بدون LLM call. أسرع وأوفر وأضمن."""
    category: str = state.get("category", "")
    platforms: list[dict[str, Any]] = state.get("validated_platforms", [])

    if category == "غير_ذي_صلة":
        return {"final_response": _IRRELEVANT_RESPONSE}

    if category == "استفسار":
        count = len(platforms)
        if count > 0:
            return {"final_response": (
                f"هلا فيك! عندي {count} منصة خيرية رسمية وموثوقة 👇\n"
                "تقدر تتصفحهم وتضغط على أي بطاقة للانتقال للموقع الرسمي.\n\n"
                "وإذا تبي تبحث عن خدمة معينة، قولي وش تحتاج وبدلّك 🤲"
            )}
        return {"final_response": (
            "هلا فيك! أنا «دالّ»، مساعدك الذكي للمنصات الخيرية السعودية الرسمية.\n"
            "قولي وش تحتاج (مثلاً: سداد فاتورة، علاج مريض، كفالة يتيم) وبدلّك على أفضل المنصات 🤲"
        )}

    if not platforms:
        rewritten = state.get("rewritten_query", state.get("user_input", "طلبك"))
        return {"final_response": _NOT_FOUND_TEMPLATE.format(query=rewritten)}

    count = len(platforms)
    return {"final_response": (
        f"أبشر، لقيت لك {count} منصات رسمية تخدم طلبك 👇\n"
        "تقدر تضغط على البطاقة للانتقال للموقع الرسمي مباشرة.\n\n"
        "الله يكتب أجرك 🤲"
    )}
