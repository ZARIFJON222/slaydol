import asyncio
import itertools
import json
import logging
import re
import threading
from typing import Any

import requests

from app.config import GEMINI_API_KEYS

logger = logging.getLogger("slayd_yasa_bot.ai")

_key_lock = threading.Lock()
_key_cycle = itertools.cycle(range(len(GEMINI_API_KEYS))) if GEMINI_API_KEYS else None
_MODELS_FALLBACK = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemma-4-31b-it"]
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class MissingApiKeyError(RuntimeError):
    pass


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    # Remove trailing commas before } or ] that LLMs occasionally emit
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text, strict=False)


def _call_gemini_with_failover(prompt: str, temperature: float, required_key: str | None = None) -> dict[str, Any]:
    """Rotates across Gemini API keys and model fallbacks, validating & repairing JSON before returning."""
    if not GEMINI_API_KEYS or _key_cycle is None:
        raise MissingApiKeyError("GEMINI_API_KEYS sozlanmagan!")

    with _key_lock:
        start_idx = next(_key_cycle)

    n = len(GEMINI_API_KEYS)
    last_exc: Exception | None = None

    for model_name in _MODELS_FALLBACK:
        is_gemma = model_name.startswith("gemma-")
        gen_cfg: dict[str, Any] = {"temperature": temperature}
        if not is_gemma:
            gen_cfg["responseMimeType"] = "application/json"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_cfg,
        }
        url = f"{_GEMINI_BASE}/{model_name}:generateContent"

        for offset in range(n):
            idx = (start_idx + offset) % n
            key = GEMINI_API_KEYS[idx]
            try:
                resp = requests.post(f"{url}?key={key}", json=payload, timeout=45)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:220]}")
                raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = _extract_json(raw_text)
                if not isinstance(parsed, dict) or (required_key and required_key not in parsed):
                    raise ValueError(f"JSON da '{required_key}' maydoni topilmadi")
                return parsed
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "%s | key #%d xato (%s): %s", model_name, idx + 1, type(exc).__name__, exc
                )

    raise RuntimeError(f"Barcha modellar va kalitlar ishlamadi: {last_exc}")


def _generate_slide_deck_sync(
    topic: str, author: str, slide_count: int, lang: str
) -> dict[str, Any]:
    lang_label = "Uzbek (Latin script, natural academic & modern Uzbek)" if lang == "uz" else "Russian (natural academic & modern Russian)"
    body_count = max(4, slide_count - 2)  # Cover + Closing handled cleanly

    prompt = f"""You are a world-class presentation designer and academic researcher.
Create a complete, factual, engaging {slide_count}-slide presentation on the topic:
"{topic}"

Output Language: {lang_label}
Author: "{author or ('@SlaydYasa_robot' if lang == 'uz' else '@SlaydYasa_robot')}"

Return ONLY valid JSON matching this exact schema (no markdown commentary outside JSON):
{{
  "title": "Compelling concise presentation title (4-8 words)",
  "subtitle": "Crisp 1-sentence subtitle (8-14 words)",
  "tag": "Short subject category (1-3 words, e.g. Texnologiya / Tarix / Iqtisodiyot)",
  "slides": [
    // Generate EXACTLY {body_count} body slides, mixing these 6 layout types in a logical narrative order:
    // 1) "agenda": {{"layout":"agenda","title":"...","items":["01 ...","02 ...","03 ...","04 ..."]}}
    // 2) "split_insight": {{"layout":"split_insight","title":"...","bullets":["...","...","...","..."],"insight_title":"...","insight_text":"2-3 crisp sentences"}}
    // 3) "three_cards": {{"layout":"three_cards","title":"...","cards":[{{"heading":"...","body":"1-2 concise sentences"}},{{"heading":"...","body":"..."}},{{"heading":"...","body":"..."}}]}}
    // 4) "stat_spotlight": {{"layout":"stat_spotlight","title":"...","stat_value":"e.g. 84% or 1428","stat_label":"3-5 words","bullets":["...","...","..."]}}
    // 5) "comparison": {{"layout":"comparison","title":"...","left_title":"...","left_items":["...","...","..."],"right_title":"...","right_items":["...","...","..."]}}
    // 6) "timeline": {{"layout":"timeline","title":"...","steps":[{{"year":"...","label":"...","desc":"short"}},{{"year":"...","label":"...","desc":"short"}},{{"year":"...","label":"...","desc":"short"}},{{"year":"...","label":"...","desc":"short"}}]}}
    // Last body slide MUST be "conclusion":
    // 7) "conclusion": {{"layout":"conclusion","title":"...","takeaways":["...","...","..."],"closing_note":"1 strong concluding sentence"}}
  ]
}}

Rules:
- Keep every bullet concise (8-15 words) so slides look airy, readable, and designer-made—never walls of text!
- First body slide should be "agenda", last body slide must be "conclusion".
- Use real historical/scientific facts where relevant; never invent fake statistics."""

    return _call_gemini_with_failover(prompt, temperature=0.65, required_key="slides")


async def generate_slide_deck_data(
    topic: str, author: str, slide_count: int, lang: str
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _generate_slide_deck_sync, topic, author, slide_count, lang
    )


def _generate_referat_sync(
    topic: str, author: str, doc_type: str, size_tier: str, lang: str
) -> dict[str, Any]:
    lang_label = "Uzbek (Latin script, formal academic Uzbek)" if lang == "uz" else "Russian (formal academic Russian)"

    tier_cfg = {
        "short": (3, 2, "5-7 pages"),
        "medium": (4, 3, "10-12 pages"),
        "long": (5, 3, "15+ pages"),
    }
    chapters_n, paras_per_ch, target_desc = tier_cfg.get(size_tier, (4, 2, "10-12 pages"))

    prompt = f"""You are a university professor and academic writer.
Write a well-structured, thorough, formal academic {doc_type} ({target_desc} density) on the topic:
"{topic}"

Output Language: {lang_label}

Return ONLY valid JSON matching this exact schema:
{{
  "title": "Formal academic title",
  "subject_area": "Academic discipline name (e.g. Axborot texnologiyalari / Iqtisodiyot)",
  "intro": [
    "Paragraph 1 of introduction (relevance and goal of the topic, 4-6 sentences)",
    "Paragraph 2 of introduction (scope and methodology, 4-5 sentences)"
  ],
  "sections": [
    // EXACTLY {chapters_n} rich chapters:
    {{
      "heading": "Chapter title without number prefix",
      "paragraphs": [
        // EXACTLY {paras_per_ch} detailed academic paragraphs (5-7 sentences each) with concrete facts, definitions, and analysis.
      ]
    }}
  ],
  "conclusion": [
    "Paragraph 1 summarizing key findings (4-6 sentences)",
    "Paragraph 2 with practical recommendations (4-5 sentences)"
  ],
  "references": [
    "5 real, standard academic books/articles/resources formatted cleanly"
  ]
}}"""

    return _call_gemini_with_failover(prompt, temperature=0.6, required_key="sections")


async def generate_referat_data(
    topic: str, author: str, doc_type: str, size_tier: str, lang: str
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _generate_referat_sync, topic, author, doc_type, size_tier, lang
    )
