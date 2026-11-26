import asyncio
import html
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import ADMIN_IDS
from app.db import (
    get_all_users,
    get_generation_totals,
    get_recent_errors,
    get_settings,
    get_stats,
    mark_user_blocked,
    update_settings,
)
from app.logger import BOT_LOG_FILE, ERROR_LOG_FILE, tail_log

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminStates(StatesGroup):
    waiting_channel = State()
    waiting_broadcast = State()


def admin_main_kb(settings: dict[str, Any]) -> InlineKeyboardMarkup:
    maint_label = "🛠 Texnik ishlar: ✅ YOQIQ" if settings.get("maintenance_mode") else "🛠 Texnik ishlar: ❌ O'CHIQ"
    sub_label = "📢 Majburiy obuna: ✅ YOQIQ" if settings.get("sub_enabled") else "📢 Majburiy obuna: ❌ O'CHIQ"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats")],
            [InlineKeyboardButton(text=maint_label, callback_data="adm:toggle_maint")],
            [InlineKeyboardButton(text=sub_label, callback_data="adm:sub_menu")],
            [InlineKeyboardButton(text="📨 Ommaviy xabar yuborish", callback_data="adm:broadcast")],
            [InlineKeyboardButton(text="🪵 Loglar va Xatolar", callback_data="adm:logs")],
        ]
    )


def admin_back_kb(target: str = "adm:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data=target)]]
    )


async def safe_edit_text(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    settings = await get_settings()
    await message.answer(
        "⚙️ <b>Admin Panel — @SlaydYasa_robot</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=admin_main_kb(settings),
    )


@router.callback_query(F.data == "adm:home")
async def cb_admin_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    settings = await get_settings()
    await safe_edit_text(
        callback.message,
        "⚙️ <b>Admin Panel — @SlaydYasa_robot</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=admin_main_kb(settings),
    )


@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    await callback.answer()
    st, gen = await asyncio.gather(get_stats(), get_generation_totals())
    tg_lines = "\n".join(
        f"  • <code>{code}</code>: <b>{cnt}</b>" for code, cnt in list(st["tg_langs"].items())[:10]
    ) or "  • Hali yo'q"

    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{st['total']}</b>\n"
        f"🟢 Faol (yozish mumkin): <b>{st['active']}</b>\n"
        f"🔴 Bloklagan / o'chirgan: <b>{st['blocked']}</b>\n"
        f"🆕 Bugun qo'shilganlar: <b>{st['today_new']}</b>\n\n"
        "📦 <b>Yaratilgan ishlar:</b>\n"
        f"  • 📊 Slaydlar: <b>{gen['slides']}</b>\n"
        f"  • 📄 Referat / Mustaqil ish: <b>{gen['referats']}</b>\n\n"
        "🌐 <b>Botda tanlangan til:</b>\n"
        f"  • 🇺🇿 O'zbekcha: <b>{st['bot_langs']['uz']}</b>\n"
        f"  • 🇷🇺 Русский: <b>{st['bot_langs']['ru']}</b>\n"
        f"  • Tanlamagan: <b>{st['bot_langs']['none']}</b>\n\n"
        "📱 <b>Telegram ilovasi tili (tahlil uchun):</b>\n"
        f"{tg_lines}"
    )
    await safe_edit_text(callback.message, text, reply_markup=admin_back_kb())


@router.callback_query(F.data == "adm:toggle_maint")
async def cb_toggle_maint(callback: CallbackQuery) -> None:
    settings = await get_settings()
    new_val = not settings.get("maintenance_mode", False)
    updated = await update_settings({"maintenance_mode": new_val})
    status_txt = "yoqildi (oddiy userlarga yopiq)" if new_val else "o'chirildi (hamma uchun ochiq)"
    await callback.answer(f"🛠 Texnik ishlar {status_txt}!", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=admin_main_kb(updated))


# --- Majburiy Obuna Bo'limi ---

def sub_menu_kb(settings: dict[str, Any]) -> InlineKeyboardMarkup:
    enabled = settings.get("sub_enabled", False)
    channels = settings.get("sub_channels") or []
    rows = [
        [
            InlineKeyboardButton(
                text="🔴 Majburiy obunani O'CHIRISH" if enabled else "🟢 Majburiy obunani YOQISH",
                callback_data="adm:sub_toggle",
            )
        ],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm:sub_add")],
    ]
    for idx, ch in enumerate(channels):
        title = ch.get("title") or ch.get("id")
        rows.append([InlineKeyboardButton(text=f"🗑 O'chirish: {title}", callback_data=f"adm:sub_del:{idx}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_sub_menu_text(settings: dict[str, Any]) -> str:
    enabled = "✅ YOQIQ" if settings.get("sub_enabled") else "❌ O'CHIQ"
    channels = settings.get("sub_channels") or []
    ch_text = (
        "\n".join(f"{i+1}. <b>{c.get('title')}</b> (<code>{c.get('id')}</code>)" for i, c in enumerate(channels))
        if channels
        else "Hozircha kanallar qo'shilmagan."
    )
    return f"📢 <b>Majburiy obuna sozlamalari</b>\nHolati: <b>{enabled}</b>\n\n<b>Kanallar:</b>\n{ch_text}"


@router.callback_query(F.data == "adm:sub_menu")
async def cb_sub_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    settings = await get_settings()
    await callback.message.edit_text(format_sub_menu_text(settings), reply_markup=sub_menu_kb(settings))


@router.callback_query(F.data == "adm:sub_toggle")
async def cb_sub_toggle(callback: CallbackQuery) -> None:
    settings = await get_settings()
    new_val = not settings.get("sub_enabled", False)
    updated = await update_settings({"sub_enabled": new_val})
    await callback.answer("✅ Yangilandi!")
    await callback.message.edit_text(format_sub_menu_text(updated), reply_markup=sub_menu_kb(updated))


@router.callback_query(F.data.startswith("adm:sub_del:"))
async def cb_sub_del(callback: CallbackQuery) -> None:
    idx = int(callback.data.split(":")[-1])
    settings = await get_settings()
    channels = list(settings.get("sub_channels") or [])
    if 0 <= idx < len(channels):
        channels.pop(idx)
    updated = await update_settings({"sub_channels": channels})
    await callback.answer("🗑 Kanal o'chirildi!")
    await callback.message.edit_text(format_sub_menu_text(updated), reply_markup=sub_menu_kb(updated))


@router.callback_query(F.data == "adm:sub_add")
async def cb_sub_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_channel)
    await callback.answer()
    await callback.message.edit_text(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Avval botni o'sha kanalga <b>Admin</b> qilib qo'shing.\n"
        "Keyin kanal <code>@username</code> ini yuboring (yoki yopiq kanal bo'lsa: <code>-1001234567890 | https://t.me/+invite</code> formatida yuboring):",
        reply_markup=admin_back_kb("adm:sub_menu"),
    )


@router.message(AdminStates.waiting_channel)
async def fsm_save_channel(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if "|" in raw:
        chat_ref, custom_url = [p.strip() for p in raw.split("|", maxsplit=1)]
    else:
        chat_ref, custom_url = raw, ""

    chat_id: str | int = int(chat_ref) if chat_ref.lstrip("-").isdigit() else chat_ref
    try:
        chat = await message.bot.get_chat(chat_id)
    except Exception as exc:
        await message.answer(
            f"❌ Kanal topilmadi yoki bot kanalga admin qilinmagan.\nXato: <code>{exc}</code>\n\nQaytadan urinib ko'ring:"
        )
        return

    url = custom_url or (f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or ""))
    if not url:
        await message.answer("❌ Yopiq kanal uchun taklif havolasi kerak: <code>-100... | https://t.me/+...</code>")
        return

    settings = await get_settings()
    channels = list(settings.get("sub_channels") or [])
    channels.append({"id": str(chat.id), "title": chat.title or str(chat.id), "url": url})
    updated = await update_settings({"sub_channels": channels})
    await state.clear()
    await message.answer(
        f"✅ Kanal qo'shildi: <b>{chat.title}</b>\n\n{format_sub_menu_text(updated)}",
        reply_markup=sub_menu_kb(updated),
    )


# --- Ommaviy Xabar (Broadcast) Bo'limi ---

@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()
    await callback.message.edit_text(
        "📨 <b>Ommaviy xabar yuborish</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni (matn, rasm, video yoki post) yuboring:",
        reply_markup=admin_back_kb(),
    )


@router.message(AdminStates.waiting_broadcast)
async def fsm_broadcast_send(message: Message, state: FSMContext) -> None:
    await state.clear()
    users = await get_all_users()
    targets = [u["user_id"] for u in users if not u.get("is_blocked") and u.get("user_id")]

    status_msg = await message.answer(f"⏳ Yuborilmoqda... Jami maqsad: <b>{len(targets)}</b> ta foydalanuvchi.")
    sent = 0
    blocked = 0
    failed = 0

    for uid in targets:
        try:
            await message.copy_to(chat_id=uid)
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
            await mark_user_blocked(uid, True)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await message.copy_to(chat_id=uid)
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        "✅ <b>Ommaviy xabar yakunlandi!</b>\n\n"
        f"📤 Yetkazildi: <b>{sent}</b>\n"
        f"🚫 Bloklagan (bazada belgilandi): <b>{blocked}</b>\n"
        f"⚠️ Xatolik: <b>{failed}</b>",
        reply_markup=admin_back_kb(),
    )


# --- Loglar va Xatolar Bo'limi ---

def logs_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Oxirgi 20 qator (bot.log)", callback_data="adm:logs_tail")],
            [InlineKeyboardButton(text="⬇️ Log fayllarni yuklash", callback_data="adm:logs_download")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home")],
        ]
    )


@router.callback_query(F.data == "adm:logs")
async def cb_logs_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    errors = await get_recent_errors(limit=6)
    if not errors:
        err_txt = "✅ Hozircha hech qanday xatolik qayd etilmagan!"
    else:
        lines = []
        for e in errors:
            ts = e.get("timestamp")
            ts_str = ts.strftime("%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)[:16]
            uid = e.get("user_id") or "-"
            uname = f"@{e['username']}" if e.get("username") else ""
            msg = html.escape(str(e.get("error_msg", ""))[:100])
            lines.append(f"• <code>{ts_str}</code> | user <code>{uid}</code> {uname}\n  <code>{msg}</code>")
        err_txt = "\n".join(lines)

    await callback.message.edit_text(
        f"🪵 <b>Oxirgi Xatolar (Firestore)</b>\n\n{err_txt}",
        reply_markup=logs_menu_kb(),
    )


@router.callback_query(F.data == "adm:logs_tail")
async def cb_logs_tail(callback: CallbackQuery) -> None:
    await callback.answer()
    snippet = html.escape(tail_log(BOT_LOG_FILE, lines=20))
    if len(snippet) > 3600:
        snippet = snippet[-3600:]
    await callback.message.edit_text(
        f"📄 <b>bot.log (oxirgi 20 qator):</b>\n\n<pre>{snippet}</pre>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm:logs_tail")],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:logs")],
            ]
        ),
    )


@router.callback_query(F.data == "adm:logs_download")
async def cb_logs_download(callback: CallbackQuery) -> None:
    await callback.answer("📤 Yuborilmoqda...")
    sent_any = False
    for fpath in (BOT_LOG_FILE, ERROR_LOG_FILE):
        if fpath.exists() and fpath.stat().st_size > 0:
            await callback.message.answer_document(FSInputFile(fpath))
            sent_any = True
    if not sent_any:
        await callback.message.answer("ℹ️ Log fayllar hozircha bo'sh.")
