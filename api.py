"""
FastAPI bridge — يربط الفرونتند مع LangGraph pipeline.
شغّله بـ: uvicorn api:app --host 0.0.0.0 --port 8080
"""

import logging
import os
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        }
    except Exception as e:
        logger.error("Query error: %s", e, exc_info=True)
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
        logger.error("Chat error: %s", e, exc_info=True)
        err = str(e).lower()
        if "rate" in err or "429" in err or "limit" in err:
            return {"response": _RATE_LIMIT_MSG}
        return {"response": "عذراً، حدث خطأ. حاول مرة أخرى."}


# ─── Serve Frontend ───────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
FRONTEND_DALL = os.path.join(BASE_DIR, "frontend-dall")


@app.get("/")
async def serve_dall():
    return FileResponse(os.path.join(FRONTEND_DALL, "index.html"))


app.mount("/assets", StaticFiles(directory=FRONTEND_DALL), name="frontend-dall")
