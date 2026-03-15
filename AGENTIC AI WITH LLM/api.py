"""
FastAPI bridge — يربط الفرونتند مع LangGraph pipeline.
شغّله بـ: uvicorn api:app --host 0.0.0.0 --port 8080
"""

import json
import os
import re
import threading
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from graph import build_graph
from nodes import get_llm_fast
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

load_dotenv()

app = FastAPI(title="دالّ API")

_RATE_LIMIT_MSG = "نعتذر منك، الخدمة تواجه ضغطاً كبيراً حالياً. فضلاً حاول مجدداً بعد قليل."


# ─── Stats Counter (Thread-Safe JSON File) ───────────────────
_STATS_PATH = os.path.join(os.path.dirname(__file__), "data", "stats.json")
_stats_lock = threading.Lock()


def _load_stats() -> dict:
    try:
        with open(_STATS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"total_visits": 0, "actual_impact_count": 0}


def _save_stats(stats: dict) -> None:
    with open(_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ───────────────────────────────────────────────────
class QueryRequest(BaseModel):
    message: str


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []
    platforms: list[dict[str, Any]] = []
    previous_response: str = ""


class LinkRequest(BaseModel):
    url: str


# ─── Routes ───────────────────────────────────────────────────
@app.post("/api/query")
async def query(req: QueryRequest):
    """الاستعلام الرئيسي — يشغّل الـ pipeline كامل."""
    try:
        graph = build_graph()
        result = graph.invoke({"user_input": req.message})

        return {
            "response": result.get("final_response", ""),
            "category": result.get("category", ""),
            "platforms": result.get("validated_platforms", []),
            "reset_context": True,
        }
    except Exception as e:
        err = str(e).lower()
        if "rate" in err or "429" in err or "limit" in err:
            msg = _RATE_LIMIT_MSG
        else:
            msg = "عذراً، حدث خطأ في المعالجة. حاول مرة أخرى."
        return {"response": msg, "category": "", "platforms": []}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """الدردشة التكميلية — أسئلة متابعة عن المنصات فقط."""
    try:
        context_parts = []
        for idx, p in enumerate(req.platforms, 1):
            context_parts.append(
                f"— المنصة {idx}: {p.get('name', '')}\n"
                f"  الجهة: {p.get('supervisor', '')}\n"
                f"  الخدمات: {', '.join(p.get('services', [])[:4])}\n"
                f"  الرابط: {p.get('direct_url', '')}"
            )

        system_msg = SystemMessage(content=(
            "أنت «دالّ»، مستشار خيري سعودي ودود.\n"
            "أجب باختصار (٣-٤ أسطر). شرح المنصات المعروضة فقط. ممنوع اقتراح منصات جديدة.\n\n"
            + "\n\n".join(context_parts)
            + ("\n\nالرد السابق:\n" + req.previous_response if req.previous_response else "")
        ))

        recent = req.history[-6:]
        lc_messages: list[Any] = [system_msg]
        for m in recent:
            if m.get("role") == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            else:
                lc_messages.append(AIMessage(content=m["content"]))

        llm = get_llm_fast(temperature=0)
        reply = llm.invoke(lc_messages, max_tokens=150)

        return {"response": reply.content}

    except Exception as e:
        err = str(e).lower()
        if "rate" in err or "429" in err or "limit" in err:
            return {"response": _RATE_LIMIT_MSG}
        return {"response": "عذراً، حدث خطأ. حاول مرة أخرى."}


# ─── Link Security Analyzer ──────────────────────────────
_SHORTENED_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "rebrand.ly", "short.link", "cutt.ly", "lnkd.in",
}


def _analyze_link(raw_url: str) -> dict[str, Any]:
    """Analyze a URL for safety in donation/charity context."""
    url = raw_url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    scheme = parsed.scheme.lower()

    checks: list[dict[str, str]] = []
    danger_level = 0  # 0=safe, 1=suspicious, 2=dangerous

    # 1) SSL Check
    if scheme == "http":
        checks.append({
            "test": "التشفير (SSL)",
            "result": "غير آمن",
            "detail": "الرابط لا يستخدم تشفير HTTPS — بياناتك قد تكون مكشوفة",
        })
        danger_level = max(danger_level, 2)
    else:
        checks.append({
            "test": "التشفير (SSL)",
            "result": "آمن",
            "detail": "الرابط يستخدم تشفير HTTPS",
        })

    # 2) Shortened URL Check
    if hostname in _SHORTENED_DOMAINS:
        checks.append({
            "test": "رابط مختصر",
            "result": "مشبوه",
            "detail": "رابط مختصر يخفي الوجهة النهائية — لا تدخل بيانات بنكية",
        })
        danger_level = max(danger_level, 1)
    else:
        checks.append({
            "test": "رابط مختصر",
            "result": "آمن",
            "detail": "الرابط كامل وواضح الوجهة",
        })

    # 3) TLD Check — .sa / .gov.sa = official Saudi
    is_sa = hostname.endswith(".sa")
    is_gov = hostname.endswith(".gov.sa")
    if is_gov:
        checks.append({
            "test": "النطاق الوطني",
            "result": "رسمي",
            "detail": "نطاق حكومي سعودي (.gov.sa) — جهة رسمية موثوقة",
        })
    elif is_sa:
        checks.append({
            "test": "النطاق الوطني",
            "result": "آمن",
            "detail": "نطاق سعودي (.sa) — مسجّل لدى هيئة الاتصالات",
        })
    else:
        # 4) Commercial domain claiming to be official
        tld = hostname.split(".")[-1] if "." in hostname else ""
        if tld in ("com", "net", "org", "info", "xyz", "online"):
            checks.append({
                "test": "النطاق الوطني",
                "result": "تحذير",
                "detail": f"نطاق تجاري (.{tld}) وليس سعودي — الجهات الرسمية تستخدم .sa",
            })
            danger_level = max(danger_level, 1)
        else:
            checks.append({
                "test": "النطاق الوطني",
                "result": "غير معروف",
                "detail": f"نطاق غير مألوف (.{tld}) — تحقق من المصدر",
            })
            danger_level = max(danger_level, 1)

    # Final verdict
    if danger_level == 0:
        verdict = "آمن ✅"
        verdict_desc = "هذا الرابط اجتاز جميع فحوصات الأمان — الموقع مشفّر ويستخدم نطاق سعودي رسمي موثوق."
        action = "يمكنك الوثوق بهذا الرابط للتبرع"
    elif danger_level == 1:
        verdict = "مشبوه ⚠️"
        verdict_desc = "هذا الرابط فيه نقاط تحتاج انتباهك — ممكن يكون رابط مختصر أو نطاق غير سعودي. لا يعني بالضرورة إنه خطير، لكن تحقق قبل ما تدخل بياناتك."
        action = "تحقق من الرابط قبل إدخال أي بيانات شخصية أو بنكية"
    else:
        verdict = "خطير 🚫"
        verdict_desc = "هذا الرابط ما يستخدم تشفير أو فيه علامات خطر واضحة — بياناتك البنكية ممكن تنكشف لو أدخلتها هنا."
        action = "لا تدخل بيانات بطاقتك البنكية هنا — قد يكون تصيّد"

    return {
        "url": raw_url,
        "hostname": hostname,
        "verdict": verdict,
        "verdict_desc": verdict_desc,
        "action": action,
        "checks": checks,
    }


@app.post("/api/analyze-link")
async def analyze_link(req: LinkRequest):
    """تحليل أمان رابط للتبرع."""
    return _analyze_link(req.url)


# ─── Stats Routes ────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    """إرجاع العدادات الحالية."""
    stats = _load_stats()
    return stats


@app.post("/api/stats/visit")
async def record_visit():
    """عداد الزيارات — يُستدعى مرة واحدة عند تحميل الصفحة."""
    with _stats_lock:
        stats = _load_stats()
        stats["total_visits"] += 1
        _save_stats(stats)
    return {"total_visits": stats["total_visits"]}


@app.post("/api/stats/impact")
async def record_impact():
    """عداد الأثر — يُستدعى فقط عند ضغط المستخدم على زر 'انتقل إلى المنصة'."""
    with _stats_lock:
        stats = _load_stats()
        stats["actual_impact_count"] += 1
        _save_stats(stats)
    return {"actual_impact_count": stats["actual_impact_count"]}


# ─── Serve Frontend ───────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
FRONTEND_DALL = os.path.join(BASE_DIR, "frontend-dall")


@app.get("/")
async def serve_dall():
    return FileResponse(os.path.join(FRONTEND_DALL, "index.html"))


app.mount("/assets", StaticFiles(directory=FRONTEND_DALL), name="frontend-dall")
