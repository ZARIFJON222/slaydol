import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from app.config import ADMIN_IDS
from app.db import get_settings, get_user, schedule_user_upsert
from app.locales import TEXTS, resolve_lang

logger = logging.getLogger("slayd_yasa_bot.access")

ALLOWED_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}


async def get_missing_channels(bot: Bot, user_id: int, channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for ch in channels:
        chat_id = ch.get("id")
        if not chat_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status not in ALLOWED_STATUSES:
                missing.append(ch)
        except Exception:
            continue
    return missing


def build_sub_keyboard(channels: list[dict[str, Any]], lang: str) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        url = ch.get("url")
        title = ch.get("title") or str(ch.get("id"))
        if url:
            rows.append([InlineKeyboardButton(text=f"📢 {title}", url=url)])
    rows.append([InlineKeyboardButton(text=TEXTS[lang]["sub_check_btn"], callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


class AccessMiddleware(BaseMiddleware):
    """Fast cached user registration, maintenance mode, mandatory subscription & latency logging."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        t0 = time.perf_counter()
        user = data.get("event_from_user")
        if user is None or user.is_bot:
            return await handler(event, data)

        # Non-blocking background sync + memory cache (0ms lag!)
        schedule_user_upsert(user)

        action = (
            f"msg:{event.text[:40]!r}"
            if isinstance(event, Message) and event.text
            else f"cb:{event.data}"
            if isinstance(event, CallbackQuery)
            else type(event).__name__
        )

        try:
            if user.id in ADMIN_IDS:
                return await handler(event, data)

            settings = await get_settings()
            db_user = await get_user(user.id)
            lang = resolve_lang((db_user or {}).get("bot_lang") or user.language_code)

            if settings.get("maintenance_mode", False):
                if isinstance(event, Message):
                    await event.answer(TEXTS[lang]["maintenance"])
                elif isinstance(event, CallbackQuery):
                    await event.answer("🛠 Texnik ishlar olib borilmoqda...", show_alert=True)
                return None

            if settings.get("sub_enabled", False) and settings.get("sub_channels"):
                if isinstance(event, CallbackQuery) and event.data == "sub:check":
                    return await handler(event, data)

                bot: Bot = data["bot"]
                missing = await get_missing_channels(bot, user.id, settings["sub_channels"])
                if missing:
                    kb = build_sub_keyboard(missing, lang)
                    if isinstance(event, Message):
                        await event.answer(TEXTS[lang]["sub_required"], reply_markup=kb)
                    elif isinstance(event, CallbackQuery):
                        await event.message.answer(TEXTS[lang]["sub_required"], reply_markup=kb)
                        await event.answer()
                    return None

            return await handler(event, data)
        finally:
            took_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "user=%s (@%s) | %s | %.0fms",
                user.id,
                user.username or "-",
                action,
                took_ms,
            )
