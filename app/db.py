import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import firebase_admin
from aiogram import types
from firebase_admin import credentials, firestore

from app.config import FIREBASE_CREDENTIALS, FIREBASE_CREDENTIALS_JSON

logger = logging.getLogger("slayd_yasa_bot.db")

_db = None

# In-memory caches to keep bot responses <150ms instead of 1.5-3s Firestore round-trips
_settings_cache: dict[str, Any] | None = None
_settings_cached_at: float = 0.0
_SETTINGS_TTL_SEC = 60.0

_user_cache: dict[int, dict[str, Any]] = {}
_user_synced_at: dict[int, float] = {}
_USER_SYNC_TTL_SEC = 300.0  # Firestore'ga qayta yozish oralig'i (5 daqiqa)
_user_gens_cache: dict[int, list[dict[str, Any]]] = {}


def init_firestore():
    """Initializes Firebase Admin SDK and returns the Firestore client."""
    global _db
    if _db is not None:
        return _db

    if not firebase_admin._apps:
        if FIREBASE_CREDENTIALS_JSON:
            raw_fb = FIREBASE_CREDENTIALS_JSON.strip().strip("'\"")
            if "{" not in raw_fb:
                raw_fb += "=" * (-len(raw_fb) % 4)
                raw_fb = base64.b64decode(raw_fb).decode("utf-8")
            start = raw_fb.find("{")
            end = raw_fb.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_fb = raw_fb[start : end + 1]
            cred_dict = json.loads(raw_fb, strict=False)
            if isinstance(cred_dict.get("private_key"), str):
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
        elif FIREBASE_CREDENTIALS.exists():
            cred = credentials.Certificate(str(FIREBASE_CREDENTIALS))
        else:
            raise FileNotFoundError(
                f"\n[XATO] Firebase kalit fayli topilmadi: {FIREBASE_CREDENTIALS}\n"
                "Lokalda firebase-credentials.json faylini qo'ying yoki Vercel'da "
                "FIREBASE_CREDENTIALS_JSON environment variable'ni kiriting."
            )
        firebase_admin.initialize_app(cred)

    _db = firestore.client()
    return _db


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _upsert_user_sync(user_data: dict[str, Any]) -> None:
    db = init_firestore()
    uid = user_data["user_id"]
    doc_ref = db.collection("users").document(str(uid))
    snap = doc_ref.get()
    now = _now_utc()

    payload: dict[str, Any] = {
        "user_id": uid,
        "username": user_data["username"],
        "first_name": user_data["first_name"],
        "last_name": user_data["last_name"],
        "telegram_lang": user_data["telegram_lang"],
        "is_blocked": False,
        "last_seen_at": now,
    }
    if not snap.exists:
        payload["created_at"] = now
        payload["bot_lang"] = None
        doc_ref.set(payload)
    else:
        existing = snap.to_dict() or {}
        if uid in _user_cache and _user_cache[uid].get("bot_lang") is None:
            _user_cache[uid]["bot_lang"] = existing.get("bot_lang")
        doc_ref.set(payload, merge=True)


async def _background_upsert(user_data: dict[str, Any]) -> None:
    try:
        await asyncio.to_thread(_upsert_user_sync, user_data)
    except Exception as exc:
        logger.error("User sync xatosi (user_id=%s): %s", user_data["user_id"], exc)


def schedule_user_upsert(user: types.User) -> None:
    """Updates in-memory user cache immediately and syncs to Firestore in the background."""
    now_mono = time.monotonic()
    uid = user.id
    user_data = {
        "user_id": uid,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "telegram_lang": (user.language_code or "unknown").lower(),
    }

    cached = _user_cache.get(uid)
    last_sync = _user_synced_at.get(uid, 0.0)
    profile_changed = (
        cached is None
        or cached.get("username") != user_data["username"]
        or cached.get("first_name") != user_data["first_name"]
        or cached.get("telegram_lang") != user_data["telegram_lang"]
    )

    if cached is None:
        _user_cache[uid] = {**user_data, "bot_lang": None, "is_blocked": False}
    else:
        cached.update(user_data)
        cached["is_blocked"] = False

    if profile_changed or (now_mono - last_sync) >= _USER_SYNC_TTL_SEC:
        _user_synced_at[uid] = now_mono
        asyncio.create_task(_background_upsert(user_data))


def _set_user_lang_sync(user_id: int, lang: str) -> None:
    db = init_firestore()
    db.collection("users").document(str(user_id)).set(
        {"bot_lang": lang, "last_seen_at": _now_utc()}, merge=True
    )


async def set_user_lang(user_id: int, lang: str) -> None:
    if user_id in _user_cache:
        _user_cache[user_id]["bot_lang"] = lang
    asyncio.create_task(asyncio.to_thread(_set_user_lang_sync, user_id, lang))


def _get_user_sync(user_id: int) -> dict[str, Any] | None:
    db = init_firestore()
    snap = db.collection("users").document(str(user_id)).get()
    return snap.to_dict() if snap.exists else None


async def get_user(user_id: int) -> dict[str, Any] | None:
    if user_id in _user_cache:
        return _user_cache[user_id]
    data = await asyncio.to_thread(_get_user_sync, user_id)
    if data:
        _user_cache[user_id] = data
    return data


def _mark_user_blocked_sync(user_id: int, blocked: bool = True) -> None:
    db = init_firestore()
    db.collection("users").document(str(user_id)).set(
        {"is_blocked": blocked, "blocked_at": _now_utc() if blocked else None},
        merge=True,
    )


async def mark_user_blocked(user_id: int, blocked: bool = True) -> None:
    if user_id in _user_cache:
        _user_cache[user_id]["is_blocked"] = blocked
    await asyncio.to_thread(_mark_user_blocked_sync, user_id, blocked)


def _get_all_users_sync() -> list[dict[str, Any]]:
    db = init_firestore()
    return [doc.to_dict() for doc in db.collection("users").stream()]


async def get_all_users() -> list[dict[str, Any]]:
    return await asyncio.to_thread(_get_all_users_sync)


def _get_stats_sync() -> dict[str, Any]:
    db = init_firestore()
    docs = [d.to_dict() for d in db.collection("users").stream()]
    now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = len(docs)
    blocked = 0
    today_new = 0
    tg_langs: dict[str, int] = {}
    bot_langs: dict[str, int] = {"uz": 0, "ru": 0, "none": 0}

    for u in docs:
        if u.get("is_blocked"):
            blocked += 1

        created = u.get("created_at")
        if created and hasattr(created, "tzinfo"):
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= today_start:
                today_new += 1

        tl = u.get("telegram_lang") or "unknown"
        tg_langs[tl] = tg_langs.get(tl, 0) + 1

        bl = u.get("bot_lang")
        if bl in ("uz", "ru"):
            bot_langs[bl] += 1
        else:
            bot_langs["none"] += 1

    sorted_tg_langs = dict(
        sorted(tg_langs.items(), key=lambda item: item[1], reverse=True)
    )
    return {
        "total": total,
        "active": total - blocked,
        "blocked": blocked,
        "today_new": today_new,
        "tg_langs": sorted_tg_langs,
        "bot_langs": bot_langs,
    }


async def get_stats() -> dict[str, Any]:
    return await asyncio.to_thread(_get_stats_sync)


DEFAULT_SETTINGS: dict[str, Any] = {
    "maintenance_mode": True,
    "sub_enabled": False,
    "sub_channels": [],
}


def _get_settings_sync() -> dict[str, Any]:
    db = init_firestore()
    ref = db.collection("config").document("settings")
    snap = ref.get()
    if not snap.exists:
        ref.set(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    data = snap.to_dict() or {}
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


async def get_settings(force_refresh: bool = False) -> dict[str, Any]:
    global _settings_cache, _settings_cached_at
    now_mono = time.monotonic()
    if (
        not force_refresh
        and _settings_cache is not None
        and (now_mono - _settings_cached_at) < _SETTINGS_TTL_SEC
    ):
        return _settings_cache
    data = await asyncio.to_thread(_get_settings_sync)
    _settings_cache = data
    _settings_cached_at = now_mono
    return data


def _update_settings_sync(updates: dict[str, Any]) -> dict[str, Any]:
    db = init_firestore()
    ref = db.collection("config").document("settings")
    ref.set(updates, merge=True)
    return _get_settings_sync()


async def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
    global _settings_cache, _settings_cached_at
    data = await asyncio.to_thread(_update_settings_sync, updates)
    _settings_cache = data
    _settings_cached_at = time.monotonic()
    return data


# --- Error Telemetry in Firestore ---

def _log_error_sync(entry: dict[str, Any]) -> None:
    db = init_firestore()
    db.collection("error_logs").add(entry)


async def log_error_to_db(
    user_id: int | None,
    username: str | None,
    action: str,
    error_type: str,
    error_msg: str,
    tb: str,
) -> None:
    entry = {
        "timestamp": _now_utc(),
        "user_id": user_id,
        "username": username or "",
        "action": action[:300],
        "error_type": error_type,
        "error_msg": error_msg[:500],
        "traceback": tb[-2000:],
    }
    try:
        await asyncio.to_thread(_log_error_sync, entry)
    except Exception as exc:
        logger.error("Firestore error_logs ga yozib bo'lmadi: %s", exc)


def _get_recent_errors_sync(limit: int = 8) -> list[dict[str, Any]]:
    db = init_firestore()
    query = (
        db.collection("error_logs")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [doc.to_dict() for doc in query.stream()]


async def get_recent_errors(limit: int = 8) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_get_recent_errors_sync, limit)


# --- Generation History & Analytics ---

def _record_generation_sync(
    user_id: int,
    gen_type: str,
    topic: str,
    theme_or_size: str,
    lang: str,
    item_count: int,
) -> None:
    db = init_firestore()
    now = _now_utc()
    db.collection("generations").add(
        {
            "user_id": user_id,
            "type": gen_type,  # "slide" | "referat"
            "topic": topic[:200],
            "variant": theme_or_size,
            "lang": lang,
            "count": item_count,
            "created_at": now,
        }
    )
    field = "slides_count" if gen_type == "slide" else "referats_count"
    db.collection("users").document(str(user_id)).set(
        {field: firestore.Increment(1), "last_seen_at": now},
        merge=True,
    )


async def record_generation(
    user_id: int,
    gen_type: str,
    topic: str,
    theme_or_size: str,
    lang: str,
    item_count: int,
) -> None:
    entry = {
        "user_id": user_id,
        "type": gen_type,
        "topic": topic[:200],
        "variant": theme_or_size,
        "lang": lang,
        "count": item_count,
        "created_at": _now_utc(),
    }
    if user_id in _user_gens_cache:
        _user_gens_cache[user_id].insert(0, entry)
        _user_gens_cache[user_id] = _user_gens_cache[user_id][:20]
    try:
        await asyncio.to_thread(
            _record_generation_sync, user_id, gen_type, topic, theme_or_size, lang, item_count
        )
    except Exception as exc:
        logger.error("Generation log xatosi (user_id=%s): %s", user_id, exc)


def _get_user_generations_sync(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    db = init_firestore()
    from google.cloud.firestore_v1.base_query import FieldFilter

    docs = [
        d.to_dict()
        for d in db.collection("generations")
        .where(filter=FieldFilter("user_id", "==", user_id))
        .stream()
    ]
    docs.sort(key=lambda x: x.get("created_at") or _now_utc(), reverse=True)
    return docs[:limit]


async def get_user_generations(user_id: int, limit: int = 6) -> list[dict[str, Any]]:
    if user_id in _user_gens_cache:
        return _user_gens_cache[user_id][:limit]
    docs = await asyncio.to_thread(_get_user_generations_sync, user_id, max(limit, 10))
    _user_gens_cache[user_id] = docs
    return docs[:limit]


def _get_generation_totals_sync() -> dict[str, int]:
    db = init_firestore()
    slides = 0
    referats = 0
    for d in db.collection("generations").stream():
        t = (d.to_dict() or {}).get("type")
        if t == "slide":
            slides += 1
        elif t == "referat":
            referats += 1
    return {"slides": slides, "referats": referats, "total": slides + referats}


async def get_generation_totals() -> dict[str, int]:
    return await asyncio.to_thread(_get_generation_totals_sync)
