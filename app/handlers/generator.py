import asyncio
import html
import logging
import re
import time
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import GENERATED_DIR
from app.db import get_user, get_user_generations, record_generation
from app.locales import (
    LANG_PROMPT_TEXT,
    MENU_BTNS,
    TEXTS,
    cancel_keyboard,
    language_keyboard,
    main_menu_keyboard,
    resolve_lang,
)
from app.services.ai_content import MissingApiKeyError, generate_referat_data, generate_slide_deck_data
from app.services.docx_builder import build_referat_docx
from app.services.pptx_builder import THEMES, build_presentation

logger = logging.getLogger("slayd_yasa_bot.generator")
router = Router(name="generator")

ALL_SLIDE_BTNS = {MENU_BTNS["uz"]["slide"], MENU_BTNS["ru"]["slide"]}
ALL_REFERAT_BTNS = {MENU_BTNS["uz"]["referat"], MENU_BTNS["ru"]["referat"]}
ALL_HISTORY_BTNS = {MENU_BTNS["uz"]["history"], MENU_BTNS["ru"]["history"]}
ALL_LANG_BTNS = {MENU_BTNS["uz"]["lang"], MENU_BTNS["ru"]["lang"]}
ALL_CANCEL_BTNS = {MENU_BTNS["uz"]["cancel"], MENU_BTNS["ru"]["cancel"]}
ALL_SKIP_BTNS = {MENU_BTNS["uz"]["skip"], MENU_BTNS["ru"]["skip"]}


class GenStates(StatesGroup):
    slide_topic = State()
    slide_author = State()
    slide_count = State()
    slide_theme = State()

    ref_type = State()
    ref_topic = State()
    ref_author = State()
    ref_size = State()


def _safe_filename(text: str, ext: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip())[:42].strip("_")
    return f"{slug or 'SlaydYasa'}_{int(time.time())}.{ext}"


async def _get_lang(message_or_cb) -> str:
    uid = message_or_cb.from_user.id
    u = await get_user(uid)
    return resolve_lang((u or {}).get("bot_lang") or message_or_cb.from_user.language_code)


# --- Global Cancel / Main Menu Shortcuts ---

@router.message(F.text.in_(ALL_CANCEL_BTNS))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await _get_lang(message)
    await message.answer(TEXTS[lang]["cancelled"], reply_markup=main_menu_keyboard(lang))


@router.message(F.text.in_(ALL_LANG_BTNS))
async def handle_lang_btn(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(LANG_PROMPT_TEXT, reply_markup=language_keyboard())


@router.message(F.text.in_(ALL_HISTORY_BTNS))
async def handle_history_btn(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await _get_lang(message)
    items = await get_user_generations(message.from_user.id, limit=6)
    if not items:
        await message.answer(TEXTS[lang]["history_empty"], reply_markup=main_menu_keyboard(lang))
        return

    lines = []
    for idx, it in enumerate(items, start=1):
        icon = "📊" if it.get("type") == "slide" else "📄"
        topic = html.escape(str(it.get("topic", "-")))
        ts = it.get("created_at")
        dt_str = ts.strftime("%d.%m %H:%M") if hasattr(ts, "strftime") else ""
        lines.append(f"{idx}. {icon} <b>{topic}</b> <i>({dt_str})</i>")
    await message.answer(
        TEXTS[lang]["history_header"] + "\n".join(lines),
        reply_markup=main_menu_keyboard(lang),
    )


# ==================== SLIDE (PPTX) WIZARD ====================

@router.message(F.text.in_(ALL_SLIDE_BTNS))
async def start_slide_wizard(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await _get_lang(message)
    await state.set_state(GenStates.slide_topic)
    await message.answer(TEXTS[lang]["ask_slide_topic"], reply_markup=cancel_keyboard(lang))


@router.message(GenStates.slide_topic)
async def got_slide_topic(message: Message, state: FSMContext) -> None:
    lang = await _get_lang(message)
    topic = (message.text or "").strip()
    if len(topic) < 4:
        await message.answer(TEXTS[lang]["topic_too_short"])
        return
    await state.update_data(topic=topic)
    await state.set_state(GenStates.slide_author)
    await message.answer(TEXTS[lang]["ask_author"], reply_markup=cancel_keyboard(lang, allow_skip=True))


@router.message(GenStates.slide_author)
async def got_slide_author(message: Message, state: FSMContext) -> None:
    lang = await _get_lang(message)
    raw = (message.text or "").strip()
    author = "" if raw in ALL_SKIP_BTNS else raw[:80]
    await state.update_data(author=author)
    await state.set_state(GenStates.slide_count)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="6 slayd" if lang == "uz" else "6 слайдов", callback_data="scnt:6"),
                InlineKeyboardButton(text="10 slayd" if lang == "uz" else "10 слайдов", callback_data="scnt:10"),
                InlineKeyboardButton(text="14 slayd" if lang == "uz" else "14 слайдов", callback_data="scnt:14"),
            ]
        ]
    )
    await message.answer(TEXTS[lang]["ask_slide_count"], reply_markup=kb)


@router.callback_query(GenStates.slide_count, F.data.startswith("scnt:"))
async def got_slide_count(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await _get_lang(callback)
    count = int(callback.data.split(":")[1])
    await state.update_data(count=count)
    await state.set_state(GenStates.slide_theme)
    await callback.answer()

    name_key = "name_uz" if lang == "uz" else "name_ru"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=THEMES["obsidian_gold"][name_key], callback_data="sthm:obsidian_gold"),
                InlineKeyboardButton(text=THEMES["ivory_editorial"][name_key], callback_data="sthm:ivory_editorial"),
            ],
            [
                InlineKeyboardButton(text=THEMES["cobalt_tech"][name_key], callback_data="sthm:cobalt_tech"),
                InlineKeyboardButton(text=THEMES["emerald_nature"][name_key], callback_data="sthm:emerald_nature"),
            ],
        ]
    )
    await callback.message.edit_text(TEXTS[lang]["ask_slide_theme"], reply_markup=kb)


@router.callback_query(GenStates.slide_theme, F.data.startswith("sthm:"))
async def got_slide_theme(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await _get_lang(callback)
    theme_key = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    topic = data["topic"]
    author = data.get("author", "")
    count = int(data.get("count", 10))
    theme_name = THEMES.get(theme_key, THEMES["obsidian_gold"])["name_uz"]

    status_msg = await callback.message.edit_text(TEXTS[lang]["progress_ai"])
    out_file: Path | None = None
    try:
        deck_data = await generate_slide_deck_data(topic, author, count, lang)
        await status_msg.edit_text(TEXTS[lang]["progress_build"])

        out_file = GENERATED_DIR / _safe_filename(topic, "pptx")
        await asyncio.to_thread(build_presentation, deck_data, theme_key, author, lang, out_file)

        await status_msg.edit_text(TEXTS[lang]["progress_send"])
        caption = TEXTS[lang]["slide_caption"].format(
            topic=html.escape(topic), theme=theme_name, count=len(deck_data.get("slides", [])) + 2
        )
        await callback.message.answer_document(
            FSInputFile(out_file),
            caption=caption,
            reply_markup=main_menu_keyboard(lang),
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
        await record_generation(callback.from_user.id, "slide", topic, theme_key, lang, count)
    except MissingApiKeyError:
        await status_msg.edit_text(TEXTS[lang]["no_api_key"])
    except Exception:
        await status_msg.edit_text(
            "⚠️ Xatolik yuz berdi, iltimos qayta urinib ko'ring." if lang == "uz" else "⚠️ Произошла ошибка, попробуйте ещё раз."
        )
        raise
    finally:
        if out_file and out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass


# ==================== REFERAT / MUSTAQIL ISH (DOCX) WIZARD ====================

@router.message(F.text.in_(ALL_REFERAT_BTNS))
async def start_referat_wizard(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await _get_lang(message)
    await state.set_state(GenStates.ref_type)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Referat" if lang == "uz" else "📄 Реферат",
                    callback_data="rtype:Referat" if lang == "uz" else "rtype:Реферат",
                ),
                InlineKeyboardButton(
                    text="📘 Mustaqil ish" if lang == "uz" else "📘 Самостоятельная работа",
                    callback_data="rtype:Mustaqil ish" if lang == "uz" else "rtype:Самостоятельная работа",
                ),
            ]
        ]
    )
    await message.answer(TEXTS[lang]["ask_referat_type"], reply_markup=kb)


@router.callback_query(GenStates.ref_type, F.data.startswith("rtype:"))
async def got_ref_type(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await _get_lang(callback)
    doc_type = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(doc_type=doc_type)
    await state.set_state(GenStates.ref_topic)
    await callback.answer()
    await callback.message.answer(TEXTS[lang]["ask_referat_topic"], reply_markup=cancel_keyboard(lang))


@router.message(GenStates.ref_topic)
async def got_ref_topic(message: Message, state: FSMContext) -> None:
    lang = await _get_lang(message)
    topic = (message.text or "").strip()
    if len(topic) < 4:
        await message.answer(TEXTS[lang]["topic_too_short"])
        return
    await state.update_data(topic=topic)
    await state.set_state(GenStates.ref_author)
    await message.answer(TEXTS[lang]["ask_author"], reply_markup=cancel_keyboard(lang, allow_skip=True))


@router.message(GenStates.ref_author)
async def got_ref_author(message: Message, state: FSMContext) -> None:
    lang = await _get_lang(message)
    raw = (message.text or "").strip()
    author = "" if raw in ALL_SKIP_BTNS else raw[:80]
    await state.update_data(author=author)
    await state.set_state(GenStates.ref_size)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5–7 bet" if lang == "uz" else "5–7 стр.", callback_data="rsize:short"),
                InlineKeyboardButton(text="10–12 bet" if lang == "uz" else "10–12 стр.", callback_data="rsize:medium"),
                InlineKeyboardButton(text="15+ bet" if lang == "uz" else "15+ стр.", callback_data="rsize:long"),
            ]
        ]
    )
    await message.answer(TEXTS[lang]["ask_referat_size"], reply_markup=kb)


@router.callback_query(GenStates.ref_size, F.data.startswith("rsize:"))
async def got_ref_size(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await _get_lang(callback)
    size_tier = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    topic = data["topic"]
    author = data.get("author", "")
    doc_type = data.get("doc_type", "Referat")

    status_msg = await callback.message.edit_text(TEXTS[lang]["progress_ai"])
    out_file: Path | None = None
    try:
        ref_data = await generate_referat_data(topic, author, doc_type, size_tier, lang)
        await status_msg.edit_text(TEXTS[lang]["progress_build"])

        out_file = GENERATED_DIR / _safe_filename(topic, "docx")
        await asyncio.to_thread(build_referat_docx, ref_data, doc_type, author, lang, out_file)

        await status_msg.edit_text(TEXTS[lang]["progress_send"])
        caption = TEXTS[lang]["referat_caption"].format(
            topic=html.escape(topic), doc_type=html.escape(doc_type)
        )
        await callback.message.answer_document(
            FSInputFile(out_file),
            caption=caption,
            reply_markup=main_menu_keyboard(lang),
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
        await record_generation(callback.from_user.id, "referat", topic, size_tier, lang, len(ref_data.get("sections", [])))
    except MissingApiKeyError:
        await status_msg.edit_text(TEXTS[lang]["no_api_key"])
    except Exception:
        await status_msg.edit_text(
            "⚠️ Xatolik yuz berdi, iltimos qayta urinib ko'ring." if lang == "uz" else "⚠️ Произошла ошибка, попробуйте ещё раз."
        )
        raise
    finally:
        if out_file and out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass
