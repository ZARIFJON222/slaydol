import asyncio
import base64
import hashlib
import hmac
import html
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, Update
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from app.config import ADMIN_IDS, BOT_TOKEN, FIREBASE_CREDENTIALS_JSON, GENERATED_DIR, WEBAPP_DIR
from app.db import get_user_generations, init_firestore, record_generation
from app.handlers import admin, generator, user
from app.locales import TEXTS
from app.logger import setup_logging
from app.middlewares import AccessMiddleware
from app.services.ai_content import MissingApiKeyError, generate_referat_data, generate_slide_deck_data
from app.services.docx_builder import build_referat_docx
from app.services.pptx_builder import THEMES, build_presentation

logger = setup_logging()
fastapi_app = FastAPI(title="SlaydYasa Studio API")

_dp: Dispatcher | None = None


def _get_bot() -> Bot:
    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def _get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        init_firestore()
        dp = Dispatcher(storage=MemoryStorage())
        access_mw = AccessMiddleware()
        dp.message.middleware(access_mw)
        dp.callback_query.middleware(access_mw)
        dp.include_router(admin.router)
        dp.include_router(user.router)
        dp.include_router(generator.router)
        _dp = dp
    return _dp


def _safe_filename(text: str, ext: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip())[:42].strip("_")
    return f"{slug or 'SlaydYasa'}_{int(time.time())}.{ext}"


def _extract_user_id(request: Request) -> int:
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    if init_data:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            raise HTTPException(status_code=401, detail="Missing hash")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            raise HTTPException(status_code=401, detail="Invalid signature")

        user_obj = json.loads(pairs.get("user", "{}"))
        uid = int(user_obj.get("id", 0))
        if not uid:
            raise HTTPException(status_code=401, detail="Missing user id")
        return uid

    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1"):
        return next(iter(ADMIN_IDS), 0)

    raise HTTPException(status_code=401, detail="Unauthorized")


@fastapi_app.get("/")
async def serve_index():
    return FileResponse(WEBAPP_DIR / "index.html")


@fastapi_app.get("/static/{filename:path}")
async def serve_static(filename: str):
    safe = Path(filename).name
    target = WEBAPP_DIR / safe
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target)


@fastapi_app.get("/api/health")
async def health():
    return {"ok": True, "bot": "@SlaydYasa_robot", "runtime": "vercel"}


@fastapi_app.get("/api/diag")
async def diag():
    fb_ok = False
    fb_error = ""
    try:
        init_firestore()
        fb_ok = True
    except Exception as exc:
        fb_error = f"{type(exc).__name__}: {exc}"
    return {
        "ok": fb_ok and bool(BOT_TOKEN),
        "has_bot_token": bool(BOT_TOKEN),
        "has_fb_json": bool(FIREBASE_CREDENTIALS_JSON),
        "fb_len": len(FIREBASE_CREDENTIALS_JSON),
        "fb_starts_with": FIREBASE_CREDENTIALS_JSON[:1],
        "fb_ok": fb_ok,
        "fb_error": fb_error,
    }


@fastapi_app.get("/api/history")
async def history(request: Request):
    init_firestore()
    uid = _extract_user_id(request)
    items = await get_user_generations(uid, limit=12) if uid else []
    serialized: list[dict[str, Any]] = []
    for it in items:
        ts = it.get("created_at")
        iso_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
        serialized.append(
            {
                "type": it.get("type", "slide"),
                "topic": it.get("topic", ""),
                "variant": it.get("variant", ""),
                "lang": it.get("lang", "uz"),
                "count": it.get("count", 0),
                "created_at": iso_ts,
            }
        )
    return {"ok": True, "items": serialized}


@fastapi_app.post("/api/generate/slide")
async def generate_slide(request: Request):
    init_firestore()
    uid = _extract_user_id(request)
    body = await request.json()

    topic = str(body.get("topic", "")).strip()
    author = str(body.get("author", "")).strip()[:80]
    lang = "ru" if body.get("lang") == "ru" else "uz"
    theme_key = str(body.get("theme", "obsidian_gold"))
    if theme_key not in THEMES:
        theme_key = "obsidian_gold"
    try:
        count = int(body.get("count", 10))
    except (TypeError, ValueError):
        count = 10
    count = max(4, min(20, count))

    if len(topic) < 4:
        return JSONResponse({"ok": False, "error": "Mavzu kamida 4 ta harf bo'lishi kerak"}, status_code=400)

    out_file: Path | None = None
    try:
        deck_data = await generate_slide_deck_data(topic, author, count, lang)
        out_file = GENERATED_DIR / _safe_filename(topic, "pptx")
        await asyncio.to_thread(build_presentation, deck_data, theme_key, author, lang, out_file)

        file_bytes = out_file.read_bytes()
        actual_slides = len(deck_data.get("slides", [])) + 2
        theme_name = THEMES[theme_key]["name_uz" if lang == "uz" else "name_ru"]
        caption = TEXTS[lang]["slide_caption"].format(
            topic=html.escape(topic), theme=theme_name, count=actual_slides
        )

        sent_ok = False
        if uid:
            bot = _get_bot()
            try:
                await bot.send_document(
                    uid,
                    BufferedInputFile(file_bytes, filename=out_file.name),
                    caption=caption,
                )
                sent_ok = True
            except Exception as exc:
                logger.warning("Vercel chatga yuborishda xato (uid=%s): %s", uid, exc)
            finally:
                await bot.session.close()
            await record_generation(uid, "slide", topic, theme_key, lang, count)

        return {
            "ok": True,
            "title": deck_data.get("title", topic),
            "slide_count": actual_slides,
            "filename": out_file.name,
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "sent_to_chat": sent_ok,
        }
    except MissingApiKeyError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
    except Exception as exc:
        logger.exception("Vercel slayd xatosi")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    finally:
        if out_file and out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass


@fastapi_app.post("/api/generate/referat")
async def generate_referat(request: Request):
    init_firestore()
    uid = _extract_user_id(request)
    body = await request.json()

    topic = str(body.get("topic", "")).strip()
    author = str(body.get("author", "")).strip()[:80]
    lang = "ru" if body.get("lang") == "ru" else "uz"
    doc_type = str(body.get("doc_type", "Referat" if lang == "uz" else "Реферат")).strip()[:40]
    size_tier = str(body.get("size_tier", "medium"))
    if size_tier not in ("short", "medium", "long"):
        size_tier = "medium"

    if len(topic) < 4:
        return JSONResponse({"ok": False, "error": "Mavzu kamida 4 ta harf bo'lishi kerak"}, status_code=400)

    out_file: Path | None = None
    try:
        ref_data = await generate_referat_data(topic, author, doc_type, size_tier, lang)
        out_file = GENERATED_DIR / _safe_filename(topic, "docx")
        await asyncio.to_thread(build_referat_docx, ref_data, doc_type, author, lang, out_file)

        file_bytes = out_file.read_bytes()
        caption = TEXTS[lang]["referat_caption"].format(
            topic=html.escape(topic), doc_type=html.escape(doc_type)
        )

        sent_ok = False
        if uid:
            bot = _get_bot()
            try:
                await bot.send_document(
                    uid,
                    BufferedInputFile(file_bytes, filename=out_file.name),
                    caption=caption,
                )
                sent_ok = True
            except Exception as exc:
                logger.warning("Vercel chatga yuborishda xato (uid=%s): %s", uid, exc)
            finally:
                await bot.session.close()
            await record_generation(uid, "referat", topic, size_tier, lang, len(ref_data.get("sections", [])))

        return {
            "ok": True,
            "title": ref_data.get("title", topic),
            "filename": out_file.name,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "sent_to_chat": sent_ok,
        }
    except MissingApiKeyError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
    except Exception as exc:
        logger.exception("Vercel referat xatosi")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    finally:
        if out_file and out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass


@fastapi_app.post("/api/webhook")
async def telegram_webhook(request: Request):
    bot = _get_bot()
    try:
        raw = await request.json()
        update = Update.model_validate(raw)
        dp = _get_dispatcher()
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as exc:
        logger.exception("Webhook xatosi")
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=200)
    finally:
        await bot.session.close()


async def app(scope, receive, send):
    """Restores original /api/... path when Vercel rewrites /api/(.*) -> /api/index?__p=$1."""
    if scope["type"] == "http" and scope.get("path") == "/api/index":
        from urllib.parse import urlencode

        qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")
        params = dict(parse_qsl(qs, keep_blank_values=True))
        sub = params.pop("__p", "").lstrip("/")
        if sub:
            scope = dict(scope)
            scope["path"] = f"/api/{sub}"
            scope["query_string"] = urlencode(params).encode("utf-8")
    await fastapi_app(scope, receive, send)
