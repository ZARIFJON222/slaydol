from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.config import WEBAPP_URL

LANG_PROMPT_TEXT = (
    "🌐 Tugmalar va boshqaruv xabarlari tilini tanlash uchun quyidagi tugmalardan foydalaning."
)

MENU_BTNS = {
    "uz": {
        "slide": "📊 Slayd (Taqdimot) yasash",
        "referat": "📄 Referat / Mustaqil ish",
        "history": "📚 Mening ishlarim",
        "lang": "🌐 Tilni o'zgartirish",
        "cancel": "❌ Bekor qilish",
        "skip": "⏭ O'tkazib yuborish",
    },
    "ru": {
        "slide": "📊 Создать презентацию",
        "referat": "📄 Реферат / Самостоятельная",
        "history": "📚 Мои работы",
        "lang": "🌐 Сменить язык",
        "cancel": "❌ Отмена",
        "skip": "⏭ Пропустить",
    },
}

TEXTS = {
    "uz": {
        "maintenance": (
            "🛠 <b>Botda hozircha texnik ishlar olib borilmoqda.</b>\n\n"
            "Tez orada to'liq ishga tushamiz. Yangiliklarni kuzatib boring!"
        ),
        "sub_required": (
            "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgach, <b>«✅ Tekshirish»</b> tugmasini bosing."
        ),
        "sub_check_btn": "✅ Tekshirish",
        "sub_not_yet": "❌ Hali barcha kanallarga obuna bo'lmagansiz!",
        "lang_saved": (
            "✅ Til tanlandi: <b>O'zbekcha</b>\n\n"
            "👋 <b>SLAYD YASASH | Taqdimot & Referat</b> botiga xush kelibsiz!\n"
            "Hech qanday login yoki ortiqcha shartlarsiz — pastdagi tugmadan kerakli xizmatni tanlang 👇"
        ),
        "ask_slide_topic": (
            "📊 <b>Taqdimot (Slayd) yaratish</b>\n\n"
            "Taqdimot mavzusini yozib yuboring:\n"
            "<i>Masalan: «Sun'iy intellektning tibbiyotdagi o'rni» yoki «Amir Temur davlatchiligi»</i>"
        ),
        "ask_referat_type": (
            "📄 <b>Hujjat turini tanlang:</b>"
        ),
        "ask_referat_topic": (
            "📝 <b>Mavzuni yozib yuboring:</b>\n"
            "<i>Masalan: «O'zbekistonda raqamli iqtisodiyot rivoji»</i>"
        ),
        "ask_author": (
            "✍️ <b>Muallif ism-familiyasi (va guruh/OTM) ni kiriting:</b>\n"
            "<i>Masalan: Azizov Sardor, 204-guruh</i>\n\n"
            "Agar kerak bo'lmasa, pastdagi <b>«⏭ O'tkazib yuborish»</b> tugmasini bosing."
        ),
        "ask_slide_count": "🔢 <b>Nechta slayd kerak?</b>",
        "ask_slide_theme": "🎨 <b>Dizayn uslubini tanlang:</b>",
        "ask_referat_size": "📏 <b>Hujjat hajmini tanlang:</b>",
        "progress_ai": "⏳ <b>1/3:</b> Mavzu tahlil qilinmoqda va reja tuzilmoqda...",
        "progress_build": "🎨 <b>2/3:</b> Dizayn va sahifalar chizilmoqda...",
        "progress_send": "📤 <b>3/3:</b> Tayyor fayl yuborilmoqda!",
        "slide_caption": (
            "✅ <b>Taqdimotingiz tayyor!</b>\n\n"
            "📌 <b>Mavzu:</b> {topic}\n"
            "🎨 <b>Uslub:</b> {theme}\n"
            "📑 <b>Slaydlar:</b> {count} ta\n\n"
            "<i>@SlaydYasa_robot — Tez, bepul va sifatli</i>"
        ),
        "referat_caption": (
            "✅ <b>Hujjatingiz tayyor!</b> (GOST shrift: Times New Roman 14pt, 1.5 interval)\n\n"
            "📌 <b>Mavzu:</b> {topic}\n"
            "📄 <b>Turi:</b> {doc_type}\n\n"
            "<i>@SlaydYasa_robot — Tez, bepul va sifatli</i>"
        ),
        "no_api_key": (
            "⚠️ Hozircha AI xizmati kaliti (`GEMINI_API_KEY`) sozlanmagan.\n"
            "Admin tez orada ulaydi — noqulaylik uchun uzr!"
        ),
        "cancelled": "❌ Bekor qilindi. Bosh menyudasiz.",
        "history_empty": "📭 Hozircha yaratgan ishlaringiz yo'q. Birinchi slaydingizni hoziroq yarating!",
        "history_header": "📚 <b>Oxirgi yaratilgan ishlaringiz:</b>\n\n",
        "topic_too_short": "⚠️ Mavzu juda qisqa. Iltimos, kamida 4 ta harfdan iborat aniqroq mavzu yozing:",
    },
    "ru": {
        "maintenance": (
            "🛠 <b>В боте сейчас ведутся технические работы.</b>\n\n"
            "Скоро мы запустимся в полном объёме. Спасибо за понимание!"
        ),
        "sub_required": (
            "📢 <b>Для использования бота подпишитесь на следующие каналы:</b>\n\n"
            "После подписки нажмите кнопку <b>«✅ Проверить»</b>."
        ),
        "sub_check_btn": "✅ Проверить",
        "sub_not_yet": "❌ Вы ещё не подписались на все каналы!",
        "lang_saved": (
            "✅ Язык выбран: <b>Русский</b>\n\n"
            "👋 Добро пожаловать в <b>SLAYD YASASH | Taqdimot & Referat</b>!\n"
            "Без логинов и лишних условий — выберите нужный раздел ниже 👇"
        ),
        "ask_slide_topic": (
            "📊 <b>Создание презентации</b>\n\n"
            "Отправьте тему презентации:\n"
            "<i>Например: «Роль искусственного интеллекта в медицине»</i>"
        ),
        "ask_referat_type": "📄 <b>Выберите тип документа:</b>",
        "ask_referat_topic": (
            "📝 <b>Напишите тему работы:</b>\n"
            "<i>Например: «Развитие цифровой экономики»</i>"
        ),
        "ask_author": (
            "✍️ <b>Укажите автора (ФИО, группа/ВУЗ):</b>\n"
            "<i>Например: Азизов Сардор, гр. 204</i>\n\n"
            "Если не нужно — нажмите <b>«⏭ Пропустить»</b>."
        ),
        "ask_slide_count": "🔢 <b>Сколько слайдов нужно?</b>",
        "ask_slide_theme": "🎨 <b>Выберите стиль оформления:</b>",
        "ask_referat_size": "📏 <b>Выберите объём работы:</b>",
        "progress_ai": "⏳ <b>1/3:</b> Анализируем тему и составляем структуру...",
        "progress_build": "🎨 <b>2/3:</b> Оформляем дизайн и страницы...",
        "progress_send": "📤 <b>3/3:</b> Отправляем готовый файл!",
        "slide_caption": (
            "✅ <b>Ваша презентация готова!</b>\n\n"
            "📌 <b>Тема:</b> {topic}\n"
            "🎨 <b>Стиль:</b> {theme}\n"
            "📑 <b>Слайдов:</b> {count}\n\n"
            "<i>@SlaydYasa_robot — Быстро, бесплатно и качественно</i>"
        ),
        "referat_caption": (
            "✅ <b>Ваш документ готов!</b> (ГОСТ: Times New Roman 14pt, интервал 1.5)\n\n"
            "📌 <b>Тема:</b> {topic}\n"
            "📄 <b>Тип:</b> {doc_type}\n\n"
            "<i>@SlaydYasa_robot — Быстро, бесплатно и качественно</i>"
        ),
        "no_api_key": (
            "⚠️ Ключ AI (`GEMINI_API_KEY`) ещё не настроен.\n"
            "Администратор скоро подключит сервис!"
        ),
        "cancelled": "❌ Отменено. Вы в главном меню.",
        "history_empty": "📭 У вас пока нет готовых работ. Создайте первую презентацию прямо сейчас!",
        "history_header": "📚 <b>Ваши последние работы:</b>\n\n",
        "topic_too_short": "⚠️ Тема слишком короткая. Напишите подробнее (минимум 4 символа):",
    },
}


def resolve_lang(lang_code: str | None) -> str:
    if lang_code and lang_code.lower().startswith("ru"):
        return "ru"
    return "uz"


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )


def main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    b = MENU_BTNS[lang]
    rows = []
    if WEBAPP_URL.startswith("https://"):
        rows.append([KeyboardButton(text="✨ Web Studio (Mini App)", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.extend([
        [KeyboardButton(text=b["slide"]), KeyboardButton(text=b["referat"])],
        [KeyboardButton(text=b["history"]), KeyboardButton(text=b["lang"])],
    ])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )


def cancel_keyboard(lang: str, allow_skip: bool = False) -> ReplyKeyboardMarkup:
    b = MENU_BTNS[lang]
    rows = []
    if allow_skip:
        rows.append([KeyboardButton(text=b["skip"])])
    rows.append([KeyboardButton(text=b["cancel"])])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
