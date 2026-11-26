import asyncio
import hashlib
import hmac
import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from aiogram import Bot
from aiogram.types import FSInputFile
from aiohttp import web

from app.config import ADMIN_IDS, BOT_TOKEN, GENERATED_DIR, WEBAPP_DIR
from app.db import get_user_generations, record_generation
from app.locales import TEXTS
from app.services.ai_content import MissingApiKeyError, generate_referat_data, generate_slide_deck_data
from app.services.docx_builder import build_referat_docx
from app.services.pptx_builder import THEMES, build_presentation

logger = logging.getLogger("slayd_yasa_bot.webapp")


def _safe_filename(text: str, ext: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip())[:42].strip("_")
    return f"{slug or 'SlaydYasa'}_{int(time.time())}.{ext}"


def extract_user_id(request: web.Request) -> int:
    """Verifies Telegram WebApp initData HMAC-SHA256 or allows local browser preview."""
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    if init_data:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            raise web.HTTPUnauthorized(text=json.dumps({"ok": False, "error": "Missing hash"}), content_type="application/json")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            raise web.HTTPUnauthorized(text=json.dumps({"ok": False, "error": "Invalid signature"}), content_type="application/json")

        user_raw = pairs.get("user", "{}")
        user_obj = json.loads(user_raw)
        uid = int(user_obj.get("id", 0))
        if not uid:
            raise web.HTTPUnauthorized(text=json.dumps({"ok": False, "error": "Missing user id"}), content_type="application/json")
        return uid

    if request.remote in ("127.0.0.1", "::1"):
        return next(iter(ADMIN_IDS), 0)

    raise web.HTTPUnauthorized(text=json.dumps({"ok": False, "error": "Unauthorized"}), content_type="application/json")


def create_webapp(bot: Bot) -> web.Application:
    app = web.Application()

    async def handle_index(request: web.Request) -> web.FileResponse:
        return web.FileResponse(WEBAPP_DIR / "index.html")

    async def handle_health(request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "bot": "@SlaydYasa_robot"})

    async def handle_history(request: web.Request) -> web.Response:
        uid = extract_user_id(request)
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
        return web.json_response({"ok": True, "items": serialized})

    async def handle_generate_slide(request: web.Request) -> web.Response:
        uid = extract_user_id(request)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON body"}, status=400)

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
            return web.json_response({"ok": False, "error": "Mavzu kamida 4 ta harf bo'lishi kerak"}, status=400)

        try:
            deck_data = await generate_slide_deck_data(topic, author, count, lang)
            out_file = GENERATED_DIR / _safe_filename(topic, "pptx")
            await asyncio.to_thread(build_presentation, deck_data, theme_key, author, lang, out_file)

            actual_slides = len(deck_data.get("slides", [])) + 2
            theme_name = THEMES[theme_key]["name_uz" if lang == "uz" else "name_ru"]
            caption = TEXTS[lang]["slide_caption"].format(
                topic=html.escape(topic), theme=theme_name, count=actual_slides
            )

            sent_ok = False
            if uid:
                try:
                    await bot.send_document(uid, FSInputFile(out_file), caption=caption)
                    sent_ok = True
                except Exception as exc:
                    logger.warning("WebApp chatga yuborishda xato (uid=%s): %s", uid, exc)

                await record_generation(uid, "slide", topic, theme_key, lang, count)

            return web.json_response(
                {
                    "ok": True,
                    "title": deck_data.get("title", topic),
                    "slide_count": actual_slides,
                    "filename": out_file.name,
                    "download_url": f"/api/download/{out_file.name}",
                    "sent_to_chat": sent_ok,
                }
            )
        except MissingApiKeyError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=503)
        except Exception as exc:
            logger.exception("WebApp slayd yaratish xatosi")
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    async def handle_generate_referat(request: web.Request) -> web.Response:
        uid = extract_user_id(request)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON body"}, status=400)

        topic = str(body.get("topic", "")).strip()
        author = str(body.get("author", "")).strip()[:80]
        lang = "ru" if body.get("lang") == "ru" else "uz"
        doc_type = str(body.get("doc_type", "Referat" if lang == "uz" else "Реферат")).strip()[:40]
        size_tier = str(body.get("size_tier", "medium"))
        if size_tier not in ("short", "medium", "long"):
            size_tier = "medium"

        if len(topic) < 4:
            return web.json_response({"ok": False, "error": "Mavzu kamida 4 ta harf bo'lishi kerak"}, status=400)

        try:
            ref_data = await generate_referat_data(topic, author, doc_type, size_tier, lang)
            out_file = GENERATED_DIR / _safe_filename(topic, "docx")
            await asyncio.to_thread(build_referat_docx, ref_data, doc_type, author, lang, out_file)

            caption = TEXTS[lang]["referat_caption"].format(
                topic=html.escape(topic), doc_type=html.escape(doc_type)
            )

            sent_ok = False
            if uid:
                try:
                    await bot.send_document(uid, FSInputFile(out_file), caption=caption)
                    sent_ok = True
                except Exception as exc:
                    logger.warning("WebApp chatga yuborishda xato (uid=%s): %s", uid, exc)

                await record_generation(uid, "referat", topic, size_tier, lang, len(ref_data.get("sections", [])))

            return web.json_response(
                {
                    "ok": True,
                    "title": ref_data.get("title", topic),
                    "filename": out_file.name,
                    "download_url": f"/api/download/{out_file.name}",
                    "sent_to_chat": sent_ok,
                }
            )
        except MissingApiKeyError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=503)
        except Exception as exc:
            logger.exception("WebApp referat yaratish xatosi")
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    async def handle_download(request: web.Request) -> web.FileResponse:
        safe = Path(request.match_info["filename"]).name
        file_path = GENERATED_DIR / safe
        if not file_path.exists() or not file_path.is_file():
            raise web.HTTPNotFound(text="Fayl topilmadi")
        return web.FileResponse(
            file_path,
            headers={"Content-Disposition": f'attachment; filename="{safe}"'},
        )

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/history", handle_history)
    app.router.add_post("/api/generate/slide", handle_generate_slide)
    app.router.add_post("/api/generate/referat", handle_generate_referat)
    app.router.add_get("/api/download/{filename}", handle_download)
    app.router.add_static("/static", WEBAPP_DIR)
    return app
