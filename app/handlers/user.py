from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db import get_settings, get_user, set_user_lang
from app.locales import (
    LANG_PROMPT_TEXT,
    TEXTS,
    language_keyboard,
    main_menu_keyboard,
    resolve_lang,
)
from app.middlewares import build_sub_keyboard, get_missing_channels

router = Router(name="user")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(LANG_PROMPT_TEXT, reply_markup=language_keyboard())


@router.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(LANG_PROMPT_TEXT, reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def cb_select_lang(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    lang = callback.data.split(":", maxsplit=1)[1]
    if lang not in ("uz", "ru"):
        lang = "uz"
    await set_user_lang(callback.from_user.id, lang)
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        TEXTS[lang]["lang_saved"],
        reply_markup=main_menu_keyboard(lang),
    )


@router.callback_query(F.data == "sub:check")
async def cb_check_sub(callback: CallbackQuery) -> None:
    settings = await get_settings()
    db_user = await get_user(callback.from_user.id)
    lang = resolve_lang((db_user or {}).get("bot_lang") or callback.from_user.language_code)

    channels = settings.get("sub_channels") or []
    missing = await get_missing_channels(callback.bot, callback.from_user.id, channels)
    if missing:
        kb = build_sub_keyboard(missing, lang)
        await callback.answer(TEXTS[lang]["sub_not_yet"], show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
        return

    await callback.message.edit_text(LANG_PROMPT_TEXT, reply_markup=language_keyboard())
    await callback.answer("✅")
