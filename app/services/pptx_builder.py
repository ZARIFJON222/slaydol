from datetime import datetime
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

THEMES: dict[str, dict[str, Any]] = {
    "obsidian_gold": {
        "name_uz": "🌑 Obsidian Gold",
        "name_ru": "🌑 Obsidian Gold",
        "bg": RGBColor(11, 13, 19),
        "card": RGBColor(21, 25, 36),
        "card_alt": RGBColor(28, 33, 47),
        "accent": RGBColor(232, 185, 96),
        "accent_soft": RGBColor(158, 120, 52),
        "fg": RGBColor(244, 239, 230),
        "muted": RGBColor(168, 162, 150),
        "border": RGBColor(48, 54, 72),
    },
    "ivory_editorial": {
        "name_uz": "🏛 Ivory Editorial",
        "name_ru": "🏛 Ivory Editorial",
        "bg": RGBColor(245, 240, 230),
        "card": RGBColor(255, 255, 255),
        "card_alt": RGBColor(236, 229, 215),
        "accent": RGBColor(142, 74, 36),
        "accent_soft": RGBColor(192, 122, 78),
        "fg": RGBColor(27, 25, 23),
        "muted": RGBColor(102, 94, 84),
        "border": RGBColor(219, 210, 195),
    },
    "cobalt_tech": {
        "name_uz": "🌊 Cobalt Tech",
        "name_ru": "🌊 Cobalt Tech",
        "bg": RGBColor(244, 247, 251),
        "card": RGBColor(255, 255, 255),
        "card_alt": RGBColor(232, 239, 252),
        "accent": RGBColor(29, 78, 216),
        "accent_soft": RGBColor(96, 165, 250),
        "fg": RGBColor(15, 23, 42),
        "muted": RGBColor(82, 96, 118),
        "border": RGBColor(209, 220, 238),
    },
    "emerald_nature": {
        "name_uz": "🌿 Emerald Nature",
        "name_ru": "🌿 Emerald Nature",
        "bg": RGBColor(242, 247, 244),
        "card": RGBColor(255, 255, 255),
        "card_alt": RGBColor(225, 240, 233),
        "accent": RGBColor(15, 118, 110),
        "accent_soft": RGBColor(52, 168, 154),
        "fg": RGBColor(17, 24, 39),
        "muted": RGBColor(75, 92, 86),
        "border": RGBColor(203, 224, 214),
    },
}

FONT_HEAD = "Segoe UI"
FONT_BODY = "Segoe UI"


def _set_bg(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_rect(slide, x, y, w, h, fill_color: RGBColor, border_color: RGBColor | None = None, rounded: bool = True):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if border_color:
        shp.line.color.rgb = border_color
        shp.line.width = Pt(1)
    else:
        shp.line.fill.background()
    return shp


def _add_text(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    size: int = 16,
    color: RGBColor = RGBColor(255, 255, 255),
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    font_name: str = FONT_BODY,
):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.name = font_name
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return tb


def _add_bullets(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    items: list[str],
    size: int,
    fg: RGBColor,
    accent: RGBColor,
    space_after: int = 12,
):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for idx, item in enumerate(items[:6]):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = 1.25
        r_mark = p.add_run()
        r_mark.text = "▪  "
        r_mark.font.name = FONT_BODY
        r_mark.font.size = Pt(size)
        r_mark.font.bold = True
        r_mark.font.color.rgb = accent

        r_txt = p.add_run()
        r_txt.text = str(item)
        r_txt.font.name = FONT_BODY
        r_txt.font.size = Pt(size)
        r_txt.font.color.rgb = fg


def _add_chrome(slide, th: dict[str, Any], idx: int, total: int, tag: str) -> None:
    # Top slim accent line + header tag + bottom clean watermark & slide counter
    _add_rect(slide, 0.7, 0.45, 0.45, 0.06, th["accent"], rounded=False)
    _add_text(slide, 1.25, 0.34, 6.0, 0.3, tag, size=11, color=th["muted"], bold=True)
    _add_text(slide, 0.7, 7.02, 5.0, 0.3, "@SlaydYasa_robot", size=10, color=th["muted"])
    _add_text(
        slide, 11.3, 7.02, 1.3, 0.3, f"{idx:02d} / {total:02d}", size=10, color=th["muted"], align=PP_ALIGN.RIGHT, bold=True
    )


def build_presentation(
    data: dict[str, Any],
    theme_key: str,
    author: str,
    lang: str,
    out_path: Path,
) -> Path:
    th = THEMES.get(theme_key, THEMES["obsidian_gold"])
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    body_slides = data.get("slides") or []
    total_slides = len(body_slides) + 2  # Cover + Closing
    tag = data.get("tag") or ("Taqdimot" if lang == "uz" else "Презентация")

    # --- 1. COVER SLIDE ---
    s_cov = prs.slides.add_slide(blank)
    _set_bg(s_cov, th["bg"])
    # Right decorative architectural card panel
    _add_rect(s_cov, 9.2, 0.65, 3.45, 6.2, th["card"], th["border"])
    _add_rect(s_cov, 9.2, 0.65, 3.45, 0.14, th["accent"], rounded=False)
    _add_text(s_cov, 9.55, 1.25, 2.8, 0.4, tag, size=13, color=th["accent"], bold=True)
    _add_text(
        s_cov,
        9.55,
        2.1,
        2.8,
        2.0,
        f"{total_slides}\n" + ("slayd" if lang == "uz" else "слайдов"),
        size=34,
        color=th["fg"],
        bold=True,
    )
    year_str = str(datetime.now().year)
    _add_text(s_cov, 9.55, 5.95, 2.8, 0.5, f"{year_str} · @SlaydYasa_robot", size=11, color=th["muted"])

    # Left hero typography
    _add_rect(s_cov, 0.85, 1.35, 1.1, 0.08, th["accent"], rounded=False)
    _add_text(
        s_cov, 0.85, 1.7, 7.9, 2.6, str(data.get("title", "")), size=38, color=th["fg"], bold=True, font_name=FONT_HEAD
    )
    _add_text(
        s_cov, 0.85, 4.45, 7.6, 1.1, str(data.get("subtitle", "")), size=17, color=th["muted"]
    )
    if author:
        lbl = "Tayyorladi:" if lang == "uz" else "Подготовил(а):"
        _add_rect(s_cov, 0.85, 5.9, 5.2, 0.72, th["card"], th["border"])
        _add_text(s_cov, 1.1, 6.08, 4.8, 0.4, f"{lbl}  {author}", size=13, color=th["fg"], bold=True)

    # --- 2. BODY SLIDES ---
    for i, sl in enumerate(body_slides, start=2):
        slide = prs.slides.add_slide(blank)
        _set_bg(slide, th["bg"])
        _add_chrome(slide, th, i, total_slides, tag)

        layout = sl.get("layout", "split_insight")
        title = str(sl.get("title", ""))
        _add_text(slide, 0.7, 0.85, 11.8, 0.8, title, size=26, color=th["fg"], bold=True, font_name=FONT_HEAD)

        if layout == "agenda":
            items = sl.get("items") or []
            for idx, item in enumerate(items[:4]):
                col = idx % 2
                row = idx // 2
                cx = 0.7 + col * 6.05
                cy = 2.0 + row * 2.25
                _add_rect(slide, cx, cy, 5.8, 1.95, th["card"], th["border"])
                _add_rect(slide, cx, cy, 0.14, 1.95, th["accent"], rounded=False)
                _add_text(slide, cx + 0.35, cy + 0.28, 1.0, 0.45, f"0{idx + 1}", size=20, color=th["accent"], bold=True)
                _add_text(slide, cx + 0.35, cy + 0.82, 5.1, 0.95, str(item), size=16, color=th["fg"], bold=True)

        elif layout == "three_cards":
            cards = sl.get("cards") or []
            for idx, card in enumerate(cards[:3]):
                cx = 0.7 + idx * 4.05
                _add_rect(slide, cx, 1.95, 3.8, 4.6, th["card"], th["border"])
                _add_rect(slide, cx, 1.95, 3.8, 0.12, th["accent"], rounded=False)
                _add_text(slide, cx + 0.3, 2.35, 3.2, 0.4, f"0{idx + 1}", size=14, color=th["accent"], bold=True)
                _add_text(slide, cx + 0.3, 2.85, 3.2, 0.9, str(card.get("heading", "")), size=18, color=th["fg"], bold=True)
                _add_text(slide, cx + 0.3, 3.85, 3.2, 2.4, str(card.get("body", "")), size=14, color=th["muted"])

        elif layout == "stat_spotlight":
            _add_rect(slide, 0.7, 1.95, 4.4, 4.5, th["card_alt"], th["border"])
            _add_text(
                slide,
                0.95,
                2.85,
                3.9,
                1.5,
                str(sl.get("stat_value", "95%")),
                size=54,
                color=th["accent"],
                bold=True,
                align=PP_ALIGN.CENTER,
            )
            _add_text(
                slide,
                0.95,
                4.5,
                3.9,
                1.0,
                str(sl.get("stat_label", "")),
                size=15,
                color=th["fg"],
                bold=True,
                align=PP_ALIGN.CENTER,
            )
            _add_rect(slide, 5.45, 1.95, 7.15, 4.5, th["card"], th["border"])
            _add_bullets(slide, 5.8, 2.35, 6.45, 3.8, sl.get("bullets") or [], 16, th["fg"], th["accent"], space_after=18)

        elif layout == "comparison":
            _add_rect(slide, 0.7, 1.95, 5.75, 4.55, th["card"], th["border"])
            _add_rect(slide, 0.7, 1.95, 5.75, 0.12, th["accent"], rounded=False)
            _add_text(slide, 1.0, 2.3, 5.1, 0.5, str(sl.get("left_title", "")), size=19, color=th["accent"], bold=True)
            _add_bullets(slide, 1.0, 2.95, 5.1, 3.2, sl.get("left_items") or [], 15, th["fg"], th["accent"])

            _add_rect(slide, 6.85, 1.95, 5.75, 4.55, th["card_alt"], th["border"])
            _add_rect(slide, 6.85, 1.95, 5.75, 0.12, th["accent_soft"], rounded=False)
            _add_text(slide, 7.15, 2.3, 5.1, 0.5, str(sl.get("right_title", "")), size=19, color=th["fg"], bold=True)
            _add_bullets(slide, 7.15, 2.95, 5.1, 3.2, sl.get("right_items") or [], 15, th["fg"], th["accent_soft"])

        elif layout == "timeline":
            steps = sl.get("steps") or []
            _add_rect(slide, 0.9, 3.25, 11.5, 0.06, th["accent_soft"], rounded=False)
            for idx, st in enumerate(steps[:4]):
                cx = 0.7 + idx * 3.05
                _add_rect(slide, cx + 1.15, 3.05, 0.45, 0.45, th["accent"], rounded=True)
                _add_text(slide, cx, 2.35, 2.8, 0.5, str(st.get("year", "")), size=18, color=th["accent"], bold=True, align=PP_ALIGN.CENTER)
                _add_rect(slide, cx, 3.75, 2.8, 2.65, th["card"], th["border"])
                _add_text(slide, cx + 0.2, 3.95, 2.4, 0.65, str(st.get("label", "")), size=15, color=th["fg"], bold=True)
                _add_text(slide, cx + 0.2, 4.7, 2.4, 1.5, str(st.get("desc", "")), size=13, color=th["muted"])

        elif layout == "conclusion":
            _add_rect(slide, 0.7, 1.9, 11.9, 3.5, th["card"], th["border"])
            _add_bullets(slide, 1.1, 2.25, 11.1, 2.9, sl.get("takeaways") or [], 17, th["fg"], th["accent"], space_after=16)
            _add_rect(slide, 0.7, 5.65, 11.9, 0.95, th["card_alt"], th["accent"])
            _add_text(slide, 1.05, 5.92, 11.2, 0.5, str(sl.get("closing_note", "")), size=16, color=th["fg"], bold=True)

        else:  # split_insight (default)
            _add_rect(slide, 0.7, 1.95, 7.4, 4.55, th["card"], th["border"])
            _add_bullets(slide, 1.05, 2.3, 6.7, 3.9, sl.get("bullets") or [], 16, th["fg"], th["accent"], space_after=16)

            _add_rect(slide, 8.45, 1.95, 4.15, 4.55, th["card_alt"], th["accent"])
            _add_text(
                slide,
                8.8,
                2.35,
                3.45,
                0.55,
                str(sl.get("insight_title") or ("Muhim xulosa" if lang == "uz" else "Ключевой вывод")),
                size=18,
                color=th["accent"],
                bold=True,
            )
            _add_text(slide, 8.8, 3.05, 3.45, 3.1, str(sl.get("insight_text", "")), size=15, color=th["fg"])

    # --- 3. CLOSING SLIDE ---
    s_end = prs.slides.add_slide(blank)
    _set_bg(s_end, th["bg"])
    _add_chrome(s_end, th, total_slides, total_slides, tag)
    thanks = "E'tiboringiz uchun rahmat!" if lang == "uz" else "Спасибо за внимание!"
    sub_thanks = (
        "Savollar va muhokama uchun ochiqmiz" if lang == "uz" else "Будем рады ответить на ваши вопросы"
    )
    _add_rect(s_end, 4.6, 2.55, 4.1, 0.08, th["accent"], rounded=False)
    _add_text(s_end, 1.2, 2.9, 10.9, 1.2, thanks, size=42, color=th["fg"], bold=True, align=PP_ALIGN.CENTER)
    _add_text(s_end, 1.2, 4.15, 10.9, 0.6, sub_thanks, size=18, color=th["muted"], align=PP_ALIGN.CENTER)
    if author:
        _add_text(s_end, 1.2, 5.1, 10.9, 0.5, author, size=15, color=th["accent"], bold=True, align=PP_ALIGN.CENTER)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path
