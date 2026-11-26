import asyncio
import html
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from aiohttp import web

from app.config import ADMIN_IDS, BOT_TOKEN, WEBAPP_PORT
from app.db import get_settings, init_firestore, log_error_to_db
from app.handlers import admin, generator, user
from app.logger import setup_logging
from app.middlewares import AccessMiddleware
from app.webapp_server import create_webapp

logger = setup_logging()


async def main() -> None:
    init_firestore()
    settings = await get_settings()
    logger.info(
        "Firestore ulandi. Texnik ishlar=%s | Majburiy obuna=%s | Adminlar=%s",
        settings.get("maintenance_mode"),
        settings.get("sub_enabled"),
        ADMIN_IDS,
    )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        exc = event.exception
        update = event.update
        user_obj = None
        action = type(update).__name__
        if update.message:
            user_obj = update.message.from_user
            action = f"msg:{(update.message.text or '')[:80]}"
        elif update.callback_query:
            user_obj = update.callback_query.from_user
            action = f"cb:{update.callback_query.data}"

        uid = user_obj.id if user_obj else None
        uname = user_obj.username if user_obj else None
        tb_str = traceback.format_exc()

        logger.error(
            "XATOLIK | user=%s (@%s) | %s | %s: %s\n%s",
            uid,
            uname or "-",
            action,
            type(exc).__name__,
            exc,
            tb_str,
        )

        await log_error_to_db(uid, uname, action, type(exc).__name__, str(exc), tb_str)

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🚨 <b>Botda xatolik!</b>\n"
                    f"👤 User: <code>{uid}</code> @{uname or '-'}\n"
                    f"📌 Amaliyot: <code>{html.escape(action)}</code>\n"
                    f"❌ Xato: <code>{html.escape(type(exc).__name__)}: {html.escape(str(exc)[:300])}</code>",
                )
            except Exception:
                pass
        return True

    access_mw = AccessMiddleware()
    dp.message.middleware(access_mw)
    dp.callback_query.middleware(access_mw)

    dp.include_router(admin.router)
    dp.include_router(user.router)
    dp.include_router(generator.router)

    webapp = create_webapp(bot)
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEBAPP_PORT)
    await site.start()
    logger.info("WebApp Studio server ishga tushdi: http://127.0.0.1:%s", WEBAPP_PORT)

    try:
        logger.info("@SlaydYasa_robot ishga tushdi (polling)...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
